"""Tests for converter "flag_affects" expansion and application (cf. 1stMud
db2.c load_objects 'F' case, handler.c equip_char/unequip_char/affect_check).

flag_affects tuples come from the area converter (see src/area_shire.txt
line ~1373, src/area_quest.txt lines ~180-325): (where, loc_name, mod, bits)
where bits is a dict of flag names (possibly with a "_unknown_bits" list of
undefined bit ints, which must never reach a runtime flag dict).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import info
from handler import (_char_base, affect_modify, affect_remove,
                     affect_to_char, equip_char, unequip_char, tpl_flag_affects)
import world
from world import ITEM_DEFS

ROOM_VNUM = 9701
RING_VNUM = 9720
SHIELD_VNUM = 9721
UNKNOWN_VNUM = 9722
HASTE_VNUM = 9723
MULTI_VNUM = 9724


def _stub_room():
    room = {"name": "Test Room", "desc": "A test room.", "exits": {},
            "items": [], "mobs": [], "area": "test", "flags": {},
            "sector": "inside"}
    world.rooms._data[ROOM_VNUM] = room
    return room


def _player():
    ch = _char_base()
    ch["id"] = 1
    ch["name"] = "Tester"
    ch["room"] = ROOM_VNUM
    world.chars[1] = ch
    return ch


def _item(vnum, tpl):
    ITEM_DEFS._data[vnum] = tpl
    return {"vnum": vnum}


def test_affects_entry_sets_and_clears_affected_by():
    """Equipping an invisibility-granting item sets affected_by; unequip clears it."""
    _stub_room()
    ch = _player()
    tpl = {"short_descr": "a plain ring", "wear_flags": {"finger": True},
           "flag_affects": (('affects', '0', 0, {"invisible": True}),)}
    obj = _item(RING_VNUM, tpl)
    ch["inv"].append(obj)

    equip_char(ch, obj, "finger_l")
    assert ch["affected_by"].get("invisible") is True

    unequip_char(ch, "finger_l")
    assert not ch["affected_by"].get("invisible")


def test_resist_entry_sets_and_clears_res_flags():
    """A resist-where entry sets/clears res_flags, not affected_by."""
    _stub_room()
    ch = _player()
    tpl = {"short_descr": "a battered shield", "wear_flags": {"shield": True},
           "flag_affects": (('resist', '0', -1, {"weapon": True}),)}
    obj = _item(SHIELD_VNUM, tpl)
    ch["inv"].append(obj)

    equip_char(ch, obj, "shield")
    assert ch["res_flags"].get("weapon") is True
    assert not ch.get("affected_by", {}).get("weapon")

    unequip_char(ch, "shield")
    assert not ch["res_flags"].get("weapon")


def test_unknown_bits_are_skipped_entirely():
    """_unknown_bits entries never land in any char flag dict."""
    _stub_room()
    ch = _player()
    tpl = {"short_descr": "a mysterious trinket", "wear_flags": {"finger": True},
           "flag_affects": (('affects', '0', 0, {"_unknown_bits": [36]}),)}
    obj = _item(UNKNOWN_VNUM, tpl)
    ch["inv"].append(obj)

    equip_char(ch, obj, "finger_l")

    assert "_unknown_bits" not in ch.get("affected_by", {})
    for key in ("affected_by", "imm_flags", "res_flags", "vuln_flags"):
        assert not ch.get(key)


def test_affect_check_retains_flag_from_equipped_template():
    """Removing a spell affect leaves the bit set if a worn non-enchanted
    item's template still grants it (cf. 1stMud handler.c:1121-1146)."""
    _stub_room()
    ch = _player()
    tpl = {"short_descr": "a pair of hasty boots", "wear_flags": {"feet": True},
           "flag_affects": (('affects', '0', 0, {"haste": True}),)}
    obj = _item(HASTE_VNUM, tpl)
    ch["inv"].append(obj)
    equip_char(ch, obj, "feet")
    assert ch["affected_by"].get("haste") is True

    # Separately apply a spell affect for the same bit, then remove it.
    spell_af = {"where": "to_affects", "location": "0", "modifier": 0,
                "bitvector": "haste", "type": 1, "duration": 5}
    affect_to_char(ch, spell_af)
    assert ch["affected_by"].get("haste") is True

    affect_remove(ch, ch["affect_list"][-1])

    # The template-granted haste from the boots should still hold the flag.
    assert ch["affected_by"].get("haste") is True


def test_enchanted_item_does_not_apply_template_flag_affects():
    """Enchanted flag on the instance suppresses template flag_affects on equip."""
    _stub_room()
    ch = _player()
    tpl = {"short_descr": "a ring", "wear_flags": {"finger": True},
           "flag_affects": (('affects', '0', 0, {"invisible": True}),)}
    obj = _item(RING_VNUM, tpl)
    obj["enchanted"] = True
    ch["inv"].append(obj)

    equip_char(ch, obj, "finger_l")

    assert not ch.get("affected_by", {}).get("invisible")


def test_multi_bit_entry_applies_modifier_once_sorted():
    """A single F-line entry with multiple bits expands to one dict per bit;
    the modifier attaches only to the first (sorted) bit, matching 1stMud's
    single AffectData node per F line."""
    tpl = {"flag_affects": (
        ('affects', '0', -5, {"pass_door": True, "dark_vision": True}),
    )}
    expanded = tpl_flag_affects(tpl)

    assert [af["bitvector"] for af in expanded] == ["dark_vision", "pass_door"]
    assert [af["modifier"] for af in expanded] == [-5, 0]
    assert all(af["where"] == "to_affects" for af in expanded)
    assert all(af["location"] == "0" for af in expanded)


