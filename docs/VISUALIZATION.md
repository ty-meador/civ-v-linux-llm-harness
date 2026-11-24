# Live visualization: watching the seats think

A read-only web page that shows a running game and, over it, *where each model's attention was this turn*.
Nothing in it can act on the game, and nothing it produces is ever returned to a seat
(`feedback_no_other_seat_metadata`: a spectator may see everything; a seat must never learn about another
seat's activity beyond what the game UI shows).

## The picture

- **The whole map is known from the start.** Terrain, hills/mountains, rivers, features and resources are fixed
  at game start (features change rarely), so the spectator dumps every plot once when it attaches
  (`harness/spectator/mapdump.py`) and draws the full hex map in **black and white**.
- **Attention is colour.** When a tool call hands a model data about a plot -- `tactical_view` returns the disk
  around a unit, `city_screen` lists the worked plots, `revealed_map` scans the known world -- those plots
  **pulse once in the seat's hue and fade back to greyscale**. Broad scans (`revealed_map`, `known_world`,
  `units`, `cities`) pulse dimly; targeted reads (`tactical_view`, `map_window`, `city_screen`,
  `unit_mission_targets`, `explore_frontier`, `compare`) pulse at full brightness.
- **Actions stay coloured** until the turn ends: `move_unit` paints its destination, `give_order` its path,
  `buy_city_plot` the plot, `set_production` the city. Intent is drawn as an outline/arrow, perception as a fill,
  so "it saw this" and "it decided this" never look alike.
- **Reset is a hard cut** at the seat's `finish_turn`. In the observer view the *previous* seat's footprint stays
  at low opacity through the other seat's turn and is cleared when its own turn begins, so where the two minds
  overlap is visible. A **heatmap toggle** accumulates every touch over the whole game and never resets.
- **Narrative floats over the tile** for a few seconds and fades: the tool and its terse arguments
  (`tactical_view Archer 1433615`), and any `remember` / `assign` text or `give_order.purpose` anchored to a
  unit or city standing there. Assignments show a role glyph on their unit/city the same way.
- **Two views, one page.** *Observer*: the spectator's unfogged world, every seat's attention overlaid in its
  hue. *Seat N*: the world as that seat's screen shows it -- the seat's own fog from the snapshot (never-seen
  plots near-black, fogged plots dimmed), its team's units and cities always, other cities and borders on
  revealed plots, other units only where it sees now -- with only that seat's attention in colour, and its
  ticker is what its own `finish_turn` digests said. Cutting between them is choosing which source drives the
  map layers.
- **Replay, and a scrubber.** The spectator records its merged stream to a JSONL file, and the page holds the
  whole recording on its own clock: a bar under the map with play/pause, a speed (0.5x to 64x), a slider whose
  ticks are the turn boundaries (in the hue of the seat whose turn begins, grey for an AI round; click one to
  jump there), and the turn and elapsed time where the clock stands. Dragging backwards rebuilds the world from
  the recording's first row -- every call in order, but of the hello, snapshot and notebook rows only the latest
  before each call and before the target, a snapshot being the whole world (holds, ghost and heat come out as they
  were; the last seconds pulse). Live with
  `--record`, the same bar scrubs through everything this spectator has recorded and a **live** button (or End)
  rejoins the tail, where new rows apply as they arrive. Space, ← → (a turn boundary), Home and End work from
  the keyboard. Recorded silence longer than 20 s is skipped while playing. This is also how the page is
  developed with no game running.

## Feeds (nothing new game-side)

| Feed | Source | Trips |
|---|---|---|
| Tool calls, with their attention | the call ledger (`CIV5_CALL_LOG`, `harness/call_ledger.py`), tailed | 0 |
| Runtime events (combat, captures, leader messages, turn start/end...) | `H.events` read **unfiltered** by the spectator via `Game.q` -- the seat servers keep using the audience-filtered `H.events_since` | 1 per poll |
| Terrain | one dump at attach | 1 |
| Dynamic state (players, cities, units, borders, each human seat's fog, active player) | a snapshot poll: after every write- or wait-kind ledger row (once it settles), every 8 s while the world moves (a write or wait landed, a runtime event fired, the last read differed), every 40 s while it is still; an unchanged read is not pushed | 1 per read |
| Notes, assignments, orders | the notebook files on disk (`harness/notes.py`, `<game_key>-seat<N>.json`), watched by mtime | 0 |
| Tokens per seat (only with `--usage`) | the clients' own usage records joined to the ledger by the report's code (`harness/usage/report.py`), read again when a file or the ledger changed | 0 |

**Tokens.** With `--usage <file or dir>` (repeatable; the paths `scripts/ledger_report.py --usage` takes) the side
panel gains a Tokens section: per seat the model requests, tokens read, the share of them read from the cache,
tokens written and a list-price estimate, once for the seat's latest turn and once for the game (hover a figure
for its parts). The numbers are the report's for the same files at that moment; the "game" row is its
`usage seat N` line. "This game" is whatever the paths hold, so point them at the files of the game being
watched. A seat-loop cycle that is still running is counted per request only for Grok (its stream carries the
requests) unless the client's own directory is among the paths (`--usage logs/night --usage ~/.codex/sessions`);
otherwise a Codex or Claude cycle arrives whole when it ends. A seat view shows that seat's counts alone. This
is the operator's view: no seat reads the page (`docs/TOKEN_ACCOUNTING.md`, rule 1), and the event carries counts
and labels only. The counts are in the recording, so a replay needs no usage file; a recording made without
`--usage` has no Tokens section.

