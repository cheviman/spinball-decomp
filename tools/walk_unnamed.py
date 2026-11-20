"""
Name:        walk_unnamed.py
Description: Sonic the Hedgehog Spinball's data the walk does not reach, described by its shape where it lies
             among data of one kind (for tools/data_walk.py)
Version:     0.2.0
Created:     19-11-2026
Modified:    19-11-2026
Author:      Sebastian Toyos

What the walk describes, it reaches from the code: an address an instruction holds, an entry of a table, the next
of a state. What is left between two things it described, it does not reach: no instruction, table or record it
follows holds its address. Where such bytes lie right against data of one kind and read whole as more of the
same, they are taken for that, and their kind says that the walk does not reach them. It is the only description
here that comes from the shape of the bytes and not from the code that reads them, and it does not say that
nothing reads them: the scenarios' reads are the check (tools/coverage.py --reads; the first time, they showed
three "sprites nothing names" drawn by 0F40BE, through tables of sprites the walk then learned to follow, and
the word at +8 of a box read by 0E5EBA).
  state            beside a state, whole states (10 bytes) whose sprites are sprites a walked state has, whose case
                   0F6BF6 has, and whose next is a state, walked or one of them (0D2944, 9; 0D2A3E, 16)
  state's sprites  between two states' sprites, whole lists by their own counts (0CB116, two of a sprite)
  screen sprite    beside a screen sprite, a multiple of its 8 bytes
  definition       between two definitions, a multiple of their 12 bytes (0C0B38, 0C0C64, 0C0CC4, 0C103C, 0C1228,
                   0C1384)
  boxes            after a box, the rest of its 12 bytes and then whole records of 12: the 2 bytes after an
                   object's box of 10 (0C4796, a box); the six after a list's box at 0C3136 were taken for these
                   until the walk followed the table at 0C3226 that hands them to 0DB900 (walk_levels.py)
  sprite group     beside a sprite group, a group by its own count: 2 bytes and 6 a sprite (099EC0)
"""
from walk_sequences import GROUP_ENTRY, GROUP_HEAD
from walk_states import SPRITE_SIZE, SPRITE_SIZE_MOST, SPRITES_HEAD, SPRITES_MOST, STATE_SIZE
from walk_patterns import long_at

SCREEN_SPRITE = 8
DEFINITION = 12
BOX_RECORD = 12                     # a box and what follows it, up to the next
BOX_REST = {"object box": 2, "box of a list": 4}    # what a walked box leaves of its record


class UnnamedWalk:
    """What the walk does not reach, by the kind of what it lies against"""

    def spans_unnamed(self, found):
        covered = bytearray(len(self.image))
        for first, stop in list(self.analysis.described) + [(first, stop) for first, (stop, _) in found.items()]:
            covered[first:stop] = b"\1" * (stop - first)
        for address, instruction in self.analysis.instructions.items():
            covered[address:address + instruction.length] = b"\1" * instruction.length
        ends = {stop: kind for stop, kind in found.values()}
        first = covered.find(b"\0")
        while first >= 0:
            stop = covered.find(b"\1", first)
            stop = len(covered) if stop < 0 else stop
            kind = self.unnamed_kind(first, stop, ends.get(first), found.get(stop, (None, None))[1])
            if kind:
                found[first] = (stop, kind + " the walk does not reach")
            first = covered.find(b"\0", stop)

    def unnamed_kind(self, first, stop, before, after):
        size, beside = stop - first, (before, after)
        if "state" in beside and not size % STATE_SIZE and self.states_in(first, stop):
            return "state"
        if beside == ("state's sprites", "state's sprites") and self.sprites_in(first, stop):
            return "state's sprites"
        if "screen sprite" in beside and not size % SCREEN_SPRITE:
            return "screen sprite"
        if beside == ("definition", "definition") and not size % DEFINITION:
            return "definition"
        if before in BOX_REST and size > BOX_REST[before] and size % BOX_RECORD == BOX_REST[before]:
            return "boxes"
        if "sprite group" in beside and self.image[first + 1] \
                and size == GROUP_HEAD + GROUP_ENTRY * self.image[first + 1]:
            return "sprite group"
        return None

    def states_in(self, first, stop):
        places = set(range(first, stop, STATE_SIZE))
        return all(not self.state_problem(place) and long_at(self.image, place) in self.state_sprites
                   and (long_at(self.image, place + 6) in places or long_at(self.image, place + 6) in self.states)
                   for place in places)

    def sprites_in(self, first, stop):
        at = first
        while at + SPRITES_HEAD <= stop:
            count = int.from_bytes(self.image[at:at + 2], "big")
            sizes = [int.from_bytes(self.image[at + SPRITES_HEAD + SPRITE_SIZE * sprite + 2:][:2], "big")
                     for sprite in range(min(count, SPRITES_MOST))]
            if count > SPRITES_MOST or any(size > SPRITE_SIZE_MOST for size in sizes):
                return False
            at += SPRITES_HEAD + SPRITE_SIZE * count
        return at == stop
