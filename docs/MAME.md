# Testing in MAME

MAME's `eps` driver (`src/mame/ensoniq/esq5505.cpp`) runs the real boot ROM
and loads the OS from a disk image, so it tests the things the Unicorn
tests can't: the boot loader, the kernel, the stacks, the OS init, and
the display.

Stock MAME doesn't boot the EPS. `mame/eps.patch` fixes it:

| Problem in stock MAME | Fix |
|---|---|
| Supervisor-mode writes to `0x0000–0x7FFF` were dropped, but the boot ROM loads the OS there in supervisor mode | EPS: all writes reach RAM; only supervisor reads see the ROM |
| Floppy select and status lines not wired for the EPS ("PLEASE INSERT DISK") | DUART OP0 = drive select, OP1 = side, IP0 = ready, IP1 = disk changed (from the schematics) |
| The OS stalled at its first button-light update | The keyboard/panel controller acks every byte with `0xFF`; the OS waits for it |

With these, stock OS 2.49 boots like the hardware: LOADING SYSTEM, TUNING
KBD - HANDS OFF, KEYBOARD TUNED, NO INSTRUMENTS.

## Build

```sh
mame/build.sh            # clones MAME (pinned commit) into build/mame/src, patches, builds
```

It builds only the Ensoniq driver (`SUBTARGET=eps`), but MAME's core is big,
so the first build takes a long time (set `JOBS=` for more cores). Needs the SDL2, ALSA and fontconfig development
packages. The boot ROM halves go in `build/bootrom/unknown/eps-h.bin` and
`eps-l.bin` (docs/RESOURCES.md; MAME's set CRC `d8747420` / `382beac1`).

## Run

```sh
mame/run.sh DISK.img [SECONDS] [SCRIPT.lua]
```

This boots the disk with no video or sound, as fast as the host allows
(about 10× real time). It then prints every display screen with its time,
followed by the Lua script's output. The default script, `mame/boot.lua`,
reports:
* the OS entry and its stack pointer;
* "main loop reached" when the OS finishes its init;
* any CPU exception (address error, illegal instruction, line F) with the
  PC where it happened;
* the sample heap end, and whether the note-on hook site is stock or calls
  the code area, and the code area's first bytes.

Example (mute group test disk):

```
   2.78s  '    LOADING SYSTEM    ...'
   8.04s  'TUNING KBD - HANDS OFF...'
   8.17s  'KEYBOARD TUNED...'
   9.19s  'NO INSTRUMENTS '
OS entry, user stack ffffca84
main loop reached
heap end (0xFF165A) 007ffa00
note-on hook site (0xFFACA4) 4eb9007ffc264e71
code area 7ffc00: 227c00ffc994323c0053425951c9fffc
```

MAME has a 4x expander fitted (heap end `0x7FFE00` stock, `0x7FFA00` with
the code area).

**Disk images:** use `.img` (raw 800K). MAME reads our `.hfe` files with a
CRC error on block 17; the Gotek reads them fine. `tools/mkcodearea.py` and
`epstool.py` write either, picked by the output file name.

## Writing scripts

* The OS runs from the low mirror in user mode, so breakpoints on OS code
  use the 16-bit address (`0x171E`, not `0xFF171E`). Code we stage in the
  `0xFFC994` area or install in sample RAM uses its full address.
* `cpu.debug:bpset(addr, "", 'printf "...\\n", ...; g')` logs and continues;
  `printf` output goes to `debug.log` (run with `-debuglog`). In the
  debugger, `sp` is the supervisor stack; the OS's user stack is `usp`.
* OS RAM: `manager.machine.memory.shares[":osram"]`, offset = address & 0xFFFF.
  Sample RAM: `cpu.spaces["program"]:read_u8(addr)`.
* Debugger `save FILE,ff0000,10000` in a breakpoint action dumps memory.
* `ESQPANEL_LOG=1` makes the patched panel log every byte the OS sends to
  the display (`PANEL time hex`); `mame/screens.py` turns that into screens.

## Not covered yet

* Pressing panel buttons and playing notes. Next: MIDI in (MAME's
  `-midiin` takes a .mid file) plus an instrument disk, to watch voices in
  RAM for the mute group test.
* The sound itself (`-sound none`); the ES5505 is emulated, so a WAV
  capture (`-wavwrite`) is possible later.
