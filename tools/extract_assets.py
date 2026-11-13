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
  levels/   the planes' maps and brushes tools/data_walk.py walks (tools/spinball_levels.py): NAME_map.csv (its rows
            of brushes, h and v when mirrored) and NAME_brushes.txt (a brush a line, its 16 cells); levels.txt says
            where each goes; NAME_plane.png is a picture of each table's plane in greys by pen, to look at (it is
            not read back).
With --check, every table, tileset, map and brushes is built from its files and compared with the cartridge's
bytes, byte for byte (nothing is written).
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
import spinball_levels as levels  # noqa: E402

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


def write_levels(analysis, names, folder):
    folder.mkdir(parents=True, exist_ok=True)
    image, walk = analysis.image, data_walk.walk_of(analysis)
    lines = ["# The planes' maps and brushes: what each file is and where it goes in the cartridge (for --check)"]
    for where, (width, rows, _) in sorted(walk.maps.items()):
        name = names.get(where, f"map_{where:06X}").removesuffix("_map")
        (folder / f"{name}_map.csv").write_text(levels.map_text(levels.read_map(image, where, width, rows)),
                                                 encoding="ascii")
        lines.append(f"map {name} at {where:06X} width {width} rows {rows}")
    for where, (count, _) in sorted(walk.brushes.items()):
        name = names.get(where, f"brushes_{where:06X}").removesuffix("_brushes")
        (folder / f"{name}_brushes.txt").write_text(levels.brushes_text(levels.read_brushes(image, where, count)),
                                                    encoding="ascii")
        lines.append(f"brushes {name} at {where:06X} count {count}")
    for where, (rows, _, _) in sorted(walk.collisions.items()):
        name = names.get(where, f"collision_{where:06X}").removesuffix("_collision")
        lists, _ = levels.read_collision(image, where, rows)
        (folder / f"{name}_collision.txt").write_text(levels.collision_text(lists), encoding="ascii")
        lines.append(f"collision {name} at {where:06X} rows {rows}")
        table = next(table for table, (kind, _) in walk.pointer_tables.items() if kind == "collision")
        level = next(level for level in range(data_walk.LEVELS) if data_walk.long_at(image, table + 4 * level) == where)
        width, height = (struct.unpack_from(">H", image, data_walk.LEVEL_SIZES + 4 * level + offset)[0]
                         for offset in (0, 2))
        asset_formats.write_png_indexed(folder / f"{name}_collision.png", levels.collision_pens(lists, width, height),
                                        GREYS, 4)
    (folder / "levels.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
    write_flippers(image, names, walk, folder)
    # the pictures: a table's planes drawn with its tiles (the first plane the code draws with the first tiles
    # the table loads, the second with the second: 0D3FF4, 0D401A; 0D4FC0, 0D5014)
    tables = [table for table, (kind, _) in walk.pointer_tables.items() if kind == "map"]
    pictures = 0
    for plane, (map_table, tiles_table) in enumerate(zip(tables, walk.tileset_tables)):
        for level in range(data_walk.LEVELS):
            where = data_walk.long_at(image, map_table + 4 * level)
            brushes_at = dict(walk.plane_places)[where]
            width, rows, _ = walk.maps[where]
            tiles = compression.ssc_decode(image, data_walk.long_at(image, tiles_table + 4 * level)).data
            picture = levels.plane_pens(levels.read_map(image, where, width, rows),
                                        levels.read_brushes(image, brushes_at, walk.brushes[brushes_at][0]), tiles)
            name = names.get(where, f"map_{where:06X}").removesuffix("_map")
            asset_formats.write_png_indexed(folder / f"{name}_plane.png", picture, GREYS, 4)
            pictures += 1
    print(f"levels: {len(walk.maps)} maps, {len(walk.brushes)} brushes, {pictures} pictures -> {folder}")


def write_flippers(image, names, walk, folder):
    """flippers.txt: each table's flippers ("X Y FLAGS"), the shapes ("X0 Y0 X1 Y1 FLAGS NUMBER", as the
    collision's) and the boxes ("X0 Y0 X1 Y1 WORD"), each section with where it goes"""
    lines = ["# The flippers: each section says where its bytes go (for --check); tools/spinball_levels.py"]
    for where, (count, level) in sorted(walk.flippers.items()):
        name = names.get(where, f"flippers_{where:06X}").removesuffix("_flippers")
        lines.append(f"flippers {name} at {where:06X}")
        lines += [f"  {x} {y} {flags:04X}" for x, y, flags in levels.read_flippers(image, where, count)]
    for where, (_, found) in sorted(walk.flipper_shapes.items()):
        lines.append(f"shape at {where:06X}  # {found}")
        lines += levels.records_text(levels.read_list(image, where)[0])
    first, count = walk.flipper_boxes
    start = data_walk.FLIPPER_BOXES + levels.FLIPPER_BOX_BYTES * first
    lines.append(f"boxes at {start:06X}  # the positions {first}-{first + count - 1}")
    lines += ["  " + " ".join(str(value) for value in levels.read_box(image, start + levels.FLIPPER_BOX_BYTES * index))
              for index in range(count)]
    (folder / "flippers.txt").write_text("\n".join(lines) + "\n", encoding="ascii")


def check_flippers(image, folder):
    problems, sections = 0, []
    for line in (folder / "flippers.txt").read_text(encoding="ascii").splitlines():
        words = line.split("#", 1)[0].split()
        if not words:
            continue
        if words[0] in ("flippers", "shape", "boxes"):
            sections.append((words[0], int(words[words.index("at") + 1], 16), []))
        else:
            sections[-1][2].append(words)
    for kind, address, rows in sections:
        if kind == "flippers":
            built = levels.flippers_bytes([(int(x), int(y), int(flags, 16)) for x, y, flags in rows])
        elif kind == "shape":
            built = levels.list_bytes([levels.parse_record(words) for words in rows])
        else:
            built = b"".join(levels.box_bytes(tuple(int(value) for value in words)) for words in rows)
        if built != image[address:address + len(built)]:
            print(f"{kind} at {address:06X}: differs from the cartridge's {len(built)} bytes")
            problems += 1
    print(f"flippers: {len(sections)} sections, " + ("identical" if not problems else f"{problems} differ"))
    return problems


def check_levels(image, folder):
    problems = 0
    for line in (folder / "levels.txt").read_text(encoding="ascii").splitlines():
        words = line.split("#", 1)[0].split()
        if not words:
            continue
        kind, name, address = words[0], words[1], int(words[3], 16)
        if kind == "map":
            built = levels.map_bytes(levels.parse_map_text((folder / f"{name}_map.csv").read_text(encoding="ascii")))
        elif kind == "collision":
            built = levels.collision_bytes(levels.parse_collision_text(
                (folder / f"{name}_collision.txt").read_text(encoding="ascii")))
        else:
            built = levels.brushes_bytes(levels.parse_brushes_text(
                (folder / f"{name}_brushes.txt").read_text(encoding="ascii")))
        if built != image[address:address + len(built)]:
            print(f"{kind} {name}: differs from the cartridge's {len(built)} bytes at {address:06X}")
            problems += 1
        else:
            print(f"{kind} {name}: {len(built)} bytes at {address:06X}, identical")
    return problems


def main():
    image, analysis, names = load()
    out_at = sys.argv.index("--out") if "--out" in sys.argv else None
    out = Path(sys.argv[out_at + 1]) if out_at is not None else game_profile.ROOT / "assets"
    if "--check" in sys.argv:
        problems = check_sprites(image, out / "sprites") + check_tilesets(image, out / "tilesets") \
            + check_levels(image, out / "levels") + check_flippers(image, out / "levels")
        print("all identical" if not problems else f"{problems} differ")
        return 1 if problems else 0
    write_sprites(analysis, names, out / "sprites")
    write_tilesets(analysis, names, out / "tilesets")
    write_levels(analysis, names, out / "levels")
    return 0


if __name__ == "__main__":
    sys.exit(main())
