// Grade windows: when the bright 3D plates (tractor, feed, packline, board) are on screen in a cut, so the
// finishing grade (scripts/grade.filter) can turn its glow and halation off there. Those plates are daylight
// photoreal renders; the glow is meant for the film's dark interface scenes and only veils the plates.
//
//   node tools/grade_windows.mjs [cut]                      print the windows for the cut (default: full film)
//   node tools/grade_windows.mjs [cut] --cmds file.txt      also write an ffmpeg sendcmd script for finalize.sh
//   node tools/grade_windows.mjs [cut] --probe              check the formulas against the real page (Chromium)
//
// v(t), the plates' combined visibility, comes from the cut's timeline (scene starts, VO cues), each plate's
// fade envelope as its scene computes it (scenes/agri.js, scenes/story.js: same env()/prog() calls), and the
// scene camera's own fade at the cuts (engine.js sceneCamera). The plate's frames are held at both ends
// (lib/shot.js), so a plate is on screen exactly while its envelope is open. The glow and the halation are
// scaled by 1 − v(t): they fade out as a plate fades in, so the ramps follow the plates' own 0.35–0.7 s fades.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const args = process.argv.slice(2);
const flag = (n) => args.includes(`--${n}`);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const cut = args[0] && !args[0].startsWith('--') ? args[0] : '';
globalThis.location = { search: cut ? `?cut=${cut}` : '' };
const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const { TIMELINE: TL, FPS, env, prog, E, sceneCamera, CAM } = await import('../src/engine.js');
const { PLATES } = await import('../src/lib/shot.js');

const BASE = { glow: 0.30, hal: 0.36 };    // scripts/grade.filter's blend opacities

function sceneCtx(id) {
  const order = TL.scenes.findIndex((s) => s.id === id);
  if (order < 0) return null;
  const info = TL.scenes[order];
  const cue = (l, seg = 0) => TL.lines[l].segs[seg][0] - info.start;
  return { id, order, first: order === 0, last: order === TL.scenes.length - 1, start: info.start, end: info.end, dur: info.end - info.start, cue };
}

// Each plate's envelope in its scene's own time, as the scene computes it.
const PLATE_ENV = {
  agri: (t, c) => {
    const cTr = c.cue('a2', 0), cMap = c.cue('a2', 2), cPack = c.cue('a3', 0), D = c.dur;
    const out = c.last ? prog(t, D - 0.8, 0.5, E.inCubic) : prog(t, D - 0.32, 0.32, E.inCubic);
    return {
      tractor: env(t, PLATES.tractor.t0(), cTr + 0.95, 0.5, 0.35),             // agri.js: trA
      feed: env(t, cTr + 0.7, cMap + 0.9, 0.35, 0.5),                            // agri.js: feedA
      packline: env(t, cPack - 0.1, D + 1, 0.45, 0.01) * (1 - out),              // agri.js: packA
    };
  },
  story: (t, c) => {
    const cGen = c.cue('t3', 2);
    const toBook = prog(t, cGen - 0.25, 0.9, E.inOutCubic);
    return { board: prog(t, -0.2, 0.7) * (1 - toBook) };                         // story.js: boardO
  },
};
const SCENE_PRE = { agri: 0.3, story: 0.2 }, SCENE_POST = { agri: 0.6, story: 0.5 };

/** Combined visibility of the bright plates at film time T (0..1), and which plate dominates. */
function visibility(T) {
  let v = 0, who = null;
  for (const [id, fn] of Object.entries(PLATE_ENV)) {
    const c = sceneCtx(id);
    if (!c) continue;
    const pre = Math.max(SCENE_PRE[id], CAM.inPre), post = Math.max(SCENE_POST[id], CAM.outPost);
    if (T < c.start - pre || T >= c.end + post) continue;
    const cam = sceneCamera(c, T).o;
    for (const [name, a] of Object.entries(fn(T - c.start, c))) {
      const x = a * cam;
      if (x > v) { v = x; who = name; }
    }
  }
  return { v: Math.min(1, v), who };
}

// sample every frame
const N = Math.round(TL.duration * FPS);
const vs = [];
for (let i = 0; i <= N; i++) vs.push(visibility(i / FPS));

