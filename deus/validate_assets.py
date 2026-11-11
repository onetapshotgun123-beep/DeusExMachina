"""Validate the shipped 1.1.0 jar: the thin deusex: command shim plus the client show mod.

Since the rewrite the show (audio, timeline, lyrics, heart, wash, sky, rain) lives in compiled client
classes, so the old function-walking rules are gone. What still has to be right, and is checked here
against the artifacts that actually ship:

  * the shim is exactly the command bridge - eight functions, no /playsound, /title, /particle,
    /weather or /kill, and load leaves the world's weather cycle ON;
  * the client audio is the recording the timeline was measured against: main_track.ogg is exactly
    ShowConstants.TOTAL_SAMPLES frames at SAMPLE_RATE, the first full-band slam lands on DROP_TICKS,
    and every lyric window sits on the singing (the onset-flux comb, ported from the data pack era);
  * the corner flash is the drums the player hears: the jar ships a per-tick kick envelope baked from
    that same recording, the HUD reads it at the heard sample, and the peak stays a hint of red;
  * the show textures are the atlases ShowRender blits, at the exact cell grids it reads;
  * the manifest, mixin config, README and build name all agree on the version, the loader is
    javafml with the range that actually loads, and no development probe is in the jar;
  * the compiled classes are Java 21 bytecode, carry the mod/mixins/network/server, and reference
    only real 1.21.1 game classes.

The jar is built by build_jar.py first; this reads it back so a stale tree cannot pass. Run with no
arguments to validate the default Downloads jar, or pass a path.
"""

import io
import json
import os
import re
import sys
import zipfile

import numpy as np
import soundfile as sf
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
CLIENT = os.path.join(ROOT, "client")
RES = os.path.join(CLIENT, "src", "main", "resources")
ASSETS = os.path.join(RES, "assets", "deusexmachina")
JAVA = os.path.join(CLIENT, "src", "main", "java", "net", "deusexmachina")
JAR = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
    "~/Downloads/DeusExMachina-NeoForge-1.21.1-1.1.0.jar")

errors = []
warns = []

if not os.path.isfile(JAR):
    print("ERROR: jar not found: %s (run build_jar.py first)" % JAR)
    sys.exit(1)
z = zipfile.ZipFile(JAR)
names = set(z.namelist())


def read(rel):
    return z.read(rel).decode("utf-8")


# ---------- constants the timeline and the audio agree on ----------
const = open(os.path.join(JAVA, "ShowConstants.java"), encoding="utf-8").read()


def cint(name):
    m = re.search(r"\b%s\s*=\s*(\d+)" % name, const)
    if not m:
        errors.append("ShowConstants has no %s" % name)
        return None
    return int(m.group(1))


SAMPLE_RATE = cint("SAMPLE_RATE")
TOTAL_SAMPLES = cint("TOTAL_SAMPLES")
DROP_TICKS = cint("DROP_TICKS")
mlead = re.search(r"RAIN_TICKS\s*=\s*DROP_TICKS\s*-\s*(\d+)", const)
mtied = re.search(r"RAIN_TICKS\s*=\s*DROP_TICKS\s*;", const)
RAIN_LEAD = int(mlead.group(1)) if mlead else None
if RAIN_LEAD is not None and DROP_TICKS is not None:
    RAIN_TICKS = DROP_TICKS - RAIN_LEAD
elif mtied and DROP_TICKS is not None:
    # Rain is ordered on the drop tick itself: the storm starts as the heart bursts.
    RAIN_TICKS = DROP_TICKS
else:
    RAIN_TICKS = cint("RAIN_TICKS")

# ---------- the shim is a command bridge, nothing more ----------
SHIM = {"load", "tick", "start", "pause", "resume", "stop", "loop", "selftest"}
shim_funcs = {n[len("data/deusex/function/"):-len(".mcfunction")]
              for n in names if n.startswith("data/deusex/function/") and n.endswith(".mcfunction")}
if shim_funcs != SHIM:
    errors.append("shim functions are %s, expected exactly %s"
                  % (sorted(shim_funcs), sorted(SHIM)))
for f in sorted(shim_funcs):
    txt = read("data/deusex/function/%s.mcfunction" % f)
    for cmd in ("playsound", "stopsound", "title", "particle", "weather", "kill", "summon"):
        if re.search(r"(?m)^\s*" + re.escape(cmd), txt):
            errors.append("shim %s runs '%s' - the show is the client mod's now" % (f, cmd))
    for r in re.findall(r"function deusex:([a-z0-9_]+)", txt):
        if r not in shim_funcs:
            errors.append("shim %s calls missing deusex:%s" % (f, r))
loadtxt = read("data/deusex/function/load.mcfunction")
if "gamerule doWeatherCycle true" not in loadtxt:
    errors.append("shim load does not leave doWeatherCycle true: natural weather would stay owned")
if "gamerule doWeatherCycle false" in loadtxt:
    errors.append("shim load turns the weather cycle off - the orchestrator owns rain only mid-show")
if "scoreboard objectives add deusex dummy" not in loadtxt:
    errors.append("shim load does not create the deusex objective the orchestrator polls")
for fn, code in (("start", 1), ("pause", 2), ("resume", 3), ("stop", 4), ("loop", 5)):
    txt = read("data/deusex/function/%s.mcfunction" % fn)
    if "scoreboard players set #cmd deusex %d" % code not in txt:
        errors.append("shim %s does not set #cmd %d" % (fn, code))
for tag, target in (("load", "deusex:load"), ("tick", "deusex:tick")):
    tj = json.loads(read("data/minecraft/tags/function/%s.json" % tag))
    if target not in tj.get("values", []):
        errors.append("%s.json does not call %s" % (tag, target))
for n in names:
    if n.startswith("assets/minecraft/") or n.startswith("assets/deusex/"):
        errors.append("the shim ships legacy asset %s - the show assets live under deusexmachina" % n)
    if n.endswith(".mcfunction") and not n.startswith("data/deusex/function/"):
        errors.append("unexpected function outside the shim: %s" % n)

# ---------- client sounds.json and the audio files ----------
sounds = json.loads(read("assets/deusexmachina/sounds.json"))
for key in ("main_track", "heartbeat", "boom", "boom_rise"):
    if key not in sounds:
        errors.append("sounds.json has no %s event" % key)
        continue
    for prov in sounds[key].get("sounds", []):
        rel = prov["name"] if isinstance(prov, dict) else prov
        rel = rel.split(":", 1)[1] if ":" in rel else rel
        if "assets/deusexmachina/sounds/%s.ogg" % rel not in names:
            errors.append("sounds.json %s points at %s.ogg, not in the jar" % (key, rel))
mt = sounds.get("main_track", {}).get("sounds", [{}])[0]
if not (isinstance(mt, dict) and mt.get("stream") is True):
    errors.append("main_track must stream (stream:true) or the whole 10 MB decode blocks the start")

snd_dir = os.path.join(ASSETS, "sounds")
full = sf.info(os.path.join(snd_dir, "main_track.ogg"))
print("main_track %d frames, %d Hz, %d ch, %.3f s"
      % (full.frames, full.samplerate, full.channels, full.frames / float(full.samplerate)))
if SAMPLE_RATE is not None and full.samplerate != SAMPLE_RATE:
    errors.append("main_track is %d Hz but ShowConstants.SAMPLE_RATE is %d"
                  % (full.samplerate, SAMPLE_RATE))
if TOTAL_SAMPLES is not None and full.frames != TOTAL_SAMPLES:
    errors.append("main_track is %d frames but ShowConstants.TOTAL_SAMPLES is %d: the server clock "
                  "would drift off the file the clients decode" % (full.frames, TOTAL_SAMPLES))
if full.channels != 2:
    errors.append("main_track is %d channels, expected stereo" % full.channels)
for key in ("heartbeat", "boom", "boom_rise"):
    info = sf.info(os.path.join(snd_dir, key + ".ogg"))
    if info.samplerate != 44100:
        errors.append("%s.ogg is %d Hz, not 44100" % (key, info.samplerate))


# ---------- the drop lands on the slam (ported from the data pack validator) ----------
def first_slam(path):
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


if DROP_TICKS is not None:
    try:
        slam, runner, heights = first_slam(os.path.join(snd_dir, "main_track.ogg"))
        print("slam measured %.3f s (+%.0f dB), next %.3f s (+%.0f dB); DROP_TICKS %d = %.3f s"
              % (slam, heights[0], runner, heights[1], DROP_TICKS, DROP_TICKS / 20.0))
        if heights[1] > 0.6 * heights[0]:
            warns.append("the slam is not unmistakable: %.3f s +%.0f dB vs %.3f s +%.0f dB"
                         % (slam, heights[0], runner, heights[1]))
        if abs(DROP_TICKS / 20.0 - slam) > 0.06:
            errors.append("DROP_TICKS %d is %.3f s but the first full-band slam measures %.3f s"
                          % (DROP_TICKS, DROP_TICKS / 20.0, slam))
    except Exception as exc:
        warns.append("could not measure the slam (%s)" % exc)
if RAIN_LEAD is not None and RAIN_LEAD < 100:
    errors.append("RAIN_TICKS leads the drop by only %d ticks; the vanilla rain ramp needs 100"
                  % RAIN_LEAD)

# ---------- lyric windows vs the singing (onset-flux comb, ported) ----------
hud = open(os.path.join(JAVA, "client", "ShowHudData.java"), encoding="utf-8").read()


def intarr(name):
    m = re.search(r"int\[\]\s+%s\s*=\s*\{([^}]*)\}" % name, hud)
    if not m:
        errors.append("ShowHudData has no %s" % name)
        return []
    return [int(x) for x in re.findall(r"-?\d+", m.group(1))]


LYRIC_START = intarr("LYRIC_START")
LYRIC_END = intarr("LYRIC_END")
if len(LYRIC_START) != 74 or len(LYRIC_END) != 74:
    errors.append("expected 74 lyric windows, got %d/%d" % (len(LYRIC_START), len(LYRIC_END)))
if LYRIC_START != sorted(LYRIC_START):
    errors.append("lyric starts not increasing")
for i, (a, b) in enumerate(zip(LYRIC_START, LYRIC_END)):
    if b <= a:
        errors.append("lyric window %d ends (%d) before it starts (%d)" % (i, b, a))
        break

y, sr = sf.read(os.path.join(snd_dir, "main_track.ogg"), dtype="float32")
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


secs = [s / 20.0 for s in LYRIC_START]
rng = np.random.default_rng(11)
for name, a, b in [("verse1+chorus1", 0, 135), ("verse2+chorus2", 135, 220),
                   ("bridge", 300, 344), ("final A", 400, 455), ("final B", 455, 546)]:
    ts = [s for s in secs if a <= s < b]
    if not ts:
        errors.append("lyric sync section %s has no windows" % name)
        continue
    c = comb(ts)
    zz = (c - c.mean()) / c.std()
    best = lags[int(np.argmax(zz))]
    nulls = []
    for _ in range(60):
        sh = np.sort(rng.uniform(min(ts), max(ts), len(ts)))
        cc = comb(sh)
        nulls.append(((cc - c.mean()) / c.std()).max())
    print("lyric sync %-14s n=%2d lag %+.2f s (z=%.2f, null 90th %.2f)"
          % (name, len(ts), best, zz.max(), np.percentile(nulls, 90)))
    if abs(best) > 0.5 and zz.max() > np.percentile(nulls, 90):
        errors.append("lyric section %s sits %+.2f s off the singing (z=%.2f beats the null)"
                      % (name, best, zz.max()))

# ---------- show textures are the atlases ShowRender blits ----------
TEX = {
    "box.png": (92, 416), "digits.png": (96, 8), "disc_c.png": (320, 128),
    "disc_v0.png": (384, 256), "disc_v1.png": (384, 256), "disc_v2.png": (384, 256),
    "disc_v3.png": (384, 256), "disc_v4.png": (384, 256),
    "heart_burst.png": (4096, 128), "heart_pulse.png": (3328, 256), "lyric.png": (1536, 2368),
    "boss_frame.png": (1024, 255), "boss_frame_glow.png": (1056, 287),
    "boss_fill.png": (970, 118), "boss_name.png": (162, 26),
    "strike_sigils.png": (3584, 512),
}


def validate_show_texture(archive, entries, fn, size, issues):
    """Inspect shipped bytes, never a potentially newer source PNG."""
    rel = "assets/deusexmachina/textures/show/" + fn
    if rel not in entries:
        issues.append("[texture-missing] show texture %s missing from the jar" % fn)
        return
    try:
        with Image.open(io.BytesIO(archive.read(rel))) as image:
            image.load()
            if image.size != size:
                issues.append("[texture-size] %s is %s, ShowRender reads a %dx%d atlas"
                              % (fn, image.size, *size))
                return
            if fn != "strike_sigils.png":
                return
            alpha = image.convert("RGBA").getchannel("A")
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        issues.append("[texture-decode] %s cannot be decoded from the jar: %s" % (fn, exc))
        return
    masks = {}
    for kind, label in enumerate(("bolt", "grasp", "siphon", "barrage", "laser", "vortex", "rupture")):
        cell = alpha.crop((kind * 512, 0, (kind + 1) * 512, 512))
        lo, hi = cell.getextrema()
        if hi == 0:
            issues.append("[sigil-empty] %s cell %d (%s) has no visible pixels" % (fn, kind, label))
        elif lo != 0:
            issues.append("[sigil-transparency] %s cell %d (%s) has no transparent background"
                          % (fn, kind, label))
        else:
            mask = cell.tobytes()
            if mask in masks:
                issues.append("[sigil-duplicate] %s cells %d and %d have identical alpha masks"
                              % (fn, masks[mask], kind))
            else:
                masks[mask] = kind


for fn, size in TEX.items():
    validate_show_texture(z, names, fn, size, errors)

# ---------- the storm and the boss's fall ----------
mfirst = re.search(r"STORM_FIRST_TICKS\s*=\s*DROP_TICKS\s*\+\s*(\d+)", const)
if not mfirst:
    errors.append("STORM_FIRST_TICKS is not tied to DROP_TICKS: the storm would drift off the drop")
WARN_TICKS = cint("STORM_WARN_TICKS")
LOCK_TICKS = cint("STORM_LOCK_TICKS")
PERIOD_TICKS = cint("STORM_PERIOD_TICKS")
DEBUFF_TICKS = cint("STORM_DEBUFF_TICKS")
if WARN_TICKS is not None and LOCK_TICKS is not None:
    if WARN_TICKS <= LOCK_TICKS or LOCK_TICKS <= 0:
        errors.append("storm warning %s must contain the %s-tick lock with time to spare"
                      % (WARN_TICKS, LOCK_TICKS))
if PERIOD_TICKS is not None and WARN_TICKS is not None and PERIOD_TICKS <= WARN_TICKS:
    errors.append("storm period %d is not longer than its %d-tick warning"
                  % (PERIOD_TICKS, WARN_TICKS))
if DEBUFF_TICKS != 80:
    errors.append("storm debuffs last %s ticks, not the four seconds (80 ticks) the show promises"
                  % DEBUFF_TICKS)
mrad = re.search(r"STORM_RADIUS\s*=\s*([\d.]+)F", const)
if not mrad or float(mrad.group(1)) <= 0.0:
    errors.append("STORM_RADIUS is missing or zero: a zero-radius bolt cannot be dodged")
mdmg = re.search(r"STORM_DAMAGE\s*=\s*([\d.]+)F", const)
if not mdmg or float(mdmg.group(1)) < 10.0:
    errors.append("STORM_DAMAGE %s is under half the vanilla health bar"
                  % (mdmg.group(1) if mdmg else "absent"))

# ---------- the disruptive attacks and the seal's second phase ----------
# Kind numbering is checked by validate_combo_constants below. The strike payload still packs
# seven kinds above its two state bits; storm metadata now carries both wave kinds explicitly.
for kname in ("GRASP_RADIUS", "SIPHON_RADIUS", "SIPHON_DRAIN", "BARRAGE_SHARD_RADIUS",
              "LASER_RADIUS"):
    m = re.search(r"\b%s\s*=\s*([\d.]+)F" % kname, const)
    if not m or float(m.group(1)) <= 0.0:
        errors.append("%s is missing or zero: the attack would do nothing" % kname)
BARRAGE_SHARDS = cint("BARRAGE_SHARDS")
if BARRAGE_SHARDS is not None and BARRAGE_SHARDS < 2:
    errors.append("BARRAGE_SHARDS is %d: a barrage needs more than one shard" % BARRAGE_SHARDS)
P2_PERIOD = cint("STORM_PHASE2_PERIOD_TICKS")
P2_REST = cint("STORM_PHASE2_REST_TICKS")
REST_TICKS = cint("STORM_REST_TICKS")
if P2_PERIOD is None or PERIOD_TICKS is None or P2_PERIOD >= PERIOD_TICKS:
    errors.append("phase 2 storm period %s is not faster than the %s-tick phase 1"
                  % (P2_PERIOD, PERIOD_TICKS))
elif WARN_TICKS is not None and P2_PERIOD <= WARN_TICKS:
    errors.append("phase 2 storm period %d leaves no warning before the next wave" % P2_PERIOD)
if P2_REST is None or REST_TICKS is None or P2_REST >= REST_TICKS:
    errors.append("phase 2 rest %s is not shorter than the %s-tick phase 1 rest"
                  % (P2_REST, REST_TICKS))

# The advancement ships as data, and the orchestrator names it in code; both have to agree or the
# boss's death would silently grant nothing.
adv_rel = "data/deusexmachina/advancement/server_free.json"
if adv_rel not in names:
    errors.append("free-server advancement %s missing from the jar" % adv_rel)
else:
    adv = json.loads(read(adv_rel))
    display = adv.get("display", {})
    if display.get("title") != "Server is finally Free.. At last.":
        errors.append("advancement title is %r, not 'Server is finally Free.. At last.'"
                      % display.get("title"))
    if display.get("icon", {}).get("id") != "minecraft:nether_star":
        errors.append("advancement icon is %r, not a nether star"
                      % display.get("icon", {}).get("id"))
    if display.get("frame") != "challenge" or display.get("show_toast") is not True:
        errors.append("advancement must be a challenge with a toast")
    criteria = adv.get("criteria", {})
    if list(criteria) != ["granted"] or criteria["granted"].get("trigger") != "minecraft:impossible":
        errors.append("advancement needs exactly one impossible criterion named 'granted'")
    if adv.get("requirements") not in (None, [["granted"]]):
        errors.append("advancement requirements do not point at its one criterion")
orch = open(os.path.join(JAVA, "server", "ShowOrchestrator.java"), encoding="utf-8").read()
madv = re.search(r'FREE_ADVANCEMENT\s*=\s*ResourceLocation\.fromNamespaceAndPath\("([^"]+)",'
                 r'\s*"([^"]+)"\)', orch)
if not madv or "%s:%s" % (madv.group(1), madv.group(2)) != "deusexmachina:server_free":
    errors.append("ShowOrchestrator's FREE_ADVANCEMENT %s does not name deusexmachina:server_free"
                  % (("%s:%s" % (madv.group(1), madv.group(2))) if madv else "absent"))
mcriterion = re.search(r'FREE_CRITERION\s*=\s*"([^"]+)"', orch)
if not mcriterion or mcriterion.group(1) != "granted":
    errors.append("FREE_CRITERION %s does not match the advancement's criterion"
                  % (mcriterion.group(1) if mcriterion else "absent"))
if not re.search(r"private void finishDefeat\(\).*?grantFreeAdvancement\(\)", orch, re.S):
    errors.append("the boss's defeat does not grant the advancement")

# The three extra attacks must actually be dispatched, and the bolt must be drawn by the mod: a
# returned vanilla LightningBolt would bypass the red render and the storm's own impact handling.
for meth in ("boltImpact", "graspImpact", "siphonImpact", "barrageImpact", "laserImpact"):
    if not re.search(r"private void %s\(" % meth, orch):
        errors.append("ShowOrchestrator has no %s: that attack would never land" % meth)
if re.search(r"EntityType\.LIGHTNING_BOLT|addFreshEntity\(.*[Ll]ightning", orch):
    errors.append("ShowOrchestrator still spawns a vanilla LightningBolt entity")
if not re.search(r"int period\s*=\s*bossPhase2\s*\?\s*ShowConstants\.STORM_PHASE2_PERIOD_TICKS",
                 orch):
    errors.append("scheduleStorms does not switch to the phase 2 storm period")
if not re.search(r"WAVE_KINDS\s*\[\s*\(stormWave\s*-\s*1\)\s*%\s*WAVE_KINDS\.length\s*\]", orch):
    errors.append("scheduleStorms does not rotate the wave kinds")
srender = open(os.path.join(JAVA, "client", "ShowStrikeRender.java"), encoding="utf-8").read()
if "RenderType.lightning()" not in srender:
    errors.append("ShowStrikeRender draws nothing through RenderType.lightning(): the attack marks "
                  "would be invisible")

# ---------- the seal lance, the blessing and the reset command ----------
# These source contracts deliberately inspect balanced method/block bodies, not regexes spanning
# unrelated methods. Pure functions also let sabotage tests supply strings without touching Java.
def java_compact(source):
    tokens = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/'
    source = re.sub(tokens, lambda m: " " if m[0].startswith(("//", "/*")) else m[0], source)
    return re.sub(r"\s+", "", source)


def java_block(code, header):
    start = code.find(header + "{")
    if start < 0:
        return ""
    start += len(header) + 1
    depth = 1
    for match in re.finditer(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]', code[start:]):
        if match[0] == "{":
            depth += 1
        elif match[0] == "}":
            depth -= 1
            if depth == 0:
                return code[start:start + match.start()]
    return ""


def java_method(code, name):
    # Require a declaration (or a package-private constructor), not an if(method(...)) call.
    declaration = r"(?:(?:public|private|protected)(?:static)?[\w<>,.\[\]]+|(?:^|[;}]))"
    match = re.search(declaration + re.escape(name) + r"\([^;{}]*\)\{", code)
    return java_block(code, match[0][:-1]) if match else ""


def validate_lance_constants(source, issues):
    code = java_compact(source)

    def number(name):
        match = re.search(r"(?:int|float)" + re.escape(name) + r"=(-?\d+(?:\.\d+)?)[Ff]?;", code)
        return float(match[1]) if match else None

    count, count2 = (number(n) for n in ("LASER_VOLLEY", "LASER_VOLLEY_P2"))
    counts_ok = (count is not None and count2 is not None
                 and 4 <= count <= 5 and 8 <= count2 <= 10)
    if not counts_ok:
        issues.append("[lance-counts] lance phases need 4..5 beams in phase 1 and 8..10 in phase 2")
    damage, damage2 = (number(n) for n in ("LASER_VOLLEY_DAMAGE", "LASER_VOLLEY_P2_DAMAGE"))
    damage_ok = (damage is not None and damage2 is not None and 3 <= damage <= 8
                 and damage < damage2 <= 12)
    if not damage_ok or (counts_ok and not (20 <= count * damage <= 60
                                           and 60 <= count2 * damage2 <= 150
                                           and 2 <= count2 * damage2 / (count * damage) <= 5)):
        issues.append("[lance-damage] per-beam damage must escalate and total volley damage must be 20..60 then 60..150 (2..5x)")
    period, period2 = (number(n) for n in ("LASER_VOLLEY_PERIOD_TICKS", "LASER_VOLLEY_P2_PERIOD_TICKS"))
    if not (period is not None and period2 is not None and 100 <= period <= 240
            and 240 <= period2 <= 420 and 1.5 <= period2 / period <= 2.5):
        issues.append("[lance-periods] lance periods must be 100..240 then 240..420 ticks, 1.5..2.5x slower")
    warning, lock, bolt_warning = (number(n) for n in
                                 ("LASER_WARN_TICKS", "STORM_LOCK_TICKS", "STORM_WARN_TICKS"))
    if not (warning == 50 and lock is not None and 0 < lock < warning
            and bolt_warning is not None and warning < bolt_warning):
        issues.append("[lance-warning] the 50-tick lance fuse must include tracking and a positive lock, shorter than the bolt")
    first = re.search(r"intLASER_FIRST_TICKS=DROP_TICKS\+(\d+);", code)
    if not first or not 100 <= int(first[1]) <= 240:
        issues.append("[lance-first] LASER_FIRST_TICKS must be DROP_TICKS + 100..240 ticks")
    radius, ring = (number(n) for n in ("LASER_RADIUS", "LASER_VOLLEY_RING"))
    if not (radius is not None and ring is not None and 2 <= radius <= 4 and 0 < ring < radius):
        issues.append("[lance-radius] the positive volley ring must fit inside the 2..4 block beam radius")


def validate_lance_source(source, issues):
    code = java_compact(source)
    tick = java_method(code, "tick")
    playing = java_block(tick, "if(state==ShowConstants.STATE_PLAYING)")
    schedule = java_method(code, "scheduleLances")
    strikes_tick = java_method(code, "tickStrikes")
    strike_class = java_block(code, "privatestaticfinalclassStrike")
    constructor = java_method(strike_class, "Strike")

    def require(ok, rule, message):
        if not ok:
            issues.append("[%s] %s" % (rule, message))

    require("scheduleStorms(tickPos);scheduleLances(tickPos);tickStrikes();" in playing
            and tick.count("scheduleLances(") == 1
            and "scheduleLances(" not in java_method(code, "scheduleStorms"),
            "lance-scheduler", "tick must run a separate lance scheduler alongside storms before ticking strikes")
    waves = java_block(code, "privatestaticfinalbyte[]WAVE_KINDS=")
    require(bool(waves) and all(re.fullmatch(r"ShowConstants\.STRIKE_(BOLT|GRASP|SIPHON|BARRAGE|VORTEX|RUPTURE)", k)
                               for k in waves.rstrip(",").split(","))
            and all("ShowConstants.STRIKE_" + kind in waves.split(",")
                    for kind in ("VORTEX", "RUPTURE")),
            "lance-rotation", "WAVE_KINDS must include vortex/rupture and only ground attacks, never a laser")
    require("if(bossDefeated||tickPos<ShowConstants.LASER_FIRST_TICKS||tickPos<nextLanceTick){return;}" in schedule
            and "nextLanceTick=(int)tickPos+(bossPhase2?ShowConstants.LASER_VOLLEY_P2_PERIOD_TICKS:ShowConstants.LASER_VOLLEY_PERIOD_TICKS);" in schedule
            and "nextStormTick" not in schedule,
            "lance-clock", "scheduleLances must gate/rearm its own clock with the phase-specific period")
    require("intcount=bossPhase2?ShowConstants.LASER_VOLLEY_P2:ShowConstants.LASER_VOLLEY;" in schedule
            and "floatdamage=bossPhase2?ShowConstants.LASER_VOLLEY_P2_DAMAGE:ShowConstants.LASER_VOLLEY_DAMAGE;" in schedule,
            "lance-phase", "scheduleLances must select both count and per-beam damage for the phase")
    volley = java_block(schedule, "for(inti=0;i<count;i++)")
    require("Strikestrike=newStrike(++nextStrikeId,player,ShowConstants.STRIKE_LASER,ShowConstants.LASER_WARN_TICKS,ShowConstants.LASER_RADIUS,damage,0,true);" in volley
            and "intage;intstartTick;" in strike_class
            and not re.search(r"\b(?:age|startTick)(?:[+\-*/]?=|\+\+|--)", constructor + schedule)
            and "pendingStrikes" not in schedule,
            "lance-synchronous", "every volley member must be constructed immediately with one fuse and default age/start")
    ring = java_block(volley, "if(i>0)")
    require("doubleoffsetX;doubleoffsetZ;" in strike_class
            and not re.search(r"\boffset[XZ]=", constructor)
            and len(re.findall(r"\bstrike\.offset[XZ]=", schedule)) == 2
            and "doubleangle=base+Math.PI*2.0*(i-1)/(count-1);" in ring
            and "strike.offsetX=Math.cos(angle)*ShowConstants.LASER_VOLLEY_RING;" in ring
            and "strike.offsetZ=Math.sin(angle)*ShowConstants.LASER_VOLLEY_RING;" in ring,
            "lance-formation", "the default centre needs count-1 evenly spaced ring offsets")
    initial = ("strike.x=player.getX()+strike.offsetX;strike.y=player.getEyeY()-0.15;"
               "strike.z=player.getZ()+strike.offsetZ;strikes.put(strike.id,strike);"
               "sendStrike(strike,ShowStrikePayload.TRACKING,strike.warnTicks);")
    # Check order without depending on the geometry's contents, which has its own diagnostic.
    initial_at = volley.find(initial)
    ring_at = volley.find("if(i>0){")
    require(initial_at >= 0 and ring_at >= 0 and initial_at > ring_at + len("if(i>0){") + len(ring)
            and volley.count("sendStrike(") == 1,
            "lance-initial", "initial TRACKING must follow ring offsets, chest position and strike registration")
    tracking = java_block(strikes_tick, "if(tracking)")
    require("strike.x=target.getX()+strike.offsetX;" in tracking
            and "strike.z=target.getZ()+strike.offsetZ;" in tracking
            and "booleantracking=strike.tracks&&strike.age<strike.warnTicks-ShowConstants.STORM_LOCK_TICKS;" in strikes_tick,
            "lance-tracking", "tracking must retain both formation offsets until the shared lock")
    collect = java_block(strikes_tick, "while(it.hasNext())")
    require("List<Strike>landed=newArrayList<>();" in strikes_tick
            and "it.remove();landed.add(strike);" in java_block(collect, "if(left<=0)")
            and "strikeImpact(" not in collect and ".hurt(" not in collect,
            "lance-collection", "tickStrikes must remove/collect landed strikes without impacting inside the iterator")
    after_collect = strikes_tick.partition("while(it.hasNext()){" + collect + "}")[2]
    require("Map<ServerPlayer,Float>lanceDamage=newHashMap<>();for(Strikestrike:landed){strikeImpact(strike,lanceDamage);}lanceDamage.forEach((player,total)->{" in after_collect,
            "lance-aggregation-order", "one tick-local damage map must be applied only after all collected impacts")
    impact = java_method(code, "strikeImpact")
    laser = java_method(code, "laserImpact")
    require("strikeImpact(Strikestrike,Map<ServerPlayer,Float>lanceDamage){" in code
            and "laserImpact(Strikestrike,ServerLevellevel,Map<ServerPlayer,Float>lanceDamage){" in code
            and "caseShowConstants.STRIKE_LASER->laserImpact(strike,level,lanceDamage);" in impact,
            "lance-dispatch", "strikeImpact must forward the tick's damage map to laserImpact")
    require(java_block(laser, "for(ServerPlayerplayer:victims(strike,level))")
            == "lanceDamage.merge(player,strike.damage,Float::sum);" and ".hurt(" not in laser,
            "lance-merge", "laserImpact must sum every victim's beam damage, never hurt per beam")
    apply_damage = java_block(strikes_tick, "lanceDamage.forEach((player,total)->")
    require("player.hurt(player.serverLevel().damageSources().magic(),total)" in apply_damage
            and strikes_tick.count(".hurt(") == 1,
            "lance-hurt", "tickStrikes must hurt each map entry once using the combined total")
    require(not re.search(r"\binvulnerableTime=(?:\(int\))?0;", code),
            "lance-immunity", "never clear vanilla invulnerableTime to force volley hits")
    eligible = java_method(code, "strikeable")
    victims = java_method(code, "victims")
    require("(bossUuid==null||!player.getUUID().equals(bossUuid))" in eligible
            and "if(!strikeable(player)){continue;}" in schedule
            and "if(!strikeable(player)||" in victims
            and "if(strikeable(player)&&player.hurt(" in apply_damage,
            "lance-boss-exclusion", "marking, victims and combined damage must retain strikeable's boss exclusion")
    reset = "nextLanceTick=ShowConstants.LASER_FIRST_TICKS;"
    for rule, body in (("field", code.split("privatestaticfinalclassStrike", 1)[0]),
                       ("start", java_method(code, "start")),
                       ("reset", java_method(code, "resetAll")),
                       ("loop", java_block(java_block(playing, "if(samples>=ShowConstants.TOTAL_SAMPLES)"), "if(loopMode==1)"))):
        require(reset in body, "lance-reset-" + rule, "nextLanceTick must initialize/reset on " + rule)
    transition = java_method(code, "enterPhase2")
    require("intposition=(int)ShowConstants.samplesToTicks(samples);" in transition
            and "nextLanceTick=Math.max(ShowConstants.LASER_FIRST_TICKS,position+ShowConstants.LASER_VOLLEY_P2_PERIOD_TICKS);" in transition,
            "lance-rearm", "enterPhase2 must rearm lances from the sample clock with the longer period, never before LASER_FIRST_TICKS")


def validate_sigil_render(source, issues):
    code = java_compact(source)
    if 'SIGIL=ResourceLocation.fromNamespaceAndPath("deusexmachina","textures/show/strike_sigils.png");' not in code:
        issues.append("[sigil-resource] ShowStrikeRender must load textures/show/strike_sigils.png")
    if "intSIGIL_TEX=512;" not in code or "intSIGIL_CELLS=7;" not in code:
        issues.append("[sigil-grid] ShowStrikeRender must use seven 512-pixel cells")
    for name in ("sigil", "upright"):
        body = java_method(code, name)
        uvs = re.findall(r"vertex\([^;]+,([^,;]+),([^,;]+)\);", body)
        if (not re.search(name + r"\(PoseStackpose,VertexConsumervc,bytekind,", code)
                or "floatu0=kind/(float)SIGIL_CELLS;floatu1=(kind+1)/(float)SIGIL_CELLS;" not in body
                or uvs != [("u0", "1.0F"), ("u0", "0.0F"), ("u1", "0.0F"), ("u1", "1.0F")]):
            issues.append("[sigil-uv-%s] %s must accept kind and use its cell's UVs on all four vertices" % (name, name))
    for name, helper, owner in (("renderWorld", "sigil", "strike"),
                                ("renderWorld", "sigil", "impact"),
                                ("laserMark", "upright", "strike")):
        body = java_method(code, name)
        if name == "renderWorld":
            typ = "Strike" if owner == "strike" else "Impact"
            body = java_block(body, "for(ShowStrike.%s%s:ShowStrike.%ss())" % (typ, owner, owner))
        args = re.findall(helper + r"\(pose,vc,([^;]+)\);", body)
        if not args or any(not arg.startswith(owner + ".kind,") for arg in args):
            issues.append("[sigil-call-%s-%s] all %s %s calls must pass %s.kind"
                          % (name, owner, name, helper, owner))
    for name in ("reticle", "edgeMark"):
        blits = re.findall(r"g\.blit\(([^;]+)\);", java_method(code, name))
        if len(blits) != 1 or not blits[0].startswith("SIGIL,") or not blits[0].endswith(
                ",strike.kind*SIGIL_TEX,0,SIGIL_TEX,SIGIL_TEX,SIGIL_TEX*SIGIL_CELLS,SIGIL_TEX"):
            issues.append("[sigil-hud-%s] %s must blit the kind's cell using the full atlas width" % (name, name))


def validate_combo_constants(source, issues):
    """Wire identities and the new attacks' explicit tuning; no jar or global error state."""
    code = java_compact(source)
    for want, kind in enumerate(("BOLT", "GRASP", "SIPHON", "BARRAGE", "LASER", "VORTEX", "RUPTURE")):
        if "byteSTRIKE_%s=%d;" % (kind, want) not in code:
            issues.append("[kind-%s] STRIKE_%s must retain wire code %d" % (kind.lower(), kind, want))
    tuning = {"COMBO_DELAY_TICKS": "24", "VORTEX_WARN_TICKS": "60", "VORTEX_RADIUS": "6.0F",
              "VORTEX_DAMAGE": "6.0F", "RUPTURE_WARN_TICKS": "60", "RUPTURE_RADIUS": "3.5F",
              "RUPTURE_DAMAGE": "10.0F", "LASER_VOLLEY_P2_PERIOD_TICKS": "300"}
    for name, value in tuning.items():
        typ = "float" if value.endswith("F") else "int"
        if typ + name + "=" + value + ";" not in code:
            issues.append("[combo-tuning-%s] %s must be %s" % (name.lower(), name, value))


