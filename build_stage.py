"""
build_stage.py — Auto-generates Master_Scene.blend from scratch.
Run via:  blender -b -P build_stage.py
Creates a 9:16 stage with camera, 3-point lighting, and a background plane.
"""
import bpy
import math
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_PATH = PROJECT_ROOT / "Master_Scene.blend"


def clear_scene():
    """Delete every object in the default scene."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    # Remove orphan data blocks
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)
    for block in bpy.data.lights:
        if block.users == 0:
            bpy.data.lights.remove(block)
    for block in bpy.data.cameras:
        if block.users == 0:
            bpy.data.cameras.remove(block)


def create_camera():
    """Create a 9:16 camera positioned to frame a character."""
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = 50
    cam_data.sensor_fit = "VERTICAL"

    cam_obj = bpy.data.objects.new("Camera", cam_data)
    bpy.context.collection.objects.link(cam_obj)

    # Position: in front of character, slightly above eye level
    cam_obj.location = (0.0, -4.0, 1.2)
    # Point toward scene center (0, 0, 0.8) — roughly character chest height
    direction = cam_obj.location.copy()
    direction.x = 0 - direction.x
    direction.y = 0 - direction.y
    direction.z = 0.8 - direction.z

    rot_quat = direction.to_track_quat("-Z", "Y")
    cam_obj.rotation_euler = rot_quat.to_euler()

    bpy.context.scene.camera = cam_obj

    # Resolution
    bpy.context.scene.render.resolution_x = 1080
    bpy.context.scene.render.resolution_y = 1920
    bpy.context.scene.render.resolution_percentage = 100

    print("  ✅ Camera created (1080×1920, lens=50mm)")
    return cam_obj


def create_lighting():
    """3-point lighting: Key (warm), Fill (cool), Back (rim)."""
    lights = []

    # ── Key Light (main, warm, upper-right) ──
    key_data = bpy.data.lights.new("Key_Light", type="AREA")
    key_data.energy = 800
    key_data.color = (1.0, 0.95, 0.85)  # Warm white
    key_data.size = 3.0
    key_obj = bpy.data.objects.new("Key_Light", key_data)
    bpy.context.collection.objects.link(key_obj)
    key_obj.location = (2.5, -2.0, 3.0)
    key_obj.rotation_euler = (math.radians(50), 0, math.radians(30))
    lights.append(key_obj)

    # ── Fill Light (soft, cool, left side) ──
    fill_data = bpy.data.lights.new("Fill_Light", type="AREA")
    fill_data.energy = 300
    fill_data.color = (0.85, 0.9, 1.0)  # Cool white
    fill_data.size = 4.0
    fill_obj = bpy.data.objects.new("Fill_Light", fill_data)
    bpy.context.collection.objects.link(fill_obj)
    fill_obj.location = (-2.0, -1.5, 2.0)
    fill_obj.rotation_euler = (math.radians(45), 0, math.radians(-20))
    lights.append(fill_obj)

    # ── Back / Rim Light (behind character, high) ──
    back_data = bpy.data.lights.new("Back_Light", type="AREA")
    back_data.energy = 500
    back_data.color = (1.0, 1.0, 1.0)
    back_data.size = 2.0
    back_obj = bpy.data.objects.new("Back_Light", back_data)
    bpy.context.collection.objects.link(back_obj)
    back_obj.location = (0.0, 2.0, 3.5)
    back_obj.rotation_euler = (math.radians(130), 0, 0)
    lights.append(back_obj)

    print("  ✅ 3-point lighting created (Key/Fill/Back)")
    return lights


def create_background_plane():
    """
    Create a vertical plane behind the character to display AI-generated backgrounds.
    Material named 'Background_Material' with an Image Texture node.
    """
    # Create plane mesh
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 2.0, 1.0))
    plane = bpy.context.active_object
    plane.name = "Background_Plane"

    # Scale to 9:16 vertical ratio — wide enough to fill camera view
    plane.scale = (4.0, 1.0, 7.1)  # X = width, Z = height (since we'll rotate)
    # Rotate to face the camera (stand upright, facing -Y)
    plane.rotation_euler = (math.radians(90), 0, 0)
    # Apply transforms
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    # ── Material Setup ──
    mat = bpy.data.materials.new("Background_Material")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Clear defaults
    for node in nodes:
        nodes.remove(node)

    # Principled BSDF
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (300, 0)
    # Make it fully emissive so lighting doesn't darken the background
    bsdf.inputs["Roughness"].default_value = 1.0

    # Image Texture node (placeholder — render_engine.py swaps the image)
    tex_node = nodes.new("ShaderNodeTexImage")
    tex_node.name = "Background_Texture"
    tex_node.label = "Background_Texture"
    tex_node.location = (0, 0)

    # Material Output
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (600, 0)

    # Wire: Image → Base Color → Output
    links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    # Assign to plane
    plane.data.materials.append(mat)

    # UV unwrap for correct image mapping
    bpy.context.view_layer.objects.active = plane
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.unwrap(method="ANGLE_BASED")
    bpy.ops.object.mode_set(mode="OBJECT")

    print("  ✅ Background_Plane created with Background_Material (Image Texture ready)")
    return plane


def configure_scene_defaults():
    """Set EEVEE as render engine and configure scene-level defaults."""
    scene = bpy.context.scene

    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.film_transparent = False
    scene.render.fps = 30

    scene.eevee.taa_render_samples = 64

    # World background as dark fallback
    world = bpy.data.worlds.get("World")
    if world is None:
        world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs["Color"].default_value = (0.02, 0.02, 0.02, 1.0)
        bg_node.inputs["Strength"].default_value = 0.5

    print("  ✅ Scene configured (EEVEE, 30fps, dark world BG)")


def main():
    print("\n🎬 build_stage.py — Generating Master_Scene.blend\n")

    clear_scene()
    print("  🗑️  Scene cleared")

    create_camera()
    create_lighting()
    create_background_plane()
    configure_scene_defaults()

    # Save
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_PATH))
    print(f"\n✅ Master_Scene.blend saved to: {OUTPUT_PATH}\n")


if __name__ == "__main__":
    main()
