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
import player as player_mod
from actor import equip_char, unequip_char
from player import create_char, save_char, load_char
from item import create_object
from world import ITEM_TEMPLATES, init_world
from mob import reset_area, create_area_states

init_world()


class FakeTerminal:
    def __init__(self):
        self.lines = []

    def print(self, text=""):
        self.lines.append(text)


def world_stub(room=3700):
    return {"rooms": {room: {"mobs": [], "items": []}}, "mobs": {}}


class MagicPhase5cTest(unittest.TestCase):
    def setUp(self):
        self.temp_vnums = []

    def tearDown(self):
        for vnum in self.temp_vnums:
            ITEM_TEMPLATES.pop(vnum, None)

    def add_item_tpl(self, **tpl):
        vnum = max(ITEM_TEMPLATES) + 1 + len(self.temp_vnums)
        base = {
            "keywords": "temp item",
            "short_descr": "temp item",
            "description": "temp item",
            "wear_flags": {"take": True},
            "extra_flags": {},
            "value": 10,
            "level": 1,
            "weight": 1,
            "type": "treasure",
        }
        base.update(tpl)
        ITEM_TEMPLATES[vnum] = base
        self.temp_vnums.append(vnum)
        return vnum

    def test_identify_scroll_shows_spell_payload(self):
        tr = FakeTerminal()
        player = create_char()
        world = world_stub(player["room"])
        sn = magic._skill_lookup("identify")
        vnum = self.add_item_tpl(
            keywords="scroll identify",
            short_descr="scroll identify",
            type="scroll",
            spell_level=12,
            spells=["identify", "cure light"],
            extra_flags={"magic": True},
            weight=10,
            value=890,
            level=7,
        )
        obj = create_object(vnum)

        ret = magic.spell_identify(tr, sn, player["level"], player, obj, magic.TARGET_OBJ, world)

        self.assertTrue(ret)
        text = "\n".join(tr.lines)
        self.assertIn("Object 'scroll identify' is type scroll, extra flags magic.", text)
        self.assertIn("Level 12 spells of: 'identify' 'cure light'.", text)

    def test_identify_wand_shows_charge_payload(self):
        tr = FakeTerminal()
        player = create_char()
        world = world_stub(player["room"])
        sn = magic._skill_lookup("identify")
        vnum = self.add_item_tpl(
            keywords="wand missile",
            short_descr="wand missile",
            type="wand",
            spell_level=4,
            spell="magic missile",
            charges=7,
            max_charges=10,
            extra_flags={"magic": True},
        )
        obj = create_object(vnum)
        obj["charges"] = 7
        obj["max_charges"] = 10

        magic.spell_identify(tr, sn, player["level"], player, obj, magic.TARGET_OBJ, world)

        self.assertIn("Has 7 charges of level 4 'magic missile'.", tr.lines)

    def test_detect_poison_matches_food_and_other_object_text(self):
        tr = FakeTerminal()
        player = create_char()
        world = world_stub(player["room"])
        sn = magic._skill_lookup("detect poison")
        food_vnum = self.add_item_tpl(
            keywords="apple",
            short_descr="apple",
            type="food",
            poisoned=False,
        )
        orb_vnum = self.add_item_tpl(
            keywords="orb",
            short_descr="orb",
            type="treasure",
        )

        magic.spell_detect_poison(tr, sn, player["level"], player, create_object(food_vnum), magic.TARGET_OBJ, world)
        magic.spell_detect_poison(tr, sn, player["level"], player, create_object(orb_vnum), magic.TARGET_OBJ, world)

        self.assertEqual("It looks delicious.", tr.lines[0])
        self.assertEqual("It doesn't look poisoned.", tr.lines[1])

    def test_bless_object_adds_flag_and_affect(self):
        tr = FakeTerminal()
        player = create_char()
        world = world_stub(player["room"])
        sn = magic._skill_lookup("bless")
        vnum = self.add_item_tpl(
            keywords="ring",
            short_descr="ring",
            type="treasure",
        )
        obj = create_object(vnum)

        ret = magic.spell_bless(tr, sn, 20, player, obj, magic.TARGET_OBJ, world)

        self.assertTrue(ret)
        self.assertTrue(obj["extra_flags"]["bless"])
        self.assertEqual("obj", obj["affect_list"][0]["where"])
        self.assertEqual("ring glows with a holy aura.", tr.lines[0])

    def test_curse_object_strips_bless_when_dispel_wins(self):
        tr = FakeTerminal()
        player = create_char()
        world = world_stub(player["room"])
        bless_sn = magic._skill_lookup("bless")
        curse_sn = magic._skill_lookup("curse")
        vnum = self.add_item_tpl(
            keywords="amulet",
            short_descr="amulet",
            type="treasure",
        )
        obj = create_object(vnum)
        old_randint = magic.randint
        magic.randint = lambda lo, hi: hi
        try:
            magic.spell_bless(tr, bless_sn, 20, player, obj, magic.TARGET_OBJ, world)
            ret = magic.spell_curse(tr, curse_sn, 20, player, obj, magic.TARGET_OBJ, world)
        finally:
            magic.randint = old_randint

        self.assertTrue(ret)
        self.assertFalse(obj.get("extra_flags", {}).get("bless"))
        self.assertFalse(obj.get("affect_list"))
        self.assertEqual("amulet glows with a red aura.", tr.lines[-1])

    def test_fireproof_adds_burn_proof_flag(self):
        tr = FakeTerminal()
        player = create_char()
        world = world_stub(player["room"])
        sn = magic._skill_lookup("fireproof")
        vnum = self.add_item_tpl(
            keywords="cloak",
            short_descr="cloak",
            type="armor",
        )
        obj = create_object(vnum)

        ret = magic.spell_fireproof(tr, sn, 20, player, obj, magic.TARGET_OBJ, world)

        self.assertTrue(ret)
        self.assertTrue(obj["extra_flags"]["burn_proof"])
        self.assertEqual("You protect cloak from fire.", tr.lines[0])

    def test_enchant_armor_survives_save_load_and_applies_on_equip_cycle(self):
        tr = FakeTerminal()
        player = create_char()
        player["_macros"] = {}
        world_rooms, world_mobs = reset_area()
        world = {"rooms": world_rooms, "mobs": world_mobs, "areas": create_area_states()}
        sn = magic._skill_lookup("enchant armor")
        vnum = self.add_item_tpl(
            keywords="mail",
            short_descr="mail",
            type="armor",
            wear_flags={"take": True, "body": True},
            level=5,
            value=100,
        )
        obj = create_object(vnum)
        player["inv"].append(obj)
        old_randint = magic.randint
        store = {}
        player_mod.hvars_set = lambda name, value: store.__setitem__(name, value)
        player_mod.hvars_get = lambda name: store.get(name, "Error: Invalid input")
        magic.randint = lambda lo, hi: hi
        try:
            ret = magic.spell_enchant_armor(tr, sn, 20, player, obj, magic.TARGET_OBJ, world)
            base_ac = player["AC"]
            equip_char(player, obj, "body")
            equipped_ac = player["AC"]
            unequip_char(player, "body")
            save_char(player, world)
            loaded_player = create_char()
            loaded_player["_macros"] = {}
            loaded_world = {"rooms": world_rooms, "mobs": world_mobs, "areas": create_area_states()}
            load_char(loaded_player, loaded_world)
        finally:
            magic.randint = old_randint

        self.assertTrue(ret)
        self.assertLess(equipped_ac, base_ac)
        self.assertEqual(base_ac, player["AC"])
        self.assertEqual(obj["affect_list"], loaded_player["inv"][0]["affect_list"])
        self.assertTrue(loaded_player["inv"][0]["extra_flags"]["magic"])

    def test_enchant_weapon_applies_hit_and_damroll_and_persists(self):
        tr = FakeTerminal()
        player = create_char()
        world = world_stub(player["room"])
        sn = magic._skill_lookup("enchant weapon")
        vnum = self.add_item_tpl(
            keywords="blade",
            short_descr="blade",
            type="weapon",
            wear_flags={"take": True, "wield": True},
            weapon_type="sword",
            weapon_flags={},
            level=5,
            value=100,
        )
        obj = create_object(vnum)
        player["inv"].append(obj)
        old_randint = magic.randint
        magic.randint = lambda lo, hi: hi
        try:
            ret = magic.spell_enchant_weapon(tr, sn, 20, player, obj, magic.TARGET_OBJ, world)
            base_hit = player["hitroll"]
            base_dam = player["damroll"]
            equip_char(player, obj, "wield")
            equipped_hit = player["hitroll"]
            equipped_dam = player["damroll"]
        finally:
            magic.randint = old_randint

        self.assertTrue(ret)
        self.assertGreater(equipped_hit, base_hit)
        self.assertGreater(equipped_dam, base_dam)
        self.assertTrue(obj["extra_flags"]["magic"])
        self.assertEqual(2, len(obj["affect_list"]))


if __name__ == "__main__":
    unittest.main()
