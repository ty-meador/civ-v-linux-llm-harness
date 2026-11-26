#!/usr/bin/env python3
"""The report of scored recordings (docs/BENCHMARK.md, "The scores file and the report").

A recording is scored on another machine, by a method that is not in this repository. What comes back is a
scores file: for each recording its name, the sha256 of the file that was scored, and its score. This script sets
the scores beside the recordings they are of and writes the report: for each starting save and number of turns
asked, each player's score, its error over its own runs where it has more than one, how many of its runs played
their turns, and the seconds and tokens a turn. The built-in AI's run is in the same table, named as the
reference. The report gives scores and says nothing of how they are made.

    scripts/benchmark_report.py scores.json --recordings logs/boards
    scripts/benchmark_report.py week-47.json week-48.json --recordings logs/boards --json report.json

A scores file (format 1):

    {"format": 1,
     "scores": [{"recording": "<name>", "sha256": "<of the file scored>", "score": 0.512},
                {"recording": "<name>", "sha256": "...", "score": 0.431, "by_turn": [[1, 0.5], [2, 0.49]]},
                {"recording": "<name>", "sha256": "...", "not_scored": "why it has no score"}]}

A row has a `score` or a `not_scored`, never both. `by_turn` is the run's score as of each turn, for a graph of
it; a file without it is whole. A row with any other key is refused: the file is to hold scores and nothing else
of the scoring. A recording's name is one run (its starting save, player and run number), so a name has one
row in a file, and a file where it has two is refused. Several scores files are read in the order given, and a
recording scored in more than one takes its row from the last: a run packed again and scored again is one run.

A score is set beside the recording whose file has the sha256 its row names: files of one name are kept in more
than one folder, and only the hash says which of them was scored. `--recordings` folders are searched to any
depth for `*.recording.zip`.

`--json FILE` writes the report for a program to read (the site): what the tables hold, each run under its
player, a run's `by_turn` where the scores file had one, and what was given no score. No path of this machine is
in it. Nothing in either form is of the moment of writing.

Exit status 0 when every score has its recording, 1 when one has none here or a file under the folders is no
recording, 2 when a scores file cannot be read. No game and no network are needed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

SCORES_FORMAT = 1
REPORT_FORMAT = 1
TARGET_ERROR = 0.05     # the standard error "runs for an error of" is worked out for, as benchmark_run.py --summary
SHA256 = re.compile(r"[0-9a-f]{64}")
SCORE_ROW_KEYS = {"recording", "sha256", "score", "not_scored", "by_turn"}
TOKENS_READ, TOKENS_WRITTEN = ("new_in", "cache_read", "cache_write"), ("out",)
FINISHED = "finished"


class Refused(Exception):
    """A scores file cannot be read as one; nothing was written."""


_recording = None


def recording():
    """scripts/benchmark_recording.py: what a packed recording is, and how one is read."""
    global _recording
    if _recording is None:
        spec = importlib.util.spec_from_file_location("benchmark_recording", Path(__file__).resolve().parent / "benchmark_recording.py")
        if spec is None or spec.loader is None or not Path(spec.origin or "").is_file():
            raise Refused("scripts/benchmark_recording.py is not beside this script")
        _recording = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_recording)
    return _recording


# ------------------------------------------------------------------ the scores file
def is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def by_turn_faults(by_turn) -> list[str]:
    if not isinstance(by_turn, list) or not by_turn:
        return ["by_turn is not a list of [turn, score]"]
    pairs_ok = all(isinstance(p, list) and len(p) == 2 and isinstance(p[0], int) and not isinstance(p[0], bool)
                   and is_number(p[1]) for p in by_turn)
    if not pairs_ok:
        return ["by_turn is not a list of [turn, score]"]
    turns = [turn for turn, _ in by_turn]
    return [] if all(a < b for a, b in zip(turns, turns[1:])) else ["by_turn's turns do not go up"]


def score_row_faults(row) -> list[str]:
    """What keeps a row of a scores file from being read; empty when it is a row."""
    if not isinstance(row, dict):
        return ["not an object"]
    faults = []
    unknown = sorted(set(row) - SCORE_ROW_KEYS)
    if unknown:
        faults.append(f"holds more than scores: {', '.join(unknown)}")
    if not isinstance(row.get("recording"), str) or not row.get("recording"):
        faults.append("names no recording")
    if not isinstance(row.get("sha256"), str) or not SHA256.fullmatch(row["sha256"]):
        faults.append("sha256 is not the 64 hex digits of a file's hash")
    if ("score" in row) == ("not_scored" in row):
        faults.append("needs a score or a not_scored, and not both")
    if "score" in row and not is_number(row["score"]):
        faults.append("score is not a number")
    if "not_scored" in row and (not isinstance(row["not_scored"], str) or not row["not_scored"]):
        faults.append("not_scored does not say why")
    if "by_turn" in row:
        faults += ["by_turn goes with a score"] if "score" not in row else by_turn_faults(row["by_turn"])
    return faults


def read_scores(path: Path) -> list[dict]:
    """The rows of a scores file, each a row as the docstring above has it. Refused whole when any row is not: a
    file carried in by hand is either read or not, never read in part."""
    try:
        data = json.loads(Path(path).read_text())
    except OSError as e:
        raise Refused(f"{path}: cannot be read ({e})") from None
    except ValueError as e:
        raise Refused(f"{path}: not JSON ({e})") from None
    if not isinstance(data, dict) or data.get("format") != SCORES_FORMAT or not isinstance(data.get("scores"), list):
        raise Refused(f"{path}: not a scores file of format {SCORES_FORMAT}")
    faults = [f"row {n}: {fault}" for n, row in enumerate(data["scores"], 1) for fault in score_row_faults(row)]
    names = [row["recording"] for row in data["scores"]] if not faults else []
    faults += [f"{name} has more than one row" for name in sorted(set(names)) if names.count(name) > 1]
    if faults:
        raise Refused(f"{path}: " + "; ".join(faults))
    return data["scores"]


def latest_scores(files: list[list[dict]]) -> dict[str, dict]:
    """One row a recording, by its name: the row of the last scores file that has it. A run packed again and
    scored again is then one run with its later score, and not two."""
    return {row["recording"]: row for rows in files for row in rows}


# ------------------------------------------------------------------ the recordings
def tokens_of(row: dict, kinds: tuple[str, ...]) -> int | None:
    """The run's tokens of these kinds; None for a run whose row counted none (the built-in AI, a record lost)."""
    tokens = (row.get("cost") or {}).get("tokens") or {}
    return sum(tokens.get(k, 0) for k in kinds) if TOKENS_READ[0] in tokens else None


def run_of(manifest: dict, row: dict, sha256: str) -> dict:
    """What the report says of one recording. Only the fields named here leave the row: it also holds the command
    line the player was started by."""
    return {"recording": manifest["name"], "sha256": sha256, "starting_save": row["save"],
            "turns_asked": row.get("turns_asked"), "player": recording().player_of(row), "seed": row.get("run", 0),
            "result": row.get("result"), "end_reason": row.get("end_reason"), "turns_played": row.get("turns_played"),
            "seconds": row.get("seconds"), "tokens_read": tokens_of(row, TOKENS_READ),
            "tokens_written": tokens_of(row, TOKENS_WRITTEN), "harness": (manifest.get("made_with") or {}).get("harness")}


def read_recording(path: Path) -> dict:
    """The run of a packed recording, with the hash of the file. Raises the recording script's Refused for a file
    that is no recording or whose row is not the run the file names."""
    rec = recording()
    manifest, members = rec.read(path)
    row, found = rec.check_row(manifest, members)
    differing = [said for status, said in found if status == rec.DIFFERS]
    if row is None or differing:
        raise rec.Refused(f"{path}: {'; '.join(differing)}")
    return run_of(manifest, row, rec.sha256(Path(path).read_bytes()))


def recordings_under(folders: list[Path]) -> tuple[dict[str, dict], list[str]]:
    """Every recording under the folders by its file's sha256, and what was said of each file that is none."""
    rec = recording()
    runs: dict[str, dict] = {}
    not_read = [f"{folder}: no such folder or file" for folder in folders if not folder.exists()]
    paths = sorted({p for folder in folders for p in ([folder] if folder.is_file() else folder.rglob(f"*{rec.SUFFIX}"))})
    for path in paths:
        try:
            run = read_recording(path)
        except rec.Refused as e:
            not_read.append(str(e))
            continue
        runs.setdefault(run["sha256"], run)
    return runs, not_read


# ------------------------------------------------------------------ the report
def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def spread(xs: list[float]) -> float | None:
    """The standard deviation over a player's own runs; None for one run, which has none."""
    if len(xs) < 2:
        return None
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def a_turn(runs: list[dict], key: str) -> float | None:
    """A total of the runs that have it, over the turns those runs played."""
    have = [r for r in runs if r.get(key) is not None and r.get("turns_played")]
    return sum(r[key] for r in have) / sum(r["turns_played"] for r in have) if have else None


def player_line(player: str, runs: list[dict]) -> dict:
    scores = [r["score"] for r in runs]
    sd = spread(scores)
    return {"player": player, "reference": player == recording().BUILT_IN_AI, "runs": len(runs), "score": mean(scores),
            "error": None if sd is None else sd / math.sqrt(len(runs)), "spread": sd,
            "runs_for_target_error": None if sd is None else max(1, math.ceil((sd / TARGET_ERROR) ** 2)),
            "finished": sum(1 for r in runs if r["result"] == FINISHED),
            "seconds_a_turn": a_turn(runs, "seconds"), "tokens_read_a_turn": a_turn(runs, "tokens_read"),
            "tokens_written_a_turn": a_turn(runs, "tokens_written"),
            "recordings": sorted(runs, key=lambda r: (r["seed"], r["sha256"]))}


def benchmarks_of(scored: list[dict]) -> list[dict]:
    """The scored runs by what they are runs of: a starting save and the turns asked of it. A player's mean is
    taken over runs of one such pair only; inside it the players stand by score, the best first."""
    groups: dict[tuple, dict[str, list[dict]]] = {}
    for run in scored:
        groups.setdefault((run["starting_save"], run["turns_asked"]), {}).setdefault(run["player"], []).append(run)
    benchmarks = []
    for (save, turns), players in sorted(groups.items(), key=lambda g: (g[0][0], g[0][1] or 0)):
        lines = sorted((player_line(name, runs) for name, runs in players.items()), key=lambda p: (-p["score"], p["player"]))
        benchmarks.append({"starting_save": save, "turns_asked": turns, "players": lines})
    return benchmarks


def by_recording(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (r["recording"], r["sha256"]))


def report_of(scores: dict[str, dict], recordings: dict[str, dict], not_read: list[str]) -> dict:
    """The whole report as data: what the tables hold, and every score or recording that has no place in them.
    `scores` is by recording name (latest_scores), `recordings` by the sha256 of the file (recordings_under)."""
    scored, not_scored, no_recording = [], [], []
    for name, row in scores.items():
        sha256 = row["sha256"]
        run = recordings.get(sha256)
        if run is None or run["recording"] != name:
            held = f"the file of that hash here is {run['recording']}" if run else "no file of that hash here"
            no_recording.append({"recording": name, "sha256": sha256, "why": held})
        elif "not_scored" in row:
            not_scored.append({"recording": name, "sha256": sha256, "why": row["not_scored"]})
        else:
            scored.append({**run, "score": row["score"], **({"by_turn": row["by_turn"]} if "by_turn" in row else {})})
    scored_files = {row["sha256"] for row in scores.values()}
    no_score = sorted(f"{run['recording']} ({sha256[:12]})" for sha256, run in recordings.items() if sha256 not in scored_files)
    return {"format": REPORT_FORMAT, "target_error": TARGET_ERROR, "benchmarks": benchmarks_of(scored),
            "not_scored": by_recording(not_scored), "no_recording": by_recording(no_recording), "no_score": no_score,
            "not_read": not_read}


