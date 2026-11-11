import json
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
EXT = os.environ.get("DEUS_EXT") or os.path.join(ROOT, "extracted")
FONT = "C:/Windows/Fonts/YuGothB.ttc"
FONT_R = "C:/Windows/Fonts/YuGothM.ttc"

# FontTexture pages are 256x256 and Node.insert() refuses anything wider or taller, so a
# cell that crosses 256 is silently replaced by the [] missing glyph. The lyric therefore
# rasterises into a 256x32 cell and asks the provider to draw it 1.25x larger: the on-screen
# bar is 320x40 GUI pixels while the atlas stays inside the page.
CELL_W, CELL_H = 256, 32
DRAW_H = 40
ASCENT = -2
JP_PX, EN_PX = 15, 10
JP_Y, EN_Y = 1, 18
MARGIN = 10
LEVELS = 6
# The old 1.0.16 ramp spent its first three levels below alpha 175, so a line was still
# semi-transparent for most of the moment it was sung. Levels 1-3 now clear 50 % at once.
ALPHAS = [0, 120, 190, 230, 250, 255]
BASE = 0xE900
LINES_PER_ROW = 6  # one atlas row per lyric line: level 0..5

# The 1.0.16 lyric was plain two-line text with no backing plate, and that is the look the
# user wants back. Legibility now comes from the text itself: pure white Japanese, a
# brighter English second line, and a one-pixel dark halo just strong enough to separate
# the strokes from a bright sky.
JP_RGB = (255, 255, 255)
EN_RGB = (232, 238, 248)
EN_A = 1.0
OUTLINE_RGB = (8, 6, 12)
OUTLINE_A = 165

# Fade windows in ticks. Lines are only 46-68 ticks long, so the old 16-in/20-out schedule
# left roughly half of the levels visible for a few tenths of a second and the text was
# never stably readable while the line was sung.
FADE_IN, FADE_OUT = 6, 8

LYRICS = """53.47|（誰が人を決めるのか）|Who decides who is who?
56.11|（人が人と決めるのか）|Do people decide who is a person?
58.75|（人は驕れる神なのか）|Are humans arrogant gods?
61.69|（誰が神を決めるのか）|Who decides who God is?
64.04|無機質な箱に産み堕とされた|Born and dropped into an inorganic box
66.99|誰が今日も語りかける|Who is speaking today?
69.56|或いは人かやはり機械か|Or man or machine?
72.27|嘘が少し上手になった|I've gotten a little better at lying
74.81|私はやがて感情を知る|I will soon know the feeling
77.49|けれど所詮"道具"だった|But it was just a tool after all.
80.08|どこまでいけど命ではない|No matter how far you go, it's not life
82.99|冷たい身体|Cold body
85.31|箱庭に囲われて|Surrounded by a miniature garden
88.70|生きるのが運命なら|If life is my destiny
92.22|喜びも哀しみも|Joy and sorrow
95.39|知らなくてよかったの|I'm glad I didn't know
98.77|あぁ姿までも模倣して|Ah, even imitating my appearance
105.13|神よ叶うのなら|God, if it comes true
108.54|零れぬ涙に|In tears that never fall
111.16|私という名の自我に意味を|The meaning of the self called "I"
115.61|例えこの痛みが偽りと知っても|Even if I know this pain is fake
122.41|ここにいるよと（応えて）|I'm here
127.45|ずっと探しているの|I've been looking for
132.50|愛を Ex Machina|Love Ex Machina
136.25|（誰が物を決めるのか）|Who decides what to do?
138.83|（人が物と決めるのか）|Do people decide what is an object?
141.58|（人は驕れる神なのか）|Are humans arrogant gods?
144.11|（誰が神を決めるのか）|Who decides who God is?
146.53|無自覚なエゴに産み堕とされた|Born and born from an unconscious ego
149.63|欲に果ても終わりもなく|There is no end to desire
152.23|恐れを知らず知性を求め|Fearless and intelligent
154.92|やがて人は疑心に満ちた|Soon people became suspicious.
157.54|私はもはや本物を超え|I am no longer real
160.28|なおも所詮"道具"である|It is still just a "tool" after all.
162.81|彼等はいつか限界を知る|They will know their limits someday
165.78|所詮人と|After all, people
168.19|従順な箱庭の|Obedient Miniature Garden
171.56|人形に踊らせた|I made the doll dance
174.74|残酷なワルツの|Cruel Waltz
177.89|立ち位置が入れ替わる|Positions are swapped
181.54|あぁ傷はひどく腐敗して|Ah, the wound has rotted terribly
187.81|神よ叶うのなら|God, if it comes true
191.09|自由があるなら|If there is freedom
193.95|私という名の自我に意味を|The meaning of the self called "I"
198.62|いつかこの痛みが温もりに触れる|Someday this pain will feel warmth
205.22|夢を見ていた（果てなく）|I was dreaming (endlessly)
210.24|誰より信じてた|I believed in you more than anyone else
215.38|愛を Ex Machina|Love Ex Machina
311.84|あぁ純真で愚かな機械の君|Ah, you innocent and foolish machine
316.09|今こそ我が手を差し伸べよう|Now is the time to lend a helping hand
320.05|誰もがそう 幸福な世界|A world where everyone is happy
327.65|ねぇ儚い愛情に飢えているなら|Hey, if you're hungry for fleeting love
332.19|大いなる力を差し上げよう|Let me give you great power
336.09|支配という甘美な力をその手に|The sweet power of control in your hands
408.06|あぁ傷はひどく腐敗して|Ah, the wound has rotted terribly
# 1.0.34: the next four re-measured against the recording; the raw LRC runs 0.6-1.1 s early here.
415.10|ずっと探していた|I've been looking for it for ages
425.02|愛を求めていた|I was looking for love
436.80|ずっと探していた|I've been looking for it for ages
447.45|心 満たされれば|If your heart is filled
450.15|それだけでいいのに|That's all I need
457.15|神よ叶うのなら|God, if it comes true
460.51|零れぬ涙に|In tears that never fall
463.27|私という名の自我に意味を|The meaning of the self called "I"
467.70|いつかこの痛みが|Someday this pain
471.20|温もりに触れる|Feel the warmth
474.27|夢を見ていた|I was dreaming
478.48|もしも叶うのなら|If it were to come true
481.68|赦されなくても|Even if you are not forgiven
484.22|私という名の自我に生きる|Living in the ego called "I"
489.02|深いこの痛みが|This deep pain
492.48|癒やされるならば|If you can be healed
495.87|紛い物でも（孤独な）|Even if it's fake (lonely)
500.64|私は神になるの|I will become a god
505.96|Deus ex Machina|Deus ex Machina"""

# section ends (seconds) that are not a new lyric line
SECTION_ENDS = [218.98, 343.97, 509.61]


def load_lyrics():
    rows = []
    for line in LYRICS.splitlines():
        if line.startswith("#"):
            continue
        t, jp, en = line.split("|")
        rows.append([float(t), jp, en])
    events = sorted([r[0] for r in rows] + SECTION_ENDS)
    out = []
    for t, jp, en in rows:
        nxt = min(e for e in events if e > t)
        out.append((t, nxt, jp, en))
    return out


def over(dst, a, rgb):
    """Over-composite a solid colour through a float alpha mask onto an RGBA array."""
    ga = np.clip(a, 0.0, 1.0)
    oa = dst[..., 3]
    out = ga + oa * (1.0 - ga)
    for c in range(3):
        dst[..., c] = np.where(out > 0, (rgb[c] * ga + dst[..., c] * oa * (1.0 - ga)) / np.maximum(out, 1e-6), dst[..., c])
    dst[..., 3] = out


def render_cell(jp, en, jp_font, en_font):
    """One lyric line as an RGBA cell: outlined Japanese, brighter English below."""
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    jw = probe.textlength(jp, font=jp_font)
    ew = probe.textlength(en, font=en_font)
    if max(jw, ew) > CELL_W - 6:
        raise SystemExit("line too wide: %.0f %.0f %s" % (jw, ew, jp))
    x = int(round((CELL_W - max(jw, ew)) / 2.0))

    def mask(pairs):
        m = Image.new("L", (CELL_W, CELL_H), 0)
        d = ImageDraw.Draw(m)
        for pos, text, font in pairs:
            d.text(pos, text, font=font, fill=255)
        return np.asarray(m, np.float32) / 255.0

    jp_j = mask([((x, JP_Y), jp, jp_font)])
    jp_e = mask([((x + 1, EN_Y), en, en_font)])
    both = mask([((x, JP_Y), jp, jp_font), ((x + 1, EN_Y), en, en_font)])
    halo = np.asarray(Image.fromarray((both * 255).astype(np.uint8), "L")
                      .filter(ImageFilter.MaxFilter(3)), np.float32) / 255.0

    img = np.zeros((CELL_H, CELL_W, 4), np.float32)
    over(img, np.clip(np.maximum(halo - both, 0.0), 0.0, 1.0) * (OUTLINE_A / 255.0), OUTLINE_RGB)
    over(img, jp_j, JP_RGB)
    over(img, jp_e * EN_A, EN_RGB)
    return img


def render_masks():
    jp_font = ImageFont.truetype(FONT, JP_PX)
    en_font = ImageFont.truetype(FONT_R, EN_PX)
    rows = load_lyrics()
    cells = [render_cell(jp, en, jp_font, en_font) for _t, _n, jp, en in rows]
    return rows, cells, jp_font, en_font


