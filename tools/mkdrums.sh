#!/bin/sh
# Build EPS249_DRUMS: OS 2.49 + code area with mute groups + the TR 8O8 and
# LIVE KIT kits from Ensoniq's factory drum disk 9 (tools/fetch.sh sounds).
# Writes build/test/EPS249_DRUMS.hfe (Gotek) and .img (MAME).
# The groups follow instrument slots: load TR 8O8 into instrument 1 and
# LIVE KIT into instrument 2 (docs/HARDWARE_TESTS.md -> Drum disk).
set -e
cd "$(dirname "$0")/.."
GROUPS="1:G2-A#2=1,1:C2-C#2=2,2:F#3-A#3=3"
for ext in hfe img; do
    python3 tools/mkcodearea.py build/eps_os_249.bin -o build/test/drums.json \
        --groups "$GROUPS" --disk build/hfe/EPS249OS.hfe build/test/drums_os.$ext
    python3 tools/epstool.py add build/test/drums_os.$ext build/sounds/DRMSET09.GKH 1 build/test/drums1.$ext
    python3 tools/epstool.py add build/test/drums1.$ext build/sounds/DRMSET09.GKH 2 build/test/EPS249_DRUMS.$ext
    rm build/test/drums_os.$ext build/test/drums1.$ext
done
python3 tools/epstool.py ls build/test/EPS249_DRUMS.hfe
