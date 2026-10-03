"""Instrument files: key maps and mute groups (tools/instfile.py), on the
factory drum disk (tools/fetch.sh sounds)."""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import epstool  # noqa: E402
import instfile as I  # noqa: E402

DRUMS = os.path.join(ROOT, "build", "sounds", "DRMSET09.GKH")


@unittest.skipUnless(os.path.exists(DRUMS), "needs build/sounds/DRMSET09.GKH")
class InstFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        img = epstool.load_image(DRUMS)
        cls.tr808 = epstool.read_file(img, epstool.get_entry(img, 1))

    def test_key_map(self):
        r = I.key_ranges(self.tr808)
        self.assertEqual(r[1], (21, 36))         # the kick, up to C2
        self.assertEqual(r[11], (43, 45))        # open hat G2-A2
        self.assertEqual(r[12], (46, 46))        # closed hat A#2
        self.assertEqual(len(I.wavesamples(self.tr808)), 14)
        self.assertEqual(set(I.groups(self.tr808).values()), {0})

    def test_set_by_key(self):
        d, done = I.set_groups(self.tr808, "G2-A#2=1,C2-C#2=2")
        self.assertEqual(done, {11: 1, 12: 1, 1: 2, 13: 2})
        g = I.groups(d)
        self.assertEqual([g[w] for w in (11, 12, 1, 13, 2)], [1, 1, 2, 2, 0])
        # only the group bytes changed
        diff = [i for i in range(len(d)) if d[i] != self.tr808[i]]
        self.assertEqual(sorted(diff), sorted(I.wavesamples(d)[w] + I.WS_GROUP for w in done))

    def test_all_then_keys(self):
        d, _ = I.set_groups(self.tr808, "ALL=3,G2-A#2=1")
        g = I.groups(d)
        self.assertEqual(g[11], 1)
        self.assertEqual({g[w] for w in g if w not in (11, 12)}, {3})

    def test_one_wavesample_two_groups_is_an_error(self):
        with self.assertRaises(ValueError):
            I.set_groups(self.tr808, "G2=1,A2=2")    # both on wavesample 11


if __name__ == "__main__":
    unittest.main()
