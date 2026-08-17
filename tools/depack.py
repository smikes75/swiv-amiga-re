#!/usr/bin/env python3
"""Dva dekrunchery ze SWIVFIX.ADF prepsane do Pythonu.

Disketa nepouziva zadny znamy packer (PP20/IMP!/RNC tam nejsou); ma vlastni
dva formaty a obe rozbalovaci rutiny si vozi s sebou. Bootblock je zavede
a spusti - viz docs/FORMAT.md.

  unpack_b()  rutina z 0x30000, 160 B, rozbaluje na 0x40000
  unpack_a()  rutina z 0x70000, 296 B, rozbaluje na 0x60000

Spolecne maji jen to, ze oba ctou proud POZPATKU od konce a zapisuji taky
pozpatku od konce ciloveho bloku, a ze oba maji stejnou 8B hlavicku:

    +0  long  delka rozbalenych dat
    +4  long  delka zabaleneho proudu (od +8)

Format B (Bytekiller):
cte se po longwordech, bity zevnitr od nejnizsiho, cisla se skladaji
nejvyssim bitem napred. Rutina si vede XOR kontrolni soucet vsech
prectenych longwordu a na konci nacte jeste jeden navic, takze spravne
rozbaleny blok konci souctem 0 - to je zdarma dostupna kontrola.

Format A:
cte se po WORDECH, cisla se berou primo ze spodku registru (nejnizsi bit
napred). Nema kontrolni soucet, zato ma bohatsi kodovani: delky zapasu
1/2/4/8 bitu s bazi 1/3/7/23 a offsety 5/9/14 bitu s bazi 0/32/544.
Delka 23 je ukradena jako uniková znacka pro dlouhy beh literalu.
Proud konci dvema poli navic: 4 B pocatecniho registru a 2 B s poctem
platnych bitu v nem.
"""

import sys


class BitReader:
    """Cte bity pozpatku, presne jako getbit na 0x82.

        lsr.l #1,d0      ; C = X = spodni bit, d0 >>= 1
        bne.s  hotovo    ; longword jeste neni vycerpany
        move.l -(a0),d0  ; dobrat dalsi (pozpatku), X zustava
        eor.l  d0,d5     ; kontrolni soucet
        roxr.l #1,d0     ; X -> bit31, novy spodni bit -> C
    """

    def __init__(self, data, end):
        self.data = data
        self.pos = end          # a0, ukazuje ZA konec proudu
        self.checksum = 0       # d5
        self.buf = self._long()  # d0

    def _long(self):
        self.pos -= 4
        if self.pos < 0:
            raise ValueError("proud dosel - poskozena data nebo spatny offset")
        v = int.from_bytes(self.data[self.pos:self.pos + 4], "big")
        self.checksum ^= v
        return v

    def bit(self):
        c = self.buf & 1
        self.buf >>= 1
        if self.buf:
            return c
        # longword vycerpany: c je zarazka, ne data
        new = self._long()
        self.buf = (c << 31) | (new >> 1)
        return new & 1

    def bits(self, n):
        """n bitu, nejvyssi napred (addx.l d2,d2 ve smycce na 0x76)."""
        v = 0
        for _ in range(n):
            v = (v << 1) | self.bit()
        return v


def unpack_b(data, off=0):
    """Rozbali blok na offsetu off. Vraci (data, ok_checksum)."""
    size = int.from_bytes(data[off:off + 4], "big")
    packed = int.from_bytes(data[off + 4:off + 8], "big")
    if size == 0 or size > 8 << 20:
        raise ValueError("nesmyslna delka rozbalenych dat: %d" % size)

    out = bytearray(size)
    br = BitReader(data, off + 8 + packed)
    p = size                                    # a1, zapis pozpatku

    def literals(n):
        nonlocal p
        for _ in range(n):
            p -= 1
            out[p] = br.bits(8)

    def match(length, offset):
        nonlocal p
        s = p + offset
        for _ in range(length):
            s -= 1
            p -= 1
            out[p] = out[s]

    while p > 0:
        if br.bit() == 0:
            if br.bit() == 0:
                literals(br.bits(3) + 1)        # 1..8 literalu
            else:
                match(2, br.bits(8))            # delka 2, offset 8 bitu
        else:
            sel = br.bits(2)
            if sel == 0:
                match(3, br.bits(9))            # delka 3, offset 9 bitu
            elif sel == 1:
                match(4, br.bits(10))           # delka 4, offset 10 bitu
            elif sel == 2:
                n = br.bits(8) + 1              # delka 1..256
                match(n, br.bits(12))           # offset 12 bitu
            else:
                literals(br.bits(8) + 9)        # 9..264 literalu

    br._long()                                  # zaverecny longword (0x9c)
    return bytes(out), br.checksum == 0


