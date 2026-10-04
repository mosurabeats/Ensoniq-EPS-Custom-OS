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

### Sample RAM is 13 bits wide (found on hardware)

The internal sample RAM is 13 DRAMs (41256, 256K x 1) on data lines
DA19-DA7 (schematic 4010007501): CPU data bits 15-3. Bits 2-0 of every
word don't exist. All 322,816 sample words in the factory instrument files
have them at 0. MAME models the RAM as 16 bits wide, so anything we put in
sample RAM that needs those bits worked there and fails on a real EPS:
* **Code can't run from sample RAM.** The code area disks give ERROR 131
  (illegal instruction) on a real EPS (OS 2.49, boot ROM 2.40, 2x
  expander); the loader's own stack is up there too. Our code has to move
  to OS RAM.
* Data in sample RAM (instrument data, sequences) can only use bits 15-3
  of each word: FULL LEVEL / ONE-SHOT values in low bytes and the undo
  tags in bits 3-0 of a note's last word need moving.

MAME now emulates this (`mame/eps.patch`: sample RAM writes keep bits
15-3). The code-area disks then fail in MAME too (ERROR 137, boot ROM 2.40)
while the stock OS boots. `EPS_SAMPLERAM16=1` gives the old 16-bit RAM back
for the code-area tests.

### Resident build (everything in OS RAM)

`tools/mkresident.py` (`tools/mkmutetest.sh`: `EPS249_MUTE`) puts mute
groups and the MUTE GROUP parameter in OS RAM, which is 64 KB and full.
The room comes from **boot-only code**: the OS entry (`0xFF171E`) is a list
of `jsr`s to init routines that never run again once the main loop
(`0xFF1774`) starts. Ours, at the end of boot:

| Where | What | From |
|---|---|---|
| `0xFF1720-0xFF1763` | mute code (`src/resmute.s`, 68 bytes) | the entry's `jsr` list (`0xFF171E-0xFF176F`) |
| `0xFF86E6-0xFF86F7` | 6 Amp index table: the 8 ROM entries, then ours | init routine `0xFF86E6` (`0xFF870A` is used later) |
| `0xFF874C-0xFF875F` | MUTE GROUP descriptor (`08 00 000F 011E 8754`) and label | init routine `0xFF874C-0xFF8765` |
| `0xFFC110` | 6 Amp page record: first/current `86E6`, last and end `86F6` | |
| `0xFFAF92` | hook `jsr 0x1720.w` over `move.w 0x16BE.w,d0` | |

Index tables, descriptors and labels in OS RAM from `0xFF8000` up work
with no hooks at all (the OS takes words from `0x8000` up as OS RAM
addresses, see Edit pages), so the menu is just data.

The hook is in the layer's voice start (`0xFFAF54`), where `a3` is the new
voice's wavesample record: the group is that wavesample's byte `0x11E`, a
high byte, safe in 13-bit RAM. Every sounding voice (both lists) whose
wavesample has the same group is cut with the OS's fast kill, except
voices of the same key and instrument (the note's other layers; the OS
retriggers a held key itself). This runs only when a voice really starts,
so key-up layers with no voice cut nothing.

**Getting the bytes there.** The boot ROM loads the OS file and jumps to
the entry, so the payload has to be in the file somewhere that survives
until the end of boot. Measured in MAME (boot ROM 2.40, a Lua write tap
from the entry's first `jsr` to the `jsr` at `0xFF1770`): the zero runs in
the file that nothing writes in that time are the bottoms of two stacks,
`0xFFC994-0xFFCA3D` (init task stack, top `0xFFCA84`; the boot reaches
`0xFFCA3E`) and `0xFFC8E8-0xFFC92B` (supervisor stack, top `0xFFC960`;
interrupts reach `0xFFC92C`), plus kernel areas that interrupts or tasks
use later (the message pool `0xFFCBEC-0xFFCFF4`, the voice task's stack
`0xFFCA84-0xFFCAFB`): not safe. The last boot call, `jsr 0x1EF4.w` at
`0xFF1770`, becomes `jsr 0xC994.w`: the late init (`src/lateinit.s`) at the
bottom of the init stack, whose stack pointer is at the top (`0xFFCA84`)
then, far above it. It copies the chunks in carrier 2 (`0xFFC8E8`, 52 bytes) and carrier 1 (after
its own code, up to `0xFFCA2D`), then jumps to `0x1EF4`. Each carrier ends
with a magic long ("MUTE"); if a stack has reached either, nothing is
copied and the stock OS runs. The hook and page record are copied last.

Confirmed on a real EPS (boot ROM 2.40, 2x expander): boots, the menu
works, groups cut as designed, and MUTE GROUP survives SAVE INSTRUMENT and
reloading (the stock OS loads such an instrument fine).

**How fast the cut is.** The kill (`0xFFB7C2`) ramps the voice's level
(voice `+90`) to 0 in a straight line, with the step per envelope tick
taken from the ROM's rate table `0xC05232` by an envelope time 0-99 (`d4`):
32767, 32767, 16384, 10922, 8192, ... (3822 at 10), so the ramp lasts
32767 / table[time] ticks. Envelope ticks are 12 ms (measured in MAME by
tapping the voice level writes, which the OS makes through the low mirror,
`0x000940` + 154 × voice). The voice stealer's time 10 is about 9 ticks:
~100 ms, long enough to hear both notes of a flam (found on hardware).
`--choke` sets it; the default is 2 (two ticks, gone ~24 ms after the new
note). The kill starts at the next tick, up to 12 ms after the note.
The OS writes K1, K2 and LVOL of each sounding voice about every
millisecond (`0x20000C-0x200010`, filter envelopes moving in small steps
between ticks), so it smooths its own 12 ms steps. MAME's EPS sound output
is silent (LVOL is 0 in MAME and nothing reaches the speaker), so clicks
can only be judged on hardware.

### Code area (our code in sample RAM)

> **Doesn't work on hardware**: code can't run from 13-bit sample RAM
> (above). Kept as the emulator-only design the features were developed
> on; they move to the resident build one at a time.

Our resident code runs from the top of physical sample RAM (4 KB by
default). It comes in two parts, built by `tools/mkcodearea.py`:

* **The loader** (`src/loader.s`, about 200 bytes) sits in a zero run of the
  OS file at `0xFFC994`, and the patch points the trampoline `0xFF832E` at it.
* **The image** (`src/codearea.s`: header, init, hook table, mute groups,
  later swing and loop recording) sits in the OS file's empty **overlay-3
  slot**: file offset `0x12000`, disk blocks 159–174, 8 KB. The OS only
  loads overlay n when a command asks for it (from block 16·(n+7)−1), and
  no command uses overlay 3. Being inside the OS file, the image travels
  with it.

At boot the OS entry's first instruction calls the trampoline, before any
other OS code runs. The loader then:

1. Runs the ROM sizing (`0xC08490`), subtracts the area from the heap size
   (`0xFF166A`), and re-runs `0xC084AC`. The heap, its header and the saved
   copies shrink the ROM's own way; the system block moves down.
2. Switches to a stack at the top of the area, so it barely uses the OS's
   (16 bytes measured).
3. Reads the image's blocks into the area with the boot loader's own block
   read (`0xC0B55C`: block in `0x228`, destination in `0x22C`, error in
   `0x2C8`, five retries). Two things have to be as during boot:
   * **The drive must be selected.** The ROM deselects it after loading the
     OS, so the loader calls `0xC0A5E0` (select, about 0.75 s spin-up wait)
     and `0xC0A5F4` (deselect) around the reads.
   * **Interrupts must be masked.** The read polls the FDC, and with
     interrupts on it loses bytes (MAME: error 4 on the first block). The
     OS entry runs in user mode, so the loader gets into supervisor mode
     through trap #10. Its vector points into OS RAM (`0xFF832A`,
     `jmp 0x95D8.w`): the loader puts `jmp super.w` there for one call,
     masks interrupts in `super`, reads, `rte`, and puts the jump back.
4. Checks the image ("EPS!", length, all words summing to 0) and calls its
   `init`, which writes `jsr` into each hook site whose stock bytes still
   match. On a read error or a bad image there are no hooks: the EPS boots
   as stock, minus the area's bytes of sample memory.
5. Restores the trampoline and returns to the OS entry with the ROM
   sizing's registers.

Boot takes about a second longer (the spin-up wait and the reads).

**Where the loader can go.** The zero run at `0xFFC994` is not free
memory: it holds the task stacks. The OS's task table at `0xFFBEDC` gives
(stack top, entry) per task: init `0xFFCA84`/`0xFF171E`, voice
`0xFFCAFC`/`0xFFAC14`, `0xFFCB74`/`0xFF583A`, `0xFFCB94`/`0xFFB1D0`. The
header at `0xFF0140` points the kernel at its other structures: task records
from `0xFFCB94`, the message buffer pool `0xFFCBEC–0xFFCFF4`, the supervisor
stack top `0xFFC960`. The boot ROM builds the task records and buffer pool
before it jumps to the OS entry. The entry then runs as the init task with
its user stack at `0xFFCA84`. So the loader lives at the bottom of the init
stack, `0xFFC994–0xFFCA63`, and the 32 bytes below `0xFFCA84` stay free
for the OS entry's `jsr` and the two ROM calls made before the stack switch.

History: the first build staged the whole payload in these stacks and
copied it out. It crashed in MAME: the init stack overwrote the payload
before the copy (illegal instruction), and an earlier variant zeroed the
kernel's buffers (ERROR 137). The second build fitted, but left only 176 +
272 bytes, so the code moved to the overlay-3 slot.

`tests/test_codearea.py` runs the loader on the real init stack, with the
kernel's data above it, garbage in sample RAM, and the ROM block read
stubbed to serve the disk, for all three memory configs and both boot
ROMs. It also checks that reads run with interrupts masked, the OS-stack
use, a read error, and a corrupted image. MAME boots the drum disk with the
image loaded from disk and the mute groups working. Not yet checked on
hardware: that the 68000 runs code from sample RAM (first hardware test).

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

### Edit pages (parameters)

`tools/params.py ROM OS` dumps every edit page with its parameters.

* **Page records** in OS RAM (pointer list at `0xFFC14C`, current page in
  `0xFFC08A`): first, last and current index entry (words), page number,
  and the end of the search-by-number range (`+8`, `0xFF2FEC`). EDIT pages:
  `0xFFC0CA` track (SEQ ST, MIX, PAN), `0xFFC11A/124/12E` envelopes 1–3,
  `0xFFC138` wavesample pitch (ROOT KEY …), `0xFFC106` filter,
  `0xFFC110` wavesample amp (WS VOLUME, PAN, fades, VOLUME MOD),
  `0xFFC142` LFO, `0xFFC0F2` wavesample (MODE, SMPL START … RANGE),
  `0xFFC0E8` layer, `0xFFC0DE` instrument, `0xFFC0B6` sequencer (TEMPO,
  CLICK, SEQ COUNTOFF, RECORD MODE), `0xFFC0A2` MIDI, `0xFFC0AC` system,
  `0xFFC0D4` the edit selection (instrument, LYR, WS).
* An **index entry** is a word pointing at an 8-byte **descriptor**: flags
  (bits 4–0 parameter number; bit 7 and 6: shown on one line with the
  next/previous one), type (handler table `0xFFD066`: 0 number 0–max,
  2 0–127, 3 signed, 0x0E choice from a label table at w2 …), w2 (max or a
  table), where the value is (an offset in the wavesample / layer /
  instrument record, or an OS RAM address), label (a ROM message number).
  Index tables and descriptors are in the boot ROM (`0xC02226…0xC027F8`).
