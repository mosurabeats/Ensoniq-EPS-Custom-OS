# Ensoniq EPS Custom OS

A patch-based custom OS for the original Ensoniq EPS, built on OS 2.49. The
first targets are **mute groups per instrument**, an **anti-aliasing filter OUT** option for sampling, and **MPC-style swing/quantize**. See
[docs/ROADMAP.md](docs/ROADMAP.md) for the full feature list and
[docs/ANALYSIS.md](docs/ANALYSIS.md) for the reverse-engineering notes.

The EPS loads its OS from floppy at every boot, so trying a custom OS is safe.
If something goes wrong, boot the stock disk.

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
tools/fetch.sh sounds && python3 mame/test_mutegroups.py   # mute groups with a real kit
python3 mame/test_loop_record.py                         # loop recording, auto-keep
```

`tools/epstool.py add OS.img SOUNDS.gkh 1 OUT.img` copies an instrument onto
a disk (reads `.img`, `.ede`, `.hfe` and Gotek `.gkh`).

## Code area and test disks

Our resident code runs from the top 4 KB of sample RAM, loaded at boot from the OS file
(docs/ANALYSIS.md → Code area). Build a test disk with mute groups:

```sh
python3 tools/mkcodearea.py build/eps_os_249.bin -o build/test/codearea_mute.json \
    --groups "1=1,2:A0-B3=2,3=1" --disk build/hfe/EPS249OS.hfe build/test/EPS249_MUTETEST.hfe
```

Use `.img` instead of `.hfe` as the output name for a disk to boot in MAME.

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
