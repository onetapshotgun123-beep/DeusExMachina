scoreboard players set #hudt deusex 0
execute if score #state deusex matches 1 run scoreboard players add #frame deusex 1
execute if score #frame deusex matches 24.. run scoreboard players set #frame deusex 0
scoreboard players operation #E deusex = #idx deusex
scoreboard players operation #E deusex *= #60 deusex
scoreboard players operation #E deusex += #t deusex
scoreboard players operation #e deusex = #E deusex
scoreboard players operation #e deusex /= #20 deusex
scoreboard players operation #min deusex = #e deusex
scoreboard players operation #min deusex /= #60 deusex
scoreboard players operation #sec deusex = #e deusex
scoreboard players operation #sec deusex %= #60 deusex
scoreboard players operation #s10 deusex = #sec deusex
scoreboard players operation #s10 deusex /= #10 deusex
scoreboard players operation #s1 deusex = #sec deusex
scoreboard players operation #s1 deusex %= #10 deusex
scoreboard players set #vis deusex 0
execute unless score #state deusex matches 0 run scoreboard players set #vis deusex 1
scoreboard players set #p deusex 0
scoreboard players set #mode deusex 0
scoreboard players set #scr deusex 0
execute if score #burst deusex matches 1.. store result score #p deusex run random value 1..10
execute if score #burst deusex matches 1.. run scoreboard players remove #burst deusex 1
execute if score #burst deusex matches 0 store result score #roll deusex run random value 0..99
execute if score #burst deusex matches 0 if score #roll deusex matches 0..4 store result score #burst deusex run random value 1..5
function deusex:lyric_tick
function deusex:hud_glyph
function deusex:hud_preset
function deusex:hud_emit
