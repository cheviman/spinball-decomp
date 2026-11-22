"""
Name:        decompile.py
Description: runs the shared core's decompile.py (tools/core) for this game: the decompiled C, the program as C
             functions (the core's m68000/decompile.py)
Version:     0.1.0
Created:     22-11-2026
Modified:    22-11-2026
Author:      Sebastian Toyos

The script is the core's (arcade-decomp, which tools/core holds); tools/game_profile.py tells it about this game.
Usage: python tools/decompile.py [cartridge] [--check] [the core's other options]. It writes build/decompiled/
(--out picks another place) from the user's own cartridge: nothing it writes may be redistributed while the C still
reads the cartridge by address.
"""
import runpy
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]
if "--out" not in sys.argv:
    sys.argv += ["--out", str(TOOLS.parent / "build" / "decompiled")]
runpy.run_path(str(TOOLS / "core" / "decompile.py"), run_name="__main__")
