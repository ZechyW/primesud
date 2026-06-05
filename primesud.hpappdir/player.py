from hpprime import eval as ppleval, keyboard
from cas import get_key
from uio import FileIO

from config import SAVE_FILE, POLL_MS
from world import (
    ROOM_INIT, ITEM_TEMPLATES, MOB_TEMPLATES, MOB_INIT,
    R_VILLAGE_SQUARE,
    SK_UNARMED, SK_SLASH, SK_HEAL, SK_WEAKEN, SK_DODGE,
    STR_APP_TOHIT, STR_APP_TODAM, DEX_APP_DEF, CON_APP_HITP,
)


# ── Player model ──────────────────────────────────────────────────────────────

def create_char():
    return {
        "name":     "",
        "level":    1,  "xp": 0, "xp_next": 100,
        "str":      10, "dex": 10, "int": 10, "wis": 10, "con": 10,
        "hp":       30, "hp_max": 30,
        "mp":       15, "mp_max": 15,
        "hitroll":  0,
        "damroll":  0,
        "AC":       100,   # base unarmored (100 = poor; negative = better)
        "wait":     0,     # skill lag in pulses
        "daze":     0,     # stun in pulses
        "room":     R_VILLAGE_SQUARE,
        "inv":      [],
        "equip": {
            "weapon": None, "offhand": None, "head": None,
            "chest": None, "legs": None, "feet": None, "hands": None,
        },
        "learned": {
            SK_UNARMED: 40,   # basic brawling
            SK_SLASH:   50,
            SK_HEAL:    75,
            SK_WEAKEN:  50,
            SK_DODGE:   10,
        },
        "fighting": None,
    }


def reset_area():
    """Create fresh room state and mob instances (cf. 1stMud reset_area)."""
    room_state = {}
    for vnum, init in ROOM_INIT.items():
        room_state[vnum] = {"items": list(init["items"]), "mobs": list(init["mobs"])}

    mob_instances = {}
    for mob_id, init in MOB_INIT.items():
        tpl = MOB_TEMPLATES[init["tpl"]]
        ps  = tpl["perm_stat"]
        mob_instances[mob_id] = {
            "tpl":        init["tpl"],
            "hp":         tpl["hp_max"],
            "state":      "idle",
            "room":       init["room"],
            "respawn_at": 0,
            "affects":    {},
            "wait":       0,
            "daze":       0,
            # Combat stats flattened from template for hot-path access
            "level":      tpl["level"],
            "str":        ps["str"],
            "dex":        ps["dex"],
            "int":        ps["int"],
            "wis":        ps["wis"],
            "con":        ps["con"],
            "hitroll":    tpl["hitroll"],
            "damroll":    tpl["damroll"],
            "AC":         tpl["AC"],
        }

    return room_state, mob_instances


def _enrich_mob_instance(inst):
    """Fill in template-derived combat stats on a freshly loaded mob instance."""
    tpl = MOB_TEMPLATES[inst["tpl"]]
    ps  = tpl["perm_stat"]
    inst.setdefault("wait",    0)
    inst.setdefault("daze",    0)
    inst.setdefault("affects", {})
    inst["level"]   = tpl["level"]
    inst["str"]     = ps["str"]
    inst["dex"]     = ps["dex"]
    inst["int"]     = ps["int"]
    inst["wis"]     = ps["wis"]
    inst["con"]     = ps["con"]
    inst["hitroll"] = tpl["hitroll"]
    inst["damroll"] = tpl["damroll"]
    inst["AC"]      = tpl["AC"]


# ── Stat application helpers ──────────────────────────────────────────────────

def _clamp_stat(v):
    return min(25, max(0, v))


def get_hitroll(char):
    """Effective hitroll: base + STR bonus + equipped weapon bonus."""
    total = char.get("hitroll", 0) + STR_APP_TOHIT[_clamp_stat(char.get("str", 10))]
    equip = char.get("equip")
    if equip:
        for vnum in equip.values():
            if vnum is not None:
                total += ITEM_TEMPLATES[vnum].get("hitroll", 0)
    return total


