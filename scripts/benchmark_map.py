#!/usr/bin/env python3
"""A map of the benchmark kept as data: read out of the game plot for plot, and laid out again from the file.

A map the game rolls is gone with its game: this build has no call that reads or sets a map's random seed. Kept as
data it can be looked at, measured, changed by hand and hosted again, with any civilizations on it.

Read the map of the game on screen (any game, best on turn 0, before a city changes a plot):

    scripts/benchmark_map.py --read pangaea-b.json

Write the map script the game hosts the map from, into the game's own Maps folder:

    scripts/benchmark_map.py --script pangaea-b.json

The script is `omt_map.lua` and holds one map at a time. The game lists a script only when it found the file at its
start, so the first time the game has to be restarted; after that it reads the file's content anew at every game
start. `benchmark_save.py --host NAME --map pangaea-b.json` writes the script and hosts on it in one step.

What a file gives each civilization, and where two files differ:

    scripts/benchmark_map.py --report pangaea-b.json
    scripts/benchmark_map.py --same pangaea-b.json read-again.json

What is laid out again: every plot's type, terrain, feature (natural wonders among them), resource and its
quantity, rivers and their flow, ancient ruins, continent art, and the starting plot of every slot. A slot starts
on its plot whichever civilization holds it. Not in the file: which city-states the game picks. It rolls them at
every game start; a save keeps the ones it got.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import benchmark_run as run

SCRIPT_NAME = "omt_map"
# A plot is these numbers, in this order. Terrain, feature, resource and improvement are places in the map's own
# legend (0: none), so a file does not lean on the numbers one build of the game gives them.
PLOT_FIELDS = ("plot", "terrain", "feature", "resource", "quantity", "rivers", "flow_e", "flow_se", "flow_sw",
               "improvement", "continent")
PLOT, TERRAIN, FEATURE, RESOURCE, QUANTITY, RIVERS, FLOW_E, FLOW_SE, FLOW_SW, IMPROVEMENT, CONTINENT = range(11)
LEGENDS = {"terrain": TERRAIN, "feature": FEATURE, "resource": RESOURCE, "improvement": IMPROVEMENT}
# A barbarian camp or a city-state's first farm belongs to a game, not to the map.
KEPT_IMPROVEMENTS = ("IMPROVEMENT_GOODY_HUT",)
MOUNTAIN, HILLS, LAND, OCEAN = 0, 1, 2, 3          # the game's PlotTypes
MINOR = "MINOR_CIV_"

# What the report counts. The game's own lists (Brave New World, no mod); a feature outside the first is a
# natural wonder.
ORDINARY_FEATURES = {"FEATURE_ICE", "FEATURE_JUNGLE", "FEATURE_MARSH", "FEATURE_OASIS", "FEATURE_FLOOD_PLAINS",
                     "FEATURE_FOREST", "FEATURE_FALLOUT", "FEATURE_ATOLL"}
STRATEGIC = {"RESOURCE_IRON", "RESOURCE_HORSE", "RESOURCE_COAL", "RESOURCE_OIL", "RESOURCE_ALUMINUM",
             "RESOURCE_URANIUM"}
BONUS = {"RESOURCE_WHEAT", "RESOURCE_COW", "RESOURCE_SHEEP", "RESOURCE_DEER", "RESOURCE_BANANA", "RESOURCE_FISH",
         "RESOURCE_STONE", "RESOURCE_BISON"}
NEAR = 5                # plots from a start that the report counts as its surroundings
STATES_WITHIN = 10      # plots from a start inside which a city-state counts as near

READ = r"""
local w, h = Map.GetGridSize()
print("size", w, h, tostring(Map.IsWrapX()))
for y = 0, h - 1 do
  local cells = {}
  for x = 0, w - 1 do
    local p = Map.GetPlot(x, y)
    local rivers = (p:IsWOfRiver() and 1 or 0) + (p:IsNWOfRiver() and 2 or 0) + (p:IsNEOfRiver() and 4 or 0)
    cells[#cells + 1] = table.concat({p:GetPlotType(), p:GetTerrainType(), p:GetFeatureType(), p:GetResourceType(-1),
      p:GetNumResource(), rivers, p:GetRiverEFlowDirection(), p:GetRiverSEFlowDirection(),
      p:GetRiverSWFlowDirection(), p:GetImprovementType(), p:GetContinentArtType()}, ",")
  end
  print("row", y, table.concat(cells, ";"))
