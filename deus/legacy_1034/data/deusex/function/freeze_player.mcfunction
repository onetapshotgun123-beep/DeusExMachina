execute store result score @s deusex_move run attribute @s minecraft:generic.movement_speed base get 1000000
execute store result score @s deusex_fly run attribute @s minecraft:generic.flying_speed base get 1000000
execute store result score @s deusex_jump run attribute @s minecraft:generic.jump_strength base get 1000000
execute store result score @s deusex_grav run attribute @s minecraft:generic.gravity base get 1000000
attribute @s minecraft:generic.movement_speed base set 0
attribute @s minecraft:generic.flying_speed base set 0
attribute @s minecraft:generic.jump_strength base set 0
attribute @s minecraft:generic.gravity base set 0
tag @s add deusex_frozen
