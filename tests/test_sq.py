"""The hardware build's swing quantizer (src/swing/sq.s, streaming) against
the reference (tools/seqstream.py quantize_take), on takes recorded in MAME,
random takes and realistic loop passes. Needs the boot ROM and OS in
build/ (the emulator maps them). Run: python3 -m unittest discover tests
"""
import os
import random
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(__file__))
from emu import EPS  # noqa: E402
import mkhook  # noqa: E402
import seqstream as S  # noqa: E402
import swing  # noqa: E402
from test_swing_asm import MAME_TAKES, random_take, realistic_pass  # noqa: E402

OS = os.path.join(ROOT, "build", "eps_os_249.bin")
ROM = os.path.join(ROOT, "build", "bootrom", "eps_boot_200.bin")
SRC = os.path.join(ROOT, "src", "swing", "sq.s")
ORG, TAKE, SCRATCH_END = 0x5F0000, 0x600000, 0x67FF00


def ref(words, grid, pct):
    """Every note on one swung grid (the take is one track)."""
    return S.quantize_take(words, {i: (grid, "mpc", pct) for i in range(16)})


@unittest.skipUnless(os.path.exists(OS) and os.path.exists(ROM), "needs OS and boot ROM in build/")
class SqTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code, cls.syms = mkhook.assemble(SRC, ORG, "sq")
        cls.eps = EPS(ROM, OS)
        cls.eps.write(ORG, cls.code)

    def run_sq(self, words, grid, pct, scratch_end=SCRATCH_END):
        e = self.eps
        data = b"".join(w.to_bytes(2, "big") for w in words)
        e.write(TAKE, data)
        end = TAKE + len(data)
        r = e.call(self.syms["sq"], max_insns=20_000_000, a0=TAKE, a1=end, a3=scratch_end,
                   d1=grid, d2=swing.offset("mpc", pct, grid))
        new_end = r["a1"] & 0xFFFFFF
        out = e.read(TAKE, new_end - TAKE)
        return [int.from_bytes(out[i:i + 2], "big") for i in range(0, len(out), 2)]

    def check(self, words, grid, pct):
        got = self.run_sq(words, grid, pct)
        exp = ref(words, grid, pct)
        if got == words:                        # nothing moved: left as it was
            self.assertEqual(S.decode(got), S.decode(exp))
        else:
            self.assertEqual(got, exp)

    def test_mame_takes(self):
        for hexw in MAME_TAKES:
            w = S.parse(hexw)
            for grid, pct in ((12, 50), (12, 66), (24, 58), (48, 50), (4, 50)):
                with self.subTest(grid=grid, pct=pct):
                    self.check(w, grid, pct)

    def test_random_takes(self):
        rnd = random.Random(7)
        for n in range(300):
            w = random_take(rnd, rnd.choice([192, 384, 768, 3000]))
            grid = rnd.choice([48, 32, 24, 16, 12, 8, 6, 4])
            pct = rnd.randrange(50, 76) if grid in (12, 24) else 50
            with self.subTest(n=n, grid=grid, pct=pct):
                self.check(w, grid, pct)

    def test_realistic_passes(self):
        rnd = random.Random(11)
        for n in range(150):
            w = realistic_pass(rnd, rnd.choice([4, 8, 16, 32]), rnd.choice([1, 2, 4]))
            with self.subTest(n=n):
                self.check(w, 12, 58)

    def test_quantized_take_is_stable(self):
        """Quantizing again changes nothing: re-quantizing every pass is the
        same as quantizing once."""
        rnd = random.Random(3)
        for _ in range(30):
            w = random_take(rnd, 384)
            once = self.run_sq(w, 12, 62)
            self.assertEqual(self.run_sq(once, 12, 62), once)

    def test_wrap_to_the_start(self):
        """A downbeat played just before the loop end goes to the start."""
        timed = [(0, [0x8BB0]), (1, [0x8B10, 0x07F0]), (1, [0x8160, 0x0040, 0x0600]),
                 (190, [0x8160, 0x0040, 0x0600]), (192, [0x8BC0])]
        w = S.encode(timed)
        got = self.run_sq(w, 12, 50)
        self.assertEqual(got, ref(w, 12, 50))
        self.assertEqual([t for t, *_ in S.notes(got)], [1, 1])

    def test_scratch_too_small(self):
        """No room after the take: it stays as it was."""
        rnd = random.Random(5)
        w = realistic_pass(rnd, 16, 2)
        self.assertEqual(self.run_sq(w, 12, 58, scratch_end=TAKE + 2 * len(w) + 4), w)


if __name__ == "__main__":
    unittest.main()
