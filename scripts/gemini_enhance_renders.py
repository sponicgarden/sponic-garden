"""
Gemini AI Photorealistic Enhancement for Sponic Garden v11 Renders

Takes structural 3D renders from Blender and uses Gemini image generation
to produce photorealistic versions that preserve layout/structure but add
real-world textures, lighting, vegetation detail, and atmosphere.

Usage:
    python3 scripts/gemini_enhance_renders.py

Requires:
    - google-genai SDK installed
    - Gemini API key in /tmp/.gemini_key_sg
    - Structural renders in design/renders/v11/
"""
import os
import sys
import json
import time
import base64
from pathlib import Path
from google import genai
from google.genai import types

# ═══════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════
PROJECT_ROOT = Path(__file__).parent.parent
INPUT_DIR = PROJECT_ROOT / "design" / "renders" / "v11"
OUTPUT_DIR = PROJECT_ROOT / "design" / "renders" / "v11-photo"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load API key
KEY_FILE = Path("/tmp/.gemini_key_sg")
if not KEY_FILE.exists():
    print("ERROR: API key file /tmp/.gemini_key_sg not found")
    print("Run the Bitwarden extraction step first")
    sys.exit(1)

API_KEY = KEY_FILE.read_text().strip()
MODEL = "gemini-2.0-flash-preview-image-generation"

# Camera-specific prompts for best results
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
}

BASE_STYLE_SUFFIX = (
    " Style: high-end architectural photography, Canon EOS R5, natural light. "
    "Photo should look like it was taken by a professional photographer for an "
    "architecture magazine. Absolutely preserve the structural layout — do NOT "
    "rearrange, add, or remove any buildings or features."
)


def enhance_render(client, input_path: Path, output_path: Path, camera_name: str) -> dict:
    """Enhance a single structural render using Gemini image generation."""
    # Read the input image
    image_bytes = input_path.read_bytes()

    # Get camera-specific prompt
    prompt = CAMERA_PROMPTS.get(camera_name, CAMERA_PROMPTS["CAM_hero"])
    full_prompt = prompt + BASE_STYLE_SUFFIX

    print(f"  Sending to Gemini ({MODEL})...")
    print(f"  Prompt: {full_prompt[:100]}...")

    # Use image-to-image: send the structural render as input
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            full_prompt,
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            temperature=0.4,
        ),
    )

    # Extract the generated image
    result_info = {
        "camera": camera_name,
        "model": MODEL,
        "prompt": full_prompt,
        "input_file": str(input_path),
        "output_file": str(output_path),
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


def main():
    print("=" * 60)
    print("  GEMINI PHOTOREALISTIC ENHANCEMENT")
    print("  Sponic Garden v11 Renders")
    print("=" * 60)
    print(f"  Model: {MODEL}")
    print(f"  Input: {INPUT_DIR}")
    print(f"  Output: {OUTPUT_DIR}")
    print("")

    # Initialize client
    client = genai.Client(api_key=API_KEY)

    # Find all v11 renders
    renders = sorted(INPUT_DIR.glob("v11_CAM_*.png"))
    if not renders:
        print("ERROR: No v11 renders found in", INPUT_DIR)
        print("Pull renders from Alpuca first:")
        print("  scp paca@192.168.1.200:~/Projects/sponic-garden-3d/renders/v11/*.png design/renders/v11/")
        sys.exit(1)

    print(f"  Found {len(renders)} renders to enhance")
    print("")

    results = []
    for i, render_path in enumerate(renders):
        camera_name = render_path.stem.replace("v11_", "")
        output_path = OUTPUT_DIR / f"v11_photo_{camera_name}.png"

        print(f"\n[{i+1}/{len(renders)}] {camera_name}")
        print(f"  Input: {render_path.name}")

        try:
            result = enhance_render(client, render_path, output_path, camera_name)
            results.append(result)

            if not result["success"]:
                print(f"  WARNING: No image generated for {camera_name}")
                if result["text_response"]:
                    print(f"  Response: {result['text_response'][:300]}")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "camera": camera_name,
                "success": False,
                "error": str(e),
            })

        # Rate limiting — Gemini has per-minute limits
        if i < len(renders) - 1:
            print("  Waiting 10s (rate limit)...")
            time.sleep(10)

    # Save metadata
    metadata_path = OUTPUT_DIR / "enhancement_metadata.json"
    metadata = {
        "version": "v11",
        "model": MODEL,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input_dir": str(INPUT_DIR),
        "output_dir": str(OUTPUT_DIR),
        "results": results,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2))

    # Summary
    success_count = sum(1 for r in results if r.get("success"))
    print(f"\n{'=' * 60}")
    print(f"  ENHANCEMENT COMPLETE")
    print(f"  Success: {success_count}/{len(renders)}")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  Metadata: {metadata_path}")
    print(f"{'=' * 60}")

    return 0 if success_count == len(renders) else 1


if __name__ == "__main__":
    sys.exit(main())
