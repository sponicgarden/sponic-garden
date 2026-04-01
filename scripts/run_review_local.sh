#!/bin/bash
# Machine A (local): Daylight + Golden hour variants
# Run this on your local Mac
# Estimated: ~13 cameras × 3 variants × 20s = ~13 min (daylight 8 + golden 5)
# With 5 variants: ~65 renders × 20s = ~22 min
#
# Usage:
#   ./scripts/run_review_local.sh          # 3 variants (default)
#   ./scripts/run_review_local.sh 5        # 5 variants
#   nohup ./scripts/run_review_local.sh 5 > /tmp/enhance_local.log 2>&1 &

set -euo pipefail

VARIANTS="${1:-3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================"
echo "  Machine A (Local) — Review Enhancement"
echo "  Sets: daylight + golden"
echo "  Variants: $VARIANTS"
echo "  Started: $(date)"
echo "============================================"

# Ensure API key is available
if [ ! -f /tmp/.gemini_key_sg ]; then
    echo "Setting up API key from Bitwarden..."
    export BW_SESSION=$(~/bin/bw-unlock)
    bw get password "Google Gemini — SponicGardens (USE THIS)" > /tmp/.gemini_key_sg
    echo "API key saved to /tmp/.gemini_key_sg"
fi

# Ensure google-genai is installed
pip3 install --quiet google-genai 2>/dev/null || true

cd "$PROJECT_DIR"
python3 scripts/enhance_v11_review.py --machine=A --variants="$VARIANTS"

echo ""
echo "============================================"
echo "  Machine A COMPLETE — $(date)"
echo "  Review page: design/renders/v11-review/review.html"
echo "============================================"
