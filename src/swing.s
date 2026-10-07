| Swing quantize of a recorded take (EPS OS 2.49), MPC style
|
| swing_take moves the notes of one take (an event stream, format in
| tools/seqstream.py and docs/ANALYSIS.md -> Sequencer) onto a swung grid,
| per instrument, and re-encodes the stream. tools/seqstream.py
| quantize_take is the reference; tests/test_swing_asm.py runs both on the
| same streams.
|
| In:  a0 = first word of the take, a1 = end (exclusive),
|      a2 = scratch (even, at or after a1), a3 = end of the scratch,
|      a4 = settings: 8 x (grid.w, offset.w), instrument 0-7 (grid 0 = leave
|           that instrument's notes as played; offset = swing ticks added to
|           every second grid line, tools/swing.py offset()).
| Out: a1 = new end (unchanged if the scratch was too small).
| Uses all registers except a7.
|
| (1) Walk the take. Each event except time events gets a record
|     (time.l, offset.w, length.w) in the scratch; notes get their
|     quantized time. (2) Notes stay at or after the take's opening events
|     and wrap to there if they land on the end. (3) Stable insertion sort
|     by time (the records are almost sorted already). (4) Re-encode after
|     the records: 7-bit gaps inside the events, time events (code 0xB9)
|     for longer gaps or after 1-word events. (5) Copy back over the take.
|
| Registers in (1)-(2): a0 take, a1 take end, a2 records, a3 scratch end,
| a4 settings, a5 record write pointer, a6 scan; d7 time, d6 floor (time
| of the last opening event), d5 time of the END event, d4 bit 0 = a note
| has been seen, bit 1 = a note moved (if none did, (3)-(5) are skipped:
| the take is already on the grid, the usual case at most wraps).

        .equ    TIME_CODE,  0xB9
        .equ    END_CODE,   0xBC
.ifndef SEQ_BASE                        | (src/looprec.s defines them too)
        .equ    SEQ_BASE,   0x8104      | sequencer memory base (abs.w)
        .equ    BUF_A,      0x8114      | take buffer offsets
        .equ    BUF_B,      0x8118
        .equ    OPEN_NOTES, 0x8134      | held notes being recorded
.endif

        .text
        .globl  swing_take, swing_full, swing_kill, quantize

| swing_take: the fast path (below), and swing_full on what it leaves if it
| has to stop. Same interface as swing_full.
swing_take:
        movem.l a0-a4,-(sp)
        bsr     swing_fast
        movem.l (sp)+,a0-a4
        tst.w   d0
        bne     swing_full              | stopped: re-encode the whole take
        rts                             | (a1: same size, unchanged)

swing_full:
        moveq   #0,d4
| swing_kill: swing_full that also leaves out the notes whose tag n (bits
| 3-0 of the last word, written by src/looprec.s for undo) has bit 16+n of
| d4 set.
swing_kill:
        move.l  a1,-(sp)                | the original end, for giving up
        movea.l a2,a5
        moveq   #0,d7
        moveq   #0,d6
        move.l  #0x7FFFFFFF,d5
        clr.w   d4
        movea.l a0,a6

| (1) records
10:     cmpa.l  a1,a6
        bhs     20f
        move.l  a6,d2                   | d2 = event start
        move.w  (a6)+,d0                | d0 = w0
11:     cmpa.l  a1,a6                   | find the next event start
        bhs.s   12f
        tst.w   (a6)
        bmi.s   12f
        addq.l  #2,a6
        bra.s   11b
12:     move.w  d0,d1
        lsr.w   #4,d1
        andi.w  #0xFF,d1                | d1 = code
        cmpi.w  #TIME_CODE,d1
        bne.s   13f
        move.w  d0,d3                   | time event: no record, add its gap
        andi.w  #0x7000,d3
        lsr.w   #1,d3                   | gap bits 13-11
        move.w  -2(a6),d1
        lsr.w   #4,d1
        andi.w  #0x7FF,d1
        or.w    d1,d3
        add.l   d3,d7
        bra.s   10b
13:     lea     8(a5),a5                | room for the record?
        cmpa.l  a3,a5
        bhi     90f
        subq.l  #8,a5
        move.l  d7,(a5)                 | time (notes: replaced below)
        move.l  d2,d3
        sub.l   a0,d3
        move.w  d3,4(a5)                | offset of the event in the take
        move.l  a6,d3
        sub.l   d2,d3
        move.w  d3,6(a5)                | length in bytes
        cmpi.w  #0xB0,d1
        bhs.s   15f
        moveq   #15,d1                  | a note. Killed (undo)?
        and.w   -2(a6),d1
        beq.s   25f
        addi.w  #16,d1
        btst    d1,d4
        beq.s   25f
        bset    #1,d4                   | yes: no record, re-encode
        bra.s   26f
25:     bset    #0,d4                   | quantize?
        cmp.l   d6,d7
        beq.s   16f                     | at the floor: stays (a downbeat)
        moveq   #15,d1
        and.w   d0,d1
        cmpi.w  #8,d1
        bhs.s   16f
        lsl.w   #2,d1
        move.w  2(a4,d1.w),d2           | swing offset
        move.w  0(a4,d1.w),d1           | grid
        beq.s   16f
        move.l  d0,-(sp)
        move.l  d7,d0
        bsr     quantize
        cmp.l   d6,d0                   | not before the opening events (the
        bge.s   18f                     | floor is final once a note is seen)
        move.l  d6,d0
18:     move.l  d0,(a5)
        cmp.l   d7,d0
        beq.s   17f
        bset    #1,d4                   | moved
17:     move.l  (sp)+,d0
        bra.s   16f
15:     btst    #0,d4                   | not a note
        bne.s   14f
        move.l  d7,d6                   | still opening: the floor moves up
14:     cmpi.w  #END_CODE,d1
        bne.s   16f
        move.l  d7,d5
16:     addq.l  #8,a5
26:     cmpi.w  #2,d3                   | 1-word events carry no gap
        bls     10b
        andi.w  #0x7000,d0              | gap: w0 bits 14-12, last word 14-11
        lsr.w   #8,d0
        move.w  -2(a6),d1
        andi.w  #0x7800,d1
        moveq   #11,d2
        lsr.w   d2,d1
        or.w    d1,d0
        andi.l  #0x7F,d0
        add.l   d0,d7
        bra     10b

| (2) notes: not before the floor, wrapped to it at or after the end
20:     movea.l a2,a6
21:     cmpa.l  a5,a6
        bhs.s   30f
        moveq   #0,d0
        move.w  4(a6),d0
        move.w  (a0,d0.l),d0
        lsr.w   #4,d0
        andi.w  #0xFF,d0
        cmpi.w  #0xB0,d0
        bhs.s   23f
        move.l  (a6),d0
        cmp.l   d5,d0
        blt.s   22f
        move.l  d6,d0                   | at or after the end: wrap
22:     cmp.l   d6,d0
        bge.s   24f
        move.l  d6,d0                   | before the opening events
24:     cmp.l   (a6),d0
        beq.s   23f
        move.l  d0,(a6)
        bset    #1,d4
23:     addq.l  #8,a6
        bra.s   21b

| (3) stable insertion sort of the 8-byte records by time
30:     btst    #1,d4
        beq     90f                     | nothing moved: take unchanged
        move.l  a3,d4                   | d4 = scratch end (a3 is j below)
        lea     8(a2),a6                | a6 = i
31:     cmpa.l  a5,a6
        bhs.s   40f
        movem.l (a6),d0-d1              | the key record
        movea.l a6,a3
32:     cmpa.l  a2,a3                   | while j > start and R[j-1] > key
        bls.s   33f
        cmp.l   -8(a3),d0
        bge.s   33f
        move.l  -4(a3),4(a3)
        move.l  -8(a3),(a3)
        subq.l  #8,a3
        bra.s   32b
33:     movem.l d0-d1,(a3)
        addq.l  #8,a6
        bra.s   31b

| (4) encode after the records: a3 = output start, a4 = output pointer
40:     movea.l a5,a3
        movea.l a5,a4
        movea.l a2,a6
41:     cmpa.l  a5,a6
        bhs     60f
        moveq   #0,d6                   | d6 = gap to the next record
        lea     8(a6),a1
        cmpa.l  a5,a1
        bhs.s   42f
        move.l  (a1),d6
        sub.l   (a6),d6
42:     moveq   #0,d0
        move.w  4(a6),d0
        lea     (a0,d0.l),a1            | a1 = the event
        moveq   #0,d5
        move.w  6(a6),d5                | d5 = its length in bytes
        move.l  a4,d0
        add.l   d5,d0
        cmp.l   d4,d0
        bhi     90f
        movea.l a4,a2                   | a2 = its first output word
        move.w  d5,d1
        lsr.w   #1,d1
        subq.w  #1,d1
