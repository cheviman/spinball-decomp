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
With --check, every table is built from its sheet and sprites.txt and compared with the cartridge's bytes,
byte for byte (nothing is written).
"""
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]
import game_profile  # noqa: E402
import importlib  # noqa: E402
import asset_formats  # noqa: E402  (the core's PNG reader and writer)
import data_walk  # noqa: E402
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


def main():
    image, analysis, names = load()
    out_at = sys.argv.index("--out") if "--out" in sys.argv else None
    out = Path(sys.argv[out_at + 1]) if out_at is not None else game_profile.ROOT / "assets"
    if "--check" in sys.argv:
        problems = check_sprites(image, out / "sprites")
        print("all identical" if not problems else f"{problems} differ")
        return 1 if problems else 0
    write_sprites(analysis, names, out / "sprites")
    return 0


if __name__ == "__main__":
    sys.exit(main())
