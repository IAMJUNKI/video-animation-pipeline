import bpy
import json
import sys

def debug_bone_map():
    char_path = "/Users/junki/Desktop/proyectos/video-animation-pipeline/Assets/Characters/Turtle.fbx"
    anim_path = "/Users/junki/Desktop/proyectos/video-animation-pipeline/Assets/Animations/Library/WALK/02_01.fbx"
    # Fallback to whatever is available
    from glob import glob
    anim_files = glob("/Users/junki/Desktop/proyectos/video-animation-pipeline/Assets/Animations/Library/*/*.fbx")
    if anim_files:
        anim_path = anim_files[0]

    # Import char
    bpy.ops.import_scene.fbx(filepath=char_path, use_anim=False)
    char_bones = []
    for o in bpy.context.scene.objects:
        if o.type == 'ARMATURE':
            char_bones = [b.name for b in o.data.bones]
            break

    # Clean up scene a bit before importing next
    bpy.ops.object.select_all(action='DESELECT')

    # Import anim
    bpy.ops.import_scene.fbx(filepath=anim_path, use_anim=True)
    anim_action = None
    for act in bpy.data.actions:
        anim_action = act
        break
    
    if not anim_action:
        print("No action found")
        return

    anim_bones = set()
    for fc in anim_action.fcurves:
        if "pose.bones" in fc.data_path:
            try:
                bname = fc.data_path.split('"')[1]
                anim_bones.add(bname)
            except:
                pass

    print("=== BONE MAPPING DIAGNOSTIC ===")
    print(f"Char bones ({len(char_bones)}): {char_bones[:10]}...")
    print(f"Anim bones ({len(anim_bones)}): {sorted(list(anim_bones))}")

debug_bone_map()
