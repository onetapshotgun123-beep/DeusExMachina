"""Render what a player actually sees for the red flash and the drop, from shipped assets.

The numbers that turn a function into pixels all come out of deus/mcsrc, not out of a guess:

  BitmapProvider.load / SheetGlyphInfo   advance = int(0.5 + inkWidth*height/cell_h) + 1,
                                         top = 7 - ascent, drawn = cell_w * height / cell_h.
                                         hudview.load_font implements that, so the sky preview and
                                         the actionbar preview share one font engine.
  RenderText + TextDisplayRenderer       1 font unit = 0.025 blocks * transformation scale, the
                                         line block is centred on the entity, and a glyph reaches
                                         ascent+3 units above it and height-ascent-3 below.
  Gui.renderTitle                        translate(guiWidth/2, guiHeight/2), then scale(4,4), then
                                         draw at (-width/2, -10) with dropShadow. A title glyph is
                                         FOUR times an actionbar glyph - the number that made the
                                         intro heart measure right against the recording.
  Gui layer order                        OVERLAY_MESSAGE (the actionbar) is registered before
                                         TITLE, so a veil painted as a title sits ON TOP of the
                                         lyrics. That is what caps how strong the wash can be.
  Font.drawStringWithBackdrop            the backdrop rect is (x-2,y-2)..(x+width/2+2,y+11) and the
                                         veil string's width is NEGATIVE (-3), so that rect is a
                                         3x13 smear: the wash is carried entirely by the alpha of
                                         red_lv.png, not by any backdrop.
  DustParticleBase                       quad = 0.2*0.75*scale blocks, lifetime =
                                         max(int(8/rand(0.2..1.0))*scale, 1), velocity *= 0.1 then
                                         friction 0.96 per tick, no gravity, opaque, size ramping
                                         in over lifetime/32 ticks.
  ParticleCommand / ClientLevel          each spawn is anchor + nextGaussian()*delta per axis and
                                         each velocity component is nextGaussian()*speed.

    python skyview.py flash    vid21/flash_strip*.png, flash_strip_yaw+030.png, veil_levels.png,
                               flash_pitch*.png, flash_yaw*.png, flash_fallback.png, veil_hud.png,
                               bands_*.png, rain_vs_reference.png
    python skyview.py burst    vid21/burst_strip.png

The rain overlay comes from LevelRenderer.renderSnowAndRain, which is in the shipped sources: a
(2l+1)^2 box of one-block-wide vertical sheets, each turned to face the camera by the rainSizeX/Z
unit vectors, alpha ((1 - (d/l)^2) * 0.5 + 0.5) * rainLevel, depthMask off at the default fancy
setting so the sheets accumulate. compare_rain() scores my composites and the user's 1.0.18
recording on the same three horizontal bands, which is the only way to tell "the sky is red" from
"a red rectangle was drawn somewhere".
"""

import json
import math
import os
import re
import sys
import glob

import numpy as np
from PIL import Image, ImageDraw

import hudview
import mclog

ROOT = os.path.dirname(os.path.abspath(__file__))
EXT = os.environ.get("DEUS_EXT") or os.path.join(ROOT, "extracted")
FUN = os.path.join(EXT, "data", "deusex", "function")
OUT = os.path.join(ROOT, "vid21")

W, H = 1280, 720
FOV_H = 70.0
TAN_H = math.tan(math.radians(FOV_H / 2.0))
TAN_V = TAN_H * H / W

# the recording is 1920x1080 at gui scale 2, so one GUI unit is two real pixels and this preview's
# 1280x720 frame stands for 960x540 GUI units
GUI_W, GUI_H = 960, 540
TITLE_SCALE = 4.0                       # Gui.renderTitle: pose().scale(4.0F, 4.0F, 4.0F)
PPU = W / GUI_W                         # world pixels per GUI unit
# The same pose draws the subtitle, in a sibling push: scale(2.0F) and y=5 instead of scale(4.0F) and
# y=-10 (Gui.java:371-376). Half the magnification is why a veil moved from the title to the subtitle
# has to be written as two cells to cover what one cell covered there.
SUBTITLE_SCALE = 2.0
TITLE_Y, SUBTITLE_Y = -10.0, 5.0


def glyph(font_name, cp):
    """One shipped glyph, with the metrics hudview measures for the actionbar."""
    return hudview.font("deusex:" + font_name)["glyphs"].get(cp)


def adv(font_name, cp):
    return hudview.advance("deusex:" + font_name, cp)


# ------------------------------------------------------------------ shipped commands
# The spawn lines are macros: `$execute rotated $(yaw) 0 ...`, and /execute rotated takes
# <yaw> <pitch> - the same order as the entity Rotation NBT - so the panel is placed on the
# player's own heading (flash_rand stores their Rotation[0] plus a -30..30 jitter) with the pitch
# flattened onto the horizon. billboard:"vertical" then turns the quad to face the camera, so what
# the yaw really decides is only *where in the view* the panel lands: dead ahead at jitter 0, up to
# 30 deg off to the side at the extremes, and never behind the player or under the floor. The
# 1.0.19-1.0.21 builds read that argument order backwards and shipped `rotated 0 ~`, which pinned
# the yaw to due south and inherited the camera pitch: the panel was somewhere else, and whatever
# the player saw was the sky.
SPAWN = re.compile(
    r"^\$execute rotated \$\(yaw\) 0 if score #sr deusex matches (\d+) (if|unless) loaded "
    r"\^ \^ \^(\d+) run summon minecraft:text_display \^ \^ \^(\d+) (\{.*\})$")

# summon anchors on the player's *feet* (at @s), and the camera sits a full block and a bit above
# that, so every height below is measured from the eye and the anchor has to be pushed down first.
EYE = 1.62


def parse_flash():
    """The shipped 24 spawn lines as [(variant, layer, gate, distance, glyph, opacity, transform)]."""
    out = []
    txt = open(os.path.join(FUN, "flash_spawn.mcfunction"), encoding="utf-8").read()
    for line in txt.splitlines():
        m = SPAWN.match(line.strip())
        if not m:
            continue
        var, gate, aim, dist, body = (int(m.group(1)), m.group(2), float(m.group(3)),
                                      float(m.group(4)), m.group(5))
        # every layer of one variant tests the chunk its *farthest* panel needs, and then plants
        # itself where that layer belongs: `if loaded ^^^54` puts the glow at 54 and the core and
        # flare nearer inside it, and `unless loaded ^^^54` - that chunk is gone - brings all three
        # in to 30/26/24, inside a 2 chunk ticking area.
        assert dist <= aim, "a layer is summoned outside the chunk the line tested"
        if gate == "unless" and dist == aim:
            raise AssertionError("the fallback still plants a panel in the chunk it says is gone")
        tags = re.findall(r'"(deusex_\w+)"', body)
        comp = json.loads(re.search(r"text:'(\{.*?\})'", body).group(1))
        tx, ty = [float(v) for v in re.search(r"translation:\[([-0-9.]+)f,([-0-9.]+)f,0\.0f\]",
                                              body).group(1, 2)]
        sx, sy = [float(v) for v in re.search(r"scale:\[([\d.]+)f,([\d.]+)f", body).group(1, 2)]
        out.append({"var": var, "gate": gate, "dist": dist, "glyph": comp["text"],
                    "font": comp["font"].split(":")[1],
                    "layer": [t for t in tags if t != "deusex_flash"][0],
                    "op": int(re.search(r"text_opacity:(-?\d+)b", body).group(1)) % 256,
                    "see_through": re.search(r"see_through:(\d)b", body).group(1),
                    "tx": tx, "ty": ty, "sx": sx, "sy": sy})
    assert out, "no flash_spawn line parsed - the shipped form is not what this reads"
    return out


