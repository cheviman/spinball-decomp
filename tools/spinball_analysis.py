"""
Name:        spinball_analysis.py
Description: the core's 68000 static analysis (tools/core/m68000/analysis.py) with what Sonic Spinball's
             compiler does that the core does not follow: its switches, its calls through registers that hold
             known functions, and its tables of addresses read relative to the PC
Version:     0.1.0
Created:     13-11-2026
Modified:    13-11-2026
Author:      Sebastian Toyos

Usage: as the core's: python tools/disassemble.py [cartridge] [--trace executed.txt ...]. The profile names this
module as its ANALYSIS, so the core's scripts (coverage.py among them) take it in the core's place.

Spinball is C (an early Sierra Systems compiler, the Sonic Retro forum believes), and three of its ways stop the
core's walk:
  - a switch is a jump through a table of words, each the place of a case less the table's: "move.w
    TABLE(PC,Dn.l), Dn" then "jmp TABLE(PC,Dn.w)", after the bound the code checks ("moveq #N, Dk; cmp.l Dk,
    Dn; bhi default", or "cmpi #N, Dn; bhi"): N+1 cases (N with bcc); without a bound in its block, the table
    goes on up to the first case's code (main at 0D5230: "moveq #6, D1; cmp.l D1, D0; bhi"). The tables are
    described data for the coverage;
  - a call through a register that holds known functions keeps the address registers all of them keep (the core
    works out what each function keeps, and keeps it for a call that names its function): 0F2F96 keeps $F3148 in
    A2 ("movea.l #$F3148, A2") across its calls through A3 and A4, then calls through A2;
  - "movea.l TABLE(PC,Xn), An" reads an entry of a table of addresses, as "movea.l (An,Xn)" does (the front
    end's sequencer, 0F4562 "movea.l $F459A(PC,D0.w), A0", 0F4566 "jmp (A0)").
Nothing else of the core changes. If another game turns out to need these, they belong in the core.
"""
import sys
from pathlib import Path

from m68000 import analysis as core
from m68000 import disassembler as dis
from m68000.analysis import *  # noqa: F401,F403  (what the core's scripts read from the profile's ANALYSIS module)
from m68000.analysis import CONSTANT, ENTRY, MAX_TABLE, ROOT, game_profile, known, load_symbols, load_trace


