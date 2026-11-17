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
   this seat like the AI at level X", which is a unit a player understands.
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

## Not checked yet

- At which handicap the AI plays an autoplayed seat. `Player:GetHandicapType()` stays the human's (Emperor in
  both games) while the seat is a computer slot; whether the seat then gets the AI's bonuses is not read. One
  duel, 93 to 174, decides nothing.
- A game that ends by another victory under autoplay (the capital lost, a spaceship), and a seat that dies.
- How many AI-only games a win estimator needs on stock rules.
- How much one board's result varies between two runs of the same agent. Everything above depends on it: it sets
  how many replicates a board needs, and so what the benchmark costs.

## A pilot that also serves token accounting

Two boards (a turn-0 opening; the Maya save at t242 as an endgame), the same seat, each played alone from a copy
of the same save by each client under the seat loop, for a fixed window. One run each gives stage 5 of token
accounting its tables. A second run of one client on one board gives the first number for run-to-run variation.
The stock AI on the same boards is the first anchor.
