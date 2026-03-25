"""
render_engine.py — Blender Headless Rendering Script.

Invoked by main.py via:
  blender -b Master_Scene.blend -P render_engine.py -- --scene_data path/to/scene.json

Handles:
  1. Character FBX import
  2. Animation FBX import + bone retargeting (CMU → Mixamo)
  3. Animation-to-audio sync (speed matching)
  4. Background image swap on Background_Plane
  5. MP4 render output
"""
import bpy
import json
import math
import sys
from pathlib import Path
from mathutils import Vector, Euler, Quaternion

# ── Parse CLI args (after the "--" separator) ──
argv = sys.argv
if "--" in argv:
    argv = argv[argv.index("--") + 1:]
else:
    argv = []

import argparse

parser = argparse.ArgumentParser(description="Blender Render Engine")
parser.add_argument("--scene_data", type=str, required=True, help="Path to scene JSON")
parser.add_argument("--help-only", action="store_true", help="Print help and exit")
args = parser.parse_args(argv)

if args.help_only:
    parser.print_help()
    sys.exit(0)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  BONE MAP: CMU Mocap → Mixamo (mixamorig:) hierarchy
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BONE_MAP = {
    # Root & Torso
    "hip":        "mixamorig:Hips",
    "abdomen":    "mixamorig:Spine",
    "chest":      "mixamorig:Spine1",
    "neck":       "mixamorig:Neck",
    "head":       "mixamorig:Head",

    # Left Arm
    "lshldr":     "mixamorig:LeftArm",
    "lforearm":   "mixamorig:LeftForeArm",
    "lhand":      "mixamorig:LeftHand",

    # Right Arm
    "rshldr":     "mixamorig:RightArm",
    "rforearm":   "mixamorig:RightForeArm",
    "rhand":      "mixamorig:RightHand",

    # Left Leg
    "lthigh":     "mixamorig:LeftUpLeg",
    "lshin":      "mixamorig:LeftLeg",
    "lfoot":      "mixamorig:LeftFoot",

    # Right Leg
    "rthigh":     "mixamorig:RightUpLeg",
    "rshin":      "mixamorig:RightLeg",
    "rfoot":      "mixamorig:RightFoot",
}

# Reverse map for looking up CMU name from Mixamo name
REVERSE_BONE_MAP = {v: k for k, v in BONE_MAP.items()}


def get_target_bone(source_name: str) -> str | None:
    """
    Resolve a CMU bone name to the Mixamo target bone.
    Case-insensitive, handles common variations.
    """
    clean = source_name.lower().strip().replace(" ", "").replace("_", "")
    # Direct lookup
    if clean in BONE_MAP:
        return BONE_MAP[clean]
    # Try without common prefixes
    for prefix in ["cmu:", "bvh:", ""]:
        key = clean.removeprefix(prefix)
        if key in BONE_MAP:
            return BONE_MAP[key]
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  1. LOAD SCENE DATA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def load_scene_data(json_path: str) -> dict:
    """Load and validate the scene JSON file."""
    with open(json_path, "r") as f:
        data = json.load(f)

    required = ["character_fbx", "animation_fbx", "background_image", "audio_duration"]
    for key in required:
        if key not in data:
            raise ValueError(f"Missing required key: '{key}' in scene data")

    print(f"  📋 Scene {data.get('id', '?')}: audio={data['audio_duration']:.1f}s")
    return data


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  2. CHARACTER IMPORT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def import_character(fbx_path: str) -> bpy.types.Object:
    """Import the rigged character FBX and return the armature."""
    print(f"  🐢 Importing character: {Path(fbx_path).name}")

    # Clear selection
    bpy.ops.object.select_all(action="DESELECT")

    # Import
    bpy.ops.import_scene.fbx(
        filepath=fbx_path,
        use_anim=False,  # Don't import animation from character file
        automatic_bone_orientation=True,
        ignore_leaf_bones=True,
    )

    # Find the armature among imported objects
    armature = None
    for obj in bpy.context.selected_objects:
        if obj.type == "ARMATURE":
            armature = obj
            break

    if armature is None:
        raise RuntimeError(f"No armature found in {fbx_path}")

    # Position at origin
    armature.location = (0, 0, 0)
    armature.rotation_euler = (0, 0, 0)

    print(f"  ✅ Character loaded: {armature.name} ({len(armature.data.bones)} bones)")
    return armature


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  3. ANIMATION IMPORT + RETARGETING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def import_and_retarget_animation(anim_fbx: str, char_armature: bpy.types.Object) -> int:
    """
    Import a CMU mocap FBX and retarget its animation to the character armature.
    Returns: number of frames in the retargeted animation.
    """
    print(f"  🎭 Importing animation: {Path(anim_fbx).name}")

    # Remember existing actions
    existing_actions = set(bpy.data.actions.keys())

    # Import animation FBX
    bpy.ops.import_scene.fbx(
        filepath=anim_fbx,
        use_anim=True,
        automatic_bone_orientation=True,
        ignore_leaf_bones=True,
    )

    # Find the new action (the animation data)
    new_actions = set(bpy.data.actions.keys()) - existing_actions
    if not new_actions:
        raise RuntimeError("No animation action found in FBX")

    # Find the imported armature (source)
    source_armature = None
    for obj in bpy.context.selected_objects:
        if obj.type == "ARMATURE" and obj != char_armature:
            source_armature = obj
            break

    source_action_name = list(new_actions)[0]
    source_action = bpy.data.actions[source_action_name]
    print(f"  📎 Found action: {source_action_name} ({source_action.frame_range[0]:.0f}-{source_action.frame_range[1]:.0f})")

    # ── Retarget: copy keyframes from CMU bones to Mixamo bones ──
    # Create a new action for the character
    retargeted_action = bpy.data.actions.new(name=f"retargeted_{source_action_name}")
    char_armature.animation_data_create()
    char_armature.animation_data.action = retargeted_action

    mapped_bones = 0
    total_keyframes = 0

    for fcurve in source_action.fcurves:
        # FCurve data_path format: 'pose.bones["BoneName"].rotation_quaternion'
        if "pose.bones" not in fcurve.data_path:
            continue

        # Extract bone name
        try:
            bone_name = fcurve.data_path.split('"')[1]
        except IndexError:
            continue

        # Get Mixamo target bone name
        target_bone = get_target_bone(bone_name)
        if target_bone is None:
            continue

        # Check if target bone exists in character
        # Handle cases where the rig has "mixamorig:Hips" vs just "Hips"
        if target_bone not in char_armature.data.bones:
            clean_target = target_bone.replace("mixamorig:", "")
            if clean_target in char_armature.data.bones:
                target_bone = clean_target
            else:
                continue

        pbone = char_armature.pose.bones[target_bone]
        property_part = fcurve.data_path.split(".")[-1]  # e.g., rotation_quaternion

        # CRITICAL FIX: Ensure the bone's rotation_mode matches the FCurve type
        # Otherwise Blender silently ignores the animation and leaves it in A-Pose
        if "euler" in property_part.lower() and pbone.rotation_mode != 'XYZ':
            pbone.rotation_mode = 'XYZ'
        elif "quaternion" in property_part.lower() and pbone.rotation_mode != 'QUATERNION':
            pbone.rotation_mode = 'QUATERNION'

        # Build the new data path
        new_data_path = f'pose.bones["{target_bone}"].{property_part}'

        # ROOT MOTION LOCK: If it's the Hips and it's a location property,
        # we skip X and Y (horizontal) to keep the character in the 9:16 frame.
        # We keep Z (index 2) so they can still bounce up and down.
        if target_bone.lower().endswith("hips") and "location" in property_part:
            if fcurve.array_index in [0, 1]:  # X and Y translation
                continue

        # Create new FCurve and copy keyframes
        new_fcurve = retargeted_action.fcurves.new(
            data_path=new_data_path,
            index=fcurve.array_index,
        )

        for kp in fcurve.keyframe_points:
            new_fcurve.keyframe_points.insert(frame=kp.co[0], value=kp.co[1])
            total_keyframes += 1

        mapped_bones += 1

    # Clean up: remove the imported source armature
    if source_armature:
        bpy.data.objects.remove(source_armature, do_unlink=True)

    # Get frame count
    frame_start = int(retargeted_action.frame_range[0])
    frame_end = int(retargeted_action.frame_range[1])
    num_frames = frame_end - frame_start

    print(f"  ✅ Retargeted {mapped_bones} bone channels, {total_keyframes} keyframes")
    print(f"  📐 Frame range: {frame_start}-{frame_end} ({num_frames} frames)")
    return num_frames


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  4. ANIMATION-TO-AUDIO SYNC
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def sync_animation_to_audio(char_armature: bpy.types.Object, audio_duration: float, fps: int = 30):
    """
    Adjust animation playback speed to match audio duration.
    Uses NLA strip scaling for precise timing.
    """
    target_frames = int(audio_duration * fps)

    action = char_armature.animation_data.action
    if action is None:
        print("  ⚠️ No action to sync — skipping")
        return target_frames

    original_start = int(action.frame_range[0])
    original_end = int(action.frame_range[1])
    original_frames = original_end - original_start

    if original_frames <= 0:
        print("  ⚠️ Animation has 0 frames — skipping sync")
        return target_frames

    # Calculate scale factor
    scale_factor = original_frames / target_frames if target_frames > 0 else 1.0

    # ── Method: push action to NLA and scale the strip ──
    anim_data = char_armature.animation_data

    # Create NLA track
    track = anim_data.nla_tracks.new()
    track.name = "SyncedAnimation"

    # Push the action into the NLA as a strip
    strip = track.strips.new(name="SyncStrip", start=1, action=action)
    strip.frame_start = 1
    strip.frame_end = target_frames + 1
    strip.scale = scale_factor
    strip.repeat = 1.0
    strip.use_auto_blend = False

    # Clear the active action (NLA takes over)
    anim_data.action = None

    # Set scene frame range
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = target_frames

    print(f"  ⏱️ Synced: {original_frames}f → {target_frames}f "
          f"(scale={scale_factor:.3f}, audio={audio_duration:.1f}s)")
    return target_frames


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  5. BACKGROUND SWAP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def swap_background(image_path: str):
    """Replace the Background_Plane's texture with the given image."""
    print(f"  🖼️ Swapping background: {Path(image_path).name}")

    # Find the Background_Plane
    plane = bpy.data.objects.get("Background_Plane")
    if plane is None:
        print("  ⚠️ Background_Plane not found in scene — skipping")
        return

    # Find the material
    mat = bpy.data.materials.get("Background_Material")
    if mat is None or not mat.use_nodes:
        print("  ⚠️ Background_Material not found — skipping")
        return

    # Find the Image Texture node
    tex_node = mat.node_tree.nodes.get("Background_Texture")
    if tex_node is None:
        # Try to find any ShaderNodeTexImage
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE":
                tex_node = node
                break

    if tex_node is None:
        print("  ⚠️ No Image Texture node found — creating one")
        tex_node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex_node.name = "Background_Texture"
        # Wire it up
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            mat.node_tree.links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

    # Load the image
    img = bpy.data.images.load(image_path, check_existing=True)
    tex_node.image = img

    print(f"  ✅ Background set: {img.name} ({img.size[0]}×{img.size[1]})")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  6. RENDER CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def configure_render(output_path: str, resolution: tuple = (1080, 1920), fps: int = 30):
    """Configure Blender render settings for fast MP4 output."""
    scene = bpy.context.scene

    # Resolution
    scene.render.resolution_x = resolution[0]
    scene.render.resolution_y = resolution[1]
    scene.render.resolution_percentage = 100
    scene.render.fps = fps

    # ── Try to enable Metal GPU (Apple Silicon / AMD) ──
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.refresh_devices()
        # Enable all available GPU devices
        for device in prefs.devices:
            if device.type in ("METAL", "OPTIX", "CUDA", "HIP"):
                device.use = True
                print(f"  🖥️ GPU enabled: {device.name} ({device.type})")
        bpy.context.preferences.addons["cycles"].preferences.compute_device_type = "METAL"
    except Exception as e:
        print(f"  ℹ️ GPU setup skipped (using CPU): {e}")

    # ── EEVEE Next — fast, high quality ──
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    # 16 samples + denoising = visually identical to 64, ~4x faster
    scene.eevee.taa_render_samples = 16
    
    # Disable EEVEE Next Raytracing (this destroys CPU performance if left on)
    try:
        scene.eevee.use_raytracing = False
    except Exception:
        pass
        
    # Disable Volumetrics (massive speedup)
    try:
        scene.eevee.use_volumetric = False
    except Exception:
        pass

    # Enable denoiser to compensate for lower samples
    try:
        scene.eevee.use_taa_reprojection = True
    except Exception:
        pass

    # ── Motion blur OFF (saves ~30% render time) ──
    scene.render.use_motion_blur = False

    # Output format: FFmpeg MP4
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.ffmpeg.audio_codec = "NONE"  # Audio added later by FFmpeg

    # Output path
    scene.render.filepath = output_path

    print(f"  🎥 Render config: {resolution[0]}×{resolution[1]} @ {fps}fps | EEVEE 16spp")
    print(f"  📁 Output: {output_path}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN ENTRY POINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    print("\n" + "=" * 50)
    print("🎬 render_engine.py — Blender Headless Renderer")
    print("=" * 50)

    # 1. Load scene data
    scene = load_scene_data(args.scene_data)

    fps = scene.get("fps", 30)
    resolution = tuple(scene.get("resolution", [1080, 1920]))
    output_path = scene.get("output_video", "/tmp/render.mp4")

    # 2. Import character
    char_armature = import_character(scene["character_fbx"])

    # 3. Import and retarget animation
    anim_frames = import_and_retarget_animation(scene["animation_fbx"], char_armature)

    # 4. Sync animation speed to audio duration
    final_frames = sync_animation_to_audio(
        char_armature,
        scene["audio_duration"],
        fps=fps,
    )

    # 5. Swap background
    bg_path = scene.get("background_image", "")
    if bg_path and Path(bg_path).exists():
        swap_background(bg_path)
    else:
        print(f"  ⚠️ Background image not found: {bg_path}")

    # 6. Configure render
    configure_render(output_path, resolution=resolution, fps=fps)

    # 7. RENDER!
    print(f"\n  🎬 Rendering {final_frames} frames...")
    bpy.ops.render.render(animation=True)

    print(f"\n  ✅ Render complete: {output_path}")
    print("=" * 50 + "\n")


# Guard: only run when called as a script (not when imported)
main()
