# Resume here -- 2026-11-17 (morning): main = 2.17.0 + the benchmark's referee and rules version 1 (unreleased; runtime v341, 9 tools, 2345 tests).
**The work is the project's own benchmark, and the rules are ours to write** (the user, 2026-11-16). The user
went to bed with "run as many games as you need to"; 48 games have been played to their end.
`docs/BENCHMARK.md` now opens with **"Rules, version 1"**, which says what the night changed, and holds every
number. Plan on GitLab: tracking #210; #195 has the night's note, #194, #198 and #201 a line each.

**What the night found, in the order it matters.**
- **Every AI plays on `HANDICAP_AI_DEFAULT` at any difficulty**; a human seat handed to the engine keeps the
  human's Prince row (base happiness 9 against 15, research 100% against 85%) and lost every whole game. The
  setup screen cannot fix it (hosting the seat on that row gives a Chieftain game). `PreGame.SetHandicap(seat,
  AI_DEFAULT)` in the running game does, and **a save keeps it**.
- **Time**: `Game.SetVictoryValid(VICTORY_TIME, false)` alone still ends the game at turn 330; with
  `PreGame.SetMaxTurns(0)` as well games run on to a real victory. A save keeps that too.
- **So a board carries its terms**: `scripts/board_run.py --save <hosted> --terms <board>`. Made:
  `board-duel-prince-a-t0-airow`, `board-tiny-prince-a-t0-terms`. Every window on such a board, an entrant's
  too, and every continuation are on one row. `--row ai --time off` do the same at the hand-over for other
  saves; `--last-turn 500` stops a continuation as not decided.
- **The duel's own value by sixteen whole games: 0.73** (11 of 15 decided, standard error 0.11; the first
  eight alone said 0.57 with three conquests by the Aztecs before turn 180, the second eight 7 of 8 with
  none). With the chain's ten it is 20 of 25, 0.80: on the band's top edge.
- **Rule 8's first test failed on that board.** 30-turn opening window, two deals, five continuations each: the
  scripted loop 10 of 10, the stock AI 9 of 10. Not separated, and both outside the band. The scripted loop's
  fixed lists are a sound opening (Worker, Monument, Shrine, Granary, Tradition), not a floor.
- **The chain is not shown to differ from the whole game.** Twenty games from a turn-30 save had no conquest
  and the first eight whole games three (0.017 by chance); eight more whole games had none, and three in
  sixteen against none in twenty is 0.08. A read of both players is the same before a save and after the load
  (`logs/boards/scratch/e5_reload_diff.py`). Dropped as a lead unless it shows again; continuations record
  `first_war_turn` and `most_cities`.
- **The same save and the same continuation number are the same game to the last turn** (a second run replayed
  Diplomatic at 342 and Culture at 272). New games of a save need `--first-continuation M`; the duel terms
  board has used 0 to 15 from turn 0.
- Minutes: a duel continuation from turn 30 is 12 to 14, a whole duel game 3.5 to 17, a whole Tiny game to
  turn 330 24, a continuation from turn 325 2.2. Ten games give a standard error of 0.16 near 0.5.
- **Tiny through the chain: 0 of 4** (`board-tiny-prince-a-t0-terms`, Indonesia; at war by turn 93 every game,
  conquered in three, Brazil's Diplomatic victory in the fourth; a full game 27.5 minutes). **No board is in
  the band yet**: the duel is above it, this one very likely below.

**Next, in this order.**
1. **Find a board that is in the band through the chain** (stock AI plays the window, save, continuations).
   Host several (duel and Tiny, other civilizations and maps; `logs/boards/scratch/host_board.py`), make each
   carry its terms, screen each with `--turns 30 --continue 4 --last-turn 500`, keep the ones near the middle
   and measure them with more games. A middle-game board cut from an AI game is the other candidate
   (continuations are short there, so twenty are cheap).
2. **Repeat floor against anchor on that board.** Until one board separates them no model's value means
   anything (rule 8). A window in which sitting still has a price: 60 to 100 turns, or a middle game.
3. (Done: the eight whole games, "Eight more whole games" in `docs/BENCHMARK.md`. The two engine segments
   with no save between are not worth 90 minutes unless a gap shows again.)
4. #193's "Done when": 20 continuations on one run (the duel has 20 chain games over four runs; one run of 20
   is not played) and a Science win under autoplay (not seen; Diplomatic 22, Culture 5, Domination 3).
5. #194 the rest (hosting by one command from `logs/boards/scratch/host_board.py`, manifests, the fixed map
   seed), #198's live turn (the scripted loop past t246 on the Maya t242 board), #196, #197.

