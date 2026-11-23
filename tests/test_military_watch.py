"""The military situation on every status of the seat's own turn (runtime v346; the user, 2026-11-23: "giving the
LLM the info it needs in real time").

Live, small-king-venice-a, Sonnet 5.5: Venice held two Warriors and a Scout beside the Zulus at turn 88, bought a
Market with 380 gold on turn 82 and was told of an army only once it stood 4 plots from the city and the war was on;
the city fell on turn 95. `status.military` now carries the Demographics screen's Soldiers row, the armies of other
players in sight near the seat's cities (at peace too) and each city under threat; a run of quiet turns stops on
what changes in it and the briefing warns of it.
"""
import unittest

import test_mcp_safety as support
from harness import military
from harness.briefing import build
from harness.briefing import warnings as briefing_warnings
from test_finish_turn import QUIET, ScriptedGame, status


WORLD = """
GameDefines = { MAX_MAJOR_CIVS = 4 }
YieldTypes = { YIELD_GOLD = 2 }
MajorCivApproachTypes = { MAJOR_CIV_APPROACH_HOSTILE = 1, MAJOR_CIV_APPROACH_GUARDED = 3, MAJOR_CIV_APPROACH_FRIENDLY = 5 }
UNITS = { [1] = { ID = 1, Type = 'UNIT_WARRIOR', Combat = 8, RangedCombat = 0 },
          [2] = { ID = 2, Type = 'UNIT_ARCHER', Combat = 5, RangedCombat = 7 },
          [3] = { ID = 3, Type = 'UNIT_SWORDSMAN', Combat = 14, RangedCombat = 0 },
          [4] = { ID = 4, Type = 'UNIT_WORKER', Combat = 0, RangedCombat = 0 },
          [5] = { ID = 5, Type = 'UNIT_IMPI', Combat = 16, RangedCombat = 0 } }
BUILDINGS = { [1] = { ID = 1, Type = 'BUILDING_WALLS', Defense = 500 }, [2] = { ID = 2, Type = 'BUILDING_MARKET', Defense = 0 } }
local function rows(t)
  return function() local i = 0; return function() i = i + 1; return t[i] end end
end
GameInfo = { Units = setmetatable(UNITS, { __call = rows(UNITS) }), Buildings = setmetatable(BUILDINGS, { __call = rows(BUILDINGS) }) }
Map = { PlotDistance = function(x1, y1, x2, y2) return math.max(math.abs(x1 - x2), math.abs(y1 - y2)) end }
HIDDEN, OWNER = {}, {}                       -- plots the seat does not see, and who owns a plot ("x,y")
function unit(kind, x, y)
  local u = UNITS[kind]
  return { GetUnitType = function() return kind end, GetX = function() return x end, GetY = function() return y end,
           IsCombatUnit = function() return u.Combat > 0 or u.RangedCombat > 0 end, IsDelayedDeath = function() return false end,
           IsInvisible = function() return false end, GetBaseCombatStrength = function() return u.Combat end,
           GetBaseRangedCombatStrength = function() return u.RangedCombat end,
           GetPlot = function()
             return { IsVisible = function() return not HIDDEN[x .. ',' .. y] end,
                      GetOwner = function() return OWNER[x .. ',' .. y] or -1 end }
           end }
end
GOLD, PRICE, UNLISTED = 300, { [1] = 110, [2] = 180, [3] = 340, [5] = 400 }, { [5] = true }
WALLS_PRICE, HAS_WALLS = 280, false
function city(id, name, x, y)
  local c = { damage = 0, garrison = nil }
  c.GetID = function() return id end; c.GetName = function() return name end
  c.GetX = function() return x end; c.GetY = function() return y end
  c.GetDamage = function() return c.damage end; c.GetMaxHitPoints = function() return 200 end
  c.GetStrengthValue = function() return 1450 end
  c.GetGarrisonedUnit = function() return c.garrison end
  c.IsCapital = function() return c.capital or false end
  c.Plot = function() return { IsVisible = function() return not HIDDEN[x .. ',' .. y] end } end
  c.IsCanPurchase = function(_, test_gold, _, uid, bid)
    if uid >= 0 then return PRICE[uid] ~= nil and not UNLISTED[uid] and (not test_gold or PRICE[uid] <= GOLD) end
    return bid == 1 and not HAS_WALLS and (not test_gold or WALLS_PRICE <= GOLD)
  end
  c.GetUnitPurchaseCost = function(_, uid) return PRICE[uid] end
  c.GetBuildingPurchaseCost = function() return WALLS_PRICE end
  return c
end
MIGHT, WAR, MET = { [0] = 4, [1] = 100, [2] = 36, [3] = 9 }, {}, { [1] = true, [2] = true }
local function player(i, name, opts)
  opts = opts or {}
  local p = { units = {}, cities = {} }
  p.IsAlive = function() return not p.dead end; p.IsMinorCiv = function() return opts.minor or false end
  p.IsBarbarian = function() return opts.barbarian or false end; p.IsHuman = function() return i == 0 end
  p.GetTeam = function() return i end; p.GetMilitaryMight = function() return MIGHT[i] or 0 end
  p.GetCivilizationShortDescription = function() return name end
  p.GetGold = function() return GOLD end
  p.GetApproachTowardsUsGuess = function(_, other) return APPROACH and APPROACH[other] or 3 end
  p.Units = function() local k = 0; return function() k = k + 1; return p.units[k] end end
  p.Cities = function() local k = 0; return function() k = k + 1; return p.cities[k] end end
  return p
end
Players = { [0] = player(0, 'Venice'), [1] = player(1, 'The Zulus'), [2] = player(2, 'Germany'), [3] = player(3, 'Korea'),
            [22] = player(22, 'Mombasa', { minor = true }), [63] = player(63, 'Barbarians', { barbarian = true }) }
Teams = {}
for _, i in ipairs({ 0, 1, 2, 3, 22, 63 }) do
  Teams[i] = { IsAtWar = function(_, t) return WAR[t] or false end, IsHasMet = function(_, t) return MET[t] or false end }
end
VENICE = city(8192, 'Venice', 10, 10)
Players[0].cities = { VENICE }
Players[0].units = { unit(1, 10, 10), unit(1, 11, 10), unit(4, 10, 11) }
function watch() return H.military_watch(0) end
function zulus(n, x, y) for k = 1, n do Players[1].units[#Players[1].units + 1] = unit(k % 2 == 0 and 5 or 3, x, y + k - 1) end end
"""


