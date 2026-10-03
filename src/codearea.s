| Code area: our resident code in the top 1 KB of sample RAM (EPS OS 2.49)
|
| Resident OS RAM is full, so new real-time code (mute groups, record-time
| swing) runs from sample RAM. This file is linked at STAGE (0xFFC994) and
| holds the installer plus the payload that gets copied out. The staged
| bytes are zeros in the stock OS file: task stacks. The OS's task table
| (0xFFBEDC) gives the stack tops:
|     init  0xFFCA84 (its stack: 0xFFC994 up to there)   entry 0xFF171E
|     voice 0xFFCAFC   task 3  0xFFCB74   task 4  0xFFCB94
| and the boot ROM's kernel builds the task records and message buffers
| from 0xFFCB94 up before the OS entry runs. During install only the init
| task runs (the others start when it first yields), so:
|     0xFFC994  install code         read before the stack can reach it
|     STACK_LO  stack reserve        the init stack while installing (the
|     0xFFCA84                       OS entry's jsr, our movem, ROM calls)
|     0xFFCA84  payload, hook table, mute group ranges  (the other tasks'
|     0xFFCB94                       stacks, unused until install is done)
| Found in MAME: with the payload inside the init stack the boot crashed.
| Data with a fixed size (the mute group table) is built in the code area
| at install time rather than staged.
|
| Boot sequence (docs/ANALYSIS.md -> Boot and memory):
|  1. The OS entry (0xFF171E) starts with "jsr 0x832E", a 6-byte trampoline
|     "jmp 0xC08490" to the ROM's sample-memory sizing. Nothing else in the
|     OS has run yet. The patch points that trampoline at install.
|  2. install runs the ROM sizing, takes AREA_SIZE bytes off the heap and
|     re-runs the ROM's own bookkeeping (0xC084AC: end, sizes, heap header,
|     saved copies), so the OS sees a sample heap 1 KB smaller and the 512-
|     byte system block 1 KB lower. The top AREA_SIZE bytes of physical sample
|     RAM are now ours: 0x5FFC00 (base), 0x67FC00 (2x), 0x7FFC00 (4x).
|  3. install copies the payload there, builds the mute group table after
|     it, restores the trampoline, and writes a "jsr" into each hook site
|     whose stock bytes still match.
|  4. It jumps to finish in the copied payload, which zeroes the staged
|     bytes (restoring the stock image; the stack reserve keeps what the
|     stack left there, as it would in a stock boot) and returns to the OS
|     entry.
|
| The payload is position independent (it doesn't know which expander is
| fitted); install writes the absolute jsr targets.

        .equ    AREA_SIZE,    1024
        .equ    ROM_SIZING,   0xC08490  | what the trampoline jumped to
        .equ    ROM_REBOUND,  0xC084AC  | recompute bounds from the size at 0x166A
        .equ    HEAP_SIZE,    0x166A    | abs.w -> 0xFF166A
        .equ    HEAP_END,     0x165A    | system block (512 bytes) starts here
        .equ    TRAMPOLINE,   0x832E    | abs.w -> 0xFF832E
        .equ    STAGE,        0xFFC994  | bottom of the init task's stack
        .equ    STACK_LO,     0xFFCA44  | install code must end here
        .equ    INIT_STACK,   0xFFCA84  | init task's stack top
        .equ    STAGE_TOP,    0xFFCB94  | task records from here up

        .text
        .globl  install
install:
        .globl  install_end, stage_end
        jsr     ROM_SIZING
        subi.l  #AREA_SIZE,HEAP_SIZE.w
        jsr     ROM_REBOUND
        movem.l d0-d5/a0-a2,-(sp)       | keep the ROM's results (d0/d1/a0) for
                                        | the OS, and our caller's other registers
        movea.l HEAP_END.w,a1
        lea     512(a1),a1              | a1 = area: just above the system block
        move.l  a1,d2                   | d2 = area base

        lea     payload(pc),a0          | copy the payload
        move.w  #(payload_end-payload)/2-1,d0
1:      move.w  (a0)+,(a1)+
        dbf     d0,1b

        move.w  #MUTE_TABLE_SIZE/2-1,d0 | a1 = mute_table in the area: clear it
1:      clr.w   (a1)+
        dbf     d0,1b
        suba.w  #MUTE_TABLE_SIZE,a1
        lea     groups(pc),a0           | and set the groups, range by range
5:      move.w  (a0)+,d0                | first index (instrument*88 + key-21)
        bmi.s   8f                      | -1 ends the list
        moveq   #0,d1
        move.b  (a0)+,d1                | keys - 1
        move.b  (a0)+,d4                | group, for odd indexes (low nibble)
        move.b  d4,d5
        lsl.b   #4,d5                   | group, for even indexes (high nibble)
6:      move.w  d0,d3
        lsr.w   #1,d3                   | byte offset; C = odd index
        bcs.s   7f
        or.b    d5,(a1,d3.w)
        bra.s   9f
7:      or.b    d4,(a1,d3.w)
9:      addq.w  #1,d0
        dbf     d1,6b
        bra.s   5b

8:
        movea.w #TRAMPOLINE,a1          | restore "jmp 0xC08490"
        move.w  #0x4EF9,(a1)+
        move.l  #ROM_SIZING,(a1)

        lea     hooks(pc),a0            | hook table: site.l, entry.w, stock 8 bytes
2:      move.l  (a0)+,d0
        beq.s   4f
        movea.l d0,a1
        move.w  (a0)+,d1                | entry offset in the payload
        lea     8(a0),a2                | next entry
        cmpm.l  (a0)+,(a1)+             | site must still hold the stock bytes
        bne.s   3f
        cmpm.l  (a0)+,(a1)+
        bne.s   3f
        subq.l  #8,a1
        move.w  #0x4EB9,(a1)+           | jsr target.l
        ext.l   d1
        add.l   d2,d1
        move.l  d1,(a1)+
        move.w  #0x4E71,(a1)            | nop
3:      movea.l a2,a0
        bra.s   2b

4:      movea.l d2,a0
        jmp     finish-payload(a0)      | continue in sample RAM

install_end:
        .org    INIT_STACK-STAGE        | the stack reserve stays zero

| ---------------------------------------------------------------- payload
        .balign 2
payload:
| Zero the staging bytes (they were zeros in the stock image) and return to
| the OS entry, which called the trampoline, with the registers the ROM
| sizing left (for the smaller heap).
finish:
        movea.l #install,a1             | absolute: this runs from sample RAM
        move.w  #(install_end-install)/2-1,d1
1:      clr.w   (a1)+
        dbf     d1,1b
        movea.l #payload,a1
        move.w  #(stage_end-payload)/2-1,d1
1:      clr.w   (a1)+
        dbf     d1,1b
        movem.l (sp)+,d0-d5/a0-a2
        rts

        .include "mutegroup.s"

        .balign 2
payload_end:                            | = mute_table: the table isn't staged

| Hook table. Each hook replaces 8 bytes with "jsr entry.l; nop" and must run
| the displaced instructions itself.
        .balign 2
hooks:
        .long   0xFFACA4                | note-on for one instrument (D5)
        .word   mute_hook-payload
        .byte   0x30,0x05,0xD0,0x40,0x32,0x7C,0xDF,0x70
        .long   0

| Mute group ranges, set at build time (tools/mkcodearea.py --groups):
| index.w (instrument*88 + key-21), keys-1.b, group.b; index -1 ends.
        .globl  groups
groups:
        .word   -1
        .space  GROUPS_SPACE

        .balign 2
stage_end:
