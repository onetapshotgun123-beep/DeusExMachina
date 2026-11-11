# Deus Ex Machina

A synchronized Minecraft music-show event: a 9:06 track drives lyrics, a heart cutscene,
a red wash, storms, aimed laser volleys and a RONOVA boss fight. Two deliverables share
one timeline:

| Deliverable | Target | Where |
|---|---|---|
| **NeoForge mod** (v1.1.0) | Minecraft 1.21.1, NeoForge 21.1.265, client-side show | `deus/client` + `deus/extracted` |
| **Paper plugin** (v1.0.0) | Paper 1.21.11, vanilla clients, auto-sent resource pack | `deus/paper` |

## Repository layout

```
deus/
  client/            NeoForge ModDev project (Java 21, mojmap, no parchment on purpose)
    src/main/java    show engine, render, mixins, network payloads, server orchestrator
    src/main/resources  mod assets: main_track.ogg, show texture atlases, mixin config
  extracted/         thin deusex: command-shim datapack + merged META-INF/neoforge.mods.toml
  legacy_1034/       asset + mcfunction baseline the generators read (fonts, sounds, timeline)
  paper/             Paper 1.21.11 plugin (pure Paper API, no NMS)
  art/               sigil source art
  build_jar.py       packs the reproducible mod jar (shim + compiled classes + assets)
  make_pack.py       regenerates the Paper resource pack zip from legacy_1034
  make_paper_data.py regenerates paper ShowData.java (font bases + timeline) from the baseline
  make_client_data.py regenerates client ShowHudData.java from the baseline
  make_*.py          asset generators (lyrics, sigils, beat envelope, burst, sky, bolt, boom)
  validate_assets.py release validator - reads the built jar back, must pass 0 errors / 0 warnings
  skyview.py         offline sky/proof-sheet renderer (dev)
  probe_show.py      dev-only in-world probe harness (never shipped in any jar)
  rcon.py            tiny RCON client used by the dev harnesses
  paper-test/        dev-only headless test bot (bot.py) + 1.21.11 packet id map
```

## Building the mod (NeoForge 1.21.1)

Requires JDK 21. From `deus/client`:

```
gradlew.bat build          # compiles classes + resources into client/build
```

Then from `deus/`:

```
python build_jar.py        # merges shim + classes + assets -> ~/Downloads/DeusExMachina-NeoForge-1.21.1-1.1.0.jar
python validate_assets.py  # validates that exact jar; must be 0 errors / 0 warnings
```

`build_jar.py` writes fixed timestamps/order so identical trees produce byte-identical
jars (releases are checked by hash). DevProbe classes are excluded from the jar by the
packer; the validator re-checks that nothing probe-related shipped.

Dev runs: `gradlew.bat runClient -PdeusexProbe=show` drives the in-world probe
(development only). Python generators need `pillow` and `numpy`.

## Building the Paper plugin (1.21.11)

Requires JDK 21. From `deus/`:

```
python make_pack.py        # regenerates paper/pack/deusex-pack.zip from legacy_1034
```

Then from `deus/paper`:

```
gradlew.bat jar            # -> build/libs/DeusExMachina-Paper-1.21.11-1.0.0.jar (embeds the pack)
```

Install/config/commands: see [deus/paper/README.md](deus/paper/README.md).

## Release rules

- Mod version stays **1.1.0** until a release is explicitly requested; jar under 30 MB.
- `validate_assets.py` must report **0 errors / 0 warnings** against the built jar.
- Builds must be reproducible: two consecutive builds of the same tree hash identically.
- **DevProbe / probe hooks / test bots never ship** in any jar.
- The Paper port was verified headlessly (protocol bots on real Paper 1.21.11); client
  visuals were not verified in game.

## Notes for AI coding agents

See [AGENTS.md](AGENTS.md) before changing anything.