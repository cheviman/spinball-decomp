# Sonic the Hedgehog Spinball — decompilation

A decompilation of Sega's 1993 Mega Drive / Genesis game *Sonic the Hedgehog Spinball* (a 68000 program
written in C, with a Z80 running the GEMS sound driver) into readable C that does exactly what the original
does, checked frame by frame against MAME's cores.

**This repository contains no game data.** You bring your own cartridge dump; the tools check it, and
everything they take from it stays on your computer.

Work in progress: the reference, the static analysis and the coverage are done; the data's formats, the
decompiled C and the builds come next (`docs/plan.md`).

## Status

As of 2026-11-20:

- [x] Cartridge verification (USA, `GM MK-1537 -00`) by CRC32 and SHA-1
- [x] Reference: the original program on MAME's 68000 core against the Mega Drive in C of
      [console-decomp](https://github.com/cheviman/console-decomp) (`mdref`), with MAME's Z80 and PSG and
      ymfm's YM2612: it boots, plays every table, makes its music, and measures how much of each frame the game
      takes
- [x] Control scripts for the four tables (`tests/controls/`): the level select's flag on and the table's
      button held at the start, then a fixed pattern of flippers and moves; and one through the four bonus
      stages (`bonus_stages.txt`); and four through the front end with real input: the attract with nothing
      pressed (`attract.txt`), Toxic Caves' three balls lost to the high scores (`game_over.txt`), every option, the
      level select's and the credits' buttons and the credits (`options.txt`), and four players' twelve balls lost by
      turns (`players.txt`); and five through the rest of a game: the multiball reached and played
      (`multiball.txt`: the rings poked one short, then flippers a search on the reference found), that game to the
      top of the high scores (`high_scores.txt`), the four boss chambers destroyed with mode 4 poked (`bosses.txt`),
      a continue won and used (`continues.txt`), and the ending and the credits after Showdown (`ending.txt`); and
      the four tables played, the ball kept in play by flippers a search on the reference found (`*_played.txt`); all
      run with `--z80-rom-reads`, as their frames were found
- [x] Static analysis without traces (arcade-decomp's 68000 analysis, with this compiler's switches and
      calls in `tools/spinball_analysis.py`): 48,553 instructions in 444 functions, and every one of the 33,006 addresses the eighteen scenarios
      execute is found; the 27 functions reached only through data are in `symbols.txt` with how they were found
- [x] The cartridge's bytes classified: 16.7% code, 81.3% described data, 0.4% unknown; the rest is data the
      code reads or points at, waiting for its formats
- [x] The uncompressed sprites: their format read from the code (`0D7D02`-`0D7FB0`), the six tables walked
      from where the code hands them over (`tools/data_walk.py`), and the 457 sprites extracted as one sheet
      per table that builds back into the cartridge's bytes exactly (`tools/extract_assets.py --check`)
- [x] The animations and the tables' objects walked from the code; the tiles: SSC (an LZSS: Mark Nelson's tree
      and Okumura's bytes) and C2 (an LZW of 9 to 11 bits) read from the game's decoders, with encoders that give
      every one of the 18 sets back byte for byte, extracted as PNG sheets (`tools/spinball_compression.py`)
- [x] The tables' planes: their maps of 32x32 brushes and the brushes, as the drawers read them, as CSV and text
      that build back byte for byte, with a picture of each plane (`tools/spinball_levels.py`)
- [x] The tables' collision (sectors of segments and circles) and the flippers' (their shapes by their position),
      as text that builds back byte for byte, with a picture of each table's collision
- [x] The palettes and their colour cycles, as text that builds back byte for byte; the tables' planes pictured
      in their own colours
- [x] The texts, found from the code that reads them, as text that builds back byte for byte
- [x] The front end's screens (their maps, palettes and sprites, and the Z80's program) and the scripts of its
      sequencer, walked a command at a time from the code that passes them (`tools/walk_sequences.py`)
- [ ] The data with names and types, and the assets as editable files that build back byte for byte: sprites
      and tilesets as PNG (raw, SSC and LZW), levels, collision splines, objects, animations, palettes, texts,
      the GEMS music and samples
- [ ] The decompiled C, checked frame by frame (state, picture, sound) against the reference
- [ ] The game in a window on Windows (SDL), built from the decompiled C

## Getting started

Requirements: Python 3.10 or newer, CMake 3.20 or newer, and a C11 / C++20 compiler (Visual Studio Build Tools
on Windows).

