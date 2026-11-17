#!/usr/bin/env python3
"""Run one LLM CLI (codex, grok or claude) as a hotseat seat, in fresh instances of N turns each.

Each cycle starts a new CLI process (a fresh context window) with the same prompt: read AGENTS.md
in the seat directory, play N game turns through the civ5 MCP tools, write a report into
reports/, stop. When the process exits the loop starts the next cycle. A file named STOP in the
seat directory ends the loop after the current cycle; STOP_NOW kills the current cycle too.

Usage:
  scripts/llm_seat_loop.py --agent codex --seat 0 --dir ~/projects/codex-seat \
      --model gpt-5.6-terra --effort low --turns 20
  scripts/llm_seat_loop.py --agent grok --seat 1 --dir ~/projects/grok-desk-seat \
      --model grok-4.7 --effort low --turns 20
  scripts/llm_seat_loop.py --agent claude --seat 2 --dir ~/projects/claude-seat \
      --model sonnet --effort low --turns 20

Where the seat is pinned: codex reads the civ5 server from its own config, grok and claude from
`.mcp.json` in the seat directory (claude is given that file and no other server). Grok starts
a folder's `.mcp.json` only in a folder it trusts (`~/.grok/trusted_folders.toml`; `grok mcp doctor`
in the seat directory says "folder untrusted" otherwise, and the seat then finds no civ5 tool).

Logs: <log-dir>/<agent>-c<cycle>.jsonl (the CLI's event stream) and <agent>-c<cycle>.err.
The loop's own line-per-event log is <log-dir>/<agent>-loop.log (cycle start/end, exit code,
report path), which is what an observer tails.

What the stream carries beside the CLI's own lines (token accounting, docs/TOKEN_ACCOUNTING.md
stage 2; `harness/usage/cycle.py` reads it):
  - every JSON line is given a `t`, the epoch second it arrived (Grok's stream has no time at all);
  - a `seat_loop.cycle` row opens the cycle (agent, model, effort, seat, cycle, turns, start, the
    ledger's client label) and a `seat_loop.cycle_end` row closes it (start, end, rc, killed,
    usage_file).
`usage_file` is the client's own per-request record, copied beside the stream when the cycle ends:
<agent>-c<cycle>.rollout.jsonl for codex (its exec stream has one total and no request), and
<agent>-c<cycle>.transcript.jsonl for claude (its stream reports a request's output before the
request is complete). Grok's stream is its record. So one cycle's accounting needs nothing from a
home directory afterwards.
"""
import argparse
import datetime as dt
import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

AGENTS = ("codex", "grok", "claude")
CYCLE, CYCLE_END = "seat_loop.cycle", "seat_loop.cycle_end"

PROMPT = """Read AGENTS.md in this directory first: it says who you are and how the civ5 tools work.

This is one instance of a long game; your context will be reset after this instance. Play your
seat until {window}, then stop:

1. Call `turn(action="briefing", since="turn")` first. Your notes from earlier instances
   (`notebook(action="recall")`, and the `assignments` shown in the briefing) are the memory that
   survives resets; trust them over guesses. The game turn you see in that first status is T0.
2. Each turn: act on the briefing's decisions and `status.todo`, give a unit a standing order where
   a plan spans turns, `notebook(action="remember")` what future-you must know, then
   `turn(action="finish")`. `reference(book="playbook")` says how to pass quiet turns cheaply.
3. The instance is over when {window}: the status that `turn(action="finish")` returns reads that
   turn. Stop there and leave that turn unplayed. Until then keep going: a finish that comes back
   on the same turn (a `gate`, a leader on screen, something still to answer) has not ended it, so
   answer what is asked and finish again. If the game ends, or a tool reports the game or the
   bridge is down, stop at once instead.
4. Then write `reports/{stamp}.md` in this directory (a plain file, nothing else on disk) with these
   headings: **Turns** (T0 to the last turn you ended, and what you did in one line per turn),
   **Stumbles** (every tool refusal, error, retry, confusing answer, or moment you did not know what
   to call: quote the tool, the arguments and the answer verbatim), **Wishes** (what a tool should
   have told you or done to make this easier), **State for next instance** (your plan, in the words
   you also left in the notebook). Then reply with one line and finish.

Rules: only the civ5 MCP tools touch the game; never run scripts or shell commands against it,
never use `session` to change the seat, load a save or leave the game, never write outside this
directory. Any other human seat is another LLM; you see nothing of its turn, and you do not try to.
Play to win.
"""


