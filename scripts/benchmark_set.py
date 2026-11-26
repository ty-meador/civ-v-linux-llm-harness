#!/usr/bin/env python3
"""The benchmarks: what a run can be a run of (docs/BENCHMARK.md, "The classes of benchmark, and what a run is told").

A starting save is a game. A benchmark is a starting save and what is asked of the player on it, and one save can
carry several: the four victory types and the open game are all played on `small-king-poland-b`. The list is
`saves/benchmark/benchmarks.json`; `scripts/benchmark_run.py --benchmark ID` plays one, and the run's row, its
game file and its recording then name the benchmark.

    scripts/benchmark_set.py              the list, a line a benchmark
    scripts/benchmark_set.py --check      every benchmark's starting save, briefing and texts are in saves/benchmark

A benchmark of the list:

    id          its name in a row, a recording and a report: the starting save's id, with what is asked after it
                when the save carries more than one benchmark
    class       open, survival, victory or scenario: what is asked and how a run is ranked
    save        the starting save's id
    turns       the turns a run is given: a game that is not over when they are played is stopped there. A
                scenario's own turn limit; 700 for a game with no last turn of its own (the user, 2026-11-26: with
                no Time victory a game nobody wins would never end, and the stop is far enough out to end none
                that somebody can)
    briefing    the file a run's first instance is told once, how a run is ranked and what is asked (not for a
                scenario, whose own texts say it and stay readable)
    victory     class victory: the victory type asked, under the game's name
    won_by      class scenario: goal (the scenario is won or not) or points (its points when it ends)
    victories   class scenario, won by a goal: the victory types the game names the seat's win by when the goal
                is reached. A scenario's own code names the winner, each scenario under a type of its choosing,
                and the game names a winner by Time when a scenario's turns run out, which is no win of it
    texts       class scenario: the scenario's description, victory conditions and special rules in the game's
                own words, a file the player can read at any time

Paths are relative to `saves/benchmark/`. No game and no network are needed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

KEPT = Path(__file__).resolve().parent.parent / "saves" / "benchmark"
LIST = KEPT / "benchmarks.json"
FORMAT = 1
CLASSES = ("open", "survival", "victory", "scenario")
VICTORY_TYPES = ("VICTORY_DOMINATION", "VICTORY_SPACE_RACE", "VICTORY_CULTURAL", "VICTORY_DIPLOMATIC")
WON_BY = ("goal", "points")
KEYS = {"id", "class", "save", "turns", "briefing", "victory", "won_by", "victories", "texts"}


class Refused(Exception):
    """The list cannot be read as one, or names no such benchmark."""


def is_name(x) -> bool:
    """A name that can stand in a file's name: letters, digits and hyphens."""
    return isinstance(x, str) and bool(x) and all(c.isalnum() or c == "-" for c in x)


def is_file_name(x) -> bool:
    return isinstance(x, str) and bool(x) and not Path(x).is_absolute() and ".." not in Path(x).parts


def faults_of(entry) -> list[str]:
    """What keeps an entry from being a benchmark; empty when it is one."""
    if not isinstance(entry, dict):
        return ["not an object"]
    faults = [f"unknown key {key}" for key in sorted(set(entry) - KEYS)]
    faults += [f"{key} is not a name of letters, digits and hyphens" for key in ("id", "save") if not is_name(entry.get(key))]
    faults += [f"{key} is not a file under saves/benchmark" for key in ("briefing", "texts")
               if key in entry and not is_file_name(entry[key])]
    turns = entry.get("turns")
    if not isinstance(turns, int) or isinstance(turns, bool) or turns < 1:
        faults.append("turns is not the number of turns a run is given")
    kind = entry.get("class")
    if kind not in CLASSES:
        return faults + [f"class is none of {', '.join(CLASSES)}"]
    if kind == "victory" and entry.get("victory") not in VICTORY_TYPES:
        faults.append(f"a victory benchmark asks for one of {', '.join(VICTORY_TYPES)}")
    if kind == "scenario":
        faults += scenario_faults(entry)
    elif "briefing" not in entry:
        faults.append("no briefing: the player is told nothing of what is asked")
    return faults


def scenario_faults(entry: dict) -> list[str]:
    faults = [] if "texts" in entry else ["no texts: a scenario's player is given the game's own"]
    if entry.get("won_by") not in WON_BY:
        return faults + [f"won_by is none of {', '.join(WON_BY)}"]
    if entry["won_by"] == "goal":
        named = entry.get("victories")
        if not isinstance(named, list) or not named or not all(isinstance(v, str) and v.startswith("VICTORY_") for v in named):
            faults.append("a scenario won by a goal needs the victory types the game names its win by")
    return faults


def read(path: Path = LIST) -> dict[str, dict]:
    """The benchmarks by id, in the list's order. Refused whole when any entry is not a benchmark."""
    try:
        data = json.loads(Path(path).read_text())
    except OSError as e:
        raise Refused(f"{path}: cannot be read ({e})") from None
    except ValueError as e:
        raise Refused(f"{path}: not JSON ({e})") from None
    if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("benchmarks"), list):
        raise Refused(f"{path}: not a list of benchmarks of format {FORMAT}")
    faults = [f"entry {n}: {fault}" for n, entry in enumerate(data["benchmarks"], 1) for fault in faults_of(entry)]
    ids = [entry["id"] for entry in data["benchmarks"]] if not faults else []
    faults += [f"{name} is there more than once" for name in sorted(set(ids)) if ids.count(name) > 1]
    if faults:
        raise Refused(f"{path}: " + "; ".join(faults))
    return {entry["id"]: entry for entry in data["benchmarks"]}


def named(name: str, path: Path = LIST) -> dict:
    """One benchmark of the list."""
    benchmarks = read(path)
    if name not in benchmarks:
        raise Refused(f"no benchmark {name!r} in {path}; there are: {', '.join(benchmarks)}")
    return benchmarks[name]


def file_of(benchmark: dict, key: str, kept: Path = KEPT) -> Path:
    """The benchmark's briefing or texts as a file. Refused when the benchmark has none or the file is not there:
    a run is not started on words that are missing."""
    if key not in benchmark:
        raise Refused(f"the benchmark {benchmark['id']!r} has no {key}")
    file = kept / benchmark[key]
    if not file.is_file():
        raise Refused(f"the {key} of {benchmark['id']!r}, {file}, is not there")
    return file


def missing_of(benchmarks: dict[str, dict], kept: Path = KEPT) -> list[str]:
    """What the benchmarks name and the folder does not hold."""
    missing = []
    for name, benchmark in benchmarks.items():
        files = [f"{benchmark['save']}.Civ5Save", f"{benchmark['save']}.json"]
        files += [benchmark[key] for key in ("briefing", "texts") if key in benchmark]
        missing += [f"{name}: no {file}" for file in files if not (kept / file).is_file()]
    return missing


def is_on_points(benchmark: dict) -> bool:
    """Whether a run of the benchmark is scored in a scenario's own points and not on the scale of 0 to 1 that
    every other benchmark's score is on."""
    return benchmark["class"] == "scenario" and benchmark["won_by"] == "points"


def line_of(benchmark: dict) -> str:
    asked = {"victory": benchmark.get("victory", ""), "scenario": f"won by {benchmark.get('won_by')}"}.get(benchmark["class"], "")
    return f"{benchmark['id']}: {benchmark['class']}{', ' + asked if asked else ''}, {benchmark['turns']} turns on {benchmark['save']}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="say what the benchmarks name and saves/benchmark does not hold")
    a = ap.parse_args(argv)
    try:
        benchmarks = read()
    except Refused as e:
        print(e, file=sys.stderr)
        return 2
    if not a.check:
        print("\n".join(line_of(b) for b in benchmarks.values()))
        return 0
    missing = missing_of(benchmarks)
    print("\n".join(missing) if missing else f"{len(benchmarks)} benchmarks, every file they name is here")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
