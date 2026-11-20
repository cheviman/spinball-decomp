"""
Name:        recompile.py
Description: runs the shared core's recompile.py (tools/core) for this game: the translation scaffold, the
             program translated into C an instruction at a time (the core's m68000/translate.py)
Version:     0.1.0
Created:     20-11-2026
Modified:    20-11-2026
Author:      Sebastian Toyos

The script is the core's (arcade-decomp, which tools/core holds); tools/game_profile.py tells it about this game.
Usage: python tools/recompile.py [cartridge]. It writes build/generated/ from the user's own cartridge: nothing it
writes may be redistributed.
"""
import runpy
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]
runpy.run_path(str(TOOLS / "core" / "recompile.py"), run_name="__main__")
