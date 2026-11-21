"""Token accounting, stage 2 (docs/TOKEN_ACCOUNTING.md; GitLab #185): the seat loop stamps the CLI's stream,
frames it with two rows of its own, keeps the client's per-request record beside it, and runs Claude; and
`harness.usage.cycle` reads a cycle back from the log directory alone."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from harness.usage import cycle, rows

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "usage"
_spec = importlib.util.spec_from_file_location("llm_seat_loop", ROOT / "scripts" / "llm_seat_loop.py")
loop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(loop)

SESSION = "11111111-2222-4333-8444-555555555555"


def fake_cli(lines: list[str], rc: int = 0) -> list[str]:
    """A command that prints the lines as a CLI would and exits."""
    return [sys.executable, "-c", f"import sys\nfor l in {lines!r}: print(l, flush=True)\nsys.exit({rc})"]


def run(tmp: Path, agent: str, lines: list[str], *, home: Path | None = None, session: str | None = None,
        cycle_no: int = 3, cmd: list[str] | None = None, **kw) -> tuple[Path, tuple[int, str]]:
    stream = tmp / f"{agent}-c{cycle_no}.jsonl"
    header = {"agent": agent, "model": "m-1", "effort": "low", "seat": 1, "cycle": cycle_no, "turns": 5,
              "client": f"{agent}/m-1", "session": session}
    got = loop.run_cycle(cmd or fake_cli(lines), cwd=tmp, env={}, stream=stream, err_path=tmp / "err",
                         header=header, timeout=kw.pop("timeout", 60), home=home or tmp / "home", **kw)
    return stream, got


def objects(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


class StampTests(unittest.TestCase):
    def test_a_json_object_gets_its_arrival_time_first_and_keeps_its_bytes(self):
        line = b'{"type": "usage", "usage": {"input_tokens": 7},  "note": "caf\xc3\xa9"}\n'
        out = loop.stamp(line, 1794631521.4337)
        self.assertEqual(out, b'{"t":1794631521.434,"type": "usage", "usage": {"input_tokens": 7},  "note": "caf\xc3\xa9"}\n')
        self.assertEqual(next(iter(json.loads(out))), "t")

    def test_what_is_not_one_object_passes_as_it_came(self):
        for line in (b"Loading...\n", b'{"torn": \n', b"[1, 2]\n", b"\n", b'{"t": 5, "type": "x"}\n'):
            self.assertEqual(loop.stamp(line, 9.0), line)
        self.assertEqual(json.loads(loop.stamp(b"{}\n", 9.0)), {"t": 9.0})
        self.assertEqual(json.loads(loop.stamp(b'  { "a": 1 }  \r\n', 9.5)), {"t": 9.5, "a": 1})


class CommandTests(unittest.TestCase):
    def test_claude_gets_the_seat_and_nothing_of_the_operators_setup(self):
        cmd = loop.build_cmd("claude", "sonnet", "low", "PROMPT", Path("/seat"), Path("/x/last.md"), SESSION)
        self.assertEqual(cmd[:3], ["claude", "-p", "PROMPT"])

        def after(flag):
            return cmd[cmd.index(flag) + 1]
        self.assertEqual((after("--model"), after("--effort"), after("--session-id")), ("sonnet", "low", SESSION))
        self.assertEqual((after("--output-format"), after("--setting-sources")), ("stream-json", "local"))
        self.assertEqual(after("--mcp-config"), "/seat/.mcp.json")
        self.assertIn("--strict-mcp-config", cmd)
        self.assertIn("--verbose", cmd)                        # stream-json under -p needs it
        self.assertEqual(after("--tools"), "Read,Write,Edit,Glob,Grep")
        self.assertEqual(cmd[cmd.index("--allowedTools") + 1:], ["mcp__civ5", "Read", "Write", "Edit", "Glob", "Grep"])
        self.assertNotIn("Bash", " ".join(cmd[3:]))

    def test_the_other_two_are_as_they_were_and_an_unknown_agent_is_refused(self):
        self.assertEqual(loop.build_cmd("codex", "m", "low", "P", Path("/s"), Path("/l"))[:2], ["codex", "exec"])
        self.assertEqual(loop.build_cmd("grok", "m", "low", "P", Path("/s"), Path("/l"))[:3], ["grok", "-p", "P"])
        with self.assertRaises(SystemExit):
            loop.build_cmd("other", "m", "low", "P", Path("/s"), Path("/l"))

    def test_the_prompt_speaks_the_nine_tools(self):
        text = loop.prompt_for(5, "c1-x")
        for old in ("finish_turn", "set_seat", "`lua`", "recall`", "skip_quiet_turns", "give_order"):
            self.assertNotIn(old, text)
        self.assertIn('turn(action="finish")', text)
        self.assertIn("reports/c1-x.md", text)

    def test_the_instance_ends_on_a_turn_that_is_the_seats_not_on_a_count_of_finishes(self):
        """Live 2026-11-16: Codex stopped after its tenth finish, a leader on screen and the game nine turns on."""
        text = loop.prompt_for(5, "c1-x")
        self.assertEqual(text.count("turn T0+5 is yours"), 2)
        self.assertNotIn("T0+4", text)
        self.assertIn("a finish that comes back\n   on the same turn", text)
        self.assertNotIn("whichever", text)

    def test_a_benchmark_runs_last_turn_is_named_as_well(self):
        text = loop.prompt_for(10, "c1-x", until=262)
        self.assertEqual(text.count("turn T0+10 or turn 262 is yours, whichever comes first"), 2)
        self.assertIn("with T0 at 262 or later there is nothing to play", text)


class RunCycleTests(unittest.TestCase):
    def test_a_grok_cycle_is_framed_stamped_and_read_back_from_the_log_directory(self):
        raw = (FIXTURES / "grok-stream.jsonl").read_text().splitlines()
        with tempfile.TemporaryDirectory() as d:
            stream, (rc, killed) = run(Path(d), "grok", ["a banner", *raw])
            self.assertEqual((rc, killed), (0, ""))
            got = [json.loads(x) for x in stream.read_text().splitlines() if x.startswith("{")]
            first, last = got[0], got[-1]
            self.assertEqual(first["type"], "seat_loop.cycle")
            self.assertEqual({k: first[k] for k in ("agent", "model", "effort", "seat", "cycle", "turns", "client")},
                             {"agent": "grok", "model": "m-1", "effort": "low", "seat": 1, "cycle": 3, "turns": 5,
                              "client": "grok/m-1"})
            self.assertEqual(last["type"], "seat_loop.cycle_end")
            self.assertEqual((last["rc"], last["killed"], last["usage_file"], last["start"]), (0, "", None, first["start"]))
            self.assertTrue(all(isinstance(o.get("t"), float) for o in got))
            self.assertTrue(all(first["start"] <= o["t"] <= last["end"] for o in got))
            self.assertIn("a banner\n", stream.read_text())

            head, usage = cycle.read(stream)
            from harness.usage import grok
            plain = grok.read(raw)
            self.assertEqual(rows.total(usage), rows.total(plain))
            self.assertEqual([r["calls"] for r in usage], [r["calls"] for r in plain])
            self.assertEqual({k: rows.total(usage)[k] for k in rows.COUNTS}, cycle.own_total(stream))
            self.assertTrue(all(first["start"] <= r["t"] <= last["end"] for r in usage))   # the fixture has no time
            self.assertEqual({(r["seat"], r["cycle"], r["label"]) for r in usage}, {(1, 3, "grok/m-1")})
            self.assertEqual((head["end"], head["rc"], head["agent"]), (last["end"], 0, "grok"))

    def test_a_codex_cycle_keeps_its_rollout_found_by_the_streams_thread_id(self):
        exec_lines = (FIXTURES / "codex-exec.jsonl").read_text().splitlines()
        rollout = (FIXTURES / "codex-rollout.jsonl").read_text()
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            thread = next(json.loads(x)["thread_id"] for x in exec_lines if '"thread.started"' in x)
            day = tmp / "home" / ".codex" / "sessions" / "2026" / "11" / "13"
            day.mkdir(parents=True)
            (day / f"rollout-2026-11-13T22-00-00-{thread}.jsonl").write_text(rollout)
            (day / "rollout-2026-11-13T21-00-00-another-thread.jsonl").write_text("{}\n")
            stream, _ = run(tmp, "codex", exec_lines)
            end = objects(stream)[-1]
            self.assertEqual((end["usage_file"], end["session"]), ("codex-c3.rollout.jsonl", thread))
            self.assertEqual((tmp / "codex-c3.rollout.jsonl").read_text(), rollout)

            from harness.usage import codex
            _, usage = cycle.read(stream)
            self.assertEqual(usage and rows.total(usage), rows.total(codex.read(rollout.splitlines())))
            self.assertEqual({k: rows.total(usage)[k] for k in rows.COUNTS}, cycle.own_total(stream))
            self.assertEqual({r["label"] for r in usage}, {"codex/m-1"})
            self.assertTrue(all(r["t"] for r in usage))            # the rollout's own times

    def test_a_claude_cycle_keeps_its_transcript_found_by_the_session_id_it_was_given(self):
        transcript = (FIXTURES / "claude-code-transcript.jsonl").read_text()
        from harness.usage import claude_code
        want = rows.total(claude_code.read(transcript.splitlines()))
        result = {"type": "result", "subtype": "success", "modelUsage": {"claude-x": {
            "inputTokens": want["new_in"], "cacheReadInputTokens": want["cache_read"],
            "cacheCreationInputTokens": want["cache_write"], "outputTokens": want["out"],
            "thinkingTokens": want["reasoning"]}}}
        # what the stream says of a request is its first frame: were it read for rows, the output would be short
        early = {"type": "assistant", "request_id": "req_1", "message": {"id": "msg_1", "model": "claude-x",
                 "usage": {"input_tokens": 2, "output_tokens": 1}, "content": []}}
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            proj = tmp / "home" / ".claude" / "projects" / "-some-seat"
            proj.mkdir(parents=True)
            (proj / f"{SESSION}.jsonl").write_text(transcript)
            stream, _ = run(tmp, "claude", [json.dumps(early), json.dumps(result)], session=SESSION)
            end = objects(stream)[-1]
            self.assertEqual((end["usage_file"], end["session"]), ("claude-c3.transcript.jsonl", SESSION))
            head, usage = cycle.read(stream)
            self.assertEqual(rows.total(usage), want)
            self.assertEqual({k: want[k] for k in rows.COUNTS}, cycle.own_total(stream))
            self.assertEqual(head["usage_file"], "claude-c3.transcript.jsonl")

    def test_a_record_that_is_not_there_is_said_and_the_cycle_has_no_rows(self):
        with tempfile.TemporaryDirectory() as d:
            stream, _ = run(Path(d), "claude", ['{"type": "system"}'], session=SESSION)
            self.assertIsNone(objects(stream)[-1]["usage_file"])
            head, usage = cycle.read(stream)
            self.assertEqual((usage, cycle.own_total(stream)), ([], None))
            self.assertNotIn("usage_file", head)

    def test_a_cycle_past_its_time_is_killed_and_still_closed(self):
        with tempfile.TemporaryDirectory() as d:
            cmd = [sys.executable, "-c", "import time\nprint('{\"type\": \"usage\", \"usage\": {\"input_tokens\": 4}}', "
                                         "flush=True)\ntime.sleep(60)"]
            stream, (rc, killed) = run(Path(d), "grok", [], cmd=cmd, timeout=0.3, poll=0.2)
            self.assertEqual(killed, "cycle timeout")
            self.assertNotEqual(rc, 0)
            end = objects(stream)[-1]
            self.assertEqual((end["type"], end["killed"]), ("seat_loop.cycle_end", "cycle timeout"))
            _, usage = cycle.read(stream)
            self.assertEqual([(r["new_in"], r["model"]) for r in usage], [(4, "m-1")])   # no `end` row: the header's model
            self.assertIsNone(cycle.own_total(stream))

    def test_stop_now_kills_the_cycle(self):
        with tempfile.TemporaryDirectory() as d:
            cmd = [sys.executable, "-c", "import time\ntime.sleep(60)"]
            _, (_, killed) = run(Path(d), "grok", [], cmd=cmd, poll=0.2, stop_now=lambda: True)
            self.assertEqual(killed, "STOP_NOW")


class OldStreamTests(unittest.TestCase):
    def test_a_stream_from_before_the_header_is_read_by_its_name(self):
        with tempfile.TemporaryDirectory() as d:
            old = Path(d) / "grok-c12.jsonl"
            old.write_text((FIXTURES / "grok-stream.jsonl").read_text())
            head, usage = cycle.read(old)
            self.assertEqual((head, bool(usage)), ({"agent": "grok", "cycle": 12}, True))
            self.assertEqual({(r["t"], r["seat"], r["label"]) for r in usage}, {(None, None, None)})
            self.assertEqual({k: rows.total(usage)[k] for k in rows.COUNTS}, cycle.own_total(old))
            codex_old = Path(d) / "codex-c4.jsonl"
            codex_old.write_text((FIXTURES / "codex-exec.jsonl").read_text())
            self.assertEqual(cycle.read(codex_old)[1], [])           # an exec stream alone has a total and no request
            self.assertIsNotNone(cycle.own_total(codex_old))



class LastTurnReached(unittest.TestCase):
    """A benchmark run's last turn (docs/BENCHMARK.md rule 5): with `--until-turn` the loop ends by the game, read
    before every cycle, and not by a count of cycles."""

    def over(self, now, until=100):
        return loop.last_turn_reached(until, 0, read=lambda seat: now)

    def test_a_run_with_turns_left_wants_another_instance(self):
        self.assertEqual(self.over({"turn": 99, "winner": -1, "alive": True}), "")

    def test_the_turn_that_is_the_seats_ends_it(self):
        self.assertIn("turns are over", self.over({"turn": 100, "winner": -1, "alive": True}))
        self.assertIn("turn 103 of 100", self.over({"turn": 103, "winner": -1, "alive": True}))

    def test_a_decided_game_or_a_dead_seat_ends_it_before_the_turn(self):
        self.assertEqual(self.over({"turn": 40, "winner": 1, "alive": True}), "the game is decided")
        self.assertEqual(self.over({"turn": 40, "winner": -1, "alive": False}), "the seat is dead")

    def test_a_read_that_fails_or_says_nothing_does_not_end_the_loop(self):
        def down(seat):
            raise OSError("no socket")
        self.assertEqual(loop.last_turn_reached(100, 0, read=down), "")
        self.assertEqual(self.over(None), "")
        self.assertEqual(self.over({}), "")

    def test_the_read_names_the_seat(self):
        seen = []
        loop.last_turn_reached(100, 2, read=lambda seat: seen.append(seat) or {"turn": 1})
        self.assertEqual(seen, [2])
        self.assertIn("Players[2]", loop.TURN_READ % 2)

if __name__ == "__main__":
    unittest.main()
