#!/usr/bin/env python3
"""Run EPS OS code in a 68000 emulator (Unicorn) for tests.

This is not a machine emulator: there is no floppy, display or keyboard, and
hardware registers are plain RAM. It loads the boot ROM and the OS the way
the EPS lays them out, so we can call real OS routines (and our hooks) with
prepared memory and check the result.

Memory:
  0x000000-0x00FFFF  mirror of OS RAM (the OS runs in user mode, where
                     MAME's lower_r maps this range to OS RAM)
  0x200000           DOC II, 0x240000 DMAC, 0x280000 DUART, 0x2C0000 FDC:
                     plain RAM so register writes don't fault
  0x580000-0x67FFFF  sample RAM (1 MB)
  0xC00000-0xC0FFFF  boot ROM
  0xFF0000-0xFFFFFF  OS RAM; resident OS at 0xFF2000, overlay at 0xFFE000
                     (also at 0xFFFF0000: Unicorn has a 32-bit bus, the 68000
                     only 24 lines)

Usage:
    eps = EPS("build/bootrom/eps_boot_200.bin", "build/eps_os_249.bin", overlay=0)
    eps.call(0xFFB7C2, a4=0xFF0940)
"""
import ctypes
import os
import sys

from unicorn import Uc, UcError, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn import UC_HOOK_INTR
from unicorn.m68k_const import UC_CPU_M68K_M68000, UC_M68K_REG_PC, UC_M68K_REG_SR
from unicorn.m68k_const import (UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_D2,
                                UC_M68K_REG_D3, UC_M68K_REG_D4, UC_M68K_REG_D5,
                                UC_M68K_REG_D6, UC_M68K_REG_D7, UC_M68K_REG_A0,
                                UC_M68K_REG_A1, UC_M68K_REG_A2, UC_M68K_REG_A3,
                                UC_M68K_REG_A4, UC_M68K_REG_A5, UC_M68K_REG_A6,
                                UC_M68K_REG_A7)

sys.path.insert(0, os.path.dirname(__file__))
import epstool  # noqa: E402

REGS = {
    "d0": UC_M68K_REG_D0, "d1": UC_M68K_REG_D1, "d2": UC_M68K_REG_D2,
    "d3": UC_M68K_REG_D3, "d4": UC_M68K_REG_D4, "d5": UC_M68K_REG_D5,
    "d6": UC_M68K_REG_D6, "d7": UC_M68K_REG_D7, "a0": UC_M68K_REG_A0,
    "a1": UC_M68K_REG_A1, "a2": UC_M68K_REG_A2, "a3": UC_M68K_REG_A3,
    "a4": UC_M68K_REG_A4, "a5": UC_M68K_REG_A5, "a6": UC_M68K_REG_A6,
    "sp": UC_M68K_REG_A7,
}
RAM_BASE = 0xFF0000
ROM_BASE = 0xC00000
SAMPLE_BASE = 0x580000
STOP = 0x100000          # return address that ends a call()
STACK_TOP = 0xFFDF7C     # just under the OS stack area (0xFFDF80-0xFFDFFF)


class EmuError(Exception):
    pass


