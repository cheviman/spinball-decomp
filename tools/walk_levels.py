"""
Name:        walk_levels.py
Description: Sonic the Hedgehog Spinball's tables' levels, walked from where the code keeps them: the planes'
             maps and brushes, the collision, the flippers, the values by the level (for
             tools/data_walk.py)
Version:     0.1.0
Created:     13-11-2026
Modified:    15-11-2026
Author:      Sebastian Toyos

  maps, brushes  what the code keeps in FF3CAC (a map) and FF58CC (its brushes) before the plane drawers
                 (0D8D0E, 0D8E12) run (tools/spinball_levels.py): an entry of a table by the level ("movea.l
                 #TABLE, A0; move.l (A0,Dn.w), FF3CAC.l": BFC00 and BFC20 plane A's, BFC10 and BFC30 plane B's,
                 0D4FC0-0D502C), or an address ("move.l #MAP, FF3CAC.l": the options screen's, 0FF446). A map is
                 as wide as MAP_WIDTHS says for its level (for a map kept by address, the level the code sets in
                 FF75B0 before it calls the function that keeps it: 4, the options', at 0FEDA4, 0FF192 and 0FF2D4),
                 and as high as LEVEL_SIZES says for the four tables, in whole rows up to the next place the code
                 hands over (Showdown's background: 48 of 64 rows, up to its collision at 5FEEA); the options'
                 map up to the next place the code names (its texts at BE248: 7 rows). Its brushes are as many as
                 the highest it uses. The drawers draw a cell more than the screen: they read the row after a
                 map's last, and the brushes its words would name. The table BFC40 by the level, kept in FFF1F4,
                 holds the collision; the tables of values LEVEL_VALUES are read by the level too.
  collision      what the code keeps in FFF1F4 (tools/spinball_levels.py): an entry of a table by the level
                 (BFC40, 0D4020-0D402A), a word a sector of 128x128 pixels (16 a row, as many rows as the table's
                 height in LEVEL_SIZES takes) that places its list, then the lists: they must follow each other in
                 the sectors' order, from the end of the words.
  flippers       the flippers' code names their tables (FLIPPERS and the next): each table's flippers by the
                 level, as many as FLIPPER_COUNTS says; their collision's shapes, lists like a sector's, by the
                 flipper's position (as many as the table holds before the next one), one table a side; and their
                 boxes by the position, those after the first (whose place the shapes' second table takes).
  zones          the objects near the screen (0D61EA): ZONES by the level points at a block, a byte a zone of
                 360x264 pixels in rows of 6 (0D6250, 0D6262, the row times 6 at 0D6270-0D6274), as many rows as
                 the table's height in LEVEL_SIZES takes, each the place in the block of the zone's list: a count
                 (0D639A), then that many objects' numbers (0D63C6). The lists follow the grid.
  sectors' objs  a table's objects by sector, for the code of its objects (0E5198, 0E663A, 0F14BE): a word a
                 sector of 128x128 pixels in rows of 16 (0F14A6-0F14BA), each the place in words of the sector's
                 list: a word of how many, then that many objects' numbers. The code reads a sector's word and then
                 the word at its place, from the same block: "movea.l #BLOCK, A0; move.w (A0,Dn.w), Dk; move.w Dk,
                 D0; add.w D0, D0; movea.l #BLOCK, A0; move.w (A0,D0.w)". The grid is as long as the place of its
                 first list says; the lists follow it.
"""
import struct
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]
import spinball_levels as levels  # noqa: E402
from walk_patterns import LEVELS, long_at  # noqa: E402

LEVEL_POINTERS = {                  # where the code keeps an entry of a table by the level, and what it is
    0xFF3CAC: "map",                # read by the plane drawers 0D8D0E, 0D8E12
    0xFF58CC: "brushes",            # the same
    0xFFF1F4: "collision",          # read by 0DC3DE, 0DCBB0, 0E1D10 and the tests 0DB900, 0DBC60
}
LEVEL_SIZES = 0x0BFC70              # the tables' width and height in pixels, two words each (0D4036)
PAIR_DISTANCE = 0x40                # how far after a map's store its brushes' store comes (in bytes of code)
FLIPPERS = 0x0C08BE                 # by the level: the table's flippers (0DDEE0), 10 bytes each (0DDEF0)
FLIPPER_COUNTS = 0x0C08EE           # by the level: how many (0DDEC8, FF58C4), a word each
FLIPPER_SHAPES = (0x0C0A86, 0x0C0A96)   # by the flipper's position, a side each (0DE53C, 0DE530)
FLIPPER_BOXES = 0x0C0A9C            # by the position, 10 bytes each (0DE336)
ZONES = 0x0BFD14                    # by the level: the table's zones of objects (0D6242)
ZONE_SIZE = (0x168, 0x108)          # a zone's width and height in pixels (0D6250, 0D6262)
ZONE_COLUMNS = 6                    # the zones of a row of the grid (0D6270-0D6274)
LEVEL_VALUES = {                    # the tables by the level walk_patterns does not find: their bytes a level
    0x0BFC50: (8, "palettes by level"),     # the palette of each of the four lines (0D419C-0D41D2: the line's
}                                           # number is added to the index, then 0D8674)


