| Exchange the window region with our store in sample RAM (resident).
|
| The store is the RESERVE bytes the early hook took off the top of the
| sample heap (HEAP_END + 512 up), one byte per word in the high byte:
| sample RAM is 13 bits wide (D15-D3), so a byte in bits 15-8 is safe.
| One exchange swaps our code in and parks what was there; the next one
| puts it back. Uses d0, d1, a0, a1. REGION and LEN from tools/mkswing.py.

        .include "common.inc"
        .text
        .globl  swapx
swapx:  movea.l HEAP_END.w,a0
        lea     512(a0),a0
        movea.w #REGION,a1
        move.w  #LEN-1,d0
1:      move.b  (a1),d1
        move.b  (a0),(a1)+
        move.b  d1,(a0)
        addq.l  #2,a0
        dbra    d0,1b
        rts
