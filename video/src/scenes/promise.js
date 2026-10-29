// 07 — How we work: the personal beat before the finale.
// "Not just another AI studio." ("another AI studio." fades and blurs away word by word), then the headline
// rises and three pillars light up as they're spoken: Listen → Adapt → Stay.
import { addScene, h, put, prog, E, clamp, lerp, env } from '../engine.js';
import { words, revealWords } from '../lib/ui.js';

const PILLARS = [
  ['Listen', 'Your people, your users, and the problem behind the request.'],
  ['Adapt', 'Flexible and agile, as your needs change.'],
  ['Stay', 'Side by side, until it really works.'],
];
const COL_W = 470, COL_GAP = 70;
const COLS_X = (1920 - (3 * COL_W + 2 * COL_GAP)) / 2;
const COLS_Y = 500;

addScene({
  id: 'promise',
  pre: 0.2,
  post: 0.3,
  setup(ctx) {
    const R = ctx.root;
    this.glow = h('div', { class: 'layer', style: { background: 'radial-gradient(ellipse 45% 40% at 50% 52%, rgba(130,52,254,0.13), transparent 70%)' } });
    R.append(this.glow);

    // ---- headline
    this.kicker = h('div', { class: 'abs kicker', style: { left: '0', width: '1920px', top: '380px', textAlign: 'center', color: 'var(--accent-text)', letterSpacing: '0.24em' } }, 'How we work');
    this.otherWords = ['another', 'AI', 'studio.'].map((w) => h('span', { style: { display: 'inline-block' } }, w));
    this.other = h('span', { style: { color: 'var(--text3)', display: 'inline-flex', gap: '0.26em' } }, ...this.otherWords);
    this.head = h('div', { class: 'abs display', style: { left: '0', width: '1920px', top: '438px', textAlign: 'center', fontSize: '104px', fontWeight: 600, letterSpacing: '-0.02em', lineHeight: '1.08', whiteSpace: 'nowrap', transformOrigin: '50% 50%' } },
      'Not just ', this.other);
    R.append(this.kicker, this.head);

    // ---- pillars
    this.cols = PILLARS.map(([word, desc], i) => {
      const el = h('div', { class: 'abs', style: { left: `${COLS_X + i * (COL_W + COL_GAP)}px`, top: `${COLS_Y}px`, width: `${COL_W}px` } });
      const num = h('div', { class: 'tnum', style: { fontSize: '16px', letterSpacing: '0.16em', color: 'var(--accent-text)' } }, String(i + 1).padStart(2, '0'));
      const title = h('div', { style: { fontFamily: 'var(--font-ui)', fontSize: '92px', fontWeight: 600, letterSpacing: '-0.035em', lineHeight: '1.15', color: '#ffffff', margin: '8px 0 18px' } }, word);
      const rule = h('div', { style: { position: 'relative', height: '2px', background: 'var(--line2)' } });
      const fill = h('i', { style: { position: 'absolute', left: '0', top: '0', height: '2px', width: '100%', background: 'var(--accent)', boxShadow: '0 0 12px rgba(130,52,254,0.7)', transformOrigin: '0 50%', display: 'block' } });
      rule.append(fill);
      const text = h('div', { style: { fontSize: '28px', fontWeight: 430, lineHeight: '1.42', letterSpacing: '-0.005em', color: 'var(--text)', marginTop: '24px', width: `${COL_W - 20}px` } });
      const spans = words(text, desc);
      el.append(num, title, rule, text);
      R.append(el);
      return { el, title, fill, text, spans };
    });
  },

  render(t, ctx) {
    const D = ctx.dur;
    const L = (id) => ctx.line(id);
    const c1 = L('p1').start, c1e = L('p1').end, c2 = L('p2').start;
    const out = prog(t, D - 0.95, 0.6, E.inCubic);

    this.glow.style.opacity = (env(t, 0, D, 1.2, 0.9) * lerp(0.7, 1, 0.5 + 0.5 * Math.sin(t * 1.3))).toFixed(3);

    // ---- headline: rises in, "another AI studio." recedes, then it moves up above the pillars
    const hIn = prog(t, c1 - 0.25, 0.8, E.outCubic);
    const move = prog(t, c2 - 0.75, 0.9, E.inOutCubic);
    put(this.kicker, { y: (1 - hIn) * 12 - move * 30, o: hIn * (1 - move) });
    put(this.head, { y: (1 - hIn) * 30 + lerp(0, -190, move) - out * 40, s: lerp(1, 0.62, move), o: hIn * (1 - out) });
    this.otherWords.forEach((w, i) => {
      const k = prog(t, c1e - 0.95 + i * 0.16, 0.6, E.inOutCubic);
      w.style.opacity = lerp(1, 0.22, k).toFixed(3);
      w.style.filter = k > 0 ? `blur(${(k * 5).toFixed(2)}px)` : 'none';
      w.style.transform = `translateY(${(k * 10).toFixed(1)}px)`;
    });

    // ---- pillars: each lights up with its line; all three settle together at the end
    const lines = ['p2', 'p3', 'p4'];
    const allOn = prog(t, L('p4').end + 0.2, 0.6);
    this.cols.forEach((c, i) => {
      const li = L(lines[i]);
      const a = i === 0 ? li.start + 0.1 : li.start - 0.3;
      const q = prog(t, a, 0.7, E.outCubic);
      const next = lines[i + 1] ? L(lines[i + 1]).start - 0.3 : Infinity;
      const dim = prog(t, next, 0.5) * (1 - allOn);
      put(c.el, { y: (1 - q) * 34 - out * 30, o: q * lerp(1, 0.5, dim) * (1 - out) });
      put(c.fill, { sx: Math.max(prog(t, a + 0.25, 0.8, E.inOutCubic), 0.0001) });
      c.title.style.textShadow = q > 0.5 && dim < 0.5 ? `0 0 34px rgba(130,52,254,${(0.45 * (1 - dim)).toFixed(3)})` : 'none';
      // description follows the narration (p2 starts its list after "We start by listening")
      const r0 = i === 0 ? li.segs[1][0] - 0.1 : li.start;
      revealWords(c.spans, prog(t, r0, li.end - r0 + 0.2, E.linear), { rise: 8, soft: 2.5 });
    });
  },
});
