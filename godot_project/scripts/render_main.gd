extends SceneTree

const SCENE_PATH := "res://scenes/RenderScene.tscn"
const ANIM_LIB_KEY := "clip"

const PROFILE_BONE_CANDIDATES := {
    "Hips": ["hips", "hip", "pelvis"],
    "Spine": ["spine", "abdomen", "spine1"],
    "Chest": ["chest", "spine1", "spine2", "upperchest"],
    "UpperChest": ["upperchest", "spine2", "spine3"],
    "Neck": ["neck"],
    "Head": ["head"],
    "LeftShoulder": ["leftshoulder", "lshoulder"],
    "LeftUpperArm": ["leftupperarm", "leftarm", "larm", "lshldr"],
    "LeftLowerArm": ["leftlowerarm", "leftforearm", "lforearm"],
    "LeftHand": ["lefthand", "lhand"],
    "RightShoulder": ["rightshoulder", "rshoulder"],
    "RightUpperArm": ["rightupperarm", "rightarm", "rarm", "rshldr"],
    "RightLowerArm": ["rightlowerarm", "rightforearm", "rforearm"],
    "RightHand": ["righthand", "rhand"],
    "LeftUpperLeg": ["leftupperleg", "leftupleg", "leftthigh", "lthigh"],
    "LeftLowerLeg": ["leftlowerleg", "leftleg", "lshin"],
    "LeftFoot": ["leftfoot", "lfoot"],
    "LeftToes": ["lefttoebase", "lefttoe", "ltoe"],
    "RightUpperLeg": ["rightupperleg", "rightupleg", "rightthigh", "rthigh"],
    "RightLowerLeg": ["rightlowerleg", "rightleg", "rshin"],
    "RightFoot": ["rightfoot", "rfoot"],
    "RightToes": ["righttoebase", "righttoe", "rtoe"],
}

const WARMUP_FRAMES := 5

var _config: Dictionary = {}
var _render_scene: Node = null
var _frames_dir: String = ""
var _output_mp4: String = ""
var _fps: int = 30
var _total_frames: int = 0
var _skip_capture: bool = false

func _initialize() -> void:
    _skip_capture = _has_flag("--skip_capture")
    _config = _load_scene_data()
    if _config.is_empty():
        push_error("No scene_data provided. Use -- --scene_data <path>")
        quit()
        return

    var packed: PackedScene = load(SCENE_PATH)
    if packed == null:
        push_error("Failed to load RenderScene.tscn")
        quit()
        return

    _render_scene = packed.instantiate()
    root.add_child(_render_scene)

    _apply_config()
    if _skip_capture:
        return
    call_deferred("_capture_loop")

func _load_scene_data() -> Dictionary:
    var args := OS.get_cmdline_user_args()
    var scene_path := ""
    var i := 0
    while i < args.size():
        if args[i] == "--scene_data" and i + 1 < args.size():
            scene_path = args[i + 1]
            break
        i += 1

    if scene_path == "":
        return {}

    if not FileAccess.file_exists(scene_path):
        push_error("scene_data not found: %s" % scene_path)
        return {}

    var json_text: String = FileAccess.get_file_as_string(scene_path)
    var parsed: Variant = JSON.parse_string(json_text)
    if typeof(parsed) != TYPE_DICTIONARY:
        push_error("scene_data JSON invalid")
        return {}
    return parsed

func _has_flag(flag: String) -> bool:
    var args := OS.get_cmdline_user_args()
    return args.has(flag)

func _apply_config() -> void:
    _fps = int(_config.get("fps", 30))

    var resolution: Array = _config.get("resolution", [])
    if resolution is Array and resolution.size() == 2:
        var w := int(resolution[0])
        var h := int(resolution[1])
        if w > 0 and h > 0:
            get_root().size = Vector2i(w, h)
            DisplayServer.window_set_size(Vector2i(w, h))

    _output_mp4 = str(_config.get("output_mp4", ""))
    var frames_dir: String = str(_config.get("output_frames_dir", ""))
    if frames_dir == "":
        frames_dir = OS.get_user_data_dir().path_join("frames")
    _frames_dir = frames_dir
    DirAccess.make_dir_recursive_absolute(_frames_dir)

    _setup_environment()
    _setup_character_and_animation()
    _compute_total_frames()

