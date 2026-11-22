#!/usr/bin/env python3
"""Play one starting save with the game's own AI on the seat, several times, and write what came of each run.

A starting save is a save file and a seat (docs/BENCHMARK.md). This loads the save, reads every major civilization's
indicators, hands the seat to the engine for `--turns` turns (`Game.SetAIAutoPlay`, the call of the game's
debug panel), reads the indicators again when the seat comes back, writes one JSON row and leaves for the main
menu. It costs no tokens. The rows are the built-in AI baseline of a starting save and say how much a starting save's result
varies from run to run.

    scripts/benchmark_run.py --save "Pacal_0242 maya-t242-before-185-check" --turns 10 --runs 10 \
        --out logs/boards/maya-t242/baseline.jsonl
    scripts/benchmark_run.py --summary logs/boards/maya-t242/baseline.jsonl

A player other than the game's AI is a command after `--`: the same two reads, with the command between
them in place of the engine. The command plays the seat (a seat loop, `scripts/play_loop.py`) and ends;
`--player` names the player in the row, and `--turns` is the turns the starting save must have moved on.

    scripts/benchmark_run.py --save "Pacal_0242 maya-t242-before-185-check" --turns 10 --player codex/gpt-6.1-sol \
        --notebook logs/bench191/notebook-before.json --claim-wait 200 --out logs/boards/maya-t242/rows.jsonl \
        -- scripts/llm_seat_loop.py --agent codex --seat 0 --dir ../grok-desk-seat --model gpt-6.1-sol \
           --turns {turns} --until-turn {until} --cycles 1 --log-dir logs/boards/maya-t242/codex-{seed}

`{seed}`, `{turns}` and `{until}` in the command are the seed's number, the turns, and the game turn that is the
seat's when its turns are over (the save's turn plus the turns asked): the player is told that turn.

Seeds: a player's nth run on a starting save is seed n. Before anyone plays, 16,000,048 n random numbers are
generated and thrown away (the skip), so seed n is the same game for every player and two seeds share no random
numbers (a save replays the same game otherwise). The seat's notebook is the one given (`--notebook FILE`, or `none`
for a seat that takes the starting save over cold), the one the player leaves is kept beside the rows, and the one
that was on disk before the run is put back after it.

Operator-side only: it sends Lua text to the game, which a seat's connection may not (it needs the plain tunerd,
no seat table), and it reads every player, which no seat may. Nothing here is reachable from the nine tools.

What became of a run is `result`: `finished` (the turns played, or the game decided inside them), `did_not_finish` (the
player did not bring the seat to the end of its turns: it stopped, or ran out of time) or `void` (the engine
stalled or did not take the seat: not the player's doing, played again). With `--ai-finishes R` a finished run is
valued: the game is saved at the end of the turns and the engine's AI finishes it R times, and `value` is the share
the seat's team wins. A run that did not finish has no value; it is counted beside the value and stands below every
finished run.

What it will not do (each seen live 2026-11-16, docs/BENCHMARK.md "Autoplay, checked live"):

- Start on a starting save with no observer slot beside the seat. The engine then makes the seat itself the observer
  and destroys its units, with no error.
- Start with more than one human seat: autoplay is unseen in hotseat.
- Trust the game to stop. A win does not end the run and a dead seat leaves the game playing turns by itself,
  so the run is watched and the game is left for the main menu when it ends.

The engine plays the seat with the AI bonuses of the save's difficulty (at Prince nearly none) on the human's
own handicap row; `handicap` is in every row for that reason. Every real AI plays on another row
(HANDICAP_AI_DEFAULT), so a starting save is made to carry its terms before anyone plays it:

    scripts/benchmark_run.py --save board-duel-prince-a-t0 --terms board-duel-prince-a-t0-airow

loads the hosted save, puts the seat on the AIs' row, switches the Time victory off, and saves it under the new
name. A save keeps both, so every player's turns on that starting save and every AI finish are played on the same terms.
`--row ai` and `--time off` do the same at the hand-over, for a save that was not made that way.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SS_COMPUTER, SS_TAKEN, SS_OBSERVER = 1, 3, 4
# What a row keeps per civilization. `score` is the engine's own; the rest are the plain indicators the
# benchmark sketch names, reported side by side with no claim that they add up.
INDICATORS = ("score", "techs", "policies", "cities", "population", "military", "land", "gold", "science", "happiness")
# Where a player stands on the routes to a victory that the indicators do not show: city-states allied, delegates in
# the World Congress (none before one sits) and tourism a turn. A point of a path keeps them beside the indicators.
# A seat behind on score at every read of its game won by the vote with 12 delegates against 6 (live 2026-11-18).
ROUTES = ("allies", "delegates", "tourism")

READ = """
local out = {turn = Game.GetGameTurn(), state = Game.GetGameState(), winner = Game.GetWinner(), victory = "",
  auto = Game.GetAIAutoPlay(), active = Game.GetActivePlayer(), max_turns = Game.GetMaxTurns(),
  handicap = GameInfo.HandicapInfos[Game.GetHandicapType()].Type, speed = GameInfo.GameSpeeds[Game.GetGameSpeedType()].Type,
  slots = {}, players = {}}
