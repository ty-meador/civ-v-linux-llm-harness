"""One sequenced stream out of every source, with a recorder, a replayer and the live poller.

Event shape: `{"seq": n, "t": unix_time, "type": ..., "data": {...}}`. Types: `hello` (the map and how to draw it),
`snapshot` (snapshot.py), `call` (one ledger row), `event` (one runtime event with its audience), `notebook` (one
seat's notes/assignments/orders), `usage` (tokens per seat, usage_watch.py; each one replaces the one before),
`status` (the spectator's own health). The ring keeps the last RING events for
SSE resumes; `state()` is what a page that just opened needs to draw the world at once.

The recording (`--record` while live, the file itself under `--replay`) is also what the page scrubs through:
`Feed.recording()` yields its rows with the seq numbers the stream carries, so the page can hold the whole file
and dedupe the SSE tail against it (server.py `/recording`).

A game file (game_file.py: one line a turn, taken inside the game) replays the same way: `open_replay()` turns it,
or a benchmark run's packed recording that holds one, into this stream's events, and the page draws it with no
code of its own for it.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import zipfile
from typing import Any, Callable, Iterable, Iterator

from . import events as events_mod
from . import game_file, ledger_tail, mapdump, notebook_watch, snapshot

RING = 6000
RECENT_CALLS = 300
RECENT_EVENTS = 300


class Feed:
    def __init__(self, record_path: str | None = None, ring: int = RING, recording_path: str | None = None,
                 mode: str = "live", recording_rows: list[dict] | None = None):
        """`record_path`: append every pushed event there. `recording_path`: the file the page may scrub
        (the record file while live, the replayed file under --replay); while live, only the rows this process
        appends count -- an earlier spectator's rows in the same file carry seq numbers that restart, so the
        recording starts at the file's size as of now. `recording_rows`: the recording held as events in place of
        a file (a game file replayed: open_replay()). `mode`: "live" or "replay", told to the page in state()."""
        self.ring: list[dict] = []
        self.ring_max = ring
        self.seq = 0
        self.cond = threading.Condition()
        self.record_path = record_path
        self.recording_path = recording_path
        self.recording_rows = recording_rows
        self.recording_offset = 0
        if recording_path and mode == "live":
            try:
                self.recording_offset = os.path.getsize(recording_path)
            except OSError:
                self.recording_offset = 0
        self.mode = mode
        self.hello: dict | None = None
        self.snapshot: dict | None = None
        self.notebooks: dict[int, dict] = {}
        self.usage: dict | None = None
        self.calls: list[dict] = []
        self.events: list[dict] = []

    def push(self, type_: str, data: dict, t: float | None = None, seq: int | None = None) -> dict:
        """Append one event. `seq` (a replayed recording's own number) is kept when it moves the sequence
        forward; anything else gets the next number, so the sequence never repeats or goes back."""
        with self.cond:
            self.seq = seq if isinstance(seq, int) and seq > self.seq else self.seq + 1
            ev = {"seq": self.seq, "t": round(t if t is not None else time.time(), 3), "type": type_, "data": data}
            self.ring.append(ev)
            if len(self.ring) > self.ring_max:
                del self.ring[: len(self.ring) - self.ring_max]
            self._remember(ev)
            self.cond.notify_all()
        if self.record_path:
            try:
                with open(self.record_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(ev, separators=(",", ":"), ensure_ascii=False) + "\n")
            except OSError:
                pass
        return ev

    def _remember(self, ev: dict) -> None:
        t, d = ev["type"], ev["data"]
        if t == "hello":
            self.hello = d
        elif t == "snapshot":
            self.snapshot = d
        elif t == "notebook" and isinstance(d.get("seat"), int):
            self.notebooks[d["seat"]] = d
        elif t == "usage":
            self.usage = d
        elif t == "call":
            self.calls.append(ev)
            del self.calls[:-RECENT_CALLS]
        elif t == "event":
            self.events.append(ev)
            del self.events[:-RECENT_EVENTS]

    def since(self, seq: int) -> list[dict]:
        with self.cond:
            return [e for e in self.ring if e["seq"] > seq]

    def wait(self, seq: int, timeout: float) -> list[dict]:
        """Events after `seq`, waiting up to `timeout` for the first one."""
        with self.cond:
            self.cond.wait_for(lambda: self.seq > seq, timeout=timeout)
            return [e for e in self.ring if e["seq"] > seq]

    def state(self) -> dict:
        with self.cond:
            return {"seq": self.seq, "mode": self.mode, "recording": self.has_recording,
                    "hello": self.hello, "snapshot": self.snapshot,
                    "notebooks": dict(self.notebooks), "usage": self.usage,
                    "calls": list(self.calls), "events": list(self.events)}

    @property
    def has_recording(self) -> bool:
        return bool(self.recording_path) or self.recording_rows is not None

    def recording(self, since: int = 0) -> Iterator[dict]:
        """The scrubbable recording's rows after `since`, numbered as the stream numbers them (nothing when the
        feed has no recording or the file is not there yet)."""
        if self.recording_rows is not None:
            yield from (ev for ev in self.recording_rows if ev["seq"] > since)
            return
        if not self.recording_path:
            return
        try:
            rows = read_recording(self.recording_path, self.recording_offset)
            for ev in rows:
                if ev["seq"] > since:
                    yield ev
        except OSError:
            return


PACKED_GAME, PACKED_CALLS = "game.jsonl", "calls.jsonl"


def json_lines(data: Iterable[bytes]) -> Iterator[dict]:
    for line in data:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            yield row


def open_replay(path: str) -> tuple[list[dict] | None, str | None]:
    """What `--replay PATH` plays: `(events, game file)` for a game file or a packed recording that holds one, the
    events being the page's stream made of its lines (game_file.events_of: the map, a snapshot a line, and a
    packed recording's calls between them) and the game file the path `/game` reads; `(None, None)` for a file
    `--record` wrote, which replays as it is. A packed recording keeps its game file inside a zip, so it is copied
    out to a temporary file. One with no game file is refused with that said."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if PACKED_GAME not in names:
                raise ValueError(f"{path} holds no {PACKED_GAME}: its run wrote no game file, so there is no map and "
                                 f"no world to draw (its calls are {PACKED_CALLS} inside it)")
            game = z.read(PACKED_GAME)
            calls = z.read(PACKED_CALLS) if PACKED_CALLS in names else b""
        name = os.path.basename(path).removesuffix(".zip")
        with tempfile.NamedTemporaryFile(prefix=f"{name}-", suffix=".jsonl", delete=False) as out:
            out.write(game)
        return game_file.events_of(json_lines(game.splitlines()), json_lines(calls.splitlines())), out.name
    with open(path, "rb") as f:
        try:
            first = json.loads(f.readline())
        except ValueError:
            first = None
    if not (isinstance(first, dict) and first.get("kind") == "game"):
        return None, None
    return game_file.events_of(row for _offset, _raw, row in game_file.read(path)), path


