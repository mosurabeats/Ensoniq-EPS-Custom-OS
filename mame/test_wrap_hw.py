#!/usr/bin/env python3
"""How long loop recording holds up the sequencer at each loop wrap, on the
swing build (13-bit sample RAM, boot ROM 2.40, as on the hardware).

Anything the wrap hook (0xFF6746, src/swing/window.s) spends delays the
first notes of the next pass: the hardware showed the downbeat 20-25 ms
late while loop recording (2026-10-05, sq re-encoding the whole take at
every wrap). The fast path (sq.s, sqf) moves only the new notes, in place.

* light: mame/keys/loop_record.txt (a snare and a hat per pass);
* busy: the same with a closed hat on every 16th of every pass, each held
  50 ms (some are held over the wrap);
* punch: a 2-bar sequence, PLAY, then RECORD + PLAY in bar 2 (recording
  starts there), hits in bar 2, one on the loop point, then in the next
  passes. The take before the punch-in's first wrap ends a tick late (385
  of 384), so the hit on the loop point is at END in the next one: it must
  wrap to the start by the second wrap, not wait for STOP.
Each wrap is timed in CPU cycles (MAME runs the EPS's 68000 at 10 MHz),
then the take kept with NEW must have every note played, on the 1/16 grid
(a hit right at the loop start, recorded before the opening events, once
went to tick 0, where the OS drops it: found on the hardware, 2026-10-06).
Needs what mame/test_mutegroups.py needs.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import test_mutegroups as T  # noqa: E402
import test_swing_hw as H  # noqa: E402
import seqstream as S  # noqa: E402

LIGHT_MAX, BUSY_MAX = 25_000, 100_000       # cycles (2.5 / 10 ms); sq alone took ~290k busy
LUA = """
local ram = manager.machine.memory.shares[":osram"]
local cpu = manager.machine.devices[":maincpu"]
local prog = cpu.spaces["program"]
local set, kept = false, false
cpu.debug:bpset(0x6746, "", 'printf "IN %d\\\\n",totalcycles; g')
cpu.debug:bpset(0x674a, "", 'printf "OUT %d\\\\n",totalcycles; g')
manager.machine.debugger:command("g")
emu.register_periodic(function()
  local t = manager.machine.time:as_double()
  if not set and t > 42 then set = true; ram:write_u8(0x815f, 2) end
  if not kept and t > 53.5 then
    kept = true
    local start = prog:read_u32(0xff8104) + prog:read_u32(0xff8114) + 28
    local s = ""
    for i = 0, 3000 do
      local v = prog:read_u16(start + 2 * i)
      s = s .. string.format("%04x ", v)
      if v & 0xFFF0 == 0x8BC0 then break end
    end
    print("KEPT " .. s)
  end
end)
"""


LOOP_NOTES = 5                              # loop_record.txt's notes after RECORD + PLAY


def run(disk, name, busy):
    lines = H.shifted(os.path.join(T.ROOT, "mame", "keys", "loop_record.txt"), 6, upto=51.5)
    played = LOOP_NOTES
    if busy:
        t = 43.6
        while t < 50.7:
            lines += [f"{t:.3f} 86 50\n", f"{t + 0.05:.3f} 06 40\n"]
            t += 0.125
            played += 1
        lines.sort(key=lambda l: float(l.split()[0]))
    lines += ["52.0 a3 00\n", "52.15 23 00\n"]             # KEEP = NEW
    keys = os.path.join(T.OUT, name + ".txt")
    open(keys, "w").write("".join(lines))
    lua = os.path.join(T.OUT, name + ".lua")
    open(lua, "w").write(LUA)
    env = dict(os.environ, KEYS=keys, RUN=os.path.join(T.OUT, "run_" + name), BOOTROM=H.ROM,
               EPS_SAMPLERAM16="0")
    out = T.sh(os.path.join(T.ROOT, "mame", "run.sh"), disk, "54", lua, env=env)
    ev = [l.split() for l in out.splitlines() if l.split()[:1] in (["IN"], ["OUT"])]
    wraps = [int(b[1]) - int(a[1]) for a, b in zip(ev, ev[1:]) if a[0] == "IN" and b[0] == "OUT"]
    kept = next((S.parse(l[5:]) for l in out.splitlines() if l.startswith("KEPT ")), [])
    return out, wraps, kept, played


PUNCH_LUA = """
local ram = manager.machine.memory.shares[":osram"]
local prog = manager.machine.devices[":maincpu"].spaces["program"]
local set, last, kept = false, nil, false
local function dump(tag, start)
  local s = ""
  for i = 0, 3000 do
    local v = prog:read_u16(start + 2 * i)
    s = s .. string.format("%04x ", v)
    if v & 0xFFF0 == 0x8BC0 then break end
  end
  print(tag .. " " .. s)
