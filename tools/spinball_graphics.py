"""
Name:        spinball_graphics.py
Description: Sonic the Hedgehog Spinball's graphics formats: the sprite tables, read and built back byte for byte,
             and their sheets; the tiles' sheets; the palettes
Version:     0.1.0
Created:     13-11-2026
Modified:    13-11-2026
Author:      Sebastian Toyos

A sprite table, as the sprite loader reads it (0D7D02-0D7FB0: an animated object's field 0A holds the table):
  u16 count, u16 flags (bit 1: the offsets are 32-bit), then the offset of each sprite from the table, 16 or 32
  bits; the sprites follow, one after the other in their order.
A sprite: u16 pieces, u16 the 8x8 tiles of the VDP its pieces take (each piece's width and height in tiles,
  rounded up, multiplied), then a 6-byte header a piece: s16 x and s16 y of its top left corner from the sprite's
  origin (mirrored, the loader takes -x - its width), u8 height in pixels, u8 width in bytes; then each piece's
  pixels: its height in rows of its width in bytes, two pixels a byte, the left one in the high nibble (the pen,
  0 transparent; the palette line is the object's).

A sheet lays a table's sprites out a row at a time: each sprite drawn whole, its pieces at their places (none of
the pieces of a sprite overlap: checked), in a cell as big as all of them. sprites.txt says where: per sprite its
cell's corner in the sheet and where its origin is, and each piece's place and size; the sheet's pixels give the
pens back.

The palettes, from 000DFC (0D863E, 0D873A: the number FF004C keeps for each of the four lines, 32 bytes a palette,
"lsl.w #5"): 16 words each, as the CRAM takes them (0000BBB0GGG0RRR0), up to the sprites at 0013DC: 47. Their text
form is a line a palette, its 16 words in hex.
"""
import struct
from dataclasses import dataclass, field

SHEET_WIDTH = 512           # a sheet's rows wrap at this width
SHEET_GAP = 2               # pixels between two cells


@dataclass
class Piece:
    x: int                  # its top left corner from the sprite's origin
    y: int
    width: int              # in pixels (twice its bytes)
    height: int
    pens: list = field(default_factory=list)    # rows of pens


@dataclass
class Sprite:
    pieces: list


