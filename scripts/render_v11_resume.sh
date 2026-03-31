#!/bin/bash
# Resume v11 renders — one camera per Blender invocation to avoid GPU memory crashes.
# Skips cameras that already have output files.
#
# Usage: nohup bash scripts/render_v11_resume.sh > renders/v11_resume.log 2>&1 &

set -e
cd ~/Projects/sponic-garden-3d

BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"
SCRIPT="scripts/build_v11_rapid.py"
RENDER_DIR="renders/v11"

echo "============================================================"
echo "  v11 RESUME — one camera at a time"
echo "  Started: $(date)"
echo "============================================================"

# Camera list
CAMERAS="CAM_hero CAM_pool_spa CAM_entrance CAM_greenhouse_detail CAM_firepit_evening CAM_coffee_bar CAM_spa_detail"

for CAM in $CAMERAS; do
    OUTFILE="$RENDER_DIR/v11_${CAM}.png"
    if [ -f "$OUTFILE" ]; then
        echo "  SKIP: $CAM (already exists)"
        continue
    fi

    echo ""
    echo "============================================================"
    echo "  Rendering $CAM — $(date)"
    echo "============================================================"

    # Create a temporary Python script that builds scene + renders single camera
    cat > /tmp/render_single_cam.py << PYEOF
import sys
sys.stdout.reconfigure(line_buffering=True)

# Execute the full build script first
exec(open("scripts/build_v11_rapid.py".replace("build_v11_rapid", "build_v11_single")).read())
PYEOF

    # Actually, simpler: modify the main script to render just one camera
    # We'll use an env var to select the camera
    export RENDER_CAM="$CAM"

    PYTHONUNBUFFERED=1 $BLENDER --background --python scripts/build_v11_single_cam.py 2>&1

    if [ -f "$OUTFILE" ]; then
        echo "  SUCCESS: $CAM — $(ls -lh $OUTFILE | awk '{print $5}')"
    else
        echo "  FAILED: $CAM"
    fi
done

echo ""
echo "============================================================"
echo "  v11 RESUME COMPLETE — $(date)"
echo "============================================================"
echo "  Renders: $(ls -1 $RENDER_DIR/*.png 2>/dev/null | wc -l) files"