func _setup_environment() -> void:
    var env_node := _render_scene.get_node("WorldEnvironment") as WorldEnvironment
    if env_node.environment == null:
        env_node.environment = Environment.new()

    var light := _render_scene.get_node("DirectionalLight3D") as DirectionalLight3D
    light.rotation_degrees = Vector3(-60.0, 0.0, 0.0)
    light.light_energy = 2.0

    var plane := _render_scene.get_node("BackgroundPlane") as MeshInstance3D
    _ensure_background_plane(plane)

    var bg_scene_path := str(_config.get("background_scene_res_path", ""))
    if bg_scene_path == "":
        bg_scene_path = str(_config.get("background_scene_file_path", ""))
    if bg_scene_path != "":
        var bg_scene := _load_packed_scene(bg_scene_path)
        if bg_scene != null:
            var bg_root := _render_scene.get_node_or_null("BackgroundRoot")
            if bg_root == null:
                bg_root = Node3D.new()
                bg_root.name = "BackgroundRoot"
                _render_scene.add_child(bg_root)
            else:
                for child in bg_root.get_children():
                    child.queue_free()
            var bg_instance := bg_scene.instantiate()
            bg_root.add_child(bg_instance)
            plane.visible = false
            env_node.environment.background_mode = Environment.BG_COLOR
            env_node.environment.background_color = Color(0, 0, 0, 1)
            return

    var bg_path := str(_config.get("background_res_path", ""))
    if bg_path == "":
        bg_path = str(_config.get("background_image_path", ""))

    if bg_path != "":
        var tex := _load_texture(bg_path)
        if tex != null:
            var mat := plane.material_override as StandardMaterial3D
            mat.albedo_texture = tex
            mat.albedo_color = Color(1, 1, 1, 1)
            env_node.environment.background_mode = Environment.BG_COLOR
            env_node.environment.background_color = Color(0, 0, 0, 1)
            return

    # Green screen fallback
    var mat_fallback := plane.material_override as StandardMaterial3D
    mat_fallback.albedo_texture = null
    mat_fallback.albedo_color = Color(0, 1, 0, 1)
    env_node.environment.background_mode = Environment.BG_COLOR
    env_node.environment.background_color = Color(0, 1, 0, 1)

func _ensure_background_plane(plane: MeshInstance3D) -> void:
    if plane.mesh == null:
        var quad := QuadMesh.new()
        quad.size = Vector2(10, 10)
        plane.mesh = quad
    if plane.material_override == null:
        var mat := StandardMaterial3D.new()
        mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
        mat.cull_mode = BaseMaterial3D.CULL_DISABLED
        plane.material_override = mat
    plane.transform.origin = Vector3(0.0, 1.6, -6.0)

func _load_texture(path: String) -> Texture2D:
    var image := Image.new()
    var err := image.load(path)
    if err != OK:
        push_warning("Failed to load background image: %s" % path)
        return null
    return ImageTexture.create_from_image(image)

