/**
 * Shared Navigation Bar — auto-injects a sticky top nav into every page.
 *
 * Style: Dark vine (#1a4d2e) with Fraunces wordmark + Sora tabs.
 * Homepage: wordmark image in nav, orchid logo stays in hero.
 * Other pages: wordmark image in nav (no orchid).
 *
 * Include as: <script type="module" src="/shared/nav.js"></script>
 */

/* ── config ────────────────────────────────────────────────────────── */
const TABS = [
  { label: 'Home', href: '/' },
  { label: 'Concept', href: '/charter.html' },
  { label: 'Design', href: '/design/venue.html' },
  { label: 'Business', href: '/bizmodel.html' },
  { label: 'Join', href: '/apply.html' },
];

const WORDMARK_SRC = '/branding/wordmark-white.png';

/* ── detect current page ──────────────────────────────────────────── */
function currentTab() {
  const path = location.pathname;
  // Home
  if (path === '/' || path === '/index.html' || path === '/en/index.html') return '/';
  // Design group
  if (path.startsWith('/design/') || path === '/physicaldesign.html') return '/design/venue.html';
  // Business group
  if (path === '/bizmodel.html' || path === '/branding.html') return '/bizmodel.html';
  // Concept group
  if (path === '/charter.html' || path === '/narrativesandbox.html') return '/charter.html';
  // Join group
  if (path === '/apply.html' || path === '/work-with-us.html') return '/apply.html';
  // Patents — no tab highlight
  if (path.startsWith('/patents/')) return null;
  return null;
}

function isHomepage() {
  const p = location.pathname;
  return p === '/' || p === '/index.html' || p === '/en/index.html';
}

/* ── inject styles (once) ─────────────────────────────────────────── */
function injectStyles() {
  if (document.getElementById('nav-styles')) return;
  const s = document.createElement('style');
  s.id = 'nav-styles';
  s.textContent = `
    /* ── nav bar ─────────────────────────── */
    .sg-nav {
      display: flex;
      align-items: center;
      padding: 0 2rem;
      height: 48px;
      background: #1a4d2e;
      border-bottom: 1px solid rgba(52,211,153,0.15);
      box-shadow: 0 1px 8px rgba(0,0,0,0.15);
      position: sticky;
      top: 0;
      z-index: 1000;
      font-family: 'Sora', 'DM Sans', sans-serif;
    }

    /* left: wordmark */
    .sg-nav__left {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex-shrink: 0;
    }
    .sg-nav__wordmark {
      height: 22px;
      width: auto;
      display: block;
      filter: brightness(0) invert(1);
      opacity: 0.92;
      transition: opacity 0.15s;
    }
    .sg-nav__wordmark:hover { opacity: 1; }

    /* center: tabs */
    .sg-nav__center {
      display: flex;
      align-items: center;
      gap: 0.15rem;
      margin: 0 auto;
    }
    .sg-nav__tab {
      font-family: 'Sora', 'DM Sans', sans-serif;
      font-size: 0.8rem;
      font-weight: 400;
      padding: 0.38rem 0.7rem;
      border-radius: 6px;
      text-decoration: none;
      color: rgba(232,240,228,0.65);
      transition: background 0.15s, color 0.15s;
      white-space: nowrap;
      position: relative;
      letter-spacing: -0.01em;
    }
    .sg-nav__tab:hover {
      background: rgba(255,255,255,0.08);
      color: #fff;
    }
    .sg-nav__tab--active {
      background: rgba(52,211,153,0.15);
      color: #34d399;
    }
    .sg-nav__tab--active::after {
      content: '';
      position: absolute;
      bottom: 2px;
      left: 50%;
      transform: translateX(-50%);
      width: 4px;
      height: 4px;
      border-radius: 50%;
      background: #34d399;
    }

    /* right: lang + sign in */
    .sg-nav__right {
      display: flex;
      align-items: center;
      gap: 0.65rem;
      flex-shrink: 0;
    }
    .sg-nav__lang {
      font-family: 'Sora', 'DM Sans', sans-serif;
      font-size: 0.75rem;
      font-weight: 600;
      padding: 0.28rem 0.6rem;
      border-radius: 100px;
      cursor: pointer;
      border: 1px solid rgba(255,255,255,0.18);
      background: transparent;
      color: rgba(232,240,228,0.75);
      display: flex;
      align-items: center;
      gap: 0.35rem;
      transition: border-color 0.15s, color 0.15s, background 0.15s;
      white-space: nowrap;
    }
    .sg-nav__lang:hover {
      border-color: rgba(255,255,255,0.35);
      color: rgba(232,240,228,1);
    }
    .sg-nav__lang.sg-nav__lang--pl {
      color: #ff6b6b;
      border-color: rgba(255,107,107,0.45);
      font-weight: 700;
    }
    .sg-nav__lang.sg-nav__lang--pl:hover {
      color: #ff8585;
      border-color: rgba(255,107,107,0.65);
    }
    /* Hide the floating pill since nav handles switching */
    #sg-lang-switcher { display: none !important; }
    .sg-nav__signin {
      font-family: 'Sora', 'DM Sans', sans-serif;
      font-size: 0.78rem;
      font-weight: 600;
      padding: 0.35rem 0.9rem;
      border-radius: 6px;
      text-decoration: none;
      border: none;
      cursor: pointer;
      background: #34d399;
      color: #1a4d2e;
      transition: opacity 0.15s;
    }
    .sg-nav__signin:hover { opacity: 0.88; }

    /* version badge inside nav */
    .sg-nav__version {
      font-family: 'JetBrains Mono', ui-monospace, monospace;
      font-size: 0.55rem;
      color: rgba(232,240,228,0.35);
      text-decoration: underline dotted;
      text-underline-offset: 2px;
      cursor: pointer;
      transition: color 0.15s;
    }
    .sg-nav__version:hover { color: rgba(232,240,228,0.6); }

    /* ── hamburger (mobile) ──────────────── */
    .sg-nav__hamburger {
      display: none;
      flex-direction: column;
      gap: 3.5px;
      cursor: pointer;
      padding: 6px 4px;
      background: none;
      border: none;
    }
    .sg-nav__hamburger span {
      width: 18px;
      height: 1.8px;
      border-radius: 1px;
      background: rgba(232,240,228,0.8);
      transition: transform 0.2s, opacity 0.2s;
      display: block;
    }
    .sg-nav__hamburger--open span:nth-child(1) {
      transform: translateY(5.3px) rotate(45deg);
    }
    .sg-nav__hamburger--open span:nth-child(2) { opacity: 0; }
    .sg-nav__hamburger--open span:nth-child(3) {
      transform: translateY(-5.3px) rotate(-45deg);
    }

    /* ── mobile drawer ───────────────────── */
    .sg-nav__drawer {
      display: none;
      position: fixed;
      top: 48px;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0,0,0,0.4);
      z-index: 999;
    }
    .sg-nav__drawer--open { display: block; }
    .sg-nav__drawer-inner {
      background: #1a4d2e;
      border-bottom: 1px solid rgba(52,211,153,0.15);
      padding: 0.75rem 1.5rem 1rem;
      box-shadow: 0 4px 20px rgba(0,0,0,0.25);
    }
    .sg-nav__drawer-tab {
      display: block;
      font-family: 'Sora', 'DM Sans', sans-serif;
      font-size: 0.95rem;
      font-weight: 400;
      padding: 0.65rem 0.5rem;
      text-decoration: none;
      color: rgba(232,240,228,0.7);
      border-bottom: 1px solid rgba(255,255,255,0.06);
      transition: color 0.15s;
    }
    .sg-nav__drawer-tab:last-child { border-bottom: none; }
    .sg-nav__drawer-tab:hover { color: #fff; }
    .sg-nav__drawer-tab--active { color: #34d399; }

    /* ── responsive ──────────────────────── */
    @media (max-width: 768px) {
      .sg-nav { padding: 0 1rem; }
      .sg-nav__center { display: none; }
      .sg-nav__signin { display: none; }
      .sg-nav__hamburger { display: flex; }
    }

    /* ── push page content below sticky nav ── */
    body { padding-top: 0; }
  `;
  document.head.appendChild(s);

  // Add Sora + Fraunces fonts if not already loaded
  if (!document.querySelector('link[href*="Sora"]')) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600&family=Fraunces:ital,wght@0,400;0,500;0,600;1,400&display=swap';
    document.head.appendChild(link);
  }
}

