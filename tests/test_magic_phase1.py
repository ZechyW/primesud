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
import combat
from magic import do_cast
from player import create_char
from player import tick_update
from world import GSN_CURE_LIGHT, SKILLS, MOB_TEMPLATES, init_world
from info import do_spells
from skill_utils import spell_mana

init_world()


class FakeTerminal:
    def __init__(self):
        self.lines = []

    def print(self, text=""):
        self.lines.append(text)


def world_stub(room=3700):
    return {"rooms": {room: {"mobs": [], "items": []}}, "mobs": {}}


def first_sn(name):
    for sn, sk in SKILLS.items():
        if sk["name"] == name:
            return sn
    raise AssertionError(name)


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
        sn = first_sn("create food")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        mp = player["mp"]

        do_cast(tr, player, ["create", "food"], world_stub(player["room"]))

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
        self.assertNotIn("create food", text)

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

    def test_cure_serious_is_registered_and_heals(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("cure serious")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        player["hp"] = 5

        do_cast(tr, player, ["cure", "serious"], world_stub(player["room"]))

        self.assertEqual(["You feel better!"], tr.lines)
        self.assertGreater(player["hp"], 5)

    def test_cure_light_other_target_prints_only_ok_to_caster(self):
        tr = FakeTerminal()
        player = create_char()
        player["learned"][GSN_CURE_LIGHT] = 100
        world = world_stub(player["room"])
        _mob_id, inst = add_mob(world, player["room"], hp=40)
        inst["hp"] = 10
        name = MOB_TEMPLATES[inst["tpl"]]["keywords"].split()[0]

        do_cast(tr, player, ["cure", name], world)

        self.assertEqual(["Ok."], tr.lines)
        self.assertGreater(inst["hp"], 10)

    def test_damage_spell_starts_combat(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("cause light")
        player["learned"][sn] = 100
        world = world_stub(player["room"])
        mob_id, inst = add_mob(world, player["room"], hp=40)
        name = MOB_TEMPLATES[inst["tpl"]]["keywords"].split()[0]

        do_cast(tr, player, ["cause", name], world)

        self.assertLess(inst["hp"], 40)
        self.assertEqual(mob_id, player["fighting"])
        self.assertIs(inst["fighting"], player)

    def test_damage_spell_can_kill_through_raw_kill(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("magic missile")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        world = world_stub(player["room"])
        mob_id, inst = add_mob(world, player["room"], hp=1)
        name = MOB_TEMPLATES[inst["tpl"]]["keywords"].split()[0]
        old_save_state = combat.save_state
        combat.save_state = lambda tr, player, world, quiet=False: True

        try:
            do_cast(tr, player, ["magic", name], world)
        finally:
            combat.save_state = old_save_state

        self.assertNotIn(mob_id, world["mobs"])
        self.assertNotIn(mob_id, world["rooms"][player["room"]]["mobs"])
        self.assertTrue(any(line.startswith("You receive ") for line in tr.lines))

    def test_armor_applies_ac_and_rejects_duplicate(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("armor")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100

        do_cast(tr, player, ["armor"], world_stub(player["room"]))
        player["wait"] = 0
        do_cast(tr, player, ["armor"], world_stub(player["room"]))

        self.assertEqual(80, player["AC"])
        self.assertEqual("You feel someone protecting you.", tr.lines[0])
        self.assertEqual("You are already armored.", tr.lines[-1])

    def test_affect_expiry_unapplies_modifier_and_prints_msg_off(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("armor")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        do_cast(tr, player, ["armor"], world_stub(player["room"]))
        player["affect_list"][0]["duration"] = 0

        tick_update(tr, player, {"heal_rate": 100, "mana_rate": 100})

        self.assertEqual(100, player["AC"])
        self.assertEqual([], player["affect_list"])
        self.assertIn("You feel less armored.", tr.lines)

    def test_bless_applies_multiple_affects_same_type(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("bless")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100

        do_cast(tr, player, ["bless"], world_stub(player["room"]))

        self.assertEqual("You feel righteous.", tr.lines[0])
        self.assertEqual(2, len([af for af in player["affect_list"] if af["type"] == sn]))
        self.assertGreaterEqual(player["hitroll"], 0)
        self.assertLessEqual(player["saving_throw"], 0)

    def test_shield_other_target_uses_target_name(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("shield")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        world = world_stub(player["room"])
        _mob_id, inst = add_mob(world, player["room"], hp=40)
        name = MOB_TEMPLATES[inst["tpl"]]["keywords"].split()[0]
        target_name = magic._char_name(player, inst, world)

        do_cast(tr, player, ["shield", name], world)
        player["wait"] = 0
        do_cast(tr, player, ["shield", name], world)

        self.assertEqual(target_name + " is surrounded by a force shield.", tr.lines[0])
        self.assertEqual(target_name + " is already protected by a shield.", tr.lines[-1])

    def test_faerie_fire_applies_ac_penalty_to_mob(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("faerie fire")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        world = world_stub(player["room"])
        _mob_id, inst = add_mob(world, player["room"], hp=40)
        name = MOB_TEMPLATES[inst["tpl"]]["keywords"].split()[0]

        do_cast(tr, player, ["faerie", "fire", name], world)

        self.assertEqual(100 + 2 * player["level"], inst["AC"])
        self.assertTrue(inst["aff_flags"]["faerie_fire"])

    def test_blindness_save_failure_prints_failed(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("blindness")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        world = world_stub(player["room"])
        _mob_id, inst = add_mob(world, player["room"], hp=40)
        name = MOB_TEMPLATES[inst["tpl"]]["keywords"].split()[0]

        do_cast(tr, player, ["blindness", name], world)

        self.assertEqual("You failed.", tr.lines[0])
        self.assertFalse(inst.get("aff_flags", {}).get("blind"))

    def test_poison_applies_when_save_fails_then_cure_poison_strips(self):
        tr = FakeTerminal()
        player = create_char()
        poison_sn = first_sn("poison")
        cure_sn = first_sn("cure poison")
        player["level"] = max(SKILLS[poison_sn]["skill_level"], SKILLS[cure_sn]["skill_level"])
        player["learned"][poison_sn] = 100
        player["learned"][cure_sn] = 100
        old_randint = magic.randint
        magic.randint = lambda lo, hi: hi
        try:
            world = world_stub(player["room"])
            _mob_id, inst = add_mob(world, player["room"], hp=40)
            name = MOB_TEMPLATES[inst["tpl"]]["keywords"].split()[0]
            do_cast(tr, player, ["poison", name], world)
            poisoned_before = bool(inst.get("aff_flags", {}).get("poison"))
            player["wait"] = 0
            player["fighting"] = None
            player["pos"] = "standing"
            inst["state"] = "idle"
            inst["fighting"] = None
            do_cast(tr, player, ["cure", "poison", name], world)
        finally:
            magic.randint = old_randint

        self.assertTrue(poisoned_before)
        self.assertTrue(any(line.endswith(" looks much better.") for line in tr.lines))
        self.assertFalse(inst.get("aff_flags", {}).get("poison"))

    def test_cure_blindness_without_blindness_exact_text(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("cure blindness")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100

        do_cast(tr, player, ["cure", "blindness"], world_stub(player["room"]))

        self.assertEqual(["You aren't blind."], tr.lines)

    def test_dispel_magic_strips_armor(self):
        tr = FakeTerminal()
        player = create_char()
        armor_sn = first_sn("armor")
        dispel_sn = first_sn("dispel magic")
        player["level"] = max(SKILLS[armor_sn]["skill_level"], SKILLS[dispel_sn]["skill_level"])
        player["learned"][armor_sn] = 100
        player["learned"][dispel_sn] = 100
        old_randint = magic.randint
        magic.randint = lambda lo, hi: hi
        try:
            world = world_stub(player["room"])
            _mob_id, inst = add_mob(world, player["room"], hp=40)
            name = MOB_TEMPLATES[inst["tpl"]]["keywords"].split()[0]
            do_cast(tr, player, ["armor", name], world)
            player["wait"] = 0
            do_cast(tr, player, ["dispel", "magic", name], world)
        finally:
            magic.randint = old_randint

        self.assertEqual(100, inst["AC"])
        self.assertFalse(inst["affect_list"])
        self.assertIn("Ok.", tr.lines)
        self.assertNotIn("You feel less armored.", tr.lines)

    def test_dispel_magic_self_success_prints_ok(self):
        tr = FakeTerminal()
        player = create_char()
        armor_sn = first_sn("armor")
        dispel_sn = first_sn("dispel magic")
        player["level"] = max(SKILLS[armor_sn]["skill_level"], SKILLS[dispel_sn]["skill_level"])
        player["learned"][armor_sn] = 100
        player["learned"][dispel_sn] = 100
        old_randint = magic.randint
        magic.randint = lambda lo, hi: hi
        try:
            world = world_stub(player["room"])
            magic.spell_armor(tr, armor_sn, player["level"], player, player, magic.TARGET_CHAR, world)
            magic.spell_dispel_magic(tr, dispel_sn, player["level"], player, player, magic.TARGET_CHAR, world)
        finally:
            magic.randint = old_randint

        self.assertIn("You feel less armored.", tr.lines)
        self.assertEqual("Ok.", tr.lines[-1])


if __name__ == "__main__":
    unittest.main()