def for_the_site(report: dict) -> dict:
    """What of the report goes out: the tables and what was given no score. What is only this machine's
    bookkeeping (recordings with no score yet, files not read, and their paths) stays here."""
    return {key: report[key] for key in ("format", "target_error", "benchmarks", "not_scored")}


def fmt(x: float | None, places: int = 3) -> str:
    return "-" if x is None else f"{x:.{places}f}"


def table_of(benchmark: dict) -> list[str]:
    turns = benchmark["turns_asked"]
    lines = [f"## {benchmark['starting_save']}, {turns if turns is not None else 'no number of'} turns asked", "",
             f"| player | runs | score | error | spread | runs for an error of {TARGET_ERROR} | played their turns | "
             "seconds a turn | tokens read a turn | tokens written a turn |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for p in benchmark["players"]:
        name = f"{p['player']} (the reference)" if p["reference"] else p["player"]
        needed = "-" if p["runs_for_target_error"] is None else str(p["runs_for_target_error"])
        lines.append(f"| {name} | {p['runs']} | {fmt(p['score'])} | {fmt(p['error'])} | {fmt(p['spread'])} | {needed} | "
                     f"{p['finished']} of {p['runs']} | {fmt(p['seconds_a_turn'], 1)} | {fmt(p['tokens_read_a_turn'], 0)} | "
                     f"{fmt(p['tokens_written_a_turn'], 0)} |")
    return lines + [""]


def markdown_of(report: dict) -> str:
    scored = sum(p["runs"] for b in report["benchmarks"] for p in b["players"])
    lines = ["# OMTbench: the scores", "",
             f"{scored} scored recordings. A player's score is the mean of its runs of one starting save and number of "
             "turns asked. The error is the standard error over those runs and the spread their standard deviation; "
             "one run has neither. Tokens and seconds are over the turns the runs played.", ""]
    for benchmark in report["benchmarks"]:
        lines += table_of(benchmark)
    for title, key in (("Sent to be scored and given no score", "not_scored"), ("Scores with no recording here", "no_recording")):
        if report[key]:
            lines += [f"## {title}", "", *(f"- {r['recording']} ({r['sha256'][:12]}): {r['why']}" for r in report[key]), ""]
    for title, key in (("Recordings here with no score", "no_score"), ("Files that are no recording", "not_read")):
        if report[key]:
            lines += [f"## {title}", "", *(f"- {said}" for said in report[key]), ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scores", type=Path, nargs="+", metavar="SCORES", help="scores files, the latest last")
    ap.add_argument("--recordings", type=Path, nargs="+", required=True, metavar="FOLDER",
                    help="where the scored recordings are kept: folders searched to any depth, or the files themselves")
    ap.add_argument("--json", type=Path, metavar="FILE", help="also write the report as JSON, for the site")
    a = ap.parse_args(argv)
    try:
        scores = latest_scores([read_scores(path) for path in a.scores])
    except Refused as e:
        print(e, file=sys.stderr)
        return 2
    recordings, not_read = recordings_under(a.recordings)
    report = report_of(scores, recordings, not_read)
    print(markdown_of(report))
    if a.json:
        a.json.write_text(json.dumps(for_the_site(report), indent=1) + "\n")
    return 1 if report["no_recording"] or report["not_read"] else 0


if __name__ == "__main__":
    sys.exit(main())
