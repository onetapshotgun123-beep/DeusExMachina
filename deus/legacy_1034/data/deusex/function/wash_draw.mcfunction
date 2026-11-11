# Paint the veil at whatever level wash_tick is carrying, into the title slot. The lyrics live in
# the actionbar, so the two never fight; the cutscene is the one place they do, because the blast is a
# title too - so this waits for #ostage 4 and opening_flash carries the identical #lv in the blast
# string for the 50 ticks before it. tint_draw and wash_level are where the two agree.
# Only a changed level needs a new title: `title @a title` restarts the display timer, so redrawing
# every tick would buy 20 packets a second per player for a picture that does not move.
# tint_refresh sets the times to 0/100000/0, which makes that restart invisible, and lv_char maps
# level 0 to cell 0 of red_lv.png - mean alpha 3/255, which is the same as no veil at all, so the
# fade to nothing also takes the veil away.
scoreboard players operation #wlv deusex = #tint deusex
scoreboard players operation #wlv deusex *= #wash deusex
scoreboard players operation #wlv deusex /= #washmax deusex
execute unless score #wlv deusex = #wlast deusex run function deusex:tint_refresh
scoreboard players operation #wlast deusex = #wlv deusex
