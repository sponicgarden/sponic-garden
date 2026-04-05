/**
 * sponic-translate-cron — Cloudflare Worker
 *
 * Runs every 5 minutes (cron: every-5-min).
 * Reports pending translation counts. Does NOT call the Anthropic API.
 * Translations are done via Claude CLI on local machines using
 * scripts/retranslate-opus.sh.
 *
 * Required secrets (set via `wrangler secret put`):
 *   SUPABASE_SERVICE_KEY  — Supabase service role JWT
 *
 * Var (in wrangler.toml):
 *   SUPABASE_URL          — https://aphrrfprbixmhissnjfn.supabase.co
 */

export default {
  // HTTP handler (health check + status)
  async fetch(request, env) {
    const result = await getTranslationStatus(env);
    return Response.json(result);
  },

  // Scheduled cron handler — just logs status
  async scheduled(event, env, ctx) {
    const status = await getTranslationStatus(env);
    if (status.pending > 0) {
      console.log(`Translation status: ${status.pending} pending, ${status.total} total`);
    }
  },
};

async function getTranslationStatus(env) {
  const supabase = makeSupabase(env.SUPABASE_URL, env.SUPABASE_SERVICE_KEY);

  // Load config
  const cfg = await loadConfig(supabase);
  const model = cfg['translation.model'] || '(not set)';

  // Count pending translations
  const { data: pendingRows, error: fetchErr } = await supabase
    .from('translations')
    .select('key, lang, pending')
    .eq('pending', true)
    .limit(5000);

  if (fetchErr) return { error: 'Fetch failed: ' + fetchErr.message };

  const pending = pendingRows?.length || 0;

  // Count total and by engine
  const { data: allRows } = await supabase
    .from('translations')
    .select('lang, translated_by, pending')
    .limit(10000);

  const total = allRows?.length || 0;
  const engines = {};
  (allRows || []).forEach(row => {
    const eng = row.translated_by || '(untagged)';
    engines[eng] = (engines[eng] || 0) + 1;
  });

  // Per-language pending counts
  const pendingByLang = {};
  (pendingRows || []).forEach(row => {
    pendingByLang[row.lang] = (pendingByLang[row.lang] || 0) + 1;
  });

  return {
    status: pending === 0 ? 'synced' : 'pending',
    pending,
    total,
    pendingByLang,
    engines,
    model,
    message: pending === 0
      ? 'All translations synced'
      : `${pending} translations pending — run scripts/retranslate-opus.sh to translate`,
  };
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

  return {
    from(table) {
      let _select = '*';
      let _filters = [];
      let _limit = null;

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
      };

      return chain;
    },
  };
}
