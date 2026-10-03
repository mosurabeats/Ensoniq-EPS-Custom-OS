#!/usr/bin/env python3
"""Swing quantize of LOOPED takes on the whole emulated EPS (MAME).

Stock vs --swing 16:mpc:58 --auto-keep (and the same with --pages, where it
presets QUANTIZE and SWING% on the sequencer page), with the TR 8O8 kit, running
mame/keys/loop_record.txt (kick, then snare and hat loop-recorded over 3
passes plus a snare in the unfinished last pass). mame/takes.lua prints
each take right after its wrap and the final take after STOP.
* Every take finished at a wrap has its notes on the swung 1/16 grid
  (except a wrap skipped because a key was held across it: the next one
  catches up), and the final take does too - including the note from the
  last pass, which only the STOP hook sees.
* Stock keeps the notes as played.
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import test_mutegroups as T  # noqa: E402
import test_loop_record as L  # noqa: E402
import seqstream as S  # noqa: E402
import swing  # noqa: E402

GRID, STYLE, AMOUNT = 12, "mpc", 58


def run(name, disk):
    env = dict(os.environ, KEYS=os.path.join(T.ROOT, "mame", "keys", "loop_record.txt"),
               RUN=os.path.join(T.OUT, "run_" + name), EPS_ROOT=T.ROOT)
    out = T.sh(os.path.join(T.ROOT, "mame", "run.sh"), disk, "46",
               os.path.join(T.ROOT, "mame", "takes.lua"), env=env)
    takes, final = [], None
    for line in out.splitlines():
        if line.startswith(("TAKE ", "FINAL ")):
            words = [int(w, 16) for w in line.split()[2:]]
            try:
                notes = S.notes(words)
            except ValueError:
                continue
            if line.startswith("TAKE"):
                takes.append(notes)
            else:
                final = notes
    return takes, final


def on_grid(notes):
    # tick 1 is the floor (the take's controller states sit there)
    return all(t == 1 or swing.quantize(t, GRID, STYLE, AMOUNT) == t for t, *_ in notes)


def main():
    os.makedirs(T.OUT, exist_ok=True)
    disks = {"swing_stock": L.make_disk("swing_stock", None),
             "swing_on": L.make_disk("swing_on", ["--swing", f"16:{STYLE}:{AMOUNT}", "--auto-keep"]),
             "swing_pages": L.make_disk("swing_pages", ["--pages", "--swing", f"16:{STYLE}:{AMOUNT}",
                                                       "--auto-keep"])}
    with ThreadPoolExecutor(3) as ex:
        res = dict(zip(disks, ex.map(lambda kv: run(*kv), disks.items())))
    ok = []

    def check(what, cond):
        ok.append(cond)
        print(f"{'PASS' if cond else 'FAIL'}  {what}")

    takes, final = res["swing_on"]
    s_takes, s_final = res["swing_stock"]
    check("swing: takes were printed", len(takes) >= 3 and final is not None)
    check("swing: first finished take on the grid", bool(takes) and on_grid(takes[0]))
    check("swing: last finished take on the grid", bool(takes) and on_grid(takes[-1]))
    check("swing: final take on the grid (STOP hook)", final is not None and on_grid(final))
    check("swing: the last-pass snare is in it", final is not None and len(final) > len(takes[-1]))
    check("stock: notes as played (off the grid)", s_final is not None and not on_grid(s_final))
    p_takes, p_final = res["swing_pages"]
    check("pages (QUANTIZE/SWING% on the sequencer page, preset 1/16 58%): final take on the grid",
          p_final is not None and on_grid(p_final) and len(p_final) == len(final or []))
    print("swing final:", [(t, k) for t, k, *_ in final or []])
    print("stock final:", [(t, k) for t, k, *_ in s_final or []])
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
