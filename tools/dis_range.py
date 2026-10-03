#!/usr/bin/env python3
"""Print disassembly lines between two addresses: dis_range.py FILE.dis START END"""
import sys
f, lo, hi = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16)
for line in open(f):
    head = line.split(":", 1)[0].strip()
    try:
        a = int(head, 16)
    except ValueError:
        continue
    if lo <= a <= hi:
        print(line.rstrip()[:100])
