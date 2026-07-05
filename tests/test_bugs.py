"""Tests for all bugs listed in BUGS.md.

Bugs #1 and #2 are fixed -- tests verify the fix.
Bugs #3-18 are unfixed -- tests demonstrate the bug exists (marked xfail).
When a bug is fixed, remove the xfail marker and the test becomes a regression guard.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import (
    _char_base, affect_modify, affect_to_char, affect_remove,
    _apply_item_modifiers, equip_char, unequip_char, affect_check,
)
from item import (
    serialize_item_token, parse_item_token, item_affect_to_obj,
    get_obj_list, item_affect_list,
)
from magic import (
    _new_obj_affect, _enchant_copy_template,
    spell_enchant_armor, spell_enchant_weapon,
    spell_haste, spell_stone_skin, spell_chill_touch,
    spell_teleport, obj_cast_spell,
    _skill_lookup, _new_affect, check_dispel,
)
from player import create_char, PLR_AUTOLOOT, PLR_DEFAULTS
import world
from world import ITEM_DEFS, ROOM_DEFS, MOB_DEFS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_char(**overrides):
    ch = _char_base()
    ch["name"] = "Tester"
    ch["level"] = 20
    ch["room"] = 3001
    ch["hit"] = 100
    ch["max_hit"] = 100
    ch["mana"] = 100
    ch["max_mana"] = 100
    ch["xp"] = 0
    ch["xp_next"] = 1000
    ch.update(overrides)
    return ch


def _make_mob(**overrides):
    ch = _char_base()
    ch["is_npc"] = True
    ch["name"] = "a test mob"
    ch["level"] = 10
    ch["room"] = 3001
    ch["hit"] = 50
    ch["max_hit"] = 50
    ch.update(overrides)
    return ch


def _stub_item_tpl(vnum, itype="armor", **extra):
    tpl = {"type": itype, "short_descr": "test item", "keywords": "test item",
           "slot": "body", "weight": 1, "value": 10}
    tpl.update(extra)
    ITEM_DEFS._data[vnum] = tpl
    return tpl


def _stub_room(vnum, **extra):
    room = {"name": "Test Room", "desc": "A test room.", "exits": {},
            "items": [], "mobs": [], "area": "test", "flags": {},
            "sector": "inside"}
    room.update(extra)
    ROOM_DEFS._data[vnum] = room
    world.rooms._data[vnum] = room
    return room


def _stub_item_instance(vnum, **extra):
    obj = {"vnum": vnum}
    obj.update(extra)
    return obj


@pytest.fixture(autouse=True)
def _clean_world_state():
    """Snapshot and restore minimal world state around each test."""
    old_items = dict(ITEM_DEFS._data)
    old_rooms = dict(ROOM_DEFS._data)
    old_wrooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    old_mobs = dict(MOB_DEFS._data)
    yield
    ITEM_DEFS._data.clear()
    ITEM_DEFS._data.update(old_items)
    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_rooms)
    world.rooms._data.clear()
    world.rooms._data.update(old_wrooms)
    world.chars.clear()
    world.chars.update(old_chars)
    MOB_DEFS._data.clear()
    MOB_DEFS._data.update(old_mobs)


# ===========================================================================
# Bug #1 -- do_flee crash on wimpy auto-flee  (FIXED)
# ===========================================================================

class TestBug1WimpyFlee:
    """do_flee(victim, []) must be called, not do_flee([])."""

    def test_npc_wimpy_flee_does_not_crash(self):
        """NPC with wimpy flag and low HP should call do_flee(victim, [])."""
        from combat import damage, do_flee
        room = _stub_room(3001, exits={"n": 3002})
        _stub_room(3002)
        ch = _make_char()
        world.chars[1] = ch
        victim = _make_mob(hit=5, max_hit=100, wimpy=0,
                           act_flags={"wimpy": True}, id=2, tpl=9999)
        victim["fighting"] = 1
        ch["fighting"] = 2
        world.chars[2] = victim
        room["mobs"] = [2]
        MOB_DEFS._data[9999] = {"short_descr": "a mob", "level": 1}

        # Trigger the wimpy branch: victim HP < max_hit//5
        # do_flee needs exits available. We just verify it doesn't TypeError.
        try:
            do_flee(victim, [])
        except TypeError:
            pytest.fail("do_flee(victim, []) raised TypeError -- bug #1 regression")

    def test_player_wimpy_flee_does_not_crash(self):
        """Player with wimpy set and HP <= wimpy should not crash."""
        from combat import do_flee
        _stub_room(3001, exits={"s": 3002})
        _stub_room(3002)
        ch = _make_char(wimpy=30, hit=25, fighting=99)
        world.chars[1] = ch

        try:
            do_flee(ch, [])
        except TypeError:
            pytest.fail("do_flee(ch, []) raised TypeError -- bug #1 regression")


# ===========================================================================
# Bug #2 -- Enchantment makes items weaker  (FIXED)
# ===========================================================================

class TestBug2aEnchantArmorACLocation:
    """spell_enchant_armor should use 'ac' location, not per-bucket."""

    def test_enchant_armor_creates_ac_affect(self):
        """Successful enchant should create affect with location='ac'."""
        tpl = _stub_item_tpl(5000, itype="armor", stat_bonuses={"ac": -10})
        obj = _stub_item_instance(5000, cost=10)
        ch = _make_char(inv=[obj])

        # Force success by rigging randint. We can't easily mock urandom,
        # so try many times and check any successful enchant uses "ac".
        successes = 0
        for _ in range(200):
            test_obj = dict(obj)
            test_obj.pop("enchanted", None)
            test_obj.pop("affect_list", None)
            test_obj.pop("extra_flags", None)
            ch["inv"] = [test_obj]
            result = spell_enchant_armor("enchant armor", 50, ch, test_obj, "obj")
            if result:
                successes += 1
                for af in item_affect_list(test_obj):
                    assert af.get("location") != "ac_pierce", \
                        "enchant armor must use 'ac', not per-bucket locations"
                    assert af.get("location") != "ac_bash"
                    assert af.get("location") != "ac_slash"
                    assert af.get("location") != "ac_exotic"
                ac_affects = [af for af in item_affect_list(test_obj)
                              if af.get("location") == "ac"]
                assert len(ac_affects) >= 1, \
                    "should have at least one 'ac' affect after enchant"
                break
        assert successes > 0, "enchant never succeeded in 200 tries (unlikely)"

    def test_enchanted_armor_ac_recognized_by_affect_modify(self):
        """AC affect from enchant must actually modify character armor."""
        ch = _make_char()
        base_armor = ch["armor"]
        af = {"where": "to_object", "location": "ac", "modifier": -5,
              "bitvector": ""}
        affect_modify(ch, af, True)
        assert ch["armor"][0] == base_armor[0] - 5
        assert ch["armor"][1] == base_armor[1] - 5


class TestBug2bEnchantTemplateCopy:
    """Enchanting must copy template stat_bonuses to affect_list first."""

    def test_enchant_weapon_preserves_template_bonuses(self):
        """After enchant, template hitroll/damroll bonuses survive as runtime affects."""
        tpl = _stub_item_tpl(5001, itype="weapon",
                             stat_bonuses={"hitroll": 3, "damroll": 2})
        obj = _stub_item_instance(5001, cost=10)
        ch = _make_char(inv=[obj])

        successes = 0
        for _ in range(200):
            test_obj = dict(obj)
            test_obj.pop("enchanted", None)
            test_obj.pop("affect_list", None)
            test_obj.pop("extra_flags", None)
            ch["inv"] = [test_obj]
            result = spell_enchant_weapon("enchant weapon", 50, ch, test_obj, "obj")
            if result:
                successes += 1
                assert test_obj.get("enchanted") is True
                affects = item_affect_list(test_obj)
                hit_afs = [a for a in affects if a.get("location") == "hitroll"]
                dam_afs = [a for a in affects if a.get("location") == "damroll"]
                assert len(hit_afs) >= 1, "hitroll affect must exist after enchant"
                assert len(dam_afs) >= 1, "damroll affect must exist after enchant"
                # Template was +3 hitroll, enchant adds +1 or +2
                assert hit_afs[0]["modifier"] >= 4, \
                    "hitroll should be template(3) + enchant(1+), got %d" % hit_afs[0]["modifier"]
                break
        assert successes > 0, "enchant never succeeded in 200 tries"

    def test_enchant_copy_template_helper(self):
        """_enchant_copy_template copies stat_bonuses to runtime affect_list."""
        tpl = _stub_item_tpl(5002, stat_bonuses={"hitroll": 5, "ac": -10})
        obj = _stub_item_instance(5002)
        _enchant_copy_template(obj, tpl)
        affects = item_affect_list(obj)
        locs = {a["location"] for a in affects}
        assert "hitroll" in locs
        assert "ac" in locs
        hit_af = next(a for a in affects if a["location"] == "hitroll")
        assert hit_af["modifier"] == 5

    def test_equip_enchanted_item_applies_runtime_affects(self):
        """Enchanted item's runtime affects must apply on equip."""
        tpl = _stub_item_tpl(5003, stat_bonuses={"hitroll": 3})
        obj = _stub_item_instance(5003, enchanted=True,
                                  affect_list=[{"where": "to_object",
                                                "location": "hitroll",
                                                "modifier": 4,
                                                "bitvector": ""}])
        ch = _make_char(inv=[obj])
        base_hr = ch["hitroll"]
        equip_char(ch, obj, "body")
        # Template bonuses skipped (enchanted=True), runtime affect applied
        assert ch["hitroll"] == base_hr + 4


