// Burned-in captions for cuts that ask for them (timeline.captions, e.g. the LinkedIn edit, where most
// people watch muted). Each VO line is split into short chunks at word boundaries (preferring punctuation),
// and each chunk is shown for a share of the line's time proportional to its length; inside a chunk the
// words brighten one by one as they are spoken.
// Lines whose words are already on screen as typography opt out with "caption": false.
import { h, put, prog, E, TIMELINE } from '../engine.js';

const MAX_CHARS = 34;

function chunk(text) {
  const words = text.split(/\s+/).filter(Boolean);
  const out = [];
  let cur = [];
  const len = (ws) => ws.join(' ').length;
  for (const w of words) {
    if (cur.length && len([...cur, w]) > MAX_CHARS) { out.push(cur); cur = []; }
    cur.push(w);
    // break early after punctuation once the chunk has some weight
    if (/[,.:;?!]$/.test(w) && len(cur) >= 18) { out.push(cur); cur = []; }
  }
  if (cur.length) out.push(cur);
  // fold a dangling one-word chunk into the previous one when it still fits
  for (let i = out.length - 1; i > 0; i--) {
    if (out[i].length === 1 && len([...out[i - 1], ...out[i]]) <= MAX_CHARS + 6) { out[i - 1].push(...out[i]); out.splice(i, 1); }
  }
  return out.map((ws) => ws.join(' '));
}

function buildCues() {
  const lines = Object.values(TIMELINE.lines).filter((l) => l.caption !== false).sort((a, b) => a.start - b.start);
  const all = Object.values(TIMELINE.lines).sort((a, b) => a.start - b.start);
  const cues = [];
  for (const l of lines) {
    const parts = chunk(l.text);
    const total = parts.reduce((s, p) => s + p.length, 0);
    const next = all.find((o) => o.start > l.start);
    const hold = Math.min(l.end + 0.35, next ? next.start - 0.05 : l.end + 0.35);
    let t = l.start - 0.05;
    const la = t;
    parts.forEach((p, i) => {
      const d = ((l.end - l.start) * p.length) / total;
      cues.push({ text: p, a: t, e: t + d, b: i === parts.length - 1 ? hold : t + d, la, lb: hold });
      t += d;
    });
  }
  return cues;
}

export function makeCaptions(stage) {
  const cues = buildCues();
  const wrap = h('div', { class: 'layer', style: { zIndex: 800, pointerEvents: 'none' } });
  const box = h('div', { class: 'abs', style: { left: '50%', bottom: '100px', maxWidth: '1700px', padding: '13px 34px 16px', borderRadius: '18px', background: 'rgba(9,9,14,0.62)', backdropFilter: 'blur(22px) saturate(1.3)', border: '1px solid rgba(255,255,255,0.10)', color: '#ffffff', fontSize: '56px', fontWeight: 600, letterSpacing: '-0.008em', lineHeight: '1.25', textAlign: 'center', whiteSpace: 'nowrap', boxShadow: '0 18px 50px -14px rgba(0,0,0,0.75), inset 0 1px 0 rgba(255,255,255,0.06)' } });
  wrap.append(box);
  stage.append(wrap);
  let shown = null, spans = [];
  return (t) => {
    const c = cues.find((q) => t >= q.a && t < q.b);
    if (!c) { box.style.opacity = '0'; shown = null; return; }
    if (shown !== c) {
      // one span per word, each with the moment it is spoken (its share of the chunk, by length)
      box.textContent = '';
      let n = 0;
      spans = c.text.split(' ').map((w, i) => {
        if (i) box.append(' ');
        const el = h('span', {}, w);
        box.append(el);
        const at = c.a + ((c.e - c.a) * n) / c.text.length;
        n += w.length + 1;
        return { el, at };
      });
      shown = c;
    }
    for (const w of spans) w.el.style.opacity = (0.42 + 0.58 * prog(t, w.at - 0.06, 0.14, E.outCubic)).toFixed(3);
    // fade only at the ends of a line; chunks within a line swap in place
    const a = Math.min(prog(t, c.la, 0.1, E.outCubic), 1 - prog(t, c.lb - 0.1, 0.1));
    const fresh = prog(t, c.a, 0.18, E.outCubic);
    box.style.transform = `translateX(-50%) translateY(${((1 - fresh) * 6).toFixed(2)}px)`;
    put(box, { o: a });
  };
}
