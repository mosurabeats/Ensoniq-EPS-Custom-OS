| Loop recording: swing quantize at every loop wrap and at STOP (EPS OS 2.49)
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
| time (tools/mkcodearea.py --swing).

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
        .equ    ST_PLAYING, 0x58D6      | (recording or playing)
        .equ    POSITION,   0x8038      | ticks into the loop
        .equ    LOG_MAX,    64

        .text
        .globl  wrap_hook, stop_hook, append_hook, swing_settings, note_log
wrap_hook:
        jsr     0x6B12.w                | the displaced calls
        jsr     0x6AD6.w
        movem.l d0-d7/a0-a6,-(sp)
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
        bsr     quantize_buffer
        lea     note_log(pc),a2
        clr.w   2(a2)                   | scanned: the log is usable again
8:      lea     note_log(pc),a2
        clr.w   (a2)                    | a new pass, an empty log
        movem.l (sp)+,d0-d7/a0-a6
        rts

append_hook:
        lea     8(a4),a0                | the displaced lea
        tst.w   (a0)
        bmi.s   9f                      | copied from the last take
        cmpi.b  #LOOPED,REC_MODE.w
        bne.s   9f
        cmpi.w  #ST_PLAYING,SEQ_STATE.w
        bne.s   9f
        move.w  (a0),d0
        lsr.w   #4,d0
        andi.w  #0xFF,d0
        cmpi.w  #0xB0,d0
        bhs.s   9f                      | not a note
        moveq   #15,d0                  | its instrument swung at all?
        and.w   (a0),d0
        cmpi.w  #8,d0
        bcc.s   9f
        lsl.w   #2,d0
        lea     swing_settings(pc),a1
        tst.w   0(a1,d0.w)
        beq.s   9f
        movem.l d1-d2,-(sp)
        move.w  2(a1,d0.w),d2           | offset
        move.w  0(a1,d0.w),d1           | grid
        lea     note_log(pc),a1
        move.w  (a1),d0
        cmpi.w  #LOG_MAX,d0
        bcs.s   1f
        move.w  #1,2(a1)                | full: next wrap scans
        bra.s   8f
1:      addq.w  #1,(a1)
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

stop_hook:
        jsr     0x74F2.w                | the displaced call
        tst.b   KEEP_NEW.w
        beq.s   9f
        cmpi.b  #LOOPED,REC_MODE.w
        bne.s   9f
        movem.l d0-d7/a0-a6,-(sp)
        move.l  WRITE_PTR.w,d1
        move.l  BUF_A.w,d2              | the final take is in buffer A
        bsr.s   quantize_buffer
        movem.l (sp)+,d0-d7/a0-a6
9:      move.l  a0,-(sp)
        lea     note_log(pc),a0         | a new recording starts with an
        clr.l   (a0)                    | empty log
        movea.l (sp)+,a0
        tst.b   KEEP_NEW.w              | the displaced test (sets the flags)
        rts

| Quantize the take in the buffer at offset d2 (end offset d1) and move the
| write pointer to its new end. The rest of the buffer is the scratch.
quantize_buffer:
        movea.l SEQ_BASE.w,a5
        lea     TAKE_HDR(a5,d2.l),a0
        lea     0(a5,d1.l),a1
        movea.l a1,a2
        lea     0(a5,d2.l),a3
        adda.l  BUF_SIZE.w,a3
        lea     swing_settings(pc),a4
        move.l  a5,-(sp)
        bsr     swing_take
        move.l  (sp)+,d0
        suba.l  d0,a1
        move.l  a1,WRITE_PTR.w
        rts

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

        .balign 2
swing_settings:
        .space  32                      | set at build time (--swing)
note_log:
        .word   0                       | entries
        .word   0                       | 1: not usable (overflow, skipped wrap)
        .space  LOG_MAX*12              | offset.l, time.l, quantized time.l

        .include "swing.s"
