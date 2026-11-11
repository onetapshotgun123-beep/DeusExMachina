"""Bake the song's drum hits into a one-byte-per-tick envelope for the HUD.

The corner flash has to move with the drums the player hears, not with a guessed tempo. Kicks are
the most legible beat in this mix, so each server tick (1/20 s) is reduced to the energy of the
35-130 Hz band relative to its own half-second neighbourhood; that keeps a quiet verse pulsing
softly and a chorus hit pulsing hard without any hand-tuned curve. The result is one byte per tick,
which ShowDrum reads straight at the heard sample.

Run from deus/:  python make_beat.py [--preview out.png]
"""

import os
import sys

import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(ROOT, "client", "src", "main", "resources", "assets", "deusexmachina")
TRACK = os.path.join(ASSETS, "sounds", "main_track.ogg")
OUT = os.path.join(ASSETS, "show", "beat.bin")
HOP = 2205          # SAMPLE_RATE / 20: one server tick
KICK_HZ = (30.0, 90.0)
NEIGHBOURHOOD = 10  # ticks either side for the local floor (half a second)
WINDOW = 40         # ticks either side for the loudness normaliser (2 s)
MIN_GAP = 8         # ticks between two accepted hits: 400 ms
GATE = 0.6          # local rise needed to call a hit
ABS_GATE_DB = 7.0   # and an absolute rise, so a quiet passage stays quiet
DECAY = 2.0         # ticks of the pulse tail
TAIL = 7


def band_energy(mono, rate, frames, band):
    seg = mono[: len(mono) // frames * frames].reshape(-1, frames)
    spec = np.abs(np.fft.rfft(seg * np.hanning(frames).astype(np.float32), axis=1))
    fr = np.fft.rfftfreq(frames, 1.0 / rate)
    mask = (fr >= band[0]) & (fr <= band[1])
    return 20.0 * np.log10(np.maximum(np.sqrt((spec[:, mask] ** 2).mean(axis=1)), 1e-9))


def novelty(mono, rate, frames, band):
    """Positive rise in a band's energy: a hit shows as a jump, a held note does not."""
    energy = band_energy(mono, rate, frames, band)
    padded = np.pad(energy, NEIGHBOURHOOD, mode="edge")
    floor = np.array([np.median(padded[i:i + 2 * NEIGHBOURHOOD + 1])
                      for i in range(len(energy))])
    return np.maximum(0.0, energy - floor)


def local_norm(x, half=WINDOW):
    padded = np.pad(x, half, mode="edge")
    scale = np.array([np.percentile(padded[i:i + 2 * half + 1], 97.0) for i in range(len(x))])
    return np.clip(x / np.maximum(scale, 1e-6), 0.0, 1.0)


def pulse_train(nov, gate=GATE, abs_gate=ABS_GATE_DB):
    """One decaying flash per accepted hit, scaled by how hard it lands in its own section."""
    n = local_norm(nov)
    env = np.zeros(len(n), dtype=np.float32)
    last = -MIN_GAP
    for i in np.flatnonzero((n > gate) & (nov > abs_gate)):
        if i - last < MIN_GAP:
            if n[i] <= n[last]:
                continue
        last = i
        s = float(min(1.0, 0.35 + 0.65 * n[i]))
        for k in range(min(TAIL, len(env) - i)):
            env[i + k] = max(env[i + k], s * float(np.exp(-k / DECAY)))
    return env


def envelope(frames=HOP):
    """Per-tick drum level in 0..1, one value per tick of the shipped track."""
    with sf.SoundFile(TRACK) as f:
        y = f.read(dtype="int16", always_2d=True).astype(np.float32)
        rate = f.samplerate
    mono = y.mean(axis=1) / 32768.0
    v = pulse_train(novelty(mono, rate, frames, KICK_HZ))
    return v.astype(np.float32), len(v)


def main():
    v, nf = envelope()
    data = np.round(v * 255.0).astype(np.uint8)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "wb") as f:
        f.write(data.tobytes())
    loud = data >= 90
    starts = np.flatnonzero(loud & ~np.r_[False, loud[:-1]])
    gaps = np.diff(starts) / 20.0
    print("%s: %d ticks, %d hits >= 0.35, mean gap %.2f s, median gap %.2f s, max %d"
          % (os.path.relpath(OUT, ROOT), nf, len(starts),
             gaps.mean() if len(gaps) else 0.0,
             np.median(gaps) if len(gaps) else 0.0, int(data.max())))
    print("first hits (s):", ", ".join("%.2f" % (s / 20.0) for s in starts[:12]))
    if "--preview" in sys.argv:
        make_preview(v, sys.argv[sys.argv.index("--preview") + 1])


def make_preview(v, path):
    """A strip the drum pattern can be eyeballed against: one column per tick."""
    from PIL import Image, ImageDraw
    w, h = 1400, 260
    img = Image.new("RGB", (w, h), (12, 8, 10))
    d = ImageDraw.Draw(img)
    cols = np.array_split(np.arange(len(v)), w)
    for x, idx in enumerate(cols):
        level = float(v[idx].max())
        top = int(h - level * (h - 30))
        shade = int(60 + 195 * level)
        d.line([(x, h), (x, top)], fill=(min(255, shade + 40), shade // 3, shade // 4))
    for sec in range(0, int(len(v) / 20) + 1, 30):
        x = int(sec * 20 / len(v) * w)
        d.line([(x, 0), (x, 12)], fill=(120, 90, 90))
        d.text((x + 2, 1), str(sec), fill=(150, 120, 120))
    img.save(path)
    print("preview:", path)


if __name__ == "__main__":
    main()
