#!/usr/bin/env python3
"""Generate Learn and Connect experience card images using Gemini."""

import os
import sys
from pathlib import Path
from google import genai
from google.genai import types

MODEL = "gemini-3-pro-image-preview"
OUTPUT_DIR = Path(__file__).parent.parent / "branding"

IMAGES = [
    {
        "filename": "hp-17-hp-learn-workshop.jpg",
        "description": "Workshop and skill-share session in a greenhouse community space",
        "prompt": (
            "A photorealistic photograph of a hands-on workshop inside a converted industrial warehouse "
            "with greenhouse glass panels and exposed steel trusses. A diverse group of 8-10 people aged "
            "20-55 gathered around a long cedar table, learning fermentation techniques — glass jars, "
            "fresh herbs, and ingredients spread across the table. An instructor demonstrates at the head. "
            "A wall-mounted screen shows an AI-curated class schedule and skill progression tracker. "
            "Potted plants and grow lights in the background, string lights overhead. Natural light through "
            "greenhouse glass. Style: high-end editorial photography, Canon EOS R5, warm golden tones, "
            "shallow depth of field. Collaborative, focused, inviting mood."
        ),
    },
    {
        "filename": "hp-18-hp-connect-gathering.jpg",
        "description": "Community dinner and firepit gathering at Sponic Gardens",
        "prompt": (
            "A photorealistic photograph of an outdoor community dinner at golden hour in a garden courtyard "
            "adjacent to an industrial greenhouse building. A long communal table set with farm-to-table food, "
            "candles, and fresh flowers from the garden. 12-15 diverse people aged 20-60 sharing a meal, "
            "laughing, and talking animatedly. In the background, a stone firepit with a few people gathered "
            "around it. Raised garden beds and climbing plants frame the scene. String lights and lanterns "
            "overhead. The greenhouse glass walls glow warmly from inside. Style: high-end editorial "
            "photography, Canon EOS R5, golden hour light, warm tones, shallow depth of field. Convivial, "
            "warm, community-focused mood."
        ),
    },
]


def generate_images():
    key_file = Path("/tmp/.gemini_key_sg")
    api_key = key_file.read_text().strip() if key_file.exists() else os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: No API key found")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for i, img in enumerate(IMAGES):
        out_path = OUTPUT_DIR / img["filename"]
        if out_path.exists():
            print(f"[{i+1}/{len(IMAGES)}] SKIP (exists): {img['filename']}")
            continue

        print(f"[{i+1}/{len(IMAGES)}] Generating: {img['filename']}...")
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=img["prompt"],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )

            saved = False
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    with open(out_path, "wb") as f:
                        f.write(part.inline_data.data)
                    size = out_path.stat().st_size
                    print(f"  -> Saved: {img['filename']} ({size:,} bytes)")
                    saved = True
                    break

            if not saved:
                text_parts = [p.text for p in response.candidates[0].content.parts if hasattr(p, 'text') and p.text]
                print(f"  -> NO IMAGE returned. Text: {text_parts[:200] if text_parts else 'none'}")

        except Exception as e:
            print(f"  -> ERROR: {e}")

    print("\nDone!")


if __name__ == "__main__":
    generate_images()
