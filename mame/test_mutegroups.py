#!/usr/bin/env python3
"""Mute groups on the whole emulated EPS (MAME), against a stock boot.

Builds three disks: stock OS 2.49, mute groups "1=1" (instrument 1 mono),
and "1:C2=1,1:E2=1" (kick/snare style: two keys cut each other, the rest
rings). Each gets the TR 8O8 kit from build/sounds/DRMSET09.GKH as file 1.
MAME boots each, loads the kit into instrument 1 from the front panel, and
plays C2, E2, G2 300 ms apart (mame/keys/load1_play.txt) while
mame/voices.lua prints the voice lists.

Needs: build/eps_os_249.bin + build/eps249os.img (tools/fetch.sh os), the
drum disk (tools/fetch.sh sounds), the boot ROM, and MAME (mame/build.sh).
Takes about a minute (the three runs go in parallel).
"""
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "build", "mame", "mutegroups")
DRUMS = os.path.join(ROOT, "build", "sounds", "DRMSET09.GKH")
C2, E2, G2 = 36, 40, 43
KILLING = 8
# The code-area builds run code from sample RAM, which the hardware can't
# (13 bits wide; mame/eps.patch emulates that): these tests keep the
# emulator's sample RAM 16 bits wide. mame/test_resident.py doesn't.
os.environ.setdefault("EPS_SAMPLERAM16", "1")


def sh(*cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw).stdout


def make_disk(name, groups):
    os_disk = os.path.join(ROOT, "build", "eps249os.img")
    disk = os.path.join(OUT, name + ".img")
    if groups is not None:
        tmp = os.path.join(OUT, name + "_os.img")
        sh(sys.executable, os.path.join(ROOT, "tools", "mkcodearea.py"),
           os.path.join(ROOT, "build", "eps_os_249.bin"),
           "-o", os.path.join(OUT, name + ".json"), "--groups", groups, "--disk", os_disk, tmp)
        os_disk = tmp
    sh(sys.executable, os.path.join(ROOT, "tools", "epstool.py"), "add", os_disk, DRUMS, "1", disk)
    return disk


def run(name, disk):
    env = dict(os.environ, KEYS=os.path.join(ROOT, "mame", "keys", "load1_play.txt"),
               RUN=os.path.join(OUT, "run_" + name))
    out = sh(os.path.join(ROOT, "mame", "run.sh"), disk, "32",
             os.path.join(ROOT, "mame", "voices.lua"), env=env)
    frames = []
    for line in out.splitlines():
        if line.startswith("VOICES "):
            t = float(line.split()[1])
            voices = [tuple(map(int, v)) for v in re.findall(r"\[k(\d+) i(\d+) s(\d+)\]", line)]
            frames.append((t, voices))
    return out, frames


def sounding_together(frames, keys):
    """Some frame where all `keys` play at once (none of them being killed)."""
    return any(set(keys) <= {k for k, _, s in v if s != KILLING} for _, v in frames)


def killed(frames, key):
    return any((key, 0, KILLING) in v for _, v in frames)


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in (DRUMS, os.path.join(ROOT, "build", "eps_os_249.bin")):
        if not os.path.exists(f):
            sys.exit(f"missing {f} (tools/fetch.sh sounds)")
    disks = {"stock": make_disk("stock", None),
             "mono": make_disk("mono", "1=1"),
             "kit": make_disk("kit", "1:C2=1,1:E2=1")}
    with ThreadPoolExecutor(3) as ex:
        res = dict(zip(disks, ex.map(lambda kv: run(*kv), disks.items())))

    checks = []
    def check(what, ok):
        checks.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {what}")

    for name, (out, frames) in res.items():
        loaded = "FILE LOADED" in out
        check(f"{name}: TR 8O8 loaded from the panel", loaded)
        check(f"{name}: notes started voices", any(frames and v for _, v in frames))
    s, m, k = (res[n][1] for n in ("stock", "mono", "kit"))
    check("stock: C2, E2, G2 ring together", sounding_together(s, (C2, E2, G2)))
    check("stock: nothing is killed", not any(st == KILLING for _, v in s for _, _, st in v))
    check("mono (1=1): E2 cuts C2", killed(m, C2))
    check("mono (1=1): G2 cuts E2", killed(m, E2))
    check("mono (1=1): never two notes at once", not sounding_together(m, (C2, E2))
          and not sounding_together(m, (E2, G2)))
    check("kit (C2, E2 in group 1): E2 cuts C2", killed(k, C2))
    check("kit: G2 (no group) leaves E2 ringing", sounding_together(k, (E2, G2))
          and not killed(k, E2))

    for name, (_, frames) in res.items():
        print(f"\n{name}:")
        for t, v in frames:
            print(f"  {t:7.3f} " + " ".join(f"k{a}{'(killing)' if st == KILLING else ''}"
                                           for a, _, st in v))
    sys.exit(0 if all(checks) else 1)


if __name__ == "__main__":
    main()