def load_scores():
    txt = open(os.path.join(FUN, "load.mcfunction"), encoding="utf-8").read()
    return {k: int(v) for k, v in
            re.findall(r"scoreboard players set (#\S+) deusex (-?\d+)", txt)}


def tick_order(*want):
    """The named functions, in the order tick.mcfunction actually calls them."""
    txt = open(os.path.join(FUN, "tick.mcfunction"), encoding="utf-8").read()
    seen, out = set(), []
    for m in re.finditer(r"function deusex:(\w+)", txt):
        if m.group(1) in want and m.group(1) not in seen:
            seen.add(m.group(1))
            out.append(m.group(1))
    return out


def held_base():
    """The veil level the song parks on between flashes, read from opening_burst.

    1.0.18 held its red sky for the whole song; this build reproduces it with #washbase, so any
    render of "what the player sees" has to use that number rather than 0.
    """
    txt = open(os.path.join(FUN, "opening_burst.mcfunction"), encoding="utf-8").read()
    m = re.search(r"^scoreboard players set #washbase deusex (\d+)$", txt, re.M)
    assert m, "opening_burst never sets #washbase"
    return int(m.group(1))


def wash_ceiling():
    """The veil level a flash spikes to, read from load.mcfunction's #washmax.

    wash_draw paints #tint*#wash/#washmax, so the cell that actually lands on screen is this number
    only while #tint equals it; the validator checks that equality, so a render may take it on faith.
    """
    txt = open(os.path.join(FUN, "load.mcfunction"), encoding="utf-8").read()
    m = re.search(r"^scoreboard players set #washmax deusex (\d+)$", txt, re.M)
    assert m, "load.mcfunction never sets #washmax"
    return int(m.group(1))


def flash_seq():
    """Replay the shipped tick loop through one flash: per-layer opacity and wash level.

    #flashd starts at 0 so flash_begin fires on the first tick instead of waiting out a roll the
    replay cannot make; every later number is the functions' own arithmetic. flash_frame writes one
    opacity row per layer per tick, and the three layers fade on different curves, so the alphas are
    keyed by tag instead of flattened to the first one the log happened to hold.

    #wash starts at 0 with the burst's base already raised, which is the order the game sees: the
    flash fires on the same tick the opening hands the screen over.
    """
    base = held_base()
    S = load_scores()
    S.update({"#state": 1, "#cstate": 0, "#ostage": 4, "#lead": 0,
              "#fframe": 0, "#flashd": 0, "#wash": 0, "#washbase": base,
              "#washc": 0, "#wlast": 0, "#wlv": 0})
    order = tick_order("wash_tick", "flash_tick", "wash_draw")
    rows = []
    for t in range(90):
        log = []
        for name in order:
            mclog.run(name, S, log)
        a = {}
        for k, _, tag, v in log:
            if k == "opacity":
                a[tag] = v
        rows.append({"t": t, "alphas": a, "frame": S["#fframe"], "wash": S["#wash"],
                     "lv": S.get("#lv"),
                     "repaint": any(k == "call" and v == "tint_refresh" for k, _, v, _ in log)})
    return rows


# ------------------------------------------------------------------ GUI title layer
MACRO = re.compile(r"^\$title @a (title|subtitle) (.*)$")


def title_items(fname, subs, slot="title"):
    """The components of a shipped `$title @a <slot>` macro line, as [(font, codepoint)].

    `$(rc)` and `$(burst)` are storage placeholders lv_char and heart_burst_frame wrote earlier in
    the same tick, so the caller hands them over and the string here stays the shipped one.
    """
    txt = open(os.path.join(FUN, fname + ".mcfunction"), encoding="utf-8").read()
    line = None
    for l in txt.splitlines():
        m = MACRO.match(l.strip())
        if m and m.group(1) == slot:
            line = m
            break
    assert line, "no $title @a %s line in %s" % (slot, fname)
    raw = line.group(2)
    for k, v in subs.items():
        raw = raw.replace("$(%s)" % k, v)
    items = []

    def walk(node):
        if isinstance(node, list):
            for n in node:
                walk(n)
            return
        if isinstance(node, str):               # `["", {..}]` - a bare component is plain text
            for ch in node:
                items.append(("default", ord(ch)))
            return
        for ch in node.get("text", ""):
            items.append((node.get("font", "minecraft:default").split(":")[-1], ord(ch)))
        walk(node.get("extra", []))

    walk(json.loads(raw))
    return items


def title_quads(items, scale=TITLE_SCALE, y_off=TITLE_Y):
    """Where each inked glyph of a title string lands, in world pixels, plus the string width.

    Two spaces meet here, which is why the veil and the burst need this model instead of a guess:
    the string lays itself out in font units, Gui.renderTitle multiplies that by `scale` to get GUI
    units, and this frame stands for GUI units at PPU pixels each. `scale`/`y_off` are the two
    numbers that differ between the title slot (4, -10) and the subtitle slot (2, 5).
    """
    tpu = PPU * scale
    width = sum(adv(fn, cp) for fn, cp in items)
    pen = GUI_W / 2.0 + scale * int(-width / 2.0)
    line_y = GUI_H / 2.0 + y_off * scale
    out = []
    for fn, cp in items:
        g = glyph(fn, cp)
        if g is not None:
            out.append((g["cell"], PPU * pen, PPU * (line_y + scale * g["top"]),
                        tpu * g["draw"], tpu * g["height"]))
        pen += scale * adv(fn, cp)
    return out, width


def subtitle_quads(items):
    return title_quads(items, SUBTITLE_SCALE, SUBTITLE_Y)


def _blit(dst, cell, x0, y0, w, h, mul=1.0):
    """Alpha-composite one glyph quad into the world frame. Returns the alpha it laid down."""
    sx0, sy0 = max(0, int(math.floor(x0))), max(0, int(math.floor(y0)))
    sx1, sy1 = min(W, int(math.ceil(x0 + w))), min(H, int(math.ceil(y0 + h)))
    if sx1 <= sx0 or sy1 <= sy0 or w <= 0 or h <= 0:
        return np.zeros((0, 0), np.float32)
    tile = Image.fromarray(np.clip(cell, 0, 255).astype(np.uint8), "RGBA").resize(
        (sx1 - sx0, sy1 - sy0), Image.LANCZOS)
    src = np.asarray(tile, np.float32)
    al = src[..., 3:4] / 255.0
    reg = dst[sy0:sy1, sx0:sx1]
    reg[:] = src[..., :3] * mul * al + reg * (1.0 - al)
    return al[..., 0]


