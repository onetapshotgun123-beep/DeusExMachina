"""Generate srvtest/cmds.txt for the 1.0.34 checks and sync the datapack mirror.

Everything the last fixes touch is asserted by walking the real functions tick by tick, so the
log is the proof:

  * #drop / #8 / lyrics list - the constants the schedule and the fade depend on, plus #lead, which
    load only defaults when the score is unset, so the header asks whether it is set at all rather
    than demanding 33.
  * tick.mcfunction itself, 1200 times, with nothing armed but what start arms. This is the walk
    that can actually fail the way a real game fails: the gates that let the flash, the veil and
    the rain run at all are #state 1, #cstate 0 and #ostage 4.., and every other section here sets
    those by hand, so a stage machine that never reaches #ostage 4 or a flash that never rearms has
    passed them all. It reports the tick each stage is first reached, whether the heartbeat count
    is the table's ten, and whether the veil was ever raised by anything other than this file. Since
    1.0.31 it also latches the tick #rain first goes up, and asks on the tick #ostage reached 3 - the
    burst, reached rather than armed - whether the sky was already wet and #lv already climbing.
  * the report and the two force-commands, for the state they leave behind - whether the tellraw
    in selftest survives an empty server, and whether test_flash really raises the veil now that
    flash_begin's arithmetic runs before its entity operations.
  * opening_hb over #E 0..400 - the heartbeat must fire exactly on the offsets in
    opening_hb.mcfunction, and a second walk from #drop to #drop+24 must fire none, because
    heartbeat.ogg is still audible about 22 ticks after it is started. A beat is detected because
    hb_beat resets #hb to 0 and the function increments it, so #hb == 1 after the call means "this
    tick was a beat". The offsets are read out of the shipped file, so this cannot drift from it.
  * run_lead then run_playing, tick by tick - the clock stays pinned at #E 0 for the whole decode
    hold, then advances one per tick, and main_track is triggered once per pass. The trigger is
    visible because play_chunk is the only thing that writes deusex:data idx: each tick starts by
    poisoning that key with -999, and a tick that leaves it poisoned did not fire a sound. This is
    the check that catches the duplicate hand-over fire - run_playing tests #t 0, and #t is still 0
    on the tick the hold ends, so the ungated line re-played the 546 s track 33 ticks after firing
    it the first time. The two dispatch lines are lifted out of tick.mcfunction and replayed in the
    order they ship in, so the walk also catches a hand-over tick that both counts the hold down
    and starts the clock, which is one tick of drift taken off the decode time it is meant to wait
    out.
  * next_chunk at the wrap - a looped pass re-arms the hold, or the second playthrough drifts the
    whole decode time ahead of the music.
  * lyric_tick over the first line's window - the picked glyph index has to climb one level per
    tick for FADE_IN ticks, hold at 5, then step down over FADE_OUT ticks.
  * opening_flash over #drop..#drop+50 - the burst frame index and the glyph it selects, plus
    #ostage reaching 4 so the title is reset and the world goes back to plain Minecraft. Since 1.0.31
    the same walk carries the veil: #wash is ramped in tick.mcfunction's own order around every call,
    the title has to repaint on all 51 ticks (rc poisoned first, so a blind tick says so), the level
    has to be min(k, #washbase) on tick k and never fall, and the tick after opening_done's reset
    wash_draw has to bring the same cell back - which only works because opening_done invalidates
    #wlast, since a level that has not changed is a level wash_draw will not paint.
  * the rain, two ways. The live walk latches the tick #rain first goes up and asserts it was already
    up on the tick #ostage reached 3; the deterministic walk drives opening_tick at #rainlead-1,
    #rainlead, #rainlead+1 and #drop - by #idx and #t, because opening_tick recomputes #E from them -
    and reads #rain back after each. The markers bracket the tick the flag moved; they cannot show the
    weather command itself, which a nested function never prints, so "exactly once" is the validator's
    replay of the gate.
  * flash_tick for two envelope lengths - the red sky flash rearms itself and counts #fframe down
    from whatever flash_begin arms it at, to 0 and not past it.
  * the veil, in five parts: wash_tick alone drains one level per DRAIN calls, never early, and
    stops on #washbase rather than on 0; the same function walks a veil left at 0 back up to the
    floor one level a tick, which is what the burst leaves behind; wash_draw alone repaints once per
    level and paints the cell that level is; the same level drawn twice does not repaint at all,
    which is the #wlv = #wlast gate that keeps the screen from restarting its title twenty times a
    second; and #wash above the ceiling is clamped before it can ask lv_char for a cell that does
    not exist. The repaint is detected by poisoning deusex:data rc with "!" and asking the server
    whether the key still matches that value, because storing a one-character string out of a
    data-get reports its length, not its codepoint, and every cell in red_lv's run is exactly one
    character.

Every walk in the frozen section runs under /tick freeze. tick.mcfunction moves #wash on any tick
where it is not already sitting on #washbase - not only while the song plays - so a world that keeps
ticking steals levels from a scripted walk and the drain rate is unknowable; #state 0 does not help
because that gate is not on #state. The freeze also keeps run_lead and run_playing from being driven
a second time by the game while the clock walk counts them by hand.

What the soak still cannot reach: the summons in flash_spawn and the playsounds need a level and
players, and the console source has neither, so they are verified in the rendered model (skyview.py /
hudview.py) instead.
"""
import io
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import make_lyrics as M

SRV = os.path.join(ROOT, "srvtest")
DP = os.path.join(SRV, "world", "datapacks", "deusex", "data")
FUN = os.path.join(ROOT, "extracted", "data", "deusex", "function")

# Poison values: both keys are always written by the real function, so a tick that leaves the
# sentinel in place is a tick that did not call it. idx is numeric, so a data-get can be compared
# against the sentinel; rc is a one-character string, and a data-get of a string answers its
# length, so rc is matched by an SNBT predicate against the sentinel itself instead.
NO_FIRE = -999
SENTINEL = '"!"'
NOT_PAINTED = 'data storage deusex:data {rc:%s}' % SENTINEL


def shipped(name):
    return io.open(os.path.join(FUN, name + ".mcfunction"), encoding="utf-8").read()


CONST = {k: int(v) for k, v in
         re.findall(r"scoreboard players set (#\S+) deusex (-?\d+)", shipped("load"))}
DROP = CONST["#drop"]
LEAD = int(re.search(r"execute if score #lead deusex matches (\d+) run function",
                     shipped("run_lead")).group(1))
# The tick the *real* track goes out, which is not the tick the lead-in is armed: run_lead spends the
# head of the window on a silent streamed prewarm that does the decode work, and fires the song only
# when #lead has counted down to this. The walk reports the fire as GAPLESS_FIRE_<n>, so the expected
# number is the gap between the two gates, not the whole hold.
FIRE = int(re.search(r"execute if score #lead deusex matches (\d+) run function deusex:fire_track",
                     shipped("run_lead")).group(1))
WASHMAX = CONST["#washmax"]
# Every number the veil and flash probes compare against, read out of the files the game actually
# runs. These probes used to hardcode 30 and a 46 tick loop, which is how a re-timed envelope kept
# passing a soak while the screen showed something else entirely.
FFRAME = int(re.search(r"^scoreboard players set #fframe deusex (\d+)$",
                       shipped("flash_begin"), re.M).group(1))
# test_wash arms the spike either by a literal or by #washmax, the way flash_begin does; since the
# floor moved above the old literal 10 it uses the ceiling, so read whichever spelling is shipped.
_mt = re.search(r"^scoreboard players (?:set #wash deusex (\d+)"
                r"|operation #wash deusex = #washmax deusex)$", shipped("test_wash"), re.M)
assert _mt, "test_wash never arms #wash"
WASH_TEST = WASHMAX if _mt.group(1) is None else int(_mt.group(1))
DRAIN = int(re.search(r"if score #washc deusex matches (\d+)\.\. if score #wash deusex >",
                      shipped("wash_tick")).group(1))
WASHBASE = int(re.search(r"^scoreboard players set #washbase deusex (\d+)$",
                         shipped("opening_burst"), re.M).group(1))
assert 0 < WASHBASE < WASHMAX, "#washbase %d outside 0..#washmax %d" % (WASHBASE, WASHMAX)
# How far ahead of the drop the storm is armed, read off load's own derivation rather than repeated
# here: ServerLevel.advanceWeatherCycle moves rainLevel 0.01F a tick, so the downpour the opening
# stands in is 100 ticks in the making and no command jumps it.
RAIN_AHEAD = int(re.search(r"^scoreboard players remove #rainlead deusex (\d+)$",
                           shipped("load"), re.M).group(1))
assert RAIN_AHEAD >= 100, "#rainlead is only %d ticks ahead of the drop" % RAIN_AHEAD
RAINLEAD = DROP - RAIN_AHEAD
# The tick the cutscene lets go of the title slot, out of opening_flash itself.
BURST_K = int(re.search(r"matches (\d+)\.\. run function deusex:opening_done",
                        shipped("opening_flash")).group(1))
LAST = CONST["#last"]
LASTLEN = CONST["#lastlen"]
BEATS = sorted(int(x) for x in re.findall(r"matches (-\d+) run function deusex:hb_beat",
                                          shipped("opening_hb")))
# The two lines the game itself uses to choose between the hold and the running clock, taken in the
# order they are written. The walk replays them rather than a copy so a reordering - which is what
# made the hand-over tick move the clock and burn the hold in the same tick - shows up here as a
# drift instead of being hidden by a second, differently ordered replica in this file.
LEAD_DISPATCH = [l.strip() for l in shipped("tick").splitlines()
                 if l.startswith("execute") and "#lead deusex" in l and "run function deusex:run" in l]
assert len(LEAD_DISPATCH) == 2, LEAD_DISPATCH


def sync():
    if os.path.isdir(DP):
        shutil.rmtree(DP)
    shutil.copytree(os.path.join(ROOT, "extracted", "data"), DP)
    print("datapack synced ->", DP)


def probe(L, section, keys):
    """Pack named scores into one storage compound so a single log line carries them all.

    Each section gets its own compound: the root of a storage cannot be replaced, so leftover
    keys from an earlier section would otherwise still print."""
    for tag, sc in keys:
        L.append("execute store result storage deusex:probe %s.%s int 1 "
                 "run scoreboard players get %s deusex" % (section, tag, sc))
    L.append("data get storage deusex:probe %s" % section)


def clock_start(L, full):
    # #state 1 because the shipped dispatch lines test it; the world cannot steal a step from the
    # walk because the game is frozen for the whole deterministic half of this soak.
    L.append("scoreboard players set #lead deusex %d" % (LEAD if full else 0))
    L.append("scoreboard players set #idx deusex 0")
    L.append("scoreboard players set #t deusex 0")
    L.append("scoreboard players set #full deusex %d" % full)
    L.append("scoreboard players set #ostage deusex 0")
    L.append("scoreboard players set #loop deusex 1")
    L.append("scoreboard players set #state deusex 1")


def one_tick(L, tick, tag):
    """Run the shipped clock for one game tick and log whether it fired a chunk sound."""
    L.append("data modify storage deusex:data idx set value %d" % NO_FIRE)
    L.extend(LEAD_DISPATCH)
    L.append("execute store result score #idxw deusex run data get storage deusex:data idx")
    L.append("execute unless score #idxw deusex matches ..-1 run say %s_FIRE_%d" % (tag, tick))
    probe(L, "ck", [("lead", "#lead"), ("idx", "#idx"), ("t", "#t")])


def draw_once(L, level):
    """Arm the veil at one level, force the repaint gate open, draw once, and read back what landed.

    #wlast is set to -1 so #wlv can always differ from it: without that the previous step's paint
    would leave the gate shut and the walk would prove nothing about the cell it selects."""
    L.append("scoreboard players set #wash deusex %d" % level)
    L.append("scoreboard players set #wlast deusex -1")
    L.append("data modify storage deusex:data rc set value %s" % SENTINEL)
    L.append("function deusex:wash_draw")
    L.append("execute unless %s run say REPAINT_%d" % (NOT_PAINTED, level))
    L.append("execute if %s run say NO_REPAINT_AT_%d" % (NOT_PAINTED, level))
    L.append("execute unless score #lv deusex matches %d run say WRONG_CELL_%d" % (level, level))
    L.append("execute unless score #lv deusex = #wlv deusex run say CELL_NOT_GATE_%d" % level)
    probe(L, "ws", [("wash", "#wash"), ("wlv", "#wlv"), ("lv", "#lv"), ("last", "#wlast")])