class BitReaderA:
    """Cte bity po wordech pozpatku, presne jako rutiny na 0xd2 a 0xea.

    Registr d6 je 32bitovy posuvnik plneny po hornich 16 bitech; d7 pocita,
    kolik bitu ve spodni polovine jeste zbyva.
    """

    M = 0xFFFFFFFF

    def __init__(self, data, end):
        self.data = data
        self.pos = end
        nbits = self._word()            # move.w -(a2),d0
        self.pos -= 4                   # move.l -(a2),d6
        buf = int.from_bytes(self.data[self.pos:self.pos + 4], "big")
        self.buf = buf >> (16 - nbits)  # lsr.l d7,d6  kde d7 = 16-nbits
        self.cnt = nbits                # d7

    def _word(self):
        self.pos -= 2
        if self.pos < 0:
            raise ValueError("proud dosel - poskozena data nebo spatny offset")
        return int.from_bytes(self.data[self.pos:self.pos + 2], "big")

    @staticmethod
    def _swap(v):
        return ((v << 16) | (v >> 16)) & BitReaderA.M

    def bit(self):
        self.cnt -= 1
        if self.cnt:
            c = self.buf & 1
            self.buf >>= 1
            return c
        # spodni pulka dosla: horni sjede dolu a nahoru prijde novy word
        self.cnt = 16
        low = self.buf & 0xFFFF
        self.buf = self._swap(self.buf >> 1)
        self.buf = (self.buf & 0xFFFF0000) | self._word()
        self.buf = self._swap(self.buf)
        return low & 1

    def bits(self, n):
        v = self.buf & ((1 << n) - 1)   # and.w maskou z tabulky na 0x102
        self.buf >>= n
        self.cnt -= n
        if self.cnt <= 0:               # bgt.s = doplnit az kdyz dojdou
            self.cnt += 16
            r = self.cnt
            self.buf = ((self.buf >> r) | (self.buf << (32 - r))) & self.M
            self.buf = (self.buf & 0xFFFF0000) | self._word()
            self.buf = ((self.buf << r) | (self.buf >> (32 - r))) & self.M
        return v


def unpack_a(data, off=0):
    """Rozbali blok formatu A. Vraci (data, True) - format nema soucet."""
    size = int.from_bytes(data[off:off + 4], "big")
    packed = int.from_bytes(data[off + 4:off + 8], "big")
    if size == 0 or size > 8 << 20:
        raise ValueError("nesmyslna delka rozbalenych dat: %d" % size)

    out = bytearray(size)
    br = BitReaderA(data, off + 8 + packed)
    p = size

    def literals(n):
        nonlocal p
        if p - n < 0:
            raise ValueError("beh literalu pretekl zacatek bloku")
        for _ in range(n):
            p -= 1
            out[p] = br.bits(8)

    def match(length, offset):
        nonlocal p
        if p - length < 0:
            raise ValueError("zapas pretekl zacatek bloku")
        s = p + offset
        for _ in range(length):
            s -= 1
            p -= 1
            out[p] = out[s]

    while p > 0:
        if br.bit():
            literals(1)
            continue

        # delka: unarni prefix vybira sirku pole a bazi
        if not br.bit():
            n = 1 + br.bits(1)
        elif not br.bit():
            n = 3 + br.bits(2)
        elif not br.bit():
            n = 7 + br.bits(4)
        else:
            n = 23 + br.bits(8)

        if n == 22:                     # ukradena hodnota = dlouhy beh literalu
            wide = 5 if br.bit() else 14
            literals(15 + br.bits(wide))
            continue
        if n > 22:
            n -= 1

        if not br.bit():
            offset = 32 + br.bits(9)
        elif not br.bit():
            offset = br.bits(5)
        else:
            offset = 544 + br.bits(14)
        match(n + 1, offset)

    return bytes(out), True


def main():
    if len(sys.argv) < 3:
        sys.exit("pouziti: depack.py <vstup> <vystup> [offset] [a|b]")
    off = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0
    data = open(sys.argv[1], "rb").read()
    fmt = sys.argv[4] if len(sys.argv) > 4 else "b"
    out, ok = (unpack_a if fmt == "a" else unpack_b)(data, off)
    open(sys.argv[2], "wb").write(out)
    print("%d B -> %d B (%.1f%%), kontrolni soucet %s"
          % (len(data) - off, len(out), 100.0 * (len(data) - off) / len(out),
             "OK" if ok else "NESEDI"))


if __name__ == "__main__":
    main()
