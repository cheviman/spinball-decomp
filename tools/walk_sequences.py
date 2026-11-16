"""
Name:        walk_sequences.py
Description: Sonic the Hedgehog Spinball's front end's scripts: what its sequencer (0F4538) reads, a command at a
             time, and what the commands hand over, walked from where the code passes a script (for
             tools/data_walk.py, with walk_screens.py)
Version:     0.1.0
Created:     15-11-2026
Modified:    15-11-2026
Author:      Sebastian Toyos

0F4538 runs the script its first argument points at (its second goes to 0F3A44, which says whether to stop).
0F454A reads a byte, the command, and jumps through the table at 0F459A to its handler, which reads what follows
it (A4) and jumps back for the next command. Before each command 0F454A asks 0F3A44; when it says stop, 0F4570
frees the sprites the script keeps (the 80 bytes from FFF87E, through 0F418A) and the script returns what 0F3A44
said. The commands, with the bytes that follow each (words and longs at even places):

  0   value                              the end: the script returns the value (a byte, signed)
  1   slot, word, three words, sprite    0F40BE makes the sprite (its first argument; the three words shifted left
                                         by 4 are its second to fourth, the second word its fifth) and the byte at
                                         FFF87E + slot keeps what it returns
  2   byte, group, three words           0F40BE makes each sprite of the group, the same way: the group is a byte
                                         of the first slot, one of how many, then a long of the sprite and a word
                                         (whose low byte the command's byte replaces) for each; the bytes from
                                         FFF87E + slot keep what 0F40BE returns
  3   slot                               0F418A frees the sprite the byte at FFF87E + slot keeps
  4   byte, group                        0F418A frees the group's sprites (it reads the group's first two bytes)
  5   (nothing)                          nothing
  6   (nothing)                          nothing
  7   slot, word, three words, sprite    0F41FE gives the sprite the slot keeps (its first argument) the sprite
                                         (its second), as command 1's words
  8   byte, group, three words           0F41FE, as command 7, for each sprite of a group (as command 2)
  9   frames                             waits that many frames (0F38C8), asking 0F3A44 at each
  10  byte, script                       runs the script (0F4538, with the same second argument); stops this one
                                         when it returns other than 0
  11  count, count longs, function       calls the function with the longs (the first read is pushed first: the
                                         last argument); a palette, where the function reads one (0F3AE0's
                                         third argument, 0F3200's second: walk_screens.py's palette readers)
  12  times, script                      runs the script that follows, up to its command 0, that many times while
                                         it returns 0, then goes on after it; stops when it returns other than 0
  13  three bytes                        adds the second and the third to the two words of the VRAM at FC00 +
                                         the first and at the first (0F3910, 0F392E, 0F3954, 0F3976)
  14  line, palette                      0F3AE0: the palette's 16 colours into the line
  15  line, word, palette                0F3200: the fade of the line to the palette's 16 colours, in the word's
                                         steps
  16  plane, ...                         a screen's map into a plane (0F3C06 for 0 or 80, 0F3C82 for the others):
                                         below 80, a long of a screen's record (its x, y and map, 8 bytes, as
                                         walk_screens.py's); FF, nothing; from 80, words of y and x, then a long
                                         of a record whose map (its long at 4) the command takes
  17  index, word                        calls the function the index picks in 0F48F2's table of 3 (GEMS's start
                                         song, stop song, stop all) with the word
"""
import struct
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]
from walk_patterns import long_at  # noqa: E402

SEQUENCER = 0x0F4538                # (script, what 0F3A44 gets): runs a script
COMMANDS = 18                       # the commands of the table at 0F459A
SONG_CALLS = 0x0F48F2               # command 17's functions: GEMS's start song, stop song and stop all
SONG_CALLS_COUNT = 3
GROUP_HEAD = 2                      # a sprite group's slot and count
GROUP_ENTRY = 6                     # a sprite's long and a word
SCREEN_RECORD_BYTES = 8             # as walk_screens.py's


