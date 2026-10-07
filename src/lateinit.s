| Late init for the resident build (EPS OS 2.49, src/resmute.s)
|
| The OS file's boot sequence ends at 0xFF1770 with "jsr 0x1EF4.w"; the main
| loop starts at 0xFF1774. That jsr becomes "jsr 0xC994.w", this code. It
| copies our chunks into boot-only OS RAM that is dead by now, then goes on
| to 0x1EF4, which returns to the main loop.
|
| The chunks travel in the OS file in two zero runs that nothing writes
| before 0xFF1770 (measured in MAME with boot ROM 2.40, every write from the
| OS entry on; docs/ANALYSIS.md -> Resident build):
|   carrier 1: 0xFFC994 up, the bottom of the init task's stack (its top is
|              0xFFCA84; the boot reaches down to 0xFFCA3E). This code and
|              table 1 (the mute code, then the hook and the page record).
|   carrier 2: 0xFFC8E8 up, the bottom of the supervisor stack (top
|              0xFFC960; interrupts reach down to 0xFFC92C). Table 2 (the
|              index table, descriptor and label).
| Each carrier ends with a magic long. If either is gone (a stack went
| deeper than measured), nothing is copied and the OS runs stock.
| Table 2 is copied first, so the hook and the page record (the end of
| table 1) only go in once everything they point at is there.
|
| Chunk: destination (word, abs.w: 0xFFxxxx), length - 1 (word), the bytes
| (an even number). A destination of 0 ends the table.
|
| d0, a0 and a1 are free here: 0x1EF4 and the main loop set them before
| reading them (the jsr is reached from two paths with different values).
|
| Defined by tools/mkresident.py: TABLE2, MAGIC, MAGIC1_AT, MAGIC2_AT.

        .text
        .globl  late
late:   cmpi.l  #MAGIC,MAGIC1_AT.w
        bne.s   9f
        cmpi.l  #MAGIC,MAGIC2_AT.w
        bne.s   9f
        lea     TABLE2.w,a0
        bsr.s   copy
        lea     table1(pc),a0
        bsr.s   copy
9:      jmp     0x1EF4.w                | the call we took the place of

copy:   move.w  (a0)+,d0
        beq.s   8f
        movea.w d0,a1
        move.w  (a0)+,d0
1:      move.b  (a0)+,(a1)+
        dbra    d0,1b
        bra.s   copy
8:      rts

        .globl  table1
table1:                                 | (tools/mkresident.py appends it)
