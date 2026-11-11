execute if score #ct deusex matches 0..39 run function deusex:closing_glitch
execute if score #ct deusex matches 40..55 run function deusex:closing_collapse
execute if score #tfade deusex matches 1 run function deusex:tint_fade_tick
# closing_start raises #wash to full and closing_tail will not run closing_end until it is back to
# 0. finish has already put #state at 0, and tick.mcfunction gates its own drain on #cstate so the
# level is not faded twice a tick, which leaves this as the ending's only decay.
execute if score #wash deusex matches 1.. run function deusex:wash_tick
execute if score #ct deusex matches 56.. run function deusex:closing_tail
scoreboard players add #ct deusex 1
