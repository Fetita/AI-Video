#!/usr/bin/env node
// Frame-accurate renderer: drives index.html through window.__seek(t) in headless
// Chromium and pipes PNG frames into ffmpeg.
//
//   node render.mjs --stills 12.5,30,44.2 [--only search] [--outdir dir]
//   node render.mjs --video [--from 0 --to 20] [--workers 4] [--out build/frames.mkv]
//
// Video mode writes a lossless RGB intermediate per worker, then joins them;
// audio is muxed and the delivery encode happens in ../scripts/finalize.sh.
import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = (name, def) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? (args[i + 1] && !args[i + 1].startsWith('--') ? args[i + 1] : true) : def;
};

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.woff2': 'font/woff2', '.svg': 'image/svg+xml', '.png': 'image/png', '.json': 'application/json', '.jpg': 'image/jpeg' };
function serve() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const url = decodeURIComponent(req.url.split('?')[0]);
      const file = path.join(ROOT, url === '/' ? 'index.html' : url);
      if (!file.startsWith(ROOT) || !fs.existsSync(file)) { res.writeHead(404); res.end(); return; }
      res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
      fs.createReadStream(file).pipe(res);
    });
    server.listen(0, '127.0.0.1', () => resolve(server));
  });
}

const BROWSER_ARGS = ['--font-render-hinting=none', '--disable-lcd-text', '--force-color-profile=srgb', '--hide-scrollbars', '--disable-gpu-vsync', '--run-all-compositor-stages-before-draw'];

async function openPage(browser, port, only) {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.error(`[page] ${m.text()}`); });
  page.on('pageerror', (e) => console.error(`[pageerror] ${e.message}`));
  const extra = opt('query', '');
  const q = `?${only ? `only=${only}&` : ''}${extra}`;
  await page.goto(`http://127.0.0.1:${port}/index.html${q}`);
  await page.waitForFunction(() => window.__ready || window.__error, null, { timeout: 120000 });
  const err = await page.evaluate(() => window.__error);
  if (err) throw new Error(err);
  return page;
}

const cdp = new WeakMap();
async function frame(page, t) {
  await page.evaluate((tt) => window.__seek(tt), t);
  let client = cdp.get(page);
  if (!client) { client = await page.context().newCDPSession(page); cdp.set(page, client); }
  const { data } = await client.send('Page.captureScreenshot', { format: 'png', optimizeForSpeed: true, captureBeyondViewport: false });
  return Buffer.from(data, 'base64');
}

async function stills(port) {
  const times = String(opt('stills')).split(',').map(Number);
  const outdir = opt('outdir', path.join(ROOT, 'build', 'stills'));
  fs.mkdirSync(outdir, { recursive: true });
  const browser = await chromium.launch({ args: BROWSER_ARGS });
  const page = await openPage(browser, port, opt('only', null));
  for (const t of times) {
    const buf = await frame(page, t);
    const f = path.join(outdir, `still_${t.toFixed(2).padStart(7, '0')}.png`);
    fs.writeFileSync(f, buf);
    console.log(f);
  }
  await browser.close();
}

function encoder(out, fps) {
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'png', '-i', '-',
    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '10', '-pix_fmt', 'yuv444p', '-g', '60', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((resolve, reject) => ff.on('close', (code) => (code === 0 ? resolve() : reject(new Error(`ffmpeg ${code}`)))));
  return { ff, done };
}

async function video(port) {
  const probe = await chromium.launch({ args: BROWSER_ARGS });
  const p0 = await openPage(probe, port, opt('only', null));
  const { duration, fps } = await p0.evaluate(() => ({ duration: window.__duration, fps: window.__fps }));
  await probe.close();
  const from = Number(opt('from', 0));
  const to = Math.min(Number(opt('to', duration)), duration);
  const f0 = Math.round(from * fps), f1 = Math.round(to * fps);
  const workers = Number(opt('workers', 4));
  const out = path.resolve(opt('out', path.join(ROOT, 'build', 'frames.mkv')));
  const segdir = path.join(path.dirname(out), 'segments');
  fs.mkdirSync(segdir, { recursive: true });
  const per = Math.ceil((f1 - f0) / workers);
  const started = Date.now();
  let rendered = 0;
  const jobs = [];
  for (let w = 0; w < workers; w++) {
    const a = f0 + w * per, b = Math.min(f1, a + per);
    if (a >= b) continue;
    const seg = path.join(segdir, `seg_${String(w).padStart(2, '0')}.mkv`);
    jobs.push({ a, b, seg });
  }
  await Promise.all(jobs.map(async (job) => {
    const browser = await chromium.launch({ args: BROWSER_ARGS });
    const page = await openPage(browser, port, opt('only', null));
    const { ff, done } = encoder(job.seg, fps);
    for (let i = job.a; i < job.b; i++) {
      const buf = await frame(page, i / fps);
      if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
      rendered++;
      if (rendered % 60 === 0) {
        const el = (Date.now() - started) / 1000;
        const rate = rendered / el;
        console.log(`frames ${rendered}/${f1 - f0}  ${rate.toFixed(1)} fps  eta ${((f1 - f0 - rendered) / rate).toFixed(0)}s`);
      }
    }
    ff.stdin.end();
    await done;
    await browser.close();
  }));
  const list = path.join(segdir, 'list.txt');
  fs.writeFileSync(list, jobs.map((j) => `file '${j.seg}'`).join('\n') + '\n');
  await new Promise((resolve, reject) => {
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', list, '-c', 'copy', out], { stdio: 'inherit' });
    ff.on('close', (c) => (c === 0 ? resolve() : reject(new Error('concat failed'))));
  });
  console.log(`wrote ${out}  (${f1 - f0} frames in ${((Date.now() - started) / 1000).toFixed(0)}s)`);
}

const server = await serve();
const port = server.address().port;
try {
  if (opt('stills')) await stills(port);
  else if (opt('video')) await video(port);
  else console.log('usage: --stills t1,t2 | --video [--from s --to s --workers n --out file]');
} finally {
  server.close();
}
