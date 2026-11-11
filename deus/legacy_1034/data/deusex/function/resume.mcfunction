execute unless score #state deusex matches 2 run tellraw @s {"text":"[Deus Ex Machina] Not paused","color":"red"}
execute if score #state deusex matches 2 run function deusex:do_resume
