scoreboard players add #frame deusex 2
execute if score #frame deusex matches 24.. run scoreboard players remove #frame deusex 24
execute store result score #p deusex run random value 1..10
scoreboard players set #mode deusex 0
scoreboard players set #scr deusex 1
scoreboard players set #vis deusex 1
function deusex:hud_glyph
function deusex:hud_preset
scoreboard players set #scr deusex 1
data modify storage deusex:data tc set value "red"
function deusex:hud_emit
