"""Per-key mute groups (src/mutegroup.s) against real OS 2.49 code in the emulator.

The hook calls the OS's own voice kill (0xFFB7C2, which calls into the boot
ROM), so these tests run real EPS code on hand-built voice lists and
instrument records.

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
import mkcodearea  # noqa: E402

OS = os.path.join(ROOT, "build", "eps_os_249.bin")
ROM = os.path.join(ROOT, "build", "bootrom", "eps_boot_200.bin")
SRC = os.path.join(ROOT, "src", "mutegroup.s")

HOOK_SITE = 0xFFACA4
AFTER_SITE = 0xFFACAC        # first instruction after the 8 displaced bytes
VOICE_KILL = 0xFFB7C2
ACTIVE, RELEASE = 0xFF16E4, 0xFF16DC
IN_KEY = 0xFF16BB
INST_TABLE = 0xFFDF70
INST_RECORDS = 0xFFCE00      # test instrument records (zeros in the image)
VOICES, VSIZE = 0xFF0940, 154
TEST_ORG = 0x5F0000          # where the hook goes for these tests (sample RAM)
C2, D2, FS2, AS2 = 36, 38, 42, 46


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
        self.groups("")
        for i in range(8):
            self.instrument(i)

    # ---------------------------------------------------------- helpers
    def groups(self, spec):
        self.eps.write(self.syms["mute_table"],
                       mkcodearea.group_table(mkcodearea.parse_groups(spec)))

    def instrument(self, i, loaded=True, transpose=0):
        rec = INST_RECORDS + i * 0x40
        self.eps.ww(INST_TABLE + 2 * i, rec)
        self.eps.ww(rec, 0x1234 if loaded else 0)
        self.eps.wb(rec + 62, transpose)

    def voice(self, i, inst, key, state=4):
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

    def note_on(self, inst, key, **regs):
        self.eps.wb(IN_KEY, key)
        return self.eps.call(self.syms["mute_hook"], d5=inst, **regs)

    def kills(self):
        # a4 holds a short address (0x09DA = 0xFF09DA through the low mirror)
        return sorted(0xFF0000 | (r["a4"] & 0xFFFF) for a, r in self.eps.calls if a == VOICE_KILL)

    # ---------------------------------------------------------- tests
    def test_no_group_kills_nothing(self):
        v = [self.voice(0, 0, C2), self.voice(1, 0, D2)]
        self.link(ACTIVE, v)
        self.link(RELEASE, [])
        self.note_on(0, C2)
        self.assertEqual(self.kills(), [])

    def test_kit_in_one_instrument(self):
        """Kick and snare cut each other, hats have their own group, the
        rest of the kit (a clap on E2) is untouched."""
        self.groups("1:C2=1,1:D2=1,1:F#2-A#2=2")
        kick, snare = self.voice(0, 0, C2), self.voice(1, 0, D2)
        open_hat, clap = self.voice(2, 0, AS2), self.voice(3, 0, 40)
        self.link(ACTIVE, [kick, snare, open_hat, clap])
        self.link(RELEASE, [])
        self.note_on(0, D2)                       # snare: cuts kick and the old snare
        self.assertEqual(self.kills(), sorted([kick, snare]))
        self.eps.calls.clear()
        self.note_on(0, FS2)                      # closed hat: cuts the open hat
        self.assertEqual(self.kills(), [open_hat])
        self.assertEqual(self.state(clap), 4)

    def test_groups_across_instruments_and_release_list(self):
        self.groups("1:C2=3,2=3")                 # inst 1 key C2 and all of inst 2
        a = [self.voice(0, 0, C2), self.voice(1, 1, 60), self.voice(2, 0, D2)]
        r = [self.voice(3, 1, 72, state=6)]
        self.link(ACTIVE, a)
        self.link(RELEASE, r)
        self.note_on(1, 50)
        self.assertEqual(self.kills(), sorted([a[0], a[1], r[0]]))

    def test_transpose_is_applied_like_the_os(self):
        # instrument 1 transposed +12: pressing C1 (24) plays key C2 (36)
        self.groups("1:C2=1")
        self.instrument(0, transpose=12)
        v = self.voice(0, 0, C2)
        self.link(ACTIVE, [v])
        self.link(RELEASE, [])
        self.note_on(0, 24)
        self.assertEqual(self.kills(), [v])

    def test_empty_instrument_is_skipped(self):
        self.groups("1=1")
        self.instrument(0, loaded=False)
        self.link(ACTIVE, [self.voice(0, 0, C2)])
        self.link(RELEASE, [])
        self.note_on(0, C2)
        self.assertEqual(self.kills(), [])

    def test_voices_already_dying_are_skipped(self):
        self.groups("1=1")
        v = [self.voice(0, 0, C2, state=8), self.voice(1, 0, D2)]
        self.link(ACTIVE, v)
        self.link(RELEASE, [])
        self.note_on(0, C2)
        self.assertEqual(self.kills(), [v[1]])

    def test_kill_rate_matches_os_stealer(self):
        self.groups("1=1")
        self.link(ACTIVE, [self.voice(i, 0, 40 + i) for i in range(4)])
        self.link(RELEASE, [])
        self.note_on(0, 40)
        rates = [r["d4"] & 0xFFFF for a, r in self.eps.calls if a == VOICE_KILL]
        self.assertEqual(rates, [10] * 4)

    def test_registers_preserved(self):
        self.groups("4=1")
        self.link(ACTIVE, [self.voice(i, 3, 50 + i) for i in range(3)])
        self.link(RELEASE, [self.voice(3, 3, 60, state=6)])
        before = dict(d1=0x11111111, d2=0x22222222, d3=0x33333333, d4=0x44444444,
                      d6=0x66666666, d7=0x77777777, a0=0xA0A0A0A0, a2=0xA2A2A2A2,
                      a3=0xA3A3A3A3, a4=0xA4A4A4A4, a5=0xA5A5A5A5, a6=0xA6A6A6A6)
        after = self.note_on(3, 50, **before)
        self.assertEqual(len(self.kills()), 4)
        for r, val in before.items():
            self.assertEqual(after[r], val, r)
        # the displaced instructions ran: d0 = 2 * instrument, a1 = 0xFFDF70
        self.assertEqual(after["d0"] & 0xFFFF, 6)
        self.assertEqual(after["a1"] & 0xFFFFFF, 0xFFDF70)

    def test_patched_site_matches_stock(self):
        """Run the note-on entry up to the first non-displaced instruction,
        patched and stock, with a choke happening, and compare every register."""
        self.groups("1=1")
        self.link(ACTIVE, [self.voice(0, 0, C2)])
        self.link(RELEASE, [])
        self.eps.wb(IN_KEY, C2)
        regs = {r: 0x01010101 * (i + 1) for i, r in enumerate(
            ("d0", "d1", "d2", "d3", "d4", "d6", "d7", "a0", "a1", "a2", "a3", "a4", "a5", "a6"))}
        regs["d5"] = 0
        patched = self.eps.run_until(HOOK_SITE, AFTER_SITE, **regs)
        stock = EPS(ROM, OS, overlay=0).run_until(HOOK_SITE, AFTER_SITE, **regs)
        self.assertEqual(len(self.kills()), 1)
        self.assertEqual(patched, stock)


class GroupSpecTest(unittest.TestCase):
    def test_note_names(self):
        self.assertEqual([mkcodearea.key_number(k) for k in ("C2", "D2", "F#2", "Bb1", "A0", "C8", "60")],
                         [36, 38, 42, 34, 21, 108, 60])

    def test_spec_and_table(self):
        g = mkcodearea.parse_groups("1:C2=1,1:D2=1,1:F#2-A#2=2,3=4")
        self.assertEqual(g[(0, 36)], 1)
        self.assertEqual(g[(0, 44)], 2)
        self.assertEqual(g[(2, 21)], 4)
        self.assertNotIn((0, 37), g)
        t = mkcodearea.group_table(g)
        self.assertEqual(len(t), 352)
        i = 36 - 21                                   # inst 0, key 36: odd index -> low nibble
        self.assertEqual(t[i // 2] & 0x0F, 1)

    def test_old_per_instrument_form(self):
        g = mkcodearea.parse_groups("1,1,2,0,0,0,0,0")
        self.assertEqual({g[(0, 60)], g[(1, 21)], g[(2, 108)]}, {1, 2})
        self.assertEqual(g[(3, 60)], 0)


if __name__ == "__main__":
    unittest.main()
