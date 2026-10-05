# Ensoniq EPS Custom OS

A patch-based custom OS for the original Ensoniq EPS, built on OS 2.49. The
first targets are **mute groups per instrument**, an **anti-aliasing filter OUT** option for sampling, and **MPC-style swing/quantize**. See
[docs/ROADMAP.md](docs/ROADMAP.md) for the full feature list and
[docs/ANALYSIS.md](docs/ANALYSIS.md) for the reverse-engineering notes.

The EPS loads its OS from floppy at every boot, so trying a custom OS is safe.
If something goes wrong, boot the stock disk.

**Using it:** [docs/QUICKSTART.md](docs/QUICKSTART.md) is the quick start
guide to every new function (mute groups, HIT, TUNE, QUANTIZE/SWING%, loop
undo, CHOP, CRUSH, the sampling filter and SP mode) on the current disk,
`EPS249_NEXT`; `tools/mkguide.py` makes it a PDF.

## Tools

```sh
python3 tools/epstool.py ls      eps249os.ede              # list disk
python3 tools/epstool.py extract eps249os.ede 0 os.bin     # pull the OS file
python3 tools/epstool.py patch   os.bin patches/x.json os_new.bin
python3 tools/epstool.py replace eps249os.ede 0 os_new.bin custom.img   # Gotek/HxC image
python3 tools/epstool.py replace eps249os.ede 0 os_new.bin custom.ede   # for EDE writers
tools/disasm.sh os.bin > os.dis                            # m68k disassembly @ 0xFF2000
```

Patches are JSON files with CPU addresses, the bytes expected there, and the
replacement bytes. A patch refuses to apply if any expected bytes don't match,
which catches a wrong OS version.

```json
{"name": "example", "edits": [{"addr": "0xFF221C", "expect": "4E75", "data": "4E71"}]}
```

## Not in this repo

Ensoniq's OS binaries, disk images and the reference PDFs are not committed
(see `.gitignore`). `tools/fetch.sh` downloads them into `build/` and checks
the OS checksum. Sources are listed in [docs/RESOURCES.md](docs/RESOURCES.md).

```sh
tools/fetch.sh        # build/eps249os.ede, eps_os_249.bin, os_versions/, refs/
```

`epstool.py` also reads HxC/Gotek `.hfe` images (`ls`, `extract`, `hfe2img`).

The boot ROM isn't fetched. Put the EPROM dumps in `build/bootrom/` (see
docs/RESOURCES.md), then:

```sh
python3 tools/bootrom.py msg      build/bootrom/eps_boot_200.bin 14eb   # 'TUNING KBD - HANDS OFF'
python3 tools/bootrom.py annotate build/bootrom/eps_boot_200.bin build/eps_os_249.dis > build/eps_os_249.ann.dis
python3 tools/bootrom.py commands build/bootrom/eps_boot_200.bin build/eps_os_249.bin   # docs/COMMANDS.md
```

## Tests

```sh
pip install unicorn
python3 -m unittest discover tests     # needs build/ OS + boot ROM
```

`tools/emu.py` runs OS routines and our hooks in a 68000 emulator. See
docs/ANALYSIS.md → Emulator tests.

Whole-machine tests run in a patched MAME (docs/MAME.md):

```sh
mame/build.sh                                   # once: MAME's EPS driver + our fixes
mame/run.sh build/test/EPS249_MUTETEST.img      # boot a disk, print the display
tools/fetch.sh sounds && python3 mame/test_resident.py    # the hardware build (13-bit sample RAM, ROM 2.40)
python3 mame/test_swing_hw.py                            # the swing build: loop recording, swing, mute, commands
python3 mame/test_undo_hw.py                             # the swing build: loop undo (RECORD while loop recording)
python3 mame/test_chop_hw.py                             # the swing build: CHOP (Edit, 8 Wave)
python3 mame/test_tune_hw.py                             # the swing build: TUNE (Edit, 9 Layer)
python3 mame/test_crush_hw.py                            # the swing build: CRUSH (Edit, 8 Wave)
python3 mame/test_mutegroups.py                          # mute groups with a real kit (code area)
python3 mame/test_loop_record.py                         # loop recording, auto-keep
python3 mame/test_swing.py                               # swing quantize of LOOPED takes
python3 mame/test_undo.py                                # loop undo (RECORD while loop recording)
python3 mame/test_panel.py                               # MUTE GROUP / QUANTIZE set from the panel
```

`tools/epstool.py add OS.img SOUNDS.gkh 1 OUT.img` copies an instrument onto
a disk (reads `.img`, `.ede`, `.hfe` and Gotek `.gkh`).

## Hardware build: mute groups (`EPS249_MUTE`)

The EPS's sample RAM is 13 bits wide, so no code can run from it (the code
area below works only in MAME). `tools/mkmutetest.sh` builds the disk to
try on a real EPS: OS 2.49 with mute groups and the MUTE GROUP parameter
(6 Amp page), all in OS RAM (`tools/mkresident.py`, docs/ANALYSIS.md →
Resident build). Writes `build/test/EPS249_MUTE.hfe` (Gotek) and `.img`
(MAME). docs/HARDWARE_TESTS.md says what to try. It works on a real EPS.

`tools/mkswingtest.sh` builds `EPS249_NEXT`: mute groups, MPC-style loop
recording (QUANTIZE and SWING% on the Seq·Song page; the takes snap to the
swung grid at every loop wrap, KEEP = OLD NEW as usual) and HIT (FULL LEVEL
/ ONE-SHOT on the Layer page). Its first hardware test was `EPS249_SWING`
(commit dfea704). The code
borrows the sequence commands' part of the overlay window while they aren't
in use (`tools/mkswing.py`, docs/ANALYSIS.md → Swing build).

## Code area and test disks (emulator only)

Our resident code runs from the top 4 KB of sample RAM, loaded at boot from the OS file
(docs/ANALYSIS.md → Code area). Build a test disk with mute groups:

```sh
python3 tools/mkcodearea.py build/eps_os_249.bin -o build/test/codearea_mute.json \
    --groups "1=1,2:A0-B3=2,3=1" --disk build/hfe/EPS249OS.hfe build/test/EPS249_MUTETEST.hfe
```

Use `.img` instead of `.hfe` as the output name for a disk to boot in MAME.

Options: `--pages` (our parameters on the EPS's edit pages: FULL LEVEL,
ONE-SHOT and MUTE GROUP on the 6 Amp page, QUANTIZE and SWING% on the
sequencer page; with it
`--swing 16:mpc:58` only sets their power-on values), `--undo` (RECORD while
loop recording takes out the last notes played; on with `--swing` and
`--pages` too), `--auto-keep` (no KEEP = OLD NEW prompt). Without `--pages`:
`--groups` (mute groups per key, fixed at build time) and `--swing` per
instrument (`1=16:mpc:58,2=8:sp1200:63`). `tools/epstool.py groups` lists or
presets the mute groups in an instrument file on a disk. `tools/mkdrums.sh`
builds the drum disk with `--pages`; `tools/mkosdisk.sh` the same OS with no
sounds on it (`EPS249_CUSTOM`).

`.hfe` output keeps the stock disk's track layout and works on any Gotek
firmware. See docs/HARDWARE_TESTS.md for what to try on the EPS.

## Building a hook

```sh
# assemble src/mutegroup.s into a code cave and hook the note-on routine
python3 tools/mkhook.py src/mutegroup.s build/eps_os_249.bin \
    --org <CAVE_ADDR> --hook 0xFFACA4 --len 8 --entry mute_hook \
    --set mute_table=0101000000000000 -o patches/mutegroup.json
```

Hooks that must stay resident go into the code area instead (see above).

## Filter probe disks

```sh
python3 tools/filterprobe.py build/eps249os.ede build/filterprobe   # 16 test disks
```

Each disk forces one sampling-filter cutoff code N (0–15, 15 = widest). See
docs/ROADMAP.md, feature 2.
