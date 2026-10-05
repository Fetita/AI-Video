#!/usr/bin/env node
// Cut the supplied character sheets into one transparent PNG per character.
// Each character is a top-level group in the sheet; we hide the background and the other
// characters, crop the viewBox to the group's bounding box and rasterize it in Chromium.
//
//   cd video && node extract_characters.mjs
//
// Sources: video/assets/characters/src/{adventurers,sloths}.svg → video/assets/characters/<name>.png
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), 'assets', 'characters');
const SHEETS = [
  { file: 'adventurers.svg', group: 'OBJECTS', names: ['scout', 'samurai', 'barbarian', 'wizard'] },
  { file: 'sloths.svg', group: null, names: ['sloth-lunge', 'sloth-namaste', 'sloth-lotus', 'sloth-stretch'] },
];
const HEIGHT = 900; // px, tallest edge of each output

const browser = await chromium.launch();
const page = await browser.newPage();
for (const sh of SHEETS) {
  const src = fs.readFileSync(path.join(DIR, 'src', sh.file), 'utf8').replace(/<\?xml[^>]*>/, '');
  for (let i = 0; i < sh.names.length; i++) {
    await page.setViewportSize({ width: 1200, height: 1200 });
    await page.setContent(`<html><body style="margin:0;background:transparent">${src}</body></html>`);
    const box = await page.evaluate(({ group, i, HEIGHT }) => {
      const svg = document.querySelector('svg');
      const top = [...svg.children].filter((k) => k.tagName === 'g');
      const holder = group ? top.find((g) => g.id === group) : top[top.length - 1];
      top.forEach((g) => { if (g !== holder) g.style.display = 'none'; });
      const chars = [...holder.children].filter((k) => k.tagName === 'g');
      chars.forEach((g, k) => { if (k !== i) g.style.display = 'none'; });
      const bb = chars[i].getBBox();
      const pad = Math.max(bb.width, bb.height) * 0.02;
      const vb = [bb.x - pad, bb.y - pad, bb.width + 2 * pad, bb.height + 2 * pad];
      const s = HEIGHT / Math.max(vb[2], vb[3]);
      svg.setAttribute('viewBox', vb.join(' '));
      svg.setAttribute('width', Math.round(vb[2] * s));
      svg.setAttribute('height', Math.round(vb[3] * s));
      svg.style.display = 'block';
      return { w: Math.round(vb[2] * s), h: Math.round(vb[3] * s) };
    }, { group: sh.group, i, HEIGHT });
    await page.setViewportSize({ width: box.w, height: box.h });
    const out = path.join(DIR, `${sh.names[i]}.png`);
    await page.locator('svg').screenshot({ path: out, omitBackground: true });
    console.log(out, box);
  }
}
await browser.close();
