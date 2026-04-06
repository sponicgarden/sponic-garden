#!/usr/bin/env python3
"""Generate GTM page images using Gemini image generation."""

import os
import sys
import json
import subprocess
from pathlib import Path
from google import genai
from google.genai import types

# ── Config ──────────────────────────────────────────────────────────
MODEL = "gemini-3-pro-image-preview"  # For image generation
OUTPUT_DIR = Path(__file__).parent.parent / "branding"

# Style suffix matching homepage illustration style
STYLE = (
    "Style: hand-drawn architectural concept illustration, watercolor and ink sketch on textured paper. "
    "Muted earth tones — sage greens, warm browns, soft grays, dusty terracotta. Visible pencil and ink "
    "line work with loose watercolor washes. Digital UI screens and dashboards rendered as clean overlays "
    "with subtle data visualizations. The overall feel is a storybook architectural rendering — warm, "
    "inviting, slightly whimsical but technically detailed. NOT photorealistic — this should look like "
    "a hand-illustrated concept drawing from an architecture firm."
)

IMAGES = [
    {
        "filename": "gtm-01-site-scouting.jpg",
        "description": "Two people scouting an empty industrial warehouse for the Sponic Gardens venue",
        "category": "gtm",
        "prompt": (
            "A hand-drawn architectural illustration of two people walking through an empty industrial warehouse "
            "space with high ceilings, exposed steel trusses, and large windows. They are assessing the space, one "
            "holding a tablet showing floor plan overlays. The space has raw concrete floors and red brick walls "
            "with natural light streaming through tall windows. Overgrown plants are visible through the windows "
            "outside, hinting at the garden potential. Warm, optimistic mood. " + STYLE
        ),
    },
    {
        "filename": "gtm-02-software-setup.jpg",
        "description": "Developer setting up Sponic Gardens software infrastructure at a workspace",
        "category": "gtm",
        "prompt": (
            "A hand-drawn architectural illustration of a modern workspace inside an industrial-garden building "
            "with exposed steel trusses and climbing vines visible through glass walls. A developer sits at a "
            "wooden table with multiple screens showing app interfaces — a mobile app with plant profiles, a "
            "dashboard with sensor data graphs, and a privacy settings panel. Cedar wood accents, potted herbs "
            "on the desk, string lights visible outside. The screens show clean UI mockups with data charts. " + STYLE
        ),
    },
    {
        "filename": "gtm-03-hardware-installation.jpg",
        "description": "Technicians installing IoT sensors and irrigation in a greenhouse",
        "category": "gtm",
        "prompt": (
            "A hand-drawn architectural illustration of technicians installing IoT sensors and cameras in a "
            "greenhouse with a steel frame and glass panels. One person is mounting a small environmental sensor "
            "on a cedar post near raised garden beds, another is running irrigation tubing. Tablets and tools are "
            "spread on a workbench. Lush green plants are growing in raised cedar beds. String lights hang between "
            "steel beams. Small digital readout overlays show temperature and humidity data. " + STYLE
        ),
    },
    {
        "filename": "gtm-04-space-setup.jpg",
        "description": "Volunteers arranging social tables and garden beds at the venue",
        "category": "gtm",
        "prompt": (
            "A hand-drawn architectural illustration of a large open-air space under a corrugated metal canopy "
            "with exposed steel trusses and string lights. Eight round wooden tables with chairs are being "
            "arranged by volunteers in the space. Adjacent to the dining area, raised cedar garden beds with "
            "young plants and an irrigation system are visible. Red brick walls, stone pathways, potted plants "
            "along the edges. Warm golden light. Wide-angle view showing the full space layout. " + STYLE
        ),
    },
    {
        "filename": "gtm-05-sunday-event.jpg",
        "description": "Lively Sunday community gathering with 8 tables of guests at Sponic Gardens",
        "category": "gtm",
        "prompt": (
            "A hand-drawn architectural illustration of a lively community gathering at an industrial-garden "
            "venue on a Sunday afternoon. Eight round tables of diverse people are engaged in animated "
            "conversation under string lights and a corrugated metal canopy with exposed steel trusses. Small "
            "microphones are visible on tables. In the background, raised garden beds with lush vegetables, a "
            "greenhouse with steel and glass, and climbing vines on red brick walls. People are smiling, "
            "gesturing. Warm golden afternoon light fills the scene. " + STYLE
        ),
    },
    {
        "filename": "gtm-06-voice-interview.jpg",
        "description": "Guest doing a pre-event voice interview on their phone",
        "category": "gtm",
        "prompt": (
            "A hand-drawn architectural illustration of a person sitting in a cozy corner of an industrial-garden "
            "space, speaking into their phone during a voice interview. They're relaxed, sitting on a wooden bench "
            "near potted plants and a cedar post with string lights overhead. Through the glass wall behind them, "
            "raised garden beds and a greenhouse are visible. A small speech-bubble overlay shows the AI voice "
            "agent interface. Warm, intimate atmosphere. Exposed steel beams above, natural materials. " + STYLE
        ),
    },
    {
        "filename": "gtm-07-gamified-growing.jpg",
        "description": "Volunteers tending plants while filming for social media with gamification",
        "category": "gtm",
        "prompt": (
            "A hand-drawn architectural illustration of volunteers in a greenhouse tending to plants while one "
            "person films with a smartphone on a small tripod. A digital scoreboard or tablet mounted on a cedar "
            "post shows a leaderboard with plant growth metrics and fun team names as a clean UI overlay. People "
            "are laughing, holding freshly harvested herbs. The greenhouse has a steel frame, glass panels, raised "
            "cedar beds with thriving plants, and irrigation sensors. Bright natural daylight. Energetic and fun. " + STYLE
        ),
    },
    {
        "filename": "gtm-08-scale-up-saturday.jpg",
        "description": "Packed Saturday event showing multiple activity zones at full capacity",
        "category": "gtm",
        "prompt": (
            "A hand-drawn architectural illustration from an elevated angle showing a packed industrial-garden "
            "venue during a Saturday event. Two distinct activity zones are visible: the main covered dining area "
            "with all eight tables full of engaged guests under string lights, and an outdoor garden area where a "
            "group is doing a guided harvest among raised cedar beds. A fire pit area with wooden seating is "
            "being prepared for the evening. Cedar saunas and hot tubs with steam rising are visible in the "
            "wellness zone. Late afternoon golden light. " + STYLE
        ),
    },
]


def generate_images(api_key: str):
    """Generate all GTM images using Gemini."""
    client = genai.Client(api_key=api_key)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for i, img in enumerate(IMAGES):
        out_path = OUTPUT_DIR / img["filename"]
        if out_path.exists():
            print(f"[{i+1}/8] SKIP (exists): {img['filename']}")
            results.append({"filename": img["filename"], "status": "skipped", "path": str(out_path)})
            continue

        print(f"[{i+1}/8] Generating: {img['filename']}...")
        try:
            response = client.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=img["prompt"],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )

            # Extract image from response
            saved = False
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    with open(out_path, "wb") as f:
                        f.write(part.inline_data.data)
                    size = out_path.stat().st_size
                    print(f"  -> Saved: {img['filename']} ({size:,} bytes)")
                    results.append({
                        "filename": img["filename"],
                        "status": "success",
                        "path": str(out_path),
                        "size": size,
                        "mime": part.inline_data.mime_type,
                        "prompt": img["prompt"],
                        "description": img["description"],
                        "category": img["category"],
                    })
                    saved = True
                    break

            if not saved:
                text_parts = [p.text for p in response.candidates[0].content.parts if hasattr(p, 'text') and p.text]
                print(f"  -> NO IMAGE returned. Text: {text_parts[:200] if text_parts else 'none'}")
                results.append({"filename": img["filename"], "status": "no_image", "text": str(text_parts)[:500]})

        except Exception as e:
            print(f"  -> ERROR: {e}")
            results.append({"filename": img["filename"], "status": "error", "error": str(e)})

    # Write results summary
    results_path = OUTPUT_DIR / "gtm-generation-results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {results_path}")

    success = sum(1 for r in results if r["status"] == "success")
    print(f"\nDone: {success}/8 images generated successfully")
    return results


if __name__ == "__main__":
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)
    generate_images(api_key)