* Words below `0x8000` are ROM offsets, from `0x8000` OS RAM (`0xFF2CA4`,
  ROM `0xC0821A`); labels likewise (ROM `0xC081EC`), and a long label
  pointer from `0x8000` up is used as it is. But the OS also keeps resolved
  index entry addresses as words (`move.w a3,a5@(4)`, `cmpa.w a5@(2),a3`),
  so index tables can only be in ROM or OS RAM.
* Value storage: `0xFF2DC6…0xFF2EB0`: instrument data (`a4`), layer offset
  (`0xFF83A0`, `d5`), wavesample offset (`0xFF83A6`, `d6`); the envelopes
  are at +0x26, +0x52, +0x7E in the wavesample record. With WS=ALL an edit
  goes to every wavesample of the layer.
* **Wavesample record** (in the instrument data, `0x120` bytes, then the
  sample data): one parameter per word, value in the high byte; name at
  +0x0A (12 characters, one per word); envelopes; +0xAA ROOT KEY … +0x11C MOD. Byte +0x11E is 0 in all
  78 factory wavesamples we have and nothing in the OS reads it: our mute
  group. The instrument data in memory is the file as on disk (checked
  byte for byte), so it saves with the instrument.
* **Panel**: in EDIT, the number buttons pick the page; codes 16/17
  (ids 0x22/0x24) step to the previous/next parameter (wrapping), the
  arrows (codes 10/11) change the value. docs/MAME.md has the codes.
* **Choice parameters** (type 0x0E): w2 points at a 6-byte table: a long
  pointer to fixed-width NUL-terminated labels, the width, the count
  (`0xFF33FC`). The OS resolves w2 at `0xFF33EA` (display) and `0xFF3B1E`
  (edit).
* **Note-on for key-up layers:** the note-off runs the instrument note-on
  `0xFFACA4` again for the KEYUP LAYERS (`0xFF16C2` = 0x32; 0x30 for the
  key-down layers, `0xFFAC4E`/`0xFFAE7C`). A hook there must check which.
* **Our parameters** (`src/pages.s`, `mkcodearea.py --pages`): the ROM index
  tables are packed, so raising a page's "last" takes in the next table's
  first entry; hooks at `0xFF2CA6`, `0xFF3214`, `0xFF32F6` return our
  descriptor for that slot when it's reached through that page's record,
  `0xFF3308` shows our label text from the code area (label words `0x7000`
  + offset), and `0xFF33EA`/`0xFF3B1E` find our choice tables. Added:
  * MUTE GROUP after VOLUME MOD on the 6 Amp page (byte +0x11E). The
    mute hook (`src/mutegroup.s`) takes the new note's group from the
    wavesample the key plays (first layer with one) and a sounding voice's
    from its wavesample (voice +22).
  * FULL LEVEL and ONE-SHOT (OFF/ON, the ROM's own OFF/ON table) before
    MUTE GROUP, in wavesample bytes +0x11F and +0x11D (0 in all factory
    wavesamples; no OS or ROM code reads a word over them). `src/voice.s`:
    FULL LEVEL makes the voice start (`0xFFB252`) use velocity 127;
    ONE-SHOT skips the release at key-up (`0xFFAE12` walks the note's held
    voices, release call at `0xFFAE5E`; `0xFFB13C` is a branch target, so
    `0xFFB136` itself can't be hooked) for no-loop samples (MODE +0xEE 0
    or 1), which then stop by themselves at the sample end.
  * QUANTIZE (choice: OFF … 1/32T) and SWING% after RECORD MODE on the
    sequencer page, in `0xFF8174`/`0xFF8175` (after the last 10-byte
    sequencer list node at `0xFF816A`; no references in the OS or ROM).
    `src/looprec.s` panel_swing turns them into the swing settings.
  MAME (`mame/test_panel.py`): both pages show and edit, groups cut, a
  QUANTIZE set on the panel quantizes a loop take.

### Kernel and tasks (boot ROM)

The CPU reads its vectors in supervisor mode, which sees the boot ROM, so the
OS file's vector block is empty and the kernel lives in the ROM. Traps 0–9
and 12–15 go to `0xC073xx–0xC076xx`; traps 10/11 point back into the OS
(`0xFF832A`/`0xFF8326`, display services). Level-1 autovector `0xC0937C`.

| Trap | Service |
|---|---|
| 0 | System error, code in d0 (the numbers in the service manual) |
| 1 | Yield (save context, reschedule) |
| 2 | Message buffer available? (carry set if not) |
| 3 | Allocate a message buffer into a5 (none left: error 144) |
| 4 | Free buffer a5 |
| 5, 7 | Wait with timeout |
| 6 | Receive: next message for the current task into a5 (waits if none) |
| 8 | Set the current task's timer (d0) |
| 9 | Send message a5 to the task whose control block is a1 |
| 12 | Queue a5 on a1 (used for MIDI out, `0xFFC97A`) |

Current task control block pointer at `0x0134`; free message list at
`0x0136`. A message has a type word at `+2` and data from `+4`. Task blocks
seen as send targets: `0xFFCB94`, `0xFFCBAA`, `0xFFCBC0` (22 bytes apart).
The OS file's header at `0xFF0140` configures the kernel. It holds the
message pool bounds `0xFFCBEC`/`0xFFCFF4`, task records `0xFFCB94`, the
supervisor stack `0xFFC960`, the stack area `0xFFC994`, and the task table
`0xFFBEDC–0xFFBEEC`: four (stack top, entry) pairs, init being
`0xFFCA84`/`0xFF171E`.

* **Voice task** (loop `0xFFAC22`): receives a message, uses the type as an
  even offset into `0xFFAC3A`: 0 → note-on `0xFFAC4E`, 2 → `0xFFAE12`,
  4 → `0xFFAEA6`, 10 → note-off `0xFFAEAC`, 12 → `0xFFAF4E`; 6 and 8 →
  system error 16 ("VC unknown message").
* **Sequencer playback** builds note messages at `0xFF654C` (type 8 or 10;
  `+4` key, `+5`, `+6` velocity, `+7` instrument bit) and sends them to
  `0xFFCBAA`, plus MIDI out through trap 12 when `0xFF16A6` enables it.
* The sequencer is a state machine: `0xFF8028`/`0xFF802A` (saved) hold
  state handler addresses. Seen in MAME: `0xFF588E` stopped, `0xFF58B2`
  playing, `0xFF58D6` recording over a track, `0xFF5942` recording a new
  sequence (`0xFF815A` bit 1 set) and, briefly, each LOOPED wrap (saved
  state `0x58D6`), `0xFF58FA` after STOP. LOOPED record mode
  (`0xFF815F` = 2) branches off them; `0xFF815E` = keep OLD/NEW.
* **Sequencer task** (task 3, entry `0xFF583A`, control block `0xFFCBC0`):
  waits on `trap #6`, then dispatches the message type through the table
  that the state word `0xFF8028` points to (stopped: `0xFF588E`; recording a new sequence:
  `0xFF5942`). Messages are dropped while `0x160A` = 1 and `0x160D` ≠ 0.
  Transport buttons arrive as type `0x16` with the button (id − 0x40) at
  `+4` and press 1 / release 2 at `+6` (sent by the panel handler
  `0xFF9774`). In every state they go to `0xFF7AA4`, which
  hands the button to entry 14 + button of the state's table (PLAY with
  RECORD held counts as RECORD). RECORD (0) only sets bit 7 of `0xFF815A`
  while held, so recording is RECORD held + PLAY, as on the real EPS
  (MAME: "SEQUENCE 01 BAR=1", state `0x5942`). While recording over a
  track (`0x58D6`) RECORD and PLAY do nothing (entries 14 and 15 are the
  no-op `0xFF588A`): loop undo uses RECORD there.
