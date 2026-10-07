"""The resident mute-groups patch (tools/mkresident.py): what the late init
(src/lateinit.s) copies, replayed in Python from the patched carriers.

Needs build/eps_os_249.bin and the boot ROM dumps (docs/RESOURCES.md).
Run: python3 -m unittest discover tests
"""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import epstool  # noqa: E402
import mkresident as R  # noqa: E402

OS = os.path.join(ROOT, "build", "eps_os_249.bin")
ROMS = [os.path.join(ROOT, "build", "bootrom", "eps_boot_240.bin"),
        os.path.join(ROOT, "build", "bootrom", "unknown", "eps_boot_unknown.bin")]


def ram_of(os_bin, patch):
    """The patched OS file's bytes as {address: byte} for the edited ranges,
    plus a reader for any loaded address."""
    new = epstool.apply_patch(os_bin, patch)

    def rd(a, n):
        o = epstool.addr_to_offset(a)
        return new[o:o + n]
    return rd


def replay(rd, table_at):
    """The copy loop: [(destination, bytes)] until a 0 destination."""
    out, a = [], table_at
    while True:
        dest = int.from_bytes(rd(a, 2), "big")
        if not dest:
            return out
        n = int.from_bytes(rd(a + 2, 2), "big") + 1
        out.append((0xFF0000 | dest, rd(a + 4, n)))
        a += 4 + n


@unittest.skipUnless(os.path.exists(OS), "needs build/eps_os_249.bin")
class Resident(unittest.TestCase):
    def setUp(self):
        self.os_bin = open(OS, "rb").read()
        self.patch, self.info = R.build(self.os_bin)
        self.rd = ram_of(self.os_bin, self.patch)

    def test_call_site(self):
        self.assertEqual(self.rd(R.CALL_SITE, 4).hex(), "4eb8c994")

    def test_tables_copy_the_payload(self):
        p = self.info["payload"]
        t1 = replay(self.rd, self.info["late"]["table1"])
        t2 = replay(self.rd, R.CARRIER2)
        self.assertEqual(t2, [p["index"], p["desc"]])
        # the hook and the page record last: after everything they point at
        self.assertEqual(t1, [p["code"], p["hook"], p["page"]])

    def test_magic_at_each_carrier_end(self):
        for start, n in (self.info["carrier1"], self.info["carrier2"]):
            self.assertEqual(int.from_bytes(self.rd(start + n - 4, 4), "big"), R.MAGIC)

    def test_hook_and_page(self):
        p = self.info["payload"]
        self.assertEqual(p["hook"][1].hex(), "4eb8" + f"{R.CODE_AT & 0xFFFF:04x}")
        rec = p["page"][1]
        first, last, cur, page, end = (int.from_bytes(rec[i:i + 2], "big") for i in range(0, 10, 2))
        self.assertEqual((first, cur, page), (R.INDEX_AT & 0xFFFF, R.INDEX_AT & 0xFFFF, 0x0600))
        self.assertEqual(last, end)
        index = p["index"][1]
        self.assertEqual(0xFF0000 | last, R.INDEX_AT + len(index) - 2)
        self.assertEqual(int.from_bytes(index[-2:], "big"), R.DESC_AT & 0xFFFF)

    def test_descriptor(self):
        d = self.info["payload"]["desc"][1]
        self.assertEqual(d[:6].hex(), "0800000f011e")       # number 0-15, at WS +0x11E
        label_at = 0xFF0000 | int.from_bytes(d[6:8], "big")
        self.assertEqual(d[label_at - R.DESC_AT:].split(b"\0")[0], b"MUTE GROUP")

    def test_rom_index_entries(self):
        """The 6 Amp page's ROM index table (0xC02562-0xC02570), copied
        into ours, is the same in the boot ROMs we have."""
        for f in ROMS:
            if not os.path.exists(f):
                continue
            rom = open(f, "rb").read()
            words = [int.from_bytes(rom[a:a + 2], "big") for a in range(0x2562, 0x2572, 2)]
            self.assertEqual(words, R.AMP_DESCS, f)

    def test_code_fits_the_boot_sequence(self):
        a, code = self.info["payload"]["code"]
        self.assertEqual(a, R.CODE_AT)
        self.assertLessEqual(a + len(code), R.CALL_SITE)


if __name__ == "__main__":
    unittest.main()