class MilitaryWatchLuaTests(unittest.TestCase):
    run_lua = support.LuaRuntimeTests.run_lua

    def setUp(self):
        support.LuaRuntimeTests.setUp(self)
        self.run_lua(WORLD)

    def test_the_soldiers_row_is_the_demographics_screens(self):
        self.run_lua("""
        local m = watch()
        assert(m.soldiers.mine == 4000 and m.soldiers.rank == 4 and m.soldiers.of == 4, H.json(m))
        assert(m.soldiers.best == 20000 and m.soldiers.best_civ == 'The Zulus', H.json(m))
        assert(m.soldiers.average == math.floor((4000 + 20000 + 12000 + 6000) / 4 + 0.5), H.json(m))
        assert(m.combat_units == 2, 'a Worker is no combat unit: ' .. H.json(m))
        assert(m.forces == nil and m.cities == nil and m.sieges == nil, H.json(m))
        """)

    def test_the_diplomacy_lists_word_for_each_met_leader_at_peace(self):
        self.run_lua("""
        APPROACH = { [1] = 1, [2] = 5 }
        local a = watch().approach
        assert(a['The Zulus'] == 'HOSTILE' and a['Germany'] == 'FRIENDLY' and a['Korea'] == nil, H.json(a))
        WAR[1] = true
        a = watch().approach
        assert(a['The Zulus'] == nil and a['Germany'] == 'FRIENDLY', 'a leader at war has no word: ' .. H.json(a))
        """)

    def test_an_enemy_city_in_sight_near_my_units_says_what_stands_around_it(self):
        self.run_lua("""
        WAR[1] = true
        local ulundi = city(1, 'Ulundi', 30, 30)
        ulundi.capital = true; ulundi.damage = 50
        Players[1].cities = { ulundi, city(2, 'Bulawayo', 60, 60) }
        Players[1].units = { unit(5, 30, 31), unit(5, 40, 40) }
        assert(watch().sieges == nil, 'no unit of mine near it: ' .. H.json(watch()))
        Players[0].units = { unit(1, 28, 30), unit(2, 28, 31), unit(2, 34, 30), unit(4, 29, 30) }
        local g = watch().sieges
        assert(#g == 1 and g[1].city == 'Ulundi' and g[1].civ == 'The Zulus' and g[1].capital == true, H.json(g))
        assert(g[1].x == 30 and g[1].y == 30 and g[1].hp == 150 and g[1].max_hp == 200 and g[1].strength == 15, H.json(g))
        assert(g[1].my_units_close.units == 2 and g[1].my_units_close.types.ARCHER == 1, H.json(g))
        assert(g[1].enemy_units_close.units == 1 and g[1].enemy_units_close.types.IMPI == 1, H.json(g))
        HIDDEN['30,30'] = true
        assert(watch().sieges == nil, 'a city I do not see now: ' .. H.json(watch()))
        """)

    def test_the_highest_is_not_named_when_it_is_not_met_and_is_you_when_it_is_mine(self):
        self.run_lua("""
        MET[1] = nil
        assert(watch().soldiers.best_civ == nil and watch().soldiers.best == 20000, H.json(watch()))
        MIGHT[0] = 400
        local s = watch().soldiers
        assert(s.rank == 1 and s.best_civ == 'you' and s.best == 40000, H.json(s))
        """)

    def test_an_army_at_peace_is_listed_from_three_units_in_sight_near_a_city(self):
        self.run_lua("""
        APPROACH = { [1] = 1 }
        zulus(2, 14, 9)
        assert(watch().forces == nil, 'two units are not an army: ' .. H.json(watch()))
        zulus(2, 13, 9)
        OWNER['13,9'] = 0
        local f = watch().forces
        assert(#f == 1 and f[1].civ == 'The Zulus' and f[1].player_id == 1 and f[1].at_war == false, H.json(f))
        assert(f[1].units == 4 and f[1].types.SWORDSMAN == 2 and f[1].types.IMPI == 2 and f[1].strength == 60, H.json(f))
        assert(f[1].nearest.city == 'Venice' and f[1].nearest.distance == 3 and f[1].in_my_land == 1, H.json(f))
        assert(f[1].approach_guess == 'MAJOR_CIV_APPROACH_HOSTILE', H.json(f))
        assert(watch().cities == nil, 'an army at peace threatens no city: ' .. H.json(watch()))
        """)

    def test_units_out_of_sight_or_far_from_every_city_are_not_counted(self):
        self.run_lua("""
        zulus(3, 13, 9)
        HIDDEN['13,9'] = true; HIDDEN['13,10'] = true
        assert(watch().forces == nil, H.json(watch()))
        HIDDEN = {}
        Players[1].units = {}
        zulus(3, 17, 10)
        assert(watch().forces == nil, 'six plots away: ' .. H.json(watch()))
        """)

    def test_an_enemy_and_the_barbarians_are_listed_from_the_first_unit_and_a_city_state_only_at_war(self):
        self.run_lua("""
        Players[63].units = { unit(1, 12, 10) }
        Players[22].units = { unit(2, 9, 12), unit(2, 9, 13), unit(2, 9, 14) }
        local f = watch().forces
        assert(#f == 1 and f[1].civ == 'Barbarians' and f[1].at_war == true and f[1].player_id == nil, H.json(f))
        WAR[1] = true; WAR[22] = true; MET[22] = true
        zulus(1, 15, 10)
        f = watch().forces
        assert(#f == 3 and f[1].civ == 'Mombasa' and f[1].units == 3, 'at war first, the most units first: ' .. H.json(f))
        assert(f[2].civ == 'Barbarians' or f[2].civ == 'The Zulus', H.json(f))
        assert(f[1].approach_guess == nil and f[2].approach_guess == nil and f[3].approach_guess == nil, H.json(f))
        """)

    def test_a_city_with_hostile_units_close_says_what_holds_it_and_what_the_treasury_buys(self):
        self.run_lua("""
        WAR[1] = true
        zulus(3, 12, 9)
        VENICE.damage = 60
        VENICE.garrison = Players[0].units[1]
        local c = watch().cities
        assert(#c == 1 and c[1].id == 8192 and c[1].name == 'Venice' and c[1].hp == 140 and c[1].max_hp == 200, H.json(c))
        assert(c[1].strength == 15 and c[1].garrison == 'WARRIOR', H.json(c))
        assert(c[1].hostile_close.units == 3 and c[1].hostile_close.types.SWORDSMAN == 2, H.json(c))
        local buy = c[1].can_buy
        assert(buy.gold == 300 and #buy.units == 2, H.json(buy))
        assert(buy.units[1].item == 'UNIT_WARRIOR' and buy.units[1].gold == 110 and buy.units[1].strength == 8, H.json(buy))
        assert(buy.units[2].item == 'UNIT_ARCHER' and buy.units[2].ranged == 7, 'strongest first: ' .. H.json(buy))
        assert(#buy.buildings == 1 and buy.buildings[1].item == 'BUILDING_WALLS' and buy.buildings[1].gold == 280, H.json(buy))
        assert(buy.cheapest_unit == nil, H.json(buy))
        """)

    def test_a_treasury_that_buys_nothing_says_the_cheapest_unit_and_its_price(self):
        self.run_lua("""
        WAR[1] = true
        zulus(1, 11, 11)
        GOLD = 90
        local c = watch().cities[1]
        assert(c.garrison == false, H.json(c))
        assert(#c.can_buy.units == 0 and c.can_buy.buildings == nil, H.json(c))
        assert(c.can_buy.cheapest_unit.item == 'UNIT_WARRIOR' and c.can_buy.cheapest_unit.gold == 110, H.json(c))
        """)

    def test_a_city_only_barbarians_stand_by_lists_no_purchases_until_it_is_damaged(self):
        self.run_lua("""
        Players[63].units = { unit(1, 11, 10) }
        local c = watch().cities[1]
        assert(c.hostile_close.units == 1 and c.can_buy ~= nil, 'a barbarian is hostile: ' .. H.json(c))
        Players[63].units = {}
        assert(watch().cities == nil, H.json(watch()))
        VENICE.damage = 10
        assert(watch().cities[1].hp == 190 and watch().cities[1].hostile_close == nil, H.json(watch()))
        """)

    def test_a_seat_with_no_city_has_its_soldiers_row_and_nothing_else(self):
        self.run_lua("""
        Players[0].cities = {}
        zulus(4, 11, 10)
        local m = watch()
        assert(m.soldiers.rank == 4 and m.forces == nil and m.cities == nil, H.json(m))
        """)

    def test_the_distances_and_the_peace_threshold(self):
        self.run_lua("""
        assert(H.MILITARY_NEAR == 5 and H.MILITARY_CLOSE == 3 and H.MILITARY_PEACE_MIN == 3)
        """)


