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

An entrant other than the game's AI is a command after `--`: the same two reads, with the command between
them in place of the engine. The command plays the seat (a seat loop, `scripts/play_loop.py`) and ends;
`--label` names the entrant in the row, and `--turns` is the window the board must have moved on.

    scripts/board_run.py --save "Pacal_0242 maya-t242-before-185-check" --turns 10 --label codex/gpt-6.1-sol \
        --notebook logs/bench191/notebook-before.json --claim-wait 200 --out logs/boards/maya-t242/rows.jsonl \
        -- scripts/llm_seat_loop.py --agent codex --seat 0 --dir ~/projects/grok-desk-seat --model gpt-6.1-sol \
           --turns {turns} --cycles 1 --log-dir logs/boards/maya-t242/codex-{deal}

Deals, as in duplicate bridge: an entrant's nth run on a board is deal n and takes 17 n draws from the game's
random stream before anyone plays, so deal n is the same dice for every entrant and two deals are not one game
(a save replays the same game otherwise). The seat's notebook is the one given (`--notebook FILE`, or `none`
for a seat that takes the board over cold), the one the entrant leaves is kept beside the rows, and the one
that was on disk before the run is put back after it.

Operator-side only: it sends Lua text to the game, which a seat's connection may not (it needs the plain tunerd,
no seat table), and it reads every player, which no seat may. Nothing here is reachable from the nine tools.

What became of a run is `result`: `finished` (the window played, or the game decided inside it), `dnf` (the
entrant did not bring the seat to the window's end: it stopped, or ran out of time) or `void` (the engine
stalled or did not take the seat: not the entrant's doing, played again). With `--continue R` a finished run is
valued: the game is saved at the window's end and played out R times by the engine, and `value` is the share
the seat's team wins. A DNF has no value; it is counted beside the value and stands below every finished run.

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
import os
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
      human = p:IsHuman(), team = p:GetTeam(), turn_active = p:IsTurnActive(), score = p:GetScore(), techs = techs, policies = policies, cities = p:GetNumCities(),
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
  alive = Players[%(seat)d]:IsAlive(), active = Game.GetActivePlayer(), turn_active = Players[%(seat)d]:IsTurnActive(),
  team = Players[%(seat)d]:GetTeam(), victory = (Game.GetVictory() or -1) >= 0 and GameInfo.Victories[Game.GetVictory()].Type or ""}
"""

BURN = """
for _ = 1, %(burn)d do Game.Rand(100, "board_run") end
return {burn = %(burn)d}
"""

STOCK_AI = "stock-ai"
BOARD = "board"               # the entrant name of a --value-only row: the save itself, played out by the engine
DRAWS_A_DEAL = 17
DRAWS_A_CONTINUATION = 29     # continuation m takes 29 (m + 1): never none, so no continuation replays the save as it is
TO_THE_END = 1000             # turns asked of the engine in a continuation: more than any game has left


LEAVE = """
Events.ExitToMainMenu()
return {ok = true}
"""


def leave(g) -> None:
    """Leave the loaded game for the main menu. The harness's own exit is a seat's: while the engine plays the seat
    the observer is the active player and the exit answers "this seat is not active". A run that ended on a win
    left its game up that way and the engine played on past turn 380 (live 2026-11-16, the user watching). The
    referee is no seat and asks the game itself."""
    reply = g.leave_to_main_menu()
    if isinstance(reply, dict) and reply.get("ok") is False:
        try:
            g.q(LEAVE)
        except Exception:   # the InGame state is torn down under the call: the reply may never come
            pass


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


def keep_end(g, row: dict, name: str | None, save_game, sleep, clock) -> None:
    """The position a played window ended on, saved for its continuations (rule 1)."""
    if not name or row.get("end_reason") != "window_played":
        return
    try:
        row["end_save"] = save_game(g, name, sleep=sleep, clock=clock)
    except Refused as e:
        row["end_save"], row["end_save_error"] = None, str(e)


def continuation(g, save: str, m: int, seat: int | None = None, poll: float = 3.0, stall: float = 900.0,
                 sleep=time.sleep, clock=time.monotonic, say=lambda _line: None) -> dict:
    """One game played on from `save` to its end by the game's own AI on every seat. Says whether the seat's team
    took the victory. It ends on a victory, on the seat's death (a game lost, whoever wins it later) or on a stall,
    and leaves for the main menu, since the engine would play on past all three."""
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
    burn = DRAWS_A_CONTINUATION * (m + 1)
    t0 = clock()
    out: dict = {"m": m, "burn": burn, "from_turn": before["turn"], "end_reason": None, "won": False}
    try:
        started = g.q(START % {"burn": burn, "turns": TO_THE_END, "seat": seat})
        if started["slot"] != SS_COMPUTER or started["active"] == seat:
            out["end_reason"] = "not_handed_over"
            return out
        last_turn, last_change = before["turn"], clock()
        while True:
            sleep(poll)
            now = g.q(POLL % {"seat": seat})
            if now["turn"] != last_turn:
                last_turn, last_change = now["turn"], clock()
                if now["turn"] % 25 == 0:
                    say(f"    continuation {m}: turn {now['turn']}  +{clock() - t0:.0f}s")
            if now["winner"] >= 0:
                out.update(end_reason="victory", won=now["winner"] == now["team"], winner=now["winner"], victory=now["victory"])
            elif not now["alive"]:
                out["end_reason"] = "seat_dead"
            elif now["auto"] == 0:
                out["end_reason"] = "count_out"
            elif clock() - last_change > stall:
                out["end_reason"] = "stalled"
            if out["end_reason"]:
                out.update(turn=now["turn"], seconds=round(clock() - t0, 1))
                return out
    finally:
        leave(g)


DECIDED = ("victory", "seat_dead")
# What became of a run (rule 5). DNF is a result of its own, as in a race: the entrant did not bring the seat to the
# end of the window. It has no value, it is counted and shown, and in any ordering it stands below every finished
# run, so that stopping never does better than playing. Void is not the entrant's doing and is played again.
FINISHED = ("window_played", "game_won", "seat_dead", "value_only")
DNF = ("window_not_played", "timeout")
VOID = ("stalled", "not_handed_over")


def result_of(row: dict) -> str:
    reason = row.get("end_reason")
    return "finished" if reason in FINISHED else "dnf" if reason in DNF else "void"


def value_of(row: dict, continuations: list[dict]) -> float | None:
    """Rule 1. Only a finished run has a value. A game decided inside the window is 1 for the seat's team and 0
    otherwise, a seat that died in it 0. A played window (or a save valued as it is) is the share of its decided
    continuations the seat won; none decided is no value."""
    reason = row.get("end_reason")
    if result_of(row) != "finished":
        return None
    if reason == "game_won":
        return 1.0 if row.get("winner") == (row.get("end") or {}).get("team") else 0.0
    if reason == "seat_dead":
        return 0.0
    decided = [c for c in continuations if c.get("end_reason") in DECIDED]
    return round(sum(1 for c in decided if c["won"]) / len(decided), 4) if decided else None


def run_once(g, save: str, turns: int, seat: int | None = None, burn: int = 0, poll: float = 3.0, stall: float = 900.0,
             end_save: str | None = None, save_game=save_as,
             sleep=time.sleep, clock=time.monotonic, say=lambda _line: None) -> dict:
    """One run of the board by the game's own AI. Loads `save` (the game must be at the main menu), hands the seat over, watches, reads,
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
    started = g.q(START % {"burn": burn, "turns": turns, "seat": seat})
    row: dict = {"entrant": STOCK_AI, "save": save, "seat": seat, "turns_asked": turns, "burn": burn,
                 "handicap": before["handicap"], "speed": before["speed"], "start": seat_view(before, seat),
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
                row["end_reason"] = "window_played"
            elif clock() - last_change > stall:
                row["end_reason"] = "stalled"
            if row["end_reason"]:
                break
        after = g.q(READ)
        row.update(seconds=round(clock() - t0, 1), end=seat_view(after, seat), winner=after["winner"],
                   victory=after["victory"], turns_played=after["turn"] - before["turn"],
                   players=[{k: p[k] for k in ("id", "civ", "alive", "score")} for p in after["players"]])
        keep_end(g, row, end_save, save_game, sleep, clock)
        return row
    finally:
        leave(g)


def notebook_path(g, seat: int) -> Path:
    """Where the harness keeps this game's notebook for the seat."""
    g.seat = seat
    return g.notebook().path


def run_entrant(g, save: str, command: list[str], label: str, turns: int, seat: int | None = None, burn: int = 0,
                notebook: str | None = None, keep_notebook: Path | None = None, claim_wait: float = 0.0,
                timeout: float = 4 * 3600.0, settle: float = 120.0, poll: float = 3.0, run=subprocess.run,
                end_save: str | None = None, save_game=save_as,
                path_of=notebook_path, sleep=time.sleep, clock=time.monotonic) -> dict:
    """One run of the board by a command that plays the seat and ends. Loads `save`, reads, puts the entrant's
    notebook in place, runs the command, reads, and leaves for the main menu with the notebook that was on disk
    before put back. The command's own exit code is in the row and decides nothing: the run played its window
    when the board is `turns` turns on, whatever the command said (a scripted loop gave up at a World Congress
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
    row: dict = {"entrant": label, "command": command, "save": save, "seat": seat, "turns_asked": turns, "burn": burn,
                 "notebook": notebook or "standing", "handicap": before["handicap"], "speed": before["speed"],
                 "start": seat_view(before, seat), "end_reason": None, "rc": None}
    try:
        if notebook == "none":
            nb.unlink(missing_ok=True)
        elif notebook:
            nb.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(notebook, nb)
        if burn:
            g.q(BURN % {"burn": burn})
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
            row["end_reason"] = "window_played" if after["turn"] - before["turn"] == turns else "window_not_played"
        row.update(end=end, winner=after["winner"], victory=after["victory"], turns_played=after["turn"] - before["turn"],
                   players=[{k: p[k] for k in ("id", "civ", "alive", "score")} for p in after["players"]])
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


def entrant_of(row: dict) -> str:
    return row.get("entrant") or STOCK_AI


def summarise_entrant(name: str, rows: list[dict]) -> list[str]:
    """One entrant on one board. Per indicator: the seat's value at the start, and over the runs that played
    their window the value at the end as mean, standard deviation, least and most, then the spread as a share
    of the mean gain."""
    done = [r for r in rows if r.get("end_reason") == "window_played"]
    lines = [f"{name}: {len(rows)} runs, {len(done)} played their window"
             + "".join(f", {n} {why}" for why in ("seat_dead", "game_won", *DNF, *VOID)
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


def value_lines(rows: list[dict]) -> list[str]:
    """The entrant's value over its finished runs, each run's own, and its DNF as a count of their own: beside the
    value, never inside its mean. The last figure is the value with every DNF as 0, what an ordering uses."""
    values = [r["value"] for r in rows if r.get("value") is not None]
    dnf = [r for r in rows if result_of(r) == "dnf"]
    lines = []
    if values:
        m, sd = mean_sd(values)
        games = [c for r in rows for c in r.get("continuations", []) if c.get("end_reason") in DECIDED]
        how = sorted({c.get("victory") or "seat_dead" for c in games})
        minutes = f", {mean_sd([c['seconds'] for c in games])[0] / 60:.1f} min each" if games else ""
        lines.append(f"value: {m:.3f} (sd {sd:.3f}) over {len(values)} finished runs and {len(games)} continuations{minutes}; "
                     f"by run: {', '.join(f'{v:.2f}' for v in values)}" + (f"; ended by {', '.join(how)}" if how else ""))
    if dnf and (values or any("continuations" in r or "value" in r for r in rows)):
        why = ", ".join(sorted({r["end_reason"] for r in dnf}))
        lines.append(f"DNF: {len(dnf)} of {len(dnf) + len(values)} runs ({why}), below every finished run in an ordering"
                     + (f"; with DNF as 0 the value is {sum(values) / (len(values) + len(dnf)):.3f}" if values else ""))
    return lines


def summarise(rows: list[dict]) -> list[str]:
    """Every entrant of a rows file by itself, then the entrants side by side when there are two or more: the
    mean at the end of the window and its spread, over the runs that played the window. Only runs of the same
    number of turns stand side by side."""
    names = list(dict.fromkeys(entrant_of(r) for r in rows))
    lines: list[str] = []
    for name in names:
        lines += ([""] if lines else []) + summarise_entrant(name, [r for r in rows if entrant_of(r) == name])
    played = {name: [r for r in rows if entrant_of(r) == name and r.get("end_reason") == "window_played"] for name in names}
    played = {name: rs for name, rs in played.items() if rs}
    windows = {r.get("turns_played", r.get("turns_asked")) for rs in played.values() for r in rs}
    if len(played) < 2:
        return lines
    if len(windows) > 1:
        return [*lines, "", f"not side by side: the runs played {', '.join(str(w) for w in sorted(windows))} turns"]
    lines += ["", f"side by side, {windows.pop()} turns, mean (sd) at the end:",
              f"{'':12}" + "".join(f"{f'{name} x{len(rs)}':>24}" for name, rs in played.items())]
    for k in INDICATORS:
        cells = [mean_sd([r["end"]["values"][k] for r in rs]) for rs in played.values()]
        lines.append(f"{k:12}" + "".join(f"{f'{m:.1f} ({sd:.1f})':>24}" for m, sd in cells))
    valued = {name: [r["value"] for r in rows if entrant_of(r) == name and r.get("value") is not None] for name in played}
    if all(valued.values()):
        lines.append(f"{'value':12}" + "".join(f"{'{:.3f} ({:.3f})'.format(*mean_sd(vs)):>24}" for vs in valued.values()))
        dnf = [sum(1 for r in rows if entrant_of(r) == name and result_of(r) == "dnf") for name in played]
        if any(dnf):
            lines.append(f"{'DNF':12}" + "".join(f"{f'{n} of {n + len(vs)}':>24}" for n, vs in zip(dnf, valued.values())))
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


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--save", help="the save's bare name, no path and no .Civ5Save")
    ap.add_argument("--turns", type=int, default=10,
                    help="the window (default 10): turns the engine plays the seat, and the turns a command's run must "
                         "have moved the board on to count as played")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--seat", type=int, default=None, help="default: the board's one human seat")
    ap.add_argument("--out", type=Path, help="JSON lines, one row a run, appended")
    ap.add_argument("--burn", choices=("none", "run"), default="run",
                    help="draws taken from the game's random stream before anyone plays: none, or 17 times the "
                         "deal's number (default; an entrant's nth run is deal n), so that runs of one save differ")
    ap.add_argument("--stall", type=float, default=900.0, help="seconds without a new turn before a run is given up")
    ap.add_argument("--label", help="the entrant's name in the row, needed with a command")
    ap.add_argument("--notebook", help="the notebook the entrant starts with: a file, or `none`; default the one on disk")
    ap.add_argument("--claim-wait", type=float, default=0.0,
                    help="seconds to wait before the command; 200 after another client played the seat (its turn claim)")
    ap.add_argument("--timeout", type=float, default=4 * 3600.0, help="seconds before the command is given up")
    ap.add_argument("--continue", dest="continuations", type=int, default=0, metavar="R",
                    help="value the run (rule 1): save at the window's end and let the engine play the game out R times "
                         "from there; the value is the share the seat's team wins")
    ap.add_argument("--value-only", action="store_true",
                    help="no window: value --save itself by --continue R continuations (a board's own worth)")
    ap.add_argument("--summary", type=Path, metavar="ROWS", help="print the summary of a rows file and do nothing else")
    ap.add_argument("command", nargs=argparse.REMAINDER,
                    help="after `--`: the entrant, a command that plays the seat and ends; {deal} and {turns} in it "
                         "are the deal's number and the window")
    a = ap.parse_args(argv)
    if a.summary:
        print("\n".join(summarise(read_rows(a.summary))))
        return 0
    command = a.command[1:] if a.command[:1] == ["--"] else a.command
    if not a.save or not a.out:
        ap.error("--save and --out are needed for a run")
    if command and not a.label or a.label == STOCK_AI:
        ap.error("a command needs --label, the entrant's name (not stock-ai)")
    if a.label and not command:
        ap.error("--label names a command's entrant; give the command after --")
    if a.value_only and (command or a.continuations < 1):
        ap.error("--value-only takes --continue R and no command")
    from harness.game import Game
    g = Game()
    if g.has_state("InGame"):
        print("a game is loaded: leave it for the main menu first (session main_menu); nothing was done", file=sys.stderr)
        return 2
    a.out.parent.mkdir(parents=True, exist_ok=True)
    name = BOARD if a.value_only else a.label or STOCK_AI
    say = lambda line: print(line, flush=True)
    done = sum(1 for r in read_rows(a.out) if entrant_of(r) == name)
    for n in range(done, done + a.runs):
        print(f"{name} deal {n}: loading {a.save!r}", flush=True)
        burn = DRAWS_A_DEAL * n if a.burn == "run" else 0
        end_save = f"{a.save}--{''.join(c if c.isalnum() else '-' for c in name)}-deal{n}-end" if a.continuations else None
        try:
            if a.value_only:
                row = {"entrant": name, "save": a.save, "seat": a.seat, "turns_asked": 0, "turns_played": 0, "burn": 0,
                       "end_reason": "value_only", "end_save": a.save}
            elif command:
                keep = a.out.with_name(f"{a.out.stem}-{''.join(c if c.isalnum() else '-' for c in name)}-deal{n}-notebook.json")
                words = [part.replace("{deal}", str(n)).replace("{turns}", str(a.turns)) for part in command]
                row = run_entrant(g, a.save, words, name, a.turns, seat=a.seat, burn=burn, notebook=a.notebook,
                                  keep_notebook=keep, claim_wait=a.claim_wait, timeout=a.timeout, end_save=end_save)
            else:
                row = run_once(g, a.save, a.turns, seat=a.seat, burn=burn, stall=a.stall, end_save=end_save, say=say)
            if a.continuations:
                row["continuations"] = []
                for m in range(a.continuations if row.get("end_save") else 0):
                    wait_main_menu(g)
                    c = continuation(g, row["end_save"], m, seat=a.seat, stall=a.stall, say=say)
                    row["continuations"].append(c)
                    print(f"  continuation {m}: {c['end_reason']}, {'won' if c['won'] else 'not won'}"
                          f"{' by ' + c['victory'] if c.get('victory') else ''}, turn {c.get('turn')}, {c.get('seconds')} s",
                          flush=True)
                row["value"] = value_of(row, row["continuations"])
            row["result"] = result_of(row)
        except Refused as e:
            print(f"refused: {e}", file=sys.stderr)
            return 2
        row.update(run=n, at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        with a.out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(f"{name} deal {n}: {row['end_reason']}, {row.get('turns_played')} turns in {row.get('seconds')} s, score "
              f"{row.get('start', {}).get('values', {}).get('score')} -> {row.get('end', {}).get('values', {}).get('score')}"
              + (f", value {row['value']}" if row.get("value") is not None else ""), flush=True)
        wait_main_menu(g)
    print("\n".join(summarise(read_rows(a.out))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
