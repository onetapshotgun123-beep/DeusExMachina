"""Sky lightning assets: a red-white bolt and a soft glow disc for text_display entities.

Geometry note: at a transformation scale of 40 one font unit is one block, because the
renderer pre-scales glyph space by 0.025. The generators in write_sky.py turn the metrics
below into per-variant scales and translations, so the sizes here are art decisions, not
world sizes: the cell is the glyph, and the bolt is drawn edge to edge inside it.
"""

import json
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.abspath(__file__))
EXT = os.environ.get("DEUS_EXT") or os.path.join(ROOT, "extracted")

BOLT_CELL = (128, 256)
BOLT_N = 4
BOLT_H = 32          # font units; write_sky.py scales this to the world
BOLT_ASCENT = 8
BOLT_BASE = 0xE700

GLOW_CELL = 128
GLOW_H = 48
GLOW_ASCENT = 24
GLOW_BASE = 0xE710


def glyph_layout(cell_w, cell_h, font_h, ascent):
    """Mirror BitmapProvider/TextDisplayRenderer geometry in font units.

    A glyph quad spans font y from (7 - ascent) to (7 - ascent + font_h) below the
    line baseline, and the display maps font y to blocks as 0.025 * scale * (10 - font y),
    so the top of the glyph ends up (ascent + 3) units above the entity and the bottom
    (font_h - ascent - 3) units below it.
    """
    scale = font_h / cell_h
    width = cell_w * scale
    advance = int(0.5 + width) + 1          # +1: the advance marker column
    return {
        "width": width,
        "height": font_h,
        "advance": advance,
        "tx": -(1.0 - advance / 2.0 + width / 2.0),
        "top": ascent + 3,
        "bottom": ascent + 3 - font_h,
    }


def stroke(size, polylines, widths, blur, gain):
    """One lighting layer: draw the polylines at the given widths, then soften."""
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    for pts, w in zip(polylines, widths):
        d.line(pts, fill=255, width=w, joint="curve")
        for p in pts:
            r = w / 2.0
            d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=255)
    if blur:
        m = m.filter(ImageFilter.GaussianBlur(blur))
    a = np.clip(np.array(m, np.float32) * gain, 0, 255).astype(np.uint8)
    return a


def tint_add(dst, alpha, rgb):
    """Over-composite one layer onto the RGBA array."""
    ga = alpha.astype(np.float32) / 255.0
    oa = dst[..., 3].astype(np.float32) / 255.0
    out = ga + oa * (1.0 - ga)
    for c in range(3):
        src = np.full(alpha.shape, rgb[c], np.float32)
        dst[..., c] = np.where(out > 0, (src * ga + dst[..., c] * oa * (1.0 - ga)) / np.maximum(out, 1e-6), dst[..., c])
    dst[..., 3] = (out * 255.0).astype(np.uint8)


def channel(rng, x0, y0, x1, y1, steps, wander):
    """A lightning main discharge: a random walk that keeps its overall direction.

    The steps are many and the per-step wander small, which is what gives the zigzag its
    fine serration; a handful of large segments instead reads as a bent tube.
    """
    pts = [(x0, y0)]
    x, y = x0, y0
    dx = (x1 - x0) / steps
    dy = (y1 - y0) / steps
    for _ in range(steps):
        x += dx + rng.uniform(-wander, wander)
        y += dy
        pts.append((x, y))
    pts[-1] = (x1, y1)
    return pts


def tree(rng, pts, depth, spread, width, out, xlo, xhi):
    """Spawn forks off a parent polyline and recurse into each of them.

    Forks only ever run downward and lose width as they branch, so the discharge tapers
    into a spray at the foot instead of closing into a loop.
    """
    if depth == 0 or len(pts) < 4:
        return
    for _ in range(rng.randint(1, 2)):
        i = rng.randint(1, len(pts) - 3)
        ox, oy = pts[i]
        ex = min(max(ox + rng.uniform(-spread, spread), xlo), xhi)
        ey = min(oy + rng.uniform(spread * 0.5, spread * 1.4), pts[-1][1])
        if abs(ey - oy) < 6:
            continue
        fork = channel(rng, ox, oy, ex, ey, rng.randint(5, 9), width * 0.45)
        w = max(1, width - 2)
        out.append((fork, w))
        tree(rng, fork, depth - 1, spread * 0.5, w, out, xlo, xhi)


def render_bolt(seed):
    """One discharge, drawn edge to edge in a 128x256 cell.

    Real bolts are thin and serrated, so the hot core is only a few pixels wide and the
    red is carried by a wide soft halo: at 44 blocks out a 5 px core is about 0.6 blocks,
    which is what a strike that far away actually looks like.
    """
    rng = random.Random(seed)
    cw, ch = BOLT_CELL
    xlo, xhi = 10, cw - 10
    main = channel(rng, cw / 2 + rng.uniform(-18, 18), -6,
                   cw / 2 + rng.uniform(-26, 26), ch - 6, 54, 6.0)
    forks = []
    tree(rng, main, 3, 40, 6, forks, xlo, xhi)
    lines = [main] + [f[0] for f in forks]
    widths = [5] + [f[1] for f in forks]
    glow_w = [17] + [min(14, w + 7) for w in widths]
    mid_w = [9] + [min(9, w + 3) for w in widths]

    size = (cw, ch)
    img = np.zeros((ch, cw, 4), np.float32)
    tint_add(img, stroke(size, lines, glow_w, 11, 0.5), (186, 12, 28))
    tint_add(img, stroke(size, lines, mid_w, 3, 0.8), (255, 66, 66))
    tint_add(img, stroke(size, lines, widths, 0, 1.0), (255, 244, 240))
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGBA")


def build_bolt():
    cw, ch = BOLT_CELL
    atlas = Image.new("RGBA", (cw * BOLT_N, ch), (0, 0, 0, 0))
    for v in range(BOLT_N):
        atlas.paste(render_bolt(2200 + v * 311), (v * cw, 0))
    px = atlas.load()
    for v in range(BOLT_N):
        px[v * cw + cw - 1, 0] = (0, 0, 0, 1)  # advance marker
    out = os.path.join(EXT, "assets/deusex/textures/font/skybolt.png")
    atlas.save(out, optimize=True)

    doc = {"providers": [{
        "type": "bitmap", "file": "deusex:font/skybolt.png",
        "ascent": BOLT_ASCENT, "height": BOLT_H,
        "chars": ["".join(chr(BOLT_BASE + v) for v in range(BOLT_N))],
    }]}
    with open(os.path.join(EXT, "assets/deusex/font/skybolt.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    lay = glyph_layout(cw, ch, BOLT_H, BOLT_ASCENT)
    print("skybolt", atlas.size, os.path.getsize(out), "bytes", lay)
    return lay


def build_glow():
    """Two glows sharing a cell: a round corona and a broad sky wash.

    The corona is left unstretched and sits behind the bolt. The wash is stretched several
    times wider than it is tall, so its light has to live along the bottom edge - a hot
    centre just turns into a white bar once the quad is squashed.
    """
    c = GLOW_CELL
    y, x = np.mgrid[0:c, 0:c].astype(np.float32)
    nx = (x - (c - 1) / 2) / (c / 2)
    ny = (y - (c - 1) / 2) / (c / 2)
    d = np.sqrt(nx * nx + ny * ny)

    # corona: the ionised glow where the channel meets the ground, so it peaks low and
    # wide with no tight white centre that would read as a ball
    hot = np.clip(1.0 - d / 0.46, 0, 1) ** 2.2
    skirt = np.clip(1.0 - d, 0, 1) ** 2.9
    low = np.clip((ny + 1.0) / 2.0, 0, 1) ** 0.65
    corona = np.zeros((c, c, 4), np.uint8)
    corona[..., 0] = np.clip(196 + hot * 59.0, 0, 255)
    corona[..., 1] = np.clip(20 + hot * 150.0, 0, 255)
    corona[..., 2] = np.clip(30 + hot * 140.0, 0, 255)
    corona[..., 3] = np.clip((skirt * 104.0 + hot * 118.0) * low, 0, 255)

    # the wash peaks just above the horizon and thins out upward and sideways
    side = np.clip(1.0 - np.abs(nx), 0, 1) ** 1.35
    low = np.clip((ny + 1.0) / 2.0, 0, 1)
    band = np.clip(1.0 - np.abs(low - 0.84) / 0.84, 0, 1) ** 1.4
    lift = (side * low) ** 2.2
    wash = np.zeros((c, c, 4), np.uint8)
    wash[..., 0] = np.clip(168 + lift * 87.0, 0, 255)
    wash[..., 1] = np.clip(12 + lift * 118.0, 0, 255)
    wash[..., 2] = np.clip(26 + lift * 104.0, 0, 255)
    wash[..., 3] = np.clip(side * band * 198.0, 0, 255)

    atlas = np.concatenate([corona, wash], axis=1)
    atlas[0, c - 1] = (0, 0, 0, 1)      # advance markers, one per glyph
    atlas[0, 2 * c - 1] = (0, 0, 0, 1)

    out = os.path.join(EXT, "assets/deusex/textures/font/skyglow.png")
    Image.fromarray(atlas, "RGBA").save(out, optimize=True)

    doc = {"providers": [{
        "type": "bitmap", "file": "deusex:font/skyglow.png",
        "ascent": GLOW_ASCENT, "height": GLOW_H,
        "chars": ["".join(chr(GLOW_BASE + i) for i in range(2))],
    }]}
    with open(os.path.join(EXT, "assets/deusex/font/skyglow.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    lay = glyph_layout(c, c, GLOW_H, GLOW_ASCENT)
    print("skyglow", atlas.shape, os.path.getsize(out), "bytes", lay)
    return lay


if __name__ == "__main__":
    build_bolt()
    build_glow()
