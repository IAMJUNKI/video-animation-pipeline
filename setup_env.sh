#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# setup_env.sh — One-shot environment setup for 3D AI Content Pipeline
# ──────────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "🚀 3D AI Content Pipeline — Environment Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Python virtual environment ──────────────────────────────────
# Kokoro TTS requires Python <3.13 — prefer 3.12 if available
VENV_DIR="venv"
if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo "📦 Creating Python virtual environment..."
    if command -v python3.12 &> /dev/null; then
        echo "  ℹ️  Using python3.12 (best Kokoro TTS compatibility)"
        python3.12 -m venv "$VENV_DIR"
    elif command -v python3.11 &> /dev/null; then
        echo "  ℹ️  Using python3.11"
        python3.11 -m venv "$VENV_DIR"
    else
        echo "  ⚠️  Using python3 ($(python3 --version)). If Kokoro fails, install Python 3.12."
        python3 -m venv "$VENV_DIR"
    fi
    echo "  ✅ venv created"
else
    echo "  ✅ venv already exists"
fi

source "$VENV_DIR/bin/activate"
echo "  🐍 Python: $(python --version)"

# ── 2. Install pip dependencies ────────────────────────────────────
echo ""
echo "📥 Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  ✅ Dependencies installed"

# ── 3. Check Blender ───────────────────────────────────────────────
echo ""
echo "🔍 Checking for Blender..."
BLENDER_PATH="/Applications/Blender.app/Contents/MacOS/Blender"

if [ -f "$BLENDER_PATH" ]; then
    BLENDER_VERSION=$("$BLENDER_PATH" --version 2>/dev/null | head -1)
    echo "  ✅ Blender found: $BLENDER_VERSION"
    echo "  📁 Path: $BLENDER_PATH"
elif command -v blender &> /dev/null; then
    BLENDER_VERSION=$(blender --version 2>/dev/null | head -1)
    echo "  ✅ Blender found in PATH: $BLENDER_VERSION"
else
    echo "  ⚠️  Blender NOT found!"
    echo "     Install from: https://www.blender.org/download/"
    echo "     Or set BLENDER_BIN environment variable."
fi

# ── 4. Check Godot ────────────────────────────────────────────────
echo ""
echo "🔍 Checking for Godot..."
GODOT_PATH="/Applications/Godot.app/Contents/MacOS/Godot"

if [ -f "$GODOT_PATH" ]; then
    GODOT_VERSION=$("$GODOT_PATH" --version 2>/dev/null | head -1)
    echo "  ✅ Godot found: $GODOT_VERSION"
    echo "  📁 Path: $GODOT_PATH"
elif command -v godot &> /dev/null; then
    GODOT_VERSION=$(godot --version 2>/dev/null | head -1)
    echo "  ✅ Godot found in PATH: $GODOT_VERSION"
else
    echo "  ⚠️  Godot NOT found!"
    echo "     Install from: https://godotengine.org/download"
    echo "     Or set GODOT_BIN environment variable."
fi

# ── 5. Check FFmpeg ────────────────────────────────────────────────
echo ""
echo "🔍 Checking for FFmpeg..."
if command -v ffmpeg &> /dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version 2>/dev/null | head -1)
    echo "  ✅ FFmpeg found: $FFMPEG_VERSION"
else
    echo "  ⚠️  FFmpeg NOT found!"
    echo "     Install via: brew install ffmpeg"
fi

# ── 6. Download CMU animation library (if needed) ──────────────────
echo ""
ANIM_LIB="./Assets/Animations/Library"
if [ -d "$ANIM_LIB" ] && [ "$(ls -A "$ANIM_LIB" 2>/dev/null)" ]; then
    ANIM_COUNT=$(find "$ANIM_LIB" -name "*.fbx" 2>/dev/null | wc -l | tr -d ' ')
    echo "  ✅ Animation library found: $ANIM_COUNT FBX files"
else
    echo "📥 Animation library not found. Downloading CMU FBX library..."
    python setup_assets.py
    echo ""
    echo "📂 Organizing animations into categories..."
    python organize_animations.py
fi

# ── 7. Build Master_Scene.blend (if needed) ────────────────────────
echo ""
if [ -f "Master_Scene.blend" ]; then
    echo "  ✅ Master_Scene.blend exists"
else
    echo "🎬 Building Master_Scene.blend..."
    "$BLENDER_PATH" -b -P build_stage.py 2>/dev/null || {
        echo "  ⚠️  Could not auto-build Master_Scene.blend"
        echo "     Run manually: blender -b -P build_stage.py"
    }
fi

# ── 8. Final summary ──────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup complete!"
echo ""
echo "Quick start:"
echo "  source venv/bin/activate"
echo "  python main.py \"A curious turtle discovers a hidden garden\""
echo ""
echo "Dry-run (no GPU/Blender needed):"
echo "  python main.py --dry-run \"A curious turtle discovers a hidden garden\""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
