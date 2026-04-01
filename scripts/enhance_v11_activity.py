#!/usr/bin/env python3
"""
Gemini AI Activity Scene Enhancement — People Using the Spaces

Takes the structural Blender renders and generates photorealistic versions
with people actively using each space. Multiple activity scenarios per camera.

Usage:
    python3 scripts/enhance_v11_activity.py                    # all scenes
    python3 scripts/enhance_v11_activity.py --machine=A        # subset A
    python3 scripts/enhance_v11_activity.py --machine=B        # subset B

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
from datetime import datetime, timezone

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("ERROR: pip install google-genai")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).parent.parent
MODEL = "gemini-3-pro-image-preview"

REVIEW_BASE = PROJECT_ROOT / "design" / "renders" / "v11-review" / "activity"

KEY_FILE = Path("/tmp/.gemini_key_sg")
if not KEY_FILE.exists():
    print("ERROR: API key not found at /tmp/.gemini_key_sg")
    sys.exit(1)

API_KEY = KEY_FILE.read_text().strip()

# Community reference image — used as style reference for people appearance
COMMUNITY_REF = PROJECT_ROOT / "design" / "renders" / "v11-review" / "community_reference.png"

# ═══════════════════════════════════════════
# ACTIVITY SCENARIOS PER CAMERA
# Each camera gets multiple activity scenes showing different uses
# ═══════════════════════════════════════════

ACTIVITY_SCENES = {
    "CAM_hero": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11",
        "input_file": "v11_CAM_hero.png",
        "scenes": [
            {
                "name": "saturday_morning",
                "prompt": (
                    "Transform this 3D architectural render into a photorealistic photograph "
                    "of Sponic Garden on a busy Saturday morning. The 2-acre industrial-garden "
                    "campus is alive with activity: 8-10 people visible at various distances — "
                    "a couple walking hand-in-hand down the main stone path, a group of 3 doing "
                    "yoga on the lawn near the greenhouse, someone tending raised garden beds "
                    "with gardening gloves, a person reading on a bench, two friends chatting "
                    "with coffee cups near the coffee bar. Everyone is dressed casually — linen, "
                    "cotton, earth tones. The space feels like a thriving community garden mixed "
                    "with a boutique wellness retreat. Bright sunny morning light, blue sky."
                ),
            },
            {
                "name": "evening_gathering",
                "prompt": (
                    "Transform this 3D render into a photorealistic photograph of Sponic Garden "
                    "during a Friday evening community gathering. Warm golden hour light. The fire "
                    "pit has flames and 6 people sitting around it with drinks. String lights glow "
                    "overhead. A small group is walking between buildings. Someone is swimming in "
                    "the pool. The coffee bar has 3 people at it, a barista making drinks. The "
                    "greenhouse interior lights are on, showing plants inside. A couple sits on "
                    "a bench near the garden beds. The overall mood is relaxed, social, warm — "
                    "like the best neighborhood gathering you've ever been to. 15-20 people total, "
                    "naturally distributed across the campus."
                ),
            },
            {
                "name": "workshop_day",
                "prompt": (
                    "Transform this 3D render into a photorealistic photograph of Sponic Garden "
                    "during a gardening workshop day. A group of 8 people gathered around the "
                    "raised garden beds with an instructor showing planting techniques. Some "
                    "people have trowels and gloves. Seedling trays on a nearby table. A few "
                    "other people are walking the campus independently. Someone exits the "
                    "greenhouse carrying a potted plant. The Welcome Center has a chalkboard "
                    "sign reading 'Saturday Workshop: Spring Planting'. Educational, hands-on, "
                    "community atmosphere. Bright midday light."
                ),
            },
        ],
    },
    "CAM_pool_spa": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11",
        "input_file": "v11_CAM_pool_spa.png",
        "scenes": [
            {
                "name": "afternoon_swim",
                "prompt": (
                    "Transform this 3D render into a photorealistic photograph of the pool and "
                    "spa area at Sponic Garden on a warm afternoon. 2 people swimming in the "
                    "turquoise pool, creating gentle ripples. 1 person lounging on a teak sun "
                    "lounger reading a book, another person on a lounger with a towel over their "
                    "face napping. Near the spa: 1 person stepping into a hot tub, steam rising. "
                    "Rolled white towels on a cedar shelf. A cold drink with condensation on a "
                    "side table. The TWO SQUARE cedar saunas have warm light glowing through "
                    "their glass windows. Relaxed, luxurious but unpretentious atmosphere."
                ),
            },
            {
                "name": "morning_cold_plunge",
                "prompt": (
                    "Transform this 3D render into a photorealistic photograph of the spa area "
                    "early morning. Misty air, dawn light. 1 person in the cold plunge pool with "
                    "an expression of invigorating shock, water up to their shoulders. Another "
                    "person sitting on the edge of a hot tub with a towel around their shoulders, "
                    "holding a cup of tea, steam rising from both the cup and the hot tub. The "
                    "pool is calm, untouched. Morning dew on the ipe wood deck. The SQUARE saunas "
                    "have soft interior glow. Peaceful, meditative, wellness-focused morning ritual."
                ),
            },
            {
                "name": "social_spa",
                "prompt": (
                    "Transform this 3D render into a photorealistic photograph of the spa area "
                    "during a social evening. 3 people in the hot tub laughing and talking, warm "
                    "light from string lights above. 1 person emerging from a SQUARE sauna cabin "
                    "through the glass door, steam billowing out. 2 people by the pool edge with "
                    "their feet in the water, sharing a bottle of wine. Lanterns lit along the "
                    "deck. The pool has underwater lights creating a turquoise glow. Intimate, "
                    "social, magical evening atmosphere."
                ),
            },
        ],
    },
    "CAM_entrance": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11",
        "input_file": "v11_CAM_entrance.png",
        "scenes": [
            {
                "name": "arrival",
                "prompt": (
                    "Transform this 3D render into a photorealistic photograph of guests arriving "
                    "at Sponic Garden. A couple in their 30s walking toward the camera down the "
                    "stone path, the woman pointing ahead excitedly at the campus. Behind them, "
                    "the Welcome Center brick building with its wide porch. A staff member in a "
                    "linen apron stands at the entrance smiling. A chalkboard sign by the door "
                    "lists the day's activities. Potted lavender and rosemary line the walkway. "
                    "String lights are on even in the daytime, creating a festive first impression. "
                    "The feeling is: 'I can't believe this place exists.'"
                ),
            },
            {
                "name": "farmers_market",
                "prompt": (
                    "Transform this 3D render into a photorealistic photograph of the entrance "
                    "during a Sunday farmers market. Small wooden tables and crates line both "
                    "sides of the walkway with fresh produce — bundles of herbs, tomatoes, "
                    "squash, flowers. A vendor arranges vegetables. 3-4 visitors browse the "
                    "stalls, one person holds a paper bag of produce. A child reaches for a "
                    "sunflower. Hand-painted signs on recycled wood. The atmosphere is warm, "
                    "local, authentic. Morning light."
                ),
            },
        ],
    },
    "CAM_greenhouse_detail": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11",
        "input_file": "v11_CAM_greenhouse_detail.png",
        "scenes": [
            {
                "name": "workshop",
                "prompt": (
                    "Transform this 3D render into a photorealistic photograph of the greenhouse "
                    "during a plant propagation workshop. Through the glass walls, 5-6 people "
                    "visible inside standing around a long potting table. An instructor holds up "
                    "a cutting to demonstrate technique. Participants have small pots, soil, and "
                    "tools in front of them. Grow lights on above. Lush tropical plants fill the "
                    "shelves — monstera, ferns, herbs. The exterior glass shows condensation. "
                    "'SPONIC GARDEN' signage on the south wall. Warm, educational, green atmosphere."
                ),
            },
            {
                "name": "quiet_morning",
                "prompt": (
                    "Transform this 3D render into a photorealistic photograph of the greenhouse "
                    "early morning. Through the glass, a single person inside watering plants with "
                    "a copper watering can, moving between the grow tables. Morning sun streams "
                    "through the east-facing glass panels creating dramatic light shafts through "
                    "the humid air. Condensation on the glass. Climbing jasmine on the exterior "
                    "steel frame. A cat sits on the stone path outside. Peaceful, contemplative, "
                    "the garden at its most intimate."
                ),
            },
        ],
    },
    "CAM_firepit_evening": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11",
        "input_file": "v11_CAM_firepit_evening.png",
        "scenes": [
            {
                "name": "campfire_stories",
                "prompt": (
                    "Transform this 3D render into a photorealistic photograph of the fire pit "
                    "during an evening gathering. 8 people sitting on the wooden bench ring around "
                    "the circular fire pit with tall flames. Faces lit warm by the fire. 2 people "
                    "hold mugs of hot chocolate, 1 person is toasting a marshmallow. A guitar "
                    "leans against the bench. String lights twinkle overhead between the industrial "
                    "buildings. Deep blue twilight sky. Someone has a blanket over their shoulders. "
                    "The scene feels like the best campfire night of summer — intimate, warm, "
                    "connected. A few people walking in the background near the lit buildings."
                ),
            },
            {
                "name": "acoustic_session",
                "prompt": (
                    "Transform this 3D render into a photorealistic photograph of a small acoustic "
                    "music session at the fire pit. A musician sits on the bench playing acoustic "
                    "guitar, 10-12 people gathered around listening — some on the bench, some "
                    "sitting on the ground on cushions. A few people standing behind with drinks. "
                    "Small speaker visible. The fire burns low with glowing embers. String lights "
                    "and lanterns create a magical intimate concert atmosphere. Blue hour sky. "
                    "This is community music at its purest."
                ),
            },
        ],
    },
    "CAM_coffee_bar": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11",
        "input_file": "v11_CAM_coffee_bar.png",
        "scenes": [
            {
                "name": "morning_rush",
                "prompt": (
                    "Transform this 3D render into a photorealistic photograph of the outdoor "
                    "coffee bar during the morning. A barista in a linen apron operates an "
                    "espresso machine, steaming milk. 2 people sit on metal bar stools chatting "
                    "over flat whites. 1 person waits standing, checking their phone. A small "
                    "chalkboard menu lists single-origin coffees and fresh juices. Fresh pastries "
                    "on a wooden board under a glass dome. Potted herbs on the counter. Morning "
                    "light filtering through the cedar roof slats. The coffee bar feels artisanal "
                    "and welcoming — a place you'd walk to every morning."
                ),
            },
            {
                "name": "smoothie_afternoon",
                "prompt": (
                    "Transform this 3D render into a photorealistic photograph of the coffee bar "
                    "on a warm afternoon, pivoted to smoothies and cold drinks. A barista blends "
                    "a green smoothie. 3 colorful smoothies in glass jars sit on the counter. "
                    "2 people sit at the bar with iced drinks, one person laughing. Fresh fruit "
                    "display: bananas, berries, mangos. A person in workout clothes walks up "
                    "from the direction of the movement studio. Warm afternoon light."
                ),
            },
        ],
    },
    "CAM_greenhouse_interior": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11-newcams",
        "input_file": "v11_CAM_greenhouse_interior.png",
        "scenes": [
            {
                "name": "growing_session",
                "prompt": (
                    "Transform this interior greenhouse 3D render into a photorealistic photograph "
                    "of a growing session. 3 people at the potting tables: one repotting a plant, "
                    "one examining a seedling tray, one writing labels. Rich soil, terracotta pots, "
                    "gardening tools scattered naturally. Grow lights glow purple-pink above. Lush "
                    "plants on shelves: monstera, tomato vines, herbs, banana plant. Humid warm "
                    "air, condensation on the glass walls. Through the glass, the campus garden "
                    "is visible outside. The feeling is productive, grounding, therapeutic."
                ),
            },
        ],
    },
    "CAM_garden_ground": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11-newcams",
        "input_file": "v11_CAM_garden_ground.png",
        "scenes": [
            {
                "name": "harvesting",
                "prompt": (
                    "Transform this ground-level 3D render into a photorealistic photograph at "
                    "knee height in the garden beds. A person's hands visible in the foreground "
                    "harvesting cherry tomatoes into a woven basket — close-up, shallow depth "
                    "of field. Rich dark soil, lush green leaves, red tomatoes. Behind them, "
                    "another person kneeling at a neighboring bed tending herbs. The greenhouse "
                    "is softly blurred in the background. Morning dew on leaves. A pair of "
                    "gardening gloves and pruning shears rest on the cedar bed edge. This is "
                    "the tactile, grounding heart of Sponic Garden."
                ),
            },
        ],
    },
    "CAM_walkway": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11-newcams",
        "input_file": "v11_CAM_walkway.png",
        "scenes": [
            {
                "name": "between_sessions",
                "prompt": (
                    "Transform this 3D render into a photorealistic photograph of the covered "
                    "walkway between sessions. 2 people walking toward the camera in conversation, "
                    "one carrying a yoga mat, both in athletic wear. A person behind them heads "
                    "the other direction carrying a tray of seedlings. Dappled light through the "
                    "cedar roof slats. String lights overhead. The walkway connects the different "
                    "zones — you can see the greenhouse at one end and the movement studio sign "
                    "at the other. The campus feels connected, walkable, alive with purposeful "
                    "movement."
                ),
            },
        ],
    },
    "CAM_sauna_eyelevel": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11-newcams",
        "input_file": "v11_CAM_sauna_eyelevel.png",
        "scenes": [
            {
                "name": "post_sauna",
                "prompt": (
                    "Transform this 3D render into a photorealistic photograph of the sauna area "
                    "in use. 1 person wrapped in a white towel stepping out of one of the SQUARE "
                    "cedar sauna cabins, steam billowing from the open glass door. Another person "
                    "sitting on the ipe deck in a robe, eyes closed, relaxing. The hot tub has "
                    "2 people in it, steam rising. A stack of clean towels on a cedar shelf. "
                    "Birch whisks (vihta) hanging by the sauna door. The saunas are SQUARE "
                    "buildings with flat roofs and glass windows — NOT barrel saunas. Evening "
                    "light, warm glow from the sauna interior."
                ),
            },
        ],
    },
}

BASE_STYLE_SUFFIX = (
    " STYLE: High-end lifestyle/architectural photography for a luxury wellness magazine. "
    "Canon EOS R5, natural light. People should look natural, diverse, and genuine — not "
    "stock-photo-posed. Candid moments, natural body language. The space should feel real, "
    "lived-in, and aspirational. "
    "CRITICAL: Preserve the structural layout from the input image — same buildings, same "
    "angles, same positions. Just add photorealistic textures, lighting, atmosphere, and people."
)

MACHINE_SPLITS = {
    "A": ["CAM_hero", "CAM_pool_spa", "CAM_entrance", "CAM_greenhouse_detail", "CAM_firepit_evening"],
    "B": ["CAM_coffee_bar", "CAM_greenhouse_interior", "CAM_garden_ground", "CAM_walkway", "CAM_sauna_eyelevel"],
}


def enhance_activity(client, input_path: Path, output_path: Path,
                     scene_prompt: str, scene_name: str, camera_name: str) -> dict:
    """Generate one activity scene with community reference image for people style."""
    image_bytes = input_path.read_bytes()

    # Build prompt with reference image instruction
    ref_instruction = ""
    parts = [
        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
    ]

    # Add community reference image if available
    if COMMUNITY_REF.exists():
        ref_bytes = COMMUNITY_REF.read_bytes()
        parts.append(types.Part.from_bytes(data=ref_bytes, mime_type="image/png"))
        ref_instruction = (
            " The SECOND image is a STYLE REFERENCE for the people in the scene. "
            "Match the appearance, fashion, age range (20s-40s), diversity, and casual "
            "earth-tone aesthetic of this group. Linen, cotton, canvas, sage green, cream, "
            "terracotta, oatmeal tones. People should look like THIS community — creative, "
            "warm, authentic. Do NOT copy poses, just match the vibe and fashion."
        )
        print(f"    Using community reference image")

    full_prompt = scene_prompt + ref_instruction + BASE_STYLE_SUFFIX
    parts.append(full_prompt)

    temp = 0.6  # slightly creative for natural people

    print(f"    Sending to {MODEL} (scene: {scene_name})...")

    response = client.models.generate_content(
        model=MODEL,
        contents=parts,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            temperature=temp,
        ),
    )

    result = {
        "camera": camera_name,
        "scene": scene_name,
        "model": MODEL,
        "temperature": temp,
        "output_file": str(output_path),
        "success": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            output_path.write_bytes(part.inline_data.data)
            result["success"] = True
            result["file_size_bytes"] = len(part.inline_data.data)
            print(f"    Saved: {output_path.name} ({len(part.inline_data.data) / 1024:.0f} KB)")
        elif part.text:
            result["text_response"] = part.text[:500]
            print(f"    Text: {part.text[:200]}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Activity scene enhancement")
    parser.add_argument("--machine", choices=["A", "B"], help="Machine split")
    parser.add_argument("--all", action="store_true", help="All cameras")
    args = parser.parse_args()

    # Determine which cameras to process
    if args.machine:
        cameras_to_process = MACHINE_SPLITS[args.machine]
    else:
        cameras_to_process = list(ACTIVITY_SCENES.keys())

    total_scenes = sum(
        len(ACTIVITY_SCENES[c]["scenes"])
        for c in cameras_to_process
        if c in ACTIVITY_SCENES
    )

    print("=" * 60)
    print("  SPONIC GARDEN v11 — ACTIVITY SCENES")
    print("=" * 60)
    print(f"  Model: {MODEL}")
    print(f"  Cameras: {len(cameras_to_process)}")
    print(f"  Total scenes: {total_scenes}")
    print(f"  Machine: {args.machine or 'all'}")
    print("=" * 60)

    client = genai.Client(api_key=API_KEY)

    all_results = []
    count = 0

    for cam_name in cameras_to_process:
        if cam_name not in ACTIVITY_SCENES:
            continue

        config = ACTIVITY_SCENES[cam_name]
        input_path = config["input_dir"] / config["input_file"]

        if not input_path.exists():
            print(f"\n  SKIP {cam_name}: {input_path} not found")
            continue

        cam_dir = REVIEW_BASE / cam_name
        cam_dir.mkdir(parents=True, exist_ok=True)

        # Copy structural for reference
        structural = cam_dir / "structural.png"
        if not structural.exists():
            import shutil
            shutil.copy2(input_path, structural)

        for scene in config["scenes"]:
            count += 1
            output_path = cam_dir / f"{scene['name']}.png"

            if output_path.exists():
                print(f"\n  [{count}/{total_scenes}] {cam_name}/{scene['name']} — exists, skipping")
                continue

            print(f"\n  [{count}/{total_scenes}] {cam_name} / {scene['name']}")

            try:
                result = enhance_activity(
                    client, input_path, output_path,
                    scene["prompt"], scene["name"], cam_name
                )
                all_results.append(result)
            except Exception as e:
                print(f"    ERROR: {e}")
                all_results.append({
                    "camera": cam_name,
                    "scene": scene["name"],
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            # Rate limit
            if count < total_scenes:
                print("    Waiting 15s...")
                time.sleep(15)

    # Save metadata
    REVIEW_BASE.mkdir(parents=True, exist_ok=True)
    meta_path = REVIEW_BASE / "activity_metadata.json"
    metadata = {
        "version": "v11-activity",
        "model": MODEL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": all_results,
    }
    meta_path.write_text(json.dumps(metadata, indent=2))

    # Generate review HTML
    generate_review_html()

    success = sum(1 for r in all_results if r.get("success"))
    print(f"\n{'=' * 60}")
    print(f"  ACTIVITY SCENES COMPLETE")
    print(f"  Success: {success}/{len(all_results)}")
    print(f"{'=' * 60}")

    return 0 if success == len(all_results) else 1


def generate_review_html():
    """Generate activity scene review page."""
    html_path = REVIEW_BASE / "review.html"

    cameras = sorted([d for d in REVIEW_BASE.iterdir() if d.is_dir()])

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sponic Garden — Activity Scenes Review</title>
<style>
:root { --bg: #0a0a0a; --card: #141414; --border: #2a2a2a; --text: #e0e0e0; --accent: #e89b4a; }
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: var(--bg); color: var(--text); font-family: -apple-system, sans-serif; }
.header { padding: 2rem; text-align: center; border-bottom: 1px solid var(--border); }
.header h1 { font-size: 1.8rem; font-weight: 300; }
.header p { color: #888; margin-top: 0.5rem; }
.section { padding: 2rem; border-bottom: 1px solid var(--border); }
.section h2 { font-size: 1.2rem; margin-bottom: 1rem; color: var(--accent); text-transform: uppercase; letter-spacing: 0.08em; }
.scenes-row { display: flex; gap: 1rem; overflow-x: auto; padding-bottom: 1rem; }
.scene-card { flex: 0 0 auto; width: 480px; background: var(--card); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
.scene-card:hover { border-color: var(--accent); }
.scene-card.structural { border-color: #555; width: 360px; }
.scene-card img { width: 100%; height: auto; display: block; cursor: pointer; }
.scene-card .label { padding: 0.5rem 0.75rem; font-size: 0.85rem; color: #aaa; }
.scene-card .label strong { color: #ddd; }
.fullscreen-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.95); z-index: 1000; cursor: zoom-out; align-items: center; justify-content: center; }
.fullscreen-overlay.active { display: flex; }
.fullscreen-overlay img { max-width: 95vw; max-height: 95vh; object-fit: contain; }
</style>
</head>
<body>
<div class="header">
<h1>Sponic Garden — Activity Scenes</h1>
<p>People using the spaces. Click to enlarge. Does the venue feel alive?</p>
</div>
"""

    scene_labels = {
        "saturday_morning": "Saturday Morning — Community Active",
        "evening_gathering": "Friday Evening — Social Gathering",
        "workshop_day": "Workshop Day — Gardening Class",
        "afternoon_swim": "Afternoon — Pool & Lounging",
        "morning_cold_plunge": "Early Morning — Cold Plunge Ritual",
        "social_spa": "Evening — Social Spa",
        "arrival": "First Arrival — Welcome",
        "farmers_market": "Sunday — Farmers Market",
        "workshop": "Plant Propagation Workshop",
        "quiet_morning": "Quiet Morning — Solo Watering",
        "campfire_stories": "Evening — Campfire Stories",
        "acoustic_session": "Acoustic Music Session",
        "morning_rush": "Morning — Coffee Rush",
        "smoothie_afternoon": "Afternoon — Smoothie Bar",
        "growing_session": "Greenhouse — Growing Session",
        "harvesting": "Garden — Harvesting",
        "between_sessions": "Walkway — Between Sessions",
        "post_sauna": "Spa — Post-Sauna",
    }

    cam_labels = {
        "CAM_hero": "Hero Overview",
        "CAM_pool_spa": "Pool & Spa",
        "CAM_entrance": "Entrance",
        "CAM_greenhouse_detail": "Greenhouse Exterior",
        "CAM_firepit_evening": "Fire Pit",
        "CAM_coffee_bar": "Coffee Bar",
        "CAM_greenhouse_interior": "Greenhouse Interior",
        "CAM_garden_ground": "Garden Ground Level",
        "CAM_walkway": "Walkway Corridor",
        "CAM_sauna_eyelevel": "Sauna Eye Level",
    }

    for cam_dir in cameras:
        cam_name = cam_dir.name
        scenes = sorted([f for f in cam_dir.glob("*.png") if f.name != "structural.png"])
        structural = cam_dir / "structural.png"

        if not scenes:
            continue

        html += f'<div class="section">\n<h2>{cam_labels.get(cam_name, cam_name)}</h2>\n'
        html += '<div class="scenes-row">\n'

        if structural.exists():
            html += f'''<div class="scene-card structural">
<img src="{cam_name}/structural.png" alt="Structural" onclick="showFS(this)">
<div class="label">Structural (Blender)</div>
</div>\n'''

        for scene_path in scenes:
            scene_name = scene_path.stem
            label = scene_labels.get(scene_name, scene_name.replace("_", " ").title())
            html += f'''<div class="scene-card">
<img src="{cam_name}/{scene_path.name}" alt="{label}" onclick="showFS(this)">
<div class="label"><strong>{label}</strong></div>
</div>\n'''

        html += '</div>\n</div>\n'

    html += """
<div class="fullscreen-overlay" id="fs" onclick="this.classList.remove('active')">
<img id="fs-img" src="">
</div>
<script>
function showFS(img){document.getElementById('fs-img').src=img.src;document.getElementById('fs').classList.add('active')}
document.addEventListener('keydown',e=>{if(e.key==='Escape')document.getElementById('fs').classList.remove('active')});
</script>
</body></html>"""

    html_path.write_text(html)
    print(f"\n  Activity review page: {html_path}")


if __name__ == "__main__":
    sys.exit(main())
