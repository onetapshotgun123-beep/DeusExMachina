function deusex:halt
function deusex:reset_screen
# No panel cleanup here. halt's last line already kills every deusex_flash panel, and a second
# `kill @e[...]` after it would throw on the fresh world where halt killed nothing - and a throw stops
# every line below it, which used to mean the show never got past this point: no #state, no pre-roll,
# no freeze, no title. Everything start needs from the cleanup is already done by the time halt
# returns.
scoreboard players set #fframe deusex 0
scoreboard players set #flashd deusex 200
scoreboard players set #wash deusex 0
scoreboard players set #washbase deusex 0
scoreboard players set #wlast deusex 0
function deusex:hud_clear
scoreboard players set #full deusex 1
# The catch-up tag only burns while the gapless hold is up, but nothing on the pause/halt/finish
# paths removes it, and a tag that survives into the NEXT show would fire chunk_0 over that show's
# main_track at its first head. start is the only function that ever raises #full to 1, so this is
# the one home the stale tag cannot get past.
tag @a remove deusex_catchup
# arm the 70 tick pre-roll: 67 ticks of silent stream warm-up, then main_track fired 3 ticks before
# the clock moves. run_lead counts it down - see that file for the two latency measurements.
scoreboard players set #lead deusex 70
# Seamless start (1.0.29): when every player online has been warm for the full 130 ticks, the silent
# pre-roll has nothing left to do, so the lead is the short 3 tick hold and the song starts now. Anyone
# who joined less than 6.5 s ago has not had their warm-up yet and keeps the 70 tick pre-roll for
# everyone, which is exactly the 1.0.28 behaviour. #quick 0 forces that behaviour.
execute store result score #warmn deusex if entity @a[scores={deusex_wt=130..}]
execute store result score #allp deusex if entity @a
execute if score #quick deusex matches 1 if score #warmn deusex = #allp deusex run scoreboard players set #lead deusex 3
scoreboard players set #state deusex 1
scoreboard players set #ostage deusex 1
execute as @a[tag=!deusex_frozen] run function deusex:freeze_player
# the three counters measure one playthrough, so a report says what this run did
scoreboard players set #tk deusex 0
scoreboard players set #beats deusex 0
scoreboard players set #flashes deusex 0
title @a times 40 100000 0
function deusex:title_black
tellraw @s {"text":"[Deus Ex Machina] Started","color":"green"}
execute if score #lead deusex matches 70 run tellraw @s {"text":"[Deus Ex Machina] Warming up the audio first - starting a few seconds after joining takes a moment longer.","color":"gray"}
