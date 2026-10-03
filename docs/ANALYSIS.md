# EPS OS 2.49: what we know so far

Source: `eps249os.exe`, a Chicken Systems "EPS/ASR DiskWriter" Windows 3.x
installer. It contains `EXTRACTO/eps249os.ede` (a Giebler EDE disk image) and
`ede.exe` (the DOS floppy writer). The installer's own archive format
(Robert Salesas ASETUP `.ARV`, `ARCV`/`BLCK` chunks) is not a standard
compressor. The easiest way to unpack it is to run the installer under Wine.

## Disk image

| Item | Value |
|---|---|
| Format | Ensoniq 800K DD: 1600 blocks × 512 B, 80 cyl × 2 heads × 10 sectors |
| EDE header | 0x00 text banner, 0xA0 skip bitmap (MSB first, 1 = block not stored), 0x1FF disk-type byte, data at 0x200 |
| Skipped blocks | Filled with the format pattern `6D B6` |
| Block 1 | Device ID block, volume label `EPS249O` at byte 31 |
| Block 2 | OS block: bytes 0–3 = free-block count (1418), `OS` at byte 28 |
| Blocks 3–4 | Root directory, 39 × 26-byte entries |
| Block 5+ | FAT, 3-byte big-endian entries, 170 per block, `1` = end of chain |
| Directory entry 0 | type 1 (OS), name `EPS-1 O.S.  `, 167 blocks, contiguous, starts at block 15 |

`tools/epstool.py` decodes and re-encodes this format byte-for-byte: EDE →
IMG → EDE gives back the identical file.

## OS file (`EPS-1 O.S.`, 85,504 bytes)

The CPU is a 68000. The OS is loaded from floppy into RAM on every boot by
the boot ROM. **The OS is not in flash, so a bad custom OS cannot brick the
unit.** Power off, insert a stock OS disk, and you're back.

### Memory map (from MAME `esq5505.cpp` plus this analysis)

| Range | What |
|---|---|
| `0x000000–0x007FFF` | Low mirror of OS RAM in user mode (boot ROM in supervisor mode) |
| `0x200000` | OTIS / ES5505 voice chip |
| `0x240000` | HD63450 DMAC |
| `0x280000` | MC68681 DUART (front-panel/keyboard link, MIDI) |
| `0x2C0000` | WD1772 floppy controller |
| `0x300000` | SCSI (WD33C93) |
| `0xC00000–0xC0FFFF` | Boot ROM. The OS calls into it about 290 times with `jsr abs.l` |
| `0xFF0000–0xFFFFFF` | OS RAM |

### OS layout: resident part + 8 KB overlays

| File offset | Loaded at | What |
|---|---|---|
| `0x00000–0x0BFFF` | `0xFF2000–0xFFDFFF` | Resident OS. Header pointer table at file 0x146 |
| (none) | `0xFF0000–0xFF1FFF` | OS variables, also reachable as `0x0000–0x1FFF` (abs.w) |
| (none) | `0xFFDF80–0xFFDFFF` | Stack (zeroed in the image), top at `0xFFE000` |
| `0x0C000` | `0xFFE000–0xFFFFFF` | Overlay 0 (in RAM at boot) |
| `0x0E000` | `0xFFE000` window | Overlay 1 |
| `0x10000` | `0xFFE000` window | Overlay 2 (disk utilities: COPY FLOPPY, BACKUP, SCSI…) |
| `0x12000` | `0xFFE000` window | **Overlay 3: empty (all `6D B6`), free for our code** |
| `0x14000` | `0xFFE000` window (at boot) | **Boot/init code** (3.4 KB, ~4.5 KB of the 8 KB slot unused): runs the init routines, ROM version check, sample-buffer setup |

Evidence:
* Short-absolute calls into `0x2000–0xBFFF` land right after an `rts` far
  more often at base 0xFF2000 than at any other base. The header pointer
  table lands on routine entries and zeroed variables at that base.
* For each 8 KB chunk from file 0xC000 on, calls into `0xFFE000+` only make
  sense if *that chunk* is what's in the window: 27/56, 41/75 and 23/35 hits,
  against 3/75 and 5/35 if the file were contiguous.
* The overlay loader at `0xFF4E40` (D1 = overlay number) reads from the
  **OS disk** into `0xFFE000`, retries with an "insert disk" prompt, and
  records the current overlay in `0xFFC8D0`. Callers pass 0, 2, or a stored
  number.
* Stack switches load `#0xE000` as SP (`0xFF85CE`, `0xFF8610`).
* The OS checks the boot ROM version word at `0xC00134` (compares it with
  `0x0114`).

`tools/epstool.py info` prints this layout, `tools/disasm.sh OS.bin [N]`
disassembles the resident part or overlay N at the right address, and patch
edits take `"overlay": N` for window addresses.

### Voice engine (resident)

| Address | What |
|---|---|
| `0xFF0940` | Voice records, 154 (0x9A) bytes each; count−1 in `0xFF16EC` |
| `0xFF16D8` | Free voice list (circular, sentinel = list head) |
| `0xFF16DC` | Releasing voices |
| `0xFF16E4` | Active (held) voices |
| `0xFF16E8` | Queue of voices waiting to start |
| `0xFFDF70` | Instrument pointer table (8 entries) |
| `0xFF16BA/BB` | Incoming note (key in BB), `0xFF16B6` velocity, `0xFF16BD` mask of instruments to play |
| `0xFF16BE` | Key after transpose, clamped 21–108 |