def draw_title(dst, items, slot="title"):
    """Paint a title string the way the title layer does: the shadow pass for the whole string, then
    the ink pass for the whole string. Font.draw runs renderText twice, the second one after a
    SHADOW_OFFSET translate that is z-only (Font.java:196-204), so the two copies of a cell overlap
    exactly and only brighten each other's edges - and a glyph later in the string is inked over the
    shadow of every glyph before it, which is what lets the blast sit on top of the veil."""
    laid = np.zeros((H, W), np.float32)
    quads = (subtitle_quads if slot == "subtitle" else title_quads)(items)[0]
    for cell, x, y, w, h in quads:
        _blit(dst, cell, x, y, w, h, mul=0.25)
    for cell, x, y, w, h in quads:
        al = _blit(dst, cell, x, y, w, h)
        if al.size:
            reg = laid[int(max(0, y)):int(min(H, y + h)), int(max(0, x)):int(min(W, x + w))]
            reg[:] = np.maximum(reg, al[:reg.shape[0], :reg.shape[1]])
    return laid


def veil_alpha(items, slot="title"):
    """The mean and peak alpha the layer really lays over the frame - what visible means here."""
    laid = draw_title(np.zeros((H, W, 3), np.float32), items, slot)
    return float(laid.mean()), float(laid.max())


# ------------------------------------------------------------------ camera
def backdrop(pitch, seed=7, night=False, rain=False):
    """The world the flash is drawn onto.

    Both a day and a night frame matter. The panel is forced fullbright so it does not change with
    the time of day, but a red veil over a bright sky and over a dark one are different amounts of
    red, and the player only ever sees one of them.

    `rain` applies FogRenderer's own weather multipliers - fogRed and fogGreen by (1 - rain * 0.5),
    fogBlue by (1 - rain * 0.4), all at rain level 1.0 - to the whole frame. That is the source's
    number for what the world looks like while it is raining, and it matters here because the burst
    forces the weather: a red layer over a dimmed blue world and over a bright one are not the same
    red. SkyRenderer itself is not in this drop of mcsrc, so the multipliers are applied to the sky
    band as well as the terrain, which is what the fog does to everything within its range.

    pitch here is the camera's elevation in degrees, positive looking up - Minecraft's own pitch is
    its negation, so "looking at the ground" is a negative number.
    """
    yy = np.mgrid[0:H, 0:W][0].astype(np.float32)
    elev = np.degrees(np.arctan((H * 0.5 - yy) * TAN_V / (H * 0.5))) + pitch
    if night:
        top, low, ground = (8, 12, 30), (26, 34, 58), (10, 14, 16)
    else:
        top, low, ground = (96, 140, 196), (176, 196, 214), (48, 62, 44)
    t = np.clip(elev / 45.0, 0, 1)[..., None]
    a = np.array(low, np.float32) + (np.array(top, np.float32) - np.array(low, np.float32)) * t
    a = np.where(elev[..., None] < 0, np.array(ground, np.float32), a)
    if rain:
        a = a * np.array([0.5, 0.5, 0.6], np.float32)
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")
    d = ImageDraw.Draw(img)
    y0 = H * 0.5 + math.tan(math.radians(pitch)) * (H * 0.5) / TAN_V
    rng = np.random.default_rng(seed)
    if night:
        for _ in range(220):
            b = int(rng.integers(90, 235))
            d.point((rng.uniform(0, W), rng.uniform(0, max(2, y0 - 2))), fill=(b, b, b))
    for x in range(-10, W + 10, 26):
        h = 14 + int(rng.integers(0, 34))
        d.rectangle([x, y0 - h, x + 34, y0 + 10], fill=(16, 24, 18) if night else (26, 40, 24))
    return np.asarray(img, np.float32)


def panel_geometry(e, lay):
    """The quad in the billboard's own frame: lateral x of the left edge, ink width, and the
    top/bottom heights, all in metres - heights above the *eye*, since the anchor is at the feet.

    transformation translation is in blocks and is applied after the scale, so tx/ty are offsets as
    written, while the glyph box is font units at 0.025 blocks each times the scale.
    """
    g = lay[e["glyph"]]
    return (e["tx"] + 0.025 * e["sx"] * (-g["advance"] / 2.0),   # alignment "center"
            0.025 * e["sx"] * g["draw"],
            e["ty"] - EYE + 0.025 * e["sy"] * (10.0 - g["top"]),
            e["ty"] - EYE + 0.025 * e["sy"] * (10.0 - g["top"] - g["height"]))


def draw_panel(dst, e, alpha, pitch, lay, yaw=0.0):
    """Composite one layer of the panel and report how much of the frame it really paints.

    `pitch` is the camera's elevation (positive looking up) and `yaw` the angle between where the
    camera points and the heading the panel was placed on - flash_rand makes that the player's own
    yaw plus a -30..30 roll, so it is never more than a third of the view off centre.

    `billboard:"vertical"` means the quad always turns to face the camera, upright, so its shape
    never foreshortens: only its *position* in the view moves with the yaw. Every pixel is
    un-projected back onto the quad plane analytically rather than drawn as a polygon, because the
    question this answers is whether the panel's own edge lands inside the view - a red rectangle
    with a visible border is the thing that looks like a decal and not like a sky.
    """
    cell = lay[e["glyph"]]["cell"]
    ch, cw = cell.shape[:2]
    x_left, bw, y_top, y_bot = panel_geometry(e, lay)
    a = math.radians(pitch)
    ca, sa = math.cos(a), math.sin(a)
    t_ = math.radians(yaw)
    ct, st = math.cos(t_), math.sin(t_)
    d = e["dist"]

    # the anchor, in the camera's *horizontal* frame: `d` blocks along the panel's heading, which is
    # yawed `t_` off the camera's, at the player's feet. Heights are carried separately, as the quad
    # offsets below, because the anchor point itself is the entity position and not the ink.
    ax, az = -d * st, d * ct
    lat0, up0, nrm0 = (ct, 0.0, st), (0.0, 1.0, 0.0), (-st, 0.0, ct)
    # ... then pitched into the view frame. rot() is the rotation about the camera's lateral axis.
    def rot(p):
        x, y, z = p
        return (x, y * ca - z * sa, y * sa + z * ca)
    anch, lat, up, nrm = rot((ax, 0.0, az)), rot(lat0), rot(up0), rot(nrm0)

    def screen(p):
        if p[2] <= 0.05:
            return None
        return (W * 0.5 + p[0] / p[2] * (W * 0.5) / TAN_H,
                H * 0.5 - p[1] / p[2] * (H * 0.5) / TAN_V)

    corners = [rot((ax + xx * lat0[0], yy, az + xx * lat0[2]))
               for xx, yy in ((x_left, y_top), (x_left + bw, y_top),
                              (x_left, y_bot), (x_left + bw, y_bot))]
    pts = [screen(p) for p in corners]
    if all(p is None for p in pts):
        return "BEHIND the camera (yaw %+3.0f pitch %+3.0f)" % (yaw, pitch), 0.0, 0.0
    xs = [p[0] for p in pts if p]
    ys = [p[1] for p in pts if p]
    horizon = H * 0.5 + math.tan(a) * (H * 0.5) / TAN_V
    x0, x1 = max(0, int(math.floor(min(xs)))), min(W, int(math.ceil(max(xs))))
    y0, y1 = max(0, int(math.floor(min(ys)))), min(H, int(math.ceil(min(max(ys), horizon))))
    span = "elev %+.0f..%+.0f deg, bearing %+3.0f" % (
        math.degrees(math.atan2(y_bot, d)), math.degrees(math.atan2(y_top, d)), yaw)
    if x1 <= x0 or y1 <= y0:
        where = ("below the terrain line" if min(ys) > horizon else
                 "above the top of the view" if max(ys) < 0 else
                 "beside the view")
        return ("OUT of the frame, %s (%s)" % (where, span)), 0.0, 0.0

    py, px = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    u = -(py - H * 0.5) * TAN_V / (H * 0.5)
    r = (px - W * 0.5) * TAN_H / (W * 0.5)
    denom = r * nrm[0] + u * nrm[1] + nrm[2]
    adist = anch[0] * nrm[0] + anch[1] * nrm[1] + anch[2] * nrm[2]
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(np.abs(denom) > 1e-6, adist / denom, np.inf)
    dx = t * r - anch[0]
    dy = t * u - anch[1]
    dz = t - anch[2]
    s = dx * lat[0] + dy * lat[1] + dz * lat[2]
    hgt = dx * up[0] + dy * up[1] + dz * up[2]
    v = (s - x_left) / bw
    w = (y_top - hgt) / (y_top - y_bot)
    inside = (v >= 0) & (v <= 1) & (w >= 0) & (w <= 1) & (t > 0)

    fx = np.clip(v * (cw - 1), 0, cw - 1)
    fy = np.clip(w * (ch - 1), 0, ch - 1)
    x0i, y0i = np.floor(fx).astype(int), np.floor(fy).astype(int)
    x1i, y1i = np.minimum(x0i + 1, cw - 1), np.minimum(y0i + 1, ch - 1)
    ax_, ay_ = (fx - x0i)[..., None], (fy - y0i)[..., None]
    tex = (cell[y0i, x0i] * (1 - ax_) + cell[y0i, x1i] * ax_) * (1 - ay_) \
        + (cell[y1i, x0i] * (1 - ax_) + cell[y1i, x1i] * ax_) * ay_
    al = tex[..., 3:4] / 255.0 * (alpha / 255.0) * inside[..., None]
    reg = dst[y0:y1, x0:x1]
    reg[:] = tex[..., :3] * al + reg * (1.0 - al)
    cov = float(inside.mean()) * (x1 - x0) * (y1 - y0) / float(W * H)
    return ("%s v%d %-13s y %.0f..%.0f x %.0f..%.0f a%-4d %2d%% of frame (%s)"
            % (e["gate"], e["var"], e["layer"], max(0, min(ys)), min(H, max(ys)),
               max(0, min(xs)), min(W, max(xs)), alpha, int(cov * 100), span),
            float(al[..., 0].mean()), cov)


def lay_of(name):
    return {chr(cp): g for cp, g in hudview.font("deusex:" + name)["glyphs"].items()}




# ------------------------------------------------------------------ the blood rain
RAIN_SHEET = None


def rain_sheet():
    """The environment/rain.png the client will actually bind: 32x128, sampled NEAREST with GL_REPEAT.

    SimpleTexture.doLoad takes blur and clamp from a .png.mcmeta and defaults both to false, and
    neither this pack nor 1.0.18 ships a rain.png.mcmeta, so the sheet wraps. The wrap is the whole
    trick: renderSnowAndRain gives each sheet a v coordinate of (block y) * 0.25, which runs past
    the bottom of the texture eleven times over, and the repeat folds the four 32-row frames back
    onto themselves down the length of the falling water.

    Since 1.0.23 the pack ships no override, so what the client binds is vanilla's own sheet, and the
    renderer has to model that. The colour is vanilla's - near white with a blue cast, because
    LevelRenderer.renderSnowAndRain writes `.setColor(1,1,1,alpha)` and the sheet is the only hue
    there is. The alpha map comes from backup/vanilla_overrides/rain_red.png, the sheet this pack used
    to ship: same 32x128, same streak layout, same coverage, so the density the veil was calibrated
    against has not moved and only the hue has.
    """
    global RAIN_SHEET
    if RAIN_SHEET is None:
        path = os.path.join(EXT, "assets", "minecraft", "textures", "environment", "rain.png")
        if os.path.isfile(path):
            RAIN_SHEET = np.asarray(Image.open(path).convert("RGBA"), np.float32)
        else:
            src = os.path.join(ROOT, "backup", "vanilla_overrides", "rain_red.png")
            old = np.asarray(Image.open(src).convert("RGBA"), np.float32)
            RAIN_SHEET = np.dstack([np.full(old.shape[:2], c, np.float32)
                                    for c in (198.0, 205.0, 214.0)] + [old[..., 3]])
            print("rain: no override in the pack, drawing vanilla's white sheet "
                  "(alpha map from %s)" % os.path.relpath(src, ROOT))
    return RAIN_SHEET


