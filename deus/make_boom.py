import numpy as np
import soundfile as sf

SR = 44100
DUR = 7.0
N = int(SR * DUR)
RISE = 0.35
import os
HD, BD, HG, BG, KN = (float(v) for v in os.environ.get('BP', '2.5,4.0,0.5,1.0,0.6').split(','))
GAP = 0.03
rng = np.random.default_rng(1337)
t = np.arange(N) / SR


def fft_filter(x, lo=None, hi=None, slope=24):
    X = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(x.shape[0], 1 / SR)
    g = np.ones_like(f)
    n = slope / 6
    if hi is not None:
        g *= 1 / np.sqrt(1 + (f / hi) ** (2 * n))
    if lo is not None:
        with np.errstate(divide="ignore"):
            g *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1e-9)) ** (2 * n))
    if X.ndim > 1:
        g = g[:, None]
    return np.fft.irfft(X * g, n=x.shape[0], axis=0)


def sweep_lowpass(x, cutoff):
    a = 1 - np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    s1 = np.zeros(x.shape[1])
    s2 = np.zeros(x.shape[1])
    for i in range(x.shape[0]):
        s1 += a[i] * (x[i] - s1)
        s2 += a[i] * (s1 - s2)
        y[i] = s2
    return y


def env(tau, attack=0.002, n=N):
    tt = np.arange(n) / SR
    return np.minimum(tt / attack, 1) * np.exp(-tt / tau)


def st(x):
    return np.stack([x, x], 1)


def reverb(x, length, tau, lo, hi):
    ir_len = int(SR * length)
    ir_t = np.arange(ir_len) / SR
    ir = rng.standard_normal((ir_len, 2)) * np.exp(-ir_t / tau)[:, None]
    ir = fft_filter(ir, lo=lo, hi=hi)
    ir /= np.sqrt(np.sum(ir ** 2, axis=0, keepdims=True))
    L = x.shape[0] + ir_len
    return np.stack(
        [np.fft.irfft(np.fft.rfft(x[:, c], L) * np.fft.rfft(ir[:, c], L), L)[: x.shape[0]] for c in range(2)], 1
    )


# ---- transient bus: kept clean so the hit lands as a hard punch ----
hit = np.zeros((N, 2))
click = fft_filter(rng.standard_normal((N, 2)), lo=2000, hi=12000) * env(0.0025, 0.0001)[:, None]
hit += click * 1.4
f_kick = 42 + 260 * np.exp(-t / 0.018)
kick = np.sin(2 * np.pi * np.cumsum(f_kick) / SR) * env(0.32, 0.0004)
hit += st(np.tanh(kick * 2.2)) * 0.95
crack = fft_filter(rng.standard_normal((N, 2)), lo=900, hi=7000) * env(0.05, 0.0003)[:, None]
hit += crack * 1.1
snap = fft_filter(rng.standard_normal((N, 2)), lo=150, hi=1800) * env(0.09, 0.0005)[:, None]
hit += snap * 1.3
f_sub = 30 + 30 * np.exp(-t / 0.25)
sub = np.sin(2 * np.pi * np.cumsum(f_sub) / SR) * env(1.1, 0.004)
hit += st(sub) * 0.75
hit_wet = reverb(hit, 2.0, 0.35, 60, 4000)
hit += hit_wet * 0.35

# ---- body bus: dark, heavy, limited hard for density ----
body = np.zeros((N, 2))
orig, osr = sf.read("backup/boom/boom_orig.ogg", dtype="float64")
src_idx = np.arange(0, orig.shape[0] - 1, 0.82)
orig_p = np.stack([np.interp(src_idx, np.arange(orig.shape[0]), orig[:, c]) for c in range(2)], 1)
m = min(N, orig_p.shape[0])
body[:m] += orig_p[:m] * 0.6

rumble = fft_filter(rng.standard_normal((N, 2)), lo=30, hi=500) * env(0.5, 0.012)[:, None]
body += rumble * 1.6

