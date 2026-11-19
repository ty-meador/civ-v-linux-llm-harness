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
  (rule 2). The first duel is 0.90 through the chain and 0.73 by sixteen whole games; the first eight whole
  games alone said 0.57, and the gap they seemed to show did not last the second eight.
- A continuation with no victory by a stop turn is not decided and is in no share (rule 1).
- A value is given with its standard error and over all of an entrant's games on the board (rule 6).
- Rule 8's first test failed on the first board (out of the band, a 30-turn window). On the first board
  found inside the band the scripted loop's 100-turn window is 0 of 10 where the stock AI's is 5 of 10, its
  60-turn window 5 of 10 and its 30-turn window 7 of 10 ("The floor against the anchor, again" and "How
  short a window" below). One board in five screened is in the band. With ten deals the stock AI there is
  0.30 and the fixed loop's eight deals 0.125 (one win): by deals not a separation ("The fixed loop's eight
  deals" below).
- **A win as the only unit costs too much**: about ten deals a side to tell 0.3 from 0.0, each deal a window
  of a model's tokens. The fitted estimator of rule 1 now exists (`scripts/board_fit.py`, "The estimator's
  first fit" and "The estimator on sixty games" below): fitted on fifty-nine of the stock AI's own games and
  read once where a window ends, it puts the stock AI's 100-turn windows 0.27 to 0.31 above the scripted
  loop's with a standard error of 0.08 to 0.10, where the same eighteen windows played out were 0.175 apart
  with one of 0.18. Most of that error is the model's own (0.07 to 0.09, a jackknife over its games; the
  first fit's "0.04" left it out) and is paid once a board in games that cost no tokens; an entrant's deals
  add 0.03 to 0.04. Continuations remain its check, and each one played is a row for the next fit.
- **The games of one deal go together** (the 60-turn window: 0 of 5 on one deal, 5 of 5 on the other, the
  seat the same at turn 60 in both). The deal is the unit: a value's standard error is taken over deals
  (rule 6), an entrant needs many deals and few continuations a deal (rule 4), and the 100-turn result
  stands on two deals a side until more are played.
- The same save and the same continuation number are the same game to its last turn, so a value can be
  recomputed by anyone, and new games of a save need new numbers.

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
- **The estimate (added 2026-11-19).** On a board with a fitted model a run has a second value: the model's
  chance of the seat winning, read once from the position the window ended on (`scripts/board_fit.py`).
  Entrants on that board are compared by the estimate. The played-out value is its audit, and every
  continuation played for the audit is a row of the board's next fit.
  - *The model is the board's.* A logistic fit of the seat's team winning on what the referee reads of every
    player at one moment (the seat's share of each indicator and route), fitted on games the engine played
    from that board: whole games, and the continuations of played windows, whoever played the window. Only
    the reads within ten turns of the turn the window ends on are fitted. It knows nothing of how a position
    was reached or who played it. A feature is kept only if it lowers the log loss on games left out of the
    fit.
  - *It is named and frozen.* A value by estimate names the model's file, its games and the turns fitted. A
    new fit revalues every entrant of the board together, never one.
  - *A window ends only where the model tells something*: in turns where it beats the base rate on games it
    never saw. On the Celts duel that is not before turn 60; at 30 the estimate tells no entrant from another.
  - *Its limit is its features.* With score as its one feature (all that helps before turn 110 on the Celts
    duel) the estimate orders entrants as their share of score does, and what is said of score above holds
    of it. It is then the board's measured rate of exchange between a lead in score and wins, not a judgement
    of the position. An entrant who plays for what the model has no feature for is valued too low: on that
    board 37 of 59 games end by the vote and delegates say nothing before turn 200. The audit is the guard.
    An entrant whose played-out value stands above its estimate by more than their errors is reported by the
    played-out value, the report says so, and its continuations go into the fit.
  - Seen ("The estimator on sixty games" below): score alone on turns 90 to 110 of 59 whole games and 21
    played windows; the stock AI's ten 100-turn windows 0.413 and the scripted loop's eight 0.093, where
    played out they were 0.30 and 0.125. Not seen: an entrant the model never saw valued and then audited; a
    second board; a model with more than score in it at a turn a window can afford.
- **The path, on a long window.** The referee can save at fixed turns inside the window and value each save the
  same way. The path says whether a lead was built early and kept, thrown away, or won back from behind. The
  headline stays the value at the window's end: an average over the path would pay for a lead that was then
  lost.
- **A continuation is stopped at a turn the board names** (500 at Quick speed so far). With no victory by
  then it is not decided: it is in no share and is counted beside the value. One whole game in eight on the
  first duel ended that way, the seat far ahead.
- Seen: 114 games played out with no screen in the way, the winner read from `Game.GetWinner()`, ended by
  Diplomatic (73), Culture (20), Domination (11), Science (1) and Time (5, before it was switched off), three
  at the seat's death and one stopped at turn 500; the chain of window, save, load and continuation; a
  continuation from turn 30 of a duel in 12 to 14 minutes. Every victory type has now been read by the
  referee; Science once, on a board made for it ("A Science victory" below).

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
  board the seat always or never wins, no window can show anything. The first duel is 0.90 through the chain
  (9 of 10) and 0.73 by sixteen whole games (11 of 15 decided), 0.80 over both: on the top edge, and not a
  board to spend an entrant on. With ten decided games a value near 0.5 is known to 0.16 either way; a board
  near an edge of the band needs more before it is kept or dropped, and a board in its middle is the better
  use of the games.
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
draws when it starts. **Deals are what an entrant needs many of.** What the other side does with a deal's
draws inside the window decides more than the continuations after it do: the scripted loop's 60-turn window
on the Celts duel was worth 0 of 5 on deal 0 and 5 of 5 on deal 1, the seat identical at turn 60 and Austria
at score 247 and 182. So eight deals with one or two continuations each, not two deals with five. For a model
every deal is a window of its tokens, and that, more than machine hours, is what a value costs.

**5. A run counts whatever happened.**

- The window is the referee's: the board must be that many turns on. **The referee closes the seat on the
  window's turn** (added 2026-11-19; the user: overshooting is the benchmark's to handle, not the entrant's).
  The seat's server is given that turn (`CIV5_UNTIL_TURN`, set by `llm_seat_loop.py --until-turn`): the finish
  that brings it says `window_over`, a run of quiet turns stops on it, and on it every order and every finish
  is refused. So an entrant cannot play past its window and a count gone wrong is not a DNF; stopping short
  still is. Before this a board one turn past the window read as not played and had no value (the pilot's
  deal 1, whose cause was the harness's own and is fixed apart from this).
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

- Per board and entrant: the mean of its finished deals' values with **the standard error over deals** (the
  deals' standard deviation over the root of their number), the anchor's and the scripted loop's beside it,
  each deal's own value, the games behind them (won W of N), and the number of deals not finished. The
  games of one deal are not independent trials (rule 4), so sqrt(p (1 - p) / N) over games, which
  `--summary` still prints, is too small and is not the error of a value. With deals worth 0 or 1 each, ten
  deals tell 1.0 from 0.5 and not 0.9 from 0.7, and a difference of 0.15 between two entrants on one board
  needs about ninety deals each. That is the price of a win as the unit, for a model it is paid in windows
  of tokens, and it is the reason for the estimate of rule 1.
- **A value by estimate has two errors and both are given** (added 2026-11-19). The deals' (the standard
  deviation of the deals' estimates over the root of their number) is the entrant's. The model's is the
  board's: a jackknife over the games of the fit (the estimate under each fit that leaves one game out, their
  spread scaled by the number of games). It is shared by every entrant valued on the board and more deals do
  not make it smaller; more games of the board do, most where entrants' windows end. A difference between two
  entrants is given with the model's error taken on the difference, since one fit values both. On the Celts
  duel at 100 turns the stock AI less the scripted loop is 0.320 with 0.045 from the deals and 0.056 from the
  model, 0.072 together; the same eighteen windows played out, 0.175 with 0.18. A deal's estimate varies far
  less than a deal's win (a standard deviation of 0.14 over the stock AI's ten deals against 0.5 for a coin),
  so eight deals give the entrant's own error as 0.05 where eight wins give 0.18. The range of the fits that
  leave one game out is not an error and is not given.
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

- *The value cannot tell a floor from the anchor.* **Open. The loop's seat is worth less the longer the loop
  holds it, on a board in the band; by deals the difference at 100 turns is not yet shown, and at 30 turns
  there is none on either board.** On `board-duel-prince-d` (the Celts against
  Austria; two deals, five continuations a deal) the scripted loop's window is worth 7 of 10 at 30 turns,
  5 of 10 at 60 (0 of 5 and 5 of 5) and **0 of 10 at 100**, where the stock AI's 100-turn window is 5 of 10
  and its fourteen games on the board are 7. The loop never builds a Settler, and the longer it holds the
  seat the less the seat is worth: that is the valuation doing what it was meant to. But the games of one
  deal go together, so the 100-turn result is two deals at 0 against two at 0.4 and 0.6, not twenty
  independent games (which would have made it 0.016 by chance). With eight more deals a side the stock AI
  is 0.30 over ten deals (standard error 0.13) and the loop finished three deals of ten, all at 0: by deals
  that is not yet a separation (three in ten by chance), and the loop's seven unfinished windows were its own
  fault, since fixed. At 30 turns the loop's opening costs nothing on this board (7 of 10 against the stock AI's 7 of
  14) or on the first duel (10 of 10 against 9 of 10): thirty opening turns of one sound build order are not
  bad play, and no test of a 30-turn window exists yet that has bad play in it.
