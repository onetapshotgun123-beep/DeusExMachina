# Agent guide (read before changing code)

This repo holds the Deus Ex Machina show: a NeoForge 1.21.1 client mod and a Paper
1.21.11 plugin port. Read `README.md` for layout and build commands. This file lists
the rules that are NOT obvious from the code.

## Hard release rules

1. **Never ship dev hooks.** `DevProbe.java`, `-PdeusexProbe`, `deusex.probe`,
   `probe_show.py` and `paper-test/bot.py` are development-only. They may live in this
   repo, but none of their classes/artifacts may end up in a released jar.
   `build_jar.py` already strips DevProbe; `validate_assets.py` re-checks the jar.
2. **Validator gate:** `python deus/validate_assets.py` must report 0 errors / 0 warnings
   against the freshly built jar before any release. It reads the jar back, so a stale
   tree cannot pass. If you change assets/timeline, re-derive the affected validator
   rules deliberately — do not weaken a rule just to make a build pass.
3. **Reproducible builds:** two consecutive builds of the same tree must hash identically
   (`build_jar.py` fixes timestamps/order; `make_pack.py` fixes zip dates). Verify with
   SHA-256 before delivering.
4. Mod version stays **1.1.0** and the mod jar stays **under 30 MB** unless the user
   explicitly asks for a version bump. Paper plugin is `1.0.0` for 1.21.11.
5. Deliver install-ready jars to `~/Downloads` when the user asks for a release.

## Build / test workflow

- Mod: `deus/client` → `gradlew.bat build` (JDK 21), then `python deus/build_jar.py`,
  then `python deus/validate_assets.py`.
- The client project intentionally has **no parchment** — it compiles against Mojang
  official mappings because the classes are merged into a jar loaded by production
  NeoForge. Adding parchment breaks member names at runtime.
- Paper: `python deus/make_pack.py` (needs pillow) → `deus/paper` → `gradlew.bat jar`.
  The pack zip is generated; it is gitignored. The jar embeds it via `processResources`.
- Generators (`make_*.py`) read `deus/legacy_1034/` (asset + mcfunction baseline) and
  write into `client`/`paper` source. If you change the timeline or fonts, regenerate
  the derived Java (`make_client_data.py`, `make_paper_data.py`) instead of hand-editing
  `ShowHudData.java` / `ShowData.java`.
- Python generators need `pillow` and `numpy`.

## Dev servers and probes

- Never run Gradle while a probe/test server is running.
- Stop test servers via RCON `stop` (see `deus/rcon.py`), not by killing processes.
- Paper headless testing: start a Paper 1.21.11 server (offline mode, flat world,
  **difficulty=peaceful** — hostile mobs contaminate boss tests), then run
  `python deus/paper-test/bot.py <Name>` per client. Packet IDs for 1.21.11
  (protocol 774) are in `deus/paper-test/proto/packet_ids.json`.
- Hard-won 1.21.11 wire facts (the bot already implements them):
  - Network NBT roots are **unnamed**; NBT strings use **2-byte big-endian lengths**.
  - Boss bar packets key on a **UUID**, not a varint id.
  - Attribute snapshot modifiers are **Identifier string + double + varint operation**.
  - Game-event ids are 0-based (START_RAINING=1, RAIN_LEVEL_CHANGE=7).
  - `ClientboundSetEntityMotionPacket` uses packed LpVec3 bits, not 3 shorts.
  - Offline-mode login UUID = MD5("OfflinePlayer:" + name) as UUID v3.

## Show mechanics (both ports must agree)

- Show clock: rain lead-in 115 t, drop/unfreeze 219 t, first storm 339 t, first lance
  379 t, total 10919 t (9:06), closing 80 t, boss-death linger 40 t.
- Boss bar maps **real health %** onto the configured HP (1-100); it never changes the
  player's actual max health. Phase 2 latches at ≤50% live HP (red bar, double storm
  frequency, boss buffs) and persists until death/reset. Siphon strikes heal the boss —
  climbing back up is intended.
- Boss death must be caught from the death event (instant-respawn safe), then grant the
  `deusexmachina:server_free` advancement to every online player and close the show.
- Paper port tradeoffs vs the mod: no custom bolt/rain/sigil rendering (vanilla particles
  + pack-font overlays), music resumes at chunk boundaries, volume via `/deusex volume`.
- The Paper port was verified headlessly only; **client visuals were never verified in
  game**. Say so in any release report.

## Workspace hygiene

- This repo is a whitelist: only `deus/` project files plus the root docs are tracked.
  Do not add scratch scripts, logs, videos, decompiled Minecraft source, test servers or
  world saves. `sessions.py` must never be tracked or modified.
- The user reports bugs via screenshots and expects terse, autonomous progress; install
  artifacts go to `~/Downloads`.