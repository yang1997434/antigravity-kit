#!/usr/bin/env node
/**
 * Antigravity CLI HUD — 3-line, 4-column fixed-width statusLine (LA style).
 *
 *   Ultra      ⋮ ctx      28% ⋮ cpu   20% ⋮ Gemini ●○○○○  11% ↻3h04m · 周  3%
 *   medium     ⋮ tok/s     71 ⋮ mem   65% ⋮ Claude ○○○○○   0% ↻4h57m · 周  0%
 *   Carbon 4   ⋮ Cache  95.4% ⋮ disk  58% ⋮ 📁 ~/Documents/Codex/AI_model  ⎇ HEAD*
 *
 * Optional config: ~/.gemini/antigravity-cli/hud/config.json
 *   { "diskPath": "/", "cols": [10, 12, 9], "sep": "⋮", "theme": "light" }
 */

import {
  readFileSync, writeFileSync, statfsSync, mkdirSync, realpathSync, existsSync,
  openSync, fstatSync, readSync, closeSync
} from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { homedir, cpus, totalmem } from 'node:os';
import { join } from 'node:path';

const HOME = homedir();
const AGY_DIR = join(HOME, '.gemini', 'antigravity-cli');
const HUD_DIR = join(AGY_DIR, 'hud');
const SYS_CACHE_PATH = join(HUD_DIR, '.sys-cache.json');
const SESSION_CACHE_PATH = join(HUD_DIR, '.session-cache.json');

const FIVE_HOURS_MS = 5 * 3600_000 + 300_000;
const CACHE_TTL_MS = 3600_000;

function loadJson(path, fallback = {}) {
  try { return JSON.parse(readFileSync(path, 'utf8')); } catch { return fallback; }
}

const CFG = loadJson(join(HUD_DIR, 'config.json'), {});
const SETTINGS = loadJson(join(AGY_DIR, 'settings.json'), {});
const DISK_PATH = typeof CFG.diskPath === 'string' ? CFG.diskPath : '/';
const COLS = Array.isArray(CFG.cols) && CFG.cols.length === 3
  ? CFG.cols.map(Number) : [10, 12, 9];

// ── Theme-aware palette (defaults to crisp bold dark-ink on light terminal) ──
const rgb = (r, g, b) => `\x1b[38;2;${r};${g};${b}m`;
const themePref = String(CFG.theme || SETTINGS.theme || 'light').toLowerCase();
const LIGHT_BG = !themePref.includes('dark');

export const C = LIGHT_BG ? {
  reset: '\x1b[0m', dim: `\x1b[1m${rgb(110, 110, 115)}`, bold: '\x1b[1m',
  blue: `\x1b[1m${rgb(20, 80, 160)}`, orange: `\x1b[1m${rgb(180, 72, 12)}`, green: `\x1b[1m${rgb(18, 110, 32)}`,
  cyan: `\x1b[1m${rgb(14, 116, 128)}`, red: `\x1b[1m${rgb(185, 32, 32)}`, yellow: `\x1b[1m${rgb(158, 106, 0)}`,
  magenta: `\x1b[1m${rgb(105, 48, 168)}`, white: `\x1b[1m${rgb(24, 24, 27)}`, gray: `\x1b[1m${rgb(72, 72, 78)}`,
  dimGray: rgb(142, 142, 148),
} : {
  reset: '\x1b[0m', dim: '\x1b[2m', bold: '\x1b[1m',
  blue: `\x1b[1m${rgb(0, 153, 255)}`, orange: `\x1b[1m${rgb(255, 176, 85)}`, green: `\x1b[1m${rgb(0, 160, 0)}`,
  cyan: `\x1b[1m${rgb(46, 149, 153)}`, red: `\x1b[1m${rgb(255, 85, 85)}`, yellow: `\x1b[1m${rgb(230, 200, 0)}`,
  magenta: `\x1b[1m${rgb(200, 100, 255)}`, white: `\x1b[1m${rgb(220, 220, 220)}`, gray: rgb(148, 148, 148),
  dimGray: rgb(90, 90, 90),
};

const SEP = typeof CFG.sep === 'string' ? CFG.sep : '⋮';
const BAR = SEP ? `${C.dimGray}${SEP}${C.reset}` : '';

// ── Display width & fixed-width alignment ───────────
const ANSI_RE = /\x1b\[[0-9;]*m/g;
const SEG = typeof Intl !== 'undefined' && Intl.Segmenter
  ? new Intl.Segmenter('en', { granularity: 'grapheme' }) : null;

function isWide(cp) {
  return (cp >= 0x1100 && cp <= 0x115F) || (cp >= 0x2E80 && cp <= 0xA4CF)
    || (cp >= 0xAC00 && cp <= 0xD7A3) || (cp >= 0xF900 && cp <= 0xFAFF)
    || (cp >= 0xFE30 && cp <= 0xFE6F) || (cp >= 0xFF00 && cp <= 0xFF60)
    || (cp >= 0xFFE0 && cp <= 0xFFE6) || (cp >= 0x1F300 && cp <= 0x1F9FF)
    || (cp >= 0x1FA70 && cp <= 0x1FAFF) || (cp >= 0x1F1E6 && cp <= 0x1F1FF);
}

export function dispWidth(str) {
  const plain = String(str).replace(ANSI_RE, '');
  let w = 0;
  const clusters = SEG ? [...SEG.segment(plain)].map(s => s.segment) : [...plain];
  for (const g of clusters) {
    const cps = [...g].map(ch => ch.codePointAt(0));
    if (cps.some(isWide)) { w += 2; continue; }
    if (cps[0] === 0x200D || cps[0] === 0xFE0F) continue;
    w += 1;
  }
  return w;
}

export function fit(str, width, align = 'left') {
  const w = dispWidth(str);
  if (w > width) {
    const plain = String(str).replace(ANSI_RE, '');
    let out = '', acc = 0;
    for (const ch of plain) {
      const cw = dispWidth(ch);
      if (acc + cw > width - 1) break;
      out += ch; acc += cw;
    }
    return out + '…' + ' '.repeat(Math.max(0, width - acc - 1));
  }
  const pad = ' '.repeat(width - w);
  return align === 'right' ? pad + str : str + pad;
}

function metric(label, value, width) {
  const gap = Math.max(1, width - dispWidth(label) - dispWidth(value));
  return `${C.white}${label}${C.reset}${' '.repeat(gap)}${value}`;
}

function healthColor(pct) {
  if (pct >= 90) return C.red;
  if (pct >= 75) return C.orange;
  if (pct >= 50) return C.yellow;
  return C.green;
}

function pctVal(pct) {
  return pct == null ? `${C.dim}  —${C.reset}`
    : `${healthColor(pct)}${String(pct).padStart(3)}%${C.reset}`;
}

// ── Dual Quota Pools: Gemini (5h + weekly) & Claude/3P (`3p-5h` + `3p-weekly`) ──
function bucketDiffMs(bucket, nowMs = Date.now()) {
  if (!bucket) return null;
  if (typeof bucket.reset_in_seconds === 'number') return bucket.reset_in_seconds * 1000;
  const raw = bucket.reset_time ?? bucket.resets_at ?? bucket.quota_resets;
  if (raw == null || raw === '') return null;
  let ms;
  if (typeof raw === 'number') ms = raw < 1e12 ? raw * 1000 : raw;
  else if (/^\d+$/.test(String(raw))) ms = Number(raw) < 1e12 ? Number(raw) * 1000 : Number(raw);
  else ms = Date.parse(String(raw));
  return Number.isFinite(ms) ? ms - nowMs : null;
}

export function fmtDurationMs(diffMs) {
  if (diffMs == null || !Number.isFinite(diffMs)) return '';
  if (diffMs <= 0) return 'now';
  const totalMin = Math.floor(diffMs / 60_000);
  const hours = Math.floor(totalMin / 60);
  const mins = totalMin % 60;
  if (hours < 1) return `${mins}m`;
  if (hours < 24) return `${hours}h${String(mins).padStart(2, '0')}m`;
  const days = Math.floor(hours / 24);
  const remHours = hours % 24;
  return remHours > 0 ? `${days}d${remHours}h` : `${days}d`;
}

function bucketUsedPct(b) {
  if (!b || typeof b !== 'object') return null;
  if (typeof b.used_percentage === 'number') return Math.min(100, Math.max(0, b.used_percentage));
  if (typeof b.remaining_fraction === 'number') return Math.min(100, Math.max(0, (1 - b.remaining_fraction) * 100));
  if (typeof b.quota_remaining === 'string' && b.quota_remaining.endsWith('%')) {
    const rem = parseFloat(b.quota_remaining);
    if (Number.isFinite(rem)) return Math.min(100, Math.max(0, 100 - rem));
  }
  return null;
}

function isClaudeOrThirdParty(tag) {
  // Antigravity names the Claude/GPT-OSS quota buckets "3p-5h" and "3p-weekly" ("3p" = third-party).
  return /(?:^|[^a-z0-9])3p(?:[^a-z0-9]|$)|claude|opus|sonnet|haiku|gpt|third[-_ ]?party|anthropic/i.test(tag);
}

function isGeminiPool(tag) {
  return /gemini|carbon|argon|hydrogen|flash|orchestrator/i.test(tag);
}

export function extractQuotaPools(quotaMap, activeModel = '', nowMs = Date.now()) {
  const res = {
    gemini: { fiveH: null, weekly: null },
    claude: { fiveH: null, weekly: null },
    credits: null
  };
  if (!quotaMap || typeof quotaMap !== 'object') return res;

  const activeLow = String(activeModel).toLowerCase();
  const pickBetter = (cur, cand, keyLow) => {
    if (!cur) return cand;
    if (activeLow && (keyLow === activeLow || activeLow.includes(keyLow))) return cand;
    if (cand.usedPct > cur.usedPct) return cand;
    return cur;
  };

  for (const [key, b] of Object.entries(quotaMap)) {
    if (!b || typeof b !== 'object' || b.disabled) continue;
    const tag = `${key} ${b.display_name || ''} ${b.description || ''}`;
    if (/credit/i.test(tag) && typeof b.remaining_amount === 'number') {
      res.credits = b.remaining_amount;
      continue;
    }
    const u = bucketUsedPct(b);
    if (u == null) continue;
    const diffMs = bucketDiffMs(b, nowMs);
    const keyLow = key.toLowerCase();
    const winStr = `${keyLow} ${String(b.window || '').toLowerCase()}`;
    const isWeekly = winStr.includes('week') || winStr.includes('7d')
      || (!winStr.includes('5h') && diffMs != null && diffMs > FIVE_HOURS_MS);

    const item = {
      usedPct: Math.round(u),
      reset: fmtDurationMs(diffMs),
      isWeekly,
    };

    const target = isClaudeOrThirdParty(tag) ? res.claude
      : (isGeminiPool(tag) ? res.gemini
      : (isClaudeOrThirdParty(activeLow) ? res.claude : res.gemini));

    if (isWeekly) target.weekly = pickBetter(target.weekly, item, keyLow);
    else target.fiveH = pickBetter(target.fiveH, item, keyLow);
  }
  return res;
}

function quotaCircles(pct) {
  const clamped = Math.min(100, Math.max(0, pct));
  const full = clamped <= 0 ? 0 : Math.max(1, Math.round(clamped / 20));
  const clr = healthColor(clamped);
  return `${clr}${'●'.repeat(full)}${C.dimGray}${'○'.repeat(5 - full)}${C.reset}`;
}

// Renders `Gemini ●○○○○  11% ↻3h04m · 周  3%` (and if only weekly is present, shows weekly directly).
function renderPoolRow(label, poolGroup, isActivePool, resetPadW = 5, credits = null) {
  const nameClr = isActivePool ? C.white : C.gray;
  const pad = ' '.repeat(Math.max(0, 6 - dispWidth(label)));
  const head = `${nameClr}${label}${C.reset}${pad}`;
  const main = poolGroup?.fiveH || poolGroup?.weekly;
  if (!main || typeof main.usedPct !== 'number') {
    return `${head} ${C.dimGray}○○○○○${C.reset} ${C.dim}  —${C.reset}`;
  }
  const p = main.usedPct;
  const onlyWeekly = !poolGroup?.fiveH && Boolean(poolGroup?.weekly);
  let resetPart = '';
  if (main.reset) {
    const rPad = ' '.repeat(Math.max(0, resetPadW - dispWidth(main.reset)));
    resetPart = onlyWeekly
      ? ` ${C.orange}↻周限 ${main.reset}${C.reset}${rPad}`
      : ` ${C.gray}↻${main.reset}${C.reset}${rPad}`;
  }
  let weekPart = '';
  if (poolGroup?.fiveH && poolGroup?.weekly) {
    const wp = poolGroup.weekly.usedPct;
    const wReset = wp >= 75 && poolGroup.weekly.reset ? ` ${C.orange}↻${poolGroup.weekly.reset}${C.reset}` : '';
    weekPart = ` ${C.dimGray}·${C.reset} ${C.gray}周${C.reset}${healthColor(wp)}${String(wp).padStart(3)}%${C.reset}${wReset}`;
  }
  const credPart = credits != null ? ` ${C.cyan}· 积分 ${credits}${C.reset}` : '';
  return `${head} ${quotaCircles(p)} ${healthColor(p)}${String(p).padStart(3)}%${C.reset}${resetPart}${weekPart}${credPart}`;
}

// ── Model & Effort parsing ──────────────────────────
export function parseModelAndEffort(modelObj) {
  const rawDisplay = String(modelObj?.display_name || modelObj?.id || '').trim();
  const rawId = String(modelObj?.id || rawDisplay).toLowerCase();

  let effort = String(modelObj?.effort || '').toLowerCase();
  const parenMatch = rawDisplay.match(/\((low|medium|high|xhigh|max)\)\s*$/i);
  if (!effort && parenMatch) effort = parenMatch[1].toLowerCase();

  let clean = rawDisplay
    .replace(/\s*\([^)]*\)\s*$/g, '')
    .replace(/\s*\[[^\]]*\]\s*$/g, '')
    .trim();

  const gemMatch = clean.match(/^Gemini\s+(\d+(?:\.\d+)?)\s+(.+)$/i);
  if (gemMatch) clean = `${gemMatch[2]} ${gemMatch[1]}`;
  else clean = clean.replace(/^Claude\s+/i, '');

  return { name: clean || 'Auto', effort, rawId };
}

