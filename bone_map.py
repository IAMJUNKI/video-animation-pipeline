"""
bone_map.py — CMU Mocap → Mixamo bone name mapping.

Used by render_engine.py to retarget CMU motion-capture FBX files
onto characters rigged with the Mixamo/Meshy `mixamorig:` bone hierarchy.
"""

# ─── Primary Map: CMU bone name → Mixamo target ─────────────────────
BONE_MAP = {
    # Root & Torso
    "hip":        "mixamorig:Hips",
    "lowerback":  "mixamorig:Spine",
    "upperback":  "mixamorig:Spine1",
    "thorax":     "mixamorig:Spine2",
    "lowerneck":  "mixamorig:Neck",
    "neck":       "mixamorig:Neck",
    "upperneck":  "mixamorig:Neck",
    "head":       "mixamorig:Head",

    # Left Arm
    "lclavicle":  "mixamorig:LeftShoulder",
    "lhumerus":   "mixamorig:LeftArm",
    "lradius":    "mixamorig:LeftForeArm",
    "lwrist":     "mixamorig:LeftHand",
    "lhand":      "mixamorig:LeftHand",
    "lfingers":   "mixamorig:LeftHandIndex1",
    "lthumb":     "mixamorig:LeftHandThumb1",

    # Right Arm
    "rclavicle":  "mixamorig:RightShoulder",
    "rhumerus":   "mixamorig:RightArm",
    "rradius":    "mixamorig:RightForeArm",
    "rwrist":     "mixamorig:RightHand",
    "rhand":      "mixamorig:RightHand",
    "rfingers":   "mixamorig:RightHandIndex1",
    "rthumb":     "mixamorig:RightHandThumb1",

    # Left Leg
    "lfemur":     "mixamorig:LeftUpLeg",
    "ltibia":     "mixamorig:LeftLeg",
    "lfoot":      "mixamorig:LeftFoot",
    "ltoes":      "mixamorig:LeftToeBase",

    # Right Leg
    "rfemur":     "mixamorig:RightUpLeg",
    "rtibia":     "mixamorig:RightLeg",
    "rfoot":      "mixamorig:RightFoot",
    "rtoes":      "mixamorig:RightToeBase",
}

# ─── Reverse Map: Mixamo → CMU ──────────────────────────────────────
REVERSE_BONE_MAP = {v: k for k, v in BONE_MAP.items()}


def get_target_bone(source_name: str) -> str | None:
    """
    Resolve a source bone name (CMU) to the Mixamo target.
    Case-insensitive, strips underscores/spaces.
    """
    clean = source_name.lower().strip().replace(" ", "").replace("_", "")
    if clean in BONE_MAP:
        return BONE_MAP[clean]
    for prefix in ("cmu:", "bvh:"):
        key = clean.removeprefix(prefix)
        if key in BONE_MAP:
            return BONE_MAP[key]
    return None


def get_mapped_bones() -> list[str]:
    """Return sorted list of all Mixamo target bone names."""
    return sorted(set(BONE_MAP.values()))