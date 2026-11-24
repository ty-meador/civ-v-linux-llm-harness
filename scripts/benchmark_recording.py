#!/usr/bin/env python3
"""A run's recording as one file, and the check of such a file (docs/BENCHMARK.md, "How a player is scored").

A recording is what one run on one seed leaves: the run's row, the seat's calls from the call ledger, the run's
game file (the whole world at the start of every turn, one JSON line a turn) and the saved game at the end of the
turns. `pack` puts them into one file, a zip, with the starting save's id and hash and the versions the run was
played on. `check` reads such a file on any machine, with no network and with this one script alone: nothing else
of the repository is needed for it.

    scripts/benchmark_recording.py pack logs/boards/<id>/rows.jsonl                      # every run of the rows file
    scripts/benchmark_recording.py pack logs/boards/<id>/rows.jsonl --player codex/gpt-6-astra-high --seed 0
    scripts/benchmark_recording.py check logs/boards/<id>/recordings/*.recording.zip     # the file: no game needed
    scripts/benchmark_recording.py check FILE --load                                     # and its saved game, in the game

What a packed file holds:

    recording.json   what this is: the player, the seed, the starting save's id and sha256, the harness, the Lua
                     runtime and the game build of the run, how the calls were chosen, what the saved game is of,
                     and the size and sha256 of every other file
    row.json         the run's row, whole, as scripts/benchmark_run.py wrote it
    calls.jsonl      the seat's rows of the call ledger between the command's start and its end, as written
    game.Civ5Save    the saved game: the end of the turns, or where the game ended inside them
    game.jsonl       the run's game file (harness/spectator/game_file.py): line 1 the game's terms, its players and
                     the static map; then the world where the run started, the world as each turn began, taken
                     inside the game so that no turn is passed over, and the world where the run ended. Every line
                     names the hash of the line before it. Any reader of JSON lines reads it: a scorer needs no
                     game for the turns between the two ends, and `python -m harness.spectator --replay FILE`
                     plays a packed file on the page (docs/VISUALIZATION.md). A run played with `--no-game-file`,
                     or before the runner wrote one, packs without it and its file says so
    on-the-way/t<turn>.Civ5Save
                     the run's saves on the way, one for each the row lists (`benchmark_run.py --checkpoint N`)

The same run packs to the same bytes every time: nothing in the file is of the moment of packing.

Nothing in a file says what of it is scored. The row is packed whole, the command line the player was started by
included: read it before a file goes to someone else.

`check` says, line by line, what holds, what differs and what it cannot say here. Without the game: the zip opens,
every file is the size and hash `recording.json` names and no other file is in it, the row is the run the file says
it is, the calls are the seat's and inside the run's times and as many as the row counted, the saved game is a save
of the game, the starting save is the one kept under `saves/benchmark/` when one of that id is kept, and the game
file is whole (its lines numbered in order, each naming the hash of the one before), is of this run, has a line
for every turn the run played, and says of the seat at the run's start and of every player at its end what the row
says. With `--load` (the game at the main menu, tunerd running): the saved game is copied where the game loads
from, loaded, read the way the runner reads a game, and set beside the row and beside the game file's last line:
the turn, the seat's indicators, every player's score. The game is left for the main menu and the copy removed. Exit status 0 when nothing differs, 1 when
something does, 2 when a file cannot be read or the game is not at the main menu.

A row written before a run kept its own times and versions (2.19.0 and earlier) packs too, and its file says so:
the calls are then the seat's last calls before the row was written, as many as the row counted, and the versions
are not named.

Operator-side only, like the runner: `--load` sends Lua text to the game through the plain tunerd. `pack` and
`--load` use the runner's own code (scripts/benchmark_run.py beside this file); `check` without `--load` does not.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
import re
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FORMAT = 2              # 2: the game file in place of the page's stream (1 was never given out)
GAME_FILE_FORMAT = 1
MANIFEST, ROW, CALLS, GAME, TURNS = "recording.json", "row.json", "calls.jsonl", "game.Civ5Save", "game.jsonl"
ON_THE_WAY = re.compile(r"on-the-way/t(\d{3,})\.Civ5Save")
# The runner's own words, said again here so that `check` needs no other file (tests/test_benchmark_recording.py
# holds them to scripts/benchmark_run.py).
BUILT_IN_AI, THE_SAVE = "built-in-ai", "save"
INDICATORS = ("score", "techs", "policies", "cities", "population", "military", "land", "gold", "science", "happiness")
WORLDS = ("start", "turn", "end")


class Refused(Exception):
    """The file cannot be read as a recording, or the run cannot be packed; nothing was changed."""


_runner = None


def runner():
    """scripts/benchmark_run.py, loaded when `pack` or `check --load` first needs it."""
    global _runner
    if _runner is None:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        spec = importlib.util.spec_from_file_location("benchmark_run", Path(__file__).resolve().parent / "benchmark_run.py")
        if spec is None or spec.loader is None or not Path(spec.origin or "").is_file():
            raise Refused("scripts/benchmark_run.py is not beside this script: pack and check --load need the repository")
        _runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_runner)
    return _runner


def order(names) -> list[str]:
    """The files of a recording in the order they are written: the saves on the way last, by turn."""
    known = [n for n in (MANIFEST, ROW, CALLS, GAME, TURNS) if n in names]
    return known + sorted(n for n in names if ON_THE_WAY.fullmatch(n))


def player_of(row: dict) -> str:
    return row.get("player") or BUILT_IN_AI


SUFFIX = ".recording.zip"
KEPT = ROOT / "saves" / "benchmark"
SAVE_MAGIC = b"CIV5"                # the first bytes of every save this build writes
MEMBER_LIMIT = 1 << 30              # no file of a recording is read past this size: a zip names its own sizes
END, GAME_OVER = "the end of the turns", "the game's end"
OK, DIFFERS, UNKNOWN = "ok", "differs", "not checked"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def plain(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name)


def name_of(row: dict) -> str:
    return f"{row['save']}--{plain(player_of(row))}-seed{row.get('run', 0)}"


# ------------------------------------------------------------------ pack

def calls_of(row: dict, ledger: Path) -> tuple[bytes, dict]:
    """The run's calls, as the ledger's own lines, and how they were chosen. A row with its own times: the seat's
    rows between them. An older row: the seat's last rows before the row was written, as many as it counted."""
    if player_of(row) in (BUILT_IN_AI, THE_SAVE):
        return b"", {"rows": 0, "chosen": "none: the engine played the seat"}
    if not ledger.is_file():
        raise Refused(f"no call ledger at {ledger}")
    began, ended, seat = row.get("began"), row.get("ended"), row.get("seat")
    exact = isinstance(began, (int, float)) and isinstance(ended, (int, float))
    counted = (row.get("cost") or {}).get("calls") or 0
    if not exact:
        try:
            written = time.mktime(time.strptime(row["at"], "%Y-%m-%dT%H:%M:%S"))
        except (KeyError, ValueError) as e:
            raise Refused(f"the row has neither the run's times nor when it was written ({e})") from None
    kept: collections.deque = collections.deque(maxlen=None if exact else counted or 1)
    with ledger.open("rb") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if not isinstance(r, dict) or r.get("seat") != seat or not isinstance(r.get("t"), (int, float)):
                continue
            if began <= r["t"] <= ended if exact else r["t"] <= written:
                kept.append((r["t"], line.rstrip(b"\r\n")))
    rows = list(kept) if exact or counted else []
    how = {"rows": len(rows), "from": rows[0][0] if rows else None, "to": rows[-1][0] if rows else None,
           "chosen": "the seat's calls between the run's own times" if exact else
                     f"the seat's last {counted} calls before the row was written: the row is from before a run kept its times"}
    return b"".join(line + b"\n" for _t, line in rows), how


