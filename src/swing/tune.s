| ------------------------------------------------------------------ tune
| TUNE (Edit, 9 Layer, ◄ twice: before HIT): "TUNE=-5". Each ▲ / ▼ moves
| every wavesample of the layer a semitone up / down, by moving its ROOT
| KEY the other way (a higher root plays lower). The total is kept in the
| layer record's spare byte +0x2F (the low byte of the key-20 map slot,
| whose high byte is HIT; bits 7-3, as 13-bit sample RAM keeps them:
| -16..+15), so it's saved with the instrument and the stock OS ignores
| it. ROOT KEY itself still works per wavesample; TUNE only counts its
| own steps. With LYR=ALL the OS calls us once per layer.
|
| The entry is our parameter type (CHOP_TYPE, src/swing/chop.s), shared
| with CHOP: x17_show / x17_edit pick by descriptor. fp = the layer
| record + L_TUNE.
        .equ    L_TUNE,     0x2F
        .equ    L_FIRST,    0x06        | layer record: its first wavesample
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
        movem.l d0-d6/a0-a5,-(sp)
        move.b  (a6),d4
        asr.b   #3,d4
        moveq   #1,d5                   | the step
        tst.w   d7
        beq.s   9f
        bpl.s   1f
        moveq   #-1,d5
1:      add.b   d5,d4
        cmpi.b  #TUNE_MIN,d4
        blt.s   9f
        cmpi.b  #TUNE_MAX,d4
        bgt.s   9f
        lea     -L_TUNE(a6),a4          | the layer record
        move.w  EDIT_INST.w,d1
        jsr     INST_BASE.w             | a1 = the instrument's data
        moveq   #0,d6                   | pass 0: check every ROOT KEY stays
2:      moveq   #0,d0                   | 0-127; pass 1: move them
        move.b  L_FIRST(a4),d0
3:      tst.b   d0
        beq.s   6f
        jsr     WS_OFF.w
        lea     0(a1,d1.l),a3
        move.b  W_ROOT(a3),d2
        sub.b   d5,d2                   | up a semitone: root one lower
        bmi.s   9f                      | (0-127: bit 7 clear)
        tst.b   d6
        beq.s   5f
        move.b  d2,W_ROOT(a3)
5:      move.b  W_NEXT(a3),d0
        bra.s   3b
6:      tst.b   d6
        bne.s   7f
        moveq   #1,d6
        bra.s   2b
7:      lsl.b   #3,d4
        move.b  d4,(a6)
        movem.l (sp)+,d0-d6/a0-a5
        jmp     CHANGED.w               | as the OS's own edits: redraw
9:      movem.l (sp)+,d0-d6/a0-a5
        jmp     NO_ERROR.w

tune_txt:
        .space  4
        .balign 2
