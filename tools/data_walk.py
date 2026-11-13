"""
Name:        data_walk.py
Description: Sonic the Hedgehog Spinball's data the code hands to its engines, walked from where it hands it over:
             the animated objects' definitions, their sprite descriptors and the sprite tables
Version:     0.1.0
Created:     13-11-2026
Modified:    13-11-2026
Author:      Sebastian Toyos

Usage: python tools/data_walk.py [cartridge]       (the coverage takes spans() through the profile's DATA_WALK)

  definition     what make_animated_object (0D5F16) takes as its first argument, 12 bytes: the address of a
                 sprite descriptor, the address of the object's animation (its field 0), a byte its field 28 takes,
                 a byte its fields 2A and 2B take, and a word it ors into its field 22 (0D5F6C-0D5F94, 0D5FC8).
                 Found where the code passes one: "pea DEFINITION.l" just before the call (63 calls), or an entry
                 of a table it indexes by the current level (FF75B0, 0-3: 0DDE70, 0DDF14-0DDF1E "move.l
                 (A0,D0.w), -(A7)" with A0 the table), four entries. The definitions the level's objects hand over
                 (their field 18) and the ones animations hold are not walked yet.
  descriptor     what a definition's first long points at, 8 bytes: the sprite table, then two words the object's
                 fields 1E and 20 take (0D5FD2-0D5FDC, 0D6048-0D604A).
  sprite table   a descriptor's first long, which the sprite loader (0D7D02) reads (tools/spinball_graphics.py);
                 or a table the code stores straight into field 0A of what an object's field 3A points at
                 ("movea.l ($3a,An), Am" then "move.l #TABLE, ($a,Am)": 0E5F42-0E5F46...).
A place that does not read as what it is taken for stops the walk with what is wrong.
"""
import importlib
import struct
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]
import game_profile  # noqa: E402
import spinball_graphics as graphics  # noqa: E402

MAKE_ANIMATED_OBJECT = 0x0D5F16     # takes a definition first
LEVELS = 4                          # the tables the game has: what a table indexed by the level holds
DEFINITION_SIZE = 12
DESCRIPTOR_SIZE = 8
SPRITE_LINK_FIELD = 0x3A            # an object's link to the structure that holds its sprite table
SPRITE_TABLE_FIELD = 0x0A           # that structure's sprite table


def long_at(image, address):
    return struct.unpack_from(">I", image, address)[0] & 0xFFFFFF