def _score_out(monkeypatch):
    lines = []
    monkeypatch.setattr(info, "chprintln", lambda ch, s="": (lines.extend(s) if type(s) is list else lines.append(s)))
    return lines


def test_do_affects_equipment_spells_section(monkeypatch):
    """do_affects prints the equipment-spells header and a line naming the
    flag and the item's short_descr when an equipped item grants a bit
    (cf. 1stMud act_info.c:2265ff)."""
    lines = _score_out(monkeypatch)
    ch = _char_base()
    ch["race"] = "Human"  # Human race aff == {} (races.py)
    tpl = {"short_descr": "a Ring of Invisibility", "wear_flags": {"finger": True},
           "flag_affects": (('affects', '0', 0, {"invisible": True}),)}
    obj = _item(RING_VNUM, tpl)
    ch["equip"]["finger_l"] = obj

    equip_ch_affect = tpl_flag_affects(tpl)[0]
    affect_modify(ch, equip_ch_affect, True)

    info.do_affects(ch, [])

    joined = "\n".join(lines)
    assert "You are affected by the following equipment spells:" in joined
    assert any("invisible" in ln and "a Ring of Invisibility" in ln for ln in lines)


def test_enchant_copy_preserves_flag_affects():
    """_enchant_copy_template copies F-line affects to the runtime affect_list
    (cf. 1stMud magic.c:2286-2292: every pIndexData node duplicated, bitvector
    included) without leaking to_affects bits into item extra_flags (1stMud
    affect_to_obj default case, handler.c:1186-1187)."""
    from magic import _enchant_copy_template
    from item import item_extra_flags

    _stub_room()
    tpl = {"short_descr": "a ring", "wear_flags": {"finger": True}, "level": 20,
           "stat_bonuses": {"str": 1},
           "flag_affects": (('affects', '0', 0, {"invisible": True}),)}
    vo = _item(RING_VNUM, tpl)

    _enchant_copy_template(vo, tpl)

    inv = [af for af in vo["affect_list"] if af.get("bitvector") == "invisible"]
    assert len(inv) == 1
    assert inv[0]["where"] == "to_affects"
    assert inv[0]["level"] == 20 and inv[0]["duration"] == -1
    assert not item_extra_flags(vo, tpl).get("invisible")

    # End-to-end: the now-enchanted item still grants the bit, via the
    # runtime affect_list (template affects are skipped once enchanted).
    vo["enchanted"] = True
    ch = _player()
    ch["inv"].append(vo)
    equip_char(ch, vo, "finger_l")
    assert ch["affected_by"].get("invisible") is True


def test_pc_death_keeps_equipment_flags_and_armor(monkeypatch):
    """raw_kill wipes affected_by/armor (1stMud fight.c fidelity), which is
    correct upstream only because the corpse takes all equipment; PrimeSUD
    players keep their gear, so reset_char must re-derive equipment-granted
    bits and AC post-death. [PRIMESUD]"""
    import combat
    import info
    from config import R_STARTING_ROOM

    _stub_room()
    world.rooms._data[R_STARTING_ROOM] = {
        "name": "The Altar", "desc": "x", "exits": {}, "items": [],
        "mobs": [], "area": "test", "flags": {}, "sector": "inside"}
    ITEM_DEFS._data[11] = {  # PC corpse template (cf. area_limbo #11)
        "keywords": "corpse", "short_descr": "The corpse of %s",
        "description": "The corpse of %s is lying here.",
        "type": "pc_corpse", "wear_flags": {}, "level": 0,
        "weight": 1000, "value": 0}
    monkeypatch.setattr(combat, "_death_cry", lambda v: None)
    monkeypatch.setattr(info, "do_look", lambda ch, args: None)

    ch = _player()
    ch["race"] = "Human"
    ch["perm_hit"] = ch["perm_mana"] = ch["perm_move"] = 100
    tpl = {"short_descr": "a Ring of Invisibility", "type": "armor",
           "wear_flags": {"finger": True}, "armor": (10, 10, 10, 10),
           "flag_affects": (('affects', '0', 0, {"invisible": True}),)}
    obj = _item(RING_VNUM, tpl)
    ch["inv"].append(obj)
    equip_char(ch, obj, "finger_l")
    assert ch["affected_by"].get("invisible") is True
    armor_worn = ch["armor"]
    assert armor_worn != (100, 100, 100, 100)

    combat.raw_kill(ch, None)

    assert ch["room"] == R_STARTING_ROOM
    assert ch["equip"]["finger_l"] is obj          # gear kept on respawn
    assert ch["affected_by"].get("invisible") is True
    assert ch["armor"] == armor_worn               # AC re-derived, not stale 100s


def test_do_affects_no_equipment_section_when_matches_race_aff(monkeypatch):
    """The equipment-spells (and generic) gate is exact-set: if the only
    active affected_by bits equal the race's own aff set, nothing about
    equipment prints (cf. 1stMud act_info.c:2264: ch->affected_by != ch->race->aff)."""
    lines = _score_out(monkeypatch)
    ch = _char_base()
    ch["race"] = "Elf"  # races.py Elf aff == {"infrared": True}
    ch["affected_by"]["infrared"] = True
    # No equipped items granting anything beyond the race's own aff.

    info.do_affects(ch, [])

    joined = "\n".join(lines)
    assert "You are affected by the following equipment spells:" not in joined
