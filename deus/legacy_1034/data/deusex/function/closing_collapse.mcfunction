scoreboard players operation #k deusex = #ct deusex
scoreboard players remove #k deusex 40
scoreboard players operation #kb deusex = #k deusex
scoreboard players operation #kb deusex /= #2 deusex
scoreboard players operation #kd deusex = #k deusex
scoreboard players operation #kd deusex *= #10 deusex
scoreboard players operation #kd deusex /= #16 deusex
execute if score #kb deusex matches 0 run data modify storage deusex:data bx set value ""
execute if score #kb deusex matches 1 run data modify storage deusex:data bx set value ""
execute if score #kb deusex matches 2 run data modify storage deusex:data bx set value ""
execute if score #kb deusex matches 3 run data modify storage deusex:data bx set value ""
execute if score #kb deusex matches 4 run data modify storage deusex:data bx set value ""
execute if score #kb deusex matches 5 run data modify storage deusex:data bx set value ""
execute if score #kb deusex matches 6 run data modify storage deusex:data bx set value ""
execute if score #kb deusex matches 7 run data modify storage deusex:data bx set value ""
execute if score #kd deusex matches 0 run data modify storage deusex:data g set value ""
execute if score #kd deusex matches 1 run data modify storage deusex:data g set value ""
execute if score #kd deusex matches 2 run data modify storage deusex:data g set value ""
execute if score #kd deusex matches 3 run data modify storage deusex:data g set value ""
execute if score #kd deusex matches 4 run data modify storage deusex:data g set value ""
execute if score #kd deusex matches 5 run data modify storage deusex:data g set value ""
execute if score #kd deusex matches 6 run data modify storage deusex:data g set value ""
execute if score #kd deusex matches 7 run data modify storage deusex:data g set value ""
execute if score #kd deusex matches 8 run data modify storage deusex:data g set value ""
execute if score #kd deusex matches 9 run data modify storage deusex:data g set value ""
function deusex:hud_show_c with storage deusex:data
