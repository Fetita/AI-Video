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
CUT = os.environ.get('CUT', '')  # alternate edit, e.g. CUT=linkedin → vo_script.linkedin.json, *-linkedin outputs
SUF = f'-{CUT}' if CUT else ''
TL = json.load(open(os.path.join(HERE, 'build', f'timeline{SUF}.json')))
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
if 'hook' in SC:
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
if 'intro' in SC:
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
if 'search' in SC:
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
if 'story' in SC:
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
if 'vision' in SC:
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
if 'agri' in SC:
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
    at(s + D - 0.55, s_whoosh(0.5, 1500, 5000, 35), -31)  # hand-off line into the search brief card


# ================================================================== DOCS
if 'docs' in SC:
    s = SC['docs']['start']
    cRead, cMapD, cFlag, cRecD, cKnow = cue('d1', 1), cue('d1', 2), cue('d1', 3), cue('d1', 4), cue('d2', 0)
    D = SC['docs']['end'] - s
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


# ================================================================== INHOUSE
if 'inhouse' in SC:
    s = SC['inhouse']['start']
    cO1, cShow, cLineO = cue('o1'), cue('o2'), cue('o4')
    feat = [cue('o3', 0), cue('o3', 1), cue('o3', 2), cLineO]
    D = SC['inhouse']['end'] - s
    at(cO1 - 0.3, s_whoosh(0.7, 400, 2000, 33), -29)
    at(cO1 + 0.3, s_rise(0.7, 500, 1000), -34)
    at(cShow - 0.75, s_whoosh(0.55, 2200, 700, 34), -29)
    at(cShow - 0.45, s_suck(0.4, 35), -30)
    at(cShow - 0.1, s_rec(), -31)
    at(cShow, s_belt(cLineO - cShow + 7.5), -38)
    for i, tt in enumerate(feat):
        at(tt - 0.1, s_lock() if i < 3 else s_pop(1000, 1500), -27, 0.5)
    at(cLineO + 3.3, s_pop(900, 1350), -30, 0.5)
    at(s + D - 0.9, s_whoosh(0.6, 1800, 500, 37), -29)


# ================================================================== PROMISE
if 'promise' in SC:
    s = SC['promise']['start']
    cP1, cP1e, cP2, cP3, cP4, cP4e = cue('p1'), L['p1']['end'], cue('p2'), cue('p3'), cue('p4'), L['p4']['end']
    at(cP1 - 0.35, s_rise(0.8, 300, 700), -34)
    at(cP1e - 0.95, s_whoosh(0.75, 900, 3000, 43), -29, 0.2)       # the strike-through
    at(cP2 - 0.75, s_whoosh(0.8, 1600, 500, 44), -31)              # headline rises
    for i, tt in enumerate([cP2 + 0.1, cP3 - 0.3, cP4 - 0.3]):
        at(tt + 0.05, s_pop(660 * 2 ** (i * 3 / 12), 990 * 2 ** (i * 3 / 12), 0.12), -29, -0.5 + i * 0.5)
    at(cP4e + 0.2, s_sparkle(1.4, 45, 6), -36)


# ================================================================== FINALE
if 'finale' in SC:
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


# ================================================================== IMPACT FILM ("Seed to Shelf")
# Sections for CUT=impact / impact-teaser; each only runs when its scene is in the timeline.
import re as _re


def s_stamp():
    n = n_of(0.5)
    t = t_of(n)
    thump = np.sin(2 * np.pi * (60 + 50 * np.exp(-t / 0.015)) * t) * np.exp(-t / 0.09)
    clack = filt(noise(n, 31), 'bp', 1800, 1.5) * np.exp(-t / 0.01)
    paper = filt(noise(n, 32), 'hp', 2500) * adsr(n, 0.005, 0.08, 0.2, 0.1) * 0.4
    return norm(thump + 0.6 * clack + paper)


def s_printer(dur=0.55):
    n = n_of(dur)
    t = t_of(n)
    buzz = np.sign(np.sin(2 * np.pi * 420 * t)) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 38 * t)))
    x = filt(buzz, 'bp', 1400, 2) * 0.6 + filt(noise(n, 33), 'bp', 3000, 1) * 0.3
    return norm(x * adsr(n, 0.01, 0.05, 0.9, 0.06))


def s_tamp():
    n = n_of(0.25)
    t = t_of(n)
    air = filt(noise(n, 34), 'lp', 1800) * np.exp(-t / 0.05)
    knock = np.sin(2 * np.pi * (180 + 120 * np.exp(-t / 0.01)) * t) * np.exp(-t / 0.03)
    return norm(0.7 * air + knock)


def s_rods(dur=6.0):
    n = n_of(dur)
    t = t_of(n)
    x = np.zeros(n)
    for k in np.arange(0, dur, 30 / 165):
        s0 = n_of(k)
        e = min(n, s0 + n_of(0.03))
        x[s0:e] += np.exp(-t_of(e - s0) / 0.006)
    x = filt(x * noise(n, 35), 'bp', 1600, 1.5) + 0.3 * filt(noise(n, 36), 'lp', 400)
    return norm(x * adsr(n, 0.3, 0.2, 1.0, 0.5))


# --- the formula's token times, mirroring video/src/lib/vo.js + equation.js (same anchors, same rules)
def _anchors(lid):
    l = L[lid]
    text, segs = l['text'], l['segs']
    T = len(text)
    dur = [b - a for a, b in segs]
    V = sum(dur) or 1
    B = [m.end() for m in _re.finditer(r'[,;:.!?…]+\s+', text) if 0 < m.end() < T]
    res, acc, frm = [0], 0.0, 0
    for j in range(len(segs) - 1):
        acc += dur[j]
        F = acc / V
        best, bd = -1, 1e9
        for i in range(frm, len(B)):
            if len(B) - 1 - i < len(segs) - 2 - j:
                break
            d = abs(B[i] / T - F)
            if d < bd:
                bd, best = d, i
        if best < 0:
            res.append(int(F * T + 0.5))
        else:
            res.append(B[best])
            frm = best + 1
    res.append(T)
    return res


def _char_time(lid, c):
    l = L[lid]
    A, segs = _anchors(lid), l['segs']
    for j in range(len(segs)):
        if c < A[j + 1] or j == len(segs) - 1:
            a, b = segs[j]
            u = max(0.0, min(1.0, (c - A[j]) / max(1, A[j + 1] - A[j])))
            return a + u * (b - a)
    return l['end']


def eq_times(line, toks):
    l = L[line]
    text = l['text'].lower()
    times, cursor, prev = [], 0, l['start']
    for kind, say in toks:
        tt = None
        if say:
            idx = text.find(say.lower(), cursor)
            if idx >= 0:
                tt = _char_time(line, idx)
                cursor = idx + 1
        if kind == 'close':
            tt = max(tt if tt is not None else prev, prev) + 0.32
        if kind == 'eq':
            tt = prev + 0.34
        if kind == 'result':
            tt = max(prev + 0.3, l['end'] - 0.12)
        if tt is None:
            tt = prev + 0.25
        tt = max(tt, prev + (0.12 if kind == 'term' else 0.08))
        times.append(tt)
        prev = tt
    return times


_T = lambda say: ('term', say)
_O = lambda say: ('op', say)
EQ = {  # mirrors EQUATIONS in video/src/lib/impact-data.js (the six impact indicators)
    'nursery': ('n4', [_T('seedlings saved'), _O('times'), _T('the cost')]),
    'lettuce': ('l4', [_T('boxes not wasted'), _O('times'), _T('their cost'), _O('plus'), _T('shortfalls avoided'), _O('times the'), _T('penalty')]),
    'onions': ('u4', [_T('sampling hours saved'), _O('times'), _T('their cost'), _O('plus'), _T('tonnes'), _O('times the'), _T('price difference')]),
    'pumpkins': ('k3', [_T('hours saved'), _O('times'), _T('cost per hour'), _O('plus'), _T('kilos graded right'), _O('times the'), _T('price difference')]),
    'labels': ('b4', [_T('rejections avoided'), _O('times'), ('open', 'times'), _T('the fine'), _O('plus the product'), _T('product'), _O('plus the freight'), _T('freight'), ('close', 'freight')]),
    'dashboard': ('g4', [_T('reporting hours saved'), _O('times'), _T('cost per hour')]),
}
PENT = [1046.5, 1174.7, 1318.5, 1568.0, 1760.0, 2093.0]


def eq_sfx(sid):
    line, toks = EQ[sid]
    if line not in L:
        return
    times = eq_times(line, toks)
    at(times[0] - 0.6, s_whoosh(0.6, 2500, 700, 61), -34)
    n = 0
    for (kind, _), tt in zip(toks, times):
        if kind == 'term':
            at(tt, s_bell(PENT[min(n, 5)], 1.0, 0.4), -28, -0.3 + 0.12 * n)
            n += 1
        else:
            at(tt, s_tick(1900, 0.01), -34)
    # the indicator is complete: an underline sweeps under it
    at(times[-1] + 0.35, s_chime(), -27)
    at(times[-1] + 0.35, s_thump(), -31)
    ds = L[line]['end'] + 0.75
    at(ds, s_suck(0.6, 62), -30)
    at(ds + 0.64, s_lock(), -30, 0.6)


def exit_line(sid):
    at(SC[sid]['end'] - 0.65, s_rise(0.55, 500, 1100), -38)


def card_sfx(s0, sol_at):
    at(s0 + 0.1, s_whoosh(0.7, 500, 2200, 63), -30)
    at(s0 + 0.5, s_paper(0.4, 64), -32)
    at(s0 + 0.75, s_pop(700, 1000), -34)
    at(sol_at, s_pop(800, 1150), -34)


def chips_sfx(t0, n):
    for i in range(n):
        at(t0 + i * 0.22, s_pop(800 + i * 80, 1150 + i * 80), -30, -0.4 + i * 0.4)


if 'impact-open' in SC:
    s0 = SC['impact-open']['start']
    D = SC['impact-open']['end'] - s0
    c1, c2, c3 = cue('x1'), cue('x2'), cue('x3')
    x3e = L['x3']['end']
    cNot, cF = cue('x4', 0), cue('x4', 1)
    gap = cNot - x3e
    fl = [x3e + 0.05 + i * min(0.32, (gap - 0.9) / 3) for i in range(3)]
    gridAt = fl[2] + 0.3
    colAt = gridAt + 0.32
    at(s0 + 0.25, s_rise(0.7, 400, 900), -34)
    at(c1 - 0.12, s_whoosh(0.4, 900, 2600, 65), -32)
    at(c1 + 0.5, s_alert(), -30)
    at(c2 - 0.12, s_data(0.8, 66, 24), -34)
    at(c2 + 0.6, s_alert(), -30, 0.3)
    at(c2 + 0.8, s_marker(), -32)
    at(c3 - 0.1, s_whoosh(0.6, 400, 1600, 67), -30)
    at(c3 + 0.8, s_stamp(), -22)
    for i, tt in enumerate(fl):
        at(tt, s_tick(1800 + 300 * i, 0.012), -28)
        at(tt, s_pixel(0.2), -36)
    for i in range(6):
        at(gridAt - 0.2 + i * 0.03, s_pop(700 + i * 90, 1000 + i * 90, 0.06), -34, -0.6 + i * 0.24)
    at(colAt, s_suck(0.35, 68), -26)
    at(colAt + 0.3, s_thump(), -22)
    at(cNot, s_whoosh(0.7, 900, 2600, 69), -32)
    at(cF - 0.05, s_glitch(0.5, 70), -30)
    for i in range(5):
        at(cF + 0.7 + i * 0.12, s_pop(660 * 2 ** (i * 2 / 12), 990 * 2 ** (i * 2 / 12), 0.08), -32)
    if 'x5' in L:
        c5, cM = cue('x5', 0), cue('x5', 1)
        at(c5 - 0.25, s_chime(), -30)
        at(cM + 2.4, s_marker(), -32)
    c6, cS = cue('x6', 0), cue('x6', 1)
    at(c6 - 0.25, s_rise(0.7, 350, 900), -34)
    for i in range(6):
        at(c6 + 0.2 + i * 0.14, s_pop(700 + i * 60, 1000 + i * 60), -30, -0.7 + i * 0.28)
    at(cS - 0.1, s_sparkle(1.0, 71, 6), -36)
    at(cS + 1.0, s_lock(), -32)
    at(s0 + D - 1.55, s_whoosh(0.9, 2000, 500, 72), -30)
    exit_line('impact-open')

if 'nursery' in SC:
    s0 = SC['nursery']['start']
    cN2, cCount, cFlag = cue('n2', 0), cue('n2', 1), cue('n2', 2)
    live = cN2 + 1.25
    dock = L['n4']['end'] + 0.75
    card_sfx(s0, cN2 - 0.15)
    at(live - 0.05, s_suck(0.4, 73), -30)
    at(live, s_rec(), -32)
    at(live, s_servo(dock - live), -40)
    at(live, s_belt(dock - live), -42)
    at(cCount - 0.3, s_scan(1.2, 74), -32)
    for i in range(3):
        at(cCount + i * 0.35, s_lock(), -32, -0.3 + i * 0.3)
    at(cFlag, s_alert(), -26)
    chips_sfx(cue('n3') - 0.1 if 'n3' in L else L['n4']['start'] - 3.3, 3)
    eq_sfx('nursery')
    exit_line('nursery')

if 'lettuce' in SC:
    s0 = SC['lettuce']['start']
    cCam, cFc, cMatch = cue('l1', 1), cue('l2', 0), cue('l2', 1)
    cPush = cCam + 0.55
    at(s0, s_engine(cPush + 1.0 - s0), -34)
    at(cCam, s_lock(), -28)
    at(cPush, s_whoosh(0.9, 400, 2400, 75), -28)
    for i in range(3):
        at(cPush + 0.75 + i * 0.3, s_lock(), -32, -0.4 + i * 0.4)
    at(cPush + 0.9, s_data(1.2, 76, 24), -36)
    at(cFc + 0.45, s_whoosh(0.6, 1800, 600, 77), -32)
    at(cFc + 0.9, s_rise(1.2, 400, 900), -36)
    at(cFc + 0.9, s_data(2.0, 78, 18), -38)
    for i in range(7):
        at(cMatch - 0.1 + i * 0.05, s_marker(0.08), -34, -0.6 + i * 0.2)
    at(cMatch + 0.3, s_alert(), -30)
    for k in range(14):
        at(cMatch + 0.8 + 2.6 * (k / 14) * 0.62 + 0.25, s_tick(1600 + k * 60, 0.01), -34, -0.5 + (k % 5) * 0.25)
    chips_sfx(cue('l3') - 0.1 if 'l3' in L else L['l4']['start'] - 2.7, 2)
    eq_sfx('lettuce')
    exit_line('lettuce')

if 'onions' in SC:
    s0 = SC['onions']['start']
    cSplit, cMiss, cSort = cue('u1', 1), cue('u2', 0), cue('u2', 2)
    live = L['u2']['segs'][0][1] - 0.05
    dock = L['u4']['end'] + 0.75
    card_sfx(s0, cSplit - 0.1)
    at(cMiss + 0.1, s_alert(), -28)
    for i in range(6):
        at(cMiss + 0.1 + i * 1.1 / 8, s_marker(0.09), -32, -0.4 + i * 0.16)
    at(live, s_suck(0.4, 79), -30)
    at(live + 0.05, s_rec(), -32)
    at(live, s_rods(dock - live), -36)
    at(live, s_belt(dock - live), -44)
    tt = live + 0.6
    while tt < dock - 0.6:
        at(tt, s_count(), -36, 0.3)
        tt += 0.48
    for i in range(4):
        at(cSort - 0.2 + i * 0.08, s_pop(700 + i * 120, 1000 + i * 120), -30)
    for i in range(6):
        at(cSort + 0.6 + i * 0.11, s_pixel(0.2), -34)
    chips_sfx(cSort + 0.5, 1)
    eq_sfx('onions')
    exit_line('onions')

if 'pumpkins' in SC:
    s0 = SC['pumpkins']['start']
    D = SC['pumpkins']['end'] - s0
    cCount = cue('k1', 1)
    cGrade = cCount + 1.2
    dock = L['k3']['end'] + 0.75
    at(s0 + 0.05, s_whoosh(0.7, 600, 2000, 81), -30)
    at(s0 + 0.4, s_click(), -30)
    at(s0, s_belt(dock - s0 + 0.5), -38)
    for k in range(40):
        tc = s0 - 0.08 + 0.6 * k
        if s0 + 0.8 < tc < dock - 0.3:
            at(tc, s_count(), -30, 0.3)
        tg = s0 + 1.28 + 0.6 * k
        if cGrade < tg < dock - 0.3:
            at(tg, s_pop(1000, 1400), -36, 0.5)
    at(cGrade - 0.3, s_scan(1.0, 82), -32)
    at(cGrade + 0.6, s_click(), -32)
    at(cGrade + 0.6, s_servo(0.8), -36)
    chips_sfx(cue('k2') - 0.1 if 'k2' in L else L['k3']['start'] - 2.5, 3)
    eq_sfx('pumpkins')
    exit_line('pumpkins')

