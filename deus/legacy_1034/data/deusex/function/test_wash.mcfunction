# Force the red wash over the world, right now, without waiting for the flash scheduler.
# This is the one line of the pipeline that a player can only judge by looking: the wash is a title
# drawn from red_lv.png, so if the font, the title slot or the alpha table is wrong nothing else in
# the pack will ever reveal it. Run it, look at the screen for two seconds, and say whether the
# whole view went red.
# While the song holds its red sky this settles on #washbase rather than clearing, which is the
# point: a spike that lands on the held level and drains back to it is the same shape the flashes
# make, so the test also proves the floor works. /function deusex:stop takes the whole thing down.
# Armed from #washmax rather than a literal, the way flash_begin arms it: the spike has to be above
# the held floor to read as a spike, and the floor moved to 14 when the sky went reddish in 1.0.30.
scoreboard players operation #wash deusex = #washmax deusex
scoreboard players set #washc deusex 0
scoreboard players set #wlast deusex -1
function deusex:wash_draw
tellraw @a ["",{"text":"DEUS-TEST-WASH ","color":"gold"},{"text":"the whole screen should have gone red for 2 s, then back down to the sky the song is holding","color":"yellow"}]