export function formatIdentity(stdin, settings = SETTINGS) {
  const tierRaw = String(stdin?.plan_tier || '').trim();
  if (tierRaw) {
    const cleanTier = tierRaw
      .replace(/^google\s+ai\s+/i, '')
      .replace(/^g1_/i, '')
      .replace(/_tier$/i, '');
    if (cleanTier) return cleanTier.charAt(0).toUpperCase() + cleanTier.slice(1).toLowerCase();
  }
  if (typeof stdin?.email === 'string' && stdin.email.includes('@')) {
    return stdin.email.split('@')[0];
  }
  return settings?.gcp?.project || 'Ultra';
}

// ── System stats (macOS / Linux) ────────────────────
function cpuSampleFromCpus(list) {
  if (!Array.isArray(list) || !list.length) return null;
  let total = 0, idle = 0;
  for (const c of list) { for (const v of Object.values(c.times)) total += v; idle += c.times.idle; }
  return { total, idle, ts: Date.now() };
}

function getCpuPct() {
  let prev = loadJson(SYS_CACHE_PATH, {})?.cpu;
  let now = cpuSampleFromCpus(cpus());
  if (!now) return null;
  if (!prev || (now.ts - prev.ts) >= 600_000 || now.total <= prev.total) {
    prev = now;
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 40);
    now = cpuSampleFromCpus(cpus());
  }
  let pct = null;
  const totalDiff = now.total - prev.total;
  const idleDiff = now.idle - prev.idle;
  if (totalDiff > 0) pct = Math.max(0, Math.min(100, Math.round((1 - idleDiff / totalDiff) * 100)));
  try {
    mkdirSync(HUD_DIR, { recursive: true });
    const cache = loadJson(SYS_CACHE_PATH, {});
    cache.cpu = now;
    writeFileSync(SYS_CACHE_PATH, JSON.stringify(cache));
  } catch { /* ignore */ }
  return pct;
}

