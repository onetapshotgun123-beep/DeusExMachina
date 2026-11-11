"""Generate the heart_burst atlas: the explosion that fires on the drop.

heart_burst.png is drawn as a *title*, so one cell covers the whole viewport: 256x128 cells at
provider height 600 become 1200x600 GUI px, which spans a 960x540 viewport (1920x1080 at GUI
scale 2) with margin on every side.

Two earlier attempts failed for opposite reasons. The first was a flat red rectangle with a thin
white ring, which read as fireworks. The second drew the blast as PIL polygons in near-white
greys - a hot core at (255,250,240), a ring at (255,235,215), filament tips at (255,196,150) -
and because those colours sit on top of the red wash, the screen came out pale fog. Vector
shapes were not the problem; the palette was.

So this version never picks a colour by hand. Every pixel gets a single heat value in 0..1 from
four additive fields (core, shockwave, filaments, embers), and heat is mapped through one fire
ramp. The ramp only reaches white at heat >= 0.9, which the field sums can only reach while the
core is still alive, i.e. the first two frames. From frame 3 down the maths cannot produce a pale
pixel even by accident.

  f1    the white-out. One tick, screen-full, brightest at the heart.
  f2..  a fireball that dies inside half a second, a turbulent front that runs outward past the
        corners, filaments riding it, embers left behind.
  wash  a vignette, not a fill. It reaches zero at the cell border so no rectangular edge can
        ever come into view, but it is still carrying most of its alpha at the viewport corner
        (radius 1.2 of the cell) so the screen edges get tinted too.

Everything is computed at 4x and box-filtered down; the fields are smooth so there is little to
alias, but the filaments are only ~2 px wide and the provider scales the cell up 4.7x.
"""
import math
import os

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(ROOT, "extracted/assets/deusex/textures/font")
FRAMES = 16
# 2:1 cells, so drawing at the same height as red_lv (600) gives the same 1200x600 screen
# coverage that already provably spans a 960x540 viewport. A square cell would leave the sides of
# the screen untinted.
CW, CH = 256, 128
SEED = 20261104
SS = 4

# wash strength per frame. opening_flash never shows frame 0, so the white-out lives in frame 1
# and only in frame 1: it is one tick, and anything longer stops reading as a hit.
WASH = [255, 255, 226, 190, 156, 124, 96, 74, 57, 43, 33, 25, 19, 14, 10, 6]

# Red from frame 3 onward. The old ramp only reached full red at frame 6, by which point the wash
# was already at 39% and the whole burst looked like pale fog.
WASH_COLOUR = [(255, 250, 245), (255, 240, 228), (255, 120, 70), (240, 55, 40),
               (225, 25, 30), (210, 15, 26), (200, 12, 24), (188, 10, 22),
               (175, 9, 20), (162, 8, 18), (150, 7, 16), (138, 6, 15),
               (126, 6, 13), (114, 5, 12), (102, 5, 11), (92, 4, 10)]

# heat -> colour. Only the top of the ramp is hot enough to look white, and only the live core
# can get there.
FIRE_RAMP = [(0.00, (118, 6, 12)),
             (0.16, (184, 14, 20)),
             (0.32, (226, 36, 30)),
             (0.48, (246, 84, 34)),
             (0.62, (255, 138, 48)),
             (0.76, (255, 192, 92)),
             (0.89, (255, 234, 168)),
             (1.00, (255, 252, 240))]


def fire_lut(steps=4096):
    x = np.linspace(0.0, 1.0, steps)
    out = np.zeros((steps, 3), np.float32)
    for i in range(len(FIRE_RAMP) - 1):
        a, ca = FIRE_RAMP[i]
        b, cb = FIRE_RAMP[i + 1]
        sel = (x >= a) & (x <= b)
        k = ((x[sel] - a) / (b - a))[:, None]
        out[sel] = np.array(ca, np.float32) * (1 - k) + np.array(cb, np.float32) * k
    return out


LUT = fire_lut()


