// Voiceover timing helpers for the impact film.
// Every time returned here is scene-relative (like ctx.cue), so scenes stay pure functions of t.
import { TIMELINE } from '../engine.js';

/** Is this VO line in the current cut? (the teaser drops a few lines) */
export const has = (id) => !!TIMELINE.lines[id];

/** Clause time, clamped to the line's last segment (ctx.cue throws on a missing segment). */
export function seg(ctx, id, k = 0, which = 0) {
  const l = ctx.line(id);
  const s = l.segs[Math.max(0, Math.min(k, l.segs.length - 1))];
  return s[which];
}
export const lineStart = (ctx, id) => ctx.line(id).start;
export const lineEnd = (ctx, id) => ctx.line(id).end;

/** seg() when the line exists, otherwise the fallback (a number or a function returning one). */
export function cueOr(ctx, id, fallback, k = 0, which = 0) {
  if (has(id)) return seg(ctx, id, k, which);
  return typeof fallback === 'function' ? fallback() : fallback;
}

// Clause boundaries: character offsets where a new clause starts (after , ; : . ! ? …).
function clauseStarts(text) {
  const out = [];
  const re = /[,;:.!?…]+\s+/g;
  let m;
  while ((m = re.exec(text))) out.push(m.index + m[0].length);
  return out;
}

/**
 * Character anchors that split the line's text into one span per speech segment.
 * Kokoro does not pause at every comma, so segments can hold several clauses: each segment
 * boundary is matched to the clause boundary whose character fraction is closest to the
 * boundary's share of voiced time (monotonic, one boundary per segment break).
 */
const ANCHORS = new Map();
function anchors(id) {
  if (ANCHORS.has(id)) return ANCHORS.get(id);
  const l = TIMELINE.lines[id];
  const text = l.text, T = text.length;
  const segs = l.segs;
  const dur = segs.map(([a, b]) => b - a);
  const V = dur.reduce((s, d) => s + d, 0) || 1;
  const B = clauseStarts(text).filter((b) => b > 0 && b < T);
  const res = [0];
  let acc = 0, from = 0;
  for (let j = 0; j < segs.length - 1; j++) {
    acc += dur[j];
    const F = acc / V;
    let best = -1, bd = Infinity;
    for (let i = from; i < B.length; i++) {
      const left = segs.length - 2 - j; // boundaries still needed after this one
      if (B.length - 1 - i < left) break;
      const d = Math.abs(B[i] / T - F);
      if (d < bd) { bd = d; best = i; }
    }
    if (best < 0) res.push(Math.round(F * T));
    else { res.push(B[best]); from = best + 1; }
  }
  res.push(T);
  ANCHORS.set(id, res);
  return res;
}

/** Character index of `phrase` in line id's text (case-insensitive), searching from `from`; -1 if absent. */
export function findPhrase(id, phrase, from = 0) {
  const l = TIMELINE.lines[id];
  return l ? l.text.toLowerCase().indexOf(phrase.toLowerCase(), from) : -1;
}

/** Scene-relative time of character offset c in line id. */
export function charTime(ctx, id, c) {
  const l = ctx.line(id);
  const A = anchors(id);
  for (let j = 0; j < l.segs.length; j++) {
    if (c < A[j + 1] || j === l.segs.length - 1) { // a phrase starting on an anchor belongs to the next segment
      const [a, b] = l.segs[j];
      const u = Math.max(0, Math.min(1, (c - A[j]) / Math.max(1, A[j + 1] - A[j])));
      return a + u * (b - a);
    }
  }
  return l.end;
}

/**
 * When `phrase` is spoken inside line `id` (scene-relative). Matches case-insensitively;
 * `end: true` returns the time the phrase finishes. Falls back to the line start.
 */
export function mark(ctx, id, phrase, { end = false, from = 0 } = {}) {
  const l = TIMELINE.lines[id];
  const i = l.text.toLowerCase().indexOf(phrase.toLowerCase(), from);
  if (i < 0) return ctx.line(id).start;
  return charTime(ctx, id, end ? i + phrase.length : i);
}