* **Recording writes a delta-time event stream** (in MAME, at `0x580220…`
  in the internal 512 KB). On a played note, `0xFF7388` first flushes the
  ticks since the last event (`0xFF804A`) as time events (`0x8B90 | …`, or
  added to the previous event's 7-bit delta when small), then the note
  event is appended (`0xFF6E72`; `0xFF74EE` patches the stream after it).
* **Note events** are three words (found by recording known notes in MAME):
  w0 bits 14–12 = delta to the next event, high 3 bits; bits 11–4 = key −
  21; w1 bits 15–3 = duration in ticks; w2 bits 14–11 = delta, low 4 bits;
  bits 10–4 = velocity. Events with "key" codes 0xB0+ are others: `0x8B9x`
  carries long time gaps, and recording starts with `0x8BBx/8B1x/8B8x/8BDx`
  controller states.
* **LOOPED recording merges every pass itself.** At each loop wrap the
  sequencer passes through state `0x5942`, and the record pointer
  (`0xFF811C`) flips between two buffers (offsets `0x0278` and `0x10278`
  in sequencer memory): the pass just played is merged into the other
  buffer. Only STOP asks "KEEP = OLD NEW".
* **The KEEP prompt** is UI code at `0xFF2702`: it shows the prompt
  (`0xFFA4EC`), waits for a button, and stores OLD (button 4) → 0 or NEW
  (button 6) → 1 in `0xFF815E`, then goes on at `0xFF2652`.
  `mkcodearea.py --auto-keep` replaces it with "store 1, go on"
  (`mame/test_loop_record.py`: no prompt, the new notes play back).
* **LOOPED internals** (sequencer memory base `0xFF8104`):
  * Two take buffers at offsets `0xFF8114` / `0xFF8118`, `0xFF8128` bytes
    each, with a 28-byte header (the take's length is stored at +0 by
    `0xFF6B2E`). `0xFF811C` = write pointer, `0xFF812C` = room left.
  * During a pass the sequencer plays one buffer and writes the other: the
    played events (copied as playback reaches them) plus what you play.
    Every take starts with `0x8BB0` (start), a 1-tick time event, the
    controller states (`0xB1`, `0xB8`, `0xBD`) at tick 1, and ends with the
    END event `0x8BC0` at the loop length.
  * Loop wrap `0xFF6726` (LOOPED: `0xFF6742`): `0xFF6B12`, `0xFF6AD6`
    (finish the take: gap to the end, END), `0xFF6B2E` (store the length,
    swap: `0xFF811C` = the other buffer + 28), state `0x5942`, then playback
    of the new take (`0xFF61EE`, `0xFF6276`, `0xFF632E` …).
  * STOP: `0xFF6A0E` assembles the final take in buffer A (the unplayed
    rest of the previous take moved next to the partial pass, memmove
    `0xFF5EE4`); then the commit `0xFF6B78` (`0xFF74F2` closes held notes,
    `0xFF7690` merges the take into the track if KEEP = NEW).
  * Writing an event: `0xFF737A` stages it at `0xFF8144` (+8 = its words,
    +21 = word count), `0xFF7428` checks room, `0xFF7388` flushes the
    ticks since the last event (`0xFF804A`), `0xFF6E56` appends it (and
    sets bit 15 of its first word). A note just played arrives with bit 15
    clear; events copied from the previous take have it set.
  * `0xFF8038` (long) = position in the loop in ticks = the take time.
  * Playback and the copy into the next take are one step: the decoder
    (`0xFF67C4`…`0xFF68AC`) reads an event of the played take into the
    staging area (`+8` its words, `+6` its gap, `+18` key, `+19`
    velocity, `+21` word count) and jumps to the handler for its type
    (table `0xFF6368`; notes `0xFF638A`). The note handler starts a voice
    (`0xFF63D6`), sets the wait from the gap (`0xFF637A`) and then copies
    the event into the take being written if LOOPED recording
    (`0xFF7586`: `0xFF5F28` clears the gap, `0xFF737A` writes it).
  * The OS writes ticks only when it writes an event (`0xFF7388`): the
    time since the last event goes into that event's 7-bit gap, or a
    time event when bit 6 of `0xFF815A` is set or the gap is too long. So
    an event that's never written leaves no hole in the timing.
  * Velocity is read as `((w2 >> 3) & 0xFF) >> 1` (`0xFF6882`): bits 3–0
    of a note's last word are unused (0 in recordings).
  * Held notes being recorded: list at `0xFF8134` (+0 next, +2 duration,
    +6 = offset of the duration word, bit 0 = buffer B). Note-off writes
    the duration there (`0xFF74C2`).
* **Swing quantize of LOOPED takes** (ROADMAP #2, `--swing`): the append
  hook logs each new note (offset, time, quantized time); at the wrap,
  after `0xFF6AD6`, the logged notes are moved in place (`src/swing.s`
  swing_logged; usually just two gaps change because the earlier notes sit
  on the grid lines), keeping the held-note records right; a note that
  quantizes onto the loop end wraps to the start. The full re-encode
  (swing_full) is the fallback, and what STOP uses. Measured in MAME: a
  pass adding 16 new 16ths costs 2.4 ms at the wrap (0.6 ms stock),
  scaling with the notes added in that pass, not the take's size. Notes
  land at the swung grid on the next pass, like an MPC.
* **Loop undo** (ROADMAP #2, `--undo`, on with `--swing`): the append hook
  tags each note played with the pass's generation (1–15) in bits 3–0 of
  its last word; copies keep only the last pass's tag. RECORD (hook in
  `0xFF7AA4` at `0xFF7AD4`) while loop recording adds a tag to the kill
  mask: this pass's if notes were played in it, else the last pass's. The
  note handler hook (`0xFF638A`) skips killed notes of the take being
  played (no voice, no copy; just `0xFF637A` for the gap), so they drop
  out of the next take with the timing intact; the kill mask lasts one
  more pass for the notes still in the take being played. STOP re-encodes
  the final take without them (swing_kill) and clears the tags before
  the commit. MAME: `mame/test_undo.py`.

### The overlay window during play and recording (room for swing)

The swing code (2.3 KB in the emulator build) can't be resident: OS RAM is
full and sample RAM can't run code. Measured and read to see whether it can
borrow part of the overlay window instead:
* **Overlays 0-2 fill the window** (8186 of 8192 bytes each; only the last
  32 bytes are the same in all three), so there's no common free tail.
  Overlay 4 is 3.4 KB, overlay 3 is empty.
* **Overlay 0 is the one normally loaded**: the sequence and track
  COMMANDS (CREATE/COPY/APPEND SEQUENCE, QUANTIZE/COPY/ERASE/SHIFT TRACK,
  EVENT EDIT, ...: docs/COMMANDS.md) plus a little code used all the time
  (the task at `0xFF583A` calls `0xFFE0B8`).
* **What runs from the window** (MAME, ROM 2.40, a read tap over the
  window by 256-byte page, `mame/keys/loop_record.txt` on the stock OS):
  boot and LOAD read `0xFFE000-0xFFE3FF`; recording a new sequence, loop
  recording, both KEEP prompts and playback read only
  `0xFFE000-0xFFE0FF`. No overlay is loaded in any of it.
* **Commands load their overlay through the dispatcher** (`0xFF2A76`):
  the command record says which (flags bits 6-4 of its byte 12), and the
  overlay loader `0xFF4E40` (D1 = overlay) is called only when
  `0xFFC8D0` (current overlay) differs. The same dispatcher answers
  "STOP SEQUENCER FIRST" while the sequencer runs (`0xFFBFD2` != 0).
  The other loader calls: `0xFF5394` (same compare), `0xFF8A1A` (overlay
  2, sampling) and `0xFF277A` (overlay 0, retried until it loads).
* **QUANTIZE TRACK** (`0xFFED96`) re-records the whole track through the
  event writer (`0xFF7388`, iterator `0xFF6792` with its handler table at
  `0xFFEE68`) into the record buffers, with the sequencer stopped: not
  usable at a loop wrap.

### Swing build (hardware)

`tools/mkswing.py` (`tools/mkswingtest.sh`). Our code borrows the region
from `0xFFE400` of the window (as long as the image, up to `0xFFFFDF`; the
first 1 KB is read at boot and `0xFFE000-0xFFE0FF` by the sequencer, the
last 32 bytes are common to all overlays), and parks what it displaced in
a store at the top of sample RAM (one byte per word, in the high byte).
It's in the window in play and Edit mode (`0xFF160A` = 0 or 2) and out in
Command mode (1, which is also where sampling runs): the main-loop hook
swaps both ways, the loader hook takes it out when the OS asks for an
overlay. Outside Command mode the stock OS can't rely on any overlay's code
(after sampling or an instrument command another overlay stays in the
window while you play and edit), and measured in MAME nothing reads the
window past `0xFFE3FF` then. (The first hardware test, `EPS249_SWING`,
commit dfea704, borrowed only `0xFFEB48-0xFFF4B7` and stayed in during
Command mode until a command asked for its overlay.)

| Piece | Where | What |
|---|---|---|
| early | `0xFFC994` (boot stage) | the trampoline `0xFF832E` to the ROM's sample sizing comes here: takes the store off the heap (`0xFF166A`), redoes the ROM bookkeeping |
| late | boot stage | instead of the boot's last `jsr 0x1EF4`: exchange (overlay 0's region bytes -> store), load overlay 3 with the OS's loader, check "SWG1", run install |
| overlay-3 slot | OS file | overlay 0 with our window image in the region |
| install | window | resident chunks below, then patch |
| mute | `0xFF1720` | as in `EPS249_MUTE`, hook `0xFFAF92` |
| ldr | `0xFF4E20-0xFF4E3F` | the loader's four callers call it; if ours is in: unpatch, exchange, and skip the disk if the overlay asked for is the one we displaced; then falls into the loader `0xFF4E40` |
| ml | `0xFF2990` (hook `0xFF1774`) | top of the UI loop: ours should be in unless the mode is Command (`0xFF160A` = 1): exchange and patch, or `out` (window: unpatch, then exchange) |
| HIT | `0xFF874C` (hook `0xFFB252`), `0xFF4EA8` + `0xFF1764` (hook `0xFFAE54`) | FULL LEVEL / ONE-SHOT, below |
| swapx | `0xFF86E8` | the exchange loop |
| vars | `0xFF8174-0xFF8177` | QUANTIZE, SWING%, in-flag, displaced overlay |

patch/unpatch (window code) switch: the 6 Amp and Seq·Song page records to
our index tables (MUTE GROUP; QUANTIZE, SWING%), five words in the OS's
page code that would otherwise reset the Seq·Song record (`0xFF3468`,
`0xFF346E`, `0xFF3472`, `0xFF3476`, `0xFF26A0`: when the Edit pages switch
between the sequence and song tables the OS rewrites the record unless
"first" is `0x23DA`), and the sequencer hooks (one `move.l` each). While
ours is in, `0xFFC8D0` = 3, so any overlay request goes through ldr.

QUANTIZE uses the ROM's own labels (`0xC04778`: 1/4 .. 1/32T, OFF; our
choice table points there). Grids at 48 ticks per quarter: 48, 32, 24, 16,
12, 8, 6, 4; SWING% (51-75, 1/8 and 1/16 only) gives the offset
round(2 x grid x % / 100) - grid on odd grid lines.

