execute unless score #state deusex matches 1 run tellraw @s {"text":"[Deus Ex Machina] Nothing is playing","color":"red"}
execute if score #state deusex matches 1 run function deusex:do_pause