def window_words(turns: int, until: int | None = None) -> str:
    """The end of an instance, as the turn that is the seat's when it is over. A count of turns ended is not
    the same thing: Codex stopped after its tenth `finish` with a leader on screen and the board nine turns on
    (live 2026-11-16), so the entrant is told the turn and that a finish on the same turn has not ended it."""
    if until is None:
        return f"turn T0+{turns} is yours"
    return (f"turn T0+{turns} or turn {until} is yours, whichever comes first (with T0 at {until} or later there "
            "is nothing to play)")


def prompt_for(turns: int, stamp: str, until: int | None = None) -> str:
    return PROMPT.format(window=window_words(turns, until), stamp=stamp)


def build_cmd(agent: str, model: str, effort: str, prompt: str, seat_dir: Path, last_msg: Path,
              session: str | None = None):
    if agent == "codex":
        return [
            "codex", "exec", "-C", str(seat_dir), "--skip-git-repo-check",
            "--sandbox", "workspace-write", "--json", "-o", str(last_msg),
            "-m", model, "-c", f"model_reasoning_effort={effort!r}",
            # exec never asks; without this the civ5 tools are refused with
            # "MCP tool call requires approval, but approval policy is never"
            "-c", "approval_policy='never'",
            "-c", 'mcp_servers.civ5.default_tools_approval_mode="approve"',
            prompt,
        ]
    if agent == "grok":
        return [
            "grok", "-p", prompt, "-m", model, "--effort", effort,
            "--always-approve", "--no-subagents", "--no-plan",
            "--output-format", "streaming-json",
        ]
    if agent == "claude":
        return [
            "claude", "-p", prompt, "--model", model, "--effort", effort,
            "--output-format", "stream-json", "--verbose", "--session-id", session or str(uuid.uuid4()),
            # The seat and nothing of the operator's own Claude Code: no user or project settings (plugins,
            # hooks, the CLAUDE.md files of the directories above), no server but the seat's, no skills, and
            # of the built-in tools only the ones a report needs. Whatever is not allowed below is denied,
            # since nobody answers a prompt under -p.
            "--setting-sources", "local", "--disable-slash-commands",
            "--strict-mcp-config", "--mcp-config", str(seat_dir / ".mcp.json"),
            "--tools", "Read,Write,Edit,Glob,Grep",
            "--allowedTools", "mcp__civ5", "Read", "Write", "Edit", "Glob", "Grep",
        ]
    raise SystemExit(f"unknown agent {agent!r}")


def stamp(line: bytes, t: float) -> bytes:
    """A stream line with its arrival time as the first key, `t`. Only a line that is one JSON object gets
    one; a banner, a torn line or an object that already has a `t` passes as it came. The rest of the line
    is not re-encoded: the bytes after the brace are the CLI's own."""
    body = line.strip()
    if not body.startswith(b"{"):
        return line
    try:
        o = json.loads(body)
    except ValueError:
        return line
    if not isinstance(o, dict) or "t" in o:
        return line
    rest = body[1:].lstrip()
    head = b'{"t":%.3f' % t
    return head + (b"}" if rest == b"}" else b"," + rest) + b"\n"


def pump(src, dst, clock=time.time) -> None:
    """Copy the CLI's stdout to the stream file line by line, each stamped as it arrives."""
    for line in iter(src.readline, b""):
        dst.write(stamp(line, clock()))
        dst.flush()


def marker(kind: str, t: float, **fields) -> bytes:
    return (json.dumps({"t": round(t, 3), "type": kind, **fields}) + "\n").encode()


