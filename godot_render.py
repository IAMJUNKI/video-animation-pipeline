"""
godot_render.py — Godot 4.x headless render bridge.

Usage:
  python godot_render.py --scene_data path/to/scene_data.json [--dry-run]
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from hashlib import sha1
from pathlib import Path

import config


def log(msg: str):
    print(msg, flush=True)


def _hash_path(path: Path) -> str:
    return sha1(str(path).encode("utf-8")).hexdigest()[:8]


def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def _copy_if_newer(src: Path, dst: Path) -> bool:
    """Copy src to dst if dst is missing or older. Returns True if copied."""
    if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
        _ensure_dir(dst.parent)
        shutil.copy2(src, dst)
        return True
    return False


def _prepare_asset(src_path: str, dest_dir: Path) -> tuple[Path | None, bool]:
    """Prepare asset in Godot project. Returns (dest_path, changed)."""
    if not src_path:
        return None, False

    src = Path(src_path)
    if not src.exists():
        log(f"  ⚠️  Asset missing: {src}")
        return None, False

    changed = False
    dst_name = f"{src.stem}_{_hash_path(src)}{src.suffix}"
    dst = dest_dir / dst_name
    copied = _copy_if_newer(src, dst)
    changed = changed or copied
    return dst, changed


def _res_path(project_dir: Path, abs_path: Path) -> str:
    rel = abs_path.relative_to(project_dir)
    return "res://" + str(rel).replace(os.sep, "/")


def _run_and_stream(cmd: list[str], cwd: Path | None = None) -> int:
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=str(cwd) if cwd else None,
    )
    assert process.stdout is not None
    for line in iter(process.stdout.readline, ""):
        if line:
            log(line.rstrip())
    process.stdout.close()
    return process.wait()


def _build_godot_base_cmd(
    scene: dict,
    godot_bin: str,
    display_driver_override: str | None = None,
    rendering_driver_override: str | None = None,
    force_headless: bool | None = None,
) -> list[str]:
    cmd = [godot_bin]
    default_headless = False if sys.platform == "darwin" else True
    use_headless = bool(scene.get("use_headless", default_headless))
    if force_headless is not None:
        use_headless = force_headless

    display_driver = (display_driver_override if display_driver_override is not None else config.GODOT_DISPLAY_DRIVER).strip()
    rendering_driver = (rendering_driver_override if rendering_driver_override is not None else config.GODOT_RENDERING_DRIVER).strip()

    # If an explicit display driver is set, prefer it over --headless.
    if display_driver:
        cmd.extend(["--display-driver", display_driver])
        if display_driver != "headless":
            use_headless = False

    if use_headless:
        cmd.append("--headless")

    if rendering_driver:
        cmd.extend(["--rendering-driver", rendering_driver])

    return cmd


def _transcode_to_mp4(input_path: Path, output_path: Path, fps: int, audio_path: Path | None = None) -> None:
    _ensure_dir(output_path.parent)
    cmd = ["ffmpeg", "-y"]

    if input_path.suffix.lower() == ".png":
        pattern = input_path.with_name(input_path.stem + "%08d.png")
        first_frame = input_path.with_name(input_path.stem + "00000000.png")
        if not first_frame.exists():
            raise FileNotFoundError(f"PNG sequence not found: {first_frame}")
        cmd.extend(["-framerate", str(fps), "-i", str(pattern)])
    else:
        if not input_path.exists():
            raise FileNotFoundError(f"Movie output not found: {input_path}")
        cmd.extend(["-i", str(input_path)])

    if audio_path and audio_path.exists():
        cmd.extend(["-i", str(audio_path)])

    cmd.extend([
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
    ])

    if audio_path and audio_path.exists():
        cmd.extend(["-map", "0:v:0", "-map", "1:a:0"])
        cmd.extend(["-c:a", "aac", "-b:a", "192k", "-shortest"])

    cmd.extend([
        "-movflags", "+faststart",
        str(output_path),
    ])
    log("  🎞️  Transcoding movie output to MP4...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg transcode failed:\\n{result.stderr[-500:]}")


def main():
    parser = argparse.ArgumentParser(description="Godot headless render bridge")
    parser.add_argument("--scene_data", type=str, required=True, help="Path to scene JSON")
    parser.add_argument("--dry-run", action="store_true", help="Skip Godot render")
    args = parser.parse_args()

    scene_path = Path(args.scene_data)
    if not scene_path.exists():
        raise FileNotFoundError(f"scene_data not found: {scene_path}")

    with scene_path.open("r") as f:
        scene = json.load(f)

    godot_project = config.GODOT_PROJECT_DIR
    if not godot_project.exists():
        raise FileNotFoundError(f"Godot project not found: {godot_project}")

    godot_bin = str(config.GODOT_BIN)
    if os.path.isabs(godot_bin) and not Path(godot_bin).exists():
        raise FileNotFoundError(
            f"Godot binary not found: {godot_bin}. Set GODOT_BIN or install Godot."
        )

    assets_changed = False

    # Character
    character_src = scene.get("character_file_path") or str(config.CHARACTERS_DIR / config.DEFAULT_CHARACTER)
    char_dst, char_changed = _prepare_asset(
        character_src,
        godot_project / "Assets" / "Characters",
    )
    assets_changed = assets_changed or char_changed

    # Animation (FBX -> GLB)
    anim_src = scene.get("animation_file_path", "")
    anim_dst, anim_changed = _prepare_asset(
        anim_src,
        godot_project / "Assets" / "Animations",
    )
    assets_changed = assets_changed or anim_changed

    # Background image (no conversion)
    bg_src = scene.get("background_image_path", "")
    bg_dst, bg_changed = _prepare_asset(
        bg_src,
        godot_project / "Assets" / "Backgrounds",
    )
    assets_changed = assets_changed or bg_changed

    # Background 3D scene (FBX/GLB/GLTF/TSN)
    bg_scene_src = scene.get("background_scene_file_path", "")
    bg_scene_dst, bg_scene_changed = _prepare_asset(
        bg_scene_src,
        godot_project / "Assets" / "Backgrounds",
    )
    assets_changed = assets_changed or bg_scene_changed

    # Audio (no conversion)
    audio_src = scene.get("audio_file_path", "")
    audio_dst, audio_changed = _prepare_asset(
        audio_src,
        godot_project / "Assets" / "Audio",
    )
    assets_changed = assets_changed or audio_changed

    # Build Godot scene data
    godot_scene = dict(scene)
    if char_dst:
        godot_scene["character_res_path"] = _res_path(godot_project, char_dst)
    if anim_dst:
        godot_scene["animation_res_path"] = _res_path(godot_project, anim_dst)
    if bg_dst:
        godot_scene["background_res_path"] = _res_path(godot_project, bg_dst)
    if bg_scene_dst:
        godot_scene["background_scene_res_path"] = _res_path(godot_project, bg_scene_dst)
    if audio_dst:
        godot_scene["audio_res_path"] = _res_path(godot_project, audio_dst)

    # Ensure frames/output locations
    output_mp4 = scene.get("output_mp4")
    if not output_mp4:
        output_mp4 = str(scene_path.parent / "render.mp4")
    godot_scene["output_mp4"] = output_mp4

    frames_dir = scene.get("output_frames_dir")
    if not frames_dir:
        frames_dir = str(scene_path.parent / "frames")
    godot_scene["output_frames_dir"] = frames_dir

    godot_json_path = scene_path.parent / "scene_data_godot.json"
    with godot_json_path.open("w") as f:
        json.dump(godot_scene, f, indent=2)

    log(f"  🧩 Godot scene JSON: {godot_json_path}")

    if args.dry_run:
        log("  ⏭️  [DRY-RUN] Skipping Godot render")
        return

    # Run import if assets changed or no import cache exists
    import_cache = godot_project / ".godot" / "imported"
    if assets_changed or not import_cache.exists():
        log("  📦 Importing assets in Godot...")
        import_cmd = _build_godot_base_cmd(scene, godot_bin) + [
            "--path", str(godot_project),
            "--import",
        ]
        code = _run_and_stream(import_cmd, cwd=godot_project)
        if code != 0:
            raise RuntimeError("Godot import failed")

    # Run headless render
    log("  🎬 Starting Godot headless render...")
    fps = int(scene.get("fps", config.RENDER_FPS))
    use_movie_writer = bool(scene.get("use_movie_writer", False))

    if use_movie_writer:
        duration = float(scene.get("audio_duration", 0.0))
        if duration <= 0.0:
            duration = 5.0
        total_frames = max(1, int(math.ceil(duration * fps)))
        movie_file = scene.get("movie_file") or str(scene_path.parent / "movie.avi")

        render_cmd = _build_godot_base_cmd(scene, godot_bin) + [
            "--path", str(godot_project),
            "--fixed-fps", str(fps),
            "--write-movie", str(movie_file),
            "--quit-after", str(total_frames),
            "--script", "res://scripts/render_main.gd",
            "--",
            "--scene_data", str(godot_json_path),
            "--skip_capture",
        ]
        code = _run_and_stream(render_cmd, cwd=godot_project)
        movie_path = Path(movie_file)
        if code != 0 or not movie_path.exists():
            log("  ⚠️  Movie writer failed; retrying with manual frame capture...")
        else:
            if output_mp4:
                audio_path = scene.get("audio_file_path")
                audio_file = Path(audio_path) if audio_path else None
                _transcode_to_mp4(movie_path, Path(output_mp4), fps, audio_file)
            return
    # Manual capture fallback (or primary if movie writer disabled)
    render_cmd = _build_godot_base_cmd(scene, godot_bin) + [
        "--path", str(godot_project),
        "--fixed-fps", str(fps),
        "--script", "res://scripts/render_main.gd",
        "--",
        "--scene_data", str(godot_json_path),
    ]
    code = _run_and_stream(render_cmd, cwd=godot_project)
    if code != 0:
        # Retry with a visible display driver if headless failed (common on macOS)
        fallback_display = config.GODOT_FALLBACK_DISPLAY_DRIVER.strip()
        if not fallback_display and sys.platform == "darwin":
            fallback_display = "macos"

        if fallback_display:
            log(f"  ⚠️  Headless render failed; retrying with display driver '{fallback_display}'...")
            render_cmd = _build_godot_base_cmd(
                scene,
                godot_bin,
                display_driver_override=fallback_display,
                force_headless=False,
            ) + [
                "--path", str(godot_project),
                "--fixed-fps", str(fps),
                "--script", "res://scripts/render_main.gd",
                "--",
                "--scene_data", str(godot_json_path),
            ]
            code = _run_and_stream(render_cmd, cwd=godot_project)

        if code != 0:
            raise RuntimeError("Godot render failed")


if __name__ == "__main__":
    main()
