"""
Name:        walk_animations.py
Description: Sonic the Hedgehog Spinball's animated objects, walked from where the code hands them over: the
             definitions, their sprite descriptors, the sprite tables, the animations and their lists,
             and the tables' objects (for tools/data_walk.py)
Version:     0.1.1
Created:     13-11-2026
Modified:    19-11-2026
Author:      Sebastian Toyos

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
                 tileset at 0394AA), and so is a place the code hands over (what it passes or keeps, the start
                 of a list or a table: an animation that runs on stops there; not what is only a constant of an
                 instruction, which may be a number: 000BB8, in the middle of an animation, is the 3,000 points
                 0F888A adds). A frame shows a sprite of its object's table, so a frame of a sprite the table does not
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
                 0 for none: 0E4E34 "tst.l ($18,A2)", then make_animated_object), the address of its box (field
                 1C, 0 for none: x0, y0, x1, y1 from its place, 8 bytes, 0E51EA-0E520E), and two bytes. Found where the
                 code does it: "movea.l #TABLE, A0; lea (A0,D0.w), A0; movea.l A0, An", then a loop that moves An
                 on by 20 until "cmpi.w #COUNT, Dn; blt" (Toxic Caves 0E626C, 173; Lava Powerhouse 0E4DFC, 211;
                 Showdown 0E9E7E, 186; The Machine 0F10EE, 158).
"""
import struct
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]
import spinball_animation as animation  # noqa: E402
import spinball_graphics as graphics  # noqa: E402
from walk_patterns import LEVELS, long_at, writes  # noqa: E402

MAKE_ANIMATED_OBJECT = 0x0D5F16     # takes a definition first
DEFINITION_SIZE = 12
TABLE_OBJECT_SIZE = 20              # a table's object, as the code that sets the table up copies it
TABLE_OBJECT_DEFINITION = 0x0A      # its definition's long
TABLE_OBJECT_BOX = 0x0E             # its box's long (the game object's field 1C: 0E51EA)
OBJECT_BOX_SIZE = 8                 # x0, y0, x1, y1 from the object's place (0E51F4-0E520E)
DESCRIPTOR_SIZE = 8
SPRITE_LINK_FIELD = 0x3A            # an object's link to the structure that holds its sprite table
SPRITE_TABLE_FIELD = 0x0A           # that structure's sprite table


LOADS_WALKED = 96                   # how far back from a call a register's load is looked for

class AnimationWalk:
    """The definitions, descriptors and sprite tables, animations and their lists, the tables' objects"""

    def init_animations(self):
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
        self.object_tables = {}         # {address: (objects, how it was found)}
        self.object_boxes = {}          # {address: how it was found}
        self.makers = {MAKE_ANIMATED_OBJECT: (0, "the engine")}     # {function: (its definition's argument, how)}

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
        # "move.l An, -(A7)" with An one of the addresses the function loads it with, each on its way: all of them
        # (0E58A4: A3 is 0C0CA0, 0C0C94 or 0C0C88, loaded at 0E57F2, 0E583C and 0E5878)
        for push in self.pushes(position, self.makers[maker][0]) or ():
            source = push.operands[0]
            if push.mnemonic == "move" and source.mode == "areg":
                for definition, at in self.loads_before(position, source.reg):
                    self.definitions.setdefault(definition, f"loaded at {at:06X} and {how}")

    def loads_before(self, position, register):
        """[(place, where)] of the "movea.l #PLACE, An" that reach the instruction at 'position', back along every
        way to it (through the jumps and branches that come in); none when a way loads An with anything else, or
        runs LOADS_WALKED instructions back without loading it"""
        loads, seen, work = [], set(), [(position - 1, 0)]
        while work:
            at, far = work.pop()
            if at in seen:
                continue
            seen.add(at)
            address, instruction = self.ordered[at]
            operands = instruction.operands
            if writes(instruction, register):
                place = operands[0].value & 0xFFFFFF if operands else 0
                if instruction.mnemonic != "movea" or operands[0].mode != "immediate" or place >= len(self.image):
                    return []
                loads.append((place, address))
                continue
            if far >= LOADS_WALKED or at == 0 or address in self.analysis.functions:
                return []
            if self.ordered[at - 1][1].flow not in ("jump", "return"):
                work.append((at - 1, far + 1))
            work.extend((source, far + 1) for source in self.comes_from.get(address, ()))
        return sorted(loads)

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
                        box = long_at(self.image, table + TABLE_OBJECT_SIZE * index + TABLE_OBJECT_BOX)
                        if box:
                            if box + OBJECT_BOX_SIZE > len(self.image):
                                raise SystemExit(f"object {index} of the table {table:06X}: a box at {box:06X}")
                            self.object_boxes.setdefault(box, f"object {index} of the table {table:06X}")
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
                return [(long_at(self.image, table + 4 * level), f"level {level} of {table:06X}")
                        for level in range(LEVELS)]
        return []

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
                if address in self.handed:
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

    def spans_animations(self, found):
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
        for box in self.object_boxes:
            found.setdefault(box, (box + OBJECT_BOX_SIZE, "object box"))
        for address, step in self.steps.items():
            found[address] = (address + step.length, "animation step")
        for address, (_, _, size, _) in self.sprite_tables.items():
            found[address] = (address + size, "sprite table")