def codex_thread(stream: Path, since: int = 0) -> str | None:
    """The thread id of the cycle that wrote the stream from byte `since` on (its `thread.started` row)."""
    found = None
    with stream.open("rb") as fh:
        fh.seek(since)
        for line in fh:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if isinstance(o, dict) and o.get("type") == "thread.started" and o.get("thread_id"):
                found = str(o["thread_id"])
    return found


def usage_source(agent: str, session: str | None, home: Path | None = None) -> Path | None:
    """The client's own per-request record of one session: codex's rollout, claude's transcript."""
    home = home or Path.home()
    if not session:
        return None
    if agent == "codex":
        root = Path(os.environ.get("CODEX_HOME") or home / ".codex") / "sessions"
        hits = sorted(root.glob(f"**/rollout-*-{session}.jsonl"))
    elif agent == "claude":
        root = Path(os.environ.get("CLAUDE_CONFIG_DIR") or home / ".claude") / "projects"
        hits = sorted(root.glob(f"*/{session}.jsonl"))
    else:
        return None
    return hits[-1] if hits else None


USAGE_SUFFIX = {"codex": "rollout", "claude": "transcript"}


def keep_usage(agent: str, session: str | None, stream: Path, home: Path | None = None) -> str | None:
    """Copy the session's record beside the stream; the name of the copy, or None when the client keeps
    none (grok) or it was not found. A cycle number run twice appends, as the stream does: the readers
    count a request id once."""
    src = usage_source(agent, session, home)
    if src is None:
        return None
    dst = stream.with_name(f"{stream.stem}.{USAGE_SUFFIX[agent]}.jsonl")
    with src.open("rb") as a, dst.open("ab") as b:
        for chunk in iter(lambda: a.read(1 << 20), b""):
            b.write(chunk)
    return dst.name