def get_damroll(char):
    """Effective damroll: base + STR bonus + equipped weapon bonus."""
    total = char.get("damroll", 0) + STR_APP_TODAM[_clamp_stat(char.get("str", 10))]
    equip = char.get("equip")
    if equip:
        for vnum in equip.values():
            if vnum is not None:
                total += ITEM_TEMPLATES[vnum].get("damroll", 0)
    return total


def get_AC(char):
    """Effective AC: base + DEX bonus + equipped armour bonus."""
    total = char.get("AC", 100) + DEX_APP_DEF[_clamp_stat(char.get("dex", 10))]
    equip = char.get("equip")
    if equip:
        for vnum in equip.values():
            if vnum is not None:
                total += ITEM_TEMPLATES[vnum].get("AC", 0)
    return total


def get_obj_list(fragment, vnum_list, templates):
    frag = fragment.lower()
    for vnum in vnum_list:
        if templates[vnum]["name"].lower() == frag:
            return vnum
    for vnum in vnum_list:
        if templates[vnum]["name"].lower().startswith(frag):
            return vnum
    return None


def get_char_room(fragment, inst_ids, mob_instances):
    frag = fragment.lower()
    for mob_id in inst_ids:
        inst = mob_instances[mob_id]
        name = MOB_TEMPLATES[inst["tpl"]]["name"].lower()
        if name == frag or name.startswith(frag):
            return mob_id
    return None


# ── Display ───────────────────────────────────────────────────────────────────

def show_prompt(tr, player, buf):
    prefix = "HP:{}/{} MP:{}/{} {}tnl>".format(
        player["hp"], player["hp_max"],
        player["mp"], player["mp_max"],
        player["xp_next"] - player["xp"],
    )
    avail = max(1, tr.columns - 6 - len(prefix))
    tr.set_status(prefix + buf[-avail:])


# ── Persistence ───────────────────────────────────────────────────────────────

def save_char(player, room_state, mob_instances):
    lines = []
    for key in ("name", "level", "xp", "xp_next",
                "str", "dex", "int", "wis", "con",
                "hp", "hp_max", "mp", "mp_max",
                "hitroll", "damroll", "AC", "room"):
        lines.append("p.{}={}".format(key, player[key]))
    lines.append("p.inv={}".format("|".join(str(v) for v in player["inv"])))
    for slot, vnum in player["equip"].items():
        lines.append("p.eq.{}={}".format(slot, vnum if vnum is not None else ""))
    learned_parts = []
    for sk, pct in player["learned"].items():
        learned_parts.append("{}:{}".format(sk, pct))
    lines.append("p.learned={}".format("|".join(learned_parts)))
    for rvnum, rs in room_state.items():
        lines.append("r.{}.items={}".format(rvnum, "|".join(str(v) for v in rs["items"])))
    for mob_id, inst in mob_instances.items():
        state = "idle" if inst["state"] == "aggro" else inst["state"]
        lines.append("m.{}=tpl={}|hp={}|state={}|room={}|respawn_at={}".format(
            mob_id, inst["tpl"], inst["hp"], state,
            inst["room"], inst.get("respawn_at", 0)))
    try:
        payload = "\n".join(lines)
        with FileIO(SAVE_FILE, "wb") as f:
            f.write(payload.encode("ascii"))
        return True
    except Exception:
        return False


