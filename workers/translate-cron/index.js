/**
 * sponic-translate-cron — Cloudflare Worker
 *
 * Runs every 5 minutes (cron: every-5-min).
 * Reads pending translations from Supabase, translates via Claude Haiku,
 * writes results back. All settings loaded from the config table at runtime
 * — change model, prompt, or batch size in the DB without redeploying.
 *
 * Required secrets (set via `wrangler secret put`):
 *   SUPABASE_SERVICE_KEY  — Supabase service role JWT
 *   ANTHROPIC_API_KEY     — Anthropic API key (sk-ant-...)
 *
 * Var (in wrangler.toml):
 *   SUPABASE_URL          — https://aphrrfprbixmhissnjfn.supabase.co
 */

export default {
  // HTTP handler (for manual trigger / health check)
  async fetch(request, env) {
    if (request.method !== 'POST' && new URL(request.url).pathname !== '/run') {
      return new Response('sponic-translate-cron OK', { status: 200 });
    }
    const result = await runTranslations(env);
    return Response.json(result);
  },

  // Scheduled cron handler
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runTranslations(env));
  },
};

async function runTranslations(env) {
  const supabase = makeSupabase(env.SUPABASE_URL, env.SUPABASE_SERVICE_KEY);

  // ── 1. Load config from DB ────────────────────────────────────────────────
  const cfg = await loadConfig(supabase);
  const model      = cfg['translation.model']      || 'claude-haiku-4-5-20251001';
  const context    = cfg['translation.context']    || 'Translate for Sponic Garden wellness venue in Warsaw, Poland.';
  const batchSize  = parseInt(cfg['translation.batch_size'] || '20', 10);

  // ── 2. Fetch pending translation rows ────────────────────────────────────
  const { data: pendingRows, error: fetchErr } = await supabase
    .from('translations')
    .select('key, lang, pending, is_source, value')
    .eq('pending', true)
    .limit(batchSize * 5); // fetch more than batch to group properly

  if (fetchErr) throw new Error('Fetch pending failed: ' + fetchErr.message);
  if (!pendingRows || pendingRows.length === 0) {
    return { translated: 0, message: 'Nothing pending' };
  }

  // ── 3. Group by key, find source value for each ───────────────────────────
  // For each pending (key, lang), we need the source row's value
  const keys = [...new Set(pendingRows.map(r => r.key))].slice(0, batchSize);

  const { data: allRows } = await supabase
    .from('translations')
    .select('key, lang, value, is_source')
    .in('key', keys);

  // Map: key → { sourceLang, sourceValue, pendingLangs[] }
  const jobs = {};
  (allRows || []).forEach(row => {
    if (!jobs[row.key]) jobs[row.key] = { sourceLang: null, sourceValue: null, pendingLangs: [] };
    if (row.is_source && row.value) {
      jobs[row.key].sourceLang  = row.lang;
      jobs[row.key].sourceValue = row.value;
    }
  });
  pendingRows.forEach(row => {
    if (keys.includes(row.key) && jobs[row.key]) {
      if (!jobs[row.key].pendingLangs.includes(row.lang)) {
        jobs[row.key].pendingLangs.push(row.lang);
      }
    }
  });

  // ── 4. Translate and upsert ────────────────────────────────────────────────
  let translated = 0;
  const upserts = [];

  for (const [key, job] of Object.entries(jobs)) {
    if (!job.sourceValue || job.pendingLangs.length === 0) continue;

    for (const targetLang of job.pendingLangs) {
      if (targetLang === job.sourceLang) continue;

      const translatedText = await translateText({
        text:       job.sourceValue,
        sourceLang: job.sourceLang,
        targetLang,
        context,
        model,
        apiKey: env.ANTHROPIC_API_KEY,
      });

      if (translatedText) {
        upserts.push({
          key,
          lang:       targetLang,
          value:      translatedText,
          pending:    false,
          is_source:  false,
          updated_at: new Date().toISOString(),
        });
        translated++;
      }
    }
  }

  if (upserts.length > 0) {
    const { error: upsertErr } = await supabase
      .from('translations')
      .upsert(upserts, { onConflict: 'key,lang' });
    if (upsertErr) throw new Error('Upsert failed: ' + upsertErr.message);
  }

  return { translated, pending: pendingRows.length, message: `Translated ${translated} strings` };
}

async function translateText({ text, sourceLang, targetLang, context, model, apiKey }) {
  const langNames = { en: 'English', pl: 'Polish', de: 'German', ru: 'Russian', fr: 'French', es: 'Spanish', uk: 'Ukrainian' };
  const from = langNames[sourceLang] || sourceLang;
  const to   = langNames[targetLang] || targetLang;

  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key':         apiKey,
      'anthropic-version': '2023-06-01',
      'content-type':      'application/json',
    },
    body: JSON.stringify({
      model,
      max_tokens: 1024,
      system: `You are a professional translator. ${context}\n\nTranslate from ${from} to ${to}. Return ONLY the translated text — no explanations, no quotes, no extra formatting. Preserve any HTML tags, emoji, or punctuation exactly as they appear.`,
      messages: [{ role: 'user', content: text }],
    }),
  });

  if (!res.ok) {
    console.error('Claude API error', res.status, await res.text());
    return null;
  }

  const data = await res.json();
  return data.content?.[0]?.text?.trim() || null;
}

async function loadConfig(supabase) {
  const { data } = await supabase.from('config').select('key, value');
  const cfg = {};
  (data || []).forEach(row => {
    cfg[row.key] = typeof row.value === 'string' ? row.value : JSON.parse(JSON.stringify(row.value));
  });
  return cfg;
}

// Minimal Supabase REST client (no npm dependency needed in CF Workers)
function makeSupabase(url, serviceKey) {
  const headers = {
    'apikey':        serviceKey,
    'Authorization': `Bearer ${serviceKey}`,
    'Content-Type':  'application/json',
    'Prefer':        'return=representation',
  };

  function buildUrl(table, params = {}) {
    const u = new URL(`${url}/rest/v1/${table}`);
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) u.searchParams.set(k, v);
    }
    return u.toString();
  }

  return {
    from(table) {
      let _select = '*';
      let _filters = [];
      let _limit = null;
      let _in = null;

      const chain = {
        select(cols) { _select = cols; return chain; },
        eq(col, val) { _filters.push(`${col}=eq.${val}`); return chain; },
        in(col, vals) { _filters.push(`${col}=in.(${vals.map(v => `"${v}"`).join(',')})`); return chain; },
        limit(n) { _limit = n; return chain; },

        async then(resolve, reject) {
          try {
            const u = new URL(`${url}/rest/v1/${table}`);
            u.searchParams.set('select', _select);
            _filters.forEach(f => {
              const [col, rest] = f.split('=');
              u.searchParams.set(col, rest);
            });
            if (_limit) u.searchParams.set('limit', _limit);
            const res = await fetch(u.toString(), { headers });
            const data = await res.json();
            if (!res.ok) resolve({ data: null, error: data });
            else resolve({ data, error: null });
          } catch (e) { reject(e); }
        },

        async upsert(rows, opts = {}) {
          const u = new URL(`${url}/rest/v1/${table}`);
          if (opts.onConflict) u.searchParams.set('on_conflict', opts.onConflict);
          const res = await fetch(u.toString(), {
            method: 'POST',
            headers: { ...headers, 'Prefer': `resolution=merge-duplicates,return=minimal` },
            body: JSON.stringify(Array.isArray(rows) ? rows : [rows]),
          });
          if (!res.ok) {
            const err = await res.json().catch(() => ({ message: res.statusText }));
            return { data: null, error: err };
          }
          return { data: null, error: null };
        },
      };

      // Make chain thenable at any stage
      chain.upsert = chain.upsert.bind(chain);
      return chain;
    },
  };
}
