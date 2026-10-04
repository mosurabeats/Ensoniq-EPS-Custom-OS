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

## Mute groups test (`EPS249_MUTE`): passed on hardware

The earlier disks (`EPS249_CUSTOM`, `EPS249_DRUMS`, `EPS249_MUTETEST`, the
`EPSDIAG` disks) run our code from sample memory, which the EPS can't do
(its sample RAM is 13 bits wide, docs/ANALYSIS.md): they stop with
"ERROR 131 - REBOOT". `EPS249_MUTE` keeps everything in the OS's own
memory. It has **only mute groups** and the MUTE GROUP parameter to set
them; nothing else is changed. Build it with `tools/mkmutetest.sh`
(after `tools/fetch.sh os`). It's just the OS: add your own samples.

**Result (2026-10-04): every step below works on a real EPS** (OS 2.49
from this disk, boot ROM 2.40, 2x expander, Gotek with HxC firmware):
boot, MUTE GROUP on the 6 Amp page, WS=ALL and per-wavesample groups,
groups across instruments, and SAVE INSTRUMENT / reload, including loading
the saved instrument on the stock OS. It matches MAME (13-bit sample RAM,
boot ROM 2.40, `mame/test_resident.py`).

**1. Boot.** Select `EPS249_MUTE.hfe` on the Gotek and power on. It should
boot exactly like the stock disk (LOADING SYSTEM, then the usual screen).
If it shows an ERROR, write down the number and power off.

**2. Find MUTE GROUP.** Sample or load a few sounds into one instrument
(say kick, snare, closed hat, open hat on different keys). Press **Edit**,
select the instrument, then **6 Amp**. You're on WS VOLUME. Press **◄**
once: the display shows `MUTE GROUP=0`. (► from VOLUME MOD gets there
too.) ▲ / ▼ or the slider change it, 0 (none) to 15.

**3. Whole instrument in one group.** On the edit selection, pick
**WS=ALL**, set MUTE GROUP to 1. Play two different keys one after the
other: the second cuts the first. Play one key repeatedly: each hit cuts
the last one's tail. Let go of a key: nothing gets cut.

**4. Groups per sound.** Select one wavesample at a time: kick and snare
MUTE GROUP 1, closed and open hat 2, everything else 0. Hit the kick, then
the open hat: the kick keeps ringing (different groups). Let the open hat
ring and hit the closed hat: the open hat stops. Hit the snare: the kick
stops.

**5. Across instruments.** Put a melodic sample on another instrument,
WS=ALL, MUTE GROUP 3: every key cuts the one before (one note at a time),
and it doesn't touch the drums. Give it group 1 instead and it cuts, and
is cut by, the kick and snare.

**6. Save.** SAVE INSTRUMENT, power off, boot `EPS249_MUTE` again, load
the instrument: are the groups still set (step 2 shows them)? Then boot
the **stock** OS and load the same instrument: does it load and play
normally? (The stock OS ignores the group; it should not complain.)

**Tell us:** which steps worked, anything odd on the display, and any
ERROR number. A short phone video of step 4 helps.

### How fast a cut note fades (`EPS249_MUTE_12MS` / `_24MS` / `_48MS`)

Found on hardware: two notes of one group played very close together
could both be heard, one quieter. The first disk faded a cut note like the
OS's voice stealer, over about 100 ms (8 envelope ticks of 12 ms), so on a
flam the first note was still audible under the second. Now the fade is a
build setting (`tools/mkresident.py --choke`): three disks, otherwise the
same, with a cut that's done in about 12, 24 or 48 ms. `EPS249_MUTE` is
the 24 ms one.

**Try on each:** a kick and a snare (or open/closed hat) in one group. Play
flams and fast rolls, and cut a long, loud, low sound (an 808 kick held
down) with a short one. Listen for:
* the first note still heard under the second (too slow);
* a click or pop when a note is cut (too fast).

**Tell us** which one sounds right. That becomes the default.

## Swing test (`EPS249_SWING`): MPC-style loop recording

