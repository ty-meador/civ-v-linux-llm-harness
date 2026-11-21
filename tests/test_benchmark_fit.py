"""scripts/benchmark_fit.py: positions with outcomes out of the runner's rows, a small logistic fit, and a run valued
by the point it ended on. No game: rows are made by hand."""
import contextlib
import io
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import benchmark_fit
import benchmark_run


def player(pid, alive=True, **kw):
    row = {"id": pid, "alive": alive, **{k: 10 for k in benchmark_run.INDICATORS}, **{k: 0 for k in benchmark_run.ROUTES}}
    row.update(kw)
    return row


def point(turn, mine, theirs, **kw):
    return {"turn": turn, "players": [player(0, score=mine, **kw), player(1, score=theirs)]}


def game(m, won, path, reason="victory", seat=0):
    return {"m": m, "seat": seat, "end_reason": reason, "won": won, "path": path}


class Points(unittest.TestCase):
    def test_a_decided_game_gives_a_point_for_each_read_of_its_path_with_the_games_outcome(self):
        rows = [{"player": "save", "seat": None, "ai_finishes": [game(0, True, [point(0, 10, 10), point(10, 30, 10)]),
                                                                    game(1, False, [point(0, 10, 10)])]}]
        pts = benchmark_fit.points_of(rows, "whole")
        self.assertEqual([(p["group"], p["turn"], p["won"]) for p in pts],
                         [("whole:0:0", 0, True), ("whole:0:0", 10, True), ("whole:0:1", 0, False)])
        self.assertEqual((pts[1]["share"]["score"], pts[1]["n"]), (0.75, 2))

    def test_the_ai_finishes_of_a_run_start_from_one_position_and_are_left_out_together(self):
        run = {"player": "built-in-ai", "seat": 0, "end_reason": "all_turns_played",
               "ai_finishes": [game(0, True, [point(100, 30, 10), point(110, 40, 10)]), game(1, False, [point(100, 30, 10)])]}
        pts = benchmark_fit.points_of([run, run], "baseline")
        self.assertEqual([p["group"] for p in pts], ["baseline:0"] * 3 + ["baseline:1"] * 3)

    def test_finishes_played_later_on_a_runs_end_save_are_its_own_with_later(self):
        with tempfile.TemporaryDirectory() as d:
            runs, later, model = Path(d) / "runs.jsonl", Path(d) / "later.jsonl", Path(d) / "model.json"
            rows = [{"player": "built-in-ai", "seat": 0, "end_reason": "all_turns_played", "end_save": f"e{i}",
                     "end_point": point(100, 60 if i % 2 else 40, 50), "value": float(i % 2),
                     "ai_finishes": [game(0, bool(i % 2), [point(100, 60 if i % 2 else 40, 50)])]} for i in range(6)]
            runs.write_text("".join(json.dumps(r) + "\n" for r in rows))
            later.write_text("".join(json.dumps(
                {"player": "save", "seat": 0, "save": f"e{i}", "end_reason": "finish_only",
                 "ai_finishes": [game(1, False, [point(100, 60 if i % 2 else 40, 50)])]}) + "\n" for i in range(6)))
            self.assertEqual(benchmark_fit.main(["--fit", str(runs), "--later", str(later), "--features", "score",
                                                 "--model", str(model)]), 0)
            kept = json.loads(model.read_text())
            self.assertEqual((kept["games"], kept["points"]), (6, 12), "six seeds of two finishes, not twelve games")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                benchmark_fit.main(["--model", str(model), "--value", str(runs), "--later", str(later)])
            self.assertIn("AI finishes won 0.250 on 6 of them", out.getvalue())

    def test_a_game_that_was_stopped_undecided_gives_none(self):
        rows = [{"seat": 0, "ai_finishes": [game(0, False, [point(0, 10, 10)], reason="last_turn")]}]
        self.assertEqual(benchmark_fit.points_of(rows), [])

    def test_an_indicator_nobody_has_any_of_is_an_even_share_and_a_dead_seat_is_no_point(self):
        shares, n = benchmark_fit.shares_of([player(0, delegates=0), player(1, delegates=0)], 0)
        self.assertEqual((shares["delegates"], n), (0.5, 2))
        self.assertIsNone(benchmark_fit.shares_of([player(0, alive=False), player(1)], 0))

    def test_a_run_with_no_path_gives_the_point_its_turns_ended_on_once_for_each_decided_ai_finish(self):
        row = {"seat": 0, "end_point": point(100, 20, 60), "end": {"alive": True, "of": 2, "turn": 100, "share": {"score": 0.9}},
               "ai_finishes": [{"m": 0, "end_reason": "victory", "won": False}, {"m": 1, "end_reason": "victory", "won": True},
                                 {"m": 2, "end_reason": "stalled", "won": False}]}
        pts = benchmark_fit.points_of([row], "floor")
        self.assertEqual([(p["group"], p["turn"], p["share"]["score"], p["won"]) for p in pts],
                         [("floor:0", 100, 0.25, False), ("floor:0", 100, 0.25, True)], "the point of every player, not the seat's view")

    def test_a_row_older_than_the_end_point_is_read_from_the_seats_own_shares(self):
        row = {"seat": 0, "end": {"alive": True, "of": 2, "turn": 60, "share": {"score": 0.4, "techs": 0.5}},
               "ai_finishes": [{"m": 0, "end_reason": "victory", "won": False}]}
        (p,) = benchmark_fit.points_of([row])
        self.assertEqual((p["turn"], p["share"]["score"]), (60, 0.4))
        self.assertIsNone(benchmark_fit.features_of(p, ("score", "delegates")), "it has no route to be asked about")

    def test_the_seat_is_the_ai_finishes_then_the_rows_then_the_one_given(self):
        self.assertEqual(benchmark_fit.seat_of({"seat": None}, {"seat": 1}), 1)
        self.assertEqual(benchmark_fit.seat_of({"seat": 0}, {}), 0)
        self.assertEqual(benchmark_fit.seat_of({"seat": None}, {}, seat=0), 0)


class Features(unittest.TestCase):
    def test_a_feature_is_the_lead_over_an_even_share_and_can_grow_with_the_turn(self):
        p = {"turn": 150, "n": 2, "share": {"score": 0.6, "techs": 0.5}}
        x = benchmark_fit.features_of(p, ("score", "score*t", "techs", "t"))
        self.assertEqual([round(v, 6) for v in x], [1.0, 0.1, 0.15, 0.0, 1.5])


class Fit(unittest.TestCase):
    def games(self, n=40, seed=7):
        """Games in which the seat with the larger share of score more often wins."""
        rng, rows = random.Random(seed), []
        for m in range(n):
            mine = rng.randint(20, 80)
            won = rng.random() < benchmark_fit.sigmoid(12 * (mine / 100 - 0.5))
            rows.append(game(m, won, [point(t, mine, 100 - mine) for t in (50, 100, 150)]))
        return [{"player": "save", "seat": 0, "end_reason": "finish_only", "ai_finishes": rows}]   # a --finish-only row

    def test_a_lead_that_wins_games_gets_a_positive_weight_and_beats_the_base_rate_on_games_it_never_saw(self):
        pts = benchmark_fit.points_of(self.games())
        xs = [benchmark_fit.features_of(p, ("score",)) for p in pts]
        coef = benchmark_fit.fit(xs, [p["won"] for p in pts])
        self.assertGreater(coef[1], 4)
        base = benchmark_fit.merit(benchmark_fit.left_out(pts, ()))
        seen = benchmark_fit.merit(benchmark_fit.left_out(pts, ("score",)))
        self.assertLess(seen["log_loss"], base["log_loss"] - 0.1)
        self.assertEqual(seen["points"], 120)

    def test_a_game_is_left_out_whole(self):
        """One game of thirty identical points that goes against every other: scored by the others, it is all wrong.
        Left out a point at a time it would be learned from its own twenty-nine."""
        rows = [{"player": "save", "seat": 0, "end_reason": "finish_only",
                 "ai_finishes": [game(m, False, [point(100, 30, 70)]) for m in range(6)]
                 + [game(m, True, [point(100, 70, 30)]) for m in range(6, 12)]
                 + [game(99, True, [point(100, 30, 70)] * 30)]}]
        scored = benchmark_fit.left_out(benchmark_fit.points_of(rows), ("score",))
        odd = [q for p, q in scored if p["group"].endswith(":99")]
        self.assertEqual(len(odd), 30)
        self.assertLess(max(odd), 0.3)

    def test_a_feature_that_splits_the_games_cleanly_still_gives_a_finite_fit(self):
        xs = [[1.0, -0.2]] * 5 + [[1.0, 0.2]] * 5
        coef = benchmark_fit.fit(xs, [False] * 5 + [True] * 5)
        self.assertTrue(0 < coef[1] < 200)
        self.assertGreater(benchmark_fit.predict(coef, [1.0, 0.2]), 0.8)


