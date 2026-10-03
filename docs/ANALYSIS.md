# EPS OS 2.49: what we know so far

Source: the stock OS 2.49 disk. `tools/fetch.sh` downloads it as
`EPS249OS.hfe` from HxC2001's `QuickInstall_FloppyDiskImages.zip` and checks
it against a second copy on archive.org (`eps-os-v-249`). Both hold the same
OS file, SHA-256 `01911d8f…cb79e3`. The notes below were first made from
`eps249os.ede` out of the Chicken Systems "EPS/ASR DiskWriter" installer, and
it is the same OS. See docs/RESOURCES.md for every source.

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

### OS layout: what the boot ROM loads where

The boot ROM (`0xC0C046`, after checking the OS version against
`0xC00134`) reads disk blocks into OS RAM. The OS file starts at block 15:

| Disk blocks | File offset | Loaded at | What |
|---|---|---|---|
| 15 | `0x00000–0x001FF` | `0xFF0000` | Exception vectors |
| 16–126 | `0x00200–0x0DFFF` | `0xFF2200–0xFFFFFF` | Resident OS, plus overlay 0 in the window |
| 175–180 | `0x14000–0x14BFF` | `0xFF1600–0xFF21FF` | Early variables (mostly zero), the **OS entry at `0xFF171E`** and low resident code, including `0xFF2000–0xFF21FF` |
| 181 | `0x14C00–0x14DFF` | `0xFF0732` | Disk/OS info block (the ROM also copies `0x732–0x758` to `0x200`) |
| 127–174 | `0x0E000–0x13FFF` | not at boot | Overlays 1, 2, 3 (3 is empty, all `6D B6`) |

| RAM | What |
|---|---|
| `0xFF0000–0xFF15FF` | Vectors, OS variables, voice records (`0xFF0940`) |
| `0xFF1600–0xFFDFFF` | Resident OS (entry `0xFF171E`); also reachable as `0x1600–0x7FFF` (abs.w) |
| `0xFFDF80–0xFFDFFF` | Stack, top at `0xFFE000` |
| `0xFFE000–0xFFFFFF` | Overlay window (overlay 0 at boot) |

The OS's overlay loader (`0xFF4E40`, D1 = overlay n) reads 16 blocks from
disk block 16·(n+7)−1 into the window, by absolute block number.

(Earlier notes called file `0x14000` a "boot overlay" run from the window.
That was wrong. The ROM loads it to `0xFF1600`: with that base, 54 of the 75
absolute calls into it land on routine entries, against 12 of 261 at
`0xFFE000`, and the OS calls into it all the time, e.g. `0xFF1E54`.)

`tools/epstool.py` (`LOAD_MAP`) maps addresses to file offsets this way.
`tools/disasm.sh OS.bin` disassembles the resident part, `… low` the
`0xFF1600` chunk, and `… N` overlay N.

Evidence:
* Short-absolute calls into `0x2000–0xBFFF` land right after an `rts` far
  more often at base 0xFF2000 than at any other base. The header pointer
  table lands on routine entries and zeroed variables at that base.
* For each 8 KB chunk from file 0xC000 on, calls into `0xFFE000+` only make
  sense if *that chunk* is what's in the window: 27/56, 41/75 and 23/35 hits,
  against 3/75 and 5/35 if the file were contiguous.
* The overlay loader at `0xFF4E40` (D1 = overlay number) reads from the
  **OS disk** (disk block 16·(n+7)−1, 16 blocks) into `0xFFE000`, retries with an "insert disk" prompt, and
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
| `0xFFB7C2` | Fast-kill a voice (a4); sets state 8 and leaves it in its list. d4 = ramp rate 0–99 (read by ROM `0xC095D0`; the stealer passes 10). Changes d4/a1; saves d6/a0 only as words |
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
(How the bounds are set, and how our code area takes 1 KB off the top: see
"Boot and the sample memory" below.)

