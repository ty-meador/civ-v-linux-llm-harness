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
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
            return self.reads.pop(0) if len(self.reads) > 1 else self.reads[0]   # the last read stands for any later one
        if "return {burn" in code:
            return {"burn": 0}
        if "ExitToMainMenu" in code:
            return {"ok": True}
        return self.polls.pop(0)

    def leave_to_main_menu(self):
        self.left += 1
        return self.leave_reply

    leave_reply = {"ok": True}

    def quick_save(self):
        self.sent.append("quick_save")
        if self.quick_file is not None:
            self.quick_file.parent.mkdir(parents=True, exist_ok=True)
            self.quick_file.write_text(f"save {len(self.sent)}")
        return self.quick_reply

    quick_file = None
    quick_reply = {"ok": True, "turn": 252}


class Clock:
    def __init__(self):
        self.t = 0.0

    def sleep(self, s):
        self.t += s

    def __call__(self):
        return self.t


def poll(turn, auto, winner=-1, alive=True, turn_active=True, victory=""):
    return {"turn": turn, "auto": auto, "winner": winner, "state": 0 if winner < 0 else 2, "alive": alive, "active": 2,
            "turn_active": turn_active, "team": 0, "victory": victory}


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

    def test_the_windows_own_terms_are_in_the_row(self):
        g = FakeGame([read(), read(turn=252)], polls=[poll(252, 0)])
        g.handed = dict(g.handed, seat_row="HANDICAP_AI_DEFAULT", time_victory=True)
        row = run(g, row="ai")
        self.assertEqual((row["seat_row"], row["time_victory"]), ("HANDICAP_AI_DEFAULT", True))
        self.assertIn("PreGame.SetHandicap(0, ", next(s for s in g.sent if "SetAIAutoPlay" in s))

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

    def test_the_command_is_told_the_turn_at_which_the_window_is_over(self):
        """Rule 5. Live 2026-11-16: told to end ten turns, Codex stopped with the board nine turns on."""
        g = self.game()
        clock = Clock()
        row = board_run.run_entrant(g, "board", ["loop", "--until-turn", "{until}"], "codex/x", 10, sleep=clock.sleep,
                                    clock=clock, path_of=lambda _g, _seat: self.nb, run=self.command(g))
        self.assertEqual(self.seen[0][0], ["loop", "--until-turn", "252"])
        self.assertEqual(row["command"], ["loop", "--until-turn", "252"])

    def test_a_command_needs_no_observer_slot(self):
        self.assertEqual(self.go(self.game(slots=(3, 1, 2, 2)))["end_reason"], "window_played")

    def test_a_command_that_ends_before_the_window_is_out_did_not_play_it(self):
        short = read(turn=246, players=[player(0, human=True, score=110, turn_active=True), player(1, score=310)])
        row = self.go(self.game(after=short, polls=[poll(246, 0)]))
        self.assertEqual((row["end_reason"], row["turns_asked"], row["turns_played"], row["rc"]), ("window_not_played", 10, 4, 3))
        self.assertIn("codex/x: 1 runs, 0 played their window, 1 window_not_played", board_run.summarise([row]))

    def test_the_command_line_wants_a_label_with_a_command_and_a_command_with_a_label(self):
        for argv in (["--save", "b", "--out", "x.jsonl", "--", "loop"], ["--save", "b", "--out", "x.jsonl", "--label", "codex"],
                     ["--save", "b", "--out", "x.jsonl", "--label", "stock-ai", "--", "loop"],
                     ["--save", "b", "--out", "x.jsonl", "--value-only"],
                     ["--save", "b", "--out", "x.jsonl", "--value-only", "--continue", "3", "--label", "c", "--", "loop"]):
            with self.subTest(argv), self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                board_run.main(argv)


