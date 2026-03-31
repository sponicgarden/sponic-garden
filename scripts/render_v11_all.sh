#!/bin/bash
# Sponic Garden v11 — Full overnight render pipeline for Alpuca Mac mini M4
# Runs 4 render phases sequentially after the main v11 job completes.
#
# Usage: nohup bash scripts/render_v11_all.sh > renders/v11_extended.log 2>&1 &

set -e
cd ~/Projects/sponic-garden-3d

BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"
BLEND="sponic-garden-v11.blend"
LOG_DIR="renders"

echo "============================================================"
echo "  SPONIC GARDEN v11 — EXTENDED RENDER PIPELINE"
echo "  Started: $(date)"
echo "============================================================"

# Wait for the main v11 render to finish if still running
echo ""
echo "Checking if main v11 render is still running..."
while pgrep -f "build_v11_rapid" > /dev/null 2>&1; do
    echo "  Main render still running. Waiting 60s... ($(date))"
    sleep 60
done
echo "  Main render complete. Starting extended pipeline."

# Verify .blend file exists
if [ ! -f "$BLEND" ]; then
    echo "ERROR: $BLEND not found. Main render may have failed."
    exit 1
fi

echo ""
echo "============================================================"
echo "  PHASE 1: Geometry Passes (128spp) — ~35 min"
echo "  Started: $(date)"
echo "============================================================"
$BLENDER --background "$BLEND" --python scripts/render_v11_passes.py 2>&1 | tee "$LOG_DIR/v11_passes.log"

echo ""
echo "============================================================"
echo "  PHASE 2: Golden Hour (5 cameras, 2048spp) — ~3 hr"
echo "  Started: $(date)"
echo "============================================================"
$BLENDER --background "$BLEND" --python scripts/render_v11_golden.py 2>&1 | tee "$LOG_DIR/v11_golden.log"

echo ""
echo "============================================================"
echo "  PHASE 3: New Cameras (4 angles, 2048spp) — ~2.5 hr"
echo "  Started: $(date)"
echo "============================================================"
$BLENDER --background "$BLEND" --python scripts/render_v11_newcams.py 2>&1 | tee "$LOG_DIR/v11_newcams.log"

echo ""
echo "============================================================"
echo "  PHASE 4: Blue Hour (2 cameras, 2048spp) — ~50 min"
echo "  Started: $(date)"
echo "============================================================"
$BLENDER --background "$BLEND" --python scripts/render_v11_bluehour.py 2>&1 | tee "$LOG_DIR/v11_bluehour.log"

echo ""
echo "============================================================"
echo "  ALL PHASES COMPLETE"
echo "  Finished: $(date)"
echo "============================================================"
echo ""
echo "Output directories:"
echo "  renders/v11/           — daylight beauty (8 cameras)"
echo "  renders/v11-passes/    — geometry passes (depth/normal/mist/AO)"
echo "  renders/v11-golden/    — golden hour (5 cameras)"
echo "  renders/v11-newcams/   — new angles (4 cameras)"
echo "  renders/v11-bluehour/  — blue hour (2 cameras)"