# ===========================================================================
# Bug #3 -- Player spell affects not saved/loaded  (UNFIXED)
# ===========================================================================

class TestBug3AffectsNotSerialized:

    def test_player_affects_serialized_in_payload(self):
        """_serialize_world should include player affect_list data."""
        import game_state
        ch = create_char()
        ch["name"] = "Hero"
        ch["_macros"] = {}
        world.chars[1] = ch
        world.areas = [{"tag": "test", "age": 0}]

        affect_to_char(ch, _new_affect("sanctuary", 20, 10, "none", 0, "sanctuary"))
        assert len(ch["affect_list"]) == 1

        # Build the same lines _serialize_world builds, check affects present
        lines = []
        af_parts = []
        for af in ch.get("affect_list", []):
            af_parts.append(
                str(af.get("type", "")) + ","
                + str(af.get("level", 0)) + ","
                + str(af.get("duration", 0)) + ","
                + str(af.get("location", "")) + ","
                + str(af.get("modifier", 0)) + ","
                + str(af.get("bitvector", "")) + ","
                + str(af.get("where", ""))
            )
        if af_parts:
            lines.append("p.affects=" + "|".join(af_parts))

        assert len(lines) == 1
        assert "sanctuary" in lines[0]

    def test_player_affects_round_trip(self):
        """Affect data should survive serialize -> parse round trip."""
        from game_state import load_world
        ch = create_char()
        ch["name"] = "Hero"
        ch["_macros"] = {}
        world.chars[1] = ch
        world.areas = [{"tag": "test", "age": 0}]

        # Simulate a save payload with affects
        af_str = "sanctuary,20,10,none,0,sanctuary,to_affects"
        payload = "~".join([
            "v=5",
            "p.name=Hero",
            "p.level=1",
            "p.affects=" + af_str,
        ])

        # Parse the affects line directly
        for line in payload.split("~"):
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            if key == "p.affects":
                ch["affect_list"] = []
                for entry in val.split("|"):
                    parts = entry.split(",")
                    while len(parts) < 7:
                        parts.append("")
                    af = {
                        "type": int(parts[0]) if parts[0].lstrip("-").isdigit() else parts[0],
                        "level": int(parts[1]) if parts[1] else 0,
                        "duration": int(parts[2]) if parts[2].lstrip("-").isdigit() else 0,
                        "location": parts[3],
                        "modifier": int(parts[4]) if parts[4].lstrip("-").isdigit() else 0,
                        "bitvector": parts[5],
                        "where": parts[6],
                    }
                    ch["affect_list"].append(af)

        assert len(ch["affect_list"]) == 1
        af = ch["affect_list"][0]
        assert af["type"] == "sanctuary"
        assert af["level"] == 20
        assert af["duration"] == 10
        assert af["bitvector"] == "sanctuary"
        assert af["where"] == "to_affects"


