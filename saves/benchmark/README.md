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

Only the first has been measured. Rule 2 keeps a starting save only if the baseline wins between 0.2 and 0.8 of its
games on it; a save with `"baseline": null` in its manifest has not been through that and no player's number on it
means anything yet.

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

The map's random seed is in no manifest: this build's setup screen has no call that reads or sets it.

## Making one

    scripts/benchmark_save.py --host <id> --civ CIVILIZATION_CELTS --world-size WORLDSIZE_DUEL --map-script pangaea
    scripts/benchmark_save.py --cut <id> --save <an opening> --turns 100 --kind middle
    scripts/benchmark_save.py --describe <id> --kind opening        # a save made by hand

The game is at the main menu, with tunerd running. Each ends with the save and its manifest in this folder.
