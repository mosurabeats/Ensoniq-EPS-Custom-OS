| Main loop hook (resident), at the top of the UI task's loop (0xFF1774,
| "move.w #320,0x1602.w"). Our code is in the window outside Command mode
| (mode 1: the commands and the sampling pages, which run from the
| overlays) and out of it in Command mode, so commands always find their
| overlay as the stock OS left it:
| * in, but Command mode: out (window: unpatch, then exchange back);
| * out, and not Command mode: exchange in, then patch (window).
| Nothing is live in registers here: the loop sets its trap's parameters
| in memory (0x1602-0x1606) right after.

        .include "common.inc"
        .text
        .globl  ml
ml:     move.w  #320,0x1602.w           | the displaced instruction
        cmpi.w  #MODE_CMD,MODE.w
        sne     d0                      | 0xFF: ours should be in
        cmp.b   FLAG.w,d0
        beq.s   9f                      | as it should be
        tst.b   d0
        beq.s   1f
        jsr     SWAPX.w                 | in
        jmp     PATCH.w
1:      jmp     OUT.w                   | out
9:      rts