- *Continuations are too slow or too noisy.* **Slow and noisy, both measured.** From an opening a duel
  continuation is 12 to 14 minutes, and a whole Tiny game to turn 330 took 24. Five an hour is a value known
  to about 0.2. "Valued within the hour" holds only for late boards (a continuation from turn 325 took 2.2
  minutes). Rule 6 now gives the standard error and says what a difference costs.
- *No board is undecided.* **One is, of five.** The seat on the human's Prince row lost every whole game. On
  the AIs' row the first duel is 0.80 over all 25 decided games of the stock AI, on the band's top edge; two
  more duels were 4 of 4 and the first Tiny board 0 of 4. `board-duel-prince-d` is 7 of 14, 0.50 (standard
  error 0.13). Boards have to be hosted in number and screened, about four for one kept.
- *The save in between.* **Holds as a mechanism; not shown to change the result.** Twenty games played out
  from a turn-30 save had no conquest and the first eight whole games on the same board had three, which
  looked like the save's doing (0.017 by chance). Eight more whole games had none: three conquests in sixteen
  whole games against none in twenty is 0.08, and the stock AI's value is 0.73 by whole games (11 of 15) and
  0.90 through the chain (9 of 10), no difference at those numbers. At turn 30 the two have not met, and what
  can be read of both players is the same before the save and after the load. The band is still measured
  through the chain, because that is how a run is valued, and every run goes through the same chain.
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
  it held, so the next whole games and the next chain games can be set side by side. (Eight more whole games
  had no conquest either: "Eight more whole games" below. The gap is not shown to be real.)
- *The scripted loop is no floor.* Its fixed lists are an opening a person would recognise, and at turn 30 it
  stood where the stock AI stood (score 112 and 120 against 106 and 102, a policy more, 110 gold less). Thirty
  turns are too few for "answers only what is forced" to cost anything.

**The same draws are the same game, to the end.** The eight whole games asked for a second time, on the board
that carries its terms, began by replaying the first run game for game: Diplomatic at turn 342 after 757 s
(775 the first time), then Culture at turn 273 (272, the poll's own second). A continuation is its number's
draws and nothing else, so new games of one save need new numbers (`--first-continuation M`), and a value can
be recomputed by anyone from the save and the numbers. The game process then died on its way back to the main
menu, about 45 loads into one process, and took both games with it, since a row was written only when all its
continuations were in; the runner now keeps them beside the rows file as it goes (`<rows>.partial`).

### Eight more whole games: the chain is not shown to differ (2026-11-17)

Games 8 to 15 of `board-duel-prince-a-t0-airow`, the engine from turn 0
(`--value-only --continue 8 --first-continuation 8 --last-turn 500`), with the war turn and the cities recorded.

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

**7 of 8, and no conquest.** With the first eight the board's whole games are **11 of 15 decided, 0.73
(standard error 0.11)**, three conquests in sixteen.

- *The gap between whole games and the chain was the first eight games' luck, as far as these games can
  say.* Three conquests in sixteen whole games against none in twenty from a turn-30 save has a chance of 0.08
  if the two are the same (560 in 7140), where the first eight alone gave 0.017. In value, 11 of 15 whole
  against 9 of 10 through the chain for the stock AI is no difference either. Nothing was found that a save
  loses, and now nothing is left that needs it. The engine's two segments with no save between are not worth
  their 90 minutes until a difference shows again; chain games record the war turn from here on.
- *The stock AI's games on this board, all of them: 20 of 25 decided, 0.80 (standard error 0.08).* The board
  sits on the top edge of the band, which is where a board is least use: the seat is Siam, whose trait is its
  city-states, against one rival, and all 20 of the seat's wins are the World Leader vote or Culture.
- *War is not the danger here after the first 180 turns.* The seat was at war in five of the eight games,
  first between turn 102 and turn 277, and the end shows one city lost in all of them (game 14, four of
  its five).
- Two games took 27 and 32 minutes for the same 340 turns the others played in 12. The machine did nothing
  else that is known. A wall-clock limit on a continuation has to allow for it.

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

### Three more duels screened (2026-11-17)

Three duels hosted one after another as the setup screen deals them (random civilizations, random map), each
made to carry its terms and screened through the chain: the stock AI's 30-turn window, the save, four
continuations (`logs/boards/scratch/screen_boards.sh WORLDSIZE_DUEL 4 ...`, about 40 minutes a board with the
hosting).

| board | the seat against | at turn 30, score | won | ended by | the seat first at war |
|---|---|---|---|---|---|
| `board-duel-prince-b` | Poland against Mongolia | 141 to 109 | 4 of 4 | Culture three times, Diplomatic once, turns 253 to 329 | never, never, turn 250, turn 263 |
| `board-duel-prince-c` | Morocco against Sweden | 126 to 116 | 4 of 4 | Culture twice, Diplomatic twice, turns 261 to 340 | never, never, turn 195, turn 261 |
| `board-duel-prince-d` | the Celts against Austria | 103 to 106 | 2 of 4 | Austria by Culture (turn 295) and Diplomatic (361); the seat by Domination (411) and Diplomatic (378) | never, turn 284, turn 309, turn 373 |

- **`board-duel-prince-d` is the first board near the middle** and is the one measured next: rule 8's first
  test again, with a 100-turn window, so that the scripted loop's one city has a price if anything has.
- Boards b and c go the way of the first duel: the seat wins by Culture or the vote and is never in danger.
  They are dropped.
- **The seat's side has won 30 of the 37 decided duel games the stock AI played on it**, on four boards,
  against the same program on the other side (a 20 of 25, b and c 4 of 4, d 2 of 4). Four boards cannot say
  whether that is these four starts or an edge the seat has of its own (it is player 0 and moves first, and
  it is the start the game gave the human). It matters for how many hosted boards a kept one costs: one in
  four so far.
- Little ends early on a duel with both sides on one row. Of the 48 such games three ended by conquest
  (turns 126 to 177, all among the first eight), and in the twenty with the war turn recorded the seat's
  first war was never before turn 102.

### The floor against the anchor, again: a board in the band, 100 turns (2026-11-17)

`board-duel-prince-d`, the Celts on the seat against Austria. The scripted loop for 100 turns, two deals, five
continuations a deal, then the stock AI through the same window
(`logs/boards/scratch/floor_anchor.sh board-duel-prince-d 100 5 logs/boards/duel-d`; a deal of the loop is 17
minutes of window and 73 of continuations, a deal of the stock AI 4 and 71).

| at turn 100 | the loop, deal 0 | the loop, deal 1 | stock AI, deal 0 | stock AI, deal 1 |
|---|---|---|---|---|
| cities, population | 1, 12 | 1, 12 | 2, 13 | 3, 11 |
| technologies, policies | 21, 9 | 20, 9 | 20, 6 | 23, 7 |
| land, military might | 28, 263 | 29, 269 | 22, 401 | 43, 91 |
| score, seat to Austria | 266 to 606 | 262 to 403 | 336 to 438 | 459 to 447 |
| continuations won | 0 of 5 | 0 of 5 | 2 of 5 | 3 of 5 |
| ended by | Austria's vote four times, its Culture once, turns 356 to 370 | Austria's vote five times, turns 384 to 406 | the vote five times, turns 377 to 450 | the vote four times and the seat's conquest, turns 369 to 413 |
| the seat first at war | never in four, turn 315 | turns 259 to 380 | turns 113 to 125 | turns 292 to 315 |

**The scripted loop 0 of 10, the stock AI 5 of 10**, 14.5 and 14.1 minutes a game.

- *The value separates them, as far as two deals a side can say.* Five wins among twenty games all on the
  anchor's side would have a chance of 0.016 if the two were one player and the games independent (252 in
  15504). They are not independent ("How short a window" below): what stands is two deals at 0 against two at
  0.4 and 0.6.
- *The board is in the band*: the stock AI is 7 of 14 through the chain, 0.50 (standard error 0.13), and its
  two 100-turn deals are 0.4 and 0.6.
- *What the loop lacked is cities.* It researches as fast as the stock AI and adopts policies faster
  (21 and 20 technologies against 20 and 23, 9 policies against 6 and 7). It
  never builds a Settler, and the engine that takes the seat at turn 100 gets it to three to eight cities too
  late: nine of the ten games went to Austria's World Leader vote.
- *A stopped window is not a lost one.* Left at turn 100 with one city, the seat is not conquered in any of the
  ten games and is at war in six, late. On a duel the price of bad play is paid at the vote, 250 turns on,
  which is why a game costs 14 minutes whatever was played.
- Not yet known: how short a window still shows it. The loop's 30-turn opening on the first duel cost
  nothing, on a board that could not have shown it. The same loop at 60 and at 30 turns on this board is the
  next measurement; the stock AI's fourteen games are the comparison for every window, since the anchor is
  the stock AI from the first turn to the last whatever the window is.

### How short a window, and the deal is the unit (2026-11-18)

The scripted loop on `board-duel-prince-d` again, 60 turns and then 30, two deals and five continuations a
deal (`logs/boards/scratch/floor.sh board-duel-prince-d 60 5 logs/boards/duel-d`, then 30). With the 100-turn
run, by window and deal, the score at the window's end (seat to Austria) and the continuations won:

| window | the loop, deal 0 | the loop, deal 1 | the loop | the stock AI |
|---|---|---|---|---|
| 30 turns | 124 to 112, 3 of 5 | 124 to 108, 4 of 5 | 7 of 10 | deal 0: 103 to 106, 2 of 4 |
| 60 turns | 202 to 247, **0 of 5** | 202 to 182, **5 of 5** | 5 of 10 | |
| 100 turns | 266 to 606, 0 of 5 | 262 to 403, 0 of 5 | 0 of 10 | deal 0: 336 to 438, 2 of 5; deal 1: 459 to 447, 3 of 5 |

- **The longer the loop holds the seat, the less the seat is worth**: 0.7, 0.5, 0.0, against the stock AI's
  0.50 over its fourteen games. Thirty turns of it cost nothing, as on the first duel.
- **The games of one deal go together.** At 60 turns the seat is the same in both deals (one city of 9, 15
  technologies, score 202) and Austria is at 247 in one and 182 in the other; the first is lost five times
  of five and the second won five times of five. Were the ten games independent at one in two, a split that
  clean would come twice in a thousand. A continuation's own draws move little: what the other side made of
  the deal's draws inside the window has decided most of it by the window's end.
- **So the deal is the unit**, and three things change. A value's error is taken over deals (rule 6): the
  loop's 60-turn value is 0.5 with deals at 0 and 1, which is no knowledge at all, and not 0.5 with a
  standard error of 0.16. An entrant's games go into deals, not continuations (rule 4). And the 100-turn
  result above is two deals a side.
- **It also says the valuation is sharp where it matters**: one position at turn 60 is worth 0 and another
  1 with the seat the same in both. The continuations are not adding much noise of their own; the noise is
  in which game the deal turned out to be.
- *A deal's path, if one deal is one game.* The loop is a fixed program and a deal is fixed draws, so the
  three windows should be three cuts of the same two games (not checked turn by turn). Then deal 1 reads 0.8
  at turn 30, 1.0 at turn 60 and 0.0 at turn 100: handed to the stock AI at turn 60 the seat wins five of
  five, kept by the loop for forty turns more it loses five of five. Deal 0 reads 0.6, 0.0, 0.0: lost
  between turn 30 and turn 60. That is rule 1's path, and the first time a window's turns are seen to cost a
  game.
- Next: eight more deals each for the loop and the stock AI at 100 turns, one continuation a deal, so that
  the comparison stands on ten deals a side.

### Ten deals of the stock AI, and a loop that did not finish (2026-11-18)

Deals 2 to 9 of the same 100-turn window for both, one continuation a deal
(`logs/boards/scratch/deals.sh board-duel-prince-d 100 4 1 logs/boards/duel-d`, twice).

| deal | the stock AI at turn 100, score to Austria | its game | the scripted loop |
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

- **The stock AI over ten deals: 0.30, standard error over deals 0.13** (deals at 0.4, 0.6, six at 0 and two
  at 1). The board is in the band, in its lower part; the 0.50 of its first fourteen games was two deals and
  a screening.
- **The scripted loop did not finish seven deals of eight**, and finished three of ten in all, each worth 0
  (0 of 11 games). By rule 5 that is its result: finished 3 of 10 windows, and a DNF stands below every
  finished run. The cause was the loop's and is fixed (ccb2de9): a Warrior it had moved off a stack kept a
  standing move, a barbarian ship came beside it, the harness held the move back and the engine blocked the
  end of the turn on the unit; the loop's skip was refused as "does not block end_turn" and it asked sixteen
  times and stopped. The refusal contradicts the hold's own note and is filed (#211). The fixed loop is
  another entrant and plays deals 0 to 7 again.
