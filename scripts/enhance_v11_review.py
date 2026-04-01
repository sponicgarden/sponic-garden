#!/usr/bin/env python3
"""
Gemini AI Photorealistic Enhancement — Review-Quality Multi-Variant Pipeline

Generates multiple variants per camera angle using gemini-3-pro-image-preview
for high-quality output suitable for human review and feedback.

Two-machine support: split work with --machine=A (daylight+golden) or --machine=B (bluehour+newcams).
Variant control: --variants=N generates N variants per camera angle.

Usage:
    # Machine A (local): daylight + golden hour
    python3 scripts/enhance_v11_review.py --machine=A --variants=3

    # Machine B (Alpuca): blue hour + new cameras + re-run priority angles
    python3 scripts/enhance_v11_review.py --machine=B --variants=3

    # Single machine, all sets
    python3 scripts/enhance_v11_review.py --all --variants=3

    # Single set
    python3 scripts/enhance_v11_review.py --daylight --variants=5

Requires:
    pip install google-genai
    API key in /tmp/.gemini_key_sg
"""
import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("ERROR: pip install google-genai")
    sys.exit(1)

# ═══════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════
PROJECT_ROOT = Path(__file__).parent.parent

MODEL = "gemini-3-pro-image-preview"
TEMPERATURE_RANGE = [0.3, 0.5, 0.7, 0.9, 1.0]  # cycle through for variety

# Output goes to v11-review/ with per-variant subdirs
REVIEW_BASE = PROJECT_ROOT / "design" / "renders" / "v11-review"

RENDER_SETS = {
    "daylight": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11",
        "pattern": "v11_CAM_*.png",
        "cam_extract": lambda stem: stem.replace("v11_", ""),
    },
    "golden": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11-golden",
        "pattern": "v11_golden_CAM_*.png",
        "cam_extract": lambda stem: stem.replace("v11_golden_", ""),
    },
    "bluehour": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11-bluehour",
        "pattern": "v11_blue_CAM_*.png",
        "cam_extract": lambda stem: stem.replace("v11_blue_", ""),
    },
    "newcams": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11-newcams",
        "pattern": "v11_CAM_*.png",
        "cam_extract": lambda stem: stem.replace("v11_", ""),
    },
}

PASSES_DIR = PROJECT_ROOT / "design" / "renders" / "v11-passes"

MACHINE_SPLITS = {
    "A": ["daylight", "golden"],
    "B": ["bluehour", "newcams"],
}

# Load API key
KEY_FILE = Path("/tmp/.gemini_key_sg")
if not KEY_FILE.exists():
    print("ERROR: API key file /tmp/.gemini_key_sg not found")
    print("  Set it with: bw get password 'Google Gemini — SponicGardens (USE THIS)' > /tmp/.gemini_key_sg")
    sys.exit(1)

API_KEY = KEY_FILE.read_text().strip()

# ═══════════════════════════════════════════
# CAMERA-SPECIFIC PROMPTS (enhanced for review quality)
# ═══════════════════════════════════════════

CAMERA_PROMPTS = {
    "CAM_aerial": (
        "Transform this overhead architectural 3D diagram into a photorealistic aerial "
        "photograph taken by a drone at 60m altitude on a sunny day. This is Sponic Garden, "
        "a 2-acre industrial-garden campus in Warsaw, Poland with 7 purpose-built buildings, "
        "a rectangular swimming pool, spa area with square cedar saunas, greenhouse, fire pit "
        "with seating ring, stone walkways, and dense ornamental gardens. "
        "Materials: corrugated Corten steel roofing, red brick walls, cedar wood cladding, "
        "steel trusses, glass greenhouse panels. Dense climbing ivy and wisteria on walls. "
        "Keep the EXACT same layout, building footprints, sizes, and relative positions. "
        "Add realistic grass textures with mowing patterns, tree canopies with individual "
        "leaves, turquoise pool water with caustics, shadow patterns matching sun position, "
        "and realistic rooftop materials. The saunas are SQUARE cabins with flat roofs and "
        "glass windows — NOT barrel or cylindrical saunas."
    ),
    "CAM_hero": (
        "Transform this 3D architectural perspective into a photorealistic photograph of "
        "Sponic Garden — a 2-acre industrial-garden campus. Shot from an elevated 15m vantage "
        "point showing the full campus. Industrial-garden aesthetic: exposed painted steel "
        "trusses visible on open-sided buildings, standing-seam corrugated metal walls, "
        "aged red brick facades with lime mortar, natural cedar wood pergolas and fencing, "
        "dense climbing wisteria and Boston ivy covering 30% of wall surfaces, lush raised "
        "garden beds with mixed plantings, festoon string lights strung between buildings. "
        "Keep the EXACT same layout, building positions, camera angle, and proportions. "
        "Add rich weathered material textures, realistic vegetation with botanical variety "
        "(hostas, ferns, ornamental grasses, herbs), atmospheric haze, and natural afternoon "
        "sunlight with soft shadows. Blue sky with scattered cumulus clouds."
    ),
    "CAM_pool_spa": (
        "Transform this 3D render into a photorealistic photograph of a luxury pool and spa "
        "area at Sponic Garden. Features: a 15m × 6m rectangular swimming pool with turquoise "
        "water showing caustic light patterns on the bottom, teak sun loungers with cream "
        "canvas umbrellas, and the adjacent spa zone with TWO SQUARE cedar sauna cabins "
        "(each ~3m × 3m, flat metal roof, large glass window on the front face, cedar plank "
        "walls, chimney flue), two round cedar hot tubs with visible steam, and a concrete "
        "cold plunge pool. Ipe wood deck connects all elements. Privacy hedges of hornbeam "
        "surround the area. Industrial buildings visible behind with corrugated metal walls. "
        "String lights overhead. Keep the EXACT same layout and camera angle. Add realistic "
        "water caustics, wet deck reflections, steam wisps from hot tubs, lush plantings, "
        "and warm afternoon sunlight."
    ),
    "CAM_entrance": (
        "Transform this ground-level 3D render into a photorealistic eye-level photograph "
        "of the entrance approach to Sponic Garden. The viewer is arriving on foot, looking "
        "straight ahead down a 3m-wide stone sett walkway toward the Welcome Center — a "
        "single-storey brick building with a wide entrance porch. Clipped boxwood hedges "
        "1.2m tall line both sides of the path. Terracotta pots with lavender and rosemary "
        "flank doorways. Festoon string lights loop between cedar posts along the walkway. "
        "Weathered steel signage reads 'SPONIC GARDEN'. Buildings visible further in: "
        "corrugated metal, exposed trusses, climbing plants. Keep the EXACT same perspective, "
        "building positions, and walkway layout. Add realistic stone paving texture with moss "
        "in joints, verdant plantings, warm golden light filtering through trees, and gentle "
        "depth of field blurring the background."
    ),
    "CAM_greenhouse_detail": (
        "Transform this close-up 3D render into a photorealistic photograph of the main "
        "greenhouse at Sponic Garden. A 15m × 20m structure with a black-painted steel frame, "
        "A-frame trusses, and floor-to-ceiling glass panels. Through the glass: wooden potting "
        "tables with terracotta pots, grow lights, and tropical plants (banana, monstera, "
        "tomato vines). Exterior: climbing jasmine and clematis on the steel frame. "
        "'SPONIC GARDEN' in painted lettering on the south gable wall. Keep the EXACT same "
        "framing, structure, and proportions. Add realistic steel patina and rivet details, "
        "glass reflections showing sky and trees, condensation droplets, warm interior glow, "
        "and sharp foreground focus with soft background bokeh. Shot with 85mm telephoto."
    ),
    "CAM_firepit_evening": (
        "Transform this 3D render into a photorealistic photograph of the fire pit gathering "
        "area at Sponic Garden, shot during early evening. A 2m diameter circular corten steel "
        "fire bowl with visible flames sits at the center of a stone circle. Built-in cedar "
        "bench seating forms a ring around it. String lights loop overhead between surrounding "
        "buildings. Industrial buildings with corrugated metal walls frame the scene. Potted "
        "grasses and low hedges define the space. Keep the EXACT same layout and camera angle. "
        "Add realistic fire with orange flames and sparks, warm firelight on faces of "
        "surrounding surfaces, twinkling string light bokeh, deep blue twilight sky above, "
        "and the cozy intimate atmosphere of an outdoor gathering space."
    ),
    "CAM_coffee_bar": (
        "Transform this 3D render into a photorealistic photograph of an outdoor coffee bar "
        "at Sponic Garden. A semi-open pavilion with cedar timber posts supporting a "
        "corrugated metal roof canopy. Long timber counter bar (reclaimed oak) with 6 metal "
        "bar stools. Espresso machine, cups, and menu board visible. String lights under "
        "the roof canopy. Surrounding: brick and metal industrial buildings, potted herbs "
        "on the counter, climbing hops on posts. Keep the EXACT same framing and structure. "
        "Add realistic weathered cedar grain, worn brass fixtures, artisanal atmosphere, "
        "steam rising from cups, dappled afternoon light, shallow depth of field."
    ),
    "CAM_spa_detail": (
        "Transform this 3D render into a photorealistic photograph of the spa zone at "
        "Sponic Garden. TWO SQUARE cedar sauna buildings (3m × 3m each, flat standing-seam "
        "metal roof, large glass window on front, vertical cedar plank walls, stainless "
        "steel chimney flue). Between them: round cedar hot tubs with visible steam and "
        "a rectangular concrete cold plunge pool with steps. Ipe wood deck surface. Clipped "
        "hornbeam hedges for privacy. Industrial Spa House building behind. Keep the EXACT "
        "same layout, sauna shapes (SQUARE with flat roof and windows — NOT barrel saunas), "
        "hot tub positions, and camera angle. Add realistic cedar wood grain with silver "
        "weathering, steam wisps, warm interior glow through sauna windows, wet deck surfaces "
        "with reflections, and lush surrounding plantings."
    ),
    "CAM_greenhouse_interior": (
        "Transform this 3D render into a photorealistic photograph taken INSIDE the greenhouse, "
        "looking south through glass walls toward the garden campus. Black steel columns and "
        "A-frame trusses overhead create dramatic lines. Wooden potting tables with terracotta "
        "pots, seedling trays, and gardening tools in the foreground. Grow lights and hanging "
        "planters. Warm humid atmosphere with visible condensation on glass. Tropical plants: "
        "banana, monstera, ferns. Through the glass, the outdoor campus is visible. Keep the "
        "EXACT same perspective and structural layout. Add realistic greenhouse atmosphere — "
        "humid air, condensation, filtered warm light, plant textures, tool details."
    ),
    "CAM_garden_ground": (
        "Transform this ground-level 3D render into a photorealistic photograph taken at "
        "knee height (80cm) among raised garden beds. Cedar-sided raised beds 60cm tall in "
        "foreground filled with lush vegetables: kale, tomatoes on stakes, herbs, lettuce. "
        "Rich dark soil visible. The glass greenhouse building rises in the background. "
        "Stone path between beds. Morning light with dew on leaves. Very shallow depth of "
        "field — sharp focus on foreground plants, soft background. Keep the EXACT same "
        "perspective and building positions. Shot with 24mm at f/2.0."
    ),
    "CAM_walkway": (
        "Transform this 3D render into a photorealistic photograph of a covered walkway "
        "corridor at Sponic Garden. Cedar timber posts and beams frame the view. Slatted "
        "cedar roof overhead creating striped shadow patterns on the stone path below. "
        "Buildings on both sides: corrugated metal and brick walls with climbing plants. "
        "String lights overhead. Potted ferns and hostas along the path edges. Through the "
        "walkway, more of the campus is visible ahead. Keep the EXACT same perspective and "
        "structural elements. Add realistic wood grain, dappled light through roof slats, "
        "atmospheric depth, and lush vegetation."
    ),
    "CAM_sauna_eyelevel": (
        "Transform this 3D render into a photorealistic eye-level photograph of TWO SQUARE "
        "cedar sauna cabins at Sponic Garden. Standing at 1.7m height, looking at the saunas "
        "from 5m away. Each sauna: 3m × 3m, vertical cedar plank walls showing silver "
        "weathering, flat standing-seam metal roof, large glass window on front face glowing "
        "warm from the interior heat, stainless steel chimney flue. Cedar hot tubs nearby "
        "with visible steam. Ipe wood deck. Clipped hedges. Keep the EXACT same layout — "
        "saunas are SQUARE buildings with flat roofs, NOT barrel/cylindrical. Add realistic "
        "cedar texture, warm window glow, steam, wet surfaces, evening atmosphere."
    ),
}