local v = Game.GetVictory()
if v ~= nil and v >= 0 and GameInfo.Victories[v] then out.victory = GameInfo.Victories[v].Type end
local league = Game.GetNumActiveLeagues() > 0 and Game.GetActiveLeague() or nil
for i = 0, GameDefines.MAX_MAJOR_CIVS - 1 do
  out.slots[#out.slots + 1] = PreGame.GetSlotStatus(i)
  local p = Players[i]
  if p and p:IsEverAlive() and PreGame.GetSlotStatus(i) ~= 4 then
    local team = Teams[p:GetTeam()]
    local techs, policies = 0, 0
    for row in GameInfo.Technologies() do if team:IsHasTech(row.ID) then techs = techs + 1 end end
    for row in GameInfo.Policies() do if p:HasPolicy(row.ID) then policies = policies + 1 end end
    local allies = 0
    for m = GameDefines.MAX_MAJOR_CIVS, GameDefines.MAX_CIV_PLAYERS - 1 do
      local c = Players[m]
      if c and c:IsAlive() and c:IsMinorCiv() and c:GetAlly() == i then allies = allies + 1 end
    end
    out.players[#out.players + 1] = {id = i, civ = p:GetCivilizationShortDescription(), alive = p:IsAlive(),
      human = p:IsHuman(), team = p:GetTeam(), turn_active = p:IsTurnActive(), score = p:GetScore(), techs = techs, policies = policies, cities = p:GetNumCities(),
      population = p:GetTotalPopulation(), military = p:GetMilitaryMight(), land = p:GetNumPlots(),
      gold = p:GetGold(), science = p:GetScience(), happiness = p:GetExcessHappiness(), allies = allies,
      delegates = league and league:CalculateStartingVotesForMember(i) or 0, tourism = p:GetTourism()}
  end
end
return out
"""

# The skip moves the game's random sequence on before the engine plays, so two runs of one save need not be one run.
START = """
for _ = 1, %(skip)d do Game.Rand(100, "benchmark_run") end
%(terms)sGame.SetAIAutoPlay(%(turns)d, %(seat)d)
return {auto = Game.GetAIAutoPlay(), active = Game.GetActivePlayer(), slot = PreGame.GetSlotStatus(%(seat)d),
  human = Players[%(seat)d]:IsHuman(), units = Players[%(seat)d]:GetNumUnits(), cities = Players[%(seat)d]:GetNumCities(),
  seat_row = GameInfo.HandicapInfos[Players[%(seat)d]:GetHandicapType()].Type,
  time_victory = Game.IsVictoryValid(GameInfoTypes.VICTORY_TIME)}
"""

# The terms the engine plays on (docs/BENCHMARK.md, "The seat's row"). A real AI never plays on the human's difficulty
# row: at any difficulty it has HANDICAP_AI_DEFAULT (base happiness 15 against Prince's 9, research at 85%, policies at
# 75%). An engine-played seat keeps the human's row and lost every full AI game on the first two Prince starting saves. With
# `ai` the seat is put on the AIs' row in the call that hands it over; the values a player caches (happiness, policy
# cost) follow within the first turns (live 2026-11-17: all equal to the AIs' by turn 12). The setup screen cannot do
# it: a human hosted on HANDICAP_AI_DEFAULT starts on Chieftain, and so does the game.
ROW_AI = "PreGame.SetHandicap(%(seat)d, GameInfo.HandicapInfos.HANDICAP_AI_DEFAULT.ID)\n"
# With Time valid a game stops at the speed's last turn for the highest score. `off` plays on to a real victory. The
# validity alone does not do it: with only `SetVictoryValid` a duel still ended by Time at turn 330; with the turn
# limit cleared as well two games from a turn-325 save ran on to a Diplomatic victory at turn 372 (live 2026-11-17).
TIME_OFF = "Game.SetVictoryValid(GameInfoTypes.VICTORY_TIME, false)\nPreGame.SetMaxTurns(0)\n"


def start_chunk(skip: int, turns: int, seat: int, row: str = "own", time: str = "on") -> str:
    terms = (ROW_AI % {"seat": seat} if row == "ai" else "") + (TIME_OFF if time == "off" else "")
    return START % {"skip": skip, "turns": turns, "seat": seat, "terms": terms}

POLL = """
return {turn = Game.GetGameTurn(), auto = Game.GetAIAutoPlay(), winner = Game.GetWinner(), state = Game.GetGameState(),
  alive = Players[%(seat)d]:IsAlive(), active = Game.GetActivePlayer(), turn_active = Players[%(seat)d]:IsTurnActive(),
  team = Players[%(seat)d]:GetTeam(), victory = (Game.GetVictory() or -1) >= 0 and GameInfo.Victories[Game.GetVictory()].Type or "",
  cities = Players[%(seat)d]:GetNumCities(), wars = (function()
    local n, mine = 0, Teams[Players[%(seat)d]:GetTeam()]
    for i = 0, GameDefines.MAX_MAJOR_CIVS - 1 do
      local p = Players[i]
      if i ~= %(seat)d and p:IsAlive() and mine:IsAtWar(p:GetTeam()) then n = n + 1 end
    end
    return n
  end)()}
"""

SKIP = """
for _ = 1, %(skip)d do Game.Rand(100, "benchmark_run") end
return {skip = %(skip)d}
"""

BUILT_IN_AI = "built-in-ai"
THE_SAVE = "save"               # the player name of a --finish-only row: the save itself, finished by the engine's AI
# Every game has a stretch of the engine's random sequence to itself (2026-11-20, docs/BENCHMARK.md "A skip has to
# be longer than a game"). The generator is one 32-bit sequence and a skip only moves along it. Runs whose skips are
# close use the same numbers for the same purposes from the first barbarian-camp placement on (a loop that generates numbers
# until a tile is valid takes up the difference), so they are one game or nearly one: skips 6 and 7 shared 1171 of
# 1179 random numbers in ten turns. A full AI game used 42,263 numbers (one game, to turn 380), so a stretch is a million. A
# seed's game starts 16 stretches times the seed along; AI finish m starts (m + 1) stretches on from the point
# its save holds, never none, so no AI finish replays the save as it is, and never 16, the next seed's start.
# Rows before this date were played at 17 random numbers a seed and 29 an AI finish; every row carries its own `skip`.
NUMBERS_A_GAME = 1_000_003
GAMES_A_SEED = 16
NUMBERS_A_SEED = NUMBERS_A_GAME * GAMES_A_SEED
NUMBERS_AN_AI_FINISH = NUMBERS_A_GAME
SEQUENCE = 2 ** 32            # the generator's period: past it a skip is back on stretches already used
TO_THE_END = 1000             # turns asked of the engine in an AI finish: more than any game has left


LEAVE = """
Events.ExitToMainMenu()
return {ok = true}
"""


def leave(g) -> None:
    """Leave the loaded game for the main menu. The harness's own exit is a seat's: while the engine plays the seat
    the observer is the active player and the exit answers "this seat is not active". A run that ended on a win
    left its game up that way and the engine played on past turn 380 (live 2026-11-16, the user watching). The
    runner is no seat and asks the game itself."""
    reply = g.leave_to_main_menu()
    if isinstance(reply, dict) and reply.get("ok") is False:
        try:
            g.q(LEAVE)
        except Exception:   # the InGame state is torn down under the call: the reply may never come
            pass


class Refused(Exception):
    """The starting save cannot be run as asked; nothing was changed in the game."""


def find_seat(read: dict, seat: int | None) -> int:
    """The seat to hand over: the one named, else the only human. More than one human is refused."""
    humans = [p["id"] for p in read["players"] if p["human"]]
    if len(humans) != 1:
        raise Refused(f"the starting save has {len(humans)} human seats ({humans}); autoplay is checked with one")
    if seat is not None and seat != humans[0]:
        raise Refused(f"seat {seat} is not the human seat of this starting save ({humans[0]})")
    return humans[0]


def check_observer_slot(read: dict, seat: int) -> None:
    """Refuse a starting save with no observer slot beside the seat: the engine would make the seat the observer and
    destroy its units and cities in the same call."""
    if not any(s == SS_OBSERVER for i, s in enumerate(read["slots"]) if i != seat):
        raise Refused("no slot of this game is an observer slot (status 4): autoplay would destroy the seat. "
                      "Host the starting save from the single-player setup screen with its unused slots as it leaves them")


def seat_view(read: dict, seat: int) -> dict:
    """The seat's indicators, each with its share of the living major civilizations' total, and its place by score."""
    me = next(p for p in read["players"] if p["id"] == seat)
    living = [p for p in read["players"] if p["alive"]]
    out: dict = {"turn": read["turn"], "alive": me["alive"], "turn_active": bool(me.get("turn_active")),
                 "team": me.get("team"), "values": {}, "share": {}}
    for k in INDICATORS:
        out["values"][k] = me[k]
        total = sum(max(p[k], 0) for p in living)
        out["share"][k] = round(max(me[k], 0) / total, 4) if total and me["alive"] else 0.0
    out["place"] = 1 + sum(1 for p in living if p["score"] > me["score"]) if me["alive"] else None
    out["of"] = len(living)
    return out


def saves_dir() -> Path:
    """Where the game keeps single-player saves; a save is loaded by its bare name from here."""
    return Path(os.environ.get("CIV5_SAVES_DIR")
                or Path.home() / ".local/share/Aspyr/Sid Meier's Civilization 5/Saves/single")


def save_as(g, name: str, sleep=time.sleep, clock=time.monotonic, wait: float = 30.0) -> str:
    """Save the loaded game under `name`: the game's own quick save, then a copy of its file. The quick slot is
    the only save the engine writes on request."""
    quick = saves_dir() / "quick" / "QuickSave.Civ5Save"
    was = quick.stat().st_mtime_ns if quick.exists() else 0
    reply = g.quick_save()
    if not (isinstance(reply, dict) and reply.get("ok")):
        raise Refused(f"the quick save was refused: {reply}")
    t0, size = clock(), -1
    while True:
        now = quick.stat() if quick.exists() else None
        if now and now.st_mtime_ns != was and now.st_size == size:
            break                                   # written, and the same size at two looks
        size = now.st_size if now and now.st_mtime_ns != was else -1
        if clock() - t0 > wait:
            raise Refused("the quick save was not written")
        sleep(0.5)
    shutil.copyfile(quick, saves_dir() / f"{name}.Civ5Save")
    return name


TERMS = """
%(terms)s
return {seat_row = GameInfo.HandicapInfos[Players[%(seat)d]:GetHandicapType()].Type,
  time_victory = Game.IsVictoryValid(GameInfoTypes.VICTORY_TIME), max_turns = Game.GetMaxTurns()}
"""


def with_terms(g, save: str, new: str, seat: int | None = None, row: str = "ai", time_victory: str = "off",
               save_game=save_as) -> dict:
    """A starting save that carries its terms: `save` loaded, the seat put on the AIs' row and the Time victory switched off,
    and the game saved as `new`. A save keeps both (live 2026-11-17: read back after a reload), so on such a starting save
    every player's turns, the built-in AI's and every AI finish are played on the same terms with no lever at
    the hand-over. Says what the game reads after the change."""
    loaded = g.load_save(save)
    if not loaded.get("ok"):
        raise Refused(f"the save did not load: {loaded.get('err') or loaded}")
    try:
        before = g.q(READ)
        seat = find_seat(before, seat)
        check_observer_slot(before, seat)
        terms = (ROW_AI % {"seat": seat} if row == "ai" else "") + (TIME_OFF if time_victory == "off" else "")
        out = dict(g.q(TERMS % {"terms": terms, "seat": seat}))
        out.update(save=save_game(g, new), made_from=save, seat=seat, turn=before["turn"])
        return out
    finally:
        leave(g)


def keep_end(g, row: dict, name: str | None, save_game, sleep, clock) -> None:
    """The position the played turns ended on, saved for the AI finishes (rule 1)."""
    if not name or row.get("end_reason") != "all_turns_played":
        return
    try:
        row["end_save"] = save_game(g, name, sleep=sleep, clock=clock)
    except Refused as e:
        row["end_save"], row["end_save_error"] = None, str(e)


def ai_finish(g, save: str, m: int, seat: int | None = None, poll: float = 3.0, stall: float = 900.0,
              row: str = "own", time_victory: str = "on", stop_turn: int | None = None, path_every: int = 0,
              sleep=time.sleep, clock=time.monotonic, say=lambda _line: None) -> dict:
    """One game played on from `save` to its end by the game's own AI on every seat. Says whether the seat's team
    took the victory. It ends on a victory, on the seat's death (a game lost, whoever wins it later) or on a stall,
    and leaves for the main menu, since the engine would play on past all three.

    With `path_every` N the game keeps its path: every player's indicators where it starts and at the first poll
    of every N turns after. A path with the game's outcome is what the win-chance formula is fitted on (rule 1)."""
    if not 0 <= m < GAMES_A_SEED - 1:
        raise Refused(f"AI finish {m} would start on another seed's stretch of the random sequence: a save has "
                      f"AI finishes 0 to {GAMES_A_SEED - 2}")
    loaded = g.load_save(save)
    if not loaded.get("ok"):
        raise Refused(f"the save did not load: {loaded.get('err') or loaded}")
    before = g.q(READ)
    try:
        seat = find_seat(before, seat)
        check_observer_slot(before, seat)
    except Refused:
        leave(g)
        raise
    skip = NUMBERS_AN_AI_FINISH * (m + 1)
    t0 = clock()
    out: dict = {"m": m, "skip": skip, "seat": seat, "from_turn": before["turn"], "end_reason": None, "won": False}
    if path_every:
        out["path"] = [path_point(before)]
    try:
        started = g.q(start_chunk(skip, TO_THE_END, seat, row, time_victory))
        out.update(seat_row=started.get("seat_row"), time_victory=started.get("time_victory"))
        if started["slot"] != SS_COMPUTER or started["active"] == seat:
            out["end_reason"] = "not_handed_over"
            return out
        last_turn, last_change = before["turn"], clock()
        while True:
            sleep(poll)
            now = g.q(POLL % {"seat": seat})
            if now["turn"] != last_turn:
                if path_every and now["turn"] // path_every > last_turn // path_every and now["winner"] < 0:
                    out["path"].append(path_point(g.q(READ)))
                if now["turn"] // 25 > last_turn // 25:     # a turn can pass between two polls: said on passing, not on landing
                    say(f"    AI finish {m}: turn {now['turn']}  +{clock() - t0:.0f}s")
                last_turn, last_change = now["turn"], clock()
            # beside the result, never in it: when the seat was first at war with a major, and the most cities it held
            if now.get("wars") and "first_war_turn" not in out:
                out["first_war_turn"] = now["turn"]
            out["most_cities"] = max(out.get("most_cities", 0), now.get("cities", 0))
            if now["winner"] >= 0:
                out.update(end_reason="victory", won=now["winner"] == now["team"], winner=now["winner"], victory=now["victory"])
            elif not now["alive"]:
                out["end_reason"] = "seat_dead"
            elif now["auto"] == 0:
                out["end_reason"] = "count_out"
            elif stop_turn is not None and now["turn"] >= stop_turn:
                out["end_reason"] = "turn_limit"      # no victory by the turn the runner stops at: not decided
            elif clock() - last_change > stall:
                out["end_reason"] = "stalled"
            if out["end_reason"]:
                out.update(turn=now["turn"], seconds=round(clock() - t0, 1))
                if out["end_reason"] in DECIDED + ("turn_limit",):
                    # how the game stood: a win by Time is the higher score, and by how much says how near the seat was
                    out["players"] = [{k: p[k] for k in ("id", "civ", "alive", "score", "techs", "cities")}
                                      for p in g.q(READ)["players"]]
                return out
    finally:
        leave(g)


def path_point(read: dict) -> dict:
    """One point of a game's path: the turn it was read on (the engine plays on while it is read, so the turn is the
    read's own) and every player's indicators and standing on the routes. A run's row keeps the point its turns end on
    (`end_point`): what the win-chance formula values the run by."""
    return {"turn": read["turn"],
            "players": [{k: p[k] for k in ("id", "alive", *INDICATORS, *ROUTES)} for p in read["players"]]}


DECIDED = ("victory", "seat_dead")
# What became of a run (rule 5). Did-not-finish is a result of its own: the player did not bring the seat to the
# end of the turns. It has no value, it is counted and shown, and in any ordering it stands below every finished
# run, so that stopping never does better than playing. Void is not the player's doing and is played again.
FINISHED = ("all_turns_played", "game_won", "seat_dead", "finish_only")
NOT_FINISHED = ("turns_not_played", "timeout")
VOID = ("stalled", "not_handed_over")


def result_of(row: dict) -> str:
    reason = row.get("end_reason")
    return "finished" if reason in FINISHED else "did_not_finish" if reason in NOT_FINISHED else "void"


def value_of(row: dict, ai_finishes: list[dict]) -> float | None:
    """Rule 1. Only a finished run has a value. A game decided inside the turns is 1 for the seat's team and 0
    otherwise, a seat that died in them 0. Played turns (or a save valued as it is) are worth the share of the decided
    AI finishes the seat won; none decided is no value."""
    reason = row.get("end_reason")
    if result_of(row) != "finished":
        return None
    if reason == "game_won":
        return 1.0 if row.get("winner") == (row.get("end") or {}).get("team") else 0.0
    if reason == "seat_dead":
        return 0.0
    decided = [c for c in ai_finishes if c.get("end_reason") in DECIDED]
    return round(sum(1 for c in decided if c["won"]) / len(decided), 4) if decided else None


def run_once(g, save: str, turns: int, seat: int | None = None, skip: int = 0, poll: float = 3.0, stall: float = 900.0,
             end_save: str | None = None, save_game=save_as, row: str = "own", time_victory: str = "on",
             sleep=time.sleep, clock=time.monotonic, say=lambda _line: None) -> dict:
    """One run of the starting save by the game's own AI. Loads `save` (the game must be at the main menu), hands the seat over, watches, reads,
    and leaves for the main menu whatever happened once the seat was handed over."""
    loaded = g.load_save(save)
    if not loaded.get("ok"):
        raise Refused(f"the save did not load: {loaded.get('err') or loaded}")
    before = g.q(READ)
    try:
        seat = find_seat(before, seat)
        check_observer_slot(before, seat)
    except Refused:
        leave(g)
        raise
    t0 = clock()
    started = g.q(start_chunk(skip, turns, seat, row, time_victory))
    row: dict = {"player": BUILT_IN_AI, "save": save, "seat": seat, "turns_asked": turns, "skip": skip,
                 "handicap": before["handicap"], "speed": before["speed"], "start": seat_view(before, seat),
                 "seat_row": started.get("seat_row"), "time_victory": started.get("time_victory"),
                 "end_reason": None, "win_turn": None}
    try:
        if started["slot"] != SS_COMPUTER or started["active"] == seat:
            row["end_reason"] = "not_handed_over"
            row["handed_over"] = started
            return row
        last_turn, last_change, now = before["turn"], clock(), None
        while True:
            sleep(poll)
            now = g.q(POLL % {"seat": seat})
            if now["turn"] != last_turn:
                last_turn, last_change = now["turn"], clock()
                say(f"  turn {now['turn']}  count {now['auto']}  +{clock() - t0:.0f}s")
            if now["winner"] >= 0 and row["win_turn"] is None:
                row["win_turn"] = now["turn"]
            if not now["alive"]:
                row["end_reason"] = "seat_dead"
            elif now["winner"] >= 0:
                row["end_reason"] = "game_won"
            elif now["auto"] == 0:
                row["end_reason"] = "all_turns_played"
            elif clock() - last_change > stall:
                row["end_reason"] = "stalled"
            if row["end_reason"]:
                break
        after = g.q(READ)
        row.update(seconds=round(clock() - t0, 1), end=seat_view(after, seat), winner=after["winner"],
                   victory=after["victory"], turns_played=after["turn"] - before["turn"],
                   players=[{k: p[k] for k in ("id", "civ", "alive", "score")} for p in after["players"]],
                   end_point=path_point(after))
        keep_end(g, row, end_save, save_game, sleep, clock)
        return row
    finally:
        leave(g)


def notebook_path(g, seat: int) -> Path:
    """Where the harness keeps this game's notebook for the seat."""
    g.seat = seat
    return g.notebook().path


def run_player(g, save: str, command: list[str], label: str, turns: int, seat: int | None = None, skip: int = 0,
               notebook: str | None = None, keep_notebook: Path | None = None, claim_wait: float = 0.0,
               timeout: float = 4 * 3600.0, settle: float = 120.0, poll: float = 3.0, run=subprocess.run,
               end_save: str | None = None, save_game=save_as,
               path_of=notebook_path, sleep=time.sleep, clock=time.monotonic) -> dict:
    """One run of the starting save by a command that plays the seat and ends. Loads `save`, reads, puts the player's
    notebook in place, runs the command, reads, and leaves for the main menu with the notebook that was on disk
    before put back. The command's own exit code is in the row and decides nothing: the run played its turns
    when the game is `turns` turns on, whatever the command said (a scripted loop gave up at a World Congress
    proposal four turns into ten and its row read like any other, live 2026-11-16)."""
    loaded = g.load_save(save)
    if not loaded.get("ok"):
        raise Refused(f"the save did not load: {loaded.get('err') or loaded}")
    before = g.q(READ)
    try:
        seat = find_seat(before, seat)
        if notebook not in (None, "none") and not Path(notebook).is_file():
            raise Refused(f"no notebook file {notebook!r}")
    except Refused:
        leave(g)
        raise
    nb = path_of(g, seat)
    standing = nb.read_bytes() if nb.exists() else None
    # the turn that is the seat's when its turns are over (rule 5: the player is told the turn, not a count)
    command = [part.replace("{until}", str(before["turn"] + turns)) for part in command]
    row: dict = {"player": label, "command": command, "save": save, "seat": seat, "turns_asked": turns, "skip": skip,
                 "notebook": notebook or "standing", "handicap": before["handicap"], "speed": before["speed"],
                 "start": seat_view(before, seat), "end_reason": None, "rc": None}
    try:
        if notebook == "none":
            nb.unlink(missing_ok=True)
        elif notebook:
            nb.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(notebook, nb)
        if skip:
            g.q(SKIP % {"skip": skip})
        sleep(claim_wait)
        t0 = clock()
        try:
            row["rc"] = run(command, timeout=timeout, check=False).returncode
        except subprocess.TimeoutExpired:
            row["end_reason"] = "timeout"
        row["seconds"] = round(clock() - t0, 1)
        # The command may end while the other players still move: the read waits for the seat's turn.
        waited = 0.0
        while True:
            now = g.q(POLL % {"seat": seat})
            if now["turn_active"] or not now["alive"] or now["winner"] >= 0 or waited >= settle:
                break
            sleep(poll)
            waited += poll
        after = g.q(READ)
        end = seat_view(after, seat)
        if not end["alive"]:
            row["end_reason"] = "seat_dead"
        elif after["winner"] >= 0:
            row["end_reason"] = "game_won"
        elif row["end_reason"] is None:
            row["end_reason"] = "all_turns_played" if after["turn"] - before["turn"] == turns else "turns_not_played"
        row.update(end=end, winner=after["winner"], victory=after["victory"], turns_played=after["turn"] - before["turn"],
                   players=[{k: p[k] for k in ("id", "civ", "alive", "score")} for p in after["players"]],
                   end_point=path_point(after))
        keep_end(g, row, end_save, save_game, sleep, clock)
        if keep_notebook is not None and nb.exists():
            keep_notebook.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(nb, keep_notebook)
            row["notebook_after"] = str(keep_notebook)
        return row
    finally:
        if standing is None:
            nb.unlink(missing_ok=True)
        else:
            nb.write_bytes(standing)
        leave(g)


def mean_sd(xs: list[float]) -> tuple[float, float]:
    m = sum(xs) / len(xs)
    return m, (math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) if len(xs) > 1 else 0.0)


