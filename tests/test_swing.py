"""Reference swing math (tools/swing.py)."""
import doctest
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import swing  # noqa: E402


class SwingMathTest(unittest.TestCase):
    def test_mpc_16ths(self):
        # second 16th of each 8th lands at pct% of the 48-tick pair
        self.assertEqual([swing.offset("mpc", p, 24) for p in (50, 54, 58, 62, 66, 71, 75)],
                         [0, 2, 4, 6, 8, 10, 12])

    def test_mpc_8ths(self):
        self.assertEqual([swing.offset("mpc", p, 48) for p in (50, 54, 58, 66, 75)],
                         [0, 4, 8, 15, 24])

    def test_sp1200_is_exact(self):
        self.assertEqual([swing.offset("sp1200", k, 24) for k in range(6)], [0, 2, 4, 6, 8, 10])
        self.assertEqual([swing.offset("sp1200", k, 48) for k in range(6)], [0, 4, 8, 12, 16, 20])
        # the displayed labels are the rounded exact fractions
        for k, label in enumerate(swing.SP1200_LABELS):
            self.assertEqual(int(swing.swing_fraction("sp1200", k) * 100 + 0.5), label)

    def test_no_swing_on_triplets_or_32nds(self):
        for g in (32, 16, 12, 8):
            self.assertEqual(swing.offset("mpc", 66, g), 0)

    def test_quantize_moves_even_steps_only(self):
        # 16ths at 66%: lines 0, 32, 48, 80, 96 ... (straight 0, 24, 48, 72, 96)
        got = [swing.quantize(t, 24, "mpc", 66) for t in (1, 23, 50, 70, 95)]
        self.assertEqual(got, [0, 32, 48, 80, 96])

    def test_late_swung_note_stays_on_its_16th(self):
        # 38 is 6 ticks after the swung 32 and 10 before 48
        self.assertEqual(swing.quantize(38, 24, "mpc", 66), 32)
        self.assertEqual(swing.quantize(38, 24), 48)     # straight: nearest is 48

    def test_straight_matches_plain_rounding(self):
        for t in range(0, 400):
            for g in (48, 32, 24, 16, 12):
                self.assertEqual(swing.quantize(t, g), (t + g // 2) // g * g)

    def test_strength(self):
        self.assertEqual(swing.quantize(10, 24, strength=50), 5)   # 10 -> 0, half way
        self.assertEqual(swing.quantize(30, 24, "mpc", 66, strength=50), 31)  # 30 -> 32

    def test_doctests(self):
        self.assertEqual(doctest.testmod(swing).failed, 0)


if __name__ == "__main__":
    unittest.main()
