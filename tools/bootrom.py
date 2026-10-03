#!/usr/bin/env python3
"""EPS boot ROM helper (2 x 27256 at 0xC00000, high byte = even addresses).

Subcommands
  join      HI.bin LO.bin OUT.bin  Interleave the two EPROM dumps into one image
  info      ROM.bin                Version word, CRCs, known ROM sets
  msg       ROM.bin NUM...         Decode display messages (NUM = hex)
  annotate  ROM.bin OS.dis         Append message text to disassembly lines
                                   whose immediate is a message number
  scan      ROM.bin OS.bin START END
                                   List words in an OS address range that are
                                   message numbers (command/page records)
  commands  ROM.bin OS.bin         Markdown table of the OS command records

Display messages: the OS passes a 16-bit "message number" (move.w #$14EB,a2;
jsr $23FC). It is the ROM offset of a NUL-terminated message. In a message a
byte < 0x20 starts a 2-byte big-endian reference to another message (so
0x069E = ref 0x0AD4 "WAVESAMPLE " + "INFORMATION"); other bytes are text.
The string layout is the same in boot ROM 2.00 and 2.40.
"""
import argparse
import re
import sys
import zlib

ROM_BASE = 0xC00000
OS_BASE = 0xFF2000
# Command records in OS 2.49: 14 bytes each, from CMD_TABLE while the message
# word is a valid message: handler.w, message.w, flags.w, 3 x button handler.w,
# 0. Handler words are absolute short addresses. The OS runs in user mode,
# where 0x000000-0x00FFFF mirrors OS RAM, so every handler is 0xFF0000 | word.
# Flags bits 15-12 = 8 + overlay number for handlers in the 0xFFE000 window.
CMD_TABLE = 0xFFC43C
CMD_SIZE = 14
KNOWN = {  # (crc32 hi, crc32 lo): name
    (0xD8747420, 0x382BEAC1): "boot ROM 2.00 (MAME 'eps': eps-h.bin / eps-l.bin)",
    (0x2492AEE1, 0x31B25DC2): "boot ROM 2.40 (version word 0x0228)",
}


def split(rom):
    return rom[0::2], rom[1::2]


def msg(rom, m, depth=0):
    """Decoded text of message m, or None if it isn't a clean message."""
    if depth > 8 or not 0x100 <= m < len(rom):
        return None
    out = []
    i = m
    while i < len(rom):
        b = rom[i]
        if b == 0:
            return "".join(out)
        if b < 0x20:
            sub = msg(rom, (b << 8) | rom[i + 1], depth + 1)
            if sub is None:
                return None
            out.append(sub)
            i += 2
        elif b < 0x7F:
            out.append(chr(b))
            i += 1
        else:
            return None
    return None


def is_msg(rom, m, strict=True):
    """Text if message number m decodes to a message. strict also wants a NUL
    or 0xFF before it (fewer false hits when scanning arbitrary words; ROM
    2.40 has other bytes there)."""
    if not 0x100 <= m < 0x2000 or (strict and rom[m - 1] not in (0x00, 0xFF)):
        return None
    t = msg(rom, m)
    return t if t and len(t.strip()) >= 2 else None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("join"); a.add_argument("hi"); a.add_argument("lo"); a.add_argument("out")
    a = sp.add_parser("info"); a.add_argument("rom")
    a = sp.add_parser("msg"); a.add_argument("rom"); a.add_argument("num", nargs="+")
    a = sp.add_parser("annotate"); a.add_argument("rom"); a.add_argument("dis")
    a = sp.add_parser("commands"); a.add_argument("rom"); a.add_argument("os")
    a = sp.add_parser("scan"); a.add_argument("rom"); a.add_argument("os")
    a.add_argument("start"); a.add_argument("end")
    args = ap.parse_args()

    if args.cmd == "join":
        hi, lo = open(args.hi, "rb").read(), open(args.lo, "rb").read()
        if len(hi) != len(lo):
            sys.exit("EPROM dumps differ in size")
        open(args.out, "wb").write(bytes(b for p in zip(hi, lo) for b in p))
        return

    rom = open(args.rom, "rb").read()
    if args.cmd == "info":
        hi, lo = split(rom)
        key = (zlib.crc32(hi), zlib.crc32(lo))
        print(f"size {len(rom)}  reset SSP {rom[0:4].hex()}  PC {rom[4:8].hex()}")
        print(f"version word @ {ROM_BASE + 0x134:#x}: {rom[0x134:0x136].hex()}")
        print(f"crc32 hi {key[0]:08x}  lo {key[1]:08x}  "
              f"-> {KNOWN.get(key, 'unknown ROM set')}")
    elif args.cmd == "msg":
        for n in args.num:
            m = int(n, 16)
            print(f"{m:04x}  {msg(rom, m)!r}")
    elif args.cmd == "annotate":
        imm = re.compile(r"#(\d+),%a[0-7]")
        for line in open(args.dis):
            line = line.rstrip("\n")
            m = imm.search(line)
            t = is_msg(rom, int(m.group(1))) if m else None
            print(f"{line}\t; \"{t}\"" if t else line)
    elif args.cmd == "commands":
        os_bin = open(args.os, "rb").read()

        def w(addr):
            return int.from_bytes(os_bin[addr - OS_BASE:addr - OS_BASE + 2], "big")

        print("| Record | Command | Msg | Handler | Overlay | Flags |")
        print("|---|---|---|---|---|---|")
        a = CMD_TABLE
        while is_msg(rom, w(a + 2), strict=False):
            h, m, f = w(a), w(a + 2), w(a + 4)
            handler = 0xFF0000 | h
            ovl = str((f >> 12) - 8) if f & 0x8000 and handler >= 0xFFE000 else ""
            print(f"| `{a:06X}` | {is_msg(rom, m, False).strip()} | `{m:04X}` | "
                  f"`{handler:06X}` | {ovl} | `{f:04X}` |")
            a += CMD_SIZE
    elif args.cmd == "scan":
        os_bin = open(args.os, "rb").read()
        start, end = int(args.start, 16), int(args.end, 16)
        for addr in range(start, end, 2):
            o = addr - OS_BASE
            m = int.from_bytes(os_bin[o:o + 2], "big")
            t = is_msg(rom, m)
            if t:
                print(f"{addr:06x}  {m:04x}  {t}")


if __name__ == "__main__":
    main()
