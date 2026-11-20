"""
Name:        walk_unnamed.py
Description: Sonic the Hedgehog Spinball's data that no code names, described by its shape where it lies among
             data of one kind (for tools/data_walk.py)
Version:     0.1.0
Created:     19-11-2026
Modified:    19-11-2026
Author:      Sebastian Toyos

What the walk describes, it reaches from the code: an address an instruction holds, an entry of a table, the next
of a state. What is left between two things it described, nothing names: no instruction, no table and no record
of the cartridge holds its address, and no scenario reads it. Where such bytes lie right against data of one kind
and read whole as more of the same, they are taken for that, and their kind says that nothing names them. It is
the only description here that comes from the shape of the bytes and not from the code that reads them:
  state            beside a state, whole states (10 bytes) whose sprites are sprites a walked state has, whose case
                   0F6BF6 has, and whose next is a state, walked or one of them (0D2944, 9; 0D2A3E, 16)
  state's sprites  between two states' sprites, whole lists by their own counts (0CB116, two of a sprite)
  screen sprite    beside a screen sprite, a multiple of its 8 bytes (0A1408-0A1A73, 43 in 9 places)
  definition       between two definitions, a multiple of their 12 bytes (0C0B38, 0C0C64, 0C0CC4, 0C103C, 0C1228,
                   0C1384)
  boxes            after a box of 8 bytes, the long after it that no code reads, and then boxes with theirs: 4
                   bytes and a multiple of 12 (0C16B8 and 0C16D0, a long of 80000000; 0C4798, a box; 0C3136, 6)
  sprite group     beside a sprite group, a group by its own count: 2 bytes and 6 a sprite (099EC0)
"""
from walk_sequences import GROUP_ENTRY, GROUP_HEAD
from walk_states import SPRITE_SIZE, SPRITE_SIZE_MOST, SPRITES_HEAD, SPRITES_MOST, STATE_SIZE
from walk_patterns import long_at

SCREEN_SPRITE = 8
DEFINITION = 12
BOX = 8                             # a box, and the long after it
BOX_LONG = 4


class UnnamedWalk:
    """What no code names, by the kind of what it lies against"""

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
                found[first] = (stop, kind)
            first = covered.find(b"\0", stop)

    def unnamed_kind(self, first, stop, before, after):
        size, beside = stop - first, (before, after)
        if "state" in beside and not size % STATE_SIZE and self.states_in(first, stop):
            return "state nothing names"
        if beside == ("state's sprites", "state's sprites") and self.sprites_in(first, stop):
            return "state's sprites nothing names"
        if "screen sprite" in beside and not size % SCREEN_SPRITE:
            return "screen sprite nothing names"
        if beside == ("definition", "definition") and not size % DEFINITION:
            return "definition nothing passes"
        if before in ("object box", "box of a list") and size % (BOX + BOX_LONG) == BOX_LONG:
            return "long after a box no code reads" if size == BOX_LONG else "boxes nothing names"
        if "sprite group" in beside and self.image[first + 1] and size == GROUP_HEAD + GROUP_ENTRY * self.image[first + 1]:
            return "sprite group nothing names"
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
