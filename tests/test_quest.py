"""Tests for the auto-quest system (quest.py) vs 1stMud quest.c."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "primesud.hpappdir")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from terminal import init_terminal
init_terminal()

import world
from world import ROOM_DEFS, MOB_DEFS, ITEM_DEFS
from handler import _char_base
import quest
from quest import (do_quest, generate_quest, quest_update, quest_room_check,
                   quest_obj_check, quest_kill_check, quest_complete,
                   end_quest, is_quester, _random_quest_mob,
                   QUEST_NONE, QUEST_KILL, QUEST_RETRIEVE, QUEST_FINDROOM,
                   QUEST_FINDMOB, QUEST_RETURN_KILL, QUEST_RETURN_RETRIEVE,
                   QUEST_TIME, _QUEST_PIECES)
from config import mins_to_ticks

QUESTMASTER_ROOM = 200  # quest area; Edurin (mob 200) resets here


@pytest.fixture
def fresh():
    # area .dat files load via cwd-relative paths
    old_cwd = os.getcwd()
    os.chdir(os.path.join(ROOT, _SRC))
    world.init_world()
    world.reset_lazy()
    ch = _char_base()
    ch["id"] = 1
    ch["name"] = "Tester"
    ch["level"] = 10
    ch["room"] = QUESTMASTER_ROOM
    ch["gold"] = 0
    for k in ("quest_points", "quest_status", "quest_time", "quest_mob",
              "quest_obj", "quest_room", "quest_giver"):
        ch[k] = 0
    for k in ("quest_mob_name", "quest_room_name", "quest_area_name"):
        ch[k] = ""
    ch["trivia"] = 0
    world.chars[1] = ch
    ROOM_DEFS[QUESTMASTER_ROOM]  # trigger quest area load + reset
    yield ch
    os.chdir(old_cwd)


def _questman(ch):
    return quest._find_spec_mob(ch, "spec_questmaster")


def test_questmaster_present(fresh):
    assert _questman(fresh) is not None


def test_random_quest_mob_valid(fresh):
    picked = _random_quest_mob(fresh)
    assert picked is not None
    mvnum, rvnum, adef = picked
    tpl = MOB_DEFS[mvnum]
    assert abs(tpl["level"] - fresh["level"]) <= 10
    assert not tpl.get("shop")
    assert adef["tag"] not in ("limbo", "quest", "immort")
    assert rvnum in ROOM_DEFS._data


def test_request_assigns_quest(fresh):
    do_quest(fresh, ["request"])
    assert is_quester(fresh)
    assert fresh["quest_giver"] == 200
    assert mins_to_ticks(15) <= fresh["quest_time"] <= mins_to_ticks(30)
    from quest import QUEST_DELIVER
    assert fresh["quest_status"] in (QUEST_KILL, QUEST_RETRIEVE,
                                     QUEST_DELIVER, QUEST_FINDROOM,
                                     QUEST_FINDMOB)
    if fresh["quest_status"] == QUEST_RETRIEVE:
        # token physically placed in the quest room
        assert fresh["quest_obj"] in _QUEST_PIECES
        items = world.rooms[fresh["quest_room"]]["items"]
        assert any(o["vnum"] == fresh["quest_obj"] for o in items)
    if fresh["quest_status"] == QUEST_DELIVER:
        # token handed to the player
        assert fresh["quest_obj"] in _QUEST_PIECES
        assert any(o["vnum"] == fresh["quest_obj"] for o in fresh["inv"])
    if fresh["quest_status"] in (QUEST_KILL, QUEST_FINDMOB, QUEST_DELIVER):
        assert fresh["quest_mob"] > 0


def test_request_while_on_quest_rejected(fresh):
    do_quest(fresh, ["request"])
    status = fresh["quest_status"]
    do_quest(fresh, ["request"])
    assert fresh["quest_status"] == status  # unchanged


def test_kill_flow(fresh):
    fresh["quest_status"] = QUEST_KILL
    fresh["quest_giver"] = 200
    fresh["quest_time"] = 20
    fresh["quest_mob"] = 3062  # any vnum; victim faked below
    victim = {"is_npc": True, "tpl": 3062, "id": 99}
    quest_kill_check(fresh, victim)
    assert fresh["quest_status"] == QUEST_RETURN_KILL
    # complete at questmaster pays out
    before = fresh["quest_points"]
    assert quest_complete(fresh, _questman(fresh)) is True
    assert fresh["quest_status"] == QUEST_NONE
    assert fresh["quest_points"] > before
    assert fresh["gold"] > 0
    assert fresh["quest_time"] == mins_to_ticks(QUEST_TIME)  # cooldown


def test_retrieve_flow(fresh):
    fresh["quest_status"] = QUEST_RETRIEVE
    fresh["quest_giver"] = 200
    fresh["quest_time"] = 20
    fresh["quest_obj"] = _QUEST_PIECES[0]
    token = {"vnum": _QUEST_PIECES[0]}
    # not carrying: complete refuses without reward
    assert quest_complete(fresh, _questman(fresh)) is False
    # pickup flips to return state
    fresh["inv"].append(token)
    quest_obj_check(fresh, token)
    assert fresh["quest_status"] == QUEST_RETURN_RETRIEVE
    assert quest_complete(fresh, _questman(fresh)) is True
    assert fresh["quest_status"] == QUEST_NONE
    assert token not in fresh["inv"]  # token extracted on reward


def test_findroom_flow(fresh):
    fresh["quest_status"] = QUEST_FINDROOM
    fresh["quest_giver"] = 200
    fresh["quest_time"] = 20
    fresh["quest_room"] = QUESTMASTER_ROOM
    quest_room_check(fresh)
    assert fresh["quest_status"] == quest.QUEST_RETURN_FINDROOM


def test_timeout_penalizes(fresh):
    fresh["quest_status"] = QUEST_KILL
    fresh["quest_time"] = 1
    quest_update()
    assert fresh["quest_status"] == QUEST_NONE
    assert fresh["quest_time"] == mins_to_ticks(QUEST_TIME - 2)  # lockout


def test_quit_penalizes(fresh):
    do_quest(fresh, ["request"])
    if not is_quester(fresh):  # rare "no quests available" roll
        pytest.skip("no quest target rolled")
    do_quest(fresh, ["quit"])
    assert fresh["quest_status"] == QUEST_NONE
    # [PRIMESUD] lenient quit penalty: announced 15, not 1stMud's 30
    assert fresh["quest_time"] == mins_to_ticks(QUEST_TIME * 3 // 4)


def test_qp_cap_32000(fresh):
    fresh["quest_points"] = 31990
    fresh["quest_status"] = QUEST_RETURN_KILL
    fresh["quest_giver"] = 200
    fresh["quest_time"] = 10
    quest_complete(fresh, _questman(fresh))
    assert fresh["quest_points"] <= 32000
    assert fresh["gold"] > 0  # overflow converted to gold


def test_shop_list_and_buy(fresh):
    do_quest(fresh, ["list"])  # no crash
    do_quest(fresh, ["buy", "shield"])  # 0 qp: refused
    assert not any(o["vnum"] == 210 for o in fresh["inv"])
    fresh["quest_points"] = 1000
    do_quest(fresh, ["buy", "shield"])
    assert fresh["quest_points"] == 250  # 750 deducted
    obj = next(o for o in fresh["inv"] if o["vnum"] == 210)
    # update_questobj scaling: level, cost, armor override, applies
    assert obj["level"] == fresh["level"]
    assert obj["cost"] == 750
    v = max(20, fresh["level"])
    assert obj["armor"] == (v, v, v, 5 * v // 6)
    pbonus = max(5, fresh["level"] // 5)
    locs = {af["location"]: af["modifier"] for af in obj["affect_list"]}
    assert locs["damroll"] == pbonus and locs["hitroll"] == pbonus
    assert obj["wear_flags"].get("no_sac")


def test_quest_sword_instance_dice_in_combat(fresh):
    # one_hit must read instance dice (tpl dice are (-1,-1,0) placeholders)
    from combat import one_hit
    fresh["quest_points"] = 2500
    do_quest(fresh, ["buy", "sword"])
    sword = next(o for o in fresh["inv"] if o["vnum"] == 203)
    assert sword["dice"] == (15, 4, 0)  # max(15, level 10)
    fresh["inv"].remove(sword)
    fresh["equip"]["wield"] = sword
    fresh["learned"] = {}
    victim = _char_base()
    victim.update({"is_npc": True, "tpl": 200, "id": 99, "level": 10,
                   "room": QUESTMASTER_ROOM, "hit": 10 ** 6,
                   "max_hit": 10 ** 6})
    world.chars[99] = victim
    for _ in range(100):
        one_hit(fresh, victim)
        if victim["hit"] < 10 ** 6:
            break
    assert victim["hit"] < 10 ** 6


def test_shop_sell_back_third(fresh):
    fresh["quest_points"] = 750
    do_quest(fresh, ["buy", "shield"])
    assert fresh["quest_points"] == 0
    do_quest(fresh, ["sell", "shield"])
    assert fresh["quest_points"] == 750 // 3
    assert not any(o["vnum"] == 210 for o in fresh["inv"])


def test_shop_identify(fresh):
    do_quest(fresh, ["identify", "aura"])  # free, no crash, nothing kept
    assert not any(o["vnum"] == 201 for o in fresh["inv"])


def test_update_all_qobjs_rescales_on_levelup(fresh):
    from quest import update_all_qobjs
    fresh["quest_points"] = 750
    do_quest(fresh, ["buy", "shield"])
    obj = next(o for o in fresh["inv"] if o["vnum"] == 210)
    fresh["level"] = 40
    update_all_qobjs(fresh)
    assert obj["level"] == 40
    assert obj["armor"] == (40, 40, 40, 33)
    locs = {af["location"]: af["modifier"] for af in obj["affect_list"]}
    assert locs["damroll"] == 8  # max(5, 40//5)
    # affects updated in place, not stacked
    assert len([a for a in obj["affect_list"] if a["location"] == "damroll"]) == 1


def _fake_room_mob(fresh, tpl_vnum, mob_id=99):
    """Register a live mob of tpl_vnum in the player's room."""
    victim = _char_base()
    victim.update({"is_npc": True, "tpl": tpl_vnum, "id": mob_id,
                   "level": 10, "room": fresh["room"]})
    world.chars[mob_id] = victim
    world.rooms[fresh["room"]]["mobs"].append(mob_id)
    return victim


