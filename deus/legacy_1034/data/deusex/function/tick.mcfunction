# selftest reads #tk: the number of times the game loop has run since the last /function deusex:start.
# A red effect that is missing and a tick loop that is not running look the same from outside the
# game, so the loop gets counted.
scoreboard players add #tk deusex 1
execute if score #state deusex matches 1..2 if score #ostage deusex matches 1..2 as @a[tag=!deusex_frozen] run function deusex:freeze_player
execute if score #state deusex matches 0 as @a[tag=deusex_frozen] run function deusex:unfreeze_player
execute if score #ostage deusex matches 3.. as @a[tag=deusex_frozen] run function deusex:unfreeze_player
# The blood rain's own gate. assets/minecraft/textures/environment/rain.png is red in this pack,
# which is the only way the drops themselves can be red - LevelRenderer.renderSnowAndRain binds that
# one path and writes `.setColor(1.0F, 1.0F, 1.0F, f7)` into every vertex, so the sheet is the hue and
# nothing in the pack can tint it per state. A texture override cannot be conditioned, so the weather
# is conditioned instead, and it is conditioned by owning it: load.mcfunction turns the world's weather
# cycle off, so rain only starts when this pack says so, and #rain is the pack's note that the rain
# outside is its own. Idle with the flag up means the show let go of the sky without clearing it - a
# state reset by hand, a run that ended on a path that never reached its clear - so the weather goes
# clear once and the flag goes with it. The cycle being off is what keeps plain rain plain: with the
# red sheet bound for every rainy frame in the world, a rain cloud the pack did not start is a red
# sky the pack did not ask for, which is the bug that took 1.0.18's texture out in the first place.
# There is no `if predicate` in this gate. The 1.21.1 soak throws "An unexpected error occurred trying
# to execute that command" for every form of it - the datapack id, minecraft:weather_check written
# inline, from the console, from inside a function, positioned over a loaded block - because
# ExecuteCommand.checkCustomPredicate needs a source this pack cannot guarantee. A throw is worse here
# than a wrong answer: it stops the rest of tick.mcfunction, and the rest of tick.mcfunction is the show.
# `unless matches 1..2` rather than `matches 0` so any state that is not the song or the opening is
# treated as idle, including the ending, where closing_start wants the sky clear anyway.
execute unless score #state deusex matches 1..2 if score #rain deusex matches 1 run weather clear
execute unless score #state deusex matches 1..2 if score #rain deusex matches 1 run scoreboard players set #rain deusex 0
# The clock does not start with the /playsound that fires main_track - it starts 3 ticks later, when
# the client has the track decoded. run_lead counts that pre-roll down with #E pinned at 0; once
# #lead reaches 0 the normal path takes over. See run_lead.mcfunction for the measurement.
# The two lines are in this order on purpose. Every execute condition is re-read after the previous
# line ran, so with run_lead first the tick that counts #lead down from 1 to 0 also passed the
# #lead 0 test, and the hand-over tick moved the clock and consumed the hold at once: the last tick
# of the hold would be swallowed and the whole intro would sit one tick ahead of the music again.
execute if score #state deusex matches 1 if score #lead deusex matches 0 run function deusex:run_playing
execute if score #state deusex matches 1 if score #lead deusex matches 1.. run function deusex:run_lead
# The veil moves whenever it is not already sitting on its held level, in the song and in the ending
# alike. #cstate owns its own copy inside closing_tick, so the two never fade it twice in one tick.
# Comparing against #washbase rather than `matches 1..` is what lets the ramp-up run at all: the
# burst raises #washbase while #wash is still 0, and that gate would otherwise never open.
execute if score #cstate deusex matches 0 unless score #wash deusex = #washbase deusex run function deusex:wash_tick
# The flash belongs to the part of the song the player watches with the world visible: during the
# cutscene there is no panel to light and nothing to time, and opening_burst has only just armed the
# #flashd roll it reads.
execute if score #state deusex matches 1 if score #cstate deusex matches 0 if score #ostage deusex matches 4.. run function deusex:flash_tick
# The veil stops where the cutscene starts, but it no longer waits for the cutscene to end. The blast
# owns the title slot for its 50 ticks, so opening_flash paints the same #lv into that string instead
# - see title_red_burst - and the two paths meet at #wash 14 on the tick opening_done resets the
# title. Before 1.0.31 nothing drew the wash until then, which is the 2.5 second lag this gate's old
# comment offered as its justification.
execute if score #state deusex matches 1 if score #cstate deusex matches 0 if score #ostage deusex matches 4.. run function deusex:wash_draw
execute if score #cstate deusex matches 1 run function deusex:closing_tick
execute unless score #cstate deusex matches 1 unless score #ostage deusex matches 1..2 if score #state deusex matches 1..2 run function deusex:hud_tick
execute unless score #cstate deusex matches 1 unless score #ostage deusex matches 1..2 if score #state deusex matches 0 if score #wash deusex matches 1.. run function deusex:hud_tick
# No /particle in this pack, and nothing below the HUD lines. The motes 1.0.19 through 1.0.25 hung
# in the air were never in the 1.0.18 look, and /particle is the one command here that can throw on
# an unloaded chunk and take the rest of the tick with it.
# Seamless start (1.0.29): last line on purpose, so nothing in front of the show depends on it.
function deusex:warm_tick
