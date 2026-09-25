"""Original score for the Eagerworks AI Studio film (100 BPM, A minor / C major).

Energy follows the edit: sparse hook → light groove (search) → magical (story)
→ peak (vision/robotics) → mechanical drive (agriculture) → steady (documents)
→ drop, riser and resolve on the logo (finale). Writes build/music.wav (48 kHz stereo).
"""
import json
import os
from functools import lru_cache

import numpy as np
import soundfile as sf

from synth import (SR, n_of, t_of, midi_hz, adsr, exp_env, saw, pluck, fm_bell, noise, filt, sweep, pan, place,
                   reverb, kick, clap, hat, shaker, rim, tom, crash, soft_clip, sine, limiter, undb)

HERE = os.path.dirname(os.path.abspath(__file__))
TL = json.load(open(os.path.join(HERE, 'build', 'timeline.json')))
BEAT = 60.0 / TL['bpm']
DUR = TL['duration'] + 2.5
N = n_of(DUR)
SC = {s['id']: s for s in TL['scenes']}
L = TL['lines']


def cue(line, seg=0, which=0):
    return L[line]['segs'][seg][which]


CH = {
    'Am9': (45, [57, 60, 64, 67, 71]),
    'Fmaj9': (41, [53, 57, 60, 64, 67]),
    'Cmaj9': (48, [55, 59, 62, 64, 67]),
    'G6sus': (43, [55, 57, 62, 64, 69]),
    'Dm9': (50, [53, 57, 60, 64, 65]),
}

# stems
S = {k: np.zeros((N, 2)) for k in ['drums', 'bass', 'pad', 'arp', 'bell', 'fx', 'stab']}
KICKS = []  # kick times for sidechain


# ------------------------------------------------------------------ cached instruments
@lru_cache(maxsize=None)
def pad_voice(chord, dur, bright):
    root, notes = CH[chord]
    n = n_of(dur + 1.6)
    L_ = np.zeros(n)
    R_ = np.zeros(n)
    for i, m in enumerate(notes):
        f = midi_hz(m)
        for d, side in [(-9, 0), (0, None), (8, 1)]:
            ff = f * 2 ** (d / 1200)
            v = saw(ff, n, max_h=int(3500 * bright / ff) + 1, phase=i * 0.7 + d, bright=1.15)
            if side is None:
                L_ += v * 0.7; R_ += v * 0.7
            elif side == 0:
                L_ += v; R_ += v * 0.35
            else:
                R_ += v; L_ += v * 0.35
    env = adsr(n, a=0.9, d=0.6, s=0.85, r=1.4)
    x = np.stack([L_, R_], axis=1) * env[:, None]
    x = filt(x, 'lp', 900 + 2600 * bright, 0.6)
    x = filt(x, 'hp', 140, 0.7)
    return x / (len(notes) * 2.2)


@lru_cache(maxsize=None)
def bass_note(m, dur, grit):
    n = n_of(dur + 0.08)
    f = midi_hz(m)
    x = sine(f, n) * 0.9 + saw(f, n, max_h=10, bright=1.3) * 0.35 * grit
    x = filt(x, 'lp', 420 + 500 * grit, 0.8)
    env = adsr(n, a=0.004, d=0.12, s=0.75, r=0.06)
    return soft_clip(x * env * 1.2, 1.4)


@lru_cache(maxsize=None)
def pluck_note(m, bright, dur=0.5):
    return pluck(midi_hz(m), dur, bright=bright, decay=0.22, K=16)


@lru_cache(maxsize=None)
def bell_note(m, dur=2.2):
    return fm_bell(midi_hz(m), dur, ratio=3.5, index=2.0, tau=1.1, itau=0.25)


@lru_cache(maxsize=None)
def stab(chord, dur=0.35):
    _, notes = CH[chord]
    n = n_of(dur)
    x = sum(saw(midi_hz(m + 12), n, max_h=24) for m in notes[:4])
    x = sweep(x, 'lp', 5200, 700, q=1.2)
    return x * exp_env(n, 0.11) / 4


_K = kick()
_KS = kick(f_hi=100, tau=0.22, click=0.2)
_C = clap()
_H = hat()
_HO = hat(dur=0.3, tau=0.12, seed=8)
_SH = shaker()
_RM = rim()
_CR = crash()


def riser(dur, seed=1):
    n = n_of(dur)
    t = t_of(n)
    x = sweep(noise(n, seed), 'bp', 300, 7000, q=1.4)
    x += 0.25 * sweep(saw(110, n, max_h=40), 'lp', 200, 4000, q=1.0)
    env = (t / dur) ** 2.2
    return pan(x * env, 0.0) * 0.5


def impact(size=1.0, seed=2):
    n = n_of(2.4)
    t = t_of(n)
    f = 38 + 60 * np.exp(-t / 0.08)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * exp_env(n, 0.7)
    nz = filt(noise(n, seed), 'lp', 2500) * exp_env(n, 0.25)
    x = pan(boom * 0.9 + nz * 0.25 * size, 0.0)
    return reverb(x, wet=0.35, dur=3.0) * size


def reverse_swell(dur=1.2, seed=4):
    x = crash(dur + 0.4, seed)[::-1][-n_of(dur):]
    return pan(filt(x, 'hp', 1500), 0.0) * 0.6


# ------------------------------------------------------------------ writers
def w_pad(t0, chord, beats, bright=0.5, gain=1.0):
    place(S['pad'], pad_voice(chord, round(beats * BEAT, 3), round(bright, 2)), t0, gain)


def w_bass(t0, chord, beats, pattern='8', grit=0.4, gain=1.0, octave=0):
    root = CH[chord][0] + octave
    step = {'8': 0.5, '16': 0.25, '4': 1.0, 'hold': beats}[pattern]
    k = 0
    b = 0.0
    while b < beats - 1e-6:
        m = root + (12 if (pattern == '8' and k % 4 == 2) else 0)
        dur = min(step, beats - b) * BEAT * (0.92 if pattern != 'hold' else 1.0)
        acc = 1.0 if (k % 4 == 0) else 0.8
        place(S['bass'], pan(bass_note(m, round(dur, 3), grit), 0.0), t0 + b * BEAT, gain * acc)
        b += step
        k += 1


def w_arp(t0, chord, beats, rate=0.25, bright=0.8, gain=1.0, span=2, pattern='up'):
    _, notes = CH[chord]
    seq = [m + 12 * o for o in range(span) for m in notes[:4]]
    if pattern == 'updown':
        seq = seq + seq[-2:0:-1]
    k = 0
    b = 0.0
    while b < beats - 1e-6:
        m = seq[k % len(seq)]
        p = 0.45 * np.sin(k * 0.9)
        acc = 1.0 if k % 4 == 0 else 0.72
        place(S['arp'], pan(pluck_note(m + 12, round(bright, 2)), p), t0 + b * BEAT, gain * acc)
        b += rate
        k += 1


def w_bells(t0, notes_beats, gain=1.0):
    for m, b in notes_beats:
        place(S['bell'], pan(bell_note(m), 0.35 * np.sin(m)), t0 + b * BEAT, gain)