1. Clone with the submodules (`tools/core` is [arcade-decomp](https://github.com/cheviman/arcade-decomp)'s
   `simpsons` branch, which has the 68000's decompiler; `tools/console` is console-decomp):

   ```bash
   git clone --recursive https://github.com/cheviman/spinball-decomp
   ```

2. Put your dump of the USA cartridge in `rom/`: the 1 MiB file, or a .zip holding it, under any name (CRC32
   `677206CB`, SHA-1 `24bf6342b98c09775089c9f39cfb2f6fbe7806f7`).

3. Build the reference into `build/bin/`:

   ```bash
   cmake -S . -B build/msvc
   ```

   ```bash
   cmake --build build/msvc --config Release --target mdref
   ```

4. Run a table and see its load (the main loop's step at `0D527A`, its wait for the next frame at `0D54B0`):

   ```bash
   build/bin/mdref --script tests/controls/the_machine.txt --step D527A --idle D54B0
   ```

5. The static analysis (`build/listing/spinball.s` and `report.txt`):

   ```bash
   python tools/disassemble.py
   ```

   and the coverage, from a scenario's run (`build/listing/coverage.txt`):

   ```bash
   mkdir -p build/scenarios/the_machine
   ```

   ```bash
   build/bin/mdref --script tests/controls/the_machine.txt --trace build/scenarios/the_machine/executed.txt --rom-reads build/scenarios/the_machine/rom_reads.txt
   ```

   ```bash
   python tools/coverage.py --trace build/scenarios/the_machine/executed.txt --reads build/scenarios
   ```

`mdref` without options prints its usage; it also writes per-frame hashes, pictures (BMP), the sound (WAV),
the code a run executes and the cycles of each function (`--profile`).

## Changing the decompilation

There is no C yet. What the tools know of the program lives in `symbols.txt` (names, and what the analysis
cannot work out, each with how it was found) and `tools/game_profile.py` (the settings the shared core reads).

## Layout

```
symbols.txt            the program's names and what the analysis cannot see by itself
runtime/               the game's side of the runtime: its cartridge (rom_set.c)
tests/controls/        control scripts: the scenarios the reference and the game run
tools/                 the game's tools: its profile, its cartridge's module, the core's scripts for it,
                       spinball_analysis.py (what this game's compiler does that the core's analysis does not follow),
                       the formats (spinball_*.py), the walk of the data from the code (data_walk.py, walk_*.py by
                       subject) and the assets' extractor
tools/core/            arcade-decomp (submodule): the decompiler, the 68000's frontend and analysis
tools/console/         console-decomp (submodule): the Mega Drive in C and mdref
docs/                  research.md (what is known of the game), plan.md, techniques.md (the
                       ways of working that found the formats)
rom/                   your cartridge (not in the repository)
external/              other people's disassemblies, for reference (not in the repository)
build/                 builds, listings, scenario runs (not in the repository)
```

## The assets

They come out of your cartridge into `assets/` (not in the repository) as files that common tools open, and
build back into the cartridge's bytes exactly:

```bash
python tools/extract_assets.py
```

```bash
python tools/extract_assets.py --check
```

So far: `assets/sprites/`, a 4-bit indexed PNG sheet per sprite table (Sonic, the common sprites, and each
table's own), each sprite drawn whole, and `sprites.txt` with where each sprite and its pieces are. The colours
are grey levels by pen until the palettes the game shows them with are known. Still to come: the tilesets (SSC and
LZW compressed), the levels and their collision, the objects and their animations, the palettes, the texts, and
the GEMS music and samples.

## Legal

- This project is licensed under the BSD 3-Clause License; see `LICENSE`.
- No ROM contents (program, graphics, sound, data) and no extracted assets are distributed by this project;
  they come from your own cartridge. The decompiled C, when it comes, is the game's program in a new form:
  logic only, with names and comments written for this project.
- The reference tools build MAME's and ymfm's code (BSD-3-Clause) from the submodules; see their `LICENSE`
  files.
- What is known of the game builds on the community's research, credited in `docs/research.md`: Andlabs'
  disassembly, the work of Wafer, Eggplant891 (Sonic Spintool) and the Sonic Retro forum.
- Sonic the Hedgehog and Sonic Spinball are trademarks of SEGA. This project is not affiliated with or
  endorsed by SEGA.