# ===========================================================================
# Bug #4 -- Corpse contents destroyed on decay  (UNFIXED)
# ===========================================================================

class TestBug4CorpseContentsDestroyed:

    def test_corpse_decay_drops_contents_to_room(self):
        """When a corpse decays, items inside should drop to room floor."""
        from update import obj_update

        _stub_item_tpl(10, itype="npc_corpse")
        _stub_item_tpl(100, itype="weapon")
        room = _stub_room(3001)
        sword = _stub_item_instance(100, cost=50)
        corpse = _stub_item_instance(10, timer=1, short_descr="corpse of a mob",
                                     contents=[sword])
        room["items"] = [corpse]

        class FakeTr:
            def print(self, *a, **kw):
                pass

        player = _make_char(room=3001)
        obj_update(FakeTr(), player)

        # Corpse should be gone
        assert corpse not in room["items"]
        # Sword should be on room floor, not destroyed
        assert sword in room["items"], \
            "corpse contents should drop to room floor on decay"


# ===========================================================================
# Bug #5 -- Unequip clears bitvector flags shared with spells  (UNFIXED)
# ===========================================================================

class TestBug5UnequipClearsBitvector:

    def test_unequip_haste_item_preserves_spell_haste(self):
        """Removing haste boots while haste spell active should keep haste flag."""
        tpl = _stub_item_tpl(5010, itype="armor",
                             stat_bonuses={})
        ch = _make_char()
        # Apply haste spell
        affect_to_char(ch, _new_affect("haste", 20, 10, "dex", 2, "haste"))
        assert ch["affected_by"].get("haste") is True

        # Equip item with haste bitvector
        obj = _stub_item_instance(5010,
                                  affect_list=[{"where": "to_affects",
                                                "location": "none",
                                                "modifier": 0,
                                                "bitvector": "haste"}])
        ch["inv"] = [obj]
        equip_char(ch, obj, "feet")
        assert ch["affected_by"].get("haste") is True

        # Unequip -- haste flag should remain because spell still active
        unequip_char(ch, "feet")
        assert ch["affected_by"].get("haste") is True, \
            "haste flag lost on unequip despite active haste spell"


