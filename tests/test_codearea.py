"""Code area (src/codearea.s): boot-time install into the top of sample RAM.

Simulates the OS entry's first call (jsr 0xFF832E: sample memory sizing) on a
patched OS, for each memory config, and compares the result with a stock
boot. Needs build/eps_os_249.bin and build/bootrom/eps_boot_200.bin.
"""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from emu import EPS  # noqa: E402
import mkcodearea  # noqa: E402

OS = os.path.join(ROOT, "build", "eps_os_249.bin")
ROM = os.path.join(ROOT, "build", "bootrom", "eps_boot_200.bin")
ROM240 = os.path.join(ROOT, "build", "bootrom", "eps_boot_240.bin")

TRAMPOLINE = 0xFF832E
HOOK_SITE, AFTER_SITE = 0xFFACA4, 0xFFACAC
VOICE_KILL = 0xFFB7C2
ACTIVE, RELEASE = 0xFF16E4, 0xFF16DC
VOICES, VSIZE = 0xFF0940, 154
BOUNDS = (0xFF165A, 0xFF165E, 0xFF1662, 0xFF166A, 0xFF166E, 0xFF1672, 0xFF1676)
PHYS_TOP = {"base": 0x600000, "2x": 0x680000, "4x": 0x800000}
ENTRY_SP = mkcodearea.INIT_STACK   # user stack at the OS entry (task table; MAME)
RESERVE = 0xEE                # fill for the stack reserve, to see how deep it goes
KERNEL = (mkcodearea.STAGE_LIMIT, 0xFFCFF0)   # task records and message buffers the
                                              # boot ROM builds before the OS entry


def kernel_pattern():
    n = KERNEL[1] - KERNEL[0]
    return bytes((i * 37 + 11) & 0xFF or 1 for i in range(n))


def boot(expander, patch=None, rom=ROM):
    eps = EPS(rom, OS, expander=expander)
    if patch:
        eps.apply_patch(patch)
    # what MAME shows at the OS entry: kernel data above the staging bytes,
    # and garbage in sample RAM
    eps.write(KERNEL[0], kernel_pattern())
    eps.write(mkcodearea.STACK_LO, bytes([RESERVE]) * (ENTRY_SP - mkcodearea.STACK_LO))
    top = PHYS_TOP[expander]
    eps.write(top - 2048, bytes((i * 13 + 5) & 0xFF for i in range(2048)))
    eps.call(TRAMPOLINE, sp=ENTRY_SP)     # what the OS entry (0xFF171E) does first
    return eps


@unittest.skipUnless(os.path.exists(OS) and os.path.exists(ROM), "needs OS and boot ROM in build/")
class CodeAreaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.os_bin = open(OS, "rb").read()
        cls.groups = mkcodearea.parse_groups("1:C2=1,1:D2=1,2=1,5=2,8:C8=15")
        cls.patch, cls.info = mkcodearea.build(cls.os_bin, cls.groups)
        cls.code = bytes.fromhex(cls.patch["edits"][0]["data"])
        cls.off = cls.info["payload_offsets"]

    def area(self, expander):
        return PHYS_TOP[expander] - mkcodearea.AREA_SIZE

    def test_install_on_every_memory_config(self):
        for exp in ("base", "2x", "4x"):
            with self.subTest(exp):
                stock, ours = boot(exp), boot(exp, self.patch)
                # heap and saved copies are exactly AREA_SIZE smaller
                for a in BOUNDS:
                    self.assertEqual(ours.rl(a), stock.rl(a) - mkcodearea.AREA_SIZE, hex(a))
                self.assertEqual(ours.rl(0xFF1656), stock.rl(0xFF1656))
                # the area is the top 1 KB of physical sample RAM, above the system block
                area = self.area(exp)
                self.assertEqual(ours.rl(0xFF165A) + 512, area)
                n = self.info["payload_bytes"]
                p = self.info["payload"] - mkcodearea.STAGE
                payload = self.code[p:p + n]
                self.assertEqual(ours.read(area, n), payload)
                # the group table, built from the ranges over garbage
                self.assertEqual(ours.read(area + n, mkcodearea.MUTE_TABLE_SIZE),
                                 mkcodearea.group_table(self.groups))
                # kernel data above the staging bytes untouched
                self.assertEqual(ours.read(KERNEL[0], KERNEL[1] - KERNEL[0]), kernel_pattern())
                # hook site now calls mute_hook in the area
                jsr = bytes.fromhex("4eb9") + (area + self.off["mute_hook"]).to_bytes(4, "big")
                self.assertEqual(ours.read(HOOK_SITE, 8), jsr + bytes.fromhex("4e71"))
                # back in the OS with the ROM's results for the smaller heap
                self.assertEqual(ours.reg("a0") & 0xFFFFFF, stock.reg("a0") & 0xFFFFFF)
                self.assertEqual(ours.reg("d0"), stock.reg("d0") - mkcodearea.AREA_SIZE)

    def test_os_ram_matches_stock_except_bounds_and_hook(self):
        for exp in ("2x", "4x"):
            with self.subTest(exp):
                stock, ours = boot(exp), boot(exp, self.patch)
                a, b = stock.read(0xFF0000, 0x10000), ours.read(0xFF0000, 0x10000)
                allowed = set(range(HOOK_SITE, HOOK_SITE + 8))
                for v in BOUNDS:
                    allowed |= set(range(v, v + 4))
                allowed |= set(range(mkcodearea.STACK_LO, ENTRY_SP))   # stack reserve
                diff = [0xFF0000 + i for i in range(0x10000) if a[i] != b[i]]
                extra = [hex(x) for x in diff if x not in allowed]
                self.assertEqual(extra, [], "staging not cleared or other RAM changed")
                # heap header at the start of sample RAM matches the smaller heap
                s = ours.rl(0xFF1656)
                self.assertNotEqual(ours.rl(s), stock.rl(s))

    def test_staging_fits_below_kernel_data(self):
        self.assertLessEqual(mkcodearea.STAGE + self.info["stage_bytes"], mkcodearea.STAGE_LIMIT)
        self.assertLessEqual(self.info["install_end"], mkcodearea.STACK_LO)

    def test_stack_stays_in_the_reserve(self):
        """The init stack (0xFFCA84 down) must not reach the install code."""
        for exp in ("base", "4x"):
            with self.subTest(exp):
                eps = boot(exp, self.patch)
                n = ENTRY_SP - mkcodearea.STACK_LO
                used = n - next(i for i, b in enumerate(eps.read(mkcodearea.STACK_LO, n))
                                if b != RESERVE)
                self.assertLessEqual(used + 8, n, f"stack used {used} of {n} bytes")
        # one range per key in every instrument is far too many
        many = {(i, k): 1 + (k % 2) for i in range(8) for k in range(21, 109)}
        with self.assertRaises(ValueError):
            mkcodearea.build(self.os_bin, many)

    def test_ranges_build_the_table(self):
        import random
        rnd = random.Random(1)
        for _ in range(50):
            g = {(rnd.randrange(8), rnd.randrange(21, 109)): rnd.randrange(16) for _ in range(12)}
            g.update({(1, k): 3 for k in range(21, 109)})
            r = mkcodearea.group_ranges(g)
            t = bytearray(mkcodearea.MUTE_TABLE_SIZE)
            for j in range(0, len(r) - 2, 4):
                idx, n, grp = int.from_bytes(r[j:j + 2], "big"), r[j + 2] + 1, r[j + 3]
                for i in range(idx, idx + n):
                    t[i // 2] |= grp << 4 if i % 2 == 0 else grp
            self.assertEqual(bytes(t), mkcodearea.group_table(g))

    def test_boot_rom_240(self):
        if not os.path.exists(ROM240):
            self.skipTest("needs build/bootrom/eps_boot_240.bin")
        ours = boot("2x", self.patch, rom=ROM240)
        self.assertEqual(ours.rl(0xFF165A) + 512, self.area("2x"))

    def test_hook_skipped_if_site_not_stock(self):
        eps = EPS(ROM, OS, expander="2x")
        eps.apply_patch(self.patch)
        eps.write(HOOK_SITE, bytes.fromhex("4e714e714e714e71"))
        eps.call(TRAMPOLINE)
        self.assertEqual(eps.read(HOOK_SITE, 8), bytes.fromhex("4e714e714e714e71"))

    def test_mute_groups_through_installed_hook(self):
        """Note-on through the patched entry: groups choke, registers as stock."""
        def setup(eps):
            for i in range(8):                     # loaded instruments, no transpose
                rec = 0xFFCE00 + 0x40 * i
                eps.ww(0xFFDF70 + 2 * i, rec)
                eps.ww(rec, 0x1234)
                eps.wb(rec + 62, 0)
            eps.wb(0xFF16BB, 38)                   # incoming key D2
            vs = []
            for i, (inst, key) in enumerate([(0, 36), (1, 60), (4, 50), (4, 51), (2, 60), (0, 40)]):
                v = VOICES + i * VSIZE
                eps.wb(v + 4, key)
                eps.wb(v + 6, inst)
                eps.wb(v + 12, 4)
                vs.append(v)
            chain = [ACTIVE] + vs + [ACTIVE]
            for x, y in zip(chain, chain[1:]):
                eps.ww(x, y)
                eps.ww(y + 2, x)
            eps.ww(RELEASE, RELEASE)
            eps.ww(RELEASE + 2, RELEASE)
            return vs

        ours, stock = boot("2x", self.patch), boot("2x")
        vs, _ = setup(ours), setup(stock)
        ours.watch(VOICE_KILL)
        regs = {r: 0x1000 * i + i for i, r in enumerate(
            ("d0", "d1", "d2", "d3", "d4", "d5", "d6", "d7",
             "a0", "a1", "a2", "a3", "a4", "a5", "a6"))}
        regs["d5"] = 0                                             # instrument 1
        r1 = ours.run_until(HOOK_SITE, AFTER_SITE, **regs)       # inst 1, D2: group 1
        r2 = stock.run_until(HOOK_SITE, AFTER_SITE, **regs)
        self.assertEqual(r1, r2)
        killed = sorted(0xFF0000 | (r["a4"] & 0xFFFF) for a, r in ours.calls if a == VOICE_KILL)
        self.assertEqual(killed, [vs[0], vs[1]])     # inst 1 C2 and all of inst 2, not inst 1 E2


if __name__ == "__main__":
    unittest.main()
