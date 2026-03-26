extends Sprite3D

var time_passed := 0.0
var base_scale := Vector3.ONE

# These should be set based on the JSON payload's 'character_state'
var is_talking := false
var is_walking := false

func apply_character_state(state: String) -> void:
    var normalized := state.strip_edges().to_lower()
    is_talking = normalized == "talking"
    is_walking = normalized == "walking"

func _ready():
    base_scale = scale

func _process(delta):
    time_passed += delta
    var current_scale = base_scale
    var current_pos = Vector3.ZERO

    # 1. Idle Breathing (Always active)
    current_scale.y += sin(time_passed * 2.0) * 0.02
    current_scale.x -= sin(time_passed * 2.0) * 0.01

    # 2. Talking Animation
    if is_talking:
        current_scale.y += sin(time_passed * 15.0) * 0.05
        current_scale.x -= sin(time_passed * 15.0) * 0.03

    # 3. Walking Animation
    if is_walking:
        current_pos.y += abs(sin(time_passed * 10.0)) * 0.2
        rotation_degrees.z = sin(time_passed * 5.0) * 5.0
    else:
        rotation_degrees.z = lerp(rotation_degrees.z, 0.0, delta * 10.0)

    scale = current_scale
    position = current_pos
