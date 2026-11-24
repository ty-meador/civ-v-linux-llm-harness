"""scripts/benchmark_recording.py: a run's recording packed as one file, and the check of one, with no game and
against a fake one.

Live 2026-11-23 (docs/BENCHMARK.md, "A recording as one file"): three runs of the duel packed and checked in the
game. The two saves of the end of the turns read as their rows say, every figure. The save of a game won by taking a
city in that turn read one figure differently after the load, the seat's happiness (23 in the row, 9 in the game):
the check says which figure differs and nothing more. The same evening a run's game file took the place of the
page's stream in the packed file: the built-in AI's ten turns, thirteen lines, checked here and on another machine
with this script alone.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("benchmark_recording", ROOT / "scripts" / "benchmark_recording.py")
rec = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(rec)
run = rec.runner()

SAVE = b"CIV5\x08\x00\x00\x00 the saved game"
MAP = {"ok": True, "w": 2, "h": 2, "key": "2x2:7", "layers": {"terrain": ["GC", "PO"]}, "legend": {}}


def player(pid, human=False, alive=True, **kw):
    row = {"id": pid, "civ": f"civ{pid}", "alive": alive, "human": human, "team": pid, "turn_active": human}
    row.update({k: 10 for k in run.INDICATORS})
    row.update({k: 0 for k in run.ROUTES})
    row.update(kw)
    return row


def game_read(turn=10, build="1.0.3.279(130961)", **seat):
    return {"turn": turn, "state": 0, "winner": -1, "victory": "", "auto": 0, "active": 0, "max_turns": 0, "build": build,
            "handicap": "HANDICAP_KING", "speed": "GAMESPEED_QUICK", "slots": [3, 1, 4, 4],
            "players": [player(0, human=True, **{"score": 150, **seat}), player(1, score=310)]}


def a_row(**kw):
    """A player's row as the runner writes it since a run keeps its own times and versions."""
    seen = game_read()
    row = {"player": "codex/x", "command": ["loop"], "save": "start-a", "seat": 0, "turns_asked": 10, "skip": 0,
           "handicap": "HANDICAP_KING", "speed": "GAMESPEED_QUICK", "game_build": "1.0.3.279(130961)",
           "end_reason": "all_turns_played", "began": 1000.0, "ended": 2000.0, "cost": {"calls": 2},
           "start": run.seat_view(game_read(turn=0, score=4), 0),
           "end": run.seat_view(seen, 0), "turns_played": 10, "winner": -1, "victory": "",
           "players": [{k: p[k] for k in ("id", "civ", "alive", "score")} for p in seen["players"]],
           "end_save": "start-a--codex-x-seed0-end", "result": "finished", "run": 0, "at": "2026-11-23T19:56:39",
           "harness": "2.20.0", "runtime": 349, "save_sha256": rec.sha256(b"the starting save")}
    row.update(kw)
    return row


def call(t, seat=0, **kw):
    return {"t": t, "seat": seat, "tool": "state", "kind": "read", "ok": True, **kw}


def world(turn, **seat):
    """The world of a game file's line that the runner's read of the same moment is `game_read(turn, **seat)` of."""
    rows = []
    for p in game_read(turn=turn, **seat)["players"]:
        row = {k: p[k] for k in ("id", "alive", "human", "team", *run.INDICATORS)}
        row["techs"], row["policies"] = [f"TECH{n}" for n in range(p["techs"])], [f"POLICY{n}" for n in range(p["policies"])]
        rows.append(row)
    return {"active": 0, "players": rows, "cities": [], "units": [], "owners": {"rows": ["..", ".."], "legend": {}}, "fog": {}}


def a_game_file(path, row=None, worlds=None, about=None):
    """A run's game file as the recorder writes it (harness/spectator/game_file.py): the game, the start, a line a
    turn, the end. `worlds`: `(kind, turn, world)` in place of the ten turns of a_row()."""
    from harness.spectator import game_file
    row = row or a_row()
    if worlds is None:
        worlds = [("start", 0, world(0, score=4)), *(("turn", t, world(t)) for t in range(1, 11)), ("end", 10, world(10))]
    Path(path).unlink(missing_ok=True)
    f = game_file.GameFile(path)
    f.append("game", {"format": game_file.FORMAT, "key": "2x2-abc", "map": MAP,
                      "game": {"players": [{"id": 0, "name": "A", "civ": "civ0"}, {"id": 1, "name": "B", "civ": "civ1"}]},
                      "run": about or {"save": row["save"], "player": row["player"], "seed": row.get("run", 0),
                                       "save_sha256": row.get("save_sha256")}}, t=1000.0)
    for n, (kind, turn, w) in enumerate(worlds):
        f.append(kind, {"turn": turn, "world": w}, t=1000.0 + n)
    return path