- **By deals the two are not yet told apart at 100 turns.** Three finished deals at 0 against ten of which six
  are at 0 could be one player three times in ten (84 in 286). Twenty games had said 0.016. Even if the fixed
  loop loses all eight of its deals, eight deals at 0 against four above 0 in ten is 0.07. A board where the
  anchor is 0.3 has little room under it: this board shows a worse player slowly and would show a better one
  faster.
- **One deal is one game, as far as the window reaches.** The loop's log of its own orders is the same line
  for line in the 30-, 60- and 100-turn runs of a deal over the turns they share, and deal 8 played again
  stopped on the same turn at the same unit. So the three windows of "How short a window" are three cuts of
  two games, and a deal's path is what that section read it as.
- **What a value costs is now measured, and it is too much for a win as the only unit.** A deal is worth 0
  or 1 or near it; ten deals give a standard error of 0.13 to 0.16; telling 0.3 from 0.0 takes about ten
  deals a side and telling 0.5 from 0.35 about ninety. For a model a deal is a window of its tokens. The
  position at the window's end already says most of what the continuations then confirm (Austria at 247 or
  at 182 with the seat the same: 0 of 5 and 5 of 5), so the next instrument is the fitted estimator of rule
  1: the stock AI's own games, read every ten turns, give positions with their outcomes for no tokens; a
  model's deal is then valued by one read at its window's end, on a scale finer than won and lost, and
  continuations check the estimator and no longer carry the value.

### The fixed loop's eight deals (2026-11-18)

The loop with the skip fixed (ccb2de9) played deals 0 to 7 of the 100-turn window on `board-duel-prince-d`, one
continuation a deal, to `--last-turn 500` (`logs/boards/duel-d/floor2-t100.jsonl`; a power cut stopped the run
inside deal 5's continuation and the same command played again took deals 5 to 7 up).

- **It finished every window** (about 17 minutes each), second by score in all eight, one city in each.
- **1 of 8: 0.125, standard error over deals 0.125.** Deal 4 was won by the vote at turn 375; six were lost to
  Austria's vote and deal 5 to its Culture at turn 280.
- **Against the stock AI's 0.30 (0.13) over ten deals the difference is 0.175 with a standard error of 0.18.**
  One deal above 0 in eight against four in ten is 0.23 by chance. Rule 8's first test is not passed at 100
  turns on this board by deals, and eighteen windows were played to learn it.
- **The won deal was won from behind.** Read every ten turns (`--path 10`, the same game to the last score as
  the run without it), the seat was behind on score at every read from turn 100 to the end (by 59 to 327 points)
  and had 12 delegates against 6 at turn 371, with 8 needed. Score alone does not see the route this board is mostly
  decided by, so a point of a path keeps allies, delegates and tourism beside the indicators.

### The estimator's first fit (2026-11-18)

*Corrected by the next section: the "standard error of 0.036" below is the error over deals alone. The
model's own error on nineteen games was 0.10 on the difference and 0.12 on each estimate (a jackknife), far
more than the leave-one-out ranges given here, and forty more games moved both estimates up by 0.08.*

Twenty whole games of `board-duel-prince-d` played by the engine on both seats (`--value-only --continue 20
--path 10 --last-turn 500`, 18 minutes a game, no tokens; `logs/boards/duel-d/whole-path.jsonl`). The seat won 9
of the 19 decided (thirteen by the vote, three by Domination, three by Culture; one not decided by turn 500).
Read every ten turns they are 713 positions with an outcome. `scripts/board_fit.py` fits the seat's team winning
on the seat's share of each indicator less an even share; every figure below is the log loss on a game the fit
never saw, beside the base rate's 0.749.

- **What decides this board comes late, and it is the vote.** Over all turns score gives 0.662 and score with
  delegates and allies 0.584. By turns: before turn 60 nothing beats the base rate (score 0.762); turns 60 to
  109 score 0.719; 110 to 159 score 0.664; from 260 delegates alone 0.379. At turn 100 the seat's share of
  score was 0.56 in the games it won (0.48 to 0.68) and 0.51 in those it lost (0.44 to 0.60).
- **A model for windows is fitted on the turns windows end in** (`--turns 20 110`, 178 points): constant -0.29,
  score +10.5 a unit of share, so an even position is 0.43 and five points of share are about 0.13. On the
  stock AI's games alone that is a thin gain (0.7325 against 0.7500), and the slope runs from 8.7 to 13.5 as one
  game or another is left out. No second feature helps in those turns.
- **Read once where a window ended, it agrees with what playing the windows out gave**, on windows it never
  saw and an entrant it never saw:

  | windows | deals | estimate (error over deals) | played out |
  |---|---|---|---|
  | stock AI, 100 turns | 10 | 0.412 (0.034) | 0.30 (0.13) |
  | fixed loop, 100 turns | 8 | 0.138 (0.012) | 0.125 (0.125) |
  | loop before the fix, 100 turns, the three finished | 3 | 0.144 (0.032) | 0 of 11 games |
  | loop, 60 turns | 2 | 0.402 (0.094) | 0.50 (0 of 5 and 5 of 5) |
  | loop, 30 turns | 2 | 0.506 (0.012) | 0.70 |

- **The same eighteen windows now separate the two entrants.** 0.412 against 0.138 is 0.27 with a standard
  error of 0.036; played out they were 0.175 apart with 0.18. A read has no won-or-lost in it, so the error left
  is how much an entrant's positions differ from deal to deal. Rule 8's first test is passed on this board at
  100 turns by the estimate; by wins it is not shown.
- **What that error leaves out.** The model's own doubt: as one game or another is left out of the fit the
  stock AI's estimate runs from 0.36 to 0.44, the loop's from 0.08 to 0.19 and the difference from 0.24 to
  0.32, and more whole games narrow it at 18 minutes each. The loop's positions (a share of 0.35)
  lie outside what the stock AI's games reach at turn 100 (0.44 to 0.68), so its estimate is a line carried on;
  the played-out 1 of 8 and 0 of 11 say the line is not far off. And score is not the game: the loop's one win
  came by the vote from behind on score at every read, and an entrant that played for delegates would be valued
  too low before turn 200. The estimate is the fine scale; continuations stay the check on it.
- **At 30 turns it cannot tell entrants apart** (0.506 with 0.012 for the loop, and the stock AI's positions at
  turn 30 run from 0.46 to 0.55 of score): the positions have not yet moved apart, whoever plays.

### The estimator on sixty games (2026-11-19)

Forty more whole games of the board (continuations 20 to 59; the sixty took 17.4 minutes a game, 11.5 to 23.4). Of the sixty,
59 are decided and the seat won 32 (0.54, standard error 0.065): 37 by the vote (16 won), 11 by Culture (10
won), 11 by Domination (6 won), ending between turn 248 and 437, half by 378. 2213 positions.

- **The difference held; the levels did not.** The first fit's model again (score alone, turns 20 to 110, now
  555 points): constant +0.03, score +8.8 (it was -0.29 and +10.5). The stock AI's ten windows 0.490, the
  loop's eight 0.219: 0.27 apart as before, and both 0.08 higher. The seat won 23 of the forty new games
  against 9 of the first nineteen.
