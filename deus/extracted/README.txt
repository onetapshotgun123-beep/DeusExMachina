Deus Ex Machina - NeoForge 1.21.1 (Heartbeat)
=============================================
Version 1.1.0

INSTALL
1. Minecraft Java 1.21.1 with NeoForge 21.1.x.
2. Remove older Deus Ex Machina JARs from your mods folder.
3. Put this JAR in the mods folder of the server and of EVERY client, then restart.
   The whole show runs in the client mod now: a player without the jar sees and hears
   nothing. There is no vanilla-client fallback. Update the server and all clients together:
   this build uses network protocol 2 and is not compatible with earlier 1.1.0 builds.

WHAT CHANGED IN 1.1.0
- Playtest readability pass (feedback: the sigils blocked the view and the red tint was
  stressful to play through). Every warning layer now draws at half strength - the ground
  sigils, seal rings, sweeping arcs, lock spikes, the lance's floating mark and its guide
  beam - while impacts keep their full brightness, so the moment something actually lands
  is still the moment it shouts. The red veil is painted at 40% of its baked intensity, the
  drum corners peak at 20 alpha instead of 36, the danger vignette is shallower and fainter,
  and the full-screen hit flash peaks at 70 instead of 120.
- Players glow so eyes find people instead of overlays: every player within 40 blocks
  carries a soft additive aura - the RONOVA bearer burns crimson, a player standing under a
  mark glows in the incoming attack's colour, everyone else keeps a faint cream ember - with
  a glint band sweeping the body every 1.6 seconds and a few rising motes. The glow fades
  out between 24 and 40 blocks and skips your own first-person body. It is drawn additively,
  so it lights the player without ever writing a solid panel over the view.
- The warning alerts are sharper but lighter: the HUD reticle is smaller and more
  translucent and gains countdown pips (one dot per second left, the newest burning white)
  above it; off-screen edge marks shrank; the wave banner's panel is fainter and carries an
  accent rule in the incoming attack's colour plus a glint sweep across the panel. The
  validator pins every one of these ceilings, so a future polish pass cannot quietly
  re-blind the player.
- The show moved out of the datapack into the client mod. Audio is decoded natively and
  driven by the sample actually being heard, so the timeline, lyrics, heart cutscene, wash,
  sky flash and rain stay locked to the music instead of drifting with server lag. The server
  is a thin orchestrator: /function deusex:start (and pause/resume/stop/loop) still work, handed
  to the mod through a scoreboard bridge.
- Natural weather is left alone. The world's weather cycle stays ON; the mod forces rain only
  while the show is past the drop and restores whatever was falling before it started. The red
  rain and the red sky are client mixins gated on the show, so a plain rainy day outside the
  event is plain white rain and a normal sky - the bug a friend reported against the old
  texture-override builds is gone for good.
- The 182 chunk copies, the entity sky panels, the title-slot wash and the lyric/wash/sky fonts
  are deleted. One streamed main_track.ogg replaces the chunk chain, so the jar is about 14 MB,
  well under the 30 MB ceiling.
- The storm: from 6 s after the drop, every non-boss player is marked in turn. A magic circle
  from the supplied sigil tracks their feet with a HUD reticle and edge marker, then pins to the
  ground for the last second - step out of it or take 12 damage plus Weakness, Slowness II and
  Blindness for four seconds. Four waves, then a 30 s rest. The boss is never marked: the banner
  reads "THE STORM SPARES YOU" instead.
- The bolt is the mod's own, not a vanilla lightning entity: a forked four-layer crimson discharge
  - faint haze, red, orange, white-hot core - that tapers toward the sky, with a ground bloom,
  radiating spark streaks and a short crater column under the strike. No LightningBolt is ever
  spawned, so the strike is event-red instead of blue-white.
- The marks now close as their fuse burns: the sigil's outer ring tightens, four arcs sweep around
  it, and a locked mark snaps a white inner ring plus twelve spinning radial spikes into place.
  Every impact expands a shockwave ring, and the lance's guide beam flares at the muzzle rather
  than drawing a hairline.
- The screen corners breathe with the drums. The build bakes a one-byte-per-tick kick envelope of
  main_track.ogg into assets/deusexmachina/show/beat.bin, and the HUD reads it at the sample being
  heard, so the flash lands on the real kicks and follows a seek. Four soft red corner washes ease
  in fast and out slow, capped at a hint of red and only during the song and burst phases - it is
  never a flashbang and never white.
- Between bolts the seal throws three more attacks, each telegraphed on the ground and named on
  the storm banner and HUD callout: BINDING SIGN (violet circle, roots you with Slowness VII,
  Nausea and Weakness for 3 s), SOUL SIPHON (blood-red ring, drains up to 4 health - never
  lethal - and heals the RONOVA bar's bearer 3 per victim) and EMBER BARRAGE (amber mark that
  bursts into three smaller bolts landing around you a heartbeat apart). All of them only mark
  non-boss players.
- SEAL LANCE now fires in formation: five chest-height lances every 8 seconds, starting 8 seconds
  after the drop. One aims at your chest and four surround it; all track together, pin for the
  last second and fire in unison after a 50-tick warning. Each beam deals 5 raw damage; staying
  in the centre takes all five. Phase 2 rearms every 15 seconds instead, with nine simultaneous
  lances dealing 9 raw damage each. Overlapping beams add into one hit before normal mitigation,
  so hurt immunity cannot erase the volley. There are no added debuffs; dodge the whole formation.
- Each attack has its own sigil in the world and on the HUD: the supplied rune seal for RED BOLT,
  shackles for BINDING SIGN, a blood vessel for SOUL SIPHON, a shattered star for EMBER BARRAGE,
  an aiming crosshair for SEAL LANCE, an inward spiral for CRIMSON VORTEX, and a split-diamond
  spike crown for RIFT ERUPTION. The seven masks share one texture atlas.
- CRIMSON VORTEX gives a 3-second warning, then deals 6 raw damage within 6 blocks and pulls
  victims inward. RIFT ERUPTION warns for 3 seconds, deals 10 raw damage within 3.5 blocks,
  and launches victims upward. Neither changes terrain; the boss is immune to both.
- After the first two solo bolts, storm waves combine two attacks: RED BOLT > SOUL SIPHON,
  CRIMSON VORTEX > RED BOLT, BINDING SIGN > RIFT ERUPTION, EMBER BARRAGE > RIFT ERUPTION,
  RIFT ERUPTION > SOUL SIPHON, and SOUL SIPHON > RED BOLT. Both marks are telegraphed;
  the second impact follows 24 active ticks (1.2 seconds) after the first. Phase 2 enables
  combos immediately. Pausing freezes their timers; reset, stop and boss death cancel them.
- Everyone who is not the boss is blessed for the whole event: Resistance I and Regeneration I
  are refreshed on every non-boss player each tick while the show runs, and the mod's copies are
  dropped the moment the event ends so nothing lingers afterwards. The boss is excluded - the
  RONOVA bar's own phase buffs are theirs.
- /deusex reset wipes the event in one go: storm marks are cancelled, boss bar, HP, wave count,
  phase and loop state are zeroed, the blessing and boss buffs are cleared and the action bar
  goes idle. It is meant for a botched setup between runs; health, items and advancements are
  left alone. /deusex start <player> <hp> still starts the show.
- Once the RONOVA bar enters phase 2 (half health) the sky answers much faster: waves come every
  70 ticks instead of 120, and the rest between volleys drops from 600 to 240 ticks.
- /deusex phase2 lets an operator (permission level 2) activate that phase during a playing
  event with a living, online boss. It activates the phase buffs and boss-bar effects without
  changing health or seeking the music, and shortens any pending storm rest. Lances still use
  the slower, stronger phase-2 cadence. The phase stays latched until reset or a new event.
- When the boss dies the show ends by itself: 40 ticks of flatline, then the storm is cancelled and
  the event closes. Every online player receives the challenge advancement "Server is finally
  Free.. At last." as the credits roll.
- Not changed: the song, the drop anchor, the lyric look and timing, the heart/burst art,
  the wash table itself (only its painted strength dropped), the volume slider in Music &
  Sound under Ambient/Environment, rejoin catch-up.

WHAT CHANGED IN 1.0.34
- The last chorus's first block (6:48-7:30, the part playing at 7:00) no longer shows its words
  about a second before they are sung. Four lines - the two "ずっと探していた", "心 満たされれば"
  and "それだけでいいのに" - carried times from the raw LRC that run 0.6-1.1 s early against the
  recording; they are re-measured from the shipped audio itself (415.10, 436.80, 447.45, 450.15).
  The block's other two lines and everything from 7:37 on were already on the voice and did not
  move.
- How it was measured: the vocal-band onset flux sampled at every line time of a section, shifted
  by a common lag, peaks at how much later the singing sits than that section's windows. The block
  peaked at +1.24 s while the sections either side sit at about +0.2 s (the method's own bias, a
  flux peak lands a little after the consonant), and the two repeated "ずっと探していた" phrases
  cross-check each other's spacing. After the re-time the block peaks at +0.18 s, in the same band
  as the rest of the song.
- validate_assets now runs that measurement on every build: a section whose lag is over 0.5 s and
  beats a shuffled-times null fails the build, so a future re-time cannot drift back unnoticed.
- Not changed: the audio, the clock, the fade ramp, the lyric look, the drop anchor, the rain, the
  wash, the sky flash, the slider, the rejoin catch-up.
- The jar is 27.4 MB, under the 30 MB ceiling.

WHAT CHANGED IN 1.0.33
- The slider shares Voice/Speech's row now - the empty right cell of the row under
  Players|Ambient/Environment - instead of adding a row of its own. The extra row left a hole in the
  left column and pushed Voice/Speech out of line with the pairs above it. The columns are back in
  line and the slider is still directly below Ambient/Environment, where it was asked for.
- Voice/Speech itself is the same widget as before; only its row was rebuilt around it to make room
  on the right. Its setting, tooltip and immediate apply survive the move - checked in a real client,
  where a click on it still moves the game's own voice volume - and the slider still keeps its
  percentage across sessions and applies to a running song the moment it moves.
- Not changed: the rejoin catch-up, the audio, the lyric clock, the drop anchor, the rain, the wash,
  the sky flash.

WHAT CHANGED IN 1.0.32
- Leaving mid-event and joining back no longer leaves you in silence until someone pauses and
  resumes the show. The gapless track is handed out once, to the players who were online when it
  fired; a client that leaves drops the stream with the world unload, and /playsound has no resume.
  warm_tick now marks a player whose join counter just started - new or rejoined - while the gapless
  show is running, and run_playing hands that mark the current chunk at the next chunk head. The
  chunks tile the same 60 tick grid the clock runs on, so the rejoiner lands on the same timeline as
  everyone else, at most one chunk (3 s) of the song behind. The mark is cleared after that one play
  and at every start, and the chunked (resumed) path never uses it because play_chunk already covers
  every player there.
- The song volume slider moved out of the plain Options screen's bottom-right corner into
  Options > Music & Sound, in the right column directly below Ambient/Environment. It is a row of
  the game's own option list, so it scrolls and resizes with the vanilla sliders; it keeps its
  percentage across sessions and still applies to a running song the moment it moves. The old
  corner is empty again.

WHAT CHANGED IN 1.0.31
- The drop is one moment now. The heart bursting, the red rain and the red screen wash used to arrive
  5 s and 2.5 s after the explosion; they land on the same tick as it.
- Why the rain was late, and why the fix is a lead rather than a faster ramp:
  ServerLevel.advanceWeatherCycle (ServerLevel.java:705-712) moves rainLevel by 0.01F a tick and
  clamps at 1.0, and LevelRenderer.renderSnowAndRain:339 writes that level into the alpha of every
  drop. Nothing in a datapack can jump the level - there is no command for it and no alpha in the
  texture to raise - so a storm forced on the drop tick is 1% wet on the drop tick and only arrives
  100 ticks (5 s) later.
