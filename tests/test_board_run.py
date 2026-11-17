"""scripts/board_run.py against a fake Game: what it refuses, when a run ends, what a row says, and the notebook
an entrant's command plays with.

Live 2026-11-16 (docs/BENCHMARK.md, "Autoplay, checked live"): `Game.SetAIAutoPlay` on a duel whose unused slots
were closed made the seat the observer and destroyed its Settler and Warrior in the same call, with no error; a
win did not stop a run; and after the seat died the game played turns by itself. The runner refuses the first
before it changes anything, and for the other two it watches the run and leaves the game itself.
"""
from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("board_run", ROOT / "scripts" / "board_run.py")
board_run = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(board_run)


def player(pid, human=False, alive=True, **kw):
    row = {"id": pid, "civ": f"civ{pid}", "alive": alive, "human": human}
    row.update({k: 10 for k in board_run.INDICATORS})
    row.update(kw)
    return row


def read(turn=242, slots=(3, 1, 4, 4), players=None, winner=-1, victory=""):
    return {"turn": turn, "state": 0, "winner": winner, "victory": victory, "auto": 0, "active": 0, "max_turns": 0,
            "handicap": "HANDICAP_EMPEROR", "speed": "GAMESPEED_QUICK", "slots": list(slots),
            "players": players or [player(0, human=True, score=100), player(1, score=300)]}


class FakeGame:
    """load_save, q and leave_to_main_menu, with the game's answers scripted: `reads` for the two full reads,
    `handed` for the reply to the autoplay call, `polls` for the watch."""

    def __init__(self, reads, polls=(), handed=None, loaded=None):
        self.reads, self.polls = list(reads), list(polls)
        self.handed = handed or {"auto": 10, "active": 2, "slot": 1, "human": False, "units": 5, "cities": 2}
        self.loaded = loaded or {"ok": True, "turn": 242}
        self.sent: list[str] = []
        self.left = 0

    def load_save(self, name):
        self.sent.append(f"load {name}")
        return self.loaded

    def q(self, code):
        self.sent.append(code)
        if "SetAIAutoPlay" in code:
            return self.handed
        if "players = {}" in code:
            return self.reads.pop(0)
        if "return {burn" in code:
            return {"burn": 0}
        return self.polls.pop(0)

    def leave_to_main_menu(self):
        self.left += 1
        return {"ok": True}


class Clock:
    def __init__(self):
        self.t = 0.0

    def sleep(self, s):
        self.t += s

    def __call__(self):
        return self.t


def poll(turn, auto, winner=-1, alive=True, turn_active=True):
    return {"turn": turn, "auto": auto, "winner": winner, "state": 0 if winner < 0 else 2, "alive": alive, "active": 2,
            "turn_active": turn_active}


def run(g, **kw):
    clock = Clock()
    return board_run.run_once(g, "board", 10, sleep=clock.sleep, clock=clock, **kw)


class Refusals(unittest.TestCase):
    def test_a_board_with_no_observer_slot_is_refused_before_the_engine_is_asked_anything(self):
        g = FakeGame([read(slots=(3, 1, 2, 2))])
        with self.assertRaisesRegex(board_run.Refused, "observer slot"):
            run(g)
        self.assertFalse(any("SetAIAutoPlay" in s for s in g.sent), "the call that destroys the seat was sent")
        self.assertEqual(g.left, 1, "the loaded board was left on screen")

    def test_the_seats_own_slot_does_not_count_as_the_observer_slot(self):
        with self.assertRaises(board_run.Refused):
            board_run.check_observer_slot(read(slots=(4, 1, 2)), 0)
        board_run.check_observer_slot(read(slots=(3, 1, 4)), 0)

    def test_two_human_seats_are_refused(self):
        g = FakeGame([read(players=[player(0, human=True), player(1, human=True)])])
        with self.assertRaisesRegex(board_run.Refused, "2 human seats"):
            run(g)
        self.assertEqual(g.left, 1)

    def test_a_seat_that_is_not_the_boards_human_is_refused(self):
        with self.assertRaisesRegex(board_run.Refused, "seat 1 is not"):
            board_run.find_seat(read(), 1)
        self.assertEqual(board_run.find_seat(read(), None), 0)

    def test_a_save_that_does_not_load_is_refused(self):
        g = FakeGame([], loaded={"ok": False, "err": "no save named 'board'"})
        with self.assertRaisesRegex(board_run.Refused, "no save named"):
            run(g)


