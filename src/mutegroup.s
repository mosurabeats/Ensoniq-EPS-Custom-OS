| Mute groups, one per instrument (EPS OS 2.49)
|
| Hook: the per-instrument note-on routine at 0xFFACA4 (D5 = instrument 0-7)
| starts with these 8 bytes:
|     FFACA4  3005        move.w  d5,d0
|     FFACA6  D040        add.w   d0,d0
|     FFACA8  327C DF70   movea.w #0xDF70,a1
| The patch replaces them with  "jsr mute_hook" (4EB9 xxxxxxxx) + nop (4E71).
| mute_hook runs the displaced instructions itself before returning.
|
| When an instrument with group G > 0 plays a note, every sounding voice
| (active list 0xFF16E4 and releasing list 0xFF16DC) whose instrument is also
| in group G gets the OS's own fast voice kill (0xFFB7C2, the voice-steal
| path). This includes other keys of the same instrument, so chopped slices
| cut each other off.
|
| Voice record (154 bytes, array at 0xFF0940): +0 next (word ptr),
| +4 key, +6 instrument, +7 layer, +12 state (8 = being killed).
|
| UNTESTED: needs a code cave in resident RAM (see docs/ROADMAP.md).

        .equ    LIST_ACTIVE,  0x16E4    | list sentinels (abs.w -> 0xFF16xx)
        .equ    LIST_RELEASE, 0x16DC
        .equ    V_INST,       6
        .equ    V_STATE,      12
        .equ    ST_KILLING,   8
        .equ    VOICE_KILL,   0xFFB7C2
        .equ    INST_TABLE,   0xDF70

        .text
        .globl  mute_hook
mute_hook:
        movem.l d0-d7/a0-a6,-(sp)
        lea     mute_table(pc),a0
        move.w  d5,d0
        andi.w  #7,d0
        move.b  (a0,d0.w),d1            | d1 = group of the new note
        beq.s   done

        move.w  #LIST_ACTIVE,d3
        bsr.s   choke_list
        move.w  #LIST_RELEASE,d3
        bsr.s   choke_list

done:   movem.l (sp)+,d0-d7/a0-a6
        move.w  d5,d0                   | displaced instructions
        add.w   d0,d0
        movea.w #INST_TABLE,a1
        rts

| d1 = group, d3 = list sentinel address, a0 = mute_table
choke_list:
        movea.w d3,a4
        movea.w (a4),a4                 | first voice
1:      cmpa.w  d3,a4
        beq.s   9f                      | back at sentinel: done
        cmpi.b  #ST_KILLING,V_STATE(a4)
        beq.s   2f
        moveq   #0,d0
        move.b  V_INST(a4),d0
        andi.w  #7,d0
        cmp.b   (a0,d0.w),d1
        bne.s   2f
        movem.l d1/d3/a0/a4,-(sp)
        moveq   #10,d4                  | same rate the voice stealer uses
        jsr     VOICE_KILL
        movem.l (sp)+,d1/d3/a0/a4
2:      movea.w (a4),a4
        bra.s   1b
9:      rts

| Group per instrument 1-8. 0 = no group. v1: set at build time;
| v2: edited from the front panel and saved with the instrument.
        .globl  mute_table
mute_table:
        .byte   0,0,0,0,0,0,0,0
