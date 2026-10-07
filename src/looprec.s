| Loop recording: swing quantize at every loop wrap and at STOP, and undo
| (EPS OS 2.49)
|
| In LOOPED record mode the EPS keeps two take buffers in sequencer memory
| (offsets in 0xFF8114 / 0xFF8118 from the base in 0xFF8104, 28-byte
| headers, size 0xFF8128 each). During a pass it plays one and writes the
| other: the played take's events plus what you play now. At the loop wrap
| (0xFF6726) 0xFF6AD6 finishes the written take (gap to the loop end, END
| event), and 0xFF6B2E stores its length and swaps (0xFF811C = write
| pointer). At STOP, 0xFF6A0E assembles the final take in buffer A and the
| commit (0xFF6B78) merges it into the track. docs/ANALYSIS.md -> Sequencer.
|
| wrap_hook replaces "jsr 0x6B12; jsr 0x6AD6" at 0xFF6742 (LOOPED wraps
| only): after those, the finished take is quantized in place
| (src/swing.s) and 0xFF811C moved to its new end, so 0xFF6B2E stores the
| right length. Notes from earlier passes are on the grid already and stay;
| the new ones snap - the MPC's timing correct, heard on the next pass.
| Held keys: the OS keeps a pointer into the take for each held note's
| duration (0xFF8134); local moves keep those right (fix_open_notes in
| src/swing.s). A full scan can't, so it waits for a wrap with no key held.
|
| stop_hook replaces "jsr 0x74F2; tst.b 0x815E" at 0xFF6B7C, the start of
| the commit: after 0x74F2 closes held notes, a LOOPED take that is being
| kept (NEW) is quantized the same way (buffer A), then the test is redone
| for the caller's branch.
|
| append_hook replaces "lea 8(a4),a0; ori.w #0x8000,(a0)" at 0xFF6E56, the
| routine that appends a staged event to the take. A note just played (not
| one copied from the previous take: its staged first word still has bit 15
| clear) is logged with its offset and time (0xFF8038, the position in the
| loop). The wrap then moves only the logged notes (swing_logged) instead of
| scanning the take: the downbeat after the wrap isn't held up. If the log
| overflows, or a wrap is skipped (a held key), the next wrap scans the take
| (swing_take). STOP always scans: its rearrangement moves everything.
|
| swing_settings (8 x grid.w, offset.w per instrument) is filled in at build
| time (tools/mkcodearea.py --swing; all zero: no quantize).
|
| Undo (RECORD pressed while loop recording) takes out the most recent
| notes, a pass at a time: the notes played so far in this pass if there
| are any, else the last pass's. Each note played gets a tag, the pass's
| generation (1-15), in bits 3-0 of its last word, which playback ignores
| (0xFF6882 drops them; the OS writes 0 there). Copies keep only the last
| pass's tag. Undo adds the tag to the kill mask; from then on play_hook
| (the note handler, 0xFF638A) skips killed notes of the take being
| played: no voice and no copy into the next take, so they're gone after
| at most one more wrap, with the timing untouched (the OS only flushes
| ticks when it writes an event). Kill masks: this pass's and the last
| pass's (killed notes still in the take being played). At STOP the
| final take is re-encoded without killed notes (swing_kill) and the tags
| are cleared before the commit.

        .equ    SEQ_BASE,   0x8104      | abs.w: 0xFF8104 ...
        .equ    BUF_A,      0x8114
        .equ    BUF_B,      0x8118
        .equ    WRITE_PTR,  0x811C
        .equ    BUF_SIZE,   0x8128
        .equ    OPEN_NOTES, 0x8134
        .equ    KEEP_NEW,   0x815E
        .equ    REC_MODE,   0x815F
        .equ    LOOPED,     2
        .equ    TAKE_HDR,   28
        .equ    SEQ_STATE,  0x8028
        .equ    ST_RECORDING, 0x58D6    | recording over a track (playing: 0x58B2)
        .equ    SAVED_STATE, 0x802A
        .equ    POSITION,   0x8038      | ticks into the loop
        .equ    LOG_MAX,    64
        .equ    REC_FLAGS,  0x815A      | bit 1: recording a new sequence
        .equ    ST_WRAP,    0x5942      | loop wrap (and new sequences)
        .equ    NOTE_GAP,   0x637A      | the note handler's last steps
        .equ    RELEASE,    0xFF7B18    | transport button: release path
        .equ    MSG_DONE,   0xFF7B1E    | trap #4 (message done); rts
        .equ    U_CUR,      0           | undo_state.w: the tag for notes played now
        .equ    U_LAST,     2           | the last pass's tag (0: none)
        .equ    U_PREV,     4           | the pass before's (still in the played take)
        .equ    U_NEW,      6           | notes tagged U_CUR so far
        .equ    U_KILL,     8           | kill mask (bit n: tag n): this pass's undos
        .equ    U_KILLP,    10          | the last pass's

        .text
        .globl  wrap_hook, stop_hook, append_hook, play_hook, rec_hook
        .globl  swing_settings, note_log, undo_state
wrap_hook:
        jsr     0x6B12.w                | the displaced calls
        jsr     0x6AD6.w
        movem.l d0-d7/a0-a6,-(sp)
.if PAGES
        bsr     panel_swing
.endif
        lea     note_log(pc),a2
        move.l  WRITE_PTR.w,d1          | end of the finished take
        move.l  BUF_A.w,d2
        cmp.l   BUF_B.w,d1
        bcs.s   2f
        move.l  BUF_B.w,d2              | it's in buffer B
2:      tst.w   2(a2)
        bne.s   3f                      | log not usable: scan
        tst.w   (a2)
        beq.s   8f                      | nothing new this pass
        bsr     quantize_logged
        bra.s   8f
3:      tst.w   OPEN_NOTES.w            | a full scan moves every note: not
        bne.s   8f                      | while a key is held (try next wrap)
        moveq   #0,d4
        bsr     quantize_buffer
        lea     note_log(pc),a2
        clr.w   2(a2)                   | scanned: the log is usable again
8:      lea     note_log(pc),a2
        clr.w   (a2)                    | a new pass, an empty log
        lea     undo_state(pc),a1       | undo: this pass's kills apply to
        move.w  U_KILL(a1),U_KILLP(a1)  | the take now played
        clr.w   U_KILL(a1)
        tst.w   U_NEW(a1)
        beq.s   9f                      | nothing new: the last pass stays
        clr.w   U_NEW(a1)
        move.w  U_LAST(a1),U_PREV(a1)
        move.w  U_CUR(a1),U_LAST(a1)
        bsr     next_gen
9:      movem.l (sp)+,d0-d7/a0-a6
        rts

append_hook:
        lea     8(a4),a0                | the displaced lea
        cmpi.b  #LOOPED,REC_MODE.w
        bne     9f
        move.w  (a0),d0
        lsr.w   #4,d0
        andi.w  #0xFF,d0
        cmpi.w  #0xB0,d0
        bhs     9f                      | not a note
        movem.l d1-d2,-(sp)
        lea     undo_state(pc),a1
        tst.w   (a0)
        bpl.s   1f
        moveq   #15,d0                  | copied from the last take: it keeps
        and.w   4(a0),d0                | the last pass's tag only
        cmp.w   U_LAST(a1),d0
        beq.s   8f
        andi.w  #0xFFF0,4(a0)
        bra.s   8f
1:      andi.w  #0xFFF0,4(a0)           | played now: tag it
        move.w  U_CUR(a1),d0
        or.w    d0,4(a0)
        addq.w  #1,U_NEW(a1)
.if PAGES
        bsr     panel_swing
.endif
        cmpi.w  #ST_RECORDING,SEQ_STATE.w | log it for swing_logged?
        bne.s   8f
        moveq   #15,d0                  | its instrument swung at all?
        and.w   (a0),d0
        cmpi.w  #8,d0
        bcc.s   8f
        lsl.w   #2,d0
        lea     swing_settings(pc),a1
        tst.w   0(a1,d0.w)
        beq.s   8f
        move.w  2(a1,d0.w),d2           | offset
        move.w  0(a1,d0.w),d1           | grid
        lea     note_log(pc),a1
        move.w  (a1),d0
        cmpi.w  #LOG_MAX,d0
        bcs.s   2f
        move.w  #1,2(a1)                | full: next wrap scans
        bra.s   8f
2:      addq.w  #1,(a1)
        mulu.w  #12,d0
        lea     4(a1,d0.w),a1
        move.l  a6,(a1)+                | offset (fp: where it goes)
        move.l  POSITION.w,d0
        move.l  d0,(a1)+                | time
        bsr     quantize
        move.l  d0,(a1)                 | quantized time
8:      movem.l (sp)+,d1-d2
9:      ori.w   #0x8000,(a0)            | the displaced ori
        rts

