| d0.l / d3.w -> d0.l, remainder d1.w (d3 > 0). Two divu steps: the high
| word, then the remainder (left in d1's high word) with the low word.
| (CHOP's first hardware test: a swap here lost the remainder, and every
| sample longer than 65535 samples was cut into slices far too short.
| tests/test_divl.py)
        .globl  divl
divl:   move.l  d0,d1
        clr.w   d1
        swap    d1                      | the high word
        divu.w  d3,d1                   | d1 = remainder : quotient
        move.w  d1,-(sp)                | the high word of the result
        move.w  d0,d1                   | remainder : the low word
        divu.w  d3,d1
        moveq   #0,d0
        move.w  (sp)+,d0
        swap    d0
        move.w  d1,d0
        swap    d1                      | the remainder
        rts