def forces(units, at_war=False, civ="The Zulus", **extra):
    return {"civ": civ, "player_id": 1, "at_war": at_war, "units": units, "strength": 14 * units,
            "types": {"SWORDSMAN": units}, "in_my_land": 0, "nearest": {"city": "Venice", "distance": 3}, **extra}


def city(hp, **extra):
    return {"id": 8192, "name": "Venice", "hp": hp, "max_hp": 200, "strength": 15, "garrison": False, **extra}


def mil(*rows, cities=None, rank=6, of=6, mine=4000, best=24000, best_civ="The Zulus", units=3, approach=None,
        sieges=None):
    m = {"soldiers": {"mine": mine, "rank": rank, "of": of, "best": best, "average": 15000}, "combat_units": units}
    if best_civ:
        m["soldiers"]["best_civ"] = best_civ
    if rows:
        m["forces"] = list(rows)
    if cities:
        m["cities"] = list(cities)
    if approach:
        m["approach"] = dict(approach)
    if sieges:
        m["sieges"] = list(sieges)
    return m


class RecordTests(unittest.TestCase):
    def test_a_status_without_the_block_has_no_record(self):
        self.assertIsNone(military.record({"turn": 5}))
        self.assertIsNone(military.record({"military": mil()}))

    def test_the_record_keeps_the_civilizations_and_leaves_the_barbarians_out(self):
        barbarians = {"civ": "Barbarians", "at_war": True, "units": 2}
        rec = military.record({"turn": 80, "military": mil(forces(4), barbarians, cities=[city(180)])})
        self.assertEqual(rec, {"turn": 80, "forces": {"The Zulus": [4, False]}, "cities": {"8192": ["Venice", 180]},
                               "last": True, "approach": {}})

    def test_nothing_wakes_without_a_baseline_but_an_enemy_army(self):
        rec = military.record({"turn": 80, "military": mil(forces(4))})
        self.assertEqual(military.wake_reasons(rec, None), [])
        rec = military.record({"turn": 80, "military": mil(forces(4, at_war=True))})
        self.assertEqual(military.wake_reasons(rec, None), ["enemy_forces_near:The Zulus:4"])

    def test_an_army_at_peace_wakes_when_it_appears_and_when_it_grows_by_two(self):
        def rec(turn, *rows):
            return military.record({"turn": turn, "military": mil(*rows)})
        self.assertEqual(military.wake_reasons(rec(81, forces(3)), rec(80)), ["foreign_forces_near:The Zulus:0->3"])
        self.assertEqual(military.wake_reasons(rec(82, forces(4)), rec(81, forces(3))), [])
        self.assertEqual(military.wake_reasons(rec(82, forces(5)), rec(81, forces(3))), ["foreign_forces_near:The Zulus:3->5"])
        self.assertEqual(military.wake_reasons(rec(82, forces(3)), rec(81, forces(5))), [])
        self.assertEqual(military.wake_reasons(rec(81, forces(5)), rec(81, forces(3))), [], "the same turn read twice")

    def test_a_city_wakes_when_it_is_first_listed_and_when_it_loses_hit_points(self):
        def rec(turn, *cities):
            return military.record({"turn": turn, "military": mil(cities=cities)})
        self.assertEqual(military.wake_reasons(rec(90, city(200)), rec(89)), ["city_threatened:Venice"])
        self.assertEqual(military.wake_reasons(rec(91, city(160)), rec(90, city(200))), ["city_damaged:Venice:200->160"])
        self.assertEqual(military.wake_reasons(rec(92, city(180)), rec(91, city(160))), [], "healing is quiet")

    def test_the_lowest_soldiers_figure_wakes_once(self):
        def rec(turn, rank):
            return military.record({"turn": turn, "military": mil(rank=rank)})
        self.assertEqual(military.wake_reasons(rec(41, 6), rec(40, 5)), ["soldiers_rank_lowest"])
        self.assertEqual(military.wake_reasons(rec(42, 6), rec(41, 6)), [])


    def test_a_leader_turning_wary_wakes_and_one_turning_friendly_does_not(self):
        def rec(turn, **approach):
            return military.record({"turn": turn, "military": mil(rank=3, approach=approach)})
        self.assertEqual(military.wake_reasons(rec(61, Zulus="HOSTILE", Germany="FRIENDLY"), rec(60, Zulus="NEUTRAL", Germany="NEUTRAL")),
                         ["approach_changed:Zulus:NEUTRAL->HOSTILE"])
        self.assertEqual(military.wake_reasons(rec(62, Zulus="HOSTILE"), rec(61, Zulus="HOSTILE")), [])
        self.assertEqual(military.wake_reasons(rec(62, Zulus="GUARDED"), rec(61)), [], "a leader just met has no earlier word")

    def test_a_record_kept_by_an_older_version_still_compares(self):
        old = {"turn": 60, "forces": {}, "cities": {}, "last": False}
        self.assertEqual(military.as_record(old), old)
        rec = military.record({"turn": 61, "military": mil(rank=3, approach={"Zulus": "HOSTILE"})})
        self.assertEqual(military.wake_reasons(rec, old), [])