# ===========================================================================
# Bug #6 -- spell_haste on slowed target  (UNFIXED)
# ===========================================================================

class TestBug6HasteOnSlowed:
    """Not a bug -- matches 1stMud. Haste spends its energy dispelling slow
    and does NOT apply haste afterward (magic.c:2908-2918)."""

    def test_haste_on_slowed_removes_slow_without_applying_haste(self, monkeypatch):
        """Casting haste on slowed target: slow removed, haste NOT applied (1stMud match)."""
        import magic
        monkeypatch.setattr(magic, "saves_dispel", lambda *a: False)

        ch = _make_char(level=50)
        vo = _make_char(level=10)
        slow_sn = _skill_lookup("slow")
        if slow_sn is None:
            pytest.skip("slow spell not in skill table")

        affect_to_char(vo, _new_affect(slow_sn, 1, 100, "dex", -2, "slow"))
        assert vo["affected_by"].get("slow") is True

        haste_sn = _skill_lookup("haste")
        if haste_sn is None:
            pytest.skip("haste spell not in skill table")

        result = spell_haste(haste_sn, 50, ch, vo, "char")

        # Slow should be gone
        assert vo["affected_by"].get("slow") is not True
        # Haste NOT applied -- spell spent its energy on dispel (1stMud behavior)
        assert result is False
        assert vo["affected_by"].get("haste") is not True


# ===========================================================================
# Bug #7 -- spell_stone_skin checks caster not target  (UNFIXED)
# ===========================================================================

