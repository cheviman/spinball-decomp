"""
Name:        spinball_compression.py
Description: Sonic the Hedgehog Spinball's two compressions, read as the game reads them: SSC (an LZSS) and C2 (an
             LZW); and their encoders, which give the cartridge's bytes back
Version:     0.1.0
Created:     13-11-2026
Modified:    19-11-2026
Author:      Sebastian Toyos

SSC, as 0D6B88 reads it (its arguments: the data, and the 8x8 tile of the VRAM it goes to, 32 bytes a tile):
  u16 the tiles it holds (the decoder skips it; the code that loads more after it adds it), then blocks: a byte of
  eight flags, the lowest first; a flag 1 is a byte as it is, a flag 0 a reference, two bytes L, H: the place
  (H & F0) << 4 | L of a 4 KB window (FF58D4), and (H & 0F) + 2 bytes copied from there on, one at a time (a copy
  can run over what it writes). Place 0 is the end. Every byte that comes out also goes into the window, at the
  next place: the first at 1, wrapping at 4 KB (the window is not cleared: a reference to a place this data has not
  written would read what was there before). The bytes go to the VDP's data port two at a time.
C2, as 0F5A7A reads it (0F3BB8 after a word 0 or less, to VRAM 0; 0F5A5E to the VRAM its first argument says):
  codes of 9 bits at first, the lowest bits first (each read as the three bytes from the one its first bit is in,
  the first the lowest, then masked with the word of 09BCD2 for its width: 1FF, 3FF, 7FF). 100 starts over: the
  next code is a byte as it is; 101 is the end; 0-FF a byte; from 102 on, the dictionary's strings (from FF54CC, 4
  bytes an entry: +1 the string's last byte, +2 the code of the rest). Each code after the first adds an entry, the
  previous code's string and the first byte of this one's (a code not in the dictionary yet is the previous string
  and its own first byte). When the next entry reaches 200 the codes take 10 bits, at 400 11 bits; there they
  stay (the dictionary would run on through RAM: the data starts over first). The bytes go to the VDP's data port
  two at a time.

The encoders give the cartridge's bytes back, every stream the game has (tools/extract_assets.py --check):
  SSC  the LZSS of Mark Nelson's "The Data Compression Book" (1991, lzss.c), its numbers as they are (a 12-bit
       place, a 4-bit length, break even at 1 byte, 17 bytes looked ahead, the first byte at place 1, place 0
       unused and the end), its binary tree kept the same way (one tree from the first byte on, a string as long
       as the one looked for takes the last place found, a whole match takes the node's place, a node deleted
       takes the last of its smaller ones), written as Okumura's LZSS writes it (a byte of flags, the lowest first,
       1 a byte as it is; a place's low byte, then its high four bits over the length less 2). The end is a
       reference to place 0, its length's four bits as found (the decoder does not read them): 0, but for the
       options' tiles at 0BDD2E, whose last two bytes are also the first cell of the options' brushes (0BDFBC:
       tile 1), so its end is 00 01.
  C2   the LZW everyone writes: the longest string the dictionary has, then a new entry, that string and the next
       byte; when the entry 7FF is taken, the next code is 100 and the dictionary starts over. It starts with 100
       and ends with 101; the last byte's bits after the end are 0. The codes are as wide as the decoder reads them.
"""
import struct

SSC_WINDOW = 0x1000
SSC_FIRST_PLACE = 1             # where the first byte goes in the window (place 0 is the end)
SSC_SHORTEST = 2                # a reference's bytes: (H & 0F) + 2
SSC_LONGEST = 17
C2_RESTART = 0x100
C2_END = 0x101
C2_FIRST_ENTRY = 0x102
C2_WIDTHS = ((0x200, 9), (0x400, 10), (None, 11))     # (the entry that makes the codes wider, the width)
C2_MASKS = 0x09BCD2             # the masks of the widths: 1FF, 3FF, 7FF


class SSCResult:
    def __init__(self):
        self.tiles = 0              # the header's word
        self.data = bytearray()
        self.size = 0               # the compressed bytes, header and end included
        self.unwritten = []         # (output position, window place) of the references to places not written yet


