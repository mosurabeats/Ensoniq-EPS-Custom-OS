| ONE-SHOT (resident), in two pieces (boot-only homes are small).
| Key-up (0xFFAE12 walks the note's held voices): 0xFFAE54 "tst.b 20(a2)"
| (a2 = the instrument's record: its sustain pedal) decides between
| releasing the voice and holding it (state 4, as with the pedal down).
| A voice whose layer has ONE-SHOT (src/swing/lvl.s marked its wavesample)
| and whose sample doesn't loop (MODE +0xEE = 0 or 1) is held too: it plays
| to its end, where it stops by itself. Looping samples release as usual.
| Out: Z clear = hold, as the stock test. Uses a0 (free there: 0xFFAE46
| sets it again for the next voice).

        .equ    V_WS,       22          | voice: its wavesample record
        .equ    WS_MODE,    0xEE
        .text
        .globl  oneshot
oneshot:
        tst.b   20(a2)                  | the displaced test: pedal down
        bne.s   9f
        movea.l V_WS(a4),a0
        cmpi.b  #1,WS_MODE(a0)
        bhi.s   8f                      | a looping sample: release
        jmp     ONESHOT2.w
8:      cmp.b   d0,d0                   | Z: release
9:      rts
