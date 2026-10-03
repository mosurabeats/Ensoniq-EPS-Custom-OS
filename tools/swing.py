#!/usr/bin/env python3
"""Reference swing/quantize math (the 68000 code is tested against this).

All times are EPS sequencer ticks: 48 per quarter note (PPQN). Measured
from sequences recorded in MAME: the deltas of a 4/4 bar add up to 192.
The QUANTIZE grid table (ROM 0xC03F32: 48, 32, 24, 16, 12, 8, 6, 4, 3, 2)
is in the same ticks. Grid sizes: 1/8 = 24, 1/16 = 12 (swing applies to these two
only, as on the MPC and SP-1200).

Swing moves every second grid step (the even 8ths/16ths: 2, 4, 6 ... of the
beat counted from 1) later. "Swing %" is the share of the pair that the first
step gets: 50% = straight, 66.7% = triplet feel.

Styles
  mpc     MPC60 / MPC3000 (Roger Linn): 50-75 in 1% steps. The offset is
          round(pair * pct / 100) - grid. The MPCs run at 96 PPQN; the EPS
          stores 48, so a 16th pair is 24 ticks and 1% is 0.24 tick: the
          percentages land on whole ticks (54% -> +1, 58% -> +2, 66% -> +4,
          75% -> +6). ASSUMPTION: round half up.
  sp1200  E-mu SP-1200: six settings shown as 50, 54, 58, 63, 67, 71%. These
          are exactly (12+k)/24 of the pair (k = 0..5): one-tick steps at
          48 PPQN, the SP-1200's own resolution, so the EPS gets them exactly.

    >>> offset("mpc", 54, 12), offset("mpc", 66, 12), offset("sp1200", 3, 12)
    (1, 4, 3)
"""
from fractions import Fraction

PPQN = 48
GRIDS = {"1/4": 48, "1/4T": 32, "1/8": 24, "1/8T": 16, "1/16": 12, "1/16T": 8,
         "1/32": 6, "1/32T": 4}
SWING_GRIDS = (24, 12)

SP1200_LABELS = (50, 54, 58, 63, 67, 71)


def swing_fraction(style, amount):
    """Exact share of the pair given to the first step."""
    if style == "mpc":
        if not 50 <= amount <= 75:
            raise ValueError("MPC swing is 50-75%")
        return Fraction(amount, 100)
    if style == "sp1200":
        if not 0 <= amount <= 5:
            raise ValueError("SP-1200 swing is setting 0-5 (50, 54, 58, 63, 67, 71%)")
        return Fraction(12 + amount, 24)
    raise ValueError(f"unknown style {style!r}")


def offset(style, amount, grid):
    """Ticks added to every second grid step (0 for grids without swing)."""
    if grid not in SWING_GRIDS:
        return 0
    pos = 2 * grid * swing_fraction(style, amount)      # second step's position
    return int(pos + Fraction(1, 2)) - grid             # round half up


def quantize(t, grid, style="mpc", amount=50, strength=100):
    """Quantized (and swung) time for an event at tick t.

    Snaps to the nearest line of the *swung* grid (ties go to the later
    line), so a note played late on a swung 16th stays on that 16th instead
    of jumping to the next beat. The grid is anchored at tick 0 (the start of
    the sequence; EPS bars are whole beats, so also every beat). strength <
    100 moves the event only part of the way, like the MPC's timing-correct
    strength.
    """
    off = offset(style, amount, grid)

    def line(step):
        return step * grid + (off if step % 2 else 0)

    first = t // grid - 1
    target = min((line(s) for s in range(first, first + 4)),
                 key=lambda p: (abs(p - t), -p))
    return t + (target - t) * strength // 100


def table():
    rows = []
    for name, g in (("1/16", 12), ("1/8", 24)):
        for pct in range(50, 76):
            rows.append(("mpc", name, f"{pct}%", offset("mpc", pct, g)))
        for k, lab in enumerate(SP1200_LABELS):
            rows.append(("sp1200", name, f"{lab}%", offset("sp1200", k, g)))
    return rows


if __name__ == "__main__":
    for style, grid, amount, off in table():
        print(f"{style:7s} {grid:5s} {amount:>4s}  +{off} ticks")