def w_drums(t0, beats, style, gain=1.0):
    """style: 'half', 'four', 'drive', 'soft', 'tick', 'mech'."""
    steps = int(round(beats * 4))
    for s in range(steps):
        t = t0 + s * BEAT / 4
        beat_in_bar = (s // 4) % 4
        sub = s % 4
        if style in ('four', 'drive', 'mech') and sub == 0:
            place(S['drums'], pan(_K, 0), t, gain * 0.95); KICKS.append(t)
        if style in ('half',) and sub == 0 and beat_in_bar in (0, 2):
            place(S['drums'], pan(_K, 0), t, gain * 0.9); KICKS.append(t)
        if style == 'half' and s % 32 == 30:
            place(S['drums'], pan(_KS, 0), t, gain * 0.6); KICKS.append(t)
        if style == 'soft' and sub == 0 and beat_in_bar == 0:
            place(S['drums'], pan(_KS, 0), t, gain * 0.7); KICKS.append(t)
        if style in ('half', 'four', 'drive', 'mech') and sub == 0 and beat_in_bar in (1, 3):
            place(S['drums'], pan(_C, 0.05), t, gain * (0.55 if style == 'half' else 0.7))
        # hats
        if style in ('half', 'soft', 'tick') and sub == 2:
            place(S['drums'], pan(_H, 0.25), t, gain * 0.35)
        if style in ('four', 'mech'):
            place(S['drums'], pan(_H, 0.25), t, gain * (0.34 if sub == 2 else 0.14))
        if style == 'drive':
            place(S['drums'], pan(_H, 0.22), t, gain * (0.4 if sub == 2 else 0.2))
            if sub == 2:
                place(S['drums'], pan(_HO, -0.2), t, gain * 0.12)
        if style in ('half', 'soft', 'four', 'drive') and sub in (1, 3):
            place(S['drums'], pan(_SH, -0.35), t, gain * 0.12)
        if style == 'mech' and s % 8 in (3, 6):
            place(S['drums'], pan(_RM, -0.3), t, gain * 0.22)
        if style == 'tick' and sub == 0:
            place(S['drums'], pan(_RM, -0.2), t, gain * 0.12)


def fill(t_end, gain=1.0):
    """Tom fill over the last beat before t_end."""
    for k, f in enumerate([180, 150, 120, 95]):
        place(S['drums'], pan(tom(f), -0.4 + k * 0.25), t_end - BEAT + k * BEAT / 4, gain * 0.5)


# ------------------------------------------------------------------ arrangement
def section_beats(sid):
    s = SC[sid]
    return s['start'], (s['end'] - s['start']) / BEAT


# HOOK ---------------------------------------------------------------
t0, nb = section_beats('hook')
hit1 = 13 * BEAT      # line converges
hit2 = 21 * BEAT      # logo fills
w_pad(t0, 'Am9', 13, bright=0.25, gain=0.8)
w_pad(t0 + hit1, 'Fmaj9', 8, bright=0.45, gain=0.9)
w_pad(t0 + hit2, 'Cmaj9', 6, bright=0.75, gain=1.0)
w_pad(t0 + 27 * BEAT, 'G6sus', 5.2, bright=0.7, gain=0.95)
w_drums(t0 + 2 * BEAT, 11, 'tick', gain=0.9)
for tc in [cue('h2') - 0.12, cue('h3') - 0.12, cue('h4') - 0.1]:
    place(S['fx'], impact(0.35, seed=int(tc * 10)), tc, 0.55)
place(S['fx'], riser(1.6, 3), t0 + hit1 - 1.6, 0.5)
place(S['fx'], impact(1.0, 5), t0 + hit1, 0.9)
place(S['drums'], pan(_CR, 0), t0 + hit1, 0.25)
w_bass(t0 + hit1, 'Fmaj9', 8, pattern='4', grit=0.2, gain=0.55)
w_arp(t0 + hit1 + 2 * BEAT, 'Fmaj9', 6, rate=0.5, bright=0.5, gain=0.35)
place(S['fx'], riser(1.8, 7), t0 + hit2 - 1.8, 0.55)
place(S['fx'], reverse_swell(1.2), t0 + hit2 - 1.2, 0.7)
place(S['fx'], impact(1.3, 9), t0 + hit2, 1.0)
place(S['drums'], pan(_CR, 0), t0 + hit2, 0.4)
w_bells(t0 + hit2, [(76, 0), (79, 0.5), (83, 1.0), (86, 1.5)], gain=0.35)
w_drums(t0 + 23 * BEAT, 9, 'half', gain=0.75)
w_bass(t0 + 23 * BEAT, 'Cmaj9', 4, pattern='8', grit=0.3, gain=0.7)
w_bass(t0 + 27 * BEAT, 'G6sus', 5, pattern='8', grit=0.3, gain=0.7)
w_arp(t0 + 23 * BEAT, 'Cmaj9', 4, rate=0.25, bright=0.6, gain=0.35)
w_arp(t0 + 27 * BEAT, 'G6sus', 5, rate=0.25, bright=0.65, gain=0.38)

# SEARCH ------------------------------------------------------------
t0, nb = section_beats('search')
prog = [('Am9', 8), ('Fmaj9', 8), ('Cmaj9', 8), ('G6sus', nb - 24)]
b = 0
for ch, n_ in prog:
    w_pad(t0 + b * BEAT, ch, n_, bright=0.5, gain=0.75)
    w_bass(t0 + b * BEAT, ch, n_ - (2 if ch == 'G6sus' else 0), pattern='8', grit=0.4, gain=0.8)
    w_arp(t0 + b * BEAT, ch, n_ - (2 if ch == 'G6sus' else 0), rate=0.25, bright=0.7, gain=0.42, pattern='updown')
    b += n_
w_drums(t0, nb - 2, 'half', gain=0.9)
place(S['fx'], impact(0.5, 11), t0, 0.5)

# STORY -------------------------------------------------------------
t0, nb = section_beats('story')
prog = [('Fmaj9', 8), ('Cmaj9', 8), ('Am9', 8), ('G6sus', 8)]
b = 0
for i, (ch, n_) in enumerate(prog):
    w_pad(t0 + b * BEAT, ch, n_, bright=0.35, gain=0.85)
    if i >= 1:
        w_bass(t0 + b * BEAT, ch, n_, pattern='hold' if i < 3 else '4', grit=0.1, gain=0.32)
    b += n_
motif = [(72, 0), (76, 1), (79, 1.5), (81, 2), (79, 3), (76, 3.5), (74, 4), (76, 5), (72, 6)]
for rep, off in enumerate([0, 8, 16, 24]):
    w_bells(t0 + off * BEAT, [(m + (0 if rep % 2 == 0 else -3 if m != 72 else 0), bb) for m, bb in motif], gain=0.3 if rep < 2 else 0.36)
w_arp(t0 + 16 * BEAT, 'Am9', 8, rate=0.5, bright=0.45, gain=0.3)
w_arp(t0 + 24 * BEAT, 'G6sus', 8, rate=0.25, bright=0.55, gain=0.3)
w_drums(t0 + 8 * BEAT, 16, 'soft', gain=0.6)
w_drums(t0 + 24 * BEAT, 8, 'half', gain=0.6)
place(S['fx'], riser(2.4, 13), t0 + nb * BEAT - 2.4, 0.6)
place(S['fx'], reverse_swell(1.2, 6), t0 + nb * BEAT - 1.2, 0.8)

# VISION (peak) -----------------------------------------------------
t0, nb = section_beats('vision')
place(S['fx'], impact(1.0, 15), t0, 0.8)
place(S['drums'], pan(_CR, 0), t0, 0.3)
w_pad(t0, 'Am9', 4, bright=0.3, gain=0.6)
w_drums(t0, 4, 'tick', gain=1.0)
for k in range(4):
    place(S['drums'], pan(_KS, 0), t0 + k * BEAT, 0.55); KICKS.append(t0 + k * BEAT)
drop = t0 + 4 * BEAT
place(S['fx'], impact(1.2, 17), drop, 0.9)
place(S['drums'], pan(_CR, 0), drop, 0.35)
prog = [('Am9', 4), ('Fmaj9', 8), ('Dm9', 8), ('G6sus', 8)]
b = 4
for ch, n_ in prog:
    w_pad(t0 + b * BEAT, ch, n_, bright=0.65, gain=0.65)
    w_bass(t0 + b * BEAT, ch, n_, pattern='16', grit=0.7, gain=0.85)
    w_arp(t0 + b * BEAT, ch, n_, rate=0.25, bright=1.0, gain=0.5, span=2, pattern='updown')
    for bb in range(int(n_ // 4)):
        place(S['stab'], pan(stab(ch), 0.15), t0 + (b + bb * 4 + 3.5) * BEAT, 0.5)
    b += n_
w_drums(drop, 19, 'drive', gain=1.0)
w_drums(drop + 19 * BEAT, 9, 'four', gain=0.85)  # robot: lighter hats
fill(t0 + 20 * BEAT, 0.9)
fill(t0 + nb * BEAT, 1.0)

# AGRI ---------------------------------------------------------------
t0, nb = section_beats('agri')
place(S['fx'], impact(0.7, 19), t0, 0.6)
prog = [('Am9', 8), ('Fmaj9', 8), ('Cmaj9', 8), ('G6sus', 8)]
b = 0
for ch, n_ in prog:
    w_pad(t0 + b * BEAT, ch, n_, bright=0.55, gain=0.62)
    w_bass(t0 + b * BEAT, ch, n_, pattern='8', grit=0.55, gain=0.85)
    w_arp(t0 + b * BEAT, ch, n_, rate=0.25, bright=0.85, gain=0.42)
    b += n_
w_drums(t0, 10, 'mech', gain=0.85)
w_drums(t0 + 10 * BEAT, 22, 'four', gain=0.9)
w_drums(t0 + 20 * BEAT, 12, 'mech', gain=0.5)
fill(t0 + nb * BEAT, 0.7)

# DOCS ---------------------------------------------------------------
t0, nb = section_beats('docs')
place(S['fx'], impact(0.5, 21), t0, 0.5)
prog = [('Fmaj9', 8), ('Am9', 6), ('G6sus', 4), ('Cmaj9', nb - 18)]
b = 0
for ch, n_ in prog:
    w_pad(t0 + b * BEAT, ch, n_, bright=0.5, gain=0.72)
    w_bass(t0 + b * BEAT, ch, n_, pattern='8', grit=0.4, gain=0.78)
    w_arp(t0 + b * BEAT, ch, n_, rate=0.5, bright=0.6, gain=0.36)
    b += n_
w_drums(t0, nb, 'half', gain=0.85)

# FINALE -------------------------------------------------------------
t0, nb = section_beats('finale')
hitF = 11 * BEAT
place(S['fx'], impact(0.8, 23), t0, 0.6)
place(S['drums'], pan(_CR, 0), t0, 0.3)
w_pad(t0, 'Fmaj9', 8, bright=0.7, gain=0.7)
w_bass(t0, 'Fmaj9', 8, pattern='8', grit=0.6, gain=0.85)
w_arp(t0, 'Fmaj9', 8, rate=0.25, bright=0.95, gain=0.45, pattern='updown')
w_drums(t0, 8, 'four', gain=1.0)
place(S['drums'], pan(_CR, 0), t0 + 3 * BEAT, 0.35)   # "One team."
place(S['fx'], impact(0.6, 25), t0 + 3 * BEAT, 0.5)
w_pad(t0 + 8 * BEAT, 'G6sus', 3.2, bright=0.9, gain=0.75)
place(S['fx'], riser(3 * BEAT + 0.3, 27), t0 + hitF - 3 * BEAT - 0.3, 0.75)
place(S['fx'], reverse_swell(1.5, 8), t0 + hitF - 1.5, 0.9)
place(S['fx'], impact(1.6, 29), t0 + hitF, 1.0)
place(S['drums'], pan(_CR, 0), t0 + hitF, 0.45)
w_pad(t0 + hitF, 'Cmaj9', 8, bright=0.8, gain=1.05)
w_pad(t0 + hitF + 8 * BEAT, 'Fmaj9', 4, bright=0.55, gain=0.8)
w_pad(t0 + hitF + 12 * BEAT, 'Cmaj9', nb - hitF / BEAT - 12 + 4, bright=0.5, gain=0.9)
w_bass(t0 + hitF, 'Cmaj9', 8, pattern='hold', grit=0.1, gain=0.6)
w_bells(t0 + hitF, [(72, 0), (76, 0.5), (79, 1.0), (83, 1.5), (84, 2.0), (88, 3.0)], gain=0.4)
w_bells(t0 + hitF + 8 * BEAT, [(76, 0), (79, 1), (84, 2)], gain=0.3)
cta = cue('f4') - 0.1
w_bells(cta, [(84, 0), (91, 0.25)], gain=0.35)
w_arp(t0 + hitF + 2 * BEAT, 'Cmaj9', 8, rate=0.5, bright=0.5, gain=0.25)

# ------------------------------------------------------------------ sidechain + mixdown
t = t_of(N)
duck = np.ones(N)
for tk in KICKS:
    s = int(tk * SR)
    e = min(N, s + n_of(0.32))
    if s >= N:
        continue
    tt = t[s:e] - tk
    duck[s:e] = np.minimum(duck[s:e], 1 - 0.55 * np.exp(-tt / 0.09))
for k in ('bass', 'pad', 'arp', 'stab'):
    S[k] *= duck[:, None] if k != 'pad' else (1 - (1 - duck) * 0.5)[:, None]

S['pad'] = reverb(S['pad'], wet=0.35, dur=3.2, tone=5500)
S['arp'] = reverb(filt(S['arp'], 'hp', 250), wet=0.28, dur=2.2)
S['bell'] = reverb(S['bell'], wet=0.45, dur=3.5, tone=8000)
S['stab'] = reverb(S['stab'], wet=0.25, dur=1.8)
S['drums'] = reverb(S['drums'], wet=0.08, dur=1.2, tone=7000)
S['bass'] = filt(S['bass'], 'hp', 32, 0.7)

LEVELS = {'drums': 0.62, 'bass': 0.3, 'pad': 0.85, 'arp': 0.52, 'bell': 0.28, 'fx': 0.38, 'stab': 1.0}
mix = sum(S[k] * LEVELS[k] for k in S)
# section dynamics: let the story breathe, peak at vision/agri
SEC_GAIN = {'hook': 1.0, 'search': 0.84, 'story': 0.72, 'vision': 1.0, 'agri': 0.94, 'docs': 0.84, 'finale': 1.0}
gcurve = np.ones(N)
for sc in TL['scenes']:
    a, b2 = int(sc['start'] * SR), int(sc['end'] * SR) if sc['id'] != 'finale' else N
    gcurve[a:b2] = SEC_GAIN[sc['id']]
k = n_of(0.6)
gcurve = np.convolve(np.pad(gcurve, (k, k), mode='edge'), np.ones(k) / k, mode='same')[k:-k]
mix *= gcurve[:, None]
mix = filt(mix, 'highshelf', 9000, 0.7, 1.5)
mix = limiter(mix * 0.9, ceiling_db=-1.5)
os.makedirs(os.path.join(HERE, 'build'), exist_ok=True)
sf.write(os.path.join(HERE, 'build', 'music.wav'), mix.astype(np.float32), SR)
for k in S:
    sf.write(os.path.join(HERE, 'build', f'stem_{k}.wav'), (S[k] * LEVELS[k]).astype(np.float32), SR)
pk = np.max(np.abs(mix))
print(f'music: {DUR:.1f}s  peak {20 * np.log10(pk):.1f} dBFS  kicks {len(KICKS)}')
