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
| Every disk access after boot failed ("DISK NOT RESPONDING") | The FDC's DRQ and INTRQ weren't connected. The OS reads blocks by DMA: WD1772 DRQ → DMAC REQ0, INTRQ → DMAC PCL0 (see below) |

The patch also adds two test hooks to the panel device, both off unless set:
`ESQPANEL_LOG=1` logs the display bytes, and `ESQPANEL_KEYS=file` plays
panel buttons and keyboard keys from a script.

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

## Pressing buttons and playing keys

`KEYS=script.txt mame/run.sh ...` sends panel bytes at set emulated times.
Each line holds the time in seconds and hex bytes; `#` starts a comment.
The protocol comes from the OS's panel receive handler (`0xFF97A6`):

| Bytes | Meaning |
|---|---|
| `code\|80 00` / `code 00` | panel button `code` pressed / released |
| `code\|80 vel` | keyboard key down, note = code + 36 (C2), velocity `vel` (1–7F) |
| `code 00` | keyboard key up |

Button codes found so far (by pressing each and reading the display):

| Code | Button |
|---|---|
| 15 | LOAD (also 26, 33 open the disk's instrument list) |
| 35 | ENTER (YES) |
| 2, 4, 8, 14, 20, 22, 28, 34 | the 8 instrument buttons; 2 = instrument 1 |
| 5 | shows FREE SYSTEM BLKS |
| 6 | CREATE NEW INSTRUMENT |
| 9, 21, 27 | the disk's directories / sequences / MIDI files |
| 16, 17 | VOLUME |

To load an instrument: LOAD, ENTER ("PICK INSTRUMENT BUTTON"), an
instrument button. Press that instrument button again afterwards to play it
from the keyboard. `mame/keys/load1_play.txt` does this for file 1 of the
disk and plays three overlapping notes.

`tools/epstool.py add OS.img SOUNDS.gkh 1 OUT.img` copies an instrument
onto the OS disk, so no disk swap is needed. (Swapping disks from Lua with
`image:load()` failed before the DMA fix and hasn't been retried.)

## The mute group test

```sh
tools/fetch.sh sounds            # EPS factory drum disk 9 (TR 8O8) -> build/sounds
python3 mame/test_mutegroups.py  # about a minute
```

It builds stock, `1=1` and `1:C2=1,1:E2=1` disks with the TR 8O8 kit,
loads the kit from the panel in each, plays C2, E2, G2 300 ms apart, and
checks the voice lists (`mame/voices.lua`):

```
stock:   30.317 k36 k40            30.617 k36 k40 k43
mono:    30.317 k36(killing) k40   30.617 k40(killing) k43
kit:     30.317 k36(killing) k40   30.617 k40 k43
```

On the stock OS all three notes ring. With instrument 1 mono, each note
starts the fast kill on the one before (gone ~80 ms later). With the kit
groups, E2 cuts C2 but G2, which is in no group, leaves E2 alone.

## How the OS reads the disk (and why stock MAME failed)

The boot ROM's loader (`0xC0C046`) polls the WD1772. After boot the OS
uses the ROM's block routines, which go through OS hooks (`0xFF8178…`).
Before each READ, the hook at `0xFFDBC2` programs DMA channel 0 of the
HD63450-compatible DMAC at `0x240000`:
* DCR `0x81`: PCL = status input with interrupt;
* OCR `0x82`: device to memory, bytes, external request (REQ line);
* SCR 4: memory address counts up; MAR = the buffer; MTC = 513;
* CCR `0x88`: start, interrupts on.

The ROM then returns from the interrupt it's in (`0xC0B552`) and waits. The
FDC's DRQ paces the DMA. At the end of the command the FDC's INTRQ drops PCL,
and the DMAC interrupts at level 2 (vectors 65/66 → `0xFF8188` →
`0xFFDC2A`, which reads the FDC status and resumes the transfer).

## Writing scripts

* The OS runs from the low mirror in user mode, so breakpoints on OS code
  reached by `jsr`/`bsr` use the 16-bit address (`0x171E`). Code reached
  through an absolute-short jump (interrupt handlers, `jmp 0xFFxx.w`) runs
  at `0xFFFFxxxx`, so set both (`0x9814` and `0xFFFF9814`). Code we stage
  at `0xFFC994` or install in sample RAM uses its full address.
* `cpu.debug:bpset(addr, "", 'printf "...\\n", ...; g')` logs and continues;
  `printf` output goes to `debug.log` (run with `-debuglog`). In the
  debugger, `sp` is the supervisor stack; the OS's user stack is `usp`.
* OS RAM: `manager.machine.memory.shares[":osram"]`, offset = address & 0xFFFF.
  Sample RAM: `cpu.spaces["program"]:read_u8(addr)`.
* Debugger `save FILE,ff0000,10000` in a breakpoint action dumps memory.
* `ESQPANEL_LOG=1` makes the patched panel log every byte the OS sends to
  the display (`PANEL time hex`); `mame/screens.py` turns that into screens.

## Not covered yet

* MIDI in: MAME's `-midiin` plays a .mid file into the EPS's MIDI port
  (from 10 s), for sequencer and swing tests.
* The sound itself (`-sound none`); the ES5505 is emulated, so a WAV
  capture (`-wavwrite`) is possible later.
* The other button codes (edit pages, sequencer).
