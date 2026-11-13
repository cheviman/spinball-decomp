"""
Name:        data_walk.py
Description: Sonic the Hedgehog Spinball's data the code hands to its engines, walked from where it hands it
             over, and checked against what the reference reads
Version:     0.1.0
Created:     13-11-2026
Modified:    13-11-2026
Author:      Sebastian Toyos

Usage: python tools/data_walk.py [cartridge] [--reads FOLDER]
(the coverage takes spans() through the profile's DATA_WALK; with --reads, the report lists what the code that
reads the walked data (READERS) read in the scenarios' runs that the walk does not have, and the animations'
bytes other code reads)

The walk starts where the code hands its data over or keeps it, and reads each place as the code that takes it
reads it; what it reads names more places. By subject:
  tools/walk_patterns.py     the patterns of the game's C (the arguments of a call, a function's prologue) and of
                             the tables it reads by the level or by a counter that wraps
  tools/walk_animations.py   the animated objects' definitions, descriptors, sprite tables, animations and lists,
                             and the tables' objects
  tools/walk_graphics.py     the tiles the loaders get, the palettes, the colour cycles
  tools/walk_levels.py       the planes' maps and brushes, the collision, the flippers, the tables' values
A place that does not read as what it is taken for stops the walk with what is wrong.
"""
import glob
import importlib
import sys
from collections import defaultdict
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]
import game_profile  # noqa: E402
from m68000.analysis import data_places  # noqa: E402  (the places an instruction reads or takes the address of)
import spinball_levels as levels  # noqa: E402
from walk_animations import AnimationWalk  # noqa: E402
from walk_graphics import TILE_LOADERS, GraphicsWalk  # noqa: E402
from walk_levels import LevelsWalk  # noqa: E402
from walk_patterns import LEVELS, CodePatterns, long_at  # noqa: E402

READERS = {                         # the code that reads what the walk has (for the report)
    "animation engine": (0x0D58B0, 0x0D60E2),
    "SSC decoder": (0x0D6B88, 0x0D6C2A),
    "tile loader": (0x0F3BB8, 0x0F3C06),
    "C2 decoder": (0x0F5A7A, 0x0F5B9E),
    "plane drawers": (0x0D8D0E, 0x0D8F22),
}
READER_FUNCTIONS = {                # the same, as the functions that make it up
    "collision code": (0x0DB900, 0x0DBC60, 0x0DBD1E, 0x0DC3DE, 0x0DCBB0, 0x0DCDFE, 0x0DCFC0, 0x0DE08E, 0x0E1D10),
    "palette code": (0x0D6C2A, 0x0D85A0, 0x0D863E, 0x0D873A),
}


class Walk(CodePatterns, AnimationWalk, GraphicsWalk, LevelsWalk):
    """The walk: what each subject finds, from the code and from what it finds"""

    def __init__(self, analysis):
        self.analysis = analysis
        self.image = analysis.image
        self.anchors = set()            # places the code names: an animation that runs on ends there
        self.init_patterns()
        self.init_animations()
        self.init_graphics()
        self.init_levels()

    def run(self):
        self.index_code()
        instructions = self.ordered
        self.find_makers()
        lists = []
        for position, (address, instruction) in enumerate(instructions):
            if instruction.flow == "call" and instruction.target in self.makers:
                self.call_site(position, address, instruction.target)
            if instruction.flow == "call" and instruction.target in TILE_LOADERS:
                self.tileset_load(position, address, instruction.target)
            self.level_pointer_store(position, address, instruction)
            self.level_value_load(position, address, instruction)
            self.cycle_load(position, address, instruction)
            self.sprite_table_store(instructions, position, address, instruction)
            lists.extend(self.animation_list_load(instructions, position, address))
            self.object_table_load(instructions, position, address)
        self.pair_planes()
        self.anchors = set(self.definitions) | set(self.level_tables) | set(self.list_tables) \
            | {table for table, _ in lists} | set(self.sprite_tables) | set(self.object_tables) \
            | set(self.tilesets) | set(self.tileset_tables) | set(self.pointer_tables)
        for table in self.pointer_tables:
            self.anchors.update(long_at(self.image, table + 4 * level) for level in range(LEVELS))
        self.anchors.update(value for _, value, _, _ in self.kept if value is not None)
        self.handed = set(self.anchors)
        for instruction in self.analysis.instructions.values():
            self.anchors.update(place for place in data_places(instruction) if place < len(self.image))
        self.walk_planes()
        self.walk_collisions()
        self.walk_flippers()
        self.walk_definitions()
        biggest = max(len(sprites) for _, sprites, _, _ in self.sprite_tables.values())
        for table, found in lists:
            self.walk_list(table, found, biggest)
        self.walk_definitions()
        for descriptor in sorted(self.descriptors):
            self.add_sprite_table(long_at(self.image, descriptor), f"descriptor {descriptor:06X}")
        self.handed |= set(self.sprite_tables)
        self.walk_palettes()

    def spans(self):
        """{first: (stop, kind)} of what the walk reads"""
        found = {}
        self.spans_animations(found)
        self.spans_graphics(found)
        self.spans_levels(found)
        self.spans_palettes(found)
        self.spans_flippers(found)
        self.spans_patterns(found)
        self.spans_level_records(found)
        self.spans_c2_masks(found)
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