def validate_combo_source(source, client_source, issues):
    """Check actual scheduling/impact bodies, not similarly named code elsewhere."""
    code, client = java_compact(source), java_compact(client_source)

    def require(ok, rule, message):
        if not ok:
            issues.append("[%s] %s" % (rule, message))

    schedule = java_method(code, "scheduleStorms")
    require(java_method(code, "comboKind") ==
            "returnswitch(kind){caseShowConstants.STRIKE_BOLT,ShowConstants.STRIKE_RUPTURE->ShowConstants.STRIKE_SIPHON;"
            "caseShowConstants.STRIKE_GRASP,ShowConstants.STRIKE_BARRAGE->ShowConstants.STRIKE_RUPTURE;"
            "default->ShowConstants.STRIKE_BOLT;};",
            "combo-pairs", "comboKind must map bolt/rupture to siphon, grasp/barrage to rupture, others to bolt")
    require("stormWave++;bytekind=WAVE_KINDS[(stormWave-1)%WAVE_KINDS.length];"
            "bytefollowupKind=bossPhase2||stormWave>2?comboKind(kind):(byte)-1;" in schedule,
            "combo-gate", "only the first two phase-1 waves are solo; phase 2 combos start immediately")
    require("if(bossDefeated||tickPos<ShowConstants.STORM_FIRST_TICKS||tickPos<nextStormTick){return;}" in schedule
            and "if(strikeable(player)){marked.add(player);}" in schedule,
            "combo-targets", "storm scheduling must gate defeat/clock and mark only strikeable players")
    require('broadcast(newShowStormPayload(stormWave,marked.size(),bossVisible?bossTarget:"",kind,followupKind));' in schedule,
            "combo-metadata", "broadcast the scheduled primary/secondary kinds and player count, not strike count")
    marked = java_block(schedule, "for(ServerPlayerplayer:marked)")
    require("Strikestrike=newStrike(++nextStrikeId,player,kind,warnTicks(kind),radius(kind),damage(kind),debuffTicks(kind),true);"
            "strikes.put(strike.id,strike);sendStrike(strike,ShowStrikePayload.TRACKING,strike.warnTicks);" in marked,
            "combo-primary", "each marked player needs the primary's own tuning, unique id and immediate warning")
    followup = java_block(marked, "if(followupKind>=0)")
    require("Strikefollowup=newStrike(++nextStrikeId,player,followupKind,strike.warnTicks+ShowConstants.COMBO_DELAY_TICKS,"
            "radius(followupKind),damage(followupKind),debuffTicks(followupKind),true);" in followup,
            "combo-separation", "followup fuse must be primary.warnTicks + COMBO_DELAY_TICKS, not its own kind's fuse")
    require("strikes.put(followup.id,followup);sendStrike(followup,ShowStrikePayload.TRACKING,followup.warnTicks);" in followup
            and "pendingStrikes" not in schedule
            and not re.search(r"\b(?:age|startTick)(?:[+\-*/]?=|\+\+|--)", schedule),
            "combo-warning", "register and warn both strikes immediately, without hidden age/start or delayed queues")
    require("strike.warnTicks=Math.max(1,payload.ticksLeft());" in java_block(java_method(client, "handle"), "if(strike==null)"),
            "combo-client-fuse", "the client must take each new mark's actual extended fuse from the packet")
    storm = java_method(client, "handleStorm")
    for field, getter in (("Primary", "primary"), ("Secondary", "secondary")):
        require("wave%sKind=payload.%sKind();" % (field, getter) in storm,
                "combo-client-" + getter, "client storm metadata must consume explicit " + getter + "Kind")
    for method, field in (("waveKind", "wavePrimaryKind"), ("waveFollowupKind", "waveSecondaryKind")):
        require(java_method(client, method) == "return" + field + ";",
                "combo-client-" + method, "wave labels must use metadata, never infer kinds from lingering marks")
    require(all("wave%sKind=-1;" % field in java_method(client, "reset") for field in ("Primary", "Secondary")),
            "combo-client-reset", "reset must clear both wave-kind sentinels")
    for kind, method in (("VORTEX", "vortexImpact"), ("RUPTURE", "ruptureImpact")):
        for helper, suffix in (("warnTicks", "WARN_TICKS"), ("radius", "RADIUS"), ("damage", "DAMAGE")):
            require("caseShowConstants.STRIKE_%s->ShowConstants.%s_%s;" % (kind, kind, suffix)
                    in java_method(code, helper), "combo-%s-%s" % (kind.lower(), helper),
                    helper + " must use " + kind + " tuning")
        require("caseShowConstants.STRIKE_%s->ShowConstants.%s_RADIUS;" % (kind, kind)
                in java_method(client, "radiusFor"), "combo-%s-client-radius" % kind.lower(),
                "client radius must match " + kind + " hit geometry")
        require("caseShowConstants.STRIKE_%s->%s(strike,level,impactY);" % (kind, method)
                in java_method(code, "strikeImpact"), "combo-%s-dispatch" % kind.lower(),
                "strikeImpact must dispatch " + kind)
        body = java_method(code, method)
        victims = java_block(body, "for(ServerPlayerplayer:victims(strike,level))")
        require(bool(victims) and body.count("for(ServerPlayer") == 1,
                "combo-%s-victims" % kind.lower(), kind + " must act only on shared eligible victims")
        # Damage and sync are checked in the method separately so an absent victim loop gets one diagnostic.
        require("if(player.hurt(level.damageSources().magic(),strike.damage)){stormHitCount++;}" in body,
                "combo-%s-damage" % kind.lower(), kind + " must deal tuned magic damage and count successful hits")
        require("player.hurtMarked=true;" in body and body.find("player.hurtMarked=true;") > body.find("player.setDeltaMovement("),
                "combo-%s-sync" % kind.lower(), kind + " must mark changed velocity for client synchronization")
    vortex = java_method(code, "vortexImpact")
    require("doubledx=strike.x-player.getX();doubledz=strike.z-player.getZ();doubledistance=Math.sqrt(dx*dx+dz*dz);" in vortex
            and "if(distance>0.01){doublespeed=Math.min(1.1,distance*0.3);"
            "player.setDeltaMovement(dx/distance*speed,Math.max(0.18,player.getDeltaMovement().y),dz/distance*speed);" in vortex,
            "combo-vortex-pull", "vortex must pull inward with bounded speed, upward floor and a zero-distance guard")
    require("player.setDeltaMovement(player.getDeltaMovement().x,0.8,player.getDeltaMovement().z);"
            in java_method(code, "ruptureImpact"),
            "combo-rupture-launch", "rupture must launch upward while preserving horizontal motion")
    victims = java_method(code, "victims")
    require("if(!strikeable(player)||!player.level().dimension().equals(strike.dimension)){continue;}" in victims
            and "if(dx*dx+dz*dz<=strike.radius*strike.radius&&Math.abs(dy)<=4.0){hit.add(player);}" in victims,
            "combo-victim-geometry", "new attacks must retain same-dimension radius/height victim filtering")
    require(java_method(code, "strikeable") == "returnplayer.isAlive()&&!player.isSpectator()&&!player.isCreative()"
            "&&(bossUuid==null||!player.getUUID().equals(bossUuid));",
            "combo-eligibility", "all combo targets/victims must be living noncreative nonspectator nonboss players")
    # Grouped switch labels are legal Java; still require zero debuffs for the lance and new attacks.
    zero_cases = re.findall(r"case([^;{}]+)->0;", java_method(code, "debuffTicks"))
    zero_kinds = {label for case in zero_cases for label in case.split(",")}
    for kind in ("LASER", "VORTEX", "RUPTURE"):
        require("ShowConstants.STRIKE_" + kind in zero_kinds,
                "combo-%s-debuff" % kind.lower(), kind + " must not apply a debuff")


def validate_phase_source(source, commands, client_source, issues):
    code, command, client = map(java_compact, (source, commands, client_source))

    def require(ok, rule, message):
        if not ok:
            issues.append("[%s] %s" % (rule, message))

    registration = java_method(command, "register")
    require('.then(Commands.literal("reset").executes(ctx->ShowOrchestrator.commandReset()))' in registration,
            "reset-registration", "/deusex reset must remain registered even when it is not the terminal child")
    require('.then(Commands.literal("phase2").requires(source->source.hasPermission(2))'
            '.executes(ctx->ShowOrchestrator.commandPhase2(ctx.getSource())))' in registration,
            "phase-command", "/deusex phase2 must be an operator-only child invoking commandPhase2 with its source")
    forced = java_method(code, "commandPhase2")
    guards = (
        ("state", "current==null||current.state!=ShowConstants.STATE_PLAYING||!current.bossVisible||current.bossUuid==null||current.bossDefeated"),
        ("living", "player==null||!player.isAlive()"),
        ("repeat", "current.bossPhase2"),
    )
    activate = forced.find("current.enterPhase2(player);")
    for label, condition in guards:
        header = "if(" + condition + ")"
        body = java_block(forced, header)
        end = forced.find(header + "{" + body + "}") + len(header) + len(body) + 2
        require(bool(body) and "source.sendFailure(" in body and body.endswith("return0;")
                and activate >= end, "phase-guard-" + label,
                "commandPhase2 must reject " + label + " before any activation")
    require("ServerPlayerplayer=current.server.getPlayerList().getPlayer(current.bossUuid);" in forced
            and forced.find("ServerPlayerplayer=") < forced.find("if(player==null||!player.isAlive())"),
            "phase-online", "forced phase must resolve the online boss by UUID before its living guard")
    require("current.enterPhase2(player);current.applyBossBuffs();current.broadcast(current.bossPayload());source.sendSuccess(" in forced
            and forced.endswith("return1;"),
            "phase-activate", "successful forced phase must enter, refresh buffs, broadcast phase and report success")
    enter = java_method(code, "enterPhase2")
    require("bossPhase2=true;" in enter and "dropAmbient(player,MobEffects.DAMAGE_RESISTANCE);" in enter,
            "phase-enter", "enterPhase2 must latch the phase and remove the phase-1 ambient resistance")
    require("nextStormTick=Math.min(nextStormTick,Math.max(ShowConstants.STORM_FIRST_TICKS,position+ShowConstants.STORM_PHASE2_PERIOD_TICKS));" in enter,
            "phase-storm-rearm", "phase 2 must accelerate storms without postponing an earlier wave or bypassing the first tick")
    natural = java_block(java_method(code, "trackBossHealth"), "if(wasPhase2!=bossPhase2)")
    require(java_block(natural, "if(bossPhase2)") == "enterPhase2(player);",
            "phase-natural", "natural health transition must use the same enterPhase2 helper")
    # Ignore message literals: saying 'health unchanged' is not evidence of leaving health unchanged.
    effect_code = re.sub(r'"(?:\\.|[^"\\])*"', '""', forced + enter)
    require(not re.search(r"\b(?:bossHp|bossLiveHp|samples|state)(?:[+\-*/]?=(?!=)|\+\+|--)|"
                          r"(?:\+\+|--)\s*(?:current\.)?(?:bossHp|bossLiveHp|samples|state)\b|"
                          r"\b(?:setHealth|heal|hurt|setBaseValue|reanchor|start|startWithBoss|resetAll|halt|stop|pause|resume)\(", effect_code),
            "phase-no-hp-clock", "forced phase/entry must not alter HP, samples, playback state or restart the show")
    require(java_method(code, "bossPayload") == "returnnewShowBossPayload(bossVisible,bossTarget,bossLiveHp,bossPhase2);",
            "phase-boss-packet", "bossPayload must transmit the explicit server phase with live HP")
    for method in ("halt", "beginClosing"):
        require('broadcast(newShowBossPayload(false,"",0,false));' in java_method(code, method),
                "phase-hide-" + method, "hidden boss packets must explicitly clear phase on " + method)
    handle = java_method(client, "handle")
    require("booleannextPhase2=hp>0&&payload.phase2();" in handle and "phase2=nextPhase2;" in handle
            and "BOSS_PHASE2_HP" not in client and not re.search(r"hp<=50|next<=50", client),
            "phase-client-explicit", "client phase must follow payload.phase2, not infer it from HP")
    require(java_block(handle, "if(nextPhase2&&!phase2)") == "phase2Ms=now;"
            and "elseif(!nextPhase2){phase2Ms=-1L;}" in handle,
            "phase-client-transition", "client must timestamp phase entry once and clear the timestamp when phase ends")


def validate_combo_network(storm_source, boss_source, network_source, issues):
    storm, boss, network = map(java_compact, (storm_source, boss_source, network_source))
    contracts = (
        ("storm", storm, "ShowStormPayload", "intwave,inttargets,Stringboss,byteprimaryKind,bytesecondaryKind",
         "ByteBufCodecs.VAR_INT,ShowStormPayload::wave,ByteBufCodecs.VAR_INT,ShowStormPayload::targets,"
         "ByteBufCodecs.STRING_UTF8,ShowStormPayload::boss,ByteBufCodecs.BYTE,ShowStormPayload::primaryKind,"
         "ByteBufCodecs.BYTE,ShowStormPayload::secondaryKind,ShowStormPayload::new"),
        ("boss", boss, "ShowBossPayload", "booleanvisible,Stringtarget,inthp,booleanphase2",
         "ByteBufCodecs.BOOL,ShowBossPayload::visible,ByteBufCodecs.STRING_UTF8,ShowBossPayload::target,"
         "ByteBufCodecs.VAR_INT,ShowBossPayload::hp,ByteBufCodecs.BOOL,ShowBossPayload::phase2,ShowBossPayload::new"),
    )
    for label, code, name, fields, codec in contracts:
        if "publicrecord" + name + "(" + fields + ")implementsCustomPacketPayload{" not in code:
            issues.append("[combo-%s-record] %s must declare the explicit metadata fields in wire order" % (label, name))
        if "CODEC=StreamCodec.composite(" + codec + ");" not in code:
            issues.append("[combo-%s-codec] %s codec must encode every field with its matching type and order" % (label, name))
    registration = java_method(network, "register")
    if 'PayloadRegistrarregistrar=event.registrar("2").optional();' not in registration:
        issues.append('[combo-protocol] changed payload layouts require optional protocol registrar "2"')
    for name, handler in (("ShowStormPayload", "ShowStrike.handleStorm"), ("ShowBossPayload", "ShowBoss.handle")):
        if "registrar.playToClient(%s.TYPE,%s.CODEC,(payload,context)->net.deusexmachina.client.%s(payload));" % (name, name, handler) not in registration:
            issues.append("[combo-network-%s] client registration must deliver %s to %s" % (name, name, handler))


def validate_soft_visuals(showr_source, strike_source, glow_source, mod_source, issues):
    """The playtest readability contract: warnings hint, impacts shout, players glow.

    Every overlay that used to cover the view is bounded here, so a future polish pass cannot
    quietly re-blind the player, and the glow that replaces the red wash stays additive.
    """
    code = java_compact(strike_source)
    glow = java_compact(glow_source)

    def require(ok, rule, message):
        if not ok:
            issues.append("[%s] %s" % (rule, message))

    mveil = re.search(r"int alpha = Math\.round\(ShowHudData\.WASH_ALPHA\[level\] \* ([\d.]+)F\);",
                      showr_source)
    require(mveil is not None and 0.0 < float(mveil[1]) <= 0.5,
            "veil-soft", "the red veil must scale the baked wash table by at most 0.5: atmosphere, not a blindfold")
    mpeak = re.search(r"int peak = Math\.round\(([\d.]+)F \+ ([\d.]+)F \* pulse\);", showr_source)
    peak_top = (float(mpeak[1]) + float(mpeak[2])) if mpeak else None
    require(peak_top is not None and peak_top <= 24.0,
            "corner-peak", "the corner flash must keep a bounded peak of at most 24 alpha: a hint, not a flashbang")

    mdim = re.search(r"floatWARN_DIM=([\d.]+)F;", code)
    require(mdim is not None and 0.0 < float(mdim[1]) <= 0.6,
            "warn-dim", "warning layers need a WARN_DIM of at most 0.6 so the world stays readable behind them")
    require(all(branch in code for branch in (
            "floatalpha=((locked?0.7F:0.4F)+0.2F*pulse)*WARN_DIM;",
            "floatalpha=((locked?0.65F:0.4F)+0.25F*pulse)*WARN_DIM;",
            "floatalpha=(0.55F+0.45F*pulse)*WARN_DIM;",
            "floatalpha=(0.30F+0.22F*pulse)*WARN_DIM;")),
            "warn-sigils", "every warning sigil branch (vortex, rupture, locked, tracking) must draw through WARN_DIM")
    require("floatalpha=(locked?0.62F+0.38F*pulse:0.34F+0.24F*pulse)*WARN_DIM;" in code,
            "warn-lance", "the lance's floating mark must draw through WARN_DIM like the ground sigils")
    require(all(part in code for part in (
            "(locked?0.72F:0.32F)*(0.6F+0.4F*pulse)*WARN_DIM",
            "(locked?0.5F:0.26F)*pulse*WARN_DIM",
            "(0.28F+0.34F*pulse)*WARN_DIM",
            "0.6F*WARN_DIM",
            "0.15F*WARN_DIM",
            "floatalpha=(0.35F+urgency*0.4F)*pulse*WARN_DIM;",
            "floatalpha=(locked?0.50F:0.16F+0.30F*urgency)*(0.7F+0.3F*pulse)*WARN_DIM;")),
            "warn-ground", "the seal rings, arcs, spikes and guide beam must all draw through WARN_DIM")
    require("tint[0],tint[1]*0.7F+0.2F,tint[2]*0.7F+0.1F,life*0.55F);" in code
            and "life*life*0.45F);" in code,
            "impact-bright", "impacts keep full brightness: the moment something lands is allowed to shout")

    medge = re.search(r"edge = ([\d.]+)F \+ ([\d.]+)F \* pulse;", strike_source)
    require(medge is not None and float(medge[1]) + float(medge[2]) <= 0.30,
            "edge-soft", "the endangered edge must stay at or under 0.30 strength: a hint, not a blindfold")
    mhit = re.search(r"Math\.max\(edge, ([\d.]+)F \* \(1\.0F - hitAge", strike_source)
    require(mhit is not None and float(mhit[1]) <= 0.5,
            "hit-edge", "the hit reaction edge must stay at or under 0.5 strength")
    mflash = re.search(r"int a = Math\.round\((\d+) \* \(1\.0F - hitAge", strike_source)
    require(mflash is not None and int(mflash[1]) <= 80,
            "hit-flash", "the full-screen hit flash must peak at or under 80 alpha")
    mdepth = re.search(r"int depth = Math\.round\(h \* ([\d.]+)F\);", strike_source)
    mcoef = re.search(r"int a = Math\.round\(([\d.]+)F \* strength \* t \* t \* t\);", strike_source)
    require(mdepth is not None and float(mdepth[1]) <= 0.12
            and mcoef is not None and float(mcoef[1]) <= 80.0,
            "vignette-soft", "the vignette must stay shallow (at most 0.12 of the height) and faint (at most 80 alpha)")

    msize = re.search(r"int size = (\d+) \+ Math\.round\(([\d.]+)F \* urgency\);", strike_source)
    malpha = re.search(r"float alpha = locked \? ([\d.]+)F : ([\d.]+)F \+ ([\d.]+)F \* pulse;",
                       strike_source)
    require(msize is not None and int(msize[1]) <= 24 and float(msize[2]) <= 10.0
            and malpha is not None and float(malpha[1]) <= 0.65 and float(malpha[2]) <= 0.45,
            "reticle-soft", "the HUD reticle must stay small (at most 24+10 px) and translucent (at most 0.65 locked)")
    require("int seconds = Math.max(0, Math.round(strike.ticksLeft / 20.0F));" in strike_source
            and "g.fill(px - 1, py - 1, px + 1, py + 1, pc);" in strike_source,
            "reticle-pips", "the reticle needs countdown pips so the fuse reads at a glance")
    mfuse = re.search(r"g\.fill\(fx, fy, fx \+ fw, fy \+ 3, 0x([0-9A-Fa-f]{8})\);", strike_source)
    require(mfuse is not None and (int(mfuse[1], 16) >> 24) <= 0x70,
            "fuse-soft", "the fuse bar backdrop must stay at or under 0x70 alpha")
    edge = java_method(code, "edgeMark")
    mesize = re.search(r"intsize=(\d+);", edge)
    metint = re.search(r"tint\(g,tint\[0\],tint\[1\],tint\[2\],([\d.]+)F\);", edge)
    require(mesize is not None and int(mesize[1]) <= 20
            and metint is not None and float(metint[1]) <= 0.6,
            "edgemark-soft", "off-screen edge marks must stay small (at most 20 px) and faint (at most 0.6)")
    mpanel = re.search(r"g\.fill\(-width / 2, -5, \(width \+ 1\) / 2, 25, "
                       r"\(Math\.round\(alpha \* ([\d.]+)F\) << 24\)\);", strike_source)
    require(mpanel is not None and float(mpanel[1]) <= 0.35,
            "banner-soft", "the wave banner panel must stay at or under 0.35 alpha")
    require("float[] accent = lockColor((byte) ShowStrike.waveKind());" in strike_source
            and "g.fill(-sw / 2, 22, sw / 2, 23, accentColor);" in strike_source
            and "float sweep = (now % 1800L) / 1800.0F;" in strike_source
            and "g.fill(px, -5, px + 1, 25, (ga << 24) | 0xFFF3E0);" in strike_source,
            "banner-alive", "the banner needs the attack-colour accent rule and a glint sweep")

    require("NeoForge.EVENT_BUS.addListener(ShowGlow::renderWorld);" in mod_source,
            "glow-registered", "ShowGlow must be registered on the NeoForge event bus or players never glow")
    require("if(event.getStage()!=RenderLevelStageEvent.Stage.AFTER_PARTICLES){return;}" in glow
            and "if(state!=ShowConstants.STATE_PLAYING&&state!=ShowConstants.STATE_PAUSED){return;}" in glow,
            "glow-gate", "the glow must draw only at AFTER_PARTICLES while the show is playing or paused")
    require("buffers.getBuffer(RenderType.lightning())" in glow
            and "buffers.endBatch(RenderType.lightning())" in glow,
            "glow-additive", "the glow must ride the additive lightning type: a solid panel would block the view again")
    require('StringbossName=ShowBoss.visible()?ShowBoss.target():"";' in glow
            and "player.getName().getString().equals(bossName)" in glow
            and "color=newfloat[]{1.0F,0.12F,0.10F};" in glow,
            "glow-boss", "the boss must be identified by name and burn crimson so the bearer is findable")
    require("color=mark.locked()?ShowStrikeRender.lockColor(mark.kind):ShowStrikeRender.trackColor(mark.kind);" in glow
            and "dx*dx+dz*dz<=reach*reach" in glow,
            "glow-marked", "a marked player must glow in the incoming attack's colour, matched by the mark's radius")
    require("doubleRANGE=40.0;" in glow and "doubleFADE_START=24.0;" in glow
            and "if(dist>RANGE){continue;}" in glow,
            "glow-fade", "the glow must fade out between 24 and 40 blocks instead of lighting the whole map")
    require("if(player==mc.player&&mc.options.getCameraType().isFirstPerson()){continue;}" in glow,
            "glow-firstperson", "the local first-person body must be skipped: an aura on the camera fills the screen")
    require("floatcycle=(now%1600L)/1600.0F;" in glow
            and "floatshine=Mth.sin(cycle*(float)Math.PI);" in glow
            and "(cycle*2.0F-1.0F)*0.45F" in glow,
            "glint-sweep", "each body needs a glint band sweeping across on a 1.6 s clock")


