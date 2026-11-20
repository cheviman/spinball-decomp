"""
Name:        frame_waits.py
Description: finds the program's frame waits by one rule and prints them.
Version:     0.1.0
Created:     20-11-2026
Modified:    20-11-2026
Author:      Sebastian Toyos

The rule: a frame wait is the conditional branch (bcc, not dbcc) back to a loop of at most 24 bytes whose
instructions only read and test: tst, cmp, cmpi, cmpa, btst, moveq, and move/and/andi into a data register Dn
(move/moveq set a register; and/andi only on a register the loop set before in the same pass), with no write to
memory, no address register written, no (An)+ or -(An), no call, and no other branch but forward ones that stay
in the loop (0D84C2 picks the bit it tests by D2). Such a loop changes nothing,
so only an interrupt can end it: the program has nothing to do until then. Besides them, the waits the rule
cannot see, loops that do work but go round with nothing to do until an interrupt (CONDITIONAL; runtime/src/frame.c
says when each is idle).

Usage: python tools/frame_waits.py [--check]. It reads build/listing/spinball.s from the repository root; --check
also compares the waits found with tools/game_profile.py's FRAME_WAIT and runtime/src/frame.c's
md_game_frame_waits[].
"""
import re
import sys
from pathlib import Path

# a listing line: "    ADDRESS  OPCODE  ARGUMENTS"
LINE = re.compile(r"    ([0-9A-F]{6})  (\S+)\s*(.*)$")
# a conditional branch (bcc): the only branch a frame wait ends with
BCC = re.compile(r"b(eq|ne|pl|mi|lt|ge|gt|le|hi|ls|cc|cs|vc|vs)$")
# a branch target: a bare "$hex" address
TARGET = re.compile(r"\$([0-9a-f]+)$")
# the instructions a frame wait's loop may hold: they only read and test
READS = {"tst.b", "tst.w", "tst.l", "cmp.b", "cmp.w", "cmp.l", "cmpi.b", "cmpi.w", "cmpi.l", "btst",
         "move.b", "move.w", "move.l", "moveq", "andi.b", "andi.w", "andi.l", "and.b", "and.w", "and.l",
         "cmpa.l", "cmpa.w"}


# the waits the rule cannot see: 0D48E2's state machine goes round (0D4EE0 "bra $d4932") while its state waits for
# the timer at FFF1FA, which the VBLANK counts down
CONDITIONAL = {0x0D4EE0: "0D48E2's state machine, while its state waits for the timer at FFF1FA"}


def find_repo_root():
    """The repository root: the first directory, walking up from the current directory and then
    from this script, that holds build/listing/spinball.s."""
    for start in (Path.cwd(), Path(__file__).resolve().parent):
        for d in (start, *start.parents):
            if (d / "build" / "listing" / "spinball.s").is_file():
                return d
    return None


def parse_listing(path):
    """The listing as (address, opcode, arguments) triples."""
    ins = []
    for l in path.read_text(encoding="utf-8").splitlines():
        m = LINE.match(l)
        if m:
            ins.append((int(m.group(1), 16), m.group(2), m.group(3).strip()))
    return ins


def find_waits(ins):
    """Every frame wait as (branch address, loop address, loop body, branch opcode)."""
    index = {a: i for i, (a, _, _) in enumerate(ins)}
    waits = []
    for i, (a, op, args) in enumerate(ins):
        if not BCC.match(op):
            continue
        m = TARGET.match(args)
        if not m:
            continue
        t = int(m.group(1), 16)
        if t > a or a - t > 24 or t not in index:
            continue
        body = ins[index[t]:i]
        ok = True
        written = set()  # data registers the loop set before now, in this pass
        for (_, o, ar) in body:
            inner = TARGET.match(ar)
            if (BCC.match(o) or o == "bra") and inner and t < int(inner.group(1), 16) <= a:
                continue    # a branch forward inside the loop
            if o not in READS:
                ok = False
                break
            parts = [p.strip() for p in re.split(r",(?![^(]*\))", ar)]
            dest = parts[-1] if len(parts) > 1 else None
            if o.startswith(("move", "and")) and o != "moveq" or o == "moveq":
                # move/moveq set a data register; and/andi only touch one the loop set before
                if not re.fullmatch(r"D[0-7]", dest or ""):
                    ok = False
                    break
                if o.startswith("and") and dest not in written:
                    ok = False
                    break
                written.add(dest)
            if re.search(r"\)\+|-\(", ar):
                ok = False
                break
        if ok:
            waits.append((a, t, body, op))
    return waits


def main():
    check = "--check" in sys.argv

    root = find_repo_root()
    if root is None:
        print("error: build/listing/spinball.s not found", file=sys.stderr)
        return 1
    listing = root / "build" / "listing" / "spinball.s"

    waits = find_waits(parse_listing(listing))

    if not check:
        for a, t, body, op in waits:
            print(f"{a:06X} -> {t:06X}  " + " ; ".join(f"{o} {ar}" for _, o, ar in body) + f" ; {op}")
        for a, why in sorted(CONDITIONAL.items()):
            print(f"{a:06X}  (conditional) {why}")
        print(f"{len(waits)} frame waits by the rule, {len(CONDITIONAL)} conditional")
        return 0

    # --check: the waits found must be exactly the profile's and runtime/src/frame.c's
    tools = root / "tools"
    if not (tools / "game_profile.py").is_file():
        tools = Path(__file__).resolve().parent
    sys.path[:0] = [str(tools / "core"), str(tools)]
    try:
        import game_profile
    except ImportError as e:
        print(f"error: cannot import game_profile: {e}", file=sys.stderr)
        return 1

    frame_c = root / "runtime" / "src" / "frame.c"
    m = re.search(r"const uint32_t md_game_frame_waits\[\]\s*=\s*\{(.*?)\};",
                  frame_c.read_text(encoding="utf-8"), re.DOTALL)
    if not m:
        print("error: md_game_frame_waits not found in runtime/src/frame.c", file=sys.stderr)
        return 1

    found = {a for a, _, _, _ in waits} | set(CONDITIONAL)
    sources = (("game_profile.py", set(game_profile.FRAME_WAIT)),
               ("runtime/src/frame.c", {int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]+)u", m.group(1))}))

    errors = []
    for name, s in sources:
        errors += [f"{name}: missing {a:06X}" for a in sorted(found - s)]
        errors += [f"{name}: extra {a:06X}" for a in sorted(s - found)]
    if errors:
        print("\n".join(errors))
        return 1

    print(f"frame waits: {len(found)}, the profile's and runtime/src/frame.c's the same")
    return 0


if __name__ == "__main__":
    sys.exit(main())
