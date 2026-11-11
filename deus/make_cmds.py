"""Generate srvtest/cmds_reset.txt + srvtest/cmds.txt for the 1.1.0 shim soak, and sync the
datapack mirror.

The show moved into the client mod, so the vanilla 1.21.1 server can only exercise what the
datapack still owns: the deusex: command bridge and the weather-cycle rule. This walks exactly
that, on the real server, in two launches (scores persist in the world, and the load tag only
defaults scores that are unset):

  * reset run: remove the objective and stop, so the next launch starts like a fresh world;
  * main run: the startup load tag (ServerFunctionManager.tick runs it before console input) must
    recreate the objective, default #state/#pos/#loop/#cmd/#tk to 0, and leave doWeatherCycle ON
    (the orchestrator forces rain only mid-show and restores it after; the pack must not own the
    cycle any more, which is the bug a friend reported against the texture-override builds);
  * each command function sets the #cmd code the orchestrator switches on (start 1, pause 2,
    resume 3, stop 4, loop 5) and nothing else - no /playsound, /title, /weather, /kill;
  * tick advances #tk once per call and touches no other score;
  * selftest runs without throwing on an empty server (its tellraw texts need a player, so the
    harness only proves the function executes clean; the strings are checked in the jar source).

Note: /reload does NOT rerun the load tag in 1.21.1 (MinecraftServer.reloadResources only swaps
the function library; ServerFunctionManager.tick fires the tag on the next tick), which is why
the defaults are proven at startup instead.

The orchestrator itself (clock, freeze, weather force/restore, payloads) is Java and is verified
on the NeoForge dev server / real client, not here - a vanilla server has no mod to poll #cmd.
"""
import os
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
SRV = os.path.join(ROOT, "srvtest")
DP = os.path.join(SRV, "world", "datapacks", "deusex", "data")
FUN = os.path.join(ROOT, "extracted", "data", "deusex", "function")


def sync():
    if os.path.isdir(DP):
        shutil.rmtree(DP)
    shutil.copytree(os.path.join(ROOT, "extracted", "data"), DP)
    print("datapack synced ->", DP)


def shipped(name):
    return open(os.path.join(FUN, name + ".mcfunction"), encoding="utf-8").read()


def write(name, L):
    path = os.path.join(SRV, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    print(name, "lines", len(L))


def main():
    # Launch 1: clear the persisted scores so launch 2 starts like a fresh world. Harmless error
    # ("Unknown scoreboard objective") if the world never had the pack.
    write("cmds_reset.txt", ["scoreboard objectives remove deusex", "stop"])

    L = []
    # The startup load tag has already run by the time console input is drained, so these read
    # what load itself wrote.
    L.append("say ---AFTER-LOAD")
    L.append("execute if score #state deusex matches 0 run say STATE_DEFAULT_0")
    L.append("execute unless score #state deusex matches 0 run say STATE_NOT_DEFAULT")
    L.append("execute if score #cmd deusex matches 0 run say CMD_DEFAULT_0")
    L.append("execute if score #loop deusex matches 0 run say LOOP_DEFAULT_0")
    L.append("execute if score #pos deusex matches 0 run say POS_DEFAULT_0")
    # the weather cycle is left ON - query the gamerule
    L.append("gamerule doWeatherCycle")
    L.append("say ---WEATHER-QUERY (expect true)")
    # the shim functions exist and only set their bridge code
    for fn, code in (("start", 1), ("pause", 2), ("resume", 3), ("stop", 4), ("loop", 5)):
        L.append("scoreboard players set #cmd deusex 0")
        L.append("function deusex:%s" % fn)
        L.append("execute if score #cmd deusex matches %d run say CMD_%s_%d_OK" % (code, fn.upper(), code))
        L.append("execute unless score #cmd deusex matches %d run say CMD_%s_BAD" % (code, fn.upper()))
    # tick advances #tk by exactly one and leaves the bridge alone
    L.append("scoreboard players set #tk deusex 0")
    L.append("scoreboard players set #cmd deusex 0")
    L.append("function deusex:tick")
    L.append("execute if score #tk deusex matches 1 run say TICK_ONCE_OK")
    L.append("execute unless score #tk deusex matches 1 run say TICK_NOT_ONCE")
    L.append("execute if score #cmd deusex matches 0 run say TICK_LEFT_CMD_OK")
    L.append("function deusex:tick")
    L.append("execute if score #tk deusex matches 2 run say TICK_TWICE_OK")
    # selftest must not throw on an empty server (no players, no entities)
    L.append("function deusex:selftest")
    L.append("say ---SELFTEST-RAN (expect no error; tellraw needs a player, source is checked in the jar)")
    # the shim ships no show commands: grep is the validator's job, but prove the functions load
    L.append("say ---SHIM-SOAK-DONE")
    L.append("stop")

    with open(os.path.join(SRV, "cmds.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    print("cmds.txt lines", len(L))
    print("expected: STATE_DEFAULT_0, CMD_DEFAULT_0, LOOP_DEFAULT_0, POS_DEFAULT_0; "
          "doWeatherCycle=true; CMD_START_1_OK, CMD_PAUSE_2_OK, CMD_RESUME_3_OK, CMD_STOP_4_OK, "
          "CMD_LOOP_5_OK; TICK_ONCE_OK, TICK_LEFT_CMD_OK, TICK_TWICE_OK; selftest ran clean; "
          "no *_BAD, no *_NOT_*, no 'An unexpected error', no 'Unknown function'")


if __name__ == "__main__":
    sync()
    main()