def draw_weather(dst, tick=0, pitch=0.0, night=False, strength=1.0, l=10):
    """Rain the way the client really draws it, read out of LevelRenderer.renderSnowAndRain.

    Not a screen overlay. One vertical billboard per block column in a (2l+1)^2 box around the eye
    - l is 10 on fancy graphics and 5 on fast, so the density halves with the graphics setting -
    each sheet one block wide and from the ground up to eye block + l. The +-d0/d1 half-offsets
    come from rainSizeX/rainSizeZ, which the renderer's own constructor fills with the unit vector
    *perpendicular* to the column, so every sheet turns to face the camera. That is what makes rain
    a canopy of overlapping streaks instead of wallpaper, and it is why the one-tile-per-pixel
    model this function replaced understated the effect by more than an order of magnitude.

    Per sheet: v = f4 + (k2 - block y) * 0.25 with f4 the per-column scroll phase, u across the
    width; alpha = ((1 - (dist/l)^2) * 0.5 + 0.5) * rainLevel, so 1.0 at the eye and 0.5 at the
    edge of the box; and the sheets do not occlude one another, because depthMask is
    Minecraft.useShaderTransparency() - false at the default fancy setting - so their alphas
    accumulate. The centre column is skipped: vanilla divides by its distance to get d0/d1 and gets
    a NaN, so it draws nothing.

    Only `light` is not read from source. The vertex carries getLightColor at the column top, and
    the sky light under rain is dimmed in LightTexture, which this drop of mcsrc does not ship, so
    the multiplier is the one number here that is calibrated rather than derived.
    """
    sheet = rain_sheet()
    sh, sw = sheet.shape[:2]
    a = math.radians(pitch)
    ca, sa = math.cos(a), math.sin(a)
    light = 0.18 if night else 0.72
    k2 = int(math.floor(EYE)) + l                 # block y of the top of every sheet
    j2 = max(0, int(math.floor(EYE)) - l)         # ... and of the bottom, clamped to the ground
    top, bot = k2 - EYE, j2 - EYE
    rng = np.random.default_rng(4021 + tick)
    yy, xx = np.mgrid[0:H, 0:W]
    tanx = (xx - W * 0.5) * TAN_H / (W * 0.5)
    tany = -(yy - H * 0.5) * TAN_V / (H * 0.5)
    laid = np.zeros((H, W), np.float32)
    n = 0

    def view(p):
        x, y, z = p
        return (x, y * ca - z * sa, y * sa + z * ca)

    for j1 in range(-l, l + 1):
        for k1 in range(-l, l + 1):
            dist = math.hypot(k1, j1)
            if dist == 0.0:
                continue
            f6 = dist / l
            col_a = ((1.0 - f6 * f6) * 0.5 + 0.5) * strength
            if col_a <= 0.01:
                continue
            d0, d1 = -j1 / (2.0 * dist), k1 / (2.0 * dist)
            f4 = float(rng.uniform(-32.0, 0.0))
            corners = [view((k1 - d0, top, j1 - d1)), view((k1 + d0, top, j1 + d1)),
                       view((k1 + d0, bot, j1 + d1)), view((k1 - d0, bot, j1 - d1))]
            near = [(cx, cy, cz) for cx, cy, cz in corners if cz > 0.05]
            if not near:
                continue
            if len(near) == 4:
                pts = [(W * 0.5 + cx / cz * (W * 0.5) / TAN_H,
                        H * 0.5 - cy / cz * (H * 0.5) / TAN_V) for cx, cy, cz in near]
                x0, x1 = max(0, int(min(p[0] for p in pts))), min(W, int(max(p[0] for p in pts)) + 1)
                y0, y1 = max(0, int(min(p[1] for p in pts))), min(H, int(max(p[1] for p in pts)) + 1)
            else:
                x0, y0, x1, y1 = 0, 0, W, H      # straddles the near plane: it runs off the frame
            if x1 <= x0 or y1 <= y0:
                continue
            r_ = tanx[y0:y1, x0:x1]
            u_ = tany[y0:y1, x0:x1]
            # The sheet's own frame, in view space: e is the u=0 -> u=1 edge, up_v the world up.
            ax_, ay_, az_ = corners[0]
            ex, ey, ez = (corners[1][0] - corners[0][0], corners[1][1] - corners[0][1],
                          corners[1][2] - corners[0][2])
            upx, upy, upz = 0.0, ca, sa
            nx, ny, nz = ey * upz - ez * upy, ez * upx - ex * upz, ex * upy - ey * upx
            denom = r_ * nx + u_ * ny + nz
            adist = ax_ * nx + ay_ * ny + az_ * nz
            with np.errstate(divide="ignore", invalid="ignore"):
                # rays that miss the sheet's plane carry t = inf, and inf * 0 is nan; `inside`
                # throws all of them away, so the arithmetic is allowed to be undefined here.
                t = np.where(np.abs(denom) > 1e-6, adist / denom, np.inf)
                hx, hy, hz = t * r_, t * u_, t
                s = ((hx - ax_) * ex + (hy - ay_) * ey + (hz - az_) * ez) / (ex * ex + ey * ey + ez * ez)
                hup = (hx - ax_) * upx + (hy - ay_) * upy + (hz - az_) * upz
                inside = (t > 0.0) & (s >= 0.0) & (s <= 1.0) & (hup >= bot - top) & (hup <= 0.0)
                yrel = hy * upy + hz * upz            # world-relative height of the hit
                vv = np.mod(f4 + (k2 - (yrel + EYE)) * 0.25, 1.0)
            if not inside.any():
                continue
            cix = np.clip(np.floor(np.clip(s, 0.0, 1.0 - 1e-6) * sw), 0, sw - 1).astype(np.int32)
            rix = np.clip(np.floor(vv * sh), 0, sh - 1).astype(np.int32)
            tex = sheet[rix, cix]
            al = np.where(inside, tex[..., 3] / 255.0 * col_a, 0.0)
            reg = dst[y0:y1, x0:x1]
            rgb = np.clip(tex[..., :3] * light, 0, 255)
            reg[:] = rgb * al[..., None] + reg * (1.0 - al[..., None])
            laid[y0:y1, x0:x1] = np.maximum(laid[y0:y1, x0:x1], al)
            n += 1
    return n, float(laid.mean()), float((laid > 0.02).mean())


def band_redness(a):
    """(sky, horizon, ground) redness of a frame, the same three bands measured off vid18."""
    h = a.shape[0]
    out = []
    for y0, y1 in ((0, int(.15 * h)), (int(.35 * h), int(.5 * h)), (int(.62 * h), int(.85 * h))):
        b = a[y0:y1]
        out.append(float((b[..., 0] - (b[..., 1] + b[..., 2]) / 2.0).mean()))
    return out


REFERENCE = [("1.0.18 quiet", "v_0100.png", (23.1, 20.3, 30.7)),
             ("1.0.18 flash", "v_0158.png", (25.4, 28.7, 29.0)),
             ("1.0.18 burst", "v_0050.png", (114.4, 113.7, 114.1))]


def rain_timeline():
    """The sky band of every frame in the reference recording, ten frames at a time.

    This is the measurement that says where 1.0.18's red actually comes from. The frames before the
    drop sit deep in the negative - a plain blue Minecraft sky - and the frames after it step to a
    flat +20 that holds for the rest of the song and only leaves when the ending runs. Nothing in
    the pack changes between those two states except `weather rain 1000000`: its own per-flash veil
    scores were dead code (hud_sky writes storage key `sk` and no draw in that jar reads $(sk)), so
    the persistent red the user is asking for is the rain overlay, not a tint and not the panel.
    """
    fs = sorted(glob.glob(os.path.join(ROOT, "vid18", "v_*.png")))
    if not fs:
        return "vid18 frames not found"
    prof = []
    for i in range(0, len(fs), 10):
        vals = []
        for f in fs[i:i + 10]:
            a = np.asarray(Image.open(f).convert("RGB").resize((160, 90)), np.float32)
            vals.append(band_redness(a)[0])
        prof.append("%d:%+.0f" % (i, float(np.median(vals))))
    return " ".join(prof)


