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
        self.assertLessEqual(self.info["image_bytes"], self.info["len"])
        self.assertLessEqual(M.REGION + self.info["len"], M.REGION_END)
        self.assertLessEqual(M.CARRIER + self.info["carrier_bytes"], M.CARRIER_END)

    def test_homes_dont_overlap(self):
        spans = sorted((a, a + len(d)) for a, d in self.info["chunks"])
        for (a0, e0), (a1, _) in zip(spans, spans[1:]):
            self.assertLessEqual(e0, a1, f"{a0:#x} overlaps {a1:#x}")

    def test_resident_homes(self):
        homes = [(M.MUTE_AT, M.MUTE_END), (M.ML_AT, M.ML_END), (M.SWAPX_AT, M.SWAPX_END),
                 (M.LDR_MIN, M.LDR_END), (M.LVL_AT, M.LVL_END), (M.OS1_AT, M.OS1_END),
                 (M.OS2_AT, M.OS2_END), (M.SPF_AT, M.SPF_END)]
        for a, d in self.info["chunks"]:
            if a not in M.STOCK:                # code (the rest are hook words)
                self.assertTrue(any(lo <= a and a + len(d) <= hi for lo, hi in homes), hex(a))
        ldr = [(a, d) for a, d in self.info["chunks"] if a == self.info["ldr_at"]][0]
        self.assertEqual(ldr[0] + len(ldr[1]), M.LDR_END)      # falls into the loader

    def test_fixed_hooks(self):
        ch = dict(self.info["chunks"])
        self.assertEqual(ch[0xFFAF92].hex(), "4eb8" + f"{M.MUTE_AT & 0xFFFF:04x}")
        self.assertEqual(ch[0xFF1774].hex(), "4eb8" + f"{M.ML_AT & 0xFFFF:04x}" + "4e71")
        self.assertEqual(ch[0xFFB252].hex(), "4eb8" + f"{M.LVL_AT & 0xFFFF:04x}")
        self.assertEqual(ch[0xFFAE54].hex(), "4eb8" + f"{M.OS1_AT & 0xFFFF:04x}")
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
        lo, hi = M.REGION - M.OVERLAY_WINDOW, M.REGION - M.OVERLAY_WINDOW + self.info["len"]
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

    def test_overlay2_sp_mode(self):
        """Overlay 2's FILTER CUTOFF reset calls the resident SP-mode code."""
        e = [e for e in self.patch["edits"] if e.get("overlay") == 2]
        self.assertEqual(len(e), 1)
        self.assertEqual(int(e[0]["addr"], 16), M.SPF_SITE)
        self.assertEqual(len(e[0]["data"]), len(e[0]["expect"]))
        self.assertIn("4eb8" + f"{M.SPF_AT & 0xFFFF:04x}", e[0]["data"])
        off = epstool.addr_to_offset(M.SPF_SITE, 2)
        self.assertEqual(self.os_bin[off:off + 20].hex(), M.SPF_STOCK)

    def test_os_words(self):
        """Every OS word patch/unpatch switches holds the stock value we put
        back (the Seq·Song page code, Edit's ENTER, the CHOP entry's type)."""
        ov3, w = self.info["ov3"], self.info["window"]
        o = w["words"] - M.OVERLAY_WINDOW
        seen = set()
        for i in range(w["NWORDS"]):
            e = ov3[o + 6 * i:o + 6 * i + 6]
            a, stock = 0xFF0000 | int.from_bytes(e[:2], "big"), e[2:4]
            off = epstool.addr_to_offset(a)
            self.assertEqual(self.os_bin[off:off + 2], stock, hex(a))
            seen.add(a)
        self.assertTrue({0xFFD064, 0xFFD066 + 2 * w["CHOP_TYPE"], 0xFFD098 + 2 * w["CHOP_TYPE"]} <= seen)


if __name__ == "__main__":
    unittest.main()
