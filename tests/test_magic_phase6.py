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

import combat
import magic
from magic import do_cast
from player import create_char
from mob import reset_area, create_area_states
from world import SKILLS, MOB_TEMPLATES, ROOMS, R_RECALL, init_world


init_world()


class FakeTerminal:
    def __init__(self):
        self.lines = []

    def print(self, text=""):
        self.lines.append(text)


def world_stub(room=3700):
    return {"rooms": {room: {"mobs": [], "items": []}}, "mobs": {}, "areas": []}


def first_sn(name):
    for sn, sk in SKILLS.items():
        if sk["name"] == name:
            return sn
    raise AssertionError(name)


def first_outdoor_room():
    for vnum, room in ROOMS.items():
        if not room.get("flags", {}).get("indoors"):
            return vnum
    raise AssertionError("no outdoor room")


def add_mob(world, room, tpl_vnum=None, hp=30, flying=False):
    if tpl_vnum is None:
        tpl_vnum = next(iter(MOB_TEMPLATES))
    mob_id = len(world["mobs"]) + 1
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
        "aff_flags": {"flying": flying} if flying else {},
    }
    world["mobs"][mob_id] = inst
    world["rooms"][room]["mobs"].append(mob_id)
    return mob_id, inst


class MagicPhase6Test(unittest.TestCase):
    def test_earthquake_damages_all_grounded_room_mobs(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("earthquake")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        world = world_stub(player["room"])
        _mob1, mob1 = add_mob(world, player["room"], hp=40)
        _mob2, mob2 = add_mob(world, player["room"], hp=40)

        do_cast(tr, player, ["earthquake"], world)

        self.assertEqual("The earth trembles beneath your feet!", tr.lines[0])
        self.assertLess(mob1["hp"], 40)
        self.assertLess(mob2["hp"], 40)

    def test_earthquake_flying_mob_takes_zero_damage(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("earthquake")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        world = world_stub(player["room"])
        _mob_id, mob = add_mob(world, player["room"], hp=40, flying=True)

        do_cast(tr, player, ["earthquake"], world)

        self.assertEqual(40, mob["hp"])
        self.assertTrue(any("misses" in line for line in tr.lines[1:]))

    def test_earthquake_survivors_aggro_player(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("earthquake")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        world = world_stub(player["room"])
        mob1_id, mob1 = add_mob(world, player["room"], hp=40)
        mob2_id, mob2 = add_mob(world, player["room"], hp=40)

        do_cast(tr, player, ["earthquake"], world)

        self.assertEqual(mob1_id, player["fighting"])
        self.assertEqual("fighting", player["pos"])
        self.assertEqual("aggro", mob1["state"])
        self.assertEqual("aggro", mob2["state"])
        self.assertIs(mob1["fighting"], player)
        self.assertIs(mob2["fighting"], player)

    def test_earthquake_kills_through_normal_kill_flow(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("earthquake")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        world = world_stub(player["room"])
        mob_id, _mob = add_mob(world, player["room"], hp=1)
        old_save_state = combat.save_state
        combat.save_state = lambda tr, player, world, quiet=False: True

        try:
            do_cast(tr, player, ["earthquake"], world)
        finally:
            combat.save_state = old_save_state

        self.assertNotIn(mob_id, world["mobs"])
        self.assertTrue(any(line.startswith("You receive ") for line in tr.lines))

    def test_word_of_recall_moves_player_to_recall_room(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("word of recall")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        room_state, mob_instances = reset_area()
        start_room = next(vnum for vnum in ROOMS if vnum != R_RECALL)
        player["room"] = start_room
        world = {"rooms": room_state, "mobs": mob_instances, "areas": create_area_states()}

        do_cast(tr, player, ["word", "of", "recall"], world)

        self.assertEqual(R_RECALL, player["room"])
        self.assertTrue(any(ROOMS[R_RECALL]["name"] in line for line in tr.lines))

    def test_word_of_recall_fails_on_npc_target(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("word of recall")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        world = world_stub(player["room"])
        _mob_id, mob = add_mob(world, player["room"], hp=40)

        ret = magic.spell_word_of_recall(
            tr, sn, player["level"], player, mob, magic.TARGET_CHAR, world)

        self.assertFalse(ret)

    def test_call_lightning_requires_outdoors(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("call lightning")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        player["room"] = 3700
        world = {"rooms": {3700: {"mobs": [], "items": []}}, "mobs": {}, "areas": create_area_states()}

        do_cast(tr, player, ["call", "lightning"], world)

        self.assertEqual(["You must be out of doors."], tr.lines)

    def test_call_lightning_requires_bad_weather(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("call lightning")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        room = first_outdoor_room()
        player["room"] = room
        areas = create_area_states()
        for area in areas:
            if area["tag"] == "midgaard":
                area["weather"]["precip"] = 0
        world = {"rooms": {room: {"mobs": [], "items": []}}, "mobs": {}, "areas": areas}

        do_cast(tr, player, ["call", "lightning"], world)

        self.assertEqual(["You need bad weather."], tr.lines)

    def test_call_lightning_damages_room_mobs_and_aggros(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("call lightning")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        room = first_outdoor_room()
        player["room"] = room
        areas = create_area_states()
        for area in areas:
            if area["tag"] == "midgaard":
                area["weather"]["precip"] = 1
        world = {"rooms": {room: {"mobs": [], "items": []}}, "mobs": {}, "areas": areas}
        mob1_id, mob1 = add_mob(world, room, hp=40)
        mob2_id, mob2 = add_mob(world, room, hp=40)

        do_cast(tr, player, ["call", "lightning"], world)

        self.assertEqual("Your lightning strikes your foes!", tr.lines[0])
        self.assertLess(mob1["hp"], 40)
        self.assertLess(mob2["hp"], 40)
        self.assertEqual(mob1_id, player["fighting"])
        self.assertEqual("aggro", mob1["state"])
        self.assertEqual("aggro", mob2["state"])
        self.assertIs(mob1["fighting"], player)
        self.assertIs(mob2["fighting"], player)

    def test_control_weather_wetter_adjusts_precip_vector(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("control weather")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        room = first_outdoor_room()
        player["room"] = room
        areas = create_area_states()
        for area in areas:
            if area["tag"] == "midgaard":
                area["weather"]["precip_vector"] = 0
        world = {"rooms": {room: {"mobs": [], "items": []}}, "mobs": {}, "areas": areas}

        do_cast(tr, player, ["control", "weather", "wetter"], world)

        self.assertEqual(["The weather is altered by your magic."], tr.lines)
        self.assertNotEqual(0, next(area for area in areas if area["tag"] == "midgaard")["weather"]["precip_vector"])

    def test_farsight_direction_scans_visible_mob(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("farsight")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        room = 3700
        dest = 3701
        world = {
            "rooms": {
                room: {"mobs": [], "items": []},
                dest: {"mobs": [], "items": []},
            },
            "mobs": {},
            "areas": [],
        }
        old_room = ROOMS[room]
        ROOMS[room] = {"name": "A", "desc": "", "flags": {}, "sector": "inside", "exits": {"n": dest}}
        ROOMS[dest] = {"name": "B", "desc": "", "flags": {}, "sector": "inside", "exits": {}}
        _mob_id, _mob = add_mob(world, dest, hp=40)
        try:
            do_cast(tr, player, ["farsight", "north"], world)
        finally:
            ROOMS[room] = old_room

        self.assertEqual("Looking north you see:", tr.lines[0])
        self.assertTrue(any("nearby to the north." in line for line in tr.lines[1:]))

    def test_locate_object_reports_room_item(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("locate object")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        room_state, mob_instances = reset_area()
        world = {"rooms": room_state, "mobs": mob_instances, "areas": create_area_states()}
        room_state[player["room"]]["items"].append({"vnum": 3011, "cost": 0})

        do_cast(tr, player, ["locate", "object", "bread"], world)

        self.assertTrue(any(line.startswith("one is in ") for line in tr.lines))

    def test_teleport_moves_player_to_new_room(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("teleport")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        room_state, mob_instances = reset_area()
        world = {"rooms": room_state, "mobs": mob_instances, "areas": create_area_states()}
        start_room = player["room"]
        old_randint = magic.randint
        magic.randint = lambda lo, hi: lo
        try:
            do_cast(tr, player, ["teleport"], world)
        finally:
            magic.randint = old_randint

        self.assertNotEqual(start_room, player["room"])
        self.assertTrue(any(ROOMS[player["room"]]["name"] in line for line in tr.lines))

    def test_chain_lightning_arcs_to_second_mob(self):
        tr = FakeTerminal()
        player = create_char()
        sn = first_sn("chain lightning")
        player["level"] = SKILLS[sn]["skill_level"]
        player["learned"][sn] = 100
        world = world_stub(player["room"])
        _mob1_id, mob1 = add_mob(world, player["room"], hp=80)
        _mob2_id, mob2 = add_mob(world, player["room"], hp=80)
        name = MOB_TEMPLATES[mob1["tpl"]]["keywords"].split()[0]

        do_cast(tr, player, ["chain", "lightning", name], world)

        self.assertLess(mob1["hp"], 80)
        self.assertLess(mob2["hp"], 80)
        self.assertTrue(any("The bolt arcs to " in line for line in tr.lines))


if __name__ == "__main__":
    unittest.main()