43:     move.w  (a1)+,(a4)+
        dbf     d1,43b
        andi.w  #0x8FFF,(a2)            | clear the old gap
        cmpi.w  #2,d5
        bls.s   45f                     | 1-word event: gap needs time events
        andi.w  #0x87FF,-2(a4)
        cmpi.l  #127,d6
        bhi.s   45f
        move.w  d6,d0                   | gap fits: high 3 bits in w0 14-12,
        lsl.w   #8,d0                   | low 4 bits in the last word 14-11
        andi.w  #0x7000,d0
        or.w    d0,(a2)
        move.w  d6,d0
        moveq   #11,d1
        lsl.w   d1,d0
        andi.w  #0x7800,d0
        or.w    d0,-2(a4)
        bra.s   49f
45:     tst.l   d6                      | time events carry the gap
        beq.s   49f
        move.l  d6,d0
        cmpi.l  #0x3FFF,d0
        bls.s   46f
        move.l  #0x3FFF,d0
46:     sub.l   d0,d6
        move.l  a4,d1
        addq.l  #4,d1
        cmp.l   d4,d1
        bhi.s   90f
        move.w  d0,d1                   | w0 = 0x8B90 | gap bits 13-11 << 12
        lsl.w   #1,d1
        andi.w  #0x7000,d1
        ori.w   #0x8B90,d1
        move.w  d1,(a4)+
        lsl.w   #4,d0                   | w1 = gap bits 10-0 << 4
        andi.w  #0x7FF0,d0
        move.w  d0,(a4)+
        bra.s   45b
49:     addq.l  #8,a6
        bra     41b

| (5) copy back over the take (the output is after it, so forwards is safe)
60:     movea.l a0,a1
61:     cmpa.l  a4,a3
        bhs.s   62f
        move.w  (a3)+,(a1)+
        bra.s   61b
62:     addq.l  #4,sp
        rts                             | a1 = new end

90:     movea.l (sp)+,a1                | scratch too small or nothing to do:
                                        | the take is unchanged
        rts

