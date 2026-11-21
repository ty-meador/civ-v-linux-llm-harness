"""A benchmark run's last turn (docs/BENCHMARK.md rule 5): the seat's server is given the turn the run ends on
(CIV5_UNTIL_TURN) and that turn is not played -- no order runs on it and no finish ends it.

Live 2026-11-19 (the first trial's seed 1 on the Celts duel): the player met turn 101 in a run that ended at 100,
and the benchmark runner, which wants the game exactly the run's turns on, had nothing to value. The user's call the
same day: overshooting is the benchmark's to handle, not the player's."""
from __future__ import annotations

import json
import os
import unittest
from unittest import mock

from harness import mcp_server as core
from harness.game import Game
from harness.surface import classes as C
from tests.test_finish_turn import QUIET, ScriptedGame, status


def limited(turns, first, until=100):
    g = ScriptedGame(turns, first_status=first)
    g.until_turn = until
    return g


class LastTurnReached(unittest.TestCase):
    def test_a_game_with_no_last_turn_is_never_over(self):
        g = ScriptedGame([(status(2), QUIET)])
        self.assertIsNone(g.until_turn)
        self.assertIsNone(g.last_turn_reached(status(500)))

    def test_the_last_turn_and_any_later_one_are_over(self):
        g = limited([], status(1))
        self.assertIsNone(g.last_turn_reached(status(99)))
        self.assertEqual(g.last_turn_reached(status(100))["until"], 100)
        over = g.last_turn_reached(status(103))
        self.assertEqual((over["until"], over["turn"]), (100, 103))
        self.assertIn("turn 100 is yours and is not played", over["note"])

    def test_a_status_without_a_turn_says_nothing(self):
        g = limited([], status(1))
        self.assertIsNone(g.last_turn_reached({}))
        self.assertIsNone(g.last_turn_reached(None))


class FinishAtTheLastTurn(unittest.TestCase):
    def test_the_finish_that_brings_the_last_turn_says_so(self):
        g = limited([(status(100), QUIET)], status(99))
        r = g.finish_turn()
        self.assertTrue(r["ok"] and r["ended"])
        self.assertEqual(r["turn"], 100)
        self.assertEqual(r["woke_because"], ["last_turn_reached"])
        self.assertEqual(r["last_turn_reached"]["until"], 100)
        self.assertIn("stop here", r["hint"])
        self.assertEqual(g.log, ["end", "wait", "digest"])

    def test_a_finish_on_the_last_turn_ends_nothing(self):
        g = limited([(status(101), QUIET)], status(100))
        r = g.finish_turn()
        self.assertFalse(r["ok"])
        self.assertFalse(r["ended"])
        self.assertEqual(r["turn"], 100)
        self.assertIn("your turns are over", r["err"])
        self.assertEqual(g.log, [], "no end, no wait")

    def test_a_run_of_quiet_turns_stops_on_the_last_turn(self):
        g = limited([(status(99), QUIET), (status(100), QUIET), (status(101), QUIET), (status(102), QUIET)], status(98))
        r = g.finish_turn(skip_quiet_turns=10)
        self.assertTrue(r["ended"])
        self.assertEqual(r["turn"], 100)
        self.assertEqual(g.log.count("end"), 2, "turns 98 and 99 ended, 100 not")
        self.assertEqual(r["turns_skipped"], 1)
        self.assertEqual(r["woke_because"], ["last_turn_reached"])

    def test_before_the_last_turn_a_finish_is_as_it_was(self):
        g = limited([(status(50), QUIET)], status(49))
        r = g.finish_turn()
        self.assertEqual(r["woke_because"], ["turn_started"])
        self.assertNotIn("last_turn_reached", r)

    def test_the_other_players_turn_is_only_waited_on(self):
        g = limited([(status(100), QUIET)], status(100, my_turn=False))
        r = g.finish_turn()
        self.assertEqual(g.log[0], "wait")
        self.assertEqual(r["woke_because"], ["last_turn_reached"])


class OrdersAtTheLastTurn(unittest.TestCase):
    def test_an_order_is_refused_and_a_read_is_not(self):
        g = limited([], status(100))
        ts = {**status(100), "discussion_pending": False}
        refused = core._refusal_for(g, ts, C.of_call("order", {"to": "unit", "action": "move"}))
        self.assertFalse(refused["ok"])
        self.assertEqual(refused["last_turn_reached"]["turn"], 100)
        self.assertIn("your turns are over", refused["err"])
        self.assertIsNone(core._refusal_for(g, ts, C.of_call("state", {"what": "units"})))
        self.assertIsNone(core._refusal_for(g, ts, C.of_handler("accept_deal")), "a leader on screen may be answered")

    def test_the_turn_before_is_played_as_ever(self):
        g = limited([], status(99))
        ts = {**status(99), "discussion_pending": False}
        self.assertIsNone(core._refusal_for(g, ts, C.of_call("order", {"to": "unit", "action": "move"})))

    def test_a_fake_that_keeps_no_last_turn_is_not_refused(self):
        g = mock.MagicMock()
        g.seat = 0
        self.assertIsNone(core._last_turn_reached(g, status(100)))

    def test_orders_sent_with_a_finish_on_the_last_turn_say_the_turns_are_over(self):
        from harness.mcp_tools import turn as tool
        g = limited([(status(101), QUIET)], status(100))
        batch = {"ok": False, "done": 0, "results": [{"ok": False, "err": "your turns are over"}], "skipped": []}
        with mock.patch.object(core, "game", return_value=g), \
                mock.patch("harness.mcp_tools.batch.run_batch", return_value=batch):
            out = json.loads(tool.finish_turn.__wrapped__(
                actions=[{"tool": "order", "args": {"to": "unit", "id": 7, "action": "mission", "args": {"mission": "MISSION_SKIP"}}}]))
        self.assertFalse(out["ok"])
        self.assertFalse(out["ended"])
        self.assertEqual(out["last_turn_reached"]["until"], 100)
        self.assertNotIn("hint", out, "not the 'send them again' of an ordinary refusal")
        self.assertNotIn("end", g.log)


class TheVariable(unittest.TestCase):
    def read(self, value):
        env = {k: v for k, v in os.environ.items() if k != "CIV5_UNTIL_TURN"}
        if value is not None:
            env["CIV5_UNTIL_TURN"] = value
        with mock.patch.dict(os.environ, env, clear=True):
            return core.until_turn()

    def test_unset_or_empty_is_no_last_turn(self):
        self.assertIsNone(self.read(None))
        self.assertIsNone(self.read(" "))

    def test_a_turn_is_read(self):
        self.assertEqual(self.read("100"), 100)

    def test_a_word_that_is_no_turn_keeps_no_last_turn(self):
        with mock.patch("sys.stderr"):
            self.assertIsNone(self.read("soon"))

    def test_the_class_keeps_none(self):
        self.assertIsNone(Game.until_turn)


if __name__ == "__main__":
    unittest.main()