end
for row in GameInfo.Terrains() do print("terrain", row.ID, row.Type) end
for row in GameInfo.Features() do print("feature", row.ID, row.Type) end
for row in GameInfo.Resources() do print("resource", row.ID, row.Type) end
for row in GameInfo.Improvements() do print("improvement", row.ID, row.Type) end
for slot = 0, GameDefines.MAX_CIV_PLAYERS - 1 do
  local p = Players[slot]
  if p and p:IsEverAlive() then
    local at = p:GetStartingPlot()
    local who = p:IsMinorCiv() and GameInfo.MinorCivilizations[p:GetMinorCivType()].Type
      or GameInfo.Civilizations[p:GetCivilizationType()].Type
    print("start", slot, who, at and at:GetX() or -1, at and at:GetY() or -1)
  end
end
print("turn", Game.GetGameTurn())
"""

SCRIPT = r"""-- %(title)s: a map kept as data. Every plot, river, resource and starting plot is written out below;
-- nothing is rolled. Written by scripts/benchmark_map.py of the harness: change the data file, not this.
include("MapGenerator");

local W, H, WRAP_X = %(w)d, %(h)d, %(wrap)s
local LEGEND = {
	terrain = {%(terrain)s},
	feature = {%(feature)s},
	resource = {%(resource)s},
	improvement = {%(improvement)s},
}
-- One string a row, the south row first. A plot is: plot type, terrain, feature, resource, quantity, river edges
-- (1: east, 2: south-east, 4: south-west), the flow on each of the three, improvement, continent art.
local ROWS = {
%(rows)s
}
-- The slot of a player -> the plot it starts on, whichever civilization holds the slot.
local STARTS = {
%(starts)s
}

function GetMapScriptInfo()
	return {
		Name = "%(title)s",
		Description = "A map kept as data: the same land, rivers, resources and starting plots every time.",
		IsAdvancedMap = false,
		IconIndex = 0,
		SortIndex = 1,
		CustomOptions = {},
	}
end

function GetMapInitData(worldSize)
	return {Width = W, Height = H, WrapX = WRAP_X, WrapY = false}
end

local function TypeOf(legend, place)
	if place == 0 then return -1 end
	local id = GameInfoTypes[LEGEND[legend][place]]
	if id == nil then error("this game does not know " .. tostring(LEGEND[legend][place])) end
	return id
end

