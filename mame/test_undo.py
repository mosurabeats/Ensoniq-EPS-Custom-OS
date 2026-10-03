#!/usr/bin/env python3
"""Loop undo on the whole emulated EPS (MAME): --undo vs stock.

All disks get the TR 8O8 kit and --auto-keep (no KEEP prompt); the
third has --swing 16:mpc:58 (which includes undo) as well.
mame/keys/loop_undo.txt records a 1-bar kick, then loop-records: D2 in
pass 1; G2 in pass 2 then RECORD (undo: that G2); RECORD early in pass 3
(nothing new yet: undo pass 1's D2), then A#2; STOP, and plays it back.
mame/undo.lua prints the takes and the voices.
* undo (both): pass 2 still plays D2; pass 3 plays neither D2 nor G2;
  the final take and the playback have only A#2 (and the kick).
* stock: RECORD does nothing while loop recording: everything stays.
Needs what mame/test_mutegroups.py needs.
"""
import os
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import test_mutegroups as T  # noqa: E402
import test_loop_record as L  # noqa: E402
import seqstream as S  # noqa: E402
import swing  # noqa: E402

C2, D2, G2, AS2 = 36, 38, 43, 46


def run(name, disk):
    env = dict(os.environ, KEYS=os.path.join(T.ROOT, "mame", "keys", "loop_undo.txt"),
               RUN=os.path.join(T.OUT, "run_" + name), EPS_ROOT=T.ROOT,
               VOICES_FROM="37", VOICES_TO="53")
    out = T.sh(os.path.join(T.ROOT, "mame", "run.sh"), disk, "53",
               os.path.join(T.ROOT, "mame", "undo.lua"), env=env)
    takes, final, starts = [], None, []
    prev = Counter()
    for line in out.splitlines():
        if line.startswith(("TAKE ", "FINAL ")):
            t = float(line.split()[1])
            try:
                notes = S.notes([int(w, 16) for w in line.split()[2:]])
            except ValueError:              # read mid-STOP
                continue
            if line.startswith("TAKE"):
                takes.append((t, notes))
            else:
                final = notes
        elif line.startswith("VOICES "):
            t = float(line.split()[1])
            now = Counter(int(k) for k in re.findall(r"\[k(\d+) i\d+ s(?:2|4)\]", line))
            for k in now:
                if now[k] > prev[k]:
                    starts.append((t, k))
            prev = now
    return out, takes, final, starts


def started(starts, lo, hi):
    return {k for t, k in starts if lo <= t <= hi}


def main():
    os.makedirs(T.OUT, exist_ok=True)
    disks = {"undo_stock": L.make_disk("undo_stock", ["--auto-keep"]),
             "undo_on": L.make_disk("undo_on", ["--undo", "--auto-keep"]),
             "undo_swing": L.make_disk("undo_swing", ["--swing", "16:mpc:58", "--auto-keep"]),
             "undo_pages": L.make_disk("undo_pages", ["--pages", "--auto-keep"])}
    with ThreadPoolExecutor(4) as ex:
        res = dict(zip(disks, ex.map(lambda kv: run(*kv), disks.items())))
    ok = []

    def check(what, cond):
        ok.append(cond)
        print(f"{'PASS' if cond else 'FAIL'}  {what}")

    for name, (out, takes, final, starts) in res.items():
        print(f"{name}: takes {[(t, [n[1] for n in ns]) for t, ns in takes]}")
        print(f"{name}: final {[n[1] for n in final or []]}")
        print(f"{name}: voice starts {starts}")
    keys = lambda notes: sorted(n[1] for n in notes or [])  # noqa: E731
    for name in ("undo_on", "undo_swing", "undo_pages"):
        _, takes, final, starts = res[name]
        check(f"{name}: pass 2 still plays pass 1's D2", D2 in started(starts, 40.6, 41.4))
        check(f"{name}: pass 3 plays no G2 (undone in pass 2)", G2 not in started(starts, 42.1, 42.9))
        check(f"{name}: pass 3 plays no D2 (undone early in pass 3)",
              D2 not in started(starts, 43.0, 43.8))
        check(f"{name}: the take after pass 3 has only A#2",
              any(44.3 < t < 45.0 and keys(ns) == [AS2] for t, ns in takes))
        check(f"{name}: final take has only A#2", keys(final) == [AS2])
        check(f"{name}: playback has the kick and A#2, no D2 or G2",
              {C2, AS2} <= started(starts, 47.0, 52.0) and not {D2, G2} & started(starts, 47.0, 52.0))
    final = res["undo_swing"][2] or []
    check("undo_swing: A#2 on the swung grid", all(swing.quantize(t, 12, "mpc", 58) == t
                                                   for t, *_ in final))
    _, s_takes, s_final, s_starts = res["undo_stock"]
    check("stock: pass 3 plays G2 and D2", {G2, D2} <= started(s_starts, 42.1, 43.8))
    check("stock: final take has D2, G2, A#2", keys(s_final) == [D2, G2, AS2])
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
