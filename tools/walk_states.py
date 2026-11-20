"""
Name:        walk_states.py
Description: Sonic the Hedgehog Spinball's chains of states: what set_state (0F789A) sets an object to and what
             the objects' step (0F780E, 0F785A) moves it on to, walked from where the code passes a state or
             stores one in an object, and the sprites each state draws the object with (for tools/data_walk.py)
Version:     0.2.0
Created:     16-11-2026
Modified:    19-11-2026
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
            The code also stores a state itself, "move.l #STATE, FIELD" with FIELD an object's field 18: its
            address, when it is 18h after an object the code names, as an absolute long (0FB102, FF75CC) or
            from a register the function loads with an address and nothing else (0F6C02, A5 with FF75B4); or
            "($18,An)" with An a pointer the code works out (0F6ABC, A2 one of the 5 objects of 32 bytes at
            FFF218). An object the code names is an address of the RAM it stores as a long where the lists
            keep their objects: "move.l #OBJECT, (A0,D0.w)", the first of a list (0FB0D6, FF75B4; 0FADE6,
            FF3F3C; 0FC490, FF40C0), and "move.l #OBJECT, FIELD.l", the next or the one before in another's
            fields 0 and 4 (0FB0F8, FF75D4 in FF75B4; 0FC4BE, FF4100 in FF40C0). The object's step takes the
            state from there like any other next.
  state's sprites  what a state's long gives field 14, and what the code stores there itself ("move.l #PLACE,
            FIELD" the same way, field 14: 0FB0EE, 0F6AA4): the sprites the object is drawn with, read by the
            two functions that fill the sprite list at FFA674, 0F798A (the objects of the lists at FF5238,
            0F79F0) and 0F7AFE (the 5 at FFF218, 0F7B4C). A word, the sprites it has (0F7AC2, 0F7BEA: signed);
            a word taken from each sprite's X and a word taken from the object's Y (0F79F4-0F7A00,
            0F7B50-0F7B5C); then 8 bytes a sprite: its Y, its size (the low byte is the one written:
            0F7A60-0F7A64), its tile, added to the object's field E, and its X (0F7A34-0F7AAA, 0F7B86-0F7BD2).
            A sprite whose X on the screen comes out 0 (of 9 bits) is not written, and the loop reads it again
            until the count runs out (0F7AAE-0F7AC0): nothing after it is drawn. 0CA40E, 0CA454, 0CA49A and
            0CA4E0 say 10 sprites and the next one starts after 8: their last two are the next one's first 16
            bytes, and their span ends where it starts.
  states' table  that table: the longs of its states.
"""
from walk_patterns import long_at

SET_STATE = 0x0F789A
STATE_SIZE = 10
STATE_CASES = 0x22                  # 0F6BF6's switch: "moveq #$22, D1; cmp.l D1, D0; bhi" (0F6C10-0F6C14)
RAM = 0xFF0000                      # where the objects are
FIELD_SPRITES = 0x14                # an object's field 14: its state's sprites
FIELD_NEXT = 0x18                   # an object's field 18: its next state
SPRITES_HEAD = 6                    # a state's sprites: the count and the two words taken from X and Y
SPRITE_SIZE = 8
SPRITES_MOST = 80                   # the sprites the console has
SPRITE_SIZE_MOST = 0xF              # a sprite's size: 2 bits across, 2 down


class StatesWalk:
    """The chains of states 0F789A sets the objects to"""

    def init_states(self):
        self.states = {}                # {address: how it was found}
        self.state_tables = {}          # {address: (entries, how it was found)}
        self.state_sprites = {}         # {address: (sprites, how it was found)}
        self.objects = set()            # the objects the code names: the addresses of the RAM it stores as longs

    def walk_states(self):
        stored = []
        for _, instruction in self.ordered:
            operands = instruction.operands
            if instruction.mnemonic == "move" and instruction.size == "l" and len(operands) == 2 \
                    and operands[0].mode == "immediate" and operands[0].value & 0xFFFFFF >= RAM \
                    and operands[1].mode in ("index", "abs_long"):
                self.objects.add(operands[0].value & 0xFFFFFF)
        for position, (address, instruction) in enumerate(self.ordered):
            place, field = self.object_store(position, instruction)
            if field == FIELD_NEXT:
                self.walk_chain(place, f"stored in an object's field 18 at {address:06X}")
            elif field == FIELD_SPRITES:
                stored.append((place, f"stored in an object's field 14 at {address:06X}"))
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
        for state in sorted(self.states):
            self.add_state_sprites(long_at(self.image, state), f"the sprites of the state {state:06X}")
        for place, found in stored:
            self.add_state_sprites(place, found)
        self.check_state_sprites()

    def object_store(self, position, instruction):
        """(place, field) of "move.l #PLACE, FIELD" with PLACE in the cartridge and FIELD an object's field 14 or
        18, or (None, None)"""
        operands = instruction.operands
        if instruction.mnemonic != "move" or instruction.size != "l" or len(operands) != 2 \
                or operands[0].mode != "immediate":
            return None, None
        place, destination = operands[0].value & 0xFFFFFFFF, operands[1]
        if place & 1 or not 0 < place < len(self.image):
            return None, None
        if destination.mode == "abs_long":
            address = destination.value & 0xFFFFFF
        elif destination.mode == "disp" and destination.reg.startswith("A") and destination.reg not in ("A6", "A7"):
            base = self.table_in(position, destination.reg)
            if base is None:            # a pointer the code works out: the field is the displacement
                if destination.disp in (FIELD_SPRITES, FIELD_NEXT):
                    return place, destination.disp
                return None, None
            address = base + destination.disp
        else:
            return None, None
        for field in (FIELD_SPRITES, FIELD_NEXT):
            if address - field in self.objects:
                return place, field
        return None, None

    def add_state_sprites(self, address, found):
        if address in self.state_sprites:
            return
        if address & 1 or address + SPRITES_HEAD > len(self.image):
            raise SystemExit(f"{address:06X}: no state's sprites ({found})")
        count = int.from_bytes(self.image[address:address + 2], "big")
        if count > SPRITES_MOST or address + SPRITES_HEAD + SPRITE_SIZE * count > len(self.image):
            raise SystemExit(f"{address:06X}: {count} sprites, no state's sprites ({found})")
        self.state_sprites[address] = (count, found)

    def check_state_sprites(self):
        """Each sprite's size, of the sprites before the next state's sprites start (those after are its bytes)"""
        groups = sorted(self.state_sprites)
        for address, following in zip(groups, groups[1:] + [len(self.image)]):
            count, found = self.state_sprites[address]
            for sprite in range(count):
                at = address + SPRITES_HEAD + SPRITE_SIZE * sprite
                size = int.from_bytes(self.image[at + 2:at + 4], "big")
                if at + SPRITE_SIZE <= following and size > SPRITE_SIZE_MOST:
                    raise SystemExit(f"{address:06X}: sprite {sprite}'s size is {size:04X}, no state's sprites "
                                     f"({found})")

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
        return set(self.states) | set(self.state_tables) | set(self.state_sprites)

    def spans_states(self, found):
        for address in self.states:
            found.setdefault(address, (address + STATE_SIZE, "state"))
        for address, (entries, _) in self.state_tables.items():
            found.setdefault(address, (address + 4 * entries, "states' table"))
        groups = sorted(self.state_sprites)
        for address, following in zip(groups, groups[1:] + [len(self.image)]):
            stop = address + SPRITES_HEAD + SPRITE_SIZE * self.state_sprites[address][0]
            found.setdefault(address, (min(stop, following), "state's sprites"))
