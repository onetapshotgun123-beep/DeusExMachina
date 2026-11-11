"""Build the Paper port's resource pack from the legacy 1.0.34 assets.
The veil cells are repainted at 0.4x alpha to match the mod's readability pass.
Rain is deliberately NOT retextured: a vanilla client cannot condition a texture
on the event, and an always-red rain.png was the bug the mod's mixins removed.
Run from deus/: python make_pack.py"""
import io
import json
import os
import zipfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
LEGACY = os.path.join(HERE, "legacy_1034", "assets", "deusex")
OUT_DIR = os.path.join(HERE, "paper", "pack")
OUT = os.path.join(OUT_DIR, "deusex-pack.zip")
FIXED_DATE = (2026, 11, 11, 0, 0, 0)


def soft_red_lv():
    src = Image.open(os.path.join(LEGACY, "textures", "font", "red_lv.png")).convert("RGBA")
    r, g, b, a = src.split()
    a = a.point(lambda v: int(v * 0.4))
    out = Image.merge("RGBA", (r, g, b, a))
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue(), src.size


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    sounds = json.load(open(os.path.join(LEGACY, "sounds.json"), encoding="utf-8"))
    sounds.pop("main_track", None)  # the plugin plays the chunked path, never the gapless file
    chunk_count = sum(1 for k in sounds if k.startswith("chunk_"))
    assert chunk_count == 182, chunk_count

    red_lv, size = soft_red_lv()
    print("red_lv.png %sx%s softened to 0.4x alpha" % size)

    entries = {}
    entries["pack.mcmeta"] = json.dumps({
        "pack": {
            "description": "Deus Ex Machina - the show's music, fonts and art",
            "min_format": 75,
            "max_format": 75,
        }
    }, indent=2).encode("utf-8")
    pack_png = os.path.join(HERE, "extracted", "pack.png")
    if os.path.exists(pack_png):
        entries["pack.png"] = open(pack_png, "rb").read()

    font_dir = os.path.join(LEGACY, "font")
    for name in sorted(os.listdir(font_dir)):
        entries["assets/deusex/font/" + name] = open(os.path.join(font_dir, name), "rb").read()
    tex_dir = os.path.join(LEGACY, "textures", "font")
    for name in sorted(os.listdir(tex_dir)):
        data = red_lv if name == "red_lv.png" else open(os.path.join(tex_dir, name), "rb").read()
        entries["assets/deusex/textures/font/" + name] = data
    snd_dir = os.path.join(LEGACY, "sounds")
    for name in sorted(os.listdir(snd_dir)):
        if name == "main_track.ogg":
            continue
        entries["assets/deusex/sounds/" + name] = open(os.path.join(snd_dir, name), "rb").read()
    entries["assets/deusex/sounds.json"] = json.dumps(sounds, indent=2).encode("utf-8")

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, entries[name])
    print("wrote %s (%d entries, %.2f MB)" % (OUT, len(entries), os.path.getsize(OUT) / 1e6))


if __name__ == "__main__":
    main()