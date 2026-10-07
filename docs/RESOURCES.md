# External resources

`tools/fetch.sh` downloads everything in the first two tables into `build/`
(not committed). Checked 2026-10.

## OS images

| What | Where | Notes |
|---|---|---|
| EPS OS 2.49 (`EPS249OS.hfe`) | hxc2001.com `download/floppy_drive_emulator/QuickInstall_FloppyDiskImages.zip` → `SDHxCFE_Ensoniq_EPS.zip` | The base OS. The site rejects curl's default user agent, so the script sends a browser one |
| EPS OS 2.2, 2.45 | same zip (`EPS2_2OS.hfe`, `EPS245OS.hfe`) | For comparing routines across versions |
| EPS-16+ OS 1.00, 1.10, 1.19, 1.30 | same zip (`EPS100OS.hfe` … `EPS130OS.hfe`) | Named "EPS" but they are EPS-16+ OSes. Reference for how the 16+ does filter OUT |
| EPS OS 2.49, second copy | archive.org `eps-os-v-249` (`EPS_OS_V249.img`) | Same OS file as the HxC one. The script checks this |
| EPS OS 2.4 boot disk | archive.org `EPS-BOOT-OS2_4` | Not fetched |

OS 2.49 file (`EPS-1 O.S.`, 85,504 bytes):
SHA-256 `01911d8f30e900892fdd1ddbc10bbc047836fb4785de6b87c8b69674edcb79e3`.

## Documents (archive.org)

| Item | Contents |
|---|---|
| `sm_Ensoniq_EPS_Schematics` | **EPS schematics**, 9 pages: power supply, display/keypad, main board 7501 (digital + analog) and 10002 (digital + analog). Source of the DUART pin map, analog mux and sampling-filter clock in ANALYSIS.md |
| `sm_Ensoniq_EPS_Service_Bulletins` | Service bulletins |
| `eps-16plus-schematics` | EPS-16+ schematics (11 pages, 200 dpi) |
| `sm_Ensoniq_EPS_16_Service_Manual` | EPS-16+ service manual |
| `ensoniq-eps-advanced-applications-guide` | EPS Advanced Applications Guide (80 pages) |

The schematic PDFs are scanned images. Use `pdfimages -j FILE.pdf out` to
get full-resolution pages.

## Code references

| What | Where |
|---|---|
| MAME `src/mame/ensoniq/esq5505.cpp` | EPS memory map, ROM set (`eps-l.bin` CRC32 `382beac1`, `eps-h.bin` CRC32 `d8747420`, 32 KB each). The driver doesn't boot |
| MAME `src/devices/sound/es5506.cpp` | ES5505/5506 voice registers. The EPS has an ES5504 (DOC II), which MAME doesn't model separately |

## Boot ROM (user-supplied, not committed)

Put the dumps in `build/bootrom/` and join them:

```sh
python3 tools/bootrom.py join build/bootrom/unknown/eps-h.bin build/bootrom/unknown/eps-l.bin \
    build/bootrom/eps_boot_200.bin
cp build/bootrom/v24/eps_os_24.bin build/bootrom/eps_boot_240.bin   # already joined
python3 tools/bootrom.py info build/bootrom/eps_boot_200.bin
```

| Set | Files | CRC32 (high / low) | Version word |
|---|---|---|---|
| 2.00 | `eps-h.bin`, `eps-l.bin` (= MAME `eps`) | `d8747420` / `382beac1` | `0x0200` |
| 2.40 | `eps_os_24_hi.bin`, `eps_os_24_lo.bin`, `eps_os_24.bin` (joined) | `2492aee1` / `31b25dc2` | `0x0228` |

Which set is in our unit is not known yet: `tools/bootrom.py info` on a dump
of U26/U27, or the version shown at power-up, would tell.

## Still missing

* **XR-1008 datasheet** (Exar switched-capacitor low-pass): the 50:1 ratio is
  known from the ROM, but not its maximum clock (N = 15 runs it at 2.5 MHz).
* **ES5504 (DOC II) register map**, to confirm which register holds the
  channel-assign (CA) bits.
* **EPS MIDI SysEx / parameter spec** (Ensoniq published one; Transoniq
  Hacker reprinted parts of it). Would name the parameter numbers.