def load_char(player, room_state, mob_instances):
    try:
        with FileIO(SAVE_FILE, "rb") as f:
            data = f.read().decode("ascii")
    except Exception:
        return False

    int_keys = {"level", "xp", "xp_next",
                "str", "dex", "int", "wis", "con",
                "hp", "hp_max", "mp", "mp_max",
                "hitroll", "damroll", "AC", "room"}

    for rs in room_state.values():
        rs["mobs"] = []

    for line in data.split("\n"):
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        if key.startswith("p.eq."):
            slot = key[5:]
            player["equip"][slot] = int(val) if val else None
        elif key == "p.inv":
            player["inv"] = [int(v) for v in val.split("|") if v]
        elif key == "p.learned":
            for entry in val.split("|"):
                if ":" in entry:
                    sk_str, pct_str = entry.split(":", 1)
                    try:
                        player["learned"][int(sk_str)] = int(pct_str)
                    except ValueError:
                        pass
        elif key.startswith("p."):
            pkey = key[2:]
            player[pkey] = int(val) if pkey in int_keys else val
        elif key.startswith("r.") and key.endswith(".items"):
            rvnum = int(key.split(".")[1])
            room_state[rvnum]["items"] = [int(v) for v in val.split("|") if v]
        elif key.startswith("m."):
            mob_id = int(key.split(".")[1])
            fields = {"tpl": 0, "hp": 0, "state": "idle",
                      "room": 0, "respawn_at": 0}
            for pair in val.split("|"):
                if "=" in pair:
                    fk, fv = pair.split("=", 1)
                    fields[fk] = int(fv) if fk != "state" else fv
            _enrich_mob_instance(fields)
            mob_instances[mob_id] = fields
            if fields["state"] != "dead":
                room_state[fields["room"]]["mobs"].append(mob_id)

    return True


# ── Input utilities ───────────────────────────────────────────────────────────

def _poll_char(tr, key_commands=None):
    """Non-blocking: return the next char if a new key was pressed, else None."""
    cur = keyboard()
    changed = cur ^ tr.last_keyboard_state
    if not changed:
        return None
    tr.last_keyboard_state = cur
    for bit in range(52):
        mask = 1 << bit
        if not (changed & mask):
            continue
        if cur & mask:  # key pressed
            get_key()
            if bit == 36:  # Alpha
                tr.alpha_hold = True
                if tr.alpha_lock:
                    if tr.is_shift:
                        tr.shift_lock = not tr.shift_lock
                    else:
                        tr.alpha_lock = tr.is_alpha = False
                        tr.shift_lock = False
                    tr.is_shift = False
                elif tr.is_alpha:
                    if tr.is_shift:
                        if tr.alpha_lock:
                            tr.shift_lock = not tr.shift_lock
                        else:
                            tr.alpha_lock = True
                        tr.is_shift = False
                    else:
                        tr.alpha_lock = True
                else:
                    tr.is_alpha = True
                tr._refresh_indicators()
            elif bit == 41:  # Shift
                tr.shift_hold = True
                if tr.is_shift:
                    tr.is_shift = tr.shift_lock if not tr.is_shift else False
                else:
                    tr.is_shift = True
                tr._refresh_indicators()
            elif bit == 1:  # Symb
                tr.symb_hold = True
                tr.symb_index = 0
            else:
                if key_commands and bit in key_commands:
                    return key_commands[bit]
                if tr.shift_hold:
                    tr.is_shift = True
                if tr.alpha_hold:
                    tr.is_alpha = True
                mod_idx = ((tr.is_shift ^ tr.shift_lock) << 1) | (tr.is_alpha | tr.alpha_lock)
                char = tr.key_map.get(bit, [None, None, None, None])[mod_idx]
                if not tr.alpha_lock:
                    tr.is_alpha = False
                if tr.is_shift and not tr.symb_hold:
                    tr.is_shift = False
                tr._refresh_indicators()
                return char
        else:  # key released
            if bit == 36:
                tr.alpha_hold = False
                tr._refresh_indicators()
            elif bit == 41:
                tr.shift_hold = False
                tr._refresh_indicators()
            elif bit == 1:
                tr.symb_hold = False
                tr._refresh_indicators()
    return None


def _resync_keyboard(tr):
    """Reset tr keyboard state after a blocking input section."""
    tr.last_keyboard_state = keyboard()
    tr.is_alpha = tr.is_shift = tr.alpha_hold = tr.shift_hold = tr.symb_hold = False
    tr._refresh_indicators()
