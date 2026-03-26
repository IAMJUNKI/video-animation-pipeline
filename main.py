"""
main.py — The Orchestrator for the 3D AI Content Pipeline.

Converts a story idea into a fully rendered 3D-animated YouTube Short (9:16).
Pipeline: G4F Script → Semantic Director → Kokoro TTS → Flux BG → Godot → FFmpeg

Usage:
    python main.py "A curious turtle discovers a hidden garden"
    python main.py --dry-run "A curious turtle discovers a hidden garden"
"""
import argparse
import json
import logging
import subprocess
import sys
import wave
from pathlib import Path
from typing import Optional

import config

# ─── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipeline")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  1. LLM INTERFACE — Gemini → G4F → OpenAI fallback chain
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import re


def _extract_json(text: str) -> str:
    """
    Robustly extract JSON from an LLM response that may contain
    markdown fences, preamble text, or trailing commentary.
    """
    text = text.strip()

    # Strip ```json ... ``` or ``` ... ``` fences
    fence_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
    match = re.search(fence_pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try to find a JSON object { ... } in the text
    brace_start = text.find('{')
    if brace_start != -1:
        # Find the matching closing brace
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    return text[brace_start:i + 1]

    # Last resort: return as-is
    return text


def llm_chat(messages: list[dict], expect_json: bool = False) -> str:
    """
    Send a chat completion request.
    Fallback chain: Gemini models (primary) → G4F models → OpenAI.
    """
    # ── Primary: Google Gemini (try multiple models) ──
    if config.GEMINI_API_KEY:
        try:
            from google import genai
            client = genai.Client(api_key=config.GEMINI_API_KEY)

            # Convert chat messages to Gemini format
            system_text = ""
            gemini_contents = []
            for msg in messages:
                if msg["role"] == "system":
                    system_text = msg["content"] + "\n\n"
                elif msg["role"] == "user":
                    gemini_contents.append(system_text + msg["content"])
                    system_text = ""
                elif msg["role"] == "assistant":
                    gemini_contents.append(msg["content"])
            prompt = "\n".join(gemini_contents)

            for model in config.GEMINI_MODELS:
                try:
                    log.info(f"  🔷 Trying Gemini ({model})")
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt,
                    )
                    content = response.text
                    if content and content.strip():
                        log.info(f"  ✅ Gemini/{model} responded ({len(content)} chars)")
                        return content.strip()
                except Exception as e:
                    log.warning(f"  ⚠️ Gemini/{model} failed: {e}")
        except ImportError:
            log.warning("  ⚠️ google-genai not installed. Run: pip install google-genai")

    # ── Fallback 1: G4F models (free, no API key) ──
    import signal

    def _timeout_handler(signum, frame):
        raise TimeoutError("G4F request timed out")

    try:
        from g4f.client import Client as G4FClient
        client = G4FClient()
        for model in config.G4F_MODELS:
            try:
                log.info(f"  🤖 Trying G4F model: {model}")
                # Set timeout to avoid hanging
                old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
                signal.alarm(config.G4F_TIMEOUT)
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                    )
                    content = response.choices[0].message.content
                finally:
                    signal.alarm(0)  # Cancel alarm
                    signal.signal(signal.SIGALRM, old_handler)

                if content and content.strip():
                    log.info(f"  ✅ G4F/{model} responded ({len(content)} chars)")
                    return content.strip()
            except TimeoutError:
                log.warning(f"  ⚠️ G4F/{model} timed out after {config.G4F_TIMEOUT}s")
                continue
            except Exception as e:
                log.warning(f"  ⚠️ G4F/{model} failed: {e}")
                continue
    except ImportError:
        log.warning("  ⚠️ g4f not installed, skipping G4F models")

    # ── Fallback 2: Official OpenAI API ──
    if config.OPENAI_API_KEY:
        log.info(f"  🔑 Falling back to OpenAI API ({config.OPENAI_MODEL})")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=config.OPENAI_API_KEY)
            kwargs = {
                "model": config.OPENAI_MODEL,
                "messages": messages,
            }
            if expect_json:
                kwargs["response_format"] = {"type": "json_object"}
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content.strip()
        except Exception as e:
            log.error(f"  ❌ OpenAI API failed: {e}")

    raise RuntimeError(
        "All LLM providers failed. Set GEMINI_API_KEY or OPENAI_API_KEY, "
        "or check your G4F install."
    )


def llm_generate_image(prompt: str, output_path: Path) -> Path:
    """Generate a 9:16 image using G4F Flux or DALL-E fallback."""
    # ── Try G4F image generation ──
    try:
        from g4f.client import Client as G4FClient
        from g4f.cookies import set_cookies
        
        if config.BING_U_COOKIE:
            set_cookies(".bing.com", {"_U": config.BING_U_COOKIE})
            
        client = G4FClient()
        for model in config.G4F_IMAGE_MODELS:
            try:
                log.info(f"  🎨 Trying G4F image model: {model}")
                response = client.images.generate(
                    model=model,
                    prompt=prompt,
                    response_format="url",
                )
                image_url = response.data[0].url

                # Download the image
                import urllib.request
                urllib.request.urlretrieve(image_url, str(output_path))
                if output_path.exists() and output_path.stat().st_size > 1000:
                    log.info(f"  ✅ Image saved: {output_path.name}")
                    return output_path
            except Exception as e:
                log.warning(f"  ⚠️ G4F/{model} image gen failed: {e}")
                continue
    except ImportError:
        log.warning("  ⚠️ g4f not installed")

    # ── Fallback: OpenAI DALL-E ──
    if config.OPENAI_API_KEY:
        log.info("  🔑 Falling back to OpenAI DALL-E 3")
        try:
            from openai import OpenAI
            import urllib.request
            client = OpenAI(api_key=config.OPENAI_API_KEY)
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1792",  # Closest 9:16 DALL-E supports
                quality="standard",
                n=1,
            )
            urllib.request.urlretrieve(response.data[0].url, str(output_path))
            log.info(f"  ✅ DALL-E image saved: {output_path.name}")
            return output_path
        except Exception as e:
            log.error(f"  ❌ DALL-E failed: {e}")

    log.warning("  ⚠️ All image generation providers failed. Skipping background.")
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  2. SCRIPT GENERATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCRIPT_SYSTEM_PROMPT = """\
You are a creative director for animated YouTube Shorts (vertical 9:16, ~60 seconds).
Given a story idea, write a script as a JSON object.

Rules:
- 5 to 8 scenes maximum
- Each scene has ONE line of dialogue (~8-15 words)
- Total dialogue should be speakable in about 50-60 seconds
- Choose an animation category from this list for each scene:
  {categories}
- Write a vivid background description for each scene (for AI image generation)
- Include an emotion tag for each scene

Respond with ONLY valid JSON (no markdown fences):
{{
  "title": "...",
  "scenes": [
    {{
      "id": 1,
      "dialogue": "...",
      "emotion": "curious|happy|sad|excited|angry|scared|thoughtful|playful",
      "anim_category": "WALK|RUN|JUMP|TALK_GESTURE|SIT_STAND|DANCE|SPORTS|DAILY_LIFE|ANIMAL|MISC",
      "bg_description": "A vivid description of the background scene, vertical composition, 9:16"
    }}
  ]
}}
"""


def generate_script(story_idea: str, max_scenes: int = 0) -> dict:
    """Ask the LLM to generate a structured script from a story idea."""
    log.info("📝 Step 1: Generating script...")

    categories = ", ".join(config.ANIMATION_CATEGORIES)
    system = SCRIPT_SYSTEM_PROMPT.format(categories=categories)
    
    if max_scenes > 0:
        system = system.replace("- 5 to 8 scenes maximum", f"- Exactly {max_scenes} scenes")

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Story idea: {story_idea}"},
    ]

    raw = llm_chat(messages, expect_json=True)

    # Robustly extract JSON from LLM response
    clean = _extract_json(raw)
    log.debug(f"  📋 Raw LLM response ({len(raw)} chars), extracted JSON ({len(clean)} chars)")

    try:
        script = json.loads(clean)
    except json.JSONDecodeError as e:
        log.error(f"  ❌ JSON parse failed. Raw response:\n{raw[:500]}")
        raise ValueError(f"LLM returned invalid JSON: {e}") from e

    # Validate
    assert "scenes" in script, "Script JSON missing 'scenes' key"
    assert len(script["scenes"]) >= 1, "Script must have at least 1 scene"

    log.info(f"  📜 Script: '{script.get('title', 'Untitled')}' — {len(script['scenes'])} scenes")
    return script


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  3. SEMANTIC DIRECTOR — Intelligent animation selection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def semantic_director(scene: dict) -> Path:
    """
    Two-pass animation selection:
    1. List all animations in the chosen category.
    2. Send the top candidates to the LLM to pick the best match.
    """
    category = scene.get("anim_category", "talk")
    emotion = scene.get("emotion", "neutral")
    dialogue = scene.get("dialogue", "")

    category_aliases = {
        "talk_gesture": "talk",
        "talk": "talk",
        "walk": "walking",
        "walking": "walking",
        "run": "walking",
        "jump": "action",
        "sit_stand": "idle",
        "idle": "idle",
        "reaction": "reaction",
        "action": "action",
        "transition": "transition",
        "dance": "action",
        "sports": "action",
        "daily_life": "action",
        "animal": "action",
        "misc": "reaction",
    }

    category_key = str(category).strip().lower()
    if category_key in category_aliases:
        category = category_aliases[category_key]

    def _collect_fbx_files(path: Path, recursive: bool = False) -> list[Path]:
        if not path.exists():
            return []
        pattern = "**/*.fbx" if recursive else "*.fbx"
        return sorted(path.glob(pattern))

    selected_category = category
    cat_dir = config.ANIMATIONS_LIB / category
    fbx_files = _collect_fbx_files(cat_dir)
    if not fbx_files:
        log.warning(f"  ⚠️ Category '{category}' not found or empty, falling back to TALK_GESTURE")
        selected_category = "TALK_GESTURE"
        cat_dir = config.ANIMATIONS_LIB / selected_category
        fbx_files = _collect_fbx_files(cat_dir)
    if not fbx_files:
        log.warning("  ⚠️ TALK_GESTURE empty, falling back to MISC")
        selected_category = "MISC"
        cat_dir = config.ANIMATIONS_LIB / selected_category
        fbx_files = _collect_fbx_files(cat_dir)
    if not fbx_files:
        # Last resort: grab any FBX in the library tree
        selected_category = "ANY"
        cat_dir = config.ANIMATIONS_LIB
        fbx_files = _collect_fbx_files(cat_dir) or _collect_fbx_files(cat_dir, recursive=True)

    # Pass 1: Get all animation files and extract descriptions
    anims = []
    for fbx_file in fbx_files:
        # Filename format: 02_01_walk_forward.fbx → desc = "walk forward"
        name = fbx_file.stem
        parts = name.split("_", 2)  # Split off the ID prefix
        desc = parts[2].replace("_", " ") if len(parts) > 2 else name.replace("_", " ")
        anims.append({"file": str(fbx_file), "name": fbx_file.name, "description": desc})

    if not anims:
        raise FileNotFoundError(f"No .fbx files found in {cat_dir}")

    # Limit to top N candidates (by simple keyword overlap)
    candidates = _rank_candidates(anims, emotion, dialogue)[:config.MAX_ANIMATION_CANDIDATES]

    # Pass 2: Ask LLM to pick the best
    prompt = f"""Pick the BEST animation for this scene.

Scene dialogue: "{dialogue}"
Scene emotion: {emotion}
Animation category: {selected_category}

Available animations (index — description):
{chr(10).join(f"  {i}. {c['description']} (file: {c['name']})" for i, c in enumerate(candidates))}

Respond with ONLY the index number (e.g., "3"). Nothing else."""

    messages = [
        {"role": "system", "content": "You are an animation director. Pick the single best animation."},
        {"role": "user", "content": prompt},
    ]

    response = llm_chat(messages)
    try:
        idx = int(response.strip().split()[0].rstrip("."))
        idx = max(0, min(idx, len(candidates) - 1))
    except (ValueError, IndexError):
        idx = 0

    chosen = Path(candidates[idx]["file"])
    log.info(f"  🎭 Chosen animation: {chosen.name} (emotion: {emotion})")
    return chosen


