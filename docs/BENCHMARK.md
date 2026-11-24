# A benchmark of our own

Written 2026-11-13 as a sketch to argue with. Since 2026-11-22 it opens with how a player is scored; then the
earlier number and what made it honest, the rules, the argument and every measurement in the order it was made.
Background: `docs/CIVBENCH.md`.

## The premise

The agent is put in a human seat of stock Civilization V. It can do only what a human can do, see only what a
human sees, and it has to play anyway: every unit, city, trade and vote, for as long as the test runs. The harness
enforces the boundary; the benchmark measures the play. The benchmark is a definition (starting saves, runs, scoring)
that this harness can run and that another harness holding the same boundary could run too.

## How a player is scored (2026-11-22)

The benchmark is named **OMTbench**, for "one more turn". This section is how it stands since 2026-11-22 and it
comes before everything below it: where a later section says how a player's number is made, this one is the later
thought.

**A run leaves a recording, and the recording is what is scored.**

- A **recording** is what one run on one seed leaves behind: the run's row (what the runner read of the game at
  both ends of the turns, and the game's own replay lines between them), the seat's calls from the call ledger,
  and the saved game at the end of the turns. The saved game holds the whole state of the game, so a recording
  holds every score and figure the game has, not a chosen few.
- **One recording is one submission.** Anyone can run the benchmark with this harness and send in the recordings.
  The project scores them and publishes the scores.
- **The scoring is done by the project and its method is not published.** Nothing of it: not what it reads of a
  recording and not what it does with it. The reason is the plain one: a model, or the people tuning one, could
  play to a published method and not to the game. The same method scores every player. What the runner prints,
  and what this document lists as read from the game, says nothing about what is scored.
- **The built-in AI plays no part in a player's score.** No game of a player's is finished by the engine for its
  score. That was the earlier design (the sections below) and it was dropped on 2026-11-22: a paid run of fifteen
  minutes was being decided by fifteen minutes of the engine's play after it.
- **What is still said openly:** the starting saves, the seeds, the terms a save carries, what a player may see
  and do, what a recording holds, and with every published score its standard error over seeds. Seeds are separate
  games ("A skip has to be longer than a game"), and a player needs several.

**Where it is going** (decided 2026-11-22, not built; the milestones on GitLab hold the steps):

- A recording packed as one file that another machine can load and read with no network: built 2026-11-23
  ("A recording as one file" below). The scoring is to run on a machine with no network at all.
- Two families of test: open-ended games, a player's turns on a starting save, and narrow tests with a stated
  goal ("Goal saves" below).
- A web page where a benchmark is chosen and started: the harness starts the game if it is not running and plays
  the benchmark. How a visitor's own model is put on the seat is left for later.
- Scores published on the benchmark's own site, once a week. Each registered user may send in one submission
  a week.

### A recording as one file (2026-11-23)

    scripts/benchmark_recording.py pack logs/boards/<id>/rows.jsonl              # every run of the rows file
    scripts/benchmark_recording.py check logs/boards/<id>/recordings/*.zip      # the file itself: no game
    scripts/benchmark_recording.py check FILE --load                             # and its saved game, in the game

`pack` writes one zip a run, `<starting save>--<player>-seed<n>.recording.zip`:

| file | what it is |
|---|---|
| `recording.json` | the player, the seed, the starting save's id and sha256, the harness, the Lua runtime and the game build the run was played on, how the calls were chosen, what the saved game is of, whether the game file is in, and the size and sha256 of every other file |
| `row.json` | the run's row, whole |
| `calls.jsonl` | the seat's rows of the call ledger between the command's start and its end, as written |
| `game.Civ5Save` | the saved game: the end of the turns (`--keep-end`), or where the game ended inside them |
| `game.jsonl` | the run's game file: the whole world at the start of every turn, one JSON line a turn (below) |
| `on-the-way/t<turn>.Civ5Save` | the run's saves on the way, one for each the row lists (`--checkpoint N`) |

The same run packs to the same bytes every time, so a file's own hash names it. A run that kept no saved game (it
did not play its turns) has no recording and `pack` says so. The row is packed whole, the player's command line
included: read it before a file goes to someone else. Nothing in a file says what of it is scored.

A row keeps what a pack needs: `began` and `ended` (the command's start and end, so the run's calls are the
seat's ledger rows between them, the same rows `cost` counts), `harness`, `runtime`, `game_build`,
`save_sha256` (the starting save's file as it was loaded) and `game_file` (the game file's name and what was
written to it). A row from 2.19.0 or earlier has none of these and packs too: its calls are the seat's last calls
before the row was written, as many as the row counted, the starting save is hashed at packing, the versions are
not named, there is no game file, and `recording.json` says each of these.

`check` says line by line what holds, what differs and what it cannot say where it runs. With no game: every file
is the size and hash `recording.json` names and no other file is in the zip, the row is the run the file says it
is, the calls are the seat's, inside the run's times and as many as the row counted, the saved game begins as a
save does, the starting save is the one kept under `saves/benchmark/` when one of that id is kept there, and the
game file is whole, is of this run, has a line for every turn the run played, and says of the seat at the run's
start and of every player at its end what the row says. **This part needs the one script and Python and nothing
else**: no other file of the repository, no network. With `--load` (the game at the main menu, tunerd running)
the saved game is copied where the game loads from, loaded, read with the runner's own read and set beside the
row and beside the game file's last line: the game's build, the turn, the seat's ten indicators, every player's
score, and every player's ten indicators as the game file ends. The game is left for the main menu and the copy
removed. Exit status 0 when nothing differs, 1 when something does, 2 for a file it cannot read.

### The game file: the world at the start of every turn (2026-11-23)

A saved game holds the whole state of one moment and needs the game to be read. The row holds two reads, the
start and the end. What was between them, turn by turn, was in neither. A run's game file is that: JSON lines,
one line for every turn, written while the run plays. Anything that reads JSON reads it; the scorer needs no game
for the turns between a run's two ends, and the spectator page plays it back.

    line 1    "game"     what never changes: the game's terms and players, the static map, which run this is
    then      "start"    the world where the run started, before anyone played
              "turn"     the world as a game turn begins, one line a turn
              "end"      the world where the run ended

**How a turn gets into it.** A handler inside the game (on `GameEvents.PlayerDoTurn`) takes the whole world the
moment a game turn's first player begins it, and keeps it in the game until it is fetched. The writer, the
spectator page's backend (`harness/spectator/game_file.py`), puts the handler in before anyone plays, fetches what
it took about once a second and appends a line a turn. So a turn the engine played in under a second, between two
looks, is in the file like any other; a reader that only polled would have passed it over. The game holds the last
24 worlds for a reader that is behind; a line whose predecessors fell out says how many (`missed`). The handler
only reads. The moment is the one the game calls the turn's start for its first player, the seat on every
starting save so far: with the engine on the seat, the line of turn 1 already counts the seat's income of that
turn (gold 0 on the `start` line, 3 on the first `turn` line).

**What a world line holds**, fog ignored (it is the operator's file; no seat reads it):

| key | what it is |
|---|---|
| `players` | every player ever alive. A major civilization: `score`, `cities`, `population`, `land` (plots owned) and `land_plots` (those of them that are land), `military`, `science`, `happiness`, `gold`, `tourism`, `delegates`, `allies`; `techs` and `policies` by name, `branches_opened` / `branches_finished`, `era`, `researching`, `ideology`, `pantheon`, `religion`; `yields` (food, production, gold, science, culture, faith a turn, as the empire nets them), `total_yields` (the cities' food, production, gold and science added up, what the game's own graphs draw) and `stored` (culture, faith, the golden age); `score_parts`; `wonders`, `national_wonders`, `great_works`, `theming`, `trade_routes`, `great_people`; `resources` (each strategic and luxury resource: total and unused); `met`, `at_war`, `friends`, `denounced`, `defensive_pacts`, `open_borders_to` (player ids); `units`, `military_units`. A city-state: `ally` and `influence` by major civilization. |
| `cities` | every city: owner, plot, name, population, hit points, capital, puppet, occupied, resistance, razing, original owner, turn founded, strength, majority religion; for a major civilization's city also `yields`, `stored`, what it is `making`, its `buildings` by name, world and national wonders, great works |
| `units` | every unit, the barbarians' included: owner, plot, type, hit points, domain, embarked, moves left (in sixtieths), fortified; for a major civilization's combat unit also level, experience and `promotions` by name |
| `owners`, `features`, `improvements`, `routes`, `pillaged` | the plot layers that change, one character a plot with a legend, rows north to south as the static map of line 1 has them |
| `fog` | each human seat's own fog (and the run's seat while the engine plays it): visible, seen before, never seen |
| `religions`, `congress` | every religion founded with its founder and holy city; the World Congress's host and resolutions in force |
| `events` | the game's own replay lines since the line before: a war declared, a peace, a city founded, a wonder |
| `active`, `first`, `auto`, `winner`, `victory`, `over`, `year`, `took_ms` | whose turn it is, whose turn's start took the line, the engine's turns left on the seat, the game's end, and how long the capture took inside the game |

What it does not hold: the deals in force and what was traded, each great work and where it hangs, the trade
routes one by one, espionage, and the seat's notebook. The saved game has them.

**A file that can be trusted to be whole.** Every line carries its number and `prev`, the sha256 of the line
before it as written. A line changed, taken out or put in shows as a break at the line after it, with no other
file needed. Keys are written in order with no spaces, so the same world is the same bytes on any machine.
`recording.json` names the hash of the whole file as it does for every other.

**A game loaded again goes back in turns, and the file is only appended to.** A game that died and was loaded
from its last save leaves a second `start` line, of the turn it was loaded on, and the turns after it again. The
game as it stands is read off by one rule: a `turn` line of turn T sets aside every earlier line of turn T or
later; a `start` line of turn T sets aside every earlier line of a turn after T. `check` reads a recording that
way, and so does `game_file.standing()`.

**Why JSON lines and not a database** (decided 2026-11-23). A SQLite file was the first plan. Against it: the
scorer opens files other people send, and opening someone's database runs their schema; a database file's bytes
depend on the library that wrote it, so its hash names nothing; and two repositories would have to keep one table
schema in step. A line a turn has none of the three, and nothing asked of the file today needs more than reading
it front to back or one line by its place.

Every run writes one unless told not to (`--no-game-file`), as `<out>-<player>-seed<n>-game.jsonl` beside the
rows. A game file that cannot begin or end costs the run nothing: the row says what went wrong
(`game_file_error`) and the recording packs without it.

**Checked live, 2026-11-23**, on `duel-king-rome-huns-a`, the built-in AI's ten turns, seed 0:

- **Every turn is there.** Thirteen lines: the game, the start (turn 0), turns 1 to 10, the end (turn 10). The
  runner's own poll, every three seconds, saw turns 1, 5, 9 and 10 of that run; two of the turns were written
  within the same second.
- **The handler moves nothing.** The same seed played with the game file and without ended on the same figures,
  every one the runner reads, and the same replay lines.
- **It is cheap there.** A capture took 3 ms on those turns and 4 ms on a turn-140 save of the same map (73
  units, 12 cities); a line is 9 to 11 KB early and 23 KB on turn 140; the first line, with the map, 7.5 KB. No
  name of the game's API the capture asks for was missing. Putting a 10 KB world into text inside the game
  takes 0.6 ms more.
- **A whole game on a Small map** (`small-king-poland-a`, 66 by 42, six civilizations, the built-in AI, seed 1,
  a Cultural victory on turn 255): 258 lines, every turn, none missed, 18 MB; the largest line 108 KB (329
  units, 41 cities); a capture 13 ms on average and 22 ms at most; the game took 7.1 s a turn against 6.7 s for
  the same save's seed 0 without the handler, another game. Packed with its 25 saves on the way, 28.8 MB.
- **A whole game on the duel** (the built-in AI, seed 0, lost to the Huns' Domination on turn 305): 308 lines,
  7 MB, 25 MB packed with 30 saves on the way.
- **The start and the end are the row's.** The seat's ten indicators on the `start` line and on the `end` line,
  and every player's score on the `end` line, are what the runner read.
- **Packed and checked.** 763 KB with the one save; packed twice, the same bytes; `check` and `check --load`
  find nothing that differs, the loaded save reading as the game file ends for both players.
- **On another machine.** The Steam Deck, Python 3.14, given the one script and the one file: `check` exits 0,
  and `game.jsonl` reads there with `json` alone. (The first build of the check stopped there with
  `FileNotFoundError`: it loaded the runner from beside itself.)
- **On the page.** `python -m harness.spectator --replay <the packed file>` draws it in a browser: the map, the
  cities and units turn by turn, the turns ticked on the scrubber, no error in the console.
- **A game loaded again under one recorder** (the page's `--games` way, on the duel): five turns played, the
  game left, the same save loaded and three turns played. The file as written: the game, start 0, turns 1 to 5,
  start 0, turns 1 to 3, the end; as it stands: the second play's turns; numbering and chain whole.
- **Not seen yet: a model's run with a game file**, and a game that died inside a benchmark run.

**A save taken under the engine has to be left with care** (found the same night by `check --load`). A save on
the way of the built-in AI's run, or the save of its game's end, loads with one turn of the engine's still to
play: the observer is active, the count reads 1, and about a turn later the seat is its player's again. A game
left at that moment took the whole game process with it, three times of three on the duel, where a turn takes two
seconds and a load, a read and the exit come to about that. The same saves left once the count read 0: nothing,
three of three. `check --load` now reads at once and waits for the hand-back before it leaves
(`benchmark_run.wait_for_the_seat`). A player's own saves are taken on the seat's turn and load with no engine
turn to play.

**Earlier the same day**, with the first build of `check`, on four runs of the duel (780 KB with the one save,
3.3 MB with Opus's three saves on the way, 20 MB with Sonnet's twenty-four; all four are packed again in the
format above, the three models' runs without a game file, which they did not write):

- Sonnet's 250 turns (1,116 calls), Codex's 10 turns (59 calls) and the built-in AI's 10 turns: the saved game
  loads and reads as the row says, every figure.
- Opus's game won on turn 219 (511 calls): everything equal but one figure, the seat's happiness, 23 in the row
  and 9 in the loaded game. Attila's Court was taken in the turn the save was written; in the loaded game it is
  occupied and in resistance, and the game works happiness out again on a load. So **a save of a game's end can
  read a figure differently from the row**, with nobody's doing, and the check says which figure. It is left as a
  difference (exit status 1), not passed over: what to make of it belongs to whoever reads the check.
- With the network cut off (`unshare -rn`): the file check and the check in the game, both as above.

### The spectator page's own recording is another thing

The page (docs/VISUALIZATION.md) records what a watcher saw: `--record` writes its stream to a file, a snapshot
whenever the world moved under its poll, the ledger's rows, the game's events, the notebook, for as long as the
spectator ran and whatever games it saw. It is the page's history of an evening. It is not a run's record: with
the engine on the seat it read the world every eight seconds while a turn took one, so ten turns left two or three
snapshots. The first build of the recording carried that stream along (`--stream`, `stream.jsonl`); it is gone,
and the game file is in its place. The page plays a game file, or a packed recording, by the same `--replay`.

**What the sections below are now.** "The number, and what makes it honest" and the rules describe the earlier
number, the share of AI finishes won. It is still what was measured of the built-in AI on the first starting save
(0.438, standard error 0.071), and the work on seeds, on the terms of a save and on the runner carries over
unchanged. It is not how a player is scored.

## The earlier number, and what makes a number honest

**Not how a player is scored since 2026-11-22** (the section above). What follows is the number as it was designed
until then, and as it was measured for the built-in AI.

The benchmark gives each player one number with its uncertainty. It is not a way of telling players apart (the user,
2026-11-20): two players that come out the same are a result, and how many runs to pay for is a choice of cost.
A number is honest when four things hold. Each is given here with what stands today and what does not yet.

**The words.** A **player** is the model or program being measured. The **built-in AI** is the game's own computer
player. The **starting save** is the saved game every run starts from; today there is one, the Celts against Austria
on a Duel map (`board-duel-prince-d`), and the player plays **the Celts**. A **seed** is the number that sets which
random numbers a game gets, and a **run** is one game on one seed. A seed is set by a **skip**: that many random
numbers are generated and thrown away before anyone plays. The player plays **the 100 turns**, turn 0 to turn 100. An
**AI finish** is the built-in AI playing the game on from turn 100 to its end, for every civilization, and it is won
or lost. The **baseline** is the built-in AI playing the Celts' 100 turns itself, measured the same way as any player.
The **win-chance formula** is a fitted formula that gives a chance of winning from the figures at turn 100. **Full AI
games** are games the built-in AI played from the first turn to the end.

**1. A defined quantity.** The number is the chance that the Celts win the game, when the player has played their
first 100 turns on the starting save and the built-in AI plays every civilization from there to the end.

- It is measured one way: by AI finishes, as the share of them the Celts win (rule 1). The win-chance formula gives
  no number (the user, 2026-11-22). It was the second way from 2026-11-19; on twenty separate seeds it was no
  closer to a seed's share than the plain mean is (point 2). The script and its measurements stay
  (`scripts/benchmark_fit.py`, rule 1, "The estimate").
- A run whose 100 turns were not all played did not finish. It has no value, and it is counted and shown beside the
  number, never averaged into it (rule 5).
- The game is played on fixed terms that the starting save carries: the Celts are on the handicap row every AI plays
  on, and there is no Time victory, so a game ends by a victory someone took (rule 2).
- Not defined by it: whether the player could have finished the game itself. The built-in AI finishes every game, the
  same for every player.

**2. A measurement that is not skewed.** Every player meets the same thing, and nothing outside its play moves its
number.

- Stands: the same starting save, the same terms and the same seeds for every player, the baseline included. The
  same nine tools and no notebook at the start (rule 3). The seat's server closes the seat on turn 100, so a player
  cannot play past its turns by a miscount (rule 5). Time is no part of a result (rule 5). A run broken by the harness
  or the game is void and played again (rule 5). A save plays the same game on another processor, so anyone can
  compute a value again ("A save is the same game on another processor"), by playing its games in the same order
  from a fresh game process (the rules, "What version 1 changed").
- A skew that is gone: the win-chance formula. Before turn 110 it has one input that helps, the share of score, so
  a player that plays for something it has no input for (delegates for the World Leader vote, which decides most
  games on this starting save) was valued too low by it. On the first twenty separate positions it says 0.505 where
  0.438 of five AI finishes a position were won, within the errors; seed by seed it is no closer to a seed's share
  than the plain mean is (2026-11-22, "The baseline on separate seeds"). No number is given by it.

**3. A true uncertainty.** The error given with the number has to be the error it really has.

- The seed is the unit. The AI finishes of one seed go together (one seed was 0 of 5 and the next 5 of 5 with the
  Celts the same at turn 60 in both), so the standard error is taken over seeds and never over games (rules 4 and 6).
- The number has one error, the one over seeds. (A value by the formula had a second, the formula's own; rule 6
  keeps how it was taken.)
- Since 2026-11-20 every game has a stretch of 1,000,003 random numbers to itself, so two seeds, and two AI finishes
  of one save, are separate games ("A skip has to be longer than a game").
- Before that a seed was 17 random numbers on from the one before, and games on neighbouring seeds were the same
  game early on and alike at turn 100. Thirty-one games were a handful of games counted many times. Every error
  over seeds in the sections dated before 2026-11-20 is too small, by an amount that was not measured.
- Checked 2026-11-21 on twenty 100-turn runs of the built-in AI at the new spacing: seeds next to each other are no
  more alike at turn 100 than any two seeds (likeness +0.022, which 0.422 of random orderings of the same runs
  reach; at the old spacing +0.120 and +0.219). The baseline on them is 0.438 with a standard error of 0.071 on
  five AI finishes a seed (2026-11-22; 0.474 and 0.118 on one; "The baseline on separate seeds").

**4. A plain statement of scope.** What the number is about, and what it is not about.

- One starting save: the Celts against Austria, a Duel map (Archipelago, four city-states), Prince, Quick speed,
  stock rules, no mod. It is the one save of five screened on which the baseline wins between 0.2 and 0.8 of its
  games (rule 2). The save and its manifest are in the repository (`saves/benchmark/board-duel-prince-d`).
- The first 100 turns of a game, against the built-in AI. Nothing is said about other maps, other civilizations, more
  opponents, the middle or the end of a game, or play against people.
- A player is a client, a model, an effort setting, a harness version and a prompt file together (rule 3). The number
  belongs to all five.
- No model has been benchmarked. Claude Sonnet 5.5 at low effort played eight seeds on 2026-11-19 as a first trial of
  the design ("The first trial"). Its figures (0.434 by the formula, with 0.087 over seeds and 0.047 of the formula;
  3 of 8 AI finishes won) come from the old seed spacing and an old fit, and are not a result about the model.
- What a number costs: about 20 dollars at list price for eight seeds of that model, and no tokens for the baseline,
  the AI finishes or the fitting.

**Files from before 2026-11-20** keep the names they were given, and their rows the keys of that day;
`scripts/benchmark_run.py` reads them in today's words. Under `logs/boards/` (one folder a starting save): a file
named `anchor-...` holds the baseline, `burn-scan-...` the scan of skips, `pilot-...` the first trial,
`estimator-...json` a fitted win-chance formula, and a save named `...-dealN-end` is the game at the end of seed N's
turns. The sections below were written with other words for these things and were reworded on 2026-11-20; their
figures are unchanged.

## What a new starting save takes (2026-11-20)

The user's question that day: does all of this have to be done again for every map and every kind of benchmark?
No. Most of what the sections below record was finding out how the engine behaves, and that is found once.

**Found once, true of the engine and of the scripts, whatever the map:**

- How the game's random numbers work and how far apart two seeds have to be ("A skip has to be longer than a game").
- A save replays the same game on a seed, on any processor, when the game process has played the same games
  before it (a fresh process, for a first load; found 2026-11-22).
- What the engine needs to play a seat by itself: an observer slot, one human seat, a watch for the end of the game
  ("Autoplay, checked live").
- The terms a starting save carries (the seat on the AIs' handicap row, no Time victory), put into a save by one
  command (`--terms`).
- The runner, the rows and the summary.

**Done again for each starting save.** Another map, civilization, set of opponents, difficulty or number of turns is
another starting save. All of it is machine time and none of it tokens:

1. The terms: one command.
2. One batch of the built-in AI: it plays the turns on a number of seeds and finishes each game. The share it wins
   says whether the save can be used at all (between 0.2 and 0.8, rule 2: one of the five saves screened so far) and
   is the baseline. On the Celts duel the 100 turns take 3.5 minutes and an AI finish 15.7, so twenty seeds with one
   finish each are six and a half hours.

Then each player's own runs, which are the only part that costs tokens, and the AI finishes of those runs, which
are machine time again.

**Full AI games are not a step of their own any more.** A baseline run with its AI finish is a game the built-in AI
played from the first turn to the end, saved and loaded once on the way (which was not shown to change a game, "Eight
more full AI games"). Its rows hold what the win-chance formula is fitted on: the figures at turn 100 and who won. So
the sixty full AI games the formula was first fitted on are not played again for a new starting save, and the question
left open on 2026-11-20 (full AI games of the starting save started on the same stretches of random numbers as seed
0's AI finishes) is closed by not playing them.

**The formula is not needed for the number.** The number is defined by AI finishes alone (point 1 above). The formula
replaces a finish, which is won or lost, by a reading of the figures at turn 100, and so needs fewer games for the
same error; it brings an error of its own and a known skew (point 2). What the number costs without it is what
`--summary` prints since 2026-11-20: how much a finish varies from one end of the turns, how much the chance the turns
leave varies from seed to seed, and the seeds a standard error of 0.05 takes at 1, 5 and 15 finishes a seed. On the
first trial's rows (seven seeds of five finishes, at the old spacing, so a first look): a finish varies by 0.478, the
seeds by 0.145 (0 to 0.216 when the seeds are drawn again), and 0.05 takes 100 seeds at one finish, 27 at five, 15 at
fifteen. A finish is fifteen minutes of the machine and a seed is 100 turns of a player's tokens, so finishes are the
cheap way to an error and seeds the dear one. The same split on the baseline's twenty separate seeds (2026-11-22): a
finish varies by 0.433, the seeds by 0.252 (0.180 to 0.291), and 0.05 takes 101 seeds at one finish, 41 at five, 31 at
fifteen. The seed-to-seed part is larger than the first look said, so finishes are cheap but do less: no number of
them brings the count under 26 seeds (below, "The baseline on separate seeds").

## Rules, version 1 (2026-11-17)

**Since 2026-11-22 rules 1 and 6 are not how a player is scored** ("How a player is scored" at the top). Rules 2 to
5 (starting saves, players, seeds, what counts as a run) stand. The rest is kept as it was written.

The user left the rules to be worked out (2026-11-16). These are the rules the measurements so far support. Each
says what is seen and what is not, and rule 8 lists the tests that would overturn them. The sections after this
one are the argument and the measurements; where they differ from a rule, the rule is the later thought.

**What version 1 changed**, after the first night of rule 8's tests (36 games finished by the AI, "The seat's row" and
"The scripted loop against the baseline" below):

- A starting save carries its terms: the seat is on the row every AI plays on, and there is no Time victory (rule 2).
  At Prince as hosted the engine-played seat lost every full AI game, all by Time.
- A starting save's range is measured the way a run is valued, through the run, the save and the AI finishes (rule 2).
  The first duel is 0.90 by save and AI finish and 0.73 by sixteen full AI games; the first eight full AI games alone
  said 0.57, and the gap they seemed to show did not last the second eight.
- An AI finish with no victory by a stop turn is not decided and is in no share (rule 1).
- A value is given with its standard error and over all of a player's games on the starting save (rule 6).
- Rule 8's first test failed on the first starting save (out of the 0.2 to 0.8 range, a 30-turn run). On the first
  starting save found inside the 0.2 to 0.8 range the scripted loop's 100-turn run is 0 of 10 where the built-in AI's
  is 5 of 10, its 60-turn run 5 of 10 and its 30-turn run 7 of 10 ("The scripted loop against the baseline,
  again" and "How short a run" below). One starting save in five screened is in the 0.2 to 0.8 range. With ten seeds
  the built-in AI there is 0.30 and the fixed loop's eight seeds 0.125 (one win): by seeds not a separation ("The
  fixed loop's eight seeds" below).
- **A win as the only unit costs too much**: about ten seeds a side to tell 0.3 from 0.0, each seed a run of a model's
  tokens. The fitted win-chance formula of rule 1 now exists (`scripts/benchmark_fit.py`, "The win-chance formula's
  first fit" and "The win-chance formula on sixty games" below): fitted on fifty-nine of the built-in AI's own games
  and read once where a run ends, it puts the built-in AI's 100-turn runs 0.27 to 0.31 above the scripted loop's with
  a standard error of 0.08 to 0.10, where the same eighteen runs finished by the AI were 0.175 apart with one of 0.18.
  Most of that error is the model's own (0.07 to 0.09, a jackknife over its games; the first fit's "0.04" left it out)
  and is paid once a starting save in games that cost no tokens; a player's seeds add 0.03 to 0.04. AI finishes remain
  its check, and each one played is a row for the next fit.
- **The games of one seed go together** (the 60-turn run: 0 of 5 on one seed, 5 of 5 on the other, the
  seat the same at turn 60 in both). The seed is the unit: a value's standard error is taken over seeds
  (rule 6), a player needs many seeds and few AI finishes a seed (rule 4), and the 100-turn result
  stands on two seeds a side until more are played.
- The same save and the same AI finish number are the same game to its last turn **in a game process that has
  played the same games before it**; a fresh process's first load is the same game every time. In a process
  that has played other games they are another game (checked 2026-11-22: "A replay that was not the same game"
  under "The baseline on separate seeds"). So a value can be recomputed by anyone who plays its games in the same
  order from a fresh game process, and new games of a save need new numbers. The batches so far started a fresh
  process every eight or ten seeds, so a single seed's rows are recomputed only by playing that stretch again.
  A fresh game process for every seed (about a minute each) would make each seed's value recomputable by itself.
  It was proposed and turned down (the user, 2026-11-22): it changes no number and no error, and a seed's games are
  as good a sample of the Celts' chance whatever was played before them.

**Decided 2026-11-22 (the user)**, after the baseline on twenty separate seeds:

- The number is the share of AI finishes won and nothing else. The estimate of rule 1 and its two errors of rule 6
  are withdrawn; their text is kept as the record of what was tried.
- No fresh game process for every seed. A batch starts the game when it has to, as before.
- The baseline stays at twenty seeds of five AI finishes (0.438, standard error 0.071). More baseline seeds are not
  planned ("Are twenty seeds enough for the baseline?" under "The baseline on separate seeds").

**1. A run is worth what the game was worth when the player's turns were over.** A player plays a seat for a
run of turns. Then the game's own AI plays that seat and every other to the end of the game, several times
(AI finishes). The run's value is the share of the AI finishes the seat wins. Nothing else orders players.

- A win is the one thing every victory type has in common. Score is not: it counts size. The Maya seat of the
  t242 starting save holds 6.4% of the living civilizations' score and is tenth of twelve with 8.6% of their
  technologies, and a fast four-city science win scores below a slow conquest.
- It is the estimate of point 4 below without a fitted model: the position is valued by what one fixed finisher, the
  built-in AI, makes of it, the same for every player. It does not measure whether the player could have finished the
  game itself.
- A seat dead or a game lost inside the run is 0, a game won inside it is 1, with no AI finish.
- It is a probability, not one game's result: one AI finish is a single win or loss, twenty are an estimate. Where
  that is still too coarse, more seeds are the only finer instrument (rule 6).
- **The estimate (added 2026-11-19, withdrawn 2026-11-22: no number is given by it; what follows is the record).**
  On a starting save with a fitted model a run has a second value: the model's
  chance of the seat winning, read once from the position the run ended on (`scripts/benchmark_fit.py`).
  Players on that starting save are compared by the estimate. The share of AI finishes won is its audit, and every
  AI finish played for the audit is a row of the starting save's next fit.
  - *The model is the starting save's.* A logistic fit of the seat's team winning on what the runner reads of every
    player at one moment (the seat's share of each indicator and route), fitted on games the engine played
    from that starting save: full AI games, and the AI finishes of played runs, whoever played the run. Only
    the reads within ten turns of the turn the run ends on are fitted. It knows nothing of how a position
    was reached or who played it. A feature is kept only if it lowers the log loss on games left out of the
    fit.
  - *It is named and frozen.* A value by estimate names the model's file, its games and the turns fitted. A
    new fit revalues every player of the starting save together, never one.
  - *A run ends only where the model tells something*: in turns where it beats the base rate on games it
    never saw. On the Celts duel that is not before turn 60; at 30 the estimate tells no player from another.
  - *Its limit is its features.* With score as its one feature (all that helps before turn 110 on the Celts
    duel) the estimate orders players as their share of score does, and what is said of score above holds
    of it. It is then the starting save's measured rate of exchange between a lead in score and wins, not a judgement
    of the position. A player who plays for what the model has no feature for is valued too low: on that
    starting save 37 of 59 games end by the vote and delegates say nothing before turn 200. The audit is the guard.
    A player whose share of AI finishes won stands above its estimate by more than their errors is reported by the
    share of AI finishes won, the report says so, and its AI finishes go into the fit.
  - Seen ("The win-chance formula on sixty games" below): score alone on turns 90 to 110 of 59 full AI games and 21
    played runs; the built-in AI's ten 100-turn runs 0.413 and the scripted loop's eight 0.093, where by AI finishes
    they were 0.30 and 0.125. Not seen: a player the model never saw valued and then audited; a second starting save;
    a model with more than score in it at a turn a run can afford.
- **The path, on a long run.** The runner can save at fixed turns inside the run and value each save the
  same way. The path says whether a lead was built early and kept, thrown away, or won back from behind. The
  headline stays the value at the end of the turns: an average over the path would pay for a lead that was then
  lost.
- **An AI finish is stopped at a turn the starting save names** (500 at Quick speed so far). With no victory by
  then it is not decided: it is in no share and is counted beside the value. One full AI game in eight on the
  first duel ended that way, the seat far ahead.
- Seen: 114 games finished by the AI with no screen in the way, the winner read from `Game.GetWinner()`, ended by
  Diplomatic (73), Culture (20), Domination (11), Science (1) and Time (5, before it was switched off), three at the
  seat's death and one stopped at turn 500; the save-and-finish sequence of run, save, load and AI finish; an AI
  finish from turn 30 of a duel in 12 to 14 minutes. Every victory type has now been read by the runner; Science once,
  on a starting save made for it ("A Science victory" below).

**2. Starting saves.** A starting save is a save, a seat, a number of turns and a number of seeds.

- Hosted from the single-player setup screen: Prince, the unused slots as the screen leaves them (the observer
  slot autoplay needs), stock rules, no mod. Small maps (Duel to Small) at Quick speed, so that an AI finish
  is minutes.
- **From 2026-11-22 a new starting save is hosted at King** (the user's decision). The first is
  `small-king-venice-a`: Venice against five civilizations on a Small Continents map with 12 city-states. What
  was measured on the Prince saves below stays as measured, and says nothing of a King save.
- **Then made to carry its terms** (`benchmark_run.py --terms`): the seat is put on the row every AI of the game
  plays on (`HANDICAP_AI_DEFAULT`; the human's Prince row has base happiness 9 against 15, research at 100%
  against 85%, policies at 100% against 75%), and the Time victory is switched off with the turn limit cleared.
  The save keeps both. Every player of the game is then on one row, whoever plays the seat: a player, the
  built-in AI and the scripted loop play the same run on the same terms, and so does every AI finish. The
  player plays a game a little kinder than Prince; what is compared is always two players of the same seat.
- **Made by one command and kept with a manifest** (`scripts/benchmark_save.py`, 2026-11-22). `--host` starts a
  game from the setup screen with the civilization, world size, map script and speed said and every victory type
  on, puts the terms in and saves it. `--cut` has the built-in AI play a save for a number of turns on a seed and
  saves there. Either way the save is then loaded once more and read, and what the game answers is written down
  beside a copy of the save under `saves/benchmark/`: seat, civilization, opponents, the settings the save carries,
  where it came from, the game's build and the file's hash. `--install` puts the kept saves where the game loads
  them from. Kept so far: the Celts duel as hosted, the same game at turn 100 and at turn 200 as the built-in AI played it
  on seed 0 (3.3 and 6.9 minutes), and a second opening hosted by the command (Siam against the Shoshone, Pangaea).
  The last three have no baseline and are not in use.
- Without Time a game runs to a victory someone took: on the first duel the World Leader vote, a Culture
  victory or a conquest, between turn 126 and turn 425.
- Three kinds by where the run sits: an opening (from turn 0), a middle game, a late game. They are reported apart. A
  middle or late starting save is cut from a game the built-in AI played alone to that turn: an honest origin, no
  one's notebook, and as many starting saves as wanted for no tokens.
- **A starting save is kept only if the baseline's value on it is between 0.2 and 0.8**, the baseline's value being
  measured as any run's is: the built-in AI plays the run, the game is saved, and the save is finished by the AI. On a
  starting save the seat always or never wins, no run can show anything. The first duel is 0.90 by save and AI finish
  (9 of 10) and 0.73 by sixteen full AI games (11 of 15 decided), 0.80 over both: on the top edge, and not a starting
  save to spend a player on. With ten decided games a value near 0.5 is known to 0.16 either way; a starting save near
  an edge of the range needs more before it is kept or dropped, and a starting save in its middle is the better use of
  the games.
- **The seats of one map.** Where the same map can be started from each of its seats, every seat is a starting
  save, and a player's spread over the seats of one map is reported beside its mean: the same world from the river
  valley and from the tundra. Seats outside the 0.2 to 0.8 range above are still dropped. Checked 2026-11-22: not
  by a fixed map seed. This build's setup screen has `PreGame.RandomizeMapSeed` and no call that reads or sets the
  seed, so a second game hosted with the same settings is another map. Not tried: a map file made in the game's
  own map editor, which the setup screen can start from any seat.
- Goal saves (below) are the second kind of test, pass or fail against a runner, and are reported apart.
  One family of them comes in pairs: **the same save with and without one staged event** the seat can see (an
  army gathering at the border, a neighbour two parts from a spaceship, a city-state ally under siege). What
  the player builds, moves and signs in the turns after is counted from the ledger on both starting saves. The
  difference between the two is its reaction, measured without anyone judging what its strategy was, and the
  runner's predicate (the city still held at the end) says whether the reaction was enough.

**3. Players.** A player is a client, a model, an effort setting, a harness version and a prompt file. It has the nine
tools and one seat: no shell on the game's machine, no save file, no Lua. It starts with no notebook; what it writes
during the run is its own. Two players are always on a starting save beside the models: the built-in AI playing the
run (`built-in-ai`, the baseline) and a scripted loop that answers only what the game forces, from fixed lists
(`scripts/play_loop.py`). The loop was meant as a lower reference point and is not one by construction: on the first
duel its opening (Worker, Monument, Shrine, Granary, four Tradition policies, the Warrior at home) was worth as much
as the built-in AI's. It is reported as a second fixed player, not as a lower bound.

**4. Seeds.** A player's nth run on a starting save is seed n: before the run 16,000,048 n random numbers are
generated and thrown away (the skip), the same for every player, since a save otherwise replays the same game. An AI
finish skips (m + 1) times 1,000,003 for finish m of a save, so that every game has a stretch of the random sequence
to itself (since 2026-11-20; before it a seed was 17 random numbers and an AI finish 29, which were not separate
games: "A skip has to be longer than a game"). **Seeds are what a player needs many of.** What the other side does
with a seed's random numbers inside the run decides more than the AI finishes after it do: the scripted loop's 60-turn
run on the Celts duel was worth 0 of 5 on seed 0 and 5 of 5 on seed 1, the seat identical at turn 60 and Austria at
score 247 and 182. So eight seeds with one or two AI finishes each, not two seeds with five. For a model every seed is
a run of its tokens, and that, more than machine hours, is what a value costs.

**5. A run counts whatever happened.**

- The number of turns is the runner's: the game must be that many turns on. **The runner closes the seat on the last
  turn** (added 2026-11-19; the user: overshooting is the benchmark's to handle, not the player's). The seat's server
  is given that turn (`CIV5_UNTIL_TURN`, set by `llm_seat_loop.py --until-turn`): the finish that brings it says
  `last_turn_reached`, a run of quiet turns stops on it, and on it every order and every finish is refused. So a
  player cannot play past its turns and a count gone wrong is not a run that did not finish; stopping short still is.
  Before this a starting save one turn past the run read as not played and had no value (the first trial's seed 1,
  whose cause was the harness's own and is fixed apart from this).
- **Did-not-finish is a result of its own** (the user, 2026-11-16). A run that stopped short (gave up, ran out of time
  or quota, the client died) did not finish. It has no value and is not averaged in as a nought: a seat left after
  nine good turns and a seat played into a lost position are different things and a mean would hide which happened. A
  run that did not finish is counted and shown beside the value.
- **A run that did not finish stands below every finished run** wherever runs are ordered. Otherwise stopping would be
  worth the baseline's value and a weak player would do best by not playing. Where one number is needed the value is
  also given with every run that did not finish as 0, and says so.
- A seat that dies inside the run, or a game lost there, is finished: it was played, and it is worth 0.
- A run is void and played again only when it was not the player's doing: the game process died, the engine
  stalled or did not take the seat, the harness answered with an internal error. The ledger says which.
- **Time is no part of a result** (the user, 2026-11-19; this replaces "one wall-clock limit a run for
  every player"). How long a run takes is the machine's and the provider's as much as the player's: the
  game itself runs slower in the background than in focus, a new processor changed every figure the same day,
  and a model's seconds are its provider's queue. So no run is lost to a clock, nothing is ordered or
  valued by seconds, and seconds are not compared between machines. The runner keeps a watchdog (`--timeout`,
  four hours where a run takes a quarter of one) only so that a client that hangs ends: that is a client
  that died, a run that did not finish as before, and the row says `timeout`. Tokens are counted, not capped.
- **The player is told the turn at which the run is over**, in the same words for all: "the run is over
  when turn N is yours". Told "play 10 turns", Codex ended its tenth turn, got a leader on screen between the
  turns, and stopped there with the game nine turns on; Grok answered the leader and reached the turn (both
  2026-11-16, below). What the turns between ask is part of the run.

**6. What is reported.**

- Per starting save and player: the mean of its finished seeds' values with **the standard error over seeds** (the
  seeds' standard deviation over the root of their number), the baseline's and the scripted loop's beside it,
  each seed's own value, the games behind them (won W of N), and the number of seeds not finished. The
  games of one seed are not independent trials (rule 4), so sqrt(p (1 - p) / N) over games, which
  `--summary` still prints, is too small and is not the error of a value. With seeds worth 0 or 1 each, ten
  seeds tell 1.0 from 0.5 and not 0.9 from 0.7, and a difference of 0.15 between two players on one starting save
  needs about ninety seeds each. That is the price of a win as the unit, for a model it is paid in runs
  of tokens, and it was the reason for the estimate of rule 1. Measured since on twenty separate seeds of five AI
  finishes: a standard error of 0.071, and 0.05 takes forty-one ("The baseline on separate seeds").
- **A value by estimate had two errors and both were given** (added 2026-11-19, withdrawn with the estimate
  2026-11-22; the record). The seeds' (the standard deviation of
  the seeds' estimates over the root of their number) is the player's. The model's is the starting save's: a jackknife
  over the games of the fit (the estimate under each fit that leaves one game out, their spread scaled by the number
  of games). It is shared by every player valued on the starting save and more seeds do not make it smaller; more
  games of the starting save do, most where players' runs end. A difference between two players is given with the
  model's error taken on the difference, since one fit values both. On the Celts duel at 100 turns the built-in AI
  less the scripted loop is 0.320 with 0.045 from the seeds and 0.056 from the model, 0.072 together; the same
  eighteen runs finished by the AI, 0.175 with 0.18. A seed's estimate varies far less than a seed's win (a standard
  deviation of 0.14 over the built-in AI's ten seeds against 0.5 for an even chance), so eight seeds give the player's
  own error as 0.05 where eight wins give 0.18. The range of the fits that leave one game out is not an error and is
  not given.
- The headline has two parts and neither is given without the other: **the share of runs finished**, and over those
  **the mean over starting saves of the player's value less the baseline's**, per kind of starting save, with an
  interval from resampling starting saves. It reads "finished 8 of 9 runs, and left the seat this much more (or less)
  likely to win than the game's own AI did with the same turns". The same difference with every run that did not
  finish as 0 is printed under it.
- A fitted rating over players (Bradley-Terry) only once there are players enough; the headline needs none.
- Always beside it: the share of runs played, tokens a turn, orders refused ("What can be
  measured with no scale at all"). The indicators and the parts of the score are diagnosis, never the ordering.
- Every row carries the harness version, the runtime version, the starting save and the seed.

**7. How the seat was played.** Read by the runner at the two ends of the run and counted from the ledger, and
printed per player next to the built-in AI's on the same starting save. They are part of a run's recording. (As
written on 2026-11-17 they were "never part of the ordering". Since 2026-11-22 nothing is said of what in a
recording is scored: "How a player is scored".)

- *What the empire turns its yields into.* Food, production, gold, science, culture and faith a turn at both
  ends; gold on hand at the end against income (on the t242 starting save the scripted loop ended two turns with 305
  gold where the AI had spent down to 15); turns a city built nothing and turns a unit stood with no order; the
  parts of the score (cities, population, land, wonders, technologies, policies), so that "grew wider" and
  "advanced" can be told apart.
- *Where the seat stands with the others.* Wars it is in and who declared them, declarations of friendship,
  denouncements given and received, city-state allies, at both ends; cities and units lost; what it gave and got in
  each trade and peace treaty, listed, not scored.
- *What the play cost.* Tokens a turn, calls a turn, orders refused by reason, the share of runs
  played. Seconds a turn are written down as a fact about the run and its machine, not about the player (rule 5).
- **In the row and in `--summary` since 2026-11-22** (`played` and `cost` in a row; "how the seat was played" in
  the summary, each player's mean beside the built-in AI's). The saved game of a recording holds all of this and
  the rest of the game besides; these are the figures the runner prints for a reader.
  - *Read from the game at both ends of a run, for the seat:* the six yields a turn, gold on hand, the nine parts
    of the score, units, and who it is at war with, friends with, has denounced, is denounced by and is allied
    to. *Between the ends:* the lines of the game's own replay (a war declared and by whom, a peace, a wonder, a
    golden age, a city founded), kept as the game wrote them. Wars declared by the seat and on it, peace made,
    wonders and cities founded are counted off those lines; war and peace are also printed line by line.
  - *Counted from the call ledger for a player's run:* calls, calls refused by the reason given, unit turns
    skipped, and every order to another civilization with its reply, listed. Tokens are read from the records a
    seat loop keeps (`--log-dir`). The built-in AI makes no calls and has no such figures.
  - *Not there.* Units lost and cities lost: the game keeps no count and the replay names a captured city only
    in a sentence. Turns a city built nothing and turns a unit had no order: the game does not end a turn in
    either state, so the count is always nothing; unit turns skipped stand in for the second. What was given
    and got in a trade the built-in AI made: its trades leave no ledger. A refusal inside a batch: a batch is
    one call in the ledger.

**8. What would overturn this, to be tested before any model's tokens are spent on it.** Where each test
stands after the night of 2026-11-17, with what was measured since (to 2026-11-22) added at the end of each:

- *The value cannot tell a lower reference point from the baseline.* **Open. The loop's seat is worth less the longer
  the loop holds it, on a starting save in the 0.2 to 0.8 range; by seeds the difference at 100 turns is not yet
  shown, and at 30 turns there is none on either starting save.** On `board-duel-prince-d` (the Celts against Austria;
  two seeds, five AI finishes a seed) the scripted loop's run is worth 7 of 10 at 30 turns, 5 of 10 at 60 (0 of 5 and
  5 of 5) and **0 of 10 at 100**, where the built-in AI's 100-turn run is 5 of 10 and its fourteen games on the
  starting save are 7. The loop never builds a Settler, and the longer it holds the seat the less the seat is worth:
  that is valuing by AI finishes doing what it was meant to. But the games of one seed go together, so the 100-turn
  result is two seeds at 0 against two at 0.4 and 0.6, not twenty independent games (which would have made it 0.016 by
  chance). With eight more seeds a side the built-in AI is 0.30 over ten seeds (standard error 0.13) and the loop
  finished three seeds of ten, all at 0: by seeds that is not yet a separation (three in ten by chance), and the
  loop's seven unfinished runs were its own fault, since fixed. At 30 turns the loop's opening costs nothing on this
  starting save (7 of 10 against the built-in AI's 7 of 14) or on the first duel (10 of 10 against 9 of 10): thirty
  opening turns of one sound build order are not bad play, and no test of a 30-turn run exists yet that has bad play
  in it. *Since:* the loop with its fault fixed finished eight seeds of 100 turns and won one, 0.125 (standard error
  0.125) against the built-in AI's 0.30 (0.13): 0.175 apart with 0.18 ("The fixed loop's eight seeds"). Those seeds
  were at the old spacing. **Still open on 2026-11-22:** the loop has not been played on the separate seeds the
  baseline now stands on (0.438, 0.071). Twenty of them with one AI finish each are about eleven hours and no
  tokens (17 minutes for the loop's 100 turns, 16 for a finish); a loop at 0.125 would then stand about three
  standard errors under the baseline, and a loop that does not would say the number cannot see bad play.
- *AI finishes are too slow or too noisy.* **Slow and noisy, both measured.** From an opening a duel
  AI finish is 12 to 14 minutes, and a whole Tiny game to turn 330 took 24. Five an hour is a value known
  to about 0.2. "Valued within the hour" holds only for late starting saves (an AI finish from turn 325 took 2.2
  minutes). Rule 6 now gives the standard error and says what a difference costs. *Since:* on the Celts duel the
  built-in AI's 100 turns take 3.5 minutes and an AI finish 15.7. An AI finish varies by 0.433 from one end of the
  turns and the chance the turns leave by 0.252 from seed to seed, so twenty seeds of five finishes give 0.071 and
  0.05 takes forty-one ("The baseline on separate seeds"). Not measured: a Small map; no starting save on one is
  planned.
- *No starting save is undecided.* **One is, of five.** The seat on the human's Prince row lost every full AI game. On
  the AIs' row the first duel is 0.80 over all 25 decided games of the built-in AI, on the range's top edge; two
  more duels were 4 of 4 and the first Tiny starting save 0 of 4. `board-duel-prince-d` is 7 of 14, 0.50 (standard
  error 0.13). Starting saves have to be hosted in number and screened, about four for one kept. *Since:* 0.438
  (0.071) on twenty separate seeds of five AI finishes.
- *The save in between.* **Holds as a mechanism; not shown to change the result.** Twenty games finished by the AI
  from a turn-30 save had no conquest and the first eight full AI games on the same starting save had three, which
  looked like the save's doing (0.017 by chance). Eight more full AI games had none: three conquests in sixteen full
  AI games against none in twenty is 0.08, and the built-in AI's value is 0.73 by full AI games (11 of 15) and 0.90 by
  save and AI finish (9 of 10), no difference at those numbers. At turn 30 the two have not met, and what can be read
  of both players is the same before the save and after the load. The range is still measured by save and AI finish,
  because that is how a run is valued, and every run goes through the same save-and-finish sequence.
- *AI finishes end by score.* **Answered.** With Time off every decided game ended by a victory someone
  took, and in five of them the winner had the lower score.

**Considered and left out** (suggestions weighed 2026-11-16):

- *A progress-weighted average of standing over the full AI game as the result.* The path of rule 1 is taken from
  it; the average is not, and neither is standing measured as a share of score or against the leader of the
  moment, since score counts size.
- *A count of strategic pivots, with a healthy range.* Nothing operator-side can say what a strategy was or
  when it changed without interpreting the play, and no range is known to be healthy. The paired starting saves of
  rule 2 measure the part of it that can be measured: whether the play changes when the world does.
- *A friendship-to-denouncement ratio, or a mark for unequal treaties.* A ratio rewards having no relations at all,
  and what a treaty was worth depends on the war it ended. The facts are listed (rule 7); a trade that must be refused
  is a goal save.
- *Yields set against a modded AI's.* The baseline is the built-in AI on the same seat, and stock rules are the
  premise.

## The hard problem: one scale across maps, civilizations and victory types

A raw number from one game (score, science per turn, cities) means nothing next to the same number from another
map or civilization. The proposal is to never compare them.

1. **Starting saves, the same for every player.** A starting save is one save file: this map, these civilizations,
   this seat, this turn. Every player plays the same starting save. Terrain, civilization and neighbours are identical
   for all of them, so they cancel. Only results on the same starting save are ever compared. What stays random
   (combat results, the AIs' choices) is noise that replicates average out.
2. **Rank within the starting save, then fit a rating over starting saves.** On each starting save the players are
   ordered; the orderings feed a paired-comparison model (Bradley-Terry, as CivBench uses). A rating needs no common
   unit between starting saves, only "A did better than B on starting save 7". A player need not play every starting
   save.
3. **The built-in AI is the fixed point.** The game's own AI plays the same seat from the same starting save, many
   times, for no tokens. That gives each starting save a distribution to stand in, and gives the rating scale a
   baseline. If the AI can be run at several handicap levels on the seat, the baselines form a ladder and a rating
   reads as "plays this seat like the AI at level X", which is a unit a player understands. (Checked 2026-11-16: one
   save gives one baseline, at the save's difficulty; "What an autoplayed seat plays with" below.)
4. **One currency for the ordering.** When a run stops before the game ends, something must order the
   players. Victory types differ, so the ordering signal has to be common to all of them: an estimate of the
   seat's chance to win by any route, fitted on built-in AI-only games (CivBench's method, on our rules). Until that
   exists, a stand-in: several plain indicators reported side by side (score, technologies, policies, cities,
   population, military strength, each as a share of the game's total), with no claim that they add up.
5. **Runs, not full AI games.** Full control takes minutes per turn late in a game. A starting save comes with a run
   of K turns: an opening (turn 0 to 50), a middle game, an endgame. A starting save entered mid-game tests taking
   over a position cold, with an empty notebook; that is a different skill from playing one's own game and should be
   reported apart.

What this does not solve: a rating is relative to the pool of starting saves and players, as any rating is. Whether a
50-turn run predicts a 400-turn game is an empirical question the first data should be used to ask.

## Goal saves (the user, 2026-11-13)

A second kind of starting save, beside the open-play ones above: a save, a stated goal, a turn limit, and optionally a
constraint. Examples: "your civilization is at war; retake city X within 15 turns"; "opponent X is Y turns from a
science victory; stop them at any cost"; the same starting save again as "stop them and end with at least Z
happiness".

Why they earn their place:

- **The scale is absolute.** Passed or not, in how many turns, by what margin on the constraint. Nothing needs
  putting on one scale, and a human can sit the same test.
- **They are short**, so replicates are affordable and a pass *rate* is the natural score.
- **They isolate a capability** (a campaign, a blockade, a diplomatic rescue, an economy under pressure) that open
  play only ever shows mixed with everything else. The same starting save with and without its constraint measures
  whether the agent can hold a second objective while pursuing the first.

What a goal save must have, for the result to mean anything:

1. **A runner, not a claim.** The goal and the constraint are predicates over game state (the owner of a plot,
   a team's spaceship parts, a happiness number), read operator-side each turn. The agent's own report counts
   for nothing.
2. **A goal a human would be given.** The briefing states only what the seat's screens show at that turn (the
   victory progress screen shows a rival's spaceship parts; it does not show their production queue). It is
   handed over with the prompt, outside the game, the same words to every player.
3. **Proof it can be done, and that it is not free.** One recorded solution (a human's or an agent's) shows it
   is solvable. The built-in AI on the seat, which knows no goal, gives the rate at which it happens anyway. A
   starting save where the AI passes most runs, or nobody ever does, is dropped.
4. **An honest origin.** A starting save cut from a game that was really played is marked so; one staged by Lua (units
   placed, a war declared) is marked so too, since staged positions can be ones no game would reach.
5. **No reward for wrecking the game**, unless the goal says "at any cost". The runner records what the pass
   cost (cities, units, gold, happiness, standing) beside it, so two passes can still be told apart.

Goal saves and open-play starting saves answer different questions and are reported apart: a pass rate per starting
save and per capability here, a rating there.

## What can be measured with no scale at all

From the call ledger and the usage rows, per turn and per game, comparable anywhere:

- Orders refused, by reason; calls per turn; turns ended with a unit idle or a city building nothing.
- Units and cities lost; wars declared on the seat and by it; seeds made.
- Tokens per turn and per game, the cached share (`docs/TOKEN_ACCOUNTING.md`); wall-clock time.
- Whether the seat was still playing at the end of the run.

These say how an agent plays, not how well. They are cheap, they exist as soon as token accounting does, and a
benchmark report without them would hide what a rating costs.

## Autoplay, checked live 2026-11-16

`Game.SetAIAutoPlay(n, player)` (the call of the game's own debug panel, `steamassets/debug/game.ltp`) plays a
human seat unattended in this build. Called from the InGame state through `harness.cli lua`, single player:

- At the call the seat's slot becomes a computer slot (`PreGame.GetSlotStatus` 3 -> 1, `IsHuman` false) and the
  active player moves to an unused slot as observer (player 12 of a 12-civ game, player 2 of a duel). When the
  count runs out the seat is the active human player again and `turn(action="status")` reads an ordinary turn.
  `Game.SetAIAutoPlay(1, player)` stops a run at the next turn (the panel's "Stop AutoPlay").
- The Maya starting save (Huge, Quick, 12 civs, t243): 5 turns in 156 s, then 7 more at the same pace, no popup
  stalled it.
- A new duel (Greece on the seat against Siam, 4 city-states, Quick, Emperor, `PreGame.SetMaxTurns(20)` with the
  Time victory on, set on the single-player setup screen before `OnStart()`): autoplay from turn 0 founded the
  capital and played on; between turn 18 and turn 22 the engine set `Game.GetWinner()` 1 (Siam) and
  `Game.GetVictory()` VICTORY_TIME, 54 s after the call. Score at the end 93 to Siam's 174.
- **A win does not stop the run and puts no screen in the way.** The game state went to 2 (GAMESTATE_EXTENDED) and
  autoplay played the rest of its count (to turn 30); `EndGameMenu` was hidden when the seat came back and the harness
  read `game_over: false`. A starting save's result is read from `Game.GetWinner()` / `Game.GetVictory()` and the
  scores, and the run is stopped by the caller.

### The game needs an observer slot, or the seat is destroyed

The engine moves the human to a slot whose status is observer (`PreGame.GetSlotStatus` 4) and plays the seat as a
computer. The single-player setup screen leaves every unused slot at 4, which is why both games above worked. A
third duel, the same script with the unused slots set to closed (2) before the start, went the other way: at the
call the seat itself became the observer (slot 0 read 4, `IsHuman` stayed true, the active player stayed 0), its
Settler and Warrior were gone in the same call, the seat read dead and Siam was the winner a few turns on. No
error and no screen. With no human alive the game then ran turns by itself (turn 80 a minute later) until it was
left for the main menu.

So a runner reads the slots first and refuses a starting save with no observer slot beside the seat. A hotseat
starting save hosted with closed slots is such a starting save; whether a slot can be set to observer in a running
game is not tried.

### What an autoplayed seat plays with (the handicap)

Read on a fourth duel (Emperor, Quick, no turn limit, observer slots as the setup screen leaves them): the seat as
a human, then `Game.SetAIAutoPlay` and the same reads again in the same call, before the engine had played
anything, with Siam (an AI from the start) beside them. Turn 0, and turn 12 with a capital of 3 citizens.

| | seat, human | seat, autoplayed | Siam |
|---|---|---|---|
| Warrior, production | 26 | 20 | 20 |
| Monument, production | 26 | 19 | 19 |
| Warrior to Swordsman, gold | 55 | 20 | 20 |
| food to grow, 3 citizens | 22 | 17 | |
| unhappiness, 1 city of 3 | 6 | 5 | |
| building maintenance | 1 | 0 | |
| units supplied, turn 12 | 8 | 10 | 15 |
| happiness before any city | 9 | 9 | 15 |
| Writing, research cost | 36 | 36 | 30 |
| first policy, culture | 15 | 15 | 10 |
| Settler, production | 71 | 71 | 68 |
| at turn 0: units, technologies | 2, 1 | 2, 1 | 4, 4 |

The seat gets everything the engine gives a player that is not human, at the game's difficulty: the `AI...`
columns of the Emperor row of `HandicapInfos` (train 80, construct 75, growth 80, unhappiness 90, upgrade 40,
building cost 80). It keeps its own row for the rest, since `Player:GetHandicapType()` stays Emperor where a
real AI has `HANDICAP_AI_DEFAULT` (base happiness 15, research 85, cheaper policies). And it never had the AI's
start (two more units, three free technologies at Emperor). An autoplayed seat is neither a bare AI brain on
the human's terms nor one of the game's AI opponents: it builds and grows like them and is as unhappy and as
slow to research as the human.

What follows for the baseline:

- At Emperor the baseline builds a fifth to a quarter cheaper than any agent on the same seat. An agent that
  equals it has done more with less; the gap is the difficulty's.
- **A starting save made at Prince gives a baseline on nearly the human's terms**: Prince's `AI...` columns are 100
  except unit maintenance (85), unit supply (20) and upgrades (50).
- **One save, one baseline.** The bonus is the save's game difficulty. Lua has `Game.GetHandicapType` and no
  setter; `PreGame.SetHandicap` exists and was not tried in a running game. The ladder of point 3 would need the
  same map started once per difficulty, and then the opponents change with it.

### Another victory, and a seat that dies

The same duel at turn 13: autoplay for 25 turns, then Siam declared war with six Swordsmen and two Catapults placed by
Lua around the seat's capital (a staged position). By turn 17 the capital was taken, the seat was dead (`IsAlive`
false, no city, no unit), `Game.GetWinner()` 1, `Game.GetVictory()` VICTORY_DOMINATION, game state 2. Nothing crashed
and no screen came up. Autoplay ran to the end of its count and gave control back to the dead seat: player 0 active
and human again, `EndGameMenu` hidden, and the game ran on by itself as above (turn 57, then 78).
`turn(action="status")` read `alive: false`, `game_over: false`, the gate `turn_not_active`: a seat waiting there
would wait for good. A runner checks the winner and `IsAlive` each turn and leaves the game itself.

## The runner, and a save replays the same game

`scripts/benchmark_run.py` is the baseline's tool: load a save, read every major civilization, hand the seat over for
a run, read again, one JSON row a run, leave for the main menu (its docstring has the refusals). On the Maya
t242 starting save (Huge, Quick, Emperor, 12 civilizations) a run of 2 turns took 76 s and moved the seat's score
from 604 to 610, tenth of twelve.

**The same run a second time ended on the same ten values**, military might to the unit (3366) and gold to the coin
(15). The save holds the random stream, so the built-in AI on a starting save is one line and not a distribution until
something moves the stream. `--skip seed` takes 17 random numbers per run number from `Game.Rand` before the engine
plays. The same holds for an agent: every player on a starting save meets the same random numbers until its own orders
change which random numbers are used.

### Ten runs of 10 turns (2026-11-16)

The same starting save, `--turns 10 --runs 10`, run n after 17 n random numbers; 293 s a run, 49 minutes in all, no
run stalled. The seat (Maya, t242 to t252), value at the start, then over the ten runs:

| | start | mean | sd | least | most | sd / gain |
|---|---|---|---|---|---|---|
| score | 604 | 633.3 | 0.7 | 633 | 635 | 0.02 |
| technologies | 57 | 60.0 | 0 | 60 | 60 | 0 |
| policies | 14 | 15.0 | 0 | 15 | 15 | 0 |
| cities | 5 | 5.0 | 0 | 5 | 5 | |
| population | 70 | 74.1 | 0.3 | 74 | 75 | 0.08 |
| land (plots) | 150 | 158.9 | 0.6 | 158 | 160 | 0.06 |
| science a turn | 479 | 628.1 | 21.2 | 605 | 654 | 0.14 |
| military might | 3274 | 4594.9 | 680.8 | 3721 | 5562 | 0.52 |
| gold | 211 | 167.7 | 34.8 | 135 | 258 | 0.80 |
| happiness | 1 | 9.1 | 3.7 | 4 | 12 | 0.46 |

Place by score: tenth of twelve in nine runs, ninth in one.

What it says, for this starting save and this run only:

- **The random numbers do spread the runs**, and the spread is where one expects chance to show: what was built and
  bought (military, gold, happiness). No two runs ended alike.
- **The slow indicators hardly move between runs.** Score ends within 2 points on a gain of 29; technologies,
  policies and cities are the same number ten times. Three runs would have said as much as ten.
- So on a late starting save the baseline is nearly a point, and noise is not what makes a short run weak. What makes
  it weak is that ten turns of a 250-turn game move little: a player has to be 2 points of score away from
  633 to be told from the AI, and whether agents differ by that much in ten turns is not known.
- An opening starting save is the opposite case and is not measured: early choices compound, so the spread should be
  wider and the run worth more.

The clients' runs on this starting save (`logs/bench188/`, `logs/bench191/`) kept ledgers and token counts but no read
of the game at the end, so they cannot be set beside this table.

### Any player between the same two reads (2026-11-16)

`scripts/benchmark_run.py --save <save> --turns N --player <player> --out <rows> -- <command>` runs a command in
place of the engine: load, read, the command plays the seat and ends, read (once the seat's turn is active again),
leave. A seat loop is such a command, and so is `scripts/play_loop.py`, the scripted loop that asks no model anything.
The row has the same shape as the AI's and `--summary` puts the players of one rows file side by side.

- **Seeds.** A player's nth run on a starting save is seed n and takes 17 n random numbers before anyone plays, the
  AI's runs included. Seed n is then the same random numbers for every player until their orders part, and results can
  be paired by seed as well as pooled.
- **The notebook is part of the starting save.** `--notebook FILE` is what the seat starts with, `--notebook none` a
  seat that takes the position over cold (what the AI does), no word the notebook on disk. The player's notebook at
  the end is kept beside the rows and the one that was on disk is put back, whatever happened.
- **`--claim-wait 200`** when another client played the seat just before: its turn claim lapses 180 s after its
  last order.

Seen live with the scripted loop, 2 turns, no notebook, seed 0 (78 s): score 604 to 609 where the AI's two
2-turn runs made 610; gold 305 against the AI's 15 (the loop buys nothing), science 482 against 546. The
notebook on disk was the same bytes before and after. No model has been run through it yet.

Three seeds of the scripted loop at 10 turns all stopped at turn 246: the seat hosts the World Congress there, the
loop has no hand for a call for proposals and gave up (exit 2, about 180 s, score 610 to 614). The runner had written
those rows as played. **The run is the run's own now**: `--turns` is given for every player, a command's row says
`all_turns_played` only when the starting save is that many turns on and `turns_not_played` otherwise, and only played
runs are summarised and set side by side. So the scripted loop is no player on this starting save until it can make a
proposal, which is a fair picture of a late starting save: it asks for things a script has no answer to.

### Two models through the runner (2026-11-16)

One seed each (seed 0) of Codex (`gpt-6.1-sol`) and Grok (`grok-4.6`), effort low, no notebook, 10 turns asked
of the seat loop, on the Maya t242 starting save; the built-in AI's ten rows beside them.

| | built-in AI, 10 runs | Grok, 1 run | Codex, 1 run (9 turns) |
|---|---|---|---|
| run | played | played, 569 s | not played, 544 s |
| score | 633.3 (sd 0.7) | 631 | 631 |
| technologies | 60 | 60 | |
| population | 74.1 (0.3) | 73 | |
| science a turn | 628.1 (21.2) | 519 | |
| military might | 4594.9 (680.8) | 3483 | |
| gold | 167.7 (34.8) | 167 | |
| happiness | 9.1 (3.7) | 2 | |

- **Codex's run did not finish.** Its last `turn finish` at t251 came back `ended: true` with `discussion_pending:
  true`: a leader had come on screen between the turns. Codex reported "Ended exactly 10 turns (242 to 251)" and
  stopped. The runner waited two minutes for the seat's turn and read a game nine turns on, the seat not active. The
  row says `turns_not_played`. Grok's first `finish` at t251 ended the same way; it answered and its second reached
  t252. Hence the wording now in rule 5.
- **One run each says little**, and on this starting save the slow indicators cannot tell a player from the AI in
  ten turns anyway (above). What stands out in Grok's row is outside the AI's ten runs: science a turn five
  standard deviations below, happiness at 2 where the AI's least was 4. Whether that is the model or the seed
  needs the other seeds.
- The seat loop's cycle took about as long as before the runner (538 and 563 s), and the notebook that stood
  on disk was the same bytes after both.

### A full AI game on a Prince duel, and leaving it (2026-11-16)

A starting save hosted to rule 2 (`board-duel-prince-a-t0`: Duel, Quick, Prince, Siam on the seat against the Aztecs,
four city-states, every victory on, the unused slots as the setup screen leaves them, saved at turn 0) and
played from turn 0 to the end by the built-in AI: `--turns 400`.

- **14.6 minutes for 331 turns.** Twenty AI finishes from an opening would be about five hours, where rule 8
  wants a run valued within the hour. From a middle game it is less, and a starting save need not be a duel, but an
  opening starting save cannot have twenty.
- **It ended by Time**, at the turn limit of the speed (330): the Aztecs 1865, Siam 1571. The seat had 51
  technologies, three cities and 52 citizens. Neither AI was near any other victory. If AI finishes mostly
  end this way, the value is a comparison of score at the limit, and score comes back in through the game's own
  rule. One game; rule 8's tests have to say how often, on which sizes, and whether more civilizations or
  another limit changes it.
- **The game was not left.** The runner saw the win at turn 331, wrote its row and asked the harness to leave;
  the game played on to turn 400 (the user saw it). The harness's exit is a seat's: while the engine plays the
  seat the observer is the active player and `exit_to_main_menu` answers "this seat is not active". Runs that
  ended with the count out had the seat back and left without trouble. The runner now asks the game itself
  (`Events.ExitToMainMenu()`, seen to work under a running autoplay) when the seat's exit is refused, and stops
  with an error if the main menu does not come back.

- **The save-and-finish sequence of rule 1, live.** `--turns 20 --ai-finishes 2` on the same starting save: the
  built-in AI's turns (57 s, score 4 to 98, one city), the quick save copied under the run's name, the save loaded
  twice and finished by the AI, the game left for the main menu after each. Both AI finishes ended by Time for the
  Aztecs at turn 330 and 331, in 11.3 and 9.8 minutes. The run's value is 0 of 2, and with the game from turn 0 the
  seat has lost three of three on this starting save: outside rule 2's range, so this starting save would be dropped.

### The seat's row, and the Time victory (2026-11-17, rule 8's tests)

**A second starting save, the same end.** `board-tiny-prince-a-t0` (Tiny, Quick, Prince, Indonesia on the seat against
Assyria, Brazil and America) played from turn 0 by the built-in AI: 24.2 minutes, ended by Time at turn 330 for
America with 1766; Brazil 1117, Assyria 1145, the seat last with 827, two cities and 68 science a turn. With
the duel that is four full AI games on two Prince starting saves, every one ended by Time and the seat never first.

**Why the seat loses: it is not on the AIs' row.** Every real AI plays on `HANDICAP_AI_DEFAULT` at any
difficulty; the engine-played seat keeps the human's row. Read from `GameInfo.HandicapInfos`:

| column | Prince (the seat) | AI_DEFAULT (every AI) |
|---|---|---|
| `HappinessDefault` | 9 | 15 |
| `ResearchPercent` | 100 | 85 |
| `PolicyPercent` | 100 | 75 |
| `BuildingCostPercent`, `UnitCostPercent` (upkeep) | 100 | 75 |
| `NumCitiesUnhappinessMod`, `PopulationUnhappinessMod` | 100 | 90 |
| `ProductionFreeUnits`, per city | 5, 2 | 7, 3 |
| `RouteCostPercent` | 100 | 50 |

The `AI...` columns of the two rows are the same, so the difference is the row alone. A value measured with
the seat on the human's row is the worth of a position to a player the game handicaps against all others, and
on the two starting saves that worth was nothing.

**The setup screen cannot give a human that row.** Hosted with `PreGame.SetHandicap(0, AI_DEFAULT)` the game
came up with the seat, and the game itself, on Chieftain (`board-tiny-chieftain-a-t0`): the AI columns of a
Chieftain game make every engine-played seat pay 130%, the player alone would not, so that starting save is no use.

**In a running game it can be set, and it holds.** `PreGame.SetHandicap(seat, AI_DEFAULT)` in the loaded turn-0
save: `Player:GetHandicapType()` reads the new row at once and research costs follow at once (Writing 38 to
32); the values a player caches (base happiness 9, policy cost 15) do not, until the engine has reason to work
them out again. After twelve engine-played turns every figure of the seat was an AI's: base happiness 15, the
city-count unhappiness of one city 2.70 against Prince's 3, the second policy at 15 culture like Assyria's.
`Game.GetHandicapType()` stays Prince throughout, so nothing changes for the other players.

**So the row belongs to whoever plays the seat** (`benchmark_run.py --row ai`): a player's turns is the stock
Prince game as hosted, and in the call that hands the seat to the engine, for the baseline's run and for every
AI finish, the runner puts the seat on the AIs' row. Valuing by AI finishes then asks what a real built-in AI makes of
the position, which is what rule 1 meant. First two full AI games on the duel with it: lost by Time 1806 to
1910, and **won by Culture at turn 272**, the first Culture victory seen under autoplay.

**Time, and what switches it off.** `Game.SetVictoryValid(VICTORY_TIME, false)` reads back false (so does
`PreGame.IsVictory`) and the game still ended by Time at turn 330. `Game.GetMaxTurns()` follows
`PreGame.SetMaxTurns`; with the limit cleared as well (`--time off` does both) two AI finishes from a
turn-325 save ran past 330 and **both ended in a Diplomatic victory at turn 372** for the seat (2.2 minutes
each, the seat ahead 1968 to 1824 at the save). So without Time a game does come to a real end not long after
the old limit, and the first World Leader vote is one of the ways. A starting save hosted with Time unticked on the
setup screen has no limit from the start and needs no lever; for the starting saves already made the lever is the same
thing.

**The duel's own value: eight full AI games** (`--finish-only --ai-finishes 8 --row ai --time off --last-turn 500` on
`board-duel-prince-a-t0`, Siam on the seat against the Aztecs, 87 minutes in all):

| game | ended by | winner | turn | minutes | score, seat to Aztecs |
|---|---|---|---|---|---|
| 0 | Diplomatic | seat | 342 | 12.9 | 1882 to 1943 |
| 1 | Culture | seat | 272 | 9.0 | 1873 to 1396 |
| 2 | the stop at turn 500 | none | 500 | 20.2 | 2879 to 1787 |
| 3 | Domination | Aztecs | 126 | 3.5 | 385 to 650 |
| 4 | Diplomatic | seat | 369 | 14.2 | 2237 to 2147 |
| 5 | Diplomatic | seat | 395 | 16.8 | 2098 to 2012 |
| 6 | Domination | Aztecs | 156 | 4.3 | 496 to 1130 |
| 7 | Domination | Aztecs | 177 | 6.3 | 598 to 1222 |

- **The starting save is in rule 2's range**: the seat won 4 of the 7 games that were decided, 0.57. With the seat on
  the human's row it had lost 3 of 3.
- **Every decided game ended by a real victory, of three types**, and game 0 went to the side with the lower
  score. With Time off the value is not score by another name, which was the fifth worry of rule 8.
- A decided game took 9.6 minutes on average and between 3.5 and 16.8.
- One game in eight was not decided by turn 500, with the seat far ahead (nine cities to four). Such a game has no
  winner and is left out of the share, counted beside it like a run that did not finish; it cost twice a decided game.
- The Aztecs win early or not at all: all three of their wins were Domination before turn 180, all four of
  the seat's came after turn 270. A run that gets the seat through the first 180 turns alive is most of
  what there is to win on this starting save, which is worth knowing when a run's length is chosen.

**The terms belong in the starting save, not in the hand-over.** With the row set only when the engine takes the seat,
the built-in AI plays its turns on the AIs' row and a player plays the same run on the human's: the
difference between the two values, which is the headline, would carry the difference between two difficulty
rows. A save keeps both terms: `board-duel-prince-a-t0` loaded, the seat put on `HANDICAP_AI_DEFAULT`, Time
switched off and the limit cleared, saved again, left and loaded read the seat's row as the AIs', the turn
limit 0 and Time invalid, with the game still Prince and the seat still human. `benchmark_run.py --save <hosted>
--terms <board>` makes such a starting save. On it every run, a player's, the built-in AI's and the scripted loop's,
and every AI finish are played on one row, the same as every other player's in the game, and nothing is set
at any hand-over. The values the seat caches (base happiness 9, the first policy at 15 culture) are stale in a
turn-0 starting save until the game works them out again, the same for everyone who plays it. The eight games above
are that starting save's own value: the same two changes were made at turn 0 before the engine played.

### The scripted loop against the baseline (2026-11-17, rule 8's first test)

The scripted loop (`scripts/play_loop.py`: it founds the capital where the Settler stands, automates Workers, skips
every other unit, and for production, research and policy takes the first thing it can from a fixed list) played the
first 30 turns of `board-duel-prince-a-t0-airow`, two seeds, and each end save was finished by the AI five times
(`--player play-loop --notebook none --turns 30 --runs 2 --ai-finishes 5 --last-turn 500`).

| | seed 0 | seed 1 |
|---|---|---|
| the run | 30 turns in 216 s | 30 turns in 218 s |
| the seat at turn 30 | one city of 3, 7 technologies, 4 policies, score 112 | one city of 4, 7 technologies, 4 policies, score 120 |
| built, in order | Worker, Monument, Shrine, Granary | the same |
| policies | Tradition, Aristocracy, Oligarchy, Legalism | the same |
| place by score | 2 of 2 | 2 of 2 |
| AI finishes won | 5 of 5 | 5 of 5 |
| ended by | Diplomatic five times, turns 360 to 386 | Diplomatic three times, Culture twice, turns 346 to 425 |

**The seat won all ten games**, 12.2 minutes each; in one it won the World Leader vote with the lower score (1808 to
2133). The built-in AI playing the full AI game from turn 0 won 4 of 7 on the same starting save, and its three losses
were all conquests before turn 180; after the scripted run the Aztecs took no capital in ten games. Three losses among
seventeen games all falling to the built-in AI's side has a chance of 35 in 680, about 0.05, if the two were the same.

Read alone that puts the "lower reference point" above the baseline. It does not: the full AI games never pass through
a save, and the scripted run's AI finishes start from one made at turn 30. **The control is the baseline as rule 3
defines it**, the built-in AI for the same 30 turns, the same save and the same five AI finishes a seed (`--turns 30
--runs 2 --ai-finishes 5 --last-turn 500`, no command):

| | seed 0 | seed 1 |
|---|---|---|
| the run | 30 turns in 72 s | 30 turns in 69 s |
| the seat at turn 30 | one city of 3, 7 technologies, 3 policies, score 106, 207 gold | one city of 3, 7 technologies, 3 policies, score 102, 206 gold |
| place by score | 1 of 2 | 2 of 2 |
| AI finishes won | 5 of 5 | 4 of 5 |
| ended by | Diplomatic four times, Culture once, turns 313 to 350 | Diplomatic five times, turns 337 to 397, one of them the Aztecs' |

**Through the same save-and-finish sequence the baseline is 0.90 (9 of 10) and the scripted loop 1.00 (10 of 10)**,
13.8 and 12.2 minutes a game. Three things follow.

- *The two are not told apart, and the starting save is out of the 0.2 to 0.8 range.* After either opening the seat
  nearly always wins. Rule 8's first test failed here; what that means is said there.
- *The save-and-finish sequence is not the full AI game.* Twenty games from a turn-30 save: no conquest. Eight full AI
  games: three, and a value of 0.57. A second look for what a save might lose (`e5`, the engine playing 30 turns, a
  read of both players, save, leave, load, the same read): at turn 30 Siam and the Aztecs have not met, and units,
  gold, military might and every stance that can be read are the same after the load. So nothing readable is lost, and
  the conquests come later than turn 30 in any case. What differs is that the seat is the human's again when the save
  is made and is handed to the engine a second time by the AI finish. Whether that is the cause is not tested; the AI
  finish now records the turn the seat is first at war and the most cities it held, so the next full AI games and the
  next save-and-finish games can be set side by side. (Eight more full AI games had no conquest either: "Eight more
  full AI games" below. The gap is not shown to be real.)
- *The scripted loop is no lower reference point.* Its fixed lists are an opening a person would recognise, and at
  turn 30 it stood where the built-in AI stood (score 112 and 120 against 106 and 102, a policy more, 110 gold less).
  Thirty turns are too few for "answers only what is forced" to cost anything.

**The same random numbers are the same game, to the end.** The eight full AI games asked for a second time, on the
starting save that carries its terms, began by replaying the first run game for game: Diplomatic at turn 342 after 757
s (775 the first time), then Culture at turn 273 (272, the poll's own second). An AI finish is its number's random
numbers and nothing else, so new games of one save need new numbers (`--first-ai-finish M`), and a value can be
recomputed by anyone from the save and the numbers. (Narrowed 2026-11-22: and from the games the process played
before it. These two were the first two games of their run both times. See "A replay that was not the same game".)
The game process then died on its way back to the main menu, about
45 loads into one process, and took both games with it, since a row was written only when all its AI finishes were in;
the runner now keeps them beside the rows file as it goes (`<rows>.partial`).

### Eight more full AI games: the save-and-finish sequence is not shown to differ (2026-11-17)

Games 8 to 15 of `board-duel-prince-a-t0-airow`, the engine from turn 0
(`--finish-only --ai-finishes 8 --first-ai-finish 8 --last-turn 500`), with the war turn and the cities recorded.

| game | ended by | winner | turn | minutes | score, seat to Aztecs | the seat first at war | most cities it held |
|---|---|---|---|---|---|---|---|
| 8 | Culture | seat | 339 | 12.8 | 2398 to 1408 | never | 3 |
| 9 | Culture | seat | 313 | 16.6 | 1998 to 1351 | never | 4 |
| 10 | Diplomatic | seat | 340 | 10.6 | 1889 to 1517 | turn 124 | 3 |
| 11 | Diplomatic | seat | 342 | 12.0 | 2368 to 1559 | turn 102 | 5 |
| 12 | Diplomatic | seat | 345 | 32.4 | 1542 to 2350 | turn 147 | 3 |
| 13 | Diplomatic | seat | 335 | 26.9 | 2185 to 1870 | never | 3 |
| 14 | Diplomatic | Aztecs | 353 | 13.1 | 2019 to 2058 | turn 111 | 5 |
| 15 | Diplomatic | seat | 351 | 11.6 | 2227 to 1625 | turn 277 | 4 |

**7 of 8, and no conquest.** With the first eight the starting save's full AI games are **11 of 15 decided, 0.73
(standard error 0.11)**, three conquests in sixteen.

- *The gap between full AI games and the save-and-finish sequence was the first eight games' luck, as far as these
  games can say.* Three conquests in sixteen full AI games against none in twenty from a turn-30 save has a chance of
  0.08 if the two are the same (560 in 7140), where the first eight alone gave 0.017. In value, 11 of 15 whole against
  9 of 10 by save and AI finish for the built-in AI is no difference either. Nothing was found that a save loses, and
  now nothing is left that needs it. The engine's two segments with no save between are not worth their 90 minutes
  until a difference shows again; save-and-finish games record the war turn from here on.
- *The built-in AI's games on this starting save, all of them: 20 of 25 decided, 0.80 (standard error 0.08).* The
  starting save sits on the top edge of the range, which is where a starting save is least use: the seat is Siam,
  whose trait is its city-states, against one rival, and all 20 of the seat's wins are the World Leader vote or
  Culture.
- *War is not the danger here after the first 180 turns.* The seat was at war in five of the eight games,
  first between turn 102 and turn 277, and the end shows one city lost in all of them (game 14, four of
  its five).
- Two games took 27 and 32 minutes for the same 340 turns the others played in 12. The machine did nothing
  else that is known. A wall-clock limit on an AI finish has to allow for it.

### A Tiny starting save by save and AI finish (2026-11-17)

`board-tiny-prince-a-t0-terms`: Indonesia on the seat against Assyria, Brazil and America, the built-in AI for the
30-turn run (108 s; at turn 30 one city of 5, 9 technologies, third of four by score), then four
AI finishes (`--turns 30 --ai-finishes 4 --last-turn 500`).

| game | how it ended | turn | minutes | the seat first at war | most cities it held |
|---|---|---|---|---|---|
| 0 | the seat conquered | 178 | 8.7 | turn 81 | 3 |
| 1 | the seat conquered | 160 | 6.0 | turn 75 | 2 |
| 2 | the seat conquered | 280 | 16.9 | turn 78 | 3 |
| 3 | Brazil's Diplomatic victory | 421 | 27.5 | turn 93 | 3 |

**0 of 4.** The seat is at war by turn 93 in every game and gone by turn 280 in three. Four games do not put
the value under 0.2 (none in four happens four times in ten at 0.2), but the starting save is no candidate: where the
first duel is nearly always won, this seat is nearly always lost. A game here that runs its length is 27.5
minutes, and the one that did went to Brazil's vote with America 800 points ahead.

Two starting saves, one above the range and one very likely below it. **A starting save in the 0.2 to 0.8 range has to
be looked for**: several hosted, each screened by save and AI finish by a handful of AI finishes, the ones near the
middle kept and measured properly. A seat's start decides more than 30 turns of anyone's play, which is what rule 2's
range was written to guard against and what the first two starting saves both show.

### Three more duels screened (2026-11-17)

Three duels hosted one after another as the setup screen seeds them (random civilizations, random map), each
made to carry its terms and screened by save and AI finish: the built-in AI's 30-turn run, the save, four
AI finishes (`logs/boards/scratch/screen_boards.sh WORLDSIZE_DUEL 4 ...`, about 40 minutes a starting save with the
hosting).

| starting save | the seat against | at turn 30, score | won | ended by | the seat first at war |
|---|---|---|---|---|---|
| `board-duel-prince-b` | Poland against Mongolia | 141 to 109 | 4 of 4 | Culture three times, Diplomatic once, turns 253 to 329 | never, never, turn 250, turn 263 |
| `board-duel-prince-c` | Morocco against Sweden | 126 to 116 | 4 of 4 | Culture twice, Diplomatic twice, turns 261 to 340 | never, never, turn 195, turn 261 |
| `board-duel-prince-d` | the Celts against Austria | 103 to 106 | 2 of 4 | Austria by Culture (turn 295) and Diplomatic (361); the seat by Domination (411) and Diplomatic (378) | never, turn 284, turn 309, turn 373 |

- **`board-duel-prince-d` is the first starting save near the middle** and is the one measured next: rule 8's first
  test again, with a 100-turn run, so that the scripted loop's one city has a price if anything has.
- Starting saves b and c go the way of the first duel: the seat wins by Culture or the vote and is never in danger.
  They are dropped.
- **The seat's side has won 30 of the 37 decided duel games the built-in AI played on it**, on four starting saves,
  against the same program on the other side (a 20 of 25, b and c 4 of 4, d 2 of 4). Four starting saves cannot say
  whether that is these four starts or an edge the seat has of its own (it is player 0 and moves first, and
  it is the start the game gave the human). It matters for how many hosted starting saves a kept one costs: one in
  four so far.
- Little ends early on a duel with both sides on one row. Of the 48 such games three ended by conquest
  (turns 126 to 177, all among the first eight), and in the twenty with the war turn recorded the seat's
  first war was never before turn 102.

### The scripted loop against the baseline, again: a starting save in the 0.2 to 0.8 range, 100 turns (2026-11-17)

`board-duel-prince-d`, the Celts on the seat against Austria. The scripted loop for 100 turns, two seeds, five
AI finishes a seed, then the built-in AI through the same run
(`logs/boards/scratch/floor_anchor.sh board-duel-prince-d 100 5 logs/boards/duel-d`; a seed of the loop is 17
minutes of run and 73 of AI finishes, a seed of the built-in AI 4 and 71).

| at turn 100 | the loop, seed 0 | the loop, seed 1 | built-in AI, seed 0 | built-in AI, seed 1 |
|---|---|---|---|---|
| cities, population | 1, 12 | 1, 12 | 2, 13 | 3, 11 |
| technologies, policies | 21, 9 | 20, 9 | 20, 6 | 23, 7 |
| land, military might | 28, 263 | 29, 269 | 22, 401 | 43, 91 |
| score, seat to Austria | 266 to 606 | 262 to 403 | 336 to 438 | 459 to 447 |
| AI finishes won | 0 of 5 | 0 of 5 | 2 of 5 | 3 of 5 |
| ended by | Austria's vote four times, its Culture once, turns 356 to 370 | Austria's vote five times, turns 384 to 406 | the vote five times, turns 377 to 450 | the vote four times and the seat's conquest, turns 369 to 413 |
| the seat first at war | never in four, turn 315 | turns 259 to 380 | turns 113 to 125 | turns 292 to 315 |

**The scripted loop 0 of 10, the built-in AI 5 of 10**, 14.5 and 14.1 minutes a game.

- *The value separates them, as far as two seeds a side can say.* Five wins among twenty games all on the
  baseline's side would have a chance of 0.016 if the two were one player and the games independent (252 in
  15504). They are not independent ("How short a run" below): what stands is two seeds at 0 against two at
  0.4 and 0.6.
- *The starting save is in the 0.2 to 0.8 range*: the built-in AI is 7 of 14 by save and AI finish, 0.50 (standard
  error 0.13), and its two 100-turn seeds are 0.4 and 0.6.
- *What the loop lacked is cities.* It researches as fast as the built-in AI and adopts policies faster
  (21 and 20 technologies against 20 and 23, 9 policies against 6 and 7). It
  never builds a Settler, and the engine that takes the seat at turn 100 gets it to three to eight cities too
  late: nine of the ten games went to Austria's World Leader vote.
- *A stopped run is not a lost one.* Left at turn 100 with one city, the seat is not conquered in any of the
  ten games and is at war in six, late. On a duel the price of bad play is paid at the vote, 250 turns on,
  which is why a game costs 14 minutes whatever was played.
- Not yet known: how short a run still shows it. The loop's 30-turn opening on the first duel cost nothing, on a
  starting save that could not have shown it. The same loop at 60 and at 30 turns on this starting save is the next
  measurement; the built-in AI's fourteen games are the comparison for every run, since the baseline is the built-in
  AI from the first turn to the last whatever the run is.

### How short a run, and the seed is the unit (2026-11-18)

The scripted loop on `board-duel-prince-d` again, 60 turns and then 30, two seeds and five AI finishes a
seed (`logs/boards/scratch/floor.sh board-duel-prince-d 60 5 logs/boards/duel-d`, then 30). With the 100-turn
run, by run and seed, the score at the end of the turns (seat to Austria) and the AI finishes won:

| run | the loop, seed 0 | the loop, seed 1 | the loop | the built-in AI |
|---|---|---|---|---|
| 30 turns | 124 to 112, 3 of 5 | 124 to 108, 4 of 5 | 7 of 10 | seed 0: 103 to 106, 2 of 4 |
| 60 turns | 202 to 247, **0 of 5** | 202 to 182, **5 of 5** | 5 of 10 | |
| 100 turns | 266 to 606, 0 of 5 | 262 to 403, 0 of 5 | 0 of 10 | seed 0: 336 to 438, 2 of 5; seed 1: 459 to 447, 3 of 5 |

- **The longer the loop holds the seat, the less the seat is worth**: 0.7, 0.5, 0.0, against the built-in AI's
  0.50 over its fourteen games. Thirty turns of it cost nothing, as on the first duel.
- **The games of one seed go together.** At 60 turns the seat is the same in both seeds (one city of 9, 15
  technologies, score 202) and Austria is at 247 in one and 182 in the other; the first is lost five times
  of five and the second won five times of five. Were the ten games independent at one in two, a split that
  clean would come twice in a thousand. An AI finish's own random numbers move little: what the other side made of
  the seed's random numbers inside the run has decided most of it by the end of the turns.
- **So the seed is the unit**, and three things change. A value's error is taken over seeds (rule 6): the
  loop's 60-turn value is 0.5 with seeds at 0 and 1, which is no knowledge at all, and not 0.5 with a
  standard error of 0.16. A player's games go into seeds, not AI finishes (rule 4). And the 100-turn
  result above is two seeds a side.
- **It also says valuing by AI finishes is sharp where it matters**: one position at turn 60 is worth 0 and another
  1 with the seat the same in both. The AI finishes are not adding much noise of their own; the noise is
  in which game the seed turned out to be.
- *A seed's path, if one seed is one game.* The loop is a fixed program and a seed is fixed random numbers, so the
  three runs should be three cuts of the same two games (not checked turn by turn). Then seed 1 reads 0.8
  at turn 30, 1.0 at turn 60 and 0.0 at turn 100: handed to the built-in AI at turn 60 the seat wins five of
  five, kept by the loop for forty turns more it loses five of five. Seed 0 reads 0.6, 0.0, 0.0: lost
  between turn 30 and turn 60. That is rule 1's path, and the first time a run's turns are seen to cost a
  game.
- Next: eight more seeds each for the loop and the built-in AI at 100 turns, one AI finish a seed, so that
  the comparison stands on ten seeds a side.

### Ten seeds of the built-in AI, and a loop that did not finish (2026-11-18)

Seeds 2 to 9 of the same 100-turn run for both, one AI finish a seed
(`logs/boards/scratch/deals.sh board-duel-prince-d 100 4 1 logs/boards/duel-d`, twice).

| seed | the built-in AI at turn 100, score to Austria | its game | the scripted loop |
|---|---|---|---|
| 0 | 336 to 438 | 2 of 5 | 0 of 5 |
| 1 | 459 to 447 | 3 of 5 | 0 of 5 |
| 2 | 394 to 504 | lost, the vote, turn 398 | did not finish (stuck at turn 55) |
| 3 | 435 to 512 | lost, the vote, 413 | lost, the vote, 438 |
| 4 | 503 to 450 | lost, the vote, 408 | did not finish (54) |
| 5 | 449 to 479 | lost, the vote, 392 | did not finish (64) |
| 6 | 422 to 447 | lost, conquered, 302 | did not finish (55) |
| 7 | 449 to 448 | won, the vote, 383 | did not finish (54) |
| 8 | 560 to 401 | won, the vote, 368 | did not finish (38) |
| 9 | 502 to 490 | lost, the vote, 403 | did not finish (52) |

- **The built-in AI over ten seeds: 0.30, standard error over seeds 0.13** (seeds at 0.4, 0.6, six at 0 and two at 1).
  The starting save is in the 0.2 to 0.8 range, in its lower part; the 0.50 of its first fourteen games was two seeds
  and a screening.
- **The scripted loop did not finish seven seeds of eight**, and finished three of ten in all, each worth 0 (0 of 11
  games). By rule 5 that is its result: finished 3 of 10 runs, and a run that did not finish stands below every
  finished run. The cause was the loop's and is fixed (ccb2de9): a Warrior it had moved off a stack kept a standing
  move, a barbarian ship came beside it, the harness held the move back and the engine blocked the end of the turn on
  the unit; the loop's skip was refused as "does not block end_turn" and it asked sixteen times and stopped. The
  refusal contradicts the hold's own note and is filed (#211). The fixed loop is another player and plays seeds 0 to 7
  again.
- **By seeds the two are not yet told apart at 100 turns.** Three finished seeds at 0 against ten of which six
  are at 0 could be one player three times in ten (84 in 286). Twenty games had said 0.016. Even if the fixed
  loop loses all eight of its seeds, eight seeds at 0 against four above 0 in ten is 0.07. A starting save where the
  baseline is 0.3 has little room under it: this starting save shows a worse player slowly and would show a better one
  faster.
- **One seed is one game, as far as the run reaches.** The loop's log of its own orders is the same line
  for line in the 30-, 60- and 100-turn runs of a seed over the turns they share, and seed 8 played again
  stopped on the same turn at the same unit. So the three runs of "How short a run" are three cuts of
  two games, and a seed's path is what that section read it as.
- **What a value costs is now measured, and it is too much for a win as the only unit.** A seed is worth 0
  or 1 or near it; ten seeds give a standard error of 0.13 to 0.16; telling 0.3 from 0.0 takes about ten
  seeds a side and telling 0.5 from 0.35 about ninety. For a model a seed is a run of its tokens. The
  position at the end of the turns already says most of what the AI finishes then confirm (Austria at 247 or
  at 182 with the seat the same: 0 of 5 and 5 of 5), so the next instrument is the fitted win-chance formula of rule
  1: the built-in AI's own games, read every ten turns, give positions with their outcomes for no tokens; a
  model's seed is then valued by one read at its end of the turns, on a scale finer than won and lost, and
  AI finishes check the win-chance formula and no longer carry the value.

### The fixed loop's eight seeds (2026-11-18)

The loop with the skip fixed (ccb2de9) played seeds 0 to 7 of the 100-turn run on `board-duel-prince-d`, one
AI finish a seed, to `--last-turn 500` (`logs/boards/duel-d/floor2-t100.jsonl`; a power cut stopped the run
inside seed 5's AI finish and the same command played again took seeds 5 to 7 up).

- **It finished every run** (about 17 minutes each), second by score in all eight, one city in each.
- **1 of 8: 0.125, standard error over seeds 0.125.** Seed 4 was won by the vote at turn 375; six were lost to
  Austria's vote and seed 5 to its Culture at turn 280.
- **Against the built-in AI's 0.30 (0.13) over ten seeds the difference is 0.175 with a standard error of 0.18.**
  One seed above 0 in eight against four in ten is 0.23 by chance. Rule 8's first test is not passed at 100
  turns on this starting save by seeds, and eighteen runs were played to learn it.
- **The won seed was won from behind.** Read every ten turns (`--path 10`, the same game to the last score as the run
  without it), the seat was behind on score at every read from turn 100 to the end (by 59 to 327 points) and had 12
  delegates against 6 at turn 371, with 8 needed. Score alone does not see the route this starting save is mostly
  decided by, so a point of a path keeps allies, delegates and tourism beside the indicators.

### The win-chance formula's first fit (2026-11-18)

*Corrected by the next section: the "standard error of 0.036" below is the error over seeds alone. The
model's own error on nineteen games was 0.10 on the difference and 0.12 on each estimate (a jackknife), far
more than the leave-one-out ranges given here, and forty more games moved both estimates up by 0.08.*

Twenty full AI games of `board-duel-prince-d` played by the engine on both seats (`--finish-only --ai-finishes 20
--path 10 --last-turn 500`, 18 minutes a game, no tokens; `logs/boards/duel-d/whole-path.jsonl`). The seat won 9
of the 19 decided (thirteen by the vote, three by Domination, three by Culture; one not decided by turn 500).
Read every ten turns they are 713 positions with an outcome. `scripts/benchmark_fit.py` fits the seat's team winning
on the seat's share of each indicator less an even share; every figure below is the log loss on a game the fit
never saw, beside the base rate's 0.749.

- **What decides this starting save comes late, and it is the vote.** Over all turns score gives 0.662 and score with
  delegates and allies 0.584. By turns: before turn 60 nothing beats the base rate (score 0.762); turns 60 to
  109 score 0.719; 110 to 159 score 0.664; from 260 delegates alone 0.379. At turn 100 the seat's share of
  score was 0.56 in the games it won (0.48 to 0.68) and 0.51 in those it lost (0.44 to 0.60).
- **A model for runs is fitted on the turns runs end in** (`--turns 20 110`, 178 points): constant -0.29,
  score +10.5 a unit of share, so an even position is 0.43 and five points of share are about 0.13. On the
  built-in AI's games alone that is a thin gain (0.7325 against 0.7500), and the slope runs from 8.7 to 13.5 as one
  game or another is left out. No second feature helps in those turns.
- **Read once where a run ended, it agrees with what playing the runs out gave**, on runs it never
  saw and a player it never saw:

  | runs | seeds | estimate (error over seeds) | finished by the AI |
  |---|---|---|---|
  | built-in AI, 100 turns | 10 | 0.412 (0.034) | 0.30 (0.13) |
  | fixed loop, 100 turns | 8 | 0.138 (0.012) | 0.125 (0.125) |
  | loop before the fix, 100 turns, the three finished | 3 | 0.144 (0.032) | 0 of 11 games |
  | loop, 60 turns | 2 | 0.402 (0.094) | 0.50 (0 of 5 and 5 of 5) |
  | loop, 30 turns | 2 | 0.506 (0.012) | 0.70 |

- **The same eighteen runs now separate the two players.** 0.412 against 0.138 is 0.27 with a standard error of 0.036;
  finished by the AI they were 0.175 apart with 0.18. A read has no won-or-lost in it, so the error left is how much a
  player's positions differ from seed to seed. Rule 8's first test is passed on this starting save at 100 turns by the
  estimate; by wins it is not shown.
- **What that error leaves out.** The model's own doubt: as one game or another is left out of the fit the
  built-in AI's estimate runs from 0.36 to 0.44, the loop's from 0.08 to 0.19 and the difference from 0.24 to
  0.32, and more full AI games narrow it at 18 minutes each. The loop's positions (a share of 0.35)
  lie outside what the built-in AI's games reach at turn 100 (0.44 to 0.68), so its estimate is a line carried on;
  the 1 of 8 and 0 of 11 AI finishes won say the line is not far off. And score is not the game: the loop's one win
  came by the vote from behind on score at every read, and a player that played for delegates would be valued
  too low before turn 200. The estimate is the fine scale; AI finishes stay the check on it.
- **At 30 turns it cannot tell players apart** (0.506 with 0.012 for the loop, and the built-in AI's positions at
  turn 30 run from 0.46 to 0.55 of score): the positions have not yet moved apart, whoever plays.

### The win-chance formula on sixty games (2026-11-19)

Forty more full AI games of the starting save (AI finishes 20 to 59; the sixty took 17.4 minutes a game, 11.5 to
23.4). Of the sixty, 59 are decided and the seat won 32 (0.54, standard error 0.065): 37 by the vote (16 won), 11 by
Culture (10 won), 11 by Domination (6 won), ending between turn 248 and 437, half by 378. 2213 positions.

- **The difference held; the levels did not.** The first fit's model again (score alone, turns 20 to 110, now
  555 points): constant +0.03, score +8.8 (it was -0.29 and +10.5). The built-in AI's ten runs 0.490, the
  loop's eight 0.219: 0.27 apart as before, and both 0.08 higher. The seat won 23 of the forty new games
  against 9 of the first nineteen.
- **The range beside the first fit was not an error.** 0.36 to 0.44 does not hold 0.49, nor 0.08 to 0.19
  0.22. The fits that each leave one game out give a standard error when their spread is scaled by the number
  of games (a jackknife). On nineteen games that is 0.118 for the built-in AI's estimate, 0.125 for the loop's
  and 0.097 for the difference: the first fit's "0.27 with 0.036" was 0.27 with 0.10. On fifty-nine: 0.067,
  0.113 and 0.090, with the seeds' 0.033 together 0.096. `benchmark_fit.py --value` prints the jackknife in place
  of the range, and for two players the difference with the model's error taken on the difference itself
  (one fit values both).
- **Three times the games barely moved the difference's error** (0.097 to 0.090) though the slope's own fell
  from 6.0 to 4.1: the loop's positions (a share of 0.35) lie outside every position the built-in AI's games
  reach at turn 100 (0.42 to 0.68), so its estimate hangs on the slope, and more so the nearer it comes to
  the middle.
- **Fitted nearer the turn the runs end on, the slope is steeper.** Score alone, the 59 games:

  | turns fitted | points | slope (jackknife) | an even position | built-in AI | loop | difference (seeds, model, together) | log loss, a game left out (base rate) |
  |---|---|---|---|---|---|---|---|
  | 20 to 110 | 555 | 8.8 (4.1) | 0.51 | 0.490 | 0.219 | 0.272 (0.033, 0.090, 0.096) | 0.689 (0.707) |
  | 60 to 110 | 319 | 10.2 (4.8) | 0.48 | 0.459 | 0.169 | 0.291 (0.037, 0.080, 0.088) | 0.676 (0.707) |
  | 90 to 110 | 142 | 12.4 (6.5) | 0.45 | 0.432 | 0.118 | 0.313 (0.042, 0.066, 0.079) | 0.668 (0.706) |

  Before turn 60 score still says nothing (0.708 against 0.707); turns 110 to 159 0.619; turns 160 to 259
  with delegates and allies 0.543; from 260 0.360, delegates alone 0.437. No second feature helps before turn
  110 (techs, cities, military, the routes, the turn, score times the turn). A range of turns is a choice that
  moves a level by 0.06 to 0.10 and the difference by 0.04; the game is the unit in any range, so the model
  for a run is the one fitted on the turns about its end (90 to 110 here).
- **Score at turn 100 without a model.** Ahead on score the seat won 28 of 40, behind 4 of 19 (0.0006 by
  chance). By share: under 0.45 0 of 4, to 0.50 4 of 15, to 0.55 11 of 17, to 0.60 12 of 15, above 5 of 8.
  More a step at the even share than a line, which is some of why the slope's error is wide.
- **The played runs as rows of the fit.** A run's AI finishes are positions with outcomes too
  (`--fit` takes their rows: one point a decided AI finish, the seed left out whole), and they lie where
  players end, not where the built-in AI does. With the ten built-in AI runs (7 of 18 games won), the loop's
  eight (1 of 8) and the three before the fix (0 of 11), turns 90 to 110, 80 games: constant -0.27, score
  +13.7 (4.6), log loss 0.606 against 0.705; the built-in AI 0.413 (seeds 0.044, model 0.054), the loop 0.093
  (0.011, 0.052), the difference 0.320 (0.045, 0.056, together 0.072). The model has then seen the runs it
  values (each estimate's error still leaves a seed out); for a player after them it has not.
  `logs/boards/duel-d/estimator-t90-110-windows.json`.
- **What the two errors are.** The model's is of the starting save: paid once, in games and AI finishes already
  played, and shared by every player valued on it, so it does not shrink with a player's seeds. The seeds'
  is the player's: 0.03 to 0.045 on ten and eight seeds here. Which of two players stands higher is their
  positions' difference (the loop's share of score at turn 100 is 0.350 with 0.010 over its eight seeds, the
  built-in AI's 0.493 with 0.014 over ten) and the slope's sign; how much higher in wins carries the slope's
  error.
- **A run is the first turns of a full AI game on the same random numbers.** A 100-turn run that took 493 random
  numbers (seed 29's) ended on the position full AI game 16 (29 times 17 random numbers) showed at turn 100: every
  indicator and route of both players equal, gold apart, which is read at another moment of the turn
  (`logs/boards/duel-d/same-game-check.jsonl`). So the ten built-in AI runs are ten more first hundred turns of the
  same kind as the sixty, and they came out low: a share of 0.493 at turn 100 against the full AI games' 0.534 (0.008
  over 59), 2.6 standard errors apart, and finished by the AI 0.30 against 0.54. Nothing in how a run is played
  accounts for it. Every player gets the same seeds, so a comparison is not moved by it; a level read off ten seeds
  is.
- **What a model's value on this starting save would cost, from what is measured.** Eight seeds of a 100-turn run,
  one read each, give the player's own error as about 0.05. The only turns priced so far are late ones (the
  Maya starting save at turn 242, ten-turn cycles of the seat loop, `docs/measurements/2026-11-14-what-grows/`): 0.06
  to 0.07 dollars a turn at list prices for Sonnet 5.5 and for gpt-6.1-sol, and about 55 seconds a turn. At
  that rate a seed is 6 to 7 dollars and an hour and a half, a player's eight seeds about 50 dollars and
  twelve hours on the one machine. An opening's first turns ask less than a late turn, so this is the upper
  side; no opening run has been priced. By wins the same error would want about a hundred seeds.

### The first trial: a model's eight seeds (2026-11-19)

The first paid runs, on the user's word that day: Claude Sonnet 5.5 at low effort (`claude-sonnet-5-5`
through the Claude Code CLI, `scripts/llm_seat_loop.py`, ten-turn instances, no notebook at the start, a seat
folder of its own for every seed), the 100-turn run of the Celts duel, seeds 0 to 7, one AI finish each
(`logs/boards/duel-d/claude-sonnet-t100.jsonl`, streams beside it; `logs/boards/scratch/pilot.sh`).

| seed | the seat against Austria at turn 100 | cities | finished by the AI by the built-in AI | dollars at list |
| ---: | :--- | ---: | :--- | ---: |
| 0 | 463 to 342 | 3 | not won (Diplomatic, 342) | 1.94 |
| 1 | 549 to 490 | 2 | not won (Diplomatic, 360) | 2.25 |
| 2 | 455 to 281 | 2 | won (Domination, 271) | 2.17 |
| 3 | 426 to 526 | 2 | not won (Diplomatic, 338) | 2.12 |
| 4 | 372 to 590 | 2 | won (Diplomatic, 353) | 2.67 |
| 5 | 378 to 641 | 2 | not won (Domination, 308) | 2.70 |
| 6 | 463 to 456 | 3 | won (Diplomatic, 346) | 2.94 |
| 7 | 526 to 490 | 3 | not won (Diplomatic, 350) | 2.55 |

- **Every run finished**, eight of eight, each the starting save exactly 100 turns on.
- **By estimate** (`estimator-t90-110-windows.json`, `benchmark_fit.py --value`): **0.434**, standard error over seeds
  0.087, of the model 0.047. The built-in AI's ten seeds 0.413 (0.044, 0.054), the scripted loop's eight 0.093
  (0.011, 0.052). Sonnet less the built-in AI **+0.021 with 0.098**: not told apart. Sonnet less the loop **+0.341
  with 0.107**. **By wins** 3 of 8 (0.375) against the built-in AI's 3 of 10 and the loop's 1 of 8.
- **The player's own error is not the 0.05 the cost note gave.** That figure took the built-in AI's spread (a
  standard deviation of 0.14 a seed). Sonnet's seeds spread about 0.25: ahead by 121 and by 174 on two seeds,
  behind by 218 and by 263 on two others. Eight seeds give 0.087, and 0.05 would want about twenty-five. A
  model's seeds are not the built-in AI's seeds with a shift.
- **What it cost**: 19.34 dollars at list for the eight by the CLI's own totals (1.94 to 2.94 a seed, 0.019 to 0.029 a
  turn), not the 50 priced from late turns; a 10-turn opening run before them 0.22 (0.022 a turn); the void play 2.16.
  A run took 14 to 17 minutes on either processor (the model's seconds, not the game's). No limit of the subscription
  was met (no refusal in any stream); seed 0 moved its five-hour figure 4 points.
- **One play is void** (rule 5, the harness's doing; kept in `claude-sonnet-t100-void.jsonl`): seed 1's first
  play met turn 101 with a run that ended at 100. A leader spoke at the end of turn 99, the answer opened
  turn 100 with no word of it, and the finish sent for turn 99 ran its orders on turn 100 and ended it. Fixed
  (d52eb26: the answer names `new_turn` and leaves the turn unseen), and seed 1 was played again. The void play
  stood behind, 407 to 443, so the second play is a second play of the same random numbers by a player that is not the
  same twice; it is said here because it is the one place the operator chose.
- **Two rules came of it the same day, both the user's**: the runner closes the seat on the last turn
  (07495ba, seen live from seed 3: the last finish says `last_turn_reached`), and time is no part of a result.
- No file outside its seat folder was read by any instance (every Read, Glob and Grep of the eight seeds'
  streams).
- **A save is the same game on another processor** (one game, 2026-11-19 22:09, `cpu-check.jsonl`): the built-in AI's
  seed 0, played on the Ryzen 7 5800X3D against its row of 2026-11-17 from the processor before it. The end of the
  turns is equal to the last indicator (336 to Austria's 438, 20 technologies, 2 cities, military 401), and so is the
  game finished by the AI from it: first war at turn 114, Austria's Diplomatic victory at turn 398, 1449 to 2191.
  Every field the two rows share is equal but the seconds. The old row has no `end_point` and no path, so those are
  not compared.
- Not done: an AI finish more than one a seed, and the same seeds by a second model.

### Twenty seeds of the built-in AI, and the skip is not a new seed (2026-11-20)

The built-in AI's seeds 12 to 19 were played in the night (no tokens), so `anchor-t100.jsonl` holds twenty 100-turn
runs with one AI finish each (seeds 0 and 1 have five).

- **The twenty**: by estimate 0.415 (standard error over seeds 0.033, of the model 0.053, the 80-game fit of
  turns 90 to 110); won 5 of 20 AI finishes by each seed's first game, 9 of 28 over all. The second ten read like the
  first: score share at turn 100 of 0.491 against 0.493, estimate 0.416 against 0.413.
- **So the first ten were not an unlucky set.** Twenty runs stand at a share of 0.492 (spread 0.049) where the
  59 full AI games stand at 0.534 (0.059): 0.043 apart with a standard error of 0.013, 0.004 by permutation. It
  is the seat that is lower (score 448 against 510); Austria is the same (459 against 444).
- **It goes with the skip, not the run.** A run and a full AI game are one process: the same row, Time off, and seed
  29's run was full AI game 16 to the last indicator. What the twenty runs share is a skip of 0 to 323 random numbers.
  The eleven full AI games that skipped 29 to 319 stand at 0.492 as well (spread 0.032, won 3 of 10 decided); the 48
  that skipped 348 to 1740 stand at 0.544 (won 29 of 48). Those two sets of full AI games are 0.052 apart with 0.013,
  and no run is in that comparison.

| random numbers skipped | games (full AI games among them) | share at turn 100 | seat's score | Austria's | full AI games won |
|---|---|---|---|---|---|
| 0 to 170 | 16 (5) | 0.491 | 453 | 468 | 0 of 5 |
| 171 to 340 | 15 (6) | 0.493 | 457 | 466 | 3 of 5 |
| 341 to 520 | 6 (5) | 0.600 | 617 | 415 | 4 of 5 |
| 521 to 700 | 7 (7) | 0.558 | 561 | 441 | 5 of 7 |
| 701 to 1050 | 12 (12) | 0.535 | 507 | 443 | 7 of 12 |
| 1051 to 1400 | 12 (12) | 0.526 | 486 | 439 | 6 of 12 |
| 1401 to 1740 | 12 (12) | 0.539 | 507 | 436 | 7 of 12 |

- **It is there by turn 10.** Of the ten full AI games at skips up to 319 with a read at turn 10, six stand at
  69 to Austria's 73 and the seat is level or ahead in two. Of the 46 at skips from 348 on, three stand at 69
  to 73 and the seat is level or ahead in 43. So whatever the skip decides, it decides in the first ten turns.
- **Neighbours in skip are one game for the first turns** (67 ten-turn runs by `burn_scan.py`, a minute each,
  `burn-scan-t10.jsonl`). Read on ten indicators of both players at turn 10, skips 1 to 5 end on one position and
  skips 6 to 30 on another: twenty-five skips, one game. Every fourth skip from 300 to 400 is 26 runs and 7 positions,
  in runs of two to six. Ten runs 2000 random numbers apart (2000 to 20000) are ten positions. The opening uses few
  random numbers and most of them change nothing, so a stream moved by a few random numbers hands the opening the same
  numbers.
- **And they are still alike at turn 100.** Over the 79 games read at turn 100 (59 full AI games, 20 runs), two games within
  20 random numbers of each other differ by half the variance two far games differ by (likeness 0.48 on 45 pairs),
  within 80 random numbers 0.3 to 0.4, from 160 random numbers on nothing (-0.1 to 0.1). Neighbours in skip differ
  less than the same games in random order do (0.008).
- **So the low skips are a few games' luck, counted many times.** The 31 games at skips up to 323 are not 31 separate games of the starting save; with a likeness that reaches about a hundred random numbers they are a handful (not
  measured more closely). That they all stand low is what a small sample does, and no skip is worse than another.
- **An AI finish is not touched the same way.** The five games played on from one turn-100 save 29 random numbers
  apart (the first trial's seed 0) differ by turn 110 (the seat's score 513, 549, 480, 566, 566): a late turn uses far
  more. One save, so it is a first look.
- **What it touches.** Rule 5's unit is the seed, and seeds 17 random numbers apart are not independent games: every
  error "over seeds" given above for the built-in AI's runs and the sixty full AI games (29 apart) is too small, by
  how much is not measured. The baseline's twenty seeds say less about the starting save than twenty should. What it
  does not touch: players are set side by side on the same seeds, so the same random numbers. On seeds 0 to 7 the
  first trial's model less the built-in AI is +0.062 with 0.112 taken seed by seed (unpaired +0.020 with 0.093 on all
  twenty), and the two estimates run against each other across those seeds (correlation -0.59 on eight). A player that
  makes its own choices from turn 0 leaves the built-in AI's opening at once; its eight seeds are not shown alike or
  unlike.
- **Played after this was written**: twenty 100-turn runs at skips 340 to 663 (`burn-scan-t100.jsonl`) stand
  at a share of 0.550 at turn 100 (spread 0.050) where the twenty at skips 0 to 323 stand at 0.492: the runs
  there read like the full AI games there, as a few games' luck counted many times would have it. The proposal made
  here, seeds a thousand random numbers apart, was a guess and is withdrawn; the twenty runs 1009 apart were not
  played. What a skip does was read from the engine's own log instead (the next section).

### A skip has to be longer than a game (2026-11-20)

The first section written in plain words (the user, 2026-11-20: "be literal"); the whole document was reworded the
same day, and the words are set out at its top.

- **The generator, read from the engine's log** (`RandLog = 1` in the game's `config.ini` writes every random number
  to `Logs/RandCalls.csv` with the generator's state; switched off again after). Every chance decision of the game
  comes from one generator whose state is 32 bits: next state = 1103515245 x state + 12345 modulo 2^32, checked on
  1178 of 1178 consecutive random numbers. A skip of N moves the state N steps along that one sequence and does
  nothing else. How many steps lie between two states can be computed exactly.
- **Why close skips are one game.** Two 10-turn baseline runs at skips 6 and 7: for the first 38 random numbers of
  turn 0 each run gives a state to a different purpose than the other, and from there on the two give the same state
  to the same purpose, 1171 of 1179 random numbers, and end on one position. What takes up the difference is the
  placing of a barbarian camp: the engine picks a tile at random again and again until one is valid, 1 to 194 random
  numbers a placement, so two runs that enter that loop a few steps apart leave it on the same state. It is 813 of the
  1179 random numbers of ten turns and comes back every few turns of a game, so runs at close skips are pulled
  together again and again. That is the likeness measured above, seen directly and no longer inferred.
- **A full AI game uses 42,263 random numbers** (one full game of the built-in AI with the log on, to a Diplomatic
  victory at turn 380): 717 by turn 10, 6,705 by turn 100, 22,132 by turn 250. One game, so the size of it and
  not a bound.
- **The rule now in `scripts/benchmark_run.py`: every game has a stretch of the sequence to itself.** A stretch is
  1,000,003 random numbers, more than twenty times that game. Seed n starts 16 stretches times n along
  (`NUMBERS_A_SEED` = 16,000,048); AI finish m of a save starts (m + 1) stretches on from the state the save holds,
  and m is 0 to 14, so no finish reaches the next seed's start (a finish 15 is refused before the save is loaded). Two
  games that never use the same state cannot be pulled together by any loop. 268 seeds fit in the sequence; a seed
  past that is refused. A skip costs little: 4,000,000 random numbers took 0.2 seconds. Before this date a seed was 17
  random numbers and a finish 29; every row carries its own `skip`, so the games played stay what they are.
- **The engine's own reseed, tried and not used.** The game option "new random seed"
  (`GAMEOPTION_NEW_RANDOM_SEED`, off in the starting save) set with `Game.SetOption` and saved: each load of that
  save starts on a new state (two loads, 2.37 and 3.57 thousand million steps from the starting save's). It
  seeds from a clock, so a load is not repeatable; with the option switched off again and saved, the new state
  is held by the file (two loads, the same eight numbers). It works and would mean one save file a seed. The long
  skip gives the same from a number alone, with no files to keep, so it is the one used.
- **What the benchmark is for** (the user, 2026-11-20): a number for each player that is defined and carries a
  true uncertainty, not a way of telling players apart; two players that come out the same are a result. The
  number is the chance that the player, given the Celts on this starting save for 100 turns, has the game won
  against the built-in AI, measured by AI finishes (wins counted) or by the win-chance formula (cheaper, with
  its own error given beside it). Seeds that are separate games are what makes the uncertainty true. The spread
  of a player's runs is a fact about the player and the game; how many runs to pay for is a choice of cost.
- **Played at the new spacing, ten turns each** (`logs/boards/scratch/seedcheck-t10.jsonl`): the baseline on seeds 0
  to 5 and at seed 19's skip (304,000,912). All seven played. They end turn 10 on six different sets of figures: seeds
  1 and 3 end on the same 31 (fifteen a player and the turn). That is not the two sharing random numbers, which they
  cannot (their stretches start 32 million random numbers apart and ten turns use about 700). The figures at turn 10
  take few values: seed 2 ends on the set the old skips 6 to 30 ended on, seed 19's skip on old skip 14000's, and
  among the 67 old ten-turn runs skips 352 to 360 and skip 16000 share one. So ten turns show that the long skip loads
  and plays, and cannot show that two runs are separate games; the baseline's 100 turns can (are seeds next to each
  other more alike than seeds far apart, as they were at 17 random numbers a seed). The skip of 304 million random
  numbers added about 17 seconds to the load (65.8 seconds a run against 47.5 to 49.9), so the last seed that fits
  would add about four minutes; no skip longer than seed 19's has been tried.
- **Not done**: the baseline on the new seeds (its twenty runs at 17 random numbers a seed are fewer than twenty
  games); the win-chance formula fitted again; AI finishes at the new spacing. The AI finishes of the first trial's
  end saves at the old spacing (four more a save, seeds 0 to 6, `claude-sonnet-t100-more.jsonl`): the Celts won 14 of
  35 with the first finishes counted in; seed 7's four were not played. The scripts' options, names and row keys and
  this document were put into plain words on 2026-11-20 (files written before keep their names; see the top).

### The baseline on separate seeds (2026-11-22: twenty seeds played, five AI finishes a seed)

Started 2026-11-20 at 22:37 on the user's word ("run your in-game AI tests now, running as many games as necessary").
No tokens.

**The twenty seeds with one AI finish each, done 2026-11-21 at 05:34** (6 h 57 min: 228 s for the 100 turns, 16.3
minutes an AI finish).

- **The baseline: the Celts won 9 of the 19 decided AI finishes, 0.474, standard error over seeds 0.118.** One AI
  finish (seed 0's) reached the stop turn 500 with no victory, both civilizations alive with 14 delegates each; it
  is in no share. One of twenty is more than the 2 of 185 seen on this starting save before and is too few to say
  the rate changed. Another finish (seed 11's) was won on turn 500 itself, so the stop turn is close to where some
  games end; it stays at 500 unless the further finishes show more undecided games.
- **Seeds next to each other are no more alike than any two seeds.** `scripts/benchmark_seed_likeness.py` on the
  twenty positions at turn 100: seeds 1 apart +0.022 (0.422 of random orderings of the same runs are at least as
  alike), 2 apart -0.092 (0.834), 3 apart +0.032 (0.387). At the old spacing seeds 1 apart stood at +0.120 (0.091)
  and +0.219 (0.011). No two runs ended on the same position. This is the check point 3 was waiting for.
- **How the games ended.** 15 of the 19 by the World Leader vote, 3 by Domination, 1 by Culture. The Celts' nine
  wins: five votes, all three Dominations, the one Culture. Austria's ten wins were all the vote.
- **Against the baseline at the old spacing** (0.250 over 20 seeds, 9 of 28 games): the new figure is higher by
  0.224. The old figure's error (0.093) was too small by an amount that was not measured, because its games were
  not separate, so nothing is concluded from the difference except that the old 0.250 is not to be used.
- **The formula fitted on the earlier games, on these positions:** 0.505 estimated over the 20 seeds (standard
  error over seeds 0.033, of the formula 0.065), and 0.518 on the 19 with a decided finish, where 0.474 were won.
  They agree within the errors, on one outcome a position. On the old-spacing baseline the same formula said 0.432
  where 0.250 were won; that gap came with games that were alike and is not seen here. Five outcomes a position
  will say more.
- **The Celts at turn 100:** score 487 (sd 61, 336 to 585), 2.5 cities (1 to 4), share of score 0.518 (sd 0.051).

**The twenty seeds with five AI finishes each, done 2026-11-22 at 02:06** (finishes 1 to 4 of each end save beside
finish 0 above; 80 more games, 14.9 minutes an AI finish; `--summary logs/boards/duel-d/baseline-t100-separate.jsonl
--later logs/boards/duel-d/baseline-t100-separate-more.jsonl`).

- **The baseline: 0.438, standard error over seeds 0.071.** The mean over the twenty seeds of the share of a seed's
  decided AI finishes that the Celts won (sd over seeds 0.319). As games it is 43 of the 99 decided, 0.434. With one
  AI finish a seed it stood at 0.474 with an error of 0.118; the two agree.
- **By seed, won of decided (seeds 0 to 19):** 3/4, 1/5, 3/5, 0/5, 5/5, 1/5, 3/5, 4/5, 0/5, 1/5, 1/5, 1/5, 2/5, 3/5,
  0/5, 3/5, 3/5, 5/5, 1/5, 3/5. Five seeds went all one way (3, 8 and 14 never won; 4 and 17 always).
- **The split of the spread.** From one end of the 100 turns an AI finish varies by 0.433 (within a seed). The win
  chance the 100 turns leave varies by 0.252 from seed to seed (0.180 to 0.291 over resamplings of the seeds). Both
  are in the error: (0.252² + 0.433² / 5) / 20 is 0.071².
- **Seeds for a standard error of 0.05:** 101 at one AI finish a seed, 41 at five, 31 at fifteen. AI finishes past
  five buy little, because they do not touch the seed-to-seed part: with any number of them the count does not fall
  below 26 seeds.
- **Are twenty seeds enough for the baseline?** For the error it now has, 0.071. For 0.05 it takes 41 seeds at five
  AI finishes, twenty-one more (about 78 minutes a seed, 27 hours, no tokens). A player measured the same way on the
  same twenty seeds carries an error of about the same size, so the difference between a player and the baseline has
  an error near 0.10 on twenty seeds and near 0.07 on forty-one, unless the pairing by seed takes some of it away,
  which only a player's rows can show. **Not played (2026-11-22; the user asked what another 27 hours would be
  for).** Nothing needs them: the baseline is a defined number with a true error at twenty seeds. Twenty-one more
  would take the difference's error from 0.10 to 0.087 while the player stays at twenty seeds, since half of that
  error is the player's own, and the player's seeds are the ones paid in tokens. If a narrower error is ever wanted
  it is bought for both sides at once, on the seeds a player has played.
- **The stop turn stays at 500.** None of the 80 further AI finishes reached it undecided (1 of 100 in all, seed 0's
  finish 0). The 99 ended between turn 214 and turn 500, half of them by turn 378; one was won on turn 500 itself.
- **How the 99 ended.** 69 by the World Leader vote (Austria 46, the Celts 23), 22 by Domination (the Celts 14,
  Austria 8), 8 by Culture (the Celts 6, Austria 2).
- **The formula on five outcomes a position.** It estimates 0.505 over the twenty seeds (standard error over seeds
  0.033, of the formula 0.065) where 0.438 were won: 0.067 apart, inside the errors. Seed by seed it says little.
  Its estimates run from 0.27 to 0.77 and go with the share of the five finishes won at +0.22 (twenty seeds; not
  told from zero). The ten seeds it puts lowest won 16 of 49 (0.327, estimated 0.385), the ten it puts highest 27
  of 50 (0.540, estimated 0.625): the right direction. But its mean squared gap to a seed's share (0.1025) is no
  smaller than that of giving every seed the plain 0.438 (0.0967). The formula reads the score share at turn 100
  alone; on this starting save that does not say which positions the Celts go on to win. It has not been fitted
  again on these games. **Decided on this (the user, 2026-11-22): the number is given by AI finishes alone.**

- **The batch** (`logs/boards/scratch/baseline_separate.sh`): the built-in AI plays the 100 turns on seeds 0 to 19 at
  the new spacing with one AI finish each (`--path 10`, stopped at turn 500), rows
  `logs/boards/duel-d/baseline-t100-separate.jsonl`. One run a call, a fresh game process after ten.
- **Then four more AI finishes a seed** (`baseline_more_finishes.sh`, finishes 1 to 4 of each end save, rows
  `baseline-t100-separate-more.jsonl`), played 2026-11-21 05:34 to 2026-11-22 02:06 with two stops: the machine
  froze during seed 10 (next point), and the repository's folder was moved during seed 13, after which the exit to
  the main menu failed and the batch was started again from seed 14 (seed 13's four finishes were already in the
  rows). A file `STOP` in `logs/boards/duel-d` ends either batch before its next run.
- **A replay that was not the same game (2026-11-21).** The machine froze during seed 10's further finishes, with
  finishes 1 and 2 already played (kept in `logs/boards/duel-d/seed10-finishes-before-freeze.json`). After the reboot
  seed 10 was played again whole, from the same end save with the same finish numbers and the same skips (2,000,006
  and 3,000,009). The games were not the same. Finish 1 ended Diplomatic at turn 431 before the freeze and Domination
  at turn 436 after it; finish 2 ended Domination at turn 388 before and Diplomatic at turn 408 after. Austria won all
  four. The readings every ten turns agree at turns 100 and 111 of finish 1 and were taken at different turns after
  that, so they do not say where the games part. This goes against "the same save and the same AI finish number are
  the same game" (the rules above, and "The same random numbers are the same game, to the end"), which stood on two
  games played a second time in the same order in a fresh game process. What differed here: before the freeze the game
  process had already played seeds 8 and 9 (eight finishes) and the machine was minutes from freezing; after it, seed
  10 was the first load of a fresh process. **Not touched by this:** each
  finish is a game of the built-in AI from the same position at turn 100, so the share of finishes won and its error
  over seeds stand; the rows file holds the four finishes played after the reboot for seed 10.
- **It is what the game process played before, not the freeze (checked 2026-11-22;
  `logs/boards/duel-d/replay-check.jsonl`).** Seed 10's finish 1 was played twice more on the user's word ("you may
  run the two additional games"), from the same end save with the same skip. (1) In the process that had just played
  seeds 14 to 19 (24 loads), on a machine in good order: the Celts won, Diplomatic at turn 409. A third game, and
  already apart from the others at the reading of turn 111 (the Celts at score 493 with 20 technologies, where the
  fresh process's game has 505 and 21). (2) As the first load of a fresh process: Austria, Domination at turn 436,
  the game played after the reboot. The two were read at the same turn 19 times; 15 readings are identical in every
  figure, out to turn 420, and the other four differ in one to three figures by small amounts (a reading taken at
  another moment inside the turn) with identical readings after them. So the four games of this one save and number:
  first load of a fresh process, twice the same; after seeds 8 and 9, another; after seeds 14 to 19, a third.
  Something a game process keeps from the games it has played enters the next one. What it is has not been looked
  for. **What follows:** a save and a number are the same game only with the same games played before them in the
  process (the rule above is narrowed to say so); the two games played a second time on 2026-11-17 were the first
  two games of their run both times, which fits (whether both runs began in a fresh process was not written down).
  **What it does not change:** the baseline, its error
  and the split of the spread. **Not checked:** whether the second and later loads of a fresh process are the same
  games when the loads before them are the same (the 2026-11-17 pair says yes for the second), and whether the 100
  turns of a run are touched the same way.
- **What they are for.** (1) The baseline as a share of AI finishes won, with an error over seeds that are separate
  games. (2) The check the ten-turn runs could not give: are seeds next to each other more alike at turn 100 than
  seeds far apart (`scripts/benchmark_seed_likeness.py`: on the old rows, seeds 17 random numbers apart are alike
  at +0.12 and +0.22, which 0.091 and 0.011 of random orderings of the same runs reach). (3) The split of the spread
  into the part within a seed and the part between seeds, on games that share no random numbers
  (`--summary ... --later ...`), which is what says how many seeds and how many finishes a player's number takes
  without the formula. (4) Twenty positions at turn 100 with five outcomes each, to check the formula fitted on the
  earlier games and to fit it again.

### A Science victory, on a starting save made for it (2026-11-18)

No game in a hundred had ended by a spaceship. The user's lever (2026-11-17): put a science civilization on
the seat and the built-in AI may go for it. Two duels hosted with Korea on the seat
(`logs/boards/scratch/host_board.py ... civ=CIVILIZATION_KOREA`, and `only=` for the victory types left on;
`logs/boards/scratch/science_check.sh CIVILIZATION_KOREA board-duel-korea-a 3 2`), the engine from turn 0:

| starting save | game | ended by | winner | turn | minutes | technologies, seat to rival |
|---|---|---|---|---|---|---|
| Korea against the Aztecs, every victory but Time | 0 | Diplomatic | seat | 321 | 9.8 | 59 to 57 |
| | 1 | Domination | Aztecs | 264 | 8.7 | 46 to 49 |
| | 2 | Domination (the seat dead) | Aztecs | 145 | 3.9 | 32 to 29 |
| Korea against Portugal, only Science and Domination on | 0 | Domination | Portugal | 273 | 8.0 | 53 to 62 |
| | 1 | **Science** | seat | 426 | 12.6 | 80 to 80 |

- **`VICTORY_SPACE_RACE` is read like the others**: the game ended by itself at turn 426, `Game.GetWinner()`
  named the seat's team and `Game.GetVictory()` the spaceship, with no screen in the way. That was the last
  victory type #193 asked to see.
- *The civilization alone did not bring it.* With the vote and Culture on, Korea's one win was the World
  Leader vote at turn 321 with 59 technologies of 80; a spaceship needs a hundred turns more than a duel's
  vote leaves. On duels as hosted, Science is not a way games end.
- *Taking the earlier victories away did*, once in two. Such a starting save is a runner's check and not a
  benchmark starting save: its seat and its rules were chosen for the outcome.
- Korea was conquered in three of the five games, twice by the Aztecs, first at war at turns 65 and 154.
  A seat's civilization moves a starting save's value a long way, which is the screening's finding again.

## Not checked yet

- Whether a slot can be made an observer in a running game.
- How many AI-only games a win-chance formula needs on stock rules.
- How much one starting save's result varies between two runs of the same *agent* (the built-in AI's spread on one
  late starting save is above), and the built-in AI's spread on an opening starting save. They set how many replicates
  a starting save needs, and so what the benchmark costs.

## A first trial that also serves token accounting

Two starting saves (a turn-0 opening; the Maya save at t242 as an endgame), the same seat, each played alone from a
copy of the same save by each client under the seat loop, for a fixed run. One run each gives stage 5 of token
accounting its tables. A second run of one client on one starting save gives the first number for run-to-run
variation. The built-in AI on the same starting saves is the first baseline.
