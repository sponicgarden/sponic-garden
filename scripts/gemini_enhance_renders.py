"""
Gemini AI Photorealistic Enhancement for Sponic Garden v11 Renders

Takes structural 3D renders from Blender and uses Gemini image generation
to produce photorealistic versions that preserve layout/structure but add
real-world textures, lighting, vegetation detail, and atmosphere.

Supports multi-pass input: beauty + depth + normal maps for better AI results.
Supports multiple lighting variants: daylight, golden hour, blue hour.
Supports new camera angles beyond the original 8.

Usage:
    python3 scripts/gemini_enhance_renders.py                    # daylight only
    python3 scripts/gemini_enhance_renders.py --all              # all variants
    python3 scripts/gemini_enhance_renders.py --golden            # golden hour only
    python3 scripts/gemini_enhance_renders.py --bluehour          # blue hour only
    python3 scripts/gemini_enhance_renders.py --newcams           # new cameras only

Requires:
    - google-genai SDK installed
    - Gemini API key in /tmp/.gemini_key_sg
    - Structural renders in design/renders/v11*/
"""
import os
import sys
import json
import time
import argparse
from pathlib import Path
from google import genai
from google.genai import types

# ═══════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════
PROJECT_ROOT = Path(__file__).parent.parent

RENDER_SETS = {
    "daylight": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11",
        "output_dir": PROJECT_ROOT / "design" / "renders" / "v11-photo",
        "pattern": "v11_CAM_*.png",
        "prefix": "v11_photo",
        "cam_extract": lambda stem: stem.replace("v11_", ""),
    },
    "golden": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11-golden",
        "output_dir": PROJECT_ROOT / "design" / "renders" / "v11-golden-photo",
        "pattern": "v11_golden_CAM_*.png",
        "prefix": "v11_golden_photo",
        "cam_extract": lambda stem: stem.replace("v11_golden_", ""),
    },
    "bluehour": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11-bluehour",
        "output_dir": PROJECT_ROOT / "design" / "renders" / "v11-bluehour-photo",
        "pattern": "v11_blue_CAM_*.png",
        "prefix": "v11_blue_photo",
        "cam_extract": lambda stem: stem.replace("v11_blue_", ""),
    },
    "newcams": {
        "input_dir": PROJECT_ROOT / "design" / "renders" / "v11-newcams",
        "output_dir": PROJECT_ROOT / "design" / "renders" / "v11-newcams-photo",
        "pattern": "v11_CAM_*.png",
        "prefix": "v11_newcam_photo",
        "cam_extract": lambda stem: stem.replace("v11_", ""),
    },
}

PASSES_DIR = PROJECT_ROOT / "design" / "renders" / "v11-passes"

# Load API key
KEY_FILE = Path("/tmp/.gemini_key_sg")
if not KEY_FILE.exists():
    print("ERROR: API key file /tmp/.gemini_key_sg not found")
    sys.exit(1)

API_KEY = KEY_FILE.read_text().strip()
MODEL = "gemini-2.5-flash-image"

# ═══════════════════════════════════════════
# CAMERA-SPECIFIC PROMPTS
# ═══════════════════════════════════════════

CAMERA_PROMPTS = {
    "CAM_aerial": (
        "Transform this overhead architectural 3D diagram into a photorealistic aerial "
        "photograph taken by a drone on a sunny day. This is Sponic Garden, a 2-acre garden "
        "campus with 7 buildings, a swimming pool, spa area, greenhouse, fire pit, walkways, "
        "and dense gardens. Industrial-garden aesthetic: exposed steel trusses, corrugated metal "
        "roofing, brick and cedar buildings, dense green vegetation, stone walkways, string lights. "
        "Keep the EXACT same layout, building positions, sizes, and shapes. Add realistic grass "
        "textures, tree canopies, water reflections, shadow patterns, and building materials. "
        "The saunas are SQUARE wooden cabins with windows, NOT barrel saunas."
    ),
    "CAM_hero": (
        "Transform this 3D architectural perspective into a photorealistic photograph of a "
        "garden campus venue called Sponic Garden. Shot from an elevated angle showing the full "
        "campus. Industrial-garden aesthetic: exposed steel trusses visible on buildings, corrugated "
        "metal walls and roofing, red brick facades, natural cedar wood, dense climbing vines on "
        "walls, lush green gardens, string lights between buildings. Keep the EXACT same layout, "
        "building positions, camera angle, and proportions. Add rich material textures, realistic "
        "vegetation, atmospheric haze, and natural sunlight with soft shadows. The saunas are "
        "square wooden cabins with glass windows. Bright sunny day, blue sky with scattered clouds."
    ),
    "CAM_pool_spa": (
        "Transform this 3D render into a photorealistic photograph of a pool and spa area at "
        "Sponic Garden. Shows a rectangular swimming pool with turquoise water, sun loungers with "
        "canvas umbrellas, and nearby spa area with square cedar saunas (with glass windows), "
        "hot tubs, and cold plunge pool. Industrial-garden setting with corrugated metal and "
        "brick buildings visible in background. Dense hedges provide privacy. String lights "
        "overhead. Keep the EXACT same layout and camera angle. Add realistic water caustics, "
        "reflections, wet surfaces, lush plantings, and natural afternoon sunlight."
    ),
    "CAM_entrance": (
        "Transform this ground-level 3D render into a photorealistic eye-level photograph of "
        "the entrance approach to Sponic Garden. Looking straight ahead down a stone walkway "
        "toward the venue. Welcome center building visible with brick walls. Hedges line the "
        "entrance path, potted plants and shrubs at building entrances. String lights and "
        "lanterns along the path. Industrial-garden aesthetic with exposed steel, brick, "
        "cedar wood. Keep the EXACT same perspective, building positions, and walkway layout. "
        "Add realistic paving textures, verdant plantings, warm lighting atmosphere, and "
        "depth of field."
    ),
    "CAM_greenhouse_detail": (
        "Transform this close-up 3D render into a photorealistic photograph of the main "
        "greenhouse at Sponic Garden. Steel frame structure with glass walls and exposed "
        "A-frame steel trusses visible through the glass. Interior tables with potted plants "
        "visible. Climbing vines on the exterior. 'SPONIC GARDEN' signage on the south wall. "
        "Keep the EXACT same framing, structure, and details. Add realistic steel patina, "
        "glass reflections and refractions, condensation, lush interior plants, and warm "
        "interior lighting glowing through the glass. Shallow depth of field, sharp focus "
        "on the greenhouse."
    ),
    "CAM_firepit_evening": (
        "Transform this 3D render into a photorealistic photograph of a fire pit area at "
        "Sponic Garden. Circular concrete fire pit with wooden seating ring, string lights "
        "visible overhead between buildings. Warm fire glow illuminating the scene. Industrial "
        "buildings visible in background with corrugated metal walls. Potted plants and hedges "
        "nearby. Keep the EXACT same layout and camera angle. Add realistic fire flames and "
        "embers, warm light on surrounding surfaces, twinkling string light bokeh, evening "
        "atmosphere with deep blue sky transitioning to warm ground-level lighting."
    ),
    "CAM_coffee_bar": (
        "Transform this close-up 3D render into a photorealistic photograph of an outdoor "
        "coffee bar at Sponic Garden. Semi-open structure with cedar posts supporting a wooden "
        "roof canopy. Counter bar with stools. String lights above. Nearby industrial buildings "
        "with brick and corrugated metal. Potted plants scattered around. Keep the EXACT same "
        "framing, structure positions, and details. Add realistic cedar grain, worn counter "
        "surfaces, artisanal coffee bar atmosphere, shallow depth of field."
    ),
    "CAM_spa_detail": (
        "Transform this close-up 3D render into a photorealistic photograph of the spa area "
        "at Sponic Garden. TWO SQUARE wooden sauna cabins with glass windows (NOT barrel saunas), "
        "cedar hot tubs, and a concrete cold plunge pool. Wooden deck underneath. Hedges provide "
        "privacy. Industrial Spa House building visible behind. Keep the EXACT same layout, "
        "sauna shapes (rectangular/square with flat roof and windows), hot tub positions, and "
        "camera angle. Add realistic cedar wood grain, steam rising from hot tubs, warm window "
        "glow from inside saunas, wet deck surfaces, and lush surrounding plantings."
    ),
    # New cameras
    "CAM_greenhouse_interior": (
        "Transform this 3D render into a photorealistic photograph taken INSIDE a large "
        "greenhouse, looking south through glass walls toward a garden campus. Steel frame "
        "columns and A-frame trusses overhead. Potting tables with plants in foreground. "
        "Glass walls show the outdoor campus beyond. Warm humid interior atmosphere with "
        "condensation on glass. Keep the EXACT same perspective and structural layout. "
        "Add realistic interior greenhouse atmosphere, plant textures, steel patina, and "
        "filtered light through glass."
    ),
    "CAM_garden_ground": (
        "Transform this ground-level 3D render into a photorealistic photograph taken at "
        "knee height among raised garden beds. Lush vegetable rows in cedar-sided beds in "
        "foreground, with a glass greenhouse building visible in the background. Dense "
        "vegetation, rich soil textures, morning dew. Shallow depth of field with sharp "
        "foreground plants. Keep the EXACT same perspective and building positions."
    ),
    "CAM_walkway": (
        "Transform this 3D render into a photorealistic photograph of a covered walkway "
        "corridor at Sponic Garden. Cedar posts and roof beams frame the view. Stone path "
        "underneath. Buildings visible on both sides — corrugated metal and brick walls. "
        "Climbing vines on walls, string lights above, potted plants along the path. "
        "Keep the EXACT same perspective and structural elements. Add realistic wood grain, "
        "dappled light through the roof slats, and lush vegetation."
    ),
    "CAM_sauna_eyelevel": (
        "Transform this 3D render into a photorealistic eye-level photograph of TWO SQUARE "
        "cedar sauna cabins at Sponic Garden. Rectangular wooden buildings with flat metal "
        "roofs, glass windows glowing warm from inside, chimney flues on top. Cedar hot tubs "
        "nearby with steam rising. Wooden deck, hedges for privacy. Keep the EXACT same layout "
        "and sauna shapes — they are SQUARE buildings, NOT barrel/cylindrical saunas. Add "
        "realistic cedar wood grain, warm window glow, steam, and wet deck surfaces."
    ),
}

