#!/usr/bin/env python3
"""
Iterative Quality Enhancement — 6-hour autonomous run on Alpuca

Analyzes existing renders and strategically re-generates where quality gains
are highest. Runs continuously for a time budget, prioritizing:

1. UPSCALE PASS: Re-run smallest files (low detail) with refined prompts
2. DEPTH PASS: Add more variants to cameras with fewest options
3. ACTIVITY BOOST: More activity scenes for cameras that only have 1
4. GOLDEN+BLUE HERO: Extra hero/pool/entrance variants in dramatic lighting
5. DETAIL REFINEMENT: High-temp creative variants on best structural renders

Usage:
    python3 scripts/enhance_v11_iterative.py --hours=6
    python3 scripts/enhance_v11_iterative.py --hours=4 --dry-run

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
from datetime import datetime, timezone, timedelta

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("ERROR: pip install google-genai")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).parent.parent
MODEL = "gemini-3-pro-image-preview"
REVIEW_BASE = PROJECT_ROOT / "design" / "renders" / "v11-review"
ACTIVITY_BASE = REVIEW_BASE / "activity"
COMMUNITY_REF = REVIEW_BASE / "community_reference.png"

KEY_FILE = Path("/tmp/.gemini_key_sg")
if not KEY_FILE.exists():
    print("ERROR: API key not found at /tmp/.gemini_key_sg")
    sys.exit(1)

API_KEY = KEY_FILE.read_text().strip()

# Rate limit between API calls (seconds)
RATE_LIMIT = 15

# ═══════════════════════════════════════════
# RENDER SET CONFIGS
# ═══════════════════════════════════════════
RENDER_SETS = {
    "daylight": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11",
        "output_base": REVIEW_BASE / "daylight",
        "pattern": "v11_CAM_*.png",
        "cam_extract": lambda stem: stem.replace("v11_", ""),
    },
    "golden": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11-golden",
        "output_base": REVIEW_BASE / "golden",
        "pattern": "v11_golden_CAM_*.png",
        "cam_extract": lambda stem: stem.replace("v11_golden_", ""),
    },
    "bluehour": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11-bluehour",
        "output_base": REVIEW_BASE / "bluehour",
        "pattern": "v11_blue_CAM_*.png",
        "cam_extract": lambda stem: stem.replace("v11_blue_", ""),
    },
    "newcams": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11-newcams",
        "output_base": REVIEW_BASE / "newcams",
        "pattern": "v11_CAM_*.png",
        "cam_extract": lambda stem: stem.replace("v11_", ""),
    },
}

PASSES_DIR = PROJECT_ROOT / "design" / "renders" / "v11-passes"

# ═══════════════════════════════════════════
# PROMPTS (imported from enhance_v11_review.py concepts)
# ═══════════════════════════════════════════

CAMERA_PROMPTS = {
    "CAM_aerial": "Transform this overhead architectural 3D diagram into a photorealistic aerial photograph taken by a drone at 60m altitude on a sunny day. This is Sponic Garden, a 2-acre industrial-garden campus with 7 purpose-built buildings, a rectangular swimming pool, spa area with square cedar saunas, greenhouse, fire pit with seating ring, stone walkways, and dense ornamental gardens. Materials: corrugated Corten steel roofing, red brick walls, cedar wood cladding, steel trusses, glass greenhouse panels. Dense climbing ivy and wisteria on walls. Keep the EXACT same layout, building footprints, sizes, and relative positions. Add realistic grass textures with mowing patterns, tree canopies with individual leaves, turquoise pool water with caustics, shadow patterns matching sun position, and realistic rooftop materials. The saunas are SQUARE cabins with flat roofs and glass windows — NOT barrel or cylindrical saunas.",
    "CAM_hero": "Transform this 3D architectural perspective into a photorealistic photograph of Sponic Garden — a 2-acre industrial-garden campus. Shot from an elevated 15m vantage point showing the full campus. Industrial-garden aesthetic: exposed painted steel trusses visible on open-sided buildings, standing-seam corrugated metal walls, aged red brick facades with lime mortar, natural cedar wood pergolas and fencing, dense climbing wisteria and Boston ivy covering 30% of wall surfaces, lush raised garden beds with mixed plantings, festoon string lights strung between buildings. Keep the EXACT same layout, building positions, camera angle, and proportions. Add rich weathered material textures, realistic vegetation with botanical variety (hostas, ferns, ornamental grasses, herbs), atmospheric haze, and natural afternoon sunlight with soft shadows. Blue sky with scattered cumulus clouds.",
    "CAM_pool_spa": "Transform this 3D render into a photorealistic photograph of a luxury pool and spa area at Sponic Garden. Features: a 15m x 6m rectangular swimming pool with turquoise water showing caustic light patterns on the bottom, teak sun loungers with cream canvas umbrellas, and the adjacent spa zone with TWO SQUARE cedar sauna cabins (each ~3m x 3m, flat metal roof, large glass window on the front face, cedar plank walls, chimney flue), two round cedar hot tubs with visible steam, and a concrete cold plunge pool. Ipe wood deck connects all elements. Privacy hedges of hornbeam surround the area. Industrial buildings visible behind with corrugated metal walls. String lights overhead. Keep the EXACT same layout and camera angle. Add realistic water caustics, wet deck reflections, steam wisps from hot tubs, lush plantings, and warm afternoon sunlight.",
    "CAM_entrance": "Transform this ground-level 3D render into a photorealistic eye-level photograph of the entrance approach to Sponic Garden. The viewer is arriving on foot, looking straight ahead down a 3m-wide stone sett walkway toward the Welcome Center — a single-storey brick building with a wide entrance porch. Clipped boxwood hedges 1.2m tall line both sides of the path. Terracotta pots with lavender and rosemary flank doorways. Festoon string lights loop between cedar posts along the walkway. Weathered steel signage reads 'SPONIC GARDEN'. Buildings visible further in: corrugated metal, exposed trusses, climbing plants. Keep the EXACT same perspective, building positions, and walkway layout. Add realistic stone paving texture with moss in joints, verdant plantings, warm golden light filtering through trees, and gentle depth of field blurring the background.",
    "CAM_greenhouse_detail": "Transform this close-up 3D render into a photorealistic photograph of the main greenhouse at Sponic Garden. A 15m x 20m structure with a black-painted steel frame, A-frame trusses, and floor-to-ceiling glass panels. Through the glass: wooden potting tables with terracotta pots, grow lights, and tropical plants (banana, monstera, tomato vines). Exterior: climbing jasmine and clematis on the steel frame. 'SPONIC GARDEN' in painted lettering on the south gable wall. Keep the EXACT same framing, structure, and proportions. Add realistic steel patina and rivet details, glass reflections showing sky and trees, condensation droplets, warm interior glow, and sharp foreground focus with soft background bokeh. Shot with 85mm telephoto.",
    "CAM_firepit_evening": "Transform this 3D render into a photorealistic photograph of the fire pit gathering area at Sponic Garden, shot during early evening. A 2m diameter circular corten steel fire bowl with visible flames sits at the center of a stone circle. Built-in cedar bench seating forms a ring around it. String lights loop overhead between surrounding buildings. Industrial buildings with corrugated metal walls frame the scene. Potted grasses and low hedges define the space. Keep the EXACT same layout and camera angle. Add realistic fire with orange flames and sparks, warm firelight on faces of surrounding surfaces, twinkling string light bokeh, deep blue twilight sky above, and the cozy intimate atmosphere of an outdoor gathering space.",
    "CAM_coffee_bar": "Transform this 3D render into a photorealistic photograph of an outdoor coffee bar at Sponic Garden. A semi-open pavilion with cedar timber posts supporting a corrugated metal roof canopy. Long timber counter bar (reclaimed oak) with 6 metal bar stools. Espresso machine, cups, and menu board visible. String lights under the roof canopy. Surrounding: brick and metal industrial buildings, potted herbs on the counter, climbing hops on posts. Keep the EXACT same framing and structure. Add realistic weathered cedar grain, worn brass fixtures, artisanal atmosphere, steam rising from cups, dappled afternoon light, shallow depth of field.",
    "CAM_spa_detail": "Transform this 3D render into a photorealistic photograph of the spa zone at Sponic Garden. TWO SQUARE cedar sauna buildings (3m x 3m each, flat standing-seam metal roof, large glass window on front, vertical cedar plank walls, stainless steel chimney flue). Between them: round cedar hot tubs with visible steam and a rectangular concrete cold plunge pool with steps. Ipe wood deck surface. Clipped hornbeam hedges for privacy. Industrial Spa House building behind. Keep the EXACT same layout, sauna shapes (SQUARE with flat roof and windows — NOT barrel saunas), hot tub positions, and camera angle. Add realistic cedar wood grain with silver weathering, steam wisps, warm interior glow through sauna windows, wet deck surfaces with reflections, and lush surrounding plantings.",
    "CAM_greenhouse_interior": "Transform this 3D render into a photorealistic photograph taken INSIDE the greenhouse, looking south through glass walls toward the garden campus. Black steel columns and A-frame trusses overhead create dramatic lines. Wooden potting tables with terracotta pots, seedling trays, and gardening tools in the foreground. Grow lights and hanging planters. Warm humid atmosphere with visible condensation on glass. Tropical plants: banana, monstera, ferns. Through the glass, the outdoor campus is visible. Keep the EXACT same perspective and structural layout. Add realistic greenhouse atmosphere — humid air, condensation, filtered warm light, plant textures, tool details.",
    "CAM_garden_ground": "Transform this ground-level 3D render into a photorealistic photograph taken at knee height (80cm) among raised garden beds. Cedar-sided raised beds 60cm tall in foreground filled with lush vegetables: kale, tomatoes on stakes, herbs, lettuce. Rich dark soil visible. The glass greenhouse building rises in the background. Stone path between beds. Morning light with dew on leaves. Very shallow depth of field — sharp focus on foreground plants, soft background. Keep the EXACT same perspective and building positions. Shot with 24mm at f/2.0.",
    "CAM_walkway": "Transform this 3D render into a photorealistic photograph of a covered walkway corridor at Sponic Garden. Cedar timber posts and beams frame the view. Slatted cedar roof overhead creating striped shadow patterns on the stone path below. Buildings on both sides: corrugated metal and brick walls with climbing plants. String lights overhead. Potted ferns and hostas along the path edges. Through the walkway, more of the campus is visible ahead. Keep the EXACT same perspective and structural elements. Add realistic wood grain, dappled light through roof slats, atmospheric depth, and lush vegetation.",
    "CAM_sauna_eyelevel": "Transform this 3D render into a photorealistic eye-level photograph of TWO SQUARE cedar sauna cabins at Sponic Garden. Standing at 1.7m height, looking at the saunas from 5m away. Each sauna: 3m x 3m, vertical cedar plank walls showing silver weathering, flat standing-seam metal roof, large glass window on front face glowing warm from the interior heat, stainless steel chimney flue. Cedar hot tubs nearby with visible steam. Ipe wood deck. Clipped hedges. Keep the EXACT same layout — saunas are SQUARE buildings with flat roofs, NOT barrel/cylindrical. Add realistic cedar texture, warm window glow, steam, wet surfaces, evening atmosphere.",
}

LIGHTING_MODIFIERS = {
    "daylight": "",
    "golden": " LIGHTING: Golden hour — sun at 12deg elevation, warm amber light (3200K color temp), long dramatic shadows stretching across the ground, warm orange tones on all surfaces, slightly hazy atmosphere with golden particles in the air. Sky gradient from deep orange at horizon through peach to pale blue at zenith.",
    "bluehour": " LIGHTING: Blue hour twilight — sun 3deg below horizon, deep cobalt blue sky with remnants of magenta and amber at the western horizon. All artificial lights are ON: warm festoon string lights (2700K) are the primary visible light source, lanterns glow along paths, fire pit flames cast orange light, warm interior light spills through building windows and sauna glass. Overall mood: intimate, magical, inviting.",
}

STYLE_SUFFIX = " STYLE: High-end architectural photography for a luxury lifestyle magazine. Shot on Canon EOS R5 with L-series glass, natural light, processed with careful color grading. The image should be indistinguishable from a real photograph. CRITICAL CONSTRAINT: Absolutely preserve the structural layout from the input — do NOT rearrange, add, or remove any buildings, features, or major elements."

# Enhancement-specific prompt additions for iterative refinement
REFINEMENT_PROMPTS = {
    "ultra_detail": " EXTRA: Push material detail to the maximum — every brick has individual mortar lines, every cedar plank shows grain and knots, every steel beam shows weld marks and patina. Leaf veins visible on close plants. Fabric texture on umbrellas. Water droplets on surfaces. This should be gallery-print quality at 300dpi.",
    "atmosphere": " EXTRA: Add rich atmosphere — visible volumetric light rays through trees and roof slats, heat shimmer above the fire pit, pollen/dust motes in sunbeams, bokeh highlights from string lights even in daylight. Cinematic color grading with slightly lifted blacks and warm highlights.",
    "botanical_max": " EXTRA: Maximum botanical density and variety. Every surface that could support a plant should have one. Window boxes, hanging baskets, climbing vines (wisteria, clematis, jasmine), moss on stone joints, self-seeded wildflowers in gravel, ferns in shade. 50+ identifiable plant species visible.",
    "weather_mood": " EXTRA: Just after rain — wet surfaces everywhere reflecting sky and lights. Puddles on stone paths. Drops on leaves and petals. Steam rising from warm surfaces. Everything glistens. The air feels fresh and clean. Colors are more saturated from the wet surfaces.",
    "magic_hour": " EXTRA: The most magical 5 minutes of light — sun touching the horizon, entire scene bathed in deep amber. Every window catches fire-orange reflections. Silhouettes of plants against the glowing sky. String lights just becoming visible. The moment photographers wait all day for.",
}

# Activity scene prompts for cameras that need more
EXTRA_ACTIVITY_SCENES = {
    "CAM_coffee_bar": [
        {"name": "morning_rush_v2", "prompt": "Transform this 3D render into a photorealistic photograph of the coffee bar during a busy morning. A barista in a canvas apron pours a latte art heart. 4 people at the bar on stools, one reading a newspaper, one sketching in a notebook, two chatting. Fresh pastries under glass. Herbs growing in pots on the counter. A dog sits patiently at someone's feet. Morning sun streams through the cedar slats above."},
    ],
    "CAM_walkway": [
        {"name": "rainy_day", "prompt": "Transform this 3D render into a photorealistic photograph of the covered walkway during rain. 2 people walking under the cedar roof, protected from the rain visible falling beyond the covered area. Puddles on the stone path reflect string lights. Plants are glistening wet. One person carries a fresh bouquet from the garden. The covered walkway suddenly feels like the most magical infrastructure choice — it connects everything rain or shine."},
    ],
    "CAM_sauna_eyelevel": [
        {"name": "winter_steam", "prompt": "Transform this 3D render into a photorealistic photograph of the saunas on a cold winter evening. Thick steam billows from the hot tubs into freezing air. The SQUARE cedar saunas glow warm through their glass windows against a deep blue winter sky. Frost on the deck edges. A person in a robe and slippers walks between sauna and plunge pool. Snow dusts the hedges and rooftops. String lights and lanterns make it magical against the cold."},
    ],
    "CAM_greenhouse_interior": [
        {"name": "dinner_event", "prompt": "Transform this interior greenhouse 3D render into a photorealistic photograph of a dinner event. A long communal table runs down the center between the plant shelves, set with candles, linen napkins, and ceramic plates. 12 people seated, mid-dinner, conversation flowing. Hanging string lights and grow lights create ambient glow. Plants everywhere — diners are literally eating among the greenery. Through the glass walls, the campus twinkles with lights at dusk. Farm-to-table made literal."},
    ],
    "CAM_garden_ground": [
        {"name": "kids_planting", "prompt": "Transform this ground-level 3D render into a photorealistic photograph of a children's planting workshop. 4-5 kids aged 6-10 kneeling at the raised beds with small trowels, supervised by 2 adults. One child holds up a worm triumphantly. Seed packets scattered on the soil. Small hand-painted plant labels. A watering can sits nearby. The greenhouse is softly blurred in background. Morning light. The scene captures pure joy and learning."},
    ],
    "CAM_pool_spa": [
        {"name": "dawn_lap_swim", "prompt": "Transform this 3D render into a photorealistic photograph at dawn. A single person swims laps in the pool, creating a smooth wake. The sky is pink and orange on the horizon, reflected in the still pool water around the swimmer. Everything else is quiet — empty loungers with neatly folded towels, the SQUARE saunas dark and waiting, dew on the deck. One other person sits at the pool edge with feet in the water, holding a coffee, watching the sunrise. The most peaceful moment of the day."},
    ],
}

BASE_ACTIVITY_STYLE = " STYLE: High-end lifestyle/architectural photography for a luxury wellness magazine. Canon EOS R5, natural light. People should look natural, diverse (ages 20s-40s), and genuine — not stock-photo-posed. Candid moments, natural body language, earth-tone clothing (linen, cotton, sage, cream, terracotta). CRITICAL: Preserve the structural layout from the input image."


def find_pass_files(camera_name: str) -> dict:
    passes = {}
    if not PASSES_DIR.exists():
        return passes
    for pass_type in ['depth', 'normal', 'mist']:
        candidates = list(PASSES_DIR.glob(f"v11_{camera_name}_{pass_type}_*"))
        if candidates:
            passes[pass_type] = candidates[0]
    return passes


def generate_image(client, input_path: Path, output_path: Path, prompt: str,
                   temperature: float = 0.5, ref_image: Path = None) -> dict:
    """Generic image generation with optional reference image."""
    parts = [types.Part.from_bytes(data=input_path.read_bytes(), mime_type="image/png")]

    if ref_image and ref_image.exists():
        parts.append(types.Part.from_bytes(data=ref_image.read_bytes(), mime_type="image/png"))

    # Add geometry passes if available
    pass_files = find_pass_files(output_path.parent.name)
    for pt in ['depth', 'normal']:
        if pass_files.get(pt):
            parts.append(types.Part.from_bytes(data=pass_files[pt].read_bytes(), mime_type="image/png"))

    parts.append(prompt)

    response = client.models.generate_content(
        model=MODEL,
        contents=parts,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            temperature=temperature,
        ),
    )

    result = {
        "output_file": str(output_path),
        "success": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature": temperature,
    }

    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(part.inline_data.data)
            result["success"] = True
            result["file_size_bytes"] = len(part.inline_data.data)
            print(f"      Saved: {output_path.name} ({len(part.inline_data.data) / 1024:.0f} KB)")
        elif part.text:
            result["text_response"] = part.text[:300]

    return result


def build_task_queue():
    """Analyze existing renders and build prioritized enhancement queue."""
    tasks = []

    # ─── PHASE 0: TARGETED FIXES for known anomalies ───
    # These address specific issues found in visual review

    targeted_fixes = [
        # Golden hero: looks CG/miniature, flat sky, no atmosphere
        {
            "set": "golden", "camera": "CAM_hero",
            "suffix": "fix_atmosphere",
            "extra_prompt": " CRITICAL FIX: The previous version looked like a miniature model. This must look like a REAL place photographed by a drone. Add atmospheric depth — haze between buildings, volumetric golden light rays, realistic scale cues (birds in sky, distant trees at horizon). The sky must have a rich gradient from deep orange at the horizon through warm peach to pale blue overhead with wispy clouds. Buildings must look FULL SIZE, not like a tabletop model.",
            "temp": 0.4,
        },
        # Aerial: layout drifts from structural
        {
            "set": "daylight", "camera": "CAM_aerial",
            "suffix": "fix_layout",
            "extra_prompt": " CRITICAL FIX: You MUST preserve the EXACT building positions, count (7 buildings), and the star/radial walkway pattern from the input image. Count the buildings in your output — there must be exactly 7 distinct structures plus the greenhouse. The radial stone paths emanating from the central circle must be preserved. Do NOT simplify or rearrange the layout. Every building footprint must match the input diagram precisely.",
            "temp": 0.3,
        },
        # Firepit daylight: walls too smooth, lost corrugated texture
        {
            "set": "daylight", "camera": "CAM_firepit_evening",
            "suffix": "fix_walls",
            "extra_prompt": " CRITICAL FIX: The surrounding buildings MUST have visible corrugated metal wall panels — you can see the vertical ridges and standing seams of the metal cladding. The walls should NOT be smooth or flat. Add weathered corrugated steel with rust streaks at fastener points, visible panel joints, and the characteristic ribbed texture of industrial metal cladding.",
            "temp": 0.4,
        },
        # Coffee bar: too rustic/shed-like, should be open pavilion
        {
            "set": "daylight", "camera": "CAM_coffee_bar",
            "suffix": "fix_openness",
            "extra_prompt": " CRITICAL FIX: The coffee bar is a SEMI-OPEN pavilion — it should feel airy and inviting, NOT like a closed wooden shed. The back wall behind the counter should be partially open or have a serving window. You should be able to see through or past the structure. Cedar posts support an open roof canopy with visible sky through the slats. The overall feeling should be an outdoor bar where you sit in fresh air, not inside a dark building.",
            "temp": 0.5,
        },
        # Golden entrance: flat lighting, needs dramatic golden shadows
        {
            "set": "golden", "camera": "CAM_entrance",
            "suffix": "fix_drama",
            "extra_prompt": " CRITICAL FIX: The golden hour lighting must be DRAMATIC — long shadows stretching across the stone path (sun is low, 12 degrees elevation, so shadows are 4-5x the height of objects). Warm amber light hitting the SIDES of buildings and hedges, with deep shadows on the opposite side. The stone path should have alternating bands of golden light and shadow. The sky at the horizon should glow deep orange. This is the 'magic hour' photographers wait all day for — make it feel special.",
            "temp": 0.4,
        },
        # Golden hero: another attempt with stronger atmosphere
        {
            "set": "golden", "camera": "CAM_hero",
            "suffix": "fix_scale",
            "extra_prompt": " CRITICAL FIX: This is a 2-ACRE campus (roughly 90m x 90m). The buildings are full-size single-storey structures 4-5m tall. Add scale references: a person walking on a path, chairs visible at the coffee bar, full-height trees (8-12m). The scene must NOT look like a scale model or architectural model — it must look like a real place you could walk through. Add atmospheric haze between the foreground and background buildings to create depth.",
            "temp": 0.4,
        },
    ]

    for fix in targeted_fixes:
        config = RENDER_SETS[fix["set"]]
        candidates = list(config["input_dir"].glob(f"*{fix['camera']}*"))
        if not candidates:
            continue

        base = CAMERA_PROMPTS.get(fix["camera"], CAMERA_PROMPTS["CAM_hero"])
        lighting = fix["set"] if fix["set"] in LIGHTING_MODIFIERS else "daylight"
        light_mod = LIGHTING_MODIFIERS.get(lighting, "")

        out_dir = config["output_base"] / fix["camera"]
        out_path = out_dir / f"variant_{fix['suffix']}.png"
        if out_path.exists():
            continue

        tasks.append({
            "phase": "0_targeted_fix",
            "priority": 0,  # highest priority
            "input": candidates[0],
            "output": out_path,
            "prompt": base + light_mod + STYLE_SUFFIX + fix["extra_prompt"],
            "temperature": fix["temp"],
            "description": f"FIX: {fix['set']}/{fix['camera']} ({fix['suffix']})",
        })

    # ─── PHASE 1: Re-run smallest variants with ultra-detail prompts ───
    all_variants = []
    for set_name, config in RENDER_SETS.items():
        out_base = config["output_base"]
        if not out_base.exists():
            continue
        for cam_dir in sorted(out_base.iterdir()):
            if not cam_dir.is_dir():
                continue
            for v in sorted(cam_dir.glob("variant_*.png")):
                all_variants.append({
                    "path": v,
                    "size": v.stat().st_size,
                    "set": set_name,
                    "camera": cam_dir.name,
                })

    # Bottom 20% by file size get re-done with ultra detail
    all_variants.sort(key=lambda x: x["size"])
    bottom_20 = all_variants[:max(len(all_variants) // 5, 5)]

    for v in bottom_20:
        cam = v["camera"]
        lighting = v["set"] if v["set"] in LIGHTING_MODIFIERS else "daylight"
        base_prompt = CAMERA_PROMPTS.get(cam, CAMERA_PROMPTS["CAM_hero"])
        light_mod = LIGHTING_MODIFIERS.get(lighting, "")

        # Find structural input
        config = RENDER_SETS[v["set"]]
        candidates = list(config["input_dir"].glob(f"*{cam}*"))
        if not candidates:
            continue

        # Re-generate with ultra detail suffix
        existing_count = len(list(v["path"].parent.glob("variant_*.png")))
        new_idx = existing_count  # next variant number

        for refine_name, refine_prompt in [("ultra_detail", REFINEMENT_PROMPTS["ultra_detail"]),
                                            ("atmosphere", REFINEMENT_PROMPTS["atmosphere"])]:
            out_path = v["path"].parent / f"variant_{new_idx}_{refine_name}.png"
            if out_path.exists():
                continue
            tasks.append({
                "phase": "1_quality_boost",
                "priority": 1,
                "input": candidates[0],
                "output": out_path,
                "prompt": base_prompt + light_mod + STYLE_SUFFIX + refine_prompt,
                "temperature": 0.4,  # lower temp for more detail
                "description": f"Quality boost: {v['set']}/{cam} ({refine_name})",
            })
            new_idx += 1

    # ─── PHASE 2: Extra activity scenes ───
    for cam_name, scenes in EXTRA_ACTIVITY_SCENES.items():
        # Find structural input
        for set_name, config in RENDER_SETS.items():
            candidates = list(config["input_dir"].glob(f"*{cam_name}*"))
            if candidates:
                break
        if not candidates:
            continue

        for scene in scenes:
            out_path = ACTIVITY_BASE / cam_name / f"{scene['name']}.png"
            if out_path.exists():
                continue

            ref_instruction = ""
            if COMMUNITY_REF.exists():
                ref_instruction = " The SECOND image is a STYLE REFERENCE for people appearance. Match the fashion, age range (20s-40s), diversity, and casual earth-tone aesthetic."

            tasks.append({
                "phase": "2_activity_scenes",
                "priority": 2,
                "input": candidates[0],
                "output": out_path,
                "prompt": scene["prompt"] + ref_instruction + BASE_ACTIVITY_STYLE,
                "temperature": 0.6,
                "ref_image": COMMUNITY_REF if COMMUNITY_REF.exists() else None,
                "description": f"Activity: {cam_name}/{scene['name']}",
            })

    # ─── PHASE 3: Weather/mood variants on hero cameras ───
    hero_cameras = ["CAM_hero", "CAM_pool_spa", "CAM_entrance", "CAM_firepit_evening"]
    mood_combos = [
        ("weather_mood", "after_rain", 0.5),
        ("magic_hour", "magic_hour", 0.6),
        ("botanical_max", "botanical_max", 0.5),
    ]

    for cam in hero_cameras:
        for set_name in ["daylight", "golden"]:
            config = RENDER_SETS[set_name]
            candidates = list(config["input_dir"].glob(f"*{cam}*"))
            if not candidates:
                continue

            base = CAMERA_PROMPTS.get(cam, CAMERA_PROMPTS["CAM_hero"])
            light = LIGHTING_MODIFIERS.get(set_name, "")

            for refine_key, suffix, temp in mood_combos:
                out_dir = config["output_base"] / cam
                out_path = out_dir / f"variant_{suffix}.png"
                if out_path.exists():
                    continue

                tasks.append({
                    "phase": "3_mood_variants",
                    "priority": 3,
                    "input": candidates[0],
                    "output": out_path,
                    "prompt": base + light + STYLE_SUFFIX + REFINEMENT_PROMPTS[refine_key],
                    "temperature": temp,
                    "description": f"Mood: {set_name}/{cam}/{suffix}",
                })

    # ─── PHASE 4: Fill gaps — cameras with < 5 variants ───
    for set_name, config in RENDER_SETS.items():
        if not config["input_dir"].exists():
            continue
        for render_path in sorted(config["input_dir"].glob(config["pattern"])):
            cam = config["cam_extract"](render_path.stem)
            cam_dir = config["output_base"] / cam
            existing = len(list(cam_dir.glob("variant_*.png"))) if cam_dir.exists() else 0

            if existing >= 5:
                continue

            base = CAMERA_PROMPTS.get(cam, CAMERA_PROMPTS["CAM_hero"])
            lighting = set_name if set_name in LIGHTING_MODIFIERS else "daylight"
            light = LIGHTING_MODIFIERS.get(lighting, "")

            for i in range(existing, 5):
                out_path = cam_dir / f"variant_{i}.png"
                if out_path.exists():
                    continue

                variant_suffixes = ["", REFINEMENT_PROMPTS["ultra_detail"],
                                   REFINEMENT_PROMPTS["atmosphere"],
                                   REFINEMENT_PROMPTS["botanical_max"],
                                   REFINEMENT_PROMPTS["weather_mood"]]
                extra = variant_suffixes[i % len(variant_suffixes)]

                tasks.append({
                    "phase": "4_fill_gaps",
                    "priority": 4,
                    "input": render_path,
                    "output": out_path,
                    "prompt": base + light + STYLE_SUFFIX + extra,
                    "temperature": [0.3, 0.5, 0.7, 0.9, 1.0][i % 5],
                    "description": f"Fill gap: {set_name}/{cam}/v{i}",
                })

    # Sort by priority
    tasks.sort(key=lambda t: t["priority"])
    return tasks


def main():
    parser = argparse.ArgumentParser(description="Iterative quality enhancement")
    parser.add_argument("--hours", type=float, default=6, help="Time budget in hours")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without running")
    args = parser.parse_args()

    deadline = datetime.now(timezone.utc) + timedelta(hours=args.hours)

    print("=" * 60)
    print("  SPONIC GARDEN v11 — ITERATIVE ENHANCEMENT")
    print("=" * 60)
    print(f"  Model: {MODEL}")
    print(f"  Time budget: {args.hours} hours")
    print(f"  Deadline: {deadline.strftime('%H:%M UTC')}")
    print(f"  Building task queue...")
    print()

    tasks = build_task_queue()

    # Group by phase for reporting
    phases = {}
    for t in tasks:
        phases.setdefault(t["phase"], []).append(t)

    for phase, items in sorted(phases.items()):
        print(f"  {phase}: {len(items)} tasks")
        if args.dry_run:
            for item in items[:5]:
                print(f"    - {item['description']}")
            if len(items) > 5:
                print(f"    ... and {len(items) - 5} more")

    print(f"\n  Total tasks: {len(tasks)}")
    est_time = len(tasks) * (RATE_LIMIT + 30) / 3600  # ~45s per task
    print(f"  Estimated time: ~{est_time:.1f} hours")

    if args.dry_run:
        print("\n  DRY RUN — no images generated")
        return 0

    print(f"\n  Starting enhancement loop...")
    print("=" * 60)

    client = genai.Client(api_key=API_KEY)

    results = []
    completed = 0
    errors = 0

    for i, task in enumerate(tasks):
        # Check time budget
        if datetime.now(timezone.utc) >= deadline:
            print(f"\n  TIME BUDGET REACHED — stopping after {completed} tasks")
            break

        remaining = (deadline - datetime.now(timezone.utc)).total_seconds() / 3600
        print(f"\n  [{i+1}/{len(tasks)}] {task['description']} ({remaining:.1f}h remaining)")

        try:
            result = generate_image(
                client,
                task["input"],
                task["output"],
                task["prompt"],
                task["temperature"],
                task.get("ref_image"),
            )
            result["task"] = task["description"]
            result["phase"] = task["phase"]
            results.append(result)

            if result["success"]:
                completed += 1
            else:
                errors += 1
                print(f"      WARNING: No image generated")

        except Exception as e:
            errors += 1
            print(f"      ERROR: {e}")
            results.append({
                "task": task["description"],
                "phase": task["phase"],
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # If rate limited, wait longer
            if "429" in str(e) or "quota" in str(e).lower():
                print(f"      Rate limited — waiting 60s...")
                time.sleep(60)

        # Rate limit
        if i < len(tasks) - 1:
            time.sleep(RATE_LIMIT)

    # Save metadata
    meta_path = REVIEW_BASE / "iterative_metadata.json"
    metadata = {
        "version": "v11-iterative",
        "model": MODEL,
        "started": (deadline - timedelta(hours=args.hours)).isoformat(),
        "ended": datetime.now(timezone.utc).isoformat(),
        "hours_budget": args.hours,
        "tasks_total": len(tasks),
        "tasks_completed": completed,
        "tasks_errors": errors,
        "results": results,
    }
    meta_path.write_text(json.dumps(metadata, indent=2))

    print(f"\n{'=' * 60}")
    print(f"  ITERATIVE ENHANCEMENT COMPLETE")
    print(f"  Completed: {completed}/{len(tasks)}")
    print(f"  Errors: {errors}")
    print(f"  Metadata: {meta_path}")
    print(f"{'=' * 60}")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
