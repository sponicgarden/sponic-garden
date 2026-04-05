#!/usr/bin/env node
/**
 * scripts/retranslate-opus.js
 *
 * One-time batch re-translation of all Polish strings using a specified model.
 * Reads English source rows from Supabase, translates in batches of 10 keys
 * per API call, upserts results with proper engine tagging.
 *
 * Usage:
 *   ANTHROPIC_API_KEY=sk-ant-... node scripts/retranslate-opus.js
 *   ANTHROPIC_API_KEY=sk-ant-... node scripts/retranslate-opus.js --model claude-sonnet-4-6
 *   ANTHROPIC_API_KEY=sk-ant-... node scripts/retranslate-opus.js --dry-run
 *
 * Requires:
 *   ANTHROPIC_API_KEY env var
 *   SUPABASE_SERVICE_KEY env var (or uses mgmt API fallback)
 */

const SUPABASE_URL = 'https://aphrrfprbixmhissnjfn.supabase.co';
const SUPABASE_MGMT_TOKEN = 'sbp_3e69f8663424f038e25a294924a011d6754d2db5';
const ANTHROPIC_KEY = process.env.ANTHROPIC_API_KEY;
const MODEL = process.argv.includes('--model')
  ? process.argv[process.argv.indexOf('--model') + 1]
  : 'claude-opus-4-6';
const DRY_RUN = process.argv.includes('--dry-run');
const TARGET_LANG = 'pl';
const BATCH_SIZE = 10; // keys per Claude API call
const DELAY_MS = 1000; // delay between API calls to avoid rate limits

if (!ANTHROPIC_KEY) {
  console.error('❌ ANTHROPIC_API_KEY env var required');
  process.exit(1);
}

async function sbQuery(sql) {
  const res = await fetch(
    `https://api.supabase.com/v1/projects/aphrrfprbixmhissnjfn/database/query`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${SUPABASE_MGMT_TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query: sql }),
    }
  );
  if (!res.ok) throw new Error(`Supabase query failed: ${res.status} ${await res.text()}`);
  return res.json();
}

async function sbUpsert(rows) {
  // Get service key for REST API upsert
  const keysRes = await fetch(
    'https://api.supabase.com/v1/projects/aphrrfprbixmhissnjfn/api-keys',
    { headers: { 'Authorization': `Bearer ${SUPABASE_MGMT_TOKEN}` } }
  );
  const keys = await keysRes.json();
  const serviceKey = keys.find(k => k.name === 'service_role')?.api_key;
  if (!serviceKey) throw new Error('Could not get service role key');

  const res = await fetch(`${SUPABASE_URL}/rest/v1/translations`, {
    method: 'POST',
    headers: {
      'apikey': serviceKey,
      'Authorization': `Bearer ${serviceKey}`,
      'Content-Type': 'application/json',
      'Prefer': 'resolution=merge-duplicates,return=minimal',
    },
    body: JSON.stringify(rows),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Upsert failed: ${res.status} ${err}`);
  }
}

async function translateBatch(entries, model) {
  const langNames = { en: 'English', pl: 'Polish' };
  const inputJson = Object.fromEntries(entries);

  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key': ANTHROPIC_KEY,
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      model,
      max_tokens: 8192,
      system: `You are a professional translator. Sponic Garden is a wellness destination venue in Warsaw, Poland. Translate maintaining a professional, warm, botanical brand voice.

Translate from English to Polish.
You will receive a JSON object where keys are translation identifiers and values are English text.
Return a JSON object with the SAME keys but Polish translated values.
Rules:
- Return ONLY valid JSON, nothing else
- Preserve any emoji, HTML tags, HTML entities (&nbsp; &mdash; &amp; etc.), punctuation
- Keep proper nouns unchanged: Sponic Gardens, Sponic Garden, Warsaw, MOST, SGGW, URK, Patent Center, Gemini, Blender, Python, FIG., Sonic Vision
- Short UI strings should be translated appropriately for Polish buttons/labels
- Use natural, fluent Polish — not word-for-word translation
- For patent/legal text, use formal Polish patent language conventions`,
      messages: [{ role: 'user', content: JSON.stringify(inputJson) }],
    }),
  });

  if (!res.ok) {
    const errBody = await res.text();
    throw new Error(`Claude API ${res.status}: ${errBody.slice(0, 300)}`);
  }

  const data = await res.json();
  const rawText = data.content?.[0]?.text?.trim() || '{}';
  const jsonMatch = rawText.match(/\{[\s\S]*\}/);
  if (!jsonMatch) throw new Error('No JSON in response');
  return JSON.parse(jsonMatch[0]);
}

async function main() {
  console.log(`🌿 Sponic Gardens — Batch Re-Translation`);
  console.log(`   Model: ${MODEL}`);
  console.log(`   Target: ${TARGET_LANG}`);
  console.log(`   Dry run: ${DRY_RUN}`);
  console.log('─'.repeat(50));

  // 1. Fetch all English source translations
  const rows = await sbQuery(
    `SELECT key, value FROM translations WHERE lang = 'en' AND is_source = true AND value IS NOT NULL ORDER BY key`
  );
  console.log(`\n  Found ${rows.length} English source keys`);

  if (DRY_RUN) {
    console.log(`\n  [dry-run] Would translate ${rows.length} keys to ${TARGET_LANG} via ${MODEL}`);
    console.log(`  [dry-run] Estimated ${Math.ceil(rows.length / BATCH_SIZE)} API calls`);
    return;
  }

  // 2. Translate in batches
  const entries = rows.map(r => [r.key, r.value]);
  let translated = 0;
  let failed = 0;
  const allUpserts = [];

  for (let i = 0; i < entries.length; i += BATCH_SIZE) {
    const batch = entries.slice(i, i + BATCH_SIZE);
    const batchNum = Math.floor(i / BATCH_SIZE) + 1;
    const totalBatches = Math.ceil(entries.length / BATCH_SIZE);

    try {
      const result = await translateBatch(batch, MODEL);

      Object.entries(result).forEach(([key, value]) => {
        if (value && typeof value === 'string') {
          allUpserts.push({
            key,
            lang: TARGET_LANG,
            value: value.trim(),
            is_source: false,
            pending: false,
            translated_by: `llm:${MODEL}`,
            review_status: 'unreviewed',
            updated_at: new Date().toISOString(),
          });
          translated++;
        }
      });

      process.stdout.write(`\r  Batch ${batchNum}/${totalBatches}: ${translated} translated, ${failed} failed`);

      // Upsert every 100 translations to avoid losing work
      if (allUpserts.length >= 100) {
        await sbUpsert(allUpserts.splice(0));
        process.stdout.write(` [saved]`);
      }

      // Rate limit delay
      if (i + BATCH_SIZE < entries.length) {
        await new Promise(r => setTimeout(r, DELAY_MS));
      }
    } catch (e) {
      console.error(`\n  ❌ Batch ${batchNum} failed: ${e.message}`);
      failed += batch.length;

      if (e.message.includes('429')) {
        console.log('  ⏳ Rate limited — waiting 30s...');
        await new Promise(r => setTimeout(r, 30000));
        i -= BATCH_SIZE; // retry
        continue;
      }
    }
  }

  // 3. Final upsert
  if (allUpserts.length > 0) {
    await sbUpsert(allUpserts);
  }

  console.log(`\n\n  ✅ Done: ${translated} translated, ${failed} failed`);
  console.log(`  Engine tag: llm:${MODEL}`);
}

main().catch(e => { console.error(e); process.exit(1); });
