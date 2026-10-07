"""CHOP's 32/16 division (src/swing/divl.s) against Python, for lengths up
to 2^24 samples (the first hardware test found it wrong above 65535).
Run: python3 -m unittest discover tests
"""
import os
import random
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from emu import EPS  # noqa: E402
import mkhook  # noqa: E402

OS = os.path.join(ROOT, "build", "eps_os_249.bin")
ROM = os.path.join(ROOT, "build", "bootrom", "eps_boot_200.bin")
ORG = 0x5F0000


@unittest.skipUnless(os.path.exists(OS) and os.path.exists(ROM), "needs OS and boot ROM in build/")
class Divl(unittest.TestCase):
    def test_divl(self):
        code, syms = mkhook.assemble(os.path.join(ROOT, "src", "swing", "divl.s"), ORG, "divl")
        e = EPS(ROM, OS)
        e.write(ORG, code)
        rnd = random.Random(1)
        cases = [(6112, 16), (65535, 16), (65536, 16), (66196, 16), (160000, 16), (250000, 3),
                 (0xFFFFFF, 32), (0xFFFFFF, 2), (5, 7)]
        cases += [(rnd.randrange(1, 1 << 24), rnd.choice([2, 3, 4, 6, 8, 12, 16, 24, 32])) for _ in range(300)]
        for n, k in cases:
            with self.subTest(n=n, k=k):
                r = e.call(syms["divl"], d0=n, d3=k)
                self.assertEqual(r["d0"] & 0xFFFFFFFF, n // k)
                self.assertEqual(r["d1"] & 0xFFFF, n % k)


if __name__ == "__main__":
    unittest.main()