**Hooks.** `0xFF6746` (`jsr 0x6AD6` at a LOOPED wrap, after the take is
finished): the finished take is quantized, unless a key is held (the OS
keeps pointers into the take for held notes, `0xFF8134`; they snap at the
next wrap). `0xFF6B7C` (`jsr 0x74F2`, the commit after KEEP): a LOOPED
take kept with NEW is quantized (buffer A). The KEEP prompt is untouched.

**The quantizer** (`src/swing/sq.s`, same result as
`tools/seqstream.py quantize_take`, `tests/test_sq.py`): a note moves less
than one grid step back, so it streams: events wait in a 32-entry buffer
sorted by new time until the scan is a grid past them; notes that wrap
(land on or after END) are found in a first pass and go out after the
events at the floor. The output goes after the take (free sequencer memory,
as the old code's scratch), then is copied back. Only event words are
written, and the event format keeps bits 3-0 at 0, so it's 13-bit safe.
Sequence memory starts at `0x580000` (sample RAM); recorded takes are the
same word for word with 13- and 16-bit sample RAM in MAME, and the note's
instrument isn't in bits 3-0 (all 0): a take is one track.

**HIT** (FULL LEVEL / ONE-SHOT). Storage had to be a high byte nothing
uses: no wavesample word is free besides `0x11E` (78 factory wavesamples:
the always-zero high bytes are parameters that default to 0, sample
address bytes, or `+0x24`, which the OS writes during sampling); the
instrument header's high bytes `+0x34-0x62` are free (zero in all factory
instruments, never touched in MAME), but the Instrument edit page
(`0xFFC0DE`) only comes up when the edit selection has no layer (no panel
button selects it; `0xFF2F6E`). So: one choice on the Layer page, layer
record `+0x2E`, the key-map slot of key 20 (the map is `+6 + 2 x key` for
keys 21-108; layer records are `0xE0` bytes; no code reads `+0x2E`).
Bit 0 FULL LEVEL, bit 1 ONE-SHOT. At the voice start (`0xFFB252`, `a6` =
the layer, `a3` = the wavesample on both paths) FULL LEVEL makes the
velocity 127 and the ONE-SHOT bit is copied into the wavesample's `+0x11F`
bit 3 (a low byte, but bit 3 exists in 13-bit RAM). At key-up the stock
test of the sustain pedal (`0xFFAE54`, `tst.b 20(a2)`) also says "hold"
for a voice whose wavesample has that bit and doesn't loop (MODE `+0xEE`
0 or 1): it plays to its end. Looping samples release as usual.

