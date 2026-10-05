// 06 — Our own products: the in-house packing-line vision system, shown with its real footage.
// Title card → live monitor playing the object counter (per-apple IDs + running total),
// then a wipe to the line-crossing counter, with a "what it does" column keyed to the VO.
import { addScene, h, put, prog, E, clamp, lerp, env } from '../engine.js';
import { makeHud } from '../lib/ui.js';
import { makeClip } from '../lib/clip.js';

const CLIP_FRAMES = 303; // 10.1 s at 30 fps (scripts/extract_clips.sh)
const PANEL = { x: 110, y: 168, w: 1280, h: 730 }; // video body; the 52 px header sits above it
const FEATURES = [
  ['Detect', 'Every apple, in every crate.'],
  ['Track', 'Its own ID, from entry to exit.'],
  ['Count', 'A running total, live.'],
  ['Line count', 'Counted once, as it crosses the line.'],
];

addScene({
  id: 'inhouse',
  pre: 0.2,
  post: 0.3,
  setup(ctx) {
    const R = ctx.root;
    const seg = (id, k) => { const s = ctx.line(id).segs; return s[Math.min(k, s.length - 1)][0]; };
    this.at = [seg('o3', 0), seg('o3', 1), seg('o3', 2), seg('o4', 0)];
    this.hud = makeHud(ctx, {
      num: '06', title: 'Computer vision · Counting · Tracking', badge: 'Our product',
      steps: FEATURES.map(([label], i) => ({ label, at: this.at[i] })),
    });

    // ---- title card
    this.card = h('div', { class: 'abs', style: { left: '0', top: '0', width: '1920px', height: '1080px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '26px' } });
    this.cardKicker = h('div', { class: 'kicker', style: { color: 'var(--accent)', letterSpacing: '0.24em' } }, 'Our own products');
    this.cardHead = h('div', { class: 'display', style: { fontSize: '108px', fontWeight: 600, letterSpacing: '-0.02em', lineHeight: '1' } }, 'Built in-house.');
    this.cardLine = h('div', { style: { width: '220px', height: '3px', background: 'var(--accent)', boxShadow: '0 0 16px rgba(212,255,90,0.6)', borderRadius: '2px' } });
    this.card.append(this.cardKicker, this.cardHead, this.cardLine);
    R.append(this.card);

    // ---- live monitor
    this.panel = h('div', { class: 'panel', style: { left: `${PANEL.x}px`, top: `${PANEL.y - 52}px`, width: `${PANEL.w}px`, transformOrigin: '50% 50%' } });
    this.mode = h('span', { class: 'kicker' }, 'Mode · Object counter');
    const head = h('div', { class: 'panel-head' },
      h('span', { class: 'dots' }, h('i'), h('i'), h('i')), h('span', { class: 'title' }, 'Packing line · Overhead camera'), h('span', { class: 'spacer' }),
      this.mode,
      h('span', { style: { display: 'flex', alignItems: 'center', gap: '8px', marginLeft: '18px' } },
        h('i', { style: { width: '8px', height: '8px', borderRadius: '50%', background: 'var(--coral)', display: 'block' } }), h('span', { class: 'kicker', style: { color: 'var(--text2)' } }, 'Live')));
    this.body = h('div', { style: { position: 'relative', width: `${PANEL.w}px`, height: `${PANEL.h}px`, overflow: 'hidden', background: '#000' } });
    this.clipA = makeClip(this.body, { name: 'object-counter', frames: CLIP_FRAMES });
    this.clipB = makeClip(this.body, { name: 'line-counter', frames: CLIP_FRAMES });
    this.wipe = h('div', { class: 'abs', style: { top: '0', bottom: '0', width: '3px', marginLeft: '-1.5px', background: 'var(--accent)', boxShadow: '0 0 18px rgba(212,255,90,0.8)' } });
    this.body.append(this.wipe);
    this.panel.append(head, this.body);
    R.append(this.panel);

    // ---- what it does
    this.col = h('div', { class: 'abs', style: { left: '1450px', top: `${PANEL.y - 52}px`, width: '380px' } });
    this.colKicker = h('div', { class: 'kicker', style: { marginBottom: '30px' } }, 'What it does');
    this.col.append(this.colKicker);
    this.items = FEATURES.map(([k, v], i) => {
      const num = h('span', { class: 'mono', style: { fontSize: '15px', letterSpacing: '0.14em', color: 'var(--text3)' } }, String(i + 1).padStart(2, '0'));
      const title = h('div', { style: { fontSize: '30px', fontWeight: 550, letterSpacing: '-0.01em', color: 'var(--text3)' } }, k);
      const desc = h('div', { style: { fontSize: '19px', lineHeight: '1.4', color: 'var(--text3)', marginTop: '6px' } }, v);
      const el = h('div', { style: { display: 'flex', gap: '20px', padding: '22px 0', borderTop: '1px solid var(--line2)' } }, num, h('div', {}, title, desc));
      this.col.append(el);
      return { el, num, title, desc };
    });
    this.colFoot = h('div', { style: { display: 'flex', alignItems: 'center', gap: '12px', paddingTop: '26px', borderTop: '1px solid var(--line2)' } },
      h('span', { class: 'chip ai', style: { height: '36px', fontSize: '15px' } }, 'One overhead camera'));
    this.col.append(this.colFoot);
    R.append(this.col);
  },

  render(t, ctx) {
    const D = ctx.dur;
    this.hud(t);
    const c1 = ctx.line('o1').segs[0][0], cShow = ctx.line('o2').segs[0][0], cLine = this.at[3];

    // ---- title card: in with o1, lifts away as the monitor rises
    const cIn = prog(t, c1 - 0.3, 0.7, E.outCubic);
    const cOut = prog(t, cShow - 0.75, 0.55, E.inCubic);
    put(this.cardKicker, { y: (1 - cIn) * 12, o: cIn });
    put(this.cardHead, { y: (1 - cIn) * 26, o: cIn });
    put(this.cardLine, { sx: prog(t, c1 + 0.3, 0.7, E.inOutCubic), o: cIn });
    put(this.card, { y: -cOut * 60, s: lerp(1, 0.96, cOut), o: 1 - cOut });

    // ---- monitor
    const pIn = prog(t, cShow - 0.45, 0.8, E.outQuart);
    const pOut = prog(t, D - 0.85, 0.6, E.inCubic);
    this.panel.style.clipPath = `inset(${((1 - pIn) * 50).toFixed(2)}% 0 ${((1 - pIn) * 50).toFixed(2)}% 0 round 18px)`;
    put(this.panel, { y: (1 - pIn) * 30 - pOut * 30, s: lerp(1, 0.95, pOut), o: (pIn > 0 ? 1 : 0) * (1 - pOut) });

    // footage A plays across "…single overhead camera / detects… IDs… running count", then B wipes in
    const aStart = cShow - 0.45, sw = cLine - 0.35;
    const rateA = Math.min(1, (CLIP_FRAMES / 30 - 0.05) / (sw + 0.6 - aStart));
    const wipe = prog(t, sw, 0.6, E.inOutCubic);
    const pending = [];
    if (pIn > 0 && wipe < 1) pending.push(this.clipA.show((t - aStart) * rateA));
    if (wipe > 0) pending.push(this.clipB.show(t - sw));
    this.clipA.el.style.opacity = wipe < 1 ? '1' : '0';
    this.clipB.el.style.opacity = wipe > 0 ? '1' : '0';
    this.clipB.el.style.clipPath = `inset(0 0 0 ${((1 - wipe) * 100).toFixed(2)}%)`;
    put(this.wipe, { x: (1 - wipe) * PANEL.w, o: wipe > 0 && wipe < 1 ? 1 : 0 });
    this.mode.textContent = wipe > 0.5 ? 'Mode · Line count' : 'Mode · Object counter';

    // ---- what it does: each item lights up as it's spoken
    const colIn = prog(t, cShow - 0.1, 0.7, E.outCubic);
    put(this.col, { x: (1 - colIn) * 30, o: colIn * (1 - pOut) });
    this.items.forEach((it, i) => {
      const on = clamp((t - this.at[i] + 0.1) / 0.35);
      const next = this.at[i + 1];
      const done = next !== undefined ? clamp((t - next + 0.1) / 0.35) : 0;
      const act = on * (1 - done * 0.6);
      it.num.style.color = on > 0.5 ? 'var(--accent)' : 'var(--text3)';
      it.title.style.color = `rgba(243,243,239,${lerp(0.42, 1, act).toFixed(3)})`;
      it.desc.style.color = `rgba(168,172,179,${lerp(0.35, 1, act).toFixed(3)})`;
    });
    put(this.colFoot, { y: (1 - prog(t, cLine + 3.4, 0.5, E.outCubic)) * 12, o: prog(t, cLine + 3.4, 0.5) });

    return pending.length ? Promise.all(pending) : undefined;
  },
});
