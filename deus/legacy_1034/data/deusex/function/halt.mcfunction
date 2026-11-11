# The scoreboard bookkeeping goes first and the commands that need a level or players last, which
# is the rule flash_begin states for itself: a command that throws stops everything after it in the
# same function, and a half-run halt is what leaves a stopped show holding the screen red. The one
# thing that may not sit in the middle is the panel cleanup, because /kill throws on an empty
# selector - see the note above it - so it is last, and guarded.
scoreboard players set #fframe deusex 0
scoreboard players set #burst deusex 0
scoreboard players set #state deusex 0
scoreboard players set #full deusex 0
scoreboard players set #lead deusex 0
scoreboard players set #idx deusex 0
scoreboard players set #t deusex 0
# The held red sky outlives the song if it is not taken back down here: tint_refresh paints the
# veil with times 0/100000/0, so a level parked on #washbase stays over the world after everything
# else has stopped, and only `stop` on a running song escapes that because closing_start drains it.
# Repainting at #wash 0 uses cell 0 of red_lv.png - mean alpha 3/255, which is the same as nothing.
scoreboard players set #washbase deusex 0
scoreboard players set #wash deusex 0
scoreboard players set #wlast deusex -1
function deusex:wash_draw
data modify storage deusex:data lyr set value ""
# opening_burst forces the rain, and the rain is the colour: the red drops come from the pack's
# assets/minecraft rain.png, which the client binds whenever it is raining at all. Stopping the show
# therefore has to stop the weather, or a halted song leaves the world raining red for no reason -
# finish gets this for free because closing_start clears it. #rain goes down with it so tick's gate
# has nothing left to re-clear, and the weather cycle load.mcfunction turned off is what stops the sky
# from picking a cloud back up on its own after this point.
# All of this sits above the panel cleanup on purpose. /kill takes an entity argument and
# EntityArgument.getEntities throws argument.entity.notfound.entity when the selector matches nothing,
# and a throw stops every line after it in the same function and in whatever called it. Most halts
# have no panel left to kill - flash_frame already killed the set at #fframe 0 - so the cleanup used
# to be the thing that stopped `weather clear`, the #rain disarm, the unfreeze and the stop_sounds
# from ever running: the stopped show kept its red sky, its frozen player and its music.
weather clear
scoreboard players set #rain deusex 0
execute as @a[tag=deusex_frozen] run function deusex:unfreeze_player
function deusex:stop_sounds
# `if entity` first: EntityArgument.getOptionalEntities returns an empty list instead of throwing, so
# a cleanup with nothing to clean is a no-op and this stays the only line that can fail at the foot of
# the function, where failing costs nothing.
execute if entity @e[type=minecraft:text_display,tag=deusex_flash] run kill @e[type=minecraft:text_display,tag=deusex_flash]
