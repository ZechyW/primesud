"""Player creation, progression, and prompt."""

from classes import CLASS_TABLE, CLASS_WARRIOR, exp_per_level, has_spells, class_name
from colors import color_len
import terminal
from terminal import tprint
from config import TERMINAL_COLS
from config import R_STARTING_ROOM
from config import POS_ORDER
from config import DAM_DISEASE, DAM_NONE, DAM_POISON, TYPE_UNDEFINED
from groups import add_base_groups, add_default_groups, gn_add, group_lookup
from skill_utils import check_improve, get_skill
from stances import STANCE_CURRENT, STANCE_AUTODROP, STANCE_NONE
from skills_table import (SKILLS, GSN_RECALL, GSN_FAST_HEALING, GSN_MEDITATION,
                         GSN_PLAGUE, GSN_POISON)
from urandom import randint
from races import RACE_TABLE, race_lookup
import world
from world import ROOM_DEFS, AREA_DEFS, ITEM_DEFS

_EQUIP_SAVE_ORDER = (
    "light", "finger_l", "finger_r", "neck_1", "neck_2", "body", "head",
    "legs", "feet", "hands", "arms", "shield", "about", "waist", "wrist_l",
    "wrist_r", "wield", "hold", "float", "secondary",
)

# Player flag bits live in handler.py (import-cycle: player -> handler);
# re-exported here so callers can import from either module.
from handler import (PLR_AUTOMAP, PLR_AUTOSKILL, PLR_AUTOASSIST, PLR_AUTOEXIT,
                     PLR_AUTOLOOT, PLR_AUTOSAC, PLR_AUTOGOLD, PLR_AUTOSPLIT,
                     PLR_AUTODAMAGE, PLR_DEFAULTS,
                     COMM_BRIEF, COMM_COMPACT, COMM_SHOW_AFFECTS)

# -- Player model --------------------------------------------------------------


def set_title(ch, title):
    """Set the player's score title (cf. 1stMud set_title in act_info.c).

    Prepends a leading space unless *title* already starts with sentence-final
    punctuation (matching 1stMud so the stored title concatenates directly
    onto the player's name for display, cf. do_score's name+title header).

    Args:
        ch (dict): Player state dict.
        title (str): New title text (already length-capped by the caller).
    """
    if title[:1] not in (".", ",", "!", "?"):
        title = " " + title
    ch["title"] = title


