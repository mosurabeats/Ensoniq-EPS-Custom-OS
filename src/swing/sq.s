| Swing quantize a take in one streaming pass (EPS OS 2.49, hardware build)
|
| Same result as tools/seqstream.py quantize_take (one setting for every
| note; the take is one track): each note moves to the nearest line of the
| swung grid, notes that land on or after the END event wrap to the take's
| floor (the time of its opening events), nothing goes before the floor,
| notes at the floor stay, and events keep their order at equal times.
|
| No sort over the whole take: a note moves less than one grid step back
| (quantize picks line s or s+1 of t = s * grid + r), so once the scan is
| at time t, nothing still to come lands before t - grid. Events wait in a
| small buffer (sorted by new time) until the scan is a grid past them,
| then go out. Notes that wrap are found first (pass 2) and go out right
| after the events at the floor. The output is written after the take, in
| the free sequencer memory (the old code area's scratch), then copied
| back: event words only, so all of it is 13-bit safe (bits 2-0 stay 0).
|
| Event format (tools/seqstream.py): first word bit 15 set, code in bits
| 11-4; notes (code < 0xB0) are 3 words; time events (0xB9) carry a 14-bit
| gap; other events of 2+ words carry a 7-bit gap to the next event (w0
| bits 14-12, last word bits 14-11); 1-word events (START 0xBB, END 0xBC)
| none.
|
| In:  a0 = take, a1 = its end, a3 = end of the free memory after it,
|      d1.w = grid (ticks; 0: no quantize), d2.w = swing offset (added on
|      odd lines), d0.b != 0: drop the notes tagged for undo (bit 3 of
|      their last word: src/swing/window.s, undo).
| Out: a1 = new end (as it was if nothing moved, or on overflow).
| Uses all registers but a7.

        .equ    C_TIME,     0xB9
        .equ    C_END,      0xBC
        .equ    NBMAX,      32          | buffered events
        .equ    NWMAX,      16          | wrapping notes
        .equ    MAX_TIME,   0x3FFF

        .text
        .globl  sq
sq:     lea     sqv(pc),a5
        move.b  d0,V_KILL(a5)
        move.l  sp,V_SP(a5)             | (overflow: back to the caller)
        move.l  a1,V_OUT0(a5)
        move.l  a3,V_LIM(a5)
        andi.l  #0xFFFF,d1
        andi.l  #0xFFFF,d2

| (1) the floor (time of the last event before the first note) and END
        clr.l   V_FLOOR(a5)
        moveq   #-1,d0
        move.l  d0,V_END(a5)
        sf      V_SEEN(a5)
        moveq   #0,d7
        movea.l a0,a6
10:     cmpa.l  a1,a6
        bhs.s   20f
        movea.l a6,a3
        bsr     evnext
        cmpi.w  #C_TIME,d4
        beq.s   14f
        cmpi.w  #0xB0,d4
        bcc.s   12f
        bsr     killed                  | (an undone note isn't there)
        bne.s   14f
        st      V_SEEN(a5)
        bra.s   14f
12:     tst.b   V_SEEN(a5)
        bne.s   13f
        move.l  d7,V_FLOOR(a5)
13:     cmpi.w  #C_END,d4
        bne.s   14f
        tst.l   V_END(a5)
        bpl.s   14f
        move.l  d7,V_END(a5)
14:     add.l   d5,d7
        bra.s   10b

| (2) notes that land on or after END: they wrap to the floor
20:     clr.w   V_NW(a5)
        tst.l   V_END(a5)
        bmi.s   30f
        lea     sqwrap(pc),a2
        moveq   #0,d7
        movea.l a0,a6
21:     cmpa.l  a1,a6
        bhs.s   30f
        movea.l a6,a3
        bsr     evnext
        cmpi.w  #0xB0,d4
        bcc.s   24f
        bsr     killed
        bne.s   24f
        cmp.l   V_FLOOR(a5),d7
        beq.s   24f
        move.l  d7,d0
        bsr     quantize
        cmp.l   V_END(a5),d0
        blt.s   24f
        cmpi.w  #NWMAX,V_NW(a5)
        bhs     fail
        move.l  a3,d0
        sub.l   a0,d0
        move.w  d0,(a2)+                | its offset and length
        move.w  d3,(a2)+
        addq.w  #1,V_NW(a5)
24:     add.l   d5,d7
        bra.s   21b

| (3) the take in order of new time
30:     lea     sqwrap(pc),a2
        move.l  a2,V_WRP(a5)
        move.w  V_NW(a5),V_WLEFT(a5)
        clr.w   V_NB(a5)
        sf      V_PREV(a5)
        sf      V_WDONE(a5)
        sf      V_MOVED(a5)
        clr.l   V_EOFF(a5)              | (END's length 0: none)
        movea.l V_OUT0(a5),a4
        moveq   #0,d7
        movea.l a0,a6
31:     cmpa.l  a1,a6
        bhs     40f
        movea.l a6,a3
        bsr     evnext
        cmpi.w  #C_TIME,d4
        beq.s   38f
        cmpi.w  #C_END,d4
        bne.s   32f
        tst.w   V_ELEN(a5)
        bne.s   32f                     | (a second END: an ordinary event)
        move.l  a3,d0
        sub.l   a0,d0
        move.w  d0,V_EOFF(a5)
        move.w  d3,V_ELEN(a5)
        bra.s   38f
32:     tst.w   V_WLEFT(a5)             | a wrapping note: already placed
        beq.s   33f
        movea.l V_WRP(a5),a2
        move.l  a3,d0
        sub.l   a0,d0
        cmp.w   (a2),d0
        bne.s   33f
        addq.l  #4,V_WRP(a5)
        subq.w  #1,V_WLEFT(a5)
        st      V_MOVED(a5)
        bra.s   38f
33:     move.l  d7,d0                   | d0 = new time
        cmpi.w  #0xB0,d4
        bcc.s   35f
        bsr     killed
        beq.s   36f
        st      V_MOVED(a5)             | undone: left out
        bra.s   38f
36:
        cmp.l   V_FLOOR(a5),d7
        beq.s   35f
        bsr     quantize
        cmp.l   V_FLOOR(a5),d0
        bge.s   34f
        move.l  V_FLOOR(a5),d0
34:     cmp.l   d7,d0
        beq.s   35f
        st      V_MOVED(a5)
35:     move.l  d7,d6                   | out with what's a grid behind
        sub.l   d1,d6
        bsr     flush
        bsr     insert
38:     add.l   d5,d7
        bra     31b

40:     moveq   #-1,d6                  | the rest, then END
        lsr.l   #1,d6
        bsr     flush
        move.w  V_ELEN(a5),d3
        beq.s   41f
        move.l  V_END(a5),d0
        moveq   #0,d6
        move.w  V_EOFF(a5),d6
        lea     (a0,d6.l),a3
        bsr     emit
41:     tst.b   V_WDONE(a5)             | (no event after the floor)
        bne.s   42f
        bsr     wraps
42:     tst.b   V_MOVED(a5)
        beq     fail                    | nothing moved: the take stays
        movea.l V_OUT0(a5),a2           | copy back (the output is after the
        movea.l a0,a3                   | take: forwards is safe)
43:     cmpa.l  a4,a2
        bhs.s   44f
        move.w  (a2)+,(a3)+
        bra.s   43b
44:     movea.l a3,a1
        rts

fail:   movea.l V_SP(a5),sp             | the take is unchanged
        rts

| Events whose new time is at most d6 go out, in order. Keeps d0-d7, a3.
flush:  movem.l d0-d5/a3,-(sp)
1:      tst.w   V_NB(a5)
        beq.s   9f
        lea     sqbuf(pc),a2
        cmp.l   (a2),d6
        blt.s   9f
        move.l  (a2),d0
        moveq   #0,d3
        move.w  4(a2),d3
        lea     (a0,d3.l),a3
        move.w  6(a2),d3
        bsr     emit
        lea     sqbuf(pc),a2            | drop it: the rest moves down
        move.w  V_NB(a5),d0
        subq.w  #1,d0
        move.w  d0,V_NB(a5)
        bra.s   3f
2:      move.l  8(a2),(a2)+
        move.l  8(a2),(a2)+
3:      dbra    d0,2b
        bra.s   1b
9:      movem.l (sp)+,d0-d5/a3
        rts

| Buffer the event at a3 (d3 bytes) with new time d0, after the ones with
| the same time (stable). Keeps d0-d7, a3.
insert: cmpi.w  #NBMAX,V_NB(a5)
        bhs     fail
        lea     sqbuf(pc),a2
        move.w  V_NB(a5),d6
        lsl.w   #3,d6
        adda.w  d6,a2
1:      lea     sqbuf(pc),a6
        cmpa.l  a6,a2
        bls.s   2f
        cmp.l   -8(a2),d0
        bge.s   2f
        move.l  -8(a2),(a2)
        move.l  -4(a2),4(a2)
        subq.l  #8,a2
        bra.s   1b
2:      move.l  d0,(a2)
        move.l  a3,d6
        sub.l   a0,d6
        move.w  d6,4(a2)
        move.w  d3,6(a2)
        addq.w  #1,V_NB(a5)
        movea.l a3,a6                   | (restore the scan pointer)
        adda.l  d3,a6
        rts

| Emit the wrapping notes at the floor (once).
wraps:  st      V_WDONE(a5)
        movem.l d0/d3/d6/a3,-(sp)
        lea     sqwrap(pc),a2
        move.w  V_NW(a5),d6
        bra.s   2f
1:      move.l  V_FLOOR(a5),d0
        moveq   #0,d3
        move.w  (a2)+,d3
        lea     (a0,d3.l),a3
        move.w  (a2)+,d3
        move.l  a2,-(sp)
        bsr.s   emit1
        movea.l (sp)+,a2
2:      dbra    d6,1b
        movem.l (sp)+,d0/d3/d6/a3
        rts

| Write the event at a3 (d3 bytes) at new time d0: first the gap from the
| one before (into it, or time events after it), then the event with its
| gap cleared. The wrapping notes go first when d0 passes the floor.
emit:   tst.b   V_WDONE(a5)
        bne.s   emit1
        cmp.l   V_FLOOR(a5),d0
        ble.s   emit1
        bsr.s   wraps
emit1:  movem.l d0-d3/a2-a3,-(sp)
        tst.b   V_PREV(a5)
        beq.s   5f
        move.l  d0,d2
        sub.l   V_PT(a5),d2             | d2 = gap
        movea.l V_PPOS(a5),a2
        move.w  V_PLEN(a5),d1
        cmpi.w  #2,d1
        bls.s   2f                      | 1-word: time events
        cmpi.l  #127,d2
        bhi.s   2f
        move.w  d2,d0                   | into the event: high 3 bits in w0
        lsl.w   #8,d0                   | 14-12, low 4 in its last word 14-11
        andi.w  #0x7000,d0
        or.w    d0,(a2)
        move.w  d2,d0
        ror.w   #5,d0
        andi.w  #0x7800,d0
        or.w    d0,-2(a2,d1.w)
        bra.s   5f
2:      tst.l   d2
        beq.s   5f
        move.l  d2,d0
        cmpi.l  #MAX_TIME,d0
        bls.s   3f
        move.l  #MAX_TIME,d0
3:      sub.l   d0,d2
        lea     4(a4),a2
        cmpa.l  V_LIM(a5),a2
        bhi     fail
        move.w  d0,d1                   | w0 = 0x8B90 | gap bits 13-11 << 12
        add.w   d1,d1
        andi.w  #0x7000,d1
        ori.w   #0x8B90,d1
        move.w  d1,(a4)+
        lsl.w   #4,d0                   | w1 = gap bits 10-0 << 4
        andi.w  #0x7FF0,d0
        move.w  d0,(a4)+
        bra.s   2b
5:      movem.l (sp),d0-d3/a2-a3
        lea     (a4,d3.w),a2
        cmpa.l  V_LIM(a5),a2
        bhi     fail
        move.l  d0,V_PT(a5)
        move.l  a4,V_PPOS(a5)
        move.w  d3,V_PLEN(a5)
        st      V_PREV(a5)
        movea.l a4,a2
        lsr.w   #1,d3
        subq.w  #1,d3
6:      move.w  (a3)+,(a4)+
        dbra    d3,6b
        andi.w  #0x8FFF,(a2)            | gap cleared
        move.w  V_PLEN(a5),d3
        cmpi.w  #2,d3
        bls.s   7f
        andi.w  #0x87FF,-2(a4)
7:      movem.l (sp)+,d0-d3/a2-a3
        rts

| Z clear if the note at a3 is to be dropped (undo). Keeps the others.
killed: tst.b   V_KILL(a5)
        beq.s   9f
        btst    #3,5(a3)                | its last word's bit 3
9:      rts

| The event at a6: d0.w = first word, d4.w = code, d3.l = length in bytes,
| d5.l = its gap; a6 = the next event. Uses d6.
evnext: move.l  a6,d3
        move.w  (a6)+,d0
1:      cmpa.l  a1,a6
        bhs.s   2f
        tst.w   (a6)
        bmi.s   2f
        addq.l  #2,a6
        bra.s   1b
2:      neg.l   d3
        add.l   a6,d3
        move.w  d0,d4
        lsr.w   #4,d4
        andi.w  #0xFF,d4
        moveq   #0,d5
        cmpi.w  #C_TIME,d4
        bne.s   3f
        move.w  d0,d5                   | time event: 14 bits
        andi.w  #0x7000,d5
        lsr.w   #1,d5
        move.w  -2(a6),d6
        lsr.w   #4,d6
        andi.w  #0x7FF,d6
        or.w    d6,d5
        rts
3:      cmpi.w  #2,d3
        bls.s   9f                      | 1-word: no gap
        move.w  d0,d5
        andi.w  #0x7000,d5
        lsr.w   #8,d5
        move.w  -2(a6),d6
        andi.w  #0x7800,d6
        rol.w   #5,d6
        or.w    d6,d5
9:      rts

| Quantize d0 (time, >= 0) to the swung grid: d1 = grid, d2 = offset
| (added on odd lines, 0 <= offset <= grid/2). With s = time / grid and
| r = time mod grid, only lines s and s+1 can be nearest: line s is
| |r - e| away (e = offset if s is odd, else 0), line s+1 is grid + e' - r
| away (e' = offset if s is even). Ties go to the later line, as in
| tools/swing.py quantize() at strength 100. Out: d0. Keeps the others.
quantize:
        tst.w   d1
        beq.s   99f                     | no grid: as played
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
99:     rts

| Variables (a5) and buffers.
        .balign 2
sqv:    .space  50
        .equ    V_SP,    0
        .equ    V_OUT0,  4
        .equ    V_LIM,   8
        .equ    V_FLOOR, 12
        .equ    V_END,   16
        .equ    V_PT,    20
        .equ    V_PPOS,  24
        .equ    V_WRP,   28
        .equ    V_PLEN,  32
        .equ    V_NW,    34
        .equ    V_WLEFT, 36
        .equ    V_NB,    38
        .equ    V_EOFF,  40
        .equ    V_ELEN,  42
        .equ    V_SEEN,  44
        .equ    V_PREV,  45
        .equ    V_WDONE, 46
        .equ    V_MOVED, 47
        .equ    V_KILL,  48
sqwrap: .space  NWMAX*4
sqbuf:  .space  NBMAX*8
