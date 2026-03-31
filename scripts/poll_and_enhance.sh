#!/bin/bash
# Poll Alpuca for new v11 renders, pull locally, and run Gemini enhancement.
# Usage: bash scripts/poll_and_enhance.sh

set -e
cd "$(dirname "$0")/.."

REMOTE="paca@192.168.1.200"
REMOTE_DIR="~/Projects/sponic-garden-3d/renders"
LOCAL_DIR="design/renders"
ENHANCE_SCRIPT="scripts/gemini_enhance_renders.py"

echo "============================================================"
echo "  POLL & ENHANCE — pulling renders from Alpuca"
echo "  Started: $(date)"
echo "============================================================"

SETS="v11 v11-golden v11-bluehour v11-newcams v11-passes"

while true; do
    NEW_FILES=0

    for SET in $SETS; do
        REMOTE_SET="$REMOTE_DIR/$SET"
        LOCAL_SET="$LOCAL_DIR/$SET"
        mkdir -p "$LOCAL_SET"

        # Get list of remote files
        REMOTE_FILES=$(ssh $REMOTE "ls $REMOTE_SET/*.png 2>/dev/null" || true)
        if [ -z "$REMOTE_FILES" ]; then
            continue
        fi

        for RF in $REMOTE_FILES; do
            BASENAME=$(basename "$RF")
            LOCAL_FILE="$LOCAL_SET/$BASENAME"
            if [ ! -f "$LOCAL_FILE" ]; then
                echo "  NEW: $SET/$BASENAME — pulling..."
                scp "$REMOTE:$RF" "$LOCAL_FILE"
                NEW_FILES=$((NEW_FILES + 1))
            fi
        done
    done

    if [ $NEW_FILES -gt 0 ]; then
        echo ""
        echo "  Pulled $NEW_FILES new files. Running Gemini enhancement..."
        python3 "$ENHANCE_SCRIPT" --all 2>&1
        echo ""
    fi

    # Check if Blender is still running on Alpuca
    if ! ssh $REMOTE 'pgrep -f Blender > /dev/null 2>&1'; then
        echo ""
        echo "  Blender no longer running on Alpuca."
        echo "  Final pull..."
        # One last pull
        for SET in $SETS; do
            REMOTE_SET="$REMOTE_DIR/$SET"
            LOCAL_SET="$LOCAL_DIR/$SET"
            mkdir -p "$LOCAL_SET"
            scp "$REMOTE:$REMOTE_SET/*.png" "$LOCAL_SET/" 2>/dev/null || true
        done
        echo "  Running final enhancement..."
        python3 "$ENHANCE_SCRIPT" --all 2>&1
        break
    fi

    echo "  $(date) — waiting 5 min..."
    sleep 300
done

echo ""
echo "============================================================"
echo "  POLL & ENHANCE COMPLETE — $(date)"
echo "============================================================"
echo "  Local renders:"
for SET in $SETS; do
    COUNT=$(ls -1 "$LOCAL_DIR/$SET"/*.png 2>/dev/null | wc -l)
    echo "    $SET: $COUNT files"
done
echo "  Enhanced:"
for SET in v11-photo v11-golden-photo v11-bluehour-photo v11-newcams-photo; do
    COUNT=$(ls -1 "$LOCAL_DIR/$SET"/*.png 2>/dev/null | wc -l)
    echo "    $SET: $COUNT files"
done
