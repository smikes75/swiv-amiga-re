# Pruchod celym levelem (survey)

Recept z 2026-09-03 (docs/TOWN-SURVEY.md):

1. Original, neomezene zivoty, snimek kazdych 8 s po fire:
   `SWIV_BASELINE_UNLIMITED_LIVES=1 tools/baseline.sh "$PWD/build/survey/orig" $(seq 17 8 273)`
2. Radek mapy kazdeho snimku korelaci s renderem mapy (build/maps/0_town.png
   z `tools/map.py`): `python3 tools/survey/rows.py 17,25,...`
   (scroll originalu NENI konstantni, radek se musi merit).
3. Prepis ve stejnych radcich: `python3 tools/survey/survey_remake.py "17:204,25:592,..."`
   (T = 4 * (3249 - radek); bez vstupu, zivoty 100000, vblBase 186,
   RNG prvnich dvou vln podle checkpointu).
4. Dvojice original|prepis: `python3 tools/survey/montage.py 17,25,... build/survey`
5. Objekty ve snimku originalu jako bloby proti mapovemu pozadi:
   `python3 tools/survey/blobs.py <t> <radek>` (cte build/survey/orig_t<t>_crop.png).
