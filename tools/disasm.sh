#!/bin/sh
# Disassemble an EPS OS file at its link address.
# Needs binutils for m68k:  apt-get install binutils-m68k-linux-gnu
# Usage: tools/disasm.sh build/eps_os_249.bin > build/eps_os_249.dis
set -e
OS=${1:?usage: disasm.sh OS.bin}
BASE=${BASE:-0xff2000}
m68k-linux-gnu-objdump -D -b binary -m m68k:68000 --adjust-vma="$BASE" "$OS"
