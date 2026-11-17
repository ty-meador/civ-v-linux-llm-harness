"""scripts/board_run.py against a fake Game: what it refuses, when a run ends, and what a row says.

Live 2026-11-16 (docs/BENCHMARK.md, "Autoplay, checked live"): `Game.SetAIAutoPlay` on a duel whose unused slots
were closed made the seat the observer and destroyed its Settler and Warrior in the same call, with no error; a
win did not stop a run; and after the seat died the game played turns by itself. The runner refuses the first
before it changes anything, and for the other two it watches the run and leaves the game itself.
"""
from __future__ import annotations

import importlib.util
import json
import sys
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


def poll(turn, auto, winner=-1, alive=True):
    return {"turn": turn, "auto": auto, "winner": winner, "state": 0 if winner < 0 else 2, "alive": alive, "active": 2}


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


def row(score, reason="window_played", start=100):
    values = {k: 10 for k in board_run.INDICATORS}
    return {"save": "board", "seat": 0, "handicap": "HANDICAP_EMPEROR", "turns_asked": 10, "seconds": 300.0,
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

    def test_no_run_that_played_its_window_is_one_line(self):
        self.assertEqual(len(board_run.summarise([row(0, reason="stalled")])), 1)


class Lua(unittest.TestCase):
    def test_the_three_chunks_compile(self):
        try:
            import lupa
        except ImportError:
            self.skipTest("lupa is not installed")
        lua = lupa.LuaRuntime()
        for name, body in (("READ", board_run.READ), ("POLL", board_run.POLL % {"seat": 0}),
                           ("START", board_run.START % {"burn": 3, "turns": 10, "seat": 0})):
            with self.subTest(name):
                self.assertTrue(lua.eval("function(src) return loadstring and loadstring(src) or load(src) end")(body),
                                f"{name} does not compile")


if __name__ == "__main__":
    unittest.main()
