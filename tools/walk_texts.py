"""
Name:        walk_texts.py
Description: Sonic the Hedgehog Spinball's texts, walked from the code that hands them to the functions that read
             them (for tools/data_walk.py)
Version:     0.1.0
Created:     13-11-2026
Modified:    13-11-2026
Author:      Sebastian Toyos

  readers        a function reads one of its arguments as a text when its prologue loads it into An and the
                 function reads "move.b (An)+" with An as it came (0DE774, the text's width: argument 0;
                 0D6A50, the game's sprintf: argument 1, its format); and so does one that passes its own
                 argument on, unchanged, as a reader's text (0DE9D4, which draws a text: argument 5; 0DE816,
                 0DE87A, 0F641C, 0FF64A). A call through a register counts as a call of the function the code
                 put in it (walk_patterns.call_target()).
  formats        a reader that compares the text's bytes with '%' and 's' (0D6A50) takes a format: each "%"
                 conversion after it takes the next argument, and a "%s" one takes a text.
  texts          what the calls of the readers get as those arguments ("pea TEXT.l", back through the branches
                 that come in among the pushes): bytes up to a 0, which ends them; one that ends on an odd address
                 is followed by FF, so the next starts on a word. (Texts the code copies whole into a local array,
                 "RINGS BONUS" at 0D4AAC, are walk_patterns' copied blocks.)
"""
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]
from walk_patterns import writes  # noqa: E402

PERCENT, STRING = 0x25, 0x73        # what a format reader compares the text's bytes with: '%' and 's'
TEXT_PAD = 0xFF                     # what evens the place after a text of an odd length
CHARACTERS = 128                    # the font's: the texts' bytes are 0-127


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

