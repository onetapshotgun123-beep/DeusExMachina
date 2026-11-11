# Deus Ex Machina 1.1.0 - command shim.
#
# The whole show (audio, timeline, lyrics, heart, wash, sky, rain) lives in the client mod now.
# This datapack only owns the scoreboard bridge the server orchestrator polls: it creates the
# objective, defaults the mirrored scores, and leaves the world's own weather cycle ON so a plain
# rainy day stays plain. The orchestrator forces rain only while the show runs and restores whatever
# was falling before it started.
scoreboard objectives add deusex dummy
execute unless score #state deusex = #state deusex run scoreboard players set #state deusex 0
execute unless score #pos deusex = #pos deusex run scoreboard players set #pos deusex 0
execute unless score #loop deusex = #loop deusex run scoreboard players set #loop deusex 0
execute unless score #cmd deusex = #cmd deusex run scoreboard players set #cmd deusex 0
execute unless score #tk deusex = #tk deusex run scoreboard players set #tk deusex 0
gamerule doWeatherCycle true