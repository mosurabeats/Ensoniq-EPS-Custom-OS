"""The hardware build's swing quantizer (src/swing/sq.s, streaming) against
the reference (tools/seqstream.py quantize_take), on takes recorded in MAME,
random takes and realistic loop passes. Needs the boot ROM and OS in
build/ (the emulator maps them). Run: python3 -m unittest discover tests
"""
import os
import random
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(__file__))
from emu import EPS  # noqa: E402
from unicorn.m68k_const import UC_M68K_REG_SR  # noqa: E402
import mkhook  # noqa: E402
import seqstream as S  # noqa: E402
import swing  # noqa: E402
from test_swing_asm import MAME_TAKES, random_take, realistic_pass  # noqa: E402

OS = os.path.join(ROOT, "build", "eps_os_249.bin")
ROM = os.path.join(ROOT, "build", "bootrom", "eps_boot_200.bin")
SRC = os.path.join(ROOT, "src", "swing", "sq.s")
ORG, TAKE, SCRATCH_END = 0x5F0000, 0x600000, 0x67FF00


def floor(words):
    """The time nothing moves before (tools/seqstream.py quantize_take)."""
    timed, _ = S.decode(words)
    first = next((i for i, (t, ev) in enumerate(timed) if S.is_note(ev)), len(timed))
    floor = timed[first - 1][0] if first else 0
    if first < len(timed):
        floor = max([floor] + [t for t, ev in timed if not S.is_note(ev) and t <= timed[first][0]])
    return floor


def ref(words, grid, pct):
    """Every note on one swung grid (the take is one track)."""
    return S.quantize_take(words, {i: (grid, "mpc", pct) for i in range(16)})


