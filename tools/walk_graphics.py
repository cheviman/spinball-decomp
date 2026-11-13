"""
Name:        walk_graphics.py
Description: Sonic the Hedgehog Spinball's graphics, walked from where the code hands them over: the tiles
             the loaders get, the palettes and their colour cycles (for tools/data_walk.py)
Version:     0.1.0
Created:     13-11-2026
Modified:    13-11-2026
Author:      Sebastian Toyos

  tiles          what the code hands to the functions that load tiles into the VRAM (tools/spinball_compression.py),
                 found like the definitions ("pea TILES.l", or a table by the level), and read as they read it:
                 0D6B88 SSC (its first argument; Toxic Caves' 0D3FE4-0D401A: the level's tiles from the table
                 BFBE0, then the ones of BFBF0 after them, from the tile the first ones' word says); 0F3BB8 a word,
                 then as many tiles as it says, as they are, or C2 if it says 0 or less (its argument); 0F5A5E C2
                 (its second argument; the bonus stage 0FA7FE-0FA826: one of four by FF3CBC). SSC tiles that read
                 a place of the window not written yet, or do not give as many as their word says, are no tiles.
                 Tiles of an odd size are followed by FF, to even the place after them. The C2 decoder reads the
                 masks of the codes' widths at 09BCD2 (four words: the fourth, FFF, is never read), and a code as
                 the three bytes from the one its first bit is in: two bytes past the end, which belong to what
                 follows.
  palettes       from 000DFC, 32 bytes each (tools/spinball_graphics.py), up to the next place the code hands over
                 (the sprites at 0013DC: 47); before them, the gaps of the shell sort at 0FE3AE (40, 13, 4, 1).
  cycles         the tables the core's analysis bounds by a counter that wraps ("cmpi.w #N, COUNTER; blt; clr.w
                 COUNTER": tools/core/m68000/analysis.py, bound_tables()) whose read goes to the palettes' copy
                 (PALETTE_COPY): 0D6C2A's colour cycles, BFD24-BFDC3.
"""
import struct
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]
import spinball_compression as compression  # noqa: E402
import spinball_graphics as graphics  # noqa: E402
from walk_patterns import LEVELS  # noqa: E402

TILE_LOADERS = {                    # the functions that load tiles into the VRAM: (what they read, its argument)
    0x0D6B88: ("ssc", 0),           # SSC; the second argument the VRAM's tile
    0x0F3BB8: ("word", 0),          # a word: above 0 that many tiles as they are, else C2; to VRAM 0
    0x0F5A5E: ("c2", 1),            # C2; the first argument the VRAM's address
}
TILESET_PAD = 0xFF                  # what evens the place after tiles of an odd size
C2_MASKS_SIZE = 8                   # four words: 1FF, 3FF, 7FF and FFF, the last not read (codes stop at 11 bits)
PALETTES = 0x000DFC                 # "movea.l #$dfc, A0" (0D8652, 0D87C8, 0D8922...): 32 bytes a palette
PALETTE_COPY = 0xFF41C4             # the palettes the VBLANK's fades and cycles write to the CRAM from (0D863E)
SORT_GAPS = 0x000DF4                # the gaps of the shell sort at 0FE3AE-0FE412, words down to 1


class GraphicsWalk:
    """The tiles, the palettes, the colour cycles"""

    def init_graphics(self):
        self.tilesets = {}              # {address: (kind, size in bytes, how it was found)}
        self.tileset_tables = {}        # {address: how it was found}: tables of four tilesets, a level each
        self.palettes = 0               # how many palettes from PALETTES
        self.sort_gaps = 0              # how many words from SORT_GAPS
        self.cycles = {}                # {address: (entries, entry size, kind, how it was found)}

    def tileset_load(self, position, address, loader):
        """The tiles a call of one of the loaders gets, where the code says which"""
        kind, argument = TILE_LOADERS[loader]
        how = f"passed to {loader:06X} at {address:06X}"
        for tiles, table in self.passed(position, argument):
            if table is not None:
                self.tileset_tables[table] = f"indexed by the level, {how}"
            self.add_tileset(tiles, kind, how if table is None else f"an entry of {table:06X}, {how}")

    def add_tileset(self, address, kind, found):
        """Tiles as the loader of 'kind' reads them; the walk stops where they do not read so"""
        if address in self.tilesets:
            return
        image = self.image
        if kind == "word" and struct.unpack_from(">h", image, address)[0] > 0:
            kind, size = "raw tiles", 2 + 32 * struct.unpack_from(">h", image, address)[0]
        elif kind == "ssc":
            result = compression.ssc_decode(image, address)
            if result.unwritten or len(result.data) != 32 * result.tiles:
                raise SystemExit(f"{address:06X} ({found}): no SSC tiles (it gives {len(result.data)} bytes for "
                                 f"{result.tiles} tiles, {len(result.unwritten)} reads of the window not written)")
            kind, size = "SSC tiles", result.size
        else:
            start = address + 2 if kind == "word" else address
            result = compression.c2_decode(image, start)
            if result.codes[0] != compression.C2_RESTART or result.most_entries > compression.C2_LAST_ENTRY + 1:
                raise SystemExit(f"{address:06X} ({found}): no C2 tiles")
            kind, size = ("C2 tiles after a word" if kind == "word" else "C2 tiles"), start - address + result.size
        if (address + size) & 1 and image[address + size] == TILESET_PAD:
            size += 1
        self.tilesets[address] = (kind, size, found)

    def walk_palettes(self):
        """The palettes, up to the next place the code hands over; and the sort's gaps, down to 1"""
        for table in (PALETTES, SORT_GAPS):
            if table not in self.anchors:
                raise SystemExit(f"{table:06X}: no instruction names it")
        self.palettes = (self.next_handed(PALETTES) - PALETTES) // graphics.PALETTE_BYTES
        gaps = 0
        while struct.unpack_from(">H", self.image, SORT_GAPS + 2 * gaps)[0] != 1:
            gaps += 1
        self.sort_gaps = gaps + 1

    def spans_graphics(self, found):
        for address, (kind, size, _) in self.tilesets.items():
            found[address] = (address + size, kind)
        for table in self.tileset_tables:
            found[table] = (table + 4 * LEVELS, "tilesets by level")

    def find_cycles(self):
        """The colour cycles: the tables the core's analysis bounds by a counter that wraps (bounded_tables) whose
        read goes to the palettes' copy (PALETTE_COPY)"""
        for table, (entries, stride, size, reader, bound, kind) in self.analysis.bounded_tables.items():
            destination = self.analysis.instructions[reader].operands[-1]
            if kind == "counter" and destination.mode == "abs_long" \
                    and PALETTE_COPY <= destination.value & 0xFFFFFF < PALETTE_COPY + 4 * graphics.PALETTE_BYTES:
                self.cycles[table] = (entries, size, "colour cycle", f"read at {reader:06X}, wrapped at {bound:06X}")

    def spans_palettes(self, found):
        for index in range(self.palettes):
            first = PALETTES + graphics.PALETTE_BYTES * index
            found[first] = (first + graphics.PALETTE_BYTES, "palette")
        if self.sort_gaps:
            found[SORT_GAPS] = (SORT_GAPS + 2 * self.sort_gaps, "sort gaps")

    def spans_c2_masks(self, found):
        if any(kind.startswith("C2") for kind, _, _ in self.tilesets.values()):
            found[compression.C2_MASKS] = (compression.C2_MASKS + C2_MASKS_SIZE, "C2 code masks")
