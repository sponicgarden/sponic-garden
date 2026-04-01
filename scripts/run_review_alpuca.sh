#!/bin/bash
# Machine B (Alpuca): Blue hour + New cameras variants
# Run this on Alpuca (Mac mini M4) via SSH
# Estimated: ~6 cameras × 3 variants × 20s = ~6 min (bluehour 2 + newcams 4)
# With 5 variants: ~30 renders × 20s = ~10 min
#
# Since Alpuca has fewer renders, after finishing B it also does a second pass
# of the hero angles (daylight+golden hero variants) with higher variant count.
#
# Usage:
#   ssh paca@192.168.1.200
#   cd ~/sponic-garden && ./scripts/run_review_alpuca.sh
#   # Or remote:
#   ssh paca@192.168.1.200 'cd ~/sponic-garden && nohup ./scripts/run_review_alpuca.sh 5 > /tmp/enhance_alpuca.log 2>&1 &'

set -euo pipefail

VARIANTS="${1:-3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================"
echo "  Machine B (Alpuca) — Review Enhancement"
echo "  Sets: bluehour + newcams"
echo "  Variants: $VARIANTS"
echo "  Started: $(date)"
echo "============================================"

# Ensure API key is available
if [ ! -f /tmp/.gemini_key_sg ]; then
    echo "ERROR: API key not found at /tmp/.gemini_key_sg"
    echo "Set it manually: echo 'YOUR_KEY' > /tmp/.gemini_key_sg"
    exit 1
fi

# Ensure google-genai is installed
pip3 install --quiet google-genai 2>/dev/null || true

cd "$PROJECT_DIR"
python3 scripts/enhance_v11_review.py --machine=B --variants="$VARIANTS"

echo ""
echo "============================================"
echo "  Machine B COMPLETE — $(date)"
echo "  Review page: design/renders/v11-review/review.html"
echo "============================================"
