"""The page's server: static files, a bootstrap state, the recording, and the feed over Server-Sent Events.
Read-only, stdlib only.

GET /            -> web/viz/index.html
GET /<path>      -> a file under the web dir (no `..`)
GET /state       -> feed.state(): mode, whether there is a recording, the map, the last snapshot, the notebooks,
                    tokens per seat (`usage`, null without --usage), recent calls and events
GET /recording   -> the recording so far as JSON lines (one event per line, the stream's seq numbers);
                    `?since=N` from seq N on; 404 when the spectator has none (live without --record)
GET /game        -> the game file in hand (game_file.py; live with --games, or a game file replayed): its name and
                    one row a line -- the line's number, kind, time, turn and each major civilization's few
                    figures -- for a chart over the game or a list of turns; 404 when there is none
GET /game/line   -> `?n=N`: line N of that file as written, one seek; 404 when there is no such line
GET /events      -> text/event-stream; `?since=N` or `Last-Event-ID: N` resumes; a comment line every KEEPALIVE
                    seconds keeps proxies and the browser happy
"""
from __future__ import annotations

import json
import mimetypes
import pathlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import game_file
from .feed import Feed

KEEPALIVE = 15.0
WEB_DIR = pathlib.Path(__file__).resolve().parents[2] / "web" / "viz"


def make_handler(feed: Feed, web_dir: pathlib.Path, game=None):
    """`game`: a call that says the path of the game file in hand, or None for none (it changes when another game
    is loaded under a live spectator)."""
    held: dict = {"path": None, "index": None}
    lock = threading.Lock()

    def index_of() -> game_file.Index | None:
        path = game() if game else None
        if not path:
            return None
        with lock:
            if held["path"] != path:
                held["path"], held["index"] = path, game_file.Index(path)
            else:
                held["index"].refresh()
            return held["index"]

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):  # quiet
            pass

        def handle(self):
            # A keep-alive client that resets between two requests (a tab closed, a test's response object collected)
            # makes handle_one_request's readline raise, and http.server only expects a timeout there: the socketserver
            # thread would print a forty-dash banner and a traceback on stderr for what is just a client gone.
            try:
                super().handle()
            except (ConnectionResetError, BrokenPipeError):
                pass

        def _json(self, obj, status: int = 200) -> None:
            body = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            self._body(body, "application/json; charset=utf-8", status)

        def _body(self, body: bytes, ctype: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/state":
                return self._json(feed.state())
            if url.path == "/recording":
                return self._recording(url)
            if url.path == "/events":
                return self._stream(url)
            if url.path in ("/game", "/game/line"):
                return self._game(url)
            return self._static(url.path)

        def _game(self, url) -> None:
            index = index_of()
            if index is None:
                self._json({"ok": False, "err": "no game file (start the spectator with --games, or --replay one)"}, 404)
                return
            if url.path == "/game":
                self._json({"ok": True, "file": index.path.name, "lines": index.rows})
                return
            try:
                n = int((parse_qs(url.query).get("n") or [""])[0])
            except ValueError:
                n = 0
            line = index.line(n)
            if line is None:
                self._json({"ok": False, "err": f"no line {n}; the file has {len(index.rows)}"}, 404)
                return
            self._body(line, "application/json; charset=utf-8")

        def _recording(self, url) -> None:
            if not feed.has_recording:
                self._json({"ok": False, "err": "no recording (start the spectator with --record or --replay)"}, 404)
                return
            try:
                since = int((parse_qs(url.query).get("since") or ["0"])[0])
            except ValueError:
                since = 0
            lines = [json.dumps(ev, separators=(",", ":"), ensure_ascii=False) for ev in feed.recording(since)]
            body = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
            self._body(body, "application/x-ndjson; charset=utf-8")

        def _stream(self, url) -> None:
            qs = parse_qs(url.query)
            since = self.headers.get("Last-Event-ID") or (qs.get("since") or ["0"])[0]
            try:
                seq = int(since)
            except ValueError:
                seq = 0
            if seq > feed.seq:      # a cursor from an earlier spectator process (live 2026-09-29): start over
                seq = 0
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            try:
                while True:
                    batch = feed.wait(seq, KEEPALIVE)
                    if not batch:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        continue
                    for ev in batch:
                        self.wfile.write(sse(ev))
                        seq = ev["seq"]
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                return

        def _static(self, path: str) -> None:
            rel = path.lstrip("/") or "index.html"
            target = (web_dir / rel).resolve()
            if web_dir.resolve() not in target.parents or not target.is_file():
                self._json({"ok": False, "err": "not found"}, 404)
                return
            ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                ctype += "; charset=utf-8"
            body = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def sse(ev: dict) -> bytes:
    data = json.dumps(ev, separators=(",", ":"), ensure_ascii=False)
    return f"id: {ev['seq']}\nevent: {ev['type']}\ndata: {data}\n\n".encode()


def serve(feed: Feed, host: str = "127.0.0.1", port: int = 8765, web_dir: pathlib.Path | None = None,
          background: bool = False, game=None) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), make_handler(feed, web_dir or WEB_DIR, game))
    httpd.daemon_threads = True
    if background:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
    else:
        httpd.serve_forever()
    return httpd