`EPS249_SWING` has mute groups (as `EPS249_MUTE`, 24 ms cut) plus
**QUANTIZE** and **SWING%** for loop recording, like an MPC's timing
correct: when you loop record, what you play snaps to the (swung) grid from
the next pass on. The KEEP = OLD NEW prompt stays as it is. Build it with
`tools/mkswingtest.sh`. Just the OS: add your own samples.

In MAME (13-bit sample RAM, boot ROM 2.40, `mame/test_swing_hw.py`): loop
takes snap to 1/16 at every wrap, SWING% 58 puts the off 16ths 2 ticks
late, KEEP = NEW keeps the quantized take, mute groups cut, and the
sequence commands and sampling still work.

How it fits: the new code is too big for the EPS's own memory, so it
borrows the part of the OS that holds the sequence commands (COPY TRACK,
QUANTIZE TRACK and so on) while you aren't using them, and keeps that part
in a corner of sample memory (5 KB) until you are. Nothing is loaded from
disk for that.

**1. Boot.** It takes a second or two longer than stock (it reads a bit
more of the OS from the disk). If it shows an ERROR, write down the number.

**2. Mute groups** work as before (6 Amp page, ◄ once: MUTE GROUP).

**3. The settings.** Edit, then **Seq·Song**. From the first parameter
press **◄** once: `SWING%=50`; again: `QUANTIZE=1/16`. QUANTIZE goes 1/4,
1/4T, 1/8, 1/8T, 1/16, 1/16T, 1/32, 1/32T, OFF (OFF = the stock EPS).
SWING% is 50 (straight) to 75, MPC style, and only swings the 1/8 and 1/16
grids. Both start at 1/16 and 50 at power-on (not saved yet).

**4. Loop record.** Make a 1- or 2-bar sequence, set RECORD MODE = LOOPED
(same page), and loop record (Record + Play) a beat: play some hits a
little early or late. From the next time around they play on the grid.
Try SWING% 54-62 with 1/16 hats: the off 16ths come in late, the MPC feel.
A downbeat played just before the loop point moves to the start.

