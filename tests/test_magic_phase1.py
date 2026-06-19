import os
import sys
import types
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
APPDIR = os.path.join(ROOT, "primesud.hpappdir")
if APPDIR not in sys.path:
    sys.path.insert(0, APPDIR)

if "urandom" not in sys.modules:
    urandom = types.ModuleType("urandom")
    urandom.randint = lambda lo, hi: lo
    sys.modules["urandom"] = urandom

if "hpprime" not in sys.modules:
    hpprime = types.ModuleType("hpprime")
    hpprime.eval = lambda expr: 0
    hpprime.dimgrob = lambda *args: None
    hpprime.getpix = lambda *args: 0
    hpprime.grobh = lambda *args: 0
    hpprime.grobw = lambda *args: 0
    hpprime.pixon = lambda *args: None
    hpprime.strblit2 = lambda *args: None
    sys.modules["hpprime"] = hpprime

import magic
from magic import do_cast
from player import create_char
from world import GSN_CURE_LIGHT, SKILLS
from info import do_spells
from skill_utils import spell_mana


class FakeTerminal:
    def __init__(self):
        self.lines = []

    def print(self, text=""):
        self.lines.append(text)


def world_stub(room=3700):
    return {"rooms": {room: {"mobs": [], "items": []}}, "mobs": {}}


class MagicPhase1Test(unittest.TestCase):
    def test_unknown_spell_uses_1stmud_text_and_spends_nothing(self):
        tr = FakeTerminal()
        player = create_char()
        mp = player["mp"]

        do_cast(tr, player, ["bogus"], world_stub(player["room"]))

        self.assertEqual(["You don't know any spells of that name."], tr.lines)
        self.assertEqual(mp, player["mp"])
        self.assertEqual(0, player["wait"])

    def test_unimplemented_known_spell_is_hidden_and_spends_nothing(self):
        tr = FakeTerminal()
        player = create_char()
        # cause light is level 1 and learned in the generated table, but Phase 1
        # has no runtime spell implementation yet.
        mp = player["mp"]

        do_cast(tr, player, ["cause"], world_stub(player["room"]))

        self.assertEqual(["You don't know any spells of that name."], tr.lines)
        self.assertEqual(mp, player["mp"])
        self.assertEqual(0, player["wait"])

    def test_cure_light_defaults_to_self_and_uses_dynamic_mana(self):
        tr = FakeTerminal()
        player = create_char()
        player["hp"] = 10
        player["learned"][GSN_CURE_LIGHT] = 100
        cost = spell_mana(player, GSN_CURE_LIGHT)

        do_cast(tr, player, ["cure"], world_stub(player["room"]))

        self.assertEqual(["You feel better!"], tr.lines)
        self.assertEqual(100 - cost, player["mp"])
        self.assertEqual(SKILLS[GSN_CURE_LIGHT]["beats"], player["wait"])
        self.assertGreater(player["hp"], 10)

    def test_spells_list_hides_unimplemented_spells(self):
        tr = FakeTerminal()
        player = create_char()
        player["learned"][GSN_CURE_LIGHT] = 100

        do_spells(tr, player, [], world_stub(player["room"]))

        text = "\n".join(tr.lines)
        self.assertIn("cure light", text)
        self.assertNotIn("cause light", text)

    def test_position_gate_uses_spell_minimum_position(self):
        tr = FakeTerminal()
        player = create_char()
        player["pos"] = "sleeping"
        player["learned"][GSN_CURE_LIGHT] = 100
        mp = player["mp"]

        do_cast(tr, player, ["cure"], world_stub(player["room"]))

        self.assertEqual(["You can't concentrate enough."], tr.lines)
        self.assertEqual(mp, player["mp"])

    def test_concentration_failure_spends_half_mana(self):
        tr = FakeTerminal()
        player = create_char()
        player["learned"][GSN_CURE_LIGHT] = 1
        cost = spell_mana(player, GSN_CURE_LIGHT)
        old_randint = magic.randint
        magic.randint = lambda lo, hi: hi

        try:
            do_cast(tr, player, ["cure"], world_stub(player["room"]))
        finally:
            magic.randint = old_randint

        self.assertEqual("You lost your concentration.", tr.lines[0])
        self.assertEqual(100 - cost // 2, player["mp"])


if __name__ == "__main__":
    unittest.main()
