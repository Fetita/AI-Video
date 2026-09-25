"""Final mix: voiceover chain + music (ducked under VO) + sound design → master.

Targets: VO ≈ −16 LUFS, music bed ~7 dB under the voice, master −14 LUFS integrated,
peaks ≤ −1 dBFS. Writes build/mix.wav (48 kHz, 24-bit) and build/vo.wav.
"""
import json
import os

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

from synth import SR, n_of, filt, pan, place, reverb, rms_env, smooth_gain, limiter, undb, db

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(HERE, 'build')
TL = json.load(open(os.path.join(B, 'timeline.json')))
DUR = TL['duration'] + 2.5
N = n_of(DUR)
meter = pyln.Meter(SR)


def compress(x, thr_db=-24, ratio=2.5, att=0.005, rel=0.12, makeup_db=0.0):
    env = db(rms_env(x, 0.02))
    over = np.maximum(0, env - thr_db)
    gr = -over * (1 - 1 / ratio)
    g = smooth_gain(undb(gr), att=att, rel=rel)
    return x * g * undb(makeup_db)


# ------------------------------------------------------------------ voiceover
vo = np.zeros(N)
for lid, l in TL['lines'].items():
    x, sr = sf.read(os.path.join(B, 'vo', f'{lid}.wav'))
    assert sr == SR
    place_at = int(round(l['start'] * SR))
    vo[place_at: place_at + len(x)] += x[: max(0, N - place_at)]
vo = filt(vo, 'hp', 75, 0.7)
vo = filt(vo, 'peak', 250, 1.0, -1.5)     # de-box
vo = filt(vo, 'peak', 3300, 0.9, 2.0)     # presence
vo = filt(vo, 'highshelf', 10000, 0.7, 1.5)
vo = compress(vo, thr_db=-26, ratio=2.2)
vo_st = reverb(pan(vo, 0.0), wet=0.07, dur=0.7, tone=6000, predelay=0.012)
vo_st *= undb(-16.0 - meter.integrated_loudness(vo_st))
sf.write(os.path.join(B, 'vo.wav'), vo_st.astype(np.float32), SR)

# ------------------------------------------------------------------ music + ducking
music, _ = sf.read(os.path.join(B, 'music.wav'))
music = music[:N] if len(music) >= N else np.pad(music, ((0, N - len(music)), (0, 0)))
env = db(rms_env(vo_st, 0.05))
active = np.clip((env + 50) / 12, 0, 1)
duck = smooth_gain(undb(-8.5 * active), att=0.09, rel=0.55)
music_bed = music * undb(-4.0) * duck[:, None]

sfx, _ = sf.read(os.path.join(B, 'sfx.wav'))
sfx = sfx[:N] if len(sfx) >= N else np.pad(sfx, ((0, N - len(sfx)), (0, 0)))
sfx *= undb(5.0)

mix = music_bed + vo_st + sfx
mix = filt(mix, 'hp', 24, 0.7)
# master: set integrated loudness, then limit; iterate once to land on target after limiting
target = -14.0
for _ in range(2):
    mix *= undb(target - meter.integrated_loudness(mix))
    mix = limiter(mix, ceiling_db=-2.3, release=0.06)
# end exactly with the picture: gentle fade over the final fade-to-black
END = n_of(TL['duration'])
fl = n_of(1.8)
mix = mix[:END]
mix[-fl:] *= (np.linspace(1, 0, fl) ** 1.6)[:, None]
sf.write(os.path.join(B, 'mix.wav'), mix.astype(np.float32), SR, subtype='FLOAT')
print(f"mix: {meter.integrated_loudness(mix):.2f} LUFS, peak {20 * np.log10(np.max(np.abs(mix))):.2f} dBFS, "
      f"VO {meter.integrated_loudness(vo_st):.1f} LUFS, bed {meter.integrated_loudness(music_bed):.1f} LUFS, sfx {meter.integrated_loudness(sfx):.1f} LUFS")
