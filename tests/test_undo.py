"""Loop undo (src/looprec.s): pass tags, the RECORD button, playback skips
and the STOP clean-up, on the emulated 68000 with the real OS in RAM.
The hooks are called directly, with the OS state they look at set up the
way MAME shows it during LOOPED recording. Needs build/eps_os_249.bin and
build/bootrom/eps_boot_200.bin."""
import os
import random
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(__file__))
from emu import EPS, STOP, STACK_TOP  # noqa: E402
import mkcodearea  # noqa: E402
import seqstream as S  # noqa: E402
from test_swing_asm import random_take  # noqa: E402

OS = os.path.join(ROOT, "build", "eps_os_249.bin")
ROM = os.path.join(ROOT, "build", "bootrom", "eps_boot_200.bin")
IMG = 0x5E0000
MSG, EVENT, TRACK = 0x5F0000, 0x5F1000, 0x5F2000
REC_FLAGS, REC_MODE, SEQ_STATE, SAVED_STATE, KEEP_NEW = 0xFF815A, 0xFF815F, 0xFF8028, 0xFF802A, 0xFF815E
AFTER_REC_SITE, RELEASE, MSG_DONE = 0xFF7ADC, 0xFF7B18, 0xFF7B1E
AFTER_PLAY_SITE = 0xFF6390
SEQ_BASE, BUF_A, BUF_B, WRITE_PTR, BUF_SIZE = 0xFF8104, 0xFF8114, 0xFF8118, 0xFF811C, 0xFF8128


