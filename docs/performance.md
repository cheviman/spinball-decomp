# How much of a frame the game takes

The measure behind the 60 fps goal: a step of the game's main loop (`MainLoop`, 0x0D527A, to the wait for
the next frame, 0x0D54B0) has to fit in one frame of the console, **128,005 cycles of the 68000** (NTSC:
3420 master clocks a line, 262 lines, the 68000 at a seventh). A step that takes longer makes the game slow
down: it does not skip frames.

Measured with `mdref` (tools/console/megadrive/reference) on the console model of console-decomp: MAME's
68000 core, the VDP's DMA and FIFO times from Charles MacDonald's table, the DRAM refresh at 2 cycles every 128
and each access of the Z80 to the 68000's bus at 8 cycles of the 68000 (BlastEm's figures, its genesis.c).
**Not yet checked against a cycle-exact emulator (BlastEm) or the console.**

## 2026-11-13, first measure

`tests/controls/toxic_caves.txt`: the title, Start twice, then Toxic Caves' start with Sonic standing on the
pipe (frames 1312-3600).

| | |
|---|---|
| Steps | 2,318 |
| Frames lost (the game did not advance) | 469 of ~2,750, about 1 in 6: the game runs at ~85% speed |
| Step work, median / 90th percentile | ~150,000 / ~169,000 cycles (117% / 132% of a frame) |
| Heaviest step | 222,806 cycles (174% of a frame) |
| DMA | none: the program writes everything to the VDP a word at a time |
| DRAM refresh | ~2,000 cycles a frame (1.6%) |
| The Z80's accesses to the 68000's bus (GEMS) | ~115 a frame, ~900 cycles of the 68000 (0.7%) |

(The per-function table below is from the first measure, without the Z80's accesses: 448 frames lost.)

Where the cycles go (68000 cycles of each function after frame 1300; self = its own instructions, inclusive =
with what it calls; the VBLANK interrupt included):

| Function | Self | Inclusive | Calls a frame | What it is (from the community's notes) |
|---|---|---|---|---|
| 0D574E | 24.4% | 74.9% | 0.8 | updates every animated object, all 256 slots used or not |
| 0D8F22 | 12.6% | 13.7% | 0.8 | ? |
| 0D61EA | 10.2% | 15.6% | 0.8 | ? |
| 0FE784 | 9.4% | 10.1% | 0.8 | ? |
| 0FE376 | 6.7% | 7.0% | 0.8 | ? |
| 0D6796 | 5.4% | 5.9% | 64.7 | ? (decompiled on the Sonic Retro forum in 2019: compares against RAM bounds) |
| 0FEBD0 | 3.6% | 4.1% | 1.0 | called by the VBLANK interrupt |
| 0D5A06 | 3.6% | 7.0% | 23.5 | ? |
| 0FF8E6 | 1.2% | 1.4% | 7.0 | the C library's 32-bit division |

## 2026-11-13, the four tables

`tests/controls/<table>.txt` (the level select's flag poked on, the table's button held at the start, then a fixed
pattern of flippers and moves to frame 5400), with the 36 blanking lines and the Z80's accesses in the model:

| Table | Steps | Frames | Frames lost | Game speed | Step work, median / 90th pct. / heaviest (of a frame) |
|---|---|---|---|---|---|
| Toxic Caves | 3,695 | 4,584 | 889 (19.4%) | 80.6% | 123% / 137% / 194% |
| Lava Powerhouse | 3,240 | 4,413 | 1,173 (26.6%) | 73.4% | 127% / 183% / 278% |
| The Machine | 2,880 | 4,414 | 1,534 (34.8%) | 65.2% | 151% / 198% / 268% |
| Showdown | 1,976 | 2,713 | 737 (27.2%) | 72.8% | 123% / 199% / 280% |

(Steps of up to 8 frames: the game's; a longer one is a screen with a loop of its own.) For 60 fps every step has
to fit in a frame: the heaviest ones are close to three frames' work, the typical ones a quarter to a half more
than a frame.

To do: the same for every table, the bonus stages and the multiball; check the times against BlastEm; name
these functions.
