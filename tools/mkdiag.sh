#!/bin/sh
# Hardware bisect disks: each adds one piece, so the first one that fails
# on a real EPS points at the culprit. All are OS 2.49, no sounds.
#   EPSDIAG1: the boot loader only (reads our image into the top of sample
#             memory, checks it, hooks nothing; FREE SYSTEM BLKS ~12 lower)
#   EPSDIAG2: + the mute group hook (old per-key form, no groups set)
#   EPSDIAG3: + auto-keep (an OS edit, no code area hook)
#   EPSDIAG4: + loop recording code (swing, undo: three sequencer hooks)
#   EPSDIAG5: everything (--pages: our edit-page parameters, FULL LEVEL,
#             ONE-SHOT) = EPS249_CUSTOM
# Writes build/test/EPSDIAG*.hfe (Gotek) and .img (MAME).
set -e
cd "$(dirname "$0")/.."
mk() {
    name=$1; shift
    for ext in hfe img; do
        python3 tools/mkcodearea.py build/eps_os_249.bin -o build/test/$name.json "$@" \
            --disk build/hfe/EPS249OS.hfe build/test/$name.$ext > /dev/null
    done
    echo "$name: $*"
}
mk EPSDIAG1 --bare
mk EPSDIAG2
mk EPSDIAG3 --auto-keep
mk EPSDIAG4 --undo --auto-keep
mk EPSDIAG5 --pages --swing 16:mpc:58 --auto-keep