class QuietRunTests(unittest.TestCase):
    def test_a_run_stops_on_the_turn_an_army_at_peace_comes_into_sight(self):
        g = ScriptedGame([(status(2, military=mil()), QUIET), (status(3, military=mil()), QUIET),
                          (status(4, military=mil(forces(4))), QUIET), (status(5, military=mil(forces(4))), QUIET)],
                         first_status=status(1, military=mil()))
        r = g.finish_turn(skip_quiet_turns=9)
        self.assertEqual((r["turn"], r["turns_skipped"]), (4, 2))
        self.assertEqual(r["woke_because"], ["foreign_forces_near:The Zulus:0->4"])
        self.assertEqual(r["status"]["military"]["forces"][0]["units"], 4)

    def test_the_same_army_standing_there_lets_the_next_turns_pass(self):
        g = ScriptedGame([(status(2, military=mil(forces(4))), QUIET), (status(3, military=mil(forces(4))), QUIET),
                          (status(4, military=mil(forces(4))), QUIET)], first_status=status(1, military=mil(forces(4))))
        r = g.finish_turn(skip_quiet_turns=2)
        self.assertEqual((r["turn"], r["turns_skipped"]), (4, 2))

    def test_no_turn_passes_while_an_enemy_army_is_in_sight_near_a_city(self):
        war = mil(forces(5, at_war=True), cities=[city(200, hostile_close={"units": 2, "types": {"SWORDSMAN": 2}})])
        g = ScriptedGame([(status(2, military=war), QUIET), (status(3, military=war), QUIET)],
                         first_status=status(1, military=war))
        r = g.finish_turn(skip_quiet_turns=9)
        self.assertEqual((r["turn"], r["turns_skipped"]), (2, 0))
        self.assertEqual(r["woke_because"], ["enemy_forces_near:The Zulus:5"])


class BriefingWarningTests(unittest.TestCase):
    def rows(self, m, kind):
        return [w for w in briefing_warnings({"turn": 80, "military": m}) if w["kind"] == kind]

    def test_the_lowest_soldiers_figure_is_a_warning_with_the_figures(self):
        (w,) = self.rows(mil(), "military_standing")
        self.assertEqual((w["mine"], w["rank"], w["of"], w["best"], w["combat_units"]), (4000, 6, 6, 24000, 3))
        self.assertIn("yours 4000, rank 6 of 6; the highest is The Zulus's 24000, 6.0 times yours", w["note"])
        self.assertIn("You have 3 combat unit(s)", w["note"])

    def test_a_middling_figure_is_no_warning_and_one_far_behind_the_highest_is(self):
        self.assertEqual(self.rows(mil(rank=3, mine=20000), "military_standing"), [])
        self.assertEqual(self.rows(mil(rank=1, mine=24000, best_civ="you"), "military_standing"), [])
        (w,) = self.rows(mil(rank=3, mine=12000, best_civ=None), "military_standing")
        self.assertIn("an unmet civilization's 24000, 2.0 times yours", w["note"])

    def test_an_army_near_my_cities_is_a_warning_at_peace_and_at_war(self):
        (w,) = self.rows(mil(forces(4, approach_guess="MAJOR_CIV_APPROACH_GUARDED")), "foreign_forces_near")
        self.assertIn("4 combat unit(s) of The Zulus in sight within 5 plots of your cities (4 SWORDSMAN), at peace with you", w["note"])
        self.assertIn("MAJOR_CIV_APPROACH_GUARDED", w["note"])
        self.assertIn("the nearest is 3 plot(s) from Venice", w["note"])
        (w,) = self.rows(mil(forces(4, at_war=True)), "enemy_forces_near")
        self.assertIn("at war with you", w["note"])
        self.assertEqual(self.rows(mil({"civ": "Barbarians", "at_war": True, "units": 2}), "enemy_forces_near"), [])

    def test_a_city_under_threat_says_what_holds_it_and_what_can_be_bought(self):
        buy = {"gold": 300, "units": [{"item": "UNIT_ARCHER", "gold": 180, "strength": 5, "ranged": 7}],
               "buildings": [{"item": "BUILDING_WALLS", "gold": 280}]}
        (w,) = self.rows(mil(cities=[city(140, hostile_close={"units": 3, "types": {"IMPI": 2, "SWORDSMAN": 1}}, can_buy=buy)]),
                         "city_threatened")
        self.assertIn("Venice: 140 of 200 hit points, strength 15, no unit garrisoned", w["note"])
        self.assertIn("3 hostile unit(s) within 3 plots (2 IMPI, 1 SWORDSMAN)", w["note"])
        self.assertIn("the treasury (300 gold) buys here now: UNIT_ARCHER 180; BUILDING_WALLS 280", w["note"])
        short = {"gold": 90, "units": [], "cheapest_unit": {"item": "UNIT_WARRIOR", "gold": 110}}
        (w,) = self.rows(mil(cities=[city(140, garrison="WARRIOR", can_buy=short)]), "city_threatened")
        self.assertIn("garrison WARRIOR", w["note"])
        self.assertIn("buys no combat unit here: the cheapest is UNIT_WARRIOR at 110", w["note"])

    def test_wary_leaders_are_one_row_and_friendly_ones_none(self):
        (w,) = self.rows(mil(rank=3, mine=20000, approach={"The Zulus": "HOSTILE", "Germany": "FRIENDLY", "Korea": "GUARDED"}),
                         "wary_leaders")
        self.assertEqual(w["approach"], {"The Zulus": "HOSTILE", "Korea": "GUARDED"})
        self.assertIn("Korea GUARDED, The Zulus HOSTILE", w["note"])
        self.assertEqual(self.rows(mil(approach={"Germany": "FRIENDLY"}), "wary_leaders"), [])

    def test_an_enemy_city_in_reach_is_a_row_with_what_stands_around_it(self):
        siege = {"city": "Attila's Court", "id": 1, "civ": "The Huns", "player_id": 1, "x": 30, "y": 12, "capital": True,
                 "hp": 150, "max_hp": 200, "strength": 18, "my_units_close": {"units": 3, "types": {"LEGION": 2, "BALLISTA": 1}},
                 "enemy_units_close": {"units": 0, "types": {}}}
        (w,) = self.rows(mil(sieges=[siege]), "enemy_city_in_reach")
        self.assertIn("Attila's Court of The Huns (its capital) at (30,12): 150 of 200 hit points, strength 18", w["note"])
        self.assertIn("you have 3 combat unit(s) (2 LEGION, 1 BALLISTA) and 0 of its owner's are in sight", w["note"])

    def test_a_status_without_the_block_warns_of_nothing(self):
        self.assertEqual(briefing_warnings({"turn": 80}), [])


