| ------------------------------------------------------------------ chop
| CHOP (Edit, 8 Wave, the last parameter: "CHOP=PRESS ENTER"): ENTER asks
| "CHOP INTO 16 SLICES?", ▲/▼ change the count (2-32), ENTER does it,
| CANCEL doesn't. The edit wavesample is cut into
| equal slices, each cut moved to the nearest zero crossing (the earlier
| one if two are as near; within a quarter slice and 127 samples), and
| each slice becomes a parameters-
| only copy of it (the OS's own COPY WAVESAMPLE, 0xFFA2D6: the sample data
| is shared, a copy costs 288 bytes) with:
| * SMPL START / SAMPLE END on the slice (loop points too), FORWARD-NO LOOP;
| * one key, from the wavesample's ROOT KEY up if that's in its key range
|   (else its lowest key; C2 if that's below the keyboard), ROOT KEY = that
|   key (the slice plays at its original pitch).
| The wavesample itself keeps its other keys. A layer's key map is built
| from its wavesamples' ranges in their order (ROM 0xC08F22: a later one
| wins), and the copies come after it. Every field we write is a high byte
| (13-bit sample RAM). docs/ANALYSIS.md -> CHOP.
        .equ    EDIT_INST,  0x169C      | Edit's instrument (record +66 layer, +68 ws)
        .equ    CUR_PAGE,   0xC08A      | the current page record
        .equ    WAVE_PAGE,  0xC0F2      | Edit 8 Wave
        .equ    SEL_INST,   0x1548      | the copy's source: instrument, layer, ws
        .equ    DST_INST,   0x1562      | its destination: instrument, layer
        .equ    COPY_DATA,  0x15ED      | 0: COPY = PARAMS ONLY
        .equ    SEQ_RUN,    0xBFD2      | the sequencer is running
        .equ    INST_BASE,  0xA4B0      | d1 = instrument -> a1 = its data
        .equ    INST_REC,   0xA4BA      | d1 = instrument -> a1 = its record
        .equ    LAYER_OFF,  0x83A0      | a1 = data, d0 = layer -> d1 = offset
        .equ    WS_OFF,     0x83A6      | a1 = data, d0 = ws -> d1 = offset
        .equ    KEYMAP,     0x83D0      | a1 = data, a0 = layer offset: rebuild
        .equ    CHECK_WS,   0x2F1C      | carry, a2 = message: no edit WS
        .equ    COPY_WS,    0xA2D6      | carry, d0 = error / d0 = the new ws
        .equ    YESNO,      0xA6DA      | a2 = message; carry: CANCEL
        .equ    SHOW,       0x23FC      | a2 = message
        .equ    ERR_MSG,    0x4A8C      | d0 = error -> a2 = message
        .equ    ENTER_EDIT, 0x2110      | Edit mode's own ENTER
        .equ    MSG_STOPSEQ, 0x0D5A     | "STOP SEQUENCER FIRST"
        .equ    MSG_ABORTED, 0x137B     | "COMMAND ABORTED"
        .equ    W_NEXT,     0x06        | wavesample record: next in the layer
        .equ    W_OWNER,    0x22        | whose data it plays (0: its own)
        .equ    W_ROOT,     0xAA
        .equ    W_MODE,     0xEE        | 0 FORWARD-NO LOOP
        .equ    W_START,    0xF0        | sample << 9, movep.l (high bytes)
        .equ    W_END,      0xF8
        .equ    W_LSTART,   0x100
        .equ    W_LEND,     0x108
        .equ    W_KEYLO,    0x112
        .equ    W_KEYHI,    0x114
        .equ    W_DATA,     0x120       | the sample data follows the record
        .equ    SNAP_MAX,   127         | samples (4 ms at 31 kHz)
        .equ    KEY_C2,     36          | the keyboard's lowest key
        .equ    CHOP_SLOT,  wave_index+2*16-wmagic+REGION16
        .equ    CHOP_TYPE,  0x17        | a parameter type no page uses
        .equ    GET_MSG,    0x1790      | carry: none; a2 = kind, d2 = button
        .equ    BUTTON,     0x1A88      | (kind) a panel button
        .equ    B_UP,       0x20
        .equ    B_DOWN,     0x21
        .equ    B_CANCEL,   0x23
        .equ    B_ENTER,    0x25
        .equ    SHOW_TEXT,  0x3838      | a parameter's value: the text at a2
        .equ    NO_ERROR,   0x9FBE

