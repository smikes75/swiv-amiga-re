| Dekrunčer A — 296 B, bootblock ho zavede na 0x70000 a zavolá (jsr).
| Rozbaluje na 0x60000 a skočí tam. Náklad je vrstva cracku N.O.M.A.D
| (záplaty pro 68020+/AGA + textové intro), ne kód hry.
| Přepis v tools/depack.py jako unpack_a().
|
| Registry:
|   a1  zápis rozbalených dat, POZPÁTKU po bajtech
|   a2  čtení zabalených dat, POZPÁTKU po WORDECH
|   a5  začátek cílového bloku = spodní mez
|   d6  32bitový posuvník bitů (plní se po horních 16)
|   d7  kolik bitů ve spodní polovině ještě zbývá
|   d3  konstanta 16

                movem.l d1-a7,-(sp)
                lea     0x128(pc),a2            | zabalená data
                lea     0x60000,a1              | cíl
                move.l  (a2)+,d1                | délka rozbalených
                move.l  (a2)+,d2                | délka zabaleného proudu

                | Pokud by si výstup přepsal vlastní vstup, přesunout
                | zabalená data na začátek cílové oblasti.
                lea     (a2),a3
                cmpa.l  a1,a3
                ble.s   noreloc
                move.l  a1,a3
                add.l   d1,a3                   | konec cíle
                cmpa.l  a2,a3
                ble.s   noreloc
                move.l  a2,a3
                lea     (a1),a4
                move.l  d2,d7
                lsr.l   #2,d7
                addq.l  #1,d7
                move.l  a4,a2
reloc:          move.l  (a3)+,(a4)+
                subq.l  #1,d7
                bne.s   reloc

noreloc:        move.l  a1,a5                   | spodní mez
                add.l   d1,a1                   | konec cíle
                add.l   d2,a2                   | konec proudu
                move.w  -(a2),d0                | kolik bitů je platných
                move.l  -(a2),d6                | počáteční obsah posuvníku
                moveq   #16,d7
                sub.w   d0,d7
                lsr.l   d7,d6                   | zarovnat platné bity dolů
                move.w  d0,d7
                moveq   #16,d3
                moveq   #0,d4

main:           cmpa.l  a5,a1
                ble     done
                bsr.s   getbit
                bcc.s   match                   | 0 -> zápas
                moveq   #0,d4                   | 1 -> jeden literál
lit:            moveq   #8,d1
                bsr     getbits
                move.b  d0,-(a1)
                dbf     d4,lit
                bra.s   main

| Únik z délky 22: dlouhý běh literálů, 15..46 nebo 15..16398
litlong:        moveq   #14,d4
                moveq   #5,d1
                bsr.s   getbit
                bcs.s   litl2
                moveq   #14,d1
litl2:          bsr     getbits
                add.w   d0,d4
                bra.s   lit

| Délka: unární prefix vybírá šířku pole i bázi
match:          bsr.s   getbit
                bcs.s   m2
                moveq   #1,d1
                moveq   #1,d4                   | 0    -> 1 bit,  délka 2..3
                bra.s   mlen
m2:             bsr.s   getbit
                bcs.s   m3
                moveq   #2,d1
                moveq   #3,d4                   | 10   -> 2 bity, délka 4..7
                bra.s   mlen
m3:             bsr.s   getbit
                bcs.s   m4
                moveq   #4,d1
                moveq   #7,d4                   | 110  -> 4 bity, délka 8..22
                bra.s   mlen
m4:             moveq   #8,d1
                moveq   #23,d4                  | 111  -> 8 bitů, délka 23..278
mlen:           bsr     getbits
                add.w   d0,d4
                cmpi.w  #22,d4
                beq.s   litlong                 | 22 je ukradená jako značka
                blt.s   moff
                subq.w  #1,d4                   | nad dírou zase o krok dolů

| Offset: taky unární prefix
moff:           bsr.s   getbit
                bcs.s   mo2
                moveq   #9,d1
                moveq   #32,d2                  | 0  -> 9 bitů,  32..543
                bra.s   mocopy
mo2:            bsr.s   getbit
                bcs.s   mo3
                moveq   #5,d1
                moveq   #0,d2                   | 10 -> 5 bitů,   0..31
                bra.s   mocopy
mo3:            moveq   #14,d1
                move.w  #544,d2                 | 11 -> 14 bitů, 544..16927
mocopy:         bsr.s   getbits
                add.w   d2,d0
                lea     (a1,d0.w),a3
mcopy:          move.b  -(a3),-(a1)
                dbf     d4,mcopy
                bra     main

| C = další bit. Spodních 16 bitů d6 je zásoba, d7 je počítadlo;
| když dojde, horní půlka sjede dolů a nahoru přijde nový word.
getbit:         subq.w  #1,d7
                bne.s   gbfast
                moveq   #16,d7
                move.w  d6,d0
                lsr.l   #1,d6
                swap    d6
                move.w  -(a2),d6
                swap    d6
                lsr.w   #1,d0
                rts
gbfast:         lsr.l   #1,d6
                rts

| d0 = d1 bitů ze spodku posuvníku (nejnižší napřed)
getbits:        move.w  d6,d0
                lsr.l   d1,d6
                sub.w   d1,d7
                bgt.s   gbsok
                add.w   d3,d7                   | došlo -> vsunout nový word
                ror.l   d7,d6
                move.w  -(a2),d6
                rol.l   d7,d6
gbsok:          add.w   d1,d1
                and.w   masks-2(pc,d1.w),d0
                rts

masks:          dc.w    0x0001,0x0003,0x0007,0x000f,0x001f,0x003f,0x007f
                dc.w    0x00ff,0x01ff,0x03ff,0x07ff,0x0fff,0x1fff,0x3fff

done:           movem.l (sp)+,d0-a6
                jmp     0x60000
