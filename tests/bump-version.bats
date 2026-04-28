#!/usr/bin/env bats
# Tests for scripts/bump-version.sh.
#
# Requires: bats-core (brew install bats-core).
# Run:      bats tests/bump-version.bats
#
# The mock psql in tests/fixtures/fake-psql stands in for a real Supabase
# connection, so these tests run offline.

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
SCRIPT="$REPO_ROOT/scripts/bump-version.sh"
FAKE_PSQL="$REPO_ROOT/tests/fixtures/fake-psql"
SAMPLE_HTML="$REPO_ROOT/tests/fixtures/sample.html"

setup() {
  TMP_DIR="$(mktemp -d)"
  # Re-create a minimal project layout so the script runs against a throwaway
  # working tree — it shells out to git, writes version.json at repo root,
  # and rewrites HTML in-place.
  mkdir -p "$TMP_DIR/scripts"
  cp "$SCRIPT" "$TMP_DIR/scripts/bump-version.sh"
  chmod +x "$TMP_DIR/scripts/bump-version.sh"
  cp "$SAMPLE_HTML" "$TMP_DIR/sample.html"

  cd "$TMP_DIR"
  git init -q
  git config user.email "test@example.com"
  git config user.name "test"
  git add -A
  git commit -q -m "initial"

  export PSQL_BIN="$FAKE_PSQL"
  export SUPABASE_DB_URL="postgres://fake"
  export RELEASE_PUSH_SHA="$(git rev-parse HEAD)"
  export RELEASE_ACTOR_LOGIN="ci-bot"
  export RELEASE_BRANCH="main"
  export RELEASE_PUSHED_AT="2026-04-16T12:00:00Z"
  export RELEASE_SOURCE="unit-test"
}

teardown() {
  rm -rf "$TMP_DIR"
}

@test "fails fast when SUPABASE_DB_URL is unset" {
  unset SUPABASE_DB_URL
  run ./scripts/bump-version.sh
  [ "$status" -ne 0 ]
  [[ "$output" == *"SUPABASE_DB_URL is required"* ]]
}

@test "fails on unknown argument" {
  run ./scripts/bump-version.sh --bogus
  [ "$status" -ne 0 ]
  [[ "$output" == *"Unknown"* ]]
}

@test "happy path writes version.json with expected fields" {
  run ./scripts/bump-version.sh --model ci
  [ "$status" -eq 0 ]
  [ -f version.json ]

  grep -q '"version": "v260416.01"' version.json
  grep -q '"release": 42' version.json
  grep -q '"actor": "test-user"' version.json
  grep -q '"source": "test-source"' version.json
  grep -q '"model": "ci"' version.json
}

@test "rewrites data-site-version spans in HTML files" {
  run ./scripts/bump-version.sh --model ci
  [ "$status" -eq 0 ]
  grep -q 'data-site-version>v260416.01<' sample.html
}

@test "rewrites site-nav__version spans in HTML files" {
  run ./scripts/bump-version.sh --model ci
  [ "$status" -eq 0 ]
  grep -q 'site-nav__version">v260416.01<' sample.html
}

@test "rewrites legacy r-prefixed version strings in body text" {
  run ./scripts/bump-version.sh --model ci
  [ "$status" -eq 0 ]
  ! grep -q 'r123456789' sample.html
  grep -q 'v260416.01' sample.html
}

@test "--model flag overrides branch-derived default" {
  run ./scripts/bump-version.sh --model claude
  [ "$status" -eq 0 ]
  grep -q '"model": "claude"' version.json
}

@test "--source flag overrides env-derived default" {
  run ./scripts/bump-version.sh --source manual-bump
  [ "$status" -eq 0 ]
  # The script echoes the DB-returned source (test-source from the mock) into
  # version.json, so we instead assert the flag round-trips into the psql
  # invocation log.
  export FAKE_PSQL_LOG="$TMP_DIR/psql.log"
  run ./scripts/bump-version.sh --source manual-bump
  [ "$status" -eq 0 ]
  grep -q "manual-bump" "$FAKE_PSQL_LOG"
}

@test "exits non-zero when the DB call fails" {
  export FAKE_PSQL_EXIT=2
  run ./scripts/bump-version.sh --model ci
  [ "$status" -ne 0 ]
}

@test "PSQL_BIN injection is honored" {
  # If the override weren't honored, the script would fall back to a real
  # psql binary (or error). We prove it's used by checking the invocation log.
  export FAKE_PSQL_LOG="$TMP_DIR/psql.log"
  run ./scripts/bump-version.sh --model ci
  [ "$status" -eq 0 ]
  [ -s "$FAKE_PSQL_LOG" ]
}

@test "idempotent re-run overwrites version.json with same content" {
  run ./scripts/bump-version.sh --model ci
  [ "$status" -eq 0 ]
  first="$(cat version.json)"

  run ./scripts/bump-version.sh --model ci
  [ "$status" -eq 0 ]
  second="$(cat version.json)"

  [ "$first" = "$second" ]
}
