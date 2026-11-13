# The plan

The decompilation follows the method arcade-decomp's games follow (TMNT, OutRunners, SegaSonic, The Simpsons):
C that does exactly what the original does, checked frame by frame against the reference, with nothing of the
ROM in the game. Then two products from the same C: a Mega Drive ROM that never lags (built from the C with a
modern compiler), and a port with an arcade's presentation (vertical and wide views).

Each step has the check that says it is done.

| # | Step | Done when | Status |
|---|---|---|---|
| 1 | Reference: the original on MAME's cores against console-decomp's Mega Drive (`mdref`) | the game boots, plays every table, sounds; two runs give the same hashes | done (picture from the model's VDP; MAME's VDP as the picture's reference: to do) |
| 2 | Scenarios: control scripts through the whole game | the attract, the four tables, the bonus stages, the multiball, the bosses, the options, 2-4 players, game over, the ending | 4 of them (`tests/controls`: the four tables' starts) |
| 3 | Static analysis without traces | every address the scenarios execute found (now 17,399 of 17,399), and the rest of the code classified | done for what runs |
| 4 | Coverage: every byte of the cartridge explained | 0 unknown bytes; every read table described in `symbols.txt` | 4,526 unknown, 180,679 read but not described; 256,036 described (24.4%) |
| 5 | The data with names and types, and the assets in editable formats with `--check` | sprites and tilesets as PNG (SSC, C2/LZW and the raw sprites), levels, splines, objects, animations, palettes, texts, GEMS music and samples; each extractor rebuilds the bytes exactly | the raw sprites: 6 tables, 457 sprites, as sheets that build back identical (`tools/extract_assets.py --check`); the animations' format read from the engine (`tools/spinball_animation.py`) and walked from the code: 179 definitions (the ones the code passes to make_animated_object or to the two functions that hand theirs on to it, by the level, in animations and in the tables' objects), 10 descriptors, 9 animation lists, 350 animations; the four tables' objects (728, 20 bytes each); every byte the animation engine reads in the scenarios walked; next: the tilesets (SSC, C2/LZW), then the palettes |
| 6 | Lift and scaffold: the program translated an instruction at a time, running natively on console-decomp's runtime | the scenarios give the reference's state hashes frame by frame | not started (the core has the 68000's: m68000/lift.py, translate.py) |
| 7 | The decompiled C | the scenarios frame by frame (state, picture, sound), the structure check at 0, the noise meter at its explained minimum, no read of the ROM by address | not started (the core's m68000/decompile.py) |
| 8 | The SDL build for Windows | it boots, looks and sounds right, plays a table, a script gives the reference's frames | — |
| 9 | The ROM from the C, at 60 fps | built with a modern GCC for the 68000; the scenarios' state per step the same as the original's; mdref's load report: 0 frames lost on every scenario, on the console's timing | — |
| 10 | The arcade port: vertical and wide | (its own plan, after 8) | — |

Measures behind step 9: docs/performance.md. What is known of the game: docs/research.md. The console's references:
tools/console/megadrive/docs/references.md.
