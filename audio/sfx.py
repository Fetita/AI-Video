"""Sound design: synthesized UI / foley sounds cued to the visual events.

Cue times are derived from the same timeline (VO clause timings) the visuals use,
so every lock-on, clack, scan and count lands on its frame. Writes build/sfx.wav.
"""
import json
import os

import numpy as np
import soundfile as sf

from synth import (SR, n_of, t_of, exp_env, adsr, noise, filt, sweep, pan, place, fm_bell, pluck, saw, square, sine,
                   reverb, soft_clip, undb)

HERE = os.path.dirname(os.path.abspath(__file__))
TL = json.load(open(os.path.join(HERE, 'build', 'timeline.json')))
SC = {s['id']: s for s in TL['scenes']}
L = TL['lines']
DUR = TL['duration'] + 2.5
N = n_of(DUR)
OUT = np.zeros((N, 2))
RNG = np.random.default_rng(42)


def cue(line, seg=0, which=0):
    return L[line]['segs'][seg][which]


def norm(x):
    return x / (np.max(np.abs(x)) + 1e-9)


# ------------------------------------------------------------------ sound library (mono unless noted)
def s_key(f=3200):
    n = n_of(0.05)
    t = t_of(n)
    return norm(filt(noise(n, RNG.integers(1e6)), 'bp', f, 2.0) * np.exp(-t / 0.004) + 0.3 * np.sin(2 * np.pi * 2400 * t) * np.exp(-t / 0.008))


def s_tick(f=2600, tau=0.015):
    n = n_of(0.08)
    t = t_of(n)
    return norm(np.sin(2 * np.pi * f * t) * np.exp(-t / tau) + 0.15 * filt(noise(n, 3), 'hp', 5000) * np.exp(-t / 0.003))


def s_pop(f0=820, f1=1250, dur=0.09):
    n = n_of(dur + 0.08)
    t = t_of(n)
    f = f0 + (f1 - f0) * np.clip(t / dur, 0, 1)
    return norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.06) * adsr(n, 0.002, 0.05, 0.6, 0.05))


def s_lock():
    a = s_tick(1500, 0.02)
    b = s_tick(2250, 0.03)
    x = np.zeros(n_of(0.16))
    x[: len(a)] += a
    x[n_of(0.055): n_of(0.055) + len(b)] += b * 0.9
    return norm(x)


def s_whoosh(dur=0.45, f0=500, f1=3500, seed=1):
    n = n_of(dur)
    t = t_of(n)
    x = sweep(noise(n, seed), 'bp', f0, f1, q=0.8)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 2
    y = x * env
    p = np.linspace(-0.6, 0.6, n)
    st = np.stack([y * np.cos((p + 1) * np.pi / 4), y * np.sin((p + 1) * np.pi / 4)], axis=1)
    return st / (np.max(np.abs(st)) + 1e-9)


def s_suck(dur=0.5, seed=2):
    n = n_of(dur)
    t = t_of(n)
    x = sweep(noise(n, seed), 'bp', 4500, 600, q=1.0)
    env = (t / dur) ** 2.5
    env[-n_of(0.01):] *= np.linspace(1, 0, n_of(0.01))
    return norm(x * env)


def s_clack(f=1.0, seed=3):
    n = n_of(0.25)
    t = t_of(n)
    modes = [(620, 0.05, 1.0), (1250, 0.035, 0.6), (2080, 0.02, 0.35), (3300, 0.012, 0.2)]
    x = sum(a * np.sin(2 * np.pi * fr * f * t) * np.exp(-t / d) for fr, d, a in modes)
    x += 0.8 * np.sin(2 * np.pi * 140 * t) * np.exp(-t / 0.06)
    x += 0.3 * filt(noise(n, seed), 'bp', 2500, 1.2) * np.exp(-t / 0.006)
    return norm(x)


def s_scan(dur=1.0, seed=4):
    n = n_of(dur)
    t = t_of(n)
    x = sweep(noise(n, seed), 'bp', 900, 3600, q=6)
    x *= 0.75 + 0.25 * np.sin(2 * np.pi * 18 * t)
    env = adsr(n, 0.08, 0.1, 0.9, 0.2)
    return norm(x * env)


def s_paper(dur=0.35, seed=5):
    n = n_of(dur)
    t = t_of(n)
    x = filt(filt(noise(n, seed), 'hp', 1500), 'bp', 4200, 0.7)
    env = adsr(n, 0.03, 0.12, 0.35, 0.18)
    return norm(x * env)