def check_reads(walk, folder):
    """Against the scenarios' rom_reads.txt: the bytes each of READERS read that the walk does not have, and the
    walked animation bytes other code reads"""
    step_bytes = set()
    for address, step in walk.steps.items():
        step_bytes.update(range(address, address + step.length))
    walked = set(step_bytes)
    for first, (stop, kind) in walk.spans().items():
        walked.update(range(first, stop))
    walked |= walk.c2_read_past()
    walked |= walk.past_maps()
    by_reader, others = defaultdict(lambda: defaultdict(set)), defaultdict(set)
    for path in glob.glob(str(Path(folder) / "**" / "rom_reads.txt"), recursive=True):
        for line in open(path, encoding="ascii"):
            if line.startswith("#") or not line.strip():
                continue
            pc, span = line.split()
            first, last = (int(value, 16) for value in span.split("-"))
            pc = int(pc, 16)
            reader = next((name for name, (start, stop) in READERS.items() if start <= pc < stop), None) \
                or next((name for name, functions in READER_FUNCTIONS.items() if walk.function_of(pc) in functions),
                        None)
            for address in range(first, last + 1):
                (by_reader[reader] if reader else others)[address].add(pc)
    for reader in list(READERS) + list(READER_FUNCTIONS):
        read = by_reader[reader]
        missing = sorted(set(read) - walked)
        runs = []
        for address in missing:
            if runs and address - runs[-1][1] <= 2:
                runs[-1][1] = address
            else:
                runs.append([address, address])
        print(f"read by the {reader}: {len(read)} bytes; not walked: {len(missing)} in {len(runs)} runs"
              + ("\n  " + " ".join(f"{first:06X}-{last:06X}" for first, last in runs[:40]) if runs else "")
              + (" ..." if len(runs) > 40 else ""))
    steps_read = {address for address in step_bytes if address in others}
    print(f"walked animation bytes other code reads: {len(steps_read)}"
          + ("  " + " ".join(f"{address:06X}" for address in sorted(steps_read)[:20]) if steps_read else ""))



def main():
    arguments = [argument for argument in sys.argv[1:]]
    reads = None
    if "--reads" in arguments:
        at = arguments.index("--reads")
        reads = arguments[at + 1]
        del arguments[at:at + 2]
    analysis_module = importlib.import_module(game_profile.ANALYSIS)
    source = Path(arguments[0]) if arguments else game_profile.ROOT / "rom"
    image = game_profile.rom.build_program(game_profile.rom.load_set(source))
    analysis = analysis_module.Analysis(image, analysis_module.load_symbols(game_profile.ROOT / "symbols.txt"))
    analysis.run()
    walk = walk_of(analysis)
    names = {address: symbol.name for address, symbol in analysis.symbols.items()}
    print(f"definitions: {len(walk.definitions)}, sprite descriptors: {len(walk.descriptors)}, animations: "
          f"{len(walk.animations)} ({len(walk.steps)} steps)")
    for function, (argument, found) in sorted(walk.makers.items()):
        print(f"maker {function:06X} {names.get(function, '')}: the definition is its argument {argument} ({found})")
    for table, (kind, found) in sorted(walk.pointer_tables.items()):
        print(f"{kind} by level {table:06X} ({found})")
    for address, (width, rows, found) in sorted(walk.maps.items()):
        print(f"map {address:06X}-{address + 2 * width * rows - 1:06X} {width}x{rows} ({found})")
    for address, (rows, size, found) in sorted(walk.collisions.items()):
        print(f"collision {address:06X}-{address + size - 1:06X} {levels.SECTORS_ACROSS}x{rows} sectors ({found})")
    for address, (count, found) in sorted(walk.brushes.items()):
        print(f"brushes {address:06X}-{address + levels.BRUSH_BYTES * count - 1:06X} {count} ({found})")
    for address, (kind, size, found) in sorted(walk.tilesets.items()):
        print(f"{address:06X}-{address + size - 1:06X} {names.get(address, '?'):28} {kind} ({found})")
    for table, (objects, found) in sorted(walk.object_tables.items()):
        print(f"table objects {table:06X}: {objects} ({found})")
    for table, (entries, found) in sorted(walk.animation_lists.items()):
        print(f"animation list {table:06X}: {entries} entries ({found})")
    print("functions the animations call: " + " ".join(f"{function:06X} (step {step:06X})"
                                                         for function, step in sorted(walk.functions.items())))
    unknown = sorted(function for function in walk.functions if function not in analysis.instructions)
    if unknown:
        print("  ... that the analysis does not know (for symbols.txt): "
              + " ".join(f"{function:06X}" for function in unknown))
    print("tables the animations' values read: "
          + " ".join(f"{table:06X} ({kind})" for table, (kind, _) in sorted(walk.value_tables.items())))
    for address, (flags, sprites, size, found) in sorted(walk.sprite_tables.items()):
        print(f"{address:06X}-{address + size - 1:06X} {names.get(address, '?'):24} {len(sprites):4} sprites ({found})")
    kinds = {}
    for first, (stop, kind) in walk.spans().items():
        kinds[kind] = kinds.get(kind, 0) + stop - first
    print("walked: " + ", ".join(f"{kind} {count}" for kind, count in sorted(kinds.items())))
    if reads:
        check_reads(walk, reads)


if __name__ == "__main__":
    main()