def ssc_decode(image, address):
    """The SSC data at 'address' as 0D6B88 reads it"""
    result = SSCResult()
    result.tiles = struct.unpack_from(">H", image, address)[0]
    at = address + 2
    written = set()             # the places this data has written
    window = [0] * SSC_WINDOW
    place = SSC_FIRST_PLACE
    out = result.data
    while True:
        flags = image[at]
        at += 1
        for _ in range(8):
            if flags & 1:
                value = image[at]
                at += 1
                out.append(value)
                window[place] = value
                written.add(place)
                place = (place + 1) % SSC_WINDOW
            else:
                low, high = image[at], image[at + 1]
                at += 2
                source = (high & 0xF0) << 4 | low
                if source == 0:
                    result.size = at - address
                    return result
                for _ in range((high & 0x0F) + SSC_SHORTEST):
                    if source not in written:
                        result.unwritten.append((len(out), source))
                    value = window[source]
                    out.append(value)
                    window[place] = value
                    written.add(place)
                    place = (place + 1) % SSC_WINDOW
                    source = (source + 1) % SSC_WINDOW
            flags >>= 1


class C2Result:
    def __init__(self):
        self.data = bytearray()
        self.size = 0               # the compressed bytes: up to the one the end code's last bit is in
        self.read_size = 0          # the bytes the decoder reads: up to the third of the end code's (0F5ABA-0F5AC6)
        self.codes = []             # the codes as read, for the encoders' check
        self.restarts = 0
        self.most_entries = 0       # the highest next entry the dictionary reached


def c2_decode(image, address):
    """The C2 data at 'address' (the codes, not the word before them) as 0F5A7A reads it"""
    result = C2Result()
    masks = [struct.unpack_from(">H", image, C2_MASKS + 2 * index)[0] for index in range(len(C2_WIDTHS))]
    bit = 0
    width_index = 0
    next_entry = C2_FIRST_ENTRY
    entries = {}
    previous = 0                # D7's low word: the previous code
    first = 0                   # A3: the first byte of the previous string

    def read():
        nonlocal bit
        offset = bit >> 3
        value = image[address + offset] | image[address + offset + 1] << 8 | image[address + offset + 2] << 16
        result.read_size = offset + 3
        code = (value >> (bit & 7)) & masks[width_index]
        bit += C2_WIDTHS[width_index][1]
        result.codes.append(code)
        return code

    def string(code):
        bytes_ = []
        while code > 0xFF:
            last, code = entries[code]
            bytes_.append(last)
        bytes_.append(code)
        return bytes_[::-1]

    while True:
        code = read()
        if code == C2_END:
            result.size = (bit + 7) >> 3
            return result
        if code == C2_RESTART:
            width_index, next_entry, entries = 0, C2_FIRST_ENTRY, {}
            result.restarts += 1
            code = read()
            previous = first = code
            result.data.append(code & 0xFF)
            continue
        if code >= next_entry:
            text = string(previous) + [first]
        else:
            text = string(code)
        result.data.extend(text)
        entries[next_entry] = (text[0], previous)
        first = text[0]
        next_entry += 1
        result.most_entries = max(result.most_entries, next_entry)
        previous = code
        limit = C2_WIDTHS[width_index][0]
        if limit is not None and next_entry >= limit:
            width_index += 1


# ---- the encoders ----

SSC_LOOK_AHEAD = SSC_LONGEST            # the bytes the encoder looks ahead (lzss.c's LOOK_AHEAD_SIZE)
SSC_UNUSED = 0                          # no node (lzss.c's UNUSED, and the decoder's end)
C2_LAST_ENTRY = 0x7FF


