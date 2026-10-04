"""The swing build (tools/mkswing.py): what lands where. Replays the window
image's install table in Python and checks the resident pieces stay in
their boot-only homes, the hooks are the right jsr's, and overlay 3 is
overlay 0 with only the region changed.

Needs build/eps_os_249.bin. Run: python3 -m unittest discover tests
"""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import epstool  # noqa: E402
import mkswing as M  # noqa: E402

OS = os.path.join(ROOT, "build", "eps_os_249.bin")


@unittest.skipUnless(os.path.exists(OS), "needs build/eps_os_249.bin")
class SwingBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.os_bin = open(OS, "rb").read()
        cls.patch, cls.info = M.build(cls.os_bin)

    def test_fits(self):
        self.assertLessEqual(self.info["image_bytes"], M.LEN)
        self.assertLessEqual(M.CARRIER + self.info["carrier_bytes"], M.CARRIER_END)

    def test_resident_homes(self):
        homes = [(M.MUTE_AT, M.MUTE_END), (M.ML_AT, M.ML_END), (M.SWAPX_AT, M.SWAPX_END),
                 (M.LDR_MIN, M.LDR_END)]
        for a, d in self.info["chunks"]:
            if len(d) > 6:                      # code (the rest are hook words)
                self.assertTrue(any(lo <= a and a + len(d) <= hi for lo, hi in homes), hex(a))
        ldr = [(a, d) for a, d in self.info["chunks"] if a == self.info["ldr_at"]][0]
        self.assertEqual(ldr[0] + len(ldr[1]), M.LDR_END)      # falls into the loader

    def test_fixed_hooks(self):
        ch = dict(self.info["chunks"])
        self.assertEqual(ch[0xFFAF92].hex(), "4eb8" + f"{M.MUTE_AT & 0xFFFF:04x}")
        self.assertEqual(ch[0xFF1774].hex(), "4eb8" + f"{M.ML_AT & 0xFFFF:04x}" + "4e71")
        for a in (0xFF277C, 0xFF2A9E, 0xFF53B8, 0xFF8A24):
            self.assertEqual(ch[a].hex(), "4eb8" + f"{self.info['ldr_at'] & 0xFFFF:04x}")
        self.assertEqual(list(ch)[-1], 0xFF1774)                # the main loop hook last

    def test_install_table_replays(self):
        ov3 = self.info["ov3"]
        o = self.info["window"]["chunks"] - M.OVERLAY_WINDOW
        got = []
        while True:
            dest = int.from_bytes(ov3[o:o + 2], "big")
            if not dest:
                break
            n = int.from_bytes(ov3[o + 2:o + 4], "big") + 1
            got.append((0xFF0000 | dest, ov3[o + 4:o + 4 + n]))
            o += 4 + n
        self.assertEqual(got, [(a, bytes(d)) for a, d in self.info["chunks"]])

    def test_overlay3_is_overlay0_outside_the_region(self):
        o0 = epstool.addr_to_offset(M.OVERLAY_WINDOW, 0)
        ov0 = self.os_bin[o0:o0 + M.OVERLAY_SIZE]
        ov3 = self.info["ov3"]
        lo, hi = M.REGION - M.OVERLAY_WINDOW, M.REGION - M.OVERLAY_WINDOW + M.LEN
        self.assertEqual(ov3[:lo], ov0[:lo])
        self.assertEqual(ov3[hi:], ov0[hi:])
        self.assertEqual(ov3[lo:lo + 4], b"SWG1")

    def test_sequencer_hooks(self):
        ov3, w = self.info["ov3"], self.info["window"]
        o = w["hooks"] - M.OVERLAY_WINDOW
        sites = {}
        for i in range(2):
            e = ov3[o + 10 * i:o + 10 * i + 10]
            sites[int.from_bytes(e[:2], "big")] = (e[2:6].hex(), e[6:10].hex())
        self.assertEqual(sites[0x6746], ("4eb86ad6", "4eb8" + f"{w['wrap_hook'] & 0xFFFF:04x}"))
        self.assertEqual(sites[0x6B7C], ("4eb874f2", "4eb8" + f"{w['stop_hook'] & 0xFFFF:04x}"))
        for a, (stock, _) in sites.items():
            off = epstool.addr_to_offset(0xFF0000 | a)
            self.assertEqual(self.os_bin[off:off + 4].hex(), stock)


if __name__ == "__main__":
    unittest.main()
