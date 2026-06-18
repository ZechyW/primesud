"""Dormant save-format replay probe for HP Prime debugging."""

from config import FNKEY_NAMES
from util import gc_collect
from world import RESETS
from player import create_char, SAVE_VERSION, _EQUIP_SAVE_ORDER
from mob import reset_area, create_area_states
from inventory import do_outfit
from macros import _MACRO_SUBST


def save_format_probe(tr):
    """Replay save-line formatting close to the observed G1 failure."""
    def _try_join(name, lines):
        bad = -1
        for i in range(len(lines)):
            if not isinstance(lines[i], str):
                bad = i
                break
        ok = True
        err = ""
        if bad < 0:
            try:
                "~".join(lines)
            except Exception as e:
                ok = False
                err = str(e)
        tr.print(name + " n=" + str(len(lines)) +
                 " bad=" + str(bad) + " join=" + str(ok))
        if bad >= 0:
            tr.print("bad line: " + str(lines[bad]))
        if err:
            tr.print(err)
        return bad >= 0 or not ok

    def _build(prefix, area_mode, areas, player, rooms, mobs):
        lines = ["v=%s" % SAVE_VERSION]
        for key in ("name", "level", "xp", "xp_next",
                    "str", "dex", "int", "wis", "con",
                    "hp", "hp_max", "mp", "mp_max",
                    "hitroll", "damroll", "AC", "room",
                    "practice", "train", "flags", "played"):
            lines.append("p.%s=%s" % (key, player[key]))
        lines.append("p.inv=%s" % "|".join(
            "%s:%s" % (o["vnum"], o["cost"]) for o in player["inv"]))
        for slot in _EQUIP_SAVE_ORDER:
            obj = player["equip"][slot]
            lines.append("p.eq.%s=%s" % (
                slot, "%s:%s" % (obj["vnum"], obj["cost"]) if obj is not None else ""))
        learned_parts = []
        for sk in sorted(player["learned"]):
            learned_parts.append("%s:%s" % (sk, player["learned"][sk]))
        lines.append("p.learned=%s" % "|".join(learned_parts))
        for k in sorted(player["_macros"]):
            lines.append("p.macro.%s=%s" % (FNKEY_NAMES.get(k, k), player["_macros"][k]))

        for _as in areas:
            if area_mode == "percent":
                lines.append("a.%s.age=%s" % (_as["tag"], _as["age"]))
            elif area_mode == "percent_str":
                lines.append("a.%s.age=%s" % (str(_as["tag"]), str(_as["age"])))
            else:
                lines.append("a." + str(_as["tag"]) + ".age=" + str(_as["age"]))

        if prefix == "areas_only" or prefix == "through_areas":
            return lines

        _single_reset_room = {}
        for entry in RESETS:
            if entry[0] == "M" and entry[2] == 1:
                _single_reset_room[entry[1]] = entry[3]

        tpl_rooms = {}
        tpl_order = []
        for mob_id in sorted(mobs):
            inst = mobs[mob_id]
            tpl = inst["tpl"]
            if tpl not in tpl_rooms:
                tpl_rooms[tpl] = []
                tpl_order.append(tpl)
            tpl_rooms[tpl].append(inst["room"])
        for tpl_vnum in tpl_order:
            _rooms = tpl_rooms[tpl_vnum]
            if (len(_rooms) == 1
                    and _single_reset_room.get(tpl_vnum) == _rooms[0]):
                continue
            lines.append("m.%s=%s" % (tpl_vnum, "|".join(str(r) for r in _rooms)))
        for rvnum in sorted(rooms):
            rs = rooms[rvnum]
            if not rs["items"]:
                continue
            lines.append("r.%s.items=%s" % (rvnum, "|".join(
                "%s:%s" % (o["vnum"], o["cost"]) for o in rs["items"])))
        return lines

    tr.clear()
    tr.print("save fmt replay")

    player = create_char()
    player["name"] = "Hero"
    player["_macros"] = _MACRO_SUBST
    rooms, mobs = reset_area()
    areas = create_area_states()
    do_outfit(tr, player, "", None)
    tr.print("setup mobs=" + str(len(mobs)) + " rooms=" + str(len(rooms)))
    tr.input("start replay", alpha=False)

    modes = ("percent", "percent_str", "concat")
    prefixes = ("areas_only", "through_areas", "full")
    for mode in modes:
        for prefix in prefixes:
            gc_collect()
            lines = _build(prefix, mode, areas, player, rooms, mobs)
            failed = _try_join(mode + "/" + prefix, lines)
            if failed:
                tr.input("STOP " + mode + "/" + prefix, alpha=False)
        tr.input("mode " + mode, alpha=False)

    # Repeat exact old area-line path after full save-list allocation.
    bad = 0
    for i in range(30):
        gc_collect()
        lines = _build("full", "percent", areas, player, rooms, mobs)
        if _try_join("rep" + str(i), lines):
            bad += 1
            tr.input("STOP rep" + str(i), alpha=False)
    tr.print("repeat bad=" + str(bad))
    tr.input("probe done", alpha=False)
