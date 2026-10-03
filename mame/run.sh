#!/bin/sh
# Boot a disk image in MAME's EPS (no video, no sound, as fast as possible)
# and print what the display showed plus the Lua script's output.
#
#   mame/run.sh DISK.img [SECONDS] [SCRIPT.lua]
#
# DISK is a raw 800K image (.img); MAME reads our .hfe files with errors.
# SCRIPT defaults to mame/boot.lua (boot steps and code-area state).
# Needs the boot ROM halves in build/bootrom/unknown/ (docs/RESOURCES.md)
# and MAME built by mame/build.sh (or MAME=path/to/eps).
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
DISK=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
SECS=${2:-15}
LUA=$(cd "$(dirname "${3:-$ROOT/mame/boot.lua}")" && pwd)/$(basename "${3:-boot.lua}")
MAME=${MAME:-$ROOT/build/mame/src/eps}
RUN=$ROOT/build/mame/run

mkdir -p "$RUN/roms/eps"
for h in h l; do
    cp -u "$ROOT/build/bootrom/unknown/eps-$h.bin" "$RUN/roms/eps/eps-$h.bin"
done
cd "$RUN"
rm -f debug.log
ESQPANEL_LOG=1 "$MAME" eps -rompath roms -flop "$DISK" -video none -sound none \
    -nothrottle -seconds_to_run "$SECS" -skip_gameinfo -debug -debugger none \
    -autoboot_script "$LUA" -debuglog >stdout.log 2>panel.log || true
python3 "$ROOT/mame/screens.py" panel.log
grep -v -e '^$' -e '^MAME debugger' -e '^Currently targeting' debug.log 2>/dev/null || true
grep -v -e '^$' -e 'control code' -e '^Average speed' stdout.log || true
