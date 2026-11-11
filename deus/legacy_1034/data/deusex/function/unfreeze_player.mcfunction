execute store result storage deusex:data speed double 0.000001 run scoreboard players get @s deusex_move
execute store result storage deusex:data fly double 0.000001 run scoreboard players get @s deusex_fly
execute store result storage deusex:data jump double 0.000001 run scoreboard players get @s deusex_jump
execute store result storage deusex:data grav double 0.000001 run scoreboard players get @s deusex_grav
function deusex:restore_player with storage deusex:data
scoreboard players reset @s deusex_move
scoreboard players reset @s deusex_fly
scoreboard players reset @s deusex_jump
scoreboard players reset @s deusex_grav
tag @s remove deusex_frozen
