import json
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.abspath(__file__))
EXT = os.path.join(ROOT, "extracted")

# bolt cell: 128 x 256 source px -> 20 x 40 font units at height 40 (80 x 160 gui px at title scale 4)
BOLT_W, BOLT_H = 128, 256
BOLT_N = 3
BOLT_FONT_H = 40
BOLT_ASCENT = 43

# flash cell: 16 x 16 -> 600 x 600 font units (full screen)
FLASH_W = FLASH_H = 16
FLASH_ALPHAS = [160, 115, 72, 34]

BOLT_BASE = 0xE700
FLASH_BASE = 0xE710


def jagged(rng, x0, y0, x1, y1, steps, spread):
    pts = [(x0, y0)]
    for i in range(1, steps):
        t = i / steps
        x = x0 + (x1 - x0) * t + rng.uniform(-spread, spread)
        y = y0 + (y1 - y0) * t + rng.uniform(-spread * 0.35, spread * 0.35)
        pts.append((x, y))
    pts.append((x1, y1))
    return pts


def draw_polys(core, glow, polylines, widths, glow_widths):
    d = ImageDraw.Draw(core)
    g = ImageDraw.Draw(glow)
    for pts, w, gw in zip(polylines, widths, glow_widths):
        d.line(pts, fill=255, width=w, joint="curve")
        g.line(pts, fill=255, width=gw, joint="curve")
        for p in pts:  # rounded joints / caps
            r = w / 2.0
            d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=255)
            rg = gw / 2.0
            g.ellipse([p[0] - rg, p[1] - rg, p[0] + rg, p[1] + rg], fill=255)


def render_bolt(seed, variant):
    rng = random.Random(seed)
    core = Image.new("L", (BOLT_W, BOLT_H), 0)
    glow = Image.new("L", (BOLT_W, BOLT_H), 0)

    top_x = 64 + rng.uniform(-10, 10)
    bot_x = 64 + rng.uniform(-22, 22)
    main = jagged(rng, top_x, -6, bot_x, BOLT_H + 6, 9, 13)
    main = [(min(max(p[0], 30), 98), p[1]) for p in main]

    branches = []
    for _ in range(rng.randint(2, 3)):
        i = rng.randint(1, len(main) - 3)
        bx, by = main[i]
        side = -1 if bx > 64 else 1
        ex = bx + side * rng.uniform(18, 36)
        ey = by + rng.uniform(34, 74)
        branches.append(jagged(rng, bx, by, min(max(ex, 14), 114), min(ey, BOLT_H - 4), 4, 9))

    draw_polys(core, glow, [main] + branches, [15] + [8] * len(branches), [34] + [20] * len(branches))

    outer = glow.filter(ImageFilter.GaussianBlur(15))
    inner = glow.filter(ImageFilter.GaussianBlur(5))
    core_img = core

    def tint(mask, rgb, gain):
        a = np.array(mask, np.float32) * gain
        a = np.clip(a, 0, 255).astype(np.uint8)
        arr = np.zeros((BOLT_H, BOLT_W, 4), np.uint8)
        arr[..., 0], arr[..., 1], arr[..., 2] = rgb
        arr[..., 3] = a
        return Image.fromarray(arr, "RGBA")

    img = tint(outer, (105, 150, 255), 0.62)
    img = Image.alpha_composite(img, tint(inner, (190, 216, 255), 1.0))
    img = Image.alpha_composite(img, tint(core_img, (246, 250, 255), 1.0))

    # fade the lower end into the storm so the cell edge never shows
    arr = np.array(img, np.uint8)
    ramp = np.ones(BOLT_H, np.float32)
    fade_start = 198
    ramp[fade_start:] = np.linspace(1.0, 0.0, BOLT_H - fade_start)
    arr[..., 3] = np.clip(arr[..., 3].astype(np.float32) * ramp[:, None], 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def build_bolt():
    atlas = Image.new("RGBA", (BOLT_W * BOLT_N, BOLT_H), (0, 0, 0, 0))
    for v in range(BOLT_N):
        atlas.paste(render_bolt(971 + v * 37, v), (v * BOLT_W, 0))
    px = atlas.load()
    for v in range(BOLT_N):
        px[v * BOLT_W + BOLT_W - 1, 0] = (0, 0, 0, 1)  # constant advance marker
    out = os.path.join(EXT, "assets/deusex/textures/font/bolt.png")
    atlas.save(out, optimize=True)

    doc = {
        "providers": [
            {
                "type": "bitmap",
                "file": "deusex:font/bolt.png",
                "ascent": BOLT_ASCENT,
                "height": BOLT_FONT_H,
                "chars": ["".join(chr(BOLT_BASE + v) for v in range(BOLT_N))],
            }
        ]
    }
    with open(os.path.join(EXT, "assets/deusex/font/bolt.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("bolt atlas", atlas.size, os.path.getsize(out), "bytes")


def build_flash():
    n = len(FLASH_ALPHAS)
    arr = np.zeros((FLASH_H, FLASH_W * n, 4), np.uint8)
    for lvl, a in enumerate(FLASH_ALPHAS):
        for y in range(FLASH_H):
            k = 1.0 - 0.18 * (y / (FLASH_H - 1))
            x0 = lvl * FLASH_W
            arr[y, x0:x0 + FLASH_W, 0] = 205
            arr[y, x0:x0 + FLASH_W, 1] = 226
            arr[y, x0:x0 + FLASH_W, 2] = 255
            arr[y, x0:x0 + FLASH_W, 3] = int(a * k)
    img = Image.fromarray(arr, "RGBA")
    out = os.path.join(EXT, "assets/deusex/textures/font/flash.png")
    img.save(out, optimize=True)

    doc = {
        "providers": [
            {
                "type": "bitmap",
                "file": "deusex:font/flash.png",
                "ascent": 297,
                "height": 600,
                "chars": ["".join(chr(FLASH_BASE + l) for l in range(n))],
            }
        ]
    }
    with open(os.path.join(EXT, "assets/deusex/font/flash.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("flash atlas", img.size, os.path.getsize(out), "bytes")


def preview():
    W, H, SC = 480, 270, 3
    base = Image.new("RGB", (W, H), (10, 12, 22))
    d = ImageDraw.Draw(base)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=(int(10 + 26 * k), int(12 + 32 * k), int(24 + 48 * k)))
    d.rectangle([0, H - 22, W, H], fill=(24, 24, 28))
    # far rain streaks
    rng = random.Random(5)
    for _ in range(180):
        x, y = rng.randint(0, W), rng.randint(0, H)
        d.line([(x, y), (x - 2, y + 9)], fill=(52, 62, 84))
    base = base.convert("RGBA")
    scenes = []
    for i, lvl in enumerate([0, 2, 3]):
        frame = base.copy()
        bimg = Image.open(os.path.join(EXT, "assets/deusex/textures/font/bolt.png"))
        bolt = bimg.crop((i * BOLT_W, 0, (i + 1) * BOLT_W, BOLT_H)).resize((80, 160), Image.LANCZOS)
        shift = [-40, -10, 24][i]
        x = W // 2 + shift * 4 - 40
        frame.alpha_composite(bolt, (x, -1))

        fimg = Image.open(os.path.join(EXT, "assets/deusex/textures/font/flash.png"))
        cell = fimg.crop((lvl * FLASH_W, 0, (lvl + 1) * FLASH_W, FLASH_H)).resize((W, H), Image.NEAREST)
        frame = Image.alpha_composite(frame, cell)
        scenes.append(frame.convert("RGB"))

    montage = Image.new("RGB", (W * 3, H))
    for i, sc in enumerate(scenes):
        montage.paste(sc, (W * i, 0))
    montage = montage.resize((W * 3 * 2, H * 2), Image.LANCZOS)
    os.makedirs(os.path.join(ROOT, "preview"), exist_ok=True)
    montage.save(os.path.join(ROOT, "preview/lightning_preview.png"))
    print("preview written")


if __name__ == "__main__":
    build_bolt()
    build_flash()
    preview()
