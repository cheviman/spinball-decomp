"""
Name:        spinball_levels.py
Description: Sonic the Hedgehog Spinball's tables' planes: their maps of brushes and the brushes, read as the game
             draws them, as text and back byte for byte
Version:     0.1.0
Created:     13-11-2026
Modified:    13-11-2026
Author:      Sebastian Toyos

A table's two planes are drawn into the VDP's planes (A at C000, B at E000, 64x32 cells that wrap) a row
(0D8D0E) or a column (0D8E12) at a time, from a map and its brushes (FF3CAC and FF58CC: the tables BFC00 and BFC20
for plane A, BFC10 and BFC30 for plane B, by the table: 0D4FC0-0D5056):
  map      the table's width in brushes (0D8D04, by the table: 40, 48, 46, 56) by its height (BFC70's, in pixels,
           over 32: 64), a row after the other, a word a brush: bits 0-10 the brush, bit 11 mirrored left to
           right, bit 12 top to bottom (the other bits are 0 in every map). Showdown's background has 48 rows: its
           collision begins after them.
  brushes  32x32 pixels each, 4x4 cells of the plane, 32 bytes: 4 rows of 4 words, the VDP's cell (bit 15 the
           priority, 13-14 the palette line, 12 and 11 mirrored, 0-10 the tile) but for the tile, which counts from
           the plane's first (plane B's tiles follow plane A's: 0D5038-0D5042 add their count, FFAD1C). A mirrored
           brush's cells come mirrored, and their mirror bits flipped (0D8DBA-0D8E04).
The text forms (tools/extract_assets.py): a map is a CSV of its rows, each brush's number followed by h and v when
mirrored; brushes are a line each, "N:" then its 16 cells, a row of four after the other with "|" between, each
cell as PALETTE:TILE then h, v (mirrored) and ! (in front).

A table's collision (the table BFC40 by the level, kept in FFF1F4; read by 0DC3DE, 0DCB.., 0E1D10 and the tests
0DB900, 0DBC60):
  sectors  128x128 pixels each, 16 a row (0DC408 "lsl.l #4": a row is 16 whatever the table's width), as many
           rows as the table's height takes: a word each, the place of its list in words from the collision's
           start (0DC40E-0DC43A). Every sector has its own list, and they follow each other in the sectors'
           order, so the words are what the lists' sizes give.
  a list   a word, how many, then that many records of 12 bytes (0DC60E-0DC61A):
             +0 x0, +2 y0, +4 x1, +6 y1   a segment (0DC512-0DC58E: its box against the object's; 0DB900 the test)
                                          or, with bit 15 of the flags, a circle: x, y, its radius at +4 (0DBC60:
                                          the distance less the radius); +6 kept as it is (mostly 0)
             +8 flags                     bit 15 a circle; bits 9-14 what touching it does (0DC66A-0DC69A: 400 a
                                          game object's, the one +A numbers, from FF784C; 4000, 800, 1000 others;
                                          200 sets FF3FFC's byte +A, 0DC5CE; 2000 calls 0E1BBE with +A, 0DC4C2);
                                          bits 0-3 one way only, against the object's speed (0DC4EE-0DC502); bit 7
                                          preferred (0DCD1A-0DCD30)
             +A a number                  the game object or the flag the record is for
The text form: per sector "sector X,Y" and a line a record, "X0 Y0 X1 Y1 FLAGS NUMBER" (the flags in hex).

The flippers (0DDE6C-0DDF58 sets them up, 0DE2xx-0DE6xx their collision):
  a table's  C08BE by the level (0DDEE0), as many as C08EE says (0DDEC8: FF58C4), 10 bytes each, copied to FF74E8
             on: a long the game fills with its animated object (0 in the cartridge), x, y, and flags its
             animated object takes (4000: mirrored), made from the definition C08CE gives by the level (0DDF18)
  shapes     a list of records as a sector's, by the flipper's position (its animated object's byte 2F, 0-3): the
             table C0A86 for one side, C0A96 for the other (0DE53C, 0DE530); each, two circles and two segments
  boxes      10 bytes by the position, from C0A9C (0DE336: x0, y0, x1, y1 and a word): the first position's
             would fall on the end of the table C0A96, so the boxes are the three after it (C0AA6-C0AC3)
"""
import math
import struct

MAP_WIDTHS = 0x0D8D04           # the tables' widths in brushes, a word each (0D8D34, 0D8E2A "lea ($d8d04,PC), A2")
BRUSH = 4                       # cells a side
BRUSH_BYTES = 2 * BRUSH * BRUSH
BRUSH_PIXELS = 8 * BRUSH
BRUSH_NUMBER = 0x07FF
MIRROR_X = 0x0800
MIRROR_Y = 0x1000
PRIORITY = 0x8000


def read_map(image, address, width, rows):
    """[[word]] of a map"""
    words = struct.unpack_from(f">{width * rows}H", image, address)
    return [list(words[row * width:(row + 1) * width]) for row in range(rows)]


def read_brushes(image, address, count):
    """[[16 words]] of brushes"""
    words = struct.unpack_from(f">{count * BRUSH * BRUSH}H", image, address)
    return [list(words[index * 16:(index + 1) * 16]) for index in range(count)]


def map_bytes(rows):
    return b"".join(struct.pack(f">{len(row)}H", *row) for row in rows)


def brushes_bytes(brushes):
    return b"".join(struct.pack(">16H", *cells) for cells in brushes)


def plane_cell(rows, brushes, x, y, first_tile=0):
    """The VDP's cell the drawers put at cell (x, y) of the plane"""
    word = rows[y // BRUSH][x // BRUSH]
    column, row = x % BRUSH, y % BRUSH
    if word & MIRROR_X:
        column = BRUSH - 1 - column
    if word & MIRROR_Y:
        row = BRUSH - 1 - row
    return ((brushes[word & BRUSH_NUMBER][row * BRUSH + column] + first_tile) & 0xFFFF) ^ (word & (MIRROR_X | MIRROR_Y))


def mirrors(word):
    return ("h" if word & MIRROR_X else "") + ("v" if word & MIRROR_Y else "")


def map_text(rows):
    """A map as CSV"""
    for row in rows:
        for word in row:
            if word & ~(BRUSH_NUMBER | MIRROR_X | MIRROR_Y):
                raise ValueError(f"a map word {word:04X} with bits the text has no place for")
    return "".join(",".join(f"{word & BRUSH_NUMBER}{mirrors(word)}" for word in row) + "\n" for row in rows)


def parse_map_text(text):
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        row = []
        for item in line.split(","):
            item = item.strip()
            number = item.rstrip("hv")
            flags = item[len(number):]
            row.append(int(number) | (MIRROR_X if "h" in flags else 0) | (MIRROR_Y if "v" in flags else 0))
        rows.append(row)
    return rows


def cell_text(word):
    return f"{word >> 13 & 3}:{word & BRUSH_NUMBER}{mirrors(word)}{'!' if word & PRIORITY else ''}"


def parse_cell(item):
    palette, rest = item.split(":")
    front = rest.endswith("!")
    rest = rest.rstrip("!")
    number = rest.rstrip("hv")
    flags = rest[len(number):]
    return (PRIORITY if front else 0) | int(palette) << 13 | (MIRROR_Y if "v" in flags else 0) \
        | (MIRROR_X if "h" in flags else 0) | int(number)


def brushes_text(brushes):
    lines = []
    for index, cells in enumerate(brushes):
        rows = [" ".join(cell_text(cells[row * BRUSH + column]) for column in range(BRUSH)) for row in range(BRUSH)]
        lines.append(f"{index}: " + " | ".join(rows))
    return "\n".join(lines) + "\n"


def parse_brushes_text(text):
    brushes = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        number, cells = line.split(":", 1)
        if int(number) != len(brushes):
            raise ValueError(f"brush {number} out of order (expected {len(brushes)})")
        brushes.append([parse_cell(item) for item in cells.replace("|", " ").split()])
    return brushes


def plane_pens(rows, brushes, tiles):
    """A picture of a plane, rows of colours: each cell's tile from 'tiles' (the plane's own, 32 bytes each),
    mirrored as the cell says, each pen with the cell's palette line over it (line * 16 + pen: 0-63; the
    priority is not in a picture)"""
    width, height = len(rows[0]) * BRUSH * 8, len(rows) * BRUSH * 8
    count = len(tiles) // 32
    picture = [[0] * width for _ in range(height)]
    for y in range(len(rows) * BRUSH):
        for x in range(len(rows[0]) * BRUSH):
            cell = plane_cell(rows, brushes, x, y)
            tile = cell & BRUSH_NUMBER
            if tile >= count:
                continue
            data = tiles[32 * tile:32 * tile + 32]
            for row in range(8):
                source = 7 - row if cell & MIRROR_Y else row
                line = [16 * (cell >> 13 & 3) + pen for byte in data[4 * source:4 * source + 4]
                        for pen in (byte >> 4, byte & 15)]
                if cell & MIRROR_X:
                    line.reverse()
                picture[8 * y + row][8 * x:8 * x + 8] = line
    return picture


# ---- the collision ----

SECTOR = 128                    # pixels a side
SECTORS_ACROSS = 16             # a row of sectors, whatever the table's width
RECORD_BYTES = 12
CIRCLE = 0x8000


def read_list(image, address):
    """A list of records: ([(x0, y0, x1, y1, flags, number)], its size in bytes)"""
    count = struct.unpack_from(">H", image, address)[0]
    records = [struct.unpack_from(">hhhhHH", image, address + 2 + RECORD_BYTES * index) for index in range(count)]
    return records, 2 + RECORD_BYTES * count


def list_bytes(records):
    return struct.pack(">H", len(records)) + b"".join(struct.pack(">hhhhHH", *record) for record in records)


def read_collision(image, address, rows):
    """The sectors' lists, [[(x0, y0, x1, y1, flags, number)]] in the sectors' order, and the size in bytes;
    ValueError when the words do not give the lists one after the other"""
    count = SECTORS_ACROSS * rows
    places = struct.unpack_from(f">{count}H", image, address)
    lists, expected = [], count
    for sector, place in enumerate(places):
        if place != expected:
            raise ValueError(f"sector {sector}: its list at word {place:X}, not at {expected:X}")
        records, size = read_list(image, address + 2 * place)
        lists.append(records)
        expected += size // 2
    return lists, 2 * expected


def collision_bytes(lists):
    places, body, place = [], bytearray(), len(lists)
    for records in lists:
        places.append(place)
        body += list_bytes(records)
        place += 1 + len(records) * RECORD_BYTES // 2
    return struct.pack(f">{len(places)}H", *places) + bytes(body)


def records_text(records):
    return [f"  {x0} {y0} {x1} {y1} {flags:04X} {number}" for x0, y0, x1, y1, flags, number in records]


def parse_record(words):
    x0, y0, x1, y1 = (int(value) for value in words[:4])
    return x0, y0, x1, y1, int(words[4], 16), int(words[5])


def collision_text(lists):
    lines = []
    for sector, records in enumerate(lists):
        lines.append(f"sector {sector % SECTORS_ACROSS},{sector // SECTORS_ACROSS}")
        lines += records_text(records)
    return "\n".join(lines) + "\n"


def parse_collision_text(text):
    lists = []
    for line in text.splitlines():
        words = line.split("#", 1)[0].split()
        if not words:
            continue
        if words[0] == "sector":
            x, y = (int(value) for value in words[1].split(","))
            if y * SECTORS_ACROSS + x != len(lists):
                raise ValueError(f"sector {words[1]} out of order")
            lists.append([])
            continue
        lists[-1].append(parse_record(words))
    return lists


def collision_pens(lists, width, height):
    """A picture of the collision, rows of pens: segments and circles, 15 the ones that only stop the ball, 10
    the ones that do something when touched (bits 9-14), 12 the one-way ones (bits 0-3)"""
    picture = [[0] * width for _ in range(height)]

    def plot(x, y, pen):
        if 0 <= x < width and 0 <= y < height:
            picture[y][x] = pen

    for records in lists:
        for x0, y0, x1, y1, flags, _ in records:
            pen = 10 if flags & 0x7E00 else 12 if flags & 0x000F else 15
            if flags & CIRCLE:
                radius = max(1, x1)
                for step in range(8 * radius):
                    angle = 2 * math.pi * step / (8 * radius)
                    plot(round(x0 + radius * math.cos(angle)), round(y0 + radius * math.sin(angle)), pen)
                continue
            steps = max(abs(x1 - x0), abs(y1 - y0), 1)
            for step in range(steps + 1):
                plot(x0 + round((x1 - x0) * step / steps), y0 + round((y1 - y0) * step / steps), pen)
    return picture


# ---- the flippers ----

FLIPPER_BYTES = 10              # a long the game fills (0 in the cartridge), x, y, flags
FLIPPER_BOX_BYTES = 10          # x0, y0, x1, y1 and a word


def read_flippers(image, address, count):
    """[(x, y, flags)] of a table's flippers; ValueError if a long the game fills is not 0"""
    flippers = []
    for index in range(count):
        filled, x, y, flags = struct.unpack_from(">IhhH", image, address + FLIPPER_BYTES * index)
        if filled:
            raise ValueError(f"flipper {index} at {address + FLIPPER_BYTES * index:06X} has {filled:08X} in its long")
        flippers.append((x, y, flags))
    return flippers


def flippers_bytes(flippers):
    return b"".join(struct.pack(">IhhH", 0, x, y, flags) for x, y, flags in flippers)


def read_box(image, address):
    return struct.unpack_from(">hhhhh", image, address)


def box_bytes(box):
    return struct.pack(">hhhhh", *box)
