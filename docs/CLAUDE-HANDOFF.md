# Predani Claudeovi — 2026-09-08

Vetev `codex/audio-motion-handoff` obsahuje kompletni reprodukovatelny
snapshot Codex verze, jeji testy a aktualizovanou dokumentaci.
Vychazi z `39c265e`, nikoli z aktualniho `main`: neslucovat ji naslepo
pres Claudeovu verzi. Aktualni Claudeovy post-game zmeny zde nejsou.

`game.html` je bajtove shodny s verejnym `main:game-codex.html` z commitu
`003f697af18a33b3a3c2f05896890d91cc897641`. Zmeny teto predavaci vetve
neprepisuji `main:game.html` ani Claudeovy testy ci dokumentaci.

## Jak to otevrit bez zasahu do rozpracovane hry

Z vlastniho klonu repozitare:

```sh
git fetch origin
git worktree add --detach ../swiv-codex-review origin/codex/audio-motion-handoff
cd ../swiv-codex-review
```

Do korene teto pracovni kopie dodat vlastni `SWIVFIX.ADF`. Testy jej
ctou lokalne, nikam ho nenahravaji. ADF, ROM ani extrahovana herni data
nejsou soucasti predani. Potreba je Python 3 a Playwright s Chromiem.
Prikazy spoustet z korene teto pracovni kopie (zejmena `uitest.py`).

```sh
python3 tools/soundtest.py
python3 tools/motiontest.py
python3 tools/displaytest.py
python3 tools/uitest.py
python3 tools/integrationtest.py
python3 tools/smoothtest.py 1 2400
```

Posledni test lze opakovat pro zony 1 az 7. Motion test zapisuje diagnosticky
snimek do `/tmp/swiv-motion.png`; ostatni podrobnosti jsou v hlavickach testu.

## Co prevzit a co jeste neni prokazane

- `tools/motiontest.py`: zlomkovy scroll a BOB/HW polohy, recyklace slotu,
  world-space strely, pruhledny HUD a historie pri dohaneni snimku.
- `tools/smoothtest.py`: aktualizovany strukturalni pixelovy oracle se
  samostatnym osetrenim zastaveneho zlomkoveho scrollu SCIFI.
- `tools/soundtest.py`: puvodni periody/hlasitosti pozdejsich efektu,
  IRQ/RNG/priority, zapojeni do hry a stereo PCM; nove tez uplne sekvence
  boss-death a TOKEN, potlaceni aliasu a skutecne TOKEN prehrani offline.
- Boss death: `0x5594` neguje RAM citac pouze pro AUDPER, nikoli AUDVOL.
  Obe poloviny dvojkroku musi drzet kladnou hlasitost 32..1.
- TOKEN: melodie a waveform aritmetika odpovidaji disassemblaci. Novy
  4x prevzorkovany filtr potlacuje aliasy, ale NENI potvrzenou shodou s
  nahravkou originalu. Presna DMA faze a mix vice hlasu zustavaji otevrene.
- `docs/SOUND.md` uvadi konkretni mereni a omezeni;
  `docs/CODEX-HANDOFF.md` popisuje sirsi stav integrace. Jeho zaznam
  o lokalnich necommitnutych zmenach popisuje puvodni pracovni slozku
  v okamziku publikovani; tento snapshot je samostatne verzovane predani.

Pri integraci testu do hlavni vetve pozor na cil: zde testuji `game.html`
Codex verze, zatimco v `main` lezi tato verze v `game-codex.html`.
Testy neprepinat na Claudeovu hru bez vedomeho posouzeni rozdilu kontraktu.
