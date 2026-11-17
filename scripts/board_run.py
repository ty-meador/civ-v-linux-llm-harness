#!/usr/bin/env python3
"""Play one board with the game's own AI on the seat, several times, and write what came of each run.

A board is a save file and a seat (docs/BENCHMARK.md). This loads the save, reads every major civilization's
indicators, hands the seat to the engine for `--turns` turns (`Game.SetAIAutoPlay`, the call of the game's
debug panel), reads the indicators again when the seat comes back, writes one JSON row and leaves for the main
menu. It costs no tokens. The rows are the stock-AI anchor of a board and say how much a board's result
varies from run to run.

    scripts/board_run.py --save "Pacal_0242 maya-t242-before-185-check" --turns 10 --runs 10 \
        --out logs/boards/maya-t242/anchor.jsonl
    scripts/board_run.py --summary logs/boards/maya-t242/anchor.jsonl

Operator-side only: it sends Lua text to the game, which a seat's connection may not (it needs the plain tunerd,
no seat table), and it reads every player, which no seat may. Nothing here is reachable from the nine tools.

What it will not do (each seen live 2026-11-16, docs/BENCHMARK.md "Autoplay, checked live"):

- Start on a board with no observer slot beside the seat. The engine then makes the seat itself the observer
  and destroys its units, with no error.
- Start with more than one human seat: autoplay is unseen in hotseat.
- Trust the game to stop. A win does not end the run and a dead seat leaves the game playing turns by itself,
  so the run is watched and the game is left for the main menu when it ends.

The engine plays the seat with the AI bonuses of the save's difficulty (at Prince nearly none) on the human's
own handicap row; `handicap` is in every row for that reason.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SS_COMPUTER, SS_TAKEN, SS_OBSERVER = 1, 3, 4
# What a row keeps per civilization. `score` is the engine's own; the rest are the plain indicators the
# benchmark sketch names, reported side by side with no claim that they add up.
INDICATORS = ("score", "techs", "policies", "cities", "population", "military", "land", "gold", "science", "happiness")

READ = """
local out = {turn = Game.GetGameTurn(), state = Game.GetGameState(), winner = Game.GetWinner(), victory = "",
  auto = Game.GetAIAutoPlay(), active = Game.GetActivePlayer(), max_turns = Game.GetMaxTurns(),
  handicap = GameInfo.HandicapInfos[Game.GetHandicapType()].Type, speed = GameInfo.GameSpeeds[Game.GetGameSpeedType()].Type,
  slots = {}, players = {}}
