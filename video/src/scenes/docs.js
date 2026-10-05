// 05 — Document intelligence · AI auditing
// Evidence → read → map to frameworks → flag gaps → recommend → readiness (decision support, not legal advice).
import { addScene, h, svg, put, prog, E, clamp, lerp, env, keys, rgba, C } from '../engine.js';
import { makeHud } from '../lib/ui.js';

const FILES = [
  ['PDF', '#ff6b57', 'Quarterly access review.pdf', '2.4 MB'],
  ['DOC', '#7cc6ff', 'Offboarding checklist.docx', '310 KB'],
  ['PNG', '#ff8fc8', 'MFA configuration.png', '1.1 MB'],
  ['XLS', '#9fe07a', 'Training completion.xlsx', '96 KB'],
  ['PDF', '#ff6b57', 'Operations report.pdf', '1.8 MB'],
];
const REQS = [
  { title: 'Periodic user access reviews', status: 'Supported', cls: 'ok', src: 0 },
  { title: 'Access removed at termination', status: 'Supported', cls: 'ok', src: 1 },
  { title: 'MFA for privileged accounts', status: 'Partial', cls: 'mid', src: 2 },
  { title: 'Contractor access reviewed', status: 'Gap', cls: 'bad', src: 3 },
  { title: 'Security awareness training', status: 'Supported', cls: 'ok', src: null },
];

addScene({
  id: 'docs',
  pre: 0.2,
  post: 0.5,
  setup(ctx) {
    const R = ctx.root;
    this.hud = makeHud(ctx, {
      num: '05', title: 'Document intelligence · AI auditing',
      steps: [
        { label: 'Read', at: ctx.cue('d1', 1) },
        { label: 'Map', at: ctx.cue('d1', 2) },
        { label: 'Flag', at: ctx.cue('d1', 3) },
        { label: 'Recommend', at: ctx.cue('d1', 4) },
      ],
    });
    this.view = h('div', { class: 'abs', style: { left: '0', top: '0', width: '1920px', height: '1080px', transformOrigin: '0 0' } });
    R.append(this.view);

    // ---------- evidence panel
    this.ev = h('div', { class: 'panel', style: { left: '80px', top: '170px', width: '470px' } });
    this.ev.append(h('div', { class: 'panel-head' }, h('span', { class: 'title' }, 'Evidence request'), h('span', { class: 'spacer' }), h('span', { class: 'kicker' }, 'Access control')));
    const list = h('div', { style: { padding: '10px 18px 18px' } });
    this.fileRows = FILES.map(([ext, col, name, size]) => {
      const bar = h('i', { style: { display: 'block', height: '100%', width: '0%', background: 'var(--accent)', borderRadius: '2px' } });
      const row = h('div', { style: { display: 'flex', alignItems: 'center', gap: '14px', padding: '14px 8px', borderBottom: '1px solid var(--line)' } },
        h('div', { style: { width: '38px', height: '46px', borderRadius: '6px', background: rgba(col, 0.14), border: `1px solid ${rgba(col, 0.5)}`, color: col, display: 'grid', placeItems: 'center', fontFamily: 'var(--font-mono)', fontSize: '10.5px', fontWeight: 700 } }, ext),
        h('div', { style: { flex: 1, minWidth: 0 } },
          h('div', { style: { fontSize: '16px', whiteSpace: 'nowrap', marginBottom: '8px' } }, name),
          h('div', { style: { height: '3px', background: 'rgba(255,255,255,0.08)', borderRadius: '2px', overflow: 'hidden' } }, bar)),
        h('span', { class: 'kicker', style: { fontSize: '11px' } }, size));
      list.append(row);
      return { row, bar };
    });
    this.ev.append(list);
    this.view.append(this.ev);
    this.handPage = h('div', { class: 'abs', style: { left: '760px', top: '280px', width: '400px', height: '520px', borderRadius: '10px', background: '#f4f3ef', boxShadow: '0 40px 80px rgba(0,0,0,0.6)', padding: '34px', transformOrigin: '0 0', zIndex: 20 } },
      h('div', { style: { fontFamily: 'var(--font-mono)', fontSize: '11px', letterSpacing: '0.16em', color: '#6b6f76', marginBottom: '12px' } }, 'DAILY OPERATIONS REPORT'),
      h('div', { style: { fontSize: '22px', fontWeight: 650, color: '#15171a', marginBottom: '22px' } }, 'Packing line · shift summary'),
      ...Array.from({ length: 11 }, (_, i) => h('div', { style: { height: '9px', borderRadius: '3px', background: i % 4 === 0 ? '#c9ccd1' : '#e2e4e7', width: `${[92, 80, 86, 60, 90, 76, 84, 58, 88, 70, 64][i]}%`, marginBottom: '14px' } })));

    // ---------- document viewer (fictional access review)
    this.doc = h('div', { class: 'abs', style: { left: '600px', top: '120px', width: '620px', height: '830px', borderRadius: '12px', background: '#f5f5f2', color: '#1b1d21', padding: '46px 52px', boxShadow: '0 50px 100px -20px rgba(0,0,0,0.75)', overflow: 'hidden' } });
    const hl = (text, kind) => { const s = h('span', { class: `hl-${kind}`, style: { backgroundImage: `linear-gradient(${kind === 'bad' ? 'rgba(255,107,87,0.28)' : 'rgba(102,134,246,0.38)'}, ${kind === 'bad' ? 'rgba(255,107,87,0.28)' : 'rgba(102,134,246,0.38)'})`, backgroundRepeat: 'no-repeat', backgroundSize: '0% 100%', borderRadius: '3px', padding: '1px 2px' } }, text); return s; };
    this.hls = [hl('All employee accounts', 'ok'), hl('revoked within 48 hours', 'ok'), hl('enforced for administrators', 'mid'), hl('Contractor accounts were out of scope', 'bad')];
    const p = (...kids) => h('p', { style: { fontSize: '17px', lineHeight: '1.62', color: '#34373d', margin: '0 0 16px' } }, ...kids);
    const sec = (n, t) => h('div', { style: { fontSize: '13px', fontFamily: 'var(--font-mono)', letterSpacing: '0.12em', color: '#7a7e86', margin: '22px 0 8px' } }, `${n}  ${t.toUpperCase()}`);
    const tr = (cells, head) => h('div', { style: { display: 'grid', gridTemplateColumns: '1.3fr 0.8fr 0.7fr 1.1fr', padding: '9px 0', borderBottom: '1px solid #e1e2e4', fontSize: '14.5px', color: head ? '#7a7e86' : '#2a2d33', fontWeight: head ? 600 : 400 } }, ...cells.map((c) => h('span', {}, c)));
    this.doc.append(
      h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '26px' } },
        h('div', { style: { width: '34px', height: '34px', borderRadius: '8px', background: '#1b1d21' } }),
        h('span', { style: { fontFamily: 'var(--font-mono)', fontSize: '11.5px', letterSpacing: '0.14em', color: '#7a7e86' } }, 'INTERNAL · Q3')),
      h('div', { style: { fontSize: '30px', fontWeight: 700, letterSpacing: '-0.01em', marginBottom: '8px' } }, 'Quarterly User Access Review'),
      h('div', { style: { fontSize: '14px', color: '#7a7e86', marginBottom: '6px' } }, 'Owner: IT Operations  ·  Status: Approved'),
      sec('01', 'Scope'), p(this.hls[0], ' in the identity provider were reviewed by their managers.'),
      sec('02', 'Method'), p('Managers confirmed each user’s access. Exceptions were ', this.hls[1], '. MFA is ', this.hls[2], '.'),
      h('div', { style: { margin: '6px 0 10px' } }, tr(['User group', 'Accounts', 'Reviewed', 'Approver'], true), tr(['Engineering', '42', '✓', 'Eng. manager']), tr(['Finance', '12', '✓', 'Finance lead']), tr(['Operations', '27', '✓', 'Ops manager'])),
      sec('03', 'Exclusions'), p(this.hls[3], ' for this review cycle.'),
      h('div', { style: { marginTop: '26px', display: 'flex', alignItems: 'center', gap: '12px', fontSize: '14px', color: '#7a7e86' } }, h('span', { style: { fontFamily: 'var(--font-story)', fontStyle: 'italic', fontSize: '24px', color: '#2a2d33' } }, 'J. Rivera'), '— IT lead, sign-off'));
    this.scan = h('div', { class: 'abs', style: { left: '0', right: '0', top: '0', height: '120px', background: 'linear-gradient(180deg, rgba(130,52,254,0), rgba(102,134,246,0.22) 70%, rgba(102,134,246,0.9) 100%)', mixBlendMode: 'multiply' } });
    this.doc.append(this.scan);
    this.view.append(this.doc);

    // ---------- framework mapping
    this.map = h('div', { class: 'panel', style: { left: '1270px', top: '170px', width: '580px' } });
    this.map.append(h('div', { class: 'panel-head' }, h('span', { class: 'title' }, 'Framework mapping'), h('span', { class: 'spacer' }),
      h('span', { class: 'chip', style: { height: '28px', fontSize: '13px' } }, 'SOC 2'), h('span', { class: 'chip', style: { height: '28px', fontSize: '13px' } }, 'ISO 27001')));
    const body = h('div', { style: { padding: '6px 20px 14px' } });
    this.reqRows = REQS.map((r) => {
      const badge = h('span', { class: `badge ${r.cls}` }, r.status);
      const ev = h('span', { class: 'kicker', style: { fontSize: '11px', color: 'var(--text3)' } }, r.src === null ? '1 evidence file' : 'Evidence linked');
      const row = h('div', { style: { display: 'flex', alignItems: 'center', gap: '14px', padding: '16px 6px', borderBottom: '1px solid var(--line)', position: 'relative' } },
        h('div', { style: { flex: 1 } }, h('div', { style: { fontSize: '17px', marginBottom: '6px' } }, r.title), ev), badge);
      body.append(row);
      return { row, badge, ev, r };
    });
    this.gapNote = h('div', { style: { margin: '10px 6px 4px', padding: '14px 16px', borderRadius: '12px', background: 'rgba(255,107,87,0.08)', border: '1px solid rgba(255,107,87,0.4)', fontSize: '15.5px', lineHeight: 1.5, color: '#ffd9d2' } },
      h('div', { class: 'kicker', style: { color: 'var(--coral)', fontSize: '11px', marginBottom: '6px' } }, 'Gap identified'),
      'Contractor accounts were excluded from the Q3 access review.');
    body.append(this.gapNote);
    this.map.append(body);
    this.view.append(this.map);

    // ---------- recommendation
    this.rec = h('div', { class: 'panel', style: { left: '1270px', top: '800px', width: '580px', padding: '20px 24px', borderColor: 'rgba(130,52,254,0.35)' } },
      h('div', { style: { display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' } }, h('span', { class: 'badge bad' }, 'Impact · High'), h('span', { class: 'kicker', style: { color: 'var(--accent-text)' } }, 'Recommendation')),
      h('div', { style: { fontSize: '18px', lineHeight: 1.5, marginBottom: '16px' } }, 'Add contractor accounts to the next quarterly review and attach the signed approval log.'),
      h('div', { style: { display: 'flex', gap: '10px' } }, h('span', { class: 'chip ai' }, 'Assign owner'), h('span', { class: 'chip' }, 'Draft evidence request')));
    this.view.append(this.rec);

    // links: evidence highlights → requirements
    this.links = svg('svg', { width: 1920, height: 1080, style: 'position:absolute;left:0;top:0;overflow:visible' });
    this.linkEls = REQS.map((r) => { const p2 = svg('path', { fill: 'none', 'stroke-width': 2, stroke: r.cls === 'bad' ? C.coral : r.cls === 'mid' ? C.amber : C.accent }); this.links.append(p2); return p2; });
    R.append(this.links);
    R.append(this.handPage);

    // ---------- readiness dashboard
    this.dash = h('div', { class: 'layer', style: { zIndex: 8 } });
    const fw = (name, sub, seg, counts) => h('div', { class: 'panel', style: { position: 'relative', width: '520px', padding: '26px 28px' } },
      h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '18px' } }, h('span', { class: 'display', style: { fontSize: '30px', fontWeight: 600 } }, name), h('span', { class: 'kicker' }, sub)),
      h('div', { style: { display: 'flex', height: '14px', gap: '4px', borderRadius: '7px', overflow: 'hidden', marginBottom: '14px' } },
        h('i', { style: { display: 'block', flex: seg[0], background: 'var(--accent)' } }), h('i', { style: { display: 'block', flex: seg[1], background: 'var(--amber)' } }), h('i', { style: { display: 'block', flex: seg[2], background: 'var(--coral)' } })),
      h('div', { style: { display: 'flex', gap: '22px', fontSize: '15px', color: 'var(--text2)' } }, h('span', {}, h('b', { style: { color: 'var(--accent-text)', fontWeight: 600 } }, counts[0]), ' supported'), h('span', {}, h('b', { style: { color: 'var(--amber)', fontWeight: 600 } }, counts[1]), ' partial'), h('span', {}, h('b', { style: { color: 'var(--coral)', fontWeight: 600 } }, counts[2]), ' gaps')));
    this.dashTitle = h('div', { class: 'abs', style: { left: '200px', top: '205px', display: 'flex', alignItems: 'baseline', gap: '18px' } }, h('span', { style: { fontSize: '40px', fontWeight: 600, letterSpacing: '-0.015em' } }, 'Audit readiness'), h('span', { class: 'kicker', style: { color: 'var(--text2)' } }, 'Decision support for your team'));
    this.dashCards = [fw('SOC 2', 'Type II', [46, 5, 2], ['46', '5', '2']), fw('ISO 27001', 'Annex A', [71, 8, 3], ['71', '8', '3'])];
    const act = (t2, who, cls) => h('div', { style: { display: 'flex', alignItems: 'center', gap: '12px', padding: '12px 0', borderBottom: '1px solid var(--line)', fontSize: '15.5px' } }, h('span', { class: `badge ${cls}`, style: { width: '84px', justifyContent: 'center' } }, cls === 'bad' ? 'Gap' : 'Partial'), h('span', { style: { flex: 1 } }, t2), h('span', { class: 'kicker', style: { fontSize: '11px' } }, who));
    this.actions = h('div', { class: 'panel', style: { position: 'relative', width: '520px', padding: '22px 28px' } },
      h('div', { style: { display: 'flex', justifyContent: 'space-between', marginBottom: '6px' } }, h('span', { style: { fontSize: '19px', fontWeight: 600 } }, 'Open actions'), h('span', { class: 'kicker' }, 'Before fieldwork')),
      act('Review contractor access', 'IT', 'bad'), act('MFA for all admin tools', 'Security', 'mid'), act('Vendor risk assessment', 'Legal', 'mid'));
    this.audit = h('div', { class: 'panel', style: { position: 'relative', width: '520px', padding: '22px 28px' } },
      h('div', { class: 'kicker', style: { marginBottom: '10px' } }, 'Next audit window'),
      h('div', { style: { display: 'flex', alignItems: 'baseline', gap: '12px' } }, h('span', { class: 'display', style: { fontSize: '52px', fontWeight: 600 } }, '21'), h('span', { style: { fontSize: '19px', color: 'var(--text2)' } }, 'days to prepare')));
    const grid = h('div', { class: 'abs', style: { left: '200px', top: '290px', display: 'grid', gridTemplateColumns: '520px 520px', gap: '26px 30px' } }, this.dashCards[0], this.dashCards[1], this.actions, this.audit);
    this.dashItems = [this.dashCards[0], this.dashCards[1], this.actions, this.audit];
    this.dash.append(this.dashTitle, grid);
    R.append(this.dash);
  },

  render(t, ctx) {
    this.hud(t);
    const D = ctx.dur;
    const cRead = ctx.cue('d1', 1), cMap = ctx.cue('d1', 2), cFlag = ctx.cue('d1', 3), cRec = ctx.cue('d1', 4), cKnow = ctx.cue('d2', 0);

    // ---------- camera through the interface
    const cam = [
      [0.0, [1.3, 330, 470]],
      [cRead - 0.3, [1.3, 330, 470]],
      [cRead + 0.5, [1.12, 905, 530], E.inOutCubic],
      [cMap + 0.4, [1.12, 905, 530]],
      [cMap + 1.4, [0.94, 1180, 540], E.inOutCubic],
      [cFlag - 0.2, [0.94, 1180, 540]],
      [cFlag + 0.6, [1.18, 1520, 650], E.inOutCubic],
      [cKnow - 0.4, [1.18, 1520, 650]],
      [cKnow + 0.5, [0.8, 1100, 560], E.inOutCubic],
    ];
    const [s, cx, cy] = keys(t, cam);
    const world = (x, y) => ({ x: (x - cx) * s + 960, y: (y - cy) * s + 540 });
    const o = world(0, 0);
    const worldOut = prog(t, cKnow - 0.1, 0.8, E.inOutCubic);
    put(this.view, { x: o.x, y: o.y, s, o: (1 - worldOut * 0.85) * prog(t, -0.2, 0.5), blur: worldOut * 6 });

    // evidence files upload
    this.fileRows.forEach((f, i) => {
      const q = prog(t, 0.1 + i * 0.18, 0.5, E.outCubic);
      put(f.row, { x: (1 - q) * -20, o: q });
      f.bar.style.width = `${(prog(t, 0.3 + i * 0.18, 0.9, E.inOutSine) * 100).toFixed(1)}%`;
    });
    put(this.ev, { o: prog(t, -0.1, 0.5) });
    // the operations report from the previous scene lands as the last evidence file
    {
      const q = prog(t, 0.0, 0.85, E.inOutCubic);
      const icon = this.fileRows[4].row.firstChild.getBoundingClientRect();
      const x0 = 760, y0 = 280 + 0, x1 = icon.left, y1 = icon.top;
      const sc = lerp(1, icon.width / 400, q);
      put(this.handPage, { x: lerp(0, x1 - x0, q) + lerp(0, 0, q), y: lerp(0, y1 - y0, q), s: sc, r: lerp(-3, 0, q), o: t < 0.85 ? 1 - prog(t, 0.65, 0.2) : 0 });
    }
    // reading: scan beam + highlights
    const scanP = prog(t, cRead - 0.1, 1.7, E.inOutSine);
    put(this.scan, { y: lerp(-120, 830, scanP), o: scanP > 0 && scanP < 1 ? 1 : 0 });
    const hlAt = [0.28, 0.45, 0.55, 0.85];
    this.hls.forEach((el, i) => { const q = clamp((scanP - hlAt[i]) / 0.08); el.style.backgroundSize = `${(q * 100).toFixed(1)}% 100%`; });
    put(this.doc, { o: prog(t, cRead - 0.6, 0.6), y: (1 - prog(t, cRead - 0.6, 0.7, E.outCubic)) * 30 });
    // mapping rows + links
    put(this.map, { o: prog(t, cMap - 0.2, 0.6), x: (1 - prog(t, cMap - 0.2, 0.7, E.outCubic)) * 30 });
    const vs = s; // links are drawn in screen space
    this.reqRows.forEach((r, i) => {
      const at = cMap + 0.35 + i * 0.5;
      const q = prog(t, at + 0.35, 0.35, E.outBack);
      put(r.badge, { s: q > 0 ? lerp(0.6, 1, Math.min(1.1, q)) : 0.6, o: clamp(q * 2) });
      put(r.row, { o: prog(t, cMap - 0.1 + i * 0.08, 0.4) });
      const lp = this.linkEls[i];
      const la = env(t, at, cFlag + 0.4, 0.3, 0.5) * (1 - worldOut);
      if (r.r.src !== null && la > 0.001) {
        const a = this.hls[r.r.src].getBoundingClientRect();
        const b = r.row.getBoundingClientRect();
        const x1 = a.right + 4, y1 = a.top + a.height / 2, x2 = b.left - 4, y2 = b.top + b.height / 2;
        const len = Math.hypot(x2 - x1, y2 - y1) * 1.3;
        const d = prog(t, at, 0.5, E.inOutCubic);
        lp.setAttribute('d', `M${x1},${y1} C${x1 + 120 * vs},${y1} ${x2 - 120 * vs},${y2} ${x2},${y2}`);
        lp.setAttribute('stroke-dasharray', `${len}`);
        lp.setAttribute('stroke-dashoffset', `${(1 - d) * len}`);
        lp.setAttribute('opacity', (0.85 * la).toFixed(3));
      } else lp.setAttribute('opacity', '0');
    });
    // gap flagged
    const gapRow = this.reqRows[3].row;
    const flag = env(t, cFlag - 0.05, cKnow, 0.3, 0.4);
    gapRow.style.background = `rgba(255,107,87,${(0.1 * flag * (0.7 + 0.3 * Math.sin(t * 7))).toFixed(3)})`;
    gapRow.style.boxShadow = flag > 0.01 ? `inset 3px 0 0 rgba(255,107,87,${flag.toFixed(3)})` : 'none';
    const gn = prog(t, cFlag + 0.15, 0.5, E.outCubic);
    this.gapNote.style.display = gn > 0 ? 'block' : 'none';
    put(this.gapNote, { y: (1 - gn) * -10, o: gn });
    // recommendation
    const rc = prog(t, cRec - 0.1, 0.6, E.outCubic);
    put(this.rec, { y: (1 - rc) * 40, o: rc });

    // ---------- readiness dashboard
    const da = prog(t, cKnow + 0.05, 0.7, E.outCubic) * (1 - prog(t, D - 0.45, 0.45, E.inCubic));
    this.dash.style.display = da > 0.001 ? 'block' : 'none';
    put(this.dashTitle, { y: (1 - da) * 20, o: da });
    this.dashItems.forEach((el, i) => { const q = prog(t, cKnow + 0.15 + i * 0.12, 0.6, E.outCubic) * (1 - prog(t, D - 0.45, 0.45, E.inCubic)); put(el, { y: (1 - q) * 40, s: lerp(0.96, 1, q), o: q }); });
  },
});
