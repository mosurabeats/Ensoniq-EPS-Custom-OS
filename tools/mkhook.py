#!/usr/bin/env python3
"""Assemble a hook and emit an epstool patch JSON.

  mkhook.py SRC.s OS.bin --org ADDR --hook ADDR --len N --entry SYM \
            [--set SYM=HEX ...] -o PATCH.json

* SRC.s is assembled (m68k-linux-gnu-as/ld) and linked at --org (the code cave).
* At --hook, N bytes (N >= 6, even) are replaced by "jsr SYM.l" + nops; the
  hook routine must execute the displaced instructions itself.
* --set overwrites the bytes at a symbol (e.g. a table) after assembly.
* Every edit records the bytes currently in OS.bin as "expect", so the patch
  only applies to the exact OS it was built against.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
import epstool  # noqa: E402


def run(*cmd):
    subprocess.run(cmd, check=True)


def assemble(src, org, entry, defsyms=None):
    """Assemble src linked at org. Returns (code bytearray, {symbol: address}).
    defsyms: {name: int} passed to the assembler as --defsym."""
    with tempfile.TemporaryDirectory() as t:
        obj, elf, binf = (os.path.join(t, n) for n in ("h.o", "h.elf", "h.bin"))
        defs = [f"--defsym={k}={v}" for k, v in (defsyms or {}).items()]
        run("m68k-linux-gnu-as", "-m68000", "--register-prefix-optional", *defs,
            "-I", os.path.dirname(os.path.abspath(src)), "-o", obj, src)
        run("m68k-linux-gnu-ld", "-e", entry, f"-Ttext={org:#x}", "-o", elf, obj)
        run("m68k-linux-gnu-objcopy", "-O", "binary", elf, binf)
        syms = {}
        for line in subprocess.run(["m68k-linux-gnu-nm", elf], capture_output=True,
                                   text=True, check=True).stdout.splitlines():
            v, _, name = line.split()
            syms[name] = int(v, 16)
        with open(binf, "rb") as f:
            return bytearray(f.read()), syms


def hook_jsr(target, length):
    """'jsr target.l' padded with nops to length bytes."""
    if length < 6 or length % 2:
        raise ValueError("hook length must be even and >= 6")
    return bytes.fromhex("4EB9") + target.to_bytes(4, "big") + \
        bytes.fromhex("4E71") * ((length - 6) // 2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("src")
    p.add_argument("os")
    p.add_argument("--org", required=True)
    p.add_argument("--hook", required=True)
    p.add_argument("--len", type=int, required=True)
    p.add_argument("--entry", required=True)
    p.add_argument("--set", action="append", default=[])
    p.add_argument("-o", "--out", required=True)
    a = p.parse_args()

    org, hook = int(a.org, 16), int(a.hook, 16)
    if a.len < 6 or a.len % 2:
        sys.exit("--len must be even and >= 6")
    code, syms = assemble(a.src, org, a.entry)

    for s in a.set:
        name, hexval = s.split("=")
        val = bytes.fromhex(hexval)
        off = syms[name] - org
        code[off:off + len(val)] = val

    osb = open(a.os, "rb").read()

    def cur(addr, n):
        off = epstool.addr_to_offset(addr)
        return osb[off:off + n].hex()

    jsr = hook_jsr(syms[a.entry], a.len)
    patch = {
        "name": os.path.splitext(os.path.basename(a.src))[0],
        "edits": [
            {"addr": f"0x{org:06X}", "expect": cur(org, len(code)), "data": code.hex()},
            {"addr": f"0x{hook:06X}", "expect": cur(hook, a.len), "data": jsr.hex()},
        ],
    }
    json.dump(patch, open(a.out, "w"), indent=1)
    print(f"{a.out}: {len(code)} bytes at {org:#x}, hook at {hook:#x}")


if __name__ == "__main__":
    main()
