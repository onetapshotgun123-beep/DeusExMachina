"""End-to-end 1.1.0 proof: NeoForge dev server soak + real-client show probe.

Server phase (RCON, no client): the orchestrator must poll the shim's #cmd, mirror #state/#pos,
start the clock at sample 0, force rain at RAIN_TICKS, hold the clock through pause, and restore
the weather and idle on stop.
Rain is ordered on the drop tick (RAIN_TICKS == DROP_TICKS, 219 ticks in), so nothing may be
falling during the build-up. The weather flag flips at RAIN_TICKS, but vanilla's rainLevel ramps
+0.01/tick and Level.isRaining() only turns true above 0.2, i.e. ~21 ticks later.

Client phase (gradle runClient -PdeusexProbe=show): DevProbe joins, screenshots vanilla rain,
runs /function deusex:start and watches the build-up, the heart scene and the drop, screenshots
drop/lyric, forces a downpour for the red tint comparison, pauses/resumes, kicks and rejoins
mid-show, restarts via /deusex start to capture the RONOVA boss bar and its buff tiers, waits for
the 7:00 lyric band, then stops the show and waits for idle. Afterwards this script parses the
client log for the DEUSPROBE invariants and measures the screenshots with Pillow.

Everything this script writes is dev scaffolding: the datapack mirror lives in client/run and the
shim data is byte-identical to the jar's.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid

from PIL import Image

from rcon import Rcon, raining, score

ROOT = os.path.dirname(os.path.abspath(__file__))
CLIENT = os.path.join(ROOT, "client")
RUN = os.path.join(CLIENT, "run")
WORLD = os.path.join(RUN, "world")
PACK = os.path.join(WORLD, "datapacks", "deusex")
SHOTS = os.path.join(RUN, "screenshots")
SERVER_LOG = os.path.join(CLIENT, "probe-server.log")
CLIENT_LOG = os.path.join(CLIENT, "probe-client.log")

failures = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ((" - " + str(detail)) if detail else ""), flush=True)
    if not ok:
        failures.append(name)


def offline_uuid(name):
    digest = bytearray(hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest())
    digest[6] = (digest[6] & 0x0F) | 0x30
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest)))


def prepare():
    if os.path.isdir(PACK):
        shutil.rmtree(PACK)
    os.makedirs(PACK)
    shutil.copytree(os.path.join(ROOT, "extracted", "data"), os.path.join(PACK, "data"))
    shutil.copy(os.path.join(ROOT, "extracted", "pack.png"), os.path.join(PACK, "pack.png"))
    with open(os.path.join(PACK, "pack.mcmeta"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"pack": {"pack_format": 48, "description": "deusex 1.1.0 probe"}}, f, indent=2)

    # A muted master volume makes SoundEngine.play skip the song outright (gain <= 0), so the
    # heard-position clock never advances. The probe needs real audio regardless of user settings.
    options = os.path.join(RUN, "options.txt")
    if os.path.exists(options):
        with open(options, encoding="utf-8") as f:
            lines = f.read().splitlines()
        out = []
        for line in lines:
            if line.startswith("soundCategory_master:"):
                out.append("soundCategory_master:1.0")
            elif line.startswith("soundCategory_record:"):
                out.append("soundCategory_record:1.0")
            else:
                out.append(line)
        with open(options, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(out) + "\n")

    ops = [{"uuid": offline_uuid("Dev"), "name": "Dev", "level": 4, "bypassesPlayerLimit": True}]
    with open(os.path.join(RUN, "ops.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(ops, f, indent=2)

    props = os.path.join(RUN, "server.properties")
    want = {
        "enable-rcon": "true",
        "rcon.password": "deusprobe",
        "rcon.port": "25575",
        "server-port": "25599",
        "online-mode": "false",
        "broadcast-rcon-to-ops": "true",
    }
    lines = []
    if os.path.exists(props):
        with open(props, encoding="utf-8") as f:
            lines = f.read().splitlines()
    out, seen = [], set()
    for line in lines:
        key = line.split("=", 1)[0]
        if key in want:
            out.append(key + "=" + want[key])
            seen.add(key)
        else:
            out.append(line)
    for key, value in want.items():
        if key not in seen:
            out.append(key + "=" + value)
    with open(props, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    print("prepared datapack, ops and server.properties", flush=True)


def gradle(args, log_path):
    log = open(log_path, "wb")
    return subprocess.Popen(["cmd", "/c", "gradlew.bat"] + args + ["--console=plain"],
                            cwd=CLIENT, stdout=log, stderr=subprocess.STDOUT), log


def wait_rcon(deadline):
    while time.time() < deadline:
        try:
            client = Rcon()
            print("rcon up", flush=True)
            return client
        except OSError:
            time.sleep(2)
    raise RuntimeError("rcon did not come up")


def wait_raining(rcon, want, deadline):
    value = raining(rcon)
    while time.time() < deadline and value != want:
        time.sleep(0.25)
        value = raining(rcon)
    return value


def server_phase(rcon):
    print("== server phase", flush=True)
    rcon.command("weather clear")
    check("clear weather settles", wait_raining(rcon, False, time.time() + 8) is False)
    check("load defaults", score(rcon, "#state") == 0 and score(rcon, "#cmd") == 0
          and score(rcon, "#loop") == 0 and score(rcon, "#pos") == 0,
          (score(rcon, "#state"), score(rcon, "#cmd"), score(rcon, "#loop"), score(rcon, "#pos")))

    rcon.command("function deusex:start")
    time.sleep(2.0)
    state = score(rcon, "#state")
    pos_a = score(rcon, "#pos")
    check("start -> state 1 and clock running", state == 1 and pos_a is not None and pos_a > 10,
          (state, pos_a))
    # ACT_START carries sample 0: two seconds in the clock must sit inside the quiet build-up,
    # nowhere near the drop tick (219).
    check("start begins with the build-up",
          pos_a is not None and 10 <= pos_a <= 90, pos_a)

    # Rain is ordered on the drop tick ~11 s in, so the sky must still be clear now.
    check("no rain before the drop", raining(rcon) is False, score(rcon, "#pos"))

    check("rain forced at the drop", wait_raining(rcon, True, time.time() + 20) is True,
          score(rcon, "#pos"))

    rcon.command("function deusex:pause")
    time.sleep(0.5)
    p1 = score(rcon, "#pos")
    time.sleep(1.0)
    p2 = score(rcon, "#pos")
    check("pause holds clock", score(rcon, "#state") == 2 and p1 == p2, (p1, p2))

    rcon.command("function deusex:resume")
    time.sleep(1.2)
    p3 = score(rcon, "#pos")
    check("resume advances clock", score(rcon, "#state") == 1 and p3 > p2, (p2, p3))

    rcon.command("function deusex:loop")
    time.sleep(0.3)
    loop_on = score(rcon, "#loop")
    rcon.command("function deusex:loop")
    time.sleep(0.3)
    loop_off = score(rcon, "#loop")
    check("loop toggles #loop", loop_on == 1 and loop_off == 0, (loop_on, loop_off))

    rcon.command("function deusex:stop")
    time.sleep(0.5)
    closing = score(rcon, "#state")
    time.sleep(5.0)
    idle = score(rcon, "#state")
    check("stop -> closing -> idle", closing == 3 and idle == 0, (closing, idle))
    check("weather restored after stop", wait_raining(rcon, False, time.time() + 6) is False)
    check("clock reset after stop", score(rcon, "#pos") == 0)


SHOT_NAMES = ("deusex-vanilla-rain.png", "deusex-show-rain.png", "deusex-skyflash.png",
              "deusex-drop.png", "deusex-lyric.png",
              "deusex-lyric-420.png", "deusex-bossbar.png", "deusex-bossbar-scale4.png",
              "deusex-bossbar-hurt.png", "deusex-bossbar-notch.png", "deusex-bossbar-phase2.png",
              "deusex-bossbar-flat.png", "deusex-strike.png", "deusex-strike-lock.png",
              "deusex-strike-impact.png", "deusex-strike-bolt.png",
              "deusex-bossbar-spared.png", "deusex-free.png",
              "deusex-laser-warn.png", "deusex-laser-lock.png", "deusex-laser-impact.png") + tuple(
    "deusex-corner-%d.png" % i for i in range(8))


def client_phase():
    print("== client phase", flush=True)
    # Stale shots from an earlier run must not be able to satisfy the pixel checks.
    for name in SHOT_NAMES:
        path = os.path.join(SHOTS, name)
        if os.path.exists(path):
            os.remove(path)
    proc, log = gradle(["runClient", "-PdeusexProbe=show"], CLIENT_LOG)
    # Poll instead of a blind wait: if the client's failsafe fires, stop waiting as soon as it
    # shuts itself down (or force it if the window hangs), so a frozen show is analyzed in seconds
    # rather than idling until the full timeout.
    deadline = time.time() + 1150
    log_offset = 0
    while time.time() < deadline:
        if proc.poll() is not None:
            break
        try:
            with open(CLIENT_LOG, "rb") as f:
                f.seek(log_offset)
                chunk = f.read()
                log_offset = f.tell()
            if b"DEUSPROBE FAILSAFE" in chunk:
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill()
                break
        except OSError:
            pass
        time.sleep(1)
    else:
        proc.kill()
        failures.append("client probe timed out")
    log.close()
    time.sleep(2.0)
    check("client exited cleanly", proc.returncode == 0, proc.returncode)

    text = ""
    for path in (os.path.join(RUN, "logs", "latest.log"), CLIENT_LOG):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text += f.read()
        except OSError:
            pass
    lines = [l for l in text.splitlines() if "DEUSPROBE" in l]

    def has(fragment):
        return any(fragment in line for line in lines)

    def line_with(tag):
        return next((line for line in lines if tag in line), "")

    # If the client's failsafe fired, surface its full diagnostic dump as the headline analysis
    # before the downstream checks, and save it to disk for the fix.
    client_text = read(CLIENT_LOG)
    fs_start = client_text.find("DEUSPROBE FAILSAFE triggered")
    if fs_start >= 0:
        fs_end = client_text.find("shutting down the probe", fs_start)
        block = client_text[fs_start:fs_end if fs_end >= 0 else fs_start + 4000]
        print("== FAILSAFE ANALYSIS (probe auto-shutdown) ==", flush=True)
        print(block, flush=True)
        with open(os.path.join(CLIENT, "probe-failsafe.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write(block + "\n")
        reason = block.splitlines()[0].split("triggered:", 1)[-1].strip()
        check("no failsafe (show clock / audio healthy)", False, reason)

    check("probe connected and joined", has("show: joined as Dev"))
    check("vanilla rain untinted", has("vanilla rain must be untinted - active=false rainRed=false"),
          line_with("vanilla-rain:"))

    def ticks_of(line):
        try:
            return int(line.split("ticks=")[1].split()[0])
        except (IndexError, ValueError):
            return -1

    start = line_with("started:")
    check("start -> PLAYING", "state=1 " in start, start)
    # ACT_START carries sample 0: the first payload tick must be barely past the top, back in the
    # quiet build-up the user asked for, not inside the heart scene.
    check("show starts with the build-up", 0 <= ticks_of(start) <= 40, start)
    intro = line_with("intro:")
    check("heart scene follows the build-up", "phase=2" in intro, intro)
    check("drop phase", "phase=3" in line_with("drop:"), line_with("drop:"))
    check("lyrics phase", "phase=4" in line_with("lyric:"), line_with("lyric:"))
    check("red rain gate on", "rainRed=true" in line_with("show-rain:"), line_with("show-rain:"))
    check("sky flash seen", has("sky flash"))
    paused = line_with("pause held")
    check("pause holds audio position", "state=2" in paused and "equal=true" in paused, paused)
    resumed = line_with("resumed advanced")
    check("resume keeps position", "state=1" in resumed, resumed)
    rejoin = line_with("rejoined -")
    check("rejoin resumes playing", "state=1 " in rejoin, rejoin)
    seven = line_with("7:00 lyric")
    check("7:00 lyric matches its window", "match=true" in seven, seven)
    idle = line_with("idle reached")
    check("stop -> idle", "rainRed=false" in idle, idle)
    check("probe completed", has("show: done"))

    sky = shot_metrics("deusex-vanilla-rain.png", "deusex-show-rain.png", "deusex-skyflash.png",
                       "deusex-drop.png", "deusex-lyric.png", "deusex-lyric-420.png",
                       "deusex-bossbar.png", "deusex-bossbar-scale4.png",
                       "deusex-bossbar-hurt.png", "deusex-bossbar-notch.png",
                       "deusex-bossbar-phase2.png", "deusex-bossbar-flat.png",
                       "deusex-strike.png", "deusex-strike-lock.png", "deusex-strike-impact.png",
                       "deusex-laser-warn.png", "deusex-laser-lock.png", "deusex-laser-impact.png",
                       "deusex-bossbar-spared.png", "deusex-free.png")
    for name, m in sky.items():
        print("  shot %-11s %s" % (name, m), flush=True)
    check("vanilla rain is not red", sky["vanilla-rain"]["redness"] < 0.45, sky["vanilla-rain"])
    check("show frame is redder than vanilla rain",
          sky["show-rain"]["redness"] > sky["vanilla-rain"]["redness"] + 0.06,
          (sky["vanilla-rain"]["redness"], sky["show-rain"]["redness"]))
    check("sky flash is redder than normal sky",
          sky["skyflash"]["redness"] > sky["vanilla-rain"]["redness"] + 0.08,
          (sky["vanilla-rain"]["redness"], sky["skyflash"]["redness"]))
    check("drop is bright", sky["drop"]["brightness"] > 60, sky["drop"])
    check("lyric band has bright text", sky["lyric"]["text"] > 100, sky["lyric"])
    check("7:00 lyric band has bright text", sky["lyric-420"]["text"] > 100, sky["lyric-420"])
    bossline = line_with("bossbar -")
    check("boss bar payload synced", "visible=true" in bossline, bossline)
    check("boss bar shows RONOVA fill and name",
          sky["bossbar"]["fill"] > 2000 and sky["bossbar"]["name"] > 20, sky["bossbar"])
    # The bar's logical size divides by GUI scale, so its physical wordmark width must not
    # grow when the scale goes 2 -> 4 (the old fixed-logical bar doubled it).
    check("boss bar stays compact at GUI scale 4",
          sky["bossbar-scale4"]["fill"] > 500 and sky["bossbar-scale4"]["name"] > 20
          and sky["bossbar-scale4"]["name_w"] <= sky["bossbar"]["name_w"] * 1.15,
          (sky["bossbar"]["name_w"], sky["bossbar-scale4"]["name_w"]))
    hurt = line_with("bossbar hurt")
    check("boss bar fill drops on damage", "dropped=true" in hurt, hurt)
    check("boss bar refills on heal", "restored=true" in line_with("bossbar heal"), line_with("bossbar heal"))
    check("boss bar empties on death", "emptied=true" in line_with("bossbar death"), line_with("bossbar death"))
    defeat = line_with("boss defeat -")
    check("boss death closes the show", "state=3" in defeat and "barVisible=false" in defeat, defeat)
    ended = line_with("boss death stopped the event")
    check("boss death ends the event", "state=0" in ended, ended)
    check("advancement toast captured",
          not sky["free"].get("missing", False) and sky["free"]["toast"] > 40, sky["free"])
    check("boss bar hurt shot shows reduced fill",
          500 < sky["bossbar-hurt"]["fill"] < sky["bossbar"]["fill"] * 0.85,
          (sky["bossbar"]["fill"], sky["bossbar-hurt"]["fill"]))
    notch = line_with("bossbar notch")
    check("hit reactions fired (recoil, big hit, frame flash)",
          "recoil=true" in notch and "bigHit=true" in notch and "frameFlash=true" in notch, notch)
    check("crossing notches flare white-hot",
          sky["bossbar-notch"]["hot"] > sky["bossbar"]["hot"] + 60,
          (sky["bossbar"]["hot"], sky["bossbar-notch"]["hot"]))
    check("phase 2 latches at half health", "phase2=true" in line_with("bossbar phase2"),
          line_with("bossbar phase2"))
    # The seal-break tint crushes the molten fill's bright orange streaks to crimson: only the
    # gold frame trim leaking into the band's top rows stays bright. Mean-green ratios drift with
    # the animated lava texture, so count bright survivors instead (untinted ~100, tinted ~trim).
    check("phase 2 burns crimson",
          sky["bossbar-phase2"]["bright"] < sky["bossbar"]["bright"] * 0.5,
          (sky["bossbar"]["bright"], sky["bossbar-phase2"]["bright"]))
    # The wordmark is a living surface now: white ink that burns crimson with the seal. The glint
    # only warms the glyphs, so the baseline count stays near zero even under a sheen band.
    check("wordmark burns crimson in phase 2",
          sky["bossbar-phase2"]["name_red"] > sky["bossbar"]["name_red"] * 2 + 150,
          (sky["bossbar"]["name_red"], sky["bossbar-phase2"]["name_red"]))
    live = line_with("bossbar live start")

    def buffs_of(line):
        """The dev probe prints its ambient effects as buffs=[id:amplifier,...]; read that field
        alone, or the "(expect ...)" hint on the same line would satisfy the check by itself."""
        if "buffs=[" not in line:
            return None
        return [p.strip() for p in line.split("buffs=[", 1)[1].split("]", 1)[0].split(",")
                if p.strip()]

    def buffs_are(line, want, forbid=()):
        got = buffs_of(line)
        return got is not None and sorted(got) == sorted(want) \
            and not any(f in got for f in forbid)

    check("buff tier 1: speed + resistance",
          buffs_are(live, ["resistance:0", "speed:0"], ["strength:0"]), live)
    check("buff tier 1 held on damage",
          buffs_are(hurt, ["resistance:0", "speed:0"], ["strength:0"]), hurt)
    check("phase 2 lends speed II, strength and regeneration",
          buffs_are(notch, ["regeneration:0", "speed:1", "strength:0"], ["resistance:0"]), notch)
    phase2line = line_with("bossbar phase2")
    check("phase 2 buff tier held",
          buffs_are(phase2line, ["regeneration:0", "speed:1", "strength:0"], ["resistance:0"]),
          phase2line)
    check("death draws an ember flatline",
          sky["bossbar-flat"]["line"] > 40 and sky["bossbar-flat"]["deck"] < 150,
          (sky["bossbar"]["deck"], sky["bossbar-flat"]["deck"], sky["bossbar-flat"]["line"]))

    # ---------------------------------------------------------------- storm proof
    warn = line_with("storm warning")
    check("storm marks only non-boss players",
          "wave=1" in warn and "targets=1" in warn and "marks=1" in warn, warn)
    lockline = line_with("storm locked")
    check("storm pins the strike point before the bolt",
          "ticksLeft=" in lockline and "urgency=" in lockline, lockline)
    hit = line_with("storm hit")
    check("failing to dodge costs health", "dropped=true" in hit, hit)
    effects = [p for p in hit.split("effects=[", 1)[-1].split("]", 1)[0].split(",") if p.strip()]
    applied = {":".join(p.split(":")[:2]) for p in effects}
    check("failed dodge lands weakness, slowness II and blindness",
          {"weakness:0", "slowness:1", "blindness:0"} <= applied, effects)
    # The debuffs last STORM_DEBUFF_TICKS = 80 ticks (four seconds); the client reads them one
    # tick after the server applied them, so 79 is on time.
    durations = [int(p.rsplit(":", 1)[-1]) for p in effects if p.rsplit(":", 1)[-1].isdigit()]
    check("storm debuffs last about four seconds",
          durations and 75 <= min(durations) <= 80, durations)
    dodge = next((l for l in lines if "storm dodge -" in l and "untouched=" in l), "")
    check("dodging the bolt is clean",
          "untouched=true" in dodge and "dodged=true" in dodge and "debuffs=[]" in dodge, dodge)
    spared = line_with("boss spared")
    check("the storm never marks the boss",
          "targets=0" in spared and "marks=0" in spared and "spared=true" in spared, spared)
    check("warning sigil drawn on the ground", sky["strike"]["ivory"] > 2000, sky["strike"])
    check("locked sigil burns crimson", sky["strike-lock"]["crimson"] > sky["strike"]["crimson"],
          (sky["strike"]["crimson"], sky["strike-lock"]["crimson"]))
    # The hit flash paints the whole frame red, so the impact reads as redder than the warning,
    # not as a white bloom (the red veil crushes every channel, so brightness falls).
    check("bolt impact flashes red", sky["strike-impact"]["redness"] > 0.8,
          sky["strike-impact"])

    # ---------------------------------------------------------------- graphics proof
    # The lance mark is client-injected at a fixed point ahead of the probe, so the three frames
    # are the same camera and can be compared to each other rather than to an absolute.
    lwarn = line_with("lance warn frame")
    check("the seal lance decodes as a lance", "laser=true" in lwarn and "marks=1" in lwarn, lwarn)
    check("the lance keeps its mark through the lock",
          "laser=true" in line_with("lance locked frame"), line_with("lance locked frame"))
    limpact = line_with("lance impact frame")
    check("the lance impact lands its beam", "impacts=" in limpact and "impacts=0" not in limpact,
          limpact)
    check("the impact column is brighter than the guide beam",
          sky["laser-impact"]["pale"] > sky["laser-warn"]["pale"],
          (sky["laser-warn"]["pale"], sky["laser-impact"]["pale"]))

    # The drum flash: eight frames over 14 ticks of the same static camera, each stamped with the
    # show tick. The baked envelope says which frames sit on a kick; the corner crops must agree.
    beat_path = os.path.join(CLIENT, "src", "main", "resources", "assets", "deusexmachina",
                             "show", "beat.bin")
    with open(beat_path, "rb") as f:
        env = f.read()
    frames = []
    for i in range(8):
        line = line_with("corner - shot=%d " % i)
        m = re.search(r"ticks=(\d+)", line)
        path = os.path.join(SHOTS, "deusex-corner-%d.png" % i)
        if not m or not os.path.exists(path):
            continue
        t = int(m.group(1))
        want = max(env[max(0, t - 1):t + 2] or b"\x00") / 255.0
        with Image.open(path) as img:
            frames.append((want, i, corner_metrics(img.convert("RGB"))))
    if len(frames) < 6:
        failures.append("corner flash frames missing (%d of 8)" % len(frames))
    else:
        hi = max(frames, key=lambda v: v[0])
        lo = min(frames, key=lambda v: v[0])
        print("  corner frames:", [(round(w, 2), i, m["corner_rg"], m["centre_rg"])
                                   for w, i, m in frames], flush=True)
        check("corner flash is on screen", hi[2]["corner_rg"] > 2.0, hi)
        check("corner flash follows the drums",
              hi[0] - lo[0] > 0.25 and hi[2]["corner_rg"] >= lo[2]["corner_rg"] + 2.0,
              ("hi", hi, "lo", lo))
        check("corner flash stays a hint", hi[2]["corner_rg"] < 90
              and hi[2]["corner_bright"] - lo[2]["corner_bright"] < 30, (hi, lo))
        check("corner flash stays out of the centre",
              hi[2]["centre_rg"] - lo[2]["centre_rg"] < 3.0, (hi[2]["centre_rg"], lo[2]["centre_rg"]))


def bossbar_metrics(rgb):
    """The RONOVA bar: molten-orange fill texels and the bright serif wordmark.

    The bar spans the upper half of the frame (top 12% is the name, then the bar itself), so
    both counts come from a top crop. Fill pixels are hot orange-red; the wordmark is neutral
    unless the seal break turns it crimson, which `name_red` counts in the wordmark rows only.
    The interior band (below the wordmark, above the subtitle) additionally counts white-hot
    notch flares, crimson phase-II tint and the ember ECG flatline, measured at GUI scale 2.
    """
    w, h = rgb.size
    top = rgb.crop((0, 0, w, int(h * 0.55)))
    fill = name = 0
    fill_g_sum = 0
    rows = {}
    for i, (r, g, b) in enumerate(top.getdata()):
        if r > 170 and 30 < g < 190 and b < 110 and r > g * 1.3:
            fill += 1
            fill_g_sum += g
        if min(r, g, b) > 185 and max(r, g, b) - min(r, g, b) < 40:
            name += 1
            x, y = i % w, i // w
            row = rows.setdefault(y, [x, x, 0])
            row[0], row[1], row[2] = min(row[0], x), max(row[1], x), row[2] + 1
    # White-hot fill sparks also read neutral; only dense glyph rows form the wordmark.
    dense = [v for v in rows.values() if v[2] >= 25]
    name_w = max(v[1] for v in dense) - min(v[0] for v in dense) + 1 if dense else 0
    inner = rgb.crop((int(w * 0.16), int(h * 0.25), int(w * 0.84), int(h * 0.37)))
    hot = crimson = 0
    for r, g, b in inner.getdata():
        if min(r, g, b) > 210:
            hot += 1
        if r > 130 and g < 75 and b < 80 and r > g * 1.8:
            crimson += 1
    mid = rgb.crop((int(w * 0.16), int(h * 0.30), int(w * 0.84), int(h * 0.33)))
    line = sum(1 for r, g, b in mid.getdata() if r > 170 and 50 < g < 170 and b < 110 and r > g * 1.4)
    # The interior deck above the ECG midline: molten fill while alive, charred nothing on death.
    deck = rgb.crop((int(w * 0.18), int(h * 0.265), int(w * 0.82), int(h * 0.295)))
    deck_fill = deck_g_sum = deck_bright = 0
    for r, g, b in deck.getdata():
        if r > 170 and 30 < g < 190 and b < 110 and r > g * 1.3:
            deck_fill += 1
            deck_g_sum += g
            if g > r * 0.45:
                deck_bright += 1
    # The wordmark rows only (the bar's frame starts at 12.9% of the frame): glyphs whose white
    # ink has burned crimson. The rain sky up here is muted lavender, far below the gate, so the
    # count is the wordmark alone.
    name_red = 0
    name_band = rgb.crop((0, 0, w, int(h * 0.12)))
    for r, g, b in name_band.getdata():
        if r > 150 and g < r * 0.60 and b < r * 0.78 and r > g * 1.9:
            name_red += 1
    return {"fill": fill, "name": name, "name_w": name_w,
            "fill_g": round(fill_g_sum / max(1, fill), 1),
            "hot": hot, "crimson": crimson, "line": line, "deck": deck_fill,
            "deck_g": round(deck_g_sum / max(1, deck_fill), 1), "bright": deck_bright,
            "name_red": name_red}


def storm_metrics(rgb):
    """The storm's ground sigil and the advancement toast.

    The sigil is drawn at full brightness over a red-veiled dusk scene, so the ivory count in the
    middle-lower band - where the ground around the player projects - collapses when the decal is
    missing. The locked ring and its bloom are crimson, and the bolt adds a white flash across that
    band. The toast is vanilla's dark card at the top right, so its white text and nether-star icon
    are counted in that corner only.
    """
    w, h = rgb.size
    band = rgb.crop((int(w * 0.15), int(h * 0.30), int(w * 0.85), int(h * 0.85)))
    ivory = crimson = 0
    bright = 0.0
    for r, g, b in band.getdata():
        # The decal is ivory at 30-52% alpha over a red-veiled dusk, so its "white" is really a
        # pale, low-chroma pixel: a 185 minimum never fires in frame and a 100 one clearly does
        # (the bolt's red flash crushes every channel down, so the impact shot reads zero).
        if min(r, g, b) > 100 and max(r, g, b) - min(r, g, b) < 100:
            ivory += 1
        if r > 150 and g < 90 and b < 90 and r > g * 1.8:
            crimson += 1
        bright += (r + g + b) / 3.0
    total = max(1, band.width * band.height)
    toast = 0
    corner = rgb.crop((int(w * 0.55), 0, w, int(h * 0.16)))
    for r, g, b in corner.getdata():
        if min(r, g, b) > 200:
            toast += 1
    return {"ivory": ivory, "crimson": crimson, "toast": toast,
            "brightness": round(bright / total, 1)}


def corner_metrics(rgb):
    """Red excess in the four corner squares - and in the centre - for one frame.

    The flash is four soft red lamps, so it lifts r over g in the corners while leaving the middle
    of the screen alone. Comparing frames taken seconds apart with the camera fixed separates the
    flash from whatever the scene's own red veil contributes.
    """
    w, h = rgb.size
    s = int(min(w, h) * 0.12)
    rgs = []
    bright = 0.0
    for box in ((0, 0, s, s), (w - s, 0, w, s), (0, h - s, s, h), (w - s, h - s, w, h)):
        crop = rgb.crop(box)
        px = list(crop.getdata())
        rgs.append(sum(p[0] - p[1] for p in px) / len(px))
        bright += sum((p[0] + p[1] + p[2]) / 3.0 for p in px) / len(px)
    centre = rgb.crop((int(w * 0.36), int(h * 0.38), int(w * 0.64), int(h * 0.62)))
    px = list(centre.getdata())
    centre_rg = sum(p[0] - p[1] for p in px) / len(px)
    return {"corner_rg": round(sum(rgs) / 4.0, 2), "corner_bright": round(bright / 4.0, 1),
            "centre_rg": round(centre_rg, 2)}


def shot_metrics(*names):
    empty = {"missing": True, "red": 0, "text": 0, "center_red": 0, "brightness": 0.0,
             "redness": 0.0, "fill": 0, "name": 0, "name_w": 0, "fill_g": 0.0,
             "hot": 0, "crimson": 0, "line": 0, "deck": 0, "deck_g": 0.0, "bright": 0,
             "name_red": 0, "ivory": 0, "toast": 0, "pale": 0}
    out = {}
    for name in names:
        key = name.replace("deusex-", "").replace(".png", "")
        path = os.path.join(SHOTS, name)
        if not os.path.exists(path):
            out[key] = dict(empty)
            continue
        with Image.open(path) as img:
            rgb = img.convert("RGB")
            w, h = rgb.size
            top = rgb.crop((0, 0, w, int(h * 0.40)))
            total = top.width * top.height
            red = bright = redness = 0
            for r, g, b in top.getdata():
                if r > 90 and r > g * 1.6 and r > b * 1.6:
                    red += 1
                bright += (r + g + b) / 3.0
                redness += r / max(1.0, float(r + g + b))
            # The lyric row sits at guiHeight-63..-23, i.e. 74-90% of the frame at scale 2.
            # Its glyphs are white under the red veil, so they are light but not pure white.
            band = rgb.crop((0, int(h * 0.70), w, int(h * 0.92)))
            text = sum(1 for r, g, b in band.getdata() if (r + g + b) / 3.0 > 170.0)
            center = rgb.crop((int(w * 0.30), int(h * 0.25), int(w * 0.70), int(h * 0.75)))
            center_red = sum(1 for r, g, b in center.getdata()
                             if r > 120 and r > g * 1.5 and r > b * 1.5)
            out[key] = {"red": red, "text": text, "center_red": center_red,
                        "brightness": round(bright / max(1, total), 1),
                        "redness": round(redness / max(1, total), 3)}
            if key in ("bossbar", "bossbar-scale4", "bossbar-hurt", "bossbar-notch",
                       "bossbar-phase2", "bossbar-flat"):
                out[key].update(bossbar_metrics(rgb))
            if key in ("strike", "strike-lock", "strike-impact", "strike-bolt", "free"):
                out[key].update(storm_metrics(rgb))
            if key.startswith("laser-"):
                # The lance's pale column and glyph against the red-veiled dusk: low-chroma bright
                # pixels in the middle of the frame, where the mark sits four blocks ahead.
                mid = rgb.crop((int(w * 0.25), int(h * 0.12), int(w * 0.75), int(h * 0.70)))
                out[key]["pale"] = sum(1 for r, g, b in mid.getdata()
                                       if min(r, g, b) > 165 and max(r, g, b) - min(r, g, b) < 60)
    return out


def main():
    prepare()
    proc, log = gradle(["runServer"], SERVER_LOG)
    try:
        deadline = time.time() + 240
        rcon = wait_rcon(deadline)
        while time.time() < deadline and "Done (" not in read(SERVER_LOG):
            time.sleep(1)
        check("dev server started", "Done (" in read(SERVER_LOG))
        server_phase(rcon)
        if "--server-only" not in sys.argv:
            client_phase()
            # The boss show's own start() reset the storm counters, so what survives here is the
            # death latch and the count of players the free-server advancement reached.
            check("server latched the boss death", score(rcon, "#dead") == 1, score(rcon, "#dead"))
            check("advancement reached the player", score(rcon, "#free") == 1,
                  (score(rcon, "#free"), score(rcon, "#wave"), score(rcon, "#hits")))
        rcon.command("scoreboard players get #state deusex")
        rcon.command("stop")
        time.sleep(5)
    finally:
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()

    print("== failures: %d" % len(failures), flush=True)
    for name in failures:
        print("  - " + name, flush=True)
    return 1 if failures else 0


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


if __name__ == "__main__":
    sys.exit(main())
