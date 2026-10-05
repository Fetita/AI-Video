// Introduction — who Eagerworks is, then a "client work" index of the five projects that follow.
// The hook's hand-off line becomes the divider under the headline, then the underline of row 01,
// and finally hands off (same position) to the search scene's brief card.
import { addScene, h, put, prog, E, clamp, lerp, env } from '../engine.js';
import { words, revealWords } from '../lib/ui.js';

const DISCIPLINES = ['Product strategy', 'UX / UI design', 'Software engineering', 'Cloud & data'];
const PROJECTS = [
  ['Location search & recommendation', 'Generative AI'],
  ['Physical-to-digital storytelling', 'Generative AI'],
  ['Vision data for robotics', 'Computer vision'],
  ['Field & packing-line analytics', 'Real-world AI'],
  ['Evidence review for audits', 'Document AI'],
];
const LINE = { x: 460, y: 483, w: 1000 }; // shared with hook.js (hand-off) and search.js (brief card)
const ROW_H = 70;

addScene({
  id: 'intro',
  pre: 0,
  post: 0.4,
  setup(ctx) {
    const R = ctx.root;
    // ---- who we are
    this.kicker = h('div', { class: 'abs kicker', style: { left: `${LINE.x}px`, top: '300px', color: 'var(--accent)', letterSpacing: '0.24em' } }, 'Who we are');
    this.head = h('div', { class: 'abs display', style: { left: `${LINE.x}px`, top: '372px', width: '1100px', fontSize: '80px', fontWeight: 600, letterSpacing: '-0.02em', lineHeight: '1.08', whiteSpace: 'nowrap', overflow: 'hidden', paddingBottom: '6px' } });
    this.headA = h('div', {}, 'Designers & engineers.');
    this.headB = h('div', { style: { position: 'absolute', left: '0', top: '0' } }, 'Products that run on ', h('span', { style: { color: 'var(--accent)' } }, 'AI'), '.');
    this.head.append(this.headA, this.headB);
    this.sub = h('div', { class: 'abs', style: { left: `${LINE.x}px`, top: '516px', width: '1000px', fontSize: '34px', fontWeight: 430, letterSpacing: '-0.01em', color: 'var(--text2)' } });
    this.subSpans = words(this.sub, 'We build digital products, from the first idea to launch.');
    this.pills = h('div', { class: 'abs', style: { left: `${LINE.x}px`, top: '604px', width: '1100px', display: 'flex', gap: '14px', flexWrap: 'nowrap' } });
    this.pillEls = DISCIPLINES.map((d) => { const el = h('span', { class: 'chip', style: { height: '46px', fontSize: '19px', padding: '0 20px' } }, d); this.pills.append(el); return el; });
    this.aiPill = h('span', { class: 'chip ai', style: { height: '46px', fontSize: '19px', padding: '0 20px', boxShadow: '0 0 24px rgba(212,255,90,0.25)' } }, 'Applied AI');
    this.pills.append(this.aiPill);
    R.append(this.kicker, this.head, this.sub, this.pills);

    // ---- client work index
    this.kicker2 = h('div', { class: 'abs kicker', style: { left: `${LINE.x}px`, top: '238px', color: 'var(--accent)', letterSpacing: '0.24em' } }, 'Client work');
    this.head2 = h('div', { class: 'abs display', style: { left: `${LINE.x}px`, top: '276px', fontSize: '64px', fontWeight: 600, letterSpacing: '-0.02em', lineHeight: '1.1', whiteSpace: 'nowrap' } }, 'Built for our clients.');
    R.append(this.kicker2, this.head2);
    this.rows = PROJECTS.map(([title, kind], i) => {
      const top = LINE.y - ROW_H + i * ROW_H;
      const el = h('div', { class: 'abs', style: { left: `${LINE.x}px`, top: `${top}px`, width: `${LINE.w}px`, height: `${ROW_H}px`, display: 'flex', alignItems: 'center', gap: '28px' } },
        h('span', { class: 'mono', style: { fontSize: '17px', letterSpacing: '0.14em', color: 'var(--accent)', width: '36px' } }, String(i + 1).padStart(2, '0')),
        h('span', { style: { fontSize: '30px', fontWeight: 500, letterSpacing: '-0.01em', color: 'var(--text)', flex: '1' } }, title),
        h('span', { class: 'kicker', style: { fontSize: '13px', color: 'var(--text3)' } }, kind));
      const rule = i === 0 ? null : h('div', { class: 'abs', style: { left: `${LINE.x}px`, top: `${top + ROW_H - 1}px`, width: `${LINE.w}px`, height: '1px', background: 'var(--line2)', transformOrigin: '0 50%' } });
      R.append(el);
      if (rule) R.append(rule);
      return { el, rule };
    });

    // the shared line (divider → row 01 underline → hand-off)
    this.line = h('div', { class: 'abs', style: { left: `${LINE.x}px`, top: `${LINE.y}px`, width: `${LINE.w}px`, height: '2px', background: 'var(--accent)', transformOrigin: '50% 50%', boxShadow: '0 0 16px rgba(212,255,90,0.6)' } });
    R.append(this.line);
  },

  render(t, ctx) {
    const D = ctx.dur;
    const seg = (id, k) => { const s = ctx.line(id).segs; return s[Math.min(k, s.length - 1)][0]; };
    const c1 = seg('i1', 0), c1b = seg('i1', 1), c1c = seg('i1', 2);
    const c2 = seg('i2', 0), c2b = seg('i2', 1), c2end = ctx.line('i2').end;
    const c3 = seg('i3', 0);
    const out1 = prog(t, c3 - 0.55, 0.5, E.inCubic); // "who we are" clears for the client index

    // ---- headline rises out of the line (the headline box clips it just above the divider)
    const hIn = prog(t, c1 - 0.15, 0.7, E.outCubic);
    const swap = prog(t, c2b - 0.1, 0.6, E.inOutCubic);
    put(this.headA, { y: lerp(110, 0, hIn) - swap * 110, o: 1 - swap });
    put(this.headB, { y: lerp(110, 0, swap), o: swap });
    put(this.head, { y: -out1 * 40, o: 1 - out1 });
    put(this.kicker, { y: (1 - prog(t, c1 - 0.1, 0.5, E.outCubic)) * 10 - out1 * 40, o: prog(t, c1 - 0.1, 0.5) * (1 - out1) });

    // ---- sub line + disciplines
    revealWords(this.subSpans, prog(t, c1b - 0.05, c1c + 1.2 - c1b, E.linear), { rise: 8, soft: 2.5 });
    put(this.sub, { y: -out1 * 40, o: 1 - out1 });
    this.pillEls.forEach((el, i) => {
      const q = prog(t, c1b + 0.2 + i * 0.32, 0.45, E.outBack);
      const dim = prog(t, c2end - 0.7, 0.4);
      put(el, { y: (1 - Math.min(q, 1)) * 16, o: clamp(q * 2) * lerp(1, 0.55, dim) });
    });
    const qa = prog(t, c2end - 0.75, 0.5, E.outBack);
    put(this.aiPill, { y: (1 - Math.min(qa, 1)) * 16, s: lerp(0.85, 1, Math.min(qa, 1)), o: clamp(qa * 2) });
    put(this.pills, { y: -out1 * 40, o: 1 - out1 });

    // ---- client work index
    const in2 = prog(t, c3 - 0.2, 0.6, E.outCubic);
    const fadeRows = prog(t, D - 1.25, 0.45, E.inCubic); // rows 02–05 + titles leave, row 01 remains
    put(this.kicker2, { y: (1 - in2) * 14, o: in2 * (1 - fadeRows) });
    put(this.head2, { y: (1 - in2) * 18, o: in2 * (1 - fadeRows) });
    this.rows.forEach((r, i) => {
      const q = prog(t, c3 + 0.1 + i * 0.2, 0.5, E.outCubic);
      const leave = i === 0 ? prog(t, D - 0.7, 0.4, E.inCubic) : fadeRows;
      put(r.el, { x: (1 - q) * 30, o: q * (1 - leave) });
      if (r.rule) { put(r.rule, { sx: prog(t, c3 + 0.1 + i * 0.2, 0.6, E.outCubic), o: 1 - fadeRows }); }
    });
    // row 01 lights up as the film moves into it
    const focus = prog(t, D - 1.25, 0.4);
    this.rows[0].el.children[1].style.color = focus > 0.5 ? '#ffffff' : 'var(--text)';

    // ---- the shared line: full lime at hand-in, quiet hairline-ish while the text plays, lime again at hand-off
    const quiet = env(t, 0.6, D - 1.0, 0.6, 0.6);
    this.line.style.opacity = lerp(1, 0.45, quiet).toFixed(3);
    this.line.style.boxShadow = `0 0 ${lerp(16, 0, quiet).toFixed(1)}px rgba(212,255,90,0.6)`;
  },
});
