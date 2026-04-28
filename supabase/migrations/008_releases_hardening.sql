-- 008_releases_hardening.sql
--
-- Hardens the releases table and record_release_event() function from migration 001:
--   1. UNIQUE(display_version) — guarantees no duplicate version strings even
--      under race. The GH Action already serializes via `concurrency:`, but a
--      DB-level constraint protects against rogue manual runs and split-brain
--      ops (multiple machines running scripts/bump-version.sh against the
--      same project).
--   2. pg_advisory_xact_lock keyed on the UTC date — serializes concurrent
--      calls *on the same day* so the count(*)+1 daily sequence cannot race.
--      Cross-day calls remain parallel.
--   3. Re-creates the function (CREATE OR REPLACE) so the lock + clearer error
--      handling are wired in atomically.
--
-- Idempotent: safe to run multiple times.

BEGIN;

-- 1) Unique constraint on display_version. Guarded so re-running the migration
--    doesn't fail if the constraint is already present.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
     WHERE conname = 'releases_display_version_key'
       AND conrelid = 'releases'::regclass
  ) THEN
    ALTER TABLE releases
      ADD CONSTRAINT releases_display_version_key UNIQUE (display_version);
  END IF;
END$$;

-- 2) Replace record_release_event with a version that takes an advisory lock
--    on the UTC date hash, then computes the daily sequence. The lock is
--    transaction-scoped (auto-released at COMMIT/ROLLBACK).

CREATE OR REPLACE FUNCTION record_release_event(
  p_push_sha      text,
  p_branch        text,
  p_compare_from  text,
  p_compare_to    text,
  p_pushed_at     timestamptz,
  p_actor_login   text,
  p_pr_number     integer,
  p_source        text,
  p_model_code    text,
  p_machine_name  text,
  p_metadata      jsonb,
  p_commits       jsonb
)
RETURNS TABLE (
  seq             bigint,
  display_version text,
  pushed_at       timestamptz,
  actor_login     text,
  source          text
)
LANGUAGE plpgsql AS $$
DECLARE
  v_existing RECORD;
  v_seq      bigint;
  v_version  text;
  v_day_seq  integer;
  v_date_str text;
  v_lock_key bigint;
BEGIN
  -- Idempotent: if this push_sha was already recorded, return it without
  -- taking the lock — repeated CI runs are common and shouldn't queue up.
  SELECT r.seq, r.display_version, r.pushed_at, r.actor_login, r.source
    INTO v_existing
    FROM releases r
   WHERE r.push_sha = p_push_sha;

  IF FOUND THEN
    seq := v_existing.seq;
    display_version := v_existing.display_version;
    pushed_at := v_existing.pushed_at;
    actor_login := v_existing.actor_login;
    source := v_existing.source;
    RETURN NEXT;
    RETURN;
  END IF;

  -- Compute date string in UTC for lock key + version format.
  v_date_str := to_char(p_pushed_at AT TIME ZONE 'UTC', 'YYMMDD');

  -- Advisory transaction lock keyed on the date — serializes concurrent
  -- callers on the same day so count(*)+1 cannot race. Auto-released at
  -- transaction end. hashtextextended returns a stable bigint.
  v_lock_key := hashtextextended('releases:' || v_date_str, 0);
  PERFORM pg_advisory_xact_lock(v_lock_key);

  -- Re-check for the row after acquiring the lock — another transaction
  -- waiting on the same lock may have inserted our push_sha while we waited.
  SELECT r.seq, r.display_version, r.pushed_at, r.actor_login, r.source
    INTO v_existing
    FROM releases r
   WHERE r.push_sha = p_push_sha;

  IF FOUND THEN
    seq := v_existing.seq;
    display_version := v_existing.display_version;
    pushed_at := v_existing.pushed_at;
    actor_login := v_existing.actor_login;
    source := v_existing.source;
    RETURN NEXT;
    RETURN;
  END IF;

  SELECT count(*) + 1 INTO v_day_seq
    FROM releases
   WHERE to_char(releases.pushed_at AT TIME ZONE 'UTC', 'YYMMDD') = v_date_str;

  v_version := 'v' || v_date_str || '.' || lpad(v_day_seq::text, 2, '0');

  INSERT INTO releases (
    push_sha, branch, compare_from, compare_to, pushed_at,
    actor_login, pr_number, source, model_code, machine_name,
    display_version, metadata, commits
  ) VALUES (
    p_push_sha, p_branch, p_compare_from, p_compare_to, p_pushed_at,
    p_actor_login, p_pr_number, p_source, p_model_code, p_machine_name,
    v_version, p_metadata, p_commits
  )
  RETURNING releases.seq INTO v_seq;

  seq := v_seq;
  display_version := v_version;
  pushed_at := p_pushed_at;
  actor_login := p_actor_login;
  source := p_source;
  RETURN NEXT;
END;
$$;

COMMIT;