validate_lance_constants(const, errors)
validate_lance_source(orch, errors)
validate_sigil_render(srender, errors)
validate_combo_constants(const, errors)
if not re.search(r"strike\.kind\s*==\s*ShowConstants\.STRIKE_LASER\s*\?\s*target\.getEyeY\(\)",
                 orch):
    errors.append("the seal lance does not track the target's chest: it would mark the ground")
if not re.search(r"strike\.kind\s*!=\s*ShowConstants\.STRIKE_LASER", orch):
    errors.append("the seal lance still snaps to the ground at the lock")
# Zero-debuff switch labels (including a grouped LASER/VORTEX/RUPTURE case) are checked below.
# Client decode: retain all six kind bits, including the new kinds.
strike_java = open(os.path.join(JAVA, "client", "ShowStrike.java"), encoding="utf-8").read()
validate_combo_source(orch, strike_java, errors)
if not re.search(r"\(packed >> 2\) & 0x3F", strike_java):
    errors.append("ShowStrike masks the kind with fewer than six bits: the lance decodes as a bolt")
if not re.search(r"private static void renderFx\(", srender):
    errors.append("ShowStrikeRender has no fx pass: the laser would be invisible")
for meth in ("warningBeam", "impactBeam", "groundGlow", "shockwave", "ring", "arc", "pillar"):
    if not re.search(r"private static void %s\(" % meth, srender):
        errors.append("ShowStrikeRender has no %s: the attack dressing is incomplete" % meth)
# A coarse bolt (few segments, no taper, one colour) was the 1.1.0 look; the release needs the
# layered discharge: at least 14 segments and a width that thins toward the sky.
mseg = re.search(r"float height = 76\.0F;\s*int segments = (\d+);", srender)
if not mseg or int(mseg.group(1)) < 14:
    errors.append("the bolt trunk is %s segments, not the layered 14+ discharge"
                  % (mseg.group(1) if mseg else "absent"))
if not re.search(r"float taper = 1\.0F - 0\.45F \* i / \(float\) segments;", srender):
    errors.append("the bolt trunk has no taper: it would draw as a uniform stripe")
if not re.search(r"quad\(m, vc, ax, 0\.0F, az.*?\n\s*quad\(m, vc, dx, 0\.0F, dz", srender):
    errors.append("band() emits one winding only: the lightning type culls the far face of the "
                  "ground rings")

