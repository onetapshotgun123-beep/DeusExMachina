execute if score #scr deusex matches 1 store result score #min deusex run random value 0..9
execute if score #scr deusex matches 1 store result score #s10 deusex run random value 0..5
execute if score #scr deusex matches 1 store result score #s1 deusex run random value 0..9
execute if score #state deusex matches 2 run data modify storage deusex:data tc set value "yellow"
execute if score #vis deusex matches 0 run function deusex:hud_only with storage deusex:data
execute if score #vis deusex matches 1 if score #mode deusex matches 0 run function deusex:hud_show with storage deusex:data
execute if score #vis deusex matches 1 if score #mode deusex matches 1 run function deusex:hud_show_box with storage deusex:data
execute if score #vis deusex matches 1 if score #mode deusex matches 2 run function deusex:lyric_only with storage deusex:data
