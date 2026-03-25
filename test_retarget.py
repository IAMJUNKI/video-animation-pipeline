import bpy
import sys
import json
from pathlib import Path

def dump_info():
    print("=== BLENDER DIAGNOSTICS ===")
    
    # 1. Import Character
    char_path = "/Users/junki/Desktop/proyectos/video-animation-pipeline/Assets/Characters/Turtle.fbx"
    bpy.ops.import_scene.fbx(filepath=char_path, use_anim=False)
    
    char_arm = None
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            char_arm = obj
            break
            
    print(f"Character Armature Name: {char_arm.name}")
    print("Sample Bones:")
    for b in list(char_arm.pose.bones)[:5]:
        print(f" - {b.name}")

    # 2. Import Animation
    anim_path = "/Users/junki/Desktop/proyectos/video-animation-pipeline/Assets/Animations/Library/WALK/02_01.fbx"
    # Or just use the first file if that doesn't exist
    from glob import glob
    anim_files = glob("/Users/junki/Desktop/proyectos/video-animation-pipeline/Assets/Animations/Library/*/*.fbx")
    if anim_files:
        anim_path = anim_files[0]
        
    bpy.ops.import_scene.fbx(filepath=anim_path, use_anim=True)
    
    anim_arm = None
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE' and obj != char_arm:
            anim_arm = obj
            break
            
    print(f"\nAnim Armature Name: {anim_arm.name if anim_arm else 'None'}")
    
    # Find action
    act = None
    for action in bpy.data.actions:
        print(f"Found Action: {action.name}")
        act = action
        break
        
    if act:
        print(f"Sample F-Curve Data Paths for '{act.name}':")
        for fc in act.fcurves[:5]:
            print(f" - {fc.data_path} [{fc.array_index}] ({len(fc.keyframe_points)} pts)")

dump_info()
