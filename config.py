"""
config.py — Central configuration for the 3D AI Content Pipeline.
All paths, API keys, and constants live here.
"""
import os
from pathlib import Path

# Load .env file if present (pip install python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass  # dotenv not installed — rely on system env vars

# ─── Project Paths ───────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "Assets"
CHARACTERS_DIR = ASSETS_DIR / "Characters"
ANIMATIONS_LIB = ASSETS_DIR / "Animations" / "Library"
BACKGROUNDS_DIR = ASSETS_DIR / "Backgrounds"
BACKGROUNDS_LIB = BACKGROUNDS_DIR / "Library"
MASTER_BLEND = PROJECT_ROOT / "Master_Scene.blend"
OUTPUT_DIR = PROJECT_ROOT / "Outputs"
TEMP_DIR = PROJECT_ROOT / "temp_renders"

# ─── Blender ─────────────────────────────────────────────────────────
BLENDER_BIN = os.getenv(
    "BLENDER_BIN",
    "/Applications/Blender.app/Contents/MacOS/Blender"
)

# ─── Godot ──────────────────────────────────────────────────────────
GODOT_PROJECT_DIR = PROJECT_ROOT / "godot_project"
GODOT_BIN = os.getenv(
    "GODOT_BIN",
    "/Applications/Godot.app/Contents/MacOS/Godot"
)
GODOT_DISPLAY_DRIVER = os.getenv("GODOT_DISPLAY_DRIVER", "")
GODOT_RENDERING_DRIVER = os.getenv("GODOT_RENDERING_DRIVER", "")
GODOT_FALLBACK_DISPLAY_DRIVER = os.getenv("GODOT_FALLBACK_DISPLAY_DRIVER", "")

# ─── Render Settings ─────────────────────────────────────────────────
RENDER_WIDTH = 1080
RENDER_HEIGHT = 1920
RENDER_FPS = 30
RENDER_ENGINE = "BLENDER_EEVEE_NEXT"  # Blender 4.x EEVEE
RENDER_SAMPLES = 16  # 16 + TAA reprojection ≈ quality of 64, ~4x faster

# ─── Character ───────────────────────────────────────────────────────
DEFAULT_CHARACTER = "Turtle.fbx"

# G4F models to try in order before falling back to the official API
# Most models require a key now, so we only try gpt-4o-mini
G4F_MODELS = [
    "gpt-4o-mini",
]

# Official OpenAI fallback (set via env var or .env file)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-nano")

# ─── Gemini (Google AI — primary) ────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Models to try in order (handles 503 overload gracefully)
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]

# ─── G4F Settings ────────────────────────────────────────────────────
G4F_TIMEOUT = 15  # seconds per model attempt

# ─── Image Generation (G4F Flux / DALL-E fallback) ───────────────────
BING_U_COOKIE = os.getenv("BING_U_COOKIE", "")
G4F_IMAGE_MODELS = [
    "dall-e-3",
    "flux",
    "flux-pro",
]
IMAGE_WIDTH = 1080
IMAGE_HEIGHT = 1920

# ─── Voice (Kokoro TTS) ─────────────────────────────────────────────
KOKORO_VOICE = "af_heart"  # Default voice
KOKORO_SPEED = 1.0
KOKORO_SAMPLE_RATE = 24000
KOKORO_DEFAULT_LANG = "en"
KOKORO_LANG_MAP = {
    "en": "a",  # American English
}
KOKORO_VOICE_NARRATOR = "af_heart"
KOKORO_VOICE_CHARACTER = "af_heart"

# ─── Whisper (Subtitle Generation) ───────────────────────────────────
WHISPER_MODEL = "base"  # tiny, base, small, medium, large
SUBTITLE_WORDS_PER_LINE = 1

# ─── FFmpeg Subtitles ────────────────────────────────────────────────
SUBTITLE_FONT = "Arial"
SUBTITLE_FONTSIZE = 48
SUBTITLE_COLOR = "&H00FFFFFF"  # White (ASS format: AABBGGRR)
SUBTITLE_OUTLINE_COLOR = "&H00000000"  # Black outline
SUBTITLE_OUTLINE_WIDTH = 3
SUBTITLE_POSITION_Y = 250  # Pixels from bottom

# ─── Pipeline Defaults ───────────────────────────────────────────────
MAX_SCENES = 8
TARGET_DURATION_SEC = 60
MAX_ANIMATION_CANDIDATES = 10  # Top-N animations sent to LLM for selection
DEFAULT_NARRATION_MODE = "third"
DEFAULT_CAMERA_MOTION = "random"

# ─── Animation Categories (mirrors organize_animations.py) ──────────
ANIMATION_CATEGORIES = [
    "talk", "idle", "reaction", "action", "transition", "walking",
]

# ─── Background Categories (3D scenes) ───────────────────────────────
BACKGROUND_CATEGORIES = [
    "forest",
    "school",
    "city",
    "interior",
    "beach",
    "garden",
    "village",
    "cave",
    "mountain",
]