def _rank_candidates(anims: list[dict], emotion: str, dialogue: str) -> list[dict]:
    """Simple keyword-overlap ranking to pre-filter candidates."""
    keywords = set((emotion + " " + dialogue).lower().split())

    def score(anim):
        desc_words = set(anim["description"].lower().split())
        return len(keywords & desc_words)

    return sorted(anims, key=score, reverse=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  4. VOICE GENERATION (Kokoro TTS)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def generate_voice(text: str, output_path: Path) -> float:
    """
    Generate speech audio using Kokoro TTS.
    Returns: audio duration in seconds.
    """
    log.info(f"  🎙️ Generating TTS: '{text[:50]}...'")

    try:
        from kokoro import KPipeline

        pipeline = KPipeline(lang_code="a")  # 'a' = American English
        generator = pipeline(
            text,
            voice=config.KOKORO_VOICE,
            speed=config.KOKORO_SPEED,
        )

        # Kokoro yields chunks — concatenate them
        import soundfile as sf
        import numpy as np

        all_audio = []
        for _, _, audio_chunk in generator:
            all_audio.append(audio_chunk)

        if not all_audio:
            raise RuntimeError("Kokoro TTS produced no audio")

        full_audio = np.concatenate(all_audio)
        sf.write(str(output_path), full_audio, config.KOKORO_SAMPLE_RATE)

        duration = len(full_audio) / config.KOKORO_SAMPLE_RATE
        log.info(f"  ✅ Audio saved: {output_path.name} ({duration:.1f}s)")
        return duration

    except ImportError:
        log.error("  ❌ Kokoro not installed. Run: pip install kokoro")
        raise


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  5. BACKGROUND GENERATION (Flux via G4F)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def generate_background(description: str, output_path: Path):
    """Generate a 9:16 background image for a scene. Returns Path or None."""
    log.info(f"  🖼️ Generating background: '{description[:60]}...'")

    prompt = (
        f"Vertical 9:16 background for animation. "
        f"No characters, no text, no logos. "
        f"Cinematic, detailed, vibrant. "
        f"Scene: {description}"
    )

    return llm_generate_image(prompt, output_path)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  6. GODOT RENDERING (subprocess)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def render_scene(scene_data: dict, scene_dir: Path, dry_run: bool = False) -> Path:
    """
    Write scene JSON and invoke Godot headless to render.
    Returns: path to rendered .mp4 clip.
    """
    json_path = scene_dir / "scene_data.json"
    output_mp4 = scene_dir / "render.mp4"

    with open(json_path, "w") as f:
        json.dump(scene_data, f, indent=2, default=str)

    cmd = [
        sys.executable,
        str(config.PROJECT_ROOT / "godot_render.py"),
        "--scene_data", str(json_path),
    ]

    log.info(f"  🎬 Godot command: {' '.join(cmd[-3:])}")

    if dry_run:
        log.info("  ⏭️  [DRY-RUN] Skipping Godot render")
        return output_mp4

    # Run Godot and stream output so it doesn't look frozen
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=str(config.PROJECT_ROOT),
    )

    # Print Godot output in real-time
    for line in iter(process.stdout.readline, ""):
        line_clean = line.strip()
        if line_clean:
            log.info(f"    🎥 {line_clean}")

    process.stdout.close()
    return_code = process.wait()

    if return_code != 0:
        log.error(f"  ❌ Godot failed with code {return_code}")
        raise RuntimeError(f"Godot render failed for scene {scene_data.get('id')}")

    log.info(f"  ✅ Rendered: {output_mp4.name}")
    return output_mp4


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  7. SUBTITLE GENERATION (Whisper)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def generate_subtitles(audio_path: Path) -> list[dict]:
    """
    Use Whisper to generate word-level timestamps from audio.
    Returns: list of {word, start, end} dicts.
    """
    log.info(f"  📝 Generating subtitles with Whisper ({config.WHISPER_MODEL})...")

    try:
        import whisper

        model = whisper.load_model(config.WHISPER_MODEL)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = model.transcribe(
                str(audio_path),
                word_timestamps=True,
                language="en",
                fp16=False,
            )

        words = []
        for segment in result.get("segments", []):
            for w in segment.get("words", []):
                words.append({
                    "word": w["word"].strip(),
                    "start": round(w["start"], 3),
                    "end": round(w["end"], 3),
                })

        log.info(f"  ✅ {len(words)} words timestamped")
        return words

    except ImportError:
        log.error("  ❌ Whisper not installed. Run: pip install openai-whisper")
        raise


