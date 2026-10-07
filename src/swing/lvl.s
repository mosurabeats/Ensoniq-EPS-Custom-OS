| HIT = FULL LEVEL / ONE-SHOT (resident), at the voice start, 0xFFB252
| "move.b 0x16B6.w,d0" (the note's velocity; 0xFFB256 stores it in the
| voice). The layer's HIT (layer record +0x2E, the Layer page; the key map
| slot of key 20, which no note reads, a high byte): bit 0 FULL LEVEL, the
| voice gets velocity 127; bit 1 ONE-SHOT, marked in the voice's wavesample
| (+0x11F bit 3: a low byte, but bit 3 survives the 13-bit sample RAM) for
| the key-up (src/swing/oneshot.s). a6 = the layer, a3 = the wavesample
| record on both paths to 0xFFB246 (0xFFB038, 0xFFB122). The layer was
| picked with the velocity played.

        .equ    VEL_IN,     0x16B6
        .equ    L_HIT,      0x2E        | layer record: HIT (high byte)
        .equ    WS_1SHOT,   0x11F       | wavesample record: bit 3
        .text
        .globl  lvl
lvl:    move.b  VEL_IN.w,d0             | the displaced instruction
        btst    #0,L_HIT(a6)
        beq.s   1f
        moveq   #127,d0                 | FULL LEVEL
1:      btst    #1,L_HIT(a6)
        sne     WS_1SHOT(a3)            | ONE-SHOT: 0xFF (0xF8 on the EPS)
        rts
