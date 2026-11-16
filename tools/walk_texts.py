"""
Name:        walk_texts.py
Description: Sonic the Hedgehog Spinball's texts, walked from the code that hands them to the functions that read
             them (for tools/data_walk.py)
Version:     0.1.0
Created:     13-11-2026
Modified:    15-11-2026
Author:      Sebastian Toyos

  readers        a function reads one of its arguments as a text when its prologue loads it into An and the
                 function reads "move.b (An)+" with An as it came (0DE774, the text's width: argument 0;
                 0D6A50, the game's sprintf: argument 1, its format); and so does one that passes its own
                 argument on, unchanged, as a reader's text (0DE9D4, which draws a text: argument 5; 0DE816,
                 0DE87A, 0F641C, 0FF64A). A call through a register counts as a call of the function the code
                 put in it (walk_patterns.call_target()).
  tables         a table of texts the code takes a text argument from ("move.l (A0,Dn.w), -(A7)" after "movea.l
                 #TABLE, A0", or "(Ap)+" from it): its entries while each is a text, up to the next place the code
                 names (the options' texts D3B54, the credits' D3C04); and the bytes that index one (the credits'
                 lines, D3BA0).
  formats        a reader that compares the text's bytes with '%' and 's' (0D6A50) takes a format: each "%"
                 conversion after it takes the next argument, and a "%s" one takes a text.
  texts          what the calls of the readers get as those arguments ("pea TEXT.l", back through the branches
                 that come in among the pushes): bytes up to a 0, which ends them; one that ends on an odd address
                 is followed by FF, so the next starts on a word. (Texts the code copies whole into a local array,
                 "RINGS BONUS" at 0D4AAC, are walk_patterns' copied blocks.)
  big font       the messages' characters drawn in tiles (0DE8EC, 0DED78 and the others that draw a message): a
                 character doubled ("add.l Dn, Dn"), "movea.l #OFFSETS, An; move.w (An,Dn.l)" its glyph's offset
                 in words, then "movea.l #GLYPHS, Am; adda.l" twice that: the glyph, whose rows of tile words the
                 code reads 8 bytes apart. OFFSETS has a word for each of the 128 characters (07E45A), and GLYPHS
                 as many glyphs as the largest offset reaches, each as big as the step between the offsets (16
                 words: 07DE1A, 50 glyphs of four rows of four, the fourth all C000, which the code does not read).
"""
import math
import struct
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]
from walk_patterns import long_at, writes  # noqa: E402

PERCENT, STRING = 0x25, 0x73        # what a format reader compares the text's bytes with: '%' and 's'
TEXT_PAD = 0xFF                     # what evens the place after a text of an odd length
CHARACTERS = 128                    # the font's: the texts' bytes are 0-127
MAX_TEXT = 256                      # the longest a text of a table can be


def read_text(image, address):
    """The bytes of the text at 'address', its 0 included"""
    end = image.index(0, address)
    return bytes(image[address:end + 1])


def conversions(text):
    """The kind of each "%" conversion of a format, in order ("%%" is none): 's' a text, another letter a number"""
    kinds, at = [], 0
    while at < len(text) - 1:
        if text[at] == PERCENT:
            if text[at + 1] != PERCENT:
                kinds.append(chr(text[at + 1]))
            at += 2
        else:
            at += 1
    return kinds


class TextsWalk:
    """The functions that read texts, and the texts their calls get"""

    def init_texts(self):
        self.text_readers = {}          # {function: {argument: how it was found}}
        self.formats = {}               # {function: its format's argument}
        self.texts = {}                 # {address: (size in bytes, how it was found)}
        self.char_widths = {}           # {address: (characters, how it was found)}
        self.text_tables_found = {}     # {address: (entries, how it was found)}
        self.text_indices = {}          # {address: (size, how it was found)}
        self.glyph_offsets = {}         # {address: (glyphs, how it was found)}: the big font's, by character
        self.glyphs = {}                # {address: (glyphs, bytes each, how it was found)}

    def function_body(self, function):
        """The positions of a function's instructions, up to the next function"""
        position = self.position_of.get(function)
        if position is None:
            return []
        found = [position]
        position += 1
        while position < len(self.ordered) and self.ordered[position][0] not in self.analysis.functions:
            found.append(position)
            position += 1
        return found

    def find_text_readers(self):
        for function in sorted(self.analysis.functions):
            after, arguments = self.prologue(function)
            if after is None or not arguments:
                continue
            body = self.function_body(function)
            for position in body:
                instruction = self.ordered[position][1]
                operands = instruction.operands
                if instruction.mnemonic == "move" and instruction.size == "b" and operands \
                        and operands[0].mode == "postinc" and operands[0].reg in arguments \
                        and not any(writes(self.ordered[step][1], operands[0].reg) for step in range(after, position)):
                    argument = arguments[operands[0].reg]
                    self.text_readers.setdefault(function, {})[argument] = f"reads it at {instruction.address:06X}"
                    compared = {step.operands[0].value for step in (self.ordered[at][1] for at in body)
                                if step.mnemonic == "cmpi" and step.size == "b"
                                and step.operands[0].mode == "immediate"}
                    if {PERCENT, STRING} <= compared:
                        self.formats[function] = argument
        grown = True
        while grown:
            grown = False
            for position, (address, instruction) in enumerate(self.ordered):
                target = self.call_target(position) if instruction.flow == "call" else None
                if target not in self.text_readers:
                    continue
                for argument in list(self.text_readers[target]):
                    pushes = self.pushes(position, argument)
                    if not pushes or any(push.mnemonic != "move" or push.operands[0].mode not in ("areg", "dreg")
                                         for push in pushes):
                        continue
                    registers = {push.operands[0].reg for push in pushes}
                    function = self.function_of(address)
                    if len(registers) != 1 or function is None:
                        continue
                    register = registers.pop()
                    after, arguments = self.prologue(function)
                    if after is None or register not in arguments \
                            or any(writes(self.ordered[step][1], register) for step in range(after, position)):
                        continue
                    if arguments[register] not in self.text_readers.get(function, {}):
                        self.text_readers.setdefault(function, {})[arguments[register]] = \
                            f"passes it on to {target:06X} at {address:06X}"
                        grown = True

    def walk_texts(self):
        self.find_text_readers()
        self.texts_read_in_place()
        self.big_font()
        for position, (address, instruction) in enumerate(self.ordered):
            target = self.call_target(position) if instruction.flow == "call" else None
            if target not in self.text_readers:
                continue
            for argument in self.text_readers[target]:
                for text, _ in self.passed(position, argument):
                    self.add_text(text, f"argument {argument} of {target:06X} at {address:06X}")
                    if self.formats.get(target) == argument:
                        for index, kind in enumerate(conversions(read_text(self.image, text))):
                            if kind == "s":
                                for value, _ in self.passed(position, argument + 1 + index):
                                    self.add_text(value, f"a %s of the format {text:06X} at {address:06X}")
        self.text_tables()

    def texts_read_in_place(self):
        """Texts a function reads itself: "movea.l #TEXT, An" (or "lea TEXT, An"), then "move.b (An)+" up to a
        0 ("bne" back) with An as it was put; and the widths of the font's characters, the table the text's
        width (the reader of argument 0 that adds a byte of a table by each character: 0DE774, C1430) indexes by
        each character, 128 of them (the texts' bytes are 0-127)"""
        for position, (address, instruction) in enumerate(self.ordered):
            operands = instruction.operands
            if len(operands) != 2 or operands[1].mode != "areg" or not (
                    (instruction.mnemonic == "movea" and operands[0].mode == "immediate")
                    or (instruction.mnemonic == "lea" and operands[0].mode == "abs_long")):
                continue
            register = operands[1].reg
            for later in range(position + 1, min(position + 4, len(self.ordered) - 1)):
                step, after = self.ordered[later][1], self.ordered[later + 1][1]
                if step.mnemonic == "move" and step.size == "b" and step.operands[0].mode == "postinc" \
                        and step.operands[0].reg == register and after.mnemonic == "bcc" \
                        and after.condition == "ne" and after.target == step.address:
                    self.add_text(operands[0].value & 0xFFFFFF, f"read in place at {step.address:06X}")
                    break
                if writes(step, register):
                    break
        for function, arguments in self.text_readers.items():
            if 0 not in arguments or not arguments[0].startswith("reads"):
                continue
            for position in self.function_body(function):
                instruction = self.ordered[position][1]
                operands = instruction.operands
                following = self.ordered[position + 1][1] if position + 1 < len(self.ordered) else None
                if instruction.mnemonic == "movea" and operands[0].mode == "immediate" and following is not None \
                        and following.mnemonic == "move" and following.size == "b" \
                        and following.operands[0].mode == "index":
                    self.char_widths[operands[0].value & 0xFFFFFF] = (CHARACTERS, f"read by {function:06X}")
        if any(byte >= CHARACTERS for address, (size, _) in self.texts.items()
               for byte in self.image[address:address + size]):
            raise SystemExit("a text has a byte past the font's characters")

    def big_font(self):
        """The messages' font of tiles: "add.l Dn, Dn; movea.l #OFFSETS, An; move.w (An,Dn.l)", then "movea.l
        #GLYPHS, Am; adda.l" in the function: a word for each character, and the glyphs the words reach"""
        for position, (address, instruction) in enumerate(self.ordered[1:-1], 1):
            operands = instruction.operands
            following, before = self.ordered[position + 1][1], self.ordered[position - 1][1]
            if instruction.mnemonic != "movea" or operands[0].mode != "immediate" or following.mnemonic != "move" \
                    or following.size != "w" or following.operands[0].mode != "index" or following.operands[0].disp \
                    or following.operands[0].reg != operands[1].reg or before.mnemonic != "add" \
                    or before.operands[0].mode != "dreg" or before.operands[0].reg != following.operands[0].index \
                    or before.operands[1].reg != before.operands[0].reg:
                continue
            offsets = operands[0].value & 0xFFFFFF
            if offsets + 2 * CHARACTERS > len(self.image):
                continue
            function = self.function_of(address)
            for later in range(position + 2, min(position + 40, len(self.ordered) - 1)):
                if self.ordered[later][0] in self.analysis.functions:
                    break
                load, add = self.ordered[later][1], self.ordered[later + 1][1]
                if load.mnemonic == "movea" and load.operands[0].mode == "immediate" and add.mnemonic == "adda" \
                        and add.operands[1].reg == load.operands[1].reg \
                        and load.operands[0].value & 0xFFFFFF < offsets:
                    self.add_big_font(offsets, load.operands[0].value & 0xFFFFFF,
                                      f"read by {function:06X} ({address:06X}, {load.address:06X})")
                    break

    def add_big_font(self, offsets, glyphs, found):
        words = [struct.unpack_from(">H", self.image, offsets + 2 * character)[0] for character in range(CHARACTERS)]
        step = 0
        for word in words:
            step = math.gcd(step, word)
        if not step or glyphs + 2 * max(words) + 2 * step > offsets:
            raise SystemExit(f"{offsets:06X}: no big font's offsets for {glyphs:06X} ({found})")
        self.glyph_offsets.setdefault(offsets, (CHARACTERS, found))
        self.glyphs.setdefault(glyphs, (max(words) // step + 1, 2 * step, found))

    def text_tables(self):
        """Tables of texts: what a reader's call gets as its text is "move.l (A0,Dn.w), -(A7)" after "movea.l
        #TABLE, A0", or "move.l (Ap)+, -(A7)" with Ap from "movea.l #TABLE, A0; lea (A0,Dx.w), Ap"; the
        table's entries go on while each is a text, up to the next place the code names. A table whose bytes,
        read "move.b (Ap)+" a few instructions before, give the index is the table's indices (the credits' lines,
        D3BA0): up to the next place the code names, each byte an entry of the texts' table"""
        for position, (address, instruction) in enumerate(self.ordered):
            target = self.call_target(position) if instruction.flow == "call" else None
            for argument in self.text_readers.get(target, {}):
                for push in self.pushes(position, argument) or ():
                    table, at = self.text_table_of(push)
                    if table is None or table in self.text_tables_found:
                        continue
                    stop = min((place for place in self.anchors if place > table), default=len(self.image))
                    entries = 0
                    while table + 4 * entries + 4 <= stop \
                            and self.is_text(long_at(self.image, table + 4 * entries)):
                        self.add_text(long_at(self.image, table + 4 * entries),
                                      f"entry {entries} of the texts' table {table:06X}")
                        entries += 1
                    if not entries:
                        continue
                    self.text_tables_found[table] = (entries, f"its texts go to {target:06X} at {address:06X}")
                    self.text_indices_for(at, table, entries)

    def text_table_of(self, push):
        """(the table, the position of its "movea.l #TABLE") a push takes a text from, or (None, None)"""
        source = push.operands[0]
        at = self.position_of[push.address]
        if push.mnemonic != "move" or push.size != "l":
            return None, None
        if source.mode == "index":
            loader = self.ordered[at - 1][1]
            if loader.mnemonic == "movea" and loader.operands[0].mode == "immediate" \
                    and loader.operands[1].reg == source.reg:
                return loader.operands[0].value & 0xFFFFFF, at - 1
        if source.mode == "postinc":
            for back in range(at - 1, max(at - 12, 1), -1):
                lea, loader = self.ordered[back][1], self.ordered[back - 1][1]
                if lea.mnemonic == "lea" and lea.operands[0].mode == "index" and lea.operands[1].reg == source.reg \
                        and loader.mnemonic == "movea" and loader.operands[0].mode == "immediate" \
                        and loader.operands[1].reg == lea.operands[0].reg:
                    return loader.operands[0].value & 0xFFFFFF, back - 1
        return None, None

    def text_indices_for(self, at, table, entries):
        """The bytes that index a texts' table, if the code reads them "move.b (Ap)+" just before its movea"""
        for back in range(at - 1, max(at - 6, 1), -1):
            read = self.ordered[back][1]
            if read.mnemonic == "move" and read.size == "b" and read.operands[0].mode == "postinc":
                pointer = read.operands[0].reg
                for earlier in range(back - 1, max(back - 12, 1), -1):
                    lea, loader = self.ordered[earlier][1], self.ordered[earlier - 1][1]
                    if lea.mnemonic == "lea" and lea.operands[0].mode == "index" and lea.operands[1].reg == pointer \
                            and loader.mnemonic == "movea" and loader.operands[0].mode == "immediate":
                        indices = loader.operands[0].value & 0xFFFFFF
                        stop = min((place for place in self.anchors if place > indices), default=len(self.image))
                        if all(byte < entries for byte in self.image[indices:stop]):
                            self.text_indices[indices] = (stop - indices, f"index the texts' table {table:06X}")
                        return
                return

    def is_text(self, address):
        """Whether the bytes at 'address' read as a text: the font's characters up to a 0, within MAX_TEXT"""
        if not 0 < address < len(self.image):
            return False
        end = self.image.find(0, address, address + MAX_TEXT)
        return end >= address and all(0x20 <= byte < CHARACTERS for byte in self.image[address:end])

    def add_text(self, address, found):
        if address in self.texts or not 0 <= address < len(self.image):
            return
        self.texts[address] = (len(read_text(self.image, address)), found)

    def spans_texts(self, found):
        """Each text, and the FF after one that ends on an odd address: the next starts on a word"""
        for address, (size, _) in self.texts.items():
            stop = address + size
            if stop & 1 and stop < len(self.image) and self.image[stop] == TEXT_PAD:
                stop += 1
            found.setdefault(address, (stop, "text"))
        for table, (characters, _) in self.char_widths.items():
            found.setdefault(table, (table + characters, "character widths"))
        for table, (entries, _) in self.text_tables_found.items():
            found.setdefault(table, (table + 4 * entries, "texts' table"))
        for table, (size, _) in self.text_indices.items():
            found.setdefault(table, (table + size, "text indices"))
        for table, (characters, _) in self.glyph_offsets.items():
            found.setdefault(table, (table + 2 * characters, "big font's offsets"))
        for address, (count, size, _) in self.glyphs.items():
            found.setdefault(address, (address + count * size, "big font"))