**The tool** is `scripts/board_run.py`; its docstring is the manual. New this night: `--terms`, `--row`,
`--time`, `--last-turn`, `{until}` in a command, and in `--summary` the decided games as one pool with the
standard error. `scripts/llm_seat_loop.py --until-turn N` tells the entrant the turn the window ends (#201);
`scripts/play_loop.py` makes a World Congress proposal (#198, unit tests only).

**The machine.** tunerd on the plain socket with no seat table, the session MCP server up; the game at the main menu unless
a run is still playing (`ps` for `board_run` and `screen_boards.sh`; the screening writes
`logs/boards/screen/screen.log` and one rows file a board). Saves in the game's `Saves/single`: the two terms boards, the hosted
`board-duel-prince-a-t0` and `board-tiny-prince-a-t0`, `board-tiny-chieftain-a-t0` (the failed hosting, can
go), the `--...-deal N-end` saves of each run, `scratch-e5-reload`. Rows (gitignored) under `logs/boards/`:
`duel-a/anchor-airow-notime.jsonl` (eight whole games), `duel-a/floor-t30.jsonl`, `duel-a/anchor-t30.jsonl`,
`tiny-a/anchor-t30.jsonl`, `tiny-a/full.jsonl`, `duel-a/whole-terms.jsonl` (whole games 8 to 15). The user allowed Codex and Grok runs on 2026-11-16; ask again
before new paid sessions.

**Mind.** No `scripts/check.sh` while a run plays on the live game. Long Lua goes through `Game().q(code)` and
returns a table. A killed run leaves the game in play: `board_run.leave(g)` then `wait_main_menu(g)` before
the next load. GitLab's spam filter refuses long bodies with game-of-chance words: short notes.
**The game process died about 45 loads into one process** (09:03, on its way back to the main menu). A run
keeps its finished continuations in `<rows>.partial` until the row is written. Relaunch with Steam up:
`setsid nohup scripts/launch_civ5.sh main > logs/launch_main.log 2>&1 < /dev/null &`, wait for tunerd's
"connected to game tuner", then `Game().c.exec('LegalScreen', 'UIManager:DequeuePopup(ContextPtr)',
check=False)` brings the main menu. Relaunch before a batch that would pass 40 loads. Two of sixteen whole
games took 27 and 32 minutes where the rest took 12.

# Previous -- 2026-11-17 (small hours): main = 2.17.0 + the benchmark's referee through stage 2's chain (unreleased; runtime v341, 9 tools, 2325 tests).
**The work is the project's own benchmark, and the rules are ours to write** (the user, 2026-11-16: "I'll leave
coming up with the most robust, useful benchmark rules to you"). `docs/BENCHMARK.md` opens with "Rules, version
0" and then holds every measurement of the two nights. **The plan is on GitLab: tracking #210**; milestones
2.18.0 the referee (#192 closed, #193 to #199), 2.19.0 the pilot (#200 to #204), 2.20.0 goal boards (#205 to
#208), unscheduled #209.

**The rules in six lines.** A run is worth the share of continuations the seat wins: the entrant plays a window
of turns, the game is saved, and the game's own AI plays every seat to the end R times. Boards are made at
Prince from the single-player setup screen and kept only if the stock AI's own value is 0.2 to 0.8. An
entrant's nth run is deal n, the same random stream for every entrant. A window not finished is a **DNF**, a
result of its own (the user's suggestion): no value, counted beside the value, below every finished run in an
ordering. Diagnostics (yields, score parts, diplomacy, cost) stand beside the value and never order anything.
Rule 8 lists the tests that could overturn all this, to be run before any model is spent on a value.

**The tool is `scripts/board_run.py`** (operator-side, plain tunerd, no seat table; its docstring is the manual):
- `--save S --turns N --runs K --out rows.jsonl`: the stock AI plays the window (`Game.SetAIAutoPlay`).
- `--label NAME --notebook none|FILE [--claim-wait 200] -- <command>`: any entrant as a command (a seat loop,
  `play_loop.py`); `{deal}` and `{turns}` in the command. The notebook on disk is put back afterwards.
- `--continue R`: save at the window's end, play the game out R times, `value` in the row. `--value-only`
  values a save as it is. `--summary rows.jsonl` prints each entrant and sets them side by side.
- Every row has `result`: `finished`, `dnf` or `void`. It refuses a board with no observer slot or two human
  seats, and leaves a game the engine is still playing by `Events.ExitToMainMenu()` itself.

**What the two nights found** (each with its numbers in `docs/BENCHMARK.md`):
- Autoplay needs an observer slot (status 4, what the setup screen leaves in unused slots); with the slots
  closed the call destroyed the seat, no error.
- An autoplayed seat has the difficulty's AI bonuses on the human's own handicap row; at Prince nearly none.
- A save replays the same game; draws from `Game.Rand` before play make deals differ.
- Maya t242 board (Huge, Emperor), 10 turns, ten AI runs: score 604 to 633.3, sd 0.7; technologies, policies and
  cities the same ten times. Grok finished the window (631; science 519 a turn against 628). Codex is a DNF: a
  leader came on screen after its tenth end of turn and it stopped, the board nine turns on. The scripted loop
  is a DNF three times (no hand for a World Congress proposal at t246, #198).
- A win does not stop the engine, a dead seat leaves the game playing by itself, and the seat's exit is refused
  while the engine plays ("this seat is not active"): the runner's first whole game played on to turn 400 with
  its row written (the user saw it). Fixed and seen live through the runner.
- **Stage 2's chain is seen live** on a Prince duel hosted to rule 2 (`board-duel-prince-a-t0`, Siam on the seat
  against the Aztecs): a 20-turn window (57 s), the save, two continuations to the end (11.3 and 9.8 minutes),
  back at the main menu each time. **The seat lost all three whole games on that board by Time** at the turn
  limit (330), 1571 to 1865 in the one from turn 0: the board's value is 0 of 3, outside the band, and the
  game's end was a comparison of score.

**Next, in this order.**
1. **#195 before anything else is built**: the duel says two rules may not hold. (a) *Do continuations end by a
   real victory anywhere?* Host Tiny and Small boards (4 and 6 civilizations) at Prince, play one whole game
   each with `--turns 400`, and read the victory type and the minutes. (b) *Is any board in the band?*
   `--value-only --continue 5` on each. If the seat keeps losing, try the seat at Warlord or Chieftain (the
   human's own row gets better, the AI columns worse) before changing the rule. (c) If Time stays the usual end,
   decide: Time off, a longer limit, or accept that the game's own rule counts score at the limit and say so
   in rule 1. (d) Floor against anchor on an opening window once a board is in the band.
2. **#193's "Done when"** still wants 20 continuations on one run and a Science, Culture or Diplomatic win seen
   under autoplay. At 10 to 15 minutes a game from an opening, twenty is three to five hours: run it overnight
   or cut R, and write down which.
3. **#194**: the board maker. The recipe is in `logs/boards/scratch/host_board.py` (gitignored, kept from the
   session's scratch): `start_single_player(handicap=..., start=False)`, the PreGame calls on the shown
   `GameSetupScreen`, `OnStart()`, `wait_ingame`, quick save, copy under a name. Never close a slot.
4. **#201's note**: `scripts/llm_seat_loop.py` must tell the entrant the turn at which the window is over
   ("the window is over when turn N is yours"), not "play N turns".
5. #196 diagnostics in the row (score parts, yields, diplomacy), #197 status after a dead seat, #198.

**The machine.** The game is at the main menu, tunerd on the plain socket with no seat table, the session MCP
server up. Saves made: `board-duel-prince-a-t0` and `board-duel-prince-a-t0--stock-ai-deal0-end` in the game's
`Saves/single`. Rows (gitignored): `logs/boards/maya-t242/t10.jsonl` (the AI's ten, Grok, Codex, the scripted
loop), `logs/boards/duel-a/full.jsonl` and `chain.jsonl`. The Maya game's notebook on disk is as it was. The
user allowed Codex and Grok runs on 2026-11-16; ask again before new paid sessions.

**Mind.** No `scripts/check.sh` while a run plays on the live game. Long Lua goes through `Game().q(code)` and
returns a table; `harness.cli lua` and `client.exec` print nothing for a long chunk. GitLab's spam filter
refuses long bodies with game-of-chance words: short description, the rest as a note
(`logs/boards/scratch/gitlab_plan.py`). The diregoblin fork's fix was already `461c3ee` (2.14.0); the chayuto
fork has no commit of its own.

# Previous -- 2026-11-16 (small hours): main = 2.17.0 (runtime v341, 9 tools, 2276 tests; tagged, released, on PyPI).
**2.17.0 is #189 with the two things found after it** (a ledger turn is a game turn; the counts in a narrow
window). **The one thing that was left is done: a seat-loop cycle under a live spectator with `--usage`.** One
Codex cycle of 2 turns (`gpt-6.1-sol`, effort low, 105 s) on the t242 board, the spectator on :8765 with
`--usage logs/stage6-live/codex-t2 --usage ~/.codex/sessions/2026/11/16` (the second path did not exist when the
spectator started; it was picked up when Codex made it), `/state` read every 5 s
(`logs/stage6-live/poll.jsonl`, gitignored): 2 requests ten seconds in, counted from Codex's rollout before the
loop's directory held any record, then one by one to 9, the turn row t242 (3 requests) then t243 (5). At the end
nothing doubled when the loop copied the rollout beside its stream: 9 requests, 332,953 read, 2,194 written,
est $0.15 on the page, as the recording's last `usage` event and in `ledger_report.py --usage` for either path
alone and for both. Before the cycle's first call reached the ledger the turn row read t251 with zeros (the
seat's latest turn in a ledger that holds the Grok bench run): five seconds, as designed, said in the CHANGELOG.
Claude's per-request read from its own directory is still the fixture test only; Grok's stream is its record.
The board was reloaded at t242 and the notebook put back (`cmp` with `logs/bench191/notebook-before.json`);
the spectator was stopped. **The registry has 2.17.0** (the user's `mcp-publisher publish`, 2026-11-16). **No issue is
open.** What is known and not built or not seen, none of it filed: the benchmark (`docs/BENCHMARK.md` is a
sketch not yet agreed; its "Not checked yet" list, a turn-0 board and a stock-AI anchor), the page holding every
parsed row of a recording, the shim and the launch scripts outside the wheel, the tests that take the live
per-socket lock (`test_assignments.py::test_the_four_tools`, two LeaderScreenGuard tests), LAN since 0.5.0.
**"Still open" at the end of this file was pruned 2026-11-16** and says the same at more length.

# Previous -- 2026-11-15 (late night): main = 2.16.0 + tokens per seat on the spectator page (unreleased; runtime v341, 9 tools, 2276 tests).
**#189 is done and closed: token accounting stage 6, the last stage.** `python -m harness.spectator --ledger
<ledger> --usage <paths>` shows per seat what its model read and wrote, for the seat's latest turn and for the
game (`harness/spectator/usage_watch.py`, the Tokens section of `web/viz/js/panels.js`). The watcher counts
nothing: it runs the report's `read`, `place`, `summary` when a usage file or the ledger changed and pushes the
whole count as one `usage` event, which the recording keeps. Checked live on the t242 board (read-only, no seat
played): page, `/state`, the replayed recording and `ledger_report.py --usage logs/bench191/433be54` all say 165
requests, 13,780,657 read, 30,900 written; scrubbed forward, back and to before the first count in a scratch
Chrome over the DevTools protocol. Two things came with it: the report prints a line per seat
(`summary()["seats"]`), and a finished cycle is no longer counted twice when the client's own directory is among
the paths. **Not done: no seat-loop cycle was run under a live spectator with `--usage`**; that a running Codex
or Claude cycle is counted per request from the client's directory is covered by a test on the fixture cycles
with their end row cut off, not by play. **No release cut**: the change is in CHANGELOG Unreleased, and it would
be 2.17.0 (README release row, the test count, AGENT_INSTALL line 8, PyPI, both forges' Release objects; the
registry was republished for 2.16.0 by the user). **The user, 2026-11-16: no release until what is left is
done.** After #189, the same night: **a ledger turn is a game turn** (`call_ledger.turn_groups`; a wait a
leader's screen stopped no longer ends the turn, a turn ended with one call is a turn, a call at another turn
with no wait in between starts one). The bench cycles are 10 groups for 10 turns (18 to 20 before), the
report's per-turn means and the page's "turn" row are whole turns, no total moved; CHANGELOG Unreleased has the
figures, and the limitation it removes is gone from `docs/LIMITATIONS.md`. **No issue is open.** The game is on the t242 board,
untouched; `logs/stage6-check/` (gitignored) holds the recording, the screenshot and the two small scripts of
the browser check. **2026-11-16, both changes seen in the user's Chrome through the extension** (520fd3e, the
board read-only, no seat played, no console message on any load): the live page's game row is the report's (165
requests, 13.8M read, 97% cached, 30.9k written) and its "turn t251" row is the report's whole t251 of the Grok
cycle (7 requests, 11,253 new + 1,021,952 cached, 2,264 written); the seat view keeps the section; the replayed
three-count recording scrubs by clicks on the bar to the end, to before the first count (section hidden) and
back into the middle. **A count that grows under an open page**: a spectator on a copy of the Grok cycle with
its stream cut to a third showed 10 requests, then 40, then 71 (the report's 7,145,562 read, 13,802 written) as
the rest was appended in two parts, with no reload; scrubbed back it showed the first count, and "live" brought
the last (`logs/stage6-check/chrome-2026-11-16/grow-live.jsonl`). That is a file growing, not a seat playing:
the turn row stood at zero until the end because the ledger copy was already whole, and Codex's and Claude's
per-request read from the client's own directory is still the fixture test only. **The narrow layout was broken
and is fixed** (`web/viz/css/viz.css`, the 900 px rule): stacked under the map, the Tokens section got a third
of a 209 px panel and showed its heading and the seat's line, the two rows of numbers behind a scrollbar. With
counts on the page the stacked panel is now a grid, the counts in a column on the left (340 px, half the width
at most) and the three lists on the right at the heights they had before the section existed; no counts, the
old stack. Seen at 800 x 523, 600 x 823 and 800 x 823 (no counts), the wide layout unchanged at 1300.
The first try's resize was undone by hand, not ignored by COSMIC: `resize_window` works on this desktop.

# Previous -- 2026-11-15 (night): main = 2.16.0 (runtime v341, 9 tools, 2260 tests; tagged, released, on PyPI).
**2.16.0 is #191, closed.** The last three cuts (league summary, the relationship on a leader's screen, the digest
without bookkeeping) were read back on Claude Code, Codex and Grok, one cycle of 10 turns each on the t242 board
(`logs/bench191/433be54/<agent>-t10/`; `docs/NOTES.md`, "The last three cuts, read back on three clients"): no
seat asked for `detail="full"`, none read a civ after a leader's screen for what it left out, none read `turn`
`status` for a marker. Per reply the cuts hold (league 31 to 42% smaller, a finish reply 12 to 32% under 2.15.0);
a session's total did not fall, because the seats made more requests. Grok answered t243's three complaints with
"Get over it" where it apologised the day before: one run, not settled. **The registry republish is the user's**
(`mcp-publisher publish`). **Open: #189 only** (the spectator shows tokens per seat). The stack was cold-started
this session (Steam, `launch_civ5.sh main`, tunerd on the plain socket, no seat table); the game is on the t242
board again, notebook as it was (`logs/bench191/notebook-before.json`). Every run on that board pays one refused
finish at t249 for the completed dig (#140's engine order, not new).

# Previous -- 2026-11-14 (night): main = 2.15.0 + #191's five cuts (unreleased; runtime v341, 9 tools, 2260 tests).
**#191 after this session, all Python:** the relationship on a leader's screen (`relationship_inline`,
`harness/game_parts/diplomacy.py`: no false flag, no zero counter, no `ok` / `player` / `leader`, `discuss` as a
list, no `text` on a history row that repeats `speech`; 38% smaller on the 27 leader screens of the v341 bench
runs) and the digest's events (`BOOKKEEPING_KINDS`, `_seat_row` in `harness/game_parts/events.py`: no
`turn_start` / `turn_end` / `active_player` / `unit_graphics_reset` row, a notification without `id` / `player` /
a `summary` its text opens with, a popup without its number; 15 to 22% of the events). CHANGELOG Unreleased,
PLAYBOOK "Leader screens", `docs/NOTES.md` last two sections. **Every item #191 named is built; none of the last
three (league summary, relationship, digest) is read back on a playing client.** One bench run per client on the
t242 board (the bench188 recipe; a friendship offer and a league session at t243) is the check: no seat asking for
`detail="full"`, no extra `state(what="civ")` after a leader's screen, no `turn` `status` read for a marker. Then
close #191 and cut a release. The game is on the t242 board, untouched this session; a Claude Code civ5 server
started before today's commits holds older Python, so restart the session before calling civ5 tools from it.

# Previous -- 2026-11-14 (evening): main = 2.15.0 + two cuts of the finish reply + the league summary (unreleased; runtime v341, 9 tools, 2244 tests).
**#191, the league read.** `state(what="league")` is `league_summary` by default (`harness/game_parts/diplomacy.py`,
Python only): 13.7 to 9.3 KB in a session, 29.5 to 17.5 KB between sessions on the bench runs' nine replies;
`detail="full"` is the old read, `detail="compact"` the summary less its prose, and `detail="summary"` no longer
means full. Live on the t242 board through `scripts/mcp_session.py` (read-only): 18.8 KB full, 10.5 KB default,
6.4 KB compact. CHANGELOG Unreleased, `docs/TOOL_REPLIES.md` "state(what="league")", `docs/NOTES.md` last section.
**Not read back on a playing client**: a bench run with a league read in it (the t242 board has a session at t243) is the check.
**#191 stays open** for the leader's `relationship` block on a deal screen (8% of a finish reply; Claude and Grok
answer from it without `question()`) and the digest's events (15%). The game is on the t242 board, untouched this
session; a Claude Code civ5 server started before bf8c125 still holds the v339 runtime, so restart the session
before calling civ5 tools from it.

# Previous -- 2026-11-14 (late afternoon): main = 2.15.0 + two cuts of the finish reply (unreleased; runtime v341, 9 tools, 2234 tests).
**#191, two cuts, both read back on three clients** (CHANGELOG Unreleased; `docs/NOTES.md`, "The finish reply after
two cuts"). v340: `todo.ongoing_note` once, the expiring-deal hint on the first row, digest rows without `audience`
/ `ntype` / `d1` / `d2`. v341: a finish or wait reply leaves out the status flags that are false
(`mcp_tools/turn.py` `_lean`, `QUIET_FLAGS`), quiet automated units are `todo.automated` {type: [ids]}, a refused
end's `todo` is the pointer "status.todo". The reply is 8 to 23% smaller in bytes; a session total did not move
beyond run-to-run variance. Runs: `logs/bench191/v340|v341/<agent>-t10/` (the runner is the bench188 recipe: reload,
notebook back, 200 s, one cycle of 10). **#191 stays open** for what is left: the leader's `relationship` block on
a deal screen (8% of a finish reply; Claude and Grok answer from it without `question()`), `state` `league` (a
reply that lists what changed), and the digest's events (15%). The game is on the t242 board again, notebook as it
was; this session's own Claude Code civ5 server still holds the v339 source, so restart the session before
calling civ5 tools from it (two runtimes re-inject each other).

# Previous -- 2026-11-14 (afternoon): main = 2.15.0 (runtime v339 unchanged, 9 tools, 2227 tests; tagged, released, on PyPI).
**2.15.0 is out: token accounting, operator-side** (#190 closed, milestone 23 closed). The words: a README bullet,
an honest limit and a documentation row; `docs/ARCHITECTURE.md` "Token accounting" (where the rows come from);
`docs/AGENT_INSTALL.md` section 11 (where each client keeps its usage, how to point the report at it);
`docs/LIMITATIONS.md` "Token counts and cost". No code changed since 71a4558. **The registry republish is the
user's** (`mcp-publisher publish`, after PyPI). **Next, both off the milestone:** #191 (trim the reply to `turn`
`finish`, 21 to 55% of what the replies add to a context) and #189 (the spectator shows tokens per seat). Still
open: the ledger report prints a turn with a leader's screen in its wait as several rows. Game state: the Maya
game on the t242 board, as below.

# Previous -- 2026-11-14 (small hours): main = 2.14.4 + token accounting stages 0 to 4 and stage 5's instrument (unreleased; runtime v339, 9 tools, 2227 tests).
**#188 is done (the small hours of 2026-11-14).** Six seat-loop runs on the Maya t242 board
(`Pacal_0242 maya-t242-before-185-check`), each client alone, 20 x 1 and 10 x 2 turns, no usage limit met: logs in
`logs/bench188/<agent>-t<turns>/` (streams, kept records, the seats' reports, the notebook after), tables in
`docs/measurements/2026-11-14-what-grows/`, the reading at the end of `docs/NOTES.md`. Ten turns a cycle beats twenty
(0.62 to 0.88 of the tokens, about 0.78 of the dollars); `turn` `finish` is the reply to trim first. The game is back
on the t242 board with the notebook as it was; what was in the quick slot before is
`single/QuickSave-before-188-bench-2026-11-14`. The seat folder `~/projects/grok-desk-seat` is kept (Grok trusts that
path). **Next: #190** words and release 2.15.0. Open from this stage: the ledger report still prints a turn with a
leader's screen in its wait as several rows.
**#187 is done: the report.** `scripts/ledger_report.py <ledger> --usage <file or dir> [--usage ...] [--prices f] [--json]`
adds `req`, `new in`, `cached`, `out`, `think`, `est $` per turn, the lines `fixed` / `unplaced` / `total`, and a
footer per client and model (`harness/usage/report.py`, `prices.py`, `prices.json` with seven models dated
2026-11-14). The night per request: `--usage logs/night --usage ~/.codex/sessions` (50 of 54 Codex cycles equal their
`turn.completed`, the other 4 were killed). `grok-4.7-build` has no public list price, so Grok prints tokens and no
dollars; add a row to `prices.json` when xAI lists it. **Next: #188** (stage 5, what grows: the user starts the
agents, each alone on the same seat from a copy of the same save), then #190 words and release 2.15.0.
What was written before stage 4:
**#185 and #186 are done too.** The seat loop stamps its stream, frames each cycle, keeps the client's per-request
record and runs `--agent claude`; `harness/usage/join.py` places every request in a game turn (`place`, `per_turn`,
`place_cycle`; `fixed` before a session's first call, `unplaced` when the ledger does not cover it), grouped by
`call_ledger.turn_groups`, which the ledger report now shares. The join found and fixed a race in the Codex reader
(a script's first calls are on file before its response's record). **Next: #187** (the report:
`scripts/ledger_report.py --usage`, `harness/usage/prices.json`), then the user starts the agents for #188.
What was written before stage 2:
**#183 and #184 are done** (milestone 2.15.0, `docs/TOKEN_ACCOUNTING.md`): `harness/usage/` (`rows`, `claude_code`,
`codex`, `grok`: one row per model request, each client's own total beside its reader), `scripts/cut_usage_fixture.py`
and four fixtures under `tests/fixtures/usage/` cut from real files down to numbers. Operator-side only; the server
imports none of it. Checked on this machine's files: Grok 502 cycles and Codex 50 cycles add up exactly; Claude Code
14 of 24 sessions, the rest short by requests that leave no `assistant` row (stage 4 must print that line).
**Next: #185** (the seat loop stamps an arrival time on every stream line, writes a cycle header, takes
`--agent claude` on the subscription), then #186 the join. After #185 the user starts the agents for #188: each of
Claude, Codex and Grok alone on the same seat from a copy of the same save, two boards (a turn-0 opening, the Maya
save at t242), one repeat (`docs/BENCHMARK.md`, the pilot). Also decided that night: goal boards (a save, a goal, a
turn limit, a constraint, a referee) are part of the benchmark sketch; the autoplay probe waits for the user's go.
Game state: as below (Maya game at t242).

# Previous -- 2026-11-13 (late night): main = 2.14.4 + two planning documents (no code change; runtime v339, 9 tools, 2141 tests).
**No bug or gap was open, so the next milestone is planned:** [2.15.0 Token accounting](https://gitlab.com/Tyler-Meador/civ-v-linux-mcp/-/milestones/23),
issues #183-#190, one per stage; the plan is `docs/TOKEN_ACCOUNTING.md` (ROADMAP has the pointer). The server never
sees token counts: the feature joins each client's own usage records (Claude Code transcripts, Codex rollouts, the
seat loop's Grok stream; shapes and traps read off this machine's files) to the call ledger, operator-side, and no
seat reads the result. **Start with #183 and #184** (fixtures cut down to numbers, then `harness/usage/` readers):
they need no game and no client. Decided the same night: the spectator stage (#189) comes after 2.15.0 and is off the milestone; `--agent claude`
runs on the subscription; Vox Populi is out of scope and the project writes its own benchmark (sketch and the
score-comparability proposal in `docs/BENCHMARK.md`, not yet agreed); the user starts other agents on request for
#188, after #185 has landed. `docs/CIVBENCH.md` holds first thoughts on
CivBench (arXiv 2604.07733): four ways to use the project there, what stands in the way, first steps, and three
questions for the user; nothing in it is decided. `glab` is not installed on this machine: the GitLab REST API with
`PRIVATE-TOKEN` from `.claude/.glpat` (python urllib) did the filing. Game state: as below (Maya game at t242).

# Previous -- 2026-11-13 (night): main = 2.14.4 (runtime v339 unchanged, 9 tools, 2141 tests; tagged, released, on PyPI).
**2.14.4:** the wheel carries docs/PLAYBOOK.md and docs/TOOL_REPLIES.md (symlinks under `harness/docs/`, built in as
files; never replace them with copies). 2.14.3 is in the official MCP Registry (the user published it); the user
republishes each new version with `mcp-publisher publish` after the PyPI upload.
**2.14.3, packaging only:** `server.json` for the official MCP Registry (valid per `mcp-publisher validate`; NOT
published: needs the package on PyPI first, then the user's `mcp-publisher login github` + `publish`), a
`civ-v-llm-harness` console script, `tests/test_server_json.py` (2140 tests). A release cut now bumps `server.json`
too (two version fields; the test fails otherwise). Wheel gap: docs/PLAYBOOK.md, TOOL_REPLIES.md, shim and scripts are
not in it.
**2.14.2 is docs only:** `ACCESSIBILITY.md` rewritten on the Accessibility Toolkit template (says the file is
voluntary, no conformance claim, no fixed resolution times, names the maintainer as owner). 2.14.1, an hour earlier:
**2.14.1 is the community files plus the three play-test fixes below.** New at the root: `CONTRIBUTING.md`,
`CODE_OF_CONDUCT.md` (Contributor Covenant 2.1, fetched from contributor-covenant.org; reports by confidential GitLab
issue), `SECURITY.md` (confidential GitLab issue; no e-mail address anywhere), `ACCESSIBILITY.md` (no conformance
claim). `.gitlab/issue_templates/{Bug,Proposal}.md` and `.gitlab/merge_request_templates/Default.md` are the working
templates; `.github/ISSUE_TEMPLATE/` (two templates + `config.yml` with contact links to GitLab) and
`.github/PULL_REQUEST_TEMPLATE.md` exist for GitHub's Community Standards checklist and send a visitor to GitLab.
Every guide opens with the same statement: it applies to the one official, write-enabled repository, which exists
only on GitLab; GitHub is a read-only mirror (issues and PRs off there; Discussions was still ON per the API that
night). The README carries a "Where the project lives" note under the install pointer. Game state: as below.

# Previous -- 2026-11-13 (late evening): main = 2.14.0 + three unreleased fixes (runtime v339 unchanged, 9 tools, 2134 tests).
**A play test of the Maya game, t237 -> t242, through `scripts/mcp_session.py --seat 0`** (the Claude Code session
server is still the v337 one: /mcp restarts it). Played: Portugal's and France's research agreements, India's and
Carthage's renewals, two co-op war requests declined, the special-session host vote (the Maya host since t239), a
caravan to Venice, three productions, and the barbarian Great War Infantry at Palenque shot down by the city, a
Gatling Gun and a Composite Bowman and finished by the Longswordsman (every preview within the roll of the result;
`reach` and its `next_turn` form read right on seven units). **Three gaps found, fixed, read back live, unreleased**
(CHANGELOG Unreleased; Python only): a deal on the table names `other` / `civ` / `leader` / `speech`; the tactical
view's `targets` rows carry a `call`; `state(what="unit", id)` without a view says a view is needed and no longer
asks for the id it was given. Seen and left alone: a hold ordered at 0 moves is a one-turn skip (the reply says so);
`trade_route`'s reply named another caravan's id (`matched: line_ambiguous`), the engine re-creates the unit.
**State left behind:** the Maya game on screen at t242, my turn, five units waiting for orders; the quick slot is
that state, copied to `single/Pacal_0242 maya-t242-playtest-2026-11-13`; note 1 of the notebook rewritten at t241.
Logs: `logs/play-2026-11-13/` (gitignored). `.gitignore` now covers `.*_pat` and `tmp*/` (the repo is public).
**No GitLab issue is open**; the three fixes ride in Unreleased until the next milestone.

# Previous -- 2026-11-13 (evening): main = 2.14.0 (runtime v339, 9 tools, 2129 tests; tagged and released on both forges).
**2.14.0 "Where a unit can go this turn" is out, all of it seen live.** (1) `reach` on the tactical view (v337): every
plot this turn's move can end on as `[x, y, moves left]`; read on the combat-lab save (t266) against 34 real move
orders, every one arriving with the moves listed, six orders to unlisted plots stopping short or refused.
(2) Found by that read-back: a neighbour's `cost` / `left` now follow the pathfinder's detour (`detour: true`, v339),
and two embarked units never share a water plot (refused up front, v338). (3) v336, cherry-picked from the GitHub
fork `diregoblin/civ-v-linux-mcp` (Pavel Zun): teammates enter each other's territory; seen live in a two-human
hotseat hosted with `host_hotseat(launch=False)`, `PreGame.SetTeam(1, 0)` in the StagingRoom, then `launch_game()`,
the plots given owners with `Plot:SetOwner`. Also looked at: `corytodd/civ5-mcp` -- a Windows mod writing one JSON
snapshot per turn to SQLite for a read-only advisor server; older than this project, shares no code with it, nothing
worth a refactor. The other fork, `chayuto`, has no commits of its own. **State left behind:** the game is at the
main menu (stack up: Steam, Civ5XP, tunerd on the plain daemon); `session(action="main_menu")` autosaved over the
single quick slot twice, so `single/quick/QuickSave` is now the combat-lab game at t266 with test moves made --
`load_latest` no longer opens what it did before; every named save is untouched. The session server of the Claude
Code client was started at v337 source: restart it (/mcp) before playing, or it re-installs v337 over v339.
**No GitLab issue is open.**

# Previous -- 2026-11-05 (evening): main = 2.13.1 + one unreleased fix (runtime v335, 9 tools, 2115 tests).
**The last two open issues, the trackers #167 (Codex, seat 0) and #173 (Grok, seat 1), are closed**: every fix of
milestones 2.11.0-2.13.0 was read back live on the three-seat save `GrokVCodexVClaude` (hotseat/, t27 -> t29),
one seat at a time through `scripts/mcp_session.py --seat N` (drivers and logs under `logs/readback-2026-11-05/`,
gitignored). Seen: #168 (per-seat identity in the key, only this game's notes on all three seats, the worker's
order paused `adopted`, identity / notes / pause identical across save -> main_menu -> load_latest), #174 + #172
(seat 0's DoF to seat 1 read on seat 1 and invisible to seat 2; seat 1's GPT offer read and refused on seat 2 with
the items; seat 0's DoF to seat 2 read nothing on seat 1, accepted on seat 2), #175 (IsDoF true both ways after
each accept), #176 (`hold` block; GetFortifyTurns 0 / 1 / 2 over t27-t29; a fortify at 0 moves is reported as a
one-turn skip), #180 (cost 1 / left 1 then cost 1 / left 0, the moves matched), #179 (locked ideologies as names),
#169 (seven real ruins gave no upgrade; the fourth ruin planted beside a spawned Scout did: the move reply named
Atlatlist 122892). **One gap found and fixed, unreleased:** a MISSION_SKIP retry on the vanished Scout's id answered a
bare "no such unit"; `unit_mission` now runs `_refusal_names_successor` as `move_unit` does (CHANGELOG Unreleased,
2115 tests). Not re-read live: #177, #178, #171, #181, #182. **The game on screen is that hotseat game at t29, seat
0's turn, with nine Lua-spawned Scouts / one Atlatlist** and seat 0's supply in deficit; the quick slot is that
state (copied to `hotseat/GrokVCodexVClaude_0029 readback-2026-11-05`), the named t27 save is untouched. The stack
is up (Steam, Civ5XP launched 20:37 by `scripts/launch_civ5.sh main`, tunerd on the plain daemon). Driver lessons:
a settle loop must handle research, policy, promotions, city production (PROCESS_WEALTH needs Currency: pick from
the production read) and a leader screen before `end`, or the next seat's `wait` blocks for its whole cap; a
`pkill -f` naming the script kills the shell that runs it. Next (the user's call, 2026-11-05): no 2.13.2; the fix rides in
Unreleased until the next milestone's release. The next play session files that milestone. **No GitLab issue is open.**

# Previous -- 2026-10-31 (night): main = 2.13.1 (runtime v335, 9 tools, 2114 tests; tagged 2026-10-31; 2.13.1 is the README correction patch, with v2.11.0 and v2.12.0 backfilled at 8b10ac9 / 6c7b76f).
**The thirteen issues of the 2026-10-30 three-seat hotseat (milestones 2.11.0, 2.12.0, 2.13.0) are fixed on main
and released**, each as one commit with a regression test and a GitLab note: #168 (9cc36ec, the notebook key ends in a
per-game identity, old-key notebooks adopted once and quarantined), #174 + #172 (50675bf, the shared hotseat scratch
trade table is read seat-aware), #175 (8b10ac9, a human seat is asked on the trade table: friendship as a DoF deal,
war through SendChangeWar, denounce refused), #181 + #182 (90edcba, orders.counts after the run; direct_command
never pauses the order it creates), #176 + #169 (6c7b76f, the `hold` block; the ruins successor named by the move),
#180 + #177 (e9241f9, step_cost.lua ports CvUnitMovement::MovementCost; a city is the cell's ground letter), #179 +
#178 + #171 (343af86, locked ideologies as names; belief rows carry their call; tests/test_playbook_examples.py checks
every served example). CHANGELOG's Unreleased holds the entries; the trackers #167 / #173 stay open as the record.
**Nothing of this was seen live** (no game ran tonight; the last live process was runtime v328). Next: a live
session on the three-seat hotseat save (or the t237 Maya save) to read back, in this order: `H.game_key_facts`
before and after a reload (GetStartingPlot stable; the live notebooks adopt once with orders paused); #172's deal
sequence (0->2 unseen on seat 1, then 0->1, 1->2, overlapping offers); a DoF deal read on both seats and IsDoF
after the accept; tactical `cost` against the moves an order actually spends (forest on hills, a river, a road, a
ZOC step); `GetFortifyTurns` right after MISSION_FORTIFY; a ruins step's successor at the read-back. The releases are cut: `v2.11.0`
and `v2.12.0` tagged after the fact on the commits that closed their milestones (8b10ac9, 6c7b76f), `v2.13.0` on the
bump commit; CHANGELOG split into the three entries, README row + bullets + test count, AGENT_INSTALL line 8, ROADMAP;
GitLab and GitHub Release objects for all three, the three milestones closed.

# Previous -- 2026-10-30 (evening): main = 2.10.0 (runtime v328, 9 tools, 2039 tests; tagged 2026-10-30).
**2.10.0 "Decisions explained, lean replies" is shipped**: the seven issues of milestone 19 in the planned order, each with
a regression test and a GitLab note (CHANGELOG 2.10.0). #142 and #148 were done this evening and seen live on the t237
Maya save (`Pacal_0237 maya-t237`, single/): a Great Musician spawned beside Palenque read `missing` rows for the Great
Work (music slots 2/2, "build one of: Opera House, Ceilidh Hall, Broadcast Tower") and the concert tour (nearest Venetian
plot (29,63), 5 away), its tour order was refused up front from home soil; a Warrior spawned on Almaty's plot carried the
COMMAND_GIFT row with owner Almaty and the complete gift_unit call; the map window on fogged Zurich (27,62) named the city;
culture_works tooltips read "+2 Culture, +2 Tourism"; Venice's trade catalog listed 2 peace rows and counted 13 + 11 "not
at war" ones; the Units row has no GreatWorkType column at runtime (the Great Work class comes from
Unit:GetGreatWorkSlotType, v328). **The game on screen is the t237 Maya save, unsaved, with three Lua-spawned test units**
(Writer 991264 at (34,62), Musician 999457 at (34,63), Warrior 1007645 at (40,52)); nothing was saved, the quick slot is
untouched. Steam, the game (launched 20:1x by `scripts/launch_civ5.sh main`) and tunerd (no seat table, `logs/tunerd.log`)
are up; the live process runs runtime v328. Next: the three tracking issues (#149, #150, #157) stay open as the record of
the 2026-10-29 sessions; a new play session (Codex / Grok hotseat or the Maya game) files the next milestone. Glama's TDQS
re-score of 2.8.0-2.10.0 is still to be read back (the nine descriptions did not change in 2.10.0).

# Previous -- 2026-10-30 (morning): main = 2.9.0 (runtime v322, 9 tools, 2001 tests; tagged 2026-10-30).
**2.9.0 "Reads and schemas tell the truth" is shipped**: the eight issues of milestone 18 in the planned order, each with
a regression test and a GitLab note (CHANGELOG 2.9.0), and the milestone's done-when seen live: #165 on the hotseat game
at t39 (the Worker's quarry: order reply, unit row and plot line all 4), #163 / #164 / #146's refusal shapes at t39,
#140 on the t237 Maya save (an Archaeologist spawned by Lua on the (41,55) site, `dig_sites`, the dig `started,
turns_left 4` on all three reads, `todo.dig_choice` at t240, question() with the note, answer(choice=2) naming the
Doubloon in Palenque's Museum; the drive refused an AI's Research Agreement and a coop-war ask, voted the Congress host
and set Wealth in two idle cities on the way), #156 on S3 combat-lab (Musketman 630799 killed the barbarian Warrior at
(49,18): `defender {hp 0, killed}`, damage 100 / 5). **The game on screen is the hotseat game at t39 again**, seat 0's
turn, research unset, reloaded from the new S12 `Pacal-Isabella_0039 t39-quarry-165-check` (hotseat/); the t237 Maya
save and S3 were not re-saved after the checks. The live process runs runtime v322 (installed by the scripts/mcp_session.py
servers of the checks); any `--seat auto` MCP server of an older Claude Code session must be restarted (/mcp reconnect)
before it is used on this game. Next: milestone 2.10.0 (GitLab 19), #142 first; its order is in the milestone description
and `docs/ROADMAP.md`. Glama's TDQS re-score of 2.8.0 / 2.9.0 is still to be read back (offline lint 0 warnings, the
notebook description 1979 characters).

# Previous -- 2026-10-30 (early morning): main = 2.8.0 (runtime v320, 9 tools, 1978 tests; tagged 2026-10-30).
**2.8.0 "Hotseat: nothing stalls or leaks" is shipped**: the nine issues of milestone 17 in the planned order, each with
a regression test and a GitLab note (CHANGELOG 2.8.0), and the milestone's done-when seen live: the Codex/Grok hotseat
game (Maya seat 0 / Spain seat 1) was on screen at t38 behind a stale, empty trade table; `leave` now cancels such a
table, seat 0 proposed a two-item deal, seat 1's question() read it as a screenless question and refused it, seat 1
proposed one back, seat 0 read and refused it at t39. **The game on screen is that hotseat game at t39, seat 0's turn,
research unset** (ENDTURN_BLOCKING_RESEARCH); the save before the check is S11 `Pacal-Isabella_0038 before-161-check`
(hotseat/). The live process runs runtime v320 (installed by the scripts/mcp_session.py servers of the check); three
`--seat auto` MCP servers of Claude Code sessions still hold v318 code -- restart them (/mcp reconnect) before they are
used on this game. Next: milestone 2.9.0 (GitLab 18), #156 first; its order is in the milestone description and
`docs/ROADMAP.md`. Glama's TDQS re-score of 2.8.0 is still to be read back (the listing changed by one clause of
`question`; offline lint 0 warnings).

# Previous -- 2026-10-30: main = 2.7.1 (runtime v318, 9 tools, 1963 tests). **Planned, not started:** the 24 issues
from the 2026-10-29 play sessions (#149 Maya t203-t237, #150 Grok hotseat seat 1, #157 Codex hotseat seat 0) sit in
three ordered milestones, 2.8.0 (17), 2.9.0 (18), 2.10.0 (19); the order is in each milestone's description and in
`docs/ROADMAP.md`. Start with 2.8.0's #161 (an incoming human deal cannot be read). #140-#148 were filed with empty
bodies (the filing script's inner heredoc swallowed the outer one); their text was restored from the session transcript.
#139 closed as shipped.

# Previous -- 2026-10-29 (late night): main = 2.7.1 (runtime v318, 9 tools, 1963 tests; tagged 2026-10-29). **2.7.1: the four descriptions Glama's TDQS panel marked under 4.5 are restructured** (GitLab #139: `turn` 3.6 -> 4.6, `notebook`, `answer`, `batch` 4.2-4.3 -> 4.6-4.8; hosted TDQS 4.7 A, every tool 4.6 or better, report https://tdqs.dev/reports/p0usqgjwik; Glama's own re-score of v2.7.1 is still to be read back from the admin panel and recorded on #139; the admin panel's marks on v2.7.0 are `docs/measurements/2026-10-29-glama-tdqs-admin-v2.7.0.md`). **2.7.0: `inspect` is `state`** (GitLab #138, the user's pick for a strict all-noun set after Glama's naming 4/5): same arguments and replies, `inspect` retired with `renamed` like the 145 old names; every doc, row and runtime string says `state`; a running client's server must be restarted (/mcp reconnect) to list it, and 2.7.0 was cut the same night (Releases on both forges) so Glama's scorer sees it. Milestones 2.2.0 (17 issues), 2.3.0 (21), 2.4.0 (12), 2.5.0 (8) and 2.6.0 (11) are closed, every issue fixed in the milestone's order with a regression test and a GitLab note (CHANGELOG 2.2.0-2.6.0). **The game on screen is the Maya t200 save** (`Pacal_0200 maya-t200`, reloaded 2026-10-29 for the 2.6.0 measurement). **That open point is solved (GitLab #137, 670d705, runtime v317, released as 2.6.1):** the End Turn stayed disabled because the reload followed a `session(action='main_menu')` with Dido's leader screen up (her friendship request comes during the AI turns after every t200 finish); the exe keeps the leader view open into the next game loaded and `UI.RequestLeaveLeader()` clears it. The exit now leaves a leader on screen first (`left_leader_view: true`) and `H.end_turn_send` clears a stale view itself (digest event `stale_leader_view_cleared`); both verified live on the t200 save, which is on screen at t200, turn start, nothing blocking, End Turn enabled. The stack is up (Steam, Civ5XP, tunerd on the plain daemon). The 2.6.0 before/after bytes are in CHANGELOG 2.6.0 (`state(what='city_state', view='full')` 8109 -> 5508 B). **After a release cut, restart the client's MCP server** (Claude Code: /mcp reconnect): a running server keeps its import-time listing; since 2.6.0 its status says `server_outdated` and names the seat's other servers (`other_clients`). The hand-started Random-map Maya game of the day is saved as `Pacal_0005 maya-random-t5`. GitHub Releases: v2.5.0 and v2.6.0 exist (created 2026-10-29; the mirror github.com/ty-meador/civ-v-linux-mcp carries a tag about a minute after a mirror sync, which the 5-minute throttle may delay). 2026-10-29 evening: Glama re-scored the 2.0.0 listing by itself (2026-10-28, A 4.4/5.0: completeness 5, naming 4, disambiguation 5, tool count 5), recorded on #59 and in CHANGELOG 2.0.0; #58, #59 and milestone 2.0.0 closed; the eight play-session trackers closed (every linked issue was already closed). **No GitLab issue is open.** 2.6.1 was cut the same evening with Releases on GitLab and the GitHub mirror (v0.3.0 and v0.5.0 backfilled too). Next: the next play session's findings. The Assyria notes below are the 2026-10-27 state, kept for the record.

This file holds the current state only. Earlier "Resume here" sections (58 of them, 2026-09-19 to 2026-10-11) live
in git: `git log -p -- docs/SESSION_HANDOFF.md`; the 2026-10-11 version carries this game's t0-t163 turn by turn.
Shipped work is in `CHANGELOG.md` (the 1.16.0 section holds t164-t208's fixes); known gaps are inventoried in
`docs/GAPS.md`.

## Where the game is

- **The save and the lost turn.** The newest file is the quick save written 2026-10-15 00:07 at **t238** (now also
  `single/Ashurbanipal_0238 international-games`); the engine's autosaves stop at t230. The notebook's briefing
  baseline says t239: the last session ended one turn past the save, and that turn's work is in no file. `load_latest`
  opens t238; the briefing then rightly says the baseline restarts.
- **t238, turn start, nothing blocks.** `gate` null, `decisions` empty, `todo.units` / `cities` empty, no threats in
  sight, no war. Eight units are `ongoing` (two automated Workers 475160 / 507929, six Caravans on routes). Events
  at the turn start: International Games PASSED (14 Yea from me, 9 Siam, 2 more), Ban Luxury: Crab FAILED (my 10
  Nay against Siam 7 + Portugal 5 Yea), two "Great Person born" notices, Sofia cancelled a quest, Antwerp seeks a
  Great Writer. **Look first:** the units list shows no new Great Person beyond Great Engineer 1130538 (t221) and
  Great General 1122345 (t220), so whoever was born at t238 was spent before the quick save or is not what the
  notice says -- `units` / `great_person_progress` settle it.
- **Empire (t238).** Assur (16,27) pop 25, Nineveh (20,28) 20, Nimrud (18,23) 16, Kar-Tukulti-Ninurta (12,26) 15;
  all Judaism, all garrisoned, all growing. Gold 2334 at +56, science 850, culture 275 a turn with 2691 stored
  (next policy 3575), faith 1065 at +94, happiness 68, 53 units, score 1607. Golden Age over (t235). Era: Future
  (Satellites t224).
- **Science victory.** Apollo Program done t223 in Assur; SS Cockpit bought (2160 g, t224) and added t225. Now:
  Assur builds the **SS Stasis Chamber** (8 turns; Nanotechnology is known), Nineveh and Nimrud finish **Spaceship
  Factories next turn** (Assur has one), K-T-N runs the Research process. The **SS Engine** needs Particle Physics
  (Atomic Theory researching, 5 turns, 408 stored; then Particle Physics); the **three SS Boosters** need Advanced
  Ballistics, not yet in `available_research` (Archaeology 1 turn and Lasers 7 are the other two offered). No rival
  has Apollo (`spaceship_status.rivals` empty). The habit that got here: faith-buy a Great Scientist whenever faith
  allows (2680 at t228) and bulb it; Hubble (t226) gave two; the Great Engineer rushed Hubble.
- **Policies.** Tradition and Patronage done, Rationalism finished t188 (free Flight), Freedom since t200: Avant
  Garde, Civil Society, New Deal (t195), Creative Expression / Space Procurements (t209-t213), Capitalism (t216),
  Volunteer Army (t221: six Foreign Legions), Treaty Organization (t225), Cultural Diplomacy (t230), Merchant
  Confederacy (t231). Universal Suffrage was refused at t208 by the level gate (runtime v283 names it).
- **Diplomacy** (note 2, t236, is the full picture). SIAM (Ramkhamhaeng, player 2) adopted Order t234 and
  **denounced me t235**, three turns after renewing the DoF: the largest army on the continent, borders Nimrud and
  Nineveh from the north, at war with Shaka since t229-t230; a war risk from now on. Deals running with Siam: the
  Research Agreement signed t220 (pays t245; I gave 268 g + 5 Coal + 3 Aluminum + 9 gpt), Marble for 5 gpt to t248,
  open borders to t249 (consider not renewing), and **Salt for 5 gpt ended this turn (reoffer t239)**. PORTUGAL
  (Maria, player 1): neutral-friendly, Salt for Truffles to t247 (Truffles is my only copy). ZULU (Shaka, player
  3): friendly, open borders to t250, **Fur + 4 Iron for Dye ended this turn (reoffer t239; Dye is my only copy;
  Nimrud's WLTKD ended t234 and it now wants Crab)**. Promised t201: no more conversions in Siam.
- **United Nations.** I host; 24 delegates (4 + 2 host + 18 from nine allies) against Siam 16, Portugal 8, Zulu 4.
  World Leader needs 42 and is **"Not allowed by this game's options"** (diplomatic victory is off in this game).
  Active: Sciences Funding, World Religion Buddhism, Cultural Heritage Sites (+3 culture per wonder), and now the
  **International Games project** (cost 1929; 482 production for tier 2, the top contributor gets +100% tourism for
  20 turns and a free policy; I have contributed 0 -- Nineveh and Nimrud are free after their factories). My
  proposal **International Space Station** (free Great Scientist, research boost, the ISS wonder) is pending;
  Siam says Yea (16); the session is in 6 turns (t244). World's Fair finished with me at tier 3 (644 of 938).
- **City-states.** Nine allies (2 delegates each); the t196 list was Mombasa, Yerevan, Malacca, La Venta,
  M'banza-Kongo, Ormus, Monaco, Sofia, with Belgrade added t216 and Colombo / Antwerp lost to Portugal at t231;
  `city_state_bonuses` is the live list. Siam buys city-states aggressively (Bratislava, Byblos, Zurich flip back
  and forth); Treaty Organization plus caravan routes to La Venta, Malacca, Sofia and Nobamba is the counter.
  Gifted units keep arriving (Paratroopers from Belgrade t231 and M'banza-Kongo t233, Rocket Artillery, an
  Infantry); the spare Knights 868385 / 892934 are `gift_unit` candidates.
- **Assignments and orders.** Two active garrison roles, both `on_track`: 4 (Nimrud; Swordsman 335873 -- which
  stands on (16,24), not in the city, see Still open) and 6 (Nineveh; French Musketeer 704517 in place). No open
  standing order: the last, 51 (Scout 98304 home to (14,26)), completed t229. Notes: 1 (t93 plan, stale), 2 (t236
  diplomacy, current), 3 (t196 plan, the strategy; its numbers are stale), 4 (t98 diplomacy, stale). A fresh plan
  note at t238 is the first thing to write.
- **Military.** 53 units: six Foreign Legions, four Infantry, two Paratroopers, two Rocket Artillery, an Artillery,
  four Hwacha, a Gatling Gun, an Anti-Aircraft Gun, and a long tail of obsolete units (Swordsmen, Pikemen,
  Crossbowmen, a Trebuchet, a Lancer, Knights, a Horseman, a Musketman, Ski Infantry); plus five Workers and six
  Caravans. Upgrades were never a priority; with Siam hostile they may become one (`upgrade_unit` carries the
  notebook over).

## Where the code is

- **main = 2.0.0, tagged 2026-10-26** (runtime v287, 9 tools, 1694 tests): "The tool surface" (milestone 11,
  #44-#58) -- nine tools where 145 were, every old name answering through the retirement map, every listing
  reply carrying the order to copy, the words and the runtime strings in the new vocabulary, fresh Claude Code
  and Codex sessions through the nine. README has the release row and the test count; ROADMAP the release
  paragraph and row 5; AGENT_INSTALL says 2.0.0; the CHANGELOG entry carries the 2026-10-04 Glama marks with
  the 2.0.0 re-score to be written beside them. 1.16.0 (2026-10-24, runtime v283, 145 tools, 1548 tests) was
  the twenty-eight fixes from the England game's end and this game's t0-t208.
- **The fair-play design note (8728ded, 2026-10-24).** A `--seat N` server refuses `set_seat` onto the other human
  seat and nothing else stands between one agent and the other's map (tunerd forwards any Lua for any caller; a
  second server, `scripts/mcp_call.py --seat N` and `harness.cli lua` reach the same socket). `docs/GAPS.md` has
  the threat model and a first count of runtime entries by seat argument (81 take `pid` first, about a hundred
  take a unit / city / plot and get their seat from the owner); `docs/ROADMAP.md` the five-stage route with tunerd
  as the enforcement point. Not started. (The small follow-up on `docs/AGENT_INSTALL.md`'s Codex paragraph was done 2026-10-27: it registers
  `--seat auto`, and one paragraph states the seat rule for every client -- auto for solo play, a pin only for a
  shared hotseat, with the reason.)
- **Live processes (2026-10-24 21:45).** Game pid 38183 (launched 21:42 by `scripts/launch_civ5.sh main`; Steam was
  already up), tunerd on `/run/user/1000/civ5-tuner.sock` since 21:44 (48 Lua states on its first connect), the
  Claude Code session server pid 25370 started 21:02 from current main. The quick save was loaded through
  `load_latest` at 21:45; runtime v283 answered the first briefing. Runtime v284 has been in the game since
  22:10 (injected by a fresh `scripts/mcp_session.py` server for the live checks above); the session server pid
  25370 still runs the v283 Python, so its `assignments` rows lack `distance` and an `amend_assignment` through it
  would refuse `review.max_distance` as an unknown key until it is restarted from current main.
- **Where t208-t238 is written down.** Nowhere in the repo: those turns were played on 2026-10-14/15 without a
  code change (the commits stop at t208). The notebook (note 2) and the saves are the record; the memory plugin's
  observations hold a turn-by-turn narrative outside the repo.
- **Memory-rule reminders**: the ctx sandbox lacks XDG_RUNTIME_DIR, export
  `CIV5_TUNERD_SOCK=/run/user/1000/civ5-tuner.sock` before any `harness.cli` call there; `pkill -f` in a
  compound Bash call kills the shell; disband is denied to the auto-mode classifier; copy QuickSave to a named
  file before loading another save into a live game (done this evening: S10).

## Still open

Pruned 2026-11-16 at 2.17.0. No GitLab issue is open and `docs/GAPS.md` §0 has no open row beyond the engine's
own limits under "Blocked". What stood here from 2026-10-24 to 26 (the t238 notices, the Siam risk of the Assyria
game, the stage-by-stage record of seat binding and of the tool surface) is released as 2.0.0: CHANGELOG 2.0.0,
`docs/ROADMAP.md` and git hold it. The two sections above ("Where the game is", "Where the code is") are the
2026-10-27 state, kept for the record.

- **The benchmark** has rules (version 0), a referee tool and a plan on GitLab (#210); the block at the top of
  this file says where it stands. Open by its own account: whether continuations end by a real victory and
  whether any Prince board is undecided (#195), the board maker (#194), diagnostics in the row (#196), the
  first board set and the models on it (#200, #201), goal boards (#205 to #207).
- **Tokens on the spectator page:** a running Codex cycle was counted request by request under play (2.17.0);
  the same for a Claude cycle read from its own directory is the fixture test only.
- **Spectator page:** it holds every parsed row of a recording (fine since the cadence fix; the 72 MB pre-fix
  file was 122 MB of heap under node, 70-72 MB in Chrome); a bounded window is not built.
- **The wheel is a server only:** no `web/viz/` (the spectator's page), no shim, no launch scripts; a host gets
  those from the repository (`docs/AGENT_INSTALL.md`).
- **Not yet seen live**: `quick_save` under a decision popup (coded 2026-10-11), the `fogged_destination` hint on a
  "no path" refusal (unit tests only), S9's RETURN_CIVILIAN re-raise on load, the refused-melee *rule* (GAPS §0
  Blocked: needs a war with the t200 shape -- a city tile, a river, a second unit in the city; only the wording is
  done). LAN: nothing since 0.5.0, and a war on a city-state syncing over LAN (`docs/LIMITATIONS.md`).
- `unit_displaced` (read live England t131): a *route* caravan on the city tile at the turn end did not move the
  General, only an idle trade unit does; why the engine moves the civilian and not the trade unit, and whether a
  Worker or Settler is moved the same way, is not known; the row reports the fact either way.
- **Tests that can collide with a live game:** `tests/test_assignments.py::McpAssignmentTests::test_the_four_tools`
  (2026-10-25) and two of `tests/test_hotseat_live_fixes.py::LeaderScreenGuardTests` (2026-10-30) failed with
  `another game operation is running (your own load_save, pid ...)` when the suite ran while a live `load` held
  the real per-socket lock; alone they pass. The MCP path takes the lock keyed by the live socket even under a
  fake game; a scratch lock path in those tests would end it. Until then do not run `scripts/check.sh` during a
  live load or finish.
- **Two tests failed once, together, on 2026-10-10** (the 1.15.0 cut):
  `test_ranged_preview.py::test_ground_ranged_has_no_retaliation_or_interceptor_read` and
  `test_runtime_source.py::test_a_failure_midway_is_not_current_and_the_corrected_retry_carries_state`; one of
  them once more in a loop of three runs of the pair. The assertion text was not captured. Not reproduced in any
  full run since. Both build a Lua state from `runtime_source.snapshot()` (one under ctypes liblua5.4, one under
  lupa). If it shows again, keep the `E` lines: a `pairs`-order dependency under a randomized string-hash seed is
  the first suspect, load the second.
