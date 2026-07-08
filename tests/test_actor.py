"""act()/chprint* message routing and formatting (moved from debug/test_actor_messages.py)."""
import pytest

import handler
import world


@pytest.fixture
def scene(monkeypatch):
    seen = []
    monkeypatch.setattr(handler, "tprint", lambda msg: seen.append(msg))
    player = {"id": 1, "room": 100, "name": "Player", "pos": "standing"}
    mob = {"id": 2, "room": 100, "name": "a goblin", "is_npc": True,
           "sex": "male", "pos": "standing"}
    other = {"id": 3, "room": 100, "name": "Victim", "pos": "standing"}
    monkeypatch.setattr(world, "chars", {1: player, 2: mob, 3: other})
    return {"seen": seen, "player": player, "mob": mob, "other": other}


# _perform_act appends {x color reset; upper() capitalizes first visible char

def test_act_to_char(scene):
    handler.act("you hit it", ch=scene["player"], arg2=scene["mob"], type=handler.TO_CHAR)
    assert scene["seen"] == ["You hit it{x"]


def test_act_to_vict(scene):
    handler.act("$n hits you", scene["mob"], None, scene["player"], handler.TO_VICT)
    assert scene["seen"] == ["A goblin hits you{x"]


def test_act_to_room(scene):
    handler.act("$n snarls", scene["mob"], None, scene["other"], handler.TO_ROOM)
    assert scene["seen"] == ["A goblin snarls{x"]


def test_act_to_notvict_excludes_player(scene):
    handler.act("$n bites $N", scene["mob"], None, scene["player"], handler.TO_NOTVICT)
    assert scene["seen"] == []


def test_act_dollar_upper_n(scene):
    handler.act("You rescue $N.", scene["player"], None, scene["other"], handler.TO_CHAR)
    assert scene["seen"] == ["You rescue Victim.{x"]


def test_act_pc_name_substitution(scene):
    handler.act("$n kicks dirt in your eyes!", scene["other"], None,
                scene["player"], handler.TO_VICT)
    assert scene["seen"] == ["Victim kicks dirt in your eyes!{x"]


def test_chprint_gates_npcs(scene):
    assert handler.chprint(scene["player"], "direct-noformat") == 1
    assert handler.chprint(scene["mob"], "skip-noformat") == 0
    assert scene["seen"] == ["direct-noformat"]


def test_chprintln_gates_npcs(scene):
    handler.chprintln(scene["player"], "direct")
    handler.chprintln(scene["mob"], "skip")
    assert scene["seen"] == ["direct"]


def test_chprintf(scene):
    assert handler.chprintf(scene["player"], "hp: %d", 7) == 1
    assert handler.chprintf(scene["mob"], "hp: %d", 9) == 0
    assert scene["seen"] == ["hp: 7"]


def test_chprintlnf(scene):
    assert handler.chprintlnf(scene["player"], "%s %d", "lvl", 3) == 1
    assert handler.chprintlnf(scene["player"], None) == 1
    assert scene["seen"] == ["lvl 3", ""]