def test_deliver_flow(fresh):
    from quest import generate_quest, QUEST_DELIVER, QUEST_RETURN_DELIVER
    from inventory import do_give
    generate_quest(fresh, _questman(fresh), QUEST_DELIVER)
    assert fresh["quest_status"] == QUEST_DELIVER
    assert fresh["quest_mob"] > 0
    token = next(o for o in fresh["inv"] if o["vnum"] in _QUEST_PIECES)
    assert token["vnum"] == fresh["quest_obj"]
    # deliver target must not be aggressive (incl. race flags) or spec'd [PRIMESUD]
    from quest import _merged_act_flags
    mtpl = MOB_DEFS[fresh["quest_mob"]]
    assert not _merged_act_flags(mtpl).get("aggressive")
    assert not mtpl.get("spec_fun")
    # wrong recipient refused
    tok_kw = ITEM_DEFS[token["vnum"]]["keywords"].split()[0]
    do_give(fresh, [tok_kw, "edurin"])
    assert fresh["quest_status"] == QUEST_DELIVER
    assert token in fresh["inv"]
    # right recipient (any instance of the vnum) completes the errand
    victim = _fake_room_mob(fresh, fresh["quest_mob"])
    v_kw = MOB_DEFS[victim["tpl"]]["keywords"].split()[0]
    do_give(fresh, [tok_kw, v_kw])
    assert fresh["quest_status"] == QUEST_RETURN_DELIVER
    assert token not in fresh["inv"]
    assert token not in victim["inv"]  # extracted, not transferred
    assert fresh["quest_obj"] == 0 and fresh["quest_mob"] == 0
    # questmaster pays out
    before = fresh["quest_points"]
    assert quest_complete(fresh, _questman(fresh)) is True
    assert 32 <= fresh["quest_points"] - before <= 40  # randint(4/5, full) of 40


