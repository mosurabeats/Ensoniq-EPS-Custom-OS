#!/usr/bin/env python3
"""Build the code-area patch: our resident code in the top of sample RAM.

  mkcodearea.py OS.bin -o PATCH.json [--groups SPEC] [--swing SPEC] [--undo]
                [--auto-keep] [--area BYTES]
                [--disk STOCK.ede|STOCK.hfe OUT.img|OUT.ede|OUT.hfe]

The patch has three edits to the OS file:
  * the loader (src/loader.s) in a zero run at 0xFFC994,
  * the boot trampoline at 0xFF832E, which now jumps to the loader,
  * the code image (src/codearea.s) in the empty overlay-3 slot (disk
    blocks 159-174), which the loader reads into the code area at boot.
The loader writes the hook jsr's at boot.

--groups sets mute groups per key, comma separated:
    I=G          every key of instrument I (1-8) in group G (0 = none, 1-15)
    I:K=G        one key (MIDI number 21-108, or a name like C2, F#3, Bb1;
                 C4 = 60)
    I:K1-K2=G    a key range
  Later items override earlier ones. Example, a kit on instrument 1 with
  kick (C2) and snare (D2) cutting each other and hats in their own group:
    --groups 1:C2=1,1:D2=1,1:F#2-A#2=2
  The old form "1,1,2,0,0,0,0,0" (one group per instrument) still works.

--swing quantizes LOOPED takes at every wrap (see --help). --undo, or
--swing, adds loop undo: RECORD pressed while loop recording takes out the
notes played so far in this pass, or if there are none the last pass's.
"""
import re
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import epstool  # noqa: E402
import mkhook  # noqa: E402
import swing  # noqa: E402

SRCDIR = os.path.join(os.path.dirname(__file__), "..", "src")
LOADER_SRC = os.path.join(SRCDIR, "loader.s")
IMAGE_SRC = os.path.join(SRCDIR, "codearea.s")
STAGE = 0xFFC994          # bottom of the init task's stack, zeros in the stock OS
STACK_LO = 0xFFCA64       # the loader ends here: the OS stack (0xFFCA84 down) is
                          # used above it until the loader switches stacks
INIT_STACK = 0xFFCA84
AREA_SIZE = 4096          # default code area (top of sample RAM)
OVERLAY_WINDOW = 0xFFE000
IMAGE_BLOCK = 159         # overlay 3's slot in the OS file (file offset 0x12000)
IMAGE_MAX_BLOCKS = 16
TRAMPOLINE = 0xFF832E
TRAMPOLINE_STOCK = "4ef900c08490"
TRAP10_STOCK = "4ef895d8"     # 0xFF832A: trap #10's target, borrowed by the loader


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


MUTE_TABLE_SIZE = 8 * NKEYS // 2

GRID_NAMES = {"4": 48, "4T": 32, "8": 24, "8T": 16, "16": 12, "16T": 8, "32": 6, "32T": 4}


def parse_one_swing(text):
    """'16:mpc:58' / '8:sp1200:63' (or setting 0-5) / 'off' -> (grid, style,
    amount) or None."""
    text = text.strip()
    if text.lower() == "off":
        return None
    parts = text.split(":")
    grid = GRID_NAMES.get(parts[0].upper().replace("1/", ""))
    if grid is None:
        raise ValueError(f"bad grid {parts[0]!r} (4, 4T, 8, 8T, 16, 16T, 32, 32T)")
    style = parts[1].lower() if len(parts) > 1 else "mpc"
    amount = int(parts[2]) if len(parts) > 2 else (50 if style == "mpc" else 0)
    if style == "sp1200" and amount in swing.SP1200_LABELS:
        amount = swing.SP1200_LABELS.index(amount)
    swing.swing_fraction(style, amount)          # validates
    return grid, style, amount


def parse_swing(spec):
    """--swing SPEC -> {instrument 0-7: (grid, style, amount)}.
    'G:STYLE:AMOUNT' for every instrument, or 'I=G:STYLE:AMOUNT,...'."""
    spec = (spec or "").strip()
    if not spec:
        return {}
    if "=" not in spec:
        one = parse_one_swing(spec)
        return {i: one for i in range(8)} if one else {}
    out = {}
    for item in spec.split(","):
        inst, setting = item.split("=", 1)
        i = int(inst) - 1
        if not 0 <= i < 8:
            raise ValueError(f"instrument {inst} (1-8)")
        one = parse_one_swing(setting)
        if one:
            out[i] = one
        else:
            out.pop(i, None)
    return out


def swing_table(settings):
    """swing_settings in src/looprec.s: 8 x (grid.w, offset.w)."""
    t = bytearray(32)
    for i, (grid, style, amount) in settings.items():
        t[4 * i:4 * i + 4] = grid.to_bytes(2, "big") + swing.offset(style, amount, grid).to_bytes(2, "big")
    return bytes(t)


def build_image(groups, swing_settings=None, undo=False, pages=False):
    """Stage 2 (src/codearea.s) at offset 0, mute table (and swing table)
    filled in and the checksum set so all words sum to 0. The loop-record
    code (src/looprec.s: swing and undo) is in it with swing settings or
    undo. Returns (bytes, symbols)."""
    looprec = bool(swing_settings) or undo
    code, syms = mkhook.assemble(IMAGE_SRC, 0, "image", {"LOOPREC": 1 if looprec else 0,
                                                          "PAGES": 1 if pages else 0})
    if pages and syms["pages_end"] > 0x1000:
        raise ValueError("src/pages.s tables must be in the image's first 4 KB")
    table = group_table(groups)
    off = syms["mute_table"]
    code[off:off + len(table)] = table
    if swing_settings:
        st = swing_table(swing_settings)
        off = syms["swing_settings"]
        code[off:off + len(st)] = st
    if len(code) != syms["image_end"] or len(code) % 2:
        raise ValueError("image length mismatch")
    total = sum(int.from_bytes(code[i:i + 2], "big") for i in range(0, len(code), 2))
    code[syms["checksum"]:syms["checksum"] + 2] = ((-total) & 0xFFFF).to_bytes(2, "big")
    return bytes(code), syms


# KEEP = OLD NEW prompt after recording over a track (UI code at 0xFF2702):
# it shows the prompt (0xFFA4EC) and waits for a button; NEW stores 1 in
# 0xFF815E and continues at 0xFF2652. Auto-keep does exactly that without
# asking: "move.b #1,0x815E.w; bra.w 0xFF2652" over the first 10 bytes.
AUTO_KEEP = {"addr": "0xFF2702", "expect": "31fc0002c2ec0c380000",
             "data": "11fc0001815e" + "6000" + ((0xFF2652 - 0xFF270A) & 0xFFFF).to_bytes(2, "big").hex()}


