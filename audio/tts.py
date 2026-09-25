"""Generate the voiceover with Kokoro (open-weight TTS, runs locally on CPU).

For every line in vo_script.json this writes a trimmed 48 kHz mono WAV to
audio/build/vo/<id>.wav and records its duration plus the speech segments
between pauses (used to sync animations to individual clauses).

Model files (Apache-2.0) are downloaded from the kokoro-onnx GitHub release:
  kokoro-v1.0.onnx, voices-v1.0.bin  ->  $KOKORO_DIR (default /home/user/models)
"""
import json
import os
import sys

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build", "vo")
MODEL_DIR = os.environ.get("KOKORO_DIR", "/home/user/models")
SR_OUT = 48000


def speech_segments(x, sr, win=0.01, thresh_db=-38.0, min_gap=0.09, min_seg=0.06):
    """Return [(start, end), ...] in seconds of voiced regions separated by pauses."""
    hop = int(sr * win)
    n = len(x) // hop
    rms = np.sqrt(np.mean(x[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms / (np.max(rms) + 1e-12))
    voiced = db > thresh_db
    segs, start, silent_run = [], None, 0
    for i, v in enumerate(voiced):
        if v:
            if start is None:
                start = i
            silent_run = 0
        elif start is not None:
            silent_run += 1
            if silent_run * win >= min_gap:
                end = i - silent_run + 1
                if (end - start) * win >= min_seg:
                    segs.append([start * win, end * win])
                start, silent_run = None, 0
    if start is not None:
        end = n - silent_run
        segs.append([start * win, end * win])
    return segs


def main():
    from kokoro_onnx import Kokoro

    script = json.load(open(os.path.join(HERE, "vo_script.json")))
    only = set(sys.argv[1:])
    os.makedirs(BUILD, exist_ok=True)
    kokoro = Kokoro(os.path.join(MODEL_DIR, "kokoro-v1.0.onnx"), os.path.join(MODEL_DIR, "voices-v1.0.bin"))
    manifest_path = os.path.join(BUILD, "manifest.json")
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {}

    for scene in script["scenes"]:
        for line in scene["lines"]:
            if only and line["id"] not in only:
                continue
            text = line.get("tts", line["text"])
            speed = line.get("speed", scene.get("speed", script["speed"]))
            audio, sr = kokoro.create(text, voice=line.get("voice", script["voice"]), speed=speed, lang="en-us")
            audio = np.asarray(audio, dtype=np.float64)
            segs = speech_segments(audio, sr)
            # Trim to the voiced region, keeping a short natural pad.
            pad_in, pad_out = 0.03, 0.12
            a = max(0, int((segs[0][0] - pad_in) * sr))
            b = min(len(audio), int((segs[-1][1] + pad_out) * sr))
            audio = audio[a:b]
            # 10 ms fades so trimmed edges never click.
            f = int(0.01 * sr)
            audio[:f] *= np.linspace(0, 1, f)
            audio[-f:] *= np.linspace(1, 0, f)
            out = resample_poly(audio, SR_OUT, sr)
            path = os.path.join(BUILD, f"{line['id']}.wav")
            sf.write(path, out.astype(np.float32), SR_OUT)
            off = a / sr
            segs = [[round(s - off, 3), round(e - off, 3)] for s, e in segs]
            manifest[line["id"]] = {"duration": round(len(out) / SR_OUT, 3), "segments": segs, "text": line["text"]}
            print(f"{line['id']:>3}  {manifest[line['id']]['duration']:6.2f}s  segs={len(segs)}  {line['text']}")

    json.dump(manifest, open(manifest_path, "w"), indent=1)


if __name__ == "__main__":
    main()
