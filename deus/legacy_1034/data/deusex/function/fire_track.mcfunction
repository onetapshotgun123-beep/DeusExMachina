# Hand the channel to the real track.
#
# The prewarm instance is stopped here rather than left to run out, because a second stream of the
# same length would still be holding a voice when main_track starts. play_chunk is the gapless path:
# with #full 1 and #idx 0 it fires main_track and nothing else.
stopsound @a * deusex:prewarm
function deusex:play_chunk
