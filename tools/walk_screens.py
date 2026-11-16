"""
Name:        walk_screens.py
Description: Sonic the Hedgehog Spinball's front end (the Sega logo, the intro, the main menu, the cutscenes and
             the ending, 0F2554-0F6BF6): its screens' maps, palettes and sprites, and the Z80's program, walked
             from the code that hands them over (for tools/data_walk.py)
Version:     0.1.0
Created:     15-11-2026
Modified:    15-11-2026
Author:      Sebastian Toyos

  maps           0F3C06 (plane A, VRAM C000) and 0F3C82 (plane B, E000) copy a map into the plane from the cell
                 their second and third arguments say (x, y): a word of width and one of height, in cells, then
                 the cells a row at a time (a row of the plane is 1 << the byte of 0F3DEE that the plane size of
                 the VDP's register 16, 0F38C4, picks). Their first argument comes as "pea MAP.l", or as "move.l
                 RECORD+4.l, -(A7)": the map of a screen's record of 8 bytes, its x and y words then the map
                 (the front end's table of them, 099364); where the other two arguments are not that record's
                 words (0F3774's), only the record's map is read.
  palettes       0F3A6C takes a word of how many colours, then the colours, into the CRAM from colour 0 (its
                 argument); 0F3AE0 as many colours as its second argument says, into the CRAM from the colour its
                 first says (its third). A function that loads one of its own arguments into a register and passes
                 it on, unchanged, as one of these palettes reads it as that palette (0F3200, the fade of a line to
                 16 colours: its second argument), with the count of the call that passes it on.
  sprites        0F40BE (its first argument) and 0F41FE (its second) take a sprite of 8 bytes: a byte no code reads,
                 the VDP's size of the sprite (its low four bits index 0F41BE's table of what mirroring it moves
                 it by), the x and the y of its corner from the place, and the VDP's word of the tile (priority,
                 palette, mirroring, tile). They come as "pea SPRITE.l", or from a table of them the code reads
                 with "move.l (An)+, -(A7)" or "move.l (An), -(A7)" after "movea.l #TABLE, An" (099344): its
                 entries while each is a sprite, up to the next place the code names.
  z80            0F601C copies the Z80's program (GEMS's driver) into the Z80's RAM from "lea START.l, A0" up to
                 "lea END.l, A1", where the next place starts (the GEMS banks), and zeroes the rest of the RAM.
  gems           0F6116 starts GEMS: the Z80's program, then command 11 (0F60EA) and the four banks' addresses
                 (0F60FA, "move.l #BANK, -(A7)" before each), in GEMS's order: the patches, the envelopes (the
                 modulators), the sequences, the samples. Each runs up to the next; the samples up to the next place
                 the code names. (Their contents are GEMS's formats.)
"""
import struct
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]
from walk_patterns import long_at, writes  # noqa: E402

MAP_LOADERS = {0x0F3C06: "plane A", 0x0F3C82: "plane B"}    # (map, x, y): a map into the plane from the cell x, y
COUNTED_PALETTE = 0x0F3A6C          # (palette): a word of how many colours, then the colours, from colour 0
PALETTE_LOADER = 0x0F3AE0           # (first colour, how many, colours)
SPRITE_MAKERS = {0x0F40BE: 0, 0x0F41FE: 1}  # the argument that is a sprite of 8 bytes
SPRITE_BYTES = 8
SCREEN_RECORD_BYTES = 8             # x, y, the map
Z80_RAM = 0xA00000                  # where 0F601C copies the Z80's program to
GEMS_INIT = 0x0F6116                # starts GEMS: the Z80's program, then the banks
GEMS_BANK = 0x0F60FA                # sends the driver one bank's address (its argument)
GEMS_BANKS = ("GEMS patches", "GEMS envelopes", "GEMS sequences", "GEMS samples")
CARTRIDGE = 0x400000                # the places below it are the cartridge's
TABLE_WALKED = 40                   # how far back from a push its table's "movea.l #TABLE" is looked for


