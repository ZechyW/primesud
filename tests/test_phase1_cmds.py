"""Tests for exits / commands / consider / compare (Phase 1 ports)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import combat
import commands
import info
import inventory
import world
from handler import _char_base
from skills_table import GSN_DAGGER, GSN_SWORD
from world import ITEM_DEFS, MOB_DEFS, ROOM_DEFS


@pytest.fixture
def out(monkeypatch):
    """Capture tprint output across all modules under test."""
    lines = []
    cap = lambda s="", end="\n": lines.append(s)
    # info/combat no longer import tprint (output routes via handler)
    for mod in (inventory, commands):
        monkeypatch.setattr(mod, "tprint", cap)
    import handler
    monkeypatch.setattr(handler, "tprint", cap)
    return lines


@pytest.fixture
def scene():
    old_rooms = dict(world.rooms._data)
    old_room_defs = dict(ROOM_DEFS._data)
    old_chars = dict(world.chars)
    old_mobs = dict(MOB_DEFS._data)
    old_items = dict(ITEM_DEFS._data)

    r1 = {"name": "Test Room", "desc": "x", "exits": {}, "items": [],
          "mobs": [], "area": "test", "sector": "inside"}
    r2 = {"name": "North Room", "desc": "x", "exits": {}, "items": [],
          "mobs": [], "area": "test", "sector": "inside"}
    r3 = {"name": "East Room", "desc": "x", "exits": {}, "items": [],
          "mobs": [], "area": "test", "sector": "inside"}
    world.rooms._data[3001] = r1
    world.rooms._data[3002] = r2
    world.rooms._data[3003] = r3
    ROOM_DEFS._data[3001] = r1
    ROOM_DEFS._data[3002] = r2
    ROOM_DEFS._data[3003] = r3
    r1["exits"] = {"n": 3002, "e": {"to": 3003, "isdoor": True, "closed": True}}

    MOB_DEFS._data[9001] = {"short_descr": "a guard", "keywords": "guard",
                            "level": 10, "description": "A guard."}
    mob = _char_base()
    mob.update({"is_npc": True, "id": 2, "tpl": 9001, "room": 3001,
                "level": 10, "hit": 50, "max_hit": 50})
    world.chars[2] = mob
    r1["mobs"] = [2]

    ITEM_DEFS._data[8001] = {"type": "weapon", "keywords": "sword",
                             "short_descr": "a sword", "dice": (2, 6, 0),
                             "weapon_type": "sword",
                             "wear_flags": {"take": True, "wield": True}}
    ITEM_DEFS._data[8002] = {"type": "weapon", "keywords": "dagger",
                             "short_descr": "a dagger", "dice": (1, 4, 0),
                             "weapon_type": "dagger",
                             "wear_flags": {"take": True, "wield": True}}
    ITEM_DEFS._data[8003] = {"type": "armor", "keywords": "vest",
                             "short_descr": "a vest", "armor": (5, 5, 5, 0),
                             "wear_flags": {"take": True, "body": True}}

    player = _char_base()
    player.update({"id": 1, "room": 3001, "level": 10,
                   "learned": {GSN_SWORD: 80, GSN_DAGGER: 80},
                   "inv": [{"vnum": 8001}, {"vnum": 8002}, {"vnum": 8003}]})
    world.chars[1] = player

    yield player

    world.rooms._data.clear()
    world.rooms._data.update(old_rooms)
    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_room_defs)
    world.chars.clear()
    world.chars.update(old_chars)
    MOB_DEFS._data.clear()
    MOB_DEFS._data.update(old_mobs)
    ITEM_DEFS._data.clear()
    ITEM_DEFS._data.update(old_items)


class TestExits:
    def test_open_exits_listed_closed_hidden(self, scene, out):
        info.do_exits(scene, [])
        assert out[0] == "Obvious exits:"
        assert any("North - North Room" in l for l in out)
        assert not any("East" in l for l in out)  # closed door hidden

    def test_no_exits(self, scene, out):
        ROOM_DEFS[3001]["exits"] = {}
        info.do_exits(scene, [])
        assert out == ["Obvious exits:", "None."]

    def test_runtime_room_state_shape(self, scene, out):
        # On device world.rooms entries are state-only ({"items", "mobs"});
        # static data lives in ROOM_DEFS. do_exits must not touch world.rooms.
        world.rooms._data[3001] = {"items": [], "mobs": []}
        world.rooms._data[3002] = {"items": [], "mobs": []}
        info.do_exits(scene, [])
        assert any("North - North Room" in l for l in out)


class TestCommands:
    def test_lists_known_commands(self, scene, out, monkeypatch):
        # do_commands routes through the tpage pager, not tprint
        monkeypatch.setattr(commands, "tpage", lambda lines: out.extend(lines))
        monkeypatch.setattr(commands, "CMD_DESC_FILE",
                            os.path.join(ROOT, "src", "commands.txt"))
        commands.do_commands(scene, [])
        blob = "\n".join(out)
        assert "kill" in blob and "look" in blob and "wimpy" in blob


class TestConsider:
    @pytest.mark.parametrize("mob_level,frag", [
        (0,  "naked and weaponless"),
        (5,  "no match for you"),
        (8,  "an easy kill"),
        (11, "The perfect match!"),
        (14, "Do you feel lucky, punk?"),
        (19, "laughs at you mercilessly"),
        (20, "Death will thank you"),
    ])
    def test_level_diff_messages(self, scene, out, mob_level, frag):
        world.chars[2]["level"] = mob_level
        combat.do_consider(scene, ["guard"])
        assert any(frag in l for l in out), out

    def test_not_here(self, scene, out):
        combat.do_consider(scene, ["dragon"])
        assert out == ["They're not here."]


class TestCompare:
    def test_better(self, scene, out):
        inventory.do_compare(scene, ["sword", "dagger"])
        assert any("looks better than" in l for l in out)

    def test_same_item(self, scene, out):
        inventory.do_compare(scene, ["sword", "sword"])
        assert any("compare a sword to itself" in l.lower() for l in out)

    def test_cross_type(self, scene, out):
        inventory.do_compare(scene, ["sword", "vest"])
        assert any("can't compare" in l for l in out)

    def test_vs_worn(self, scene, out):
        scene["equip"]["wield"] = scene["inv"].pop(1)  # wear the dagger
        inventory.do_compare(scene, ["sword"])
        assert any("looks better than" in l for l in out)

    def test_nothing_comparable(self, scene, out):
        inventory.do_compare(scene, ["sword"])
        assert out == ["You aren't wearing anything comparable."]

    def test_scores_include_damage_affects(self, scene, out):
        ITEM_DEFS[8002]["stat_bonuses"] = {"damroll": 6}
        inventory.do_compare(scene, ["sword", "dagger"])
        assert any("a sword [140] looks worse than a dagger [170]" in l.lower()
                   for l in out)

    def test_weapon_score_uses_combat_skill_floor_and_bonus(self, scene):
        sword = scene["inv"][0]
        scene["learned"][GSN_SWORD] = 0
        assert inventory.gear_score(scene, sword) == 28
        scene["learned"][GSN_SWORD] = 100
        assert inventory.gear_score(scene, sword) == 168

    def test_vs_weakest_paired_slot(self, scene, out):
        for vnum, keyword, hitroll in (
                (8004, "strongring", 3),
                (8005, "weakring", 1),
                (8006, "upgradering", 2)):
            ITEM_DEFS._data[vnum] = {
                "type": "jewelry", "keywords": keyword,
                "short_descr": keyword, "level": 1,
                "wear_flags": {"take": True, "finger": True},
                "extra_flags": {}, "stat_bonuses": {"hitroll": hitroll},
            }
        strong = {"vnum": 8004}
        weak = {"vnum": 8005}
        upgrade = {"vnum": 8006}
        scene["inv"] = [strong, weak]
        inventory.equip_char(scene, strong, "finger_l")
        inventory.equip_char(scene, weak, "finger_r")
        scene["inv"].append(upgrade)

        inventory.do_compare(scene, ["upgradering"])

        assert any("upgradering [20] looks better than weakring [10]" in l.lower()
                   for l in out)

    def test_gear_score_armor_and_modifier_polarities(self, scene):
        vest = scene["inv"][2]
        ITEM_DEFS[8003]["armor"] = (5, 5, 5, 5)
        ITEM_DEFS[8003]["stat_bonuses"] = {"ac": -2, "saves": -1}
        assert inventory.gear_score(scene, vest) == 300

        ITEM_DEFS[8003]["stat_bonuses"] = {"ac": 2, "saves": 1}
        assert inventory.gear_score(scene, vest) == 100

    def test_gear_score_enchanted_uses_runtime_affects(self, scene):
        vest = scene["inv"][2]
        ITEM_DEFS[8003]["armor"] = (0, 0, 0, 0)
        ITEM_DEFS[8003]["stat_bonuses"] = {"damroll": 50}
        vest["enchanted"] = True
        vest["affect_list"] = [
            {"where": "to_object", "location": "damroll", "modifier": 2,
             "bitvector": ""},
            {"where": "to_affects", "location": "none", "modifier": 0,
             "bitvector": "haste"},
        ]
        assert inventory.gear_score(scene, vest) == 240

    def test_wear_best_replaces_worse_gear(self, scene, out):
        ITEM_DEFS._data[8004] = {
            "type": "armor", "keywords": "plate", "short_descr": "a plate",
            "armor": (6, 6, 6, 6), "level": 1,
            "wear_flags": {"take": True, "body": True}, "extra_flags": {},
        }
        old = scene["inv"][2]
        scene["inv"] = [old]
        inventory.equip_char(scene, old, "body")
        better = {"vnum": 8004}
        scene["inv"].append(better)

        inventory.do_wear(scene, ["best"])

        assert scene["equip"]["body"] is better
        assert old in scene["inv"]

    def test_bare_wear_picker_offers_best(self, scene, out, monkeypatch):
        seen = {}
        scene["equip"].update({"wield": None, "body": None})

        def pick(title, labels):
            seen["title"] = title
            seen["labels"] = labels
            return len(labels) - 1

        monkeypatch.setattr(inventory, "pick_from", pick)

        resolved = inventory.do_wear(scene, [])

        assert seen["title"] == "Wear what?"
        assert seen["labels"] == [
            "a sword", "a dagger", "a vest", "[all]",
            "[best] (Equip strongest gear)",
        ]
        assert resolved == "wear best"
        assert scene["equip"]["body"] is not None
        assert scene["equip"]["wield"] is not None

    def test_bare_wear_picker_all_entry_resolves(self, scene, out, monkeypatch):
        """The [all] entry equips everything and records its typed form."""
        scene["equip"].update({"wield": None, "body": None})
        # index 3 == "[all]", the slot right after the three items
        monkeypatch.setattr(inventory, "pick_from", lambda title, labels: 3)

        resolved = inventory.do_wear(scene, [])

        assert resolved == "wear all"
        assert scene["equip"]["body"] is not None
        assert scene["equip"]["wield"] is not None

    def test_bare_wear_picker_single_item_offers_best_not_all(self, scene, out,
                                                              monkeypatch):
        """With one equippable item, [all] is absent and index 1 is [best].

        Guards the index collision: len(equippable) == best_idx == 1 here, so
        a positional `idx == len(equippable)` test for [all] would swallow the
        [best] pick (or the item pick, if the branches were reordered).
        """
        seen = {}
        vest = scene["inv"][2]
        scene["inv"] = [vest]
        scene["equip"].update({"body": None})

        def pick(title, labels):
            seen["labels"] = labels
            return 1

        monkeypatch.setattr(inventory, "pick_from", pick)

        resolved = inventory.do_wear(scene, [])

        assert seen["labels"] == ["a vest", "[best] (Equip strongest gear)"]
        assert resolved == "wear best"
        assert scene["equip"]["body"] is vest

    def test_bare_wear_picker_single_item_picks_item(self, scene, out, monkeypatch):
        """Picking the lone item wears it singly, not via the [all] loop."""
        vest = scene["inv"][2]
        scene["inv"] = [vest]
        scene["equip"].update({"body": None})
        monkeypatch.setattr(inventory, "pick_from", lambda title, labels: 0)

        resolved = inventory.do_wear(scene, [])

        assert resolved == "wear vest"
        assert scene["equip"]["body"] is vest

    def test_wear_best_replaces_weaker_paired_slot(self, scene, out):
        for vnum, hitroll in ((8004, 3), (8005, 1), (8006, 2)):
            ITEM_DEFS._data[vnum] = {
                "type": "jewelry", "keywords": "ring" + str(vnum),
                "short_descr": "a ring", "level": 1,
                "wear_flags": {"take": True, "finger": True},
                "extra_flags": {}, "stat_bonuses": {"hitroll": hitroll},
            }
        strong = {"vnum": 8004}
        weak = {"vnum": 8005}
        upgrade = {"vnum": 8006}
        scene["inv"] = [strong, weak]
        inventory.equip_char(scene, strong, "finger_l")
        inventory.equip_char(scene, weak, "finger_r")
        scene["inv"].append(upgrade)

        inventory.do_wear(scene, ["best"])

        assert scene["equip"]["finger_l"] is strong
        assert scene["equip"]["finger_r"] is upgrade
        assert weak in scene["inv"]

    def test_wear_best_equips_duplicate_items(self, scene, out):
        ITEM_DEFS._data[8004] = {
            "type": "jewelry", "keywords": "ring", "short_descr": "a ring",
            "level": 1, "wear_flags": {"take": True, "finger": True},
            "extra_flags": {}, "stat_bonuses": {"hitroll": 2},
        }
        ring_a = {"vnum": 8004}
        ring_b = {"vnum": 8004}
        assert ring_a == ring_b  # equal dicts trip equality-based membership
        scene["inv"] = [ring_a, ring_b]

        inventory.do_wear(scene, ["best"])

        assert scene["equip"]["finger_l"] is not None
        assert scene["equip"]["finger_r"] is not None
        assert scene["inv"] == []
        assert not any("already wearing your best gear" in l for l in out)

    def _hand_defs(self, scene):
        # Real players have every slot pre-seeded with None (player.py).
        for slot in ("wield", "secondary", "shield", "hold"):
            scene["equip"].setdefault(slot, None)
        ITEM_DEFS._data[8004] = {
            "type": "weapon", "keywords": "sword2", "short_descr": "a sword2",
            "level": 1, "weight": 20, "weapon_type": "sword",
            "dice": (2, 6, 0),  # score 140 at skill 80
            "wear_flags": {"take": True, "wield": True}, "extra_flags": {},
        }
        ITEM_DEFS._data[8005] = {
            "type": "armor", "keywords": "buckler", "short_descr": "a buckler",
            "level": 1, "armor": (3, 3, 3, 3),  # score 120
            "wear_flags": {"take": True, "shield": True}, "extra_flags": {},
        }
        ITEM_DEFS._data[8006] = {
            "type": "weapon", "keywords": "claymore", "short_descr": "a claymore",
            "level": 1, "weight": 50, "weapon_type": "sword",
            "dice": (4, 8, 0),  # score 360
            "weapon_flags": {"two_hands": True},
            "wear_flags": {"take": True, "wield": True}, "extra_flags": {},
        }

    def test_wear_best_two_hander_replaces_sword_and_shield(self, scene, out):
        self._hand_defs(scene)
        sword = {"vnum": 8004}
        shield = {"vnum": 8005}
        claymore = {"vnum": 8006}
        scene["inv"] = [sword, shield]
        inventory.equip_char(scene, sword, "wield")
        inventory.equip_char(scene, shield, "shield")
        scene["inv"].append(claymore)

        inventory.do_wear(scene, ["best"])

        assert scene["equip"]["wield"] is claymore
        assert scene["equip"]["shield"] is None
        assert sword in scene["inv"] and shield in scene["inv"]

    def test_wear_best_keeps_shield_over_weaker_two_hander(self, scene, out):
        self._hand_defs(scene)
        ITEM_DEFS._data[8006]["dice"] = (2, 9, 0)  # score 200 < 140 + 120
        sword = {"vnum": 8004}
        shield = {"vnum": 8005}
        claymore = {"vnum": 8006}
        scene["inv"] = [sword, shield]
        inventory.equip_char(scene, sword, "wield")
        inventory.equip_char(scene, shield, "shield")
        scene["inv"].append(claymore)

        inventory.do_wear(scene, ["best"])

        assert scene["equip"]["wield"] is sword
        assert scene["equip"]["shield"] is shield
        assert claymore in scene["inv"]

    def test_wear_best_splits_two_hander_for_better_combo(self, scene, out):
        self._hand_defs(scene)
        ITEM_DEFS._data[8006]["dice"] = (2, 9, 0)  # score 200 < 140 + 120
        sword = {"vnum": 8004}
        shield = {"vnum": 8005}
        claymore = {"vnum": 8006}
        scene["inv"] = [claymore]
        inventory.equip_char(scene, claymore, "wield")
        scene["inv"].extend([sword, shield])

        inventory.do_wear(scene, ["best"])

        assert scene["equip"]["wield"] is sword
        assert scene["equip"]["shield"] is shield
        assert claymore in scene["inv"]

    def test_wear_best_adopts_dual_wield(self, scene, out):
        self._hand_defs(scene)
        sword = {"vnum": 8004}
        # dagger: score 60 at skill 80, light enough for the off-hand
        ITEM_DEFS._data[8002]["weight"] = 5
        dagger = {"vnum": 8002}
        scene["inv"] = [sword]
        inventory.equip_char(scene, sword, "wield")
        scene["inv"].append(dagger)

        inventory.do_wear(scene, ["best"])

        assert scene["equip"]["wield"] is sword
        assert scene["equip"]["secondary"] is dagger
        assert any("off-hand" in l for l in out)

    def test_wear_best_parks_wield_during_str_shield_swap(self, scene, out):
        # Swapping one +STR shield for another dips STR below the kept
        # wield's weight mid-apply; affect_modify would floor-drop it.
        self._hand_defs(scene)
        ITEM_DEFS._data[8007] = {
            "type": "weapon", "keywords": "maul", "short_descr": "a maul",
            "level": 1, "weight": 150, "weapon_type": "sword",
            "dice": (2, 6, 0),
            "wear_flags": {"take": True, "wield": True}, "extra_flags": {},
        }
        ITEM_DEFS._data[8008] = {
            "type": "armor", "keywords": "oldstr", "short_descr": "an old shield",
            "level": 1, "armor": (1, 1, 1, 1), "stat_bonuses": {"str": 2},
            "wear_flags": {"take": True, "shield": True}, "extra_flags": {},
        }
        ITEM_DEFS._data[8009] = {
            "type": "armor", "keywords": "newstr", "short_descr": "a new shield",
            "level": 1, "armor": (2, 2, 2, 2), "stat_bonuses": {"str": 2},
            "wear_flags": {"take": True, "shield": True}, "extra_flags": {},
        }
        maul = {"vnum": 8007}
        old_shield = {"vnum": 8008}
        new_shield = {"vnum": 8009}
        scene["inv"] = [maul, old_shield]
        inventory.equip_char(scene, old_shield, "shield")
        inventory.equip_char(scene, maul, "wield")
        scene["inv"].append(new_shield)

        inventory.do_wear(scene, ["best"])

        assert scene["equip"]["wield"] is maul
        assert scene["equip"]["shield"] is new_shield
        assert world.rooms[3001]["items"] == []

    def test_wear_best_parks_wield_during_str_ring_swap(self, scene, out):
        self._hand_defs(scene)
        defs = (
            (8007, "might", {"str": 3}),
            (8008, "greatermight", {"str": 3, "hitroll": 2}),
            (8010, "power", {"hitroll": 20}),
        )
        for vnum, keyword, bonuses in defs:
            ITEM_DEFS._data[vnum] = {
                "type": "jewelry", "keywords": keyword, "short_descr": keyword,
                "level": 1, "wear_flags": {"take": True, "finger": True},
                "extra_flags": {}, "stat_bonuses": bonuses,
            }
        ITEM_DEFS._data[8009] = {
            "type": "weapon", "keywords": "maul", "short_descr": "a maul",
            "level": 1, "weight": 150, "weapon_type": "sword",
            "dice": (2, 6, 0),
            "wear_flags": {"take": True, "wield": True}, "extra_flags": {},
        }
        might = {"vnum": 8007}
        upgrade = {"vnum": 8008}
        maul = {"vnum": 8009}
        power = {"vnum": 8010}
        scene["inv"] = [might, maul, power]
        inventory.equip_char(scene, might, "finger_l")
        inventory.equip_char(scene, power, "finger_r")
        inventory.equip_char(scene, maul, "wield")
        scene["inv"].append(upgrade)

        inventory.do_wear(scene, ["best"])

        assert scene["equip"]["finger_l"] is upgrade
        assert scene["equip"]["wield"] is maul
        assert might in scene["inv"]
        assert world.rooms[3001]["items"] == []

    def test_wear_best_secondary_str_cannot_prop_up_primary(self, scene, out):
        # A secondary needs the primary wielded first (do_second), so its
        # +STR may not justify a primary too heavy to wield without it.
        self._hand_defs(scene)
        ITEM_DEFS._data[8007] = {
            "type": "weapon", "keywords": "greatmaul",
            "short_descr": "a great maul", "level": 1, "weight": 150,
            "weapon_type": "sword", "dice": (4, 8, 0),
            "weapon_flags": {"two_hands": True},
            "wear_flags": {"take": True, "wield": True}, "extra_flags": {},
        }
        ITEM_DEFS._data[8008] = {
            "type": "weapon", "keywords": "strblade",
            "short_descr": "a strength blade", "level": 1, "weight": 5,
            "weapon_type": "sword", "dice": (1, 4, 0),
            "stat_bonuses": {"str": 3},
            "wear_flags": {"take": True, "wield": True}, "extra_flags": {},
        }
        sword = {"vnum": 8004}
        maul = {"vnum": 8007}
        blade = {"vnum": 8008}
        scene["inv"] = [sword]
        inventory.equip_char(scene, sword, "wield")
        scene["inv"].extend([maul, blade])

        inventory.do_wear(scene, ["best"])

        # maul+blade would score highest but is illegal; dual wield wins.
        assert scene["equip"]["wield"] is sword
        assert scene["equip"]["secondary"] is blade
        assert maul in scene["inv"]

    def test_wear_best_does_not_remove_strength_supporting_wield(self, scene, out):
        defs = (
            (8004, "might", "a ring of might", "finger", {"str": 3}, 0),
            (8005, "power", "a ring of power", "finger", {"hitroll": 20}, 0),
            (8006, "upgrade", "an upgrade ring", "finger", {"hitroll": 10}, 0),
            (8007, "heavy", "a heavy sword", "wield", {}, 150),
        )
        for vnum, keyword, short, flag, bonuses, weight in defs:
            ITEM_DEFS._data[vnum] = {
                "type": "weapon" if flag == "wield" else "jewelry",
                "keywords": keyword, "short_descr": short, "level": 1,
                "wear_flags": {"take": True, flag: True},
                "extra_flags": {}, "stat_bonuses": bonuses,
                "weight": weight, "weapon_type": "sword", "dice": (1, 4, 0),
            }
        might = {"vnum": 8004}
        power = {"vnum": 8005}
        upgrade = {"vnum": 8006}
        sword = {"vnum": 8007}
        scene["inv"] = [might, power, sword]
        inventory.equip_char(scene, might, "finger_l")
        inventory.equip_char(scene, power, "finger_r")
        inventory.equip_char(scene, sword, "wield")
        scene["inv"].append(upgrade)

        inventory.do_wear(scene, ["best"])

        assert scene["equip"]["finger_l"] is might
        assert scene["equip"]["wield"] is sword
        assert sword not in world.rooms[scene["room"]]["items"]

    def test_wear_best_checks_weight_without_replaced_weapon(self, scene, out):
        ITEM_DEFS._data[8004] = {
            "type": "weapon", "keywords": "oldblade",
            "short_descr": "an old blade", "level": 1, "weight": 150,
            "weapon_type": "sword", "dice": (1, 4, 0),
            "wear_flags": {"take": True, "wield": True}, "extra_flags": {},
            "stat_bonuses": {"str": 3},
        }
        ITEM_DEFS._data[8005] = {
            "type": "weapon", "keywords": "newblade",
            "short_descr": "a new blade", "level": 1, "weight": 150,
            "weapon_type": "sword", "dice": (10, 10, 0),
            "wear_flags": {"take": True, "wield": True}, "extra_flags": {},
        }
        old = {"vnum": 8004}
        new = {"vnum": 8005}
        scene["inv"] = [old]
        inventory.equip_char(scene, old, "wield")
        scene["inv"].append(new)

        inventory.do_wear(scene, ["best"])

        assert scene["equip"]["wield"] is old
        assert old not in scene["inv"]
        assert new in scene["inv"]
