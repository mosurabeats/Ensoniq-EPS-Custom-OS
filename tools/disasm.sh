#!/bin/sh
# Disassemble an EPS OS file at its link addresses.
# Needs binutils for m68k:  apt-get install binutils-m68k-linux-gnu
#
#   tools/disasm.sh OS.bin        resident part (file 0x0000-0xBFFF @ 0xFF2000)
#   tools/disasm.sh OS.bin N      overlay N (file 0xC000 + N*0x2000 @ 0xFFE000)
set -e
OS=${1:?usage: disasm.sh OS.bin [overlay]}
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
if [ -z "$2" ]; then
    head -c $((0xC000)) "$OS" > "$TMP"
    BASE=0xff2000
else
    tail -c +$((0xC000 + $2 * 0x2000 + 1)) "$OS" | head -c $((0x2000)) > "$TMP"
    BASE=0xffe000
fi
m68k-linux-gnu-objdump -D -b binary -m m68k:68000 --adjust-vma="$BASE" "$TMP"