# Lighting-specific prompt modifiers
LIGHTING_MODIFIERS = {
    "daylight": "",
    "golden": (
        " The scene is lit by golden hour sunset light — warm orange sun low on the horizon, "
        "long dramatic shadows, warm tones on all surfaces, slightly hazy atmosphere. The sky "
        "should show warm sunset gradients from orange to blue."
    ),
    "bluehour": (
        " The scene is during blue hour twilight — the sun has set, the sky is deep blue with "
        "remnants of purple and orange at the horizon. Artificial lights are the primary "
        "illumination: string lights glow warmly, lanterns along paths, fire pit flames, and "
        "warm interior light glows through building windows. The overall mood is intimate and "
        "magical."
    ),
}

BASE_STYLE_SUFFIX = (
    " Style: high-end architectural photography, Canon EOS R5, natural light. "
    "Photo should look like it was taken by a professional photographer for an "
    "architecture magazine. Absolutely preserve the structural layout — do NOT "
    "rearrange, add, or remove any buildings or features."
)


def find_pass_files(camera_name: str) -> dict:
    """Find depth/normal/mist pass files for a camera if they exist."""
    passes = {}
    if not PASSES_DIR.exists():
        return passes

    for pass_type in ['depth', 'normal', 'mist']:
        # File output nodes append frame number, so look for patterns
        candidates = list(PASSES_DIR.glob(f"v11_{camera_name}_{pass_type}_*"))
        if candidates:
            passes[pass_type] = candidates[0]  # take first match
    return passes


def enhance_render(client, input_path: Path, output_path: Path,
                   camera_name: str, lighting: str = "daylight") -> dict:
    """Enhance a single structural render using Gemini image generation."""
    image_bytes = input_path.read_bytes()

    # Get camera-specific prompt
    prompt = CAMERA_PROMPTS.get(camera_name, CAMERA_PROMPTS["CAM_hero"])
    lighting_mod = LIGHTING_MODIFIERS.get(lighting, "")
    full_prompt = prompt + lighting_mod + BASE_STYLE_SUFFIX

    # Build content parts
    parts = [types.Part.from_bytes(data=image_bytes, mime_type="image/png")]

    # Add geometry passes if available (only for daylight — same geometry)
    pass_files = find_pass_files(camera_name)
    pass_instructions = ""

    if pass_files.get('depth'):
        depth_bytes = pass_files['depth'].read_bytes()
        parts.append(types.Part.from_bytes(data=depth_bytes, mime_type="image/png"))
        pass_instructions += (
            " The second image is a depth map (white=near, black=far). "
            "Use it to apply realistic atmospheric haze and depth of field blur."
        )

    if pass_files.get('normal'):
        normal_bytes = pass_files['normal'].read_bytes()
        parts.append(types.Part.from_bytes(data=normal_bytes, mime_type="image/png"))
        pass_instructions += (
            f" Image {len(parts)} is a surface normal map. Use it to understand "
            "surface angles for accurate material textures and specular highlights."
        )

    parts.append(full_prompt + pass_instructions)

    print(f"  Sending to Gemini ({MODEL})...")
    print(f"  Images: 1 beauty" + (f" + {len(pass_files)} passes" if pass_files else ""))
    print(f"  Lighting: {lighting}")

    response = client.models.generate_content(
        model=MODEL,
        contents=parts,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            temperature=0.4,
        ),
    )

    result_info = {
        "camera": camera_name,
        "lighting": lighting,
        "model": MODEL,
        "prompt": full_prompt[:500],
        "input_file": str(input_path),
        "output_file": str(output_path),
        "passes_used": list(pass_files.keys()),
        "text_response": "",
        "success": False,
    }

    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            output_path.write_bytes(part.inline_data.data)
            result_info["success"] = True
            result_info["file_size_bytes"] = len(part.inline_data.data)
            result_info["mime_type"] = part.inline_data.mime_type
            print(f"  Saved: {output_path.name} ({len(part.inline_data.data) / 1024:.0f} KB)")
        elif part.text:
            result_info["text_response"] = part.text
            print(f"  Text: {part.text[:200]}")

    return result_info


def process_render_set(client, set_name: str) -> list:
    """Process a complete render set (daylight, golden, etc.)."""
    config = RENDER_SETS[set_name]
    input_dir = config["input_dir"]
    output_dir = config["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    lighting = set_name if set_name in LIGHTING_MODIFIERS else "daylight"

    renders = sorted(input_dir.glob(config["pattern"]))
    if not renders:
        print(f"\n  No renders found in {input_dir} matching {config['pattern']}")
        return []

    print(f"\n  Found {len(renders)} renders in {set_name}")

    results = []
    for i, render_path in enumerate(renders):
        camera_name = config["cam_extract"](render_path.stem)
        output_path = output_dir / f"{config['prefix']}_{camera_name}.png"

        # Skip if already processed
        if output_path.exists():
            print(f"\n  [{i+1}/{len(renders)}] {camera_name} — already processed, skipping")
            continue

        print(f"\n  [{i+1}/{len(renders)}] {camera_name}")

        try:
            result = enhance_render(client, render_path, output_path, camera_name, lighting)
            results.append(result)

            if not result["success"]:
                print(f"  WARNING: No image generated for {camera_name}")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "camera": camera_name,
                "lighting": lighting,
                "success": False,
                "error": str(e),
            })

        # Rate limiting
        if i < len(renders) - 1:
            print("  Waiting 10s (rate limit)...")
            time.sleep(10)

    return results


def main():
    parser = argparse.ArgumentParser(description="Gemini photorealistic enhancement")
    parser.add_argument("--all", action="store_true", help="Process all render sets")
    parser.add_argument("--daylight", action="store_true", help="Process daylight renders")
    parser.add_argument("--golden", action="store_true", help="Process golden hour renders")
    parser.add_argument("--bluehour", action="store_true", help="Process blue hour renders")
    parser.add_argument("--newcams", action="store_true", help="Process new camera renders")
    args = parser.parse_args()

    # Default to daylight if nothing specified
    sets_to_process = []
    if args.all:
        sets_to_process = ["daylight", "golden", "bluehour", "newcams"]
    else:
        if args.daylight or (not any([args.golden, args.bluehour, args.newcams])):
            sets_to_process.append("daylight")
        if args.golden:
            sets_to_process.append("golden")
        if args.bluehour:
            sets_to_process.append("bluehour")
        if args.newcams:
            sets_to_process.append("newcams")

    print("=" * 60)
    print("  GEMINI PHOTOREALISTIC ENHANCEMENT")
    print("  Sponic Garden v11")
    print("=" * 60)
    print(f"  Model: {MODEL}")
    print(f"  Sets: {', '.join(sets_to_process)}")
    print(f"  Passes dir: {PASSES_DIR}")
    print("")

    client = genai.Client(api_key=API_KEY)

    all_results = []
    for set_name in sets_to_process:
        print(f"\n{'=' * 60}")
        print(f"  Processing: {set_name}")
        print(f"{'=' * 60}")
        results = process_render_set(client, set_name)
        all_results.extend(results)

    # Save metadata
    meta_dir = PROJECT_ROOT / "design" / "renders"
    metadata_path = meta_dir / "enhancement_metadata.json"

    # Load existing metadata if present
    existing = {}
    if metadata_path.exists():
        try:
            existing = json.loads(metadata_path.read_text())
        except:
            pass

    existing_results = existing.get("results", [])
    existing_results.extend(all_results)

    metadata = {
        "version": "v11",
        "model": MODEL,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sets_processed": sets_to_process,
        "results": existing_results,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2))

    success_count = sum(1 for r in all_results if r.get("success"))
    total_count = len(all_results)

    print(f"\n{'=' * 60}")
    print(f"  ENHANCEMENT COMPLETE")
    print(f"  Success: {success_count}/{total_count}")
    print(f"  Metadata: {metadata_path}")
    print(f"{'=' * 60}")

    return 0 if success_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())