class Files(unittest.TestCase):
    def setUp(self):
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.saves, self.starts, self.out = self.dir / "saves", self.dir / "starts", self.dir / "out"
        self.saves.mkdir()
        self.starts.mkdir()
        (self.saves / "start-a.Civ5Save").write_bytes(b"the starting save")
        (self.saves / "start-a--codex-x-seed0-end.Civ5Save").write_bytes(SAVE)
        self.ledger = self.dir / "calls.jsonl"
        self.calls([call(999.9), call(1000.0), call(1500.0, seat=1), call(2000.0), call(2000.1)])

    def calls(self, rows):
        self.ledger.write_text("".join(json.dumps(r) + "\n" for r in rows) + "not json\n")

    def pack(self, row=None, **kw):
        return rec.pack(row or a_row(**kw), self.out, self.ledger, self.saves)

    def with_game_file(self, worlds=None, about=None, **kw):
        """A run that wrote a game file, packed: the file and its `recording.json`."""
        row = a_row(**kw)
        file = a_game_file(self.dir / "rows-codex-x-seed0-game.jsonl", row, worlds, about)
        row["game_file"] = {"file": str(file), "lines": 13}
        return rec.pack(row, self.out, self.ledger, self.saves)

    def differs(self, path):
        return [what for state, what in self.check(path) if state == rec.DIFFERS]

    def check(self, path):
        return rec.check(path, self.starts)[3]

    def states(self, path):
        return {state for state, _what in self.check(path)}

    def rewritten(self, path, **members):
        """The packed file with some of its files replaced or added, `recording.json` as it was."""
        with zipfile.ZipFile(path) as z:
            was = {n: z.read(n) for n in z.namelist()}
        was.update({k.replace("__", "."): v for k, v in members.items()})
        with zipfile.ZipFile(path, "w") as z:
            for name, data in was.items():
                z.writestr(name, data)
        return path


