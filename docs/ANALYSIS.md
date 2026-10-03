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

### Load address: 0xFF2000 (confirmed for the first 56 KB)

Evidence:
* Short-absolute calls (`jsr $xxxx.w`, about 2,000 of them) whose targets fall in
  `0x0000–0xBFFF` land right after an `rts` far more often when file offset =
  address − 0x2000 than at any other base.
* The pointer table at file offset 0x146 holds addresses like `0xFFC960` and
  `0xFF964A`. At base 0xFF2000 the code pointers land on routine entries (right
  after `rts`) and the data pointers land on zeroed variables.

Still open:
1. **Where the tail of the file goes.** At 0xFF2000 only 0xE000 bytes fit
   below 0xFFFFFF, but the file is 0x14E00 bytes and has code all the way to the
   end. Either some segments are copied or relocated at boot, or the EPS has
   more OS RAM than MAME maps. Calls into `0xFFC000–0xFFFFFF` don't fit
   base 0x2000 well, which suggests a RAM jump table or overlay there.
   Tracing the boot ROM's loader would answer this. That needs a dump of the
   `eps-l`/`eps-h` boot ROMs, which an owner can read from their own unit.
2. **The 8 KB block of `6D B6` at file offset 0x12000–0x13FFF.** This
   looks like a hole in the image (probably uninitialised RAM / BSS). If the OS
   doesn't use it at runtime, it is the obvious place for custom code.
3. **UI text is not stored as plain ASCII.** Only a few disk-utility strings
   (`COPY FLOPPY`, `BACKUP`, `RESTORE`, `INTERLEAVE`…) are readable. The main
   parameter and page names (TRUNCATE, LAYER, etc.) must be encoded or
   tokenised. Finding the display routine and its text format is needed before
   any new page or prompt can be added.

### Where the interesting code is (by hardware references)

| File offset page | Touches | Probably |
|---|---|---|
| 0x9000, 0x10000 | OTIS voice regs | Voice start/stop and allocation. **Mute groups hook here** |
| 0xB000, 0x11000 | FDC + DMAC | Disk I/O |
| 0x6000–0x7000, 0x10000 | DUART | Front panel / keyboard / MIDI |
| 0x6000, 0xB000 | Many boot-ROM calls | UI and disk layers |

The OS uses 68000 `TRAP #0–#15` (about 218 sites) as a system-call layer,
probably into the boot ROM.

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