class Walk:
    """The walk: definitions, descriptors and sprite tables, each {address: how it was found}"""

    def __init__(self, analysis):
        self.analysis = analysis
        self.image = analysis.image
        self.definitions = {}
        self.descriptors = {}
        self.sprite_tables = {}         # {address: (flags, sprites, size, how it was found)}

    def run(self):
        instructions = sorted(self.analysis.instructions.items())
        for position, (address, instruction) in enumerate(instructions):
            if instruction.target == MAKE_ANIMATED_OBJECT and instruction.flow == "call":
                self.call_site(instructions, position, address)
            self.sprite_table_store(instructions, position, address, instruction)
        for definition, found in sorted(self.definitions.items()):
            descriptor = long_at(self.image, definition)
            self.descriptors.setdefault(descriptor, f"definition {definition:06X}")
        for descriptor, found in sorted(self.descriptors.items()):
            self.add_sprite_table(long_at(self.image, descriptor), f"descriptor {descriptor:06X}")

    def call_site(self, instructions, position, address):
        """The definition a call of make_animated_object hands over, where the code says which"""
        previous = instructions[position - 1][1]
        if previous.mnemonic == "pea" and previous.operands[0].mode == "abs_long":
            self.definitions.setdefault(previous.operands[0].value & 0xFFFFFF, f"passed at {address:06X}")
            return
        operand = previous.operands[1] if len(previous.operands) == 2 else None
        source = previous.operands[0] if previous.operands else None
        if previous.mnemonic == "move" and source is not None and source.mode == "index" and operand is not None \
                and operand.mode == "predec" and position >= 2:
            loader = instructions[position - 2][1]
            if loader.mnemonic == "movea" and loader.operands[0].mode == "immediate" \
                    and loader.operands[1].reg == source.reg:
                table = loader.operands[0].value & 0xFFFFFF
                for index in range(LEVELS):
                    self.definitions.setdefault(long_at(self.image, table + 4 * index),
                                                f"entry {index} of {table:06X}, passed at {address:06X}")
                self.level_tables = getattr(self, "level_tables", {})
                self.level_tables[table] = f"indexed by the level at {address:06X}"

    def sprite_table_store(self, instructions, position, address, instruction):
        operands = instruction.operands
        if instruction.mnemonic == "move" and instruction.size == "l" and len(operands) == 2 \
                and operands[0].mode == "immediate" and operands[1].mode == "disp" \
                and operands[1].disp == SPRITE_TABLE_FIELD and position:
            previous = instructions[position - 1][1]
            if previous.address + previous.length == address and previous.mnemonic == "movea" \
                    and previous.operands[0].mode == "disp" and previous.operands[0].disp == SPRITE_LINK_FIELD \
                    and previous.operands[1].reg == operands[1].reg:
                self.add_sprite_table(operands[0].value & 0xFFFFFF, f"stored by {address:06X}")

    def add_sprite_table(self, address, found):
        if address in self.sprite_tables:
            return
        try:
            flags, sprites, size = graphics.read_table(self.image, address)
        except (ValueError, IndexError, struct.error) as problem:
            raise SystemExit(f"{address:06X} ({found}) does not read as a sprite table: {problem}")
        self.sprite_tables[address] = (flags, sprites, size, found)

    def spans(self):
        found = {}
        for address in self.definitions:
            found[address] = (address + DEFINITION_SIZE, "definition")
        for address in self.descriptors:
            found[address] = (address + DESCRIPTOR_SIZE, "sprite descriptor")
        for table in getattr(self, "level_tables", {}):
            found[table] = (table + 4 * LEVELS, "definitions by level")
        for address, (_, _, size, _) in self.sprite_tables.items():
            found[address] = (address + size, "sprite table")
        return found


_walks = {}


def walk_of(analysis):
    """The walk of an analysis (made once)"""
    if id(analysis) not in _walks:
        walk = Walk(analysis)
        walk.run()
        _walks[id(analysis)] = walk
    return _walks[id(analysis)]


def sprite_tables(analysis):
    """{address: (flags, sprites, size, how it was found)}"""
    return walk_of(analysis).sprite_tables


def spans(analysis):
    """For the coverage (the profile's DATA_WALK): {first: (stop, kind)} of what the walk reads"""
    return walk_of(analysis).spans()


def main():
    analysis_module = importlib.import_module(game_profile.ANALYSIS)
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else game_profile.ROOT / "rom"
    image = game_profile.rom.build_program(game_profile.rom.load_set(source))
    analysis = analysis_module.Analysis(image, analysis_module.load_symbols(game_profile.ROOT / "symbols.txt"))
    analysis.run()
    walk = walk_of(analysis)
    names = {address: symbol.name for address, symbol in analysis.symbols.items()}
    print(f"definitions: {len(walk.definitions)}, sprite descriptors: {len(walk.descriptors)}")
    for address, (flags, sprites, size, found) in sorted(walk.sprite_tables.items()):
        print(f"{address:06X}-{address + size - 1:06X} {names.get(address, '?'):24} {len(sprites):4} sprites ({found})")
    kinds = {}
    for first, (stop, kind) in walk.spans().items():
        kinds[kind] = kinds.get(kind, 0) + stop - first
    print("walked: " + ", ".join(f"{kind} {count}" for kind, count in sorted(kinds.items())))


if __name__ == "__main__":
    main()