@unittest.skipUnless(os.path.exists(OS) and os.path.exists(ROM), "needs OS and boot ROM in build/")
class SqTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code, cls.syms = mkhook.assemble(SRC, ORG, "sq")
        cls.eps = EPS(ROM, OS)
        cls.eps.write(ORG, cls.code)

    def run_sq(self, words, grid, pct, scratch_end=SCRATCH_END, kill=0):
        e = self.eps
        data = b"".join(w.to_bytes(2, "big") for w in words)
        e.write(TAKE, data)
        end = TAKE + len(data)
        r = e.call(self.syms["sq"], max_insns=20_000_000, a0=TAKE, a1=end, a3=scratch_end,
                   d0=kill, d1=grid, d2=swing.offset("mpc", pct, grid) if grid else 0)
        new_end = r["a1"] & 0xFFFFFF
        out = e.read(TAKE, new_end - TAKE)
        return [int.from_bytes(out[i:i + 2], "big") for i in range(0, len(out), 2)]

    def run_sqf(self, words, grid, pct, flags=0):
        """The fast path (sqf): (words after it, done). Not done: the take
        may be partly done, and sq finishes it."""
        e = self.eps
        data = b"".join(w.to_bytes(2, "big") for w in words)
        e.write(TAKE, data)
        end = TAKE + len(data)
        r = e.call(self.syms["sqf"], max_insns=20_000_000, a0=TAKE, a1=end,
                   d0=flags, d1=grid, d2=swing.offset("mpc", pct, grid))
        self.assertEqual((r["a0"] & 0xFFFFFF, r["a1"] & 0xFFFFFF), (TAKE, end))
        done = not e.uc.reg_read(UC_M68K_REG_SR) & 1
        out = e.read(TAKE, len(data))
        return [int.from_bytes(out[i:i + 2], "big") for i in range(0, len(out), 2)], done

    def check(self, words, grid, pct):
        got = self.run_sq(words, grid, pct)
        exp = ref(words, grid, pct)
        if got == words:                        # nothing moved: left as it was
            self.assertEqual(S.decode(got), S.decode(exp))
        else:
            self.assertEqual(got, exp)

    def test_mame_takes(self):
        for hexw in MAME_TAKES:
            w = S.parse(hexw)
            for grid, pct in ((12, 50), (12, 66), (24, 58), (48, 50), (4, 50)):
                with self.subTest(grid=grid, pct=pct):
                    self.check(w, grid, pct)

    def test_random_takes(self):
        rnd = random.Random(7)
        for n in range(300):
            w = random_take(rnd, rnd.choice([192, 384, 768, 3000]))
            grid = rnd.choice([48, 32, 24, 16, 12, 8, 6, 4])
            pct = rnd.randrange(50, 76) if grid in (12, 24) else 50
            with self.subTest(n=n, grid=grid, pct=pct):
                self.check(w, grid, pct)

    def test_realistic_passes(self):
        rnd = random.Random(11)
        for n in range(150):
            w = realistic_pass(rnd, rnd.choice([4, 8, 16, 32]), rnd.choice([1, 2, 4]))
            with self.subTest(n=n):
                self.check(w, 12, 58)

    def test_quantized_take_is_stable(self):
        """Quantizing again changes nothing: re-quantizing every pass is the
        same as quantizing once."""
        rnd = random.Random(3)
        for _ in range(30):
            w = random_take(rnd, 384)
            once = self.run_sq(w, 12, 62)
            self.assertEqual(self.run_sq(once, 12, 62), once)

    def test_wrap_to_the_start(self):
        """A downbeat played just before the loop end goes to the start."""
        timed = [(0, [0x8BB0]), (1, [0x8B10, 0x07F0]), (1, [0x8160, 0x0040, 0x0600]),
                 (190, [0x8160, 0x0040, 0x0600]), (192, [0x8BC0])]
        w = S.encode(timed)
        got = self.run_sq(w, 12, 50)
        self.assertEqual(got, ref(w, 12, 50))
        self.assertEqual([t for t, *_ in S.notes(got)], [1, 1])

    def test_undo_kill(self):
        """Notes tagged for undo (bit 3 of the last word) are dropped, with
        or without quantize; untagged ones stay (reference: tag 8 killed)."""
        rnd = random.Random(9)
        for n in range(200):
            evs = S.split(random_take(rnd, rnd.choice([192, 768])))
            for ev in evs:
                if S.is_note(ev) and rnd.random() < 0.3:
                    ev[2] |= 8
            words = [w for ev in evs for w in ev]
            grid = rnd.choice([0, 12, 24])
            pct = 58 if grid else 50
            got = self.run_sq(words, grid, pct, kill=1)
            exp = S.quantize_take(words, {i: (grid, "mpc", pct) for i in range(16)} if grid else {},
                                  kill=1 << 8)
            with self.subTest(n=n, grid=grid):
                if got == words:
                    self.assertEqual(S.decode(got), S.decode(exp))
                else:
                    self.assertEqual(got, exp)

    def test_tags_kept_without_kill(self):
        """Without undo, tagged notes are quantized like the others and keep
        their tag (it marks the newest pass)."""
        rnd = random.Random(4)
        evs = S.split(realistic_pass(rnd, 8, 2))
        for ev in evs:
            if S.is_note(ev):
                ev[2] |= 8
        words = [w for ev in evs for w in ev]
        got = self.run_sq(words, 12, 58)
        self.assertEqual(got, ref(words, 12, 58))
        self.assertTrue(all(ev[2] & 8 for ev in S.split(got) if S.is_note(ev)))

    def test_scratch_too_small(self):
        """No room after the take: it stays as it was."""
        rnd = random.Random(5)
        w = realistic_pass(rnd, 16, 2)
        self.assertEqual(self.run_sq(w, 12, 58, scratch_end=TAKE + 2 * len(w) + 4), w)


    # ---------------------------------------------------------- the fast path
    def new_pass(self, rnd, grid, pct, length, new, near_end=False):
        """A take as a wrap sees it: an earlier take quantized (untagged),
        plus `new` notes played in the pass just finished (tagged, bit 3),
        some of them chords, a few near the loop end if near_end."""
        base = ref(random_take(rnd, length), grid, pct)
        timed, _ = S.decode(base)
        end = next(t for t, ev in timed if S.code(ev[0]) == S.END)
        timed = [(t, ev, 0) for t, ev in timed if S.code(ev[0]) != S.END]
        for _ in range(new):
            t = rnd.randrange(2, end)
            if near_end and rnd.random() < 0.2:
                t = end - rnd.randrange(0, 6)               # (0: on the loop point, at END)
            for _ in range(rnd.choice([1, 1, 1, 2, 3])):     # chords
                ev = [0x8000 | rnd.randrange(15, 40) << 4 | rnd.randrange(3), rnd.randrange(1, 300) << 3,
                      rnd.randrange(1, 128) << 4 | 8]
                timed.append((t, ev, 1))
        timed.sort(key=lambda x: (x[0], x[2]))                # new after old at one time
        words = S.encode([(t, ev) for t, ev, _ in timed] + [(end, [0x8BC0])])
        if floor(words) != floor(base):
            return None     # a new note before the first old one moved the floor (an old note
        return words        # at it now moves too: sq's job; rare, a controller before the first note)

    def check_fast(self, words, grid, pct):
        """sqf alone or sqf then sq: the same take as the reference (time
        events may differ where sqf left them; the events and times not)."""
        exp = ref(words, grid, pct)
        got, done = self.run_sqf(words, grid, pct)
        if not done:
            got = self.run_sq(got, grid, pct)
        self.assertEqual(S.decode(got), S.decode(exp))
        return done

    def test_fast_path(self):
        rnd = random.Random(21)
        fast = total = 0
        for n in range(400):
            grid = rnd.choice([24, 12, 12, 8, 6])
            pct = rnd.randrange(50, 76) if grid in (12, 24) else 50
            w = self.new_pass(rnd, grid, pct, rnd.choice([192, 384, 768]), rnd.choice([1, 2, 4, 8]),
                              near_end=rnd.random() < 0.3)
            if w is None:
                continue
            total += 1
            with self.subTest(n=n, grid=grid, pct=pct):
                fast += self.check_fast(w, grid, pct)
        self.assertGreater(fast, total * 3 // 4)  # it's the usual case

    def test_fast_path_realistic(self):
        """Busy one- and two-bar takes, new notes a few ticks off the grid:
        the fast path does them alone."""
        rnd = random.Random(22)
        fast = 0
        for n in range(150):
            evs = S.split(realistic_pass(rnd, rnd.choice([8, 16]), rnd.choice([1, 2])))
            words = [w for ev in evs for w in ev]
            on_grid = {t for t, ev in S.decode(ref(words, 12, 58))[0] if S.is_note(ev)}
            t = 0
            for ev in evs:                      # the new ones: off the grid
                if S.is_note(ev) and t not in on_grid:
                    ev[2] |= 8
                t += S.gap_of(ev)
            words = [w for ev in evs for w in ev]
            with self.subTest(n=n):
                fast += self.check_fast(words, 12, 58)
        self.assertGreater(fast, 100)

    def test_fast_path_nothing_new(self):
        """No tagged notes: nothing changes."""
        rnd = random.Random(23)
        for _ in range(20):
            w = self.run_sq(random_take(rnd, 384), 12, 58)
            got, done = self.run_sqf(w, 12, 58)
            self.assertTrue(done)
            self.assertEqual(got, w)

    def test_note_before_the_opening_events(self):
        """Found on the hardware (2026-10-06): a hit right at the loop start
        is recorded at tick 1 before the opening events (also at tick 1). It
        stays at tick 1: the floor counts them (it went to tick 0, where the
        OS drops it on the next pass). The take as MAME recorded it."""
        w = S.parse("8bb0 8b90 0010 8160 0040 0608 8b10 07f0 8b80 0000 8bd0 07f0 8b10 07f0 8b80 0000 "
                    "bbd0 5ff0 9110 0040 4600 d110 0040 2600 9160 0040 4600 8bc0")
        for grid, pct in ((12, 50), (12, 58), (24, 50)):
            with self.subTest(grid=grid, pct=pct):
                exp = ref(w, grid, pct)
                self.assertEqual(S.notes(exp)[0][:2], (1, 43))
                got = self.run_sq(w, grid, pct)
                self.assertEqual(S.decode(got), S.decode(exp))
                for flags in ((0, 1, 2) if (grid, pct) == (12, 50) else (1,)):  # (0, 2: the
                                                    # old notes on the grid: the straight 1/16)
                    got, done = self.run_sqf(w, grid, pct, flags)
                    if not done:
                        got = self.run_sq(got, grid, pct)
                    self.assertEqual(S.decode(got), S.decode(exp))
                    self.assertTrue(all(t >= 1 for t, *_ in S.notes(got)))

    def test_note_at_the_end(self):
        """Found in MAME (2026-10-06): a hit played on the loop point is
        recorded at END's time. It's on the grid but it must wrap to the
        start (at END it never plays); sqf left it there."""
        timed = [(0, [0x8BB0]), (1, [0x8B10, 0x07F0]), (1, [0x8160, 0x0040, 0x0600]),
                 (96, [0x8170, 0x0040, 0x0600]), (192, [0x8160, 0x0040, 0x0608]),
                 (192, [0x8170, 0x0040, 0x0608]), (192, [0x8BC0])]
        w = S.encode(timed)
        exp = ref(w, 12, 50)
        self.assertEqual([t for t, *_ in S.notes(exp)], [1, 1, 1, 96])
        for flags in (0, 1):
            got, done = self.run_sqf(w, 12, 50, flags)
            self.assertTrue(done)
            self.assertEqual(S.decode(got), S.decode(exp))
        got, done = self.run_sqf(w, 12, 50, flags=2)      # keys held: next time
        self.assertFalse(done)
        self.assertEqual(got, w)
        # an earlier pass's (untagged) note there too: the take before a
        # punch-in ends a tick late (MAME), so its last hit is at END now
        w2 = S.encode([(t, ev[:2] + [ev[2] & ~8] if len(ev) == 3 else ev) for t, ev in timed])
        got, done = self.run_sqf(w2, 12, 50)
        self.assertTrue(done)
        self.assertEqual(S.decode(got), S.decode(ref(w2, 12, 50)))

    def test_fast_path_wrap(self):
        """A note played just before the loop end wraps to the start, as sq
        does it; not while keys are held (nothing may move then)."""
        timed = [(0, [0x8BB0]), (1, [0x8B10, 0x07F0]), (1, [0x8160, 0x0040, 0x0600]),
                 (96, [0x8170, 0x0040, 0x0600]), (190, [0x8160, 0x0040, 0x0608]), (192, [0x8BC0])]
        w = S.encode(timed)
        got, done = self.run_sqf(w, 12, 50)
        self.assertTrue(done)
        self.assertEqual(S.decode(got), S.decode(ref(w, 12, 50)))
        self.assertEqual([t for t, *_ in S.notes(got)], [1, 1, 96])
        got, done = self.run_sqf(w, 12, 50, flags=2)
        self.assertFalse(done)

    def test_fast_path_every_note(self):
        """Flag bit 0 (the first wrap, QUANTIZE changed): every note, not
        just the tagged ones."""
        rnd = random.Random(24)
        fast = 0
        for n in range(300):
            grid = rnd.choice([24, 12, 8])
            pct = rnd.randrange(50, 76) if grid in (12, 24) else 50
            w = random_take(rnd, rnd.choice([192, 384, 768]))
            with self.subTest(n=n, grid=grid, pct=pct):
                exp = ref(w, grid, pct)
                got, done = self.run_sqf(w, grid, pct, flags=1)
                if not done:
                    got = self.run_sq(got, grid, pct)
                fast += done
                self.assertEqual(S.decode(got), S.decode(exp))
        self.assertGreater(fast, 30)

    def test_fast_path_held(self):
        """Keys held (bit 1): in place only, never a move; sq finishes."""
        rnd = random.Random(25)
        for n in range(200):
            grid = rnd.choice([24, 12, 8])
            pct = 58 if grid == 12 else 50
            w = self.new_pass(rnd, grid, pct, 192, rnd.choice([2, 4, 8]), near_end=True)
            if w is None:
                continue
            got, done = self.run_sqf(w, grid, pct, flags=2)
            with self.subTest(n=n):
                self.assertEqual(len(got), len(w))
                old = [ev for ev in S.split(w)]
                self.assertEqual([ev[0] & 0x8FFF for ev in S.split(got) if S.is_note(ev)],
                                 [ev[0] & 0x8FFF for ev in old if S.is_note(ev)])  # nothing moved
                if not done:
                    got = self.run_sq(got, grid, pct)
                self.assertEqual(S.decode(got), S.decode(ref(w, grid, pct)))

if __name__ == "__main__":
    unittest.main()
