// 01 — Generative AI · Search · Recommendation
// Brief → parse → search → evaluate → recommend → refine (conversation).
import { addScene, h, svg, put, prog, E, clamp, lerp, env, makeCanvas, rng, rgba, C, hash, rrect } from '../engine.js';
import { makeHud, words, revealWords, pop, placeCaret } from '../lib/ui.js';
import { PLACES, thumb } from '../lib/places.js';

const BRIEF = [
  ["We're looking for a "], ['sunlit', 1], [' '], ['industrial loft', 0], [' with '], ['exposed brick', 2], [' and '], ['tall windows', 3],
  ['. Room for a '], ['crew of twelve', 4], [', ideally '], ['within an hour of the city', 5], ['. '], ['Moody, but never dark.', 6],
];
const REQS = [
  { k: 'TYPE', v: ['Industrial loft'], src: 0 },
  { k: 'LIGHT', v: ['Natural', 'Sunlit'], src: 1 },
  { k: 'MUST-HAVE', v: ['Exposed brick', 'Tall windows'], src: 2 },
  { k: 'CAPACITY', v: ['Crew of 12'], src: 4 },
  { k: 'TRAVEL', v: ['≤ 60 min from city'], src: 5 },
  { k: 'MOOD', v: ['Moody', 'Not dark'], src: 6 },
];
// Candidates: checks per requirement (2 = match, 1 = partial, 0 = miss)
const CANDS = [
  { name: 'The Foundry Loft', art: 'loft', checks: [2, 2, 2, 2, 2, 2], tier: 1, meta: 'Industrial loft · 35 min', why: 'Exposed brick, west light all afternoon, freight lift for gear.' },
  { name: 'Canal Street Studio', art: 'studio', checks: [2, 2, 1, 2, 2, 2], tier: 1, meta: 'Double-height studio · 50 min', why: 'Double-height windows, raw concrete, space for a full crew.' },
  { name: 'Harbor Warehouse', art: 'warehouse', checks: [2, 1, 0, 2, 2, 1], tier: 2 },
  { name: 'Mill House No. 9', art: 'mill', checks: [2, 2, 2, 1, 2, 2], tier: 1, meta: 'Converted mill · 42 min', why: 'Original brickwork, arched windows, golden-hour exterior.' },
  { name: 'Glasshouse Offices', art: 'office', checks: [0, 2, 0, 2, 2, 0], tier: 0 },
  { name: 'Ridgeline Barn', art: 'barn', checks: [0, 2, 1, 2, 0, 2], tier: 0 },
];
const ROOFTOP = { name: 'Pier 4 Rooftop Studio', art: 'rooftop', meta: 'Loft + rooftop · 45 min', why: 'Brick interior, big windows and a private rooftop deck.' };