/* ── build the nav DOM ────────────────────────────────────────────── */
function buildNav() {
  const active = currentTab();
  const nav = document.createElement('nav');
  nav.className = 'sg-nav';
  nav.setAttribute('aria-label', 'Main navigation');

  // Left — wordmark
  const left = document.createElement('div');
  left.className = 'sg-nav__left';
  const wmLink = document.createElement('a');
  wmLink.href = '/';
  wmLink.setAttribute('aria-label', 'Sponic Gardens — Home');
  const wmImg = document.createElement('img');
  wmImg.src = WORDMARK_SRC;
  wmImg.alt = 'Sponic Gardens';
  wmImg.className = 'sg-nav__wordmark';
  wmLink.appendChild(wmImg);
  left.appendChild(wmLink);

  // Version badge — right of wordmark
  const ver = document.createElement('span');
  ver.className = 'sg-nav__version site-nav__version';
  ver.textContent = '—';
  left.appendChild(ver);

  nav.appendChild(left);

  // Center — tabs
  const center = document.createElement('div');
  center.className = 'sg-nav__center';
  for (const tab of TABS) {
    const a = document.createElement('a');
    a.href = tab.href;
    a.className = 'sg-nav__tab';
    a.textContent = tab.label;
    if (tab.href === active) a.classList.add('sg-nav__tab--active');
    center.appendChild(a);
  }
  nav.appendChild(center);

  // Right — lang, version, sign-in, hamburger
  const right = document.createElement('div');
  right.className = 'sg-nav__right';

  const lang = document.createElement('button');
  lang.className = 'sg-nav__lang';
  lang.setAttribute('aria-label', 'Change language');

  function updateLangBtn() {
    const i18n = window.__sg_i18n;
    if (!i18n) { lang.innerHTML = '🇵🇱 Polski'; lang.classList.add('sg-nav__lang--pl'); return; }
    const code = i18n.getLang();
    // Show the language you can SWITCH TO (the other one)
    const other = { en: { flag: '🇵🇱', label: 'Polski', pl: true }, pl: { flag: '🇬🇧', label: 'EN', pl: false } };
    const target = other[code] || { flag: '🌐', label: code === 'en' ? 'Polski' : 'EN', pl: code !== 'pl' };
    lang.innerHTML = `${target.flag} ${target.label}`;
    lang.classList.toggle('sg-nav__lang--pl', target.pl);
  }

  lang.addEventListener('click', () => {
    const i18n = window.__sg_i18n;
    if (!i18n) return;
    const next = i18n.getLang() === 'pl' ? 'en' : 'pl';
    i18n.setLang(next);
    updateLangBtn();
  });

  document.addEventListener('sg:langchange', updateLangBtn);

  // Update once i18n is ready
  if (window.__sg_i18n) {
    updateLangBtn();
  } else {
    const iv = setInterval(() => { if (window.__sg_i18n) { updateLangBtn(); clearInterval(iv); } }, 100);
  }

  right.appendChild(lang);

  const signin = document.createElement('a');
  signin.href = '#';
  signin.className = 'sg-nav__signin';
  signin.textContent = 'Sign in';
  right.appendChild(signin);

  // Hamburger
  const burger = document.createElement('button');
  burger.className = 'sg-nav__hamburger';
  burger.setAttribute('aria-label', 'Toggle menu');
  burger.innerHTML = '<span></span><span></span><span></span>';
  right.appendChild(burger);

  nav.appendChild(right);

  // Drawer (mobile)
  const drawer = document.createElement('div');
  drawer.className = 'sg-nav__drawer';
  const drawerInner = document.createElement('div');
  drawerInner.className = 'sg-nav__drawer-inner';
  for (const tab of TABS) {
    const a = document.createElement('a');
    a.href = tab.href;
    a.className = 'sg-nav__drawer-tab';
    a.textContent = tab.label;
    if (tab.href === active) a.classList.add('sg-nav__drawer-tab--active');
    drawerInner.appendChild(a);
  }
  // Sign in link in drawer
  const drawerSignin = document.createElement('a');
  drawerSignin.href = '#';
  drawerSignin.className = 'sg-nav__drawer-tab';
  drawerSignin.textContent = 'Sign in';
  drawerSignin.style.color = '#34d399';
  drawerInner.appendChild(drawerSignin);
  drawer.appendChild(drawerInner);

  // Toggle logic
  burger.addEventListener('click', () => {
    const open = drawer.classList.toggle('sg-nav__drawer--open');
    burger.classList.toggle('sg-nav__hamburger--open', open);
    burger.setAttribute('aria-expanded', String(open));
  });
  drawer.addEventListener('click', (e) => {
    if (e.target === drawer) {
      drawer.classList.remove('sg-nav__drawer--open');
      burger.classList.remove('sg-nav__hamburger--open');
    }
  });

  return { nav, drawer };
}

/* ── inject into page ─────────────────────────────────────────────── */
function init() {
  // Skip admin pages
  if (location.pathname.startsWith('/admin/')) return;
  // Skip if nav already exists
  if (document.querySelector('.sg-nav')) return;

  injectStyles();
  const { nav, drawer } = buildNav();

  // Remove existing siteHeader (version badge) — we have it in nav now
  const oldHeader = document.getElementById('siteHeader');
  if (oldHeader) oldHeader.remove();

  // Remove existing per-page <nav> elements
  const oldNavs = document.querySelectorAll('body > nav, .hero + nav');
  oldNavs.forEach(n => n.remove());

  // Insert at top of body
  document.body.prepend(drawer);
  document.body.prepend(nav);

  // On homepage, adjust hero so nav sits above it
  if (isHomepage()) {
    const hero = document.querySelector('.hero');
    if (hero) {
      hero.style.marginTop = '0';
    }
  }
}

/* ── auto-init ────────────────────────────────────────────────────── */
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

export { init as setupNav };
