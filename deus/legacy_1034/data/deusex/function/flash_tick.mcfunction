# the only sky effect in the mod: a red glow fills the sky in front of every player for about a
# second, at intervals nobody can predict. Three panels per player - broad glow, hot core, red
# flare - on the 1.0.18 envelope, together with the rain the burst forces and the veil wash.
execute if score #fframe deusex matches 1.. run function deusex:flash_frame
execute if score #fframe deusex matches 0 run scoreboard players remove #flashd deusex 1
execute if score #fframe deusex matches 0 if score #flashd deusex matches ..0 run function deusex:flash_begin
