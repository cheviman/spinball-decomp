"""
Name:        game_profile.py
Description: what the shared decompiler core (tools/core) needs to know of Sonic the Hedgehog Spinball: where
             the game is, its cartridge, and its settings
Version:     0.1.0
Created:     13-11-2026
Modified:    13-11-2026
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
ANALYSIS = "m68000.analysis"                    # the static analysis and the disassembler of the 68000
DISASSEMBLER = "m68000.disassembler"
CODE_START = 0x000200                           # after the vectors (000000-0000FF) and the header (000100-0001FF)
# the C compiler's switches: a jump through a table of words relative to the table (core/m68000/analysis.py;
# main at 0D5230: "move.w $D52C2(PC,D0.l), D0", "jmp $D52C2(PC,D0.w)" after "moveq #6, D1; cmp.l D1, D0; bhi")
SWITCH_TABLES = True
# the front end's sequencer jumps through a table of addresses read relative to the PC (0F4562 "movea.l
# $F459A(PC,D0.w), A0", 0F4566 "jmp (A0)"; core/m68000/analysis.py)
PC_TABLES = True
# a call through a register that holds known functions keeps what they all keep (0F2F96 keeps $F3148 in A2 across
# its calls through A3 and A4; core/m68000/analysis.py)
KNOWN_CALL_TARGETS = True
