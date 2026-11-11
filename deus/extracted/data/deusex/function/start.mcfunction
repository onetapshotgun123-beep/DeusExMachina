# Hand the start command to the client mod's server orchestrator via the #cmd bridge.
scoreboard players set #cmd deusex 1
scoreboard players set #tk deusex 0
tellraw @s {"text":"[Deus Ex Machina] Starting the show.","color":"green"}