class Pack(Files):
    def test_one_file_holds_the_row_the_seats_calls_of_the_run_and_the_saved_game(self):
        path, manifest = self.pack()
        self.assertEqual(path.name, "start-a--codex-x-seed0.recording.zip")
        with zipfile.ZipFile(path) as z:
            self.assertEqual(z.namelist(), ["recording.json", "row.json", "calls.jsonl", "game.Civ5Save"])
            self.assertEqual(json.loads(z.read("row.json")), a_row())
            self.assertEqual([json.loads(line)["t"] for line in z.read("calls.jsonl").splitlines()], [1000.0, 2000.0])
            self.assertEqual(z.read("game.Civ5Save"), SAVE)
        self.assertEqual(manifest["starting_save"], {"id": "start-a", "sha256": rec.sha256(b"the starting save"), "hashed": "by the run"})
        self.assertEqual(manifest["made_with"], {"harness": "2.20.0", "runtime": 349, "game_build": "1.0.3.279(130961)", "said": "by the run"})
        self.assertEqual((manifest["calls"]["rows"], manifest["calls"]["from"], manifest["calls"]["to"]), (2, 1000.0, 2000.0))
        self.assertEqual(manifest["saved_game"], {"name": "start-a--codex-x-seed0-end", "of": rec.END, "turn": 10})
        self.assertEqual(manifest["files"]["game.Civ5Save"], {"bytes": len(SAVE), "sha256": rec.sha256(SAVE)})
        self.assertEqual(manifest["game_file"], {"packed": False, "why": "the run wrote none"})
        self.assertEqual((manifest["format"], manifest["saves_on_the_way"]), (rec.FORMAT, []))

    def test_the_same_run_packs_to_the_same_bytes(self):
        first = self.pack()[0].read_bytes()
        time.sleep(0.01)
        self.assertEqual(self.pack()[0].read_bytes(), first)

    def test_a_row_from_before_a_run_kept_its_times_takes_the_seats_last_calls_as_many_as_it_counted(self):
        at = time.mktime(time.strptime("2026-11-23T19:56:39", "%Y-%m-%dT%H:%M:%S"))
        self.calls([call(at - 900), call(at - 300), call(at - 200, seat=1), call(at - 100), call(at + 50)])
        row = a_row()
        for key in ("began", "ended", "harness", "runtime", "game_build", "save_sha256"):
            del row[key]
        path, manifest = self.pack(row)
        with zipfile.ZipFile(path) as z:
            self.assertEqual([json.loads(line)["t"] for line in z.read("calls.jsonl").splitlines()], [at - 300, at - 100])
        self.assertIn("last 2 calls before the row was written", manifest["calls"]["chosen"])
        self.assertEqual((manifest["made_with"]["harness"], manifest["made_with"]["runtime"]), (None, None))
        self.assertIn("not kept", manifest["made_with"]["said"])
        self.assertEqual(manifest["starting_save"]["sha256"], rec.sha256(b"the starting save"))
        self.assertIn("at packing", manifest["starting_save"]["hashed"])
        self.assertNotIn(rec.DIFFERS, self.states(path))

    def test_the_built_in_ais_run_has_no_calls(self):
        (self.saves / "start-a--built-in-ai-seed3-end.Civ5Save").write_bytes(SAVE)
        row = a_row(player=run.BUILT_IN_AI, end_save="start-a--built-in-ai-seed3-end", run=3)
        del row["cost"], row["began"], row["ended"]
        path, manifest = self.pack(row)
        self.assertEqual(path.name, "start-a--built-in-ai-seed3.recording.zip")
        self.assertEqual(manifest["calls"]["rows"], 0)
        self.assertNotIn(rec.DIFFERS, self.states(path))

    def test_a_game_that_ended_inside_the_turns_packs_the_save_of_its_end(self):
        (self.saves / "start-a--codex-x-seed0-game-over.Civ5Save").write_bytes(SAVE)
        row = a_row(end_reason="game_won", game_over_save="start-a--codex-x-seed0-game-over", game_over_save_turn=7)
        del row["end_save"]
        self.assertEqual(self.pack(row)[1]["saved_game"], {"name": "start-a--codex-x-seed0-game-over", "of": rec.GAME_OVER, "turn": 7})

    def test_the_saves_on_the_way_are_packed_one_for_each_the_row_lists(self):
        """What the game's file holds only as of the save is read at every save a run kept (`--checkpoint N`), so a
        recording without them is not the whole run."""
        for turn in (10, 20):
            (self.saves / f"start-a--codex-x-seed0-t{turn:03d}.Civ5Save").write_bytes(SAVE + bytes([turn]))
        kept = [{"turn": 10, "save": "start-a--codex-x-seed0-t010", "seen_on_turn": 11},
                {"turn": 20, "save": "start-a--codex-x-seed0-t020", "seen_on_turn": 20}, {"turn": 30, "save": None}]
        path, manifest = self.pack(checkpoints=kept)
        with zipfile.ZipFile(path) as z:
            self.assertEqual(z.namelist(), ["recording.json", "row.json", "calls.jsonl", "game.Civ5Save",
                                            "on-the-way/t010.Civ5Save", "on-the-way/t020.Civ5Save"])
            self.assertEqual(z.read("on-the-way/t020.Civ5Save"), SAVE + bytes([20]))
        self.assertEqual(manifest["saves_on_the_way"],
                         [{"file": "on-the-way/t010.Civ5Save", "turn": 10, "name": "start-a--codex-x-seed0-t010", "seen_on_turn": 11},
                          {"file": "on-the-way/t020.Civ5Save", "turn": 20, "name": "start-a--codex-x-seed0-t020", "seen_on_turn": 20}])
        self.assertIn((rec.OK, "2 saves on the way, turns 10, 20"), self.check(path))
        self.rewritten(path, **{"on-the-way/t020__Civ5Save": b"junk"})
        self.assertTrue(any(what.startswith("on-the-way/t020.Civ5Save: not the bytes") for state, what in self.check(path) if state == rec.DIFFERS))
        (self.saves / "start-a--codex-x-seed0-t010.Civ5Save").unlink()
        with self.assertRaisesRegex(rec.Refused, "save on the way 'start-a--codex-x-seed0-t010' is not in"):
            self.pack(checkpoints=kept)

    def test_a_run_with_no_saved_game_has_no_recording(self):
        row = a_row(end_reason="turns_not_played")
        del row["end_save"]
        with self.assertRaisesRegex(rec.Refused, "kept no saved game.*turns_not_played.*--keep-end"):
            self.pack(row)
        with self.assertRaisesRegex(rec.Refused, "is not in"):
            self.pack(end_save="gone")
        with self.assertRaisesRegex(rec.Refused, "no run"):
            self.pack(end_reason="finish_only")
        self.assertFalse(self.out.exists())

    def test_the_runs_game_file_is_packed_as_it_was_written_and_the_page_plays_the_packed_file(self):
        path, manifest = self.with_game_file()
        written = (self.dir / "rows-codex-x-seed0-game.jsonl").read_bytes()
        self.assertEqual(manifest["game_file"], {"packed": True, "format": 1, "lines": 13})
        with zipfile.ZipFile(path) as z:
            self.assertEqual(z.namelist(), ["recording.json", "row.json", "calls.jsonl", "game.Civ5Save", "game.jsonl"])
            self.assertEqual(z.read("game.jsonl"), written)
        self.assertIn((rec.OK, "game.jsonl: 13 lines, whole and in order; of this run; the start (turn 0), turns 1 to 10, "
                               "the end (turn 10); the seat at the start and every player at the end as the row says"), self.check(path))
        self.assertNotIn(rec.DIFFERS, self.states(path))
        from harness.spectator import feed
        events, game = feed.open_replay(str(path))
        self.addCleanup(Path(game).unlink)
        self.assertEqual(Path(game).read_bytes(), written)
        self.assertEqual([e["type"] for e in events], ["hello", "snapshot", "call", *["snapshot"] * 11, "call"])
        self.assertEqual((events[0]["data"], events[1]["data"]["players"][0]["civ"]), ({"map": MAP}, "civ0"))
        self.assertEqual([e["seq"] for e in events], list(range(1, 16)))

    def test_a_row_that_names_a_game_file_that_is_gone_is_not_packed(self):
        with self.assertRaisesRegex(rec.Refused, "names a game file.*no such file"):
            self.pack(game_file={"file": str(self.dir / "gone.jsonl")})
        self.assertEqual(self.pack(game_file_error="NoGame: no tunerd")[1]["game_file"], {"packed": False, "why": "NoGame: no tunerd"})

    def test_the_page_refuses_a_packed_file_with_no_game_file_and_takes_a_stream_as_it_is(self):
        from harness.spectator import feed
        with self.assertRaisesRegex(ValueError, "holds no game.jsonl"):
            feed.open_replay(str(self.pack()[0]))
        self.assertEqual(feed.open_replay(str(self.ledger)), (None, None))
        file = a_game_file(self.dir / "alone.jsonl")
        events, game = feed.open_replay(str(file))
        self.assertEqual((game, [e["type"] for e in events]), (str(file), ["hello", *["snapshot"] * 12]))


