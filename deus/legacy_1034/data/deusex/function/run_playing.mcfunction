# tick.mcfunction only reaches this path once #lead has counted down the track's decode time, so
# #E here is the position of the audio the player is actually hearing.
execute if score #ostage deusex matches 1.. run function deusex:opening_tick
# Every chunk head fires the next sound - but only in the chunked path. In the gapless path the
# pre-roll owns the fire: run_lead hands main_track to fire_track on the tick #lead hits 3, and #t is
# still 0 when the clock finally moves, so an ungated fire here triggered the track a second time.
# Two instances of the same 546 s recording start one tick apart and the whole intro plays as a
# flam. #full 1 only ever means that pre-roll is in play (halt and do_pause both clear it), and the
# chunk sounds it would skip are silent by design - play_macro answers only #idx 0 while #full is 1.
execute if score #t deusex matches 0 if score #full deusex matches 0 run function deusex:play_chunk
# A rejoiner waits here: play_chunk answers @a but only fires while the gapless hold is off, and the
# track itself was a one-time hand-out, so anyone tagged deusex_catchup since the last head gets the
# current chunk instead. Gated on #full 1 so a resumed (chunked) show never plays it twice - play_chunk
# already covers every player there.
execute if score #t deusex matches 0 if score #full deusex matches 1 if entity @a[tag=deusex_catchup] run function deusex:play_catchup
scoreboard players set #limit deusex 60
execute if score #idx deusex = #last deusex run scoreboard players operation #limit deusex = #lastlen deusex
scoreboard players add #t deusex 1
execute if score #t deusex >= #limit deusex run function deusex:next_chunk