**Loop undo** (one level). RECORD alone while loop recording over a
track (`0xFF7ADC` in the transport handler, `clr.b 0xC430.w`; the press is
then finished with `0xFF7B1E` so recording goes on) takes out the newest
notes: this pass's, or if none were played yet in this pass, the last
pass's. Bit 3 of a note's last word marks the newest pass with notes
(playback ignores bits 3-0, `0xFF6882`; bits 2-0 don't exist in 13-bit
sample RAM, bit 3 does). Flags U_NEW (this pass has notes) and U_KILL (1 =
this pass's, 2 = the last pass's), both in the window. Hooks:
* append (`0xFF6E56`, `lea 8(a4),a0`, appends the staged event): a note
  played now gets bit 3 unless an undo is pending; the first one of a pass
  clears bit 3 on everything already written (no longer the newest). A
  note copied from the take being played loses bit 3 once this pass has
  new notes or an undo is pending.
* play (`0xFF638C` in the note handler, `move.b 3(a6),d1`): with U_KILL =
  2, a note with bit 3 in the take being played is skipped (no voice, no
  copy; its gap still counts: `0xFF637A`).
* the wrap and commit hooks re-encode the take with sq's kill flag (`d0`):
  notes with bit 3 are dropped. At the commit the kept take is untagged.
