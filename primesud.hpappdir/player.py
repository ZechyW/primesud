"""Player creation, progression, and prompt."""

from colors import color_len
from terminal import tprint, tr
from config import TERMINAL_COLS
from config import R_STARTING_ROOM, MAX_MORTAL_LEVEL
from skills_table import SKILL_TABLE, SKILLS, GSN_SWORD, GSN_RECALL
import world
from world import ROOM_DEFS, AREA_DEFS

_EQUIP_SAVE_ORDER = (
    "light", "finger_l", "finger_r", "neck_1", "neck_2", "body", "head",
    "legs", "feet", "hands", "arms", "shield", "about", "waist", "wrist_l",
    "wrist_r", "wield", "hold", "float", "secondary",
)

# -- Player flag bits (cf. 1stMud PLR_* in bits.h) -----------------------------
PLR_AUTOMAP = 1
PLR_AUTOLOOT = 16    # BIT_E
PLR_AUTOSAC = 32     # BIT_F
PLR_AUTOGOLD = 64    # BIT_G
PLR_AUTOSPLIT = 128  # BIT_H
PLR_DEFAULTS = PLR_AUTOMAP | PLR_AUTOLOOT | PLR_AUTOSAC | PLR_AUTOGOLD | PLR_AUTOSPLIT

# -- Player model --------------------------------------------------------------


def create_char():
    """Return fresh player state dict with default starting values.

    Overlays player-only (pcdata) fields onto _char_base()
    (cf. 1stMud new_char + new_pcdata in recycle.c; char_data in structs.h:560).

    Returns:
        dict: Player state dict.
    """
    ch = _char_base()
    ch.update({
        "hit":      20,   "max_hit":  20,   "perm_hit":  20,
        "mana":     100,  "max_mana": 100,  "perm_mana": 100,
        "move":     100,  "max_move": 100,  "perm_move": 100,
        "room":     R_STARTING_ROOM,
        "id":       1,
        # pcdata fields (cf. 1stMud PcData in structs.h):
        "xp_next":  1000,
        "practice": 5,
        "train":    3,
        "trivia":   0,
        "flags":    PLR_DEFAULTS,  # PLR_* bits; [DEVIATION] separate from act_flags
        "played":   0,
        # [PRIMESUD] Classless: grant all learnable skills at 1% from creation.
        # Level-gated via can_use_skill_spell; practice list filters by level.
        # Sword=40 mirrors nanny.c weapon choice; recall=50 explicit in nanny.c.
        "learned": {
            sn: (40 if sn == GSN_SWORD else 50 if sn == GSN_RECALL else 1)
            for sn, data in SKILL_TABLE
            if data["skill_level"] <= MAX_MORTAL_LEVEL
        },
        "equip": {
            "light":     None, "finger_l":  None, "finger_r":  None,
            "neck_1":    None, "neck_2":    None, "body":      None,
            "head":      None, "legs":      None, "feet":      None,
            "hands":     None, "arms":      None, "shield":    None,
            "about":     None, "waist":     None, "wrist_l":   None,
            "wrist_r":   None, "wield":     None, "hold":      None,
            "float":     None, "secondary": None,
        },
    })
    return ch




from actor import (get_curr_stat, affect_remove, affect_modify, _char_base,
                   _apply_item_modifiers, _item_armor_runtime)
from world import ITEM_DEFS


def reset_char(player):
    """Strip and reapply all equipment and spell affect bonuses (cf. 1stMud reset_char in handler.c).

    Zeroes mod_stat, resets max_hit/mana/move to perm baselines, clears
    armor/hitroll/damroll/saving_throw, then re-applies equipment (with
    enchanted check via _apply_item_modifiers) and character spell affects.

    [PRIMESUD] Omits perm-recovery block (no legacy saves to migrate).
    [PRIMESUD] Omits last_level (XP penalty not ported).
    [PRIMESUD] Omits sex handling (hardcoded neutral until character customisation ported).

    Args:
        player (dict): Player state dict.
    """
    # -- Reset to baselines (cf. 1stMud handler.c lines 512-528)
    for k in player.get("mod_stat", {}):
        player["mod_stat"][k] = 0
    player["max_hit"] = player["perm_hit"]
    player["max_mana"] = player["perm_mana"]
    player["max_move"] = player["perm_move"]
    player["armor"] = (100, 100, 100, 100)
    player["hitroll"] = 0
    player["damroll"] = 0
    player["saving_throw"] = 0

    # -- Re-apply equipment (cf. 1stMud handler.c lines 530-668)
    for slot in _EQUIP_SAVE_ORDER:
        obj = player["equip"].get(slot)
        if obj is None:
            continue
        tpl = ITEM_DEFS.get(obj["vnum"])
        if tpl is None:
            continue
        armor = _item_armor_runtime(tpl)
        if armor is not None:
            a = player["armor"]
            player["armor"] = (a[0]-armor[0], a[1]-armor[1], a[2]-armor[2], a[3]-armor[3])
        _apply_item_modifiers(player, obj, tpl, True)

    # -- Re-apply character spell affects (cf. 1stMud handler.c lines 671-734)
    for af in player.get("affect_list", []):
        affect_modify(player, af, True)


# -- Tick regen ---------------------------------------------------------------

def tick_update(tr, player, room):
    """Regenerate HP and MP once per world tick (cf. 1stMud hit_gain/mana_gain in update.c).

    Position is always treated as resting -- no position system [PRIMESUD].
    Hunger/thirst conditions omitted [PRIMESUD].

    Args:
        tr: Terminal for affect wear-off messages.
        player (dict): Player state dict.
        room (dict): Current room (supplies heal_rate/mana_rate).

    Uses imported world module for player stat lookups.
    """
    con  = get_curr_stat(player, "con")
    int_ = get_curr_stat(player, "int")
    wis  = get_curr_stat(player, "wis")
    level = player.get("level", 1)

    # HP (cf. 1stMud hit_gain in update.c)
    hp_gain = max(3, con - 3 + level // 2) + (player["max_hit"] - 10)
    # TODO: fast_healing bonus -- if roll < skill%, gain += roll * gain / 100
    # Position: always resting [PRIMESUD] -- sleeping=/1, resting=/2, standing=/4, fighting=/6
    hp_gain //= 2
    # Hunger/thirst omitted [PRIMESUD]
    hp_gain = hp_gain * room.get("heal_rate", 100) // 100
    # TODO: poison /4, plague /8, haste/slow /2
    hp_gain = max(1, hp_gain)

    # MP (cf. 1stMud mana_gain in update.c) -- base (WIS+INT+level)/2, resting /2
    mp_gain = (int_ + wis + level) // 4
    mp_gain = mp_gain * room.get("mana_rate", 100) // 100
    # TODO: poison /4, plague /8, haste/slow /2
    mp_gain = max(1, mp_gain)

    # MV (cf. 1stMud move_gain in update.c) -- base max(15, level), resting +DEX/2
    dex = get_curr_stat(player, "dex")
    mv_gain = max(15, level) + dex // 2
    mv_gain = mv_gain * room.get("heal_rate", 100) // 100
    # TODO: poison /4, plague /8, haste/slow /2
    mv_gain = max(1, mv_gain)

    player["hit"] = min(player["max_hit"], player["hit"] + hp_gain)
    player["mana"] = min(player["max_mana"], player["mana"] + mp_gain)
    player["move"] = min(player["max_move"], player["move"] + mv_gain)

    for aff in list(player.get("affect_list", [])):
        if aff["duration"] > 0:
            aff["duration"] -= 1
        elif aff["duration"] == 0:
            msg = SKILLS.get(aff.get("type"), {}).get("msg_off", "")
            if msg and not msg.startswith("!"):
                tr.print(msg)
            affect_remove(player, aff)


# -- Display -------------------------------------------------------------------

def show_prompt(player, buf):
    """Update the terminal status bar with the current HP/MP/XP prompt.

    Args:
        player (dict): Player state dict.
        buf (str): Current input buffer shown on the right of the prompt.
    """
    prefix = "{R%d/%dhp {M%d/%dmn {B%d/%dmv{x %dtnl>" % (
        player["hit"], player["max_hit"],
        player["mana"], player["max_mana"],
        player["move"], player["max_move"],
        player["xp_next"] - player["xp"],
    )
    avail = max(1, TERMINAL_COLS - 6 - color_len(prefix))
    tr.set_status(prefix + buf[-avail:])
