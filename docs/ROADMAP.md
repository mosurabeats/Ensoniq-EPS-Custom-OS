# Custom OS roadmap

Target: original Ensoniq EPS, OS 2.49 (68000, loaded from floppy).

The approach is the same as community MPC firmware projects: keep the stock OS
and **patch** it rather than rewrite it. We redirect a few `jsr` calls into new
code, and keep every change as a verified, version-locked patch
(`tools/epstool.py patch`). Because the OS boots from disk, each test is just
"write a floppy (or Gotek image) and power on".

## Feature ideas

Feasibility: ★★★ = mostly a hook into existing code; ★ = needs new UI and
file-format work.

### Sampling and chopping

| Feature | What it does | Feasibility |
|---|---|---|
| **Auto-chop (equal slices)** | Split one wavesample into 2/4/8/16/32 slices and map them to consecutive keys from a root key, each at original pitch. Slices are new wavesamples that point into the **same** sample memory (start/end pointers only), so no RAM is copied. | ★★ |
| **Auto-chop (transient)** | Same, but slice points come from an energy/onset detector with a sensitivity setting. A 68000 at 8 MHz can scan a full EPS memory in a few seconds. | ★★ |
| **Zero-crossing snap** | Start/end/loop edits jump to the nearest zero crossing, so no clicks. | ★★★ |
| **Slice nudge + audition** | Patch Select buttons move the current slice boundary by a coarse or fine step and retrigger it. | ★★ |
| **Auto-trim silence** | Truncate leading and trailing audio below a threshold in one step. | ★★★ |
| **Chop to sequence** | After chopping, write a sequencer track that plays the slices in order, so the loop plays back intact at any tempo. | ★ |

### Playback

| Feature | What it does | Feasibility |
|---|---|---|
| **Mute / choke groups** | Starting a voice in group N stops every other voice in group N, like open and closed hi-hats or MPC-style mute groups. v1: a per-instrument "mono-choke" (each key chokes the others, ideal for chopped breaks). v2: group number per layer or wavesample. | ★★★ (v1) / ★★ (v2) |
| **Choke on release (one-shot off)** | Option to ignore note-off so slices play out fully. | ★★★ |
| **Velocity → sample start** | Harder hits start later in the sample (or earlier). | ★★ |
| **Round-robin layers** | Cycle through layers on repeated notes instead of picking by velocity. | ★★ |

### Sequencer and MIDI

| Feature | What it does | Feasibility |
|---|---|---|
| **Swing quantize** | MPC-style 50–75% swing on 1/8 and 1/16. | ★★ |
| **Note repeat** | Hold a Patch Select button, and held keys retrigger at the quantize rate. Aftertouch sets velocity. | ★★ |
| **MIDI clock / SPP fixes** | Tighter slave sync. Echo clock out when slaved. | ★★ |

### Quality of life

| Feature | What it does | Feasibility |
|---|---|---|
| Free-memory readout on the main page | | ★★ |
| Faster disk loads (skip verify, bigger DMA bursts) | | ★ (needs care) |
| Custom boot banner / version tag | First "hello world" patch | ★★★ |

## How mute groups would work

1. Find the voice-start routine, which writes the OTIS (ES5505) voice
   registers at `0x200000`. It is in file pages 0x9000 / 0x10000 (see
   ANALYSIS.md).
2. Hook its call site. Before a voice starts, check the group of the new
   voice's instrument. For every active voice with the same group, write a
   fast-release or stop to OTIS.
3. Store the group number:
   * v1: one byte per instrument in OS RAM, set from a new parameter. It is
     not saved to disk.
   * v2: an unused byte in the instrument or layer parameter block, so the
     setting saves with the instrument and old OSes ignore it. This needs the
     instrument file format mapped first.

## How auto-chop would work

1. Find the wavesample parameter block: start, end, loop start/end, root key,
   and key range.
2. Find the existing **Copy Wavesample** command and drive it to clone the
   source wavesample N times, sharing sample data.
3. For slice *i*: start = s + i·len/N (or the i-th detected onset), end = next
   start − 1, loop off, key range = root+i..root+i, root key = root+i.
4. Expose it as a new command, for example from the Edit → Wavesample command
   page: `CHOP INTO 16? (YES)`.

## Milestones

| # | Milestone | Status |
|---|---|---|
| M0 | Unpack installer, EDE ⇄ IMG, extract and replace the OS, patch tool, disassembly | **done** |
| M1 | Memory map: how the boot ROM loads the 85 KB OS, the free space, and the display text encoding | in progress |
| M2 | "Hello world": change the boot banner or version and confirm on hardware or Gotek | needs a tester with an EPS |
| M3 | Mute groups v1 (per-instrument choke) | |
| M4 | Equal-slice auto-chop | |
| M5 | Transient chop, zero-crossing snap, swing, note repeat | |

## Testing

There is no working emulator yet. MAME has an EPS driver but it is not
functional, and it needs the boot ROM dumps. So every patch needs a hardware
test. The fastest loop is a Gotek with FlashFloppy:
`tools/epstool.py replace stock.ede 0 patched_os.bin test.img`, copy it to the
USB stick, and power-cycle. Getting MAME's EPS driver to boot would make
development much faster and is worth doing in parallel.