// windows: runs of frames with v > 0
const windows = [];
let cur = null;
vs.forEach((s, i) => {
  if (s.v > 0.001) {
    if (!cur) cur = { a: i, b: i, plates: new Set() };
    cur.b = i;
    cur.plates.add(s.who);
    if (s.v > 0.999) { cur.fullA ??= i; cur.fullB = i; }
  } else if (cur) { windows.push(cur); cur = null; }
});
if (cur) windows.push(cur);
console.log(`${cut || 'full film'}: ${TL.duration} s, ${windows.length} window(s) with the glow off`);
for (const w of windows) {
  console.log(`  ${(w.a / FPS).toFixed(2).padStart(7)} – ${(w.b / FPS).toFixed(2).padStart(7)} s   fully off ${(w.fullA / FPS).toFixed(2)} – ${(w.fullB / FPS).toFixed(2)}   ramps ${((w.fullA - w.a) / FPS).toFixed(2)} / ${((w.b - w.fullB) / FPS).toFixed(2)} s   [${[...w.plates].join(', ')}]`);
}

// ffmpeg sendcmd script: blend@glow / blend@hal all_opacity per frame wherever it changes
const cmdsFile = opt('cmds');
if (cmdsFile) {
  const lines = [];
  let prev = null;
  vs.forEach((s, i) => {
    const k = 1 - s.v;
    const q = Math.round(k * 1000) / 1000;
    if (q === prev) return;
    prev = q;
    const t = Math.max(0, i / FPS - 0.5 / FPS).toFixed(4);          // a half frame early: applies to frame i
    lines.push(`${t} [enter] blend@glow all_opacity ${(BASE.glow * q).toFixed(4)}, [enter] blend@hal all_opacity ${(BASE.hal * q).toFixed(4)};`);
  });
  fs.writeFileSync(cmdsFile, lines.join('\n') + '\n');
  console.log(`wrote ${cmdsFile} (${lines.length} commands)`);
}
if (flag('json')) console.log(JSON.stringify(windows.map((w) => ({ start: w.a / FPS, end: w.b / FPS, offStart: w.fullA / FPS, offEnd: w.fullB / FPS, plates: [...w.plates] }))));

// --probe: seek the real film and measure each plate's on-screen opacity (its <img>'s opacity up the DOM)
if (flag('probe')) {
  const { chromium } = await import('playwright');
  const http = await import('node:http');
  const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.woff2': 'font/woff2', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.json': 'application/json' };
  const server = http.createServer((req, res) => {
    const url = decodeURIComponent(req.url.split('?')[0]);
    const file = path.join(ROOT, url === '/' ? 'index.html' : url);
    if (!file.startsWith(ROOT) || !fs.existsSync(file)) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
    fs.createReadStream(file).pipe(res);
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const browser = await chromium.launch(process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {});
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto(`http://127.0.0.1:${server.address().port}/index.html${cut ? `?cut=${cut}` : ''}`);
  await page.waitForFunction(() => window.__ready || window.__error, null, { timeout: 120000 });
  let worst = 0, worstT = 0, n = 0;
  for (const w of windows) {
    for (let i = Math.max(0, w.a - 15); i <= Math.min(N, w.b + 15); i += 2) {
      const T = i / FPS;
      await page.evaluate((tt) => window.__seek(tt), T);
      const real = await page.evaluate(() => {
        let best = 0;
        for (const img of document.querySelectorAll('img')) {
          if (!/\/clips\/(tractor|feed|packline|board)\//.test(img.src)) continue;
          let o = 1, el = img;
          for (; el; el = el.parentElement) {
            const cs = getComputedStyle(el);
            if (cs.display === 'none' || cs.visibility === 'hidden') { o = 0; break; }
            o *= +cs.opacity;
          }
          best = Math.max(best, o);
        }
        return best;
      });
      const d = Math.abs(real - vs[i].v);
      n++;
      if (d > worst) { worst = d; worstT = T; }
    }
  }
  console.log(`probe: ${n} frames checked against the page, largest difference ${worst.toFixed(3)} at ${worstT.toFixed(2)} s`);
  await browser.close();
  server.close();
}
