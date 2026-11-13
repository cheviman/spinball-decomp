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
"""
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
    """A picture of a plane, rows of pens: each cell's tile from 'tiles' (the plane's own, 32 bytes each),
    mirrored as the cell says (its palette line and priority are not in a picture of pens)"""
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
                line = [pen for byte in data[4 * source:4 * source + 4] for pen in (byte >> 4, byte & 15)]
                if cell & MIRROR_X:
                    line.reverse()
                picture[8 * y + row][8 * x:8 * x + 8] = line
    return picture