A wrap with a key held can't re-encode (as for quantize): U_KILL becomes
2 and the undone notes are skipped as they play. MAME:
`mame/test_undo_hw.py`. (Found while testing it: sq uses `a4`, which the
wrap and commit hooks point at the flags; qbuf saves it.)

**CHOP** (`src/swing/chop.s`). Edit, 8 Wave, the last entry
"CHOP=PRESS ENTER": ENTER asks "CHOP INTO 16 SLICES?", ▲/▼ pick 2, 3, 4,
6, 8, 12, 16, 24 or 32, ENTER chops, CANCEL doesn't. What it builds on:
* **Parameter storage is per page.** A descriptor's "where" is added to a
  base the page decides (`0xFF2E10`): absolute (OS RAM) only for page
  records below `0xFFC0DE` (MIDI, system, sequencer, track); the
  instrument, layer and wavesample pages add it to that record. So a value
  of ours can't live on the Wave page. The entry is a parameter type no
  page uses (`0x17`; also free: `0x01`, `0x06`, `0x10`, `0x13`) whose
  display (`0xFFD066 + 2 x type`) and edit (`0xFFD098 + 2 x type`) words
  point at ours while ours is in: the label and "PRESS ENTER", arrows do
  nothing.
* **Edit mode's buttons.** `0xFF1A88` dispatches a button by its id's
  high nibble (table at `0xFF15F8`); ids `0x20-0x25` in Edit mode go
  through `0xFFD05A + 2 x (id & 15)`: ▲ `0x20`, ▼ `0x21`, ◄ `0x22`,
  CANCEL `0x23`, ► `0x24`, ENTER `0x25` (`0xFF2110`, which only redraws).
  Our ENTER (`0xFFD064`) checks for the Wave page (`0xFFC08A` =
  `0xFFC0F2`) on our entry (record +4), else goes on to `0xFF2110`. The
  prompt is a copy of the OS's YES/NO prompt loop (`0xFFA6DA`: `trap #5`,
  `0xFF1790` gets a message, `a2` = `0x1A88` for a button, `d2` its id).
  `0xFF1790` and the edit-selection check `0xFF2F1C` both use `a6`.
* **The edit selection**: instrument `0xFF169C`; that instrument's record
  (`0xFFA4BA`, d1 = instrument) +66 layer, +68 wavesample (0 = ALL).
  `0xFF2F1C` sets carry and `a2` = "NO EDIT WS SELECTED" (`0x175C`) when
  there's none. `0xFFA4B0` gives an instrument's data (through its handle,
  `0xFFDCC4…`); ROM `0xC08D0E` / `0xC08D36` (`0xFF83A0` / `0xFF83A6`, a1 =
  data, d0 = number) a layer's / wavesample's offset.
* **COPY WAVESAMPLE** (`0xFF4C6E`, command record `0xFFC6A4`, no overlay)
  asks TO INST, TO LAYER, COPY = PARAMS ONLY / ALL DATA, then calls
  `0xFFA2D6`: source `0xFF1548/154A/154C` (instrument, layer,
  wavesample), destination `0xFF1562/1564` (instrument, layer),
  `0xFF15ED` = 0 for parameters only (same instrument). It adds a 288-byte
  record at the end of the instrument (`+0x22` = the wavesample whose data
  it plays) and returns its number in d0, or carry and an error code
  (`0xFF4A8C` turns it into a message). CHOP sets those variables, calls
  it once per slice and puts them back.
* **Wavesample fields** (all high bytes): `+0x06` the next wavesample in
  the layer, `+0x22` whose data it plays, `+0xAA` ROOT KEY, `+0xEE` MODE
  (0 FORWARD-NO LOOP … 4 LOOP AND RELEASE), `+0xF0/+0xF8/+0x100/+0x108`
  SMPL START, SAMPLE END, LOOPSTART, LOOPEND (`movep.l`: sample number
  x 512, a 9-bit fraction below; sample n is the word at record + 0x120 +
  2n of the owner), `+0x112/+0x114` its lowest and highest key.
* **Key maps are derived.** ROM `0xC08F22` (`0xFF83D0`, a1 = data, a0 =
  layer offset) clears the layer's map (+0x30-0xDF, keys 21-108) and
  fills each wavesample's range in chain order (layer +6, then each
  record's +6), so a later one wins. The OS calls it after copying,
  creating and deleting wavesamples and after range edits. (It doesn't
  touch +0x2E, HIT.) CHOP gives each copy a one-key range and calls it.