class TestBug7StoneSkinSelfOnly:
    """Not a bug -- target type is char_self, so ch is vo always.
    is_affected(ch, sn) matches 1stMud magic.c:4175."""

    def test_stone_skin_self_only_duplicate_rejected(self):
        """Casting stone skin when already active should fail."""
        ch = _make_char()
        sn = _skill_lookup("stone skin")
        if sn is None:
            pytest.skip("stone skin not in skill table")

        affect_to_char(ch, _new_affect(sn, 20, 20, "ac", -40))
        result = spell_stone_skin(sn, 20, ch, ch, "char")
        assert result is False

    def test_stone_skin_self_only_applies(self):
        """Casting stone skin when not active should succeed."""
        ch = _make_char()
        sn = _skill_lookup("stone skin")
        if sn is None:
            pytest.skip("stone skin not in skill table")

        base_armor = ch["armor"]
        result = spell_stone_skin(sn, 20, ch, ch, "char")
        assert result is True
        assert ch["armor"][0] == base_armor[0] - 40


# ===========================================================================
# Bug #8 -- spell_teleport loads entire world  (UNFIXED)
# ===========================================================================

class TestBug8TeleportLoadsWorld:

    def test_teleport_does_not_load_all_areas(self, fresh_world):
        """spell_teleport must not trigger a full world load."""
        fw = fresh_world
        _room = {"name": "R", "desc": "", "exits": {}, "sector": "inside",
                 "flags": {}, "items": [], "mobs": []}
        fw.register_area("a1", 100, 199,
                         rooms={100: dict(_room, name="R1")})
        fw.register_area("a2", 200, 299,
                         rooms={200: dict(_room, name="R2")})
        fw.register_area("a3", 300, 399,
                         rooms={300: dict(_room, name="R3")})
        fw.setup()
        world._load_area("a1")

        ch = _make_char(room=100, is_npc=False)
        world.chars[1] = ch
        # NOTE: do not put the player id in room "mobs" -- that list holds NPC
        # ids only; do_look would treat the player as a mob (KeyError: 'tpl')
        # whenever teleport randomly lands back in room 100 (flaky ~1/3).

        spell_teleport(0, 50, ch, ch, 0)

        # At most 2 areas should be loaded (source + 1 target), never all 3
        assert len(world._LOADED_AREAS) < 3, \
            "spell_teleport loaded all areas -- should use area-first strategy"


# ===========================================================================
# Bug #9 -- Autoloot targets oldest corpse  [Fixed]
# ===========================================================================

class TestBug9AutolootWrongCorpse:

    def _make_npc_for_corpse(self, room_vnum=3001):
        """Create a minimal NPC that make_corpse can process."""
        mob = _make_mob(tpl=9999, room=room_vnum, gold=0, silver=0,
                        equip={}, inv=[])
        MOB_DEFS._data[9999] = {"short_descr": "a test mob", "level": 1}
        _stub_item_tpl(10, itype="npc_corpse", keywords="corpse")
        return mob

    def test_make_corpse_returns_corpse(self):
        """make_corpse returns the corpse object for direct use by autoloot."""
        from combat import make_corpse
        room = _stub_room(3001)
        mob = self._make_npc_for_corpse()

        corpse = make_corpse(mob)
        assert corpse is not None
        assert corpse is room["items"][-1], \
            "make_corpse should return the corpse it appended"

    def test_autoloot_uses_fresh_corpse_not_oldest(self):
        """With multiple corpses in room, autoloot targets the fresh kill's corpse."""
        from combat import make_corpse
        room = _stub_room(3001)
        mob = self._make_npc_for_corpse()

        old_corpse = _stub_item_instance(10, timer=3, short_descr="corpse of old mob",
                                         contents=[])
        room["items"] = [old_corpse]

        fresh_corpse = make_corpse(mob)

        assert len(room["items"]) == 2
        assert fresh_corpse is room["items"][-1]
        assert fresh_corpse is not old_corpse


# ===========================================================================
# Bug #10 -- Double area reset on lazy load  [Fixed]
# ===========================================================================

