| ------------------------------------------------------------------ tune
| TUNE (Edit, 4 Pitch, ◄ once: after the ROM's entries): "TUNE=-5". Each
| ▲ / ▼ moves the edit wavesample a semitone up / down, by moving its ROOT
| KEY the other way (a higher root plays lower). Its total is kept in the
| wavesample record's spare byte +0x11D (bits 7-3, as 13-bit sample RAM
| keeps them: -16..+15; 0 in the ROM's new-wavesample template 0xC02DA4,
| so a new sample starts at +0), saved with the instrument; the stock OS
| ignores it. COPY WAVESAMPLE, CHOP and CRUSH copy it with the ROOT KEY.
| With WS=ALL the OS calls us once per wavesample: each moves by one.
|
| The entry is our parameter type (CHOP_TYPE, src/swing/chop.s), shared
| with CHOP: x17_show / x17_edit pick by descriptor. fp = the wavesample
| record + W_TUNE.
        .equ    W_TUNE,     0x11D
        .equ    TUNE_MIN,   -16
        .equ    TUNE_MAX,   15
        .equ    CHANGED,    0x44E0      | the OS's "a value changed" (redraws)
        .equ    TUNE_DESC16, tune_desc-wmagic+REGION16
        .balign 2                       | (chop.s ends with a byte)

x17_show:
        cmpa.w  #TUNE_DESC16,a3
        bne     chop_show
        move.b  (a6),d0
        asr.b   #3,d0                   | -16..+15
        lea     tune_txt(pc),a2
        moveq   #'+',d1
        tst.b   d0
        bpl.s   1f
        moveq   #'-',d1
        neg.b   d0
1:      move.b  d1,(a2)+
        ext.w   d0
        ext.l   d0
        divu.w  #10,d0
        tst.w   d0
        beq.s   2f
        add.b   #'0',d0
        move.b  d0,(a2)+
2:      swap    d0
        add.b   #'0',d0
        move.b  d0,(a2)+
        clr.b   (a2)
        lea     tune_txt(pc),a2
        jmp     SHOW_TEXT.w

| d7: > 0 up a semitone, < 0 down, 0 (the slider): nothing.
x17_edit:
        cmpa.w  #TUNE_DESC16,a3
        bne     chop_edit
        movem.l d0-d1/d4,-(sp)
        move.b  (a6),d4
        asr.b   #3,d4
        moveq   #1,d1                   | the step
        tst.w   d7
        beq.s   9f
        bpl.s   1f
        moveq   #-1,d1
1:      add.b   d1,d4
        cmpi.b  #TUNE_MIN,d4
        blt.s   9f
        cmpi.b  #TUNE_MAX,d4
        bgt.s   9f
        move.b  W_ROOT-W_TUNE(a6),d0
        sub.b   d1,d0                   | up a semitone: root one lower
        bmi.s   9f                      | (0-127: bit 7 clear)
        move.b  d0,W_ROOT-W_TUNE(a6)
        lsl.b   #3,d4
        move.b  d4,(a6)
        movem.l (sp)+,d0-d1/d4
        jmp     CHANGED.w               | as the OS's own edits: redraw
9:      movem.l (sp)+,d0-d1/d4
        jmp     NO_ERROR.w

tune_txt:
        .space  4
        .balign 2