class ScreensWalk:
    """The front end's maps, palettes and sprites, and the Z80's program"""

    def init_screens(self):
        self.screen_maps = {}           # {address: (width, height, how it was found)}
        self.screen_records = {}        # {address: how it was found}
        self.record_maps = {}           # {the place of a record's map: how}, where the code takes only the map
        self.counted_palettes = {}      # {address: (colours, how it was found)}
        self.screen_palettes = {}       # {address: (colours, how it was found)}
        self.screen_sprites = {}        # {address: how it was found}
        self.screen_sprite_tables = {}         # {address: (entries, how it was found)}
        self.palette_readers = {}       # {function: {argument: colours, or ("argument", k): its argument k's}}
        self.z80_program = None         # (first, stop, how it was found)
        self.gems_banks = {}            # {address: (kind, how it was found)}, in GEMS's order

    # ---- what a call gets ----

    def pointers_passed(self, position, argument):
        """[(value, where)] of what the call at 'position' gets as its stack argument 'argument', where the code
        says: "pea ADDRESS.l" (where None) or "move.l ADDRESS.l, -(A7)" (the long at ADDRESS, where ADDRESS)"""
        found = []
        for push in self.pushes(position, argument) or ():
            source = push.operands[0]
            if source.mode != "abs_long" or source.value & 0xFFFFFF >= len(self.image):
                continue
            if push.mnemonic == "pea":
                found.append((source.value & 0xFFFFFF, None))
            elif push.mnemonic == "move":
                found.append((long_at(self.image, source.value & 0xFFFFFF), source.value & 0xFFFFFF))
        return found

    def numbers_passed(self, position, argument):
        """The numbers the call at 'position' gets as its stack argument 'argument' ("pea N.w", "move.l #N",
        "clr.l"), or None where one of the ways pushes something else"""
        found = set()
        for push in self.pushes(position, argument) or [None]:
            source = push.operands[0] if push is not None and push.operands else None
            if push is None:
                return None
            if push.mnemonic == "clr":
                found.add(0)
            elif push.mnemonic == "pea" and source.mode == "abs_short":
                found.add(source.value & 0xFFFF)
            elif push.mnemonic == "move" and source.mode == "immediate":
                found.add(source.value)
            else:
                return None
        return found

    def word_read_before(self, push, register):
        """The place of "move.w PLACE.l, Dn" just before a push of Dn ("ext.l Dn" between them), or None"""
        at = self.position_of[push.address]
        for back in range(at - 1, max(at - 4, 0), -1):
            step = self.ordered[back][1]
            operands = step.operands
            if step.mnemonic == "ext" and operands[0].reg == register:
                continue
            if step.mnemonic == "move" and step.size == "w" and len(operands) == 2 and operands[1].mode == "dreg" \
                    and operands[1].reg == register and operands[0].mode == "abs_long":
                return operands[0].value & 0xFFFFFF
            return None
        return None

    def table_of(self, push):
        """The table a push "move.l (An)+, -(A7)" or "move.l (An), -(A7)" reads, where An comes from "movea.l
        #TABLE, An" earlier in the function and only steps on since; or None"""
        source = push.operands[0]
        if push.mnemonic != "move" or source.mode not in ("indirect", "postinc"):
            return None
        at = self.position_of[push.address]
        function = self.function_of(push.address)
        for back in range(at - 1, max(at - TABLE_WALKED, 0), -1):
            step = self.ordered[back][1]
            operands = step.operands
            if step.mnemonic == "movea" and operands[0].mode == "immediate" and operands[1].reg == source.reg:
                return operands[0].value & 0xFFFFFF
            if step.mnemonic in ("addq", "adda") and operands[-1].mode == "areg" and operands[-1].reg == source.reg:
                continue
            if writes(step, source.reg) and not (operands and operands[0].mode == "postinc"
                                                  and operands[0].reg == source.reg):
                return None
            if self.ordered[back][0] == function:
                return None
        return None

    # ---- the walk ----

    def walk_screens(self):
        self.find_palette_readers()
        for position, (address, instruction) in enumerate(self.ordered):
            self.z80_copy(position, address, instruction)
            if instruction.flow != "call":
                continue
            target = self.call_target(position)
            if target in MAP_LOADERS:
                self.map_load(position, address, target)
            elif target == COUNTED_PALETTE:
                for palette, _ in self.pointers_passed(position, 0):
                    self.add_counted_palette(palette, f"passed to {target:06X} at {address:06X}")
            elif target in SPRITE_MAKERS:
                self.sprite_passed(position, address, target)
            if target in self.palette_readers:
                for argument, colours in self.palette_readers[target].items():
                    if isinstance(colours, tuple):
                        counts = self.numbers_passed(position, colours[1])
                        if not counts or len(counts) != 1:
                            continue
                        colours = counts.pop()
                    for palette, _ in self.pointers_passed(position, argument):
                        self.add_palette(palette, colours, f"argument {argument} of {target:06X} at {address:06X}")

    def map_load(self, position, address, loader):
        how = f"passed to {loader:06X} ({MAP_LOADERS[loader]}) at {address:06X}"
        for screen_map, place in self.pointers_passed(position, 0):
            if place is not None:
                x, y = (self.pushes(position, argument) or [None] for argument in (1, 2))
                words = [self.word_read_before(push[0], push[0].operands[0].reg)
                         if len(push) == 1 and push[0] is not None and push[0].operands[0].mode == "dreg" else None
                         for push in (x, y)]
                if words == [place - 4, place - 2]:
                    self.screen_records.setdefault(place - 4, how)
                else:
                    self.record_maps.setdefault(place, how)
            self.add_map(screen_map, how)

    def add_map(self, address, found):
        width, height = struct.unpack_from(">HH", self.image, address)
        if not (0 < width <= 128 and 0 < height <= 128):
            raise SystemExit(f"{address:06X}: no map ({width}x{height}), {found}")
        self.screen_maps.setdefault(address, (width, height, found))

    def add_counted_palette(self, address, found):
        colours = struct.unpack_from(">H", self.image, address)[0]
        if not 0 < colours <= 64:
            raise SystemExit(f"{address:06X}: no palette ({colours} colours), {found}")
        self.counted_palettes.setdefault(address, (colours, found))

    def add_palette(self, address, colours, found):
        if address >= CARTRIDGE:
            return
        if any(struct.unpack_from(">H", self.image, address + 2 * index)[0] & 0xF111 for index in range(colours)):
            raise SystemExit(f"{address:06X}: no palette of {colours} colours, {found}")
        known = self.screen_palettes.get(address)
        if known is None or known[0] < colours:
            self.screen_palettes[address] = (colours, found)

    def find_palette_readers(self):
        """0F3AE0's colours (its third argument, as many as its second), and the functions that pass one of
        their own arguments on to it (or to one of these), unchanged"""
        self.palette_readers = {PALETTE_LOADER: {2: ("argument", 1)}}
        grown = True
        while grown:
            grown = False
            for position, (address, instruction) in enumerate(self.ordered):
                target = self.call_target(position) if instruction.flow == "call" else None
                if target not in self.palette_readers:
                    continue
                function = self.function_of(address)
                after, arguments = self.prologue(function)
                if after is None:
                    continue
                for argument, colours in list(self.palette_readers[target].items()):
                    pushes = self.pushes(position, argument)
                    if not pushes or len(pushes) != 1 or pushes[0].mnemonic != "move" \
                            or pushes[0].operands[0].mode not in ("areg", "dreg"):
                        continue
                    register = pushes[0].operands[0].reg
                    if register not in arguments \
                            or any(writes(self.ordered[step][1], register) for step in range(after, position)):
                        continue
                    if isinstance(colours, tuple):
                        counts = self.numbers_passed(position, colours[1])
                        if not counts or len(counts) != 1:
                            continue
                        colours = counts.pop()
                    if arguments[register] not in self.palette_readers.get(function, {}):
                        self.palette_readers.setdefault(function, {})[arguments[register]] = colours
                        grown = True

    def sprite_passed(self, position, address, maker):
        argument = SPRITE_MAKERS[maker]
        how = f"argument {argument} of {maker:06X} at {address:06X}"
        for sprite, place in self.pointers_passed(position, argument):
            if place is None:
                self.add_sprite(sprite, how)
        for push in self.pushes(position, argument) or ():
            table = self.table_of(push)
            if table is not None and table not in self.screen_sprite_tables:
                self.screen_sprite_tables[table] = (None, f"its entries go to {maker:06X} at {address:06X}")

    def add_sprite(self, address, found):
        if address & 1 or address + SPRITE_BYTES > len(self.image):
            raise SystemExit(f"{address:06X}: no sprite, {found}")
        self.screen_sprites.setdefault(address, found)

    def walk_screen_sprite_tables(self):
        """A table of sprites: its entries while each is a sprite of the cartridge, up to the next place the
        code names (099344's six, before the word 0F2BD0 reads at 09935C)"""
        named = self.anchors | self.handed
        for table, (_, found) in list(self.screen_sprite_tables.items()):
            stop, entries = min((place for place in named if place > table), default=len(self.image)), 0
            while table + 4 * entries + 4 <= stop:
                sprite = long_at(self.image, table + 4 * entries)
                if sprite & 1 or not 0 < sprite < len(self.image):
                    break
                self.add_sprite(sprite, f"entry {entries} of the table {table:06X}")
                entries += 1
            self.screen_sprite_tables[table] = (entries, found)

    def z80_copy(self, position, address, instruction):
        """0F601C: "lea START.l, A0; lea END.l, A1", then the Z80's RAM into A1 and the copy"""
        operands = instruction.operands
        if instruction.mnemonic != "lea" or operands[0].mode != "abs_long" or position + 5 >= len(self.ordered):
            return
        second = self.ordered[position + 1][1]
        if second.mnemonic != "lea" or second.operands[0].mode != "abs_long":
            return
        for _, step in self.ordered[position + 2:position + 6]:
            if step.mnemonic == "lea" and step.operands[0].mode == "abs_long" \
                    and step.operands[0].value & 0xFFFFFF == Z80_RAM:
                first, stop = operands[0].value & 0xFFFFFF, second.operands[0].value & 0xFFFFFF
                if first < stop <= len(self.image):
                    self.z80_program = (first, stop, f"copied into the Z80's RAM at {address:06X}")
                return

    def screen_places(self):
        """The places the screens' walk found, for the places the code hands over"""
        places = set(self.screen_maps) | set(self.screen_records) | set(self.counted_palettes) \
            | set(self.screen_palettes) | set(self.screen_sprites) | set(self.screen_sprite_tables) \
            | set(self.record_maps)
        if self.z80_program:
            places |= {self.z80_program[0], self.z80_program[1]}
        return places

    def walk_gems(self):
        """The banks 0F6116 sends the driver, in the order of its calls of 0F60FA"""
        first = self.position_of.get(GEMS_INIT)
        if first is None:
            raise SystemExit(f"{GEMS_INIT:06X}: GEMS's start is not in the analysis")
        banks = []
        for position in range(first, min(first + 40, len(self.ordered))):
            address, instruction = self.ordered[position]
            if position > first and address in self.analysis.functions:
                break
            if instruction.flow == "call" and self.call_target(position) == GEMS_BANK:
                values = self.numbers_passed(position, 0)
                if not values or len(values) != 1:
                    raise SystemExit(f"{address:06X}: a GEMS bank that is not a number")
                banks.append((values.pop() & 0xFFFFFF, address))
        if len(banks) != len(GEMS_BANKS):
            raise SystemExit(f"{GEMS_INIT:06X}: {len(banks)} GEMS banks, not {len(GEMS_BANKS)}")
        for (bank, address), kind in zip(banks, GEMS_BANKS):
            self.gems_banks[bank] = (kind, f"sent to the driver at {address:06X}")

    def spans_screens(self, found):
        for address, (width, height, _) in self.screen_maps.items():
            found.setdefault(address, (address + 4 + 2 * width * height, "screen map"))
        for address in self.screen_records:
            found.setdefault(address, (address + SCREEN_RECORD_BYTES, "screen record"))
        for address in self.record_maps:
            if address - 4 not in self.screen_records:
                found.setdefault(address, (address + 4, "screen record's map"))
        for address, (colours, _) in self.counted_palettes.items():
            found.setdefault(address, (address + 2 + 2 * colours, "counted palette"))
        for address, (colours, _) in self.screen_palettes.items():
            found.setdefault(address, (address + 2 * colours, "screen palette"))
        for address in self.screen_sprites:
            found.setdefault(address, (address + SPRITE_BYTES, "screen sprite"))
        for table, (entries, _) in self.screen_sprite_tables.items():
            if entries:
                found.setdefault(table, (table + 4 * entries, "screen sprites' table"))
        if self.z80_program:
            first, stop, _ = self.z80_program
            found.setdefault(first, (stop, "Z80 program"))
        banks = sorted(self.gems_banks)
        for bank, after in zip(banks, banks[1:] + [None]):
            stop = after if after is not None else min(
                (place for place in self.anchors | self.handed if place > bank), default=len(self.image))
            found.setdefault(bank, (stop, self.gems_banks[bank][0]))
