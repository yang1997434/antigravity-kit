import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import {
  C, dispWidth, parseModelAndEffort, extractQuotaPools, freshState, scanTranscript,
  buildGrid, formatIdentity, resolveTranscriptPath, fallbackCachePctFromUsage
} from './hud.mjs';

const ANSI_RE = /\x1b\[[0-9;]*m/g;
const strip = (s) => s.replace(ANSI_RE, '');

test('default palette uses bold dark-ink text instead of washed-out light-white', () => {
  assert.match(C.white, /^\x1b\[1m\x1b\[38;2;24;24;27m$/);
  assert.match(C.green, /^\x1b\[1m/);
});

test('formatIdentity prefers personal plan_tier and email over stale gcp.project', () => {
  assert.equal(formatIdentity({ plan_tier: 'Google AI Ultra', email: 'dev@example.com' }, { gcp: { project: 'demo-gcp-project' } }), 'Ultra');
  assert.equal(formatIdentity({ email: 'dev@example.com' }, { gcp: { project: 'demo-gcp-project' } }), 'dev');
});

test('parseModelAndEffort extracts effort from display_name parens and compacts Gemini name', () => {
  const r = parseModelAndEffort({ id: 'Gemini 4 Carbon (Medium)', display_name: 'Gemini 4 Carbon (Medium)' });
  assert.equal(r.name, 'Carbon 4');
  assert.equal(r.effort, 'medium');
});

test('extractQuotaPools maps real agy 3p-5h / 3p-weekly / gemini-5h / gemini-weekly buckets', () => {
  const now = 1_700_000_000_000;
  const pools = extractQuotaPools({
    '3p-5h': { remaining_fraction: 1, reset_in_seconds: 17870 },
    '3p-weekly': { remaining_fraction: 1, reset_in_seconds: 604670 },
    'gemini-5h': { remaining_fraction: 0.8934, reset_in_seconds: 11054 },
    'gemini-weekly': { remaining_fraction: 0.9717, reset_in_seconds: 597854 },
    'ai_credits': { remaining_amount: 450 },
  }, 'Gemini 4 Carbon (Medium)', now);

  assert.deepEqual(pools.gemini.fiveH, { usedPct: 11, reset: '3h04m', isWeekly: false });
  assert.deepEqual(pools.gemini.weekly, { usedPct: 3, reset: '6d22h', isWeekly: true });
  assert.deepEqual(pools.claude.fiveH, { usedPct: 0, reset: '4h57m', isWeekly: false });
  assert.deepEqual(pools.claude.weekly, { usedPct: 0, reset: '6d23h', isWeekly: true });
  assert.equal(pools.credits, 450);
});

test('fallbackCachePctFromUsage computes instant Cache % from stdin current_usage when transcript is unavailable', () => {
  const pct = fallbackCachePctFromUsage({
    current_usage: { input_tokens: 2049, output_tokens: 266, cache_creation_input_tokens: 0, cache_read_input_tokens: 286116 }
  });
  assert.equal(Math.round(pct * 10) / 10, 99.3);
  assert.equal(fallbackCachePctFromUsage({}), null);
});

test('buildGrid aligns Gemini/Claude 5h+weekly pools and falls back to current_usage Cache %', () => {
  const sys = { cpu: 20, mem: 64, disk: 61 };
  const rowsA = buildGrid({
    plan_tier: 'Google AI Ultra',
    model: { id: 'Gemini 4 Carbon (Medium)', display_name: 'Gemini 4 Carbon (Medium)' },
    context_window: {
      used_percentage: 27.5,
      current_usage: { input_tokens: 2049, cache_read_input_tokens: 286116 }
    },
    quota: {
      'gemini-5h': { remaining_fraction: 0.8934, reset_in_seconds: 11054 },
      'gemini-weekly': { remaining_fraction: 0.9717, reset_in_seconds: 597854 },
      '3p-5h': { remaining_fraction: 1.0, reset_in_seconds: 17870 },
      '3p-weekly': { remaining_fraction: 1.0, reset_in_seconds: 604670 },
    },
    subagents: [{ name: 'coder', status: 'running' }, { name: 'checker', status: 'running' }],
    bg_tasks: 1,
    vcs: { branch: 'main', dirty: true },
    cwd: '/Users/demo/workspace/my-project',
  }, sys, { tps: 71, cachePct: null, cacheWarm: true });

  const sepPositions = (row) => {
    const plain = strip(row);
    const idxs = [];
    for (let i = 0; i < plain.length; i++) if (plain[i] === '⋮') idxs.push(dispWidth(plain.slice(0, i)));
    return idxs;
  };
  const expected = sepPositions(rowsA[0]);
  for (const r of rowsA) {
    assert.deepEqual(sepPositions(r), expected, `misaligned row: ${strip(r)}`);
  }

  assert.match(strip(rowsA[0]), /Gemini ●○○○○  11% ↻3h04m · 周  3%$/);
  assert.match(strip(rowsA[1]), /Claude ○○○○○   0% ↻4h57m · 周  0%$/);
  assert.match(strip(rowsA[2]), /Cache  99\.3%/);
  assert.match(strip(rowsA[2]), /⎇ main\*  ⚙ 2 sub · 1 bg$/);
});

test('scanTranscript incrementally computes tok/s, ignores USER_INPUT pause, and computes Cache %', () => {
  const dir = mkdtempSync(join(tmpdir(), 'hud-test-'));
  try {
    const p = join(dir, 'transcript.jsonl');
    writeFileSync(p, [
      JSON.stringify({ type: 'USER_INPUT', created_at: '2026-11-18T02:00:00Z' }),
      JSON.stringify({
        type: 'PLANNER_RESPONSE',
        created_at: '2026-11-18T02:00:00Z',
        input_tokens: 2000,
        cache_read_tokens: 98000,
        output_tokens: 500
      }),
      JSON.stringify({ type: 'GENERIC', created_at: '2026-11-18T02:00:05Z' }),
      JSON.stringify({ type: 'PLANNER_RESPONSE', created_at: '2026-11-18T02:00:06Z', output_tokens: 400 }),
      JSON.stringify({ type: 'USER_INPUT', created_at: '2026-11-18T02:05:06Z' }),
    ].join('\n') + '\n');
    let st = freshState(p);
    st = scanTranscript(st, Date.parse('2026-11-18T03:00:00Z'));
    assert.equal(st.cacheRead, 98000);
    assert.equal(st.uncachedIn, 2000);
    assert.equal(st.recent.length, 1);
    assert.equal(Math.round(st.recent[0].out / (st.recent[0].dur / 1000)), 100);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('resolveTranscriptPath falls back from .gemini/antigravity/ to actual .gemini/antigravity-cli/ file', () => {
  const root = mkdtempSync(join(tmpdir(), 'gemini-root-'));
  try {
    const convId = 'ec9305ec-167b-4f7b-a464-1d3e45536f52';
    const realDir = join(root, 'antigravity-cli', 'brain', convId, '.system_generated', 'logs');
    mkdirSync(realDir, { recursive: true });
    const realFile = join(realDir, 'transcript.jsonl');
    writeFileSync(realFile, '');

    const wrongPath = join(root, 'antigravity', 'brain', convId, '.system_generated', 'logs', 'transcript.jsonl');
    assert.equal(resolveTranscriptPath({ conversation_id: convId, transcript_path: wrongPath }, root), realFile);
    assert.equal(resolveTranscriptPath({ conversation_id: 'missing-id', transcript_path: '/no/such/file.jsonl' }, root), '/no/such/file.jsonl');
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
