"""Darkness / visibility predicate + gating tests (darkness Phases A+B).

Phase A: room_is_dark truth table, the can_see dark/infrared gate,
can_see_obj, and check_blind.
Phase B (below TestCheckBlind): do_look pitch-black gating + red eyes, exits
"Too dark to tell", and aggro shielding.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import world
from world import ROOM_DEFS, MOB_DEFS, ITEM_DEFS
from game_time import time_info, SUN_DARK, SUN_LIGHT, SUN_RISE, SUN_SET
from handler import _char_base


def _room(vnum, sector="field", flags=None):
    ROOM_DEFS._data[vnum] = {"name": "R", "desc": "A dim place.", "exits": {},
                             "sector": sector, "flags": flags or {}}
    world.rooms._data[vnum] = {"mobs": [], "items": []}


def _char(room, **aff):
    c = _char_base()
    c.update({"room": room, "equip": {"light": None}, "affected_by": dict(aff)})
    return c


# ---------------------------------------------------------------------------
# Phase A -- room_is_dark truth table (each sunlight state / sector / flag)
# ---------------------------------------------------------------------------

class TestRoomIsDark:
    def test_sunlight_states_outdoors(self, fresh_world):
        from handler import room_is_dark
        _room(1, sector="field")
        old = time_info["sunlight"]
        try:
            for sun, expected in ((SUN_LIGHT, False), (SUN_RISE, False),
                                  (SUN_SET, True), (SUN_DARK, True)):
                time_info["sunlight"] = sun
                assert room_is_dark(1) is expected, sun
        finally:
            time_info["sunlight"] = old

    def test_inside_and_city_never_dark_at_night(self, fresh_world):
        from handler import room_is_dark
        _room(2, sector="inside")
        _room(3, sector="city")
        old = time_info["sunlight"]
        try:
            time_info["sunlight"] = SUN_DARK
            assert room_is_dark(2) is False
            assert room_is_dark(3) is False
        finally:
            time_info["sunlight"] = old

    def test_dark_flag_beats_sector(self, fresh_world):
        from handler import room_is_dark
        _room(4, sector="city", flags={"dark": True})
        assert room_is_dark(4) is True

    def test_lit_char_overrides_dark_flag(self, fresh_world):
        from handler import room_is_dark
        ITEM_DEFS._data[500] = {"type": "light", "light_hours": -1,
                                "keywords": "torch", "short_descr": "a torch"}
        _room(5, sector="field", flags={"dark": True})
        c1 = _char_base()
        c1.update({"room": 5, "equip": {"light": {"vnum": 500}}})
        world.chars[1] = c1
        try:
            assert room_is_dark(5) is False
        finally:
            del world.chars[1]

    def test_lit_floor_light_overrides_dark_flag(self, fresh_world):
        # [PRIMESUD] a lit light lying on the floor lights the room, unlike
        # stock ROM/1stMud which count only worn lights
        from handler import room_is_dark
        ITEM_DEFS._data[501] = {"type": "light", "light_hours": -1,
                                "keywords": "torch", "short_descr": "a torch"}
        _room(6, sector="field", flags={"dark": True})
        world.rooms._data[6]["items"].append({"vnum": 501})
        assert room_is_dark(6) is False

    def test_dead_floor_light_stays_dark(self, fresh_world):
        # a burnt-out (0 fuel) floor light does not illuminate
        from handler import room_is_dark
        ITEM_DEFS._data[502] = {"type": "light", "light_hours": 0,
                                "keywords": "torch", "short_descr": "a torch"}
        _room(7, sector="field", flags={"dark": True})
        world.rooms._data[7]["items"].append({"vnum": 502})
        assert room_is_dark(7) is True


# ---------------------------------------------------------------------------
# Phase A -- can_see dark / infrared gate
# ---------------------------------------------------------------------------

class TestCanSeeDark:
    def test_dark_room_hides_victim(self, fresh_world):
        from handler import can_see
        _room(1, flags={"dark": True})
        ch = _char(1)
        victim = _char(1)
        assert can_see(ch, victim) is False

    def test_infrared_pierces_dark(self, fresh_world):
        from handler import can_see
        _room(1, flags={"dark": True})
        ch = _char(1, infrared=True)
        victim = _char(1)
        assert can_see(ch, victim) is True

    def test_lit_room_visible(self, fresh_world):
        from handler import can_see
        _room(1, sector="inside")
        assert can_see(_char(1), _char(1)) is True

    def test_blind_beats_everything(self, fresh_world):
        from handler import can_see
        _room(1, sector="inside")
        assert can_see(_char(1, blind=True), _char(1)) is False


# ---------------------------------------------------------------------------
# Quest / gquest target sight overrides (handler.c:2421-2426, 2461)
# ---------------------------------------------------------------------------

class TestQuestSight:
    def test_quester_sees_target_mob_in_dark(self, fresh_world):
        from handler import can_see
        _room(1, flags={"dark": True})
        ch = _char(1)
        ch.update(quest_status=1, quest_mob=9405)
        victim = _char(1)
        victim.update(is_npc=True, tpl=9405)
        assert can_see(ch, victim) is True

    def test_quester_other_mob_still_hidden(self, fresh_world):
        from handler import can_see
        _room(1, flags={"dark": True})
        ch = _char(1)
        ch.update(quest_status=1, quest_mob=9405)
        victim = _char(1)
        victim.update(is_npc=True, tpl=9999)
        assert can_see(ch, victim) is False

    def test_gquester_sees_remaining_target_in_dark(self, fresh_world):
        from handler import can_see
        from gquest import gquest_info, GQUEST_RUNNING, GQUEST_OFF
        _room(1, flags={"dark": True})
        ch = _char(1)
        victim = _char(1)
        victim.update(is_npc=True, tpl=9405)
        old = (gquest_info["running"], gquest_info["joined"],
               list(gquest_info["pmobs"]))
        try:
            gquest_info["running"] = GQUEST_RUNNING
            gquest_info["joined"] = True
            gquest_info["pmobs"] = [9405]
            assert can_see(ch, victim) is True
            gquest_info["pmobs"] = [-1]          # already killed -> no override
            assert can_see(ch, victim) is False
        finally:
            (gquest_info["running"], gquest_info["joined"],
             gquest_info["pmobs"]) = old

    def test_quester_sees_quest_obj_in_dark(self, fresh_world):
        from handler import can_see_obj
        _room(1, flags={"dark": True})
        ITEM_DEFS._data[214] = {"type": "gem", "keywords": "token",
                                "short_descr": "a quest token",
                                "extra_flags": {}}
        ch = _char(1)
        ch.update(quest_status=2, quest_obj=214)
        assert can_see_obj(ch, {"vnum": 214}) is True
        ch["quest_obj"] = 215
        assert can_see_obj(ch, {"vnum": 214}) is False


# ---------------------------------------------------------------------------
# Phase A -- can_see_obj full port
# ---------------------------------------------------------------------------

class TestCanSeeObj:
    def _item(self, vnum, otype="trash", flags=None, **extra):
        ITEM_DEFS._data[vnum] = dict({"type": otype, "keywords": "thing",
                                      "short_descr": "a thing",
                                      "extra_flags": flags or {}}, **extra)
        return vnum

    def test_vis_death_hidden(self, fresh_world):
        from handler import can_see_obj
        _room(1, sector="inside")
        v = self._item(600, flags={"vis_death": True})
        assert can_see_obj(_char(1), v) is False

    def test_blind_hides_non_potion(self, fresh_world):
        from handler import can_see_obj
        _room(1, sector="inside")
        v = self._item(601)
        assert can_see_obj(_char(1, blind=True), v) is False

    def test_blind_still_sees_potion(self, fresh_world):
        from handler import can_see_obj
        _room(1, sector="inside")
        v = self._item(602, otype="potion")
        assert can_see_obj(_char(1, blind=True), v) is True

    def test_lit_light_visible_in_dark(self, fresh_world):
        from handler import can_see_obj
        _room(1, flags={"dark": True})
        v = self._item(603, otype="light", light_hours=-1)
        assert can_see_obj(_char(1), v) is True

    def test_dead_light_hidden_in_dark(self, fresh_world):
        from handler import can_see_obj
        _room(1, flags={"dark": True})
        v = self._item(604, otype="light", light_hours=0)
        assert can_see_obj(_char(1), v) is False

    def test_invis_needs_detect(self, fresh_world):
        from handler import can_see_obj
        _room(1, sector="inside")
        v = self._item(605, flags={"invis": True})
        assert can_see_obj(_char(1), v) is False
        assert can_see_obj(_char(1, detect_invis=True), v) is True

    def test_glow_visible_in_dark(self, fresh_world):
        from handler import can_see_obj
        _room(1, flags={"dark": True})
        v = self._item(606, flags={"glow": True})
        assert can_see_obj(_char(1), v) is True

    def test_dark_room_hides_plain_item(self, fresh_world):
        from handler import can_see_obj
        _room(1, flags={"dark": True})
        v = self._item(607)
        assert can_see_obj(_char(1), v) is False
        assert can_see_obj(_char(1, dark_vision=True), v) is True

    def test_lit_room_shows_plain_item(self, fresh_world):
        from handler import can_see_obj
        _room(1, sector="inside")
        v = self._item(608)
        assert can_see_obj(_char(1), v) is True


# ---------------------------------------------------------------------------
# Phase A -- check_blind
# ---------------------------------------------------------------------------

class TestCheckBlind:
    def test_blind_prints_and_fails(self, fresh_world, monkeypatch):
        import handler
        lines = []
        monkeypatch.setattr(handler, "chprintln",
                            lambda ch, s="": lines.append(s))
        assert handler.check_blind(_char(1, blind=True)) is False
        assert lines == ["You can't see a thing!"]

    def test_sighted_passes_silently(self, fresh_world, monkeypatch):
        import handler
        lines = []
        monkeypatch.setattr(handler, "chprintln",
                            lambda ch, s="": lines.append(s))
        assert handler.check_blind(_char(1)) is True
        assert lines == []


# ---------------------------------------------------------------------------
# Phase B -- do_look / do_exits gating and aggro shielding
# ---------------------------------------------------------------------------

def _look_player(room):
    from handler import PLR_DEFAULTS
    c = _char_base()
    c.update({"id": 1, "name": "Tester", "room": room, "level": 10,
              "flags": PLR_DEFAULTS & ~(PLR_DEFAULTS),  # 0: no automap/autoexit
              "inv": [], "equip": {}, "affected_by": {}})
    return c


@pytest.fixture
def look_out(monkeypatch):
    import info
    import handler
    lines = []
    # do_look sends a pre-split list batch; flatten so assertions see lines
    cap = lambda ch, s="": (
        lines.extend(s) if type(s) is list else lines.append(s))
    # do_look/do_exits print via info.chprintln; check_blind via handler's own
    monkeypatch.setattr(info, "chprintln", cap)
    monkeypatch.setattr(handler, "chprintln", cap)
    return lines


class TestLookDark:
    def test_pitch_black_blocks_room(self, fresh_world, look_out):
        import info
        _room(1, flags={"dark": True})
        ROOM_DEFS._data[1]["name"] = "Secret Vault"
        info.do_look(_look_player(1), [])
        assert look_out == ["It is pitch black ... "]

    def test_infrared_shows_chars_not_room(self, fresh_world, look_out):
        # cf. 1stMud act_info.c:1114 -- infrared does NOT lift the pitch-black
        # gate: room name/desc stay hidden, but living things (heat) show.
        import info
        _room(1, flags={"dark": True})
        ROOM_DEFS._data[1]["name"] = "Secret Vault"
        MOB_DEFS._data[900] = {"short_descr": "a cave bat",
                               "long_descr": "A cave bat flaps here.",
                               "start_pos": "stand"}
        c2 = _char_base()
        c2.update({"id": 2, "is_npc": True, "tpl": 900, "room": 1,
                   "pos": "standing", "fighting": None,
                   "affected_by": {}})
        world.chars[2] = c2
        world.rooms._data[1]["mobs"].append(2)
        p = _look_player(1)
        p["affected_by"] = {"infrared": True}
        info.do_look(p, [])
        joined = " ".join(look_out)
        assert "It is pitch black ... " in joined  # room desc still gated
        assert "Secret Vault" not in joined         # room name never revealed
        assert "cave bat" in joined                 # infrared reveals the mob

    def test_targeted_look_also_pitch_black(self, fresh_world, look_out):
        import info
        _room(1, flags={"dark": True})
        info.do_look(_look_player(1), ["sword"])
        assert look_out == ["It is pitch black ... "]

    def test_red_eyes_for_infrared_mob(self, fresh_world, look_out):
        import info
        _room(1, flags={"dark": True})
        c2 = _char_base()
        c2.update({"id": 2, "is_npc": True, "room": 1,
                   "affected_by": {"infrared": True}})
        world.chars[2] = c2
        world.rooms._data[1]["mobs"].append(2)
        info.do_look(_look_player(1), [])
        assert look_out == ["It is pitch black ... ",
                            "You see glowing red eyes watching YOU!"]

    def test_no_red_eyes_for_plain_mob(self, fresh_world, look_out):
        import info
        _room(1, flags={"dark": True})
        c2 = _char_base()
        c2.update({"id": 2, "is_npc": True, "room": 1,
                   "affected_by": {}})
        world.chars[2] = c2
        world.rooms._data[1]["mobs"].append(2)
        info.do_look(_look_player(1), [])
        assert look_out == ["It is pitch black ... "]

    def test_blind_blocks_look(self, fresh_world, look_out):
        import info
        _room(1, sector="inside")
        ROOM_DEFS._data[1]["name"] = "Bright Hall"
        p = _look_player(1)
        p["affected_by"] = {"blind": True}
        info.do_look(p, [])
        assert look_out == ["You can't see a thing!"]


class TestExitsDark:
    def test_dark_destination_hidden(self, fresh_world, look_out):
        import info
        _room(1, sector="city")
        _room(2, flags={"dark": True})
        ROOM_DEFS._data[2]["name"] = "Black Pit"
        ROOM_DEFS._data[1]["exits"] = {"n": 2}
        c = _char_base()
        c.update({"room": 1, "affected_by": {}})
        info.do_exits(c, [])
        joined = " ".join(look_out)
        assert "Too dark to tell" in joined
        assert "Black Pit" not in joined

    def test_lit_destination_named(self, fresh_world, look_out):
        import info
        _room(1, sector="city")
        _room(2, sector="inside")
        ROOM_DEFS._data[2]["name"] = "Marble Foyer"
        ROOM_DEFS._data[1]["exits"] = {"n": 2}
        c = _char_base()
        c.update({"room": 1, "affected_by": {}})
        info.do_exits(c, [])
        joined = " ".join(look_out)
        assert "Marble Foyer" in joined
        assert "Too dark to tell" not in joined


class TestAggroShield:
    """A dark room shields an unlit player from a non-infrared aggressor;
    an infrared mob still sees through it (mob aggro routes through can_see)."""

    def test_non_infrared_mob_blinded_in_dark(self, fresh_world):
        from handler import can_see
        _room(1, flags={"dark": True})
        mob = _char_base()
        mob.update({"id": 2, "is_npc": True, "room": 1, "affected_by": {}})
        player = _char_base()
        player.update({"id": 1, "room": 1, "affected_by": {}})
        assert can_see(mob, player) is False

    def test_infrared_mob_sees_in_dark(self, fresh_world):
        from handler import can_see
        _room(1, flags={"dark": True})
        mob = _char_base()
        mob.update({"id": 2, "is_npc": True, "room": 1,
                    "affected_by": {"infrared": True}})
        player = _char_base()
        player.update({"id": 1, "room": 1, "affected_by": {}})
        assert can_see(mob, player) is True


# ---------------------------------------------------------------------------
# [PRIMESUD] "holylight" debug channel = 1stMud PLR_HOLYLIGHT imm sight
# ---------------------------------------------------------------------------

@pytest.fixture
def holylight():
    from debug import DBG
    DBG.add("holylight")
    yield
    DBG.discard("holylight")


class TestHolylight:
    def test_can_see_ignores_dark(self, fresh_world, holylight):
        from handler import can_see
        _room(1, flags={"dark": True})
        assert can_see(_char(1), _char(1)) is True

    def test_can_see_obj_ignores_dark_and_blind(self, fresh_world, holylight):
        from handler import can_see_obj
        _room(1, flags={"dark": True})
        ITEM_DEFS._data[610] = {"type": "trash", "keywords": "thing",
                                "short_descr": "a thing", "extra_flags": {}}
        assert can_see_obj(_char(1), 610) is True
        assert can_see_obj(_char(1, blind=True), 610) is True

    def test_npc_observer_not_holylit(self, fresh_world, holylight):
        # cf. handler.c:2403/2458 -- the PLR_HOLYLIGHT leg is !IsNPC only
        from handler import can_see
        _room(1, flags={"dark": True})
        mob = _char_base()
        mob.update({"id": 2, "is_npc": True, "room": 1, "affected_by": {}})
        player = _char_base()
        player.update({"id": 1, "room": 1, "affected_by": {}})
        assert can_see(mob, player) is False

    def test_check_blind_passes(self, fresh_world, holylight, monkeypatch):
        import handler
        lines = []
        monkeypatch.setattr(handler, "chprintln",
                            lambda ch, s="": lines.append(s))
        assert handler.check_blind(_char(1, blind=True)) is True
        assert lines == []

    def test_look_shows_dark_room(self, fresh_world, holylight, look_out):
        import info
        _room(1, flags={"dark": True})
        ROOM_DEFS._data[1]["name"] = "Secret Vault"
        info.do_look(_look_player(1), [])
        joined = " ".join(look_out)
        assert "Secret Vault" in joined
        assert "pitch black" not in joined

    def test_toggle_messages(self, fresh_world, monkeypatch):
        # cf. 1stMud do_holylight set_on_off messages (act_wiz.c:2946)
        import debug
        lines = []

        class _TR:
            print = staticmethod(lambda s: lines.append(s))
        monkeypatch.setattr(debug.terminal, "tr", _TR)
        debug.DBG.discard("holylight")
        try:
            debug._debug_holylight(None, [])
            assert "holylight" in debug.DBG
            debug._debug_holylight(None, [])
            assert "holylight" not in debug.DBG
            assert lines == ["Holy light mode on.", "Holy light mode off."]
        finally:
            debug.DBG.discard("holylight")

    def test_debug_all_leaves_holylight_alone(self, fresh_world, monkeypatch):
        import debug
        lines = []

        class _TR:
            print = staticmethod(lambda s: lines.append(s))
        monkeypatch.setattr(debug.terminal, "tr", _TR)
        debug.DBG.add("holylight")
        try:
            debug.do_debug(None, ["all"])   # all channels on
            assert "holylight" in debug.DBG
            debug.do_debug(None, ["all"])   # all channels off
            assert "holylight" in debug.DBG
            assert not debug.DBG.intersection(debug._CHANNELS)
        finally:
            debug.DBG.discard("holylight")
            debug.DBG.difference_update(debug._CHANNELS)


class TestObjectVisibilityGates:
    """can_see_obj baked into get_obj_here / look-item scan / container list
    (cf. handler.c:2063, act_info.c:1234-1300, show_list_to_char)."""

    def _invis_item(self, vnum):
        ITEM_DEFS._data[vnum] = {"type": "trash", "keywords": "bauble",
                                 "short_descr": "a shimmering bauble",
                                 "extra_flags": {"invis": True}}
        return vnum

    def _actor(self, room, **aff):
        p = _char(room, **aff)
        p.update(inv=[], equip={})
        return p

    def test_get_obj_here_skips_invisible(self, fresh_world):
        from item import get_obj_here
        _room(1, sector="inside")
        v = self._invis_item(620)
        world.rooms._data[1]["items"].append(v)
        assert get_obj_here(self._actor(1), "bauble") is None
        assert get_obj_here(self._actor(1, detect_invis=True), "bauble") == v

    def test_look_scan_skips_invisible(self, fresh_world):
        import info
        v = self._invis_item(621)
        _room(1, sector="inside")
        found, count = info._look_scan_items(self._actor(1), "bauble", 1, 0, [v])
        assert found is False
        found, count = info._look_scan_items(
            self._actor(1, detect_invis=True), "bauble", 1, 0, [v])
        assert found is True

    def test_container_hides_invisible_contents(self, fresh_world, look_out):
        import info
        _room(1, sector="inside")
        self._invis_item(622)
        ITEM_DEFS._data[623] = {"type": "container", "keywords": "chest",
                                "short_descr": "a chest", "extra_flags": {}}
        chest = {"vnum": 623, "contents": [622]}
        info._show_container(self._actor(1), chest, ITEM_DEFS._data[623])
        assert look_out == ["a chest holds:", "  Nothing."]


class TestConsiderPicker:
    """The no-arg consider picker offers only mobs the player can see, so an
    undetected invis mob is not betrayed by the menu (combat.do_consider)."""

    def _scene(self, monkeypatch, **aff):
        import combat
        _room(1, sector="inside")
        MOB_DEFS._data[700] = {"short_descr": "a plain rat", "keywords": "rat",
                               "level": 1, "affected_by": {}}
        MOB_DEFS._data[701] = {"short_descr": "a ghostly wraith",
                               "keywords": "wraith", "level": 1,
                               "affected_by": {"invisible": True}}
        c2 = _char_base()
        c2.update({"id": 2, "is_npc": True, "tpl": 700, "room": 1,
                   "level": 1, "affected_by": {}})
        world.chars[2] = c2
        c3 = _char_base()
        c3.update({"id": 3, "is_npc": True, "tpl": 701, "room": 1,
                   "level": 1, "affected_by": {"invisible": True}})
        world.chars[3] = c3
        world.rooms._data[1]["mobs"] = [2, 3]
        offered = []
        monkeypatch.setattr(combat, "pick_from",
                            lambda title, opts: offered.append(opts) or -1)
        p = _look_player(1)
        p["affected_by"] = dict(aff)
        combat.do_consider(p, [])
        return offered

    def test_invis_mob_absent_without_detect(self, fresh_world, monkeypatch):
        assert self._scene(monkeypatch) == [["a plain rat"]]

    def test_invis_mob_offered_with_detect(self, fresh_world, monkeypatch):
        assert self._scene(monkeypatch, detect_invis=True) == [
            ["a plain rat", "a ghostly wraith"]]

    def test_no_visible_mobs_prints_prompt(self, fresh_world, monkeypatch):
        import combat
        out = []
        monkeypatch.setattr(combat, "chprintln", lambda ch, msg: out.append(msg))
        monkeypatch.setattr(combat, "pick_from",
                            lambda title, opts: pytest.fail("picker shown"))
        _room(1, sector="inside")
        MOB_DEFS._data[702] = {"short_descr": "a ghostly wraith",
                               "keywords": "wraith", "level": 1,
                               "affected_by": {"invisible": True}}
        c4 = _char_base()
        c4.update({"id": 4, "is_npc": True, "tpl": 702, "room": 1,
                   "level": 1, "affected_by": {"invisible": True}})
        world.chars[4] = c4
        world.rooms._data[1]["mobs"] = [4]
        combat.do_consider(_look_player(1), [])
        assert out == ["You don't see anyone here."]


class TestKillPicker:
    """The no-arg kill picker shares do_consider's visibility filter, so an
    undetected invis mob is not betrayed by the menu either (combat.do_kill)."""

    def _scene(self, monkeypatch, **aff):
        import combat
        _room(1, sector="inside")
        MOB_DEFS._data[710] = {"short_descr": "a plain rat", "keywords": "rat",
                               "level": 1, "affected_by": {}}
        MOB_DEFS._data[711] = {"short_descr": "a ghostly wraith",
                               "keywords": "wraith", "level": 1,
                               "affected_by": {"invisible": True}}
        c2 = _char_base()
        c2.update({"id": 2, "is_npc": True, "tpl": 710, "room": 1,
                   "level": 1, "affected_by": {}})
        world.chars[2] = c2
        c3 = _char_base()
        c3.update({"id": 3, "is_npc": True, "tpl": 711, "room": 1,
                   "level": 1, "affected_by": {"invisible": True}})
        world.chars[3] = c3
        world.rooms._data[1]["mobs"] = [2, 3]
        offered = []
        monkeypatch.setattr(combat, "pick_from",
                            lambda title, opts: offered.append(opts) or -1)
        p = _look_player(1)
        p["affected_by"] = dict(aff)
        combat.do_kill(p, [])
        return offered

    def test_invis_mob_absent_without_detect(self, fresh_world, monkeypatch):
        assert self._scene(monkeypatch) == [["a plain rat"]]

    def test_invis_mob_offered_with_detect(self, fresh_world, monkeypatch):
        assert self._scene(monkeypatch, detect_invis=True) == [
            ["a plain rat", "a ghostly wraith"]]

    def test_no_visible_mobs_prints_prompt(self, fresh_world, monkeypatch):
        import combat
        out = []
        monkeypatch.setattr(combat, "chprintln", lambda ch, msg: out.append(msg))
        monkeypatch.setattr(combat, "pick_from",
                            lambda title, opts: pytest.fail("picker shown"))
        _room(1, sector="inside")
        MOB_DEFS._data[712] = {"short_descr": "a ghostly wraith",
                               "keywords": "wraith", "level": 1,
                               "affected_by": {"invisible": True}}
        c4 = _char_base()
        c4.update({"id": 4, "is_npc": True, "tpl": 712, "room": 1,
                   "level": 1, "affected_by": {"invisible": True}})
        world.chars[4] = c4
        world.rooms._data[1]["mobs"] = [4]
        combat.do_kill(_look_player(1), [])
        assert out == ["You don't see anyone here."]

    def test_empty_room_prints_prompt(self, fresh_world, monkeypatch):
        import combat
        out = []
        monkeypatch.setattr(combat, "chprintln", lambda ch, msg: out.append(msg))
        monkeypatch.setattr(combat, "pick_from",
                            lambda title, opts: pytest.fail("picker shown"))
        _room(1, sector="inside")
        combat.do_kill(_look_player(1), [])
        assert out == ["You don't see anyone here."]


class TestGivePicker:
    """The no-arg give picker only lists mobs the player can see, so a room
    holding nothing visible says so instead of prompting (inventory.do_give)."""

    def test_no_visible_mobs_prints_prompt(self, fresh_world, monkeypatch):
        import inventory
        out = []
        monkeypatch.setattr(inventory, "chprintln", lambda ch, msg: out.append(msg))
        monkeypatch.setattr(inventory, "pick_from",
                            lambda title, opts: pytest.fail("picker shown"))
        _room(1, sector="inside")
        MOB_DEFS._data[720] = {"short_descr": "a ghostly wraith",
                               "keywords": "wraith", "level": 1,
                               "affected_by": {"invisible": True}}
        c2 = _char_base()
        c2.update({"id": 2, "is_npc": True, "tpl": 720, "room": 1,
                   "level": 1, "affected_by": {"invisible": True}})
        world.chars[2] = c2
        world.rooms._data[1]["mobs"] = [2]
        inventory.do_give(_look_player(1), [])
        assert out == ["You don't see anyone here."]

    def test_empty_room_prints_prompt(self, fresh_world, monkeypatch):
        import inventory
        out = []
        monkeypatch.setattr(inventory, "chprintln", lambda ch, msg: out.append(msg))
        monkeypatch.setattr(inventory, "pick_from",
                            lambda title, opts: pytest.fail("picker shown"))
        _room(1, sector="inside")
        inventory.do_give(_look_player(1), [])
        assert out == ["You don't see anyone here."]


class TestCastPicker:
    """[PRIMESUD] cast target pickers share the other menus' sight filters, so
    an undetected invis mob/item is not betrayed (magic._pick_cast_target_name)."""

    def _sn(self, name):
        from skills_table import SKILL_TABLE
        for sn, sk in SKILL_TABLE:
            if sk["name"] == name:
                return sn
        pytest.fail("no such spell: " + name)

    def _mobs(self, monkeypatch, **aff):
        import magic
        _room(1, sector="inside")
        MOB_DEFS._data[730] = {"short_descr": "a plain rat", "keywords": "rat",
                               "level": 1, "affected_by": {}}
        MOB_DEFS._data[731] = {"short_descr": "a ghostly wraith",
                               "keywords": "wraith", "level": 1,
                               "affected_by": {"invisible": True}}
        c2 = _char_base()
        c2.update({"id": 2, "is_npc": True, "tpl": 730, "room": 1,
                   "level": 1, "affected_by": {}})
        world.chars[2] = c2
        c3 = _char_base()
        c3.update({"id": 3, "is_npc": True, "tpl": 731, "room": 1,
                   "level": 1, "affected_by": {"invisible": True}})
        world.chars[3] = c3
        world.rooms._data[1]["mobs"] = [2, 3]
        offered = []
        monkeypatch.setattr(magic, "pick_from",
                            lambda title, opts: offered.append(opts) or -1)
        p = _look_player(1)
        p["affected_by"] = dict(aff)
        magic._pick_cast_target_name(p, self._sn("acid blast"))
        return offered

    def test_invis_mob_absent_without_detect(self, fresh_world, monkeypatch):
        assert self._mobs(monkeypatch) == [["a plain rat"]]

    def test_invis_mob_offered_with_detect(self, fresh_world, monkeypatch):
        assert self._mobs(monkeypatch, detect_invis=True) == [
            ["a plain rat", "a ghostly wraith"]]

    def test_no_visible_mobs_skips_picker(self, fresh_world, monkeypatch):
        import magic
        _room(1, sector="inside")
        MOB_DEFS._data[732] = {"short_descr": "a ghostly wraith",
                               "keywords": "wraith", "level": 1,
                               "affected_by": {"invisible": True}}
        c2 = _char_base()
        c2.update({"id": 2, "is_npc": True, "tpl": 732, "room": 1,
                   "level": 1, "affected_by": {"invisible": True}})
        world.chars[2] = c2
        world.rooms._data[1]["mobs"] = [2]
        monkeypatch.setattr(magic, "pick_from",
                            lambda title, opts: pytest.fail("picker shown"))
        # empty menu falls through to the typed path's parity messages
        assert magic._pick_cast_target_name(
            _look_player(1), self._sn("acid blast")) == ""

    def _items(self, monkeypatch, **aff):
        """obj_inventory picker over one plain and one invis carried item."""
        import magic
        _room(1, sector="inside")
        ITEM_DEFS._data[733] = {"type": "trash", "keywords": "stick",
                                "short_descr": "a plain stick",
                                "extra_flags": {}}
        ITEM_DEFS._data[734] = {"type": "trash", "keywords": "bauble",
                                "short_descr": "a shimmering bauble",
                                "extra_flags": {"invis": True}}
        offered = []
        monkeypatch.setattr(magic, "pick_from",
                            lambda title, opts: offered.append(opts) or -1)
        p = _look_player(1)
        p["affected_by"] = dict(aff)
        p["inv"] = [{"vnum": 733}, {"vnum": 734}]
        magic._pick_cast_target_name(p, self._sn("create water"))
        return offered

    def test_invis_item_absent_without_detect(self, fresh_world, monkeypatch):
        assert self._items(monkeypatch) == [["a plain stick"]]

    def test_invis_item_offered_with_detect(self, fresh_world, monkeypatch):
        assert self._items(monkeypatch, detect_invis=True) == [
            ["a plain stick", "a shimmering bauble"]]

    def _whom_or_what(self, monkeypatch, **aff):
        """obj_char_offensive picker: room mobs then room items."""
        import magic
        _room(1, sector="inside")
        MOB_DEFS._data[735] = {"short_descr": "a plain rat", "keywords": "rat",
                               "level": 1, "affected_by": {}}
        MOB_DEFS._data[736] = {"short_descr": "a ghostly wraith",
                               "keywords": "wraith", "level": 1,
                               "affected_by": {"invisible": True}}
        c2 = _char_base()
        c2.update({"id": 2, "is_npc": True, "tpl": 735, "room": 1,
                   "level": 1, "affected_by": {}})
        world.chars[2] = c2
        c3 = _char_base()
        c3.update({"id": 3, "is_npc": True, "tpl": 736, "room": 1,
                   "level": 1, "affected_by": {"invisible": True}})
        world.chars[3] = c3
        world.rooms._data[1]["mobs"] = [2, 3]
        ITEM_DEFS._data[737] = {"type": "trash", "keywords": "stick",
                                "short_descr": "a plain stick",
                                "extra_flags": {}}
        ITEM_DEFS._data[738] = {"type": "trash", "keywords": "bauble",
                                "short_descr": "a shimmering bauble",
                                "extra_flags": {"invis": True}}
        world.rooms._data[1]["items"] = [737, 738]
        offered = []
        monkeypatch.setattr(magic, "pick_from",
                            lambda title, opts: offered.append(opts) or -1)
        p = _look_player(1)
        p["affected_by"] = dict(aff)
        magic._pick_cast_target_name(p, self._sn("curse"))
        return offered

    def test_invis_mob_and_item_absent_without_detect(self, fresh_world,
                                                     monkeypatch):
        assert self._whom_or_what(monkeypatch) == [
            ["a plain rat", "a plain stick"]]

    def test_invis_mob_and_item_offered_with_detect(self, fresh_world,
                                                    monkeypatch):
        assert self._whom_or_what(monkeypatch, detect_invis=True) == [
            ["a plain rat", "a ghostly wraith",
             "a plain stick", "a shimmering bauble"]]


class TestDoMapBlind:
    def test_blind_refuses_map(self, fresh_world, look_out):
        import info
        _room(1, sector="inside")
        p = _look_player(1)
        p["affected_by"] = {"blind": True}
        info.do_map(p, [])
        assert look_out == ["You can't see a thing!"]