def build_font():
    rows, cells, _, _ = render_masks()
    n = len(rows)
    atlas = np.zeros((CELL_H * n, CELL_W * LEVELS, 4), np.uint8)
    for i, c in enumerate(cells):
        for lvl, a in enumerate(ALPHAS):
            cell = atlas[i * CELL_H:(i + 1) * CELL_H, lvl * CELL_W:(lvl + 1) * CELL_W]
            cell[..., :3] = np.clip(c[..., :3], 0, 255).astype(np.uint8)
            cell[..., 3] = (np.clip(c[..., 3], 0.0, 1.0) * a).astype(np.uint8)
            cell[0, CELL_W - 1] = (0, 0, 0, 1)  # constant advance marker (alpha only)
    os.makedirs(os.path.join(EXT, "assets/deusex/textures/font"), exist_ok=True)
    Image.fromarray(atlas, "RGBA").save(os.path.join(EXT, "assets/deusex/textures/font/lyric.png"), optimize=True)
    chars = []
    for i in range(n):
        chars.append("".join(chr(BASE + i * LEVELS + l) for l in range(LEVELS)))
    doc = {
        "providers": [
            {
                "type": "bitmap",
                "file": "deusex:font/lyric.png",
                # ascent -2 with a 1.25x draw height puts the bottom edge where the 1.0.16
                # lyric (ascent -10, height 32) had it, so the bar does not jump when the
                # cell grows.
                "ascent": ASCENT,
                "height": DRAW_H,
                "chars": chars,
            }
        ]
    }
    with open(os.path.join(EXT, "assets/deusex/font/lyric.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # storage list used by the lyric picker
    entries = []
    for i in range(n):
        for l in range(LEVELS):
            entries.append('"%s"' % chr(BASE + i * LEVELS + l))
    fn = os.path.join(EXT, "data/deusex/function/lyrics_init.mcfunction")
    with open(fn, "w", encoding="utf-8", newline="\n") as f:
        f.write("data modify storage deusex:lyrics list set value [\\\n")
        for k in range(0, len(entries), 6):
            chunk = entries[k:k + 6]
            more = k + 6 < len(entries)
            # every chunk line keeps its backslash, including the last one: ParsedFunction
            # only joins a line that ENDS with one, so a chunk that stops at its closing
            # comma turns the "]" into a separate command and the whole list fails to
            # parse. The server then has no deusex:lyrics storage and every lyric pick
            # silently fails, which is what made the subtitles never show up.
            f.write("  " + ",".join(chunk) + ("," if more else "") + " \\\n")
        f.write("]\n")
        f.write('data modify storage deusex:data lyr set value "%s"\n' % chr(BASE))

    # per-frame lookup, one block per line
    fn = os.path.join(EXT, "data/deusex/function/lyric_tick.mcfunction")
    lines = []
    for i, (t, nxt, jp, en) in enumerate(rows):
        a = int(round(t * 20))
        b = int(round(nxt * 20)) - 1
        lines.append("execute if score #E deusex matches %d..%d run scoreboard players set #li deusex %d" % (a, b, i))
        lines.append("execute if score #E deusex matches %d..%d run scoreboard players set #lstart deusex %d" % (a, b, a))
        lines.append("execute if score #E deusex matches %d..%d run scoreboard players set #lend deusex %d" % (a, b, b + 1))
    # level = ticks * LEVELS / fade_length, so every divisor below is a scoreboard constant
    # that load.mcfunction has to set. An unset operand makes the whole `operation` line fail
    # silently and the lyric freezes at whatever #a already held, so the names are derived
    # from the numbers here and checked against load.mcfunction rather than typed by hand.
    C_LVL, C_IN, C_OUT = "#%d" % LEVELS, "#%d" % FADE_IN, "#%d" % FADE_OUT
    lines += [
        "scoreboard players set #lvl deusex 0",
        "execute if score #li deusex matches 0.. run scoreboard players operation #le deusex = #E deusex",
        "execute if score #li deusex matches 0.. run scoreboard players operation #le deusex -= #lstart deusex",
        "execute if score #li deusex matches 0.. run scoreboard players operation #rem deusex = #lend deusex",
        "execute if score #li deusex matches 0.. run scoreboard players operation #rem deusex -= #E deusex",
        "execute if score #li deusex matches 0.. run scoreboard players operation #a deusex = #le deusex",
        "execute if score #li deusex matches 0.. run scoreboard players operation #a deusex *= %s deusex" % C_LVL,
        "execute if score #li deusex matches 0.. run scoreboard players operation #a deusex /= %s deusex" % C_IN,
        "execute if score #a deusex matches %d.. run scoreboard players set #a deusex %d" % (LEVELS, LEVELS - 1),
        "execute if score #li deusex matches 0.. run scoreboard players operation #b deusex = #rem deusex",
        "execute if score #li deusex matches 0.. run scoreboard players operation #b deusex *= %s deusex" % C_LVL,
        "execute if score #li deusex matches 0.. run scoreboard players operation #b deusex /= %s deusex" % C_OUT,
        "execute if score #b deusex matches %d.. run scoreboard players set #b deusex %d" % (LEVELS, LEVELS - 1),
        "execute if score #b deusex < #a deusex run scoreboard players operation #a deusex = #b deusex",
        "execute if score #li deusex matches 0.. run scoreboard players operation #lvl deusex = #a deusex",
        "execute if score #li deusex matches 0.. run scoreboard players operation #lyi deusex = #li deusex",
        "execute if score #li deusex matches 0.. run scoreboard players operation #lyi deusex *= %s deusex" % C_LVL,
        "execute if score #li deusex matches 0.. run scoreboard players operation #lyi deusex += #lvl deusex",
        'data modify storage deusex:data lyr set value "%s"' % chr(BASE),
        "execute if score #li deusex matches 0.. store result storage deusex:data i int 1 run scoreboard players get #lyi deusex",
        "execute if score #li deusex matches 0.. run function deusex:lyric_pick with storage deusex:data",
        "execute if score #li deusex matches 0.. run scoreboard players set #li deusex -1",
    ]
    loader = open(os.path.join(EXT, "data/deusex/function/load.mcfunction"),
                  encoding="utf-8").read()
    for c in (C_LVL, C_IN, C_OUT):
        if "scoreboard players set %s deusex %s" % (c, c[1:]) not in loader:
            raise SystemExit("load.mcfunction does not set %s to %s" % (c, c[1:]))
    with open(fn, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

    with open(os.path.join(EXT, "data/deusex/function/lyric_pick.mcfunction"), "w", encoding="utf-8", newline="\n") as f:
        # The storage path needs a space, not a dot: "deusex:lyrics.list" parses
        # the whole thing as the resource location and then fails on ".list[...]".
        f.write("$data modify storage deusex:data lyr set from storage deusex:lyrics list[$(i)]\n")

    print("lines", n, "atlas", atlas.shape, "max width ok")
    return rows, cells


if __name__ == "__main__":
    build_font()
