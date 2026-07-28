"""Regression test for build_dist.PRESERVE_LOCALS.

Without the preserved names, python-minifier renames `_best_hand_layout`'s
captured locals into its comprehension variables and the nested closures bind
to a cell object instead of the player dict -- `wear best` then crashes on
device with a type error deep in `get_curr_stat`. Nothing in the .py symbol
check or the area data check catches a miscompile inside a function body, so
exercise the minified module directly.
"""

import sys
import types

import pytest

sys.path.insert(0, "../tools")
from tools import build_dist
from test_phase1_cmds import out, scene  # noqa: F401

_HAND_SLOTS = ("wield", "secondary", "shield", "hold")


@pytest.fixture(scope="module")
def minified_inventory():
    source = open("../src/inventory.py", encoding="utf-8").read()
    code = build_dist.minify_source(source,
                                    build_dist.PRESERVE_LOCALS["inventory.py"])
    module = types.ModuleType("inventory_minified")
    exec(compile(code, "inventory_minified", "exec"), module.__dict__)
    return module


def test_minified_best_hand_layout_runs(minified_inventory, scene, out):
    """The minified build must reach the same layout as the source build."""
    import inventory

    scene["equip"].update({slot: None for slot in _HAND_SLOTS})
    start_equip = dict(scene["equip"])
    start_inv = list(scene["inv"])

    assert inventory._best_hand_layout(scene) is True
    expected_hands = {k: scene["equip"].get(k) for k in _HAND_SLOTS}

    # _best_hand_layout equips out of the inventory list, so replay from the
    # same starting state rather than clearing the slots.
    scene["equip"].clear()
    scene["equip"].update(start_equip)
    scene["inv"][:] = start_inv

    assert minified_inventory._best_hand_layout(scene) is True
    assert {k: scene["equip"].get(k) for k in _HAND_SLOTS} == expected_hands
