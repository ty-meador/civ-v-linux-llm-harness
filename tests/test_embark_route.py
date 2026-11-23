"""A move to land that would put a land unit in the water, and who can strike the plot a move ends on (runtime v347).

Live 2026-11-23 (Opus 5.5, the duel against the Huns, turns 188 to 212): the engine's pathfinder embarked Cannons and
Artillery into a lake and onto the coast beside Galleasses on moves of two and three plots to land, and Artillery that
ended a move inside a city's two plots was lost to it; the move's reply said nothing of either ("would have saved
about 3 artillery"). The engine's path is closed to Lua, so H.move_route walks step_cost.lua's rule turn by turn over
the known map, by land alone and with the water, and H.embark_plan decides before anything is sent:
by land in fewer turns: the move goes out as it always did; the same turns: the unit walks the land route, a leg a
turn; the water faster or the only way: refused with both, unless the order said `land_only` or `confirm`.

The map is the tactical view's mocked 8 x 5 wrapped one (tests/test_tactical_view.py WORLD), unit at (2,2): NE (2,3),
E (3,2), SE (2,1). (4,2) lies behind E; by land it is reached over (2,3) and (3,3), or (2,1) and (3,1).
"""
import unittest

import test_mcp_safety as support
from test_tactical_step_cost import COSTS
from test_tactical_view import WORLD

NET = r"""
SENT = {}
Game.GetActivePlayer = function() return 0 end
Game.GetGameTurn = function() return 7 end
Game.SelectionListGameNetMessage = function(msg, a, b, c) SENT[#SENT + 1] = { msg, a, b, c } end
GameMessageTypes = { GAMEMESSAGE_PUSH_MISSION = 9 }
UI = { GetHeadSelectedUnit = function() return SELECTED end, SelectUnit = function(u) SELECTED = u end }
Teams[0].CanEmbark = function() return true end
H.pending_moves = {}
function lake() plot(3, 2, { water = true }) end
function forest(...) for _, xy in ipairs({ ... }) do plot(xy[1], xy[2], { forest = true }) end end
"""


