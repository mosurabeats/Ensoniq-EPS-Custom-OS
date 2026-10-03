| Mute groups per key (EPS OS 2.49)
|
| Every key of every instrument has a mute group: 0 = none, 1-15. When a
| note starts on (instrument I, key K) with group G > 0, every sounding voice
| whose own (instrument, key) is also in group G is cut: kick and snare on
| two keys of one kit can cut each other while the hats use another group,
| and groups work across instruments too. A key in a group also cuts itself
| when retriggered (MPC style).
|
| Hook: the per-instrument note-on routine at 0xFFACA4 (D5 = instrument 0-7,
| called once per instrument in the note's instrument mask) starts with:
|     FFACA4  3005        move.w  d5,d0
|     FFACA6  D040        add.w   d0,d0
|     FFACA8  327C DF70   movea.w #0xDF70,a1
| These 8 bytes become "jsr mute_hook" + nop. mute_hook runs the displaced
| instructions itself, so on return d0.w = 2*d5 (upper word as on entry),
| a1 = 0xFFDF70 and every other register is unchanged.
|
| Key: the OS computes it right after the hook site (0xFFACB8): incoming key
| 0xFF16BB plus the instrument's transpose (instrument record +62), as a
| byte, clamped to 21-108 (signed byte compare for the low end). It stores
| it in each voice at +4. We compute the new note's key the same way and
| read +4 for sounding voices, so both sides use the same number: MIDI note
| numbers 21 (A0) to 108 (C8). Instruments with no data (record word 0) are
| skipped, like the OS does.
|
| Cutting uses the OS's own fast kill (0xFFB7C2, the voice-steal path) with
| the stealer's rate (d4 = 10, read by ROM 0xC095D0). The kill sets state 8
| and leaves the voice in its list (the OS frees it when the ramp ends), so
| walking the list across kills is safe; note-off only releases state-4
| voices. Voices already being killed (state 8) are skipped.
|
| Voice record (154 bytes, array at 0xFF0940): +0 next (word ptr), +4 key,
| +5 source, +6 instrument, +7 layer, +12 state (4 held, 8 being killed).
|
| Tested in the emulator (tests/test_mutegroup.py); not yet on hardware.

        .equ    LIST_ACTIVE,  0x16E4    | list sentinels (abs.w -> 0xFF16xx)
        .equ    LIST_RELEASE, 0x16DC
        .equ    IN_KEY,       0x16BB    | incoming key (before transpose)
        .equ    V_KEY,        4
        .equ    V_INST,       6
        .equ    V_STATE,      12
        .equ    ST_KILLING,   8
        .equ    I_TRANSPOSE,  62        | instrument record
        .equ    VOICE_KILL,   0xB7C2    | abs.w -> 0xFFB7C2
        .equ    INST_TABLE,   0xDF70
        .equ    CHOKE_RATE,   10        | kill ramp rate, same as the OS stealer
        .equ    KEY_LO,       21
        .equ    KEY_HI,       108
        .equ    NKEYS,        88

        .text
        .globl  mute_hook
mute_hook:
        movem.l d0-d4/d6/a0/a4,-(sp)
        lea     mute_table(pc),a0
        moveq   #7,d0
        and.w   d5,d0                   | d0 = instrument
        move.w  d0,d1
        add.w   d1,d1
        movea.w #INST_TABLE,a4
        movea.w (a4,d1.w),a4            | instrument record
        tst.w   (a4)
        beq.s   done                    | nothing loaded: the OS skips it too
        moveq   #0,d1
        move.b  IN_KEY.w,d1
        add.b   I_TRANSPOSE(a4),d1      | same key the OS will give the voice
        cmpi.b  #KEY_LO,d1
        bge.s   1f
        moveq   #KEY_LO,d1
        bra.s   2f
1:      cmpi.w  #KEY_HI,d1
        ble.s   2f
        moveq   #KEY_HI,d1
2:      bsr.s   group_of
        move.w  d1,d2                   | d2 = group of the new note
        beq.s   done
        move.w  #LIST_ACTIVE,d3
        bsr.s   choke_list
        move.w  #LIST_RELEASE,d3
        bsr.s   choke_list
done:   movem.l (sp)+,d0-d4/d6/a0/a4    | d0 too: the displaced
                                        | move.w keeps its upper word
        move.w  d5,d0                   | displaced instructions
        add.w   d0,d0
        movea.w #INST_TABLE,a1
        rts

| Kill every voice of group d2 in the list whose sentinel is at d3.
| In: d2 = group, d3 = sentinel, a0 = mute_table. Uses d0, d1, d4, a1, a4.
| The OS kill changes d4 and a1, and saves d6/a0 only as words (movem.w),
| which sign-extends them on the way out. So d2/d3/a0/a4 are saved around
| it, d4 is reloaded each time, and mute_hook saves the caller's d4 and d6.
choke_list:
        movea.w d3,a4                   | a4 = sentinel
1:      movea.w (a4),a4                 | next voice
        cmpa.w  d3,a4
        beq.s   9f                      | back at the sentinel
        cmpi.b  #ST_KILLING,V_STATE(a4)
        beq.s   1b
        moveq   #7,d0
        and.b   V_INST(a4),d0
        moveq   #0,d1
        move.b  V_KEY(a4),d1
        bsr.s   group_of
        cmp.w   d1,d2
        bne.s   1b
        movem.l d2-d3/a0/a4,-(sp)
        moveq   #CHOKE_RATE,d4
        jsr     VOICE_KILL.w
        movem.l (sp)+,d2-d3/a0/a4
        bra.s   1b
9:      rts

| Group of (instrument d0.w 0-7, key d1.w 21-108) -> d1.w (0-15). Uses d0.
| Keys outside 21-108 have no group.
group_of:
        subi.w  #KEY_LO,d1
        cmpi.w  #NKEYS,d1
        bhs.s   8f                      | (unsigned: also catches < 21)
        mulu.w  #NKEYS,d0
        add.w   d1,d0                   | d0 = instrument * 88 + key - 21
        move.w  d0,d1
        lsr.w   #1,d0
        move.b  (a0,d0.w),d0            | two keys per byte
        btst    #0,d1
        bne.s   1f
        lsr.b   #4,d0                   | even index: high nibble
1:      moveq   #15,d1
        and.w   d0,d1
        rts
8:      moveq   #0,d1
        rts

| Group per key, 4 bits each: instrument 0 keys 21-108, then instrument 1 ...
| (even index in the high nibble). Set at build time (tools/mkcodearea.py
| --groups); later: edited from the front panel and saved with the instrument.
        .balign 2
        .globl  mute_table
mute_table:
        .space  8*NKEYS/2