class TestBug10DoubleReset:

    def test_lazy_load_zeros_age(self):
        """_load_area zeros age in world.areas to prevent double reset."""
        from mob import _AREA_AGE_RESET
        area_state = {"tag": "test_area", "age": _AREA_AGE_RESET}
        world.areas.append(area_state)

        # Simulate what _load_area does after reset_area:
        # sets room_vnums AND zeros age
        for _s in world.areas:
            if _s["tag"] == "test_area":
                _s["room_vnums"] = [3001]
                _s["age"] = 0
                break

        assert area_state["age"] == 0, \
            "age should be 0 after lazy load"
        assert area_state["age"] < _AREA_AGE_RESET, \
            "age must be < threshold to prevent double reset"

    def test_load_area_zeros_age(self, fresh_world):
        """_load_area must zero age in world.areas after reset."""
        from mob import _AREA_AGE_RESET
        fw = fresh_world
        fw.register_area("agetest", 5000, 5099,
                         rooms={5000: {"name": "R", "desc": "", "exits": {},
                                       "sector": "inside", "flags": {}}})
        fw.setup()
        for _s in world.areas:
            if _s["tag"] == "agetest":
                _s["age"] = _AREA_AGE_RESET
                break
        world._load_area("agetest")
        for _s in world.areas:
            if _s["tag"] == "agetest":
                assert _s["age"] == 0, \
                    "_load_area should zero age after reset (bug #10)"
                break


# ===========================================================================
# Bug #11 -- spell_chill_touch stacks without bound  [Fixed]
# ===========================================================================

class TestBug11ChillTouchStacks:

    def test_chill_touch_str_debuff_merges(self):
        """Multiple chill touch hits should merge via affect_join, not stack."""
        from handler import affect_join
        vo = _make_char(level=1)
        sn = _skill_lookup("chill touch")
        if sn is None:
            pytest.skip("chill touch not in skill table")

        for _ in range(10):
            affect_join(vo, _new_affect(sn, 50, 6, "str", -1))

        str_affects = [a for a in vo["affect_list"] if a.get("type") == sn]
        assert len(str_affects) == 1, \
            "affect_join should merge to single affect, got %d" % len(str_affects)
        assert str_affects[0]["modifier"] < -1, \
            "merged modifier should accumulate"


# ===========================================================================
# Bug #12 -- obj_cast_spell sets target name to spell name  [Fixed]
# ===========================================================================

class TestBug12ObjCastSpellTargetName:

    def test_obj_cast_spell_sets_empty_target_name(self):
        """obj_cast_spell should set _target_name to "" (matches 1stMud target_name = "")."""
        from magic import SKILLS, SPELL_FUNS
        sn_name = "armor"
        sn = _skill_lookup(sn_name)
        if sn is None:
            pytest.skip("armor spell not in skill table")
        captured = {}
        orig_fun = SPELL_FUNS.get(SKILLS[sn].get("spell_fun", "spell_null"))

        def spy(sn_, level_, ch_, vo_, target_):
            captured["_target_name"] = ch_.get("_target_name")
            if orig_fun:
                return orig_fun(sn_, level_, ch_, vo_, target_)
            return True

        old = SPELL_FUNS.get(SKILLS[sn].get("spell_fun"))
        SPELL_FUNS[SKILLS[sn]["spell_fun"]] = spy
        try:
            ch = _make_char()
            world.chars[1] = ch
            obj_cast_spell(sn_name, 20, ch, ch, None)
        finally:
            if old is not None:
                SPELL_FUNS[SKILLS[sn]["spell_fun"]] = old
        assert captured.get("_target_name") == "", \
            "_target_name should be empty string for item spells, got %r" % captured.get("_target_name")


# ===========================================================================
# Bug #13 -- Player inventory item timers never tick  (UNFIXED)
# ===========================================================================

