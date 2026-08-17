# SWIV — rozbor amigové diskety

Reverzní analýza hry **S.W.I.V.** (Storm / The Sales Curve, 1991) na Amize:
formát diskety, zaváděcí řetěz a oba vlastní packery, které si hra veze
s sebou. Cílem je dostat se k datům a kódu hry a popsat, jak je postavená.

Stejným postupem stavíme [Captain Beeble](https://github.com/smikes75/captain-beeble-web)
na Atari 8-bit — nejdřív úplný popis originálu, teprve pak cokoli dalšího.

## Disketa v repu není

Hra není public domain, takže se tu distribuují **jen nástroje a popis**.
Vlastní obraz diskety si musíš dodat sám a položit ho do kořene projektu.

Ověřený obraz, se kterým je všechno níže proměřené:

```
SWIVFIX.ADF   901 120 B
SHA-256       13d8beba136d433971379cc5eb6d6d7707e5cb7874c28301ba57583baa41cb5a
```

Jiný obraz může mít jiné offsety — je to crackovaná verze a těch koluje víc.

## Použití

```sh
python3 tools/unboot.py SWIVFIX.ADF      # projde zaváděcí řetěz, vysype do build/
python3 tools/depack.py <in> <out> <off> [a|b]   # jednotlivý blok
```

Na disassembly je potřeba `m68k-elf-binutils` (`brew install m68k-elf-binutils`).

## Co je hotové

| | |
|---|---|
| bootblock rozebraný | ✅ tři čtení přes `DoIO`, lineární offsety |
| ochrana proti kopírování | ✅ **žádná** — v tomhle obrazu už není |
| packer A rozebraný a přepsaný | ✅ 5 328 B → 21 548 B |
| packer B rozebraný a přepsaný | ✅ ověřeno vlastním kontrolním součtem |
| zavaděč hry (`0x50000`) | ⬜ další na řadě |
| katalog a soubory | ⬜ |
| `AMPROG.OBJ` | ⬜ |

Podrobný popis všeho zjištěného je v **[docs/FORMAT.md](docs/FORMAT.md)**,
anotované disassembly obou dekrunčerů v [`src-asm/`](src-asm/).

## Struktura

```
├── tools/
│   ├── unboot.py        projde zaváděcí řetěz a vysype všechny články
│   └── depack.py        oba packery přepsané do Pythonu
├── src-asm/
│   ├── decrunch-a.asm   anotovaná disassembly, 296 B
│   └── decrunch-b.asm   anotovaná disassembly, 160 B
└── docs/
    └── FORMAT.md        formát diskety, zaváděcí řetěz, oba packery
```

## Poznámka k obsahu

Obraz je crack: originál rozlomila skupina *The Company*, opravy pro
68020+/AGA přidal *N.O.M.A.D*. Blok rozbalený na `0x60000` je právě ta
cizí vrstva, **ne kód hry** — při analýze se to nesmí zaměnit.
