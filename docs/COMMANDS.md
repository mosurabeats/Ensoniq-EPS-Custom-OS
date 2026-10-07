# OS 2.49 command records

Generated with `python3 tools/bootrom.py commands build/bootrom/eps_boot_200.bin build/eps_os_249.bin`
(identical with boot ROM 2.40). See ANALYSIS.md → Boot ROM → Command records.

* **Handler**: `0xFF0000 |` the record's handler word. The OS runs in user
  mode, where `0x000000–0x00FFFF` mirrors OS RAM, so `7F88` is `FF7F88`.
  `FF4B54` is a do-nothing handler shared by several records.
* **Overlay**: flags bits 15–12 minus 8, for handlers in the overlay window.
* The record's other words are three button handlers and a 0.

| Record | Command | Msg | Handler | Overlay | Flags |
|---|---|---|---|---|---|
| `FFC43C` | CREATE NEW SEQUENCE | `0CB2` | `FFE2FA` | 0 | `8100` |
| `FFC44A` | COPY SEQUENCE | `0CD6` | `FFE8AE` | 0 | `8100` |
| `FFC458` | DELETE SEQUENCE | `0CC6` | `FFE924` | 0 | `8200` |
| `FFC466` | SAVE CURRENT SEQUENCE | `0ECD` | `FF7F7C` |  | `8200` |
| `FFC474` | SAVE SONG + ALL SEQS | `0EE3` | `FF4D82` |  | `8200` |
| `FFC482` | RENAME SONG/SEQUENCE | `0F18` | `FFE9E8` | 0 | `8200` |
| `FFC490` | SEQUENCER INFORMATION | `0F58` | `FFE9DC` | 0 | `8100` |
| `FFC49E` | ERASE SONG + ALL SEQS | `0F2D` | `FFE9C0` | 0 | `8000` |
| `FFC4AC` | APPEND SEQUENCE | `0CE4` | `FFE396` | 0 | `8100` |
| `FFC4BA` | CHANGE SEQUENCE LENGTH | `0CF4` | `FFE6CE` | 0 | `8100` |
| `FFC4C8` | EDIT SONG STEPS | `0EBD` | `FFFCBE` | 0 | `8200` |
| `FFC4D6` | QUANTIZE TRACK | `0C78` | `FFED96` | 0 | `8100` |
| `FFC4E4` | COPY TRACK | `0C5D` | `FFEB46` | 0 | `8100` |
| `FFC4F2` | ERASE/UNDEFINE TRACK | `0BC6` | `FFEC9A` | 0 | `8100` |
| `FFC500` | ERASE CONTROLLER | `0C02` | `FFED1C` | 0 | `8100` |
| `FFC50E` | ERASE KEY PRESSURE | `0C13` | `FFEC70` | 0 | `8100` |
| `FFC51C` | ERASE KEY RANGE | `0C26` | `FFEC82` | 0 | `8100` |
| `FFC52A` | ERASE PROGRAM CHANGES | `0BDB` | `FFEC8E` | 0 | `8100` |
| `FFC538` | MERGE TWO TRACKS | `0C4C` | `FFEC2A` | 0 | `8100` |
| `FFC546` | EVENT EDIT TRACK | `0C87` | `FFF68E` | 0 | `8200` |
| `FFC554` | TRANSPOSE TRACK | `0C68` | `FFEC50` | 0 | `8100` |
| `FFC562` | SCALE CONTROLLER | `0BF1` | `FFED40` | 0 | `8100` |
| `FFC570` | SHIFT TRACK BY CLOCKS | `0C36` | `FFED60` | 0 | `8100` |
| `FFC57E` | NO COMMANDS ON PAGE | `153B` | `FF4B54` |  | `0000` |
| `FFC58C` | CALIBRATE KEYBOARD | `132A` | `FF7F88` |  | `0000` |
| `FFC59A` | SOFTWARE INFORMATION | `13C2` | `FF4B54` |  | `0100` |
| `FFC5A8` | EXAMINE DOS STATUS | `1640` | `FF7FC6` |  | `0200` |
| `FFC5B6` | EXAMINE ANALOG INPUTS | `1499` | `FFBE84` |  | `0200` |
| `FFC5C4` | MSB ADJUSTMENT | `154F` | `FFFD82` | 2 | `A000` |
| `FFC5D2` | DC OFFSET ADJUSTMENT | `09D6` | `FF4B54` |  | `A100` |
| `FFC5E0` | CREATE NEW INSTRUMENT | `169A` | `FF4CEC` |  | `0115` |
| `FFC5EE` | COPY INSTRUMENT | `16BE` | `FF4CF6` |  | `0112` |
| `FFC5FC` | DELETE INSTRUMENT | `16A2` | `FF4D16` |  | `009C` |
| `FFC60A` | SAVE INSTRUMENT | `1718` | `FF4D46` |  | `0100` |
| `FFC618` | SAVE BANK | `171E` | `FF4D5A` |  | `0100` |
| `FFC626` | CREATE PRESET | `15DE` | `FF4DD0` |  | `01C4` |
| `FFC634` | CREATE NEW LAYER | `16A8` | `FF4B96` |  | `0016` |
| `FFC642` | COPY LAYER | `16CA` | `FF4BE8` |  | `0198` |
| `FFC650` | DELETE LAYER | `16E2` | `FF4CCE` |  | `0097` |
| `FFC65E` | EDIT PITCH TABLE | `16B0` | `FF4B54` |  | `A200` |
| `FFC66C` | COPY PITCH TABLE | `16D0` | `FFFED4` | 2 | `A100` |
| `FFC67A` | DELETE PITCH TABLE | `16E8` | `FFFEE8` | 2 | `A000` |
| `FFC688` | EXTRAPOLATE PITCH TBL | `1480` | `FFFEBE` | 2 | `A200` |
| `FFC696` | CREATE NEW WAVESAMPLE | `16B6` | `FF4C28` |  | `0099` |
| `FFC6A4` | COPY WAVESAMPLE | `16D6` | `FF4C6E` |  | `019B` |
| `FFC6B2` | DELETE WAVESAMPLE | `16DC` | `FF4C96` |  | `009A` |
| `FFC6C0` | WAVESAMPLE INFORMATION | `069E` | `FF4B54` |  | `0100` |
| `FFC6CE` | TRUNCATE WAVESAMPLE | `06AC` | `FFE7D2` | 1 | `909E` |
| `FFC6DC` | CROSS FADE LOOP | `06F4` | `FFF368` | 1 | `92A6` |
| `FFC6EA` | REVERSE CROSS FADE | `0710` | `FFF46C` | 1 | `92A9` |
| `FFC6F8` | ENSEMBLE CROSS FADE | `0718` | `FFF4D6` | 1 | `92AA` |
| `FFC706` | BOWTIE CROSS FADE LOOP | `0728` | `FFF6E0` | 1 | `92AB` |
| `FFC714` | BIDIRECTIONAL X-FADE | `0732` | `FFF650` | 1 | `92C3` |
| `FFC722` | MAKE LOOP LONGER | `0720` | `FFF502` | 1 | `92AC` |
| `FFC730` | SYNTHESIZED LOOP | `0752` | `FFF8C8` | 1 | `92C2` |
| `FFC73E` | CONVERT SAMPLE RATE | `0702` | `FFF08E` | 1 | `9200` |
| `FFC74C` | COPY WAVE PARAMETERS | `15FA` | `FF4AF4` |  | `0100` |
| `FFC75A` | NORMALIZE GAIN | `06EE` | `FFE714` | 1 | `90C1` |
| `FFC768` | VOLUME SMOOTHING | `074C` | `FFEF34` | 1 | `91AF` |
| `FFC776` | MIX WAVESAMPLES | `073A` | `FFEC30` | 1 | `912D` |
| `FFC784` | MERGE WAVESAMPLES | `0740` | `FFE902` | 1 | `912E` |
| `FFC792` | SPLICE WAVESAMPLES | `0746` | `FFE8DE` | 1 | `912E` |
| `FFC7A0` | FADE IN | `06D6` | `FFE682` | 1 | `91A7` |
| `FFC7AE` | FADE OUT | `06DC` | `FFE6AA` | 1 | `91A8` |
| `FFC7BC` | CLEAR DATA | `06B2` | `FFE5B0` | 1 | `919F` |
| `FFC7CA` | COPY DATA | `06BE` | `FFE5C4` | 1 | `9120` |
| `FFC7D8` | REPLICATE DATA | `06FC` | `FFE886` | 1 | `91A5` |
| `FFC7E6` | REVERSE DATA | `06C4` | `FFE6D2` | 1 | `91A4` |
| `FFC7F4` | INVERT DATA | `06CA` | `FFE6E6` | 1 | `91A3` |
| `FFC802` | ADD DATA | `06E2` | `FFE63E` | 1 | `9121` |
| `FFC810` | SCALE DATA | `06E8` | `FFE6FA` | 1 | `91A2` |
