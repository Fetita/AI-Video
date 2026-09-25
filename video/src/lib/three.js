// Minimal 3D math for canvas renders: vectors, rotations, look-at cameras, projection.
export const v3 = (x = 0, y = 0, z = 0) => ({ x, y, z });
export const add = (a, b) => ({ x: a.x + b.x, y: a.y + b.y, z: a.z + b.z });
export const sub = (a, b) => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z });
export const mul = (a, s) => ({ x: a.x * s, y: a.y * s, z: a.z * s });
export const dot = (a, b) => a.x * b.x + a.y * b.y + a.z * b.z;
export const cross = (a, b) => ({ x: a.y * b.z - a.z * b.y, y: a.z * b.x - a.x * b.z, z: a.x * b.y - a.y * b.x });
export const len = (a) => Math.hypot(a.x, a.y, a.z);
export const norm = (a) => { const l = len(a) || 1; return { x: a.x / l, y: a.y / l, z: a.z / l }; };
export const lerp3 = (a, b, t) => ({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, z: a.z + (b.z - a.z) * t });

/** Rotate v around unit axis k by angle a (Rodrigues). */
export function rotAxis(v, k, a) {
  const c = Math.cos(a), s = Math.sin(a);
  const kv = cross(k, v), kd = dot(k, v);
  return { x: v.x * c + kv.x * s + k.x * kd * (1 - c), y: v.y * c + kv.y * s + k.y * kd * (1 - c), z: v.z * c + kv.z * s + k.z * kd * (1 - c) };
}
/** Rotation from yaw (around y), pitch (around x), roll (around z). Returns fn(v). */
export function euler(yaw = 0, pitch = 0, roll = 0) {
  const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch), cr = Math.cos(roll), sr = Math.sin(roll);
  return (v) => {
    // roll (z)
    let x = v.x * cr - v.y * sr, y = v.x * sr + v.y * cr, z = v.z;
    // pitch (x)
    const y2 = y * cp - z * sp, z2 = y * sp + z * cp; y = y2; z = z2;
    // yaw (y)
    const x3 = x * cy + z * sy, z3 = -x * sy + z * cy;
    return { x: x3, y, z: z3 };
  };
}

/** Look-at camera. Returns {project(p) -> {x,y,z,s}} with z = view depth and s = px per world unit at that depth. */
export function camera(eye, target, { f = 1100, cx = 960, cy = 540, up = v3(0, 1, 0) } = {}) {
  // World is x right, y up, z forward (left-handed), so right = up × forward.
  const fw = norm(sub(target, eye));
  const rt = norm(cross(up, fw));
  const u = cross(fw, rt);
  return {
    eye, fw, rt, u,
    project(p) {
      const d = sub(p, eye);
      const z = dot(d, fw);
      const x = dot(d, rt), y = dot(d, u);
      const s = f / Math.max(z, 0.05);
      return { x: cx + x * s, y: cy - y * s, z, s };
    },
  };
}
/** Simple pinhole projection for points already in camera space (x right, y down, z forward). */
export const pinhole = (p, f = 1100, cx = 960, cy = 540) => { const s = f / Math.max(p.z, 0.05); return { x: cx + p.x * s, y: cy + p.y * s, z: p.z, s }; };