class Analysis(core.Analysis):
    """The core's analysis, and the C compiler's switches (switch_tables: {table: case addresses})"""

    def reset(self):
        super().reset()
        self.switch_tables = {}

    def ends_table(self, address, table):
        return super().ends_table(address, table) or (address != table and address in self.switch_tables)

    @staticmethod
    def switch_bound(block):
        """How many cases the bound before a switch's jump allows: the last unsigned comparison of the block
        with a constant (cmpi #N, or cmp of a register moveq set to N) and the bhi or bcc after it; None if the
        block has none"""
        for position in range(len(block) - 2, 0, -1):
            branch = block[position]
            if branch.mnemonic != "bcc" or branch.condition not in ("hi", "cc"):
                continue
            compare = block[position - 1]
            if compare.mnemonic not in ("cmp", "cmpi") or len(compare.operands) != 2:
                return None
            source = compare.operands[0]
            bound = None
            if source.mode == "immediate":
                bound = source.value
            elif source.mode == "dreg":
                for earlier in reversed(block[:position - 1]):
                    if len(earlier.operands) == 2 and earlier.operands[1].mode == "dreg" \
                            and earlier.operands[1].reg == source.reg:
                        if earlier.mnemonic == "moveq":
                            bound = earlier.operands[0].value
                        break
            if bound is None or bound < 0:
                return None
            return bound + 1 if branch.condition == "hi" else bound
        return None

    def read_switch_table(self, table, count, state):
        """A switch's cases: 'count' words, or up to the first case's code when the count is not known"""
        if table in self.switch_tables:
            return
        entries = []
        for index in range(count if count is not None else MAX_TABLE):
            where = table + 2 * index
            if count is None and (self.ends_table(where, table) or (entries and where >= min(entries))):
                break
            word = self.mem.r16(where)
            target = (table + word - (0x10000 if word & 0x8000 else 0)) & 0xFFFFFF
            if not self.plausible(target) or (count is None and not self.clean(target)):
                break
            entries.append(target)
        self.switch_tables[table] = entries
        for target in entries:
            self.enter(target, state, "loc")

    def computed(self, instruction, state, block):
        operand = instruction.operands[0]
        if operand.mode == "pc_index" and instruction.flow == dis.FLOW_JUMP:
            self.read_switch_table((operand.base + operand.disp) & 0xFFFFFF, self.switch_bound(block), state)
            return
        super().computed(instruction, state, block)

    def source_values(self, operand, size, state):
        if operand.mode == "pc_index" and size == "l":
            return frozenset({(ENTRY, (operand.base + operand.disp) & 0xFFFFFF)})
        return super().source_values(operand, size, state)

    def call_keeps(self, instruction, state):
        """The address registers a call leaves alone: its function's (the core's), or for a call through a
        register that holds known functions, the ones all of them leave alone"""
        if instruction.target is not None:
            return self.preserved.get(instruction.target, ())
        operand = instruction.operands[0]
        if operand.mode not in ("indirect", "disp"):
            return ()
        values = known(state.get(operand.reg))
        if not values or any(kind != CONSTANT for kind, _ in values):
            return ()
        offset = operand.disp if operand.mode == "disp" else 0
        kept = None
        for _, value in values:
            leaves = frozenset(self.preserved.get((value + offset) & 0xFFFFFF, ()))
            kept = leaves if kept is None else kept & leaves
        return kept or ()

    def walk(self, address):
        """The core's walk, but for what a call leaves (call_keeps)"""
        state = dict(self.entry_states[address])
        start = address
        block = []
        while True:
            if not self.plausible(address):
                return
            instruction = self.instructions.get(address) or dis.decode(self.mem, address)
            if instruction.flow == dis.FLOW_INVALID:
                return
            self.instructions[address] = instruction
            block.append(instruction)
            self.note_store(instruction, state)
            flow = instruction.flow
            if flow == dis.FLOW_CALL:
                if instruction.target is not None:
                    self.enter(instruction.target, state, "func")
                else:
                    self.computed(instruction, state, block)
                kept = self.call_keeps(instruction, state)
                state = {register: values for register, values in state.items() if register in kept}
            elif flow == dis.FLOW_BRANCH:
                self.enter(instruction.target, state, "loc")
            elif flow == dis.FLOW_JUMP:
                if instruction.target is not None:
                    self.enter(instruction.target, state, "loc")
                else:
                    self.computed(instruction, state, block)
                return
            elif flow == dis.FLOW_RETURN:
                return
            else:
                self.step(instruction, state)
            address += instruction.length
            if address in self.entry_states and address != start:
                self.enter(address, state)
                return

    def finish(self):
        """The core's, and the switches' tables as described data"""
        super().finish()
        for table, entries in self.switch_tables.items():
            self.described.append((table, table + 2 * len(entries)))


def write_report(analysis, path, executed=None):
    """The core's report, and the switches"""
    core.write_report(analysis, path, executed)
    line = f"switch tables: {len(analysis.switch_tables)} ({sum(map(len, analysis.switch_tables.values()))} cases)"
    with open(path, "a", encoding="ascii") as out:
        out.write(line + "\n")
    print(line)


def main():
    """The core's main, with this analysis"""
    arguments = sys.argv[1:]
    traces = []
    while "--trace" in arguments:
        position = arguments.index("--trace")
        traces.append(Path(arguments[position + 1]))
        del arguments[position:position + 2]
    source = Path(arguments[0]) if arguments else ROOT / "rom"
    image = game_profile.rom.build_program(game_profile.rom.load_set(source))
    symbols_path = ROOT / "symbols.txt"
    symbols = load_symbols(symbols_path) if symbols_path.exists() else {}
    analysis = Analysis(image, symbols)
    analysis.run()
    out = ROOT / "build" / "listing"
    out.mkdir(parents=True, exist_ok=True)
    core.write_listing(analysis, out / f"{game_profile.BINARY}.s")
    executed = load_trace(traces)[0] if traces else None
    write_report(analysis, out / "report.txt", executed)


if __name__ == "__main__":
    main()
