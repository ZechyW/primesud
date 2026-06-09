from hpprime import eval as ppleval, keyboard
from cas import get_key
from urandom import randint

from config import SAVE_VAR, POLL_MS, TERMINAL_COLS
from world import (
    ROOM_INIT, ITEM_TEMPLATES, MOB_TEMPLATES, MOB_INIT,
    R_VILLAGE_SQUARE,
    GSN_HAND_TO_HAND, GSN_KICK, GSN_CURE_LIGHT, GSN_PARRY,
    STR_APP_TOHIT, STR_APP_TODAM, DEX_APP_DEF, CON_APP_HITP, WIS_APP_PRACTICE,
)


# ── Player flag bits (cf. 1stMud PLR_* in bits.h) ─────────────────────────────
PLR_AUTOMAP  = 1
PLR_DEFAULTS = PLR_AUTOMAP

# ── Player model ──────────────────────────────────────────────────────────────

def _roll_hp(hp_dice):
    num, size, bonus = hp_dice
    total = bonus
    for _ in range(num):
        total += randint(1, size)
    return max(1, total)


def create_char():
    return {
        "name":     "",
        "is_npc":   False,
        "level":    1,  "xp": 0, "xp_next": 1000,
        "str":      13, "dex": 13, "int": 13, "wis": 13, "con": 13,
        "hp":       20, "hp_max": 20,
        "mp":       100, "mp_max": 100,
        "practice": 5,  "train": 3,
        "hitroll":  0,
        "damroll":  0,
        "AC":       100,   # base unarmored (100 = poor; negative = better)
        "wait":     0,     # skill lag in pulses
        "daze":     0,     # stun in pulses
        "affects":  {},
        "room":     R_VILLAGE_SQUARE,
        "inv":      [],
        "equip": {
            "weapon": None, "offhand": None, "head": None,
            "chest": None, "legs": None, "feet": None, "hands": None,
        },
        "learned": {
            GSN_HAND_TO_HAND: 40,
            GSN_KICK:         50,
            GSN_CURE_LIGHT:   75,
            GSN_PARRY:        10,
        },
        "fighting": None,
        "flags":    PLR_DEFAULTS,
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
        _hp = _roll_hp(tpl["hp_dice"])
        mob_instances[mob_id] = {
            "tpl":        init["tpl"],
            "is_npc":     True,
            "name":       tpl["name"],
            "hp":         _hp,
            "hp_max":     _hp,
            "state":      "idle",
            "room":       init["room"],
            "respawn_at": 0,
            "affects":    {},
            "wait":       0,
            "daze":       0,
            "fighting":   None,
            "learned":    dict(tpl.get("skills", {})),
            "off_flags":  dict(tpl.get("off_flags", {})),
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
    inst.setdefault("wait",     0)
    inst.setdefault("daze",     0)
    inst.setdefault("affects",  {})
    inst.setdefault("fighting", None)
    inst["is_npc"]   = True
    inst["name"]     = tpl["name"]
    inst["learned"]  = dict(tpl.get("skills", {}))
    inst["off_flags"] = dict(tpl.get("off_flags", {}))
    inst["level"]    = tpl["level"]
    inst["str"]      = ps["str"]
    inst["dex"]      = ps["dex"]
    inst["int"]      = ps["int"]
    inst["wis"]      = ps["wis"]
    inst["con"]      = ps["con"]
    inst["hitroll"]  = tpl["hitroll"]
    inst["damroll"]  = tpl["damroll"]
    inst["AC"]       = tpl["AC"]
    if inst.get("hp_max", 0) == 0:
        inst["hp_max"] = inst["hp"]


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
    avail = max(1, TERMINAL_COLS - 6 - len(prefix))
    tr.set_status(prefix + buf[-avail:])


# ── Persistence ───────────────────────────────────────────────────────────────
# Save data is stored in a PPL home variable (SAVE_VAR) via HVars so it
# survives app reinstalls.  Serialisation constraints:
#   - Lines are joined with '~'; no saved field value may contain '~'.
#   - No field value may contain '"' (would break the PPL string literal).
#   - HVars returns the string "Error: Invalid input" when the variable does
#     not exist yet (i.e. no save found); load_char treats this as no-save.

def save_char(player, room_state, mob_instances, macros=None):
    lines = []
    for key in ("name", "level", "xp", "xp_next",
                "str", "dex", "int", "wis", "con",
                "hp", "hp_max", "mp", "mp_max",
                "hitroll", "damroll", "AC", "room",
                "practice", "train", "flags"):
        lines.append("p.{}={}".format(key, player[key]))
    lines.append("p.inv={}".format("|".join(str(v) for v in player["inv"])))
    for slot, vnum in player["equip"].items():
        lines.append("p.eq.{}={}".format(slot, vnum if vnum is not None else ""))
    learned_parts = []
    for sk, pct in player["learned"].items():
        learned_parts.append("{}:{}".format(sk, pct))
    lines.append("p.learned={}".format("|".join(learned_parts)))
    if macros is not None:
        for k, v in macros.items():
            lines.append("p.macro.{}={}".format(k, v))
    for rvnum, rs in room_state.items():
        lines.append("r.{}.items={}".format(rvnum, "|".join(str(v) for v in rs["items"])))
    for mob_id, inst in mob_instances.items():
        state = "idle" if inst["state"] == "aggro" else inst["state"]
        lines.append("m.{}=tpl={}|hp={}|hp_max={}|state={}|room={}|respawn_at={}".format(
            mob_id, inst["tpl"], inst["hp"], inst.get("hp_max", inst["hp"]), state,
            inst["room"], inst.get("respawn_at", 0)))
    try:
        payload = "~".join(lines)
        ppleval('HVars("' + SAVE_VAR + '"):="' + payload + '"')
        return True
    except Exception:
        return False


def load_char(player, room_state, mob_instances, macros=None):
    try:
        data = ppleval('HVars("' + SAVE_VAR + '")')
        if not data or not isinstance(data, str) or data.startswith("Error:"):
            return False
    except Exception:
        return False

    int_keys = {"level", "xp", "xp_next",
                "str", "dex", "int", "wis", "con",
                "hp", "hp_max", "mp", "mp_max",
                "hitroll", "damroll", "AC", "room",
                "practice", "train", "flags"}

    if macros is not None:
        macros.clear()

    for rs in room_state.values():
        rs["mobs"] = []

    for line in data.split("~"):
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
        elif key.startswith("p.macro.") and macros is not None:
            macros[key[8:]] = val
        elif key.startswith("p."):
            pkey = key[2:]
            player[pkey] = int(val) if pkey in int_keys else val
        elif key.startswith("r.") and key.endswith(".items"):
            rvnum = int(key.split(".")[1])
            room_state[rvnum]["items"] = [int(v) for v in val.split("|") if v]
        elif key.startswith("m."):
            mob_id = int(key.split(".")[1])
            fields = {"tpl": 0, "hp": 0, "hp_max": 0, "state": "idle",
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
            else:
                if key_commands and bit in key_commands:
                    cmd, auto_submit = key_commands[bit]
                    return (cmd, auto_submit)
                if tr.shift_hold:
                    tr.is_shift = True
                if tr.alpha_hold:
                    tr.is_alpha = True
                mod_idx = ((tr.is_shift ^ tr.shift_lock) << 1) | (tr.is_alpha | tr.alpha_lock)
                char = tr.key_map.get(bit, [None, None, None, None])[mod_idx]
                if not tr.alpha_lock:
                    tr.is_alpha = False
                if tr.is_shift:
                    tr.is_shift = False
                tr._refresh_indicators()
                return (char, None)
        else:  # key released
            if bit == 36:
                tr.alpha_hold = False
                tr._refresh_indicators()
            elif bit == 41:
                tr.shift_hold = False
                tr._refresh_indicators()
    return None


def _resync_keyboard(tr):
    """Reset tr keyboard state after a blocking input section."""
    tr.last_keyboard_state = keyboard()
    tr.is_alpha = tr.is_shift = tr.alpha_hold = tr.shift_hold = tr.symb_hold = False
    tr._refresh_indicators()