def compare_rain():
    """My composite against the user's own 1.0.18 frames, band by band.

    Read the first pair of rows as the claim this file exists to check. "plain sky" is what
    1.0.19 through 1.0.21 showed - the user's "the sky is stay normal", and its sky band is deep in
    the negative, the colour of a clear Minecraft afternoon. "rain only" is that same world with
    `weather rain 1000000` in force and nothing else: since 1.0.23 the pack ships no
    assets/minecraft override, so the drops are vanilla's own near-white sheet. That row is the
    fix for "my friend's normal rain turned red" - a rainy overworld outside the event is plain
    Minecraft, because a resource-pack texture cannot be conditioned on a scoreboard.

    The held row is the one this file exists to check. 1.0.18's sky band steps from -65 to a flat
    +20 and stays there for the whole 60 s of song, and the only thing in that jar that could hold
    it - hud_sky - writes a storage key nothing reads; its visible red came from the rain.png
    override this pack no longer ships. So the held level is not a copy of 1.0.18's code, it is a
    copy of its picture: opening_burst raises #washbase, wash_tick walks the veil up to it and
    refuses to drain past it, and closing_start takes it to 0. That number landing on the reference
    plateau is what "the sky is red" has to mean for this to be fixed.

    "held lv6" is the state the song sits in from the drop to the ending. Nothing is drawn into the
    air any more: 1.0.26 retired the dust motes, which were a second, coarser rain laid over the
    real one and had no part in the picture this build is measured against.

    "rain + flash" over-shoots 1.0.18's own flashes on purpose: that build had no veil during the
    song at all, so its panel was the whole blink and the screen barely moved. The complaint was
    never that the flashes were too subtle.
    """
    os.makedirs(OUT, exist_ok=True)
    panels = parse_flash()
    lays = {}
    for name in ("skyglow", "skyred"):
        lays.update(lay_of(name))
    group = layers_for(panels, 0)
    base = held_base()
    ceil = wash_ceiling()
    # (label, weather, veil level, flash panel lit, extra title items). The flash row paints
    # #washmax, three cells above the held floor since 1.0.30, so a blink is a brightening that
    # settles back into a sky that stayed red rather than a fall to plain grey and back.
    rows = []
    for tag, weather, veil, lit, extra in (
            ("plain sky", False, 0, False, None),
            ("rain only", True, 0, False, None),
            ("held lv%d" % base, True, base, False, None),
            ("rain + flash", True, ceil, True, None),
            ("rain + burst", True, base, False,
             title_items("title_red_burst", {"burst": chr(0xE52F)}))):
        acc = backdrop(0.0, rain=weather)
        if lit:
            for p in group:
                draw_panel(acc, p, p["op"], 0.0, lays)
        if weather:
            draw_weather(acc, tick=3)
        if extra:
            draw_title(acc, extra)
        if veil:
            draw_title(acc, veil_items(veil))
        img = Image.fromarray(np.clip(acc, 0, 255).astype(np.uint8), "RGB")
        img.save(os.path.join(OUT, "bands_%s.png" % re.sub(r"[^a-z0-9]+", "_", tag.lower())))
        rows.append((tag, img, band_redness(np.asarray(img, np.float32))))
        print("  %-14s bands sky %5.1f  horizon %5.1f  ground %5.1f" % (tag, *rows[-1][2]))
    for name, path, b in REFERENCE:
        print("  %-26s bands sky %5.1f  horizon %5.1f  ground %5.1f  (measured, %s)"
              % (name, *b, path))
    hit = [r for r in rows if r[0].startswith("held")][0]
    print("  held lv%-2d vs 1.0.18 plateau: sky %+.1f of %+.1f, horizon %+.1f of %+.1f"
          % (base, hit[2][0], REFERENCE[0][2][0], hit[2][1], REFERENCE[0][2][1]))
    tw, th = 420, 236
    sh = Image.new("RGB", (tw * len(rows), th * 2), (12, 12, 12))
    for i, (tag, img, b) in enumerate(rows):
        sh.paste(img.resize((tw, th), Image.LANCZOS), (i * tw, 0))
    for i, (name, path, b) in enumerate(REFERENCE):
        sh.paste(Image.open(os.path.join(ROOT, "vid18", path)).resize((tw, th), Image.LANCZOS),
                 (i * tw, th))
    # every label after every paste: the reference row sits directly under the first row's text, and
    # an earlier version of this sheet pasted straight over its own labels.
    draw = ImageDraw.Draw(sh)
    for i, (tag, img, b) in enumerate(rows):
        draw.text((i * tw + 6, th - 24), "%s\n%4.1f %4.1f %4.1f" % (tag, *b), fill=(240, 240, 240))
    for i, (name, path, b) in enumerate(REFERENCE):
        draw.text((i * tw + 6, th * 2 - 32), "%s\n%4.1f %4.1f %4.1f" % (name, *b),
                  fill=(255, 214, 96))
    sh.save(os.path.join(OUT, "rain_vs_reference.png"))
    print(os.path.join(OUT, "rain_vs_reference.png"))
    n, mean, cov = draw_weather(np.zeros((H, W, 3), np.float32), tick=3)
    print("rain: %d of 440 sheets reached the frame, mean alpha %.1f%% of it, inked on %.0f%%"
          % (n, mean * 100, cov * 100))
    print("reference sky band over the whole recording: %s" % rain_timeline())


# ------------------------------------------------------------------ the flash on screen
def veil_items(lv):
    return title_items("title_red", {"rc": chr(0xE410 + max(0, min(19, lv or 0)))})


def layers_for(panels, var, gate="if"):
    """The three panels one #sr roll summons, farthest first: glow, core, flare."""
    order = ["deusex_fglow", "deusex_fcore", "deusex_fflare"]
    want = sorted([p for p in panels if p["var"] == var and p["gate"] == gate],
                  key=lambda p: -p["dist"])
    return want if [p["layer"] for p in want] == order else None


