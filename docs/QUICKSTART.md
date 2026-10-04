# Quick start: the custom EPS OS (`EPS249_NEXT`)

Everything the stock EPS OS 2.49 does, plus mute groups, MPC-style swing
for loop recording, loop undo, HIT (full level / one-shot), CHOP and SP
sampling mode. For the original EPS (tested with boot ROM 2.40 and the 2x
expander), from a Gotek or a floppy.

## Boot

1. Copy `EPS249_NEXT.hfe` to the Gotek's USB stick (works with HxC and
   FlashFloppy firmware).
2. Select it and power on the EPS. It boots like the stock disk, a second
   or two slower.
3. Load your sounds as usual. The disk holds just the OS, so put your
   sounds on another disk.

If anything goes wrong, power off and boot your stock OS disk: nothing is
written to the instrument itself.

## Finding the new parameters

All new settings live on normal Edit pages, after the stock ones. On a
page, **◄** from the first parameter wraps round to the new ones at the
end. **▲ / ▼** or the slider change a value.

| Feature | Where | Saved with |
|---|---|---|
| MUTE GROUP | Edit, **6 Amp**, ◄ once | the instrument (per wavesample) |
| HIT | Edit, **9 Layer**, ◄ once | the instrument (per layer) |
| CHOP | Edit, **8 Wave**, ◄ once | (an action) |
| SWING% / QUANTIZE | Edit, **Seq·Song**, ◄ once / twice | not saved: 1/16 and 50 at power-on |
| Loop undo | **RECORD** while loop recording | |
| SP sampling mode | sampling: SAMPLE RATE = **26.04 KHZ** | (a sampling setting) |

To pick what you're editing (instrument, layer, wavesample): press
**Edit**. With the cursor on **WS=**, press a key to select the wavesample
it plays, or choose **WS=ALL** for all of them.

## Mute groups (choke)

Sounds in the same group cut each other, like an open and a closed hi-hat.

* Edit, **6 Amp**, ◄: `MUTE GROUP=0` (0 = none, 1-15 = a group).
* Set it per wavesample, or with **WS=ALL** for the whole instrument (then
  every key cuts the one before: one note at a time).
* Groups work across instruments: a group-1 kick in one instrument cuts a
  group-1 snare in another.
* A note retriggering itself also cuts its own tail. Letting go of a key
  doesn't cut anything.
* Saved with the instrument. The stock OS loads it fine and ignores it.

## HIT: full level and one-shot

Edit, **9 Layer**, ◄: `HIT=NORMAL`. ▲ steps through:

* **FULL LEVEL**: every hit at full velocity, however hard you play.
* **ONE-SHOT**: letting go of the key doesn't stop the sound, so a
  sample without a loop plays to its end. Looping samples release as
  usual.
* **FULL+1SHOT**: both.

It's per layer. A drum kit or a chopped break usually has one layer, so
that's the whole instrument. Saved with the instrument.

## Loop recording with QUANTIZE and SWING% (MPC timing correct)

1. Edit, **Seq·Song**, ◄ once: `SWING%=50`, ◄ again:
    `QUANTIZE=1/16`.
    * QUANTIZE: 1/4, 1/4T, 1/8, 1/8T, 1/16, 1/16T, 1/32, 1/32T, OFF
     (OFF = the stock EPS).
    * SWING%: 50 (straight) to 75. It swings only the 1/8 and 1/16 grids:
     every second 8th or 16th comes in later.
    * Try 54-58% for a light shuffle and 62-67% for a heavy one. The
     SP-1200's settings are 54, 58, 63, 67 and 71 here too.
2. Make a 1- or 2-bar sequence. On the same page set **RECORD MODE =
    LOOPED**.
3. Hold **RECORD**, press **PLAY**, and play. What you play snaps to the
   grid from the next time round the loop. A hit played just before the
   loop point moves to the start.
4. Press **STOP**: `KEEP = OLD NEW` as usual. **NEW** keeps the new take,
   quantized.

QUANTIZE and SWING% apply only while loop recording. The notes saved are
ordinary notes, so the sequence saves and loads normally. A key held over
the loop point snaps one pass later.

## Loop undo

