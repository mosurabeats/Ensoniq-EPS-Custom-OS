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
        .equ    L_HIT,      0x2E        | layer record (src/swing/lvl.s)
        .equ    ROM_QLABELS, 0xC04778   | "1/4  ", "1/4T ", ... "1/32T", "OFF  " (ROM)

| Address words of our own tables: their low word (abs.w, sign-extended
| to 0xFFxxxx), as an offset in the image + REGION's low word.
| (Two bytes, not .word: gas turns a .word of a symbol difference that
| doesn't fit 15 bits into a "broken word" jump table.)
        .macro  aw sym
        .byte   (\sym-wmagic+REGION16)>>8, (\sym-wmagic+REGION16)&0xFF
        .endm

        .text
        .globl  wmagic, install, patch, unpatch, out, chunks
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
        add.w   6(a0),d0                | + our first
        move.w  d0,4(a1)
        move.w  6(a0),(a1)              | first
        move.w  8(a0),2(a1)             | last
        move.w  10(a0),8(a1)            | end of the search range
        lea     12(a0),a0
        dbra    d1,2b
        lea     words(pc),a0            | the OS's own page code: ours
        moveq   #NWORDS-1,d1
4:      movea.w (a0)+,a1
        move.w  2(a0),(a1)
        addq.l  #4,a0
        dbra    d1,4b
        lea     hooks(pc),a0            | the sequencer hooks: ours
        moveq   #NHOOKS-1,d1
5:      movea.w (a0)+,a1
        move.l  4(a0),(a1)              | (one move.l: never half a jsr)
        addq.l  #8,a0
        dbra    d1,5b
        rts

| Ours goes out of the window next (src/swing/ldr.s exchanges it).
unpatch:
        lea     pages(pc),a0
        moveq   #NPAGES-1,d1
2:      movea.w (a0)+,a1
        move.w  4(a1),d0
        sub.w   6(a0),d0                | - our first
        add.w   (a0),d0                 | + ROM first
        cmp.w   2(a0),d0
        bls.s   3f
        move.w  (a0),d0                 | was on one of ours: back to the first
3:      move.w  d0,4(a1)
        move.w  (a0),(a1)
        move.w  2(a0),2(a1)
        move.w  4(a0),8(a1)
        lea     12(a0),a0
        dbra    d1,2b
        lea     words(pc),a0            | the OS's own page code: the ROM's
        moveq   #NWORDS-1,d1
4:      movea.w (a0)+,a1
        move.w  (a0),(a1)
        addq.l  #4,a0
        dbra    d1,4b
        lea     hooks(pc),a0            | the sequencer hooks: stock
        moveq   #NHOOKS-1,d1
5:      movea.w (a0)+,a1
        move.l  (a0),(a1)
        addq.l  #8,a0
        dbra    d1,5b
        clr.b   FLAG.w
        move.b  DISP.w,OV_CUR.w
        rts

| Command mode (src/swing/ml.s): unpatch, then the exchange puts back what
| we displaced (a jump: it overwrites this code).
out:    bsr     unpatch
        jmp     SWAPX.w

| Page record; ROM first, last and search-range end; ours.
        .balign 2
pages:  .word   0xC110, 0x2562, 0x2570, 0x2570
        aw      amp_index
        aw      amp_index+2*8
        aw      amp_index+2*8
        .word   0xC0B6, 0x23DA, 0x23EE, 0x23EE
        aw      seq_index
        aw      seq_index+2*12
        aw      seq_index+2*12
        .word   0xC0E8, 0x224A, 0x2256, 0x2256
        aw      layer_index
        aw      layer_index+2*7
        aw      layer_index+2*7
        .word   0xC0F2, 0x24FA, 0x2518, 0x251E
        aw      wave_index
        aw      wave_index+2*16
        aw      wave_index+2*16
        .equ    NPAGES, 4

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
        .word   0xD064, 0x2110          | Edit mode's ENTER (src/swing/chop.s)
        aw      chop_enter
        .word   0xD066+2*CHOP_TYPE, 0x388A  | display of a parameter type no
        aw      chop_show               | page uses: the CHOP entry
        .word   0xD098+2*CHOP_TYPE, 0x3C10  | its edit (the arrows): nothing
        aw      chop_edit
        .equ    NWORDS, 8

| Sequencer hooks: address, stock bytes, ours (jsr abs.w).
hooks:  .word   0x6746                  | the loop wrap: jsr 0x6AD6.w
        .long   0x4EB86AD6
        .word   0x4EB8
        aw      wrap_hook
        .word   0x6B7C                  | the commit (after KEEP): jsr 0x74F2.w
        .long   0x4EB874F2
        .word   0x4EB8
        aw      stop_hook
        .word   0x6E56                  | append to the take: lea 8(a4),a0
        .long   0x41EC0008
        .word   0x4EB8
        aw      append_hook
        .word   0x638C                  | note playback: move.b 3(a6),d1
        .long   0x122E0003
        .word   0x4EB8
        aw      play_hook
        .word   0x7ADC                  | RECORD pressed: clr.b 0xC430.w
        .long   0x4238C430
        .word   0x4EB8
        aw      rec_hook
        .equ    NHOOKS, 5

| The Layer page (Edit, 9 Layer): its ROM entries, then HIT: NORMAL, FULL
| LEVEL (velocity 127), ONE-SHOT (no release at key-up for samples that
| don't loop), both. Layer record +0x2E (src/swing/lvl.s).
layer_index:
        .word   0x22C8, 0x22D0, 0x22D8, 0x22E0, 0x22E8, 0x22F0, 0x22F8
        aw      hit_desc
hit_desc:
        .byte   0x06, 0x0E              | parameter 6, a choice
        aw      hit_choices
        .word   L_HIT                   | where (layer record)
        aw      hit_label
hit_choices:
        .long   hit_labels
        .byte   10, 4                   | width, count
hit_labels:
        .asciz  "NORMAL    "
        .asciz  "FULL LEVEL"
        .asciz  "ONE-SHOT  "
        .asciz  "FULL+1SHOT"
        .balign 2

| The Wave page (Edit, 8 Wave): its ROM entries, then CHOP (src/swing/chop.s).
wave_index:
        .word   0x25A0, 0x25A8, 0x25B0, 0x25B8, 0x25C0, 0x25C8, 0x25D0, 0x25D8
        .word   0x25E0, 0x25E8, 0x25F0, 0x25F8, 0x2600, 0x2608, 0x2610, 0x2618
        aw      chop_desc
chop_desc:
        .byte   0x0A, CHOP_TYPE         | parameter 10, our type (no value)
        .word   0, 0                    | (w2, where: unused)
        aw      chop_label
chop_label:
        .asciz  "CHOP"
        .balign 2

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
hit_label:
        .asciz  "HIT"
quant_label:
        .asciz  "QUANTIZE"
swing_label:
        .asciz  "SWING%"
        .balign 2

| ---------------------------------------------------------------- swing
| QUANTIZE and SWING% (the Seq·Song page) apply when loop recording (RECORD
| MODE = LOOPED), like an MPC's timing correct: at each loop wrap the take
| just finished is quantized, so what you played lands on the swung grid
| from the next pass on; at the commit (after KEEP = NEW) the final take.
| docs/ANALYSIS.md -> Sequencer, src/looprec.s (the emulator build).
        .equ    SEQ_BASE,   0x8104
        .equ    BUF_A,      0x8114
        .equ    BUF_B,      0x8118
        .equ    WRITE_PTR,  0x811C
        .equ    BUF_SIZE,   0x8128
        .equ    OPEN_NOTES, 0x8134      | held notes being recorded
        .equ    KEEP_NEW,   0x815E
        .equ    REC_MODE,   0x815F
        .equ    LOOPED,     2
        .equ    TAKE_HDR,   28

| At a loop wrap (0xFF6746, LOOPED wraps only), after 0x6AD6 finished the
| take (gap to the loop end, END), before 0x6B2E stores its length. Not
| while a key is held: the OS keeps pointers into the take for held notes'
| durations (0xFF8134), which a re-encode would break; the next wrap gets
| those notes.
wrap_hook:
        jsr     0x6AD6.w                | the call we replaced
        movem.l d0-d7/a0-a6,-(sp)
        lea     undo(pc),a4
        bsr     settings
        bne.s   1f
        tst.b   U_KILL(a4)
        beq.s   8f                      | no quantize, nothing undone
1:      tst.w   OPEN_NOTES.w
        bne.s   7f
        move.l  WRITE_PTR.w,d3          | end of the finished take
        bsr     wbuf
        move.b  U_KILL(a4),d0
        bsr     qbuf
        clr.b   U_KILL(a4)              | the undone notes are gone
        bra.s   8f
7:      tst.b   U_KILL(a4)              | a key held: no re-encode; undone
        beq.s   8f                      | notes left in the take are skipped
        move.b  #2,U_KILL(a4)           | as it plays next time
8:      clr.b   U_NEW(a4)               | a new pass
9:      movem.l (sp)+,d0-d7/a0-a6
        rts

| d4 = offset of the buffer the take ending at offset d3 is in.
wbuf:   move.l  BUF_A.w,d4
        cmp.l   BUF_B.w,d3
        bcs.s   1f
        move.l  BUF_B.w,d4              | it's in buffer B
1:      rts

| At the commit (0xFF6B7C), after 0x74F2 closed held notes: a LOOPED take
| kept with NEW (it's in buffer A). The OS's "tst.b 0x815E" follows.
stop_hook:
        jsr     0x74F2.w                | the call we replaced
        movem.l d0-d7/a0-a6,-(sp)
        lea     undo(pc),a4
        tst.b   KEEP_NEW.w
        beq.s   8f
        cmpi.b  #LOOPED,REC_MODE.w
        bne.s   8f
        bsr     settings                | quantize, and leave out what was
        move.l  WRITE_PTR.w,d3          | undone
        move.l  BUF_A.w,d4
        move.b  U_KILL(a4),d0
        bsr     qbuf
        movea.l SEQ_BASE.w,a0           | the track gets the notes untagged
        movea.l a0,a1
        adda.l  BUF_A.w,a0
        lea     TAKE_HDR(a0),a0
        adda.l  WRITE_PTR.w,a1
        bsr     untag
8:      clr.w   U_NEW(a4)               | (U_NEW, U_KILL) a new recording
9:      movem.l (sp)+,d0-d7/a0-a6
        rts

| ------------------------------------------------------------------ undo
| RECORD pressed while loop recording takes out the newest notes: the ones
| played so far in this pass, or if there are none, the last pass's. One
| level, like the MPC60. Bit 3 of a note's last word marks the newest pass
| with notes (playback ignores bits 3-0: 0xFF6882; bits 2-0 don't exist in
| 13-bit sample RAM, bit 3 does). Notes played after an undo aren't marked.
| Undone notes: the ones in the take being written go at the next wrap
| (sq drops them); the last pass's still in the take being played are
| skipped as it plays (no voice, no copy). U_KILL: 1 = this pass's, 2 = the
| last pass's. docs/ANALYSIS.md -> Swing build.
        .equ    U_NEW,      0           | this pass has notes played
        .equ    U_KILL,     1
        .equ    REC_FLAGS,  0x815A      | bit 1: recording a new sequence
        .equ    SEQ_STATE,  0x8028
        .equ    ST_RECORDING, 0x58D6
        .equ    ST_WRAP,    0x5942
        .equ    SAVED_STATE, 0x802A
        .equ    NOTE_GAP,   0x637A      | the note handler's last steps
        .equ    MSG_DONE,   0x7B1E      | trap #4 (message done); rts

| 0xFF6E56, the routine that appends a staged event (a4 + 8) to the take
| being written; the OS's "ori.w #0x8000,(a0)" follows (bit 15 of the
| first word is still clear for a note played now, set for one copied
| from the take being played).
append_hook:
        lea     8(a4),a0                | the displaced lea
        cmpi.b  #LOOPED,REC_MODE.w
        bne.s   9f
        move.w  (a0),d0
        lsr.w   #4,d0
        andi.w  #0xFF,d0
        cmpi.w  #0xB0,d0
        bhs.s   9f                      | not a note
        movem.l d0-d7/a1-a6,-(sp)
        lea     undo(pc),a4
        tst.w   (a0)
        bpl.s   1f
        tst.w   (a4)                    | copied: newer notes this pass, or
        beq.s   8f                      | an undo: no longer the newest
        andi.w  #0xFFF7,4(a0)
        bra.s   8f
1:      andi.w  #0xFFF7,4(a0)           | played now
        tst.b   U_KILL(a4)
        bne.s   8f                      | after an undo: kept, unmarked
        ori.w   #8,4(a0)
        tst.b   U_NEW(a4)
        bne.s   8f
        st      U_NEW(a4)               | the first of this pass: what's
        move.l  a0,-(sp)                | written so far is no longer the
        move.l  WRITE_PTR.w,d3          | newest
        bsr     wbuf
        movea.l SEQ_BASE.w,a0
        movea.l a0,a1
        adda.l  d4,a0
        lea     TAKE_HDR(a0),a0
        adda.l  d3,a1
        bsr.s   untag
        movea.l (sp)+,a0
8:      movem.l (sp)+,d0-d7/a1-a6
9:      rts

| Clear bit 3 of the notes from a0 to a1. Uses d0, a0.
untag:  cmpa.l  a1,a0
        bhs.s   9f
        move.w  (a0)+,d0
        bpl.s   untag                   | not an event's first word
        lsr.w   #4,d0
        andi.w  #0xFF,d0
        cmpi.w  #0xB0,d0
        bhs.s   untag
        andi.w  #0xFFF7,2(a0)           | a note: its last word
        addq.l  #4,a0
        bra.s   untag
9:      rts

| 0xFF638C in the note playback handler (a4 = the event, its words from
| +8; the OS did "moveq #0,d1"): the last pass's undone notes are skipped:
| no voice, no copy into the take being written; only their gap counts
| (0xFF637A, whose rts goes back to the handler's caller).
play_hook:
        move.b  3(a6),d1                | the displaced instruction
        cmpi.b  #2,undo+U_KILL
        bne.s   9f
        btst    #3,13(a4)
        beq.s   9f
        bsr.s   loop_rec
        bne.s   9f
        addq.l  #4,sp
        jmp     NOTE_GAP.w
9:      rts

| 0xFF7ADC: RECORD (transport button 0) pressed (a5 = the message). While
| loop recording over a track: undo, and the press is done with.
rec_hook:
        clr.b   0xC430.w                | the displaced instruction
        bsr.s   loop_rec
        bne.s   9f
        move.l  a4,-(sp)
        lea     undo(pc),a4
        tst.b   U_KILL(a4)
        bne.s   8f                      | one level
        move.b  #2,U_KILL(a4)
        tst.b   U_NEW(a4)
        beq.s   8f                      | nothing played yet: the last pass
        move.b  #1,U_KILL(a4)           | this pass's
        sf      U_NEW(a4)
8:      movea.l (sp)+,a4
        move.l  #MSG_DONE,(sp)
9:      rts

| Z set if loop recording over a track: LOOPED, recording (0x58D6) or at
| a wrap (0x5942, going back to 0x58D6), not a new sequence.
loop_rec:
        cmpi.b  #LOOPED,REC_MODE.w
        bne.s   9f
        btst    #1,REC_FLAGS.w
        bne.s   9f
        cmpi.w  #ST_RECORDING,SEQ_STATE.w
        beq.s   9f
        cmpi.w  #ST_WRAP,SEQ_STATE.w
        bne.s   9f
        cmpi.w  #ST_RECORDING,SAVED_STATE.w
9:      rts

        .balign 2
undo:   .byte   0, 0                    | U_NEW, U_KILL

| Quantize the take in the buffer at offset d4 (end offset d3), then move
| the write pointer to its new end. d1/d2: grid, offset.
qbuf:   movea.l SEQ_BASE.w,a2
        lea     TAKE_HDR(a2,d4.l),a0
        lea     0(a2,d3.l),a1
        lea     0(a2,d4.l),a3
        adda.l  BUF_SIZE.w,a3
        movem.l a2/a4,-(sp)             | sq uses a4 (the callers' undo)
        bsr     sq
        movem.l (sp)+,d0/a4
        suba.l  d0,a1
        move.l  a1,WRITE_PTR.w
        rts

| QUANTIZE (0-7: 1/4 .. 1/32T at 48 ticks per quarter, 8: OFF) and SWING%
| -> d1 = grid, d2 = swing offset; Z when off. Swing (MPC: the second 8th
| or 16th of each pair at SWING% of the pair, tools/swing.py offset()) on
| the 1/8 and 1/16 grids, from 51%.
settings:
        moveq   #0,d1
        moveq   #0,d2
        moveq   #0,d0
        move.b  QUANT.w,d0
        cmpi.w  #8,d0
        bcc.s   9f
        add.w   d0,d0
        move.w  grids(pc,d0.w),d1
        cmpi.w  #24,d1
        beq.s   1f
        cmpi.w  #12,d1
        bne.s   9f
1:      move.b  SWING.w,d0
        cmpi.w  #50,d0
        bls.s   9f                      | straight
        cmpi.w  #75,d0
        bls.s   2f
        moveq   #75,d0
2:      mulu.w  d1,d0
        add.l   d0,d0                   | 2 * grid * pct
        addi.l  #50,d0
        divu.w  #100,d0                 | rounded
        sub.w   d1,d0
        move.w  d0,d2
9:      tst.w   d1
        rts
grids:  .word   48, 32, 24, 16, 12, 8, 6, 4

        .include "sq.s"
        .include "chop.s"

        .balign 2
chunks:                                 | (tools/mkswing.py appends them)