export function memPctFromVmStat(text, totalBytes) {
  const page = Number((text.match(/page size of (\d+) bytes/) || [])[1]);
  const pages = (key) => Number((text.match(new RegExp(`^${key}:\\s+(\\d+)\\.`, 'm')) || [])[1]);
  const used = pages('Pages active') + pages('Pages wired down') + pages('Pages occupied by compressor');
  if (!page || !totalBytes || Number.isNaN(used)) return null;
  return Math.max(0, Math.min(100, Math.round((used * page / totalBytes) * 100)));
}

function getMemPct() {
  if (process.platform !== 'darwin') return null;
  try {
    return memPctFromVmStat(execFileSync('vm_stat', { encoding: 'utf8', timeout: 800 }), totalmem());
  } catch { return null; }
}

function getDiskPct(path) {
  try {
    const s = statfsSync(path);
    const total = Number(s.blocks) * Number(s.bsize);
    if (!total) return null;
    return Math.round(((total - Number(s.bavail) * Number(s.bsize)) / total) * 100);
  } catch { return null; }
}

// ── Transcript incremental scanner (tok/s + prompt Cache %) ──
export function freshState(path) {
  return {
    path, offset: 0, ino: null, pending: null,
    out: 0, cacheRead: 0, uncachedIn: 0, lastPlannerTs: null,
    recent: [], touched: Date.now()
  };
}