| Quantize d0 (time, >= 0) to the swung grid: d1 = grid, d2 = offset
| (added on odd lines, 0 <= offset <= grid/2). With s = time / grid and
| r = time mod grid, only lines s and s+1 can be nearest: line s is
| |r - e| away (e = offset if s is odd, else 0), line s+1 is grid + e' - r
| away (e' = offset if s is even). Ties go to the later line, as in
| tools/swing.py quantize() at strength 100. Out: d0. Keeps the others.
quantize:
        movem.l d3-d6,-(sp)
        move.l  d0,d3
        divu.w  d1,d3                   | d3 = r:s
        bvs.s   9f                      | (time / grid > 65535: leave it)
        move.l  d3,d4
        swap    d4
        andi.l  #0xFFFF,d4              | d4 = r
        moveq   #0,d5                   | d5 = e
        moveq   #0,d6                   | d6 = e'
        btst    #0,d3
        beq.s   1f
        move.w  d2,d5                   | s odd
        bra.s   2f
1:      move.w  d2,d6                   | s even
2:      sub.l   d4,d0                   | d0 = s * grid
        move.w  d4,d3
        sub.w   d5,d3
        bpl.s   3f
        neg.w   d3                      | d3 = |r - e|
3:      add.w   d1,d6
        sub.w   d4,d6                   | d6 = grid + e' - r
        cmp.w   d3,d6
        bhi.s   4f                      | line s is nearer
        add.l   d4,d0                   | line s+1: s * grid + r + d6
        add.l   d6,d0
        bra.s   9f
4:      add.l   d5,d0                   | line s
9:      movem.l (sp)+,d3-d6
        rts

| ------------------------------------------------------------- fast path
| swing_fast: walk the take once and move each off-grid note locally (the
| notes from earlier passes are on the grid already): shift the events
| between its old and new place by its 6 bytes and fix three gaps. Mirrors
| tools/seqstream.py _fast. Returns d0.w = 0 when done, 1 when it had to stop
| (a gap over 127, or a 1-word / time event, where a gap must go; a move
| back over more than HISTORY events). A note that quantizes onto the end
| wraps to the start, after the opening events.
| The take keeps its size. In: a0, a1, a4 as swing_take. Uses all
| registers; a0, a1, a4 stay.
|
| a6 = this event, a3 = the event before it (0: none), d7 = its time,
| d6 = floor, d4 bit 0 = a note has been seen, d5 = q. Locals (sp):
        .equ    HISTORY, 16
        .equ    L_GAPN, 0               | the note's gap
        .equ    L_TFAR, 4               | later: tm; earlier: tr
        .equ    L_PFAR, 8               | later: last (0 = none); earlier: p
        .equ    L_TP,   12              | earlier: tp (time of p)
        .equ    L_CNT,  16              | earlier: events walked back
        .equ    L_GB,   20              | new gaps: b (before the note),
        .equ    L_GP,   24              |  p / last,
        .equ    L_GN,   28              |  the note
        .equ    L_LOGP, 32              | log mode: next log entry,
        .equ    L_LOGN, 36              |  entries left,
        .equ    L_BASE, 40              |  sequencer memory base,
        .equ    L_LO,   44              |  a later move: [lo, hi) moved
        .equ    L_HI,   48              |  down by 6
        .equ    L_MODE, 52              | d4's mode bits (restored after moves)
        .equ    L_SIZE, 56              | (plus the word under the sentinel)

swing_fast:
        move.w  (a1),-(sp)              | sentinel at the end (restored below)
        move.w  #0x8000,(a1)
        lea     -L_SIZE(sp),sp
        move.l  #1,L_MODE(sp)
        movea.l a0,a6
        suba.l  a3,a3
        moveq   #0,d7
        moveq   #0,d6
        moveq   #0,d4
f_loop: cmpa.l  a1,a6
        bhs     f_done
        movea.l a6,a5
        bsr     evinfo                  | d1 code, d2 length, d3 gap
        cmpi.w  #0xB0,d1
        bhs     f_other
f_note: bset    #0,d4                   | a note
        moveq   #15,d0
        and.w   (a6),d0
        cmpi.w  #8,d0
        bhs     f_next
        cmp.l   d6,d7
        beq     f_next                  | at the floor: it stays
        lsl.w   #2,d0
        move.w  0(a4,d0.w),d1           | grid
        beq     f_next
        move.l  d3,L_GAPN(sp)
        move.w  2(a4,d0.w),d2           | swing offset
        move.l  d7,d0
        bsr     quantize
        cmp.l   d6,d0
        bge.s   1f
        move.l  d6,d0
1:      move.l  d0,d5                   | d5 = q
        cmp.l   d7,d5
        beq     f_note_next
        cmpa.w  #0,a3
        beq     f_stop                  | nothing before the note
        cmp.l   d7,d5
        blt     f_earlier

| ---- later: the events before q go in front of the note
        lea     6(a6),a2                | a2 = m
        move.l  d7,d0
        add.l   L_GAPN(sp),d0
        move.l  d0,L_TFAR(sp)           | tm
        clr.l   L_PFAR(sp)
2:      move.l  L_TFAR(sp),d0
        cmp.l   d5,d0
        bge.s   3f
        cmpa.l  a1,a2
        bhs     f_wrap
        movea.l a2,a5
        bsr     evinfo
        cmpi.w  #END_CODE,d1
        beq     f_wrap                  | past the end: wrap to the start
        move.l  a2,L_PFAR(sp)
        add.l   d3,L_TFAR(sp)
        adda.w  d2,a2
        bra.s   2b
3:      cmpa.l  a1,a2                   | END at or before q: wrap
        bhs.s   4f
        movea.l a2,a5
        bsr     evinfo
        cmpi.w  #END_CODE,d1
        bne.s   4f
        move.l  L_TFAR(sp),d0
        cmp.l   d5,d0
        ble     f_wrap
4:      tst.l   L_PFAR(sp)
        bne.s   f_later_move
        movea.l a3,a5                   | nothing in between. b: + (q - t)
        bsr     evinfo
        add.l   d5,d3
        sub.l   d7,d3
        bsr     gap_check
        bne     f_stop
        move.l  d3,L_GB(sp)
        move.l  L_GAPN(sp),d3           | note: - (q - t)
        sub.l   d5,d3
        add.l   d7,d3
        bsr     note_gap_check
        bne     f_stop
        move.l  d3,L_GN(sp)
        bsr     evinfo                  | b again (a5): d2
        move.l  L_GB(sp),d3
        bsr     set_gap
        movea.l a6,a5
        moveq   #6,d2
        move.l  L_GN(sp),d3
        bsr     set_gap
        bra     f_note_next

f_later_move:
        movea.l L_PFAR(sp),a5           | last: q - its time
        bsr     evinfo
        move.l  L_TFAR(sp),d0
        sub.l   d3,d0                   | its time = tm - its gap
        move.l  d5,d3
        sub.l   d0,d3
        bsr     gap_check
        bne     f_stop
        move.l  d3,L_GP(sp)
        move.l  L_TFAR(sp),d3           | note: tm - q
        sub.l   d5,d3
        bsr     note_gap_check
        bne     f_stop
        move.l  d3,L_GN(sp)
        movea.l a3,a5                   | b: + the note's gap
        bsr     evinfo
        add.l   L_GAPN(sp),d3
        bsr     gap_check
        bne     f_stop
        bsr     set_gap                 | edits from here on
        movea.l L_PFAR(sp),a5
        bsr     evinfo
        move.l  L_GP(sp),d3
        bsr     set_gap
        adda.w  d2,a5                   | a5 = end of the block (m)
        move.l  a5,d1
        movem.w (a6),d2-d4              | the note (d4: its bit 0 is restored
        movea.l a6,a2                   |  below - a note has been seen)
        lea     6(a6),a5
5:      cmpa.l  d1,a5                   | [note+6, m) down by 6
        bhs.s   6f
        move.w  (a5)+,(a2)+
        bra.s   5b
6:      movea.l a2,a5                   | the note at m - 6
        move.w  d2,(a2)+
        move.w  d3,(a2)+
        move.w  d4,(a2)+
        move.l  L_MODE(sp),d4           | (bit 1: log mode; bit 0 set)
        moveq   #6,d2
        move.l  L_GN(sp),d3
        bsr     set_gap
        move.l  a5,-(sp)                | the note's new place
        lea     6(a6),a5
        move.l  a5,L_LO+4(sp)           | [note+6, m) moved down by 6
        move.l  d1,L_HI+4(sp)
        move.l  a5,d0                   | held notes' duration pointers
        moveq   #-6,d2
        movea.l a6,a2
        movea.l (sp)+,a5
        bsr     fix_open_notes
        btst    #1,d4
        bne     l_after_later
        move.l  L_GAPN(sp),d0           | on with the first moved event:
        add.l   d0,d7                   | a6 points at it, time t + gap
        bra     f_loop

| ---- earlier: the events after q go behind the note
f_earlier:
        movea.l a6,a2                   | a2 = r
        move.l  d7,L_TFAR(sp)           | tr
        clr.l   L_CNT(sp)
7:      movea.l a2,a5
        bsr     prev_event              | a5 = p, the event before r
        bne     f_stop
        bsr     evinfo
        move.l  L_TFAR(sp),d0
        sub.l   d3,d0                   | tp
        cmp.l   d5,d0
        ble.s   8f
        movea.l a5,a2                   | r = p
        move.l  d0,L_TFAR(sp)
        addq.l  #1,L_CNT(sp)
        cmpi.l  #HISTORY,L_CNT(sp)
        bhi     f_stop
        bra.s   7b
8:
f_earlier_found:                        | a5 = p (time d0), a2 = r (L_TFAR)
        move.l  a5,L_PFAR(sp)
        move.l  d0,L_TP(sp)
        cmpa.l  a6,a2
        bne.s   f_earlier_move
        movea.l a3,a5                   | nothing in between. b: - (t - q)
        bsr     evinfo
        sub.l   d7,d3
        add.l   d5,d3
        bsr     gap_check
        bne     f_stop
        move.l  d3,L_GB(sp)
        move.l  L_GAPN(sp),d3           | note: + (t - q)
        add.l   d7,d3
        sub.l   d5,d3
        bsr     note_gap_check
        bne     f_stop
        move.l  d3,L_GN(sp)
        bsr     evinfo
        move.l  L_GB(sp),d3
        bsr     set_gap
        movea.l a6,a5
        moveq   #6,d2
        move.l  L_GN(sp),d3
        bsr     set_gap
        bra     f_note_next

f_earlier_move:                         | a5 = p, a2 = r
        bsr     evinfo                  | p: q - tp
        move.l  d5,d3
        sub.l   L_TP(sp),d3
        bsr     gap_check
        bne     f_stop
        move.l  d3,L_GP(sp)
        move.l  L_TFAR(sp),d3           | note: tr - q
        sub.l   d5,d3
        bsr     note_gap_check
        bne     f_stop
        move.l  d3,L_GN(sp)
        movea.l a3,a5                   | b: + the note's gap
        bsr     evinfo
        add.l   L_GAPN(sp),d3
        bsr     gap_check
        bne     f_stop
        bsr     set_gap                 | edits from here on
        movea.l L_PFAR(sp),a5
        bsr     evinfo
        move.l  L_GP(sp),d3
        bsr     set_gap
        movem.w (a6),d2-d4              | the note
        lea     6(a6),a5                | [r, note) up by 6
        movea.l a6,a3
9:      cmpa.l  a2,a3
        bls.s   10f
        move.w  -(a3),-(a5)
        bra.s   9b
10:     movea.l a2,a5                   | the note at r
        move.w  d2,(a5)+
        move.w  d3,(a5)+
        move.w  d4,(a5)+
        subq.l  #6,a5
        move.l  L_MODE(sp),d4
        moveq   #6,d2
        move.l  L_GN(sp),d3
        bsr     set_gap
        move.l  a2,d0                   | held notes' duration pointers:
        move.l  a6,d1                   | [r, note) moved up by 6, the
        moveq   #6,d2                   | note from a6 to r
        movem.l a2/a5,-(sp)
        movea.l a6,a2
        bsr     fix_open_notes
        movem.l (sp)+,a2/a5
        btst    #1,d4
        bne     l_next
        lea     6(a6),a6                | on with the event after the note,
        move.l  L_GAPN(sp),d0           | at t + the note's old gap
        add.l   d0,d7
        movea.l a6,a5                   | the event before it
        bsr     prev_event
        movea.l a5,a3
        bra     f_loop

| ---- wrap: a note that quantizes onto the end goes to the start, after
| the events at or before the floor (r = the first event after it)
f_wrap: move.l  d6,d5                   | q = floor
        movea.l a0,a2
        clr.l   L_TFAR(sp)
11:     move.l  L_TFAR(sp),d0
        cmp.l   d5,d0
        bgt.s   12f
        movea.l a2,a5
        bsr     evinfo
        move.l  L_TFAR(sp),L_TP(sp)     | time of this event (p if last)
        move.l  a2,L_PFAR(sp)
        add.l   d3,L_TFAR(sp)
        adda.w  d2,a2
        bra.s   11b
12:     movea.l L_PFAR(sp),a5
        move.l  L_TP(sp),d0
        bra     f_earlier_found

f_other:
        btst    #0,d4
        bne.s   f_next
        cmpi.w  #TIME_CODE,d1
        beq.s   f_next
        move.l  d7,d6                   | an opening event: the floor
f_next: btst    #1,d4
        bne     l_next
        movea.l a6,a3
        adda.w  d2,a6
        add.l   d3,d7
        bra     f_loop
f_note_next:                            | a note handled (6 bytes)
        btst    #1,d4
        bne     l_next
        movea.l a6,a3
        lea     6(a6),a6
        add.l   L_GAPN(sp),d7
        bra     f_loop

f_stop: lea     L_SIZE(sp),sp
        move.w  (sp)+,(a1)
        moveq   #1,d0
        rts
f_done: lea     L_SIZE(sp),sp
        move.w  (sp)+,(a1)
        moveq   #0,d0
        rts

| ------------------------------------------------------------- log mode
| swing_logged: like swing_fast, but only the logged notes are looked at
| (src/looprec.s logs each note recorded in the pass: its offset from the
| sequencer base, its time, and its quantized time, worked out when it was
| recorded so the wrap has less to do). In: a0, a1, a4 as swing_take,
| a2 = log entries (offset.l, time.l, q.l), d0.w = how many, a5 = base.
| Out: d0.w = 0 done, 1 stopped (the caller then runs swing_full).
        .globl  swing_logged
swing_logged:
        move.w  (a1),-(sp)              | sentinel, as swing_fast
        move.w  #0x8000,(a1)
        lea     -L_SIZE(sp),sp
        move.l  #3,L_MODE(sp)           | log mode
        move.l  a2,L_LOGP(sp)
        andi.l  #0xFFFF,d0
        move.l  d0,L_LOGN(sp)
        move.l  a5,L_BASE(sp)
        moveq   #3,d4
        moveq   #0,d6                   | floor: the last opening event's
        moveq   #0,d7                   | time (scan to the first note)
        movea.l a0,a6
1:      cmpa.l  a1,a6
        bhs.s   l_next
        movea.l a6,a5
        bsr     evinfo
        cmpi.w  #0xB0,d1
        bcs.s   l_next
        cmpi.w  #TIME_CODE,d1
        beq.s   2f
        move.l  d7,d6
2:      add.l   d3,d7
        adda.w  d2,a6
        bra.s   1b

l_next: subq.l  #1,L_LOGN(sp)
        bmi     f_done
        movea.l L_LOGP(sp),a2
        movea.l L_BASE(sp),a6
        adda.l  (a2)+,a6                | the note
        move.l  (a2)+,d7                | its time
        move.l  (a2)+,d5                | its quantized time
        move.l  a2,L_LOGP(sp)
        cmpa.l  a0,a6                   | in the take, and a note?
        bls     f_stop
        cmpa.l  a1,a6
        bhs     f_stop
        tst.w   (a6)
        bpl     f_stop
        movea.l a6,a5
        bsr     prev_event
        bne     f_stop
        movea.l a5,a3                   | a3 = b, the event before the note
| The usual case inline: nothing between the note's old and new time (the
| earlier notes sit on the grid lines), so only b's gap and the note's
| change. b's last word is the word before the note.
        move.w  (a6),d0
        move.w  d0,d1
        lsr.w   #4,d1
        andi.w  #0xFF,d1
        cmpi.w  #0xB0,d1
        bhs     f_stop                  | not a note
        moveq   #15,d1
        and.w   d0,d1
        cmpi.w  #8,d1
        bhs     l_next
        cmp.l   d6,d7
        beq     l_next                  | at the floor: stays
        lsl.w   #2,d1
        tst.w   0(a4,d1.w)              | grid
        beq     l_next
        move.l  d5,d0                   | q (logged), not before the floor
        cmp.l   d6,d0
        bge.s   1f
        move.l  d6,d0
