-- Translation infrastructure: config, languages, translations, translation_queue
-- Supports unlimited languages (EN, PL, DE, RU, etc.) with zero schema changes.
-- All system settings are cloud-reconfigurable via the config table.

-- ─── config ────────────────────────────────────────────────────────────────────
-- All runtime settings. Change model, prompt, batch size, etc. from the DB
-- without redeploying any code. The translation Worker reads this at runtime.

CREATE TABLE IF NOT EXISTS config (
  key         TEXT PRIMARY KEY,
  value       JSONB NOT NULL,
  description TEXT,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO config (key, value, description) VALUES
  ('translation.context',
   '"Sponic Garden is a wellness destination venue in Warsaw, Poland. Translate maintaining a professional, warm, botanical brand voice."',
   'System prompt context injected into every translation request'),
  ('translation.model',
   '"claude-haiku-4-5-20251001"',
   'Claude model used for batch translation'),
  ('translation.batch_size',
   '20',
   'Max keys to translate per cron run'),
  ('translation.cron_interval_min',
   '5',
   'Target cron interval in minutes (informational — actual trigger set in Cloudflare Worker)'),
  ('site.default_lang',
   '"en"',
   'Fallback language if geo-detection is unavailable'),
  ('site.geo_detect_enabled',
   'true',
   'Auto-detect language from Cloudflare CF-IPCountry header (no browser permission required)'),
  ('site.admin_emails',
   '["rahulioson@gmail.com","wingsiebird@gmail.com"]',
   'Emails allowed to access /admin pages via Google OAuth')
ON CONFLICT (key) DO NOTHING;

ALTER TABLE config ENABLE ROW LEVEL SECURITY;

-- Anon can read all config (frontend reads site.* keys at runtime)
CREATE POLICY "Public read config"
  ON config FOR SELECT
  USING (true);

-- Only authenticated users can write
CREATE POLICY "Authenticated write config"
  ON config FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);


-- ─── languages ─────────────────────────────────────────────────────────────────
-- Shared registry of active languages. Adding a row here enables the language
-- across the entire translation system (static content + future speech subtitles).
-- alpacapps reads this table from sponic-garden Supabase via REST.

CREATE TABLE IF NOT EXISTS languages (
  code       TEXT PRIMARY KEY,         -- ISO 639-1: 'en', 'pl', 'de', 'ru'
  name       TEXT NOT NULL,            -- Display name: 'English', 'Polski'
  flag       TEXT,                     -- Flag emoji: '🇬🇧', '🇵🇱'
  enabled    BOOLEAN NOT NULL DEFAULT true,
  is_base    BOOLEAN NOT NULL DEFAULT false,  -- Primary source language (only one)
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO languages (code, name, flag, is_base, sort_order) VALUES
  ('en', 'English', '🇬🇧', true,  0),
  ('pl', 'Polski',  '🇵🇱', false, 1)
ON CONFLICT (code) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_languages_enabled ON languages (enabled) WHERE enabled = true;

ALTER TABLE languages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read languages"
  ON languages FOR SELECT
  USING (true);

CREATE POLICY "Authenticated write languages"
  ON languages FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);


-- ─── translations ───────────────────────────────────────────────────────────────
-- One row per (key, lang). Adding a language = new rows, no schema change.
-- is_source: this row was authored (not machine-translated).
-- pending:   this row needs to be (re)generated from the source lang.

CREATE TABLE IF NOT EXISTS translations (
  key        TEXT NOT NULL,
  lang       TEXT NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
  value      TEXT,
  pending    BOOLEAN NOT NULL DEFAULT false,
  is_source  BOOLEAN NOT NULL DEFAULT false,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (key, lang)
);

CREATE INDEX IF NOT EXISTS idx_translations_pending
  ON translations (pending) WHERE pending = true;

CREATE INDEX IF NOT EXISTS idx_translations_key
  ON translations (key);

ALTER TABLE translations ENABLE ROW LEVEL SECURITY;

-- Public read: i18n.js fetches all translations on page load
CREATE POLICY "Public read translations"
  ON translations FOR SELECT
  USING (true);

CREATE POLICY "Authenticated write translations"
  ON translations FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);


-- ─── translation_queue ─────────────────────────────────────────────────────────
-- Generic queue for translating dynamic content from any table.
-- Source table pushes a job here; the Cloudflare Worker processes it and writes
-- the result back to the originating table. Extensible to events, posts, etc.

CREATE TABLE IF NOT EXISTS translation_queue (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_table    TEXT NOT NULL,   -- 'translations', 'events', 'posts', etc.
  source_id       TEXT NOT NULL,   -- row key or UUID in source_table
  source_field    TEXT NOT NULL,   -- column name, e.g. 'body', 'title'
  source_lang     TEXT NOT NULL,   -- authored language
  target_lang     TEXT NOT NULL,   -- language to translate into
  source_text     TEXT NOT NULL,   -- the text to translate
  status          TEXT NOT NULL DEFAULT 'pending',  -- pending / processing / done / error
  translated_text TEXT,
  error_message   TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tq_pending
  ON translation_queue (status, created_at) WHERE status = 'pending';

ALTER TABLE translation_queue ENABLE ROW LEVEL SECURITY;

-- No public access — only the Worker (service role) reads/writes this
CREATE POLICY "No public access to translation_queue"
  ON translation_queue FOR SELECT
  USING (false);
