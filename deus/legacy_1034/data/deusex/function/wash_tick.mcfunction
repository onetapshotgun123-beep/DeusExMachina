# The veil drains one level every 4 ticks, but only down to #washbase - the level the sky holds for
# the whole song - and climbs back up to it one level per tick whenever a flash's spike has drained
# away. #washmax 17 down to #washbase 14 is 3 levels, so a blink runs 12 ticks (0.6 s) inside the 22
# tick panel it is timed against: the sky flares bright red, settles back to the red it never left,
# and the glow that carries on after it is the panel, not the wash. Before 1.0.30 the floor was 6,
# so a blink spent 40 ticks falling to nearly plain - dramatic, and the wrong picture: the user's
# screenshot of the running event measured its sky at a red-minus-blue of +8 (lavender) and asked
# for it to look reddish.
# closing_start drops #washbase to 0 so that same drain goes all the way home: the 68 tick fade out
# IS the transition back to plain Minecraft.
# flash_begin raises #wash for the sky flash and closing_start raises it for the ending, so this is
# the only decay either one needs. tick.mcfunction calls it while the song plays and closing_tick
# calls it while the ending plays - #state is already 0 by then, so the old `if #state 1` gate left
# #wash stuck at full red for the whole ending, and closing_tail waits on #wash 0 before it will run
# closing_end. The screen never came back.
scoreboard players add #washc deusex 1
execute if score #washc deusex matches 4.. if score #wash deusex > #washbase deusex run scoreboard players remove #wash deusex 1
execute if score #washc deusex matches 4.. run scoreboard players set #washc deusex 0
# 1.0.18's sky_tick walked #sky up to #skymax one level per tick. Same rate here, so the held red is
# on screen 14 ticks after the burst raises the floor - inside the explosion, not after it.
execute if score #wash deusex < #washbase deusex run scoreboard players add #wash deusex 1
execute if score #wash deusex > #washmax deusex run scoreboard players operation #wash deusex = #washmax deusex