1:      move.l  d0,d5
        sub.l   d7,d0                   | q - t
        beq     l_next
        move.w  (a6),d2                 | note gap: w0 14-12, w2 14-11
        andi.w  #0x7000,d2
        lsr.w   #8,d2
        move.w  4(a6),d3
        andi.w  #0x7800,d3
        rol.w   #5,d3
        or.w    d3,d2                   | d2 = the note's gap
        lea     -2(a6),a5               | b's last word
        cmpa.l  a3,a5
        beq     l_general               | b is 1 word
        move.w  (a3),d3
        move.w  d3,d1
        lsr.w   #4,d1
        andi.w  #0xFF,d1
        cmpi.w  #TIME_CODE,d1
        beq     l_general
        andi.w  #0x7000,d3              | b's gap
        lsr.w   #8,d3
        move.w  (a5),d1
        andi.w  #0x7800,d1
        rol.w   #5,d1
        or.w    d1,d3                   | d3 = b's gap
        tst.l   d0
        bmi.s   2f
        | later by d0: the next event must be at or after q, and not an END
        | the note would reach (wrap)
        move.w  d2,d1
        sub.w   d0,d1                   | the note's new gap (t + gap >= q?)
        bmi.s   l_general
        lea     6(a6),a2
        cmpa.l  a1,a2
        bhs.s   l_general
        move.w  (a2),d4
        lsr.w   #4,d4
        andi.w  #0xFF,d4
        cmpi.w  #END_CODE,d4
        bne.s   3f
        tst.w   d1                      | END at q: wrap
        beq.s   l_general
