"""The four gaps left from Opus 5.5's reports of the duel against the Huns (runtime v348).

Its siege of Attila's Court, turns 198 to 219 (`bench-seats/duel-king-rome-huns-a/opus-medium-from-t180/`):
  "A 'threat map' per tile: which enemy ranged units and cities can hit it next turn, for picking siege positions."
  "A hex-distance helper, or a ring listing such as 'plots at distance N from (x,y)'."
  how many turns a standing move takes (the move's reply said only that it was still on its way);
  "The unit_attacks row had listed this cannon as 'in_range 2, needs_set_up', so I spent a move setting it up for
  nothing" (hills stood in the line of fire).

Who can strike a plot is H.plot_threats, the plots at a distance H.plot_ring, both read as
state(what="map", view="window", x, y, detail="threats" | "ring"); a move that does not arrive says
`arrives_in_turns` / `arrives_turn` and `going_to` keeps the turn; a `needs_set_up` row counts the line of fire.

The map is the tactical view's mocked 8 x 5 wrapped one (tests/test_tactical_view.py WORLD), unit at (2,2).
"""
import itertools
import json
import unittest
from unittest import mock

import test_mcp_safety as support
from test_embark_route import NET, THREATS
from test_tactical_step_cost import COSTS
from test_tactical_view import WORLD
from tests.test_after_reads import _game


class PlotThreatTests(unittest.TestCase):
    run_lua = support.LuaRuntimeTests.run_lua

    def setUp(self):
        support.LuaRuntimeTests.setUp(self)
        self.run_lua(WORLD)
        self.run_lua(COSTS)
        self.run_lua(THREATS)
        self.run_lua("GameInfo.Units[5].Moves = 3")

    def test_a_plot_nobody_stands_on_is_asked_before_the_move(self):
        self.run_lua("""
        enemy_city(4, 2, "Attila's Court")               -- two plots east of (2,2)
        unit(7, 63, 5, 2, 3)                             -- a barbarian Galleass one plot away, range 2
        unit(8, 63, 2, 1, 2)                             -- a Brute: no ranged attack
        local r = H.plot_threats(2, 2, 0)
        assert(r.ok and r.x == 2 and r.y == 2 and r.total == 2, H.json(r))
        assert(r.in_range_of[1].unit == 'GALLEASS' and r.in_range_of[1].distance == 1 and r.in_range_of[1].hp == 100, H.json(r.in_range_of))
        assert(r.in_range_of[2].city == "Attila's Court" and r.in_range_of[2].range == 2 and r.in_range_of[2].owner == 'Persia')
        assert(r.could_move_into_range == nil and r.not_in_sight == nil, H.json(r))
        assert(r.scope:find('line of fire is not tested', 1, true), r.scope)
        """)

    def test_a_ranged_unit_a_move_would_bring_into_range_is_named_apart(self):
        self.run_lua("""
        unit(7, 63, 5, 5, 2)                             -- three plots off: range 2, three moves
        unit(9, 63, 3, 6, 2)                             -- an Archer four plots off: no Moves in the pedia row
        local r = H.plot_threats(2, 2, 0)
        assert(r.ok and r.total == 0 and #r.in_range_of == 0, H.json(r))
        assert(#r.could_move_into_range == 1, H.json(r.could_move_into_range))
        local g = r.could_move_into_range[1]
        assert(g.unit == 'GALLEASS' and g.distance == 3 and g.range == 2 and g.moves == 3 and g.x == 5, H.json(g))
        assert(r.could_move_note:find('are not counted', 1, true), r.could_move_note)
        assert(H.strike_threats(UNITS[1] or unit(1, 0, 1, 2, 2), 0) == nil, 'a move reply names only who covers the plot now')
        """)

    def test_what_is_not_in_sight_is_counted_and_never_read(self):
        self.run_lua("""
        plot(1, 2, { fog = true })                       -- GetUnit on it errors (WORLD's forbidden reads)
        plot(0, 0, { revealed = false })
        local r = H.plot_threats(2, 2, 0)
        assert(r.ok and r.total == 0 and r.not_in_sight == 2, H.json(r))
        assert(r.not_in_sight_note:find('2 of the plots within 4 are not in my sight', 1, true), r.not_in_sight_note)
        local no = H.plot_threats(0, 0, 0)
        assert(no.ok == false and no.err:find('not on the map I have revealed', 1, true), H.json(no))
        """)

    def test_units_at_peace_and_units_afloat_strike_nothing(self):
        self.run_lua("""
        unit(7, 3, 3, 2, 3)                              -- Persia's Archer, at peace
        local afloat = unit(8, 63, 5, 3, 2)
        afloat.IsEmbarked = function() return true end
        local r = H.plot_threats(2, 2, 0)
        assert(r.total == 0 and r.could_move_into_range == nil, H.json(r))
        """)


class PlotRingTests(unittest.TestCase):
    run_lua = support.LuaRuntimeTests.run_lua

    def setUp(self):
        support.LuaRuntimeTests.setUp(self)
        self.run_lua(WORLD)
        self.run_lua(COSTS)
        self.run_lua(THREATS)

    def test_the_ring_is_every_plot_at_that_distance_and_no_other(self):
        self.run_lua("""
        for n = 1, 2 do
          local r = H.plot_ring(2, 2, n, 0)
          assert(r.ok and r.distance == n and r.total == 6 * n and #r.plots == 6 * n, H.json({ n, r.total }))
          local seen = {}
          for _, e in ipairs(r.plots) do
            assert(hexdist(2, 2, e.x, e.y) == n, e.x .. ',' .. e.y)
            assert(not seen[e.x .. ',' .. e.y], 'a plot twice')
            seen[e.x .. ',' .. e.y] = true
          end
        end
        local one = H.plot_ring(2, 2, 1, 0).plots
        assert(one[1].x == 1 and one[1].y == 3 and one[2].x == 2 and one[#one].y == 1, 'north first, then west to east: ' .. H.json(one))
        """)

    def test_a_row_says_the_ground_who_stands_there_and_who_can_strike_it(self):
        self.run_lua("""
        plot(3, 2, { hills = true }); plot(2, 3, { forest = true }); plot(2, 1, { water = true }); plot(1, 2, { mountain = true })
        enemy_city(4, 2, "Attila's Court")
        P['4,2'].o.city = { GetName = function() return "Attila's Court" end, GetOwner = function() return 3 end }
        unit(5, 0, 1, 3, 2)                              -- my Warrior on the hill
        unit(8, 63, 2, 1, 3)                             -- a Brute
        local by = {}
        for _, e in ipairs(H.plot_ring(2, 2, 1, 0).plots) do by[e.x .. ',' .. e.y] = e end
        assert(by['3,2'].ground == 'hills' and by['3,2'].struck_by == 1, H.json(by['3,2']))
        assert(by['3,2'].units[1].unit == 'WARRIOR' and by['3,2'].units[1].owner == 'you' and by['3,2'].units[1].id == 5)
        assert(by['2,3'].ground == 'flat' and by['2,3'].feature == 'FOREST' and by['2,3'].struck_by == 1, H.json(by['2,3']))
        assert(by['2,1'].ground == 'water' and by['1,2'].ground == 'mountain')
        assert(by['1,3'].units[1].unit == 'BRUTE' and by['1,3'].units[1].owner == 'Barbarians' and by['1,3'].units[1].id == nil)
        assert(by['1,3'].struck_by == nil, 'three plots from the city: ' .. H.json(by['1,3']))
        local two = {}
        for _, e in ipairs(H.plot_ring(2, 2, 2, 0).plots) do two[e.x .. ',' .. e.y] = e end
        assert(two['4,2'].city == "Attila's Court" and two['4,2'].owner == 'Persia', H.json(two['4,2']))
        """)

    def test_a_fogged_plot_keeps_its_ground_and_an_unrevealed_one_is_its_coordinates(self):
        self.run_lua("""
        plot(3, 2, { fog = true, hills = true })         -- GetUnit / GetFeatureType on it error
        plot(2, 3, { revealed = false })
        local by = {}
        for _, e in ipairs(H.plot_ring(2, 2, 1, 0).plots) do by[e.x .. ',' .. e.y] = e end
        assert(by['3,2'].ground == 'hills' and by['3,2'].fogged == true and by['3,2'].units == nil, H.json(by['3,2']))
        assert(by['2,3'].unrevealed == true and by['2,3'].ground == nil and by['2,3'].struck_by == nil, H.json(by['2,3']))
        """)


class MoveTurnsLuaTests(unittest.TestCase):
    run_lua = support.LuaRuntimeTests.run_lua

    def setUp(self):
        support.LuaRuntimeTests.setUp(self)
        self.run_lua(WORLD)
        self.run_lua(COSTS)
        self.run_lua(NET)

    def test_a_move_says_how_many_turns_it_takes_and_the_record_keeps_the_turn(self):
        self.run_lua("""
        local u = unit(1, 0, 1, 2, 2)
        local r = H.move_unit(1, 4, 2, 0)                -- two open steps, two moves
        assert(r.ok and r.turns == 0 and r.turn == 7, H.json(r))
        forest({ 3, 2 }, { 2, 3 }, { 2, 1 }, { 3, 3 }, { 3, 1 })   -- every way costs both moves a step
        r = H.move_unit(1, 4, 2, 0)
        assert(r.ok and r.turns == 1, 'the second step is next turn: ' .. H.json(r))
        local pm = H.pending_moves[H.pm_key(1, 0)]
        assert(pm.arrives_turn == 8, H.json(pm))
        local g = H.going_to(u, 0)
        assert(g.x == 4 and g.y == 2 and g.arrives_turn == 8, H.json(g))
        """)

    def test_a_unit_with_no_moves_left_starts_next_turn(self):
        self.run_lua("""
        unit(1, 0, 1, 2, 2, { moves = 0 })
        local r = H.move_unit(1, 4, 2, 0)
        assert(r.ok and r.turns == 1, H.json(r))
        r = H.move_unit(1, 3, 2, 0)                      -- the plot beside it
        assert(r.ok and r.turns == 1, H.json(r))
        """)

    def test_the_land_walk_and_the_engines_own_route_count_alike(self):
        self.run_lua("""
        lake(); forest({ 2, 1 })
        unit(1, 0, 1, 2, 2)
        local r = H.move_unit(1, 4, 2, 0)                -- walks by land, a leg a turn
        assert(r.route.by == 'land' and r.turns == 1 and r.route.arrives == 'next turn', H.json(r))
        forest({ 2, 3 }, { 3, 3 }, { 3, 1 })
        r = H.move_unit(1, 4, 2, 0, 'confirm')           -- the water is faster and the order says take it
        assert(r.ok and r.route == nil and r.turns == 1, 'the faster of the two ways: ' .. H.json(r))
        """)

    def test_an_attack_and_a_way_the_walk_does_not_find_say_nothing(self):
        self.run_lua("""
        unit(1, 0, 1, 2, 2)
        H.move_route = function() return nil end
        local r = H.move_unit(1, 4, 2, 0)
        assert(r.ok and r.turns == nil, H.json(r))
        assert(H.pending_moves[H.pm_key(1, 0)].arrives_turn == nil)
        H.melee_defender = function(u, q) return q == P['3,2'] and {} or nil end
        r = H.move_unit(1, 3, 2, 0)
        assert(r.ok and r.turns == nil, 'an attack is never a standing move: ' .. H.json(r))
        """)

    def test_a_resumed_standing_move_says_the_turns_left(self):
        self.run_lua("""
        H.melee_defender = function() return nil end
        H.peaceful_occupant = function() return nil end
        H.hold_standing_move = function() return nil end
        forest({ 3, 2 }, { 2, 3 }, { 2, 1 }, { 3, 3 }, { 3, 1 })
        local u = unit(1, 0, 1, 2, 2)
        u.GetBuildType = function() return -1 end
        H.pending_moves[H.pm_key(1, 0)] = { x = 4, y = 2, pid = 0, unit_id = 1, arrives_turn = 5 }
        local out = H.resume_moves(0)
        assert(#out == 1 and out[1].resumed == true and out[1].arrives_in_turns == 1, H.json(out))
        assert(H.pending_moves[H.pm_key(1, 0)].arrives_turn == 8, 'counted again from this turn')
        """)


class MoveTurnsReplyTests(unittest.TestCase):
    def setUp(self):
        self.sleep = mock.patch("harness.game_parts.units.time.sleep")
        self.sleep.start()
        self.clock = mock.patch("harness.game_parts.units.time.monotonic", side_effect=itertools.count(0, 0.6))
        self.clock.start()

    def tearDown(self):
        self.sleep.stop()
        self.clock.stop()

    def test_a_move_still_on_its_way_says_the_turns_and_the_turn(self):
        g = _game([("H.attack_before", {"attack": False}),
                   ("H.move_unit", {"ok": True, "x": 4, "y": 5, "moves": 2, "turns": 3, "turn": 201}),
                   ("H.unit_pos", {"ok": True, "x": 5, "y": 5, "moves": 0, "activity": 6, "revealed": {"count": 0}}),
                   ("H.note_unit", True)])
        r = g.move_unit(9, 12, 5)
        self.assertTrue(r["ok"] and not r["arrived"])
        self.assertEqual((r["arrives_in_turns"], r["arrives_turn"], r["destination"]), (3, 204, {"x": 12, "y": 5}))

    def test_a_count_of_this_turn_that_did_not_arrive_is_next_turn(self):
        g = _game([("H.attack_before", {"attack": False}),
                   ("H.move_unit", {"ok": True, "x": 4, "y": 5, "moves": 2, "turns": 0, "turn": 201}),
                   ("H.unit_pos", {"ok": True, "x": 5, "y": 5, "moves": 0, "activity": 6, "revealed": {"count": 0}}),
                   ("H.note_unit", True)])
        r = g.move_unit(9, 6, 5)
        self.assertEqual((r["arrives_in_turns"], r["arrives_turn"]), (1, 202))

    def test_a_queued_move_says_it_too_and_an_arrival_or_no_count_says_nothing(self):
        g = _game([("H.attack_before", {"attack": False}),
                   ("H.move_unit", {"ok": True, "x": 4, "y": 5, "moves": 0, "turns": 2, "turn": 201}),
                   ("H.unit_pos", {"ok": True, "x": 4, "y": 5, "moves": 0, "activity": 6, "revealed": {"count": 0}})])
        r = g.move_unit(9, 8, 5)
        self.assertTrue(r["queued"])
        self.assertEqual((r["arrives_in_turns"], r["arrives_turn"], r["going_to"]), (2, 203, {"x": 8, "y": 5}))
        g = _game([("H.attack_before", {"attack": False}),
                   ("H.move_unit", {"ok": True, "x": 4, "y": 5, "moves": 2, "turns": 0, "turn": 201}),
                   ("H.unit_pos", {"ok": True, "x": 5, "y": 5, "moves": 1, "activity": 0, "revealed": {"count": 0}}),
                   ("H.note_unit", True)])
        r = g.move_unit(9, 5, 5)
        self.assertTrue(r["arrived"])
        self.assertNotIn("arrives_in_turns", r)
        g = _game([("H.attack_before", {"attack": False}),
                   ("H.move_unit", {"ok": True, "x": 4, "y": 5, "moves": 2}),
                   ("H.unit_pos", {"ok": True, "x": 5, "y": 5, "moves": 0, "activity": 6, "revealed": {"count": 0}}),
                   ("H.note_unit", True)])
        self.assertNotIn("arrives_in_turns", g.move_unit(9, 12, 5))


class MapDetailTests(unittest.TestCase):
    """Both reads are details of the map window: the catalog of old handlers stays what it was (#44)."""

    def test_the_two_details_route_through_the_map_window(self):
        from harness.surface import dispatch as D
        call = D.resolve("state", {"what": "map", "view": "window"}, {"x": 13, "y": 11, "detail": "threats"})
        self.assertIsInstance(call, D.Call)
        self.assertEqual((call.tool, call.args), ("map_window", {"x": 13, "y": 11, "detail": "threats"}))
        call = D.resolve("state", {"what": "map", "view": "window"}, {"x": 13, "y": 11, "radius": 3, "detail": "ring"})
        self.assertEqual(call.args, {"x": 13, "y": 11, "radius": 3, "detail": "ring"})

    def test_the_handler_reads_the_one_asked_for(self):
        from harness import mcp_server as core
        from harness.mcp_tools import units
        g = _game([("H.plot_threats(13, 11", {"ok": True, "total": 0, "in_range_of": []}),
                   ("H.plot_ring(13, 11, 3", {"ok": True, "distance": 3, "plots": []}),
                   ("H.plots_around(13, 11, 3", [{"x": 13, "y": 11}])])
        with mock.patch.object(core, "game", return_value=g):
            self.assertEqual(json.loads(units.map_window.__wrapped__(13, 11, detail="threats")), {"ok": True, "total": 0, "in_range_of": []})
            self.assertEqual(json.loads(units.map_window.__wrapped__(13, 11, 3, "ring"))["distance"], 3)
            self.assertEqual(json.loads(units.map_window.__wrapped__(13, 11)), [{"x": 13, "y": 11}])
            no = json.loads(units.map_window.__wrapped__(13, 11, detail="roads"))
            self.assertEqual((no["ok"], no["err"]), (False, "detail is one of plots (default), threats, ring, not 'roads'"))
        with self.assertRaises(ValueError):
            g.plot_ring(13, 11, 7)
        with self.assertRaises(ValueError):
            g.plot_ring(13, 11, 0)


if __name__ == "__main__":
    unittest.main()
