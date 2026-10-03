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

## Still missing

* **Boot ROM image** (U26/U27, 2 × 27256). It holds the display text, TRAP
  layer, parameter descriptors and sampling tables. Best source: dump the
  EPROMs of our own unit with any 27C256-capable programmer and compare the
  CRCs above.
* **XR-1008 datasheet** (Exar switched-capacitor low-pass) for the
  clock-to-cutoff ratio.
* **ES5504 (DOC II) register map**, to confirm which register holds the
  channel-assign (CA) bits.
* **EPS MIDI SysEx / parameter spec** (Ensoniq published one; Transoniq
  Hacker reprinted parts of it). Would name the parameter numbers.
