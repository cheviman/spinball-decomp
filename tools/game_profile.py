"""
Name:        game_profile.py
Description: what the shared decompiler core (tools/core) needs to know of Sonic the Hedgehog Spinball: where
             the game is, its cartridge, and its settings
Version:     0.1.0
Created:     13-11-2026
Modified:    22-11-2026
Author:      Sebastian Toyos

The core (arcade-decomp: the decompiler, the CPU frontends, the analysis, the checks) is the same for every
game; the console (console-decomp, tools/console) is the same for every Mega Drive game; this module gives the
core this game's: the repository's root, the cartridge's module (spinball_rom) and the names the generated
files carry. The decompiler's settings come here as the steps that need them are reached; until then the
core's neutral defaults stand.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "core"))

import spinball_rom as rom  # noqa: E402,F401

ROOT = Path(__file__).resolve().parents[1]
GAME = "Sonic the Hedgehog Spinball (Mega Drive / Genesis, Sega 1993)"    # in the generated files' headers
ROM_SET_TITLE = "Sonic the Hedgehog Spinball (USA, GM MK-1537 -00)"
CPU = "68000"
BINARY = "spinball"                             # its executables
GUARD = "SPINBALL"                              # the generated headers' include guards
REFERENCE = "mdref"                             # the reference (tools/console/megadrive/reference)
ANALYSIS = "spinball_analysis"                  # the core's 68000 analysis with this compiler's ways (tools/spinball_analysis.py)
DISASSEMBLER = "m68000.disassembler"
CODE_START = 0x000200                           # after the vectors (000000-0000FF) and the header (000100-0001FF)
DATA_WALK = "data_walk"                         # the data the engines take, walked (tools/data_walk.py)
READERS = {                                     # the code that reads each kind of data: the coverage says, for
    "animation engine": [(0x0D58B0, 0x0D60E2)], # each, what it read that no table describes
    "SSC decoder": [(0x0D6B88, 0x0D6C2A)],
    "tile loader": [(0x0F3BB8, 0x0F3C06)],
    "C2 decoder": [(0x0F5A7A, 0x0F5B9E)],
    "plane drawers": [(0x0D8D0E, 0x0D8F22)],
    "collision code": [(0x0DB900, 0x0DBCEA), (0x0DBD1E, 0x0DBF62), (0x0DC3DE, 0x0DCE40), (0x0DCFC0, 0x0DDCC4),
                       (0x0DE08E, 0x0DE774), (0x0E1D10, 0x0E1ECA)],
    "palette code": [(0x0D6C2A, 0x0D7AB8), (0x0D85A0, 0x0D85F4), (0x0D863E, 0x0D8674), (0x0D873A, 0x0D8BB6)],
}

# The translation scaffold (tools/recompile.py: the core's m68000/translate.py), the program translated an
# instruction at a time
TRANSLATOR = "m68000.translate"
# where the program waits for its next frame: the branches back of the loops that only read and test until an
# interrupt changes what they read (tools/frame_waits.py finds them by that rule and checks this list and
# runtime/src/frame.c's): the VBLANK's frame count at FF0000 (the main loop's 0D54C2, the demo's 0D47B6, 0D3E0C,
# 0D3E20), the front end's VBLANK clearing FFF2C9 (0F38CE), the VBLANK serving the requests at FF559E and the palette's
# command at FF0058, the Z80's bus, the boot; and 0D48E2's state machine, which goes round (0D4EE0) while its state
# waits for the timer the VBLANK counts down (runtime/src/frame.c says when). The program has nothing to do when it
# takes one: with frame timing the board moves on to its next frame there
FRAME_WAIT = (0x00024C, 0x0D3E0C, 0x0D3E20, 0x0D41DA, 0x0D4328, 0x0D47B6, 0x0D54C2, 0x0D84D6, 0x0D86C4,
              0x0D86E2, 0x0D86FE, 0x0D871A, 0x0D8736, 0x0F38CE, 0x0F5FBC, 0x0F600E, 0x0F60B6, 0x0FF59C, 0x0FF7DA, 0x0FF808,
              0x0D4EE0)
REPLACED_CODE = {}
# the reference runs the program as the translated and the decompiled game run it when the scenarios compare them
# (tools/check_scenarios.py: mdref --timing frames, md/frames.h)
REFERENCE_OPTIONS = ["--timing", "frames"]                              # the console runs the whole program: nothing in its place

# The decompiled C (tools/decompile.py: the core's m68000/decompile.py, into build/decompiled/)
DECOMPILER = "m68000.decompile"
DECOMPILED = "22-11-2026"                       # when build/decompiled/ was first written (its files' headers)
# the whole program runs in supervisor mode: it never clears S (its writes of SR set the interrupt mask, ori #$700,
# or put back an SR it saved), so a privileged instruction takes no exception anywhere
SUPERVISOR_CODE = ((CODE_START, 0x100000),)
# its C compiler's functions save the address registers they use as they start ("link A6", "movem.l ..., -(A7)")
# and put them back: the function pointers the code keeps in A3-A5 (0DFAE0's "movea.l #$DE9D4, A3") hold across its
# calls
CALLEE_SAVED = True
# symbols.txt names every piece the translation scaffold split the C functions into (1,736): a piece no call
# reaches (a switch's case, a branch's target) is a place in its function, which the decompiler writes whole (516)
LABELS_NOT_ENTRIES = True
# the 9 calls through A0/A4/A5 whose address comes from the caller or the game's data: call_code(address)
DYNAMIC_CALLS = True
