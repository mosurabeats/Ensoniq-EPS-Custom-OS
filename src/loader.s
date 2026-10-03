| Code area loader (stage 1), EPS OS 2.49
|
| Resident OS RAM is full, so our resident code runs from the top of sample
| RAM (the code area). The code itself (stage 2, src/codearea.s) is stored
| in the OS file's empty overlay-3 slot: file offset 0x12000, disk blocks
| 159-174 (the OS file always starts at block 15; the OS loads overlay n
| from block 16*(n+7)-1, and nothing ever asks for overlay 3). This loader
| reads it from disk at boot, with the boot ROM's own block read.
|
| The loader is staged in a zero run of the OS file at 0xFFC994: the bottom
| of the init task's stack (its top is 0xFFCA84; the OS task table at
| 0xFFBEDC). Above the init stack the other tasks' stacks and the kernel's
| records start; we don't touch them.
| The OS's stack is only used until the loader switches to its own stack
| (the OS entry's jsr, a1 and two ROM calls, about 20 bytes), so the loader must
| end at STACK_LO, 32 bytes below the init stack's top.
|
| Boot sequence (docs/ANALYSIS.md -> Code area):
|  1. The OS entry (0xFF171E) starts with "jsr 0x832E", a trampoline
|     "jmp 0xC08490" to the ROM's sample-memory sizing. Nothing else in the
|     OS has run yet. The patch points the trampoline at install.
|  2. install runs the ROM sizing, takes AREA_SIZE bytes off the heap and
|     re-runs the ROM's bookkeeping (0xC084AC), so the OS sees a smaller
|     heap. The top AREA_SIZE bytes of physical sample RAM are ours.
|  3. It moves to a stack at the top of the area (so the ROM calls and our
|     register saves don't need the OS's stack), reads STAGE2_BLOCKS blocks
|     from block STAGE2_BLOCK into the area, in supervisor mode with
|     interrupts masked like the boot ROM (see super; drive select 0xC0A5E0: the ROM
|     deselected it after loading the OS; then ROM 0xC0B55C: block in 0x228,
|     destination in 0x22C, error in 0x2C8, five retries, polled I/O, the
|     same routine that loaded the OS), and checks the image (magic word,
|     length, checksum).
|  4. If it's good, it calls the image's init (src/codearea.s), which puts
|     a "jsr" into each hook site whose stock bytes still match. If not: no
|     hooks; the EPS boots as stock with AREA_SIZE bytes less sample memory.
|  5. It restores the trampoline and returns to the OS entry with the ROM
|     sizing's registers. Its own bytes stay behind at the bottom of the
|     init stack, which the OS doesn't expect to be zero.
|
| Built by tools/mkcodearea.py, which defines STAGE2_BLOCK, STAGE2_BLOCKS
| and AREA_SIZE.

        .equ    ROM_SIZING,   0xC08490  | what the trampoline jumped to
        .equ    ROM_REBOUND,  0xC084AC  | recompute bounds from the size at 0x166A
        .equ    ROM_READ,     0xC0B55C  | read one block (boot loader's routine)
        .equ    ROM_SELECT,   0xC0A5E0  | drive select (DUART OP0) + spin-up wait
        .equ    ROM_DESELECT, 0xC0A5F4  | drive deselect
        .equ    RD_BLOCK,     0x228     | ROM disk variables (abs.w)
        .equ    RD_DEST,      0x22C
        .equ    RD_ERROR,     0x2C8
        .equ    HEAP_SIZE,    0x166A    | abs.w -> 0xFF166A
        .equ    HEAP_END,     0x165A    | system block (512 bytes) starts here
        .equ    TRAMPOLINE,   0x832E    | abs.w -> 0xFF832E
        .equ    MAGIC,        0x45505321  | "EPS!" at the start of the image
        .equ    TRAP10,       0x832A    | trap #10 vector target (abs.w)
        .equ    TRAP10_STOCK, 0x4EF895D8  | "jmp 0x95D8.w" there
        .equ    STACK_LO,     0xFFCA64

        .text
        .globl  install, install_end
install:
        jsr     ROM_SIZING
        subi.l  #AREA_SIZE,HEAP_SIZE.w
        jsr     ROM_REBOUND
        move.l  a1,-(sp)                | the caller's a1, on the OS's stack
        movea.l HEAP_END.w,a1
        lea     512+AREA_SIZE(a1),a1    | top of the area
        move.l  sp,-(a1)                | the OS's stack pointer
        movea.l a1,sp                   | our stack: the top of the area
        movem.l d0-d7/a0-a6,-(sp)       | d0/d1/a0 = the ROM's results
        movea.l HEAP_END.w,a3
        lea     512(a3),a3              | a3 = area base

        move.l  #0x4EF80000+(super-0xFF0000),TRAP10.w  | "jmp super.w"
        trap    #10                     | read in supervisor mode (super)
        move.l  #TRAP10_STOCK,TRAP10.w
        tst.b   RD_ERROR.w
        bne.s   done                    | disk error: boot without our code

        cmpi.l  #MAGIC,(a3)             | check the image
        bne.s   done
        move.w  4(a3),d1                | length in bytes (even)
        cmpi.w  #STAGE2_BLOCKS*512,d1
        bhi.s   done
        lsr.w   #1,d1
        subq.w  #1,d1
        moveq   #0,d0
        movea.l a3,a0
2:      add.w   (a0)+,d0                | all words sum to 0
        dbf     d1,2b
        tst.w   d0
        bne.s   done
        movea.l a3,a0
        adda.w  6(a3),a0
        jsr     (a0)                    | the image's init (a3 = area): hooks

done:   movea.w #TRAMPOLINE,a1          | restore "jmp 0xC08490"
        move.w  #0x4EF9,(a1)+
        move.l  #ROM_SIZING,(a1)
        movem.l (sp)+,d0-d7/a0-a6
        movea.l (sp),sp                 | back on the OS's stack
        movea.l (sp)+,a1
        rts

| Trap #10's vector points at 0xFF832A in OS RAM; the loader puts a jump to
| here in it for one call. Supervisor mode lets us mask interrupts like the
| boot ROM does while it loads the OS: with them on, the polled reads lose
| bytes (seen in MAME: error 4 on the first block).
super:  ori.w   #0x0700,sr
        jsr     ROM_SELECT              | the ROM deselected the drive after boot
        move.l  a3,RD_DEST.w            | read stage 2 into the area
        move.l  #STAGE2_BLOCK,RD_BLOCK.w
        moveq   #STAGE2_BLOCKS-1,d7
1:      jsr     ROM_READ
        tst.b   RD_ERROR.w
        bne.s   2f
        addi.l  #512,RD_DEST.w
        addq.l  #1,RD_BLOCK.w
        dbf     d7,1b
2:      jsr     ROM_DESELECT            | as the ROM left it
        rte

        .balign 2
install_end:
