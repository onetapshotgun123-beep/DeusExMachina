# The gapless track was handed to the players who were online when it fired, once; a player who
# leaves and comes back has a client that dropped the stream with the world unload, and /playsound
# has no resume primitive - the only way back into the song is another play. The chunks tile the
# same 60 tick grid the clock runs on, so firing the current chunk at the next head puts the
# rejoiner on the same timeline as everyone else, at most one chunk (3 s) of the song behind.
# Same shape as play_chunk: a plain function fills the macro cell, the macro line lives in a
# function called with storage, because a $ line only binds arguments handed to its own call.
execute store result storage deusex:data idx int 1 run scoreboard players get #idx deusex
function deusex:catchup_macro with storage deusex:data
tag @a[tag=deusex_catchup] remove deusex_catchup