if 'labels' in SC:
    s0 = SC['labels']['start']
    cWrong, cFine = cue('b1', 1), cue('b1', 2)
    cAI, cCheck, cHold = cue('b2', 0), cue('b2', 1), cue('b2', 3)
    ai = cAI - 0.4
    dock = L['b4']['end'] + 0.75
    at(s0, s_belt(ai - s0 + 0.3), -42)
    at(cWrong + 1.45, s_stamp(), -22)
    for i in range(3):
        at(cFine + i * 0.18, s_pop(700 + i * 80, 900 + i * 80), -30)
    at(ai, s_whoosh(0.8, 500, 2600, 83), -28)
    at(ai, s_belt(dock - ai), -38)
    hold_k = round((cHold + 0.2 - 1180 / 230 - (ai - 3.2)) / 1.25)
    for k in range(16):
        t0k = ai - 3.2 + 1.25 * k
        tcam, tchk, tlab = t0k + 700 / 230, t0k + 870 / 230, t0k + 1180 / 230
        if cAI - 0.1 < tcam < dock - 0.5:
            at(tcam, s_lock(), -32, -0.2)
        if cCheck - 0.2 < tchk < dock - 0.5:
            at(tchk, s_marker(0.09), -34, 0.1)
        if k == hold_k:
            at(tlab, s_alert(), -26, 0.3)
            at(tlab + 0.1, s_servo(0.8), -34)
        elif ai < tlab < dock - 0.5:
            at(tlab - 0.35, s_printer(), -32, 0.4)
            at(tlab, s_tamp(), -28, 0.4)
    chips_sfx(cue('b3') - 0.1 if 'b3' in L else L['b4']['start'] - 2.3, 3)
    eq_sfx('labels')
    exit_line('labels')

if 'dashboard' in SC:
    s0 = SC['dashboard']['start']
    cLand, cDash, cRep, cAlert = cue('g1', 1), cue('g2', 0), cue('g2', 1), cue('g2', 2)
    cAsk, cAns = cue('g3', 0), cue('g3', 1)
    for i in range(5):
        at(s0 + 0.15 + i * 0.1, s_pop(800 + i * 70, 1100 + i * 70), -32, -0.6 + i * 0.3)
    at(s0 + 0.4, s_data(2.5, 84, 20), -36)
    at(cLand - 0.2, s_suck(0.5, 85), -30)
    at(cLand + 0.5, s_thump(), -28)
    at(cDash + 0.2, s_whoosh(1.0, 400, 2000, 86), -28)
    at(cDash + 0.4, s_paper(0.4, 87), -30)
    for i in range(5):
        at(cDash + 0.7 + i * 0.1, s_pop(900 + i * 60, 1250 + i * 60, 0.07), -34)
    at(cDash + 0.9, s_data(1.5, 88, 16), -38)
    for i in range(3):
        at(cRep - 0.1 + i * 0.16, s_paper(0.3, 89 + i), -28, 0.4)
    at(cRep + 0.5, s_pop(1000, 1400), -30, 0.5)
    at(cAlert, s_alert(), -24, 0.4)
    at(cAsk - 0.3, s_whoosh(0.5, 2200, 800, 92), -32)
    at(cAsk, s_typing(1.2, 93, 12), -30)
    at(cAns - 0.1, s_chime(), -33)
    at(cAns, s_data(1.0, 94, 20), -38)
    for i in range(3):
        at(cAns + 0.9 + i * 0.15, s_tick(1700 + i * 200, 0.012), -34)
    eq_sfx('dashboard')
    exit_line('dashboard')

if 'impact-close' in SC:
    s0 = SC['impact-close']['start']
    cSix, cForm, cOne = cue('z1', 0), cue('z1', 1), cue('z1', 2)
    cName, cCta = cue('z3', 0), cue('z4', 0)
    at(s0 + 0.05, s_rise(0.6, 400, 1000), -34)
    for i in range(6):
        at(cSix - 0.25 + i * 0.07, s_pop(650 + i * 50, 900 + i * 50, 0.07), -31, -0.7 + i * 0.28)
    for i in range(6):
        ra = cForm + 0.45 + i * 0.14
        at(ra, s_pop(660 * 2 ** (i * 2 / 12), 990 * 2 ** (i * 2 / 12), 0.1), -29, -0.5 + i * 0.2)
    at(cOne, s_sparkle(1.2, 95, 8), -34)
    at(cName - 1.25, s_suck(0.95, 96), -22)
    for i in range(3):
        at(cName - 0.45 + i * 0.13, s_tick(1760 + i * 220, 0.02), -29)
    at(cName - 0.25, s_rise(0.7, 500, 1000), -33)
    tagAt = (cName + 1.6 + cCta) / 2 - 0.4
    at(tagAt, s_sparkle(1.6, 97, 8), -34)
    at(cCta - 0.1, s_pop(900, 1400, 0.1), -25)


OUT = reverb(OUT, wet=0.12, dur=1.4, tone=7000)
sf.write(os.path.join(HERE, 'build', f'sfx{SUF}.wav'), OUT.astype(np.float32), SR)
print('sfx peak', round(20 * np.log10(np.max(np.abs(OUT)) + 1e-12), 1), 'dBFS')
