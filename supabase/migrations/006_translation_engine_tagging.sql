-- Add engine tagging and review workflow to translations table.
-- Tracks which model/human produced each translation and review status.

ALTER TABLE translations ADD COLUMN IF NOT EXISTS translated_by TEXT;
ALTER TABLE translations ADD COLUMN IF NOT EXISTS review_status TEXT NOT NULL DEFAULT 'unreviewed';
ALTER TABLE translations ADD COLUMN IF NOT EXISTS reviewed_by TEXT;
ALTER TABLE translations ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;

-- Index for filtering by review status in admin UI
CREATE INDEX IF NOT EXISTS idx_translations_review_status
  ON translations (review_status);

-- Audit table: log every translation change for traceability
CREATE TABLE IF NOT EXISTS translation_history (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key            TEXT NOT NULL,
  lang           TEXT NOT NULL,
  old_value      TEXT,
  new_value      TEXT,
  translated_by  TEXT,
  changed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_translation_history_key_lang
  ON translation_history (key, lang, changed_at DESC);

ALTER TABLE translation_history ENABLE ROW LEVEL SECURITY;

-- Public can read history (admin UI displays it)
CREATE POLICY "Public read translation_history"
  ON translation_history FOR SELECT
  USING (true);

-- Only authenticated/service role can write
CREATE POLICY "Authenticated write translation_history"
  ON translation_history FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Convention for translated_by values:
--   'llm:<model-id>'       e.g. 'llm:claude-haiku-4-5-20251001'
--   'human:<email>'        e.g. 'human:rahulioson@gmail.com'
--   'human:seed'           for seed script source rows
--   'import:<source>'      for bulk imports
