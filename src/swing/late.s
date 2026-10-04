| Boot stage of the swing build (EPS OS 2.49), staged in a zero run of the
| OS file at the bottom of the init task's stack (0xFFC994), like the
| resident mute build's late init (docs/ANALYSIS.md -> Resident build).
|
| early: the boot sequence's first call (0xFF171E) goes to the ROM's
|   sample-memory sizing through the trampoline at 0xFF832E; it now comes
|   here, sizes, takes RESERVE bytes off the top of the heap for our store
|   (above the 512-byte system block at HEAP_END) and redoes the ROM's
|   bookkeeping, as the code-area loader did.
| late: instead of the boot sequence's last call ("jsr 0x1EF4.w" at
|   0xFF1770): park overlay 0's region bytes in the store (exchange), load
|   overlay 3 (overlay 0 with our image in the region) with the OS's own
|   loader, check it and run its install. If anything is wrong, overlay 0
|   is loaded again and the EPS runs stock. Then on to 0x1EF4.
| A magic long at the end of the staged bytes: if the boot's stack reached
| it, late does nothing.
| Defined by tools/mkswing.py: RESERVE, REGION, LEN, MAGIC_AT.

        .include "common.inc"
        .equ    ROM_SIZING,  0xC08490
        .equ    ROM_REBOUND, 0xC084AC
        .equ    HEAP_SIZE,   0x166A
        .equ    MAGIC,       0x53574721 | "SWG!"
        .equ    WMAGIC,      0x53574731 | "SWG1" at the start of the region

        .text
        .globl  early, late
early:  jsr     ROM_SIZING
        subi.l  #RESERVE,HEAP_SIZE.w
        jmp     ROM_REBOUND

late:   cmpi.l  #MAGIC,MAGIC_AT.w
        bne.s   9f
        bsr.s   swapc                   | the store gets overlay 0's region
        moveq   #3,d1
        jsr     LOADER.w
        bcs.s   8f
        cmpi.l  #WMAGIC,REGION.w
        bne.s   8f
        jsr     REGION+4.w              | install
        bra.s   9f
8:      moveq   #0,d1                   | no good: overlay 0 again, stock
        jsr     LOADER.w
9:      jmp     0x1EF4.w

| swapx (src/swing/swapx.s), for boot: the resident copy isn't there yet.
swapc:  movea.l HEAP_END.w,a0
        lea     512(a0),a0
        movea.w #REGION,a1
        move.w  #LEN-1,d0
1:      move.b  (a1),d1
        move.b  (a0),(a1)+
        move.b  d1,(a0)
        addq.l  #2,a0
        dbra    d0,1b
        rts
        .globl  late_end
late_end:
