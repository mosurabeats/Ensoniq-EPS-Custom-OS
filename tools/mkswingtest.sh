#!/bin/sh
# Build the swing build (tools/mkswing.py): mute groups (MUTE GROUP on the
# 6 Amp page), MPC-style loop recording (QUANTIZE and SWING% on the Seq·Song
# page) and HIT (FULL LEVEL / ONE-SHOT, the Layer page). Just the OS: the
# rest of the disk is free for your own sounds.
# Writes build/test/$NAME.hfe (Gotek) and .img (MAME); NAME defaults to
# EPS249_NEXT. (EPS249_SWING, the first hardware test of it, is commit
# dfea704 of this script.) docs/HARDWARE_TESTS.md.
set -e
cd "$(dirname "$0")/.."
NAME=${NAME:-EPS249_NEXT}
for ext in hfe img; do
    python3 tools/mkswing.py build/eps_os_249.bin -o build/test/swing.json \
        --disk build/hfe/EPS249OS.hfe build/test/$NAME.$ext
done
python3 tools/epstool.py ls build/test/$NAME.hfe
