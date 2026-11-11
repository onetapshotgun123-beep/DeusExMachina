scoreboard players set #state deusex 2
# The envelope is ended here, above everything else. tick only drives flash_tick at #state 1, so a
# pause freezes a flash mid-frame: the counter stops above 0 and the panels stay lit at whatever
# opacity the last row wrote, and on resume they light up again in whatever direction the player is
# now facing. #fframe 0 puts the flash away for good and the kill below it takes the panels with it.
# The write sits at the head of the file because a command that throws stops every line under it -
# both a `kill @e[...]` with nothing to kill and a `tellraw @s` from a source that is not a player do
# that, and this is the line the pause exists for.
scoreboard players set #fframe deusex 0
function deusex:stop_sounds
scoreboard players set #full deusex 0
# resuming plays one of the 3 s chunk files, which start on the tick they are fired - no lead-in
scoreboard players set #lead deusex 0
scoreboard players set #t deusex 0
tellraw @s {"text":"[Deus Ex Machina] Paused","color":"yellow"}
# Guarded, and last: see halt for the same trap one exit path over.
execute if entity @e[type=minecraft:text_display,tag=deusex_flash] run kill @e[type=minecraft:text_display,tag=deusex_flash]
