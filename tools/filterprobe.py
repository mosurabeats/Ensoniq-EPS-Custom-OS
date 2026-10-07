#!/usr/bin/env python3
"""Build test OS disks that force the sampling input-filter cutoff code.

Hardware (EPS schematics, see docs/ANALYSIS.md -> Sampling filter hardware):
the anti-aliasing filter is an XR-1008 switched-capacitor low-pass, always in
the signal path. Its clock is

    FCLK = 10 MHz / (2 * (17 - N))       N = 4-bit preset of a 74LS161

with N = {OP4, CA2, CA1, CA0}: OP4 is a DUART output (also the analog mux's
AN1 line), CA0-2 are the DOC II channel-address outputs. The XR-1008 cutoff is
FCLK / 50 (the boot ROM labels the stock settings 6.25 ... 20.0 KHZ, which is
exactly FCLK / 50 for N = 1 ... 12). Higher N = higher cutoff.

overlay 2 reads one table byte E per filter setting (boot ROM 0xC0704E:
29 2a 2b 2c 2d 2e 2f 38 39 3a 3b 3c, i.e. setting k -> N = k + 1) and uses
it for everything:

    FFE38E  1831 0000   move.b (a1,d0.w),d4   ; E = table[filter index]
            E & 7  -> DOC II reg 0x12 on the voice pages -> CA0-CA2
            E bit 4,5,6 -> OP4,OP5,OP6 = mux AN1,AN2,AN0 (FFE2F6)

The mux must stay on an audio input: Y4 (AN2=1, AN1=0, AN0=0) and Y6
(AN2=1, AN1=1, AN0=0) are both wired to the sampling input, which is how OP4
can double as the counter MSB. So each probe forces

    E = 0x28 | (N & 8) << 1 | (N & 7)

(bit 3 is set in every stock entry and nothing reads it) by replacing the
table read with "moveq #E,d4" + nop. N = 1-12 reproduce the stock entries.
MIC/LINE (0xFF0211 -> OP7) and everything else are untouched. N = 15 is the
widest setting the hardware can produce (50 kHz; the stock top is 20 kHz)
and is the filter OUT candidate. Sample white noise or cymbals at a LOW rate
with each disk and compare.

Usage: filterprobe.py STOCK.ede OUTDIR [N...]   (default 0-15)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import epstool  # noqa: E402

SITE = 0xFFE38E
OVERLAY = 2
EXPECT = "18310000"


def entry(n):
    return 0x28 | (n & 8) << 1 | (n & 7)


def fclk(n):
    return 10e6 / (2 * (17 - n))


def probe_patch(n):
    return {"name": f"filterprobe-N{n}", "edits": [
        {"addr": hex(SITE), "overlay": OVERLAY, "expect": EXPECT,
         "data": f"78{entry(n):02x}4e71"}]}


def main():
    src, outdir = sys.argv[1], sys.argv[2]
    codes = [int(x) for x in sys.argv[3:]] or list(range(16))
    os.makedirs(outdir, exist_ok=True)
    stock = open(src, "rb").read()
    img = epstool.load_image(src)
    os_bin = epstool.read_file(img, epstool.get_entry(img, 0))
    for n in codes:
        if not 0 <= n <= 15:
            sys.exit(f"N must be 0-15, got {n}")
        new_os = epstool.apply_patch(os_bin, probe_patch(n))
        out = bytearray(img)
        epstool.replace_file(out, 0, new_os)
        base = os.path.join(outdir, f"eps249_filterprobe_N{n:02d}")
        epstool.save_image(out, base + ".img")
        epstool.save_image(out, base + ".ede", stock if src.lower().endswith(".ede") else None)
        print(f"N={n:2d}  E={entry(n):#04x}  FCLK={fclk(n) / 1e3:7.1f} kHz  "
              f"cutoff={fclk(n) / 50e3:5.2f} kHz -> {base}.img/.ede")


if __name__ == "__main__":
    main()
