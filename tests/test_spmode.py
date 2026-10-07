"""Sampling on the swing build (src/swing/spsample.s): FILTER CUTOFF up to
50 kHz and SP sampling mode. Runs the patched overlay 2 in the emulator and
checks the page and tables against the ROM's. Needs the boot ROM and OS in
build/. Run: python3 -m unittest discover tests
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
class Sampling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os_bin = open(OS, "rb").read()
        patch, info = M.build(os_bin)
        cls.rom = open(ROM, "rb").read()
        cls.patched = epstool.apply_patch(os_bin, patch)
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(cls.patched)
            cls.path = f.name
        cls.syms = info["sampling"]

    @classmethod
    def tearDownClass(cls):
        os.unlink(cls.path)

    def r(self, n, a):
        return self.rom[a - 0xC00000:a - 0xC00000 + n]

    def ram(self, eps, a, n):
        return eps.read(a, n)

    def filter_for(self, eps, rate):
        eps.wb(RATE, rate)
        eps.wb(FILTER, 0x55)
        eps.call(0xFFE20E, a6=RATE & 0xFFFF)     # as 0xFF45A6 calls it
        return eps.rb(FILTER)

    def test_sp_rate_opens_the_filter(self):
        """26.04 kHz picks 20.0 KHZ; every other rate the ROM's filter."""
        eps = EPS(ROM, self.path, overlay=2)
        table = self.r(40, 0xC06FFE)
        for rate in range(40):
            with self.subTest(rate=rate):
                self.assertEqual(self.filter_for(eps, rate), 11 if rate == 27 else table[rate])

    def test_the_sp_rate_is_26_04_khz(self):
        divisor = self.r(1, 0xC07026 + 27)[0]
        self.assertEqual(divisor, 24)
        self.assertAlmostEqual(625 / divisor, 26.04, places=2)

    def test_filter_table(self):
        """Both readers of the filter table read ours: the ROM's 12, then
        N = 13, 14, 15 (E = 0x28 | (N & 8) << 1 | (N & 7))."""
        eps = EPS(ROM, self.path, overlay=2)
        etab = self.syms["etab"]
        got = self.ram(eps, etab, 15)
        self.assertEqual(got[:12], self.r(12, 0xC0704E))
        self.assertEqual(list(got), [0x28 | (n & 8) << 1 | (n & 7) for n in range(1, 16)])
        for site in (0xFFE38A, 0xFFE642):
            self.assertEqual(eps.rl(site), etab)

    def test_sampling_page(self):
        """The page record and the OS code that names its entries point at
        our index: the ROM's entries, ours for FILTER CUTOFF (15 choices,
        the ROM's 12 labels then 25.0, 33.3, 50.0)."""
        eps = EPS(ROM, self.path, overlay=2)
        first, last = self.syms["sindex"], self.syms["sindex_last"]
        self.assertEqual([eps.rw(0xFFC23A + 2 * i) for i in range(3)],
                         [first & 0xFFFF, last & 0xFFFF, first & 0xFFFF])
        for a, v in ((0xFF31A8, first), (0xFF3240, first), (0xFF324A, last)):
            self.assertEqual(eps.rw(a), v & 0xFFFF, hex(a))
        ours = [eps.rw(first + 2 * i) for i in range(6)]
        rom = [int.from_bytes(self.r(2, 0xC028A6 + 2 * i), "big") for i in range(6)]
        self.assertEqual(ours[:2] + ours[3:], rom[:2] + rom[3:])
        desc = 0xFF0000 | ours[2]
        self.assertEqual(rom[2], 0x28E2)                       # the ROM's FILTER CUTOFF
        stock = self.r(8, 0xC028E2)
        mine = self.ram(eps, desc, 8)
        self.assertEqual(mine[:2] + mine[4:], stock[:2] + stock[4:])   # all but the table
        tbl = 0xFF0000 | int.from_bytes(mine[2:4], "big")
        labels, width, count = eps.rl(tbl), eps.rb(tbl + 4), eps.rb(tbl + 5)
        self.assertEqual((width, count), (3, 15))
        texts = [self.ram(eps, labels + i * 4, 3) for i in range(15)]
        rp = int.from_bytes(self.r(4, 0xC03ABE), "big")
        rw = self.r(1, 0xC03AC2)[0]
        rom_texts = [self.r(3, rp + i * (rw + 1)) for i in range(12)]
        self.assertEqual(texts[:12], rom_texts)
        self.assertEqual(texts[12:], [b"2:0", b"3(3", b"5!0"])

    def test_msb_adjustment_does_nothing(self):
        eps = EPS(ROM, self.path)
        self.assertEqual(eps.rw(0xFFC5C4), 0x4B54)
        self.assertEqual(eps.rw(0xFFC5D2), 0x4B54)              # as DC OFFSET ADJUSTMENT

    def test_stock_overlay_2(self):
        eps = EPS(ROM, OS, overlay=2)
        self.assertEqual(self.filter_for(eps, 27), self.r(40, 0xC06FFE)[27])


if __name__ == "__main__":
    unittest.main()
