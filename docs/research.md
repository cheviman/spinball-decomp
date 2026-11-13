# Sonic Spinball (Mega Drive / Genesis): what is known before we start

Reconnaissance notes (step 0 of the decompilation method), 2026-11-13. Facts carry their source; anything
not checked against the ROM yet is marked **(to verify)**.

## The ROM

| Version | CRC32 | MD5 | SHA-1 |
|---|---|---|---|
| USA (our target) | 677206cb | 841e347b30a6e298ee2b0c722f19fe74 | 24bf6342b98c09775089c9f39cfb2f6fbe7806f7 |
| Europe (later, bug fixes) | aea0786d | 800c7c12bc1eae7ddb61186875b29733 | f61a568314133b60de82ac162b5b52473adc9e1c |
| Japan | acd08ce8 | 3a12dc6b4f41681e0dc0ae3b2f894b4f | 43b2fdac9c747d6f6a629347c589599074408cd9 |
| USA, "alternate music" (late prototype leaked by SNEAKERS) | e9960371 | 3fb84c8a3dcc64af079e4c37cd2ec8e0 | 8f372e3552e309d3462adeb700242b251f59def1 |

Hashes from Eggplant891/spindisasm `doc/rom_hashes.txt`; ours matches the USA line. 1 MiB, header
`GM MK-1537 -00`, `(C)SEGA 1993.SEP`, checksum in the header is correct (0x2A3F). An August 1993 prototype
also exists.

## How it was made

- Programmed mostly by **Polygames** (Lee Actor, Dennis Koble; ~90% of the code), art, design and music by
  Sega Technical Institute, in about nine months (Sonic Retro, Development page).
- Written in **C**, unusual for the Mega Drive in 1993 (Sonic Retro). Ghidra shows a mix of C and assembly;
  the compiler is believed to be an **early Sierra Systems C**, an exact version nobody has found, so a
  byte-matching decompilation is not possible today (Sonic Retro forum, 2019 and 2026). Our method does not
  need it: the C is checked by behavior, frame by frame, not by recompiling to the same bytes.
- What the ROM itself shows (our count): `LINK A6` frames (86), the caller pops the arguments (770
  `lea n(sp),sp`), switch tables `add.l d0,d0 / move.w tbl(pc,d0.l) / jmp tbl(pc,d0.w)`, multiplies by
  constants strength-reduced (`index * 76` for the player array), runtime helpers with register arguments
  (32-bit multiply at 0x0FF8B8, called 137 times; 32-bit divide at 0x0FF8E6, 90 times), `sprintf`, `abs`,
  a function the disassembly calls `main`, and `jsr x(pc) / nop` pairs (calls shortened by the linker).
- Sound: **GEMS** (Recreational Brainware's driver, Z80) with its 68000 library (`GEMS_stdstartup`,
  `GEMS_stdcmdwrite`, `GEMSStartSong`...). Music by Howard Drossin and others.

## Layout of the ROM

| Range | What | Source |
|---|---|---|
| 0x000000–0x0001FF | vectors, header | ROM |
| 0x000200–~0x0006FF | boot, TMSS, region check (assembly) | disassembly |
| 0x0006FE | player animation pointers | forum (Eggplant891) |
| 0x000DFC–0x0013DB | 47 palettes of 32 bytes (the "48th" is not a palette) | SilverTheGoldfish docs, forum |
| 0x0011BC–0x00139C | bonus stage palettes | forum |
| 0x0013DC–0x03909D | uncompressed sprites, one table per set: player 0x13DC, global 0xE47A, Toxic Caves 0x12B0C, Lava Powerhouse 0x20666, The Machine 0x2B7A4, Showdown 0x318EE | forum |
| 0x03909E, 0x07E55A, 0x098ECA, 0x07ED68 | animation pointers per level (TC, LP, TM, SD) | forum |
| 0x0394AA... 0x081EB6 | level tilesets, SSC compressed (TC FG 0x394AA, BG 0x3DBB2; SD 0x4FEE4/0x53214; LP 0x64BB6/0x67672; TM 0x7F29C/0x81EB6), font 0x7DA22 | SSCDec, forum |
| 0x0A1388–0x0A3126 | "C2" (LZW) graphics: intro 0xA3126, Veg-O-Fortress 0xA1B8C, Robotnik's ship 0xA30BC | forum |
| 0x0AA0B0 | GEMS patches | forum |
| 0x0AB4AB–0x0BDD2E | GEMS modulators, sequences (0xAB502), samples (0xB39DD) | forum (2010) |
| 0x0BDE06 | options screen frames (SSC) | SSCDec |
| 0x0BE248–0x0BFCAF | text in ASCII: on-screen messages (with `%d`/`%s`), options, credits | ROM |
| 0x0BFBE0–0x0BFC98 | per-level tables: tilesets, 32x32 "brushes", layouts, collision, palettes, size, camera start, music, game-over timer | forum |
| 0x0C150C | per-level animation pointer arrays | forum |
| 0x0C151C–0x0C7653 | ring counts, ring and object definitions per level | forum |
| 0x0D3B54–0x0D3D4B | options and credits string tables | disassembly |
| 0x0D3D4C–~0x0FFA80 | **all the game code** (~180 KB, ~450 functions) | ROM, disassembly |

