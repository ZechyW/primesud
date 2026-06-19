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
from magic import obj_cast_spell, cast_item_spells
from item import serialize_item_token, parse_item_token
from player import create_char
from world import ITEM_TEMPLATES, MOB_TEMPLATES, init_world

init_world()


class FakeTerminal:
    def __init__(self):
        self.lines = []

    def print(self, text=""):
        self.lines.append(text)


def world_stub(room=3700):
    return {"rooms": {room: {"mobs": [], "items": []}}, "mobs": {}}


def add_mob(world, room, tpl_vnum=None, hp=30):
    if tpl_vnum is None:
        tpl_vnum = next(iter(MOB_TEMPLATES))
    mob_id = 1
    inst = {
        "is_npc": True,
        "tpl": tpl_vnum,
        "room": room,
        "level": 1,
        "hp": hp,
        "hp_max": hp,
        "AC": 100,
        "wait": 0,
        "daze": 0,
        "state": "idle",
        "fighting": None,
        "affects": {},
        "affect_list": [],
        "mod_stat": {},
        "saving_throw": 0,
        "equip": {},
        "inv": [],
        "off_flags": {},
    }
    world["mobs"][mob_id] = inst
    world["rooms"][room]["mobs"].append(mob_id)
    return mob_id, inst


def first_item_vnum(item_type):
    for vnum, tpl in ITEM_TEMPLATES.items():
        if tpl.get("type") == item_type:
            return vnum
    raise AssertionError(item_type)


class MagicPhase5aTest(unittest.TestCase):
    def test_item_token_round_trip_keeps_mutable_magic_state(self):
        obj = {
            "vnum": 5001,
            "cost": 1200,
            "charges": 2,
            "max_charges": 3,
            "enchanted": True,
            "extra_flags": {"magic": True, "bless": True},
            "affect_list": [{
                "type": 42,
                "level": 20,
                "duration": 24,
                "location": "AC",
                "modifier": -20,
                "bitvector": "bless",
                "where": "obj",
            }],
        }

        token = serialize_item_token(obj)
        parsed = parse_item_token(token)

        self.assertEqual(obj["vnum"], parsed["vnum"])
        self.assertEqual(obj["cost"], parsed["cost"])
        self.assertEqual(obj["charges"], parsed["charges"])
        self.assertEqual(obj["max_charges"], parsed["max_charges"])
        self.assertTrue(parsed["enchanted"])
        self.assertEqual({"magic": True, "bless": True}, parsed["extra_flags"])
        self.assertEqual(obj["affect_list"], parsed["affect_list"])

    def test_obj_cast_spell_offensive_defaults_to_current_fighting_target(self):
        tr = FakeTerminal()
        player = create_char()
        world = world_stub(player["room"])
        mob_id, inst = add_mob(world, player["room"], hp=40)
        player["fighting"] = mob_id
        inst["fighting"] = player

        ret = obj_cast_spell(tr, "cause light", 10, player, None, None, world)

        self.assertTrue(ret)
        self.assertLess(inst["hp"], 40)

    def test_obj_cast_spell_defensive_defaults_to_self(self):
        tr = FakeTerminal()
        player = create_char()
        player["hp"] = 10
        world = world_stub(player["room"])

        ret = obj_cast_spell(tr, "cure light", 10, player, None, None, world)

        self.assertTrue(ret)
        self.assertEqual(["You feel better!"], tr.lines)
        self.assertGreater(player["hp"], 10)

    def test_obj_cast_spell_missing_object_target_fails_cleanly(self):
        tr = FakeTerminal()
        player = create_char()
        world = world_stub(player["room"])
        cure_sn = magic._skill_lookup("cure light")
        old_target = magic.SKILLS[cure_sn]["target"]
        magic.SKILLS[cure_sn]["target"] = "obj_inventory"

        try:
            ret = obj_cast_spell(tr, "cure light", 10, player, None, None, world)
        finally:
            magic.SKILLS[cure_sn]["target"] = old_target

        self.assertFalse(ret)
        self.assertEqual(["[DEV] item: target resolution failed for 'cure light'"], tr.lines)

    def test_offensive_item_cast_starts_aggro_when_target_survives(self):
        tr = FakeTerminal()
        player = create_char()
        world = world_stub(player["room"])
        mob_id, inst = add_mob(world, player["room"], hp=40)
        item_obj = {"vnum": first_item_vnum("potion")}

        ret = obj_cast_spell(tr, "cause light", 10, player, inst, None, world, item_obj)

        self.assertTrue(ret)
        self.assertEqual(mob_id, player["fighting"])
        self.assertIs(inst["fighting"], player)

    def test_cast_item_spells_fails_loud_on_bad_template_spell_name(self):
        tr = FakeTerminal()
        player = create_char()
        world = world_stub(player["room"])
        vnum = max(ITEM_TEMPLATES) + 1
        ITEM_TEMPLATES[vnum] = {
            "keywords": "bad potion",
            "short_descr": "A bad potion",
            "type": "potion",
            "spell_level": 12,
            "spells": ["not a spell"],
            "value": 10,
        }

        try:
            ret = cast_item_spells(tr, player, {"vnum": vnum, "cost": 10}, player, None, world)
        finally:
            del ITEM_TEMPLATES[vnum]

        self.assertFalse(ret)
        self.assertEqual(["[DEV] A bad potion: unknown spell 'not a spell'"], tr.lines)


if __name__ == "__main__":
    unittest.main()
