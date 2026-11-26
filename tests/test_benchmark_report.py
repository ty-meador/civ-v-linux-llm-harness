"""scripts/benchmark_report.py: a scores file set beside the recordings it scores, and the report of them.

No game and no scorer: the recordings are packed here with a row and nothing else, and the scores are written by
hand, as a file carried back from the scoring machine would hold them.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("benchmark_report", ROOT / "scripts" / "benchmark_report.py")
report = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(report)
rec = report.recording()

SEAT_FOLDER = "/home/someone/bench-seats/seat"


def a_row(player="codex/x", run=0, save="start-a", **kw):
    row = {"player": player, "command": ["loop", "--dir", SEAT_FOLDER], "save": save, "turns_asked": 100,
           "turns_played": 100, "result": "finished", "end_reason": "all_turns_played", "seconds": 500.0, "run": run,
           "cost": {"calls": 40, "tokens": {"new_in": 1000, "cache_read": 3000, "cache_write": 0, "out": 200}}}
    row.update(kw)
    if player is None:
        del row["player"], row["cost"]      # the built-in AI's row names no player and counts no calls
    return row


class Files(unittest.TestCase):
    def setUp(self):
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.recordings = self.dir / "recordings"

    def packed(self, row=None, folder="", **kw) -> dict:
        """A recording of `row` under the recordings folder, as a row of a scores file with no score in it yet."""
        row = row or a_row(**kw)
        manifest = {"format": rec.FORMAT, "name": rec.name_of(row), "player": rec.player_of(row), "seed": row.get("run", 0),
                    "starting_save": {"id": row["save"]}, "made_with": {"harness": "2.20.0"}, "files": {},
                    **({"benchmark": row["benchmark"]} if "benchmark" in row else {})}
        path = self.recordings / folder / (manifest["name"] + rec.SUFFIX)
        rec.write(path, {rec.MANIFEST: json.dumps(manifest).encode(), rec.ROW: json.dumps(row).encode()})
        return {"recording": manifest["name"], "sha256": rec.sha256(path.read_bytes())}

    def scores(self, rows, name="scores.json", **kw) -> Path:
        path = self.dir / name
        path.write_text(json.dumps({"format": report.SCORES_FORMAT, "scores": rows, **kw}))
        return path

    def report(self, *rows) -> dict:
        found, not_read = report.recordings_under([self.recordings])
        return report.report_of(report.latest_scores([report.read_scores(self.scores(list(rows)))]), found, not_read)

    def run_main(self, *argv) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = report.main([str(a) for a in argv])
        return status, out.getvalue(), err.getvalue()


class ScoresFile(Files):
    def refused(self, row, **kw) -> str:
        with self.assertRaises(report.Refused) as caught:
            report.read_scores(self.scores([row], **kw))
        return str(caught.exception)

    def test_a_row_with_a_score_or_with_the_reason_it_has_none_is_read(self):
        scored, left = {**self.packed(), "score": 0.5}, {**self.packed(run=1), "not_scored": "no game file in it"}
        self.assertEqual(report.read_scores(self.scores([scored, left])), [scored, left])

    def test_a_row_may_carry_the_runs_score_turn_by_turn(self):
        row = {**self.packed(), "score": 0.5, "by_turn": [[1, 0.5], [2, 0.48], [10, 0.61]]}
        self.assertEqual(report.read_scores(self.scores([row])), [row])

    def test_a_row_that_holds_more_than_scores_is_refused(self):
        said = self.refused({**self.packed(), "score": 0.5, "figures": {"gold": 0.4}})
        self.assertIn("row 1: holds more than scores: figures", said)

    def test_a_row_needs_one_of_a_score_and_a_reason(self):
        neither, both = self.packed(), {**self.packed(), "score": 0.5, "not_scored": "why"}
        for row in (neither, both):
            self.assertIn("needs a score or a not_scored, and not both", self.refused(row))

    def test_a_score_that_is_no_number_and_a_hash_that_is_no_hash_are_said(self):
        for score in ("0.5", True, float("nan"), None):
            self.assertIn("score is not a number", self.refused({**self.packed(), "score": score}))
        self.assertIn("sha256 is not", self.refused({"recording": "a", "sha256": "abc", "score": 0.5}))
        self.assertIn("names no recording", self.refused({"recording": "", "sha256": "0" * 64, "score": 0.5}))

    def test_scores_by_turn_go_up_by_turn_and_go_with_a_score(self):
        base = self.packed()
        self.assertIn("turns do not go up", self.refused({**base, "score": 0.5, "by_turn": [[2, 0.5], [2, 0.6]]}))
        self.assertIn("not a list of [turn, score]", self.refused({**base, "score": 0.5, "by_turn": [[1, "x"]]}))
        self.assertIn("by_turn goes with a score", self.refused({**base, "not_scored": "why", "by_turn": [[1, 0.5]]}))

    def test_a_file_of_another_format_or_that_is_no_json_is_refused(self):
        self.assertIn("not a scores file of format 1", self.refused({**self.packed(), "score": 0.5}, format=2))
        path = self.dir / "broken.json"
        path.write_text("{")
        with self.assertRaisesRegex(report.Refused, "not JSON"):
            report.read_scores(path)
        with self.assertRaisesRegex(report.Refused, "cannot be read"):
            report.read_scores(self.dir / "absent.json")

    def test_a_recording_with_two_rows_in_one_file_is_refused(self):
        earlier, later = self.packed(folder="first", seconds=100.0), self.packed(folder="again", seconds=900.0)
        with self.assertRaisesRegex(report.Refused, "start-a--codex-x-seed0 has more than one row"):
            report.read_scores(self.scores([{**earlier, "score": 0.4}, {**later, "score": 0.6}]))

    def test_a_run_packed_and_scored_again_is_one_run_with_the_score_of_the_last_file(self):
        earlier, later = self.packed(folder="first", seconds=100.0), self.packed(folder="again", seconds=900.0)
        first_week = self.scores([{**earlier, "score": 0.4}], name="week-1.json")
        second_week = self.scores([{**later, "score": 0.6}], name="week-2.json")
        found, not_read = report.recordings_under([self.recordings])
        latest = report.latest_scores([report.read_scores(first_week), report.read_scores(second_week)])
        made = report.report_of(latest, found, not_read)
        [line] = made["benchmarks"][0]["players"]
        self.assertEqual((line["runs"], line["score"], line["seconds_a_turn"]), (1, 0.6, 9.0))
        self.assertEqual(made["no_score"], [f"{earlier['recording']} ({earlier['sha256'][:12]})"])


class Report(Files):
    def test_a_players_score_is_the_mean_of_its_runs_with_its_error_over_them(self):
        runs = [{**self.packed(run=n), "score": s} for n, s in enumerate((0.4, 0.5, 0.6))]
        [benchmark] = self.report(*runs)["benchmarks"]
        [line] = benchmark["players"]
        self.assertEqual((benchmark["starting_save"], benchmark["turns_asked"]), ("start-a", 100))
        self.assertEqual((line["player"], line["runs"], line["finished"]), ("codex/x", 3, 3))
        self.assertAlmostEqual(line["score"], 0.5)
        self.assertAlmostEqual(line["spread"], 0.1)
        self.assertAlmostEqual(line["error"], 0.1 / 3 ** 0.5)
        self.assertEqual(line["runs_for_target_error"], 4)      # (0.1 / 0.05) squared
        self.assertEqual([r["seed"] for r in line["recordings"]], [0, 1, 2])

    def test_one_run_is_a_score_with_no_error(self):
        [benchmark] = self.report({**self.packed(), "score": 0.5})["benchmarks"]
        [line] = benchmark["players"]
        self.assertEqual((line["score"], line["error"], line["spread"], line["runs_for_target_error"]), (0.5, None, None, None))

    def test_the_built_in_ai_stands_in_the_same_table_as_the_reference(self):
        model, engine = {**self.packed(), "score": 0.4}, {**self.packed(player=None), "score": 0.6}
        [benchmark] = self.report(model, engine)["benchmarks"]
        self.assertEqual([(p["player"], p["reference"]) for p in benchmark["players"]],
                         [("built-in-ai", True), ("codex/x", False)])
        engine_line = benchmark["players"][0]
        self.assertEqual((engine_line["tokens_read_a_turn"], engine_line["tokens_written_a_turn"]), (None, None))
        self.assertEqual(engine_line["seconds_a_turn"], 5.0)

    def test_runs_of_another_number_of_turns_or_another_save_are_another_table(self):
        rows = [{**self.packed(), "score": 0.5}, {**self.packed(run=1, turns_asked=250), "score": 0.7},
                {**self.packed(save="start-b"), "score": 0.3}]
        self.assertEqual([(b["starting_save"], b["turns_asked"]) for b in self.report(*rows)["benchmarks"]],
                         [("start-a", 100), ("start-a", 250), ("start-b", 100)])

    def test_two_benchmarks_of_one_starting_save_are_two_tables(self):
        """A run that names no benchmark is of its starting save, as every run was before a save carried several."""
        rows = [{**self.packed(), "score": 0.5}, {**self.packed(benchmark="start-a-science"), "score": 0.9},
                {**self.packed(benchmark="start-a-culture"), "score": 0.0}]
        made = self.report(*rows)
        self.assertEqual([(b["benchmark"], b["starting_save"]) for b in made["benchmarks"]],
                         [("start-a", "start-a"), ("start-a-culture", "start-a"), ("start-a-science", "start-a")])
        self.assertIn("## start-a-science, 100 turns asked", report.markdown_of(made))

    def test_tokens_and_seconds_are_over_the_turns_played_and_runs_that_did_not_finish_are_counted(self):
        whole = {**self.packed(), "score": 0.5}
        stopped = {**self.packed(run=1, turns_played=50, seconds=400.0, result="did_not_finish", end_reason="timeout",
                                 cost={"calls": 9, "tokens": {"new_in": 500, "cache_read": 1500, "cache_write": 0, "out": 100}}),
                   "score": 0.2}
        [line] = self.report(whole, stopped)["benchmarks"][0]["players"]
        self.assertEqual((line["runs"], line["finished"]), (2, 1))
        self.assertAlmostEqual(line["seconds_a_turn"], 900.0 / 150)
        self.assertAlmostEqual(line["tokens_read_a_turn"], 6000 / 150)
        self.assertAlmostEqual(line["tokens_written_a_turn"], 300 / 150)

    def test_a_score_is_set_beside_the_file_of_its_hash_among_files_of_one_name(self):
        earlier = self.packed(folder="first", seconds=100.0)
        later = self.packed(folder="again", seconds=900.0)
        self.assertEqual(earlier["recording"], later["recording"])
        [line] = self.report({**later, "score": 0.5})["benchmarks"][0]["players"]
        self.assertEqual(line["seconds_a_turn"], 9.0)

    def test_a_score_with_no_recording_here_is_said_and_stands_in_no_table(self):
        gone = {"recording": "start-a--codex-x-seed7", "sha256": "0" * 64, "score": 0.5}
        renamed = {**self.packed(), "recording": "another-name", "score": 0.5}
        made = self.report(gone, renamed)
        self.assertEqual(made["benchmarks"], [])
        self.assertEqual([(r["recording"], r["why"]) for r in made["no_recording"]],
                         [("another-name", "the file of that hash here is start-a--codex-x-seed0"),
                          ("start-a--codex-x-seed7", "no file of that hash here")])

    def test_a_recording_given_no_score_and_one_not_scored_yet_are_listed_apart(self):
        refused = {**self.packed(), "not_scored": "no game file in it"}
        waiting = self.packed(run=1)
        made = self.report(refused)
        self.assertEqual(made["benchmarks"], [])
        self.assertEqual([(r["recording"], r["why"]) for r in made["not_scored"]], [(refused["recording"], "no game file in it")])
        self.assertEqual(made["no_score"], [f"{waiting['recording']} ({waiting['sha256'][:12]})"])

    def test_a_scores_by_turn_are_kept_under_its_run(self):
        by_turn = [[1, 0.5], [2, 0.52]]
        [line] = self.report({**self.packed(), "score": 0.5, "by_turn": by_turn})["benchmarks"][0]["players"]
        self.assertEqual(line["recordings"][0]["by_turn"], by_turn)
        [plain] = self.report({**self.packed(), "score": 0.5})["benchmarks"][0]["players"]
        self.assertNotIn("by_turn", plain["recordings"][0])


class Command(Files):
    def test_the_report_is_printed_and_written_for_the_site_without_this_machines_paths(self):
        model, engine = {**self.packed(), "score": 0.4, "by_turn": [[1, 0.5]]}, {**self.packed(player=None), "score": 0.6}
        self.packed(run=1)
        out = self.dir / "report.json"
        status, printed, _ = self.run_main(self.scores([model, engine]), "--recordings", self.recordings, "--json", out)
        self.assertEqual(status, 0)
        self.assertIn("## start-a, 100 turns asked", printed)
        self.assertIn("| built-in-ai (the reference) | 1 | 0.600 | - | - | - | 1 of 1 | 5.0 | - | - |", printed)
        self.assertIn("| codex/x | 1 | 0.400 | - | - | - | 1 of 1 | 5.0 | 40 | 2 |", printed)
        self.assertIn("## Recordings here with no score", printed)
        written = out.read_text()
        self.assertEqual(sorted(json.loads(written)), ["benchmarks", "format", "not_scored", "target_error"])
        self.assertIn('"by_turn"', written)
        for private in (str(self.dir), SEAT_FOLDER, "command"):
            self.assertNotIn(private, written)

    def test_the_same_scores_and_recordings_write_the_same_report(self):
        rows = [{**self.packed(run=n), "score": 0.1 * n} for n in range(3)]
        first = self.run_main(self.scores(rows), "--recordings", self.recordings)
        again = self.run_main(self.scores(rows[::-1], name="again.json"), "--recordings", self.recordings)
        self.assertEqual(first, again)

    def test_a_score_with_no_recording_and_a_file_that_is_no_recording_end_with_1(self):
        status, printed, _ = self.run_main(self.scores([{"recording": "gone", "sha256": "0" * 64, "score": 0.5}]),
                                           "--recordings", self.recordings)
        self.assertEqual(status, 1)
        self.assertIn("- gone (000000000000): no file of that hash here", printed)
        scored = {**self.packed(), "score": 0.5}
        (self.recordings / ("broken" + rec.SUFFIX)).write_bytes(b"not a zip")
        status, printed, _ = self.run_main(self.scores([scored]), "--recordings", self.recordings, self.dir / "absent")
        self.assertEqual(status, 1)
        self.assertIn("## Files that are no recording", printed)
        self.assertIn("not a readable zip", printed)
        self.assertIn("absent: no such folder or file", printed)

    def test_a_scores_file_that_cannot_be_read_ends_with_2_and_prints_no_report(self):
        path = self.dir / "broken.json"
        path.write_text("[]")
        status, printed, said = self.run_main(path, "--recordings", self.recordings)
        self.assertEqual((status, printed), (2, ""))
        self.assertIn("not a scores file of format 1", said)

    def test_a_recording_whose_row_is_another_run_is_not_reported(self):
        row = a_row()
        scored = self.packed(row=row)
        path = self.recordings / (scored["recording"] + rec.SUFFIX)
        manifest = {"format": rec.FORMAT, "name": "start-a--someone-else-seed0", "player": "someone/else", "seed": 0,
                    "starting_save": {"id": "start-a"}, "files": {}}
        rec.write(path, {rec.MANIFEST: json.dumps(manifest).encode(), rec.ROW: json.dumps(row).encode()})
        status, printed, _ = self.run_main(self.scores([{"recording": manifest["name"], "sha256": rec.sha256(path.read_bytes()),
                                                         "score": 0.9}]), "--recordings", self.recordings)
        self.assertEqual(status, 1)
        self.assertIn("the row is", printed)
        self.assertNotIn("| someone/else |", printed)


if __name__ == "__main__":
    unittest.main()
