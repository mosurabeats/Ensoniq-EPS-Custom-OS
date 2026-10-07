| FULL LEVEL and ONE-SHOT per wavesample (EPS OS 2.49)
|
| Two OFF/ON parameters on the 6 Amp page after MUTE GROUP (src/pages.s),
| stored in bytes of the wavesample record that are 0 in every factory
| wavesample and that no OS or ROM code reads (docs/ANALYSIS.md -> Edit
| pages): +0x11F FULL LEVEL, +0x11D ONE-SHOT. With WS=ALL they're set on
| every wavesample of the layer; they save with the instrument.
|
| FULL LEVEL: a new voice plays at velocity 127, whatever the key was hit
| with (the MPC's full level). Hook at 0xFFB252 in the voice start
| (0xFFB246, a3 = the wavesample, a4 = the voice): "move.b 0x16B6,d0;
| move.b d0,8(a4)", the velocity the voice keeps (+8, +9, and the
| velocity tables after it all come from d0). The layer velocity ranges
| are still picked with the velocity played.
|
| ONE-SHOT: key-up doesn't release the voice, so a sample without a loop
| plays to its end, where the voice stops by itself (seen in MAME: a held
| short hat ends on its own). Only for MODE FORWARD-NO LOOP and
| BACKWARD-NO LOOP (+0xEE = 0 or 1): a looping sample would ring forever,
| so it releases as usual. Hook at the key-up's release call (0xFFAE12,
| voice task message 2: walks the held voices of that note): 0xFFAE5A
| "move.w a5,-(sp); move.w (a4),-(sp); jsr 0xFFB136" (0xFFB136 itself
| can't be hooked: 0xFFB13C is a branch target). The all-notes-off path
| (0xFFAEAC, releases at 0xFFAED4/0xFFAF00) is left alone, and so is
| anything else that stops voices.

        .equ    VEL_IN,     0x16B6      | the note's velocity (abs.w)
        .equ    V_WSREC,    22          | voice: its wavesample record
        .equ    WS_FULL,    0x11F
        .equ    WS_ONESHOT, 0x11D
        .equ    WS_MODE,    0xEE        | 0, 1: no loop
        .equ    RELEASE_V,  0xB136      | release a voice (a4)

        .text
        .globl  level_hook, keyup_hook

level_hook:
        move.b  VEL_IN.w,d0             | the displaced instructions, with
        tst.b   WS_FULL(a3)             | 127 for FULL LEVEL
        beq.s   1f
        moveq   #127,d0
1:      move.b  d0,8(a4)
        rts

| Leaves the stack as the displaced pushes do ((a4) on top, then a5),
| under our return address, then releases the voice unless it's a
| one-shot (0xFFB136 returns to our caller).
keyup_hook:
        subq.l  #4,sp
        move.l  4(sp),(sp)              | the return address
        move.w  a5,6(sp)
        move.w  (a4),4(sp)
        movem.l d0/a0,-(sp)
        movea.l V_WSREC(a4),a0
        move.l  a0,d0
        beq.s   1f
        tst.b   WS_ONESHOT(a0)
        beq.s   1f
        cmpi.b  #1,WS_MODE(a0)
        bhi.s   1f                      | a looping sample: release it
        movem.l (sp)+,d0/a0
        rts                             | one-shot: no release
1:      movem.l (sp)+,d0/a0
        jmp     RELEASE_V.w