3:      add.w   d0,d3                   | b's new gap
        cmpi.w  #127,d3
        bhi.s   l_general
        bra.s   4f
2:      | earlier by -d0: b must be at or before q
        add.w   d0,d3                   | b's new gap (b's time <= q?)
        bmi.s   l_general
        move.w  d2,d1
        sub.w   d0,d1                   | the note's new gap
        cmpi.w  #127,d1
        bhi.s   l_general
4:      move.w  d3,d0                   | write b's gap (w0 at a3, last at a5)
        lsl.w   #8,d0
        andi.w  #0x7000,d0
        andi.w  #0x8FFF,(a3)
        or.w    d0,(a3)
        move.w  d3,d0
        ror.w   #5,d0
        andi.w  #0x7800,d0
        andi.w  #0x87FF,(a5)
        or.w    d0,(a5)
        move.w  d1,d0                   | and the note's (w0, w2)
        lsl.w   #8,d0
        andi.w  #0x7000,d0
        andi.w  #0x8FFF,(a6)
        or.w    d0,(a6)
        move.w  d1,d0
        ror.w   #5,d0
        andi.w  #0x7800,d0
        andi.w  #0x87FF,4(a6)
        or.w    d0,4(a6)
        moveq   #3,d4
        bra     l_next

l_general:                              | everything else: the general move
        moveq   #3,d4
        movea.l a6,a5
        bsr     evinfo
        bra     f_note

