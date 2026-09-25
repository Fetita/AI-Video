"""Small numpy DSP toolkit used to synthesize the score and sound design.

Everything is generated from scratch (no samples), so the soundtrack is fully
original and license-free.
"""
import numpy as np
from scipy.signal import lfilter, fftconvolve

SR = 48000


def secs(n):
    return n / SR


def n_of(dur):
    return max(1, int(round(dur * SR)))


def t_of(n):
    return np.arange(n) / SR


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


# ----------------------------------------------------------------- envelopes
def adsr(n, a=0.01, d=0.1, s=0.7, r=0.2):
    env = np.full(n, s, dtype=np.float64)
    na, nd, nr = n_of(a), n_of(d), n_of(r)
    na = min(na, n)
    env[:na] = np.linspace(0, 1, na, endpoint=False)
    e = min(n, na + nd)
    if e > na:
        env[na:e] = np.linspace(1, s, e - na, endpoint=False)
    nr = min(nr, n)
    env[n - nr:] *= np.linspace(1, 0, nr) ** 1.5
    return env


def exp_env(n, tau, attack=0.002):
    t = t_of(n)
    env = np.exp(-t / tau)
    na = min(n, n_of(attack))
    if na > 1:
        env[:na] *= np.linspace(0, 1, na)
    return env


def fade(x, fin=0.005, fout=0.02):
    x = x.copy()
    a, b = min(len(x), n_of(fin)), min(len(x), n_of(fout))
    if a > 1:
        x[:a] *= np.linspace(0, 1, a)[:, None] if x.ndim == 2 else np.linspace(0, 1, a)
    if b > 1:
        x[-b:] *= np.linspace(1, 0, b)[:, None] if x.ndim == 2 else np.linspace(1, 0, b)
    return x


# ----------------------------------------------------------------- oscillators
def sine(f, n, phase=0.0):
    return np.sin(2 * np.pi * np.asarray(f) * t_of(n) + phase) if np.isscalar(f) else np.sin(2 * np.pi * np.cumsum(f) / SR + phase)


def saw(f, n, max_h=48, phase=0.0, bright=1.0):
    """Band-limited sawtooth (additive), harmonics up to ~16 kHz."""
    t = t_of(n)
    K = int(min(max_h, 16000 / f))
    out = np.zeros(n)
    for k in range(1, K + 1):
        out += np.sin(2 * np.pi * k * f * t + phase * k) / (k ** bright)
    return out * (2 / np.pi)


def square(f, n, max_h=31, phase=0.0):
    t = t_of(n)
    K = int(min(max_h, 16000 / f))
    out = np.zeros(n)
    for k in range(1, K + 1, 2):
        out += np.sin(2 * np.pi * k * f * t + phase * k) / k
    return out * (4 / np.pi)


def pluck(f, dur, bright=1.0, decay=0.6, K=28):
    """Additive plucked tone: upper harmonics decay faster."""
    n = n_of(dur)
    t = t_of(n)
    out = np.zeros(n)
    for k in range(1, K + 1):
        if k * f > 15000:
            break
        amp = 1.0 / (k ** (1.25 / bright))
        out += amp * np.sin(2 * np.pi * k * f * t) * np.exp(-t * (1.0 / decay + 1.6 * (k - 1) / bright))
    return out * exp_env(n, decay * 2.2, attack=0.002)


def fm_bell(f, dur, ratio=3.5, index=2.4, tau=1.4, itau=0.35):
    n = n_of(dur)
    t = t_of(n)
    I = index * np.exp(-t / itau)
    x = np.sin(2 * np.pi * f * t + I * np.sin(2 * np.pi * f * ratio * t))
    x += 0.25 * np.sin(2 * np.pi * f * 2.0 * t) * np.exp(-t / (tau * 0.4))
    return x * exp_env(n, tau, attack=0.003)


def noise(n, seed=0):
    return np.random.default_rng(seed).standard_normal(n)


