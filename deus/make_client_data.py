"""Generate ShowHudData.java for the client mod from the shipped datapack/assets.

Every number comes from the same sources the datapack used, so the client
renderer reproduces the approved look exactly:
  - lyric windows from lyric_tick.mcfunction
  - glyph advances with vanilla's BitmapProvider ink rule (hudview.py model)
  - HUD presets from hud_preset.mcfunction
  - flash envelope from flash_frame.mcfunction
  - wash alphas measured from red_lv.png
"""
import json
import os
import re

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
# The shipped pack is now a thin command shim; the show lives in the client mod. The numbers this
# generator derives still come from the approved 1.0.34 datapack, kept whole under legacy_1034 as the
# source of truth so a regen reproduces the look the user signed off on rather than a fresh guess.
EXT = os.path.join(ROOT, "legacy_1034")
FUNC = os.path.join(EXT, "data", "deusex", "function")
ASSETS = os.path.join(EXT, "assets", "deusex")
OUT = os.path.join(ROOT, "client", "src", "main", "java", "net", "deusexmachina", "client", "ShowHudData.java")


def font(name):
    return json.load(open(os.path.join(ASSETS, "font", name + ".json"), encoding="utf-8"))


def advances(name):
    """codepoint -> (advance, cell_w, cell_h, draw_w, draw_h, top, col, row, file)"""
    doc = font(name)
    out = {}
    for pr in doc["providers"]:
        if pr["type"] == "space":
            for k, v in pr["advances"].items():
                out[ord(k)] = dict(adv=v)
            continue
        img = np.array(Image.open(os.path.join(ASSETS, "textures", pr["file"].split(":", 1)[1])).convert("RGBA"))
        grid = pr["chars"]
        ch, cw = img.shape[0] // len(grid), img.shape[1] // len(grid[0])
        f = pr["height"] / ch
        for r, row in enumerate(grid):
            for c, cp in enumerate(row):
                if cp == "\x00":
                    continue
                cell = img[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw]
                ink = (cell[..., 3] != 0) | (cell[..., :3].sum(2) != 0)
                cols = np.nonzero(ink.any(0))[0]
                actual = 0 if len(cols) == 0 else int(cols[-1]) + 1
                out[ord(cp)] = dict(adv=int(0.5 + actual * f) + 1, cw=cw, ch=ch,
                                    dw=cw * f, dh=pr["height"], top=7 - pr["ascent"],
                                    col=c, row=r, file=pr["file"])
    return out


SPACE = advances("space")
LYRIC = advances("lyric")
BOX = advances("box")
DISCS = [advances("hud_v%d" % i) for i in range(5)]
DISC_C = advances("hud_c")
DIGITS = advances("hud_text")


def sp(cp):
    return SPACE[ord(cp)]["adv"] if cp else 0


def arr(name, values, per_line=16):
    lines = []
    for i in range(0, len(values), per_line):
        lines.append("        " + ", ".join(str(v) for v in values[i:i + per_line]))
    return "    public static final int[] %s = {\n%s\n    };" % (name, ",\n".join(lines))


# lyric windows
text = open(os.path.join(FUNC, "lyric_tick.mcfunction"), encoding="utf-8").read()
starts, ends = {}, {}
for m in re.finditer(r"matches (\d+)\.\.(\d+) run scoreboard players set #li deusex (\d+)", text):
    starts[int(m[3])] = int(m[1])
for m in re.finditer(r"matches (\d+)\.\.(\d+) run scoreboard players set #lend deusex (\d+)", text):
    pass
for m in re.finditer(r"set #lend deusex (\d+)", text):
    pass
# lend lines follow the same window; pair by order
li_order = [int(m[1]) for m in re.finditer(r"set #li deusex (\d+)", text)]
lend_vals = [int(m[1]) for m in re.finditer(r"set #lend deusex (\d+)", text)]
for li, lend in zip(li_order, lend_vals):
    ends[li] = lend
n_lyrics = max(starts) + 1
LYRIC_START = [starts[i] for i in range(n_lyrics)]
LYRIC_END = [ends[i] for i in range(n_lyrics)]
LYRIC_ADV = [LYRIC[0xe900 + i]["adv"] for i in range(444)]

BOX_ADV = [BOX[0xe300 + i]["adv"] for i in range(13)]
DISC_ADV = [[DISCS[v][0xe200 + i]["adv"] for i in range(24)] for v in range(5)]
DISC_C_ADV = [DISC_C[0xe200 + i]["adv"] for i in range(10)]
DIGIT_ADV = [DIGITS[ord(c)]["adv"] for c in "0123456789:/"]