def test_give_coins_and_item(fresh):
    from inventory import do_give
    victim = _fake_room_mob(fresh, 202)  # the Registrar; resets elsewhere
    v_kw = MOB_DEFS[202]["keywords"].split()[0]
    fresh["gold"] = 100
    do_give(fresh, ["40", "gold", v_kw])
    assert fresh["gold"] == 60 and victim["gold"] == 40
    do_give(fresh, ["70", "gold", v_kw])  # more than carried
    assert fresh["gold"] == 60 and victim["gold"] == 40
    # plain item hand-over
    from item import create_object
    obj = create_object(214)
    obj["extra_flags"] = {}  # instance override: plain giveable item
    fresh["inv"].append(obj)
    kw = ITEM_DEFS[214]["keywords"].split()[0]
    do_give(fresh, [kw, v_kw])
    assert obj not in fresh["inv"] and obj in victim["inv"]


def test_give_changer_exchanges_coins(fresh):
    from inventory import do_give
    victim = _fake_room_mob(fresh, 202)
    victim["act_flags"] = {"changer": True}
    victim["name"] = "The Registrar"
    v_kw = MOB_DEFS[202]["keywords"].split()[0]
    fresh["gold"] = 10
    fresh["silver"] = 0
    do_give(fresh, ["10", "gold", v_kw])
    assert fresh["gold"] == 0
    assert fresh["silver"] == 950  # 95 silver per gold
    do_give(fresh, ["300", "silver", v_kw])
    assert fresh["silver"] == 950 - 300 + (95 * 300 // 100 - 2 * 100)  # remainder back
    assert fresh["gold"] == 2  # 95*300/100/100
    # too little to change: refunded
    silver_before = fresh["silver"]
    do_give(fresh, ["1", "silver", v_kw])
    assert fresh["silver"] == silver_before


def test_give_quest_item_refused(fresh):
    from inventory import do_give
    victim = _fake_room_mob(fresh, 202)
    v_kw = MOB_DEFS[202]["keywords"].split()[0]
    fresh["quest_points"] = 750
    do_quest(fresh, ["buy", "shield"])
    do_give(fresh, ["shield", v_kw])
    assert any(o["vnum"] == 210 for o in fresh["inv"])  # still ours
    assert not victim["inv"]


def test_end_quest_clears_state(fresh):
    fresh["quest_status"] = QUEST_KILL
    fresh["quest_mob"] = 1234
    fresh["quest_mob_name"] = "someone"
    end_quest(fresh, 5)
    assert fresh["quest_status"] == QUEST_NONE
    assert fresh["quest_mob"] == 0
    assert fresh["quest_mob_name"] == ""
    assert fresh["quest_time"] == mins_to_ticks(5)


def _goto_spec(fresh, spec):
    for rv, room in world.rooms._data.items():
        for mid in room["mobs"]:
            inst = world.chars.get(mid)
            if inst and MOB_DEFS[inst["tpl"]].get("spec_fun") == spec:
                fresh["room"] = rv
                return True
    return False


def test_tpspend(fresh):
    from quest import do_tpspend
    assert _goto_spec(fresh, "spec_triviamob")
    do_tpspend(fresh, ["list"])  # no crash
    fresh["trivia"] = 3
    fresh["practice"] = 0
    fresh["train"] = 0
    do_tpspend(fresh, ["practices"])
    assert fresh["practice"] == 40 and fresh["trivia"] == 2
    do_tpspend(fresh, ["trains"])
    assert fresh["train"] == 5 and fresh["trivia"] == 1
    do_tpspend(fresh, ["questpoints"])
    assert fresh["quest_points"] == 75 and fresh["trivia"] == 0
    do_tpspend(fresh, ["pill"])  # broke: falls back to list, no purchase
    assert not any(o["vnum"] == 200 for o in fresh["inv"])
    fresh["trivia"] = 1
    do_tpspend(fresh, ["pill"])
    assert any(o["vnum"] == 200 for o in fresh["inv"])
    assert fresh["trivia"] == 0


# -- gquest ---------------------------------------------------------------

def test_gquest_start_join_kill_complete(fresh):
    import gquest
    from gquest import (do_gquest, gquest_update, gq_kill_check, gq_reset,
                        gquest_info, GQUEST_WAITING, GQUEST_RUNNING, GQUEST_OFF)
    gq_reset()
    fresh["room"] = 202  # registar's room (mob 202 resets at room 201... find via spec)
    # place player in the registar's actual room
    for rv, room in world.rooms._data.items():
        for mid in room["mobs"]:
            inst = world.chars.get(mid)
            if inst and MOB_DEFS[inst["tpl"]].get("spec_fun") == "spec_registar":
                fresh["room"] = rv
                break
    fresh["trivia"] = 10
    do_gquest(fresh, ["start", "1", "30", "5"])
    assert gquest_info["running"] == GQUEST_WAITING
    assert len(gquest_info["mobs"]) == 5
    assert len(set(gquest_info["mobs"])) == 5  # distinct targets
    assert fresh["trivia"] == 10 - (5 + 5 // 5)
    do_gquest(fresh, ["join"])
    assert gquest_info["joined"]
    assert gquest_info["pmobs"] == gquest_info["mobs"]
    # waiting timer (3-minute join window) runs out -> running
    for _ in range(mins_to_ticks(3) + 2):
        gquest_update()
    assert gquest_info["running"] == GQUEST_RUNNING
    # kill all targets
    for vnum in list(gquest_info["mobs"]):
        gq_kill_check(fresh, {"is_npc": True, "tpl": vnum, "id": 99})
    assert all(v == -1 for v in gquest_info["pmobs"])
    qp_before = fresh["quest_points"]
    gold_before = fresh["gold"]
    do_gquest(fresh, ["complete"])
    assert gquest_info["running"] == GQUEST_OFF
    assert fresh["quest_points"] > qp_before
    assert fresh["gold"] > gold_before


def test_gquest_countdown_announcement(fresh, capsys):
    import gquest
    from gquest import gquest_update, gq_reset, gquest_info
    gq_reset()
    gquest_info["timer"] = 41  # decrements to 40 -> announce (20 real min)
    gquest_update()
    assert gquest_info["timer"] == 40
    assert "global quest will begin in about 20 minutes" in capsys.readouterr().out
    gquest_update()  # 39: no announcement
    assert "global quest" not in capsys.readouterr().out


def test_gquest_auto_delay_uses_configured_range(fresh, monkeypatch):
    import gquest
    from gquest import end_gquest, gq_reset, gquest_info
    monkeypatch.setattr(gquest, "GQUEST_AUTO_DELAY_MIN", 7)
    monkeypatch.setattr(gquest, "GQUEST_AUTO_DELAY_MAX", 7)
    end_gquest()
    assert gquest_info["timer"] == mins_to_ticks(7)
    # New games use the fixed initial delay instead
    monkeypatch.setattr(gquest, "GQUEST_INITIAL_DELAY", 9)
    gq_reset()
    assert gquest_info["timer"] == mins_to_ticks(9)


def test_gquest_save_roundtrip(fresh):
    from gquest import gq_save_lines, gq_load_line, gquest_info, gq_reset
    gq_reset()
    gquest_info.update({"running": 2, "timer": 42, "mob_count": 3,
                        "minlevel": 5, "maxlevel": 20, "qpoints": 60,
                        "gold": 300, "cost": 6, "who": "Tester",
                        "mobs": [301, 302, 303], "joined": True,
                        "pmobs": [301, -1, 303]})
    lines = gq_save_lines()
    snapshot = dict(gquest_info, mobs=list(gquest_info["mobs"]),
                    pmobs=list(gquest_info["pmobs"]))
    gq_reset()
    for line in lines:
        key, val = line.split("=", 1)
        assert gq_load_line(key, val)
    for k in snapshot:
        assert gquest_info[k] == snapshot[k], k
