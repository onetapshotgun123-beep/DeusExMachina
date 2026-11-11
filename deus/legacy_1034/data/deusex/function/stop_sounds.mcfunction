scoreboard players operation #prev deusex = #idx deusex
scoreboard players remove #prev deusex 1
execute if score #prev deusex matches ..-1 run scoreboard players set #prev deusex 0
execute store result storage deusex:data idx int 1 run scoreboard players get #idx deusex
execute store result storage deusex:data prev int 1 run scoreboard players get #prev deusex
function deusex:stop_macro with storage deusex:data