# presets
COLORS = {"white": 0xFFFFFF, "aqua": 0x55FFFF, "light_purple": 0xFF55FF, "red": 0xFF5555, "yellow": 0xFFFF55}
presets = {}
text = open(os.path.join(FUNC, "hud_preset.mcfunction"), encoding="utf-8").read()
for line in text.splitlines():
    m = re.search(r"if score #p deusex matches (\d+) run data merge storage deusex:data \{(.*)\}", line)
    if m:
        p = int(m[1])
        body = m[2]
        fields = dict(re.findall(r'(\w+):"([^"]*)"', body))
        pr = presets.setdefault(p, dict(mode=0, scr=0))
        pr["bx"] = ord(fields["bx"]) - 0xe300
        for k in ("bsp", "bsn", "dsp", "dsn", "tsp", "tsn"):
            pr[k] = sp(fields.get(k, ""))
        pr["df"] = int(fields["df"][-1])
        pr["tc"] = COLORS[fields["tc"]]
    m = re.search(r"if score #p deusex matches (\d+) run scoreboard players set #mode deusex (\d+)", line)
    if m:
        presets.setdefault(int(m[1]), dict(mode=0, scr=0))["mode"] = int(m[2])
    m = re.search(r"if score #p deusex matches (\d+) run scoreboard players set #scr deusex (\d+)", line)
    if m:
        presets.setdefault(int(m[1]), dict(mode=0, scr=0))["scr"] = int(m[2])
# preset 0 is the default line
m = re.search(r"^data merge storage deusex:data \{(.*)\}", text, re.M)
fields = dict(re.findall(r'(\w+):"([^"]*)"', m[1]))
pr = presets.setdefault(0, dict(mode=0, scr=0))
pr["bx"] = ord(fields["bx"]) - 0xe300
for k in ("bsp", "bsn", "dsp", "dsn", "tsp", "tsn"):
    pr[k] = sp(fields.get(k, ""))
pr["df"] = int(fields["df"][-1])
pr["tc"] = COLORS[fields["tc"]]

# flash envelope (unsigned byte opacities), rows keyed 22 down to 1
text = open(os.path.join(FUNC, "flash_frame.mcfunction"), encoding="utf-8").read()
env = {}
for m in re.finditer(r"matches (\d+) as @e\[tag=deusex_(\w+)\] run data merge entity @s \{text_opacity:(-?\d+)b\}", text):
    frame, tag, op = int(m[1]), m[2], int(m[3])
    env.setdefault(frame, {})[tag] = op & 0xFF
FLASH_GLOW = [env[f]["fglow"] for f in range(22, 0, -1)]
FLASH_CORE = [env[f]["fcore"] for f in range(22, 0, -1)]
FLASH_FLARE = [env[f]["fflare"] for f in range(22, 0, -1)]

# closing collapse box frames
text = open(os.path.join(FUNC, "closing_collapse.mcfunction"), encoding="utf-8").read()
COLLAPSE_BOX = [ord(cp) - 0xe300 for cp in re.findall(r'set value "(.)"', text)][:8]

# wash alphas from the shipped texture
im = np.array(Image.open(os.path.join(ASSETS, "textures", "font", "red_lv.png")).convert("RGBA"))
WASH_ALPHA = [int(round(im[i * 16:(i + 1) * 16, :, 3].mean())) for i in range(20)]

java = []
java.append("package net.deusexmachina.client;")
java.append("")
java.append("/** Generated by deus/make_client_data.py from the shipped assets - do not edit by hand. */")
java.append("public final class ShowHudData {")
java.append("    private ShowHudData() {}")
java.append(arr("LYRIC_START", LYRIC_START))
java.append(arr("LYRIC_END", LYRIC_END))
java.append(arr("LYRIC_ADV", LYRIC_ADV, 24))
java.append(arr("BOX_ADV", BOX_ADV))
for v in range(5):
    java.append(arr("DISC_ADV_%d" % v, DISC_ADV[v], 24))
java.append("    public static final int[][] DISC_ADV = {DISC_ADV_0, DISC_ADV_1, DISC_ADV_2, DISC_ADV_3, DISC_ADV_4};")
java.append(arr("DISC_C_ADV", DISC_C_ADV))
java.append(arr("DIGIT_ADV", DIGIT_ADV))
java.append("    // \" / 9:06\" in the digits font: space is 4, the rest are glyphs")
java.append("    public static final int TIME_SUFFIX_ADV = 4 + DIGIT_ADV[11] + 4 + DIGIT_ADV[9] + DIGIT_ADV[10] + DIGIT_ADV[0] + DIGIT_ADV[6];")
for key in ("bx", "bsp", "bsn", "dsp", "dsn", "tsp", "tsn", "df", "tc", "mode", "scr"):
    java.append(arr("P_" + key.upper(), [presets[p][key] for p in range(11)]))
java.append(arr("BEAT_TICKS", [50, 84, 114, 140, 162, 178, 188, 196]))
java.append(arr("HB_WASH", [17, 16, 13, 10, 7, 4, 15, 14, 11, 8, 5, 3, 1, 0]))
java.append(arr("WASH_ALPHA", WASH_ALPHA))
java.append(arr("FLASH_GLOW", FLASH_GLOW))
java.append(arr("FLASH_CORE", FLASH_CORE))
java.append(arr("FLASH_FLARE", FLASH_FLARE))
java.append(arr("COLLAPSE_BOX", COLLAPSE_BOX))
java.append("}")
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(java) + "\n")
print("wrote", OUT)
print("lyrics", n_lyrics, "presets", len(presets), "wash14", WASH_ALPHA[14], "wash17", WASH_ALPHA[17])