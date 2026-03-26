# Godot Headless Renderer (4.x)

This project is a minimal headless renderer used by the pipeline. It loads a character and animation at runtime, performs humanoid retargeting via BoneMaps, locks root motion, follows the character with a dynamic camera, and captures frames for FFmpeg to encode.

## Folder Layout

- `scenes/RenderScene.tscn`: Main scene loaded by the headless script.
- `scripts/render_main.gd`: Headless entrypoint (parses JSON, captures frames, runs FFmpeg).
- `scripts/character_controller.gd`: Root motion lock + camera follow.
- `Assets/Characters/`: Imported character GLB files.
- `Assets/Animations/`: Imported animation GLB files.
- `Assets/Backgrounds/`: Background images.
- `Assets/Audio/`: Audio files.
- `retarget/character_bone_map.tres`: BoneMap for character rig.
- `retarget/animation_bone_map.tres`: BoneMap for animation rig.

## Automated Retargeting (No Manual Setup Required)

The renderer now auto-builds BoneMaps at runtime by scanning your skeletons and mapping common bone names (Mixamo + CMU) to the Humanoid profile. This means:

- You do **not** need to manually assign BoneMaps in the editor.
- The same character + animation library will work across clips automatically.
- Mixamo and CMU bone names are both supported.

If you still want to fine-tune BoneMaps manually, you can use the `retarget/` resources as usual.

## Headless Render Flow

The pipeline writes a JSON file and calls:

```
<godot_bin> --headless --path <project> --fixed-fps <fps> --script res://scripts/render_main.gd -- --scene_data <json>
```

### JSON Keys

Required:
- `scene_text`
- `animation_file_path`
- `background_image_path`
- `audio_file_path`

Optional:
- `audio_duration`
- `fps`
- `resolution` (array of `[width, height]`)
- `character_file_path`
- `camera_follow_bone`
- `root_bone`
- `camera_offset` (array `[x, y, z]`)
- `look_at_offset` (array `[x, y, z]`)
- `output_mp4`
- `output_frames_dir`
- `use_movie_writer` (boolean, uses Godot Movie Writer instead of manual capture)
- `movie_file` (path to `.avi` or `.png` output when using Movie Writer)
- `use_headless` (boolean; defaults to `false` on macOS and `true` elsewhere)

## Notes

- If `background_image_path` is empty or missing, a green screen is used.
- FBX is imported directly by Godot (ufbx). No external conversion step is required.
- If `use_movie_writer` is enabled, the script will skip manual capture, let Godot write an AVI, then transcode it to MP4 with FFmpeg while muxing `audio_file_path`.
- You can override drivers via environment variables: `GODOT_DISPLAY_DRIVER` and `GODOT_RENDERING_DRIVER`. This can help if Movie Writer crashes under headless display drivers.
- If headless capture fails on macOS, the bridge will retry using the `macos` display driver (or `GODOT_FALLBACK_DISPLAY_DRIVER` if set).