def s_alert():
    n = n_of(0.3)
    t = t_of(n)
    tri = lambda f: 2 / np.pi * np.arcsin(np.sin(2 * np.pi * f * t))
    x = np.where(t < 0.11, tri(880), tri(622)) * exp_env(n, 0.12)
    x *= (t < 0.1) | (t > 0.12)
    return norm(filt(x, 'lp', 5000))


def s_glitch(dur=0.55, seed=6):
    n = n_of(dur)
    r = np.random.default_rng(seed)
    x = np.zeros(n)
    pos = 0
    while pos < n:
        seg = int(r.integers(n_of(0.012), n_of(0.05)))
        kind = r.random()
        tt = t_of(min(seg, n - pos))
        if kind < 0.4:
            y = np.sign(np.sin(2 * np.pi * r.uniform(300, 2500) * tt))
        elif kind < 0.7:
            y = np.repeat(r.uniform(-1, 1, len(tt) // 40 + 1), 40)[: len(tt)]
        else:
            y = np.zeros(len(tt))
        x[pos: pos + len(tt)] = y * r.uniform(0.3, 1.0)
        pos += seg
    return norm(filt(x, 'lp', 7000) * adsr(n, 0.01, 0.1, 0.8, 0.1))


def s_bell(f=2093, dur=1.2, tau=0.5):
    return norm(fm_bell(f, dur, ratio=2.0, index=1.4, tau=tau, itau=0.15))


def s_chime():
    a = s_bell(1568, 1.4, 0.6)
    b = s_bell(2093, 1.4, 0.6)
    x = np.zeros(n_of(1.6))
    x[: len(a)] += a
    x[n_of(0.09): n_of(0.09) + len(b)] += b
    return norm(x)


def s_sparkle(dur=2.0, seed=7, count=14):
    r = np.random.default_rng(seed)
    x = np.zeros((n_of(dur + 1.0), 2))
    scale = [0, 3, 5, 7, 10]
    for i in range(count):
        m = 84 + scale[int(r.integers(0, 5))] + 12 * int(r.integers(0, 2))
        f = 440 * 2 ** ((m - 69) / 12)
        b = fm_bell(f, 0.8, ratio=2.0, index=0.8, tau=0.3, itau=0.1)
        place(x, pan(b, r.uniform(-0.7, 0.7)), r.uniform(0, dur), r.uniform(0.3, 1.0))
    return x / (np.max(np.abs(x)) + 1e-9)


def s_data(dur=1.0, seed=8, rate=26):
    r = np.random.default_rng(seed)
    x = np.zeros((n_of(dur + 0.1), 2))
    for i in range(int(dur * rate)):
        place(x, pan(s_tick(r.uniform(2400, 6200), 0.006), r.uniform(-0.6, 0.6)), r.uniform(0, dur), r.uniform(0.2, 0.8))
    return x / (np.max(np.abs(x)) + 1e-9)


def s_rec():
    n = n_of(0.14)
    t = t_of(n)
    return norm(np.sin(2 * np.pi * 1000 * t) * adsr(n, 0.004, 0.02, 0.8, 0.03))


def s_error():
    n = n_of(0.2)
    return norm(filt(square(140, n, max_h=15), 'lp', 1800) * adsr(n, 0.005, 0.05, 0.7, 0.06))


def s_servo(dur=2.6):
    n = n_of(dur)
    t = t_of(n)
    speed = np.sin(np.pi * np.clip(t / dur, 0, 1))
    f = 160 + 140 * speed
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(f * 2.01) / SR)
    x = filt(x, 'lp', 1500) + 0.25 * filt(noise(n, 9), 'bp', 1800, 3) * speed
    return norm(x * (0.25 + 0.75 * speed) * adsr(n, 0.08, 0.1, 1, 0.12))


def s_click():
    n = n_of(0.05)
    t = t_of(n)
    return norm(filt(noise(n, 10), 'hp', 2000) * np.exp(-t / 0.003) + 0.6 * np.sin(2 * np.pi * 900 * t) * np.exp(-t / 0.01))


def s_engine(dur=6.5):
    n = n_of(dur)
    t = t_of(n)
    x = np.sin(2 * np.pi * 46 * t) * (0.7 + 0.3 * np.sin(2 * np.pi * 11 * t)) + 0.5 * np.sin(2 * np.pi * 92 * t + 1)
    x += 0.6 * filt(noise(n, 11), 'lp', 300)
    return norm(filt(x, 'hp', 30) * adsr(n, 0.8, 0.2, 1.0, 1.0))


def s_belt(dur=7.0):
    n = n_of(dur)
    t = t_of(n)
    x = 0.5 * np.sin(2 * np.pi * 98 * t) + 0.4 * filt(noise(n, 12), 'bp', 700, 1.0)
    ticks = np.zeros(n)
    for k in np.arange(0, dur, 0.12):
        s = n_of(k)
        e = min(n, s + n_of(0.02))
        ticks[s:e] += np.exp(-t_of(e - s) / 0.004)
    x += 0.5 * filt(ticks * noise(n, 13), 'bp', 2400, 2)
    return norm(x * adsr(n, 0.4, 0.2, 1.0, 0.6))


def s_count():
    return norm(pluck(1318.5, 0.35, bright=1.3, decay=0.12, K=10))


def s_rise(dur=0.8, f0=300, f1=900):
    n = n_of(dur)
    t = t_of(n)
    f = f0 * (f1 / f0) ** (t / dur)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.6 + 0.4 * sweep(noise(n, 14), 'bp', f0 * 2, f1 * 3, q=2)
    return norm(x * np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.5)


def s_marker(dur=0.1):
    n = n_of(dur)
    return norm(sweep(noise(n, 15), 'bp', 1800, 3600, q=2) * adsr(n, 0.01, 0.03, 0.6, 0.04))


def s_pixel(dur=0.3):
    n = n_of(dur)
    x = np.repeat(np.random.default_rng(16).uniform(-1, 1, n // 60 + 1), 60)[:n]
    return norm(filt(x, 'lp', 6000) * adsr(n, 0.005, 0.05, 0.7, 0.1))


def s_thump():
    n = n_of(0.2)
    t = t_of(n)
    return norm(np.sin(2 * np.pi * (70 + 40 * np.exp(-t / 0.02)) * t) * np.exp(-t / 0.07))


def s_typing(dur=1.0, seed=17, rate=11):
    r = np.random.default_rng(seed)
    x = np.zeros((n_of(dur + 0.1), 2))
    tt = 0.0
    while tt < dur:
        place(x, pan(s_key(r.uniform(2600, 4200)), r.uniform(-0.2, 0.2)), tt, r.uniform(0.5, 1.0))
        tt += r.uniform(0.6, 1.4) / rate
    return x / (np.max(np.abs(x)) + 1e-9)


# ------------------------------------------------------------------ cue helpers
def at(t, snd, gain_db=-24, p=0.0):
    if t < 0:
        return
    x = snd if snd.ndim == 2 else pan(snd, p)
    place(OUT, x, t, undb(gain_db))


# ================================================================== HOOK
s = SC['hook']['start']
c2, c3, c4 = cue('h2'), cue('h3'), cue('h4')
cNot, cProd, cName, cWf, cOut = cue('h5', 0), cue('h5', 1), cue('h6', 0), cue('h6', 1), cue('h6', 2)
D = SC['hook']['end'] - s
at(0.25, s_rise(0.9, 400, 1200), -30)
at(1.1, s_typing(0.9, 1, 11), -31)
for i in range(4):
    at(1.95 + i * 0.09, s_pop(900 + i * 90, 1300 + i * 90), -27, -0.3 + i * 0.2)
at(c2 - 0.14, s_whoosh(0.32, 600, 3000, 2), -27)
at(c2 - 0.12 + 0.42, s_clack(1.0), -19)
at(c2 + 0.1, s_lock(), -25)
at(c3 - 0.14, s_whoosh(0.32, 700, 3500, 3), -27)
at(c3 - 0.05, s_click(), -28)
for i in range(7):
    at(c3 + 0.15 + i * 0.045, s_tick(2800 + i * 120, 0.01), -33, -0.5 + i * 0.16)
at(c4 - 0.12, s_paper(0.4, 4), -22)
at(c4 + 0.15, s_scan(0.9, 5), -29)
at(c4 + 0.45, s_pop(1000, 1500), -27, 0.3)
at(c4 + 0.75, s_alert(), -26, 0.3)
conv0 = c4 + 1.25
at(conv0 - 0.3, s_whoosh(0.4, 3000, 800, 6), -27)
at(conv0 + 0.3, s_suck(0.5), -24)
at(cNot + 0.35, s_marker(0.18), -27)
at(cProd - 0.05, s_glitch(0.55), -30)
at(cProd + 0.25, s_bell(2093, 1.2, 0.5), -28)
for i in range(3):
    at(cName - 0.55 + i * 0.19, s_tick(1760 + i * 220, 0.02), -29)
at(cName - 0.25, s_rise(0.8, 500, 1000), -33)
for i, tt in enumerate([cName + 3.2, cWf, cOut]):
    at(tt - 0.1, s_pop(700 + i * 110, 1000 + i * 110), -29)
at(s + D - 0.55, s_whoosh(0.5, 1500, 5000, 7), -31)

# ================================================================== INTRO
s = SC['intro']['start']
seg = lambda lid, k: L[lid]['segs'][min(k, len(L[lid]['segs']) - 1)][0]
cI1, cI1b, cI2end, cI3 = seg('i1', 0), seg('i1', 1), L['i2']['end'], seg('i3', 0)
D = SC['intro']['end'] - s
at(cI1 - 0.2, s_whoosh(0.6, 400, 1800, 30), -31)
for i in range(4):
    at(cI1b + 0.2 + i * 0.32, s_pop(820 + i * 70, 1200 + i * 70), -31, -0.45 + i * 0.25)
at(cI2end - 0.75, s_chime(), -30, 0.4)
at(cI3 - 0.25, s_whoosh(0.5, 2200, 700, 31), -29)
for i in range(5):
    at(cI3 + 0.1 + i * 0.2, s_tick(1500 + i * 160, 0.014), -31, -0.4 + i * 0.2)
at(s + D - 1.25, s_whoosh(0.5, 600, 2400, 32), -32)

# ================================================================== SEARCH
s = SC['search']['start']
cP, cS, cE, cR, cF, cF2 = cue('s2', 0), cue('s2', 1), cue('s2', 2), cue('s2', 3), cue('s3', 0), cue('s3', 1)
D = SC['search']['end'] - s
at(s + 0.0, s_rise(0.6, 300, 800), -32)
at(s + 0.6, s_typing(L['s1']['end'] - s - 0.8, 21, 9), -35)
for i in range(7):
    at(cP + 0.05 + i * 0.16, s_marker(), -31, -0.4 + i * 0.1)
rows = [1, 2, 2, 1, 1, 2]
for r, cnt in enumerate(rows):
    for k in range(cnt):
        at(cP + 0.5 + r * 0.12 + k * 0.08 + 0.6, s_pop(1100, 1600), -32, 0.4)
at(cS - 0.35, s_whoosh(0.45, 2000, 600, 8), -27)
at(cS + 0.1, s_scan(1.3, 9), -28)
for i in range(14):
    f = RNG.random()
    at(cS + 0.1 + 1.3 * ((f + 0.15) / 1.3) + 0.05, s_tick(2000 + RNG.random() * 1500, 0.02), -32, -0.8 + 1.6 * f)
at(cE - 0.2, s_whoosh(0.5, 600, 2600, 10), -27)
tiers = [1, 1, 2, 1, 0, 0]
for i in range(6):
    ev = cE + 0.55 + i * 0.22
    for k in range(6):
        at(ev + k * 0.05, s_tick(3000, 0.006), -37, -0.7 + i * 0.28)
    snd = s_pop(900, 1400) if tiers[i] == 1 else (s_pop(700, 800) if tiers[i] == 2 else s_thump())
    at(ev + 0.4, snd, -28 if tiers[i] else -24, -0.7 + i * 0.28)
at(cR + 0.0, s_whoosh(0.6, 500, 2200, 11), -27)
at(cR + 0.4, s_chime(), -30)
at(cF - 0.3, s_whoosh(0.4, 900, 3000, 12), -30, 0.5)
at(cF + 0.15, s_pop(700, 1100), -25, 0.5)
at(cF + 0.8, s_typing(1.1, 23, 7), -38, 0.4)
at(cF2 + 0.05, s_chime(), -27, 0.3)
at(cF2 - 0.1, s_whoosh(0.7, 800, 2400, 13), -30, -0.4)
at(cF2 + 0.5, s_bell(1760, 0.8, 0.3), -29, -0.6)
at(s + D - 0.95, s_rise(0.9, 400, 1100), -31)

# ================================================================== STORY
s = SC['story']['start']
cPlace, cRec, cReason, cGen, cSys, cApp = cue('t2', 0), cue('t3', 0), cue('t3', 1), cue('t3', 2), cue('t4', 0), cue('t4', 1)
D = SC['story']['end'] - s
at(s - 0.1, s_sparkle(0.6, 31, 5), -32)
at(s + 0.15 + 0.5, s_clack(0.95, 1), -21)
at(s + 2.0, s_sparkle(2.8, 32, 12), -31)
at(s + 3.4, s_whoosh(1.1, 400, 1600, 14), -30)
for i, off in enumerate([0.35, 0.85, 1.35]):
    at(cPlace + off + 0.5, s_clack([1.08, 0.9, 1.15][i], 20 + i), -20, -0.3 + i * 0.3)
for i in range(4):
    at(cRec + i * 0.28, s_lock(), -26, -0.6 + i * 0.4)
for k in range(4):
    at(cReason + k * 0.2 + 0.2, s_pop(560 + k * 140, 700 + k * 160, 0.12), -29)
at(cGen - 0.1, s_paper(0.5, 24), -22)
at(cGen + 0.15, s_sparkle(1.8, 33, 16), -29)
at(cGen + 0.8, s_typing(cSys - cGen - 1.0, 25, 10), -36)
at(cSys - 0.25, s_whoosh(0.6, 500, 2000, 15), -28)
for i, off in enumerate([0, 0.35, 0.6, 0.15]):
    tt = cSys - 0.2 + off + (cApp - cSys - 0.35 if i == 1 else 0)
    at(tt, s_pop(800 + i * 60, 1150 + i * 60), -31, -0.6 + i * 0.4)

# ================================================================== VISION
s = SC['vision']['start']
cStack, cVS, cDet, cTrk, cDs, cTr, cRb = cue('v1', 1), cue('v2', 0), cue('v2', 1), cue('v2', 2), cue('v2', 3), cue('v3', 0), cue('v3', 1)
D = SC['vision']['end'] - s
at(s + 0.05, s_pop(600, 900), -28)
for i in range(6):
    at(cStack + 0.12 + i * 0.1, s_tick(1400 + i * 180, 0.015), -29)
at(cStack + 0.35, s_error(), -30)
at(cVS - 0.38, s_suck(0.45, 26), -26)
at(cVS - 0.3, s_rec(), -30)
at(cVS + 0.35, s_lock(), -24, -0.3)
at(cVS + 0.55, s_lock(), -24, 0.3)
at(cVS + 0.4, s_data(0.9, 27), -33)
at(cDet - 0.08, s_whoosh(0.3, 3000, 900, 16), -26)
for i in range(3):
    at(cDet + 0.15 + i * 0.17, s_lock(), -27, -0.5 + i * 0.5)
at(cDet + 0.8, s_pixel(), -29)
at(cTrk - 0.1, s_whoosh(0.4, 500, 2500, 17), -27)
at(cTrk + 0.1, s_data(1.4, 28, 14), -35)
at(cDs - 0.12, s_whoosh(0.4, 2500, 700, 18), -27)
at(cDs, s_data(1.5, 29, 40), -33)
at(cTr - 0.05, s_rise(cRb - cTr - 0.2, 300, 1200), -34)
at(cTr + 0.667 * (cRb - cTr - 0.2), s_bell(1760, 0.8, 0.3), -27, 0.4)
at(cRb - 0.15, s_whoosh(0.5, 600, 2400, 19), -27)
at(cRb + 1.1, s_servo(2.6), -30)
at(cRb + 1.12, s_click(), -26, -0.3)
at(cRb + 1.1 + 2.55, s_click(), -26, 0.3)

# ================================================================== AGRI
s = SC['agri']['start']
cCam, cData, cTrA, cCount, cMap, cPack, cID = cue('a1', 1), cue('a1', 2), cue('a2', 0), cue('a2', 1), cue('a2', 2), cue('a3', 0), cue('a3', 1)
D = SC['agri']['end'] - s
at(s - 0.2, s_engine(cTrA - s + 1.2), -31)
at(cCam - 0.1, s_bell(1568, 0.7, 0.25), -27)
at(cData, s_data(cTrA - cData, 34, 12), -35)
at(cTrA + 0.1, s_whoosh(0.8, 400, 2200, 20), -25)
at(cTrA + 0.7, s_rec(), -30)
tt = cTrA + 1.0
while tt < cMap + 0.9:
    at(tt, s_tick(2400 + RNG.random() * 2000, 0.008), -39, RNG.uniform(-0.7, 0.7))
    tt += RNG.uniform(0.07, 0.16)
at(cCount - 0.2, s_marker(0.3), -30)
at(cCount + 0.7, s_pop(1500, 1800), -30)
at(cMap + 0.3, s_whoosh(0.6, 2200, 600, 21), -27)
at(cMap + 1.3, s_bell(1760, 0.8, 0.3), -28)
at(cPack - 0.15, s_whoosh(0.5, 600, 2500, 22), -26)
at(cPack - 0.1, s_belt(s + D - cPack + 0.8), -33)
BV, LINE_DX = 250, 1080 + 110
for k in range(40):
    t0 = cPack - 2.6 + k * 0.62 + (np.modf(np.sin(k * 12.9898 + 4 * 78.233) * 43758.5453)[0] % 1 - 0.5) * 0.0
    enter = t0 + 130 / BV
    cross = t0 + LINE_DX / BV
    if enter > cID - 0.2 and enter < s + D:
        at(enter, s_tick(2400, 0.012), -32, -0.8)
    if cross > cID - 0.2 and cross < s + D:
        at(cross, s_count(), -25, 0.25)
at(s + D - 0.9, s_paper(0.4, 35), -24)

# ================================================================== DOCS
s = SC['docs']['start']
cRead, cMapD, cFlag, cRecD, cKnow = cue('d1', 1), cue('d1', 2), cue('d1', 3), cue('d1', 4), cue('d2', 0)
D = SC['docs']['end'] - s
at(s + 0.0, s_paper(0.5, 36), -24)
at(s + 0.8, s_thump(), -30)
for i in range(5):
    at(s + 0.1 + i * 0.18, s_pop(900 + i * 50, 1200 + i * 50), -33)
at(s + 0.3, s_rise(1.6, 400, 800), -38)
at(cRead - 0.6, s_paper(0.45, 37), -24)
at(cRead - 0.1, s_scan(1.7, 38), -27)
for th in [0.28, 0.45, 0.55, 0.85]:
    u = np.arccos(1 - 2 * th) / np.pi  # inverse of inOutSine
    at(cRead - 0.1 + 1.7 * u, s_marker() if th < 0.8 else s_alert(), -30 if th < 0.8 else -27)
kinds = ['ok', 'ok', 'mid', 'bad', 'ok']
for i, kd in enumerate(kinds):
    a = cMapD + 0.35 + i * 0.5
    at(a, s_marker(0.14), -33, 0.4)
    at(a + 0.35, s_pop(1000, 1500) if kd == 'ok' else (s_pop(800, 900) if kd == 'mid' else s_alert()), -28, 0.5)
at(cFlag - 0.05, s_alert(), -25, 0.5)
at(cRecD - 0.1, s_chime(), -27, 0.5)
at(cKnow + 0.0, s_whoosh(0.7, 500, 2200, 23), -27)
for i in range(4):
    at(cKnow + 0.15 + i * 0.12, s_pop(750 + i * 80, 1050 + i * 80), -32, -0.4 + i * 0.3)

# ================================================================== FINALE
s = SC['finale']['start']
cDiff, cOne, cBuild, cNameF, cTag, cCta = cue('f1', 0), cue('f1', 1), cue('f1', 2), cue('f2', 0), cue('f3', 0), cue('f4', 0)
at(s - 0.2, s_whoosh(0.9, 400, 2500, 24), -25)
at(s - 0.1, s_data(0.8, 40, 30), -34)
for i in range(15):
    at(cDiff - 0.1 + i * 0.075, s_tick(1600 + i * 110, 0.012), -33, -0.8 + (i % 5) * 0.4)
for i, tt in enumerate([cOne + 0.75, cBuild, cBuild + 0.55]):
    at(tt - 0.05, s_pop(880 * 2 ** (i * 4 / 12), 1320 * 2 ** (i * 4 / 12), 0.1), -26)
at(cNameF - 1.25, s_suck(0.95, 41), -22)
for i in range(3):
    at(cNameF - 0.45 + i * 0.13, s_tick(1760 + i * 220, 0.02), -29)
at(cNameF - 0.25, s_rise(0.7, 500, 1000), -33)
at(cTag - 0.05, s_sparkle(1.6, 42, 8), -34)
at(cCta - 0.1, s_pop(900, 1400, 0.1), -25)

OUT = reverb(OUT, wet=0.12, dur=1.4, tone=7000)
sf.write(os.path.join(HERE, 'build', 'sfx.wav'), OUT.astype(np.float32), SR)
print('sfx peak', round(20 * np.log10(np.max(np.abs(OUT)) + 1e-12), 1), 'dBFS')
