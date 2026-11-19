"""A referee's window (docs/BENCHMARK.md rule 5): the seat's server is given the turn the window ends on
(CIV5_UNTIL_TURN) and that turn is not played -- no order runs on it and no finish ends it.

Live 2026-11-19 (the pilot's deal 1 on the Celts duel): the entrant met turn 101 with a window that ended at 100,
and the referee, which wants the board exactly the window's turns on, had nothing to value. The user's call the
same day: overshooting is the benchmark's to handle, not the entrant's."""
from __future__ import annotations

import json
import os
import unittest
from unittest import mock

from harness import mcp_server as core
from harness.game import Game
from harness.surface import classes as C
from tests.test_finish_turn import QUIET, ScriptedGame, status


def windowed(turns, first, until=100):
    g = ScriptedGame(turns, first_status=first)
    g.window_until = until
    return g


class WindowOver(unittest.TestCase):
    def test_no_window_is_never_over(self):
        g = ScriptedGame([(status(2), QUIET)])
        self.assertIsNone(g.window_until)
        self.assertIsNone(g.window_over(status(500)))

    def test_the_windows_turn_and_any_later_one_are_over(self):
        g = windowed([], status(1))
        self.assertIsNone(g.window_over(status(99)))
        self.assertEqual(g.window_over(status(100))["until"], 100)
        over = g.window_over(status(103))
        self.assertEqual((over["until"], over["turn"]), (100, 103))
        self.assertIn("turn 100 is yours and is not played", over["note"])

    def test_a_status_without_a_turn_says_nothing(self):
        g = windowed([], status(1))
        self.assertIsNone(g.window_over({}))
        self.assertIsNone(g.window_over(None))


class FinishAtTheWindow(unittest.TestCase):
    def test_the_finish_that_brings_the_windows_turn_says_so(self):
        g = windowed([(status(100), QUIET)], status(99))
        r = g.finish_turn()
        self.assertTrue(r["ok"] and r["ended"])
        self.assertEqual(r["turn"], 100)
        self.assertEqual(r["woke_because"], ["window_over"])
        self.assertEqual(r["window_over"]["until"], 100)
        self.assertIn("stop here", r["hint"])
        self.assertEqual(g.log, ["end", "wait", "digest"])

    def test_a_finish_on_the_windows_turn_ends_nothing(self):
        g = windowed([(status(101), QUIET)], status(100))
        r = g.finish_turn()
        self.assertFalse(r["ok"])
        self.assertFalse(r["ended"])
        self.assertEqual(r["turn"], 100)
        self.assertIn("the window is over", r["err"])
        self.assertEqual(g.log, [], "no end, no wait")

    def test_a_run_of_quiet_turns_stops_on_the_windows_turn(self):
        g = windowed([(status(99), QUIET), (status(100), QUIET), (status(101), QUIET), (status(102), QUIET)], status(98))
        r = g.finish_turn(skip_quiet_turns=10)
        self.assertTrue(r["ended"])
        self.assertEqual(r["turn"], 100)
        self.assertEqual(g.log.count("end"), 2, "turns 98 and 99 ended, 100 not")
        self.assertEqual(r["turns_skipped"], 1)
        self.assertEqual(r["woke_because"], ["window_over"])

    def test_before_the_window_a_finish_is_as_it_was(self):
        g = windowed([(status(50), QUIET)], status(49))
        r = g.finish_turn()
        self.assertEqual(r["woke_because"], ["turn_started"])
        self.assertNotIn("window_over", r)

    def test_the_other_players_turn_is_only_waited_on(self):
        g = windowed([(status(100), QUIET)], status(100, my_turn=False))
        r = g.finish_turn()
        self.assertEqual(g.log[0], "wait")
        self.assertEqual(r["woke_because"], ["window_over"])


class OrdersAtTheWindow(unittest.TestCase):
    def test_an_order_is_refused_and_a_read_is_not(self):
        g = windowed([], status(100))
        ts = {**status(100), "discussion_pending": False}
        refused = core._refusal_for(g, ts, C.of_call("order", {"to": "unit", "action": "move"}))
        self.assertFalse(refused["ok"])
        self.assertEqual(refused["window_over"]["turn"], 100)
        self.assertIn("the window is over", refused["err"])
        self.assertIsNone(core._refusal_for(g, ts, C.of_call("state", {"what": "units"})))
        self.assertIsNone(core._refusal_for(g, ts, C.of_handler("accept_deal")), "a leader on screen may be answered")

    def test_the_turn_before_is_played_as_ever(self):
        g = windowed([], status(99))
        ts = {**status(99), "discussion_pending": False}
        self.assertIsNone(core._refusal_for(g, ts, C.of_call("order", {"to": "unit", "action": "move"})))

    def test_a_fake_that_keeps_no_window_is_not_refused(self):
        g = mock.MagicMock()
        g.seat = 0
        self.assertIsNone(core._window_over(g, status(100)))

    def test_orders_sent_with_a_finish_on_the_windows_turn_name_the_window(self):
        from harness.mcp_tools import turn as tool
        g = windowed([(status(101), QUIET)], status(100))
        batch = {"ok": False, "done": 0, "results": [{"ok": False, "err": "the window is over"}], "skipped": []}
        with mock.patch.object(core, "game", return_value=g), \
                mock.patch("harness.mcp_tools.batch.run_batch", return_value=batch):
            out = json.loads(tool.finish_turn.__wrapped__(
                actions=[{"tool": "order", "args": {"to": "unit", "id": 7, "action": "mission", "args": {"mission": "MISSION_SKIP"}}}]))
        self.assertFalse(out["ok"])
        self.assertFalse(out["ended"])
        self.assertEqual(out["window_over"]["until"], 100)
        self.assertNotIn("hint", out, "not the 'send them again' of an ordinary refusal")
        self.assertNotIn("end", g.log)


class TheVariable(unittest.TestCase):
    def read(self, value):
        env = {k: v for k, v in os.environ.items() if k != "CIV5_UNTIL_TURN"}
        if value is not None:
            env["CIV5_UNTIL_TURN"] = value
        with mock.patch.dict(os.environ, env, clear=True):
            return core.window_until()

    def test_unset_or_empty_is_no_window(self):
        self.assertIsNone(self.read(None))
        self.assertIsNone(self.read(" "))

    def test_a_turn_is_read(self):
        self.assertEqual(self.read("100"), 100)

    def test_a_word_that_is_no_turn_keeps_no_window(self):
        with mock.patch("sys.stderr"):
            self.assertIsNone(self.read("soon"))

    def test_the_class_keeps_none(self):
        self.assertIsNone(Game.window_until)


if __name__ == "__main__":
    unittest.main()
