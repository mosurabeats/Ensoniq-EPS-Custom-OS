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

Ensoniq's OS binaries and disk images are not committed (see `.gitignore`).
Put your own copy of `eps249os.ede` in `build/`. The steps to get it from the
Chicken Systems installer are in docs/ANALYSIS.md.

## Building a hook

```sh
# assemble src/mutegroup.s into a code cave and hook the note-on routine
python3 tools/mkhook.py src/mutegroup.s build/eps_os_249.bin \
    --org <CAVE_ADDR> --hook 0xFFACA4 --len 8 --entry mute_hook \
    --set mute_table=0101000000000000 -o patches/mutegroup.json
```

The code-cave address is still open. See docs/ROADMAP.md.

## Filter probe disks

```sh
python3 tools/filterprobe.py build/eps249os.ede build/filterprobe   # 8 test disks
```

Each disk forces one setting of the sampling filter-select lines. See
docs/ROADMAP.md, feature 2.
