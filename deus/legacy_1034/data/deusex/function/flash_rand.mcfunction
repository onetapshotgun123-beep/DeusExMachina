execute store result score #sr deusex run random value 0..3
execute store result score #sy deusex run data get entity @s Rotation[0]
execute store result score #sa deusex run random value -30..30
scoreboard players operation #sy deusex += #sa deusex
execute store result storage deusex:data yaw int 1 run scoreboard players get #sy deusex