class Runs(unittest.TestCase):
    def test_a_window_played_out_gives_the_seat_before_and_after(self):
        after = read(turn=252, players=[player(0, human=True, score=140, cities=3), player(1, score=310)])
        g = FakeGame([read(), after], polls=[poll(243, 9), poll(243, 9), poll(251, 1), poll(252, 0)])
        said: list[str] = []
        row = run(g, say=said.append)
        self.assertEqual(row["end_reason"], "window_played")
        self.assertEqual((row["turns_played"], row["seat"], row["handicap"]), (10, 0, "HANDICAP_EMPEROR"))
        self.assertEqual((row["start"]["values"]["score"], row["end"]["values"]["score"]), (100, 140))
        self.assertEqual(row["end"]["values"]["cities"], 3)
        self.assertEqual((row["end"]["place"], row["end"]["of"]), (2, 2))
        self.assertEqual(row["seconds"], 12.0)
        self.assertEqual(len(said), 3, "one line a new turn, none for a poll that saw the same turn")
        self.assertEqual(g.left, 1, "the game was not left for the main menu")
        json.dumps(row)

    def test_the_draws_come_before_the_handover_and_the_seat_is_the_one_found(self):
        g = FakeGame([read(), read(turn=252)], polls=[poll(252, 0)])
        run(g, burn=34)
        start = next(s for s in g.sent if "SetAIAutoPlay" in s)
        self.assertIn("for _ = 1, 34 do Game.Rand(", start)
        self.assertLess(start.index("Game.Rand("), start.index("Game.SetAIAutoPlay(10, 0)"))

    def test_a_dead_seat_ends_the_run_though_the_count_is_not_out(self):
        after = read(turn=246, winner=1, victory="VICTORY_DOMINATION",
                     players=[player(0, human=True, alive=False, score=0), player(1, score=300)])
        g = FakeGame([read(), after], polls=[poll(244, 8), poll(246, 6, winner=1, alive=False), poll(250, 2)])
        row = run(g)
        self.assertEqual((row["end_reason"], row["win_turn"], row["victory"]), ("seat_dead", 246, "VICTORY_DOMINATION"))
        self.assertEqual((row["end"]["alive"], row["end"]["place"], row["end"]["share"]["score"]), (False, None, 0.0))
        self.assertEqual(len(g.polls), 1, "the run was watched on after the seat died")
        self.assertEqual(g.left, 1, "a game with no living human plays turns by itself until it is left")

    def test_a_win_ends_the_run_and_names_its_turn(self):
        after = read(turn=248, winner=1, victory="VICTORY_TIME")
        g = FakeGame([read(), after], polls=[poll(247, 5), poll(248, 4, winner=1), poll(249, 3)])
        row = run(g)
        self.assertEqual((row["end_reason"], row["win_turn"], row["winner"]), ("game_won", 248, 1))
        self.assertEqual(g.left, 1)

    def test_no_new_turn_for_the_stall_time_gives_the_run_up(self):
        g = FakeGame([read(), read(turn=243)], polls=[poll(243, 9)] * 6)
        row = run(g, poll=3.0, stall=10.0)
        self.assertEqual(row["end_reason"], "stalled")
        self.assertEqual(len(g.polls), 1, "polls 1 to 5 are 3 to 15 s after the turn was first seen at 3 s")
        self.assertEqual(g.left, 1)

    def test_a_seat_the_engine_did_not_take_is_said_and_the_game_is_left(self):
        g = FakeGame([read()], handed={"auto": 10, "active": 0, "slot": 4, "human": True, "units": 0, "cities": 0})
        row = run(g)
        self.assertEqual(row["end_reason"], "not_handed_over")
        self.assertEqual(row["handed_over"]["units"], 0)
        self.assertEqual(g.left, 1)