| The CHOP entry's value and edit (types 0x17 while ours is in).
chop_show:
        lea     press(pc),a2
        jmp     SHOW_TEXT.w
chop_edit:
        jmp     NO_ERROR.w

| 0xFFD064: Edit mode's ENTER (button 0x25). On CHOP: chop; else the OS's.
chop_enter:
        cmpi.w  #WAVE_PAGE,CUR_PAGE.w
        bne.s   1f
        cmpi.w  #CHOP_SLOT,WAVE_PAGE+4.w
        beq.s   chop
1:      jmp     ENTER_EDIT.w

chop:   movem.l d0-d7/a0-a6,-(sp)
        movea.w #MSG_STOPSEQ,a2
        tst.w   SEQ_RUN.w
        bne     show
        jsr     CHECK_WS.w              | (a2 = the instrument's record; uses a6)
        bcs     show
        lea     cv(pc),a6
        move.w  EDIT_INST.w,C_INST(a6)
        move.w  66(a2),C_LAYER(a6)
        move.w  68(a2),C_SRC(a6)
| "CHOP INTO nn SLICES?": ▲/▼, ENTER or CANCEL (as the OS's own YES/NO
| prompt, 0xFFA6DA: shown again when the message timer runs out).
1:      moveq   #0,d0
        move.b  chop_n(pc),d0
        move.b  slices(pc,d0.w),d0
        move.w  d0,C_N(a6)
        lea     ask_n(pc),a0
        bsr     digits
        lea     ask(pc),a2
        move.l  a2,d0
        movea.w d0,a2
        jsr     SHOW.w
        moveq   #-1,d0
        trap    #8
2:      moveq   #0,d0
        trap    #5
        andi.b  #0x80,d0
        beq.s   1b                      | timer: show it again
        jsr     GET_MSG.w
        bcs.s   2b
        cmpa.w  #BUTTON,a2
        bne.s   2b
        lea     chop_n(pc),a0
        cmpi.b  #B_UP,d2
        bne.s   3f
        cmpi.b  #8,(a0)
        bcc.s   1b
        addq.b  #1,(a0)
        bra.s   1b
3:      cmpi.b  #B_DOWN,d2
        bne.s   4f
        tst.b   (a0)
        beq.s   1b
        subq.b  #1,(a0)
        bra.s   1b
4:      cmpi.b  #B_ENTER,d2
        beq.s   5f
        cmpi.b  #B_CANCEL,d2
        bne.s   2b
        movea.w #MSG_ABORTED,a2
        bra     show
slices: .byte   2, 3, 4, 6, 8, 12, 16, 24, 32
        .balign 2

| The cut points, from the wavesample as it is now (the copies are added at
| the end of the instrument: nothing we read moves).
5:      lea     cv(pc),a6               | (the OS's message loop uses a6)
        bsr     src_rec                 | a3 = the wavesample, a1 = data
        moveq   #0,d0                   | slices from its ROOT KEY up when
        move.b  W_ROOT(a3),d0           | that's one of its keys (a sample
        cmp.b   W_KEYLO(a3),d0          | over the whole keyboard: where it
        bcs.s   3f                      | was put), else from its lowest
        cmp.b   W_KEYHI(a3),d0          | key; not below the keyboard
        bls.s   4f
3:      move.b  W_KEYLO(a3),d0
4:      cmpi.w  #KEY_C2,d0
        bcc.s   1f
        moveq   #KEY_C2,d0
1:      move.w  d0,C_KEY(a6)
        move.w  #109,d1
        sub.w   d0,d1                   | keys left up to 108
        cmp.w   C_N(a6),d1
        bcc.s   2f
        move.w  d1,C_N(a6)
2:      lea     W_DATA(a3),a5           | its sample data (or the one it plays)
        moveq   #0,d0
        move.b  W_OWNER(a3),d0
        beq.s   3f
        jsr     WS_OFF.w
        lea     0(a1,d1.l),a5
        lea     W_DATA(a5),a5
3:      movep.l W_START(a3),d4
        lsr.l   #8,d4
        lsr.l   #1,d4                   | first sample
        movep.l W_END(a3),d5
        lsr.l   #8,d5
        lsr.l   #1,d5
        addq.l  #1,d5                   | after the last
        move.l  d5,d0
        sub.l   d4,d0                   | length
        move.w  C_N(a6),d3
        bsr     divl                    | d0 = length / n, d1 = remainder
        cmpi.l  #2,d0
        bcs     done                    | too short to chop
        lea     bounds(pc),a4
        move.l  d4,(a4)+
        move.l  d0,d6                   | q
        move.l  d6,d7
        lsr.l   #2,d7                   | how far to look for a crossing
        cmpi.l  #SNAP_MAX,d7
        bls.s   4f
        move.l  #SNAP_MAX,d7
4:      moveq   #0,d2                   | remainder sum
        move.w  d3,d0
        subq.w  #2,d0                   | n-1 inner points
        bmi.s   7f
5:      add.l   d6,d4
        add.w   d1,d2
        cmp.w   d3,d2
        bcs.s   6f
        sub.w   d3,d2
        addq.l  #1,d4
6:      bsr     snap                    | d4 -> a crossing
        move.l  a0,(a4)+
        dbra    d0,5b
7:      move.l  d5,(a4)                 | the end

| The copies: COPY WAVESAMPLE (params only) from the edit wavesample to
| its own layer, then the slice's fields.
        lea     SEL_INST.w,a0
        lea     saved(pc),a1
        move.l  (a0)+,(a1)+             | the OS's copy selection, put back
        move.w  (a0),(a1)+              | after
        move.l  DST_INST.w,(a1)+
        move.b  COPY_DATA.w,(a1)
        move.w  C_INST(a6),SEL_INST.w
        move.w  C_LAYER(a6),SEL_INST+2.w
        move.w  C_SRC(a6),SEL_INST+4.w
        move.w  C_INST(a6),DST_INST.w
        move.w  C_LAYER(a6),DST_INST+2.w
        clr.b   COPY_DATA.w
        clr.w   C_DONE(a6)
        lea     bounds(pc),a4
10:     move.w  C_DONE(a6),d0
        cmp.w   C_N(a6),d0
        bcc.s   20f
        jsr     COPY_WS.w
        bcs.s   19f
        move.w  C_INST(a6),d1           | the new one's record
        jsr     INST_BASE.w
        jsr     WS_OFF.w
        lea     0(a1,d1.l),a3
        move.l  (a4)+,d0                | start
        move.l  (a4),d1
        subq.l  #1,d1                   | end
        lsl.l   #8,d0
        add.l   d0,d0
        lsl.l   #8,d1
        add.l   d1,d1
        movep.l d0,W_START(a3)
        movep.l d0,W_LSTART(a3)
        movep.l d1,W_END(a3)
        movep.l d1,W_LEND(a3)
        clr.b   W_MODE(a3)
        move.w  C_KEY(a6),d0
        add.w   C_DONE(a6),d0
        move.b  d0,W_ROOT(a3)
        move.b  d0,W_KEYLO(a3)
        move.b  d0,W_KEYHI(a3)
        addq.w  #1,C_DONE(a6)
        bra.s   10b
19:     jsr     ERR_MSG.w                 | stopped (memory full ...)
        move.l  a2,-(sp)
        bra.s   21f
20:     lea     made_n(pc),a0           | "nn SLICES CREATED"
        move.w  C_DONE(a6),d0
        bsr     digits
        lea     made_n(pc),a2
        move.l  a2,d0
        movea.w d0,a2
        move.l  a2,-(sp)
21:     move.w  C_INST(a6),d1           | the key map from the new ranges
        jsr     INST_BASE.w
        move.w  C_LAYER(a6),d0
        jsr     LAYER_OFF.w
        movea.l d1,a0
        jsr     KEYMAP.w
        lea     saved(pc),a1
        lea     SEL_INST.w,a0
        move.l  (a1)+,(a0)+
        move.w  (a1)+,(a0)
        move.l  (a1)+,DST_INST.w
        move.b  (a1),COPY_DATA.w
        movea.l (sp)+,a2
show:   jsr     SHOW.w
done:   movem.l (sp)+,d0-d7/a0-a6
        rts

| a3 = the edit wavesample's record, a1 = the instrument's data.
src_rec:
        move.w  C_INST(a6),d1
        jsr     INST_BASE.w
        move.w  C_SRC(a6),d0
        jsr     WS_OFF.w
        lea     0(a1,d1.l),a3
        rts

| d0.l / d3.w -> d0.l, remainder d1.w (d0 < 2^24).
divl:   move.l  d0,d1
        clr.w   d1
        swap    d1
        divu.w  d3,d1                   | high word
        move.w  d1,-(sp)
        swap    d1                      | remainder: high half of the next
        move.w  d0,d1
        divu.w  d3,d1
        moveq   #0,d0
        move.w  (sp)+,d0
        swap    d0
        move.w  d1,d0
        swap    d1                      | remainder
        rts

| a0 = the zero crossing (a sign change between two samples) nearest d4,
| the earlier one of two as near, at most d7 (< 128) samples away; d4
| itself if there's none. a5 = the sample data.
snap:   movem.l d0-d3/d5,-(sp)
        movea.l d4,a0
        move.w  d7,d1
        moveq   #0,d5                   | distance
1:      move.l  d4,d2
        sub.l   d5,d2
        bsr.s   cross
        beq.s   2f
        move.l  d4,d2
        add.l   d5,d2
        bsr.s   cross
        beq.s   2f
        addq.l  #1,d5
        dbra    d1,1b
        bra.s   9f
2:      movea.l d2,a0
9:      movem.l (sp)+,d0-d3/d5
        rts
| Z if the sign changes from sample d2-1 to d2. Uses d0, d3.
cross:  move.l  d2,d0
        add.l   d0,d0
        move.w  -2(a5,d0.l),d3
        move.w  0(a5,d0.l),d0
        eor.w   d3,d0
        spl     d0
        tst.b   d0
        rts

| d0.w (1-99) -> two characters at a0 (a space for the tens if 0).
digits: ext.l   d0
        divu.w  #10,d0
        add.b   #'0',d0
        cmpi.b  #'0',d0
        bne.s   1f
        moveq   #' ',d0
1:      move.b  d0,(a0)+
        swap    d0
        add.b   #'0',d0
        move.b  d0,(a0)
        rts

| Variables (in the window: exchanged with the rest of our image).
        .equ    C_INST,     0
        .equ    C_LAYER,    2
        .equ    C_SRC,      4
        .equ    C_N,        6
        .equ    C_KEY,      8
        .equ    C_DONE,     10
        .balign 2
cv:     .space  12
saved:  .space  12
bounds: .space  4*33
ask:    .ascii  "CHOP INTO "
ask_n:  .asciz  "16 SLICES?"
press:  .asciz  "PRESS ENTER"
made_n: .ascii  "16"
made:   .asciz  " SLICES CREATED"
        .balign 2
chop_n: .byte   6                       | the count last used (16)