# ----------------------------------------------------------------- filters (RBJ biquads)
def biquad(kind, f0, q=0.707, gain_db=0.0):
    A = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * min(f0, SR * 0.45) / SR
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2 * q)
    if kind == 'lp':
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]; a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == 'hp':
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]; a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == 'bp':
        b = [alpha, 0, -alpha]; a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == 'peak':
        b = [1 + alpha * A, -2 * cw, 1 - alpha * A]; a = [1 + alpha / A, -2 * cw, 1 - alpha / A]
    elif kind == 'lowshelf':
        sq = 2 * np.sqrt(A) * alpha
        b = [A * ((A + 1) - (A - 1) * cw + sq), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - sq)]
        a = [(A + 1) + (A - 1) * cw + sq, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - sq]
    elif kind == 'highshelf':
        sq = 2 * np.sqrt(A) * alpha
        b = [A * ((A + 1) + (A - 1) * cw + sq), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - sq)]
        a = [(A + 1) - (A - 1) * cw + sq, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - sq]
    else:
        raise ValueError(kind)
    b, a = np.array(b) / a[0], np.array(a) / a[0]
    return b, a


def filt(x, kind, f0, q=0.707, gain_db=0.0):
    b, a = biquad(kind, f0, q, gain_db)
    return lfilter(b, a, x, axis=0)


def sweep(x, kind, f_start, f_end, q=0.9, block=256, curve='exp'):
    """Time-varying biquad (coefficients updated per block, state carried)."""
    n = len(x)
    out = np.zeros_like(x)
    zi = np.zeros(2) if x.ndim == 1 else np.zeros((2, x.shape[1]))
    nb = (n + block - 1) // block
    for i in range(nb):
        u = i / max(1, nb - 1)
        f = f_start * (f_end / f_start) ** u if curve == 'exp' else f_start + (f_end - f_start) * u
        b, a = biquad(kind, f, q)
        s, e = i * block, min(n, (i + 1) * block)
        out[s:e], zi = lfilter(b, a, x[s:e], axis=0, zi=zi)
    return out


def sweep_env(x, kind, fenv, q=0.9, block=128):
    """Filter with an arbitrary cutoff envelope (array with one value per sample)."""
    n = len(x)
    out = np.zeros_like(x)
    zi = np.zeros(2) if x.ndim == 1 else np.zeros((2, x.shape[1]))
    for s in range(0, n, block):
        e = min(n, s + block)
        b, a = biquad(kind, float(fenv[s]), q)
        out[s:e], zi = lfilter(b, a, x[s:e], axis=0, zi=zi)
    return out


# ----------------------------------------------------------------- stereo, placement, dynamics
def pan(x, p=0.0):
    """Constant-power pan, p in [-1, 1]. Mono in → stereo out."""
    a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], axis=1)


def widen(xl, xr):
    return np.stack([xl, xr], axis=1)


def place(buf, x, t0, gain=1.0):
    """Mix stereo (or mono → centered) x into buf starting at t0 seconds."""
    if x.ndim == 1:
        x = pan(x, 0.0)
    s = int(round(t0 * SR))
    if s >= len(buf):
        return
    if s < 0:
        x = x[-s:]
        s = 0
    e = min(len(buf), s + len(x))
    buf[s:e] += x[: e - s] * gain


def db(x):
    return 20 * np.log10(np.maximum(np.abs(x), 1e-12))


def undb(d):
    return 10 ** (d / 20.0)


def rms_env(x, win=0.05):
    m = x if x.ndim == 1 else np.mean(x, axis=1)
    k = n_of(win)
    p = np.convolve(m ** 2, np.ones(k) / k, mode='same')
    return np.sqrt(p + 1e-12)


def smooth_gain(g, att=0.01, rel=0.2):
    """One-pole attack/release smoothing of a gain curve (vectorized in blocks)."""
    out = np.empty_like(g)
    a_att, a_rel = np.exp(-1 / (att * SR)), np.exp(-1 / (rel * SR))
    y = g[0]
    # process at 1/16 resolution then interpolate (fast and smooth enough for gain curves)
    step = 16
    idx = np.arange(0, len(g), step)
    ys = np.empty(len(idx))
    aa, ar = a_att ** step, a_rel ** step
    for i, j in enumerate(idx):
        target = g[j]
        c = aa if target < y else ar
        y = c * y + (1 - c) * target
        ys[i] = y
    return np.interp(np.arange(len(g)), idx, ys)


def limiter(x, ceiling_db=-1.0, lookahead=0.004, release=0.08):
    ceiling = undb(ceiling_db)
    peak = np.max(np.abs(x), axis=1) if x.ndim == 2 else np.abs(x)
    k = n_of(lookahead)
    # running max over the lookahead window
    from scipy.ndimage import maximum_filter1d
    pk = maximum_filter1d(peak, size=2 * k + 1)
    gain = np.minimum(1.0, ceiling / np.maximum(pk, 1e-9))
    gain = smooth_gain(gain, att=0.0005, rel=release)
    gain = np.minimum(gain, ceiling / np.maximum(pk, 1e-9) * 1.0001)
    return x * (gain[:, None] if x.ndim == 2 else gain)


