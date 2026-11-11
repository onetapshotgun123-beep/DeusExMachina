scoreboard players set #cstate deusex 1
scoreboard players set #ct deusex 0
# The ending opens on the same full strength a flash arms, so the collapse reads as the sky coming
# down over the whole screen and not as a tint. wash_tick then fades it one level every 4 ticks: 68
# ticks, 3.4 s, and closing_tail will not run closing_end - the title reset that hands the game back
# - until #wash is home at 0. That is the transition out of the mod, so the drain is the ending's
# real length and not something to rush.
scoreboard players operation #wash deusex = #washmax deusex
# The held level goes away first, so the drain below it has somewhere to end: wash_tick stops at
# #washbase, and closing_tail will not run closing_end until #wash is home at 0.
scoreboard players set #washbase deusex 0
scoreboard players set #washc deusex 0
weather clear
scoreboard players set #rain deusex 0
execute if score #ostage deusex matches 1..2 run function deusex:opening_abort
scoreboard players set #tfade deusex 0
execute if score #ostage deusex matches 3..4 run scoreboard players set #tfade deusex 1
scoreboard players set #ostage deusex 0
