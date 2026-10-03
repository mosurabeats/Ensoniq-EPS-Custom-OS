| Code area image (stage 2), EPS OS 2.49
|
| Our resident code. It's stored in the OS file's overlay-3 slot (file
| offset 0x12000, blocks 159-174) and src/loader.s reads it into the top
| of sample RAM at boot (docs/ANALYSIS.md -> Code area). It runs wherever
| the area is (base, 2x or 4x expander), so everything here is position
| independent; the loader writes the absolute jsr's.
|
| Header (checked by the loader before it calls init):
|   +0  "EPS!"
|   +4  length of the image in bytes (even)
|   +6  offset of init
|   +8  checksum: tools/mkcodearea.py sets it so all words sum to 0

        .text
        .globl  image
image:
        .long   0x45505321              | "EPS!"
        .word   image_end-image
        .word   init-image
        .globl  checksum
checksum:
        .word   0

| Called once by the loader at boot, user mode, a3 = this image. Puts
| "jsr entry.l; nop" into each hook site whose 8 stock bytes still match
| (a site that differs, say from another patch, is left alone). Uses
| d0, d1, a0-a2 (the loader saves everything).
init:   lea     hooks(pc),a0
1:      move.l  (a0)+,d0
        beq.s   9f
        movea.l d0,a1
        move.w  (a0)+,d1                | entry offset in the image
        lea     8(a0),a2                | next entry
        cmpm.l  (a0)+,(a1)+
        bne.s   2f
        cmpm.l  (a0)+,(a1)+
        bne.s   2f
        subq.l  #8,a1
        move.w  #0x4EB9,(a1)+           | jsr entry.l
        ext.l   d1
        add.l   a3,d1
        move.l  d1,(a1)+
        move.w  #0x4E71,(a1)            | nop
2:      movea.l a2,a0
        bra.s   1b
9:
.if PAGES
        bsr     page_init
.endif
        rts

| Hook table: site.l, entry offset.w, the site's 8 stock bytes; ends with
| a 0 long. Each hook must run the displaced instructions itself.

        .balign 2
hooks:
        .long   0xFFACA4                | note-on for one instrument (D5)
        .word   mute_hook-image
        .byte   0x30,0x05,0xD0,0x40,0x32,0x7C,0xDF,0x70
.if LOOPREC
        .long   0xFF6742                | LOOPED wrap: jsr 0x6B12; jsr 0x6AD6
        .word   wrap_hook-image
        .byte   0x4E,0xB8,0x6B,0x12,0x4E,0xB8,0x6A,0xD6
        .long   0xFF6B7C                | commit: jsr 0x74F2; tst.b 0x815E
        .word   stop_hook-image
        .byte   0x4E,0xB8,0x74,0xF2,0x4A,0x38,0x81,0x5E
        .long   0xFF6E56                | append: lea 8(a4),a0; ori.w #$8000,(a0)
        .word   append_hook-image
        .byte   0x41,0xEC,0x00,0x08,0x00,0x50,0x80,0x00
        .long   0xFF638A                | note playback: moveq #0,d1; move.b 3(fp),d1; move.l d1,d0
        .word   play_hook-image
        .byte   0x72,0x00,0x12,0x2E,0x00,0x03,0x20,0x01
        .long   0xFF7AD4                | RECORD: cmpi.b #1,6(a5); bne.s 0xFF7B18
        .word   rec_hook-image
        .byte   0x0C,0x2D,0x00,0x01,0x00,0x06,0x66,0x3C
.endif
.if PAGES
        .long   0xFF2CA6                | current entry's descriptor -> a3
        .word   desc_hook-image
        .byte   0x36,0x53,0xB6,0xFC,0x80,0x00,0x65,0x0A
        .long   0xFF3214                | descriptor -> a2
        .word   desc2_hook-image
        .byte   0x34,0x53,0x4E,0xF9,0x00,0xC0,0x82,0x1A
        .long   0xFF32F6                | is it the current entry's descriptor?
        .word   cur_hook-image
        .byte   0x4E,0xB8,0x2C,0xB0,0xB0,0x53,0xC1,0x8B
        .long   0xFF3308                | show a parameter's label
        .word   label_hook-image
        .byte   0x34,0x6B,0x00,0x06,0x4E,0xB8,0x24,0x00
.endif
        .long   0

.if PAGES
        .include "pages.s"              | first: its tables need small offsets
.endif
        .include "mutegroup.s"
        .space  MUTE_TABLE_SIZE         | set at build time (--groups)
.if LOOPREC
        .include "looprec.s"
.endif

        .balign 2
        .globl  image_end
image_end:
