scoreboard objectives add deusex dummy
scoreboard players set #last deusex 181
scoreboard players set #lastlen deusex 59
execute unless score #state deusex = #state deusex run scoreboard players set #state deusex 0
execute unless score #loop deusex = #loop deusex run scoreboard players set #loop deusex 0
execute unless score #idx deusex = #idx deusex run scoreboard players set #idx deusex 0
execute unless score #t deusex = #t deusex run scoreboard players set #t deusex 0
execute unless score #frame deusex = #frame deusex run scoreboard players set #frame deusex 0
execute unless score #hudt deusex = #hudt deusex run scoreboard players set #hudt deusex 0
execute unless score #burst deusex = #burst deusex run scoreboard players set #burst deusex 0
execute unless score #ostage deusex = #ostage deusex run scoreboard players set #ostage deusex 0
execute unless score #cstate deusex = #cstate deusex run scoreboard players set #cstate deusex 0
execute unless score #ct deusex = #ct deusex run scoreboard players set #ct deusex 0
execute unless score #wash deusex = #wash deusex run scoreboard players set #wash deusex 0
execute unless score #washc deusex = #washc deusex run scoreboard players set #washc deusex 0
execute unless score #wlast deusex = #wlast deusex run scoreboard players set #wlast deusex 0
# the level the veil sits at between flashes. Guarded, not set: closing_start drives it to 0 and a
# world that reloaded mid-ending must not have the red sky handed back to it.
execute unless score #washbase deusex = #washbase deusex run scoreboard players set #washbase deusex 0
# 10.947 s x 20 = 218.9 ticks -> 219: the song's real drop. In the original recording the arrangement
# cuts to a ~2 ms hole at 10.945 s and the whole band slams in at 10.947 s in one step (sub-bass +52 dB,
# 100-400 Hz +34 dB, mids +13 dB, highs +18 dB). 1.0.18 moved this anchor to 319 (15.95 s) because the
# shipped main_track.ogg had been ducked 18.6 dB from 10.3 s to 14.4 s, which buried that hit and left a
# swell ending at 15.9 s as the only "slam" a measurement could find. As of 1.0.27 main_track.ogg and
# chunks 3-5 are rebuilt from the original recording (the duck now ends at the hole, so the hit is at
# full level), and the anchor is back on the real drop.
# Set, not "unless unset", so a world that already cached the old 319 picks the corrected anchor up on reload.
scoreboard players set #drop deusex 219
# When the storm gets its orders, as opposed to when it lands. ServerLevel.advanceWeatherCycle adds
# 0.01F to rainLevel every tick and clamps at 1.0 (ServerLevel.java:705-712), and the drops a client
# draws are multiplied by that level (LevelRenderer.renderSnowAndRain:269 and :339), so 100 ticks is
# the shortest possible run-up to a full downpour and `weather rain` cannot skip any of it. Four ticks
# of slack over the ramp, so rainLevel is already clamped when opening_burst fires.
scoreboard players operation #rainlead deusex = #drop deusex
scoreboard players remove #rainlead deusex 104
scoreboard players set #washmax deusex 17
scoreboard players set #60 deusex 60
scoreboard players set #20 deusex 20
scoreboard players set #16 deusex 16
scoreboard players set #10 deusex 10
scoreboard players set #2 deusex 2
scoreboard players set #6 deusex 6
scoreboard players set #8 deusex 8
scoreboard players set #3 deusex 3
# flash_begin's delay is computed, not rolled: #1103515245 is the LCG multiplier, #261 the width
# of the window, and #lcg the carried state. A wrapped int is fine - the fold only needs spread.
# The seed is guarded rather than set so the sequence keeps its phase across restarts; c=12345 is
# odd and m-1 is a multiple of 4, so the state has full 2^32 period and no fixed point at 0.
scoreboard players set #1103515245 deusex 1103515245
scoreboard players set #261 deusex 261
execute unless score #lcg deusex = #lcg deusex run scoreboard players set #lcg deusex 0
execute unless score #full deusex = #full deusex run scoreboard players set #full deusex 0
# 0, never 33: the lead-in is armed by start.mcfunction and by a looped next_chunk, and a world
# that reloads mid-hold recovers because run_playing still fires the chunk head at #t 0.
execute unless score #lead deusex = #lead deusex run scoreboard players set #lead deusex 0
execute unless score #tk deusex = #tk deusex run scoreboard players set #tk deusex 0
execute unless score #beats deusex = #beats deusex run scoreboard players set #beats deusex 0
execute unless score #flashes deusex = #flashes deusex run scoreboard players set #flashes deusex 0
execute unless score #panels deusex = #panels deusex run scoreboard players set #panels deusex 0
# which flare shape the next panel draws (0..3, picked per player by flash_rand). Defaulted so a
# world that reloads mid-flash still has a legal index for the macro spawner to read.
execute unless score #sr deusex = #sr deusex run scoreboard players set #sr deusex 0
scoreboard objectives add deusex_move dummy
scoreboard objectives add deusex_fly dummy
scoreboard objectives add deusex_jump dummy
scoreboard objectives add deusex_grav dummy
# Seamless start (1.0.29), see warm_tick.mcfunction. deusex_wt counts ticks since a player joined,
# deusex_left is the leave-game statistic that tells a rejoin from a continuing session. Every counter
# is cleared on load: a world that went down without a leave being counted would otherwise carry a
# "warm" count into a client that has been restarted since.
scoreboard objectives add deusex_wt dummy
scoreboard objectives add deusex_left minecraft.custom:minecraft.leave_game
scoreboard players reset * deusex_wt
# 1 = start the song at once when every player is warm; 0 = always use the 70 tick pre-roll
execute unless score #quick deusex = #quick deusex run scoreboard players set #quick deusex 1