func _setup_character_and_animation() -> void:
    var character_root := _render_scene.get_node("CharacterRoot") as Node3D
    var cam_offset: Array = _config.get("camera_offset", [])
    if cam_offset is Array and cam_offset.size() == 3:
        character_root.set("camera_offset", Vector3(cam_offset[0], cam_offset[1], cam_offset[2]))
    var look_offset: Array = _config.get("look_at_offset", [])
    if look_offset is Array and look_offset.size() == 3:
        character_root.set("look_at_offset", Vector3(look_offset[0], look_offset[1], look_offset[2]))
    if _config.has("smooth_speed"):
        character_root.set("smooth_speed", float(_config.get("smooth_speed")))
    if _config.has("lock_root_motion"):
        character_root.set("lock_root_motion", bool(_config.get("lock_root_motion")))
    if _config.has("snap_distance"):
        character_root.set("snap_distance", float(_config.get("snap_distance")))
    if _config.has("camera_snap_distance"):
        character_root.set("camera_snap_distance", float(_config.get("camera_snap_distance")))
    if _config.has("loop_correction_threshold"):
        character_root.set("loop_correction_threshold", float(_config.get("loop_correction_threshold")))
    if _config.has("camera_drift_enabled"):
        character_root.set("camera_drift_enabled", bool(_config.get("camera_drift_enabled")))
    if _config.has("camera_drift_axis"):
        var axis: Array = _config.get("camera_drift_axis", [])
        if axis is Array and axis.size() == 3:
            character_root.set("camera_drift_axis", Vector3(axis[0], axis[1], axis[2]))
    if _config.has("camera_drift_amount"):
        character_root.set("camera_drift_amount", float(_config.get("camera_drift_amount")))
    if _config.has("camera_drift_speed"):
        character_root.set("camera_drift_speed", float(_config.get("camera_drift_speed")))
    if _config.has("camera_drift_phase"):
        character_root.set("camera_drift_phase", float(_config.get("camera_drift_phase")))

    var char_path := str(_config.get("character_res_path", ""))
    if char_path == "":
        char_path = str(_config.get("character_file_path", ""))

    var char_scene := _load_packed_scene(char_path)
    if char_scene == null:
        push_error("Character scene not found: %s" % char_path)
        return

    var char_instance := char_scene.instantiate()
    character_root.add_child(char_instance)

    var target_skel := _find_skeleton(char_instance)
    var target_bone_map: BoneMap = BoneMap.new()
    if target_skel != null:
        target_bone_map = _build_bone_map(target_skel)

    var follow_name := str(_config.get("camera_follow_bone", "Hips"))
    var root_name := str(_config.get("root_bone", "Hips"))
    if target_skel != null:
        if target_skel.find_bone(follow_name) == -1 and target_bone_map != null:
            var mapped_follow := target_bone_map.get_skeleton_bone_name(follow_name)
            if mapped_follow != StringName():
                follow_name = String(mapped_follow)
        if target_skel.find_bone(root_name) == -1 and target_bone_map != null:
            var mapped_root := target_bone_map.get_skeleton_bone_name(root_name)
            if mapped_root != StringName():
                root_name = String(mapped_root)

    character_root.set("follow_bone_name", follow_name)
    character_root.set("root_bone_name", root_name)

    var anim_player := _find_animation_player(char_instance)
    if anim_player == null:
        anim_player = AnimationPlayer.new()
        anim_player.name = "AnimationPlayer"
        character_root.add_child(anim_player)
        anim_player.root_node = anim_player.get_path_to(char_instance)

    var anim_path := str(_config.get("animation_res_path", ""))
    if anim_path == "":
        anim_path = str(_config.get("animation_file_path", ""))

    var anim_lib: Resource = load(anim_path)
    if anim_lib is AnimationLibrary:
        anim_player.add_animation_library(ANIM_LIB_KEY, anim_lib)
        var anim_name := str(_config.get("animation_name", ""))
        if anim_name == "":
            var anims: PackedStringArray = anim_lib.get_animation_list()
            if anims.size() > 0:
                anim_name = anims[0]
        if anim_name != "":
            var anim_obj: Animation = anim_lib.get_animation(anim_name)
            if anim_obj != null and target_skel != null and target_bone_map != null:
                var source_map: BoneMap = _build_bone_map_from_animation(anim_obj)
                var source_path: NodePath = _infer_source_skeleton_path(anim_obj)
                var target_path := char_instance.get_path_to(target_skel)
                anim_obj = _retarget_animation(anim_obj, source_map, target_bone_map, source_path, target_path)
            _ensure_loop(anim_obj)
            if anim_obj != null:
                var lib := AnimationLibrary.new()
                lib.add_animation(anim_name, anim_obj)
                if anim_player.has_animation_library(ANIM_LIB_KEY):
                    anim_player.remove_animation_library(ANIM_LIB_KEY)
                anim_player.add_animation_library(ANIM_LIB_KEY, lib)
                _play_animation(anim_player, ANIM_LIB_KEY + "/" + anim_name)
            else:
                push_warning("Animation not found in library: %s" % anim_name)
        else:
            push_warning("No animation found in library")
    elif anim_lib is PackedScene:
        var temp_scene: Node = anim_lib.instantiate()
        var source_player := _find_animation_player(temp_scene)
        var source_skel := _find_skeleton(temp_scene)
        if source_player != null:
            var anims2: PackedStringArray = source_player.get_animation_list()
            if anims2.size() > 0:
                var anim2: Animation = source_player.get_animation(anims2[0])
                if source_skel != null and target_skel != null and target_bone_map != null:
                    var source_bone_map := _build_bone_map(source_skel)
                    var target_path := char_instance.get_path_to(target_skel)
                    var source_path := temp_scene.get_path_to(source_skel)
                    anim2 = _retarget_animation(anim2, source_bone_map, target_bone_map, source_path, target_path)
                _ensure_loop(anim2)
                var lib := AnimationLibrary.new()
                lib.add_animation("clip", anim2)
                anim_player.add_animation_library(ANIM_LIB_KEY, lib)
                _play_animation(anim_player, ANIM_LIB_KEY + "/clip")
            else:
                push_warning("No animations found in source FBX scene")
        else:
            push_warning("AnimationPlayer not found in source FBX scene")
        temp_scene.queue_free()
    else:
        push_warning("Animation library not found or invalid: %s" % anim_path)

