"""
Name:        data_walk.py
Description: Sonic the Hedgehog Spinball's data the code hands to its engines, walked from where it hands it
             over, and checked against what the reference reads
Version:     0.1.0
Created:     13-11-2026
Modified:    16-11-2026
Author:      Sebastian Toyos

Usage: python tools/data_walk.py [cartridge] [--reads FOLDER]
(the coverage takes spans() through the profile's DATA_WALK, and says what each of the profile's READERS read
in the scenarios that no table describes; with --reads, the report lists the animations' bytes other code reads)

The walk starts where the code hands its data over or keeps it, and reads each place as the code that takes it
reads it; what it reads names more places. By subject:
  tools/walk_patterns.py     the patterns of the game's C (the arguments of a call, a function's prologue) and of
                             the tables it reads by the level or by a counter that wraps
  tools/walk_animations.py   the animated objects' definitions, descriptors, sprite tables, animations and lists,
                             and the tables' objects
  tools/walk_graphics.py     the tiles the loaders get, the palettes, the colour cycles
  tools/walk_levels.py       the planes' maps and brushes, the collision, the flippers, the tables' values
  tools/walk_texts.py        the texts the functions that read them get
  tools/walk_screens.py      the front end's screens (maps, palettes, sprites) and the Z80's program
  tools/walk_sequences.py    the front end's scripts, a command at a time
  tools/walk_states.py       the chains of states 0F789A sets the objects to
A place that does not read as what it is taken for stops the walk with what is wrong.
"""
import glob
import importlib
import sys
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
from walk_screens import ScreensWalk  # noqa: E402
from walk_sequences import SequencesWalk  # noqa: E402
from walk_states import StatesWalk  # noqa: E402
from walk_texts import TextsWalk  # noqa: E402

class Walk(CodePatterns, AnimationWalk, GraphicsWalk, LevelsWalk, TextsWalk, ScreensWalk,
           SequencesWalk, StatesWalk):
    """The walk: what each subject finds, from the code and from what it finds"""

    def __init__(self, analysis):
        self.analysis = analysis
        self.image = analysis.image
        self.anchors = set()            # places the code names: an animation that runs on ends there
        self.init_patterns()
        self.init_animations()
        self.init_graphics()
        self.init_levels()
        self.init_texts()
        self.init_screens()
        self.init_sequences()
        self.init_states()

    def run(self):
        self.index_code()
        instructions = self.ordered
        self.find_makers()
        self.interpolated_tables()
        self.parallel_tables()
        lists = []
        for position, (address, instruction) in enumerate(instructions):
            if instruction.flow == "call" and instruction.target in self.makers:
                self.call_site(position, address, instruction.target)
            if instruction.flow == "call" and instruction.target in TILE_LOADERS:
                self.tileset_load(position, address, instruction.target)
            self.level_pointer_store(position, address, instruction)
            self.level_value_load(position, address, instruction)
            self.block_copy(position, address, instruction)
            self.pointer_loop(position, address, instruction)
            self.sequence_counter(position, address, instruction)
            self.masked_index(position, address, instruction)
            self.counted_loop(position, address, instruction)
            self.pointed_record(position, address, instruction)
            self.sprite_table_store(instructions, position, address, instruction)
            lists.extend(self.animation_list_load(instructions, position, address))
            self.object_table_load(instructions, position, address)
        self.pair_planes()
        self.find_cycles()
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
        self.walk_zones()
        self.walk_texts()
        self.walk_screens()
        self.walk_gems()
        self.walk_sequences()
        self.walk_states()
        self.handed |= self.screen_places() | self.sequence_places() | self.state_places()
        self.walk_screen_sprite_tables()
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
        self.spans_texts(found)
        self.spans_screens(found)
        self.spans_sequences(found)
        self.spans_states(found)
        self.spans_pointed(found)
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
    """Against the scenarios' rom_reads.txt: the walked animation bytes code other than the animation engine reads
    (what each reader reads that no table describes, the core's coverage says, by the profile's READERS)"""
    engine = game_profile.READERS["animation engine"]
    step_bytes = set()
    for address, step in walk.steps.items():
        step_bytes.update(range(address, address + step.length))
    others = set()
    for path in glob.glob(str(Path(folder) / "**" / "rom_reads.txt"), recursive=True):
        for line in open(path, encoding="ascii"):
            if line.startswith("#") or not line.strip():
                continue
            pc, span = line.split()
            first, last = (int(value, 16) for value in span.split("-"))
            if not any(start <= int(pc, 16) < stop for start, stop in engine):
                others.update(range(first, last + 1))
    steps_read = sorted(step_bytes & others)
    print(f"walked animation bytes other code reads: {len(steps_read)}"
          + ("  " + " ".join(f"{address:06X}" for address in steps_read[:20]) if steps_read else ""))


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
    print(f"scripts: {len(walk.scripts)}, sprite groups: {len(walk.sprite_groups)}; the functions they call: "
          + " ".join(f"{function:06X}" for function in sorted(walk.script_calls)))
    unknown = sorted(function for function in walk.script_calls if function not in analysis.instructions)
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
