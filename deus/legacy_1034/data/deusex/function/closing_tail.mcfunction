scoreboard players operation #cm deusex = #ct deusex
scoreboard players operation #cm deusex %= #2 deusex
execute if score #cm deusex matches 0 if score #wash deusex matches 1.. run function deusex:hud_only
execute if score #wash deusex matches 0 run function deusex:closing_end
