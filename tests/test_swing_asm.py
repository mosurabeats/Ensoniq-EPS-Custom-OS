"""The 68000 swing quantizer (src/swing.s) against the reference
(tools/seqstream.py quantize_take), on takes recorded in MAME and on random
takes. Needs the boot ROM and OS in build/ (the emulator maps them)."""
import os
import random
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from emu import EPS  # noqa: E402
import mkhook  # noqa: E402
import seqstream as S  # noqa: E402
import swing  # noqa: E402

OS = os.path.join(ROOT, "build", "eps_os_249.bin")
ROM = os.path.join(ROOT, "build", "bootrom", "eps_boot_200.bin")
SRC = os.path.join(ROOT, "src", "swing.s")
ORG, SETTINGS, TAKE, SCRATCH_END = 0x5F0000, 0x5F8000, 0x600000, 0x67FF00

# finished LOOPED takes dumped from MAME (mame/keys/loop_record.txt)
MAME_TAKES = [
    "8bb0 8b90 0010 8b10 07f0 8b80 0000 bbd0 7ff0 e110 0040 4600 9160 0040 4600 8bc0",
    "8bb0 8b90 0010 8160 0040 0600 8b10 07f0 8b80 0000 8bd0 07f0 8b10 07f0 8b80 0000 "
    "bbd0 7ff0 9110 0040 0600 d110 0040 4600 9160 0040 4600 8bc0",
]


def settings_table(settings):
    t = bytearray(32)
    for inst, (grid, style, amount) in settings.items():
        t[4 * inst:4 * inst + 4] = grid.to_bytes(2, "big") + swing.offset(style, amount, grid).to_bytes(2, "big")
    return bytes(t)


def random_take(rnd, length):
    """A take like the EPS records: start marker, controller states, notes
    (some instruments, mid-take controllers), END at the loop length."""
    timed = [(0, [0x8BB0])]
    t0 = 1
    for c in (0xB1, 0xB8, 0xBD):
        timed.append((t0, [0x8000 | c << 4, rnd.randrange(128) << 4]))
    t = t0
    while True:
        t += rnd.choice([0, 0, 1, 3, 5, 7, 11, 13, 40, 100, 130, 200, 600])
        if t >= length:
            break
        if rnd.random() < 0.15:
            timed.append((t, [0x8000 | 0xB1 << 4 | rnd.randrange(8), rnd.randrange(128) << 4]))
        else:
            inst = rnd.choice([0, 0, 1, 2, 7])
            key = rnd.randrange(21, 109)
            timed.append((t, [0x8000 | (key - 21) << 4 | inst, rnd.randrange(1, 400) << 3,
                              rnd.randrange(1, 128) << 4]))
    timed.append((length, [0x8BC0]))
    return S.encode(timed)


