# Seamless start (1.0.29): pay the cold-start cost of the first streamed sound when a player joins,
# not when the show starts.
#
# run_lead.mcfunction explains the cost: the first streamed play of a client session starts about
# 1.5 s later than every play after it, because jOrbis is still interpreted. start used to hide that
# by arming a 70 tick pre-roll on every run - 67 ticks of silent warm-up and only then the song - which
# is the silence between "[Deus Ex Machina] Started" and the music. The warm-up is a once per session
# cost, so it is moved here: 60 ticks after a player joins (the terrain is up by then) the same silent
# prewarm.ogg is streamed to them once. start then only takes the short path when every player online
# has had at least the 70 ticks of headroom the old pre-roll gave (counter 130 = 60 + 70).
#
# deusex_wt counts ticks since the player's join, capped at 200. deusex_left is the leave-game
# statistic: a player who left and came back is a new client session (the game may have been
# restarted in between), so their counter starts again. load.mcfunction clears every counter for the
# case where the world or server went down without a leave being counted.
execute as @a[scores={deusex_left=1..}] run function deusex:warm_reset
execute as @a unless score @s deusex_wt = @s deusex_wt run scoreboard players set @s deusex_wt 0
# A player whose counter just started is new or rejoined: if the gapless track is already running they
# never received it (the stream went to the players who were online when it fired), so mark them for
# the next chunk head - run_playing -> play_catchup. The #lead 0 and #t 1.. gates keep the tag off a
# joiner who is about to be covered anyway: fire_track hands the track to @a on the hand-over tick,
# and the hand-over tick still has #t 0, so tagging there would double-fire chunk_0 on top of the
# track three seconds in.
execute as @a[scores={deusex_wt=0}] if score #state deusex matches 1 if score #full deusex matches 1 if score #lead deusex matches 0 if score #t deusex matches 1.. run tag @s add deusex_catchup
scoreboard players add @a[scores={deusex_wt=..199}] deusex_wt 1
# silent, a real stream open; skipped while a show is running because the show's own track is the warm-up
execute unless score #state deusex matches 1..2 as @a[scores={deusex_wt=60}] at @s run playsound deusex:prewarm record @s ~ ~ ~ 1 1 1
