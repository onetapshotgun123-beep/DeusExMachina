# #drop is 219 ticks of main_track.ogg (10.947 s, the song's real drop) and, since run_lead, 219 ticks
# of the audio the player is actually hearing - so this is the tick the slam lands on.
execute as @a at @s run playsound deusex:boom master @s ~ ~ ~ 1 1 1
# heartbeat.ogg is a lub at 0.00 and a dub 17.4 ticks later, audible to tick 21.8, so a beat fired
# on the way down is still thumping over the explosion. Name the event and cut it, instead of
# trusting the table to have stopped far enough ahead.
execute as @a run stopsound @s master deusex:heartbeat
execute as @a[tag=deusex_frozen] run function deusex:unfreeze_player
scoreboard players set #ostage deusex 3
# No `weather rain` here. It used to be the line above #washbase, and it is the reason the drop landed
# on a dry-looking sky: ServerLevel moves rainLevel 0.01 at a time, so a storm started on this tick is
# 1% visible on this tick and takes 100 of them to become the downpour. opening_rain is fired 104 ticks
# ahead of #drop from opening_tick, so by the time the heart goes the rain is already at full and the
# red drops are part of the explosion instead of arriving five seconds after it.
# The screenshot the user sent of the running event measured its sky at (108,83,100) - a red-minus-
# blue of +8, which is lavender. That is not the veil failing to paint: ClientLevel.getSkyColor
# multiplies the biome colour by a time-of-day factor and then desaturates it toward grey by the rain
# level (f7 = 1 - rain * 0.75), and the show forces rain, so three quarters of whatever hue the sky
# had is gone before the wash is ever composited. Repainting the user's own frame with the veil
# taken off and put back at each level is what turns that into a number: lv6 (today) (108,83,100) +8,
# lv12 (115,60,74) +41, lv14 (121,48,60) +60, lv16 (134,29,38) +97. The ask was "make the sky look
# reddish so it brings more impact", and 14 is the level where the frame reads as a red sky while the
# drops, the disc and the lyric are still in the picture; 16 is "strongly red" and 18 erases it.
# wash_tick ramps to this at one level per tick and will not drain below it, and opening_flash is what
# puts those levels on screen while the burst is still running: 14 ticks of climbing wash against 14
# ticks of decaying white flash, so the red sky arrives inside the explosion instead of after it.
# closing_start takes the floor back to 0, and that last drain is the hand-over to plain Minecraft.
# The ceiling is #washmax 17, three levels above this, so a flash is still a blink over a sky that is
# already red.
scoreboard players set #washbase deusex 14
scoreboard players set #flashd deusex 200
scoreboard players set #fframe deusex 0