l_after_later:                          | the rest of the log: pointers in
        move.l  L_LOGP(sp),a2           | [lo, hi) are 6 lower now
        move.l  L_LOGN(sp),d0
        movea.l L_BASE(sp),a5
        bra.s   2f
1:      move.l  (a2),d1
        add.l   a5,d1
        cmp.l   L_LO(sp),d1
        bcs.s   3f
        cmp.l   L_HI(sp),d1
        bcc.s   3f
        subq.l  #6,(a2)
3:      lea     12(a2),a2
2:      dbf     d0,1b
        bra     l_next

| fix_open_notes: after a block of the take moved, keep the OS's held-note
| records right. Each (list at 0xFF8134, linked by +0) holds at +6 the
| offset of its note's duration word in the take buffer (bit 0: buffer B),
| written into at note-off (0xFF74C2). d0/d1 = the block [lo, hi) that
| moved by d2.w bytes; a2 = the note's old address, a5 = its new one.
| Keeps every register.
fix_open_notes:
        movem.l d0-d6/a0-a2/a5,-(sp)
        ext.l   d2
        movea.w OPEN_NOTES.w,a0
1:      cmpa.w  #0,a0
        beq.s   9f
        moveq   #0,d3
        move.w  6(a0),d3
        move.l  BUF_A.w,d4
        btst    #0,d3
        beq.s   2f
        move.l  BUF_B.w,d4
