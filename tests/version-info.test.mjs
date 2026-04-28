// Tests for shared/version-info.js pure helpers.
//
// Run: node --test tests/version-info.test.mjs
//
// No external deps — uses node:test + node:assert. DOM-dependent paths
// (setupVersionInfo, injectStyles, showModal) are covered separately by
// manual/browser verification; here we lock down the schema resolver and
// formatting helpers, which are where regressions have historically been
// easy to introduce (the old/new version.json schema branch).

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  resolveInfo,
  val,
  rNum,
  modelName,
  shortSha,
} from '../shared/version-info.js';

/* ── rNum ───────────────────────────────────────────────────────────── */

test('rNum: pads to 5 digits with r prefix', () => {
  assert.equal(rNum(1), 'r00001');
  assert.equal(rNum(42), 'r00042');
  assert.equal(rNum(99999), 'r99999');
});

test('rNum: accepts numeric strings', () => {
  assert.equal(rNum('7'), 'r00007');
});

test('rNum: returns em-dash for non-numeric input', () => {
  assert.equal(rNum('abc'), '—');
  assert.equal(rNum(null), '—');
  assert.equal(rNum(undefined), '—');
  assert.equal(rNum(''), '—');
});

/* ── val ────────────────────────────────────────────────────────────── */

test('val: returns first non-empty string trimmed', () => {
  assert.equal(val('', '  hello  ', 'world'), 'hello');
});

test('val: returns first finite number as string', () => {
  assert.equal(val(undefined, 0, 5), '0');
  assert.equal(val(null, NaN, 7), '7');
});

test('val: returns em-dash when everything is empty or invalid', () => {
  assert.equal(val(undefined, null, '', '   ', NaN), '—');
});

/* ── modelName ──────────────────────────────────────────────────────── */

test('modelName: maps known codes to friendly names', () => {
  assert.equal(modelName('o4.6'), 'Claude Opus 4.6');
  assert.equal(modelName('ci'), 'CI');
  assert.equal(modelName('cursor'), 'Cursor');
});

test('modelName: echoes unknown codes', () => {
  assert.equal(modelName('mystery'), 'mystery');
});

test('modelName: returns em-dash for null/undefined/empty', () => {
  assert.equal(modelName(null), '—');
  assert.equal(modelName(undefined), '—');
  assert.equal(modelName(''), '—');
});

/* ── shortSha ───────────────────────────────────────────────────────── */

test('shortSha: slices to 8 chars', () => {
  assert.equal(shortSha('abcdef1234567890'), 'abcdef12');
});

test('shortSha: returns em-dash for falsy input', () => {
  assert.equal(shortSha(''), '—');
  assert.equal(shortSha(null), '—');
  assert.equal(shortSha(undefined), '—');
});

/* ── resolveInfo (new schema — top-level fields) ────────────────────── */

test('resolveInfo: returns null for null/undefined input', () => {
  assert.equal(resolveInfo(null), null);
  assert.equal(resolveInfo(undefined), null);
});

test('resolveInfo: new schema (release is a number) maps flat fields', () => {
  const info = {
    version: 'v260416.01',
    release: 42,
    sha: 'abc12345',
    fullSha: 'abc12345def67890',
    actor: 'ci-bot',
    source: 'github-main-push',
    model: 'ci',
    machine: 'runner-1',
    pushedAt: '2026-04-16T12:00:00Z',
    commits: [{ sha: 'deadbeef', message: 'fix: thing' }],
  };
  const d = resolveInfo(info);
  assert.equal(d.version, 'v260416.01');
  assert.equal(d.release, '42');
  assert.equal(d.sha, 'abc12345');
  assert.equal(d.fullSha, 'abc12345def67890');
  assert.equal(d.actor, 'ci-bot');
  assert.equal(d.source, 'github-main-push');
  assert.equal(d.model, 'ci');
  assert.equal(d.machine, 'runner-1');
  assert.equal(d.pushedAt, '2026-04-16T12:00:00Z');
  assert.deepEqual(d.commits, [{ sha: 'deadbeef', message: 'fix: thing' }]);
});

/* ── resolveInfo (old schema — release is an object with DB-side keys) ─ */

test('resolveInfo: old schema (release is object) pulls from release.*', () => {
  const info = {
    release: {
      seq: 17,
      display_version: 'v260415.02',
      push_sha: 'longsha123456',
      actor_login: 'alice',
      source: 'manual',
      model_code: 'claude',
      machine_name: 'laptop',
      pushed_at: '2026-04-15T18:00:00Z',
    },
  };
  const d = resolveInfo(info);
  assert.equal(d.version, 'v260415.02');
  assert.equal(d.release, '17');
  assert.equal(d.sha, 'longsha1');
  assert.equal(d.fullSha, 'longsha123456');
  assert.equal(d.actor, 'alice');
  assert.equal(d.source, 'manual');
  assert.equal(d.model, 'claude');
  assert.equal(d.machine, 'laptop');
  assert.equal(d.pushedAt, '2026-04-15T18:00:00Z');
});

/* ── resolveInfo (defaults) ─────────────────────────────────────────── */

test('resolveInfo: returns em-dash defaults for missing fields', () => {
  const d = resolveInfo({});
  assert.equal(d.version, '—');
  assert.equal(d.actor, '—');
  assert.equal(d.source, '—');
  assert.equal(d.model, '—');
  assert.equal(d.machine, '—');
  assert.equal(d.pushedAt, '');
  assert.deepEqual(d.commits, []);
});

test('resolveInfo: commits falls back to info.changes if commits is absent', () => {
  const d = resolveInfo({ changes: [{ sha: 'x', message: 'y' }] });
  assert.deepEqual(d.commits, [{ sha: 'x', message: 'y' }]);
});

test('resolveInfo: info.commit (singular) feeds sha when info.sha is missing', () => {
  const d = resolveInfo({ commit: 'aabbccdd' });
  assert.equal(d.sha, 'aabbccdd');
});
