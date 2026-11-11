# The one place the veil's level is worked out: #lv = #tint * #wash / #washmax, mapped onto a cell of
# red_lv.png by lv_char. Two callers need it. tint_draw paints the song's wash into the title slot, and
# opening_flash paints it into the *blast* string, because the burst owns that slot for the 50 ticks
# after the drop and the red sky has to arrive with the explosion rather than after it. Keeping the
# maths in one file is what stops those two from ever disagreeing about which cell is on screen.
scoreboard players operation #lv deusex = #tint deusex
scoreboard players operation #lv deusex *= #wash deusex
scoreboard players operation #lv deusex /= #washmax deusex
function deusex:lv_char