func _load_packed_scene(path: String) -> PackedScene:
    if path == "":
        return null
    if not ResourceLoader.exists(path):
        push_warning("Resource not found: %s" % path)
        return null
    var res: Resource = load(path)
    if res is PackedScene:
        return res
    return null

func _ensure_loop(anim: Animation) -> void:
    if anim == null:
        return
    anim.loop_mode = Animation.LOOP_LINEAR

func _play_animation(anim_player: AnimationPlayer, anim_path: String) -> void:
    anim_player.play(anim_path)
    anim_player.seek(0.0, true)

func _find_animation_player(node: Node) -> AnimationPlayer:
    if node is AnimationPlayer:
        return node
    for child in node.get_children():
        var found := _find_animation_player(child)
        if found != null:
            return found
    return null

func _find_skeleton(node: Node) -> Skeleton3D:
    if node is Skeleton3D:
        return node
    for child in node.get_children():
        var found := _find_skeleton(child)
        if found != null:
            return found
    return null

func _normalize_bone_name(name: String) -> String:
    var n := name.to_lower()
    n = n.replace("mixamorig:", "")
    n = n.replace("mixamorig_", "")
    n = n.replace(":", "")
    n = n.replace(" ", "")
    n = n.replace("_", "")
    return n

func _build_bone_map(skel: Skeleton3D) -> BoneMap:
    var bm := BoneMap.new()
    var profile := SkeletonProfileHumanoid.new()
    bm.profile = profile
    if skel == null:
        return bm

    var lookup: Dictionary = {}
    for i in range(skel.get_bone_count()):
        var bone_name := skel.get_bone_name(i)
        lookup[_normalize_bone_name(bone_name)] = bone_name

    for profile_bone in PROFILE_BONE_CANDIDATES.keys():
        var candidates: Array = PROFILE_BONE_CANDIDATES[profile_bone]
        for cand in candidates:
            var key := _normalize_bone_name(cand)
            if lookup.has(key):
                bm.set_skeleton_bone_name(profile_bone, lookup[key])
                break
    return bm

func _build_bone_map_from_animation(anim: Animation) -> BoneMap:
    var bm := BoneMap.new()
    var profile := SkeletonProfileHumanoid.new()
    bm.profile = profile
    if anim == null:
        return bm

    var lookup: Dictionary = {}
    for i in range(anim.get_track_count()):
        var path := anim.track_get_path(i)
        if path.get_subname_count() == 0:
            continue
        var bone_name := String(path.get_subname(0))
        if bone_name == "":
            continue
        lookup[_normalize_bone_name(bone_name)] = bone_name

    for profile_bone in PROFILE_BONE_CANDIDATES.keys():
        var candidates: Array = PROFILE_BONE_CANDIDATES[profile_bone]
        for cand in candidates:
            var key := _normalize_bone_name(cand)
            if lookup.has(key):
                bm.set_skeleton_bone_name(profile_bone, lookup[key])
                break
    return bm

