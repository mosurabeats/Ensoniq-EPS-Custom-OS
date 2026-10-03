# Hardware tests

Each test is a disk image for a Gotek (or a real floppy). The EPS loads its
OS from disk at every power-up, so nothing is written to the instrument: if
a test disk misbehaves, power off and boot your stock OS disk.

## Getting a test disk onto the Gotek

* **`.hfe`** works on both FlashFloppy and HxC firmware with no settings. Use
  this one if you're not sure which firmware your Gotek runs.
* **`.img`** works on FlashFloppy only with `host = ensoniq` in `FF.CFG` on
  the USB stick (that gives the Ensoniq 800K layout, sectors numbered from 0).

Copy the file to the USB stick, select it on the Gotek, and power on the EPS
(it boots from the disk in the drive).

Build the disks yourself with:

```sh
tools/fetch.sh os                       # stock OS 2.49 (build/hfe/EPS249OS.hfe)
python3 tools/mkcodearea.py build/eps_os_249.bin -o build/test/codearea_mute.json \
    --groups "1=1,2:A0-B3=2,3=1" --disk build/hfe/EPS249OS.hfe build/test/EPS249_MUTETEST.hfe
```

## Test 1: code area + mute groups (`EPS249_MUTETEST`)

> **Use a disk built on or after the MAME fix.** The first test disks staged
> the code where the OS keeps its task stacks, and they crash at boot
> ("ERROR 137" or "ERROR 131 - REBOOT ?"). The current build boots to the
> main loop in MAME with the hook installed (`mame/run.sh`, docs/MAME.md).
>
> In MAME the mute groups already work with a real instrument: the TR 8O8
> kit loaded from the panel, notes played on the keyboard, voices cut as
> expected (`mame/test_mutegroups.py`). What MAME can't tell us is whether
> the real 68000 board runs code from sample RAM, and how it sounds.

**What it checks:** that the EPS can load our code from the disk at boot
into the top 4 KB of sample RAM (the code area), run it there, and that
mute groups work. Boot takes about a second longer than stock (the drive
spins up again to read our code).

The disk is stock OS 2.49 plus the code area, with per-key mute groups set
so that any sounds work (middle C = C4):

| Instrument | Keys | Group | Expected |
|---|---|---|---|
| 1 | all | 1 | every new note cuts the previous one (mono), even the same key again |
| 2 | below middle C | 2 | the lower half is mono; the upper half plays normally (chords ring) |
| 3 | all | 1 | shares group 1 with instrument 1: a note on 1 cuts 3 and vice versa |
| 4–8 | | none | normal |

**Steps**

1. Boot `EPS249_MUTETEST`. Does it reach the normal screen like the stock
   disk? (If it hangs, resets, or shows an error number, write the number
   down. Boot the stock disk to recover.)
2. Load a sound with a long release or loop (a pad, an open hi-hat) into
   instruments 1, 2 and 3, from your own disks.
3. Instrument 1: play a chord or two notes in a row. Only the last note
   should sound; the earlier ones stop within a few milliseconds (the same
   fast fade the EPS uses when it steals a voice).
4. Instrument 2: chords below middle C collapse to one note; chords from
   middle C up ring normally.
5. Hold a long note on instrument 1, then play instrument 3: the instrument
   1 note stops (and the other way round).
6. Instruments 4–8 should behave exactly like the stock OS.
7. Optional: sample something short and play it back. Sample memory is 4 KB
   smaller than stock, which should make no audible difference.

**What to report:** did it boot (step 1), and steps 3–6 (works / doesn't /
anything odd: clicks, hangs, wrong voices cut). Also tell us whether you have
a 2x or 4x memory expander, or none.

**If step 1 fails** something in the boot sequence differs from MAME (the
disk read at boot, or running code from sample RAM). Write down what the
display shows; boot your stock disk to recover.

**If it boots but nothing gets cut**, our code didn't load: the loader
couldn't read it from the disk (or the image failed its check) and the EPS
fell back to stock behaviour. Tell us; that's a disk-read problem, not a
mute-group one.

## Drum disk (`EPS249_DRUMS`)

A disk to play with: OS 2.49 with our additions, plus two kits from
Ensoniq's factory drum disk 9. Build it with `tools/mkdrums.sh` (after
`tools/fetch.sh sounds`).