class Entrant(unittest.TestCase):
    """A command plays the seat between the two reads. The notebook is the one asked for while it plays and the
    one that stood on disk again afterwards."""

    def setUp(self):
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.nb = self.dir / "notes" / "game-seat0.json"
        self.nb.parent.mkdir()
        self.nb.write_text("standing")
        self.given = self.dir / "given.json"
        self.given.write_text("given")
        self.seen: list = []

    def command(self, g, writes="left by the entrant", raises=None):
        def run(cmd, timeout, check):
            g.sent.append("command")
            self.seen.append((cmd, self.nb.read_text() if self.nb.exists() else None, timeout, check))
            if raises:
                raise raises
            if writes is not None:
                self.nb.write_text(writes)
            return subprocess.CompletedProcess(cmd, 3)
        return run

    def go(self, g, **kw):
        clock = Clock()
        kw.setdefault("run", self.command(g))
        return board_run.run_entrant(g, "board", ["loop", "--turns", "10"], "codex/x", 10, sleep=clock.sleep, clock=clock,
                                     path_of=lambda _g, _seat: self.nb, **kw)

    def game(self, after=None, polls=None, **kw):
        after = after or read(turn=252, players=[player(0, human=True, score=150, turn_active=True), player(1, score=310)])
        return FakeGame([read(**kw), after], polls=polls or [poll(252, 0)])

    def test_the_row_is_the_two_reads_around_the_command(self):
        g = self.game()
        row = self.go(g, keep_notebook=self.dir / "rows" / "kept.json")
        self.assertEqual((row["entrant"], row["end_reason"], row["rc"], row["turns_played"]), ("codex/x", "window_played", 3, 10))
        self.assertEqual((row["start"]["values"]["score"], row["end"]["values"]["score"]), (100, 150))
        self.assertTrue(row["end"]["turn_active"])
        self.assertEqual(self.seen[0][0], ["loop", "--turns", "10"])
        self.assertIs(self.seen[0][3], False)
        order = ["read" if "players = {}" in s else s for s in g.sent if "players = {}" in s or s == "command"]
        self.assertEqual(order, ["read", "command", "read"])
        self.assertEqual(g.left, 1)
        json.dumps(row)

    def test_the_notebook_given_is_the_one_played_with_and_the_standing_one_comes_back(self):
        g = self.game()
        row = self.go(g, notebook=str(self.given), keep_notebook=self.dir / "rows" / "kept.json")
        self.assertEqual(self.seen[0][1], "given")
        self.assertEqual(self.nb.read_text(), "standing")
        self.assertEqual((self.dir / "rows" / "kept.json").read_text(), "left by the entrant")
        self.assertEqual(row["notebook_after"], str(self.dir / "rows" / "kept.json"))

    def test_none_is_a_seat_with_no_notebook(self):
        self.go(self.game(), notebook="none")
        self.assertEqual(self.seen[0][1], None)
        self.assertEqual(self.nb.read_text(), "standing")

    def test_with_no_word_on_it_the_standing_notebook_is_played_with_and_still_put_back(self):
        row = self.go(self.game())
        self.assertEqual((self.seen[0][1], row["notebook"]), ("standing", "standing"))
        self.assertEqual(self.nb.read_text(), "standing")

    def test_a_game_that_had_no_notebook_has_none_afterwards(self):
        self.nb.unlink()
        self.go(self.game(), keep_notebook=self.dir / "kept.json")
        self.assertFalse(self.nb.exists())
        self.assertEqual((self.dir / "kept.json").read_text(), "left by the entrant")

    def test_a_notebook_file_that_is_not_there_is_refused_before_the_command(self):
        g = self.game()
        with self.assertRaisesRegex(board_run.Refused, "no notebook file"):
            self.go(g, notebook=str(self.dir / "absent.json"))
        self.assertEqual((self.seen, g.left, self.nb.read_text()), ([], 1, "standing"))

    def test_the_deals_draws_are_taken_before_the_command(self):
        g = self.game()
        self.go(g, burn=34)
        burn = next(i for i, s in enumerate(g.sent) if "for _ = 1, 34 do Game.Rand(" in s)
        self.assertLess(burn, g.sent.index("command"))
        g = self.game()
        self.go(g)
        self.assertFalse(any("Game.Rand(" in s for s in g.sent), "deal 0 takes no draw")

    def test_a_command_that_does_not_end_is_given_up_and_the_board_is_still_read_and_left(self):
        g = self.game()
        row = self.go(g, run=self.command(g, raises=subprocess.TimeoutExpired("loop", 5)), notebook=str(self.given), timeout=5)
        self.assertEqual((row["end_reason"], row["rc"], self.seen[0][2]), ("timeout", None, 5))
        self.assertEqual((row["end"]["values"]["score"], g.left, self.nb.read_text()), (150, 1, "standing"))

    def test_the_second_read_waits_for_the_seats_turn(self):
        g = self.game(polls=[poll(251, 0, turn_active=False), poll(251, 0, turn_active=False), poll(252, 0)])
        self.go(g)
        self.assertEqual(g.polls, [])
        g = self.game(polls=[poll(251, 0, turn_active=False)] * 9)
        self.go(g, settle=6.0, poll=3.0)
        self.assertEqual(len(g.polls), 6, "polls at 0, 3 and 6 s, then the read whatever the turn")

    def test_a_dead_seat_and_a_win_are_said_over_the_commands_own_end(self):
        dead = read(turn=247, winner=1, victory="VICTORY_DOMINATION",
                    players=[player(0, human=True, alive=False), player(1)])
        row = self.go(self.game(after=dead, polls=[poll(247, 0, winner=1, alive=False, turn_active=False)]))
        self.assertEqual((row["end_reason"], row["rc"], row["victory"]), ("seat_dead", 3, "VICTORY_DOMINATION"))
        won = read(turn=247, winner=0, victory="VICTORY_SPACE_RACE")
        self.assertEqual(self.go(self.game(after=won))["end_reason"], "game_won")

    def test_a_command_needs_no_observer_slot(self):
        self.assertEqual(self.go(self.game(slots=(3, 1, 2, 2)))["end_reason"], "window_played")

    def test_a_command_that_ends_before_the_window_is_out_did_not_play_it(self):
        short = read(turn=246, players=[player(0, human=True, score=110, turn_active=True), player(1, score=310)])
        row = self.go(self.game(after=short, polls=[poll(246, 0)]))
        self.assertEqual((row["end_reason"], row["turns_asked"], row["turns_played"], row["rc"]), ("window_not_played", 10, 4, 3))
        self.assertIn("codex/x: 1 runs, 0 played their window, 1 window_not_played", board_run.summarise([row]))

    def test_the_command_line_wants_a_label_with_a_command_and_a_command_with_a_label(self):
        for argv in (["--save", "b", "--out", "x.jsonl", "--", "loop"], ["--save", "b", "--out", "x.jsonl", "--label", "codex"],
                     ["--save", "b", "--out", "x.jsonl", "--label", "stock-ai", "--", "loop"]):
            with self.subTest(argv), self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                board_run.main(argv)