func _infer_source_skeleton_path(anim: Animation) -> NodePath:
    if anim == null:
        return NodePath()
    for i in range(anim.get_track_count()):
        var path := anim.track_get_path(i)
        if path.get_subname_count() == 0:
            continue
        var path_str := String(path)
        var colon_idx := path_str.find(":")
        if colon_idx != -1:
            path_str = path_str.substr(0, colon_idx)
        if path_str != "":
            return NodePath(path_str)
    return NodePath()

func _retarget_animation(
    anim: Animation,
    source_map: BoneMap,
    target_map: BoneMap,
    source_skel_path: NodePath,
    target_skel_path: NodePath
) -> Animation:
    var retargeted: Animation = anim.duplicate()
    var target_path_str := String(target_skel_path)
    if target_path_str == "":
        return retargeted
    var source_path_str := String(source_skel_path)

    for i in range(retargeted.get_track_count()):
        var path: NodePath = retargeted.track_get_path(i)
        var path_str := String(path)
        if source_path_str != "" and not path_str.begins_with(source_path_str):
            continue
        if path.get_subname_count() == 0:
            continue

        var source_bone := StringName(path.get_subname(0))
        if source_bone == StringName():
            continue

        var profile_bone := source_map.find_profile_bone_name(source_bone)
        if profile_bone == StringName():
            continue

        var target_bone := target_map.get_skeleton_bone_name(profile_bone)
        if target_bone == StringName():
            continue

        var new_path := NodePath(target_path_str + ":" + String(target_bone))
        retargeted.track_set_path(i, new_path)

    return retargeted

func _compute_total_frames() -> void:
    var duration := float(_config.get("audio_duration", 0.0))
    if duration <= 0.0:
        var audio_res := str(_config.get("audio_res_path", ""))
        if audio_res != "" and ResourceLoader.exists(audio_res):
            var stream: Resource = load(audio_res)
            if stream is AudioStream:
                duration = stream.get_length()

    if duration <= 0.0:
        duration = 5.0

    _total_frames = int(ceil(duration * float(_fps)))
    if _total_frames < 1:
        _total_frames = 1

func _capture_loop() -> void:
    print("[Godot] Capturing %d frames at %d fps" % [_total_frames, _fps])
    for _i in range(WARMUP_FRAMES):
        await process_frame
        await RenderingServer.frame_post_draw
    for i in range(_total_frames):
        await process_frame
        await RenderingServer.frame_post_draw
        _save_frame(i)

    var ok := _encode_video()
    if not ok:
        push_error("FFmpeg encoding failed")
    quit()

func _save_frame(index: int) -> void:
    var img := get_root().get_texture().get_image()
    var frame_path := _frames_dir.path_join("frame_%05d.png" % index)
    var err := img.save_png(frame_path)
    if err != OK:
        push_warning("Failed to save frame: %s" % frame_path)

func _encode_video() -> bool:
    if _output_mp4 == "":
        push_warning("No output_mp4 specified; skipping encode")
        return true

    DirAccess.make_dir_recursive_absolute(_output_mp4.get_base_dir())

    var pattern := _frames_dir.path_join("frame_%05d.png")
    var args: Array = ["-y", "-framerate", str(_fps), "-i", pattern]

    var audio_path := str(_config.get("audio_file_path", ""))
    if audio_path != "" and FileAccess.file_exists(audio_path):
        args.append_array(["-i", audio_path])

    args.append_array(["-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p"])

    if audio_path != "" and FileAccess.file_exists(audio_path):
        args.append_array(["-map", "0:v:0", "-map", "1:a:0"])
        args.append_array(["-c:a", "aac", "-b:a", "192k", "-shortest"])

    args.append(_output_mp4)

    var output: PackedStringArray = PackedStringArray()
    var code := OS.execute("ffmpeg", args, output, true)
    if code != 0:
        if output.size() > 0:
            var joined := ""
            for i in range(output.size()):
                joined += output[i]
                if i < output.size() - 1:
                    joined += "\n"
            push_warning(joined)
        return false
    return true
