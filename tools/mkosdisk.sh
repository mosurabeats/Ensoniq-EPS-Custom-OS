#!/bin/sh
# Build EPS249_CUSTOM: OS 2.49 + code area with our edit-page parameters
# (--pages: MUTE GROUP on the 6 Amp page, QUANTIZE and SWING% on the
# sequencer page), loop recording undo and auto-keep (no KEEP = OLD NEW
# prompt). Just the OS: the rest of the disk is free for your own sounds.
# Writes build/test/EPS249_CUSTOM.hfe (Gotek) and .img (MAME).
# (tools/mkdrums.sh: the same OS plus two factory kits, for testing.)
set -e
cd "$(dirname "$0")/.."
SWING="16:mpc:58"                    # QUANTIZE 1/16, SWING% 58 at power-on
for ext in hfe img; do
    python3 tools/mkcodearea.py build/eps_os_249.bin -o build/test/custom.json \
        --pages --swing "$SWING" --auto-keep --disk build/hfe/EPS249OS.hfe build/test/EPS249_CUSTOM.$ext
done
python3 tools/epstool.py ls build/test/EPS249_CUSTOM.hfe
