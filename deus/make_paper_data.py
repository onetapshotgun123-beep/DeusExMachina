"""Generate ShowData.java for the Paper port from the legacy 1.0.34 datapack fonts/functions
and the mod's ShowHudData timing tables. Run from deus/: python make_paper_data.py"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
LEGACY = os.path.join(HERE, "legacy_1034")
FONT = os.path.join(LEGACY, "assets", "deusex", "font")
FUNC = os.path.join(LEGACY, "data", "deusex", "function")
MOD_DATA = os.path.join(HERE, "client", "src", "main", "java", "net", "deusexmachina", "client", "ShowHudData.java")
OUT = os.path.join(HERE, "paper", "src", "main", "java", "net", "deusexmachina", "paper", "ShowData.java")


def font(name):
    with open(os.path.join(FONT, name + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


def bitmap_cells(name):
    cells = []
    for p in font(name)["providers"]:
        if p["type"] == "bitmap":
            for row in p["chars"]:
                cells.extend(row)
    return cells


def contiguous(cells):
    codes = [ord(c) for c in cells]
    assert codes == list(range(codes[0], codes[0] + len(codes))), "non-contiguous cells"
    return codes[0]


def func(name):
    with open(os.path.join(FUNC, name + ".mcfunction"), encoding="utf-8") as fh:
        return fh.read()


def jstr(s):
    out = []
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif 32 <= o < 127:
            out.append(ch)
        else:
            out.append("\\u%04X" % o)
    return '"' + "".join(out) + '"'


def template(name, kind):
    """Pull the $title JSON out of a macro function, turning score refs into placeholders."""
    text = func(name)
    prefix = "$title @a " + kind + " "
    plain = "title @a " + kind + " "
    line = next(l for l in text.splitlines() if l.startswith(prefix) or l.startswith(plain))
    raw = line[len(prefix):] if line.startswith(prefix) else line[len(plain):]
    obj = json.loads(raw)

    def walk(node):
        if isinstance(node, list):
            return [walk(x) for x in node]
        if isinstance(node, dict):
            if "score" in node:
                score = node["score"]["name"]
                ph = {"#min": "$(min)", "#s10": "$(s10)", "#s1": "$(s1)"}[score]
                node = dict(node)
                del node["score"]
                node["text"] = ph
            return {k: walk(v) for k, v in node.items()}
        return node

    obj = walk(obj)
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def preset_rows():
    """Parse hud_preset's data merge lines into 11 preset dicts."""
    rows = [None] * 11
    for line in func("hud_preset").splitlines():
        m = re.match(r"data merge storage deusex:data \{(.+)\}", line)
        if m:
            row = {}
            for key, val in re.findall(r'(\w+):"([^"]*)"', m.group(1)):
                row[key] = val
            rows[0] = row
        m = re.match(r"execute if score #p deusex matches (\d+) run data merge storage deusex:data \{(.+)\}", line)
        if m:
            idx = int(m.group(1))
            row = {}
            for key, val in re.findall(r'(\w+):"([^"]*)"', m.group(2)):
                row[key] = val
            rows[idx] = row
    assert all(r is not None for r in rows), "missing preset"
    return rows


def char_map(name, pattern):
    """Map an index to the single glyph set on that line."""
    out = {}
    for line in func(name).splitlines():
        m = re.search(pattern, line)
        if m:
            out[int(m.group(1))] = m.group(2)
    return out


def mod_array(name):
    src = open(MOD_DATA, encoding="utf-8").read()
    m = re.search(name + r"\s*=\s*\{([^}]+)\}", src)
    return [int(x) for x in re.findall(r"-?\d+", m.group(1))]


