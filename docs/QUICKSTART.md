# Quick start: the custom EPS OS (`EPS249_NEXT`)

Everything the stock EPS OS 2.49 does, plus mute groups, MPC-style swing
for loop recording, loop undo, HIT (full level / one-shot), TUNE, CHOP,
CRUSH and SP sampling mode. For the original EPS (tested with boot ROM 2.40 and the 2x
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
| TUNE | Edit, **4 Pitch**, ◄ once | the instrument (per wavesample) |
| CHOP | Edit, **8 Wave**, ◄ once | (an action) |
| CRUSH | Edit, **8 Wave**, ◄ twice | (an action: makes a new wavesample) |
| SWING% / QUANTIZE | Edit, **Seq·Song**, ◄ once / twice | not saved: 1/16 and 50 at power-on |
| Loop undo | **RECORD** while loop recording | |
| SP sampling mode, FILTER CUTOFF to 50 kHz | sampling: SAMPLE RATE = **26.04 KHZ**, FILTER CUTOFF | (sampling settings) |

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

* **FULL LEVEL**: every hit at full velocity, however hard you play. You
  hear it on soft hits (a new sample's soft hits are about half level).
* **ONE-SHOT**: letting go of the key doesn't stop the sound, so a
  sample without a loop plays to its end. Looping samples release as
  usual. **A new sample on the EPS loops** (MODE = LOOP FORWARD on the
  8 Wave page): set MODE = FORWARD-NO LOOP for ONE-SHOT to work on it.
  CHOP's slices are already NO LOOP.
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
ordinary notes, so the sequence saves and loads normally. A hit played
just before the loop point and still held when the loop comes round snaps
to the start one pass later.

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

* Slices on consecutive keys, starting at the wavesample's **ROOT KEY**
  (the key it plays at its original pitch, e.g. middle C for a fresh
  sample), each at its original pitch, no loop. (If the root is outside
  the wavesample's keys: from its lowest key, C2 at the lowest.)
* Tapping a key briefly cuts a slice short (key-up starts its release).
  To let every slice play through, like pads, set **HIT = ONE-SHOT** on
  the Layer page.
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

## CRUSH: the SP-1200's pitching and 12 bits

The SP-1200 plays a sample at another pitch by skipping or repeating
samples at a fixed rate, with no smoothing, and keeps 12 bits. Pitched
down, that's the grainy, ringing low end; pitched up, it aliases. The EPS
pitches smoothly, so CRUSH bakes the SP way into a new wavesample.

1. **Edit**, cursor on **WS=**, press a key the sample plays.
2. **8 Wave**, ◄ twice (once is CHOP): `CRUSH=PRESS ENTER`.
3. **ENTER**: `CRUSH PITCH=+0?`. ▲ / ▼ pick -12 to +12 semitones,
   **ENTER**.
4. `CRUSH BITS=12?`. ▲ / ▼ pick **12** (the SP-1200's and the MPC60's),
   **8** (dustier) or **OFF** (the EPS's own), **ENTER**.
5. `CRUSHING`, then `CRUSHED: WS 5` (the new wavesample's number).
   **CANCEL** at either question backs out.

What you get:

* A **new wavesample** on the same keys, playing the sound at the new
  pitch from its ROOT KEY: `PITCH=-5` sounds 5 semitones lower, with the
  SP's grain. Pitch down is the classic use: sample the record fast (45
  rpm), then CRUSH it back down.
* Everything else is copied: envelopes, filter, ROOT KEY, keys, MODE,
  mute group; the loop points move with the pitch.
* It becomes the edit wavesample, so **CHOP** right after chops the
  crushed sound.
* The original stays in memory, underneath it (its keys now play the
  crushed one). To free its memory: Edit, at **WS=** pick the original's
  number with ▲ / ▼ (note it before crushing), then DELETE WAVESAMPLE.
* It needs memory for its own copy: a sample pitched down 12 is twice as
  long. No room: `MEMORY FULL` and nothing changes.
* Saved with the instrument, and it loads on a stock EPS (it's an
  ordinary wavesample).

Things to know:

* Stop the sequencer first (`STOP SEQUENCER FIRST`), and pick one
  wavesample (with **WS=ALL**: `NO EDIT WS SELECTED`).
* `PITCH=+0, BITS=12` just makes a 12-bit copy. `BITS=OFF` with a pitch
  gives the SP pitching without the 12-bit grit.
* Crushing a crushed sample adds up: crush once, from the original.

## Sampling: FILTER CUTOFF up to 50 kHz, and SP sampling mode

The EPS's input filter keeps high sounds from folding back down as
aliasing when you sample at a low rate. Stock, it stops at 20.0 kHz; the
hardware goes further, so FILTER CUTOFF now has three more steps:
**25.0, 33.3 and 50.0** (50.0 is as open as this filter gets). The
display shows the values without "KHZ", e.g. `FILTER CUTOFF=5!0` for 50.0
(the EPS draws "5." as one character).

**SP sampling mode:** set **SAMPLE RATE = 26.04 KHZ**, the E-mu
SP-1200's own rate, and FILTER CUTOFF jumps to **20.0**. (Stock, that
rate picks 9.09 kHz, which keeps it clean.) Everything between 13 kHz
(the most 26.04 kHz can hold) and the cutoff folds back as grit on hats
and cymbals.

* **Real SP amount:** the SP's own input filter is steep and closes at
  about 13 kHz (measured on the SP-12, its predecessor), so only a little
  aliases. For that, set FILTER CUTOFF to **14.3** after picking the
  rate.
* **Dirtier than an SP:** 20.0 (the default here), 25.0, 33.3 or 50.0.
* Every other rate works as on the stock EPS (FILTER CUTOFF is reset
  when you change the rate, so set it after).
* Then trim, **CRUSH** (12-bit and SP-style pitching, below) and CHOP.
  The filter only decides how much grit gets in while sampling; most of
  an SP-1200's sound is how it plays samples back, which is what CRUSH
  does.

(To make room, the factory service command MSB ADJUSTMENT now does
nothing, like DC OFFSET ADJUSTMENT already did. It's a DAC trim for
service technicians.)

## TUNE: pitch a sample (or everything) up or down

Edit, **4 Pitch**, ◄ once (from ROOT KEY): `TUNE=+0`.

* **▲** = a semitone **up**, **▼** = a semitone **down**, from -16 to +15.
  `TUNE=-5` plays the sample 5 semitones lower than it was.
* It's **per wavesample**, like ROOT KEY. Pick what it changes on the
  Edit page's **WS=** field:
  * **One sample:** cursor on **WS=**, press a key the sample plays.
    Only that sample moves, and its TUNE shows its own number.
  * **Everything:** **WS=ALL**. Every sample of the layer (a kit or a
    break: usually the whole instrument) moves a semitone at each press,
    each keeping its key and its own number.
* **A new sample starts at TUNE=+0**, whatever the others are tuned to.
  Sample a loop, TUNE it -5, sample the next one: it shows +0, and -5 on
  it takes it down 5 too, without touching the first.
* Saved with the instrument (the stock OS loads it fine). CHOP's slices
  and CRUSH's copy keep the tuning and its number.
* The old "sample the record at 45, play it at 33" trick: TUNE -5 (45 to
  33 1/3 rpm is 5.2 semitones; FINE, next to ROOT KEY, does the rest).

TUNE works by moving the sample's **ROOT KEY** (the key that plays it at
its original pitch) the other way: TUNE -1 = ROOT KEY one key higher. Its
number counts only its own steps, so if you change ROOT KEY by hand TUNE
doesn't follow. **FINE** tunes between semitones.

(Instruments tuned with the earlier disk, where TUNE was on the 9 Layer
page, keep their pitch; their TUNE just starts from +0 here.)

## Good to know

* **Command mode and sampling are the stock OS** (apart from the
  sampling filter: SP mode and the steps above 20 kHz). Our code steps
  aside while you're in Command mode or sampling, and comes back when you
  leave. Sequence commands, disk commands and sampling work as always.
* **Not saved:** QUANTIZE and SWING% (1/16 and 50 at power-on). Mute
  groups, HIT, TUNE, chopped slices, crushed samples and tuning are
  saved with the instrument.
* **If you see an ERROR:** write down the number and what you just did,
  then power off and boot again.

Details and test notes: docs/HARDWARE_TESTS.md in the project. How it
works: docs/ANALYSIS.md.
