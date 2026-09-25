"""Visual QA for audio I can't audition: short-term loudness, spectrogram, clicks, peaks.

python3 analyze.py build/music.wav out.png
"""
import json, os, sys
import numpy as np
import soundfile as sf
import pyloudnorm as pyln
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.signal import spectrogram

HERE = os.path.dirname(os.path.abspath(__file__))
path, out = sys.argv[1], sys.argv[2]
x, sr = sf.read(path)
mono = x.mean(axis=1) if x.ndim == 2 else x
meter = pyln.Meter(sr)
integ = meter.integrated_loudness(x)
# short-term loudness (3 s window, 0.5 s hop)
st, times = [], []
win, hop = int(3 * sr), int(0.5 * sr)
for s in range(0, len(x) - win, hop):
    st.append(meter.integrated_loudness(x[s:s + win]) if np.max(np.abs(x[s:s + win])) > 1e-4 else -70)
    times.append((s + win / 2) / sr)
# clicks: sample-to-sample jumps far above the local signal slope
d = np.abs(np.diff(mono))
thr = 0.25
clicks = np.where(d > thr)[0] / sr
peak = 20 * np.log10(np.max(np.abs(x)) + 1e-12)
tl = json.load(open(os.path.join(HERE, 'build', 'timeline.json')))
fig, ax = plt.subplots(3, 1, figsize=(16, 10), gridspec_kw={'height_ratios': [1, 1, 2]})
tt = np.arange(len(mono)) / sr
env = np.sqrt(np.convolve(mono ** 2, np.ones(2400) / 2400, mode='same'))
ax[0].plot(tt[::240], 20 * np.log10(env[::240] + 1e-9), lw=0.6)
ax[0].set_ylim(-60, 0); ax[0].set_ylabel('RMS dBFS'); ax[0].set_title(f'{os.path.basename(path)}  integrated {integ:.1f} LUFS  peak {peak:.1f} dBFS  big jumps {len(clicks)}')
ax[1].plot(times, st, lw=1.2, color='tab:orange'); ax[1].set_ylim(-40, -5); ax[1].set_ylabel('short-term LUFS'); ax[1].grid(alpha=0.3)
f, t, Sxx = spectrogram(mono, sr, nperseg=4096, noverlap=2048)
ax[2].pcolormesh(t, f, 10 * np.log10(Sxx + 1e-14), shading='auto', vmin=-130, vmax=-40, cmap='magma')
ax[2].set_yscale('symlog', linthresh=200); ax[2].set_ylim(30, 20000); ax[2].set_ylabel('Hz')
for a in ax:
    for s in tl['scenes']:
        a.axvline(s['start'], color='cyan', lw=0.8, alpha=0.6)
    a.set_xlim(0, len(mono) / sr)
for s in tl['scenes']:
    ax[0].text(s['start'] + 0.3, -8, s['id'], color='teal', fontsize=9)
plt.tight_layout(); plt.savefig(out, dpi=80)
print(f'integrated {integ:.2f} LUFS, peak {peak:.2f} dBFS, jumps>{thr}: {len(clicks)}', clicks[:10])
