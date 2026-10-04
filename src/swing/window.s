| Our part of the overlay window (EPS OS 2.49, hardware build)
|
| OS RAM is full and sample RAM can't run code, so our bigger code borrows
| a region of the overlay window: REGION..REGION+LEN, inside overlay 0's
| sequence/track commands, which only run from Command mode and are always
| reached through the command dispatcher, which loads overlay 0 first when
| the OS's current overlay (0xFFC8D0) says something else is there
| (docs/ANALYSIS.md -> The overlay window during play and recording).
|
| The OS file's overlay-3 slot holds overlay 0 with this image in the
| region. At boot (src/swing/late.s) overlay 0's region bytes go to our
| store in sample RAM, overlay 3 is loaded, and install runs: the window
| then holds overlay 0 with our code, OV_CUR says 3.
|
| Out and back in (resident src/swing/ldr.s, ml.s, swapx.s):
| * when the OS asks for an overlay, unpatch, then exchange the region with
|   the store: the overlay we displaced is back, and if that's the one
|   asked for no disk read is needed;
| * at the top of the UI loop, outside Command mode, exchange again and
|   patch.
| patch/unpatch switch our page entries (MUTE GROUP on the 6 Amp page,
| QUANTIZE and SWING% on the Seq·Song page) and, later, the sequencer
| hooks. Each hook word is written with one move.l: an interrupt can't
| split an instruction, so no task ever sees half a patch.

        .include "common.inc"
        .equ    WS_GROUP,   0x11E
        .equ    ROM_QLABELS, 0xC04778   | "1/4  ", "1/4T ", ... "1/32T", "OFF  " (ROM)

| Address words of our own tables: their low word (abs.w, sign-extended
| to 0xFFxxxx), as an offset in the image + REGION's low word.
| (Two bytes, not .word: gas turns a .word of a symbol difference that
| doesn't fit 15 bits into a "broken word" jump table.)
        .macro  aw sym
        .byte   (\sym-wmagic+REGION16)>>8, (\sym-wmagic+REGION16)&0xFF
        .endm

        .text
        .globl  wmagic, install, patch, unpatch, chunks
wmagic: .ascii  "SWG1"
install:
        lea     chunks(pc),a0           | resident code and fixed hooks
1:      move.w  (a0)+,d0                | (dest.w, length-1.w, bytes, even)
        beq.s   2f
        movea.w d0,a1
        move.w  (a0)+,d0
3:      move.b  (a0)+,(a1)+
        dbra    d0,3b
        bra.s   1b
2:      clr.b   DISP.w                  | the store holds overlay 0's bytes
        move.b  #QUANT_DEFAULT,QUANT.w
        move.b  #SWING_DEFAULT,SWING.w
                                        | (on into patch)

| Ours is in the window now (just exchanged in, or loaded at boot).
patch:  move.b  OV_CUR.w,d0
        cmpi.b  #OV_OURS,d0
        beq.s   1f                      | (boot: overlay 3 was loaded)
        move.b  d0,DISP.w
1:      move.b  #OV_OURS,OV_CUR.w
        st      FLAG.w
        lea     pages(pc),a0
        moveq   #NPAGES-1,d1
2:      movea.w (a0)+,a1                | page record
        move.w  4(a1),d0                | current entry
        sub.w   (a0),d0                 | - ROM first
        add.w   4(a0),d0                | + our first
        move.w  d0,4(a1)
        move.w  4(a0),(a1)              | first
        move.w  6(a0),2(a1)             | last
        move.w  6(a0),8(a1)             | end of the search range
        addq.l  #8,a0
        dbra    d1,2b
        lea     words(pc),a0            | the OS's own page code: ours
        moveq   #NWORDS-1,d1
4:      movea.w (a0)+,a1
        move.w  2(a0),(a1)
        addq.l  #4,a0
        dbra    d1,4b
        rts

| Ours goes out of the window next (src/swing/ldr.s exchanges it).
unpatch:
        lea     pages(pc),a0
        moveq   #NPAGES-1,d1
2:      movea.w (a0)+,a1
        move.w  4(a1),d0
        sub.w   4(a0),d0                | - our first
        add.w   (a0),d0                 | + ROM first
        cmp.w   2(a0),d0
        bls.s   3f
        move.w  (a0),d0                 | was on one of ours: back to the first
3:      move.w  d0,4(a1)
        move.w  (a0),(a1)
        move.w  2(a0),2(a1)
        move.w  2(a0),8(a1)
        addq.l  #8,a0
        dbra    d1,2b
        lea     words(pc),a0            | the OS's own page code: the ROM's
        moveq   #NWORDS-1,d1
4:      movea.w (a0)+,a1
        move.w  (a0),(a1)
        addq.l  #4,a0
        dbra    d1,4b
        clr.b   FLAG.w
        move.b  DISP.w,OV_CUR.w
        rts

| Page record, ROM first and last entry, our first and last entry.
        .balign 2
pages:  .word   0xC110, 0x2562, 0x2570
        aw      amp_index
        aw      amp_index+2*8
        .word   0xC0B6, 0x23DA, 0x23EE
        aw      seq_index
        aw      seq_index+2*12
        .equ    NPAGES, 2

| Words in OS code that name the Seq·Song page's entries: when the Edit
| pages switch between the sequence and song tables (0xFF3456), the OS
| rewrites the record unless "first" is 0x23DA, and resets "current"
| (0xFF269E). Address, the ROM's value, ours.
words:  .word   0x3468, 0x23DA
        aw      seq_index
        .word   0x346E, 0x23DA
        aw      seq_index
        .word   0x3472, 0x23EE
        aw      seq_index+2*12
        .word   0x3476, 0x23DA
        aw      seq_index
        .word   0x26A0, 0x23DA
        aw      seq_index
        .equ    NWORDS, 5

| The 6 Amp page: its ROM entries, then MUTE GROUP.
amp_index:
        .word   0x2748, 0x2750, 0x2758, 0x2760, 0x2768, 0x2770, 0x2778, 0x2780
        aw      mute_desc
mute_desc:
        .byte   0x08, 0x00              | parameter 8, a number 0-max
        .word   15, WS_GROUP            | max, where (wavesample record)
        aw      mute_label
| The Seq·Song page: its ROM entries, then QUANTIZE and SWING%.
seq_index:
        .word   0x2426, 0x242E, 0x2436, 0x243E, 0x2446, 0x244E, 0x2456, 0x245E
        .word   0x2466, 0x246E, 0x2476
        aw      quant_desc
        aw      swing_desc
quant_desc:
        .byte   0x0A, 0x0E              | parameter 10, a choice
        aw      quant_choices
        .word   QUANT
        aw      quant_label
swing_desc:
        .byte   0x0B, 0x00              | parameter 11, a number 0-max
        .word   75, SWING
        aw      swing_label
quant_choices:
        .long   ROM_QLABELS             | the ROM's own labels, 6 bytes apart
        .byte   5, 9                    | width, count
mute_label:
        .asciz  "MUTE GROUP"
quant_label:
        .asciz  "QUANTIZE"
swing_label:
        .asciz  "SWING%"
        .balign 2
chunks:                                 | (tools/mkswing.py appends them)
