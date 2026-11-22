"""scripts/benchmark_save.py: a starting save of the benchmark made by one command, and its manifest (GitLab #194).

No game: the game's answers are scripted. What is checked is what the command sends, what it refuses, and what a
manifest says.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import benchmark_run
import benchmark_save


def player(pid, civ, human=False, alive=True):
    return {"id": pid, "civ": civ, "human": human, "alive": alive, "team": pid, "turn_active": human, "score": 10}


def read(turn=0, slots=(3, 1, 4, 4), winner=-1, players=None):
    return {"turn": turn, "state": 0, "winner": winner, "victory": "", "auto": 0, "active": 0, "max_turns": 0,
            "handicap": "HANDICAP_PRINCE", "speed": "GAMESPEED_QUICK", "slots": list(slots),
            "players": players or [player(0, "the Celts", human=True), player(1, "Austria")]}


SETTINGS = {"world_size": "WORLDSIZE_DUEL", "map_script": "Assets\\Maps\\pangaea.lua", "seat_row": "HANDICAP_AI_DEFAULT",
            "victories": ["VICTORY_SPACE_RACE", "VICTORY_DOMINATION", "VICTORY_CULTURAL", "VICTORY_DIPLOMATIC"],
            "start_era": "ERA_ANCIENT", "city_states": 4, "build": "1.0.3.279(130961)"}


class FakeGame:
    def __init__(self, reads=None, loaded=None):
        self.reads = reads or read()
        self.loaded = loaded or {"ok": True}
        self.sent: list[str] = []
        self.left = 0

    def load_save(self, name):
        self.sent.append(f"load {name}")
        return self.loaded

    def start_single_player(self, **kw):
        self.sent.append(f"host {json.dumps(kw, sort_keys=True)}")
        return {"world_size": kw["world_size"], "victories": "VICTORY_TIME,VICTORY_DOMINATION"}

    def q(self, code):
        self.sent.append(code)
        if "players = {}" in code:
            return self.reads
        if "world_size" in code:
            return dict(SETTINGS)
        return {"seat_row": "HANDICAP_AI_DEFAULT", "time_victory": False, "max_turns": 0}

    def leave_to_main_menu(self):
        self.left += 1
        return {"ok": True}

    def has_state(self, name):
        return False

    def front_end_screen(self):
        return "MainMenu"


class Folders(unittest.TestCase):
    """The game's save folder and the folder of kept saves, both temporary."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.game_saves, self.kept = Path(self.tmp.name) / "single", Path(self.tmp.name) / "kept"
        self.game_saves.mkdir()
        patch = mock.patch.dict(os.environ, {"CIV5_SAVES_DIR": str(self.game_saves)})
        patch.start()
        self.addCleanup(patch.stop)

    def a_save(self, name, text="a save"):
        (self.game_saves / f"{name}.Civ5Save").write_text(text)

    def main(self, g, *argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("harness.game.Game", return_value=g), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = benchmark_save.main([*argv, "--dir", str(self.kept)])
        return code, out.getvalue(), err.getvalue()


class Describe(Folders):
    def test_a_manifest_says_what_the_loaded_save_holds_and_the_save_is_kept_beside_it(self):
        self.a_save("board-x")
        g = FakeGame()
        code, _out, err = self.main(g, "--describe", "board-x")
        self.assertEqual(code, 0, err)
        m = json.loads((self.kept / "board-x.json").read_text())
        self.assertEqual((m["id"], m["save"], m["kind"], m["turn"], m["seat"]), ("board-x", "board-x.Civ5Save", "opening", 0, 0))
        self.assertEqual((m["civilization"], m["opponents"]), ("the Celts", ["Austria"]))
        self.assertEqual((m["turns"], m["seeds"], m["baseline"]), (100, 20, None))
        self.assertEqual(m["settings"]["seat_row"], "HANDICAP_AI_DEFAULT")
        self.assertIs(m["settings"]["time_victory"], False, "Time is not among the victories the save holds")
        self.assertEqual(m["game_build"], "1.0.3.279(130961)")
        self.assertNotIn("build", m["settings"])
        self.assertEqual(m["sha256"], benchmark_save.sha256(self.kept / "board-x.Civ5Save"))
        self.assertEqual((self.kept / "board-x.Civ5Save").read_text(), "a save")
        self.assertEqual(g.left, 1, "the game is left for the main menu after the read")

    def test_a_save_past_turn_0_needs_its_kind_said(self):
        self.a_save("board-x-t100")
        code, _out, err = self.main(FakeGame(read(turn=100)), "--describe", "board-x-t100")
        self.assertEqual(code, 2)
        self.assertIn("--kind middle or --kind late", err)
        self.assertFalse((self.kept / "board-x-t100.json").exists())
        code, _out, err = self.main(FakeGame(read(turn=100)), "--describe", "board-x-t100", "--kind", "middle")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads((self.kept / "board-x-t100.json").read_text())["kind"], "middle")

    def test_a_save_no_player_could_be_given_is_refused_and_the_game_is_left(self):
        for reads, why in ((read(slots=(3, 1, 1, 1)), "observer slot"),
                           (read(players=[player(0, "the Celts", human=True, alive=False), player(1, "Austria")]), "dead"),
                           (read(winner=1), "already won"),
                           (read(players=[player(0, "the Celts"), player(1, "Austria")]), "0 human seats")):
            g = FakeGame(reads)
            with self.assertRaises(benchmark_run.Refused) as e:
                benchmark_save.describe(g, "board-x")
            self.assertIn(why, str(e.exception))
            self.assertEqual(g.left, 1)

    def test_a_save_that_does_not_load_is_refused(self):
        with self.assertRaises(benchmark_run.Refused):
            benchmark_save.describe(FakeGame(loaded={"ok": False, "err": "no such save"}), "nothing")