- **The range beside the first fit was not an error.** 0.36 to 0.44 does not hold 0.49, nor 0.08 to 0.19
  0.22. The fits that each leave one game out give a standard error when their spread is scaled by the number
  of games (a jackknife). On nineteen games that is 0.118 for the stock AI's estimate, 0.125 for the loop's
  and 0.097 for the difference: the first fit's "0.27 with 0.036" was 0.27 with 0.10. On fifty-nine: 0.067,
  0.113 and 0.090, with the deals' 0.033 together 0.096. `board_fit.py --value` prints the jackknife in place
  of the range, and for two entrants the difference with the model's error taken on the difference itself
  (one fit values both).
- **Three times the games barely moved the difference's error** (0.097 to 0.090) though the slope's own fell
  from 6.0 to 4.1: the loop's positions (a share of 0.35) lie outside every position the stock AI's games
  reach at turn 100 (0.42 to 0.68), so its estimate hangs on the slope, and more so the nearer it comes to
  the middle.
- **Fitted nearer the turn the windows end on, the slope is steeper.** Score alone, the 59 games:

  | turns fitted | points | slope (jackknife) | an even position | stock AI | loop | difference (deals, model, together) | log loss, a game left out (base rate) |
  |---|---|---|---|---|---|---|---|
  | 20 to 110 | 555 | 8.8 (4.1) | 0.51 | 0.490 | 0.219 | 0.272 (0.033, 0.090, 0.096) | 0.689 (0.707) |
  | 60 to 110 | 319 | 10.2 (4.8) | 0.48 | 0.459 | 0.169 | 0.291 (0.037, 0.080, 0.088) | 0.676 (0.707) |
  | 90 to 110 | 142 | 12.4 (6.5) | 0.45 | 0.432 | 0.118 | 0.313 (0.042, 0.066, 0.079) | 0.668 (0.706) |

  Before turn 60 score still says nothing (0.708 against 0.707); turns 110 to 159 0.619; turns 160 to 259
  with delegates and allies 0.543; from 260 0.360, delegates alone 0.437. No second feature helps before turn
  110 (techs, cities, military, the routes, the turn, score times the turn). A band of turns is a choice that
  moves a level by 0.06 to 0.10 and the difference by 0.04; the game is the unit in any band, so the model
  for a window is the one fitted on the turns about its end (90 to 110 here).