def saved_game_of(row: dict, saves: Path) -> tuple[bytes, dict]:
    """The run's saved game and what it is of. A run that kept none has no recording."""
    if row.get("end_reason") == "finish_only":
        raise Refused("a --finish-only row is no run: nothing was played")
    for key, of in (("end_save", END), ("game_over_save", GAME_OVER)):
        name = row.get(key)
        if not name:
            continue
        file = saves / f"{name}.Civ5Save"
        if not file.is_file():
            raise Refused(f"the row's saved game {name!r} is not in {saves}")
        info = {"name": name, "of": of, "turn": (row.get("end") or {}).get("turn") if of == END else row.get("game_over_save_turn")}
        if row.get("game_over_save_from"):
            info["from"] = row["game_over_save_from"]
        return file.read_bytes(), info
    raise Refused(f"the run kept no saved game (it ended as {row.get('end_reason')!r}); a recording needs one: "
                  f"play the run with --keep-end")


def saves_on_the_way_of(row: dict, saves: Path) -> tuple[dict[str, bytes], list[dict]]:
    """The saves the run kept on the way (`--checkpoint N`), by their names in the zip, and what each is. A save
    the row lists and the folder no longer holds stops the pack: a recording is whole or it is not made. A turn
    the row says no file came for is passed over, as the row has it."""
    files, listed = {}, []
    for kept in row.get("checkpoints") or []:
        if not isinstance(kept, dict) or not kept.get("save"):
            continue
        file = saves / f"{kept['save']}.Civ5Save"
        if not file.is_file():
            raise Refused(f"the row's save on the way {kept['save']!r} is not in {saves}")
        member = f"on-the-way/t{int(kept['turn']):03d}.Civ5Save"
        files[member] = file.read_bytes()
        listed.append({"file": member, "turn": kept["turn"], "name": kept["save"],
                       **({"seen_on_turn": kept["seen_on_turn"]} if "seen_on_turn" in kept else {})})
    return files, listed


