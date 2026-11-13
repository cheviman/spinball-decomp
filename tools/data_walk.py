"""
Name:        data_walk.py
Description: Sonic the Hedgehog Spinball's data the code hands to its engines, walked from where it hands it over:
             for now, the sprite tables the sprite loader reads
Version:     0.1.0
Created:     13-11-2026
Modified:    13-11-2026
Author:      Sebastian Toyos

Usage: python tools/data_walk.py [cartridge]       (the coverage takes spans() through the profile's DATA_WALK)

  sprite table   what field 0A holds of the structure an object's field 3A points at, which the sprite loader
                 (0D7D02) reads (tools/spinball_graphics.py): a table the code stores there ("movea.l ($3a,An),
                 Am" then "move.l #TABLE, ($a,Am)": 0E5F42-0E5F46, 0EB450-0EB454, 0EE3BE-0EE3C2...), or one
                 symbols.txt names *_sprites (held by data the walk does not read yet: the records at 0C0AC4).
                 A start that does not read as a sprite table whole stops the walk with what is wrong.
"""
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]
import game_profile  # noqa: E402
import importlib  # noqa: E402
import spinball_graphics as graphics  # noqa: E402

SPRITE_LINK_FIELD = 0x3A        # an object's link to the structure that holds its sprite table
SPRITE_TABLE_FIELD = 0x0A       # that structure's sprite table


def sprite_table_starts(analysis):
    """{address: how it was found} of the sprite tables: the code's stores into field 0A of what an object's field
    3A points at, symbols.txt's *_sprites"""
    starts = {}
    previous = None
    for address, instruction in sorted(analysis.instructions.items()):
        operands = instruction.operands
        if instruction.mnemonic == "move" and instruction.size == "l" and len(operands) == 2 \
                and operands[0].mode == "immediate" and operands[1].mode == "disp" \
                and operands[1].disp == SPRITE_TABLE_FIELD and previous is not None \
                and previous.address + previous.length == address and previous.mnemonic == "movea" \
                and previous.operands[0].mode == "disp" and previous.operands[0].disp == SPRITE_LINK_FIELD \
                and previous.operands[1].reg == operands[1].reg:
            starts.setdefault(operands[0].value & 0xFFFFFF, f"stored by {address:06X}")
        previous = instruction
    for address, symbol in analysis.symbols.items():
        if symbol.kind == "data" and symbol.name.endswith("_sprites"):
            starts.setdefault(address, f"symbols.txt {symbol.name}")
    return starts


def sprite_tables(analysis):
    """{address: (flags, sprites, size, how it was found)}"""
    tables = {}
    for address, found in sprite_table_starts(analysis).items():
        try:
            flags, sprites, size = graphics.read_table(analysis.image, address)
        except (ValueError, IndexError) as problem:
            raise SystemExit(f"{address:06X} ({found}) does not read as a sprite table: {problem}")
        tables[address] = (flags, sprites, size, found)
    return tables


def spans(analysis):
    """For the coverage (the profile's DATA_WALK): {first: (stop, kind)} of what the walk reads"""
    return {address: (address + size, "sprite table") for address, (_, _, size, _) in sprite_tables(analysis).items()}


def main():
    analysis_module = importlib.import_module(game_profile.ANALYSIS)
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else game_profile.ROOT / "rom"
    image = game_profile.rom.build_program(game_profile.rom.load_set(source))
    analysis = analysis_module.Analysis(image, analysis_module.load_symbols(game_profile.ROOT / "symbols.txt"))
    analysis.run()
    names = {address: symbol.name for address, symbol in analysis.symbols.items()}
    total = 0
    for address, (flags, sprites, size, found) in sorted(sprite_tables(analysis).items()):
        total += size
        print(f"{address:06X}-{address + size - 1:06X} {names.get(address, '?'):24} {len(sprites):4} sprites, "
              f"flags {flags:04X} ({found})")
    print(f"sprite tables: {total} bytes")


if __name__ == "__main__":
    main()
