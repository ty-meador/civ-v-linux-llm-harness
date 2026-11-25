"""scripts/benchmark_run.py against a fake Game: what it refuses, when a run ends, what a row says, and the notebook
a player's command plays with.

Live 2026-11-16 (docs/BENCHMARK.md, "Autoplay, checked live"): `Game.SetAIAutoPlay` on a duel whose unused slots
were closed made the seat the observer and destroyed its Settler and Warrior in the same call, with no error; a
win did not stop a run; and after the seat died the game played turns by itself. The runner refuses the first
before it changes anything, and for the other two it watches the run and leaves the game itself.
"""
from __future__ import annotations

import importlib.util
import contextlib
import hashlib
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

_spec = importlib.util.spec_from_file_location("benchmark_run", ROOT / "scripts" / "benchmark_run.py")
benchmark_run = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(benchmark_run)


def player(pid, human=False, alive=True, **kw):
    row = {"id": pid, "civ": f"civ{pid}", "alive": alive, "human": human}
    row.update({k: 10 for k in benchmark_run.INDICATORS})
    row.update({k: 0 for k in benchmark_run.ROUTES})
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
        if "return {skip" in code:
            return {"skip": 0}
        if "score_parts" in code:
            return self.played_reply
        if "ExitToMainMenu" in code:
            return {"ok": True}
        if "c.hooked" in code or code == benchmark_run.CHECKPOINT_OFF:
            return {"ok": True}
        if code == benchmark_run.SAVE_NOW:
            if self.save_now_writes:
                self.write_quick("asked at the end")
            return {"ok": True, "turn": 248}
        now = self.polls.pop(0)
        if now.get("wrote"):
            self.write_quick(now["wrote"])
        return now

    def write_quick(self, text):
        """The game's quick save, written again: another file each time, by its time."""
        self.writes += 1
        self.quick_file.parent.mkdir(parents=True, exist_ok=True)
        self.quick_file.write_text(text)
        os.utime(self.quick_file, ns=(self.writes * 10 ** 9, self.writes * 10 ** 9))

    writes = 0
    save_now_writes = True   # False: the game answers the save asked at the game's end and writes no file

    played_reply = None   # what the game answers the read of rule 7's figures; None stands for a read that failed

    def leave_to_main_menu(self):
        self.left += 1
        return self.leave_reply

    leave_reply = {"ok": True}

    def has_state(self, name):
        self.looked += 1
        return name == "InGame" and self.looked <= self.up_for

    looked = 0
    up_for = 0   # how many looks still find the game up after an exit that answered nothing

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
    return benchmark_run.run_once(g, "save", 10, sleep=clock.sleep, clock=clock, **kw)


class Refusals(unittest.TestCase):
    def test_a_save_with_no_observer_slot_is_refused_before_the_engine_is_asked_anything(self):
        g = FakeGame([read(slots=(3, 1, 2, 2))])
        with self.assertRaisesRegex(benchmark_run.Refused, "observer slot"):
            run(g)
        self.assertFalse(any("SetAIAutoPlay" in s for s in g.sent), "the call that destroys the seat was sent")
        self.assertEqual(g.left, 1, "the loaded game was left on screen")

    def test_the_seats_own_slot_does_not_count_as_the_observer_slot(self):
        with self.assertRaises(benchmark_run.Refused):
            benchmark_run.check_observer_slot(read(slots=(4, 1, 2)), 0)
        benchmark_run.check_observer_slot(read(slots=(3, 1, 4)), 0)

    def test_two_human_seats_are_refused(self):
        g = FakeGame([read(players=[player(0, human=True), player(1, human=True)])])
        with self.assertRaisesRegex(benchmark_run.Refused, "2 human seats"):
            run(g)
        self.assertEqual(g.left, 1)

    def test_a_seat_that_is_not_the_saves_human_is_refused(self):
        with self.assertRaisesRegex(benchmark_run.Refused, "seat 1 is not"):
            benchmark_run.find_seat(read(), 1)
        self.assertEqual(benchmark_run.find_seat(read(), None), 0)

    def test_a_save_that_does_not_load_is_refused(self):
        g = FakeGame([], loaded={"ok": False, "err": "no save named 'save'"})
        with self.assertRaisesRegex(benchmark_run.Refused, "no save named"):
            run(g)


class Runs(unittest.TestCase):
    def test_turns_played_to_their_end_give_the_seat_before_and_after(self):
        after = read(turn=252, players=[player(0, human=True, score=140, cities=3), player(1, score=310)])
        g = FakeGame([read(), after], polls=[poll(243, 9), poll(243, 9), poll(251, 1), poll(252, 0)])
        said: list[str] = []
        row = run(g, say=said.append)
        self.assertEqual(row["end_reason"], "all_turns_played")
        self.assertEqual((row["turns_played"], row["seat"], row["handicap"]), (10, 0, "HANDICAP_EMPEROR"))
        self.assertEqual((row["start"]["values"]["score"], row["end"]["values"]["score"]), (100, 140))
        self.assertEqual(row["end"]["values"]["cities"], 3)
        self.assertEqual((row["end"]["place"], row["end"]["of"]), (2, 2))
        self.assertEqual(row["seconds"], 12.0)
        self.assertEqual(len(said), 3, "one line a new turn, none for a poll that saw the same turn")
        self.assertEqual(g.left, 1, "the game was not left for the main menu")
        self.assertEqual((row["end_point"]["turn"], [p["score"] for p in row["end_point"]["players"]]), (252, [140, 310]),
                         "every player where the turns ends: what a win-chance formula values it by")
        self.assertEqual(set(row["end_point"]["players"][1]), {"id", "alive", *benchmark_run.INDICATORS, *benchmark_run.ROUTES})
        json.dumps(row)

    def test_the_skip_comes_before_the_handover_and_the_seat_is_the_one_found(self):
        g = FakeGame([read(), read(turn=252)], polls=[poll(252, 0)])
        run(g, skip=34)
        start = next(s for s in g.sent if "SetAIAutoPlay" in s)
        self.assertIn("for _ = 1, 34 do Game.Rand(", start)
        self.assertLess(start.index("Game.Rand("), start.index("Game.SetAIAutoPlay(10, 0)"))

    def test_the_runs_own_terms_are_in_the_row(self):
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


class TheSeatHandedBack(unittest.TestCase):
    """benchmark_run.wait_for_the_seat: a save taken under the engine loads with one engine turn to play."""

    class Game:
        def __init__(self, looks):
            self.looks, self.asked = list(looks), 0

        def q(self, _code):
            self.asked += 1
            return self.looks.pop(0) if len(self.looks) > 1 else self.looks[0]

    def test_it_waits_until_the_count_is_0_and_a_moment_more(self):
        slept = []
        g = self.Game([{"auto": 1, "winner": -1, "active": 2}, {"auto": 1, "winner": -1, "active": 2}, {"auto": 0, "winner": -1, "active": 0}])
        look = benchmark_run.wait_for_the_seat(g, 0, poll=0.5, settle=2.0, sleep=slept.append, clock=lambda: 0.0)
        self.assertEqual((look["auto"], g.asked, slept), (0, 3, [0.5, 0.5, 2.0]))

    def test_an_engine_that_never_hands_back_is_waited_for_no_longer_than_asked(self):
        now = [0.0]
        def sleep(s):
            now[0] += s
        g = self.Game([{"auto": 5, "winner": -1, "active": 2}])
        look = benchmark_run.wait_for_the_seat(g, 0, wait=3.0, poll=1.0, settle=2.0, sleep=sleep, clock=lambda: now[0])
        self.assertEqual((look["auto"], g.asked, now[0]), (5, 3, 5.0))


