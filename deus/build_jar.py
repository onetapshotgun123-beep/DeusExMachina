"""Pack the deliverable JAR, byte for byte reproducibly.

Since 1.1.0 the show lives in the client mod, so the jar is a merge of three trees:
  * extracted/                 - the thin deusex: command-shim datapack (functions + tags), the
                                 README, pack.png and the merged META-INF/neoforge.mods.toml.
  * client/build/classes/...   - the compiled mod, mixin and network classes. DevProbe is a
                                 development-only probe and is never shipped.
  * client/build/resources/... - the mod's own assets (sounds, show textures, sounds.json) and
                                 its mixin config. The manifest here is skipped: extracted's
                                 merged one is the single source of truth for the jar.

NeoForge reads neoforge.mods.toml out of META-INF and takes assets and data straight from the jar,
so the jar IS the mod. Entries are written in a fixed order with a fixed timestamp and mode because
a release is checked by hash: anything that varies between runs (mtimes, walk order) makes a rebuild
of the same tree look like a different build.
"""

import os
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SHIM = os.path.join(ROOT, "extracted")
CLASSES = os.path.join(ROOT, "client", "build", "classes", "java", "main")
RESOURCES = os.path.join(ROOT, "client", "build", "resources", "main")
OUT = os.path.expanduser("~/Downloads/DeusExMachina-NeoForge-1.21.1-1.1.0.jar")

STAMP = (1980, 1, 1, 0, 0, 0)
DIR_MODE = 0o40755 << 16
FILE_MODE = 0o100644 << 16

files = {}


def add_tree(base, skip=None):
    for dirpath, _sub, names in os.walk(base):
        for n in names:
            path = os.path.join(dirpath, n)
            rel = os.path.relpath(path, base).replace("\\", "/")
            if skip and skip(rel):
                continue
            files[rel] = path


# The shim datapack and the merged manifest. pack.mcmeta is not a thing NeoForge reads.
add_tree(SHIM, skip=lambda rel: rel == "pack.mcmeta")
# Compiled mod classes, minus the development-only probe (and any inner classes it owns).
add_tree(CLASSES, skip=lambda rel: rel.rsplit("/", 1)[-1].split("$", 1)[0] == "DevProbe.class"
         or rel.rsplit("/", 1)[-1].startswith("DevProbe"))
# Mod assets + mixin config. The manifest is taken from the shim tree above, not duplicated here.
add_tree(RESOURCES, skip=lambda rel: rel == "META-INF/neoforge.mods.toml")

# A directory entry for every parent, or the loader's zip listing has paths with no node.
dirs = set()
for rel in files:
    parts = rel.split("/")[:-1]
    for i in range(1, len(parts) + 1):
        dirs.add("/".join(parts[:i]) + "/")

with zipfile.ZipFile(OUT, "w") as z:
    for rel in sorted(dirs):
        info = zipfile.ZipInfo(rel, STAMP)
        info.external_attr = DIR_MODE
        z.writestr(info, b"")
    for rel in sorted(files):
        info = zipfile.ZipInfo(rel, STAMP)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = FILE_MODE
        z.writestr(info, open(files[rel], "rb").read())

print(OUT, os.path.getsize(OUT), "bytes,", len(dirs), "dirs,", len(files), "files")