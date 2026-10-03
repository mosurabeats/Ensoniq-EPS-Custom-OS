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

**What it checks:** that the EPS can run our code from the top 1 KB of
sample RAM (the code area), and that mute groups work there.

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
7. Optional: sample something short and play it back. Sample memory is 1 KB
   smaller than stock, which should make no audible difference.

**What to report:** did it boot (step 1), and steps 3–6 (works / doesn't /
anything odd: clicks, hangs, wrong voices cut). Also tell us whether you have
a 2x or 4x memory expander, or none.

**If step 1 fails** the 68000 can't run code from sample RAM, or something
in the boot sequence differs from the emulator. Then we know to keep code in
OS RAM instead, and nothing else on the disk matters.
