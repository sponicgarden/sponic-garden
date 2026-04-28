#!/bin/bash
# optimize-images.sh — generate WebP siblings for every image in branding/.
#
# WebP cuts JPEG/PNG payloads by ~25–60% with imperceptible quality loss.
# This script is opt-in (run manually): we don't want CI to bloat the repo
# unprompted.
#
# Strategy:
#   - For every .jpg/.jpeg/.png in branding/, write `${name}.webp` next to it.
#   - Skip files whose .webp already exists and is newer than the source.
#   - Use cwebp -q 82 (sweet spot for photo/illustration mix).
#
# branding.html's <picture>/<source> markup picks up the .webp automatically;
# browsers without WebP support fall back to the original.
#
# Requires: cwebp  (brew install webp)
# Usage:    ./scripts/optimize-images.sh [--force] [--quality N]

set -euo pipefail

QUALITY=82
FORCE=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --force)   FORCE=true; shift ;;
    --quality) QUALITY="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,17p' "$0"; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if ! command -v cwebp >/dev/null 2>&1; then
  echo "ERROR: cwebp not found. Install with: brew install webp" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BRAND_DIR="$ROOT/branding"

[ -d "$BRAND_DIR" ] || { echo "ERROR: $BRAND_DIR not found" >&2; exit 1; }

count_total=0
count_skipped=0
count_converted=0
bytes_before=0
bytes_after=0

while IFS= read -r -d '' src; do
  count_total=$((count_total + 1))
  base="${src%.*}"
  dst="${base}.webp"

  if [ -f "$dst" ] && [ "$FORCE" != true ] && [ "$dst" -nt "$src" ]; then
    count_skipped=$((count_skipped + 1))
    continue
  fi

  before=$(stat -f%z "$src" 2>/dev/null || stat -c%s "$src")
  cwebp -quiet -q "$QUALITY" "$src" -o "$dst"
  after=$(stat -f%z "$dst" 2>/dev/null || stat -c%s "$dst")

  bytes_before=$((bytes_before + before))
  bytes_after=$((bytes_after + after))
  count_converted=$((count_converted + 1))

  pct=$(( (before - after) * 100 / before ))
  printf '  %3d%% smaller  %s\n' "$pct" "$(basename "$src")"
done < <(find "$BRAND_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \) -print0)

echo
echo "Total scanned:    $count_total"
echo "Already current:  $count_skipped"
echo "Newly converted:  $count_converted"
if [ "$bytes_before" -gt 0 ]; then
  saved_mb=$(awk -v b="$bytes_before" -v a="$bytes_after" 'BEGIN{printf "%.1f", (b-a)/1048576}')
  pct=$(( (bytes_before - bytes_after) * 100 / bytes_before ))
  echo "Bytes saved:      ${saved_mb} MB (${pct}%)"
fi
