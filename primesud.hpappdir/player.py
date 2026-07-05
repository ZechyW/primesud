"""Player creation, progression, and prompt."""

from classes import CLASS_TABLE, CLASS_WARRIOR, exp_per_level
from colors import color_len
import terminal
from terminal import tprint
from config import TERMINAL_COLS
from config import R_STARTING_ROOM
from skills_table import SKILLS, GSN_RECALL
from races import RACE_TABLE
import world
from world import ROOM_DEFS, AREA_DEFS

_EQUIP_SAVE_ORDER = (
    "light", "finger_l", "finger_r", "neck_1", "neck_2", "body", "head",
    "legs", "feet", "hands", "arms", "shield", "about", "waist", "wrist_l",
    "wrist_r", "wield", "hold", "float", "secondary",
)

# Player flag bits live in handler.py (import-cycle: player -> handler);
# re-exported here so callers can import from either module.
from handler import (PLR_AUTOMAP, PLR_AUTOASSIST, PLR_AUTOEXIT, PLR_AUTOLOOT,
                     PLR_AUTOSAC, PLR_AUTOGOLD, PLR_AUTOSPLIT, PLR_AUTODAMAGE,
                     PLR_DEFAULTS)

# -- Player model --------------------------------------------------------------


def create_char(class_idx=CLASS_WARRIOR):
    """Return fresh player state dict with default starting values.

    Overlays player-only (pcdata) fields onto _char_base()
    (cf. 1stMud new_char + new_pcdata in recycle.c; char_data in structs.h:560).
    Also derives form_flags/part_flags from RACE_TABLE (cf. 1stMud
    nanny.c:533-534 `ch->form = race->form; ch->parts = race->parts;`),
    so PC deaths hit the same body-part-drop logic as mobs (combat.py
    _death_cry).

    Args:
        class_idx (int): Starting class index into CLASS_TABLE. Default only
            matters for the load path, where the save overwrites it.

    Returns:
        dict: Player state dict.
    """
    ch = _char_base()
    ch.update({
        # [PRIMESUD] Start new players with more max hp than 1stMud's 20:
        # stances are forced from the start, which lowers damage output at
        # low mastery, and mud school is a tutorial. Flat offset only --
        # advance_level/do_train add absolutely and remort resets to 100*b.
        "hit":      50,   "max_hit":  50,   "perm_hit":  50,
        "mana":     100,  "max_mana": 100,  "perm_mana": 100,
        "move":     100,  "max_move": 100,  "perm_move": 100,
        "room":     R_STARTING_ROOM,
        "id":       1,
        # cf. 1stMud nanny.c CON_READ_MOTD level==0 block: ch->gold = 10
        # (base is 0 -- see _char_base).
        "gold":     10,
        # cf. 1stMud ch->Class[] array in multiclass.c; grows on remort.
        "classes":     [class_idx],
        "prime_class": 0,  # slot index into classes (cf. pcdata->prime_class)
        # pcdata fields (cf. 1stMud PcData in structs.h):
        "practice": 5,
        "train":    3,
        "trivia":   0,
        # cf. 1stMud pcdata->quest (QuestData); vnum-based, see quest.py
        "quest_points": 0,
        "quest_status": 0,
        "quest_time":   0,
        "quest_mob":    0,
        "quest_obj":    0,
        "quest_room":   0,
        "quest_giver":  0,
        "quest_mob_name":  "",
        "quest_room_name": "",
        "quest_area_name": "",
        "flags":    PLR_DEFAULTS,  # PLR_* bits; [DEVIATION] separate from act_flags
        "played":   0,
        # cf. 1stMud pcdata->group_known; filled by gn_add below.
        "groups":  [],
        # cf. 1stMud nanny default path: "rom basics" + class basics +
        # class default groups, recall 50. The weapon pick's Max(40, learned)
        # floor (nanny.c HANDLE_CON_PICK_WEAPON) is applied by game_state.py
        # new_game, not here -- it needs the player's choice of weapon, and
        # this function has no interactive path. Other skills cost trains at
        # a gain trainer (do_gain). Customization/creation points not ported
        # (see groups.py). (Racial skills: none for Human; revisit when race
        # selection is ported.)
        "learned": {},
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
    # cf. 1stMud nanny.c CON_READ_MOTD level==0 block:
    # ch->perm_stat[class_table[prime_class(ch)].attr_prime] += 3 -- applied
    # once for brand-new characters only. Safe on the load path too: game_state
    # load_world's "p.str"/"p.dex"/etc. save lines overwrite perm_stat
    # wholesale after create_char() runs, so this +3 is never double-applied
    # or left stale for a loaded character.
    ch["perm_stat"][CLASS_TABLE[class_idx]["attr_prime"]] += 3
    # [PRIMESUD] Start out of stance with no autostance (1stMud zeroed
    # stance[] leaves new chars silently in the normal stance). First combat
    # then triggers the one-time stance pick in autodrop() -- surfaces the
    # stance system to new players.
    from stances import STANCE_CURRENT, STANCE_AUTODROP, STANCE_NONE
    ch["stance"][STANCE_CURRENT] = STANCE_NONE
    ch["stance"][STANCE_AUTODROP] = STANCE_NONE
    # cf. 1stMud nanny.c CON_ROLL_STATS 'y' + add_default_groups ('N' path)
    group_add_basics_and_defaults(ch)
    ch["learned"][GSN_RECALL] = 50  # cf. nanny.c: learned[gsn_recall] = 50
    # cf. 1stMud exp_per_level in skills.c (race class_mult scaling)
    ch["xp_next"] = exp_per_level(ch)
    # cf. 1stMud nanny.c:533-534 / save.c:723-724: ch->form = race->form;
    # ch->parts = race->parts -- derived from race, not persisted. Only
    # "Human" is currently selectable (no race chargen prompt yet), but this
    # keeps the load path correct too: game_state.load_game() calls
    # create_char() before load_world(), and load_world has no
    # p.form_flags/p.part_flags save key, so whatever create_char sets here
    # survives the load overlay untouched -- matching 1stMud's
    # re-derive-from-race-on-load behaviour.
    _race = RACE_TABLE.get(ch["race"], RACE_TABLE["Human"])
    ch["form_flags"] = dict(_race.get("form", {}))
    ch["part_flags"] = dict(_race.get("parts", {}))
    return ch


def group_add_basics_and_defaults(ch):
    """Grant "rom basics" + base + default groups for all held classes
    (cf. 1stMud nanny.c creation/remort grants). [PRIMESUD] helper."""
    from groups import add_base_groups, add_default_groups, gn_add, group_lookup
    gn_add(ch, group_lookup("rom basics"))
    add_base_groups(ch)
    add_default_groups(ch)




from handler import (get_curr_stat, affect_remove, affect_modify, _char_base,
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
        armor = _item_armor_runtime(tpl, obj)
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

    pos = player.get("pos", "standing")

    # HP (cf. 1stMud hit_gain in update.c)
    hp_gain = max(3, con - 3 + level // 2) + (player["max_hit"] - 10)
    # TODO: fast_healing bonus -- if roll < skill%, gain += roll * gain / 100
    # Position divisors: sleeping /1, resting /2, fighting /6, other /4
    if pos == "resting":
        hp_gain //= 2
    elif pos == "fighting":
        hp_gain //= 6
    elif pos != "sleeping":
        hp_gain //= 4
    # Hunger/thirst omitted [PRIMESUD]
    hp_gain = hp_gain * room.get("heal_rate", 100) // 100
    # TODO: poison /4, plague /8, haste/slow /2
    hp_gain = max(1, hp_gain)

    # MP (cf. 1stMud mana_gain in update.c) -- base (WIS+INT+level)/2, same divisors
    mp_gain = (int_ + wis + level) // 2
    if pos == "resting":
        mp_gain //= 2
    elif pos == "fighting":
        mp_gain //= 6
    elif pos != "sleeping":
        mp_gain //= 4
    mp_gain = mp_gain * room.get("mana_rate", 100) // 100
    # TODO: poison /4, plague /8, haste/slow /2
    mp_gain = max(1, mp_gain)

    # MV (cf. 1stMud move_gain in update.c) -- base max(15, level);
    # sleeping +DEX, resting +DEX/2
    dex = get_curr_stat(player, "dex")
    mv_gain = max(15, level)
    if pos == "sleeping":
        mv_gain += dex
    elif pos == "resting":
        mv_gain += dex // 2
    mv_gain = mv_gain * room.get("heal_rate", 100) // 100
    # TODO: poison /4, plague /8, haste/slow /2
    mv_gain = max(1, mv_gain)

    player["hit"] = min(player["max_hit"], player["hit"] + hp_gain)
    player["mana"] = min(player["max_mana"], player["mana"] + mp_gain)
    player["move"] = min(player["max_move"], player["move"] + mv_gain)

    _tick_affects(player, tr)

    # Mob affects tick too (cf. 1stMud char_update iterating char_first;
    # wear-off messages are char-directed, so silent for mobs)
    import world as _world
    for _inst in list(_world.chars.values()):
        if _inst.get("is_npc") and _inst.get("affect_list"):
            _tick_affects(_inst, None)


def _tick_affects(ch, tr):
    """Decrement affect durations, remove expired (cf. 1stMud char_update affect loop in update.c).

    Args:
        ch (dict): Character (player or mob instance).
        tr: Terminal for wear-off messages, or None to tick silently (mobs).
    """
    for aff in list(ch.get("affect_list", [])):
        if aff["duration"] > 0:
            aff["duration"] -= 1
        elif aff["duration"] == 0:
            if tr is not None:
                msg = SKILLS.get(aff.get("type"), {}).get("msg_off", "")
                if msg and not msg.startswith("!"):
                    tr.print(msg)
            affect_remove(ch, aff)


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
    terminal.tr.set_status(prefix + buf[-avail:])
