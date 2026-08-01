"""Tests for gear scoring and equipping: do_compare, gear_score, wear best,
and the bare-wear / get pickers (inventory.py). [PRIMESUD]"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import inventory
import world
from skills_table import GSN_DAGGER, GSN_SWORD
from world import ITEM_DEFS

from scene_fixture import out, scene  # noqa: F401


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
        # skill 80: dice parts carry the (skill + 20) / 140 hit weighting;
        # the flat damroll bonus does not.
        assert any("a sword [120] looks worse than a dagger [162]" in l.lower()
                   for l in out)

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


class TestGearScore:
    def test_weapon_score_uses_combat_skill_floor_and_bonus(self, scene):
        sword = scene["inv"][0]
        # 2d6 -> base 14; score = 14 * skill // 10 * (skill + 20) // 140,
        # skill = 20 + proficiency (one_hit floor + expected-hit weighting).
        scene["learned"][GSN_SWORD] = 0
        assert inventory.gear_score(scene, sword) == 8
        scene["learned"][GSN_SWORD] = 100
        assert inventory.gear_score(scene, sword) == 168

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


class TestWearPicker:
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


class TestWearBest:
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
        # claymore 146 (incl. no-shield bonus) < sword 120 + shield 61
        ITEM_DEFS._data[8006]["dice"] = (1, 12, 0)
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
        # claymore 146 (incl. no-shield bonus) < sword 120 + shield 61
        ITEM_DEFS._data[8006]["dice"] = (1, 12, 0)
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

    def test_wear_best_downweights_unlearnt_weapon(self, scene, out):
        """Expected-hit weighting beats bigger dice on an unlearnt weapon."""
        # 3d6 sword (4x the dagger's dice) at skill 20 scores 12; the
        # learnt 1d4 dagger scores 42 -- the hit weighting decides it.
        # Weights make either dual-wield combo illegal (do_second rules),
        # so the primary pick alone carries the assertion.
        ITEM_DEFS[8001]["dice"] = (3, 6, 0)
        ITEM_DEFS[8001]["weight"] = 30
        ITEM_DEFS[8002]["weight"] = 40
        dagger = scene["inv"][1]
        scene["learned"] = {GSN_DAGGER: 80}
        scene["equip"].update({"wield": None})

        inventory.do_wear(scene, ["best"])

        assert scene["equip"]["wield"] is dagger


class TestGetPickerHistory:
    def test_get_picker_all_resolves(self, scene, out, monkeypatch):
        """The [all] entry returns its typed form for history replay."""
        rs = world.rooms[3001]
        rs["items"] = [{"vnum": 8001}, {"vnum": 8002}]
        # index 2 == "[all]", the slot right after the two items
        monkeypatch.setattr(inventory, "pick_from", lambda title, labels: 2)

        assert inventory.do_get(scene, []) == "get all"
        assert rs["items"] == []

    def test_get_loot_picker_resolves(self, scene, out, monkeypatch):
        """Loot picker choices resolve to typed get-from-container forms."""
        ITEM_DEFS._data[8007] = {
            "type": "container", "keywords": "chest box",
            "short_descr": "a chest", "wear_flags": {},
        }
        chest = {"vnum": 8007,
                 "contents": [{"vnum": 8001}, {"vnum": 8002}]}
        world.rooms[3001]["items"] = [chest]

        picks = iter((0, 2))  # the chest, then [all]
        monkeypatch.setattr(inventory, "pick_from",
                            lambda title, labels: next(picks))
        assert inventory.do_get(scene, []) == "get all chest"
        assert chest["contents"] == []

        chest["contents"] = [{"vnum": 8001}, {"vnum": 8002}]
        picks = iter((0, 1))  # the chest, then the dagger
        assert inventory.do_get(scene, []) == "get dagger chest"