class VictoriesAllowedTests(unittest.TestCase):
    TS = {"turn": 0, "todo": {"units": [], "cities": []}, "blocking_name": "NO_ENDTURN_BLOCKING_TYPE", "pending_popups": []}

    def briefing(self, board, include_rules=True):
        out, _snap = build(self.TS, {}, [], [], {"event_seq": 1, "threats": [], "camps": [], **board},
                           {"comparable": False}, None, [], limit=8, include_rules=include_rules)
        return out

    def test_the_briefing_that_carries_the_rules_names_the_victories_the_game_allows(self):
        self.assertEqual(self.briefing({"victories": ["DOMINATION"]})["victories_allowed"], ["DOMINATION"])

    def test_a_later_briefing_and_an_older_runtime_carry_none(self):
        self.assertNotIn("victories_allowed", self.briefing({"victories": ["DOMINATION"]}, include_rules=False))
        self.assertNotIn("victories_allowed", self.briefing({}))


class VictoriesAllowedLuaTests(unittest.TestCase):
    run_lua = support.LuaRuntimeTests.run_lua

    def setUp(self):
        support.LuaRuntimeTests.setUp(self)

    def test_the_board_lists_the_victories_the_game_says_are_valid(self):
        self.run_lua("""
        local rows = { { ID = 0, Type = 'VICTORY_TIME' }, { ID = 1, Type = 'VICTORY_DOMINATION' }, { ID = 2, Type = 'VICTORY_CULTURAL' } }
        GameInfo = { Victories = function() local i = 0; return function() i = i + 1; return rows[i] end end }
        Game.IsVictoryValid = function(id) return id == 1 end
        Players = { [0] = { GetTeam = function() return 0 end,
                            Cities = function() return function() return nil end end,
                            Units = function() return function() return nil end end } }
        Teams = { [0] = {} }
        Map = {}
        local b = H.briefing_board(0, nil)
        assert(#b.victories == 1 and b.victories[1] == 'DOMINATION', H.json(b))
        """)


if __name__ == "__main__":
    unittest.main()
