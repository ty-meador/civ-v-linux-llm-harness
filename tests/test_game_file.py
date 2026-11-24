"""harness/spectator/game_file.py: a game as one file, one JSON line a turn, with no game and against a fake one.

Live 2026-11-23 (docs/BENCHMARK.md, "The game file"): the built-in AI's ten turns on the duel wrote thirteen lines,
the game, the start, turns 1 to 10 and the end, while the runner's own poll, every three seconds, saw turns 1, 5, 9
and 10; the same seed played without the handler ended on the same figures; the capture took 3 ms a turn there and
no name of the game's API was missing.
"""
from __future__ import annotations

import json
import re
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from harness.spectator import game_file as G

MAP = {"ok": True, "w": 2, "h": 2, "wrap": True, "key": "2x2:7", "legend": {},
       "layers": {"terrain": ["GC", "PO"], "elev": ["..", ".."], "feature": ["..", ".."], "river": ["..", ".."],
                  "resource": ["..", ".."]}}


def world(turn: int, score: int = 10, **more) -> dict:
    return {"turn": turn, "kind": "turn", "active": 0, "at": 1000 + turn, "cities": [], "units": [], "events": [],
            "players": [{"id": 0, "alive": True, "human": True, "team": 0, "score": score, "cities": 1, "techs": ["POTTERY"]},
                        {"id": 22, "alive": True, "human": False, "team": 22, "score": 3, "minor": True, "influence": []},
                        {"id": 63, "alive": True, "human": False, "team": 63, "score": 0, "barb": True}],
            "owners": {"rows": ["A.", ".."], "legend": {"A": 0}}, "fog": [], "map_key": "2x2:7", **more}


class FakeGame:
    """The game's side of the three calls, for `game_file.Q.query`: a Lua state with the handler in it or not, the
    worlds it holds, and the game's own facts."""

    def __init__(self, keep: int = G.KEEP):
        self.state, self.installed, self.seq, self.ring, self.turn, self.keep = 1, False, 0, [], 0, keep
        self.map = dict(MAP)
        self.asked: list[str] = []
        self.down = False
        self.seats = None

    def put(self, kind: str) -> int:
        self.seq += 1
        self.ring.append({"seq": self.seq, "kind": kind, "turn": self.turn,
                          "json": json.dumps({**world(self.turn, score=10 + self.turn), "kind": kind})})
        del self.ring[:-self.keep]
        return self.seq

    def play(self, turns: int = 1) -> None:
        for _ in range(turns):
            self.turn += 1
            if self.installed:
                self.put("turn")

    def load(self, turn: int) -> None:
        """Another Lua state: the game was loaded again."""
        self.state, self.installed, self.seq, self.ring, self.turn = self.state + 1, False, 0, [], turn

    def query(self, _client, code: str, timeout=None):
        if self.down:
            raise OSError("no InGame state")
        if "GameEvents.PlayerDoTurn" in code:
            self.asked.append("install")
            self.installed = True
            self.seats = re.search(r"R\.also = \d+, \d+, \{ (.*?) \}", code).group(1)
            return {"ok": True, "id": f"state{self.state}", "seq": self.seq, "turn": self.turn, "version": G.RECORDER}
        if "MinorCivTraits" in code:
            self.asked.append("facts")
            return {"turn": self.turn, "handicap": "HANDICAP_KING", "speed": "GAMESPEED_QUICK", "start_turn": 0,
                    "victories": {"VICTORY_DOMINATION": True}, "options": [], "eras": ["ERA_ANCIENT", "ERA_CLASSICAL"],
                    "players": [{"id": 0, "team": 0, "name": "Augustus", "civ": "Rome", "leader": "LEADER_AUGUSTUS",
                                 "civilization": "CIVILIZATION_ROME", "color": [1, 2, 3], "color2": [4, 5, 6]},
                                {"id": 22, "team": 22, "name": "Wellington", "civ": "City State", "minor": True},
                                {"id": 63, "team": 63, "name": "Barbarians", "civ": "Barbarians", "barb": True}]}
        if "Map.IsWrapX()" in code:
            self.asked.append("map")
            return self.map
        if not self.installed:
            return {"installed": False}
        if "R.put(" in code:
            kind = re.search(r'R\.put\("(\w+)"', code).group(1)
            self.asked.append(kind)
            return {"installed": True, "id": f"state{self.state}", "seq": self.put(kind), "error": ""}
        self.asked.append("fetch")
        since = int(re.search(r"e\.seq > (\d+)", code).group(1))
        return {"installed": True, "id": f"state{self.state}", "seq": self.seq, "errors": 0, "error": "", "turn": self.turn,
                "missing": [], "rows": [dict(e) for e in self.ring if e["seq"] > since][:2]}      # two a fetch: a reply has a size


