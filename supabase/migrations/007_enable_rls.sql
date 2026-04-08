-- 007_enable_rls.sql
-- Fix Supabase Security Advisor: rls_disabled_in_public on `releases` and
-- `spgd_building_components`. Both tables were created without RLS in 001/002,
-- exposing them to the anon key via PostgREST.
--
-- No anon access is required:
--   - `releases` is written by scripts/bump-version.sh via SUPABASE_DB_URL
--     (direct Postgres, bypasses RLS) and read by DevControl from GitHub's API,
--     not from this table.
--   - `spgd_building_components` is server-side only.
-- Enabling RLS with no policies denies all anon/authenticated access while
-- service_role and direct DB connections continue to work.

ALTER TABLE releases ENABLE ROW LEVEL SECURITY;
ALTER TABLE spgd_building_components ENABLE ROW LEVEL SECURITY;