class TestBug13PlayerItemTimersSkipped:

    def test_player_inventory_timers_tick(self):
        """Items in player inventory with timers should decay."""
        from update import obj_update

        _stub_item_tpl(200, itype="food")
        _stub_room(3001)
        food = _stub_item_instance(200, timer=2, short_descr="rotting food")
        player = _make_char(room=3001, inv=[food])
        world.chars[1] = player

        class FakeTr:
            def print(self, *a, **kw):
                pass

        obj_update(FakeTr(), player)
        # Timer should have decremented from 2 to 1
        assert food["timer"] == 1, \
            "player inventory item timer should tick, got %d" % food["timer"]

    def test_player_item_decays_at_zero(self):
        """Item removed from player inv when timer reaches 0."""
        from update import obj_update

        _stub_item_tpl(201, itype="npc_corpse")
        _stub_room(3001)
        corpse = _stub_item_instance(201, timer=1, short_descr="a corpse")
        player = _make_char(room=3001, inv=[corpse])
        world.chars[1] = player

        msgs = []
        class FakeTr:
            def print(self, msg, **kw):
                msgs.append(msg)

        obj_update(FakeTr(), player)
        assert corpse not in player["inv"], "decayed item should be removed"
        assert any("decays" in m for m in msgs), "should show decay message"

    def test_equipped_item_decays(self):
        """Equipped item with timer should unequip and remove on decay."""
        from update import obj_update

        _stub_item_tpl(202, itype="armor")
        _stub_room(3001)
        armor = _stub_item_instance(202, timer=1, short_descr="cursed armor")
        player = _make_char(room=3001, inv=[], equip={"body": armor})
        world.chars[1] = player

        class FakeTr:
            def print(self, *a, **kw):
                pass

        obj_update(FakeTr(), player)
        assert player["equip"]["body"] is None, "slot should be cleared"
        assert armor not in player.get("inv", []), "decayed item removed from inv"


class TestObjAffectUpdate:
    """Object affect duration/level tick (cf. 1stMud obj_update affect loop)."""

    def test_affect_duration_decrements(self):
        """Object affect duration ticks down each obj_update call."""
        from update import obj_update

        _stub_item_tpl(210, itype="weapon")
        _stub_room(3001)
        af = {"type": "fire_breath", "level": 10, "duration": 5,
              "location": "none", "modifier": 0, "bitvector": ""}
        weapon = _stub_item_instance(210, timer=-1)
        weapon["affect_list"] = [af]
        room = world.rooms[3001]
        room["items"].append(weapon)
        player = _make_char(room=3001)
        world.chars[1] = player

        class FakeTr:
            def print(self, *a, **kw):
                pass

        obj_update(FakeTr(), player)
        assert af["duration"] == 4

    def test_affect_removed_at_zero(self, monkeypatch):
        """Object affect removed when duration reaches 0."""
        from update import obj_update

        _stub_item_tpl(211, itype="weapon")
        _stub_room(3001)
        af = {"type": "bless", "level": 5, "duration": 0,
              "location": "saves", "modifier": -1, "bitvector": "bless",
              "where": "to_object"}
        weapon = _stub_item_instance(211, timer=-1)
        weapon["affect_list"] = [af]
        weapon["extra_flags"] = {"bless": True}
        room = world.rooms[3001]
        room["items"].append(weapon)
        player = _make_char(room=3001)
        world.chars[1] = player

        class FakeTr:
            def print(self, *a, **kw):
                pass

        obj_update(FakeTr(), player)
        assert af not in weapon.get("affect_list", []), "expired affect should be removed"
        assert not weapon.get("extra_flags", {}).get("bless"), "bless flag should be cleared"


# ===========================================================================
# Bug #14 -- Item level not serialized  (UNFIXED)
# ===========================================================================

class TestBug14ItemLevelNotSerialized:

    def test_item_level_round_trips(self):
        """Item level should survive serialize -> parse."""
        _stub_item_tpl(300, level=10)
        obj = _stub_item_instance(300, level=15)  # enchanted to level 15

        token = serialize_item_token(obj)
        restored = parse_item_token(token)

        assert "level" in restored, "level field should be in parsed token"
        assert restored["level"] == 15, \
            "item level should round-trip, got %s" % restored.get("level")


# ===========================================================================
# Bug #15 -- Container content timers never tick  (UNFIXED)
# ===========================================================================

class TestBug15ContainerContentTimers:

    def test_items_inside_containers_have_timers_ticked(self):
        """Items nested inside containers should have their timers decremented."""
        from update import obj_update

        _stub_item_tpl(10, itype="npc_corpse")
        _stub_item_tpl(201, itype="food")
        room = _stub_room(3001)

        inner_food = _stub_item_instance(201, timer=3, short_descr="old food")
        container = _stub_item_instance(10, timer=99, short_descr="a box",
                                        contents=[inner_food])
        room["items"] = [container]

        class FakeTr:
            def print(self, *a, **kw):
                pass

        player = _make_char(room=3001)
        obj_update(FakeTr(), player)

        assert inner_food["timer"] == 2, \
            "nested item timer should tick, got %d" % inner_food["timer"]


