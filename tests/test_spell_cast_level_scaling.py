"""Tests for spell cast level scaling (cf. 1stMud magic.c:492-499).

1stMud casts non-caster PCs at 3 * level / 4; NPCs and caster PCs get full level.
PrimeSUD must match this behavior.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "primesud.hpappdir")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from terminal import init_terminal
init_terminal()

import world
from world import ROOM_DEFS, MOB_DEFS, ITEM_DEFS
from handler import _char_base
from magic import do_cast, SPELL_FUNS, SKILLS, _skill_lookup
from classes import CLASS_MAGE, CLASS_CLERIC, CLASS_WARRIOR, CLASS_THIEF
from skill_utils import get_skill


def _make_player(**overrides):
    """Create a player character with full setup."""
    ch = _char_base()
    ch["name"] = "TestPlayer"
    ch["level"] = 20
    ch["room"] = 3001
    ch["pos"] = "standing"
    ch["hit"] = 200
    ch["max_hit"] = 200
    ch["mana"] = 9999
    ch["max_mana"] = 9999
    ch["learned"] = {}
    ch.update(overrides)
    return ch


def _make_npc(**overrides):
    """Create an NPC with full setup."""
    ch = _char_base()
    ch["is_npc"] = True
    ch["name"] = "TestMob"
    ch["level"] = 20
    ch["room"] = 3001
    ch["pos"] = "standing"
    ch["hit"] = 200
    ch["max_hit"] = 200
    ch["mana"] = 9999
    ch.update(overrides)
    return ch


@pytest.fixture(autouse=True)
def _clean_world_state():
    """Snapshot and restore minimal world state around each test."""
    old_rooms = dict(ROOM_DEFS._data)
    old_wrooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    yield
    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_rooms)
    world.rooms._data.clear()
    world.rooms._data.update(old_wrooms)
    world.chars.clear()
    world.chars.update(old_chars)


@pytest.fixture
def test_room():
    """Create a test room."""
    room = {
        "name": "Test Room",
        "desc": "A test room.",
        "exits": {},
        "items": [],
        "mobs": [],
        "area": "test",
        "flags": {},
        "sector": "inside"
    }
    ROOM_DEFS._data[3001] = room
    world.rooms._data[3001] = room
    return room


class TestSpellCastLevelScaling:
    """Verify spell cast level matches 1stMud formula."""

    def test_npc_casts_at_full_level(self, test_room, monkeypatch):
        """NPC should cast at full level (not scaled)."""
        # Capture the level argument passed to the spell function
        captured = {}

        def spy_armor(sn, level, ch, vo, target):
            captured["level"] = level
            return True

        armor_sn = _skill_lookup("armor")
        if armor_sn is None:
            pytest.skip("armor spell not in skill table")

        npc = _make_npc(level=20)
        npc["id"] = 1
        npc["learned"] = {armor_sn: 50}  # NPCs need learned field too
        world.chars[1] = npc
        test_room["mobs"] = [1]

        # Patch get_skill to return high value (will pass concentration check)
        # Check: if randint(1, 100) > get_skill -> fail. So need randint <= get_skill
        monkeypatch.setattr("magic.get_skill", lambda ch, sn: 150)
        # Patch randint to return low value (passes skill check)
        monkeypatch.setattr("magic.randint", lambda a, b: 50)

        orig_fun = SPELL_FUNS.get(SKILLS[armor_sn].get("spell_fun"))
        SPELL_FUNS[SKILLS[armor_sn]["spell_fun"]] = spy_armor
        try:
            do_cast(npc, ["armor"])
        finally:
            if orig_fun:
                SPELL_FUNS[SKILLS[armor_sn]["spell_fun"]] = orig_fun

        # NPC should get full level
        assert captured.get("level") == 20, \
            "NPC should cast at full level (20), got %s" % captured.get("level")

    def test_caster_pc_casts_at_full_level(self, test_room, monkeypatch):
        """Caster PC (Mage/Cleric) should cast at full level."""
        captured = {}

        def spy_armor(sn, level, ch, vo, target):
            captured["level"] = level
            return True

        armor_sn = _skill_lookup("armor")
        if armor_sn is None:
            pytest.skip("armor spell not in skill table")

        # Mage (CLASS_MAGE = 0) is a caster
        player = _make_player(level=20, classes=[CLASS_MAGE])
        player["id"] = 1
        player["learned"][armor_sn] = 50  # Mark as learned
        world.chars[1] = player
        test_room["mobs"] = []

        # Patch get_skill to return high value (will pass concentration check)
        monkeypatch.setattr("magic.get_skill", lambda ch, sn: 150)
        # Patch randint to return low value (passes skill check)
        monkeypatch.setattr("magic.randint", lambda a, b: 50)

        orig_fun = SPELL_FUNS.get(SKILLS[armor_sn].get("spell_fun"))
        SPELL_FUNS[SKILLS[armor_sn]["spell_fun"]] = spy_armor
        try:
            do_cast(player, ["armor"])
        finally:
            if orig_fun:
                SPELL_FUNS[SKILLS[armor_sn]["spell_fun"]] = orig_fun

        # Caster PC should get full level
        assert captured.get("level") == 20, \
            "Caster PC should cast at full level (20), got %s" % captured.get("level")

    def test_noncaster_pc_casts_at_scaled_level(self, test_room, monkeypatch):
        """Non-caster PC (Warrior/Thief) should cast at 3*level/4."""
        captured = {}

        def spy_armor(sn, level, ch, vo, target):
            captured["level"] = level
            return True

        armor_sn = _skill_lookup("armor")
        if armor_sn is None:
            pytest.skip("armor spell not in skill table")

        # Warrior (CLASS_WARRIOR = 3) is NOT a caster
        player = _make_player(level=20, classes=[CLASS_WARRIOR])
        player["id"] = 1
        player["learned"][armor_sn] = 50  # Mark as learned
        world.chars[1] = player
        test_room["mobs"] = []

        # Patch get_skill to return high value (will pass concentration check)
        monkeypatch.setattr("magic.get_skill", lambda ch, sn: 150)
        # Patch randint to return low value (passes skill check)
        monkeypatch.setattr("magic.randint", lambda a, b: 50)

        orig_fun = SPELL_FUNS.get(SKILLS[armor_sn].get("spell_fun"))
        SPELL_FUNS[SKILLS[armor_sn]["spell_fun"]] = spy_armor
        try:
            do_cast(player, ["armor"])
        finally:
            if orig_fun:
                SPELL_FUNS[SKILLS[armor_sn]["spell_fun"]] = orig_fun

        # Non-caster PC should get 3*level/4 = 3*20/4 = 15
        expected_level = 3 * 20 // 4
        assert captured.get("level") == expected_level, \
            "Non-caster PC should cast at 3*level/4 (%d), got %s" % (expected_level, captured.get("level"))

    def test_thief_non_caster_scaled_level(self, test_room, monkeypatch):
        """Thief (non-caster) should scale level even for spells they can learn."""
        captured = {}

        def spy_armor(sn, level, ch, vo, target):
            captured["level"] = level
            return True

        armor_sn = _skill_lookup("armor")
        if armor_sn is None:
            pytest.skip("armor spell not in skill table")

        # Thief (CLASS_THIEF = 2) is NOT a caster
        player = _make_player(level=20, classes=[CLASS_THIEF])
        player["id"] = 1
        player["learned"][armor_sn] = 50
        world.chars[1] = player
        test_room["mobs"] = []

        # Patch get_skill to return high value (will pass concentration check)
        monkeypatch.setattr("magic.get_skill", lambda ch, sn: 150)
        # Patch randint to return low value (passes skill check)
        monkeypatch.setattr("magic.randint", lambda a, b: 50)

        orig_fun = SPELL_FUNS.get(SKILLS[armor_sn].get("spell_fun"))
        SPELL_FUNS[SKILLS[armor_sn]["spell_fun"]] = spy_armor
        try:
            do_cast(player, ["armor"])
        finally:
            if orig_fun:
                SPELL_FUNS[SKILLS[armor_sn]["spell_fun"]] = orig_fun

        expected_level = 3 * 20 // 4  # = 15
        assert captured.get("level") == expected_level, \
            "Thief should cast at 3*level/4, got %s" % captured.get("level")

    def test_multiclass_with_caster_class_gets_full_level(self, test_room, monkeypatch):
        """Multiclass PC with at least one caster class should get full level."""
        captured = {}

        def spy_armor(sn, level, ch, vo, target):
            captured["level"] = level
            return True

        armor_sn = _skill_lookup("armor")
        if armor_sn is None:
            pytest.skip("armor spell not in skill table")

        # Warrior + Cleric = non-caster + caster -> should get full level (has_spells = True)
        player = _make_player(level=20, classes=[CLASS_WARRIOR, CLASS_CLERIC])
        player["id"] = 1
        player["learned"][armor_sn] = 50
        world.chars[1] = player
        test_room["mobs"] = []

        # Patch get_skill to return high value (will pass concentration check)
        monkeypatch.setattr("magic.get_skill", lambda ch, sn: 150)
        # Patch randint to return low value (passes skill check)
        monkeypatch.setattr("magic.randint", lambda a, b: 50)

        orig_fun = SPELL_FUNS.get(SKILLS[armor_sn].get("spell_fun"))
        SPELL_FUNS[SKILLS[armor_sn]["spell_fun"]] = spy_armor
        try:
            do_cast(player, ["armor"])
        finally:
            if orig_fun:
                SPELL_FUNS[SKILLS[armor_sn]["spell_fun"]] = orig_fun

        # Multiclass with caster should get full level
        assert captured.get("level") == 20, \
            "Multiclass with caster should cast at full level (20), got %s" % captured.get("level")

    def test_multiclass_all_noncasters_gets_scaled_level(self, test_room, monkeypatch):
        """Multiclass PC with only non-caster classes should get scaled level."""
        captured = {}

        def spy_armor(sn, level, ch, vo, target):
            captured["level"] = level
            return True

        armor_sn = _skill_lookup("armor")
        if armor_sn is None:
            pytest.skip("armor spell not in skill table")

        # Warrior + Thief = non-caster + non-caster -> should get scaled level
        player = _make_player(level=20, classes=[CLASS_WARRIOR, CLASS_THIEF])
        player["id"] = 1
        player["learned"][armor_sn] = 50
        world.chars[1] = player
        test_room["mobs"] = []

        # Patch get_skill to return high value (will pass concentration check)
        monkeypatch.setattr("magic.get_skill", lambda ch, sn: 150)
        # Patch randint to return low value (passes skill check)
        monkeypatch.setattr("magic.randint", lambda a, b: 50)

        orig_fun = SPELL_FUNS.get(SKILLS[armor_sn].get("spell_fun"))
        SPELL_FUNS[SKILLS[armor_sn]["spell_fun"]] = spy_armor
        try:
            do_cast(player, ["armor"])
        finally:
            if orig_fun:
                SPELL_FUNS[SKILLS[armor_sn]["spell_fun"]] = orig_fun

        expected_level = 3 * 20 // 4  # = 15
        assert captured.get("level") == expected_level, \
            "Multiclass with no casters should cast at 3*level/4, got %s" % captured.get("level")

    def test_level_20_scales_to_15(self, test_room, monkeypatch):
        """Verify exact math: level 20 scales to 15 (3*20/4)."""
        captured = {}

        def spy_armor(sn, level, ch, vo, target):
            captured["level"] = level
            return True

        armor_sn = _skill_lookup("armor")
        if armor_sn is None:
            pytest.skip("armor spell not in skill table")

        player = _make_player(level=20, classes=[CLASS_WARRIOR])
        player["id"] = 1
        player["learned"][armor_sn] = 50
        world.chars[1] = player
        test_room["mobs"] = []

        # Patch get_skill to return high value (will pass concentration check)
        monkeypatch.setattr("magic.get_skill", lambda ch, sn: 150)
        # Patch randint to return low value (passes skill check)
        monkeypatch.setattr("magic.randint", lambda a, b: 50)

        orig_fun = SPELL_FUNS.get(SKILLS[armor_sn].get("spell_fun"))
        SPELL_FUNS[SKILLS[armor_sn]["spell_fun"]] = spy_armor
        try:
            do_cast(player, ["armor"])
        finally:
            if orig_fun:
                SPELL_FUNS[SKILLS[armor_sn]["spell_fun"]] = orig_fun

        assert captured.get("level") == 15, \
            "Level 20 non-caster should scale to 15 (3*20//4), got %s" % captured.get("level")

    def test_level_50_scales_to_37(self, test_room, monkeypatch):
        """Verify exact math: level 50 scales to 37 (3*50//4 with truncation)."""
        captured = {}

        def spy_armor(sn, level, ch, vo, target):
            captured["level"] = level
            return True

        armor_sn = _skill_lookup("armor")
        if armor_sn is None:
            pytest.skip("armor spell not in skill table")

        player = _make_player(level=50, classes=[CLASS_WARRIOR])
        player["id"] = 1
        player["learned"][armor_sn] = 50
        world.chars[1] = player
        test_room["mobs"] = []

        # Patch get_skill to return high value (will pass concentration check)
        monkeypatch.setattr("magic.get_skill", lambda ch, sn: 150)
        # Patch randint to return low value (passes skill check)
        monkeypatch.setattr("magic.randint", lambda a, b: 50)

        orig_fun = SPELL_FUNS.get(SKILLS[armor_sn].get("spell_fun"))
        SPELL_FUNS[SKILLS[armor_sn]["spell_fun"]] = spy_armor
        try:
            do_cast(player, ["armor"])
        finally:
            if orig_fun:
                SPELL_FUNS[SKILLS[armor_sn]["spell_fun"]] = orig_fun

        # 3*50//4 = 150//4 = 37
        assert captured.get("level") == 37, \
            "Level 50 non-caster should scale to 37 (3*50//4), got %s" % captured.get("level")