class Check(Files):
    def test_a_packed_file_checks_and_says_what_it_cannot(self):
        found = self.check(self.pack()[0])
        self.assertEqual({state for state, _ in found}, {rec.OK, rec.UNKNOWN})
        self.assertEqual([what for state, what in found if state == rec.UNKNOWN],
                         [f"starting save 'start-a': none of that id is kept under {self.starts}; its hash is "
                          f"{rec.sha256(b'the starting save')[:12]}... (by the run)",
                          "no game.jsonl: the run wrote none; the turns between the run's two ends are not in this file"])

    def test_the_check_needs_this_script_and_nothing_else_of_the_repository(self):
        """Seen on another machine, 2026-11-23: the first check loaded scripts/benchmark_run.py from beside itself
        and stopped with FileNotFoundError where only the one script had been copied."""
        self.assertEqual((rec.BUILT_IN_AI, rec.THE_SAVE, rec.INDICATORS), (run.BUILT_IN_AI, run.THE_SAVE, run.INDICATORS))
        from harness.spectator import game_file
        self.assertEqual((rec.GAME_FILE_FORMAT, rec.WORLDS, rec.TURNS), (game_file.FORMAT, game_file.KINDS, "game.jsonl"))
        path = self.with_game_file()[0]
        alone = self.dir / "alone"
        alone.mkdir()
        shutil.copy(ROOT / "scripts" / "benchmark_recording.py", alone)
        done = subprocess.run([sys.executable, "-I", "benchmark_recording.py", "check", str(path), "--starts", str(self.starts)],
                              cwd=alone, capture_output=True, text=True, check=False)
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        self.assertIn("game.jsonl: 13 lines, whole and in order", done.stdout)
        self.assertIn("=> nothing differs", done.stdout)
        done = subprocess.run([sys.executable, "-I", "benchmark_recording.py", "check", str(path), "--load"],
                              cwd=alone, capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 2)
        self.assertIn("benchmark_run.py is not beside this script", done.stderr)

    def test_a_game_file_with_a_line_changed_or_gone_is_said(self):
        path = self.with_game_file()[0]
        with zipfile.ZipFile(path) as z:
            lines, manifest = z.read("game.jsonl").splitlines(), json.loads(z.read("recording.json"))

        def packed_as(data: bytes):
            manifest["files"]["game.jsonl"] = {"bytes": len(data), "sha256": rec.sha256(data)}
            return self.rewritten(path, game__jsonl=data, recording__json=json.dumps(manifest).encode())
        changed = [line.replace(b'"gold":10', b'"gold":99') if n == 5 else line for n, line in enumerate(lines)]
        self.assertEqual(self.differs(packed_as(b"\n".join(changed) + b"\n")),
                         ["game.jsonl: line 7 does not name the hash of the line before it"])
        self.assertEqual(self.differs(packed_as(b"\n".join(lines[:5] + lines[6:]) + b"\n"))[:2],
                         ["game.jsonl: line 6 says it is line 7", "game.jsonl: line 6 does not name the hash of the line before it"])
        self.assertEqual(self.differs(packed_as(b"\n".join(lines) + b"\n" + lines[3][:40])),
                         ["game.jsonl: line 14 is not a JSON object"])
        self.assertEqual(self.differs(packed_as(b"")), ["game.jsonl: no line"])
        self.assertIn("game.jsonl: recording.json says one is packed and the file holds none",
                      self.differs(self.without(path, "game.jsonl")))

    def without(self, path, name):
        with zipfile.ZipFile(path) as z:
            was = {n: z.read(n) for n in z.namelist() if n != name}
        with zipfile.ZipFile(path, "w") as z:
            for n, data in was.items():
                z.writestr(n, data)
        return path

    def test_a_game_file_of_another_run_or_one_that_says_other_figures_than_the_row_differs(self):
        self.assertEqual(self.differs(self.with_game_file(about={"save": "start-b", "player": "codex/x", "seed": 0})[0]),
                         ["game.jsonl: it is of ('start-b', 'codex/x', 0), the row is ('start-a', 'codex/x', 0)"])
        other_start = {"save": "start-a", "player": "codex/x", "seed": 0, "save_sha256": "0" * 64}
        self.assertEqual(self.differs(self.with_game_file(about=other_start)[0]),
                         ["game.jsonl: the starting save it names is not the one recording.json names"])
        turns = [("turn", t, world(t)) for t in range(1, 11)]
        end = world(10, happiness=9)
        end["players"][1]["score"] = 311
        self.assertEqual(self.differs(self.with_game_file([("start", 0, world(0, score=4)), *turns, ("end", 10, end)])[0]),
                         ["game.jsonl: at the run's end, the seat's happiness: row 10, game file 9",
                          "game.jsonl: at the run's end, player 1: row alive True score 310, game file alive True score 311"])
        self.assertEqual(self.differs(self.with_game_file([("start", 0, world(0, score=5)), *turns, ("end", 10, world(10))])[0]),
                         ["game.jsonl: the seat at the run's start, score: row 4, game file 5"])

    def test_a_turn_with_no_line_and_a_file_that_does_not_end_where_the_run_did_are_said(self):
        start, end = ("start", 0, world(0, score=4)), ("end", 10, world(10))
        turns = [("turn", t, world(t)) for t in range(1, 11)]
        self.assertEqual(self.differs(self.with_game_file([start, *turns[:3], *turns[5:], end])[0]),
                         ["game.jsonl: no line for the start of turn 4, 5"])
        self.assertEqual(self.differs(self.with_game_file([start, *turns])[0]),
                         ["game.jsonl: it does not end with the world the run ended on (a 'turn' line, turn 10)"])
        self.assertEqual(self.differs(self.with_game_file([*turns, end])[0]),
                         ["game.jsonl: it does not begin with the world the run started on (a 'turn' line, turn 1)"])
        # the engine played on between the runner's read and the recorder's last line: said, and not a difference
        found = self.check(self.with_game_file([start, *turns, ("turn", 11, world(11)), ("end", 11, world(11, score=999))])[0])
        self.assertNotIn(rec.DIFFERS, {state for state, _what in found})
        self.assertTrue(any(state == rec.UNKNOWN and "its last line is of turn 11 and the row was read on turn 10" in what
                            for state, what in found))

    def test_a_game_loaded_again_inside_the_run_is_read_as_it_stands(self):
        """A game that died and was loaded again from its last save goes back in turns; the file keeps both."""
        worlds = [("start", 0, world(0, score=4)), *(("turn", t, world(t, score=1)) for t in range(1, 7)),
                  ("start", 4, world(4)), *(("turn", t, world(t)) for t in range(5, 11)), ("end", 10, world(10))]
        found = self.check(self.with_game_file(worlds)[0])
        self.assertNotIn(rec.DIFFERS, {state for state, _what in found})
        self.assertTrue(any(what.startswith("game.jsonl: 16 lines, whole and in order") for _state, what in found))

    def test_the_starting_save_is_set_beside_the_one_kept_here(self):
        path = self.pack()[0]
        (self.starts / "start-a.json").write_text(json.dumps({"id": "start-a", "sha256": rec.sha256(b"the starting save")}))
        self.assertIn((rec.OK, "starting save 'start-a': the one kept here (by the run)"), self.check(path))
        (self.starts / "start-a.json").write_text(json.dumps({"id": "start-a", "sha256": "0" * 64}))
        self.assertIn(rec.DIFFERS, self.states(path))

    def test_a_file_changed_after_packing_differs(self):
        path = self.rewritten(self.pack()[0], game__Civ5Save=SAVE + b"!")
        self.assertTrue(any(state == rec.DIFFERS and what.startswith("game.Civ5Save: not the bytes") for state, what in self.check(path)))

    def test_a_file_the_manifest_does_not_name_differs(self):
        path = self.rewritten(self.pack()[0], **{"extra__txt": b"x"})
        self.assertIn((rec.DIFFERS, "extra.txt: in the file and not named in recording.json"), self.check(path))

    def test_calls_of_another_seat_outside_the_run_or_not_as_many_as_counted_differ(self):
        def packed(**kw):
            """A file whose calls are `rows` under a manifest that names them truly: only the row disagrees."""
            members = rec.members_of(a_row(**kw), self.ledger, self.saves)
            path = self.out / "x.recording.zip"
            rec.write(path, members)
            return path
        self.assertTrue(any("the row counted 5" in what for state, what in self.check(packed(cost={"calls": 5})) if state == rec.DIFFERS))
        path = self.pack()[0]
        with zipfile.ZipFile(path) as z:
            manifest = json.loads(z.read("recording.json"))
        calls = (json.dumps(call(1000.0, seat=1)) + "\n" + json.dumps(call(2500.0)) + "\n").encode()
        manifest["files"]["calls.jsonl"] = {"bytes": len(calls), "sha256": rec.sha256(calls)}
        self.rewritten(path, calls__jsonl=calls, recording__json=json.dumps(manifest).encode())
        whats = [what for state, what in self.check(path) if state == rec.DIFFERS]
        self.assertEqual(whats, ["calls.jsonl: calls of seat 1; the run's seat is 0", "calls.jsonl: 1 calls outside the run's own times"])

    def test_a_row_that_is_another_run_or_a_save_that_is_no_save_differs(self):
        path = self.rewritten(self.pack()[0])
        with zipfile.ZipFile(path) as z:
            manifest = json.loads(z.read("recording.json"))
        row = (json.dumps(a_row(player="someone/else")) + "\n").encode()
        manifest["files"]["row.json"] = {"bytes": len(row), "sha256": rec.sha256(row)}
        manifest["files"]["game.Civ5Save"] = {"bytes": 4, "sha256": rec.sha256(b"junk")}
        self.rewritten(path, row__json=row, game__Civ5Save=b"junk", recording__json=json.dumps(manifest).encode())
        whats = [what for state, what in self.check(path) if state == rec.DIFFERS]
        self.assertTrue(whats[0].startswith("the row is ('start-a--someone-else-seed0', 'someone/else', 0, 'start-a'), the file says"))
        self.assertEqual(whats[1], "game.Civ5Save: does not begin as a save of the game does")

    def test_what_is_no_recording_is_refused(self):
        junk = self.dir / "junk.zip"
        junk.write_text("not a zip")
        with self.assertRaisesRegex(rec.Refused, "not a readable zip"):
            rec.check(junk, self.starts)
        with zipfile.ZipFile(junk, "w") as z:
            z.writestr("other.txt", "x")
        with self.assertRaisesRegex(rec.Refused, "not a recording"):
            rec.check(junk, self.starts)


class FakeGame:
    def __init__(self, seen, loaded=None):
        self.seen, self.loaded = seen, loaded or {"ok": True}
        self.did: list[str] = []
        self.in_saves: list[str] = []

    def load_save(self, name):
        self.did.append(f"load {name}")
        self.in_saves = sorted(p.name for p in self.saves.iterdir())
        return self.loaded

    def q(self, code):
        self.did.append("read" if code == run.READ else code)
        return self.seen


class InTheGame(Files):
    def beside(self, seen, row=None, loaded=None, turns=None, **kw):
        row = row or a_row(**kw)
        manifest = self.pack(row)[1]
        g = FakeGame(seen, loaded)
        g.saves = self.saves
        found = rec.check_in_game(g, manifest, row, SAVE, self.saves, leave=lambda g: g.did.append("leave"), turns=turns,
                                  hand_back=lambda g, seat: g.did.append(f"wait for seat {seat}"))
        return g, found

    def test_the_save_is_loaded_read_and_left_and_its_copy_removed(self):
        g, found = self.beside(game_read())
        name = f"recording-check-{rec.sha256(SAVE)[:12]}"
        self.assertEqual(g.did, [f"load {name}", "read", "leave"])
        self.assertIn(f"{name}.Civ5Save", g.in_saves)
        self.assertFalse((self.saves / f"{name}.Civ5Save").exists())
        self.assertEqual([state for state, _ in found], [rec.OK, rec.OK, rec.OK])
        self.assertEqual(found[-1][1], "the game reads as the row says: turn 10, the seat's 10 indicators (score 150), 2 players' scores")

    def test_a_save_the_engine_was_playing_is_left_only_when_the_seat_is_handed_back(self):
        """Live 2026-11-23: a duel's saves taken under the engine, loaded, read and left at once, killed the game
        process three times of three; left after the engine's one turn, never."""
        seen = game_read()
        seen["auto"] = 1
        g, found = self.beside(seen)
        self.assertEqual(g.did[1:], ["read", "wait for seat 0", "leave"])
        self.assertEqual([state for state, _ in found], [rec.OK, rec.OK, rec.OK])

    def test_the_loaded_game_is_set_beside_the_game_files_last_line_every_player(self):
        turns = a_game_file(self.dir / "g.jsonl").read_bytes()
        _g, found = self.beside(game_read(), turns=turns)
        self.assertEqual(found[-1], (rec.OK, "the game reads as game.jsonl ends: 2 players, 10 indicators each"))
        seen = game_read()
        seen["players"][1]["gold"] = 77
        _g, found = self.beside(seen, turns=turns)
        self.assertEqual([what for state, what in found if state == rec.DIFFERS], ["player 1 (civ1), gold: game 77, game.jsonl 10"])
        (self.saves / "over.Civ5Save").write_bytes(SAVE)
        row = a_row(end_reason="game_won", game_over_save="over", game_over_save_turn=8)
        del row["end_save"]
        _g, found = self.beside(game_read(turn=8), row=row, turns=turns)
        self.assertEqual(found[-1], (rec.UNKNOWN, "the saved game (turn 8) is not of the moment game.jsonl ends on (turn 10): "
                                                  "the two are not set beside each other"))

    def test_a_dead_civilization_is_set_beside_its_line_by_what_the_line_holds(self):
        """Live 2026-11-24 (America, dead in the game Poland wins from `small-king-poland-a-t200`): the game file
        writes a dead civilization without figures, the game still counts its technologies and its gold, and
        `check --load` named nine differences in a recording that was whole."""
        lines = a_game_file(self.dir / "g.jsonl").read_bytes().splitlines()
        last = json.loads(lines[-1])
        last["world"]["players"] = [p if p["id"] != 1 else {"id": 1, "team": 1, "human": False, "alive": False, "score": 0}
                                    for p in last["world"]["players"]]
        turns = b"\n".join([*lines[:-1], json.dumps(last).encode()]) + b"\n"
        seen = game_read()
        seen["players"][1].update(alive=False, score=0)
        _g, found = self.beside(seen, turns=turns)
        self.assertEqual([what for _state, what in found if "game.jsonl" in what],
                         ["the game reads as game.jsonl ends: 2 players, 10 indicators each"])
        seen = game_read()
        seen["players"][1].update(alive=False, score=5)
        _g, found = self.beside(seen, turns=turns)
        self.assertEqual([what for _state, what in found if "game.jsonl" in what],
                         ["player 1 (civ1), score: game 5, game.jsonl 0"])

    def test_every_figure_that_differs_is_named(self):
        seen = game_read(turn=11, happiness=9)
        seen["players"][1]["score"] = 311
        _g, found = self.beside(seen)
        self.assertEqual([what for state, what in found if state == rec.DIFFERS],
                         ["turn: row 10, game 11", "the seat's happiness: row 10, game 9",
                          "player 1: row civ1 alive True score 310, game civ1 alive True score 311"])

    def test_a_save_that_does_not_load_is_said_and_its_copy_removed(self):
        g, found = self.beside(game_read(), loaded={"ok": False, "err": "no such save"})
        self.assertEqual(found, [(rec.DIFFERS, "the saved game did not load: no such save")])
        self.assertEqual(g.did, [g.did[0]])
        self.assertEqual(sorted(p.name for p in self.saves.iterdir()), ["start-a--codex-x-seed0-end.Civ5Save", "start-a.Civ5Save"])

    def test_another_game_build_differs_and_a_run_that_named_none_is_not_checked(self):
        _g, found = self.beside(game_read(build="1.0.3.144"))
        self.assertIn((rec.DIFFERS, "game build: the run was played on 1.0.3.279(130961), this game is 1.0.3.144"), found)
        row = a_row()
        del row["harness"]
        _g, found = self.beside(game_read(), row=row)
        self.assertIn((rec.UNKNOWN, "the run names no game build; this game is 1.0.3.279(130961)"), found)

    def test_a_save_from_before_the_rows_read_is_loaded_and_its_figures_not_compared(self):
        (self.saves / "over.Civ5Save").write_bytes(SAVE)
        row = a_row(end_reason="game_won", game_over_save="over", game_over_save_turn=8)
        del row["end_save"]
        _g, found = self.beside(game_read(turn=8, happiness=0), row=row)
        self.assertEqual([state for state, _ in found], [rec.OK, rec.OK, rec.OK, rec.UNKNOWN])
        self.assertIn("the row was read on turn 10, after the save", found[-1][1])
        row["game_over_save_from"] = "the last quick save of the run, from before the end"
        row["game_over_save_turn"] = None
        _g, found = self.beside(game_read(turn=8), row=row)
        self.assertEqual(found[-1][0], rec.UNKNOWN)