class Host(Folders):
    def test_one_command_hosts_with_every_setting_said_carries_the_terms_saves_and_reads_the_save_back(self):
        g = FakeGame()

        def save_game(_g, name):
            self.a_save(name, "hosted")
            g.sent.append(f"save {name}")
            return name

        origin = benchmark_save.host(g, "board-e", "CIVILIZATION_CELTS", "WORLDSIZE_DUEL", "pangaea", "GAMESPEED_QUICK",
                                     "HANDICAP_PRINCE", save_game=save_game)
        hosted = json.loads(g.sent[0].removeprefix("host "))
        self.assertEqual(hosted, {"all_victories": True, "civilization": "CIVILIZATION_CELTS", "game_speed": "GAMESPEED_QUICK",
                                  "handicap": "HANDICAP_PRINCE", "map_script": "pangaea", "world_size": "WORLDSIZE_DUEL"})
        terms = next(s for s in g.sent if "HANDICAP_AI_DEFAULT.ID" in s)
        self.assertIn("PreGame.SetHandicap(0,", terms)
        self.assertIn("Game.SetVictoryValid(GameInfoTypes.VICTORY_TIME, false)", terms)
        self.assertLess(g.sent.index(terms), g.sent.index("save board-e"), "the terms are in the game before it is saved")
        self.assertEqual(origin["how"], "hosted")
        self.assertEqual(origin["setup_screen"]["world_size"], "WORLDSIZE_DUEL")
        self.assertEqual(g.left, 1)

    def test_a_hosted_game_with_no_observer_slot_is_not_saved(self):
        g = FakeGame(read(slots=(3, 1)))
        with self.assertRaises(benchmark_run.Refused):
            benchmark_save.host(g, "board-e", "CIVILIZATION_CELTS", "WORLDSIZE_DUEL", None, "GAMESPEED_QUICK",
                                "HANDICAP_PRINCE", save_game=lambda *_: self.fail("saved"))
        self.assertEqual(g.left, 1)

    def test_host_needs_a_civilization(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            benchmark_save.main(["--host", "board-e"])


class Cut(Folders):
    def test_the_built_in_ai_plays_the_turns_on_the_seed_and_the_origin_says_so(self):
        asked = {}

        def play(_g, save, turns, skip=0, end_save=None, say=None):
            asked.update(save=save, turns=turns, skip=skip, end_save=end_save)
            return {"end_reason": "all_turns_played", "end_save": end_save, "seconds": 210.0, "turns_played": turns}

        origin = benchmark_save.cut(FakeGame(), "board-d", "board-d-t100", 100, seed=2, play=play)
        self.assertEqual(asked, {"save": "board-d", "turns": 100, "skip": 2 * benchmark_run.NUMBERS_A_SEED,
                                 "end_save": "board-d-t100"})
        self.assertEqual(origin, {"how": "cut", "from": "board-d", "played_by": "built-in-ai", "turns": 100, "seed": 2,
                                  "skip": 2 * benchmark_run.NUMBERS_A_SEED, "seconds": 210.0})

    def test_a_game_decided_inside_the_turns_is_no_starting_save(self):
        def play(*_a, **_kw):
            return {"end_reason": "game_won", "end_save": None, "turns_played": 61}

        with self.assertRaises(benchmark_run.Refused) as e:
            benchmark_save.cut(FakeGame(), "board-d", "board-d-t100", 100, play=play)
        self.assertIn("game_won, 61 of 100", str(e.exception))

    def test_cut_needs_the_save_and_the_turns(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            benchmark_save.main(["--cut", "board-d-t100", "--save", "board-d"])


class Install(Folders):
    def kept_save(self, name, text="kept"):
        self.kept.mkdir(exist_ok=True)
        (self.kept / f"{name}.Civ5Save").write_text(text)
        manifest = {"id": name, "save": f"{name}.Civ5Save", "sha256": benchmark_save.sha256(self.kept / f"{name}.Civ5Save")}
        (self.kept / f"{name}.json").write_text(json.dumps(manifest))

    def test_kept_saves_are_copied_to_the_games_folder_and_nothing_there_is_overwritten(self):
        self.kept_save("board-a")
        self.kept_save("board-b")
        self.kept_save("board-c")
        self.a_save("board-b", "kept")
        self.a_save("board-c", "someone else's file")
        lines = benchmark_save.install(self.kept)
        self.assertEqual(lines[0], "board-a: installed")
        self.assertEqual((self.game_saves / "board-a.Civ5Save").read_text(), "kept")
        self.assertEqual(lines[1], "board-b: there already")
        self.assertIn("left alone", lines[2])
        self.assertEqual((self.game_saves / "board-c.Civ5Save").read_text(), "someone else's file")

    def test_a_kept_save_that_is_not_its_manifests_is_not_installed(self):
        self.kept_save("board-a")
        (self.kept / "board-a.Civ5Save").write_text("changed since")
        self.assertIn("not installed", benchmark_save.install(self.kept)[0])
        self.assertFalse((self.game_saves / "board-a.Civ5Save").exists())


if __name__ == "__main__":
    unittest.main()