def logged_pass(rnd, per_bar, bars, new):
    """A take as a wrap sees it in log mode: earlier notes on the swung 1/16
    grid, `new` new ones up to 5 ticks off. Returns (words, log) with log =
    [(word index, time)] of the new notes, in stream order."""
    length = 192 * bars
    timed = [(0, [0x8BB0], 0)] + [(1, [0x8000 | c << 4, rnd.randrange(128) << 4], 0) for c in (0xB1, 0xB8, 0xBD)]
    for _ in range(per_bar * bars):
        step = rnd.randrange(length // 12)
        t = max(1, step * 12 + (2 if step % 2 else 0))
        timed.append((min(t, length - 1), [0x8000 | rnd.randrange(15, 40) << 4 | rnd.randrange(3), 8 << 3, 0x60 << 4], 0))
    for _ in range(new):
        t = 12 + rnd.randrange(length // 12 - 1) * 12 + rnd.randrange(-5, 6)
        timed.append((t, [0x8000 | rnd.randrange(15, 40) << 4 | rnd.randrange(3), 8 << 3, 0x60 << 4], 1))
    timed.sort(key=lambda x: x[0])
    timed.append((length, [0x8BC0], 0))
    words = S.encode([(t, ev) for t, ev, _ in timed])
    log, wi, k = [], 0, 0
    for ev in S.split(words):
        if S.code(ev[0]) != S.TIME:
            if timed[k][2]:
                log.append((wi, timed[k][0]))
            k += 1
        wi += len(ev)
    return words, log


def realistic_pass(rnd, per_bar, bars):
    """Notes from earlier passes on the swung 1/16 grid (58%), plus a
    quarter as many new ones played up to 5 ticks off."""
    length = 192 * bars
    timed = [(0, [0x8BB0])] + [(1, [0x8000 | c << 4, rnd.randrange(128) << 4]) for c in (0xB1, 0xB8, 0xBD)]
    for _ in range(per_bar * bars):
        step = rnd.randrange(length // 12)
        t = max(1, step * 12 + (2 if step % 2 else 0))
        timed.append((min(t, length - 1), [0x8000 | rnd.randrange(15, 40) << 4 | rnd.randrange(3), 8 << 3, 0x60 << 4]))
    for _ in range(max(1, per_bar * bars // 4)):
        t = 12 + rnd.randrange(length // 12 - 1) * 12 + rnd.randrange(-5, 6)
        timed.append((t, [0x8000 | rnd.randrange(15, 40) << 4 | rnd.randrange(3), 8 << 3, 0x60 << 4]))
    timed.sort(key=lambda x: x[0])
    timed.append((length, [0x8BC0]))
    return S.encode(timed)


@unittest.skipUnless(os.path.exists(OS) and os.path.exists(ROM), "needs OS and boot ROM in build/")
class SwingAsmTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code, cls.syms = mkhook.assemble(SRC, ORG, "swing_take")
        cls.eps = EPS(ROM, OS)
        cls.eps.write(ORG, cls.code)

    def run_asm(self, words, settings, scratch_end=SCRATCH_END):
        e = self.eps
        data = b"".join(w.to_bytes(2, "big") for w in words)
        e.write(TAKE, data)
        e.write(SETTINGS, settings_table(settings))
        end = TAKE + len(data)
        r = e.call(self.syms["swing_take"], max_insns=20_000_000, a0=TAKE, a1=end,
                   a2=end, a3=scratch_end, a4=SETTINGS)
        new_end = r["a1"] & 0xFFFFFF
        out = e.read(TAKE, new_end - TAKE)
        return [int.from_bytes(out[i:i + 2], "big") for i in range(0, len(out), 2)]

    def check(self, words, settings):
        got = self.run_asm(words, settings)
        self.assertEqual(got, S.swing_take(words, settings))           # exact
        self.assertEqual(sorted(S.notes(got)), sorted(S.notes(S.quantize_take(words, settings))))

    def test_mame_takes(self):
        for hexw in MAME_TAKES:
            w = S.parse(hexw)
            for settings in ({0: (12, "mpc", 50)}, {0: (12, "mpc", 66)}, {0: (24, "sp1200", 3)}, {}):
                with self.subTest(settings=settings):
                    self.check(w, settings)

    def test_nothing_to_do_is_identity(self):
        for hexw in MAME_TAKES:
            w = S.parse(hexw)
            self.assertEqual(self.run_asm(w, {}), w)

    def test_random_takes(self):
        rnd = random.Random(7)
        for n in range(300):
            w = random_take(rnd, rnd.choice([192, 384, 768, 3000]))
            settings = {i: (rnd.choice([12, 24, 8, 6, 48]), rnd.choice(["mpc", "sp1200"]), 0)
                        for i in rnd.sample(range(8), rnd.randrange(0, 4))}
            for i, (g, st, _) in list(settings.items()):
                settings[i] = (g, st, rnd.randrange(50, 76) if st == "mpc" else rnd.randrange(6))
            with self.subTest(n=n):
                self.check(w, settings)

    def test_quantized_take_is_stable(self):
        """Quantizing again changes nothing (what makes re-quantizing every
        pass the same as quantizing at record time)."""
        rnd = random.Random(3)
        for _ in range(30):
            w = random_take(rnd, 384)
            s = {0: (12, "mpc", 62), 1: (24, "sp1200", 4)}
            once = self.run_asm(w, s)
            self.assertEqual(self.run_asm(once, s), once)

    def test_realistic_passes(self):
        """A quantized take plus a pass of new, off-grid hits (what a wrap
        sees): the fast path does it."""
        rnd = random.Random(11)
        st = {i: (12, "mpc", 58) for i in range(8)}
        for n in range(150):
            w = realistic_pass(rnd, rnd.choice([4, 8, 16, 32]), rnd.choice([1, 2, 4]))
            with self.subTest(n=n):
                self.check(w, st)

    def run_logged(self, words, settings, log):
        e = self.eps
        data = b"".join(w.to_bytes(2, "big") for w in words)
        e.write(TAKE, data)
        e.write(SETTINGS, settings_table(settings))
        LOG = 0x5F9000
        def q(wi, t):                       # what the append hook works out
            inst = words[wi] & 0xF
            if inst not in settings:
                return t
            g, style, amount = settings[inst]
            return swing.quantize(t, g, style, amount)
        e.write(LOG, b"".join((TAKE + 2 * wi).to_bytes(4, "big") + t.to_bytes(4, "big")
                              + q(wi, t).to_bytes(4, "big") for wi, t in log))
        end = TAKE + len(data)
        r = e.call(self.syms["swing_logged"], max_insns=20_000_000, a0=TAKE, a1=end,
                   a2=LOG, a4=SETTINGS, a5=0, d0=len(log))
        out = e.read(TAKE, len(data))
        return [int.from_bytes(out[i:i + 2], "big") for i in range(0, len(out), 2)], r["d0"] & 0xFFFF

    def test_logged_passes(self):
        """Log mode: only the logged notes move; same as the reference, and
        the same notes as quantizing the whole take."""
        rnd = random.Random(21)
        st = {i: (12, "mpc", 58) for i in range(8)}
        stopped = 0
        for n in range(300):
            words, log = logged_pass(rnd, rnd.choice([4, 8, 16, 32]), rnd.choice([1, 2, 4]),
                                     rnd.choice([1, 2, 4, 8, 16]))
            with self.subTest(n=n):
                got, status = self.run_logged(words, st, log)
                evs = S.split(list(words))
                try:
                    S._logged(evs, st, log)
                    exp_status = 0
                except S._Fallback:
                    exp_status = 1
                exp = [w for ev in evs for w in ev]
                self.assertEqual(status, exp_status)
                stopped += status
                if status == 0:
                    self.assertEqual(got, exp)
                    self.assertEqual(sorted(S.notes(got)), sorted(S.notes(S.quantize_take(words, st))))
        self.assertLess(stopped, 30)

    def test_held_notes_follow_their_notes(self):
        """The OS's held-note records (0xFF8134 list, +6 = offset of the
        duration word in the take buffer) still point at the same notes
        after log-mode moves shuffle the take."""
        e = self.eps
        rnd = random.Random(8)
        st = {i: (12, "mpc", 58) for i in range(8)}
        BASE, BUF = TAKE - 0x1000, 0x1000 - 28          # take = base + buf + 28
        NODES = 0xFFCE80                                  # 3 records, 8 bytes each
        checked = 0
        for n in range(200):
            words, log = logged_pass(rnd, 16, 1, 6)
            evs = S.split(words)
            note_idx = [k for k, ev in enumerate(evs) if S.is_note(ev)]
            held = rnd.sample(note_idx, 3)
            for j, k in enumerate(held):                  # unique velocities
                evs[k][2] = evs[k][2] & 0xF80F | (0x71 + j) << 4
            words = [w for ev in evs for w in ev]
            offs = [sum(len(ev) for ev in evs[:k]) * 2 + 2 for k in held]
            e.wl(0xFF8104, BASE)
            e.wl(0xFF8114, BUF)
            e.wl(0xFF8118, BUF + 0x10000)
            for j, off in enumerate(offs):                # +0 next, +6 offset
                a = NODES + 8 * j
                e.ww(a, (a + 8) & 0xFFFF if j < 2 else 0)
                e.ww(a + 6, off + 28)
            e.ww(0xFF8134, NODES & 0xFFFF)
            got, status = self.run_logged(words, st, log)
            e.ww(0xFF8134, 0)
            if status:
                continue
            for j in range(3):
                off = e.rw(NODES + 8 * j + 6) - 28
                w2 = got[off // 2 + 1]
                self.assertEqual((w2 >> 4) & 0x7F, 0x71 + j, f"take {n}, record {j}")
            checked += 1
        self.assertGreater(checked, 150)

    def test_small_scratch(self):
        """The fast path needs no scratch. When it has to stop and the full
        path has too little room, the take is left as the fast path left it
        (valid, partly quantized)."""
        rnd = random.Random(1)
        st = {0: (12, "mpc", 58)}
        seen_fallback = seen_fast = False
        for _ in range(40):
            w = random_take(rnd, 768)
            end = TAKE + 2 * len(w)
            got = self.run_asm(w, st, scratch_end=end + 16)
            fast = S.quantize_take_fast(w, st)
            if fast is not None:
                seen_fast = True
                self.assertEqual(got, fast)
            else:
                seen_fallback = True
                self.assertEqual(S.decode(got)[1], S.decode(w)[1])        # same length
                self.assertEqual(len(S.notes(got)), len(S.notes(w)))
        self.assertTrue(seen_fallback and seen_fast)


if __name__ == "__main__":
    unittest.main()
