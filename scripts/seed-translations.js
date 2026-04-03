#!/usr/bin/env node
/**
 * scripts/seed-translations.js
 *
 * Extracts all data-i18n keys + English text from HTML files,
 * upserts them to Supabase, then auto-translates pending languages
 * via Claude Haiku (using the config table for model/context).
 *
 * Usage:
 *   node scripts/seed-translations.js              # extract + seed EN only
 *   node scripts/seed-translations.js --translate  # also translate to all other langs
 *   node scripts/seed-translations.js --dry-run    # print what would be seeded
 *
 * Requires:
 *   SUPABASE_SERVICE_KEY env var  (or pass via --key flag)
 *   ANTHROPIC_API_KEY env var     (only needed with --translate)
 */

import { readFileSync, readdirSync, statSync } from 'fs';
import { join, relative } from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');

const SUPABASE_URL  = 'https://aphrrfprbixmhissnjfn.supabase.co';
const SUPABASE_KEY  = process.env.SUPABASE_SERVICE_KEY;
const ANTHROPIC_KEY = process.env.ANTHROPIC_API_KEY;

const DRY_RUN   = process.argv.includes('--dry-run');
const TRANSLATE = process.argv.includes('--translate');

// ── HTML files to scan ───────────────────────────────────────────────────────
const HTML_FILES = [
  'index.html',
  'charter.html',
  'bizmodel.html',
  'branding.html',
  'narrativesandbox.html',
  'patents/index.html',
  'patents/specification.html',
  'patents/filing-guide.html',
  'design/venue.html',
  'design/review.html',
  'design/design-process.html',
  'docs/spaces/index.html',
  'docs/spaces/MOSToffer.html',
];

