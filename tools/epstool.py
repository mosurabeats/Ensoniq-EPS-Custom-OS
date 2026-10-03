#!/usr/bin/env python3
"""Ensoniq EPS disk / OS toolkit.

Subcommands
  ede2img  IN.ede OUT.img            Expand a Giebler .EDE image to a raw 800K .img
  img2ede  IN.img OUT.ede [--template T.ede]
                                     Compress a raw .img back to .EDE
  ls       IMAGE                     List the root directory of an .img/.ede
  extract  IMAGE INDEX OUT.bin       Extract directory entry INDEX to a file
  replace  IMAGE INDEX NEW.bin OUT   Replace file INDEX with NEW.bin (may grow
                                     into free blocks directly after it)
  patch    OS.bin PATCH.json OUT.bin Apply a verified byte patch to an OS file
  info     OS.bin                    Summarise an OS file

Raw .img layout: 1600 blocks x 512 bytes (80 cyl x 2 heads x 10 sectors), the
same order Gotek/FlashFloppy and HxC expect for Ensoniq 800K disks.
"""
import argparse
import json
import sys

BLOCK = 512
NBLOCKS = 1600
FILL = bytes([0x6D, 0xB6]) * (BLOCK // 2)  # Ensoniq unused-block pattern

EDE_BITMAP = 0xA0       # skip bitmap, 1 bit per block, MSB first, 1 = not stored
EDE_DATA = 0x200        # stored blocks start here

DIR_BLOCKS = (3, 4)     # root directory: 2 blocks, 39 entries x 26 bytes
DIR_ENTRY = 26
FAT_START = 5           # FAT: 3-byte big-endian entries, 170 per block
FAT_PER_BLOCK = 170
FAT_EOF = 1

# OS file layout (see docs/ANALYSIS.md): file 0x0000-0xBFFF is resident at
# 0xFF2000-0xFFDFFF; the rest is 8 KB overlays that the OS reads from the OS
# disk into the window at 0xFFE000-0xFFFFFF on demand (overlay 0 at 0xC000).
OS_LOAD_ADDR = 0xFF2000
RESIDENT_END = 0xFFE000
OVERLAY_WINDOW = 0xFFE000
OVERLAY_FILE_BASE = 0xC000
OVERLAY_SIZE = 0x2000


def addr_to_offset(addr, overlay=None):
    """CPU address (+ overlay number for the 0xFFE000 window) -> file offset."""
    if overlay is not None:
        if not OVERLAY_WINDOW <= addr < OVERLAY_WINDOW + OVERLAY_SIZE:
            sys.exit(f"{addr:#x} is outside the overlay window")
        return OVERLAY_FILE_BASE + overlay * OVERLAY_SIZE + addr - OVERLAY_WINDOW
    if not OS_LOAD_ADDR <= addr < RESIDENT_END:
        sys.exit(f"{addr:#x} is not resident; give \"overlay\" for 0xFFE000+")
    return addr - OS_LOAD_ADDR

FILE_TYPES = {1: "OS", 2: "DIR", 3: "INST", 4: "BANK", 5: "SEQ", 6: "SONG",
              7: "SYSEX", 8: "PARENT", 9: "MACRO"}


# ---------------------------------------------------------------- EDE codec

def ede_decode(ede):
    bitmap = ede[EDE_BITMAP:EDE_BITMAP + NBLOCKS // 8]
    pos = EDE_DATA
    img = bytearray()
    for b in range(NBLOCKS):
        if (bitmap[b // 8] >> (7 - b % 8)) & 1:
            img += FILL
        else:
            img += ede[pos:pos + BLOCK]
            pos += BLOCK
    return bytes(img)


def ede_encode(img, template=None):
    if template is not None:
        header = bytearray(template[:EDE_DATA])
    else:
        header = bytearray(EDE_DATA)
        text = b"\r\nEPS Disk".ljust(0x9D, b" ") + b"\r\n\x1a"
        header[:len(text)] = text
        header[0x1FF] = 0x03
    bitmap = bytearray(NBLOCKS // 8)
    body = bytearray()
    for b in range(NBLOCKS):
        blk = img[b * BLOCK:(b + 1) * BLOCK]
        # Like Giebler's tools: only unused blocks that still hold the
        # format pattern are left out; used blocks are always stored.
        if blk == FILL and (b == 0 or fat_get(img, b) == 0):
            bitmap[b // 8] |= 0x80 >> (b % 8)
        else:
            body += blk
    header[EDE_BITMAP:EDE_BITMAP + len(bitmap)] = bitmap
    return bytes(header) + bytes(body) + b"\x00"


def load_image(path):
    data = open(path, "rb").read()
    if path.lower().endswith(".ede"):
        return bytearray(ede_decode(data))
    if len(data) != NBLOCKS * BLOCK:
        sys.exit(f"{path}: expected {NBLOCKS * BLOCK} bytes, got {len(data)}")
    return bytearray(data)


def save_image(img, path, template=None):
    if path.lower().endswith(".ede"):
        open(path, "wb").write(ede_encode(img, template))
    else:
        open(path, "wb").write(img)


# ------------------------------------------------------------- filesystem

def blk(img, n):
    return img[n * BLOCK:(n + 1) * BLOCK]


def fat_off(n):
    return (FAT_START + n // FAT_PER_BLOCK) * BLOCK + (n % FAT_PER_BLOCK) * 3


def fat_get(img, n):
    o = fat_off(n)
    return int.from_bytes(img[o:o + 3], "big")


def fat_set(img, n, v):
    o = fat_off(n)
    img[o:o + 3] = v.to_bytes(3, "big")


def dir_entries(img):
    raw = blk(img, DIR_BLOCKS[0]) + blk(img, DIR_BLOCKS[1])
    out = []
    for i in range(39):
        e = raw[i * DIR_ENTRY:(i + 1) * DIR_ENTRY]
        ftype = e[1]
        if ftype == 0:
            continue
        out.append(dict(index=i, type=ftype,
                        name=e[2:14].decode("latin-1"),
                        blocks=int.from_bytes(e[14:16], "big"),
                        contiguous=int.from_bytes(e[16:18], "big"),
                        start=int.from_bytes(e[18:22], "big"),
                        raw_off=DIR_BLOCKS[0] * BLOCK + i * DIR_ENTRY))
    return out


def chain(img, start):
    out, b = [], start
    while b not in (0, FAT_EOF) and len(out) < NBLOCKS:
        out.append(b)
        b = fat_get(img, b)
    return out


def get_entry(img, index):
    for e in dir_entries(img):
        if e["index"] == index:
            return e
    sys.exit(f"no directory entry {index}")


def read_file(img, e):
    return b"".join(blk(img, b) for b in chain(img, e["start"]))[:e["blocks"] * BLOCK]


def free_count(img):
    return int.from_bytes(img[2 * BLOCK:2 * BLOCK + 4], "big")


def replace_file(img, index, data):
    """Rewrite file `index` in place, growing into free blocks right after it."""
    e = get_entry(img, index)
    old = chain(img, e["start"])
    if old != list(range(e["start"], e["start"] + len(old))):
        sys.exit("replace only supports contiguous files")
    need = (len(data) + BLOCK - 1) // BLOCK
    data = data + FILL[:need * BLOCK - len(data)]
    end = e["start"] + need
    for b in range(e["start"] + len(old), end):
        if b >= NBLOCKS or fat_get(img, b) != 0:
            sys.exit(f"block {b} is not free; cannot grow file to {need} blocks")
    for b in range(e["start"] + need, e["start"] + len(old)):  # shrink: free tail
        fat_set(img, b, 0)
        img[b * BLOCK:(b + 1) * BLOCK] = FILL
    for i in range(need):
        b = e["start"] + i
        img[b * BLOCK:(b + 1) * BLOCK] = data[i * BLOCK:(i + 1) * BLOCK]
        fat_set(img, b, b + 1 if i < need - 1 else FAT_EOF)
    o = e["raw_off"]
    img[o + 14:o + 16] = need.to_bytes(2, "big")
    img[o + 16:o + 18] = need.to_bytes(2, "big")
    fc = free_count(img) - (need - len(old))
    img[2 * BLOCK:2 * BLOCK + 4] = fc.to_bytes(4, "big")


# ------------------------------------------------------------------ patches

def apply_patch(os_bin, patch):
    """patch = {"name":..., "edits":[{"addr","expect","data"[,"overlay"]}]}

    `addr` is a CPU address (add "overlay": n for addresses in the 0xFFE000
    overlay window); `expect` and `data` are hex strings. Every
    `expect` must match before anything is written, so a patch made for one
    OS version refuses to apply to another.
    """
    out = bytearray(os_bin)
    edits = []
    for ed in patch["edits"]:
        off = addr_to_offset(int(ed["addr"], 16), ed.get("overlay"))
        exp = bytes.fromhex(ed["expect"])
        new = bytes.fromhex(ed["data"])
        if out[off:off + len(exp)] != exp:
            sys.exit(f"{ed['addr']}: expected {exp.hex()} found "
                     f"{out[off:off + len(exp)].hex()} - wrong OS version?")
        edits.append((off, new))
    for off, new in edits:
        if off + len(new) > len(out):
            out += FILL[:off + len(new) - len(out)]
        out[off:off + len(new)] = new
    return bytes(out)


# --------------------------------------------------------------------- CLI

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("ede2img"); a.add_argument("src"); a.add_argument("dst")
    a = sp.add_parser("img2ede"); a.add_argument("src"); a.add_argument("dst")
    a.add_argument("--template")
    a = sp.add_parser("ls"); a.add_argument("image")
    a = sp.add_parser("extract"); a.add_argument("image"); a.add_argument("index", type=int)
    a.add_argument("dst")
    a = sp.add_parser("replace"); a.add_argument("image"); a.add_argument("index", type=int)
    a.add_argument("src"); a.add_argument("dst")
    a = sp.add_parser("patch"); a.add_argument("os"); a.add_argument("patch")
    a.add_argument("dst")
    a = sp.add_parser("info"); a.add_argument("os")
    args = p.parse_args()

    if args.cmd == "ede2img":
        open(args.dst, "wb").write(ede_decode(open(args.src, "rb").read()))
    elif args.cmd == "img2ede":
        tpl = open(args.template, "rb").read() if args.template else None
        open(args.dst, "wb").write(ede_encode(open(args.src, "rb").read(), tpl))
    elif args.cmd == "ls":
        img = load_image(args.image)
        label = blk(img, 1)[31:38].rstrip(b"\0 ").decode("latin-1")
        print(f"label {label!r}  free blocks {free_count(img)}")
        for e in dir_entries(img):
            t = FILE_TYPES.get(e["type"], f"type{e['type']}")
            print(f"{e['index']:3d}  {t:6s} {e['name']!r}  {e['blocks']} blocks "
                  f"@ {e['start']}")
    elif args.cmd == "extract":
        img = load_image(args.image)
        open(args.dst, "wb").write(read_file(img, get_entry(img, args.index)))
    elif args.cmd == "replace":
        img = load_image(args.image)
        replace_file(img, args.index, open(args.src, "rb").read())
        tpl = open(args.image, "rb").read() if args.image.lower().endswith(".ede") else None
        save_image(img, args.dst, tpl)
    elif args.cmd == "patch":
        patch = json.load(open(args.patch))
        out = apply_patch(open(args.os, "rb").read(), patch)
        open(args.dst, "wb").write(out)
        print(f"applied {patch.get('name', args.patch)}: {len(patch['edits'])} edits")
    elif args.cmd == "info":
        d = open(args.os, "rb").read()
        print(f"size {len(d)} bytes ({(len(d) + 511) // 512} blocks)")
        print(f"resident  file 0x0000-{OVERLAY_FILE_BASE - 1:#06x} -> "
              f"{OS_LOAD_ADDR:#x}-{RESIDENT_END - 1:#x}")
        for n, off in enumerate(range(OVERLAY_FILE_BASE, len(d), OVERLAY_SIZE)):
            chunk = d[off:off + OVERLAY_SIZE]
            state = "empty (6DB6 fill)" if chunk == FILL[:2] * (len(chunk) // 2) else \
                f"{len(chunk)} bytes"
            print(f"overlay {n} file {off:#07x} -> {OVERLAY_WINDOW:#x}: {state}")


if __name__ == "__main__":
    main()
