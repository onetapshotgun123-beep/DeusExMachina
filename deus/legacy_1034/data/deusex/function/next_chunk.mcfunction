scoreboard players set #t deusex 0
scoreboard players add #idx deusex 1
execute if score #idx deusex > #last deusex if score #loop deusex matches 1 run scoreboard players set #idx deusex 0
# a looped replay fires main_track from its head again, so it needs the same pre-roll that
# start.mcfunction arms: silent stream first, then the track 3 ticks before the clock moves.
execute if score #idx deusex matches 0 if score #full deusex matches 1 run scoreboard players set #lead deusex 70
execute if score #idx deusex > #last deusex run function deusex:finish