def strip_flash(pitch=0.0, yaw=0.0, night=False, var=0,
                pick=(1, 2, 3, 4, 6, 8, 11, 14, 18, 22, 27, 34, 44, 60, 80)):
    """What one flash really puts on the screen, tick by tick, from the shipped functions.

    Three layers ride every flash, so a single "the panel" number is not what the player sees: the
    glow is the red sky, the core is the hot middle and the flare is the bright heart inside it. All
    three are drawn, farthest first, and the coverage each one paints is printed - a glow that stops
    short of the frame edge is a decal, and a layer that lands outside the view is nothing at all.
    """
    os.makedirs(OUT, exist_ok=True)
    lays = {}
    for name in ("skyglow", "skyred"):
        lays.update(lay_of(name))
    panels = parse_flash()
    seq = flash_seq()
    group = layers_for(panels, var)
    assert group, "variant %d does not hold glow + core + flare" % var
    live = [i for i, r in enumerate(seq) if r["alphas"]]
    print("tick order from tick.mcfunction: %s" % ", ".join(
        tick_order("wash_tick", "flash_tick", "wash_draw")))
    print("panel: %d ticks of envelope, %d layers (variant %d at %s blocks)"
          % (len(live), len(group), var, "/".join(str(int(p["dist"])) for p in group)))
    for p in group:
        a = [seq[i]["alphas"].get(p["layer"]) for i in live]
        print("  %-13s first %-3d peak %-3d last %-3d" % (p["layer"], a[0], max(a), a[-1]))
    base = held_base()
    ceil = wash_ceiling()          # the veil a lit flash sits under, not the held floor
    wash = [r["wash"] for r in seq]
    settle = next((i for i, v in enumerate(wash) if i > 3 and v == base), None)
    print("wash: peak %d, on the held base %d from t=%s, then %s, levels %s, repaints %d"
          % (max(wash), base, settle,
             "holds" if wash[settle:] == [base] * len(wash[settle:]) else "LEAVES THE FLOOR",
             [r["lv"] for r in seq if r["lv"] is not None][:12],
             sum(1 for r in seq if r["repaint"])))
    print("particles: none - the pack draws no /particle, the rain in these frames is the sheet")
    print("camera pitch %+3.0f deg, panel bearing %+3.0f deg (the flash_rand roll)" % (pitch, yaw))

    def frame_at(t):
        r = seq[t]
        # The burst forces the weather and only closing_start clears it, so every frame of the song
        # is a rainy one: the sky takes FogRenderer's darkening and the pack's own red rain.png
        # sheets come down over all of it - then the veil goes on last, on
        # top of the world, which is what makes the drops read red without the pack touching a
        # texture the client binds outside the event.
        acc = backdrop(pitch, night=night, rain=True)
        bits = []
        for p in group:                          # farthest first: the flare sits inside the glow
            a = r["alphas"].get(p["layer"])
            if a is None:
                continue
            bits.append(draw_panel(acc, p, a, pitch, lays, yaw)[0])
        if not r["alphas"]:
            bits.append("(panel dead)")
        sheets, mean, cov = draw_weather(acc, tick=t, pitch=pitch, night=night)
        bits.append("rain %d sheets on %.0f%%" % (sheets, cov * 100))
        if r["lv"] is not None:
            draw_title(acc, veil_items(r["lv"]))
            mean, mx = veil_alpha(veil_items(r["lv"]))
            bits.append("veil lv%-2d mean %4.1f%% peak %3.0f%%" % (r["lv"], mean * 100, mx * 100))
        print("  t=%-3d %s" % (t, "  |  ".join(bits)))
        return r["alphas"].get("deusex_fflare", 0), Image.fromarray(
            np.clip(acc, 0, 255).astype(np.uint8), "RGB")

    tiles = [(t, a, im) for t, (a, im) in ((t, frame_at(t)) for t in pick if t < len(seq))]
    sheet(tiles, os.path.join(OUT, "flash_strip%s.png"
                              % ("_night" if night else ("_yaw%+03.0f" % yaw if yaw else ""))),
          lambda i, t, a: "t=%d flare=%d" % (t, a))

    if night or yaw:
        return
    levels_sheet()
    # the sheet the user watched: the panel has to stay on screen through the pitches a player
    # actually holds, and the veil is what carries the red when they look up or down. Every one of
    # these is a rainy frame: the burst forces the weather for the whole song.
    for p_ in (-40.0, -20.0, 0.0, 20.0, 40.0):
        acc = backdrop(p_, rain=True)
        for pl in group:
            print("  camera %+3.0f deg  %s" % (p_, draw_panel(acc, pl, pl["op"], p_, lays)[0]))
        print("  camera %+3.0f deg  rain %d sheets" % (p_, draw_weather(acc, tick=4, pitch=p_)[0]))
        draw_title(acc, veil_items(ceil))
        Image.fromarray(np.clip(acc, 0, 255).astype(np.uint8), "RGB").save(
            os.path.join(OUT, "flash_pitch%+03.0f.png" % p_))
    for y_ in (-30.0, -15.0, 15.0, 30.0):
        acc = backdrop(0.0, rain=True)
        for pl in group:
            print("  bearing %+3.0f deg  %s"
                  % (y_, draw_panel(acc, pl, pl["op"], 0.0, lays, y_)[0]))
        draw_weather(acc, tick=4, pitch=0.0)
        draw_title(acc, veil_items(ceil))
        Image.fromarray(np.clip(acc, 0, 255).astype(np.uint8), "RGB").save(
            os.path.join(OUT, "flash_yaw%+03.0f.png" % y_))
    fb = layers_for(panels, var, "unless")
    acc = backdrop(pitch, rain=True)
    for pl in fb:
        print("  fallback (%d blocks)  %s"
              % (int(pl["dist"]), draw_panel(acc, pl, pl["op"], pitch, lays, yaw)[0]))
    draw_weather(acc, tick=4, pitch=pitch)
    draw_title(acc, veil_items(ceil))
    Image.fromarray(np.clip(acc, 0, 255).astype(np.uint8), "RGB").save(
        os.path.join(OUT, "flash_fallback.png"))