**5. A key held over the loop point:** those notes snap one pass later
(they're still being recorded at that wrap). That's expected.

**6. Stop.** The KEEP = OLD NEW prompt comes up as usual. NEW keeps the
take, and the notes of the last, unfinished pass snap too. Play it back.

**7. Commands and sampling:** a sequence command (Command, Seq·Song, e.g.
COPY TRACK) and sampling should work as on the stock EPS; going back to
Edit, QUANTIZE and SWING% are there again.

**Tell us:** does it feel right, any hiccup at the loop point (the snapping
happens right there, a few milliseconds), anything odd on the display, any
ERROR number. Saving and loading the sequence afterwards should be normal:
the quantized notes are ordinary notes.

## Next disk (`EPS249_NEXT`): HIT, loop undo, CHOP, SP sampling, more room

Everything on `EPS249_SWING`, plus:

* **HIT** on the Layer page: Edit, **9 Layer**, ◄ once from the first
  parameter: `HIT=NORMAL`. ▲ steps through FULL LEVEL (every hit at full
  velocity, however hard you play), ONE-SHOT (letting go of the key doesn't
  start the release, so a sample without a loop plays to its end; looping
  samples release as usual), and FULL+1SHOT (both). It's per layer: a kit
  or a chopped break sampled into one instrument has one layer, so it's the
  whole instrument. Saved with the instrument.
* **Undo while loop recording** (one level, like the MPC60): press
  RECORD on its own (not RECORD + PLAY) while loop recording over a track.
  It takes out the notes you played so far in this pass; if you haven't
  played anything new in this pass yet, it takes out the last pass's notes
  instead (they stop sounding right away). One press per pass: a second
  press in the same pass does nothing. No message on the display. Undone
  notes are gone for good at the next loop wrap or at STOP + KEEP = NEW.
* **CHOP** (automatic chopping): pick a wavesample in Edit (Edit, ► to
  the WS field, press a key it plays), then **8 Wave** and ◄ once from the
  first parameter: `CHOP=PRESS ENTER`. ENTER: `CHOP INTO 16 SLICES?`, ▲ / ▼
  pick 2, 3, 4, 6, 8, 12, 16, 24 or 32, ENTER chops (CANCEL doesn't):
  `16 SLICES CREATED`. The wavesample is cut into equal slices, each cut
  moved to the nearest zero crossing (at most about 4 ms away, so no
  clicks and the hits stay whole). Each slice is a "parameters only" copy
  (it plays the same sample data, so it costs almost no memory) on its own
  key, from the wavesample's lowest key up (from C2 if that's lower), at
  its original pitch, FORWARD-NO LOOP. Slices replace whatever those keys
  played before, so chop a break in its own instrument. A slice is an
  ordinary wavesample: edit its envelope, start/end, mute group; delete it
  with DELETE WAVESAMPLE; it's saved with the instrument and loads on a
  stock EPS too. The sequencer must be stopped. Trim the sample to the
  loop first (TRUNCATE), so 16 slices of a 1-bar break are its 16ths.
* **Sampling filter up to 50 kHz and SP sampling mode:** FILTER CUTOFF has
  three more steps after 20.0: 25.0, 33.3, 50.0 (shown without "KHZ":
  `2:0`, `3(3`, `5!0`). SAMPLE RATE = 26.04 KHZ (the SP-1200's rate) picks
  20.0 by itself instead of the stock 9.09; 14.3 is closest to a real
  SP-1200's input filter. MSB ADJUSTMENT (a service command) now does
  nothing: its code made room.
* Behind the scenes: the borrowed part of the OS is now the whole
  sequence-commands overlay except its first kilobyte (room for about 7 KB
  of our code, 3.9 KB used), and our code steps aside whenever you're in
  Command mode or sampling, so those always see the stock OS.

MAME (13-bit sample RAM, boot ROM 2.40, `mame/test_swing_hw.py`, 16
checks): everything on the swing list, plus HIT = FULL+1SHOT plays a soft
snare at velocity 127 and lets it ring past the key-up; NORMAL plays it as
hit and releases it. `mame/test_undo_hw.py` (8 checks): G2 played in pass
2 then RECORD: gone from pass 3 on, the earlier D2 stays; RECORD early in
pass 2 before playing anything: pass 1's D2 isn't heard in pass 2 and
isn't kept; notes played after an undo are kept; the kept take has no
undo marks left. `mame/test_chop_hw.py` (16 checks): the TR 8O8 kick chopped
into 16: 16 wavesamples on C2 up, end to end over the kick, cuts on the
nearest zero crossings, C#2 plays slice 2; NO EDIT WS SELECTED with WS=ALL;
CANCEL makes nothing.

**Try:** the swing test above, then HIT: set FULL+1SHOT on a drum kit's
layer and play soft and hard, short taps on long samples. Tell us whether
it feels right, and whether a sample with a loop still releases. Then
undo: loop record a beat, play a wrong hit and press RECORD in the same
pass (it shouldn't come round again); play a pass, then press RECORD at
the start of the next one before playing (that pass's notes should go
silent). Keep with NEW and play the sequence back.
Sampling filter: at SAMPLE RATE 26.04 KHZ (check that FILTER CUTOFF shows
20.0 right after), sample the same break or record with FILTER CUTOFF
14.3, 20.0, 25.0, 33.3 and 50.0. The higher ones should sound brighter and
grittier on hats and cymbals. Listen especially at 33.3 and 50.0: those
run the filter chip faster than the stock OS ever does, so tell us if
they sound wrong (silence, a whine, distortion, much more noise) or the
level meter behaves oddly. Check that other rates still pick their usual
filter, and that normal sampling (e.g. 31.25 KHZ) sounds as before.
Then CHOP: sample (or load) a drum break into its own instrument, trim it
to a bar or two, chop it into 16 and play the slices. Tell us whether the
cuts sound clean and land on the hits, and whether SAVE INSTRUMENT and
loading it back keep the slices.

## Test 1: code area + mute groups (`EPS249_MUTETEST`)

> **Doesn't run on hardware** (ERROR 131: code in sample RAM). Kept for
> the record; use `EPS249_MUTE` above.

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

## Boot disk (`EPS249_CUSTOM`) and drum disk (`EPS249_DRUMS`)

> **Don't run on hardware yet** (ERROR 131: their code runs from sample
> RAM). They work in MAME with `EPS_SAMPLERAM16=1`. The features move to
> OS RAM one at a time, starting with `EPS249_MUTE` above.

`EPS249_CUSTOM` is the one to use: OS 2.49 with our additions and nothing
else, so the rest of the disk (about 700 KB) is free for your own sounds.
Build it with `tools/mkosdisk.sh`. Everything below works the same on it;
set mute groups on your own samples on the 6 Amp page.

`EPS249_DRUMS` is the same OS plus two kits from Ensoniq's factory drum
disk 9, for testing. Build it with `tools/mkdrums.sh` (after
`tools/fetch.sh sounds`).

**Load the kits:** LOAD, ENTER, instrument button 1 for TR 8O8 (file 1);
then LOAD, arrow to FILE 2, ENTER, instrument button 2 for LIVE KIT.
Together they need about 640 KB of sample memory, so without a memory
expander load one at a time. The mute groups are stored in the kits'
wavesamples (set on this disk with `tools/epstool.py groups`), so they work
in any instrument slot and stay with the kit when you save it.

### Setting things on the EPS (new parameters)

Our parameters sit on the EPS's own Edit pages. Step through a page's
parameters with the ◄ / ► arrows, and change a value with ▲ / ▼ or the
Data Entry slider, as for any other parameter.

* **MUTE GROUP** (0 = none, 1–15): Edit, select the instrument, then
  **6 Amp** (the page with WS VOLUME, PAN, the fades and VOLUME MOD).
  MUTE GROUP is right after VOLUME MOD: press ◄ once from WS VOLUME.
  * With **WS=ALL** on the edit selection screen, the value goes to every
    wavesample of the layer: the whole instrument in one group (a chopped
    loop where every slice cuts the others).
  * With **one wavesample** selected, only that one: kick and snare in
    group 1, open and closed hat in group 2, and so on.
  * Groups are shared by all instruments: group 2 on two instruments chokes
    across them. Use different numbers to keep them apart.
  * A sounding note is cut when a note in the same group starts (also the
    same key again, MPC style). Releasing a key cuts nothing.
* **FULL LEVEL** (OFF/ON) and **ONE-SHOT** (OFF/ON), on the same 6 Amp
  page, before MUTE GROUP: from WS VOLUME, ◄ twice for ONE-SHOT, three
  times for FULL LEVEL. WS=ALL sets them for the whole instrument; they
  save with the instrument like the mute group.
  * FULL LEVEL: every hit plays at full velocity (127), however hard you
    play. (Layers switched by velocity still follow how hard you play.)
  * ONE-SHOT: letting go of the key doesn't start the release, so the
    sample plays to its end: no more setting a long release on every
    sample. Only for samples without a loop (MODE FORWARD-NO LOOP or
    BACKWARD-NO LOOP); looping samples release as usual so they can't
    hang. Hitting the same key again still restarts it.
* **QUANTIZE** (OFF, 1/4, 1/4T, 1/8, 1/8T, 1/16, 1/16T, 1/32, 1/32T) and
  **SWING%** (50–75; below 50 = straight, only 1/8 and 1/16 swing): Edit,
  **Seq·Song**, right after RECORD MODE (◄ once from the first page gets to
  SWING%, twice to QUANTIZE). They apply to every instrument
  when you loop record (RECORD MODE = LOOPED): what you play lands on the
  grid from the next pass on, like an MPC's timing correct. This disk
  starts at 1/16 and 58%. Not saved with the sequence (yet): set them after
  power-on.
* **Undo while loop recording:** press Record on its own (not Record +
  Play). It takes out the notes you played so far in this pass, or if you
  haven't played any yet, the last pass's. A second press takes out the
  pass before. No message on the display.

**Please try and tell us:**
1. MUTE GROUP, FULL LEVEL and ONE-SHOT show on the 6 Amp page and ▲ / ▼
   change them; WS=ALL vs one wavesample behaves as above. Soft hits with
   FULL LEVEL on are as loud as hard ones; ONE-SHOT samples play out after
   you let go.
2. **SAVE INSTRUMENT** after changing these, power off, reload: are they
   still set? (MAME can't save to disk yet, so this is untested.)
3. QUANTIZE/SWING% on the Seq·Song page, and a loop recording with them.
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
