# A benchmark of our own (design sketch)

Written 2026-11-13. A sketch to argue with, not a plan. Background: `docs/CIVBENCH.md`.

## The premise

The agent is put in a human seat of stock Civilization V. It can do only what a human can do, see only what a
human sees, and it has to play anyway: every unit, city, deal and vote, for as long as the test runs. The harness
enforces the boundary; the benchmark measures the play. The benchmark is a definition (boards, windows, scoring)
that this harness can run and that another harness holding the same boundary could run too.

## The hard problem: one scale across maps, civilizations and victory types

A raw number from one game (score, science per turn, cities) means nothing next to the same number from another
map or civilization. The proposal is to never compare them.

1. **Boards, as in duplicate bridge.** A board is one save file: this map, these civilizations, this seat, this
   turn. Every entrant plays the same board. Terrain, civilization and neighbours are identical for all of them,
   so they cancel. Only results on the same board are ever compared. What stays random (combat rolls, the AIs'
   choices) is noise that replicates average out.
2. **Rank within the board, then fit a rating over boards.** On each board the entrants are ordered; the orderings
   feed a paired-comparison model (Bradley-Terry, as CivBench uses). A rating needs no common unit between boards,
   only "A did better than B on board 7". An entrant need not play every board.
3. **The stock AI is the fixed point.** The game's own AI plays the same seat from the same board, many times,
   for no tokens. That gives each board a distribution to stand in, and gives the rating scale an anchor. If the
   AI can be run at several handicap levels on the seat, the anchors form a ladder and a rating reads as "plays
   this seat like the AI at level X", which is a unit a player understands. (Checked 2026-11-16: one save gives
   one anchor, at the save's difficulty; "What an autoplayed seat plays with" below.)
4. **One currency for the ordering.** When a window stops before the game ends, something must order the
   entrants. Victory types differ, so the ordering signal has to be common to all of them: an estimate of the
   seat's chance to win by any route, fitted on stock AI-only games (CivBench's method, on our rules). Until that
   exists, a stand-in: several plain indicators reported side by side (score, technologies, policies, cities,
   population, military strength, each as a share of the game's total), with no claim that they add up.
5. **Windows, not whole games.** Full control takes minutes per turn late in a game. A board comes with a window
   of K turns: an opening (turn 0 to 50), a middle game, an endgame. A board entered mid-game tests taking over a
   position cold, with an empty notebook; that is a different skill from playing one's own game and should be
   reported apart.

What this does not solve: a rating is relative to the pool of boards and entrants, as any rating is. Whether a
50-turn window predicts a 400-turn game is an empirical question the first data should be used to ask.

## Goal boards (the user, 2026-11-13)

A second kind of board, beside the open-play ones above: a save, a stated goal, a turn limit, and optionally a
constraint. Examples: "your civilization is at war; retake city X within 15 turns"; "opponent X is Y turns from a
science victory; stop them at any cost"; the same board again as "stop them and end with at least Z happiness".

Why they earn their place:

- **The scale is absolute.** Passed or not, in how many turns, by what margin on the constraint. Nothing needs
  homologating, and a human can sit the same test.
- **They are short**, so replicates are affordable and a pass *rate* is the natural score.
- **They isolate a capability** (a campaign, a blockade, a diplomatic rescue, an economy under pressure) that
  open play only ever shows mixed with everything else. The same board with and without its constraint measures
  whether the agent can hold a second objective while pursuing the first.

What a goal board must have, for the result to mean anything:

1. **A referee, not a claim.** The goal and the constraint are predicates over game state (the owner of a plot,
   a team's spaceship parts, a happiness number), read operator-side each turn. The agent's own report counts
   for nothing.
2. **A goal a human would be given.** The briefing states only what the seat's screens show at that turn (the
   victory progress screen shows a rival's spaceship parts; it does not show their production queue). It is
   handed over with the prompt, outside the game, the same words to every entrant.
3. **Proof it can be done, and that it is not free.** One recorded solution (a human's or an agent's) shows it
   is solvable. The stock AI on the seat, which knows no goal, gives the rate at which it happens anyway. A
   board where the AI passes most runs, or nobody ever does, is dropped.
4. **An honest origin.** A board cut from a game that was really played is marked so; one staged by Lua (units
   placed, a war declared) is marked so too, since staged positions can be ones no game would reach.
5. **No reward for wrecking the game**, unless the goal says "at any cost". The referee records what the pass
   cost (cities, units, gold, happiness, standing) beside it, so two passes can still be told apart.

Goal boards and open-play boards answer different questions and are reported apart: a pass rate per board and
per capability here, a rating there.

## What can be measured with no scale at all

From the call ledger and the usage rows, per turn and per game, comparable anywhere:

- Orders refused, by reason; calls per turn; turns ended with a unit idle or a city building nothing.
- Units and cities lost; wars declared on the seat and by it; deals made.
- Tokens per turn and per game, the cached share (`docs/TOKEN_ACCOUNTING.md`); wall-clock time.
- Whether the seat was still playing at the end of the window.

These say how an agent plays, not how well. They are cheap, they exist as soon as token accounting does, and a
benchmark report without them would hide what a rating costs.

## Autoplay, checked live 2026-11-16

`Game.SetAIAutoPlay(n, player)` (the call of the game's own debug panel, `steamassets/debug/game.ltp`) plays a
human seat unattended in this build. Called from the InGame state through `harness.cli lua`, single player:

- At the call the seat's slot becomes a computer slot (`PreGame.GetSlotStatus` 3 -> 1, `IsHuman` false) and the
  active player moves to an unused slot as observer (player 12 of a 12-civ game, player 2 of a duel). When the
  count runs out the seat is the active human player again and `turn(action="status")` reads an ordinary turn.
  `Game.SetAIAutoPlay(1, player)` stops a run at the next turn (the panel's "Stop AutoPlay").
- The Maya board (Huge, Quick, 12 civs, t243): 5 turns in 156 s, then 7 more at the same pace, no popup stalled it.
- A new duel (Greece on the seat against Siam, 4 city-states, Quick, Emperor, `PreGame.SetMaxTurns(20)` with the
  Time victory on, set on the single-player setup screen before `OnStart()`): autoplay from turn 0 founded the
  capital and played on; between turn 18 and turn 22 the engine set `Game.GetWinner()` 1 (Siam) and
  `Game.GetVictory()` VICTORY_TIME, 54 s after the call. Score at the end 93 to Siam's 174.
- **A win does not stop the run and puts no screen in the way.** The game state went to 2 (GAMESTATE_EXTENDED) and
  autoplay played the rest of its count (to turn 30); `EndGameMenu` was hidden when the seat came back and the
  harness read `game_over: false`. A board's result is read from `Game.GetWinner()` / `Game.GetVictory()` and the
  scores, and the run is stopped by the caller.

### The game needs an observer slot, or the seat is destroyed

The engine moves the human to a slot whose status is observer (`PreGame.GetSlotStatus` 4) and plays the seat as a
computer. The single-player setup screen leaves every unused slot at 4, which is why both games above worked. A
third duel, the same script with the unused slots set to closed (2) before the start, went the other way: at the
call the seat itself became the observer (slot 0 read 4, `IsHuman` stayed true, the active player stayed 0), its
Settler and Warrior were gone in the same call, the seat read dead and Siam was the winner a few turns on. No
error and no screen. With no human alive the game then ran turns by itself (turn 80 a minute later) until it was
left for the main menu.

So a runner reads the slots first and refuses a board with no observer slot beside the seat. A hotseat board
hosted with closed slots is such a board; whether a slot can be set to observer in a running game is not tried.

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

What follows for the anchor:

- At Emperor the anchor builds a fifth to a quarter cheaper than any agent on the same seat. An agent that
  equals it has done more with less; the gap is the difficulty's.
- **A board made at Prince gives an anchor on nearly the human's terms**: Prince's `AI...` columns are 100 except
  unit maintenance (85), unit supply (20) and upgrades (50).
- **One save, one anchor.** The bonus is the save's game difficulty. Lua has `Game.GetHandicapType` and no
  setter; `PreGame.SetHandicap` exists and was not tried in a running game. The ladder of point 3 would need the
  same map started once per difficulty, and then the opponents change with it.

### Another victory, and a seat that dies

The same duel at turn 13: autoplay for 25 turns, then Siam declared war with six Swordsmen and two Catapults
placed by Lua around the seat's capital (a staged position). By turn 17 the capital was taken, the seat was
dead (`IsAlive` false, no city, no unit), `Game.GetWinner()` 1, `Game.GetVictory()` VICTORY_DOMINATION, game
state 2. Nothing crashed and no screen came up. Autoplay played out its count and gave control back to the dead
seat: player 0 active and human again, `EndGameMenu` hidden, and the game ran on by itself as above (turn 57,
then 78). `turn(action="status")` read `alive: false`, `game_over: false`, the gate `turn_not_active`: a seat
waiting there would wait for good. A runner checks the winner and `IsAlive` each turn and leaves the game itself.

## The runner, and a save replays the same game

`scripts/board_run.py` is the anchor's tool: load a save, read every major civilization, hand the seat over for
a window, read again, one JSON row a run, leave for the main menu (its docstring has the refusals). On the Maya
t242 board (Huge, Quick, Emperor, 12 civilizations) a window of 2 turns took 76 s and moved the seat's score
from 604 to 610, tenth of twelve.

**The same run a second time ended on the same ten values**, military might to the unit (3366) and gold to the
coin (15). The save holds the random stream, so the stock AI on a board is one line and not a distribution until
something moves the stream. `--burn run` takes 17 draws per run number from `Game.Rand` before the engine plays.
The same holds for an agent: every entrant on a board meets the same dice until its own orders change what is
rolled.

### Ten runs of a 10-turn window (2026-11-16)

The same board, `--turns 10 --runs 10`, run n after 17 n draws; 293 s a run, 49 minutes in all, no run stalled.
The seat (Maya, t242 to t252), value at the start, then over the ten runs:

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

What it says, for this board and this window only:

- **The draws do spread the runs**, and the spread is where one expects dice: what was built and bought
  (military, gold, happiness). No two runs ended alike.
- **The slow indicators hardly move between runs.** Score ends within 2 points on a gain of 29; technologies,
  policies and cities are the same number ten times. Three runs would have said as much as ten.
- So on a late board the anchor is nearly a point, and noise is not what makes a short window weak. What makes
  it weak is that ten turns of a 250-turn game move little: an entrant has to be 2 points of score away from
  633 to be told from the AI, and whether agents differ by that much in ten turns is not known.
- An opening board is the opposite case and is not measured: early choices compound, so the spread should be
  wider and the window worth more.

The clients' runs on this board (`logs/bench188/`, `logs/bench191/`) kept ledgers and token counts but no read
of the board at the end, so they cannot be set beside this table. The next piece is the same two reads around a
seat-loop run.

## Not checked yet

- A spaceship, culture or diplomatic win under autoplay (Time and Domination are seen).
- Whether a slot can be made an observer in a running game, and whether `PreGame.SetHandicap` in a running game
  moves the seat's own row.
- How many AI-only games a win estimator needs on stock rules.
- How much one board's result varies between two runs of the same *agent* (the stock AI's spread on one late
  board is above), and the stock AI's spread on an opening board. They set how many replicates a board needs,
  and so what the benchmark costs.
- An agent's result on a board read by the referee: the runner's two reads around a seat-loop run.

## A pilot that also serves token accounting

Two boards (a turn-0 opening; the Maya save at t242 as an endgame), the same seat, each played alone from a copy
of the same save by each client under the seat loop, for a fixed window. One run each gives stage 5 of token
accounting its tables. A second run of one client on one board gives the first number for run-to-run variation.
The stock AI on the same boards is the first anchor.
