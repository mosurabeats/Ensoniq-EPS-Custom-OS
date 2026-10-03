"""Mute-group hook (src/mutegroup.s) against real OS 2.49 code in the emulator.

The hook calls the OS's own voice kill (0xFFB7C2, which calls into the boot
ROM), so these tests run real EPS code on hand-built voice lists.

Needs build/eps_os_249.bin (tools/fetch.sh) and build/bootrom/eps_boot_200.bin
(see docs/RESOURCES.md). Run: python3 -m unittest discover tests
"""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from emu import EPS  # noqa: E402
import mkhook  # noqa: E402

OS = os.path.join(ROOT, "build", "eps_os_249.bin")
ROM = os.path.join(ROOT, "build", "bootrom", "eps_boot_200.bin")
SRC = os.path.join(ROOT, "src", "mutegroup.s")

HOOK_SITE = 0xFFACA4
AFTER_SITE = 0xFFACAC        # first instruction after the 8 displaced bytes
VOICE_KILL = 0xFFB7C2
ACTIVE, RELEASE = 0xFF16E4, 0xFF16DC
VOICES, VSIZE = 0xFF0940, 154
TEST_ORG = 0x5F0000          # where the hook goes for these tests (sample RAM)


@unittest.skipUnless(os.path.exists(OS) and os.path.exists(ROM), "needs OS and boot ROM in build/")
class MuteGroupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code, cls.syms = mkhook.assemble(SRC, TEST_ORG, "mute_hook")

    def setUp(self):
        self.eps = EPS(ROM, OS, overlay=0)
        self.eps.write(TEST_ORG, self.code)
        self.eps.write(HOOK_SITE, mkhook.hook_jsr(self.syms["mute_hook"], 8))
        self.eps.watch(VOICE_KILL)
        self.groups([0] * 8)

    # ---------------------------------------------------------- helpers
    def groups(self, g):
        self.eps.write(self.syms["mute_table"], bytes(g))

    def voice(self, i, inst, state=4, key=60):
        v = VOICES + i * VSIZE
        self.eps.wb(v + 4, key)
        self.eps.wb(v + 6, inst)
        self.eps.wb(v + 12, state)
        return v

    def link(self, sentinel, voices):
        """Circular list: sentinel -> voices... -> sentinel (+0 next, +2 prev)."""
        chain = [sentinel] + voices + [sentinel]
        for a, b in zip(chain, chain[1:]):
            self.eps.ww(a, b)
            self.eps.ww(b + 2, a)

    def state(self, v):
        return self.eps.rb(v + 12)

    def note_on(self, inst, **regs):
        return self.eps.call(self.syms["mute_hook"], d5=inst, **regs)

    def kills(self):
        # a4 holds a short address (0x09DA = 0xFF09DA through the low mirror)
        return [0xFF0000 | (r["a4"] & 0xFFFF) for a, r in self.eps.calls if a == VOICE_KILL]

    # ---------------------------------------------------------- tests
    def test_no_group_kills_nothing(self):
        v = [self.voice(0, 2), self.voice(1, 2)]
        self.link(ACTIVE, v)
        self.link(RELEASE, [])
        self.note_on(2)
        self.assertEqual(self.kills(), [])
        self.assertEqual([self.state(x) for x in v], [4, 4])

    def test_group_chokes_both_lists(self):
        # instruments 2 and 3 share group 1 (open/closed hat); 4 is group 2
        self.groups([0, 0, 1, 1, 2, 0, 0, 0])
        a = [self.voice(0, 2), self.voice(1, 3), self.voice(2, 4), self.voice(3, 3)]
        r = [self.voice(4, 3, state=6), self.voice(5, 4, state=6), self.voice(6, 0, state=6)]
        self.link(ACTIVE, a)
        self.link(RELEASE, r)
        self.note_on(2)
        killed = {a[0], a[1], a[3], r[0]}
        self.assertEqual(set(self.kills()), killed)
        for x in a + r:
            self.assertEqual(self.state(x) == 8, x in killed, hex(x))

    def test_own_other_keys_are_cut(self):
        # one instrument in a group: a chopped break plays mono
        self.groups([0, 0, 0, 0, 0, 5, 0, 0])
        v = [self.voice(0, 5, key=40), self.voice(1, 5, key=41)]
        self.link(ACTIVE, v)
        self.link(RELEASE, [])
        self.note_on(5)
        self.assertEqual(sorted(self.kills()), sorted(v))

    def test_voices_already_dying_are_skipped(self):
        self.groups([1] * 8)
        v = [self.voice(0, 1, state=8), self.voice(1, 1)]
        self.link(ACTIVE, v)
        self.link(RELEASE, [])
        self.note_on(1)
        self.assertEqual(self.kills(), [v[1]])

    def test_kill_rate_matches_os_stealer(self):
        self.groups([1] * 8)
        self.link(ACTIVE, [self.voice(i, i) for i in range(4)])
        self.link(RELEASE, [])
        self.note_on(0)
        rates = [r["d4"] & 0xFFFF for a, r in self.eps.calls if a == VOICE_KILL]
        self.assertEqual(rates, [10] * 4)

    def test_registers_preserved(self):
        self.groups([1] * 8)
        self.link(ACTIVE, [self.voice(i, 1) for i in range(3)])
        self.link(RELEASE, [self.voice(3, 1, state=6)])
        before = dict(d1=0x11111111, d2=0x22222222, d3=0x33333333, d4=0x44444444,
                      d6=0x66666666, d7=0x77777777, a0=0xA0A0A0A0, a2=0xA2A2A2A2,
                      a3=0xA3A3A3A3, a4=0xA4A4A4A4, a5=0xA5A5A5A5, a6=0xA6A6A6A6)
        after = self.note_on(3, **before)
        self.assertEqual(len(self.kills()), 4)
        for r, val in before.items():
            self.assertEqual(after[r], val, r)
        # the displaced instructions ran: d0 = 2 * instrument, a1 = 0xFFDF70
        self.assertEqual(after["d0"] & 0xFFFF, 6)
        self.assertEqual(after["a1"] & 0xFFFFFF, 0xFFDF70)

    def test_patched_site_matches_stock(self):
        """Run the note-on entry up to the first non-displaced instruction,
        patched and stock, and compare every register."""
        self.link(ACTIVE, [])
        self.link(RELEASE, [])
        regs = dict(d0=0xDEADBEEF, d5=0x00000004, a1=0x12345678, a5=0x55)
        patched = self.eps.run_until(HOOK_SITE, AFTER_SITE, **regs)
        stock = EPS(ROM, OS, overlay=0).run_until(HOOK_SITE, AFTER_SITE, **regs)
        self.assertEqual(patched, stock)


if __name__ == "__main__":
    unittest.main()