| Replaces "moveq #0,d1; move.b 3(fp),d1; move.l d1,d0" at 0xFF638A, the
| start of the playback handler for notes (a4 = the event being played,
| its words from +8). While loop recording, a killed note (undo) is
| skipped: no voice, no copy into the take being written; only its gap
| counts (0xFF637A, whose rts goes back to the handler's caller).
play_hook:
        move.l  undo_kill(pc),d0        | this pass's kills.w, the last's.w
        beq.s   1f
        bsr.s   loop_rec
        bne.s   1f
        moveq   #15,d1
        and.w   12(a4),d1               | its tag
        beq.s   1f
        btst    d1,d0
        bne.s   2f
        addi.w  #16,d1
        btst    d1,d0
        beq.s   1f
2:      addq.l  #4,sp
        jmp     NOTE_GAP.w
1:      moveq   #0,d1                   | the displaced instructions
        move.b  3(a6),d1
        move.l  d1,d0
        rts

| Replaces "cmpi.b #1,6(a5); bne.s 0xFF7B18" at 0xFF7AD4: RECORD (transport
| button 0) pressed or released (a5 = the message). Pressed while loop
| recording over a track: undo, and the press is done with.
rec_hook:
        cmpi.b  #1,6(a5)                | the displaced test
        beq.s   1f
        move.l  #RELEASE,(sp)           | and branch
        rts
1:      bsr.s   loop_rec
        bne.s   9f
        movem.l d0-d2/a1,-(sp)
        lea     undo_state(pc),a1
        tst.w   U_NEW(a1)
        beq.s   3f
        move.w  U_CUR(a1),d0            | the notes played in this pass
        bsr.s   kill
        clr.w   U_NEW(a1)
        bsr.s   next_gen                | (the ones played next are kept)
        bra.s   4f
3:      move.w  U_LAST(a1),d0           | else the last pass's notes
        beq.s   4f
        bsr.s   kill
        clr.w   U_LAST(a1)
4:      movem.l (sp)+,d0-d2/a1
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

kill:   move.w  U_KILL(a1),d1           | a1 = undo_state, d0 = tag
        bset    d0,d1
        move.w  d1,U_KILL(a1)
        rts

| U_CUR = the next tag (1-15) that isn't the last two passes' or killed
| (those can still be in the takes). a1 = undo_state; uses d0-d2.
next_gen:
        move.w  U_CUR(a1),d0
        moveq   #14,d2
1:      addq.w  #1,d0
        andi.w  #15,d0
        beq.s   1b
        cmp.w   U_LAST(a1),d0
        beq.s   2f
        cmp.w   U_PREV(a1),d0
        beq.s   2f
        move.w  U_KILL(a1),d1
        or.w    U_KILLP(a1),d1
        btst    d0,d1
        bne.s   2f
        move.w  d0,U_CUR(a1)
        rts
2:      dbf     d2,1b
        rts                             | none free: keep the tag

stop_hook:
        jsr     0x74F2.w                | the displaced call
        tst.b   KEEP_NEW.w
        beq.s   9f
        cmpi.b  #LOOPED,REC_MODE.w
        bne.s   9f
        movem.l d0-d7/a0-a6,-(sp)
.if PAGES
        bsr     panel_swing
.endif
        lea     undo_state(pc),a2
        move.w  U_KILL(a2),d4           | killed notes still in the take
        or.w    U_KILLP(a2),d4
        swap    d4
        clr.w   d4
        move.l  WRITE_PTR.w,d1
        move.l  BUF_A.w,d2              | the final take is in buffer A
        bsr.s   quantize_buffer
        move.l  BUF_A.w,d2
        bsr     clear_tags
        movem.l (sp)+,d0-d7/a0-a6
9:      move.l  a0,-(sp)
        lea     note_log(pc),a0         | a new recording starts with an
        clr.l   (a0)                    | empty log
        lea     undo_state(pc),a0       | and no undo
        move.l  #0x00010000,(a0)+
        clr.l   (a0)+
        clr.l   (a0)
        movea.l (sp)+,a0
        tst.b   KEEP_NEW.w              | the displaced test (sets the flags)
        rts

| Quantize the take in the buffer at offset d2 (end offset d1) and move the
| write pointer to its new end. The rest of the buffer is the scratch.
| d4 high word: kill mask (undo; 0 = none).
quantize_buffer:
        movea.l SEQ_BASE.w,a5
        lea     TAKE_HDR(a5,d2.l),a0
        lea     0(a5,d1.l),a1
        movea.l a1,a2
        lea     0(a5,d2.l),a3
        adda.l  BUF_SIZE.w,a3
        lea     swing_settings(pc),a4
        move.l  a5,-(sp)
        tst.l   d4
        bne.s   1f
        bsr     swing_take
        bra.s   2f
1:      bsr     swing_kill
2:      move.l  (sp)+,d0
        suba.l  d0,a1
        move.l  a1,WRITE_PTR.w
        rts

| Clear the tags of the notes in the take at offset d2 (to the write
| pointer): the track gets the notes as the OS writes them.
clear_tags:
        movea.l SEQ_BASE.w,a5
        lea     TAKE_HDR(a5,d2.l),a0
        movea.l a5,a1
        adda.l  WRITE_PTR.w,a1
1:      cmpa.l  a1,a0
        bhs.s   9f
        move.w  (a0)+,d0
        bpl.s   1b                      | not an event's first word
        lsr.w   #4,d0
        andi.w  #0xFF,d0
        cmpi.w  #0xB0,d0
        bhs.s   1b
        andi.w  #0xFFF0,2(a0)           | a note: its last word
        addq.l  #4,a0
        bra.s   1b
9:      rts

| Quantize the logged notes of the take at offset d2 (end offset d1);
| a2 = note_log. If that has to stop, the whole take is scanned.
quantize_logged:
        movea.l SEQ_BASE.w,a5
        lea     TAKE_HDR(a5,d2.l),a0
        lea     0(a5,d1.l),a1
        lea     swing_settings(pc),a4
        move.w  (a2),d0
        addq.l  #4,a2
        movem.l d1-d2/a0-a1/a4-a5,-(sp)
        bsr     swing_logged
        movem.l (sp)+,d1-d2/a0-a1/a4-a5
        tst.w   d0
        beq.s   9f
        tst.w   OPEN_NOTES.w            | stopped: the full path (later if a
        bne.s   8f                      | key is held: mark the log unusable)
        movea.l a1,a2
        lea     0(a5,d2.l),a3
        adda.l  BUF_SIZE.w,a3
        move.l  a5,-(sp)
        bsr     swing_full
        move.l  (sp)+,d0
        suba.l  d0,a1
        move.l  a1,WRITE_PTR.w
9:      rts
8:      lea     note_log(pc),a2         | stopped with a key held: the next
        move.w  #1,2(a2)                | wrap scans the whole take
        rts

.if PAGES
| QUANTIZE and SWING% from the sequencer page (src/pages.s), the same for
| every instrument -> swing_settings. Swing (MPC: the second 8th or 16th
| of each pair at SWING% of the pair, tools/swing.py offset()) only on the
| 1/8 and 1/16 grids.
panel_swing:
        movem.l d0-d2/a0,-(sp)
        moveq   #0,d0
        move.b  QUANT_VAR.w,d0
        cmpi.w  #NQUANT,d0
        bcs.s   1f
        moveq   #0,d0
1:      add.w   d0,d0
        lea     quant_grids(pc),a0
        move.w  0(a0,d0.w),d1           | grid
        moveq   #0,d2                   | offset
        cmpi.w  #24,d1
        beq.s   2f
        cmpi.w  #12,d1
        bne.s   4f
2:      moveq   #0,d0
        move.b  SWING_VAR.w,d0
        cmpi.w  #50,d0
        bls.s   4f                      | straight
        cmpi.w  #75,d0
        bls.s   3f
        moveq   #75,d0
3:      mulu.w  d1,d0
        add.l   d0,d0                   | 2 * grid * pct
        addi.l  #50,d0
        divu.w  #100,d0                 | rounded
        sub.w   d1,d0
        move.w  d0,d2
4:      lea     swing_settings(pc),a0
        moveq   #7,d0
5:      move.w  d1,(a0)+
        move.w  d2,(a0)+
        dbf     d0,5b
        movem.l (sp)+,d0-d2/a0
        rts
.endif

        .balign 2
swing_settings:
        .space  32                      | set at build time (--swing)
note_log:
        .word   0                       | entries
        .word   0                       | 1: not usable (overflow, skipped wrap)
        .space  LOG_MAX*12              | offset.l, time.l, quantized time.l
undo_state:
        .word   1, 0, 0, 0              | U_CUR, U_LAST, U_PREV, U_NEW
undo_kill:
        .word   0, 0                    | U_KILL, U_KILLP

        .include "swing.s"