LIGHTING_MODIFIERS = {
    "daylight": "",
    "golden": (
        " LIGHTING: Golden hour — sun at 12° elevation, warm amber light (3200K color temp), "
        "long dramatic shadows stretching across the ground, warm orange tones on all surfaces, "
        "slightly hazy atmosphere with golden particles in the air. Sky gradient from deep "
        "orange at horizon through peach to pale blue at zenith."
    ),
    "bluehour": (
        " LIGHTING: Blue hour twilight — sun 3° below horizon, deep cobalt blue sky with "
        "remnants of magenta and amber at the western horizon. All artificial lights are ON: "
        "warm festoon string lights (2700K) are the primary visible light source, lanterns "
        "glow along paths, fire pit flames cast orange light, warm interior light spills "
        "through building windows and sauna glass. Overall mood: intimate, magical, inviting."
    ),
}

BASE_STYLE_SUFFIX = (
    " STYLE: High-end architectural photography for a luxury lifestyle magazine. "
    "Shot on Canon EOS R5 with L-series glass, natural light, processed with careful "
    "color grading. The image should be indistinguishable from a real photograph. "
    "CRITICAL CONSTRAINT: Absolutely preserve the structural layout from the input — "
    "do NOT rearrange, add, or remove any buildings, features, or major elements. "
    "The output must show the SAME scene from the SAME angle, just made photorealistic."
)

# Prompt variations for diversity across variants
VARIANT_SUFFIXES = [
    "",  # base prompt
    " Emphasize lush vegetation — every surface that could have a plant should have one. Climbing vines, hanging baskets, window boxes, green roofs where appropriate. Maximum botanical density.",
    " Emphasize atmosphere and mood — visible atmospheric haze, volumetric light rays through trees, bokeh highlights from string lights, cinematic depth of field. Moody and evocative.",
    " Emphasize architectural materials and details — focus on textures: brick mortar lines, corrugated metal ridges, cedar wood grain, steel patina, stone paving joints. Sharp detail throughout.",
    " Emphasize human scale and warmth — include subtle signs of use: worn paths, a forgotten coffee cup, garden tools leaning against a wall, a book on a lounger. The space feels lived-in and loved.",
]


def find_pass_files(camera_name: str) -> dict:
    """Find depth/normal/mist pass files for a camera."""
    passes = {}
    if not PASSES_DIR.exists():
        return passes
    for pass_type in ['depth', 'normal', 'mist']:
        candidates = list(PASSES_DIR.glob(f"v11_{camera_name}_{pass_type}_*"))
        if candidates:
            passes[pass_type] = candidates[0]
    return passes


def enhance_render(client, input_path: Path, output_path: Path,
                   camera_name: str, lighting: str, variant_idx: int) -> dict:
    """Enhance a single render, producing one variant."""
    image_bytes = input_path.read_bytes()

    prompt = CAMERA_PROMPTS.get(camera_name, CAMERA_PROMPTS["CAM_hero"])
    lighting_mod = LIGHTING_MODIFIERS.get(lighting, "")
    variant_suffix = VARIANT_SUFFIXES[variant_idx % len(VARIANT_SUFFIXES)]
    full_prompt = prompt + lighting_mod + BASE_STYLE_SUFFIX + variant_suffix

    # Cycle temperature for variety
    temp = TEMPERATURE_RANGE[variant_idx % len(TEMPERATURE_RANGE)]

    parts = [types.Part.from_bytes(data=image_bytes, mime_type="image/png")]

    # Add geometry passes if available
    pass_files = find_pass_files(camera_name)
    pass_instructions = ""

    if pass_files.get('depth'):
        depth_bytes = pass_files['depth'].read_bytes()
        parts.append(types.Part.from_bytes(data=depth_bytes, mime_type="image/png"))
        pass_instructions += (
            " The second image is a DEPTH MAP (white=near, black=far). "
            "Use it to apply realistic atmospheric haze at distance and depth of field blur."
        )

    if pass_files.get('normal'):
        normal_bytes = pass_files['normal'].read_bytes()
        parts.append(types.Part.from_bytes(data=normal_bytes, mime_type="image/png"))
        pass_instructions += (
            f" Image {len(parts)} is a SURFACE NORMAL MAP (RGB encodes XYZ normals). "
            "Use it for accurate surface material rendering and specular highlights."
        )

    parts.append(full_prompt + pass_instructions)

    print(f"    Sending to {MODEL} (temp={temp}, variant={variant_idx})...")
    print(f"    Images: 1 beauty" + (f" + {len(pass_files)} passes" if pass_files else ""))

    response = client.models.generate_content(
        model=MODEL,
        contents=parts,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            temperature=temp,
        ),
    )

    result_info = {
        "camera": camera_name,
        "lighting": lighting,
        "variant": variant_idx,
        "temperature": temp,
        "variant_style": VARIANT_SUFFIXES[variant_idx % len(VARIANT_SUFFIXES)][:60] or "base",
        "model": MODEL,
        "prompt_length": len(full_prompt),
        "input_file": str(input_path),
        "output_file": str(output_path),
        "passes_used": list(pass_files.keys()),
        "text_response": "",
        "success": False,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            output_path.write_bytes(part.inline_data.data)
            result_info["success"] = True
            result_info["file_size_bytes"] = len(part.inline_data.data)
            result_info["mime_type"] = part.inline_data.mime_type
            print(f"    ✓ Saved: {output_path.name} ({len(part.inline_data.data) / 1024:.0f} KB)")
        elif part.text:
            result_info["text_response"] = part.text[:500]
            print(f"    Text: {part.text[:200]}")

    return result_info


def process_set(client, set_name: str, num_variants: int) -> list:
    """Process all cameras in a render set, generating N variants each."""
    config = RENDER_SETS[set_name]
    input_dir = config["input_dir"]
    lighting = set_name if set_name in LIGHTING_MODIFIERS else "daylight"

    renders = sorted(input_dir.glob(config["pattern"]))
    if not renders:
        print(f"\n  No renders found in {input_dir} matching {config['pattern']}")
        return []

    print(f"\n  Found {len(renders)} cameras × {num_variants} variants = {len(renders) * num_variants} renders")

    # Output directory: v11-review/{lighting}/{camera}/variant_N.png
    results = []
    total = len(renders) * num_variants
    count = 0

    for render_path in renders:
        camera_name = config["cam_extract"](render_path.stem)
        cam_dir = REVIEW_BASE / set_name / camera_name
        cam_dir.mkdir(parents=True, exist_ok=True)

        # Copy structural render for comparison
        structural_dest = cam_dir / "structural.png"
        if not structural_dest.exists():
            import shutil
            shutil.copy2(render_path, structural_dest)

        for v in range(num_variants):
            count += 1
            output_path = cam_dir / f"variant_{v}.png"

            if output_path.exists():
                print(f"\n  [{count}/{total}] {set_name}/{camera_name} v{v} — exists, skipping")
                continue

            print(f"\n  [{count}/{total}] {set_name}/{camera_name} variant {v}")

            try:
                result = enhance_render(client, render_path, output_path, camera_name, lighting, v)
                results.append(result)

                if not result["success"]:
                    print(f"    WARNING: No image generated")

            except Exception as e:
                print(f"    ERROR: {e}")
                results.append({
                    "camera": camera_name,
                    "lighting": lighting,
                    "variant": v,
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                })

            # Rate limiting — be generous with pro model
            if count < total:
                wait = 15  # longer wait for pro model rate limits
                print(f"    Waiting {wait}s (rate limit)...")
                time.sleep(wait)

    return results


def generate_review_html():
    """Generate a review comparison page from all variants."""
    html_path = REVIEW_BASE / "review.html"

    # Scan what exists
    sections = []
    for set_name in ["daylight", "golden", "bluehour", "newcams"]:
        set_dir = REVIEW_BASE / set_name
        if not set_dir.exists():
            continue
        cameras = sorted([d for d in set_dir.iterdir() if d.is_dir()])
        if not cameras:
            continue

        cam_data = []
        for cam_dir in cameras:
            structural = cam_dir / "structural.png"
            variants = sorted(cam_dir.glob("variant_*.png"))
            if variants:
                cam_data.append({
                    "name": cam_dir.name,
                    "structural": f"{set_name}/{cam_dir.name}/structural.png" if structural.exists() else None,
                    "variants": [f"{set_name}/{cam_dir.name}/{v.name}" for v in variants],
                })

        if cam_data:
            sections.append({"name": set_name, "cameras": cam_data})

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sponic Garden v11 — Review Variants</title>
<style>
:root { --bg: #0a0a0a; --card: #141414; --border: #2a2a2a; --text: #e0e0e0; --accent: #4a9; }
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.5; }
.header { padding: 2rem; text-align: center; border-bottom: 1px solid var(--border); }
.header h1 { font-size: 1.8rem; font-weight: 300; letter-spacing: 0.05em; }
.header p { color: #888; margin-top: 0.5rem; }
.section { padding: 2rem; border-bottom: 1px solid var(--border); }
.section h2 { font-size: 1.3rem; font-weight: 400; margin-bottom: 1.5rem; color: var(--accent); text-transform: capitalize; }
.camera-group { margin-bottom: 3rem; }
.camera-group h3 { font-size: 1rem; font-weight: 500; margin-bottom: 1rem; color: #aaa; text-transform: uppercase; letter-spacing: 0.08em; }
.variants-row { display: flex; gap: 1rem; overflow-x: auto; padding-bottom: 1rem; }
.variant-card { flex: 0 0 auto; width: 420px; background: var(--card); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; transition: border-color 0.2s; position: relative; }
.variant-card:hover { border-color: var(--accent); }
.variant-card.structural { border-color: #555; }
.variant-card img { width: 100%; height: auto; display: block; cursor: pointer; }
.variant-card .label { padding: 0.5rem 0.75rem; font-size: 0.8rem; color: #888; display: flex; justify-content: space-between; align-items: center; }
.variant-card .label .tag { background: #222; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; }
.vote-btn { background: none; border: 1px solid #444; color: #888; padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 0.75rem; }
.vote-btn:hover { border-color: var(--accent); color: var(--accent); }
.vote-btn.voted { background: var(--accent); color: #000; border-color: var(--accent); }
.feedback-area { margin-top: 0.5rem; }
.feedback-area textarea { width: 100%; background: #1a1a1a; border: 1px solid #333; color: #ccc; padding: 0.5rem; border-radius: 4px; font-size: 0.8rem; resize: vertical; min-height: 40px; }
.stats { padding: 1rem 2rem; background: #111; font-size: 0.85rem; color: #888; }
.fullscreen-overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.95); z-index: 1000; cursor: zoom-out; align-items: center; justify-content: center; }
.fullscreen-overlay.active { display: flex; }
.fullscreen-overlay img { max-width: 95vw; max-height: 95vh; object-fit: contain; }
.export-btn { position: fixed; bottom: 1.5rem; right: 1.5rem; background: var(--accent); color: #000; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; cursor: pointer; font-size: 0.9rem; font-weight: 600; z-index: 100; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }
.export-btn:hover { opacity: 0.9; }
</style>
</head>
<body>
<div class="header">
<h1>Sponic Garden v11 — Review Variants</h1>
<p>Click images to enlarge. Vote for your favorites. Add feedback notes per camera.</p>
<p style="margin-top:0.3rem;font-size:0.85rem;color:#666;">"""

    total_variants = sum(len(c["variants"]) for s in sections for c in s["cameras"])
    total_cameras = sum(len(s["cameras"]) for s in sections)
    html += f"{total_cameras} cameras &times; {total_variants} total variants | Model: {MODEL}"

    html += """</p>
</div>
"""

    for section in sections:
        lighting_labels = {"daylight": "Daylight", "golden": "Golden Hour", "bluehour": "Blue Hour", "newcams": "New Camera Angles"}
        html += f'<div class="section">\n<h2>{lighting_labels.get(section["name"], section["name"])}</h2>\n'

        for cam in section["cameras"]:
            cam_label = cam["name"].replace("CAM_", "").replace("_", " ").title()
            html += f'<div class="camera-group">\n<h3>{cam_label}</h3>\n<div class="variants-row">\n'

            if cam["structural"]:
                html += f'''<div class="variant-card structural">
<img src="{cam["structural"]}" alt="Structural" onclick="showFullscreen(this)">
<div class="label"><span>Structural (Blender)</span><span class="tag">reference</span></div>
</div>\n'''

            for i, variant_path in enumerate(cam["variants"]):
                style_labels = ["Base", "Lush Vegetation", "Atmospheric", "Material Detail", "Lived-In"]
                style = style_labels[i % len(style_labels)]
                html += f'''<div class="variant-card" data-camera="{cam["name"]}" data-set="{section["name"]}" data-variant="{i}">
<img src="{variant_path}" alt="Variant {i}" onclick="showFullscreen(this)">
<div class="label">
<span>Variant {i} — {style}</span>
<button class="vote-btn" onclick="toggleVote(this)">★ Pick</button>
</div>
<div class="feedback-area" style="padding:0 0.5rem 0.5rem;">
<textarea placeholder="Notes on this variant..." oninput="saveFeedback(this)"></textarea>
</div>
</div>\n'''

            html += '</div>\n</div>\n'
        html += '</div>\n'

    html += """
<div class="fullscreen-overlay" id="fullscreen" onclick="this.classList.remove('active')">
<img id="fullscreen-img" src="" alt="">
</div>

<button class="export-btn" onclick="exportFeedback()">Export Feedback</button>

<script>
const votes = {};
const feedback = {};

function showFullscreen(img) {
    const overlay = document.getElementById('fullscreen');
    document.getElementById('fullscreen-img').src = img.src;
    overlay.classList.add('active');
}

function toggleVote(btn) {
    const card = btn.closest('.variant-card');
    const key = card.dataset.set + '/' + card.dataset.camera + '/v' + card.dataset.variant;
    btn.classList.toggle('voted');
    votes[key] = btn.classList.contains('voted');
}

function saveFeedback(textarea) {
    const card = textarea.closest('.variant-card');
    const key = card.dataset.set + '/' + card.dataset.camera + '/v' + card.dataset.variant;
    feedback[key] = textarea.value;
}

function exportFeedback() {
    const picked = Object.entries(votes).filter(([k,v]) => v).map(([k]) => k);
    const notes = Object.entries(feedback).filter(([k,v]) => v.trim());
    const report = {
        timestamp: new Date().toISOString(),
        picks: picked,
        feedback: Object.fromEntries(notes),
    };
    const blob = new Blob([JSON.stringify(report, null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'sponic-review-feedback-' + new Date().toISOString().slice(0,10) + '.json';
    a.click();
}

// Keyboard navigation
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') document.getElementById('fullscreen').classList.remove('active');
});
</script>
</body>
</html>"""

    html_path.write_text(html)
    print(f"\n  Review page: {html_path}")
    return html_path


def main():
    parser = argparse.ArgumentParser(description="Review-quality multi-variant enhancement")
    parser.add_argument("--machine", choices=["A", "B"], help="Machine split: A=daylight+golden, B=bluehour+newcams")
    parser.add_argument("--all", action="store_true", help="All render sets")
    parser.add_argument("--daylight", action="store_true")
    parser.add_argument("--golden", action="store_true")
    parser.add_argument("--bluehour", action="store_true")
    parser.add_argument("--newcams", action="store_true")
    parser.add_argument("--variants", type=int, default=3, help="Variants per camera (default: 3)")
    parser.add_argument("--review-only", action="store_true", help="Only generate review HTML")
    args = parser.parse_args()

    if args.review_only:
        generate_review_html()
        return 0

    # Determine sets
    if args.machine:
        sets_to_process = MACHINE_SPLITS[args.machine]
    elif args.all:
        sets_to_process = ["daylight", "golden", "bluehour", "newcams"]
    else:
        sets_to_process = []
        if args.daylight: sets_to_process.append("daylight")
        if args.golden: sets_to_process.append("golden")
        if args.bluehour: sets_to_process.append("bluehour")
        if args.newcams: sets_to_process.append("newcams")
        if not sets_to_process:
            sets_to_process = ["daylight"]

    total_cameras = sum(
        len(list(RENDER_SETS[s]["input_dir"].glob(RENDER_SETS[s]["pattern"])))
        for s in sets_to_process
        if RENDER_SETS[s]["input_dir"].exists()
    )
    total_renders = total_cameras * args.variants
    est_minutes = total_renders * 20 / 60  # ~20s per render with rate limit

    print("=" * 60)
    print("  SPONIC GARDEN v11 — REVIEW ENHANCEMENT")
    print("=" * 60)
    print(f"  Model: {MODEL}")
    print(f"  Sets: {', '.join(sets_to_process)}")
    print(f"  Variants per camera: {args.variants}")
    print(f"  Total renders: ~{total_renders}")
    print(f"  Estimated time: ~{est_minutes:.0f} min")
    print(f"  Output: {REVIEW_BASE}/")
    print(f"  Machine: {args.machine or 'single'}")
    print("=" * 60)

    client = genai.Client(api_key=API_KEY)

    all_results = []
    for set_name in sets_to_process:
        print(f"\n{'=' * 60}")
        print(f"  Processing: {set_name}")
        print(f"{'=' * 60}")
        results = process_set(client, set_name, args.variants)
        all_results.extend(results)

        # Save metadata after each set (in case of crash)
        meta_path = REVIEW_BASE / "enhancement_metadata.json"
        REVIEW_BASE.mkdir(parents=True, exist_ok=True)
        existing = {}
        if meta_path.exists():
            try:
                existing = json.loads(meta_path.read_text())
            except:
                pass
        existing_results = existing.get("results", [])
        existing_results.extend(results)
        metadata = {
            "version": "v11-review",
            "model": MODEL,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "sets_processed": sets_to_process,
            "variants_per_camera": args.variants,
            "results": existing_results,
        }
        meta_path.write_text(json.dumps(metadata, indent=2))

    # Generate review page
    generate_review_html()

    success = sum(1 for r in all_results if r.get("success"))
    total = len(all_results)

    print(f"\n{'=' * 60}")
    print(f"  ENHANCEMENT COMPLETE")
    print(f"  Success: {success}/{total}")
    print(f"  Review page: {REVIEW_BASE / 'review.html'}")
    print(f"{'=' * 60}")

    return 0 if success == total else 1


if __name__ == "__main__":
    sys.exit(main())
