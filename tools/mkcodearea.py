#!/usr/bin/env python3
"""Build the code-area patch (src/codearea.s): installer + payload in sample RAM.

  mkcodearea.py OS.bin -o PATCH.json [--groups SPEC]
                [--disk STOCK.ede|STOCK.hfe OUT.img|OUT.ede|OUT.hfe]

The patch has two edits: the staging bytes at STAGE (zeros in the stock OS)
and the boot trampoline at 0xFF832E, which now jumps to the installer. The
installer itself writes the hook jsr's at boot (see src/codearea.s).

--groups sets mute groups per key, comma separated:
    I=G          every key of instrument I (1-8) in group G (0 = none, 1-15)
    I:K=G        one key (MIDI number 21-108, or a name like C2, F#3, Bb1;
                 C4 = 60)
    I:K1-K2=G    a key range
  Later items override earlier ones. Example, a kit on instrument 1 with
  kick (C2) and snare (D2) cutting each other and hats in their own group:
    --groups 1:C2=1,1:D2=1,1:F#2-A#2=2
  The old form "1,1,2,0,0,0,0,0" (one group per instrument) still works.
"""
import re
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


KEY_LO, NKEYS = 21, 88
NOTES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def key_number(text):
    """MIDI note number from '36' or a name like 'C2', 'F#3', 'Bb1' (C4 = 60)."""
    text = text.strip()
    if text.isdigit():
        k = int(text)
    else:
        m = re.fullmatch(r"([A-Ga-g])([#b]?)(-?\d)", text)
        if not m:
            raise ValueError(f"bad key {text!r}")
        k = NOTES[m.group(1).upper()] + {"#": 1, "b": -1, "": 0}[m.group(2)] \
            + 12 * (int(m.group(3)) + 1)
    if not KEY_LO <= k < KEY_LO + NKEYS:
        raise ValueError(f"key {text!r} = {k} is outside 21-108 (A0-C8)")
    return k


def parse_groups(spec):
    """--groups SPEC -> {(instrument 0-7, key 21-108): group}."""
    groups = {}
    spec = (spec or "").strip()
    if not spec:
        return groups
    items = [x.strip() for x in spec.split(",")]
    if all(x.isdigit() for x in items):                     # old per-instrument form
        if len(items) != 8:
            raise ValueError("per-instrument form needs 8 numbers")
        items = [f"{i + 1}={g}" for i, g in enumerate(items)]
    for item in items:
        m = re.fullmatch(r"(\d)(?::([^=-]+)(?:-([^=]+))?)?=(\d+)", item)
        if not m:
            raise ValueError(f"bad --groups item {item!r}")
        inst, lo, hi, g = int(m.group(1)) - 1, m.group(2), m.group(3), int(m.group(4))
        if not 0 <= inst < 8 or not 0 <= g <= 15:
            raise ValueError(f"{item!r}: instrument 1-8, group 0-15")
        lo = key_number(lo) if lo else KEY_LO
        hi = key_number(hi) if hi else (lo if m.group(2) else KEY_LO + NKEYS - 1)
        for k in range(min(lo, hi), max(lo, hi) + 1):
            groups[(inst, k)] = g
    return groups


def group_table(groups):
    """The 352-byte table in src/mutegroup.s: 4 bits per (instrument, key)."""
    t = bytearray(8 * NKEYS // 2)
    for (inst, key), g in groups.items():
        i = inst * NKEYS + key - KEY_LO
        t[i // 2] |= g << 4 if i % 2 == 0 else g
    return bytes(t)


def build(os_bin, groups=""):
    code, syms = mkhook.assemble(SRC, STAGE, "install")
    if not isinstance(groups, dict):
        groups = parse_groups(groups)
    table = group_table(groups)
    off = syms["mute_table"] - STAGE
    code[off:off + len(table)] = table
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
    ap.add_argument("--groups", default="")
    ap.add_argument("--disk", nargs=2, metavar=("STOCK", "OUT"))
    a = ap.parse_args()
    os_bin = open(a.os, "rb").read()
    groups = parse_groups(a.groups)
    patch, info = build(os_bin, groups)
    json.dump(patch, open(a.out, "w"), indent=1)
    used = sorted({g for g in groups.values() if g})
    print(f"{a.out}: {info['stage_bytes']} staging bytes, payload "
          f"{info['payload_bytes']}/{AREA_SIZE}, {sum(1 for g in groups.values() if g)} "
          f"keys in groups {used}")
    if a.disk:
        stock, out = a.disk
        img = epstool.load_image(stock)
        new_os = epstool.apply_patch(epstool.read_file(img, epstool.get_entry(img, 0)), patch)
        epstool.replace_file(img, 0, new_os)
        epstool.save_image(img, out, open(stock, "rb").read())
        print(f"{out}: disk written")


if __name__ == "__main__":
    main()
