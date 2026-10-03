#!/usr/bin/env python3
"""Build test OS disks that force the sampling input-filter select lines.

When sampling is set up, overlay 2 builds the DUART output-port byte from the
filter table entry (boot ROM 0xC0704E[filter index]):

    FFE2F6  C03C 00F0   andi.b #$F0,d0   ; keep OP4-OP7 from the table
    FFE2FA  803C 0004   ori.b  #$04,d0   ; plus OP2
    ...                                  ; OP7 is then forced by 0xFF0211

Each probe replaces those 8 bytes with "moveq #(P<<4)|4,d0" + 3 nops, so the
filter-select lines take pattern P (OP4..OP7 = bits 0..3 of P) whatever the
cutoff setting says. The other part of the filter setting (bits sent to the
OTIS chip) is left alone. Sample the same bright source (white noise or
cymbals) at a LOW sample rate with each probe disk and compare. A pattern
that lets everything through (lots of aliasing) is a filter OUT candidate.

Usage: filterprobe.py STOCK.ede OUTDIR [patterns...]   (default 0-7)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import epstool  # noqa: E402

SITE = 0xFFE2F6
OVERLAY = 2
EXPECT = "c03c00f0803c0004"


def probe_patch(p):
    val = ((p << 4) | 4) & 0xFF
    return {"name": f"filterprobe-{p}", "edits": [
        {"addr": hex(SITE), "overlay": OVERLAY, "expect": EXPECT,
         "data": f"70{val:02x}4e714e714e71"}]}


def main():
    src, outdir = sys.argv[1], sys.argv[2]
    pats = [int(x) for x in sys.argv[3:]] or list(range(8))
    os.makedirs(outdir, exist_ok=True)
    stock = open(src, "rb").read()
    img = epstool.load_image(src)
    os_bin = epstool.read_file(img, epstool.get_entry(img, 0))
    for p in pats:
        new_os = epstool.apply_patch(os_bin, probe_patch(p))
        out = bytearray(img)
        epstool.replace_file(out, 0, new_os)
        for ext in ("img", "ede"):
            path = os.path.join(outdir, f"eps249_filterprobe_{p}.{ext}")
            epstool.save_image(out, path, stock if ext == "ede" else None)
        print(f"pattern {p}: OP4-OP7 = {p:04b} (LSB = OP4) -> {outdir}/eps249_filterprobe_{p}.img/.ede")


if __name__ == "__main__":
    main()