2:      add.l   SEQ_BASE.w,d4           | d4 = the buffer's address
        move.l  d3,d5
        andi.w  #0xFFFE,d5
        add.l   d4,d5                   | d5 = the duration word's address
        lea     2(a2),a1
        cmpa.l  d5,a1
        bne.s   3f
        lea     2(a5),a1                | the moved note
        move.l  a1,d5
        bra.s   4f
3:      cmp.l   d0,d5
        bcs.s   5f
        cmp.l   d1,d5
        bcc.s   5f
        add.l   d2,d5                   | in the moved block
4:      sub.l   d4,d5
        andi.w  #1,d3
        or.w    d3,d5
        move.w  d5,6(a0)
5:      movea.w (a0),a0
        bra.s   1b
9:      movem.l (sp)+,d0-d6/a0-a2/a5
        rts

| note_gap_check: can a note carry gap d3 (0-127)? Z set if so.
note_gap_check:
        tst.l   d3
        bmi.s   1f
        cmpi.l  #127,d3
        bhi.s   1f
        cmp.w   d3,d3                   | Z
1:      rts

| evinfo: event at a5 -> d1.w = code, d2.w = length in bytes, d3.l = its
| gap (7-bit, 14-bit for time events, 0 for 1-word events). Uses d0.
| swing_fast keeps a sentinel word (bit 15 set) at the take's end, so the
| next event start is found without bounds checks.
evinfo:
        move.w  (a5),d0
        move.w  d0,d1
        lsr.w   #4,d1
        andi.w  #0xFF,d1
        moveq   #2,d2
        tst.w   2(a5)
        bmi.s   2f
        moveq   #4,d2
        tst.w   4(a5)
        bmi.s   2f
        moveq   #6,d2
1:      tst.w   0(a5,d2.w)
        bmi.s   2f
        addq.w  #2,d2
        bra.s   1b
2:      moveq   #0,d3
        cmpi.w  #TIME_CODE,d1
        bne.s   3f
        move.w  d0,d3                   | time event: 14 bits
        andi.w  #0x7000,d3
        lsr.w   #1,d3
        move.w  2(a5),d0
        lsr.w   #4,d0
        andi.w  #0x7FF,d0
        or.w    d0,d3
        rts
3:      cmpi.w  #2,d2
        bls.s   4f
        andi.w  #0x7000,d0              | 7 bits: w0 14-12, last word 14-11
        lsr.w   #8,d0
        move.w  d0,d3
        move.w  -2(a5,d2.w),d0
        andi.w  #0x7800,d0
        rol.w   #5,d0
        or.w    d0,d3
4:      rts

| gap_check: can the event (code d1, length d2) carry gap d3? Z set if so.
gap_check:
        cmpi.w  #2,d2
        bls.s   1f
        cmpi.w  #TIME_CODE,d1
        beq.s   1f
        tst.l   d3
        bmi.s   1f
        cmpi.l  #127,d3
        bhi.s   1f
        cmp.w   d3,d3                   | Z
        rts
1:      cmpi.w  #1,d2                   | (never 1: NZ)
        rts

| set_gap: write the 7-bit gap d3 into the event at a5 (length d2).
set_gap:
        move.l  d0,-(sp)
        andi.w  #0x8FFF,(a5)
        move.w  d3,d0
        lsl.w   #8,d0
        andi.w  #0x7000,d0
        or.w    d0,(a5)
        andi.w  #0x87FF,-2(a5,d2.w)
        move.w  d3,d0
        lsl.w   #8,d0
        lsl.w   #3,d0
        andi.w  #0x7800,d0
        or.w    d0,-2(a5,d2.w)
        move.l  (sp)+,d0
        rts

| prev_event: a5 -> the start of the event before it. NZ if there is none.
prev_event:
        cmpa.l  a0,a5
        bls.s   2f
1:      subq.l  #2,a5
        tst.w   (a5)
        bmi.s   3f
        cmpa.l  a0,a5
        bhi.s   1b
2:      moveq   #1,d0                   | (NZ)
        rts
3:      cmp.w   d0,d0                   | Z
        rts