class Commands(Files):
    def go(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = rec.main([str(a) for a in argv])
        return status, out.getvalue(), err.getvalue()

    def rows(self, *rows):
        file = self.dir / "board" / "rows.jsonl"
        file.parent.mkdir(exist_ok=True)
        file.write_text("".join(json.dumps(r) + "\n" for r in rows))
        return file

    def test_pack_writes_every_run_of_a_rows_file_beside_it_and_says_which_it_could_not(self):
        lost = a_row(run=1, end_reason="turns_not_played")
        del lost["end_save"]
        rows = self.rows(a_row(), lost)
        status, out, err = self.go("pack", rows, "--ledger", self.ledger, "--saves", self.saves)
        self.assertEqual(status, 2)
        packed = rows.parent / "recordings" / "start-a--codex-x-seed0.recording.zip"
        self.assertIn(f"{packed}\n  {packed.stat().st_size} bytes, sha256 {rec.sha256(packed.read_bytes())}", out)
        self.assertIn("start-a, codex/x, seed 1: not packed: the run kept no saved game", err)
        self.assertEqual([p.name for p in packed.parent.iterdir()], [packed.name])

    def test_pack_takes_one_player_and_one_seed(self):
        (self.saves / "other-end.Civ5Save").write_bytes(SAVE)
        rows = self.rows(a_row(), a_row(player="grok/y", end_save="other-end"))
        status, _out, _err = self.go("pack", rows, "--player", "grok/y", "--seed", 0, "--out", self.out,
                                     "--ledger", self.ledger, "--saves", self.saves)
        self.assertEqual((status, [p.name for p in self.out.iterdir()]), (0, ["start-a--grok-y-seed0.recording.zip"]))
        self.assertEqual(self.go("pack", rows, "--player", "nobody", "--ledger", self.ledger, "--saves", self.saves)[0], 2)

    def test_check_exits_0_when_nothing_differs_1_when_something_does_2_for_what_it_cannot_read(self):
        good = self.pack()[0]
        status, out, _err = self.go("check", good, "--starts", self.starts)
        self.assertEqual(status, 0)
        self.assertIn("=> nothing differs; the saved game was not loaded (--load)", out)
        bad = self.dir / "bad.recording.zip"
        bad.write_bytes(good.read_bytes())
        self.rewritten(bad, game__Civ5Save=SAVE + b"!")
        status, out, _err = self.go("check", good, bad, "--starts", self.starts)
        self.assertEqual(status, 1)
        self.assertIn("=> 1 differ", out)
        junk = self.dir / "junk.zip"
        junk.write_text("x")
        status, _out, err = self.go("check", junk, good, "--starts", self.starts)
        self.assertEqual(status, 2)
        self.assertIn("refused:", err)


if __name__ == "__main__":
    unittest.main()
