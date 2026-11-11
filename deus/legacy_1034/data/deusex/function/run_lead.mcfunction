# The gapless track needs a lead-in before the clock may run, and the lead-in has to be paid by
# something other than main_track.ogg itself.
#
# main_track.ogg is 546 s of audio. /playsound hands it to the client as a stream, and the client
# decodes four one-second buffers of it with pure-Java jOrbis before play() is ever reached
# (Channel.attachBufferStream -> pumpBuffers(4)), so the tick the track is fired on is not the tick
# the player hears. SoundBufferLibrary.getStream opens a fresh JOrbisAudioStream for every play and
# caches nothing, so the cost is the decoder, not the file.
#
# That cost is not a constant. Two recordings of this pack on the same machine, the same
# sounds.json, put the audible start at different offsets from the fire: the 1.0.19 footage gives
# +1.66 s (33.2 ticks, four independent 20 s windows agreeing on the track's own loudness envelope),
# the 1.0.18 footage gives +0.12 s. Cold and warm JVM - jOrbis runs interpreted until it is hot, and
# only the first streamed play of a session pays that.
#
# A fixed hold can only be right for one of the two, and holding 33 ticks was right only for the
# cold one: on a warm session the burst then landed 1.5 s AFTER the slam, which is what "not
# exploding at the beatdrop" was. So the hold is short (3 ticks, the warm number) and the cold part
# is removed instead of compensated - a 5 s silent stream of the same 44.1 kHz stereo format is
# fired first, 67 ticks ahead of the track. It is inaudible, but it is a real streamed play, so
# jOrbis and the OpenAL upload path are hot by the time main_track is fired and its own prefill
# costs what the warm session already measured.
execute if score #lead deusex matches 70 run function deusex:play_prewarm
execute if score #lead deusex matches 3 run function deusex:fire_track
scoreboard players remove #lead deusex 1