* **Cuts**: length / n (32/16 division in two steps), the remainder spread
  over the slices; each inner cut goes to the nearest sign change between
  two samples (the earlier of two as near), at most a quarter slice and 127
  samples away; slices end where the next starts. The cut points are
  worked out before the first copy (copies go at the end of the instrument,
  so the source doesn't move, but other instruments may).
MAME: `mame/test_chop_hw.py` (16 checks).

**Tasks.** The wrap hook runs in the sequencer task (user stack around
`0xFFCB56`, task 3, entry `0xFF583A`), the commit and ldr/ml in the UI task
(`0xFFCA84`). Measured in MAME with a 50 ms busy loop in the wrap hook and
panel buttons every 40 ms: the UI loop never ran inside it, so ours can't
be exchanged out from under a running hook.

### Room for our code: what's left, and shrinking the OS

What we have now, all measured on 13-bit sample RAM:
* **Window region** (`0xFFE400-0xFFFFDF`, swapped in outside Command mode):
  7136 bytes, 3870 used (swing, loop undo, CHOP, patch/unpatch, page
  tables).
  Real-time hooks that only need to work in play/Edit mode (the sequencer
  ones) can live here. This is where the next features go.
* **Resident** (always there, for hooks that must also work in Command
  mode: mute, HIT, the swap itself): boot-only code only. Used: `0xFF1720`
  (mute 68 + HIT 8), `0xFF2990` (ml 38), `0xFF4E20` (ldr 32), `0xFF4EA8`
  (HIT 26), `0xFF86E8` (swapx 30), `0xFF874C` (HIT 26). Left: `0xFF5214-
  0xFF5223` (16) and a few 2-4 byte ends. Not usable: `0xFF17D4` and
  `0xFF242A` (called at runtime, e.g. by the disk code), the zero runs in
  `0xFF818C-0xFF844A` (kernel jump and vector tables with unused slots:
  the ROM kernel indexes them).
* **Sample RAM**: data only, one byte per word or values in bits 15-3.

**Shrinking the stock OS** (asked on 2026-10-04) was looked at, not done:
* Finding dead code safely is hard: much of the OS is reached through
  tables (command records with handler words, page descriptors, task and
  trap tables, message handlers), so a static call graph misses entry
  points and a dynamic one (MAME coverage) can't see rarely used paths.
  Removing a routine that turns out to be reachable crashes the EPS in
  exactly the rare situation nobody tested.
* Rewriting OS routines for size: hand-written 68000 code, already tight;
  the gain per routine is small and every byte moved breaks absolute
  references elsewhere.
* The safe version of the idea is what Ensoniq did themselves: move
  self-contained, rarely used resident code that is only reached through a
  command record into an overlay (the record has an overlay field; the
  dispatcher loads it). The overlay-3 slot is ours now, but a fifth slot
  can be added to the OS file. Only worth doing if the resident budget
  (not the window) runs out: the window covers everything planned so far.

### Unused and unfinished bits

Signs of features that were started or planned but aren't in OS 2.49:

* **Overlay 3 is empty** in every original-EPS OS (2.2, 2.45, 2.49). The
  loader and the command dispatcher already handle it. The EPS-16+ OS fills
  it from 1.19 on. We can use it for new non-real-time commands.
* **Command dispatcher** (`0xFF5370`): walks the 14-byte records, matches
  the flags' low byte (command number), and loads overlay
  `(flags_high & 0x7F) >> 4` before calling the handler (`0xFFC3C4` = wanted,
  `0xFFC8D0` = current). Flags `0xB…` would select overlay 3.
* **Unreferenced ROM messages** (26 of 683; no OS or ROM word points at them,
  though fixed-width label tables like `'PEDDWN '`/`'PRESSR '` are read by
  index and only look unused):
  * An input-calibration wizard: a meter `-XX -XX 00 +XX +XX GO?`, "TURN
    LEFT/RIGHT CONTINUE?" (turn a trim pot), "CANNOT CALIBRATE", "INCORRECT
    AUDIO INPUT" and a success message **"YOU'RE A COOL DUDE NOW"** that
    nothing displays. The OS only has the manual service commands MSB
    ADJUSTMENT and DC OFFSET ADJUSTMENT. The guided version looks cut or
    simplified.
  * **"SCSI STATUS"**: a command title right after FORMAT SCSI DRIVE, with no
    command record.
  * **"BAR RANGE ERROR"**, **"SOURCE BAR ERROR"**: sequencer errors for bar-range
    edits; no such check uses them.
  * "COUNTING", "NO WAVESMPLS IN LAYER", "SLAVE", "KEYSCALE", "FREQUENCY"
    and a few labels.
* **Envelope modes** are NORMAL / CYCLE / REPEAT: no one-shot.
* A parameter scan against the ROM descriptors was inconclusive: most
  instrument/layer/wavesample parameters store structure offsets, not RAM
  addresses, so it needs the parameter system decoded first.

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
* `tests/test_codearea.py`: the boot-time install (all memory configs, both
  boot ROMs) on the real init stack, with the kernel's data above the staging
  bytes, and the mute hook through the installed jsr.
* `tests/test_swing.py`: the reference swing math in `tools/swing.py`.
* `tests/test_swing_asm.py`: `src/swing.s` against `tools/seqstream.py`
  (MAME takes, random takes, log mode, held notes, undo's kill).
* `tests/test_undo.py`: the loop undo hooks (tags, RECORD, the playback
  skip, STOP) with the OS state set up as MAME shows it.

MAME (`mame/`, docs/MAME.md) runs the whole machine: the boot ROM loads the
OS from a disk image, and the OS boots to its main loop. That caught the
staging/stack bug the routine tests missed. With panel and key input
scripted, it also loads instruments from disk and plays them, and
`mame/test_mutegroups.py` checks mute groups on the voice lists.

### Panel protocol and disk DMA (found while getting MAME to work)

* **Panel → CPU** (DUART B, handler `0xFF97A6`, state in `0xFF164E`): a
  byte below `0xC0` with bit 7 set starts a press, without it a release;
  bits 0–5 are the code. A second byte of 0 means a panel button (code →
  button through ROM table `0xC02032`), non-zero means a keyboard key with
  that velocity, note = code + 36. `0xFF` = ack for the last byte sent,
  `0xFC xx` = data byte, `0xF7` = end. Button codes: docs/MAME.md.
* **Disk after boot**: the OS uses the ROM's block routines through hooks
  at `0xFF8178–0xFF818B`. They program DMAC channel 0 (`0x240000`,
  HD63450/MC68450 layout) for FDC transfers, with FDC DRQ on REQ0 and FDC
  INTRQ on PCL0; the DMAC interrupts at level 2, vectors 65/66 → `0xFF8188`.
  Vectors 67/68 (`0xC0EAD2`) are presumably channel 1, the sampling ADC.

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
