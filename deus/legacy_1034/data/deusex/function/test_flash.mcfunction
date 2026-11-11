# Fire the flash immediately: the sky panel and the veil, both at once, without waiting
# for the 8-21 s scheduler. Whatever appears on screen tells us which of the two is broken -
# the panel is an entity in the world and the wash is a title, so they fail
# for entirely different reasons and a player can only tell them apart by looking.
function deusex:flash_begin
tellraw @a ["",{"text":"DEUS-TEST-FLASH ","color":"gold"},{"text":"the sky in FRONT of you should light up red for about a second (three layers: broad glow, hot core, red flare), the screen should tint red and fade over 3 s","color":"yellow"}]
tellraw @a ["",{"text":"DEUS-TEST-FLASH ","color":"gold"},{"text":"if the sky stays blue, look around: the panel is placed in front of wherever you are facing. Is it red anywhere at all?","color":"aqua"}]
execute if score #state deusex matches 0 run tellraw @a ["",{"text":"DEUS-TEST-FLASH ","color":"gold"},{"text":"note: the song is not playing, so the flash will be re-armed by the scheduler as soon as it is","color":"gray"}]