**Load the kits:** LOAD, ENTER, instrument button 1 for TR 8O8 (file 1);
then LOAD, arrow to FILE 2, ENTER, instrument button 2 for LIVE KIT.
Together they need about 640 KB of sample memory, so without a memory
expander load one at a time. The mute groups are stored in the kits'
wavesamples (set on this disk with `tools/epstool.py groups`), so they work
in any instrument slot and stay with the kit when you save it.

### Setting things on the EPS (new parameters)

Our parameters sit on the EPS's own EDIT pages. Step through a page's
parameters with the two buttons that move to the previous/next parameter,
and change a value with the arrows or the data slider, as for any other
parameter.

* **MUTE GROUP** (0 = none, 1–15): EDIT, select the instrument, then
  wavesample page 6 (the one with WS VOLUME, PAN, the fades and VOLUME
  MOD). MUTE GROUP is right after VOLUME MOD (or one step back from WS
  VOLUME).
  * With **WS=ALL** on the edit selection screen, the value goes to every
    wavesample of the layer: the whole instrument in one group (a chopped
    loop where every slice cuts the others).
  * With **one wavesample** selected, only that one: kick and snare in
    group 1, open and closed hat in group 2, and so on.
  * Groups are shared by all instruments: group 2 on two instruments chokes
    across them. Use different numbers to keep them apart.
  * A sounding note is cut when a note in the same group starts (also the
    same key again, MPC style). Releasing a key cuts nothing.
* **QUANTIZE** (OFF, 1/4, 1/4T, 1/8, 1/8T, 1/16, 1/16T, 1/32, 1/32T) and
  **SWING%** (50–75; below 50 = straight, only 1/8 and 1/16 swing): EDIT,
  SEQ/SONG page, right after RECORD MODE. They apply to every instrument
  when you loop record (RECORD MODE = LOOPED): what you play lands on the
  grid from the next pass on, like an MPC's timing correct. This disk
  starts at 1/16 and 58%. Not saved with the sequence (yet): set them after
  power-on.
* **Undo while loop recording:** press RECORD on its own (not RECORD +
  PLAY). It takes out the notes you played so far in this pass, or if you
  haven't played any yet, the last pass's. A second press takes out the
  pass before. No message on the display.

**Please try and tell us:**
1. MUTE GROUP shows on wavesample page 6 and the arrows change it; WS=ALL
   vs one wavesample behaves as above.
2. **SAVE INSTRUMENT** after changing a group, power off, reload: is the
   group still there? (MAME can't save to disk yet, so this is untested.)
3. QUANTIZE/SWING% on the SEQ/SONG page, and a loop recording with them.
4. Anything on those pages that looks wrong: garbled text, the wrong
   parameter, a value that won't change, or an error/reboot.

**TR 8O8** (instrument 1). Keys found by playing every key in MAME and
analysing the samples:

| Keys | Sound | Mute group |
|---|---|---|
| C2, C#2 (the kick wavesample covers A0–C2) | kick (808 boom, sustains while held) | 2: a new kick cuts the old one's tail |
| D2, E2, F#2 | snare | |
| D#2 | rim | |
| F2 | noise loop (hat-like) | |
| G2–A2 | open hat | 1 |
| A#2 | closed hat | 1: chokes the open hat |
| B2–C4, C#4–D#5 | toms / congas (tuned across the keys) | |
| E5–A5 | clave | |
| A#5–D#6 | clap | |
| E6–A6 | maracas | |
| A#6–C7 | cowbell | |

**LIVE KIT** (instrument 2). General MIDI drum order, an octave up:

| Keys | Sound | Mute group |
|---|---|---|
| C2 | kick | |
| C#2 | side stick | |
| D2, E2 | snares | |
| D#2 | crash | |
| F2–A#2, B2–F3 | toms | |
| F#3 | closed hat | 3 |
| G#3 | pedal hat | 3 |
| A#3 | open hat | 3: closed and pedal hat choke it |
| C#4, D#4 | cymbals | |

(The sound names are educated guesses from length, brightness and noise;
tell us if a key is something else.)

The drum disk also has:
* **Auto-keep**: after recording over a track (any record mode), STOP keeps
  the new take without the "KEEP = OLD NEW" prompt. Outside loop recording
  there's no undo, so don't record over anything precious.
* QUANTIZE 1/16 at SWING% 58 and loop undo, as above.

**Try:** hold or let ring the open hat, then hit the closed hat: the open hat
stops. Roll the 808 kick on C2: each hit cuts the last one's boom. In MAME
both kits behave like this (`mame/keys/drums_disk.txt`).