RAM `0xFF2000–0xFF21FF` is loaded from file `0x14A00`, not from file
`0x0000` (which holds the vectors and goes to `0xFF0000`). That's why the
OS's `jsr 0x2080` looked like a call into data in earlier notes.

### Boot and the sample memory

The OS entry `0xFF171E` first calls `0xFF832E`, a trampoline
(`jmp 0xC08490`) to the ROM's sample-memory setup, then the other init
routines, then the main loop (`0xFF1774`, `trap #6` waits for events).
`0xFF832E` has no other caller.

ROM `0xC08490` → `0xC0854C` sizes sample RAM with a write/read test:

| Fitted | Start (`0xFF1656`) | Size | Heap end (`0xFF165A`) | Physical top |
|---|---|---|---|---|
| Base EPS | `0x580000` | 512 KB | `0x5FFE00` | `0x600000` |
| 2x expander | `0x580000` | 1 MB | `0x67FE00` | `0x680000` |
| 4x expander | `0x600000` | 2 MB | `0x7FFE00` | `0x800000` |

Then `0xC084AC` sets the heap `[start, start + size − 512)` (size in
`0xFF166A`, also `0xFF165E/62`), writes the heap header at `start`, and saves
copies (`0xFF1666…0xFF1676`) that `0xFF833A` (`0xC08500`, used at `0xFFA112`,
`0xFFA176` and overlay 2) restores later. The 512 bytes above the heap are
the system block (`0xFF86EE` builds it from the ROM template `0xC02000`).
With a 4x expander the internal 512 KB at `0x580000` is outside the heap,
and overlay 0 uses it for sequencer memory (`0xFFE0EE`). The OS reads
`0xFF1672` as an available-size figure (minimums 656, 224), never as a fixed
total.

### Code area (our code in sample RAM)

`src/codearea.s` takes the top 1 KB of physical sample RAM for our resident
code (`tools/mkcodearea.py` builds it):

1. The patch points `0xFF832E` at an installer staged in a zero run of the
   OS file (`0xFFC994`, runtime buffers). Since the OS entry calls it first,
   nothing else in the OS has run yet.
2. The installer runs `0xC08490`, subtracts 1 KB from `0xFF166A` and re-runs
   `0xC084AC`. The heap, its header and the saved copies all shrink by 1 KB
   the ROM's own way, and the system block moves 1 KB down.
3. It copies the payload to the top 1 KB (`0x5FFC00` / `0x67FC00` /
   `0x7FFC00`), restores the trampoline, and writes `jsr` into each hook site
   whose stock bytes match (skipping any that don't).
4. It jumps to the copy, which zeroes the staging bytes and returns to the
   OS entry with the ROM's registers. After that, OS RAM matches a stock boot
   except for the bounds (1 KB less) and the hook sites.

The emulator test (`tests/test_codearea.py`) checks this for all three memory
configs and both boot ROMs. Not yet checked on hardware: that the 68000 runs
code from sample RAM (first hardware test).

### Sampling (overlay 2)

Overlay 2 holds the sampling code along with the disk utilities.

| Address | What |
|---|---|
| `0xFF020F` | Sample rate index (default 35). 40 rates, 6.25–52.1 kHz |
| `0xFF0210` | Sampling parameter, ×2000 when used (default 0) |
| `0xFF0211` | Flag (default 1). When 0, OP7 is driven the other way. Probably INPUT LEVEL = MIC/LINE (service manual sampling test) |
| `0xFF0212` | Filter cutoff index (default 11) |
| `0xC06FFE` (ROM) | 40-byte table: rate index → default filter index (0 up to rate 20, then rising to 11 at rate 39) |
| `0xC07026` (ROM) | 40-byte table: rate index → divisor, 100 … 12. Sample rate = 625 kHz / divisor |
| `0xC0704E` (ROM) | Filter table, 12 entries: `29 2a 2b 2c 2d 2e 2f 38 39 3a 3b 3c`. Byte E: bits 0–2 → sound chip → CA0–CA2, bits 4–6 → OP4–OP6, bit 3 unused (see below) |
| `0xFFE20E` | Reset filter from the rate (called from `0xFF45A0` when the rate parameter changes) |
| `0xFFE2BA` | Sample clock: divisor × 4 → DUART counter (`movep.w` to CTUR/CTLR at `0x28000D`) |
| `0xFFE2D6` | Sampling setup: MUTE (OP2) high, then OP4–OP6 from E and OP7 from `0xFF0211` (`0xFFE2F6`), written via the DUART set/reset output-port registers (`0x28001D/1F`). A pin is high when its E bit is 1 |
| `0xFFE358` | Reads E (`0xFFE38E`) and writes `(E & 7) \| 0x38` to sound-chip reg `0x200012` on a range of voice pages. Returns E in d0. Only caller is `0xFFE2F4` |
| `0xFFE3E6` | Input level meter: reads the input sample from OTIS `0x200018`, peak and average |
| `0xFFFD14` | Sampling defaults |

The resident analog-control scanner (`0xFFBE46`, 6 × 24-byte records at
`0xFFC334`) also drives OP4–OP6 to select which front-panel analog input to
read. Sampling disables that interrupt (IMR = `0x20`) before using the same
lines for the filter, so the lines are probably shared or latched. The
service manual's analog test page lists exactly six analog inputs (pitch
wheel, mod wheel, volume slider, CV pedal, data slider, patch-select
buttons), which matches the scanner's six records. So OP4–OP6 are definitely
the analog-mux select lines. The schematics (below) show how OP4 also sets the
filter.

