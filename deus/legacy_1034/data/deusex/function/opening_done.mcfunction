title @a reset
# The blast string has been carrying the wash for these 50 ticks and `reset` takes the wash away with
# it. wash_draw repaints only when its level *changes* (#wlv against #wlast), and it has not run once
# since start put #wlast at 0, because tick.mcfunction gates it on #ostage 4.. - so left alone, the
# last burst frame would be the thing `reset` removes and the song would play under a plain sky. -1 is
# the value halt uses for the same reason: no level the gate can hold equals it, so the wash_draw line
# that runs after this in the same tick paints the ceiling of #wash 14 back unconditionally, into the
# title slot, at the cell the burst was already showing. That is what makes the hand-over invisible.
scoreboard players set #wlast deusex -1
scoreboard players set #ostage deusex 4
