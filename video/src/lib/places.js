// Fictional location "photos" for the scouting demo — editorial flat illustrations.
// Each returns an SVG string (viewBox 0 0 480 300). `id` keeps defs unique per instance.

const bricks = (id, base = '#8e4632', mortar = 'rgba(38,18,12,0.38)') => `
  <pattern id="${id}b" width="36" height="16" patternUnits="userSpaceOnUse">
    <rect width="36" height="16" fill="${base}"/>
    <path d="M0 0.5H36M0 8.5H36M0.5 0V8M18.5 8V16" stroke="${mortar}" stroke-width="1.2"/>
    <rect x="2" y="2" width="14" height="5" fill="rgba(255,255,255,0.035)"/>
    <rect x="21" y="10" width="12" height="5" fill="rgba(0,0,0,0.06)"/>
  </pattern>`;

export function loft(id = 'lf') {
  const panes = [];
  for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) panes.push(`<rect x="${158 + i * 45}" y="${46 + j * 45}" width="40" height="40" fill="url(#${id}g)"/>`);
  const floorPanes = [];
  for (let i = 0; i < 4; i++) for (let j = 0; j < 2; j++) {
    const x0 = 262 + i * 38 + j * 22, y0 = 248 + j * 20;
    floorPanes.push(`<path d="M${x0} ${y0}L${x0 + 34} ${y0}L${x0 + 54} ${y0 + 17}L${x0 + 20} ${y0 + 17}Z" fill="rgba(255,226,170,0.20)"/>`);
  }
  return `<svg viewBox="0 0 480 300" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice">
  <defs>${bricks(id)}
    <linearGradient id="${id}g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff1d6"/><stop offset="1" stop-color="#f6c07e"/></linearGradient>
    <linearGradient id="${id}w" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="0.45"/></linearGradient>
    <linearGradient id="${id}beam" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff3d9" stop-opacity="0.30"/><stop offset="1" stop-color="#fff3d9" stop-opacity="0"/></linearGradient>
    <linearGradient id="${id}f" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5a3824"/><stop offset="1" stop-color="#2c1a10"/></linearGradient>
  </defs>
  <rect width="480" height="300" fill="url(#${id}b)"/>
  <rect width="480" height="300" fill="url(#${id}w)"/>
  <rect x="150" y="38" width="196" height="196" fill="#1b2024"/>
  ${panes.join('')}
  <path d="M172 118 L205 88 L232 104 L232 132 L172 132Z" fill="rgba(160,120,80,0.25)"/>
  <path d="M150 234 L346 234 L480 300 L230 300Z" fill="url(#${id}beam)"/>
  <rect x="0" y="236" width="480" height="64" fill="url(#${id}f)"/>
  <path d="M0 252H480M0 270H480M0 290H480" stroke="rgba(0,0,0,0.25)" stroke-width="1"/>
  ${floorPanes.join('')}
  <path d="M150 38 L346 38 L480 300 L230 300Z" fill="url(#${id}beam)" opacity="0.55"/>
  <path d="M410 0V58" stroke="#111" stroke-width="2"/>
  <path d="M392 72 Q410 50 428 72Z" fill="#15191c"/><ellipse cx="410" cy="73" rx="10" ry="3" fill="#ffd9a0"/>
  <rect x="52" y="246" width="34" height="30" rx="3" fill="#2a2d2f"/>
  <path d="M69 248 C50 220 40 206 48 190 C60 205 64 222 69 248 C72 214 80 196 92 186 C94 206 82 226 69 248 C84 224 100 216 110 214 C104 232 88 242 69 248Z" fill="#2f5a36"/>
  <rect x="360" y="226" width="96" height="26" rx="6" fill="#3a2a22"/><rect x="354" y="214" width="108" height="16" rx="7" fill="#4a3529"/>
</svg>`;
}

export function studio(id = 'st') {
  const city = (x) => `
    <rect x="${x}" y="30" width="86" height="176" fill="url(#${id}sky)"/>
    <path d="M${x} 206 V150 h14 v-22 h12 v30 h10 v-44 h16 v52 h10 v-26 h14 v60Z" fill="#1d2433"/>
    <rect x="${x + 16}" y="140" width="3" height="3" fill="#ffd27a"/><rect x="${x + 44}" y="126" width="3" height="3" fill="#ffd27a"/><rect x="${x + 50}" y="160" width="3" height="3" fill="#ffd27a"/>
    <path d="M${x + 43} 30V206M${x} 88H${x + 86}M${x} 148H${x + 86}" stroke="#23272c" stroke-width="4"/>
    <rect x="${x}" y="30" width="86" height="176" fill="none" stroke="#23272c" stroke-width="6"/>`;
  return `<svg viewBox="0 0 480 300" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice">
  <defs>
    <linearGradient id="${id}sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2d4466"/><stop offset="0.7" stop-color="#8a8fa8"/><stop offset="1" stop-color="#f0b27a"/></linearGradient>
    <linearGradient id="${id}wall" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#7f8284"/><stop offset="1" stop-color="#a3a6a6"/></linearGradient>
    <linearGradient id="${id}fl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6d706f"/><stop offset="1" stop-color="#3f4241"/></linearGradient>
  </defs>
  <rect width="480" height="300" fill="url(#${id}wall)"/>
  <path d="M0 0H480V14H0Z" fill="#5f6264"/>
  ${city(70)}${city(186)}
  <rect x="0" y="206" width="480" height="94" fill="url(#${id}fl)"/>
  <path d="M70 206 L156 206 L176 300 L60 300Z" fill="rgba(240,178,122,0.16)"/>
  <path d="M186 206 L272 206 L300 300 L186 300Z" fill="rgba(240,178,122,0.14)"/>
  <rect x="300" y="112" width="180" height="6" fill="#2b2e31"/>
  <path d="M306 112V90M324 112V90M342 112V90M360 112V90M378 112V90M396 112V90M414 112V90M432 112V90M450 112V90M468 112V90M300 90H480" stroke="#2b2e31" stroke-width="2"/>
  <rect x="330" y="132" width="110" height="74" fill="#565a5d"/>
  <path d="M330 144H440M330 156H440M330 168H440M330 180H440M330 192H440M385 132V206" stroke="#46494c" stroke-width="2"/>
  <rect x="24" y="226" width="30" height="42" rx="2" fill="#2b2f33"/><rect x="18" y="220" width="42" height="8" rx="2" fill="#3a3f44"/>
</svg>`;
}

export function mill(id = 'ml') {
  const wins = [];
  for (let r = 0; r < 3; r++) for (let c = 0; c < 5; c++) {
    const x = 150 + c * 50, y = 92 + r * 52;
    wins.push(`<path d="M${x} ${y + 30} V${y + 12} A14 12 0 0 1 ${x + 28} ${y + 12} V${y + 30} Z" fill="${(r + c) % 3 === 0 ? '#ffd79a' : '#2a2f38'}"/>`);
    wins.push(`<path d="M${x + 14} ${y} V${y + 30} M${x} ${y + 17} H${x + 28}" stroke="#5b3025" stroke-width="1.5"/>`);
  }
  return `<svg viewBox="0 0 480 300" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice">
  <defs>${bricks(id, '#9c4f37', 'rgba(50,20,12,0.32)')}
    <linearGradient id="${id}sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8fb0d6"/><stop offset="0.65" stop-color="#f1c490"/><stop offset="1" stop-color="#f6a867"/></linearGradient>
    <radialGradient id="${id}sun" cx="0.8" cy="0.62" r="0.5"><stop offset="0" stop-color="#fff2c9" stop-opacity="0.9"/><stop offset="1" stop-color="#fff2c9" stop-opacity="0"/></radialGradient>
    <linearGradient id="${id}wa" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5b6f86"/><stop offset="1" stop-color="#2a3442"/></linearGradient>
    <linearGradient id="${id}shade" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#000" stop-opacity="0.28"/><stop offset="0.5" stop-color="#000" stop-opacity="0"/></linearGradient>
  </defs>
  <rect width="480" height="300" fill="url(#${id}sky)"/>
  <rect width="480" height="300" fill="url(#${id}sun)"/>
  <rect x="96" y="24" width="26" height="226" fill="url(#${id}b)"/><rect x="92" y="18" width="34" height="10" fill="#6c3326"/>
  <rect x="136" y="70" width="276" height="180" fill="url(#${id}b)"/>
  <rect x="136" y="70" width="276" height="180" fill="url(#${id}shade)"/>
  <path d="M130 70 L274 34 L418 70Z" fill="#5a2c21"/>
  ${wins.join('')}
  <rect x="0" y="246" width="480" height="54" fill="url(#${id}wa)"/>
  <rect x="136" y="250" width="276" height="26" fill="#9c4f37" opacity="0.35"/>
  <path d="M40 262H120M170 270H300M330 262H440M60 284H200M260 290H420" stroke="rgba(255,220,170,0.35)" stroke-width="2"/>
</svg>`;
}

export function rooftop(id = 'rt') {
  const bulbs = [];
  for (let i = 0; i <= 12; i++) {
    const x = 20 + i * 37, y = 96 + Math.sin((i / 12) * Math.PI) * 26;
    bulbs.push(`<circle cx="${x}" cy="${y}" r="7" fill="#ffd27a" opacity="0.18"/><circle cx="${x}" cy="${y}" r="2.6" fill="#fff0c2"/>`);
  }
  const lit = [];
  const rnd = (s) => { const x = Math.sin(s * 91.7) * 43758.5; return x - Math.floor(x); };
  for (let i = 0; i < 46; i++) lit.push(`<rect x="${(rnd(i) * 470) | 0}" y="${(150 + rnd(i + 50) * 60) | 0}" width="3" height="3" fill="#ffcf7a" opacity="${0.5 + rnd(i + 9) * 0.5}"/>`);
  return `<svg viewBox="0 0 480 300" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice">
  <defs>
    <linearGradient id="${id}sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1b2446"/><stop offset="0.5" stop-color="#8e5a86"/><stop offset="0.85" stop-color="#f0a15e"/></linearGradient>
    <linearGradient id="${id}deck" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3b2c2a"/><stop offset="1" stop-color="#1c1514"/></linearGradient>
  </defs>
  <rect width="480" height="300" fill="url(#${id}sky)"/>
  <path d="M0 216 V160 h26 v-30 h18 v40 h22 v-58 h30 v70 h20 v-36 h24 v52 h18 v-80 h28 v88 h16 v-44 h30 v60 h22 v-28 h26 v42 h20 v-66 h30 v76 h16 v-36 h20 v40 h22 v-22 h14 v42 Z" fill="#161b2d"/>
  ${lit.join('')}
  <path d="M20 96 Q240 150 464 96" stroke="#2a2330" stroke-width="1.2" fill="none"/>
  ${bulbs.join('')}
  <rect x="0" y="222" width="480" height="78" fill="url(#${id}deck)"/>
  <path d="M0 222H480" stroke="#8f8a9c" stroke-width="2"/>
  <path d="M0 206H480M40 206V222M120 206V222M200 206V222M280 206V222M360 206V222M440 206V222" stroke="#6f6a7c" stroke-width="2"/>
  <path d="M0 240H480M0 262H480M0 286H480" stroke="rgba(0,0,0,0.3)"/>
  <rect x="150" y="236" width="70" height="8" rx="3" fill="#57412f"/><path d="M160 244V270M210 244V270" stroke="#57412f" stroke-width="4"/>
  <rect x="300" y="244" width="46" height="26" rx="5" fill="#2f3a3a"/><rect x="298" y="232" width="8" height="38" rx="3" fill="#2f3a3a"/>
</svg>`;
}

export function warehouse(id = 'wh') {
  const ribs = [];
  for (let x = 60; x < 420; x += 9) ribs.push(`<path d="M${x} 104V238" stroke="rgba(0,0,0,0.16)" stroke-width="2"/>`);
  return `<svg viewBox="0 0 480 300" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice">
  <defs><linearGradient id="${id}sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#aab6bf"/><stop offset="1" stop-color="#e3e7ea"/></linearGradient></defs>
  <rect width="480" height="300" fill="url(#${id}sky)"/>
  <path d="M50 104 L240 62 L430 104 V238 H50Z" fill="#6c7a84"/>
  ${ribs.join('')}
  <rect x="190" y="150" width="100" height="88" fill="#3d464d"/><path d="M190 162H290M190 174H290M190 186H290M190 198H290M190 210H290M190 222H290" stroke="#4b555c"/>
  <rect x="330" y="200" width="120" height="40" fill="#b8563d"/><rect x="340" y="170" width="100" height="32" fill="#3f6b7c"/>
  <rect x="0" y="238" width="480" height="62" fill="#8b8f90"/><path d="M0 262H480" stroke="#9fa3a4" stroke-width="3" stroke-dasharray="26 18"/>
</svg>`;
}

export function office(id = 'of') {
  return `<svg viewBox="0 0 480 300" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice">
  <defs><linearGradient id="${id}g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#dfe9f1"/><stop offset="1" stop-color="#b9c9d6"/></linearGradient></defs>
  <rect width="480" height="300" fill="url(#${id}g)"/>
  <path d="M0 40H480" stroke="#fff" stroke-width="10" opacity="0.8"/><path d="M60 40H160M220 40H320M380 40H470" stroke="#ffffff" stroke-width="4"/>
  <path d="M80 60V230M200 60V230M320 60V230M440 60V230" stroke="rgba(120,150,170,0.5)" stroke-width="3"/>
  <rect x="90" y="170" width="100" height="10" fill="#f5f7f9"/><rect x="210" y="170" width="100" height="10" fill="#f5f7f9"/><rect x="330" y="170" width="100" height="10" fill="#f5f7f9"/>
  <rect x="120" y="140" width="34" height="26" fill="#30404d"/><rect x="240" y="140" width="34" height="26" fill="#30404d"/><rect x="360" y="140" width="34" height="26" fill="#30404d"/>
  <rect x="0" y="230" width="480" height="70" fill="#cfd8df"/>
</svg>`;
}

export function barn(id = 'bn') {
  return `<svg viewBox="0 0 480 300" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice">
  <defs><linearGradient id="${id}sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9cc3de"/><stop offset="1" stop-color="#f3e2c4"/></linearGradient></defs>
  <rect width="480" height="300" fill="url(#${id}sky)"/>
  <path d="M0 200 Q120 150 250 190 T480 180 V300 H0Z" fill="#7d9a5b"/>
  <path d="M0 240 Q160 200 300 236 T480 226 V300 H0Z" fill="#5f7d43"/>
  <path d="M170 120 L240 76 L310 120 V222 H170Z" fill="#8f3b2c"/>
  <path d="M170 120 L240 76 L310 120" stroke="#f1e9dc" stroke-width="5" fill="none"/>
  <rect x="214" y="160" width="52" height="62" fill="#6d2a1f" stroke="#f1e9dc" stroke-width="4"/><path d="M214 160L266 222M266 160L214 222" stroke="#f1e9dc" stroke-width="3"/>
  <rect x="228" y="104" width="24" height="20" fill="#2c2420" stroke="#f1e9dc" stroke-width="3"/>
</svg>`;
}

export const PLACES = { loft, studio, mill, rooftop, warehouse, office, barn };

/** Tiny procedural thumbnail for the catalog wall (canvas 2D). */
export function thumb(g, x, y, w, hh, r) {
  const skies = [['#8fb0d6', '#f1c490'], ['#2d4466', '#f0b27a'], ['#aab6bf', '#e3e7ea'], ['#1b2446', '#f0a15e'], ['#9cc3de', '#f3e2c4'], ['#dfe9f1', '#b9c9d6'], ['#5b3a2a', '#c07a4f']];
  const walls = ['#9c4f37', '#6c7a84', '#8f3b2c', '#7f8284', '#3f6b7c', '#c9b79c', '#56463b', '#2c3440'];
  const s = skies[Math.floor(r() * skies.length)];
  const grad = g.createLinearGradient(0, y, 0, y + hh);
  grad.addColorStop(0, s[0]); grad.addColorStop(1, s[1]);
  g.fillStyle = grad;
  g.fillRect(x, y, w, hh);
  const n = 1 + Math.floor(r() * 3);
  for (let i = 0; i < n; i++) {
    const bw = w * (0.25 + r() * 0.45), bh = hh * (0.3 + r() * 0.55);
    const bx = x + r() * (w - bw), by = y + hh - bh - hh * 0.12;
    g.fillStyle = walls[Math.floor(r() * walls.length)];
    g.fillRect(bx, by, bw, bh);
    g.fillStyle = 'rgba(255,225,160,0.55)';
    const cols = 2 + Math.floor(r() * 3);
    for (let c = 0; c < cols; c++) g.fillRect(bx + (c + 0.3) * (bw / cols), by + bh * 0.25, bw / cols * 0.35, bh * 0.2);
  }
  g.fillStyle = 'rgba(20,16,14,0.55)';
  g.fillRect(x, y + hh * 0.88, w, hh * 0.12);
}
