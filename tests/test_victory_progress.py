"""The briefing that opens an instance says where every civilization stands toward every victory (runtime v349,
the user's decision of 2026-11-26).

A seat is handed a new context every ten turns and, unlike a player who opens the Victory Progress screen when
they wonder, never looked. The table is that screen's own (with the Culture Overview's victory tab and the World
Congress's member column): a civilization the seat has not met is a row without a name, as it is there, and a
victory the game's options do not allow has no column.
"""
import unittest

import test_mcp_safety as support
from harness.briefing import build


WORLD = """
GameDefines = { MAX_CIV_PLAYERS = 4, MAX_MAJOR_CIVS = 4 }
InfluenceLevelTrend = { INFLUENCE_TREND_FALLING = 0, INFLUENCE_TREND_STATIC = 1, INFLUENCE_TREND_RISING = 2 }
InfluenceLevelTypes = { NO_INFLUENCE_LEVEL = -1 }
Locale = { Lookup = function(k) return k end }
OFF = {}                                   -- victory types this game's options do not allow
GameInfo = { Victories = { VICTORY_CULTURAL = { ID = 1 }, VICTORY_SPACE_RACE = { ID = 2 },
                           VICTORY_DIPLOMATIC = { ID = 3 }, VICTORY_DOMINATION = { ID = 4 } },
             Project_VictoryThresholds = function()
               local rows = { { ProjectType = 'PROJECT_APOLLO_PROGRAM', Threshold = 1 },
                              { ProjectType = 'PROJECT_SS_BOOSTER', Threshold = 3 },
                              { ProjectType = 'PROJECT_SS_COCKPIT', Threshold = 1 },
                              { ProjectType = 'PROJECT_SS_STASIS_CHAMBER', Threshold = 1 },
                              { ProjectType = 'PROJECT_SS_ENGINE', Threshold = 1 } }
               local i = 0
               return function() i = i + 1; return rows[i] end
             end }
GameInfoTypes = { PROJECT_APOLLO_PROGRAM = 10, PROJECT_SS_BOOSTER = 11, PROJECT_SS_COCKPIT = 12,
                  PROJECT_SS_STASIS_CHAMBER = 13, PROJECT_SS_ENGINE = 14 }
PreGame = { IsVictory = function(id) return not OFF[id] end }
CIVS = {}                -- per civilization: capitals (original capitals in its hands), lost, dead, projects, votes
local function civ(i, name)
  CIVS[i] = { influential_on = 0, capitals = 1, projects = {}, votes = 0 }
  local c = CIVS[i]
  return { IsAlive = function() return not c.dead end, IsEverAlive = function() return true end,
           IsMinorCiv = function() return false end, GetTeam = function() return i end,
           IsHasLostCapital = function() return c.lost or false end,
           Cities = function()
             local n = 0
             return function()
               n = n + 1
               if n <= c.capitals then return { IsOriginalMajorCapital = function() return true end } end
               if n == c.capitals + 1 then return { IsOriginalMajorCapital = function() return false end } end
             end
           end,
           GetCivilizationShortDescriptionKey = function() return name end,
           GetCivilizationShortDescription = function() return name end,
           GetNumCivsInfluentialOn = function() return c.influential_on end,
           GetNumCivsToBeInfluentialOn = function() return 3 end,
           GetTourism = function() return 100 end, GetInfluenceLevel = function() return 1 end,
           GetJONSCultureEverGenerated = function() return 50000 end, GetInfluenceOn = function() return 11000 end,
           GetInfluencePerTurn = function() return 100 end, GetInfluenceTrend = function() return 2 end,
           GetTurnsToInfluential = function() return 40 end }
end
Players = { [0] = civ(0, 'Germany'), [1] = civ(1, 'America'), [2] = civ(2, 'The Huns'), [3] = civ(3, 'The Celts') }
MET = { [0] = true, [1] = true, [3] = true }   -- a team has met itself; the Huns are not met
Teams = {}
for i = 0, 3 do
  Teams[i] = { IsHasMet = function(_, t) return MET[t] or false end,
               GetProjectCount = function(_, proj) return CIVS[i].projects[proj] or 0 end }
end
LEAGUES, UN, NEEDED = 0, false, 20
Game.IsUnitedNationsActive = function() return UN end
Game.GetNumActiveLeagues = function() return LEAGUES end
Game.GetVotesNeededForDiploVictory = function() return NEEDED end
Game.GetActiveLeague = function()
  return { IsMember = function() return true end,
           CalculateStartingVotesForMember = function(_, i) return CIVS[i].votes end,
           GetTurnsUntilVictorySession = function() return 7 end }
end
function progress() return H.victory_progress(0) end
function row(n) return progress().civs[n] end
"""


class VictoryProgressLuaTests(unittest.TestCase):
    run_lua = support.LuaRuntimeTests.run_lua

    def setUp(self):
        support.LuaRuntimeTests.setUp(self)
        self.run_lua(WORLD)

    def test_the_seat_comes_first_and_an_unmet_civilization_last_without_a_name(self):
        self.run_lua("""
        local civs = progress().civs
        assert(#civs == 4, H.json(civs))
        assert(civs[1].civ == 'Germany' and civs[1].you == true and civs[1].player == 0, H.json(civs[1]))
        assert(civs[2].civ == 'America' and civs[2].player == 1 and civs[3].civ == 'The Celts', H.json(civs))
        assert(civs[4].civ == 'an unmet civilization' and civs[4].player == nil and civs[4].you == nil, H.json(civs[4]))
        """)

    def test_who_holds_their_own_capital_and_how_many_original_capitals(self):
        self.run_lua("""
        CIVS[1].capitals = 2; CIVS[3].capitals = 0; CIVS[3].lost = true
        assert(row(2).own_capital == 'held' and row(2).original_capitals_held == 2, H.json(row(2)))
        assert(row(3).own_capital == 'lost' and row(3).original_capitals_held == 0, H.json(row(3)))
        assert(row(4).own_capital == 'held' and row(4).original_capitals_held == 1, 'the screen shows an unmet player\\'s: ' .. H.json(row(4)))
        assert(progress().needs.domination:find('last player holding their own original capital', 1, true))
        """)

    def test_a_destroyed_civilization_is_a_row_with_nothing_in_it(self):
        self.run_lua("""
        CIVS[3].dead = true
        local celts = row(3)
        assert(celts.destroyed == true and celts.own_capital == nil and celts.spaceship_parts == nil, H.json(celts))
        assert(row(2).destroyed == nil, H.json(row(2)))
        """)

    def test_the_space_race_of_every_civilization(self):
        self.run_lua("""
        CIVS[1].projects = { [10] = 1, [11] = 5, [12] = 1 }
        CIVS[2].projects = { [10] = 1, [13] = 1 }
        assert(row(2).apollo == true and row(2).spaceship_parts == 4, 'a part counts to its number: ' .. H.json(row(2)))
        assert(row(4).apollo == true and row(4).spaceship_parts == 1, 'an unmet civilization is in the list: ' .. H.json(row(4)))
        assert(row(1).apollo == false and row(1).spaceship_parts == 0, H.json(row(1)))
        assert(progress().needs.spaceship_parts == 6, 'Apollo is no part: ' .. H.json(progress().needs))
        """)

    def test_influence_is_the_culture_overviews_and_so_of_met_civilizations_only(self):
        self.run_lua("""
        CIVS[0].influential_on = 1; CIVS[1].influential_on = 2; CIVS[2].influential_on = 2
        assert(row(1).influential_on == 1 and row(1).influential_needed == 3, H.json(row(1)))
        assert(row(2).influential_on == 2 and row(2).influential_needed == 3, H.json(row(2)))
        assert(row(4).influential_on == nil and row(4).influential_needed == nil, H.json(row(4)))
        """)

    def test_delegates_once_there_is_a_world_congress(self):
        self.run_lua("""
        CIVS[0].votes = 3; CIVS[1].votes = 9; CIVS[2].votes = 4
        local p = progress()
        assert(p.civs[2].delegates == nil, 'no World Congress, no delegates: ' .. H.json(p.civs[2]))
        assert(p.needs.delegates == 20 and p.needs.diplomatic:find('no World Congress yet', 1, true), H.json(p.needs))
        LEAGUES = 1
        p = progress()
        assert(p.civs[1].delegates == 3 and p.civs[2].delegates == 9, H.json(p.civs))
        assert(p.civs[4].delegates == 4, 'the member column lists an unmet member: ' .. H.json(p.civs[4]))
        assert(p.needs.diplomatic:find('none before the United Nations', 1, true), H.json(p.needs))
        assert(p.needs.turns_until_world_leader_vote == nil, H.json(p.needs))
        UN = true
        p = progress()
        assert(p.needs.turns_until_world_leader_vote == 7 and p.needs.diplomatic == '20 delegates in a World Leader vote', H.json(p.needs))
        """)

    def test_a_victory_the_game_does_not_allow_has_no_column(self):
        self.run_lua("""
        LEAGUES = 1
        OFF[2] = true; OFF[3] = true
        local p = progress()
        assert(p.civs[2].apollo == nil and p.civs[2].spaceship_parts == nil and p.civs[2].delegates == nil, H.json(p.civs[2]))
        assert(p.needs.science == nil and p.needs.diplomatic == nil and p.needs.delegates == nil, H.json(p.needs))
        assert(p.civs[2].own_capital == 'held' and p.civs[2].influential_needed == 3, H.json(p.civs[2]))
        """)

    def test_a_victory_switched_off_after_the_game_was_hosted_has_no_column(self):
        self.run_lua("""
        Game.IsVictoryValid = function(id) return id ~= 4 end
        local p = progress()
        assert(p.civs[1].own_capital == nil and p.needs.domination == nil, H.json(p))
        """)


PROGRESS = {"civs": [{"civ": "Poland", "player": 0, "you": True, "own_capital": "held", "original_capitals_held": 1},
                     {"civ": "an unmet civilization", "own_capital": "held", "original_capitals_held": 2}],
            "needs": {"domination": "to be the last player holding their own original capital"}}


class VictoryProgressBriefingTests(unittest.TestCase):
    def briefing(self, include_rules: bool) -> dict:
        ts = {"turn": 120, "todo": {"units": [], "cities": []}, "blocking_name": "NO_ENDTURN_BLOCKING_TYPE",
              "pending_popups": []}
        board = {"event_seq": 1, "threats": [], "camps": [], "victory_progress": PROGRESS}
        out, _snap = build(ts, {}, [], [], board, {"comparable": False}, None, [], limit=8, include_rules=include_rules)
        return out

    def test_the_briefing_that_opens_an_instance_carries_the_table(self):
        table = self.briefing(include_rules=True)["victory_progress"]
        self.assertEqual(table["civs"], PROGRESS["civs"])
        self.assertEqual(table["needs"], PROGRESS["needs"])
        self.assertIn("Victory Progress screen", table["note"])

    def test_a_briefing_inside_an_instance_does_not_repeat_it(self):
        self.assertNotIn("victory_progress", self.briefing(include_rules=False))


if __name__ == "__main__":
    unittest.main()
