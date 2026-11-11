scoreboard players operation #E deusex = #idx deusex
scoreboard players operation #E deusex *= #60 deusex
scoreboard players operation #E deusex += #t deusex
execute if score #ostage deusex matches 1 if score #E deusex matches 42.. run function deusex:opening_hb_begin
# The storm is armed ahead of the hit, not with it: #rainlead is #drop minus 104, which is what the
# 0.01-a-tick rain ramp costs, and opening_rain keeps the numbers. #rain makes this fire exactly
# once - it is 0 until that line runs, and halt and closing_start take it back down with the weather.
execute if score #ostage deusex matches 2 if score #rain deusex matches 0 if score #E deusex >= #rainlead deusex run function deusex:opening_rain
execute if score #ostage deusex matches 2 if score #E deusex >= #drop deusex run function deusex:opening_burst
execute if score #ostage deusex matches 2 run function deusex:opening_hb
execute if score #ostage deusex matches 3 run function deusex:opening_flash
