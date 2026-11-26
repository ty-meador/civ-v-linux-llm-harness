# The benchmark's starting saves

A starting save of `docs/BENCHMARK.md` (rule 2) is a save, a seat, a number of turns and a number of seeds. Each one
here is two files: the game's own `.Civ5Save` and a manifest, `<id>.json`, that says what the save holds. Both are
written by `scripts/benchmark_save.py`, which reads the save back from the game after making it.

| id | kind | turn | the seat against | made | baseline |
|---|---|---|---|---|---|
| `board-duel-prince-d` | opening | 0 | the Celts against Austria, Duel, Archipelago | hosted 2026-11-17 | 0.438, standard error 0.071 (twenty seeds, five AI finishes each) |
| `board-duel-prince-d-t100` | middle | 100 | the same game | cut 2026-11-22: the built-in AI played 100 turns on seed 0 | not measured |
| `board-duel-prince-d-t200` | late | 200 | the same game | cut 2026-11-22: the built-in AI played 200 turns on seed 0 | not measured |
| `board-duel-prince-e` | opening | 0 | Siam against the Shoshone, Duel, Pangaea | hosted 2026-11-22 by `--host` | not measured |
| `small-king-venice-a` | opening | 0 | Venice against the Zulus, Russia, Germany, Korea and Morocco, Small, Continents, 12 city-states, King | hosted 2026-11-22 by `--host` | not measured |
| `small-king-germany-a` | opening | 0 | Germany against America, the Huns, Mongolia, the Celts and the Zulus, Small, Continents, 12 city-states, King | hosted 2026-11-22 by hand, described by `--describe` | not measured |
| `small-king-poland-a` | opening | 0 | Poland against America, the Huns, Mongolia, the Celts and the Zulus, Small, Pangaea, 12 city-states, King | hosted 2026-11-23 by `--host` | not measured |
| `duel-king-rome-huns-a` | opening | 0 | Rome against the Huns, Duel, Pangaea, 4 city-states, King, Domination the only victory | hosted 2026-11-23 by `--host` | not measured |
| `scenario-civilwar-union-king` | opening | 0 | the Union against the Confederacy, the American Civil War scenario, King, 50 turns | started 2026-11-25 from the scenario's menu, described by `--describe` | not measured |
| `scenario-civilwar-confederacy-king` | opening | 0 | the Confederacy against the Union, the same scenario | the same | not measured |

Only the first has the built-in AI's study behind it (its share of AI finishes won; `docs/BENCHMARK.md`). A save
with `"baseline": null` in its manifest has none. How a player's runs on these saves are scored is in
`docs/BENCHMARK.md`, "How a player is scored".

## Using them

    scripts/benchmark_save.py --install

copies each save into the folder the game loads from (`Saves/single/`), checks it against the manifest's `sha256`,
and overwrites nothing. `scripts/benchmark_run.py --save <id>` then plays it.

## A manifest

- `id`, `save`, `sha256`: the name the game loads it by, the file, and the file's hash.
- `kind`, `turn`: opening, middle or late, and the game turn the save is on.
- `seat`, `civilization`, `opponents`: the seat a player is given and who else is alive.
- `turns`, `seeds`: the turns a player plays on it and the seeds it is measured on.
- `settings`: what the game reads after a load: the difficulty the game was hosted at, the row the seat is on
  (`HANDICAP_AI_DEFAULT`, the one every AI plays on), speed, world size, map script, the victory types that are on,
  whether Time is among them, the turn limit, the start era, the living city-states.
- `origin`: hosted from the setup screen, or cut from another save (which save, how many turns, which seed, played
  by the built-in AI).
- `game_build`: the game's own version string.
- `baseline`: the built-in AI's share of AI finishes won on it with its standard error over seeds, or null.

The map's random seed is in no manifest: this build's setup screen has no call that reads or sets it. A map kept as
data stands in for it (`map`, below).

## Making one

    scripts/benchmark_save.py --host <id> --civ CIVILIZATION_CELTS --world-size WORLDSIZE_DUEL --map-script pangaea
    scripts/benchmark_save.py --cut <id> --save <an opening> --turns 100 --kind middle
    scripts/benchmark_save.py --describe <id> --kind opening        # a save made by hand

The game is at the main menu, with tunerd running. Each ends with the save and its manifest in this folder.

On a map kept as data (`scripts/benchmark_map.py --read` makes the file from a game on screen):

    scripts/benchmark_save.py --host <id> --civ CIVILIZATION_POLAND --world-size WORLDSIZE_SMALL --map <a map file>

The save is refused unless it holds the file's map plot for plot. The map as the save holds it is kept here as
`<id>.map.json`, and the manifest's `map` names it with its sha256. The first time, the game has to be restarted
once after `scripts/benchmark_map.py --script <a map file>`: it lists a map script only when it found the file
at its own start.

A scenario's save is a game with a mod active: its manifest names the mod (`settings.mods`), the game keeps and
loads it from `ModdedSaves/single`, and `--install` puts it there. `scenario-civilwar.md` is the scenario's
description, victory conditions and special rules in the game's own words (its Dawn of Man text, from the game's
text files); a player of the scenario is given that file and can read it at any time.
