# Migrate sponicgardens.com from GitHub Pages to Cloudflare Pages

## Prompt

You are migrating sponicgardens.com from GitHub Pages to Cloudflare Pages. Follow these phases in order. Do not skip the verification steps — test on the preview domain before touching DNS.

---

## Current State

- **Domain:** `sponicgardens.com`
- **Hosting:** GitHub Pages (static HTML, no build step)
- **DNS:** Already managed by Cloudflare (separate account from the one we'll use for Pages)
- **Repo:** `sponicgarden/sponic-garden` on GitHub (public)
- **CI:** `.github/workflows/bump-version-on-push.yml` — auto-bumps version on every push to `main`, commits back to repo
- **Backend:** Supabase (`aphrrfprbixmhissnjfn.supabase.co`) — feedback, auth, version tracking, image storage
- **External CDNs:** Google Fonts, jsDelivr (Supabase JS client)
- **Auth:** Google OAuth via Supabase on patent pages — uses `window.location.origin` (auto-adapts to any domain)

---

## Phase 1: Create Cloudflare Pages Project (15 min)

1. Log into Cloudflare dashboard
2. Go to **Workers & Pages → Create → Pages → Connect to Git**
3. Select the `sponicgarden/sponic-garden` repository
4. Configure build settings:
   - **Production branch:** `main`
   - **Build command:** *(leave empty — static site, no build step)*
   - **Build output directory:** `/` *(root — all HTML files are at top level)*
5. Click **Save and Deploy**
6. Wait for initial deploy to complete
7. Note the `*.pages.dev` preview URL

### Verify on preview domain

Open the `*.pages.dev` URL and confirm:

- [ ] Homepage loads with correct styles, images, and fonts
- [ ] Navigation works to all subpages: `bizmodel.html`, `charter.html`, `branding.html`, `design/venue.html`
- [ ] Feedback widget appears and submits successfully (check Supabase `feedback` table)
- [ ] Patent pages (`patents/index.html`) show Google OAuth login
- [ ] Version badge displays and tooltip works (loads `version.json`)
- [ ] Design review page loads render images from Supabase Storage
- [ ] No console errors on any page

**Do not proceed to Phase 2 until all checks pass on the preview domain.**

---

## Phase 2: DNS Cutover (30 min)

DNS is already on Cloudflare but in a different account. Two options:

### Option A: Same Cloudflare account (recommended)

If you can add the domain to the same account as the Pages project:

1. In Cloudflare Pages project settings → **Custom domains → Add custom domain**
2. Enter `sponicgardens.com`
3. Cloudflare will auto-configure DNS if the domain is in the same account
4. Also add `www.sponicgardens.com` with a redirect to apex

### Option B: Cross-account (DNS in account A, Pages in account B)

1. In the DNS account (account A), lower the TTL on the existing A/CNAME record for `sponicgardens.com` to **300 seconds** (5 min). Wait for old TTL to expire.
2. In the Pages account (account B), go to **Custom domains → Add custom domain** → enter `sponicgardens.com`
3. Cloudflare Pages will give you a CNAME target (e.g., `sponic-garden.pages.dev`)
4. In account A DNS settings, update the record for `sponicgardens.com`:
   - **Type:** CNAME
   - **Target:** `sponic-garden.pages.dev` *(or whatever Pages provides)*
   - **Proxy:** OFF (DNS only / grey cloud) — Cloudflare Pages handles its own edge
5. Wait for propagation (usually <5 min with 300s TTL)
6. Verify `sponicgardens.com` resolves to the Cloudflare Pages deployment

### SSL

Cloudflare Pages auto-provisions an SSL certificate. Verify HTTPS works after DNS cutover.

### Downtime expectation

0–30 minutes depending on DNS propagation. Do this during off-hours (Warsaw time: late evening or early morning).

---

## Phase 3: Verify Live Site (30 min)

After DNS cutover, verify everything works on the live domain:

| Check | How | Pass? |
|---|---|---|
| Homepage loads | Visit `sponicgardens.com` | [ ] |
| All subpages load | `/bizmodel.html`, `/charter.html`, `/branding.html`, `/design/venue.html`, `/en/index.html` | [ ] |
| Feedback widget | Submit test feedback, check Supabase table | [ ] |
| Patent page auth | Log in via Google OAuth on `patents/index.html` | [ ] |
| Supabase Storage images | Browse `design/review.html`, verify render images load | [ ] |
| Google Fonts | Visual check — DM Sans, DM Serif Display, Cormorant Garamond load | [ ] |
| OG meta tags | Paste URL in social media debugger (Twitter Card Validator, FB Sharing Debugger) | [ ] |
| Version display | Click version badge, verify tooltip shows correct version | [ ] |
| HTTPS | Confirm padlock icon, no mixed content warnings | [ ] |
| CI deploy | Push a test commit to `main`, verify version bumps and Cloudflare deploys | [ ] |

---

## Phase 4: Update CI Workflow (30 min)

The existing GitHub Actions workflow continues to work as-is — it commits version bumps to `main`, which triggers Cloudflare Pages auto-deploy. But clean up:

1. **Delete the `CNAME` file** from the repo root (no longer needed)
2. **Disable GitHub Pages** in repo settings: Settings → Pages → Source → None
3. Commit and push these changes

### Double deploy note

Every push to `main` triggers:
1. Cloudflare deploy #1 (the actual code change)
2. GitHub Actions runs version bump → commits → triggers Cloudflare deploy #2

This is harmless — deploy #2 overwrites #1 within seconds. At ~90 builds/month (current cadence), well within the free tier limit of 500 builds/month.

**Optional optimization (do later if needed):** Add `[skip deploy]` to version bump commit messages and configure Cloudflare Pages to skip those commits. Or move version bumping into a Cloudflare Pages build command.

---

## Phase 5: Enable Cloudflare Features (optional, 15 min)

Now that you're on Cloudflare Pages, enable these free features:

1. **Web Analytics:** Cloudflare dashboard → Analytics → Web Analytics → Enable for `sponicgardens.com`
   - Privacy-friendly, no JS tag needed
2. **Cache rules:** Pages handles this automatically, but review in Caching → Configuration
3. **Security headers:** Add via `_headers` file in repo root:
   ```
   /*
     X-Content-Type-Options: nosniff
     X-Frame-Options: DENY
     Referrer-Policy: strict-origin-when-cross-origin
   ```
4. **Preview deploys:** Already enabled — every PR gets a unique URL automatically

---

## Rollback Plan

If anything breaks after DNS cutover:

1. Re-enable GitHub Pages in repo settings (Settings → Pages → Deploy from branch: `main`)
2. Re-add `CNAME` file with `sponicgardens.com`
3. Update DNS record to point back to GitHub Pages (`sponicgarden.github.io`)
4. **Full rollback time: ~15 minutes**

---

## Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| DNS propagation delay | Medium | 30 min downtime | Lower TTL before cutover. Do off-hours. |
| Double deploys | Certain | None (cosmetic) | Accept; optimize later |
| OAuth callback fails | Low | Patent pages down | Uses `window.location.origin` — auto-adapts. Tested on preview. |
| Supabase CORS issues | Very Low | API calls fail | Anon key is not domain-restricted. |
| Build output wrong (blank site) | Low | Site down | Tested on preview domain first. |

---

## What We Gain

- 300+ global edge PoPs (vs GitHub's limited CDN)
- Preview deploy URLs for every PR
- Free Web Analytics dashboard
- Workers capability for future i18n routing (`Accept-Language` → `/pl/`)
- Instant cache purge on deploy
- DDoS protection
- `_headers` and `_redirects` file support for server-side behavior
