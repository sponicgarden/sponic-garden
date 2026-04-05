#!/bin/bash
# retranslate-opus.sh — Batch re-translate all PL strings using Claude CLI (Opus 4.6)
# Uses the local Claude Code subscription — no API key needed.
#
# Usage: bash scripts/retranslate-opus.sh [--dry-run]
#
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
unset CLAUDECODE  # Allow nested claude invocation

MODEL="claude-opus-4-6"
SUPABASE_MGMT="sbp_3e69f8663424f038e25a294924a011d6754d2db5"
SUPABASE_PROJECT="aphrrfprbixmhissnjfn"
SUPABASE_URL="https://aphrrfprbixmhissnjfn.supabase.co"
DRY_RUN="${1:-}"
BATCH_DIR="/tmp/sg_translate_batches"
RESULTS_DIR="/tmp/sg_translate_results"

mkdir -p "$BATCH_DIR" "$RESULTS_DIR"

echo "🌿 Sponic Gardens — Batch Re-Translation via Claude CLI"
echo "   Model: $MODEL"
echo "   $(date)"
echo "──────────────────────────────────────────"

# 1. Get service role key for upserts
SERVICE_KEY=$(curl -s "https://api.supabase.com/v1/projects/$SUPABASE_PROJECT/api-keys" \
  -H "Authorization: Bearer $SUPABASE_MGMT" | python3 -c "
import json, sys
for k in json.load(sys.stdin):
    if k['name'] == 'service_role': print(k['api_key'])
")

# 2. Fetch all English source translations
echo "  Fetching English source keys..."
curl -s -X POST "https://api.supabase.com/v1/projects/$SUPABASE_PROJECT/database/query" \
  -H "Authorization: Bearer $SUPABASE_MGMT" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT key, value FROM translations WHERE lang = '\''en'\'' AND is_source = true AND value IS NOT NULL ORDER BY key;"}' > "$BATCH_DIR/all_en.json"

TOTAL=$(python3 -c "import json; print(len(json.load(open('$BATCH_DIR/all_en.json'))))")
echo "  Found $TOTAL English source keys"

# 3. Split into batches of 15 (smaller for reliable Claude CLI output)
python3 -c "
import json
rows = json.load(open('$BATCH_DIR/all_en.json'))
bs = 15
for i in range(0, len(rows), bs):
    batch = {r['key']: r['value'] for r in rows[i:i+bs]}
    json.dump(batch, open(f'$BATCH_DIR/batch_{i//bs:03d}.json', 'w'), ensure_ascii=False)
print(f'Created {(len(rows) + bs - 1) // bs} batches')
"

BATCH_COUNT=$(ls "$BATCH_DIR"/batch_*.json 2>/dev/null | wc -l | tr -d ' ')
echo "  $BATCH_COUNT batches of ~15 keys"

if [[ "$DRY_RUN" == "--dry-run" ]]; then
    echo "  [dry-run] Would translate $TOTAL keys in $BATCH_COUNT batches"
    exit 0
fi

# 4. Translate each batch via Claude CLI
TRANSLATED=0
FAILED=0

SYSTEM_PROMPT='You are a professional translator. Sponic Garden is a wellness destination venue in Warsaw, Poland.

Translate all JSON values from English to Polish. Output ONLY valid JSON — no markdown, no code fences, no explanation.

Rules:
- Preserve emoji, HTML tags, HTML entities (&nbsp; &mdash; etc.), punctuation exactly
- Keep proper nouns unchanged: Sponic Gardens, Sponic Garden, Warsaw, MOST, SGGW, URK, Patent Center, Gemini, Blender, Python, FIG., Sonic Vision
- Use natural, fluent Polish — not word-for-word
- For patent/legal text, use formal Polish patent language
- Short UI strings: translate appropriately for buttons/labels'

for BATCH_FILE in "$BATCH_DIR"/batch_*.json; do
    BATCH_NUM=$(basename "$BATCH_FILE" .json | sed 's/batch_//')
    RESULT_FILE="$RESULTS_DIR/result_${BATCH_NUM}.json"

    # Skip if already translated
    if [[ -f "$RESULT_FILE" ]]; then
        COUNT=$(python3 -c "import json; print(len(json.load(open('$RESULT_FILE'))))" 2>/dev/null || echo 0)
        if [[ "$COUNT" -gt 0 ]]; then
            TRANSLATED=$((TRANSLATED + COUNT))
            printf "\r  Batch %s/%s: %d translated (cached)" "$((10#$BATCH_NUM + 1))" "$BATCH_COUNT" "$TRANSLATED"
            continue
        fi
    fi

    INPUT=$(cat "$BATCH_FILE")

    # Call Claude CLI
    OUTPUT=$(claude -p --model "$MODEL" --verbose --output-format stream-json \
        "$SYSTEM_PROMPT

Input JSON:
$INPUT" 2>&1 | grep '"type":"assistant"' | python3 -c "
import json, sys, re
for line in sys.stdin:
    try:
        d = json.loads(line.strip())
        for c in d.get('message', {}).get('content', []):
            if c.get('type') == 'text':
                text = c['text']
                # Strip markdown code fences if present
                text = re.sub(r'^\`\`\`json?\s*', '', text)
                text = re.sub(r'\s*\`\`\`$', '', text)
                m = re.search(r'\{[\s\S]*\}', text)
                if m:
                    parsed = json.loads(m.group())
                    print(json.dumps(parsed, ensure_ascii=False))
    except: pass
" 2>/dev/null | tail -1)

    if [[ -z "$OUTPUT" ]]; then
        echo ""
        echo "  ❌ Batch $((10#$BATCH_NUM + 1)) failed — no JSON output"
        BATCH_KEYS=$(python3 -c "import json; print(len(json.load(open('$BATCH_FILE'))))")
        FAILED=$((FAILED + BATCH_KEYS))
        continue
    fi

    echo "$OUTPUT" > "$RESULT_FILE"
    COUNT=$(python3 -c "import json; print(len(json.load(open('$RESULT_FILE'))))" 2>/dev/null || echo 0)
    TRANSLATED=$((TRANSLATED + COUNT))

    printf "\r  Batch %s/%s: %d translated, %d failed" "$((10#$BATCH_NUM + 1))" "$BATCH_COUNT" "$TRANSLATED" "$FAILED"

    # Upsert this batch to Supabase immediately
    python3 -c "
import json, sys
result = json.load(open('$RESULT_FILE'))
rows = []
for key, value in result.items():
    if value and isinstance(value, str):
        rows.append({
            'key': key,
            'lang': 'pl',
            'value': value.strip(),
            'is_source': False,
            'pending': False,
            'translated_by': 'llm:$MODEL',
            'review_status': 'unreviewed',
            'updated_at': '$(date -u +%Y-%m-%dT%H:%M:%SZ)'
        })
print(json.dumps(rows))
" | curl -s -X POST "$SUPABASE_URL/rest/v1/translations?on_conflict=key,lang" \
    -H "apikey: $SERVICE_KEY" \
    -H "Authorization: Bearer $SERVICE_KEY" \
    -H "Content-Type: application/json" \
    -H "Prefer: resolution=merge-duplicates,return=minimal" \
    -d @- > /dev/null

    # Small delay between batches
    sleep 2
done

echo ""
echo "──────────────────────────────────────────"
echo "  ✅ Done: $TRANSLATED translated, $FAILED failed"
echo "  Engine tag: llm:$MODEL"
echo "  Results saved in: $RESULTS_DIR/"
