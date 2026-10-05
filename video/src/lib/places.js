// Location photographs for the scouting marketplace. Every photo is a procedural Cycles render
// of a fictional location (scripts/render_locations.py → assets/places/<name>.jpg).
import { h } from '../engine.js';

export const SHORTLIST = ['loft', 'studio', 'mill', 'rooftop', 'warehouse', 'office', 'barn'];
export const CATALOG = [...SHORTLIST, 'cafe', 'house', 'chapel', 'greenhouse', 'pool', 'library'];
export const photoSrc = (name) => `assets/places/${name}.jpg`;

/** A cover-fitted photo element that fills its parent. */
export function photo(name, pos = '50% 50%') {
  return h('img', { src: photoSrc(name), style: { position: 'absolute', inset: '0', width: '100%', height: '100%', objectFit: 'cover', objectPosition: pos, display: 'block' } });
}

/** Hidden <img> elements for every catalog photo, so the film waits for them before frame 0. */
export function preloadCatalog(parent) {
  const imgs = Object.fromEntries(CATALOG.map((n) => [n, h('img', { src: photoSrc(n), style: { display: 'none' } })]));
  parent.append(...Object.values(imgs));
  return imgs;
}

/** One catalog-wall thumbnail: a random crop of a catalog photo (canvas 2D). */
export function thumb(g, imgs, x, y, w, hh, r) {
  const im = imgs[CATALOG[Math.floor(r() * CATALOG.length)]];
  const iw = im.naturalWidth, ih = im.naturalHeight;
  const zoom = 1 + r() * 0.9;
  const sw = Math.min(iw, (ih * w) / hh) / zoom, sh = (sw * hh) / w;
  const sx = r() * (iw - sw), sy = r() * (ih - sh);
  g.save();
  if (r() < 0.5) { g.translate(x * 2 + w, 0); g.scale(-1, 1); }
  g.drawImage(im, sx, sy, sw, sh, x, y, w, hh);
  g.restore();
}