# ---------- the corner flash follows the drums the player actually hears ----------
# Not a guessed tempo: the jar ships a one-byte-per-tick kick envelope of the exact track, the
# client reads it at the sample being heard (so a seek moves the flash too), and the peak stays a
# hint of red rather than a flashbang.
beat_rel = "assets/deusexmachina/show/beat.bin"
srate = cint("SAMPLE_RATE")
beat_ticks = (TOTAL_SAMPLES // (srate // 20)) if TOTAL_SAMPLES and srate else None
if beat_rel not in names:
    errors.append("the drum envelope %s is missing: the corner flash would have no beat" % beat_rel)
else:
    data = z.read(beat_rel)
    if beat_ticks is not None and len(data) != beat_ticks:
        errors.append("beat.bin is %d ticks but the track is %d: the flash would drift off the song"
                      % (len(data), beat_ticks))
    else:
        peak = int(np.max(np.frombuffer(data, dtype=np.uint8)))
        if peak < 200:
            errors.append("beat.bin never rises past %d/255: the flash would never reach a hit"
                          % peak)
        else:
            if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            try:
                import make_beat
                level, ntick = make_beat.envelope()
                baked = np.round(level * 255.0)
                if ntick != len(data):
                    errors.append("the track bakes to %d envelope ticks but beat.bin holds %d"
                                  % (ntick, len(data)))
                else:
                    off = float(np.abs(np.frombuffer(data, dtype=np.uint8).astype(np.float32)
                                       - baked.astype(np.float32)).mean())
                    if off > 1.5:
                        errors.append("beat.bin is not the drum envelope of the shipped track: "
                                      "%.1f levels off on average, so the flash would not land on "
                                      "the kicks" % off)
            except Exception as exc:
                errors.append("the beat envelope could not be recomputed from the track: %s" % exc)
sdrum = open(os.path.join(JAVA, "client", "ShowDrum.java"), encoding="utf-8").read()
if not re.search(r'fromNamespaceAndPath\("deusexmachina",\s*"show/beat\.bin"\)', sdrum):
    errors.append("ShowDrum does not read show/beat.bin")
if "ShowClient.position()" not in sdrum or "SAMPLES_PER_TICK" not in sdrum:
    errors.append("ShowDrum is not tied to the heard sample: the flash would slide off the audio")
if not re.search(r"smooth \+= \(target - smooth\) \*", sdrum) or "Mth.clamp" not in sdrum:
    errors.append("ShowDrum does not ease its level into 0..1: the corners would strobe")
showr = open(os.path.join(JAVA, "client", "ShowRender.java"), encoding="utf-8").read()
if "ShowDrum.pulse(" not in showr:
    errors.append("ShowRender never asks ShowDrum for the beat: the corners would never flash")
if not re.search(r"phase == ShowTimeline\.PH_SONG\s*\|\|\s*phase == ShowTimeline\.PH_BURST\)"
                 r"\s*\{\s*drumCorners\(g, delta\);", showr):
    errors.append("the corner flash is not painted by the song-phase HUD")
mfade = re.search(r"for \(int k = steps; k >= 1; k--\)", showr)
if not mfade:
    errors.append("the corner flash is not a stack of fading steps: it would paint four hard blocks")
for corner in ("g.fill(0, 0, size, size, color)", "g.fill(w - size, 0, w, size, color)",
               "g.fill(0, h - size, size, h, color)", "g.fill(w - size, h - size, w, h, color)"):
    if corner not in showr:
        errors.append("the corner flash skips a corner (%s)" % corner)
# The peak bound itself lives in validate_soft_visuals (corner-peak), with the rest of the
# readability contract the playtest asked for.
mtint = re.search(r"\(band << 24\) \| 0x([0-9A-Fa-f]{6})", showr)
if not mtint:
    errors.append("the corner flash has no fixed red tint")
else:
    tint = int(mtint.group(1), 16)
    tr, tg, tb = (tint >> 16) & 0xFF, (tint >> 8) & 0xFF, tint & 0xFF
    if tr < 0x90 or tr < tg + 0x50 or tr < tb + 0x50:
        errors.append("the corner flash tint 0x%s is not a deep red" % mtint.group(1))
glow_java = open(os.path.join(JAVA, "client", "ShowGlow.java"), encoding="utf-8").read()
mod_java = open(os.path.join(JAVA, "client", "DeusExMachinaMod.java"), encoding="utf-8").read()
validate_soft_visuals(showr, srender, glow_java, mod_java, errors)

# The blessing keeps everyone who is not the boss standing for the whole event.
if not re.search(r"private void blessUnmarked\(\)", orch):
    errors.append("ShowOrchestrator has no blessUnmarked: non-boss players get no buff")
for eff in ("MobEffects.DAMAGE_RESISTANCE", "MobEffects.REGENERATION"):
    if not re.search(r"buff\(player,\s*%s" % re.escape(eff), orch):
        errors.append("the blessing never grants %s" % eff)
if not re.search(r"private void clearBlessing\(\)", orch):
    errors.append("the blessing is never cleared: it would outlive the event")
# The reset path has to clear the show and be reachable from the command tree.
if not re.search(r"public static int commandReset\(\)", orch):
    errors.append("ShowOrchestrator has no commandReset")
if not re.search(r"private void resetAll\(\)", orch):
    errors.append("ShowOrchestrator has no resetAll")
cmds = open(os.path.join(JAVA, "server", "ShowCommands.java"), encoding="utf-8").read()
boss_java = open(os.path.join(JAVA, "client", "ShowBoss.java"), encoding="utf-8").read()
storm_payload = open(os.path.join(JAVA, "net", "ShowStormPayload.java"), encoding="utf-8").read()
boss_payload = open(os.path.join(JAVA, "net", "ShowBossPayload.java"), encoding="utf-8").read()
network_java = open(os.path.join(JAVA, "net", "ShowNetwork.java"), encoding="utf-8").read()
validate_phase_source(orch, cmds, boss_java, errors)
validate_combo_network(storm_payload, boss_payload, network_java, errors)

# ---------- manifest, mixins, version agreement ----------
toml = read("META-INF/neoforge.mods.toml")
mver = re.search(r'^version="(\d+\.\d+\.\d+)"', toml, re.M)
vtoml = mver.group(1) if mver else None
if not vtoml:
    errors.append("manifest has no parseable version")
mloader = re.search(r'^modLoader="(\w+)"', toml, re.M)
if not mloader or mloader.group(1) != "javafml":
    errors.append("modLoader is %s; the mod has classes, so it must be javafml"
                  % (mloader.group(1) if mloader else "absent"))
mrange = re.search(r'^loaderVersion="([^"]+)"', toml, re.M)
if not mrange or mrange.group(1) != "[1,)":
    errors.append('loaderVersion is %s; the javafml provider reports 4.0.45, so only "[1,)" loads'
                  % (mrange.group(1) if mrange else "absent"))
if 'config="deusexmachina.mixins.json"' not in toml:
    errors.append("manifest does not register deusexmachina.mixins.json")
mix = json.loads(read("deusexmachina.mixins.json"))
for cls in ("ChannelMixin", "SkyMixin", "RainMixin"):
    if cls not in mix.get("client", []):
        errors.append("mixin config client list missing %s" % cls)
    if "net/deusexmachina/mixin/%s.class" % cls not in names:
        errors.append("mixin class %s not in the jar" % cls)
rdtxt = read("README.txt")
mread = re.search(r"^Version (\d+\.\d+\.\d+)$", rdtxt, re.M)
if not mread or mread.group(1) != vtoml:
    errors.append("README version %s != manifest %s" % (mread.group(1) if mread else "absent", vtoml))
heads = re.findall(r"^WHAT CHANGED IN (\d+\.\d+\.\d+)$", rdtxt, re.M)
if not heads or heads[0] != vtoml:
    errors.append("newest changelog header %s != manifest %s" % (heads[0] if heads else "absent", vtoml))
nums = [tuple(int(x) for x in h.split(".")) for h in heads]
if nums != sorted(nums, reverse=True):
    errors.append("changelog not descending: %s" % heads)
jarline = open(os.path.join(ROOT, "build_jar.py"), encoding="utf-8").read()
mjar = re.search(r"DeusExMachina-NeoForge-1\.21\.1-(\d+\.\d+\.\d+)\.jar", jarline)
if not mjar or mjar.group(1) != vtoml:
    errors.append("build_jar.py name version %s != manifest %s"
                  % (mjar.group(1) if mjar else "absent", vtoml))
selftxt = read("data/deusex/function/selftest.mcfunction")
mst = re.search(r'\{"text":"(\d+\.\d+\.\d+)","color":"red"', selftxt)
if not mst or mst.group(1) != vtoml:
    errors.append("selftest build id %s != manifest %s" % (mst.group(1) if mst else "absent", vtoml))
gradle = open(os.path.join(CLIENT, "gradle.properties"), encoding="utf-8").read()
mg = re.search(r"^mod_version=(\d+\.\d+\.\d+)", gradle, re.M)
if not mg or mg.group(1) != vtoml:
    errors.append("gradle mod_version %s != manifest %s" % (mg.group(1) if mg else "absent", vtoml))
cmanifest = open(os.path.join(RES, "META-INF", "neoforge.mods.toml"), encoding="utf-8").read()
mc = re.search(r'^version="(\d+\.\d+\.\d+)"', cmanifest, re.M)
if not mc or mc.group(1) != vtoml:
    errors.append("client source manifest %s != merged manifest %s"
                  % (mc.group(1) if mc else "absent", vtoml))

# ---------- compiled classes ----------
classes = {n for n in names if n.endswith(".class")}
dev = sorted(n for n in classes if "DevProbe" in n)
if dev:
    errors.append("development probe shipped: %s" % ", ".join(dev))
WANTED = {
    "net/deusexmachina/client/DeusExMachinaMod.class",
    "net/deusexmachina/client/MusicVolume.class",
    "net/deusexmachina/client/ShowClient.class",
    "net/deusexmachina/client/ShowTimeline.class",
    "net/deusexmachina/client/ShowRender.class",
    "net/deusexmachina/client/ShowStrike.class",
    "net/deusexmachina/client/ShowStrikeRender.class",
    "net/deusexmachina/client/ShowSound.class",
    "net/deusexmachina/client/VorbisStream.class",
    "net/deusexmachina/server/ShowOrchestrator.class",
    "net/deusexmachina/net/ShowNetwork.class",
    "net/deusexmachina/net/ShowStrikePayload.class",
    "net/deusexmachina/net/ShowStormPayload.class",
    "net/deusexmachina/ShowConstants.class",
}
missing = sorted(WANTED - classes)
if missing:
    errors.append("classes missing from the jar: %s" % ", ".join(missing))
mcs = os.path.join(ROOT, "mcsrc")
for n in sorted(classes):
    blob = z.read(n)
    if blob[:4] != b"\xca\xfe\xba\xbe":
        errors.append("%s is not a class file" % n)
        continue
    major = int.from_bytes(blob[6:8], "big")
    if major > 65:
        errors.append("%s is Java %d bytecode; the game runs Java 21 (65)" % (n, major - 44))
    if os.path.isdir(mcs):
        for owner in sorted({m.group(0).split(b"$")[0].decode() for m in
                             re.finditer(rb"net/minecraft/[A-Za-z0-9/_$]+", blob)}):
            if not os.path.isfile(os.path.join(mcs, owner + ".java")):
                errors.append("%s references %s, not a 1.21.1 class" % (n, owner.replace("/", ".")))

# ---------- size ----------
mb = os.path.getsize(JAR) / 1048576.0
print("jar %.2f MB, %d entries (%d classes)" % (mb, len(names), len(classes)))
if mb >= 30.0:
    errors.append("jar is %.2f MB, over the 30 MB ceiling" % mb)

print("\nERRORS:", len(errors))
for e in errors:
    print("  -", e)
print("WARNINGS:", len(warns))
for w in warns:
    print("  -", w)
sys.exit(1 if errors else 0)