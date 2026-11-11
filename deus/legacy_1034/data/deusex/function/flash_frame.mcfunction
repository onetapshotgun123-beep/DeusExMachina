# One flash, 22 lit frames, straight from the 1.0.18 envelope: the flare and the hot core snap to
# full brightness, the broad glow follows a frame behind, and the three then decay together. The
# opacity values are signed bytes on purpose - the client reads text_opacity as unsigned, so -1b is
# 255 and -21b is 235, and that is what made this version bright enough to notice.
# Every tick of the envelope names all three tags, because text_opacity is sticky: a frame that
# skips a panel leaves it frozen at whatever the previous tick wrote.
# The countdown and the kill are the first two lines. A command that throws stops the rest of its
# own function, so with the bookkeeping at the bottom one bad entity write would leave the sky lit
# forever; doing it first means the envelope always drains and always cleans up. flash_begin arms
# #fframe one above the first row, so the row keyed 22 is the picture's first frame.
# The kill is guarded because a bare `kill @e[...]` throws on an empty selector, and at this point in a
# flash there is very often nothing left to kill. The rows below are keyed 22 down to 1, so a throw
# here costs nothing - but the pack no longer relies on that.
scoreboard players remove #fframe deusex 1
execute if score #fframe deusex matches 0 if entity @e[type=minecraft:text_display,tag=deusex_flash] run kill @e[type=minecraft:text_display,tag=deusex_flash]
execute if score #fframe deusex matches 22 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:-1b}
execute if score #fframe deusex matches 22 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:-1b}
execute if score #fframe deusex matches 22 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:-21b}
execute if score #fframe deusex matches 21 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:-66b}
execute if score #fframe deusex matches 21 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:-96b}
execute if score #fframe deusex matches 21 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:-116b}
execute if score #fframe deusex matches 20 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:-1b}
execute if score #fframe deusex matches 20 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:-21b}
execute if score #fframe deusex matches 20 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:-51b}
execute if score #fframe deusex matches 19 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:-31b}
execute if score #fframe deusex matches 19 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:-51b}
execute if score #fframe deusex matches 19 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:-81b}
execute if score #fframe deusex matches 18 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:95b}
execute if score #fframe deusex matches 18 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:120b}
execute if score #fframe deusex matches 18 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:95b}
execute if score #fframe deusex matches 17 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:-1b}
execute if score #fframe deusex matches 17 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:-11b}
execute if score #fframe deusex matches 17 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:-41b}
execute if score #fframe deusex matches 16 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:-101b}
execute if score #fframe deusex matches 16 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:-71b}
execute if score #fframe deusex matches 16 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:-101b}
execute if score #fframe deusex matches 15 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:65b}
execute if score #fframe deusex matches 15 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:125b}
execute if score #fframe deusex matches 15 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:105b}
execute if score #fframe deusex matches 14 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:35b}
execute if score #fframe deusex matches 14 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:95b}
execute if score #fframe deusex matches 14 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:80b}
execute if score #fframe deusex matches 13 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:20b}
execute if score #fframe deusex matches 13 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:75b}
execute if score #fframe deusex matches 13 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:62b}
execute if score #fframe deusex matches 12 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:0b}
execute if score #fframe deusex matches 12 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:60b}
execute if score #fframe deusex matches 12 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:50b}
execute if score #fframe deusex matches 11 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:0b}
execute if score #fframe deusex matches 11 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:50b}
execute if score #fframe deusex matches 11 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:42b}
execute if score #fframe deusex matches 10 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:0b}
execute if score #fframe deusex matches 10 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:42b}
execute if score #fframe deusex matches 10 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:35b}
execute if score #fframe deusex matches 9 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:0b}
execute if score #fframe deusex matches 9 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:35b}
execute if score #fframe deusex matches 9 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:28b}
execute if score #fframe deusex matches 8 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:0b}
execute if score #fframe deusex matches 8 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:28b}
execute if score #fframe deusex matches 8 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:22b}
execute if score #fframe deusex matches 7 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:0b}
execute if score #fframe deusex matches 7 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:22b}
execute if score #fframe deusex matches 7 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:17b}
execute if score #fframe deusex matches 6 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:0b}
execute if score #fframe deusex matches 6 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:17b}
execute if score #fframe deusex matches 6 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:13b}
execute if score #fframe deusex matches 5 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:0b}
execute if score #fframe deusex matches 5 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:13b}
execute if score #fframe deusex matches 5 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:10b}
execute if score #fframe deusex matches 4 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:0b}
execute if score #fframe deusex matches 4 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:9b}
execute if score #fframe deusex matches 4 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:7b}
execute if score #fframe deusex matches 3 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:0b}
execute if score #fframe deusex matches 3 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:6b}
execute if score #fframe deusex matches 3 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:5b}
execute if score #fframe deusex matches 2 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:0b}
execute if score #fframe deusex matches 2 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:3b}
execute if score #fframe deusex matches 2 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:3b}
execute if score #fframe deusex matches 1 as @e[tag=deusex_fflare] run data merge entity @s {text_opacity:0b}
execute if score #fframe deusex matches 1 as @e[tag=deusex_fcore] run data merge entity @s {text_opacity:0b}
execute if score #fframe deusex matches 1 as @e[tag=deusex_fglow] run data merge entity @s {text_opacity:0b}