@unittest.skipUnless(os.path.exists(OS) and os.path.exists(ROM), "needs OS and boot ROM in build/")
class UndoTest(unittest.TestCase):
    def setUp(self):
        image, self.syms = mkcodearea.build_image({}, None, undo=True)
        self.e = e = EPS(ROM, OS)
        e.write(IMG, image)
        e.wb(REC_MODE, 2)                   # LOOPED
        e.wb(REC_FLAGS, 0x04)               # as in MAME while loop recording
        e.ww(SEQ_STATE, 0x58D6)             # recording over a track
        e.ww(SAVED_STATE, 0x58D6)
        for a in (0x6B12, 0x6AD6, 0x74F2):  # (jsr abs.w: the mirror at 0)
            e.stub(a)
        for a in (AFTER_PLAY_SITE, AFTER_REC_SITE, RELEASE, MSG_DONE):
            e.stub(a)

    def sym(self, name):
        return IMG + self.syms[name]

    def state(self):
        a = self.sym("undo_state")
        return [self.e.rw(a + 2 * i) for i in range(6)]   # cur last prev new kill killp

    def set_state(self, *words):
        for i, w in enumerate(words):
            self.e.ww(self.sym("undo_state") + 2 * i, w)

    def press(self, kind=1):
        """RECORD pressed (1) or released (2): where the hook returns to."""
        e = self.e
        e.wb(MSG + 6, kind)
        sp = STACK_TOP - 8
        e.wl(sp, AFTER_REC_SITE)
        e.wl(sp + 4, STOP)
        e.calls.clear()
        e.run_until(self.sym("rec_hook"), STOP, sp=sp, a5=MSG)
        hits = [a for a, _ in e.calls if a in (AFTER_REC_SITE, RELEASE, MSG_DONE)]
        self.assertEqual(len(hits), 1)
        return hits[0]

    def append(self, w0, w1, w2):
        """The append hook on a staged note; returns the staged words."""
        e = self.e
        for i, w in enumerate((w0, w1, w2)):
            e.ww(EVENT + 8 + 2 * i, w)
        e.call(self.sym("append_hook"), a4=EVENT, a6=0x100)
        return [e.rw(EVENT + 8 + 2 * i) for i in range(3)]

    def played(self, w2):
        """The note handler's hook: True if the note plays (and is copied)."""
        e = self.e
        e.ww(EVENT + 12, w2)
        e.ww(EVENT + 6, 5)                  # its gap
        sp = STACK_TOP - 8
        e.wl(sp, AFTER_PLAY_SITE)
        e.wl(sp + 4, STOP)                  # the handler's caller
        e.calls.clear()
        e.run_until(self.sym("play_hook"), STOP, sp=sp, a4=EVENT, a6=TRACK)
        hit = any(a == AFTER_PLAY_SITE for a, _ in e.calls)
        if not hit:                         # skipped: only its gap (0xFF637A)
            self.assertEqual(e.rw(TRACK + 4), 5)
        return hit

    def wrap(self):
        self.e.wl(WRITE_PTR, 0x100)
        self.e.wl(BUF_A, 0x0)
        self.e.wl(BUF_B, 0x10000)
        self.e.call(self.sym("wrap_hook"))

    NOTE = 0x8000 | 0x13 << 4               # key 40, instrument 0

    def test_new_notes_are_tagged_copies_keep_the_last_pass(self):
        self.assertEqual(self.state(), [1, 0, 0, 0, 0, 0])
        w = self.append(self.NOTE & 0x7FFF, 8 << 3, 0x4605)
        self.assertEqual(w, [self.NOTE, 8 << 3, 0x4601])
        self.assertEqual(self.state()[3], 1)
        self.set_state(2, 1, 0, 0, 0, 0)
        self.assertEqual(self.append(self.NOTE, 64, 0x0601)[2], 0x0601)  # last pass: kept
        self.assertEqual(self.append(self.NOTE, 64, 0x0603)[2], 0x0600)  # older: cleared
        self.assertEqual(self.state()[3], 0)                              # copies don't count

    def test_not_looped_nothing_happens(self):
        self.e.wb(REC_MODE, 0)
        self.assertEqual(self.append(self.NOTE & 0x7FFF, 64, 0x4600)[2], 0x4600)
        self.assertEqual(self.press(), AFTER_REC_SITE)
        self.e.wb(REC_MODE, 2)
        for state, flags in ((0x58B2, 0x80), (0x588E, 0x80), (0x5942, 0xC2), (0x58D6, 0x86)):
            self.e.ww(SEQ_STATE, state)     # playing, stopped, new sequence
            self.e.wb(REC_FLAGS, flags)
            self.assertEqual(self.press(), AFTER_REC_SITE)
        self.assertEqual(self.state(), [1, 0, 0, 0, 0, 0])

    def test_release_takes_the_release_path(self):
        self.assertEqual(self.press(2), RELEASE)

    def test_undo_this_pass_then_the_last(self):
        self.append(self.NOTE & 0x7FFF, 64, 0x4600)              # pass 1: tag 1
        self.wrap()
        self.assertEqual(self.state(), [2, 1, 0, 0, 0, 0])
        self.append(self.NOTE & 0x7FFF, 64, 0x4600)              # pass 2: tag 2
        self.assertEqual(self.press(), MSG_DONE)                 # undo pass 2's note
        self.assertEqual(self.state(), [3, 1, 0, 0, 1 << 2, 0])
        self.assertFalse(self.played(0x4602))
        self.assertTrue(self.played(0x4601))
        self.assertTrue(self.played(0x4600))
        self.assertEqual(self.press(), MSG_DONE)                 # then pass 1's
        self.assertEqual(self.state(), [3, 0, 0, 0, 1 << 2 | 1 << 1, 0])
        self.assertFalse(self.played(0x4601))
        self.assertEqual(self.press(), MSG_DONE)                 # nothing left
        self.assertEqual(self.state(), [3, 0, 0, 0, 1 << 2 | 1 << 1, 0])
        self.wrap()                                              # still skipped next pass
        self.assertEqual(self.state(), [3, 0, 0, 0, 0, 1 << 2 | 1 << 1])
        self.assertFalse(self.played(0x4602))
        self.assertFalse(self.played(0x4601))
        self.wrap()
        self.assertTrue(self.played(0x4601))
        self.e.ww(SEQ_STATE, 0x58B2)                             # playing: no skips
        self.set_state(3, 0, 0, 0, 2, 2)
        self.assertTrue(self.played(0x4601))

    def test_wrap_wait_state_counts_too(self):
        self.append(self.NOTE & 0x7FFF, 64, 0x4600)
        self.e.ww(SEQ_STATE, 0x5942)
        self.assertEqual(self.press(), MSG_DONE)
        self.assertEqual(self.state()[4], 1 << 1)

    def test_pass_without_new_notes_keeps_the_last(self):
        self.append(self.NOTE & 0x7FFF, 64, 0x4600)
        self.wrap()
        self.wrap()
        self.assertEqual(self.state(), [2, 1, 0, 0, 0, 0])

    def test_next_tag_skips_tags_in_use(self):
        self.set_state(15, 1, 2, 1, 1 << 3, 1 << 4)
        self.wrap()                         # LAST=15, PREV=1, kills: 3 (last pass)
        self.assertEqual(self.state()[:3], [2, 15, 1])
        self.set_state(13, 15, 14, 1, 0, 0)
        self.assertEqual(self.press(), MSG_DONE)
        self.assertEqual(self.state()[0], 1)

    def test_stop_drops_killed_notes_and_clears_tags(self):
        e = self.e
        rnd = random.Random(4)
        base = 0x600000
        killed = 0
        for n in range(60):
            words = random_take(rnd, rnd.choice([192, 384]))
            evs = S.split(words)
            for ev in evs:
                if S.is_note(ev):
                    ev[2] |= rnd.randrange(16)
            words = [w for ev in evs for w in ev]
            kill, killp = rnd.randrange(0x10000) & 0xFFFE, rnd.choice([0, 1 << rnd.randrange(1, 16)])
            e.wl(SEQ_BASE, base)
            e.wl(BUF_A, 0x278)
            e.wl(BUF_B, 0x10278)
            e.wl(BUF_SIZE, 0xFFFE)
            take = base + 0x278 + 28
            e.write(take, b"".join(w.to_bytes(2, "big") for w in words))
            e.wl(WRITE_PTR, 0x278 + 28 + 2 * len(words))
            e.wb(KEEP_NEW, 1)
            self.set_state(5, 4, 3, 2, kill, killp)
            e.call(self.sym("stop_hook"))
            end = base + e.rl(WRITE_PTR)
            got = [e.rw(a) for a in range(take, end, 2)]
            with self.subTest(n=n):
                exp = S.quantize_take(words, {}, kill | killp, opening=False)
                if exp != S.quantize_take(words, {}, opening=False):          # something killed
                    killed += 1
                    self.assertEqual(got, S.clear_tags(exp))
                    self.assertLess(len(S.notes(got)), len(S.notes(words)))
                else:
                    self.assertEqual(got, S.clear_tags(words))
                self.assertEqual(self.state(), [1, 0, 0, 0, 0, 0])
        self.assertGreater(killed, 30)


if __name__ == "__main__":
    unittest.main()
