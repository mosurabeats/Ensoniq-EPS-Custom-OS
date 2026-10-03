#!/usr/bin/env python3
"""Dump the EPS edit-page parameter tables (OS 2.49 + boot ROM).

  params.py ROM.bin OS.bin

The edit pages are driven by page records in OS RAM (list of pointers at
0xFFC14C; each record: first index entry.w, last entry.w, current entry.w,
page number.b, 0, and one more word). An index entry is a word pointing at a
parameter descriptor; the index tables and the descriptors are in the boot
ROM. A word below 0x8000 is a ROM offset (0xC00000 + w), one from 0x8000 up
is OS RAM (0xFF0000 + w) (OS 0xFF2CA4), so RAM tables and descriptors work
too. Descriptor, 8 bytes:
  +0 byte  flags / parameter number (bits 5-0)
  +1 byte  type (display and edit handler)
  +2 word  max value, or for some types a handler or table (type 0x0E: an OS
           routine, 0xFF0000 + w)
  +4 word  where the value is: an offset into the edited record
           (instrument, layer, wavesample), or an OS RAM address
  +6 word  label (a ROM message number)
See docs/ANALYSIS.md -> Edit pages.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bootrom  # noqa: E402

ROM_BASE, OS_BASE = 0xC00000, 0xFF2000
PAGE_LIST, PAGE_COUNT = 0xFFC14C, 29


class Tables:
    def __init__(self, rom, os_bin):
        self.rom, self.os = rom, os_bin

    def os_w(self, a):
        i = a - OS_BASE
        return int.from_bytes(self.os[i:i + 2], "big")

    def at(self, w):
        """(where, reader) for a table word: ROM below 0x8000, OS RAM above."""
        if w < 0x8000:
            return ROM_BASE + w, lambda a, n: self.rom[a - ROM_BASE:a - ROM_BASE + n]
        return 0xFF0000 + w, lambda a, n: self.os[a - OS_BASE:a - OS_BASE + n]

    def word(self, w_addr):
        a, rd = self.at(w_addr)
        return a, int.from_bytes(rd(a, 2), "big")

    def descriptor(self, w):
        a, rd = self.at(w)
        d = rd(a, 8)
        label = bootrom.msg(self.rom, int.from_bytes(d[6:8], "big")) or ""
        return {"addr": a, "flags": d[0], "type": d[1], "w2": int.from_bytes(d[2:4], "big"),
                "where": int.from_bytes(d[4:6], "big"), "label": label.strip()}

    def pages(self):
        seen = []
        for i in range(PAGE_COUNT):
            p = self.os_w(PAGE_LIST + 2 * i)
            if p < 0xC000:
                break
            if p not in seen:
                seen.append(p)
        for p in seen:
            rec = 0xFF0000 + p
            first, last, cur, num = (self.os_w(rec), self.os_w(rec + 2), self.os_w(rec + 4),
                                     self.os_w(rec + 6) >> 8)
            entries = []
            if first < 0xC000 or first >= 0xF000:           # an index table (not a command list)
                for e in range(first, last + 2, 2):
                    ea, dw = self.word(e)
                    entries.append((ea, self.descriptor(dw)))
            yield rec, first, last, cur, num, entries


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom")
    ap.add_argument("os")
    a = ap.parse_args()
    t = Tables(open(a.rom, "rb").read(), open(a.os, "rb").read())
    for rec, first, last, cur, num, entries in t.pages():
        print(f"page record {rec:06x}: entries {first:04x}-{last:04x} (current {cur:04x}), page {num:#x}")
        for ea, d in entries:
            print(f"   {ea:06x} -> {d['addr']:06x}  flags {d['flags']:02x} type {d['type']:02x} "
                  f"w2 {d['w2']:04x} at {d['where']:04x}  {d['label']}")


if __name__ == "__main__":
    main()
