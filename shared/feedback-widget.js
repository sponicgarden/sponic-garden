/**
 * Feedback widget — auto-injects a feedback form before the <footer> on every page.
 * Stores submissions in the Supabase `feedback` table.
 *
 * Usage: <script type="module" src="/shared/feedback-widget.js"></script>
 */

const SUPABASE_URL = 'https://aphrrfprbixmhissnjfn.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFwaHJyZnByYml4bWhpc3NuamZuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk5MzA0MjUsImV4cCI6MjA4NTUwNjQyNX0.yYkdQIq97GQgxK7yT2OQEPi5Tt-a7gM45aF8xjSD6wk';

function injectStyles() {
  const style = document.createElement('style');
  style.textContent = `
    .sg-feedback {
      max-width: 720px;
      margin: 2rem auto 0;
      padding: 0 1.25rem 1.5rem;
    }
    .sg-feedback-box {
      background: var(--surface, #ffffff);
      border: 1px solid var(--border-light, #d8e3cf);
      border-radius: var(--radius-lg, 14px);
      padding: 1.5rem;
    }
    .sg-feedback-box h3 {
      font-family: 'DM Serif Display', serif;
      font-size: 1.1rem;
      color: var(--text, #1a2412);
      margin-bottom: 0.25rem;
    }
    .sg-feedback-box .sg-fb-sub {
      font-size: 0.82rem;
      color: var(--text-muted, #7a9168);
      margin-bottom: 1rem;
    }
    .sg-feedback-box input,
    .sg-feedback-box textarea {
      display: block;
      width: 100%;
      font-family: 'DM Sans', sans-serif;
      font-size: 0.9rem;
      padding: 0.6rem 0.75rem;
      border: 1px solid var(--border, #c4d4ba);
      border-radius: var(--radius, 10px);
      background: var(--bg, #f4f7f1);
      color: var(--text, #1a2412);
      outline: none;
      transition: border-color 0.2s;
    }
    .sg-feedback-box input:focus,
    .sg-feedback-box textarea:focus {
      border-color: var(--green, #2d6a1e);
    }
    .sg-feedback-box textarea {
      min-height: 80px;
      resize: vertical;
      margin-top: 0.5rem;
    }
    .sg-feedback-box button {
      margin-top: 0.75rem;
      padding: 0.55rem 1.25rem;
      font-family: 'DM Sans', sans-serif;
      font-size: 0.85rem;
      font-weight: 600;
      color: #fff;
      background: var(--green, #2d6a1e);
      border: none;
      border-radius: var(--radius, 10px);
      cursor: pointer;
      transition: opacity 0.2s;
    }
    .sg-feedback-box button:hover { opacity: 0.85; }
    .sg-feedback-box button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .sg-fb-status {
      margin-top: 0.5rem;
      font-size: 0.82rem;
      min-height: 1.2em;
    }
    .sg-fb-status.success { color: var(--emerald, #047857); }
    .sg-fb-status.error   { color: var(--rose, #be123c); }
  `;
  document.head.appendChild(style);
}

function buildForm() {
  const wrapper = document.createElement('div');
  wrapper.className = 'sg-feedback';
  wrapper.innerHTML = `
    <div class="sg-feedback-box">
      <h3>Share Your Thoughts</h3>
      <p class="sg-fb-sub">Viewing: <strong>${document.title}</strong></p>
      <form id="sg-feedback-form" autocomplete="off">
        <input type="email" name="email" placeholder="Your email (optional)" />
        <textarea name="message" placeholder="What do you think? Any ideas, questions, or feedback..." required></textarea>
        <button type="submit">Send Feedback</button>
      </form>
      <div class="sg-fb-status" id="sg-fb-status"></div>
    </div>
  `;
  return wrapper;
}

async function submitFeedback(email, message) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/feedback`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'apikey': SUPABASE_ANON_KEY,
      'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
      'Prefer': 'return=minimal'
    },
    body: JSON.stringify({
      email: email || null,
      message,
      page_path: window.location.pathname,
      page_title: document.title
    })
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
}

function init() {
  injectStyles();

  const footer = document.querySelector('footer');
  const form = buildForm();

  if (footer) {
    footer.parentNode.insertBefore(form, footer);
  } else {
    document.body.appendChild(form);
  }

  const formEl = document.getElementById('sg-feedback-form');
  const statusEl = document.getElementById('sg-fb-status');

  formEl.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = formEl.querySelector('button');
    btn.disabled = true;
    statusEl.className = 'sg-fb-status';
    statusEl.textContent = 'Sending...';

    try {
      const fd = new FormData(formEl);
      await submitFeedback(fd.get('email'), fd.get('message'));
      statusEl.className = 'sg-fb-status success';
      statusEl.textContent = 'Thank you for your feedback!';
      formEl.reset();
    } catch (err) {
      statusEl.className = 'sg-fb-status error';
      statusEl.textContent = 'Something went wrong. Please try again.';
      console.error('Feedback submission error:', err);
    } finally {
      btn.disabled = false;
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