local v = Game.GetVictory()
if v ~= nil and v >= 0 and GameInfo.Victories[v] then out.victory = GameInfo.Victories[v].Type end
for i = 0, GameDefines.MAX_MAJOR_CIVS - 1 do
  out.slots[#out.slots + 1] = PreGame.GetSlotStatus(i)
  local p = Players[i]
  if p and p:IsEverAlive() and PreGame.GetSlotStatus(i) ~= 4 then
    local team = Teams[p:GetTeam()]
    local techs, policies = 0, 0
    for row in GameInfo.Technologies() do if team:IsHasTech(row.ID) then techs = techs + 1 end end
    for row in GameInfo.Policies() do if p:HasPolicy(row.ID) then policies = policies + 1 end end
    out.players[#out.players + 1] = {id = i, civ = p:GetCivilizationShortDescription(), alive = p:IsAlive(),
      human = p:IsHuman(), score = p:GetScore(), techs = techs, policies = policies, cities = p:GetNumCities(),
      population = p:GetTotalPopulation(), military = p:GetMilitaryMight(), land = p:GetNumPlots(),
      gold = p:GetGold(), science = p:GetScience(), happiness = p:GetExcessHappiness()}
  end
end
return out
"""

# The draws move the game's random stream before the engine plays, so two runs of one save need not be one run.
START = """
for _ = 1, %(burn)d do Game.Rand(100, "board_run") end
Game.SetAIAutoPlay(%(turns)d, %(seat)d)
return {auto = Game.GetAIAutoPlay(), active = Game.GetActivePlayer(), slot = PreGame.GetSlotStatus(%(seat)d),
  human = Players[%(seat)d]:IsHuman(), units = Players[%(seat)d]:GetNumUnits(), cities = Players[%(seat)d]:GetNumCities()}
"""

POLL = """
return {turn = Game.GetGameTurn(), auto = Game.GetAIAutoPlay(), winner = Game.GetWinner(), state = Game.GetGameState(),
  alive = Players[%(seat)d]:IsAlive(), active = Game.GetActivePlayer()}
"""


class Refused(Exception):
    """The board cannot be run as asked; nothing was changed in the game."""


def find_seat(read: dict, seat: int | None) -> int:
    """The seat to hand over: the one named, else the only human. More than one human is refused."""
    humans = [p["id"] for p in read["players"] if p["human"]]
    if len(humans) != 1:
        raise Refused(f"the board has {len(humans)} human seats ({humans}); autoplay is checked with one")
    if seat is not None and seat != humans[0]:
        raise Refused(f"seat {seat} is not the human seat of this board ({humans[0]})")
    return humans[0]


def check_observer_slot(read: dict, seat: int) -> None:
    """Refuse a board with no observer slot beside the seat: the engine would make the seat the observer and
    destroy its units and cities in the same call."""
    if not any(s == SS_OBSERVER for i, s in enumerate(read["slots"]) if i != seat):
        raise Refused("no slot of this game is an observer slot (status 4): autoplay would destroy the seat. "
                      "Host the board from the single-player setup screen with its unused slots as it leaves them")


def seat_view(read: dict, seat: int) -> dict:
    """The seat's indicators, each with its share of the living major civilizations' total, and its place by score."""
    me = next(p for p in read["players"] if p["id"] == seat)
    living = [p for p in read["players"] if p["alive"]]
    out: dict = {"turn": read["turn"], "alive": me["alive"], "values": {}, "share": {}}
    for k in INDICATORS:
        out["values"][k] = me[k]
        total = sum(max(p[k], 0) for p in living)
        out["share"][k] = round(max(me[k], 0) / total, 4) if total and me["alive"] else 0.0
    out["place"] = 1 + sum(1 for p in living if p["score"] > me["score"]) if me["alive"] else None
    out["of"] = len(living)
    return out


def run_once(g, save: str, turns: int, seat: int | None = None, burn: int = 0, poll: float = 3.0, stall: float = 900.0,
             sleep=time.sleep, clock=time.monotonic, say=lambda _line: None) -> dict:
    """One run of the board. Loads `save` (the game must be at the main menu), hands the seat over, watches, reads,
    and leaves for the main menu whatever happened once the seat was handed over."""
    loaded = g.load_save(save)
    if not loaded.get("ok"):
        raise Refused(f"the save did not load: {loaded.get('err') or loaded}")
    before = g.q(READ)
    try:
        seat = find_seat(before, seat)
        check_observer_slot(before, seat)
    except Refused:
        g.leave_to_main_menu()
        raise
    t0 = clock()
    started = g.q(START % {"burn": burn, "turns": turns, "seat": seat})
    row: dict = {"save": save, "seat": seat, "turns_asked": turns, "burn": burn, "handicap": before["handicap"],
                 "speed": before["speed"], "start": seat_view(before, seat), "end_reason": None, "win_turn": None}
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
                row["end_reason"] = "window_played"
            elif clock() - last_change > stall:
                row["end_reason"] = "stalled"
            if row["end_reason"]:
                break
        after = g.q(READ)
        row.update(seconds=round(clock() - t0, 1), end=seat_view(after, seat), winner=after["winner"],
                   victory=after["victory"], turns_played=after["turn"] - before["turn"],
                   players=[{k: p[k] for k in ("id", "civ", "alive", "score")} for p in after["players"]])
        return row
    finally:
        g.leave_to_main_menu()


def mean_sd(xs: list[float]) -> tuple[float, float]:
    m = sum(xs) / len(xs)
    return m, (math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) if len(xs) > 1 else 0.0)


def summarise(rows: list[dict]) -> list[str]:
    """Per indicator: the seat's value at the start, and over the runs that played their window the value at the
    end as mean, standard deviation, least and most, then the spread as a share of the mean gain."""
    done = [r for r in rows if r.get("end_reason") == "window_played"]
    lines = [f"{len(rows)} runs, {len(done)} played their window"
             + "".join(f", {n} {why}" for why in ("seat_dead", "game_won", "stalled", "not_handed_over")
                       if (n := sum(1 for r in rows if r.get("end_reason") == why)))]
    if not done:
        return lines
    first = done[0]
    lines.append(f"save {first['save']!r}, seat {first['seat']}, {first['handicap']}, {first['turns_asked']} turns, "
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
    if len({json.dumps(r["end"]["values"], sort_keys=True) for r in done}) == 1 and len(done) > 1:
        lines.append("every run ended on the same values: the save replays the same game")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--save", help="the save's bare name, no path and no .Civ5Save")
    ap.add_argument("--turns", type=int, default=10, help="the window: turns the engine plays the seat (default 10)")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--seat", type=int, default=None, help="default: the board's one human seat")
    ap.add_argument("--out", type=Path, help="JSON lines, one row a run, appended")
    ap.add_argument("--burn", choices=("none", "run"), default="run",
                    help="draws taken from the game's random stream before the engine plays: none, or 17 times the "
                         "run's number (default), so that runs of one save differ")
    ap.add_argument("--stall", type=float, default=900.0, help="seconds without a new turn before a run is given up")
    ap.add_argument("--summary", type=Path, metavar="ROWS", help="print the summary of a rows file and do nothing else")
    a = ap.parse_args(argv)
    if a.summary:
        print("\n".join(summarise([json.loads(line) for line in a.summary.read_text().splitlines() if line.strip()])))
        return 0
    if not a.save or not a.out:
        ap.error("--save and --out are needed for a run")
    from harness.game import Game
    g = Game()
    if g.has_state("InGame"):
        print("a game is loaded: leave it for the main menu first (session main_menu); nothing was done", file=sys.stderr)
        return 2
    a.out.parent.mkdir(parents=True, exist_ok=True)
    done = sum(1 for line in a.out.read_text().splitlines() if line.strip()) if a.out.exists() else 0
    for n in range(done, done + a.runs):
        print(f"run {n}: loading {a.save!r}", flush=True)
        try:
            row = run_once(g, a.save, a.turns, seat=a.seat, burn=17 * n if a.burn == "run" else 0, stall=a.stall,
                           say=lambda line: print(line, flush=True))
        except Refused as e:
            print(f"refused: {e}", file=sys.stderr)
            return 2
        row.update(run=n, at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        with a.out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(f"run {n}: {row['end_reason']}, {row.get('turns_played')} turns in {row.get('seconds')} s, score "
              f"{row['start']['values']['score']} -> {row.get('end', {}).get('values', {}).get('score')}", flush=True)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline and g.front_end_screen() != "MainMenu":
            time.sleep(2)
    print("\n".join(summarise([json.loads(line) for line in a.out.read_text().splitlines() if line.strip()])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
