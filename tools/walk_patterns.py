"""
Name:        walk_patterns.py
Description: Sonic the Hedgehog Spinball's code read for what it hands over: the patterns of its C compiler's
             calls and of the tables it reads by the level, for the walk (tools/data_walk.py)
Version:     0.1.0
Created:     13-11-2026
Modified:    13-11-2026
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
"""
import struct
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]

SCRATCH = {"D0", "D1", "A0", "A1"}  # the registers a call of the game's C does not keep
PUSHES_WALKED = 64                  # how far back from a call its pushes are looked for
LEVELS = 4                          # the tables the game has: what a table indexed by the level holds
LEVEL_VARIABLE = 0xFF75B0           # the level: 0-3 the tables, 4 the options screen (0FEDA4)


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
        self.handed = set()             # the places the code hands over or keeps in a table (the anchors but
                                        # the constants of instructions)

    def index_code(self):
        self.ordered = sorted(self.analysis.instructions.items())
        for position, (address, instruction) in enumerate(self.ordered):
            self.position_of[address] = position
            if instruction.flow in ("jump", "branch") and instruction.target is not None:
                self.comes_from.setdefault(instruction.target, []).append(position)

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
