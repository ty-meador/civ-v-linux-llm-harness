#!/usr/bin/env python3
"""Make a starting save of the benchmark and its manifest, by one command (docs/BENCHMARK.md, rule 2).

A starting save is a save, a seat, a number of turns and a number of seeds. This makes the save and writes down
what it is: a manifest, one JSON file, kept with a copy of the save under `saves/benchmark/`.

An opening, hosted from the single-player setup screen (the game at the main menu):

    scripts/benchmark_save.py --host board-duel-prince-e --civ CIVILIZATION_CELTS --world-size WORLDSIZE_DUEL \
        --map-script pangaea

Prince, Quick speed and every victory type on unless said otherwise; the unused slots are left as the screen leaves
them (the observer slot the engine needs to play a seat). The game is then made to carry the benchmark's terms (the
seat on the row every AI plays on, no Time victory; `benchmark_run.py --terms` does the same to a save made by hand)
and saved under the name.

A middle or a late starting save, cut from a game the built-in AI played alone:

    scripts/benchmark_save.py --cut board-duel-prince-d-t100 --save board-duel-prince-d --turns 100 --kind middle

The built-in AI plays `--save` for `--turns` turns on seed `--seed` (default 0) and the game is saved there: no
one's notebook, no tokens.

A manifest for a save that exists already, and the checked-in saves put where the game loads them from:

    scripts/benchmark_save.py --describe board-duel-prince-d --kind opening
    scripts/benchmark_save.py --install

Every way ends by loading the save once more and reading it, so a manifest says what the save holds after a load
and not what the command meant to put there. `--run-turns` and `--seeds` are the turns a player plays on the save and
the seeds it is measured on (100 and 20 unless given). Whether a save can be used at all is not decided here: rule 2
keeps a starting save only if the baseline wins between 0.2 and 0.8 of its games, and that is a batch of
`benchmark_run.py`. A manifest says `baseline: null` until one is written into it.

Not in a manifest: the map's random seed. This build's setup screen has no call that reads or sets one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import benchmark_run as run

KINDS = ("opening", "middle", "late")
KEPT = Path(__file__).resolve().parent.parent / "saves" / "benchmark"

# What a manifest says of the game beyond the runner's own read: the settings a save carries and the game's build.
SETTINGS = """
local v = {}
for row in GameInfo.Victories() do if Game.IsVictoryValid(row.ID) then v[#v + 1] = row.Type end end
local minors = 0
for m = GameDefines.MAX_MAJOR_CIVS, GameDefines.MAX_CIV_PLAYERS - 1 do
  local c = Players[m]
  if c and c:IsAlive() and c:IsMinorCiv() then minors = minors + 1 end
end
return {world_size = GameInfo.Worlds[Map.GetWorldSize()].Type, map_script = PreGame.GetMapScript(), victories = v,
  seat_row = GameInfo.HandicapInfos[Players[%(seat)d]:GetHandicapType()].Type,
  start_era = GameInfo.Eras[Game.GetStartEra()].Type, city_states = minors,
  build = UI.GetVersionInfo and UI.GetVersionInfo() or ""}
"""


def describe(g, name: str, seat: int | None = None) -> dict:
    """Load `name`, read what it holds, leave. Refuses a save a player could not be given: no single human seat, no
    observer slot, or a seat that is dead."""
    loaded = g.load_save(name)
    if not loaded.get("ok"):
        raise run.Refused(f"the save did not load: {loaded.get('err') or loaded}")
    try:
        read = g.q(run.READ)
        seat = run.find_seat(read, seat)
        run.check_observer_slot(read, seat)
        me = next(p for p in read["players"] if p["id"] == seat)
        if not me["alive"]:
            raise run.Refused(f"the seat is dead on turn {read['turn']} of this save")
        if read.get("winner", -1) >= 0:
            raise run.Refused(f"the game of this save is already won (turn {read['turn']})")
        settings = dict(g.q(SETTINGS % {"seat": seat}))
        return {"turn": read["turn"], "seat": seat, "civilization": me["civ"],
                "opponents": [p["civ"] for p in read["players"] if p["id"] != seat and p["alive"]],
                "seat_turn_active": bool(me.get("turn_active")), "build": settings.pop("build", ""),
                "settings": {"handicap": read["handicap"], "speed": read["speed"], "max_turns": read["max_turns"],
                             "time_victory": "VICTORY_TIME" in settings["victories"], **settings}}
    finally:
        run.leave(g)


def host(g, name: str, civilization: str, world_size: str, map_script: str | None, speed: str, handicap: str,
         row: str = "ai", time_victory: str = "off", save_game=run.save_as, opponents: list[str] | None = None,
         victories: list[str] | None = None) -> dict:
    """A new game from the single-player setup screen, made to carry the terms, saved as `name`. Says what the setup
    screen held when the game started."""
    more = {k: v for k, v in (("opponents", opponents), ("victories", victories)) if v}
    screen = g.start_single_player(civilization=civilization, handicap=handicap, world_size=world_size,
                                   map_script=map_script, game_speed=speed, all_victories=not victories, **more)
    try:
        read = g.q(run.READ)
        seat = run.find_seat(read, None)
        run.check_observer_slot(read, seat)
        terms = (run.ROW_AI % {"seat": seat} if row == "ai" else "") + (run.TIME_OFF if time_victory == "off" else "")
        g.q(run.TERMS % {"terms": terms, "seat": seat})
        save_game(g, name)
        return {"how": "hosted", "setup_screen": screen}
    finally:
        run.leave(g)


def cut(g, save: str, name: str, turns: int, seed: int = 0, say=lambda _line: None, play=run.run_once) -> dict:
    """The built-in AI plays `save` for `turns` turns on `seed` and the game is saved as `name`."""
    skip = run.NUMBERS_A_SEED * seed
    row = play(g, save, turns, skip=skip, end_save=name, say=say)
    if row.get("end_save") != name:
        raise run.Refused(f"the turns were not all played ({row.get('end_reason')}, {row.get('turns_played')} of {turns}); "
                          f"nothing was saved{': ' + row['end_save_error'] if row.get('end_save_error') else ''}")
    return {"how": "cut", "from": save, "played_by": run.BUILT_IN_AI, "turns": turns, "seed": seed, "skip": skip,
            "seconds": row.get("seconds")}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def keep(name: str, seen: dict, origin: dict, kind: str, run_turns: int, seeds: int, kept: Path = KEPT,
         today: str | None = None) -> dict:
    """Copy the save beside its manifest under `kept` and write the manifest. Says the manifest."""
    kept.mkdir(parents=True, exist_ok=True)
    file = kept / f"{name}.Civ5Save"
    shutil.copyfile(run.saves_dir() / file.name, file)
    manifest = {"id": name, "save": file.name, "sha256": sha256(file), "kind": kind, "turn": seen["turn"],
                "seat": seen["seat"], "civilization": seen["civilization"], "opponents": seen["opponents"],
                "turns": run_turns, "seeds": seeds, "settings": seen["settings"],
                "origin": {**origin, "at": today or time.strftime("%Y-%m-%d")}, "game_build": seen["build"],
                "baseline": None}
    (kept / f"{name}.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


def install(kept: Path = KEPT) -> list[str]:
    """Copy every kept starting save into the folder the game loads from. A copy that is there already and is another
    file is left alone and said."""
    lines = []
    for path in sorted(kept.glob("*.json")):
        manifest = json.loads(path.read_text())
        src, dst = kept / manifest["save"], run.saves_dir() / manifest["save"]
        if not src.exists() or sha256(src) != manifest["sha256"]:
            lines.append(f"{manifest['id']}: the kept save is not the one its manifest names; not installed")
        elif dst.exists() and sha256(dst) != manifest["sha256"]:
            lines.append(f"{manifest['id']}: another file of that name is in {dst.parent}; left alone")
        elif dst.exists():
            lines.append(f"{manifest['id']}: there already")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            lines.append(f"{manifest['id']}: installed")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    how = ap.add_mutually_exclusive_group(required=True)
    how.add_argument("--host", metavar="NAME", help="host a new game from the setup screen and save it as NAME")
    how.add_argument("--cut", metavar="NAME", help="the built-in AI plays --save for --turns turns; saved as NAME")
    how.add_argument("--describe", metavar="NAME", help="write the manifest of a save that exists")
    how.add_argument("--install", action="store_true", help="copy the kept saves to where the game loads them from")
    ap.add_argument("--civ", help="with --host: the seat's civilization, a CIVILIZATION_* type")
    ap.add_argument("--world-size", default="WORLDSIZE_DUEL", help="with --host (default WORLDSIZE_DUEL)")
    ap.add_argument("--map-script", help="with --host: a script's file name, e.g. pangaea (default: as the screen has it)")
    ap.add_argument("--speed", default="GAMESPEED_QUICK", help="with --host (default GAMESPEED_QUICK)")
    ap.add_argument("--handicap", default="HANDICAP_PRINCE", help="with --host (default HANDICAP_PRINCE)")
    ap.add_argument("--opponent", action="append", metavar="CIVILIZATION",
                    help="with --host: the civilization of the next rival slot, a CIVILIZATION_* type (repeat for more; "
                         "a slot not named gets a random leader)")
    ap.add_argument("--victories", metavar="TYPES",
                    help="with --host: only these victories, VICTORY_* types with commas between (default: all, and "
                         "the terms then switch Time off)")
    ap.add_argument("--save", help="with --cut: the save the built-in AI plays from")
    ap.add_argument("--turns", type=int, help="with --cut: the turns the built-in AI plays")
    ap.add_argument("--seed", type=int, default=0, help="with --cut: the seed it plays them on (default 0)")
    ap.add_argument("--kind", choices=KINDS, help="opening, middle or late (default: opening for a save on turn 0)")
    ap.add_argument("--run-turns", type=int, default=100, help="the turns a player plays on the save (default 100)")
    ap.add_argument("--seeds", type=int, default=20, help="the seeds a player is measured on (default 20)")
    ap.add_argument("--dir", type=Path, default=KEPT, help="where saves and manifests are kept (default saves/benchmark)")
    a = ap.parse_args(argv)
    if a.install:
        print("\n".join(install(a.dir) or ["no manifest under " + str(a.dir)]))
        return 0
    if a.host and not a.civ:
        ap.error("--host needs --civ")
    if a.cut and not (a.save and a.turns and a.turns > 0):
        ap.error("--cut needs --save and --turns")
    name = a.host or a.cut or a.describe
    from harness.game import Game
    g = Game()
    if g.has_state("InGame"):
        print("a game is loaded: leave it for the main menu first (session main_menu); nothing was done", file=sys.stderr)
        return 2
    try:
        if a.host:
            origin = host(g, name, a.civ, a.world_size, a.map_script, a.speed, a.handicap, opponents=a.opponent,
                          victories=a.victories.split(",") if a.victories else None)
        elif a.cut:
            origin = cut(g, a.save, name, a.turns, a.seed, say=lambda line: print(line, flush=True))
        else:
            origin = {"how": "described", "note": "the save was made before this command; see docs/BENCHMARK.md"}
        run.wait_main_menu(g)
        seen = describe(g, name)
        kind = a.kind or ("opening" if seen["turn"] == 0 else None)
        if kind is None:
            raise run.Refused(f"the save is on turn {seen['turn']}: say --kind middle or --kind late")
        manifest = keep(name, seen, origin, kind, a.run_turns, a.seeds, kept=a.dir)
    except run.Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
