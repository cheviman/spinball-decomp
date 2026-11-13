"""
Name:        extract_assets.py
Description: Sonic the Hedgehog Spinball's assets from the player's cartridge into common formats, by subject, and
             back byte for byte
Version:     0.1.0
Created:     13-11-2026
Modified:    13-11-2026
Author:      Sebastian Toyos

Usage: python tools/extract_assets.py [cartridge] [--check] [--out FOLDER]   (assets/ by default)

Writes the assets (none of them goes into the repository):
  sprites/  the sprite tables tools/data_walk.py walks, a sheet each (NAME.png, by symbols.txt's name for the
            table): 4-bit indexed PNGs whose palette indices are the pens (0 is transparent), each sprite drawn
            whole in its cell; sprites.txt says, per table, where each sprite's cell and origin are and its
            pieces' places and sizes (tools/spinball_graphics.py). The colours are grey levels by pen for now:
            the palette each object shows with comes from a census of what the game shows (to do).
  tilesets/ the tiles tools/data_walk.py walks (SSC, C2 and as they are), a sheet each (NAME.png, by symbols.txt's
            name): 4-bit indexed PNGs, 16 tiles a row, greys by pen like the sprites; tilesets.txt says per sheet
            how its tiles are kept and what else gives the cartridge's bytes back (tools/spinball_compression.py).
With --check, every table and tileset is built from its sheet and its text and compared with the cartridge's bytes,
byte for byte (nothing is written).
"""
import struct
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]
import game_profile  # noqa: E402
import importlib  # noqa: E402
import asset_formats  # noqa: E402  (the core's PNG reader and writer)
import data_walk  # noqa: E402
import spinball_compression as compression  # noqa: E402
import spinball_graphics as graphics  # noqa: E402

GREYS = [(level, level, level) for level in range(0, 256, 17)]


def load():
    """The cartridge's image, its analysis (run), and the names symbols.txt gives places"""
    arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
    out_at = sys.argv.index("--out") if "--out" in sys.argv else None
    if out_at is not None:
        arguments = [argument for argument in arguments if argument != sys.argv[out_at + 1]]
    source = Path(arguments[0]) if arguments else game_profile.ROOT / "rom"
    image = game_profile.rom.build_program(game_profile.rom.load_set(source))
    module = importlib.import_module(game_profile.ANALYSIS)
    analysis = module.Analysis(image, module.load_symbols(game_profile.ROOT / "symbols.txt"))
    analysis.run()
    names = {address: symbol.name for address, symbol in analysis.symbols.items()}
    return image, analysis, names


def table_name(names, address):
    return names.get(address, f"sprites_{address:06X}").removesuffix("_sprites")


def write_sprites(analysis, names, folder):
    folder.mkdir(parents=True, exist_ok=True)
    sections = ["# The sprite tables' sheets: per table its flags and the cartridge's address (for --check), then per",
                "# sprite: its cell's corner in the sheet, where its origin falls in the sheet, and its pieces as",
                "# X,Y,WIDTHxHEIGHT from the origin (tools/spinball_graphics.py)"]
    count = 0
    for address, (flags, sprites, _, _) in sorted(data_walk.sprite_tables(analysis).items()):
        overlaps = [index for index, sprite in enumerate(sprites) if graphics.overlapping(sprite)]
        if overlaps:
            raise SystemExit(f"{address:06X}: sprites {overlaps} have pieces that overlap: a drawn cell would lose pens")
        name = table_name(names, address)
        places, size = graphics.lay_out(sprites)
        asset_formats.write_png_indexed(folder / f"{name}.png", graphics.draw_sheet(sprites, places, size), GREYS, 4,
                                        transparent=0)
        sections.append("")
        sections.append(graphics.sprites_text(name, address, flags, sprites, places).rstrip())
        count += len(sprites)
    (folder / "sprites.txt").write_text("\n".join(sections) + "\n", encoding="ascii")
    print(f"sprites: {count} sprites in {len(data_walk.sprite_tables(analysis))} sheets -> {folder}")


def check_sprites(image, folder):
    tables = graphics.parse_sprites_text((folder / "sprites.txt").read_text(encoding="ascii"))
    problems = 0
    for name, (flags, address, layout) in tables.items():
        rows, _ = asset_formats.read_png_indexed(folder / f"{name}.png")
        built = graphics.build_table(flags, graphics.sprites_from_sheet(rows, layout))
        original = image[address:address + len(built)]
        if built != original:
            first = next(index for index, (a, b) in enumerate(zip(built, original)) if a != b) \
                if any(a != b for a, b in zip(built, original)) else min(len(built), len(original))
            print(f"sprites {name}: differs from the cartridge at {address + first:06X}")
            problems += 1
        else:
            print(f"sprites {name}: {len(built)} bytes at {address:06X}, identical")
    return problems


def tileset_line(name, address, kind, size, image):
    """(tilesets.txt's line, the tiles' bytes) of a tileset the walk found"""
    word = struct.unpack_from(">H", image, address)[0]
    if kind == "raw tiles":
        short, data, own = "raw", image[address + 2:address + size], size
        extra = f" word {word:04X}"
    elif kind == "SSC tiles":
        result = compression.ssc_decode(image, address)
        short, data, own = "ssc", result.data, result.size
        extra = f" word {word:04X} end {image[address + own - 1] & 0x0F:X}"
    else:
        start = address + 2 if kind == "C2 tiles after a word" else address
        result = compression.c2_decode(image, start)
        short, data, own = "c2", result.data, start - address + result.size
        extra = f" word {word:04X}" if start != address else ""
    pad = " pad" if size > own else ""
    return f"tiles {name} {short} at {address:06X} bytes {len(data)}{extra}{pad}", data


def write_tilesets(analysis, names, folder):
    folder.mkdir(parents=True, exist_ok=True)
    lines = ["# The tiles' sheets: per sheet its name, how the cartridge keeps its tiles (ssc, c2 or raw: as they",
             "# are), where (for --check), the bytes its tiles take (the last tile may be cut short), the word before",
             "# them (ssc: the tiles; raw: the tiles; c2: what makes 0F3BB8 decode), the length bits of the SSC end,",
             "# and whether an FF evens the place after them (tools/spinball_compression.py)"]
    walk = data_walk.walk_of(analysis)
    for address, (kind, size, _) in sorted(walk.tilesets.items()):
        name = names.get(address, f"tiles_{address:06X}").removesuffix("_tiles")
        line, data = tileset_line(name, address, kind, size, analysis.image)
        asset_formats.write_png_indexed(folder / f"{name}.png", graphics.tiles_sheet(bytes(data)), GREYS, 4)
        lines.append(line)
    (folder / "tilesets.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
    print(f"tilesets: {len(walk.tilesets)} sheets -> {folder}")


def check_tilesets(image, folder):
    problems = 0
    for line in (folder / "tilesets.txt").read_text(encoding="ascii").splitlines():
        words = line.split("#", 1)[0].split()
        if not words:
            continue
        name, kind, address, size = words[1], words[2], int(words[4], 16), int(words[6])
        fields = dict(zip(words[7::2], words[8::2]))
        rows, _ = asset_formats.read_png_indexed(folder / f"{name}.png")
        data = graphics.tiles_from_sheet(rows, size)
        head = struct.pack(">H", int(fields["word"], 16)) if "word" in fields else b""
        if kind == "ssc":
            built = compression.ssc_encode(data, int(fields["word"], 16), int(fields["end"], 16))
        elif kind == "c2":
            built = head + compression.c2_encode(data)
        else:
            built = head + data
        if words[-1] == "pad":
            built += bytes([data_walk.TILESET_PAD])
        if built != image[address:address + len(built)]:
            print(f"tiles {name}: differs from the cartridge's {len(built)} bytes at {address:06X}")
            problems += 1
        else:
            print(f"tiles {name}: {len(built)} bytes at {address:06X}, identical")
    return problems


def main():
    image, analysis, names = load()
    out_at = sys.argv.index("--out") if "--out" in sys.argv else None
    out = Path(sys.argv[out_at + 1]) if out_at is not None else game_profile.ROOT / "assets"
    if "--check" in sys.argv:
        problems = check_sprites(image, out / "sprites") + check_tilesets(image, out / "tilesets")
        print("all identical" if not problems else f"{problems} differ")
        return 1 if problems else 0
    write_sprites(analysis, names, out / "sprites")
    write_tilesets(analysis, names, out / "tilesets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