def build(os_bin, groups="", area_size=None, auto_keep=False, swing_settings=None, undo=False,
          pages=False):
    if not isinstance(groups, dict):
        groups = parse_groups(groups)
    if isinstance(swing_settings, str):
        swing_settings = parse_swing(swing_settings)
    image, isyms = build_image(groups, swing_settings, undo, pages)
    blocks = (len(image) + 511) // 512
    if blocks > IMAGE_MAX_BLOCKS:
        raise ValueError(f"image is {len(image)} bytes, the overlay-3 slot holds "
                         f"{IMAGE_MAX_BLOCKS * 512}")
    # whole blocks are read into the area, with the loader's stack above them
    area = max(area_size or AREA_SIZE, blocks * 512 + 512)
    if area % 512:
        raise ValueError("area size must be a multiple of 512")
    loader, syms = mkhook.assemble(LOADER_SRC, STAGE, "install", {
        "STAGE2_BLOCK": IMAGE_BLOCK, "STAGE2_BLOCKS": blocks, "AREA_SIZE": area})
    if syms["install_end"] > STACK_LO:
        raise ValueError(f"loader ends at {syms['install_end']:#x}, past {STACK_LO:#x}")
    so = epstool.addr_to_offset(STAGE)
    if any(os_bin[so:so + len(loader)]):
        raise ValueError("staging bytes are not zero in this OS")
    to = epstool.addr_to_offset(TRAMPOLINE)
    if os_bin[to - 4:to + 6].hex() != TRAP10_STOCK + TRAMPOLINE_STOCK:
        raise ValueError("trap #10 jump / trampoline at 0xFF832A is not stock")
    io = epstool.addr_to_offset(OVERLAY_WINDOW, 3)
    fill = epstool.FILL[:2] * (len(image) // 2)
    if os_bin[io:io + len(image)] != fill:
        raise ValueError("overlay-3 slot of this OS is not empty")
    patch = {"name": "codearea", "edits": [
        {"addr": f"0x{STAGE:06X}", "expect": "00" * len(loader), "data": loader.hex()},
        {"addr": f"0x{TRAMPOLINE:06X}", "expect": TRAMPOLINE_STOCK,
         "data": "4ef9" + STAGE.to_bytes(4, "big").hex()},
        {"addr": f"0x{OVERLAY_WINDOW:06X}", "overlay": 3, "expect": fill.hex(),
         "data": image.hex()},
    ]}
    if auto_keep:
        patch["edits"].append(dict(AUTO_KEEP))
    info = {"loader_bytes": len(loader), "install_end": syms["install_end"],
            "image_bytes": len(image), "blocks": blocks,
            "area_size": area, "image": image, "image_offsets": isyms}
    return patch, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("os")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--groups", default="")
    ap.add_argument("--swing", default="",
                    help="quantize + swing LOOPED takes: G:STYLE:AMOUNT (e.g. 16:mpc:58, "
                         "8:sp1200:63) for all instruments, or I=G:STYLE:AMOUNT,... ; "
                         "G = 4 4T 8 8T 16 16T 32 32T, STYLE = mpc (50-75) or sp1200 "
                         "(50 54 58 63 67 71)")
    ap.add_argument("--undo", action="store_true",
                    help="RECORD while loop recording takes out the last notes played "
                         "(on with --swing too)")
    ap.add_argument("--pages", action="store_true",
                    help="our parameters on the edit pages (MUTE GROUP on wavesample page 6)")
    ap.add_argument("--auto-keep", action="store_true",
                    help="no KEEP = OLD NEW prompt after recording: keep NEW")
    ap.add_argument("--area", type=int, default=AREA_SIZE,
                    help=f"code area size in bytes (default {AREA_SIZE})")
    ap.add_argument("--disk", nargs=2, metavar=("STOCK", "OUT"))
    a = ap.parse_args()
    os_bin = open(a.os, "rb").read()
    groups = parse_groups(a.groups)
    swing_settings = parse_swing(a.swing)
    patch, info = build(os_bin, groups, a.area, a.auto_keep, swing_settings, a.undo, a.pages)
    json.dump(patch, open(a.out, "w"), indent=1)
    used = sorted({g for g in groups.values() if g})
    print(f"{a.out}: loader {info['install_end'] - STAGE}/{STACK_LO - STAGE} bytes, "
          f"image {info['image_bytes']} bytes ({info['blocks']} blocks of "
          f"{IMAGE_MAX_BLOCKS}), code area {info['area_size']} bytes, "
          f"{sum(1 for g in groups.values() if g)} keys in groups {used}"
          + (f", swing {a.swing}" if swing_settings else "")
          + (", loop undo" if swing_settings or a.undo else ""))
    if a.disk:
        stock, out = a.disk
        img = epstool.load_image(stock)
        new_os = epstool.apply_patch(epstool.read_file(img, epstool.get_entry(img, 0)), patch)
        epstool.replace_file(img, 0, new_os)
        epstool.save_image(img, out, open(stock, "rb").read())
        print(f"{out}: disk written")


if __name__ == "__main__":
    main()