def read_recording(path: str, offset: int = 0) -> Iterator[dict]:
    """The events of a recording file from byte `offset`, each with a seq that only ever grows: a row's own seq is
    kept while it moves forward, otherwise the row takes the next number (two spectators appending to one file
    restart at 1; a page dedupes the SSE tail by seq, so the numbers must agree with what replay() pushes).
    Lines that are not an event (half-written, not JSON, no type) are skipped."""
    last = 0
    with open(path, encoding="utf-8") as f:
        if offset:
            f.seek(offset)
        for line in f:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if not isinstance(ev, dict) or "type" not in ev:
                continue
            s = ev.get("seq")
            last = s if isinstance(s, int) and s > last else last + 1
            ev["seq"] = last
            yield ev


# ------------------------------------------------------------------ live

class Live:
    """Poll every source into a feed. `client` is a raw harness.client.Civ5 (query only)."""

    def __init__(self, feed: Feed, client: Any, ledger_path: str | None, notes_dir: str | None = None,
                 ledger_every: float = 0.5, events_every: float = 2.0, snapshot_every: float = 8.0,
                 snapshot_idle_every: float = 40.0, notes_every: float = 2.0, settle: float = 0.6,
                 sleep: Callable[[float], None] = time.sleep, usage: Any = None, usage_every: float = 5.0,
                 recorder: Any = None, turns_every: float = 1.0):
        """`usage`: a usage_watch.UsageWatch (the operator's `--usage` paths), or None for a page without
        token counts."""
        self.feed, self.client = feed, client
        self.tail = ledger_tail.LedgerTail(ledger_path) if ledger_path else None
        self.notes = notebook_watch.NotebookWatch(notes_dir)
        self.usage, self.usage_every = usage, usage_every
        self.ledger_every, self.events_every = ledger_every, events_every
        self.snapshot_every, self.snapshot_idle_every = snapshot_every, snapshot_idle_every
        self.notes_every, self.settle = notes_every, settle
        self.sleep = sleep
        self.event_seq = 0
        self.snapshot_due = 0.0          # a write-kind call asks for a snapshot `settle` seconds later
        # `recorder`: a game_file.Recorder (the operator's `--games`), or None: the game being watched is then
        # written turn by turn into its own file, whatever the page shows
        self.recorder, self.turns_every = recorder, turns_every
        self.turns_error: str | None = None
        self.last = {"events": 0.0, "snapshot": 0.0, "notes": 0.0, "usage": 0.0, "turns": 0.0}
        # The snapshot is the one poll that costs the game a plot loop, so it runs at `snapshot_every` only while
        # something moves -- a write or wait call landed, a runtime event fired, or the last read differed from the
        # one before -- and at `snapshot_idle_every` otherwise (a seat reading screens, a game sitting at a boundary).
        # An unchanged read is never pushed: the stream and the recording carry a snapshot only when the world did.
        self.last_snapshot: dict | None = None
        self.stirred = True              # activity since the last snapshot read
        self.stop = threading.Event()
        self.map_key: str | None = None

    # each source is one guarded step so a tunerd blip never takes the others down
    def step_hello(self) -> bool:
        """The map into the feed: once when the poller starts, and again from step_snapshot() when a snapshot's
        `map_key` is not the dumped map's `key` (another game loaded under a running spectator)."""
        try:
            m = mapdump.read(self.client)
        except Exception as e:
            self.feed.push("status", {"source": "map", "err": str(e)[:200]})
            return False
        if not mapdump.valid(m):
            self.feed.push("status", {"source": "map", "err": f"unexpected map reply {str(m)[:120]}"})
            return False
        self.map_key = m.get("key") if isinstance(m.get("key"), str) else None
        self.feed.push("hello", {"map": m})
        return True

    def step_ledger(self, now: float) -> None:
        if not self.tail:
            return
        for row in self.tail.poll():
            self.feed.push("call", row, t=row.get("t") if isinstance(row.get("t"), (int, float)) else None)
            if row.get("kind") in ("write", "wait"):
                self.snapshot_due = now + self.settle
                self.stirred = True

    def step_events(self) -> None:
        try:
            evs, seq = events_mod.read(self.client, self.event_seq)
        except Exception as e:
            self.feed.push("status", {"source": "events", "err": str(e)[:200]})
            return
        if seq < self.event_seq:            # the ring was reset: start over
            self.event_seq = 0
            return
        for e in evs:
            self.feed.push("event", e)
            self.stirred = True
        self.event_seq = seq

    def step_snapshot(self) -> bool:
        """One snapshot read; pushed only when it differs from the last one pushed. True when it did."""
        try:
            s = snapshot.read(self.client)
        except Exception as e:
            self.feed.push("status", {"source": "snapshot", "err": str(e)[:200]})
            return False
        if not snapshot.valid(s) or s == self.last_snapshot:
            return False
        key = s.get("map_key")
        if isinstance(key, str) and self.map_key and key != self.map_key:
            # another game under a running spectator (load_save, a new hotseat): the page's terrain is stale until a
            # new hello, which goes out ahead of this snapshot (a dump that fails leaves the snapshot for the next read)
            self.feed.push("status", {"source": "map", "err": f"map changed ({self.map_key} -> {key}): dumped again"})
            if not self.step_hello():
                return False
        self.last_snapshot = s
        self.feed.push("snapshot", s)
        return True

    def snapshot_interval(self) -> float:
        return self.snapshot_every if self.stirred else self.snapshot_idle_every

    def step_notes(self) -> None:
        for rec in self.notes.poll():
            self.feed.push("notebook", rec)

    def step_usage(self) -> None:
        """Tokens per seat, when the clients' usage files or the ledger moved (usage_watch.py)."""
        if not self.usage:
            return
        try:
            data = self.usage.poll()
        except Exception as e:
            self.feed.push("status", {"source": "usage", "err": str(e)[:200]})
            return
        if data is not None:
            self.feed.push("usage", data)

    def step_turns(self) -> None:
        """One look of the game file's recorder (game_file.py): the turns the game took since the last look go
        into the game's file. No game loaded is no news; anything else is said once on the page's status line."""
        if not self.recorder:
            return
        try:
            self.recorder.step()
            self.turns_error = None
        except game_file.NoGame:
            pass
        except Exception as e:
            err = f"{type(e).__name__}: {e}"[:200]
            if err != self.turns_error:
                self.feed.push("status", {"source": "game file", "err": err})
            self.turns_error = err

    def tick(self, now: float) -> None:
        self.step_ledger(now)
        if now - self.last["turns"] >= self.turns_every:
            self.step_turns()
            self.last["turns"] = now
        if now - self.last["usage"] >= self.usage_every:
            self.step_usage()
            self.last["usage"] = now
        if now - self.last["events"] >= self.events_every:
            self.step_events()
            self.last["events"] = now
        if self.snapshot_due and now < self.snapshot_due:
            pass                                      # a write is settling: read then, not on the cadence
        elif self.snapshot_due or now - self.last["snapshot"] >= self.snapshot_interval():
            self.snapshot_due = 0.0
            self.stirred = self.step_snapshot()       # a world that moved keeps the fast cadence; a still one idles
            self.last["snapshot"] = now
        if now - self.last["notes"] >= self.notes_every:
            self.step_notes()
            self.last["notes"] = now

    def run(self) -> None:
        while not self.stop.is_set() and not self.step_hello():
            self.sleep(5.0)
        while not self.stop.is_set():
            self.tick(time.time())
            self.sleep(self.ledger_every)


# ------------------------------------------------------------------ replay

def replay(path: str | Iterable[dict], feed: Feed, speed: float = 1.0, sleep: Callable[[float], None] = time.sleep,
           stop: threading.Event | None = None) -> int:
    """Re-push a recorded stream with its original spacing divided by `speed` (0 = as fast as possible), under
    the seq numbers read_recording() gives the rows (the same ones `/recording` serves). `path`: the file, or the
    events themselves (a game file's: open_replay()). Returns how many events were pushed."""
    n = 0
    prev: float | None = None
    for ev in (read_recording(path) if isinstance(path, str) else path):
        if stop is not None and stop.is_set():
            break
        t = ev.get("t")
        if speed > 0 and prev is not None and isinstance(t, (int, float)):
            gap = (t - prev) / speed
            if gap > 0:
                sleep(min(gap, 30.0 / speed))
        if isinstance(t, (int, float)):
            prev = t
        feed.push(ev["type"], ev.get("data") or {}, t=t if isinstance(t, (int, float)) else None, seq=ev["seq"])
        n += 1
    return n
