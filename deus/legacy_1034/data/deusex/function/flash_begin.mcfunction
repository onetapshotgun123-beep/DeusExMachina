# 8 to 21 s between flashes. Short enough that it happens several times in a song, long enough
# that two never blur into one.
# /random and /time cannot be used here. Anything that needs a level throws "An unexpected error
# occurred trying to execute that command" when the tick loop's console source has no level, and a
# function that throws never reliably reaches its later lines - so the flash would silently stop
# rearming. A wrapped 31-bit LCG is pure scoreboard arithmetic: same spread, always runs, and the
# headless soak can actually prove it.
# The state is carried in #lcg, which load.mcfunction only initialises when unset, so the sequence
# keeps its phase across restarts instead of flashing the same interval every time the world loads.
scoreboard players operation #lcg deusex *= #1103515245 deusex
scoreboard players add #lcg deusex 12345
scoreboard players operation #flashd deusex = #lcg deusex
scoreboard players operation #flashd deusex %= #261 deusex
execute if score #flashd deusex matches ..-1 run scoreboard players add #flashd deusex 261
scoreboard players add #flashd deusex 160
scoreboard players set #fframe deusex 23
# The veil and the panel are one event. This is the ramp-up that went away with the storm: nothing
# else raises #wash during the song, so the sky could flash red while the world in front of the
# player stayed plain. wash_tick then fades it one level every 4 ticks, so the screen keeps bleeding
# red for about three seconds after the panel has died - which is how long 1.0.18 let its sky tint
# drain, and the difference between a flash you notice and one you don't.
scoreboard players operation #wash deusex = #washmax deusex
scoreboard players set #washc deusex 0
# selftest reads #flashes: how many times the sky has been armed since the last start.
scoreboard players add #flashes deusex 1
# The lines that need a level come last, because a command that throws stops everything after it in the
# same function. The score bookkeeping above is what the rest of the pack reads, so it has to be
# finished before anything can fail - and because of that order the headless soak can prove the flash
# raises the veil instead of setting #wash by hand.
# The cleanup has to stay in front of flash_player: flash_frame writes the envelope by tag
# (`as @e[tag=deusex_fflare] run data merge`), so a panel left over from the last flash would take this
# one's opacities and light up red where the player stood three seconds ago. It is guarded, though,
# because a bare `kill @e[...]` throws on an empty selector and there is usually nothing to kill - the
# set dies at #fframe 0 in flash_frame. That throw used to swallow the line below it, and flash_player
# is the only thing in the pack that ever summons a panel, so an aborted cleanup meant no flash at all -
# and no panel to kill next time, so the next one aborted the same way and the sky never lit again.
execute if entity @e[type=minecraft:text_display,tag=deusex_flash] run kill @e[type=minecraft:text_display,tag=deusex_flash]
execute as @a at @s run function deusex:flash_player