export function scanTranscript(st, nowMs = Date.now()) {
  let fd, buf, mtimeMs = null;
  try {
    fd = openSync(st.path, 'r');
    const stat = fstatSync(fd);
    const { size, ino } = stat;
    mtimeMs = stat.mtimeMs;
    if (size < st.offset || (st.ino != null && ino !== st.ino)) st = freshState(st.path);
    st.ino = ino;
    if (size <= st.offset) return st;
    buf = Buffer.alloc(size - st.offset);
    buf = buf.subarray(0, readSync(fd, buf, 0, buf.length, st.offset));
  } catch { return st; }
  finally { if (fd !== undefined) closeSync(fd); }

  const end = buf.lastIndexOf(10) + 1;
  if (end === 0) return st;

  for (const line of buf.subarray(0, end).toString('utf8').split('\n')) {
    if (!line) continue;
    let d;
    try { d = JSON.parse(line); } catch { continue; }
    const ts = d.created_at ? Date.parse(d.created_at) : null;

    if (st.pending && ts != null) {
      if (d.type !== 'USER_INPUT') {
        const dur = ts - st.pending.start;
        if (st.pending.out > 0 && dur >= 1000 && dur < 600_000) {
          st.recent.push({ out: st.pending.out, dur });
          if (st.recent.length > 5) st.recent.shift();
        }
      }
      st.pending = null;
    }

    if (d.type === 'PLANNER_RESPONSE') {
      const outTok = typeof d.output_tokens === 'number' ? d.output_tokens : 0;
      const inTok = typeof d.input_tokens === 'number' ? d.input_tokens : 0;
      const crTok = typeof d.cache_read_tokens === 'number' ? d.cache_read_tokens : 0;
      st.out += outTok;
      st.uncachedIn += inTok;
      st.cacheRead += crTok;
      if (ts != null) st.lastPlannerTs = ts;
      if (outTok > 0 && ts != null) {
        st.pending = { start: ts, out: outTok };
      }
    }
  }
  if (st.pending && mtimeMs != null && Math.abs(nowMs - mtimeMs) < 10_000) {
    const dur = mtimeMs - st.pending.start;
    if (st.pending.out > 0 && dur >= 1000 && dur < 600_000) {
      st.recent.push({ out: st.pending.out, dur });
      if (st.recent.length > 5) st.recent.shift();
      st.pending = null;
    }
  }
  st.offset += end;
  st.touched = nowMs;
  return st;
}

export function resolveTranscriptPath(stdin, geminiRoot = join(HOME, '.gemini')) {
  const raw = typeof stdin?.transcript_path === 'string' ? stdin.transcript_path : '';
  if (raw && existsSync(raw)) return raw;

  const candidates = [];
  if (raw) {
    for (const surface of ['antigravity-cli', 'antigravity', 'antigravity-ide']) {
      candidates.push(raw.replace(/\/\.gemini\/antigravity(?:-cli|-ide)?\//, `/.gemini/${surface}/`));
    }
  }
  const convId = stdin?.conversation_id || stdin?.session_id;
  if (convId) {
    for (const surface of ['antigravity-cli', 'antigravity', 'antigravity-ide']) {
      candidates.push(join(geminiRoot, surface, 'brain', convId, '.system_generated', 'logs', 'transcript.jsonl'));
    }
  }
  for (const c of candidates) {
    if (c && existsSync(c)) return c;
  }
  return raw || candidates[0] || null;
}

function sessionStats(stdin, nowMs = Date.now()) {
  const convId = stdin.conversation_id || stdin.session_id;
  const path = resolveTranscriptPath(stdin);
  if (!path) return { tps: null, cachePct: null, cacheWarm: true };

  const all = loadJson(SESSION_CACHE_PATH, {});
  const key = convId || path;
  let st = all[key];
  if (!st || st.path !== path || typeof st.cacheRead !== 'number') st = freshState(path);
  st = scanTranscript(st, nowMs);
  all[key] = st;
  try {
    mkdirSync(HUD_DIR, { recursive: true });
    const cutoff = nowMs - 86_400_000;
    for (const k of Object.keys(all)) if ((all[k]?.touched ?? 0) < cutoff) delete all[k];
    writeFileSync(SESSION_CACHE_PATH, JSON.stringify(all));
  } catch { /* ignore */ }

  const win = st.recent.slice(-5);
  const outSum = win.reduce((a, r) => a + r.out, 0);
  const durSum = win.reduce((a, r) => a + r.dur, 0);
  const tps = durSum > 0 ? (outSum / (durSum / 1000)) : null;

  const totalPrompt = st.cacheRead + st.uncachedIn;
  const cachePct = totalPrompt > 0 ? (st.cacheRead / totalPrompt) * 100 : null;
  const cacheWarm = st.lastPlannerTs == null || (nowMs - st.lastPlannerTs) <= CACHE_TTL_MS;
  return { tps, cachePct, cacheWarm };
}

export function fallbackCachePctFromUsage(contextWindow) {
  const cu = contextWindow?.current_usage;
  if (!cu || typeof cu !== 'object') return null;
  const cr = typeof cu.cache_read_input_tokens === 'number' ? cu.cache_read_input_tokens : 0;
  const inp = typeof cu.input_tokens === 'number' ? cu.input_tokens : 0;
  const cc = typeof cu.cache_creation_input_tokens === 'number' ? cu.cache_creation_input_tokens : 0;
  const tot = cr + inp + cc;
  return tot > 0 ? (cr / tot) * 100 : null;
}

// ── Path & Subagent suffix formatting ───────────────
const CWD_MAX = 40;

export function fmtCwd(cwd) {
  if (!cwd) return '';
  const p = cwd.startsWith(HOME) ? '~' + cwd.slice(HOME.length) : cwd;
  if (p.length <= CWD_MAX) return p;
  const segs = p.split('/').filter(Boolean);
  if (segs.length >= 4) {
    const lead = p.startsWith('/') ? '/' : (p.startsWith('~') ? '~/' : '');
    const head = p.startsWith('~') ? '' : segs[0];
    const cand = `${lead}${head}${head ? '/' : ''}…/${segs.slice(-2).join('/')}`;
    if (cand.length <= CWD_MAX) return cand;
  }
  return '…' + p.slice(p.length - (CWD_MAX - 1));
}

function renderTaskSuffix(stdin) {
  const subs = Array.isArray(stdin.subagents) ? stdin.subagents : [];
  const runSubs = subs.filter(s => s && s.status === 'running').length;
  const bg = Number(stdin.bg_tasks ?? stdin.task_count ?? 0);
  if (runSubs <= 0 && bg <= 0) return '';
  const parts = [];
  if (runSubs > 0) parts.push(`${runSubs} sub`);
  if (bg > 0) parts.push(`${bg} bg`);
  return `  ${C.cyan}⚙ ${parts.join(' · ')}${C.reset}`;
}

export function buildGrid(stdin, sys = null, sessOverride = null, nowMs = Date.now()) {
  const sess = sessOverride || sessionStats(stdin, nowMs);
  const cpuPct = sys ? sys.cpu : getCpuPct();
  const memPct = sys ? sys.mem : getMemPct();
  const diskPct = sys ? sys.disk : getDiskPct(DISK_PATH);

  // Column 1: Identity, Effort, Model
  const rawIdentity = formatIdentity(stdin);
  const idCell = fit(`${C.white}${rawIdentity}${C.reset}`, COLS[0]);

  const { name: modelName, effort, rawId } = parseModelAndEffort(stdin.model || { display_name: SETTINGS.model });
  const effColor = { low: C.green, medium: C.cyan, high: C.blue, xhigh: C.magenta, max: C.red }[effort] || C.white;
  const effCell = fit(effort ? `${effColor}${effort}${C.reset}` : `${C.dim}—${C.reset}`, COLS[0]);

  let modelColor = C.cyan;
  if (/carbon|pro|opus/i.test(rawId)) modelColor = C.magenta;
  else if (/lite|haiku/i.test(rawId)) modelColor = C.green;
  const modelCell = fit(`${modelColor}${modelName}${C.reset}`, COLS[0]);

  // Column 2: ctx %, tok/s, Cache % (falls back to stdin.context_window.current_usage instantly)
  const cw = stdin.context_window;
  const ctxPct = cw
    ? (typeof cw.used_percentage === 'number'
        ? Math.min(100, Math.max(0, Math.round(cw.used_percentage)))
        : (cw.context_window_size > 0
            ? Math.round(((cw.total_input_tokens || 0) / cw.context_window_size) * 100) : null))
    : null;
  const ctxCell = metric('ctx', pctVal(ctxPct), COLS[1]);

  const tpsCell = sess.tps == null
    ? metric('tok/s', `${C.dim}   —${C.reset}`, COLS[1])
    : metric('tok/s', `${C.cyan}${String(Math.round(sess.tps)).padStart(4)}${C.reset}`, COLS[1]);

  const rawCh = typeof stdin.prompt_cache?.hit_ratio === 'number'
    ? stdin.prompt_cache.hit_ratio * 100
    : (sess.cachePct ?? fallbackCachePctFromUsage(cw));
  const chPct = rawCh == null ? null : Math.round(rawCh * 10) / 10;
  const warm = stdin.prompt_cache?.warm !== false && sess.cacheWarm !== false;
  const cacheCell = chPct == null
    ? metric('Cache', `${C.dim}    —${C.reset}`, COLS[1])
    : metric('Cache', `${warm ? healthColor(100 - chPct) : C.dim}${chPct.toFixed(1).padStart(5)}%${C.reset}`, COLS[1]);

  // Column 3: cpu, mem, disk
  const cpuCell = metric('cpu', pctVal(cpuPct), COLS[2]);
  const memCell = metric('mem', pctVal(memPct), COLS[2]);
  const diskCell = metric('disk', pctVal(diskPct), COLS[2]);

  // Column 4: Dual Quota Pools (Gemini 5h+weekly, Claude/3p 5h+weekly) + CWD / Git / Subagents
  const pools = extractQuotaPools(stdin.quota, rawId, nowMs);
  const activeIsClaude = isClaudeOrThirdParty(rawId);
  const r1 = (pools.gemini.fiveH || pools.gemini.weekly)?.reset || '';
  const r2 = (pools.claude.fiveH || pools.claude.weekly)?.reset || '';
  const resetPadW = Math.max(dispWidth(r1), dispWidth(r2));
  const gemRow = renderPoolRow('Gemini', pools.gemini, !activeIsClaude, resetPadW, pools.credits);
  const cldRow = renderPoolRow('Claude', pools.claude, activeIsClaude, resetPadW, null);

  const cwd = stdin.workspace?.current_dir ?? stdin.cwd ?? '';
  const branch = stdin.vcs?.branch || '';
  const dirty = stdin.vcs?.dirty ? `${C.orange}*${C.reset}` : '';
  const vcsSuffix = branch ? `  ${C.gray}⎇ ${C.white}${branch}${C.reset}${dirty}` : '';
  const taskSuffix = renderTaskSuffix(stdin);
  const cwdCell = cwd ? `📁 ${C.white}${fmtCwd(cwd)}${C.reset}${vcsSuffix}${taskSuffix}` : taskSuffix.trimStart();

  const joiner = BAR ? ` ${BAR} ` : '   ';
  return [
    [idCell, ctxCell, cpuCell, gemRow].join(joiner),
    [effCell, tpsCell, memCell, cldRow].join(joiner),
    [modelCell, cacheCell, diskCell, cwdCell].join(joiner),
  ];
}

async function readStdin() {
  if (process.stdin.isTTY) return null;
  const chunks = [];
  try {
    process.stdin.setEncoding('utf8');
    for await (const chunk of process.stdin) chunks.push(chunk);
    const raw = chunks.join('');
    return raw.trim() ? JSON.parse(raw) : null;
  } catch { return null; }
}

async function main() {
  const stdin = await readStdin();
  if (!stdin) process.exit(0);
  const lines = buildGrid(stdin);
  if (lines.length) console.log(lines.join('\n'));
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) main();
