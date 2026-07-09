"""Tests for the MOBprogram interpreter core (cf. 1stMud programs.c).

Phase A of MOBPROG_PLAN.md: the pure interpreter (num_eval, expand_arg,
cmd_eval, program_flow control flow, buggy-prog aborts) plus the
mob-as-command-actor spike driving say/emote/north through the real
command interpreter.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from terminal import init_terminal
init_terminal()

import mobprog
import handler
import world
from handler import _char_base
from world import ROOM_DEFS, MOB_DEFS


# -- num_eval ------------------------------------------------------------------

def test_num_eval_operators():
    assert mobprog.num_eval(5, "==", 5)
    assert not mobprog.num_eval(5, "==", 6)
    assert mobprog.num_eval(5, "!=", 6)
    assert mobprog.num_eval(6, ">", 5)
    assert mobprog.num_eval(5, "<", 6)
    assert mobprog.num_eval(5, ">=", 5)
    assert mobprog.num_eval(5, "<=", 5)
    assert not mobprog.num_eval(5, ">", 5)


def test_num_eval_bad_operator_false(monkeypatch):
    logged = []
    monkeypatch.setattr(mobprog, "dbg", lambda m: logged.append(m))
    assert mobprog.num_eval(5, "=<", 5) is False
    assert logged  # logged the invalid oper


# -- expand_arg ----------------------------------------------------------------

def _mob(**kw):
    m = {"name": "big guard", "short_descr": "the big guard", "is_npc": True,
         "sex": "male", "level": 10, "mprog_target": None, "affected_by": {}}
    m.update(kw)
    return m


def _pc(**kw):
    c = {"name": "John Doe", "short_descr": None, "is_npc": False,
         "sex": "female", "level": 5, "affected_by": {}}
    c.update(kw)
    return c


def test_expand_arg_char_codes():
    mob = _mob()
    ch = _pc()
    # $i mob first word (no capitalize), $I mob short, $n ch cap first word
    assert mobprog.expand_arg("$i", mob, ch, None, None, None) == "big"
    assert mobprog.expand_arg("$I", mob, ch, None, None, None) == "the big guard"
    assert mobprog.expand_arg("$n", mob, ch, None, None, None) == "John"
    # $N of a PC = name; of an NPC = short_descr
    assert mobprog.expand_arg("$N", mob, ch, None, None, None) == "John Doe"
    npc_ch = _pc(name="rat", short_descr="a small rat", is_npc=True)
    assert mobprog.expand_arg("$N", mob, npc_ch, None, None, None) == "a small rat"


def test_expand_arg_missing_char_is_someone():
    mob = _mob()
    assert mobprog.expand_arg("$n", mob, None, None, None, None) == "someone"


def test_expand_arg_pronouns():
    mob = _mob(sex="male")
    ch = _pc(sex="female")
    assert mobprog.expand_arg("$j", mob, ch, None, None, None) == "he"   # subject
    assert mobprog.expand_arg("$k", mob, ch, None, None, None) == "him"  # object
    assert mobprog.expand_arg("$l", mob, ch, None, None, None) == "his"  # possessive
    assert mobprog.expand_arg("$e", mob, ch, None, None, None) == "she"
    assert mobprog.expand_arg("$m", mob, ch, None, None, None) == "her"
    assert mobprog.expand_arg("$s", mob, ch, None, None, None) == "her"


def test_expand_arg_literal_and_bad_code(monkeypatch):
    logged = []
    monkeypatch.setattr(mobprog, "dbg", lambda m: logged.append(m))
    mob = _mob()
    out = mobprog.expand_arg("hi $n, meet $i.", mob, _pc(), None, None, None)
    assert out == "hi John, meet big."
    bad = mobprog.expand_arg("x$zy", mob, None, None, None, None)
    assert "<@@@>" in bad
    assert logged


# -- cmd_eval ------------------------------------------------------------------

def test_cmd_eval_rand_bounds(monkeypatch):
    mob = _mob()
    monkeypatch.setattr(mobprog, "_number_percent", lambda: 50)
    assert mobprog.cmd_eval("rand", "100", mob, None, None, None, None, 1)
    assert not mobprog.cmd_eval("rand", "10", mob, None, None, None, None, 1)


def test_cmd_eval_numeric_char_check():
    mob = _mob(level=10)
    assert mobprog.cmd_eval("level", "$i > 5", mob, None, None, None, None, 1)
    assert not mobprog.cmd_eval("level", "$i > 50", mob, None, None, None, None, 1)


def test_cmd_eval_bool_checks():
    mob = _mob()
    pc = _pc()
    # $n is the triggering PC
    assert mobprog.cmd_eval("ispc", "$n", mob, pc, None, None, None, 1)
    assert not mobprog.cmd_eval("isnpc", "$n", mob, pc, None, None, None, 1)
    assert mobprog.cmd_eval("isnpc", "$i", mob, pc, None, None, None, 1)


def test_cmd_eval_flag_check():
    mob = _mob()
    pc = _pc(name="John Doe")
    assert mobprog.cmd_eval("name", "$n john", mob, pc, None, None, None, 1)
    assert not mobprog.cmd_eval("name", "$n mary", mob, pc, None, None, None, 1)


def test_cmd_eval_unported_check_logs_false(monkeypatch):
    logged = []
    monkeypatch.setattr(mobprog, "dbg", lambda m: logged.append(m))
    mob = _mob()
    # 'clan' is valid 1stMud vocab but outside the Phase A subset
    assert mobprog.cmd_eval("clan", "$n", mob, _pc(), None, None, None, 1) is False
    assert any("not ported" in m for m in logged)


# -- program_flow control flow -------------------------------------------------

@pytest.fixture
def dispatched(monkeypatch):
    """Capture dispatched command lines instead of running the interpreter."""
    calls = []
    monkeypatch.setattr(mobprog, "_dispatch",
                        lambda pv, mob, ctrl, expanded: calls.append(expanded))
    return calls


def test_flow_simple_true_branch(dispatched):
    prog = "\n".join([
        "if level $i > 5",
        "say yes",
        "endif",
        "say always",
    ])
    mobprog.program_flow(1, prog, _mob(level=10), None)
    assert dispatched == ["say yes", "say always"]


def test_flow_false_branch_skips(dispatched):
    prog = "\n".join([
        "if level $i > 50",
        "say no",
        "endif",
        "say always",
    ])
    mobprog.program_flow(1, prog, _mob(level=10), None)
    assert dispatched == ["say always"]


def test_flow_if_else_nesting(dispatched):
    prog = "\n".join([
        "if level $i > 5",
        "say outer",
        "if level $i > 50",
        "say inner-skip",
        "else",
        "say inner-else",
        "endif",
        "say after-inner",
        "endif",
        "say end",
    ])
    mobprog.program_flow(1, prog, _mob(level=10), None)
    assert dispatched == ["say outer", "say inner-else", "say after-inner", "say end"]


def test_flow_or_combines(dispatched):
    prog = "\n".join([
        "if level $i > 50",
        "or level $i > 5",
        "say b",
        "endif",
    ])
    mobprog.program_flow(1, prog, _mob(level=10), None)
    assert dispatched == ["say b"]


def test_flow_and_combines(dispatched):
    prog = "\n".join([
        "if level $i > 5",
        "and level $i > 50",
        "say b",
        "endif",
        "say c",
    ])
    mobprog.program_flow(1, prog, _mob(level=10), None)
    assert dispatched == ["say c"]


def test_flow_comment_and_break(dispatched):
    prog = "\n".join([
        "* this is a comment",
        "say one",
        "break",
        "say unreachable",
    ])
    mobprog.program_flow(1, prog, _mob(level=10), None)
    assert dispatched == ["say one"]


def test_flow_expands_codes_before_dispatch(dispatched):
    prog = "say hi $n"
    mobprog.program_flow(1, prog, _mob(), _pc(name="John Doe"))
    assert dispatched == ["say hi John"]


# -- program_flow abort paths (buggy_prog) -------------------------------------

@pytest.fixture
def flow_errors(monkeypatch):
    calls = []
    errs = []
    monkeypatch.setattr(mobprog, "_dispatch",
                        lambda pv, mob, ctrl, expanded: calls.append(expanded))
    monkeypatch.setattr(mobprog, "dbg", lambda m: errs.append(m))
    return calls, errs


def test_abort_endif_without_if(flow_errors):
    calls, errs = flow_errors
    prog = "\n".join(["say before", "endif", "say after"])
    mobprog.program_flow(1, prog, _mob(), None)
    assert calls == ["say before"]        # aborted at the stray endif
    assert any("endif without if" in m for m in errs)


def test_abort_else_without_if(flow_errors):
    calls, errs = flow_errors
    prog = "\n".join(["say before", "else", "say after"])
    mobprog.program_flow(1, prog, _mob(), None)
    assert calls == ["say before"]
    assert any("else without if" in m for m in errs)


def test_abort_unknown_if_check(flow_errors):
    calls, errs = flow_errors
    prog = "\n".join(["if boguscheck $n", "say x", "endif", "say y"])
    mobprog.program_flow(1, prog, _mob(), None)
    assert calls == []                    # aborted at the invalid if_check
    assert any("invalid if_check" in m for m in errs)


def test_abort_max_call_level(flow_errors):
    calls, errs = flow_errors
    mobprog.program_flow(1, "say x", _mob(), None,
                         call_level=mobprog.MAX_CALL_LEVEL)
    assert calls == []
    assert any("max call level" in m for m in errs)


# -- Phase A spike: mob-as-command-actor through the real interpreter ----------

@pytest.fixture
def spike_world(monkeypatch):
    """Two connected rooms, a player and a mob, with captured act() output."""
    old_rd = dict(ROOM_DEFS._data)
    old_wr = dict(world.rooms._data)
    old_ch = dict(world.chars)
    old_md = dict(MOB_DEFS._data)

    def _room(vnum, exits):
        r = {"name": "Room %d" % vnum, "desc": "x", "exits": exits,
             "items": [], "mobs": [], "area": "test", "flags": {},
             "sector": "inside"}
        ROOM_DEFS._data[vnum] = r
        world.rooms._data[vnum] = r
        return r

    _room(9001, {"n": {"to": 9002}})
    _room(9002, {"s": {"to": 9001}})
    MOB_DEFS._data[9405] = {"short_descr": "a test guard", "keywords": "guard",
                            "level": 10}

    player = _char_base()
    player["id"] = 1
    player["is_npc"] = False
    player["name"] = "Tester"
    player["room"] = 9001
    player["pos"] = "standing"
    world.chars[1] = player

    mob = _char_base()
    mob["id"] = 2
    mob["is_npc"] = True
    mob["tpl"] = 9405
    mob["name"] = "guard"
    mob["short_descr"] = "a test guard"
    mob["room"] = 9001
    mob["pos"] = "standing"
    mob["mprog_target"] = None
    world.chars[2] = mob
    world.rooms._data[9001]["mobs"].append(2)

    out = []
    monkeypatch.setattr(handler, "tprint", lambda s="", end="\n": out.append(s))

    yield player, mob, out

    ROOM_DEFS._data.clear(); ROOM_DEFS._data.update(old_rd)
    world.rooms._data.clear(); world.rooms._data.update(old_wr)
    world.chars.clear(); world.chars.update(old_ch)
    MOB_DEFS._data.clear(); MOB_DEFS._data.update(old_md)


def test_spike_mob_say(spike_world):
    player, mob, out = spike_world
    mobprog.program_flow(1, "say Hello There", mob, player)
    # act() TO_ROOM reaches the player; the arg is lowercased by interpret()'s
    # one_argument (documented prog-safety finding).  The {G..{g wrapping is
    # from do_say's own template, not the mob text.
    assert any("says" in l and "hello there" in l for l in out)
    # TO_CHAR (the mob's own line) must NOT leak to the player
    assert not any("You say" in l for l in out)


def test_spike_mob_emote(spike_world):
    player, mob, out = spike_world
    mobprog.program_flow(1, "emote waves happily.", mob, player)
    # act $n renders the actor's *name* ("Guard"), not the short_descr
    assert any("Guard waves happily." in l for l in out)


def test_spike_mob_walks_north(spike_world):
    player, mob, out = spike_world
    mobprog.program_flow(1, "north", mob, player)
    assert mob["room"] == 9002
    assert 2 not in world.rooms._data[9001]["mobs"]
    assert 2 in world.rooms._data[9002]["mobs"]
    # the player, left behind in 9001, saw the mob leave
    assert any("leaves" in l for l in out)


def test_spike_full_prog_chain(spike_world):
    player, mob, out = spike_world
    prog = "\n".join(["say hi $n", "emote nods.", "north"])
    mobprog.program_flow(1, prog, mob, player)
    assert any("says" in l and "hi tester" in l for l in out)
    assert any("nods." in l for l in out)
    assert mob["room"] == 9002
