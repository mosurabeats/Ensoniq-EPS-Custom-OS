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
    --groups 1,1,2,0,0,0,0,0 --disk build/hfe/EPS249OS.hfe build/test/EPS249_MUTETEST.hfe
```

## Test 1: code area + mute groups (`EPS249_MUTETEST`)

**What it checks:** that the EPS can run our code from the top 1 KB of
sample RAM (the code area), and that mute groups work there.

The disk is stock OS 2.49 plus the code area, with mute groups:

| Instrument | Group | Expected |
|---|---|---|
| 1 | 1 | a note on 1 or 2 cuts whatever 1 and 2 are playing (open/closed hat) |
| 2 | 1 | |
| 3 | 2 | a new note on 3 cuts 3's previous notes (mono, like a chopped break) |
| 4–8 | none | normal |

**Steps**

1. Boot `EPS249_MUTETEST`. Does it reach the normal screen like the stock
   disk? (If it hangs, resets, or shows an error number, write the number
   down. Boot the stock disk to recover.)
2. Load a sound with a long release or loop (a pad, an open hi-hat) into
   instruments 1, 2 and 3, from your own disks.
3. Instrument 1: hold a long note, then play a note on instrument 2. The
   instrument 1 note should stop within a few milliseconds (the same fast
   fade the EPS uses when it steals a voice).
4. Instrument 3: play one note, then another key while the first still
   sounds. The first should stop.
5. Instruments 4–8 should behave exactly like the stock OS.
6. Optional: sample something short and play it back. Sample memory is 1 KB
   smaller than stock, which should make no audible difference.

**What to report:** did it boot (step 1), and steps 3–5 (works / doesn't /
anything odd: clicks, hangs, wrong voices cut). Also tell us whether you have
a 2x or 4x memory expander, or none.

**If step 1 fails** the 68000 can't run code from sample RAM, or something
in the boot sequence differs from the emulator. Then we know to keep code in
OS RAM instead, and nothing else on the disk matters.