- **Score at turn 100 without a model.** Ahead on score the seat won 28 of 40, behind 4 of 19 (0.0006 by
  chance). By share: under 0.45 0 of 4, to 0.50 4 of 15, to 0.55 11 of 17, to 0.60 12 of 15, above 5 of 8.
  More a step at the even share than a line, which is some of why the slope's error is wide.
- **The played windows as rows of the fit.** A window's continuations are positions with outcomes too
  (`--fit` takes their rows: one point a decided continuation, the deal left out whole), and they lie where
  entrants end, not where the stock AI does. With the ten stock-AI windows (7 of 18 games won), the loop's
  eight (1 of 8) and the three before the fix (0 of 11), turns 90 to 110, 80 games: constant -0.27, score
  +13.7 (4.6), log loss 0.606 against 0.705; the stock AI 0.413 (deals 0.044, model 0.054), the loop 0.093
  (0.011, 0.052), the difference 0.320 (0.045, 0.056, together 0.072). The model has then seen the windows it
  values (each estimate's error still leaves a deal out); for an entrant after them it has not.
  `logs/boards/duel-d/estimator-t90-110-windows.json`.
- **What the two errors are.** The model's is of the board: paid once, in games and continuations already
  played, and shared by every entrant valued on it, so it does not shrink with an entrant's deals. The deals'
  is the entrant's: 0.03 to 0.045 on ten and eight deals here. Which of two entrants stands higher is their
  positions' difference (the loop's share of score at turn 100 is 0.350 with 0.010 over its eight deals, the
  stock AI's 0.493 with 0.014 over ten) and the slope's sign; how much higher in wins carries the slope's
  error.
- **A window is the first turns of a whole game on the same draws.** A 100-turn window that took 493 draws
  (deal 29's) ended on the position whole game 16 (29 times 17 draws) showed at turn 100: every indicator and
  route of both players equal, gold apart, which is read at another moment of the turn
  (`logs/boards/duel-d/same-game-check.jsonl`). So the ten stock-AI windows are ten more first hundred turns
  of the same kind as the sixty, and they came out low: a share of 0.493 at turn 100 against the whole games'
  0.534 (0.008 over 59), 2.6 standard errors apart, and played out 0.30 against 0.54. Nothing in how a window
  is played accounts for it. Every entrant gets the same deals, so a comparison is not moved by it; a level
  read off ten deals is.
- **What a model's value on this board would cost, from what is measured.** Eight deals of a 100-turn window,
  one read each, give the entrant's own error as about 0.05. The only turns priced so far are late ones (the
  Maya board at turn 242, ten-turn cycles of the seat loop, `docs/measurements/2026-11-14-what-grows/`): 0.06
  to 0.07 dollars a turn at list prices for Sonnet 5.5 and for gpt-6.1-sol, and about 55 seconds a turn. At
  that rate a deal is 6 to 7 dollars and an hour and a half, an entrant's eight deals about 50 dollars and
  twelve hours on the one machine. An opening's first turns ask less than a late turn, so this is the upper
  side; no opening window has been priced. By wins the same error would want about a hundred deals.

### A Science victory, on a board made for it (2026-11-18)

No game in a hundred had ended by a spaceship. The user's lever (2026-11-17): put a science civilization on
the seat and the stock AI may go for it. Two duels hosted with Korea on the seat
(`logs/boards/scratch/host_board.py ... civ=CIVILIZATION_KOREA`, and `only=` for the victory types left on;
`logs/boards/scratch/science_check.sh CIVILIZATION_KOREA board-duel-korea-a 3 2`), the engine from turn 0:

| board | game | ended by | winner | turn | minutes | technologies, seat to rival |
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
- *Taking the earlier victories away did*, once in two. Such a board is a referee's check and not a
  benchmark board: its seat and its rules were chosen for the outcome.
- Korea was conquered in three of the five games, twice by the Aztecs, first at war at turns 65 and 154.
  A seat's civilization moves a board's value a long way, which is the screening's finding again.

## Not checked yet

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
