/**
 * shared/i18n.js — Sponic Gardens i18n runtime
 *
 * Fetches translations from Supabase, swaps [data-i18n] element content,
 * handles attribute translations, and caches in localStorage (5-min TTL
 * matching the cron interval so content stays fresh).
 *
 * Usage: <script type="module" src="/shared/i18n.js"></script>
 * The module self-initialises on load.
 *
 * Exports:
 *   setLang(code)  — switch language and re-translate page
 *   getLang()      — get active language code
 *   t(key)         — get a translation string programmatically
 */

const SUPABASE_URL  = 'https://aphrrfprbixmhissnjfn.supabase.co';
const SUPABASE_ANON = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFwaHJyZnByYml4bWhpc3NuamZuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk5MzA0MjUsImV4cCI6MjA4NTUwNjQyNX0.yYkdQIq97GQgxK7yT2OQEPi5Tt-a7gM45aF8xjSD6wk';
const CACHE_KEY     = 'sg_i18n_cache';
const CACHE_TTL_MS  = 5 * 60 * 1000; // 5 minutes — matches cron interval
const LANG_KEY      = 'sg_lang';

// ── In-memory state ──────────────────────────────────────────────────────────
let translations = {};  // { 'hero.title': { en: '...', pl: '...' } }
let languages    = [];  // [{ code, name, flag, is_base }]
let activeLang   = 'en';

// ── Public API ───────────────────────────────────────────────────────────────
export function getLang() { return activeLang; }

export function t(key) {
  const row = translations[key];
  if (!row) return key;
  return row[activeLang] || row['en'] || key;
}

export async function setLang(code) {
  activeLang = code;
  localStorage.setItem(LANG_KEY, code);
  document.documentElement.lang = code;
  applyTranslations();
  document.dispatchEvent(new CustomEvent('sg:langchange', { detail: { lang: code } }));
}

// ── Initialisation ───────────────────────────────────────────────────────────
async function init() {
  // 1. Determine language: localStorage → geo-detect → default
  activeLang = await resolveLanguage();
  document.documentElement.lang = activeLang;

  // 2. Load translations (cache-first)
  await loadTranslations();

  // 3. Apply to DOM
  applyTranslations();

  // 4. Expose on window for language-switcher and other scripts
  window.__sg_i18n = { getLang, setLang, t, languages };
}

async function resolveLanguage() {
  // Explicit user preference wins
  const stored = localStorage.getItem(LANG_KEY);
  if (stored) return stored;

  // Cloudflare CF-IPCountry (available when site is served via Cloudflare Workers/Pages)
  // Falls back to ip geolocation API if header not available
  try {
    const cfCountry = document.querySelector('meta[name="cf-country"]')?.content;
    if (cfCountry === 'PL') return 'pl';

    // Lightweight IP lookup — no browser permission required
    const geo = await fetch('https://ipapi.co/json/', { signal: AbortSignal.timeout(2000) })
      .then(r => r.json()).catch(() => null);
    if (geo?.country_code === 'PL') return 'pl';
  } catch {}

  return 'en';
}

// Paginate through PostgREST results (server max-rows cap is typically 1000)
async function fetchAllRows(baseUrl) {
  const PAGE = 1000;
  const all = [];
  let offset = 0;
  while (true) {
    const res = await fetch(`${baseUrl}&limit=${PAGE}&offset=${offset}`, {
      headers: { 'apikey': SUPABASE_ANON, 'Authorization': `Bearer ${SUPABASE_ANON}` }
    });
    if (!res.ok) break;
    const batch = await res.json();
    all.push(...batch);
    if (batch.length < PAGE) break;
    offset += PAGE;
  }
  return all;
}

async function loadTranslations() {
  // Check cache
  try {
    const cached = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null');
    if (cached && Date.now() - cached.ts < CACHE_TTL_MS) {
      translations = cached.data;
      languages    = cached.languages || [];
      return;
    }
  } catch {}

  // Fetch from Supabase (public anon read)
  try {
    // Fetch languages and all translation rows (paginated — server max-rows = 1000)
    const [rows, lRes] = await Promise.all([
      fetchAllRows(`${SUPABASE_URL}/rest/v1/translations?select=key,lang,value&order=key`),
      fetch(`${SUPABASE_URL}/rest/v1/languages?select=code,name,flag,is_base&enabled=eq.true&order=sort_order`, {
        headers: { 'apikey': SUPABASE_ANON, 'Authorization': `Bearer ${SUPABASE_ANON}` }
      }),
    ]);

    languages   = lRes.ok  ? await lRes.json()  : [];

    // Reshape: { key: { en: '...', pl: '...' } }
    translations = {};
    rows.forEach(({ key, lang, value }) => {
      if (!translations[key]) translations[key] = {};
      if (value) translations[key][lang] = value;
    });

    // Cache
    localStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), data: translations, languages }));
  } catch (e) {
    console.warn('[i18n] Failed to load translations:', e);
  }
}

function applyTranslations() {
  const baseLang = languages.find(l => l.is_base)?.code || 'en';
  const isBase = activeLang === baseLang;

  // [data-i18n="key"] — replace textContent
  document.querySelectorAll('[data-i18n]').forEach(el => {
    // Save original English text on first encounter
    if (!('i18nOriginal' in el.dataset)) el.dataset.i18nOriginal = el.textContent;
    if (isBase) { el.textContent = el.dataset.i18nOriginal; return; }
    const val = t(el.dataset.i18n);
    if (val && val !== el.dataset.i18n) el.textContent = val;
  });

  // [data-i18n-html="key"] — replace innerHTML (for keys with markup)
  document.querySelectorAll('[data-i18n-html]').forEach(el => {
    if (!('i18nOriginalHtml' in el.dataset)) el.dataset.i18nOriginalHtml = el.innerHTML;
    if (isBase) { el.innerHTML = el.dataset.i18nOriginalHtml; return; }
    const val = t(el.dataset.i18nHtml);
    if (val && val !== el.dataset.i18nHtml) el.innerHTML = val;
  });

  // [data-i18n-content="key"] — replace content attribute (meta tags)
  document.querySelectorAll('[data-i18n-content]').forEach(el => {
    if (!('i18nOriginalContent' in el.dataset)) el.dataset.i18nOriginalContent = el.getAttribute('content') || '';
    if (isBase) { el.setAttribute('content', el.dataset.i18nOriginalContent); return; }
    const val = t(el.dataset.i18nContent);
    if (val && val !== el.dataset.i18nContent) el.setAttribute('content', val);
  });

  // [data-i18n-placeholder="key"] — replace placeholder attribute
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    if (!('i18nOriginalPlaceholder' in el.dataset)) el.dataset.i18nOriginalPlaceholder = el.getAttribute('placeholder') || '';
    if (isBase) { el.setAttribute('placeholder', el.dataset.i18nOriginalPlaceholder); return; }
    const val = t(el.dataset.i18nPlaceholder);
    if (val && val !== el.dataset.i18nPlaceholder) el.setAttribute('placeholder', val);
  });

  // [data-i18n-title="key"] — replace title attribute (tooltips)
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    if (!('i18nOriginalTitle' in el.dataset)) el.dataset.i18nOriginalTitle = el.getAttribute('title') || '';
    if (isBase) { el.setAttribute('title', el.dataset.i18nOriginalTitle); return; }
    const val = t(el.dataset.i18nTitle);
    if (val && val !== el.dataset.i18nTitle) el.setAttribute('title', val);
  });

  // Update <html lang>
  document.documentElement.lang = activeLang;
}

// Self-initialise
init();
