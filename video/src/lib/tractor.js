// Line-art tractor (side view) with a boom-mounted camera and its field of view.
// Shared by the agriculture scene of the AI Studio film and the field chapter of the impact film.
import { rgba, C, rrect } from '../engine.js';
import { SPEED } from './field.js';

export function drawTractor(g, t, ox, oy, S, camPulse, a) {
  g.save(); g.globalAlpha = a; g.translate(ox, oy); g.scale(S, S);
  g.lineJoin = 'round'; g.lineCap = 'round';
  const ink = 'rgba(243,243,239,0.9)', fill = '#0f1216';
  // boom + camera + FOV
  g.strokeStyle = ink; g.lineWidth = 3;
  g.beginPath(); g.moveTo(300, -40); g.lineTo(430, -120); g.lineTo(520, -120); g.stroke();
  const fov = g.createLinearGradient(0, -110, 0, 95);
  fov.addColorStop(0, `rgba(130,52,254,${0.35 + camPulse * 0.25})`); fov.addColorStop(1, 'rgba(130,52,254,0.04)');
  g.fillStyle = fov; g.beginPath(); g.moveTo(520, -108); g.lineTo(420, 95); g.lineTo(650, 95); g.closePath(); g.fill();
  g.strokeStyle = rgba(C.accent, 0.55); g.lineWidth = 1.5; g.beginPath(); g.moveTo(520, -108); g.lineTo(420, 95); g.moveTo(520, -108); g.lineTo(650, 95); g.stroke();
  g.fillStyle = fill; g.strokeStyle = C.accent; g.lineWidth = 3; rrect(g, 500, -134, 42, 28, 6); g.fill(); g.stroke();
  g.fillStyle = C.accent; g.beginPath(); g.arc(521, -106, 5, 0, Math.PI * 2); g.fill();
  if (camPulse > 0) { g.strokeStyle = rgba(C.accent, camPulse); g.lineWidth = 2; g.beginPath(); g.arc(521, -120, 30 + (1 - camPulse) * 30, 0, Math.PI * 2); g.stroke(); }
  // body
  g.fillStyle = fill; g.strokeStyle = ink; g.lineWidth = 3;
  g.beginPath(); g.moveTo(40, -40); g.lineTo(310, -52); g.quadraticCurveTo(334, -50, 336, -26); g.lineTo(336, 8); g.lineTo(40, 14); g.closePath(); g.fill(); g.stroke();
  for (let i = 0; i < 4; i++) { g.beginPath(); g.moveTo(318, -40 + i * 11); g.lineTo(334, -40 + i * 11); g.stroke(); }
  g.beginPath(); g.moveTo(180, -48); g.lineTo(180, -118); g.stroke();
  // cabin
  g.beginPath(); g.moveTo(-70, -40); g.lineTo(-58, -222); g.lineTo(96, -222); g.lineTo(118, -40); g.closePath(); g.fill(); g.stroke();
  g.strokeStyle = 'rgba(243,243,239,0.35)'; g.lineWidth = 2; rrect(g, -44, -206, 128, 120, 8); g.stroke();
  g.strokeStyle = ink; g.lineWidth = 3;
  g.beginPath(); g.moveTo(-80, -226); g.lineTo(106, -226); g.stroke();
  // wheels
  const wheel = (x, y, R) => {
    g.fillStyle = '#0b0d10'; g.beginPath(); g.arc(x, y, R, 0, Math.PI * 2); g.fill();
    g.strokeStyle = ink; g.lineWidth = 3; g.stroke();
    g.strokeStyle = 'rgba(243,243,239,0.5)'; g.lineWidth = 2; g.beginPath(); g.arc(x, y, R * 0.58, 0, Math.PI * 2); g.stroke();
    const rot = -t * (SPEED * 0.9 / R);
    for (let i = 0; i < 14; i++) { const an = rot + (i / 14) * Math.PI * 2; g.beginPath(); g.moveTo(x + Math.cos(an) * R * 0.78, y + Math.sin(an) * R * 0.78); g.lineTo(x + Math.cos(an) * R * 0.97, y + Math.sin(an) * R * 0.97); g.stroke(); }
    g.fillStyle = ink; g.beginPath(); g.arc(x, y, R * 0.12, 0, Math.PI * 2); g.fill();
  };
  wheel(0, 0, 95);
  wheel(262, 40, 55);
  g.restore();
}