def starting_save_of(row: dict, saves: Path) -> dict:
    if row.get("save_sha256"):
        return {"id": row["save"], "sha256": row["save_sha256"], "hashed": "by the run"}
    file = saves / f"{row['save']}.Civ5Save"
    if not file.is_file():
        return {"id": row["save"], "sha256": None, "hashed": None}
    return {"id": row["save"], "sha256": sha256(file.read_bytes()),
            "hashed": "at packing: the row is from before a run kept the hash"}


def made_with_of(row: dict) -> dict:
    if row.get("harness"):
        return {"harness": row["harness"], "runtime": row.get("runtime"), "game_build": row.get("game_build"), "said": "by the run"}
    return {"harness": None, "runtime": None, "game_build": None,
            "said": "not kept: the row is from before a run kept its versions"}


def game_file_of(row: dict, rows_file: Path | None) -> tuple[bytes | None, dict]:
    """The run's game file and what the manifest says of it. A row that names none (a run before the runner wrote
    one, or one played with --no-game-file) packs without; a row that names one that is no longer there stops the
    pack, like a save on the way."""
    said = row.get("game_file") if isinstance(row.get("game_file"), dict) else None
    named = (said or {}).get("file")
    if not named:
        return None, {"packed": False, "why": row.get("game_file_error") or "the run wrote none"}
    for file in (Path(named), ROOT / named, *((rows_file.parent / Path(named).name,) if rows_file else ())):
        if file.is_file():
            data = file.read_bytes()
            return data, {"packed": True, "format": GAME_FILE_FORMAT, "lines": data.count(b"\n")}
    raise Refused(f"the row names a game file, {named!r}, and no such file is there")


def members_of(row: dict, ledger: Path, saves: Path, rows_file: Path | None = None) -> dict[str, bytes]:
    """Every file of the run's recording by its name in the zip, `recording.json` included."""
    calls, how = calls_of(row, ledger)
    game, of = saved_game_of(row, saves)
    on_the_way, listed = saves_on_the_way_of(row, saves)
    files = {ROW: (json.dumps(row) + "\n").encode(), CALLS: calls, GAME: game, **on_the_way}
    turns, said = game_file_of(row, rows_file)
    if turns is not None:
        files[TURNS] = turns
    manifest = {"format": FORMAT, "name": name_of(row), "player": player_of(row), "seed": row.get("run", 0),
                "starting_save": starting_save_of(row, saves), "made_with": made_with_of(row),
                "packed_with": {"harness": runner().harness_version()}, "calls": how, "saved_game": of,
                "saves_on_the_way": listed, "game_file": said,
                "files": {name: {"bytes": len(data), "sha256": sha256(data)} for name, data in files.items()}}
    return {MANIFEST: (json.dumps(manifest, indent=1) + "\n").encode(), **files}


def write(path: Path, members: dict[str, bytes]) -> None:
    """The zip, the same bytes for the same members: a fixed order, a fixed date, nothing of the machine."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in order(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o644 << 16
            z.writestr(info, members[name])


def pack(row: dict, out: Path, ledger: Path, saves: Path, rows_file: Path | None = None) -> tuple[Path, dict]:
    """One run's recording written under `out`. Says the file and its `recording.json`."""
    members = members_of(row, ledger, saves, rows_file)
    path = out / (name_of(row) + SUFFIX)
    write(path, members)
    return path, json.loads(members[MANIFEST])


# ------------------------------------------------------------------ check

def read(path: Path) -> tuple[dict, dict[str, bytes]]:
    """`recording.json` and the files of a packed recording. Only the names a recording has are read, each up to
    MEMBER_LIMIT; nothing is written to disk."""
    try:
        with zipfile.ZipFile(path) as z:
            sizes = {i.filename: i.file_size for i in z.infolist()}
            if MANIFEST not in sizes:
                raise Refused(f"{path}: no {MANIFEST} in it; not a recording")
            known = order(sizes)
            big = [n for n in known if sizes[n] > MEMBER_LIMIT]
            if big:
                raise Refused(f"{path}: {', '.join(big)} is past {MEMBER_LIMIT} bytes; not read")
            members = {n: z.read(n) for n in known}
            members.update({n: b"" for n in sizes if n not in known})    # named, so the check can say it is there
    except (OSError, zipfile.BadZipFile) as e:
        raise Refused(f"{path}: not a readable zip ({e})") from None
    try:
        manifest = json.loads(members[MANIFEST])
    except ValueError as e:
        raise Refused(f"{path}: {MANIFEST} is not JSON ({e})") from None
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict):
        raise Refused(f"{path}: {MANIFEST} names no files")
    return manifest, members


