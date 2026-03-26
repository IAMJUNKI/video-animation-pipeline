"""
character_generator.py — Generate 2.5D character sprites using Gemini.

Usage:
  python character_generator.py "A friendly turtle in a hoodie" --draft
"""
import argparse
import logging
import sys
from pathlib import Path

from google import genai
from google.genai import types

import config

# ─── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("character_generator")


def generate_25d_character(character_desc: str, output_path: Path, draft: bool = False) -> Path:
    # 512px for draft, 1024px for high quality
    prompt = (
        f"{character_desc}, full body visible, flat 2D vector art style, "
        f"standing straight, isolated on a pure, bright chroma green background. "
        f"No shadows on the floor, crisp edges."
    )

    if not config.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set. Add it to .env or your environment.")

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    response = client.models.generate_content(
        model="gemini-3.1-flash-image-preview",
        contents=[prompt]
    )

    if not response.candidates or not response.candidates[0].content.parts:
        raise RuntimeError("No image data returned by the model.")

    # 2. Extract the image bytes from the response parts
    image_bytes = None
    for part in response.candidates[0].content.parts:
        if part.inline_data:
            image_bytes = part.inline_data.data
            break
            
    if not image_bytes:
         raise RuntimeError("No inline image data found in the response.")

    # 3. Save the bytes directly
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(image_bytes)

    if draft:
        try:
            from PIL import Image
        except ImportError as e:
            log.warning("Pillow not installed; skipping draft downscale: %s", e)
            return output_path

        with Image.open(output_path) as img:
            if img.size != (512, 512):
                img = img.resize((512, 512), Image.LANCZOS)
                img.save(output_path)

    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a 2.5D character sprite with Gemini")
    parser.add_argument(
        "description",
        type=str,
        help='Character description, e.g. "A friendly turtle in a hoodie"',
    )
    parser.add_argument(
        "--output",
        type=str,
        default="characters/latest.png",
        help="Output path for the generated sprite",
    )
    parser.add_argument(
        "--draft",
        action="store_true",
        help="Downscale output to 512x512 for faster iteration",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = (config.PROJECT_ROOT / output_path).resolve()

    try:
        log.info("🎨 Generating 2.5D character...")
        result = generate_25d_character(args.description, output_path, draft=args.draft)
        log.info("✅ Character saved: %s", result)
        return 0
    except Exception as e:
        log.error("❌ Character generation failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