The spectator is one more tunerd client; the game accepts one tuner connection and tunerd already multiplexes
the seat servers, so its reads queue with theirs. Every read is a query; it never sends a command.

### What the ledger row gained

`call_ledger.row()` now takes the call's arguments and adds (all computed from the reply already in hand, so
logging still costs no trips; `harness/attention.py`):

- `tool`, `action`, `called` (stage 2d, GitLab #51): the call in the nine-tool vocabulary -- `tool` one of the
  nine, `action` the label (`league`, `unit/tactical`, `city/produce`, `finish`, an answer's choice; none for
  `question` and `batch`), `called` the old name or alias the client used when it was not the tool's own
  (`harness/surface/classes.py`). A row written before this stage carries the old name as `tool` and no
  `action`; the page prints `tool · action` when there is one and the bare tool otherwise (`callLabel`).
- `args`: the arguments as the client sent them, as compact JSON, cut at `ARGS_CHARS`. The fields below are
  read off the *old handler's* arguments the call resolves to (`dispatch.old_call`), so a unit's id and a plot
  are found under their old names whichever name the client used.
- `excerpt`: the first `EXCERPT_CHARS` of a write's reply, or of a refusal (reads are large and say nothing new).
- `scope`: `broad` / `focus` / `act` -- how bright the pulse is. `focus` is a read of one object or spot
  (`attention.FOCUS`, by `(tool, action)` key: a unit's tactical view, targets, actions and home, a map window
  or frontier, a city's screen, production and strikes, a comparison).
- `seen`: plots the reply described, as `[x, y]` pairs, cut at `SEEN_MAX` with `seen_more` counting the rest.
  Generic: every object with integer `x` and `y`. `revealed_map`: every non-blank character of the `vis` grid
  (or the first grid present) placed by `window`. `tactical_view` / `map_window`: the hex disk of `radius`
  around the unit / the given plot (the disk is not wrapped; the page wraps x modulo the map width).
- `intent`: plots the *arguments* pointed at (`x`/`y`, `dest_x`/`dest_y`, `give_order` steps, `compare` plots).
- `refs`: `unit_id` / `city_id` / `unit_ids` / `city_ids` from the arguments, for the spectator to resolve to a
  position from its own snapshot.

`scripts/ledger_report.py` groups by `kind` and lists the reads of a turn as `tool · action` labels.

## Code layout

```
harness/hexgrid.py            odd-r offset hex maths (distance, disk, wrap) shared by attention and tests
harness/attention.py          seen / intent / refs / scope from one call's args and reply
harness/call_ledger.py        the row, now with args + attention
harness/spectator/
  mapdump.py                  Lua + parser: the static map as character grids with legends
  snapshot.py                 Lua + parser: players, cities, units, borders, per-seat fog, active player, turn
  events.py                   unfiltered H.events reader
  ledger_tail.py              JSONL tailer (handles truncation)
  notebook_watch.py           notes / assignments / orders per seat from the notes dir
  usage_watch.py              tokens per seat from the clients' usage records, by the report's own steps (--usage)
  game_file.py                a game as one file, a JSON line a turn: the handler put into the game, the one
                              writer, the readers (a line by its number, the page's stream out of a file)
  feed.py                     merges the sources into one sequenced stream; records; replays (a stream, a game file)
  server.py                   SSE (/events), bootstrap (/state), the recording (/recording), the game file
                              (/game, /game/line), static files (/)
  __main__.py                 `python -m harness.spectator` (live, --record, --games, --replay)
web/viz/
  index.html
  css/viz.css
  js/hex.js                   geometry (mirrors hexgrid.py)
  js/palette.js               greyscale terrain, seat hues, glyphs
  js/feed.js                  /state, /recording and the SSE stream
  js/timeline.js              the recording as the page holds it (deduped by seq) and the player: cursor, clock,
                              speed, seek forward / rebuild backward, follow the live tail (no DOM: tested under node; seen in Chrome 2026-10-08)
  js/scrub.js                 the scrubber bar: controls, slider, turn ticks, keyboard
  js/world.js                 map + snapshot + notebook state
  js/attention.js             per-seat pulse / hold / ghost / heat state machine
  js/map_canvas.js            the hex map on a 2D canvas: two cached bitmaps (terrain; fog + borders) over the visible
                              window, a live pass each redraw, d3.zoom for pan and wheel, a hit test behind the hover
                              tip (docs/CANVAS_MIGRATION.md)
  js/panels.js                thinking column, ticker, seat switcher, the token counts
  js/app.js                   wiring
```

Stream event types: `hello` (map, players, seats), `snapshot`, `call` (a ledger row), `event` (a runtime
event, with its `audience`), `notebook` (one seat's notes/assignments/orders), `usage` (tokens per seat, the
whole count each time: a seek applies only the latest, like a snapshot), `turn` (active player / turn
changed). Every event carries `seq` and `t`; the page resumes an SSE with `Last-Event-ID`.

`GET /recording` (JSON lines, `?since=N`) is the recording so far under the seq numbers the stream carries:
under `--replay` the file's rows (a seq that restarts, two spectators having appended to one file, is
renumbered the same way `replay()` pushes it); live with `--record`, the rows this process appended. The page
loads it once, then dedupes the SSE tail against it by seq. A ledger row's `t` is the call's own time and can
precede the snapshot pushed before it, so the page's slider runs on a per-row time that never goes back.

## Running

```
CIV5_CALL_LOG=logs/calls.jsonl  <the seat servers, as usual>
python -m harness.spectator --ledger logs/calls.jsonl --record logs/spectate.jsonl   # live, http://127.0.0.1:8765
python -m harness.spectator --replay logs/spectate.jsonl                              # no game needed
python -m harness.spectator --ledger logs/calls.jsonl --usage logs/night --record logs/spectate.jsonl   # with tokens per seat
```

### A game as one file, turn by turn

```
python -m harness.spectator --ledger logs/calls.jsonl --games logs/games              # live, and each game into its own file
python -m harness.spectator --replay logs/games/game-40x24-e81c31c9d160.jsonl         # a game file, no game needed
python -m harness.spectator --replay logs/boards/<id>/recordings/<run>.recording.zip  # a benchmark run's packed recording
```

`--record` keeps what the page saw at the page's pace. `--games DIR` keeps the game itself: one JSON line for
every turn with the whole world as the turn begins, taken inside the game by a handler so that a turn played
between two polls is not passed over, in a file named by the game and gone on with when the game is loaded again
(`harness/spectator/game_file.py`; what a line holds is in docs/BENCHMARK.md, "The game file"). It is the
operator's file: fog ignored, no seat reads it, and writing it changes nothing in the game. A benchmark run writes
the same file for itself and its packed recording carries it.

`--replay` plays a game file, or a packed recording, as it plays a stream: the map from the file's first line,
then a snapshot for every line, and a packed recording's calls between them at their own times. The page needs no
code of its own for it and scrubs it turn by turn. `GET /game` lists the lines of the game file in hand (live
with `--games`, or the file being replayed) with each line's number, kind, turn, time and every major
civilization's few figures, enough for a chart over the game; `GET /game/line?n=N` is line N as written, found
with one seek. Seen in Chrome 2026-11-23 on a packed run of the duel.

A replay starts at the recording's first row and plays on the page's clock; `--speed N` additionally makes the
server pace the stream it pushes (the page's player does not need it).

## Developing without a game

`python3 scripts/spectator_demo.py logs/spectator_demo.jsonl` writes a synthetic recording (two seats, a small
wrapped map, every event type in the shapes the real feed produces); `python -m harness.spectator --replay
logs/spectator_demo.jsonl` plays it. Tests: `tests/test_attention.py` (the ledger fields),
`tests/test_spectator.py` (tail, notebooks, the usage watcher against the report, feed, poller cadence, SSE, the
recording route),
`tests/test_spectator_lua.py` (the two Lua queries under lupa), `tests/test_viz_js.py` (every page module parses
under node, and the timeline/player's seeks, silence skipping, tail following and dedupe; skipped without node).

The seat fog is the game's own (`Plot:IsVisible` / `IsRevealed` for the seat's team), read only into
`snapshot.fog` for the page; the map dump and the pieces stay unfogged. A unit the game hides from a seat on a
visible plot (a submarine it has not detected: `Unit:IsInvisible(team)`) carries that seat under `h` in its
snapshot row, and the seat view leaves it out; the observer still draws it.

Known simplifications: the page holds every parsed row of the recording (the 72 MB file from before the snapshot
cadence fix streams in line by line in about 3 s and 122 MB of heap, never as one string; a seek applies the
latest snapshot before each call and before the target, 18 of its 1,386); the map is dumped once per spectator
start, never reused from the record file (and again when a snapshot's `map_key` is not the dumped map's `key`:
another game loaded under a running spectator gets a new `hello`).

The map is a canvas (since 2026-10-09; it was SVG, one `<polygon>` per plot, through 1.13.0): one visible canvas
composed from two cached bitmaps and a live pass, only the plots in the viewport rendered, a hit test under the
pointer in place of `<title>`. [CANVAS_MIGRATION.md](CANVAS_MIGRATION.md) is the plan as it was carried out, with
the SVG baseline and the side-by-side numbers on synthetic maps up to 200x120 and on two real recordings; the SVG
renderer (`js/map.js`) and the `?renderer=` switch went with the switch-over and are in git history.