class Views(unittest.TestCase):
    def test_shares_are_of_the_living_and_the_place_is_by_score(self):
        r = read(players=[player(0, human=True, score=100, techs=30), player(1, score=300, techs=50),
                          player(2, score=50, techs=20), player(3, alive=False, score=900, techs=99)])
        v = board_run.seat_view(r, 0)
        self.assertEqual((v["place"], v["of"]), (2, 3))
        self.assertEqual(v["share"]["techs"], 0.3)
        self.assertEqual(v["share"]["score"], round(100 / 450, 4))

    def test_a_negative_value_counts_as_nothing_in_a_share(self):
        r = read(players=[player(0, human=True, happiness=-4), player(1, happiness=8)])
        self.assertEqual(board_run.seat_view(r, 0)["share"]["happiness"], 0.0)


def row(score, reason="window_played", start=100, **kw):
    values = {k: 10 for k in board_run.INDICATORS}
    return {**kw, "save": "board", "seat": 0, "handicap": "HANDICAP_EMPEROR", "turns_asked": 10, "seconds": 300.0,
            "end_reason": reason, "start": {"values": dict(values, score=start)},
            "end": {"values": dict(values, score=score), "share": {k: 0.1 for k in board_run.INDICATORS},
                    "place": 2, "of": 12}}


class Summary(unittest.TestCase):
    def test_the_spread_is_set_against_the_gain(self):
        lines = board_run.summarise([row(130), row(140), row(150), row(0, reason="seat_dead")])
        self.assertIn("4 runs, 3 played their window, 1 seat_dead", lines[0])
        score = next(line for line in lines if line.startswith("score"))
        self.assertEqual(score.split()[:7], ["score", "100", "140.0", "10.0", "130", "150", "0.25"])
        self.assertFalse(any("replays the same game" in line for line in lines))

    def test_runs_that_all_end_alike_are_said_to_be_one_game(self):
        lines = board_run.summarise([row(140), row(140)])
        self.assertTrue(any("replays the same game" in line for line in lines))
        self.assertFalse(any("replays the same game" in line for line in board_run.summarise([row(140)])))

    def test_rows_with_no_entrant_are_the_stock_ais(self):
        self.assertTrue(board_run.summarise([row(140)])[0].startswith("stock-ai: 1 runs"))

    def test_two_entrants_stand_side_by_side_on_runs_that_played_the_window(self):
        rows = [row(130, turns_played=10), row(150, turns_played=10),
                row(180, entrant="codex/x", turns_played=10),
                row(0, reason="timeout", entrant="codex/x", turns_played=4)]
        lines = board_run.summarise(rows)
        self.assertIn("codex/x: 2 runs, 1 played their window, 1 timeout", lines)
        head = lines.index("side by side, 10 turns, mean (sd) at the end:")
        self.assertEqual(lines[head + 1].split(), ["stock-ai", "x2", "codex/x", "x1"])
        self.assertEqual(lines[head + 2].split(), ["score", "140.0", "(14.1)", "180.0", "(0.0)"])

    def test_runs_of_different_windows_do_not_stand_side_by_side(self):
        lines = board_run.summarise([row(130, turns_played=10), row(180, entrant="codex/x", turns_played=7)])
        self.assertEqual(lines[-1], "not side by side: the runs played 7, 10 turns")
        self.assertFalse(any(line.startswith("side by side") for line in lines))

    def test_no_run_that_played_its_window_is_one_line(self):
        self.assertEqual(len(board_run.summarise([row(0, reason="stalled")])), 1)


class Lua(unittest.TestCase):
    def test_the_chunks_compile(self):
        try:
            import lupa
        except ImportError:
            self.skipTest("lupa is not installed")
        lua = lupa.LuaRuntime()
        for name, body in (("READ", board_run.READ), ("POLL", board_run.POLL % {"seat": 0}),
                           ("BURN", board_run.BURN % {"burn": 17}),
                           ("START", board_run.START % {"burn": 3, "turns": 10, "seat": 0})):
            with self.subTest(name):
                self.assertTrue(lua.eval("function(src) return loadstring and loadstring(src) or load(src) end")(body),
                                f"{name} does not compile")


if __name__ == "__main__":
    unittest.main()
