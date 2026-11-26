"""scripts/benchmark_map.py: a map kept as data, read out of the game and laid out again by a map script.

No game: the game's answer is written out here, and the map script runs against a tiny fake engine under lupa that
writes down every call it gets.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import benchmark_map
import benchmark_run

try:
    import lupa
except ImportError:  # pragma: no cover
    lupa = None

# A map two plots wide and two high. South row: grass with a river on its east edge, ocean. North row: grass hills
# with forest, 3 iron and ancient ruins; a grass mountain with rivers on its two southern edges and a barbarian camp.
ANSWER = [
    "size\t2\t2\ttrue",
    "row\t0\t2,0,-1,-1,0,1,2,-1,-1,-1,1;3,1,-1,-1,0,0,-1,-1,-1,-1,0",
    "row\t1\t1,0,5,7,3,0,-1,-1,-1,9,1;0,0,-1,-1,0,6,-1,3,4,8,1",
    "terrain\t0\tTERRAIN_GRASS", "terrain\t1\tTERRAIN_OCEAN",
    "feature\t5\tFEATURE_FOREST",
    "resource\t7\tRESOURCE_IRON",
    "improvement\t8\tIMPROVEMENT_BARBARIAN_CAMP", "improvement\t9\tIMPROVEMENT_GOODY_HUT",
    "start\t0\tCIVILIZATION_POLAND\t0\t0",
    "start\t22\tMINOR_CIV_GENEVA\t0\t1",
    "turn\t0",
]

# The engine as the map script meets it. Slots 0, 1 and 22 exist; slot 1 was never alive.
ENGINE = r"""
CALLS = {}
local function note(...) CALLS[#CALLS + 1] = table.concat({...}, " ") end
function include() end
GameInfoTypes = {TERRAIN_GRASS = 10, TERRAIN_OCEAN = 11, FEATURE_FOREST = 20, RESOURCE_IRON = 30,
                 IMPROVEMENT_GOODY_HUT = 40}
GameDefines = {MAX_CIV_PLAYERS = 63}
local function plot(x, y)
  local at = x .. "," .. y
  local p = {at = at}
  for _, call in ipairs({"SetPlotType", "SetTerrainType", "SetWOfRiver", "SetNWOfRiver", "SetNEOfRiver",
                         "SetFeatureType", "SetResourceType", "SetImprovementType", "SetContinentArtType"}) do
    p[call] = function(_, a, b) note(at, call, tostring(a), tostring(b)) end
  end
  return p
end
Map = {GetPlot = function(x, y) return plot(x, y) end, RecalculateAreas = function() note("areas") end}
local function player(slot, ever_alive)
  return {IsEverAlive = function() return ever_alive end,
          SetStartingPlot = function(_, p) note("slot", slot, "starts", p.at) end}
end
Players = {[0] = player(0, true), [1] = player(1, false), [22] = player(22, true)}
"""


def the_map() -> dict:
    return benchmark_map.read_map(ANSWER)


@unittest.skipIf(lupa is None, "lupa is not installed")
class TheMapScript(unittest.TestCase):
    def lay_out(self, data: dict, more_engine: str = "") -> list[str]:
        lua = lupa.LuaRuntime()
        lua.execute(ENGINE + more_engine)
        lua.execute(benchmark_map.script_of(data))
        lua.eval("GenerateMap")()
        return list(lua.globals().CALLS.values())

    def test_every_plot_gets_what_the_file_says_under_the_games_own_numbers(self):
        calls = self.lay_out(the_map())
        for call in ("0,0 SetPlotType 2 false", "1,0 SetPlotType 3 false", "1,1 SetPlotType 0 false",
                     "0,0 SetTerrainType 10 false", "1,0 SetTerrainType 11 false",
                     "0,1 SetFeatureType 20 -1", "0,1 SetResourceType 30 3", "0,1 SetImprovementType 40 nil",
                     "0,0 SetContinentArtType 1 nil", "1,0 SetContinentArtType 0 nil"):
            self.assertIn(call, calls)

    def test_a_river_is_laid_on_the_edge_it_was_read_from_with_its_flow(self):
        calls = self.lay_out(the_map())
        self.assertIn("0,0 SetWOfRiver true 2", calls)
        self.assertIn("1,1 SetNWOfRiver true 3", calls)
        self.assertIn("1,1 SetNEOfRiver true 4", calls)
        self.assertEqual(sum("River" in call for call in calls), 3)

    def test_nothing_is_put_where_the_file_has_nothing(self):
        calls = self.lay_out(the_map())
        self.assertEqual([c for c in calls if "SetFeatureType" in c], ["0,1 SetFeatureType 20 -1"])
        self.assertEqual([c for c in calls if "SetResourceType" in c], ["0,1 SetResourceType 30 3"])
        self.assertEqual([c for c in calls if "SetImprovementType" in c], ["0,1 SetImprovementType 40 nil"])

    def test_the_order_is_land_then_areas_then_rivers_and_features_then_areas_then_resources(self):
        calls = self.lay_out(the_map())
        first = {word: next(i for i, c in enumerate(calls) if word in c)
                 for word in ("SetPlotType", "SetTerrainType", "SetWOfRiver", "SetFeatureType", "SetResourceType")}
        areas = [i for i, c in enumerate(calls) if c == "areas"]
        self.assertEqual(len(areas), 2)
        self.assertLess(first["SetPlotType"], first["SetTerrainType"])
        self.assertLess(first["SetTerrainType"], areas[0])
        self.assertLess(areas[0], first["SetWOfRiver"])
        self.assertLess(first["SetFeatureType"], areas[1])
        self.assertLess(areas[1], first["SetResourceType"])

    def test_a_slot_starts_on_its_plot_and_a_slot_that_never_lived_is_passed_over(self):
        calls = self.lay_out(the_map())
        self.assertEqual([c for c in calls if c.startswith("slot")], ["slot 0 starts 0,0", "slot 22 starts 0,1"])

    def test_a_player_the_map_has_no_starting_plot_for_stops_the_script(self):
        data = the_map()
        del data["starts"]["22"]
        with self.assertRaisesRegex(lupa.LuaError, "no starting plot for the player in slot 22"):
            self.lay_out(data)

    def test_a_type_the_game_does_not_know_stops_the_script(self):
        with self.assertRaisesRegex(lupa.LuaError, "does not know RESOURCE_IRON"):
            self.lay_out(the_map(), more_engine="GameInfoTypes.RESOURCE_IRON = nil")

    def test_the_script_says_the_size_of_the_map_whatever_size_the_setup_screen_asks_for(self):
        lua = lupa.LuaRuntime()
        lua.execute(ENGINE)
        lua.execute(benchmark_map.script_of(the_map()))
        init = lua.eval("GetMapInitData")(5)
        self.assertEqual((init.Width, init.Height, init.WrapX, init.WrapY), (2, 2, True, False))


class ReadingTheGamesAnswer(unittest.TestCase):
    def test_types_are_kept_by_name_through_the_maps_own_legend(self):
        data = the_map()
        self.assertEqual(data["legend"], {"terrain": ["TERRAIN_GRASS", "TERRAIN_OCEAN"], "feature": ["FEATURE_FOREST"],
                                          "resource": ["RESOURCE_IRON"], "improvement": ["IMPROVEMENT_GOODY_HUT"]})
        self.assertEqual(data["rows"][1][0], [1, 1, 1, 1, 3, 0, -1, -1, -1, 1, 1])
        self.assertEqual((data["w"], data["h"], data["wrap_x"], data["read_on_turn"]), (2, 2, True, 0))

    def test_an_improvement_that_is_a_games_and_not_the_maps_is_left_out(self):
        self.assertEqual(the_map()["rows"][1][1][benchmark_map.IMPROVEMENT], 0)

    def test_every_slots_starting_plot_is_kept_with_who_held_it(self):
        self.assertEqual(the_map()["starts"], {"0": {"who": "CIVILIZATION_POLAND", "x": 0, "y": 0},
                                               "22": {"who": "MINOR_CIV_GENEVA", "x": 0, "y": 1}})

    def test_an_answer_with_a_row_missing_is_refused(self):
        with self.assertRaisesRegex(benchmark_run.Refused, "not a whole map"):
            benchmark_map.read_map([line for line in ANSWER if not line.startswith("row\t1")])


class WhereTwoMapsDiffer(unittest.TestCase):
    def test_a_map_is_the_same_as_itself_whoever_holds_its_slots(self):
        other = the_map()
        other["starts"]["0"]["who"] = "CIVILIZATION_ROME"
        self.assertEqual(benchmark_map.differences(the_map(), other), [])

    def test_a_changed_plot_is_named_with_both_types_in_words(self):
        other = benchmark_map.read_map([line.replace("TERRAIN_OCEAN", "TERRAIN_COAST") for line in ANSWER])
        self.assertEqual(benchmark_map.differences(the_map(), other), ["(1,0) terrain: TERRAIN_OCEAN against TERRAIN_COAST"])

    def test_a_moved_start_is_named(self):
        other = the_map()
        other["starts"]["0"].update(x=0, y=1)
        self.assertEqual(benchmark_map.differences(the_map(), other), ["start of slot 0: (0, 0) against (0, 1)"])

    def test_maps_of_two_sizes_differ_in_size_and_are_not_compared_further(self):
        other = the_map()
        other["w"] = 3
        self.assertEqual(benchmark_map.differences(the_map(), other), ["w: 2 against 3"])


def strip_of_land(width: int, wrap: bool, sea_at: tuple[int, ...] = (), starts: dict | None = None) -> dict:
    """One row of flat grass, `sea_at` its ocean plots."""
    row = [[benchmark_map.OCEAN if x in sea_at else benchmark_map.LAND, 1, 0, 0, 0, 0, -1, -1, -1, 0, 1]
           for x in range(width)]
    return {"w": width, "h": 1, "wrap_x": wrap, "rows": [row], "starts": starts or {},
            "legend": {"terrain": ["TERRAIN_GRASS"], "feature": [], "resource": [], "improvement": []}}


class TheMapInNumbers(unittest.TestCase):
    def test_plots_between_two_plots_follow_the_games_grid_of_shifted_rows(self):
        data = {"w": 10, "h": 10, "wrap_x": False}
        self.assertEqual(benchmark_map.distance((0, 0), (0, 2), data), 2)
        self.assertEqual(benchmark_map.distance((0, 0), (1, 2), data), 2)
        self.assertEqual(benchmark_map.distance((0, 0), (2, 2), data), 3)
        self.assertEqual(benchmark_map.distance((3, 1), (3, 0), data), 1)
        self.assertEqual(benchmark_map.distance((3, 1), (4, 0), data), 1)
        self.assertEqual(benchmark_map.distance((3, 1), (2, 0), data), 2)

    def test_a_map_that_wraps_is_measured_the_short_way_round(self):
        self.assertEqual(benchmark_map.distance((0, 0), (9, 0), {"w": 10, "h": 1, "wrap_x": True}), 1)
        self.assertEqual(benchmark_map.distance((0, 0), (9, 0), {"w": 10, "h": 1, "wrap_x": False}), 9)

    def test_a_capital_across_the_sea_is_not_walked_to_unless_the_map_wraps_round_to_it(self):
        starts = {"0": {"who": "CIVILIZATION_POLAND", "x": 0, "y": 0}, "1": {"who": "CIVILIZATION_ROME", "x": 5, "y": 0}}
        cut_off = benchmark_map.report(strip_of_land(6, wrap=False, sea_at=(3,), starts=starts))
        round_the_world = benchmark_map.report(strip_of_land(6, wrap=True, sea_at=(3,), starts=starts))
        self.assertEqual(cut_off["starts"]["0"]["capitals_walked_to"], 0)
        self.assertEqual(round_the_world["starts"]["0"]["capitals_walked_to"], 1)
        self.assertEqual(round_the_world["starts"]["0"]["nearest_plots"], 1)

    def test_a_natural_wonder_and_ice_are_not_walked_over(self):
        for feature in ("FEATURE_FUJI", "FEATURE_ICE"):
            data = strip_of_land(3, wrap=False)
            data["legend"]["feature"] = [feature]
            data["rows"][0][1][benchmark_map.FEATURE] = 1
            self.assertEqual(benchmark_map.walked_from(data, (0, 0)), {(0, 0)})

    def test_a_starts_surroundings_count_land_and_tell_luxuries_from_other_resources(self):
        data = strip_of_land(8, wrap=False, sea_at=(1,), starts={"0": {"who": "CIVILIZATION_POLAND", "x": 0, "y": 0},
                                                                   "22": {"who": "MINOR_CIV_GENEVA", "x": 7, "y": 0}})
        data["legend"]["resource"] = ["RESOURCE_IRON", "RESOURCE_WHEAT", "RESOURCE_SILK"]
        for x, resource in ((2, 1), (3, 2), (4, 3), (7, 3)):
            data["rows"][0][x][benchmark_map.RESOURCE] = resource
        data["rows"][0][2][benchmark_map.PLOT] = benchmark_map.HILLS
        data["rows"][0][2][benchmark_map.RIVERS] = 1
        numbers = benchmark_map.report(data)
        start = numbers["starts"]["0"]
        self.assertEqual((numbers["land"], numbers["city_states"]), (7, 1))
        self.assertEqual({k: start[k] for k in ("land", "hills", "river", "strategic", "luxuries")},
                         {"land": 5, "hills": 1, "river": 1, "strategic": 1, "luxuries": ["silk"]})
        self.assertEqual((start["city_states_near"], start["nearest"], start["rivals"]), (1, None, 0))


class TheCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        saves = self.tmp / "Saves" / "single"
        saves.mkdir(parents=True)
        patch = mock.patch.dict(os.environ, {"CIV5_SAVES_DIR": str(saves)})
        patch.start()
        self.addCleanup(patch.stop)
        self.file = self.tmp / "map.json"
        self.file.write_text(json.dumps(the_map()))

    def run_main(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = benchmark_map.main(list(argv))
        return rc, out.getvalue()

    def test_the_script_goes_into_the_games_folder_of_maps_beside_its_saves(self):
        rc, said = self.run_main("--script", str(self.file))
        script = self.tmp / "Maps" / "omt_map.lua"
        self.assertEqual((rc, said.strip()), (0, str(script)))
        self.assertEqual(script.read_text(), benchmark_map.script_of(the_map()))

    def test_two_files_of_one_map_are_the_same_and_the_command_ends_well(self):
        self.assertEqual(self.run_main("--same", str(self.file), str(self.file)), (0, "the same map\n"))

    def test_two_files_that_differ_end_the_command_badly_and_say_where(self):
        other = the_map()
        other["rows"][0][0][benchmark_map.QUANTITY] = 2
        (self.tmp / "other.json").write_text(json.dumps(other))
        rc, said = self.run_main("--same", str(self.file), str(self.tmp / "other.json"))
        self.assertEqual((rc, said), (1, "(0,0) quantity: 0 against 2\n1 differences\n"))

    def test_the_report_gives_a_line_a_civilization(self):
        rc, said = self.run_main("--report", str(self.file))
        self.assertEqual(rc, 0)
        self.assertIn("map\n  land plots 2, city-states 1\n  0 Poland    no rival | walks to 0 of 0 capitals", said)

    def test_reading_the_game_writes_the_file_and_says_what_was_read(self):
        game = mock.Mock()
        game.c.exec.return_value = ANSWER
        with mock.patch("harness.game.Game", return_value=game):
            rc, said = self.run_main("--read", str(self.tmp / "read.json"))
        self.assertEqual((rc, said), (0, "2 by 2, 2 starting plots, read on turn 0\n"))
        self.assertEqual(json.loads((self.tmp / "read.json").read_text()), the_map())
        self.assertEqual(game.c.exec.call_args.args, ("InGame", benchmark_map.READ))


if __name__ == "__main__":
    unittest.main()
