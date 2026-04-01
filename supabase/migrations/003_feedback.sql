-- Visitor feedback table
-- Stores feedback submitted from the form at the bottom of every page.

CREATE TABLE IF NOT EXISTS feedback (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  email       text,
  message     text NOT NULL,
  page_path   text NOT NULL,
  page_title  text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_page_path  ON feedback (page_path);

-- Allow anonymous inserts from the frontend (Supabase anon key)
ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can insert feedback"
  ON feedback FOR INSERT
  WITH CHECK (true);

CREATE POLICY "No public reads"
  ON feedback FOR SELECT
  USING (false);
