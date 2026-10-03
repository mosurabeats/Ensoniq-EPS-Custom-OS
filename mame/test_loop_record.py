#!/usr/bin/env python3
"""Loop recording on the whole emulated EPS (MAME): stock vs --auto-keep.

Both disks get the TR 8O8 kit. mame/keys/loop_record.txt records a 1-bar
kick, loop-records snare and hat over it (LOOPED mode, set by
mame/loop.lua), stops, and plays the sequence back.
* stock: STOP asks "KEEP = OLD NEW".
* --auto-keep: no prompt, and playback has the kick plus the new notes.
Needs what mame/test_mutegroups.py needs.
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
import test_mutegroups as T  # noqa: E402


def make_disk(name, opts):
    disk = os.path.join(T.OUT, name + ".img")
    os_disk = os.path.join(T.ROOT, "build", "eps249os.img")
    if opts is not None:
        tmp = os.path.join(T.OUT, name + "_os.img")
        T.sh(sys.executable, os.path.join(T.ROOT, "tools", "mkcodearea.py"),
             os.path.join(T.ROOT, "build", "eps_os_249.bin"),
             "-o", os.path.join(T.OUT, name + ".json"), *opts, "--disk", os_disk, tmp)
        os_disk = tmp
    T.sh(sys.executable, os.path.join(T.ROOT, "tools", "epstool.py"), "add", os_disk, T.DRUMS, "1", disk)
    return disk


def run(name, disk):
    env = dict(os.environ, KEYS=os.path.join(T.ROOT, "mame", "keys", "loop_record.txt"),
               RUN=os.path.join(T.OUT, "run_" + name))
    out = T.sh(os.path.join(T.ROOT, "mame", "run.sh"), disk, "53",
               os.path.join(T.ROOT, "mame", "loop.lua"), env=env)
    keys = set()
    for line in out.splitlines():
        if line.startswith("PLAYBACK "):
            keys |= {int(k[1:]) for k in line.split()[2:]}
    return out, keys


def main():
    os.makedirs(T.OUT, exist_ok=True)
    disks = {"loop_stock": make_disk("loop_stock", None),
             "loop_autokeep": make_disk("loop_autokeep", ["--auto-keep"])}
    with ThreadPoolExecutor(2) as ex:
        res = dict(zip(disks, ex.map(lambda kv: run(*kv), disks.items())))
    ok = []

    def check(what, cond):
        ok.append(cond)
        print(f"{'PASS' if cond else 'FAIL'}  {what}")

    s_out, _ = res["loop_stock"]
    a_out, a_keys = res["loop_autokeep"]
    check("stock: STOP asks KEEP = OLD NEW", "KEEP =   OLD    NEW" in s_out)
    check("auto-keep: no KEEP prompt", "KEEP =" not in a_out)
    check("auto-keep: playback has the kick and the looped snare and hat",
          {T.C2, 38, T.G2} <= a_keys)
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
