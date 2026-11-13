"""
Name:        data_walk.py
Description: Sonic the Hedgehog Spinball's data the code hands to its engines, walked from where it hands it over:
             the animated objects' definitions, their sprite descriptors, the sprite tables and the animations
Version:     0.1.0
Created:     13-11-2026
Modified:    13-11-2026
Author:      Sebastian Toyos

Usage: python tools/data_walk.py [cartridge] [--reads FOLDER]
(the coverage takes spans() through the profile's DATA_WALK; with --reads, the report lists what the animation
engine read in the scenarios' runs that the walk does not have, and what it has that other code reads)

  definition     what make_animated_object (0D5F16) takes as its first argument, 12 bytes: the address of a
                 sprite descriptor, the address of the object's animation (its field 0), a byte its field 28 takes,
                 a byte its fields 2A and 2B take, and a word it ors into its field 22 (0D5F6C-0D5F94, 0D5FC8).
                 Found where the code passes one: "pea DEFINITION.l" just before the call (63 calls), or an entry
                 of a table it indexes by the current level (FF75B0, 0-3: 0DDE70, 0DDF14-0DDF1E "move.l
                 (A0,D0.w), -(A7)" with A0 the table), four entries; or the long of an animation's command 0C.
                 The definitions the level's objects hand over (their field 18) are not walked yet.
  descriptor     what a definition's first long points at, 8 bytes: the sprite table, then two words the object's
                 fields 1E and 20 take (0D5FD2-0D5FDC, 0D6048-0D604A).
  sprite table   a descriptor's first long, which the sprite loader (0D7D02) reads (tools/spinball_graphics.py);
                 or a table the code stores straight into field 0A of what an object's field 3A points at
                 ("movea.l ($3a,An), Am" then "move.l #TABLE, ($a,Am)": 0E5F42-0E5F46...).
  animation      a definition's second long, or an entry of an animation list: steps (tools/spinball_animation.py)
                 walked from there, following where they go (03, 04, the tables of 06) until an end (00) or a step
                 that goes elsewhere for good (03); after a step that gives the object back to its owner's code
                 (a frame, 01, 07, 08, 09: the owner may give it another animation), what does not read as a step
                 is the animation's end (the animation at 03948A ends with 01 at 0394A8, before Toxic Caves'
                 tileset at 0394AA), and so is a place the code names (an anchor: what it hands over, the start
                 of a list or a table, an address an instruction reads or takes: an animation that runs on stops
                 there). A frame shows a sprite of its object's table, so a frame of a sprite the table does not
                 have is no step. The definitions their 0C commands hold are walked too, and the
                 functions their 10 commands call and the tables their values read are listed.
  animation list a list of animations' addresses the code gives an object one of: it takes an entry, less 2, as
                 the object's field 0 (the player's, 0DB800-0DB80C "movea.l #LIST, A0; move.l (A0,D0.l), D0;
                 subq.l #2, D0; move.l D0, (A1)"), or an entry of the list a table by the current level holds
                 (0E1ADE-0E1AF4: the four tables' lists). A list's entries go on while each is the address of an
                 animation that walks whole (a step of its object's sprites: as many as the biggest table has),
                 and stop at one that is not, or where something walked begins.
A place that does not read as what it is taken for stops the walk with what is wrong.
"""
import glob
import importlib
import struct
import sys
from collections import defaultdict
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]
import game_profile  # noqa: E402
from m68000.analysis import data_places  # noqa: E402  (the places an instruction reads or takes the address of)
import spinball_animation as animation  # noqa: E402
import spinball_graphics as graphics  # noqa: E402

MAKE_ANIMATED_OBJECT = 0x0D5F16     # takes a definition first
LEVELS = 4                          # the tables the game has: what a table indexed by the level holds
DEFINITION_SIZE = 12
DESCRIPTOR_SIZE = 8
SPRITE_LINK_FIELD = 0x3A            # an object's link to the structure that holds its sprite table
SPRITE_TABLE_FIELD = 0x0A           # that structure's sprite table
ANIMATION_ENGINE = (0x0D58B0, 0x0D60E2)     # the code that reads animations (for the report: 0D58B0-0D60E0)


def long_at(image, address):
    return struct.unpack_from(">I", image, address)[0] & 0xFFFFFF


