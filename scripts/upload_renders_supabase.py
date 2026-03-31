"""
Upload v11 renders (structural + photorealistic) to Supabase storage
and insert metadata into the image_assets table.

Usage:
    python3 scripts/upload_renders_supabase.py

Requires:
    - Supabase credentials in /tmp/.supabase_creds_sg
    - Renders in design/renders/v11/ and design/renders/v11-photo/
"""
import os
import sys
import json
import time
import requests
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
V11_DIR = PROJECT_ROOT / "design" / "renders" / "v11"
V11_PHOTO_DIR = PROJECT_ROOT / "design" / "renders" / "v11-photo"

# Load Supabase credentials
CREDS_FILE = Path("/tmp/.supabase_creds_sg")
if not CREDS_FILE.exists():
    print("ERROR: Supabase credentials not found at /tmp/.supabase_creds_sg")
    sys.exit(1)

lines = CREDS_FILE.read_text().strip().split("\n")
SUPABASE_URL = lines[0].strip()
SERVICE_ROLE_KEY = lines[1].strip()
BUCKET = "branding"

HEADERS = {
    "apikey": SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
}

# Enhancement metadata
METADATA_FILE = V11_PHOTO_DIR / "enhancement_metadata.json"


def upload_file(filepath: Path, storage_path: str) -> str:
    """Upload a file to Supabase storage. Returns the public URL."""
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}"

    with open(filepath, "rb") as f:
        data = f.read()

    # Try upsert
    resp = requests.post(
        url,
        headers={
            **HEADERS,
            "Content-Type": "image/png",
            "x-upsert": "true",
        },
        data=data,
    )

    if resp.status_code not in (200, 201):
        print(f"  Upload error: {resp.status_code} {resp.text[:200]}")
        return ""

    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
    return public_url


def insert_asset(record: dict) -> bool:
    """Insert a row into image_assets table."""
    url = f"{SUPABASE_URL}/rest/v1/image_assets"
    resp = requests.post(
        url,
        headers={
            **HEADERS,
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json=record,
    )
    if resp.status_code not in (200, 201):
        print(f"  Insert error: {resp.status_code} {resp.text[:200]}")
        return False
    return True


def get_prompt_for_camera(camera_name: str) -> str:
    """Get the Gemini prompt used for this camera from metadata."""
    if METADATA_FILE.exists():
        meta = json.loads(METADATA_FILE.read_text())
        for r in meta.get("results", []):
            if r.get("camera") == camera_name and r.get("prompt"):
                return r["prompt"]
    return ""


CAMERA_DESCRIPTIONS = {
    "CAM_aerial": "Aerial overview of Sponic Garden campus — all 7 buildings, pool, spa, greenhouse, gardens",
    "CAM_hero": "Hero perspective shot of Sponic Garden from elevated angle",
    "CAM_pool_spa": "Pool and spa area with loungers, umbrellas, saunas, and hot tubs",
    "CAM_entrance": "Eye-level entrance approach along the main walkway",
    "CAM_greenhouse_detail": "Close-up of the main greenhouse with steel trusses and glass walls",
    "CAM_firepit_evening": "Fire pit area with circular seating and string lights",
    "CAM_coffee_bar": "Outdoor coffee bar with cedar posts and counter stools",
    "CAM_spa_detail": "Spa detail — square cedar saunas with windows, hot tubs, cold plunge",
}


def main():
    print("=" * 60)
    print("  SUPABASE UPLOAD — v11 Renders")
    print("=" * 60)
    print(f"  URL: {SUPABASE_URL}")
    print(f"  Bucket: {BUCKET}")
    print("")

    uploaded = 0
    errors = 0

    # Upload structural renders
    structural_renders = sorted(V11_DIR.glob("v11_CAM_*.png"))
    print(f"  Structural renders: {len(structural_renders)}")
    for f in structural_renders:
        camera = f.stem.replace("v11_", "")
        storage_path = f"renders/v11/{f.name}"
        print(f"\n  Uploading {f.name}...")
        public_url = upload_file(f, storage_path)
        if public_url:
            record = {
                "filename": f.name,
                "bucket": BUCKET,
                "storage_path": storage_path,
                "public_url": public_url,
                "description": f"v11 structural render — {CAMERA_DESCRIPTIONS.get(camera, camera)}",
                "category": "render",
                "ai_model": "blender-cycles",
                "prompt": "Blender Cycles 2048spp, 2K, clean daylight, square saunas, industrial-garden aesthetic",
                "keywords": "{" + ",".join(["v11", "structural", "blender", "cycles", camera.lower(), "sponic-garden"]) + "}",
                "mime_type": "image/png",
                "file_size_bytes": f.stat().st_size,
                "is_active": True,
            }
            if insert_asset(record):
                uploaded += 1
            else:
                errors += 1
        else:
            errors += 1

    # Upload all photorealistic render sets
    PHOTO_SETS = [
        ("v11-photo", "v11_photo_*.png", "v11_photo_", "daylight"),
        ("v11-golden-photo", "v11_golden_photo_*.png", "v11_golden_photo_", "golden hour"),
        ("v11-bluehour-photo", "v11_blue_photo_*.png", "v11_blue_photo_", "blue hour"),
        ("v11-newcams-photo", "v11_newcam_photo_*.png", "v11_newcam_photo_", "new angle"),
    ]

    for dirname, pattern, prefix, variant in PHOTO_SETS:
        photo_dir = PROJECT_ROOT / "design" / "renders" / dirname
        if not photo_dir.exists():
            continue
        photo_renders = sorted(photo_dir.glob(pattern))
        if not photo_renders:
            continue
        print(f"\n  {variant.title()} photorealistic renders: {len(photo_renders)}")
        for f in photo_renders:
            camera = f.stem.replace(prefix, "")
            storage_path = f"renders/{dirname}/{f.name}"
            prompt = get_prompt_for_camera(camera)
            print(f"\n  Uploading {f.name}...")
            public_url = upload_file(f, storage_path)
            if public_url:
                record = {
                    "filename": f.name,
                    "bucket": BUCKET,
                    "storage_path": storage_path,
                    "public_url": public_url,
                    "description": f"v11 {variant} photorealistic — {CAMERA_DESCRIPTIONS.get(camera, camera)}",
                    "category": "render",
                    "ai_model": "gemini-2.5-flash-image",
                    "prompt": prompt or f"Gemini image-to-image {variant} photorealistic enhancement",
                    "keywords": "{" + ",".join(["v11", "photorealistic", "gemini", variant.replace(" ", "-"), camera.lower(), "sponic-garden"]) + "}",
                    "mime_type": "image/png",
                    "file_size_bytes": f.stat().st_size,
                    "is_active": True,
                }
                if insert_asset(record):
                    uploaded += 1
                else:
                    errors += 1
            else:
                errors += 1

    print(f"\n{'=' * 60}")
    print(f"  UPLOAD COMPLETE")
    print(f"  Uploaded: {uploaded}")
    print(f"  Errors: {errors}")
    print(f"{'=' * 60}")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