class TheRunsOwnMaking(unittest.TestCase):
    """What a row says of how it was made, for its recording: read before the run, written into every row."""

    def test_the_harness_the_runtime_and_the_starting_saves_hash(self):
        from harness.game_parts.support import RUNTIME_VERSION
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"CIV5_SAVES_DIR": d}):
            (Path(d) / "start.Civ5Save").write_bytes(b"the starting save")
            made = benchmark_run.made_with("start")
            self.assertEqual(benchmark_run.made_with("gone")["save_sha256"], None)
        version = next(line for line in (ROOT / "pyproject.toml").read_text().splitlines() if line.startswith("version = "))
        self.assertEqual(made, {"harness": version.split('"')[1], "runtime": RUNTIME_VERSION,
                                "save_sha256": hashlib.sha256(b"the starting save").hexdigest()})

    def test_the_engines_run_has_its_game_file_begun_before_the_seat_is_handed_over_and_ended_before_the_game_is_left(self):
        """The handler that takes a world a turn has to be in the game before the engine plays the first one."""
        g = FakeGame([{**read(), "build": "1.0.3.279(130961)"}, read(turn=252)], polls=[poll(252, 0)])
        def record(seat):
            g.sent.append(f"game file begins, seat {seat}")
            def end():
                g.sent.append(f"game file ends, left {g.left}")
                return {"file": "g.jsonl", "lines": 13, "bytes": 20}
            return end
        row = run(g, record=record)
        order = [s if s.startswith("game file") else "handed over" for s in g.sent if s.startswith("game file") or "SetAIAutoPlay" in s]
        self.assertEqual(order, ["game file begins, seat 0", "handed over", "game file ends, left 0"])
        self.assertEqual((row["game_file"]["lines"], row["game_build"], g.left), (13, "1.0.3.279(130961)", 1))

    def test_the_runs_last_read_takes_the_game_files_end_in_the_same_call(self):
        """Live 2026-11-24, small-king-poland-a-t200: the game was won, the engine went on with the turn, and the
        `end` line asked for after the row's read had two civilizations four points of score further."""
        from harness.spectator import game_file
        g = FakeGame([read(), read(turn=252)], polls=[poll(252, 0)])
        run(g, record=lambda seat: lambda: {"file": "g.jsonl", "lines": 13, "bytes": 20})
        reads = [s for s in g.sent if "players = {}" in s]
        self.assertEqual([s.startswith(game_file.END_WITH) for s in reads], [False, True], "the first read takes no end")
        self.assertEqual(reads[1], game_file.END_WITH + benchmark_run.READ)
        plain = FakeGame([read(), read(turn=252)], polls=[poll(252, 0)])
        run(plain)
        self.assertFalse(any("SpectatorTurns" in s for s in plain.sent), "no game file, nothing taken")

    def test_the_runs_game_file_is_written_by_the_recorder_of_the_page_with_the_seat_and_the_run_said(self):
        from harness.game_parts.support import RUNTIME_VERSION
        from harness.spectator import game_file
        made = {}

        class Recorder:
            def __init__(self, client, path, seats, run, made_with):
                made.update(client=client, path=path, seats=seats, run=run, made_with=made_with, did=[])

            def begin(self):
                made["did"].append("begin")

        def record(recorder):
            made["did"].append("record")
            return lambda: {"file": str(made["path"]), "lines": 3}

        with tempfile.TemporaryDirectory() as d, mock.patch.object(game_file, "Recorder", Recorder), \
                mock.patch.object(game_file, "record", record):
            path = Path(d) / "board" / "rows-x-seed0-game.jsonl"
            path.parent.mkdir()
            path.write_text("an earlier run's file under the same name\n")
            end = benchmark_run.record_game(path, seat=0, about={"save": "start", "seed": 0}, client="the client")
            self.assertFalse(path.exists())
            self.assertEqual(end(), {"file": str(path), "lines": 3})
        self.assertEqual((made["seats"], made["run"], made["did"]), ([0], {"save": "start", "seed": 0, "seat": 0}, ["begin", "record"]))
        self.assertEqual(made["made_with"], {"harness": benchmark_run.harness_version(), "runtime": RUNTIME_VERSION})


class SavesWhileTheEnginePlays(unittest.TestCase):
    """`--checkpoint N`: the game saves itself (a handler, CHECKPOINT) and the runner copies each save out of the quick
    slot. Live 2026-11-22 on the Prince duel: saves at turns 5, 10 and 15 of 17 turns, the engine not interrupted."""

    def checked(self, polls, after):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"CIV5_SAVES_DIR": d}):
            g = FakeGame([read(), after], polls=polls)
            g.quick_file = Path(d) / "quick" / "QuickSave.Civ5Save"
            row = run(g, checkpoint=10, checkpoint_name="save--built-in-ai-seed0")
            files = {p.stem: p.read_text() for p in Path(d).glob("*.Civ5Save")}
        return g, row, files

    def test_every_save_the_game_took_is_kept_under_its_turn_and_the_win_has_one_of_its_own(self):
        polls = [poll(249, 993), dict(poll(250, 992), saved=250, wrote="turn 250"), dict(poll(255, 987), saved=250),
                 dict(poll(260, 982), saved=260, wrote="turn 260"),
                 dict(poll(263, 979, winner=1), saved=260, over=263, wrote="won on turn 263")]
        g, row, files = self.checked(polls, read(turn=263, winner=1, victory="VICTORY_SPACE_RACE"))
        self.assertEqual(row["checkpoints"], [{"turn": 250, "save": "save--built-in-ai-seed0-t250"},
                                              {"turn": 260, "save": "save--built-in-ai-seed0-t260"}])
        self.assertEqual((row["end_reason"], row["game_over_save"], row["game_over_save_turn"]),
                         ("game_won", "save--built-in-ai-seed0-game-over", 263))
        self.assertEqual(files, {"save--built-in-ai-seed0-t250": "turn 250", "save--built-in-ai-seed0-t260": "turn 260",
                                 "save--built-in-ai-seed0-game-over": "won on turn 263"})
        handler = next(s for s in g.sent if "c.hooked" in s)
        self.assertIn("c.every, c.seat, c.after, c.saved, c.over, c.error = 10, 0, 242, -1, -1", handler)
        self.assertLess(g.sent.index(handler), next(i for i, s in enumerate(g.sent) if "SetAIAutoPlay(10, 0)" in s),
                        "the handler is in the game before the engine has the seat")
        self.assertEqual(g.sent[-1], benchmark_run.CHECKPOINT_OFF, "the handler was left saving in the game")
        json.dumps(row)

    def test_a_win_the_handler_has_not_seen_is_saved_by_the_runners_own_call(self):
        g, row, files = self.checked([poll(247, 995), poll(248, 994, winner=1)], read(turn=248, winner=1))
        self.assertIn(benchmark_run.SAVE_NOW, g.sent)
        self.assertEqual((row["checkpoints"], row["game_over_save_turn"]), ([], 248))
        self.assertEqual(files, {"save--built-in-ai-seed0-game-over": "asked at the end"})

    def test_a_save_that_did_not_come_is_said_and_the_run_goes_on(self):
        polls = [dict(poll(250, 992), saved=250), poll(251, 0)]      # the game says saved, the quick slot holds no file
        _, row, files = self.checked(polls, read(turn=251))
        self.assertEqual((row["end_reason"], row["checkpoints"], files), ("all_turns_played", [{"turn": 250, "save": None}], {}))

    def test_a_run_with_no_saves_asked_sends_the_game_no_handler(self):
        g = FakeGame([read(), read(turn=252)], polls=[poll(252, 0)])
        row = run(g)
        self.assertFalse(any("BenchmarkCheckpoint = c" in s for s in g.sent))
        self.assertNotIn("checkpoints", row)