def check_files(manifest: dict, members: dict[str, bytes]) -> list[tuple[str, str]]:
    out = []
    if manifest.get("format") != FORMAT:
        out.append((DIFFERS, f"format {manifest.get('format')!r}: this script reads format {FORMAT}"))
    named = manifest["files"]
    for name, meta in named.items():
        if name not in members:
            out.append((DIFFERS, f"{name}: named in {MANIFEST} and not in the file"))
        elif len(members[name]) != meta.get("bytes") or sha256(members[name]) != meta.get("sha256"):
            out.append((DIFFERS, f"{name}: not the bytes {MANIFEST} names ({len(members[name])} bytes, sha256 {sha256(members[name])[:12]}...)"))
        else:
            out.append((OK, f"{name}: {meta['bytes']} bytes, sha256 as named"))
    for name in members:
        if name != MANIFEST and name not in named:
            out.append((DIFFERS, f"{name}: in the file and not named in {MANIFEST}"))
    for name in (ROW, CALLS, GAME):
        if name not in named:
            out.append((DIFFERS, f"{name}: a recording has one and {MANIFEST} names none"))
    return out


def check_row(manifest: dict, members: dict[str, bytes]) -> tuple[dict | None, list[tuple[str, str]]]:
    try:
        row = json.loads(members.get(ROW, b""))
        assert isinstance(row, dict)
    except (ValueError, AssertionError):
        return None, [(DIFFERS, f"{ROW}: not a row")]
    said = (manifest.get("name"), manifest.get("player"), manifest.get("seed"), (manifest.get("starting_save") or {}).get("id"))
    is_ = (name_of(row), player_of(row), row.get("run", 0), row.get("save")) if row.get("save") else None
    if said != is_:
        return row, [(DIFFERS, f"the row is {is_}, the file says {said}")]
    return row, [(OK, f"the row is the run the file names: {row.get('save')}, {player_of(row)}, seed {row.get('run', 0)}, "
                      f"{row.get('end_reason')} after {row.get('turns_played')} turns")]


def check_calls(manifest: dict, row: dict, members: dict[str, bytes]) -> list[tuple[str, str]]:
    lines = members.get(CALLS, b"").splitlines()
    rows = []
    for n, line in enumerate(lines, 1):
        try:
            r = json.loads(line)
            assert isinstance(r, dict) and isinstance(r.get("t"), (int, float))
        except (ValueError, AssertionError):
            return [(DIFFERS, f"{CALLS}: line {n} is not a ledger row")]
        rows.append(r)
    out = []
    others = sorted({str(r.get("seat")) for r in rows if r.get("seat") != row.get("seat")})
    if others:
        out.append((DIFFERS, f"{CALLS}: calls of seat {', '.join(others)}; the run's seat is {row.get('seat')}"))
    began, ended = row.get("began"), row.get("ended")
    if isinstance(began, (int, float)) and isinstance(ended, (int, float)):
        outside = sum(1 for r in rows if not began <= r["t"] <= ended)
        if outside:
            out.append((DIFFERS, f"{CALLS}: {outside} calls outside the run's own times"))
    said, counted = (manifest.get("calls") or {}).get("rows"), (row.get("cost") or {}).get("calls")
    if said != len(rows):
        out.append((DIFFERS, f"{CALLS}: {len(rows)} calls, {MANIFEST} says {said}"))
    if counted is not None and counted != len(rows):
        out.append((DIFFERS, f"{CALLS}: {len(rows)} calls, the row counted {counted}"))
    if not out:
        which = "as many as the row counted" if counted is not None else "the row counted none: the engine played the seat"
        out.append((OK, f"{CALLS}: {len(rows)} calls of seat {row.get('seat')}, {which}"
                        + ("" if isinstance(began, (int, float)) or counted is None else "; chosen by count, the row has no times of its own")))
    return out


def check_saved_game(manifest: dict, members: dict[str, bytes]) -> list[tuple[str, str]]:
    game, of = members.get(GAME, b""), manifest.get("saved_game") or {}
    if not game.startswith(SAVE_MAGIC):
        return [(DIFFERS, f"{GAME}: does not begin as a save of the game does")]
    out = [(OK, f"{GAME}: a save of the game, of {of.get('of')}, turn {of.get('turn')}"
                + (f" ({of['from']})" if of.get("from") else ""))]
    listed = [k for k in manifest.get("saves_on_the_way") or [] if isinstance(k, dict)]
    there = sorted(n for n in members if ON_THE_WAY.fullmatch(n))
    if sorted(str(k.get("file")) for k in listed) != there:
        out.append((DIFFERS, f"saves on the way: {MANIFEST} lists {len(listed)}, the file holds {len(there)}"))
    bad = [n for n in there if not members[n].startswith(SAVE_MAGIC)]
    if bad:
        out.append((DIFFERS, f"{', '.join(bad)}: does not begin as a save of the game does"))
    elif there and len(out) == 1:
        out.append((OK, f"{len(there)} saves on the way, turns {', '.join(str(k.get('turn')) for k in listed)}"))
    return out


def check_starting_save(manifest: dict, starts: Path) -> list[tuple[str, str]]:
    start = manifest.get("starting_save") or {}
    if not start.get("sha256"):
        return [(UNKNOWN, f"starting save {start.get('id')!r}: the file names no hash")]
    kept = starts / f"{start.get('id')}.json"
    try:
        known = json.loads(kept.read_text()).get("sha256")
    except (OSError, ValueError):
        return [(UNKNOWN, f"starting save {start.get('id')!r}: none of that id is kept under {starts}; its hash is {start['sha256'][:12]}... ({start.get('hashed')})")]
    if known != start["sha256"]:
        return [(DIFFERS, f"starting save {start.get('id')!r}: the run's file is not the one kept here ({start['sha256'][:12]}... against {str(known)[:12]}...)")]
    return [(OK, f"starting save {start.get('id')!r}: the one kept here ({start.get('hashed')})")]


def figures(player: dict) -> dict:
    """A player's indicators out of a world line, in the row's shape: a list (the techs, the policies) by its count."""
    return {k: len(player[k]) if isinstance(player.get(k), list) else player.get(k) for k in INDICATORS}


def game_lines(data: bytes) -> tuple[list[dict], list[str]]:
    """The lines of a game file and what is wrong with them as a file, in words: every line a JSON object, line 1
    the game, the numbers in order, every `prev` the sha256 of the line before as written, every other line the
    world of a turn."""
    rows, wrong, prev = [], [], None
    for n, raw in enumerate(data.splitlines(), 1):
        try:
            row = json.loads(raw)
            assert isinstance(row, dict)
        except (ValueError, AssertionError):
            return rows, wrong + [f"line {n} is not a JSON object"]
        if row.get("line") != n:
            wrong.append(f"line {n} says it is line {row.get('line')!r}")
        if row.get("prev") != prev:
            wrong.append(f"line {n} does not name the hash of the line before it")
        if (n == 1) != (row.get("kind") == "game"):
            wrong.append(f"line {n} is of kind {row.get('kind')!r}")
        elif n > 1 and not (row.get("kind") in WORLDS and isinstance(row.get("turn"), int) and isinstance(row.get("world"), dict)):
            wrong.append(f"line {n} is no world of a turn")
        if len(wrong) > 8:
            return rows, wrong
        rows.append(row)
        prev = sha256(raw)
    if data and not data.endswith(b"\n"):
        wrong.append("the file ends in a half line")
    if not rows:
        wrong.append("no line")
    return rows, wrong


def standing(rows: list[dict]) -> list[dict]:
    """The game as it stands: a `turn` line of turn T sets aside every earlier world of turn T or later, a `start`
    line of turn T every earlier world of a turn after T (the game was loaded again and played on from there)."""
    kept: list[dict] = []
    for row in rows:
        if row.get("kind") == "turn":
            kept = [r for r in kept if r["turn"] < row["turn"]]
        elif row.get("kind") == "start":
            kept = [r for r in kept if r["turn"] <= row["turn"]]
        if row.get("kind") in WORLDS:
            kept.append(row)
    return kept


def seat_of(world: dict, seat) -> dict | None:
    return next((p for p in world.get("players") or [] if isinstance(p, dict) and p.get("id") == seat), None)