class EPS:
    def __init__(self, rom_path, os_path, overlay=None):
        self.uc = uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        uc.ctl_set_cpu_model(UC_CPU_M68K_M68000)
        # One host buffer for OS RAM, mapped twice (0xFF0000 and the mirror at 0).
        self._ram = ctypes.create_string_buffer(0x10000)
        uc.mem_map_ptr(RAM_BASE, 0x10000, 7, ctypes.addressof(self._ram))
        uc.mem_map_ptr(0x000000, 0x10000, 7, ctypes.addressof(self._ram))
        # The 68000 drives only 24 address lines, so abs.w addresses that the
        # CPU sign-extends to 0xFFFFxxxx land in OS RAM too.
        uc.mem_map_ptr(0xFFFF0000, 0x10000, 7, ctypes.addressof(self._ram))
        uc.mem_map(ROM_BASE, 0x20000, 5)
        for io in (0x200000, 0x240000, 0x280000, 0x2C0000, 0x300000):
            uc.mem_map(io, 0x1000, 3)
        uc.mem_map(SAMPLE_BASE, 0x100000, 7)
        uc.mem_map(STOP, 0x1000, 7)

        self.os = bytearray(open(os_path, "rb").read())
        uc.mem_write(ROM_BASE, open(rom_path, "rb").read())
        uc.mem_write(epstool.OS_LOAD_ADDR, bytes(self.os[:epstool.OVERLAY_FILE_BASE]))
        if overlay is not None:
            self.load_overlay(overlay)
        self._stubs = {}
        self._watch = set()
        self.calls = []      # (address, regs) for every stub hit
        uc.hook_add(UC_HOOK_CODE, self._on_code)
        uc.hook_add(UC_HOOK_INTR, self._on_intr)

    # ------------------------------------------------------------ memory
    def load_overlay(self, n):
        off = epstool.OVERLAY_FILE_BASE + n * epstool.OVERLAY_SIZE
        self.write(epstool.OVERLAY_WINDOW, bytes(self.os[off:off + epstool.OVERLAY_SIZE]))

    def apply_patch(self, patch):
        """Apply an epstool patch dict to memory (after checking 'expect')."""
        for e in patch["edits"]:
            addr = int(e["addr"], 16)
            data = bytes.fromhex(e["data"])
            if "expect" in e and addr >= RAM_BASE:
                have = self.read(addr, len(data)).hex()
                if have != e["expect"].lower():
                    raise EmuError(f"patch expect mismatch at {addr:#x}: {have}")
            self.write(addr, data)

    def read(self, addr, n):
        return bytes(self.uc.mem_read(addr, n))

    def write(self, addr, data):
        self.uc.mem_write(addr, bytes(data))

    def rw(self, addr):
        return int.from_bytes(self.read(addr, 2), "big")

    def rl(self, addr):
        return int.from_bytes(self.read(addr, 4), "big")

    def rb(self, addr):
        return self.read(addr, 1)[0]

    def ww(self, addr, v):
        self.write(addr, (v & 0xFFFF).to_bytes(2, "big"))

    def wl(self, addr, v):
        self.write(addr, (v & 0xFFFFFFFF).to_bytes(4, "big"))

    def wb(self, addr, v):
        self.write(addr, bytes([v & 0xFF]))

    # ------------------------------------------------------------ registers
    def reg(self, name):
        return self.uc.reg_read(REGS[name])

    def set_reg(self, name, value):
        self.uc.reg_write(REGS[name], value & 0xFFFFFFFF)

    def regs(self):
        return {r: self.reg(r) for r in REGS}

    # ------------------------------------------------------------ execution
    def stub(self, addr, fn=None):
        """Replace the routine at addr: record the call, run fn(eps), return."""
        self._stubs[addr] = fn

    def watch(self, addr):
        """Record (addr, regs) in self.calls each time addr executes."""
        self._watch.add(addr)

    def _on_code(self, uc, addr, size, _):
        addr &= 0xFFFFFF                 # 24-bit bus: 0xFFFFxxxx is 0xFFxxxx
        if addr in self._watch:
            self.calls.append((addr, self.regs()))
        if addr in self._stubs:
            self.calls.append((addr, self.regs()))
            fn = self._stubs[addr]
            if fn:
                fn(self)
            sp = self.reg("sp")
            uc.reg_write(UC_M68K_REG_PC, self.rl(sp))
            self.set_reg("sp", sp + 4)

    def _on_intr(self, uc, intno, _):
        pc = uc.reg_read(UC_M68K_REG_PC)
        raise EmuError(f"CPU exception {intno} at pc={pc:#x}")

    def run_until(self, start, until, max_insns=100_000, **regs):
        """Execute from start until pc == until (for checking code fragments)."""
        self.uc.reg_write(UC_M68K_REG_SR, 0x0000)
        regs.setdefault("sp", STACK_TOP)
        for r, v in regs.items():
            self.set_reg(r, v)
        try:
            self.uc.emu_start(start, until, count=max_insns)
        except UcError as e:
            pc = self.uc.reg_read(UC_M68K_REG_PC)
            raise EmuError(f"{e} at pc={pc:#x}") from None
        pc = self.uc.reg_read(UC_M68K_REG_PC)
        if pc != until:
            raise EmuError(f"stopped at pc={pc:#x}, expected {until:#x}")
        return self.regs()

    def call(self, addr, max_insns=1_000_000, **regs):
        """Call addr like 'jsr addr' with the given registers; return regs."""
        sp = regs.pop("sp", STACK_TOP)
        self.uc.reg_write(UC_M68K_REG_SR, 0x0000)   # user mode, like the OS
        for r, v in regs.items():
            self.set_reg(r, v)
        sp -= 4
        self.wl(sp, STOP)
        self.set_reg("sp", sp)
        try:
            self.uc.emu_start(addr, STOP, count=max_insns)
        except UcError as e:
            pc = self.uc.reg_read(UC_M68K_REG_PC)
            raise EmuError(f"{e} at pc={pc:#x}") from None
        pc = self.uc.reg_read(UC_M68K_REG_PC)
        if pc != STOP:
            raise EmuError(f"did not return (pc={pc:#x} after {max_insns} instructions)")
        if self.reg("sp") != sp + 4:
            raise EmuError(f"stack unbalanced: sp={self.reg('sp'):#x}, expected {sp + 4:#x}")
        return self.regs()
