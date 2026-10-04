#!/usr/bin/env python3
"""The resident mute-groups build (tools/mkresident.py) on the whole emulated
EPS, with 13-bit sample RAM (mame/eps.patch) as on the hardware.

One disk: OS 2.49 with the resident patch + the TR 8O8 kit. Runs, with boot
ROM 2.40 (the hardware we test on) and the other ROM we have:
* mame/keys/panel_mute.txt: EDIT, the 6 Amp page, ◄ = MUTE GROUP, ▲ = 1
  with WS=ALL, then C2, E2, G2 with key-ups in between: each note cuts the
  one before, a key-up cuts nothing, every wavesample's byte 0x11E is 1.
* the same without ▲ (MUTE GROUP stays 0): nothing is cut.
* without ▲, on a copy of the disk with groups preset per wavesample
  (tools/epstool.py groups: C2 and G2 in group 1, E2 in group 2): E2
  doesn't cut C2, G2 cuts C2 and leaves E2 alone.
Needs what mame/test_mutegroups.py needs, and build/bootrom/r240/eps-h.bin,
eps-l.bin (ROM 2.40's halves, docs/MAME.md).
"""
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
import test_mutegroups as T  # noqa: E402
import test_panel as P  # noqa: E402

C2, E2, G2 = 36, 40, 43
ROMS = {"2.40": os.path.join(T.ROOT, "build", "bootrom", "r240"),
        "other": os.path.join(T.ROOT, "build", "bootrom", "unknown")}


def make_disk():
    os_disk = os.path.join(T.OUT, "resident_os.img")
    disk = os.path.join(T.OUT, "resident.img")
    T.sh(sys.executable, os.path.join(T.ROOT, "tools", "mkresident.py"),
         os.path.join(T.ROOT, "build", "eps_os_249.bin"), "-o", os.path.join(T.OUT, "resident.json"),
         "--disk", os.path.join(T.ROOT, "build", "eps249os.img"), os_disk)
    T.sh(sys.executable, os.path.join(T.ROOT, "tools", "epstool.py"), "add", os_disk, T.DRUMS, "1", disk)
    mixed = os.path.join(T.OUT, "resident_mixed.img")
    T.sh(sys.executable, os.path.join(T.ROOT, "tools", "epstool.py"), "groups", disk, "1",
         "C2=1,G2=1,E2=2", mixed)
    return disk, mixed


def run(disk, name, keys, rom):
    lua = os.path.join(T.OUT, name + ".lua")
    open(lua, "w").write(f'dofile("{T.ROOT}/mame/voices.lua")\n' + P.GROUPS_LUA)
    env = dict(os.environ, KEYS=keys, RUN=os.path.join(T.OUT, "run_" + name), BOOTROM=rom,
               EPS_SAMPLERAM16="0",
               VOICES_FROM="32.9", VOICES_TO="34.5")
    out = T.sh(os.path.join(T.ROOT, "mame", "run.sh"), disk, "35", lua, env=env)
    frames, groups = [], None
    for line in out.splitlines():
        if line.startswith("VOICES "):
            frames.append((float(line.split()[1]),
                           [tuple(map(int, v)) for v in re.findall(r"\[k(\d+) i(\d+) s(\d+)\]", line)]))
        elif line.startswith("GROUPS "):
            groups = [int(g) for g in line.split()[2:]]
    return out, frames, groups


def main():
    os.makedirs(T.OUT, exist_ok=True)
    disk, mixed = make_disk()
    mute_keys = os.path.join(T.ROOT, "mame", "keys", "panel_mute.txt")
    no_group = os.path.join(T.OUT, "resident_nogroup.txt")
    open(no_group, "w").write("".join(l for l in open(mute_keys) if " 8a 00" not in l
                                      and " 0a 00" not in l))
    jobs = {}
    with ThreadPoolExecutor(4) as ex:
        for rname, rom in ROMS.items():
            tag = rname.replace(".", "")
            jobs[rname] = (ex.submit(run, disk, f"res_mute_{tag}", mute_keys, rom),
                           ex.submit(run, disk, f"res_none_{tag}", no_group, rom),
                           ex.submit(run, mixed, f"res_mixed_{tag}", no_group, rom))
    ok = []

    def check(what, cond):
        ok.append(cond)
        print(f"{'PASS' if cond else 'FAIL'}  {what}")

    for rname, (f_mute, f_none, f_mixed) in jobs.items():
        (out, frames, groups), (n_out, n_frames, n_groups) = f_mute.result(), f_none.result()
        _, m_frames, _ = f_mixed.result()
        k = lambda key: P.killed_at(frames, key)  # noqa: E731
        print(f"-- boot ROM {rname}")
        check("no ERROR on the display", "ERROR" not in out and "ERROR" not in n_out)
        check("MUTE GROUP shows on the 6 Amp page", "MUTE GROUP=" in out)
        check("WS=ALL: every wavesample's group is 1", groups == [1] * 13)
        check("E2 cuts C2 (only once E2 starts)", k(C2) and min(k(C2)) > 33.25)
        check("G2 cuts E2", k(E2) and min(k(E2)) > 33.55)
        check("key-ups cut nothing (G2 rings out)", not k(G2))
        check("group 0: nothing is cut", not any(s == P.KILLING for _, v in n_frames for _, _, s in v))
        check("group 0: bytes stay 0", n_groups == [0] * 13)
        mk = lambda key: P.killed_at(m_frames, key)  # noqa: E731
        check("mixed: E2 (group 2) doesn't cut C2; G2 (group 1) does",
              bool(mk(C2)) and min(mk(C2)) > 33.55)
        check("mixed: G2 leaves E2 alone (not killed)", not mk(E2)
              and any(kk == E2 for t, v in m_frames if t > 33.6 for kk, _, _ in v))
        for t, v in frames:
            print(f"  {t:7.3f} " + " ".join(f"k{kk}{'(killing)' if s == P.KILLING else ''}" for kk, _, s in v))
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
