#!/usr/bin/env python3
"""Our edit-page parameters (--pages) on the whole emulated EPS (MAME).

One --pages --auto-keep disk with the TR 8O8 kit, three runs:
* mame/keys/panel_mute.txt: EDIT, the 6 Amp page, MUTE GROUP = 1 with
  WS=ALL (the whole kit one group), then C2, E2, G2 with key-ups in
  between: each note cuts the one before, a key-up cuts nothing, and every
  wavesample's byte 0x11E holds 1.
* the same without the arrow (MUTE GROUP stays 0): nothing is cut.
* mame/keys/loop_panel_quant.txt: QUANTIZE 1/16 set on the sequencer page
  (no --swing), then loop_record.txt: the final take is on the straight
  1/16 grid (SWING% 0).
Needs what mame/test_mutegroups.py needs.
"""
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import test_mutegroups as T  # noqa: E402
import test_loop_record as L  # noqa: E402
import seqstream as S  # noqa: E402

C2, E2, G2 = 36, 40, 43
KILLING = 8
GROUPS_LUA = """
local cpu = manager.machine.devices[":maincpu"]
local ram = manager.machine.memory.shares[":osram"]
local prog = cpu.spaces["program"]
local last = ""
emu.register_periodic(function()
  local t = manager.machine.time:as_double()
  if t < 29 then return end
  local rec = ram:read_u16(0xDF70)
  if rec == 0 then return end
  local data = prog:read_u32(0xFF0000 + ram:read_u16(rec))
  local s = ""
  for ws = 1, 13 do
    local a = data + 4 * ws
    local off = (((prog:read_u8(a + 135) >> 4) << 16) | (prog:read_u8(a + 132) << 8)
                 | prog:read_u8(a + 134)) << 4
    s = s .. string.format(" %d", prog:read_u8(data + off + 0x11e))
  end
  if s ~= last then print(string.format("GROUPS %.2f%s", t, s)); last = s end
end)
"""


def run_mute(disk, name, keys):
    lua = os.path.join(T.OUT, name + ".lua")
    open(lua, "w").write(f'dofile("{T.ROOT}/mame/voices.lua")\n' + GROUPS_LUA)
    env = dict(os.environ, KEYS=keys, RUN=os.path.join(T.OUT, "run_" + name),
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


def killed_at(frames, key):
    """Times at which the voice of key is being killed."""
    return [t for t, v in frames if any(k == key and s == KILLING for k, _, s in v)]


def run_loop(disk, name):
    env = dict(os.environ, KEYS=os.path.join(T.ROOT, "mame", "keys", "loop_panel_quant.txt"),
               RUN=os.path.join(T.OUT, "run_" + name), EPS_ROOT=T.ROOT)
    out = T.sh(os.path.join(T.ROOT, "mame", "run.sh"), disk, "46",
               os.path.join(T.ROOT, "mame", "takes.lua"), env=env)
    final = None
    for line in out.splitlines():
        if line.startswith("FINAL "):
            final = S.notes([int(w, 16) for w in line.split()[2:]])
    return out, final


def main():
    os.makedirs(T.OUT, exist_ok=True)
    disk = L.make_disk("panel", ["--pages", "--auto-keep"])
    mute_keys = os.path.join(T.ROOT, "mame", "keys", "panel_mute.txt")
    no_group = os.path.join(T.OUT, "panel_nogroup.txt")
    open(no_group, "w").write("".join(l for l in open(mute_keys) if " 8a 00" not in l
                                      and " 0a 00" not in l))
    with ThreadPoolExecutor(3) as ex:
        f_mute = ex.submit(run_mute, disk, "panel_mute", mute_keys)
        f_none = ex.submit(run_mute, disk, "panel_nogroup", no_group)
        f_loop = ex.submit(run_loop, disk, "panel_quant")
        (out, frames, groups), (_, n_frames, n_groups), (l_out, final) = \
            f_mute.result(), f_none.result(), f_loop.result()
    ok = []

    def check(what, cond):
        ok.append(cond)
        print(f"{'PASS' if cond else 'FAIL'}  {what}")

    check("MUTE GROUP shows on the 6 Amp page", "MUTE GROUP=" in out)
    check("WS=ALL: every wavesample's group is 1", groups == [1] * 13)
    check("E2 cuts C2 (only once E2 starts)", killed_at(frames, C2) and min(killed_at(frames, C2)) > 33.25)
    check("G2 cuts E2", killed_at(frames, E2) and min(killed_at(frames, E2)) > 33.55)
    check("key-ups cut nothing (G2 rings out)", not killed_at(frames, G2))
    check("group 0: nothing is cut", not any(s == KILLING for _, v in n_frames for _, _, s in v))
    check("group 0: bytes stay 0", n_groups == [0] * 13)
    check("QUANTIZE shows on the sequencer page", "QUANTIZE=" in l_out)
    check("QUANTIZE 1/16 from the panel: final take on the straight 1/16 grid",
          bool(final) and all(t == 1 or t % 12 == 0 for t, *_ in final))
    print("final take:", [(t, k) for t, k, *_ in final or []])
    for t, v in frames:
        print(f"  {t:7.3f} " + " ".join(f"k{k}{'(killing)' if s == KILLING else ''}" for k, _, s in v))
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
