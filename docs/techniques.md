# Techniques

What this decompilation found out how to do, beyond reading the code: the ways of working that turned up the
formats and settled them. Each says where it lives, what it found here, and whether it would serve another game.

## 1. Every byte a reader reads is walked

The reference records every byte of the cartridge each instruction reads as data (`mdref --rom-reads`). The
coverage (`tools/coverage.py --reads`, the core's) groups those reads by the code that reads each kind of data
(the profile's `READERS`: the animation engine, the two decompressors, the plane drawers, the collision code,
the palette code) and lists the bytes each one read that no table describes.

That turns "the format looks complete" into a count that must be 0, and every time it was not 0 it pointed at
something new:

- the two functions that pass their second argument on to `make_animated_object`;
- the flippers' collision shapes, read by the collision code;
- the colour cycles, read by the palette code;
- the row the drawers read past each map, and the brushes its words would name;
- the VBLANK's vector, which mdref counted as read by the interrupted instruction (fixed in console-decomp).

It serves any game, so it lives in the core (arcade-decomp, `simpsons`, 49ac220): a game gives its profile a
`READERS`. What it still lists for Spinball is honest: the 52 bytes of texts the drawers read past the options'
map and the byte the C2 decoder reads past the cutscene's tiles, until the texts and what follows are described.

## 2. What a call gets, in the game's C

The game's C pushes the arguments last to first and keeps D2-D7/A2-A6 across a call (`tools/walk_patterns.py`).
So what a call gets is found back from the call one push at a time, following the jumps and branches that come
in among the pushes (`pushes()`, `passed()`). What a function does with its arguments comes out of its prologue
(`movem.l` then `move(a).l (d,A7), Rn`: `prologue()`). A function that loads an argument and pushes that same
register, unchanged, to `make_animated_object` passes the definition on (`find_makers()`: 0E1ECA and 0E1F5C,
found this way).

It serves code compiled from C with arguments on the stack. Konami's and Sega's arcade games in arcade-decomp are
assembly, so it stays here until another C game needs it.

## 3. A table's length is the bound of its index

The code that reads a table says how long it is, with whatever bounds the index:

- a switch: `moveq #N, Dk; cmp.l Dk, Dn; bhi` (`tools/spinball_analysis.py`);
- a loop: `cmpi.w #N, Dn; blt` (the tables' objects: 173, 211, 186, 158);
- a counter that wraps: `cmpi.w #N, COUNTER; blt; clr.w COUNTER` (the colour cycles: 5, 6 and 9 colours);
- the level: `move.w FF75B0, Dn` (or through a register that holds FF75B0), a scale (`add.w Dn, Dn`,
  `lsl.w #2`, none), `movea.l #TABLE, An`, `(An,Dn.w)`: four entries, each as big as the read.

The first two are the core's 68000 analysis' now (`bound_tables()`: a counter or a loop counting from 0); it
found the colour cycles and two tables nobody had (C3226, six pointers the collision code walks for Toxic Caves;
C4734, four words), and nothing in TMNT or The Simpsons, whose coverage came out the same. Each of these replaced
a table typed in by hand. The ones still typed in (`LEVEL_VALUES`' palettes, `FLIPPERS`'
shapes and boxes, `PALETTES`) are read in ways these patterns do not cover yet, and each says where.

It serves any game: the bounds are the CPU's, not the compiler's.

## 4. The original compressor, byte for byte

To give the cartridge's compressed bytes back from an edited asset, the encoder has to choose what the original
chose. The way that worked:

1. Port the game's decoder and check its output against the reference's VRAM.
2. Measure the original's choices: for every reference, the longest match available, and which of the equal
   ones it took (nearest, farthest, other). SSC always took the longest, but not always the nearest.
3. Recognise a known implementation by its constants. Place 0 "unused" and also "the end", the first byte at
   place 1, 17 bytes looked ahead, break even at 1: Mark Nelson's LZSS (*The Data Compression Book*, 1991),
   written with Okumura's byte layout.
4. Implement that implementation's own data structure, quirks included: Nelson's binary tree, where a string as
   long as the best takes its place (`>=`), and a node deleted takes the last of its smaller ones. Okumura's tree
   with the same rule matched the first 4 KB and failed after the window wrapped.
5. Keep what the data carries but the decoder ignores: the options' SSC end is `00 01` because its brushes begin
   on those two bytes.

C2 turned out to be a plain greedy LZW that starts over once entry 7FF is taken. All 18 sets build back
identical (`tools/spinball_compression.py`).

It serves any game whose data a known tool compressed: measure the choices, then find the tool.

## 5. A format is checked against the console, not against itself

A decoded format reads back consistently whether it is right or not. What settles it is the console's state in
the reference (`mdref --dump`):

- the tiles, found whole in the VRAM;
- the planes, rebuilt from maps and brushes and compared with the nametables cell by cell. That showed which
  set is the background and that the drawers read a row above the top;
- the palettes, compared with the CRAM. Every colour matched but the ones the cycles change, which led to the
  cycles.

It serves any game on any board: build the picture's memory from the data and compare.

## 6. What the C will have to read the same way

The original reads the cartridge in ways a C that reads named data would not:

- through pointers that can be 0: 0D91FC reads a record's flags at +8 from a pointer that can be 0, which reads
  the cartridge's 000008-000009; 0F3EB8 copies to the VRAM from address 0;
- data that overlaps: the options' brushes over the end of their SSC tiles;
- past the data: the C2 decoder's two bytes after each stream; the drawers' row past each map.

The decompiled C has to read those bytes the same way, or the frames differ.

## Where else they went (13-11-2026)

- arcade-decomp (`simpsons`, 49ac220): the per-reader read check (1) in `coverage.py`, the counter and loop
  bounds (3) in the 68000's analysis.
- console-decomp: the vector fix (b938084).
- The kit's skills: 1, 3 and 5 in `kit-descompilacion-arcade`'s step 6, 4 in its lessons ("Compresion"), and
  4 and 6 in `descompilado-prolijo`'s assets.
