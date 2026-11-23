"""No turn passes unplayed while a rival is close to a victory (runtime v344, the user's decision of 2026-11-23).

Live, Germany t325: the briefing had said America needed one more civilization for a Culture victory, and a
skip_quiet_turns=9 run went through the turn the victory landed on. The status now lists the rivals that are close
(`victory_watch`), a run of quiet turns stops on every turn one is listed, and the reply says why.
"""
import unittest

import test_mcp_safety as support
from harness.briefing import build
from test_finish_turn import QUIET, ScriptedGame, status


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
CIVS = {}                                  -- per civilization: influential_on, needed, level, projects, votes, lost, dead, ever
local function civ(i, name)
  CIVS[i] = { influential_on = 0, needed = 3, level = 1, projects = {}, votes = 0 }
  local c = CIVS[i]
  return { IsAlive = function() return not c.dead end, IsEverAlive = function() return true end,
           IsMinorCiv = function() return false end, GetTeam = function() return i end,
           IsHasLostCapital = function() return c.lost or false end,
           GetCivilizationShortDescriptionKey = function() return name end,
           GetCivilizationShortDescription = function() return name end,
           GetNumCivsInfluentialOn = function() return c.influential_on end,
           GetNumCivsToBeInfluentialOn = function() return c.needed end,
           GetTourism = function() return 100 end, GetInfluenceLevel = function() return c.level end,
           GetJONSCultureEverGenerated = function() return 50000 end, GetInfluenceOn = function() return 11000 end,
           GetInfluencePerTurn = function() return 100 end, GetInfluenceTrend = function() return 2 end,
           GetTurnsToInfluential = function() return 40 end }
end
Players = { [0] = civ(0, 'Germany'), [1] = civ(1, 'America'), [2] = civ(2, 'The Huns'), [3] = civ(3, 'The Celts') }
MET = { [1] = true, [2] = true, [3] = true }
Teams = {}
for i = 0, 3 do
  Teams[i] = { IsHasMet = function(_, t) return MET[t] or false end,
               GetProjectCount = function(_, proj) return CIVS[i].projects[proj] or 0 end }
end
UN, NEEDED = false, 20
Game.IsUnitedNationsActive = function() return UN end
Game.GetNumActiveLeagues = function() return 1 end
Game.GetVotesNeededForDiploVictory = function() return NEEDED end
Game.GetActiveLeague = function()
  return { IsMember = function() return true end,
           CalculateStartingVotesForMember = function(_, i) return CIVS[i].votes end,
           GetTurnsUntilVictorySession = function() return 7 end }
end
function watch() return H.victory_watch(0) end
function only(kind)
  local rows = {}
  for _, r in ipairs(watch()) do if r.victory == kind then rows[#rows + 1] = r end end
  return rows
end
"""


class VictoryWatchLuaTests(unittest.TestCase):
    run_lua = support.LuaRuntimeTests.run_lua

    def setUp(self):
        support.LuaRuntimeTests.setUp(self)
        self.run_lua(WORLD)

    def test_nobody_close_lists_nothing(self):
        self.run_lua("assert(#watch() == 0, H.json(watch()))")

    def test_one_civilization_short_of_a_culture_victory(self):
        self.run_lua("""
        CIVS[1].influential_on = 2
        local rows = watch()
        assert(#rows == 1 and rows[1].victory == 'culture' and rows[1].civ == 'America' and rows[1].player == 1, H.json(rows))
        assert(rows[1].influential_on == 2 and rows[1].needed == 3, H.json(rows))
        assert(rows[1].note:find('influential on 2 of the 3', 1, true), rows[1].note)
        CIVS[1].influential_on = 1
        assert(#watch() == 0, 'two short is not close')
        """)

    def test_two_civilizations_left_are_not_always_one_short(self):
        # With one rival alive `needed` is 1 and `influential_on` 0 from the first turn: that is a duel, not a threat,
        # until the rival is popular with the civilization it lacks.
        self.run_lua("""
        CIVS[1].needed = 1
        assert(#watch() == 0, H.json(watch()))
        CIVS[1].level = 2
        local rows = watch()
        assert(#rows == 1 and rows[1].victory == 'culture', H.json(rows))
        """)

    def test_my_own_progress_and_an_unmet_civilization_are_not_listed(self):
        self.run_lua("""
        CIVS[0].influential_on = 2
        CIVS[2].influential_on = 2
        MET[2] = nil
        assert(#watch() == 0, H.json(watch()))
        """)

    def test_half_the_spaceship_in_the_ship(self):
        self.run_lua("""
        CIVS[2].projects = { [11] = 3 }
        assert(#watch() == 0, 'parts without Apollo are not a ship')
        CIVS[2].projects = { [10] = 1, [11] = 2 }
        assert(#watch() == 0, 'two of six is not half')
        CIVS[2].projects = { [10] = 1, [11] = 5, [12] = 0 }
        local rows = watch()
        assert(#rows == 1 and rows[1].victory == 'science' and rows[1].civ == 'The Huns', H.json(rows))
        assert(rows[1].parts_in_ship == 3 and rows[1].parts_needed == 6, 'Apollo is no part and a part counts to its number: ' .. H.json(rows))
        """)

    def test_four_fifths_of_the_delegates_once_the_united_nations_sits(self):
        self.run_lua("""
        CIVS[3].votes = 16
        assert(#watch() == 0, 'no United Nations, no World Leader vote')
        UN = true
        local rows = watch()
        assert(#rows == 1 and rows[1].victory == 'diplomatic' and rows[1].civ == 'The Celts', H.json(rows))
        assert(rows[1].delegates == 16 and rows[1].needed == 20 and rows[1].turns_until_world_leader_vote == 7, H.json(rows))
        CIVS[3].votes = 15
        assert(#watch() == 0, 'fifteen of twenty is not four fifths')
        """)

    def test_the_last_two_holding_their_own_capital(self):
        self.run_lua("""
        CIVS[2].lost = true
        assert(#watch() == 0, 'three still hold theirs')
        CIVS[3].dead = true
        local rows = watch()
        assert(#rows == 1 and rows[1].victory == 'domination' and rows[1].civ == 'America', H.json(rows))
        assert(rows[1].last_capital_mine == true and rows[1].note:find('takes yours', 1, true), H.json(rows))
        CIVS[0].lost = true; CIVS[2].lost = false
        rows = only('domination')
        assert(#rows == 2, 'both of the last two are close when neither is me: ' .. H.json(rows))
        """)

    def test_a_duel_is_not_a_domination_threat_from_its_first_turn(self):
        self.run_lua("""
        Players[2], Players[3] = nil, nil
        assert(#watch() == 0, H.json(watch()))
        """)

    def test_a_victory_the_game_does_not_allow_is_not_listed(self):
        self.run_lua("""
        CIVS[1].influential_on = 2
        CIVS[2].projects = { [10] = 1, [11] = 3 }
        UN = true; CIVS[3].votes = 20
        assert(#watch() == 3, H.json(watch()))
        OFF[1] = true; OFF[3] = true
        local rows = watch()
        assert(#rows == 1 and rows[1].victory == 'science', H.json(rows))
        """)


WATCH = [{"victory": "culture", "player": 1, "civ": "America", "influential_on": 4, "needed": 5,
          "note": "America is influential on 4 of the 5 civilizations a Culture victory needs"}]


class QuietTurnsHeldTests(unittest.TestCase):
    def test_no_quiet_turn_passes_while_a_rival_is_close(self):
        g = ScriptedGame([(status(2, victory_watch=WATCH), QUIET), (status(3, victory_watch=WATCH), QUIET)])
        r = g.finish_turn(skip_quiet_turns=9)
        self.assertEqual((r["turn"], r["turns_skipped"]), (2, 0))
        self.assertEqual(r["woke_because"], ["rival_close_to_victory:America:culture"])
        self.assertEqual(g.log.count("end"), 1, "only the caller's own turn was ended")
        self.assertIn("passes no turn while a rival is close to a victory", r["quiet_turns_held"])
        self.assertIn("America is influential on 4 of the 5", r["quiet_turns_held"])

    def test_a_run_stops_on_the_turn_a_rival_becomes_close(self):
        g = ScriptedGame([(status(2), QUIET), (status(3), QUIET), (status(4, victory_watch=WATCH), QUIET),
                          (status(5, victory_watch=WATCH), QUIET)])
        r = g.finish_turn(skip_quiet_turns=9)
        self.assertEqual((r["turn"], r["turns_skipped"]), (4, 2))
        self.assertEqual(r["woke_because"], ["rival_close_to_victory:America:culture"])

    def test_a_plain_finish_names_the_rival_and_is_told_nothing_of_quiet_turns(self):
        g = ScriptedGame([(status(2, victory_watch=WATCH), QUIET)])
        r = g.finish_turn()
        self.assertEqual(r["woke_because"], ["rival_close_to_victory:America:culture"])
        self.assertNotIn("quiet_turns_held", r)

    def test_the_run_goes_on_once_nobody_is_close(self):
        g = ScriptedGame([(status(2), QUIET), (status(3), QUIET), (status(4), QUIET)])
        r = g.finish_turn(skip_quiet_turns=2)
        self.assertEqual((r["turn"], r["turns_skipped"]), (4, 2))
        self.assertNotIn("quiet_turns_held", r)


class VictoryThreatWarningTests(unittest.TestCase):
    def test_the_briefing_warns_of_a_rival_close_to_another_victory(self):
        ts = {"turn": 280, "todo": {"units": [], "cities": []}, "blocking_name": "NO_ENDTURN_BLOCKING_TYPE",
              "pending_popups": [],
              "victory_watch": WATCH + [{"victory": "science", "player": 2, "civ": "The Huns", "parts_in_ship": 4,
                                         "parts_needed": 6, "note": "The Huns has 4 of the 6 spaceship parts in its ship"}]}
        board = {"event_seq": 1, "threats": [], "camps": []}
        out, _snap = build(ts, {}, [], [], board, {"comparable": False}, None, [], limit=8, include_rules=False)
        rows = [w for w in out.get("warnings", []) if w["kind"] == "victory_threat"]
        self.assertEqual(len(rows), 1, "the Culture row is the culture_victory_threat warning's")
        self.assertEqual(rows[0]["civ"], "The Huns")
        self.assertIn("close to a Science victory", rows[0]["note"])


if __name__ == "__main__":
    unittest.main()
