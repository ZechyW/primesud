"""Tests for the class system (classes.py) against 1stMud multiclass.c semantics."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "primesud.hpappdir")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from classes import (
    CLASS_MAGE, CLASS_CLERIC, CLASS_THIEF, CLASS_WARRIOR,
    CLASS_TABLE, skill_level, skill_rating, can_use_skill_spell,
    has_spells, get_thac00, get_thac32, exp_per_level, get_hp_gain,
    lvl_bonus, class_long,
)
from combat import get_thac0, interpolate, _cdiv
from config import LEVEL_IMMORTAL
from player import create_char
from skills_table import SKILLS, GSN_BASH, GSN_SANCTUARY, WEAPON_GSN_MAP


def _pc(*cls, **kw):
    ch = {"is_npc": False, "level": kw.get("level", 1), "classes": list(cls),
          "race": "Human"}
    return ch


class TestClassLookups:
    def test_skill_level_uses_best_class(self):
        mage    = _pc(CLASS_MAGE)
        warrior = _pc(CLASS_WARRIOR)
        multi   = _pc(CLASS_MAGE, CLASS_WARRIOR)
        bash_lv = SKILLS[GSN_BASH]["skill_level"]
        assert bash_lv[CLASS_MAGE] == 53      # data premise: mage never learns bash
        assert skill_level(warrior, GSN_BASH) == bash_lv[CLASS_WARRIOR]
        # unavailable classes return the raw 53 (ANGEL), not a sentinel --
        # matches 1stMud skill_level, which only maps "no classes at all" to 52
        assert skill_level(mage, GSN_BASH) == 53
        assert skill_level(multi, GSN_BASH) == bash_lv[CLASS_WARRIOR]

    def test_skill_level_no_classes_returns_immortal(self):
        assert skill_level({"is_npc": False, "race": "Human"}, GSN_BASH) == LEVEL_IMMORTAL

    def test_skill_rating_ignores_zero_ratings(self):
        multi = _pc(CLASS_MAGE, CLASS_WARRIOR)
        # bash: mage rating 0 must not shadow warrior's positive rating
        assert SKILLS[GSN_BASH]["rating"][CLASS_MAGE] == 0  # data premise
        assert skill_rating(multi, GSN_BASH) == SKILLS[GSN_BASH]["rating"][CLASS_WARRIOR]

    def test_can_use_gates_by_level(self):
        # bash is warrior level 1 in 1stMud data; mage 53 -> never usable
        warrior = _pc(CLASS_WARRIOR, level=1)
        mage    = _pc(CLASS_MAGE, level=51)
        assert can_use_skill_spell(warrior, GSN_BASH)
        assert not can_use_skill_spell(mage, GSN_BASH)
        # sanctuary: warrior CAN learn it (level 30) -- 1stMud data is
        # permissive; class identity is level/rating gaps, not hard locks
        w30 = _pc(CLASS_WARRIOR, level=30)
        assert not can_use_skill_spell(_pc(CLASS_WARRIOR, level=29), GSN_SANCTUARY)
        assert can_use_skill_spell(w30, GSN_SANCTUARY)

    def test_has_spells_fixed_upstream_bug(self):
        # 1stMud bug: class_table[i] instead of class_table[Class[i]] made
        # every single-class char a caster. Warrior must NOT be one.
        assert has_spells(_pc(CLASS_MAGE))
        assert not has_spells(_pc(CLASS_WARRIOR))
        assert not has_spells(_pc(CLASS_THIEF))
        assert has_spells(_pc(CLASS_WARRIOR, CLASS_CLERIC))


class TestThac0:
    def test_interpolate_truncates_toward_zero(self):
        # C: 20 + 1*(-30)/32 = 20 (trunc); Python floor would give 19
        assert interpolate(1, 20, -10) == 20
        assert _cdiv(-27, 2) == -13  # floor would give -14

    def test_player_curves(self):
        warrior = _pc(CLASS_WARRIOR, level=32)
        mage    = _pc(CLASS_MAGE, level=32)
        # warrior: interpolate -> -10, /2 -> -5, second cap not triggered
        assert get_thac0(warrior) == -5
        assert get_thac0(mage) == 6

    def test_multiclass_takes_worst00_best32(self):
        multi = _pc(CLASS_MAGE, CLASS_WARRIOR)
        assert get_thac00(multi) == 20
        assert get_thac32(multi) == -10

    def test_npc_act_flag_curves(self):
        mob = {"is_npc": True, "level": 32, "act_flags": {"warrior": True}}
        assert get_thac0(mob) == -5
        mob["act_flags"] = {"mage": True}
        assert get_thac0(mob) == 6
        mob["act_flags"] = {}  # default thac0_32 = -4
        assert get_thac0(mob) == -4 // 2


class TestProgression:
    def test_exp_per_level_human_flat(self):
        assert exp_per_level(_pc(CLASS_MAGE)) == 1000

    def test_hp_gain_within_class_die(self):
        warrior = _pc(CLASS_WARRIOR)
        c = CLASS_TABLE[CLASS_WARRIOR]
        for _ in range(50):
            g = get_hp_gain(warrior)
            assert c["hp_min"] <= g <= c["hp_max"] + 1  # +count fuzz

    def test_lvl_bonus_matches_float_reference(self):
        # cf. 1stMud float loop: level 1 -> 1.09 -> 1; level 10 -> 10.405 -> 10
        assert lvl_bonus(_pc(CLASS_WARRIOR, level=1)) == 1
        assert lvl_bonus(_pc(CLASS_WARRIOR, level=10)) == 10

    def test_class_long_tiers(self):
        assert class_long(_pc(CLASS_MAGE)) == "Mage"
        assert class_long(_pc(CLASS_MAGE, CLASS_CLERIC)) == "Wizard/Priest"


class TestCreateChar:
    def test_learned_filtered_by_class(self):
        mage = create_char(CLASS_MAGE)
        warrior = create_char(CLASS_WARRIOR)
        assert mage["classes"] == [CLASS_MAGE]
        # bash is warrior-only: mage must not start with it
        assert GSN_BASH not in mage["learned"]
        assert GSN_BASH in warrior["learned"]
        # every granted skill must be learnable by the class (weapon exempt)
        weapon_gsn = WEAPON_GSN_MAP["sword"]
        for sn in warrior["learned"]:
            d = SKILLS[sn]
            assert sn == weapon_gsn or (
                d["skill_level"][CLASS_WARRIOR] <= 51
                and d["rating"][CLASS_WARRIOR] > 0)

    def test_class_weapon_starts_at_40(self):
        mage = create_char(CLASS_MAGE)
        warrior = create_char(CLASS_WARRIOR)
        assert mage["learned"][WEAPON_GSN_MAP["dagger"]] == 40
        assert warrior["learned"][WEAPON_GSN_MAP["sword"]] == 40

    def test_xp_next_from_class_mult(self):
        assert create_char(CLASS_MAGE)["xp_next"] == 1000


class TestGuildRooms:
    """Guild-room entry restriction (cf. 1stMud act_move.c guild check)."""

    def _setup_rooms(self):
        import world
        from world import ROOM_DEFS
        base = {"desc": "x", "items": [], "mobs": [], "area": "test",
                "sector": "inside", "flags": {}}
        r1 = dict(base, name="Street", exits={"n": 3018})
        r2 = dict(base, name="Mage's Bar", exits={"s": 3001}, guild=(CLASS_MAGE,))
        for vnum, room in ((3001, r1), (3018, r2)):
            ROOM_DEFS._data[vnum] = room
            world.rooms._data[vnum] = room
        return world

    def test_non_member_blocked_member_allowed(self):
        from movement import move_char
        world = self._setup_rooms()
        try:
            for cls, expected_room in ((CLASS_WARRIOR, 3001), (CLASS_MAGE, 3018)):
                player = create_char(cls)
                player["room"] = 3001
                world.chars[1] = player
                world.rooms._data[3001]["mobs"] = []
                move_char(player, "n")
                assert player["room"] == expected_room, cls
        finally:
            for vnum in (3001, 3018):
                world.rooms._data.pop(vnum, None)
                from world import ROOM_DEFS
                ROOM_DEFS._data.pop(vnum, None)
            world.chars.pop(1, None)

    def test_paladin_shares_cleric_guild(self):
        # "guild" fields are patched into the generated area data by
        # patch_1stmud_deltas; check the artifact without booting the world
        path = os.path.join(ROOT, _SRC, "area_midgaard.dat")
        with open(path) as f:
            text = f.read()
        assert '"guild": (1, 4),' in text  # cleric rooms shared with paladin
        assert '"guild": (3, 5),' in text  # warrior rooms shared with ranger
        assert '"guild": (0,),' in text    # mage rooms mage-only


class TestRemort:
    """do_remort / finish_remort (cf. 1stMud multiclass.c)."""

    def _hero(self, monkeypatch, pick=0):
        """Max-level warrior in his guild with a trainer, rich, at 3022."""
        import world
        from world import ROOM_DEFS, MOB_DEFS
        from classes import calc_max_level

        room = {"name": "Bar of Swordsmen", "desc": "x", "items": [], "mobs": [2],
                "area": "test", "sector": "inside", "flags": {}, "exits": {},
                "guild": (CLASS_WARRIOR,)}
        ROOM_DEFS._data[3022] = room
        world.rooms._data[3022] = room
        MOB_DEFS._data[9900] = {"short_descr": "the guildmaster", "level": 60,
                                "act_flags": {"train": True}}
        trainer = {"is_npc": True, "id": 2, "tpl": 9900, "room": 3022}
        world.chars[2] = trainer

        player = create_char(CLASS_WARRIOR)
        player["room"] = 3022
        player["gold"] = 500000
        player["quest_points"] = 500  # remort gate (cf. 1stMud do_remort)
        player["level"] = calc_max_level(player)
        world.chars[1] = player

        import training
        monkeypatch.setattr(training, "pick_from", lambda t, o: pick)
        monkeypatch.setattr(training, "save_world", lambda quiet=False: True,
                            raising=False)
        # school outfit items not loaded in the test world
        monkeypatch.setattr(training, "do_outfit", lambda p, a: None)
        return player

    def _teardown(self):
        import world
        from world import ROOM_DEFS, MOB_DEFS
        ROOM_DEFS._data.pop(3022, None)
        world.rooms._data.pop(3022, None)
        MOB_DEFS._data.pop(9900, None)
        world.chars.pop(1, None)
        world.chars.pop(2, None)

    def test_remort_full_flow(self, monkeypatch):
        import training
        from classes import calc_max_level
        # patch the function-level import target
        import game_state
        monkeypatch.setattr(game_state, "save_world", lambda quiet=False: True)
        player = self._hero(monkeypatch, pick=0)  # first available = Mage
        try:
            old_cap = calc_max_level(player)
            training.do_remort(player, [])          # confirm prompt
            assert player["confirm_remort"] is True
            training.do_remort(player, [])          # confirmed -> picker -> remort
            assert player["classes"] == [CLASS_WARRIOR, CLASS_MAGE]
            assert player["level"] == 1
            assert player["gold"] == 0
            assert player["xp"] == 0
            # b = lvl_bonus at level 49 with the new class already appended
            # (2 classes): 2 + 48*.9 + inclev sums = 60.194 -> 60 (cf. 1stMud
            # nanny appends class before finish_remort computes b)
            assert player["max_hit"] == player["perm_hit"] == 6000
            assert player["train"] == 5 * (player["max_hit"] // 100)
            assert player["practice"] == 7 * (player["max_hit"] // 100)
            # level cap grew by one
            assert calc_max_level(player) == old_cap + 1
            # mage skills granted at 1%
            assert player["learned"].get(GSN_SANCTUARY, 0) >= 1
            # in-progress skills reset to 1 (weapon was 40 -> but dagger set to 40)
            assert player["learned"][WEAPON_GSN_MAP["dagger"]] == 40
            assert player["learned"][WEAPON_GSN_MAP["sword"]] == 1
            assert player["room"] == 3700 or player["room"] != 3022  # moved to school
        finally:
            self._teardown()

    def test_remort_refused_when_not_max_level(self, monkeypatch):
        import training
        player = self._hero(monkeypatch)
        player["level"] = 10
        try:
            training.do_remort(player, [])
            assert "confirm_remort" not in player or not player["confirm_remort"]
            assert player["classes"] == [CLASS_WARRIOR]
        finally:
            self._teardown()

    def test_remort_refused_outside_guild(self, monkeypatch):
        import training
        from world import ROOM_DEFS
        import world
        player = self._hero(monkeypatch)
        street = {"name": "Street", "desc": "x", "items": [], "mobs": [],
                  "area": "test", "sector": "inside", "flags": {}, "exits": {}}
        ROOM_DEFS._data[3001] = street
        world.rooms._data[3001] = street
        player["room"] = 3001
        try:
            training.do_remort(player, [])
            assert not player.get("confirm_remort")
        finally:
            ROOM_DEFS._data.pop(3001, None)
            world.rooms._data.pop(3001, None)
            self._teardown()

    def test_remort_cap(self, monkeypatch):
        import training
        player = self._hero(monkeypatch)
        player["classes"] = [CLASS_WARRIOR, CLASS_MAGE]
        try:
            training.do_remort(player, [])
            assert not player.get("confirm_remort")
            assert len(player["classes"]) == 2
        finally:
            self._teardown()