def run_cycle(cmd: list[str], *, cwd: Path, env: dict, stream: Path, err_path: Path, header: dict,
              timeout: float, stop_now=lambda: False, poll: float = 15, home: Path | None = None) -> tuple[int, str]:
    """One CLI process from start to exit: its stdout stamped into `stream` between the two cycle rows, its
    stderr into `err_path`. Returns (exit code, why it was killed or "")."""
    agent = header["agent"]
    t0 = time.time()
    with stream.open("ab") as out, err_path.open("ab") as err:
        since = out.tell()
        out.write(marker(CYCLE, t0, **header, start=round(t0, 3)))
        out.flush()
        proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=err, env=env,
                                stdin=subprocess.DEVNULL, start_new_session=True)
        reader = threading.Thread(target=pump, args=(proc.stdout, out), daemon=True)
        reader.start()
        killed = ""
        while True:
            try:
                rc = proc.wait(timeout=poll)
                break
            except subprocess.TimeoutExpired:
                pass
            if stop_now():
                killed = "STOP_NOW"
            elif time.time() - t0 > timeout:
                killed = "cycle timeout"
            if killed:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    rc = proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    rc = proc.wait()
                break
        reader.join(timeout=30)            # a child that outlives the CLI may still hold the pipe: do not wait on it
        out.flush()
        session = header.get("session") or (codex_thread(stream, since) if agent == "codex" else None)
        try:
            usage_file = keep_usage(agent, session, stream, home)
        except OSError:
            usage_file = None
        t1 = time.time()
        out.write(marker(CYCLE_END, t1, cycle=header.get("cycle"), start=round(t0, 3), end=round(t1, 3), rc=rc,
                         killed=killed, session=session, usage_file=usage_file))
    return rc, killed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent", choices=AGENTS, required=True)
    ap.add_argument("--seat", type=int, required=True, help="only for the log line and the cycle row; the seat is pinned in the CLI's MCP config")
    ap.add_argument("--dir", required=True, help="the seat directory (AGENTS.md, reports/)")
    ap.add_argument("--model", required=True)
    ap.add_argument("--effort", default="low")
    ap.add_argument("--turns", type=int, default=20)
    ap.add_argument("--until-turn", type=int, default=None, metavar="N",
                    help="a referee's window: every instance is also told to stop when game turn N is the seat's")
    ap.add_argument("--cycles", type=int, default=0, help="0 = until STOP")
    ap.add_argument("--cycle-timeout", type=int, default=4 * 3600, help="seconds before a cycle is killed")
    ap.add_argument("--log-dir", default=str(Path(__file__).resolve().parent.parent / "logs" / "night"))
    ap.add_argument("--start-cycle", type=int, default=1)
    args = ap.parse_args()

    seat_dir = Path(args.dir).expanduser().resolve()
    log_dir = Path(args.log_dir).expanduser().resolve()
    if args.agent == "claude" and not (seat_dir / ".mcp.json").is_file():
        raise SystemExit(f"--agent claude needs {seat_dir / '.mcp.json'}: the civ5 server with the seat pinned "
                         "(it is the only server the seat is given)")
    log_dir.mkdir(parents=True, exist_ok=True)
    (seat_dir / "reports").mkdir(parents=True, exist_ok=True)
    loop_log = log_dir / f"{args.agent}-loop.log"

    def log(msg: str) -> None:
        line = f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {args.agent} seat {args.seat}: {msg}"
        with loop_log.open("a") as fh:
            fh.write(line + "\n")
        print(line, flush=True)

    cycle = args.start_cycle
    quick = 0
    log(f"loop start pid {os.getpid()} model {args.model} effort {args.effort} turns/cycle {args.turns}")
    while True:
        if (seat_dir / "STOP").exists() or (seat_dir / "STOP_NOW").exists():
            log("STOP file present, loop ends")
            return 0
        if args.cycles and cycle >= args.start_cycle + args.cycles:
            log("cycle budget spent, loop ends")
            return 0
        stamp_ = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        prompt = prompt_for(args.turns, f"c{cycle}-{stamp_}", args.until_turn)
        last_msg = log_dir / f"{args.agent}-c{cycle}.last.md"
        session = str(uuid.uuid4()) if args.agent == "claude" else None
        cmd = build_cmd(args.agent, args.model, args.effort, prompt, seat_dir, last_msg, session)
        t0 = time.time()
        log(f"cycle {cycle} start")
        # The call ledger (harness/call_ledger.py) attributes rows to this agent and model when the CLI passes
        # its environment on to the MCP server it spawns (grok and claude do; codex needs the seat's config to
        # forward CIV5_CLIENT and CIV5_CALL_LOG). Both are left alone when the operator already set them.
        env = dict(os.environ)
        env.setdefault("CIV5_CLIENT", f"{args.agent}/{args.model}")
        env.setdefault("CIV5_CALL_LOG", str(Path(__file__).resolve().parent.parent / "logs" / "calls.jsonl"))
        if args.agent == "claude":
            # a loop started from inside a Claude Code session must not hand that session's identity down, and
            # the seat's memory is the notebook: no second one under the operator's home
            for k in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"):
                env.pop(k, None)
            env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
        header = {"agent": args.agent, "model": args.model, "effort": args.effort, "seat": args.seat,
                  "cycle": cycle, "turns": args.turns, "client": env["CIV5_CLIENT"], "session": session}
        rc, killed = run_cycle(cmd, cwd=seat_dir, env=env, stream=log_dir / f"{args.agent}-c{cycle}.jsonl",
                               err_path=log_dir / f"{args.agent}-c{cycle}.err", header=header,
                               timeout=args.cycle_timeout, stop_now=(seat_dir / "STOP_NOW").exists)
        reports = sorted(p for p in (seat_dir / "reports").glob(f"c{cycle}-*.md"))
        log(f"cycle {cycle} end rc {rc} after {int(time.time() - t0)} s"
            + (f" ({killed})" if killed else "")
            + (f" report {reports[-1].name}" if reports else " NO REPORT"))
        cycle += 1
        if killed == "STOP_NOW":
            return 0
        # a cycle that ends within a minute did not play: back off instead of spinning
        if time.time() - t0 < 60:
            quick += 1
            pause = min(600, 60 * quick)
            log(f"cycle ended early ({quick} in a row); pausing {pause} s")
            time.sleep(pause)
        else:
            quick = 0
            time.sleep(5)


if __name__ == "__main__":
    sys.exit(main())
