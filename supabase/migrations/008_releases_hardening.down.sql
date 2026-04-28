-- Reverse of 008_releases_hardening.sql.
--
-- Restores the function to its 001 implementation (no advisory lock, no
-- post-lock re-check) and drops the UNIQUE(display_version) constraint.
-- Run only if 002 needs to be backed out — ordinary forward migration is
-- idempotent and re-runnable.

BEGIN;

ALTER TABLE releases DROP CONSTRAINT IF EXISTS releases_display_version_key;

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
BEGIN
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

  v_date_str := to_char(p_pushed_at AT TIME ZONE 'UTC', 'YYMMDD');
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