class Continuations(unittest.TestCase):
    """Rule 1: the game played out from the window's end by the engine, and the share of those games the seat won."""

    def go(self, g, m=0, **kw):
        clock = Clock()
        return board_run.continuation(g, "board--end", m, sleep=clock.sleep, clock=clock, **kw)

    def test_a_victory_of_the_seats_team_is_a_game_won(self):
        g = FakeGame([read(turn=252)], polls=[poll(300, 950), poll(318, 932, winner=0, victory="VICTORY_SPACE_RACE"), poll(319, 0)])
        c = self.go(g)
        self.assertEqual((c["end_reason"], c["won"], c["victory"], c["turn"], c["from_turn"]),
                         ("victory", True, "VICTORY_SPACE_RACE", 318, 252))
        self.assertEqual((len(g.polls), g.left), (1, 1), "the engine plays on past a victory: the game is left")

    def test_a_game_the_engine_still_plays_is_left_by_the_referee_itself(self):
        """Live 2026-11-16: the seat's exit answered "this seat is not active" after a win under autoplay, and the
        game played on to turn 380 with the row already written."""
        g = FakeGame([read()], polls=[poll(331, 69, winner=1, victory="VICTORY_TIME")])
        g.leave_reply = {"ok": False, "err": "this seat is not active"}
        self.go(g)
        self.assertEqual(g.left, 1)
        self.assertIn("Events.ExitToMainMenu()", g.sent[-1])
        quiet = FakeGame([read()], polls=[poll(331, 69, winner=1)])
        self.go(quiet)
        self.assertFalse(any("ExitToMainMenu" in s for s in quiet.sent), "a seat's exit that worked is not sent twice")

    def test_a_decided_game_keeps_how_it_stood(self):
        end = read(turn=330, winner=1, victory="VICTORY_TIME", players=[player(0, human=True, score=1571), player(1, score=1865)])
        c = self.go(FakeGame([read(), end], polls=[poll(330, 900, winner=1, victory="VICTORY_TIME")]))
        self.assertEqual([(p["id"], p["score"]) for p in c["players"]], [(0, 1571), (1, 1865)])
        self.assertEqual(set(c["players"][0]), {"id", "civ", "alive", "score", "techs", "cities"})
        stalled = self.go(FakeGame([read()], polls=[poll(260, 990)] * 6), poll=3.0, stall=10.0)
        self.assertNotIn("players", stalled)

    def test_the_seat_is_put_on_the_ais_row_and_time_switched_off_in_the_call_that_hands_it_over(self):
        """Live 2026-11-17: the seat on the human's Prince row lost every whole game of two boards; set in play, the
        AIs' row is the seat's own by turn 12."""
        g = FakeGame([read()], polls=[poll(330, 1, winner=1)])
        g.handed = dict(g.handed, seat_row="HANDICAP_AI_DEFAULT", time_victory=False)
        c = self.go(g, row="ai", time_victory="off")
        start = next(s for s in g.sent if "SetAIAutoPlay" in s)
        setting = "PreGame.SetHandicap(0, GameInfo.HandicapInfos.HANDICAP_AI_DEFAULT.ID)"
        off = "Game.SetVictoryValid(GameInfoTypes.VICTORY_TIME, false)"
        self.assertLess(start.index("Game.Rand("), start.index(setting))
        self.assertLess(start.index(setting), start.index(off))
        self.assertLess(start.index(off), start.index("Game.SetAIAutoPlay("))
        # the validity alone is not enough: with it off a duel still ended by Time at turn 330 (live 2026-11-17)
        self.assertIn("PreGame.SetMaxTurns(0)", start)
        self.assertEqual((c["seat_row"], c["time_victory"]), ("HANDICAP_AI_DEFAULT", False))
        plain = FakeGame([read()], polls=[poll(330, 1, winner=1)])
        self.go(plain)
        start = next(s for s in plain.sent if "SetAIAutoPlay" in s)
        self.assertNotIn("SetHandicap", start)
        self.assertNotIn("SetVictoryValid", start)

    def test_a_game_with_no_victory_by_the_last_turn_is_stopped_and_not_decided(self):
        g = FakeGame([read()], polls=[poll(599, 500), poll(600, 499), poll(601, 498)])
        c = self.go(g, time_victory="off", stop_turn=600)
        self.assertEqual((c["end_reason"], c["won"], c["turn"], len(g.polls), g.left), ("turn_limit", False, 600, 1, 1))
        self.assertIn("players", c)
        self.assertIsNone(board_run.value_of({"end_reason": "window_played"}, [c]))

    def test_another_teams_victory_is_a_game_not_won(self):
        c = self.go(FakeGame([read()], polls=[poll(330, 900, winner=1, victory="VICTORY_TIME")]))
        self.assertEqual((c["end_reason"], c["won"], c["winner"]), ("victory", False, 1))

    def test_a_dead_seat_is_a_game_lost_without_waiting_for_the_winner(self):
        g = FakeGame([read()], polls=[poll(260, 990), poll(270, 980, alive=False), poll(300, 950, winner=1)])
        c = self.go(g)
        self.assertEqual((c["end_reason"], c["won"], len(g.polls), g.left), ("seat_dead", False, 1, 1))

    def test_a_stall_is_no_result(self):
        c = self.go(FakeGame([read()], polls=[poll(260, 990)] * 6), poll=3.0, stall=10.0)
        self.assertEqual((c["end_reason"], c["won"]), ("stalled", False))
        self.assertIsNone(board_run.value_of({"end_reason": "window_played"}, [c]))

    def test_every_continuation_takes_draws_and_asks_for_more_turns_than_a_game_has(self):
        for m, draws in ((0, 29), (1, 58), (19, 580)):
            g = FakeGame([read()], polls=[poll(330, 1, winner=1)])
            self.assertEqual(self.go(g, m=m)["burn"], draws)
            start = next(s for s in g.sent if "SetAIAutoPlay" in s)
            self.assertIn(f"for _ = 1, {draws} do Game.Rand(", start)
            self.assertIn("Game.SetAIAutoPlay(1000, 0)", start)

    def test_a_save_with_no_observer_slot_is_refused_and_left(self):
        g = FakeGame([read(slots=(3, 1, 2))])
        with self.assertRaisesRegex(board_run.Refused, "observer slot"):
            self.go(g)
        self.assertEqual((g.left, any("SetAIAutoPlay" in s for s in g.sent)), (1, False))

    def test_the_value_is_the_share_of_decided_games_won(self):
        games = [{"end_reason": "victory", "won": True}, {"end_reason": "victory", "won": False},
                 {"end_reason": "seat_dead", "won": False}, {"end_reason": "stalled", "won": False}]
        self.assertEqual(board_run.value_of({"end_reason": "window_played"}, games), round(1 / 3, 4))
        self.assertEqual(board_run.value_of({"end_reason": "value_only"}, games[:2]), 0.5)

    def test_a_run_that_did_not_finish_has_no_value_and_is_a_result_of_its_own(self):
        won = [{"end_reason": "victory", "won": True}]
        for reason, result in (("window_not_played", "dnf"), ("timeout", "dnf"), ("stalled", "void"), ("not_handed_over", "void")):
            self.assertIsNone(board_run.value_of({"end_reason": reason}, won), reason)
            self.assertEqual(board_run.result_of({"end_reason": reason}), result)

    def test_a_game_ended_inside_the_window_is_finished_and_all_or_nothing(self):
        self.assertEqual(board_run.value_of({"end_reason": "game_won", "winner": 0, "end": {"team": 0}}, []), 1.0)
        self.assertEqual(board_run.value_of({"end_reason": "game_won", "winner": 1, "end": {"team": 0}}, []), 0.0)
        self.assertEqual(board_run.value_of({"end_reason": "seat_dead"}, []), 0.0)
        for reason in ("window_played", "game_won", "seat_dead", "value_only"):
            self.assertEqual(board_run.result_of({"end_reason": reason}), "finished")


class EndSave(unittest.TestCase):
    def setUp(self):
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(mock.patch.dict(os.environ, {"CIV5_SAVES_DIR": str(self.dir)}))

    def game(self, **kw):
        g = FakeGame([read(), read(turn=252)], polls=[poll(252, 0)], **kw)
        g.quick_file = self.dir / "quick" / "QuickSave.Civ5Save"
        return g

    def test_a_played_window_is_saved_under_its_name_before_the_game_is_left(self):
        g = self.game()
        clock = Clock()
        row = board_run.run_once(g, "board", 10, end_save="board--stock-ai-deal0-end", sleep=clock.sleep, clock=clock)
        self.assertEqual(row["end_save"], "board--stock-ai-deal0-end")
        self.assertTrue((self.dir / "board--stock-ai-deal0-end.Civ5Save").read_text().startswith("save "))
        self.assertEqual(g.left, 1)

    def test_an_old_quick_save_is_not_taken_for_the_new_one(self):
        g = self.game()
        g.quick_file.parent.mkdir()
        g.quick_file.write_text("an older game")
        clock = Clock()
        board_run.save_as(g, "kept", sleep=clock.sleep, clock=clock)
        self.assertNotEqual((self.dir / "kept.Civ5Save").read_text(), "an older game")

    def test_a_quick_save_that_is_refused_or_never_written_is_said_in_the_row(self):
        refused, unwritten = self.game(), self.game()
        refused.quick_reply = {"ok": False, "err": "not your turn"}
        unwritten.quick_file = None
        for g, why in ((refused, "refused"), (unwritten, "not written")):
            clock = Clock()
            row = board_run.run_once(g, "board", 10, end_save="kept", sleep=clock.sleep, clock=clock)
            self.assertEqual((row["end_reason"], row["end_save"]), ("window_played", None))
            self.assertIn(why, row["end_save_error"])
            self.assertEqual(g.left, 1)

    def test_a_window_that_was_not_played_is_not_saved(self):
        g = FakeGame([read(), read(turn=246, winner=1, players=[player(0, human=True, alive=False), player(1)])],
                     polls=[poll(246, 6, winner=1, alive=False)])
        clock = Clock()
        row = board_run.run_once(g, "board", 10, end_save="kept", sleep=clock.sleep, clock=clock)
        self.assertNotIn("end_save", row)
        self.assertNotIn("quick_save", g.sent)


