// 02 — Generative AI · Physical to digital
// Pieces on a board → recognition → reasoning → an illustrated story → end-to-end system.
import { addScene, h, svg, put, prog, E, clamp, lerp, env, makeCanvas, rng, rgba, C, keys, makeNoise, rrect } from '../engine.js';
import { makeHud, words, revealWords, tag, reticle, brackets, placeCaret, FONT_MONO } from '../lib/ui.js';
import { piece, storyIllustration } from '../lib/story-art.js';

// board-space layout (origin = board center)
const SLOTS = [
  { kind: 'fox', x: -470, y: -30, label: 'CHARACTER · FOX' },
  { kind: 'lantern', x: -150, y: 70, label: 'OBJECT · LANTERN' },
  { kind: 'moon', x: 170, y: -70, label: 'OBJECT · MOON' },
  { kind: 'forest', x: 480, y: 40, label: 'PLACE · FOREST' },
];
const EDGES = [[0, 1, 'finds', -120], [0, 2, 'wants to reach', -300], [1, 3, 'lights the way', 230], [2, 3, 'rises over', -110]];
const BW = 1560, BH = 880, PD = 230; // board size, piece diameter
const STORY_TITLE = 'Pip and the Lantern Moon';
const STORY_TEXT = 'Pip the fox found a lantern that only glowed for the brave. So one quiet night, Pip carried it up the tallest hill, to ask the moon for a little more light.';

function drawBoard() {
  const { c, ctx: g } = makeCanvas(null, BW, BH, '');
  const n = makeNoise(11);
  rrect(g, 0, 0, BW, BH, 48); g.save(); g.clip();
  const base = g.createLinearGradient(0, 0, BW, BH);
  base.addColorStop(0, '#6b4529'); base.addColorStop(0.5, '#5a3920'); base.addColorStop(1, '#43291a');
  g.fillStyle = base; g.fillRect(0, 0, BW, BH);
  // wood grain
  for (let i = 0; i < 180; i++) {
    const y0 = (i / 180) * BH;
    g.beginPath();
    for (let x = 0; x <= BW; x += 12) {
      const y = y0 + n.fbm(x * 0.0016, i * 0.07, 3) * 26 + Math.sin(x * 0.003 + i) * 3;
      x === 0 ? g.moveTo(x, y) : g.lineTo(x, y);
    }
    const shade = n.n2(i * 0.3, 1.7);
    g.strokeStyle = shade > 0 ? `rgba(255,220,170,${(0.035 + shade * 0.03).toFixed(3)})` : `rgba(20,10,4,${(0.07 - shade * 0.06).toFixed(3)})`;
    g.lineWidth = 1 + Math.abs(shade) * 2.2;
    g.stroke();
  }
  // bevel
  const bev = g.createLinearGradient(0, 0, 0, BH);
  bev.addColorStop(0, 'rgba(255,230,190,0.10)'); bev.addColorStop(0.08, 'rgba(255,230,190,0)'); bev.addColorStop(0.92, 'rgba(0,0,0,0)'); bev.addColorStop(1, 'rgba(0,0,0,0.35)');
  g.fillStyle = bev; g.fillRect(0, 0, BW, BH);
  // engraved slots
  for (const s of SLOTS) {
    const x = s.x + BW / 2, y = s.y + BH / 2, r = PD / 2 + 10;
    const sg = g.createRadialGradient(x, y - 10, r * 0.6, x, y, r);
    sg.addColorStop(0, 'rgba(20,10,4,0.55)'); sg.addColorStop(1, 'rgba(20,10,4,0.2)');
    g.fillStyle = sg; g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill();
    g.strokeStyle = 'rgba(255,225,180,0.16)'; g.lineWidth = 2; g.beginPath(); g.arc(x, y + 2, r, 0.15 * Math.PI, 0.85 * Math.PI); g.stroke();
    g.strokeStyle = 'rgba(0,0,0,0.35)'; g.lineWidth = 2; g.beginPath(); g.arc(x, y - 1, r, 1.15 * Math.PI, 1.85 * Math.PI); g.stroke();
  }
  g.restore();
  return c;
}

