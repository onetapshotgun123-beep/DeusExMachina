
scoreboard players set #fframe deusex 0
scoreboard players set #state deusex 0
scoreboard players set #idx deusex 0
scoreboard players set #t deusex 0
# closing_start clears the weather and takes #rain down with it, so nothing that can throw may sit in
# front of it. finish runs from run_playing inside the tick loop, and the bare `kill @e[...]` that used
# to be this function's first line throws whenever the sky has no panel to clear - which is most of the
# time, because flash_frame kills the set at #fframe 0 - and a throw stops every line after it, in this
# function and in whatever called it. The ending therefore never started on those runs: the veil stayed
# up at full strength and the world kept raining the pack's own red.
function deusex:closing_start
# The cleanup belongs here, last, and guarded. flash_tick only drives the envelope while the song runs,
# so a flash that was mid-frame when the track ended would freeze at whatever opacity it had reached and
# hold a lit red panel in the sky forever: a text_display has no Duration in 1.21.1, nothing removes it
# but a kill. `if entity` asks EntityArgument.getOptionalEntities, which returns an empty list instead
# of throwing, so a sky with nothing to clear costs nothing.
execute if entity @e[type=minecraft:text_display,tag=deusex_flash] run kill @e[type=minecraft:text_display,tag=deusex_flash]
