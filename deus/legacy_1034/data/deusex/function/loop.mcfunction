execute if score #loop deusex matches 0 run scoreboard players set #loop deusex 2
execute if score #loop deusex matches 1 run scoreboard players set #loop deusex 0
execute if score #loop deusex matches 2 run scoreboard players set #loop deusex 1
execute if score #loop deusex matches 1 run tellraw @s {"text":"[Deus Ex Machina] Loop: ON","color":"aqua"}
execute if score #loop deusex matches 0 run tellraw @s {"text":"[Deus Ex Machina] Loop: OFF","color":"gray"}