def live_tick(L, ticks):
    """Drive the real game loop, tick.mcfunction whole, for `ticks` iterations.

    Every other walk in this file calls one function at a time with the state it wants already
    armed, which is exactly how the last two releases passed a soak and still showed nothing on
    screen: the gates that decide whether the sky flash, the veil and the rain are allowed to run
    at all (#state 1, #cstate 0, #ostage 4..) were set by hand rather than reached. Here nothing is
    armed except what start.mcfunction would arm, so a stage machine that never gets to #ostage 4,
    or a flash that never rearms, or a veil that is never raised, fails this walk the way it fails
    in a real game.
    """
    L.append("say ---LIVE-TICK %d ticks of tick.mcfunction itself" % ticks)
    # start.mcfunction cannot be called from a console: its third line is a kill @e, which throws
    # without a level and stops the rest of the function, so the same scores are set here in the
    # same order the shipped file sets them.
    for sc, val in (("state", 1), ("ostage", 1), ("cstate", 0), ("full", 1), ("lead", LEAD),
                    ("idx", 0), ("t", 0), ("wash", 0), ("washbase", 0), ("washc", 0), ("wlast", 0),
                    ("fframe", 0),
                    ("flashd", 200), ("loop", 1), ("tk", 0), ("beats", 0), ("flashes", 0),
                    ("hb", 99), ("E", 0), ("li", -1), ("hudt", 0), ("s2", 0), ("s3", 0),
                    ("s4", 0), ("sw", 0), ("sf", 0), ("sheld", 0), ("sr", 0), ("sv", 0),
                    ("cu", 0), ("cidx", 0)):
        L.append("scoreboard players set #%s deusex %d" % (sc, val))
    for t in range(ticks):
        L.append("function deusex:tick")
        # The two questions 1.0.31 is answerable by, asked of the game's own loop rather than of a
        # state this file armed by hand: was the sky already wet on the tick the heart bursts, and did
        # the wash reach the screen *during* the cutscene instead of 50 ticks after it? The veil check
        # asks for #lv 1.. rather than 14 because the drop tick is deliberately lv 0 - the blast is a
        # white-out there - and wash_tick only walks one level a tick after opening_flash has drawn.
        L.append("execute if score #rain deusex matches 1 unless score #sr deusex matches 1 "
                 "run say RAIN_ARMED_AT_%d" % t)
        L.append("execute if score #rain deusex matches 1 run scoreboard players set #sr deusex 1")
        L.append("execute if score #ostage deusex matches 3 unless score #s3 deusex matches 1 "
                 "if score #rain deusex matches 1 run say BURST_WET")
        L.append("execute if score #ostage deusex matches 3 unless score #s3 deusex matches 1 "
                 "unless score #rain deusex matches 1 run say BURST_DRY")
        L.append("execute if score #ostage deusex matches 3 if score #lv deusex matches 1.. "
                 "unless score #sv deusex matches 1 run say BURST_VEIL_AT_%d" % t)
        L.append("execute if score #ostage deusex matches 3 if score #lv deusex matches 1.. "
                 "run scoreboard players set #sv deusex 1")
        # the first tick each stage is reached, once - a stage machine that stalls would otherwise
        # look identical to one that simply takes its time
        for stage, flag in (("2", "#s2"), ("3", "#s3"), ("4", "#s4")):
            L.append("execute if score #ostage deusex matches %s unless score %s deusex "
                     "matches 1 run say STAGE%s_AT_%d" % (stage, flag, stage, t))
            L.append("execute if score #ostage deusex matches %s run scoreboard players "
                     "set %s deusex 1" % (stage, flag))
        L.append("execute if score #flashes deusex matches 1.. unless score #sf deusex "
                 "matches 1 run say FIRST_FLASH_AT_%d" % t)
        L.append("execute if score #flashes deusex matches 1.. run scoreboard players "
                 "set #sf deusex 1")
        L.append("execute if score #wash deusex matches 1.. unless score #sw deusex "
                 "matches 1 run say WASH_UP_AT_%d" % t)
        L.append("execute if score #wash deusex matches 1.. run scoreboard players "
                 "set #sw deusex 1")
        # The floor is the whole port: wash_tick may drain to #washbase and no further. The check is
        # latched rather than immediate because the burst raises #washbase while #wash is still 0 and
        # wash_tick walks it up one level a tick - the first #washbase ticks are the ramp, not a
        # failure - and it runs every tick instead of at the end because a flash can be mid-drain on
        # the last one.
        L.append("execute if score #washbase deusex matches 1.. if score #wash deusex >= "
                 "#washbase deusex unless score #sheld deusex matches 1 run say VEIL_FLOOR_HIT_AT_%d"
                 % t)
        L.append("execute if score #washbase deusex matches 1.. if score #wash deusex >= "
                 "#washbase deusex run scoreboard players set #sheld deusex 1")
        L.append("execute if score #sheld deusex matches 1 if score #wash deusex < "
                 "#washbase deusex run say VEIL_UNDER_FLOOR_%d" % t)
        # 1.0.32: a rejoiner is served at the first chunk head after their tag. The walk has no
        # players, so the tag itself cannot be applied here; what it can prove is that a head exists
        # mid-song on the gapless path, and that the macro the head would run binds its cell and
        # answers an empty @a[tag] by running zero times instead of throwing into run_playing.
        head = ("if score #t deusex matches 0 if score #full deusex matches 1 "
                "if score #E deusex matches 600.. unless score #cu deusex matches 1")
        L.append("execute %s run say CATCHUP_HEAD_AT_%d" % (head, t))
        L.append("execute %s store result storage deusex:data idx int 1 "
                 "run scoreboard players get #idx deusex" % head)
        L.append("execute %s run function deusex:catchup_macro with storage deusex:data" % head)
        L.append("execute %s store result score #cidx deusex "
                 "run data get storage deusex:data idx" % head)
        L.append("execute %s if score #cidx deusex = #idx deusex run say CATCHUP_IDX_OK" % head)
        L.append("execute %s unless score #cidx deusex = #idx deusex "
                 "run say CATCHUP_IDX_WRONG" % head)
        L.append("execute %s run scoreboard players set #cu deusex 1" % head)
        if t % 20 == 0 or t == ticks - 1:
            probe(L, "lt", [("tk", "#tk"), ("os", "#ostage"), ("E", "#E"), ("beats", "#beats"),
                             ("fl", "#flashes"), ("wash", "#wash"), ("base", "#washbase"),
                             ("wlv", "#wlv"), ("lv", "#lv"), ("ff", "#fframe"), ("fd", "#flashd")])
    L.append("execute if score #tk deusex matches %d run say LOOP_COUNTED" % ticks)
    L.append("execute unless score #tk deusex matches %d run say LOOP_MISSED" % ticks)
    L.append("execute if score #beats deusex matches %d run say BEATS_RAN_%d" % (len(BEATS), len(BEATS)))
    L.append("execute unless score #beats deusex matches %d run say BEATS_COUNT_%d"
             % (len(BEATS), len(BEATS)))
    L.append("execute if score #ostage deusex matches 4 run say LIVE_STAGE_DONE")
    L.append("execute unless score #ostage deusex matches 4 run say LIVE_STAGE_STUCK")
    L.append("execute if score #flashes deusex matches 1.. run say LIVE_FLASH_FIRED")
    L.append("execute unless score #flashes deusex matches 1.. run say LIVE_FLASH_DEAD")
    L.append("execute unless score #wash deusex matches 1.. run say LIVE_VEIL_NEVER_RAISED")
    # ... and the two 1.0.31 latches above, answered once instead of per tick.
    L.append("execute unless score #sr deusex matches 1 run say LIVE_RAIN_NEVER_ARMED")
    # The walk stops 60 s into a song that runs four minutes, with #ostage 4 and the flash roll still
    # armed, so the right question at the end is not "did the rain go away" but "is the show still the
    # one that owns the sky". A flag that fell mid-song would leave the red sheet bound to rain the
    # pack never started - 1.0.18's bug - and leave halt nothing to clear.
    L.append("execute if score #rain deusex matches 1 run say LIVE_RAIN_UP_MID_SONG")
    L.append("execute unless score #rain deusex matches 1 run say LIVE_RAIN_DROPPED_MID_SONG")
    L.append("execute unless score #sv deusex matches 1 run say LIVE_BURST_VEIL_DEAD")
    # The complaint this port answers is "the sky is stay normal": a veil that only spikes and then
    # goes home is a blink, not a red sky. The floor has to be raised by the burst and the veil has
    # to still be sitting on it, at or above, when the walk ends.
    L.append("execute if score #washbase deusex matches 1.. run say LIVE_BASE_RAISED")
    L.append("execute unless score #washbase deusex matches 1.. run say LIVE_BASE_NEVER_SET")
    L.append("execute if score #wash deusex >= #washbase deusex if score #washbase deusex "
             "matches 1.. run say LIVE_VEIL_HELD")
    L.append("execute unless score #sheld deusex matches 1 run say LIVE_VEIL_NEVER_REACHED_FLOOR")
    L.append("execute if score #cu deusex matches 1 run say LIVE_CATCHUP_HEAD_SEEN")
    L.append("execute unless score #cu deusex matches 1 run say LIVE_CATCHUP_NO_HEAD")
    L.append("say ---LIVE-TICK-DONE")