class APlayersRun(unittest.TestCase):
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

    def command(self, g, writes="left by the player", raises=None):
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
        return benchmark_run.run_player(g, "save", ["loop", "--turns", "10"], "codex/x", 10, sleep=clock.sleep, clock=clock,
                                     path_of=lambda _g, _seat: self.nb, **kw)

    def game(self, after=None, polls=None, **kw):
        after = after or read(turn=252, players=[player(0, human=True, score=150, turn_active=True), player(1, score=310)])
        return FakeGame([read(**kw), after], polls=polls or [poll(252, 0)])

    def test_the_row_is_the_two_reads_around_the_command(self):
        g = self.game()
        row = self.go(g, keep_notebook=self.dir / "rows" / "kept.json")
        self.assertEqual((row["player"], row["end_reason"], row["rc"], row["turns_played"]), ("codex/x", "all_turns_played", 3, 10))
        self.assertEqual((row["start"]["values"]["score"], row["end"]["values"]["score"]), (100, 150))
        self.assertTrue(row["end"]["turn_active"])
        self.assertEqual(self.seen[0][0], ["loop", "--turns", "10"])
        self.assertIs(self.seen[0][3], False)
        order = ["read" if "players = {}" in s else s for s in g.sent if "players = {}" in s or s == "command"]
        self.assertEqual(order, ["read", "command", "read"])
        self.assertEqual(g.left, 1)
        json.dumps(row)

    def test_the_row_keeps_the_runs_own_times_and_the_games_build_for_its_recording(self):
        """The seat's ledger rows between `began` and `ended` are the run's calls (scripts/benchmark_recording.py):
        the times are taken around the command, to the millisecond and outwards, and `cost` counts inside them."""
        g = FakeGame([{**read(), "build": "1.0.3.279(130961)"},
                      read(turn=252, players=[player(0, human=True, score=150, turn_active=True), player(1, score=310)])],
                     polls=[poll(252, 0)])
        times = iter([1000.0004, 1090.0001, 1090.5])
        ledger = self.dir / "calls.jsonl"
        ledger.write_text("".join(json.dumps({"t": t, "seat": 0, "tool": "state"}) + "\n" for t in (999.9, 1000.0, 1090.001, 1090.002)))
        with mock.patch.dict(os.environ, {"CIV5_CALL_LOG": str(ledger)}):
            row = self.go(g, now=lambda: next(times))
        self.assertEqual((row["began"], row["ended"], row["cost"]["calls"]), (1000.0, 1090.001, 2))
        self.assertEqual(row["game_build"], "1.0.3.279(130961)")

    def test_the_game_file_is_begun_before_the_command_and_ended_before_the_game_is_left(self):
        g = self.game()
        def record(seat):
            g.sent.append(f"game file begins, seat {seat}")
            def end():
                g.sent.append(f"game file ends, left {g.left}")
                return {"file": "g.jsonl", "lines": 13, "bytes": 30}
            return end
        row = self.go(g, record=record)
        order = [s for s in g.sent if s == "command" or s.startswith("game file")]
        self.assertEqual(order, ["game file begins, seat 0", "command", "game file ends, left 0"])
        self.assertEqual((row["game_file"], g.left), ({"file": "g.jsonl", "lines": 13, "bytes": 30}, 1))
        self.assertNotIn("game_file_error", row)

    def test_a_game_file_that_does_not_begin_or_end_costs_the_run_nothing(self):
        def broken(_seat):
            raise OSError("no tunerd")
        row = self.go(self.game(), record=broken)
        self.assertEqual((row["end_reason"], row["game_file_error"]), ("all_turns_played", "OSError: no tunerd"))
        self.assertNotIn("game_file", row)
        def ends_badly(_seat):
            def end():
                raise RuntimeError("gone")
            return end
        g = self.game()
        row = self.go(g, record=ends_badly)
        self.assertEqual((row["end_reason"], row["game_file_error"], g.left), ("all_turns_played", "RuntimeError: gone", 1))

    def test_the_notebook_given_is_the_one_played_with_and_the_standing_one_comes_back(self):
        g = self.game()
        row = self.go(g, notebook=str(self.given), keep_notebook=self.dir / "rows" / "kept.json")
        self.assertEqual(self.seen[0][1], "given")
        self.assertEqual(self.nb.read_text(), "standing")
        self.assertEqual((self.dir / "rows" / "kept.json").read_text(), "left by the player")
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
        self.assertEqual((self.dir / "kept.json").read_text(), "left by the player")

    def test_a_notebook_file_that_is_not_there_is_refused_before_the_command(self):
        g = self.game()
        with self.assertRaisesRegex(benchmark_run.Refused, "no notebook file"):
            self.go(g, notebook=str(self.dir / "absent.json"))
        self.assertEqual((self.seen, g.left, self.nb.read_text()), ([], 1, "standing"))

    def test_the_seeds_skip_is_made_before_the_command(self):
        g = self.game()
        self.go(g, skip=34)
        skip = next(i for i, s in enumerate(g.sent) if "for _ = 1, 34 do Game.Rand(" in s)
        self.assertLess(skip, g.sent.index("command"))
        g = self.game()
        self.go(g)
        self.assertFalse(any("Game.Rand(" in s for s in g.sent), "seed 0 skips no random number")

    def test_a_command_that_does_not_end_is_given_up_and_the_save_is_still_read_and_left(self):
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

    def lost(self, save_now_writes=True, played_saves=False):
        """A run with its end save asked whose seat is destroyed on turn 247, in a folder of saves of its own."""
        dead = read(turn=247, players=[player(0, human=True, alive=False), player(1)])
        g = self.game(after=dead, polls=[poll(247, 0, alive=False, turn_active=False)])
        g.quick_file, g.save_now_writes = self.dir / "saves" / "quick" / "QuickSave.Civ5Save", save_now_writes
        run = self.command(g)
        if played_saves:        # the seat's own quick save, written while the command played
            def run(cmd, timeout, check, inner=run):
                g.write_quick("the seat's last saved turn")
                return inner(cmd, timeout, check)
        with mock.patch.dict(os.environ, {"CIV5_SAVES_DIR": str(self.dir / "saves")}):
            row = self.go(g, run=run, end_save="save--codex-x-seed0-end", now=lambda: 0.5)
        files = {p.stem: p.read_text() for p in (self.dir / "saves").glob("*.Civ5Save")}
        return row, files

    def test_a_game_the_seat_lost_keeps_its_save_where_it_ended(self):
        row, files = self.lost(played_saves=True)
        self.assertEqual((row["end_reason"], row["game_over_save"], row["game_over_save_turn"]),
                         ("seat_dead", "save--codex-x-seed0-game-over", 248))
        self.assertEqual(files, {"save--codex-x-seed0-game-over": "asked at the end"})
        self.assertNotIn("end_save", row, "the save at the end of the turns is of a run that played them")
        self.assertNotIn("game_over_save_from", row)
        self.assertEqual(benchmark_run.result_of(row), "finished")

    def test_with_no_save_from_the_game_at_the_end_the_seats_last_quick_save_of_the_run_is_kept_and_said(self):
        row, files = self.lost(save_now_writes=False, played_saves=True)
        self.assertEqual(files, {"save--codex-x-seed0-game-over": "the seat's last saved turn"})
        self.assertEqual((row["game_over_save"], row["game_over_save_turn"]), ("save--codex-x-seed0-game-over", None))
        self.assertIn("before the end", row["game_over_save_from"])

    def test_with_no_save_at_all_the_row_says_none(self):
        row, files = self.lost(save_now_writes=False)
        self.assertEqual((row["game_over_save"], files), (None, {}))

    def test_the_command_is_told_the_turn_at_which_its_turns_are_over(self):
        """Rule 5. Live 2026-11-16: told to end ten turns, Codex stopped with the game nine turns on."""
        g = self.game()
        clock = Clock()
        row = benchmark_run.run_player(g, "save", ["loop", "--until-turn", "{until}"], "codex/x", 10, sleep=clock.sleep,
                                    clock=clock, path_of=lambda _g, _seat: self.nb, run=self.command(g))
        self.assertEqual(self.seen[0][0], ["loop", "--until-turn", "252"])
        self.assertEqual(row["command"], ["loop", "--until-turn", "252"])

    def test_a_command_needs_no_observer_slot(self):
        self.assertEqual(self.go(self.game(slots=(3, 1, 2, 2)))["end_reason"], "all_turns_played")

    def test_a_command_that_ends_before_its_turns_are_played_did_not_finish(self):
        short = read(turn=246, players=[player(0, human=True, score=110, turn_active=True), player(1, score=310)])
        row = self.go(self.game(after=short, polls=[poll(246, 0)]))
        self.assertEqual((row["end_reason"], row["turns_asked"], row["turns_played"], row["rc"]), ("turns_not_played", 10, 4, 3))
        self.assertIn("codex/x: 1 runs, 0 played their turns, 1 turns_not_played", benchmark_run.summarise([row]))

    def test_the_command_line_wants_a_label_with_a_command_and_a_command_with_a_label(self):
        for argv in (["--save", "b", "--out", "x.jsonl", "--", "loop"], ["--save", "b", "--out", "x.jsonl", "--player", "codex"],
                     ["--save", "b", "--out", "x.jsonl", "--player", "built-in-ai", "--", "loop"],
                     ["--save", "b", "--out", "x.jsonl", "--finish-only"],
                     ["--save", "b", "--out", "x.jsonl", "--finish-only", "--ai-finishes", "3", "--player", "c", "--", "loop"]):
            with self.subTest(argv), self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                benchmark_run.main(argv)


class AiFinishes(unittest.TestCase):
    """Rule 1: the game finished by the engine's AI from the end of the turns, and the share of those games the seat won."""

    def go(self, g, m=0, **kw):
        clock = Clock()
        return benchmark_run.ai_finish(g, "save--end", m, sleep=clock.sleep, clock=clock, **kw)

    def test_a_victory_of_the_seats_team_is_a_game_won(self):
        g = FakeGame([read(turn=252)], polls=[poll(300, 950), poll(318, 932, winner=0, victory="VICTORY_SPACE_RACE"), poll(319, 0)])
        c = self.go(g)
        self.assertEqual((c["end_reason"], c["won"], c["victory"], c["turn"], c["from_turn"]),
                         ("victory", True, "VICTORY_SPACE_RACE", 318, 252))
        self.assertEqual((len(g.polls), g.left), (1, 1), "the engine plays on past a victory: the game is left")

    def test_a_game_the_engine_still_plays_is_left_by_the_runner_itself(self):
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

    def test_an_exit_that_answered_nothing_is_looked_at_before_the_game_is_taken_as_left(self):
        """Live 2026-11-21: the daemon could not read the runtime source, the seat's exit answered `{}` (the same
        answer as a state torn down under the call), and the engine played on from a win at turn 421 to 479."""
        clock = Clock()
        stuck = FakeGame([read()])
        stuck.leave_reply, stuck.up_for = {}, 10**6
        benchmark_run.leave(stuck, settle=15.0, clock=clock, sleep=clock.sleep)
        self.assertIn("Events.ExitToMainMenu()", stuck.sent[-1], "still up after the settle time: asked itself")
        self.assertGreaterEqual(clock.t, 15.0)
        leaving = FakeGame([read()])
        leaving.leave_reply, leaving.up_for = {}, 2
        benchmark_run.leave(leaving, settle=15.0, clock=clock, sleep=clock.sleep)
        self.assertEqual((leaving.looked, leaving.sent), (3, []), "a game that goes within the time is not asked twice")
        answered = FakeGame([read()])
        benchmark_run.leave(answered, clock=clock, sleep=clock.sleep)
        self.assertEqual((answered.looked, answered.sent), (0, []), "an exit that answered ok is taken at its word")

    def test_the_first_war_and_the_most_cities_stand_beside_the_result(self):
        polls = [dict(poll(260, 900), wars=0, cities=2), dict(poll(271, 889), wars=1, cities=3),
                 dict(poll(290, 870), wars=0, cities=1), dict(poll(300, 860, winner=1, victory="VICTORY_DOMINATION"), wars=1, cities=1)]
        c = self.go(FakeGame([read(turn=252)], polls=polls))
        self.assertEqual((c["first_war_turn"], c["most_cities"], c["won"]), (271, 3, False))
        quiet = self.go(FakeGame([read(turn=252)], polls=[poll(300, 860, winner=0, victory="VICTORY_CULTURAL")]))
        self.assertNotIn("first_war_turn", quiet)

    def test_a_path_is_every_players_indicators_at_the_start_and_every_n_turns(self):
        """The win-chance formula's rows (rule 1): positions the built-in AI played from, with the game's outcome beside them."""
        two = [player(0, human=True, score=100), player(1, score=140)]
        reads = [read(turn=95, players=two), read(turn=101, players=two), read(turn=112, players=two),
                 read(turn=130, winner=1, victory="VICTORY_DOMINATION", players=two)]
        polls = [poll(99, 900), poll(101, 898), poll(105, 894), poll(112, 887), poll(119, 880),
                 poll(130, 870, winner=1, victory="VICTORY_DOMINATION")]
        c = self.go(FakeGame(reads, polls=polls), path_every=10)
        self.assertEqual([pt["turn"] for pt in c["path"]], [95, 101, 112], "the start, then the first poll of each ten turns")
        self.assertEqual(c["path"][0]["players"][1],
                         {"id": 1, "alive": True, **{k: two[1][k] for k in benchmark_run.INDICATORS + benchmark_run.ROUTES}})
        self.assertEqual((c["end_reason"], c["won"], [p["score"] for p in c["players"]]), ("victory", False, [100, 140]),
                         "the poll that brings the winner is the end, not a point")
        self.assertEqual(c["seat"], 0, "a save valued as it is names no seat in its row: the game says whose it was")

    def test_no_path_is_kept_unless_asked(self):
        c = self.go(FakeGame([read(turn=95)], polls=[poll(101, 898), poll(130, 870, winner=0, victory="VICTORY_CULTURAL")]))
        self.assertNotIn("path", c)

    def test_a_decided_game_keeps_how_it_stood(self):
        end = read(turn=330, winner=1, victory="VICTORY_TIME", players=[player(0, human=True, score=1571), player(1, score=1865)])
        c = self.go(FakeGame([read(), end], polls=[poll(330, 900, winner=1, victory="VICTORY_TIME")]))
        self.assertEqual([(p["id"], p["score"]) for p in c["players"]], [(0, 1571), (1, 1865)])
        self.assertEqual(set(c["players"][0]), {"id", "civ", "alive", "score", "techs", "cities"})
        stalled = self.go(FakeGame([read()], polls=[poll(260, 990)] * 6), poll=3.0, stall=10.0)
        self.assertNotIn("players", stalled)

    def test_the_seat_is_put_on_the_ais_row_and_time_switched_off_in_the_call_that_hands_it_over(self):
        """Live 2026-11-17: the seat on the human's Prince row lost every full AI game of two starting saves; set in play, the
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
        self.assertIsNone(benchmark_run.value_of({"end_reason": "all_turns_played"}, [c]))

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
        self.assertIsNone(benchmark_run.value_of({"end_reason": "all_turns_played"}, [c]))

    def test_no_game_starts_on_another_games_stretch_of_the_random_sequence(self):
        # a seed's game, its AI finishes and the next seed's game start a whole stretch apart, and a stretch is
        # many times the 42,263 random numbers a full AI game took (live 2026-11-20)
        starts = sorted([benchmark_run.NUMBERS_A_SEED * n for n in range(3)]
                        + [benchmark_run.NUMBERS_A_SEED * n + benchmark_run.NUMBERS_AN_AI_FINISH * (m + 1)
                           for n in range(3) for m in range(benchmark_run.GAMES_A_SEED - 1)])
        self.assertEqual(len(set(starts)), len(starts))
        self.assertGreaterEqual(min(b - a for a, b in zip(starts, starts[1:])), 20 * 42_263)
        g = FakeGame([read()], polls=[poll(330, 1, winner=1)])
        with self.assertRaises(benchmark_run.Refused):
            self.go(g, m=benchmark_run.GAMES_A_SEED - 1)
        self.assertEqual(g.sent, [])                      # refused before the save is loaded

    def test_every_ai_finish_skips_numbers_and_asks_for_more_turns_than_a_game_has(self):
        for m, numbers in ((0, 1_000_003), (1, 2_000_006), (14, 15_000_045)):
            g = FakeGame([read()], polls=[poll(330, 1, winner=1)])
            self.assertEqual(self.go(g, m=m)["skip"], numbers)
            start = next(s for s in g.sent if "SetAIAutoPlay" in s)
            self.assertIn(f"for _ = 1, {numbers} do Game.Rand(", start)
            self.assertIn("Game.SetAIAutoPlay(1000, 0)", start)

    def test_a_save_with_no_observer_slot_is_refused_and_left(self):
        g = FakeGame([read(slots=(3, 1, 2))])
        with self.assertRaisesRegex(benchmark_run.Refused, "observer slot"):
            self.go(g)
        self.assertEqual((g.left, any("SetAIAutoPlay" in s for s in g.sent)), (1, False))

    def test_the_value_is_the_share_of_decided_games_won(self):
        games = [{"end_reason": "victory", "won": True}, {"end_reason": "victory", "won": False},
                 {"end_reason": "seat_dead", "won": False}, {"end_reason": "stalled", "won": False}]
        self.assertEqual(benchmark_run.value_of({"end_reason": "all_turns_played"}, games), round(1 / 3, 4))
        self.assertEqual(benchmark_run.value_of({"end_reason": "finish_only"}, games[:2]), 0.5)

    def test_a_run_that_did_not_finish_has_no_value_and_is_a_result_of_its_own(self):
        won = [{"end_reason": "victory", "won": True}]
        for reason, result in (("turns_not_played", "did_not_finish"), ("timeout", "did_not_finish"), ("stalled", "void"), ("not_handed_over", "void")):
            self.assertIsNone(benchmark_run.value_of({"end_reason": reason}, won), reason)
            self.assertEqual(benchmark_run.result_of({"end_reason": reason}), result)

    def test_a_game_ended_inside_the_turns_is_finished_and_worth_one_or_nothing(self):
        self.assertEqual(benchmark_run.value_of({"end_reason": "game_won", "winner": 0, "end": {"team": 0}}, []), 1.0)
        self.assertEqual(benchmark_run.value_of({"end_reason": "game_won", "winner": 1, "end": {"team": 0}}, []), 0.0)
        self.assertEqual(benchmark_run.value_of({"end_reason": "seat_dead"}, []), 0.0)
        for reason in ("all_turns_played", "game_won", "seat_dead", "finish_only"):
            self.assertEqual(benchmark_run.result_of({"end_reason": reason}), "finished")


class EndSave(unittest.TestCase):
    def setUp(self):
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(mock.patch.dict(os.environ, {"CIV5_SAVES_DIR": str(self.dir)}))

    def game(self, **kw):
        g = FakeGame([read(), read(turn=252)], polls=[poll(252, 0)], **kw)
        g.quick_file = self.dir / "quick" / "QuickSave.Civ5Save"
        return g

    def test_the_end_of_played_turns_is_saved_under_its_name_before_the_game_is_left(self):
        g = self.game()
        clock = Clock()
        row = benchmark_run.run_once(g, "save", 10, end_save="save--built-in-ai-seed0-end", sleep=clock.sleep, clock=clock)
        self.assertEqual(row["end_save"], "save--built-in-ai-seed0-end")
        self.assertTrue((self.dir / "save--built-in-ai-seed0-end.Civ5Save").read_text().startswith("save "))
        self.assertEqual(g.left, 1)

    def test_an_old_quick_save_is_not_taken_for_the_new_one(self):
        g = self.game()
        g.quick_file.parent.mkdir()
        g.quick_file.write_text("an older game")
        clock = Clock()
        benchmark_run.save_as(g, "kept", sleep=clock.sleep, clock=clock)
        self.assertNotEqual((self.dir / "kept.Civ5Save").read_text(), "an older game")

    def test_a_quick_save_that_is_refused_or_never_written_is_said_in_the_row(self):
        refused, unwritten = self.game(), self.game()
        refused.quick_reply = {"ok": False, "err": "not your turn"}
        unwritten.quick_file = None
        for g, why in ((refused, "refused"), (unwritten, "not written")):
            clock = Clock()
            row = benchmark_run.run_once(g, "save", 10, end_save="kept", sleep=clock.sleep, clock=clock)
            self.assertEqual((row["end_reason"], row["end_save"]), ("all_turns_played", None))
            self.assertIn(why, row["end_save_error"])
            self.assertEqual(g.left, 1)

    def test_a_run_that_did_not_finish_is_saved_where_it_stopped(self):
        """The user, 2026-11-24: such a run packs. A recording needs a saved game, so the runner takes one."""
        clock = Clock()
        for reason in benchmark_run.NOT_FINISHED:
            g, row = self.game(), {"end_reason": reason}
            benchmark_run.keep_end(g, row, "kept", benchmark_run.save_as, clock.sleep, clock)
            self.assertEqual(row["end_save"], "kept")
            self.assertTrue((self.dir / "kept.Civ5Save").read_text().startswith("save "))
        for reason in ("seat_dead", "game_won", "stalled", "not_handed_over"):
            g, row = self.game(), {"end_reason": reason}
            benchmark_run.keep_end(g, row, "kept", benchmark_run.save_as, clock.sleep, clock)
            self.assertNotIn("end_save", row)
            self.assertNotIn("quick_save", g.sent)

    def test_turns_that_were_not_all_played_are_not_saved(self):
        g = FakeGame([read(), read(turn=246, winner=1, players=[player(0, human=True, alive=False), player(1)])],
                     polls=[poll(246, 6, winner=1, alive=False)])
        clock = Clock()
        row = benchmark_run.run_once(g, "save", 10, end_save="kept", sleep=clock.sleep, clock=clock)
        self.assertNotIn("end_save", row)
        self.assertNotIn("quick_save", g.sent)


class Terms(unittest.TestCase):
    """Live 2026-11-17: a save made after the seat was put on the AIs' row and Time switched off reads both back
    after a reload, so a starting save can carry its terms and every run on it is played on them."""

    TOLD = {"seat_row": "HANDICAP_AI_DEFAULT", "time_victory": False, "max_turns": 0}

    def make(self, g, **kw):
        saved = []
        out = benchmark_run.with_terms(g, "save-t0", "save-t0-terms", save_game=lambda _g, name: saved.append(name) or name, **kw)
        return out, saved

    @staticmethod
    def sent_terms(g):
        return next(c for c in g.sent if "seat_row" in c and "SetAIAutoPlay" not in c and "players = {}" not in c)

    def test_the_save_is_changed_then_saved_under_the_new_name_and_left(self):
        g = FakeGame([read(turn=0)], polls=[dict(self.TOLD)])
        out, saved = self.make(g)
        chunk = self.sent_terms(g)
        self.assertIn("PreGame.SetHandicap(0, GameInfo.HandicapInfos.HANDICAP_AI_DEFAULT.ID)", chunk)
        self.assertIn("PreGame.SetMaxTurns(0)", chunk)
        self.assertFalse(any("SetAIAutoPlay" in c for c in g.sent))          # nobody plays a turn
        self.assertEqual(saved, ["save-t0-terms"])
        self.assertEqual(out, {**self.TOLD, "save": "save-t0-terms", "made_from": "save-t0", "seat": 0, "turn": 0})
        self.assertEqual(g.left, 1)

    def test_either_term_can_be_left_as_hosted(self):
        g = FakeGame([read(turn=0)], polls=[dict(self.TOLD)])
        self.make(g, row="own")
        chunk = self.sent_terms(g)
        self.assertNotIn("SetHandicap", chunk)
        self.assertIn("PreGame.SetMaxTurns(0)", chunk)

    def test_a_save_with_no_observer_slot_is_refused_unchanged_and_left(self):
        g = FakeGame([read(slots=(3, 1, 2, 2))])
        with self.assertRaises(benchmark_run.Refused):
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
        with mock.patch.object(benchmark_run, "with_terms", fake), mock.patch("harness.game.Game", return_value=game), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(benchmark_run.main(["--save", "a", "--terms", "b"]), 0)
            self.assertEqual(seen, {"save": "a", "new": "b", "row": "ai", "time": "off"})
            self.assertEqual(benchmark_run.main(["--save", "a", "--terms", "b", "--time", "on"]), 0)
            self.assertEqual(seen["time"], "on")


class NewGamesOfOneSave(unittest.TestCase):
    """Live 2026-11-17: eight full AI games of one save were asked for twice, and the second run replayed the first
    two game for game (Diplomatic at turn 342, Culture at 272) before the game process died with nothing written."""

    def finish_only(self, out, *more, die_at=None):
        seen = []

        def fake(_g, save, m, **_kw):
            if m == die_at:
                raise RuntimeError("game connection lost")
            seen.append(m)
            return {"m": m, "end_reason": "victory", "won": True, "seconds": 60.0, "turn": 300}

        game = mock.Mock()
        game.has_state.return_value = False
        with mock.patch.object(benchmark_run, "ai_finish", fake), mock.patch.object(benchmark_run, "wait_main_menu"), \
                mock.patch("harness.game.Game", return_value=game), contextlib.redirect_stdout(io.StringIO()):
            try:
                benchmark_run.main(["--save", "a", "--finish-only", "--ai-finishes", "3", "--out", str(out), *more])
            except RuntimeError:
                pass
        return seen

    def test_the_ai_finishes_are_numbered_from_the_one_named(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "rows.jsonl"
            self.assertEqual(self.finish_only(out), [0, 1, 2])
            self.assertEqual(self.finish_only(out, "--first-ai-finish", "8"), [8, 9, 10])
            self.assertEqual([c["m"] for c in benchmark_run.read_rows(out)[1]["ai_finishes"]], [8, 9, 10])
            self.assertFalse(Path(str(out) + ".partial").exists())

    def test_the_games_played_before_a_crash_are_kept_beside_the_rows(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "rows.jsonl"
            self.assertEqual(self.finish_only(out, die_at=2), [0, 1])
            self.assertFalse(out.exists())
            kept = json.loads(Path(str(out) + ".partial").read_text())
            self.assertEqual([c["m"] for c in kept["ai_finishes"]], [0, 1])


class KeepEnd(unittest.TestCase):
    """A run with no AI finish asked can still keep the position its turns ended on."""

    def asked(self, *more, reason="all_turns_played"):
        seen = {}

        def fake(_g, save, turns, **kw):
            seen.update(end_save=kw.get("end_save"))
            return {"player": "built-in-ai", "save": save, "end_reason": reason, "turns_played": turns,
                    "seconds": 1.0, "end_save": kw.get("end_save")}

        game = mock.Mock()
        game.has_state.return_value = False
        with tempfile.TemporaryDirectory() as d, mock.patch.object(benchmark_run, "run_once", fake), \
                mock.patch.object(benchmark_run, "wait_main_menu"), mock.patch.object(benchmark_run, "ai_finish") as finish, \
                mock.patch.object(benchmark_run, "summarise", return_value=[]), \
                mock.patch("harness.game.Game", return_value=game), contextlib.redirect_stdout(io.StringIO()):
            benchmark_run.main(["--save", "a", "--turns", "100", "--out", str(Path(d) / "rows.jsonl"), *more])
            row = benchmark_run.read_rows(Path(d) / "rows.jsonl")[0]
        finish.assert_not_called()
        return seen["end_save"], row

    def test_the_end_is_saved_under_the_seeds_name_and_no_ai_finish_is_played(self):
        name, row = self.asked("--keep-end")
        self.assertEqual(name, "a--built-in-ai-seed0-end")
        self.assertNotIn("ai_finishes", row)
        self.assertNotIn("value", row)

    def test_without_it_a_run_with_no_ai_finish_saves_nothing(self):
        self.assertIsNone(self.asked()[0])

    def test_no_ai_finish_is_played_from_where_a_run_stopped(self):
        """The save of a run that did not finish is for its recording: the run has no value to be finished for."""
        for reason in benchmark_run.NOT_FINISHED:
            name, row = self.asked("--ai-finishes", "2", reason=reason)
            self.assertEqual((name, row["ai_finishes"]), ("a--built-in-ai-seed0-end", []))


class RunsOfOneSave(unittest.TestCase):
    """Every run of a starting save starts on the save's own random numbers unless separate games are asked for."""

    def skips(self, *more):
        seen = []

        def fake(_g, save, turns, **kw):
            seen.append(kw.get("skip"))
            return {"player": "built-in-ai", "save": save, "end_reason": "all_turns_played", "turns_played": turns,
                    "seconds": 1.0}

        game = mock.Mock()
        game.has_state.return_value = False
        with tempfile.TemporaryDirectory() as d, mock.patch.object(benchmark_run, "run_once", fake), \
                mock.patch.object(benchmark_run, "wait_main_menu"), mock.patch.object(benchmark_run, "summarise", return_value=[]), \
                mock.patch("harness.game.Game", return_value=game), contextlib.redirect_stdout(io.StringIO()):
            benchmark_run.main(["--save", "a", "--turns", "10", "--runs", "3", "--out", str(Path(d) / "rows.jsonl"), *more])
            runs = [r.get("run") for r in benchmark_run.read_rows(Path(d) / "rows.jsonl")]
        return seen, runs

    def test_by_default_no_run_skips_a_random_number_and_each_keeps_its_own_number(self):
        self.assertEqual(self.skips(), ([0, 0, 0], [0, 1, 2]))

    def test_separate_games_are_still_there_to_ask_for(self):
        seen, _ = self.skips("--skip", "seed")
        self.assertEqual(seen, [n * benchmark_run.NUMBERS_A_SEED for n in range(3)])


