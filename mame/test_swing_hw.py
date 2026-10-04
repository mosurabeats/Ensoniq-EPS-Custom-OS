#!/usr/bin/env python3
"""The swing build (tools/mkswing.py, EPS249_SWING) on the whole emulated
EPS, with 13-bit sample RAM and boot ROM 2.40, as on the hardware.

One disk: OS 2.49 with the swing patch + the TR 8O8 kit. Runs:
* loop recording (mame/keys/loop_record.txt, 6 s later: this OS boots
  slower), QUANTIZE 1/16 and SWING% 50 (the power-on settings): the takes
  at the wraps and the take kept with KEEP = NEW are on the 1/16 grid, and
  the KEEP = OLD NEW prompt still comes up;
* the same with SWING% set to 58 on the Seq·Song page first (◄ once from
  the first parameter, ▲ 8 times): the odd 16ths are 2 ticks late;
* mute groups from the 6 Amp page (mame/keys/panel_mute.txt, 3 s later):
  E2 cuts C2, G2 cuts E2;
* Command mode: CREATE NEW SEQUENCE (overlay 0 comes back from the store,
  no disk read), then QUANTIZE on the Seq·Song page again.
Needs what mame/test_mutegroups.py needs, and build/bootrom/r240.
"""
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import test_mutegroups as T  # noqa: E402
import test_panel as P  # noqa: E402
import seqstream as S  # noqa: E402

ROM = os.path.join(T.ROOT, "build", "bootrom", "r240")
C2, E2, G2 = 36, 40, 43


def shifted(src, by, upto=None, extra_from=None, extra=0):
    """Key lines `by` seconds later (and `extra` more from `extra_from` on,
    in the original times)."""
    out = []
    for line in open(src):
        m = re.match(r"^(\d+(?:\.\d+)?)(\s.*)$", line)
        if m:
            t0 = float(m.group(1))
            t = t0 + by + (extra if extra_from is not None and t0 >= extra_from else 0)
            if upto is None or t < upto:
                out.append(f"{t:.2f}{m.group(2)}\n")
    return out


def make_disk():
    os_disk = os.path.join(T.OUT, "swinghw_os.img")
    disk = os.path.join(T.OUT, "swinghw.img")
    T.sh(sys.executable, os.path.join(T.ROOT, "tools", "mkswing.py"),
         os.path.join(T.ROOT, "build", "eps_os_249.bin"), "-o", os.path.join(T.OUT, "swinghw.json"),
         "--disk", os.path.join(T.ROOT, "build", "eps249os.img"), os_disk)
    T.sh(sys.executable, os.path.join(T.ROOT, "tools", "epstool.py"), "add", os_disk, T.DRUMS, "1", disk)
    return disk


# Loop recording, 6 s later than mame/keys/loop_record.txt. The take at each
# wrap (after the buffer switch), the final take at STOP (before KEEP) and
# the kept one after ENTER at the prompt (KEEP = NEW).
SHIFT = 6
LOOP_LUA = """
local ram = manager.machine.memory.shares[":osram"]
local prog = manager.machine.devices[":maincpu"].spaces["program"]
local SHIFT = %d
local set, swing_set, last, pending, final_done, kept_done = false, false, nil, nil, false, false
local function dump(tag, t, start)
  local s = ""
  for i = 0, 2000 do
    local v = prog:read_u16(start + 2 * i)
    s = s .. string.format("%%04x ", v)
    if v & 0xFFF0 == 0x8BC0 then break end
  end
  print(string.format("%%s %%.2f %%s", tag, t, s))
end
emu.register_periodic(function()
  local t = manager.machine.time:as_double()
  if not set and t > 36 + SHIFT then set = true; ram:write_u8(0x815f, 2) end
  if t < 37 + SHIFT or prog:read_u8(0xff815f) ~= 2 then return end
  local base, a, b, w = prog:read_u32(0xff8104), prog:read_u32(0xff8114), prog:read_u32(0xff8118), prog:read_u32(0xff811c)
  if t < 45 + SHIFT and w ~= 0 then
    local cur = (w >= b) and "B" or "A"
    if last and cur ~= last then pending = t + 0.05 end
    last = cur
    if pending and t >= pending then
      pending = nil
      dump("TAKE", t, base + ((cur == "B") and a or b) + 28)
    end
  end
  if not final_done and t > 45.4 + SHIFT then final_done = true; dump("FINAL", t, base + a + 28) end
  if not kept_done and t > 46.8 + SHIFT then kept_done = true; dump("KEPT", t, base + a + 28) end
end)
"""


def run_loop(disk, name, swing_keys):
    """Loop recording; with swing_keys, they go in a 5 s gap after the
    instrument is selected (29.15 s + SHIFT), before recording."""
    keys = os.path.join(T.OUT, name + ".txt")
    extra = 5 if swing_keys else 0
    shift = SHIFT + extra                   # for the recording part
    lines = shifted(os.path.join(T.ROOT, "mame", "keys", "loop_record.txt"), SHIFT,
                    upto=45.5 + shift, extra_from=29.5, extra=extra)
    lines += [f"{46.0 + shift:.2f} a3 00    # ENTER at KEEP = OLD NEW: NEW\n",
              f"{46.15 + shift:.2f} 23 00\n"]
    open(keys, "w").write("".join(swing_keys + lines))
    lua = os.path.join(T.OUT, name + ".lua")
    open(lua, "w").write(LOOP_LUA % shift)
    env = dict(os.environ, KEYS=keys, RUN=os.path.join(T.OUT, "run_" + name), BOOTROM=ROM,
               EPS_SAMPLERAM16="0")
    out = T.sh(os.path.join(T.ROOT, "mame", "run.sh"), disk, str(int(48 + shift)), lua, env=env)
    takes = {}
    for line in out.splitlines():
        p = line.split()
        if p and p[0] in ("TAKE", "FINAL", "KEPT"):
            try:
                takes.setdefault(p[0], []).append(S.notes([int(x, 16) for x in p[2:]]))
            except ValueError:
                pass
    return out, takes


# SWING% 58 from the panel before recording (after the instrument is
# selected at 35.15 s): Edit, Seq·Song, ◄ (SWING%), ▲ x8, then instrument 1
# again (play mode).
SWING58 = (["35.60 85 00\n", "35.75 05 00\n", "36.00 95 00\n", "36.15 15 00\n",
            "36.40 90 00\n", "36.55 10 00\n"]
           + [f"{36.8 + 0.3 * i:.2f} 8a 00\n{36.95 + 0.3 * i:.2f} 0a 00\n" for i in range(8)]
           + ["39.40 82 00\n", "39.55 02 00\n"])


def run_mute(disk):
    keys = os.path.join(T.OUT, "swinghw_mute.txt")
    open(keys, "w").write("".join(shifted(os.path.join(T.ROOT, "mame", "keys", "panel_mute.txt"), 3)))
    lua = os.path.join(T.OUT, "swinghw_mute.lua")
    open(lua, "w").write(f'dofile("{T.ROOT}/mame/voices.lua")\n' + P.GROUPS_LUA.replace("t < 29", "t < 32"))
    env = dict(os.environ, KEYS=keys, RUN=os.path.join(T.OUT, "run_swinghw_mute"), BOOTROM=ROM,
               EPS_SAMPLERAM16="0", VOICES_FROM="35.9", VOICES_TO="37.5")
    out = T.sh(os.path.join(T.ROOT, "mame", "run.sh"), disk, "38", lua, env=env)
    frames = [(float(l.split()[1]), [tuple(map(int, v)) for v in re.findall(r"\[k(\d+) i(\d+) s(\d+)\]", l)])
              for l in out.splitlines() if l.startswith("VOICES ")]
    return out, frames


CMD_KEYS = ["32.0 82 00\n32.15 02 00\n",                          # instrument 1
            "33.0 86 00\n33.15 06 00\n33.6 95 00\n33.75 15 00\n",  # Command, Seq·Song
            "34.2 a3 00\n34.35 23 00\n35.0 a1 00\n35.15 21 00\n",  # CREATE NEW SEQUENCE, Cancel
            "36.0 85 00\n36.15 05 00\n36.6 95 00\n36.75 15 00\n",  # Edit, Seq·Song
            "37.2 90 00\n37.35 10 00\n37.8 90 00\n37.95 10 00\n"]  # ◄ ◄: QUANTIZE
