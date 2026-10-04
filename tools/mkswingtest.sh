#!/bin/sh
# Build EPS249_SWING: OS 2.49 with mute groups (MUTE GROUP on the 6 Amp
# page) and MPC-style loop recording (QUANTIZE and SWING% on the Seq·Song
# page), the hardware build (tools/mkswing.py). Just the OS: the rest of the
# disk is free for your own sounds.
# Writes build/test/EPS249_SWING.hfe (Gotek) and .img (MAME).
# docs/HARDWARE_TESTS.md -> Swing test.
set -e
cd "$(dirname "$0")/.."
for ext in hfe img; do
    python3 tools/mkswing.py build/eps_os_249.bin -o build/test/swing.json \
        --disk build/hfe/EPS249OS.hfe build/test/EPS249_SWING.$ext
done
python3 tools/epstool.py ls build/test/EPS249_SWING.hfe
