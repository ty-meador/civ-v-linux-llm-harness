# A benchmark of our own (design sketch)

Written 2026-11-13 as a sketch to argue with. Since 2026-11-16 it opens with rules (version 0) and a list of the
tests that would overturn them; the rest is the argument and what was measured. Background: `docs/CIVBENCH.md`.

## The premise

The agent is put in a human seat of stock Civilization V. It can do only what a human can do, see only what a
human sees, and it has to play anyway: every unit, city, deal and vote, for as long as the test runs. The harness
enforces the boundary; the benchmark measures the play. The benchmark is a definition (boards, windows, scoring)
that this harness can run and that another harness holding the same boundary could run too.

## Rules, version 1 (2026-11-17)

The user left the rules to be worked out (2026-11-16). These are the rules the measurements so far support. Each
says what is seen and what is not, and rule 8 lists the tests that would overturn them. The sections after this
one are the argument and the measurements; where they differ from a rule, the rule is the later thought.

**What version 1 changed**, after the first night of rule 8's tests (36 games played out, "The seat's row" and
"The floor against the anchor" below):

- A board carries its terms: the seat is on the row every AI plays on, and there is no Time victory (rule 2).
  At Prince as hosted the engine-played seat lost every whole game, all by Time.
- A board's band is measured the way a run is valued, through the window, the save and the continuations
  (rule 2). The first duel is 0.57 by whole games and 0.90 through the chain.
- A continuation with no victory by a stop turn is not decided and is in no share (rule 1).
- A value is given with its standard error and over all of an entrant's games on the board (rule 6).
- Rule 8's first test failed on the first board and is open: see there. Neither of the first two boards is
  in the band (the duel 0.90, a Tiny board 0 of 4), so the next work is finding one.

**1. A run is worth what the game was worth when the entrant's turns were over.** An entrant plays a seat for a
window of turns. Then the game's own AI plays that seat and every other to the end of the game, several times
(continuations). The run's value is the share of the continuations the seat wins. Nothing else orders entrants.

- A win is the one thing every victory type has in common. Score is not: it counts size. The Maya seat of the
  t242 board holds 6.4% of the living civilizations' score and is tenth of twelve with 8.6% of their
  technologies, and a fast four-city science win scores below a slow conquest.
- It is the estimate of point 4 below without a fitted model: the position is valued by what one fixed player
  makes of it, the same player for every entrant. It does not measure whether the entrant could have finished
  the game itself. Every continuation is also a row for the fitted estimator, should one be wanted later.
- A seat dead or a game lost inside the window is 0, a game won inside it is 1, with no continuation.
- It is a probability, not one game's result: one continuation is a coin, twenty are an estimate. Where that is
  still too coarse the fitted estimator is the finer instrument, and the continuations are what it is fitted on.
- **The path, on a long window.** The referee can save at fixed turns inside the window and value each save the
  same way. The path says whether a lead was built early and kept, thrown away, or won back from behind. The
  headline stays the value at the window's end: an average over the path would pay for a lead that was then
  lost.
- **A continuation is stopped at a turn the board names** (500 at Quick speed so far). With no victory by
  then it is not decided: it is in no share and is counted beside the value. One whole game in eight on the
  first duel ended that way, the seat far ahead.
- Seen: 36 games played out with no screen in the way, the winner read from `Game.GetWinner()`, ended by
  Diplomatic (22), Culture (5), Domination (3) and Time (5, before it was switched off), one stopped at turn
  500; the chain of window, save, load and continuation; a continuation from turn 30 of a duel in 12 to 14
  minutes. Not seen: a Science victory.

**2. Boards.** A board is a save, a seat, a window and a number of deals.

- Hosted from the single-player setup screen: Prince, the unused slots as the screen leaves them (the observer
  slot autoplay needs), stock rules, no mod. Small maps (Duel to Small) at Quick speed, so that a continuation
  is minutes.
- **Then made to carry its terms** (`board_run.py --terms`): the seat is put on the row every AI of the game
  plays on (`HANDICAP_AI_DEFAULT`; the human's Prince row has base happiness 9 against 15, research at 100%
  against 85%, policies at 100% against 75%), and the Time victory is switched off with the turn limit cleared.
  The save keeps both. Every player of the game is then on one row, whoever plays the seat: an entrant, the
  stock AI and the scripted floor play the same window on the same terms, and so does every continuation. The
  entrant plays a game a little kinder than Prince; what is compared is always two players of the same seat.