class WithAGame(unittest.TestCase):
    def setUp(self):
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.game = FakeGame()
        self.enterContext(mock.patch.object(G.Q, "query", self.game.query))

    def lines(self, path) -> list[dict]:
        return [row for _offset, _raw, row in G.read(path)]

    def kinds(self, path) -> list[tuple]:
        return [(row["kind"], row.get("turn")) for row in self.lines(path)]


class TheLua(unittest.TestCase):
    """The text sent to the game. The game's own API is not here: what is run is the handler's bookkeeping, with the
    capture replaced."""

    FILLED = dict(id="abc", version=G.RECORDER, keep=3, seats="0, 4", since=0, limit=G.REPLY_BYTES, kind="start")

    def setUp(self):
        try:
            import lupa
        except ImportError:
            self.skipTest("lupa is not installed")
        self.lua = lupa.LuaRuntime()
        self.lua.execute("""
            turn, handlers = 7, {}
            Game = { GetGameTurn = function() return turn end }
            GameInfo = setmetatable({}, { __index = function() return function() return function() return nil end end end })
            GameEvents = { PlayerDoTurn = { Add = function(f) handlers[#handlers + 1] = f end } }
            function __hjson(v) return "world of turn " .. tostring(v.turn) end
            function run(src) local f, err = load(src) if not f then error(err) end return f() end
        """)

    def run_lua(self, name, **values):
        return self.lua.globals().run(G.fill(getattr(G, name), **{**self.FILLED, **values}))

    def test_every_chunk_compiles(self):
        check = self.lua.eval("function(src) local f, err = load(src) return err end")
        for name in ("INSTALL", "FETCH", "NOW", "GAME"):
            self.assertIsNone(check(G.fill(getattr(G, name), **self.FILLED)), name)

    def test_one_world_a_turn_at_the_turns_first_player_and_no_more_than_the_game_is_told_to_hold(self):
        made = self.run_lua("INSTALL")
        self.assertEqual((made["id"], made["seq"], made["turn"]), ("abc", 0, 7))
        self.lua.execute("SpectatorTurns.capture = function(kind, first) return { turn = turn, kind = kind, first = first } end")
        g = self.lua.globals()
        handler = g.handlers[1]
        handler(3)                                        # a later player of the turn the handler went in on: nothing
        self.assertEqual(self.run_lua("FETCH")["seq"], 0)
        for turn in (8, 9, 10, 11):
            g.turn = turn
            handler(0)
            handler(1)                                    # the turn's other players add nothing
        reply = self.run_lua("FETCH")
        self.assertEqual(reply["seq"], 4)
        self.assertEqual([(e["seq"], e["kind"], e["turn"], e["json"]) for e in reply["rows"].values()],
                         [(2, "turn", 9, "world of turn 9"), (3, "turn", 10, "world of turn 10"), (4, "turn", 11, "world of turn 11")])
        self.assertEqual([e["seq"] for e in self.run_lua("FETCH", since=3)["rows"].values()], [4])

    def test_sent_again_it_keeps_its_count_and_its_one_handler_and_a_world_asked_for_is_kept_with_the_turns(self):
        self.run_lua("INSTALL")
        self.lua.execute("SpectatorTurns.capture = function(kind) return { turn = turn, kind = kind } end")
        g = self.lua.globals()
        self.assertEqual(self.run_lua("NOW")["seq"], 1)
        again = self.run_lua("INSTALL", id="another")
        self.assertEqual((again["id"], again["seq"], len(g.handlers)), ("abc", 1, 1))
        self.assertEqual([e["kind"] for e in self.run_lua("FETCH")["rows"].values()], ["start"])

    def test_a_capture_that_fails_is_counted_and_said_and_the_game_goes_on(self):
        self.run_lua("INSTALL")
        self.lua.execute("SpectatorTurns.capture = function() error('no such thing') end")
        g = self.lua.globals()
        g.turn = 8
        g.handlers[1](0)
        reply = self.run_lua("FETCH")
        self.assertEqual((reply["seq"], reply["errors"]), (0, 1))
        self.assertIn("no such thing", reply["error"])

    def test_a_game_without_the_handler_or_with_another_version_of_it_says_so(self):
        self.assertFalse(self.run_lua("FETCH")["installed"])
        self.assertFalse(self.run_lua("NOW")["installed"])
        self.run_lua("INSTALL")
        self.assertFalse(self.run_lua("FETCH", version=G.RECORDER + 1)["installed"])


