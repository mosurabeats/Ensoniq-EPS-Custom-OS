#!/usr/bin/env python3
"""Build the swing patch (hardware build): mute groups plus our code in a
borrowed region of the overlay window (src/swing/, docs/ANALYSIS.md ->
The overlay window during play and recording).

  mkswing.py OS.bin -o PATCH.json [--quantize N] [--swing PCT]
             [--disk STOCK.hfe|STOCK.img OUT.hfe|OUT.img]

Edits to the OS file:
  * 0xFF832E: the trampoline to the ROM's sample-memory sizing jumps to
    early (src/swing/late.s), which takes our store off the sample heap,
  * 0xFF1770: the boot sequence's last call goes to late, which loads
    overlay 3 and runs its install,
  * 0xFFC994: early and late (a zero run at the bottom of the init stack),
  * the overlay-3 slot: overlay 0 with our window image (src/swing/
    window.s + the resident chunks it installs) in the region,
  * overlay 2, 0xFFE20E (FILTER CUTOFF from SAMPLE RATE): SP sampling mode,
    src/swing/spf.s.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import epstool  # noqa: E402
import mkhook  # noqa: E402
import mkresident  # noqa: E402

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
SW = os.path.join(SRC, "swing")
REGION = 0xFFE400                      # our part of the window: from here,
REGION_END = 0xFFFFE0                   # as long as the image (the window's first
                                        # 1 KB is used at boot and by the sequencer;
                                        # the last 32 bytes are the same in all overlays)
OVERLAY_WINDOW, OVERLAY_SIZE = 0xFFE000, 0x2000
CARRIER, CARRIER_END = 0xFFC994, 0xFFCA30   # the boot's init stack reaches 0xFFCA3E
MAGIC = 0x53574721                      # "SWG!" (src/swing/late.s)
QLABELS = ["1/4", "1/4T", "1/8", "1/8T", "1/16", "1/16T", "1/32", "1/32T", "OFF"]

# resident homes: boot-only code, dead once the main loop runs
MUTE_AT, MUTE_END = 0xFF1720, 0xFF1770  # the boot sequence's jsr list
ML_AT, ML_END = 0xFF2990, 0xFF29BA      # boot routine 0xFF298E (4-aligned for ld)
SWAPX_AT, SWAPX_END = 0xFF86E8, 0xFF870A  # boot routine 0xFF86E6 (0xFF870A is used later)
LVL_AT, LVL_END = 0xFF874C, 0xFF8766    # boot routine 0xFF874C
OS1_AT, OS1_END = 0xFF4EA8, 0xFF4EC2    # boot routine 0xFF4EA6
OS2_AT, OS2_END = 0xFF1764, 0xFF1774    # after the mute code: the jsr at 0xFF1770 runs once
LDR_END = 0xFF4E40                      # boot routine 0xFF4E20, right before the loader
LDR_MIN = 0xFF4E20
SPF_AT, SPF_END = 0xFF5214, 0xFF5224    # the tail of boot routine 0xFF5212
SPF_SITE = 0xFFE20E                     # overlay 2: FILTER CUTOFF from SAMPLE RATE
SPF_STOCK = "70001038020f207c00c06ffe11f0000002124e75"

STOCK = {                               # sites we patch: address -> stock bytes
    0xFF832E: "4ef900c08490",           # trampoline: jmp ROM sizing
    0xFF1770: "4eb81ef4",               # jsr 0x1EF4.w
    0xFFAF92: "303816be",               # mute hook (src/resmute.s)
    0xFF1774: "31fc01401602",           # main loop top
    0xFF277C: "4eb84e40", 0xFF2A9E: "4eb84e40",   # the overlay loader's callers
    0xFF53B8: "4eb84e40", 0xFF8A24: "4eb84e40",
    0xFFB252: "103816b6",               # FULL LEVEL: move.b 0x16B6.w,d0 (voice start)
    0xFFAE54: "4a2a0014",               # ONE-SHOT: tst.b 20(a2) (key-up)
    0xFF5212: "31fcc97ac68e4238c3f44278c81a4ef854a6",   # boot-only (SP mode's home)
}


def w(v):
    return (v & 0xFFFF).to_bytes(2, "big")


def chunk(dest, data):
    data = bytes(data)
    if len(data) % 2 or not data:
        raise ValueError("chunks are an even number of bytes")
    return w(dest) + w(len(data) - 1) + data


def asm(name, org, entry, defs=None):
    code, syms = mkhook.assemble(os.path.join(SW, name), org, entry, defs)
    if syms.get(entry) != org:
        raise ValueError(f"{name}: {entry} at {syms.get(entry, 0):#x}, not {org:#x} (align it)")
    return bytes(code), syms


def spf_site():
    """Overlay 2's FILTER CUTOFF reset, same 20 bytes: the rate (its only
    caller, 0xFF45A6, has a6 = 0x20F, SAMPLE RATE) and the ROM table go to
    the resident spf (src/swing/spf.s), which picks the filter."""
    code = (bytes.fromhex("7000")                # moveq #0,d0
            + bytes.fromhex("1016")              # move.b (a6),d0
            + bytes.fromhex("207c00c06ffe")      # movea.l #0xC06FFE,a0
            + bytes.fromhex("4eb8") + w(SPF_AT)  # jsr spf.w
            + bytes.fromhex("11c10212")          # move.b d1,0x212.w
            + bytes.fromhex("4e75"))             # rts
    assert len(code) == len(SPF_STOCK) // 2
    return code


def build(os_bin, quantize=QLABELS.index("1/16"), swing=50, choke=mkresident.CHOKE_DEFAULT):
    if not 0 <= quantize <= 8 or not 0 <= swing <= 75:
        raise ValueError("--quantize 0-8, --swing 0-75")
    def image_for(length):
        """Everything at region length `length` (only swapx and the boot
        stage use it, and their size doesn't depend on it)."""
        reg = {"REGION": REGION & 0xFFFF, "LEN": length}
        swapx, _ = asm("swapx.s", SWAPX_AT, "swapx", reg)
        win, wsyms = asm("window.s", REGION, "wmagic",
                         {"QUANT_DEFAULT": quantize, "SWING_DEFAULT": swing,
                          "REGION16": REGION & 0xFFFF, "SWAPX": SWAPX_AT & 0xFFFF})
        mute, msyms = mkhook.assemble(os.path.join(SRC, "resmute.s"), MUTE_AT, "mute",
                                      {"CHOKE_RATE": choke})
        if msyms["mute"] != MUTE_AT or msyms["mute_end"] > MUTE_END:
            raise ValueError("mute code doesn't fit")
        calls = {"SWAPX": SWAPX_AT & 0xFFFF, "PATCH": wsyms["patch"] & 0xFFFF,
                 "UNPATCH": wsyms["unpatch"] & 0xFFFF, "OUT": wsyms["out"] & 0xFFFF,
                 "ONESHOT2": OS2_AT & 0xFFFF}
        ldr0, _ = mkhook.assemble(os.path.join(SW, "ldr.s"), 0, "ldr", calls)
        ldr_at = LDR_END - len(ldr0)
        ldr, _ = asm("ldr.s", ldr_at, "ldr", calls)
        ml, _ = asm("ml.s", ML_AT, "ml", calls)
        lvl, _ = asm("lvl.s", LVL_AT, "lvl")
        os1, _ = asm("oneshot.s", OS1_AT, "oneshot", calls)
        os2, _ = asm("oneshot2.s", OS2_AT, "oneshot2")
        spf, _ = asm("spf.s", SPF_AT, "spf")
        for name, at_, code, end in (("swapx", SWAPX_AT, swapx, SWAPX_END), ("ml", ML_AT, ml, ML_END),
                                     ("ldr", ldr_at, ldr, LDR_END), ("lvl", LVL_AT, lvl, LVL_END),
                                     ("oneshot", OS1_AT, os1, OS1_END),
                                     ("oneshot2", OS2_AT, os2, OS2_END),
                                     ("spf", SPF_AT, spf, SPF_END)):
            if at_ + len(code) > end or (name == "ldr" and at_ < LDR_MIN):
                raise ValueError(f"{name} doesn't fit ({len(code)} bytes)")
        if ldr_at + len(ldr) != LDR_END:
            raise ValueError("ldr must end at the loader")
        chunks = [(MUTE_AT, mute), (SWAPX_AT, swapx), (ldr_at, ldr), (ML_AT, ml),
                  (LVL_AT, lvl), (OS1_AT, os1), (OS2_AT, os2), (SPF_AT, spf),
                  (0xFFAF92, bytes.fromhex("4eb8") + w(MUTE_AT)),
                  (0xFFB252, bytes.fromhex("4eb8") + w(LVL_AT)),
                  (0xFFAE54, bytes.fromhex("4eb8") + w(OS1_AT))]
        chunks += [(a, bytes.fromhex("4eb8") + w(ldr_at)) for a in (0xFF277C, 0xFF2A9E, 0xFF53B8, 0xFF8A24)]
        chunks += [(0xFF1774, bytes.fromhex("4eb8") + w(ML_AT) + bytes.fromhex("4e71"))]   # last
        image = bytearray(win) + b"".join(chunk(a, d) for a, d in chunks) + w(0)
        if wsyms["chunks"] - REGION != len(win):
            raise ValueError("the chunk table must follow window.s")
        return image, wsyms, chunks, ldr_at, reg

    image, *_ = image_for(16)
    LEN = (len(image) + 15) // 16 * 16
    image, wsyms, chunks, ldr_at, reg = image_for(LEN)
    if len(image) > LEN or REGION + LEN > REGION_END:
        raise ValueError(f"window image is {len(image)} bytes, the region {REGION_END - REGION}")
    win = image

    reserve = (2 * LEN + 511) // 512 * 512
    defs = dict(reg, RESERVE=reserve, MAGIC_AT=0)
    late, lsyms = asm("late.s", CARRIER, "early", defs)
    defs["MAGIC_AT"] = (CARRIER + len(late)) & 0xFFFF
    late, lsyms = asm("late.s", CARRIER, "early", defs)
    carrier = late + MAGIC.to_bytes(4, "big")
    if CARRIER + len(carrier) > CARRIER_END:
        raise ValueError(f"boot stage ends at {CARRIER + len(carrier):#x}, past {CARRIER_END:#x}")

    def at(a, n, overlay=None):
        o = epstool.addr_to_offset(a, overlay)
        return os_bin[o:o + n]
    for a, stock in STOCK.items():
        if at(a, len(stock) // 2).hex() != stock:
            raise ValueError(f"{a:#x} is not stock OS 2.49")
    if at(SPF_SITE, len(SPF_STOCK) // 2, 2).hex() != SPF_STOCK:
        raise ValueError(f"overlay 2 {SPF_SITE:#x} is not stock OS 2.49")
    if any(at(CARRIER, len(carrier))):
        raise ValueError("the boot stage's bytes are not zero in this OS")
    ov0 = at(OVERLAY_WINDOW, OVERLAY_SIZE, 0)
    slot3 = at(OVERLAY_WINDOW, OVERLAY_SIZE, 3)
    if slot3 != epstool.FILL[:2] * (OVERLAY_SIZE // 2):
        raise ValueError("the overlay-3 slot of this OS is not empty")
    ov3 = bytearray(ov0)
    off = REGION - OVERLAY_WINDOW
    ov3[off:off + len(image)] = image
    patch = {"name": "swing", "edits": [
        {"addr": "0xFF832E", "expect": STOCK[0xFF832E],
         "data": "4ef8" + w(lsyms["early"]).hex() + "4e71"},
        {"addr": "0xFF1770", "expect": STOCK[0xFF1770], "data": "4eb8" + w(lsyms["late"]).hex()},
        {"addr": f"0x{CARRIER:06X}", "expect": "00" * len(carrier), "data": carrier.hex()},
        {"addr": f"0x{OVERLAY_WINDOW:06X}", "overlay": 3, "expect": slot3.hex(), "data": ov3.hex()},
        {"addr": f"0x{SPF_SITE:06X}", "overlay": 2, "expect": SPF_STOCK, "data": spf_site().hex()},
    ]}
    info = {"window": wsyms, "image_bytes": len(image), "carrier_bytes": len(carrier), "len": LEN,
            "ldr_at": ldr_at, "reserve": reserve, "chunks": chunks, "ov3": bytes(ov3)}
    return patch, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("os")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--quantize", default="1/16", choices=QLABELS,
                    help="QUANTIZE at power-on (default 1/16)")
    ap.add_argument("--swing", type=int, default=50, help="SWING%% at power-on (default 50)")
    ap.add_argument("--disk", nargs=2, metavar=("STOCK", "OUT"))
    ap.add_argument("--choke", type=int, default=mkresident.CHOKE_DEFAULT,
                    help="mute groups: the cut's fade, envelope time 0-99")
    a = ap.parse_args()
    patch, info = build(open(a.os, "rb").read(), QLABELS.index(a.quantize), a.swing, a.choke)
    json.dump(patch, open(a.out, "w"), indent=1)
    print(f"{a.out}: window image {info['image_bytes']} bytes at {REGION:#x} (room for "
          f"{REGION_END - REGION}), boot stage "
          f"{info['carrier_bytes']} bytes, store {info['reserve']} bytes of sample RAM")
    if a.disk:
        stock, out = a.disk
        img = epstool.load_image(stock)
        new_os = epstool.apply_patch(epstool.read_file(img, epstool.get_entry(img, 0)), patch)
        epstool.replace_file(img, 0, new_os)
        epstool.save_image(img, out, open(stock, "rb").read())
        print(f"{out}: disk written")


if __name__ == "__main__":
    main()
