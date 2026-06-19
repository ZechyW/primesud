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

import inventory
from inventory import do_quaff, do_recite, do_zap, do_brandish
from player import create_char
from item import create_object
from skills_table import GSN_SCROLLS, GSN_STAVES, GSN_WANDS
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
    mob_id = 1 if not world["mobs"] else max(world["mobs"]) + 1
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


class MagicPhase5bTest(unittest.TestCase):
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
        }
        base.update(tpl)
        ITEM_TEMPLATES[vnum] = base
        self.temp_vnums.append(vnum)
        return vnum

    def test_quaff_potion_self_cast_consumes_item(self):
        tr = FakeTerminal()
        player = create_char()
        world = world_stub(player["room"])
        vnum = self.add_item_tpl(
            keywords="healpot potion",
            short_descr="healing potion",
            type="potion",
            wear_flags={"take": True, "hold": True},
            spell_level=5,
            spells=["cure light"],
        )
        obj = create_object(vnum)
        player["inv"].append(obj)

        do_quaff(tr, player, ["healpot"], world)

        self.assertEqual(["You quaff healing potion.", "You feel better!"], tr.lines)
        self.assertEqual([], player["inv"])

    def test_recite_defaults_to_self(self):
        tr = FakeTerminal()
        player = create_char()
        player["learned"][GSN_SCROLLS] = 100
        world = world_stub(player["room"])
        vnum = self.add_item_tpl(
            keywords="scroll heal",
            short_descr="healing scroll",
            type="scroll",
            spell_level=5,
            spells=["cure light"],
        )
        scroll = create_object(vnum)
        player["inv"].append(scroll)
        seen = []
        old_cast = inventory.cast_item_spells
        inventory.cast_item_spells = lambda tr, ch, item_obj, victim, obj, world: seen.append((victim, obj)) or True

        try:
            do_recite(tr, player, ["scroll"], world)
        finally:
            inventory.cast_item_spells = old_cast

        self.assertIs(seen[0][0], player)
        self.assertIsNone(seen[0][1])
        self.assertEqual([], player["inv"])

    def test_recite_explicit_object_target_routes_object(self):
        tr = FakeTerminal()
        player = create_char()
        player["learned"][GSN_SCROLLS] = 100
        world = world_stub(player["room"])
        scroll_vnum = self.add_item_tpl(
            keywords="scroll utility",
            short_descr="utility scroll",
            type="scroll",
            spell_level=5,
            spells=["cure light"],
        )
        target_vnum = self.add_item_tpl(
            keywords="orb test",
            short_descr="test orb",
            type="treasure",
        )
        scroll = create_object(scroll_vnum)
        target = create_object(target_vnum)
        player["inv"].append(scroll)
        world["rooms"][player["room"]]["items"].append(target)
        seen = []
        old_cast = inventory.cast_item_spells
        inventory.cast_item_spells = lambda tr, ch, item_obj, victim, obj, world: seen.append((victim, obj)) or True

        try:
            do_recite(tr, player, ["scroll", "orb"], world)
        finally:
            inventory.cast_item_spells = old_cast

        self.assertIsNone(seen[0][0])
        self.assertIs(seen[0][1], target)

    def test_zap_defaults_to_current_fighting_target(self):
        tr = FakeTerminal()
        player = create_char()
        player["learned"][GSN_WANDS] = 100
        world = world_stub(player["room"])
        mob_id, mob = add_mob(world, player["room"])
        player["fighting"] = mob_id
        vnum = self.add_item_tpl(
            keywords="wand zap",
            short_descr="zap wand",
            type="wand",
            spell_level=10,
            spell="cause light",
            charges=2,
            max_charges=2,
        )
        wand = create_object(vnum)
        player["equip"]["hold"] = wand
        seen = []
        old_cast = inventory.cast_item_spells
        inventory.cast_item_spells = lambda tr, ch, item_obj, victim, obj, world: seen.append((victim, obj)) or True

        try:
            do_zap(tr, player, [], world)
        finally:
            inventory.cast_item_spells = old_cast

        self.assertIs(seen[0][0], mob)
        self.assertIsNone(seen[0][1])
        self.assertEqual(1, wand["charges"])

    def test_brandish_filters_defensive_vs_offensive_targets(self):
        tr = FakeTerminal()
        player = create_char()
        player["learned"][GSN_STAVES] = 100
        world = world_stub(player["room"])
        _mob1, mob1 = add_mob(world, player["room"])
        _mob2, mob2 = add_mob(world, player["room"])
        def_vnum = self.add_item_tpl(
            keywords="staff bless",
            short_descr="bless staff",
            type="staff",
            spell_level=10,
            spell="bless",
            charges=2,
            max_charges=2,
        )
        off_vnum = self.add_item_tpl(
            keywords="staff harm",
            short_descr="harm staff",
            type="staff",
            spell_level=10,
            spell="cause light",
            charges=2,
            max_charges=2,
        )
        seen = []
        old_cast = inventory.cast_item_spells
        inventory.cast_item_spells = lambda tr, ch, item_obj, victim, obj, world: seen.append(victim) or True

        try:
            player["equip"]["hold"] = create_object(def_vnum)
            do_brandish(tr, player, [], world)
            self.assertEqual([player], seen)
            seen[:] = []
            player["equip"]["hold"] = create_object(off_vnum)
            do_brandish(tr, player, [], world)
        finally:
            inventory.cast_item_spells = old_cast

        self.assertEqual([mob1, mob2], seen)

    def test_charge_depletion_removes_wand_and_staff(self):
        tr = FakeTerminal()
        player = create_char()
        player["learned"][GSN_WANDS] = 100
        player["learned"][GSN_STAVES] = 100
        world = world_stub(player["room"])
        mob_id, _mob = add_mob(world, player["room"])
        player["fighting"] = mob_id
        wand_vnum = self.add_item_tpl(
            keywords="wand one",
            short_descr="fragile wand",
            type="wand",
            spell_level=10,
            spell="cause light",
            charges=1,
            max_charges=1,
        )
        staff_vnum = self.add_item_tpl(
            keywords="staff one",
            short_descr="fragile staff",
            type="staff",
            spell_level=10,
            spell="bless",
            charges=1,
            max_charges=1,
        )
        old_cast = inventory.cast_item_spells
        inventory.cast_item_spells = lambda tr, ch, item_obj, victim, obj, world: True

        try:
            player["equip"]["hold"] = create_object(wand_vnum)
            do_zap(tr, player, [], world)
            self.assertIsNone(player["equip"]["hold"])
            player["equip"]["hold"] = create_object(staff_vnum)
            do_brandish(tr, player, [], world)
            self.assertIsNone(player["equip"]["hold"])
        finally:
            inventory.cast_item_spells = old_cast

        self.assertIn("Your fragile wand explodes into fragments.", tr.lines)
        self.assertIn("Your fragile staff blazes bright and is gone.", tr.lines)


if __name__ == "__main__":
    unittest.main()
