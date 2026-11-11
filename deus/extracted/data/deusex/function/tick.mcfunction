# The orchestrator polls #cmd and mirrors #state/#pos/#loop on the server tick. This loop only
# counts ticks so selftest can prove the datapack side is alive; the show clock is the mod's.
scoreboard players add #tk deusex 1