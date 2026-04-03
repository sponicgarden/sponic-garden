/**
 * shared/language-switcher.js — Sponic Gardens language switcher
 *
 * Injects a prominent EN/PL pill into every page (top-right, after version badge).
 * - Shows flag + language name for each active language
 * - "Polski" label styled in brand red when Polish is active
 * - Auto-detects Poland via IP (no browser permission required)
 * - Persists preference in localStorage
 * - Works alongside i18n.js (listens for sg:langchange events)
 *
 * Usage: <script type="module" src="/shared/language-switcher.js"></script>
 */

const SUPABASE_URL  = 'https://aphrrfprbixmhissnjfn.supabase.co';
const SUPABASE_ANON = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFwaHJyZnByYml4bWhpc3NuamZuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk5MzA0MjUsImV4cCI6MjA4NTUwNjQyNX0.yYkdQIq97GQgxK7yT2OQEPi5Tt-a7gM45aF8xjSD6wk';

const LANG_KEY = 'sg_lang';

// Brand red matching Polish flag
const POLISH_RED = '#DC143C';

const SWITCHER_STYLES = `
  #sg-lang-switcher {
    position: fixed;
    top: 16px;
    right: 16px;
    z-index: 9000;
    display: inline-flex;
    align-items: center;
    background: rgba(255,255,255,0.92);
    border: 1px solid rgba(0,0,0,0.12);
    border-radius: 100px;
    padding: 4px 6px;
    gap: 2px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.10);
    backdrop-filter: blur(8px);
    font-family: 'DM Sans', -apple-system, sans-serif;
    font-size: 13px;
    user-select: none;
  }
  #sg-lang-switcher .sg-lang-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    border-radius: 100px;
    border: none;
    background: none;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    color: #4a6040;
    transition: background 0.15s, color 0.15s;
    white-space: nowrap;
  }
  #sg-lang-switcher .sg-lang-btn:hover {
    background: rgba(45,106,30,0.07);
  }
  #sg-lang-switcher .sg-lang-btn.active {
    background: rgba(45,106,30,0.10);
    color: #1a2412;
    font-weight: 600;
  }
  #sg-lang-switcher .sg-lang-btn.active.pl {
    color: ${POLISH_RED};
    background: rgba(220,20,60,0.07);
  }
  #sg-lang-switcher .sg-lang-flag {
    font-size: 15px;
    line-height: 1;
  }
  #sg-lang-switcher .sg-lang-sep {
    width: 1px;
    height: 16px;
    background: rgba(0,0,0,0.12);
    margin: 0 2px;
    flex-shrink: 0;
  }
  @media (max-width: 480px) {
    #sg-lang-switcher {
      top: 10px;
      right: 10px;
    }
    #sg-lang-switcher .sg-lang-btn span.sg-lang-name {
      display: none;
    }
  }
`;

async function init() {
  // Wait for i18n.js to expose __sg_i18n (it may load slightly later)
  await waitForI18n();

  const { getLang, setLang, languages } = window.__sg_i18n;
  const activeLangs = (languages || []).filter(l => l.enabled !== false);
  if (activeLangs.length < 2) return; // nothing to switch

  injectStyles();
  const switcher = buildSwitcher(activeLangs, getLang());
  document.body.appendChild(switcher);

  // Listen for external lang changes (e.g. from i18n.js init)
  document.addEventListener('sg:langchange', () => {
    updateActive(getLang());
  });

  updateActive(getLang());
}

function waitForI18n(maxMs = 3000) {
  return new Promise(resolve => {
    if (window.__sg_i18n) return resolve();
    const start = Date.now();
    const check = setInterval(() => {
      if (window.__sg_i18n || Date.now() - start > maxMs) {
        clearInterval(check);
        resolve();
      }
    }, 50);
  });
}

function injectStyles() {
  const style = document.createElement('style');
  style.textContent = SWITCHER_STYLES;
  document.head.appendChild(style);
}

function buildSwitcher(langs, currentLang) {
  const container = document.createElement('div');
  container.id = 'sg-lang-switcher';
  container.setAttribute('role', 'navigation');
  container.setAttribute('aria-label', 'Language selector');

  langs.forEach((lang, i) => {
    if (i > 0) {
      const sep = document.createElement('div');
      sep.className = 'sg-lang-sep';
      sep.setAttribute('aria-hidden', 'true');
      container.appendChild(sep);
    }

    const btn = document.createElement('button');
    btn.className = `sg-lang-btn ${lang.code}`;
    btn.dataset.code = lang.code;
    btn.setAttribute('aria-label', `Switch to ${lang.name}`);
    btn.innerHTML = `
      <span class="sg-lang-flag" aria-hidden="true">${lang.flag || ''}</span>
      <span class="sg-lang-name">${lang.name}</span>
    `;

    btn.addEventListener('click', () => {
      window.__sg_i18n.setLang(lang.code);
      updateActive(lang.code);
    });

    container.appendChild(btn);
  });

  return container;
}

function updateActive(lang) {
  document.querySelectorAll('#sg-lang-switcher .sg-lang-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.code === lang);
  });
}

// Self-init after DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