def tiles_of(pieces):
    """The 8x8 tiles of the VDP a sprite's pieces take, as its header counts them"""
    return sum(((piece.height + 7) // 8) * ((piece.width + 7) // 8) for piece in pieces)


def read_table(image, address):
    """A sprite table at 'address': (flags, [Sprite], its size in bytes); ValueError when the bytes do not read
    as one (the sprites not one after the other from the end of the offsets, or a header that disagrees)"""
    count, flags = struct.unpack_from(">HH", image, address)
    wide = flags & 2
    offsets = [struct.unpack_from(">I" if wide else ">H", image, address + 4 + (4 if wide else 2) * index)[0]
               for index in range(count)]
    cursor = 4 + count * (4 if wide else 2)
    sprites = []
    for index, offset in enumerate(offsets):
        if offset != cursor:
            raise ValueError(f"sprite {index} of {address:06X} at +{offset:X}, not at +{cursor:X}")
        at = address + offset
        count_pieces, tiles = struct.unpack_from(">HH", image, at)
        pieces = []
        data = at + 4 + 6 * count_pieces
        for number in range(count_pieces):
            x, y, height, width_bytes = struct.unpack_from(">hhBB", image, at + 4 + 6 * number)
            pens = []
            for row in range(height):
                line = image[data + row * width_bytes:data + (row + 1) * width_bytes]
                pens.append([pen for byte in line for pen in (byte >> 4, byte & 15)])
            data += height * width_bytes
            pieces.append(Piece(x, y, 2 * width_bytes, height, pens))
        if tiles_of(pieces) != tiles:
            raise ValueError(f"sprite {index} of {address:06X} says {tiles} tiles, its pieces take {tiles_of(pieces)}")
        sprites.append(Sprite(pieces))
        cursor = data - address
    return flags, sprites, cursor


def build_table(flags, sprites):
    """The bytes of a sprite table"""
    wide = flags & 2
    body = bytearray()
    offsets = []
    first = 4 + len(sprites) * (4 if wide else 2)
    for sprite in sprites:
        offsets.append(first + len(body))
        body += struct.pack(">HH", len(sprite.pieces), tiles_of(sprite.pieces))
        for piece in sprite.pieces:
            body += struct.pack(">hhBB", piece.x, piece.y, piece.height, piece.width // 2)
        for piece in sprite.pieces:
            for row in piece.pens:
                body += bytes(row[index] << 4 | row[index + 1] for index in range(0, len(row), 2))
    head = struct.pack(">HH", len(sprites), flags)
    head += b"".join(struct.pack(">I" if wide else ">H", offset) for offset in offsets)
    return bytes(head + body)


def bounds(sprite):
    """(left, top, right, bottom) of a sprite's pieces, from its origin; (0, 0, 1, 1) for one with none"""
    if not sprite.pieces:
        return 0, 0, 1, 1
    return (min(piece.x for piece in sprite.pieces), min(piece.y for piece in sprite.pieces),
            max(piece.x + piece.width for piece in sprite.pieces), max(piece.y + piece.height for piece in sprite.pieces))


def overlapping(sprite):
    """Whether two of a sprite's pieces cover the same pixel (then a drawn sprite would not give them back)"""
    covered = set()
    for piece in sprite.pieces:
        for row in range(piece.height):
            for column in range(piece.width):
                spot = (piece.x + column, piece.y + row)
                if spot in covered:
                    return True
                covered.add(spot)
    return False


def lay_out(sprites):
    """Where each sprite's cell goes in the sheet, [(x, y)], and the sheet's (width, height)"""
    places, x, y, line, width = [], 0, 0, 0, 1
    for sprite in sprites:
        left, top, right, bottom = bounds(sprite)
        cell_width, cell_height = right - left, bottom - top
        if x and x + cell_width > SHEET_WIDTH:
            x, y, line = 0, y + line + SHEET_GAP, 0
        places.append((x, y))
        x += cell_width + SHEET_GAP
        line = max(line, cell_height)
        width = max(width, x - SHEET_GAP)
    return places, (width, y + line)


def draw_sheet(sprites, places, size):
    """The sheet's rows of pens"""
    width, height = size
    rows = [[0] * width for _ in range(height)]
    for sprite, (cell_x, cell_y) in zip(sprites, places):
        left, top, _, _ = bounds(sprite)
        for piece in sprite.pieces:
            for row in range(piece.height):
                for column in range(piece.width):
                    rows[cell_y + piece.y - top + row][cell_x + piece.x - left + column] = piece.pens[row][column]
    return rows


def sprites_text(name, address, flags, sprites, places):
    """A table's section of sprites.txt"""
    lines = [f"table {name} flags {flags:04X} at {address:06X}"]
    for index, (sprite, (cell_x, cell_y)) in enumerate(zip(sprites, places)):
        left, top, _, _ = bounds(sprite)
        pieces = " ".join(f"{piece.x},{piece.y},{piece.width}x{piece.height}" for piece in sprite.pieces)
        lines.append(f"  {index} cell {cell_x},{cell_y} origin {cell_x - left},{cell_y - top} pieces {pieces}".rstrip())
    return "\n".join(lines) + "\n"


def parse_sprites_text(text):
    """{name: (flags, address, [(origin_x, origin_y, [(x, y, width, height)])])} from sprites.txt"""
    tables, current = {}, None
    for line in text.splitlines():
        line = line.split("#", 1)[0].rstrip()
        if not line:
            continue
        words = line.split()
        if words[0] == "table":
            current = []
            tables[words[1]] = (int(words[3], 16), int(words[5], 16), current)
            continue
        origin_x, origin_y = (int(value) for value in words[4].split(","))
        pieces = []
        for item in words[6:]:
            position, size = item.rsplit(",", 1)
            x, y = (int(value) for value in position.split(","))
            width, height = (int(value) for value in size.split("x"))
            pieces.append((x, y, width, height))
        current.append((origin_x, origin_y, pieces))
    return tables


def sprites_from_sheet(rows, layout):
    """The table's sprites back from its sheet's pens and its section of sprites.txt"""
    sprites = []
    for origin_x, origin_y, pieces in layout:
        built = []
        for x, y, width, height in pieces:
            pens = [rows[origin_y + y + row][origin_x + x:origin_x + x + width] for row in range(height)]
            built.append(Piece(x, y, width, height, pens))
        sprites.append(Sprite(built))
    return sprites


# ---- tiles ----

TILE_SIZE = 8               # pixels a side
TILE_BYTES = 32             # 8 rows of 4 bytes, two pixels a byte, the left one in the high nibble
TILES_ACROSS = 16           # a tile sheet's tiles a row


def tiles_sheet(data):
    """The rows of pens of a sheet of the tiles in 'data' (TILES_ACROSS a row; a last tile cut short is drawn
    with pen 0 where it has no bytes)"""
    count = (len(data) + TILE_BYTES - 1) // TILE_BYTES
    rows = [[0] * (TILES_ACROSS * TILE_SIZE) for _ in range(((count + TILES_ACROSS - 1) // TILES_ACROSS) * TILE_SIZE)]
    for index, value in enumerate(data):
        tile, inside = divmod(index, TILE_BYTES)
        row, column = divmod(inside, TILE_SIZE // 2)
        y = (tile // TILES_ACROSS) * TILE_SIZE + row
        x = (tile % TILES_ACROSS) * TILE_SIZE + 2 * column
        rows[y][x], rows[y][x + 1] = value >> 4, value & 15
    return rows


def tiles_from_sheet(rows, size):
    """The first 'size' bytes of the tiles a sheet's rows of pens hold"""
    data = bytearray()
    for index in range(size):
        tile, inside = divmod(index, TILE_BYTES)
        row, column = divmod(inside, TILE_SIZE // 2)
        y = (tile // TILES_ACROSS) * TILE_SIZE + row
        x = (tile % TILES_ACROSS) * TILE_SIZE + 2 * column
        data.append(rows[y][x] << 4 | rows[y][x + 1])
    return bytes(data)


# ---- palettes ----

PALETTE_COLORS = 16
PALETTE_BYTES = 2 * PALETTE_COLORS     # a word a colour, as the VDP's CRAM takes it: 0000BBB0GGG0RRR0


def read_palettes(image, address, count):
    """[[16 words]] of 'count' palettes"""
    return [list(struct.unpack_from(f">{PALETTE_COLORS}H", image, address + PALETTE_BYTES * index))
            for index in range(count)]


def palettes_bytes(palettes):
    return b"".join(struct.pack(f">{PALETTE_COLORS}H", *colors) for colors in palettes)


def rgb(word):
    """A CRAM word's colour as 8-bit red, green, blue (each of the three levels' 0-7 over 7)"""
    return tuple(round(((word >> shift) & 0x0E) / 2 * 255 / 7) for shift in (0, 4, 8))


def palettes_text(palettes):
    lines = [f"palette {index}: " + " ".join(f"{word:04X}" for word in colors) for index, colors in enumerate(palettes)]
    return "\n".join(lines) + "\n"


def parse_palettes_text(text):
    palettes = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        number, words = line.removeprefix("palette").split(":")
        if int(number) != len(palettes):
            raise ValueError(f"palette {number.strip()} out of order (expected {len(palettes)})")
        palettes.append([int(word, 16) for word in words.split()])
    return palettes


def palettes_picture(palettes, swatch=8):
    """(rows of indices, the colours) of a picture of the palettes: a row of 16 swatches each"""
    colors = sorted({word for colors in palettes for word in colors})
    index = {word: number for number, word in enumerate(colors)}
    rows = []
    for palette in palettes:
        line = [index[word] for word in palette for _ in range(swatch)]
        rows += [list(line) for _ in range(swatch)]
    return rows, [rgb(word) for word in colors]
