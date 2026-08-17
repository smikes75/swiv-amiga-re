| Dekrunčer B — 160 B, bootblock ho zavede na 0x30000 a skočí do něj.
| Rozbaluje na 0x40000 a rts do rozbaleného kódu.
| Formát: Bytekiller. Přepis v tools/depack.py jako unpack_b().
| Adresy jsou offsety uvnitř bloku (za běhu +0x30000).
|
| Registry:
|   a0  čtení zabalených dat, POZPÁTKU po longwordech
|   a1  zápis rozbalených dat, POZPÁTKU po bajtech
|   a2  začátek cílového bloku = spodní mez
|   d0  bitový zásobník
|   d5  kontrolní součet (XOR všech přečtených longwordů)
|   d7  hodnota psaná do NOOP registru (zbytek po blikání okrajem)

                lea     0xa0(pc),a0             | zabalená data
                lea     0x40000,a1              | cíl
                pea     (a1)                    | návratová adresa pro závěrečné rts
                move.w  #0x00f0,d7
                eor.l   d5,d5                   | vynulovat součet
                move.l  a1,a2                   | a2 = spodní mez
                add.l   (a0)+,a1                | a1 = konec cíle   (hlavička +0)
                add.l   (a0)+,a0                | a0 = konec proudu (hlavička +4)
                bsr.s   getlong                 | naplnit zásobník

main:           cmpa.l  a1,a2
                bge.s   done                    | zápis došel na začátek
                bsr.s   getbit
                bcs.s   match                   | 1 -> zápas

                | 0 -> literály, případně krátký zápas
                moveq   #7,d1                   | 8 bitů na bajt
                moveq   #1,d3                   | délka 2 pro krátký zápas
                bsr.s   getbit
                bcs.s   copy                    | 01 -> zápas délky 2, offset 8 bitů
                moveq   #2,d1                   | 00 -> 3 bity počtu
                moveq   #0,d4                   | báze 0
lit:            bsr.s   getbits
                exg     d2,d3                   | d3 = počet-1
                add.w   d4,d3                   | + báze
                moveq   #7,d1
litbyte:        bsr.s   getbit
                addx.w  d2,d2                   | skládat bajt
                dbf     d1,litbyte
                move.b  d2,-(a1)
                dbf     d3,litbyte
                bra     main

litlong:        moveq   #7,d1                   | 8 bitů počtu
                moveq   #8,d4                   | báze 8 -> 9..264 literálů
                bra.s   lit

match:          moveq   #1,d1
                bsr.s   getbits                 | 2 bity třídy
                subq.w  #2,d2
                bmi.s   shortm                  | třída 0,1
                subq.w  #1,d2
                beq.s   litlong                 | třída 3 -> dlouhý běh literálů
                moveq   #7,d1                   | třída 2
                bsr.s   getbits                 | 8 bitů délky
                moveq   #11,d1                  | offset 12 bitů
                bra.s   setup
shortm:         moveq   #10,d1
                add.w   d2,d1                   | 9 nebo 10 bitů offsetu
                addq.w  #4,d2                   | délka-1 = 2 nebo 3
setup:          exg     d2,d3                   | d3 = délka-1, d1 = šířka offsetu
copy:           bsr.s   getbits                 | d2 = offset
                lea     (a1,d2.l),a3            | zdroj je PŘED zápisem (jedeme pozpátku)
copyb:          move.b  -(a3),-(a1)
                dbf     d3,copyb
                bra     main

| d2 = d1+1 bitů, nejvyšší napřed
getbits:        moveq   #0,d2
gbloop:         bsr.s   getbit
                addx.l  d2,d2
                dbf     d1,gbloop
                rts

| C = další bit. Nejvyšší nastavený bit longwordu slouží jako zarážka,
| takže se nemusí počítat, kolik bitů zbývá.
getbit:         move.w  d7,0xdff1fe             | NOOP registr — cracker sem svedl
                eori.w  #0x0f0f,d7              | původní blikání okrajem obrazovky
                lsr.l   #1,d0                   | C = X = spodní bit
                bne.s   gbdone
                bsr.s   getlong                 | vyčerpáno, dobrat (X přežije)
                roxr.l  #1,d0                   | X -> bit31 jako nová zarážka
gbdone:         rts

getlong:        move.l  -(a0),d0
                eor.l   d0,d5                   | kontrolní součet
                rts

done:           bsr.s   getlong                 | závěrečný longword; d5 musí být 0
                rts                             | -> skok na 0x40000 (pea na začátku)
