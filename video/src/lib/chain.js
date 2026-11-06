// The value chain ("from seed to shelf"): the standard hand-off line every chapter enters
// from and exits into, the big six-station chain of the open and close, and the small chain
// map (top right) that tracks the season. Coral = a leak not fixed yet; violet = fixed.
import { addGlobal, h, put, prog, E, clamp, lerp, env, makeCanvas, rgba, C, TIMELINE } from '../engine.js';
import { icon, drawIcon } from './icons.js';
import { STATIONS, GAINS, stationIndex } from './impact-data.js';
import { dockStart, DOCK_DUR } from './gain.js';
import './impact-theme.js';

/** The one standard hand-off line between chapters. */
export const CHAIN = { x0: 160, x1: 1760, y: 540 };

/** Glowing violet line on canvas. */
export function drawLine(g, x0, x1, y, { a = 1, w = 3, color = C.accent, glow = 18 } = {}) {
  if (a <= 0.001 || x1 - x0 < 0.5) return;
  g.save();
  g.globalAlpha *= a;
  g.fillStyle = color;
  g.shadowColor = rgba(color, 0.75);
  g.shadowBlur = glow;
  g.fillRect(x0, y - w / 2, x1 - x0, w);
  g.restore();
}

/** Previous / next scene ids in the current cut. */
export function neighbors(ctx) {
  const ids = TIMELINE.scenes.map((s) => s.id);
  const i = ids.indexOf(ctx.id);
  return { prev: ids[i - 1] || null, next: ids[i + 1] || null };
}

/** Chapter progress: absolute time a station's gain card has docked (its dot turns violet). */
export function stationDone(sceneId) {
  const def = GAINS[sceneId];
  return def ? dockStart(def) + DOCK_DUR * 0.8 : Infinity;
}

// ------------------------------------------------------------------ chain map (top right)
export const MAP = { x0: 1460, x1: 1808, y: 80 };
export const mapDot = (i) => ({ x: lerp(MAP.x0, MAP.x1, i / (STATIONS.length - 1)), y: MAP.y });

const chapterScenes = () => TIMELINE.scenes.filter((s) => stationIndex(s.id) >= 0);
let registered = false;
function registerMap() {
  if (registered || !chapterScenes().length) return;
  registered = true;
  addGlobal({
    setup(stage) {
      this.root = h('div', { class: 'layer', style: { zIndex: '55' } });
      if (new URLSearchParams(location.search).has('nohud')) this.root.style.display = 'none';
      this.cv = makeCanvas(this.root, 520, 150, '');
      Object.assign(this.cv.c.style, { position: 'absolute', left: `${MAP.x0 - 80}px`, top: `${MAP.y - 50}px`, width: '520px', height: '150px' });
      this.label = h('div', { class: 'abs ix-map' }, h('span', { class: 'lbl' }, ''));
      this.root.append(this.label);
      stage.append(this.root);
      const ch = chapterScenes();
      this.t0 = ch[0].start;
      const close = TIMELINE.scenes.find((s) => s.id === 'impact-close');
      this.t1 = close ? close.start : TIMELINE.duration;
      this.visited = new Set(ch.map((s) => s.id));
      this.lastLabel = '';
    },
    render(T) {
      const a = prog(T, this.t0 - 0.2, 0.5) * (1 - prog(T, this.t1 + 0.15, 0.45));
      this.root.style.opacity = a.toFixed(3);
      if (a <= 0.001) return;
      const g = this.cv.ctx;
      const ox = MAP.x0 - 80, oy = MAP.y - 50;
      g.clearRect(0, 0, 520, 150);
      g.save();
      g.translate(-ox, -oy);
      const cur = TIMELINE.scenes.find((s) => T >= s.start && T < s.end);
      const ai = cur ? stationIndex(cur.id) : -1;
      // base line + violet progress up to the last fixed station
      g.fillStyle = 'rgba(255,255,255,0.16)';
      g.fillRect(MAP.x0, MAP.y - 0.5, MAP.x1 - MAP.x0, 1);
      let last = -1;
      STATIONS.forEach((st, i) => { if (T >= stationDone(st.id)) last = i; });
      const px = last >= 0 ? mapDot(last).x : MAP.x0;
      if (last >= 0) { g.fillStyle = C.accent; g.shadowColor = rgba(C.accent, 0.7); g.shadowBlur = 8; g.fillRect(MAP.x0, MAP.y - 1, px - MAP.x0, 2); g.shadowBlur = 0; }
      STATIONS.forEach((st, i) => {
        const { x, y } = mapDot(i);
        const doneP = prog(T, stationDone(st.id) - 0.25, 0.4, E.outBack);
        const visited = this.visited.has(st.id);
        const active = i === ai;
        if (doneP > 0.01) {
          g.fillStyle = C.accent; g.shadowColor = rgba(C.accent, 0.8); g.shadowBlur = 12;
          g.beginPath(); g.arc(x, y, 6.5 * Math.min(1.15, doneP), 0, Math.PI * 2); g.fill(); g.shadowBlur = 0;
          if (doneP > 0.6) { g.strokeStyle = '#fff'; g.lineWidth = 1.6; g.lineCap = 'round'; g.lineJoin = 'round'; g.beginPath(); g.moveTo(x - 2.6, y + 0.2); g.lineTo(x - 0.6, y + 2.2); g.lineTo(x + 2.8, y - 1.8); g.stroke(); }
        } else {
          g.fillStyle = '#0b0d10';
          g.strokeStyle = visited ? rgba(C.coral, active ? 0.95 : 0.7) : 'rgba(255,255,255,0.28)';
          g.lineWidth = 1.5;
          g.beginPath(); g.arc(x, y, 5.5, 0, Math.PI * 2); g.fill(); g.stroke();
        }
        if (active) {
          const pulse = 0.5 + 0.5 * Math.sin(T * 4);
          g.strokeStyle = rgba(doneP > 0.5 ? C.accent : '#ffffff', 0.35 + 0.25 * pulse);
          g.lineWidth = 1.2;
          g.beginPath(); g.arc(x, y, 11 + pulse * 2, 0, Math.PI * 2); g.stroke();
        }
      });
      g.restore();
      // active station name under its dot
      const name = ai >= 0 ? STATIONS[ai].label : '';
      if (name !== this.lastLabel) { this.label.firstChild.textContent = name; this.lastLabel = name; }
      if (ai >= 0) {
        const { x } = mapDot(ai);
        const w = this.label.offsetWidth || 60;
        put(this.label, { x: Math.min(MAP.x1 + 20 - w, Math.max(MAP.x0 - 20, x - w / 2)), y: MAP.y + 16, o: 1 });
        this.label.firstChild.style.color = 'var(--text2)';
      } else put(this.label, { o: 0 });
    },
  });
}
registerMap();

// ------------------------------------------------------------------ big value chain (open & close)
export const BIG = { x0: 300, x1: 1620, y: 540 };
export const bigDot = (i) => ({ x: lerp(BIG.x0, BIG.x1, i / (STATIONS.length - 1)), y: BIG.y });

/**
 * DOM value chain. set({draw, nodes:[0..1], lit:[0..1], labels, a, x, y, s, leak}) drives it.
 * The container transform (x, y, s) lets the open shrink it into the chain map.
 */
export function makeValueChain(parent) {
  const root = h('div', { class: 'abs', style: { left: '0', top: '0', width: '1920px', height: '1080px', transformOrigin: '0 0' } });
  const base = h('div', { class: 'abs', style: { left: `${BIG.x0}px`, top: `${BIG.y - 1}px`, width: `${BIG.x1 - BIG.x0}px`, height: '2px', background: 'rgba(255,255,255,0.18)', transformOrigin: '0 50%' } });
  const prog_ = h('div', { class: 'abs', style: { left: `${BIG.x0}px`, top: `${BIG.y - 1.5}px`, width: `${BIG.x1 - BIG.x0}px`, height: '3px', background: 'var(--accent)', boxShadow: '0 0 16px rgba(130,52,254,0.7)', transformOrigin: '0 50%' } });
  root.append(base, prog_);
  const nodes = STATIONS.map((st, i) => {
    const { x, y } = bigDot(i);
    const ring = h('div', { class: 'abs', style: { left: `${x - 38}px`, top: `${y - 38}px`, width: '76px', height: '76px', borderRadius: '50%', border: '2px solid rgba(255,107,87,0.75)', background: '#0c0e12', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#f3f3ef', boxShadow: '0 20px 50px -20px rgba(0,0,0,0.9)', transformOrigin: '50% 50%' } }, icon(st.icon, { size: 34, stroke: 1.8 }));
    const fill = h('div', { class: 'abs', style: { inset: '-2px', borderRadius: '50%', background: 'radial-gradient(circle at 50% 35%, rgba(150,90,255,0.55), rgba(130,52,254,0.25))', border: '2px solid #8234fe', opacity: '0', boxShadow: '0 0 30px rgba(130,52,254,0.55)' } });
    ring.prepend(fill);
    ring.lastChild.style.position = 'relative';
    const label = h('div', { class: 'abs', style: { left: `${x - 120}px`, width: '240px', top: `${y + 58}px`, textAlign: 'center', fontFamily: 'var(--font-ui)', fontWeight: '600', fontSize: '16px', letterSpacing: '0.2em', textTransform: 'uppercase', color: 'var(--text2)' } }, st.label);
    const num = h('div', { class: 'abs', style: { left: `${x - 60}px`, width: '120px', top: `${y - 82}px`, textAlign: 'center', fontFamily: 'var(--font-ui)', fontWeight: '600', fontSize: '13px', letterSpacing: '0.2em', color: 'var(--text3)' } }, String(i + 1).padStart(2, '0'));
    root.append(ring, label, num);
    return { ring, fill, label, num };
  });
  parent.append(root);
  return {
    el: root,
    nodes,
    set({ draw = 1, prog: pv = 0, node = () => 1, lit = () => 0, labels = 1, a = 1, x = 0, y = 0, s = 1 } = {}) {
      root.style.opacity = a.toFixed(3);
      root.style.display = a > 0.001 ? 'block' : 'none';
      root.style.transform = `translate(${x.toFixed(2)}px, ${y.toFixed(2)}px) scale(${s.toFixed(4)})`;
      base.style.transform = `scaleX(${draw.toFixed(4)})`;
      prog_.style.transform = `scaleX(${pv.toFixed(4)})`;
      prog_.style.opacity = pv > 0.001 ? '1' : '0';
      nodes.forEach((n, i) => {
        const q = node(i);
        const L = lit(i);
        n.ring.style.opacity = clamp(q * 1.6).toFixed(3);
        n.ring.style.transform = `scale(${lerp(0.4, 1, Math.min(1.08, E.outBack(clamp(q), 1.8))).toFixed(4)})`;
        n.fill.style.opacity = L.toFixed(3);
        n.ring.style.borderColor = L > 0.5 ? '#8234fe' : 'rgba(255,107,87,0.75)';
        n.label.style.opacity = (clamp(q * 1.4 - 0.3) * labels).toFixed(3);
        n.num.style.opacity = (clamp(q * 1.4 - 0.4) * labels).toFixed(3);
        n.label.style.color = L > 0.5 ? '#f3f3ef' : 'var(--text2)';
      });
    },
  };
}