def levels_sheet():
    """How much red each veil level actually puts on screen, against both skies."""
    rows = []
    for night in (False, True):
        for lv in (0, 4, 7, 10, 13, 16, 19):
            acc = backdrop(12.0, night=night)
            draw_title(acc, veil_items(lv))
            mean, mx = veil_alpha(veil_items(lv))
            img = Image.fromarray(np.clip(acc, 0, 255).astype(np.uint8), "RGB")
            ImageDraw.Draw(img).text((8, 6), "%s lv%-2d  %.1f%%"
                                     % ("night" if night else "day", lv, mean * 100),
                                     fill=(255, 255, 255))
            rows.append(img)
            print("  %-5s veil lv%-2d  mean alpha over the frame %5.1f%%  (flat cell, peak %3.0f%%)"
                  % ("night" if night else "day", lv, mean * 100, mx * 100))
    tw, th = 320, 180
    sh = Image.new("RGB", (tw * 7, th * 2), (12, 12, 12))
    for i, im in enumerate(rows):
        sh.paste(im.resize((tw, th), Image.LANCZOS), ((i % 7) * tw, (i // 7) * th))
    sh.save(os.path.join(OUT, "veil_levels.png"))
    print(os.path.join(OUT, "veil_levels.png"))


def lyrics_over_veil():
    """The actionbar is registered before TITLE in Gui.java, so the veil paints OVER the lyrics.

    This sheet is what caps how strong the wash is allowed to be: hudview draws in the real
    1920x1080 pixel space, so its layer is downscaled into this frame instead of being pasted at
    the wrong size - which is what made the first version of this tile show no bar at all.
    """
    tiles = []
    for lv in (held_base(), (held_base() + wash_ceiling()) // 2, wash_ceiling()):
        for idx, lvl in ((1, 3), (7, 5)):
            acc = backdrop(0.0)
            draw_title(acc, veil_items(lv))
            base = Image.fromarray(np.clip(acc, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
            layer = Image.new("RGBA", (GUI_W * hudview.SCALE, GUI_H * hudview.SCALE), (0, 0, 0, 0))
            items = hudview.build(0, 0, frame=6, lyric_level=lvl, lyric_index=idx)
            hudview.draw_items(items, layer, (GUI_W - hudview.measure(items)) // 2)
            base.alpha_composite(layer.resize((W, H), Image.LANCZOS))
            out = base.convert("RGB")
            ImageDraw.Draw(out).text((8, 6), "veil lv%-2d lyric %d/%d" % (lv, idx, lvl),
                                     fill=(255, 255, 255))
            tiles.append(out)
            out.save(os.path.join(OUT, "veil_lv%d_hud%d_%d.png" % (lv, idx, lvl)))
    tw, th = 420, 236
    sh = Image.new("RGB", (tw * 2, th * 3), (12, 12, 12))
    for i, im in enumerate(tiles):
        sh.paste(im.resize((tw, th), Image.LANCZOS), ((i % 2) * tw, (i // 2) * th))
    sh.save(os.path.join(OUT, "veil_hud.png"))
    print(os.path.join(OUT, "veil_hud.png"))


def sheet(tiles, fn, label):
    tw, th, cols = 420, 236, 6
    sh = Image.new("RGB", (tw * cols, th * ((len(tiles) + cols - 1) // cols)), (16, 16, 16))
    for i, (t, a, im) in enumerate(tiles):
        im = im.resize((tw, th), Image.LANCZOS)
        ImageDraw.Draw(im).text((6, 4), label(i, t, a), fill=(240, 240, 240))
        sh.paste(im, ((i % cols) * tw, (i // cols) * th))
    os.makedirs(OUT, exist_ok=True)
    sh.save(fn)
    print(fn)


# ------------------------------------------------------------------ the drop
def burst_pacing():
    """[(tick after the drop, burst frame)] from the shipped opening_flash."""
    oflash = open(os.path.join(FUN, "opening_flash.mcfunction"), encoding="utf-8").read()
    end = int(re.search(r"matches (\d+)\.\. run function deusex:opening_done", oflash).group(1))
    out = []
    for k in range(1, end + 1):
        S = {"#E": k, "#drop": 0, "#3": 3, "#bf": 0}
        mclog.run("opening_flash", S, [])
        out.append((k, S.get("#bf", 0)))
    return end, out


def frame_coverage(quads):
    """The share of the 1280x720 frame the string's inked boxes actually reach."""
    m = np.zeros((H, W), bool)
    for _, x, y, w, h in quads:
        m[max(0, int(y)):min(H, int(math.ceil(y + h))),
          max(0, int(x)):min(W, int(math.ceil(x + w)))] = True
    return float(m.mean())


def veil_slots(lv=14):
    """What each way of spending a veil cell actually puts on the screen, title slot and subtitle
    slot side by side.

    The answer that surprised me: coverage is not what separates them. red_lv.png's cell is 1200x600
    font units, which is 2.5x the 960x540 GUI viewport even at the subtitle's half scale, so every
    row here reaches the whole frame and lays the same flat 34.9%. What the subtitle would still
    cost is a second title packet on each of the fifty burst ticks, a slot that only `title @a reset`
    empties, and - the part this pack can check - a veil drawn on a different box than the one
    `wash_draw` paints from opening_done onwards. The last row is the shipped answer: the blast and
    the wash in one string, the second cell walked back over the first by tspace's -1201, so the
    cell at the hand-over is the same cell at the same pen, not a half-scaled copy of it.
    """
    cell = 0xE410 + lv
    for label, items, slot in (("title, one cell", veil_items(lv), "title"),
                               ("subtitle, one cell", [("fx", cell)], "subtitle"),
                               ("subtitle, two cells", [("fx", cell), ("fx", cell)], "subtitle"),
                               ("title, blast over it", burst_items(15, lv), "title")):
        quads = (subtitle_quads if slot == "subtitle" else title_quads)(items)[0]
        mean, mx = veil_alpha(items, slot)
        print("veil %s: covers %5.1f%% of the frame, mean alpha %.1f%%, peak %.1f%%"
              % (label.ljust(20), frame_coverage(quads) * 100, mean * 100, mx * 100))


def burst_items(frame, lv):
    """The shipped burst string with both storage macros resolved: blast `frame`, wash cell `lv`."""
    return title_items("title_red_burst",
                       {"burst": chr(0xE520 + frame), "rc": chr(0xE410 + max(0, min(19, lv or 0)))})


def burst_geometry():
    hold = held_base()
    end, pacing = burst_pacing()
    items = burst_items(15, hold)
    quads, width = title_quads(items)
    v, g = glyph("fx", 0xE410 + hold), glyph("burst", 0xE520)
    print("burst title: one string, wash cell (advance %d, ink %d, height %d, top %d) then the blast "
          "cell (advance %d) walked back over it; string width %d"
          % (v["advance"], int(v["draw"]), v["height"], v["top"], g["advance"], width))
    for name, (_c, x, y, w, h) in zip(("wash", "blast"), quads):
        print("   %-5s pen x=%+.0f y=%+.0f GUI at TITLE_SCALE %gx: %.0f x %.0f GUI units in a %dx%d viewport"
              % (name, x / PPU, y / PPU, TITLE_SCALE, w / PPU, h / PPU, GUI_W, GUI_H))
    print("   the two pens are %.0f world px apart over the same cell, so the blast lands on the wash"
          % abs(quads[1][1] - quads[0][1]))
    _c, x, y, w, h = quads[0]
    print("   so the screen shows columns %.0f%%..%.0f%% and rows %.0f%%..%.0f%% of the cell"
          % (max(0, -x / w) * 100, min(1, (W - x) / w) * 100,
             max(0, -y / h) * 100, min(1, (H - y) / h) * 100))
    print("   the pair reaches %.1f%% of the frame" % (frame_coverage(quads) * 100))
    print("   pacing (tick:frame) %s" % ", ".join("%d:%d" % kp for kp in pacing[:14]))
    veil_slots()
    return end, pacing


def strip_burst(frames=(0, 1, 2, 3, 5, 8, 11, 15)):
    """The drop, tick by tick, as the two curves the player actually watches.

    The wash is not up at full depth on the burst tick: `opening_burst` raises #washbase while #wash is
    still 0, and wash_tick walks it one level a tick from there. The blast is brightest on exactly
    that tick and falls off over the same fourteen. Drawing each frame at the level its own tick
    carries is what shows the hand-over - the red does not arrive after the explosion, it arrives
    through it - and the last tile is the tick after opening_done reset the title, painted by
    wash_draw from the shipped title_red instead, at the same cell.
    """
    os.makedirs(OUT, exist_ok=True)
    end, pacing = burst_geometry()
    hold = held_base()
    first = {}
    for k, bf in pacing:
        first.setdefault(bf, k)
    world = backdrop(0.0, seed=11)
    tiles = []
    full = os.path.join(OUT, "full")
    os.makedirs(full, exist_ok=True)
    for f in frames:
        k = first.get(f, 0)
        lv = min(k, hold)                    # wash_tick's one level a tick, from 0 at the drop
        acc = world.copy()
        items = burst_items(f, lv)
        draw_title(acc, items)
        mean, mx = veil_alpha(items)
        print("   frame %2d  t=+%-2d  wash lv%-2d  laid over the frame: mean %.1f%% peak %.0f%%"
              % (f, k, lv, mean * 100, mx * 100))
        img = Image.fromarray(np.clip(acc, 0, 255).astype(np.uint8), "RGB")
        img.save(os.path.join(full, "burst_f%02d.png" % f))
        tiles.append((k, (f, lv), img))
    acc = world.copy()
    draw_title(acc, veil_items(hold))
    mean, mx = veil_alpha(veil_items(hold))
    print("   hand-over  t=+%d  wash_draw repaints lv%d the string was carrying: mean %.1f%% peak %.0f%%"
          % (end + 1, hold, mean * 100, mx * 100))
    tiles.append((end + 1, (None, hold),
                  Image.fromarray(np.clip(acc, 0, 255).astype(np.uint8), "RGB")))
    sheet(tiles, os.path.join(OUT, "burst_strip.png"),
          lambda i, t, a: ("t=+%d  wash_draw lv%d, same cell" % (t, a[1]) if a[0] is None
                           else "f%d  t=+%d  wash lv%d" % (a[0], t, a[1])))


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    os.makedirs(OUT, exist_ok=True)
    if what in ("all", "flash"):
        strip_flash()
        strip_flash(night=True)
        strip_flash(yaw=30.0)                # the worst roll flash_rand can make: 30 deg off centre
        lyrics_over_veil()
        compare_rain()
    if what in ("all", "burst"):
        strip_burst()
