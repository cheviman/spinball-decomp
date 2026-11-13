"""
Name:        data_walk.py
Description: Sonic the Hedgehog Spinball's data the code hands to its engines, walked from where it hands it over:
             the animated objects' definitions, their sprite descriptors, the sprite tables, the animations and
             the tables' objects
Version:     0.1.0
Created:     13-11-2026
Modified:    13-11-2026
Author:      Sebastian Toyos

Usage: python tools/data_walk.py [cartridge] [--reads FOLDER]
(the coverage takes spans() through the profile's DATA_WALK; with --reads, the report lists what the code that
reads the walked data (the animation engine, the tile loaders) read in the scenarios' runs that the walk does not
have, and the animations' bytes other code reads)

  definition     what make_animated_object (0D5F16) takes as its first argument, 12 bytes: the address of a
                 sprite descriptor, the address of the object's animation (its field 0), a byte its field 28 takes,
                 a byte its fields 2A and 2B take, and a word it ors into its field 22 (0D5F6C-0D5F94, 0D5FC8).
                 Found where the code passes one, to make_animated_object or to a function that hands one of its
                 own arguments on to it as the definition (a maker: 0E1ECA and 0E1F5C, their second; found from
                 the code, the register the function's prologue loads from its stack arguments pushed as the
                 definition, and nothing writing it on the way), back from the call a push at a time, through the
                 jumps and branches that come in among the pushes: "pea DEFINITION.l" as that argument, or an
                 entry of a table the code indexes by the current level (FF75B0, 0-3: 0DDE70, 0DDF14-0DDF1E
                 "move.l (A0,D0.w), -(A7)" with A0 the table, "movea.l #TABLE, A0" just before), four entries;
                 the long of an animation's command 0C; or the long of a table's object (below).
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
  table objects  a table's objects, 20 bytes each, which the code that sets the table up copies one by one into
                 a game object (the one the record's second byte numbers, from FF784C, 34 bytes each), at its byte
                 0E: a type, a number, a word, x, y, two bytes, the definition of its animated object (field 18,
                 0 for none: 0E4E34 "tst.l ($18,A2)", then make_animated_object), and six bytes. Found where the
                 code does it: "movea.l #TABLE, A0; lea (A0,D0.w), A0; movea.l A0, An", then a loop that moves An
                 on by 20 until "cmpi.w #COUNT, Dn; blt" (Toxic Caves 0E626C, 173; Lava Powerhouse 0E4DFC, 211;
                 Showdown 0E9E7E, 186; The Machine 0F10EE, 158).
  tiles          what the code hands to the functions that load tiles into the VRAM (tools/spinball_compression.py),
                 found like the definitions ("pea TILES.l", or a table by the level), and read as they read it:
                 0D6B88 SSC (its first argument; Toxic Caves' 0D3FE4-0D401A: the level's tiles from the table
                 BFBE0, then the ones of BFBF0 after them, from the tile the first ones' word says); 0F3BB8 a word,
                 then as many tiles as it says, as they are, or C2 if it says 0 or less (its argument); 0F5A5E C2
                 (its second argument; the bonus stage 0FA7FE-0FA826: one of four by FF3CBC). SSC tiles that read
                 a place of the window not written yet, or do not give as many as their word says, are no tiles.
                 Tiles of an odd size are followed by FF, to even the place after them. The C2 decoder reads the
                 masks of the codes' widths at 09BCD2 (four words: the fourth, FFF, is never read), and a code as
                 the three bytes from the one its first bit is in: two bytes past the end, which belong to what
                 follows.
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
import spinball_compression as compression  # noqa: E402
import spinball_graphics as graphics  # noqa: E402

MAKE_ANIMATED_OBJECT = 0x0D5F16     # takes a definition first
SCRATCH = {"D0", "D1", "A0", "A1"}  # the registers a call of the game's C does not keep
PUSHES_WALKED = 64                  # how far back from a call its pushes are looked for
LEVELS = 4                          # the tables the game has: what a table indexed by the level holds
DEFINITION_SIZE = 12
TABLE_OBJECT_SIZE = 20              # a table's object, as the code that sets the table up copies it
TABLE_OBJECT_DEFINITION = 0x0A      # its definition's long
DESCRIPTOR_SIZE = 8
SPRITE_LINK_FIELD = 0x3A            # an object's link to the structure that holds its sprite table
SPRITE_TABLE_FIELD = 0x0A           # that structure's sprite table
TILE_LOADERS = {                    # the functions that load tiles into the VRAM: (what they read, its argument)
    0x0D6B88: ("ssc", 0),           # SSC; the second argument the VRAM's tile
    0x0F3BB8: ("word", 0),          # a word: above 0 that many tiles as they are, else C2; to VRAM 0
    0x0F5A5E: ("c2", 1),            # C2; the first argument the VRAM's address
}
TILESET_PAD = 0xFF                  # what evens the place after tiles of an odd size
C2_MASKS_SIZE = 8                   # four words: 1FF, 3FF, 7FF and FFF, the last not read (codes stop at 11 bits)
READERS = {                         # the code that reads what the walk has (for the report)
    "animation engine": (0x0D58B0, 0x0D60E2),
    "SSC decoder": (0x0D6B88, 0x0D6C2A),
    "tile loader": (0x0F3BB8, 0x0F3C06),
    "C2 decoder": (0x0F5A7A, 0x0F5B9E),
}
C2_READ_PAST = 2                    # the C2 decoder reads a code as the three bytes from its first: past the end


def long_at(image, address):
    return struct.unpack_from(">I", image, address)[0] & 0xFFFFFF


def pushes_long(instruction):
    """Whether an instruction pushes a long onto the stack: pea, or move.l / clr.l to -(A7)"""
    operands = instruction.operands
    return instruction.mnemonic == "pea" or (
        instruction.mnemonic in ("move", "clr") and instruction.size == "l" and operands
        and operands[-1].mode == "predec" and operands[-1].reg == "A7")


def moves_stack(instruction):
    """Whether an instruction moves the stack pointer otherwise (another push or pop, or A7 written)"""
    return instruction.flow in ("call", "return") or any(
        operand.reg == "A7" and operand.mode in ("predec", "postinc", "areg") for operand in instruction.operands)


def writes(instruction, register):
    """Whether an instruction can change 'register'"""
    operands = instruction.operands
    if any(operand.mode in ("predec", "postinc") and operand.reg == register for operand in operands):
        return True
    if instruction.flow == "call":
        return register in SCRATCH
    if instruction.mnemonic in ("cmp", "cmpa", "cmpi", "tst", "btst") or not operands:
        return False
    if instruction.mnemonic == "exg":
        return any(operand.reg == register for operand in operands)
    last = operands[-1]
    return (last.mode in ("areg", "dreg") and last.reg == register) \
        or (last.mode == "reglist" and register in last.registers)


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
        self.object_tables = {}         # {address: (objects, how it was found)}
        self.makers = {MAKE_ANIMATED_OBJECT: (0, "the engine")}     # {function: (its definition's argument, how)}
        self.tilesets = {}              # {address: (kind, size in bytes, how it was found)}
        self.tileset_tables = {}        # {address: how it was found}: tables of four tilesets, a level each
        self.ordered = []               # [(address, Instruction)] of the analysis, in address order
        self.position_of = {}           # {address: its position in ordered}
        self.comes_from = defaultdict(list)     # {address: positions of the jumps and branches that go there}

    # ---- what the code hands over ----

    def run(self):
        instructions = self.ordered = sorted(self.analysis.instructions.items())
        for position, (address, instruction) in enumerate(instructions):
            self.position_of[address] = position
            if instruction.flow in ("jump", "branch") and instruction.target is not None:
                self.comes_from[instruction.target].append(position)
        self.find_makers()
        lists = []
        for position, (address, instruction) in enumerate(instructions):
            if instruction.flow == "call" and instruction.target in self.makers:
                self.call_site(position, address, instruction.target)
            if instruction.flow == "call" and instruction.target in TILE_LOADERS:
                self.tileset_load(position, address, instruction.target)
            self.sprite_table_store(instructions, position, address, instruction)
            lists.extend(self.animation_list_load(instructions, position, address))
            self.object_table_load(instructions, position, address)
        self.anchors = set(self.definitions) | set(self.level_tables) | set(self.list_tables) \
            | {table for table, _ in lists} | set(self.sprite_tables) | set(self.object_tables) \
            | set(self.tilesets) | set(self.tileset_tables)
        for instruction in self.analysis.instructions.values():
            self.anchors.update(place for place in data_places(instruction) if place < len(self.image))
        self.walk_definitions()
        biggest = max(len(sprites) for _, sprites, _, _ in self.sprite_tables.values())
        for table, found in lists:
            self.walk_list(table, found, biggest)
        self.walk_definitions()
        for descriptor in sorted(self.descriptors):
            self.add_sprite_table(long_at(self.image, descriptor), f"descriptor {descriptor:06X}")

    def pushes(self, position, argument):
        """The instructions that can push the stack argument 'argument' (0: the one pushed last) of the call at
        'position': back from it a push at a time, through the jumps and branches that come in on the way; None
        where the stack moves otherwise first, or the way back runs too long"""
        found, seen, work = [], set(), [(position, argument)]
        while work:
            at, left = work.pop()
            here = self.ordered[at][0]
            before = list(self.comes_from.get(here, ()))
            if at:
                previous_address, previous = self.ordered[at - 1]
                if previous_address + previous.length == here and previous.flow not in ("jump", "return"):
                    before.append(at - 1)
            for step in before:
                if (step, left) in seen:
                    continue
                seen.add((step, left))
                if len(seen) > PUSHES_WALKED:
                    return None
                instruction = self.ordered[step][1]
                if instruction.flow in ("jump", "branch"):
                    work.append((step, left))
                elif pushes_long(instruction):
                    if left:
                        work.append((step, left - 1))
                    else:
                        found.append(instruction)
                elif moves_stack(instruction):
                    return None
                else:
                    work.append((step, left))
        return found

    def function_of(self, address):
        """The start of the function an address is in: the last the analysis has at or before it"""
        return max((start for start in self.analysis.functions if start <= address), default=None)

    def prologue(self, function):
        """(the position after it, {register: argument}) of what a function's prologue loads from its stack
        arguments: "movem.l REGISTERS, -(A7)" (or one register's move.l) then "move(a).l (d,A7), Rn", one after
        the other"""
        position = self.position_of.get(function)
        if position is None:
            return None, {}
        first = self.ordered[position][1]
        saved = 0
        if first.mnemonic == "movem" and first.operands[1].mode == "predec" and first.operands[1].reg == "A7":
            saved, position = len(first.operands[0].registers), position + 1
        elif pushes_long(first) and first.mnemonic == "move" and first.operands[0].mode in ("areg", "dreg"):
            saved, position = 1, position + 1
        arguments = {}
        while position < len(self.ordered):
            instruction = self.ordered[position][1]
            operands = instruction.operands
            if instruction.mnemonic not in ("move", "movea") or instruction.size != "l" or len(operands) != 2 \
                    or operands[0].mode != "disp" or operands[0].reg != "A7" \
                    or operands[1].mode not in ("areg", "dreg"):
                break
            arguments[operands[1].reg] = (operands[0].disp - 4 * saved - 4) // 4
            position += 1
        return position, arguments

    def find_makers(self):
        """The functions that hand one of their arguments on to make_animated_object (or to another such
        function) as the definition: the register their prologue loads it into is what they push as the
        definition, and nothing writes it from the prologue to the call"""
        grown = True
        while grown:
            grown = False
            for position, (address, instruction) in enumerate(self.ordered):
                if instruction.flow != "call" or instruction.target not in self.makers:
                    continue
                pushes = self.pushes(position, self.makers[instruction.target][0])
                if not pushes or any(push.mnemonic != "move" or push.operands[0].mode not in ("areg", "dreg")
                                     for push in pushes):
                    continue
                registers = {push.operands[0].reg for push in pushes}
                function = self.function_of(address)
                if len(registers) != 1 or function is None or function in self.makers:
                    continue
                register = registers.pop()
                after, arguments = self.prologue(function)
                if after is None or register not in arguments or any(writes(self.ordered[step][1], register)
                                                    for step in range(after, position)):
                    continue
                self.makers[function] = (arguments[register],
                                         f"hands its argument {arguments[register]} on at {address:06X}")
                grown = True

    def passed(self, position, argument):
        """[(address, table)] of what the call at 'position' gets as its stack argument 'argument', where the code
        says which: "pea ADDRESS.l" (table None), or each of the four entries of a table by the level
        ("movea.l #TABLE, A0" then "move.l (A0,Dn.w), -(A7)")"""
        found = []
        for push in self.pushes(position, argument) or ():
            source = push.operands[0]
            if push.mnemonic == "pea" and source.mode == "abs_long":
                found.append((source.value & 0xFFFFFF, None))
                continue
            if push.mnemonic != "move" or source.mode != "index":
                continue
            at = self.position_of[push.address]
            loader = self.ordered[at - 1][1] if at else None
            if loader is not None and loader.mnemonic == "movea" and loader.operands[0].mode == "immediate" \
                    and loader.operands[1].reg == source.reg:
                table = loader.operands[0].value & 0xFFFFFF
                found.extend((long_at(self.image, table + 4 * index), table) for index in range(LEVELS))
        return found

    def call_site(self, position, address, maker):
        """The definition a call of make_animated_object, or of a function that hands it on, gets, where the code
        says which"""
        how = f"{'passed' if maker == MAKE_ANIMATED_OBJECT else f'passed to {maker:06X}'} at {address:06X}"
        for definition, table in self.passed(position, self.makers[maker][0]):
            if table is None:
                self.definitions.setdefault(definition, how)
            else:
                index = next(index for index in range(LEVELS) if long_at(self.image, table + 4 * index) == definition)
                self.definitions.setdefault(definition, f"entry {index} of {table:06X}, {how}")
                self.level_tables[table] = f"indexed by the level, {how}"

    def tileset_load(self, position, address, loader):
        """The tiles a call of one of the loaders gets, where the code says which"""
        kind, argument = TILE_LOADERS[loader]
        how = f"passed to {loader:06X} at {address:06X}"
        for tiles, table in self.passed(position, argument):
            if table is not None:
                self.tileset_tables[table] = f"indexed by the level, {how}"
            self.add_tileset(tiles, kind, how if table is None else f"an entry of {table:06X}, {how}")

    def add_tileset(self, address, kind, found):
        """Tiles as the loader of 'kind' reads them; the walk stops where they do not read so"""
        if address in self.tilesets:
            return
        image = self.image
        if kind == "word" and struct.unpack_from(">h", image, address)[0] > 0:
            kind, size = "raw tiles", 2 + 32 * struct.unpack_from(">h", image, address)[0]
        elif kind == "ssc":
            result = compression.ssc_decode(image, address)
            if result.unwritten or len(result.data) != 32 * result.tiles:
                raise SystemExit(f"{address:06X} ({found}): no SSC tiles (it gives {len(result.data)} bytes for "
                                 f"{result.tiles} tiles, {len(result.unwritten)} reads of the window not written)")
            kind, size = "SSC tiles", result.size
        else:
            start = address + 2 if kind == "word" else address
            result = compression.c2_decode(image, start)
            if result.codes[0] != compression.C2_RESTART or result.most_entries > compression.C2_LAST_ENTRY + 1:
                raise SystemExit(f"{address:06X} ({found}): no C2 tiles")
            kind, size = ("C2 tiles after a word" if kind == "word" else "C2 tiles"), start - address + result.size
        if (address + size) & 1 and image[address + size] == TILESET_PAD:
            size += 1
        self.tilesets[address] = (kind, size, found)

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

    def object_table_load(self, instructions, position, address):
        """A table's objects where the code copies them: "movea.l #TABLE, A0; lea (A0,D0.w), A0; movea.l A0, An",
        then a loop back to the next instruction that moves An on by 20 and ends at "cmpi.w #COUNT, Dn; blt" """
        instruction = instructions[position][1]
        if instruction.mnemonic != "movea" or instruction.operands[0].mode != "immediate" \
                or position + 3 >= len(instructions):
            return
        lea, keep = instructions[position + 1][1], instructions[position + 2][1]
        if lea.mnemonic != "lea" or lea.operands[0].mode != "index" or keep.mnemonic != "movea" \
                or keep.operands[0].mode != "areg" or keep.operands[0].reg != lea.operands[1].reg:
            return
        loop, register = instructions[position + 3][0], keep.operands[1].reg
        moves_by_20 = False
        for later_position in range(position + 3, min(position + 600, len(instructions) - 1)):
            later = instructions[later_position][1]
            ops = later.operands
            if later.mnemonic == "adda" and len(ops) == 2 and ops[1].mode == "areg" and ops[1].reg == register:
                previous = instructions[later_position - 1][1]
                moves_by_20 = moves_by_20 or (previous.mnemonic == "moveq"
                                              and previous.operands[0].value == TABLE_OBJECT_SIZE)
            branch = instructions[later_position + 1][1]
            if later.mnemonic == "cmpi" and ops[0].mode == "immediate" and branch.mnemonic == "bcc" \
                    and branch.condition == "lt" and branch.target == loop:
                if moves_by_20:
                    table = instruction.operands[0].value & 0xFFFFFF
                    self.object_tables[table] = (ops[0].value, f"copied by the loop {loop:06X}-{later.address:06X}")
                    for index in range(ops[0].value):
                        definition = long_at(self.image, table + TABLE_OBJECT_SIZE * index + TABLE_OBJECT_DEFINITION)
                        if definition:
                            self.definitions.setdefault(definition, f"object {index} of the table {table:06X}")
                return

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
        for table, (objects, _) in self.object_tables.items():
            found[table] = (table + TABLE_OBJECT_SIZE * objects, "table objects")
        for address, step in self.steps.items():
            found[address] = (address + step.length, "animation step")
        for address, (_, _, size, _) in self.sprite_tables.items():
            found[address] = (address + size, "sprite table")
        for address, (kind, size, _) in self.tilesets.items():
            found[address] = (address + size, kind)
        for table in self.tileset_tables:
            found[table] = (table + 4 * LEVELS, "tilesets by level")
        if any(kind.startswith("C2") for kind, _, _ in self.tilesets.values()):
            found[compression.C2_MASKS] = (compression.C2_MASKS + C2_MASKS_SIZE, "C2 code masks")
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
    for address, (kind, size, _) in walk.tilesets.items():
        if kind.startswith("C2"):
            walked.update(range(address + size, address + size + C2_READ_PAST))
    by_reader, others = defaultdict(lambda: defaultdict(set)), defaultdict(set)
    for path in glob.glob(str(Path(folder) / "**" / "rom_reads.txt"), recursive=True):
        for line in open(path, encoding="ascii"):
            if line.startswith("#") or not line.strip():
                continue
            pc, span = line.split()
            first, last = (int(value, 16) for value in span.split("-"))
            pc = int(pc, 16)
            reader = next((name for name, (start, stop) in READERS.items() if start <= pc < stop), None)
            for address in range(first, last + 1):
                (by_reader[reader] if reader else others)[address].add(pc)
    for reader in READERS:
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
