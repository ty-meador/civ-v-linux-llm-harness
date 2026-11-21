"""scripts/benchmark_seed_likeness.py: whether runs on seeds next to each other ended more alike than runs on seeds
far apart. No game: rows are made by hand."""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import benchmark_run
import benchmark_seed_likeness as sl


def player(pid, **kw):
    row = {"id": pid, "alive": True, **{k: 10 for k in benchmark_run.INDICATORS}, **{k: 0 for k in benchmark_run.ROUTES}}
    row.update(kw)
    return row


def run(seed, score, result="finished", **kw):
    """A run whose turns ended with the seat on `score` of 100 between the two players."""
    return {"run": seed, "seat": 0, "result": result,
            "end_point": {"turn": 100, "players": [player(0, score=score, **kw), player(1, score=100 - score)]}}


class Points(unittest.TestCase):
    def test_finished_runs_are_read_at_the_end_of_their_turns_in_the_order_of_the_seeds(self):
        pts = sl.points([run(2, 60), run(0, 40), run(1, 50, result="refused")])
        self.assertEqual([(seed, share["score"]) for seed, share in pts], [(0, 0.4), (2, 0.6)])

    def test_a_run_with_no_turns_played_is_left_out(self):
        self.assertEqual(sl.points([{"run": 0, "seat": 0, "result": "finished"}]), [])


class Distances(unittest.TestCase):
    def test_a_pair_on_the_same_shares_is_at_no_distance_and_an_indicator_all_level_on_is_left_out(self):
        d = sl.distances(sl.points([run(0, 40), run(1, 40), run(2, 60)]))
        self.assertEqual(d[0][1], 0)
        self.assertGreater(d[0][2], 0)
        self.assertEqual(d[0][2], d[2][0])

    def test_each_indicator_is_measured_in_its_own_spread(self):
        """Score shares 0.4, 0.6 and gold shares 0.1, 0.9 are the same two runs one spread apart in each."""
        one = sl.distances(sl.points([run(0, 40), run(1, 60)]))[0][1]
        two = sl.distances(sl.points([run(0, 40, gold=1), run(1, 60, gold=90)]))[0][1]
        self.assertAlmostEqual(two, 2 * one)


class Likeness(unittest.TestCase):
    D = [[0, 1, 4, 4],
         [1, 0, 4, 4],
         [4, 4, 0, 1],
         [4, 4, 1, 0]]

    def test_likeness_is_one_less_the_near_pairs_mean_distance_over_the_other_pairs(self):
        # 1 apart: (0,1)=1, (1,2)=4, (2,3)=1, mean 2; the other three pairs are all 4
        self.assertAlmostEqual(sl.likeness(self.D, [0, 1, 2, 3], 1), 0.5)
        # in the order 0, 2, 1, 3 every neighbour is a far one: mean 4 against (1+4+1)/3
        self.assertAlmostEqual(sl.likeness(self.D, [0, 2, 1, 3], 1), -1.0)

    def test_the_gap_says_how_far_apart_in_the_order_the_pairs_are(self):
        # 2 apart: (0,2)=4, (1,3)=4; the others 1, 4, 4, 1
        self.assertAlmostEqual(sl.likeness(self.D, [0, 1, 2, 3], 2), 1 - 4 / 2.5)


class Lines(unittest.TestCase):
    def test_too_few_runs_say_so(self):
        self.assertEqual(sl.likeness_lines([run(0, 40), run(1, 50)], "rows"), ["rows: 2 finished runs, too few"])

    def test_runs_all_on_one_position_are_counted_and_not_compared(self):
        lines = sl.likeness_lines([run(i, 50) for i in range(4)], "rows")
        self.assertEqual(lines, ["rows: 4 finished runs, seeds 0 to 3", "  pairs that ended on the same shares: 6"])

    def test_seeds_that_drift_with_their_number_are_alike_next_to_each_other_as_few_orderings_are(self):
        lines = sl.likeness_lines([run(i, 30 + 4 * i) for i in range(10)], "rows", shuffles=400, rng=random.Random(0))
        self.assertEqual(lines[0], "rows: 10 finished runs, seeds 0 to 9")
        self.assertIn("seeds 1 apart (9 pairs): likeness +0.9", lines[2])
        self.assertIn("0.000 of 400 random orderings", lines[2])
        self.assertEqual(len(lines), 5)

    def test_seeds_in_no_order_are_not(self):
        scores = [52, 31, 66, 45, 38, 60, 49, 33, 57, 41]
        lines = sl.likeness_lines([run(i, s) for i, s in enumerate(scores)], "rows", shuffles=400, rng=random.Random(0))
        share = float(lines[2].split("; ")[1].split()[0])
        self.assertGreater(share, 0.2)


if __name__ == "__main__":
    unittest.main()