notes = [36.71, 73.42, 77.78, 103.83, 110.0, 146.83]
gains = [1.0, 0.8, 0.45, 0.4, 0.55, 0.3]
braam = np.zeros((N, 2))
for f0, g in zip(notes, gains):
    for k, det in enumerate((-0.006, 0.0, 0.0065)):
        ph = rng.uniform(0, 1)
        bend = 1 - 0.035 * (1 - np.exp(-t / 1.8))
        saw = 2 * ((np.cumsum(f0 * (1 + det) * bend) / SR + ph) % 1) - 1
        pan = (k - 1) * 0.6
        braam[:, 0] += saw * g * (1 - pan) / 2
        braam[:, 1] += saw * g * (1 + pan) / 2
cut = 300 + 3200 * np.exp(-t / 1.2)
braam = sweep_lowpass(braam, cut)
benv = np.minimum(t / 0.015, 1) * (0.3 + 0.7 * np.exp(-t / 0.6)) * np.exp(-t / 2.6)
braam = np.tanh(braam * benv[:, None] * 3.0)
body += braam * 1.4
body += fft_filter(np.tanh(braam * 6.0), lo=300, hi=2600) * 0.4

low = fft_filter(body, hi=110)
body += fft_filter(np.tanh(low * 4.0), lo=120, hi=2500)
body += reverb(body, 3.4, 0.85, 40, 2200) * 0.45

fade = int(SR * 1.2)
body[-fade:] *= np.linspace(1, 0, fade)[:, None] ** 2
body -= body.mean(axis=0)
body /= np.max(np.abs(body))
body = np.tanh(body * BD) / np.tanh(BD)

hit[-fade:] *= np.linspace(1, 0, fade)[:, None] ** 2
hit /= np.max(np.abs(hit))
hit = np.tanh(hit * HD) / np.tanh(HD)

mix = hit * HG + body * BG
knee = KN
over = np.abs(mix) > knee
mix[over] = np.sign(mix[over]) * (knee + (1 - knee) * np.tanh((np.abs(mix[over]) - knee) / (1 - knee)))
mix *= 0.97 / np.max(np.abs(mix))
mix[:3] *= np.array([0.25, 0.5, 0.75])[:, None]

# ---- rise: reverse swell that cuts to silence just before the hit ----
RN = int(SR * RISE)
G = int(SR * GAP)
rt = np.arange(RN) / SR
swell_len = RN - G
rev = reverb(np.vstack([body[: int(SR * 0.6)], np.zeros((int(SR * 1.5), 2))]), 1.6, 0.5, 80, 3000)
rev = rev[::-1][-swell_len:]
rev /= np.max(np.abs(rev)) + 1e-9
st_t = np.arange(swell_len) / SR
shape = (st_t / st_t[-1]) ** 2.5
noise = fft_filter(rng.standard_normal((swell_len, 2)), lo=100, hi=2500) * (st_t / st_t[-1])[:, None] ** 3
sub_rise = np.sin(2 * np.pi * np.cumsum(28 + 50 * st_t / st_t[-1]) / SR) * shape
rise = np.zeros((RN, 2))
rise[:swell_len] = rev * shape[:, None] * 0.55 + noise * 0.3 + st(sub_rise) * 0.45
cutoff = int(SR * 0.004)
rise[swell_len - cutoff : swell_len] *= np.linspace(1, 0, cutoff)[:, None]
rise *= 0.85 / np.max(np.abs(rise))

out = "extracted/assets/deusex/sounds/"
sf.write(out + "boom.ogg", mix.astype(np.float32), SR, format="OGG", subtype="VORBIS", compression_level=0.0)
sf.write(out + "boom_rise.ogg", rise.astype(np.float32), SR, format="OGG", subtype="VORBIS", compression_level=0.0)
prev = np.zeros((int(SR * 0.8) + N, 2))
s = int(SR * 0.8) - RN
prev[s : s + RN] += rise
prev[s + RN :] += mix
sf.write("preview/boom_new.wav", prev.astype(np.float32), SR)
print("done boom", mix.shape, "rise", rise.shape, "peak", np.max(np.abs(mix)))