class SequencesWalk:
    """The front end's scripts, a command at a time"""

    def init_sequences(self):
        self.scripts = {}               # {address: (stop, how it was found)}
        self.sprite_groups = {}         # {address: (sprites, or None when only its slot and count are read, how)}
        self.script_calls = {}          # {function: the commands that call it}
        self.song_calls = set()         # command 17's indexes

    def walk_sequences(self):
        for position, (address, instruction) in enumerate(self.ordered):
            if instruction.flow == "call" and self.call_target(position) == SEQUENCER:
                for script, _ in self.pointers_passed(position, 0):
                    self.walk_script(script, f"passed to {SEQUENCER:06X} at {address:06X}")

    def walk_script(self, address, found):
        if address in self.scripts:
            return
        self.scripts[address] = (None, found)
        self.scripts[address] = (self.script_block(address, f"the script {address:06X} ({found})"), found)

    def script_block(self, at, where):
        """The commands from 'at' up to the command 0 that ends them: where they stop"""
        while True:
            command = self.image[at]
            if command >= COMMANDS:
                raise SystemExit(f"{at:06X}: no command ({command}), in {where}")
            if command == 0:
                return at + 2
            at = self.script_command(at, command, where)

    def script_word(self, at, where):
        if at & 1:
            raise SystemExit(f"{at:06X}: a word at an odd place, in {where}")
        return struct.unpack_from(">H", self.image, at)[0]

    def script_long(self, at, where):
        if at & 1:
            raise SystemExit(f"{at:06X}: a long at an odd place, in {where}")
        return long_at(self.image, at)

    def script_command(self, at, command, where):
        """What a command (not 0) hands over: where the next command is"""
        how = f"command {command} at {at:06X}"
        if command in (1, 7):
            for word in range(4):
                self.script_word(at + 2 + 2 * word, where)
            self.add_sprite(self.script_long(at + 10, where), how)
            return at + 14
        if command in (2, 8):
            for word in range(3):
                self.script_word(at + 6 + 2 * word, where)
            self.add_sprite_group(self.script_long(at + 2, where), True, how)
            return at + 12
        if command in (3, 9):
            return at + 2
        if command == 4:
            self.add_sprite_group(self.script_long(at + 2, where), False, how)
            return at + 6
        if command in (5, 6):
            return at + 1
        if command == 10:
            self.walk_script(self.script_long(at + 2, where), how)
            return at + 6
        if command == 11:
            count = self.image[at + 1]
            arguments = [self.script_long(at + 2 + 4 * read, where) for read in range(count)][::-1]
            function = self.script_long(at + 2 + 4 * count, where)
            self.script_calls.setdefault(function, []).append(at)
            for argument, colours in self.palette_readers.get(function, {}).items():
                if isinstance(colours, tuple):
                    colours = arguments[colours[1]] if colours[1] < count else None
                if argument < count and colours:
                    self.add_palette(arguments[argument], colours, f"argument {argument} of {function:06X}, {how}")
            return at + 6 + 4 * count
        if command == 12:
            return self.script_block(at + 2, f"command 12's script at {at + 2:06X}, in {where}")
        if command == 13:
            return at + 4
        if command == 14:
            self.add_palette(self.script_long(at + 2, where), 16, how)
            return at + 6
        if command == 15:
            self.script_word(at + 2, where)
            self.add_palette(self.script_long(at + 4, where), 16, how)
            return at + 8
        if command == 16:
            plane = self.image[at + 1]
            if plane == 0xFF:
                return at + 2
            if plane < 0x80:
                record = self.script_long(at + 2, where)
                self.screen_records.setdefault(record, how)
                self.add_map(long_at(self.image, record + 4), f"the record {record:06X}'s, {how}")
                return at + 6
            self.script_word(at + 2, where)
            self.script_word(at + 4, where)
            record = self.script_long(at + 6, where)
            self.record_maps.setdefault(record + 4, how)
            self.add_map(long_at(self.image, record + 4), f"the record {record:06X}'s, {how}")
            return at + 10
        if command == 17:
            index = self.image[at + 1]
            if index >= SONG_CALLS_COUNT:
                raise SystemExit(f"{at:06X}: command 17's function {index} (of {SONG_CALLS_COUNT}), in {where}")
            self.script_word(at + 2, where)
            self.song_calls.add(index)
            return at + 4
        raise SystemExit(f"{at:06X}: command {command}, in {where}")

    def add_sprite_group(self, address, whole, found):
        if address & 1 or address + GROUP_HEAD > len(self.image):
            raise SystemExit(f"{address:06X}: no sprite group, {found}")
        known = self.sprite_groups.get(address)
        if not whole:
            if known is None:
                self.sprite_groups[address] = (None, found)
            return
        if known is not None and known[0] is not None:
            return
        count = self.image[address + 1]
        if not count:
            raise SystemExit(f"{address:06X}: a sprite group of no sprites, {found}")
        for entry in range(count):
            self.add_sprite(long_at(self.image, address + GROUP_HEAD + GROUP_ENTRY * entry),
                            f"sprite {entry} of the group {address:06X}")
        self.sprite_groups[address] = (count, found)

    def sequence_places(self):
        """The places the scripts' walk found, for the places the code hands over"""
        return set(self.scripts) | set(self.sprite_groups)

    def spans_sequences(self, found):
        for address, (stop, _) in self.scripts.items():
            found.setdefault(address, (stop, "sequencer script"))
        for address, (count, _) in self.sprite_groups.items():
            size = GROUP_HEAD + GROUP_ENTRY * count if count else GROUP_HEAD
            found.setdefault(address, (address + size, "sprite group" if count else "sprite group's slot and count"))
        if self.song_calls:
            found.setdefault(SONG_CALLS, (SONG_CALLS + 4 * SONG_CALLS_COUNT, "sequencer's song calls"))
