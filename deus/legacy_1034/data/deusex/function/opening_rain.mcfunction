# The weather half of the drop, fired #rainlead ticks early - 104, which is 4 ticks more than the
# ramp costs. This is the switch the red sheet waits for: assets/minecraft/textures/environment/
# rain.png is red in this pack, so the drops themselves are blood from here on, with the sound, the
# wet sheen, the splash particles and FogRenderer's darkening that go with them. Nothing else can
# make a rain drop red - LevelRenderer.renderSnowAndRain binds that one path (line 327) and writes
# `.setColor(1.0F, 1.0F, 1.0F, f7)` into every vertex, with f7 = ((1 - d^2) * 0.5 + 0.5) * rainLevel
# (line 339), so the rain level is not just how WET it is, it is how VISIBLE the drops are.
# That is why this cannot live in opening_burst. ServerLevel.advanceWeatherCycle moves rainLevel by
# 0.01F a tick (ServerLevel.java:705-712) and nothing in a datapack can jump that cut, so forcing the
# weather on the drop tick made the explosion land on a sky at 1% rain: the downpour took another 100
# ticks, five full seconds, to arrive. Armed at #E 115 it is clamped at 1.0 four ticks before #drop,
# so the blood rain is already at full alpha on the tick the heart bursts, and the swell through the
# heartbeat section is the storm coming in rather than a switch being thrown.
# load.mcfunction keeps the world's own weather cycle off, which leaves this command as the only thing
# that can make it rain while the pack is installed, and #rain is the note that says the rain out
# there belongs to the show. 1.0.19 cleared the weather on the burst instead, which took the sky back
# to plain Minecraft a whole song too early; the ending (closing_start) is what clears it.
weather rain 1000000
scoreboard players set #rain deusex 1
