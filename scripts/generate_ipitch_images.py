#!/usr/bin/env python3
"""Generate illustrated images for the investor pitch deck (docs/ipitch.html).

Style mirrors the Sonia recruiting pitch: editorial line illustration,
flat muted color washes, cream paper background. Concepts are abstract
and conceptual (no people likeness) — appropriate for investor framing.

Run with --slide title to generate one slide for style approval, or
--all to generate every slide image.
"""

import argparse
import os
import sys
from pathlib import Path
from google import genai
from google.genai import types

MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "img" / "ipitch"

STYLE = (
    "Editorial line illustration in the style of Christoph Niemann or Malika Favre. "
    "Confident, slightly imperfect black ink linework — fine pen, no sketchy hatching. "
    "Flat color fills using a tight palette of warm muted tones: "
    "soft cream paper background (#f4efe2), deep vine green (#1a4d2e), warm gold-ochre (#8b7b4a), "
    "and a touch of emerald accent (#34d399) used sparingly. "
    "Generous negative space. Slightly off-register flat color shapes that don't perfectly match the linework — like risograph or screenprint. "
    "Modern, calm, intelligent, magazine-editorial mood. Minimal but specific. "
    "NO photorealism. NO 3D. NO gradients. NO heavy shading. NO watercolor. NO text or words anywhere in the image. "
    "Square 1:1 aspect ratio composition. White margin around the subject."
)

SLIDES = {
    "title": {
        "filename": "01-title.jpg",
        "prompt": (
            "A stylized greenhouse and warehouse silhouette merged into a single building, with vine leaves "
            "growing along the roofline and a single small emerald-green node glowing inside the structure — "
            "suggesting a place that is half garden, half intelligent system. Calm, iconic, foundational."
        ),
    },
    "problem": {
        "filename": "02-problem.jpg",
        "prompt": (
            "Five small disconnected buildings in a row — a gym, a cafe, a sauna, a workshop, an apartment — "
            "each illustrated as a tiny separate icon, separated by empty negative space, with no path or "
            "thread between them. A single small lone figure silhouette stands between them looking lost. "
            "The composition feels fragmented, isolating, and inefficient."
        ),
    },
    "why-now": {
        "filename": "03-why-now.jpg",
        "prompt": (
            "An open eye stylized as a circle, with a network of fine line-work circuits and small glowing "
            "emerald nodes radiating outward into a stylized landscape of plants, buildings, and people. "
            "The eye is calm, watchful, and integrated into the environment — suggesting AI as ambient "
            "infrastructure, not a screen or device."
        ),
    },
    "solution": {
        "filename": "04-solution.jpg",
        "prompt": (
            "A single circular floor-plan diagram divided into six wedges, each wedge containing a tiny "
            "iconographic symbol: a leaf (cultivate), two figures together (connect), an open book (learn), "
            "a moving body in motion (move), a sound wave (vibe), and a curving steam shape (restore). "
            "At the center of the circle, a small glowing emerald node. Clean, schematic, confident — "
            "the brain and body of the venue in one diagram."
        ),
    },
    "product": {
        "filename": "05-product.jpg",
        "prompt": (
            "An exploded isometric-style diagram of a single building, with stylized layers floating apart: "
            "a greenhouse roof with plants, a thermal circuit floor with small steam shapes, a movement studio "
            "with a yoga pose silhouette, a market floor with vendor stalls, and a maker space with a 3D printer. "
            "Thin connecting lines tie the layers together. Schematic and elegant, not photorealistic."
        ),
    },
    "brain": {
        "filename": "06-brain.jpg",
        "prompt": (
            "A continuous loop drawn as a stylized circular arrow, with four labeled stages represented "
            "iconographically (no actual text): an eye for observe, a brain or node cluster for reason, "
            "a hand or actuator shape for actuate, and a small sprout for learn. The loop is filled with "
            "small emerald glowing nodes connected by fine line-work. Set on a deep vine-green background "
            "instead of cream — the only inverted slide. Suggests intelligence and continuous improvement."
        ),
    },
    "market": {
        "filename": "07-market.jpg",
        "prompt": (
            "Four overlapping circles arranged as a Venn diagram, each circle representing a category: "
            "a small dumbbell for wellness, a fork and knife for dining, a desk for coworking, a sofa with "
            "candle for social club. At the center where all four circles overlap, a single small emerald "
            "leaf marks the intersection. The composition feels analytical and confident, like a strategy "
            "consulting diagram with personality."
        ),
    },
    "model": {
        "filename": "08-model.jpg",
        "prompt": (
            "Three stylized streams of small flowing dots converging into a single tall vase or vessel "
            "growing a flowering plant. Each stream is a different color (vine green, gold-ochre, emerald) "
            "representing day passes, memberships, and market commission. The composition is botanical, "
            "calm, and suggests revenue compounding into growth."
        ),
    },
    "unit": {
        "filename": "09-unit.jpg",
        "prompt": (
            "A simple line chart drawn as a single elegant curve climbing from lower-left to upper-right, "
            "crossing a horizontal dashed line that represents breakeven. Below the curve is filled with a "
            "soft gold-ochre wash; above the curve is filled with a soft vine-green wash. A single small "
            "emerald dot marks the breakeven crossing point. The line is hand-drawn and slightly imperfect — "
            "confident but not corporate."
        ),
    },
    "gtm": {
        "filename": "10-gtm.jpg",
        "prompt": (
            "Three stylized growing plants arranged in a horizontal row from left to right: a small sprout "
            "with two leaves (phase 1), a young plant with several leaves (phase 2), and a full flowering "
            "plant with many leaves and a single fruit (phase 3). Each plant is rooted in its own small "
            "soil mound. A continuous thin line connects the soil mounds underneath. Suggests a phased, "
            "patient launch strategy — growth, not blitz."
        ),
    },
    "moat": {
        "filename": "11-moat.jpg",
        "prompt": (
            "A stylized castle-keep or fortress reimagined as a botanical structure: a central tower made "
            "of a thick tree trunk, surrounded by four concentric circular walls, each wall labeled "
            "iconographically (no text) — a scroll for patent, a network of dots for data, gear-and-leaf "
            "for integration, and connected silhouettes for community. Vines climb the central trunk. "
            "Defensibility as something living, not just legal."
        ),
    },
    "team": {
        "filename": "12-team.jpg",
        "prompt": (
            "Two abstract stylized figures (no faces, just elegant silhouettes) standing side by side, "
            "each holding a different tool: one holds a sprouting plant, the other holds a small glowing "
            "emerald node. Between them, a single thin line connects their hands. Behind them, a horizon "
            "line and a single rising sun. Suggests complementary partnership, not symmetry."
        ),
    },
    "ask": {
        "filename": "13-ask.jpg",
        "prompt": (
            "A single stylized hand offering a small acorn or seed with a tiny emerald sprout already "
            "emerging from its top. The hand is open, palm up, drawn confidently. Around the hand, a few "
            "thin radiating lines suggest the seed's potential. Calm, intentional, the gesture of an ask "
            "that is also an offering."
        ),
    },
    "close": {
        "filename": "14-close.jpg",
        "prompt": (
            "A single stylized doorway or archway opening onto a horizon, with a path of stepping stones "
            "leading through it. Vines climb the sides of the archway. Through the opening, a soft emerald "
            "glow and several small floating glowing nodes suggest a future being built. The viewer is on "
            "the threshold. Set against a deep vine-green background — inverted from cream — to mirror the "
            "closing slide's dark aesthetic. Forward-moving, decisive, hopeful."
        ),
    },
}


def generate(slide_id: str, skip_existing: bool = False):
    spec = SLIDES[slide_id]
    out_path = OUTPUT_DIR / spec["filename"]

    if skip_existing and out_path.exists():
        print(f"SKIP [{slide_id}] -> {spec['filename']} (already exists)")
        return out_path

    key_file = Path("/tmp/.gemini_key_sg")
    api_key = key_file.read_text().strip() if key_file.exists() else os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: No Gemini API key found at /tmp/.gemini_key_sg or $GEMINI_API_KEY")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    full_prompt = f"{spec['prompt']}\n\n{STYLE}"
    print(f"Generating [{slide_id}] -> {spec['filename']} (model={MODEL}) ...")

    response = client.models.generate_content(
        model=MODEL,
        contents=full_prompt,
        config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            with open(out_path, "wb") as f:
                f.write(part.inline_data.data)
            size = out_path.stat().st_size
            print(f"  -> Saved {out_path} ({size:,} bytes)")
            return out_path

    text = " ".join(p.text for p in response.candidates[0].content.parts if getattr(p, "text", None))
    print(f"  -> NO IMAGE returned. Text: {text[:300]}")
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--slide", default="title", help="single slide id to generate")
    parser.add_argument("--all", action="store_true", help="generate all slides")
    args = parser.parse_args()

    if args.all:
        for sid in SLIDES.keys():
            generate(sid, skip_existing=True)
    else:
        generate(args.slide)