def check_game_file(manifest: dict, row: dict, members: dict[str, bytes]) -> list[tuple[str, str]]:
    said = manifest.get("game_file") if isinstance(manifest.get("game_file"), dict) else {}
    if TURNS not in members:
        if said.get("packed"):
            return [(DIFFERS, f"{TURNS}: {MANIFEST} says one is packed and the file holds none")]
        return [(UNKNOWN, f"no {TURNS}: {said.get('why') or 'the run wrote none'}; the turns between the run's two ends are not in this file")]
    rows, wrong = game_lines(members[TURNS])
    if wrong:
        return [(DIFFERS, f"{TURNS}: {w}") for w in wrong]
    head, worlds = rows[0], standing(rows[1:])
    out = []
    if head.get("format") != GAME_FILE_FORMAT:
        out.append((DIFFERS, f"{TURNS}: format {head.get('format')!r}: this script reads format {GAME_FILE_FORMAT}"))
    of, start_hash = head.get("run"), (manifest.get("starting_save") or {}).get("sha256")
    if not isinstance(of, dict):
        out.append((UNKNOWN, f"{TURNS}: its first line does not say which run it is of"))
    else:
        is_ = (of.get("save"), of.get("player"), of.get("seed"))
        if is_ != (row.get("save"), player_of(row), row.get("run", 0)):
            out.append((DIFFERS, f"{TURNS}: it is of {is_}, the row is {(row.get('save'), player_of(row), row.get('run', 0))}"))
        if of.get("save_sha256") and start_hash and of["save_sha256"] != start_hash:
            out.append((DIFFERS, f"{TURNS}: the starting save it names is not the one {MANIFEST} names"))
    seat, start, end = row.get("seat"), row.get("start") or {}, row.get("end") or {}
    first = worlds[0] if worlds else None
    last = worlds[-1] if worlds else None
    if first is None:
        return out + [(DIFFERS, f"{TURNS}: no world in it")]
    # where the run started: the seat's figures the runner read before anyone played
    me = seat_of(first["world"], seat)
    if first.get("kind") != "start" or me is None:
        out.append((DIFFERS, f"{TURNS}: it does not begin with the world the run started on (a {first.get('kind')!r} line, turn {first.get('turn')})"))
    elif start.get("values"):
        differs = [f"{k}: row {start['values'].get(k)}, game file {v}" for k, v in figures(me).items() if start["values"].get(k) != v]
        if first["turn"] != start.get("turn"):
            differs.insert(0, f"turn: row {start.get('turn')}, game file {first['turn']}")
        out += [(DIFFERS, f"{TURNS}: the seat at the run's start, {d}") for d in differs]
    # every turn the run played has its line
    turns = {w["turn"] for w in worlds if w.get("kind") == "turn"}
    if isinstance(start.get("turn"), int) and isinstance(end.get("turn"), int):
        absent = [t for t in range(start["turn"] + 1, end["turn"] + 1) if t not in turns]
        if absent:
            out.append((DIFFERS, f"{TURNS}: no line for the start of turn {', '.join(map(str, absent[:12]))}"
                                 + (f" and {len(absent) - 12} more" if len(absent) > 12 else "")))
    # where the run ended: what the runner read of the seat and of every player
    if last.get("kind") != "end":
        out.append((DIFFERS, f"{TURNS}: it does not end with the world the run ended on (a {last.get('kind')!r} line, turn {last.get('turn')})"))
    elif end.get("values"):
        if last["turn"] != end.get("turn"):
            out.append((UNKNOWN, f"{TURNS}: its last line is of turn {last['turn']} and the row was read on turn {end.get('turn')} "
                                 f"(the game went on between the two reads): the two are not set beside each other"))
        else:
            me = seat_of(last["world"], seat) or {}
            differs = [f"the seat's {k}: row {end['values'].get(k)}, game file {v}" for k, v in figures(me).items() if end["values"].get(k) != v]
            for p in row.get("players") or []:
                q = seat_of(last["world"], p.get("id")) or {}
                if (p.get("alive"), p.get("score")) != (q.get("alive"), q.get("score")):
                    differs.append(f"player {p.get('id')}: row alive {p.get('alive')} score {p.get('score')}, "
                                   f"game file alive {q.get('alive')} score {q.get('score')}")
            out += [(DIFFERS, f"{TURNS}: at the run's end, {d}") for d in differs]
    if not any(state == DIFFERS for state, _what in out):
        span = f"turns {min(turns)} to {max(turns)}" if turns else "no turn begun"
        out.append((OK, f"{TURNS}: {len(rows)} lines, whole and in order; of this run; the start (turn {first['turn']}), "
                        f"{span}, the end (turn {last['turn']}); the seat at the start and every player at the end as the row says"))
    return out


def check(path: Path, starts: Path = KEPT) -> tuple[dict, dict | None, dict[str, bytes], list[tuple[str, str]]]:
    """Everything that can be said of a packed recording with no game: the manifest, the row, the files and the
    findings, each `(ok | differs | not checked, what)`."""
    manifest, members = read(path)
    found = check_files(manifest, members)
    row, more = check_row(manifest, members)
    found += more
    if row is not None:
        found += check_calls(manifest, row, members)
    found += check_saved_game(manifest, members) + check_starting_save(manifest, starts)
    if row is not None:
        found += check_game_file(manifest, row, members)
    made = manifest.get("made_with") or {}
    found.append((OK if made.get("harness") else UNKNOWN,
                  f"played on harness {made.get('harness')}, runtime {made.get('runtime')}, game {made.get('game_build')} ({made.get('said')})"))
    return manifest, row, members, found


def check_in_game(g, manifest: dict, row: dict, game: bytes, saves: Path, leave=None,
                  turns: bytes | None = None, hand_back=None) -> list[tuple[str, str]]:
    """The saved game loaded and read the way the runner reads a game, set beside the row and, with the run's game
    file (`turns`), beside that file's last line. The game is left for the main menu and the copy of the save
    removed, whatever was found. A save the engine was playing when it was taken (the built-in AI's) is read at
    once and left only when the engine has handed the seat back: left a moment earlier, the game process died
    (benchmark_run.wait_for_the_seat)."""
    run = runner()
    leave, hand_back = leave or run.leave, hand_back or run.wait_for_the_seat
    of = manifest.get("saved_game") or {}
    name = f"recording-check-{sha256(game)[:12]}"
    file = saves / f"{name}.Civ5Save"
    saves.mkdir(parents=True, exist_ok=True)
    file.write_bytes(game)
    try:
        loaded = g.load_save(name)
        if not (isinstance(loaded, dict) and loaded.get("ok")):
            return [(DIFFERS, f"the saved game did not load: {(loaded or {}).get('err') if isinstance(loaded, dict) else loaded}")]
        seen = None
        try:
            seen = g.q(run.READ)
            out = [(OK, f"the saved game loads: turn {seen['turn']}")]
            return out + beside_the_row(seen, manifest, row, of) + beside_the_game_file(seen, of, turns)
        finally:
            if isinstance(seen, dict) and seen.get("auto"):
                try:
                    hand_back(g, row.get("seat") if isinstance(row.get("seat"), int) else 0)
                except Exception:       # the exit is tried whatever the wait came to
                    pass
            leave(g)
    finally:
        file.unlink(missing_ok=True)


