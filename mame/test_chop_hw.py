#!/usr/bin/env python3
"""CHOP on the swing build (src/swing/chop.s), 13-bit sample RAM and boot
ROM 2.40, as on the hardware.

* mame/keys/chop.txt: the TR 8O8 kick (WS 1, keys 21-36, 6112 samples)
  chopped into 16: 16 new wavesamples, one key each from C2 up, ROOT KEY =
  the key, FORWARD-NO LOOP, playing WS 1's data, end to end over WS 1's
  start..end, every inner cut on the sign change of the data nearest the
  equal cut (within 127 samples and a quarter slice); C#2 then plays
  slice 2.
* mame/keys/chop_refuse.txt: with WS=ALL, NO EDIT WS SELECTED; ENTER then
  CANCEL: COMMAND ABORTED; nothing made.
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
local done, last = {}, {}
local function base()
  local w = prog:read_u16(0xffdf70)               -- instrument 1's record
  return prog:read_u32(0xff0000 + prog:read_u16(0xff0000 + w)) & 0xffffff
end
local function dump(tag)
  local f = io.open("%s_" .. tag .. ".bin", "wb")
  local b = base()
  for i = 0, 0x40000 - 1 do f:write(string.char(prog:read_u8(b + i))) end
  f:close()
  print(string.format("BASE %%x", b))
end
emu.register_periodic(function()
  local t = manager.machine.time:as_double()
  if not done.a and t > 33 then done.a = true; dump("before") end
  if not done.b and t > 39.5 then done.b = true; dump("after") end
  if t > 39.8 and t < 41 then                      -- voices started: key, ws record
    for _, sentinel in ipairs({0x16e4, 0x16dc}) do  -- held, releasing
      local v, n = prog:read_u16(0xff0000 + sentinel), 0
      while v ~= sentinel and n < 24 do
        local a = 0xff0000 + v
        local k = prog:read_u8(a + 4)
        if not last[k] then
          last[k] = true
          print(string.format("VOICE %%d %%x", k, prog:read_u32(a + 22) & 0xffffff))
        end
        v = prog:read_u16(a); n = n + 1
      end
    end
  end
end)
"""


def run(disk, name, keyfile):
    pre = os.path.join(T.OUT, name)
    lua = pre + ".lua"
    open(lua, "w").write(LUA % pre)
    env = dict(os.environ, KEYS=os.path.join(T.ROOT, "mame", "keys", keyfile),
               RUN=os.path.join(T.OUT, "run_" + name), BOOTROM=H.ROM, EPS_SAMPLERAM16="0")
    out = T.sh(os.path.join(T.ROOT, "mame", "run.sh"), disk, "41", lua, env=env)
    before = open(pre + "_before.bin", "rb").read()
    after = open(pre + "_after.bin", "rb").read()
    return out, before, after


def mp(r, o):
    return (r[o] << 24 | r[o + 2] << 16 | r[o + 4] << 8 | r[o + 6]) >> 9


def sample(d, o, i):
    v = d[o + 0x120 + 2 * i] << 8 | d[o + 0x120 + 2 * i + 1]
    return v - 0x10000 if v & 0x8000 else v


def main():
    os.makedirs(T.OUT, exist_ok=True)
    disk = H.make_disk()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(2) as ex:
        fa = ex.submit(run, disk, "chop_a", "chop.txt")
        fb = ex.submit(run, disk, "chop_b", "chop_refuse.txt")
        (a_out, a_before, a_after), (b_out, b_before, b_after) = fa.result(), fb.result()
    ok = []

    def check(what, cond):
        ok.append(bool(cond))
        print(f"{'PASS' if cond else 'FAIL'}  {what}")

    check("no ERROR on the display", "ERROR" not in a_out + b_out)
    check("the CHOP entry on the Wave page", "CHOP=<62>PRESS ENTER" in a_out)
    check("the prompt, ▲/▼ change the count",
          "CHOP INTO 16 SLICES?" in a_out and "CHOP INTO 24 SLICES?" in a_out)
    check("16 SLICES CREATED", "16 SLICES CREATED" in a_out)

    W0, W = I.wavesamples(a_before), I.wavesamples(a_after)
    new = sorted(set(W) - set(W0))
    check("16 new wavesamples", len(new) == 16)
    src = a_after[W[1]:W[1] + 0x120]
    s0, e0 = mp(src, 0xF0), mp(src, 0xF8)
    recs = [a_after[W[w]:W[w] + 0x120] for w in new]
    km = I.key_map(a_after)
    check("one key each from C2 up (layer 1's key map)",
          [dict(km.get(36 + i, []))[0] for i in range(16)] == new)
    check("ROOT KEY = the key, one-key range",
          all(r[0xAA] == 36 + i and r[0x112] == r[0x114] == 36 + i for i, r in enumerate(recs)))
    check("FORWARD-NO LOOP, playing WS 1's data",
          all(r[0xEE] == 0 and r[0x22] == 1 for r in recs))
    starts, ends = [mp(r, 0xF0) for r in recs], [mp(r, 0xF8) for r in recs]
    check("end to end over WS 1's start..end",
          starts[0] == s0 and ends[-1] == e0 and all(ends[i] + 1 == starts[i + 1] for i in range(15)))
    check("loop points on the slice", all(mp(r, 0x100) == mp(r, 0xF0) and mp(r, 0x108) == mp(r, 0xF8)
                                          for r in recs))
    n = e0 - s0 + 1
    q, lim = n // 16, min(127, n // 16 // 4)

    def crossing(i):
        return (sample(a_after, W[1], i - 1) ^ sample(a_after, W[1], i)) < 0

    def nearest(p):
        for k in range(lim + 1):
            for c in (p - k, p + k):
                if crossing(c):
                    return c
        return p
    want = [s0] + [nearest(s0 + q * i + (n % 16) * i // 16) for i in range(1, 16)]
    check("cuts at the nearest sign change to the equal cuts", starts == want)
    check("WS 1 itself unchanged", a_before[W0[1]:W0[1] + 0x120] == src)
    voices = dict((int(l.split()[1]), int(l.split()[2], 16)) for l in a_out.splitlines()
                  if l.startswith("VOICE "))
    base = int(next(l for l in a_out.splitlines() if l.startswith("BASE ")).split()[1], 16)
    check("C#2 plays slice 2", voices.get(37) == base + W[new[1]])

    check("WS=ALL: NO EDIT WS SELECTED", "NO EDIT WS SELECTED" in b_out)
    check("CANCEL: COMMAND ABORTED", "COMMAND ABORTED" in b_out)
    check("nothing made", I.wavesamples(b_after) == I.wavesamples(b_before) and b_after == b_before)
    print("   slices:", list(zip(starts, ends)))
    print("   voices:", {k: hex(v) for k, v in voices.items()}, "slice 2 at", hex(base + W[new[1]]))
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
