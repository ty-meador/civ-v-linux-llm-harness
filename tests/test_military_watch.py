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
from harness.briefing import build, decisions
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
        assert(m.soldiers.lowest == 4000, H.json(m))
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
        assert(g[1].strike_range == 2 and g[1].my_units_in_strike_range.units == 2, 'the Warrior and the Archer two plots off: ' .. H.json(g))
        GameDefines.CITY_ATTACK_RANGE = 1
        assert(watch().sieges[1].strike_range == 1 and watch().sieges[1].my_units_in_strike_range.units == 0, H.json(watch().sieges))
        GameDefines.CITY_ATTACK_RANGE = nil
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

    def test_a_unit_on_the_citys_tile_blocks_the_purchase_and_the_row_says_so(self):
        self.run_lua("""
        WAR[1] = true
        zulus(1, 11, 11)
        local sells = VENICE.IsCanPurchase
        VENICE.IsCanPurchase = function(c, test_gold, x, uid, bid) if test_gold and uid >= 0 then return false end return sells(c, test_gold, x, uid, bid) end
        local buy = watch().cities[1].can_buy
        assert(#buy.units == 0 and #buy.blocked == 2 and buy.blocked[1].item == 'UNIT_WARRIOR', H.json(buy))
        assert(buy.blocked_note:find('a tile holds one', 1, true) and buy.cheapest_unit == nil, H.json(buy))
        assert(#buy.buildings == 1, 'a building is still for sale: ' .. H.json(buy))
        """)

    def test_no_culture_victory_no_culture_threat(self):
        self.run_lua("""
        local rows = { VICTORY_CULTURAL = { ID = 2 } }
        GameInfo.Victories = rows
        H.culture_overview = function() return { civs = { { civ = 'The Huns', needed = 1, influential_on = 0, on = {} } } } end
        Game.IsVictoryValid = function(id) return true end
        assert(#H.culture_threats(0) == 1, H.json(H.culture_threats(0)))
        Game.IsVictoryValid = function(id) return id ~= 2 end
        assert(#H.culture_threats(0) == 0, H.json(H.culture_threats(0)))
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

    def test_the_upgrades_the_unit_panel_offers_and_the_ones_it_greys(self):
        self.run_lua("""
        local function upgradable(id, kind, to, price, can, x, y)
          local u = unit(kind, x, y)
          u.GetID = function() return id end; u.GetOwner = function() return 0 end
          u.GetUpgradeUnitType = function() return to end
          u.UpgradePrice = function() return price end
          u.CanUpgradeRightNow = function() return can end
          return u
        end
        TRAINABLE = { [3] = true }
        Players[0].CanTrain = function(_, ut) return TRAINABLE[ut] or false end
        OWNER['10,10'] = 0; OWNER['11,10'] = 0
        Players[0].units = { upgradable(7, 1, 3, 120, true, 10, 10), upgradable(8, 1, 3, 400, false, 11, 10),
                             upgradable(9, 2, 5, 90, true, 12, 10), unit(4, 10, 11) }
        local up = watch().upgrades
        assert(up.gold == 300 and #up.ready == 1 and up.ready_total == 1, H.json(up))
        assert(up.ready[1].id == 7 and up.ready[1].unit == 'WARRIOR' and up.ready[1].to == 'SWORDSMAN' and up.ready[1].gold == 120, H.json(up))
        assert(#up.waiting == 1 and up.waiting[1].id == 8 and up.waiting[1].why[1] == 'gold', H.json(up))
        TRAINABLE = {}
        assert(watch().upgrades == nil, 'no button while the target cannot be trained: ' .. H.json(watch()))
        """)

    def test_the_military_advisors_first_line_and_the_whole_counsel(self):
        self.run_lua("""
        AdvisorTypes = { ADVISOR_MILITARY = 0, ADVISOR_ECONOMIC = 1, ADVISOR_FOREIGN = 2, ADVISOR_SCIENCE = 3 }
        Game.GetAdvisorCounsel = function()
          return { [0] = { 'The Zulu Kingdom wields an army that could wipe us off the planet.', 'We are nearly defenseless!' },
                   [1] = { 'Unit maintenance costs us 9 [ICON_GOLD] a turn.' }, [2] = {}, [3] = {} }
        end
        local said = watch().advisor
        assert(#said == 2 and said[1] == 'The Zulu Kingdom wields an army that could wipe us off the planet.'
               and said[2] == 'We are nearly defenseless!', H.json(watch()))
        local c = H.advisor_counsel(0)
        assert(#c.military == 2 and c.foreign == nil and c.science == nil, H.json(c))
        assert(c.economic[1] == 'Unit maintenance costs us 9 Gold a turn.' or c.economic[1]:find('9', 1, true), H.json(c))
        assert(H.advisor_counsel(1) == nil, 'the game keeps the counsel of the player on screen only')
        Game.GetAdvisorCounsel = nil
        assert(watch().advisor == nil and H.advisor_counsel(0) == nil)
        """)

    def test_units_with_something_to_attack_are_listed_whatever_they_are_doing(self):
        self.run_lua("""
        local function fighter(id, kind, x, y, moves)
          local u = unit(kind, x, y)
          u.GetID = function() return id end; u.MovesLeft = function() return moves end
          u.GetCurrHitPoints = function() return 80 end
          return u
        end
        Players[0].units = { fighter(7, 1, 10, 10, 60), fighter(8, 2, 10, 10, 60), fighter(9, 2, 11, 10, 0), fighter(10, 1, 20, 20, 60) }
        H.ranged_targets = function(u)
          return { { x = 12, y = 10, unit = 'ZULU_IMPI', hp = 76, preview = { expected_damage_dealt = 31, expected_damage_taken = 0 } },
                   { x = 12, y = 11, unit = 'SWORDSMAN', hp = 100, preview = { expected_damage_dealt = 24, expected_damage_taken = 0 } } }
        end
        H.melee_targets = function(u)
          if u:GetID() ~= 7 then return {} end
          return { { x = 11, y = 11, city = 'Ulundi', hp = 150, preview = { expected_damage_dealt = 12, expected_damage_taken = 40 } } }
        end
        local rows, more = H.unit_attacks(0)
        assert(#rows == 2 and more == 0, 'no moves, no attack; nothing beside it, no attack: ' .. H.json(rows))
        assert(rows[1].id == 8 and rows[1].unit == 'ARCHER' and rows[1].ranged == true and rows[1].targets == 2, H.json(rows))
        assert(rows[1].most_damage_on.unit == 'ZULU_IMPI' and rows[1].most_damage_on.deals == 31 and rows[1].most_damage_on.x == 12, H.json(rows))
        assert(rows[2].id == 7 and rows[2].ranged == false and rows[2].most_damage_on.city == 'Ulundi' and rows[2].most_damage_on.takes == 40, H.json(rows))
        H.MILITARY_ATTACKS_SHOWN = 1
        rows, more = H.unit_attacks(0)
        assert(#rows == 1 and more == 1, H.json(rows))
        """)

    def test_a_siege_unit_that_has_not_set_up_is_listed_with_what_is_in_its_range(self):
        self.run_lua("""
        UNITS[6] = { ID = 6, Type = 'UNIT_CANNON', Combat = 14, RangedCombat = 20, Range = 2 }
        local cannon = unit(6, 10, 10)
        cannon.GetID = function() return 9 end; cannon.MovesLeft = function() return 60 end
        cannon.GetCurrHitPoints = function() return 100 end
        SET_UP = false
        cannon.IsMustSetUpToRangedAttack = function() return true end
        cannon.IsSetUpForRangedAttack = function() return SET_UP end
        Players[0].units = { cannon }
        H.ranged_targets = function() return SET_UP and { { x = 12, y = 10, unit = 'PIKEMAN', hp = 100, preview = { expected_damage_dealt = 40, expected_damage_taken = 0 } } } or {} end
        Map.PlotXYWithRangeCheck = function(x, y, dx, dy, range)
          return { GetX = function() return x + dx end, GetY = function() return y + dy end }
        end
        H.ranged_target_info = function(u, q) if q:GetX() == 12 and q:GetY() == 10 then return { unit = 'PIKEMAN' } end return {} end
        local rows = H.unit_attacks(0)
        assert(#rows == 1 and rows[1].id == 9 and rows[1].needs_set_up == true and rows[1].in_range == 1 and rows[1].targets == nil, H.json(rows))
        SET_UP = true
        rows = H.unit_attacks(0)
        assert(#rows == 1 and rows[1].needs_set_up == nil and rows[1].targets == 1 and rows[1].most_damage_on.deals == 40, H.json(rows))
        SET_UP = false
        H.ranged_target_info = function() return {} end
        assert(#H.unit_attacks(0) == 0, 'nothing in range, nothing listed')
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

    def test_the_lowest_of_two_armies_of_a_size_does_not_wake(self):
        def rec(turn, rank, mine):
            return military.record({"turn": turn, "military": mil(rank=rank, of=2, mine=mine, best=5000)})
        self.assertEqual(military.wake_reasons(rec(11, 2, 4000), rec(10, 1, 5000)), [], "5000 is not half again 4000")
        self.assertEqual(military.wake_reasons(rec(12, 2, 3000), rec(11, 2, 4000)), ["soldiers_rank_lowest"])


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


ATTACK = {"id": 8, "unit": "CROSSBOWMAN", "x": 57, "y": 33, "hp": 100, "ranged": True, "targets": 3,
          "most_damage_on": {"x": 56, "y": 31, "unit": "ZULU_IMPI", "hp": 76, "deals": 31, "takes": 0}}


class UnitAttackTests(unittest.TestCase):
    def test_a_unit_that_can_attack_is_no_quiet_turn_and_its_hint_alone_is(self):
        todo = {"units": [], "cities": [], "promotions": [], "research_unset": False, "unit_attacks": [ATTACK],
                "unit_attacks_hint": "state(what='unit', id, view='tactical') ..."}
        g = ScriptedGame([(status(2, todo=todo), QUIET), (status(3), QUIET)])
        r = g.finish_turn(skip_quiet_turns=9)
        self.assertEqual((r["turn"], r["turns_skipped"], r["woke_because"]), (2, 0, ["todo.unit_attacks"]))

    def test_the_briefing_lists_it_as_a_decision_with_the_shot(self):
        melee = {"id": 7, "unit": "SWORDSMAN", "ranged": False, "targets": 1, "most_damage_on": {"x": 58, "y": 32, "unit": "ZULU_IMPI"}}
        ts = {"turn": 141, "todo": {"units": [], "cities": [], "unit_attacks": [ATTACK, melee], "unit_attacks_hint": "h"},
              "blocking_name": "NO_ENDTURN_BLOCKING_TYPE", "pending_popups": []}
        rows = [d for d in decisions(ts, []) if d["kind"] == "unit_attack"]
        self.assertEqual([d["id"] for d in rows], [8, 7])
        self.assertEqual(rows[0]["actions"][1], {"tool": "order", "args": {"to": "unit", "action": "mission", "id": 8,
                         "args": {"mission": "MISSION_RANGE_ATTACK", "x": 56, "y": 31}}})
        self.assertEqual(rows[1]["actions"][1], {"tool": "order", "args": {"to": "unit", "action": "move", "id": 7,
                         "args": {"x": 58, "y": 32}}})
        ts["todo"]["unit_attacks"] = [{"id": 9, "unit": "CANNON", "ranged": True, "needs_set_up": True, "in_range": 2}]
        (row,) = [d for d in decisions(ts, []) if d["kind"] == "unit_attack"]
        self.assertEqual(row["actions"][0], {"tool": "order", "args": {"to": "unit", "action": "mission", "id": 9,
                         "args": {"mission": "MISSION_SET_UP_FOR_RANGED_ATTACK"}}})
        self.assertEqual((row["needs_set_up"], row["in_range"]), (True, 2))
        self.assertEqual([d["kind"] for d in decisions(ts, []) if d["kind"].startswith("unit_attacks")], [],
                         "the hint and the list are not decisions of their own")


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

    def test_the_lower_of_two_armies_of_a_size_is_no_warning(self):
        self.assertEqual(self.rows(mil(rank=2, of=2, mine=17436, best=17889, best_civ=None), "military_standing"), [])
        self.assertEqual(len(self.rows(mil(rank=2, of=2, mine=10000, best=15000), "military_standing")), 1)

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
        blocked = {"gold": 172, "units": [], "blocked": [{"item": "UNIT_SCOUT", "gold": 100, "strength": 5}]}
        (w,) = self.rows(mil(cities=[city(200, garrison="WARRIOR", can_buy=blocked)]), "city_threatened")
        self.assertIn("buys here now: no combat unit while one stands on the city's tile", w["note"])
        self.assertIn("the gold covers UNIT_SCOUT 100", w["note"])
        short = {"gold": 90, "units": [], "cheapest_unit": {"item": "UNIT_WARRIOR", "gold": 110}}
        (w,) = self.rows(mil(cities=[city(140, garrison="WARRIOR", can_buy=short)]), "city_threatened")
        self.assertIn("garrison WARRIOR", w["note"])
        self.assertIn("buys no combat unit here: the cheapest is UNIT_WARRIOR at 110", w["note"])

    def test_an_upgrade_the_panel_offers_now_is_a_row(self):
        m = mil(rank=3, mine=20000)
        m["upgrades"] = {"gold": 300, "ready": [{"id": 7, "unit": "WARRIOR", "to": "SWORDSMAN", "gold": 120}], "ready_total": 1,
                         "waiting": [{"id": 8, "unit": "WARRIOR", "to": "SWORDSMAN", "gold": 400, "why": ["gold"]}]}
        (w,) = self.rows(m, "upgrades_ready")
        self.assertIn("offers an upgrade now for 1 combat unit(s), treasury 300 gold: WARRIOR 7 to SWORDSMAN for 120", w["note"])
        del m["upgrades"]["ready"]
        self.assertEqual(self.rows(m, "upgrades_ready"), [])

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
        siege.update(strike_range=2, my_units_in_strike_range={"units": 1, "types": {"BALLISTA": 1}})
        (w,) = self.rows(mil(sieges=[siege]), "enemy_city_in_reach")
        self.assertIn("strength 18, it strikes 2 plots and 1 of your units stand inside that (1 BALLISTA); within 3 plots", w["note"])

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

    def test_a_game_only_domination_wins_says_so_with_the_capitals(self):
        capitals = [{"original_player": 0, "civ": "Rome", "city": "Rome", "owner": 0, "owner_civ": "Rome", "controlled_by_us": True,
                     "revealed": True, "x": 26, "y": 7, "lost_capital": False},
                    {"original_player": 1, "civ": "The Huns", "city": "Attila's Court", "owner": 1, "owner_civ": "The Huns",
                     "controlled_by_us": False, "revealed": True, "x": 30, "y": 19, "distance_from_my_capital": 12, "lost_capital": False}]
        out = self.briefing({"victories": ["DOMINATION"], "domination": capitals})
        self.assertEqual(out["only_victory"]["victory"], "DOMINATION")
        self.assertIn("Domination is the only victory this game can be won by", out["only_victory"]["note"])
        self.assertIn("Rome (yours, held by you); Attila's Court (The Huns's, held by The Huns) at (30,19), 12 plots from your capital",
                      out["only_victory"]["note"])
        hidden = [dict(capitals[1], revealed=False)]
        del hidden[0]["x"], hidden[0]["y"], hidden[0]["distance_from_my_capital"]
        self.assertIn("its plot not revealed to you", self.briefing({"victories": ["DOMINATION"], "domination": hidden})["only_victory"]["note"])
        self.assertNotIn("only_victory", self.briefing({"victories": ["DOMINATION", "CULTURAL"], "domination": capitals}))

    def test_the_briefing_carries_what_the_games_advisors_say(self):
        out = self.briefing({"counsel": {"military": ["We are nearly defenseless! We need to train more units!"], "foreign": []}},
                            include_rules=False)
        self.assertEqual(out["advisors"]["military"], ["We are nearly defenseless! We need to train more units!"])
        self.assertNotIn("foreign", out["advisors"])
        self.assertIn("the game's own", out["advisors"]["note"])
        self.assertNotIn("advisors", self.briefing({}))

    def test_a_later_briefing_and_an_older_runtime_carry_none(self):
        self.assertNotIn("victories_allowed", self.briefing({"victories": ["DOMINATION"]}, include_rules=False))
        self.assertNotIn("victories_allowed", self.briefing({}))


class SoldiersChangeTests(unittest.TestCase):
    TS = {"turn": 240, "todo": {"units": [], "cities": []}, "blocking_name": "NO_ENDTURN_BLOCKING_TYPE", "pending_popups": []}

    def briefing(self, soldiers, prev=None):
        ts = {**self.TS, "military": {"soldiers": soldiers}}
        return build(ts, {}, [], [], {"event_seq": 1, "threats": [], "camps": []},
                     {"comparable": prev is not None}, prev, [], limit=8, include_rules=False)

    def test_the_next_briefing_says_how_the_soldiers_figures_moved(self):
        _out, snap = self.briefing({"mine": 163377, "rank": 1, "of": 2, "best": 163377, "average": 157000, "lowest": 151486})
        self.assertEqual(snap["soldiers"], {"mine": 163377, "best": 163377, "lowest": 151486})
        out, _snap = self.briefing({"mine": 182746, "rank": 2, "of": 2, "best": 243253, "average": 213000, "lowest": 182746}, prev=snap)
        self.assertEqual(out["changes"]["soldiers"], {"mine": {"was": 163377, "now": 182746},
                                                      "highest": {"was": 163377, "now": 243253},
                                                      "lowest": {"was": 151486, "now": 182746}})

    def test_figures_that_did_not_move_and_a_baseline_without_them_say_nothing(self):
        row = {"mine": 4000, "rank": 6, "of": 6, "best": 24000, "average": 15000, "lowest": 4000}
        _out, snap = self.briefing(row)
        out, _snap = self.briefing(row, prev=snap)
        self.assertNotIn("soldiers", out.get("changes", {}))
        out, _snap = self.briefing(row, prev={"turn": 230, "empire": {}, "cities": {}, "units": {}})
        self.assertNotIn("soldiers", out.get("changes", {}))


class CapitalToTakeTests(unittest.TestCase):
    ONLY = {"victory": "DOMINATION", "wins": "the last player holding their own original capital",
            "capitals": [{"city": "Attila's Court", "civ": "The Huns", "held_by": "The Huns", "player_id": 1, "x": 13, "y": 11,
                          "distance_from_my_capital": 15}]}

    def rows(self, **ts):
        from harness.briefing import opportunities
        return [r for r in opportunities({}, {"turn": 180, **ts}) if r["kind"] == "capital_to_take"]

    def test_the_capital_that_wins_the_game_is_an_opportunity_with_where_it_is_and_both_armies(self):
        m = {"soldiers": {"mine": 105071, "rank": 1, "of": 2, "best": 105071, "best_civ": "you", "average": 90000, "lowest": 74929}}
        (r,) = self.rows(only_victory=self.ONLY, military=m)
        self.assertEqual((r["city"], r["x"], r["y"], r["at_war"]), ("Attila's Court", 13, 11, False))
        self.assertIn("Domination, the only victory of this game, goes to the last player holding their own original capital", r["detail"])
        self.assertIn("Attila's Court (The Huns's, held by The Huns) stands at (13,11), 15 plots from your capital; you are at peace with The Huns", r["detail"])
        self.assertIn("Soldiers on the Demographics screen: yours 105071, theirs 74929", r["detail"])
        self.assertEqual(r["actions"], [{"tool": "state", "args": {"what": "map", "view": "window", "x": 13, "y": 11}},
                                        {"tool": "state", "args": {"what": "civ", "id": 1, "view": "war"}}])

    def test_at_war_it_says_so_and_the_weaker_side_reads_the_highest_figure(self):
        m = {"soldiers": {"mine": 25377, "rank": 2, "of": 2, "best": 73946, "average": 49662, "lowest": 25377}}
        wars = {"majors": [{"player_id": 1, "civ": "The Huns"}], "minors": []}
        (r,) = self.rows(only_victory=self.ONLY, military=m, wars=wars)
        self.assertTrue(r["at_war"])
        self.assertIn("you are at war with The Huns. Soldiers on the Demographics screen: yours 25377, theirs 73946", r["detail"])
        self.assertEqual(len(r["actions"]), 1, "no declare-war read for a war already on")

    def test_a_capital_in_sight_says_what_its_banner_shows(self):
        seen = {**self.ONLY, "capitals": [{**self.ONLY["capitals"][0], "in_sight": True, "hp": 300, "max_hp": 300, "strength": 61,
                                           "units_in_sight_within_2": 2}]}
        (r,) = self.rows(only_victory=seen)
        self.assertIn("in your sight now: 300 of 300 hit points, strength 61, 2 of its owner's combat unit(s) within 2 plots; you are at peace",
                      r["detail"])

    def test_no_row_without_the_one_victory_for_a_capital_i_hold_or_one_i_have_not_found(self):
        self.assertEqual(self.rows(), [])
        held = {**self.ONLY, "capitals": [{"city": "Attila's Court", "civ": "The Huns", "held_by": "you"}]}
        self.assertEqual(self.rows(only_victory=held), [])
        unknown = {**self.ONLY, "capitals": [{"city": "Attila's Court", "civ": "The Huns", "held_by": "The Huns", "player_id": 1}]}
        self.assertEqual(self.rows(only_victory=unknown), [])

    def test_three_civilizations_give_no_figure_for_the_other(self):
        m = {"soldiers": {"mine": 100, "rank": 1, "of": 3, "best": 100, "average": 80, "lowest": 60}}
        (r,) = self.rows(only_victory=self.ONLY, military=m)
        self.assertNotIn("Soldiers", r["detail"])


class VictoriesAllowedLuaTests(unittest.TestCase):
    run_lua = support.LuaRuntimeTests.run_lua

    def setUp(self):
        support.LuaRuntimeTests.setUp(self)

    def test_the_status_names_the_capitals_not_in_my_hands_when_only_domination_wins(self):
        self.run_lua("""
        local rows = { { ID = 0, Type = 'VICTORY_TIME' }, { ID = 1, Type = 'VICTORY_DOMINATION' }, { ID = 2, Type = 'VICTORY_CULTURAL' } }
        GameInfo = { Victories = function() local i = 0; return function() i = i + 1; return rows[i] end end }
        VALID = { [1] = true }
        Game.IsVictoryValid = function(id) return VALID[id] or false end
        Map = { PlotDistance = function(x1, y1, x2, y2) return math.max(math.abs(x1 - x2), math.abs(y1 - y2)) end }
        Players = { [0] = { GetCapitalCity = function() return { GetX = function() return 26 end, GetY = function() return 7 end } end,
                            IsHasLostCapital = function() return false end } }
        H.domination_progress = function()
          return { capitals = { { original_player = 0, civ = 'Rome', city = 'Rome', owner_civ = 'Rome', controlled_by_us = true, x = 26, y = 7 },
                                { original_player = 1, civ = 'The Huns', city = "Attila's Court", owner_civ = 'The Huns',
                                  controlled_by_us = false, x = 13, y = 11 } } }
        end
        local o = H.only_victory(0)
        assert(o.victory == 'DOMINATION' and #o.capitals == 1 and o.wins:find('original capital', 1, true), H.json(o))
        assert(o.capitals[1].in_sight == nil and o.capitals[1].hp == nil, 'a capital I do not see has no banner: ' .. H.json(o))
        SEEN = false
        local huns = { Units = function() local k = 0; local us = { { IsCombatUnit = function() return true end, IsDelayedDeath = function() return false end,
                                                                     IsInvisible = function() return false end, GetX = function() return 14 end, GetY = function() return 11 end,
                                                                     GetPlot = function() return { IsVisible = function() return true end } end } }
                                 return function() k = k + 1; return us[k] end end }
        Players[0].GetTeam = function() return 0 end
        Players[1] = huns
        Map.GetPlot = function(x, y)
          return { IsVisible = function() return SEEN end,
                   GetPlotCity = function() return { GetMaxHitPoints = function() return 300 end, GetDamage = function() return 40 end,
                                                     GetStrengthValue = function() return 6149 end, GetOwner = function() return 1 end } end }
        end
        SEEN = true
        local c2 = H.only_victory(0).capitals[1]
        assert(c2.in_sight == true and c2.hp == 260 and c2.max_hp == 300 and c2.strength == 61 and c2.units_in_sight_within_2 == 1, H.json(c2))
        SEEN = false
        local c = o.capitals[1]
        assert(c.city == "Attila's Court" and c.civ == 'The Huns' and c.held_by == 'The Huns' and c.x == 13 and c.y == 11
               and c.distance_from_my_capital == 13, H.json(o))
        VALID[2] = true
        assert(H.only_victory(0) == nil, 'two victories: nothing is the only one')
        VALID = { [2] = true }
        assert(H.only_victory(0) == nil, 'only Culture: no capitals to list')
        """)

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
