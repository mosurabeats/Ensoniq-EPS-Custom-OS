| Our parameters on the EPS's own edit pages (EPS OS 2.49)
|
| The edit pages are driven by page records in OS RAM (0xFFC036-0xFFC142):
| first, last and current index entry, page number, and the end of the
| search range (+8). An index entry is a word pointing at an 8-byte
| parameter descriptor (flags/number, type, max, where the value is,
| label). tools/params.py dumps them all; docs/ANALYSIS.md -> Edit pages.
|
| The OS keeps index entry addresses as words (page records, "current",
| word compares), so index tables can only be in the boot ROM or in OS
| RAM, and OS RAM has no room. But the ROM index tables are packed one
| after another: raising a page's "last" by one takes in the next word,
| the first entry of the next table. Our hooks hand back our descriptor
| for that slot when it's reached through this page's record (a5), and
| the ROM's own descriptor otherwise. Descriptors and labels are ours, in
| the code area:
|   0xFF2CA6  current entry -> descriptor (a3)
|   0xFF3214  entry -> descriptor (a2), for walking a page
|   0xFF32F6  "is this descriptor the current entry's?"
|   0xFF3308  label word -> text, shown via 0xFF2400 (ROM 0xC081EC uses a
|             long a2 from 0x8000 up as it is, so the text can be ours).
|             Our label words are 0x7000 + offset in this image (ROM
|             0xC07000-0xC07FFF is kernel code, never a label).
|
| Wavesample page 6 (WS VOLUME, PAN, fades, VOLUME MOD) gets MUTE GROUP
| (0-15) after VOLUME MOD, stored in byte 0x11E of the wavesample record:
| the last header word, 0 in every factory wavesample we have and not
| used by the OS. The record is saved with the instrument as it is in
| memory.

        .equ    RESV,       0x7000      | our label words: RESV + offset
        .equ    ROM_BASE,   0xC00000
        .equ    WS_GROUP,   0x11E       | wavesample record: mute group

        .text
        .globl  desc_hook, desc2_hook, cur_hook, label_hook, page_init

| a3 = entry address. Ours (the slot after this page's ROM table, reached
| through this page's record a5)? Then a3 = our descriptor and Z is set.
| Uses d0 and a0.
ours:   lea     slots(pc),a0
1:      move.w  (a0)+,d0
        beq.s   8f
        cmpa.w  d0,a5                   | the page record
        bne.s   2f
        move.l  a3,d0
        subi.l  #ROM_BASE,d0
        cmp.l   (a0),d0                 | the slot (high word 0)
        bne.s   2f
        move.w  4(a0),d0                | our descriptor
        lea     image(pc),a3
        adda.w  d0,a3
        moveq   #0,d0                   | Z
        rts
2:      addq.l  #6,a0
        bra.s   1b
8:      moveq   #1,d0                   | not ours: Z clear
        rts

| a3 = descriptor word (sign-extended) -> address, as the OS does.
resolve:
        cmpa.l  #0x8000,a3
        bcc.s   9f
        adda.l  #ROM_BASE,a3
9:      rts

| 0xFF2CA6: "movea.w (a3),a3; cmpa.w #0x8000,a3; bcs.s 0xFF2CB8", then rts.
desc_hook:
        movem.l d0/a0,-(sp)
        bsr.s   ours
        beq.s   9f
        movea.w (a3),a3
        bsr.s   resolve
9:      movem.l (sp)+,d0/a0
        rts

| 0xFF3214: "movea.w (a3),a2; jmp 0xC0821A" (the end of a routine).
desc2_hook:
        addq.l  #4,sp
        movem.l d0/a0/a3,-(sp)
        bsr.s   ours
        beq.s   9f
        movea.w (a3),a3
        bsr.s   resolve
9:      movea.l a3,a2
        movem.l (sp)+,d0/a0/a3
        rts

| 0xFF32F6: "jsr 0x2CB0; cmp.w (a3),d0; exg d0,a3" (d0 = a descriptor
| address, a3 = the current entry word): the flags say whether it's the
| current entry's descriptor. Out as the OS: d0 = entry address, a3 = the
| descriptor.
cur_hook:
        jsr     0x2CB0.w                | a3 = entry address
        movem.l d1/a0-a1,-(sp)
        move.l  d0,d1                   | the descriptor to test
        movea.l a3,a1                   | the entry
        bsr.s   ours
        bne.s   1f
        cmpa.l  d1,a3                   | our slot: our descriptor?
        bra.s   2f
1:      cmp.w   (a1),d1                 | the OS's test (low words)
2:      movea.l d1,a3                   | (movea, exg and movem to registers
        exg     a1,d0                   | leave the flags alone)
        movem.l (sp)+,d1/a0-a1
        rts

| 0xFF3308: "movea.w 6(a3),a2; jsr 0x2400" (show the label).
label_hook:
        movea.w 6(a3),a2
        cmpa.w  #RESV,a2
        bcs.s   9f                      | a ROM message
        cmpa.w  #RESV+0x1000,a2         | (0xFFFF8000: OS RAM text is above)
        bcc.s   9f
        suba.w  #RESV,a2
        move.l  a2,-(sp)
        lea     image(pc),a2
        adda.l  (sp)+,a2                | ours: a long address >= 0x8000
9:      jmp     0x2400.w

| At boot (from init): each page with a slot gets "last" (and the end of
| its search range, if that was "last") one entry further.
page_init:
        lea     slots(pc),a0
1:      move.w  (a0)+,d0
        beq.s   9f
        movea.w d0,a1                   | page record
        move.w  2(a1),d1
        cmp.w   8(a1),d1
        bne.s   2f
        addq.w  #2,8(a1)
2:      addq.w  #2,2(a1)                | last
        addq.l  #6,a0
        bra.s   1b
9:      rts

        .balign 2
| page record, the ROM index entry it takes in (ROM offset, long), our
| descriptor (offset in the image)
slots:
        .word   0xC110                  | wavesample page 6
        .long   0x2572
        .word   mute_group_desc-image
        .word   0

mute_group_desc:
        .byte   0x08, 0x00              | parameter 8, type 0: number 0-max
        .word   15                      | max
        .word   WS_GROUP                | in the wavesample record
        .word   RESV+(mute_group_label-image)
mute_group_label:
        .asciz  "MUTE GROUP"
        .balign 2
        .globl  pages_end
pages_end:                              | (mkcodearea.py: must be below 0x1000)