def main():
    rows = M.load_lyrics()
    t0, n0 = rows[0][0], rows[1][0]
    a, b = int(round(t0 * 20)), int(round(n0 * 20)) - 1

    L = ["reload", "say ---AFTER-RELOAD", "forceload add -96 -96 96 96",
         "function deusex:lyrics_init",
         "data modify storage deusex:lyrics list set from storage deusex:lyrics list",
         "execute store result score #nlist deusex run data get storage deusex:lyrics list",
         "say LIST_SIZE",
         "execute if score #nlist deusex matches 444 run say LIST_IS_444",
         "execute unless score #nlist deusex matches 444 run say LIST_BAD",
         "execute if score #drop deusex matches %d run say DROP_%d_OK" % (DROP, DROP),
         "execute unless score #drop deusex matches %d run say DROP_BAD" % DROP,
         "execute if score #rainlead deusex matches %d run say RAINLEAD_%d_OK" % (RAINLEAD, RAINLEAD),
         "execute unless score #rainlead deusex matches %d run say RAINLEAD_BAD" % RAINLEAD,
         "execute if score #8 deusex matches 8 run say CONST8_OK",
         "execute unless score #8 deusex matches 8 run say CONST8_BAD",
         "execute if score #6 deusex matches 6 run say CONST6_OK",
         # load guards #lead rather than setting it, so a reload in the middle of a hold keeps the
         # countdown that is already running. All this can prove is that the score exists and is
         # inside the window, which is the part a missing constant would break.
         "execute unless score #lead deusex = #lead deusex run say LEAD_UNSET",
         "execute if score #lead deusex = #lead deusex if score #lead deusex matches 0..%d "
         "run say LEAD_IN_WINDOW" % LEAD,
         "execute if score #lead deusex = #lead deusex unless score #lead deusex matches 0..%d "
         "run say LEAD_OUT_OF_WINDOW" % LEAD,
         "execute if score #washmax deusex matches %d run say WASHMAX_OK" % WASHMAX,
         "execute if score #tint deusex matches %d run say TINT_EQ_WASHMAX" % WASHMAX,
         "execute unless score #tint deusex matches %d run say TINT_BAD" % WASHMAX]

    # The pack paints vanilla's rain red, so the only thing that keeps a plain rainy afternoon from
    # looking like the event is owning the weather: load.mcfunction turns the world's own cycle off, and
    # tick clears the sky on the one tick a show let go of it raining. 1.21.1 cannot read the weather
    # back out of a command - `execute if predicate` is the only spelling that tries, and it throws for
    # every source this pack runs from (soak38, gate_probe.log: console, function, positioned, inline
    # JSON all answer "An unexpected error occurred trying to execute that command") - so the proof runs
    # through the flag and the log instead: the first idle tick spends #rain and prints exactly one
    # weather line, the second idle tick prints none, a song tick leaves the flag up, and halt takes the
    # flag down with its own clear.
    L.append("say ---WEATHER-GATE")
    L.append("function deusex:load")
    L.append("execute store result score #wcq deusex run gamerule doWeatherCycle")
    L.append("execute if score #wcq deusex matches 0 run say CYCLE_OFF")
    L.append("execute unless score #wcq deusex matches 0 run say CYCLE_RUNNING")
    L.append("execute unless score #rain deusex = #rain deusex run say RAIN_FLAG_UNSET")
    L.append("scoreboard players set #state deusex 0")
    L.append("scoreboard players set #ostage deusex 0")
    L.append("scoreboard players set #cstate deusex 0")
    L.append("weather rain 1000000")
    L.append("scoreboard players set #rain deusex 1")
    L.append("say GATE_T1_BEGIN")
    L.append("function deusex:tick")
    L.append("say GATE_T1_END")
    L.append("execute if score #rain deusex matches 0 run say GATE_IDLE_DISARMED")
    L.append("execute if score #rain deusex matches 1 run say GATE_IDLE_KEPT")
    L.append("say GATE_T2_BEGIN")
    L.append("function deusex:tick")
    L.append("say GATE_T2_END")
    # The song's own tick has to leave the rain alone: the red sheet is the colour of the whole opening,
    # and a gate that ate it would take the sky back to plain Minecraft mid-show.
    L.append("scoreboard players set #rain deusex 1")
    L.append("scoreboard players set #state deusex 1")
    L.append("say GATE_T3_BEGIN")
    L.append("function deusex:tick")
    L.append("say GATE_T3_END")
    L.append("execute if score #rain deusex matches 1 run say GATE_SONG_KEPT")
    L.append("execute unless score #rain deusex matches 1 run say GATE_ATE_SONG_RAIN")
    # halt is the exit that clears the weather itself, so it has to take the flag with it - otherwise
    # the tick gate re-claims the sky every idle tick after a stop.
    L.append("function deusex:halt")
    L.append("execute if score #rain deusex matches 0 run say HALT_DISARMED")
    L.append("execute if score #rain deusex matches 1 run say HALT_LEFT_FLAG")
    L.append("weather clear")

    # The two exit paths the panel cleanup used to strangle. Both functions start with a bare
    # `kill @e[type=minecraft:text_display,tag=deusex_flash]`, which throws whenever the sky holds no
    # panel - and it usually holds none, because flash_frame kills the set at #fframe 0 - so every
    # line under it was dead code: finish never reached closing_start (the song ended with the veil at
    # full strength and the world still raining the pack's own red), and do_pause never wrote
    # #fframe 0 (a paused show resumed into a half-dead envelope). Now the cleanup is guarded and
    # last, so what is left below it can only be reached. The headless source cannot resolve any `@e`
    # selector at all, so the trailing kill still throws here - and that is the point: it throws on
    # the last line, where throwing costs nothing, while the state writes above it run for real.
    L.append("say ---EXIT-PATHS")
    L.append("say FIN_BEGIN")
    L.append("weather rain 1000000")
    L.append("scoreboard players set #rain deusex 1")
    L.append("scoreboard players set #state deusex 1")
    L.append("scoreboard players set #cstate deusex 0")
    L.append("scoreboard players set #idx deusex 999")
    L.append("function deusex:finish")
    L.append("say FIN_END")
    L.append("execute if score #cstate deusex matches 1 run say FIN_ENDING_STARTED")
    L.append("execute unless score #cstate deusex matches 1 run say FIN_ENDING_NEVER_STARTED")
    L.append("execute if score #rain deusex matches 0 run say FIN_RAIN_DOWN")
    L.append("execute if score #rain deusex matches 1 run say FIN_RAIN_UP")
    L.append("execute if score #state deusex matches 0 run say FIN_STATE_IDLE")
    L.append("execute if score #idx deusex matches 0 run say FIN_INDEX_RESET")
    L.append("execute if score #wash deusex matches 16 run say FIN_VEIL_AT_FULL")
    L.append("function deusex:halt")
    L.append("scoreboard players set #fframe deusex 11")
    L.append("say PAUSE_BEGIN")
    L.append("function deusex:do_pause")
    L.append("say PAUSE_END")
    L.append("execute if score #fframe deusex matches 0 run say PAUSE_ENVELOPE_STOPPED")
    L.append("execute unless score #fframe deusex matches 0 run say PAUSE_ENVELOPE_KEPT")
    L.append("execute if score #state deusex matches 2 run say PAUSE_IS_PAUSED")
    L.append("function deusex:halt")

    L.append("say ---FREEZE")
    L.append("tick freeze")
    live_tick(L, 1200)
    L.append("say ---REPORT")
    # #panels is poisoned first because selftest's second line is what writes it: a tellraw that
    # throws with nobody online would stop the report after one line, and the player would get a
    # half answer and no way to tell me which one.
    L.append("scoreboard players set #panels deusex -777")
    L.append("function deusex:selftest")
    L.append("execute if score #panels deusex matches -777 run say REPORT_DIED_EARLY")
    L.append("execute unless score #panels deusex matches -777 run say REPORT_RAN")
    # the two force-commands, proved the only way a console can: by the state they leave behind.
    # Whether any of it reaches a screen is the question only a player can answer.
    L.append("function deusex:test_wash")
    L.append("execute if score #wash deusex matches %d run say TEST_WASH_ARMED" % WASH_TEST)
    L.append("execute unless score #wash deusex matches %d run say TEST_WASH_STUCK" % WASH_TEST)
    L.append("scoreboard players set #flashes deusex 0")
    L.append("scoreboard players set #wash deusex 0")
    L.append("function deusex:test_flash")
    L.append("execute if score #flashes deusex matches 1 run say TEST_FLASH_COUNTED")
    L.append("execute unless score #flashes deusex matches 1 run say TEST_FLASH_NOT_COUNTED")
    L.append("execute if score #wash deusex matches %d run say TEST_FLASH_RAISED_VEIL" % WASHMAX)
    L.append("execute unless score #wash deusex matches %d run say TEST_FLASH_NO_VEIL" % WASHMAX)
    L.append("execute if score #fframe deusex matches %d run say TEST_FLASH_ARMED_ENVELOPE" % FFRAME)
    L.append("say ---REPORT-DONE")

    L.append("say ---BEAT-SCHEDULE")
    L.append("scoreboard players set #hb deusex 99")
    for E in range(0, 401):
        L.append("scoreboard players set #E deusex %d" % E)
        L.append("function deusex:opening_hb")
        L.append("execute if score #hb deusex matches 1 run say BEAT_AT_%d" % E)
    # Nothing may still be thumping on the drop tick or after it. heartbeat.ogg runs to about
    # tick 21.8, so the window is the drop plus the length of one dub.
    L.append("say ---BEATS-STOP-BEFORE-DROP")
    for E in range(DROP, DROP + 25):
        L.append("scoreboard players set #hb deusex 99")
        L.append("scoreboard players set #E deusex %d" % E)
        L.append("function deusex:opening_hb")
        L.append("execute if score #hb deusex matches 1 run say LATE_BEAT_AT_%d" % E)
    L.append("say ---BEAT-DONE")

    L.append("say ---LEAD-IN prewarm=0 track=%d hand-over=%d" % (LEAD - FIRE, LEAD))
    clock_start(L, 1)
    for tick in range(LEAD + 8):
        one_tick(L, tick, "GAPLESS")
    L.append("execute if score #lead deusex matches 0 run say LEAD_COUNTED_DOWN")
    L.append("execute unless score #lead deusex matches 0 run say LEAD_STUCK")
    # The clock starts on tick LEAD, the first tick whose #lead is 0, so the eight calls after it
    # leave #t at exactly 8. Anything else is a double step, which is what a live tick used to do
    # here when the two dispatch lines were in the other order.
    L.append("execute if score #t deusex matches %d run say CLOCK_MOVED_ONCE" % 8)
    L.append("execute unless score #t deusex matches %d run say CLOCK_DRIFTED" % 8)
    L.append("say ---CHUNKED-RESUME (no hold, chunk heads must fire)")
    clock_start(L, 0)
    for tick in range(4):
        one_tick(L, tick, "CHUNKED")
    L.append("say ---LOOP-REARM")
    L.append("scoreboard players set #idx deusex %d" % LAST)
    L.append("scoreboard players set #t deusex 59")
    L.append("scoreboard players set #full deusex 1")
    L.append("scoreboard players set #loop deusex 1")
    L.append("scoreboard players set #lead deusex 0")
    L.append("function deusex:next_chunk")
    L.append("execute if score #idx deusex matches 0 if score #lead deusex matches %d "
             "run say LOOP_REARM_OK" % LEAD)
    L.append("execute unless score #idx deusex matches 0 run say LOOP_NO_WRAP")
    L.append("execute if score #idx deusex matches 0 unless score #lead deusex matches %d "
             "run say LOOP_NO_LEADIN" % LEAD)
    probe(L, "lp", [("idx", "#idx"), ("t", "#t"), ("lead", "#lead")])
    L.append("say ---CLOCK-DONE")

    L.append("say ---LYRIC-FADE line0 window %d..%d" % (a, b))
    L.append("scoreboard players set #li deusex -1")
    for E in range(a - 2, b + 3):
        L.append("scoreboard players set #E deusex %d" % E)
        L.append("function deusex:lyric_tick")
        L.append("data get storage deusex:data i")
    L.append("say ---FADE-DONE")

    # The rain, walked through the gate that arms it. opening_tick recomputes #E from #idx and #t on
    # its first three lines, so a walk that writes #E by hand is overwritten before the gate reads it
    # - this sets the chunk index and the in-chunk tick and lets the function do its own arithmetic,
    # which also proves the clock it gates on is the one the song runs. Four ticks: one before the
    # lead (dry), the lead itself (wet), the tick after (must not re-fire: the log between
    # RAIN_T<n>_BEGIN and _END carries the weather line exactly once) and the drop, where
    # opening_burst runs and finds the sky already raining.
    L.append("say ---RAIN-LEAD armed at #E %d, %d ticks ahead of the drop" % (RAINLEAD, RAIN_AHEAD))
    L.append("weather clear")
    L.append("scoreboard players set #rain deusex 0")
    L.append("scoreboard players set #state deusex 1")
    L.append("scoreboard players set #ostage deusex 2")
    L.append("scoreboard players set #wash deusex 0")
    L.append("scoreboard players set #washbase deusex 0")
    L.append("scoreboard players set #washc deusex 0")
    L.append("scoreboard players set #wlast deusex 0")
    for E, want in ((RAINLEAD - 1, 0), (RAINLEAD, 1), (RAINLEAD + 1, 1), (DROP, 1)):
        L.append("scoreboard players set #idx deusex %d" % (E // 60))
        L.append("scoreboard players set #t deusex %d" % (E % 60))
        L.append("say RAIN_T%d_BEGIN" % E)
        L.append("function deusex:opening_tick")
        L.append("say RAIN_T%d_END" % E)
        L.append("execute if score #E deusex matches %d run say CLOCK_%d_OK" % (E, E))
        L.append("execute unless score #E deusex matches %d run say CLOCK_%d_BAD" % (E, E))
        L.append("execute if score #rain deusex matches %d run say RAIN_FLAG_%d_AS_EXPECTED" % (want, E))
        L.append("execute unless score #rain deusex matches %d run say RAIN_FLAG_%d_WRONG" % (want, E))
    L.append("execute if score #ostage deusex matches 3 run say LEAD_BURST_FIRED")
    L.append("execute unless score #ostage deusex matches 3 run say LEAD_BURST_MISSING")
    L.append("execute unless score #washbase deusex matches %d run say LEAD_FLOOR_BAD" % WASHBASE)
    L.append("execute if score #rain deusex matches 1 run say RAIN_UP_AT_BURST")
    L.append("execute unless score #rain deusex matches 1 run say RAIN_DRY_AT_BURST")

    # The drop, tick by tick, with the veil in the same walk. opening_flash paces the burst against
    # #k = #E - #drop and hands the frame index to heart_burst_frame, so #gl == 1 every tick proves
    # the shipped glyph table always selected a character rather than leaving the macro string empty.
    # Since 1.0.31 the same function also picks the wash cell and emits it in that one title string,
    # which is the whole of "the rain and the red overlay were a bit delayed": #wash is ramped here in
    # tick.mcfunction's own order - opening_flash first (line 35's dispatch), wash_tick after (line 41)
    # - so the drop tick is lv 0 by design, the blast is a white-out there, and the red has to arrive
    # one level a tick through the decay. A blind tick is the delay back; a level that falls or jumps
    # is a step on the screen.
    L.append("say ---BURST-PACING drop=%d, %d ticks, floor %d" % (DROP, BURST_K, WASHBASE))
    L.append("scoreboard players set #ostage deusex 3")
    L.append("scoreboard players set #plv deusex 0")
    for k in range(0, BURST_K + 1):
        if k:
            L.append("function deusex:wash_tick")
        L.append("scoreboard players set #E deusex %d" % (DROP + k))
        L.append("data modify storage deusex:data rc set value %s" % SENTINEL)
        L.append("function deusex:opening_flash")
        L.append("execute if %s run say BURST_BLIND_%d" % (NOT_PAINTED, k))
        L.append("execute unless score #lv deusex matches %d run say BURST_LEVEL_OFF_%d"
                 % (min(k, WASHBASE), k))
        L.append("execute if score #lv deusex < #plv deusex run say BURST_LEVEL_FELL_%d" % k)
        L.append("execute store result score #plv deusex run scoreboard players get #lv deusex")
        L.append("execute store result score #glen deusex run "
                 "data get storage deusex:data burst")
        probe(L, "burst", [("k", "#k"), ("bf", "#bf"), ("os", "#ostage"), ("gl", "#glen"),
                           ("wash", "#wash"), ("lv", "#lv")])
    L.append("execute if score #ostage deusex matches 4 run say BURST_RESET_OK")
    L.append("execute unless score #ostage deusex matches 4 run say BURST_STUCK")
    # The hand-over, on the tick after the reset. opening_done took the title away and #wlast with it;
    # wash_draw is the only thing left that can paint, and it paints only when the level *changes* -
    # which is exactly the trap this walk is here for, because the level has not changed since the
    # burst. Same cell, on screen again, in the same tick: that is what "seamless" means here.
    L.append("say ---HANDOVER")
    L.append("execute if score #wlast deusex matches -1 run say HANDOVER_GATE_OPEN")
    L.append("execute unless score #wlast deusex matches -1 run say HANDOVER_GATE_STUCK")
    L.append("data modify storage deusex:data rc set value %s" % SENTINEL)
    L.append("function deusex:wash_draw")
    L.append("execute unless %s run say HANDOVER_REPAINTED" % NOT_PAINTED)
    L.append("execute if %s run say HANDOVER_PLAIN_SCREEN" % NOT_PAINTED)
    L.append("execute if score #lv deusex = #plv deusex run say HANDOVER_SAME_CELL")
    L.append("execute unless score #lv deusex = #plv deusex run say HANDOVER_STEPPED")
    L.append("execute unless score #wlast deusex matches %d run say HANDOVER_FLOOR_BAD" % WASHBASE)
    L.append("weather clear")
    L.append("scoreboard players set #rain deusex 0")
    L.append("scoreboard players set #ostage deusex 0")
    L.append("say ---BURST-DONE")

    # The delay is computed by a wrapped LCG so the headless soak can prove it, but note what the
    # soak still cannot reach: flash_begin's last two lines (`kill @e`, `execute as @a`) and every
    # summon in flash_spawn need a level, and the console source has none, so they throw here and
    # are verified only in the rendered model. The scoreboard arithmetic before them is what runs -
    # which is also why the veil below raises #wash by hand instead of through flash_begin.
    L.append("say ---FLASH-DELAYS")
    L.append("scoreboard players set #lcg deusex 0")
    for i in range(12):
        L.append("function deusex:flash_begin")
        L.append("execute if score #flashd deusex matches 160..420 run say D%d_IN_RANGE" % i)
        L.append("execute unless score #flashd deusex matches 160..420 run say D%d_BAD" % i)
        L.append("execute store result score #ff0 deusex run scoreboard players get #fframe deusex")
        L.append("execute if score #ff0 deusex matches %d run say D%d_ARMED" % (FFRAME, i))
    L.append("say ---FLASH-ENVELOPE %d ticks counting down" % FFRAME)
    L.append("scoreboard players set #fframe deusex 0")
    L.append("scoreboard players set #flashd deusex 1")
    for t in range(0, 2 * FFRAME):
        L.append("function deusex:flash_tick")
        probe(L, "fl", [("ff", "#fframe"), ("fd", "#flashd")])
    L.append("execute if score #fframe deusex matches 0 run say FLASH_ENVELOPE_CLOSED")
    L.append("execute unless score #fframe deusex matches 0 run say FLASH_ENVELOPE_STUCK")
    L.append("say ---FLASH-DONE")

    # Drain rate first, then the paint walk, then the gate, then the ceiling. #washbase is pinned to
    # 0 here on purpose: this walk is the ending's, and a floor left over from the burst would stop
    # the drain short and make the walk prove nothing.
    L.append("say ---VEIL-DRAIN %d levels x %d ticks = %d ticks" % (WASHMAX, DRAIN, DRAIN * WASHMAX))
    L.append("scoreboard players set #washbase deusex 0")
    L.append("scoreboard players set #wash deusex %d" % WASHMAX)
    L.append("scoreboard players set #washc deusex 0")
    for step in range(WASHMAX):
        hold = WASHMAX - step
        for call in range(1, DRAIN):
            L.append("function deusex:wash_tick")
            L.append("execute unless score #wash deusex matches %d run say EARLY_DRAIN_%d_AT_%d"
                     % (hold, step, call))
        L.append("function deusex:wash_tick")
        L.append("execute if score #wash deusex matches %d run say DRAINED_TO_%d" % (hold - 1, step))
        L.append("execute unless score #wash deusex matches %d run say VEIL_DRIFT_%d"
                 % (hold - 1, step))
    L.append("execute if score #wash deusex matches 0 run say VEIL_CLEARED")
    L.append("execute unless score #wash deusex matches 0 run say VEIL_STUCK")
    L.append("execute if score #washc deusex matches 0 run say VEIL_COUNTER_RESET")
    L.append("execute unless score #washc deusex matches 0 run say VEIL_COUNTER_LEFT")
    probe(L, "wd", [("wash", "#wash"), ("washc", "#washc")])

    L.append("say ---VEIL-PAINT-CELLS (one repaint per level, %d..0)" % WASHMAX)
    for level in range(WASHMAX, -1, -1):
        draw_once(L, level)
    L.append("execute if score #lv deusex matches 0 run say VEIL_CELL_0")

    # The gate: the same level twice must not restart the title, or every player gets a title
    # packet twenty times a second and the veil flickers instead of fading.
    L.append("say ---VEIL-GATE-HOLD")
    L.append("scoreboard players set #wash deusex %d" % WASHMAX)
    L.append("scoreboard players set #wlast deusex -1")
    L.append("data modify storage deusex:data rc set value %s" % SENTINEL)
    L.append("function deusex:wash_draw")
    L.append("execute unless %s run say GATE_OPENED" % NOT_PAINTED)
    L.append("data modify storage deusex:data rc set value %s" % SENTINEL)
    L.append("function deusex:wash_draw")
    L.append("execute if %s run say GATE_HELD" % NOT_PAINTED)
    L.append("execute unless %s run say GATE_REPAINTED_SAME_LEVEL" % NOT_PAINTED)

    # Above the ceiling wash_tick clamps #wash before the next draw, so lv_char is never asked for
    # a cell the font does not have - a missing glyph over the whole screen is how 1.0.16 failed.
    L.append("say ---VEIL-CEILING")
    L.append("scoreboard players set #wash deusex 99")
    L.append("scoreboard players set #washc deusex 0")
    L.append("scoreboard players set #wlast deusex -1")
    L.append("function deusex:wash_tick")
    L.append("execute if score #wash deusex matches %d run say CEILING_CLAMPED" % WASHMAX)
    L.append("execute unless score #wash deusex matches %d run say CEILING_NOT_CLAMPED" % WASHMAX)
    L.append("data modify storage deusex:data rc set value %s" % SENTINEL)
    L.append("function deusex:wash_draw")
    L.append("execute unless score #lv deusex matches %d run say CEILING_CELL_WRONG" % WASHMAX)
    L.append("execute if score #lv deusex matches %d run say CEILING_CELL_OK" % WASHMAX)

    # The floor, in both directions, which is the whole of "the sky is red and stays red". A drain
    # that runs past #washbase is a blink; a ramp that never starts is a burst that sets the floor
    # and leaves the screen plain, which is what the old `if #wash matches 1..` gate guaranteed.
    L.append("say ---VEIL-BASE floor %d" % WASHBASE)
    L.append("scoreboard players set #washbase deusex %d" % WASHBASE)
    L.append("scoreboard players set #wash deusex %d" % WASHMAX)
    L.append("scoreboard players set #washc deusex 0")
    for call in range(DRAIN * (WASHMAX - WASHBASE) + 12):
        L.append("function deusex:wash_tick")
        L.append("execute if score #wash deusex < #washbase deusex run say FLOOR_BROKEN_%d" % call)
    L.append("execute if score #wash deusex matches %d run say FLOOR_HELD" % WASHBASE)
    L.append("execute unless score #wash deusex matches %d run say FLOOR_NOT_HELD" % WASHBASE)
    L.append("scoreboard players set #wash deusex 0")
    L.append("scoreboard players set #washc deusex 0")
    for call in range(WASHBASE):
        L.append("function deusex:wash_tick")
        L.append("execute if score #wash deusex matches %d run say RAMP_%d" % (call + 1, call))
        L.append("execute unless score #wash deusex matches %d run say RAMP_DRIFT_%d"
                 % (call + 1, call))
    L.append("function deusex:wash_tick")
    L.append("execute if score #wash deusex matches %d run say RAMP_HELD" % WASHBASE)
    L.append("execute unless score #wash deusex matches %d run say RAMP_PAST_FLOOR" % WASHBASE)
    L.append("say ---VEIL-DONE")

    L.append("tick resume")
    L.append("stop")

    with open(os.path.join(SRV, "cmds.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    print("cmds.txt lines", len(L))
    print("expected BEAT_AT lines:", sorted(DROP + o for o in BEATS),
          "(last beat %+d, silent from tick %d)" % (BEATS[-1], DROP + BEATS[-1] + 22))
    print("expected LATE_BEAT lines: none (the drop is #E %d)" % DROP)
    print("expected *_FIRE lines: GAPLESS_FIRE_%d only, plus CHUNKED_FIRE_0 "
          "(prewarm on arm, track %d ticks later, clock on tick %d, song %d ticks of #E)"
          % (LEAD - FIRE, LEAD - FIRE, LEAD, LAST * 60 + LASTLEN))
    print("expected DRAINED_TO lines: %d (one per %d wash_tick calls)" % (WASHMAX, DRAIN))
    print("expected FLOOR/RAMP: no FLOOR_BROKEN, FLOOR_HELD once, RAMP_0..%d then RAMP_HELD "
          "(floor %d, ceiling %d)" % (WASHBASE - 1, WASHBASE, WASHMAX))
    print("expected REPAINT lines: %d (%d down to 0), NO_REPAINT lines: none, GATE_HELD once"
          % (WASHMAX + 1, WASHMAX))
    print("expected WEATHER-GATE: CYCLE_OFF, GATE_IDLE_DISARMED, GATE_SONG_KEPT and HALT_DISARMED once "
          "each; CYCLE_RUNNING, RAIN_FLAG_UNSET, GATE_IDLE_KEPT, GATE_ATE_SONG_RAIN and HALT_LEFT_FLAG "
          "never. The section still prints one 'An unexpected error' line per function that ends on its "
          "panel cleanup (load, halt): the soak's console source has no level, so it cannot resolve any "
          "@e selector, guarded or not. That is the shape the fix is about - the throw now happens on "
          "the last line of the file, where there is nothing left to strand.")
    print("expected WEATHER-GATE weather lines: exactly one between GATE_T1_BEGIN and GATE_T1_END, none "
          "between GATE_T2_BEGIN/GATE_T2_END or GATE_T3_BEGIN/GATE_T3_END (an idle show that never "
          "disarms would print 'Nothing changed' twenty times a second)")
    print("expected EXIT-PATHS: FIN_ENDING_STARTED, FIN_RAIN_DOWN, FIN_STATE_IDLE, FIN_INDEX_RESET, "
          "FIN_VEIL_AT_FULL, PAUSE_ENVELOPE_STOPPED and PAUSE_IS_PAUSED once each; "
          "FIN_ENDING_NEVER_STARTED, FIN_RAIN_UP, PAUSE_ENVELOPE_KEPT never - those three are the "
          "ending and the pause that a panel kill with nothing to kill used to switch off")
    print("expected RAIN-LEAD: RAINLEAD_%d_OK, CLOCK_%d_OK for each of #E %s, RAIN_FLAG_<E>_AS_EXPECTED "
          "for all four, RAIN_UP_AT_BURST and LEAD_BURST_FIRED; RAIN_DRY_AT_BURST, LEAD_FLOOR_BAD and "
          "every RAIN_FLAG_*_WRONG never. Note what the markers cannot show: the server only echoes the "
          "command it was handed, so opening_rain's own `weather rain` prints no line from inside "
          "opening_tick (soak43 brackets the tick the flag moved and nothing else). That the storm is "
          "armed exactly once is validate_assets.py's replay of the gate over #E 0..#drop+30."
          % (RAINLEAD, RAINLEAD, [RAINLEAD - 1, RAINLEAD, RAINLEAD + 1, DROP]))
    print("expected BURST-WASH: %d BURST_BLIND, BURST_LEVEL_OFF or BURST_LEVEL_FELL lines, and "
          "burst probes whose lv reads 0,1,2..%d,14,14 (the drop tick is lv 0 on purpose: the blast "
          "is a white-out there and wash_tick runs after opening_flash, exactly as in tick.mcfunction)"
          % (0, WASHBASE - 1))
    print("expected HANDOVER: HANDOVER_GATE_OPEN, HANDOVER_REPAINTED and HANDOVER_SAME_CELL once each; "
          "HANDOVER_GATE_STUCK, HANDOVER_PLAIN_SCREEN and HANDOVER_STEPPED never. Plain screen is the "
          "regression this whole section is here for: the reset takes the veil with it and wash_draw "
          "will not repaint a level it thinks it already painted.")
    print("expected LIVE-TICK: BURST_WET, BURST_VEIL_AT_<t> with t past STAGE3_AT and "
          "LIVE_RAIN_UP_MID_SONG once each; LIVE_RAIN_DROPPED_MID_SONG, LIVE_RAIN_NEVER_ARMED, "
          "BURST_DRY, LIVE_BURST_VEIL_DEAD never. The live walk ends 60 s into a four minute song, so "
          "the rain flag being up when it ends is the pass: the pack still owns the sky. Handing the "
          "weather back is what FIN_RAIN_DOWN and the HANDOVER walk check.")
    print("expected CATCH-UP: CATCHUP_HEAD_AT_<t> and CATCHUP_IDX_OK once each, LIVE_CATCHUP_HEAD_SEEN "
          "at the end; CATCHUP_IDX_WRONG and LIVE_CATCHUP_NO_HEAD never, and no 'unexpected error' "
          "from catchup_macro - an empty @a[tag] must run the macro zero times, not throw. The tag "
          "itself needs a player, so warm_tick's tag line and run_playing's gate are shape rules in "
          "validate_assets.py; the head this probe lands on is the same 60 tick grid the clock "
          "replay counts.")


if __name__ == "__main__":
    sync()
    main()