def fields():
    """Per-pixel coordinate fields, computed once and shared by every frame."""
    W, Hh = CW * SS, CH * SS
    yy, xx = np.mgrid[0:Hh, 0:W].astype(np.float32)
    dx, dy = xx - W / 2.0, yy - Hh / 2.0
    corner = math.hypot(W / 2.0, Hh / 2.0)
    # texture pixels are square on screen (the provider scales x and y by the same factor), so a
    # circle here is a circle in game. r is normalised to the half-diagonal so the front can run
    # past the corners.
    r = np.hypot(dx, dy) / corner
    th = np.arctan2(dy, dx)

    rng = np.random.default_rng(SEED)

    # turbulence: a few plane waves at random directions. Breaks the shockwave into fingers
    # without the regular, knitted look of a fixed harmonic ring.
    pl = np.zeros((Hh, W), np.float32)
    wsum = 0.0
    for amp, wl in [(1.0, 74.0), (0.75, 41.0), (0.5, 23.0), (0.3, 13.0), (0.18, 7.0)]:
        a = rng.uniform(0.0, 2 * math.pi)
        p = rng.uniform(0.0, 2 * math.pi)
        f = 2 * math.pi / (wl * SS)
        pl += amp * np.sin(math.cos(a) * dx * f + math.sin(a) * dy * f + p)
        wsum += amp
    pl = np.clip(0.5 + 0.5 * pl / wsum, 0.0, 1.0)

    # filaments: narrow angular spokes at even spacing, so the burst stays radially symmetric -
    # that symmetry is what reads as an explosion - and only their brightness varies.
    n = 56
    sa = np.linspace(0.0, 2 * math.pi, n, endpoint=False) + rng.uniform(-0.045, 0.045, n)
    sw = rng.uniform(0.10, 1.0, n) ** 1.7
    sig = rng.uniform(0.028, 0.062, n)
    sp = np.zeros((Hh, W), np.float32)
    for i in range(n):
        d = (th - sa[i] + math.pi) % (2 * math.pi) - math.pi
        sp += np.float32(sw[i]) * np.exp(-(d * d) / (2 * sig[i] * sig[i]))
    sp = np.clip(sp, 0.0, 1.0)

    # embers: sparse, hashed on angle so they stay put across frames instead of boiling
    ne = 190
    ea = rng.uniform(0.0, 2 * math.pi, ne)
    er = rng.uniform(0.12, 1.5, ne)
    eb = rng.uniform(0.25, 1.0, ne)
    es = rng.uniform(0.010, 0.030, ne)
    emb = np.zeros((Hh, W), np.float32)
    for i in range(ne):
        d = (th - ea[i] + math.pi) % (2 * math.pi) - math.pi
        rr = r - er[i]
        emb += np.float32(eb[i]) * np.exp(-(d * d) / (2 * es[i] * es[i]) - (rr * rr) / 0.0016)
    emb = np.clip(emb, 0.0, 1.0)

    # wash falloff. The viewport corner sits at r = 1.2 of the cell, so the falloff has to still
    # carry most of its alpha there, but it must reach zero at the cell's own border.
    nx = dx / (W / 2.0)
    ny = dy / (Hh / 2.0)
    dn = np.hypot(nx, ny)
    rad = np.clip(1.0 - (np.clip(dn - 0.20, 0.0, None) / 1.35) ** 2.2, 0.0, 1.0)
    border = np.clip(1.0 - (np.maximum(np.abs(nx), np.abs(ny)) - 0.94) / 0.06, 0.0, 1.0)
    vig = (rad * border).astype(np.float32)

    return dict(r=r, pl=pl, sp=sp, emb=emb, vig=vig)


def heat(f, F):
    """Additive fire field for one frame, in 0..1."""
    t = f / float(FRAMES - 1)
    r, pl = F["r"], F["pl"]
    out = np.zeros_like(r)

    # core: the heart itself. It has to be *gone* within half a second, or the blast leaves a
    # white ball sitting in the middle of the screen instead of an expanding front.
    if t < 0.42:
        ca = (1.0 - t / 0.42) ** 1.5
        rc = 0.05 + 0.55 * t
        out += ca * np.exp(-((r / rc) ** 2) * 1.7) * (0.70 + 0.55 * pl)

    # shockwave: a turbulent front that runs outward past the corners.
    wa = max(0.0, 1.0 - t * 1.12) ** 1.25
    rf = 0.10 + 1.60 * t ** 0.5
    if wa > 0.01:
        turb = 0.80 + 0.34 * pl
        wr = 0.050 + 0.070 * (1.0 - t)
        out += wa * np.exp(-(((r - rf * turb) / wr) ** 2)) * (0.45 + 0.80 * pl)

        # filaments riding the front. The band has to stay narrow and *on* the front: whenever it
        # spans most of the radius the spokes converge into a hyperspace fan instead of a blast.
        band = np.exp(-((r - 0.80 * rf * turb) ** 2) / (2 * (0.16 * rf + 0.03) ** 2))
        out += wa * 0.80 * F["sp"] * band

    # embers left behind the front. Their positions are static, so the visible band sweeps
    # outward with the front - which reads as debris being carried out rather than boiling.
    # Deliberately not multiplied by the spoke field: that is what turned them into rays.
    if t > 0.12:
        fade = max(0.0, 1.0 - t * 0.95) ** 1.6
        behind = np.exp(-((r - 0.55 * rf) ** 2) / (2 * (0.34 * rf + 0.05) ** 2))
        out += fade * 0.70 * F["emb"] * behind

    return np.clip(out, 0.0, 1.0)


def render_frame(f, F):
    if f == 0:
        # hard white hit. opening_flash never shows this frame, but a stray index 0 should still
        # read as the flash rather than as an empty cell.
        return np.full((CH, CW, 4), 255, np.uint8)

    Hh = heat(f, F)
    # The gain keeps the ramp out of the white end as the burst ages: by frame 4 nothing can
    # reach heat 0.9 no matter how the fields add up.
    gain = 1.0 if f <= 2 else max(0.42, 1.0 - 0.16 * (f - 2))
    h = np.clip(Hh * gain, 0.0, 1.0)

    idx = (h * (len(LUT) - 1)).astype(np.int32)
    fire_rgb = LUT[idx]
    fire_a = np.clip(h ** 0.82, 0.0, 1.0)[..., None] * F["vig"][..., None]

    cover = (F["vig"] * (WASH[f] / 255.0))[..., None]
    col = np.array(WASH_COLOUR[f], np.float32)

    alpha = fire_a + cover * (1.0 - fire_a)
    rgb = (fire_rgb * fire_a + col * cover * (1.0 - fire_a)) / np.maximum(alpha, 1e-4)
    # rgb is already 0..255 (the LUT and WASH_COLOUR are byte palettes) while alpha is a 0..1
    # fraction; clipping both to 0..1 used to clamp every coloured pixel up to pure white
    out = np.concatenate([rgb, alpha * 255.0], axis=2)
    big = np.clip(out, 0, 255).astype(np.uint8)
    return np.asarray(Image.fromarray(big, "RGBA").resize((CW, CH), Image.BOX))


def main():
    F = fields()
    cells = [render_frame(f, F) for f in range(FRAMES)]
    atlas = np.concatenate(cells, axis=1)
    Image.fromarray(atlas, "RGBA").save(os.path.join(TEX, "heart_burst.png"))
    print("heart_burst.png", atlas.shape[1], "x", atlas.shape[0])

    os.makedirs(os.path.join(ROOT, "preview"), exist_ok=True)
    sheet = Image.new("RGBA", (CW * FRAMES, CH), (20, 26, 30, 255))
    for f, c in enumerate(cells):
        bg = Image.new("RGBA", (CW, CH), (20, 26, 30, 255))
        bg.alpha_composite(Image.fromarray(c, "RGBA"))
        sheet.paste(bg, (f * CW, 0))
    sheet.convert("RGB").save(os.path.join(ROOT, "preview/burst_frames.png"))

    corner = math.hypot(CW / 2.0, CH / 2.0)
    yy, xx = np.mgrid[0:CH, 0:CW]
    # the part a 960x540 viewport actually shows of a 1200x600 title
    vx0, vx1 = int(CW * 0.1), int(CW * 0.9)
    vy0, vy1 = int(CH * 0.05), int(CH * 0.95)
    for f, c in enumerate(cells):
        al = c[:, :, 3].astype(np.float32) / 255.0
        rgb = c[:, :, :3].astype(np.int32)
        # "pale" = bright but not saturated, which is exactly the fog failure mode
        mx, mn = rgb.max(2), rgb.min(2)
        pale = ((mn > 150) & (mx - mn < 60) & (al > 0.5)).mean()
        edge = max(al[0, :].max(), al[-1, :].max(), al[:, 0].max(), al[:, -1].max())
        hot = al > 0.55
        rad = (0.0 if not hot.any()
               else float(np.hypot(xx[hot] - CW / 2, yy[hot] - CH / 2).max()) / corner)
        print("  f%-2d cell a %3d%%  screen a %3d%%  border a %2d%%  pale %2d%%  "
              "front r=%.2f  peak %.2f"
              % (f, int(100 * al.mean()), int(100 * al[vy0:vy1, vx0:vx1].mean()),
                 int(100 * edge), int(100 * pale), rad, al.max()))


if __name__ == "__main__":
    main()
