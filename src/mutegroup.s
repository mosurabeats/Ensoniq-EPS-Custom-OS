| Mute groups, one per instrument (EPS OS 2.49)
|
| Hook: the per-instrument note-on routine at 0xFFACA4 (D5 = instrument 0-7)
| starts with these 8 bytes:
|     FFACA4  3005        move.w  d5,d0
|     FFACA6  D040        add.w   d0,d0
|     FFACA8  327C DF70   movea.w #0xDF70,a1
| The patch replaces them with "jsr mute_hook" (4EB9 xxxxxxxx) + nop (4E71).
| mute_hook runs the displaced instructions itself before returning, so on
| return d0 = 2*d5, a1 = 0xFFDF70 and every other register is unchanged.
|
| When an instrument with group G > 0 plays a note, every voice in the active
| list (0xFF16E4) and the releasing list (0xFF16DC) whose instrument is also
| in group G gets the OS's own fast kill (0xFFB7C2, the voice-steal path).
| That includes other keys of the same instrument, so chopped slices cut each
| other off. Voices already being killed (state 8) are skipped.
|
| The kill rate is d4 (0-99, read by ROM 0xC095D0); 10 is what the OS's own
| voice stealer passes (0xFFAFFC, 0xFFB0F8).
|
| The kill sets state 8 and leaves the voice in its list (the OS frees it
| when the ramp ends), so walking the list across kills is safe. Note-off
| only releases state-4 voices, so a killed voice is never released twice.
|
| Voice record (154 bytes, array at 0xFF0940): +0 next (word ptr),
| +6 instrument, +7 layer, +12 state (4 held, 8 being killed).
|
| Tested in the emulator (tests/test_mutegroup.py); not yet on hardware.

        .equ    LIST_ACTIVE,  0x16E4    | list sentinels (abs.w -> 0xFF16xx)
        .equ    LIST_RELEASE, 0x16DC
        .equ    V_INST,       6
        .equ    V_STATE,      12
        .equ    ST_KILLING,   8
        .equ    VOICE_KILL,   0xB7C2    | abs.w -> 0xFFB7C2
        .equ    INST_TABLE,   0xDF70
        .equ    CHOKE_RATE,   10        | kill ramp rate, same as the OS stealer

        .text
        .globl  mute_hook
mute_hook:
        movem.l d0-d1/d3-d4/d6/a0/a4,-(sp)
        lea     mute_table(pc),a0
        moveq   #7,d0
        and.w   d5,d0
        move.b  (a0,d0.w),d1            | d1 = group of the new note
        beq.s   done
        move.w  #LIST_ACTIVE,d3
        bsr.s   choke_list
        move.w  #LIST_RELEASE,d3
        bsr.s   choke_list
done:   movem.l (sp)+,d0-d1/d3-d4/d6/a0/a4   | d0 too: the displaced
                                        | move.w keeps its upper word
        move.w  d5,d0                   | displaced instructions
        add.w   d0,d0
        movea.w #INST_TABLE,a1
        rts

| Kill every voice of group d1 in the list whose sentinel is at d3.
| In: d1 = group, d3 = sentinel, a0 = mute_table. Uses d0, d4, a1, a4.
| The OS kill changes d4 and a1, and saves d6/a0 only as words (movem.w),
| which sign-extends them on the way out. So d1/d3/a0/a4 are saved around it,
| d4 is reloaded each time, and mute_hook saves the caller's d4 and d6.
choke_list:
        movea.w d3,a4                   | a4 = sentinel
1:      movea.w (a4),a4                 | next voice
        cmpa.w  d3,a4
        beq.s   9f                      | back at the sentinel
        cmpi.b  #ST_KILLING,V_STATE(a4)
        beq.s   1b
        moveq   #7,d0
        and.b   V_INST(a4),d0
        cmp.b   (a0,d0.w),d1
        bne.s   1b
        movem.l d1/d3/a0/a4,-(sp)
        moveq   #CHOKE_RATE,d4
        jsr     VOICE_KILL.w
        movem.l (sp)+,d1/d3/a0/a4
        bra.s   1b
9:      rts

| Group per instrument 1-8. 0 = no group. v1: set at build time;
| v2: edited from the front panel and saved with the instrument.
        .globl  mute_table
mute_table:
        .byte   0,0,0,0,0,0,0,0