const ctx0 = addScene({
  id: 'search',
  pre: 0.2,
  post: 0.6,
  setup(ctx) {
    const R = ctx.root;
    this.hud = makeHud(ctx, {
      num: '01', title: 'Generative AI · Search · Recommendation',
      steps: [
        { label: 'Parse', at: ctx.cue('s2', 0) },
        { label: 'Search', at: ctx.cue('s2', 1) },
        { label: 'Evaluate', at: ctx.cue('s2', 2) },
        { label: 'Recommend', at: ctx.cue('s2', 3) },
        { label: 'Refine', at: ctx.cue('s3', 0) },
      ],
    });

    // ---------------- brief card
    this.brief = h('div', { class: 'panel', style: { left: '460px', top: '318px', width: '1000px', transformOrigin: '0 0' } });
    const head = h('div', { class: 'panel-head' },
      h('span', { class: 'dots' }, h('i'), h('i'), h('i')), h('span', { class: 'title' }, 'New brief'), h('span', { class: 'spacer' }),
      h('span', { class: 'kicker' }, 'Brief · 0231'));
    const who = h('div', { style: { display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '22px' } },
      h('div', { style: { width: '40px', height: '40px', borderRadius: '50%', background: 'linear-gradient(135deg,#3a4150,#1d2129)', border: '1px solid var(--line2)', display: 'grid', placeItems: 'center', fontSize: '14px', fontWeight: 600, color: 'var(--text2)' } }, 'PT'),
      h('div', { style: { fontSize: '17px', color: 'var(--text)' } }, 'Production team', h('span', { style: { color: 'var(--text3)' } }, '  ·  Spring campaign shoot')));
    this.briefText = h('div', { style: { position: 'relative', fontSize: '35px', lineHeight: '1.5', fontWeight: 430, letterSpacing: '-0.01em', color: 'var(--text)' } });
    this.wordSpans = [];
    this.phrases = [];
    for (const [text, key] of BRIEF) {
      if (key === undefined) {
        const holder = h('span');
        this.briefText.append(holder);
        this.wordSpans.push(...words(holder, text));
      } else {
        const ph = h('span', { class: 'hl', style: { backgroundImage: 'linear-gradient(rgba(212,255,90,0.16), rgba(212,255,90,0.16))', backgroundRepeat: 'no-repeat', backgroundSize: '0% 100%', borderRadius: '4px', boxShadow: 'inset 0 -2px 0 rgba(212,255,90,0)', padding: '0 2px', margin: '0 -2px' } });
        this.briefText.append(ph);
        this.wordSpans.push(...words(ph, text));
        this.phrases[key] = ph;
      }
    }
    this.caret = h('span', { style: { position: 'absolute', display: 'block', width: '3px', height: '40px', background: 'var(--accent)', borderRadius: '2px' } });
    this.briefText.append(this.caret);
    this.brief.append(head, h('div', { style: { padding: '30px 40px 40px' } }, who, this.briefText));
    R.append(this.brief);

    // ---------------- requirements panel
    this.reqPanel = h('div', { class: 'panel', style: { left: '1130px', top: '300px', width: '600px' } });
    this.reqPanel.append(h('div', { class: 'panel-head' },
      h('span', { style: { width: '9px', height: '9px', borderRadius: '2px', background: 'var(--accent)', transform: 'rotate(45deg)' } }),
      h('span', { class: 'title' }, 'Structured requirements'), h('span', { class: 'spacer' }), h('span', { class: 'kicker' }, 'LLM · Parsed')));
    const body = h('div', { style: { padding: '14px 26px 22px' } });
    this.reqRows = REQS.map((r) => {
      const chips = r.v.map((v) => h('span', { class: 'chip ai' }, v));
      const row = h('div', { style: { display: 'flex', alignItems: 'center', height: '58px', borderBottom: '1px solid var(--line)' } },
        h('div', { class: 'kicker', style: { width: '150px', color: 'var(--text3)' } }, r.k),
        h('div', { style: { display: 'flex', gap: '10px' } }, ...chips));
      body.append(row);
      return { row, chips, src: r.src };
    });
    this.reqRows[this.reqRows.length - 1].row.style.borderBottom = 'none';
    this.reqPanel.append(body);
    R.append(this.reqPanel);

    // flying chips: each parsed phrase travels from the brief into its structured field
    this.flyLayer = h('div', { class: 'layer', style: { zIndex: 40 } });
    this.flyers = [];
    this.reqRows.forEach((r, i) => r.chips.forEach((c, j) => {
      const f = h('span', { class: 'chip ai', style: { position: 'absolute', left: '0', top: '0', transformOrigin: '0 0', boxShadow: '0 10px 30px rgba(0,0,0,0.5), 0 0 18px rgba(212,255,90,0.25)' } }, c.textContent);
      this.flyLayer.append(f);
      this.flyers.push({ f, row: i, chip: c, src: r.src, k: j });
    }));
    R.append(this.flyLayer);

    // ---------------- catalog wall (3D plane)
    this.catWrap = h('div', { class: 'abs', style: { left: '0', top: '0', width: '1920px', height: '1080px', perspective: '1500px', perspectiveOrigin: '50% 30%', maskImage: 'linear-gradient(180deg, transparent 30%, #000 44%, #000 80%, transparent 93%)', webkitMaskImage: 'linear-gradient(180deg, transparent 30%, #000 44%, #000 80%, transparent 93%)' } });
    const COLS = 22, ROWS = 14, TW = 76, TH = 50, GAP = 10;
    this.cat = { COLS, ROWS, TW, TH, GAP, W: COLS * (TW + GAP) - GAP, H: ROWS * (TH + GAP) - GAP };
    const base = makeCanvas(null, this.cat.W, this.cat.H);
    const r = rng(42);
    for (let j = 0; j < ROWS; j++) for (let i = 0; i < COLS; i++) {
      const x = i * (TW + GAP), y = j * (TH + GAP);
      base.ctx.save();
      rrect(base.ctx, x, y, TW, TH, 5); base.ctx.clip();
      thumb(base.ctx, x, y, TW, TH, r);
      base.ctx.restore();
    }
    this.catBase = base.c;
    const vis = makeCanvas(this.catWrap, this.cat.W, this.cat.H, '');
    vis.c.style.position = 'absolute';
    vis.c.style.left = `${(1920 - this.cat.W) / 2}px`;
    vis.c.style.top = '300px';
    vis.c.style.transformOrigin = '50% 50%';
    this.catCanvas = vis.c;
    this.catCtx = vis.ctx;
    // lit tiles = strong matches
    const rr = rng(7);
    this.lit = [];
    while (this.lit.length < 14) {
      const i = Math.floor(rr() * COLS), j = Math.floor(rr() * ROWS);
      if (!this.lit.some((l) => l.i === i && l.j === j)) this.lit.push({ i, j, d: rr() });
    }
    this.catLabel = h('div', { class: 'abs kicker', style: { left: '0', width: '1920px', textAlign: 'center', top: '232px', color: 'var(--text2)', fontSize: '14px' } }, 'Searching the location catalog');
    R.append(this.catWrap, this.catLabel);

    // ---------------- candidate cards
    this.cands = CANDS.map((c, i) => {
      const art = h('div', { style: { width: '100%', height: '156px', overflow: 'hidden' }, html: PLACES[c.art](`c${i}`) });
      art.firstChild.style.width = '100%'; art.firstChild.style.height = '100%'; art.firstChild.style.display = 'block';
      const dots = c.checks.map(() => h('span', { style: { width: '22px', height: '22px', borderRadius: '6px', border: '1px solid var(--line2)', display: 'grid', placeItems: 'center', fontSize: '12px', fontWeight: 700, fontFamily: 'var(--font-mono)' } }, ''));
      const badge = h('span', { class: 'badge neutral', style: { position: 'absolute', right: '12px', top: '12px', backdropFilter: 'none', boxShadow: '0 0 0 1px rgba(255,255,255,0.08), 0 6px 18px rgba(0,0,0,0.45)' } }, '');
      const scan = h('div', { style: { position: 'absolute', left: '0', top: '0', width: '2px', height: '100%', background: 'linear-gradient(180deg, transparent, var(--accent), transparent)', boxShadow: '0 0 18px rgba(212,255,90,0.6)' } });
      const card = h('div', { class: 'panel', style: { left: '0', top: '0', width: '252px', transformOrigin: '50% 50%' } },
        art,
        h('div', { style: { padding: '14px 16px 16px' } },
          h('div', { style: { fontSize: '16px', fontWeight: 600, marginBottom: '12px', whiteSpace: 'nowrap' } }, c.name),
          h('div', { style: { display: 'flex', gap: '7px' } }, ...dots)),
        badge, scan);
      R.append(card);
      return { card, dots, badge, scan, c };
    });

    // ---------------- shortlist cards (large)
    const bigCard = (c, id) => {
      const art = h('div', { style: { width: '100%', height: '250px', overflow: 'hidden', position: 'relative' }, html: PLACES[c.art](id) });
      art.firstChild.style.cssText = 'width:100%;height:100%;display:block';
      const rank = h('span', { class: 'mono', style: { color: 'var(--accent)', fontSize: '14px', letterSpacing: '0.14em' } }, '01');
      const upd = h('span', { class: 'badge ok', style: { position: 'absolute', left: '16px', top: '16px', opacity: 0 } }, 'New match');
      art.append(upd);
      const tags = h('div', { style: { display: 'flex', gap: '8px', margin: '14px 0 16px' } });
      const card = h('div', { class: 'panel', style: { left: '0', top: '0', width: '440px', transformOrigin: '0 0' } },
        art,
        h('div', { style: { padding: '20px 24px 24px' } },
          h('div', { style: { display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' } }, rank, h('span', { class: 'kicker' }, c.meta)),
          h('div', { style: { fontSize: '25px', fontWeight: 600, letterSpacing: '-0.01em' } }, c.name),
          tags,
          h('div', { style: { fontSize: '15.5px', lineHeight: 1.5, color: 'var(--text2)' } }, h('span', { style: { color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontSize: '11.5px', letterSpacing: '0.14em', marginRight: '8px' } }, 'WHY IT FITS'), c.why)));
      R.append(card);
      return { card, rank, tags, upd };
    };
    this.big = [0, 1, 3].map((ci) => bigCard(CANDS[ci], `b${ci}`));
    const tagSets = [['Exposed brick', 'West light'], ['Tall windows', 'Crew of 12'], ['Brickwork', 'Golden hour']];
    this.big.forEach((b, i) => tagSets[i].forEach((tg) => b.tags.append(h('span', { class: 'chip', style: { height: '30px', fontSize: '13.5px' } }, tg))));
    this.roof = bigCard(ROOFTOP, 'broof');
    ['Rooftop deck', 'Exposed brick'].forEach((tg, i) => this.roof.tags.append(h('span', { class: i === 0 ? 'chip ai' : 'chip', style: { height: '30px', fontSize: '13.5px' } }, tg)));
    this.slHead = h('div', { class: 'abs', style: { left: '0', top: '0', display: 'flex', alignItems: 'baseline', gap: '18px', whiteSpace: 'nowrap' } },
      h('span', { style: { fontSize: '30px', fontWeight: 600, letterSpacing: '-0.01em' } }, 'Your shortlist'),
      h('span', { class: 'kicker', style: { color: 'var(--text2)' } }, 'Ranked for brief 0231'));
    R.append(this.slHead);

    // ---------------- chat panel
    this.chat = h('div', { class: 'panel', style: { left: '1300px', top: '262px', width: '500px', height: '500px' } });
    this.chat.append(h('div', { class: 'panel-head' },
      h('span', { style: { width: '10px', height: '10px', borderRadius: '50%', background: 'var(--accent)', boxShadow: '0 0 12px rgba(212,255,90,0.7)' } }),
      h('span', { class: 'title' }, 'Scouting assistant'), h('span', { class: 'spacer' }), h('span', { class: 'kicker' }, 'Live')));
    const bubble = (who, text) => h('div', {
      style: who === 'me'
        ? { alignSelf: 'flex-end', maxWidth: '360px', background: 'var(--panel3)', border: '1px solid var(--line2)', borderRadius: '18px 18px 4px 18px', padding: '14px 18px', fontSize: '18px', lineHeight: 1.45 }
        : { alignSelf: 'flex-start', maxWidth: '380px', background: 'rgba(212,255,90,0.07)', border: '1px solid rgba(212,255,90,0.35)', borderRadius: '18px 18px 18px 4px', padding: '14px 18px', fontSize: '18px', lineHeight: 1.45, color: '#f1ffd0' },
    }, text);
    this.bUser = bubble('me', 'Love the second one. Anything similar with a rooftop?');
    this.bTyping = h('div', { style: { alignSelf: 'flex-start', display: 'flex', gap: '6px', padding: '16px 18px', borderRadius: '18px', background: 'rgba(212,255,90,0.07)', border: '1px solid rgba(212,255,90,0.3)' } },
      h('i', { style: { width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent)', display: 'block' } }),
      h('i', { style: { width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent)', display: 'block' } }),
      h('i', { style: { width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent)', display: 'block' } }));
    this.bAi = bubble('ai', 'One similar space has a private rooftop. I’ve moved it to the top of your shortlist.');
    this.bHint = h('div', { class: 'kicker', style: { alignSelf: 'flex-start', color: 'var(--text3)', marginTop: '-4px' } }, 'Shortlist re-ranked · 3 locations');
    this.chatBody = h('div', { style: { display: 'flex', flexDirection: 'column', gap: '16px', padding: '26px 24px' } }, this.bUser, this.bTyping, this.bAi, this.bHint);
    this.chat.append(this.chatBody);
    this.chat.append(h('div', { style: { position: 'absolute', left: '20px', right: '20px', bottom: '20px', height: '54px', borderRadius: '14px', border: '1px solid var(--line2)', background: 'var(--panel2)', display: 'flex', alignItems: 'center', padding: '0 18px', color: 'var(--text3)', fontSize: '16px' } }, 'Ask a follow-up…'));
    R.append(this.chat);

    // outro dot (hands off to the story scene's recognition ring)
    this.dot = h('div', { class: 'abs', style: { left: '0', top: '0', width: '28px', height: '28px', marginLeft: '-14px', marginTop: '-14px', borderRadius: '50%', background: 'var(--accent)', boxShadow: '0 0 30px rgba(212,255,90,0.8)' } });
    R.append(this.dot);
  },

  render(t, ctx) {
    const cP = ctx.cue('s2', 0), cS = ctx.cue('s2', 1), cE = ctx.cue('s2', 2), cR = ctx.cue('s2', 3), cF = ctx.cue('s3', 0), cF2 = ctx.cue('s3', 1);
    const D = ctx.dur;
    this.hud(t);

    // ---------- brief card: opens from a line, types in sync with VO s1
    const open = prog(t, 0.0, 0.7, E.outQuart);
    const toLeft = prog(t, cP + 0.35, 0.9, E.inOutCubic);
    const briefOut = prog(t, cS - 0.35, 0.55, E.inOutCubic);
    this.brief.style.clipPath = `inset(${((1 - open) * 50).toFixed(2)}% 0 ${((1 - open) * 50).toFixed(2)}% 0 round 18px)`;
    put(this.brief, {
      x: lerp(0, -300, toLeft) + lerp(0, -40, briefOut), y: lerp(0, -8, toLeft) + lerp(0, -40, briefOut),
      s: lerp(1, 0.88, toLeft) * lerp(1, 0.9, briefOut), o: (t < 0 ? 0 : 1) * (1 - briefOut),
    });
    revealWords(this.wordSpans, prog(t, 0.55, ctx.line('s1').end - 0.55, E.linear), { rise: 8, soft: 3 });
    placeCaret(this.caret, this.wordSpans, { dx: 4, dy: 6 });
    this.caret.style.opacity = t < ctx.line('s1').end + 0.4 ? (t < ctx.line('s1').end - 0.2 || Math.floor(t * 2.4) % 2 === 0 ? 1 : 0.15) : 0;

    // highlights sweep during "AI parses every requirement"
    const order = [1, 0, 2, 3, 4, 5, 6];
    order.forEach((k, i) => {
      const p = prog(t, cP + 0.05 + i * 0.16, 0.4, E.outCubic);
      const ph = this.phrases[k];
      ph.style.backgroundSize = `${(p * 100).toFixed(1)}% 100%`;
      ph.style.boxShadow = `inset 0 -2px 0 rgba(212,255,90,${(0.9 * p).toFixed(3)})`;
      ph.style.color = p > 0.5 ? '#eeffc6' : '';
    });

    // ---------- requirements panel + flying links
    const reqIn = prog(t, cP + 0.5, 0.8, E.outCubic);
    put(this.reqPanel, { x: lerp(60, -110, reqIn) + lerp(0, -60, briefOut), y: lerp(0, 0, reqIn) - 40 * briefOut, o: reqIn * (1 - briefOut), s: lerp(0.97, 1, reqIn) * lerp(1, 0.9, briefOut) });
    const flyAt = (row, k) => cP + 0.5 + row * 0.12 + k * 0.08;
    this.flyers.forEach((fl) => {
      const t0 = flyAt(fl.row, fl.k), p = clamp((t - t0) / 0.6);
      const landed = p >= 1;
      put(fl.chip, { x: 0, o: landed ? 1 : 0 });
      if (p <= 0 || landed || briefOut >= 1) { fl.f.style.display = 'none'; return; }
      fl.f.style.display = 'inline-flex';
      const a = this.phrases[fl.src].getBoundingClientRect();
      const b = fl.chip.getBoundingClientRect();
      const e = E.inOutCubic(p);
      const x = lerp(a.left + fl.k * 24, b.left, e), y = lerp(a.top, b.top, e) - Math.sin(p * Math.PI) * 70;
      const s0 = a.height / b.height;
      put(fl.f, { x, y, s: lerp(s0 * 0.9, 1, e), o: clamp(p * 5) });
    });
    this.reqRows.forEach((r) => r.row.style.opacity = '1');

    // ---------- catalog plane: rises, scan beam sweeps, matches light up
    const catIn = prog(t, cS - 0.15, 0.9, E.outCubic);
    const catOut = prog(t, cE + 0.25, 0.7, E.inCubic);
    const catVis = catIn * (1 - catOut);
    this.catWrap.style.display = catVis > 0.001 ? 'block' : 'none';
    if (catVis > 0.001) {
      const rx = lerp(62, 50, catIn) + catOut * 6;
      const yy = lerp(260, 40, catIn) + catOut * 120;
      this.catCanvas.style.transform = `translateY(${yy.toFixed(1)}px) rotateX(${rx.toFixed(2)}deg) scale(${lerp(1.25, 1.12, catIn).toFixed(3)})`;
      this.catCanvas.style.opacity = catVis.toFixed(3);
      const g = this.catCtx, cat = this.cat;
      g.clearRect(0, 0, cat.W, cat.H);
      g.drawImage(this.catBase, 0, 0);
      const beam = lerp(-0.15, 1.15, prog(t, cS + 0.1, 1.3, E.inOutSine));
      const bx = beam * cat.W;
      const passed = (x) => clamp((bx - x) / 160);
      // dim non-matching tiles once the beam has passed them
      for (let j = 0; j < cat.ROWS; j++) for (let i = 0; i < cat.COLS; i++) {
        const x = i * (cat.TW + cat.GAP), y = j * (cat.TH + cat.GAP);
        const isLit = this.lit.some((l) => l.i === i && l.j === j);
        const d = passed(x);
        if (!isLit && d > 0) { g.fillStyle = `rgba(7,8,10,${(0.72 * d).toFixed(3)})`; g.fillRect(x - 1, y - 1, cat.TW + 2, cat.TH + 2); }
      }
      const grad = g.createLinearGradient(bx - 220, 0, bx + 30, 0);
      grad.addColorStop(0, 'rgba(212,255,90,0)');
      grad.addColorStop(0.85, 'rgba(212,255,90,0.22)');
      grad.addColorStop(1, 'rgba(212,255,90,0)');
      g.fillStyle = grad;
      g.fillRect(bx - 220, 0, 250, cat.H);
      g.fillStyle = 'rgba(212,255,90,0.9)';
      g.fillRect(bx, 0, 2, cat.H);
      for (const l of this.lit) {
        const x = l.i * (cat.TW + cat.GAP), y = l.j * (cat.TH + cat.GAP);
        const d = passed(x);
        if (d <= 0) continue;
        g.save();
        g.strokeStyle = rgba(C.accent, d);
        g.lineWidth = 3;
        g.shadowColor = 'rgba(212,255,90,0.7)';
        g.shadowBlur = 14 * d;
        rrect(g, x - 2, y - 2, cat.TW + 4, cat.TH + 4, 7);
        g.stroke();
        g.restore();
      }
    }
    put(this.catLabel, { o: env(t, cS, cE + 0.4, 0.4, 0.3), y: 0 });

    // ---------- candidate cards: evaluate against the brief
    const n = this.cands.length;
    const cw = 252, gap = 22, total = n * cw + (n - 1) * gap, x0 = (1920 - total) / 2;
    const recP = prog(t, cR - 0.1, 1.0, E.inOutCubic);
    this.cands.forEach((cd, i) => {
      const inP = prog(t, cE - 0.15 + i * 0.06, 0.75, E.outCubic);
      const tx = x0 + i * (cw + gap), ty = 360;
      const sx = 960 + (this.lit[i].i - 11) * 70, sy = 520 + (this.lit[i].j - 7) * 30;
      const x = lerp(sx - cw / 2, tx, inP), y = lerp(sy, ty, inP);
      const evalAt = cE + 0.55 + i * 0.22;
      // checks tick in as the scan passes
      cd.c.checks.forEach((v, k) => {
        const p = clamp((t - evalAt - k * 0.05) / 0.2);
        const dot = cd.dots[k];
        if (p > 0) {
          dot.textContent = v === 2 ? '✓' : v === 1 ? '~' : '✕';
          const col = v === 2 ? C.accent : v === 1 ? C.amber : C.coral;
          dot.style.color = col;
          dot.style.borderColor = rgba(col, 0.5 * p);
          dot.style.background = rgba(col, 0.12 * p);
        } else { dot.textContent = ''; dot.style.borderColor = ''; dot.style.background = ''; }
      });
      const scanP = prog(t, evalAt - 0.1, 0.45, E.inOutSine);
      put(cd.scan, { x: scanP * cw, o: scanP > 0 && scanP < 1 ? 1 : 0 });
      const bp = pop(t, evalAt + 0.4, 0.45);
      const tiers = { 1: ['Tier 1', 'ok'], 2: ['Tier 2', 'neutral'], 0: ['Discarded', 'bad'] };
      const [lbl, cls] = tiers[cd.c.tier];
      cd.badge.textContent = lbl;
      cd.badge.className = `badge ${cls}`;
      cd.badge.style.background = cls === 'ok' ? '#1d2410' : cls === 'bad' ? '#2a1411' : '#1c1f24';
      put(cd.badge, { s: bp > 0 ? lerp(0.6, 1, Math.min(bp, 1.2)) : 0.6, o: clamp(bp * 2) });
      // discarded cards dim
      const dimP = prog(t, evalAt + 0.6, 0.5);
      // recommend: non-tier-1 cards fall away; tier-1 hand over to the big cards
      let o = inP, dy = 0, s = 1;
      if (cd.c.tier !== 1) { o *= (1 - (cd.c.tier === 0 ? 0.45 : 0.2) * dimP) * (1 - recP); dy = recP * 60; s = 1 - recP * 0.06; }
      else { o *= 1 - prog(t, cR + 0.35, 0.35, E.linear); }
      put(cd.card, { x, y: y + dy, s: s * lerp(0.7, 1, inP), o, blur: (1 - inP) * 6 });
    });

    // ---------- shortlist (3 big cards), then re-rank after the conversation
    const bigIn = prog(t, cR + 0.05, 0.85, E.outCubic);
    const chatIn = prog(t, cF - 0.3, 0.8, E.inOutCubic);
    const rerank = prog(t, cF2 - 0.15, 1.0, E.inOutCubic);
    const outro = prog(t, D - 1.0, 0.8, E.inOutCubic);
    const layout = (slot, k) => {
      // slot positions for 3 cards: wide layout (no chat) → compact (with chat)
      const bw = 440, g2 = 44;
      const wideX = (1920 - (3 * bw + 2 * g2)) / 2 + slot * (bw + g2);
      const compactS = 0.8;
      const compX = 110 + slot * (bw * compactS + 30);
      return { x: lerp(wideX, compX, k), y: lerp(292, 330, k), s: lerp(1, compactS, k) };
    };
    const srcIdx = [0, 1, 3];
    this.big.forEach((b, i) => {
      // ranking: before rerank: loft 01, studio 02, mill 03 ; after: rooftop 01, studio 02, loft 03, mill out
      const from = i;
      const to = i === 0 ? 2 : i === 1 ? 1 : 3;
      const slot = lerp(from, to, rerank);
      const L = layout(slot, chatIn);
      const src = this.cands[srcIdx[i]];
      const sx = x0 + srcIdx[i] * (cw + gap);
      const x = lerp(sx, L.x, bigIn), y = lerp(360, L.y, bigIn);
      let o = clamp(bigIn * 1.6) * (1 - outro);
      if (i === 2) o *= 1 - prog(t, cF2 - 0.1, 0.6);
      put(b.card, { x, y, s: lerp(cw / 440, L.s, bigIn), o });
      b.rank.textContent = `0${Math.round(lerp(from, Math.min(to, 2), rerank)) + 1}`;
    });
    {
      const L = layout(lerp(-0.6, 0, rerank), chatIn);
      put(this.roof.card, { x: L.x, y: L.y + (1 - rerank) * 20, s: L.s, o: prog(t, cF2 - 0.1, 0.6) * (1 - outro) });
      this.roof.rank.textContent = '01';
      put(this.roof.upd, { o: env(t, cF2 + 0.5, D - 0.9, 0.3, 0.3) });
    }
    put(this.slHead, { x: lerp(260, 110, chatIn), y: lerp(226, 266, chatIn), o: prog(t, cR + 0.3, 0.6) * (1 - outro) });

    // ---------- chat refinement
    put(this.chat, { x: lerp(120, 0, chatIn), o: chatIn * (1 - outro) });
    const uP = prog(t, cF + 0.15, 0.45, E.outCubic);
    put(this.bUser, { y: (1 - uP) * 16, o: uP });
    const typing = env(t, cF + 0.75, cF2 + 0.05, 0.2, 0.15);
    this.bTyping.style.display = typing > 0.001 ? 'flex' : 'none';
    put(this.bTyping, { o: typing });
    [...this.bTyping.children].forEach((d, i) => { d.style.opacity = (0.35 + 0.65 * (0.5 + 0.5 * Math.sin(t * 9 - i * 1.1))).toFixed(3); });
    const aP = prog(t, cF2 + 0.05, 0.45, E.outCubic);
    this.bAi.style.display = typing > 0.001 ? 'none' : 'block';
    put(this.bAi, { y: (1 - aP) * 16, o: aP });
    this.bHint.style.display = this.bAi.style.display;
    put(this.bHint, { o: prog(t, cF2 + 0.9, 0.4) });

    // ---------- outro: the assistant's signal dot carries the idea into the next scene
    const dP = prog(t, D - 0.95, 0.9, E.inOutCubic);
    const dx = lerp(1300 + 32, 960, dP), dy = lerp(262 + 26, 540, dP);
    put(this.dot, { x: dx, y: dy, s: lerp(0.4, 1.0, dP), o: t > D - 0.95 ? clamp((t - (D - 0.95)) / 0.2) : 0 });
  },
});
export default ctx0;