def _generate_ass_subtitles(all_scenes_words: list[dict], output_path: Path) -> Path:
    """Generate an ASS subtitle file with word-by-word highlighting."""
    header = f"""[Script Info]
Title: Pipeline Subtitles
ScriptType: v4.00+
PlayResX: {config.RENDER_WIDTH}
PlayResY: {config.RENDER_HEIGHT}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{config.SUBTITLE_FONT},{config.SUBTITLE_FONTSIZE},{config.SUBTITLE_COLOR},&H000000FF,{config.SUBTITLE_OUTLINE_COLOR},&H80000000,-1,0,0,0,100,100,0,0,1,{config.SUBTITLE_OUTLINE_WIDTH},0,2,40,40,{config.SUBTITLE_POSITION_Y},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    # Group words into subtitle lines (3-5 words per line)
    chunk_size = 4
    for i in range(0, len(all_scenes_words), chunk_size):
        chunk = all_scenes_words[i:i + chunk_size]
        if not chunk:
            continue
        start = chunk[0]["start"]
        end = chunk[-1]["end"]
        text = " ".join(w["word"] for w in chunk)
        start_ts = _seconds_to_ass_time(start)
        end_ts = _seconds_to_ass_time(end)
        events.append(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{text}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(events))

    return output_path


def _seconds_to_ass_time(seconds: float) -> str:
    """Convert seconds to ASS timestamp format H:MM:SS.CC."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  8. FINAL ASSEMBLY (FFmpeg)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def assemble_final_video(
    scene_clips: list[dict],
    output_path: Path,
    dry_run: bool = False,
) -> Path:
    """
    Merge all scene clips + audio + subtitles into the final video.
    scene_clips: list of {video: Path, audio: Path, words: list}
    """
    log.info("🎬 Step 6: Assembling final video...")

    concat_dir = output_path.parent
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ── 1. Generate word timestamps for all scenes ──
    all_words = []
    time_offset = 0.0
    concat_entries = []

    for i, sc in enumerate(scene_clips):
        # Adjust word timestamps with cumulative offset
        for w in sc.get("words", []):
            all_words.append({
                "word": w["word"],
                "start": w["start"] + time_offset,
                "end": w["end"] + time_offset,
            })

        # Get audio duration for offset
        if sc["audio"].exists():
            with wave.open(str(sc["audio"]), "r") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                duration = frames / float(rate)
        else:
            duration = 5.0  # Fallback

        time_offset += duration
        concat_entries.append(f"file '{sc['video']}'")

    # ── 2. Write concat list ──
    concat_file = concat_dir / "concat_list.txt"
    concat_file.write_text("\n".join(concat_entries))

    # ── 3. Generate ASS subtitle file ──
    ass_file = concat_dir / "subtitles.ass"
    _generate_ass_subtitles(all_words, ass_file)

    # ── 4. Concatenate all audio files ──
    audio_concat_file = concat_dir / "audio_concat_list.txt"
    audio_entries = [f"file '{sc['audio']}'" for sc in scene_clips]
    audio_concat_file.write_text("\n".join(audio_entries))
    merged_audio = concat_dir / "merged_audio.wav"

    if dry_run:
        log.info("  ⏭️  [DRY-RUN] Skipping FFmpeg assembly")
        return output_path

    # Merge audio
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(audio_concat_file),
        "-c", "copy", str(merged_audio),
    ], capture_output=True, text=True)

    # ── 5. Final FFmpeg: video + audio + subtitles ──
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-i", str(merged_audio),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-vf", f"ass=f='{ass_file.name}'",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path),
    ]

    log.info(f"  🔧 FFmpeg final assembly...")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(concat_dir))

    if result.returncode != 0:
        log.error(f"  ❌ FFmpeg failed:\n{result.stderr[-500:]}")
        raise RuntimeError("FFmpeg assembly failed")

    log.info(f"  ✅ Final video: {output_path}")
    return output_path


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN PIPELINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def run_pipeline(story_idea: str, dry_run: bool = False, draft: bool = False, test_scenes: int = 0):
    """Full pipeline: story → rendered YouTube Short."""

    log.info("=" * 60)
    log.info(f"🚀 3D AI Content Pipeline")
    log.info(f"📖 Story: '{story_idea}'")
    mode_str = []
    if dry_run:
        mode_str.append("🧪 DRY-RUN")
    if draft:
        mode_str.append("⚡ DRAFT MODE (540x960)")
    if test_scenes > 0:
        mode_str.append(f"⏱️ TEST SCENES ({test_scenes})")
    if not mode_str:
        mode_str.append("🎬 PRODUCTION MODE")
    log.info(" | ".join(mode_str))
    log.info("=" * 60)

    # Ensure directories exist
    config.TEMP_DIR.mkdir(parents=True, exist_ok=True)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Check Master_Scene.blend
    if not config.MASTER_BLEND.exists() and not dry_run:
        log.info("🔧 Master_Scene.blend not found — building it...")
        subprocess.run(
            [str(config.BLENDER_BIN), "-b", "-P", str(config.PROJECT_ROOT / "build_stage.py")],
            capture_output=True, text=True,
            cwd=str(config.PROJECT_ROOT),
        )
        if not config.MASTER_BLEND.exists():
            raise FileNotFoundError("Failed to generate Master_Scene.blend")

    # ── Step 1: Generate Script ──
    script = generate_script(story_idea, max_scenes=test_scenes)
    import re
    title = re.sub(r'[^a-z0-9_]', '', script.get("title", "untitled").replace(" ", "_").lower())[:30]

    # ── Step 2-5: Process each scene ──
    scene_clips = []
    for i, scene in enumerate(script["scenes"]):
        if test_scenes > 0 and i >= test_scenes:
            log.info(f"  ⏭️ Stopping early at scene {i+1} due to --test-scenes={test_scenes}")
            break

        scene_id = scene["id"]
        log.info(f"\n{'─' * 40}")
        log.info(f"🎬 Scene {scene_id}: \"{scene['dialogue'][:40]}...\"")
        log.info(f"{'─' * 40}")

        scene_dir = config.TEMP_DIR / f"scene_{scene_id:02d}"
        scene_dir.mkdir(parents=True, exist_ok=True)

        # 2. Semantic Director — choose animation
        if dry_run:
            try:
                anim_path = semantic_director(scene)
            except Exception as e:
                log.warning(f"  ⚠️ Semantic director skipped: {e}")
                anim_path = Path("placeholder.fbx")
        else:
            anim_path = semantic_director(scene)

        # 3. Generate voice audio
        audio_path = scene_dir / "dialogue.wav"
        if dry_run:
            log.info("  ⏭️  [DRY-RUN] Skipping TTS")
            audio_duration = 5.0
        else:
            audio_duration = generate_voice(scene["dialogue"], audio_path)

        # 4. Generate background image
        bg_path_expected = scene_dir / "background.png"
        if dry_run:
            log.info("  ⏭️  [DRY-RUN] Skipping background generation")
            bg_path = ""
        else:
            actual_bg = generate_background(scene["bg_description"], bg_path_expected)
            bg_path = str(actual_bg) if actual_bg else ""

        # 5. Render in Godot
        scene_render_data = {
            "id": scene_id,
            "scene_text": scene["dialogue"],
            "character_file_path": str(config.CHARACTERS_DIR / config.DEFAULT_CHARACTER),
            "animation_file_path": str(anim_path),
            "background_image_path": bg_path,
            "audio_file_path": str(audio_path),
            "audio_duration": audio_duration,
            "output_mp4": str(scene_dir / "render.mp4"),
            "output_frames_dir": str(scene_dir / "frames"),
            "use_movie_writer": True,
            "movie_file": str(scene_dir / "movie.avi"),
            "fps": config.RENDER_FPS,
            "resolution": [540, 960] if draft else [config.RENDER_WIDTH, config.RENDER_HEIGHT],
        }

        render_path = render_scene(scene_render_data, scene_dir, dry_run=dry_run)

        # Generate subtitles from audio
        words = []
        if not dry_run and audio_path.exists():
            words = generate_subtitles(audio_path)

        scene_clips.append({
            "video": render_path,
            "audio": audio_path,
            "words": words,
        })

    # ── Step 6: Final Assembly ──
    output_file = config.OUTPUT_DIR / f"{title}_final.mp4"
    assemble_final_video(scene_clips, output_file, dry_run=dry_run)

    log.info("\n" + "=" * 60)
    log.info(f"🏁 Pipeline complete!")
    log.info(f"📁 Output: {output_file}")
    log.info("=" * 60)

    return output_file


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CLI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    parser = argparse.ArgumentParser(
        description="3D AI Content Pipeline — Story → YouTube Short"
    )
    parser.add_argument(
        "story",
        type=str,
        help='Story idea in quotes, e.g. "A curious turtle discovers a hidden garden"',
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without Godot/TTS/image-gen (validates LLM + file structure)",
    )
    parser.add_argument(
        "--draft",
        action="store_true",
        help="Render at 540x960 for 4x faster execution",
    )
    parser.add_argument(
        "--test-scenes",
        type=int,
        default=0,
        help="Limit the number of scenes generated (e.g., --test-scenes 3)",
    )
    args = parser.parse_args()

    try:
        run_pipeline(args.story, dry_run=args.dry_run, draft=args.draft, test_scenes=args.test_scenes)
    except Exception as e:
        log.error(f"\n💥 Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
