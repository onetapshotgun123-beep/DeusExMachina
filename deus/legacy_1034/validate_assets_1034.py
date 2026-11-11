import json
import math
import os
import re
import sys

import soundfile as sf
from PIL import Image

import mclog

ROOT = os.path.dirname(os.path.abspath(__file__))
EXT = os.environ.get("DEUS_EXT") or os.path.join(ROOT, "extracted")
FUN = os.path.join(EXT, "data/deusex/function")
ASSETS = os.path.join(EXT, "assets/deusex")

errors = []
warns = []

# ---------- function references ----------
funcs = {os.path.splitext(f)[0] for f in os.listdir(FUN) if f.endswith(".mcfunction")}
macro_vars = {}
sets_in_data = set()
for f in sorted(funcs):
    path = os.path.join(FUN, f + ".mcfunction")
    text = open(path, encoding="utf-8").read()
    refs = re.findall(r"(?<![-:\w])function deusex:([a-z0-9_]+)", text)
    for r in refs:
        if r not in funcs:
            errors.append("missing function deusex:%s (in %s)" % (r, f))
    for line in text.splitlines():
        if line.startswith("$"):
            for v in re.findall(r"\$\(([a-z0-9_]+)\)", line):
                macro_vars.setdefault(f, set()).add(v)
        m = re.search(r"storage deusex:data ([a-z0-9_]+) set", line)
        if m:
            sets_in_data.add(m.group(1))
        m = re.search(r"store result storage deusex:data ([a-z0-9_]+)", line)
        if m:
            sets_in_data.add(m.group(1))
        m = re.search(r"data merge storage deusex:data \{([^}]*)\}", line)
        if m:
            for k in re.findall(r"([a-z0-9_]+):", m.group(1)):
                sets_in_data.add(k)
        if re.search(r"function deusex:(\w+) with storage", line) and line.strip().startswith("$"):
            errors.append("macro call with storage on a macro line in %s" % f)

with_call = set(re.findall(r"function deusex:(\w+) with storage deusex:data", "\n".join(
    open(os.path.join(FUN, f + ".mcfunction"), encoding="utf-8").read() for f in funcs)))
for f, vs in macro_vars.items():
    missing = vs - sets_in_data
    if missing:
        errors.append("macro %s uses never-set keys %s" % (f, sorted(missing)))
    if f not in with_call:
        errors.append("macro function %s is never called with storage" % f)
for f in funcs:
    txt = open(os.path.join(FUN, f + ".mcfunction"), encoding="utf-8").read()
    if re.search(r"function deusex:" + f + r"(?! with)", txt):
        warns.append("plain self/call reference to macro? %s" % f)

# ---------- sounds ----------
sounds = json.load(open(os.path.join(ASSETS, "sounds.json"), encoding="utf-8"))
for f in funcs:
    txt = open(os.path.join(FUN, f + ".mcfunction"), encoding="utf-8").read()
    for snd in re.findall(r"playsound (deusex:[a-z0-9_]+)", txt):
        if snd.endswith("_"):
            continue
        if snd.split(":")[1] not in sounds:
            errors.append("missing sound %s (in %s)" % (snd, f))
    # @s master, not only @a *: opening_burst cuts the heartbeat for the player the command is
    # running as, and a mistyped event name there fails silently rather than loudly.
    for snd in re.findall(r"stopsound (?:@a|@s) (?:\*|\w+) (deusex:[a-z0-9_]+)", txt):
        if snd.endswith("_"):
            continue
        if snd.split(":")[1] not in sounds:
            errors.append("missing stopsound %s (in %s)" % (snd, f))

# ---------- fonts ----------
def load_font(name):
    d = json.load(open(os.path.join(ASSETS, "font", name + ".json"), encoding="utf-8"))
    adv = {}
    for p in d["providers"]:
        if p["type"] == "space":
            for k, v in p["advances"].items():
                adv[ord(k)] = v
            continue
        path = os.path.join(ASSETS, "textures", p["file"].replace("deusex:", ""))
        im = Image.open(path)
        g = p["chars"]
        rows, cols = len(g), len(g[0])
        if any(len(r) != cols for r in g):
            errors.append("ragged chars grid in %s" % name)
        if p["ascent"] > p["height"]:
            # BitmapProvider.Definition.validate() turns this into a DataResult
            # error, the whole provider is dropped and every glyph renders as [].
            errors.append("font %s: ascent %d > height %d" % (name, p["ascent"], p["height"]))
        cw, ch = im.width // cols, im.height // rows
        if cw > 256 or ch > 256:
            # FontTexture pages are 256x256 and Node.insert() returns null for anything
            # wider or taller, so the glyph is never uploaded and stitch() hands back
            # SpecialGlyphs.MISSING - a [] on screen. Grow the provider "height" instead.
            errors.append("font %s glyph cell %dx%d exceeds the 256px atlas page" % (name, cw, ch))
        sc = p["height"] / ch
        alpha = im.split()[-1].load()
        for r in range(rows):
            for c, cp in enumerate(g[r]):
                if ord(cp) in adv:
                    errors.append("duplicate codepoint in font %s" % name)
                w = 0
                for x in range(cw - 1, -1, -1):
                    if any(alpha[c * cw + x, r * ch + y] for y in range(ch)):
                        w = x + 1
                        break
                adv[ord(cp)] = int(0.5 + w * sc) + 1
    return adv, d

FONT = {n: load_font(n) for n in [
    "space", "tspace", "box", "hud_text", "hud_v0", "hud_v1", "hud_v2", "hud_v3",
    "hud_v4", "hud_c", "fx", "lyric", "burst", "skyglow", "skyred"]}
for n, (adv, _) in FONT.items():
    print("font %-9s glyphs %4d" % (n, len(adv)))

# ---------- actionbar/title macro JSON ----------
PRESET = {"bx": "\ue300", "bsp": "", "bsn": "", "dsp": "", "dsn": "", "tsp": "", "tsn": "",
          "df": "deusex:hud_v0", "tc": "white", "g": "\ue200", "lyr": "\ue900",
          "b": "\ue700", "rc": "\ue400", "heart": "\ue500", "burst": "\ue520"}
def check_json_func(f, default_font="minecraft:default"):
    txt = open(os.path.join(FUN, f + ".mcfunction"), encoding="utf-8").read()
    start = min((i for i in (txt.find("["), txt.find("{")) if i >= 0), default=-1)
    if start < 0:
        return None
    raw = txt[start:]
    raw = re.sub(r"\$\(([a-z0-9_]+)\)", lambda m: PRESET.get(m.group(1), ""), raw)
    try:
        j = json.loads(raw)
    except Exception as e:
        errors.append("%s: bad JSON: %s" % (f, e))
        return None
    W = 0
    if isinstance(j, dict):
        j = [j]
    for el in j:
        if isinstance(el, str):
            continue
        font = el.get("font", default_font).replace("deusex:", "")
        if font == "minecraft:default":
            continue
        if font not in FONT:
            errors.append("%s: unknown font %s" % (f, font))
            continue
        if "score" in el:
            W += 6
            continue
        for c in el.get("text", ""):
            if ord(c) not in FONT[font][0]:
                errors.append("%s: char %04x missing from font %s" % (f, ord(c), font))
            W += FONT[font][0].get(ord(c), 0)
    return W

for f in ["hud_show", "hud_show_box", "lyric_only", "title_red",
          "title_hb", "title_red_burst", "title_black", "title_white", "hud_clear", "hud_show_c"]:
    W = check_json_func(f)
    print("string %-16s width %s" % (f, W))

# ---------- the lyric has to sit still ----------
# The actionbar centres the whole line, so the lyric's own centre lands at
# (advance before it - advance after it) / 2 - the widget in front of it is what moves it. hud_tick
# repaints every 2 ticks and hud_draw rolls #p 1..10 while the burst runs, and #p 8 drops the disc
# entirely (mode 2, lyric_only). If that frame does not put the word at the same offset as the two
# frames that carry the widget, the line jumps sideways on every glitch, which is exactly what the
# player sees. Score elements use the same flat 6 px the widths above do; the scrambled digits of
# presets 3 and 9 wobble that by under a pixel, which is not what this is about.
def lyric_offset(f):
    """Px from the actionbar's centre to the lyric's, for one emit line at the default preset."""
    txt = open(os.path.join(FUN, f + ".mcfunction"), encoding="utf-8").read()
    at = [i for i in (txt.find("["), txt.find("{")) if i >= 0]
    if not at:
        return None
    raw = re.sub(r"\$\(([a-z0-9_]+)\)",
                 lambda m: m.group(0) if m.group(1) == "lyr" else PRESET.get(m.group(1), ""),
                 txt[min(at):])
    try:
        els = json.loads(raw)
    except Exception:
        return None
    acc, centre = 0, None
    for el in els:
        if not isinstance(el, dict):
            continue
        font = el.get("font", "minecraft:default").replace("deusex:", "")
        if "score" in el:
            acc += 6
            continue
        if font == "minecraft:default" or font not in FONT:
            continue
        adv = FONT[font][0]
        text = el.get("text", "")
        if "$(lyr)" in text:
            head, tail = text.split("$(lyr)", 1)
            centre = (acc + sum(adv.get(ord(c), 0) for c in head),
                      sum(adv.get(ord(c), 0) for c in tail))
            acc = 0
            continue
        if centre is None:
            acc += sum(adv.get(ord(c), 0) for c in text)
        else:
            centre = (centre[0], centre[1] + sum(adv.get(ord(c), 0) for c in text))
    if centre is None:
        return None
    return (centre[0] - centre[1]) / 2.0


CENTRE = {}
for f in ["hud_show", "hud_show_box", "lyric_only"]:
    o = lyric_offset(f)
    if o is None:
        errors.append("%s carries no $(lyr), so hud_emit cannot show the word" % f)
    else:
        CENTRE[f] = o
print("lyric centre %s" % ", ".join("%s %+.1f px" % (k, v) for k, v in sorted(CENTRE.items())))
if len(CENTRE) > 1 and max(CENTRE.values()) - min(CENTRE.values()) > 1.0:
    worst = sorted(CENTRE.items(), key=lambda kv: -abs(kv[1] - sum(CENTRE.values()) / len(CENTRE)))
    errors.append("the lyric is not static: %s - the glitch frames that drop the disc move the word "
                  "sideways, which is what 'make the lyric not move' is about"
                  % ", ".join("%s is at %+.1f px" % (k, v) for k, v in CENTRE.items()))

# ---------- lyrics ----------
lrc = open(os.path.join(FUN, "lyric_tick.mcfunction"), encoding="utf-8").read()
starts = [int(x) for x in re.findall(r"scoreboard players set #lstart deusex (\d+)", lrc)]
if starts != sorted(starts):
    errors.append("lyric starts not increasing")
if len(starts) != 74:
    errors.append("expected 74 lyric windows, got %d" % len(starts))
init = open(os.path.join(FUN, "lyrics_init.mcfunction"), encoding="utf-8").read()
glyphs = re.findall(r'"(.)"', init)
print("lyric window starts %d..%d ticks, glyph entries %d" % (starts[0], starts[-1], len(glyphs)))
lyrfont = FONT["lyric"][0]
for g in glyphs:
    if ord(g) not in lyrfont:
        errors.append("lyrics_init glyph %04x missing" % ord(g))
        break
# every glyph used by lyric_tick index math must exist: indices 0..443
for idx in range(444):
    if not (0xE900 + idx) in lyrfont:
        errors.append("lyric atlas missing index %d" % idx)
        break

# ---------- lyric windows vs the singing ----------
# The window shape above can be perfect while the words still arrive a second before the voice:
# the raw LRC's final-chorus times were 0.6-1.1 s early and nothing in the pack could see it.
# Sample the vocal-band onset flux at every window start of a section, shifted by a common lag:
# the lag that maximises the mean is how much later the singing sits than that section's windows.
# A section whose peak is both big (|lag| > 0.5 s) and stronger than a shuffled-times null is out
# of sync with the recording it ships with. The ~+0.2-0.3 s bias of a perfect section (flux peaks a
# little after the consonant) is why the band is 0.5 and not 0. The flux is smoothed over 0.12 s:
# narrower and the comb jumps on the windows' own 0.05 s tick quantisation, wider and the peak
# washes out below the null.
import numpy as np
y, sr = sf.read(os.path.join(ASSETS, "sounds", "main_track.ogg"), dtype="float32")
if y.ndim > 1:
    y = y.mean(axis=1)
WIN, HOP = 2048, 512
nfr = 1 + max(0, (len(y) - WIN) // HOP)
w = np.hanning(WIN)
fr = np.fft.rfftfreq(WIN, 1.0 / sr)
band = (fr >= 300) & (fr <= 3400)
e = np.empty(nfr)
for i in range(nfr):
    s = y[i * HOP:i * HOP + WIN] * w
    e[i] = (np.abs(np.fft.rfft(s))[band] ** 2).mean()
ft = (np.arange(nfr) * HOP + WIN / 2.0) / sr
flux = np.concatenate([np.maximum(0.0, np.diff(e)), [0.0]])
k = int(round(0.12 * sr / HOP))
flux = np.convolve(flux, np.ones(k) / k, mode="same")
lags = np.arange(-2.0, 2.001, 0.02)


def comb(times):
    idx = np.clip(np.round((np.asarray(times)[:, None] + lags[None, :] - ft[0]) * sr / HOP
                           ).astype(int), 0, len(flux) - 1)
    return flux[idx].mean(axis=0)


secs = [s / 20.0 for s in starts]
rng = np.random.default_rng(11)
for name, a, b in [("verse1+chorus1", 0, 135), ("verse2+chorus2", 135, 220),
                   ("bridge", 300, 344), ("final A", 400, 455), ("final B", 455, 546)]:
    ts = [s for s in secs if a <= s < b]
    if not ts:
        errors.append("lyric sync section %s has no windows" % name)
        continue
    c = comb(ts)
    z = (c - c.mean()) / c.std()
    best = lags[int(np.argmax(z))]
    nulls = []
    for _ in range(60):
        sh = np.sort(rng.uniform(min(ts), max(ts), len(ts)))
        cc = comb(sh)
        nulls.append(((cc - c.mean()) / c.std()).max())
    print("lyric sync %-14s n=%2d lag %+.2f s (z=%.2f, null 90th %.2f)"
          % (name, len(ts), best, z.max(), np.percentile(nulls, 90)))
    if abs(best) > 0.5 and z.max() > np.percentile(nulls, 90):
        errors.append("lyric section %s sits %+.2f s away from the singing (z=%.2f beats the "
                      "shuffled null): the windows are early/late against the shipped recording"
                      % (name, best, z.max()))

# ---------- audio clock ----------
# The lyric and lyric-fade timings above are all derived from #E = #idx * 60 + #t, which is only
# true if every chunk is exactly three seconds of audio and the chunk set is the same recording as
# main_track. Re-encoding or re-cutting the audio silently breaks the sync, so the frames are read
# out of the shipped files rather than assumed.
snd_dir = os.path.join(ASSETS, "sounds")
names = [f for f in os.listdir(snd_dir) if f.startswith("chunk_")]
for key, ent in sounds.items():
    for prov in ent.get("sounds", []):
        rel = (prov["name"] if isinstance(prov, dict) and "name" in prov else key)
        if rel.startswith("deusex:"):
            rel = rel.split(":")[1]
        if not os.path.isfile(os.path.join(snd_dir, rel + ".ogg")):
            errors.append("sounds.json %s points at deusex:%s.ogg, which is not in the pack"
                          % (key, rel))
loadtxt0 = open(os.path.join(FUN, "load.mcfunction"), encoding="utf-8").read()
nlast = int(re.search(r"scoreboard players set #last deusex (-?\d+)", loadtxt0).group(1))
ltick = int(re.search(r"scoreboard players set #lastlen deusex (-?\d+)", loadtxt0).group(1))
total = 0
off = 0
for i in range(nlast + 1):
    info = sf.info(os.path.join(snd_dir, "chunk_%d.ogg" % i))
    total += info.frames
    ticks = info.frames / float(info.samplerate) * 20.0
    if i == nlast:
        # The last chunk is whatever length the song happens to be (58.49 ticks here) and #lastlen is
        # the tick at which it hands over to `finish`, so it is rounded up: rounding down would cut
        # the tail off the ending. It has to sit in that one-tick window.
        if not ticks <= ltick < ticks + 1:
            off += 1
            errors.append("chunk_%d runs %.2f ticks but #lastlen is %d: the ending is either cut "
                          "short or held as silence" % (i, ticks, ltick))
        continue
    if abs(ticks - 60.0) > 0.5:
        off += 1
        errors.append("chunk_%d is %.2f ticks, and the clock assumes 60: the lyric timing list is "
                      "built on #E = #idx * 60 + #t" % (i, ticks))
    if info.samplerate != 44100 or info.channels != 2:
        errors.append("chunk_%d is %d Hz / %d ch, not the 44100 Hz stereo the rest is"
                      % (i, info.samplerate, info.channels))
full = sf.info(os.path.join(snd_dir, "main_track.ogg"))
mb = lambda fs: sum(os.path.getsize(os.path.join(snd_dir, f)) for f in fs) / 1048576.0
print("audio %d chunks (%.1f MB) + main_track (%.1f MB), %.2f s of song, %d chunks off the "
      "60-tick grid" % (nlast + 1, mb(names), mb(["main_track.ogg"]),
                        full.frames / float(full.samplerate), off))
if abs(full.frames - total) > full.samplerate / 2:
    errors.append("main_track is %d frames and the chunks total %d: the resume path and the full "
                  "playback are different recordings" % (full.frames, total))

# ---------- random red sky flash ----------
# The sky is the 1.0.18 picture, ported: three panels per player (broad glow, hot core, red flare)
# on a 22 frame envelope, forced rain, and the veil wash underneath it. Four client-side things
# still have to be right or none of it shows:
#   * DisplayRenderer.render uses `int j = i != -1 ? i : packedLight`, so without a brightness
#     override the glyph is multiplied by the world lightmap and renders near black.
#   * view_range scales the 64 block cull radius, so the default 1.0 culls a panel 54 blocks out.
#   * a summon into an unloaded chunk reports success and then drops the entity, so every tier
#     needs its fallback inside a 2 chunk ticking area.
#   * billboard "vertical" keeps it world-upright and see_through 0b lets terrain occlude the low
#     edge, which is what stops it reading as a rectangle pasted over the world.
# /execute rotated takes <yaw> <pitch> - the same order as the entity Rotation NBT, where Rotation[0]
# is the yaw flash_rand jitters by +-30. So `rotated $(yaw) 0` aims the panel where the player is
# looking and flattens the drop onto the horizon. The mirror form `rotated 0 ~` pins the yaw to due
# south and inherits the player's pitch instead: the panel lands behind them unless they happen to
# face south, and under the floor whenever they look down. 1.0.19, 1.0.20 and 1.0.21 all shipped
# that second form because this file required it, on a wrong reading of the argument order - which
# is exactly how three builds passed the whole soak while the user reported a plain blue sky.
FLASHLINE = re.compile(
    r"^\$execute rotated \$\(yaw\) 0 if score #sr deusex matches (\d+) (if|unless) loaded "
    r"\^ \^ \^(\d+) run summon minecraft:text_display \^ \^ \^(\d+) (\{.*\})$")
# which glyph sheet each layer draws, and the tag that names it in the envelope
LAYERS = {"deusex_fglow": "skyglow", "deusex_fcore": "skyglow", "deusex_fflare": "skyred"}

# The storm mechanic is still gone: no lightning entity, no thunder audio, no /weather thunder and
# none of the functions that drove them. That ban reads executable lines only - a comment is allowed
# to name the dead mechanic to explain why it went - and `weather rain` moved from the forbidden list
# to a requirement: rain is the sound, the wet sheen, the splash particles and FogRenderer's
# darkening, and the pack's own red rain.png paints every drop of it while the song runs. 1.0.19
# cleared the weather instead of forcing it and deleted the whole effect.
DEAD = ("#skygo", "#skyc", "#skymax", "deusex_sky", "sky_tick", "sky_spawn", "sky_frame",
        "sky_rand", "sky_player", "sky_end", "storm_run", "storm_strike", "storm_tick",
        "hud_sky", "opening_hold", "minecraft:entity.lightning_bolt", "weather thunder")

dead = []
for f in sorted(funcs):
    txt = open(os.path.join(FUN, f + ".mcfunction"), encoding="utf-8").read()
    live = "\n".join(l for l in txt.splitlines() if not l.strip().startswith("#"))
    for w in DEAD:
        if w in live:
            dead.append("%s still references %s" % (f, w))
    # A line that starts with $ is a macro line, and the server rejects a macro line with no
    # $(...) in it - "Macro without variables" - which silently drops the *whole* function. The
    # flash spawn lines carried a leftover $ like that and the sky glow never appeared, so this
    # is checked for every function rather than only the ones being worked on.
    for i, line in enumerate(txt.splitlines(), 1):
        s = line.strip()
        if s.startswith("$") and "$(" not in s:
            errors.append("%s:%d is a macro line with no $(...) - the server will refuse to "
                          "load the function" % (f, i))
        if "$(" in s and not s.startswith("$"):
            errors.append("%s:%d uses $(...) without the leading $" % (f, i))
for w in ("sky_spawn", "sky_frame", "sky_tick", "sky_rand", "sky_player", "sky_end",
          "storm_run", "storm_strike", "storm_tick", "hud_sky", "opening_hold"):
    if w in funcs:
        dead.append("%s.mcfunction should have been deleted with the lightning" % w)
errors += dead
print("storm mechanic removed: %d functions, %d leftovers" % (len(funcs), len(dead)))

# The blood rain has to actually start somewhere, and it has to start EARLY. opening_rain is the only
# place that can force the weather and the ending is the only place allowed to stop it, but where the
# command sits is the whole question: ServerLevel.advanceWeatherCycle moves rainLevel by 0.01F a tick
# and clamps at 1.0, and LevelRenderer.renderSnowAndRain multiplies every drop's alpha by that level
# (line 339: f7 = ((1 - d^2) * 0.5 + 0.5) * rainLevel), so a storm forced on the drop tick is 1%
# visible on the drop tick and arrives five seconds late. That lag is what "the rain was a bit delayed
# after the heart explode" describes, and the fix is a lead, not a faster ramp - there is no command
# that jumps the level.
oburst = open(os.path.join(FUN, "opening_burst.mcfunction"), encoding="utf-8").read()
orain = open(os.path.join(FUN, "opening_rain.mcfunction"), encoding="utf-8").read()
if not re.search(r"^weather rain \d+$", orain, re.M):
    errors.append("opening_rain does not force the rain: with the world dry there is no downpour at "
                  "all - no sound, no wet sheen, no splash, and above all no drops for the red "
                  "rain.png sheet to paint")
if "scoreboard players set #rain deusex 1" not in orain:
    errors.append("opening_rain makes it rain without arming #rain, so the pack can no longer tell "
                  "its own downpour from one the world started - and the veil, the red sheet and the "
                  "weather gate all hang off that flag")
elif orain.index("weather rain") > orain.index("scoreboard players set #rain deusex 1"):
    errors.append("opening_rain arms #rain before it sets the weather: if the weather command is ever "
                  "cut short the flag says the show owns a sky it never started, and tick's idle gate "
                  "will not clear it")
# The lag only goes away if the burst itself stopped being the thing that starts the storm.
if re.search(r"^weather rain \d+$", oburst, re.M) or "#rain deusex 1" in oburst:
    errors.append("opening_burst forces the weather again: the 0.01-a-tick ramp needs 100 ticks, so a "
                  "storm started on the drop tick is still 1% wet when the player is watching for it. "
                  "opening_rain, fired #rainlead ticks ahead, is the only place that may do it")

# The lead has to be long enough to cover the ramp, and it has to be measured off #drop rather than
# written twice, or the two drift apart the next time the anchor moves.
RAIN_RAMP = 100                       # ServerLevel.java:705-712, 0.01F a tick to a clamp at 1.0
# rdrop is read here rather than inside the replay because the proof line at the bottom prints it
# whatever path the block takes: a rule that has already recorded an error returns early, and a
# `%d` on None turned those regressions into a traceback instead of a report.
mrd = re.search(r"^scoreboard players set #drop deusex (\d+)$", loadtxt0, re.M)
rdrop = int(mrd.group(1)) if mrd else None
RAIN_LEAD, fires = None, []
if mrd is None:
    errors.append("load.mcfunction does not set #drop, so nothing here can say how long the "
                  "run-up is or when the storm has to be armed")
ml = re.search(r"^scoreboard players operation #rainlead deusex = #drop deusex$", loadtxt0, re.M)
mn = re.search(r"^scoreboard players remove #rainlead deusex (\d+)$", loadtxt0, re.M)
if not (ml and mn):
    errors.append("load.mcfunction does not derive #rainlead from #drop, so the storm's run-up and "
                  "the drop anchor are two numbers to keep in step instead of one")
else:
    RAIN_LEAD = int(mn.group(1))
    if RAIN_LEAD < RAIN_RAMP:
        errors.append("#rainlead is #drop minus %d, which is shorter than the %d tick rain ramp: the "
                      "downpour would still be climbing on the tick the heart bursts"
                      % (RAIN_LEAD, RAIN_RAMP))
    gate = ("execute if score #ostage deusex matches 2 if score #rain deusex matches 0 "
            "if score #E deusex >= #rainlead deusex run function deusex:opening_rain")
    otickx = open(os.path.join(FUN, "opening_tick.mcfunction"), encoding="utf-8").read()
    if gate not in otickx:
        errors.append("opening_tick does not fire opening_rain on #E >= #rainlead while #rain is 0, "
                      "so the storm either never starts or starts again every tick")
    elif otickx.find("function deusex:opening_burst") < 0:
        errors.append("opening_tick no longer calls opening_burst, so there is no drop for the "
                      "storm's run-up to be measured against")
    elif otickx.index(gate) > otickx.index("function deusex:opening_burst"):
        errors.append("opening_tick arms the rain after the burst line, which is the tick the "
                      "explosion is already on screen - the lead would be spent on the wrong side")
    elif rdrop is not None:
        # "Exactly once, on the right tick" cannot be read out of the soak log: the server only echoes
        # the result of the command it was handed, so a `weather rain` nested two functions deep prints
        # nothing (soak43 lines 8898-8917: the flag moves and no weather line follows). Walk the gate
        # instead - #idx and #t, because opening_tick recomputes #E from them - and count the calls.
        rlead = rdrop - RAIN_LEAD
        rs = {k: int(v) for k, v in
              re.findall(r"scoreboard players set (#\S+) deusex (-?\d+)", loadtxt0)}
        rs.update({"#drop": rdrop, "#rainlead": rlead, "#state": 1, "#cstate": 0, "#ostage": 2,
                   "#rain": 0, "#idx": 0, "#t": 0, "#E": 0, "#hb": 99, "#hbE": 0, "#k": 0, "#bf": 0})
        fires = []
        for e in range(rdrop + 30):
            rs["#idx"], rs["#t"] = e // 60, e % 60
            rl = []
            mclog.run("opening_tick", rs, rl)
            if any(c == "opening_rain" for k, f, c, v in rl):
                fires.append(e)
        if fires != [rlead]:
            errors.append("the storm is armed at #E %s, not once on #rainlead %d: %s"
                          % (fires, rlead,
                             "the downpour would still be climbing on the drop" if not fires else
                             "a second weather command on the show's own tail is the same bug as the "
                             "red sheet being unconditional"))
        elif rs["#rain"] != 1:
            errors.append("opening_rain ran but #rain is %s on the drop tick, so tick's idle gate "
                          "takes the sky back to plain Minecraft mid-song" % rs["#rain"])
        elif rs["#ostage"] != 3:
            errors.append("the run-up replay never reached #ostage 3, so the burst is not being "
                          "driven by the clock this walk is checking")
for name in ("closing_start", "halt"):
    if "weather clear" not in open(os.path.join(FUN, name + ".mcfunction"), encoding="utf-8").read():
        errors.append("%s leaves the world raining after the song ends or is halted - a forced "
                      "downpour the player cannot switch off is the same class of bug as the red "
                      "sheet was" % name)
if fires and rdrop is not None and RAIN_LEAD is not None:
    print("blood rain armed %d ticks before the drop (needs %d): opening_rain called at #E %s of "
          "the walk-up to %d, cleared by closing_start and halt"
          % (RAIN_LEAD, RAIN_RAMP, fires, rdrop))
else:
    # The gate replay only runs once every shape rule above has passed, so getting here means one of
    # them failed and errors already says which. Printing the numbers anyway would be the `%d` on
    # None that turned these regressions into a traceback.
    print("blood rain lead: not measured, the rules above reported why")

fspawn = open(os.path.join(FUN, "flash_spawn.mcfunction"), encoding="utf-8").read()
flines = [l for l in fspawn.splitlines() if l.startswith("$execute rotated")]
if len(flines) != 24:
    errors.append("flash_spawn should hold 4 flare variants x 3 layers x (loaded, fallback) = 24 "
                  "macro lines, got %d" % len(flines))
parsed = []
for i, line in enumerate(flines):
    m = FLASHLINE.match(line)
    if not m:
        errors.append("flash_spawn line %d is not a yaw-from-the-player, pitch-flattened, "
                      "loaded-gated summon: %s" % (i, line[:80]))
        continue
    var, gate, gdist, dist, body = (int(m.group(1)), m.group(2), int(m.group(3)),
                                    int(m.group(4)), m.group(5))
    tags = re.findall(r'"(deusex_\w+)"', body)
    if "deusex_flash" not in tags:
        errors.append("flash_spawn line %d is not tagged deusex_flash, so nothing kills it" % i)
    layer = [t for t in tags if t != "deusex_flash"]
    if len(layer) != 1 or layer[0] not in LAYERS:
        errors.append("flash_spawn line %d tags %s: exactly one of %s has to name the layer, or "
                      "the envelope cannot fade it" % (i, tags, sorted(LAYERS)))
        continue
    layer = layer[0]
    comp = json.loads(re.search(r"text:'(\{.*?\})'", body).group(1))
    font = comp.get("font", "").replace("deusex:", "")
    if font != LAYERS[layer]:
        errors.append("flash_spawn %s draws font %s, expected deusex:%s"
                      % (layer, comp.get("font"), LAYERS[layer]))
    elif ord(comp["text"]) not in FONT[font][0]:
        errors.append("flash_spawn glyph %04x missing from %s" % (ord(comp["text"]), font))
    if "brightness:{block:15,sky:15}" not in body:
        errors.append("flash_spawn line %d has no brightness override: the lightmap multiplies "
                      "the panel to near black" % i)
    if "view_range:4.0f" not in body:
        errors.append("flash_spawn line %d is culled: view_range scales the 64 block radius" % i)
    if 'billboard:"vertical"' not in body or "see_through:0b" not in body:
        errors.append("flash_spawn line %d is not a terrain-occluded vertical billboard, so it "
                      "pastes over the world" % i)
    for a_ in re.findall(r"text_opacity:(-?\d+)b", body):
        if not -128 <= int(a_) <= 127:
            errors.append("flash_spawn line %d text_opacity %s is not a valid SNBT byte" % (i, a_))
    f_ = lambda t: float(t.rstrip("f"))
    tr = [f_(x) for x in re.search(r"translation:\[([-0-9.f]+),([-0-9.f]+),0\.0f\]", body).group(1, 2)]
    sc = [f_(x) for x in re.search(r"scale:\[([-0-9.f]+),([-0-9.f]+),", body).group(1, 2)]
    parsed.append({"i": i, "var": var, "layer": layer, "gate": gate, "gdist": gdist, "dist": dist,
                   "tr": tr, "sc": sc, "font": font, "glyph": comp["text"],
                   "op": int(re.search(r"text_opacity:(-?\d+)b", body).group(1)) % 256})

# Four flare variants, three layers each, and a near copy of every variant for the case where the
# chunk 54..88 blocks out has not loaded. One gate per variant, at the distance the farthest layer
# needs: if each layer tested its own chunk, a partially loaded sky would show the glow and drop the
# flare, which is the difference between a red sky and a red smudge.
ORDER = ["deusex_fglow", "deusex_fcore", "deusex_fflare"]
for var in sorted(set(p["var"] for p in parsed)):
    for gate in ("if", "unless"):
        group = [p for p in parsed if p["var"] == var and p["gate"] == gate]
        if [p["layer"] for p in sorted(group, key=lambda p: -p["dist"])] != ORDER:
            errors.append("flash_spawn variant %d %s-loaded puts the layers at %s: the glow has to "
                          "be farthest, then the core, then the flare, or the flare draws in front "
                          "of the glow it is supposed to sit inside"
                          % (var, gate, [(p["layer"], p["dist"]) for p in
                                         sorted(group, key=lambda p: -p["dist"])]))
        gates = set(p["gdist"] for p in group)
        if len(gates) != 1:
            errors.append("flash_spawn variant %d %s-loaded gates on %s, not one distance"
                          % (var, gate, sorted(gates)))
        elif group and gate == "if" and gates != {max(p["dist"] for p in group)}:
            errors.append("flash_spawn variant %d tests chunk %s but its farthest layer sits at %d"
                          % (var, sorted(gates), max(p["dist"] for p in group)))
    loaded = [p for p in parsed if p["var"] == var and p["gate"] == "if"]
    back = [p for p in parsed if p["var"] == var and p["gate"] == "unless"]
    if loaded and back:
        if any(p["dist"] > 40 for p in back):
            errors.append("flash_spawn variant %d falls back to %d blocks, outside a 2 chunk "
                          "ticking area" % (var, max(p["dist"] for p in back)))
        # Both branches ask about the *same* chunk - the one the farthest panel sits in - and only
        # differ in how far out they place it. If the fallback tested a nearer chunk there is a
        # window where neither branch fires: the far chunk is unloaded so `if loaded` is skipped,
        # and the near chunk is loaded so `unless loaded` is skipped too, and the flash is a plain
        # sky. If they asked about different chunks the pair could also both fire and stack two
        # panels on one player.
        asked = set(p["gdist"] for p in loaded) | set(p["gdist"] for p in back)
        if len(asked) != 1:
            errors.append("flash_spawn variant %d has a fallback that tests chunk %s while the "
                          "panel tests %s: on a partially loaded sky neither branch would fire and "
                          "the flash shows nothing, or both fire and the panel doubles"
                          % (var, sorted(set(p["gdist"] for p in back)),
                             sorted(set(p["gdist"] for p in loaded))))
print("flash_spawn: variants %s, layers %s, loaded tiers up to %d blocks, fallbacks up to %d"
      % (sorted(set(p["var"] for p in parsed)), ORDER,
         max([p["dist"] for p in parsed if p["gate"] == "if"] or [0]),
         max([p["dist"] for p in parsed if p["gate"] == "unless"] or [0])))

# The panel has to be bigger than the view. A 70 degree FOV shows +-35 horizontally and
# +-21.3 vertically at 16:9; if either edge of the quad lands inside that arc the player sees
# the corner of a floating rectangle, which is exactly what the old strike did.
UNIT, EYE, FOV_H = 0.025, 1.62, 70.0
TAN_H = math.tan(math.radians(FOV_H / 2.0))
TAN_V = TAN_H * 9.0 / 16.0


def quad_units(font):
    """Drawn width, height and the vertical box of one cell, in font units."""
    prov = [pp for pp in FONT[font][1]["providers"] if pp["type"] != "space"][0]
    im = Image.open(os.path.join(ASSETS, "textures", prov["file"].split(":")[1]))
    sc_ = prov["height"] / (im.height // len(prov["chars"]))
    h = prov["height"]
    return {"w": im.width // len(prov["chars"][0]) * sc_, "h": h,
            "top": prov["ascent"] + 3, "bottom": prov["ascent"] + 3 - h}


for p in parsed:
    q = quad_units(p["font"])
    wide = UNIT * p["sc"][0] * q["w"]
    half = UNIT * p["sc"][1] * q["h"] / 2.0
    mid = p["tr"][1] + UNIT * p["sc"][1] * 0.5 * (q["top"] + q["bottom"])
    p["side"] = math.degrees(math.atan(wide / 2.0 / p["dist"]))
    p["top"] = math.degrees(math.atan2(mid + half - EYE, p["dist"]))
    p["foot"] = math.degrees(math.atan2(mid - half - EYE, p["dist"]))
    print("flash v%d %-13s %s %2d blocks: +-%.0f deg sideways, %.1f..%.1f deg high, op %d"
          % (p["var"], p["layer"], p["gate"], p["dist"], p["side"], p["foot"], p["top"], p["op"]))

# Only the glow has to be bigger than the view: it is the layer that makes the whole sky red, and a
# rectangle whose edge lands inside a 70 degree FOV reads as a decal - which is what the old strike
# looked like. The core and the flare are deliberately smaller and sit in front of it, so their job
# is the hot centre, not the coverage; what is checked on them is that they are not so small that
# they disappear, and that nothing reaches full brightness as a speck.
for p in parsed:
    if p["layer"] == "deusex_fglow":
        if p["side"] < 36.0:
            errors.append("flash v%d %s glow only reaches %.1f deg sideways: the screen edge of the "
                          "quad is inside a 70 degree view" % (p["var"], p["gate"], p["side"]))
        if p["top"] < 24.0:
            errors.append("flash v%d %s glow tops out at %.1f deg: it fits under the top of the view "
                          "and reads as a decal" % (p["var"], p["gate"], p["top"]))
        if p["foot"] > 0.0:
            errors.append("flash v%d %s glow floats %.1f deg above the horizon, so terrain never "
                          "clips its foot" % (p["var"], p["gate"], p["foot"]))
    elif p["side"] < 6.0:
        errors.append("flash v%d %s layer %s is only %.1f deg wide: nothing of that size reads as "
                      "part of the sky" % (p["var"], p["gate"], p["layer"], p["side"]))

# the envelope: replay flash_tick with the shipped score maths and read the alphas back out.
fbegin = open(os.path.join(FUN, "flash_begin.mcfunction"), encoding="utf-8").read()
fframe = open(os.path.join(FUN, "flash_tick.mcfunction"), encoding="utf-8").read()
fbody = open(os.path.join(FUN, "flash_frame.mcfunction"), encoding="utf-8").read()
# The delay is computed, not rolled. /random, /time and anything with a @e selector throws "An
# unexpected error occurred" in the headless soak because the console source has no level, so a
# function that used them never reached the line that arms the envelope. The range therefore has to
# be proved from the fold - `%= width`, a fix-up for the negative remainder, `+ base` - and from the
# replay below, which runs the shipped arithmetic.
mmod = re.search(r"scoreboard players operation #flashd deusex %= #(\d+) deusex", fbegin)
mfix = re.search(r"execute if score #flashd deusex matches \.\.-1 run "
                 r"scoreboard players add #flashd deusex (\d+)", fbegin)
mlast = [l for l in fbegin.splitlines()
         if re.match(r"scoreboard players add #flashd deusex \d+$", l.strip())]
# the constants the fold needs have to actually be set somewhere, or the operations silently fail
loadtxt = open(os.path.join(FUN, "load.mcfunction"), encoding="utf-8").read()
CONST = dict(re.findall(r"scoreboard players set (#\S+) deusex (-?\d+)", loadtxt))
if "random value" in fbegin or "random roll" in fbegin or "time query" in fbegin:
    errors.append("flash_begin reads a level-dependent command: the tick loop's console source "
                  "has no level, so the line throws and the flash stops rearming")
elif "execute unless score #lcg deusex = #lcg deusex run" not in loadtxt:
    errors.append("load.mcfunction re-seeds #lcg on every reload, so the closed-form delay "
                  "would restart from the same phase and the flashes fall on the same beats")
if not mmod or not mfix or len(mlast) != 1:
    errors.append("flash_begin does not fold its delay as `%%= width`, fix the negative "
                  "remainder, then add a base")
    lo, hi = 0, 0
else:
    width = int(mmod.group(1))
    if int(mfix.group(1)) != width:
        errors.append("flash_begin fixes the remainder with %s but folds with %d: the low end "
                      "of the range is wrong" % (mfix.group(1), width))
    base = int(re.search(r"(\d+)$", mlast[0].strip()).group(1))
    lo, hi = base, base + width - 1
    print("flash delay %d..%d ticks (%.0f..%.0f s), computed not rolled"
          % (lo, hi, lo / 20.0, hi / 20.0))
    if hi - lo < 120:
        errors.append("flash_begin spreads its delay over only %d ticks: too narrow to feel "
                      "random" % (hi - lo))
written = set(re.findall(r"^scoreboard players (?:set|add|remove|operation) (#\S+) deusex",
                         fbegin, re.M))
written |= set(re.findall(r"store result score (#\S+) deusex", fbegin))
for tok in set(re.findall(r"(?:\+=|-=|\*=|/=|%=|><|=|>|<) #(\S+) deusex", fbegin)):
    if "#" + tok not in CONST and "#" + tok not in written:
        errors.append("flash_begin reads #%s but neither sets it nor has load.mcfunction set it"
                      % tok)
if "matches 1.. run function deusex:flash_frame" not in fframe:
    errors.append("flash_tick does not run flash_frame while #fframe counts down")
if "if score #fframe deusex matches 0 if score #flashd deusex matches ..0 run function deusex:flash_begin" not in fframe:
    errors.append("flash_tick does not rearm flash_begin when the delay runs out")
if "scoreboard players remove #fframe deusex 1" not in fbody:
    errors.append("flash_frame does not count the envelope down")
# flash_frame, flash_begin, halt, load, finish and do_pause all clear the panel set; see the cleanup
# rules further down for why every one of them is now `if entity`-gated. The replay has to read the
# guarded form or the envelope looks like it never dies.
if not re.search(r"matches 0 if entity @e\[type=minecraft:text_display,tag=deusex_flash\] "
                 r"run kill @e\[type=minecraft:text_display,tag=deusex_flash\]", fbody):
    errors.append("flash_frame leaves the panel in the sky at the end of the envelope")

S = {k: int(v) for k, v in CONST.items()}
S.update({"#fframe": 0, "#flashd": 1})   # 1 so the first tick rearms
env = []           # (tick, {layer: opacity written this tick}, killed?)
for tick in range(70):
    log = []
    mclog.run("flash_tick", S, log)
    written_ = {}
    for k, _, tag, b in log:
        if k != "opacity":
            continue
        if tag in written_:
            errors.append("flash envelope tick %d writes %s twice: two rows match the same #fframe, "
                          "so the panel jumps to whichever merge lands last" % (tick, tag))
        written_[tag] = b
    env.append((tick, written_, any(k == "kill" for k, _, _, _ in log)))
start = next((i for i, (_, w, _) in enumerate(env) if w), None)
if start is None:
    errors.append("flash_tick never writes an opacity at all")
else:
    # The 1.0.18 envelope is a flash, not a fade: every layer snaps to full on the first frame,
    # stutters near peak for a few frames, then decays monotonically to nothing. What has to stay
    # true is that it is bright, that it dies, and that it cannot light up again early.
    for layer in ORDER:
        alphas = [w[layer] for _, w, _ in env[start:] if layer in w]
        if not alphas:
            errors.append("flash envelope never writes %s: that layer stays at whatever the summon "
                          "left in text_opacity" % layer)
            continue
        peak = max(alphas)
        print("flash %-13s %2d ticks (%.2f s) first %3d peak %3d tail %s"
              % (layer, len(alphas), len(alphas) / 20.0, alphas[0], peak, alphas[-3:]))
        if peak < 200:
            errors.append("%s only reaches opacity %d: text_opacity above 127 has to be written as "
                          "its wrapped byte or the panel caps at half alpha" % (layer, peak))
        if len(alphas) < 12:
            errors.append("%s is only %d ticks: it reads as a glitch, not a flash" % (layer, len(alphas)))
        if alphas[0] < 0.8 * peak:
            errors.append("%s starts at %d and peaks at %d: the flash fades in instead of snapping "
                          "on, which is how the glow ended up invisible in 1.0.19"
                          % (layer, alphas[0], peak))
        if alphas[-1] > 8:
            errors.append("%s ends at opacity %d instead of dying out" % (layer, alphas[-1]))
        for v in alphas:
            if not 0 <= v <= 255:
                errors.append("%s alpha %d is outside 0..255" % (layer, v))
        lit = [i for i, v in enumerate(alphas) if v >= 200]
        if lit:
            tail = alphas[lit[-1] + 1:]
            if tail != sorted(tail, reverse=True):
                errors.append("%s brightens again after its last full-brightness frame: %s"
                              % (layer, tail))
        if not env[start + len(alphas)][2]:
            errors.append("%s is never killed at the end of the envelope" % layer)
        if any(layer in w for _, w, _ in env[start + len(alphas) + 1:]):
            errors.append("%s restarts itself before the delay expires" % layer)
        # Every layer is summoned already lit, because flash_begin arms #fframe one above the
        # first row: the panel appears on the tick before flash_frame runs, so the summon value has
        # to equal the frame it will be faded from or the eye sees a pop.
        want = alphas[0]
        for p in [q for q in parsed if q["layer"] == layer]:
            if p["op"] != want:
                errors.append("flash_spawn v%d %s summons at opacity %d but the envelope's first "
                              "frame is %d: the panel changes brightness when flash_frame first "
                              "touches it" % (p["var"], layer, p["op"], want))
    d = re.search(r"scoreboard players set #fframe deusex (\d+)", fbegin)
    n = max(len([w[layer] for _, w, _ in env[start:] if layer in w]) for layer in ORDER)
    if d and int(d.group(1)) != n + 1:
        errors.append("flash_begin arms #fframe %d but flash_frame writes alphas for %d frames: the "
                      "countdown runs first, so the arm has to be one above the highest row"
                      % (int(d.group(1)), n))


# The delay has to be checked over a long run, not one envelope: the arithmetic is the only
# thing standing between the mod and two flashes landing on top of each other.
S = {k: int(v) for k, v in CONST.items()}
S.update({"#fframe": 0, "#flashd": 1})
delays = []
for tick in range(6000):
    log = []
    mclog.run("flash_tick", S, log)
    # the *final* delay, not the intermediate writes: flash_begin copies the raw state into
    # #flashd, folds it, then adds the base, and only the last of those is what flash_tick counts
    if any(k == "call" and a == "flash_begin" for k, _, a, _ in log):
        delays.append(S["#flashd"])
if not delays:
    errors.append("flash_begin never armed a delay in 6000 ticks of flash_tick")
else:
    bad = [v for v in delays if not lo <= v <= hi]
    print("flash delay over 5 minutes: %d rearms, %d..%d, %d distinct"
          % (len(delays), min(delays), max(delays), len(set(delays))))
    if bad:
        errors.append("flash_begin produced %d delays outside %d..%d, e.g. %d"
                      % (len(bad), lo, hi, bad[0]))
    if len(set(delays)) < 8:
        errors.append("flash_begin only ever waits %d different lengths: it is a metronome, "
                      "not a random flash" % len(set(delays)))
    if len(delays) < 15:
        errors.append("only %d flashes in 5 minutes: the sky looks dead" % len(delays))


# ---------- particles ----------
# The pack draws no particles, and this is a ban rather than a taste. The red dust motes 1.0.19
# through 1.0.25 hung in the air were never part of the look the build is being held to: the 1.0.18
# jar has no /particle line in any of its functions. The drops themselves are red because of
# assets/minecraft/textures/environment/rain.png, which nothing drawn by /particle can match, so the
# motes only ever added a second, worse rain on top of the real one. They also carried a cost: a
# /particle box that lands in a chunk the server does not have throws, and a throw stops every line
# after it in the same function - which is why these two lines used to sit at the very foot of
# tick.mcfunction rather than where the rest of the weather logic lives.
ticktxt = open(os.path.join(FUN, "tick.mcfunction"), encoding="utf-8").read()
PARTICLE = re.compile(r"(?:^|\bs run )particle\s+minecraft:")
offenders = []
for f in sorted(funcs):
    for i, ln in enumerate(open(os.path.join(FUN, f + ".mcfunction"), encoding="utf-8")
                           .read().splitlines(), 1):
        s = ln.strip()
        if s and not s.startswith("#") and PARTICLE.search(s):
            offenders.append("%s:%d %s" % (f, i, s[:70]))
if offenders:
    errors.append("the pack draws particles again (%s): the motes were retired in 1.0.26 - the red "
                  "rain is the rain.png sheet, and /particle only put a coarser rain over it and a "
                  "throw in the middle of the tick" % "; ".join(offenders[:3]))
for gone in ("blood_rain", "flash_rain", "test_rain"):
    if gone in funcs:
        errors.append("%s.mcfunction is still shipped: it exists only to spawn the retired motes" % gone)
    if ("deusex:%s" % gone) in ticktxt:
        errors.append("tick.mcfunction still calls deusex:%s, which is no longer in the pack. A call "
                      "to an unknown function is not a runtime miss: StaticCommandFunction resolves "
                      "it while the datapack loads, so the whole tick fails to build and the mod "
                      "looks dead rather than merely quiet" % gone)
print("particles: %d /particle lines in %d functions; blood_rain, flash_rain and test_rain retired"
      % (len(offenders), len(funcs)))

# The drops themselves are red because the pack says so. assets/minecraft/textures/environment/
# rain.png is the one path LevelRenderer.renderSnowAndRain binds, and it writes
# `.setColor(1.0F, 1.0F, 1.0F, f7)` into every vertex, so that sheet is the only hue a rain drop can
# ever carry - which is why 1.0.23 and 1.0.24, having removed it, could not make the rain look like
# 1.0.18 however deep they drove the veil.
#
# The override is unconditional, and "plain rain outside the event is blood" is what a friend of the
# author noticed about it. The answer is not to drop the sheet, it is to own the weather: load.mcfunction
# turns the world's weather cycle off, which leaves opening_rain as the only command that can start rain
# while the pack is installed, and #rain is the pack's note that the rain out there is its own - idle
# with the flag up means a show let go of the sky without clearing it, and the next tick clears it once.
# Every part of that has to ship together or the promise is a lie, so the sheet, the cycle, the flag and
# the gate are all checked here.
RAIN_PATH = "minecraft/textures/environment/rain.png"
van = []
for base, _s, names in os.walk(os.path.join(ASSETS, os.pardir, "minecraft")) if os.path.isdir(
        os.path.join(ASSETS, os.pardir, "minecraft")) else []:
    for n in names:
        van.append(os.path.relpath(os.path.join(base, n), os.path.join(ASSETS, os.pardir))
                   .replace("\\", "/"))
RAIN_RED = RAIN_PATH in van
if not RAIN_RED:
    errors.append("the pack ships no %s, so the rain itself is vanilla white again. The user asked "
                  "for the 1.0.18 rain twice; no particle field, title wash or veil depth has ever "
                  "stood in for the sheet, because a drop's colour can only come from this path."
                  % RAIN_PATH)
stray = [v for v in van if v != RAIN_PATH]
if stray:
    errors.append("the rain sheet is the only vanilla asset this pack has a reason to override; "
                  "these have no gate and would change plain Minecraft: %s" % ", ".join(sorted(stray)))
if RAIN_RED:
    px = list(Image.open(os.path.join(EXT, "assets", RAIN_PATH)).convert("RGBA").getdata())
    tot = sum(p[3] for p in px)
    inked = sum(1 for p in px if p[3] > 0)
    if tot == 0 or inked * 20 < len(px):
        errors.append("the red rain sheet inks only %d of %d pixels: at that density the drops read "
                      "as plain water whatever hue they carry" % (inked, len(px)))
    else:
        rw, gw, bw = (sum(p[k] * p[3] for p in px) / tot for k in range(3))
        if not (rw >= 120 and gw <= 60 and bw <= 60):
            errors.append("the rain sheet's alpha-weighted colour is (%.0f, %.0f, %.0f): that is not "
                          "blood, and the sheet is the whole of the drop's colour" % (rw, gw, bw))
        print("rain sheet: %d/%d pixels inked, alpha-weighted rgb (%.0f, %.0f, %.0f)"
              % (inked, len(px), rw, gw, bw))

# No predicate in the gate, and no predicate in the pack. `execute if predicate` is the only way 1.21.1
# can read the weather from a command and it is unusable here: the soak answers "An unexpected error
# occurred trying to execute that command" for the datapack id, for minecraft:weather_check written
# inline, from the console, from inside a function and positioned over a loaded block - 1.21.1's
# ExecuteCommand.checkCustomPredicate builds a LootContext around a command source that only a real
# player fills in completely. A throw is the worst outcome this line can have: it stops the rest of
# tick.mcfunction, and the rest of tick.mcfunction is the show.
bad = []
for f in sorted(os.listdir(FUN)):
    if f.endswith(".mcfunction"):
        for ln in open(os.path.join(FUN, f), encoding="utf-8").read().splitlines():
            if not ln.startswith("#") and re.search(r"\b(if|unless) predicate\b", ln):
                bad.append("%s: %s" % (f, ln.strip()))
if bad:
    errors.append("these lines gate on a predicate, which 1.21.1 throws on for every non-player source "
                  "tested (console, function, positioned, inline JSON): %s" % "; ".join(bad))
if os.path.isdir(os.path.join(EXT, "data", "deusex", "predicate")):
    errors.append("the pack still carries a data/deusex/predicate directory: nothing may use it, so it "
                  "only invites the next attempt at a weather check that cannot run")

GATE_CLEAR = (r"^execute unless score #state deusex matches 1\.\.2 "
              r"if score #rain deusex matches 1 run weather clear$")
GATE_ARM = (r"^execute unless score #state deusex matches 1\.\.2 "
            r"if score #rain deusex matches 1 run scoreboard players set #rain deusex 0$")
if not re.search(GATE_CLEAR, ticktxt, re.M):
    errors.append("tick.mcfunction has no rain gate, so a sky the pack left raining keeps drawing the "
                  "red sheet while the event is idle - the bug reported against 1.0.18 and 1.0.22.")
if not re.search(GATE_ARM, ticktxt, re.M):
    errors.append("tick.mcfunction clears the weather but never disarms #rain, so the gate runs "
                  "`weather clear` on every idle tick and the server log takes a \"Nothing changed\" "
                  "line twenty times a second")
if "scoreboard players set #rain deusex 1" not in orain:
    errors.append("nothing arms #rain, so the pack can no longer tell its own downpour from one the "
                  "world started - and the veil, the red sheet and the weather gate all hang off that "
                  "flag. opening_rain is where it belongs")
for nm in ("halt", "closing_start"):
    txt = open(os.path.join(FUN, nm + ".mcfunction"), encoding="utf-8").read()
    if "weather clear" in txt and "scoreboard players set #rain deusex 0" not in txt:
        errors.append("%s clears the weather and leaves #rain armed, so the exit path and the tick gate "
                      "both claim the sky: the stop prints a second weather line and the flag goes stale"
                      % nm)
if "gamerule doWeatherCycle false" not in loadtxt:
    errors.append("load.mcfunction leaves the world's weather cycle running, so any afternoon the game "
                  "picks a cloud for itself puts the red sheet up outside the song. Turning the cycle "
                  "off is the only thing a data-only pack can do about an unconditional texture.")
if not re.search(r"^execute unless score #state deusex matches 1\.\.2 run weather clear$",
                 loadtxt, re.M):
    errors.append("load.mcfunction does not clear an idle sky, so rain that was already falling when "
                  "the pack was installed keeps drawing red through the next /reload")
if "scoreboard players add #rain deusex 0" not in loadtxt:
    errors.append("load.mcfunction never defaults #rain. The gate reads it before anything writes it on "
                  "a fresh world, and an unset score is a different answer from 0 to `matches 1`.")
print("vanilla asset overrides: %d, weather gate: sheet %s, cycle %s, flag %s"
      % (len(van), "red" if RAIN_RED else "white",
         "off" if "gamerule doWeatherCycle false" in loadtxt else "running",
         "armed" if re.search(GATE_CLEAR, ticktxt, re.M) else "missing"))


# ---------- panel cleanup that cannot throw ----------
# /kill takes an entity argument, and EntityArgument.getEntities (1.21.1,
# net/minecraft/commands/arguments/EntityArgument.java:59) raises argument.entity.notfound.entity as
# soon as the selector matches nothing. Inside a function that is not a polite "no": the exception
# stops every line below it and takes its caller with it. Seven exit paths in this pack had a bare
# `kill @e[...]` sitting in front of the work that matters, which is how 1.0.19 through 1.0.24 could
# look clean in a soak whose console source has no level and still be wrong on screen:
#   * halt killed the panels ahead of `weather clear` and the #rain disarm, so a stopped show kept the
#     world raining the pack's own red - the bug the author's friend reported, and the reason the
#     soak39 gate read HALT_LEFT_FLAG.
#   * flash_begin killed them ahead of flash_player, and flash_player is the only thing in the pack
#     that summons a panel, so the abort left nothing to kill on the next pass and the sky never lit
#     again.
#   * finish killed them ahead of closing_start, so the ending never started: the veil stayed at full
#     strength and the rain stayed up with it.
#   * load killed them ahead of the three lines that own the weather, so a fresh world - no panel -
#     came up with the cycle still running and plain rain drawing the red sheet.
# `if entity` reads the same selector through EntityArgument.getOptionalEntities, which hands back an
# empty list instead of throwing, so a cleanup with nothing to clean stops being a grenade.
def code(name):
    return [l.strip() for l in open(os.path.join(FUN, name + ".mcfunction"), encoding="utf-8")
            .read().splitlines() if l.strip() and not l.strip().startswith("#")]


KILL = re.compile(r"\bkill @e\[")
naked = []
for f in sorted(funcs):
    for i, ln in enumerate(open(os.path.join(FUN, f + ".mcfunction"), encoding="utf-8")
                           .read().splitlines(), 1):
        s = ln.strip()
        if s and not s.startswith("#") and KILL.search(s) and "if entity @e[" not in s:
            naked.append("%s:%d %s" % (f, i, s[:70]))
if naked:
    errors.append("these panel kills throw on an empty selector and strand every line under them - "
                  "gate them with `execute if entity @e[...] run`: %s" % "; ".join(naked))

# The order is the other half of the rule. A guarded kill still throws in the headless soak, because
# the console source there has no level, so anything the shipped game needs on those lines has to be
# able to survive losing them.
CLEAN = "execute if entity @e[type=minecraft:text_display,tag=deusex_flash] run " \
        "kill @e[type=minecraft:text_display,tag=deusex_flash]"
for f, must_be_last in (("flash_begin", False), ("halt", True), ("load", True), ("finish", True),
                        ("do_pause", True)):
    lines = code(f)
    hits = [i for i, l in enumerate(lines) if KILL.search(l)]
    if len(hits) != 1:
        errors.append("%s has %d panel kills, expected exactly one guarded one" % (f, len(hits)))
        continue
    if must_be_last and hits[0] != len(lines) - 1:
        errors.append("%s's panel cleanup is not its last line: the lines under it are the ones the "
                      "world depends on, and a cleanup that fails must not be able to reach them" % f)
if code("flash_begin")[-1] != "execute as @a at @s run function deusex:flash_player":
    errors.append("flash_begin does not end on the line that summons the sky panel; everything this "
                  "build knows about red skies goes through flash_player, so nothing may sit above it")
halt_lines = code("halt")
for probe in ("weather clear", "scoreboard players set #rain deusex 0",
              "execute as @a[tag=deusex_frozen] run function deusex:unfreeze_player",
              "function deusex:stop_sounds"):
    if probe in halt_lines and halt_lines.index(probe) > halt_lines.index(CLEAN):
        errors.append("halt runs `%s` after its panel cleanup, so one failed cleanup leaves the "
                      "stopped show holding it" % probe)
load_lines = code("load")
for probe in ("scoreboard players add #rain deusex 0",
              "execute unless score #state deusex matches 1..2 run weather clear",
              "gamerule doWeatherCycle false"):
    if probe not in load_lines:
        errors.append("load.mcfunction no longer ships `%s`" % probe)
    elif load_lines.index(probe) > load_lines.index(CLEAN):
        errors.append("load.mcfunction sets the weather ownership after its panel cleanup, so a "
                      "fresh world with no panel to kill never gets there")
fin_lines = code("finish")
if "function deusex:closing_start" not in fin_lines or \
        fin_lines.index("function deusex:closing_start") > fin_lines.index(CLEAN):
    errors.append("finish's cleanup sits in front of closing_start, so the ending does not start when "
                  "the sky has no panel to clear - and closing_start is what takes the rain down")
print("panel cleanups: %d guarded, %d naked; halt/load/finish end on theirs"
      % (sum(1 for f in funcs for l in code(f) if KILL.search(l)), len(naked)))

# How deep the held veil has to be depends on which of the two colour sources shipped above. Without
# the sheet the wash is alone, and 1.0.23's level 9 (18.0% mean alpha) drew "the screen didnt turn
# into red" - that path needs a third of the frame.
#
# With the sheet the drops are red but the sky is not, and that is the arithmetic of
# ClientLevel.getSkyColor: it multiplies the biome colour by a time-of-day factor and then lerps it
# toward grey by the rain level (f7 = 1 - rain * 0.75), so forcing rain - which opening_rain does,
# #rainlead ticks ahead of the drop -
# throws away three quarters of the hue before the wash is even composited. The screenshot the user
# sent of the running event measures its sky at (108, 83, 100): a red-minus-blue of +8. Stripping
# that frame's veil and repainting it from red_lv.png at each level is the calibration, and skyview
# reproduces it: lv6 (today's floor) +8, lv12 +41, lv14 (121, 48, 60) +60, lv16 (134, 29, 38) +97,
# lv18 +145. "Make the sky look reddish" is the +60 band; below +41 the frame still reads lavender
# and at +145 there is no scene left to be impressed by.
wb = re.search(r"^scoreboard players set #washbase deusex (\d+)$", oburst, re.M)
if not wb:
    errors.append("opening_burst never raises #washbase, so the song has no held sky colour at all")
elif RAIN_RED and not (13 <= int(wb.group(1)) <= 15):
    errors.append("#washbase %s is not the held veil level that reddens the sky: measured over the "
                  "user's own event frame, 14 gives red-minus-blue +60 and 13-15 is the band where "
                  "the sky reads red while the drops, the disc and the lyric stay in the picture. "
                  "12 is +41 and still lavender-grey; 16 is +97 and 18 +145, which is a red screen "
                  "with no event on it" % wb.group(1))
elif not RAIN_RED and int(wb.group(1)) < 13:
    errors.append("#washbase %s with no red rain.png in the pack: the veil is the only colour left, "
                  "and anything under 13 is a cast rather than a red screen"
                  % wb.group(1))

# The two red effects over the world have to agree about when they are allowed to run. During the
# opening the title slot belongs to the cutscene, and during the ending the closing sequence owns
# the veil.
WINDOW = ("if score #state deusex matches 1 if score #cstate deusex matches 0 "
          "if score #ostage deusex matches 4..")
for f in ("flash_tick", "wash_draw"):
    if "execute " + WINDOW + " run function deusex:" + f not in ticktxt:
        errors.append("tick.mcfunction does not gate %s on the plain-world window (#state 1, "
                      "#cstate 0, #ostage 4..), so panel and veil would disagree" % f)

# ---------- red wash ----------
# The other half of "the red sky is gone": the 1.0.19 rewrite left flash_begin raising only the
# sky panel, so the world in front of the camera never tinted. The veil lives in the title slot,
# which the cutscene also uses - hence the #ostage 4.. gate above.
if "scoreboard players operation #wash deusex = #washmax deusex" not in fbegin:
    errors.append("flash_begin never raises #wash: nothing else does during the song, so the sky "
                  "can flash red while the world in front of the player stays plain")
if "scoreboard players set #washc deusex 0" not in fbegin:
    errors.append("flash_begin raises the veil without resetting #washc, so the first fade step "
                  "lands up to three ticks late and inherits the ending's carry")
washmax = int(CONST.get("#washmax", 0))
mtint = re.search(r"^scoreboard players set #tint deusex (\d+)$", loadtxt, re.M)
if not mtint:
    errors.append("#tint is only initialised `unless unset`, so a world that cached the old "
                  "strength never picks up the corrected one (same reason #drop is set)")
elif not washmax:
    errors.append("load.mcfunction does not set #washmax, so wash_draw divides the level by zero")
elif int(mtint.group(1)) != washmax:
    errors.append("#tint is %s but #washmax is %d: wash_draw paints #tint*#wash/#washmax, so the "
                  "veil tops out at %d%% of a level and no longer names a red_lv cell"
                  % (mtint.group(1), washmax, 100 * int(mtint.group(1)) // washmax))

# Drain and repaint, replayed through the shipped arithmetic rather than a second copy of it. The
# song and the ending run the same function against different floors, so both get simulated: the
# song holds #washbase and must settle there, the ending drops the base to 0 and must go home.
def drain(base, start_at, ticks):
    st = {k: int(v) for k, v in CONST.items()}
    st.update({"#wash": start_at, "#washc": 0, "#washbase": base,
               "#wlv": 0, "#wlast": 0, "#lv": -1})
    out, painted, mism = [], 0, []
    for tick in range(ticks):
        mclog.run("wash_tick", st, [])
        log = []
        mclog.run("wash_draw", st, log)
        painted += sum(1 for k, _, a, _ in log if k == "call" and a == "tint_refresh")
        out.append(st["#wash"])
        # tint_draw recomputes the level from #wash itself. If the two ever differ, the repaint gate
        # in wash_draw is guarding a number that is not the one on screen.
        if st["#lv"] != st["#wash"]:
            mism.append((tick, st["#lv"], st["#wash"]))
    return out, painted, mism


mbase = re.search(r"^scoreboard players set #washbase deusex (\d+)$", oburst, re.M)
if not mbase:
    errors.append("opening_burst never raises #washbase: 1.0.18 held its red sky for the whole song "
                  "and this build only blinked it, which is the 'sky is stay normal' complaint")
washbase = int(mbase.group(1)) if mbase else 0
if washbase and not (0 < washbase < washmax):
    errors.append("#washbase %d is not between 0 and #washmax %d: at the ceiling a flash cannot "
                  "spike above the held red, at the floor the sky goes plain between blinks"
                  % (washbase, washmax))

# The ending: base 0, armed at full, and every level has to reach the screen.
ending, e_repaints, e_mismatch = drain(0, washmax, 80)
levels = ending
repaints, mismatched = e_repaints, e_mismatch
cleared = next((i for i, v in enumerate(levels) if v == 0), None)
print("wash (ending): %d -> 0 in %s ticks, %d repaints for %d distinct levels, gate/paint mismatches %d"
      % (washmax, (cleared + 1) if cleared is not None else "never", repaints, len(set(levels)),
         len(mismatched)))
if mismatched:
    errors.append("wash_draw's repaint gate and tint_draw's painted level disagree on %d ticks, "
                  "e.g. tick %d paints %s while gating on %s"
                  % (len(mismatched), mismatched[0][0], mismatched[0][1], mismatched[0][2]))
if levels != sorted(levels, reverse=True):
    errors.append("the veil brightens during its own fade: %s" % levels)
if min(levels) < 0:
    errors.append("wash_tick drives #wash negative (%d): lv_char clamps it to cell 0 but the score "
                  "then never returns to a value the drain recognises" % min(levels))
if cleared is None or cleared + 1 > 4 * washmax + 4:
    errors.append("the veil takes %s ticks to clear, not the %d wash_tick advertises: the screen "
                  "stays red" % (cleared, 4 * washmax))
elif cleared + 1 != 4 * washmax:
    errors.append("the veil drains in %d ticks, not 4 per level x %d levels: one of the two "
                  "numbers in wash_tick is stale" % (cleared + 1, washmax))
if repaints != len(set(levels)):
    errors.append("the veil repainted %d times for %d levels: either a step is skipped or the "
                  "screen is redrawn 20x a second, and `title @a title` restarts the timer every "
                  "time" % (repaints, len(set(levels))))

# The song: the same drain against the held floor. A flash starts at #washmax and the screen has to
# come back to #washbase and sit there - if it undershoots the sky pulses plain between blinks, and
# if it never settles the flash spike is the only red the player is being offered either way.
song, s_repaints, s_mismatch = drain(washbase, washmax, 120)
settled = next((i for i, v in enumerate(song) if v == washbase), None)
print("wash (song):   %d -> %d held from tick %s, %d repaints for %d distinct levels, "
      "gate/paint mismatches %d"
      % (washmax, washbase, settled, s_repaints, len(set(song)), len(s_mismatch)))
if s_mismatch:
    errors.append("with the base raised, wash_draw gates on a level tint_draw is not painting on "
                  "%d ticks" % len(s_mismatch))
if min(song) < washbase:
    errors.append("the drain runs under #washbase to %d: the floor is not being honoured, so the sky "
                  "goes plain between flashes" % min(song))
elif settled is None:
    errors.append("the veil never settles on #washbase %d inside 120 ticks: wash_tick is not reaching "
                  "its floor" % washbase)
elif song[settled:] != [washbase] * (len(song) - settled):
    errors.append("the held red wobbles after settling: %s" % song[settled:settled + 12])
elif settled + 1 != 4 * (washmax - washbase):
    errors.append("a flash bleeds off in %d ticks, not 4 per level over the %d above the base: one "
                  "of the numbers in wash_tick is stale" % (settled + 1, washmax - washbase))
if s_repaints != len(set(song)):
    errors.append("the held veil repainted %d times for %d levels: the settled sky must not be "
                  "re-issued every tick" % (s_repaints, len(set(song))))
# And the other direction: the burst lifts the base under a veil that is still at 0, so tick has to
# be able to climb back up. The old `if #wash matches 1..` gate could not open at 0, which is exactly
# how a held red sky ends up invisible.
climb, _, _ = drain(washbase, 0, 40)
reach = next((i for i, v in enumerate(climb) if v >= washbase), None)
print("wash (ramp):   0 -> %s over %s ticks" % (washbase, "%d" % (reach + 1) if reach is not None else "never"))
if reach is None:
    errors.append("wash_tick never climbs from #wash 0 to #washbase %d: the burst sets the floor and "
                  "nothing walks the veil up to it" % washbase)
elif reach + 1 != washbase:
    errors.append("the veil climbs to the base in %d ticks, not one level per tick over %d: "
                  "wash_tick's ramp and the burst's number disagree" % (reach + 1, washbase))
tref = open(os.path.join(FUN, "tint_refresh.mcfunction"), encoding="utf-8").read()
if "title @a times 0 100000 0" not in tref:
    errors.append("tint_refresh does not zero the title fade: every repaint would fade the veil in "
                  "and blink it out instead of stepping down a level")
# Only a changed level may repaint, and the drain has exactly one owner per tick: tick.mcfunction
# covers the song, closing_tick covers the ending, and #state is already 0 by then. The song's copy
# asks on `#wash != #washbase` rather than `#wash matches 1..`, which is what lets the ramp start
# from a veil that is still at 0.
if ("execute if score #cstate deusex matches 0 unless score #wash deusex = #washbase deusex "
        "run function deusex:wash_tick") not in ticktxt:
    errors.append("tick.mcfunction does not run wash_tick from `#wash != #washbase` with #cstate 0: "
                  "either the ending fades the veil twice a tick, or the burst's floor is set and "
                  "nothing walks the screen up to it")
ctxt = open(os.path.join(FUN, "closing_tick.mcfunction"), encoding="utf-8").read()
if "execute if score #wash deusex matches 1.. run function deusex:wash_tick" not in ctxt:
    errors.append("closing_tick does not drain the veil, so the ending's red never leaves")
for l in ctxt.splitlines():
    if "wash_tick" in l and l.strip().startswith("execute") and "#state" in l:
        errors.append("closing_tick gates the veil drain on #state: finish has already put the song "
                      "away, so the ending's red would sit at full strength forever")
ctail = open(os.path.join(FUN, "closing_tail.mcfunction"), encoding="utf-8").read()
if "if score #wash deusex matches 0 run function deusex:closing_end" not in ctail:
    errors.append("closing_tail does not wait for the veil to clear before closing_end")
# closing_end - the title reset that hands the game back - waits for the veil to reach 0, so the
# ending's real length is the drain and not the #ct gate. The tail line is a start and not a
# deadline: while it keeps firing every tick, closing_end lands on the tick the drain finishes.
# 1.0.21 asked the drain for a shorter ending by starting #wash below #washmax, which is also what
# made the ending faint; #washmax 17 with 4 ticks a level is 68 ticks, 3.4 s, and it still fits.
mtail = re.search(r"execute if score #ct deusex matches (\d+)\.\.?(\d*) run function "
                  r"deusex:closing_tail", ctxt)
if not mtail:
    errors.append("closing_tick never hands over to closing_tail, so nothing waits for the veil and "
                  "the ending never ends")
elif mtail.group(2):
    errors.append("closing_tail is gated on the bounded window #ct %s..%s: past its top the tail "
                  "stops being asked, so a veil that is still draining strands the screen in red "
                  "forever" % (mtail.group(1), mtail.group(2)))
else:
    cstart = open(os.path.join(FUN, "closing_start.mcfunction"), encoding="utf-8").read()
    mwash = re.search(r"^scoreboard players (?:set #wash deusex (\d+)"
                      r"|operation #wash deusex = #washmax deusex)$", cstart, re.M)
    if not mwash:
        errors.append("closing_start never raises the veil, so the ending collapses over a plain "
                      "screen instead of a red one")
    else:
        armed = washmax if mwash.group(1) is None else int(mwash.group(1))
        if armed != washmax:
            errors.append("closing_start arms the veil at %d of #washmax %d: the ending opens at "
                          "%.0f%% of the red a flash gets"
                          % (armed, washmax, 100.0 * armed / washmax))
        ending = max(int(mtail.group(1)), 4 * min(armed, washmax))
        print("ending: veil %d -> 0, closing_end at #ct %d (%.1f s)"
              % (armed, ending, ending / 20.0))
        if ending > 100:
            errors.append("the ending holds the screen in red for %d ticks: the player thinks the "
                          "mod is stuck, because the game never comes back" % ending)
        # closing_tail waits on #wash 0, and wash_tick now refuses to drain under #washbase. A base
        # left at the song's value would strand the screen in red and never run closing_end.
        if "scoreboard players set #washbase deusex 0" not in cstart:
            errors.append("closing_start raises the veil without clearing #washbase: wash_tick stops "
                          "its drain at the song's held level, so the ending never reaches #wash 0 "
                          "and the game never comes back")

# The same floor has to be gone on every other way out of the show: halt is what a player runs, and
# start is what arms a run. tint_refresh paints with times 0/100000/0, so a level left standing
# after the song is a red screen until the world reloads.
for name in ("start", "halt"):
    txt = open(os.path.join(FUN, name + ".mcfunction"), encoding="utf-8").read()
    if "scoreboard players set #washbase deusex 0" not in txt:
        errors.append("%s does not clear #washbase, so the held red sky survives the show being "
                      "stopped or restarted" % name)
if "execute unless score #washbase deusex = #washbase deusex run scoreboard players set " \
       "#washbase deusex 0" not in loadtxt:
    errors.append("load.mcfunction leaves #washbase uninitialised, so the first tick's `unless "
                  "#wash = #washbase` compares two empty scores and the ramp never runs")

# red_lv.png has to answer the level lv_char names: cell 0 is the "no veil" step the fade ends on,
# and cell #washmax is the ceiling #tint paints at full wash.
lvc = open(os.path.join(FUN, "lv_char.mcfunction"), encoding="utf-8").read()
lvmap = {int(n): ord(v) for n, v in
         re.findall(r'matches (\d+) run data modify storage deusex:data rc set value "(.)"', lvc)}
if sorted(lvmap) != list(range(20)):
    errors.append("lv_char does not cover levels 0..19: %s" % sorted(lvmap))
elif [lvmap[n] - lvmap[0] for n in range(20)] != list(range(20)):
    errors.append("lv_char's glyphs are not one contiguous run, so a level lands on the wrong cell")
elif washmax and washmax not in lvmap:
    errors.append("#washmax %d has no glyph in lv_char: the veil would stick at the last cell" % washmax)
elif washbase not in lvmap:
    errors.append("#washbase %d has no glyph in lv_char: the held sky would stick at the last cell"
                  % washbase)
else:
    fxp = next((pp for pp in FONT["fx"][1]["providers"]
                if pp["type"] == "bitmap" and pp["file"].endswith("red_lv.png")), None)
    if fxp is None:
        errors.append("deusex:fx has no red_lv.png bitmap provider, so lv_char names cells that "
                      "are not in any atlas")
    else:
        lim = Image.open(os.path.join(ASSETS, "textures", fxp["file"].split(":")[1]))
        # red_lv.png stacks its twenty levels in one column, so cell n is row n of the sheet.
        rows, cols = len(fxp["chars"]), len(fxp["chars"][0])
        ch, cw2 = lim.height // rows, lim.width // cols
        cellmean = lambda n: sum(lim.convert("RGBA").crop((0, n * ch, cw2, (n + 1) * ch))
                                 .split()[3].tobytes()) / float(cw2 * ch)
        means = [cellmean(n) for n in range(rows * cols)]
        print("red_lv cell 0 mean alpha %.1f/255, ceiling cell %d %.1f/255, last cell %d %.1f/255"
              % (means[0], washmax, means[washmax], len(means) - 1, means[-1]))
        if means[0] > 8:
            errors.append("lv_char level 0 still lays %.1f/255 alpha: fading the veil to nothing "
                          "leaves a floor of red on the screen" % means[0])
        # The rule behind "the screen has to turn red", measured rather than asserted - but only when
        # the wash is the only colour left. With the red rain sheet in the world the drops carry it
        # themselves and a shallow floor is the picture that was asked for.
        if not RAIN_RED and washbase and means[washbase] < 0.30 * 255:
            errors.append("the held veil lays only %.1f/255 (%.1f%% of the frame) at level %d: the "
                          "report from the real game at 18%% was \"the screen didnt turn into red\", "
                          "so the floor of the song's sky has to be a third of the frame or deeper"
                          % (means[washbase], 100.0 * means[washbase] / 255, washbase))
        if washmax and means[washmax] < 40:
            errors.append("the veil's ceiling cell is only %.1f/255 mean alpha: #tint %d is a "
                          "strength nobody can see" % (means[washmax], washmax))
        if means != sorted(means):
            errors.append("red_lv.png's cells are not ordered by alpha, so the drain jumbles "
                          "instead of stepping down: %s" % [round(v) for v in means])

# ---------- audio clock lead-in ----------
# The 1.0.19 recording has the heart exploding about 1.6 s before the slam you can hear, and the
# heartbeat still thumping over it. main_track.ogg is 546 s of gapless audio and /playsound hands it
# over as a stream: Channel.attachBufferStream pumps four one-second buffers through pure-Java jOrbis
# before play() is reached, so the tick the track is fired on is not the tick the player hears.
# SoundBufferLibrary.getStream caches nothing, so the cost is the decoder and it is not a constant:
# the 1.0.19 footage puts the audible start 33.2 ticks after the fire, the 1.0.18 footage 2.4 ticks.
# Same machine, same sounds.json - the difference is a cold and a warm JVM.
#
# Holding the clock for the cold number was the 1.0.22 bug: on a warm session every visual then landed
# 1.5 s after the audio, which is "the lyric is out of sync" and "not exploding at the beatdrop". So
# run_lead holds only the warm number and removes the cold one instead, by firing a silent stream of
# the same format first. The validator checks both halves of that, because a pre-roll that is too
# short to cover a cold decode is the 1.0.19 bug again.
LEADRE = r"scoreboard players set #lead deusex %s"
lr = open(os.path.join(FUN, "run_lead.mcfunction"), encoding="utf-8").read()
mpre = re.search(r"execute if score #lead deusex matches (\d+) run function deusex:play_prewarm", lr)
marm = re.search(r"execute if score #lead deusex matches (\d+) run function deusex:fire_track", lr)
if not mpre or not marm:
    errors.append("run_lead is missing a stage: it has to fire the silent warm-up stream and then "
                  "the track, and %s" % ("no play_prewarm line" if not mpre else "no fire_track line"))
    LEAD, FIRE = 70, 3
else:
    LEAD, FIRE = int(mpre.group(1)), int(marm.group(1))
    if LEAD <= FIRE:
        errors.append("run_lead arms the warm-up at #lead %d but fires the track at %d: the warm-up "
                      "would come after the track and warm nothing" % (LEAD, FIRE))
# Ticks between the two fires. #lead is read at the head of the tick and counted down at the foot of
# it, so arming at LEAD and testing for FIRE fires the track LEAD-FIRE ticks after the warm-up. The
# warm-up has to finish its own cold prefill before main_track is asked for, and the cold prefill is
# the 33.2 ticks the 1.0.19 footage measured.
PRE = LEAD - FIRE
if LEAD > FIRE and PRE < 44:
    errors.append("only %d ticks between the warm-up and the track: a cold jOrbis prefill measured "
                  "33 ticks, so main_track would still be decoded cold and the burst would land "
                  "early on a session that has not played the song yet" % PRE)
if not 2 <= FIRE <= 6:
    errors.append("the track is fired at #lead %d, %d ticks before the clock moves: the warm decode "
                  "the two recordings agree on is 2-3 ticks, so this either fires the visuals before "
                  "the audio or leaves them behind it" % (FIRE, FIRE))
if ("scoreboard players remove #lead deusex 1") not in lr:
    errors.append("run_lead never counts the hold down")
for l in [l.strip() for l in lr.splitlines() if l.strip() and not l.strip().startswith("#")]:
    if re.search(r"scoreboard players (?:set|add|remove|operation) #(?:t|idx|E) deusex", l):
        errors.append("run_lead moves the clock while holding it: %s - #E has to stay 0 until the "
                      "player can actually hear sample 0" % l[:60])
        break
# The warm-up only removes the cold cost if it is a real streamed play of the same shape as the
# track: same rate, same channel count, and long enough to fill the four one-second buffers.
pw = sounds.get("prewarm", {}).get("sounds", [{}])[0]
if not pw:
    errors.append("sounds.json has no prewarm entry, so run_lead's warm-up line plays nothing")
else:
    if pw.get("stream") is not True:
        errors.append("prewarm is stream:%s: the cold cost lives in the streamed path, so a static "
                      "buffer warms the wrong code" % pw.get("stream"))
    pwp = os.path.join(snd_dir, "prewarm.ogg")
    if not os.path.isfile(pwp):
        errors.append("sounds.json prewarm points at prewarm.ogg, which is not in the pack")
    else:
        i = sf.info(pwp)
        if (i.samplerate, i.channels) != (full.samplerate, full.channels):
            errors.append("prewarm.ogg is %d Hz x %d ch and main_track is %d Hz x %d ch: the warm-up "
                          "has to exercise the same decode shape as the track"
                          % (i.samplerate, i.channels, full.samplerate, full.channels))
        if i.frames < 4 * i.samplerate:
            errors.append("prewarm.ogg is %.2f s, under the 4 s the client prefills: the last buffer "
                          "would never be decoded, so the JIT stays cold" % (i.frames / i.samplerate))
        print("prewarm %.1f s streamed silence, %d Hz x %d ch, same shape as main_track"
              % (i.frames / i.samplerate, i.samplerate, i.channels))
stxt = open(os.path.join(FUN, "start.mcfunction"), encoding="utf-8").read()
nctxt = open(os.path.join(FUN, "next_chunk.mcfunction"), encoding="utf-8").read()
htxt = open(os.path.join(FUN, "halt.mcfunction"), encoding="utf-8").read()
ptxt = open(os.path.join(FUN, "do_pause.mcfunction"), encoding="utf-8").read()
if LEADRE % LEAD not in stxt:
    errors.append("start.mcfunction does not arm the %d tick pre-roll, so the first #E of the song is "
                  "%d ticks of music the player has not heard yet" % (LEAD, FIRE))
rear = ("execute if score #idx deusex matches 0 if score #full deusex matches 1 run "
        + LEADRE % LEAD)
if rear not in nctxt:
    errors.append("a looped replay re-arms #idx 0 without the hold, so the second pass drifts the "
                  "whole decode time ahead of the music")
elif nctxt.index(rear) < nctxt.index("if score #idx deusex > #last deusex if score #loop"):
    errors.append("next_chunk re-arms the hold before the wrap line can set #idx back to 0, so the "
                  "test never fires and only the first pass is in sync")
for name, txt in (("halt", htxt), ("do_pause", ptxt)):
    if LEADRE % 0 not in txt:
        errors.append("%s leaves #lead armed, so the clock restarts 33 ticks behind the chunk file "
                      "it plays next" % name)
if LEADRE % "0" not in loadtxt or "unless score #lead deusex = #lead deusex" not in loadtxt:
    errors.append("load.mcfunction does not default #lead, so a world that reloads mid-hold runs "
                  "with an unset score and tick.mcfunction's `matches 1..` / `matches 0` gates "
                  "both miss and the song stops")
# The burst has to land on the slam, and where the slam is belongs to the audio the player hears,
# not to a number this file remembers. 1.0.26 carried 15.95 s here because the shipped ogg had been
# ducked 18.6 dB across the song's real drop, so the first full-level hit a meter could find was the
# end of the recovery ramp; 1.0.27 rebuilt the audio from the recording and moved #drop to 10.95 s,
# and the stale constant reported the corrected anchor as the error. So the anchor is measured from
# the file, over the first minute - the only window a drop anchor may legitimately sit in, since the
# opening hands over to the song inside it.
def first_slam(path):
    import numpy as np
    y, sr = sf.read(path, dtype="float32", frames=int(60 * 44100))
    if y.ndim > 1:
        y = y.mean(axis=1)
    hop = int(sr * 0.02)
    nf = len(y) // hop
    seg = y[: nf * hop].reshape(nf, hop)
    spec = np.abs(np.fft.rfft(seg * np.hanning(hop), axis=1))
    fr = np.fft.rfftfreq(hop, 1.0 / sr)
    gain = np.zeros(nf - 1)
    for lo, hi in ((0, 60), (100, 400), (1000, 4000), (4000, float(fr.max()))):
        band = (fr >= lo) & (fr <= hi)
        e = 20.0 * np.log10(np.maximum(np.sqrt((spec[:, band] ** 2).sum(axis=1)) / band.sum(), 1e-9))
        gain += np.maximum(np.clip(e[1:] - e[:-1], None, None), 0.0)
    warm = int(3.0 / 0.02)
    order = np.argsort(gain[warm:])[::-1]
    return (warm + int(order[0]) + 1) * 0.02, (warm + int(order[1]) + 1) * 0.02, gain[warm:][order[:2]]


mdrop = re.search(r"^scoreboard players set #drop deusex (\d+)$", loadtxt, re.M)
if not mdrop:
    errors.append("#drop is only initialised `unless unset`, so a world that cached the old anchor "
                  "keeps the burst off the slam")
else:
    drop = int(mdrop.group(1))
    slam = None
    try:
        slam, runner, heights = first_slam(os.path.join(snd_dir, "main_track.ogg"))
    except Exception as exc:
        warns.append("could not measure the slam in main_track.ogg (%s), so #drop %d was not checked "
                     "against the audio" % (exc, drop))
    print("lead-in %d ticks (%.2f s): prewarm at arm, track %d ticks later, clock %d ticks after "
          "that; drop anchor #drop %d = %.2f s of main_track"
          % (LEAD, LEAD / 20.0, PRE, FIRE, drop, drop / 20.0))
    if slam is not None:
        print("slam measured from the shipped audio: %.3f s (+%.0f dB across four bands), the next "
              "candidate is %.3f s (+%.0f dB)"
              % (slam, heights[0], runner, heights[1]))
        if heights[1] > 0.6 * heights[0]:
            warns.append("the slam is not unmistakable in main_track.ogg: %.3f s gains +%.0f dB and "
                         "%.3f s gains +%.0f dB, so which one the burst should land on is a judgement"
                         % (slam, heights[0], runner, heights[1]))
        if abs(drop / 20.0 - slam) > 0.06:
            errors.append("#drop %d is %.2f s, but the first full-band slam in the shipped "
                          "main_track.ogg measures %.2f s - the burst fires %.2f s away from the hit"
                          % (drop, drop / 20.0, slam, abs(drop / 20.0 - slam)))
    otickx = open(os.path.join(FUN, "opening_tick.mcfunction"), encoding="utf-8").read()
    if ("execute if score #ostage deusex matches 2 if score #E deusex >= #drop deusex run "
            "function deusex:opening_burst") not in otickx:
        errors.append("opening_tick does not fire the burst on the first tick the audio clock reaches "
                      "#drop, so the explosion is not tied to the slam")


# The hand-over is order-sensitive and every execute head re-reads the scores after the line before
# it ran, so the replay follows tick.mcfunction's own two lines instead of assuming they are
# mutually exclusive. Written the other way round, the tick that counts #lead from 1 down to 0 also
# passed the #lead 0 test, and the hold cost 32 ticks while the clock started - one tick of the
# measured decode time spent waiting for nothing, with #E a tick ahead of the audio again.
LEADGATES = []
for raw in mclog.load("tick"):
    line = raw.strip()
    if "#lead deusex" in line and "run function deusex:run" in line:
        conds, body = mclog.split_execute(line)
        if conds is None:
            errors.append("tick.mcfunction's lead dispatch is not a plain score gate, so the replay "
                          "cannot follow it: %s" % line[:70])
            continue
        mfn = re.search(r"function deusex:(\w+)", body)
        LEADGATES.append((conds, mfn.group(1)))
if len(LEADGATES) != 2:
    errors.append("tick.mcfunction dispatches the clock through %d #lead lines, not 2" % len(LEADGATES))
else:
    order = [n for _c, n in LEADGATES]
    if order.index("run_lead") < order.index("run_playing"):
        errors.append("tick.mcfunction counts the hold down before it hands over, so the last tick of "
                       "the lead-in also advances the clock: #E starts %d ticks after the track "
                       "instead of %d" % (FIRE - 1, FIRE))


def clock(full, ticks, lead=0):
    """Walk the shipped tick paths one game tick at a time.

    Returns the ticks on which play_chunk fired and #E for every tick, so the hand-over from the
    lead-in to the running clock is something the validator counts instead of believes.
    """
    C = {k: int(v) for k, v in CONST.items()}
    C.update({"#lead": lead, "#state": 1, "#idx": 0, "#t": 0, "#ostage": 0, "#loop": 1,
              "#full": full})
    fires, E = [], []
    for _ in range(ticks):
        log = []
        for conds, fn in LEADGATES:
            if all(mclog.holds(c, C) for c in conds):
                mclog.run(fn, C, log)
                if any(k == "call" and a == "play_chunk" for k, _, a, _ in log):
                    fires.append(len(E))
        E.append(C["#idx"] * 60 + C["#t"])
    return fires, E


# The track must be triggered once per pass. #t is still 0 on the tick the hold hands over, so an
# ungated chunk-head fire in run_playing played main_track a second time after the first - two
# instances of the same recording a tick apart, which is a flam over the whole intro.
gfires, gE = clock(1, LEAD + 200, lead=LEAD)
if gfires != [PRE]:
    errors.append("the gapless pass fires play_chunk on ticks %s, not %d ticks after the pre-roll is "
                  "armed (the warm-up gets %d ticks of its own before the track)"
                  % (gfires, PRE, PRE))
if set(gE[:LEAD]) != {0} or gE[LEAD] != 1:
    errors.append("the clock moved during the hold (#E at ticks %d..%d is %s)"
                  % (0, LEAD, gE[:LEAD + 1]))
cfires, cE = clock(0, 200)
if cfires != [0, 60, 120, 180]:
    errors.append("the chunked path fires on ticks %s, not at every chunk head: resuming after a "
                  "pause would be silent" % cfires)
if cE != list(range(1, 201)):
    errors.append("the chunked clock is not one #E per tick: %s..%s" % (cE[0], cE[-1]))
song = nlast * 60 + ltick
lfires, _ = clock(1, LEAD + song + LEAD + 40, lead=LEAD)
print("clock: song is %d ticks of #E, lead %d -> %d fires across a looped pass at ticks %s"
      % (song, LEAD, len(lfires), lfires))
if len(lfires) != 2 or lfires[0] != PRE:
    errors.append("a looped pass fires main_track %d times (ticks %s): exactly the arm pass and "
                  "the wrap should trigger a sound" % (len(lfires), lfires))
elif abs(lfires[1] - (LEAD + song + PRE)) > 2:
    errors.append("the looped pass re-fires at tick %d, %d ticks away from the pre-roll the wrap at "
                  "%d should have armed" % (lfires[1], abs(lfires[1] - (LEAD + song + PRE)),
                                            LEAD + song))

# ---------- rejoin catch-up ----------
# The gapless track is handed out once, to whoever was online when fire_track ran; a client that
# leaves drops the stream with the world unload and /playsound has no resume, so a rejoiner heard
# nothing until a pause/resume switched the show to the chunked path. warm_tick tags a player whose
# join counter just started, run_playing hands that tag the current chunk at the next head, and
# play_catchup clears it. mclog models neither tags nor @a, so these are shape rules over the shipped
# text; the clock replay above already proves the heads the catch-up rides on are the same 60 tick
# grid every other player hears, at most one chunk (3 s) behind.
CT = os.path.join(FUN, "play_catchup.mcfunction")
if not os.path.isfile(CT):
    errors.append("play_catchup.mcfunction is missing: a rejoiner never gets the song back")
else:
    ct_txt = open(CT, encoding="utf-8").read()
    if "storage deusex:data idx" not in ct_txt or "scoreboard players get #idx deusex" not in ct_txt:
        errors.append("play_catchup does not read #idx into the macro cell, so $(idx) has no value")
    if "function deusex:catchup_macro with storage deusex:data" not in ct_txt:
        errors.append("play_catchup does not hand the cell to its macro line with storage: a $ line "
                      "only binds arguments passed to its own call, so $(idx) would stay unbound")
    cm_path = os.path.join(FUN, "catchup_macro.mcfunction")
    cm_txt = open(cm_path, encoding="utf-8").read() if os.path.isfile(cm_path) else ""
    if "$execute as @a[tag=deusex_catchup] at @s run playsound deusex:chunk_$(idx) record @s ~ ~ ~ 1 1 1" \
            not in cm_txt:
        errors.append("catchup_macro does not fire the current chunk at exactly the tagged players")
    if "main_track" in ct_txt or "main_track" in cm_txt:
        errors.append("play_catchup fires main_track: a rejoiner would restart the song from zero "
                      "instead of joining the grid everyone else is on")
    if ct_txt.strip().splitlines()[-1].strip() != "tag @a[tag=deusex_catchup] remove deusex_catchup":
        errors.append("play_catchup does not end by clearing the tag: every later chunk head would "
                      "fire the song at the rejoiner again, one instance per chunk")
rp_txt = open(os.path.join(FUN, "run_playing.mcfunction"), encoding="utf-8").read()
CT_GATE = ("execute if score #t deusex matches 0 if score #full deusex matches 1 "
           "if entity @a[tag=deusex_catchup] run function deusex:play_catchup")
if CT_GATE not in rp_txt:
    errors.append("run_playing lacks the catch-up gate (chunk head, gapless only, somebody tagged): "
                  "without #t 0 it fires mid-chunk, without #full 1 a resumed show plays every chunk "
                  "twice, without the entity test the macro runs for nobody every head")
elif rp_txt.index(CT_GATE) > rp_txt.index("scoreboard players add #t deusex 1"):
    errors.append("the catch-up gate sits after the clock step, so #t is never 0 when it is read")
wt_txt = open(os.path.join(FUN, "warm_tick.mcfunction"), encoding="utf-8").read()
CT_TAG = ("execute as @a[scores={deusex_wt=0}] if score #state deusex matches 1 "
          "if score #full deusex matches 1 if score #lead deusex matches 0 "
          "if score #t deusex matches 1.. run tag @s add deusex_catchup")
if CT_TAG not in wt_txt:
    errors.append("warm_tick lacks the rejoin tag (first warm tick, show running, gapless, hold off, "
                  "clock moving): a joiner is either never marked or marked while fire_track still "
                  "covers them, which double-fires chunk_0 over the track")
else:
    reset = "run scoreboard players set @s deusex_wt 0"
    add = "scoreboard players add @a[scores={deusex_wt=..199}] deusex_wt 1"
    if not (wt_txt.index(reset) < wt_txt.index(CT_TAG) < wt_txt.index(add)):
        errors.append("the rejoin tag is not between the counter reset and the counter step: after "
                      "the step a first tick reads wt 1 and nobody is ever tagged")
full_writers = []
for fn in sorted(os.listdir(FUN)):
    if fn.endswith(".mcfunction"):
        txt = open(os.path.join(FUN, fn), encoding="utf-8").read()
        if re.search(r"^scoreboard players set #full deusex 1$", txt, re.M):
            full_writers.append(fn)
if full_writers != ["start.mcfunction"]:
    errors.append("#full 1 is armed by %s, not only start: the stale-tag clear below would miss a "
                  "path into the gapless show" % full_writers)
st_txt = open(os.path.join(FUN, "start.mcfunction"), encoding="utf-8").read()
if "tag @a remove deusex_catchup" not in st_txt:
    errors.append("start does not clear deusex_catchup: a tag left from a previous show would fire "
                  "a chunk at the next head on top of the fresh track")
print("rejoin catch-up: tag on the first warm tick, current chunk at the next head, tag cleared; "
      "#full 1 armed only by %s" % full_writers)

# ---------- heartbeat stops at the drop ----------
# heartbeat.ogg is a lub at 0.00 and a dub 17.4 ticks later, audible to about tick 21.8. The tail of
# the old table ran -19 then -9, so both beats were still thumping *after* the slam - which is what
# "the intro heartbeat is not stopping at the beat drop" describes.
TAIL = 22
hbtxt = open(os.path.join(FUN, "opening_hb.mcfunction"), encoding="utf-8").read()
offs = [int(x) for x in re.findall(r"matches (-\d+) run function deusex:hb_beat", hbtxt)]
if not offs:
    errors.append("opening_hb schedules no heartbeat beats")
else:
    gaps = [b - a for a, b in zip(offs, offs[1:])]
    print("heartbeat beats %s, gaps %s, last thump silent from tick %+d"
          % (offs, gaps, offs[-1] + TAIL))
    if offs != sorted(offs):
        errors.append("the beat table is not in playing order: %s" % offs)
    if max(offs) + TAIL > 0:
        errors.append("the last beat lands at %+d and its dub runs to %+d: the heart is still "
                      "thumping over the drop" % (max(offs), max(offs) + TAIL))
    if gaps[-1] != min(gaps):
        errors.append("the gaps %s do not close on the drop, so the heart does not race into the slam"
                      % gaps)
if "scoreboard players operation #hbE deusex -= #drop deusex" not in hbtxt:
    errors.append("opening_hb does not measure its beats from #drop, so the whole ramp slides off "
                  "the slam whenever the anchor moves")
if "deusex:heartbeat" not in open(os.path.join(FUN, "hb_beat.mcfunction"), encoding="utf-8").read():
    errors.append("hb_beat does not play deusex:heartbeat")
burst_txt = open(os.path.join(FUN, "opening_burst.mcfunction"), encoding="utf-8").read()
if "stopsound @s master deusex:heartbeat" not in burst_txt:
    errors.append("opening_burst does not cut the heartbeat by name: a beat fired on the way down is "
                  "still audible over the explosion, and stopsound of the whole channel would have "
                  "to be trusted to the table instead")
otickb = open(os.path.join(FUN, "opening_tick.mcfunction"), encoding="utf-8").read()
if "matches 2 run function deusex:opening_hb" not in otickb:
    errors.append("opening_tick never runs the beat table, so the offsets above are dead code")
if "scoreboard players set #ostage deusex 3" not in burst_txt:
    errors.append("opening_burst leaves #ostage at 2, so the beat table keeps running after the drop")

# ---------- heart burst ----------
# The blast is one full-screen glyph per frame drawn as a title. It has to cover exactly what
# the red wash covered, or the screen sides stay unlit and the explosion reads as a rectangle;
# and the cutscene has to end by dropping the title outright, which is the "back to normal
# Minecraft" the user is asking for.
bq = quad_units("burst")
redlv = None
for prov in FONT["fx"][1]["providers"]:
    if prov["type"] == "bitmap" and prov["file"].endswith("red_lv.png"):
        im = Image.open(os.path.join(ASSETS, "textures", prov["file"].split(":")[1]))
        sc_ = prov["height"] / (im.height // len(prov["chars"]))
        redlv = {"w": im.width // len(prov["chars"][0]) * sc_, "h": prov["height"]}
print("burst cell %.0fx%.0f font units, red_lv wash %.0fx%.0f"
      % (bq["w"], bq["h"], redlv["w"], redlv["h"]))
if redlv and abs(bq["w"] - redlv["w"]) > 1:
    errors.append("burst glyph is %.0f units wide but the proven full-screen wash is %.0f: "
                  "the blast leaves the sides of the screen untouched" % (bq["w"], redlv["w"]))
if redlv and abs(bq["h"] - redlv["h"]) > 1:
    errors.append("burst glyph is %.0f units tall vs the wash's %.0f: it will not fill the screen"
                  % (bq["h"], redlv["h"]))

hbf = open(os.path.join(FUN, "heart_burst_frame.mcfunction"), encoding="utf-8").read()
seq = [ord(x) for x in re.findall(r'data modify storage deusex:data burst set value "(.)"', hbf)]
if not seq:
    errors.append("heart_burst_frame sets no burst glyph")
for cp in seq:
    if cp not in FONT["burst"][0]:
        errors.append("heart_burst_frame glyph %04x missing from deusex:burst" % cp)
idx = [int(x) for x in re.findall(r"matches (\d+) run data modify storage deusex:data burst", hbf)]
if idx != sorted(idx) or len(set(idx)) != len(idx):
    errors.append("heart_burst_frame frame indices are not a clean increasing list: %s" % idx)
if seq and [c - seq[0] for c in seq] != list(range(len(seq))):
    errors.append("heart_burst_frame glyphs are not contiguous in the atlas")
print("heart burst frames %d..%d -> glyphs %s..%s" % (min(idx), max(idx), hex(seq[0]), hex(seq[-1])))

oflash = open(os.path.join(FUN, "opening_flash.mcfunction"), encoding="utf-8").read()
if "#k deusex -= #drop deusex" not in oflash:
    errors.append("opening_flash does not measure #k from #drop: the burst is not tied to the drop")
hi_bf = max(idx)
if "matches %d.. run scoreboard players set #bf deusex %d" % (hi_bf + 1, hi_bf) not in oflash:
    errors.append("opening_flash does not clamp #bf to the last burst frame %d" % hi_bf)
for f in ("heart_burst_frame", "title_red_burst"):
    if "function deusex:%s" % f not in oflash:
        errors.append("opening_flash never calls %s" % f)
m = re.search(r"matches (\d+)\.\. run function deusex:opening_done", oflash)
if not m:
    errors.append("opening_flash never ends the cutscene")
else:
    end_k = int(m.group(1))
    print("burst ends %d ticks (%.1f s) after the drop" % (end_k, end_k / 20.0))
    # replay opening_flash with the shipped pacing maths: the wavefront has to finish expanding
    # while the title is still up, or the player sees the blast frozen mid-shock and then cut.
    trace = []
    for k in range(1, end_k):
        S = {"#E": k, "#drop": 0, "#3": 3, "#bf": 0}
        mclog.run("opening_flash", S, [])
        trace.append(S.get("#bf", 0))
    print("burst frame index per tick: %s" % trace)
    if trace != sorted(trace):
        errors.append("the burst frame index goes backwards: %s" % trace)
    if hi_bf not in trace:
        errors.append("the pacing only reaches frame %d of %d before the title resets at tick %d: "
                      "the blast never finishes expanding" % (max(trace), hi_bf, end_k))
    if end_k - trace.index(hi_bf) < 3:
        errors.append("the fully expanded frame is up for %d tick(s) before the cut: the last "
                      "stage of the shock is invisible" % (end_k - trace.index(hi_bf)))
    if len(set(trace)) < hi_bf:
        errors.append("burst pacing skips frames %s"
                      % sorted(set(range(hi_bf + 1)) - set(trace)))
done = open(os.path.join(FUN, "opening_done.mcfunction"), encoding="utf-8").read()
if "title @a reset" not in done:
    errors.append("opening_done leaves the blast title on the screen instead of returning to the game")
if "scoreboard players set #ostage deusex 4" not in done:
    errors.append("opening_done does not advance #ostage, so opening_flash runs forever")
otick = open(os.path.join(FUN, "opening_tick.mcfunction"), encoding="utf-8").read()
if "matches 4 run" in otick:
    errors.append("opening_tick still draws for ostage 4: the cutscene never ends")
burstf = open(os.path.join(FUN, "opening_burst.mcfunction"), encoding="utf-8").read()
if "deusex:boom" not in burstf:
    errors.append("opening_burst does not fire the boom on the drop")
if "#flashd" not in burstf:
    errors.append("opening_burst does not arm the random sky flash for the rest of the song")
tr_ = open(os.path.join(FUN, "title_red_burst.mcfunction"), encoding="utf-8").read()
if '"$(burst)"' not in tr_ or "deusex:burst" not in tr_:
    errors.append("title_red_burst must carry the $(burst) glyph in the burst font")

# The other half of "seamless": the veil has to be in that same string. tick.mcfunction will not run
# wash_draw until #ostage 4, and opening_done is only called at #k 50, so before 1.0.31 the first
# pixel of red sky appeared two and a half seconds after the slam - wash_tick had silently ramped
# #wash to 14 the whole time with nothing on screen to show it. The burst title is the only string
# this function owns on the drop tick, and skyview measures the cell it puts there at 100% of the
# frame: the subtitle slot would have covered too (the cell is 2.5x the viewport even at scale 2)
# at the price of a second packet per tick and a half-scaled box that opening_done then jumps.
#
# Overlapping the two cells is a pen question, and the answer is checkable rather than arguable.
# Gui.renderTitle puts the left edge at guiWidth/2 + scale * int(-width/2), so a cell's screen x is
# fixed by (string width, pen relative to the string start). title_red is the string the veil is
# measured on for the rest of the song, so if the two agree on both numbers the burst's wash is
# pixel-for-pixel the wash the player keeps watching - and the blast cell has to sit on the veil's
# own pen, not beside it, or each half-covers the screen.
def title_cells(f):
    """(string width, [(pen, font, codepoint)]) for one shipped `$title @a title [...]` line."""
    txt = open(os.path.join(FUN, f + ".mcfunction"), encoding="utf-8").read()
    m = re.search(r"^\$title @a title (\[.*)$", txt, re.M)
    if not m:
        return None, []
    raw = re.sub(r"\$\(([a-z0-9_]+)\)", lambda mo: PRESET.get(mo.group(1), ""), m.group(1))
    try:
        els = json.loads(raw)
    except Exception as e:
        errors.append("%s: bad title JSON: %s" % (f, e))
        return None, []
    acc, cells = 0, []
    for el in els:
        if isinstance(el, str):
            continue
        fn = el.get("font", "minecraft:default")
        for c in el.get("text", ""):
            a = FONT.get(fn.replace("deusex:", ""), [{}])[0].get(ord(c), 0)
            cells.append((acc, fn, ord(c)))
            acc += a
    return acc, cells

w_ref, ref = title_cells("title_red")
w_bst, bst = title_cells("title_red_burst")
pen = lambda cells, fn: sorted({p for p, f2, _ in cells if f2 == "deusex:" + fn})
fx_ref, fx_b = pen(ref, "fx"), pen(bst, "fx")
bu_b = pen(bst, "burst")
burst_adv = [FONT["burst"][0][ord(PRESET["burst"]) + i] for i in range(16)]
if not fx_b:
    errors.append("title_red_burst carries no deusex:fx cell, so the screen is plain until opening_"
                  "done hands over to wash_draw 50 ticks (2.5 s) after the heart bursts")
elif not bu_b:
    errors.append("title_red_burst carries no deusex:burst cell")
elif w_bst != w_ref or fx_b != fx_ref:
    errors.append("the burst title puts the veil cell at pen %s in a string of width %s, but the "
                  "shipped veil title is %s in %s: Gui.renderTitle centres by string width, so the "
                  "wash would jump sideways the moment the blast appears and again when it leaves"
                  % (fx_b, w_bst, fx_ref, w_ref))
elif abs(bu_b[0] - fx_b[0]) > max(burst_adv) - min(burst_adv):
    errors.append("the burst cell is at pen %d and the veil cell at %d: that is %d font units apart, "
                  "more than the %d-unit spread of the sixteen blast advances, so the tspace between "
                  "them no longer walks the pen back exactly one cell and the blast covers the "
                  "sides while the red sits in the middle (or the other way round)"
                  % (bu_b[0], fx_b[0], bu_b[0] - fx_b[0], max(burst_adv) - min(burst_adv)))
else:
    print("burst title: veil cell pen %+d in a string of width %d, identical to title_red; blast "
          "overlaps it to within %d units of drift across the %d frames"
          % (fx_b[0], w_bst, max(burst_adv) - min(burst_adv), len(burst_adv)))

# Both titles must agree on the LEVEL, too, or the hand-over at opening_done is a step even though
# the geometry matches. wash_level is the single home of the arithmetic; if either caller keeps its
# own copy the two drift the next time #tint or #washmax moves.
wl = open(os.path.join(FUN, "wash_level.mcfunction"), encoding="utf-8").read()
for probe in ("#lv deusex = #tint deusex", "#lv deusex *= #wash deusex",
              "#lv deusex /= #washmax deusex", "function deusex:lv_char"):
    if probe not in wl:
        errors.append("wash_level no longer does `%s`, which is half of the veil level maths" % probe)
for f, why in (("tint_draw", "the held wash and the ending's drain"),
               ("opening_flash", "the wash under the blast")):
    txt = open(os.path.join(FUN, f + ".mcfunction"), encoding="utf-8").read()
    if "function deusex:wash_level" not in txt:
        errors.append("%s computes its own veil level instead of calling wash_level, so %s and the "
                      "burst can disagree about which red_lv cell is on screen" % (f, why))
if "function deusex:wash_level" in oflash and "function deusex:title_red_burst" in oflash and \
        oflash.index("function deusex:wash_level") > oflash.index("function deusex:title_red_burst"):
    errors.append("opening_flash picks the wash cell after it emits the title, so the burst always "
                  "shows the level one tick behind - and the first frame shows no level at all")
if "title @a reset" in done and "scoreboard players set #wlast deusex -1" not in done:
    errors.append("opening_done resets the blast title, which takes the veil with it, but leaves "
                  "#wlast holding the level the string was painting. wash_draw only repaints when "
                  "#wlv changes, so nothing redraws it: the screen would clear to plain sky at the "
                  "exact moment the song proper starts. -1 is a level the gate cannot hold")

# ---------- mcfunction parser shape ----------
# A line only continues onto the next one when it ends with a backslash, so a
# multi-line command written without them silently becomes N broken commands.
for f in sorted(funcs):
    txt = open(os.path.join(FUN, f + ".mcfunction"), encoding="utf-8").read()
    if "[" not in txt:
        continue
    cmds, buf = [], ""
    for line in txt.splitlines():
        if line.endswith("\\"):
            buf += line[:-1]
        else:
            cmds.append((buf + line).strip())
            buf = ""
    depth = 0
    for c in cmds:
        depth += c.count("[") - c.count("]")
    if depth:
        errors.append("%s: unbalanced brackets across %d commands" % (f, len(cmds)))
    # ... but that total hides the real failure: a chunk line that forgets its trailing
    # backslash leaves the closing "]" as its own command, so the list command is short
    # one bracket and the whole function fails to load. Check each command on its own.
    for n, c in enumerate(cmds):
        if c.count("[") != c.count("]"):
            errors.append("%s command %d: %d '[' vs %d ']' - a continued line is missing "
                          "its trailing backslash" % (f, n + 1, c.count("["), c.count("]")))
            break
        if c.count("{") != c.count("}"):
            errors.append("%s command %d: unbalanced braces" % (f, n + 1))
            break
if "storage deusex:lyrics list" not in open(os.path.join(FUN, "lyric_pick.mcfunction"), encoding="utf-8").read():
    errors.append("lyric_pick must use 'storage deusex:lyrics list[...]' with a space")
for f in sorted(funcs):
    txt = open(os.path.join(FUN, f + ".mcfunction"), encoding="utf-8").read()
    for m in re.finditer(r"storage ([a-z0-9_]+:[a-z0-9_]+)\.(?!\.)", txt):
        errors.append("%s: %s uses a dot where a space is required" % (f, m.group(0)))

# ---------- release identity ----------
# A release is three files that have to move together: the loader's version, the notes the player
# reads, and the name the build script writes. Two of them disagreeing is invisible in game - the
# jar installs, the effects run, and the person comparing recordings has no idea which build they
# have - so the bump is checked rather than trusted.
rdtxt = open(os.path.join(EXT, "README.txt"), encoding="utf-8").read()
toml = open(os.path.join(EXT, "META-INF/neoforge.mods.toml"), encoding="utf-8").read()
mread = re.search(r"^Version (\d+\.\d+\.\d+)$", rdtxt, re.M)
mtoml = re.search(r'^version="(\d+\.\d+\.\d+)"', toml, re.M)
if not mread or not mtoml:
    errors.append("README.txt or neoforge.mods.toml has no parseable version line")
else:
    vread, vtoml = mread.group(1), mtoml.group(1)
    if vread != vtoml:
        errors.append("README says %s but the loader says %s" % (vread, vtoml))
    jarline = open(os.path.join(ROOT, "build_jar.py"), encoding="utf-8").read()
    mjar = re.search(r"OUT = .*/DeusExMachina-NeoForge-1\.21\.1-(\d+\.\d+\.\d+)-", jarline)
    if not mjar:
        errors.append("build_jar.py's output name does not carry a version")
    elif mjar.group(1) != vtoml:
        errors.append("build_jar.py writes %s but the mod declares itself %s" % (mjar.group(1), vtoml))
    heads = re.findall(r"^WHAT CHANGED IN (\d+\.\d+\.\d+)$", rdtxt, re.M)
    # selftest prints the build id into the player's chat, because "the sky is still not red" and
    # "you are still running the old jar" are indistinguishable from out here. It is a literal in a
    # function, so it has to be checked against the loader rather than trusted to remember.
    selftxt = open(os.path.join(FUN, "selftest.mcfunction"), encoding="utf-8").read()
    mst = re.search(r'\{"text":"(\d+\.\d+\.\d+)","color":"red"', selftxt)
    if not mst:
        errors.append("selftest.mcfunction does not print a build id")
    elif mst.group(1) != vtoml:
        errors.append("selftest reports build %s while the loader says %s" % (mst.group(1), vtoml))
    for d in ("selftest", "test_wash", "test_flash"):
        if not os.path.isfile(os.path.join(FUN, d + ".mcfunction")):
            errors.append("the diagnostic function deusex:%s is missing" % d)
        elif "/function deusex:%s " % d not in rdtxt and "/function deusex:%s\n" % d not in rdtxt:
            errors.append("README does not document /function deusex:%s" % d)
    if not heads or heads[0] != vtoml:
        errors.append("the newest changelog header is %s but the mod declares itself %s"
                      % (heads[0] if heads else "absent", vtoml))
    # compared as numbers, because 1.0.6 sorts above 1.0.15 as text and the README is older than it
    # looks
    nums = [tuple(int(x) for x in h.split(".")) for h in heads]
    if nums != sorted(nums, reverse=True):
        errors.append("the changelog is not in descending order: %s" % heads)

# ---------- client code ----------
# Everything above is data, and data fails loudly: a broken function is in the server log the second
# the pack loads. The song volume slider is the one part of this mod that is compiled, and every way
# it can be wrong is quiet. Under the lowcodefml loader the earlier jars used a mod class is never
# constructed, so the listener is never registered, the slider never appears in Options and the song
# stays at full volume with nothing printed. A loaderVersion the provider does not satisfy drops the
# mod before its classes are even read. Bytecode newer than the game's own Java throws on load and
# takes the whole mod with it. So the classes are checked here, and the run checks the rest.
CLASS_DIR = "net/deusexmachina/client"
WANTED = {
    "DeusExMachinaMod.class",
    "MusicVolume.class",
    "MusicVolume$Slider.class",
    "MusicVolume$Scaled.class",
    "MusicVolume$ScaledTickable.class",
}
found = {}
for base, _, files in os.walk(EXT):
    for f in files:
        if f.endswith(".class"):
            found[os.path.relpath(os.path.join(base, f), EXT).replace(os.sep, "/")] = os.path.join(base, f)
mloader = re.search(r'^modLoader="(\w+)"', toml, re.M)
mrange = re.search(r'^loaderVersion="([^"]+)"', toml, re.M)
if found:
    if not mloader or mloader.group(1) != "javafml":
        errors.append("the jar carries %d class files but modLoader is %s; lowcodefml never "
                      "constructs a mod class, so the song volume slider would never register"
                      % (len(found), mloader.group(1) if mloader else "absent"))
    # The javafml provider reports the FML artifact's own version - 4.0.45 on NeoForge 21.1.265 - not
    # the Minecraft version, so the [21.1,) range that templates copy in rejects the very loader the
    # mod is asking for. This was not theoretical: the first dev run failed exactly this way.
    if not mrange or mrange.group(1) != "[1,)":
        errors.append('loaderVersion is %s; the javafml provider reports 4.0.45 on 21.1.265, so the '
                      'only range that loads is "[1,)"' % (mrange.group(1) if mrange else "absent"))
    outside = sorted(r for r in found if not r.startswith(CLASS_DIR + "/"))
    if outside:
        errors.append("class files outside %s: %s" % (CLASS_DIR, ", ".join(outside)))
    dev = sorted(r for r in found if "DevProbe" in r)
    if dev:
        errors.append("the development probe is in the shipped jar: %s" % ", ".join(dev))
    missing = sorted(WANTED - {r.rsplit("/", 1)[-1] for r in found})
    if missing:
        errors.append("client classes missing from the jar: %s" % ", ".join(missing))
    for rel, path in sorted(found.items()):
        head = open(path, "rb").read(8)
        major = int.from_bytes(head[6:8], "big")
        if head[:4] != b"\xca\xfe\xba\xbe":
            errors.append("%s is not a class file" % rel)
        elif major > 65:
            errors.append("%s is Java %d bytecode but the game runs Java 21 (65); UnsupportedClass"
                          "VersionError skips the whole mod" % (rel, major - 44))
    # Names are the other silent failure. These classes compile against Mojang official mappings and
    # run in a production client that speaks nothing else, so every game class they mention has to
    # exist at that exact path - SoundSource.RECORD (it is RECORDS) compiled only because the dev
    # environment caught it, and a wrong member would still only surface at the first sound.
    mcs = os.path.join(ROOT, "mcsrc")
    if not os.path.isdir(mcs):
        warns.append("mcsrc is missing, so the client classes' game references went unchecked")
    else:
        for rel, path in sorted(found.items()):
            blob = open(path, "rb").read()
            for owner in sorted({m.group(0).split(b"$")[0].decode() for m in
                                 re.finditer(rb"net/minecraft/[A-Za-z0-9/_$]+", blob)}):
                if not os.path.isfile(os.path.join(mcs, owner + ".java")):
                    errors.append("%s references %s, which is not a 1.21.1 class" %
                                  (rel, owner.replace("/", ".")))

print("\nERRORS:", len(errors))
for e in errors:
    print("  -", e)
print("WARNINGS:", len(warns))
for w in warns:
    print("  -", w)
sys.exit(1 if errors else 0)