class TheFile(unittest.TestCase):
    def setUp(self):
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.path = self.dir / "game.jsonl"

    def written(self, turns=(1, 2, 3)) -> G.GameFile:
        f = G.GameFile(self.path)
        f.append("game", {"format": G.FORMAT, "key": "2x2-k", "game": {"players": []}, "map": MAP}, t=100.0)
        f.append("start", {"turn": 0, "world": {"players": []}}, t=100.5)
        for turn in turns:
            f.append("turn", {"turn": turn, "world": {"players": []}}, t=100.0 + turn)
        return f

    def rows(self):
        return [(raw, row) for _offset, raw, row in G.read(self.path)]

    def test_every_line_is_numbered_and_names_the_hash_of_the_line_before(self):
        self.written()
        rows = self.rows()
        self.assertEqual([row["line"] for _raw, row in rows], [1, 2, 3, 4, 5])
        self.assertEqual([row["prev"] for _raw, row in rows], [None, *(G.digest(raw) for raw, _row in rows[:-1])])
        self.assertEqual(G.problems(rows), [])
        self.assertEqual(rows[0][0], G.dumps(rows[0][1]))            # as written is as any machine writes it

    def test_no_line_is_written_with_a_time_before_the_line_before_it(self):
        f = self.written(turns=())
        f.append("turn", {"turn": 1, "world": {}}, t=99.0)           # the game's clock, in whole seconds, behind ours
        self.assertEqual([row["t"] for _raw, row in self.rows()], [100.0, 100.5, 100.5])

    def test_a_file_that_is_there_is_gone_on_with_and_a_half_line_at_its_end_is_cut_off(self):
        self.written()
        whole = self.path.read_bytes()
        self.path.write_bytes(whole + b'{"line":6,"kind":"tu')
        f = G.GameFile(self.path)
        self.assertEqual((f.lines, f.header["key"], f.bytes, self.path.read_bytes()), (5, "2x2-k", len(whole), whole))
        f.append("turn", {"turn": 4, "world": {"players": []}}, t=104.0)
        self.assertEqual(G.problems(self.rows()), [])
        self.assertEqual([row["line"] for _raw, row in self.rows()], [1, 2, 3, 4, 5, 6])

    def test_a_line_changed_taken_out_or_out_of_place_is_said(self):
        self.written()
        rows = self.rows()
        changed = [(raw.replace(b'"turn":2', b'"turn":7'), row) if row.get("turn") == 2 else (raw, row) for raw, row in rows]
        self.assertEqual(G.problems(changed), ["line 5 does not follow the line before it (prev)"])
        self.assertEqual(G.problems(rows[:2] + rows[3:]),
                         ["line 3 says it is line 4", "line 3 does not follow the line before it (prev)",
                          "line 4 says it is line 5"])
        self.assertIn("line 1 is of kind 'start'", G.problems(rows[1:]))
        self.assertEqual(G.problems([]), ["no line"])

    def test_the_game_as_it_stands_after_a_load_is_the_turns_played_last(self):
        def row(kind, turn, n):
            return {"kind": kind, "turn": turn, "n": n}
        rows = [row("start", 50, 1), row("turn", 51, 2), row("turn", 52, 3), row("turn", 53, 4),
                row("start", 51, 5),                       # loaded again, the save of turn 51
                row("turn", 52, 6), row("turn", 53, 7), row("end", 53, 8)]
        self.assertEqual([r["n"] for r in G.standing(rows)], [1, 2, 5, 6, 7, 8])
        self.assertEqual([r["n"] for r in G.standing(rows[:4] + [row("turn", 52, 9)])], [1, 2, 9])

    def test_a_line_by_its_number_is_one_seek_and_the_index_follows_the_file_as_it_grows(self):
        f = self.written()
        index = G.Index(self.path)
        self.assertEqual([(r["line"], r["kind"], r.get("turn")) for r in index.rows],
                         [(1, "game", None), (2, "start", 0), (3, "turn", 1), (4, "turn", 2), (5, "turn", 3)])
        self.assertEqual(json.loads(index.line(4))["turn"], 2)
        self.assertIsNone(index.line(6))
        self.assertIsNone(index.line(0))
        f.append("turn", {"turn": 4, "world": {"players": [{"id": 0, "score": 77, "cities": 2, "techs": ["A"]},
                                                         {"id": 22, "score": 5, "minor": True}]}}, t=104.0)
        self.assertEqual(index.refresh(), 6)
        self.assertEqual(index.rows[-1]["players"], {"0": {"score": 77, "cities": 2}})
        self.assertEqual(json.loads(index.line(6))["turn"], 4)


class ThePagesStream(unittest.TestCase):
    def test_a_file_is_the_map_then_a_snapshot_a_line_with_each_players_name_and_colours_back_on_its_row(self):
        head = {"kind": "game", "t": 100.7, "map": MAP,
                "game": {"players": [{"id": 0, "name": "Augustus", "civ": "Rome", "color": [1, 2, 3], "leader": "LEADER_AUGUSTUS"},
                                     {"id": 22, "name": "Wellington", "civ": "City State", "minor": True}]}}
        def as_written(turn):                     # the turn is the line's own, not the world's
            return {k: v for k, v in world(turn).items() if k not in ("turn", "kind", "at")}
        lines = [head, {"kind": "start", "turn": 0, "t": 100.7, "world": as_written(0)},
                 {"kind": "turn", "turn": 1, "t": 100, "world": as_written(1)},   # the game's clock behind ours
                 {"kind": "turn", "turn": 2, "t": 130, "world": as_written(2)}]
        calls = [{"t": 90.0, "seat": 0, "tool": "state"}, {"t": 120.0, "seat": 0, "tool": "order"}, {"t": 130.0, "seat": 0, "tool": "turn"}]
        events = G.events_of(lines, calls)
        self.assertEqual([(e["seq"], e["type"], e["t"]) for e in events],
                         [(1, "hello", 100.7), (2, "snapshot", 100.7), (3, "snapshot", 100.7), (4, "call", 100.7),
                          (5, "call", 120.0), (6, "snapshot", 130), (7, "call", 130.0)])
        self.assertEqual(events[0]["data"], {"map": MAP})
        self.assertEqual([e["data"]["turn"] for e in events if e["type"] == "snapshot"], [0, 1, 2])
        seat, minor, barb = events[1]["data"]["players"]
        self.assertEqual((seat["name"], seat["civ"], seat["color"], seat["human"], seat["minor"], seat["barb"]),
                         ("Augustus", "Rome", [1, 2, 3], True, False, False))
        self.assertNotIn("leader", seat)
        self.assertEqual((minor["name"], minor["minor"], barb["barb"], barb.get("name")), ("Wellington", True, True, None))
        from harness.spectator import snapshot
        self.assertTrue(snapshot.valid(events[1]["data"]))

    def test_an_empty_object_comes_over_the_wire_as_a_list_and_is_put_right(self):
        tidy = G.tidy({"fog": [], "units": [], "players": [{"influence": [], "great_people": [], "techs": []}],
                       "owners": {"rows": [], "legend": []}})
        self.assertEqual(tidy, {"fog": {}, "units": [], "players": [{"influence": {}, "great_people": {}, "techs": []}],
                                "owners": {"rows": [], "legend": {}}})


