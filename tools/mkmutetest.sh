#!/bin/sh
# Build EPS249_MUTE: OS 2.49 with mute groups only (MUTE GROUP on the 6 Amp
# page), all in OS RAM (tools/mkresident.py): the build for real hardware,
# whose sample RAM can't hold code. Just the OS: the rest of the disk is
# free for your own sounds.
# Writes build/test/EPS249_MUTE.hfe (Gotek) and .img (MAME).
# docs/HARDWARE_TESTS.md -> Mute groups test.
set -e
cd "$(dirname "$0")/.."
for ext in hfe img; do
    python3 tools/mkresident.py build/eps_os_249.bin -o build/test/resmute.json \
        --disk build/hfe/EPS249OS.hfe build/test/EPS249_MUTE.$ext
done
python3 tools/epstool.py ls build/test/EPS249_MUTE.hfe