def beside_the_row(seen: dict, manifest: dict, row: dict, of: dict) -> list[tuple[str, str]]:
    out = []
    build, ran_on = seen.get("build") or None, (manifest.get("made_with") or {}).get("game_build")
    if ran_on is None:
        out.append((UNKNOWN, f"the run names no game build; this game is {build}"))
    elif build != ran_on:
        out.append((DIFFERS, f"game build: the run was played on {ran_on}, this game is {build}"))
    else:
        out.append((OK, f"game build: {build}, the run's"))
    end = row.get("end") or {}
    if of.get("turn") is None or of.get("from"):
        return out + [(UNKNOWN, f"the saved game is not of the turn the row was read on ({of.get('from') or 'its turn is not named'}): "
                                f"its figures are not set beside the row's")]
    if of.get("turn") != end.get("turn"):
        ok = seen["turn"] == of["turn"]
        return out + [(OK if ok else DIFFERS, f"turn {seen['turn']}; the file says the save is of turn {of['turn']}"),
                      (UNKNOWN, f"the row was read on turn {end.get('turn')}, after the save: its figures are not set beside the row's")]
    differs = []
    if seen["turn"] != end.get("turn"):
        differs.append(f"turn: row {end.get('turn')}, game {seen['turn']}")
    for key in ("handicap", "speed"):
        if row.get(key) is not None and seen.get(key) != row[key]:
            differs.append(f"{key}: row {row[key]}, game {seen.get(key)}")
    seat = row.get("seat")
    if not any(p["id"] == seat for p in seen["players"]):
        return out + [(DIFFERS, f"the game has no player {seat}, the row's seat")]
    me = next(p for p in seen["players"] if p["id"] == seat)
    view = {"alive": me["alive"], "values": {k: me[k] for k in INDICATORS}}
    if view["alive"] != end.get("alive"):
        differs.append(f"the seat alive: row {end.get('alive')}, game {view['alive']}")
    for key in INDICATORS:
        if (end.get("values") or {}).get(key) != view["values"][key]:
            differs.append(f"the seat's {key}: row {(end.get('values') or {}).get(key)}, game {view['values'][key]}")
    in_row = {p.get("id"): p for p in row.get("players") or []}
    for p in seen["players"]:
        r = in_row.pop(p["id"], None)
        if r is None:
            differs.append(f"player {p['id']} ({p['civ']}): in the game and not in the row")
        elif (r.get("civ"), r.get("alive"), r.get("score")) != (p["civ"], p["alive"], p["score"]):
            differs.append(f"player {p['id']}: row {r.get('civ')} alive {r.get('alive')} score {r.get('score')}, "
                           f"game {p['civ']} alive {p['alive']} score {p['score']}")
    differs += [f"player {pid}: in the row and not in the game" for pid in in_row]
    if differs:
        return out + [(DIFFERS, d) for d in differs]
    return out + [(OK, f"the game reads as the row says: turn {seen['turn']}, the seat's {len(INDICATORS)} indicators "
                       f"(score {view['values']['score']}), {len(seen['players'])} players' scores")]


def beside_the_game_file(seen: dict, of: dict, turns: bytes | None) -> list[tuple[str, str]]:
    """The loaded game beside the game file's last line: every player's indicators. Only for a saved game of the
    moment that line is of (the end of the turns)."""
    if turns is None:
        return []
    rows, wrong = game_lines(turns)
    worlds = standing(rows[1:]) if not wrong else []
    last = worlds[-1] if worlds else None
    if last is None or last.get("kind") != "end":
        return [(UNKNOWN, f"{TURNS} has no last line to set the loaded game beside")]
    if of.get("from") or of.get("turn") != last["turn"] or seen["turn"] != last["turn"]:
        return [(UNKNOWN, f"the saved game (turn {seen['turn']}) is not of the moment {TURNS} ends on (turn {last['turn']}): "
                          f"the two are not set beside each other")]
    differs = []
    for p in seen["players"]:
        q = seat_of(last["world"], p["id"])
        if q is None:
            differs.append(f"player {p['id']} ({p['civ']}): in the game and not in {TURNS}")
            continue
        differs += [f"player {p['id']} ({p['civ']}), {k}: game {p[k]}, {TURNS} {v}" for k, v in figures(q).items() if p[k] != v]
    if differs:
        return [(DIFFERS, d) for d in differs]
    return [(OK, f"the game reads as {TURNS} ends: {len(seen['players'])} players, {len(INDICATORS)} indicators each")]