## The engine

- **Main loop** (`main`, 0x0D5230; the loop itself at 0x0D527A): reads the pads captured by the vertical interrupt, runs one step of the
  current game mode (`GameMode` at 0xFF3CB4: 0 front end, 1 level intro, 2 level, 3 multiball, 4 boss
  chamber destruction, 5 ?, 6 tally and bonus stage), then waits until the frame counter (0xFF0000) changes.
  If a step takes more than one frame there is no wait and no frame skipping: **the game simply runs
  slower**. That is the slowdown.
- **Vertical interrupt** (0x0D3D4C): counts frames, decrements a timer (0xFFF1FA) unless paused, sends
  sprites/tiles/scroll to the VDP (0x0D873A, 0x0D4F2A, 0x0FEBD0, 0x0DF89C) and reads the pads. Some timers
  run per vertical interrupt and others per game step, so the original's timing depends on how much it lags.
- **Objects**: game objects (34 bytes, array at 0xFF784C), animated objects (64 bytes, 256 slots at 0xFFAD24
  in four pools of 64) and a sprite pool of 256. **Every frame the update loop (0x0D574E) walks all 256
  slots whether used or not**; that, and the sprite pool, are the main known cause of the slowdown.
- **Player**: 76-byte records, an array of four (4 players take turns), at 0xFF5758; current player at
  0xFF5736.
- **Collision** uses **splines** (one-sided line segments with flags: walkable, triggers, death zones,
  teleports), radial collision for bumpers and enemies and boxes for a few objects, organised in 16x16 grids
  of 128x128-pixel cells; sprites and animation are activated by 6x8 sectors of 360x264 pixels around the
  camera. Collision and drawing are separate.
- **Graphics**: sprites are stored as linear 4bpp bitmaps cut in pieces of up to 32x32, loaded into VRAM by
  an allocator while the game runs **(to verify: how they are converted to tiles and sent, CPU or DMA)**;
  levels are 8x8 tiles grouped into 32x32 brushes; rings have their own code and structures.
- **The tables' planes** (`tools/spinball_levels.py`): plane A (C000) is the table, plane B (E000) its
  background, each a map of 32x32 brushes (a word: the brush in bits 0-10, mirrored by bits 11 and 12) as wide
  as 0D8D04 says (40, 48, 46, 56; 10 for the options screen, level 4) and as high as BFC70 says (64 rows), and
  its brushes (4x4 VDP cells; plane B's tiles count from its own first, after plane A's). Showdown's background
  has 48 rows: its collision begins right after. The drawers draw a cell more than the screen shows, and read
  the row after each map. The options screen's brushes begin on the last two bytes of its SSC tiles: the end's
  second byte, 01, is the first brush's first cell (tile 1), which is why that one SSC end is not 00 00.