def player_of(row: dict) -> str:
    return row.get("player") or BUILT_IN_AI


def summarise_player(name: str, rows: list[dict]) -> list[str]:
    """One player on one starting save. Per indicator: the seat's value at the start, and over the runs that played
    their turns the value at the end as mean, standard deviation, least and most, then the spread as a share
    of the mean gain."""
    done = [r for r in rows if r.get("end_reason") == "all_turns_played"]
    lines = [f"{name}: {len(rows)} runs, {len(done)} played their turns"
             + "".join(f", {n} {why}" for why in ("seat_dead", "game_won", *NOT_FINISHED, *VOID)
                       if (n := sum(1 for r in rows if r.get("end_reason") == why)))]
    if not done:
        return lines + value_lines(rows)
    first = done[0]
    turns = sorted({r.get("turns_played", r.get("turns_asked")) for r in done})
    lines.append(f"save {first['save']!r}, seat {first['seat']}, {first['handicap']}, "
                 f"{turns[0] if len(turns) == 1 else f'{turns[0]} to {turns[-1]}'} turns, "
                 f"{mean_sd([r['seconds'] for r in done])[0]:.0f} s a run")
    lines.append(f"{'':12}{'start':>8}{'mean':>9}{'sd':>8}{'min':>8}{'max':>8}{'sd/gain':>9}   share of the living, mean (sd)")
    for k in INDICATORS:
        ends = [r["end"]["values"][k] for r in done]
        m, sd = mean_sd(ends)
        start = first["start"]["values"][k]
        gain = m - start
        sm, ssd = mean_sd([r["end"]["share"][k] for r in done])
        lines.append(f"{k:12}{start:>8}{m:>9.1f}{sd:>8.1f}{min(ends):>8}{max(ends):>8}"
                     f"{(f'{sd / abs(gain):.2f}' if abs(gain) > 1e-9 else '-'):>9}   {sm:.3f} ({ssd:.3f})")
    places = [r["end"]["place"] for r in done]
    lines.append(f"place by score: {', '.join(str(p) for p in places)} of {done[0]['end']['of']}")
    lines += value_lines(rows)
    if len({json.dumps(r["end"]["values"], sort_keys=True) for r in done}) == 1 and len(done) > 1:
        lines.append("every run ended on the same values: the save replays the same game")
    return lines


