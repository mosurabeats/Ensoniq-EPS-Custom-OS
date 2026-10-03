#!/usr/bin/env python3
"""Build the code-area patch (src/codearea.s): installer + payload in sample RAM.

  mkcodearea.py OS.bin -o PATCH.json [--groups 1,1,0,0,2,0,0,0]
                [--disk STOCK.ede|STOCK.hfe OUT.img|OUT.ede|OUT.hfe]

The patch has two edits: the staging bytes at STAGE (zeros in the stock OS)
and the boot trampoline at 0xFF832E, which now jumps to the installer. The
installer itself writes the hook jsr's at boot (see src/codearea.s).

--groups sets the mute group (0 = none, 1-8) of instruments 1-8.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import epstool  # noqa: E402
import mkhook  # noqa: E402

SRC = os.path.join(os.path.dirname(__file__), "..", "src", "codearea.s")
STAGE = 0xFFC994          # zeros in the stock OS up to 0xFFCFFC (runtime buffers)
STAGE_LIMIT = 0xFFCFFC
AREA_SIZE = 1024
TRAMPOLINE = 0xFF832E
TRAMPOLINE_STOCK = "4ef900c08490"


def build(os_bin, groups=(0,) * 8):
    code, syms = mkhook.assemble(SRC, STAGE, "install")
    if len(groups) != 8 or not all(0 <= g <= 8 for g in groups):
        raise ValueError("need 8 mute groups, each 0-8")
    off = syms["mute_table"] - STAGE
    code[off:off + 8] = bytes(groups)
    payload = syms["payload_end"] - syms["payload"]
    if STAGE + len(code) > STAGE_LIMIT:
        raise ValueError(f"staging overflow: {len(code)} bytes")
    if payload > AREA_SIZE:
        raise ValueError(f"payload is {payload} bytes, area is {AREA_SIZE}")
    so = epstool.addr_to_offset(STAGE)
    if any(os_bin[so:so + len(code)]):
        raise ValueError("staging bytes are not zero in this OS")
    to = epstool.addr_to_offset(TRAMPOLINE)
    if os_bin[to:to + 6].hex() != TRAMPOLINE_STOCK:
        raise ValueError("trampoline at 0xFF832E is not stock")
    patch = {"name": "codearea", "edits": [
        {"addr": f"0x{STAGE:06X}", "expect": "00" * len(code), "data": code.hex()},
        {"addr": f"0x{TRAMPOLINE:06X}", "expect": TRAMPOLINE_STOCK,
         "data": "4ef9" + STAGE.to_bytes(4, "big").hex()},
    ]}
    info = {"stage_bytes": len(code), "payload_bytes": payload,
            "payload_offsets": {k: v - syms["payload"] for k, v in syms.items()
                                if syms["payload"] <= v < syms["payload_end"]}}
    return patch, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("os")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--groups", default="0,0,0,0,0,0,0,0")
    ap.add_argument("--disk", nargs=2, metavar=("STOCK", "OUT"))
    a = ap.parse_args()
    os_bin = open(a.os, "rb").read()
    groups = [int(x) for x in a.groups.split(",")]
    patch, info = build(os_bin, groups)
    json.dump(patch, open(a.out, "w"), indent=1)
    print(f"{a.out}: {info['stage_bytes']} staging bytes, payload "
          f"{info['payload_bytes']}/{AREA_SIZE}, groups {groups}")
    if a.disk:
        stock, out = a.disk
        img = epstool.load_image(stock)
        new_os = epstool.apply_patch(epstool.read_file(img, epstool.get_entry(img, 0)), patch)
        epstool.replace_file(img, 0, new_os)
        epstool.save_image(img, out, open(stock, "rb").read())
        print(f"{out}: disk written")


if __name__ == "__main__":
    main()