- **The collision** (`tools/spinball_levels.py`): each table's, from BFC40 by the level (FFF1F4), is 16x16
  sectors of 128x128 pixels, a word each placing its list (in the sectors' order), and the lists: a count, then
  records of 12 bytes, a segment (x0, y0, x1, y1) or, with bit 15 of the flags, a circle (x, y, radius), the flags
  (bits 9-14 what touching it does: a game object's, a flag at FF3FFC, a call of 0E1BBE...; bits 0-3 one way
  only; bit 7 preferred) and the number of the object or flag. The community's "collision tiles" of 128x128 are
  these sectors. The flippers' collision is a list of the same kind by their position (2 circles, 2 segments),
  one table a side (C0A86, C0A96 for the mirrored); their places come by the table from C08BE.
- The code at 0D91FC reads the flags (+8) of a record through a pointer that can be 0: it reads the cartridge's
  bytes 000008-000009 (the C has to read them the same way).
- Compression: **SSC** (an LZSS) for the tables' tiles, the HUD's and the options'; **C2** (an LZW of 9 to
  11-bit codes, not 12: the decoder at 0F5A7A stops widening at 11; its masks' table at 09BCD2 has a fourth word,
  FFF, it never reads) for the cutscenes, the main menu and the bonus stages. Both are read from the game's
  decoders in `tools/spinball_compression.py`, with encoders that give all 18 sets back byte for byte: SSC is the
  LZSS of Mark Nelson's *The Data Compression Book* (1991: 12-bit place, 4-bit length, break even 1, 17 bytes
  looked ahead, place 0 unused and the end, the first byte at place 1, its binary tree) written in the bytes of
  Okumura's LZSS.C (a byte of flags, the place's low byte, its high four bits over the length); C2 is a plain
  greedy LZW that starts over once entry 7FF is taken. SonicSpintool (2026) has an SSC decoder but its encoder
  stores every byte as it is; its C2 encoder searches for the smallest output, not the original's.
- Options at 0xFF035E: players (1–4), SPEED (normal/fast: changes the force of collisions, 0xFFF8D8 = 0x0E or
  0x13, not the simulation speed), music, flipper buttons.

## Known work on the frame rate

- An overclocked Mega Drive makes the game "transform" (forum, 2024).
- Eggplant891 (2024–2026): with the object and sprite pools cut from 256 to 16–64 entries, The Machine almost
  holds 60 fps; with rings and scenery removed too, Toxic Caves runs at 60 "crude and unstable, not a true
  code optimisation". With a few real optimisations (skipping unused sprites and objects) there is "a
  noticeable uplift", but it still drops with many objects on screen. The remaining losses are attributed to
  collision with triggers and tiles. Profiled with md-profiler on his disassembly with symbols.
- So nobody has a version at 60 fps that keeps all the game.

## Existing work we can learn from

| What | Where | License |
|---|---|---|
| Andlabs' disassembly (IDA), builds the same ROM with asm68k | github.com/sonicretro/spindisasm | none ("informational and educational purposes only") |
| Eggplant891's fork: 141 commits, split sources, symbols, notes on objects, player, animation, OSD, Ghidra project | github.com/Eggplant891/spindisasm | none |
| SonicSpintool: editor (sprites, tiles, levels, splines, objects), SSC and C2 codecs | github.com/Eggplant891/SonicSpintool | GPL-3.0 |
| AlpasNet's SpinTool fork (title, bonus and intro formats; sent upstream as SonicSpintool PR #5) | github.com/AlpasNet/SpinTool (not found on 2026-11-13) | (to verify) |
| Forum thread "ASM – Spinball disassembly" (2010–2026) | forums.sonicretro.org/threads/spinball-disassembly.22874/ | — |
| GEMS tools | segaretro.org/GEMS, forum thread 18892 | — |

These repositories have no license, so we read them and learn the facts (addresses, formats, names), but
copy none of their files into ours; SonicSpintool is GPL-3.0 and is used the same way. What is downloaded for
this game lives in `external/`, which git ignores.

## References for the console

Sega's manuals, Nemesis's timings, BlastEm's source and the GEMS research serve every Mega Drive game, so they
live with the console: console-decomp's `megadrive/docs/references.md` (this repository's `tools/console`), and
the material in its `external/megadrive/`.

## Sources

- https://info.sonicretro.org/Sonic_the_Hedgehog_Spinball/Development
- https://info.sonicretro.org/Sonic_the_Hedgehog_Spinball/Region_coding
- https://forums.sonicretro.org/threads/spinball-disassembly.22874/ (pages 1–6)
- https://github.com/sonicretro/spindisasm, https://github.com/Eggplant891/spindisasm
- https://github.com/Eggplant891/SonicSpintool, https://github.com/SilverTheGoldfish/SonicSpinballDocumentation