Voice record fields: `+0/+2` list links, `+4` key, `+6` instrument,
`+7` layer, `+10` pointer, `+12` state (0 idle, 4 held, 8 being killed,
10 start pending), `+16` layer ptr, `+22` wavesample params, `+26` sample
base, `+42/+44` start-queue links, `+150/+152` level.

| Routine | What |
|---|---|
| `0xFFACA4` | Note-on for one instrument (D5 = instrument); loops over its 8 layers |
| `0xFFAF54` | Allocate a voice for a layer (poly): retrigger the same key, else free list, else steal |
| `0xFFB046` | Allocate for mono/legato layers |
| `0xFFAEAC` | Note-off: walks the active list by key, releases via `0xFFB136` |
| `0xFFB7C2` | Fast-kill a voice (used when stealing); sets state 8 |
| `0xFFB4E8` | Start a voice on OTIS: page select, start/end/loop from the wavesample block (`+240/+248/+256/+264` via `movep.l`), sample-start modulation (`+280…+284`) |
| `0xFFBA92` | Drains the start queue `0xFF16E8` into `0xFFB4E8` |
| `0xFFB65C` | Stop all voices |

### Sample memory and the memory expander

The boot ROM sizes sample RAM (base EPS, or with the 2x/4x expander) and
leaves the bounds in two longs that the OS **only reads**:

| Variable | Use |
|---|---|
| `0xFF1656` | Sample memory start. The voice-start routine subtracts it from wavesample addresses, and a range check compares it with `0x580000` |
| `0xFF165A` | Upper bound of the sample area. A system buffer is set up at this address (`0xFF86EE`) and it is used as a base (`0xFF415E`), so the OS uses what sits above it |
| `0xFF1649` | Flag derived from bit 0 of the boot ROM version word `0xC00134` (`0xFF242A`) |
| `0xFF164C` | Copy of the boot ROM version word |

So patches must never hard-code sample addresses. They must read the
bounds, and then they work the same on a stock, 2x or 4x EPS.

The first 512 bytes of the OS file (`0xFF2000–0xFF21FF`) don't match what is
in RAM at run time. Code branches into this block (`bsr 0xFF21AC`) where the
file holds data, and calls `jsr 0x2080` into an all-zero area. The boot ROM
probably fills it with vectors and trampolines, so it is **not** free space.

### Sequencer (partial)

96 ticks per quarter note. `0xFF1602` = bar length (384 in 4/4).
Time-signature and bar/beat/tick math is at `0xFF5A18–0xFF5AE0` (variables
`0xFF803C` ticks per beat, `0xFF803E` beats, `0xFF8040` signature). The
record-time quantize ("auto-correct") routine is not found yet.

### Where the interesting code is (by hardware references)

| File offset page | Touches | Probably |
|---|---|---|
| 0x8000–0x9FFF (resident) | OTIS voice regs | Voice engine, mapped above |
| 0x10000 (overlay 2) | OTIS, DUART, DMAC | Disk/utility overlay code |
| 0xB000, 0x11000 | FDC + DMAC | Disk I/O |
| 0x6000–0x7000, 0x10000 | DUART | Front panel / keyboard / MIDI |
| 0x6000, 0xB000 | Many boot-ROM calls | UI and disk layers |

The OS uses 68000 `TRAP #0–#15` (about 218 sites) as a system-call layer,
probably into the boot ROM.

### Open questions

1. **Display text format.** Only a few disk-utility strings (`COPY FLOPPY`,
   `BACKUP`, `RESTORE`, `INTERLEAVE`, `COPY OS TO SCSI DRIVE?`) are plain
   ASCII, and all of them are in overlay 2. Parameter and page names
   (TRUNCATE, LAYER…) must be encoded or tokenised. Finding them is needed
   before adding pages or parameters.
2. **Free resident space** for real-time hooks. None found yet (see
   ROADMAP.md).
3. **How overlay numbers map to disk blocks.** The loader computes
   `d3 = n + 7` before the read, so the unit isn't confirmed yet. We need to
   confirm the OS will load overlay 3 when asked.
4. **How the boot code at file 0x14000 gets into the window**, and whether the loader always reads a full 8 KB (needed before appending code to it).

## Reproducing

```sh
# 1. Unpack the installer (Wine + a virtual display)
apt-get install wine wine32:i386 xvfb xdotool
Xvfb :9 & DISPLAY=:9 wine eps249os.exe   # press Enter through the wizard
cp ~/.wine/drive_c/EXTRACTO/eps249os.ede build/

# 2. Disk image -> OS binary -> disassembly
python3 tools/epstool.py ls      build/eps249os.ede
python3 tools/epstool.py extract build/eps249os.ede 0 build/eps_os_249.bin
python3 tools/epstool.py info    build/eps_os_249.bin
tools/disasm.sh build/eps_os_249.bin > build/eps_os_249.dis
```
