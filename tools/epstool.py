#!/usr/bin/env python3
"""Ensoniq EPS disk / OS toolkit.

Subcommands
  ede2img  IN.ede OUT.img            Expand a Giebler .EDE image to a raw 800K .img
  hfe2img  IN.hfe OUT.img            Decode an HxC .hfe (Gotek/HxC) image to .img
                                     (ls/extract/replace also take .hfe; replace
                                     writes .hfe using the input .hfe's tracks)
  img2ede  IN.img OUT.ede [--template T.ede]
                                     Compress a raw .img back to .EDE
  ls       IMAGE                     List the root directory of an .img/.ede
  extract  IMAGE INDEX OUT.bin       Extract directory entry INDEX to a file
  replace  IMAGE INDEX NEW.bin OUT   Replace file INDEX with NEW.bin (may grow
                                     into free blocks directly after it)
  add      IMAGE SRC INDEX OUT       Copy file INDEX of disk SRC (e.g. an
                                     instrument) onto IMAGE, write OUT
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

# OS file layout (see docs/ANALYSIS.md): resident code per LOAD_MAP below;
# file 0xC000-0x13FFF is overlays 0-3, 8 KB each, which the OS reads from the
# OS disk into the window at 0xFFE000-0xFFFFFF on demand (overlay 0 is there
# at boot, overlay 3 is empty).
OS_LOAD_ADDR = 0xFF2000
RESIDENT_END = 0xFFE000
OVERLAY_WINDOW = 0xFFE000
OVERLAY_FILE_BASE = 0xC000
OVERLAY_SIZE = 0x2000


# Where the boot ROM puts each part of the OS file (ROM 0xC0C046; see
# docs/ANALYSIS.md -> Boot). RAM 0xFF2000-0xFF21FF comes from the low chunk,
# not from file 0x0000 (that block holds the exception vectors).
LOAD_MAP = [  # (RAM start, RAM end, file offset)
    (0xFF0000, 0xFF0200, 0x00000),     # vectors
    (0xFF0732, 0xFF0932, 0x14C00),     # disk/OS info block
    (0xFF1600, 0xFF2200, 0x14000),     # OS entry 0xFF171E, low code, variables
    (0xFF2200, 0xFFE000, 0x00200),     # resident OS
]


def addr_to_offset(addr, overlay=None):
    """CPU address (+ overlay number for the 0xFFE000 window) -> file offset."""
    if overlay is not None:
        if not OVERLAY_WINDOW <= addr < OVERLAY_WINDOW + OVERLAY_SIZE:
            sys.exit(f"{addr:#x} is outside the overlay window")
        return OVERLAY_FILE_BASE + overlay * OVERLAY_SIZE + addr - OVERLAY_WINDOW
    for lo, hi, off in LOAD_MAP:
        if lo <= addr < hi:
            return off + addr - lo
    sys.exit(f"{addr:#x} is not loaded from the OS file; give \"overlay\" for 0xFFE000+")

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


# ---------------------------------------------------------------- HFE reader
# HxC .hfe v1: 512-byte header, track table at block hdr[18], each track is
# interleaved 256-byte chunks of side 0 / side 1, MFM bits LSB first. We find
# IBM sync marks (0x4489), read IDAM + data fields and check both CRCs.

def _crc16(data, crc=0xFFFF):
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else crc << 1
    return crc


def _mfm_sectors(raw):
    """Yield (sector, mark, data, bit position of the first data byte)."""
    bits = "".join(format(b, "08b")[::-1] for b in raw)
    bits += bits[:8192]                       # a sector may wrap the index
    sync = "0100010010001001" * 3

    def read(pos, n):
        return bytes(int(bits[pos + 16 * i + 1:pos + 16 * i + 16:2], 2)
                     for i in range(n))

    idam = None
    pos = bits.find(sync)
    while pos != -1 and pos + 48 + 16 * 515 <= len(bits):
        p = pos + 48
        mark = read(p, 1)[0]
        if mark == 0xFE:
            hdr = read(p, 7)
            idam = hdr[1:5] if _crc16(b"\xA1\xA1\xA1" + hdr) == 0 else None
        elif mark in (0xFB, 0xF8) and idam:
            size = 128 << idam[3]
            data = read(p, 3 + size)
            if _crc16(b"\xA1\xA1\xA1" + data) == 0:
                yield idam[2], mark, data[1:1 + size], p + 16
            idam = None
        pos = bits.find(sync, pos + 48)


def _hfe_tracks(hfe):
    """Yield (track, offset, length, [side0, side1]) of an HFE v1 image."""
    if hfe[:8] != b"HXCPICFE":
        sys.exit("not an HFE v1 image")
    lut = int.from_bytes(hfe[18:20], "little") * 512
    for t in range(hfe[9]):
        off = int.from_bytes(hfe[lut + 4 * t:lut + 4 * t + 2], "little") * 512
        length = int.from_bytes(hfe[lut + 4 * t + 2:lut + 4 * t + 4], "little")
        sides = [bytearray(), bytearray()]
        for i in range(0, length, 512):
            n = min(256, (length - i) // 2)
            sides[0] += hfe[off + i:off + i + n]
            sides[1] += hfe[off + i + 256:off + i + 256 + n]
        yield t, off, length, sides


def _block_of(t, s, r):
    return (t * 2 + s) * 10 + r


def hfe_decode(hfe):
    secs = {}
    for t, _, _, sides in _hfe_tracks(hfe):
        for s in range(hfe[10]):
            for r, _, data, _ in _mfm_sectors(sides[s]):
                secs.setdefault((t, s, r), data)
    img = bytearray()
    for b in range(NBLOCKS):
        key = (b // 20, b // 10 % 2, b % 10)
        if key not in secs:
            sys.exit(f"HFE: block {b} (cyl {key[0]} head {key[1]} sec {key[2]}) "
                     "missing or bad CRC")
        img += secs[key]
    return bytes(img)


def hfe_encode(img, template):
    """New .hfe = template with every sector whose data differs from img
    re-encoded in place (MFM data + CRC). Gaps, IDs and timing stay as in
    the template, so the result looks like a real EPS disk to the drive."""
    out = bytearray(template)
    for t, off, length, sides in _hfe_tracks(template):
        for s in range(template[10]):
            raw = sides[s]
            nbits = len(raw) * 8
            bits = bytearray((byte >> k) & 1 for byte in raw for k in range(8))
            changed = False
            for r, mark, data, pos in _mfm_sectors(raw):
                new = img[_block_of(t, s, r) * BLOCK:(_block_of(t, s, r) + 1) * BLOCK]
                if new == data:
                    continue
                crc = _crc16(b"\xA1\xA1\xA1" + bytes([mark]) + new)
                prev = mark & 1
                for byte in new + crc.to_bytes(2, "big"):
                    for k in range(7, -1, -1):
                        bit = (byte >> k) & 1
                        bits[pos % nbits] = int(prev == 0 and bit == 0)   # clock
                        bits[(pos + 1) % nbits] = bit
                        prev = bit
                        pos += 2
                nxt = bits[(pos + 1) % nbits]                 # first gap bit's clock
                bits[pos % nbits] = int(prev == 0 and nxt == 0)
                changed = True
            if not changed:
                continue
            raw = bytes(sum(bits[i * 8 + k] << k for k in range(8)) for i in range(len(raw)))
            for i in range(0, length, 512):
                n = min(256, (length - i) // 2)
                j = i // 2
                out[off + i + 256 * s:off + i + 256 * s + n] = raw[j:j + n]
    return bytes(out)


def load_image(path):
    data = open(path, "rb").read()
    if path.lower().endswith(".ede"):
        return bytearray(ede_decode(data))
    if path.lower().endswith(".hfe"):
        return bytearray(hfe_decode(data))
    if data[:5] == b"TDDFI" and len(data) > NBLOCKS * BLOCK:
        data = data[-NBLOCKS * BLOCK:]          # Gotek .gkh: header + raw image
    if len(data) != NBLOCKS * BLOCK:
        sys.exit(f"{path}: expected {NBLOCKS * BLOCK} bytes, got {len(data)}")
    return bytearray(data)


def save_image(img, path, template=None):
    if path.lower().endswith(".hfe"):
        if template is None or template[:8] != b"HXCPICFE":
            sys.exit("writing .hfe needs an .hfe template (the stock disk)")
        open(path, "wb").write(hfe_encode(img, template))
        return
    if path.lower().endswith(".ede"):
        if template is not None and template[:8] == b"HXCPICFE":
            template = None
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


def add_file(img, src_img, src_index):
    """Copy file src_index of src_img into a free directory slot of img,
    in the first run of free blocks big enough (contiguous), keeping the
    source's directory entry fields. Returns the new entry's index."""
    e = get_entry(src_img, src_index)
    data = read_file(src_img, e)
    need = e["blocks"]
    raw = DIR_BLOCKS[0] * BLOCK
    slot = next((i for i in range(39) if img[raw + i * DIR_ENTRY + 1] == 0), None)
    if slot is None:
        sys.exit("directory full")
    start, run = None, 0
    for b in range(NBLOCKS):
        run = run + 1 if fat_get(img, b) == 0 else 0
        if run == need:
            start = b - need + 1
            break
    if start is None:
        sys.exit(f"no {need} contiguous free blocks")
    data = data + FILL[:need * BLOCK - len(data)]
    for i in range(need):
        b = start + i
        img[b * BLOCK:(b + 1) * BLOCK] = data[i * BLOCK:(i + 1) * BLOCK]
        fat_set(img, b, b + 1 if i < need - 1 else FAT_EOF)
    o = raw + slot * DIR_ENTRY
    img[o:o + DIR_ENTRY] = src_img[e["raw_off"]:e["raw_off"] + DIR_ENTRY]
    img[o + 16:o + 18] = need.to_bytes(2, "big")
    img[o + 18:o + 22] = start.to_bytes(4, "big")
    fc = free_count(img) - need
    img[2 * BLOCK:2 * BLOCK + 4] = fc.to_bytes(4, "big")
    return slot


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
    a = sp.add_parser("hfe2img"); a.add_argument("src"); a.add_argument("dst")
    a = sp.add_parser("img2ede"); a.add_argument("src"); a.add_argument("dst")
    a.add_argument("--template")
    a = sp.add_parser("ls"); a.add_argument("image")
    a = sp.add_parser("extract"); a.add_argument("image"); a.add_argument("index", type=int)
    a.add_argument("dst")
    a = sp.add_parser("replace"); a.add_argument("image"); a.add_argument("index", type=int)
    a.add_argument("src"); a.add_argument("dst")
    a = sp.add_parser("add"); a.add_argument("image"); a.add_argument("src")
    a.add_argument("index", type=int); a.add_argument("dst")
    a = sp.add_parser("patch"); a.add_argument("os"); a.add_argument("patch")
    a.add_argument("dst")
    a = sp.add_parser("info"); a.add_argument("os")
    args = p.parse_args()

    if args.cmd == "ede2img":
        open(args.dst, "wb").write(ede_decode(open(args.src, "rb").read()))
    elif args.cmd == "hfe2img":
        open(args.dst, "wb").write(hfe_decode(open(args.src, "rb").read()))
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
        tpl = open(args.image, "rb").read()   # .ede header / .hfe track layout
        save_image(img, args.dst, tpl)
    elif args.cmd == "add":
        img = load_image(args.image)
        slot = add_file(img, load_image(args.src), args.index)
        save_image(img, args.dst, open(args.image, "rb").read())
        print(f"{args.dst}: added as entry {slot}, {free_count(img)} blocks free")
    elif args.cmd == "patch":
        patch = json.load(open(args.patch))
        out = apply_patch(open(args.os, "rb").read(), patch)
        open(args.dst, "wb").write(out)
        print(f"applied {patch.get('name', args.patch)}: {len(patch['edits'])} edits")
    elif args.cmd == "info":
        d = open(args.os, "rb").read()
        print(f"size {len(d)} bytes ({(len(d) + 511) // 512} blocks)")
        for lo, hi, off in LOAD_MAP:
            print(f"file {off:#07x}-{off + hi - lo - 1:#07x} -> {lo:#x}-{hi - 1:#x}")
        for n, off in enumerate(range(OVERLAY_FILE_BASE, 0x14000, OVERLAY_SIZE)):
            chunk = d[off:off + OVERLAY_SIZE]
            state = "empty (6DB6 fill)" if chunk == FILL[:2] * (len(chunk) // 2) else \
                f"{len(chunk)} bytes"
            print(f"overlay {n} file {off:#07x} -> {OVERLAY_WINDOW:#x}: {state}")


if __name__ == "__main__":
    main()
