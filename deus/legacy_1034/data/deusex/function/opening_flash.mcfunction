# k is the tick count since #drop. The wavefront has to be *ahead* of the ear, so the frames
# run fast off the mark (two ticks on the white flash, then three ticks per frame) and the whole
# explosion is over 1.5 s after the hit rather than dissolving for 2.75 s like the old table did.
scoreboard players operation #k deusex = #E deusex
scoreboard players operation #k deusex -= #drop deusex
scoreboard players set #bf deusex 0
execute if score #k deusex matches 1 run scoreboard players set #bf deusex 1
execute if score #k deusex matches 2.. run scoreboard players operation #bf deusex = #k deusex
execute if score #k deusex matches 2.. run scoreboard players remove #bf deusex 2
execute if score #k deusex matches 2.. run scoreboard players operation #bf deusex /= #3 deusex
execute if score #k deusex matches 2.. run scoreboard players add #bf deusex 2
execute if score #bf deusex matches 16.. run scoreboard players set #bf deusex 15
function deusex:heart_burst_frame
# The wash rides in the same string as the blast - see title_red_burst - so the level has to be worked
# out here too, and wash_level is the one place that maths lives. Before 1.0.31 this function drew the
# explosion and nothing else, and wash_draw did not run until #ostage 4, which opening_done only
# reaches on the tick below: the red sky arrived 50 ticks, 2.5 s, after the hit it is supposed to be
# part of. wash_tick is not gated on #ostage, so #wash has been climbing one level a tick since the
# burst raised #washbase, and this walks that into cells 1..14 over the first fourteen ticks of the
# blast - exactly while the white frame is decaying from 100% of the screen to 31%. The two curves
# cross in the middle: the explosion does not stop and the wash start, they hand over to each other.
function deusex:wash_level
function deusex:title_red_burst with storage deusex:data
# 50 ticks (2.5 s) after the hit the title is dropped entirely. Nothing is drawn over the world
# from here on, which is what makes it read as a cut to normal Minecraft instead of a fade into
# a permanent red wash.
execute if score #k deusex matches 50.. run function deusex:opening_done
