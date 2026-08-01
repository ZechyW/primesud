"""Tests for do_exits (info.py), do_commands (commands.py), do_consider (combat.py)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import combat
import commands
import info
import world
from world import ROOM_DEFS

from scene_fixture import out, scene  # noqa: F401


class TestExits:
    def test_open_exits_listed_closed_hidden(self, scene, out):
        info.do_exits(scene, [])
        assert out[0] == "Obvious exits:"
        assert any("North - North Room" in l for l in out)
        assert not any("East" in l for l in out)  # closed door hidden

    def test_no_exits(self, scene, out):
        ROOM_DEFS[3001]["exits"] = {}
        info.do_exits(scene, [])
        assert out == ["Obvious exits:", "None."]

    def test_runtime_room_state_shape(self, scene, out):
        # On device world.rooms entries are state-only ({"items", "mobs"});
        # static data lives in ROOM_DEFS. do_exits must not touch world.rooms.
        world.rooms._data[3001] = {"items": [], "mobs": []}
        world.rooms._data[3002] = {"items": [], "mobs": []}
        info.do_exits(scene, [])
        assert any("North - North Room" in l for l in out)


class TestCommands:
    def test_lists_known_commands(self, scene, out, monkeypatch):
        # do_commands routes through the tpage pager, not tprint
        monkeypatch.setattr(commands, "tpage", lambda lines: out.extend(lines))
        monkeypatch.setattr(commands, "CMD_DESC_FILE",
                            os.path.join(ROOT, "src", "commands.txt"))
        commands.do_commands(scene, [])
        blob = "\n".join(out)
        assert "kill" in blob and "look" in blob and "wimpy" in blob


class TestConsider:
    @pytest.mark.parametrize("mob_level,frag", [
        (0,  "naked and weaponless"),
        (5,  "no match for you"),
        (8,  "an easy kill"),
        (11, "The perfect match!"),
        (14, "Do you feel lucky, punk?"),
        (19, "laughs at you mercilessly"),
        (20, "Death will thank you"),
    ])
    def test_level_diff_messages(self, scene, out, mob_level, frag):
        world.chars[2]["level"] = mob_level
        combat.do_consider(scene, ["guard"])
        assert any(frag in l for l in out), out

    def test_not_here(self, scene, out):
        combat.do_consider(scene, ["dragon"])
        assert out == ["They're not here."]
