"""Tests for the [PRIMESUD] prestige tier system (finish_tier_reset et al.).

No 1stMud equivalent; design settled 11/07/2026 (see DESIGN.md multiclass
tiering). Stock remort behaviour is covered by test_classes.py TestRemort.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import world
from classes import (CLASS_MAGE, CLASS_CLERIC, CLASS_WARRIOR, CLASS_TABLE,
                     calc_max_level, can_use_skill_spell, class_who,
                     skill_adept_cap)
from config import MAX_STATS, SKILL_ADEPT
from handler import get_max_train
from player import create_char
from skills_table import SKILLS, GSN_BASH, GSN_RECALL, WEAPON_GSN_MAP


def _hero(monkeypatch, pick=0, classes=(CLASS_WARRIOR, CLASS_MAGE), race_pick=0):
    """Max-level multiclass hero in his guild with a trainer, rich, at 3022."""
    from world import ROOM_DEFS, MOB_DEFS

    room = {"name": "Bar of Swordsmen", "desc": "x", "items": [], "mobs": [2],
            "area": "test", "sector": "inside", "flags": {}, "exits": {},
            "guild": (CLASS_WARRIOR,)}
    ROOM_DEFS._data[3022] = room
    world.rooms._data[3022] = room
    # dice/combat fields present so create_mobile can spawn a pet from it
    MOB_DEFS._data[9900] = {"short_descr": "the guildmaster", "level": 60,
                            "act_flags": {"train": True},
                            "hp_dice": (1, 1, 100), "hitroll": 0,
                            "damage": (1, 4, 0), "armor": (0, 0, 0, 0)}
    # "fighting" present: stop_fighting(both=True) indexes it on every char
    world.chars[2] = {"is_npc": True, "id": 2, "tpl": 9900, "room": 3022,
                      "fighting": None}

    player = create_char(CLASS_WARRIOR)
    player["classes"] = list(classes)
    player["room"] = 3022
    player["gold"] = 500000
    player["quest_points"] = 500
    player["level"] = calc_max_level(player)
    world.chars[1] = player

    # earlier suites (test_quest.py) can leave a global gquest running,
    # which trips do_remort's quest gate
    from gquest import gquest_info, GQUEST_OFF
    gquest_info["running"] = GQUEST_OFF
    gquest_info["joined"] = False

    import training
    # remort now runs two pickers: race ("What is your race?") then class
    monkeypatch.setattr(training, "pick_from",
                        lambda t, o: race_pick if "race" in t else pick)
    monkeypatch.setattr(training, "save_world", lambda quiet=False: True,
                        raising=False)
    monkeypatch.setattr(training, "do_outfit", lambda p, a: None)
    import game_state
    monkeypatch.setattr(game_state, "save_world", lambda quiet=False: True)
    return player


def _teardown():
    from world import ROOM_DEFS, MOB_DEFS
    ROOM_DEFS._data.pop(3022, None)
    world.rooms._data.pop(3022, None)
    MOB_DEFS._data.pop(9900, None)
    world.chars.pop(1, None)
    world.chars.pop(2, None)


class TestTierReset:
    def test_full_flow(self, monkeypatch):
        import training
        # avail = all 6 classes on a tier reset; pick=1 -> Cleric
        player = _hero(monkeypatch, pick=CLASS_CLERIC)
        # in-progress skill above the floor, one below, one mastered
        player["learned"][WEAPON_GSN_MAP["sword"]] = 100   # mastered, kept
        player["learned"][GSN_BASH] = 60                   # floors to 10
        # pets do not survive (cf. 1stMud finish_remort nuke_pets)
        from mob import spawn_pet
        pet = spawn_pet(9900, player, announce=False)
        try:
            training.do_remort(player, [])          # confirm prompt
            assert player["confirm_remort"] is True
            training.do_remort(player, [])          # confirmed -> picker -> reset
            assert player["tier"] == 1
            assert player["classes"] == [CLASS_CLERIC]
            assert player["prime_class"] == 0
            assert player["level"] == 1
            assert player["xp"] == 0
            assert player["gold"] == 0
            assert player["quest_points"] == 0
            # near-fresh pools: create_char baselines + 50 per tier
            assert player["max_hit"] == player["perm_hit"] == 100
            assert player["max_mana"] == player["perm_mana"] == 150
            assert player["max_move"] == player["perm_move"] == 150
            assert player["hit"] == 100 and player["mana"] == 150
            assert player["wimpy"] == 20
            assert player["train"] == 6
            assert player["practice"] == 8
            # race prompt ran (Human kept): stats reset to race base + tier
            # (chargen prime +3 lost, cf. nanny.c:527); same race -> no lock
            for st in ("str", "dex", "int", "wis", "con"):
                assert player["perm_stat"][st] == 13 + 1
            assert player["stay_race"] == 0
            # mastered kept; in-progress floored at 10*tier
            assert player["learned"][WEAPON_GSN_MAP["sword"]] == 100
            assert player["learned"][GSN_BASH] == 10
            # kindness floors for the new class
            assert player["learned"][WEAPON_GSN_MAP["mace"]] >= 40
            assert player["learned"][GSN_RECALL] >= 50
            # back to one class -> level cap back to LEVEL_HERO
            assert calc_max_level(player) == 49
            assert player["room"] != 3022  # moved to school
            assert player["confirm_remort"] is False
            # pet extracted (cf. 1stMud multiclass.c:207 nuke_pets)
            assert player["pet"] is None
            assert pet["id"] not in world.chars
        finally:
            _teardown()

    def test_skill_below_floor_untouched(self, monkeypatch):
        import training
        player = _hero(monkeypatch, pick=CLASS_CLERIC)
        player["learned"][GSN_BASH] = 5  # below the 10*tier floor
        try:
            training.do_remort(player, [])
            training.do_remort(player, [])
            assert player["learned"][GSN_BASH] == 5
        finally:
            _teardown()

    def test_second_reset_scales(self, monkeypatch):
        import training
        player = _hero(monkeypatch, pick=CLASS_MAGE)
        player["tier"] = 1
        try:
            training.do_remort(player, [])
            training.do_remort(player, [])
            assert player["tier"] == 2
            assert player["max_hit"] == 150
            assert player["max_mana"] == 200
            assert player["train"] == 7
            assert player["practice"] == 9
        finally:
            _teardown()

    def test_repeat_class_allowed(self, monkeypatch):
        import training
        player = _hero(monkeypatch, pick=CLASS_WARRIOR)
        try:
            training.do_remort(player, [])
            training.do_remort(player, [])
            assert player["classes"] == [CLASS_WARRIOR]
            assert player["tier"] == 1
        finally:
            _teardown()

    def test_race_change_on_reset(self, monkeypatch):
        # Dwarf pick (PC_RACE_ORDER[2]): stats reset to Dwarf base + tier,
        # race locked forever, race fields/skills re-derived
        import training
        from races import RACE_TABLE
        player = _hero(monkeypatch, pick=CLASS_WARRIOR, race_pick=2)
        try:
            training.do_remort(player, [])
            training.do_remort(player, [])
            assert player["race"] == "Dwarf"
            assert player["stay_race"] == 1
            stats = RACE_TABLE["Dwarf"]["stats"]
            for i, st in enumerate(("str", "dex", "int", "wis", "con")):
                assert player["perm_stat"][st] == stats[i] + 1  # + tier perk
            assert player["res_flags"].get("poison")
            assert player["vuln_flags"].get("drowning")
            # dwarven berserk granted at 1%
            from magic import _skill_lookup
            assert player["learned"].get(_skill_lookup("berserk"), 0) >= 1
        finally:
            _teardown()

    def test_locked_race_keeps_plus_one_perk(self, monkeypatch):
        # stay_race set: no race prompt, stats keep accumulating +1 per tier
        import training
        player = _hero(monkeypatch, pick=CLASS_MAGE,
                       race_pick=99)  # picker must not ask for race
        player["stay_race"] = 1
        old_stats = dict(player["perm_stat"])
        try:
            training.do_remort(player, [])
            training.do_remort(player, [])
            assert player["race"] == "Human"
            for st in ("str", "dex", "int", "wis", "con"):
                assert player["perm_stat"][st] == old_stats[st] + 1
        finally:
            _teardown()

    def test_gates_still_apply(self, monkeypatch):
        import training
        player = _hero(monkeypatch)
        player["gold"] = 0
        try:
            training.do_remort(player, [])
            assert not player.get("confirm_remort")
            assert player["tier"] == 0
        finally:
            _teardown()


class TestTierPerks:
    def test_skill_adept_cap(self):
        assert skill_adept_cap({"tier": 0}) == SKILL_ADEPT
        assert skill_adept_cap({}) == SKILL_ADEPT  # NPC/legacy dicts
        assert skill_adept_cap({"tier": 2}) == SKILL_ADEPT + 10
        assert skill_adept_cap({"tier": 10}) == 95  # hard cap

    def test_get_max_train_tier_raise(self):
        ch = create_char(CLASS_WARRIOR)
        base = get_max_train(ch, "dex")  # non-prime for warrior
        ch["tier"] = 2
        assert get_max_train(ch, "dex") == min(base + 2, MAX_STATS)
        ch["tier"] = 50
        assert get_max_train(ch, "dex") == MAX_STATS  # clamp holds

    def test_mastered_skill_dormant_until_reheld(self):
        # bash: mage skill_level 53 -> unusable even at 100%; re-holding
        # a warrior class instantly reactivates it (skill_level unchanged)
        ch = {"is_npc": False, "level": 50, "classes": [CLASS_MAGE],
              "race": "Human", "learned": {GSN_BASH: 100}, "tier": 1}
        assert not can_use_skill_spell(ch, GSN_BASH)
        ch["classes"].append(CLASS_WARRIOR)
        assert can_use_skill_spell(ch, GSN_BASH)

    def test_practice_past_stock_adept(self, monkeypatch):
        """A tier-1 char can practice a skill from 75 up to 80."""
        import training
        from world import ROOM_DEFS, MOB_DEFS
        room = {"name": "Guild", "desc": "x", "items": [], "mobs": [2],
                "area": "test", "sector": "inside", "flags": {}, "exits": {}}
        ROOM_DEFS._data[3022] = room
        world.rooms._data[3022] = room
        MOB_DEFS._data[9900] = {"short_descr": "the teacher", "level": 60,
                                "act_flags": {"practice": True}}
        world.chars[2] = {"is_npc": True, "id": 2, "tpl": 9900, "room": 3022}
        player = create_char(CLASS_WARRIOR)
        player["room"] = 3022
        player["tier"] = 1
        player["practice"] = 5
        sword = WEAPON_GSN_MAP["sword"]
        player["learned"][sword] = 75
        world.chars[1] = player
        try:
            training.do_practice(player, ["sword"])
            assert 75 < player["learned"][sword] <= 80
        finally:
            _teardown()


class TestTierDisplay:
    def test_class_who_suffix(self):
        ch = {"is_npc": False, "level": 1, "classes": [CLASS_WARRIOR],
              "race": "Human", "prime_class": 0}
        assert class_who(ch) == "Warr"
        ch["tier"] = 2
        assert class_who(ch) == "Warr*2"
        # 2 classes -> remort-tier display names ("Gladiator"[:2] + count)
        ch["classes"] = [CLASS_WARRIOR, CLASS_MAGE]
        assert class_who(ch) == "Gl+1*2"


class TestTierSaveLoad:
    def test_tier_roundtrip(self, tmp_path, monkeypatch):
        import game_state
        monkeypatch.setattr(game_state, "SAVE_FILE", str(tmp_path / "t.sav"))
        world.areas = []
        player = create_char()
        player["name"] = "Tester"
        player["room"] = 9001
        player["_macros"] = {}
        player["tier"] = 3
        player["stay_race"] = 1
        world.chars[1] = player
        game_state._serialize_world()

        world.chars.clear()
        player2 = create_char()
        player2["name"] = "Tester"
        player2["room"] = 9001
        player2["_macros"] = {}
        world.chars[1] = player2
        assert game_state.load_world() == "file"
        assert player2["tier"] == 3
        assert player2["stay_race"] == 1

    def test_fresh_char_defaults_tier_zero(self):
        # old saves carry no p.tier/p.stay_race lines; create_char defaults hold
        ch = create_char()
        assert ch["tier"] == 0
        assert ch["stay_race"] == 0
