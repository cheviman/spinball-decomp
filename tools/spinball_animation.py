"""
Name:        spinball_animation.py
Description: Sonic the Hedgehog Spinball's animations: the steps an animated object runs, read as the game reads
             them
Version:     0.1.0
Created:     13-11-2026
Modified:    13-11-2026
Author:      Sebastian Toyos

An animation is a list of 16-bit words an object's field 0 walks (0D5A06: when the frame's time runs out, the
next word; words with bit 15 set are commands, run until a frame or a command that yields):
  frame      bit 15 clear: bits 0-13 the sprite of the object's sprite table (3FFF: none), bit 14 mirrored
             against the object (0D591E-0D5A00). The frame shows for the object's frame time (field 2B).
  command    bit 15 set: bits 8-12 the command, bits 13-14 how its value comes, bits 0-7 its byte (0D5B4E,
             0D5DF8). Command 1F is a longer one: its byte is the command, and the next word its value.
             The value (0D5DF8):
               mode 0000  the byte, signed (1F: the next word)
               mode 2000  a variable: the byte (1F: the next word) is its number (0D66AE: 00-3F the
                          variables at FFAB78 from the object's field 2D on, 40-45 the object's own bytes at 2E,
                          46-4B its parent's, 4C on the other's at field 7)
               mode 4000  a variable as above, then a long: an address (its top four bits 0)
               mode 6000  a variable as above, then a long: a table's address in its low 28 bits, and in its top
                          four what the variable picks in it: 0 a byte at +n (and 3, 7 on), 1 a byte at +2n, 2 a
                          byte at +2n+1, 4 a word at +2n, 5 a word at +4n, 6 a word at +4n+2
  Command 0D shows a frame worked out (0D591E): with mode 4000, the next word plus the variable; with another
  mode, the word at +2n of the table whose address the long after it holds. The other commands, by 0D5B2E's switch
  (0D5B94), and what they take besides their value:
    00 end: the object is done (field 22 bit 15)       01 yield
    02 nothing                                          03 go to the address
    04 go to the address until a counter (field 2C) reaches the byte, then on
    06 a word N, then N+1 longs: go to the value's one (1 to N+1), or on past them when the value is 0 or more
    07 wait: the frame time this once is the value     08 wait a random time up to the value (0D69FA)
    09 field 22 bit 5, and yield unless its bit 1      0B the frame time (field 2B) becomes the value
    0C make an animated object: the long is its definition, then two words, x and y from this one
    0E 0D6724 with the value                           0F 0D6724 with the value and, in mode 0, the next word
    10 call the function at the address, with the object   11 0D560E with the value's byte (a sound)
    13 0D8410 with the value's byte                     14 field 0C, and field 4 of what field 3A points at
    15 0F6174 with the value's byte
    (through 1F) 20 x += value, 21 y += value, 25 x = value, 26 y = value, each followed by the collision's
    check (0D6796, 0D65B0)
    any other: 0D3E6C (the game's error stop)
"""
import struct
from dataclasses import dataclass, field

FRAME_NONE = 0x3FFF
COMMAND_NAMES = {
    0x00: "end", 0x01: "yield", 0x02: "nothing", 0x03: "go", 0x04: "repeat", 0x06: "choose", 0x07: "wait",
    0x08: "wait_random", 0x09: "flag", 0x0B: "frame_time", 0x0C: "make", 0x0D: "frame_of", 0x0E: "set",
    0x0F: "set2", 0x10: "call", 0x11: "sound", 0x13: "effect", 0x14: "field", 0x15: "music",
    0x20: "move_x", 0x21: "move_y", 0x25: "place_x", 0x26: "place_y",
}
# the steps after which the engine gives the object back to its owner's code until the next frame (0D5AC2: a
# command that returns 2, or a frame), which may give it another animation: what follows one may be no step
YIELDS = {0x01, 0x07, 0x08, 0x09}
GOES_ON = {0x01, 0x02, 0x04, 0x06, 0x07, 0x08, 0x09, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x13, 0x14, 0x15,
           0x20, 0x21, 0x25, 0x26}


@dataclass
class Step:
    address: int
    length: int                     # bytes
    kind: str                       # "frame" or a command's name
    command: int = -1
    mode: int = 0
    goes_on: bool = True            # whether the next step follows it
    yields: bool = False            # whether the object goes back to its owner's code after it
    targets: list = field(default_factory=list)       # animation steps it can go to
    definitions: list = field(default_factory=list)   # definitions it makes objects from
    functions: list = field(default_factory=list)     # code it calls
    tables: list = field(default_factory=list)        # (address, kind) of data its value reads


def u16(image, address):
    return struct.unpack_from(">H", image, address)[0]


def u32(image, address):
    return struct.unpack_from(">I", image, address)[0]


def read_step(image, address):
    """The step at 'address'; ValueError for a command the game stops on"""
    word = u16(image, address)
    if not word & 0x8000:
        return Step(address, 2, "frame", yields=True)
    command = (word >> 8) & 0x1F
    mode = word & 0x6000
    if command == 0x0D:
        if mode == 0x4000:
            return Step(address, 4, "frame_of", command, mode)
        table = u32(image, address + 2) & 0x0FFFFFFF
        return Step(address, 6, "frame_of", command, mode, tables=[(table, "frame table")])
    words = 1
    if command == 0x1F:
        command = word & 0xFF
        words += 1
    long_at = None
    if mode in (0x4000, 0x6000):
        long_at = address + 2 * words
        words += 2
    if command not in COMMAND_NAMES:
        raise ValueError(f"{address:06X}: command {command:02X} (word {word:04X}) stops the game")
    step = Step(address, 2 * words, COMMAND_NAMES[command], command, mode, command in GOES_ON, command in YIELDS)
    value_long = u32(image, long_at) if long_at is not None else None
    address_value = value_long & 0x0FFFFFFF if value_long is not None else None
    if mode == 0x6000:
        step.tables.append((address_value, f"value table, kind {value_long >> 28:X}"))
    if command in (0x03, 0x04):
        if mode == 0x4000:
            step.targets.append(address_value)
    elif command == 0x06:
        count = u16(image, address + 2 * words)
        entries = [u32(image, address + 2 * words + 2 + 4 * index) & 0xFFFFFF for index in range(count + 1)]
        step.targets.extend(entries)
        step.length += 2 + 4 * (count + 1)
    elif command == 0x0C:
        if mode == 0x4000:
            step.definitions.append(address_value)
        step.length += 4
    elif command == 0x0F and mode == 0:
        step.length += 2
    elif command == 0x10 and mode == 0x4000:
        step.functions.append(address_value)
    return step
