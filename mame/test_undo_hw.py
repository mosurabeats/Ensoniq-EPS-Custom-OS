#!/usr/bin/env python3
"""Loop undo on the swing build (tools/mkswing.py), 13-bit sample RAM and
boot ROM 2.40, as on the hardware.

One level of undo (like the MPC60): RECORD while loop recording takes out
the notes played so far in this pass, or if there are none, the last
pass's. Two runs, 6 s later than the key files (this OS boots slower),
ENTER at the KEEP = OLD NEW prompt (NEW):
* mame/keys/loop_undo.txt: D2 in pass 1; G2 in pass 2 then RECORD (undo:
  that G2); RECORD early in pass 3 (one level: nothing more to undo), then
  A#2. Pass 2 still plays D2, pass 3 no G2; kept: D2 and A#2.
* mame/keys/loop_undo_prev.txt: D2 in pass 1; RECORD early in pass 2
  (nothing new yet: undo pass 1's D2), then A#2. Pass 2 doesn't play D2;
  kept: A#2 only.
Both: no undo marks (bit 3) left in the kept take.
Needs what mame/test_mutegroups.py needs.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import test_mutegroups as T  # noqa: E402
import test_swing_hw as H  # noqa: E402
import seqstream as S  # noqa: E402

C2, D2, G2, AS2 = 36, 38, 43, 46
SHIFT = 6
PASS2 = (39.65 + SHIFT, 42.05 + SHIFT)
PASS3 = (42.05 + SHIFT, 44.45 + SHIFT)


def run(disk, name, keyfile):
    keys = os.path.join(T.OUT, name + ".txt")
    lines = H.shifted(os.path.join(T.ROOT, "mame", "keys", keyfile), SHIFT, upto=45.5 + SHIFT)
    lines += [f"{46.0 + SHIFT:.2f} a3 00    # ENTER at KEEP = OLD NEW: NEW\n", f"{46.15 + SHIFT:.2f} 23 00\n"]
    open(keys, "w").write("".join(lines))
    lua = os.path.join(T.OUT, name + ".lua")
    open(lua, "w").write(LUA % SHIFT)
    env = dict(os.environ, KEYS=keys, RUN=os.path.join(T.OUT, "run_" + name),
               BOOTROM=H.ROM, EPS_SAMPLERAM16="0")
    out = T.sh(os.path.join(T.ROOT, "mame", "run.sh"), disk, str(int(48 + SHIFT)), lua, env=env)
    starts = [(float(l.split()[1]), int(l.split()[2])) for l in out.splitlines() if l.startswith("START ")]
    kept_line = next((l for l in out.splitlines() if l.startswith("KEPT ")), "KEPT")
    words = [int(w, 16) for w in kept_line.split()[1:]]
    return out, starts, words

LUA = """
local prog = manager.machine.devices[":maincpu"].spaces["program"]
local SHIFT = %d
local set, kept = false, false
local last = {}
emu.register_periodic(function()
  local t = manager.machine.time:as_double()
  if not set and t > 36 + SHIFT then set = true; prog:write_u8(0xff815f, 2) end
  if t > 37 + SHIFT and t < 45 + SHIFT then        -- voice starts (a key not sounding before)
    local now = {}
    for _, sentinel in ipairs({0xFF16E4, 0xFF16DC}) do
      local v, n = prog:read_u16(sentinel), 0
      while v ~= (sentinel & 0xFFFF) and n < 24 do
        local a = 0xFF0000 + v
        if prog:read_u8(a + 12) ~= 8 then now[prog:read_u8(a + 4)] = true end
        v = prog:read_u16(a); n = n + 1
      end
    end
    for k in pairs(now) do if not last[k] then print(string.format("START %%.3f %%d", t, k)) end end
    last = now
  end
  if not kept and t > 46.8 + SHIFT then
    kept = true
    local start = prog:read_u32(0xff8104) + prog:read_u32(0xff8114) + 28
    local s = ""
    for i = 0, 2000 do
      local v = prog:read_u16(start + 2 * i)
      s = s .. string.format("%%04x ", v)
      if v & 0xFFF0 == 0x8BC0 then break end
    end
    print("KEPT " .. s)
  end
end)
"""


def main():
    os.makedirs(T.OUT, exist_ok=True)
    disk = H.make_disk()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(2) as ex:
        fa = ex.submit(run, disk, "undohw_a", "loop_undo.txt")
        fb = ex.submit(run, disk, "undohw_b", "loop_undo_prev.txt")
        (a_out, a_starts, a_words), (b_out, b_starts, b_words) = fa.result(), fb.result()
    ok = []

    def check(what, cond):
        ok.append(bool(cond))
        print(f"{'PASS' if cond else 'FAIL'}  {what}")

    def in_pass(starts, p, k):
        return [t for t, kk in starts if kk == k and p[0] <= t < p[1]]

    def keys_of(words):
        return sorted({k for _, k, *_ in S.notes(words)}) if words else []

    def unmarked(words):
        return words and not any(ev[2] & 8 for ev in S.split(words) if S.is_note(ev))

    check("no ERROR on the display", "ERROR" not in a_out + b_out)
    check("A: pass 2 still plays pass 1's D2", in_pass(a_starts, PASS2, D2))
    check("A: pass 3 plays no G2 (undone in pass 2)", not in_pass(a_starts, PASS3, G2))
    check("A: kept D2 and A#2, no G2", [k for k in keys_of(a_words) if k != C2] == [D2, AS2])
    check("A: no undo marks left", unmarked(a_words))
    check("B: pass 2 doesn't play pass 1's D2 (undone early in pass 2)",
          not in_pass(b_starts, PASS2, D2) and in_pass(b_starts, (37 + SHIFT, PASS2[0]), D2))
    check("B: kept A#2 only", [k for k in keys_of(b_words) if k != C2] == [AS2])
    check("B: no undo marks left", unmarked(b_words))
    print("   A starts:", a_starts)
    print("   A kept:  ", [(t, k) for t, k, *_ in S.notes(a_words)] if a_words else None)
    print("   B starts:", b_starts)
    print("   B kept:  ", [(t, k) for t, k, *_ in S.notes(b_words)] if b_words else None)
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
