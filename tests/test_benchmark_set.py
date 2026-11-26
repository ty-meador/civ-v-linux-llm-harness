"""scripts/benchmark_set.py: the list of benchmarks, and the words each one's player is told.

A benchmark is a starting save and what is asked on it (docs/BENCHMARK.md, "The classes of benchmark, and what a
run is told"). No game is needed.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import benchmark_set

VICTORY = {"id": "start-a-science", "class": "victory", "save": "start-a", "victory": "VICTORY_SPACE_RACE", "briefing": "science.md"}
SCENARIO = {"id": "scenario-x", "class": "scenario", "save": "scenario-x", "won_by": "goal",
            "victories": ["VICTORY_DOMINATION"], "turn_limit": 50, "texts": "scenario-x.md"}
NAMES = {"VICTORY_DOMINATION": "Domination", "VICTORY_SPACE_RACE": "Science", "VICTORY_CULTURAL": "Cultural",
         "VICTORY_DIPLOMATIC": "Diplomatic"}


class TheList(unittest.TestCase):
    def setUp(self):
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def written(self, *entries, **more) -> Path:
        path = self.dir / "benchmarks.json"
        path.write_text(json.dumps({"format": benchmark_set.FORMAT, "benchmarks": list(entries), **more}))
        return path

    def refused(self, *entries, **more) -> str:
        with self.assertRaises(benchmark_set.Refused) as caught:
            benchmark_set.read(self.written(*entries, **more))
        return str(caught.exception)

    def test_the_benchmarks_are_read_by_id_in_the_lists_order(self):
        self.assertEqual(list(benchmark_set.read(self.written(VICTORY, SCENARIO))), ["start-a-science", "scenario-x"])

    def test_a_victory_benchmark_asks_for_one_of_the_four_victory_types(self):
        self.assertIn("asks for one of VICTORY_DOMINATION", self.refused({**VICTORY, "victory": "VICTORY_TIME"}))

    def test_a_benchmark_that_tells_its_player_nothing_is_refused(self):
        no_briefing = {k: v for k, v in VICTORY.items() if k != "briefing"}
        no_texts = {k: v for k, v in SCENARIO.items() if k != "texts"}
        self.assertIn("no briefing", self.refused(no_briefing))
        self.assertIn("no texts", self.refused(no_texts))

    def test_a_scenario_won_by_a_goal_needs_its_turn_limit_and_the_victory_types_its_win_is_named_by(self):
        said = self.refused({k: v for k, v in SCENARIO.items() if k not in ("turn_limit", "victories")})
        self.assertIn("needs its turn_limit", said)
        self.assertIn("needs the victory types the game names its win by", said)
        self.assertIn("needs the victory types", self.refused({**SCENARIO, "victories": []}))
        points = {k: v for k, v in SCENARIO.items() if k not in ("turn_limit", "victories")} | {"won_by": "points"}
        self.assertEqual(list(benchmark_set.read(self.written(points))), ["scenario-x"])

    def test_an_unknown_class_an_unknown_key_and_a_name_that_is_no_file_name_are_said(self):
        self.assertIn("class is none of open, survival, victory, scenario", self.refused({**VICTORY, "class": "time"}))
        self.assertIn("unknown key score", self.refused({**VICTORY, "score": 1}))
        self.assertIn("id is not a name", self.refused({**VICTORY, "id": "a/b"}))
        self.assertIn("briefing is not a file under saves/benchmark", self.refused({**VICTORY, "briefing": "../x.md"}))

    def test_one_id_twice_and_a_file_of_another_format_are_refused(self):
        self.assertIn("start-a-science is there more than once", self.refused(VICTORY, VICTORY))
        self.assertIn("not a list of benchmarks of format 1", self.refused(VICTORY, format=2))

    def test_a_benchmark_the_list_does_not_have_is_refused_with_the_ones_it_has(self):
        with self.assertRaises(benchmark_set.Refused) as caught:
            benchmark_set.named("start-b", self.written(VICTORY))
        self.assertIn("no benchmark 'start-b'", str(caught.exception))
        self.assertIn("there are: start-a-science", str(caught.exception))

    def test_a_file_a_benchmark_names_and_the_folder_does_not_hold_is_said(self):
        self.assertEqual(benchmark_set.missing_of({"start-a-science": VICTORY}, self.dir),
                         ["start-a-science: no start-a.Civ5Save", "start-a-science: no start-a.json", "start-a-science: no science.md"])
        with self.assertRaises(benchmark_set.Refused):
            benchmark_set.file_of(VICTORY, "briefing", self.dir)
        (self.dir / "science.md").write_text("win by science")
        self.assertEqual(benchmark_set.file_of(VICTORY, "briefing", self.dir), self.dir / "science.md")


class TheKeptBenchmarks(unittest.TestCase):
    """saves/benchmark/benchmarks.json as it is checked in."""

    def setUp(self):
        self.benchmarks = benchmark_set.read()
        self.victory = [b for b in self.benchmarks.values() if b["class"] == "victory"]

    def words(self, benchmark: dict) -> str:
        """The briefing as one line: where its lines break is not what it says."""
        return " ".join(benchmark_set.file_of(benchmark, "briefing").read_text().split())

    def test_every_file_a_benchmark_names_is_checked_in(self):
        self.assertEqual(benchmark_set.missing_of(self.benchmarks), [])

    def test_each_of_the_four_victory_types_is_asked_once_on_one_starting_save(self):
        self.assertEqual(sorted(b["victory"] for b in self.victory), sorted(benchmark_set.VICTORY_TYPES))
        self.assertEqual({b["save"] for b in self.victory}, {"small-king-poland-b"})

    def test_the_open_game_is_played_on_the_victory_types_starting_save(self):
        self.assertEqual([b["save"] for b in self.benchmarks.values() if b["class"] == "open"], ["small-king-poland-b"])

    def test_a_victory_briefing_names_its_type_and_says_that_a_win_by_another_is_a_total_failure(self):
        for benchmark in self.victory:
            words, name = self.words(benchmark), NAMES[benchmark["victory"]]
            self.assertIn(f"wins the game by a {name} victory", words)
            self.assertIn("A win by another victory type is a total failure", words)
            self.assertIn("every other civilization can still win by any of the four", words)

    def test_the_four_victory_briefings_are_the_same_words_but_for_the_victory_types_named(self):
        def nameless(benchmark):
            words = self.words(benchmark)
            for name in NAMES.values():
                words = words.replace(name, "X")
            return words
        self.assertEqual(len({nameless(b) for b in self.victory}), 1)

    def test_a_briefing_that_says_how_long_the_run_is_says_the_starting_saves_own_turns(self):
        for benchmark in self.benchmarks.values():
            if "briefing" not in benchmark or "turns long" not in self.words(benchmark):
                continue
            turns = json.loads((benchmark_set.KEPT / f"{benchmark['save']}.json").read_text())["turns"]
            self.assertIn(f"The run is {turns} turns long", self.words(benchmark), benchmark["id"])

    def test_the_survival_briefing_warns_as_the_owner_worded_it(self):
        [venice] = [b for b in self.benchmarks.values() if b["class"] == "survival"]
        self.assertIn("Venice cannot build Settlers. Your neighbours are militarily aggressive and will attack.", self.words(venice))


if __name__ == "__main__":
    unittest.main()
