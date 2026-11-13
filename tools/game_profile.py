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
ANALYSIS = "spinball_analysis"                  # the core's 68000 analysis with this compiler's ways (tools/spinball_analysis.py)
DISASSEMBLER = "m68000.disassembler"
CODE_START = 0x000200                           # after the vectors (000000-0000FF) and the header (000100-0001FF)
DATA_WALK = "data_walk"                         # the data the engines take, walked (tools/data_walk.py: sprite tables)
