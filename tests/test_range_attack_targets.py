"""state(what='unit', view='targets') for a unit that shoots, and whether a siege unit is set up (runtime v347).

Live 2026-11-23 (Opus 5.5, the duel against the Huns): `view='targets'` with MISSION_RANGE_ATTACK read "mission is not
offered for this unit" for a Cannon before its set-up and after it, the same view without a mission read "needs
mission" with a list that held no attack, a set-up was spent on a shot the hills blocked, and nothing said a unit was
set up. The view now answers for MISSION_RANGE_ATTACK (the default for a unit that shoots): the visible enemies within
range from the plot the unit stands on with the combat panel's preview, the ones out of the line of fire apart, and
whether it fires now.

The map is the tactical view's mocked 8 x 5 wrapped one (tests/test_tactical_view.py WORLD), unit at (2,2).
"""
import unittest

import test_mcp_safety as support
from test_tactical_view import WORLD

HELPERS = r"""
TARGETS, HIDDEN = {}, {}
GameInfo.InterfaceModes = {}
function no_air(u)                                 -- what H.targeted_missions asks of every unit
  u.CanAirAttack = function() return false end; u.GetDropRange = function() return 0 end
  u.CanAirlift = function() return false end; u.CanNuke = function() return false end
  return u
end
H.ranged_target_info = function(u, q, pid) return TARGETS[q:GetX() .. ',' .. q:GetY()] or {} end
function shooter(o)
  o = o or {}
  local u = no_air(unit(1, 0, 3, 2, 2, { moves = o.moves or 2 }))
  u.Range = function() return o.range or 2 end
  u.GetBaseRangedCombatStrength = function() return 7 end
  u.IsMustSetUpToRangedAttack = function() return o.siege == true end
  u.IsSetUpForRangedAttack = function() return o.set_up == true end
  u.IsOutOfAttacks = function() return o.attacked == true end
  P['2,2'].CanSeePlot = function(_, q) return not HIDDEN[q:GetX() .. ',' .. q:GetY()] end
  return u
end
function targets(mission) return H.unit_mission_targets(1, mission, 0, 0, 100) end
"""


class RangeAttackTargetTests(unittest.TestCase):
    run_lua = support.LuaRuntimeTests.run_lua

    def setUp(self):
        support.LuaRuntimeTests.setUp(self)
        self.run_lua(WORLD)
        self.run_lua(HELPERS)

    def test_the_enemies_in_range_nearest_first_with_the_preview_and_the_hidden_ones_apart(self):
        self.run_lua("""
        shooter()
        TARGETS['4,2'] = { city = "Attila's Court", owner = 3, hp = 102, preview = { damage = 31 } }
        TARGETS['3,2'] = { id = 7, unit = 'PIKEMAN', hp = 100, preview = { damage = 22 } }
        TARGETS['0,2'] = { id = 8, unit = 'CANNON', hp = 59, preview = { damage = 30 } }
        TARGETS['5,2'] = { id = 9, unit = 'KNIGHT', hp = 100, preview = {} }      -- three plots: out of range
        HIDDEN['0,2'] = true                                                       -- hills in between
        local r = targets('MISSION_RANGE_ATTACK')
        assert(r.ok and r.mission == 'MISSION_RANGE_ATTACK' and r.unit_id == 1 and r.range == 2, H.json(r))
        assert(r.total == 2 and #r.targets == 2, H.json(r.targets))
        assert(r.targets[1].unit == 'PIKEMAN' and r.targets[1].distance == 1 and r.targets[1].x == 3, H.json(r.targets[1]))
        assert(r.targets[2].city == "Attila's Court" and r.targets[2].distance == 2 and r.targets[2].preview.damage == 31)
        assert(#r.out_of_line_of_fire == 1 and r.out_of_line_of_fire[1].unit == 'CANNON', H.json(r.out_of_line_of_fire))
        assert(r.out_of_line_of_fire[1].line_of_fire == false and r.out_of_line_of_fire[1].preview == nil)
        assert(r.line_of_fire_note:find('block the shot', 1, true))
        assert(r.fires_now == true and r.why_not_now == nil and r.set_up == nil, 'an Archer needs no set-up: ' .. H.json(r))
        """)

    def test_no_mission_named_is_the_ranged_attack_for_a_unit_that_shoots(self):
        self.run_lua("""
        shooter()
        TARGETS['3,2'] = { id = 7, unit = 'PIKEMAN', hp = 100 }
        local r = targets('')
        assert(r.ok and r.mission == 'MISSION_RANGE_ATTACK' and r.total == 1, H.json(r))
        r = targets(nil)
        assert(r.ok and r.mission == 'MISSION_RANGE_ATTACK', H.json(r))
        """)

    def test_a_siege_unit_is_shown_its_targets_before_the_set_up_and_told_what_the_set_up_costs(self):
        self.run_lua("""
        shooter({ siege = true, range = 2 })
        TARGETS['4,2'] = { city = "Attila's Court", owner = 3, hp = 102 }
        local r = targets('MISSION_RANGE_ATTACK')
        assert(r.ok and r.total == 1 and r.set_up == false and r.fires_now == false, H.json(r))
        assert(r.why_not_now:find('not set up', 1, true) and r.why_not_now:find('sets up and fires this turn', 1, true), r.why_not_now)
        """)
        self.run_lua("""
        P['2,2'].o.units = {}
        shooter({ siege = true, moves = 1 })
        local r = targets('MISSION_RANGE_ATTACK')
        assert(r.fires_now == false and r.why_not_now:find('sets up now and fires next turn', 1, true), r.why_not_now)
        P['2,2'].o.units = {}
        shooter({ siege = true, set_up = true })
        r = targets('MISSION_RANGE_ATTACK')
        assert(r.set_up == true and r.fires_now == true and r.why_not_now == nil, H.json(r))
        P['2,2'].o.units = {}
        shooter({ siege = true, set_up = true, attacked = true })
        r = targets('MISSION_RANGE_ATTACK')
        assert(r.fires_now == false and r.why_not_now == 'the unit has already attacked this turn', H.json(r))
        P['2,2'].o.units = {}
        shooter({ moves = 0 })
        r = targets('MISSION_RANGE_ATTACK')
        assert(r.fires_now == false and r.why_not_now:find('no moves left', 1, true), H.json(r))
        """)

    def test_a_unit_without_a_ranged_attack_is_sent_to_the_tactical_view(self):
        self.run_lua("""
        no_air(unit(1, 0, 1, 2, 2))                      -- a Warrior
        for _, m in ipairs({ 'MISSION_RANGE_ATTACK', '' }) do
          local r = targets(m)
          assert(r.ok == false and r.err:find('no ranged attack', 1, true) and r.err:find("view='tactical'", 1, true), H.json(r))
        end
        """)


if __name__ == "__main__":
    unittest.main()