class Value(unittest.TestCase):
    def test_a_run_is_valued_at_the_point_its_turns_ended_on_beside_what_the_ai_finishes_gave(self):
        model = {"features": ["score"], "coef": [0.0, 10.0]}
        rows = [{"player": "play-loop", "seat": 0, "end_reason": "all_turns_played", "end_point": point(100, 60, 40), "value": 1.0},
                {"player": "play-loop", "seat": 0, "end_reason": "all_turns_played", "end_point": point(100, 40, 60), "value": 0.0},
                {"player": "play-loop", "seat": 0, "end_reason": "turns_not_played", "end_point": point(38, 90, 10)}]
        (line,) = benchmark_fit.value_lines(model, rows)
        self.assertIn("play-loop: estimate 0.500 over 2 seeds", line, "a run that did not finish has no value, estimated or by AI finishes")
        self.assertIn("AI finishes won 0.500 on 2 of them", line)
        self.assertNotIn("outside", line)

    def test_a_run_that_ended_outside_the_turns_of_the_fit_is_said(self):
        model = {"features": ["score"], "coef": [0.0, 10.0], "turns": [20, 110]}
        rows = [{"player": "built-in-ai", "seat": 0, "end_reason": "all_turns_played", "end_point": point(t, 60, 40)} for t in (100, 250)]
        (line,) = benchmark_fit.value_lines(model, rows)
        self.assertIn("over 2 seeds", line)
        self.assertIn("1 ended outside turns 20 to 110", line)

    def test_the_models_own_error_stands_beside_the_estimate(self):
        """The error over seeds is how a player's positions differ; how far the fit moves with its games is another,
        and it is a jackknife over the games, not the range of the fits that leave one out (0.622 to 0.881 here)."""
        model = {"features": ["score"], "coef": [0.0, 10.0], "left_out_coefs": [[0.0, 5.0], [0.0, 20.0]]}
        rows = [{"player": "built-in-ai", "seat": 0, "end_reason": "all_turns_played", "end_point": point(100, 60, 40)}]
        (line,) = benchmark_fit.value_lines(model, rows)
        self.assertIn("estimate 0.731 over 1 seeds", line)
        self.assertIn("of the model 0.129 by a jackknife over its 2 games", line)

    def test_a_jackknife_of_a_mean_is_the_means_standard_error(self):
        xs = [1.0, 2.0, 4.0, 7.0, 11.0]
        left_out = [(sum(xs) - x) / (len(xs) - 1) for x in xs]
        mean = sum(xs) / len(xs)
        se = (sum((x - mean) ** 2 for x in xs) / (len(xs) - 1) / len(xs)) ** 0.5
        self.assertAlmostEqual(benchmark_fit.jackknife(left_out), se)

    def test_two_players_get_their_difference_with_the_models_error_taken_on_the_difference(self):
        """One fit values both, so a steeper fit moves both estimates apart and a flatter one together: the model's
        error of the difference is not the two errors added."""
        model = {"features": ["score"], "coef": [0.0, 10.0], "left_out_coefs": [[0.0, 5.0], [0.0, 20.0]]}
        rows = [{"player": "built-in-ai", "seat": 0, "end_reason": "all_turns_played", "end_point": point(100, 60, 40)},
                {"player": "play-loop", "seat": 0, "end_reason": "all_turns_played", "end_point": point(100, 40, 60)},
                {"player": "nobody", "seat": 0, "end_reason": "turns_not_played", "end_point": point(38, 90, 10)}]
        (line,) = benchmark_fit.difference_lines(benchmark_fit.runs_of(model, rows))
        self.assertEqual(line, "built-in-ai less play-loop: +0.462 (standard error over seeds 0.000, of the model 0.258, "
                               "together 0.258)")

    def test_the_command_fits_writes_the_model_and_values_rows_with_it(self):
        with tempfile.TemporaryDirectory() as d:
            rows, model = Path(d) / "whole.jsonl", Path(d) / "model.json"
            rows.write_text("".join(json.dumps(r) + "\n" for r in Fit().games()))
            self.assertEqual(benchmark_fit.main(["--fit", str(rows), "--features", "score", "--model", str(model)]), 0)
            kept = json.loads(model.read_text())
            self.assertEqual((kept["features"], kept["games"], kept["points"]), (["score"], 40, 120))
            self.assertEqual(len(kept["left_out_coefs"]), 40, "one fit a game left out: the model's own doubt")
            self.assertEqual(benchmark_fit.main(["--model", str(model), "--value", str(rows)]), 0)
            self.assertEqual(benchmark_fit.main(["--fit", str(rows), "--features", "score", "--turns", "100", "150", "--model", str(model)]), 0)
            kept = json.loads(model.read_text())
            self.assertEqual((kept["turns"], kept["points"]), ([100, 150], 80), "the points read at turn 50 are not fitted")

    def test_fewer_than_three_decided_games_is_nothing_to_fit(self):
        with tempfile.TemporaryDirectory() as d:
            rows = Path(d) / "two.jsonl"
            rows.write_text(json.dumps({"seat": 0, "ai_finishes": [game(0, True, [point(0, 10, 10)])]}) + "\n")
            self.assertEqual(benchmark_fit.main(["--fit", str(rows)]), 2)


if __name__ == "__main__":
    unittest.main()
