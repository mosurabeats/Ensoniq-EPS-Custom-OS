| SP sampling mode (resident, 0xFF5214: the tail of a boot-only routine).
|
| When SAMPLE RATE changes, the OS sets FILTER CUTOFF from a ROM table
| (overlay 2, 0xFFE20E: about 0.36 x the rate from 15.6 kHz up, so little
| aliasing). Picking 26.04 kHz, the E-mu SP-1200's own rate (EPS setting
| 27: 625 kHz / 24), gives the widest filter instead, 20.0 KHZ: far above
| that rate's 13 kHz limit, so the input aliases like the SP-1200's. Every
| other rate is stock, and FILTER CUTOFF can still be set by hand after.
| tools/mkswing.py patches 0xFFE20E (overlay 2, in the OS file) to put the
| rate in d0 and the ROM table in a0, call here, and store d1.
        .equ    SP_RATE,    27          | 26.04 kHz
        .equ    FILTER_MAX, 11          | 20.0 KHZ (the stock maximum)
        .text
        .globl  spf
spf:    move.b  0(a0,d0.w),d1           | the stock choice
        cmpi.b  #SP_RATE,d0
        bne.s   1f
        moveq   #FILTER_MAX,d1
1:      rts