class RouteTests(unittest.TestCase):
    run_lua = support.LuaRuntimeTests.run_lua

    def setUp(self):
        support.LuaRuntimeTests.setUp(self)
        self.run_lua(WORLD)
        self.run_lua(COSTS)
        self.run_lua(NET)

    def test_dry_ground_has_no_water_route_and_the_move_is_left_alone(self):
        self.run_lua("""
        local u = unit(1, 0, 1, 2, 2)
        local r = H.move_route(u, P['4,2'], 0)
        assert(r.land and r.land.turns == 0 and r.water == nil, H.json({ r.land and r.land.turns, r.water ~= nil }))
        assert(r.land.stop == P['4,2'], 'two open steps: it arrives this turn')
        assert(H.embark_plan(u, P['4,2'], 0, nil, false) == nil)
        """)

    def test_a_unit_that_cannot_embark_is_never_planned(self):
        self.run_lua("""
        Teams[0].CanEmbark = function() return false end
        lake()
        local u = unit(1, 0, 1, 2, 2)
        assert(H.embark_plan(u, P['4,2'], 0, nil, false) == nil)
        """)

    def test_the_same_turns_by_land_and_by_water_walks_the_land_route(self):
        self.run_lua("""
        lake(); forest({ 2, 1 })                         -- SE costs both moves: the way over NE is the better one
        local u = unit(1, 0, 1, 2, 2)
        local r = H.move_route(u, P['4,2'], 0)
        assert(r.land.turns == 1 and r.water.turns == 1, H.json({ r.land.turns, r.water.turns }))
        assert(r.water.embark_at == P['3,2'] and r.water.stop == P['3,2'], 'the lake is where it would spend the night')
        assert(r.land.stop == P['3,3'], 'this turn ends on (3,3): ' .. r.land.stop:GetX() .. ',' .. r.land.stop:GetY())
        local plan = H.embark_plan(u, P['4,2'], 0, nil, false)
        assert(plan and plan.mode == 'land' and plan.stop == P['3,3'] and plan.refuse == nil, 'no refusal at a tie')
        assert(plan.embark_at.x == 3 and plan.embark_at.y == 2)
        """)

    def test_a_plot_that_holds_another_of_my_units_is_passed_through_and_never_a_turns_end(self):
        """Live on the t210 save of the duel: the walk ended a turn on my own Artillery's plot, called that way two
        turns and left the move to the engine, which went another way and stalled."""
        self.run_lua("""
        lake(); forest({ 2, 1 })
        local u = unit(1, 0, 1, 2, 2)
        unit(2, 0, 1, 3, 3)                              -- my other Warrior where the first turn would have ended
        local r = H.move_route(u, P['4,2'], 0)
        assert(r.land.turns == 1 and r.land.stop == P['2,3'], 'this turn ends a plot short, and the next passes through: '
               .. r.land.turns .. ' ' .. r.land.stop:GetX() .. ',' .. r.land.stop:GetY())
        local plan = H.embark_plan(u, P['4,2'], 0, nil, false)
        assert(plan.mode == 'land' and plan.stop == P['2,3'])
        """)

    def test_a_land_route_a_turn_ahead_is_still_walked_and_one_two_turns_ahead_is_left_to_the_engine(self):
        self.run_lua("""
        local u = unit(1, 0, 1, 2, 2)
        H.move_route = function() return { land = { turns = 1, stop = P['2,3'] }, water = { turns = 2, embark_at = P['3,2'] } } end
        local plan = H.embark_plan(u, P['4,2'], 0, nil, false)
        assert(plan and plan.mode == 'land' and plan.stop == P['2,3'], 'the count of turns is the harness own: a turn is its margin')
        H.move_route = function() return { land = { turns = 1, stop = P['2,3'] }, water = { turns = 3, embark_at = P['3,2'] } } end
        assert(H.embark_plan(u, P['4,2'], 0, nil, false) == nil)
        assert(H.embark_plan(u, P['4,2'], 0, 'land', false).mode == 'land', 'land_only walks whatever the water takes')
        assert(H.embark_plan(u, P['4,2'], 0, nil, true).mode == 'land', 'and so does a standing move taken up again')
        """)

    def test_water_that_is_faster_is_refused_with_both_routes_until_the_order_says_which(self):
        self.run_lua("""
        lake(); forest({ 2, 3 }, { 2, 1 }, { 3, 3 }, { 3, 1 })
        local u = unit(1, 0, 1, 2, 2)
        local plan = H.embark_plan(u, P['4,2'], 0, nil, false)
        local r = plan and plan.refuse
        assert(r and r.ok == false and r.embarks == true, H.json(r))
        assert(r.embarks_at.x == 3 and r.embarks_at.y == 2 and r.turns_by_water == 1 and r.turns_by_land == 2, H.json(r))
        assert(r.err:find('enters the water at (3,2) and arrives next turn, by land it arrives in 2 turns', 1, true), r.err)
        assert(r.err:find('land_only: true', 1, true) and r.err:find('confirm: true', 1, true), r.err)
        assert(H.embark_plan(u, P['4,2'], 0, 'confirm', false) == nil, 'the engine routes it')
        plan = H.embark_plan(u, P['4,2'], 0, 'land', false)
        assert(plan and plan.mode == 'land' and plan.stop and not plan.stop:IsWater(), 'land_only walks')
        assert(plan.turns == 2 and plan.water_turns == 1)
        plan = H.embark_plan(u, P['4,2'], 0, nil, true)
        assert(plan and plan.mode == 'land', 'a standing move taken up again never embarks unasked')
        """)

    def test_no_land_route_is_refused_and_says_so(self):
        self.run_lua("""
        for y = 0, 4 do plot(3, y, { water = true }); plot(7, y, { revealed = false }) end
        local u = unit(1, 0, 1, 2, 2)
        local r = H.move_route(u, P['4,2'], 0)
        assert(r.land == nil and r.water and r.water.turns == 1, H.json({ r.land ~= nil, r.water and r.water.turns }))
        local refuse = H.embark_plan(u, P['4,2'], 0, nil, false).refuse
        assert(refuse.turns_by_land == nil and refuse.err:find('no way by land to (4,2) is open now', 1, true), refuse.err)
        assert(not refuse.err:find('land_only', 1, true), 'nothing to walk: ' .. refuse.err)
        assert(H.embark_plan(u, P['4,2'], 0, nil, true).refuse, 'a standing move is held, not sent to sea')
        """)

    def test_land_that_is_faster_goes_out_as_it_always_did(self):
        self.run_lua("""
        lake()
        local u = unit(1, 0, 1, 2, 2)
        local r = H.move_route(u, P['3,3'], 0)
        assert(r.land.turns == 0 and (r.water == nil or r.water.turns >= 1))
        assert(H.embark_plan(u, P['3,3'], 0, nil, false) == nil)
        """)

    def test_water_destinations_attacks_and_units_afloat_are_not_planned(self):
        self.run_lua("""
        lake()
        local u = unit(1, 0, 1, 2, 2)
        assert(H.embark_plan(u, P['3,2'], 0, nil, false) == nil, 'the seat chose the water')
        assert(H.embark_plan(u, P['3,3'], 0, nil, false) == nil)
        u.IsEmbarked = function() return true end
        assert(H.embark_plan(u, P['4,2'], 0, nil, false) == nil, 'already afloat')
        """)

    def test_the_move_order_sends_the_leg_and_keeps_the_destination(self):
        self.run_lua("""
        lake(); forest({ 2, 1 })
        unit(1, 0, 1, 2, 2)
        local r = H.move_unit(1, 4, 2, 0)
        assert(r.ok == true and r.route and r.route.by == 'land', H.json(r))
        assert(r.route.leg.x == 3 and r.route.leg.y == 3 and r.route.arrives == 'next turn', H.json(r.route))
        assert(r.route.note:find('same length may go by water, entering it at (3,2)', 1, true), r.route.note)
        assert(#SENT == 1 and SENT[1][3] == 3 and SENT[1][4] == 3, 'the engine is sent the leg: ' .. H.json(SENT))
        local pm = H.pending_moves[H.pm_key(1, 0)]
        assert(pm.x == 4 and pm.y == 2 and pm.route == 'land', 'the record keeps the destination: ' .. H.json(pm))
        """)

    def test_the_move_order_refuses_before_anything_is_sent_and_confirm_sends_it(self):
        self.run_lua("""
        lake(); forest({ 2, 3 }, { 2, 1 }, { 3, 3 }, { 3, 1 })
        unit(1, 0, 1, 2, 2)
        local r = H.move_unit(1, 4, 2, 0)
        assert(r.ok == false and r.embarks == true and #SENT == 0, H.json(r))
        assert(H.pending_moves[H.pm_key(1, 0)] == nil, 'a refused move leaves no standing record')
        r = H.move_unit(1, 4, 2, 0, 'confirm')
        assert(r.ok == true and r.route == nil, H.json(r))
        assert(#SENT == 1 and SENT[1][3] == 4 and SENT[1][4] == 2, H.json(SENT))
        assert(H.pending_moves[H.pm_key(1, 0)].route == 'confirm', 'the word stays with the standing move')
        SENT = {}
        r = H.move_unit(1, 4, 2, 0, 'land')
        assert(r.ok == true and r.route.by == 'land' and r.route.arrives == 'in 2 turns', H.json(r))
        assert(r.route.note:find('is faster by water (it arrives next turn; args.confirm=true takes it)', 1, true), r.route.note)
        assert(#SENT == 1 and not P[SENT[1][3] .. ',' .. SENT[1][4]]:IsWater(), H.json(SENT))
        """)

    def test_a_standing_move_that_would_embark_is_held_and_one_that_was_confirmed_goes_on(self):
        self.run_lua("""
        H.melee_defender = function() return nil end
        H.peaceful_occupant = function() return nil end
        H.hold_standing_move = function() return nil end
        for y = 0, 4 do plot(3, y, { water = true }); plot(7, y, { revealed = false }) end
        local u = unit(1, 0, 1, 2, 2)
        u.GetBuildType = function() return -1 end
        H.pending_moves[H.pm_key(1, 0)] = { x = 4, y = 2, pid = 0, unit_id = 1 }
        local out = H.resume_moves(0)
        assert(#out == 1 and out[1].held == true and out[1].reason == 'would_embark', H.json(out))
        assert(out[1].err:find('standing move held: this move would embark the unit', 1, true), out[1].err)
        assert(out[1].embarks_at.x == 3 and #SENT == 0, 'nothing was sent')
        local pm = H.pending_moves[H.pm_key(1, 0)]
        assert(pm and pm.held_turn == 7 and pm.held_reason == 'would_embark', 'the record is kept: ' .. H.json(pm))
        H.pending_moves[H.pm_key(1, 0)] = { x = 4, y = 2, pid = 0, unit_id = 1, route = 'confirm' }
        out = H.resume_moves(0)
        assert(#out == 1 and out[1].resumed == true and #SENT == 1 and SENT[1][3] == 4, H.json(out))
        """)


THREATS = r"""
Game.GetActivePlayer = function() return 0 end
H.reveal_diff = function() return { count = 0 } end
H.unit_hold_state = function() return {} end
GameInfo.Units[3].RangedCombat = 7
GameInfo.Units[5] = { Type = 'UNIT_GALLEASS', Range = 2, RangedCombat = 17 }
function enemy_city(x, y, name)
  P[x .. ',' .. y].o.enemy_city = { GetName = function() return name end, GetOwner = function() return 3 end }
end
H.enemy_city_at = function(q) return q.o.enemy_city end
"""


class StrikeThreatTests(unittest.TestCase):
    run_lua = support.LuaRuntimeTests.run_lua

    def setUp(self):
        support.LuaRuntimeTests.setUp(self)
        self.run_lua(WORLD)
        self.run_lua(COSTS)
        self.run_lua(THREATS)

    def test_a_city_and_a_ranged_unit_in_reach_are_named_nearest_first(self):
        self.run_lua("""
        unit(1, 0, 1, 2, 2)
        enemy_city(4, 2, "Attila's Court")               -- two plots east: a city strikes two plots
        local g = unit(7, 63, 5, 2, 3)                   -- a barbarian Galleass on NE, range 2
        unit(8, 63, 2, 1, 2)                             -- a Brute beside me: no ranged attack
        local t = H.unit_pos(1, 0, true).in_range_of
        assert(#t == 2, H.json(t))
        assert(t[1].unit == 'GALLEASS' and t[1].distance == 1 and t[1].range == 2 and t[1].owner == 'Barbarians', H.json(t[1]))
        assert(t[2].city == "Attila's Court" and t[2].distance == 2 and t[2].range == 2 and t[2].owner == 'Persia', H.json(t[2]))
        assert(H.unit_pos(1, 0).in_range_of == nil, 'only the read after a move carries it')
        """)

    def test_out_of_reach_at_peace_fogged_or_afloat_says_nothing(self):
        self.run_lua("""
        local me = unit(1, 0, 1, 2, 2)
        enemy_city(5, 2, 'Far')                          -- three plots
        unit(7, 3, 3, 2, 3)                              -- Persia's Archer, at peace
        local afloat = unit(8, 63, 3, 1, 2)
        afloat.IsEmbarked = function() return true end
        assert(H.strike_threats(me, 0) == nil, H.json(H.strike_threats(me, 0)))
        assert(H.unit_pos(1, 0, true).in_range_of == nil)
        """)


if __name__ == "__main__":
    unittest.main()
