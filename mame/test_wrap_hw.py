#!/usr/bin/env python3
"""How long loop recording holds up the sequencer at each loop wrap, on the
swing build (13-bit sample RAM, boot ROM 2.40, as on the hardware).

Anything the wrap hook (0xFF6746, src/swing/window.s) spends delays the
first notes of the next pass: the hardware showed the downbeat 20-25 ms
late while loop recording (2026-10-05, sq re-encoding the whole take at
every wrap). The fast path (sq.s, sqf) moves only the new notes, in place.

* light: mame/keys/loop_record.txt (a snare and a hat per pass);
* busy: the same with a closed hat on every 16th of every pass, each held
  50 ms (some are held over the wrap).
Each wrap is timed in CPU cycles (MAME runs the EPS's 68000 at 10 MHz),
then the take kept with NEW must have every note on the 1/16 grid.
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


def run(disk, name, busy):
    lines = H.shifted(os.path.join(T.ROOT, "mame", "keys", "loop_record.txt"), 6, upto=51.5)
    if busy:
        t = 43.6
        while t < 50.7:
            lines += [f"{t:.3f} 86 50\n", f"{t + 0.05:.3f} 06 40\n"]
            t += 0.125
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
    return out, wraps, kept


def main():
    os.makedirs(T.OUT, exist_ok=True)
    disk = H.make_disk()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(2) as ex:
        fl = ex.submit(run, disk, "wrap_light", False)
        fb = ex.submit(run, disk, "wrap_busy", True)
    ok = []

    def check(what, cond):
        ok.append(bool(cond))
        print(f"{'PASS' if cond else 'FAIL'}  {what}")

    for name, f, limit in (("light", fl, LIGHT_MAX), ("busy", fb, BUSY_MAX)):
        out, wraps, kept = f.result()
        notes = S.notes(kept) if kept else []
        print(f"   {name}: wraps {wraps} cycles ({', '.join(f'{c / 1e4:.1f}' for c in wraps)} ms), "
              f"{len(notes)} notes kept")
        check(f"{name}: no ERROR", "ERROR" not in out)
        check(f"{name}: 3 wraps, each under {limit} cycles ({limit / 1e4:.1f} ms)",
              len(wraps) == 3 and max(wraps) < limit)
        check(f"{name}: the kept take's notes on the 1/16 grid",
              notes and all(t % 12 == 0 or t == 1 for t, *_ in notes))
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
