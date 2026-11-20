"""
Name:        walk_patterns.py
Description: Sonic the Hedgehog Spinball's code read for what it hands over: the patterns of its C compiler's
             calls and of the tables it reads by the level, for the walk (tools/data_walk.py)
Version:     0.2.0
Created:     13-11-2026
Modified:    19-11-2026
Author:      Sebastian Toyos

The game's C passes arguments on the stack, pushed last to first, and keeps D2-D7/A2-A6 across a call. So
what a call gets is found back from it a push at a time (pushes(): through the jumps and branches that come in
among the pushes; passed(): "pea ADDRESS.l", or the entries of a table by the level), and what a function does
with its arguments from its prologue ("movem.l REGISTERS, -(A7)" then "move(a).l (d,A7), Rn": prologue()).

How long a table is, the code that reads it says with the bound of its index; here, two of them:
  values         a table the code reads by the level: "move.w FF75B0.l, Dn", "add.w Dn, Dn" or "lsl.w #2, Dn"
                 or nothing, "movea.l #TABLE, An", and "(An,Dn.w)" read right after (or where a "bra" goes):
                 four entries as far apart as the scale says, each as big as the read (the collision's what
                 touching does at C06BA-C0705, the tables' sizes, and others).
  masked         a table the code reads by an index it masks: "andi.w #M, Dn", "add.w Dn, Dn" or "lsl.w #k, Dn"
                 to the size of an entry (or nothing), "lea TABLE, An" (PC-relative or absolute) or "movea.l
                 #TABLE, An", and "(An,Dn.w)" right after, the index maybe through copies ("move.w Dm, Dn"): M + 1
                 entries (0F40BE's and 0F41FE's shifts of a sprite by its size at 0F41BE, the maps' loaders' rows by
                 the plane size at 0F3DEE, the four random choices of 0EE45A at 0C59E8-0C5A0B). The same with the
                 table read from the code's own place, "move (d,PC,Dn.w)" (the pads' bits at 0D3DF4 and 0D3DF8,
                 8 longs at 0F3822, 16 words at 0F4350).
  counted        a table a "dbra" loop reads from its start: "lea TABLE, An" (PC-relative or absolute) or "movea.l
                 #TABLE, An", "moveq #N, Dk" within the next three, then a loop that reads "(An)+" and ends "dbra Dk"
                 back to its start: N + 1 entries of what it reads each time round (0F3842's 20 registers of the
                 VDP at 0F38B4). A loop that can end sooner counts the same ("cmp.b (A0)+, D0; dbls D1": the 10
                 kinds 0E6382 looks an object's up in, 0E63A8).
  interpolated   the sine (0D6918) and the arctangent (0D6ADA) read a word of a table and the word after it,
                 between which they interpolate: "adda.w Dn, An; move.w (An)+, Dx; move.w (An), Dy" after "movea.l
                 #TABLE, An". The sine's index is its angle folded into a quarter (0-4000) over 64: 0-256, 257 words
                 (0C02B6: 0 to 4000, 1.0; at 90 degrees the word after the last is read too, and multiplied by 0);
                 the arctangent's, the ratio of its arguments below 8000 over 128: 0-255 and the word after, 257
                 (0C04B8: 0 to 2000, 45 degrees).
  pointed        a record the code reads through a pointer it loads: "movea.l #RECORD, An", then "(An)" and
                 "(d,An)" read (not "lea" or "pea") on every way from it, until An changes, a call that does not
                 keep it, a return, or the next function: as far as the furthest of those reads (the shapes object
                 types 17-19 hand to the collision's tests at 0C5ADC-0C5B45, a word of x, of y, two more and the
                 kind at +8). The weakest description: where another subject describes the place, it wins.
  in place       a value the code reads by its address in the cartridge, "move.l $FFAB4.l, (-$4,A6)" (0F255A),
                 "move.w $A8816.l, -(A7)" (0F5CAC): as many bytes as the instruction reads (not "lea", "pea" or
                 a jump, which take the address). The weakest of all: any other description wins.
  zeros          up to ZEROS_MOST bytes of 0 right after something the walk describes and before the next thing
                 (another description, a place the code names, code): what evens a record or fills it out, which
                 no code reads (the long after each 8-byte box, the bytes before a place at an even address, an
                 entry of 6 in a sprite group of none at 09943A).
  parallel       tables a function reads side by side by the same field ("move.w (d,Ar), Dn; add.w Dn, Dn; movea.l
                 #TABLE, A0; move.w (A0,Dn.w)"), one after the other at the same distance: each that long (the four
                 colours of a message by its style, 0C13F0-0C142F, 8 styles); the last, up to the next place the
                 code names, where that is within the distance.
  scaled         a table the code reads by an index it scales and the function does not bound: before "movea.l
                 #TABLE, An", in a straight line (from the last place a jump comes in), the index is loaded, then
                 copied, shifted, added to itself or to another and multiplied ("move.b ($a,A2), D0; ext.w D0;
                 move.w D0, D1; lsl.w #2, D0; add.w D1, D0; add.w D0, D0": times 10, 0DA838-0DA844), and "(An,Dn.w)"
                 is read or taken ("lea") right after, or where a "bra" goes. The scale is the size of an entry
                 (the smallest, where the index is a sum: a block's size and an entry's), and the table goes on in
                 whole entries up to the next thing: a place the code names, what another subject describes, or
                 code. The index may come scaled from further back, or be what a call gave ("jsr (A3); addq.l
                 #8, A7; lsl.w #2, D0": the 3 longs at 0A881E, 0F5CD8-0F5CE4). An index the lines before do not
                 touch is a byte's ("move.b (A0,D2.w), D0" with D2 a loop's count: 0C02A6 and 0C02AC, 0D9C5C-0D9C74).
                 Where the index is a loop's counter, cleared before it and "addq.w #1; cmpi.w #N; blt" after the
                 read, the table is N entries (0C02A6 and 0C02AC, 5 bytes each, 0D9C92), and a byte at an odd place
                 between it and the next thing is the byte that evens it. It is not taken where that leaves a part
                 of an entry, where a read is longer than an entry,
                 or where it would be longer than SCALED_MOST. The index's values are whatever the code that sets
                 it gives (0BFDC4 and 0BFFFE, 57 entries of 10 bytes by an object's byte at +0A; the two tables
                 after them, 5). Where the code reads a word of entries of 4 bytes and the table is whole only
                 from 2 bytes before, it names the low word of its longs ("move.w (A0,D0.w), D1" with A0 the
                 table plus 2: 0D210E for the 7 longs at 0D210C, 09BC3C for the 3 at 09BC3A), and the table
                 before it ends there. Weaker than a bound: another subject's description wins, and it wins
                 over a record read through a pointer.
  searched       a table of longs a binary search reads, "lsl.w #2, D0; movea.l #TABLE, A0; move.l (A0,D0.w), D0"
                 with D0 the middle of two ends it starts at 0 and at N: N + 1 longs, which must end at a place
                 the code names (SEARCHED: 0F7D8E's, between 0 and 5Ah, 0F7D96-0F7D98; the one at 0FC990, between
                 0 and 96h, 0FC96C-0FC972).
"""
import bisect
import struct
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]

SCRATCH = {"D0", "D1", "A0", "A1"}  # the registers a call of the game's C does not keep
PUSHES_WALKED = 4096                # how far back from a call its pushes are looked for (many ways can share it)
LOOP_WALKED = 64                    # how far after its setup a loop's end is looked for
MASK_WALKED = 24                    # how far back from a read its index's mask is looked for
CALL_TARGET_WALKED = 4096           # how far back from a call through a register its loader is looked for
LEVELS = 4                          # the tables the game has: what a table indexed by the level holds
LEVEL_VARIABLE = 0xFF75B0           # the level: 0-3 the tables, 4 the options screen (0FEDA4)
INTERPOLATED = {0x0D6918: 257, 0x0D6ADA: 257}  # the sine and the arctangent: the words of their tables
SIZES = {"b": 1, "w": 2, "l": 4}
SCALE_WALKED = 14                   # how far back from a table's load its index's scale is looked for
SCALED_MOST = 0x400                 # the longest table taken by the scale of its index alone, in bytes
ZEROS_MOST = 6                      # the longest run of zeros taken as what fills out a record
SEARCHED = {0x0D338E: 0x0F7D96, 0x0D1E94: 0x0FC96C}    # a searched table: where the search's far end is loaded


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



class CodePatterns:
    """The code in address order, and what its patterns say"""

    def init_patterns(self):
        self.ordered = []               # [(address, Instruction)] of the analysis, in address order
        self.position_of = {}           # {address: its position in ordered}
        self.comes_from = {}            # {address: positions of the jumps and branches that go there}
        self.value_tables_by_level = {}     # {address: (stride, size of an entry, how it was found)}
        self.copied_blocks = {}         # {address: (size, how it was found)}
        self.loop_tables = {}           # {address: (entries, stride, how it was found)}
        self.bounded_tables = {}        # {address: (entries, stride, kind, how)}: as many as a mask or a count says
        self.pointed_records = {}       # {address: (size, how it was found)}: read through a pointer at offsets
        self.scaled_tables = {}         # {address: (size of an entry, bytes read, how)}: by an index the code scales
        self.scaled_bounds = {}         # {table: entries}: by the count of the loop whose counter indexes it
        self.values_in_place = {}       # {address: bytes read}: what the code reads by its address
        self.handed = set()             # the places the code hands over or keeps in a table (the anchors but
                                        # the constants of instructions)

    def index_code(self):
        self.ordered = sorted(self.analysis.instructions.items())
        for position, (address, instruction) in enumerate(self.ordered):
            self.position_of[address] = position
            if instruction.flow in ("jump", "branch") and instruction.target is not None:
                self.comes_from.setdefault(instruction.target, []).append(position)
        # a switch's cases come from its jump: the instruction that ends where its table starts
        ends = {address + instruction.length: position for position, (address, instruction) in enumerate(self.ordered)}
        for table, cases in getattr(self.analysis, "switch_tables", {}).items():
            if table in ends:
                for case in cases:
                    self.comes_from.setdefault(case, []).append(ends[table])

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
        the other; or, with a frame ("link A6, #n", then maybe the movem), "move(a).l (d,A6), Rn"; the
        arguments start at (8,A6)"""
        position = self.position_of.get(function)
        if position is None:
            return None, {}
        first = self.ordered[position][1]
        frame = first.mnemonic == "link" and first.operands[0].reg == "A6"
        if frame:
            position += 1
            first = self.ordered[position][1]
        saved = 0
        if first.mnemonic == "movem" and first.operands[1].mode == "predec" and first.operands[1].reg == "A7":
            saved, position = len(first.operands[0].registers), position + 1
        elif pushes_long(first) and first.mnemonic == "move" and first.operands[0].mode in ("areg", "dreg"):
            saved, position = 1, position + 1
        base, start = ("A6", 8) if frame else ("A7", 4 * saved + 4)
        arguments = {}
        while position < len(self.ordered):
            instruction = self.ordered[position][1]
            operands = instruction.operands
            if instruction.mnemonic not in ("move", "movea") or instruction.size != "l" or len(operands) != 2 \
                    or operands[0].mode != "disp" or operands[0].reg != base \
                    or operands[1].mode not in ("areg", "dreg"):
                break
            arguments[operands[1].reg] = (operands[0].disp - start) // 4
            position += 1
        return position, arguments

    def call_target(self, position):
        """Where the call at 'position' goes: its target, or for "jsr (An)" the function the code put in An on
        every way back to it ("movea.l #FUNCTION, An" or "lea FUNCTION, An", nothing writing An after it):
        back from the call through the jumps and branches that come in; None if the ways disagree"""
        instruction = self.ordered[position][1]
        if instruction.flow != "call":
            return None
        if instruction.target is not None:
            return instruction.target
        operand = instruction.operands[0] if instruction.operands else None
        if operand is None or operand.mode != "indirect":
            return None
        register, found, seen, work = operand.reg, set(), {position}, [position]
        while work:
            at = work.pop()
            for step in self.before(at):
                if step in seen:
                    continue
                seen.add(step)
                if len(seen) > CALL_TARGET_WALKED:
                    return None
                loader = self.ordered[step][1]
                operands = loader.operands
                if len(operands) == 2 and operands[1].mode == "areg" and operands[1].reg == register and (
                        (loader.mnemonic == "movea" and operands[0].mode == "immediate")
                        or (loader.mnemonic == "lea" and operands[0].mode == "abs_long")):
                    found.add(operands[0].value & 0xFFFFFF)
                elif writes(loader, register) or self.ordered[step][0] in self.analysis.functions:
                    return None
                else:
                    work.append(step)
        if len(found) == 1 and next(iter(found)) in self.analysis.instructions:
            return found.pop()
        return None

    def before(self, at):
        """The positions the instruction at 'at' can come from: the one before it if it falls through, and the
        jumps and branches that go to it"""
        here = self.ordered[at][0]
        found = list(self.comes_from.get(here, ()))
        if at:
            previous_address, previous = self.ordered[at - 1]
            if previous_address + previous.length == here and previous.flow not in ("jump", "return"):
                found.append(at - 1)
        return found

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
                if table + 4 * LEVELS <= len(self.image):
                    found.extend((long_at(self.image, table + 4 * index), table) for index in range(LEVELS))
        return found

    def levels_set_before(self, function, depth=3):
        """The levels the code sets ("move.w #N, FF75B0.l") before it calls 'function': in each caller, the last
        one before the call, or else in the callers' callers"""
        found = set()
        for position, (address, instruction) in enumerate(self.ordered):
            if instruction.flow != "call" or instruction.target != function:
                continue
            caller = self.function_of(address)
            start = self.position_of.get(caller, position)
            settings = [step.operands[0].value for _, step in self.ordered[start:position]
                        if step.mnemonic == "move" and step.size == "w" and len(step.operands) == 2
                        and step.operands[0].mode == "immediate" and step.operands[1].mode == "abs_long"
                        and step.operands[1].value & 0xFFFFFF == LEVEL_VARIABLE]
            if settings:
                found.add(settings[-1])
            elif depth:
                found |= self.levels_set_before(caller, depth - 1)
        return found

    def next_handed(self, address):
        """The next place after 'address' the code hands over or keeps in a table (not every constant that
        could be an address: an instruction's 40000 is no place)"""
        return min((place for place in self.handed if place > address), default=len(self.image))

    def level_value_load(self, position, address, instruction):
        """A table of values by the level: the level in Dn ("move.w FF75B0.l, Dn", or "move.w (Am), Dn" with Am
        holding FF75B0: holds_level()), then "add.w Dn, Dn" (an entry every 2 bytes), "lsl.w #2, Dn" (every 4) or
        nothing (every byte), "movea.l #TABLE, An", and the read of "(An,Dn.w)" right after it or where the "bra"
        after it goes: its size is the entry's ("lea (An,Dn.w)" takes the whole entry)"""
        operands = instruction.operands
        if instruction.mnemonic != "movea" or operands[0].mode != "immediate" or position < 2:
            return
        register, stride, at = operands[1].reg, 1, position - 1
        scale = self.ordered[at][1]
        if scale.mnemonic == "add" and len(scale.operands) == 2 and scale.operands[0].mode == "dreg" \
                and scale.operands[0].reg == scale.operands[1].reg:
            stride, at = 2, at - 1
        elif scale.mnemonic == "lsl" and scale.operands[0].mode in ("quick", "immediate") \
                and scale.operands[0].value == 2:
            stride, at = 4, at - 1
        load = self.ordered[at][1]
        if load.mnemonic != "move" or load.size != "w" or len(load.operands) != 2 or load.operands[1].mode != "dreg":
            return
        source = load.operands[0]
        if not (source.mode == "abs_long" and source.value & 0xFFFFFF == LEVEL_VARIABLE) \
                and not (source.mode == "indirect" and self.holds_level(at, source.reg)):
            return
        index = load.operands[1].reg
        if stride > 1 and scale.operands[-1].reg != index:
            return
        reader = self.ordered[position + 1][1]
        if reader.mnemonic == "bra":
            reader = self.analysis.instructions.get(reader.target)
        if reader is None:
            return
        for operand in reader.operands:
            if operand.mode == "index" and operand.reg == register and operand.index == index:
                size = stride if reader.mnemonic == "lea" else {"b": 1, "w": 2, "l": 4}[reader.size]
                if size <= stride:
                    table = operands[0].value & 0xFFFFFF
                    self.value_tables_by_level.setdefault(table, (stride, size, f"read at {reader.address:06X}"))
                return

    def holds_level(self, position, register):
        """Whether 'register' holds FF75B0's address at 'position': "movea.l #FF75B0, An" earlier in the function,
        and nothing writing it since"""
        first = self.position_of.get(self.function_of(self.ordered[position][0]), position)
        for at in range(position - 1, first - 1, -1):
            instruction = self.ordered[at][1]
            operands = instruction.operands
            if instruction.mnemonic == "movea" and operands[0].mode == "immediate" and operands[1].reg == register:
                return operands[0].value & 0xFFFFFF == LEVEL_VARIABLE
            if writes(instruction, register):
                return False
        return False

    def block_copy(self, position, address, instruction):
        """A block the code copies as a whole (C's initialised local array or structure): "movea.l #BLOCK, An"
        (or "lea BLOCK, An"), the destination into Am, then "move.l (An)+, (Am)+" (or .w, .b) one after the other:
        as many bytes as they move"""
        operands = instruction.operands
        if len(operands) != 2 or operands[1].mode != "areg" or not (
                (instruction.mnemonic == "movea" and operands[0].mode == "immediate")
                or (instruction.mnemonic == "lea" and operands[0].mode == "abs_long")):
            return
        source = operands[1].reg
        at = position + 1
        if at < len(self.ordered) and self.ordered[at][1].mnemonic in ("lea", "movea") \
                and self.ordered[at][1].operands[1].reg != source:
            at += 1
        size = 0
        while at < len(self.ordered):
            move = self.ordered[at][1]
            moved = move.operands
            if move.mnemonic != "move" or len(moved) != 2 or moved[0].mode != "postinc" or moved[0].reg != source \
                    or moved[1].mode != "postinc":
                break
            size += {"b": 1, "w": 2, "l": 4}[move.size]
            at += 1
        if size > 1:
            block = operands[0].value & 0xFFFFFF
            if block + size <= len(self.image):
                self.copied_blocks.setdefault(block, (size, f"copied at {address:06X}"))

    def pointer_loop(self, position, address, instruction):
        """A table a loop walks from its start with a pointer: a counter cleared ("clr.w Dk" or "moveq #0, Dk")
        just before, "movea.l #TABLE, An; lea (An,Dx.w), Ap" (maybe "movea.l Ap, Aq" after), or the table straight
        into the pointer with the counter cleared right after ("movea.l #TABLE, Ap; clr.w Dk"), then a loop that
        moves the pointer on by what it reads with "(Ap)+" or adds to it ("addq", "adda"), and ends "addq.w #1,
        Dk; cmpi.w #N, Dk; blt" back, the index from that counter: N entries of that stride (a table of the
        cartridge), up to the next place the code names (a loop can move on past what it reads: 0FEEA4's six
        steps read the first three)"""
        operands = instruction.operands
        if instruction.mnemonic != "movea" or len(operands) != 2 or operands[0].mode != "immediate" \
                or position + 3 >= len(self.ordered) or operands[0].value & 0xFFFFFF >= len(self.image):
            return
        lea = self.ordered[position + 1][1]
        direct = lea.mnemonic != "lea"
        if direct:
            # the table straight into the pointer, the counter cleared right after: "movea.l #TABLE, Ap; clr.w Dk"
            pointer, at = operands[1].reg, position + 1
            clear = self.ordered[at][1]
            if clear.mnemonic not in ("clr", "moveq") or clear.operands[-1].mode != "dreg":
                return
            at += 1
        elif lea.operands[0].mode != "index" or lea.operands[0].reg != operands[1].reg:
            return
        else:
            pointer, at = lea.operands[1].reg, position + 2
            keep = self.ordered[at][1]
            if keep.mnemonic == "movea" and keep.operands[0].mode == "areg" and keep.operands[0].reg == pointer:
                pointer, at = keep.operands[1].reg, at + 1
        for end in range(at, min(at + LOOP_WALKED, len(self.ordered) - 2)):
            compare, branch = self.ordered[end][1], self.ordered[end + 1][1]
            if compare.mnemonic != "cmpi" or compare.size != "w" or compare.operands[1].mode != "dreg" \
                    or branch.mnemonic != "bcc" or branch.condition != "lt" or branch.target is None \
                    or not self.ordered[at][0] <= branch.target <= compare.address:
                continue
            counter = compare.operands[1].reg
            if direct:
                if self.ordered[position + 1][1].operands[-1].reg != counter:
                    return
            elif not self.cleared_before(position, counter) or (lea.operands[0].index != counter and not any(
                    step.mnemonic == "move" and step.operands[0].mode == "dreg" and step.operands[0].reg == counter
                    and step.operands[1].reg == lea.operands[0].index
                    for step in (self.ordered[back][1] for back in range(max(position - 8, 0), position)))):
                return
            first = self.position_of[branch.target]
            stride = 0
            for step in (self.ordered[index][1] for index in range(first, end)):
                moved = step.operands
                if moved and moved[0].mode == "postinc" and moved[0].reg == pointer:
                    stride += {"b": 1, "w": 2, "l": 4}.get(step.size, 0)
                if step.mnemonic in ("addq", "adda") and len(moved) == 2 and moved[1].mode == "areg" \
                        and moved[1].reg == pointer and moved[0].mode in ("quick", "immediate"):
                    stride += moved[0].value
            if stride:
                table = operands[0].value & 0xFFFFFF
                self.loop_tables.setdefault(table, (compare.operands[0].value, stride,
                                                    f"walked by the loop {branch.target:06X}-{compare.address:06X}"))
            return

    def cleared_before(self, position, register):
        """Whether 'register' is cleared ("clr.w" or "moveq #0") a few instructions before 'position', and nothing
        else writes it since"""
        for at in range(position - 1, max(position - 9, -1), -1):
            step = self.ordered[at][1]
            moved = step.operands
            if (step.mnemonic == "clr" and moved[0].mode == "dreg" and moved[0].reg == register) \
                    or (step.mnemonic == "moveq" and moved[0].value == 0 and moved[1].reg == register):
                return True
            if writes(step, register):
                return False
        return False

    def masked_index(self, position, address, instruction):
        """A table read by an index the code masks: "andi.w #M, Dn", then "add.w Dn, Dn" or "lsl.w #k, Dn" (or
        nothing), "lea TABLE, An" or "movea.l #TABLE, An" right before "move (An,Dn.w)": M + 1 entries as far apart
        as the scale says. Back from the read the index can pass through copies ("move.w Dm, Dn") and other
        instructions that leave it; the way back stops where a jump or a branch comes in"""
        operands = instruction.operands
        if instruction.mnemonic not in ("move", "movea") or not operands or operands[0].index_size != "w" \
                or position < 2:
            return
        if operands[0].mode == "pc_index":      # read from the code's own place
            index, table, last = operands[0].index, (operands[0].base + operands[0].disp) & 0xFFFFFF, position - 1
        elif operands[0].mode == "index" and not operands[0].disp:
            base, index, last = operands[0].reg, operands[0].index, position - 2
            load = self.ordered[position - 1][1]
            if len(load.operands) != 2 or load.operands[1].reg != base or not (
                    (load.mnemonic == "lea" and load.operands[0].mode in ("pc_disp", "abs_long"))
                    or (load.mnemonic == "movea" and load.operands[0].mode == "immediate")):
                return
            table = load.operands[0].value & 0xFFFFFF
        else:
            return
        stride = 1
        if table >= len(self.image):
            return
        for back in range(last, max(position - MASK_WALKED, -1), -1):
            if self.ordered[back + 1][0] in self.comes_from:
                return
            step = self.ordered[back][1]
            step_operands = step.operands
            scaled = len(step_operands) == 2 and step_operands[-1].mode == "dreg" and step_operands[-1].reg == index
            if scaled and step.mnemonic == "add" and step.size == "w" and step_operands[0].mode == "dreg" \
                    and step_operands[0].reg == index:
                stride *= 2
            elif scaled and step.mnemonic == "lsl" and step.size == "w" and step_operands[0].mode == "quick":
                stride <<= step_operands[0].value
            elif scaled and step.mnemonic == "move" and step.size == "w" and step_operands[0].mode == "dreg":
                index = step_operands[0].reg
            elif scaled and step.mnemonic == "andi" and step.size == "w" and step_operands[0].mode == "immediate":
                self.bounded_tables.setdefault(table, (step_operands[0].value + 1, stride, "table by a masked index",
                                                       f"read by the index {step.address:06X} masks"))
                return
            elif writes(step, index) or step.flow != "normal":
                return

    def pointed_record(self, position, address, instruction):
        """A record read through a pointer: "movea.l #RECORD, An", then "(An)"/"(d,An)" reads while An holds it"""
        operands = instruction.operands
        if instruction.mnemonic != "movea" or len(operands) != 2 or operands[0].mode != "immediate":
            return
        record, pointer, size = operands[0].value & 0xFFFFFF, operands[1].reg, 0
        if record >= len(self.image):
            return
        work, seen = [position + 1], set()
        while work and len(seen) < 4 * LOOP_WALKED:
            at = work.pop()
            if at in seen or at >= len(self.ordered) or self.ordered[at][0] in self.analysis.functions:
                continue
            seen.add(at)
            step = self.ordered[at][1]
            if step.mnemonic not in ("lea", "pea"):
                for operand in step.operands:
                    if operand.mode in ("indirect", "disp") and operand.reg == pointer and step.size in SIZES:
                        size = max(size, (operand.disp if operand.mode == "disp" else 0) + SIZES[step.size])
            if writes(step, pointer) or step.flow == "return" or (step.flow == "call" and pointer in SCRATCH):
                continue
            if step.flow in ("jump", "branch") and step.target in self.position_of:
                work.append(self.position_of[step.target])  # where it goes on: 0F1F6E's loop back to 0F1EDE
            if step.flow != "jump":
                work.append(at + 1)
        if size and record + size <= len(self.image):
            known = self.pointed_records.get(record)
            if known is None or known[0] < size:
                self.pointed_records[record] = (size, f"read through {pointer} from {address:06X}")

    def parallel_tables(self):
        """Tables a function reads side by side by the same field: "move.w (d,Ar), Dn; add.w Dn, Dn; movea.l
        #TABLE, A0; move.w (A0,Dn.w)", the same (d,Ar) for each; one after the other at the same distance, each
        is as long as that distance (the four colours of a message by its style at 0C13F0-0C142F: 0DEB2A)"""
        tables = {}
        for position in range(len(self.ordered) - 3):
            load, scale, base, read = (self.ordered[position + k][1] for k in range(4))
            if load.mnemonic != "move" or load.size != "w" or load.operands[0].mode != "disp" \
                    or load.operands[1].mode != "dreg" or scale.mnemonic != "add" or scale.size != "w" \
                    or base.mnemonic != "movea" or base.operands[0].mode != "immediate" or read.mnemonic != "move" \
                    or read.operands[0].mode != "index" or read.operands[0].reg != base.operands[1].reg \
                    or read.operands[0].index != load.operands[1].reg or read.size not in SIZES:
                continue
            key = (self.function_of(self.ordered[position][0]), load.operands[0].disp, load.operands[0].reg)
            tables.setdefault(key, set()).add((base.operands[0].value & 0xFFFFFF, SIZES[read.size]))
        for (function, _, _), found in tables.items():
            addresses = sorted(table for table, _ in found)
            gaps = {second - first for first, second in zip(addresses, addresses[1:])}
            sizes = {size for _, size in found}
            if len(addresses) < 2 or len(gaps) != 1 or len(sizes) != 1 or addresses[-1] >= len(self.image):
                continue
            gap, size = gaps.pop(), sizes.pop()
            last = addresses[-1]
            stop = min((place for place in self.anchors if place > last), default=len(self.image))
            for table in addresses:
                # the last has no next to bound it: up to the next place the code names, if within the distance
                # (0F6DBE's second table at 0D32B2 is shorter than its distance from the first)
                entries = gap // size if table != last else (stop - last) // size if stop - last <= gap else 0
                if entries:
                    self.bounded_tables.setdefault(table, (entries, size, "parallel table",
                                                           f"read side by side by {function:06X}"))

    def interpolated_tables(self):
        """The sine's and the arctangent's tables: the last "movea.l #TABLE, An" before "adda.w Dn, An; move.w
        (An)+, Dx; move.w (An), Dy" in the function, as many words as INTERPOLATED says"""
        for function, entries in INTERPOLATED.items():
            first = self.position_of.get(function)
            if first is None:
                raise SystemExit(f"{function:06X}: the interpolating function is not in the analysis")
            table = None
            for at in range(first, min(first + LOOP_WALKED, len(self.ordered) - 2)):
                if at > first and self.ordered[at][0] in self.analysis.functions:
                    break
                step, after, last = (self.ordered[at + k][1] for k in range(3))
                if step.mnemonic == "movea" and step.operands[0].mode == "immediate":
                    table = (step.operands[0].value & 0xFFFFFF, step.operands[1].reg)
                if step.mnemonic == "adda" and table and step.operands[1].reg == table[1] \
                        and after.mnemonic == "move" and after.operands[0].mode == "postinc" \
                        and after.operands[0].reg == table[1] and last.mnemonic == "move" \
                        and last.operands[0].mode == "indirect" and last.operands[0].reg == table[1]:
                    self.bounded_tables.setdefault(table[0], (entries, 2, "interpolated table",
                                                              f"read by {function:06X} at {after.address:06X}"))
                    break
            else:
                raise SystemExit(f"{function:06X}: no interpolated table")

    def searched_tables(self):
        """The tables a binary search reads (SEARCHED): as many longs as the far end it starts at, and one"""
        for table, at in SEARCHED.items():
            far = self.analysis.instructions.get(at)
            loads = [address for address, instruction in self.ordered
                     if instruction.mnemonic == "movea" and instruction.operands[0].mode == "immediate"
                     and instruction.operands[0].value & 0xFFFFFF == table]
            if far is None or far.mnemonic not in ("moveq", "move") or far.operands[0].mode not in (
                    "immediate", "quick") or not loads or self.function_of(loads[0]) != self.function_of(at):
                raise SystemExit(f"{table:06X}: no searched table (its search's far end at {at:06X})")
            entries = far.operands[0].value + 1
            if table + 4 * entries not in self.anchors:
                raise SystemExit(f"{table:06X}: a searched table of {entries} longs that ends where nothing starts")
            self.bounded_tables.setdefault(table, (entries, 4, "searched table",
                                                   f"searched by {loads[0]:06X} up to the {far.operands[0].value} "
                                                   f"of {at:06X}"))

    def counted_loop(self, position, address, instruction):
        """A table a "dbra" loop reads from its start: "lea TABLE, An" or "movea.l #TABLE, An", "moveq #N, Dk"
        within the next three, then the loop reading "(An)+", "dbra Dk" back: N + 1 entries of what a round reads
        (not a loop with a loop inside, which reads more each round: the boot's at 000368)"""
        operands = instruction.operands
        if len(operands) != 2 or operands[1].mode != "areg" or not (
                (instruction.mnemonic == "movea" and operands[0].mode == "immediate")
                or (instruction.mnemonic == "lea" and operands[0].mode in ("abs_long", "pc_disp"))):
            return
        table, pointer, count = operands[0].value & 0xFFFFFF, operands[1].reg, None
        if table >= len(self.image):
            return
        for at in range(position + 1, min(position + 4, len(self.ordered))):
            step = self.ordered[at][1]
            if step.mnemonic == "moveq" and step.operands[1].mode == "dreg":
                count, counter, start = step.operands[0].value, step.operands[1].reg, at + 1
                break
            if writes(step, pointer) or step.flow != "normal":
                return
        if count is None or count < 0:
            return
        for end in range(start, min(start + LOOP_WALKED, len(self.ordered))):
            step = self.ordered[end][1]
            if step.mnemonic == "dbcc" and step.operands[0].reg == counter:
                if step.target is None or not self.ordered[start][0] <= step.target < step.address:
                    return
                stride = 0
                for _, body in self.ordered[self.position_of[step.target]:end]:
                    reads = [operand for operand in body.operands
                             if operand.mode == "postinc" and operand.reg == pointer]
                    inner = body.flow == "branch" and body.target is not None and body.target <= body.address
                    written = any(operand.mode == "postinc" and operand.reg == pointer
                                  for operand in body.operands[1:])
                    if body.flow == "call" or inner or (writes(body, pointer) and not reads) or written:
                        return
                    stride += SIZES.get(body.size, 0) * len(reads)
                if stride:
                    self.bounded_tables.setdefault(table, (count + 1, stride, "table of a counted loop",
                                                           f"read by the loop {step.address:06X} ends"))
                return
            if step.flow not in ("normal", "branch"):
                return

    def sequence_counter(self, position, address, instruction):
        """A sequence read by a counter the code steps on to N: "move.b COUNTER, Dn; ext.w Dn; add.w Dn, Dn;
        movea.l #TABLE, An; move.w (An,Dn.w)", and in the function "addq.b #1, COUNTER; cmpi.b #N, COUNTER"
        (COUNTER an absolute byte or (Am)): N words. A counter that stays at N once it gets there indexes on past
        them: the options' level select (FF5750, 0FF034-0FF078) keeps its 15 until a press that is not the word it
        indexes clears it, so the next press reads a 16th word, the options' sequence's first (0FF044 reads 0D3D28
        in `options`), and while the presses go on matching it, the words after"""
        operands = instruction.operands
        if instruction.mnemonic != "movea" or len(operands) != 2 or operands[0].mode != "immediate" or position < 3 \
                or operands[0].value & 0xFFFFFF >= len(self.image):
            return
        load, extend, scale = (self.ordered[position - back][1] for back in (3, 2, 1))
        if load.mnemonic != "move" or load.size != "b" or extend.mnemonic != "ext" or scale.mnemonic != "add" \
                or load.operands[0].mode not in ("abs_long", "indirect"):
            return
        counter = load.operands[0]

        def same(operand):
            return operand.mode == counter.mode and operand.reg == counter.reg and operand.value == counter.value

        function = self.function_of(address)
        first = self.position_of.get(function, position)
        for at in range(first, len(self.ordered) - 1):
            if at > position + LOOP_WALKED * 4 or (at > first and self.ordered[at][0] in self.analysis.functions):
                break
            step, compare = self.ordered[at][1], self.ordered[at + 1][1]
            if step.mnemonic == "addq" and step.size == "b" and step.operands[0].value == 1 and same(step.operands[1]) \
                    and compare.mnemonic == "cmpi" and compare.size == "b" and same(compare.operands[1]):
                table = operands[0].value & 0xFFFFFF
                self.loop_tables.setdefault(table, (compare.operands[0].value, 2,
                                                    f"read by the counter that {compare.address:06X} ends"))
                return

    def index_scale(self, position, register):
        """What the instructions before 'position', in a straight line, multiply the index in 'register' by: the
        smallest factor of the values they load, when the others are its multiples; or None"""
        first = position
        while first > 0 and position - first < SCALE_WALKED and self.ordered[first - 1][1].flow == "normal" \
                and self.ordered[first][0] not in self.comes_from:
            first -= 1
        factors = {}                    # {register: {the address that loaded a value: what it is multiplied by}}
        for address, instruction in self.ordered[first:position]:
            operands, mnemonic = instruction.operands, instruction.mnemonic
            if not operands or operands[-1].mode != "dreg" or mnemonic in ("ext", "tst", "andi", "cmp", "cmpi",
                                                                           "addq", "subq", "addi", "subi"):
                continue
            target, source = operands[-1].reg, operands[0]
            amount = source.value if source.mode in ("immediate", "quick") else None
            if mnemonic in ("clr", "moveq"):
                factors[target] = {}
            elif mnemonic == "move" and source.mode == "dreg":
                other = factors.setdefault(source.reg, {source.reg: 1})    # a register as it comes: a value
                factors[target] = dict(other) if other is not None else None
            elif mnemonic == "move":
                factors[target] = {} if amount is not None else {address: 1}
            elif mnemonic in ("lsl", "asl", "mulu", "muls") and amount is not None:
                by = 1 << amount if mnemonic in ("lsl", "asl") else amount
                held = factors.setdefault(target, {target: 1})
                factors[target] = None if held is None else {value: factor * by for value, factor in held.items()}
            elif mnemonic in ("add", "sub") and source.mode == "dreg":
                held = factors.setdefault(target, {target: 1})
                other = factors.setdefault(source.reg, {source.reg: 1})
                if held is None or other is None:
                    factors[target] = None
                else:
                    total = dict(held)
                    for value, factor in other.items():
                        total[value] = total.get(value, 0) + (factor if mnemonic == "add" else -factor)
                    factors[target] = {value: factor for value, factor in total.items() if factor}
            else:
                factors[target] = None
        if register not in factors:
            return 1                    # the index as it comes: a byte a value
        held = factors[register]
        if not held or min(held.values()) <= 0 or any(factor % min(held.values()) for factor in held.values()):
            return None
        return min(held.values())

    def scaled_index(self, position, address, instruction):
        """A table read by an index the code scales: "movea.l #TABLE, An" after the index's scale, "(An,Dn.w)"
        read or taken right after (or where a "bra" goes)"""
        operands = instruction.operands
        if instruction.mnemonic != "movea" or operands[0].mode != "immediate":
            return
        table, pointer = operands[0].value & 0xFFFFFF, operands[1].reg
        if table >= len(self.image) or table in self.analysis.instructions:
            return
        at = position + 1
        for _ in range(4):
            if at >= len(self.ordered):
                return
            step = self.ordered[at][1]
            if step.mnemonic == "bra" and step.target in self.position_of:
                at = self.position_of[step.target]
                continue
            uses = [operand for operand in step.operands if operand.mode == "index" and operand.reg == pointer]
            if uses:
                scale = self.index_scale(position, uses[0].index)
                if scale is None or (step.mnemonic != "lea" and SIZES.get(step.size, 0) > scale)                         or (scale == 1 and step.mnemonic == "lea"):
                    return
                known = self.scaled_tables.get(table)
                if known is None or scale > known[0]:
                    read = scale if step.mnemonic == "lea" else SIZES.get(step.size, scale)
                    self.scaled_tables[table] = (scale, read, f"its index times {scale} at {address:06X}, read at "
                                                              f"{step.address:06X}")
                bound = self.loop_bound(at, uses[0].index)
                if bound is not None:
                    self.scaled_bounds[table] = bound
                return
            if writes(step, pointer) or step.flow != "normal":
                return
            at += 1

    def loop_bound(self, position, register):
        """The count of the loop whose counter indexes the read at 'position': forward from it in a straight line
        (through calls too: the compiler keeps D2-D7 across them), "addq.w #1, Dreg" then "cmpi.w #N, Dreg" then a
        "blt"/"bcs" back to at or before the read, the counter cleared before that target; None where the loop is
        not found"""
        here = self.ordered[position][0]
        for at in range(position + 1, min(position + 1 + LOOP_WALKED, len(self.ordered) - 2)):
            step = self.ordered[at][1]
            operands = step.operands
            if step.mnemonic == "addq" and step.size == "w" and operands[0].mode in ("quick", "immediate") \
                    and operands[0].value == 1 and operands[1].mode == "dreg" and operands[1].reg == register:
                compare, branch = self.ordered[at + 1][1], self.ordered[at + 2][1]
                if compare.mnemonic != "cmpi" or compare.size != "w" or compare.operands[0].mode != "immediate" \
                        or compare.operands[1].mode != "dreg" or compare.operands[1].reg != register:
                    return None
                if branch.flow != "branch" or branch.target is None or branch.target > here \
                        or branch.target not in self.position_of \
                        or not (branch.mnemonic in ("blt", "bcs")
                                or (branch.mnemonic == "bcc" and branch.condition in ("lt", "cs"))):
                    return None
                first = self.position_of[branch.target]
                for back in range(first - 1, max(first - 9, -1), -1):
                    earlier = self.ordered[back][1]
                    moved = earlier.operands
                    if (earlier.mnemonic == "clr" and moved[0].mode == "dreg" and moved[0].reg == register) \
                            or (earlier.mnemonic == "moveq" and moved[0].value == 0 and moved[1].reg == register):
                        return compare.operands[0].value
                    if writes(earlier, register):
                        return None
                return None
            if writes(step, register) or step.flow not in ("normal", "call"):
                return None
        return None

    def spans_scaled(self, found):
        """The tables by a scaled index, in whole entries up to the next thing, where nothing describes them"""
        spans = sorted((first, stop) for first, (stop, _) in found.items())
        spans += sorted(tuple(span) for span in self.analysis.described)
        things = sorted(set(self.anchors) | set(self.analysis.instructions) | {first for first, _ in spans}
                        | set(self.scaled_tables))

        def after(place):
            at = bisect.bisect_right(things, place)
            return things[at] if at < len(things) else len(self.image)

        low_words = {}                  # {the place the code names: where its longs start}
        for table, (scale, read, _) in self.scaled_tables.items():
            if (scale, read) == (4, 2) and (after(table) - table) % scale == read:
                low_words[table] = table - (scale - read)
        things = sorted(set(things) - set(low_words) | set(low_words.values()))
        for table, (scale, _, _) in sorted(self.scaled_tables.items()):
            start = low_words.get(table, table)
            if any(first <= start < stop for first, stop in spans):
                continue
            stop = after(start)
            if table in self.scaled_bounds:
                bounded = start + self.scaled_bounds[table] * scale
                if bounded <= stop:
                    stop = bounded
            if (stop - start) % scale or stop - start > SCALED_MOST:
                continue
            found[start] = (stop, "table by a scaled index")
            if stop % 2 and after(stop) == stop + 1:
                found[stop] = (stop + 1, "byte that evens a table")

    def read_in_place(self, position, address, instruction):
        """A value the code reads by its address in the cartridge"""
        if instruction.mnemonic in ("lea", "pea", "jsr", "jmp") or instruction.size not in SIZES:
            return
        for operand in instruction.operands[:1]:
            if operand.mode in ("abs_long", "abs_short") and 0 < operand.value & 0xFFFFFF < len(self.image):
                place = operand.value & 0xFFFFFF
                self.values_in_place[place] = max(self.values_in_place.get(place, 0), SIZES[instruction.size])

    def spans_in_place(self, found):
        """The values read in place, where nothing else describes them"""
        spans = sorted((first, stop) for first, (stop, _) in found.items())
        starts = [first for first, _ in spans]
        for place, size in self.values_in_place.items():
            at = bisect.bisect_right(starts, place) - 1
            if at >= 0 and spans[at][1] > place:
                continue
            found[place] = (place + size, "value read in place")

    def spans_zeros(self, found):
        """The zeros that fill out what the walk describes, up to the next thing"""
        things = sorted(set(self.anchors) | set(self.analysis.instructions) | set(found)
                        | {first for first, _ in self.analysis.described})
        covered = bytearray(len(self.image))
        for first, stop in list(self.analysis.described) + [(first, stop) for first, (stop, _) in found.items()]:
            covered[first:stop] = b"\1" * (stop - first)
        for stop in sorted({stop for stop, _ in found.values()}):
            if stop >= len(self.image) or covered[stop] or stop in self.analysis.instructions:
                continue
            at = bisect.bisect_right(things, stop)
            after = things[at] if at < len(things) else len(self.image)
            if after - stop <= ZEROS_MOST and not any(self.image[stop:after]) and not any(covered[stop:after]):
                found[stop] = (after, "zeros that fill out a record")

    def spans_pointed(self, found):
        """The records read through a pointer, last: where another subject describes the place, its description
        is the whole of what is there (a table of which the code reads the first entry this way)"""
        for record, (size, _) in self.pointed_records.items():
            found.setdefault(record, (record + size, "record read through a pointer"))

    def spans_patterns(self, found):
        """The values by the level, an entry each, but the tables another subject describes and the entries
        inside another's (a table read as words of longs: "every 4, 2 read" inside "every 4, 4 read")"""
        entries = sorted((table + stride * level, table + stride * level + size)
                         for table, (stride, size, _) in self.value_tables_by_level.items() if table not in found
                         for level in range(LEVELS))
        stop = 0
        for first, last in entries:
            if first >= stop:
                found.setdefault(first, (last, "values by level"))
            stop = max(stop, last)
        for block, (size, _) in self.copied_blocks.items():
            found.setdefault(block, (block + size, "copied block"))
        for table, (entries, stride, _) in self.loop_tables.items():
            stop = min(table + entries * stride, min((place for place in self.anchors if place > table),
                                                     default=len(self.image)))
            found.setdefault(table, (stop, "loop table"))
        for table, (entries, stride, kind, _) in self.bounded_tables.items():
            found.setdefault(table, (min(table + entries * stride, len(self.image)), kind))
