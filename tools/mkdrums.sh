#!/bin/sh
# Build EPS249_DRUMS: OS 2.49 + code area with our edit-page parameters
# (--pages: MUTE GROUP on wavesample page 6, QUANTIZE and SWING% on the
# sequencer page), loop recording undo, auto-keep (no KEEP = OLD NEW prompt)
# + the TR 8O8 and LIVE KIT kits from Ensoniq's factory drum disk 9
# (tools/fetch.sh sounds), with mute groups preset in their wavesamples.
# Writes build/test/EPS249_DRUMS.hfe (Gotek) and .img (MAME).
# docs/HARDWARE_TESTS.md -> Drum disk.
set -e
cd "$(dirname "$0")/.."
TR808_GROUPS="G2-A#2=1,C2-C#2=2"     # hats choke each other; the 808 kick cuts itself
LIVE_GROUPS="F#3-A#3=3"              # closed and pedal hat choke the open hat
SWING="16:mpc:58"                    # QUANTIZE 1/16, SWING% 58 at power-on
for ext in hfe img; do
    python3 tools/mkcodearea.py build/eps_os_249.bin -o build/test/drums.json \
        --pages --swing "$SWING" --auto-keep --disk build/hfe/EPS249OS.hfe build/test/drums_os.$ext
    python3 tools/epstool.py add build/test/drums_os.$ext build/sounds/DRMSET09.GKH 1 build/test/drums1.$ext
    python3 tools/epstool.py add build/test/drums1.$ext build/sounds/DRMSET09.GKH 2 build/test/drums2.$ext
    python3 tools/epstool.py groups build/test/drums2.$ext 1 "$TR808_GROUPS" build/test/drums3.$ext >/dev/null
    python3 tools/epstool.py groups build/test/drums3.$ext 2 "$LIVE_GROUPS" build/test/EPS249_DRUMS.$ext >/dev/null
    rm build/test/drums_os.$ext build/test/drums1.$ext build/test/drums2.$ext build/test/drums3.$ext
done
python3 tools/epstool.py ls build/test/EPS249_DRUMS.hfe
python3 tools/epstool.py groups build/test/EPS249_DRUMS.hfe 1
python3 tools/epstool.py groups build/test/EPS249_DRUMS.hfe 2