class Terms(unittest.TestCase):
    """Live 2026-11-17: a save made after the seat was put on the AIs' row and Time switched off reads both back
    after a reload, so a board can carry its terms and every window on it is played on them."""

    TOLD = {"seat_row": "HANDICAP_AI_DEFAULT", "time_victory": False, "max_turns": 0}

    def make(self, g, **kw):
        saved = []
        out = board_run.with_terms(g, "board-t0", "board-t0-terms", save_game=lambda _g, name: saved.append(name) or name, **kw)
        return out, saved

    @staticmethod
    def sent_terms(g):
        return next(c for c in g.sent if "seat_row" in c and "SetAIAutoPlay" not in c and "players = {}" not in c)

    def test_the_board_is_changed_then_saved_under_the_new_name_and_left(self):
        g = FakeGame([read(turn=0)], polls=[dict(self.TOLD)])
        out, saved = self.make(g)
        chunk = self.sent_terms(g)
        self.assertIn("PreGame.SetHandicap(0, GameInfo.HandicapInfos.HANDICAP_AI_DEFAULT.ID)", chunk)
        self.assertIn("PreGame.SetMaxTurns(0)", chunk)
        self.assertFalse(any("SetAIAutoPlay" in c for c in g.sent))          # nobody plays a turn
        self.assertEqual(saved, ["board-t0-terms"])
        self.assertEqual(out, {**self.TOLD, "save": "board-t0-terms", "made_from": "board-t0", "seat": 0, "turn": 0})
        self.assertEqual(g.left, 1)

    def test_either_term_can_be_left_as_hosted(self):
        g = FakeGame([read(turn=0)], polls=[dict(self.TOLD)])
        self.make(g, row="own")
        chunk = self.sent_terms(g)
        self.assertNotIn("SetHandicap", chunk)
        self.assertIn("PreGame.SetMaxTurns(0)", chunk)

    def test_a_board_with_no_observer_slot_is_refused_unchanged_and_left(self):
        g = FakeGame([read(slots=(3, 1, 2, 2))])
        with self.assertRaises(board_run.Refused):
            self.make(g)
        self.assertFalse(any("SetHandicap" in c for c in g.sent))
        self.assertEqual(g.left, 1)

    def test_the_command_line_makes_both_terms_unless_told_otherwise(self):
        seen = {}

        def fake(_g, save, new, seat=None, row="ai", time_victory="off", **_kw):
            seen.update(save=save, new=new, row=row, time=time_victory)
            return {"save": new}

        game = mock.Mock()
        game.has_state.return_value = False
        with mock.patch.object(board_run, "with_terms", fake), mock.patch("harness.game.Game", return_value=game), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(board_run.main(["--save", "a", "--terms", "b"]), 0)
            self.assertEqual(seen, {"save": "a", "new": "b", "row": "ai", "time": "off"})
            self.assertEqual(board_run.main(["--save", "a", "--terms", "b", "--time", "on"]), 0)
            self.assertEqual(seen["time"], "on")


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

    def test_the_value_has_its_own_line_and_its_row_side_by_side(self):
        games = [{"end_reason": "victory", "won": True, "victory": "VICTORY_TIME", "seconds": 600.0}] * 2
        rows = [row(130, turns_played=10, value=0.5, continuations=games), row(150, turns_played=10, value=0.3, continuations=games),
                row(180, entrant="codex/x", turns_played=10, value=0.7, continuations=games),
                row(0, reason="window_not_played", entrant="codex/x", turns_played=4, value=None)]
        lines = board_run.summarise(rows)
        self.assertIn("value: 0.400 (sd 0.141) over 2 finished runs and 4 continuations, 10.0 min each; by run: 0.50, 0.30; "
                      "ended by VICTORY_TIME", lines)
        self.assertTrue(any(line.startswith("value: 0.700 (sd 0.000) over 1 finished runs") for line in lines),
                        "a DNF is not averaged into the value")
        self.assertIn("DNF: 1 of 2 runs (window_not_played), below every finished run in an ordering; "
                      "with DNF as 0 the value is 0.350", lines)
        self.assertEqual(lines[-2].split(), ["value", "0.400", "(0.141)", "0.700", "(0.000)"])
        self.assertEqual(lines[-1].split(), ["DNF", "0", "of", "2", "1", "of", "2"])

    def test_a_save_valued_as_it_is_has_one_line(self):
        only = {"entrant": "board", "end_reason": "value_only", "value": 0.25,
                "continuations": [{"end_reason": "seat_dead", "won": False, "seconds": 120.0}]}
        lines = board_run.summarise([only])
        self.assertEqual(lines[0], "board: 1 runs, 0 played their window")
        self.assertTrue(lines[1].startswith("value: 0.250 (sd 0.000) over 1 finished runs and 1 continuations, 2.0 min each"))
        self.assertTrue(lines[1].endswith("ended by seat_dead"))

    def test_the_games_as_one_pool_and_the_ones_the_stop_turn_left_open(self):
        games = [{"end_reason": "victory", "won": True, "seconds": 60.0, "victory": "VICTORY_CULTURAL"},
                 {"end_reason": "victory", "won": False, "seconds": 60.0, "victory": "VICTORY_DOMINATION"},
                 {"end_reason": "turn_limit", "won": False, "seconds": 600.0, "turn": 500}]
        lines = board_run.summarise([{"entrant": "board", "end_reason": "value_only", "value": 0.5,
                                      "continuations": games}])
        self.assertIn("and 2 continuations, 1.0 min each", lines[1])      # the open game is in no mean
        self.assertEqual(lines[2], "games: the seat won 1 of 2 decided, 0.500 (standard error 0.354)")
        self.assertEqual(lines[3], "not decided by the stop turn: 1 (turn 500), in no share")

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
                           ("BURN", board_run.BURN % {"burn": 17}), ("LEAVE", board_run.LEAVE),
                           ("START", board_run.start_chunk(3, 10, 0)),
                           ("START with terms", board_run.start_chunk(3, 10, 0, row="ai", time="off"))):
            with self.subTest(name):
                self.assertTrue(lua.eval("function(src) return loadstring and loadstring(src) or load(src) end")(body),
                                f"{name} does not compile")


if __name__ == "__main__":
    unittest.main()
