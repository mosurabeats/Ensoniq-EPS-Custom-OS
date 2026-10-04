| Mute groups, resident in OS RAM (EPS OS 2.49): the hardware-safe build
|
| Sample RAM is 13 bits wide on the EPS (docs/ANALYSIS.md -> Sample RAM),
| so no code can run from it. This build keeps everything in OS RAM, in
| boot-only code that is dead once the OS reaches its main loop:
|   0xFF1720  this code (the boot sequence's jsr list, 0xFF171E-0xFF176F)
|   0xFF86E6  the 6 Amp page's index table, ROM entries + ours (src/pages.s)
|   0xFF874C  our MUTE GROUP descriptor and label
| src/lateinit.s copies them there at the end of boot, then sets the page
| record (0xFFC110) and the hook below. tools/mkresident.py builds it.
|
| MUTE GROUP (0-15, the 6 Amp page, after VOLUME MOD) is byte 0x11E of the
| wavesample record, the high byte of a word, so it survives the 13-bit
| sample RAM. It saves with the instrument.
|
| Hook: 0xFFAF92 in the layer's voice start (0xFFAF54), once the layer's
| wavesample is known (a3 = its record, d5 = instrument, d6 = layer) and
| before the OS looks for a voice to retrigger:
|     FFAF92  3038 16BE   move.w  0x16BE,d0     (the key)
| becomes "jsr 0x1720.w". If the new wavesample has a group, every sounding
| voice whose wavesample has the same group is cut with the OS's fast kill
| (0xFFB7C2, d4 = 10, as the voice stealer), except voices of the same key
| and instrument: the note's other layers, and the OS's own retrigger of a
| held key. Voices already being killed (state 8) are skipped.
|
| Registers: d2, d4, a0, a1 and a4 are set again by the OS after the hook
| (0xFFAF9A on). d0 is loaded first, as the displaced instruction does, and
| is also our key to compare. The kill keeps d0, d2, d5 and a4 (the OS's
| own loop here relies on that); it changes d4 and a1 and restores a0 as a
| word.

        .equ    NEW_KEY,      0x16BE    | word: the note's key (low byte)
        .equ    LIST_ACTIVE,  0x16E4    | voice list sentinels
        .equ    LIST_RELEASE, 0x16DC
        .equ    V_KEY,        4
        .equ    V_INST,       6
        .equ    V_STATE,      12
        .equ    V_WS,         22        | voice: its wavesample record
        .equ    ST_KILLING,   8
        .equ    WS_GROUP,     0x11E
        .equ    VOICE_KILL,   0xB7C2
| CHOKE_RATE: the kill's fade, an envelope time (ROM rate table 0xC05232:
| a linear ramp of 32767 / table[time] ticks of 12 ms). Set by
| tools/mkresident.py --choke.

        .text
        .globl  mute
mute:   move.w  NEW_KEY.w,d0            | the displaced instruction; our key
        move.b  WS_GROUP(a3),d2         | the new note's group
        beq.s   9f
        movea.w #LIST_ACTIVE,a0
        bsr.s   cut
        movea.w #LIST_RELEASE,a0        | (falls into cut)

| Cut the voices of group d2 in the list whose sentinel is a0.
cut:    movea.w a0,a4
1:      movea.w (a4),a4                 | next voice
        cmpa.w  a0,a4
        beq.s   9f                      | back at the sentinel
        cmpi.b  #ST_KILLING,V_STATE(a4)
        beq.s   1b
        movea.l V_WS(a4),a1
        cmp.b   WS_GROUP(a1),d2
        bne.s   1b
        cmp.b   V_KEY(a4),d0
        bne.s   2f
        cmp.b   V_INST(a4),d5
        beq.s   1b                      | same key and instrument
2:      moveq   #CHOKE_RATE,d4
        jsr     VOICE_KILL.w
        bra.s   1b
9:      rts
        .globl  mute_end
mute_end:
