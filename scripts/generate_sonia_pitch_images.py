#!/usr/bin/env python3
"""Generate illustrated images for the Sonia recruiting pitch deck.

Style: editorial line illustration with flat muted color washes.
Run with --slide title (or any single slide id) to generate just one image
for style approval; run with --all to generate every slide image.
"""

import argparse
import os
import sys
from pathlib import Path
from google import genai
from google.genai import types

MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")
OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "recruiting" / "img"

# Shared style preamble appended to every prompt for visual consistency.
STYLE = (
    "Editorial line illustration in the style of Christoph Niemann or Malika Favre. "
    "Confident, slightly imperfect black ink linework — fine pen, no sketchy hatching. "
    "Flat color fills using a tight palette of warm muted tones: "
    "soft cream paper background (#f4efe2), deep vine green (#1a4d2e), warm gold-ochre (#8b7b4a), "
    "and dark brown (#2d1f12) — the dark brown is reserved EXCLUSIVELY for hair fills, never used for clothing or scenery. "
    "Generous negative space. Slightly off-register flat color shapes that don't perfectly match the linework — like risograph or screenprint. "
    "Modern, calm, intelligent, magazine-editorial mood. Minimal but specific. "
    "NO photorealism. NO 3D. NO gradients. NO shading. NO watercolor. NO text or words anywhere in the image. "
    "Square 1:1 aspect ratio composition. White margin around the subject."
)

# Sonia likeness fragment — used in title and closing only.
SONIA = (
    "A young woman in her late twenties (around 27–28), of Polish/Eastern European appearance: "
    "DARK BROWN hair (almost black, NOT blonde, NOT golden, NOT ochre) pulled back in a low ponytail — "
    "her hair must be filled flat with a deep dark brown color, NOT the gold-ochre accent color. "
    "Smooth youthful skin, high cheekbones, slim athletic build, calm thoughtful expression with a hint of a smile. "
    "She looks fresh, vital, and alive — clearly in her late twenties, NOT in her thirties or forties. "
    "Drawn as a stylized illustrated character, NOT a portrait — recognizable but interpreted through the editorial illustration style. "
    "Avoid drawing any forehead lines, smile lines, or aging features."
)

SLIDES = {
    # === TEST IMAGE — START HERE ===
    "title": {
        "filename": "01-title.jpg",
        "prompt": (
            f"{SONIA} She sits in three-quarter profile, looking off to the side with a slight smile, "
            "hands resting in her lap. Behind her, a few stylized vine leaves curl upward and a single small "
            "circle (like a sun or moon) sits in the upper corner. The composition is centered, calm, and intimate — "
            "the feeling of a personal letter or invitation."
        ),
    },
    "why-you": {
        "filename": "02-why-you.jpg",
        "prompt": (
            "An overhead view of a long communal wooden table with mismatched chairs, viewed from above. "
            "Empty plates, two wine glasses, a candle, scattered crumbs, leaves, and a small vase of wildflowers — "
            "the after-image of a meaningful gathering. No people visible. The composition suggests community, intimacy, "
            "and the lived-in beauty of a shared meal."
        ),
    },
    "r1": {
        "filename": "03-reason-1-moment.jpg",
        "prompt": (
            "A single open door standing alone in an empty room. Through the doorway, a stylized network of "
            "circuit-like vines and glowing nodes extends outward — half organic, half digital. Light pours through. "
            "The door is the threshold between watching and participating."
        ),
    },
    "r2": {
        "filename": "04-reason-2-capacity.jpg",
        "prompt": (
            "A tall, slightly leaning ladder reaching upward into open space, with a few green leaves growing out "
            "of one of the rungs. A small figure (no specific likeness, generic silhouette) stands at the bottom looking up. "
            "The ladder vanishes off the top of the frame — no visible ceiling. Calm, purposeful, aspirational."
        ),
    },
    "r3": {
        "filename": "05-reason-3-people.jpg",
        "prompt": (
            "A constellation of stylized human silhouettes in profile, each one a different shape and size, connected "
            "by thin line-work paths between them — like a star map of relationships. A few of the figures glow softly with "
            "a gold-ochre fill. No faces, just elegant silhouettes. The composition feels like a network of people, not a crowd."
        ),
    },
    "r4": {
        "filename": "06-reason-4-organization.jpg",
        "prompt": (
            "A blueprint-style cross-section of a small organic structure — half tree, half building — with rooms inside the "
            "trunk and branches. Tiny generic silhouette figures move between the rooms. Roots spread underground in clean line-work. "
            "Suggests both biology and architecture: an organization growing like a living thing."
        ),
    },
    "r5": {
        "filename": "07-reason-5-ideas.jpg",
        "prompt": (
            "A single hand, palm up and open, with a small green sprout growing out of the center of the palm. Around the hand, "
            "a few stylized petals and circles drift in negative space. Quiet, hopeful, intimate."
        ),
    },
    "r6": {
        "filename": "08-reason-6-economic.jpg",
        "prompt": (
            "Three stylized seed-pods on a single curved vine, each one a different size. The middle pod is open and a small "
            "gold coin (or sun) is emerging from it. The composition is clean, botanical, and quietly confident — wealth grown, not extracted."
        ),
    },
    "r7": {
        "filename": "09-reason-7-doors.jpg",
        "prompt": (
            "A row of five stylized doorways of slightly different shapes (arched, rectangular, rounded) standing in open space, "
            "each slightly ajar. A vine grows along the ground in front of all of them, connecting them. Suggests optionality "
            "and future paths opening, not closing."
        ),
    },
    "r8": {
        "filename": "10-reason-8-fun.jpg",
        "prompt": (
            "Two abstract stylized figures (no faces, just elegant silhouettes) leaning together over a small fire or candle, "
            "laughing — implied through posture, not facial detail. A few sparks rise upward into negative space. "
            "Warm, conspiratorial, alive."
        ),
    },
    "roles": {
        "filename": "11-roles.jpg",
        "prompt": (
            "Two parallel paths drawn in clean line work, side by side, each leading toward the same horizon. Between them, "
            "a few thin connecting lines bridge the two paths at intervals. A single tree grows where the paths meet at the top. "
            "Suggests parallel work, meeting at the top — distinct lanes, one shared destination."
        ),
    },
    "commitment": {
        "filename": "12-commitment.jpg",
        "prompt": (
            "A horizontal line representing a calendar timeline, with four equal segments labeled by season — early summer, "
            "mid summer, late summer, early autumn — but rendered abstractly with no text. Above each segment, a stylized "
            "plant grows progressively: bare stem, first leaves, full leaves, a single flower or fruit. At the end of the "
            "fourth segment, a small circle marks a reassessment checkpoint. Clean, calm, finite — a defined window of growth."
        ),
    },
    "close": {
        "filename": "13-close.jpg",
        "prompt": (
            f"{SONIA} She is shown from behind, walking away from the viewer down a path lined with stylized vines and small leaves. "
            "Her ponytail is visible. Ahead of her, a doorway or arch opens onto a softly glowing horizon. "
            "Calm, decisive, forward-moving — the moment of saying yes."
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
