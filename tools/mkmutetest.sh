#!/bin/sh
# Build EPS249_MUTE: OS 2.49 with mute groups only (MUTE GROUP on the 6 Amp
# page), all in OS RAM (tools/mkresident.py): the build for real hardware,
# whose sample RAM can't hold code. Just the OS: the rest of the disk is
# free for your own sounds.
# Writes build/test/EPS249_MUTE.hfe (Gotek) and .img (MAME), and three
# disks to compare how fast a cut note fades: EPS249_MUTE_12MS, _24MS
# (the default, same as EPS249_MUTE) and _48MS (.hfe).
# docs/HARDWARE_TESTS.md -> Mute groups test.
set -e
cd "$(dirname "$0")/.."
for ext in hfe img; do
    python3 tools/mkresident.py build/eps_os_249.bin -o build/test/resmute.json \
        --disk build/hfe/EPS249OS.hfe build/test/EPS249_MUTE.$ext
done
for f in 1:12 2:24 4:48; do
    python3 tools/mkresident.py build/eps_os_249.bin -o build/test/resmute.json --choke ${f%:*} \
        --disk build/hfe/EPS249OS.hfe build/test/EPS249_MUTE_${f#*:}MS.hfe
done
python3 tools/epstool.py ls build/test/EPS249_MUTE.hfe