class LevelsWalk:
    """The planes, the collision, the flippers"""

    def init_levels(self):
        self.pointer_tables = {}        # {address: (what its entries point at, how it was found)}: by the level
        self.kept = []                  # [(kind, address or None, table or None, where)] LEVEL_POINTERS' stores
        self.plane_pairs = []           # [(map, its table, brushes, their table, where)] kept one after the other
        self.plane_places = []          # [(map, brushes)] walked
        self.widths_read = 0            # the entries of MAP_WIDTHS the walked maps take
        self.maps = {}                  # {address: (width, rows, how it was found)}
        self.brushes = {}               # {address: (count, how it was found)}
        self.collisions = {}            # {address: (rows of sectors, size in bytes, how it was found)}
        self.flippers = {}              # {address: (count, level)}
        self.flipper_shapes = {}        # {address: (size in bytes, how it was found)}
        self.flipper_boxes = (0, 0)     # (first, count) of the boxes walked
        self.zones = {}                 # {block: (rows, {a list's place in the block: its count}, how it was found)}
        self.object_sectors = {}        # {block: (cells, {a list's place in words: its count}, how it was found)}

    def level_pointer_store(self, position, address, instruction):
        """What the code keeps in one of LEVEL_POINTERS: an entry of a table by the level ("movea.l #TABLE, A0"
        then "move.l (A0,Dn.w), POINTER.l"), or an address ("move.l #ADDRESS, POINTER.l"); a map and its brushes
        are kept one after the other, before a plane is drawn"""
        operands = instruction.operands
        if instruction.mnemonic != "move" or instruction.size != "l" or len(operands) != 2 \
                or operands[1].mode != "abs_long" or not position:
            return
        kind = LEVEL_POINTERS.get(operands[1].value & 0xFFFFFF)
        if kind is None:
            return
        if operands[0].mode == "immediate":
            self.kept.append((kind, operands[0].value & 0xFFFFFF, None, address))
            return
        loader = self.ordered[position - 1][1]
        if operands[0].mode != "index" or loader.mnemonic != "movea" or loader.operands[0].mode != "immediate" \
                or loader.operands[1].reg != operands[0].reg:
            return
        table = loader.operands[0].value & 0xFFFFFF
        self.pointer_tables.setdefault(table, (kind, f"kept in {operands[1].value & 0xFFFFFF:06X} at {address:06X}"))
        self.kept.append((kind, None, table, address))

    def pair_planes(self):
        """The maps and their brushes from what the code keeps: each brushes after the map kept just before it"""
        last_map = None
        for kind, value, table, address in self.kept:
            if kind == "map":
                last_map = (value, table, address)
            elif kind == "brushes" and last_map is not None and address - last_map[2] < PAIR_DISTANCE:
                pair = (last_map[0], last_map[1], value, table, address)
                if pair[:4] not in [known[:4] for known in self.plane_pairs]:
                    self.plane_pairs.append(pair)
                last_map = None

    def walk_planes(self):
        """Each map and its brushes: a map is its table's width (MAP_WIDTHS, by the level: for a map the code keeps
        itself, the level the code sets before it calls the function that keeps it) by its height in brushes: a
        table's from LEVEL_SIZES (over 32), in whole rows up to the next place the code hands over; another
        screen's, the whole rows up to the next place the code names (the options': 7, the screen's 224 lines,
        up to its texts at BE248). Its brushes, as many as the highest it uses, must end by the next place the
        code hands over"""
        for map_address, map_table, brushes_address, brushes_table, address in self.plane_pairs:
            if map_table is not None:
                entries = [(level, long_at(self.image, map_table + 4 * level),
                            long_at(self.image, brushes_table + 4 * level),
                            f"entry {level} of {map_table:06X}", f"entry {level} of {brushes_table:06X}")
                           for level in range(LEVELS)]
            elif map_address in self.maps:
                continue
            else:
                found = self.levels_set_before(self.function_of(address))
                if len(found) != 1:
                    raise SystemExit(f"the map kept at {address:06X}: the code sets the levels {sorted(found)} first")
                level = found.pop()
                entries = [(level, map_address, brushes_address, f"kept at {address:06X} for level {level}",
                            f"kept at {address:06X}")]
            for level, where, brushes_at, map_found, brushes_found in entries:
                self.add_plane(level, where, brushes_at, map_found, brushes_found)

    def add_plane(self, level, where, brushes_at, map_found, brushes_found):
        width = struct.unpack_from(">H", self.image, levels.MAP_WIDTHS + 2 * level)[0]
        self.widths_read = max(self.widths_read, level + 1)
        if level < LEVELS:
            height = struct.unpack_from(">H", self.image, LEVEL_SIZES + 4 * level + 2)[0] // levels.BRUSH_PIXELS
            rows = min(height, (self.next_handed(where) - where) // (2 * width))
        else:
            next_named = min(anchor for anchor in self.anchors if anchor > where)
            height = rows = (next_named - where) // (2 * width)
        self.maps[where] = (width, rows, map_found + ("" if rows == height else f", {rows} of {height} rows: what "
                                                      f"the code hands over next is at {where + 2 * width * rows:06X}"))
        count = 1 + max(word & levels.BRUSH_NUMBER for row in levels.read_map(self.image, where, width, rows)
                        for word in row)
        if brushes_at + levels.BRUSH_BYTES * count > self.next_handed(brushes_at):
            raise SystemExit(f"the brushes at {brushes_at:06X} ({count} for the map {where:06X}) run into "
                             f"{self.next_handed(brushes_at):06X}")
        self.brushes[brushes_at] = (count, f"{brushes_found}, for the map {where:06X}")
        self.plane_places.append((where, brushes_at))

    def walk_collisions(self):
        """Each table's collision, from the tables by the level the code keeps in FFF1F4"""
        for table, (kind, _) in self.pointer_tables.items():
            if kind != "collision":
                continue
            for level in range(LEVELS):
                where = long_at(self.image, table + 4 * level)
                height = struct.unpack_from(">H", self.image, LEVEL_SIZES + 4 * level + 2)[0]
                rows = (height + levels.SECTOR - 1) // levels.SECTOR
                try:
                    _, size = levels.read_collision(self.image, where, rows)
                except ValueError as problem:
                    raise SystemExit(f"the collision at {where:06X} (entry {level} of {table:06X}): {problem}")
                if where + size > self.next_handed(where):
                    raise SystemExit(f"the collision at {where:06X} runs into {self.next_handed(where):06X}")
                self.collisions[where] = (rows, size, f"entry {level} of {table:06X}")

    def walk_flippers(self):
        """The flippers' tables by the level, their shapes by the position, and the boxes: FLIPPERS and the other
        tables the flippers' code names (each must be named by an instruction)"""
        for table, (stride, size) in ((FLIPPERS, (4, 4)), (FLIPPER_COUNTS, (2, 2))):
            if self.value_tables_by_level.get(table, (0, 0))[:2] != (stride, size):
                raise SystemExit(f"{table:06X}: the code does not read it by the level, {size} bytes every {stride}")
        for table in (FLIPPER_BOXES,) + FLIPPER_SHAPES:
            if table not in self.anchors:
                raise SystemExit(f"{table:06X}: no instruction names it")
        for level in range(LEVELS):
            where = long_at(self.image, FLIPPERS + 4 * level)
            count = struct.unpack_from(">H", self.image, FLIPPER_COUNTS + 2 * level)[0]
            try:
                levels.read_flippers(self.image, where, count)
            except ValueError as problem:
                raise SystemExit(str(problem))
            self.flippers[where] = (count, level)
        positions = (FLIPPER_SHAPES[1] - FLIPPER_SHAPES[0]) // 4
        for side, table in enumerate(FLIPPER_SHAPES):
            for position in range(positions):
                where = long_at(self.image, table + 4 * position)
                _, size = levels.read_list(self.image, where)
                self.flipper_shapes[where] = (size, f"position {position} of {table:06X}")
        first = next(position for position in range(positions)
                     if FLIPPER_BOXES + levels.FLIPPER_BOX_BYTES * position >= FLIPPER_SHAPES[1] + 4 * positions)
        self.flipper_boxes = (first, positions - first)

    def walk_zones(self):
        """Each table's zones of objects: the grid, as many rows as its height takes, then the lists it places"""
        if ZONES not in self.anchors:
            raise SystemExit(f"{ZONES:06X} (zones by level): no instruction names it")
        for level in range(LEVELS):
            block = long_at(self.image, ZONES + 4 * level)
            height = struct.unpack_from(">H", self.image, LEVEL_SIZES + 4 * level + 2)[0]
            rows = (height - 1) // ZONE_SIZE[1] + 1
            cells = self.image[block:block + rows * ZONE_COLUMNS]
            if min(cells) < len(cells):
                raise SystemExit(f"{block:06X}: a zone's list inside the grid of {rows} rows (level {level})")
            lists = {place: self.image[block + place] for place in set(cells)}
            self.zones[block] = (rows, lists, f"level {level} of {ZONES:06X}")
        for position in range(len(self.ordered) - 5):
            steps = [self.ordered[position + k][1] for k in range(6)]
            if all(steps[k].mnemonic == "movea" and steps[k].operands[0].mode == "immediate" for k in (0, 4)) \
                    and steps[0].operands[0].value == steps[4].operands[0].value \
                    and all(steps[k].mnemonic == "move" and steps[k].operands[0].mode == "index" for k in (1, 5)) \
                    and steps[2].mnemonic == "move" and steps[2].operands[0].reg == steps[1].operands[1].reg \
                    and steps[3].mnemonic == "add":
                block = steps[0].operands[0].value & 0xFFFFFF
                if block < len(self.image):
                    self.walk_object_sectors(block, f"read at {self.ordered[position + 1][0]:06X}")

    def walk_object_sectors(self, block, found):
        """A block of objects by sector: the grid up to its first list, then the lists"""
        words = (len(self.image) - block) // 2

        def word(index):
            return struct.unpack_from(">H", self.image, block + 2 * index)[0]

        cells, first = 0, word(0)
        while cells < min(first, words):
            first = min(first, word(cells))
            cells += 1
        if not cells:
            raise SystemExit(f"{block:06X}: no objects' sectors ({found})")
        self.object_sectors.setdefault(block, (cells, {place: word(place) for place in
                                                       {word(cell) for cell in range(cells)}}, found))

    def spans_levels(self, found):
        for table, (kind, _) in self.pointer_tables.items():
            found[table] = (table + 4 * LEVELS, f"{kind} by level")
        for address, (width, rows, _) in self.maps.items():
            found[address] = (address + 2 * width * rows, "map")
        for address, (_, size, _) in self.collisions.items():
            found[address] = (address + size, "collision")

    def spans_flippers(self, found):
        if self.flippers:
            found[FLIPPERS] = (FLIPPERS + 4 * LEVELS, "flippers by level")
            found[FLIPPER_COUNTS] = (FLIPPER_COUNTS + 2 * LEVELS, "flipper counts by level")
            for table in FLIPPER_SHAPES:
                found[table] = (table + FLIPPER_SHAPES[1] - FLIPPER_SHAPES[0], "flipper shapes by position")
            first, count = self.flipper_boxes
            boxes = FLIPPER_BOXES + levels.FLIPPER_BOX_BYTES * first
            found[boxes] = (boxes + levels.FLIPPER_BOX_BYTES * count, "flipper boxes")

    def spans_level_records(self, found):
        for address, (count, _) in self.flippers.items():
            found[address] = (address + levels.FLIPPER_BYTES * count, "flippers")
        for address, (size, _) in self.flipper_shapes.items():
            found[address] = (address + size, "flipper shape")
        for address, (count, _) in self.brushes.items():
            found[address] = (address + levels.BRUSH_BYTES * count, "brushes")
        if self.widths_read:
            found[levels.MAP_WIDTHS] = (levels.MAP_WIDTHS + 2 * self.widths_read, "map widths")
        for block, (cells, lists, _) in self.object_sectors.items():
            found[block] = (block + 2 * cells, "objects' sectors")
            for place, count in lists.items():
                found[block + 2 * place] = (block + 2 * (place + 1 + count), "sector's objects")
        for block, (rows, lists, _) in self.zones.items():
            found[block] = (block + rows * ZONE_COLUMNS, "zones' grid")
            for place, count in lists.items():
                found[block + place] = (block + place + 1 + count, "zone's objects")
        for table, (size, kind) in LEVEL_VALUES.items():
            if table not in self.anchors:
                raise SystemExit(f"{table:06X} ({kind}): no instruction names it")
            found[table] = (table + size * LEVELS, kind)