CMD_LUA = """
local cpu = manager.machine.devices[":maincpu"]
cpu.debug:bpset(0x4e40, "", 'printf "DISKLOAD %x\\\\n",d1; g')
manager.machine.debugger:command("g")
"""


def run_cmd(disk):
    keys = os.path.join(T.OUT, "swinghw_cmd.txt")
    open(keys, "w").write("".join(shifted(os.path.join(T.ROOT, "mame", "keys", "panel_mute.txt"), 3, upto=16)
                                  + CMD_KEYS))
    lua = os.path.join(T.OUT, "swinghw_cmd.lua")
    open(lua, "w").write(CMD_LUA)
    env = dict(os.environ, KEYS=keys, RUN=os.path.join(T.OUT, "run_swinghw_cmd"), BOOTROM=ROM,
               EPS_SAMPLERAM16="0")
    return T.sh(os.path.join(T.ROOT, "mame", "run.sh"), disk, "39", lua, env=env)


def on_grid(notes, swing=0):
    """Every note on the 1/16 grid (tick 1: the take's floor, a downbeat),
    odd 16ths `swing` ticks late."""
    return all(t == 1 or (t - (swing if (t // 12) % 2 else 0)) % 12 == 0 for t, *_ in notes)


def main():
    os.makedirs(T.OUT, exist_ok=True)
    disk = make_disk()
    with ThreadPoolExecutor(4) as ex:
        f_straight = ex.submit(run_loop, disk, "swinghw_loop", [])
        f_swing = ex.submit(run_loop, disk, "swinghw_loop58", SWING58)
        f_mute = ex.submit(run_mute, disk)
        f_cmd = ex.submit(run_cmd, disk)
        (out, takes), (s_out, s_takes) = f_straight.result(), f_swing.result()
        m_out, frames = f_mute.result()
        c_out = f_cmd.result()
    ok = []

    def check(what, cond):
        ok.append(bool(cond))
        print(f"{'PASS' if cond else 'FAIL'}  {what}")

    check("no ERROR on the display", "ERROR" not in out + s_out + m_out + c_out)
    check("KEEP = OLD NEW still asked at STOP", "KEEP =   OLD    NEW" in out)
    check("the wraps quantize: the last take before STOP on the 1/16 grid",
          takes.get("TAKE") and takes["TAKE"][-1] and on_grid(takes["TAKE"][-1]))
    check("kept with NEW: the final take on the 1/16 grid (its last pass too)",
          takes.get("KEPT") and on_grid(takes["KEPT"][0]) and not on_grid(takes["FINAL"][0]))
    print("   final before KEEP:", [(t, k) for t, k, *_ in takes.get("FINAL", [[]])[0]])
    print("   kept:             ", [(t, k) for t, k, *_ in takes.get("KEPT", [[]])[0]])
    check("SWING% 58 set on the Seq·Song page", "SWING%=" in s_out)
    kept58 = s_takes.get("KEPT", [[]])[0]
    check("SWING% 58: odd 16ths 2 ticks late", kept58 and on_grid(kept58, 2) and not on_grid(kept58)
          and any((t // 12) % 2 for t, *_ in kept58 if t > 1))
    print("   kept (58%):       ", [(t, k) for t, k, *_ in kept58])
    killed = lambda key: P.killed_at(frames, key)  # noqa: E731
    check("mute groups: MUTE GROUP on the 6 Amp page", "MUTE GROUP=" in m_out)
    check("mute groups: E2 cuts C2, G2 cuts E2, G2 rings",
          killed(C2) and killed(E2) and not killed(G2))
    check("Command: CREATE NEW SEQUENCE runs", "NEW NAME=" in c_out)
    check("Command: overlay 0 back without a disk read", "DISKLOAD 0" not in c_out)
    check("back in Edit: QUANTIZE on the Seq·Song page again", "QUANTIZE=" in c_out)
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
