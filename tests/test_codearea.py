"""Code area: the boot-time loader (src/loader.s) and image (src/codearea.s).

Simulates the OS entry's first call (jsr 0xFF832E: sample-memory sizing) on
a patched OS, on the real init stack, with the kernel's data above it and
garbage in sample RAM, for each memory config. The ROM's block read
(0xC0B55C) is stubbed to serve blocks of an OS disk (the OS file from block
15). Needs build/eps_os_249.bin and build/bootrom/eps_boot_200.bin.
"""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from emu import EPS  # noqa: E402
from unicorn.m68k_const import UC_M68K_REG_SR  # noqa: E402
import epstool  # noqa: E402
import mkcodearea  # noqa: E402

OS = os.path.join(ROOT, "build", "eps_os_249.bin")
ROM = os.path.join(ROOT, "build", "bootrom", "eps_boot_200.bin")
ROM240 = os.path.join(ROOT, "build", "bootrom", "eps_boot_240.bin")

TRAMPOLINE = 0xFF832E
ROM_READ = 0xC0B55C
ROM_SELECT, ROM_DESELECT = 0xC0A5E0, 0xC0A5F4
RD_BLOCK, RD_DEST, RD_ERROR = 0xFF0228, 0xFF022C, 0xFF02C8
HOOK_SITE, AFTER_SITE = 0xFFACA4, 0xFFACAC
VOICE_KILL = 0xFFB7C2
ACTIVE, RELEASE = 0xFF16E4, 0xFF16DC
VOICES, VSIZE = 0xFF0940, 154
BOUNDS = (0xFF165A, 0xFF165E, 0xFF1662, 0xFF166A, 0xFF166E, 0xFF1672, 0xFF1676)
PHYS_TOP = {"base": 0x600000, "2x": 0x680000, "4x": 0x800000}
ENTRY_SP = mkcodearea.INIT_STACK      # user stack at the OS entry (task table; MAME)
KERNEL = (ENTRY_SP, 0xFFCFF0)         # other tasks' stacks, task records, buffers
RESERVE = 0xEE
GROUPS = "1:C2=1,1:D2=1,2=1,5=2,8:C8=15"


def pattern(n, seed):
    return bytes((i * seed + 11) & 0xFF or 1 for i in range(n))


def boot(expander, patch=None, rom=ROM, disk_os=None, read_error_at=None):
    """Run the OS entry's first call. disk_os: the OS file on the disk the
    stubbed ROM read serves (default: the patched OS)."""
    eps = EPS(rom, OS, expander=expander)
    os_file = bytearray(open(OS, "rb").read())
    if patch:
        eps.apply_patch(patch)
        os_file = bytearray(epstool.apply_patch(bytes(os_file), patch))
    if disk_os is not None:
        os_file = disk_os
    eps.reads = []
    eps.read_srs = []

    def read_block(e):
        b, dest = e.rl(RD_BLOCK), e.rl(RD_DEST)
        e.reads.append((b, dest))
        e.read_srs.append(e.uc.reg_read(UC_M68K_REG_SR))
        if read_error_at is not None and len(e.reads) > read_error_at + 1:
            e.wb(RD_ERROR, 3)
            return
        e.wb(RD_ERROR, 0)
        off = (b - 15) * 512
        e.write(dest & 0xFFFFFF, bytes(os_file[off:off + 512]).ljust(512, b"\0"))
    eps.stub(ROM_READ, read_block)
    eps.stub(ROM_SELECT, lambda e: e.reads.append("select"))
    eps.stub(ROM_DESELECT, lambda e: e.reads.append("deselect"))
    eps.write(KERNEL[0], pattern(KERNEL[1] - KERNEL[0], 37))
    eps.write(mkcodearea.STACK_LO, bytes([RESERVE]) * (ENTRY_SP - mkcodearea.STACK_LO))
    top = PHYS_TOP[expander]
    eps.write(top - 0x4000, pattern(0x4000, 13))
    eps.call(TRAMPOLINE, sp=ENTRY_SP)     # what the OS entry (0xFF171E) does first
    return eps


@unittest.skipUnless(os.path.exists(OS) and os.path.exists(ROM), "needs OS and boot ROM in build/")
class CodeAreaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.os_bin = open(OS, "rb").read()
        cls.groups = mkcodearea.parse_groups(GROUPS)
        cls.patch, cls.info = mkcodearea.build(cls.os_bin, cls.groups)
        cls.area_size = cls.info["area_size"]
        cls.image = cls.info["image"]
        cls.off = cls.info["image_offsets"]

    def area(self, expander):
        return PHYS_TOP[expander] - self.area_size

    def test_install_on_every_memory_config(self):
        for exp in ("base", "2x", "4x"):
            with self.subTest(exp):
                stock, ours = boot(exp), boot(exp, self.patch)
                for a in BOUNDS:          # heap and saved copies shrink by the area
                    self.assertEqual(ours.rl(a), stock.rl(a) - self.area_size, hex(a))
                self.assertEqual(ours.rl(0xFF1656), stock.rl(0xFF1656))
                area = self.area(exp)
                self.assertEqual(ours.rl(0xFF165A) + 512, area)
                # the image was read from blocks 159.. into the area
                self.assertEqual(ours.reads[0], "select")       # drive on, then off
                self.assertEqual(ours.reads[-1], "deselect")
                self.assertEqual([b for b, _ in ours.reads[1:-1]],
                                 list(range(159, 159 + self.info["blocks"])))
                self.assertEqual(ours.reads[1][1], area)
                self.assertEqual(ours.read(area, len(self.image)), self.image)
                self.assertEqual(ours.read(area + self.off["mute_table"], mkcodearea.MUTE_TABLE_SIZE),
                                 mkcodearea.group_table(self.groups))
                jsr = bytes.fromhex("4eb9") + (area + self.off["mute_hook"]).to_bytes(4, "big")
                self.assertEqual(ours.read(HOOK_SITE, 8), jsr + bytes.fromhex("4e71"))
                self.assertEqual(ours.read(TRAMPOLINE - 4, 10).hex(),
                                 mkcodearea.TRAP10_STOCK + mkcodearea.TRAMPOLINE_STOCK)
                # read in supervisor mode with interrupts masked, like the boot ROM
                self.assertTrue(all(sr & 0x2700 == 0x2700 for sr in ours.read_srs))
                # back in the OS with the ROM's results for the smaller heap
                self.assertEqual(ours.reg("a0") & 0xFFFFFF, stock.reg("a0") & 0xFFFFFF)
                self.assertEqual(ours.reg("d0"), stock.reg("d0") - self.area_size)
                for r in ("d2", "d3", "d4", "d5", "d6", "d7", "a1", "a2", "a3", "a4", "a5", "a6"):
                    self.assertEqual(ours.reg(r), stock.reg(r), r)
                # the other tasks' stacks and the kernel's data untouched
                self.assertEqual(ours.read(KERNEL[0], KERNEL[1] - KERNEL[0]),
                                 pattern(KERNEL[1] - KERNEL[0], 37))

    def test_os_ram_matches_stock_except_bounds_hook_and_loader(self):
        for exp in ("2x", "4x"):
            with self.subTest(exp):
                stock, ours = boot(exp), boot(exp, self.patch)
                a, b = stock.read(0xFF0000, 0x10000), ours.read(0xFF0000, 0x10000)
                allowed = set(range(HOOK_SITE, HOOK_SITE + 8))
                for v in BOUNDS:
                    allowed |= set(range(v, v + 4))
                allowed |= set(range(mkcodearea.STAGE, ENTRY_SP))      # loader + stack
                allowed |= set(range(0xFF0228, 0xFF0230)) | {0xFF02C8}  # ROM disk variables
                diff = [0xFF0000 + i for i in range(0x10000) if a[i] != b[i]]
                self.assertEqual([hex(x) for x in diff if x not in allowed], [])

    def test_os_stack_use_before_the_switch(self):
        """Only the OS entry's jsr and the two ROM calls use the OS stack."""
        eps = boot("4x", self.patch)
        n = ENTRY_SP - mkcodearea.STACK_LO
        used = n - next(i for i, b in enumerate(eps.read(mkcodearea.STACK_LO, n)) if b != RESERVE)
        self.assertLessEqual(used, 20, f"OS stack used {used} of {n} bytes")
        self.assertLessEqual(self.info["install_end"], mkcodearea.STACK_LO)

    def test_read_error_boots_without_hooks(self):
        eps = boot("2x", self.patch, read_error_at=1)
        self.assertEqual(eps.reads[-1], "deselect")
        self.assertEqual(eps.read(HOOK_SITE, 8), bytes.fromhex("3005d040327cdf70"))
        self.assertEqual(eps.read(TRAMPOLINE, 6).hex(), mkcodearea.TRAMPOLINE_STOCK)
        self.assertEqual(eps.rl(0xFF165A) + 512, self.area("2x"))   # heap still shrunk

    def test_bad_image_boots_without_hooks(self):
        os_file = bytearray(epstool.apply_patch(self.os_bin, self.patch))
        os_file[0x12000 + 100] ^= 1                          # one bit flipped
        eps = boot("2x", self.patch, disk_os=os_file)
        self.assertEqual(eps.read(HOOK_SITE, 8), bytes.fromhex("3005d040327cdf70"))
        os_file = bytearray(self.os_bin)                     # a stock OS on the disk
        eps = boot("2x", self.patch, disk_os=os_file)
        self.assertEqual(eps.read(HOOK_SITE, 8), bytes.fromhex("3005d040327cdf70"))

    def test_image_checksum_and_slot(self):
        words = [int.from_bytes(self.image[i:i + 2], "big") for i in range(0, len(self.image), 2)]
        self.assertEqual(sum(words) & 0xFFFF, 0)
        self.assertEqual(self.image[:4], b"EPS!")
        with self.assertRaises(ValueError):              # overlay-3 slot already used
            mkcodearea.build(epstool.apply_patch(self.os_bin, self.patch), self.groups)

    def test_boot_rom_240(self):
        if not os.path.exists(ROM240):
            self.skipTest("needs build/bootrom/eps_boot_240.bin")
        ours = boot("2x", self.patch, rom=ROM240)
        self.assertEqual(ours.rl(0xFF165A) + 512, self.area("2x"))
        self.assertEqual(ours.read(HOOK_SITE, 2), bytes.fromhex("4eb9"))

    def test_hook_skipped_if_site_not_stock(self):
        eps = EPS(ROM, OS, expander="2x")
        eps.apply_patch(self.patch)
        os_file = epstool.apply_patch(self.os_bin, self.patch)
        eps.stub(ROM_READ, lambda e: (e.wb(RD_ERROR, 0), e.write(
            e.rl(RD_DEST) & 0xFFFFFF, os_file[(e.rl(RD_BLOCK) - 15) * 512:][:512])))
        eps.stub(ROM_SELECT)
        eps.stub(ROM_DESELECT)
        eps.write(HOOK_SITE, bytes.fromhex("4e714e714e714e71"))
        eps.call(TRAMPOLINE, sp=ENTRY_SP)
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