def main():
    red_lv = bitmap_cells("fx")[2:22]  # black, white, then 20 levels
    fx_cells = bitmap_cells("fx")
    assert len(fx_cells) == 35
    heart = fx_cells[22:]
    burst = bitmap_cells("burst")
    lyric = bitmap_cells("lyric")
    box = bitmap_cells("box")
    disc_c = bitmap_cells("hud_c")
    discs = [bitmap_cells("hud_v%d" % i) for i in range(5)]
    assert len(red_lv) == 20 and len(heart) == 13 and len(burst) == 16
    assert len(lyric) == 444 and len(box) == 13 and len(disc_c) == 10
    assert all(len(d) == 24 for d in discs)
    bases = {n: contiguous(c) for n, c in
             [("red_lv", red_lv), ("heart", heart), ("burst", burst), ("lyric", lyric),
              ("box", box), ("disc_c", disc_c)] + [("disc_v%d" % i, d) for i, d in enumerate(discs)]}

    presets = preset_rows()
    collapse = func("closing_collapse")
    cbox = char_map("closing_collapse", r'#kb deusex matches (\d+) run data modify storage deusex:data bx set value "(.)"')
    cdisc = char_map("closing_collapse", r'#kd deusex matches (\d+) run data modify storage deusex:data g set value "(.)"')
    assert len(cbox) == 8 and len(cdisc) == 10

    lines = []
    w = lines.append
    w("package net.deusexmachina.paper;")
    w("")
    w("/** Generated by deus/make_paper_data.py from the legacy datapack fonts and the mod's")
    w(" *  timing tables - do not edit by hand. */")
    w("public final class ShowData {")
    w("    private ShowData() {}")
    w("    public static final String BLACK = %s;" % jstr(fx_cells[0]))
    w("    public static final String WHITE = %s;" % jstr(fx_cells[1]))
    for name, cells in [("RED_LV", red_lv), ("HEART", heart), ("BURST", burst),
                        ("BOX", box), ("DISC_C", disc_c)]:
        w("    public static final int %s_BASE = 0x%04X;" % (name, bases[name.lower()]))
        w("    public static final int %s_COUNT = %d;" % (name, len(cells)))
    for i, d in enumerate(discs):
        w("    public static final int DISC_V%d_BASE = 0x%04X;" % (i, bases["disc_v%d" % i]))
    w("    public static final int LYRIC_BASE = 0x%04X;" % bases["lyric"])
    w("    public static final int LYRIC_COUNT = %d;" % len(lyric))
    w("")
    keys = ["bx", "bsp", "bsn", "dsp", "dsn", "tsp", "tsn"]
    for key in keys:
        w("    public static final String[] P_%s = {%s};" %
          (key.upper(), ", ".join(jstr(r[key]) for r in presets)))
    w("    public static final String[] P_DF = {%s};" % ", ".join(jstr(r["df"]) for r in presets))
    w("    public static final String[] P_TC = {%s};" % ", ".join(jstr(r["tc"]) for r in presets))
    w("")
    w("    public static final String T_BLACK = %s;" % jstr(template("title_black", "title")))
    w("    public static final String T_WASH = %s;" % jstr(template("title_red", "title")))
    w("    public static final String T_HEART = %s;" % jstr(template("title_hb", "title")))
    w("    public static final String T_BURST = %s;" % jstr(template("title_red_burst", "title")))
    w("    public static final String T_HUD = %s;" % jstr(template("hud_show", "actionbar")))
    w("    public static final String T_BOX = %s;" % jstr(template("hud_show_box", "actionbar")))
    w("    public static final String T_LYRIC = %s;" % jstr(template("lyric_only", "actionbar")))
    w("    public static final String T_COLLAPSE = %s;" % jstr(template("hud_show_c", "actionbar")))
    w("")
    w("    public static final String[] COLLAPSE_BOX = {%s};" %
      ", ".join(jstr(cbox[i]) for i in range(8)))
    w("    public static final String[] COLLAPSE_DISC = {%s};" %
      ", ".join(jstr(cdisc[i]) for i in range(10)))
    w("")
    for name in ["LYRIC_START", "LYRIC_END", "BEAT_TICKS", "HB_WASH", "WASH_ALPHA", "P_MODE", "P_SCR"]:
        vals = mod_array(name)
        w("    public static final int[] %s = {%s};" % (name, ", ".join(str(v) for v in vals)))
    w("}")
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("wrote", OUT)
    print("bases:", {k: hex(v) for k, v in bases.items()})
    print("presets:", [(r["df"], r["tc"]) for r in presets])


if __name__ == "__main__":
    main()