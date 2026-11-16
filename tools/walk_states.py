"""
Name:        walk_states.py
Description: Sonic the Hedgehog Spinball's chains of states: what set_state (0F789A) sets an object to and what
             the objects' step (0F780E, 0F785A) moves it on to, walked from where the code passes a state (for
             tools/data_walk.py)
Version:     0.1.0
Created:     16-11-2026
Modified:    16-11-2026
Author:      Sebastian Toyos

  state     what 0F789A takes as its second argument (its first is the object), 10 bytes: a long the object's
            field 14 takes, a byte its field 10 takes (sign-extended: the steps the state lasts), a byte 0F6BF6
            gets (the case of its switch the state runs when it starts, 0-22h), and the next state, which its
            field 18 takes (0F789A-0F78BE). 0F780E (each object of a list) and 0F785A (one object) count field 10
            down and, when it runs out, set the object to the state field 18 holds the same way (0F7828-0F7848,
            0F786E-0F788E): a state's next is a state, and a chain goes round (its last state's next is one of
            its own). Found where the code passes one, "pea STATE.l" as 0F789A's second argument (a bsr, a jsr,
            or a "jsr (An)" with An the function), or an entry of a table, "move.l (An), -(A7)" with An loaded
            "movea.l #TABLE, An" in the same function and nowhere else (0F8C4C: 0F8C76, then a loop that moves
            A4 on by 4, 7 times, 0F8E98-0F8EA4); then each next until a state already walked. A table's entries
            go on while each is a chain of states, and stop at one that is not (after 0D3556's 7, 000A0003).
            0D2944 and 0D2A3E start two chains no code and no long of the cartridge names: unknown.
  states' table  that table: the longs of its states.
"""
from walk_patterns import long_at

SET_STATE = 0x0F789A
STATE_SIZE = 10
STATE_CASES = 0x22                  # 0F6BF6's switch: "moveq #$22, D1; cmp.l D1, D0; bhi" (0F6C10-0F6C14)


class StatesWalk:
    """The chains of states 0F789A sets the objects to"""

    def init_states(self):
        self.states = {}                # {address: how it was found}
        self.state_tables = {}          # {address: (entries, how it was found)}

    def walk_states(self):
        for position, (address, instruction) in enumerate(self.ordered):
            if instruction.flow != "call" or self.call_target(position) != SET_STATE:
                continue
            where = f"passed to {SET_STATE:06X} at {address:06X}"
            for state, _ in self.pointers_passed(position, 1):
                self.walk_chain(state, where)
            for push in self.pushes(position, 1) or ():
                source = push.operands[0]
                if push.mnemonic == "move" and source.mode == "indirect" and source.reg.startswith("A"):
                    table = self.table_in(position, source.reg)
                    if table is not None:
                        self.walk_state_table(table, f"its entries {where}")

    def table_in(self, position, register):
        """The table "movea.l #TABLE, An" loads in the function of the instruction at 'position', when that is the
        only place the function loads An from"""
        function = self.function_of(self.ordered[position][0])
        start = self.position_of.get(function)
        if start is None:
            return None
        tables = set()
        for at, instruction in self.ordered[start:]:
            operands = instruction.operands
            if at != function and at in self.analysis.functions:
                break
            if instruction.mnemonic == "movea" and len(operands) == 2 and operands[1].mode == "areg" \
                    and operands[1].reg == register:
                if operands[0].mode != "immediate":
                    return None
                tables.add(operands[0].value & 0xFFFFFF)
        return tables.pop() if len(tables) == 1 else None

    def walk_state_table(self, table, found):
        entries = 0
        while self.is_chain(long_at(self.image, table + 4 * entries)):
            self.walk_chain(long_at(self.image, table + 4 * entries), f"entry {entries} of {table:06X} ({found})")
            entries += 1
        if not entries:
            raise SystemExit(f"{table:06X}: no states' table ({found})")
        self.state_tables[table] = (entries, found)

    def state_problem(self, address):
        """What keeps 'address' from being a state, or None"""
        if address & 1 or address + STATE_SIZE > len(self.image):
            return "no state"
        if self.image[address + 5] > STATE_CASES:
            return f"a state whose case ({self.image[address + 5]:02X}) 0F6BF6 has not"
        return None

    def is_chain(self, address):
        seen = set()
        while address not in seen and address not in self.states:
            if self.state_problem(address):
                return False
            seen.add(address)
            address = long_at(self.image, address + 6)
        return True

    def walk_chain(self, address, found):
        while address not in self.states:
            problem = self.state_problem(address)
            if problem:
                raise SystemExit(f"{address:06X}: {problem} ({found})")
            self.states[address] = found
            found = f"the next of {address:06X}"
            address = long_at(self.image, address + 6)

    def state_places(self):
        """The states the walk found, for the places the code hands over"""
        return set(self.states) | set(self.state_tables)

    def spans_states(self, found):
        for address in self.states:
            found.setdefault(address, (address + STATE_SIZE, "state"))
        for address, (entries, _) in self.state_tables.items():
            found.setdefault(address, (address + 4 * entries, "states' table"))
