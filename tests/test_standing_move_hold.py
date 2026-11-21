"""A standing move is held, not resumed, when resuming would walk the unit into harm or waste its purpose (GitLab #98).

Live Maya t34-t38 and t54-t62 (2026-10-27): the resume ran at the turn start, before the seat saw the turn. A
Spearman and then a Scout walked one plot a turn around a barbarian camp, arrived in `ongoing` with 0 moves every
turn, were bombarded every AI turn and died with no turn to react. Settlers and Prophets arrived with 0 moves and
lost the turn their purpose needed. Now the record is kept and the move is not re-issued when a hostile or a camp
is beside the unit, or when a civilian's destination is within this turn's reach; the unit stands in todo.units
with its moves and the reason.
"""
import unittest

import test_mcp_safety as support
from harness.game import Game

WORLD = """
GameDefines = { MOVE_DENOMINATOR = 60 }
GameInfoTypes = { IMPROVEMENT_BARBARIAN_CAMP = 7 }
GameInfo = GameInfo or {}
GameInfo.Units = { [1] = { Type = 'UNIT_WARRIOR' }, [2] = { Type = 'UNIT_SETTLER' } }
PLOTS = {}
function plot(x, y)
  local k = x .. ',' .. y
  PLOTS[k] = PLOTS[k] or { units = {}, imp = -1,
    GetX = function() return x end, GetY = function() return y end,
    IsVisible = function() return true end, IsRevealed = function() return true end,
    IsImpassable = function() return false end,
    GetRevealedImprovementType = function(self) return self.imp end,
    GetNumUnits = function(self) return #self.units end, GetUnit = function(self, i) return self.units[i + 1] end }
  return PLOTS[k]
end
Map = { GetPlot = plot, PlotDistance = function(x1, y1, x2, y2) return math.max(math.abs(x1 - x2), math.abs(y1 - y2)) end }
UNITS = {}
Players = { [0] = { GetTeam = function() return 0 end, IsBarbarian = function() return false end,
                    GetUnitByID = function(_, id) return UNITS[id] end },
            [63] = { GetTeam = function() return 63 end, IsBarbarian = function() return true end } }
Teams = { [0] = { IsAtWar = function() return false end } }
H.melee_defender = function() return nil end
H.enemy_city_at = function() return false end
H.peaceful_occupant = function() return nil end
MOVED = {}
H.move_unit = function(id, x, y, pid) MOVED[#MOVED + 1] = { id, x, y }; return { ok = true } end
function mk(id, utype, x, y, combat)
  return { GetID = function() return id end, GetX = function() return x end, GetY = function() return y end,
           MovesLeft = function() return 120 end, MaxMoves = function() return 120 end,
           IsDelayedDeath = function() return false end, IsCombatUnit = function() return combat end,
           GetBuildType = function() return -1 end, GetUnitType = function() return utype end,
           GetOwner = function() return 0 end }
end
UNITS[1] = mk(1, 1, 22, 48, true)    -- the Spearman beside the camp
UNITS[2] = mk(2, 2, 10, 10, false)   -- a Settler
UNITS[3] = mk(3, 1, 5, 5, true)      -- a Warrior with nothing around
BRUTE = { GetOwner = function() return 63 end, IsCombatUnit = function() return true end,
          IsInvisible = function() return false end, GetUnitType = function() return 1 end,
          GetCurrHitPoints = function() return 100 end }
plot(23, 48).units = { BRUTE }
H.pending_moves = {}
"""


class HeldStandingMoveLuaTests(unittest.TestCase):
    run_lua = support.LuaRuntimeTests.run_lua

    def setUp(self):
        support.LuaRuntimeTests.setUp(self)
        self.run_lua(WORLD)

    def test_a_hostile_beside_the_unit_holds_the_move_and_keeps_the_record(self):
        self.run_lua("""
        H.pending_moves[H.pm_key(1, 0)] = { x = 31, y = 60, pid = 0, unit_id = 1 }
        local out = H.resume_moves(0)
        assert(#out == 1 and out[1].held == true and out[1].reason == 'hostile', H.json(out))
        assert(out[1].err:find('standing move held', 1, true) and out[1].err:find('COMMAND_CANCEL', 1, true), out[1].err)
        assert(out[1].attention[1].kind == 'hostile' and out[1].attention[1].x == 23, H.json(out[1].attention))
        assert(#MOVED == 0, 'the move was not re-issued')
        assert(H.pending_moves[H.pm_key(1, 0)] ~= nil, 'the record survives: a move to the same plot resumes it')
        """)

    def test_a_camp_beside_the_unit_holds_it_too(self):
        self.run_lua("""
        plot(23, 48).units = {}
        plot(21, 47).imp = 7
        H.pending_moves[H.pm_key(1, 0)] = { x = 31, y = 60, pid = 0, unit_id = 1 }
        local out = H.resume_moves(0)
        assert(#out == 1 and out[1].held == true and out[1].reason == 'camp', H.json(out))
        assert(out[1].err:find('barbarian camp at (21,47)', 1, true), out[1].err)
        assert(#MOVED == 0)
        """)

    def test_a_civilian_within_reach_is_left_to_the_seat_and_a_far_one_resumes(self):
        self.run_lua("""
        H.pending_moves[H.pm_key(2, 0)] = { x = 11, y = 10, pid = 0, unit_id = 2 }
        local out = H.resume_moves(0)
        assert(#out == 1 and out[1].held == true and out[1].reason == 'within_reach', H.json(out))
        assert(out[1].err:find('act on arrival', 1, true), out[1].err)
        assert(#MOVED == 0 and H.pending_moves[H.pm_key(2, 0)] ~= nil)
        H.pending_moves = {}
        H.pending_moves[H.pm_key(2, 0)] = { x = 20, y = 10, pid = 0, unit_id = 2 }
        out = H.resume_moves(0)
        assert(#out == 1 and out[1].resumed == true, H.json(out))
        assert(#MOVED == 1 and MOVED[1][1] == 2 and MOVED[1][2] == 20, H.json(MOVED))
        """)

    def test_my_own_civilian_on_the_destination_keeps_the_move(self):
        """GitLab #86 (Assyria t253): an automated Worker walked into the capital overnight and the Booster's standing
        move was dropped for good. One of my own civilians moves on: the record stays and tries again next turn."""
        self.run_lua("""
        H.move_unit = function(id, x, y, pid)
          return { ok = false, err = 'destination already holds your WORKER 172039 (automated; it still holds the plot) (one civilian per tile)',
                   blocking_unit = { id = 172039, type = 'WORKER', automated = true } }
        end
        H.pending_moves[H.pm_key(2, 0)] = { x = 20, y = 10, pid = 0, unit_id = 2 }
        local out = H.resume_moves(0)
        assert(#out == 1 and out[1].held == true and out[1].reason == 'own_unit_on_destination', H.json(out))
        assert(out[1].blocking_unit.id == 172039 and out[1].err:find('tries again next turn start', 1, true), H.json(out))
        assert(H.pending_moves[H.pm_key(2, 0)] ~= nil, 'the record survives')
        H.move_unit = function() return { ok = false, err = 'no path' } end
        out = H.resume_moves(0)
        assert(out[1].dropped == true and H.pending_moves[H.pm_key(2, 0)] == nil, 'any other refusal still drops it')
        """)

    def test_a_combat_unit_with_nothing_around_resumes_as_before(self):
        self.run_lua("""
        H.pending_moves[H.pm_key(3, 0)] = { x = 9, y = 9, pid = 0, unit_id = 3 }
        local out = H.resume_moves(0)
        assert(#out == 1 and out[1].resumed == true, H.json(out))
        assert(#MOVED == 1 and MOVED[1][1] == 3, H.json(MOVED))
        """)

    # GitLab #211 (live 2026-11-18, the scripted loop on the Celts duel, turn 38): the held unit blocks the end of
    # the turn, its note names MISSION_SKIP, and the skip was refused as "does not block end_turn".
    ORDERS = """
    MissionTypes = { MISSION_SKIP = 4 }
    GameMessageTypes = { GAMEMESSAGE_PUSH_MISSION = 9 }
    ActivityTypes = { ACTIVITY_AWAKE = 0, ACTIVITY_MISSION = 6 }
    SENT = {}
    Game.SelectionListGameNetMessage = function(msg, a, b, c) SENT[#SENT + 1] = { msg, a } end
    UI = { GetHeadSelectedUnit = function() return SELECTED end, SelectUnit = function(u) SELECTED = u end }
    for _, u in pairs(UNITS) do
      u.queue, u.activity, u.moves = 0, 0, 120
      u.GetLengthMissionQueue = function() return u.queue end
      u.GetActivityType = function() return u.activity end
      u.MovesLeft = function() return u.moves end
      u.CanStartMission = function() return true end
    end
    """

    def test_a_skip_on_a_held_unit_goes_through_and_says_which_path_it_dropped(self):
        self.run_lua(self.ORDERS + """
        H.pending_moves[H.pm_key(1, 0)] = { x = 31, y = 60, pid = 0, unit_id = 1 }
        local out = H.resume_moves(0)
        assert(out[1].held == true and out[1].err:find('MISSION_SKIP', 1, true), H.json(out))
        local r = H.unit_mission(1, 'MISSION_SKIP', nil, nil, nil, 0)
        assert(r.ok == true, H.json(r))
        local d = r.standing_move_dropped
        assert(d and d.x == 31 and d.y == 60 and d.held_because == 'hostile', H.json(r))
        assert(d.note:find('held this turn and is dropped', 1, true), d.note)
        assert(#SENT == 1 and SENT[1][1] == 9 and SENT[1][2] == 4, 'the skip was sent: ' .. H.json(SENT))
        assert(H.pending_moves[H.pm_key(1, 0)] == nil, 'the record is gone')
        """)

    def test_a_skip_on_a_move_held_for_my_own_unit_on_the_destination_goes_through_too(self):
        self.run_lua(self.ORDERS + """
        H.move_unit = function() return { ok = false, err = 'destination already holds your WORKER 9',
                                          blocking_unit = { id = 9, type = 'WORKER' } } end
        H.pending_moves[H.pm_key(3, 0)] = { x = 9, y = 9, pid = 0, unit_id = 3 }
        local out = H.resume_moves(0)
        assert(out[1].held == true and out[1].reason == 'own_unit_on_destination', H.json(out))
        local r = H.unit_mission(3, 'MISSION_SKIP', nil, nil, nil, 0)
        assert(r.ok == true and r.standing_move_dropped.held_because == 'own_unit_on_destination', H.json(r))
        """)

    def test_a_skip_on_a_move_that_is_under_way_is_still_refused_and_the_record_kept(self):
        self.run_lua(self.ORDERS + """
        -- the Caravel of t306: the path is queued, or the unit spent its moves walking it
        for _, case in ipairs({ { queue = 1, moves = 120 }, { queue = 0, moves = 0 }, { queue = 0, moves = 120 } }) do
          SENT = {}
          UNITS[3].queue, UNITS[3].moves = case.queue, case.moves
          H.pending_moves[H.pm_key(3, 0)] = { x = 9, y = 9, pid = 0, unit_id = 3 }
          local r = H.unit_mission(3, 'MISSION_SKIP', nil, nil, nil, 0)
          assert(r.ok == false and r.err:find('does not block end_turn', 1, true), H.json(case) .. ' ' .. H.json(r))
          assert(#SENT == 0 and H.pending_moves[H.pm_key(3, 0)] ~= nil, 'nothing sent, the record stays: ' .. H.json(case))
        end
        """)

    def test_a_hold_of_an_earlier_turn_does_not_let_a_skip_through(self):
        self.run_lua(self.ORDERS + """
        H.pending_moves[H.pm_key(3, 0)] = { x = 9, y = 9, pid = 0, unit_id = 3, held_turn = 0, held_reason = 'hostile' }
        local r = H.unit_mission(3, 'MISSION_SKIP', nil, nil, nil, 0)
        assert(r.ok == false and r.err:find('does not block end_turn', 1, true), H.json(r))
        """)

    def test_the_skip_refusal_names_the_cancel_command(self):
        from harness import runtime_source
        src = runtime_source.snapshot().text
        self.assertIn("COMMAND_CANCEL'}) to drop the path on purpose", src)


class HeldMoveIsATodoNote(unittest.TestCase):
    """The arrival puts a held move's reason on the unit's todo row, as it does a dropped one's."""

    def test_the_row_carries_the_reason(self):
        g = Game.__new__(Game)
        g.seat = 0
        g._runtime_ok = True
        g._pid = lambda pid=None: 0
        held = {"unit_id": 24576, "x": 31, "y": 60, "held": True, "reason": "hostile",
                "err": "standing move held: Barbarians WARRIOR at (23,48) is beside the unit, so it keeps its moves this turn"}
        flags = dict.fromkeys(Game.MODAL_FLAGS, False)

        def q(code, timeout=None):
            if "H.resume_moves" in code:
                return [held]
            if "H.turn_state" in code:
                return {"turn": 35, "active_player": 0, "my_turn": True, "processing": False, "hotseat": False,
                        "pending_popups": [], **flags,
                        "todo": {"units": [{"id": 24576, "type": "SPEARMAN", "x": 22, "y": 48, "moves": 2}]}}
            return []
        g.q = q
        g.notebook = lambda: (_ for _ in ()).throw(RuntimeError("no notebook here"))
        g.expiring_city_states = list
        g._unit_rows = lambda pid=None: [{"id": 24576, "x": 22, "y": 48, "moves": 2, "max_moves": 2}]
        from unittest import mock
        with mock.patch("harness.game.time.sleep", lambda s: None):
            ts = g._arrive(g.turn_state())
        self.assertEqual(ts["resumed_moves"], [held])
        self.assertEqual(ts["todo"]["units"][0]["note"], held["err"])

    def test_an_ongoing_row_carries_the_reason_too(self):
        """Live Maya t5: the move was ordered on an automated Warrior at 0 moves; the hold landed and the unit sat in
        `ongoing` with no word of it."""
        g = Game.__new__(Game)
        g.seat = 0
        g._runtime_ok = True
        g._pid = lambda pid=None: 0
        held = {"unit_id": 16385, "x": 31, "y": 25, "held": True, "reason": "camp", "err": "standing move held: a barbarian camp"}
        flags = dict.fromkeys(Game.MODAL_FLAGS, False)
        g.q = lambda code, timeout=None: [held] if "H.resume_moves" in code else (
            {"turn": 5, "active_player": 0, "my_turn": True, "processing": False, "hotseat": False, "pending_popups": [], **flags,
             "todo": {"units": [], "ongoing": [{"id": 16385, "type": "WARRIOR", "automated": True, "x": 31, "y": 24}]}}
            if "H.turn_state" in code else [])
        g.notebook = lambda: (_ for _ in ()).throw(RuntimeError("none"))
        g.expiring_city_states = list
        g._unit_rows = lambda pid=None: [{"id": 16385, "x": 31, "y": 24, "moves": 0, "max_moves": 2}]
        from unittest import mock
        with mock.patch("harness.game.time.sleep", lambda s: None):
            ts = g._arrive(g.turn_state())
        self.assertEqual(ts["todo"]["ongoing"][0]["note"], held["err"])

    def test_a_held_move_on_a_unit_listed_by_id_makes_it_a_row_again(self):
        """v341 (#191): a quiet automated unit is an id under its type; a held move gives it something to say."""
        g = Game.__new__(Game)
        g.seat = 0
        g._runtime_ok = True
        g._pid = lambda pid=None: 0
        held = {"unit_id": 16385, "x": 31, "y": 25, "held": True, "reason": "camp", "err": "standing move held: a barbarian camp"}
        flags = dict.fromkeys(Game.MODAL_FLAGS, False)
        g.q = lambda code, timeout=None: [held] if "H.resume_moves" in code else (
            {"turn": 5, "active_player": 0, "my_turn": True, "processing": False, "hotseat": False, "pending_popups": [], **flags,
             "todo": {"units": [], "automated": {"WARRIOR": [16385], "WORKER": [9]}}}
            if "H.turn_state" in code else [])
        g.notebook = lambda: (_ for _ in ()).throw(RuntimeError("none"))
        g.expiring_city_states = list
        g._unit_rows = lambda pid=None: [{"id": 16385, "x": 31, "y": 24, "moves": 0, "max_moves": 2}]
        from unittest import mock
        with mock.patch("harness.game.time.sleep", lambda s: None):
            ts = g._arrive(g.turn_state())
        self.assertEqual(ts["todo"]["ongoing"], [{"id": 16385, "type": "WARRIOR", "automated": True, "note": held["err"]}])
        self.assertEqual(ts["todo"]["automated"], {"WORKER": [9]})


if __name__ == "__main__":
    unittest.main()