# The veil's ceiling in red_lv.png levels. Set, not "unless unset", so a world that cached the old
# strength picks the new one up on reload - same reason #drop is set. It has to equal #washmax,
# because wash_draw paints #tint*#wash/#washmax: at 17 the level tracks #wash one for one and the
# ending's drain steps through the cells the fade actually walks.
# Measured on the shipped texture, the red the cell lays over the frame: lv6 12.2%, lv9 18.0%,
# lv14 34.9%, lv16 52.2%, lv17 65.1%, lv19 92.2%. The held level (opening_burst's #washbase 14) is
# the sky the song lives under, so this number only has to be above it by enough for a flash to read
# as a blink: 17 - 14 is three levels, 12 ticks of drain, roughly half the 22 tick panel, so the sky
# brightens and comes back inside one lit flash instead of cutting between two strengths.
# 17 rather than the 1.0.24 ceiling of 19 because 19 lays 92% red and the world behind it is gone -
# the same reason the held level stops at 14: the user asked for a redder sky, not a red screen with
# no sky in it. The actionbar lyrics stay readable because the wash only bites above level 4 and the
# held floor is 35%, not 90%.
scoreboard players set #tint deusex 17
execute unless score #hb deusex = #hb deusex run scoreboard players set #hb deusex 99
execute unless score #tfade deusex = #tfade deusex run scoreboard players set #tfade deusex 0
execute unless score #li deusex = #li deusex run scoreboard players set #li deusex -1
execute unless score #E deusex = #E deusex run scoreboard players set #E deusex 0
execute unless score #flashd deusex = #flashd deusex run scoreboard players set #flashd deusex 200
execute unless score #fframe deusex = #fframe deusex run scoreboard players set #fframe deusex 0
# The rain this pack owns. assets/minecraft/textures/environment/rain.png is red and the client binds
# that one path for every rainy frame in the world, so a cloud the pack did not start is a red sky the
# pack did not ask for - which is what a friend of the author found in 1.0.18, and no texture can fix
# it from the inside because an override cannot be conditioned on #state. The data-only answer is to
# own the weather instead: the world's own cycle goes off, so the only thing that can make it rain is
# opening_rain, and whatever is already falling while the show is not running goes clear. Guarded
# rather than set, and idle is decided by #state (a score that has never been set fails `matches 1..2`,
# so a first run on a fresh world clears too).
# Above the cleanup below, not under it. /kill takes an entity argument, and EntityArgument
# .getEntities throws argument.entity.notfound.entity when the selector matches nothing, and a throw
# stops every line after it in the same function - so a fresh world, which has no panel to kill, used
# to lose the three lines that own the sky. Same reason halt puts them before its own cleanup.
scoreboard players add #rain deusex 0
execute unless score #state deusex matches 1..2 run weather clear
gamerule doWeatherCycle false
function deusex:lyrics_init
execute if entity @e[type=minecraft:text_display,tag=deusex_flash] run kill @e[type=minecraft:text_display,tag=deusex_flash]
