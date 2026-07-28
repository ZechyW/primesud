"""Tests for the shared-flag area transform and the invariant it relies on.

`tools/build_dist.py` makes identical template flag dicts share one object per
area file, so a single in-place mutation of a template flag dict would now
corrupt every template sharing it. The runtime test below pins the invariant
that makes the transform safe: spawn paths copy or merge template flags into
fresh instance dicts before anything edits them.
"""

import item
import world
from tools import build_dist
from world import MOB_DEFS, ITEM_DEFS, _load_area

from test_lazy_loading import _item_tpl, _mob_tpl


_MOB_FLAGS = {
    "act_flags": {"sentinel": True},
    "affected_by": {"infrared": True},
    "off_flags": {"dodge": True},
    "imm_flags": {"fire": True},
    "res_flags": {"cold": True},
    "vuln_flags": {"magic": True},
    "form_flags": {"biped": True},
    "part_flags": {"arms": True},
}


def test_shared_flag_variant_preserves_payload_and_reuses_true_maps():
    source = """
AREA = {}
MOBILES = {
    1: {"act_flags": {"sentinel": True}},
    2: {"act_flags": {"sentinel": True}},
    3: {"act_flags": {"_unknown_bits": [4]}},
}
ROOMS = {}
OBJECTS = {
    10: {"wear_flags": {"take": True}},
    11: {"wear_flags": {"take": True}},
    12: {"wear_flags": {}},
    13: {"wear_flags": {}},
}
RESETS = ()
MOBPROGS = {}
OBJPROGS = {}
ROOMPROGS = {}
"""

    transformed, shared = build_dist._share_area_flag_dicts(source)
    before = build_dist._area_payload(source)
    after = build_dist._area_payload(transformed)
    ns = {}
    exec(transformed, ns)

    assert shared == 2
    assert after == before
    assert ns["MOBILES"][1]["act_flags"] is ns["MOBILES"][2]["act_flags"]
    assert ns["OBJECTS"][10]["wear_flags"] is ns["OBJECTS"][11]["wear_flags"]
    # Empty dicts stay distinct: no measurable saving, and `{}` is the shape
    # runtime code is most likely to reach for with setdefault.
    assert ns["OBJECTS"][12]["wear_flags"] is not ns["OBJECTS"][13]["wear_flags"]
    assert "_F0" in transformed


def test_area_payload_tolerates_missing_sections():
    assert build_dist._area_payload("AREA = {}")["MOBILES"] is None


def test_spawned_instances_never_alias_template_flag_dicts(fresh_world):
    """Template flag dicts must never reach an instance by reference."""
    fw = fresh_world
    fw.register_area(
        "alpha", 100, 199,
        rooms={100: {"name": "R100", "exits": {}, "flags": {"safe": True}}},
        mobiles={100: _mob_tpl(**_MOB_FLAGS)},
        objects={150: _item_tpl(extra_flags={"glow": True},
                                wear_flags={"take": True})},
        resets=(("M", 100, 1, 100, 1), ("O", 150, 100)))
    fw.setup()

    _load_area("alpha")

    mob_tpl = MOB_DEFS._data[100]
    spawned = [c for c in world.chars.values() if c.get("tpl") == 100]
    assert spawned, "reset spawned no mob to check"
    for inst in spawned:
        for field, expected in _MOB_FLAGS.items():
            # create_mobile ORs race defaults in, so the instance dict grows;
            # it must be a fresh dict and the template must stay untouched.
            assert inst[field] is not mob_tpl[field]
            assert mob_tpl[field] == expected

    # Items keep flags on the template until first mutated; the mutation must
    # copy rather than edit the template in place.
    item_tpl = ITEM_DEFS._data[150]
    obj = item.create_object(150)
    item.set_item_extra_flag(obj, item_tpl, "had_timer", True)
    assert obj["extra_flags"] is not item_tpl["extra_flags"]
    assert item_tpl["extra_flags"] == {"glow": True}