- opening_rain is therefore armed 104 ticks early: load.mcfunction derives #rainlead from #drop
  (#drop - 104 = 115) so the two cannot drift apart, and opening_tick fires it once, while the
  heartbeat run-up is still playing, when #E reaches #rainlead and #rain is still 0. The game's own
  ramp does the rest and the level is clamped at 1.0 by the time the heart bursts. opening_burst no
  longer touches the weather at all.
- The soak measures the fix instead of restating it: tick 185 of the real game loop is the first tick
  with the storm up, the burst is tick 289 - exactly 104 ticks of lead - and the sky is wet on the
  burst tick itself. "Fires once" is proved by replaying that gate over #E 0..249, because the server
  only echoes the command it was handed and a weather command nested two functions deep prints
  nothing.
- Why the wash was late: tick.mcfunction only drew the veil from #ostage 4, and the cutscene did not
  reach #ostage 4 until opening_done, 50 ticks after the blast. The explosion played over a plain
  screen and the red arrived with the song proper.
- The fix is one title string rather than a faster gate. title_red_burst carries the veil cell
  (deusex:fx, $(rc)) and the blast cell (deusex:burst, $(burst)) in the same title packet, and a
  deusex:tspace glyph (\ue606, advance -1201) walks the pen back exactly one cell between them, so
  the blast is painted over the wash instead of next to it. The veil keeps the geometry the song has
  always used: cell pen -602 in a string of width -3, byte for byte the position title_red puts it
  at, and the validator compares the two pens instead of trusting this sentence.
- What is on screen is a cross-dissolve, not a cut. The blast is a white-out on the drop tick - 100%
  of the frame laid - and it thins as the wash climbs one level a tick: 81.1% at lv1, 65.5% at lv5,
  42.2% at lv11, 34.9% from lv14, which is the level the song holds. 51 ticks later opening_done
  resets the title and wash_draw repaints the same 34.9% cell, so the hand-over tile is identical to
  the burst tile. vid21/burst_strip.png is those eight frames plus the hand-over.
- opening_done also sets #wlast to -1. The reset erases the veil from the screen while wash_draw still
  believes it painted that level, and without the nudge nothing redraws it: the screen would clear to
  plain sky on the exact tick the song proper starts.
- The level maths has one home now. wash_level.mcfunction computes #lv = #tint * #wash / #washmax and
  the $(rc) glyph for it, and tint_draw, opening_flash and the burst title all read that. It was
  duplicated before, which is how the veil and the blast could disagree about which cell to draw.
- Not changed: the audio, the drop anchor (219), the song volume slider, the seamless start, the lyric
  clock, the red rain texture, the weather gate, the veil levels (14 held, 17 ceiling).
- The jar is 27.4 MB, under the 30 MB ceiling.

WHAT CHANGED IN 1.0.30
- The sky of the event is red instead of lavender-grey. The screenshot it was asked for measured its
  sky band at (109, 83, 100): red minus blue is +9, which is a grey with a hint of purple in it.
  The same frame with the new held wash is (118, 43, 54), +64, and the peak of a flash is
  (146, 16, 24), +122. vid21/skyred_1030.png is that one frame, three times: what 1.0.29 does, what
  this holds, what a flash spikes to.
- Why the sky was grey in the first place, and why it is not a texture: ClientLevel.getSkyColor
  multiplies the biome's sky colour by the time-of-day factor and then lerps it toward grey by the
  rain level, f7 = 1 - rain * 0.75. The show forces rain, so three quarters of whatever hue the sky
  had is gone before anything this pack paints is even composited. The biome JSON cannot answer it
  (sky_color is a required field of BiomeSpecialEffects, static per biome, so it would recolour
  plain afternoons too), and NeoForge 21.1 has no sky-box event to hook, only fog. What is left is
  the screen-space wash, which is drawn in the title slot and therefore reddens the sky wherever the
  player looks, including the zenith the in-world panels cannot reach.
- The numbers: #washbase, the level the song holds for the whole track, goes from 6 to 14 (12.2% to
  34.9% of the frame covered in the veil's red), and the ceiling #washmax / #tint goes from 16 to 17
  so a flash still has somewhere to go above a floor that is already red. 14 is the level where the
  drops, the disc and the lyric stay in the picture; 16 measures +97 and 18 +145, which is a red
  screen with no event left on it.
- A blink is therefore 12 ticks instead of 40: three cells of headroom at one level per 4 ticks,
  inside the 22 tick panel it rides on. The old 40 tick fall was long because it had somewhere to
  fall to; now it does not, and the tail of a flash is a flare settling back into a red sky.
- The opening's ramp up to the held level is 14 ticks (0.7 s) rather than 6, still inside the
  explosion. The ending is unchanged in shape and 4 ticks longer: closing_start drops the floor to 0
  and the drain walks 17 cells home, 68 ticks (3.4 s), and closing_end - the title reset that hands
  the game back - waits for it.
- /function deusex:test_wash now arms the spike from #washmax instead of a literal 10, because 10 is
  below the new floor and would have read as nothing happening.
- Not changed: the audio, the song volume slider, the drop anchor (219), the seamless start, the
  lyric clock, the red rain texture, the weather gate, the rain itself.
- The jar is 27.4 MB, under the 30 MB ceiling.

WHAT CHANGED IN 1.0.29
- The song starts the moment you run start. Before, "[Deus Ex Machina] Started" was followed by 3.5 s
  of silence on a black screen - the 70 tick pre-roll (67 ticks of an inaudible warm-up stream, then the
  song) - before the music and the heartbeat intro began.
- Why the silence was there: the first streamed sound of a client session starts about 1.5 s late
  (jOrbis is still interpreted), every one after it about 0.1 s. The pre-roll paid that cost on every
  start, although it is a once-per-session cost. It is now paid when a player joins: 60 ticks after
  joining, the same silent prewarm.ogg is streamed to that player once (deusex_wt counts ticks since the
  join; deusex_left, the leave-game statistic, restarts the count when someone rejoins, and load
  clears all counts). start counts the players online and, when every one of them has had 130 ticks
  (60 + the 70 the old pre-roll gave), arms the short 3 tick lead and fires the song at once.
- Falls back safely: if anyone joined less than 6.5 s ago the 70 tick pre-roll runs exactly as in
  1.0.28 and a grey line says why, so a cold client can never push the burst off the drop.
- The clock is unchanged: #E is 0 three ticks after the song is fired, the heartbeat beats, boom,
  burst and lyrics are on the same ticks of the music as before. The only thing that moved is how
  long you wait before the music begins.
- /scoreboard players set #quick deusex 0 brings the 70 tick pre-roll back for every start.
- Not changed: the audio, the song volume slider, the drop anchor (219), the looped replay (it still
  uses its own 70 tick lead).

WHAT CHANGED IN 1.0.28
- The song has its own volume. Esc -> Options now carries a slider in the empty corner to the right of
  Done, and it defaults to 45%. Its label is "Deus Ex music: 45%"; a window too narrow for that label
  shows "Song: 45%" instead, and hovering either one explains what it does.
- Why this needed a jar change rather than a datapack line: /playsound writes a fixed volume of 1 and
  cannot read anything back, and the sliders the game already has are shared with the rest of the world.
  The pack plays its music through the record category, which is the "Jukebox/Note Blocks" slider - that
  is why the song kept playing with Music turned off.
- The pack therefore ships five compiled classes for the first time, and the loader in
  META-INF/neoforge.mods.toml is javafml. The lowcodefml the data-only builds used never constructs a
  mod class, so Java sitting in that jar would do nothing at all, and say nothing either.
- What the classes do: every sound in the deusex namespace is wrapped on its way to the sound engine,
  and the wrapper reports the original volume times the slider at the moment the engine asks for it.
  Moving the slider therefore changes the song that is already playing, not just the next one. No sound
  outside deusex is touched, and the game's own master and Jukebox sliders still apply on top.
- The number is saved per client in config/deusexmachina-client.properties. It is a client setting: a
  dedicated server never loads these classes, and the mod still installs on the server as before.
- Not changed: the audio, the lyric clock, the drop anchor, the rain, the wash, the sky flash.

WHAT CHANGED IN 1.0.27
- The heartbeat intro is back on the song's real drop. The burst, the boom, the rain and the release all
  fire on tick 219 (10.95 s) again, not 319 (15.95 s). Measured on the original recording, the
  arrangement cuts to a 2 ms hole at 10.945 s and the whole band slams in at 10.947 s: sub-bass +52 dB,
  100-400 Hz +34 dB, mids +13 dB, highs +18 dB in one step. Nothing in the original happens at 15.95 s
  except a loop already playing at full level, so the 1.0.18-1.0.26 burst fired about five seconds after
  the drop.
- Why 1.0.18 got it wrong, and why this needed the audio rebuilt and not just a number changed:
  main_track.ogg and resume chunks 3-5 had been ducked by 18.6 dB from 10.3 s to 14.4 s, with a ramp
  back to full volume ending at 15.5 s. That buried the real hit (it was 19 dB quieter than the original)
  and made the first full-level "slam" in the shipped file the end of that ramp, which is where the
  anchor was then put. The heartbeat table, the boom and the cutscene were all synced to the edited
  audio, not to the song. Setting #drop back to 219 on its own would have fired a boom over a drop nobody
  could hear.
- main_track.ogg and chunk_3/4/5.ogg are rebuilt from the original recording. The only shaping kept
  is the lead-in duck the intro was designed around: a linear fade from 9.79 s to 10.30 s down to
  -18.6 dB, held until the 2 ms hole at 10.945 s and released inside it, so the drop itself plays at
  the original's level (checked: -8.8 dB RMS in the first 100 ms after the hit, original -8.8 dB, the
  1.0.26 file -27.4 dB). Sample counts are unchanged (24075264 for the track, 132300 per chunk) and the
  new track is sample-aligned with the original (0 samples of lag), so the 60-tick chunk grid and
  the lyric clock are untouched.
- Side effect: the old main_track.ogg also had a 0.4 s dip of up to -6 dB at the head of every 3 second
  chunk for the whole song (the chunk head dip rode into the gapless track). The rebuilt track
  is cut straight from the recording and does not have it. The other 179 resume chunks are unchanged,
  so a resume still has that dip at each chunk boundary, as before.
- The beat table is re-timed for a 146 tick run-up instead of 246: eight beats at ticks 50, 84, 114,
  140, 162, 178, 188 and 196 (gaps 34, 30, 26, 22, 16, 10, 8). The last beat still lands 23 ticks
  before the drop so its tail is gone before the slam, boom_rise still starts 7 ticks ahead of it, and
  opening_burst still cuts the heartbeat by name.
- Not changed: the pre-roll, the prewarm, the lyric clock, the red rain, the wash, the flash and the
  ending. The sync is as good as the client's audio start latency: the tick clock follows the music
  by the lead-in measured in run_lead, and that latency can still vary by a tick or two between
  sessions.

WHAT CHANGED IN 1.0.26
- The red specks in the air are gone. blood_rain, flash_rain and the test_rain that forced them are
  deleted, and the two tick.mcfunction lines that called them with them, which takes the pack to no
  /particle command at all. What you were seeing was `minecraft:dust` at scale 2.6 and 2.4 - 38 of
  them a tick for every tick of the song's rain, and 23 more per blink while the sky panel was lit.
  They were added in 1.0.19 as the depth a flat billboard field has none of, and they survived the
  1.0.25 return of the red rain sheet even though the 1.0.18 jar this build is measured against has
  no /particle line in any of its 71 functions. The drops you want are the texture; the motes were a
  second, coarser rain drawn over the real one.
- Removing them also removed the only command in the tick loop that can throw on the world. A
  /particle box that lands in a chunk the server has not loaded fails, and a failed command stops
  every line after it in the same function - which is the same class of bug as the panel kills fixed
  in 1.0.25, and is why these two lines had been parked at the very foot of tick.mcfunction, under
  the HUD, so the worst they could cost was a tick of weather. There is nothing left down there to
  protect now.
- The validator refuses the shape rather than tuning it. validate_assets.py used to spend about 130
  lines checking that the dust lines were forced, heading-kept, red enough, big enough and inside
  the camera frustum; it now walks every shipped function for a `run particle` and errors on the
  first one, and errors on the three deleted names reappearing or still being called from the tick -
  a call to a function that is not in the pack is resolved while the datapack loads, so it would
  take the whole tick loop down with it rather than quietly doing nothing.

WHAT CHANGED IN 1.0.25
- The rain is red again, the way 1.0.18 had it. The pack ships assets/minecraft/textures/environment/
  rain.png in red - 401 of its 4096 pixels inked, alpha-weighted rgb (171, 19, 27) - because
  LevelRenderer.renderSnowAndRain binds exactly that path and then writes `.setColor(1.0F, 1.0F,
  1.0F, f7)` into every vertex. A rain drop has no tint of its own anywhere in the game, so that
  sheet is the only thing that can ever make one red. 1.0.23 took it away and 1.0.24 tried to
  replace it with a deeper screen wash plus more motes; neither looked like the old build, because
  neither was the falling water.
- The bug reported against that texture is still fixed, and the gate moved from the colour to the
  weather. An override cannot be conditioned on anything - no score, no tag, no state - so the pack
  takes the question apart instead: the last lines of load.mcfunction set `gamerule doWeatherCycle
  false` and clear any sky that is already raining while the show is not running, which leaves
  opening_burst as the only command that can make it rain while this pack is installed. #rain is the
  pack's note that the rain out there is its own, and the first block of tick.mcfunction clears the
  weather on the first idle tick that still finds the flag up - the one case the exit paths cannot
  cover, a show that let go of the sky without clearing it. Red rain therefore appears only while
  deusex:start owns the world. The cost is that a world with this pack installed never rains on its
  own; that is the only trade a data-only pack can make here, and it is what buys both halves of the
  request.
- There is no predicate in that gate, even though `execute if predicate` reading a
  `minecraft:weather_check` condition is the natural spelling - 1.21.1 has no weather factor of its own
  (execute if/unless knows biome, blocks, data, dimension, entity, function, items, loaded, predicate,
  score and success). It throws. The headless soak answers "An unexpected error occurred trying to
  execute that command" for the datapack id, for the same condition written inline, from the console,
  from inside a function and positioned over a loaded block, because ExecuteCommand.checkCustomPredicate
  builds a loot context around a command source only a real player fills in completely. A throw is
  worse here than a wrong answer: it stops the rest of tick.mcfunction, and the rest of tick.mcfunction
  is the show. The flag costs two score tests an idle tick instead.
- Why the gate was not enough on its own: /kill takes an entity argument, and EntityArgument
  .getEntities (1.21.1) throws argument.entity.notfound.entity the moment the selector matches nothing.
  Inside a function that is not a polite "no" - it stops every line below it and takes its caller with
  it. Six of these cleanups shipped in front of the work that mattered, and the sky almost never holds
  a panel to clear, because flash_frame kills the set at #fframe 0:
    * halt killed the panels ahead of `weather clear` and the #rain disarm, so every stopped show left
      the world raining red - the exact thing the author's friend reported, and the reason the first
      attempt at the gate above read as if it did not work.
    * load killed them ahead of the three lines that own the weather, so a fresh world came up with the
      world's own cycle still running.
    * flash_begin killed them ahead of flash_player, which is the only thing in the pack that summons a
      panel - so the abort left nothing to kill on the next pass either, and the random red sky flash
      was dead from the first frame of the first song.
    * finish killed them ahead of closing_start, so the ending never started: the veil held its full
      depth and the rain held with it.
    * do_pause and start each killed them ahead of #fframe 0 and of the whole of start.
  Every cleanup is now `execute if entity @e[...] run kill @e[...]`, which reads the same selector
  through getOptionalEntities and so treats an empty sky as nothing to do, and each one sits at the
  foot of its file or after the writes it used to be able to swallow. start's is gone altogether:
  halt already clears the panels, and a cleanup that had nothing to clear was the only thing standing
  between /function deusex:start and the show. validate_assets now refuses a naked `kill @e[`, checks
  that halt/load/finish/do_pause end on theirs, and that flash_begin ends on flash_player.
- The veil goes back to the depth 1.0.22 shipped, which is the one measured against the red sheet:
  #washbase 6 and #washmax / #tint 16. Over the sheet, cell 6 scores sky +21 / horizon +26 / ground
  +33 against the 1.0.18 recording's +23 / +20 / +31 plateau. 1.0.24's floor of 14 and ceiling of 19
  were calibrated for a world of white drops and put the composite well past the reference once the
  sheet came back.
- A blink is 40 ticks again (16 down to 6 is 10 levels at one per 4 ticks), so a flash reads as a
  blink in a sky that is already red rather than as the whole screen going red and back. The ending's
  fade out is the 64 tick drain, which is still the hand-over to plain Minecraft.
- The blood motes stay - 38 a tick, still aimed into the camera's frustum rather than over the
  player's head - but their job changed: they are the red hanging in the air in front of the camera,
  the depth a flat billboard sheet has none of, not the colour itself.
- validate_assets now refuses a build that ships one half of this without the other. No rain sheet, a
  sheet that is not red or barely inked, any other file under assets/minecraft, a load that leaves the
  world's weather cycle running or an idle sky raining, a tick without both gate lines, #rain armed
  before the weather is set or left up by halt or closing_start, and any `if predicate` in any
  function - which is the spelling that throws - are each an error. The held veil level is checked
  against whichever of the two colour sources actually shipped: 5-7 with the sheet, 13 or deeper
  without it.
- 1.0.24 (Screen-Turns-Red) is superseded by this build; delete it from the mods folder.
- The jar is 27.4 MB, under the 30 MB ceiling.

WHAT CHANGED IN 1.0.24
- The screen turns red. 1.0.23 held its veil at #washbase 9, which lays 18.0% mean alpha over the
  frame; over a rainy grey world that is a cast, not a colour, and the report from the real game was
  "the screen didnt turn into red". The held floor is now 14 (34.9%) and the flash ceiling is the top
  cell of red_lv.png, 19 (92.2%). #washmax and #tint both moved to 19 so that wash_draw's
  #tint*#wash/#washmax still paints exactly one cell per level. Measured off the rendered frame: the
  held state scores sky +59 / horizon +64 / ground +69 in the red band against the 1.0.18
  recording's +23 / +20 / +31 plateau, and a flash peaks at +167.
- The red rain texture did NOT come back, and this is the reason. LevelRenderer.renderSnowAndRain
  binds one hardcoded path, minecraft:textures/environment/rain.png, and writes
  `.setColor(1.0F, 1.0F, 1.0F, f7)` into every vertex, so the sheet is the only hue there is and a
  resource-pack override cannot be conditioned on a scoreboard, a weather state or anything else.
  Shipping it again would make plain rain outside deusex:start blood again - the bug reported in
  1.0.23. This build therefore puts the colour where the datapack can gate it: the veil, which the
  title slot paints over the world and the drops alike, plus the motes it owns.
- A blink is 20 ticks instead of 28. #washmax 19 down to #washbase 14 is 5 cells of headroom at one
  level per 4 ticks, which is two ticks shorter than the 22 tick panel it rides on. That is the price
  of a floor this deep: the panel now dies into a screen that is still a third red rather than into
  plain Minecraft, so the tail of a flash is a fade between two reds.
- The ending's fade out is 76 ticks (3.8 s) rather than 64, because closing_start drops the floor to
  0 and the drain walks all twenty cells home. closing_tail waits on #wash 0 before it will run
  closing_end, so the hand-over to plain Minecraft is that drain and nothing else.
- The downpour is a little thicker: 38 motes a tick rather than 34, still inside the 40 the
  validator allows per player per tick.
- The lyric stays readable at the held level - vid21/veil_hud.png draws the real actionbar over
  lv14, lv16 and lv19 side by side. At the very peak of a flash, for the first ticks while #wash sits
  on 19, the word is under 92% red. That is what the flash is.
- The jar is 27.4 MB, under the 30 MB ceiling.

WHAT CHANGED IN 1.0.23
- The rain outside the event is plain Minecraft rain again. The jar used to ship
  assets/minecraft/textures/environment/rain.png in red, and LevelRenderer.renderSnowAndRain binds
  that one path for every rainy frame in the world - it writes `.setColor(1.0F, 1.0F, 1.0F, f7)` into
  every vertex, so the sheet is the only hue there is and a resource-pack override cannot be
  conditioned on a scoreboard, a biome or anything else. Every rainy afternoon anywhere in the world
  was blood. The pack no longer touches vanilla assets at all (validate_assets walks for it and fails
  the build on the first file it finds), and the event draws its own downpour instead: blood_rain's
  two forced dust lines run only inside the same window as the flashes and the veil - #state 1,
  #cstate 0, #ostage 4 and higher - so the red starts on the beat drop and stops the tick the ending
  takes over.
- The mote boxes aim into the camera, not at the player. The first cut hung them 14 blocks over the
  head and centred them on the player, and at a 43 degree vertical FOV a mote has to stay under
  0.39 x its own distance to be on screen at all: the renderer counted 6 of 176 reaching the frame.
  The shipped lines sit 8 and 5 blocks up at 28 and 15 blocks ahead, and 199 of 374 land in view.
  validate_assets checks that inequality per line, so a sheet nobody can see cannot ship again.
- The colour the texture used to supply now comes from the veil, so #washbase went 6 -> 9. Cell 6
  measured +21/+26/+33 only because the backdrop it was scored against already had the red sheet in
  it; over vanilla's white drops the same cell falls to +7/+13/+23. Level 9 gives +22/+27/+35 with
  the motes, against the 1.0.18 recording's +23/+20/+31 plateau. A blink still swings to the full
  #washmax 16 and bleeds back down to 9 over 28 ticks, longer than the 22 tick panel it rides on.
  Superseded by 1.0.24: +22/+27/+35 on this metric is still not a red screen, and the player holding
  the jar agreed.
- The lyrics and the heart burst land where the music is. The old lead-in held the clock 33 ticks
  before firing the track - a number measured off a cold first play. The client decodes four
  one-second buffers before a streamed sound starts (Channel.attachBufferStream -> pumpBuffers(4)),
  and that cost 1.66 s on the first play of a session and 0.12 s on every play after it. A fixed hold
  can only fit one of the two, so the warm runs - most sessions - were about 1.5 s late, which is how
  the words drifted and the heart stopped exploding on the drop. start now arms a 70 tick lead: tick
  70 fires a silent 5 s streamed prewarm that puts the decode path through its work, tick 3 fires the
  real track, and the clock starts 3 ticks after that, at the warm latency. A cold session gets 67
  ticks of headroom, a warm one 3, and both end up within about 0.02 s of the audible music. #E is
  the audio clock, and the burst, the heartbeat stop and the explosion all read it, so this is also
  the cutscene timing fix.
- The lyric does not move when the disc HUD glitches. hud_show, hud_show_box and lyric_only each
  centre the word with their own pad glyphs, and lyric_only's pair sat 74 px off the other two, so
  every frame that swapped between them slid the word sideways. Its pads are now the same pair, and
  validate_assets measures the centre of $(lyr) in every actionbar frame that carries it and fails
  the build if any two disagree by more than 1 px. hudview reports 405 px for all three frames across
  all eleven glitch presets.
- The jar is 27.4 MB, under the 30 MB ceiling.

WHAT CHANGED IN 1.0.22
- The red sky now holds instead of blinking, which is what "the sky is stay normal" was about. The
  veil has a floor, #washbase, and opening_burst raises it to 6 on the beat drop. wash_tick walks the
  screen up to that floor one level a tick and refuses to drain below it, so from the burst to the
  ending the world is tinted red continuously; each random flash still spikes to the full #washmax
  16 and bleeds back down over 40 ticks, so a blink sits on top of a red sky instead of being the
  whole of it. closing_start drops the floor to 0, and that last 64 tick drain is the transition
  back to plain Minecraft.
- Why 6 and not some other number: the 1.0.18 jar pointed at as the reference was measured frame by
  frame. Its sky band steps from -65 (plain blue) to a flat +19..+26 and holds there for the whole
  60 s of song. Rendering cell 6 of red_lv.png over a rainy backdrop gives +21 / +26 / +33 against
  that +23 / +20 / +31, and cell 16 gives +110, which is where the same recording's burst frame sits.
  1.0.18 itself aimed at #tint 7, but its hud_sky draw wrote a storage key nothing reads, so the
  held red was never actually painted - this build copies that jar's picture, not its code.
  (That +21/+26/+33 was scored over the red rain sheet this jar still shipped. With the sheet gone
  the same cell reads +7/+13/+23, which is why 1.0.23 holds 9 instead.)
- Blood rain needed no new code and is now provably on for the whole song: both jars ship the same
  red environment/rain.png (identical md5), and opening_burst's `weather rain 1000000` is what makes
  the client draw it. What changed is that nothing clears it until the ending.
  (Superseded by 1.0.23, and this is the line that caused the bug a friend reported: a texture the
  client binds for every rainy frame cannot be turned off when the event is not running.)
- halt does its scoreboard work before anything that needs a level, for the same reason flash_begin
  was reordered in 1.0.21: a command that throws stops the rest of its function, and a halt that
  stopped at `kill @e` would leave the held floor standing - a red screen after the show is over.
  halt now zeroes #washbase and repaints at cell 0, whose mean alpha of 3/255 is the same as nothing.
- The soak gained a VEIL-BASE walk: the drain stops on the floor and never under it, and a veil left
  at 0 climbs back to it one level a tick. The live tick walk latches the tick the floor is first
  reached (357, five ticks after the burst) and reports VEIL_UNDER_FLOOR for any later tick below it;
  across 1200 live ticks there were none. Every number the veil and flash probes compare against is
  now read out of the shipped functions instead of hardcoded, which is how a re-timed envelope used
  to keep passing a soak while the screen showed something else.
- /function deusex:selftest prints the held floor next to the live veil level, so "is the sky
  supposed to be red right now" is one number instead of an argument.
- No timing, audio, lyric or glyph values changed in this build.

WHAT CHANGED IN 1.0.21
- This build exists because the last one was declared fixed and was not, and there was no way to
  find out which part was lying. Nothing in the pack could be seen from the outside: a red sky that
  is not red, a beat a second off, and a title that never reaches the client all look identical on
  a scoreboard, so every release so far was verified by replaying the functions in Python and on a
  headless server, which is exactly the kind of proof that cannot fail in the way it actually did.
- /function deusex:selftest prints the live state in chat, and the build id with it, so one command
  says both which jar is installed and what the pack thinks it is doing: how many times the game
  loop has run since the last start, which stage the opening is in, #E and the chunk position and
  the lead-in, how many heartbeats fired, how many flashes were armed, how many sky panels are
  alive right now, the veil level next to the cell it painted and the ceiling it is scaled against,
  and which lyric line is current. Run it about half a minute into the song.
  The reason all of those are in there: the flash, the veil and the rain are each gated on
  #state 1 and #cstate 0 and #ostage 4 and higher, so one stuck stage turns all three off at once
  and looks exactly like a mod that does nothing. #tk is the first thing to read - if it does not
  climb once per game tick, the tick loop is not running and nothing else matters.
- /function deusex:test_wash and /function deusex:test_flash force one mechanism each, on demand,
  without waiting for the 8 to 21 s scheduler. They are separate because the two red things are made
  of two different subsystems - the sky panel is an entity in the world, the wash is a title drawn
  from a bitmap font - and they fail for different reasons that no log can distinguish from the
  player's side. The drops are neither: they are a texture, and a texture cannot be fired on demand.
- flash_begin now does its arithmetic before anything that needs a level. A command that throws
  stops the rest of its function, and the line that killed the old sky panel sat in front of the
  line that raises #wash, so one bad entity write cost the whole screen its red. It also means the
  soak can prove the flash raises the veil instead of setting #wash by hand.
- The soak has a new walk that runs tick.mcfunction itself 1200 times, with nothing armed except
  what start arms, and reports the tick at which each opening stage is first reached, whether the
  heartbeat fires the table's ten beats in a live run, and whether the veil was raised by anything
  other than the test file. The older sections all pass a piecemeal state, which is how 1.0.19 and
  1.0.20 both shipped green.
- The build id in selftest is checked against the loader's version, along with the README version,
  the changelog order and the name the build script writes, so this file cannot claim to be a build
  it is not.
- No timing, audio, lyric or glyph values changed in this build.

WHAT CHANGED IN 1.0.20
- The red rain and the red sky are back, and they were missing for three separate reasons, each of
  which is now asserted by the validator instead of assumed:
  * flash_spawn planted the glow panel with `rotated ~ 0`. `/execute rotated A B` takes pitch first
    and yaw second, so that line kept the player's pitch and forced the yaw to due south: look at
    the ground and the panel went 54 blocks into the floor. It is `rotated 0 ~` now, which flattens
    the pitch and keeps the yaw, so the glow is in the sky whichever way the player is looking. In
    the rendered first-person model it covers 100% of a 1280x720 frame from +43 degrees elevation
    down to -3 and +-57 degrees across, at camera pitch -40, -10, +12 and +40, and the 26 block
    fallback for an unloaded chunk covers 100% as well.
  * Nothing raised #wash while the song played. The veil had only ever been raised by the ending, so
    the sky could flash red over a perfectly plain world. flash_begin now puts #wash at full on the
    same tick it arms the panel: one event, two halves - the sky lights, the screen bleeds red, and
    wash_tick takes 40 ticks to fade the second half out after the first one dies.
  * There were no particles at all. flash_rain is two `execute ... rotated 0 ~ run particle
    minecraft:dust{...} ^ ^n ^m ... force @s` lines gated on #fframe 21.., which is the bright half
    of the envelope: 23 motes a tick for the nine ticks the gate is open, 207 per flash. Both say
    `force`, because ServerLevel.sendParticles drops a normal particle more than 32 blocks from the
    player and /particle then reports the tick as a failure. The colors are 1.0/0.05/0.05 at scale
    1.8 and 0.9/0.03/0.08 at 1.1 - blood, not confetti.
- The veil is stronger and no longer optional to notice: #tint is 10, not 7. In the render model 7
  lays 14% red over the frame, which disappears as soon as the player looks at the ground; 10 lays
  20% and the lyrics are still legible under it, which matters because Gui.java registers the
  actionbar before the title, so the wash paints over the words. It is also set on load rather than
  guarded, so a world that cached 7 picks the new strength up on /reload. At 10 it equals #washmax,
  which makes the painted cell track #wash one for one and the drain walk through all eleven cells.
- The intro heartbeat stops before the drop, and the clock says when the music actually is.
  * main_track.ogg needs 1.64 s to decode - about 96 MB of PCM - before its first sample reaches the
    mixer. Measured on the 1.0.19 evidence recording: four independent 20 second windows match the
    track's own loudness envelope at 0.989-0.994 and put #E=0 at file time +24.36 s, while the small
    heartbeat files, which start the tick they are fired, put #E=0 at +22.72 s. The tick clock was
    therefore 33 ticks ahead of the music and everything keyed to #E inherited it, so the heart
    exploded during the silence before the slam. That reads exactly like "the heartbeat does not
    stop at the beatdrop". run_lead now fires the track and holds #E at 0 for those 33 ticks.
    (Superseded by 1.0.23: 1.64 s is what the decode costs on a *cold* first play, and a warm replay
    of the same session pays 0.12 s, so a fixed 33 tick hold was right once per session at best and
    1.5 s late the rest of the time. See the lead-in and prewarm in the 1.0.23 notes.)
  * The hand-over was a tick short of that, and finding it needed the server: tick.mcfunction tested
    `#lead 1..` before `#lead 0`, and every execute head re-reads the scores after the line above it
    has run, so the tick that counted #lead from 1 down to 0 also started the clock in the same tick.
    32 ticks of hold, one tick of the measured decode time spent waiting for nothing. Reordered. The
    validator's clock replay used to pick the path itself (`run_lead if #lead >= 1 else run_playing`),
    which is exactly the exclusivity the bug broke - it could not have failed. It now replays
    tick.mcfunction's own two gates, in the order they ship in.
  * run_playing re-fired main_track on that hand-over tick, because #t is still 0 there and the
    chunk-head fire was ungated. Two instances of the same 546 s recording starting one tick apart is
    a flam over the whole intro. It fires only while #full is 0 now, and the chunk sounds it skips
    are silent by design.
  * The last heartbeat lands 23 ticks before the drop and heartbeat.ogg is audible for about 22, so
    the thump is gone at #E 318 with the slam at 319. opening_burst also stops the heartbeat by name
    - a beat fired on the way down would still be audible over the explosion - and takes #ostage to
    3, which is what keeps the beat table running after the drop.
- Proof, on a real 1.21.1 dedicated server. The ten beats fire at #E 50, 88, 124, 156, 184, 228,
  252, 273, 288 and 296 and nothing between #drop and #drop+24 fires one. The clock walk holds #E at
  0 for 33 ticks, then moves one per tick, and play_chunk fires exactly twice over a full pass: the
  tick the hold is armed and the wrap, at tick 10951 of a 10919 tick song. Twelve flash delays all
  land inside 160..420 and every envelope closes. The veil drains ten levels in forty ticks with no
  level lost early, repaints exactly eleven times for the eleven levels, never paints a cell that is
  not the level it carries, does not repaint at all when the level has not moved, and clamps #wash 99
  to the ceiling before lv_char is ever asked for a glyph the font does not have. The burst walks to
  frame 15 and #ostage reaches 4, so the title is dropped 50 ticks after the slam. The lyric list is
  444 entries and the fade ramp is unchanged.
- The soak itself had to be fixed before any of that meant anything. tick.mcfunction drains #wash on
  any tick where it is above zero - not only while the song plays - so a world that keeps ticking
  steals levels from a scripted walk and the drain rate is unknowable, and the game's own
  run_lead/run_playing did the same to the clock. The deterministic half of the walk now runs under
  /tick freeze, which leaves the scripted calls as the only thing that moves state. And the veil's
  repaint is detected by poisoning deusex:data rc with "!" and asking the server whether the key
  still *matches* that value: storing a one character string out of a data-get answers its length,
  not its codepoint, so every cell in red_lv's run read back as 1 and the old numeric test could not
  tell a repaint from none. The "46 repaints" was a harness lie, not a mod bug.
- The caveat about that server is unchanged: a console source has no level, so summon, kill @e and
  anything addressed to @a throw there - 44 of those lines, all of them in the two flash sections
  and none in the veil, dust, clock, beat, lyric or burst sections. What the soak proves is the
  arithmetic, the schedule and the stage machine. The panels, the motes and the veil are verified
  where they are actually seen: skyview.py lays the shipped glyph geometry and every alpha onto a
  1280x720 frame, and hudview.py renders the actionbar the way 1.21.1 does, with 0 missing glyphs.
- Nothing about the audio changed. Still 26 MB, still one vorbis quality setting for main_track and
  the 182 chunks alike.

WHAT CHANGED IN 1.0.19
- The lightning is gone. No bolt, no strike, no thunder, no storm scheduler: 65 functions ship and
  the validator fails the build if the words bolt, strike, thunder or lightning survive anywhere in
  them. The sky now does one thing - a red flash at an interval nobody can predict.
- The flash is a single glow panel per player, summoned 54 blocks out along your own sightline with
  the pitch forced to zero, so it sits in the sky whether you are looking up or at your feet. It is
  drawn from the new skyglow font: densest along its bottom edge and fading upward, so the horizon
  catches fire and the zenith goes pale instead of the whole dome turning one flat red rectangle.
  Terrain occludes it (see_through is off), and if 54 blocks is not loaded the same panel is placed
  at 26 blocks instead. 30 ticks: 70, 140, 200, 255 alpha over the first four, then a linear decay
  to nothing, and the panel is killed on the tick it reaches zero.
- 8 to 21 seconds between flashes, computed rather than rolled. /random and /time need a level, and
  the tick loop runs as a source that has none, so a function that used them stopped before the line
  that rearms the flash. A wrapped 31-bit LCG in scoreboard arithmetic gives the same spread with no
  level dependency, and its 2^32 period and the odd increment mean the seed at zero is not a fixed
  point. load.mcfunction only seeds it when it is unset, so a world keeps its place in the sequence
  across restarts instead of flashing on the same beats every time. Over five simulated minutes: 20
  flashes, delays 186 to 411 ticks, 19 distinct values.
- flash_frame now counts down and kills the panel as its first two lines, before the alpha writes.
  A command that throws stops the rest of its function - proved on the test server, where one bad
  entity line froze the envelope at frame 30 forever - so the bookkeeping happens while it still can
  and a failed write can only cost a frame, never leave the sky lit.
- The heart now visibly explodes at the drop. The burst is 16 new full-screen frames built from one
  heat field through a fire ramp - white core, orange shockwave, red filaments on the front, embers
  behind it - and it is the same 1200x600 font units as the red wash it replaces, so no edge of the
  screen is left unlit and the blast does not read as a rectangle. Measured in the render model: 91%
  of the viewport inked on frame 1, down to 1% by frame 15.
- The burst reaches its last frame and holds it. It used to cut out at frame 8 because the pacing ran
  off the wash counter instead of the blast; it now paces against #E - #drop, so 50 ticks after the
  slam the title is dropped outright and the game is plain Minecraft again. Verified tick by tick on
  a real 1.21.1 dedicated server: the frame index walks 1,2,2,2,3,3,3,4 ... 15,15,15,15,15,15,15,15,15
  and the stage counter reaches 4, which is the reset.
- That reset was blocked by a function that never loaded. flash_spawn had two lines beginning with
  $ but containing no $(...), and a macro line with no variables makes the server refuse the whole
  function - so nothing the flash tried to summon existed. Both lines are fixed and the validator now
  rejects any function that mixes up the $ prefix, in either direction.
- The delay arithmetic is proven the same way twice: the shipped flash_begin replayed in Python and
  run on the real server produce identical values (the thirteenth flash is 333 ticks in both), and
  the 1.0.18 beat schedule, lyric fade ramp and 444-entry lyric list still pass on the server.
- One caveat about that server test: a headless console source has no level, so summon, kill @e, and
  anything addressed to @a throw there. What the soak proves is the score arithmetic, the schedule and
  the stage machine; the panels themselves are verified in the rendered first-person model.

- The JAR is 26 MB instead of 43 MB. The pack has always carried the song twice: main_track.ogg is
  what `start` plays, and 182 three-second chunks are what a resume plays, because /playsound cannot
  begin partway through a file. The two copies were cut at different rates - main_track at 176 kbps
  and the chunks at about 400 kbps, so the copy nobody normally heard was nearly three times the size
  of the copy everybody does. Both are now encoded at one vorbis quality setting (level 0.4), which is
  158 kbps on main_track and about 183 kbps median on the chunks: matching the setting rather than the
  number is what guarantees a resume cannot sound weaker than the opening. 22.1 MB of audio in total.
  What did not change is the length: every file still decodes to the same number of samples, and the
  validator reads those counts out of the shipped files and refuses the build if any chunk is off the
  60-tick grid the lyric clock (#E = #idx * 60 + #t) is built on, if the sample rate or channel count
  drifts, if sounds.json names a file that is not in the pack, or if the chunks stop adding up to
  main_track's length. The pre-encode originals are kept under backup/sounds_originals.

WHAT CHANGED IN 1.0.18
- The heartbeat intro now lands on the real drop. The burst was anchored at 219 ticks (10.95 s),
  which is where the bass first enters, while the song's actual slam is at 15.95 s - the only
  sustained full-band jump in the first 16 seconds of main_track.ogg. #drop is now 319, and it is
  set outright instead of "unless already set" so a world that cached the old value picks the
  correction up on /reload. The eleven beats now accelerate from 38 ticks apart down to 10, with a
  deliberate pause across the 10.6-10.9 s hole where the arrangement drops out, and the 7 tick
  inhale rise ends exactly on the drop tick so the boom lands on the slam. Verified on a real
  1.21.1 dedicated server: walking #E from 0 to 400 through opening_hb fires a beat at 50, 88, 124,
  156, 184, 228, 252, 272, 289, 300 and 310 and at nothing else.
- The lyric is the 1.0.16 design again. The dark plate from 1.0.17 is gone: plain Japanese over
  English, no box behind it. It is far easier to read than either old version because the kana is
  now pure white, the English is brighter and at full alpha, the text carries a thin 3 px outline
  instead of a plate, and the cell is still drawn 1.25x larger with its bottom edge exactly where
  1.0.16 had it.
- The lyric fade no longer trails the singing. Lines are only 46-68 ticks long, and the old ramp
  spent 16 ticks fading in and 20 fading out with its first three levels under 70% alpha - so a
  line only became readable about a second after you had already heard it, which is what read as
  "the lyrics are not in sync". The ramp is now 6 ticks in and 8 out with alphas
  0/120/190/230/250/255, and 86% of every line's window is at full opacity. Confirmed tick by tick
  on the server: the picked glyph walks 0,1,2,3,4,5, holds, then 4,3,3,2,1,0.
- The lyric timings themselves were checked against the recording before anything was changed, and
  they were already right: the file is 545.92 s against the source's 546.0 s, the 218.98 s section
  break matches a measured break in the mid and high bands, and the verse repeat period measures
  82.75 s where the timing sheet says 82.78 s. The words were on the right beats; only the way they
  faded made them feel late.
- The lyric generator now refuses to write the fade if load.mcfunction does not define its
  constants. A scoreboard operand that does not exist makes the whole operation line fail silently,
  which would freeze the fade at whatever value it last held.
- Revalidated: 444 lyric glyphs, 0 errors and 0 warnings, and no missing glyph box anywhere in the
  actionbar.

WHAT CHANGED IN 1.0.17
- The lyrics now reach the screen at all. The 444 entry lyric list is written as one command over
  many lines, and its last line was missing the trailing backslash, so the closing "]" became a
  command of its own and the whole list failed to parse at load. The game then had no lyric to
  pick and every subtitle stayed blank. Confirmed on a real 1.21.1 dedicated server: the list now
  loads with all 444 entries and a mid-song tick resolves the exact glyph it should show.
- The lyric is a subtitle bar instead of faint text. Each line is drawn on a dark plate with an
  outline, Japanese above English, and the whole cell is 1.25x larger than before, so it stays
  readable over a bright sky. The cell is rasterised at 256 px because a font page wider than that
  is silently replaced by the missing glyph box, which is why an earlier attempt at a bigger lyric
  showed up as "[]".
- Lightning is a strike, not a smudge. One strike is now three quads: a sky wide wash 2.6x its own
  distance across, a corona around the bolt, and the bolt itself. It runs from just under the
  skyline up past 44 degrees, so only the middle of it fits on screen and it reads as enormous, and
  the foot is clipped by the terrain like a real distant strike.
- Fixed the bolt rendering near black. A text display is multiplied by the world lightmap, and a
  thunderstorm darkens sky light, so the art was being dimmed to almost nothing - that is the pink
  smudge at the horizon. Every sky quad now carries a full bright override, and a 4 block view range
  so the default 64 block culling does not hide it.
- Fixed one strike drawing four bolts. Every line of a macro function runs, so all four variants
  summoned at once at four different distances and the thunder came from whichever one the selector
  happened to reach. Each variant is now guarded by the score that rolled it, and the loaded chunk
  test uses that variant's own distance instead of the rolled one. Verified on the server: one
  strike, one bolt, 74 blocks out in the direction the player was facing.
- The fade no longer freezes. Text opacity is sticky, so a frame that skips a layer leaves it at its
  last value; every frame now sets all three layers and the last one takes them to zero. Verified
  mid strike (bolt 0, corona 42, wash 35) and after it, with no display entities left in the world.
- Verified on a real 1.21.1 dedicated server with no load errors, and the whole strike sequence and
  clean up checked from the log.

WHAT CHANGED IN 1.0.16
- Lightning is now out in the world instead of on the screen. Each strike is a tall red bolt
  placed 40, 52, 64 or 76 blocks away in the direction you are looking (plus a random 35 degree
  spread), with a softer red glow 8 blocks behind it so the two never sit in the same plane.
  It flashes bright, fades over half a second, and the thunder follows about 1.5 seconds later.
  Nothing is drawn over your screen anymore; the world around you stays visible.
- Fixed the empty box that popped up on every strike. The old screen space bolt and flash fonts
  asked for a taller glyph line than their textures could provide, so the game fell back to the
  missing glyph box. Those fonts are gone; the two new sky fonts are validated so an ascent can
  never exceed its own texture height.
- Fixed the bug found while rebuilding this: the strike rotation was written as
  "rotated 0 <yaw>", but that command takes yaw first. Every bolt landed on the same line and
  slid downwards instead of spreading across the sky. It is now "rotated <yaw> 0".
- A strike whose far end is outside the loaded world no longer vanishes. The old code summoned
  and assumed it had landed, because summoning into an unloaded chunk reports success while
  silently discarding the entity. Each strike now checks whether the target chunk is loaded and
  puts the bolt 24 blocks out (glow 16) instead, so short render distances still see lightning.
- The synced lyrics now actually appear. The line lookup used "deusex:lyrics list[i]" without the
  space the storage path requires, so every lookup came back empty, and the lyric list itself was
  written across several lines without line continuations, so only its first line ever loaded.
- Verified on a real 1.21.1 dedicated server: 17 storms fired by the normal game tick, every one
  placing exactly one bolt and one glow at the requested distance, at the same height, with the
  whole fade sequence and the clean up after it correct, and no leftover display entities.

WHAT CHANGED IN 1.0.15
- Synced HUD lyrics in the bottom-left corner, drawn over the game (no chat spam).
  Japanese on top, English directly underneath. They fade in, hold, then fade out,
  and only appear while the drop section is playing.
- Sky lightning in the background: random branching bolts strike down across the sky,
  lighting it up with a white-blue flash, then the image dims and settles back into
  the red tint. Thunder follows about half a second later.
- Strikes are random (bolt shape, screen position) and happen every 7-16 seconds.
  They only run while the song is playing, and stop/reset cleanly on pause,
  finish and stop.

WHAT CHANGED IN 1.0.14
- The boom now hits on the exact tick the heart explodes (the same tick as the music's
  drop and the release back to the game). Before, it landed about 0.75 s late.
- The boom is triggered by the song clock instead of a separate countdown, so it can no
  longer drift or fire late after a pause or server lag.
- More impact: a sharp click, a hard pitch-dropping kick and a crack now lead the hit
  (full level within 0.1 ms) and are kept clean of the limiter. The low braaam and tail
  sit underneath and are about 2 dB louder than in 1.0.13 (+3 dB in the first 150 ms).
- The inhale swell is now its own sound (deusex:boom_rise). It starts 7 ticks earlier
  and cuts to dead silence 30 ms before the hit, so the explosion slams in.
- Boom, rise and heartbeat sounds are preloaded, so the first play has no disk-load delay.

WHAT CHANGED IN 1.0.13
- Final boom redesigned: much louder (about +8 dB perceived, +10 dB on laptop speakers
  and headphones) and far more ominous. A short reverse "inhale" swell pulls into a hard
  impact, followed by a dissonant low brass "braaam" (D with minor second and tritone)
  that slowly darkens into a long reverb tail (~7 s). The original sub-bass is kept
  underneath. The hit still lands at the same moment as before.
- The old playsound volume of 2.6 had no effect (Minecraft caps volume at 1.0); the
  loudness is now built into the sound itself.
- Stop and pause now also cut the boom.

WHAT CHANGED IN 1.0.12
- Heart overlay is now pixel-centered: every pulse and burst frame reports the same
  glyph width (301 units), so the title can no longer re-center itself from frame to
  frame. Previously the hold frames sat about 280 px off-center at 4x scale and the
  burst drifted right by up to about 120 px.
- Heart and burst glyph elevation corrected (ascent 147) so their art centers on the
  screen center vertically as well, matching the blackout and tint layers exactly.
- Music no longer doubles every 3 seconds: the 182 playback chunks were re-cut from
  the master into exact 3.0 s pieces (last 2.924 s) instead of 3.4 s windows with
  0.4 s of duplicated content. Resuming after pause now plays cleanly.

WHAT CHANGED IN 1.0.6
- The shatter effect is gone.
- Final heartbeat: only the seventh/final beat is followed by a separate, loud cinematic boom.
  The music ducks before that last beat and fades back to full volume after the boom.
- Intro: the screen fades to black, then a red heartbeat (lub-dub) pulses on the black
  screen with a matching deep heartbeat sound. The beats speed up toward the beatdrop.
- Pre-drop visual: the supplied anatomical heart is visible on the black intro screen; a red ring expands on every heartbeat. At the beatdrop, the heart bursts into flying fragments with expanding shockwave rings before the red flash continues.
- Beatdrop: a red flash, then players are released and the blood rain starts.
- After the drop a light red tint settles over the screen in about 0.5 seconds (about 14% by default).
  Change it live: /scoreboard players set #tint deusex 7   (0 = off, 4 lighter, 10 stronger, max 19)
- The rain is now thin, short and fine like real rain instead of long heavy streaks.
- On stop/end the tint fades out together with the rain.

COMMANDS
/deusex start <player> <hp>   /deusex phase2   /deusex reset
/function deusex:start   /function deusex:stop   /function deusex:pause   /function deusex:resume   /function deusex:loop

DIAGNOSIS
/function deusex:selftest     prints DEUS-BUILD 1.1.0, then the bridge: #tk (the datapack
                              tick counter), #state (0 idle, 1 playing, 2 paused, 3 closing),
                              #pos (song tick, 0-10918) and #loop. If #tk is not climbing,
                              the datapack loop is not running; if #state and #pos do not
                              move after start, the server half of the mod is not loaded.

TUNING
Song volume: Esc -> Options -> Music & Sound -> the slider beside Voice/Speech, under
Ambient/Environment (default 45%, kept in the client's
config/deusexmachina-client.properties). It multiplies what the mod plays, so the game's own Master
and Jukebox/Note Blocks sliders still sit on top of it.
The drop at tick 219 and the rain lead of 104 ticks are compiled into the mod now, so the old
/scoreboard players set #drop deusex ... tuning no longer does anything.

- Visual repair: pulse rings and beatdrop shockwave are reduced to half-size and precisely centered. The blackout and red flash layers are widened to cover widescreen displays, preventing the moving world from showing through the intro.
