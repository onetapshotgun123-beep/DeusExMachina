scoreboard players operation #hbE deusex = #E deusex
scoreboard players operation #hbE deusex -= #drop deusex
# Beat offsets are relative to #drop, which sits on the song's real drop: the full-band slam at
# 10.947 s of the original recording (tick 219). The heart appears at tick 42 and the first beat is at
# tick 50, so there are 146 ticks to fill. The gaps shrink 34 -> 8 ticks so the heart races into the hit
# (beats at ticks 50, 84, 114, 140, 162, 178, 188, 196).
# The table used to be spread over 246 ticks for a drop at 319 (15.95 s), which is not where the song
# drops - see load.mcfunction for how that anchor came to be wrong.
# heartbeat.ogg is one lub at 0.00 and one dub 17.4 ticks later, audible to tick 21.8, so a beat late
# in the run-up would still be thumping *after* the drop - which is what "the heartbeat does not stop
# at the beat drop" describes. The last beat lands at -23: its dub peaks 0.28 s before the slam and
# its tail is gone by tick 218, one tick ahead of the slam at 219.
execute if score #hbE deusex matches -169 run function deusex:hb_beat
execute if score #hbE deusex matches -135 run function deusex:hb_beat
execute if score #hbE deusex matches -105 run function deusex:hb_beat
execute if score #hbE deusex matches -79 run function deusex:hb_beat
execute if score #hbE deusex matches -57 run function deusex:hb_beat
execute if score #hbE deusex matches -41 run function deusex:hb_beat
execute if score #hbE deusex matches -31 run function deusex:hb_beat
execute if score #hbE deusex matches -23 run function deusex:hb_beat
execute if score #hbE deusex matches -7 as @a at @s run playsound deusex:boom_rise master @s ~ ~ ~ 1 1 1
scoreboard players set #lv deusex 0
execute if score #hb deusex matches 0 run scoreboard players set #lv deusex 17
execute if score #hb deusex matches 1 run scoreboard players set #lv deusex 16
execute if score #hb deusex matches 2 run scoreboard players set #lv deusex 13
execute if score #hb deusex matches 3 run scoreboard players set #lv deusex 10
execute if score #hb deusex matches 4 run scoreboard players set #lv deusex 7
execute if score #hb deusex matches 5 run scoreboard players set #lv deusex 4
execute if score #hb deusex matches 6 run scoreboard players set #lv deusex 15
execute if score #hb deusex matches 7 run scoreboard players set #lv deusex 14
execute if score #hb deusex matches 8 run scoreboard players set #lv deusex 11
execute if score #hb deusex matches 9 run scoreboard players set #lv deusex 8
execute if score #hb deusex matches 10 run scoreboard players set #lv deusex 5
execute if score #hb deusex matches 11 run scoreboard players set #lv deusex 3
execute if score #hb deusex matches 12 run scoreboard players set #lv deusex 1
execute if score #hb deusex matches 13 run scoreboard players set #lv deusex 0
function deusex:lv_char
function deusex:heart_frame
function deusex:title_hb with storage deusex:data
scoreboard players add #hb deusex 1
execute if score #hb deusex matches 100.. run scoreboard players set #hb deusex 99