class Walk:
    """The walk: definitions, descriptors and sprite tables, animations and their lists"""

    def __init__(self, analysis):
        self.analysis = analysis
        self.image = analysis.image
        self.definitions = {}           # {address: how it was found}
        self.descriptors = {}
        self.sprite_tables = {}         # {address: (flags, sprites, size, how it was found)}
        self.level_tables = {}          # {address: how it was found}: tables of four definitions, a level each
        self.animations = {}            # {start: how it was found}
        self.steps = {}                 # {address: Step}
        self.functions = {}             # {code address: the step that calls it}
        self.value_tables = {}          # {address: (kind, the step that reads it)}
        self.animation_lists = {}       # {address: (entries, how it was found)}
        self.list_tables = {}           # {address: how it was found}: tables of four lists, a level each
        self.anchors = set()            # places the code names: an animation that runs on ends there

    # ---- what the code hands over ----

    def run(self):
        instructions = sorted(self.analysis.instructions.items())
        lists = []
        for position, (address, instruction) in enumerate(instructions):
            if instruction.target == MAKE_ANIMATED_OBJECT and instruction.flow == "call":
                self.call_site(instructions, position, address)
            self.sprite_table_store(instructions, position, address, instruction)
            lists.extend(self.animation_list_load(instructions, position, address))
        self.anchors = set(self.definitions) | set(self.level_tables) | set(self.list_tables)             | {table for table, _ in lists} | set(self.sprite_tables)
        for instruction in self.analysis.instructions.values():
            self.anchors.update(place for place in data_places(instruction) if place < len(self.image))
        self.walk_definitions()
        biggest = max(len(sprites) for _, sprites, _, _ in self.sprite_tables.values())
        for table, found in lists:
            self.walk_list(table, found, biggest)
        self.walk_definitions()
        for descriptor in sorted(self.descriptors):
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

    def animation_list_load(self, instructions, position, address):
        """[(list, how it was found)] for "movea.l #TABLE, An" whose entry, less 2, goes into an object's field
        0 a few instructions on: TABLE is a list of animations, or (the entry is a list) a table of four"""
        instruction = instructions[position][1]
        operands = instruction.operands
        if instruction.mnemonic != "movea" or operands[0].mode != "immediate":
            return []
        table = operands[0].value & 0xFFFFFF
        register = operands[1].reg
        holds_lists = False
        following = [step for _, step in instructions[position + 1:position + 10]]
        for index, step in enumerate(following):
            ops = step.operands
            if step.mnemonic == "movea" and len(ops) == 2 and ops[0].mode == "index" and ops[0].reg == register:
                holds_lists, register = True, ops[1].reg
            elif step.mnemonic == "subq" and step.size == "l" and len(ops) == 2 and ops[0].value == 2 \
                    and index + 1 < len(following) and following[index + 1].mnemonic == "move" \
                    and following[index + 1].operands[0].mode == "dreg" \
                    and following[index + 1].operands[0].reg == ops[1].reg \
                    and following[index + 1].operands[1].mode == "indirect":
                found = f"{'a table of lists by the level' if holds_lists else 'a list'}, read at {address:06X}"
                if not holds_lists:
                    return [(table, found)]
                self.list_tables[table] = found
                return [(long_at(self.image, table + 4 * level), f"level {level} of {table:06X}") for level in range(LEVELS)]
        return []

    # ---- the walks ----

    def walk_definitions(self):
        walked = set(getattr(self, "_definitions_walked", ()))
        while len(walked) < len(self.definitions):
            for definition in sorted(set(self.definitions) - walked):
                walked.add(definition)
                descriptor = long_at(self.image, definition)
                self.descriptors.setdefault(descriptor, f"definition {definition:06X}")
                table = long_at(self.image, descriptor)
                self.add_sprite_table(table, f"descriptor {descriptor:06X}")
                sprites = len(self.sprite_tables[table][1])
                self.walk_animation(long_at(self.image, definition + 4), f"definition {definition:06X}", sprites)
        self._definitions_walked = walked

    def problem_with(self, step, sprites):
        """What makes a step impossible for an object whose sprite table holds 'sprites' sprites, or None"""
        size = len(self.image)
        if step.kind == "frame":
            sprite = animation.u16(self.image, step.address) & 0x3FFF
            if sprite != animation.FRAME_NONE and sprite >= sprites:
                return f"{step.address:06X}: frame of sprite {sprite}, its object's table has {sprites}"
        for target in step.targets:
            if target >= size or target & 1:
                return f"{step.address:06X}: goes to {target:06X}"
        for definition in step.definitions:
            if definition + DEFINITION_SIZE > size or definition & 1 or long_at(self.image, definition) + 8 > size:
                return f"{step.address:06X}: makes an object from {definition:06X}, no definition"
        for function in step.functions:
            if function not in self.analysis.instructions and not self.analysis.clean(function):
                return f"{step.address:06X}: calls {function:06X}, which is no code"
        return None

    def walk_steps(self, start, sprites):
        """({address: Step} of the steps from 'start' not walked yet, the first problem or None)"""
        steps = {}
        work = [(start, False)]
        while work:
            address, after_yield = work.pop()
            while address not in self.steps and address not in steps:
                try:
                    step = animation.read_step(self.image, address)
                    problem = self.problem_with(step, sprites)
                except (ValueError, struct.error) as error:
                    problem = str(error)
                if problem:
                    if after_yield:
                        break
                    return steps, problem
                steps[address] = step
                for target in step.targets:
                    work.append((target, False))
                if not step.goes_on:
                    break
                after_yield = step.yields
                address += step.length
                if address in self.anchors:
                    break
        return steps, None

    def take_steps(self, steps):
        for address, step in steps.items():
            self.steps[address] = step
            for definition in step.definitions:
                self.definitions.setdefault(definition, f"made by the animation step {address:06X}")
            for function in step.functions:
                self.functions.setdefault(function, address)
            for table, kind in step.tables:
                self.value_tables.setdefault(table, (kind, address))

    def walk_animation(self, start, found, sprites):
        """An animation that has to walk whole"""
        steps, problem = self.walk_steps(start, sprites)
        if problem:
            raise SystemExit(f"the animation from {start:06X} ({found}): {problem}")
        self.animations.setdefault(start, found)
        self.take_steps(steps)

    def walk_list(self, table, found, sprites):
        """A list of animations: its entries while each is an animation that walks whole"""
        if table in self.animation_lists:
            return
        known = set(self.steps) | set(self.definitions) | set(self.descriptors) | set(self.animation_lists)
        index = 0
        while True:
            where = table + 4 * index
            if where + 4 > len(self.image) or (index and where in known):
                break
            entry = long_at(self.image, where)
            if entry >= len(self.image) or entry & 1 or struct.unpack_from(">I", self.image, where)[0] >> 24:
                break
            steps, problem = self.walk_steps(entry, sprites)
            if problem:
                break
            self.animations.setdefault(entry, f"entry {index} of the list {table:06X} ({found})")
            self.take_steps(steps)
            known |= set(steps)
            index += 1
        self.animation_lists[table] = (index, found)

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
        for table in self.level_tables:
            found[table] = (table + 4 * LEVELS, "definitions by level")
        for table in self.list_tables:
            found[table] = (table + 4 * LEVELS, "animation lists by level")
        for table, (entries, _) in self.animation_lists.items():
            found[table] = (table + 4 * entries, "animation list")
        for address, step in self.steps.items():
            found[address] = (address + step.length, "animation step")
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


