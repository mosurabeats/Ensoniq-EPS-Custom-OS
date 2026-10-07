| Loader hook (resident): the four calls of the overlay loader (0xFF4E40)
| call this instead; it ends right where the loader starts.
|
| If our code is in the window, the OS wants an overlay: take ours out
| (unpatch, then exchange the region back) so the window holds the overlay
| we displaced (DISP) again. If that's the one asked for, it's loaded:
| return with carry clear (cmp equal) and no disk read. Else go on to the
| loader, which reads the asked one from disk as usual.

        .include "common.inc"
        .text
        .globl  ldr
ldr:    nop                             | (so it starts 4-aligned and ends at the loader)
        tst.b   FLAG.w
        beq.s   9f
        movem.l d0-d1/a0-a1,-(sp)
        jsr     UNPATCH.w               | (window: sets OV_CUR = DISP, FLAG = 0)
        jsr     SWAPX.w
        movem.l (sp)+,d0-d1/a0-a1
        cmp.b   OV_CUR.w,d1
        bne.s   9f
        rts                             | the one asked for: carry clear
9:                                      | (the loader follows)