end
emu.register_periodic(function()
  local t = manager.machine.time:as_double()
  if not set and t > 42 then set = true; ram:write_u8(0x815f, 2) end
  if t < 43 then return end
  local base, a, b, w = prog:read_u32(0xff8104), prog:read_u32(0xff8114), prog:read_u32(0xff8118), prog:read_u32(0xff811c)
  if t < 58 and w ~= 0 then
    local cur = (w >= b) and "B" or "A"
    if last and cur ~= last then dump("TAKE", base + ((cur == "B") and a or b) + 28) end
    last = cur
  end
  if not kept and t > 60 then kept = true; dump("KEPT", base + a + 28) end
end)
"""
PUNCH_NOTES = [(47.3, 2), (47.6, 7), (48.0, 2), (48.4, 7), (49.0, 4), (49.4, 4), (50.0, 2), (50.5, 7),
               (51.2, 4)]                   # 48.0: on the loop point


def run_punch(disk):
    k = lambda t, x: f"{t:.2f} {x}\n"  # noqa: E731
    lines = [k(16.5, "8f 00"), k(16.65, "0f 00"), k(17.5, "a3 00"), k(17.65, "23 00"),
             k(18.5, "82 00"), k(18.65, "02 00"), k(35.0, "82 00"), k(35.15, "02 00"),
             k(36.0, "83 00"), k(36.2, "9d 00"), k(36.35, "1d 00"), k(36.5, "03 00"),   # record 2 bars
             k(37.0, "80 40"), k(37.1, "00 40"), k(41.0, "97 00"), k(41.15, "17 00"),
             k(42.0, "a3 00"), k(42.15, "23 00"),
             k(43.2, "9d 00"), k(43.35, "1d 00"),                                        # PLAY
             k(45.4, "83 00"), k(45.6, "9d 00"), k(45.75, "1d 00"), k(45.9, "03 00")]    # RECORD + PLAY
    for t, key in PUNCH_NOTES:
        lines += [k(t, f"{0x80 | key:02x} 60"), k(t + 0.08, f"{key:02x} 40")]
    lines += [k(58.0, "97 00"), k(58.15, "17 00"), k(59.0, "a3 00"), k(59.15, "23 00")]
    lines.sort(key=lambda l: float(l.split()[0]))
    keys = os.path.join(T.OUT, "wrap_punch.txt")
    open(keys, "w").write("".join(lines))
    lua = os.path.join(T.OUT, "wrap_punch.lua")
    open(lua, "w").write(PUNCH_LUA)
    env = dict(os.environ, KEYS=keys, RUN=os.path.join(T.OUT, "run_wrap_punch"), BOOTROM=H.ROM,
               EPS_SAMPLERAM16="0")
    out = T.sh(os.path.join(T.ROOT, "mame", "run.sh"), disk, "62", lua, env=env)
    takes = [S.parse(l[5:]) for l in out.splitlines() if l.startswith("TAKE ")]
    kept = next((S.parse(l[5:]) for l in out.splitlines() if l.startswith("KEPT ")), [])
    return out, takes, kept


def main():
    os.makedirs(T.OUT, exist_ok=True)
    disk = H.make_disk()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(3) as ex:
        fl = ex.submit(run, disk, "wrap_light", False)
        fb = ex.submit(run, disk, "wrap_busy", True)
        fp = ex.submit(run_punch, disk)
    ok = []

    def check(what, cond):
        ok.append(bool(cond))
        print(f"{'PASS' if cond else 'FAIL'}  {what}")

    for name, f, limit in (("light", fl, LIGHT_MAX), ("busy", fb, BUSY_MAX)):
        out, wraps, kept, played = f.result()
        notes = S.notes(kept) if kept else []
        print(f"   {name}: wraps {wraps} cycles ({', '.join(f'{c / 1e4:.1f}' for c in wraps)} ms), "
              f"{len(notes)} notes kept")
        check(f"{name}: no ERROR", "ERROR" not in out)
        check(f"{name}: 3 wraps, each under {limit} cycles ({limit / 1e4:.1f} ms)",
              len(wraps) == 3 and max(wraps) < limit)
        check(f"{name}: the kept take's notes on the 1/16 grid",
              notes and all(t % 12 == 0 or t == 1 for t, *_ in notes))
        check(f"{name}: every note played kept ({played})", len(notes) == played)
    out, takes, kept = fp.result()
    end = lambda w: next(t for t, ev in S.decode(w)[0] if S.code(ev[0]) == S.END)  # noqa: E731
    print("   punch: takes", [[(t, k) for t, k, *_ in S.notes(w)] + [("END", end(w))] for w in takes])
    check("punch: no ERROR", "ERROR" not in out)
    check("punch: from the second wrap on, every note before END (the loop-point hit at the start)",
          len(takes) >= 2 and all(t < end(w) for w in takes[1:] for t, *_ in S.notes(w))
          and any(t <= 1 for t, *_ in S.notes(takes[1])))
    check(f"punch: every note played kept ({len(PUNCH_NOTES)})", len(S.notes(kept)) == len(PUNCH_NOTES))
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
