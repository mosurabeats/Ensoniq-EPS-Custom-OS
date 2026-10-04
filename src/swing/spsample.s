| Sampling (overlay 2, 0xFFFD84-0xFFFE0D: where MSB ADJUSTMENT was; that
| service command now does nothing, like DC OFFSET ADJUSTMENT). Static
| edits to the OS file (tools/mkswing.py): nothing here is installed at
| boot, and it's in the window exactly when overlay 2 is (sampling).
|
| FILTER CUTOFF up to 50 kHz. The sampling filter's cutoff is set by a 4-bit
| counter N (docs/ANALYSIS.md -> Sampling filter hardware): cutoff =
| 10 MHz / (2 x (17 - N)) / 50. The stock OS uses N = 1-12 (6.25-20.0 kHz);
| N = 13, 14, 15 give 25.0, 33.3 and 50.0 kHz, the widest the hardware can
| do. FILTER CUTOFF (0xFF0212) becomes a choice of 15:
| * etab replaces the ROM's filter table (0xC0704E) at both places that
|   read it (0xFFE388, 0xFFE640);
| * the sampling page (record 0xFFC23A, resident) uses sindex, a copy of
|   the ROM's (0xC028A6) with our FILTER CUTOFF descriptor; the OS's code
|   that names its first and last entry (0xFF31A6, 0xFF323E, 0xFF3248)
|   names ours.
| Labels drop " KHZ" to fit (the ROM's one-cell "digit." codes: ! 0. # 1.
| % 2. ( 3. ) 4. : 5. ; 6. [ 7. \ 8. ] 9.).
|
| SP sampling mode: when SAMPLE RATE changes the OS picks FILTER CUTOFF
| from a ROM table (0xFFE20E: about 0.36 x the rate, little aliasing). At
| 26.04 kHz, the E-mu SP-1200's own rate (EPS setting 27: 625 kHz / 24),
| spf picks 20.0 KHZ instead, far above that rate's 13 kHz limit; every
| other rate is stock, and FILTER CUTOFF can be set by hand after (up to
| 50.0). 0xFFE20E is rewritten in place to put the rate in d0 and the ROM
| table in a0, call spf and store d1.
| Address words of our own data: low word (ORG16, --defsym),
| as two bytes (a .word of a symbol difference becomes a "broken word").
        .macro  aw sym
        .byte   (\sym-etab+ORG16)>>8, (\sym-etab+ORG16)&0xFF
        .endm
        .text
        .globl  etab, sindex, sindex_last, spf
        .equ    SP_RATE,    27          | 26.04 kHz
        .equ    FILTER_SP,  11          | 20.0 KHZ
| E = 0x28 | (N & 8) << 1 | (N & 7), N = 1-15.
etab:   .byte   0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F
        .byte   0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F, 0
| The sampling page: the ROM's entries, ours for FILTER CUTOFF.
sindex: .word   0x28D2, 0x28DA
        aw      fdesc
        .word   0x28EA, 0x28F2
sindex_last:
        .word   0x28FA
fdesc:  .byte   0x02, 0x0E              | as the ROM's (0xC028E2): a choice
        aw      fchoices
        .word   0x0212                  | FILTER CUTOFF
        .word   0x19F6                  | "FILTER CUTOFF" (ROM message)
fchoices:
        .long   flabels
        .byte   3, 15                   | width, count
flabels:
        .asciz  ";25"                   | 6.25
        .asciz  ";67"                   | 6.67
        .asciz  "[14"                   | 7.14
        .asciz  "[69"                   | 7.69
        .asciz  "\\33"                  | 8.33
        .asciz  "]09"                   | 9.09
        .asciz  "1!0"                   | 10.0
        .asciz  "1#1"                   | 11.1
        .asciz  "1%5"                   | 12.5
        .asciz  "1)3"                   | 14.3
        .asciz  "1;7"                   | 16.7
        .asciz  "2!0"                   | 20.0
        .asciz  "2:0"                   | 25.0
        .asciz  "3(3"                   | 33.3
        .asciz  "5!0"                   | 50.0
        .balign 2

| d0 = SAMPLE RATE, a0 = the ROM's rate -> filter table: d1 = the filter.
spf:    move.b  0(a0,d0.w),d1           | the stock choice
        cmpi.b  #SP_RATE,d0
        bne.s   1f
        moveq   #FILTER_SP,d1
1:      rts
fend:
