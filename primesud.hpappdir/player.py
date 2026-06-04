import math
from hpprime import eval as ppleval, keyboard
from cas import get_key
from uio import FileIO

from config import SAVE_FILE, POLL_MS
from world import (
    ROOM_INIT, ITEM_TEMPLATES, MOB_TEMPLATES, MOB_INIT,
    R_VILLAGE_SQUARE, SK_ATTACK, SK_HEAL,
)


# ── Player model ──────────────────────────────────────────────────────────────

def player_stat(player, stat):
    base = player.get(stat, 0)
    for item_vnum in player["equip"].values():
        if item_vnum is not None:
            base += ITEM_TEMPLATES[item_vnum].get("stats", {}).get(stat, 0)
    return base


def resolve_name(fragment, vnum_list, templates):
    frag = fragment.lower()
    for vnum in vnum_list:
        if templates[vnum]["name"].lower() == frag:
            return vnum
    for vnum in vnum_list:
        if templates[vnum]["name"].lower().startswith(frag):
            return vnum
    return None


def resolve_mob_name(fragment, inst_ids, mob_instances):
    frag = fragment.lower()
    for mob_id in inst_ids:
        inst = mob_instances[mob_id]
        name = MOB_TEMPLATES[inst["tpl"]]["name"].lower()
        if name == frag or name.startswith(frag):
            return mob_id
    return None


def make_player():
    return {
        "name": "",
        "level": 1, "xp": 0, "xp_next": 100,
        "str": 10, "dex": 10, "int": 10, "con": 10,
        "hp": 30, "hp_max": 30, "mp": 15, "mp_max": 15,
        "room": R_VILLAGE_SQUARE,
        "inv": [],
        "equip": {
            "weapon": None, "offhand": None, "head": None,
            "chest": None, "legs": None, "feet": None, "hands": None,
        },
        "skills": [SK_ATTACK, SK_HEAL],
    }


def make_room_state():
    state = {}
    for vnum, init in ROOM_INIT.items():
        state[vnum] = {"items": list(init["items"]), "mobs": list(init["mobs"])}
    return state


def make_mob_instances():
    instances = {}
    for mob_id, init in MOB_INIT.items():
        instances[mob_id] = dict(init)
    return instances


# ── Display ───────────────────────────────────────────────────────────────────

def show_status(tr, player):
    tr.set_status("HP:{}/{} MP:{}/{} L:{}".format(
        player["hp"], player["hp_max"],
        player["mp"], player["mp_max"],
        player["level"],
    ))


def show_prompt(tr, player, buf):
    prefix = "HP:{}/{} MP:{}/{} L:{}>".format(
        player["hp"], player["hp_max"],
        player["mp"], player["mp_max"],
        player["level"],
    )
    avail = max(1, tr.columns - 6 - len(prefix))
    tr.set_status(prefix + buf[-avail:])


# ── Persistence ───────────────────────────────────────────────────────────────

def save_game(player, room_state, mob_instances):
    lines = []
    for key in ("name", "level", "xp", "xp_next", "str", "dex", "int", "con",
                "hp", "hp_max", "mp", "mp_max", "room"):
        lines.append("p.{}={}".format(key, player[key]))
    lines.append("p.inv={}".format("|".join(str(v) for v in player["inv"])))
    lines.append("p.skills={}".format("|".join(str(v) for v in player["skills"])))
    for slot, vnum in player["equip"].items():
        lines.append("p.eq.{}={}".format(slot, vnum if vnum is not None else ""))
    for rvnum, rs in room_state.items():
        lines.append("r.{}.items={}".format(rvnum, "|".join(str(v) for v in rs["items"])))
    for mob_id, inst in mob_instances.items():
        lines.append("m.{}=tpl={}|hp={}|state={}|room={}|respawn_at={}".format(
            mob_id, inst["tpl"], inst["hp"], inst["state"],
            inst["room"], inst.get("respawn_at", 0)))
    try:
        payload = "\n".join(lines)
        with FileIO(SAVE_FILE, "wb") as f:
            f.write(payload.encode("ascii"))
        return True
    except Exception:
        return False


def load_game(player, room_state, mob_instances):
    try:
        with FileIO(SAVE_FILE, "rb") as f:
            data = f.read().decode("ascii")
    except Exception:
        return False

    int_keys = {"level", "xp", "xp_next", "str", "dex", "int", "con",
                "hp", "hp_max", "mp", "mp_max", "room"}

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
        elif key == "p.skills":
            player["skills"] = [int(v) for v in val.split("|") if v]
        elif key.startswith("p."):
            pkey = key[2:]
            player[pkey] = int(val) if pkey in int_keys else val
        elif key.startswith("r.") and key.endswith(".items"):
            rvnum = int(key.split(".")[1])
            room_state[rvnum]["items"] = [int(v) for v in val.split("|") if v]
        elif key.startswith("m."):
            parts_key = key.split(".")
            mob_id = int(parts_key[1])
            fields = {"tpl": 0, "hp": 0, "state": "idle", "room": 0, "respawn_at": 0}
            for pair in val.split("|"):
                if "=" in pair:
                    fk, fv = pair.split("=", 1)
                    fields[fk] = int(fv) if fk != "state" else fv
            mob_instances[mob_id] = fields
            if fields["state"] != "dead":
                room_state[fields["room"]]["mobs"].append(mob_id)

    return True


# ── Input utilities ───────────────────────────────────────────────────────────

def _pressed_keys():
    state = keyboard()
    keys = set()
    while state:
        n = state & (-state)
        keys.add(round(math.log2(n)))
        state &= state - 1
    return keys


def _wait_digit(max_val):
    """Block until a digit key 1..max_val is pressed. Returns the int."""
    # Digit bit indices from tml._default_key_map:
    # 1=42, 2=43, 3=44, 4=37, 5=38, 6=39, 7=32, 8=33, 9=34
    DIGIT_KEYS = {42: 1, 43: 2, 44: 3, 37: 4, 38: 5, 39: 6, 32: 7, 33: 8, 34: 9}
    last = _pressed_keys()
    while True:
        cur = _pressed_keys()
        new = cur - last
        last = cur
        for bit in new:
            digit = DIGIT_KEYS.get(bit)
            if digit is not None and 1 <= digit <= max_val:
                return digit
        ppleval("WAIT({}/1e3)".format(POLL_MS))


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
    """Reset tr keyboard state after a blocking input section (e.g. run_title)."""
    tr.last_keyboard_state = keyboard()
    tr.is_alpha = tr.is_shift = tr.alpha_hold = tr.shift_hold = tr.symb_hold = False
    tr._refresh_indicators()
