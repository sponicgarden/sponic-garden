/* docs/auth-guard.js — Supabase Google OAuth guard for docs pages */
(function () {
  const SUPABASE_URL = 'https://aphrrfprbixmhissnjfn.supabase.co';
  const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFwaHJyZnByYml4bWhpc3NuamZuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk5MzA0MjUsImV4cCI6MjA4NTUwNjQyNX0.yYkdQIq97GQgxK7yT2OQEPi5Tt-a7gM45aF8xjSD6wk';
  const ALLOWED_EMAILS = ['rahulioson@gmail.com', 'wingsiebird@gmail.com', 'hrsonnad@gmail.com'];

  const sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

  // Inject overlay HTML
  const overlay = document.createElement('div');
  overlay.id = 'auth-overlay';
  overlay.innerHTML = `
    <div class="auth-card">
      <img src="/branding/94-vines-waveform-orchid-transparent.png" alt="Sponic Gardens" class="auth-logo">
      <h2>Sponic Garden</h2>
      <p class="auth-subtitle">Sign in to view confidential documents</p>
      <button id="auth-google-btn" type="button">
        <svg width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59a14.5 14.5 0 0 1 0-9.18l-7.98-6.19a24.08 24.08 0 0 0 0 21.56l7.98-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>
        Sign in with Google
      </button>
      <p id="auth-error" class="auth-error" style="display:none"></p>
      <p class="auth-footer">Access restricted to authorized personnel</p>
    </div>
  `;
  document.body.prepend(overlay);

  // Hide page content until auth passes
  document.body.classList.add('auth-locked');

  const btn = document.getElementById('auth-google-btn');
  const errorEl = document.getElementById('auth-error');

  function unlock() {
    overlay.style.display = 'none';
    document.body.classList.remove('auth-locked');
  }

  function deny(msg) {
    errorEl.textContent = msg || 'Access denied. This account is not authorized.';
    errorEl.style.display = 'block';
  }

  btn.addEventListener('click', async function () {
    btn.disabled = true;
    btn.textContent = 'Redirecting…';
    const { error } = await sb.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin + window.location.pathname }
    });
    if (error) {
      deny(error.message);
      btn.disabled = false;
      btn.textContent = 'Sign in with Google';
    }
  });

  // Single auth handler — works for both existing sessions and OAuth callbacks
  sb.auth.onAuthStateChange(async (event, session) => {
    if (event === 'INITIAL_SESSION' || event === 'SIGNED_IN' || event === 'TOKEN_REFRESHED') {
      if (!session) return;            // no session yet — stay on sign-in
      if (!ALLOWED_EMAILS.includes(session.user.email)) {
        await sb.auth.signOut();
        deny();
        return;
      }
      unlock();
    }
  });
})();
