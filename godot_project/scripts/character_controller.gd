extends Node3D

@export var camera_rig_path: NodePath = NodePath("../CameraRig")
@export var follow_bone_name: String = "Hips"
@export var root_bone_name: String = "Hips"
@export var camera_offset: Vector3 = Vector3(0.0, 1.6, 4.0)
@export var look_at_offset: Vector3 = Vector3(0.0, 1.2, 0.0)
@export var smooth_speed: float = 8.0
@export var lock_root_motion: bool = true
@export var snap_distance: float = 0.5
@export var camera_snap_distance: float = 0.75
@export var loop_correction_threshold: float = 0.75

var _skeleton: Skeleton3D = null
var _camera_rig: Node3D = null
var _follow_bone_idx: int = -1
var _root_bone_idx: int = -1
var _initialized: bool = false
var _last_root_local: Vector3 = Vector3.ZERO
var _has_last_root_local: bool = false

func _ready() -> void:
    _refresh_refs()

func _process(delta: float) -> void:
    if _skeleton == null:
        _refresh_refs()
        return

    if _follow_bone_idx == -1:
        _follow_bone_idx = _skeleton.find_bone(follow_bone_name)
    if _root_bone_idx == -1:
        _root_bone_idx = _skeleton.find_bone(root_bone_name)
    if _follow_bone_idx == -1:
        return

    var follow_pose: Transform3D = _skeleton.get_bone_global_pose(_follow_bone_idx)
    var root_pose: Transform3D = follow_pose
    if _root_bone_idx != -1:
        root_pose = _skeleton.get_bone_global_pose(_root_bone_idx)

    if lock_root_motion:
        var root_local := root_pose.origin
        if _has_last_root_local:
            var delta_root := root_local - _last_root_local
            if delta_root.length() <= loop_correction_threshold:
                global_transform.origin -= Vector3(delta_root.x, 0.0, delta_root.z)
        _last_root_local = root_local
        _has_last_root_local = true

    if _camera_rig != null:
        var follow_global: Transform3D = _skeleton.global_transform * follow_pose
        var cam_target := follow_global.origin + (global_transform.basis * camera_offset)
        var t2: float = min(max(delta * smooth_speed, 0.0), 1.0)
        if not _initialized or _camera_rig.global_transform.origin.distance_to(cam_target) > camera_snap_distance:
            _camera_rig.global_transform.origin = cam_target
        else:
            _camera_rig.global_transform.origin = _camera_rig.global_transform.origin.lerp(cam_target, t2)
        _camera_rig.look_at(follow_global.origin + look_at_offset, Vector3.UP)
    _initialized = true

func _refresh_refs() -> void:
    _camera_rig = get_node_or_null(camera_rig_path)
    _skeleton = _find_skeleton(self)
    if _skeleton != null:
        _follow_bone_idx = _skeleton.find_bone(follow_bone_name)
        _root_bone_idx = _skeleton.find_bone(root_bone_name)

func _find_skeleton(node: Node) -> Skeleton3D:
    if node is Skeleton3D:
        return node
    for child in node.get_children():
        var found := _find_skeleton(child)
        if found != null:
            return found
    return null