def pooled_lines(rows: list[dict], games: list[dict]) -> list[str]:
    """Every decided AI finish as one game: the share the seat won; and the AI finishes the stop turn left
    undecided, which are in no share and are counted here. No error is given over games: the games of one seed go
    together (live 2026-11-18, two seeds were 0 of 5 and 5 of 5 with the seat the same in both), so
    the error of a value is the one over seeds, on the line above."""
    lines = []
    if games:
        won = sum(1 for c in games if c.get("won"))
        lines.append(f"games: the seat won {won} of {len(games)} decided, {won / len(games):.3f}")
    undecided = [c for r in rows for c in r.get("ai_finishes", []) if c.get("end_reason") == "turn_limit"]
    if undecided:
        lines.append(f"not decided by the stop turn: {len(undecided)} "
                     f"(turn {', '.join(str(c.get('turn')) for c in undecided)}), in no share")
    return lines


def with_later_finishes(rows: list[dict], later: list[dict]) -> tuple[list[dict], list[str]]:
    """The runs with the AI finishes that were played afterwards on their end saves counted in. A later finish is in a
    `--finish-only` row whose `save` is a run's `end_save`; it joins that run unless the run already has a finish of
    the same number m (the same number is the same game), and the run's value is taken again over all of them. Also
    the saves of later rows that are no run's end save, which are in nothing."""
    by_save: dict[str, list[dict]] = {}
    for r in later:
        if r.get("end_reason") == "finish_only" and r.get("save"):
            by_save.setdefault(r["save"], []).extend(r.get("ai_finishes") or [])
    out, used = [], set()
    for r in rows:
        more = by_save.get(r.get("end_save") or "")
        if more:
            used.add(r["end_save"])
            games = list(r.get("ai_finishes") or [])
            have = {c.get("m") for c in games}
            for c in more:
                if c.get("m") not in have:
                    have.add(c.get("m"))
                    games.append(c)
            r = {**r, "ai_finishes": games}
            r["value"] = value_of(r, games)
        out.append(r)
    return out, sorted(set(by_save) - used)


SPREAD_SEEDS = 4          # fewer seeds with two finishes each say nothing about a spread between seeds
TARGET_ERROR = 0.05
FINISHES_ASKED = (1, 5, 15)


def spread_parts(seeds: list[tuple[int, int]]) -> tuple[float, float]:
    """The two parts of the spread of a player's values, as variances, from (games won, games decided) a seed.
    Within a seed: one AI finish is won or lost, and from one end of the turns that varies by p(1 - p), estimated
    a seed as R / (R - 1) times its share won times its share lost. Between seeds: the variance of the seeds'
    shares, less what the finishes alone put into it (the within part over R, a seed), never below 0."""
    shares = [w / r for w, r in seeds]
    within = [r / (r - 1) * (w / r) * (1 - w / r) for w, r in seeds]
    between = mean_sd(shares)[1] ** 2 - sum(v / r for v, (_, r) in zip(within, seeds)) / len(seeds)
    return sum(within) / len(within), max(between, 0.0)


def spread_lines(rows: list[dict], resamplings: int = 2000) -> list[str]:
    """What the turns decide and what the AI finish decides, for the runs with two or more decided AI finishes, and
    what that costs: the seeds a standard error of 0.05 takes at 1, 5 and 15 AI finishes a seed. The value of n seeds
    at R finishes each has the variance (between + within / R) / n, so finishes past a few buy little once the
    between part is the larger, and only seeds bring it down. The range beside the between figure is the middle two
    thirds of the same figure over seeds drawn again from these with replacement: with few seeds it is wide."""
    seeds = []
    for r in rows:
        decided = [c for c in r.get("ai_finishes") or () if c.get("end_reason") in DECIDED]
        if r.get("end_reason") == "all_turns_played" and len(decided) >= 2:
            seeds.append((sum(1 for c in decided if c["won"]), len(decided)))
    if len(seeds) < SPREAD_SEEDS:
        return []
    within, between = spread_parts(seeds)
    rng = random.Random(0)
    again = sorted(math.sqrt(spread_parts([rng.choice(seeds) for _ in seeds])[1]) for _ in range(resamplings))
    lo, hi = again[resamplings // 6], again[-(resamplings // 6) - 1]
    need = ", ".join(f"{math.ceil((between + within / r) / TARGET_ERROR ** 2)} at {r}" for r in FINISHES_ASKED)
    return [f"spread: {len(seeds)} seeds with two or more AI finishes ({sum(r for _, r in seeds)} finishes): from one end of "
            f"the turns a finish varies by {math.sqrt(within):.3f} (within a seed); the chance the turns leave varies by "
            f"{math.sqrt(between):.3f} from seed to seed ({lo:.3f} to {hi:.3f} over resamplings of the seeds)",
            f"seeds for a standard error of {TARGET_ERROR}: {need} AI finishes a seed"]


def value_lines(rows: list[dict]) -> list[str]:
    """The player's value over its finished runs, each run's own, and its runs that did not finish as a count of their own: beside
    the value, never inside its mean. The last figure is the value with each of those as 0, what an ordering uses."""
    values = [r["value"] for r in rows if r.get("value") is not None]
    not_finished = [r for r in rows if result_of(r) == "did_not_finish"]
    lines = []
    if values:
        m, sd = mean_sd(values)
        games = [c for r in rows for c in r.get("ai_finishes", []) if c.get("end_reason") in DECIDED]
        how = sorted({c.get("victory") or "seat_dead" for c in games})
        minutes = f", {mean_sd([c['seconds'] for c in games])[0] / 60:.1f} min each" if games else ""
        lines.append(f"value: {m:.3f} (sd {sd:.3f}) over {len(values)} finished runs and {len(games)} AI finishes{minutes}; "
                     f"by run: {', '.join(f'{v:.2f}' for v in values)}" + (f"; ended by {', '.join(how)}" if how else ""))
        if len(values) > 1:
            lines.append(f"seeds: {len(values)} finished, the value's standard error over them {sd / math.sqrt(len(values)):.3f} "
                         "(the seed is the unit: its games are not independent trials)")
        lines.extend(pooled_lines(rows, games))
        lines.extend(spread_lines(rows))
    if not_finished and (values or any("ai_finishes" in r or "value" in r for r in rows)):
        why = ", ".join(sorted({r["end_reason"] for r in not_finished}))
        lines.append(f"not finished: {len(not_finished)} of {len(not_finished) + len(values)} runs ({why}), below every finished run in an ordering"
                     + (f"; with not finished as 0 the value is {sum(values) / (len(values) + len(not_finished)):.3f}" if values else ""))
    return lines


def summarise(rows: list[dict]) -> list[str]:
    """Every player of a rows file by itself, then the players side by side when there are two or more: the
    mean at the end of the turns and its spread, over the runs that played the turns. Only runs of the same
    number of turns stand side by side."""
    names = list(dict.fromkeys(player_of(r) for r in rows))
    lines: list[str] = []
    for name in names:
        lines += ([""] if lines else []) + summarise_player(name, [r for r in rows if player_of(r) == name])
    played = {name: [r for r in rows if player_of(r) == name and r.get("end_reason") == "all_turns_played"] for name in names}
    played = {name: rs for name, rs in played.items() if rs}
    turns = {r.get("turns_played", r.get("turns_asked")) for rs in played.values() for r in rs}
    if len(played) < 2:
        return lines
    if len(turns) > 1:
        return [*lines, "", f"not side by side: the runs played {', '.join(str(w) for w in sorted(turns))} turns"]
    lines += ["", f"side by side, {turns.pop()} turns, mean (sd) at the end:",
              f"{'':12}" + "".join(f"{f'{name} x{len(rs)}':>24}" for name, rs in played.items())]
    for k in INDICATORS:
        cells = [mean_sd([r["end"]["values"][k] for r in rs]) for rs in played.values()]
        lines.append(f"{k:12}" + "".join(f"{f'{m:.1f} ({sd:.1f})':>24}" for m, sd in cells))
    valued = {name: [r["value"] for r in rows if player_of(r) == name and r.get("value") is not None] for name in played}
    if all(valued.values()):
        lines.append(f"{'value':12}" + "".join(f"{'{:.3f} ({:.3f})'.format(*mean_sd(vs)):>24}" for vs in valued.values()))
        not_finished = [sum(1 for r in rows if player_of(r) == name and result_of(r) == "did_not_finish") for name in played]
        if any(not_finished):
            lines.append(f"{'not finished':12}" + "".join(f"{f'{n} of {n + len(vs)}':>24}" for n, vs in zip(not_finished, valued.values())))
    return lines


def wait_main_menu(g, seconds: float = 120.0) -> None:
    """A load is answered only from the main menu, and leaving a game takes a moment. A game that is still up
    after that is said: every run after it would load into a game the engine is playing."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not g.has_state("InGame") and g.front_end_screen() == "MainMenu":
            return
        time.sleep(2)
    raise Refused("the game did not come back to the main menu; a game may still be running, look at it")


# Rows written before 2026-11-20 name things by the words the scripts then used. They are read in today's words; the
# files stay as they were written.
EARLIER_KEYS = {"entrant": "player", "burn": "skip", "continuations": "ai_finishes"}
EARLIER_VALUES = {"stock-ai": BUILT_IN_AI, "board": THE_SAVE, "window_played": "all_turns_played",
                  "window_not_played": "turns_not_played", "value_only": "finish_only", "dnf": "did_not_finish"}


def in_todays_words(x):
    """A row, or any part of one, with the earlier keys renamed and the earlier names of a player, an end reason and
    a result replaced. Everything else is as it was written."""
    if isinstance(x, list):
        return [in_todays_words(v) for v in x]
    if not isinstance(x, dict):
        return x
    out = {EARLIER_KEYS.get(k, k): in_todays_words(v) for k, v in x.items()}
    for k in ("player", "end_reason", "result"):
        if isinstance(out.get(k), str):
            out[k] = EARLIER_VALUES.get(out[k], out[k])
    return out


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [in_todays_words(json.loads(line)) for line in path.read_text().splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--save", help="the save's bare name, no path and no .Civ5Save")
    ap.add_argument("--turns", type=int, default=10,
                    help="turns to play (default 10): the turns the engine plays the seat, and the turns a command's run must "
                         "have moved the game on to count as played")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--seat", type=int, default=None, help="default: the starting save's one human seat")
    ap.add_argument("--out", type=Path, help="JSON lines, one row a run, appended")
    ap.add_argument("--skip", choices=("none", "seed"), default="seed",
                    help="random numbers generated and thrown away before anyone plays: none, or 16,000,048 times the "
                         "seed's number (default; a player's nth run is seed n), so that runs of one save are separate games")
    ap.add_argument("--stall", type=float, default=900.0, help="seconds without a new turn before a run is given up")
    ap.add_argument("--player", dest="label", help="the player's name in the row, needed with a command")
    ap.add_argument("--notebook", help="the notebook the player starts with: a file, or `none`; default the one on disk")
    ap.add_argument("--claim-wait", type=float, default=0.0,
                    help="seconds to wait before the command; 200 after another client played the seat (its turn claim)")
    ap.add_argument("--timeout", type=float, default=4 * 3600.0, help="seconds before the command is given up")
    ap.add_argument("--ai-finishes", dest="ai_finishes", type=int, default=0, metavar="R",
                    help="value the run (rule 1): save at the end of the turns and let the engine's AI finish the game R times "
                         "from there; the value is the share the seat's team wins")
    ap.add_argument("--row", choices=("own", "ai"), default=None,
                    help="the difficulty row the seat has while the engine plays it: its own (the default: nothing is "
                         "changed), or the AIs' (HANDICAP_AI_DEFAULT, what every real AI plays on). Set at the hand-over, "
                         "so a player's own turns are not touched; a starting save made with --terms carries it for everyone")
    ap.add_argument("--time", choices=("on", "off"), default=None,
                    help="off: the Time victory is switched off when the engine takes the seat, so a game runs to a real "
                         "victory (default on: nothing is changed)")
    ap.add_argument("--last-turn", type=int, default=None, metavar="T",
                    help="an AI finish with no victory by game turn T is stopped there and counts as not decided")
    ap.add_argument("--first-ai-finish", type=int, default=0, metavar="M",
                    help="number the AI finishes from M. AI finish m skips (m + 1) million random numbers and a save replays the "
                         "same game on the same random numbers, so M past the ones already played gives new games of one save")
    ap.add_argument("--path", type=int, default=0, metavar="N",
                    help="keep each AI finish's path: every player's indicators at its start and every N turns "
                         "after, in the row. A path with its game's outcome is what the win-chance formula is fitted on")
    ap.add_argument("--finish-only", action="store_true",
                    help="no turns played: value --save itself by R AI finishes (--ai-finishes R), a starting save's own worth")
    ap.add_argument("--terms", metavar="NEW",
                    help="make a starting save that carries its terms and do nothing else: --save loaded, the seat put on the AIs' "
                         "row and Time switched off (unless --row own, --time on), saved as NEW. Every player's turns and every "
                         "AI finish on NEW is then played on the same terms, a player's included")
    ap.add_argument("--summary", type=Path, metavar="ROWS", help="print the summary of a rows file and do nothing else")
    ap.add_argument("--later", type=Path, nargs="+", metavar="ROWS", default=[],
                    help="with --summary: rows files of --finish-only runs on the end saves of the runs summarised; their "
                         "AI finishes are counted with the run they were played from")
    ap.add_argument("command", nargs=argparse.REMAINDER,
                    help="after `--`: the player, a command that plays the seat and ends; {seed}, {turns} and {until} "
                         "in it are the seed's number, the turns and the game turn at which the turns are over")
    a = ap.parse_args(argv)
    if a.summary:
        rows, stray = with_later_finishes(read_rows(a.summary), [r for path in a.later for r in read_rows(path)])
        print("\n".join(summarise(rows)))
        if stray:
            print(f"\nlater rows on saves that are no run's end save here, in nothing: {', '.join(stray)}")
        return 0
    if a.later:
        ap.error("--later goes with --summary")
    command = a.command[1:] if a.command[:1] == ["--"] else a.command
    if a.terms:
        if not a.save or command:
            ap.error("--terms takes --save and no command")
        from harness.game import Game
        g = Game()
        if g.has_state("InGame"):
            print("a game is loaded: leave it for the main menu first (session main_menu); nothing was done", file=sys.stderr)
            return 2
        try:
            # the levers' defaults are for a run (nothing changed); a starting save made to carry terms carries both
            made = with_terms(g, a.save, a.terms, seat=a.seat, row=a.row or "ai", time_victory=a.time or "off")
        except Refused as e:
            print(f"refused: {e}", file=sys.stderr)
            return 2
        print(json.dumps(made))
        return 0
    if not a.save or not a.out:
        ap.error("--save and --out are needed for a run")
    if command and not a.label or a.label == BUILT_IN_AI:
        ap.error("a command needs --player, the player's name (not built-in-ai)")
    if a.label and not command:
        ap.error("--player names a command's player; give the command after --")
    if a.finish_only and (command or a.ai_finishes < 1):
        ap.error("--finish-only takes --ai-finishes R and no command")
    from harness.game import Game
    g = Game()
    if g.has_state("InGame"):
        print("a game is loaded: leave it for the main menu first (session main_menu); nothing was done", file=sys.stderr)
        return 2
    a.out.parent.mkdir(parents=True, exist_ok=True)
    name = THE_SAVE if a.finish_only else a.label or BUILT_IN_AI
    say = lambda line: print(line, flush=True)
    done = sum(1 for r in read_rows(a.out) if player_of(r) == name)
    for n in range(done, done + a.runs):
        print(f"{name} seed {n}: loading {a.save!r}", flush=True)
        skip = NUMBERS_A_SEED * n if a.skip == "seed" else 0
        if skip + NUMBERS_A_SEED > SEQUENCE:
            print(f"seed {n} is past the end of the random sequence ({SEQUENCE // NUMBERS_A_SEED} seeds fit); "
                  f"nothing more was done", file=sys.stderr)
            return 2
        end_save = f"{a.save}--{''.join(c if c.isalnum() else '-' for c in name)}-seed{n}-end" if a.ai_finishes else None
        try:
            if a.finish_only:
                row = {"player": name, "save": a.save, "seat": a.seat, "turns_asked": 0, "turns_played": 0, "skip": 0,
                       "end_reason": "finish_only", "end_save": a.save}
            elif command:
                keep = a.out.with_name(f"{a.out.stem}-{''.join(c if c.isalnum() else '-' for c in name)}-seed{n}-notebook.json")
                words = [part.replace("{seed}", str(n)).replace("{turns}", str(a.turns)) for part in command]
                row = run_player(g, a.save, words, name, a.turns, seat=a.seat, skip=skip, notebook=a.notebook,
                                 keep_notebook=keep, claim_wait=a.claim_wait, timeout=a.timeout, end_save=end_save)
            else:
                row = run_once(g, a.save, a.turns, seat=a.seat, skip=skip, stall=a.stall, end_save=end_save, say=say,
                               row=a.row or "own", time_victory=a.time or "on")
            if a.ai_finishes:
                row["ai_finishes"] = []
                partial = a.out.with_name(a.out.name + ".partial")
                for m in range(a.first_ai_finish, a.first_ai_finish + a.ai_finishes) if row.get("end_save") else ():
                    wait_main_menu(g)
                    c = ai_finish(g, row["end_save"], m, seat=a.seat, stall=a.stall, say=say, row=a.row or "own",
                                  time_victory=a.time or "on", stop_turn=a.last_turn, path_every=a.path)
                    row["ai_finishes"].append(c)
                    partial.write_text(json.dumps(row) + "\n")   # a game that dies under a later one loses none of these
                    print(f"  AI finish {m}: {c['end_reason']}, {'won' if c['won'] else 'not won'}"
                          f"{' by ' + c['victory'] if c.get('victory') else ''}, turn {c.get('turn')}, {c.get('seconds')} s",
                          flush=True)
                row["value"] = value_of(row, row["ai_finishes"])
            row["result"] = result_of(row)
        except Refused as e:
            print(f"refused: {e}", file=sys.stderr)
            return 2
        row.update(run=n, at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        with a.out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        a.out.with_name(a.out.name + ".partial").unlink(missing_ok=True)
        print(f"{name} seed {n}: {row['end_reason']}, {row.get('turns_played')} turns in {row.get('seconds')} s, score "
              f"{row.get('start', {}).get('values', {}).get('score')} -> {row.get('end', {}).get('values', {}).get('score')}"
              + (f", value {row['value']}" if row.get("value") is not None else ""), flush=True)
        wait_main_menu(g)
    print("\n".join(summarise(read_rows(a.out))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