class Views(unittest.TestCase):
    def test_shares_are_of_the_living_and_the_place_is_by_score(self):
        r = read(players=[player(0, human=True, score=100, techs=30), player(1, score=300, techs=50),
                          player(2, score=50, techs=20), player(3, alive=False, score=900, techs=99)])
        v = benchmark_run.seat_view(r, 0)
        self.assertEqual((v["place"], v["of"]), (2, 3))
        self.assertEqual(v["share"]["techs"], 0.3)
        self.assertEqual(v["share"]["score"], round(100 / 450, 4))

    def test_a_negative_value_counts_as_nothing_in_a_share(self):
        r = read(players=[player(0, human=True, happiness=-4), player(1, happiness=8)])
        self.assertEqual(benchmark_run.seat_view(r, 0)["share"]["happiness"], 0.0)


def row(score, reason="all_turns_played", start=100, **kw):
    values = {k: 10 for k in benchmark_run.INDICATORS}
    return {**kw, "save": "save", "seat": 0, "handicap": "HANDICAP_EMPEROR", "turns_asked": 10, "seconds": 300.0,
            "end_reason": reason, "start": {"values": dict(values, score=start)},
            "end": {"values": dict(values, score=score), "share": {k: 0.1 for k in benchmark_run.INDICATORS},
                    "place": 2, "of": 12}}


