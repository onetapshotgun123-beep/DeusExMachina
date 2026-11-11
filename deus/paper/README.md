# Deus Ex Machina — Paper 1.21.11 plugin

The full Deus Ex Machina show as a **server-side Paper plugin**. Players join with a
**vanilla client — no mod install**. Music, lyrics, the heart cutscene, the red wash,
storms, lances, the RONOVA boss fight and the victory advancement are all delivered
through an auto-sent resource pack plus vanilla effects.

- Plugin: `DeusExMachina-Paper-1.21.11-1.0.0.jar` (~16 MB, includes the resource pack)
- Resource pack (also embedded in the jar): `deusex-pack.zip` (~16 MB)

## Requirements

- **Paper 1.21.11** (tested on build 132). Spigot/Bukkit are not supported — the plugin
  uses Paper-only APIs.
- **Java 21** or newer.
- A TCP port for the built-in pack server (default **25599**) reachable by every player,
  or your own HTTPS host for the pack.

## Install

1. Drop `DeusExMachina-Paper-1.21.11-1.0.0.jar` into the server's `plugins/` folder.
2. Start the server. On first run the plugin:
   - extracts `deusex-pack.zip` next to the jar,
   - starts a small HTTP server that serves the pack to clients,
   - installs the `deusexmachina` datapack (the victory advancement).
3. Edit `plugins/DeusExMachina/config.yml` (see below) and restart, or use `/reload`
   at your own risk — a clean restart is recommended.
4. Join with a vanilla 1.21.11 client and accept the resource pack prompt.

### Config (`plugins/DeusExMachina/config.yml`)

```yaml
music:
  default-volume: 45   # 0-100, per-player override with /deusex volume

pack:
  host: 127.0.0.1      # IMPORTANT: set your public IP or domain for a real server
  port: 25599          # built-in pack HTTP server port (open it in your firewall)
  url: ""              # optional: full external URL (e.g. HTTPS). Overrides host/port.
  prompt: "Deus Ex Machina needs this pack to draw the show."
  required: true       # kick players who decline — the show is unreadable without it
```

**`pack.host: 127.0.0.1` only works when the client runs on the same machine as the
server.** For anything else, set `host` to the address players connect to (public IP or
domain) and make sure `port` is open. If you host `deusex-pack.zip` yourself (recommended:
HTTPS), put the full URL in `pack.url` and the built-in server is bypassed. The pack is
~16 MB; clients download it once and cache it.

## Commands

| Command | Permission | What it does |
|---|---|---|
| `/deusex start <player> <hp 1-100>` | `deusex.use` (op) | Starts the show. That player becomes RONOVA with a boss bar scaled to `hp`. |
| `/deusex pause` / `resume` | `deusex.use` | Freezes / continues the show clock, music and attacks. |
| `/deusex stop` | `deusex.use` | Ends the show and runs the closing sequence. |
| `/deusex loop` | `deusex.use` | Toggles looping the 9:06 track instead of closing. |
| `/deusex status` | `deusex.use` | Show state, clock, boss HP, phase, loop mode. |
| `/deusex phase2` | `deusex.admin` (op) | Forces phase 2 (debug/admin). |
| `/deusex reset` | `deusex.admin` (op) | Full reset: weather, buffs, bar, clock, advancement state. |
| `/deusex volume [0-100]` | `deusex.volume` (everyone) | Shows or sets your own music volume. Applies from the next music chunk. Players only. |

## How the show runs

- **Start**: everyone is frozen (movement/gravity/jump zeroed) while the heart cutscene
  plays; rain leads in, then the beat drop (~11 s) unfreezes everyone and the 9:06 track
  begins. Lyrics run on the action bar; the music HUD shows the current time.
- **Boss bar mechanic**: the bar does **not** change the player's real health pool (20 HP).
  It maps real health percentage onto the configured HP — e.g. with `start Steve 100`,
  half health shows 50/100. Damage, regeneration and absorption all read correctly.
- **Attacks**: tracked storm strikes, aimed laser volleys with sigil warnings, Grasp,
  Soul Siphon and Ember Barrage — all built from vanilla particles, sounds and effects.
  Siphon strikes heal RONOVA (the boss can climb back up — that is by design).
- **Phase 2** latches when RONOVA drops to **≤ 50% health**: bar turns red, storms double
  in frequency, and the boss gets Speed II + Strength + Regeneration. Other players keep
  a passive bless buff for the whole event.
- **Victory**: when RONOVA dies, the show lingers 2 s, grants every online player the
  `deusexmachina:server_free` advancement ("The seal is broken. Server is finally free...
  at last."), removes the bar and closes. Instant-respawn setups are handled — the death
  is caught from the death event, not polling.
- Non-boss players glow (vanilla Glowing effect) so they stay readable in the red wash.

## Differences from the NeoForge mod (vanilla-client tradeoffs)

Everything a vanilla client can draw is kept; anything that needed client-side rendering
mixins is approximated:

- No custom red lightning bolt art — strikes use vanilla particles/sounds (sparks, soul
  flames, explosion emitters) plus the pack's red screen overlays.
- No red rain streaks or sky veil shader — the red wash is drawn with pack-font screen
  overlays; rain itself is vanilla weather (forced during the show, restored after).
- No sigil atlas / drum-corner HUD art — warnings and the heart/burst cutscene use
  pack-font titles and the action bar.
- Music is streamed as pack sound chunks: pausing is exact, but **resume restarts from
  the current chunk boundary** (a second or two of position can be lost), and rejoining
  mid-show re-syncs at the next chunk.
- No options-menu slider — use `/deusex volume`.

## Verified test results

Tested headlessly on a real Paper 1.21.11 server (build 132) with two protocol-level bot
clients: pack push + SHA-1 match + accept, freeze/unfreeze attribute values, rain ramp and
restore, cutscene titles, music HUD, waves and laser callouts on schedule, pause silence
(zero audio/particle packets while paused), phase 2 latch + red bar, boss death →
advancement grant to both clients → bar removal → clean idle. Zero exceptions in the
server log.

**Client visuals were not verified in an actual game client** — testing was headless
(protocol bots). If anything looks off in game, report it with a screenshot.

## Hashes (SHA-256)

```
DeusExMachina-Paper-1.21.11-1.0.0.jar  fbb3b77e3f2829ac7f0aaf6be4ca52a52927a7eb5224f6852745b1cdd6912f0b
deusex-pack.zip                        3a8f47a34e86b421ab5ceb1c750e8d379f86b10867aadffdac5b1474a4e1bf00
```