### Sampling filter hardware (from the schematics)

Source: *Ensoniq EPS Schematics* (archive.org `sm_Ensoniq_EPS_Schematics`),
main board 4010007501 rev N (digital) / 4010007501 rev P (analog) and
4010010002 rev L (1 MEG RAMS board). `tools/fetch.sh` downloads it.

**DUART output port** (68681, U38 on 10002, U58 on 7501):

| Pin | Net | Pin | Net |
|---|---|---|---|
| OP0 | DSEL (drive select) | OP4 | AN1 (mux select) + filter counter MSB |
| OP1 | SSEL (side select) | OP5 | AN2 (mux select) |
| OP2 | MUTE | OP6 | AN0 (mux select) |
| OP3 | SREQ (counter/timer out = sample clock) | OP7 | MIC/LINE (preamp gain, 4053 U54) |

Inputs: IP0 DSTAT, IP1 DSKCH, IP2/IP3 500 kHz (timer clock), X1 5 MHz.

**Analog mux** (4051, U45 on 10002): Y0 pitch wheel, Y1 patch buttons, Y2 mod wheel,
Y3 volume slider, **Y4 sampling input**, Y5 data slider, **Y6 sampling
input**, Y7 pedal/CV. Channel = 4·AN2 + 2·AN1 + AN0. The sampling input is
wired to both Y4 and Y6, so AN1 (OP4) can change without changing the mux
input. During sampling AN2 must be 1 and AN0 must be 0.
(Both Y4 and Y6 read "SAMPLE" on a low-resolution scan. This fits OP4 doubling
as the counter MSB, and probe disks N ≥ 8 and N < 8 would show it.)

**Anti-aliasing filter:** an XR-1008 switched-capacitor low-pass (U53 on 10002), always
in the signal path between the input preamp and the A/D. It has no bypass.
The cutoff follows its clock FCLK:

```
10 MHz -> 74LS161 (preset N = {D=AN1/OP4, C=CA2, B=CA1, A=CA0})
       -> RCO -> 74LS74 (reload; held off by MUTE low) -> 74LS74 ÷2 -> FCLK
FCLK = 10 MHz / (2 * (17 - N))     N = 0 … 15  ->  294 kHz … 2.5 MHz
```

