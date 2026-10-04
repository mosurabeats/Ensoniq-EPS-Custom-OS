"""SP sampling mode (src/swing/spf.s): picking SAMPLE RATE 26.04 kHz gives
FILTER CUTOFF 20.0 KHZ; every other rate gets the stock filter. Runs the
patched overlay 2 (tools/mkswing.py) and the resident routine in the
emulator. Needs the boot ROM and OS in build/.
Run: python3 -m unittest discover tests
"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from emu import EPS  # noqa: E402
import epstool  # noqa: E402
import mkswing as M  # noqa: E402

OS = os.path.join(ROOT, "build", "eps_os_249.bin")
ROM = os.path.join(ROOT, "build", "bootrom", "eps_boot_200.bin")
RATE, FILTER = 0xFF020F, 0xFF0212


@unittest.skipUnless(os.path.exists(OS) and os.path.exists(ROM), "needs OS and boot ROM in build/")
class SPMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os_bin = open(OS, "rb").read()
        patch, info = M.build(os_bin)
        cls.table = open(ROM, "rb").read()[0x6FFE:0x6FFE + 40]   # ROM 0xC06FFE
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(epstool.apply_patch(os_bin, patch))
            cls.path = f.name
        cls.chunks = info["chunks"]

    @classmethod
    def tearDownClass(cls):
        os.unlink(cls.path)

    def filter_for(self, eps, rate):
        eps.wb(RATE, rate)
        eps.wb(FILTER, 0x55)
        eps.call(0xFFE20E, a6=RATE & 0xFFFF)     # as 0xFF45A6 calls it
        return eps.rb(FILTER)

    def test_sp_rate_opens_the_filter(self):
        eps = EPS(ROM, self.path, overlay=2)
        for a, d in self.chunks:                  # what install puts in OS RAM
            if M.SPF_AT <= a < M.SPF_END:
                eps.write(a, d)
        for rate in range(40):
            with self.subTest(rate=rate):
                want = 11 if rate == 27 else self.table[rate]
                self.assertEqual(self.filter_for(eps, rate), want)

    def test_the_sp_rate_is_26_04_khz(self):
        divisor = open(ROM, "rb").read()[0x7026 + 27]     # ROM 0xC07026
        self.assertEqual(divisor, 24)
        self.assertAlmostEqual(625 / divisor, 26.04, places=2)

    def test_stock_overlay_2(self):
        eps = EPS(ROM, OS, overlay=2)
        self.assertEqual(self.filter_for(eps, 27), self.table[27])


if __name__ == "__main__":
    unittest.main()