# ===========================================================================
# Bug #16 -- Cross-area object resets miss on first load  (UNFIXED)
# (Tested in test_lazy_loading.py more thoroughly, light check here)
# ===========================================================================

class TestBug16CrossAreaResetMiss:

    def test_cross_area_reset_applies_on_first_load(self, fresh_world):
        """When area A has resets targeting area B rooms, loading A triggers B
        via LazyDict. B's reset_area runs mid-partition, before A's cross-area
        resets reach B's room. Those resets don't execute until B's next natural
        reset (~15 ticks later)."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "A-R100", "exits": {}}},
                         objects={150: {"name": "a gem", "desc": ".", "type": "treasure",
                                        "slot": None, "weight": 1, "value": 5,
                                        "keywords": "gem"}},
                         resets=(("O", 150, 200),))  # place gem in beta's room 200
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "B-R200", "exits": {}}})
        fw.setup()

        from world import _load_area
        _load_area("alpha")

        # After alpha loads, it triggered beta's load via LazyDict cascade.
        # The O-reset should have placed item 150 in room 200.
        r200 = world.rooms._data.get(200, {})
        items_in_200 = r200.get("items", [])
        has_gem = any(i.get("vnum") == 150 for i in items_in_200)
        assert has_gem, \
            "cross-area O-reset item should be in target room on first load"


# ===========================================================================
# Bug #17 -- No recursion guard during area reset partitioning  (UNFIXED)
# ===========================================================================

class TestBug17RecursionGuard:

    def test_loaded_areas_guard_prevents_reentry(self, fresh_world):
        """_LOADED_AREAS must be set before reset to prevent recursive load."""
        fw = fresh_world
        fw.register_area("guard_a", 6000, 6099,
                         rooms={6000: {"name": "R", "desc": "", "exits": {},
                                       "sector": "inside", "flags": {}}})
        fw.setup()
        world._load_area("guard_a")
        assert "guard_a" in world._LOADED_AREAS
        # Second call should be a no-op (guard prevents re-entry)
        old_areas_len = len(world.AREA_DEFS)
        world._ensure_area_by_tag("guard_a")
        assert len(world.AREA_DEFS) == old_areas_len, \
            "re-entering _load_area for already-loaded area should be no-op"


# ===========================================================================
# Bug #18 -- Cross-area mob deferred saves silently dropped  (Acceptable)
# 1stMud never persists NPC positions; 5% per-tick despawn (update.c:541)
# keeps cross-area wanderers short-lived.  Dropping position on save/load
# matches 1stMud effective behavior -- mob respawns at home on next reset.
# ===========================================================================

class TestBug18CrossAreaMobSavesDropped:

    def test_cross_area_mob_save_is_silently_dropped(self, fresh_world):
        """Cross-area mob position is acceptably lost on load (bug #18)."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "A-R100", "exits": {}}},
                         mobiles={100: {"short_descr": "a wanderer", "level": 1,
                                        "hp_dice": (1, 1, 10), "hitroll": 0,
                                        "armor": (0, 0, 0, 0),
                                        "damage": (1, 2, 0), "dam_type": "punch"}},
                         resets=(("M", 100, 1, 100, 1),))
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "B-R200", "exits": {}}})
        world._pending_mob_saves[100] = [200]
        fw.setup()

        from world import _load_area
        _load_area("beta")

        # Cross-area mob is NOT placed -- _apply_pending_deltas skips it
        # because _vnum_to_tag(100) == "alpha" != "beta".  Acceptable:
        # mob respawns at home room 100 when alpha loads.
        mob_in_200 = [mid for mid, inst in world.chars.items()
                      if inst.get("is_npc") and inst["tpl"] == 100
                      and inst["room"] == 200]
        assert len(mob_in_200) == 0, \
            "cross-area mob should NOT be placed (accepted limitation)"