local function ReadPlots()
	local plots = {}
	for y = 0, H - 1 do
		local x = 0
		for cell in string.gmatch(ROWS[y + 1], "[^;]+") do
			local fields = {}
			for number in string.gmatch(cell, "-?%%d+") do fields[#fields + 1] = tonumber(number) end
			plots[#plots + 1] = {plot = Map.GetPlot(x, y), fields = fields}
			x = x + 1
		end
		if x ~= W then error("row " .. y .. " holds " .. x .. " plots, the map is " .. W .. " wide") end
	end
	return plots
end

-- The order is the game's own (MapGenerator.lua): land and terrain, areas, rivers, features, areas again, and
-- only then what sits on a plot.
function GenerateMap()
	print("%(title)s: laying the map out from its data");
	local plots = ReadPlots()
	for _, at in ipairs(plots) do at.plot:SetPlotType(at.fields[1], false, false) end
	for _, at in ipairs(plots) do at.plot:SetTerrainType(TypeOf("terrain", at.fields[2]), false, false) end
	Map.RecalculateAreas();
	for _, at in ipairs(plots) do
		local plot, rivers = at.plot, at.fields[6]
		if rivers %% 2 == 1 then plot:SetWOfRiver(true, at.fields[7]) end
		if math.floor(rivers / 2) %% 2 == 1 then plot:SetNWOfRiver(true, at.fields[8]) end
		if math.floor(rivers / 4) %% 2 == 1 then plot:SetNEOfRiver(true, at.fields[9]) end
	end
	for _, at in ipairs(plots) do
		if at.fields[3] ~= 0 then at.plot:SetFeatureType(TypeOf("feature", at.fields[3]), -1) end
	end
	Map.RecalculateAreas();
	for _, at in ipairs(plots) do
		local plot, fields = at.plot, at.fields
		if fields[4] ~= 0 then plot:SetResourceType(TypeOf("resource", fields[4]), fields[5]) end
		if fields[10] ~= 0 then plot:SetImprovementType(TypeOf("improvement", fields[10])) end
		plot:SetContinentArtType(fields[11]);
	end
	for slot = 0, GameDefines.MAX_CIV_PLAYERS - 1 do
		local player = Players[slot]
		if player ~= nil and player:IsEverAlive() then
			local at = STARTS[slot]
			if at == nil then error("the map has no starting plot for the player in slot " .. slot) end
			player:SetStartingPlot(Map.GetPlot(at[1], at[2]));
		end
	end
end
"""


def read_map(lines: list[str]) -> dict:
    """The map the READ lines describe, its types named through its own legends."""
    game_ids: dict[str, dict[int, str]] = {name: {} for name in LEGENDS}
    rows: dict[int, list[list[int]]] = {}
    out: dict = {"starts": {}}
    for line in lines:
        key, *rest = line.split("\t")
        if key == "size":
            out.update(w=int(rest[0]), h=int(rest[1]), wrap_x=rest[2] == "true")
        elif key == "row":
            rows[int(rest[0])] = [[int(float(n)) for n in cell.split(",")] for cell in rest[1].split(";")]
        elif key in game_ids:
            game_ids[key][int(rest[0])] = rest[1]
        elif key == "start":
            out["starts"][rest[0]] = {"who": rest[1], "x": int(rest[2]), "y": int(rest[3])}
        elif key == "turn":
            out["read_on_turn"] = int(rest[0])
    if "w" not in out or len(rows) != out["h"] or any(len(row) != out["w"] for row in rows.values()):
        raise run.Refused(f"the game's answer is not a whole map: {len(rows)} rows for {out.get('w')} by {out.get('h')}")
    out["legend"] = {name: [] for name in LEGENDS}
    out["rows"] = [[name_types(plot, game_ids, out["legend"]) for plot in rows[y]] for y in range(out["h"])]
    return out


def name_types(plot: list[int], game_ids: dict, legend: dict) -> list[int]:
    """The plot with the game's numbers swapped for places in the map's legend. An improvement that is not the
    map's is left out."""
    named = list(plot)
    for name, field in LEGENDS.items():
        kind = game_ids[name].get(plot[field]) if plot[field] >= 0 else None
        if kind is None or name == "improvement" and kind not in KEPT_IMPROVEMENTS:
            named[field] = 0
            continue
        if kind not in legend[name]:
            legend[name].append(kind)
        named[field] = legend[name].index(kind) + 1
    return named


def read_game(g) -> dict:
    """The map of the game on screen."""
    return read_map(g.c.exec("InGame", READ, timeout=120))


def script_of(data: dict, title: str = "OMT map") -> str:
    """The map script that lays `data` out again."""
    quoted = {name: ", ".join(f'"{kind}"' for kind in data["legend"][name]) for name in LEGENDS}
    rows = ",\n".join('\t"' + ";".join(",".join(str(n) for n in plot) for plot in row) + '"' for row in data["rows"])
    starts = "\n".join(f"\t[{slot}] = {{{at['x']}, {at['y']}}},  -- {at['who']}"
                       for slot, at in sorted(data["starts"].items(), key=lambda item: int(item[0])))
    return SCRIPT % {"title": title, "w": data["w"], "h": data["h"], "wrap": str(data["wrap_x"]).lower(),
                     "rows": rows, "starts": starts, **quoted}


def user_maps_dir() -> Path:
    """Where the game looks for a player's own map scripts: beside its folder of saves."""
    return run.saves_dir().parent.parent / "Maps"


def write_script(data: dict, folder: Path | None = None) -> Path:
    """Put the map's script where the game finds it. Says the file; its name without `.lua` is what
    `start_single_player(map_script=...)` takes."""
    folder = folder or user_maps_dir()
    folder.mkdir(parents=True, exist_ok=True)
    file = folder / f"{SCRIPT_NAME}.lua"
    file.write_text(script_of(data))
    return file


def named(data: dict, field: str, value: int):
    if field not in LEGENDS:
        return value
    return data["legend"][field][value - 1] if value else None


def differences(a: dict, b: dict) -> list[str]:
    """Where two maps differ, in words; empty when they are the same map. Who holds a slot is not compared."""
    found = [f"{key}: {a.get(key)} against {b.get(key)}" for key in ("w", "h", "wrap_x") if a.get(key) != b.get(key)]
    if found:
        return found
    for y, (row_a, row_b) in enumerate(zip(a["rows"], b["rows"], strict=True)):
        for x, (plot_a, plot_b) in enumerate(zip(row_a, row_b, strict=True)):
            for place, field in enumerate(PLOT_FIELDS):
                one, other = named(a, field, plot_a[place]), named(b, field, plot_b[place])
                if one != other:
                    found.append(f"({x},{y}) {field}: {one} against {other}")
    for slot in sorted(set(a["starts"]) | set(b["starts"]), key=int):
        one, other = (m["starts"].get(slot) and (m["starts"][slot]["x"], m["starts"][slot]["y"]) for m in (a, b))
        if one != other:
            found.append(f"start of slot {slot}: {one} against {other}")
    return found


def axial(x: int, y: int) -> tuple[int, int]:
    """A plot of the game's grid (odd rows sit half a hex to the east) in axial coordinates."""
    return x - (y - (y & 1)) // 2, y


def distance(a: tuple[int, int], b: tuple[int, int], data: dict) -> int:
    """Plots between two plots, round the world when the map wraps."""
    q1, r1 = axial(*a)
    steps = []
    for shift in (-data["w"], 0, data["w"]) if data["wrap_x"] else (0,):
        q2, r2 = axial(b[0] + shift, b[1])
        steps.append(max(abs(q1 - q2), abs(r1 - r2), abs((q1 + r1) - (q2 + r2))))
    return min(steps)


def neighbours(x: int, y: int, data: dict):
    east = y & 1
    for dx, dy in ((1, 0), (-1, 0), (east, 1), (east - 1, 1), (east, -1), (east - 1, -1)):
        nx, ny = x + dx, y + dy
        if not 0 <= ny < data["h"]:
            continue
        if data["wrap_x"]:
            nx %= data["w"]
        elif not 0 <= nx < data["w"]:
            continue
        yield nx, ny


def walkable(data: dict, x: int, y: int) -> bool:
    """Whether a land unit can stand there: flat land or hills, no ice and no natural wonder."""
    plot = data["rows"][y][x]
    feature = named(data, "feature", plot[FEATURE])
    return plot[PLOT] in (HILLS, LAND) and feature != "FEATURE_ICE" and (feature is None or feature in ORDINARY_FEATURES)


def walked_from(data: dict, start: tuple[int, int]) -> set[tuple[int, int]]:
    """Every plot a land unit reaches from `start` without embarking."""
    seen, queue = {start}, deque([start])
    while queue:
        for step in neighbours(*queue.popleft(), data):
            if step not in seen and walkable(data, *step):
                seen.add(step)
                queue.append(step)
    return seen


def surroundings(data: dict, start: tuple[int, int]) -> dict:
    """What lies within NEAR plots of a start: plots a city can work the land of, and what is on them."""
    counts = {"land": 0, "hills": 0, "river": 0, "strategic": 0}
    luxuries: set[str] = set()
    for y, row in enumerate(data["rows"]):
        for x, plot in enumerate(row):
            if plot[PLOT] in (OCEAN, MOUNTAIN) or distance(start, (x, y), data) > NEAR:
                continue
            counts["land"] += 1
            counts["hills"] += plot[PLOT] == HILLS
            counts["river"] += plot[RIVERS] != 0
            resource = named(data, "resource", plot[RESOURCE])
            counts["strategic"] += resource in STRATEGIC
            if resource and resource not in STRATEGIC and resource not in BONUS:
                luxuries.add(resource.removeprefix("RESOURCE_").lower())
    return {**counts, "luxuries": sorted(luxuries)}


def report(data: dict) -> dict:
    """The map in numbers: its land, and for every civilization's start its nearest rival, the capitals it walks
    to, the city-states near it and its surroundings."""
    spot = {slot: (at["x"], at["y"]) for slot, at in data["starts"].items()}
    majors = [slot for slot, at in data["starts"].items() if not at["who"].startswith(MINOR)]
    minors = [slot for slot in data["starts"] if slot not in majors]
    starts = {}
    for slot in sorted(majors, key=int):
        rivals = {other: distance(spot[slot], spot[other], data) for other in majors if other != slot}
        nearest = min(rivals, key=rivals.get) if rivals else None
        reached = walked_from(data, spot[slot])
        starts[slot] = {"who": data["starts"][slot]["who"],
                        "nearest": nearest and data["starts"][nearest]["who"], "nearest_plots": rivals.get(nearest),
                        "capitals_walked_to": sum(spot[other] in reached for other in rivals), "rivals": len(rivals),
                        "city_states_near": sum(distance(spot[slot], spot[m], data) <= STATES_WITHIN for m in minors),
                        **surroundings(data, spot[slot])}
    return {"land": sum(plot[PLOT] in (HILLS, LAND) for row in data["rows"] for plot in row),
            "city_states": len(minors), "starts": starts}


def report_lines(numbers: dict) -> list[str]:
    def short(who):
        return who.removeprefix("CIVILIZATION_").title()
    lines = [f"land plots {numbers['land']}, city-states {numbers['city_states']}"]
    for slot, s in numbers["starts"].items():
        nearest = f"nearest {short(s['nearest'])} {s['nearest_plots']}" if s["nearest"] else "no rival"
        lines.append(f"{slot} {short(s['who']):9} {nearest}"
                     f" | walks to {s['capitals_walked_to']} of {s['rivals']} capitals"
                     f" | city-states within {STATES_WITHIN}: {s['city_states_near']}"
                     f" | within {NEAR}: land {s['land']} hills {s['hills']} river {s['river']}"
                     f" strategic {s['strategic']} luxuries {','.join(s['luxuries']) or 'none'}")
    return lines


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    how = ap.add_mutually_exclusive_group(required=True)
    how.add_argument("--read", type=Path, metavar="FILE", help="read the map of the game on screen into FILE")
    how.add_argument("--script", type=Path, metavar="FILE", help="write the map script that lays FILE out again")
    how.add_argument("--report", type=Path, nargs="+", metavar="FILE", help="what each file gives each civilization")
    how.add_argument("--same", type=Path, nargs=2, metavar="FILE", help="say where two files differ")
    a = ap.parse_args(argv)
    try:
        if a.read:
            from harness.game import Game
            data = read_game(Game())
            a.read.write_text(json.dumps(data) + "\n")
            print(f"{data['w']} by {data['h']}, {len(data['starts'])} starting plots, read on turn {data['read_on_turn']}")
        elif a.script:
            print(write_script(load(a.script)))
        elif a.report:
            for path in a.report:
                print("\n  ".join([path.stem, *report_lines(report(load(path)))]))
        else:
            found = differences(*(load(path) for path in a.same))
            print("\n".join([*found[:20], f"{len(found)} differences" if found else "the same map"]))
            return 1 if found else 0
    except run.Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
