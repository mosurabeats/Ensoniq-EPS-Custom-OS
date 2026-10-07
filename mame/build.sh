#!/bin/sh
# Build MAME's EPS driver with our patches (eps.patch) into build/mame/src.
# Needs git, a C++17 compiler, python3, make, and the SDL2/ALSA/fontconfig
# development packages. Takes a while (one driver only).
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SRC=${MAME_SRC:-$ROOT/build/mame/src}
COMMIT=a2b6ba2d4be70dabf7ff7a642749dda0c6e70498   # MAME 0.289 development tree

if [ ! -d "$SRC/.git" ]; then
    mkdir -p "$SRC"
    git -C "$SRC" init -q
    git -C "$SRC" remote add origin https://github.com/mamedev/mame.git
    git -C "$SRC" fetch --depth 1 origin "$COMMIT"
    git -C "$SRC" checkout -q FETCH_HEAD
fi
if git -C "$SRC" apply --check "$ROOT/mame/eps.patch" 2>/dev/null; then
    git -C "$SRC" apply "$ROOT/mame/eps.patch"
fi
cd "$SRC"
nice make SUBTARGET=eps SOURCES=src/mame/ensoniq/esq5505.cpp NOWERROR=1 \
    NO_USE_PORTAUDIO=1 NO_USE_PIPEWIRE=1 USE_QTDEBUG=0 TOOLS=0 -j"${JOBS:-4}"
echo "built $SRC/eps"
