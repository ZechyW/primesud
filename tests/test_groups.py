"""Tests for skill groups (groups.py) and do_gain against 1stMud skills.c."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import handler
import groups as groups_mod
import world
from classes import (CLASS_MAGE, CLASS_CLERIC, CLASS_THIEF, CLASS_WARRIOR,
                     CLASS_TABLE)
from groups import (GROUP_TABLE, GROUP_SKILLS, GROUP_SUBGROUPS, gn_add,
                    group_lookup, group_rating, do_grlist)
from player import create_char
from skills_table import SKILLS, GSN_BASH, GSN_SANCTUARY, GSN_RECALL, WEAPON_GSN_MAP


def _sn(name):
    for sn, sk in SKILLS.items():
        if sk["name"] == name:
            return sn
    raise KeyError(name)


class TestGroupData:
    def test_all_ratings_are_six_tuples(self):
        for name, ratings, members in GROUP_TABLE:
            assert len(ratings) == len(CLASS_TABLE), name

    def test_rom_basics_free_for_all(self):
        gn = group_lookup("rom basics")
        assert GROUP_TABLE[gn][1] == (0, 0, 0, 0, 0, 0)

    def test_members_resolved(self):
        # import-time resolution raises on unknown names; spot-check contents
        gn = group_lookup("protective")
        assert GSN_SANCTUARY in GROUP_SKILLS[gn]
        gn = group_lookup("mage default")
        assert group_lookup("protective") in GROUP_SUBGROUPS[gn]

    def test_group_lookup_prefix(self):
        # cf. 1stMud group_lookup str_prefix match
        assert group_lookup("prot") == group_lookup("protective")
        assert group_lookup("bogus") == -1
        assert group_lookup("") == -1

    def test_group_rating_best_across_classes(self):
        gn = group_lookup("protective")
        warrior = {"is_npc": False, "classes": [CLASS_WARRIOR]}
        multi = {"is_npc": False, "classes": [CLASS_WARRIOR, CLASS_CLERIC]}
        thief = {"is_npc": False, "classes": [CLASS_THIEF]}
        assert group_rating(warrior, gn) == 8
        assert group_rating(multi, gn) == 4  # cleric's 4 wins
        assert group_rating(thief, gn) == 7
        # beguiling is mage/thief only -> 0 (unavailable) for warrior
        assert group_rating(warrior, group_lookup("beguiling")) == 0


class TestCreateCharGrants:
    """1stMud nanny default path: base + default groups only, not grant-all."""

    def test_warrior_gets_default_groups_not_spells(self):
        w = create_char(CLASS_WARRIOR)
        assert GSN_BASH in w["learned"]          # warrior default
        assert _sn("second attack") in w["learned"]  # warrior basics
        assert _sn("scrolls") in w["learned"]    # rom basics
        # sanctuary is warrior-learnable (level 30) but NOT in his default
        # groups: it must now cost trains at a gain trainer
        assert GSN_SANCTUARY not in w["learned"]
        assert _sn("dodge") not in w["learned"]  # thief default only
        assert w["learned"][GSN_RECALL] == 50
        # cf. 1stMud nanny.c: the class weapon only reaches 40 once picked at
        # HANDLE_CON_PICK_WEAPON (ported in game_state.py new_game);
        # create_char alone only grants the 1% base-group floor.
        assert w["learned"][WEAPON_GSN_MAP["sword"]] == 1

    def test_mage_gets_spell_groups(self):
        m = create_char(CLASS_MAGE)
        assert GSN_SANCTUARY in m["learned"]     # protective via mage default
        assert _sn("magic missile") in m["learned"]  # combat
        assert GSN_BASH not in m["learned"]

    def test_groups_known_recorded(self):
        w = create_char(CLASS_WARRIOR)
        for name in ("rom basics", "warrior basics", "warrior default",
                     "weaponsmaster"):  # weaponsmaster via warrior default
            assert group_lookup(name) in w["groups"], name
        assert group_lookup("protective") not in w["groups"]

    def test_gn_add_recursive_and_idempotent(self):
        w = create_char(CLASS_WARRIOR)
        gn = group_lookup("mage default")
        gn_add(w, gn)
        assert group_lookup("protective") in w["groups"]
        assert w["learned"][GSN_SANCTUARY] == 1
        w["learned"][GSN_SANCTUARY] = 77
        gn_add(w, gn)  # re-grant must not clobber progress
        assert w["learned"][GSN_SANCTUARY] == 77
        assert w["groups"].count(gn) == 1


class TestDoGain:
    """do_gain (cf. 1stMud do_gain in skills.c)."""

    def _setup(self, monkeypatch):
        import world
        from world import ROOM_DEFS, MOB_DEFS

        room = {"name": "Bar", "desc": "x", "items": [], "mobs": [2],
                "area": "test", "sector": "inside", "flags": {}, "exits": {}}
        ROOM_DEFS._data[3022] = room
        world.rooms._data[3022] = room
        MOB_DEFS._data[9901] = {"short_descr": "the guildmaster", "level": 60,
                                "act_flags": {"gain": True}}
        world.chars[2] = {"is_npc": True, "id": 2, "tpl": 9901, "room": 3022}

        player = create_char(CLASS_WARRIOR)
        player["room"] = 3022
        world.chars[1] = player
        return player

    def _teardown(self):
        import world
        from world import ROOM_DEFS, MOB_DEFS
        ROOM_DEFS._data.pop(3022, None)
        world.rooms._data.pop(3022, None)
        MOB_DEFS._data.pop(9901, None)
        world.chars.pop(1, None)
        world.chars.pop(2, None)

    def test_gain_group_costs_trains(self, monkeypatch):
        import training
        player = self._setup(monkeypatch)
        try:
            player["train"] = 8
            training.do_gain(player, ["protective"])
            assert player["train"] == 0
            assert group_lookup("protective") in player["groups"]
            assert player["learned"][GSN_SANCTUARY] == 1
        finally:
            self._teardown()

    def test_gain_group_refused_without_trains(self, monkeypatch):
        import training
        player = self._setup(monkeypatch)
        try:
            player["train"] = 7  # protective costs warrior 8
            training.do_gain(player, ["protective"])
            assert player["train"] == 7
            assert GSN_SANCTUARY not in player["learned"]
        finally:
            self._teardown()

    def test_gain_spell_individually_refused(self, monkeypatch):
        import training
        player = self._setup(monkeypatch)
        try:
            player["train"] = 50
            training.do_gain(player, ["sanctuary"])
            assert player["train"] == 50
            assert GSN_SANCTUARY not in player["learned"]
        finally:
            self._teardown()

    def test_gain_nonspell_skill(self, monkeypatch):
        import training
        player = self._setup(monkeypatch)
        try:
            hide = _sn("hide")
            assert hide not in player["learned"]
            player["train"] = 6  # hide rating for warrior
            training.do_gain(player, ["hide"])
            assert player["learned"][hide] == 1
            assert player["train"] == 0
        finally:
            self._teardown()

    def test_gain_known_group_refused(self, monkeypatch):
        import training
        player = self._setup(monkeypatch)
        try:
            player["train"] = 50
            training.do_gain(player, ["warrior", "default"])
            assert player["train"] == 50
        finally:
            self._teardown()

    def test_gain_unavailable_group_refused(self, monkeypatch):
        import training
        player = self._setup(monkeypatch)
        try:
            player["train"] = 50
            training.do_gain(player, ["beguiling"])  # mage/thief only
            assert player["train"] == 50
            assert group_lookup("beguiling") not in player["groups"]
        finally:
            self._teardown()

    def test_gain_convert(self, monkeypatch):
        import training
        player = self._setup(monkeypatch)
        try:
            player["practice"] = 23
            player["train"] = 0
            training.do_gain(player, ["convert"])
            assert (player["practice"], player["train"]) == (13, 1)
            training.do_gain(player, ["1", "convert"])  # leading count
            assert (player["practice"], player["train"]) == (3, 2)
            training.do_gain(player, ["convert"])  # < 10 practices: refused
            assert (player["practice"], player["train"]) == (3, 2)
        finally:
            self._teardown()

    def test_gain_needs_gain_trainer(self, monkeypatch):
        import training
        from world import MOB_DEFS
        player = self._setup(monkeypatch)
        try:
            MOB_DEFS._data[9901]["act_flags"] = {"train": True}  # not gain
            player["train"] = 50
            training.do_gain(player, ["protective"])
            assert player["train"] == 50
        finally:
            self._teardown()


class TestDoGrlist:
    """do_grlist (cf. 1stMud do_grlist in skills.c)."""

    def _setup(self):
        player = create_char(CLASS_WARRIOR)
        world.chars[1] = player
        return player

    def _teardown(self):
        world.chars.pop(1, None)

    def _out(self, monkeypatch):
        lines = []
        monkeypatch.setattr(handler, "tprint", lambda s="", end="\n": lines.append(s))
        return lines

    def _paged(self, monkeypatch):
        captured = []
        monkeypatch.setattr(groups_mod, "tpage", lambda lines: captured.extend(lines))
        return captured

    def test_no_arg_lists_known_groups(self, monkeypatch):
        paged = self._paged(monkeypatch)
        player = self._setup()
        try:
            do_grlist(player, [])
            assert any("Groups you currently have:" in l for l in paged)
            # cf. test_groups_known_recorded: warrior default grants this
            assert any("weaponsmaster" in l for l in paged)
            # [PRIMESUD] creation-point economy not ported: no trailing
            # "Creation points: N" line
            assert not any("Creation points" in l for l in paged)
        finally:
            self._teardown()

    def test_no_arg_no_groups_known(self, monkeypatch):
        out = self._out(monkeypatch)
        player = self._setup()
        player["groups"] = []
        try:
            do_grlist(player, [])
            assert any("You know no groups." in l for l in out)
        finally:
            self._teardown()

    def test_all_lists_groups_available_to_class(self, monkeypatch):
        paged = self._paged(monkeypatch)
        player = self._setup()
        try:
            do_grlist(player, ["all"])
            assert any("Groups available to you:" in l for l in paged)
            assert any("weaponsmaster" in l for l in paged)
            # beguiling is mage/thief only -- not available to a warrior
            assert not any("beguiling" in l for l in paged)
        finally:
            self._teardown()

    def test_class_branch_lists_groups_for_named_class(self, monkeypatch):
        paged = self._paged(monkeypatch)
        player = self._setup()
        try:
            do_grlist(player, ["warrior"])
            assert any("Groups available for the {W" "Warrior" in l for l in paged)
            assert any("weaponsmaster" in l for l in paged)
        finally:
            self._teardown()

    def test_group_branch_lists_spells_in_group(self, monkeypatch):
        paged = self._paged(monkeypatch)
        player = self._setup()
        try:
            do_grlist(player, ["weaponsmaster"])
            assert any("Spells available in {W" "weaponsmaster" in l for l in paged)
            assert any("Level" in l and "Spell" in l for l in paged)
            assert any("sword" in l for l in paged)
        finally:
            self._teardown()

    def test_group_branch_unknown_group_no_spells(self, monkeypatch):
        # illusion's members are all immortal-only (skill_level 53) for a
        # warrior -- none pass the MAX_MORTAL_LEVEL cutoff.
        out = self._out(monkeypatch)
        player = self._setup()
        try:
            do_grlist(player, ["illusion"])
            assert any("No spells available in the {W" "illusion" in l for l in out)
        finally:
            self._teardown()

    def test_skill_branch_lists_groups_containing_skill(self, monkeypatch):
        paged = self._paged(monkeypatch)
        player = self._setup()
        try:
            do_grlist(player, ["sword"])
            assert any("is in the following groups:" in l for l in paged)
            assert any("weaponsmaster" in l for l in paged)
        finally:
            self._teardown()

    def test_skill_branch_skill_not_in_any_group_member_list(self, monkeypatch):
        # "kick" is a real skill (skills_table.py) but is not listed as a
        # direct member of any GROUP_TABLE entry.
        out = self._out(monkeypatch)
        player = self._setup()
        try:
            do_grlist(player, ["kick"])
            assert any("{c can't be found in any groups." in l for l in out)
        finally:
            self._teardown()

    def test_unrecognized_argument_prints_syntax(self, monkeypatch):
        out = self._out(monkeypatch)
        player = self._setup()
        try:
            do_grlist(player, ["zzzznotarealthing"])
            assert any("Syntax: grlist" in l for l in out)
            assert any("list your current groups" in l for l in out)
            assert any("list all available groups" in l for l in out)
        finally:
            self._teardown()
