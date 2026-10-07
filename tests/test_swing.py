"""Reference swing math (tools/swing.py)."""
import doctest
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import swing  # noqa: E402


class SwingMathTest(unittest.TestCase):
    def test_mpc_16ths(self):
        # second 16th of each 8th lands at pct% of the 24-tick pair (48 PPQN)
        self.assertEqual([swing.offset("mpc", p, 12) for p in (50, 54, 58, 62, 66, 71, 75)],
                         [0, 1, 2, 3, 4, 5, 6])

    def test_mpc_8ths(self):
        self.assertEqual([swing.offset("mpc", p, 24) for p in (50, 54, 58, 66, 75)],
                         [0, 2, 4, 8, 12])

    def test_sp1200_is_exact(self):
        self.assertEqual([swing.offset("sp1200", k, 12) for k in range(6)], [0, 1, 2, 3, 4, 5])
        self.assertEqual([swing.offset("sp1200", k, 24) for k in range(6)], [0, 2, 4, 6, 8, 10])
        # the displayed labels are the rounded exact fractions
        for k, label in enumerate(swing.SP1200_LABELS):
            self.assertEqual(int(swing.swing_fraction("sp1200", k) * 100 + 0.5), label)

    def test_no_swing_on_triplets_or_32nds(self):
        for g in (48, 32, 16, 8, 6):
            self.assertEqual(swing.offset("mpc", 66, g), 0)

    def test_quantize_moves_even_steps_only(self):
        # 16ths at 66%: lines 0, 16, 24, 40, 48 ... (straight 0, 12, 24, 36, 48)
        got = [swing.quantize(t, 12, "mpc", 66) for t in (1, 11, 25, 35, 47)]
        self.assertEqual(got, [0, 16, 24, 40, 48])

    def test_late_swung_note_stays_on_its_16th(self):
        # 19 is 3 ticks after the swung 16 and 5 before 24
        self.assertEqual(swing.quantize(19, 12, "mpc", 66), 16)
        self.assertEqual(swing.quantize(19, 12), 24)     # straight: nearest is 24

    def test_straight_matches_plain_rounding(self):
        for t in range(0, 400):
            for g in (48, 32, 24, 16, 12):
                self.assertEqual(swing.quantize(t, g), (t + g // 2) // g * g)

    def test_strength(self):
        self.assertEqual(swing.quantize(4, 12, strength=50), 2)    # 4 -> 0, half way
        self.assertEqual(swing.quantize(14, 12, "mpc", 66, strength=50), 15)  # 14 -> 16

    def test_doctests(self):
        self.assertEqual(doctest.testmod(swing).failed, 0)


if __name__ == "__main__":
    unittest.main()
