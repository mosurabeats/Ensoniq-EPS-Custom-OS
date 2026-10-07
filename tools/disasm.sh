#!/bin/sh
# Disassemble an EPS OS file at its link addresses.
# Needs binutils for m68k:  apt-get install binutils-m68k-linux-gnu
#
#   tools/disasm.sh OS.bin        resident part (file 0x0200-0xBFFF @ 0xFF2200)
#   tools/disasm.sh OS.bin low    low code (file 0x14000-0x14BFF @ 0xFF1600,
#                                 OS entry 0xFF171E; also covers 0xFF2000-0xFF21FF)
#   tools/disasm.sh OS.bin N      overlay N (file 0xC000 + N*0x2000 @ 0xFFE000)
set -e
OS=${1:?usage: disasm.sh OS.bin [overlay]}
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
if [ -z "$2" ]; then
    head -c $((0xC000)) "$OS" | tail -c +$((0x200 + 1)) > "$TMP"
    BASE=0xff2200
elif [ "$2" = low ]; then
    tail -c +$((0x14000 + 1)) "$OS" | head -c $((0xC00)) > "$TMP"
    BASE=0xff1600
else
    tail -c +$((0xC000 + $2 * 0x2000 + 1)) "$OS" | head -c $((0x2000)) > "$TMP"
    BASE=0xffe000
fi
m68k-linux-gnu-objdump -D -b binary -m m68k:68000 --adjust-vma="$BASE" "$TMP"