# ------------------------------------------------------------------ the commands

def pack_command(a) -> int:
    run = runner()
    rows = [r for r in run.read_rows(a.rows)
            if (a.player is None or player_of(r) == a.player) and (a.seed is None or r.get("run", 0) == a.seed)]
    if not rows:
        print(f"no row of {a.rows} is that run", file=sys.stderr)
        return 2
    out = a.out or a.rows.parent / "recordings"
    status = 0
    for row in rows:
        try:
            path, manifest = pack(row, out, a.ledger or run.ledger_path(), a.saves or run.saves_dir(), a.rows)
        except (Refused, run.Refused) as e:
            print(f"{row.get('save')}, {player_of(row)}, seed {row.get('run', 0)}: not packed: {e}", file=sys.stderr)
            status = 2
            continue
        game = manifest["saved_game"]
        print(f"{path}\n  {path.stat().st_size} bytes, sha256 {sha256(path.read_bytes())}\n"
              f"  {manifest['calls']['rows']} calls ({manifest['calls']['chosen']}); the saved game is of {game['of']}, "
              f"turn {game['turn']}; {len(manifest['saves_on_the_way'])} saves on the way; "
              + (f"the game file, {manifest['game_file']['lines']} lines" if manifest['game_file']['packed']
                 else f"no game file ({manifest['game_file']['why']})"))
    return status


def check_command(a) -> int:
    status, g = 0, None
    for path in a.files:
        print(path)
        gone = None
        try:
            manifest, row, members, found = check(path, a.starts)
            if a.load and row is not None and members.get(GAME, b"").startswith(SAVE_MAGIC):
                run = runner()
                if g is None:
                    from harness.game import Game
                    try:
                        g = Game()
                    except OSError as e:
                        raise Refused(f"tunerd does not answer ({e}); the saved game was not loaded") from None
                if g.has_state("InGame"):
                    raise Refused("a game is loaded: leave it for the main menu first (session main_menu); the saved game was not loaded")
                try:
                    found += check_in_game(g, manifest, row, members[GAME], a.saves or run.saves_dir(), turns=members.get(TURNS))
                except run.Refused as e:
                    raise Refused(str(e)) from None
                except Exception as e:      # the game or tunerd stopped answering under the check
                    for state, what in found:
                        print(f"  {state + ':':13}{what}")
                    g = None
                    raise Refused(f"the game stopped answering ({type(e).__name__}: {str(e)[:160]}); what is above was "
                                  f"found before that, and the saved game's check is not finished") from None
                try:
                    run.wait_main_menu(g)
                except Exception as e:      # the check is whole; the game is not where the next file needs it
                    gone = (f"the game did not come back to the main menu after the saved game was read "
                            f"({type(e).__name__}: {str(e)[:160]}): look at it before anything else is loaded")
                    g = None
        except Refused as e:
            print(f"  refused: {e}", file=sys.stderr)
            status = 2
            continue
        for state, what in found:
            print(f"  {state + ':':13}{what}")
        differs = sum(1 for state, _what in found if state == DIFFERS)
        print(f"  => {'nothing differs' if not differs else f'{differs} differ'}"
              + ("" if a.load else "; the saved game was not loaded (--load)"))
        status = max(status, 1 if differs else 0)
        if gone:
            print(f"  refused: {gone}", file=sys.stderr)
            status = 2
    return status


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="what", required=True)
    p = sub.add_parser("pack", help="pack the recording of each run of a rows file into one file")
    p.add_argument("rows", type=Path, help="a rows file of scripts/benchmark_run.py")
    p.add_argument("--player", help="only this player's runs")
    p.add_argument("--seed", type=int, help="only the run on this seed")
    p.add_argument("--out", type=Path, help="the folder the files go to (default: recordings/ beside the rows file)")
    p.add_argument("--ledger", type=Path, help="the call ledger (default: CIV5_CALL_LOG, else logs/calls.jsonl)")
    p.add_argument("--saves", type=Path, help="where the game keeps its saves (default: CIV5_SAVES_DIR, else the game's own folder)")
    c = sub.add_parser("check", help="check packed recordings: the files, and with --load the saved game in the game")
    c.add_argument("files", type=Path, nargs="+", metavar="FILE")
    c.add_argument("--load", action="store_true",
                   help="also load each saved game and set what the game reads beside the row (the game at the main menu)")
    c.add_argument("--starts", type=Path, default=KEPT, help="where starting saves and their manifests are kept (default saves/benchmark)")
    c.add_argument("--saves", type=Path, help="where the game loads saves from (default: CIV5_SAVES_DIR, else the game's own folder)")
    a = ap.parse_args(argv)
    return pack_command(a) if a.what == "pack" else check_command(a)


if __name__ == "__main__":
    sys.exit(main())