The divider is drawn on the 7501 digital sheet (U37 74LS161A, U39 74LS74,
sheet bottom right). On the 10002 sheet FCLK leaves the digital section
through R74 (22 Ω); its source there is not traced yet, so check it on the
10002 board before relying on it.

CA0–CA2 are the sound chip's channel-address outputs (U43 on 7501, U37 on
10002, marked **5504 DOC II**, i.e. ES5504, not ES5505/OTIS). So the filter
code is split: E bits 0–2 go out through the sound chip (the `0x200012`
write, presumably the voices' channel-assign field), and E bit 4 goes out on
OP4. **Higher N = higher cutoff; N = 15 is the widest the hardware can do.**
**The cutoff is FCLK / 50.** The boot ROM confirms the whole chain:

* The stock table decodes to N = 1, 2, … 12 for filter settings 0 … 11
  (N = setting + 1). N = 0 and 13–15 are never used.
* The FILTER CUTOFF display labels (ROM `0xC03AC4`, 12 values) are
  6.25, 6.67, 7.14, 7.69, 8.33, 9.09, 10.0, 11.1, 12.5, 14.3, 16.7, 20.0 KHZ,
  exactly FCLK / 50 for N = 1 … 12 with the formula above.
* The default filter per rate gives fc ≈ 0.34–0.38·fs from rate 21 up. Below
  that the filter stays at its floor (6.25 kHz, above Nyquist), so the stock
  EPS already aliases at low rates.

N = 13, 14, 15 would be 25, 33.3 and 50 kHz. (Whether the XR-1008 still
behaves at a 2.5 MHz clock is for the probe to show.)

Consequences:
* A true filter bypass needs a hardware mod. In software, OUT = force N = 15.
* E = `0x28 | (N & 8) << 1 | (N & 7)` keeps the mux on Y4/Y6 and matches the
  stock entries for N = 1–12.
  `tools/filterprobe.py` builds one disk per N this way.
* The earlier probe disks (which forced OP4–OP6 directly) mostly switched the
  A/D to a wheel or slider. Only patterns 2 and 3 sampled audio.

### From the EPS/EPS-M service manual (P/N 9312 000 701-B)

* No schematics (they are a separate document, see above); it's a
  module-swap manual. Boot EPROMs: **U26 = LOWER, U27
  = UPPER** on the main board. Boot ROM v2.0+ is needed for SCSI and OS ≥ 2.00.
* Two main-board revisions: **7501**, and **10002** (serial ≥ 16582 /
  240 V ≥ 502603: new layout, gate array, different RAM chips). Filter and
  input behaviour should be checked on the board the tester has.
* 2x expander: FREE SYSTEM BLOCKS > 2000; 4x: > 4000.
* The keyboard/KPC is a 68HC11 on the DUART (error 32 = DUART overrun from
  the MC68HC11), and all display traffic goes through it.
* System error codes: 16 VC unknown message, 17 voice list corrupted,
  49 parser bad parameter type, 56/57 memory allocation, 63 RAM, 64 no SCSI,
  128–139 CPU exceptions, 144 out of system buffers, **145 unknown sampling
  interrupt**, 192 unknown sequencer event, 194 no sequencer event buffers.
  Useful for diagnosing crashes in patched OSes.

### Sequencer (partial)

96 ticks per quarter note. `0xFF1602` = bar length (384 in 4/4).
Time-signature and bar/beat/tick math is at `0xFF5A18–0xFF5AE0` (variables
`0xFF803C` ticks per beat, `0xFF803E` beats, `0xFF8040` signature). There is
no record-time quantize text in the ROM; QUANTIZE TRACK seems to be the only
quantize.

**Track events** (decoded by the iterator `0xFF6792`, which calls a handler
per event type from a table): variable length, first word's bits 11–4 = code.

| Code | Type | Size | Notes |
|---|---|---|---|
| 0–87 | 0 | 2 words | Note on, key = code. Delta = w0 bits 14–12 (high) + w1 bits 14–11 (low), 0–127 ticks. Velocity = w1 bits 10–4 |
| 88–175 | 1 | 2 words | Probably note off, key = code − 88, same layout |
| 176–183 | 2 | | |
| 184 | 3 | 1 word | |
| 185 | 4 | 2 words | |
| 186 | 5 | 5 words | |
| 187… | 6… | | |

The iterator keeps its state at `0xFF8144` (`+2` event pointer, `+6` delta,
`+8` first word, `+18` code, `+19` velocity). Longer gaps need other events,
since a delta is at most 127 ticks.

**QUANTIZE TRACK** (record `0xFFC4D6`, handler `0xFFED96`, overlay 0):
* Grid = word table at ROM `0xC03F32` indexed by `0xFFE00C`:
  48, 32, 24, 16, 12, 8, 6, 4, 3, 2 ticks (1/8 … 1/128T, "QUANTIZE TO 1/").
* `0xFFEE26` aligns to the grid: `divu` gives step and remainder; the
  remainder against grid/2 decides down or up, and sets the window
  `0xFF804E`/`0xFF8050` (distance to the next half-grid boundary / grid line)
  and the running position `0xFF804A`.
* Per-event handlers come from the table at `0xFFEE68` (type 0 → `0xFFEEE0`,
  most others → `0xFFEF08`). `0xFFEF1C…0xFFEFBE` advances the window by each
  event's delta, adds `grid` each time a boundary is passed (`0xFFEF34`), and
  moves notes by swapping event words and adjusting deltas.
* Swing fits in that loop: alternate the boundary step between grid + offset
  and grid − offset, starting from the step parity found at `0xFFEE26`.

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

## Boot ROM

Two dumps, not committed. Put them in `build/bootrom/` (see RESOURCES.md):

| Set | Version word `0xC00134` | CRC32 high / low EPROM |
|---|---|---|
| 2.00 (MAME `eps`: `eps-h.bin`, `eps-l.bin`) | `0x0200` | `d8747420` / `382beac1` |
| 2.40 (`eps_os_24_hi/lo.bin`) | `0x0228` | `2492aee1` / `31b25dc2` |

2 × 32 KB, interleaved (high EPROM = even bytes) at `0xC00000–0xC0FFFF`.
Reset SSP `0x1548`, PC `0xC0BE38`. `tools/bootrom.py join` builds the 64 KB
image. The two versions differ in 492 bytes. Every string and table used
below sits at the same address in both.

### Display messages

The OS's "message numbers" (`move.w #$14EB,a2; jsr $23FC`) are **ROM offsets
of NUL-terminated messages**. Inside a message, a byte below `0x20` starts a
2-byte big-endian reference to another message; other bytes are text. So
`0x069E` = ref `0x0AD4` ("WAVESAMPLE ") + "INFORMATION". All message numbers
are below `0x2000`. Digits with a decimal point have their own codes (`;` =
"6.", `[` = "7.", `!` = "0." …). `tools/bootrom.py msg` decodes messages, and
`annotate` adds the text to a disassembly (65 sites in the resident part,
17 in overlay 0, 27 in overlay 2; short lowercase hits like "cjgb" are
probably display graphics, not text).

### Command records

`0xFFC43C–0xFFC81D` in the OS holds 71 command records of 14 bytes:
handler.w, message.w, flags.w, 3 × button handler.w, 0. Handler words are
short addresses in OS RAM: the handler is `0xFF0000 | word` (see "User mode
and the low mirror" below). docs/COMMANDS.md lists them all
(`tools/bootrom.py commands`).

### User mode and the low mirror

The OS runs in **user mode**. MAME's `lower_r` maps `0x000000–0x00FFFF` to
the boot ROM for supervisor accesses and to OS RAM (`0xFF0000+`) otherwise.
So every short absolute address in the OS is OS RAM: `jsr $23FC` is
`0xFF23FC` (`moveq #102,d2; trap #10`, a display call into the ROM), and
`0x7F88` is `0xFF7F88` (CALIBRATE KEYBOARD). The OS reaches the ROM through
`TRAP`s and `jmp $C0xxxx`.

For handlers in the overlay window, **flags bits 15–12 = 8 + overlay
number**: `0x8…` = overlay 0 (sequencer commands, e.g. QUANTIZE TRACK at
`0xFFED96`), `0x9…` = overlay 1 (wavesample edits), `0xA…` = overlay 2
(pitch tables, MSB ADJUSTMENT). Checked by finding a routine entry at the
handler address in that overlay for 19 commands. The dispatcher that reads
the flags isn't located yet. If it handles `0xB…`, new commands can live in
overlay 3.

### Sampling page parameters

Descriptors at ROM `0xC028DC`: display handler, RAM variable, message, word:

| Variable | Message | Display |
|---|---|---|
| `0xFF020F` | SAMPLE RATE (`0x19EA`) | ROM `0x38F0` |
| `0xFF0212` | FILTER CUTOFF (`0x19F6`) | ROM `0x3ABE`: 12 labels 6.25 … 20.0 KHZ |
| `0xFF0210` | (`0x19FC`, pre-trigger) | |
| `0xFF0211` | INPUT LEVEL (`0x1B6C`) | ROM `0x3AAE`: MIC / LINE |

### Open questions

1. ~~**Display text format.**~~ Solved: messages live in the boot ROM (see
   Boot ROM → Display messages). New pages can reuse ROM messages. New text
   still needs a way to print our own strings.
2. **Free resident space** for real-time hooks. None found yet (see
   ROADMAP.md).
3. ~~**How overlay numbers map to disk blocks.**~~ Disk block 16·(n+7)−1,
   16 blocks (see OS layout). Overlay 3's slot is empty and loadable.
4. ~~**Boot code at file 0x14000.**~~ Not a boot overlay: it's loaded to
   `0xFF1600` and holds the OS entry (see OS layout).
5. **Boot ROM code.** We have the ROM now (2.00 and 2.40). Still to map:
   the TRAP handlers, the display routine behind `jsr $23FC`, the command
   dispatcher (flags → overlay) and how the low-RAM handler addresses
   (`0x4B54`, `0x7F88` …) get filled.
6. ~~**XR-1008 clock-to-cutoff ratio.**~~ 50:1, from the ROM's cutoff labels.

## Emulator tests

`tools/emu.py` runs OS code in Unicorn (68000), with the boot ROM at
`0xC00000`, the OS at `0xFF2000`, an overlay in the window, and OS RAM also
mapped at `0x000000` (user-mode mirror) and `0xFFFF0000` (24-bit bus).
Hardware registers are plain RAM. No floppy, panel or timing, so it tests
routines, not the machine. `python3 -m unittest discover tests` runs:

* `tests/test_mutegroup.py`: the mute hook calling the real OS voice kill
  (and its ROM routine) on hand-built voice lists, plus a check that the
  patched note-on entry leaves every register as stock does. These caught two
  bugs: the kill's word-sized `movem` sign-extends d6, and `moveq` cleared
  d0's upper word.
* `tests/test_swing.py`: the reference swing math in `tools/swing.py`.

## Reproducing

```sh
apt-get install binutils-m68k-linux-gnu poppler-utils
tools/fetch.sh                      # OS images + schematics/manuals -> build/

python3 tools/epstool.py ls      build/eps249os.ede
python3 tools/epstool.py info    build/eps_os_249.bin
tools/disasm.sh build/eps_os_249.bin > build/eps_os_249.dis
```

The schematic PDFs are scans without text. `pdfimages -j` gives the full
2480 × 1760 pages.

Older OS files land in `build/os_versions/`: EPS 2.2 and 2.45, and EPS-16+
1.00–1.30 (the HxC files `EPS1xxOS.hfe` are EPS-16+ OSes, file name
`EPS-16+ O.S.`). 2.45 is relocated against 2.49 (44k bytes differ), so compare
routines, not offsets.
