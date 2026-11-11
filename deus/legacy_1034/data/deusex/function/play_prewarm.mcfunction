# Warm the streamed-sound path without warming anything the player can hear.
#
# prewarm.ogg is five seconds of digital zero at 44.1 kHz stereo - the same format as main_track.ogg
# and long enough to fill the four one-second buffers Channel.attachBufferStream pumps before play().
# Firing it is a real stream open, so jOrbis gets compiled hot and the OpenAL buffer upload runs,
# which is the whole cost of a cold first play. Digital zero stays zero through the mixer, so this
# tick is silent even though the volume is 1.
stopsound @a * deusex:prewarm
execute as @a at @s run playsound deusex:prewarm record @s ~ ~ ~ 1 1 1
