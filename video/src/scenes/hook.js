// Hook — four inputs flash by (brief · toy · camera · evidence), converge into one line,
// "AI as a feature" decodes into "AI as the product", and the Eagerworks AI Studio lockup builds itself.
import { addScene, h, put, prog, E, clamp, lerp, env, makeCanvas, rgba, C, rrect, W, H, FPS } from '../engine.js';
import { words, revealWords, decode, tag, reticle, box, brackets, placeCaret } from '../lib/ui.js';
import { piece } from '../lib/story-art.js';
import { drawEgo } from '../lib/ego.js';
import { drawPose } from '../lib/hand.js';
import { plantSprite, soilTile } from '../lib/field.js';
import { makeLockup } from '../lib/logo.js';
import { VIEWBOX, ICON_VIEWBOX } from '../lib/logo-data.js';

const BRIEF = 'A sunlit loft with exposed brick, close to the river.';
const CHIPS = ['Loft', 'Sunlit', 'Exposed brick', 'Near the river'];
const QUAD = [[-480, -250], [480, -250], [-480, 250], [480, 250]]; // 2×2 convergence layout (offsets from center)

addScene({
  id: 'hook',
  pre: 0,
  post: 0.4,
  setup(ctx) {
    const R = ctx.root;
    const cv = makeCanvas(R);
    this.g = cv.ctx;
    this.plants = Array.from({ length: 6 }, (_, i) => plantSprite(900 + i));
    this.soil = soilTile(1620, 1200);

    // V1 — creative brief
    this.v1 = h('div', { class: 'abs', style: { left: '0', top: '0', width: '1920px', height: '1080px', transformOrigin: '960px 540px' } });
    this.briefText = h('div', { style: { position: 'absolute', left: '0', width: '1920px', top: '440px', textAlign: 'center', fontSize: '58px', fontWeight: 450, letterSpacing: '-0.015em' } });
    this.briefWrap = h('span', { style: { position: 'relative', display: 'inline-block' } });
    this.briefText.append(this.briefWrap);
    this.briefSpans = words(this.briefWrap, BRIEF);
    this.caret = h('span', { style: { position: 'absolute', width: '4px', height: '62px', background: 'var(--accent)', borderRadius: '2px' } });
    this.briefWrap.append(this.caret);
    this.chipRow = h('div', { style: { position: 'absolute', left: '0', width: '1920px', top: '560px', display: 'flex', justifyContent: 'center', gap: '14px' } });
    this.chips = CHIPS.map((c) => { const el = h('span', { class: 'chip ai', style: { height: '46px', fontSize: '20px', padding: '0 20px' } }, c); this.chipRow.append(el); return el; });
    this.v1.append(this.briefText, this.chipRow);
    R.append(this.v1);

    // V2 — child's toy (a story piece: the sloth)
    this.v2 = h('div', { class: 'abs', style: { left: '0', top: '0', width: '1920px', height: '1080px', transformOrigin: '960px 540px' } });
    this.toy = h('div', { class: 'abs', style: { left: '810px', top: '390px', width: '300px', height: '300px', transformOrigin: '50% 50%' } }, piece('sloth', 'hooksloth'));
    this.toyShadow = h('div', { class: 'abs', style: { left: '810px', top: '390px', width: '300px', height: '300px', borderRadius: '50%', background: 'radial-gradient(circle, rgba(0,0,0,0.6) 40%, transparent 70%)' } });
    this.v2.append(this.toyShadow, this.toy);
    R.append(this.v2);

    // V4 — stack of evidence
    this.v4 = h('div', { class: 'abs', style: { left: '0', top: '0', width: '1920px', height: '1080px', transformOrigin: '960px 540px' } });
    this.pages = [0, 1, 2].map((i) => {
      const lines = Array.from({ length: 12 }, (_, k) => h('div', { style: { height: '10px', borderRadius: '3px', marginBottom: '14px', width: `${[90, 76, 84, 62, 88, 70, 80, 58, 86, 74, 66, 50][k]}%`, background: '#dcdee2', position: 'relative', overflow: 'hidden' } }, h('i', { style: { position: 'absolute', inset: '0', width: '0%', background: k === 7 ? 'rgba(255,107,87,0.75)' : 'rgba(102,134,246,0.85)', display: 'block' } })));
      const pg = h('div', { class: 'abs', style: { left: '810px', top: '330px', width: '300px', height: '400px', borderRadius: '10px', background: '#f4f4f1', padding: '34px 30px', boxShadow: '0 30px 70px rgba(0,0,0,0.6)', transformOrigin: '50% 90%' } },
        h('div', { style: { height: '16px', width: '60%', background: '#1b1d21', borderRadius: '4px', marginBottom: '26px' } }), ...lines);
      this.v4.append(pg);
      return { pg, lines };
    });
    this.scan = h('div', { class: 'abs', style: { left: '0', right: '0', top: '0', height: '90px', background: 'linear-gradient(180deg, rgba(130,52,254,0), rgba(102,134,246,0.35) 80%, rgba(102,134,246,0.95))', mixBlendMode: 'multiply' } });
    this.pages[1].pg.append(this.scan);
    this.gapChip = h('span', { class: 'badge bad', style: { position: 'absolute', left: '1130px', top: '560px', fontSize: '14px', height: '32px', padding: '0 14px', background: '#2a1411' } }, 'Gap found');
    this.okChip = h('span', { class: 'badge ok', style: { position: 'absolute', left: '1130px', top: '470px', fontSize: '14px', height: '32px', padding: '0 14px', background: '#1e1538' } }, '✓ SOC 2 mapped');
    this.v4.append(this.gapChip, this.okChip);
    R.append(this.v4);

    // typography: AI as a feature → AI as the product
    this.type = h('div', { class: 'abs display', style: { left: '0', top: '470px', width: '1920px', textAlign: 'center', fontSize: '128px', fontWeight: 600, letterSpacing: '-0.02em', lineHeight: '1', whiteSpace: 'nowrap' } });
    this.typeA = h('span', { style: { color: 'var(--text)' } }, 'AI as ');
    this.typeB = h('span', { style: { position: 'relative', display: 'inline-block' } }, 'a feature');
    this.under = h('i', { style: { position: 'absolute', left: '-4px', right: '-4px', top: '58%', height: '6px', background: 'var(--text2)', transformOrigin: '0 50%', display: 'block', borderRadius: '3px' } });
    this.typeB.append(this.under);
    this.type.append(this.typeA, this.typeB, h('span', {}, '.'));
    this.typeWrap = h('div', { class: 'abs', style: { left: '0', top: '0', width: '1920px', height: '1080px', transformOrigin: '960px 530px' } }, this.type);
    R.append(this.typeWrap);

    // logo lockup + outcomes
    this.lock = makeLockup({ height: 88 });
    this.lockWrap = h('div', { class: 'abs', style: { left: '0', top: '0', transformOrigin: '50% 50%' } }, this.lock.el);
    this.lock.el.style.position = 'relative';
    R.append(this.lockWrap);
    this.outcomes = h('div', { class: 'abs', style: { left: '0', width: '1920px', top: '668px', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '26px', fontFamily: 'var(--font-mono)', fontSize: '19px', letterSpacing: '0.2em', textTransform: 'uppercase', color: 'var(--text2)' } });
    this.outItems = ['Real products', 'Workflows', 'Measurable outcomes'].map((x, i) => {
      const el = h('span', { style: { display: 'flex', alignItems: 'center', gap: '26px' } }, i ? h('i', { style: { width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent)', display: 'block' } }) : null, h('span', {}, x));
      this.outcomes.append(el);
      return el;
    });
    R.append(this.outcomes);
    // handoff line into the search scene's brief card
    this.handoff = h('div', { class: 'abs', style: { left: '460px', top: '483px', width: '1000px', height: '2px', background: 'var(--accent)', transformOrigin: '50% 50%', boxShadow: '0 0 16px rgba(130,52,254,0.6)' } });
    R.append(this.handoff);
  },

  render(t, ctx, T) {
    const g = this.g;
    g.clearRect(0, 0, W, H);
    const c1 = ctx.cue('h1', 0), c2 = ctx.cue('h2', 0), c3 = ctx.cue('h3', 0), c4 = ctx.cue('h4', 0);
    const cNot = ctx.cue('h5', 0), cProd = ctx.cue('h5', 1), cName = ctx.cue('h6', 0), cWf = ctx.cue('h6', 1), cOut = ctx.cue('h6', 2);
    const D = ctx.dur;
    const conv0 = c4 + 1.25, conv1 = conv0 + 0.55; // 2×2 grid, then collapse into a line
    const grid = prog(t, conv0 - 0.25, 0.35, E.outCubic);
    const collapse = prog(t, conv0 + 0.35, 0.4, E.inCubic);
    // slot transform for vignette k: solo → quadrant (grid) → collapsed line
    const slot = (k, soloA) => {
      const q = QUAD[k];
      const inGrid = grid;
      const x = lerp(0, q[0], inGrid) * (1 - collapse);
      const y = lerp(0, q[1], inGrid) * (1 - collapse);
      const s = lerp(1, 0.42, inGrid);
      const o = Math.max(soloA, inGrid) * (1 - collapse);
      return { x, y, s, sy: 1 - collapse * 0.98, o };
    };

    // ---- opening line → caret
    const lineP = prog(t, 0.25, 0.8, E.inOutCubic);
    const lineOut = prog(t, 1.0, 0.25);
    if (lineP > 0 && lineOut < 1) {
      g.save(); g.globalAlpha = 1 - lineOut;
      g.fillStyle = C.accent; g.shadowColor = 'rgba(130,52,254,0.7)'; g.shadowBlur = 16;
      const w = 900 * lineP * (1 - lineOut);
      g.fillRect(960 - w / 2, 499, w, 2);
      g.restore();
    }

    // ---- V1 brief
    const v1a = env(t, 0.95, c2 - 0.1, 0.2, 0.15);
    { const S = slot(0, v1a); put(this.v1, { x: S.x, y: S.y, s: S.s, sy: S.sy, o: S.o }); }
    revealWords(this.briefSpans, prog(t, 1.1, 0.9, E.linear), { rise: 6, soft: 2 });
    placeCaret(this.caret, this.briefSpans, { dx: 6, dy: 4 });
    this.caret.style.opacity = t < 2.2 ? (t < 2.0 || Math.floor(t * 4) % 2 ? 1 : 0.2) : 0;
    this.chips.forEach((c, i) => { const q = prog(t, 1.95 + i * 0.09, 0.35, E.outBack); put(c, { y: (1 - Math.min(q, 1)) * 18, o: clamp(q * 2) }); });
    // highlight words that became chips
    ['sunlit', 'loft', 'exposed', 'brick,', 'river.'].forEach(() => {});
    this.briefSpans.forEach((s) => { const w2 = s.textContent.toLowerCase(); if (['sunlit', 'loft', 'exposed', 'brick,', 'river.'].includes(w2)) s.style.color = t > 1.9 ? '#e9ffb3' : ''; });

    // ---- V2 toy
    const v2a = env(t, c2 - 0.12, c3 - 0.1, 0.12, 0.15);
    { const S = slot(1, v2a); put(this.v2, { x: S.x, y: S.y, s: S.s, sy: S.sy, o: S.o }); }
    const drop = prog(t, c2 - 0.12, 0.45, E.outCubic);
    put(this.toy, { y: (1 - drop) * -30, s: lerp(1.25, 1, drop), r: (1 - drop) * 20 });
    put(this.toyShadow, { x: 14 + (1 - drop) * 30, y: 22 + (1 - drop) * 40, s: lerp(1.2, 1.02, drop), o: 0.6 * drop });
    // canvas overlays follow the V2 slot
    const withSlot = (k, soloA, fn) => {
      const S = slot(k, soloA);
      if (S.o <= 0.001) return;
      g.save(); g.globalAlpha = S.o;
      g.translate(960 + S.x, 540 + S.y); g.scale(S.s, S.s * S.sy); g.translate(-960, -540);
      fn();
      g.restore();
    };
    withSlot(1, v2a, () => {
      const q = prog(t, c2 + 0.1, 0.5, E.outCubic);
      reticle(g, 960, 540, 176, { p: q, spin: t * 0.8, lw: 3 });
      tag(g, 960 - 150, 540 - 196, 'CHARACTER · SLOTH', { a: q, size: 16 });
    });

    // ---- V3 camera feeds (ego hands + crop rows)
    const v3a = env(t, c3 - 0.12, c4 - 0.1, 0.12, 0.15);
    const expand = prog(t, c3 - 0.12, 0.45, E.outCubic);
    withSlot(2, v3a, () => {
      const panels = [{ x: 190, y: 330, w: 760, h: 420 }, { x: 970, y: 330, w: 760, h: 420 }];
      panels.forEach((P, i) => {
        g.save();
        const cx = P.x + P.w / 2, cy = P.y + P.h / 2;
        g.translate(cx, cy); g.scale(lerp(0.3, 1, expand), lerp(0.3, 1, expand)); g.translate(-cx, -cy);
        rrect(g, P.x, P.y, P.w, P.h, 16); g.save(); g.clip();
        if (i === 0) {
          const sc = P.w / 1620;
          g.save(); g.translate(P.x, P.y); g.scale(sc, sc); g.translate(-150, -118 - 80);
          drawEgo(g, t - c3 + 2.2, (hands) => { hands.forEach((hd) => drawPose(g, hd.P, { alpha: prog(t, c3 + 0.1, 0.4), r: 7, lw: 3.4 })); });
          g.restore();
        } else {
          const sc = P.w / 1620;
          g.save(); g.translate(P.x, P.y); g.scale(sc, sc);
          const off = ((t * 230) % 1200 + 1200) % 1200;
          g.drawImage(this.soil, 0, off - 1200); g.drawImage(this.soil, 0, off);
          for (let r = 0; r < 6; r++) for (let k = -1; k < 7; k++) {
            const x = 200 + r * 244, y = ((k * 150 + t * 230) % 1200) - 100;
            const sz = 116;
            g.drawImage(this.plants[(r + k + 12) % 6], x - sz / 2, y - sz / 2, sz, sz);
            const a = prog(t, c3 + 0.15 + (r * 0.03), 0.3);
            box(g, x - 46, y - 46, 92, 92, { a, lw: 2.4 });
          }
          g.restore();
        }
        g.restore();
        g.strokeStyle = 'rgba(255,255,255,0.18)'; g.lineWidth = 1.5; rrect(g, P.x + 0.5, P.y + 0.5, P.w, P.h, 16); g.stroke();
        tag(g, P.x + 18, P.y + 34, i === 0 ? 'HAND KEYPOINTS' : 'PLANT DETECTION', { a: prog(t, c3 + 0.2, 0.3), size: 13 });
        g.restore();
      });
      brackets(g, 160, 300, 1600, 480, { a: 0.5 * expand, len: 36 });
    });

    // ---- V4 evidence
    const v4a = env(t, c4 - 0.12, conv0 - 0.2, 0.12, 0.2);
    { const S = slot(3, v4a); put(this.v4, { x: S.x, y: S.y, s: S.s, sy: S.sy, o: S.o }); }
    const fan = prog(t, c4 - 0.1, 0.5, E.outCubic);
    this.pages.forEach((p, i) => put(p.pg, { x: (i - 1) * 190 * fan, y: Math.abs(i - 1) * 20 * fan, r: (i - 1) * 7 * fan }));
    const scanP = prog(t, c4 + 0.15, 0.9, E.inOutSine);
    put(this.scan, { y: lerp(-90, 400, scanP), o: scanP > 0 && scanP < 1 ? 1 : 0 });
    this.pages[1].lines.forEach((l, k) => { if ([2, 3, 7].includes(k)) l.firstChild.style.width = `${(clamp((scanP - k / 14) * 6) * 100).toFixed(1)}%`; });
    put(this.gapChip, { x: fan * 60, o: prog(t, c4 + 0.75, 0.3) });
    put(this.okChip, { x: fan * 60, o: prog(t, c4 + 0.45, 0.3) });

    // ---- convergence line
    if (collapse > 0 && t < cNot + 0.5) {
      const lp = prog(t, conv0 + 0.55, 0.4, E.inOutCubic);
      g.save();
      g.fillStyle = C.accent; g.shadowColor = 'rgba(130,52,254,0.8)'; g.shadowBlur = 20;
      const w = lerp(1500, 900, lp) * (1 - prog(t, cNot - 0.1, 0.35));
      g.globalAlpha = collapse;
      g.fillRect(960 - w / 2, 529, w, 3);
      g.restore();
    }

    // ---- typography
    const tIn = prog(t, cNot - 0.2, 0.55, E.outCubic);
    const tOut = prog(t, cName - 0.75, 0.5, E.inCubic);
    const fromLine = `inset(${((1 - tIn) * 50).toFixed(2)}% -10% ${((1 - tIn) * 50).toFixed(2)}% -10%)`;
    this.type.style.clipPath = fromLine;
    put(this.typeWrap, { s: lerp(1, 0.94, tOut) * lerp(0.98, 1, tIn), sy: 1 - tOut * 0.9, o: tIn * (1 - tOut) });
    const dp = prog(t, cProd - 0.05, 0.55, E.linear);
    const frame = Math.round(T * FPS);
    this.typeB.firstChild.textContent = dp <= 0 ? 'a feature' : dp >= 1 ? 'the product' : decode('a feature', 'the product', dp, 7, frame);
    this.typeB.style.color = dp > 0.95 ? '#ffffff' : dp > 0 ? 'var(--accent)' : 'var(--text2)';
    this.typeA.style.color = 'var(--text)';
    // strike through "a feature", then drop into the underline beneath "the product"
    const strike = prog(t, cNot + 0.35, 0.45, E.inOutCubic);
    const sink = prog(t, cProd + 0.25, 0.5, E.inOutCubic);
    this.under.style.transform = `translateY(${(sink * 70).toFixed(1)}px) scaleX(${strike.toFixed(3)})`;
    this.under.style.background = sink > 0.5 ? 'var(--accent)' : 'var(--text2)';
    this.under.style.boxShadow = sink > 0.5 ? `0 0 ${(18 * sink).toFixed(1)}px rgba(130,52,254,0.6)` : 'none';

    // ---- logo lockup
    if (!this.lockW) { const r = this.lock.el.getBoundingClientRect(); if (r.width > 10) this.lockW = r.width; }
    const lw = this.lockW || 1400;
    const lx = (1920 - lw) / 2, ly = 540 - this.lock.height / 2 - 40;
    const la = prog(t, cName - 0.6, 0.3) * (1 - prog(t, D - 0.75, 0.45, E.inCubic));
    const push = lerp(1, 1.035, prog(t, cName, D - cName, E.linear));
    // icon builds centered, then slides left as the wordmark reveals
    const iconW = this.lock.height * (ICON_VIEWBOX[2] / VIEWBOX[3]);
    const center = (lw / 2 - iconW / 2) * (1 - prog(t, cName + 0.35, 1.0, E.inOutCubic));
    put(this.lockWrap, { x: lx + center - (push - 1) * lw / 2, y: ly - (push - 1) * 75 - prog(t, D - 0.75, 0.5, E.inCubic) * 40, s: push, o: la });
    this.lock.set({
      strokes: prog(t, cName - 0.55, 0.6),
      outline: prog(t, cName - 0.25, 0.8),
      fill: prog(t, cName + 0.45, 0.6),
      letters: prog(t, cName + 0.55, 0.9),
      studio: prog(t, cName + 1.15, 0.7),
      glow: env(t, cName + 0.5, cName + 2.2, 0.3, 1.0) * 0.8,
    });
    const oa = 1 - prog(t, D - 0.75, 0.45, E.inCubic);
    const outAt = [cName + 3.2, cWf, cOut];
    this.outItems.forEach((el, i) => { const q = prog(t, outAt[i] - 0.1, 0.45, E.outCubic); put(el, { y: (1 - q) * 12, o: q * oa }); });
    // handoff to the brief card
    const hp = prog(t, D - 0.55, 0.5, E.inOutCubic);
    put(this.handoff, { sx: hp, o: hp > 0 ? 1 : 0 });
  },
});
