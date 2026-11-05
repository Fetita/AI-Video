#!/usr/bin/env python3
"""Extract the FS Studio logo from the brand book PDF (page 1, vector) into the film's logo data.

    python3 scripts/extract_fsstudio_logo.py path/to/FS_Studios_Brand_Book.pdf

Writes
  video/assets/logo/fsstudio-logo.svg      the artwork as supplied (pink icon + wordmark), for reference
  video/src/lib/logo-data-fsstudio.js      icon + letter paths, and the icon's centreline (so the build can
                                           draw it as one continuous line), plus the three long straight runs
                                           of that line (the finale's tiles collapse onto them)

Needs pdftocairo (poppler), numpy, scipy and scikit-image. The centreline comes from skeletonising a
10 px/unit rasterisation of the icon, walked tip to tip and simplified (RDP, 0.2 units).
"""
import json
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
from scipy import ndimage
from skimage import io, morphology

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINK = 'rgb(100%, 0.392151%, 64.31427%)'
INK = 'rgb(16.862488%, 16.862488%, 16.862488%)'
VB = [510, 400, 900, 280]           # lockup viewBox (page units): icon + wordmark
ICON_VB = [510, 400, 280, 280]      # icon only
SCALE = 10                          # raster px per unit for the skeleton


def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    d = b - a
    v = pts - a
    dist = np.abs(d[0] * v[:, 1] - d[1] * v[:, 0]) / np.hypot(*d)
    i = int(np.argmax(dist))
    if dist[i] > eps:
        return np.vstack([rdp(pts[:i + 1], eps)[:-1], rdp(pts[i:], eps)])
    return np.vstack([a, b])


def rasterise(svg_text, w, h, out_png):
    """Render an SVG with headless Chromium (Playwright, from video/node_modules)."""
    with tempfile.NamedTemporaryFile('w', suffix='.svg', delete=False) as f:
        f.write(svg_text)
    js = (
        "const {chromium}=require(process.argv[1]+'/video/node_modules/playwright');"
        "(async()=>{const o=process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{};"
        "const b=await chromium.launch(o);const p=await b.newPage({viewport:{width:+process.argv[3],height:+process.argv[4]}});"
        "await p.goto('file://'+process.argv[2]);await p.screenshot({path:process.argv[5]});await b.close();})()"
    )
    subprocess.run(['node', '-e', js, ROOT, f.name, str(w), str(h), out_png], check=True)


def main():
    pdf = sys.argv[1]
    tmp = tempfile.mkdtemp()
    page = os.path.join(tmp, 'p1.svg')
    subprocess.run(['pdftocairo', '-svg', '-f', '1', '-l', '1', pdf, page], check=True)
    s = open(page).read()
    found = re.findall(r'<path fill-rule="nonzero" fill="(rgb\([^)]*\))" fill-opacity="1" d="([^"]+)"', s)
    icon = [d for f, d in found if f == PINK]
    letters = [d for f, d in found if f == INK]
    assert len(icon) == 1 and len(letters) == 8, (len(icon), len(letters))
    icon = icon[0]

    # reference artwork
    art = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{" ".join(map(str, VB))}">\n'
           f'<path fill="#ff059f" d="{icon}"/>\n' + ''.join(f'<path fill="#2b2b2b" d="{d}"/>\n' for d in letters) + '</svg>\n')
    open(os.path.join(ROOT, 'video/assets/logo/fsstudio-logo.svg'), 'w').write(art)

    # centreline of the icon
    x0, y0, w, h = ICON_VB
    png = os.path.join(tmp, 'icon.png')
    rasterise(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0} {y0} {w} {h}" width="{w * SCALE}" height="{h * SCALE}">'
              f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="#fff"/><path fill="#000" d="{icon}"/></svg>',
              w * SCALE, h * SCALE, png)
    mask = io.imread(png)[..., :3].mean(-1) < 128
    width = float(np.median(ndimage.distance_transform_edt(mask)[morphology.skeletonize(mask)])) * 2 / SCALE
    sk = morphology.skeletonize(mask)
    pts = set(zip(*[a.tolist() for a in np.nonzero(sk)]))
    nb = lambda p: [(p[0] + dy, p[1] + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy or dx) and (p[0] + dy, p[1] + dx) in pts]
    ends = [p for p in pts if len(nb(p)) == 1]
    cur = min(ends, key=lambda p: p[0])  # start at the outer tip (top)
    path, seen = [cur], {cur}
    while True:
        n = [q for q in nb(cur) if q not in seen]
        if not n:
            break
        n.sort(key=lambda q: abs(q[0] - cur[0]) + abs(q[1] - cur[1]))
        cur = n[0]
        seen.add(cur)
        path.append(cur)
    P = np.array([[x0 + x / SCALE, y0 + y / SCALE] for y, x in path])
    Q = rdp(P, 0.2)
    centre = 'M' + ' L'.join(f'{x:.2f},{y:.2f}' for x, y in Q)
    seg = [(np.hypot(*(Q[k + 1] - Q[k])), k) for k in range(len(Q) - 1)]
    longest = sorted(sorted(seg, reverse=True)[:3], key=lambda s: s[1])
    strokes = [{'x1': round(float(Q[k][0]), 2), 'y1': round(float(Q[k][1]), 2), 'x2': round(float(Q[k + 1][0]), 2), 'y2': round(float(Q[k + 1][1]), 2)} for _, k in longest]
    length = float(sum(s for s, _ in seg))

    allx = [float(v) for d in letters for v in re.findall(r'-?\d+\.?\d*', d)[0::2]]
    ally = [float(v) for d in letters for v in re.findall(r'-?\d+\.?\d*', d)[1::2]]
    js = f"""// Generated by scripts/extract_fsstudio_logo.py from the FS Studio brand book (page 1, vector). Do not edit by hand.
// Units are the brand book's page units; the lockup viewBox spans the icon and the FSSTUDIO wordmark.
export const VIEWBOX = {json.dumps(VB)};
export const ICON_VIEWBOX = {json.dumps(ICON_VB)};
/** The icon artwork (filled outline, brand pink #FF059F). */
export const ICON_PATH = {json.dumps(icon)};
/** The icon's centreline, tip to tip, and the stroke width that reproduces the artwork. */
export const CENTRE_PATH = {json.dumps(centre)};
export const CENTRE_LENGTH = {length:.1f};
export const STROKE_W = {width:.2f};
/** The three long straight runs of the centreline (the finale's recap tiles collapse onto them). */
export const STROKES = {json.dumps(strokes)};
/** FSSTUDIO, one path per letter, left to right. */
export const LETTER_PATHS = {json.dumps(letters, indent=1)};
export const WORDMARK = {{ x1: {min(allx):.2f}, x2: {max(allx):.2f}, top: {min(ally):.2f}, baseline: {max(ally):.2f} }};
"""
    open(os.path.join(ROOT, 'video/src/lib/logo-data-fsstudio.js'), 'w').write(js)
    print(f'icon centreline: {len(Q)} points, length {length:.1f}, stroke {width:.2f}; strokes {strokes}')


if __name__ == '__main__':
    main()
