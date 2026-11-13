"""
Name:        disassemble.py
Description: runs the 68000 static analysis for this game (the core's, tools/core/m68000/analysis.py, with
             tools/spinball_analysis.py's additions): the program's code found without traces, its listing and
             a report
Version:     0.1.0
Created:     13-11-2026
Modified:    13-11-2026
Author:      Sebastian Toyos

The analysis is the core's (arcade-decomp, which tools/core holds), with what this game's compiler does
(tools/spinball_analysis.py); tools/game_profile.py tells it about this game. Usage:
python tools/disassemble.py [cartridge] [--trace executed.txt ...]
"""
import runpy
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]
runpy.run_module("spinball_analysis", run_name="__main__")