def soft_clip(x, drive=1.0):
    return np.tanh(x * drive) / np.tanh(drive)


# ----------------------------------------------------------------- reverb
def reverb_ir(dur=2.6, predelay=0.018, tone=6500, seed=3, early=True):
    n = n_of(dur)
    t = t_of(n)
    rng = np.random.default_rng(seed)
    out = np.zeros((n + n_of(predelay), 2))
    for ch in range(2):
        nz = rng.standard_normal(n)
        env = np.exp(-t * 6.9 / dur)  # -60 dB at dur
        tail = nz * env
        tail = filt(tail, 'lp', tone, 0.5)
        tail = filt(tail, 'hp', 180, 0.6)
        out[n_of(predelay):, ch] = tail
        if early:
            for k in range(8):
                d = n_of(predelay * 0.3 + rng.uniform(0.003, 0.045))
                out[d, ch] += rng.uniform(0.25, 0.6) * (1 if rng.random() > 0.5 else -1)
    out /= np.sqrt(np.sum(out ** 2) / 2)
    return out


_IR_CACHE = {}


def reverb(x, wet=0.25, dur=2.6, tone=6500, predelay=0.018):
    key = (round(dur, 2), tone, round(predelay, 3))
    if key not in _IR_CACHE:
        _IR_CACHE[key] = reverb_ir(dur, predelay, tone)
    ir = _IR_CACHE[key]
    if x.ndim == 1:
        x = pan(x, 0.0)
    y = np.stack([fftconvolve(x[:, 0], ir[:, 0])[: len(x)], fftconvolve(x[:, 1], ir[:, 1])[: len(x)]], axis=1)
    return x * (1 - wet) + y * wet


# ----------------------------------------------------------------- drums
def kick(dur=0.5, f_hi=120, f_lo=44, punch=0.035, tau=0.32, click=0.35):
    n = n_of(dur)
    t = t_of(n)
    f = f_lo + (f_hi - f_lo) * np.exp(-t / punch)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * exp_env(n, tau, attack=0.001)
    c = filt(noise(n, 11), 'hp', 2500) * exp_env(n, 0.004, attack=0.0003) * click
    return soft_clip(body * 1.1 + c, 1.3)


def clap(dur=0.35, tone=1600, seed=5):
    n = n_of(dur)
    t = t_of(n)
    nz = filt(noise(n, seed), 'bp', tone, 0.9)
    env = np.zeros(n)
    for k, off in enumerate([0.0, 0.011, 0.022]):
        s = n_of(off)
        env[s:] += np.exp(-(t[: n - s]) / 0.006) * (0.8 if k < 2 else 1.0)
    env += np.exp(-t / 0.11) * 0.55 * (t > 0.022)
    return nz * env


def hat(dur=0.08, tau=0.028, seed=7, tone=8500):
    n = n_of(dur)
    x = filt(noise(n, seed), 'hp', tone, 0.7)
    x = filt(x, 'peak', 11000, 1.0, 3)
    return x * exp_env(n, tau, attack=0.0005)


def shaker(dur=0.12, seed=9):
    n = n_of(dur)
    t = t_of(n)
    x = filt(noise(n, seed), 'bp', 6000, 0.8)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 2
    return x * env


def rim(dur=0.08, f=1750):
    n = n_of(dur)
    t = t_of(n)
    x = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.012) + 0.4 * filt(noise(n, 21), 'bp', 3500, 2) * np.exp(-t / 0.006)
    return x


def tom(f=110, dur=0.45):
    n = n_of(dur)
    t = t_of(n)
    fr = f * (1 + 0.6 * np.exp(-t / 0.05))
    return np.sin(2 * np.pi * np.cumsum(fr) / SR) * exp_env(n, 0.22) + 0.2 * filt(noise(n, 4), 'bp', 900, 1) * exp_env(n, 0.03)


def crash(dur=2.5, seed=13):
    n = n_of(dur)
    x = filt(noise(n, seed), 'hp', 4500, 0.6)
    x = filt(x, 'peak', 7000, 0.8, 4)
    return x * exp_env(n, 0.9, attack=0.002)
