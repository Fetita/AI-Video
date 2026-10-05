// Frame-accurate footage: a clip is a folder of numbered JPEG frames (scripts/extract_clips.sh)
// shown through an <img>. show() returns a promise that resolves once the requested frame is decoded,
// and the engine's seek() waits for it, so every rendered frame shows exactly the right source frame.
import { h, clamp } from '../engine.js';

export function makeClip(parent, { name, frames, fps = 30, style = {} }) {
  const img = h('img', { style: { position: 'absolute', left: '0', top: '0', width: '100%', height: '100%', objectFit: 'cover', display: 'block', ...style } });
  parent.append(img);
  let cur = -1;
  let ready = null;
  return {
    el: img,
    /** Show the frame at clip time `t` (seconds). Returns a promise while that frame decodes. */
    show(t) {
      const i = clamp(Math.floor(t * fps + 1e-6), 0, frames - 1);
      if (i !== cur) {
        cur = i;
        img.src = `build/clips/${name}/${String(i).padStart(4, '0')}.jpg`;
        ready = img.decode().catch(() => {});
      }
      return ready;
    },
  };
}
