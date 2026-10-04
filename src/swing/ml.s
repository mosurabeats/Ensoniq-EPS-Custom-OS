| Main loop hook (resident), at the top of the UI task's loop (0xFF1774,
| "move.w #320,0x1602.w"): whenever our code is out of the window and the
| EPS isn't in Command mode (whose commands and the sampling pages run from
| the overlays), put it back in: exchange the region, then patch (window).

        .include "common.inc"
        .text
        .globl  ml
ml:     move.w  #320,0x1602.w           | the displaced instruction
        tst.b   FLAG.w
        bne.s   9f
        cmpi.w  #MODE_CMD,MODE.w
        beq.s   9f
        movem.l d0-d1/a0-a1,-(sp)
        jsr     SWAPX.w
        jsr     PATCH.w                 | (window, ours now)
        movem.l (sp)+,d0-d1/a0-a1
9:      rts
