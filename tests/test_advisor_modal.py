"""An attack the game's own Military Advisor asks about is refused with the advisor's sentence, and confirm makes it.

Live 2026-11-23, the duel on duel-king-rome-huns-a, turn 106: Sonnet ordered a Warrior onto a Hun Pikeman. The game
raised its confirmation screen (advisormodal.lua, BUTTONPOPUP_ADVISOR_MODAL: "We may want to reconsider this attack;
you will do marginal damage to your opponent and they will do considerable damage to you", Attack anyway / Cancel).
Nothing in the harness answered it: `question()` said nothing was asked, every later order and the end of the turn
were refused, and three instances in a row gave the turn up until the screen was closed by hand.
"""
import unittest

import test_mcp_safety as support
from harness.game import Game

SAID = "We may want to reconsider this attack; you will do marginal damage to your opponent and they will do considerable damage to you."


class FakeGame(Game):
    """A melee attack onto (6, 11). `modal`: the screen comes up unless the engine was told the seat is warned."""

    def __init__(self, modal=True):
        self.seat = 0
        self.modal = modal
        self.warned = False
        self.calls: list[str] = []

    def q(self, lua, *a, **kw):
        self.calls.append(lua)
        if "H.attack_before" in lua:
            return {"attack": True, "def_player": 1, "def_unit": 55, "def_hp": 100, "my_hp": 100,
                    "defender": {"unit": "PIKEMAN", "owner": "The Huns", "x": 6, "y": 11, "hp": 100, "max_hp": 100}}
        if "H.combat_warned(true" in lua:
            self.warned = True
            return {"ok": True, "warned": True}
        if "H.combat_warned(false" in lua:
            self.warned = False
            return {"ok": True, "warned": False}
        if "H.advisor_modal(true" in lua:
            return {"up": True, "text": SAID, "closed": True} if self.modal else {"up": False}
        if "H.attack_after" in lua:
            return {"def_hp": 70, "my_hp": 60, "def_killed": False, "my_unit_killed": False}
        if "H.captured_at" in lua:
            return None
        return {"ok": True}

    def _move_unit(self, unit_id, x, y, pid=None, settle_timeout=1.0):
        self.calls.append(f"move {unit_id} {x} {y} warned={self.warned}")
        if self.modal and not self.warned:
            return {"ok": False, "err": "unit did not move", "x": 5, "y": 11, "moves": 2}
        return {"ok": True, "x": 5, "y": 11, "moves": 0}

    def _refused_attack(self, r, pre, unit_id, x, y, pid):
        r["refused_attack"] = True

    def _refusal_names_successor(self, r, unit_id, pid):
        return r


class AdvisorStoppedTests(unittest.TestCase):
    def test_the_attack_is_refused_with_the_advisors_sentence_and_the_screen_is_closed(self):
        g = FakeGame()
        r = g.move_unit(17, 6, 11)
        self.assertFalse(r["ok"])
        self.assertEqual(r["advisor"], SAID)
        self.assertTrue(r["advisor_screen_closed"])
        self.assertIn("the game's Military Advisor stopped this attack and asks for a confirmation: " + SAID, r["err"])
        self.assertIn("args.confirm=true attacks anyway", r["err"])
        self.assertEqual(r["moves"], 2, "the unit keeps its moves")
        self.assertTrue(any("H.advisor_modal(true" in c for c in g.calls))
        self.assertFalse(any("H.combat_warned" in c for c in g.calls), "nothing is set without confirm")

    def test_confirm_makes_the_attack_as_the_screens_own_button_does_and_clears_the_flag(self):
        g = FakeGame()
        r = g.move_unit(17, 6, 11, confirm=True)
        self.assertTrue(r["ok"])
        self.assertIn("move 17 6 11 warned=True", g.calls)
        self.assertFalse(g.warned, "the flag is for this one order")
        self.assertNotIn("advisor", r)

    def test_an_attack_the_game_does_not_ask_about_is_untouched(self):
        g = FakeGame(modal=False)
        r = g.move_unit(17, 6, 11)
        self.assertTrue(r["ok"])
        self.assertFalse(any("H.advisor_modal" in c for c in g.calls), "a made attack reads no screen")

    def test_a_refusal_with_no_screen_up_stays_the_refusal_it_was(self):
        class Dropped(FakeGame):
            def _move_unit(self, unit_id, x, y, pid=None, settle_timeout=1.0):
                return {"ok": False, "err": "unit did not move", "x": 5, "y": 11, "moves": 2}
        g = Dropped(modal=False)
        r = g.move_unit(17, 6, 11)
        self.assertFalse(r["ok"])
        self.assertNotIn("advisor", r)
        self.assertTrue(r.get("refused_attack"))


class AdvisorModalLuaTests(unittest.TestCase):
    run_lua = support.LuaRuntimeTests.run_lua

    def setUp(self):
        support.LuaRuntimeTests.setUp(self)
        self.run_lua("""
        HIDDEN, DEQUEUED, WARNED = true, 0, nil
        local labels = { ['/InGame/AdvisorModal/DescriptionLabel'] = 'We may want to reconsider this attack.',
                         ['/InGame/AdvisorModal/TitleLabel'] = 'Bad Attack' }
        MODAL = { IsHidden = function() return HIDDEN end }
        ContextPtr = { LookUpControl = function(_, path)
          if path == '/InGame/AdvisorModal' then return MODAL end
          local text = labels[path]
          return text and { GetText = function() return text end } or nil
        end }
        UIManager = { DequeuePopup = function(_, ctx) assert(ctx == MODAL); DEQUEUED = DEQUEUED + 1; HIDDEN = true end }
        Game.SetCombatWarned = function(on) WARNED = on end
        """)

    def test_no_screen_up_reads_as_none_and_closes_nothing(self):
        self.run_lua("""
        local m = H.advisor_modal(true, 0)
        assert(m.up == false and m.text == nil and DEQUEUED == 0, H.json(m))
        """)

    def test_the_screen_is_read_and_cancelled_only_when_asked(self):
        self.run_lua("""
        HIDDEN = false
        local m = H.advisor_modal(false, 0)
        assert(m.up == true and m.text == 'We may want to reconsider this attack.' and m.title == 'Bad Attack', H.json(m))
        assert(m.closed == nil and DEQUEUED == 0, H.json(m))
        m = H.advisor_modal(true, 0)
        assert(m.up == true and m.closed == true and DEQUEUED == 1, H.json(m))
        assert(H.advisor_modal(true, 0).up == false)
        """)

    def test_the_warned_flag_is_the_engines(self):
        self.run_lua("""
        assert(H.combat_warned(true, 0).warned == true and WARNED == true)
        assert(H.combat_warned(false, 0).warned == false and WARNED == false)
        """)


if __name__ == "__main__":
    unittest.main()