def check_reads(walk, folder):
    """Against the scenarios' rom_reads.txt: the bytes the animation engine read that the walk does not have, and
    the walked animation bytes other code reads"""
    step_bytes = set()
    for address, step in walk.steps.items():
        step_bytes.update(range(address, address + step.length))
    walked = set(step_bytes)
    for first, (stop, kind) in walk.spans().items():
        walked.update(range(first, stop))
    engine, others = defaultdict(set), defaultdict(set)
    for path in glob.glob(str(Path(folder) / "**" / "rom_reads.txt"), recursive=True):
        for line in open(path, encoding="ascii"):
            if line.startswith("#") or not line.strip():
                continue
            pc, span = line.split()
            first, last = (int(value, 16) for value in span.split("-"))
            pc = int(pc, 16)
            for address in range(first, last + 1):
                (engine if ANIMATION_ENGINE[0] <= pc < ANIMATION_ENGINE[1] else others)[address].add(pc)
    missing = sorted(set(engine) - walked)
    runs = []
    for address in missing:
        if runs and address - runs[-1][1] <= 2:
            runs[-1][1] = address
        else:
            runs.append([address, address])
    steps_read = {address for address in step_bytes if address in others}
    print(f"read by the animation engine: {len(engine)} bytes; not walked: {len(missing)} in {len(runs)} runs")
    print("  " + " ".join(f"{first:06X}-{last:06X}" for first, last in runs[:40]) + (" ..." if len(runs) > 40 else ""))
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
    for table, (entries, found) in sorted(walk.animation_lists.items()):
        print(f"animation list {table:06X}: {entries} entries ({found})")
    print("functions the animations call: " + " ".join(f"{function:06X} (step {step:06X})"
                                                         for function, step in sorted(walk.functions.items())))
    unknown = sorted(function for function in walk.functions if function not in analysis.instructions)
    if unknown:
        print("  ... that the analysis does not know (for symbols.txt): " + " ".join(f"{function:06X}" for function in unknown))
    print("tables the animations' values read: " + " ".join(f"{table:06X} ({kind})"
                                                               for table, (kind, _) in sorted(walk.value_tables.items())))
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