def create_char(class_idx=CLASS_WARRIOR, race_name="Human"):
    """Create a new player character with the given class and race
    (cf. 1stMud nanny.c chargen path).

    Overlays player-only (pcdata) fields onto _char_base()
    (cf. 1stMud new_char + new_pcdata in recycle.c; char_data in structs.h:560).
    Also derives race-backed combat/body fields from RACE_TABLE (cf. 1stMud
    nanny.c:533-540 / save.c:723-730), so PCs get racial
    aff/imm/res/vuln/stats/size plus the same body-part-drop logic as mobs
    (combat.py _death_cry).

    Args:
        class_idx (int): Starting class index into CLASS_TABLE. Default only
            matters for the load path, where the save overwrites it.
        race_name (str): Starting race name, looked up in RACE_TABLE. Default
            only matters for the load path, where the save overwrites it.

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
        # [PRIMESUD] prestige tier counter; bumped by finish_tier_reset
        # (training.py). See DESIGN.md multiclass tiering.
        "tier":        0,
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
        # cf. 1stMud pcdata->alias[]/alias_sub[] parallel arrays; PrimeSUD
        # uses a single list of [name, sub] pairs, order preserved (see
        # aliases.py substitute_alias / do_alias).
        "aliases": [],
        # cf. 1stMud nanny default path: "rom basics" + class basics +
        # class default groups, recall 50. The weapon pick's Max(40, learned)
        # floor (nanny.c HANDLE_CON_PICK_WEAPON) is applied by game_state.py
        # new_game, not here -- it needs the player's choice of weapon, and
        # this function has no interactive path. Other skills cost trains at
        # a gain trainer (do_gain). Customization/creation points not ported
        # (see groups.py). (Racial skills granted below after race-merge block.)
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
    ch["race"] = race_name
    _race = race_lookup(ch["race"]) or RACE_TABLE["Human"]
    _stats = _race.get("stats", (13, 13, 13, 13, 13))
    ch["perm_stat"] = {
        "str": _stats[0], "dex": _stats[1], "int": _stats[2],
        "wis": _stats[3], "con": _stats[4],
    }
    ch["size"] = _race.get("size", "medium")
    ch["affected_by"] = dict(_race.get("aff", {}))
    ch["imm_flags"] = dict(_race.get("imm", {}))
    ch["res_flags"] = dict(_race.get("res", {}))
    ch["vuln_flags"] = dict(_race.get("vuln", {}))
    ch["form_flags"] = dict(_race.get("form", {}))
    ch["part_flags"] = dict(_race.get("parts", {}))
    # cf. 1stMud nanny.c: group_add(ch, race->skills[i], false) grants
    # racial skills at 1% learned. 1stMud group_add calls skill_lookup
    # internally (skills.c:900); PrimeSUD uses _skill_lookup (magic.py).
    from magic import _skill_lookup  # deferred: player -> magic -> combat -> player cycle
    for rsk_name in _race.get("skills", ()):
        rsk_sn = _skill_lookup(rsk_name)
        if rsk_sn is not None and ch["learned"].get(rsk_sn, 0) == 0:
            ch["learned"][rsk_sn] = 1
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
    ch["stance"][STANCE_CURRENT] = STANCE_NONE
    ch["stance"][STANCE_AUTODROP] = STANCE_NONE
    # cf. 1stMud nanny.c CON_ROLL_STATS 'y' + add_default_groups ('N' path)
    group_add_basics_and_defaults(ch)
    ch["learned"][GSN_RECALL] = 50  # cf. nanny.c: learned[gsn_recall] = 50
    # cf. 1stMud exp_per_level in skills.c (race class_mult scaling)
    ch["xp_next"] = exp_per_level(ch)
    # cf. 1stMud nanny.c CON_READ_MOTD: sprintf(buf, "the %s %s", race->name,
    # ClassName(prime_class)); set_title(ch, buf) -- default score title.
    # [PRIMESUD] Saves from before the title field existed have no "p.title"
    # save line, so a loaded old character keeps this freshly-derived title
    # (computed from create_char's placeholder class/race, not the loaded
    # ones) until `title` is used to set a new one -- cosmetic only, same
    # "left at create_char() defaults" precedent as any other additive save
    # field (see game_state.py SAVE_VERSION comment).
    set_title(ch, "the " + race_name + " " + class_name(ch, class_idx))
    return ch


def group_add_basics_and_defaults(ch):
    """Grant "rom basics" + base + default groups for all held classes
    (cf. 1stMud nanny.c creation/remort grants). [PRIMESUD] helper."""
    gn_add(ch, group_lookup("rom basics"))
    add_base_groups(ch)
    add_default_groups(ch)




import handler
from handler import (get_curr_stat, affect_remove, affect_modify, _char_base,
                   _apply_item_modifiers, _item_armor_runtime,
                   act, affect_find, affect_join, chprintln, is_affected,
                   unequip_char, TO_CHAR, TO_ROOM)
from world import ITEM_DEFS


def reset_char(player):
    """Strip and reapply all equipment and spell affect bonuses (cf. 1stMud reset_char in handler.c).

    Zeroes mod_stat, resets max_hit/mana/move to perm baselines, clears
    armor/hitroll/damroll/saving_throw, then re-applies equipment (with
    enchanted check via _apply_item_modifiers) and character spell affects.

    [PRIMESUD] Omits perm-recovery block (no legacy saves to migrate).
    [PRIMESUD] Omits last_level (XP penalty not ported).

    Args:
        player (dict): Player state dict.
    """
    # -- Reset to baselines (cf. 1stMud handler.c lines 512-528)
    # cf. 1stMud: ch->sex = ch->pcdata->true_sex (handler.c:518)
    player["sex"] = player.get("true_sex", player.get("sex", "neutral"))
    for k in player.get("mod_stat", {}):
        player["mod_stat"][k] = 0
    player["max_hit"] = player["perm_hit"]
    player["max_mana"] = player["perm_mana"]
    player["max_move"] = player["perm_move"]
    player["armor"] = (100, 100, 100, 100)
    player["hitroll"] = 0
    player["damroll"] = 0
    player["saving_throw"] = 0

    # [PRIMESUD] Hold handler._affect_depth so affect_modify's wield-drop
    # can't fire on transient mid-reset stats (e.g. wield re-applied before a
    # +str item in a later slot). 1stMud reset_char applies mods with its own
    # inline switch (handler.c:530-734), never via affect_modify, so it can
    # never drop during a reset either.
    handler._affect_depth += 1
    try:
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
    finally:
        handler._affect_depth -= 1


# -- Tick regen ---------------------------------------------------------------

def _regen_tail(gain, char, rate):
    """Room-rate multiply then affect divisors on a regen gain. [PRIMESUD]

    Shared tail of 1stMud hit_gain/mana_gain/move_gain (update.c:226-238):
    room heal/mana rate, then poison /4, plague /8, haste|slow /2. Furniture
    value[3]/value[4] multipliers skipped -- no furniture content (DESIGN.md).
    Integer math only.

    Args:
        gain (int): Pre-tail regen amount.
        char (dict): Player or mob instance (supplies affected_by).
        rate (int): Room heal_rate (hp/mv) or mana_rate (mp), percent.

    Returns:
        int: Adjusted gain.
    """
    gain = gain * rate // 100
    aff = char.get("affected_by", {})
    if aff.get("poison"):
        gain //= 4
    if aff.get("plague"):
        gain //= 8
    if aff.get("haste") or aff.get("slow"):
        gain //= 2
    return gain


def _mob_hp_regen(mob):
    """Regenerate one tick of hp for a mob (cf. 1stMud hit_gain IsNPC branch,
    update.c:169-190, gated by char_update at update.c:538/550-553). [PRIMESUD]

    Hp only: mob instances carry no mana/move pools (create_mobile never seeds
    them; spec casters cast without mana), so mana_gain/move_gain
    (update.c:253-267, 331-333) are not ported. Integer math only; no
    allocations.

    Args:
        mob (dict): NPC instance dict (hit/max_hit/pos/level/room/affected_by).
    """
    # char_update gate: skip mortal/incap/dead (position < POS_STUNNED)
    if POS_ORDER.get(mob.get("pos", "standing"), 8) < POS_ORDER["stunned"]:
        return
    hit = mob.get("hit", 0)
    max_hit = mob.get("max_hit", 0)
    if hit >= max_hit:  # already full -- early out
        return
    gain = 5 + mob.get("level", 1)
    if mob.get("affected_by", {}).get("regeneration"):
        gain *= 2
    pos = mob.get("pos", "standing")
    if pos == "sleeping":
        gain = 3 * gain // 2
    elif pos == "resting":
        pass
    elif pos == "fighting":
        gain //= 3
    else:
        gain //= 2
    rdef = ROOM_DEFS.get(mob.get("room"))
    rate = rdef.get("heal_rate", 100) if rdef else 100
    gain = _regen_tail(gain, mob, rate)
    mob["hit"] = min(max_hit, hit + gain)


def _char_disease_tick(ch):
    """Plague/poison periodic damage, with contagion, or incap/mortal
    bleed-out -- one branch only, per tick (cf. 1stMud char_update
    plague/poison/incap/mortal if/else-if chain in update.c:670-746).
    [PRIMESUD]

    A plagued char skips the poison and bleed-out branches this tick; a
    poisoned-but-not-slowed char skips bleed-out; the four cases are mutually
    exclusive, matching upstream's single if/else-if chain exactly.

    NPCs never occupy incap/mortal in real play (update_pos kills a mob
    outright at hit < 1, mirroring 1stMud), so the bleed-out branches are
    explicitly skipped for is_npc chars [PRIMESUD] (defends against an
    externally-forced incap/mortal mob state, which combat.damage's
    stop_fighting is not equipped to self-damage safely). Plague/poison
    still tick for any char, so a plagued or poisoned NPC keeps taking
    damage and can still spread/catch plague via the room-occupant loop
    below (mob<->player contagion is intentional).

    [PRIMESUD] IsImmortal(vch) contagion-immunity check omitted -- no
    reachable immortal levels in single-player PrimeSUD (cf. mob.py
    aggr_update's equivalent omission).

    Args:
        ch (dict): Character state dict (player or mob instance).
    """
    from combat import damage  # deferred: combat imports player
    from magic import saves_spell, _new_affect  # deferred: magic -> combat -> player cycle

    if is_affected(ch, GSN_PLAGUE):
        if ch.get("room") is None:
            return
        act("$n writhes in agony as plague sores erupt from $s skin.", ch, None, None, TO_ROOM)
        chprintln(ch, "You writhe in agony from the plague.")
        af = affect_find(ch, GSN_PLAGUE)
        if af is None:
            ch.get("affected_by", {}).pop("plague", None)
            return
        if af["level"] == 1:
            return

        plague_level = af["level"] - 1
        # cf. update.c:697-703 -- new contagion affect, one level weaker
        plague = _new_affect(GSN_PLAGUE, plague_level,
                             randint(1, 2 * plague_level), "str", -5, "plague")
        room = world.rooms.get(ch["room"])
        if room is not None:
            # Room occupants: NPCs in the room + the player if present (mobs
            # are tracked per-room; the player is not -- movement.py).
            occupant_ids = list(room.get("mobs", []))
            _player = world.chars.get(1)
            if (_player is not None and _player.get("room") == ch["room"]
                    and 1 not in occupant_ids):
                occupant_ids.append(1)
            for vid in occupant_ids:
                vch = world.chars.get(vid)
                if vch is None:
                    continue
                if (not saves_spell(plague["level"] - 2, vch, DAM_DISEASE)
                        and not vch.get("affected_by", {}).get("plague")
                        and randint(0, 15) == 0):  # cf. 1stMud number_bits(4) == 0
                    chprintln(vch, "You feel hot and feverish.")
                    act("$n shivers and looks very ill.", vch, None, None, TO_ROOM)
                    affect_join(vch, plague)

        dam = min(ch.get("level", 1), af["level"] // 5 + 1)
        ch["mana"] = ch.get("mana", 0) - dam
        ch["move"] = ch.get("move", 0) - dam
        damage(ch, ch, dam, GSN_PLAGUE, DAM_DISEASE, False)
        return

    aff = ch.get("affected_by", {})
    if aff.get("poison") and not aff.get("slow"):
        poison = affect_find(ch, GSN_POISON)
        if poison is not None:
            act("$n shivers and suffers.", ch, None, None, TO_ROOM)
            chprintln(ch, "You shiver and suffer.")
            damage(ch, ch, poison["level"] // 10 + 1, GSN_POISON, DAM_POISON, False)
        return

    # Bleed-out: 1stMud reaches this branch only for players in practice --
    # update_pos (fight.c) forces IsNPC chars straight to POS_DEAD at hit < 1,
    # so a mob can never carry pos incap/mortal from real combat. [PRIMESUD]
    # guard on !is_npc anyway: an externally-forced incap/mortal mob state
    # (e.g. debug/test tooling) would otherwise self-damage via combat.damage,
    # which assumes a fully-populated mob instance (tpl, etc.) that such a
    # state may not have.
    if ch.get("is_npc"):
        return
    pos = ch.get("pos", "standing")
    if pos == "incap" and randint(0, 1) == 0:  # cf. 1stMud number_range(0,1) == 0
        damage(ch, ch, 1, TYPE_UNDEFINED, DAM_NONE, False)
    elif pos == "mortal":
        damage(ch, ch, 1, TYPE_UNDEFINED, DAM_NONE, False)


def tick_update(tr, player, room):
    """Regenerate HP/MP/MV once per world tick, gated on position, then tick
    affects and disease/bleed-out (cf. 1stMud char_update in update.c).

    Regen only runs at ``position >= POS_STUNNED`` (update.c:538); below that
    (incap/mortal/dead) the char instead bleeds out via
    :func:`_char_disease_tick`, matching upstream's split between the regen
    block (update.c:538-564) and the unconditional plague/poison/incap/mortal
    chain that follows the affect loop (update.c:670-746).

    Hunger/thirst conditions omitted [PRIMESUD].

    Args:
        tr: Terminal for affect wear-off messages.
        player (dict): Player state dict.
        room (dict): Current room (supplies heal_rate/mana_rate).

    Uses imported world module for player stat lookups.
    """
    # deferred: player -> skill_utils -> handler load-order
    con  = get_curr_stat(player, "con")
    int_ = get_curr_stat(player, "int")
    wis  = get_curr_stat(player, "wis")
    level = player.get("level", 1)

    pos = player.get("pos", "standing")

    # cf. 1stMud update.c:538 -- hit/mana/move gain only while conscious
    # (>= POS_STUNNED); incap/mortal/dead chars bleed instead (see below).
    if POS_ORDER.get(pos, 8) >= POS_ORDER["stunned"]:
        # HP (cf. 1stMud hit_gain in update.c:191-201)
        hp_gain = max(3, con - 3 + level // 2) + (player["max_hit"] - 10)
        # fast healing bonus (cf. update.c:195-201): roll == skill% is a miss (<)
        roll = randint(1, 100)
        if roll < get_skill(player, GSN_FAST_HEALING):
            hp_gain += roll * hp_gain // 100
            if player["hit"] < player["max_hit"]:
                check_improve(player, GSN_FAST_HEALING, True, 8)
        # Position divisors: sleeping /1, resting /2, fighting /6, other /4
        if pos == "resting":
            hp_gain //= 2
        elif pos == "fighting":
            hp_gain //= 6
        elif pos != "sleeping":
            hp_gain //= 4
        # Hunger/thirst omitted [PRIMESUD]
        hp_gain = _regen_tail(hp_gain, player, room.get("heal_rate", 100))

        # MP (cf. 1stMud mana_gain in update.c:269-297) -- base (WIS+INT+level)/2
        mp_gain = (int_ + wis + level) // 2
        # meditation bonus (cf. update.c:274-280), same roll shape as fast healing
        roll = randint(1, 100)
        if roll < get_skill(player, GSN_MEDITATION):
            mp_gain += roll * mp_gain // 100
            if player["mana"] < player["max_mana"]:
                check_improve(player, GSN_MEDITATION, True, 8)
        # non-casters regen mana at half (cf. update.c:281-282)
        if not has_spells(player):
            mp_gain //= 2
        if pos == "resting":
            mp_gain //= 2
        elif pos == "fighting":
            mp_gain //= 6
        elif pos != "sleeping":
            mp_gain //= 4
        mp_gain = _regen_tail(mp_gain, player, room.get("mana_rate", 100))

        # MV (cf. 1stMud move_gain in update.c) -- base max(15, level);
        # sleeping +DEX, resting +DEX/2
        dex = get_curr_stat(player, "dex")
        mv_gain = max(15, level)
        if pos == "sleeping":
            mv_gain += dex
        elif pos == "resting":
            mv_gain += dex // 2
        mv_gain = _regen_tail(mv_gain, player, room.get("heal_rate", 100))

        player["hit"] = min(player["max_hit"], player["hit"] + hp_gain)
        player["mana"] = min(player["max_mana"], player["mana"] + mp_gain)
        player["move"] = min(player["max_move"], player["move"] + mv_gain)

    # cf. 1stMud update.c:566-567 -- a stunned char whose hit points have
    # recovered stands back up on the next tick (without this, a stunned
    # player who regens above 0 hp has no recovery path: the interpreter
    # blocks all commands below sleeping)
    if player.get("pos") == "stunned":
        from combat import update_pos  # deferred: combat imports player
        update_pos(player)

    _tick_affects(player, tr)

    # cf. 1stMud char_update plague/poison/incap/mortal chain, update.c:670-746
    _char_disease_tick(player)

    _light_burnout(tr, player)

    # Mobs tick affects + regen hp too (cf. 1stMud char_update iterating
    # char_first, update.c:528). Wear-off messages are char-directed, so
    # silent for mobs. _mob_hp_regen gates its own position; _char_disease_tick
    # skips its bleed-out branch for is_npc chars (see that function's
    # docstring), but plague/poison still tick for mobs, so a plagued or
    # poisoned NPC keeps taking damage and can still spread/catch plague from
    # the room.
    for _inst in list(world.chars.values()):
        if not _inst.get("is_npc"):
            continue
        if _inst.get("affect_list"):
            _tick_affects(_inst, None)
        _mob_hp_regen(_inst)
        _char_disease_tick(_inst)


def _light_burnout(tr, player):
    """Burn one hour of fuel from the player's equipped light (cf. 1stMud char_update light block in update.c:597-613).

    Players only -- 1stMud gates the block on ``!IsNPC`` and level below
    immortal, so NPC lights never burn. [PRIMESUD] the room light counter is
    computed (room_light), so there is nothing to decrement there. An infinite
    (absent/negative) or already-dead (0) light carries no instance
    ``light_hours`` and is skipped by the ``> 0`` guard.

    Args:
        tr: Terminal for flicker / burnout messages.
        player (dict): Player state dict.
    """
    light = (player.get("equip") or {}).get("light")
    if not isinstance(light, dict):
        return
    if ITEM_DEFS[light["vnum"]].get("type") != "light":
        return
    fuel = light.get("light_hours")
    if fuel is None or fuel <= 0:
        return
    fuel -= 1
    light["light_hours"] = fuel
    if fuel == 0:
        act("$p goes out.", player, light, None, TO_ROOM)
        act("$p flickers and goes out.", player, light, None, TO_CHAR)
        # cf. 1stMud extract_obj: the dead light leaves the game entirely.
        # unequip_char reverses its modifiers and returns it to inventory
        # (mirrors update.py's decay extraction); then drop it for good.
        unequip_char(player, "light")
        player["inv"].remove(light)
    elif fuel <= 5:
        act("$p flickers.", player, light, None, TO_CHAR)


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
