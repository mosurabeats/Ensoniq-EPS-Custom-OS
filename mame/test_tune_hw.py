#!/usr/bin/env python3
"""TUNE on the swing build (src/swing/tune.s), 13-bit sample RAM and boot
ROM 2.40, as on the hardware. mame/keys/tune.txt: TR 8O8, Edit, 9 Layer,
◄ ◄ = TUNE, ▼ ▼ ▲: TUNE=-1, every wavesample of layer 1 one semitone lower
(ROOT KEY + 1), layer 2's untouched, the total in layer record +0x2F.
Needs what mame/test_mutegroups.py needs.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import test_mutegroups as T  # noqa: E402
import test_swing_hw as H  # noqa: E402
import instfile as I  # noqa: E402

LUA = """
local prog = manager.machine.devices[":maincpu"].spaces["program"]
local done = {}
local function dump(tag)
  local w = prog:read_u16(0xffdf70)
  local b = prog:read_u32(0xff0000 + prog:read_u16(0xff0000 + w)) & 0xffffff
  local f = io.open("%s_" .. tag .. ".bin", "wb")
  for i = 0, 0x40000 - 1 do f:write(string.char(prog:read_u8(b + i))) end
  f:close()
end
emu.register_periodic(function()
  local t = manager.machine.time:as_double()
  if not done.a and t > 33 then done.a = true; dump("before") end
  if not done.b and t > 37.5 then done.b = true; dump("after") end
end)
"""


def main():
    os.makedirs(T.OUT, exist_ok=True)
    disk = H.make_disk()
    pre = os.path.join(T.OUT, "tune")
    open(pre + ".lua", "w").write(LUA % pre)
    env = dict(os.environ, KEYS=os.path.join(T.ROOT, "mame", "keys", "tune.txt"),
               RUN=os.path.join(T.OUT, "run_tune"), BOOTROM=H.ROM, EPS_SAMPLERAM16="0")
    out = T.sh(os.path.join(T.ROOT, "mame", "run.sh"), disk, "38", pre + ".lua", env=env)
    before, after = (open(f"{pre}_{t}.bin", "rb").read() for t in ("before", "after"))
    ok = []

    def check(what, cond):
        ok.append(bool(cond))
        print(f"{'PASS' if cond else 'FAIL'}  {what}")

    screen = next((l for l in out.splitlines() if "TUNE=" in l), "")
    check("no ERROR on the display", "ERROR" not in out)
    check("TUNE on the Layer page: +0, then -1, -2, -1 as ▼ ▼ ▲ change it",
          "TUNE=<62>+0<72><63>-1<72><63>-2<72><63>-1" in screen)
    L = I.layers(after)
    lw = {}
    for l, lo in L.items():
        w, seen = after[lo + 6], []
        while w and w not in seen:
            seen.append(w)
            w = after[I.wavesamples(after)[w] + 6]
        lw[l] = seen
    W0, W1 = I.wavesamples(before), I.wavesamples(after)
    roots = {w: (before[W0[w] + 0xAA], after[W1[w] + 0xAA]) for w in W1}
    check("layer 1: every wavesample's ROOT KEY + 1 (a semitone lower)",
          lw[0] and all(roots[w][1] == roots[w][0] + 1 for w in lw[0]))
    check("layer 2 untouched", all(roots[w][1] == roots[w][0] for w in lw.get(1, [])))
    check("TUNE kept in layer record +0x2F (-1 << 3)", after[L[0] + 0x2F] == 0xF8)
    check("HIT untouched (+0x2E)", after[L[0] + 0x2E] == before[L[0] + 0x2E])
    print("   layers:", lw, " roots:", roots)
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
