| Code area: our resident code in the top 1 KB of sample RAM (EPS OS 2.49)
|
| Resident OS RAM is full, so new real-time code (mute groups, record-time
| swing) runs from sample RAM. This file is linked at STAGE, a run of zeros
| in the OS file (runtime buffers, 0xFFC994...), and holds the installer plus
| the payload that gets copied out.
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
|  3. install copies the payload there, restores the trampoline, and writes
|     a "jsr" into each hook site whose stock bytes still match.
|  4. It jumps to finish in the copied payload, which zeroes the staging
|     bytes (restoring the stock image) and returns to the OS entry.
|
| The payload is position independent (it doesn't know which expander is
| fitted); install writes the absolute jsr targets.

        .equ    AREA_SIZE,    1024
        .equ    ROM_SIZING,   0xC08490  | what the trampoline jumped to
        .equ    ROM_REBOUND,  0xC084AC  | recompute bounds from the size at 0x166A
        .equ    HEAP_SIZE,    0x166A    | abs.w -> 0xFF166A
        .equ    HEAP_END,     0x165A    | system block (512 bytes) starts here
        .equ    TRAMPOLINE,   0x832E    | abs.w -> 0xFF832E

        .text
        .globl  install
install:
        jsr     ROM_SIZING
        subi.l  #AREA_SIZE,HEAP_SIZE.w
        jsr     ROM_REBOUND
        movem.l d0-d2/a0-a2,-(sp)       | keep the ROM's results (d0/d1/a0) for
                                        | the OS, and our caller's d2/a1/a2
        movea.l HEAP_END.w,a1
        lea     512(a1),a1              | a1 = area: just above the system block
        move.l  a1,d2                   | d2 = area base

        lea     payload(pc),a0          | copy the payload
        move.w  #(payload_end-payload)/2-1,d0
1:      move.w  (a0)+,(a1)+
        dbf     d0,1b

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

| Hook table. Each hook replaces 8 bytes with "jsr entry.l; nop" and must run
| the displaced instructions itself.
        .balign 2
hooks:
        .long   0xFFACA4                | note-on for one instrument (D5)
        .word   mute_hook-payload
        .byte   0x30,0x05,0xD0,0x40,0x32,0x7C,0xDF,0x70
        .long   0

| ---------------------------------------------------------------- payload
        .balign 2
payload:
| Zero the staging bytes (they were zeros in the stock image) and return to
| the OS entry, which called the trampoline, with the registers the ROM
| sizing left (for the smaller heap).
finish:
        movea.l #install,a1             | absolute: this runs from sample RAM
        move.w  #(stage_end-install)/2-1,d1
1:      clr.w   (a1)+
        dbf     d1,1b
        movem.l (sp)+,d0-d2/a0-a2
        rts

        .include "mutegroup.s"

        .balign 2
payload_end:
stage_end:
