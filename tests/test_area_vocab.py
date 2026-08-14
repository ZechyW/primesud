"""Data-word lint over src/area_*.txt (field spec: docs/AREA_FILES.md). [PRIMESUD]

Every enumerated string field must match the vocabulary it is looked up
against at runtime.  Unknown words degrade silently -- weapon_type falls
back to exotic, stat_bonuses locations no-op, flag keys go dead -- and
1stMud's loader was MORE lenient than PrimeSUD's exact dict lookups
(weapon_class in handler.c prefix-matches, so upstream survived chess2's
truncated "polear"; see docs/FIXES.md).  This lint makes exact matching
safe by rejecting unknown words at test time instead.

Vocabularies come from the engine table that consumes each field where one
exists (ATTACK_TABLE, _WEAPON_CLASS_NUM, _WEAPON_FLAG_BIT), else from the
converter's canonical decode maps (tools/are_to_primesud.py), which are the
single source for what conversion can ever emit.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import are_to_primesud as conv

import config
import item

_ATTACK = set(config.ATTACK_TABLE)
_UNK = {"_unknown_bits"}  # lossless leftover key emitted by the converter

# field -> allowed words; dict-valued fields lint their keys, str fields
# their value.  Absent fields are skipped (presence rules live in the
# loader/converter, not here).
_OBJ_VOCAB = {
    "type":            set(conv.ITEM_TYPE_NUM.values()),
    "wear_flags":      set(conv.WEAR_SLOT.values()) | {"take"} | _UNK,
    "extra_flags":     set(conv.EXTRA_FLAGS.values()) | _UNK,
    "weapon_type":     set(item._WEAPON_CLASS_NUM),
    "dam_type":        _ATTACK,
    "weapon_flags":    set(item._WEAPON_FLAG_BIT) | _UNK,
    "container_flags": set(conv.CONTAINER_FLAGS.values()) | _UNK,
    "stat_bonuses":    set(conv.APPLY_LOC.values()),
}
_RESIST = set(conv.RESIST_FLAGS.values()) | _UNK
_MOB_VOCAB = {
    "dam_type":    _ATTACK,
    "act_flags":   set(conv.ACT_FLAGS.values()) | _UNK,
    "affected_by": set(conv.AFFECTED_BY.values()) | _UNK,
    "off_flags":   set(conv.OFF_FLAGS.values()) | _UNK,
    "imm_flags":   _RESIST,
    "res_flags":   _RESIST,
    "vuln_flags":  _RESIST,
    "form_flags":  set(conv.FORM_FLAGS.values()) | _UNK,
    "part_flags":  set(conv.PART_FLAGS.values()) | _UNK,
}
_ROOM_VOCAB = {
    "flags":  set(conv.ROOM_FLAGS.values()) | _UNK,
    "sector": set(conv.SECTOR_NAMES.values()),
}
# flag_affects (where, loc, modifier, flags): flag vocab depends on `where`
# (docs/AREA_FILES.md sec. flag_affects)
_FLAG_AFFECT_WHERE = {
    "affects": set(conv.AFFECTED_BY.values()) | _UNK,
    "immune":  _RESIST,
    "resist":  _RESIST,
    "vuln":    _RESIST,
}

# cwd is pinned to src/ (tests/conftest.py), so area files resolve bare
AREA_FILES = sorted(f for f in os.listdir(".")
                    if f.startswith("area_") and f.endswith(".txt"))


def _words(value):
    return value.keys() if isinstance(value, dict) else (value,)


def _lint(defs, vocab, label, errors):
    for vnum in sorted(defs):
        d = defs[vnum]
        for field, allowed in sorted(vocab.items()):
            if field not in d:
                continue
            for w in _words(d[field]):
                if w not in allowed:
                    errors.append("%s %d %s: %r" % (label, vnum, field, w))
        for entry in d.get("flag_affects", ()):
            where, flags = entry[0], entry[3]
            allowed = _FLAG_AFFECT_WHERE.get(where)
            if allowed is None:
                errors.append("%s %d flag_affects where: %r" % (label, vnum, where))
                continue
            for w in flags:
                if w not in allowed:
                    errors.append("%s %d flag_affects[%s]: %r" % (label, vnum, where, w))


def test_area_file_list_nonempty():
    assert len(AREA_FILES) > 20  # guard against a silently-empty sweep


@pytest.mark.parametrize("fname", AREA_FILES)
def test_area_data_words(fname):
    ns = {}
    with open(fname) as f:
        exec(f.read(), ns)
    errors = []
    _lint(ns.get("OBJECTS", {}), _OBJ_VOCAB, "obj", errors)
    _lint(ns.get("MOBILES", {}), _MOB_VOCAB, "mob", errors)
    _lint(ns.get("ROOMS", {}), _ROOM_VOCAB, "room", errors)
    assert not errors, fname + " unknown data words:\n" + "\n".join(errors)
