#!/usr/bin/env python3
"""Build the resident mute-groups patch: everything in OS RAM, nothing in
sample RAM (13 bits wide on the hardware: no code can run there).

  mkresident.py OS.bin -o PATCH.json [--disk STOCK.hfe|STOCK.img OUT.hfe|OUT.img]

Edits to the OS file (src/lateinit.s, src/resmute.s):
  * 0xFF1770: the boot sequence's last call, "jsr 0x1EF4.w", calls the late
    init at 0xFFC994 instead (it goes on to 0x1EF4 itself),
  * carrier 1 at 0xFFC994: the late init, then table 1 (the mute code for
    0xFF1720, the hook at 0xFFAF92, the 6 Amp page record 0xFFC110), magic,
  * carrier 2 at 0xFFC8E8: table 2 (the index table at 0xFF86E6, our
    descriptor and label at 0xFF874C), magic.
docs/ANALYSIS.md -> Resident build.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import epstool  # noqa: E402
import mkhook  # noqa: E402

SRCDIR = os.path.join(os.path.dirname(__file__), "..", "src")
MAGIC = 0x4D555445                  # "MUTE"

CALL_SITE, CALL_STOCK = 0xFF1770, "4eb81ef4"
CARRIER1, CARRIER1_END = 0xFFC994, 0xFFCA30   # the boot's init stack reaches 0xFFCA3E
CARRIER2, CARRIER2_END = 0xFFC8E8, 0xFFC920   # interrupts reach 0xFFC92C
CODE_AT, CODE_END = 0xFF1720, 0xFF1770        # boot sequence (0xFF171E on), dead after it;
                                              # 4-aligned, or ld pads the start
INDEX_AT, INDEX_END = 0xFF86E6, 0xFF870A      # boot routine (0xFF870A is used later)
DESC_AT, DESC_END = 0xFF874C, 0xFF8766        # boot routine
HOOK_AT, HOOK_STOCK = 0xFFAF92, "303816be"    # move.w 0x16BE.w,d0
PAGE_REC, PAGE_STOCK = 0xFFC110, "25622570256206002570"   # 6 Amp: first, last, current, page, end
AMP_DESCS = [0x2748, 0x2750, 0x2758, 0x2760, 0x2768, 0x2770, 0x2778, 0x2780]  # ROM 0xC02562 on
WS_GROUP = 0x11E
CHOKE_DEFAULT = 2       # the cut's fade: 2 ticks of 12 ms (src/resmute.s CHOKE_RATE)


def w(v):
    return v.to_bytes(2, "big")


def chunk(dest, data):
    if len(data) % 2 or not data:
        raise ValueError("chunks are an even number of bytes")
    return w(dest & 0xFFFF) + w(len(data) - 1) + bytes(data)


def payload(choke=CHOKE_DEFAULT):
    """{name: (address, bytes)} of what goes into OS RAM at the end of boot."""
    code, syms = mkhook.assemble(os.path.join(SRCDIR, "resmute.s"), CODE_AT, "mute",
                                 {"CHOKE_RATE": choke})
    if syms["mute"] != CODE_AT:
        raise ValueError(f"mute code starts at {syms['mute']:#x}, not {CODE_AT:#x}")
    if syms["mute_end"] > CODE_END or len(code) % 2:
        raise ValueError(f"mute code ends at {syms['mute_end']:#x}, past {CODE_END:#x}")
    index = b"".join(w(d) for d in AMP_DESCS) + w(DESC_AT & 0xFFFF)
    label = b"MUTE GROUP\0"
    label += b"\0" * (len(label) % 2)
    desc = bytes([0x08, 0x00]) + w(15) + w(WS_GROUP) + w((DESC_AT + 8) & 0xFFFF) + label
    first, last = INDEX_AT & 0xFFFF, (INDEX_AT + 2 * len(AMP_DESCS)) & 0xFFFF
    rec = w(first) + w(last) + w(first) + w(0x0600) + w(last)
    out = {"code": (CODE_AT, bytes(code)), "index": (INDEX_AT, index), "desc": (DESC_AT, desc),
           "hook": (HOOK_AT, bytes.fromhex("4eb8") + w(CODE_AT & 0xFFFF)), "page": (PAGE_REC, rec)}
    for name, end in (("index", INDEX_END), ("desc", DESC_END)):
        a, d = out[name]
        if a + len(d) > end:
            raise ValueError(f"{name} ends at {a + len(d):#x}, past {end:#x}")
    return out


def build(os_bin, choke=CHOKE_DEFAULT):
    if not 0 <= choke <= 99:
        raise ValueError("--choke: 0-99")
    p = payload(choke)
    table2 = chunk(*p["index"]) + chunk(*p["desc"]) + w(0)
    table1 = chunk(*p["code"]) + chunk(*p["hook"]) + chunk(*p["page"]) + w(0)
    defs = {"TABLE2": CARRIER2 & 0xFFFF, "MAGIC": MAGIC, "MAGIC1_AT": 0, "MAGIC2_AT": 0}
    late, syms = mkhook.assemble(os.path.join(SRCDIR, "lateinit.s"), CARRIER1, "late", defs)
    magic1 = CARRIER1 + len(late) + len(table1)
    magic2 = CARRIER2 + len(table2)
    defs.update(MAGIC1_AT=magic1 & 0xFFFF, MAGIC2_AT=magic2 & 0xFFFF)
    late, syms = mkhook.assemble(os.path.join(SRCDIR, "lateinit.s"), CARRIER1, "late", defs)
    if syms["table1"] != CARRIER1 + len(late):
        raise ValueError("table 1 must follow the late init")
    c1 = bytes(late) + table1 + MAGIC.to_bytes(4, "big")
    c2 = table2 + MAGIC.to_bytes(4, "big")
    if CARRIER1 + len(c1) > CARRIER1_END:
        raise ValueError(f"carrier 1 ends at {CARRIER1 + len(c1):#x}, past {CARRIER1_END:#x}")
    if CARRIER2 + len(c2) > CARRIER2_END:
        raise ValueError(f"carrier 2 ends at {CARRIER2 + len(c2):#x}, past {CARRIER2_END:#x}")

    def at(a, n):
        o = epstool.addr_to_offset(a)
        return os_bin[o:o + n]
    for a, stock in ((HOOK_AT, HOOK_STOCK), (PAGE_REC, PAGE_STOCK), (CALL_SITE, CALL_STOCK)):
        if at(a, len(stock) // 2).hex() != stock:
            raise ValueError(f"{a:#x} is not stock OS 2.49")
    for a, d in ((CARRIER1, c1), (CARRIER2, c2)):
        if any(at(a, len(d))):
            raise ValueError(f"carrier at {a:#x} is not zero in this OS")
    patch = {"name": "resident-mute", "edits": [
        {"addr": f"0x{CALL_SITE:06X}", "expect": CALL_STOCK,
         "data": "4eb8" + w(CARRIER1 & 0xFFFF).hex()},
        {"addr": f"0x{CARRIER1:06X}", "expect": "00" * len(c1), "data": c1.hex()},
        {"addr": f"0x{CARRIER2:06X}", "expect": "00" * len(c2), "data": c2.hex()},
    ]}
    info = {"payload": p, "carrier1": (CARRIER1, len(c1)), "carrier2": (CARRIER2, len(c2)),
            "late": syms}
    return patch, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("os")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--disk", nargs=2, metavar=("STOCK", "OUT"))
    ap.add_argument("--choke", type=int, default=CHOKE_DEFAULT,
                    help=f"the cut's fade: envelope time 0-99 (default {CHOKE_DEFAULT})")
    a = ap.parse_args()
    patch, info = build(open(a.os, "rb").read(), a.choke)
    json.dump(patch, open(a.out, "w"), indent=1)
    (s1, n1), (s2, n2) = info["carrier1"], info["carrier2"]
    print(f"{a.out}: carrier 1 {s1:#x}-{s1 + n1 - 1:#x} ({n1} of {CARRIER1_END - s1}), "
          f"carrier 2 {s2:#x}-{s2 + n2 - 1:#x} ({n2} of {CARRIER2_END - s2}), "
          f"mute code {len(info['payload']['code'][1])} bytes")
    if a.disk:
        stock, out = a.disk
        img = epstool.load_image(stock)
        new_os = epstool.apply_patch(epstool.read_file(img, epstool.get_entry(img, 0)), patch)
        epstool.replace_file(img, 0, new_os)
        epstool.save_image(img, out, open(stock, "rb").read())
        print(f"{out}: disk written")


if __name__ == "__main__":
    main()
