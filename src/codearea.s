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
9:      rts

| Hook table: site.l, entry offset.w, the site's 8 stock bytes; ends with
| a 0 long. Each hook must run the displaced instructions itself.

        .balign 2
hooks:
        .long   0xFFACA4                | note-on for one instrument (D5)
        .word   mute_hook-image
        .byte   0x30,0x05,0xD0,0x40,0x32,0x7C,0xDF,0x70
        .long   0

        .include "mutegroup.s"
        .space  MUTE_TABLE_SIZE         | set at build time (--groups)

        .balign 2
        .globl  image_end
image_end:
