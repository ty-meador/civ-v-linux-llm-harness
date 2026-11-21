# CivBench and this project (first thoughts)

Written 2026-11-13. Thinking, not a plan: nothing here is decided or built. Source for every CivBench fact:
Chen, Cheng, Gurkan, Lin, "CivBench: Progress-Based Evaluation for LLMs' Strategic Decision-Making in
Civilization V", arXiv 2604.07733v1 (April 2026), read in full text that day.

## What CivBench is

- A benchmark for "LLM strategists" in multiplayer Civilization V, built on Vox Deorum (a modified game DLL, the
  Vox Populi mod, a bridge service and an MCP server; Windows).
- The LLM replaces the *strategic module* of Vox Populi's AI and nothing else. Each turn it reads one Markdown
  report and calls `set-flavors` (a grand strategy and 34 weights), `set-persona`, `set-relationship`,
  `set-research`, `set-policy` or `keep-status-quo`, in at most five steps. The in-game AI moves every unit,
  runs every city and conducts the diplomacy.
- The measurement is the contribution. Win or loss is too sparse over hundreds of turns, so estimators are trained
  on turn-level state (23 features in 9 groups, encoded as shares of the cross-player total and gaps to the
  leader, plus turn progress) to predict each player's victory probability. A game becomes a progress-weighted
  relative standing, and Bradley-Terry ratings are fitted over games, with the stock Vox Populi AI fixed at 1500.
- The study: 307 games, 8 players each, Communitas_79a map, 7 LLMs in two setups (Simple, Briefed), plus 194
  AI-only games to train the estimators. Four strategists tie with the AI; none beats it; all beat the ablation
  with the strategic module suppressed (1339).
- Cost: $10,497 at list price. Per game a strategist read 7 to 25 million input tokens and wrote 0.5 to 3 million.
- Data: about 777 MB of turn-level statistics "will be publicized alongside the code"; raw trajectories (SQLite)
  and telemetry (OpenTelemetry), 644 GB, on request. Whether the code and data are out yet was not checked.
- The paper says a run may start "from turn 0 or from existing savegames", allows any player count, and names
  not-fully-crossed runs against AI "or even human strategists" as future work.

## How this project differs

| | CivBench / Vox Deorum | This harness |
|---|---|---|
| Game | Vox Populi mod, modified DLL, Windows | stock Brave New World, Linux, no mod, through the tuner port |
| What the LLM controls | strategy weights, research, policy | everything a human seat does: every unit, city, deal, vote |
| Information | a report compiled by the mod, with analysis from the AI | what the seat's screen shows, enforced (tunerd seat binding) |
| Opponents | 8 players, LLM strategists and AI | the built-in AI, and other LLMs as hotseat seats |
| Pace | about 15 s per turn; hundreds of games | minutes per turn late in a game; a handful of games |
| Agent | their own loop and prompts | any MCP client as it ships (Claude Code, Codex, Grok) |

The two answer different questions. CivBench asks whether a model can steer a competent AI. This harness asks
whether a model can play the game. CivBench's own result (no strategist beats the rule-based module) leaves the
second question open, and the paper's design explicitly leaves tactics and diplomacy to the AI.

## Four ways to use the project there, cheapest first

1. **Their method on our games.** The estimator's inputs are all things the Lua API reads for every player:
   technologies, policies, science / culture / tourism / gold / production / faith per turn, cities, population,
   military strength and supply use, wars, truces, friendships, votes, happiness. An operator-side recorder (the
   spectator already reads every player each turn) could write one row per player per turn in their field names.
   A game played through the harness then has a CivBench-shaped trajectory. Operator-side only: a seat never
   reads it.
2. **A short-horizon protocol.** Full control is too slow for 300 games of 400 turns. Progress-based scoring is
   what makes a slow player measurable: start every model from the same saved positions, play K turns, score the
   *change* in estimated standing against the built-in AI playing the same seat from the same save
   (`Game.SetAIAutoPlay` gives that baseline for no tokens). The paper allows savegame starts. The saves, the
   seat, K and the settings would be the benchmark's definition.
3. **A full-control condition next to Simple and Briefed.** The same rating scale, a third kind of agent. This
   needs the harness on their game: Vox Populi, their DLL, 8 players. Unknown and likely large: the DLL is a
   Windows build (the harness drives the native Linux binary; the tuner port under Proton is untested), and
   Vox Populi changes rules the runtime's reads assume (happiness, the city-count penalty, the trade and
   diplomacy screens).
4. **Cost as a shared axis.** Their table is tokens per game per model. With token accounting
   (`docs/TOKEN_ACCOUNTING.md`) this project prints the same for full control: tokens per turn, per game, the
   cached share. "What does a point of standing cost" is a comparison neither project has made.

## What stands in the way

- **The estimators are fitted to Vox Populi.** Stock BNW balances differently (their `_adj` features exist
  because of a Vox Populi penalty). Their trained models cannot be assumed to transfer; a stock-rules estimator
  needs stock-rules games. AI-only autoplay games cost no tokens, so a training set is a matter of machine time,
  but nobody has checked how many are needed (they used 194 AI games plus the LLM games) or that this build
  autoplays unattended to a victory screen.
- **Seat count.** Their games have 8 competing players. A hotseat here has been run with 3 LLM seats.
- **Reproducibility.** They note exact reproduction is infeasible (the game's randomness); the same holds here.
- **Fair play cuts both ways.** A recorder that reads every player is a spectator, never a seat's tool.
- **Licence.** Vox Deorum is CC BY-NC-SA 4.0 (its DLL GPL 3.0). Reusing field names and a published method is
  not reusing code, but any code taken from them carries those terms.

## First steps, if this goes ahead

1. Check whether CivBench's code, configurations and the 777 MB statistics are public, and read the feature code.
2. A recorder prototype: one row per player per turn with their `PlayerSummaries` fields, written from a replay
   of an existing save (read-only), compared field by field with what the game's own screens show.
3. One unattended AI-only game on stock rules, start to victory screen, recorded. That proves or kills way 2's
   baseline and the training set.
4. Write to the authors (the paper lists contact addresses) once 1 to 3 are known: whether a stock-rules,
   full-control track is something they would want beside theirs, and what a submission would have to contain.

## Decided (the user, 2026-11-13)

- **Vox Populi is not in scope.** Way 3 is dropped.
- **The project writes its own benchmark**, which can optionally be run with this harness. The reason is the
  harness's own premise: the agent sits in a human seat, can do only what a human can do, sees only what a human
  sees, and has to play anyway. That is a better foundation for a long-horizon benchmark than setting a strategy
  for a rule-based AI to carry out.
- What is borrowed from CivBench is method (progress instead of win/loss, ratings fitted over games, the built-in AI as the baseline), not code or data. The design sketch and its open problem, how to make scores comparable across
  maps, civilizations and victory types, are in `docs/BENCHMARK.md`.

Still open: how much unattended machine time for AI-only games is acceptable.