class Summary(unittest.TestCase):
    def test_the_spread_is_set_against_the_gain(self):
        lines = benchmark_run.summarise([row(130), row(140), row(150), row(0, reason="seat_dead")])
        self.assertIn("4 runs, 3 played their turns, 1 seat_dead", lines[0])
        score = next(line for line in lines if line.startswith("score"))
        self.assertEqual(score.split()[:7], ["score", "100", "140.0", "10.0", "130", "150", "0.25"])
        self.assertFalse(any("replays the same game" in line for line in lines))

    def test_runs_that_all_end_alike_are_said_to_be_one_game(self):
        lines = benchmark_run.summarise([row(140), row(140)])
        self.assertTrue(any("replays the same game" in line for line in lines))
        self.assertFalse(any("replays the same game" in line for line in benchmark_run.summarise([row(140)])))

    def test_rows_with_no_player_are_the_built_in_ais(self):
        self.assertTrue(benchmark_run.summarise([row(140)])[0].startswith("built-in-ai: 1 runs"))

    def test_two_players_stand_side_by_side_on_runs_that_played_their_turns(self):
        rows = [row(130, turns_played=10), row(150, turns_played=10),
                row(180, player="codex/x", turns_played=10),
                row(0, reason="timeout", player="codex/x", turns_played=4)]
        lines = benchmark_run.summarise(rows)
        self.assertIn("codex/x: 2 runs, 1 played their turns, 1 timeout", lines)
        head = lines.index("side by side, 10 turns, mean (sd) at the end:")
        self.assertEqual(lines[head + 1].split(), ["built-in-ai", "x2", "codex/x", "x1"])
        self.assertEqual(lines[head + 2].split(), ["score", "140.0", "(14.1)", "180.0", "(0.0)"])

    def test_runs_of_different_lengths_do_not_stand_side_by_side(self):
        lines = benchmark_run.summarise([row(130, turns_played=10), row(180, player="codex/x", turns_played=7)])
        self.assertEqual(lines[-1], "not side by side: the runs played 7, 10 turns")
        self.assertFalse(any(line.startswith("side by side") for line in lines))

    def test_the_value_has_its_own_line_and_its_row_side_by_side(self):
        games = [{"end_reason": "victory", "won": True, "victory": "VICTORY_TIME", "seconds": 600.0}] * 2
        rows = [row(130, turns_played=10, value=0.5, ai_finishes=games), row(150, turns_played=10, value=0.3, ai_finishes=games),
                row(180, player="codex/x", turns_played=10, value=0.7, ai_finishes=games),
                row(0, reason="turns_not_played", player="codex/x", turns_played=4, value=None)]
        lines = benchmark_run.summarise(rows)
        self.assertIn("value: 0.400 (sd 0.141) over 2 finished runs and 4 AI finishes, 10.0 min each; by run: 0.50, 0.30; "
                      "ended by VICTORY_TIME", lines)
        self.assertTrue(any(line.startswith("value: 0.700 (sd 0.000) over 1 finished runs") for line in lines),
                        "a run that did not finish is not averaged into the value")
        # the seed is the unit (live 2026-11-18: two seeds were 0 of 5 and 5 of 5): 0.141 / sqrt(2)
        self.assertIn("seeds: 2 finished, the value's standard error over them 0.100 "
                      "(the seed is the unit: its games are not independent trials)", lines)
        self.assertEqual(sum(1 for line in lines if line.startswith("seeds: ")), 1, "one seed has no error over seeds")
        self.assertFalse(any("standard error" in line for line in lines if line.startswith("games: ")))
        self.assertIn("not finished: 1 of 2 runs (turns_not_played), below every finished run in an ordering; "
                      "with not finished as 0 the value is 0.350", lines)
        self.assertEqual(lines[-2].split(), ["value", "0.400", "(0.141)", "0.700", "(0.000)"])
        self.assertEqual(lines[-1].split(), ["not", "finished", "0", "of", "2", "1", "of", "2"])

    def test_a_save_valued_as_it_is_has_one_line(self):
        only = {"player": "save", "end_reason": "finish_only", "value": 0.25,
                "ai_finishes": [{"end_reason": "seat_dead", "won": False, "seconds": 120.0}]}
        lines = benchmark_run.summarise([only])
        self.assertEqual(lines[0], "save: 1 runs, 0 played their turns")
        self.assertTrue(lines[1].startswith("value: 0.250 (sd 0.000) over 1 finished runs and 1 AI finishes, 2.0 min each"))
        self.assertTrue(lines[1].endswith("ended by seat_dead"))

    def test_the_games_as_one_pool_and_the_ones_the_stop_turn_left_open(self):
        games = [{"end_reason": "victory", "won": True, "seconds": 60.0, "victory": "VICTORY_CULTURAL"},
                 {"end_reason": "victory", "won": False, "seconds": 60.0, "victory": "VICTORY_DOMINATION"},
                 {"end_reason": "turn_limit", "won": False, "seconds": 600.0, "turn": 500}]
        lines = benchmark_run.summarise([{"player": "save", "end_reason": "finish_only", "value": 0.5,
                                      "ai_finishes": games}])
        self.assertIn("and 2 AI finishes, 1.0 min each", lines[1])      # the open game is in no mean
        self.assertEqual(lines[2], "games: the seat won 1 of 2 decided, 0.500")
        self.assertEqual(lines[3], "not decided by the stop turn: 1 (turn 500), in no share")

    def test_no_run_that_played_its_turns_gives_one_line(self):
        self.assertEqual(len(benchmark_run.summarise([row(0, reason="stalled")])), 1)


def finishes(*won, first=0, reason="victory"):
    return [{"m": first + i, "end_reason": reason, "won": bool(w), "seconds": 60.0} for i, w in enumerate(won)]


def valued(*won, **kw):
    return row(140, turns_played=10, value=sum(won) / len(won), ai_finishes=finishes(*won), **kw)


class LaterFinishes(unittest.TestCase):
    """AI finishes played afterwards on a run's end save are that run's games (2026-11-20: the baseline's seeds got
    one finish each with the run and four more from a second batch, in a rows file of their own)."""

    def test_a_later_finish_joins_the_run_whose_end_save_it_was_played_from(self):
        runs = [valued(0, end_save="save--x-seed0-end"), valued(1, end_save="save--x-seed1-end")]
        later = [{"player": "save", "save": "save--x-seed0-end", "end_reason": "finish_only", "value": 1.0,
                  "ai_finishes": finishes(1, 1, 1, first=1)}]
        got, stray = benchmark_run.with_later_finishes(runs, later)
        self.assertEqual([c["m"] for c in got[0]["ai_finishes"]], [0, 1, 2, 3])
        self.assertEqual(got[0]["value"], 0.75)
        self.assertEqual(got[1], runs[1])
        self.assertEqual(stray, [])
        self.assertEqual(len(runs[0]["ai_finishes"]), 1, "the rows read are not changed")

    def test_a_finish_of_a_number_the_run_has_is_the_same_game_and_is_not_counted_twice(self):
        runs = [valued(0, end_save="e0")]
        later = [{"save": "e0", "end_reason": "finish_only", "ai_finishes": finishes(0, 1)},
                 {"save": "e0", "end_reason": "finish_only", "ai_finishes": finishes(1, first=1)}]
        got, _ = benchmark_run.with_later_finishes(runs, later)
        self.assertEqual([(c["m"], c["won"]) for c in got[0]["ai_finishes"]], [(0, False), (1, True)])
        self.assertEqual(got[0]["value"], 0.5)

    def test_later_rows_on_a_save_no_run_ended_on_are_named_and_in_nothing(self):
        got, stray = benchmark_run.with_later_finishes(
            [valued(1, end_save="e0")], [{"save": "another", "end_reason": "finish_only", "ai_finishes": finishes(0)}])
        self.assertEqual((got[0]["value"], stray), (1.0, ["another"]))

    def test_a_run_that_did_not_finish_stays_without_a_value(self):
        runs = [row(0, reason="turns_not_played", value=None, end_save="e0")]
        got, _ = benchmark_run.with_later_finishes(runs, [{"save": "e0", "end_reason": "finish_only", "ai_finishes": finishes(1)}])
        self.assertIsNone(got[0]["value"])

    def test_the_summary_takes_later_rows_files(self):
        with tempfile.TemporaryDirectory() as d:
            runs, later = Path(d) / "runs.jsonl", Path(d) / "later.jsonl"
            runs.write_text(json.dumps(valued(0, end_save="e0")) + "\n")
            later.write_text(json.dumps({"player": "save", "save": "e0", "end_reason": "finish_only",
                                         "ai_finishes": finishes(1, 1, 1, first=1)}) + "\n"
                             + json.dumps({"player": "save", "save": "e9", "end_reason": "finish_only",
                                           "ai_finishes": finishes(1)}) + "\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(benchmark_run.main(["--summary", str(runs), "--later", str(later)]), 0)
        self.assertIn("value: 0.750 (sd 0.000) over 1 finished runs and 4 AI finishes", out.getvalue())
        self.assertIn("later rows on saves that are no run's end save here, in nothing: e9", out.getvalue())


class Spread(unittest.TestCase):
    """The spread of a player's values has two parts and they cost differently: a finish is machine time, a seed is
    the player's 100 turns."""
    SEEDS = [(0, 4), (4, 4), (2, 4), (2, 4)]

    def test_the_two_parts(self):
        within, between = benchmark_run.spread_parts(self.SEEDS)
        # within: 0, 0 and twice 4/3 x 0.25; between: the shares' variance 1/6 less the mean of within / 4
        self.assertAlmostEqual(within, 1 / 6)
        self.assertAlmostEqual(between, 1 / 6 - 1 / 24)

    def test_seeds_that_differ_no_more_than_their_finishes_alone_would_have_no_part_between(self):
        self.assertEqual(benchmark_run.spread_parts([(2, 4), (2, 4), (1, 4), (3, 4)])[1], 0.0)

    def test_the_lines_say_both_parts_and_the_seeds_an_error_takes(self):
        rows = [valued(*([1] * w + [0] * (r - w))) for w, r in self.SEEDS]
        lines = benchmark_run.spread_lines(rows)
        self.assertTrue(lines[0].startswith(
            "spread: 4 seeds with two or more AI finishes (16 finishes): from one end of the turns a finish varies by "
            "0.408 (within a seed); the chance the turns leave varies by 0.354 from seed to seed ("), lines[0])
        self.assertEqual(lines[1], "seeds for a standard error of 0.05: 117 at 1, 64 at 5, 55 at 15 AI finishes a seed")
        self.assertEqual(benchmark_run.spread_lines(rows), lines, "the resampling is the same every time")
        self.assertEqual([line for line in benchmark_run.summarise(rows) if line.startswith(("spread", "seeds for"))], lines)

    def test_seeds_with_one_finish_and_runs_that_did_not_play_their_turns_are_not_in_it(self):
        rows = [valued(*([1] * w + [0] * (r - w))) for w, r in self.SEEDS]
        more = [*rows, valued(1), row(0, reason="seat_dead", value=0.0, ai_finishes=finishes(0, 0)),
                row(140, value=None, ai_finishes=finishes(0, 0, reason="turn_limit"))]
        self.assertEqual(benchmark_run.spread_lines(more), benchmark_run.spread_lines(rows))

    def test_too_few_seeds_give_no_line(self):
        self.assertEqual(benchmark_run.spread_lines([valued(1, 0), valued(0, 0), valued(1, 1)]), [])


def played_reply(**kw):
    """What the game answers the read of rule 7's figures."""
    out = {"leader": "Boudicca", "gold": 120, "units": 9, "military_units": 5,
           "yields": {"food": 30, "production": 20, "gold": 4, "science": 15, "culture": 6, "faith": 2},
           "score_parts": {k: 10 for k in benchmark_run.SCORE_PARTS},
           "at_war": {}, "friends": ["Austria"], "denounced": {}, "denounced_by": {}, "allies": ["Sidon"], "events": {}}
    out.update(kw)
    return out


EVENTS = [{"turn": 242, "player": 0, "kind": 0, "text": "Session 4 starts"},
          {"turn": 243, "player": 0, "kind": 1, "text": "Dublin is founded."},
          {"turn": 244, "player": 0, "kind": 0, "text": "Boudicca declares war on Maria Theresa!"},
          {"turn": 245, "player": 23, "kind": 0, "text": "Sidon declares war on Boudicca!"},
          {"turn": 246, "player": 1, "kind": 0, "text": "Maria Theresa completes Great Library!"},
          {"turn": 247, "player": 0, "kind": 0, "text": "Boudicca completes Parthenon!"},
          {"turn": 250, "player": 1, "kind": 0, "text": "Maria Theresa has made peace with Boudicca!"}]


class HowTheSeatWasPlayed(unittest.TestCase):
    """Rule 7 (#196): the seat's figures at both ends of a run and what the game's replay says happened between, in
    the row; the call ledger's count of a player's run; all of it in the summary, ordering no one."""

    def game(self):
        after = read(turn=252, players=[player(0, human=True, score=140), player(1, score=310)])
        g = FakeGame([read(), after], polls=[poll(252, 0)])
        g.played_reply = played_reply(events=list(EVENTS))
        return g

    def test_a_run_keeps_the_figures_at_both_ends_and_the_events_between(self):
        g = self.game()
        row = run(g)
        asked = [c for c in g.sent if "score_parts" in c]
        self.assertEqual(len(asked), 2)
        self.assertLess(g.sent.index(asked[0]), next(i for i, c in enumerate(g.sent) if "SetAIAutoPlay" in c),
                        "the first read is before the engine takes the seat")
        self.assertIn(f"m.Turn >= {benchmark_run.NO_EVENTS}", asked[0], "the read at the start asks for no events")
        self.assertIn("m.Turn >= 242", asked[1], "the read at the end asks for the run's turns")
        how = row["played"]
        self.assertEqual(how["end"]["yields"]["science"], 15)
        self.assertEqual((how["end"]["at_war"], how["end"]["friends"]), ([], ["Austria"]), "an empty Lua table is an empty list")
        self.assertNotIn("events", how["end"])
        self.assertEqual([e["turn"] for e in how["events"]], [243, 244, 245, 246, 247, 250], "the replay's session line is no event")
        self.assertEqual(how["counts"], {"wars_declared": 1, "wars_declared_on_it": 1, "peace_made": 1, "wonders": 1,
                                         "cities_founded": 1})

    def test_a_read_the_game_does_not_answer_is_kept_as_its_error_and_the_run_stands(self):
        g = self.game()
        g.played_reply = None
        row = run(g)
        self.assertEqual(row["end_reason"], "all_turns_played")
        self.assertIn("error", row["played"]["end"])
        self.assertNotIn("counts", row["played"])
        self.assertEqual(benchmark_run.played_lines({"built-in-ai": [row]}), [], "and it is in no table")

    def test_the_ledger_is_counted_for_the_seat_between_the_two_moments(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "calls.jsonl"
            rows = [{"t": 99.0, "seat": 0, "tool": "state", "ok": True},
                    {"t": 100.0, "seat": 0, "tool": "state", "action": "units", "ok": True},
                    {"t": 101.0, "seat": 1, "tool": "order", "action": "unit/move", "ok": True},
                    {"t": 102.0, "seat": 0, "tool": "order", "action": "unit/mission", "ok": True,
                     "args": '{"args":{"mission":"MISSION_SKIP"}}'},
                    {"t": 103.0, "seat": 0, "tool": "order", "action": "city/produce", "ok": False,
                     "err": "city cannot build this: already built"},
                    {"t": 104.0, "seat": 0, "tool": "order", "action": "civ/friendship", "ok": True, "turn": 247,
                     "args": '{"to":"civ","action":"friendship","id":3}', "excerpt": '{"ok":true,"accepted":true}'},
                    {"t": 200.0, "seat": 0, "tool": "turn", "action": "finish", "ok": True}]
            path.write_text("not json\n" + "".join(json.dumps(r) + "\n" for r in rows))
            got = benchmark_run.ledger_counts(path, 0, 100.0, 150.0)
            self.assertEqual((got["calls"], got["unit_skips"]), (4, 1))
            self.assertEqual(got["refused"], {"city cannot build this": 1})
            self.assertEqual(got["with_civs"], [{"turn": 247, "action": "civ/friendship", "ok": True,
                                                 "args": '{"to":"civ","action":"friendship","id":3}',
                                                 "reply": '{"ok":true,"accepted":true}'}])
            self.assertIn("error", benchmark_run.ledger_counts(Path(d) / "none.jsonl", 0, 0, 1))

    def test_a_command_that_names_no_log_folder_has_no_tokens(self):
        self.assertIsNone(benchmark_run.tokens_of(["loop", "--turns", "10"]))
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(benchmark_run.tokens_of(["loop", "--log-dir", d]), "a folder with no record in it")

    def test_the_summary_sets_the_players_figures_side_by_side_and_lists_what_was_said_between_civilizations(self):
        def a_row(name, science, n, cost=None):
            end = played_reply(yields=dict(played_reply()["yields"], science=science))
            end.pop("events")
            r = row(140, turns_played=10, run=n, played={"start": {}, "end": end, "events": EVENTS[1:],
                                                         "counts": {"wars_declared": 1, "wonders": 1}})
            if name:
                r["player"] = name
            if cost:
                r["cost"] = cost
            return r

        cost = {"calls": 60, "refused": {"city cannot build this": 2}, "unit_skips": 7, "tokens": {"new_in": 1000,
                "cache_read": 8000, "cache_write": 1000, "out": 500},
                "with_civs": [{"turn": 247, "action": "civ/friendship", "ok": True, "args": "{}", "reply": "accepted"}]}
        lines = benchmark_run.summarise([a_row(None, 20, 0), a_row(None, 30, 1), a_row("codex/x", 50, 0, cost)])
        at = next(i for i, line in enumerate(lines) if line.startswith("how the seat was played"))
        self.assertEqual(lines[at + 1].split(), ["built-in-ai", "x2", "codex/x", "x1"])
        cell = lambda label: next(line for line in lines[at:] if line.startswith(label))[32:].split()
        self.assertEqual(cell("science a turn"), ["25.0", "50.0"])
        self.assertEqual(cell("friends"), ["1.0", "1.0"])
        self.assertEqual(cell("wars declared, in the run"), ["1.0", "1.0"])
        self.assertEqual(cell("calls a turn"), ["-", "6.0"], "the built-in AI makes no calls")
        self.assertEqual(cell("tokens read a turn"), ["-", "1000.0"])
        self.assertEqual(cell("tokens written a turn"), ["-", "50.0"])
        self.assertEqual(cell("seconds a turn"), ["30.0", "30.0"], "a fact of the run and its machine, whoever played")
        self.assertIn("codex/x, calls refused by reason: 2 city cannot build this", lines)
        self.assertTrue(any(line.startswith("codex/x seed 0, turn 247: civ/friendship") for line in lines))
        war = next(line for line in lines if line.startswith("built-in-ai seed 1, war and peace:"))
        self.assertIn("turn 244 Boudicca declares war on Maria Theresa!", war)
        self.assertIn("turn 250 Maria Theresa has made peace with Boudicca!", war)
        self.assertNotIn("Great Library", war)

    def test_rows_from_before_have_no_such_table(self):
        self.assertFalse(any("how the seat was played" in line for line in benchmark_run.summarise([row(140), row(150)])))


class Lua(unittest.TestCase):
    def test_the_chunks_compile(self):
        try:
            import lupa
        except ImportError:
            self.skipTest("lupa is not installed")
        lua = lupa.LuaRuntime()
        for name, body in (("READ", benchmark_run.READ), ("POLL", benchmark_run.POLL % {"seat": 0}),
                           ("SKIP", benchmark_run.SKIP % {"skip": 17}), ("LEAVE", benchmark_run.LEAVE),
                           ("START", benchmark_run.start_chunk(3, 10, 0)),
                           ("START with terms", benchmark_run.start_chunk(3, 10, 0, row="ai", time="off"))):
            with self.subTest(name):
                self.assertTrue(lua.eval("function(src) return loadstring and loadstring(src) or load(src) end")(body),
                                f"{name} does not compile")


class APlayersSavesOnTheWay(unittest.TestCase):
    """`--checkpoint N` with a player's command: the seat's own server quick-saves before it ends each turn, and the
    runner keeps a copy of that file for every game turn that is a multiple of N."""

    def setUp(self):
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(mock.patch.dict(os.environ, {"CIV5_SAVES_DIR": str(self.dir)}))
        self.quick = self.dir / "quick" / "QuickSave.Civ5Save"
        self.writes = 0

    def write(self, text):
        self.writes += 1
        self.quick.parent.mkdir(parents=True, exist_ok=True)
        self.quick.write_text(text)
        os.utime(self.quick, ns=(self.writes * 10 ** 9, self.writes * 10 ** 9))

    def saves(self, every=10, start=242):
        clock = Clock()
        return benchmark_run.SavesOnTheWay(every, "save--codex-x-seed0", start,
                                           copy=lambda name, was: benchmark_run.copy_quick(name, was, sleep=clock.sleep, clock=clock))

    def files(self):
        return {p.stem: p.read_text() for p in self.dir.glob("*.Civ5Save")}

    def test_the_first_quick_save_written_at_or_past_a_multiple_is_kept_under_it(self):
        s = self.saves()
        self.write("turn 248")
        self.assertIsNone(s.look(249))
        self.write("turn 249")                       # the seat ends turn 249: its file is of the turn before the multiple
        self.assertIsNone(s.look(250), "the file that stood when turn 250 was first seen is not turn 250's")
        self.assertIsNone(s.look(250))
        self.write("turn 250")
        self.assertEqual(s.look(250), {"turn": 250, "save": "save--codex-x-seed0-t250", "seen_on_turn": 250})
        self.write("turn 251")
        self.assertIsNone(s.look(252))
        self.assertEqual(self.files(), {"save--codex-x-seed0-t250": "turn 250"})
        self.assertEqual(s.next, 260)

    def test_a_seat_that_ended_many_turns_between_two_looks_has_one_save_for_them(self):
        s = self.saves()
        self.write("turn 249")
        self.assertIsNone(s.look(263))               # quiet turns skipped: two multiples went by between two looks
        self.write("turn 263")
        self.assertEqual(s.look(264), {"turn": 250, "save": "save--codex-x-seed0-t250", "seen_on_turn": 264})
        self.assertEqual(s.next, 270, "a second file of the same turns for the multiple that went by")

    def test_a_game_with_no_new_quick_save_keeps_nothing(self):
        s = self.saves()
        self.write("turn 249")
        for turn in (250, 251, 252):
            self.assertIsNone(s.look(turn))
        self.assertEqual((s.kept, self.files()), ([], {}))

    def test_the_first_multiple_is_the_one_after_the_turn_the_run_starts_on(self):
        self.assertEqual((self.saves(start=0).next, self.saves(start=250).next, self.saves(every=25, start=30).next), (10, 260, 50))

    def player_run(self, checkpoint):
        seen = {}

        def watch(g, seat, saves, poll):
            seen["saves"], seen["ended"] = saves, 0
            def end():
                seen["ended"] += 1
            return end

        def command(cmd, timeout, check):
            s = seen.get("saves")
            if s is not None:
                s.copy = lambda name, was: benchmark_run.copy_quick(name, was, sleep=Clock().sleep, clock=Clock())
                for turn, text in ((249, "turn 249"), (250, None), (250, "turn 250"), (251, "turn 251"), (252, None)):
                    if text:
                        self.write(text)
                    s.look(turn)
            return subprocess.CompletedProcess(cmd, 0)

        nb = self.dir / "notes" / "game-seat0.json"
        g = FakeGame([read(), read(turn=252, players=[player(0, human=True, turn_active=True), player(1)])], polls=[poll(252, 0)])
        clock = Clock()
        row = benchmark_run.run_player(g, "save", ["loop"], "codex/x", 10, run=command, watch=watch, checkpoint=checkpoint,
                                       checkpoint_name="save--codex-x-seed0", sleep=clock.sleep, clock=clock,
                                       path_of=lambda _g, _seat: nb)
        return row, seen

    def test_a_players_run_lists_the_saves_kept_on_the_way_and_ends_the_watch(self):
        row, seen = self.player_run(10)
        self.assertEqual(row["checkpoints"], [{"turn": 250, "save": "save--codex-x-seed0-t250", "seen_on_turn": 250}])
        self.assertEqual(self.files(), {"save--codex-x-seed0-t250": "turn 250"})
        self.assertEqual(seen["ended"], 1, "the watch was left running after the command")
        self.assertEqual(seen["saves"].next, 260)
        json.dumps(row)

    def test_a_players_run_with_no_saves_asked_is_not_watched(self):
        row, seen = self.player_run(0)
        self.assertEqual((seen, self.files()), ({}, {}))
        self.assertNotIn("checkpoints", row)

    def test_the_watch_looks_at_the_games_turn_until_it_is_ended_and_a_failed_read_costs_one_look(self):
        looks = []

        class Saves:
            def look(self, turn):
                looks.append(turn)

        class Game:
            asked = 0

            def q(self, code):
                self.asked += 1
                if self.asked == 2:
                    raise RuntimeError("the game did not answer")
                return {"turn": 250 + self.asked}

        g = Game()
        end = benchmark_run.watch_saves(g, 0, Saves(), poll=0.01)
        import time as _time
        t0 = _time.monotonic()
        while len(looks) < 3 and _time.monotonic() - t0 < 5:
            _time.sleep(0.01)
        end()
        asked = g.asked
        _time.sleep(0.05)
        self.assertEqual(looks[:3], [251, 253, 254], "the look after the failed read was not made")
        self.assertEqual(g.asked, asked, "the watch went on after it was ended")

    def test_saves_on_the_way_go_with_a_run_and_not_with_finish_only(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            benchmark_run.main(["--save", "s", "--out", str(self.dir / "rows.jsonl"), "--checkpoint", "10",
                                "--finish-only", "--ai-finishes", "1"])
        self.assertIn("--checkpoint N goes with a run", err.getvalue())


if __name__ == "__main__":
    unittest.main()
