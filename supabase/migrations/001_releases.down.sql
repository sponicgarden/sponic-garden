-- Reverse of 001_releases.sql.
-- DESTRUCTIVE: drops all release history. Use only if reverting the entire
-- release-tracking subsystem.

BEGIN;

DROP FUNCTION IF EXISTS record_release_event(
  text, text, text, text, timestamptz, text, integer, text, text, text, jsonb, jsonb
);
DROP INDEX IF EXISTS idx_releases_pushed_at;
DROP TABLE IF EXISTS releases;

COMMIT;
