# CLI Flags Reference

This file documents **all CLI flags** supported by `main.py`.

## Usage

```bash
python main.py "A curious turtle discovers a hidden garden"
```

## Positional Argument

- `story` (required): Story idea in quotes.

## Core Pipeline Flags

- `--dry-run`
  - Run without Godot/TTS/background selection. Validates LLM + file structure only.
  - Default: disabled.
- `--draft`
  - Render at 540x960 for faster iteration.
  - Default: disabled (uses 1080x1920).
- `--test-scenes <int>`
  - Limit the number of scenes generated.
  - Default: `0` (no limit).

## Narration & TTS

- `--narration {third,first,mixed}`
  - `third`: narrator only  
  - `first`: character only  
  - `mixed`: narrator + occasional character lines  
  - Default: `third`
- `--tts-lang <code>`
  - Language code mapped to Kokoro `lang_code` (see `docs/kokoro_voices.md`).
  - Default: `en`
- `--tts-voice <voice>`
  - Default Kokoro voice (single‑voice mode).
  - Default: `af_heart`
- `--tts-voice-narrator <voice>`
  - Kokoro voice for narrator (mixed mode).
  - Default: `af_heart`
- `--tts-voice-character <voice>`
  - Kokoro voice for character (mixed mode).
  - Default: `af_heart`

## Subtitles

- `--subtitle-words <int>`
  - Number of words per subtitle line.
  - Default: `1` (word‑by‑word).

## Camera

- `--camera-motion {static,random,drift}`
  - `static`: fixed camera  
  - `drift`: subtle sinusoidal drift  
  - `random`: 50/50 static or drift per scene  
  - Default: `random`
- `--camera-seed <int>`
  - Seed for deterministic camera (and background) selection.
  - Default: none.

## Backgrounds (3D)

- `--bg-category <name>`
  - Override background category for all scenes (e.g., `forest`, `school`, `city`).
  - Default: none (LLM selects per scene).

## Examples

```bash
# Fast draft render
python main.py --draft --test-scenes 1 "A curious turtle discovers a hidden garden"

# Mixed narration with two voices
python main.py --narration mixed --tts-voice-narrator af_heart --tts-voice-character af_sky \
  "A curious turtle discovers a hidden garden"

# Force a 3D background category and static camera
python main.py --bg-category forest --camera-motion static "A curious turtle discovers a hidden garden"
```
