"""Bake seven distinct attack masks, preserving the original five cells."""
import math
from pathlib import Path
from PIL import Image, ImageDraw

INK = (255, 238, 214, 255)
CELL = 512
SS = 4
CELLS = 7
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "client/src/main/resources/assets/deusexmachina/textures/show/strike_sigils.png"


def canvas():
    return Image.new("RGBA", (CELL * SS, CELL * SS), (0, 0, 0, 0))


def ring(d, r, w):
    c = CELL * SS / 2
    d.ellipse([c - r, c - r, c + r, c + r], outline=INK, width=w)


def arc(d, r, w, a0, a1):
    c = CELL * SS / 2
    d.arc([c - r, c - r, c + r, c + r], a0, a1, fill=INK, width=w)


def line(d, x0, y0, x1, y1, w):
    d.line([(x0, y0), (x1, y1)], fill=INK, width=w)


def polar(cx, cy, r, deg):
    a = math.radians(deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def rune_band(d, r, count):
    c = CELL * SS / 2
    ring(d, 222 * SS, 3 * SS)
    for i in range(count):
        deg = 360.0 * i / count
        base = polar(c, c, r, deg)
        tip = polar(c, c, r + 14 * SS, deg)
        d.line([base, tip], fill=INK, width=3 * SS)
        branch = polar(c, c, r + (14 if i % 2 else 4) * SS, deg + 2)
        middle = polar(c, c, r + 7 * SS, deg)
        d.line([branch, middle], fill=INK, width=3 * SS)
        if i % 3 == 0:
            branch = polar(c, c, r + 14 * SS, deg - 2)
            d.line([branch, middle], fill=INK, width=3 * SS)


def grasp_cell():
    """The binding circle: six shackles on a ring, each dragging a bar toward the trapped centre."""
    im = canvas()
    d = ImageDraw.Draw(im)
    ring(d, 236 * SS, 4 * SS)
    rune_band(d, 200 * SS, 36)
    ring(d, 148 * SS, 4 * SS)
    c = CELL * SS / 2
    for i in range(6):
        deg = 60 * i + 30
        # Shackle: a small circle riding the ring, with its binding bar aimed at the centre.
        sx, sy = polar(c, c, 148 * SS, deg)
        d.ellipse([sx - 20 * SS, sy - 20 * SS, sx + 20 * SS, sy + 20 * SS],
                  outline=INK, width=5 * SS)
        ex, ey = polar(c, c, 56 * SS, deg)
        line(d, sx, sy, ex, ey, 9 * SS)
    ring(d, 46 * SS, 5 * SS)
    # Four clamps that have already closed, pointing the last stretch inward.
    for deg in (45, 135, 225, 315):
        a = math.radians(deg)
        ax, ay = polar(c, c, 118 * SS, deg)
        bx, by = polar(c, c, 62 * SS, deg)
        px = -math.sin(a) * 18 * SS
        py = math.cos(a) * 18 * SS
        d.polygon([(bx, by), (ax + px, ay + py), (ax - px, ay - py)],
                  outline=INK, width=4 * SS)
    return im


def siphon_cell():
    """The blood rite: a central chalice-drop ringed by twelve drops being pulled into it."""
    im = canvas()
    d = ImageDraw.Draw(im)
    ring(d, 236 * SS, 4 * SS)
    rune_band(d, 200 * SS, 36)
    c = CELL * SS / 2
    # The chalice drop at the centre: a circle with a rising spire, the classic rite vessel.
    ring(d, 62 * SS, 5 * SS)
    d.polygon([(c - 44 * SS, c - 34 * SS), (c, c - 128 * SS), (c + 44 * SS, c - 34 * SS)],
              outline=INK, width=5 * SS)
    line(d, c - 44 * SS, c - 34 * SS, c + 44 * SS, c - 34 * SS, 5 * SS)
    # Twelve drops on the ring, each drawn as a small circle with a tail bent toward the centre.
    for i in range(12):
        deg = 30 * i
        dx, dy = polar(c, c, 158 * SS, deg)
        r = 11 * SS
        d.ellipse([dx - r, dy - r, dx + r, dy + r], outline=INK, width=4 * SS)
        tx, ty = polar(c, c, 126 * SS, deg)
        line(d, dx, dy, tx, ty, 4 * SS)
    # Two crescents pulling the whole rite together.
    arc(d, 92 * SS, 4 * SS, 200, 340)
    arc(d, 92 * SS, 4 * SS, 20, 160)
    return im


def barrage_cell():
    """The fragmentation star: a hex core ringed by eight wedge shards on dotted arcs."""
    im = canvas()
    d = ImageDraw.Draw(im)
    ring(d, 236 * SS, 4 * SS)
    rune_band(d, 200 * SS, 36)
    c = CELL * SS / 2
    pts = [polar(c, c, 70 * SS, 60 * i + 30) for i in range(6)]
    d.polygon(pts, outline=INK, width=5 * SS)
    # Eight wedge shards flying outward, each a long thin triangle.
    for i in range(8):
        deg = 45 * i + 22
        tipx, tipy = polar(c, c, 196 * SS, deg)
        for off in (-8, 8):
            bx, by = polar(c, c, 96 * SS, deg + off)
            d.line([(bx, by), (tipx, tipy)], fill=INK, width=4 * SS)
        d.line([polar(c, c, 96 * SS, deg - 8), polar(c, c, 96 * SS, deg + 8)],
               fill=INK, width=4 * SS)
    # Dotted arcs stitch between the shard tips.
    for i in range(8):
        a0 = 45 * i + 34
        arc(d, 176 * SS, 3 * SS, a0, a0 + 27)
    return im


def laser_cell():
    """The crosshair: a beam line through the whole cell, a ringed centre dot and an X."""
    im = canvas()
    d = ImageDraw.Draw(im)
    ring(d, 236 * SS, 4 * SS)
    c = CELL * SS / 2
    # The beam: one unbroken line across the cell, chevroned at both ends.
    line(d, 16 * SS, c, (CELL - 16) * SS, c, 6 * SS)
    for sgn in (1, -1):
        x = c + sgn * 196 * SS
        line(d, x, c - 26 * SS, x + sgn * 34 * SS, c, 5 * SS)
        line(d, x, c + 26 * SS, x + sgn * 34 * SS, c, 5 * SS)
    # Long cardinal ticks cross the outer ring, the aiming hair.
    for deg in (0, 90, 180, 270):
        x0, y0 = polar(c, c, 248 * SS, deg)
        x1, y1 = polar(c, c, 118 * SS, deg)
        line(d, x0, y0, x1, y1, 5 * SS)
    # The X the player breaks out of.
    for deg in (45, 135, 225, 315):
        x0, y0 = polar(c, c, 198 * SS, deg)
        x1, y1 = polar(c, c, 84 * SS, deg)
        line(d, x0, y0, x1, y1, 4 * SS)
    ring(d, 58 * SS, 5 * SS)
    d.ellipse([c - 10 * SS, c - 10 * SS, c + 10 * SS, c + 10 * SS], fill=INK)
    # A short tick collar inside the ring so the cell reads as aimed, not ornamented.
    for i in range(12):
        deg = 30 * i + 15
        x0, y0 = polar(c, c, 168 * SS, deg)
        x1, y1 = polar(c, c, 196 * SS, deg)
        line(d, x0, y0, x1, y1, 4 * SS)
    return im


def vortex_cell():
    im = canvas()
    d = ImageDraw.Draw(im)
    c = CELL * SS / 2
    ring(d, 236 * SS, 4 * SS)
    rune_band(d, 200 * SS, 36)
    for arm in range(3):
        points = []
        for step in range(181):
            t = step / 180
            points.append(polar(c, c, (184 - 150 * t) * SS, arm * 120 + t * 255))
        d.line(points, fill=INK, width=7 * SS, joint="curve")
        tx, ty = points[-1]
        px, py = points[-9]
        angle = math.atan2(ty - py, tx - px)
        backx = tx - math.cos(angle) * 24 * SS
        backy = ty - math.sin(angle) * 24 * SS
        side = 13 * SS
        d.polygon([(tx, ty), (backx - math.sin(angle) * side, backy + math.cos(angle) * side),
                   (backx + math.sin(angle) * side, backy - math.cos(angle) * side)], fill=INK)
    ring(d, 17 * SS, 4 * SS)
    for i in range(6):
        arc(d, 190 * SS, 3 * SS, i * 60 + 12, i * 60 + 40)
    return im


def rupture_cell():
    im = canvas()
    d = ImageDraw.Draw(im)
    c = CELL * SS / 2
    for i in range(8):
        deg = i * 45
        arc(d, 232 * SS, 4 * SS, deg + 8, deg + 37)
        tip = polar(c, c, 246 * SS, deg)
        left = polar(c, c, 166 * SS, deg - 8)
        notch = polar(c, c, 186 * SS, deg + 1)
        right = polar(c, c, 156 * SS, deg + 10)
        d.polygon([left, tip, right, notch], outline=INK, width=5 * SS)
    halves = [
        [(-18, -150), (-148, 0), (-18, 150), (-34, 64), (-6, 20), (-42, -18), (-14, -64)],
        [(18, -150), (148, 0), (18, 150), (2, 64), (30, 20), (-6, -18), (22, -64)],
    ]
    for points in halves:
        d.polygon([(c + x * SS, c + y * SS) for x, y in points], outline=INK, width=6 * SS)
    for side in (-1, 1):
        points = [(c + side * x * SS, c + y * SS)
                  for x, y in ((100, 10), (72, -6), (82, -44), (46, -78))]
        d.line(points, fill=INK, width=4 * SS, joint="curve")
    return im


def preview(atlas):
    size = 256
    image = Image.new("RGBA", (size * CELLS, 620), (12, 10, 19, 255))
    draw = ImageDraw.Draw(image)
    names = ("RED BOLT", "BINDING SIGN", "SOUL SIPHON", "EMBER BARRAGE", "SEAL LANCE",
             "CRIMSON VORTEX", "RIFT ERUPTION")
    palettes = (
        ((255, 26, 18), (209, 56, 255), (255, 15, 10), (255, 97, 13), (255, 143, 26),
         (230, 5, 82), (255, 71, 5)),
        ((255, 219, 173), (204, 115, 255), (255, 71, 56), (255, 153, 51), (255, 245, 209),
         (255, 13, 102), (255, 140, 20)),
    )
    for row, colors in enumerate(palettes):
        y = row * 310
        draw.text((12, y + 10), "LOCK WARNING" if row == 0 else "IMPACT", fill=(181, 175, 196))
        for idx, color in enumerate(colors):
            cell = atlas.crop((idx * CELL, 0, (idx + 1) * CELL, CELL)).resize((size, size), Image.LANCZOS)
            tinted = Image.new("RGBA", (size, size), color + (255,))
            tinted.putalpha(cell.getchannel("A"))
            image.alpha_composite(tinted, (idx * size, y + 35))
            draw.text((idx * size + 12, y + 294), names[idx], fill=color)
    path = ROOT / "strike_sigils_preview.png"
    image.convert("RGB").save(path)
    print("wrote %s %s" % (path, image.size))


def main():
    bolt = Image.open(ROOT / "art/strike_sigil_source.png").convert("RGBA")
    assert bolt.size == (CELL, CELL)
    atlas = Image.new("RGBA", (CELL * CELLS, CELL), (0, 0, 0, 0))
    atlas.paste(bolt, (0, 0))
    for idx, fn in enumerate((grasp_cell, siphon_cell, barrage_cell, laser_cell,
                              vortex_cell, rupture_cell), start=1):
        alpha = fn().getchannel("A").resize((CELL, CELL), Image.LANCZOS)
        cell = Image.new("RGBA", (CELL, CELL), INK)
        cell.putalpha(alpha)
        atlas.paste(cell, (idx * CELL, 0))
    atlas.save(OUT)
    print("wrote %s %s" % (OUT, atlas.size))
    preview(atlas)


if __name__ == "__main__":
    main()
