| ----------------------------------------------------------------- crush
| CRUSH (Edit, 8 Wave, after CHOP: "CRUSH=PRESS ENTER"): makes a new
| wavesample from the edit wavesample the way an E-mu SP-1200 would play
| it, and puts it in its place on the keyboard (the original stays in
| memory). ENTER, then two prompts (▲/▼, ENTER; CANCEL stops):
| * "CRUSH PITCH=-5?": -12..+12 semitones, SP style: the sample is read at
|   a fixed rate with a step of 2^(p/12) samples and no smoothing between
|   samples (each output sample is the input sample the step lands in), so
|   down it's stepped (the SP's ringing), up it aliases. The new sample is
|   longer (down) or shorter (up) and plays at that pitch on the ROOT KEY.
| * "CRUSH BITS=12?": 12 (the SP-1200's, the MPC60's), 8 (dustier) or OFF
|   (the EPS's own 13).
| The rest of the wavesample is copied (envelopes, filter, ROOT KEY, keys,
| MODE; loop points moved with the pitch). The new one gets its own data
| (the OS's own "add a wavesample" routine, 0xFFA45E, as COPY WAVESAMPLE
| uses: MEMORY FULL if there's no room) and becomes the edit wavesample,
| ready for CHOP. docs/ANALYSIS.md -> CRUSH.
        .equ    ADD_WS,     0xA45E      | d7 = bytes, d0 = layer, a1 = data ->
                                        | carry, d0 = error / d0 = the new ws
        .equ    MEM_DONE,   0x8352      | the OS's tidy-up after adding one
        .equ    CRUSH_SLOT, wave_index+2*16-wmagic+REGION16
        .equ    W_HDR,      10          | the record's own header (links)
        .equ    CR_INST,    0
        .equ    CR_LAYER,   2
        .equ    CR_SRC,     4
        .equ    CR_NEW,     6
        .equ    CR_LEN,     8           | .l the source's length (samples)
        .equ    CR_OUT,     12          | .l the new length
        .equ    CR_LS,      16          | .l source loop start - start
        .equ    CR_LE,      20          | .l source loop end - start
        .equ    CR_NLS,     24          | .l the new loop start
        .equ    CR_NLE,     28          | .l the new loop end
        .equ    CR_STEP,    32          | .l the step, 16.16
        .equ    CR_FIELD,   36          | .b the prompt: 0 pitch, 1 bits
        .equ    CR_PITCH,   37          | .b 0..24 = -12..+12
        .equ    CR_BITS,    38          | .b 0 12, 1 8, 2 OFF
        .equ    CR_MASK,    40          | .w
        .equ    CR_SIZE,    42

crush:  movem.l d0-d7/a0-a6,-(sp)
        movea.w #MSG_STOPSEQ,a2
        tst.w   SEQ_RUN.w
        bne     cr_show
        jsr     CHECK_WS.w              | (a2 = the instrument's record)
        bcs     cr_show
        lea     cr(pc),a6
        move.w  EDIT_INST.w,CR_INST(a6)
        move.w  66(a2),CR_LAYER(a6)
        move.w  68(a2),CR_SRC(a6)
        clr.b   CR_FIELD(a6)
        bsr     cr_ask
        bcs     cr_abort
        lea     cr(pc),a6
        move.b  #1,CR_FIELD(a6)
        bsr     cr_ask
        bcs     cr_abort
        lea     cr_busy(pc),a2          | "CRUSHING"
        bsr     cr_msg
        lea     cr(pc),a6
        moveq   #0,d0
        move.b  CR_BITS(a6),d0
        add.w   d0,d0
        move.w  cr_masks(pc,d0.w),CR_MASK(a6)
        moveq   #0,d0
        move.b  CR_PITCH(a6),d0
        add.w   d0,d0
        add.w   d0,d0
        move.l  cr_steps(pc,d0.w),CR_STEP(a6)
        bra.s   1f
cr_masks:
        .word   0xFFF0, 0xFF00, 0xFFFF
| 2^(p/12) for p = -12..+12, 16.16
cr_steps:
        .long   0x8000, 0x879c, 0x8fad, 0x9838, 0xa145, 0xaadc, 0xb505, 0xbfc9
        .long   0xcb30, 0xd745, 0xe412, 0xf1a2, 0x10000, 0x10f39, 0x11f5a
        .long   0x13070, 0x1428a, 0x155b8, 0x16a0a, 0x17f91, 0x19660, 0x1ae8a
        .long   0x1c824, 0x1e343, 0x20000

| The source: its length and loop points (samples, from its start).
1:      bsr     cr_src                  | a3 = the source, a5 = its data
        movep.l W_START(a3),d4
        lsr.l   #8,d4
        lsr.l   #1,d4                   | s
        movep.l W_END(a3),d0
        lsr.l   #8,d0
        lsr.l   #1,d0
        sub.l   d4,d0
        addq.l  #1,d0
        move.l  d0,CR_LEN(a6)
        movep.l W_LSTART(a3),d0
        bsr     cr_rel
        move.l  d0,CR_LS(a6)
        movep.l W_LEND(a3),d0
        bsr     cr_rel
        move.l  d0,CR_LE(a6)
| Pass 1: how long the new one is, where its loop points land.
        clr.l   CR_NLS(a6)
        clr.l   CR_NLE(a6)
        moveq   #0,d4                   | input position, whole samples
        moveq   #0,d5                   | its fraction
        moveq   #0,d2                   | n, output samples
        moveq   #-1,d3                  | loop start not found yet
        move.l  CR_STEP(a6),d6
        move.l  d6,d7
        swap    d7                      | d7.w: the step's whole part
        andi.l  #0xFFFF,d7
2:      cmp.l   CR_LEN(a6),d4
        bcc.s   4f
        tst.l   d3
        bpl.s   3f
        cmp.l   CR_LS(a6),d4
        bcs.s   3f
        move.l  d2,d3                   | the first output at the loop start
        move.l  d2,CR_NLS(a6)
3:      cmp.l   CR_LE(a6),d4
        bhi.s   5f
        move.l  d2,CR_NLE(a6)           | the last at or before the loop end
5:      addq.l  #1,d2
        add.w   d6,d5
        bcc.s   6f
        addq.l  #1,d4
6:      add.l   d7,d4
        bra.s   2b
4:      move.l  d2,CR_OUT(a6)
| A new wavesample with room for it, in the source's layer.
        move.l  d2,d7
        add.l   d7,d7
        addi.l  #W_DATA,d7
        move.w  CR_INST(a6),d1
        jsr     INST_BASE.w
        move.w  CR_LAYER(a6),d0
        jsr     ADD_WS.w
        bcs     cr_err
        lea     cr(pc),a6
        move.w  d0,CR_NEW(a6)
| (Memory may have moved: everything from the instrument again.)
        bsr     cr_src                  | a3 = the source, a5 = its data
        movep.l W_START(a3),d4
        lsr.l   #8,d4
        lsr.l   #1,d4
        add.l   d4,d4
        adda.l  d4,a5                   | its first sample
        move.w  CR_NEW(a6),d0
        jsr     WS_OFF.w
        lea     0(a1,d1.l),a2           | the new one
        move.w  #W_HDR,d0               | its parameters: the source's
7:      move.w  0(a3,d0.w),0(a2,d0.w)
        addq.w  #2,d0
        cmpi.w  #W_DATA,d0
        bcs.s   7b
        clr.l   W_OWNER(a2)             | its own data
        moveq   #0,d0
        movep.l d0,W_START(a2)
        move.l  CR_OUT(a6),d0
        subq.l  #1,d0
        lsl.l   #8,d0
        add.l   d0,d0
        movep.l d0,W_END(a2)
        move.l  CR_NLS(a6),d0
        lsl.l   #8,d0
        add.l   d0,d0
        movep.l d0,W_LSTART(a2)
        move.l  CR_NLE(a6),d0
        lsl.l   #8,d0
        add.l   d0,d0
        movep.l d0,W_LEND(a2)
| Pass 2: the samples, SP style.
        lea     W_DATA(a2),a4
        move.w  CR_MASK(a6),d1
        move.l  CR_OUT(a6),d2
        moveq   #0,d4
        moveq   #0,d5
        move.l  CR_STEP(a6),d6
        move.l  d6,d7
        swap    d7
        andi.l  #0xFFFF,d7
        bra.s   9f
8:      move.l  d4,d0
        add.l   d0,d0
        move.w  0(a5,d0.l),d0
        and.w   d1,d0
        move.w  d0,(a4)+
        add.w   d6,d5
        bcc.s   10f
        addq.l  #1,d4
10:     add.l   d7,d4
9:      subq.l  #1,d2
        bpl.s   8b
        jsr     MEM_DONE.w
        lea     cr(pc),a6
        move.w  CR_INST(a6),d1          | the key map from the ranges (it
        jsr     INST_BASE.w             | takes the source's keys: later in
        move.w  CR_LAYER(a6),d0         | the layer)
        jsr     LAYER_OFF.w
        movea.l d1,a0
        jsr     KEYMAP.w
        move.w  CR_INST(a6),d1          | the edit wavesample: the new one
        jsr     INST_REC.w
        move.w  CR_NEW(a6),68(a1)
        lea     cr_done_n(pc),a0        | "CRUSHED: WS nnn"
        move.w  CR_NEW(a6),d0
        bsr     digits3
        lea     cr_done(pc),a2
        bra.s   cr_show2
cr_err: jsr     ERR_MSG.w               | (MEMORY FULL ...)
        bra.s   cr_show
cr_abort:
        movea.w #MSG_ABORTED,a2
cr_show:
        jsr     SHOW.w
        movem.l (sp)+,d0-d7/a0-a6
        rts
cr_show2:
        bsr.s   cr_msg
        movem.l (sp)+,d0-d7/a0-a6
        rts

| Show our text at a2.
cr_msg: move.l  a2,d0
        movea.w d0,a2
        jmp     SHOW.w

| d0 = a sample address (<< 9) -> samples from the source's start (d4),
| at least 0.
cr_rel: lsr.l   #8,d0
        lsr.l   #1,d0
        sub.l   d4,d0
        bcc.s   1f
        moveq   #0,d0
1:      rts

| a6 = cr; a3 = the source's record, a5 = its sample data (or the data it
| plays), a1 = the instrument's data.
cr_src: lea     cr(pc),a6
        move.w  CR_INST(a6),d1
        jsr     INST_BASE.w
        move.w  CR_SRC(a6),d0
        jsr     WS_OFF.w
        lea     0(a1,d1.l),a3
        lea     W_DATA(a3),a5
        moveq   #0,d0
        move.b  W_OWNER(a3),d0
        beq.s   1f
        jsr     WS_OFF.w
        lea     0(a1,d1.l),a5
        lea     W_DATA(a5),a5
1:      rts

| The prompt for CR_FIELD: ▲/▼ change it, ENTER: carry clear, CANCEL:
| carry set. (The OS's message loop changes a2-a6 and some data
| registers: everything from memory each time.)
cr_ask:
1:      lea     cr(pc),a6
        lea     cr_txt(pc),a0
        tst.b   CR_FIELD(a6)
        bne.s   2f
        lea     cr_pitch_t(pc),a1       | "CRUSH PITCH=-5?"
3:      move.b  (a1)+,(a0)+
        bne.s   3b
        subq.l  #1,a0
        moveq   #0,d0
        move.b  CR_PITCH(a6),d0
        subi.w  #12,d0
        moveq   #'+',d1
        tst.w   d0
        bpl.s   4f
        moveq   #'-',d1
        neg.w   d0
4:      move.b  d1,(a0)+
        cmpi.w  #10,d0
        bcs.s   5f
        move.b  #'1',(a0)+
        subi.w  #10,d0
5:      addi.b  #'0',d0
        move.b  d0,(a0)+
        bra.s   7f
2:      lea     cr_bits_t(pc),a1        | "CRUSH BITS=12?"
3:      move.b  (a1)+,(a0)+
        bne.s   3b
        subq.l  #1,a0
        moveq   #0,d0
        move.b  CR_BITS(a6),d0
        lsl.w   #2,d0
        lea     cr_bitsv(pc),a1
        adda.w  d0,a1
6:      move.b  (a1)+,(a0)+
        bne.s   6b
        subq.l  #1,a0
7:      move.b  #'?',(a0)+
        clr.b   (a0)
        lea     cr_txt(pc),a2
        bsr     cr_msg
        moveq   #-1,d0
        trap    #8
8:      moveq   #0,d0
        trap    #5
        andi.b  #0x80,d0
        beq     1b                      | timer: show it again
        jsr     GET_MSG.w
        bcs.s   8b
        cmpa.w  #BUTTON,a2
        bne.s   8b
        lea     cr(pc),a6
        lea     CR_PITCH(a6),a0
        moveq   #24,d1                  | the field's maximum
        tst.b   CR_FIELD(a6)
        beq.s   9f
        lea     CR_BITS(a6),a0
        moveq   #2,d1
9:      cmpi.b  #B_UP,d2
        bne.s   10f
        cmp.b   (a0),d1
        bls     1b
        addq.b  #1,(a0)
        bra     1b
10:     cmpi.b  #B_DOWN,d2
        bne.s   11f
        tst.b   (a0)
        beq     1b
        subq.b  #1,(a0)
        bra     1b
11:     cmpi.b  #B_ENTER,d2
        beq.s   12f
        cmpi.b  #B_CANCEL,d2
        bne.s   8b
        ori     #1,ccr
        rts
12:     andi    #0xFE,ccr
        rts
cr_bitsv:                               | 4 bytes each
        .byte   '1', '2', 0, 0
        .byte   '8', 0, 0, 0
        .byte   'O', 'F', 'F', 0

| d0.w (0-999) -> three characters at a0 (leading blanks).
digits3:
        ext.l   d0
        divu.w  #100,d0
        move.b  #' ',d1
        tst.w   d0
        beq.s   1f
        move.b  d0,d1
        addi.b  #'0',d1
1:      move.b  d1,(a0)+
        clr.w   d0
        swap    d0
        bsr     digits
        rts

        .balign 2
cr:     .space  CR_PITCH
        .byte   12, 0                   | PITCH 0, BITS 12 (the last used)
        .space  CR_SIZE-CR_PITCH-2
cr_txt: .space  24
cr_pitch_t:
        .asciz  "CRUSH PITCH="
cr_bits_t:
        .asciz  "CRUSH BITS="
cr_busy:
        .asciz  "CRUSHING"
cr_done:
        .ascii  "CRUSHED: WS"
cr_done_n:
        .asciz  "nnn"
        .balign 2