class _SSCTree:
    """lzss.c's binary tree of the strings the window holds: one node a place, the root at SSC_WINDOW"""

    def __init__(self, window):
        self.window = window
        size = SSC_WINDOW + 1
        self.parent, self.smaller, self.larger = [SSC_UNUSED] * size, [SSC_UNUSED] * size, [SSC_UNUSED] * size

    def start(self, node):
        self.larger[SSC_WINDOW] = node
        self.parent[node] = SSC_WINDOW
        self.larger[node] = self.smaller[node] = SSC_UNUSED

    def contract(self, old, new):
        parent = self.parent[old]
        self.parent[new] = parent
        if self.larger[parent] == old:
            self.larger[parent] = new
        else:
            self.smaller[parent] = new
        self.parent[old] = SSC_UNUSED

    def replace(self, old, new):
        parent = self.parent[old]
        if self.smaller[parent] == old:
            self.smaller[parent] = new
        else:
            self.larger[parent] = new
        self.parent[new], self.smaller[new], self.larger[new] = parent, self.smaller[old], self.larger[old]
        self.parent[self.smaller[new]] = new
        self.parent[self.larger[new]] = new
        self.parent[old] = SSC_UNUSED

    def delete(self, node):
        if self.parent[node] == SSC_UNUSED:
            return
        if self.larger[node] == SSC_UNUSED:
            self.contract(node, self.smaller[node])
        elif self.smaller[node] == SSC_UNUSED:
            self.contract(node, self.larger[node])
        else:
            replacement = self.smaller[node]
            while self.larger[replacement] != SSC_UNUSED:
                replacement = self.larger[replacement]
            self.delete(replacement)
            self.replace(node, replacement)

    def add(self, node):
        """(length, place) of the longest string the tree has like the one at 'node' (the last of the longest),
        putting 'node' in"""
        if node == SSC_UNUSED:
            return 0, 0
        window = self.window
        test = self.larger[SSC_WINDOW]
        length = place = 0
        while True:
            same = 0
            delta = 0
            while same < SSC_LOOK_AHEAD:
                delta = window[(node + same) % SSC_WINDOW] - window[(test + same) % SSC_WINDOW]
                if delta:
                    break
                same += 1
            if same >= length:
                length, place = same, test
                if length >= SSC_LOOK_AHEAD:
                    self.replace(test, node)
                    return length, place
            children = self.larger if delta >= 0 else self.smaller
            if children[test] == SSC_UNUSED:
                children[test] = node
                self.parent[node] = test
                self.larger[node] = self.smaller[node] = SSC_UNUSED
                return length, place
            test = children[test]


def ssc_encode(data, tiles, end_length=0):
    """The SSC bytes of 'data': the word 'tiles', the blocks, the end (place 0, its length's bits 'end_length')"""
    window = bytearray(SSC_WINDOW)
    tree = _SSCTree(window)
    out = bytearray(struct.pack(">H", tiles))
    group, bit = bytearray([0]), 1

    def token(literal, *values):
        nonlocal group, bit
        if literal:
            group[0] |= bit
        group += bytes(values)
        bit = (bit << 1) & 0xFF
        if not bit:
            out.extend(group)
            group, bit = bytearray([0]), 1

    current = SSC_FIRST_PLACE
    taken = min(SSC_LOOK_AHEAD, len(data))
    window[current:current + taken] = data[:taken]
    ahead = taken
    tree.start(current)
    length = place = 0
    while ahead > 0:
        length = min(length, ahead)
        if length < SSC_SHORTEST:
            count = 1
            token(True, window[current])
        else:
            count = length
            token(False, place & 0xFF, (place >> 4) & 0xF0 | (length - SSC_SHORTEST))
        for _ in range(count):
            incoming = (current + SSC_LOOK_AHEAD) % SSC_WINDOW
            tree.delete(incoming)
            if taken < len(data):
                window[incoming] = data[taken]
                taken += 1
            else:
                ahead -= 1
            current = (current + 1) % SSC_WINDOW
            if ahead:
                length, place = tree.add(current)
    token(False, 0, end_length & 0x0F)
    if bit != 1:
        out.extend(group)
    return bytes(out)


def c2_codes(data):
    """The codes of 'data': 100, the longest strings the dictionary has, 101"""
    codes = [C2_RESTART]
    entries = {}
    next_entry = C2_FIRST_ENTRY
    current = data[0]
    for value in data[1:]:
        longer = entries.get((current, value))
        if longer is not None:
            current = longer
            continue
        codes.append(current)
        if next_entry <= C2_LAST_ENTRY:
            entries[(current, value)] = next_entry
            next_entry += 1
        else:
            codes.append(C2_RESTART)
            entries, next_entry = {}, C2_FIRST_ENTRY
        current = value
    codes += [current, C2_END]
    return codes


def c2_encode(data):
    """The C2 bytes of 'data': its codes, each as wide as the decoder reads it, the lowest bits first"""
    packed = bits = 0
    width_index, next_entry, after_restart = 0, C2_FIRST_ENTRY, False
    for code in c2_codes(data):
        packed |= code << bits
        bits += C2_WIDTHS[width_index][1]
        if code == C2_RESTART:
            width_index, next_entry, after_restart = 0, C2_FIRST_ENTRY, True
        elif after_restart:
            after_restart = False
        elif code != C2_END:
            next_entry += 1
            limit = C2_WIDTHS[width_index][0]
            if limit is not None and next_entry >= limit:
                width_index += 1
    return packed.to_bytes((bits + 7) // 8, "little")