addScene({
  id: 'story',
  pre: 0.2,
  post: 0.5,
  setup(ctx) {
    const R = ctx.root;
    this.hud = makeHud(ctx, {
      num: '02', title: 'Generative AI · Physical to digital',
      steps: [
        { label: 'Place', at: ctx.cue('t2', 0) },
        { label: 'Recognize', at: ctx.cue('t3', 0) },
        { label: 'Reason', at: ctx.cue('t3', 1) },
        { label: 'Generate', at: ctx.cue('t3', 2) },
      ],
    });
    // warm ambient light for this chapter
    this.warm = h('div', { class: 'layer', style: { background: 'radial-gradient(ellipse 60% 55% at 50% 50%, rgba(255,170,90,0.10), transparent 70%)' } });
    R.append(this.warm);

    this.table = h('div', { class: 'abs', style: { left: '0', top: '0', width: '4200px', height: '2600px', transformOrigin: '0 0',
      background: 'radial-gradient(ellipse 45% 45% at 50% 50%, #2a1d14 0%, #17110c 55%, #0a0807 100%)' } });
    this.table.append(h('div', { style: { position: 'absolute', inset: '0', opacity: 0.5, backgroundImage: 'repeating-linear-gradient(90deg, rgba(255,255,255,0.012) 0 1px, transparent 1px 5px), repeating-linear-gradient(0deg, rgba(0,0,0,0.05) 0 1px, transparent 1px 4px)' } }));
    R.append(this.table);
    this.board = drawBoard();
    this.board.style.cssText = 'position:absolute;left:0;top:0;transform-origin:0 0;box-shadow:0 60px 120px -20px rgba(0,0,0,0.8), 0 0 0 2px rgba(0,0,0,0.4);border-radius:48px';
    R.append(this.board);

    this.pieces = SLOTS.map((s) => {
      const shadow = h('div', { class: 'abs', style: { left: '0', top: '0', width: `${PD}px`, height: `${PD}px`, borderRadius: '50%', background: 'radial-gradient(circle, rgba(0,0,0,0.55) 40%, rgba(0,0,0,0) 70%)', transformOrigin: '50% 50%' } });
      const el = h('div', { class: 'abs', style: { left: '0', top: '0', width: `${PD}px`, height: `${PD}px`, transformOrigin: '50% 50%' }, html: piece(s.kind, `p${s.kind}`) });
      el.firstChild.style.cssText = 'width:100%;height:100%;display:block';
      R.append(shadow, el);
      return { ...s, el, shadow };
    });

    // overlay canvas: recognition rings, graph, particles
    const ov = makeCanvas(R);
    ov.c.style.zIndex = 5;
    this.g = ov.ctx;
    this.sparks = Array.from({ length: 70 }, (_, i) => { const r = rng(300 + i); return { a: r() * Math.PI * 2, d: r(), s: 0.4 + r() * 0.8, ph: r() * 10 }; });

    // ---------------- storybook
    const art = storyIllustration('bk');
    this.book = h('div', { class: 'abs', style: { left: '310px', top: '170px', width: '1300px', height: '740px', transformOrigin: '50% 50%' } });
    const pageBase = 'position:absolute;top:0;width:650px;height:740px;overflow:hidden;';
    const left = h('div', { style: { cssText: `${pageBase}left:0;border-radius:14px 4px 4px 14px;background:linear-gradient(90deg,#efe5d2 0%,#f4ecdc 70%,#d9ccb3 100%)` } });
    const right = h('div', { style: { cssText: `${pageBase}left:650px;border-radius:4px 14px 14px 4px;background:linear-gradient(90deg,#d6c9b0 0%,#f2e9d8 12%,#f5eee0 100%)` } });
    this.illus = svg('svg', { viewBox: '0 0 600 640', width: 582, height: 672, style: 'position:absolute;left:34px;top:34px;border-radius:8px' });
    this.illus.innerHTML = `<defs>${art.defs}</defs>` + ['sky', 'stars', 'moon', 'hills', 'trees', 'lantern', 'fox', 'fireflies'].map((k) => `<g class="L-${k}">${art.layers[k]}</g>`).join('');
    this.layers = Object.fromEntries(['sky', 'stars', 'moon', 'hills', 'trees', 'lantern', 'fox', 'fireflies'].map((k) => [k, this.illus.querySelector(`.L-${k}`)]));
    this.starEls = [...this.illus.querySelectorAll('.star')];
    this.flyEls = [...this.illus.querySelectorAll('.fly')];
    this.lglow = this.illus.querySelector('.lglow');
    left.append(this.illus);
    this.genNoise = h('div', { style: { position: 'absolute', left: '34px', top: '34px', width: '582px', height: '672px', borderRadius: '8px', background: 'repeating-radial-gradient(circle at 30% 40%, rgba(255,255,255,0.08) 0 2px, rgba(0,0,0,0.12) 2px 5px)', mixBlendMode: 'overlay' } });
    left.append(this.genNoise);
    this.title = h('div', { style: { position: 'absolute', left: '84px', top: '96px', right: '70px', fontFamily: 'var(--font-story)', fontSize: '46px', lineHeight: '1.12', fontWeight: 600, color: '#2c2433', fontVariationSettings: '"SOFT" 100, "WONK" 1', letterSpacing: '-0.01em' } });
    this.titleSpans = words(this.title, STORY_TITLE);
    this.body = h('div', { style: { position: 'absolute', left: '84px', top: '260px', right: '76px', fontFamily: 'var(--font-story)', fontSize: '29px', lineHeight: '1.55', fontWeight: 400, color: '#3b3440', fontVariationSettings: '"SOFT" 50' } });
    this.bodySpans = words(this.body, STORY_TEXT);
    this.caret = h('span', { style: { position: 'absolute', display: 'block', width: '3px', height: '32px', background: '#8fb31f', borderRadius: '2px' } });
    this.body.append(this.caret);
    const pno = h('div', { style: { position: 'absolute', bottom: '40px', right: '64px', fontFamily: 'var(--font-story)', fontSize: '20px', color: '#9a8f80', fontStyle: 'italic' } }, '1');
    const orn = h('div', { style: { position: 'absolute', left: '84px', top: '222px', width: '60px', height: '2px', background: '#c9a86a' } });
    right.append(this.title, orn, this.body, pno);
    const edge = h('div', { style: { position: 'absolute', left: '-8px', right: '-8px', top: '8px', bottom: '-14px', borderRadius: '18px', background: '#3a2618', boxShadow: '0 50px 100px -20px rgba(0,0,0,0.8)' } });
    const pagesEdge = h('div', { style: { position: 'absolute', left: '-3px', right: '-3px', top: '4px', bottom: '-6px', borderRadius: '16px', background: 'repeating-linear-gradient(0deg,#e6dcc8 0 2px,#cfc3ab 2px 3px)' } });
    const gutter = h('div', { style: { position: 'absolute', left: '610px', width: '80px', top: '0', bottom: '0', background: 'linear-gradient(90deg, transparent, rgba(60,40,20,0.22) 50%, transparent)' } });
    this.book.append(edge, pagesEdge, left, right, gutter);
    R.append(this.book);

    // ---------------- end-to-end system row
    this.sys = h('div', { class: 'layer', style: { zIndex: 6 } });
    const node = (title, sub) => {
      const vis = h('div', { style: { height: '200px', borderBottom: '1px solid var(--line)', position: 'relative', overflow: 'hidden', background: 'radial-gradient(ellipse at 50% 40%, rgba(255,255,255,0.04), transparent 70%)' } });
      const n = h('div', { class: 'panel', style: { left: '0', top: '0', width: '330px', transformOrigin: '0 0' } }, vis,
        h('div', { style: { padding: '18px 22px 20px' } },
          h('div', { style: { fontSize: '20px', fontWeight: 600, marginBottom: '6px' } }, title),
          h('div', { class: 'kicker', style: { fontSize: '11.5px', color: 'var(--text2)' } }, sub)));
      this.sys.append(n);
      return { n, vis };
    };
    this.nodes = [node('Board & pieces', 'Physical input'), node('Companion app', 'Configure the experience'), node('Story engine', 'AI architecture'), node('Illustrated story', 'Personal output')];
    // node visuals
    const mini = h('div', { style: { position: 'absolute', left: '40px', top: '40px', width: '250px', height: '120px', borderRadius: '14px', background: 'linear-gradient(135deg,#6b4529,#43291a)' } });
    ['fox', 'lantern', 'moon', 'forest'].forEach((k, i) => { const p = h('div', { style: { position: 'absolute', left: `${14 + i * 58}px`, top: `${i % 2 ? 50 : 22}px`, width: '50px', height: '50px' }, html: piece(k, `m${k}`) }); p.firstChild.style.cssText = 'width:100%;height:100%'; mini.append(p); });
    this.nodes[0].vis.append(mini);
    const phone = h('div', { style: { position: 'absolute', left: '95px', top: '18px', width: '140px', height: '230px', borderRadius: '24px', border: '2px solid #2d323a', background: '#0c0e12', padding: '26px 12px' } });
    const row = (k, v, on) => h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', height: '26px', borderBottom: '1px solid rgba(255,255,255,0.06)', fontSize: '9.5px', color: '#b9bec6' } }, h('span', {}, k),
      on === undefined ? h('span', { style: { color: '#f3f3ef' } }, v) : h('span', { style: { width: '22px', height: '12px', borderRadius: '6px', background: on ? 'var(--accent)' : '#333', position: 'relative' } }, h('i', { style: { position: 'absolute', top: '2px', left: on ? '12px' : '2px', width: '8px', height: '8px', borderRadius: '50%', background: '#0c0e12', display: 'block' } })));
    phone.append(h('div', { style: { fontSize: '11px', fontWeight: 600, marginBottom: '8px', color: '#f3f3ef' } }, 'Story settings'), row('Reader age', '4–6'), row('Tone', 'Gentle'), row('Length', '3 min'), row('Bedtime mode', '', true), row('Read aloud', '', true));
    this.nodes[1].vis.append(phone);
    const eng = h('div', { style: { position: 'absolute', left: '34px', top: '30px', right: '34px', display: 'flex', flexDirection: 'column', gap: '9px' } });
    this.engRows = ['Piece recognition', 'Story planning', 'Text generation', 'Illustration', 'Content guardrails'].map((k) => {
      const r = h('div', { style: { height: '20px', borderRadius: '6px', border: '1px solid rgba(212,255,90,0.3)', background: 'rgba(212,255,90,0.06)', fontFamily: 'var(--font-mono)', fontSize: '10.5px', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#dff5a8', display: 'flex', alignItems: 'center', padding: '0 10px' } }, k);
      eng.append(r); return r;
    });
    this.nodes[2].vis.append(eng);
    this.miniBook = h('div', { style: { position: 'absolute', left: '60px', top: '40px', width: '210px', height: '120px' } });
    const mb = svg('svg', { viewBox: '0 0 600 640', width: 100, height: 112, style: 'position:absolute;left:6px;top:4px;border-radius:4px' });
    mb.innerHTML = `<defs>${storyIllustration('mb').defs}</defs>` + ['sky', 'stars', 'moon', 'hills', 'trees', 'lantern', 'fox'].map((k) => storyIllustration('mb').layers[k]).join('');
    this.miniBook.append(h('div', { style: { position: 'absolute', inset: '0', borderRadius: '6px', background: '#f4ecdc' } }), mb,
      h('div', { style: { position: 'absolute', left: '118px', top: '14px', right: '10px', display: 'flex', flexDirection: 'column', gap: '7px' } },
        ...[0, 1, 2, 3, 4, 5].map((i) => h('i', { style: { display: 'block', height: i === 0 ? '8px' : '4px', width: i === 0 ? '70%' : `${[0, 95, 88, 92, 70, 50][i]}%`, background: i === 0 ? '#2c2433' : '#9a8f80', borderRadius: '2px' } }))));
    this.nodes[3].vis.append(this.miniBook);
    this.sysKicker = h('div', { class: 'abs kicker', style: { left: '0', width: '1920px', top: '290px', textAlign: 'center', color: 'var(--text2)', fontSize: '14px' } }, 'One team · the whole system');
    this.sys.append(this.sysKicker);
    this.sysLinks = svg('svg', { width: 1920, height: 1080, style: 'position:absolute;left:0;top:0' });
    this.sys.prepend(this.sysLinks);
    this.linkEls = [0, 1, 2].map(() => { const p = svg('path', { stroke: 'rgba(212,255,90,0.5)', 'stroke-width': 1.5, fill: 'none', 'stroke-dasharray': '4 6' }); this.sysLinks.append(p); return p; });
    this.pulseEls = [0, 1, 2].map(() => { const c = svg('circle', { r: 4, fill: C.accent }); this.sysLinks.append(c); return c; });
    R.append(this.sys);
  },

  render(t, ctx) {
    const D = ctx.dur;
    const cPlace = ctx.cue('t2', 0), cRec = ctx.cue('t3', 0), cReason = ctx.cue('t3', 1), cGen = ctx.cue('t3', 2), cSys = ctx.cue('t4', 0), cApp = ctx.cue('t4', 1);
    this.hud(t, { hideSteps: t > cSys - 0.4 });
    const g = this.g;
    g.clearRect(0, 0, 1920, 1080);

    // ---------- camera over the board
    const fox = SLOTS[0];
    const zoom = keys(t, [[0, 1.75], [3.4, 1.85], [4.6, 0.92, E.inOutCubic], [cRec, 0.95], [cGen, 1.0]]);
    const cx = keys(t, [[0, fox.x], [3.4, fox.x], [4.6, 0, E.inOutCubic]]);
    const cy = keys(t, [[0, fox.y], [3.4, fox.y], [4.6, 10, E.inOutCubic]]);
    const toBook = prog(t, cGen - 0.25, 0.9, E.inOutCubic);
    const W2 = (x, y) => ({ x: (x - cx) * zoom + 960, y: (y - cy) * zoom + 540 - toBook * 120 });
    const b0 = W2(-BW / 2, -BH / 2);
    const boardO = prog(t, -0.2, 0.7) * (1 - toBook);
    put(this.board, { x: b0.x, y: b0.y, s: zoom, o: boardO, blur: toBook * 8 });
    const tb = W2(-2100, -1300);
    put(this.table, { x: tb.x, y: tb.y, s: zoom, o: boardO });
    this.warm.style.opacity = (0.6 + 0.4 * prog(t, 0, 2)).toFixed(3);

    // ---------- pieces: fox is present from the start (hero), others drop in on "places a few pieces"
    const drops = [0.15, cPlace + 0.35, cPlace + 0.85, cPlace + 1.35];
    this.pieces.forEach((p, i) => {
      const d = clamp((t - drops[i]) / 0.55);
      const land = E.outCubic(d);
      const hover = (1 - land) * 1;
      const P = W2(p.x, p.y);
      const sz = PD * zoom;
      const lift = hover * 0.35;
      const spin = i === 0 ? keys(t, [[0, -14], [3.6, 0, E.inOutSine]]) : (1 - land) * 18;
      put(p.el, { x: P.x - PD / 2, y: P.y - PD / 2 - lift * 40 * zoom, s: zoom * (1 + lift), r: spin, o: clamp(d * 4) * (1 - toBook) });
      put(p.shadow, { x: P.x - PD / 2 + 10 * zoom * (1 + lift * 3), y: P.y - PD / 2 + 16 * zoom * (1 + lift * 3), s: zoom * (1.05 + lift * 0.4), o: clamp(d * 3) * (0.55 - lift * 0.3) * (1 - toBook) });
      p.screen = P; p.r = (PD / 2) * zoom;
    });

    // hero glow + sparks rising from the fox ("physical → personal")
    const sparkA = env(t, 2.0, cPlace + 0.2, 0.6, 0.8);
    if (sparkA > 0) {
      const P = this.pieces[0].screen;
      g.save();
      g.globalCompositeOperation = 'lighter';
      for (const s of this.sparks) {
        const life = ((t * s.s * 0.6 + s.ph) % 1);
        const rr = this.pieces[0].r * (0.6 + s.d * 0.7);
        const x = P.x + Math.cos(s.a) * rr * (0.6 + life * 0.6);
        const y = P.y + Math.sin(s.a) * rr * 0.8 - life * 180;
        const a = sparkA * Math.sin(life * Math.PI) * 0.8;
        const gr = g.createRadialGradient(x, y, 0, x, y, 7);
        gr.addColorStop(0, `rgba(255,214,130,${a.toFixed(3)})`); gr.addColorStop(1, 'rgba(255,214,130,0)');
        g.fillStyle = gr; g.fillRect(x - 7, y - 7, 14, 14);
      }
      g.restore();
    }
    // incoming handoff: the ring that the previous scene's dot became
    const ringA = env(t, -0.2, 2.2, 0.3, 0.6);
    if (ringA > 0) {
      const P = this.pieces[0].screen;
      reticle(g, P.x, P.y, this.pieces[0].r + 26, { a: ringA, p: prog(t, -0.1, 0.8, E.outCubic), spin: t * 0.4 });
    }

    // ---------- recognition: viewfinder + rings + labels
    const recA = env(t, cRec - 0.2, cGen + 0.1, 0.3, 0.4);
    if (recA > 0) {
      brackets(g, 150, 150, 1620, 780, { a: recA * 0.6, len: 40 });
      tag(g, 150, 136, 'VISION · PIECE RECOGNITION', { bg: null, fg: 'rgba(255,255,255,0.6)', size: 12, a: recA, anchor: 'bl', pad: 0 });
      this.pieces.forEach((p, i) => {
        const at = cRec + i * 0.28;
        const q = prog(t, at, 0.5, E.outCubic);
        if (q <= 0) return;
        reticle(g, p.screen.x, p.screen.y, p.r + 16, { a: recA * q, p: q, spin: t * 0.5 + i });
        tag(g, p.screen.x - p.r * 0.75, p.screen.y - p.r - 26, p.label, { a: recA * q, size: 13, anchor: 'bl' });
      });
    }
    // ---------- reasoning: relations between pieces
    const reA = env(t, cReason - 0.05, cGen + 0.25, 0.3, 0.4);
    if (reA > 0) {
      g.save();
      EDGES.forEach(([a, b, label, bend], k) => {
        const q = prog(t, cReason + k * 0.2, 0.55, E.inOutCubic);
        if (q <= 0) return;
        const A = this.pieces[a].screen, B = this.pieces[b].screen;
        const mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2 + bend * zoom;
        const bez = (u) => ({ x: (1 - u) * (1 - u) * A.x + 2 * (1 - u) * u * mx + u * u * B.x, y: (1 - u) * (1 - u) * A.y + 2 * (1 - u) * u * my + u * u * B.y });
        // trim to the recognition rings so lines never cross the pieces
        const rr = this.pieces[a].r + 22;
        let u0 = 0, u1 = 1;
        for (let u = 0; u < 0.5; u += 0.005) { const P = bez(u); if (Math.hypot(P.x - A.x, P.y - A.y) > rr) { u0 = u; break; } }
        for (let u = 1; u > 0.5; u -= 0.005) { const P = bez(u); if (Math.hypot(P.x - B.x, P.y - B.y) > rr) { u1 = u; break; } }
        g.strokeStyle = rgba(C.accent, 0.85 * reA);
        g.lineWidth = 2;
        g.beginPath();
        const steps = 48;
        for (let s2 = 0; s2 <= steps; s2++) {
          const u = u0 + (u1 - u0) * (s2 / steps) * q;
          const P = bez(u);
          s2 === 0 ? g.moveTo(P.x, P.y) : g.lineTo(P.x, P.y);
        }
        g.stroke();
        const head = bez(u0 + (u1 - u0) * q);
        g.fillStyle = rgba(C.accent, reA);
        g.beginPath(); g.arc(head.x, head.y, 4, 0, Math.PI * 2); g.fill();
        if (q > 0.6) {
          const L = bez(0.5);
          tag(g, L.x, L.y, label, { a: reA * clamp((q - 0.6) / 0.3), bg: '#0d0f12', fg: C.accent, stroke: rgba(C.accent, 0.6), size: 14, anchor: 'c', font: FONT_MONO, weight: 500, pad: 9 });
        }
      });
      g.restore();
    }

    // ---------- storybook: generated illustration + streamed text
    const bookIn = prog(t, cGen - 0.05, 0.9, E.outCubic);
    const toSys = prog(t, cSys - 0.35, 1.0, E.inOutCubic);
    const bookO = bookIn * (1 - toSys);
    // book flies into the 4th system node
    const SC = 1.18, NW = 330 * SC, NG = 64;
    const nodeX = (i) => 960 - (4 * NW + 3 * NG) / 2 + i * (NW + NG);
    const bx = lerp(0, nodeX(3) + NW / 2 - 960, toSys), by = lerp(0, 360 + 118 * SC - 540, toSys);
    put(this.book, { x: bx, y: by + (1 - bookIn) * 60, s: lerp(0.9, 1, bookIn) * lerp(1, 0.22, toSys), o: bookO, rx: (1 - bookIn) * 16 });
    this.book.style.display = bookO > 0.001 ? 'block' : 'none';
    if (bookO > 0.001) {
      const gen = prog(t, cGen + 0.15, 1.8, E.outCubic);
      this.illus.style.filter = gen < 0.999 ? `blur(${((1 - gen) * 16).toFixed(2)}px) saturate(${(0.4 + 0.6 * gen).toFixed(2)})` : 'none';
      this.genNoise.style.opacity = (1 - gen).toFixed(3);
      const order = ['sky', 'stars', 'moon', 'hills', 'trees', 'lantern', 'fox', 'fireflies'];
      order.forEach((k, i) => { const q = prog(t, cGen + 0.1 + i * 0.12, 0.6, E.outCubic); this.layers[k].style.opacity = q.toFixed(3); this.layers[k].setAttribute('transform', `translate(0 ${((1 - q) * 18).toFixed(1)})`); });
      this.layers.moon.setAttribute('transform', `translate(0 ${lerp(40, 0, prog(t, cGen, 3, E.outCubic)).toFixed(1)})`);
      this.starEls.forEach((s, i) => s.setAttribute('opacity', (0.35 + 0.65 * (0.5 + 0.5 * Math.sin(t * 2.2 + i * 1.7))).toFixed(3)));
      this.flyEls.forEach((f, i) => {
        const a = t * (0.35 + (i % 5) * 0.07) + i;
        f.setAttribute('cx', (300 + Math.sin(a * 1.3 + i) * 220).toFixed(1));
        f.setAttribute('cy', (420 + Math.cos(a * 0.9 + i * 2) * 120).toFixed(1));
        f.setAttribute('opacity', (0.4 + 0.6 * (0.5 + 0.5 * Math.sin(t * 5 + i))).toFixed(3));
      });
      this.lglow.setAttribute('opacity', (0.85 + 0.15 * Math.sin(t * 6)).toFixed(3));
      revealWords(this.titleSpans, prog(t, cGen + 0.25, 0.6, E.linear), { rise: 6, soft: 1.5 });
      const txtP = prog(t, cGen + 0.8, cSys - cGen - 1.0, E.linear);
      revealWords(this.bodySpans, txtP, { rise: 4, soft: 2, blur: 3 });
      placeCaret(this.caret, this.bodySpans, { dx: 4, dy: 6 });
      this.caret.style.opacity = txtP > 0 && txtP < 1 ? 1 : txtP >= 1 && Math.floor(t * 2.4) % 2 ? 0.9 : 0;
    }

    // ---------- end-to-end system row
    const sysA = prog(t, cSys - 0.2, 0.8, E.outCubic) * (1 - prog(t, D - 0.5, 0.5, E.inCubic));
    this.sys.style.display = sysA > 0.001 ? 'block' : 'none';
    if (sysA > 0.001) {
      this.nodes.forEach((nd, i) => {
        const q = prog(t, cSys - 0.2 + [0, 0.35, 0.6, 0.15][i] + (i === 1 ? cApp - cSys - 0.35 : 0), 0.6, E.outCubic);
        put(nd.n, { x: nodeX(i), y: 360 + (1 - q) * 30, s: SC, o: q * sysA * (i === 3 ? prog(t, cSys + 0.4, 0.4) : 1) });
      });
      this.engRows.forEach((r, i) => put(r, { x: 0, o: prog(t, cSys + 0.5 + i * 0.12, 0.4) }));
      put(this.sysKicker, { o: prog(t, cSys + 0.1, 0.5) * sysA, y: 0 });
      this.linkEls.forEach((p, i) => {
        const x1 = nodeX(i) + NW, x2 = nodeX(i + 1), y = 360 + 118 * SC;
        p.setAttribute('d', `M${x1 + 6},${y} L${x2 - 6},${y}`);
        p.setAttribute('opacity', (prog(t, cSys + 0.2 + i * 0.25, 0.4) * sysA).toFixed(3));
        const u = ((t * 0.9 + i * 0.33) % 1);
        this.pulseEls[i].setAttribute('cx', lerp(x1 + 6, x2 - 6, u).toFixed(1));
        this.pulseEls[i].setAttribute('cy', y);
        this.pulseEls[i].setAttribute('opacity', (prog(t, cSys + 0.5 + i * 0.25, 0.3) * sysA * Math.sin(u * Math.PI)).toFixed(3));
      });
    }
  },
});
