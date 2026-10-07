| ONE-SHOT, second piece (src/swing/oneshot.s): the mark lvl.s left.
        .equ    WS_1SHOT,   0x11F
        .text
        .globl  oneshot2
oneshot2:
        btst    #3,WS_1SHOT(a0)         | Z clear: hold (one-shot)
        rts
