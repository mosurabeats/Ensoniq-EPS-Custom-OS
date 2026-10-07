| Shared addresses for the swing build (src/swing/*.s, tools/mkswing.py).
| abs.w addresses from 0x8000 up sign-extend to 0xFFxxxx (OS RAM).

        .equ    QUANT,      0x8174      | QUANTIZE choice (0-7: 1/4 .. 1/32T, 8: OFF)
        .equ    SWING,      0x8175      | SWING% (50-75; below 50: straight)
        .equ    FLAG,       0x8176      | our code is in the window (0xFF when in)
        .equ    DISP,       0x8177      | the overlay our code displaced
        .equ    OV_CUR,     0xC8D0      | the OS's current overlay
        .equ    OV_OURS,    3           | what OV_CUR says while ours is in
        .equ    MODE,       0x160A      | 0 play, 1 Command, 2 Edit
        .equ    MODE_CMD,   1
        .equ    HEAP_END,   0x165A      | long: our store starts 512 bytes above
        .equ    LOADER,     0x4E40      | overlay loader, d1 = overlay
