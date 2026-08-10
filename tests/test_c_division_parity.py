"""C-division parity: sites where the 1stMud C original divides a value that
can be negative at runtime.

C's `/` truncates toward zero; Python's `//` floors.  Every test here pins the
C result with an exact expected value, chosen so the floored result differs.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import combat
import handler
import magic
import mob
import world
from combat import _cdiv, do_bash, do_disarm, one_hit
from config import AC_BASH
from handler import _char_base, mob_condition
from game_time import _trunc_div

ROOM_VNUM = 9601
MOB_TPL_SMALL = 9602
MOB_TPL_MEDIUM = 9603


# ---------------------------------------------------------------------------
# Scaffolding
# ---------------------------------------------------------------------------
def _stub_room(vnum):
    room = {"name": "Test Room", "desc": "A test room.", "exits": {},
            "items": [], "mobs": [], "area": "test", "flags": {},
            "sector": "inside"}
    world.ROOM_DEFS._data[vnum] = room
    world.rooms._data[vnum] = room
    return room


@pytest.fixture
def arena():
    """Two combatants in a throwaway room, torn down afterwards."""
    _stub_room(ROOM_VNUM)
    ch = _char_base()
    ch.update({"id": 9001, "name": "Tester", "level": 20, "room": ROOM_VNUM,
               "learned": {}})
    victim = _char_base()
    victim.update({"id": 9002, "name": "a target", "level": 20,
                   "room": ROOM_VNUM, "is_npc": True, "tpl": MOB_TPL_MEDIUM,
                   "hit": 10 ** 6, "max_hit": 10 ** 6})
    world.chars[9001] = ch
    world.chars[9002] = victim
    world.rooms._data[ROOM_VNUM]["mobs"].append(9002)
    yield ch, victim
    world.chars.pop(9001, None)
    world.chars.pop(9002, None)
    world.rooms._data.pop(ROOM_VNUM, None)
    world.ROOM_DEFS._data.pop(ROOM_VNUM, None)


def _neuter_combat(monkeypatch, damage_sink):
    """Silence the parts of one_hit/do_bash/do_disarm the arithmetic ignores."""
    monkeypatch.setattr(combat, "damage", damage_sink)
    monkeypatch.setattr(combat, "check_improve", lambda *a, **k: None)
    monkeypatch.setattr(combat, "get_skill", lambda *a, **k: 0)
    monkeypatch.setattr(combat, "can_see", lambda *a, **k: True)
    monkeypatch.setattr(combat, "in_stance", lambda *a, **k: True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def test_cdiv_truncates_toward_zero():
    assert _cdiv(-350, 3) == -116      # floor would give -117
    assert _cdiv(-147, 10) == -14      # floor would give -15
    assert _cdiv(-1, 4) == 0           # floor would give -1
    assert _cdiv(350, 3) == 116
    assert _cdiv(-350, -3) == 116
    assert _cdiv(350, -3) == -116
    assert _cdiv(-9, 3) == -3          # exact division: no divergence
    assert _trunc_div(-350, 3) == -116


# ---------------------------------------------------------------------------
# magic.spell_ray_of_truth -- align = -1000 + (align + 1000) / 3
# ---------------------------------------------------------------------------
def test_ray_of_truth_align_truncates_toward_zero(monkeypatch, arena):
    ch, victim = arena
    ch["alignment"] = 1000          # caster is good, so no self-explosion
    victim["alignment"] = -1000     # align = -1350, below the -1000 floor
    seen = []

    monkeypatch.setattr(magic, "act", lambda *a, **k: None)
    monkeypatch.setattr(magic, "chprintln", lambda *a, **k: None)
    monkeypatch.setattr(magic, "dice", lambda n, s: 1000)
    monkeypatch.setattr(magic, "saves_spell", lambda *a, **k: False)
    monkeypatch.setattr(magic, "damage",
                        lambda c, v, dam, *a, **k: seen.append(dam) or True)

    magic.spell_ray_of_truth(0, 30, ch, victim, 0)

    # C: align = -1000 + (-350 / 3) = -1000 + -116 = -1116
    #    dam  = 1000 * 1116 * 1116 / 1000000 = 1245
    # Python floor would give align -1117 -> dam 1247.
    assert seen == [1245]


# ---------------------------------------------------------------------------
# combat.one_hit -- victim_ac = GetArmor(...) / 10 (fight.c:660-669)
# ---------------------------------------------------------------------------
def test_one_hit_victim_ac_truncates_toward_zero(monkeypatch, arena):
    ch, victim = arena
    victim["armor"] = (-147, -147, -147, -147)   # DEX_APP_DEF[13] == 0
    victim["pos"] = "standing"                   # no position AC adjustment
    seen = []

    _neuter_combat(monkeypatch, lambda *a, **k: seen.append(a[2]) or True)
    monkeypatch.setattr(combat, "get_thac0", lambda c: 0)
    monkeypatch.setattr(combat, "get_hitroll", lambda c: 0)
    monkeypatch.setattr(combat, "_get_weapon_skill", lambda c, sn: 80)  # skill 100
    monkeypatch.setattr(combat, "randint",
                        lambda a, b: 14 if (a, b) == (0, 19) else b)

    # C: victim_ac = -147 / 10 = -14, so the miss test is `14 < 0 - (-14)` ->
    # 14 < 14 -> false -> hit.  Python floor gives -15 -> 14 < 15 -> miss.
    assert one_hit(ch, victim) is True
    assert seen and seen[0] > 0


# ---------------------------------------------------------------------------
# combat.one_hit -- dam += GetDamroll(ch) * Min(100, skill) / 100 (fight.c:770)
# ---------------------------------------------------------------------------
def test_one_hit_negative_damroll_truncates_toward_zero(monkeypatch, arena):
    ch, victim = arena
    ch["level"] = 100
    victim["armor"] = (0, 0, 0, 0)
    victim["pos"] = "standing"
    seen = []

    _neuter_combat(monkeypatch, lambda *a, **k: seen.append(a[2]) or True)
    monkeypatch.setattr(combat, "get_thac0", lambda c: 0)
    monkeypatch.setattr(combat, "get_hitroll", lambda c: 0)
    monkeypatch.setattr(combat, "get_damroll", lambda c: -7)
    monkeypatch.setattr(combat, "_get_weapon_skill", lambda c, sn: 25)  # skill 45
    monkeypatch.setattr(combat, "randint",
                        lambda a, b: 19 if (a, b) == (0, 19) else b)

    assert one_hit(ch, victim) is True
    # Unarmed roll takes its max: (2*100/3) * 45/100 = 29; normal stance
    # (player) 29 * 115 / 100 = 33; damroll -7 * 45 / 100 = -3 (C) -> 30.
    # Python floor would give -4 -> 29.
    assert seen == [30]


# ---------------------------------------------------------------------------
# combat.do_bash -- chance -= GetArmor(victim, AC_BASH) / 25 (fight.c:2892)
# ---------------------------------------------------------------------------
def test_do_bash_negative_ac_truncates_toward_zero(monkeypatch, arena):
    ch, victim = arena
    victim["armor"] = (-60, -60, -60, -60)
    victim["pos"] = "standing"
    ch["fighting"] = victim["id"]

    _neuter_combat(monkeypatch, lambda *a, **k: True)
    monkeypatch.setattr(combat, "get_skill", lambda *a, **k: 75)
    monkeypatch.setattr(combat, "is_safe", lambda *a, **k: False)
    monkeypatch.setattr(combat, "_get_size", lambda c: 2)
    monkeypatch.setattr(combat, "randint",
                        lambda a, b: 73 if (a, b) == (1, 100) else a)

    assert victim["armor"][AC_BASH] == -60
    do_bash(ch, [])
    # chance = 75 + 0 + 13 - 17 - (-60/25) = 71 + 2 = 73 (C truncation), so
    # `73 < 73` fails and the bash misses.  Python floor gives -3 -> chance 74,
    # `73 < 74` succeeds and the victim would be knocked to "resting".
    assert victim["pos"] == "standing"


# ---------------------------------------------------------------------------
# combat.do_disarm -- chance += (ch_vict_weapon / 2 - vict_weapon) / 2
# ---------------------------------------------------------------------------
def test_do_disarm_negative_skill_delta_truncates_toward_zero(monkeypatch,
                                                              arena):
    ch, victim = arena
    ch["equip"]["wield"] = {"vnum": 1}
    victim["equip"]["wield"] = {"vnum": 1}
    ch["fighting"] = victim["id"]
    disarmed = []

    _neuter_combat(monkeypatch, lambda *a, **k: True)
    monkeypatch.setattr(combat, "get_skill", lambda *a, **k: 60)
    monkeypatch.setattr(combat, "disarm",
                        lambda c, v: disarmed.append(1))
    monkeypatch.setattr(combat, "_get_weapon_sn",
                        lambda c, slot="wield": ((101 if c is ch else 102),
                                                 {"weapon_type": "sword"}))
    # ch is a master of its own weapon and a novice with the victim's.
    monkeypatch.setattr(
        combat, "_get_weapon_skill",
        lambda c, sn: 100 if sn == 101 else (75 if c is victim else 0))
    monkeypatch.setattr(combat, "randint",
                        lambda a, b: 9 if (a, b) == (1, 100) else a)

    do_disarm(ch, [])
    # chance = 60*100/100 + (0/2 - 75)/2 + 13 - 26 + 0
    #        = 60 + (-37) + 13 - 26 = 10 (C truncation) -> `9 < 10` disarms.
    # Python floor gives -38 -> chance 9 -> `9 < 9` fails.
    assert disarmed == [1]


# ---------------------------------------------------------------------------
# mob.create_mobile -- perm_stat[CON] += (size - SIZE_MEDIUM) / 2 (db.c:1885)
# ---------------------------------------------------------------------------
@pytest.fixture
def small_mob_tpl():
    tpl = {"short_descr": "a small test mob", "level": 10,
           "hp_dice": (1, 1, 10), "hitroll": 0, "armor": (0, 0, 0, 0),
           "damage": (1, 2, 0), "dam_type": "punch", "size": "small"}
    world.MOB_DEFS._data[MOB_TPL_SMALL] = tpl
    yield tpl
    world.MOB_DEFS._data.pop(MOB_TPL_SMALL, None)


def test_small_mob_con_truncates_toward_zero(small_mob_tpl):
    inst = mob.create_mobile(MOB_TPL_SMALL)
    # base = min(25, 11 + 10/4) = 13; size_delta = SIZE_SMALL - SIZE_MEDIUM = -1
    # C: con += -1/2 = 0 -> 13.  Python floor would give -1 -> 12.
    assert inst["perm_stat"]["con"] == 13
    assert inst["perm_stat"]["str"] == 12   # str takes the raw delta


# ---------------------------------------------------------------------------
# handler.mob_condition -- percent = (100 * hit) / max_hit (act_info.c:415)
# ---------------------------------------------------------------------------
def test_mob_condition_negative_hp_truncates_toward_zero():
    tpl = {"short_descr": "a dying mob"}
    inst = {"name": "a dying mob", "hit": -1, "max_hit": 200}
    # C: (100 * -1) / 200 == 0 -> the `percent >= 0` bucket.
    # Python floor gives -1 -> "bleeding to death".
    assert mob_condition(inst, tpl) == "A dying mob is in awful condition."


def test_mob_condition_deeply_negative_hp_still_bleeds():
    tpl = {"short_descr": "a dying mob"}
    inst = {"name": "a dying mob", "hit": -10, "max_hit": 200}
    # C: -1000 / 200 == -5 -> below zero -> "bleeding to death".
    assert mob_condition(inst, tpl) == "A dying mob is bleeding to death."


def test_mob_condition_zero_max_hit_sentinel():
    tpl = {"short_descr": "a broken mob"}
    inst = {"name": "a broken mob", "hit": 5, "max_hit": 0}
    assert mob_condition(inst, tpl) == "A broken mob is bleeding to death."