While loop recording, press **RECORD** on its own (not RECORD + PLAY):

* If you've played notes in this pass, they're taken out.
* If you haven't played anything yet in this pass, the **previous pass's**
  notes are taken out, and they go silent right away.

It's one level, like the MPC60: a second press in the same pass does
nothing. Nothing shows on the display. Notes you play after an undo are
kept.

## CHOP: automatic chopping

Cuts a wavesample into slices, one per key, the way you'd do it by hand
with COPY WAVESAMPLE (parameters only), but in one step.

1. Sample or load the break into **its own instrument**. **TRUNCATE** it
   to exactly 1 or 2 bars, so the slices land on the beat (16 slices of a
   1-bar break = its 16ths).
2. **Edit**, cursor on **WS=**, press a key the break plays.
3. **8 Wave**, ◄: `CHOP=PRESS ENTER`.
4. **ENTER**: `CHOP INTO 16 SLICES?`. ▲ / ▼ pick 2, 3, 4, 6, 8, 12,
   16, 24 or 32.
5. **ENTER** chops (`16 SLICES CREATED`); **CANCEL** backs out.

What you get:

* Slices on consecutive keys, from the wavesample's lowest key up (from
  **C2** if that's lower), each at its original pitch, no loop.
* Each cut is moved to the nearest zero crossing (within about 4 ms), so
  the slices don't click and the hits stay whole.
* The slices share the original sample data, so 32 slices cost under
  10 KB. Each one is a normal wavesample: give it its own envelope, tune
  it, trim its start/end, put it in a mute group (a mono break: WS=ALL,
  MUTE GROUP 1), or remove it with DELETE WAVESAMPLE.
* Saved with the instrument, and it loads on a stock EPS too.

Things to know:

* The slices replace whatever those keys played before, so chop in an
  instrument of its own, not inside a kit.
* Stop the sequencer first (otherwise: `STOP SEQUENCER FIRST`).
* With **WS=ALL** selected: `NO EDIT WS SELECTED`. Pick one wavesample.
* Good with HIT = ONE-SHOT (slices play out) and a mute group (one slice
  at a time, like an MPC's mono pad).

## SP sampling mode (SP-1200 grit)

The SP-1200 samples at 26.04 kHz with little filtering on its input, so
high sounds fold back down as gritty aliasing. The EPS has that exact rate
in its list.

* Sample as usual and set **SAMPLE RATE = 26.04 KHZ**. FILTER CUTOFF
  jumps to **20.0 KHZ**, its widest setting: the input is then barely
  filtered, like the SP's. (Stock, that rate gets a 9.09 KHZ filter that
  keeps it clean.)
* Want it a bit smoother? Lower FILTER CUTOFF by hand after picking the
  rate. Every other rate works as on the stock EPS.
* Then trim, CHOP and pitch as usual. For the full SP feel: 12-bit
  crunch and SP-style pitching are planned (CRUSH).

## Tuning a sample down (or up)

The stock EPS already does this, on the **4 Pitch** page (Edit):

* **ROOT KEY** is the key that plays the sample at its original pitch.
  Raise it by one and the sample plays **one semitone lower** on every
  key; lower it to play higher. **FINE** tunes between semitones.
* With **WS=ALL** selected, ROOT KEY moves every wavesample of the layer
  by the same amount (a whole kit or a chopped break goes down together,
  each keeping its place).
* With one wavesample selected, it tunes just that one.
* The old "sample the record at 45, play at 33" trick: raise ROOT KEY by
  5 and FINE a little lower (45 to 33 1/3 is 5.2 semitones down).

## Good to know

* **Command mode and sampling are the stock OS** (apart from SP sampling
  mode's filter choice). Our code steps aside while you're in Command
  mode or sampling, and comes back when you leave. Sequence commands,
  disk commands and sampling work as always.
* **Not saved:** QUANTIZE and SWING% (1/16 and 50 at power-on). Mute
  groups, HIT, chopped slices and tuning are saved with the instrument.
* **If you see an ERROR:** write down the number and what you just did,
  then power off and boot again.

Details and test notes: docs/HARDWARE_TESTS.md in the project. How it
works: docs/ANALYSIS.md.