// ── Extract keys from HTML ───────────────────────────────────────────────────
function extractKeysFromHtml(html) {
  const keys = {};

  // data-i18n="key">text content<  (captures innerText of element)
  const tagPattern = /data-i18n="([^"]+)"[^>]*>([^<]{1,500})</g;
  let m;
  while ((m = tagPattern.exec(html)) !== null) {
    const key = m[1];
    const text = m[2].trim().replace(/\s+/g, ' ');
    if (key && text && !text.startsWith('{') && text.length > 0) {
      keys[key] = text;
    }
  }

  // data-i18n-html="key">innerHTML<  (elements with inner HTML tags)
  const htmlTagPattern = /data-i18n-html="([^"]+)"[^>]*>([\s\S]{1,3000}?)<\/(?:p|div|span|strong|em|h[1-6]|td|li|section|blockquote)>/g;
  let hm;
  while ((hm = htmlTagPattern.exec(html)) !== null) {
    const key = hm[1];
    const innerHTML = hm[2].trim().replace(/\s+/g, ' ');
    if (key && innerHTML && !innerHTML.startsWith('{') && innerHTML.length > 0) {
      keys[key] = innerHTML;
    }
  }

  // data-i18n-content="key" content="value"  (meta tags)
  const metaPattern = /data-i18n-content="([^"]+)"[^>]*content="([^"]+)"/g;
  while ((m = metaPattern.exec(html)) !== null) {
    keys[m[1]] = m[2].trim();
  }

  // content="value" data-i18n-content="key"  (reversed attribute order)
  const metaPattern2 = /content="([^"]+)"[^>]*data-i18n-content="([^"]+)"/g;
  while ((m = metaPattern2.exec(html)) !== null) {
    keys[m[2]] = m[1].trim();
  }

  return keys;
}

async function main() {
  console.log('🌿 Sponic Gardens — Translation Seeder');
  console.log('─'.repeat(50));

  // ── 1. Scan HTML files ────────────────────────────────────────────────────
  const allKeys = {};
  let fileCount = 0;

  for (const file of HTML_FILES) {
    const path = join(ROOT, file);
    try {
      const html = readFileSync(path, 'utf-8');
      const keys = extractKeysFromHtml(html);
      const count = Object.keys(keys).length;
      if (count > 0) {
        Object.assign(allKeys, keys);
        fileCount++;
        console.log(`  ✓ ${file} — ${count} keys`);
      }
    } catch (e) {
      console.log(`  ⚠ ${file} — ${e.message}`);
    }
  }

  const keyCount = Object.keys(allKeys).length;
  console.log(`\n  Total: ${keyCount} unique keys across ${fileCount} files`);

  if (DRY_RUN) {
    console.log('\n[dry-run] Would upsert:');
    Object.entries(allKeys).slice(0, 20).forEach(([k, v]) => {
      console.log(`  ${k}: "${v.slice(0, 60)}${v.length > 60 ? '…' : ''}"`);
    });
    if (keyCount > 20) console.log(`  ... and ${keyCount - 20} more`);
    return;
  }

  if (!SUPABASE_KEY) {
    console.error('\n❌ SUPABASE_SERVICE_KEY env var required');
    process.exit(1);
  }

  // ── 2. Load active languages ──────────────────────────────────────────────
  const langsRes = await sbFetch('/rest/v1/languages?enabled=eq.true&order=sort_order');
  const langs = await langsRes.json();
  const baseLang = langs.find(l => l.is_base)?.code || 'en';
  const otherLangs = langs.filter(l => l.code !== baseLang).map(l => l.code);

  console.log(`\n  Languages: ${baseLang} (base) + [${otherLangs.join(', ')}]`);

  // ── 3. Build upsert payload ───────────────────────────────────────────────
  // For each key: upsert EN row as source, create pending rows for other langs
  const rows = [];
  for (const [key, enValue] of Object.entries(allKeys)) {
    rows.push({
      key, lang: baseLang,
      value: enValue,
      is_source: true, pending: false,
      updated_at: new Date().toISOString(),
    });
    for (const lang of otherLangs) {
      rows.push({
        key, lang,
        value: null,
        is_source: false, pending: true,
        updated_at: new Date().toISOString(),
      });
    }
  }

  // ── 4. Upsert in batches of 200 ───────────────────────────────────────────
  const BATCH = 200;
  console.log(`\n  Upserting ${rows.length} rows in batches of ${BATCH}…`);
  for (let i = 0; i < rows.length; i += BATCH) {
    const batch = rows.slice(i, i + BATCH);
    const res = await sbFetch('/rest/v1/translations', {
      method: 'POST',
      headers: { 'Prefer': 'resolution=merge-duplicates,return=minimal' },
      body: JSON.stringify(batch),
    });
    if (!res.ok) {
      const err = await res.text();
      console.error(`  ❌ Batch ${Math.floor(i/BATCH)+1} failed:`, err);
    } else {
      process.stdout.write('.');
    }
  }
  console.log(`\n  ✅ Seeded ${keyCount} keys (${rows.length} rows)`);

  // ── 5. Auto-translate if requested ───────────────────────────────────────
  if (!TRANSLATE) {
    console.log(`\n  💡 Run with --translate to auto-translate ${otherLangs.join('/')} via Claude`);
    console.log('     Or the 5-min cron will pick them up automatically once the Worker is deployed.');
    return;
  }

  if (!ANTHROPIC_KEY) {
    console.error('\n❌ ANTHROPIC_API_KEY required for --translate');
    process.exit(1);
  }

  // Load config for model/context
  const cfgRes = await sbFetch('/rest/v1/config?select=key,value');
  const cfgRows = await cfgRes.json();
  const cfg = Object.fromEntries(cfgRows.map(r => [r.key, r.value]));
  const model   = cfg['translation.model']   || 'claude-haiku-4-5-20251001';
  const context = cfg['translation.context'] || 'Sponic Garden wellness venue Warsaw';

  console.log(`\n  Translating ${keyCount} keys → [${otherLangs.join(', ')}] via ${model}…`);

  const langNames = { en: 'English', pl: 'Polish', de: 'German', ru: 'Russian', fr: 'French' };
  let done = 0;

  for (const targetLang of otherLangs) {
    const from = langNames[baseLang] || baseLang;
    const to   = langNames[targetLang] || targetLang;
    const upserts = [];

    // Batch translate in groups of 10 keys per Claude call
    const entries = Object.entries(allKeys);
    for (let i = 0; i < entries.length; i += 10) {
      const batch = entries.slice(i, i + 10);
      const inputJson = Object.fromEntries(batch);

      try {
        const res = await fetch('https://api.anthropic.com/v1/messages', {
          method: 'POST',
          headers: {
            'x-api-key': ANTHROPIC_KEY,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
          },
          body: JSON.stringify({
            model,
            max_tokens: 4096,
            system: `You are a professional translator. ${context}\n\nTranslate from ${from} to ${to}.\nYou will receive a JSON object where keys are translation identifiers and values are ${from} text.\nReturn a JSON object with the SAME keys but ${to} translated values.\nRules:\n- Return ONLY valid JSON, nothing else\n- Preserve any emoji, HTML tags, punctuation\n- Keep proper nouns (Sponic Gardens, Warsaw, MOST) unchanged\n- Short UI strings should be translated appropriately for buttons/labels`,
            messages: [{ role: 'user', content: JSON.stringify(inputJson) }],
          }),
        });

        if (!res.ok) { console.error('\n  API error', res.status); continue; }
        const data = await res.json();
        const rawText = data.content?.[0]?.text?.trim() || '{}';

        // Extract JSON from response (may be wrapped in ```json blocks)
        const jsonMatch = rawText.match(/\{[\s\S]*\}/);
        if (!jsonMatch) continue;
        const translated = JSON.parse(jsonMatch[0]);

        Object.entries(translated).forEach(([key, value]) => {
          if (value && typeof value === 'string') {
            upserts.push({
              key, lang: targetLang,
              value: value.trim(),
              is_source: false, pending: false,
              updated_at: new Date().toISOString(),
            });
          }
        });

        done += batch.length;
        process.stdout.write(`\r  ${targetLang}: ${done}/${keyCount} translated`);
      } catch (e) {
        console.error('\n  Translation batch error:', e.message);
      }
    }

    // Upsert translations
    for (let i = 0; i < upserts.length; i += BATCH) {
      const b = upserts.slice(i, i + BATCH);
      await sbFetch('/rest/v1/translations', {
        method: 'POST',
        headers: { 'Prefer': 'resolution=merge-duplicates,return=minimal' },
        body: JSON.stringify(b),
      });
    }
    console.log(`\n  ✅ ${targetLang}: ${upserts.length} strings translated`);
    done = 0;
  }

  console.log('\n🎉 Done! Translations are live in Supabase.');
}

function sbFetch(path, opts = {}) {
  return fetch(`${SUPABASE_URL}${path}`, {
    ...opts,
    headers: {
      'apikey': SUPABASE_KEY,
      'Authorization': `Bearer ${SUPABASE_KEY}`,
      'Content-Type': 'application/json',
      ...(opts.headers || {}),
    },
  });
}

main().catch(e => { console.error(e); process.exit(1); });