- Without Time a game runs to a victory someone took: on the first duel the World Leader vote, a Culture
  victory or a conquest, between turn 126 and turn 425.
- Three kinds by where the window sits: an opening (from turn 0), a middle game, a late game. They are reported
  apart. A middle or late board is cut from a game the stock AI played alone to that turn: an honest origin, no
  one's notebook, and as many boards as wanted for no tokens.
- **A board is kept only if the anchor's value on it is between 0.2 and 0.8**, the anchor's value being
  measured as any run's is: the stock AI plays the window, the game is saved, and the save is played out. On a
  board the seat always or never wins, no window can show anything. Whole games from the board's first turn
  are not the measure: the first duel is 0.57 by eight whole games and 0.90 through the chain (below), and so
  it is out. With ten decided games a value near 0.5 is known to 0.16 either way; a board near an edge of the
  band needs more before it is kept or dropped.
- **The seats of one map.** Where the same map can be started from each of its seats (a fixed map seed on the
  setup screen, not yet tried), every seat is a board, and an entrant's spread over the seats of one map is
  reported beside its mean: the same world from the river valley and from the tundra. Seats outside the band
  above are still dropped.
- Goal boards (below) are the second kind of test, pass or fail against a referee, and are reported apart.
  One family of them comes in pairs: **the same save with and without one staged event** the seat can see (an
  army gathering at the border, a neighbour two parts from a spaceship, a city-state ally under siege). What
  the entrant builds, moves and signs in the turns after is counted from the ledger on both boards. The
  difference between the two is its reaction, measured without anyone judging what its strategy was, and the
  referee's predicate (the city still held at the end) says whether the reaction was enough.

**3. Entrants.** An entrant is a client, a model, an effort setting, a harness version and a prompt file. It has
the nine tools and one seat: no shell on the game's machine, no save file, no Lua. It starts with no notebook;
what it writes during the window is its own. Two entrants are always on a board beside the models: the stock AI
playing the window (`stock-ai`, the anchor) and a scripted loop that answers only what the game forces, from
fixed lists (`scripts/play_loop.py`). The loop was meant as a floor and is not one by construction: on the
first duel its opening (Worker, Monument, Shrine, Granary, four Tradition policies, the Warrior at home) was
worth as much as the stock AI's. It is reported as a second fixed player, not as a lower bound.

**4. Deals.** An entrant's nth run on a board is deal n: 17 n draws from the game's random stream before the
window, the same for every entrant, since a save otherwise replays the same game. A continuation takes its own
draws when it starts. At least three deals an entrant and board; whether a model's own variation asks for more
is not known.

**5. A run counts whatever happened.**

- The window is the referee's: the board must be that many turns on.
- **DNF is a result of its own** (the user, 2026-11-16). A run that stopped short (gave up, ran out of time or
  quota, the client died) did not finish. It has no value and is not averaged in as a nought: a seat left
  after nine good turns and a seat played into a lost position are different things and a mean would hide
  which happened. A DNF is counted and shown beside the value, as in a race.
- **A DNF stands below every finished run** wherever runs are ordered. Otherwise stopping would be worth the
  anchor's value and a weak entrant would do best by not playing. Where one number is needed the value is also
  given with every DNF as 0, and says so.
- A seat that dies inside the window, or a game lost there, is finished: it was played, and it is worth 0.
- A run is void and played again only when it was not the entrant's doing: the game process died, the engine
  stalled or did not take the seat, the harness answered with an internal error. The ledger says which.
- One wall-clock limit a window for every entrant. Tokens are counted, not capped.
- **The entrant is told the turn at which the window is over**, in the same words for all: "the window is over
  when turn N is yours". Told "play 10 turns", Codex ended its tenth turn, got a leader on screen between the
  turns, and stopped there with the board nine turns on; Grok answered the leader and reached the turn (both
  2026-11-16, below). What the turns between ask is part of the window.

**6. What is reported.**

- Per board and entrant: the value over all the decided games of its finished deals (won W of N) with its
  standard error, sqrt(p (1 - p) / N), the anchor's and the scripted loop's beside it, each deal's own value,
  and the number of deals not finished. Ten games tell 1.0 from 0.6 and not 0.9 from 0.7; a difference of 0.15
  between two entrants on one board needs about ninety games each. That is the price of a win as the unit,
  it is paid in machine hours and not in tokens, and it is the reason the fitted estimator of rule 1 stays on
  the list.
- The headline has two parts and neither is given without the other: **the share of windows finished**, and
  over those **the mean over boards of the entrant's value less the anchor's**, per kind of board, with an
  interval from resampling boards. It reads "finished 8 of 9 windows, and left the seat this much more (or
  less) likely to win than the game's own AI did with the same turns". The same difference with every DNF as
  0 is printed under it.
- A fitted rating over entrants (Bradley-Terry) only once there are entrants enough; the headline needs none.
- Always beside it: the share of windows played, tokens and seconds a turn, orders refused ("What can be
  measured with no scale at all"). The indicators and the parts of the score are diagnosis, never the ordering.
- Every row carries the harness version, the runtime version, the board and the deal.

**7. Beside the value: how the seat was played.** Read by the referee at the two ends of the window and counted
from the ledger, reported per entrant next to the anchor's figure on the same board, and never part of the
ordering. They explain a value; they do not replace it.

- *What the empire turns its yields into.* Food, production, gold, science, culture and faith a turn at both
  ends; gold on hand at the end against income (on the t242 board the scripted loop ended two turns with 305
  gold where the AI had spent down to 15); turns a city built nothing and turns a unit stood with no order; the
  parts of the score (cities, population, land, wonders, technologies, policies), so that "grew wider" and
  "advanced" can be told apart.
- *Where the seat stands with the others.* Wars it is in and who declared them, declarations of friendship,
  denouncements given and received, city-state allies, at both ends; cities and units lost; what it gave and
  got in each deal and peace treaty, listed, not scored.
- *What the play cost.* Tokens and seconds a turn, calls a turn, orders refused by reason, the share of windows
  played.

**8. What would overturn this, to be tested before any model's tokens are spent on it.** Where each test
stands after the night of 2026-11-17:

- *The value cannot tell a floor from the anchor.* **Failed on the first board, open.** On the duel's opening
  (30 turns from turn 0, two deals, five continuations a deal) the scripted loop's value is 1.00 (10 of 10)
  and the anchor's 0.90 (9 of 10). Nothing separates them, and both are outside the band: after either
  opening the seat nearly always wins, mostly the World Leader vote. This says the board and window were
  wrong (a duel leaves the seat one rival and few ways to lose, and 30 opening turns of sitting still cost
  nothing there), and it does not yet say the valuation is right. The test is to be repeated on a board that is
  in the band through the chain, with a window in which sitting still has a price; until one separates them
  no model's value means anything.
- *Continuations are too slow or too noisy.* **Slow and noisy, both measured.** From an opening a duel
  continuation is 12 to 14 minutes, and a whole Tiny game to turn 330 took 24. Five an hour is a value known
  to about 0.2. "Valued within the hour" holds only for late boards (a continuation from turn 325 took 2.2
  minutes). Rule 6 now gives the standard error and says what a difference costs.
- *No board is undecided.* **Answered for the row, open for the band.** The seat on the human's Prince row
  lost every whole game; on the AIs' row the duel is 0.57 by whole games. Through the chain the same board is
  0.90, out of the band from the other side, and the first Tiny board is 0 of 4 through the chain, the seat
  conquered in three. No board is in the band yet; boards have to be hosted in number and screened.
- *The save in between.* **Holds as a mechanism, and changes the result.** Twenty games played out from a
  turn-30 save had no conquest; eight whole games on the same board had three, all by the Aztecs before turn
  180. At turn 30 the two have not met, and what can be read of both players is the same before the save and
  after the load. Either it is chance (three conquests in 28 games all falling among those eight: 0.017) or
  the second hand-over matters: at the save the seat is the human's again, and a continuation hands it to the
  engine anew. It does not make the comparison between entrants unfair, since every run goes through the same
  chain, but it is why the band is measured through the chain, and it is not explained.
- *Continuations end by score.* **Answered.** With Time off every decided game ended by a victory someone
  took, and in five of them the winner had the lower score.

**Considered and left out** (suggestions weighed 2026-11-16):

- *A progress-weighted average of standing over the whole game as the result.* The path of rule 1 is taken from
  it; the average is not, and neither is standing measured as a share of score or against the leader of the
  moment, since score counts size.
- *A count of strategic pivots, with a healthy range.* Nothing operator-side can say what a strategy was or
  when it changed without interpreting the play, and no range is known to be healthy. The paired boards of
  rule 2 measure the part of it that can be measured: whether the play changes when the world does.
- *A friendship-to-denouncement ratio, or a mark for unequal treaties.* A ratio rewards having no relations
  at all, and what a treaty was worth depends on the war it ended. The facts are listed (rule 7); a deal that
  must be refused is a goal board.
- *Yields set against a modded AI's.* The anchor is the stock AI on the same seat, and stock rules are the
  premise.

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
of the board at the end, so they cannot be set beside this table.

### Any entrant between the same two reads (2026-11-16)

`scripts/board_run.py --save <save> --turns N --label <entrant> --out <rows> -- <command>` runs a command in place of the
engine: load, read, the command plays the seat and ends, read (once the seat's turn is active again), leave. A
seat loop is such a command, and so is `scripts/play_loop.py`, the scripted loop that asks no model anything.
The row has the same shape as the AI's and `--summary` puts the entrants of one rows file side by side.

- **Deals.** An entrant's nth run on a board is deal n and takes 17 n draws before anyone plays, the AI's runs
  included. Deal n is then the same dice for every entrant until their orders part, and results can be paired
  by deal as well as pooled.
- **The notebook is part of the board.** `--notebook FILE` is what the seat starts with, `--notebook none` a seat
  that takes the position over cold (what the AI does), no word the notebook on disk. The entrant's notebook at
  the end is kept beside the rows and the one that was on disk is put back, whatever happened.
- **`--claim-wait 200`** when another client played the seat just before: its turn claim lapses 180 s after its
  last order.

Seen live with the scripted loop, 2 turns, no notebook, deal 0 (78 s): score 604 to 609 where the AI's two
2-turn runs made 610; gold 305 against the AI's 15 (the loop buys nothing), science 482 against 546. The
notebook on disk was the same bytes before and after. No model has been run through it yet.

Three deals of the scripted loop at 10 turns all stopped at turn 246: the seat hosts the World Congress there,
the loop has no hand for a call for proposals and gave up (exit 2, about 180 s, score 610 to 614). The runner
had written those rows as played. **The window is the run's own now**: `--turns` is given for every entrant, a
command's row says `window_played` only when the board is that many turns on and `window_not_played`
otherwise, and only played windows are summarised and set side by side. So the scripted loop is no entrant on
this board until it can make a proposal, which is a fair picture of a late board: it asks for things a script
has no answer to.

### Two models through the runner (2026-11-16)

One deal each (deal 0) of Codex (`gpt-6.1-sol`) and Grok (`grok-4.6`), effort low, no notebook, 10 turns asked
of the seat loop, on the Maya t242 board; the stock AI's ten rows beside them.

| | stock AI, 10 runs | Grok, 1 run | Codex, 1 run (9 turns) |
|---|---|---|---|
| window | played | played, 569 s | not played, 544 s |
| score | 633.3 (sd 0.7) | 631 | 631 |
| technologies | 60 | 60 | |
| population | 74.1 (0.3) | 73 | |
| science a turn | 628.1 (21.2) | 519 | |
| military might | 4594.9 (680.8) | 3483 | |
| gold | 167.7 (34.8) | 167 | |
| happiness | 9.1 (3.7) | 2 | |

- **Codex's run is a DNF.** Its last `turn finish` at t251 came back `ended: true` with
  `discussion_pending: true`: a leader had come on screen between the turns. Codex reported "Ended exactly 10
  turns (242 to 251)" and stopped. The referee waited two minutes for the seat's turn and read a board nine
  turns on, the seat not active. The row says `window_not_played`. Grok's first `finish` at t251 ended the
  same way; it answered and its second reached t252. Hence the wording now in rule 5.
- **One run each says little**, and on this board the slow indicators cannot tell an entrant from the AI in
  ten turns anyway (above). What stands out in Grok's row is outside the AI's ten runs: science a turn five
  standard deviations below, happiness at 2 where the AI's least was 4. Whether that is the model or the deal
  needs the other deals.
- The seat loop's cycle took about as long as before the runner (538 and 563 s), and the notebook that stood
  on disk was the same bytes after both.

### A whole game on a Prince duel, and leaving it (2026-11-16)

A board hosted to rule 2 (`board-duel-prince-a-t0`: Duel, Quick, Prince, Siam on the seat against the Aztecs,
four city-states, every victory on, the unused slots as the setup screen leaves them, saved at turn 0) and
played from turn 0 to the end by the stock AI: `--turns 400`.

- **14.6 minutes for 331 turns.** Twenty continuations from an opening would be about five hours, where rule 8
  wants a run valued within the hour. From a middle game it is less, and a board need not be a duel, but an
  opening board cannot have twenty.
- **It ended by Time**, at the turn limit of the speed (330): the Aztecs 1865, Siam 1571. The seat had 51
  technologies, three cities and 52 citizens. Neither AI was near any other victory. If continuations mostly
  end this way, the value is a comparison of score at the limit, and score comes back in through the game's own
  rule. One game; rule 8's tests have to say how often, on which sizes, and whether more civilizations or
  another limit changes it.
- **The game was not left.** The runner saw the win at turn 331, wrote its row and asked the harness to leave;
  the game played on to turn 400 (the user saw it). The harness's exit is a seat's: while the engine plays the
  seat the observer is the active player and `exit_to_main_menu` answers "this seat is not active". Runs that
  ended with the count out had the seat back and left without trouble. The runner now asks the game itself
  (`Events.ExitToMainMenu()`, seen to work under a running autoplay) when the seat's exit is refused, and stops
  with an error if the main menu does not come back.

- **The chain of rule 1, live.** `--turns 20 --continue 2` on the same board: the stock AI's window (57 s,
  score 4 to 98, one city), the quick save copied under the run's name, the save loaded twice and played out,
  the game left for the main menu after each. Both continuations ended by Time for the Aztecs at turn 330 and
  331, in 11.3 and 9.8 minutes. The run's value is 0 of 2, and with the game from turn 0 the seat has lost
  three of three on this board: outside rule 2's band, so this board would be dropped.

### The seat's row, and the Time victory (2026-11-17, rule 8's tests)

**A second board, the same end.** `board-tiny-prince-a-t0` (Tiny, Quick, Prince, Indonesia on the seat against
Assyria, Brazil and America) played from turn 0 by the stock AI: 24.2 minutes, ended by Time at turn 330 for
America with 1766; Brazil 1117, Assyria 1145, the seat last with 827, two cities and 68 science a turn. With
the duel that is four whole games on two Prince boards, every one ended by Time and the seat never first.

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
on the two boards that worth was nothing.

**The setup screen cannot give a human that row.** Hosted with `PreGame.SetHandicap(0, AI_DEFAULT)` the game
came up with the seat, and the game itself, on Chieftain (`board-tiny-chieftain-a-t0`): the AI columns of a
Chieftain game make every engine-played seat pay 130%, the entrant alone would not, so that board is no use.

**In a running game it can be set, and it holds.** `PreGame.SetHandicap(seat, AI_DEFAULT)` in the loaded turn-0
save: `Player:GetHandicapType()` reads the new row at once and research costs follow at once (Writing 38 to
32); the values a player caches (base happiness 9, policy cost 15) do not, until the engine has reason to work
them out again. After twelve engine-played turns every figure of the seat was an AI's: base happiness 15, the
city-count unhappiness of one city 2.70 against Prince's 3, the second policy at 15 culture like Assyria's.
`Game.GetHandicapType()` stays Prince throughout, so nothing changes for the other players.

**So the row belongs to whoever plays the seat** (`board_run.py --row ai`): an entrant's window is the stock
Prince game as hosted, and in the call that hands the seat to the engine, for the anchor's window and for every
continuation, the referee puts the seat on the AIs' row. The valuation then asks what a real stock AI makes of
the position, which is what rule 1 meant. First two whole games on the duel with it: lost by Time 1806 to
1910, and **won by Culture at turn 272**, the first Culture victory seen under autoplay.

**Time, and what switches it off.** `Game.SetVictoryValid(VICTORY_TIME, false)` reads back false (so does
`PreGame.IsVictory`) and the game still ended by Time at turn 330. `Game.GetMaxTurns()` follows
`PreGame.SetMaxTurns`; with the limit cleared as well (`--time off` does both) two continuations from a
turn-325 save ran past 330 and **both ended in a Diplomatic victory at turn 372** for the seat (2.2 minutes
each, the seat ahead 1968 to 1824 at the save). So without Time a game does come to a real end not long after
the old limit, and the first World Leader vote is one of the ways. A board hosted with Time unticked on the
setup screen has no limit from the start and needs no lever; for the boards already made the lever is the same
thing.

**The duel's own value: eight whole games** (`--value-only --continue 8 --row ai --time off --last-turn 500` on
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

- **The board is in rule 2's band**: the seat won 4 of the 7 games that were decided, 0.57. With the seat on
  the human's row it had lost 3 of 3.
- **Every decided game ended by a real victory, of three types**, and game 0 went to the side with the lower
  score. With Time off the value is not score by another name, which was the fifth worry of rule 8.
- A decided game took 9.6 minutes on average and between 3.5 and 16.8.
- One game in eight was not decided by turn 500, with the seat far ahead (nine cities to four). Such a game
  has no winner and is left out of the share, counted beside it like a DNF; it cost twice a decided game.
- The Aztecs win early or not at all: all three of their wins were Domination before turn 180, all four of
  the seat's came after turn 270. A window that gets the seat through the first 180 turns alive is most of
  what there is to win on this board, which is worth knowing when a window's length is chosen.

**The terms belong in the board, not in the hand-over.** With the row set only when the engine takes the seat,
the stock AI plays its window on the AIs' row and an entrant plays the same window on the human's: the
difference between the two values, which is the headline, would carry the difference between two difficulty
rows. A save keeps both terms: `board-duel-prince-a-t0` loaded, the seat put on `HANDICAP_AI_DEFAULT`, Time
switched off and the limit cleared, saved again, left and loaded read the seat's row as the AIs', the turn
limit 0 and Time invalid, with the game still Prince and the seat still human. `board_run.py --save <hosted>
--terms <board>` makes such a board. On it every window, an entrant's, the stock AI's and the scripted floor's,
and every continuation are played on one row, the same as every other player's in the game, and nothing is set
at any hand-over. The values the seat caches (base happiness 9, the first policy at 15 culture) are stale in a
turn-0 board until the game works them out again, the same for everyone who plays it. The eight games above
are that board's own value: the same two changes were made at turn 0 before the engine played.

### The floor against the anchor (2026-11-17, rule 8's first test)

The scripted loop (`scripts/play_loop.py`: it founds the capital where the Settler stands, automates Workers,
skips every other unit, and for production, research and policy takes the first thing it can from a fixed
list) played the first 30 turns of `board-duel-prince-a-t0-airow`, two deals, and each end save was played
out five times
(`--label play-loop --notebook none --turns 30 --runs 2 --continue 5 --last-turn 500`).

| | deal 0 | deal 1 |
|---|---|---|
| the window | 30 turns in 216 s | 30 turns in 218 s |
| the seat at turn 30 | one city of 3, 7 technologies, 4 policies, score 112 | one city of 4, 7 technologies, 4 policies, score 120 |
| built, in order | Worker, Monument, Shrine, Granary | the same |
| policies | Tradition, Aristocracy, Oligarchy, Legalism | the same |
| place by score | 2 of 2 | 2 of 2 |
| continuations won | 5 of 5 | 5 of 5 |
| ended by | Diplomatic five times, turns 360 to 386 | Diplomatic three times, Culture twice, turns 346 to 425 |

**The seat won all ten games**, 12.2 minutes each; in one it won the World Leader vote with the lower score
(1808 to 2133). The stock AI playing the whole game from turn 0 won 4 of 7 on the same board, and its three
losses were all conquests before turn 180; after the scripted window the Aztecs took no capital in ten games.
Three losses among seventeen games all falling to the stock AI's side has a chance of 35 in 680, about 0.05,
if the two were the same.

Read alone that puts the "floor" above the anchor. It does not: the whole games never pass through a save,
and the scripted run's continuations start from one made at turn 30. **The control is the anchor as rule 3
defines it**, the stock AI for the same 30 turns, the same save and the same five continuations a deal
(`--turns 30 --runs 2 --continue 5 --last-turn 500`, no command):

| | deal 0 | deal 1 |
|---|---|---|
| the window | 30 turns in 72 s | 30 turns in 69 s |
| the seat at turn 30 | one city of 3, 7 technologies, 3 policies, score 106, 207 gold | one city of 3, 7 technologies, 3 policies, score 102, 206 gold |
| place by score | 1 of 2 | 2 of 2 |
| continuations won | 5 of 5 | 4 of 5 |
| ended by | Diplomatic four times, Culture once, turns 313 to 350 | Diplomatic five times, turns 337 to 397, one of them the Aztecs' |

**Through the same chain the anchor is 0.90 (9 of 10) and the scripted loop 1.00 (10 of 10)**, 13.8 and 12.2
minutes a game. Three things follow.

- *The two are not told apart, and the board is out of the band.* After either opening the seat nearly always
  wins. Rule 8's first test failed here; what that means is said there.
- *The chain is not the whole game.* Twenty games from a turn-30 save: no conquest. Eight whole games: three,
  and a value of 0.57. A second look for what a save might lose (`e5`, the engine playing 30 turns, a read of
  both players, save, leave, load, the same read): at turn 30 Siam and the Aztecs have not met, and units,
  gold, military might and every stance that can be read are the same after the load. So nothing readable is
  lost, and the conquests come later than turn 30 in any case. What differs is that the seat is the human's
  again when the save is made and is handed to the engine a second time by the continuation. Whether that is
  the cause is not tested; the continuation now records the turn the seat is first at war and the most cities
  it held, so the next whole games and the next chain games can be set side by side.
- *The scripted loop is no floor.* Its fixed lists are an opening a person would recognise, and at turn 30 it
  stood where the stock AI stood (score 112 and 120 against 106 and 102, a policy more, 110 gold less). Thirty
  turns are too few for "answers only what is forced" to cost anything.

### A Tiny board through the chain (2026-11-17)

`board-tiny-prince-a-t0-terms`: Indonesia on the seat against Assyria, Brazil and America, the stock AI for the
30-turn window (108 s; at turn 30 one city of 5, 9 technologies, third of four by score), then four
continuations (`--turns 30 --continue 4 --last-turn 500`).

| game | how it ended | turn | minutes | the seat first at war | most cities it held |
|---|---|---|---|---|---|
| 0 | the seat conquered | 178 | 8.7 | turn 81 | 3 |
| 1 | the seat conquered | 160 | 6.0 | turn 75 | 2 |
| 2 | the seat conquered | 280 | 16.9 | turn 78 | 3 |
| 3 | Brazil's Diplomatic victory | 421 | 27.5 | turn 93 | 3 |

**0 of 4.** The seat is at war by turn 93 in every game and gone by turn 280 in three. Four games do not put
the value under 0.2 (none in four happens four times in ten at 0.2), but the board is no candidate: where the
first duel is nearly always won, this seat is nearly always lost. A game here that runs its length is 27.5
minutes, and the one that did went to Brazil's vote with America 800 points ahead.

Two boards, one above the band and one very likely below it. **A board in the band has to be looked for**:
several hosted, each screened through the chain by a handful of continuations, the ones near the middle kept
and measured properly. A seat's start decides more than 30 turns of anyone's play, which is what rule 2's band
was written to guard against and what the first two boards both show.

## Not checked yet

- A spaceship win under autoplay (Time, Domination, Culture and Diplomatic are seen).
- Whether a slot can be made an observer in a running game.
- How many AI-only games a win estimator needs on stock rules.
- How much one board's result varies between two runs of the same *agent* (the stock AI's spread on one late
  board is above), and the stock AI's spread on an opening board. They set how many replicates a board needs,
  and so what the benchmark costs.

## A pilot that also serves token accounting

Two boards (a turn-0 opening; the Maya save at t242 as an endgame), the same seat, each played alone from a copy
of the same save by each client under the seat loop, for a fixed window. One run each gives stage 5 of token
accounting its tables. A second run of one client on one board gives the first number for run-to-run variation.
The stock AI on the same boards is the first anchor.
