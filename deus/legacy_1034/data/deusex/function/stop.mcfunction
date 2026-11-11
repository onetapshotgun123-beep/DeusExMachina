scoreboard players operation #was deusex = #state deusex
function deusex:halt
execute unless score #was deusex matches 0 run function deusex:closing_start
tellraw @s {"text":"[Deus Ex Machina] Stopped","color":"red"}
