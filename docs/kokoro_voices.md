# Kokoro Voices & Languages

This project uses **Kokoro TTS** via `KPipeline`. Voices and language codes depend on the Kokoro package you have installed.

## Default Mapping Used by This Pipeline

| Human Language | CLI `--tts-lang` | Kokoro `lang_code` | Notes |
| --- | --- | --- | --- |
| English (US) | `en` | `a` | Default |

If you pass a language code that isn’t mapped, the pipeline falls back to `en → a`.

## How to List Voices Available on Your Machine

Run this in the project venv:

```bash
python - <<'PY'
from kokoro import KPipeline
pipeline = KPipeline(lang_code="a")
print("Available voices:", pipeline.voices)
PY
```

If the `voices` attribute isn’t available in your Kokoro build, list the installed voice files:

```bash
python - <<'PY'
import os, glob
from pathlib import Path
import site

paths = site.getsitepackages()
roots = []
for p in paths:
    roots.append(Path(p) / "kokoro")
for root in roots:
    if root.exists():
        print("Kokoro package root:", root)
        for pt in glob.glob(str(root / "**" / "*.pt"), recursive=True):
            print(" -", os.path.basename(pt))
PY
```

## CLI Usage Examples

Single‑voice:

```bash
python main.py --tts-lang en --tts-voice af_heart "A curious turtle discovers a hidden garden"
```

Mixed voices (narrator + character):

```bash
python main.py --narration mixed --tts-voice-narrator af_heart --tts-voice-character af_sky "A curious turtle discovers a hidden garden"
```