class TheRecorder(WithAGame):
    def test_it_begins_with_the_handler_the_game_and_where_the_game_stands(self):
        path = self.dir / "run-game.jsonl"
        rec = G.Recorder(object(), path=path, seats=[0], made_with={"harness": "2.20.0"}, run={"save": "start-a", "seed": 3})
        self.assertEqual(rec.step(), 1)
        self.assertEqual(self.game.asked[:3], ["install", "facts", "map"])
        self.assertEqual(self.game.seats, "0")
        head, start = self.lines(path)
        self.assertEqual((head["line"], head["kind"], head["format"], head["key"], head["map"]), (1, "game", G.FORMAT, rec.key, MAP))
        self.assertEqual((head["written_by"], head["run"]), ({"recorder": G.RECORDER, "harness": "2.20.0"}, {"save": "start-a", "seed": 3}))
        self.assertEqual(head["game"]["players"][0]["name"], "Augustus")
        self.assertEqual(head["game"]["eras"], ["ERA_ANCIENT", "ERA_CLASSICAL"])
        self.assertEqual((start["line"], start["kind"], start["turn"], start["t"] >= head["t"]), (2, "start", 0, True))
        self.assertEqual(start["world"]["fog"], {})
        for gone in ("kind", "turn", "at"):
            self.assertNotIn(gone, start["world"])
        self.assertRegex(rec.key, r"^2x2-[0-9a-f]{12}$")

    def test_every_turn_the_game_took_is_a_line_however_many_passed_between_two_looks(self):
        path = self.dir / "g.jsonl"
        rec = G.Recorder(object(), path=path)
        rec.step()
        self.assertEqual(rec.step(), 0)
        self.game.play(5)                         # five turns between two looks; a fetch brings two at a time
        self.assertEqual(rec.step(), 5)
        self.assertEqual(self.kinds(path), [("game", None), ("start", 0), *(("turn", t) for t in range(1, 6))])
        self.assertEqual([row["world"]["players"][0]["score"] for row in self.lines(path)[2:]], [11, 12, 13, 14, 15])
        said = rec.end()
        self.assertEqual(self.kinds(path)[-1], ("end", 5))
        self.assertEqual(said, {"file": str(path), "lines": 8, "bytes": path.stat().st_size, "key": rec.key,
                                "start": 1, "turn": 5, "end": 1})
        self.assertEqual(G.problems((raw, row) for _o, raw, row in G.read(path)), [])

    def test_worlds_the_game_let_go_of_before_they_were_fetched_are_counted_in_the_line_after_them(self):
        self.game.keep = 3
        path = self.dir / "g.jsonl"
        rec = G.Recorder(object(), path=path)
        rec.step()
        self.game.play(5)
        rec.step()
        self.assertEqual(self.kinds(path)[2:], [("turn", 3), ("turn", 4), ("turn", 5)])
        self.assertEqual((self.lines(path)[2]["missed"], rec.said()["missed"]), (2, 2))

    def test_a_game_loaded_again_gets_the_handler_again_and_a_line_for_where_it_stands(self):
        path = self.dir / "g.jsonl"
        rec = G.Recorder(object(), path=path)
        rec.step()
        self.game.play(3)
        rec.step()
        self.game.load(turn=2)                    # the save of turn 2, a new Lua state with no handler
        self.assertEqual(rec.step(), 0)           # this look finds the handler gone
        self.assertEqual(rec.step(), 1)           # the next puts it back
        self.game.play(2)
        rec.step()
        self.assertEqual(self.kinds(path), [("game", None), ("start", 0), ("turn", 1), ("turn", 2), ("turn", 3),
                                            ("start", 2), ("turn", 3), ("turn", 4)])
        self.assertEqual([(r["kind"], r["turn"], r["line"]) for r in G.standing(self.lines(path)[1:])],
                         [("start", 0, 2), ("turn", 1, 3), ("turn", 2, 4), ("start", 2, 6), ("turn", 3, 7), ("turn", 4, 8)])
        self.assertEqual(G.problems((raw, row) for _o, raw, row in G.read(path)), [])

    def test_a_folder_holds_a_file_for_each_game_gone_on_with_by_a_later_recorder(self):
        rec = G.Recorder(object(), folder=self.dir / "games")
        rec.step()
        first = rec.file.path
        self.assertRegex(first.name, G.NAME)
        self.game.play(1)
        rec.step()
        later = G.Recorder(object(), folder=self.dir / "games")
        later.step()
        self.assertEqual((later.file.path, [k for k, _t in self.kinds(first)]), (first, ["game", "start", "turn", "start"]))
        self.game.load(turn=0)
        self.game.map = {**MAP, "key": "2x2:8"}   # another game under the recorder
        rec.step()
        rec.step()
        self.assertNotEqual(rec.file.path, first)
        self.assertEqual(sorted(p.name for p in (self.dir / "games").iterdir()), sorted([first.name, rec.file.path.name]))

    def test_one_file_is_one_game(self):
        path = self.dir / "g.jsonl"
        G.Recorder(object(), path=path).step()
        self.game.map = {**MAP, "key": "2x2:8"}
        with self.assertRaisesRegex(ValueError, "the file of another game"):
            G.Recorder(object(), path=path).step()
        with self.assertRaises(ValueError):
            G.Recorder(object())
        with self.assertRaises(ValueError):
            G.Recorder(object(), path=path, folder=self.dir)

    def test_no_game_is_no_file_and_the_end_never_raises(self):
        self.game.down = True
        rec = G.Recorder(object(), path=self.dir / "g.jsonl")
        with self.assertRaises(G.NoGame):
            rec.step()
        self.assertFalse((self.dir / "g.jsonl").exists())
        said = rec.end()
        self.assertEqual((said["lines"], said["file"]), (0, None))
        self.assertIn("NoGame", said["error"])

    def test_a_recorder_at_work_looks_by_itself_and_ends_with_the_world_as_it_is(self):
        path = self.dir / "g.jsonl"
        rec = G.Recorder(object(), path=path)
        rec.begin()
        end = G.record(rec, every=0.01)
        self.game.play(3)
        deadline = time.time() + 5
        while rec.written["turn"] < 3 and time.time() < deadline:
            time.sleep(0.01)
        said = end()
        self.assertEqual((said["turn"], said["end"], self.kinds(path)[-1]), (3, 1, ("end", 3)))


if __name__ == "__main__":
    unittest.main()
