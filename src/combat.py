"""Combat rounds, damage resolution, skills, and fight state."""

import classes
import terminal
import world
from colors import upper
from comm import die_follower, do_emote, do_function, nuke_pets, stop_follower
from config import (
    KEY_COMMANDS,
    LEVEL_HERO,
    PULSE_VIOLENCE,
    POS_ORDER,
    POS_FROM_SHORT,
    R_STARTING_ROOM,
    DEATH_MSG_DELAY,
    CON_APP_HITP,
    WIS_APP_PRACTICE,
    ATTACK_TABLE,
    TYPE_HIT,
    TYPE_UNDEFINED,
    DAM_NONE,
    DAM_BASH,
    DAM_PIERCE,
    DAM_SLASH,
    DAM_FIRE,
    DAM_COLD,
    DAM_LIGHTNING,
    DAM_POISON,
    DAM_NEGATIVE,
    AC_PIERCE,
    AC_BASH,
    AC_SLASH,
    AC_EXOTIC,
    IS_NORMAL,
    IS_IMMUNE,
    IS_RESISTANT,
    IS_VULNERABLE,
    IMMUNE_NONE,
    DAM_TO_FLAG,
    XP_BASE,
    SIZE_RANK,
)
from debug import DBG, dbg  # [PRIMESUD]
from effects import TARGET_CHAR, fire_effect, cold_effect, shock_effect
from gquest import gq_kill_check
from handler import (get_hitroll, get_damroll, get_armor, get_curr_stat, act,
                     is_awake, can_see, affect_to_char, affect_remove, affect_strip,
                     affect_join, is_affected,
                     chprintln, get_char_room, unequip_char,
                     TO_CHAR, TO_NOTVICT, TO_ROOM, TO_VICT,
                     is_good, is_evil, is_neutral,
                     PLR_AUTOLOOT, PLR_AUTOSAC, PLR_AUTOGOLD, PLR_AUTOASSIST,
                     PLR_AUTODAMAGE, PLR_DEFAULTS)
from hunt import hunt_victim
from item import (create_object, item_extra_flags,
                  set_item_extra_flag, apply_money_pickup, item_weapon_flags,
                  item_affect_find, item_type as _item_type)
from picker import pick_from
from player import reset_char
from quest import (QUEST_DELIVER, QUEST_FINDMOB, is_quester, quest_kill_check,
                   update_all_qobjs)
from races import race_lookup
from skill_utils import get_skill, check_improve, skill_level, WaitState, DazeState
from skills_table import (
    SKILL_TABLE, SKILLS, WEAPON_GSN_MAP,
    GSN_BACKSTAB, GSN_BASH, GSN_BERSERK, GSN_DIRT, GSN_DISARM,
    GSN_DODGE, GSN_ENHANCED_DAMAGE, GSN_HAND_TO_HAND, GSN_KICK, GSN_PARRY,
    GSN_RESCUE, GSN_SHIELD_BLOCK, GSN_SECOND_ATTACK, GSN_THIRD_ATTACK,
    GSN_TRIP, GSN_POISON, GSN_SWORD, GSN_FLOWING_FORM, GSN_RIPOSTE,
    GSN_DRIVING_FORM,
)
from stances import (STANCE_TABLE, MAX_STANCE,
                     STANCE_NONE, STANCE_NORMAL, STANCE_VIPER, STANCE_CRANE,
                     STANCE_CRAB, STANCE_MONGOOSE, STANCE_BULL, STANCE_MANTIS,
                     STANCE_DRAGON, STANCE_TIGER, STANCE_MONKEY, STANCE_SWALLOW,
                     STANCE_CURRENT, STANCE_AUTODROP,
                     valid_stance, get_stance, set_stance, in_stance,
                     stance_name, stance_lookup, can_use_stance,
                     improve_stance, autodrop)
from urandom import randint
from util import wait, count_str, num_str, obj_remove, pad_right
from world import MOB_DEFS, ROOM_DEFS, item_tpl
from world import (
    OBJ_VNUM_CORPSE_NPC, OBJ_VNUM_CORPSE_PC,
    OBJ_VNUM_SILVER_ONE,
    OBJ_VNUM_GOLD_ONE,
    OBJ_VNUM_SILVER_SOME,
    OBJ_VNUM_GOLD_SOME,
    OBJ_VNUM_COINS,
)


# -- Violence update (called every PULSE_VIOLENCE) -----------------------------

def violence_update(player):
    """One combat pulse: all chars with a fight target attack (cf. 1stMud violence_update in fight.c).
    [Verified: 21/07/2026] -- [PRIMESUD] autoskill hook, keyboard-drain
    checkpoints, and active-fighter index scan added.

    Args:
        player (dict): Player state dict.
    """
    chars = world.chars
    _pump = getattr(terminal.tr, "_pump_keyboard", None)  # tests stub tr without it

    room_trig = False  # room TRIG_FIGHT at most once per pulse (cf. fight.c:65)
    # [PRIMESUD] Scan only the active-fighter index instead of every loaded
    # char (139-char full-world scan cost ~100ms/round on device). sorted()
    # both snapshots to a list (FIGHTERS/chars can be mutated during
    # iteration -- deaths, stop_fighting, programs) and preserves the old
    # deterministic id-order iteration for the chars that would have acted.
    for cid in sorted(world.FIGHTERS):
        ch = chars.get(cid)
        # [PRIMESUD] stale-tolerant: ch may have been extracted/evicted
        # without going through stop_fighting (e.g. far-area eviction
        # deletes chars wholesale), or a direct writer may have cleared
        # fighting/hunting without updating the index. Either way the
        # entry is no longer useful -- drop it and move on.
        if ch is None or (ch["fighting"] is None and ch.get("hunting") is None):
            world.FIGHTERS.discard(cid)
            continue

        # 1stMud: IsNPC(ch) && ch->fighting == NULL && IsAwake(ch) && ch->hunting != NULL
        if ch["is_npc"] and ch["fighting"] is None and is_awake(ch) and ch.get("hunting") is not None:
            hunt_victim(ch)
            continue

        # 1stMud: victim = ch->fighting; if victim == NULL || ch->in_room == NULL: continue
        # [PRIMESUD] ch->in_room == NULL cannot occur; all chars store fighting as char ID
        if ch["fighting"] is None:
            continue
        victim = chars.get(ch["fighting"])
        if victim is None:
            # [PRIMESUD] 1stMud nulls stale fighting refs in extract_char; we have no
            # equivalent sweep, so detect and clean up lazily here.
            stop_fighting(ch, both=False)
            continue

        # 1stMud: if IsAwake(ch) && ch->in_room == victim->in_room: multi_hit else stop_fighting
        if is_awake(ch) and ch["room"] == victim["room"]:
            multi_hit(ch, victim)
        else:
            stop_fighting(ch, both=False)

        # [PRIMESUD] drain firmware key FIFO (4-deep) between combatants so
        # long rounds cannot drop input; local 16-entry queue holds them for
        # the game loop.
        if _pump:
            _pump(KEY_COMMANDS)

        # 1stMud: victim = ch->fighting; if victim == NULL: continue
        # (fight.c:86 re-fetches: multi_hit may have killed and retargeted,
        # leaving the old local victim pointing at an extracted char)
        victim = chars.get(ch["fighting"]) if ch["fighting"] is not None else None
        if victim is None:
            continue

        # 1stMud: check_assist(ch, victim)
        check_assist(ch, victim)

        # mob TRIG_FIGHT / TRIG_HPCNT (cf. fight.c:91-98); opponent = victim
        if ch["is_npc"]:
            from mobprog import fight_trigger  # deferred: keep mobprog off the boot path
            fight_trigger(ch, victim)
        else:
            # [PRIMESUD] autoskill: player fires one auto combat action per
            # round, mirroring where mobs fire their specials
            from autoskill import auto_skill_round  # deferred: autoskill imports combat
            auto_skill_round(ch)
        # worn-item then room TRIG_FIGHT, the room at most once per pulse;
        # the prog's triggering char is ch's opponent (cf. fight.c:99-113)
        import mobprog  # deferred: keep mobprog off the boot path
        for obj in ch["equip"].values():
            if obj is not None and mobprog.has_otrigger(obj, "fight"):
                mobprog.opercent_trigger(
                    {"obj": obj, "room": ch["room"], "carrier": ch},
                    victim, None, None, "fight")
        if not room_trig and mobprog.has_rtrigger(ch["room"], "fight"):
            room_trig = True
            mobprog.rpercent_trigger(ch["room"], victim, None, None, "fight")

    if "fidx" in DBG:  # [PRIMESUD] costs nothing when the channel is off
        for cid, cch in chars.items():
            if cch["fighting"] is not None and cid not in world.FIGHTERS:
                dbg("fidx: missing " + num_str(cid))
                world.FIGHTERS.add(cid)


def check_assist(ch, victim):
    """Let idle room chars join combat (cf. 1stMud check_assist in fight.c).
    [Verified: 04/07/2026]

    Three cases mirror 1stMud exactly:
    - ch is player, rch is mob with assist_players: rch jumps in against victim.
    - ch is player or charmed: charmed rch in ch's group assists; the player
      as assisting rch (PLR_AUTOASSIST) is special-cased after the loop since
      rs["mobs"] excludes the player.
    - ch is mob (not charmed), rch is mob: assist_all / group / race / align / vnum;
      50% trigger chance; target picked from victim's group (single-player: victim).

    Args:
        ch (dict): Attacker (player or mob).
        victim (dict): Ch's current fight target.
    """
    chars = world.chars
    rs    = world.rooms[ch["room"]]
    if ch["is_npc"]:
        ch_tpl = MOB_DEFS[ch["tpl"]]

    for mob_id in list(rs["mobs"]):
        rch = chars.get(mob_id)
        if rch is None or not is_awake(rch) or rch["fighting"] is not None:
            continue

        rch_tpl = MOB_DEFS[rch["tpl"]]
        off = rch["off_flags"]

        # Case 1: mob with assist_players aids player against victim
        if not ch["is_npc"]:
            if off.get("assist_players") and rch["level"] + 6 > victim["level"]:
                do_function(rch, do_emote, "screams and attacks!")
                multi_hit(rch, victim)
                continue

        # Case 2: charmed follower assists its group (cf. 1stMud fight.c:139-148)
        if not ch["is_npc"] or ch["affected_by"].get("charm"):
            if (rch["affected_by"].get("charm")
                    and is_same_group(ch, rch)
                    and not is_safe(rch, victim)):
                multi_hit(rch, victim)
            continue

        # Case 3: ch is mob (not charmed)
        ch_grp  = ch_tpl.get("group")
        rch_grp = rch_tpl.get("group")
        qualifies = (
            off.get("assist_all")
            or (rch_grp and rch_grp == ch_grp)
            or (off.get("assist_race")
                and rch_tpl.get("race", "").lower() == ch_tpl.get("race", "").lower())
            or (off.get("assist_align") and _same_align(rch_tpl, ch_tpl))
            or (off.get("assist_vnum") and rch["tpl"] == ch["tpl"])
        )
        if not qualifies:
            continue

        # 50% chance to skip (cf. 1stMud number_bits(1) == 0)
        if randint(0, 1) == 0:
            continue

        # Pick random target from victim's group (cf. 1stMud target selection loop:
        # candidates require can_see(rch, vch)).
        # [PRIMESUD] Single-player: victim's group = victim only; target is always victim.
        if not can_see(rch, victim):
            continue
        do_function(rch, do_emote, "screams and attacks!")
        multi_hit(rch, victim)

    # [PRIMESUD] Player as assisting rch: 1stMud's rch loop naturally includes
    # players in the room, but our rs["mobs"] excludes the player, so the
    # PLR_AUTOASSIST branch of case 2 is handled here (fires when the charmed
    # pet fights and the player is idle).
    player = chars.get(1)
    if (player is not None and ch is not player
            and ch["is_npc"] and ch["affected_by"].get("charm")
            and ch["room"] == player["room"]
            and is_awake(player) and player["fighting"] is None
            and player.get("flags", PLR_DEFAULTS) & PLR_AUTOASSIST
            and is_same_group(ch, player)
            and not is_safe(player, victim)):
        multi_hit(player, victim)


# -- Helpers -------------------------------------------------------------------

def _same_align(tpl_a, tpl_b):
    """True if both templates share the same alignment band (good/neutral/evil). [PRIMESUD]

    Args:
        tpl_a (dict): First mob template.
        tpl_b (dict): Second mob template.

    Returns:
        bool: True if both are in the same alignment band.
    """
    return ((is_good(tpl_a) and is_good(tpl_b))
            or (is_evil(tpl_a) and is_evil(tpl_b))
            or (is_neutral(tpl_a) and is_neutral(tpl_b)))


def dice(num, size):
    """Roll num dice of size sides and return the sum (cf. 1stMud `dice` in db.c).
    [Verified: 03/07/2026]

    Args:
        num (int): Number of dice to roll.
        size (int): Number of sides per die.

    Returns:
        int: Sum of all dice rolls.
    """
    if size == 0:
        return 0
    if size == 1:
        return num
    total = 0
    for _ in range(num):
        total += randint(1, size)
    return total


def _cdiv(a, b):
    """Integer division truncating toward zero (C semantics; Python // floors). [PRIMESUD]"""
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def interpolate(level, value_00, value_32):
    """Linear interpolation between level-0 and level-32 values (cf. 1stMud interpolate in db.c).
    [Verified: 02/07/2026]"""
    return value_00 + _cdiv(level * (value_32 - value_00), 32)


def get_thac0(ch):
    """Base THAC0 before hitroll/skill adjustments (cf. 1stMud one_hit in fight.c).
    [Verified: 02/07/2026]

    NPC curve from act class flags; player curve from the class table
    (worst thac0_00, best thac0_32 across held classes).

    Args:
        ch (dict): Attacker (player or mob instance).

    Returns:
        int: Base THAC0 after the negative soft-caps.
    """
    if ch["is_npc"]:
        act = ch["act_flags"]
        thac0_00 = 20
        thac0_32 = -4
        if act.get("warrior"):
            thac0_32 = -10
        elif act.get("thief"):
            thac0_32 = -4
        elif act.get("cleric"):
            thac0_32 = 2
        elif act.get("mage"):
            thac0_32 = 6
    else:
        thac0_00 = classes.get_thac00(ch)
        thac0_32 = classes.get_thac32(ch)
    thac0 = interpolate(ch["level"], thac0_00, thac0_32)
    if thac0 < 0:
        thac0 = _cdiv(thac0, 2)
    if thac0 < -5:
        thac0 = -5 + _cdiv(thac0 + 5, 2)
    return thac0


def xp_compute(gch, victim, total_levels):
    """Compute XP for gch from killing victim in a group of total_levels
    (cf. 1stMud xp_compute in fight.c).
    [Verified: 02/07/2026] -- time_per_level penalty skipped (no play-time tracking).

    Includes alignment-based XP modifiers and alignment drift on the killer.

    Args:
        gch (dict): Group member receiving XP (player).
        victim (dict): Defeated mob instance.
        total_levels (int): Sum of effective levels in the group
            (PCs at full level, NPCs at level/2).

    Returns:
        int: XP gain for this group member.
    """
    level_range = victim["level"] - gch["level"]

    # -- Base XP from level difference (cf. 1stMud xp_compute switch)
    if level_range <= -10:
        base_exp = 0
    elif level_range > 4:
        base_exp = 160 + 20 * (level_range - 4)
    else:
        base_exp = XP_BASE[level_range]

    # -- Alignment drift (cf. 1stMud xp_compute alignment section)
    victim_align = victim.get("alignment", 0)
    gch_align = gch.get("alignment", 0)
    victim_act = victim["act_flags"]

    align = victim_align - gch_align

    if not victim_act.get("noalign"):
        if align > 500:
            change = (align - 500) * base_exp // 500 * gch["level"] // total_levels
            change = max(1, change)
            gch["alignment"] = max(-1000, gch_align - change)
        elif align < -500:
            change = (-align - 500) * base_exp // 500 * gch["level"] // total_levels
            change = max(1, change)
            gch["alignment"] = min(1000, gch_align + change)
        else:
            # C division truncates toward zero; Python // floors. gch_align may
            # be negative here, so compute on the magnitude and re-apply sign.
            change = abs(gch_align) * base_exp // 500 * gch["level"] // total_levels
            if gch_align < 0:
                change = -change
            gch["alignment"] -= change

    # -- Alignment XP modifiers (cf. 1stMud xp_compute alignment XP section)
    gch_align = gch.get("alignment", 0)
    if victim_act.get("noalign"):
        xp = base_exp
    elif gch_align > 500:
        if victim_align < -750:
            xp = base_exp * 4 // 3
        elif victim_align < -500:
            xp = base_exp * 5 // 4
        elif victim_align > 750:
            xp = base_exp // 4
        elif victim_align > 500:
            xp = base_exp // 2
        elif victim_align > 250:
            xp = base_exp * 3 // 4
        else:
            xp = base_exp
    elif gch_align < -500:
        if victim_align > 750:
            xp = base_exp * 5 // 4
        elif victim_align > 500:
            xp = base_exp * 11 // 10
        elif victim_align < -750:
            xp = base_exp // 2
        elif victim_align < -500:
            xp = base_exp * 3 // 4
        elif victim_align < -250:
            xp = base_exp * 9 // 10
        else:
            xp = base_exp
    elif gch_align > 200:
        if victim_align < -500:
            xp = base_exp * 6 // 5
        elif victim_align > 750:
            xp = base_exp // 2
        elif victim_align > 0:
            xp = base_exp * 3 // 4
        else:
            xp = base_exp
    elif gch_align < -200:
        if victim_align > 500:
            xp = base_exp * 6 // 5
        elif victim_align < -750:
            xp = base_exp // 2
        elif victim_align < 0:
            xp = base_exp * 3 // 4
        else:
            xp = base_exp
    else:
        if victim_align > 500 or victim_align < -500:
            xp = base_exp * 4 // 3
        elif -200 < victim_align < 200:
            xp = base_exp // 2
        else:
            xp = base_exp

    # -- Low-level scaling (cf. 1stMud xp_compute)
    if gch["level"] < 6:
        xp = 10 * xp // (gch["level"] + 4)

    # -- High-level scaling (cf. 1stMud xp_compute)
    if gch["level"] > 35:
        xp = 15 * xp // (gch["level"] - 25)

    # -- Time-per-level penalty
    # [PRIMESUD] skip time_per_level (no play-time tracking ported)

    # -- Randomize +/-25% (cf. 1stMud xp_compute: number_range(xp*3/4, xp*5/4))
    xp = randint(xp * 3 // 4, xp * 5 // 4)

    # -- Group scaling (cf. 1stMud xp_compute: xp * gch->level / total_levels)
    xp = xp * gch["level"] // max(1, total_levels - 1)

    return xp


def _get_weapon_sn(ch, slot="wield"):
    """Return (sn, tpl_or_None) for the weapon in the given equip slot (cf. get_weapon_sn in handler.c).
    [Verified: 02/07/2026] -- 1stMud maps a wielded non-weapon to hand_to_hand; PrimeSUD's
    slot system only seats weapons in wield/secondary, so the case cannot occur.

    Args:
        ch (dict): Player or mob instance dict.
        slot (str): Equip slot key ('wield' or 'secondary').

    Returns:
        tuple: (sn (int), weapon_tpl (dict or None)).
            sn=GSN_HAND_TO_HAND when unarmed; sn=-1 for unknown weapon type.
    """
    wobj = ch["equip"].get(slot)
    if wobj is None:
        return GSN_HAND_TO_HAND, None
    tpl = item_tpl(wobj)
    sn = WEAPON_GSN_MAP.get(tpl.get("weapon_type", ""), -1)
    return sn, tpl


def _get_weapon_skill(ch, sn):
    """Return weapon skill% for ch and sn (cf. get_weapon_skill in handler.c).
    [Verified: 02/07/2026] -- 1stMud clamps Range(0,skill,100); learned is capped
    at 100 by check_improve and NPC formulas are non-negative, so min() suffices.

    Args:
        ch (dict): Player or mob instance dict.
        sn (int): Skill GSN; -1 = unknown weapon type.

    Returns:
        int: Skill percentage (0-100), capped.
            NPC: level-scaled formula. Player: learned dict lookup.
    """
    if ch.get("is_npc"):
        if sn == -1:
            skill = 3 * ch["level"]
        elif sn == GSN_HAND_TO_HAND:
            skill = 40 + 2 * ch["level"]
        else:
            skill = 40 + 5 * ch["level"] // 2
        return min(skill, 100)
    if sn == -1:
        return min(3 * ch["level"], 100)
    return ch["learned"].get(sn, 0)


# -- Damage flavour ------------------------------------------------------------

def _damage_verb(dmg):
    """Return verb pair for a damage amount (cf. 1stMud dam_message in fight.c).
    [Verified: 02/07/2026] -- {f flash codes dropped (unsupported); top-tier first-person grammar fixed.

    Args:
        dmg (int): Damage dealt (0 = miss).

    Returns:
        tuple: (first_person_verb (str), third_person_verb (str)).
    """
    # fmt: off
    if dmg == 0:     return ("miss",                                              "misses")
    if dmg <= 4:     return ("scratch",                                           "scratches")
    if dmg <= 8:     return ("graze",                                             "grazes")
    if dmg <= 12:    return ("hit",                                               "hits")
    if dmg <= 16:    return ("injure",                                            "injures")
    if dmg <= 20:    return ("wound",                                             "wounds")
    if dmg <= 24:    return ("maul",                                              "mauls")
    if dmg <= 28:    return ("decimate",                                          "decimates")
    if dmg <= 32:    return ("devastate",                                         "devastates")
    if dmg <= 36:    return ("maim",                                              "maims")
    if dmg <= 40:    return ("MUTILATE",                                          "MUTILATES")
    if dmg <= 44:    return ("DISEMBOWEL",                                        "DISEMBOWELS")
    if dmg <= 48:    return ("DISMEMBER",                                         "DISMEMBERS")
    if dmg <= 52:    return ("MASSACRE",                                          "MASSACRES")
    if dmg <= 56:    return ("MANGLE",                                            "MANGLES")
    if dmg <= 60:    return ("{b*** {BDEMOLISH {b***{x",                          "{b*** {BDEMOLISHES {b***{x")
    if dmg <= 75:    return ("{m*** {MDEVASTATE {m***{x",                         "{m*** {MDEVASTATES {m***{x")
    if dmg <= 100:   return ("{c=== {COBLITERATE {c==={x",                        "{c=== {COBLITERATES {c==={x")
    if dmg <= 125:   return ("{R>>> {YANNIHILATE {R<<<{x",                        "{R>>> {YANNIHILATES {R<<<{x")
    if dmg <= 150:   return ("{Y<<< {RERADICATE {Y>>>{x",                         "{Y<<< {RERADICATES {Y>>>{x")
    if dmg <= 185:   return ("{W***** {CPULVERIZE {W*****{x",                     "{W***** {CPULVERIZES {W*****{x")
    if dmg <= 220:   return ("{B-=- VAPORIZE -=-{x",                              "{B-=- VAPORIZES -=-{x")
    if dmg <= 275:   return ("{M<-==-> {CATOMIZE {M<-==->{x",                     "{M<-==-> {CATOMIZES {M<-==->{x")
    if dmg <= 315:   return ("{C<{W-:-{C>{W ASPHYXIATE {C<{W-:-{C>{x",            "{C<{W-:-{C>{W ASPHYXIATES {C<{W-:-{C>{x")
    if dmg <= 390:   return ("{W<-*-> {CRAVAGE {W<-*->{x",                        "{W<-*-> {CRAVAGES {W<-*->{x")
    if dmg <= 435:   return ("{M<>*<> {CFISSURE {M<>*<>{x",                       "{M<>*<> {CFISSURES {M<>*<>{x")
    if dmg <= 500:   return ("{Y<*>{R<*> {bLIQUIDATE {R<*>{Y<*>{x",               "{Y<*>{R<*> {bLIQUIDATES {R<*>{Y<*>{x")
    if dmg <= 590:   return ("{b<*>{Y<*>{R<*>{G EVAPORATE {R<*>{Y<*>{b<*>{x",     "{b<*>{Y<*>{R<*>{G EVAPORATES {R<*>{Y<*>{b<*>{x")
    if dmg <= 650:   return ("{Y<-=-> {RSUNDER {Y<-=->{x",                        "{Y<-=-> {RSUNDERS {Y<-=->{x")
    if dmg <= 790:   return ("{W<=-=><=-=> {GTEAR INTO {W<=-=><=-=>{x",           "{W<=-=><=-=> {GTEARS INTO {W<=-=><=-=>{x")
    if dmg <= 880:   return ("{Y<->*<=> {bWASTE {Y<=>*<->{x",                     "{Y<->*<=> {bWASTES {Y<=>*<->{x")
    if dmg <= 960:   return ("{R<-+-><-*-> {WCREMATE {R<-*-><-+->{x",             "{R<-+-><-*-> {WCREMATES {R<-*-><-+->{x")
    if dmg <= 1040:  return ("{M<*><*>{R<*><*> ANNIHILATE <*><*>{M<*><*>{x",      "{M<*><*>{R<*><*> ANNIHILATES <*><*>{M<*><*>{x")
    # [PRIMESUD] {f flash code unsupported on Prime -- dropped from PAIN/INCONCEIVABLE tiers
    if dmg <= 3000:  return ("{rinflict {RUNSPEAKABLE PAIN{r on{x",               "{rinflicts {RUNSPEAKABLE PAIN{r on{x")
    if dmg <= 6000:  return ("{rinflict {RUNTHINKABLE PAIN{r on{x",               "{rinflicts {RUNTHINKABLE PAIN{r on{x")
    if dmg <= 9000:  return ("{rinflict {RUNIMAGINABLE PAIN{r on{x",              "{rinflicts {RUNIMAGINABLE PAIN{r on{x")
    if dmg <= 12000: return ("{rinflict {RUNBELIEVABLE PAIN{r on{x",              "{rinflicts {RUNBELIEVABLE PAIN{r on{x")
    # [PRIMESUD] 1stMud ungrammatically uses "does ..." for first person too; fixed to "do"
    return ("do {mTOTALLY{x, {mUTTERLY{x, and in all other ways {mINCONCEIVABLE{w{x things to",
            "does {mTOTALLY{x, {mUTTERLY{x, and in all other ways {mINCONCEIVABLE{w{x things to")
    # fmt: on


def _damage_punct(dmg):
    """Return punctuation string matching damage severity (cf. 1stMud dam_message in fight.c).
    [Verified: 02/07/2026]

    Args:
        dmg (int): Damage dealt.

    Returns:
        str: One of '?', '.', '!', '!!', '!!!', '!!!!'.
    """
    if dmg < 0:     return "?"
    if dmg <= 250:  return "."
    if dmg <= 1000: return "!"
    if dmg <= 3000: return "!!"
    if dmg <= 5000: return "!!!"
    return "!!!!"


def _attack_info(dam_type):
    """Resolve display noun and damage class for a dam_type key (cf. 1stMud attack_table in const.c).
    [Verified: 02/07/2026] -- table entries match const.c exactly; DAM_NONE -> DAM_BASH
    mirrors 1stMud one_hit's "if (dam_type == -1) dam_type = DAM_BASH".

    Args:
        dam_type (str): Attack type name from area file (e.g. 'bite', 'divine').

    Returns:
        tuple: (noun (str), dam_class (int)).
    """
    noun, dc = ATTACK_TABLE.get(dam_type, ("hit", DAM_BASH))
    if dc == DAM_NONE:
        dc = DAM_BASH
    return noun, dc


def _ac_type_for_damage_class(dam_class):
    """Map damage class to 1stMud armor bucket. [PRIMESUD]"""
    if dam_class == DAM_PIERCE:
        return AC_PIERCE
    if dam_class == DAM_SLASH:
        return AC_SLASH
    if dam_class == DAM_BASH or dam_class == DAM_NONE:
        return AC_BASH
    return AC_EXOTIC


# -- Immunity check (cf. 1stMud check_immune in handler.c) ---------------------

def check_immune(ch, dam_type):
    """Determine immunity/resistance/vulnerability of ch to a damage class
    (cf. 1stMud check_immune in handler.c).
    [Verified: 02/07/2026]

    Two-pass check: first determine broad-category default (weapon or magic),
    then override with specific damage-type flag if present.

    Args:
        ch (dict): Victim (mob instance or player dict).
        dam_type (int): DAM_* damage class constant.

    Returns:
        int: One of IS_NORMAL, IS_IMMUNE, IS_RESISTANT, IS_VULNERABLE.
    """
    if dam_type == DAM_NONE:
        return IMMUNE_NONE

    # [not ported] 1stMud reads ch->imm_flags etc. directly; PrimeSUD stores
    # merged flags on mob instances (race defaults OR'd in at create_mobile).
    # Player imm/res/vuln flags will come from equipment affects when ported.
    imm  = ch["imm_flags"]
    res  = ch["res_flags"]
    vuln = ch["vuln_flags"]

    # -- Pass 1: broad category default (cf. 1stMud check_immune first switch)
    if dam_type in (DAM_BASH, DAM_PIERCE, DAM_SLASH):
        broad = "weapon"
    else:
        broad = "magic"

    if imm.get(broad):
        default = IS_IMMUNE
    elif res.get(broad):
        default = IS_RESISTANT
    elif vuln.get(broad):
        default = IS_VULNERABLE
    else:
        default = IS_NORMAL

    # -- Pass 2: specific damage-type flag (cf. 1stMud check_immune second switch)
    flag = DAM_TO_FLAG.get(dam_type)
    if flag is None:
        return default

    immune = IMMUNE_NONE
    if imm.get(flag):
        immune = IS_IMMUNE
    elif res.get(flag) and immune != IS_IMMUNE:
        immune = IS_RESISTANT
    elif vuln.get(flag):
        if immune == IS_IMMUNE:
            immune = IS_RESISTANT
        elif immune == IS_RESISTANT:
            immune = IS_NORMAL
        else:
            immune = IS_VULNERABLE

    if immune == IMMUNE_NONE:
        return default
    return immune


def update_mob_timers():
    """Bulk-decrement wait/daze for NPCs in current room (cf. 1stMud multi_hit NPC path).
    [PRIMESUD] per-pulse over the player's room instead of per-multi_hit-call;
    mobs in other rooms only tick when the player is present."""
    rs = world.rooms[world.chars[1]["room"]]
    for mid in rs["mobs"]:
        inst = world.chars[mid]
        inst["wait"] = max(0, inst.get("wait", 0) - PULSE_VIOLENCE)
        inst["daze"] = max(0, inst.get("daze", 0) - PULSE_VIOLENCE)


# -- Defensive checks ----------------------------------------------------------

def can_counter(ch):
    """True if ch's stance counters stance defences (cf. 1stMud can_counter in fight.c)."""
    return in_stance(ch, STANCE_MONKEY)


def can_bypass(ch, victim):
    """True if ch's stance bypasses stance defences (cf. 1stMud can_bypass in fight.c)."""
    return (in_stance(ch, STANCE_VIPER)
            or in_stance(ch, STANCE_MANTIS)
            or in_stance(ch, STANCE_TIGER))


def dambonus(ch, victim, dam, stance):
    """Stance damage modifiers for attacker and victim (cf. 1stMud dambonus in fight.c).

    Args:
        ch (dict): Attacker.
        victim (dict): Defender.
        dam (int): Damage so far.
        stance (int): ch's current stance id.

    Returns:
        int: Modified damage.
    """
    if dam < 1:
        return 0

    if not valid_stance(stance):
        return dam

    if not can_counter(victim):
        if in_stance(ch, STANCE_MONKEY):
            mindam = dam * 25 // 100
            dam *= (get_stance(ch, STANCE_MONKEY) + 1) // 200
            if dam < mindam:
                dam = mindam
        elif (in_stance(ch, STANCE_BULL)
                and get_stance(ch, STANCE_BULL) > 100):
            dam += dam * (get_stance(ch, STANCE_BULL) // 100)
        elif (in_stance(ch, STANCE_DRAGON)
                and get_stance(ch, STANCE_DRAGON) > 100):
            dam += dam * (get_stance(ch, STANCE_DRAGON) // 100)
        elif (in_stance(ch, STANCE_TIGER)
                and get_stance(ch, STANCE_TIGER) > 100):
            dam += dam * (get_stance(ch, STANCE_TIGER) // 100)
        elif (get_stance(ch, STANCE_CURRENT) > 0
                and get_stance(ch, stance) < 100):
            dam = dam * 5 // 10

    if not can_counter(ch):
        if (in_stance(victim, STANCE_CRAB)
                and get_stance(victim, STANCE_CRAB) > 100):
            dam //= get_stance(victim, STANCE_CRAB) // 100
        elif (in_stance(victim, STANCE_DRAGON)
                and get_stance(victim, STANCE_DRAGON) > 100):
            dam //= get_stance(victim, STANCE_DRAGON) // 100
        elif (in_stance(victim, STANCE_SWALLOW)
                and get_stance(victim, STANCE_SWALLOW) > 100):
            dam //= get_stance(victim, STANCE_SWALLOW) // 100

    return dam


_RIPOSTE_LINES = (
    ("You hang your blade over $N's stroke and return the point.",
     "$n hangs $s blade over $N's stroke and returns the point."),
    ("You lift $N's attack aside and answer in the same motion.",
     "$n lifts $N's attack aside and answers in the same motion."),
    ("Your wrist coils around $N's blade; your point springs free.",
     "$n's wrist coils around $N's blade; $s point springs free."),
    ("You press $N's sword down and cut across the opening.",
     "$n presses $N's sword down and cuts across the opening."),
)


def _wields_sword(ch):
    """Return whether ch's primary weapon is a sword. [PRIMESUD]"""
    return _get_weapon_sn(ch)[0] == GSN_SWORD


def _swordsman_dex_bonus(ch):
    """Return small capped DEX bonus for Swordsman skills. [PRIMESUD]"""
    return min(5, max(0, get_curr_stat(ch, "dex") - 13) // 2)


def _sword_act(lines, ch, victim):
    """Emit one random paired swordsman combat line. [PRIMESUD]"""
    actor, room = lines[randint(0, len(lines) - 1)]
    act(actor, ch, None, victim, TO_CHAR)
    act(room, ch, None, victim, TO_ROOM)


def _try_riposte(ch, victim):
    """Let victim answer one successful parry with a sword attack. [PRIMESUD]"""
    if (victim["is_npc"] or ch.get("_riposting")
            or get_skill(victim, GSN_RIPOSTE) <= 0
            or not _wields_sword(victim)):
        return
    chance = (get_skill(victim, GSN_RIPOSTE) // 4
              + _swordsman_dex_bonus(victim))
    if randint(1, 100) > chance:
        check_improve(victim, GSN_RIPOSTE, False, 4)
        return
    _sword_act(_RIPOSTE_LINES, victim, ch)
    victim["_riposting"] = True
    try:
        hit = one_hit(victim, ch)
    finally:
        victim.pop("_riposting", None)
    check_improve(victim, GSN_RIPOSTE, hit, 4)


def check_parry(ch, victim):
    """Check if victim parries ch's strike (cf. 1stMud check_parry in fight.c).
    [Verified: 03/07/2026] -- [PRIMESUD] riposte hook added.

    Args:
        ch (dict): Attacker (player or mob instance).
        victim (dict): Defender (player or mob instance).

    Returns:
        bool: True if the attack was parried.
    """
    if not is_awake(victim):
        return False

    if victim["is_npc"]:
        chance = get_skill(victim, GSN_PARRY, is_mob=True) // 2
    else:
        chance = get_skill(victim, GSN_PARRY) // 2

    if victim["equip"].get("wield") is None:
        if victim["is_npc"]:
            chance //= 2
        else:
            return False

    if not can_see(ch, victim):
        chance //= 2

    # Stance bonuses (cf. 1stMud check_parry fight.c:1539-1545)
    if (in_stance(victim, STANCE_CRANE)
            and get_stance(victim, STANCE_CRANE) > 0
            and not can_counter(ch) and not can_bypass(ch, victim)):
        chance += get_stance(victim, STANCE_CRANE) * 25 // 100
    elif (in_stance(victim, STANCE_MANTIS)
            and get_stance(victim, STANCE_MANTIS) > 0
            and not can_counter(ch) and not can_bypass(ch, victim)):
        chance += get_stance(victim, STANCE_MANTIS) * 25 // 100

    if randint(1, 100) >= chance + victim["level"] - ch["level"]:
        return False

    act("You parry $n's attack.", ch, None, victim, TO_VICT)
    act("$N parries your attack.", ch, None, victim, TO_CHAR)
    if not victim["is_npc"]:
        # 1stMud calls check_improve unconditionally; its IsNPC early-return is this gate
        check_improve(victim, GSN_PARRY, True, 6)
        _try_riposte(ch, victim)
    return True


def check_shield_block(ch, victim):
    """Check if victim blocks ch's strike with shield (cf. 1stMud check_shield_block in fight.c).
    [Verified: 02/07/2026]

    Args:
        ch (dict): Attacker (player or mob instance).
        victim (dict): Defender (player or mob instance).

    Returns:
        bool: True if the attack was blocked.
    """
    if not is_awake(victim):
        return False

    if victim["is_npc"]:
        chance = get_skill(victim, GSN_SHIELD_BLOCK, is_mob=True) // 5 + 3
    else:
        chance = get_skill(victim, GSN_SHIELD_BLOCK) // 5 + 3

    if victim["equip"].get("shield") is None:
        return False

    if randint(1, 100) >= chance + victim["level"] - ch["level"]:
        return False

    act("You block $n's attack with your shield.", ch, None, victim, TO_VICT)
    act("$N blocks your attack with a shield.", ch, None, victim, TO_CHAR)
    if not victim["is_npc"]:
        check_improve(victim, GSN_SHIELD_BLOCK, True, 6)
    return True


def check_dodge(ch, victim):
    """Check if victim dodges ch's strike (cf. 1stMud check_dodge in fight.c).
    [Verified: 03/07/2026]

    Args:
        ch (dict): Attacker (player or mob instance).
        victim (dict): Defender (player or mob instance).

    Returns:
        bool: True if the attack was dodged.
    """
    if not is_awake(victim):
        return False

    if victim["is_npc"]:
        chance = get_skill(victim, GSN_DODGE, is_mob=True) // 2
    else:
        chance = get_skill(victim, GSN_DODGE) // 2

    if not can_see(victim, ch):
        chance //= 2

    # Stance bonuses (cf. 1stMud check_dodge fight.c:1589-1596; both may stack
    # in 1stMud but current stance is single, so at most one applies)
    if (in_stance(victim, STANCE_MONGOOSE)
            and get_stance(victim, STANCE_MONGOOSE) > 0
            and not can_counter(ch) and not can_bypass(ch, victim)):
        chance += get_stance(victim, STANCE_MONGOOSE) * 25 // 100
    if (in_stance(victim, STANCE_SWALLOW)
            and get_stance(victim, STANCE_SWALLOW) > 0
            and not can_counter(ch) and not can_bypass(ch, victim)):
        chance += get_stance(victim, STANCE_SWALLOW) * 25 // 100

    if randint(1, 100) >= chance + victim["level"] - ch["level"]:
        return False

    act("You dodge $n's attack.", ch, None, victim, TO_VICT)
    act("$N dodges your attack.", ch, None, victim, TO_CHAR)
    if not victim["is_npc"]:
        check_improve(victim, GSN_DODGE, True, 6)
    return True


# -- Core damage resolution ----------------------------------------------------

def update_pos(ch):
    """Set ch's position from current HP
    (cf. 1stMud update_pos in fight.c).
    [Verified: 23/06/2026]

    Args:
        ch (dict): Character state dict.
    """
    hp = ch["hit"]

    if hp > 0:
        if POS_ORDER[ch["pos"]] <= POS_ORDER["stunned"]:
            ch["pos"] = "standing"
        return

    if ch["is_npc"] and hp < 1:
        ch["pos"] = "dead"
        return

    if hp <= -11:
        ch["pos"] = "dead"
    elif hp <= -6:
        ch["pos"] = "mortal"
    elif hp <= -3:
        ch["pos"] = "incap"
    else:
        ch["pos"] = "stunned"


def _randomize_damage(dam, roll):
    """Apply +/-50% variance to damage (cf. 1stMud randomize_damage in fight.c).
    [Verified: 02/07/2026]

    Args:
        dam (int): Pre-variance damage.
        roll (int): Random 1-100 value.

    Returns:
        int: Adjusted damage.
    """
    return dam * (roll + 50) // 100


def is_safe(ch, victim):
    """Check if ch is prevented from attacking victim (cf. 1stMud is_safe in fight.c).
    [Verified: 08/07/2026]
    -- PvP branches not ported (single-player, noted inline);
    "$g" deity rendered as "the gods".

    Returns True (and prints a message) if the attack should be blocked.
    Unlike is_safe_spell, this prints feedback explaining why.

    Args:
        ch (dict): Attacker (player or mob instance).
        victim (dict): Potential target.

    Returns:
        bool: True means target is protected -- abort the attack.
    """
    if victim.get("fighting") == ch.get("id") or victim is ch:
        return False

    # [PRIMESUD] immortal check skipped -- single-player, no immortals

    if victim["is_npc"]:
        # 1stMud: IsSet(victim->in_room->room_flags, ROOM_SAFE)
        if ROOM_DEFS.get(victim.get("room"), {}).get("flags", {}).get("safe"):
            chprintln(ch, "Not in this room.")
            return True

        if MOB_DEFS[victim["tpl"]].get("shop"):
            chprintln(ch, "The shopkeeper wouldn't like that.")
            return True

        act_f = victim["act_flags"]
        if (act_f.get("train") or act_f.get("practice")
                or act_f.get("healer") or act_f.get("changer")):
            # 1stmud: "I don't think $g would approve." -- $g = deity, not ported
            chprintln(ch, "I don't think the gods would approve.")
            return True

        if not ch["is_npc"]:
            if act_f.get("pet"):
                act("But $N looks so cute and cuddly...", ch, None, victim, TO_CHAR)
                return True

            if (victim["affected_by"].get("charm")
                    and ch.get("id") != victim.get("master")):
                chprintln(ch, "You don't own that monster.")
                return True

            # 1stMud: quest deliver/findmob target protected;
            # [PRIMESUD] vnum match instead of instance pointer
            if (ch.get("quest_status") in (QUEST_DELIVER, QUEST_FINDMOB)
                    and victim.get("tpl") == ch.get("quest_mob", 0)):
                # 1stMud: "You are supposed to deliver $p to $N, not kill $M."
                # [PRIMESUD] generic text; findmob quests carry no object
                act("You are supposed to find $N, not kill $M.",
                    ch, None, victim, TO_CHAR)
                return True
    else:
        # 1stMud: player victim
        if ch["is_npc"]:
            # 1stMud: IsSet(victim->in_room->room_flags, ROOM_SAFE)
            if ROOM_DEFS.get(victim.get("room"), {}).get("flags", {}).get("safe"):
                chprintln(ch, "Not in this room.")
                return True
            master = world.chars.get(ch["master"]) if ch.get("master") is not None else None
            if (ch["affected_by"].get("charm") and master is not None
                    and master.get("fighting") != victim.get("id")):
                chprintln(ch, "Players are your friends!")
                return True
        # [PRIMESUD] PvP checks skipped -- single-player
    return False


def is_safe_spell(ch, victim, area):
    """Silent safety check for spell targeting (cf. 1stMud is_safe_spell in fight.c).
    [Verified: 08/07/2026]
    -- immortal and PvP branches not ported (single-player, noted inline).

    Returns True if victim should NOT be hit. Unlike is_safe, prints no
    messages.

    Args:
        ch (dict): Caster.
        victim (dict): Potential target.
        area (bool): True for area-effect spells.

    Returns:
        bool: True means target is protected.
    """
    if victim is ch and area:
        return True
    if victim.get("fighting") == ch.get("id") or victim is ch:
        return False
    if victim["is_npc"]:
        # 1stMud: IsSet(victim->in_room->room_flags, ROOM_SAFE)
        if ROOM_DEFS.get(victim.get("room"), {}).get("flags", {}).get("safe"):
            return True
        if MOB_DEFS[victim["tpl"]].get("shop"):
            return True
        act = victim["act_flags"]
        if (act.get("train") or act.get("practice")
                or act.get("healer") or act.get("changer")):
            return True
        if not ch["is_npc"]:
            if act.get("pet"):
                return True
            if (victim["affected_by"].get("charm")
                    and (area or ch.get("id") != victim.get("master"))):
                return True
            # 1stMud: victim->fighting != NULL && !is_same_group(ch, victim->fighting)
            if (victim.get("fighting") is not None
                    and not is_same_group(ch, world.chars.get(victim["fighting"]))):
                return True
            # 1stMud: quest deliver/findmob target protected;
            # [PRIMESUD] vnum match instead of instance pointer
            if (ch.get("quest_status") in (QUEST_DELIVER, QUEST_FINDMOB)
                    and victim.get("tpl") == ch.get("quest_mob", 0)):
                return True
        else:
            # 1stMud: area && !is_same_group(victim, ch->fighting)
            if area and not is_same_group(victim, world.chars.get(ch.get("fighting"))):
                return True
    else:
        # 1stMud: player victim
        # [PRIMESUD] area immortal check skipped -- no immortals
        if ch["is_npc"]:
            master = world.chars.get(ch["master"]) if ch.get("master") is not None else None
            if (ch["affected_by"].get("charm") and master is not None
                    and master.get("fighting") != victim.get("id")):
                return True
            # 1stMud: IsSet(victim->in_room->room_flags, ROOM_SAFE)
            if ROOM_DEFS.get(victim.get("room"), {}).get("flags", {}).get("safe"):
                return True
            if (ch.get("fighting") is not None
                    and not is_same_group(world.chars.get(ch["fighting"]), victim)):
                return True
        # [PRIMESUD] PvP checks skipped -- single-player
    return False


def dam_message(ch, victim, dam, dt, immune, attack_noun=None):
    """Print damage message from ch's attack on victim (cf. 1stMud dam_message in fight.c).
    [Verified: 04/07/2026]
    -- MudFlag(DISABLE_AUTODAM) global tag kill-switch not ported (mud_info);
    bugf on out-of-range dt not ported (attack_noun is passed in, see below).

    Single-player: the player sees messages as attacker (TO_CHAR, ch=player),
    victim (TO_VICT, ch=mob), or onlooker (TO_NOTVICT -- or TO_ROOM for a
    self-hit -- when two mobs fight in the player's room).

    # [PRIMESUD] attack_noun passed explicitly; 1stMud resolves it internally via
    # attack_table[dt - TYPE_HIT].noun, but PrimeSUD uses string-keyed dam_type
    # (from area files) rather than integer offsets, so dt alone is insufficient.

    Args:
        ch (dict): Attacker (player or mob instance).
        victim (dict): Defender (player or mob instance).
        dam (int): Final damage dealt (0 = miss).
        dt (int): Damage type; dt >= TYPE_HIT means physical attack.
        immune (bool): True if victim was fully immune (dam forced to 0 by immunity).
        attack_noun (str or None): Attack display noun (e.g. "slash", "kick"); None = unarmed.
    """
    vs, vp = _damage_verb(dam)
    punct  = _damage_punct(dam)

    # cf. 1stMud SEE_DAMAGE(ch): damage tag only for player viewers with
    # PLR_AUTODAMAGE ("{x" otherwise); TO_CHAR line sees ch's flag, TO_VICT
    # line sees victim's flag
    tag = " {W[{R" + num_str(dam) + "{W]{x"
    tag_ch = tag if (not ch["is_npc"]
                     and ch.get("flags", PLR_DEFAULTS) & PLR_AUTODAMAGE) else "{x"
    tag_vict = tag if (not victim["is_npc"]
                       and victim.get("flags", PLR_DEFAULTS) & PLR_AUTODAMAGE) else "{x"

    # Observer (buf1) line. 1stMud sends it with a trailing "$t" and TO_DAMAGE
    # so each viewer's own PLR_AUTODAMAGE decides whether the tag renders
    # (comm.c:1868-1880); the only possible observer here is the solo player,
    # so the tag is resolved inline like tag_ch/tag_vict above ("" is what $t
    # renders to for a viewer without the flag).
    # [PRIMESUD] perf guard: build/send the line only when the player is
    # actually an onlooker -- mob-vs-mob fights tick world-wide, and act()'s
    # own routing would discard the line after we had paid to build it.
    player = world.chars.get(1)
    show_room = (player is not None and player is not ch and player is not victim
                 and player.get("room") == ch.get("room"))
    tag_room = ""
    if show_room and player.get("flags", PLR_DEFAULTS) & PLR_AUTODAMAGE:
        tag_room = tag

    # 1stMud dam_message: TO_CHAR goes to attacker, TO_VICT goes to defender,
    # TO_NOTVICT (TO_ROOM on a self-hit) to onlookers (cf. fight.c:2610-2696).
    # Routing replaces is_npc branching.
    # ch is victim is reachable: chain lightning grounding out through its own
    # caster (magic.py spell_lightning_bolt, cf. magic.c:1195).
    self_hit = ch is victim
    if attack_noun is None and not immune:
        # dt == TYPE_HIT: bare hit, no attack noun (misses included -- 1stMud
        # has no separate miss branch; dam 0 resolves to miss/misses verbs).
        # Observer line takes vp (plural verb), like the TO_VICT line.
        if self_hit:
            if show_room:
                # [PRIMESUD] 1stMud writes "$melf", which perform_act renders as
                # "$m" + literal "elf" ("himelf"); typo fixed to "$mself".
                act("{B$n " + vp + "{B $mself" + punct + tag_room, ch, None, None, TO_ROOM)
            act("{GYou " + vs + "{G yourself" + punct + tag_ch, ch, None, None, TO_CHAR)
        else:
            if show_room:
                act("{B$n " + vp + "{B $N" + punct + tag_room, ch, None, victim, TO_NOTVICT)
            act("{GYou " + vs + "{G $N" + punct + tag_ch, ch, None, victim, TO_CHAR)
            act("{R$n " + vp + "{R you" + punct + tag_vict, ch, None, victim, TO_VICT)
    else:
        # 1stMud: dt == TYPE_HIT under immunity resolves attack_table[0].noun = "hit"
        noun = attack_noun if attack_noun else "hit"
        if immune:
            if self_hit:
                if show_room:
                    act("{B$n is unaffected by $s own " + noun + ".{x", ch, None, None, TO_ROOM)
                act("{GLuckily, you are immune to that.{x", ch, None, None, TO_CHAR)
            else:
                if show_room:
                    act("{B$N is unaffected by $n's " + noun + "!{x", ch, None, victim, TO_NOTVICT)
                act("{G$N is unaffected by your " + noun + "!{x", ch, None, victim, TO_CHAR)
                act("{R$n's " + noun + " is powerless against you.{x", ch, None, victim, TO_VICT)
        else:
            if self_hit:
                if show_room:
                    # 1stMud uses "$m" (not the reflexive) here -- kept bug-faithful
                    act("{B$n's " + noun + " " + vp + "{B $m" + punct + tag_room, ch, None, None, TO_ROOM)
                act("{GYour " + noun + " " + vp + "{G you" + punct + tag_ch, ch, None, None, TO_CHAR)
            else:
                if show_room:
                    act("{B$n's " + noun + " " + vp + "{B $N" + punct + tag_room, ch, None, victim, TO_NOTVICT)
                act("{GYour " + noun + " " + vp + "{G $N" + punct + tag_ch, ch, None, victim, TO_CHAR)
                act("{R$n's " + noun + " " + vp + "{R you" + punct + tag_vict, ch, None, victim, TO_VICT)


def damage(ch, victim, dam, dt, dam_type, show, attack_noun=None):
    """Apply damage to victim from ch; handle combat state, immunity, and death
    (cf. 1stMud damage in fight.c).
    [Verified: 09/07/2026] -- force/static/flame shields, drunk reduction,
    arena/war, PvP, and wiznet not ported (noted inline);
    autoloot/autogold/autosac inlined instead of do_get/do_sacrifice
    dispatch; [PRIMESUD] owned-pet kills trigger the present owner's
    autoloot/autogold/autosac; randomize_damage applied (1stMud discards
    it -- see FIXES.md).

    dt >= TYPE_HIT = physical attack (dodge/parry checks apply).
    dt < TYPE_HIT  = skill/spell (no defensive checks).

    Args:
        ch (dict): Attacker (player or mob instance).
        victim (dict): Defender (player or mob instance).
        dam (int): Raw damage before soft-caps and modifiers.
        dt (int): Damage type ID; TYPE_HIT for weapon, skill sn for spells/skills.
        dam_type (int): DAM_* class for immunity checks.
        show (bool): Print dam_message if True (position messages always shown).
        attack_noun (str or None): [PRIMESUD] Attack display noun for dam_message.

    Returns:
        bool: True if damage applied (including kill); False on miss/dodge/parry/immune/dead.
    """
    if victim.get("pos") == "dead":
        return False

    # 1stmud: Anti-cheat check here
    if dam > 10000 and dt >= TYPE_HIT:
        dam = 10000

    # Damage soft caps
    if dam > 35:
        dam = (dam - 35) // 2 + 35
    if dam > 80:
        dam = (dam - 80) // 2 + 80

    # Global damage multipliers
    # [PRIMESUD] skip pcdam/mobdam multipliers (mud_info not ported)

    if victim is not ch:
        if is_safe(ch, victim):
            return False
        # [PRIMESUD] check_killer not ported -- pvp

        if POS_ORDER[victim["pos"]] > POS_ORDER["stunned"]:
            if victim["fighting"] is None:
                set_fighting(victim, ch)
                # TRIG_KILL: NPC victim joining combat reacts to attacker
                # (cf. fight.c:920); named "kill" upstream but fires on engage.
                if victim["is_npc"]:
                    from mobprog import has_trigger, kill_trigger  # deferred: keep mobprog off the boot path
                    if has_trigger(victim, "kill"):
                        kill_trigger(victim, ch)
            # 1stMud: if (victim->timer <= 4) victim->position = POS_FIGHTING;
            # [PRIMESUD] timer is connection idle counter -- always 0 in single-player, so always true
            victim["pos"] = "fighting"

        # 1stMud: if (victim->position > POS_STUNNED) {
        #             if (ch->fighting == NULL) set_fighting(ch, victim); }
        if POS_ORDER[victim["pos"]] > POS_ORDER["stunned"]:
            if ch["fighting"] is None:
                set_fighting(ch, victim)

        # 1stMud: if (victim->master == ch) stop_follower(victim);
        if victim.get("master") == ch.get("id"):
            stop_follower(victim)

    # 1stMud: if (IsAffected(ch, AFF_INVISIBLE)) { affect_strip invis + mass invis;
    #             RemBit(AFF_INVISIBLE); act("$n fades into existence.", TO_ROOM); }
    if ch["affected_by"].get("invisible"):
        for _sn, _sk in SKILL_TABLE:
            if _sk["name"] == "invis" or _sk["name"] == "mass invis":
                affect_strip(ch, _sn)
        ch["affected_by"].pop("invisible", None)
        act("$n fades into existence.", ch, type=TO_ROOM)

    # 1stMud: if (dam > 1 && !IsNPC(victim) && victim->pcdata->condition[COND_DRUNK] > 10)
    #             dam = 9 * dam / 10;
    # [PRIMESUD] skip drunk damage reduction (condition system not ported)

    # 1stMud: if (dam > 1 && IsAffected(victim, AFF_SANCTUARY)) dam /= 2;
    if dam > 1 and victim["affected_by"].get("sanctuary"):
        dam //= 2

    # 1stMud: if (dam > 1 && ((IsAffected(victim, AFF_PROTECT_EVIL) && IsEvil(ch))
    #             || (IsAffected(victim, AFF_PROTECT_GOOD) && IsGood(ch)))) dam -= dam / 4;
    if dam > 1:
        v_aff = victim["affected_by"]
        if ((v_aff.get("protect_evil") and is_evil(ch))
                or (v_aff.get("protect_good") and is_good(ch))):
            dam -= dam // 4

    # 1stMud: if (mud_info.bonus.status == BONUS_DAM) dam *= mud_info.bonus.mod;
    # [PRIMESUD] skip bonus damage event (not ported)

    # 1stMud: if (dt >= TYPE_HIT && ch != victim) { check_dodge; check_parry; check_shield_block; ... }
    immune = False
    if dt >= TYPE_HIT and ch is not victim:
        # 1stMud: if (check_dodge(ch, victim)) return false;
        if check_dodge(ch, victim):
            return False
        # Stance second dodge chance (cf. 1stMud damage fight.c:967-975)
        if (in_stance(victim, STANCE_MONGOOSE)
                and get_stance(victim, STANCE_MONGOOSE) > 100
                and not can_counter(ch) and not can_bypass(ch, victim)
                and check_dodge(ch, victim)):
            return False
        elif (in_stance(victim, STANCE_SWALLOW)
                and get_stance(victim, STANCE_SWALLOW) > 100
                and not can_counter(ch) and not can_bypass(ch, victim)
                and check_dodge(ch, victim)):
            return False
        # 1stMud: if (check_parry(ch, victim)) return false;
        if check_parry(ch, victim):
            return False
        # Stance second parry chance (cf. 1stMud damage fight.c:978-985)
        if (in_stance(victim, STANCE_CRANE)
                and get_stance(victim, STANCE_CRANE) > 100
                and not can_counter(ch) and not can_bypass(ch, victim)
                and check_parry(ch, victim)):
            return False
        elif (in_stance(victim, STANCE_MANTIS)
                and get_stance(victim, STANCE_MANTIS) > 100
                and not can_counter(ch) and not can_bypass(ch, victim)
                and check_parry(ch, victim)):
            return False
        # 1stMud: if (check_shield_block(ch, victim)) return false;
        if check_shield_block(ch, victim):
            return False
        # 1stMud: if (IsAffected(victim,AFF_FORCE_SHIELD) && check_force_shield(...)) return false;
        # 1stMud: if (IsAffected(victim,AFF_STATIC_SHIELD) && check_static_shield(...)) return false;
        # [PRIMESUD] skip force/static shields (not ported)

    # 1stMud: if (IsAffected(victim, AFF_FLAME_SHIELD) && dam_type <= 3) check_flame_shield(ch, victim);
    # [PRIMESUD] skip flame_shield (not ported)

    # 1stMud: switch (check_immune(victim, dam_type)) {
    #             case IS_IMMUNE:    immune=true; dam=0; break;
    #             case IS_RESISTANT: dam -= dam/3; break;
    #             case IS_VULNERABLE: dam += dam/2; break; }
    imm_result = check_immune(victim, dam_type)
    if imm_result == IS_IMMUNE:
        immune = True
        dam = 0
    elif imm_result == IS_RESISTANT:
        dam -= dam // 3
    elif imm_result == IS_VULNERABLE:
        dam += dam // 2

    # 1stMud: randomize_damage(ch, dam, dice(1,100));
    # [PRIMESUD] 1stMud discards return value (bug); we apply it. See FIXES.md.
    dam = _randomize_damage(dam, randint(1, 100))

    # 1stMud: if (show) dam_message(ch, victim, dam, dt, immune);
    if show:
        # [PRIMESUD] Auto-resolve attack_noun from skill table for spells.
        # 1stMud does this inside dam_message via skill_table[dt].noun_damage,
        # but we pass it explicitly because PrimeSUD uses string-keyed dam_type.
        if attack_noun is None and dt < TYPE_HIT and dt in SKILLS:
            sk = SKILLS[dt]
            attack_noun = sk.get("noun_damage") or sk["name"]
        dam_message(ch, victim, dam, dt, immune, attack_noun)

    # 1stMud: if (dam == 0) return false;
    if dam == 0:
        return False

    # 1stMud: victim->hit -= dam;
    victim["hit"] -= dam

    # 1stMud: if (!IsNPC(victim) && victim->level >= LEVEL_IMMORTAL && victim->hit < 1)
    #             victim->hit = 1;
    # [PRIMESUD] skip immortal HP floor (no immortal players)

    # 1stMud: update_pos(victim);
    update_pos(victim)

    # 1stMud: switch (victim->position) { case POS_MORTAL: ... case POS_DEAD: ... default: ... }
    # pos captured before stop_fighting (called below) can reset it to "standing".
    pos = victim.get("pos", "standing")

    if pos == "mortal":
        act("$n is mortally wounded, and will die soon, if not aided.", victim, type=TO_ROOM)
        if not victim["is_npc"]:
            chprintln(victim, "You are mortally wounded, and will die soon, if not aided.")
    elif pos == "incap":
        act("$n is incapacitated and will slowly die, if not aided.", victim, type=TO_ROOM)
        if not victim["is_npc"]:
            chprintln(victim, "You are incapacitated and will slowly die, if not aided.")
    elif pos == "stunned":
        act("$n is stunned, but will probably recover.", victim, type=TO_ROOM)
        if not victim["is_npc"]:
            chprintln(victim, "You are stunned, but will probably recover.")
    elif pos == "dead":
        act("$n is DEAD!!", victim, type=TO_ROOM)
        # [PRIMESUD] player death message printed by game loop (primesud.py) to avoid duplicate
    else:
        # 1stMud: default:
        #   if (dam > victim->max_hit/4) chprintln(victim, "That really did HURT!")
        #   if (victim->hit < victim->max_hit/4) chprintln(victim, "You sure are BLEEDING!")
        if not victim["is_npc"]:
            max_hit = victim.get("max_hit", 1)
            if dam > max_hit // 4:
                chprintln(victim, "That really did HURT!")
            if victim["hit"] < max_hit // 4:
                chprintln(victim, "You sure are BLEEDING!")

    # 1stMud: if (!IsAwake(victim)) stop_fighting(victim, false);
    if not is_awake(victim):
        stop_fighting(victim, both=False)

    # 1stMud: if (victim->position == POS_DEAD) { ... raw_kill(victim, ch) ... }
    if pos == "dead":
        # 1stMud: if (IS_IN_ARENA...) check_arena; if (InWar...) check_war;
        # [PRIMESUD] skip arena and war (not ported)

        # 1stMud: group_gain(ch, victim)
        group_gain(ch, victim)

        # 1stMud: if (!IsNPC(victim)) { logf(...); if (!IsQuester...)
        #             gain_exp(victim, 2*(exp_per_level*level - exp)/3 + 50); }
        # [PRIMESUD] per-level XP model: level floor is xp == 0, so the
        # penalty is -2/3 of progress into the current level, +50.
        # C division truncates toward zero.
        # 1stMud: no XP penalty when a quester dies to their own quest mob;
        # [PRIMESUD] vnum match instead of instance pointer
        if (not victim["is_npc"] and victim.get("xp", 0) > 0
                and not (is_quester(victim)
                         and ch.get("tpl") == victim.get("quest_mob", 0))):
            gain_exp(victim, 50 - (2 * victim["xp"]) // 3)

        # 1stMud: new_wiznet / announce
        # [PRIMESUD] skip wiznet/announce (not ported)

        # TRIG_DEATH: NPC victim's death prog runs before extraction, restored
        # to standing so it can act (cf. fight.c:1141)
        if victim["is_npc"]:
            from mobprog import has_trigger, death_trigger  # deferred: keep mobprog off the boot path
            if has_trigger(victim, "death"):
                death_trigger(victim, ch)

        # 1stMud: update_death(victim, ch)
        update_death(victim, ch)

        # 1stMud: raw_kill(victim, ch)
        corpse = raw_kill(victim, ch)

        if victim.get("is_npc"):
            _advance_target(ch, world.chars, world.rooms)

        # 1stMud: if (ch != victim && !IsNPC(ch) && ...) outlaw flag removal
        # [PRIMESUD] skip outlaw flag removal (not ported)

        # 1stMud: if (!IsNPC(ch) && (corpse = get_obj_list...) ... autoloot/autogold/autosac
        # [PRIMESUD] use corpse returned by raw_kill instead of searching by
        # name -- 1stMud searches and gets oldest corpse when multiples exist.
        # [PRIMESUD] an owned pet's kill uses its present owner's auto flags
        # (autoloot/autogold/autosac, each only if set); generic charmies and
        # remote owners remain NPC kills.
        auto_ch = ch
        if ch.get("is_npc"):
            owner = world.chars.get(ch.get("master"))
            if (owner is not None and owner.get("pet") == ch.get("id")
                    and owner.get("room") == ch.get("room")
                    and owner.get("flags", PLR_DEFAULTS)
                    & (PLR_AUTOLOOT | PLR_AUTOGOLD | PLR_AUTOSAC)):
                auto_ch = owner

        if not auto_ch.get("is_npc"):
            flags = auto_ch.get("flags", PLR_DEFAULTS)
            if (corpse is not None and isinstance(corpse, dict)
                    and item_tpl(corpse).get("type") == "npc_corpse"):
                contents = corpse.get("contents", [])

                # 1stMud: if (PLR_AUTOLOOT && corpse->content_first) do_get("all corpse")
                if flags & PLR_AUTOLOOT and contents:
                    for cobj in list(contents):
                        ctpl = item_tpl(cobj)
                        obj_remove(corpse["contents"], cobj)
                        chprintln(auto_ch, "You get " + (cobj.get("short_descr") or ctpl["short_descr"]) + ".")
                        if not apply_money_pickup(auto_ch, cobj, ctpl):
                            auto_ch["inv"].append(cobj)

                # 1stMud: if (PLR_AUTOGOLD && content_first && !PLR_AUTOLOOT) get gold only
                if (flags & PLR_AUTOGOLD and corpse.get("contents")
                        and not (flags & PLR_AUTOLOOT)):
                    for cobj in list(corpse["contents"]):
                        ctpl = item_tpl(cobj)
                        if _item_type(cobj, ctpl) == "money":
                            obj_remove(corpse["contents"], cobj)
                            chprintln(auto_ch, "You get " + (cobj.get("short_descr") or ctpl["short_descr"]) + ".")
                            apply_money_pickup(auto_ch, cobj, ctpl)

                # 1stMud: if (PLR_AUTOSAC) { if (autoloot && still has contents) skip; else sacrifice }
                if flags & PLR_AUTOSAC:
                    if flags & PLR_AUTOLOOT and corpse.get("contents"):
                        pass
                    else:
                        silver = max(1, corpse.get("level", 0) * 3)
                        if silver == 1:
                            chprintln(auto_ch, "Your deity gives you one silver coin for your sacrifice.")
                        else:
                            chprintln(auto_ch, "Your deity gives you " + num_str(silver) + " silver coins for your sacrifice.")
                        auto_ch["silver"] = auto_ch.get("silver", 0) + silver
                        short = corpse.get("short_descr", "a corpse")
                        chprintln(auto_ch, "You sacrifice " + short + " to your deity.")
                        obj_remove(world.rooms[auto_ch["room"]]["items"], corpse)

        return True

    # 1stMud: if (victim == ch) return true;
    if victim is ch:
        return True

    # 1stMud: if (!IsNPC(victim) && victim->desc == NULL) { ... perform_recall ... }
    # [PRIMESUD] skip linkdead recall (no multiplayer)

    # 1stMud: if (IsNPC(victim) && dam > 0 && victim->wait < PULSE_VIOLENCE/2) {
    #             if (ACT_WIMPY && number_bits(2)==0 && hit < max_hit/5) do_flee;
    #             elif (AFF_CHARM && master && master->in_room != victim->in_room) do_flee; }
    if victim["is_npc"] and dam > 0 and victim.get("wait", 0) < PULSE_VIOLENCE // 2:
        act_flags = victim["act_flags"]
        master = world.chars.get(victim["master"]) if victim.get("master") is not None else None
        if ((act_flags.get("wimpy") and randint(0, 3) == 0
                and victim["hit"] < victim.get("max_hit", 1) // 5)
                or (victim["affected_by"].get("charm") and master is not None
                    and master.get("room") != victim.get("room"))):
            do_flee(victim, [])

    # 1stMud: player wimpy auto-flee
    if (not victim.get("is_npc") and victim["hit"] > 0
            and victim["hit"] <= victim.get("wimpy", 0)
            and victim.get("wait", 0) < PULSE_VIOLENCE // 2):
        do_flee(victim, [])

    # 1stMud: tail_chain();
    # [PRIMESUD] skip tail_chain (event queue not ported)

    return True


# -- Core attack: one_hit ------------------------------------------------------

def one_hit(ch, victim, dt=TYPE_UNDEFINED, bonus_damroll=0, secondary=False,
            accuracy_bonus=0, damage_percent=100):
    """One attack from ch against victim (cf. 1stMud one_hit in fight.c).
    [Verified: 01/08/2026] -- old-format mob damage fallback skipped.

    Args:
        ch (dict): Attacker (player or mob instance).
        victim (dict): Defender (player or mob instance).
        dt (int): Damage type; TYPE_UNDEFINED = resolve from weapon/mob,
            skill GSN (e.g. GSN_BACKSTAB) = skill-driven attack.
        bonus_damroll (int): Extra damage roll bonus (e.g. from skills).
        secondary (bool): True = secondary weapon (cf. 1stMud bool secondary).
        accuracy_bonus (int): [PRIMESUD] THAC0 points subtracted for this hit.
        damage_percent (int): [PRIMESUD] Final pre-cap damage multiplier.

    Returns:
        bool: True if damage was applied.
    """
    # 1stMud: if (victim == ch || ch == NULL || victim == NULL) return;
    #         if (victim->position == POS_DEAD || ch->in_room != victim->in_room) return;
    if victim is ch or victim.get("pos") == "dead" or ch.get("room") != victim.get("room"):
        return False

    # Weapon / skill (cf. 1stMud one_hit: skill = 20 + get_weapon_skill, fight.c)
    slot = "secondary" if secondary else "wield"
    if secondary and ch["equip"].get(slot) is None:
        return False
    sk_vnum, wtpl = _get_weapon_sn(ch, slot)
    skill = 20 + _get_weapon_skill(ch, sk_vnum)

    # THAC0
    thac0 = get_thac0(ch)
    thac0 -= get_hitroll(ch) * skill // 100
    thac0 += 5 * (100 - skill) // 100
    thac0 -= accuracy_bonus

    # Backstab THAC0 bonus (cf. 1stMud one_hit fight.c:654-655)
    if dt == GSN_BACKSTAB:
        thac0 -= 10 * (100 - get_skill(ch, GSN_BACKSTAB, ch["is_npc"]))

    # Attack noun and damage class
    if ch["is_npc"]:
        ch_tpl   = MOB_DEFS[ch["tpl"]]
        dam_type = ch_tpl.get("dam_type", "none")
    else:
        dam_type = wtpl["dam_type"] if wtpl is not None else "none"
        ch_tpl   = None
    attack_noun, dam_class = _attack_info(dam_type)
    # Skill-driven attack: override noun from skill table (cf. 1stMud dt < TYPE_HIT branch)
    if dt != TYPE_UNDEFINED and dt < TYPE_HIT:
        noun = SKILLS[dt]["noun_damage"]
    else:
        # None = unarmed (no noun in dam_message); mirrors 1stMud !armed display branch
        noun = None if dam_type == "none" else attack_noun
    victim_ac = get_armor(victim, _ac_type_for_damage_class(dam_class)) // 10
    if victim_ac < -15:  # soft cap (cf. 1stMud one_hit fight.c)
        victim_ac = -((-victim_ac - 15) // 5) - 15

    # 1stMud: if (!can_see(ch, victim)) victim_ac -= 4;
    if not can_see(ch, victim):
        victim_ac -= 4
    # 1stMud: if (victim->position < POS_FIGHTING) victim_ac += 4;
    #         if (victim->position < POS_RESTING)  victim_ac += 6;
    vpos = POS_ORDER[victim["pos"]]
    if vpos < POS_ORDER["fighting"]:
        victim_ac += 4
    if vpos < POS_ORDER["resting"]:
        victim_ac += 6

    # 1stMud: if (diceroll == 0 || (diceroll != 19 && diceroll < thac0 - victim_ac))
    #             { damage(ch, victim, 0, dt, dam_type, true); return; }
    # Resolve dt for damage() calls: skill GSN stays as-is, otherwise TYPE_HIT
    effective_dt = dt if (dt != TYPE_UNDEFINED and dt < TYPE_HIT) else TYPE_HIT
    roll = randint(0, 19)
    if roll == 0 or (roll != 19 and roll < thac0 - victim_ac):
        damage(ch, victim, 0, effective_dt, dam_class, show=True, attack_noun=noun)
        improve_stance(ch)  # cf. 1stMud one_hit fight.c:692 (miss path only)
        return False

    # Damage calculation (cf. 1stMud one_hit fight.c:697-735 -- armed NPCs use
    # weapon dice like players; only unarmed NPCs use mob damage dice)
    if ch["is_npc"] and wtpl is None:
        num, size, _ = ch_tpl["damage"]
        dam = dice(num, size)
    else:
        # 1stMud improves the weapon skill here, before damage() resolves
        # dodge/parry -- landing the swing is enough
        if not ch["is_npc"] and sk_vnum != -1:
            check_improve(ch, sk_vnum, True, 5)
        if wtpl is not None:
            # 1stMud reads instance values (fight.c:714 wield->value[1]/[2]);
            # instance "dice" carries quest-gear scaling (cf. quest.c 253-256)
            wobj = ch["equip"][slot]
            num, size, bonus = wobj.get("dice") or wtpl.get("dice", (1, 4, 0))
            dam = (dice(num, size) + bonus) * skill // 100
            # 1stMud: if (get_eq_char(ch, WEAR_SHIELD) == NULL) dam = dam * 11 / 10;
            if ch["equip"].get("shield") is None:
                dam = dam * 11 // 10
            # 1stMud: WEAPON_SHARP double-damage proc (fight.c:723-729)
            if item_weapon_flags(wobj, wtpl).get("sharp"):
                percent = randint(1, 100)
                if percent <= skill // 8:
                    dam = 2 * dam + (dam * 2 * percent // 100)
        else:
            # Unarmed (cf. 1stMud: number_range(1 + 4*skill/100, 2*ch->level/3 * skill/100);
            # C divides by 3 before multiplying by skill)
            lo = 1 + 4 * skill // 100
            hi = max(lo, (2 * ch["level"] // 3) * skill // 100)
            dam = randint(lo, hi)

    # Stance damage modifiers (cf. 1stMud one_hit fight.c:737-745)
    if in_stance(ch, STANCE_NORMAL):
        if ch["is_npc"]:
            dam = dam * 113 // 100
        else:
            dam = dam * 115 // 100
    else:
        dam = dambonus(ch, victim, dam, get_stance(ch, STANCE_CURRENT))

    # 1stMud: enhanced damage skill chance (improves on success)
    ed_skill = get_skill(ch, GSN_ENHANCED_DAMAGE, ch["is_npc"])
    if ed_skill > 0:
        diceroll = randint(1, 100)
        if diceroll <= ed_skill:
            if not ch["is_npc"]:
                check_improve(ch, GSN_ENHANCED_DAMAGE, True, 6)
            dam += 2 * (dam * diceroll // 300)

    # Position bonus: sleeping victim takes double, non-fighting victim takes 1.5x (cf. 1stMud one_hit in fight.c)
    vpos = POS_ORDER[victim["pos"]]
    if not is_awake(victim):
        dam *= 2
    elif vpos < POS_ORDER["fighting"]:
        dam = dam * 3 // 2

    # Backstab damage multiplier (cf. 1stMud one_hit fight.c:762-768)
    if dt == GSN_BACKSTAB and wtpl is not None:
        if wtpl.get("weapon_type") != "dagger":
            dam *= 2 + ch["level"] // 10
        else:
            dam *= 2 + ch["level"] // 8

    dam += (get_damroll(ch) + bonus_damroll) * min(100, skill) // 100
    dam = dam * damage_percent // 100
    dam = max(1, dam)

    # 1stMud: return damage(ch, victim, dam, dt, dam_type, true);
    # Soft caps, immunity, dodge/parry all handled inside damage().
    hit = damage(ch, victim, dam, effective_dt, dam_class, show=True, attack_noun=noun)

    # 1stMud: weapon flag procs run here (fight.c:777-861); each proc
    # re-checks ch->fighting == victim so a kill mid-chain stops the rest
    if hit and wtpl is not None:
        _weapon_procs(ch, victim, ch["equip"][slot], wtpl)

    return hit


def _weapon_procs(ch, victim, wobj, wtpl):
    """Post-hit weapon flag procs (cf. 1stMud one_hit in fight.c:777-861).
    [Verified: 04/07/2026]

    Args:
        ch (dict): Attacker wielding the weapon.
        victim (dict): Defender.
        wobj (dict): Weapon instance.
        wtpl (dict): Weapon template.
    """
    from magic import saves_spell  # late import: magic imports combat
    wf = item_weapon_flags(wobj, wtpl)
    wlevel = wobj.get("level", wtpl.get("level", 0))
    vid = victim["id"]

    if ch["fighting"] == vid and wf.get("poison"):
        poison = item_affect_find(wobj, GSN_POISON)
        level = poison.get("level", wlevel) if poison else wlevel
        if not saves_spell(level // 2, victim, DAM_POISON):
            chprintln(victim, "You feel poison coursing through your veins.")
            act("$n is poisoned by the venom on $p.", victim, wobj, None, TO_ROOM)
            affect_join(victim, {
                "where": "to_affects", "type": GSN_POISON,
                "level": level * 3 // 4, "duration": level // 2,
                "location": "str", "modifier": -1, "bitvector": "poison",
            })
        if poison is not None:
            poison["level"] = max(0, poison.get("level", 0) - 2)
            poison["duration"] = max(0, poison.get("duration", 0) - 1)
            # 1stMud only prints here; the affect itself expires (and the
            # weapon flag clears) in the obj update tick at duration 0
            if poison["level"] == 0 or poison["duration"] == 0:
                act("The poison on $p has worn off.", ch, wobj, None, TO_CHAR)

    if ch["fighting"] == vid and wf.get("vampiric"):
        pdam = randint(1, wlevel // 5 + 1)
        act("$p draws life from $n.", victim, wobj, None, TO_ROOM)
        act("You feel $p drawing your life away.", victim, wobj, None, TO_CHAR)
        damage(ch, victim, pdam, 0, DAM_NEGATIVE, show=False)
        ch["alignment"] = max(-1000, ch.get("alignment", 0) - 1)
        ch["hit"] += pdam // 2

    if ch["fighting"] == vid and wf.get("flaming"):
        pdam = randint(1, wlevel // 4 + 1)
        act("$n is burned by $p.", victim, wobj, None, TO_ROOM)
        act("$p sears your flesh.", victim, wobj, None, TO_CHAR)
        fire_effect(victim, wlevel // 2, pdam, TARGET_CHAR)
        damage(ch, victim, pdam, 0, DAM_FIRE, show=False)

    if ch["fighting"] == vid and wf.get("frost"):
        pdam = randint(1, wlevel // 6 + 2)
        act("$p freezes $n.", victim, wobj, None, TO_ROOM)
        act("The cold touch of $p surrounds you with ice.", victim, wobj, None, TO_CHAR)
        cold_effect(victim, wlevel // 2, pdam, TARGET_CHAR)
        damage(ch, victim, pdam, 0, DAM_COLD, show=False)

    if ch["fighting"] == vid and wf.get("shocking"):
        pdam = randint(1, wlevel // 5 + 2)
        act("$n is struck by lightning from $p.", victim, wobj, None, TO_ROOM)
        act("You are shocked by $p.", victim, wobj, None, TO_CHAR)
        shock_effect(victim, wlevel // 2, pdam, TARGET_CHAR)
        damage(ch, victim, pdam, 0, DAM_LIGHTNING, show=False)


_FLOWING_FORM_LINES = (
    ("You yield a step, drawing the point of your sword back along $N's guard.",
     "$n yields a step, drawing the point of $s sword back along $N's guard."),
    ("Your wrist turns softly; the edge rises through $N's opening.",
     "$n's wrist turns softly; the edge rises through $N's opening."),
    ("You gather your sword at your centre, then unfold into a cut.",
     "$n gathers $s sword at $s centre, then unfolds into a cut."),
    ("The point of your sword traces a small circle and slips toward $N.",
     "The point of $n's sword traces a small circle and slips toward $N."),
)

_DRIVING_FORM_LINES = (
    ("You drive from the waist and thrust straight at $N.",
     "$n drives from the waist and thrusts straight at $N."),
    ("Your sword falls in a clean, upright cleave at $N.",
     "$n's sword falls in a clean, upright cleave at $N."),
    ("Your wrist snaps, hurling the point beneath $N's guard.",
     "$n's wrist snaps, hurling the point beneath $N's guard."),
    ("You turn through a level sweep, blade tearing toward $N.",
     "$n turns through a level sweep, blade tearing toward $N."),
)

_FLOWING_FLOURISHES = (
    ("You yield half a step, your sword returning to your centre.",
     "$n yields half a step, $s sword returning to $s centre."),
    ("Your loose wrist guides the point of your sword through a quiet circle.",
     "$n's loose wrist guides the point of $s sword through a quiet circle."),
    ("Your blade moves with your body in one unbroken arc.",
     "$n's blade moves with $s body in one unbroken arc."),
    ("You gather your sword close, then let it drift outward.",
     "$n gathers $s sword close, then lets it drift outward."),
)

_DRIVING_FLOURISHES = (
    ("You crowd $N's guard with short, sharp cuts.",
     "$n crowds $N's guard with short, sharp cuts."),
    ("The point of your sword snaps from one line to the next.",
     "The point of $n's sword snaps from one line to the next."),
    ("You step in behind the blade, pressing $N hard.",
     "$n steps in behind the blade, pressing $N hard."),
    ("You turn from the waist and drive your sword through a heavy cut.",
     "$n turns from the waist and drives $s sword through a heavy cut."),
)


def _do_sword_form(ch, sn, form, lines, accuracy_bonus, damage_percent):
    """Perform one active Swordsman form attack. [PRIMESUD]"""
    skill = get_skill(ch, sn)
    if skill <= 0:
        chprintln(ch, "You do not know that form.")
        return None
    target_id = ch.get("fighting")
    if target_id is None:
        chprintln(ch, "You aren't fighting anyone.")
        return None
    if not _wields_sword(ch):
        chprintln(ch, "You must wield a sword to use that form.")
        return None

    skill = min(100, skill + _swordsman_dex_bonus(ch))
    target = world.chars[target_id]
    ch["_sword_form"] = form
    WaitState(ch, SKILLS[sn]["beats"])
    _sword_act(lines, ch, target)
    if randint(1, 100) < skill:
        hit = one_hit(ch, target, accuracy_bonus=accuracy_bonus,
                      damage_percent=damage_percent)
        check_improve(ch, sn, hit, 2)
    else:
        damage(ch, target, 0, sn, DAM_SLASH, show=True,
               attack_noun=SKILLS[sn]["noun_damage"])
        check_improve(ch, sn, False, 2)
    return None


def do_flow(ch, args):
    """Use flowing form for one precise sword attack. [PRIMESUD]"""
    return _do_sword_form(ch, GSN_FLOWING_FORM, "flowing",
                          _FLOWING_FORM_LINES, 4, 90)


def do_drive(ch, args):
    """Use driving form for one committed sword attack. [PRIMESUD]"""
    return _do_sword_form(ch, GSN_DRIVING_FORM, "driving",
                          _DRIVING_FORM_LINES, 0, 140)


def _sword_flourish(ch, victim):
    """Sometimes show a cosmetic line matching ch's active form. [PRIMESUD]"""
    if (ch["is_npc"] or not classes.is_class(ch, classes.CLASS_SWORDSMAN)
            or not _wields_sword(ch) or randint(1, 8) != 1):
        return
    lines = (_DRIVING_FLOURISHES if ch.get("_sword_form") == "driving"
             else _FLOWING_FLOURISHES)
    _sword_act(lines, ch, victim)


def do_kick(ch, args):
    """Kick for player or mob (cf. 1stMud do_kick in fight.c).
    [Verified: 04/07/2026] -- check_killer not ported.

    Args:
        ch (dict): Acting character (player or mob instance).
        args (list): Command arguments (unused).
    """
    # 1stMud: !IsNPC && !can_use_skpell -> message; IsNPC && !OFF_KICK -> silent return
    if not ch["is_npc"] and not classes.can_use_skill_spell(ch, GSN_KICK):
        chprintln(ch, "You better leave the martial arts to fighters.")
        return None
    if ch["is_npc"] and not ch["off_flags"].get("kick"):
        return None

    target_id = ch["fighting"]
    if target_id is None:
        chprintln(ch, "You aren't fighting anyone.")
        return None
    target = world.chars[target_id]

    skill_pct = get_skill(ch, GSN_KICK, ch["is_npc"])
    WaitState(ch, SKILLS[GSN_KICK]["beats"])

    if skill_pct > randint(1, 100):
        dam = randint(1, max(1, ch["level"]))
        # 1stMud: damage(ch, victim, dam, gsn_kick, DAM_BASH, true)
        damage(ch, target, dam, GSN_KICK, DAM_BASH, show=True, attack_noun="kick")
        if not ch["is_npc"]:
            check_improve(ch, GSN_KICK, True, 1)
    else:
        # 1stMud: damage(ch, victim, 0, gsn_kick, DAM_BASH, true)
        damage(ch, target, 0, GSN_KICK, DAM_BASH, show=True, attack_noun="kick")
        if not ch["is_npc"]:
            check_improve(ch, GSN_KICK, False, 1)
    return None


def do_backstab(ch, args, victim=None):
    """Backstab a target from behind (cf. 1stMud do_backstab in fight.c).
    [Verified: 19/07/2026]
    -- check_killer not ported.

    Args:
        ch (dict): Acting character (player or mob instance).
        args (list): Command arguments -- target keyword.  Ignored when
            `victim` is given.
        victim (dict, optional): Pre-resolved target. [PRIMESUD] 1stMud
            resolves the target by name via a room person list that holds
            both players and NPCs; our `get_char_room` only searches NPC
            instances (players aren't modeled as mob instances), so callers
            that already know the target -- e.g. a mob attacking the player
            in special.py -- pass it directly instead of a name fragment.
    """
    # [PRIMESUD] explicit gate; 1stMud lets it through but get_skill returns 0 -> guaranteed miss + lag
    if not ch["is_npc"] and GSN_BACKSTAB not in ch["learned"]:
        chprintln(ch, "You don't know how to backstab.")
        return None

    if victim is None and not args:
        chprintln(ch, "Backstab whom?")
        return None

    if ch["fighting"] is not None:
        chprintln(ch, "You're facing the wrong end.")
        return None

    if victim is None:
        rs = world.rooms[ch["room"]]
        target_id = get_char_room(" ".join(args), rs["mobs"], world.chars, ch)
        if target_id is None:
            chprintln(ch, "They aren't here.")
            return None
        victim = world.chars[target_id]

    if victim is ch:
        chprintln(ch, "How can you sneak up on yourself?")
        return None

    if is_safe(ch, victim):
        return None

    # 1stMud: IsNPC(victim) && fighting && !is_same_group -> kill stealing
    if (victim["is_npc"] and victim.get("fighting") is not None
            and not is_same_group(ch, world.chars.get(victim["fighting"]))):
        chprintln(ch, "Kill stealing is not permitted.")
        return None

    if ch["equip"].get("wield") is None:
        chprintln(ch, "You need to wield a weapon to backstab.")
        return None

    if victim["hit"] < victim["max_hit"] // 3:
        act("$N is hurt and suspicious ... you can't sneak up.", ch, None, victim, TO_CHAR)
        return None

    # [PRIMESUD] check_killer not ported
    WaitState(ch, SKILLS[GSN_BACKSTAB]["beats"])
    skill_pct = get_skill(ch, GSN_BACKSTAB, ch["is_npc"])
    if randint(1, 100) < skill_pct or (skill_pct >= 2 and not is_awake(victim)):
        check_improve(ch, GSN_BACKSTAB, True, 1)
        multi_hit(ch, victim, dt=GSN_BACKSTAB)
    else:
        check_improve(ch, GSN_BACKSTAB, False, 1)
        damage(ch, victim, 0, GSN_BACKSTAB, DAM_NONE, show=True, attack_noun="backstab")
    return None


def _picker_mob_lists(player, live):
    """Build the id/label lists for the no-args consider/kill pickers. [PRIMESUD]

    Mobs the player cannot see are dropped, so an undetected hide/invis mob is
    not betrayed by the menu.  Visible mobs keep room order, but ones the
    player cannot attack (shopkeepers, pets, quest targets -- anything
    is_safe_spell protects) are demoted below the attackable ones and dimmed.

    Args:
        player (dict): Player state dict.
        live (list): Mob ids present in the player's room.

    Returns:
        tuple: (ids, names) -- parallel lists of mob ids and picker labels.
    """
    kill_ids = []
    safe_ids = []
    for i in live:
        mob = world.chars[i]
        if not can_see(player, mob):
            continue
        if is_safe_spell(player, mob, False):
            safe_ids.append(i)
        else:
            kill_ids.append(i)
    names = [MOB_DEFS[world.chars[i]["tpl"]]["short_descr"] for i in kill_ids]
    for i in safe_ids:
        names.append("{D" + MOB_DEFS[world.chars[i]["tpl"]]["short_descr"] + "{x")
    return kill_ids + safe_ids, names


def do_consider(player, args):
    """Judge a potential opponent's level relative to yours (cf. 1stMud do_consider in act_info.c).

    Args:
        player (dict): Player state dict.
        args (list): Target keyword; [PRIMESUD] picker shown if omitted.
    """
    rs = world.rooms[player["room"]]
    live = rs["mobs"]
    if args:
        mob_id = get_char_room(" ".join(args), live, world.chars, player)
        if mob_id is None:
            chprintln(player, "They're not here.")
            return
    else:
        # [PRIMESUD] picker menu when no args (1stMud prints "Consider killing whom?"
        # and stops). Offers only mobs the player can actually see, so an
        # undetected hide/invis mob is not betrayed by the menu; mobs that
        # can't be attacked (shopkeepers, pets, ...) sink to the bottom of the
        # list and are dimmed.
        vis, names = _picker_mob_lists(player, live)
        if not vis:
            # [PRIMESUD] not upstream's "Consider killing whom?" argument
            # prompt: an empty menu means nothing visible, not a missing arg
            chprintln(player, "You don't see anyone here.")
            return
        idx = pick_from("Consider killing whom?", names)
        if idx < 0:
            return
        mob_id = vis[idx]

    victim = world.chars[mob_id]

    if is_safe(player, victim):
        chprintln(player, "Don't even think about it.")
        return

    diff = victim.get("level", 1) - player.get("level", 1)

    if diff <= -10:
        msg = "You can kill $N naked and weaponless."
    elif diff <= -5:
        msg = "$N is no match for you."
    elif diff <= -2:
        msg = "$N looks like an easy kill."
    elif diff <= 1:
        msg = "The perfect match!"
    elif diff <= 4:
        msg = "$N says 'Do you feel lucky, punk?'."
    elif diff <= 9:
        msg = "$N laughs at you mercilessly."
    else:
        msg = "Death will thank you for your gift."

    act(msg, player, None, victim, TO_CHAR)
    if not args:
        # [PRIMESUD] full keywords string, like do_kill's picker -- the typed
        # path joins args, and the short_descr fallback avoids split()[0]
        # blowing up on a keywordless template
        vtpl = MOB_DEFS[victim["tpl"]]
        return "consider " + vtpl.get("keywords", vtpl["short_descr"])


def do_kill(player, args):
    """Initiate melee combat with a target (cf. 1stMud do_kill in fight.c).
    [Verified: 04/07/2026] -- self-hit branch and check_killer not ported;
    [PRIMESUD] picker menu when no args.

    Args:
        player (dict): Player state dict.
        args (list): Target keyword; [PRIMESUD] picker shown if omitted.
    """
    rs = world.rooms[player["room"]]
    live = rs["mobs"]
    if args:
        mob_id = get_char_room(" ".join(args), live, world.chars, player)
        if mob_id is None:
            chprintln(player, "They aren't here.")
            return
    else:
        # [PRIMESUD] picker menu when no args (1stMud prints "Kill whom?" and
        # stops). Offers only mobs the player can actually see, so an
        # undetected hide/invis mob is not betrayed by the menu; mobs that
        # can't be attacked (shopkeepers, pets, ...) sink to the bottom of the
        # list and are dimmed.  An empty room -- or one holding nothing the
        # player can see -- prints "You don't see anyone here." instead of
        # upstream's "Kill whom?" missing-argument prompt.
        vis, names = _picker_mob_lists(player, live)
        if not vis:
            chprintln(player, "You don't see anyone here.")
            return
        idx = pick_from("Kill whom?", names)
        if idx < 0:
            return
        mob_id = vis[idx]

    victim = world.chars[mob_id]

    # 1stMud: if (victim == ch) { "You hit yourself. Ouch!"; multi_hit(ch,ch,...); return; }
    # [PRIMESUD] player can't target self (mob_id lookup is mob-only)

    if is_safe(player, victim):
        return

    # 1stMud: victim->fighting != NULL && !is_same_group -> kill stealing
    if (victim.get("fighting") is not None
            and not is_same_group(player, world.chars.get(victim["fighting"]))):
        chprintln(player, "Kill stealing is not permitted.")
        return

    # 1stMud: AFF_CHARM && ch->master == victim -> "beloved master"
    if (player["affected_by"].get("charm")
            and player.get("master") == victim.get("id")):
        act("$N is your beloved master.", player, None, victim, TO_CHAR)
        return

    if player.get("pos") == "fighting":
        chprintln(player, "You do the best you can!")
        return

    WaitState(player, PULSE_VIOLENCE)
    # [PRIMESUD] check_killer not ported
    multi_hit(player, victim)
    if not args:
        # [PRIMESUD] full keywords string, like the inventory/shop pickers --
        # and the short_descr fallback avoids split()[0] blowing up on a
        # keywordless template
        vtpl = MOB_DEFS[victim["tpl"]]
        return "kill " + vtpl.get("keywords", vtpl["short_descr"])


def mob_hit(ch, victim, dt=TYPE_UNDEFINED):
    """Full attack sequence for one mob per combat round (cf. 1stMud mob_hit in fight.c).
    [Verified: 02/07/2026] -- ACT_MAGE/ACT_CLERIC cast cases, OFF_TAIL, OFF_CRUSH,
    and OFF_BACKSTAB are no-ops in 1stMud and skipped here.

    Args:
        ch (dict): Attacking mob instance dict.
        victim (dict): Player state dict.
        dt (int): Damage type passed from multi_hit (e.g. GSN_BACKSTAB).
    """
    one_hit(ch, victim, dt=dt)
    if ch.get("fighting") != victim.get("id"):
        return

    # 1stMud: OFF_AREA_ATTACK -- also hit everyone else in the room fighting ch
    if ch["off_flags"].get("area_attack"):
        rs = world.rooms[ch["room"]]
        others = [world.chars[m] for m in list(rs["mobs"])]
        player = world.chars[1]
        if player.get("room") == ch.get("room"):
            others.append(player)
        for vch in others:
            if vch is not victim and vch.get("fighting") == ch.get("id"):
                one_hit(ch, vch, dt=dt)

    # 1stMud: AFF_HASTE || (OFF_FAST && !AFF_SLOW) -> extra hit
    if (ch["affected_by"].get("haste")
            or (ch["off_flags"].get("fast")
                and not ch["affected_by"].get("slow"))):
        one_hit(ch, victim, dt=dt)

    # Backstab = single hit only (cf. 1stMud mob_hit fight.c:475)
    if ch.get("fighting") != victim.get("id") or dt == GSN_BACKSTAB:
        return

    # Second and third attacks (cf. 1stMud mob_hit; get_skill NPC branch in handler.c)
    slowed = (ch["affected_by"].get("slow")
              and not ch["off_flags"].get("fast"))
    chance = get_skill(ch, GSN_SECOND_ATTACK, is_mob=True) // 2
    if slowed:
        chance //= 2
    if randint(1, 100) < chance:
        one_hit(ch, victim, dt=dt)
        if ch.get("fighting") != victim.get("id"):
            return

    chance = 0 if slowed else get_skill(ch, GSN_THIRD_ATTACK, is_mob=True) // 4
    if randint(1, 100) < chance:
        one_hit(ch, victim, dt=dt)
        if ch.get("fighting") != victim.get("id"):
            return

    # 1stMud: if (ch->wait > 0) return; -- blocks mob specials
    if ch.get("wait", 0) > 0:
        return

    # 1stMud: number_range(0,2) ACT_MAGE / ACT_CLERIC cases are empty blocks -- skipped

    # Off-flag specials (cf. 1stMud mob_hit fight.c:517-573 random switch)
    off = ch["off_flags"]
    number = randint(0, 8)
    if number == 0:
        if off.get("bash"):
            do_bash(ch, [])
    elif number == 1:
        if off.get("berserk") and not ch["affected_by"].get("berserk"):
            do_berserk(ch, [])
    elif number == 2:
        act_f = ch["act_flags"]
        if (off.get("disarm")
                or (_get_weapon_sn(ch)[0] != GSN_HAND_TO_HAND
                    and (act_f.get("warrior") or act_f.get("thief")))):
            do_disarm(ch, [])
    elif number == 3:
        if off.get("kick"):
            do_kick(ch, [])
    elif number == 4:
        if off.get("kick_dirt"):
            do_dirt(ch, [])
    elif number == 6:
        if off.get("trip"):
            do_trip(ch, [])
    # cases 5 (OFF_TAIL) and 7 (OFF_CRUSH) are empty blocks in 1stMud; case 8
    # (OFF_BACKSTAB) calls do_backstab with no argument, which no-ops -- skipped


# -- Special stance moves (cf. 1stMud special_move in fight.c) -----------------

# Each move is a sequence of (template, actor, act_type) acts. Actor "ch"
# acts pass victim as $N; actor "v" acts are victim-only with no argument.
# Templates byte-exact from fight.c:212-352, including the lines in case 4
# that are missing their {x terminator upstream.
_SPECIAL_MOVES = [
    (   # case 1
        ("{RYou pull your hands into your waist then snap them into $N's{R stomach.{x", "ch", TO_CHAR),
        ("{R$n{R pulls $s{R hands into $s{R waist then snaps them into your stomach.{x", "ch", TO_VICT),
        ("{R$n{R pulls $s{R hands into $s{R waist then snaps them into $N's{R stomach.{x", "ch", TO_NOTVICT),
        ("{RYou double over in agony, and fall to the ground gasping for breath.{x", "v", TO_CHAR),
        ("{R$n{R doubles over in agony, and falls to the ground gasping for breath.{x", "v", TO_ROOM),
    ),
    (   # case 2
        ("{RYou spin in a low circle, catching $N{R behind $S{R ankle.{x", "ch", TO_CHAR),
        ("{R$n{R spins in a low circle, catching you behind your ankle.{x", "ch", TO_VICT),
        ("{R$n{R spins in a low circle, catching $N{R behind $S{R ankle.{x", "ch", TO_NOTVICT),
        ("{RYou crash to the ground, stunned.{x", "v", TO_CHAR),
        ("{R$n{R crashes to the ground, stunned.{x", "v", TO_ROOM),
    ),
    (   # case 3
        ("{RYou roll between $N's{R legs and flip to your feet.{x", "ch", TO_CHAR),
        ("{R$n{R rolls between your legs and flips to $s{R feet.{x", "ch", TO_VICT),
        ("{R$n{R rolls between $N's{R legs and flips to $s{R feet.{x", "ch", TO_NOTVICT),
        ("{RYou spin around and smash your elbow into the back of $N's{R head.{x", "ch", TO_CHAR),
        ("{R$n{R spins around and smashes $s{R elbow into the back of your head.{x", "ch", TO_VICT),
        ("{R$n{R spins around and smashes $s{R elbow into the back of $N's{R head.{x", "ch", TO_NOTVICT),
        ("{RYou fall to the ground, stunned.{x", "v", TO_CHAR),
        ("{R$n{R falls to the ground, stunned.{x", "v", TO_ROOM),
    ),
    (   # case 4
        ("{RYou somersault over $N's{R head and land lightly on your toes.{x", "ch", TO_CHAR),
        ("{R$n{R somersaults over your head and lands lightly on $s toes.{x", "ch", TO_VICT),
        ("{R$n{R somersaults over $N's{R head and lands lightly on $s toes.{x", "ch", TO_NOTVICT),
        ("{RYou roll back onto your shoulders and kick both feet into $N's{R back.{x", "ch", TO_CHAR),
        ("{R$n{R rolls back onto $s{R shoulders and kicks both feet into your back.{x", "ch", TO_VICT),
        ("{R$n{R rolls back onto $s{R shoulders and kicks both feet into $N's{R back.{x", "ch", TO_NOTVICT),
        ("{RYou fall to the ground, stunned.", "v", TO_CHAR),
        ("{R$n{R falls to the ground, stunned.", "v", TO_ROOM),
        ("{RYou flip back up to your feet.", "ch", TO_CHAR),
        ("{R$n{R flips back up to $s feet.", "ch", TO_ROOM),
    ),
    (   # case 5
        ("{RYou grab $N{R by the waist and hoist $M{R above your head.{x", "ch", TO_CHAR),
        ("{R$n{R grabs $N{R by the waist and hoists $M{R above $s{R head.{x", "ch", TO_NOTVICT),
        ("{R$n{R grabs you by the waist and hoists you above $s{R head.{x", "ch", TO_VICT),
        ("{RYou crash to the ground, stunned.{x", "v", TO_CHAR),
        ("{R$n{R crashes to the ground, stunned.{x", "v", TO_ROOM),
    ),
    (   # case 6
        ("{RYou grab $N{R by the head and slam $S{R face into your knee.{x", "ch", TO_CHAR),
        ("{R$n{R grabs you by the head and slams your face into $s{R knee.{x", "ch", TO_VICT),
        ("{R$n{R grabs $N{R by the head and slams $S{R face into $s{R knee.{x", "ch", TO_NOTVICT),
        ("{RYou crash to the ground, stunned.{x", "v", TO_CHAR),
        ("{R$n{R crashes to the ground, stunned.{x", "v", TO_ROOM),
        ("{RYou flip back up to your feet.{x", "ch", TO_CHAR),
        ("{R$n{R flips back up to $s{R feet.{x", "ch", TO_ROOM),
    ),
    (   # case 7
        ("{RYou duck under $N's{R attack and pound your fist into $S{R stomach.{x", "ch", TO_CHAR),
        ("{R$n{R ducks under your attack and pounds $s{R fist into your stomach.{x", "ch", TO_VICT),
        ("{R$n{R ducks under $N's{R attack and pounds $s{R fist into $N's{R stomach.{x", "ch", TO_NOTVICT),
        ("{RYou double over in agony.{x", "v", TO_CHAR),
        ("{R$n{R doubles over in agony.{x", "v", TO_ROOM),
    ),
]


def special_move(ch, victim):
    """Stance-mastery special move: flavour acts + stun (cf. 1stMud special_move in fight.c).
    [Verified: 04/07/2026] -- 1stMud's switch default is unreachable
    (number_range(1,7) always lands on a case) and collapses away; the
    seven case bodies are table-driven here, acts byte-exact.

    Triggered from multi_hit when the current stance is trained to 200
    (1-in-100). Victim stops fighting and is left stunned.

    Args:
        ch (dict): Attacker (player or mob instance).
        victim (dict): Target (player or mob instance).
    """
    if victim is None or victim.get("pos") == "dead":
        return
    move = _SPECIAL_MOVES[randint(0, len(_SPECIAL_MOVES) - 1)]
    for template, actor, act_type in move:
        if actor == "ch":
            act(template, ch, None, victim, act_type)
        else:
            act(template, victim, None, None, act_type)
    stop_fighting(victim, both=True)
    victim["pos"] = "stunned"


# -- Multi-hit (player's full attack sequence) ---------------------------------

def multi_hit(ch, victim, dt=TYPE_UNDEFINED):
    """Full attack sequence for one combat round (cf. 1stMud multi_hit in fight.c).
    [Verified: 04/07/2026] -- Returns kill status ([PRIMESUD]; 1stMud is
    void); [PRIMESUD] Swordsman flourishes added.

    Args:
        ch (dict): Attacker (player or mob instance).
        victim (dict): Defender (player or mob instance).
        dt (int): Damage type; TYPE_UNDEFINED for normal round,
            skill GSN (e.g. GSN_BACKSTAB) for skill-initiated attacks.

    Returns:
        bool: True if the victim was killed this round.
    """
    # 1stMud: NPC wait/daze decrement (ch->desc == NULL) handled by update_mob_timers()

    # 1stMud: if (ch->position < POS_RESTING) return;
    if POS_ORDER[ch["pos"]] < POS_ORDER["resting"]:
        return False

    if ch["is_npc"]:
        mob_hit(ch, victim, dt=dt)
        return victim.get("pos") == "dead"

    if dt == TYPE_UNDEFINED:
        _sword_flourish(ch, victim)

    # Primary
    one_hit(ch, victim, dt=dt)

    # Offhand weapon (cf. 1stMud multi_hit WEAR_SECONDARY in fight.c)
    # [PRIMESUD] ensures that secondary item is a weapon before allowing hit
    secondary_obj = ch["equip"].get("secondary")
    if secondary_obj is not None and item_tpl(secondary_obj).get("type") == "weapon":
        one_hit(ch, victim, dt=dt, secondary=True)

    # 1stMud: if (ch->fighting != victim) return;
    if ch.get("fighting") != victim.get("id"):
        return victim.get("pos") == "dead"

    # 1stMud: if (IsAffected(ch, AFF_HASTE)) one_hit(ch, victim, dt, false);
    if ch["affected_by"].get("haste"):
        one_hit(ch, victim, dt=dt)

    # Backstab = single hit only (cf. 1stMud multi_hit fight.c:390)
    if ch.get("fighting") != victim.get("id") or dt == GSN_BACKSTAB:
        return victim.get("pos") == "dead"

    # Stance special move: mastered stance, 1-in-100 (cf. 1stMud multi_hit fight.c:393-398)
    if (valid_stance(get_stance(ch, STANCE_CURRENT))
            and get_stance(ch, get_stance(ch, STANCE_CURRENT)) >= 200
            and randint(1, 100) == 50):
        special_move(ch, victim)
        return victim.get("pos") == "dead"

    # Second attack: skill/2 chance; third: skill/4 chance (cf. 1stMud multi_hit in fight.c)
    chance = get_skill(ch, GSN_SECOND_ATTACK) // 2
    if ch["affected_by"].get("slow"):
        chance //= 2
    if randint(1, 100) < chance:
        one_hit(ch, victim, dt=dt)
        check_improve(ch, GSN_SECOND_ATTACK, True, 5)
        if ch.get("fighting") != victim.get("id"):
            return victim.get("pos") == "dead"

    chance = get_skill(ch, GSN_THIRD_ATTACK) // 4
    if ch["affected_by"].get("slow"):
        chance = 0
    if randint(1, 100) < chance:
        one_hit(ch, victim, dt=dt)
        check_improve(ch, GSN_THIRD_ATTACK, True, 6)
        if ch.get("fighting") != victim.get("id"):
            return victim.get("pos") == "dead"

    # Viper/mantis/tiger stance extra hit (cf. 1stMud multi_hit fight.c:426-446;
    # C compares number_percent() < stance * 0.5, so use (stance + 1) // 2)
    if (in_stance(ch, STANCE_VIPER)
            and randint(1, 100) < (get_stance(ch, STANCE_VIPER) + 1) // 2):
        one_hit(ch, victim, dt=dt)
        if ch.get("fighting") != victim.get("id"):
            return victim.get("pos") == "dead"
    elif (in_stance(ch, STANCE_MANTIS)
            and randint(1, 100) < (get_stance(ch, STANCE_MANTIS) + 1) // 2):
        one_hit(ch, victim, dt=dt)
        if ch.get("fighting") != victim.get("id"):
            return victim.get("pos") == "dead"
    elif (in_stance(ch, STANCE_TIGER)
            and randint(1, 100) < (get_stance(ch, STANCE_TIGER) + 1) // 2):
        one_hit(ch, victim, dt=dt)
        if ch.get("fighting") != victim.get("id"):
            return victim.get("pos") == "dead"

    return False


# -- Combat state --------------------------------------------------------------

# default_pos short forms in area data -> position keys (cf. 1stMud position_table)
_DEFAULT_POS = POS_FROM_SHORT


def set_fighting(ch, victim):
    """Engage ch in combat against victim (cf. 1stMud set_fighting in fight.c).
    [Verified: 03/07/2026] -- [PRIMESUD] Swordsman form default added."""
    # 1stMud: if (ch->fighting != NULL) { bug("Set_fighting: already fighting"); return; }
    if ch.get("fighting") is not None:
        return

    # 1stMud: if (IsAffected(ch, AFF_SLEEP)) affect_strip(ch, gsn_sleep);
    if ch["affected_by"].get("sleep"):
        for _sn, _sk in SKILL_TABLE:
            if _sk["name"] == "sleep":
                affect_strip(ch, _sn)
                break

    ch["fighting"] = victim["id"]
    # [PRIMESUD] active-fighter index -- if you ever set ch['fighting']
    # directly elsewhere, you MUST update world.FIGHTERS too.
    world.FIGHTERS.add(ch["id"])
    ch["pos"] = "fighting"
    if (not ch["is_npc"] and classes.is_class(ch, classes.CLASS_SWORDSMAN)
            and "_sword_form" not in ch):
        ch["_sword_form"] = "flowing"
    autodrop(ch)  # cf. 1stMud set_fighting fight.c:1651


def stop_fighting(ch, both=False):
    """
    Given character stops fighting its target.
    Optionally make all other characters stop fighting it.
    (cf. 1stMud stop_fighting in fight.c).
    [Verified: 03/07/2026]

    Args:
        ch (dict): Character that stops fighting its target.
        both (bool): If true, all other characters stop fighting `ch`.
    """
    for char in world.chars.values():
        if char is ch or (both and char["fighting"] == ch["id"]):
            char["fighting"] = None
            # [PRIMESUD] active-fighter index -- mirrors the set_fighting add.
            world.FIGHTERS.discard(char["id"])
            # 1stMud: fch->position = IsNPC(fch) ? fch->default_pos : POS_STANDING;
            if char["is_npc"]:
                char["pos"] = _DEFAULT_POS.get(
                    MOB_DEFS[char["tpl"]].get("default_pos", "stand"), "standing")
            else:
                char["pos"] = "standing"
            update_pos(char)
            # [PRIMESUD] original .are files allow for mobs to have default positions
            # specified, but we haven't ported this yet.
            char["pos"] = "standing"
            update_pos(char)
            # cf. 1stMud: SetStance(fch, STANCE_CURRENT, STANCE_NONE)
            set_stance(char, STANCE_CURRENT, STANCE_NONE)


def _advance_target(player, mob_instances, room_state):
    """Switch player's combat target to the next aggro mob in the room. [PRIMESUD]

    Args:
        player (dict): Player state dict.
        mob_instances (dict): Mob instance mapping mob ID -> mob instance dict.
        room_state (dict): Room state mapping room ID -> room state dict.
    """
    rs      = room_state[player["room"]]
    next_id = None
    for mid in rs["mobs"]:
        if mob_instances[mid]["fighting"] is not None:
            next_id = mid
            break
    if next_id is not None:
        # [PRIMESUD] full set_fighting, not a direct write: raw_kill's
        # stop_fighting(both=True) just cleared the player's fighting/pos/
        # stance and removed them from world.FIGHTERS; re-engaging must
        # restore all of those, exactly as the next mob's damage() ->
        # set_fighting would have in 1stMud's no-retarget flow.
        set_fighting(player, mob_instances[next_id])
    else:
        stop_fighting(player, both=False)


# -- Death / Victory -----------------------------------------------------------

# OBJ_VNUM_* body-part templates (area_limbo.txt #12-17; cf. 1stMud
# vnums.h). Not exposed as named constants in world.py (only the corpse
# vnums OBJ_VNUM_CORPSE_NPC/OBJ_VNUM_CORPSE_PC are), so defined locally here.
_OBJ_VNUM_SEVERED_HEAD = 12
_OBJ_VNUM_TORN_HEART   = 13
_OBJ_VNUM_SLICED_ARM   = 14
_OBJ_VNUM_SLICED_LEG   = 15
_OBJ_VNUM_GUTS         = 16
_OBJ_VNUM_BRAINS       = 17

_DEATH_CRY_DEFAULT = "You hear $n's death cry."

# Death-cry cases keyed by number_bits(4) roll (cf. 1stMud death_cry switch
# in fight.c): (message, part_flags key, body-part OBJ_VNUM). part key of
# None means unconditional; a part-gated case only fires when ch's
# part_flags has that key set, otherwise it falls through to
# _DEATH_CRY_DEFAULT (rolls 8-15 have no case at all and always fall
# through too). 1stMud case 1 additionally guards on `ch->material == 0`:
# PCs leave that pointer NULL, while NPC creation always assigns a string.
# PrimeSUD needs no material field to preserve that distinction -- NPC roll 1
# falls through to case 2 (guts), while PC roll 1 keeps the blood message.
_DEATH_CRY_CASES = {
    0: ("$n hits the ground ... DEAD.", None, 0),
    1: ("$n splatters blood on your armor.", None, 0),
    2: ("$n spills $s guts all over the floor.", "guts", _OBJ_VNUM_GUTS),
    3: ("$n's severed head plops on the ground.", "head", _OBJ_VNUM_SEVERED_HEAD),
    4: ("$n's heart is torn from $s chest.", "heart", _OBJ_VNUM_TORN_HEART),
    5: ("$n's arm is sliced from $s dead body.", "arms", _OBJ_VNUM_SLICED_ARM),
    6: ("$n's leg is sliced from $s dead body.", "legs", _OBJ_VNUM_SLICED_LEG),
    7: ("$n's head is shattered, and $s brains splash all over you.", "brains", _OBJ_VNUM_BRAINS),
}

# short_descr / description templates for dropped body parts (cf. 1stMud
# death_cry: sprintf(buf, obj->short_descr / obj->description, name)).
# PrimeSUD uses str() + concat instead of sprintf/"%" since these strings
# persist on the item instance (see CLAUDE.md string-format-bug note).
# Tuple: (short_descr prefix, description prefix, description suffix).
_BODY_PART_TEXT = {
    _OBJ_VNUM_SEVERED_HEAD: ("The head of ", "The severed head of ", " is lying here."),
    _OBJ_VNUM_TORN_HEART:   ("The heart of ", "The torn-out heart of ", " is lying here."),
    _OBJ_VNUM_SLICED_ARM:   ("The arm of ", "The sliced-off arm of ", " is lying here."),
    _OBJ_VNUM_SLICED_LEG:   ("The leg of ", "The sliced-off leg of ", " is lying here."),
    _OBJ_VNUM_GUTS:         ("The guts of ", "A steaming pile of ", "'s entrails is lying here."),
    _OBJ_VNUM_BRAINS:       ("The brains of ", "The splattered brains of ", " are lying here."),
}


def _death_cry(ch):
    """Death flavour message, body-part drop, and adjacent-room cry
    (cf. 1stMud death_cry in fight.c).
    [Verified: 23/07/2026]
    -- part-flag gated message/object selection,
    poison-food/trash-downgrade, and adjacent-room broadcast added per
    fight.c. PCs now get form_flags/part_flags from RACE_TABLE via
    player.py create_char (cf. 1stMud nanny.c:533-534 / save.c:723-724),
    so PC victims of part-bearing races hit the same drop logic as mobs.

    Args:
        ch (dict): Dying character (player or mob instance).
    """
    msg = _DEATH_CRY_DEFAULT
    vnum = 0
    roll = randint(0, 15)  # 1stMud: number_bits(4)
    if roll == 1 and ch.get("is_npc"):
        roll = 2
    case = _DEATH_CRY_CASES.get(roll)
    if case is not None:
        cmsg, part, cvnum = case
        if part is None or ch["part_flags"].get(part):
            msg, vnum = cmsg, cvnum

    act(msg, ch, type=TO_ROOM)

    if vnum:
        # 1stMud: name = IsNPC(ch) ? ch->short_descr : ch->name;
        name = MOB_DEFS[ch["tpl"]]["short_descr"] if ch.get("is_npc") else ch.get("name", "someone")
        obj = create_object(vnum)
        # 1stMud: obj->timer = number_range(4, 7);
        obj["timer"] = randint(4, 7)
        pre_short, pre_desc, suf_desc = _BODY_PART_TEXT[vnum]
        obj["short_descr"] = pre_short + name
        obj["description"] = pre_desc + name + suf_desc
        # 1stMud: if (obj->item_type == ITEM_FOOD) { poison, or downgrade
        # to ITEM_TRASH if not FORM_EDIBLE }
        # [PRIMESUD] item_tpl, not ITEM_DEFS[vnum]: consistent with the
        # snapshot-aware template-read sweep (limbo is resident in practice,
        # so this is uniformity, not a reload fix).
        if item_tpl(vnum).get("type") == "food":
            form_flags = ch["form_flags"]
            if form_flags.get("poison"):
                obj["poisoned"] = True  # 1stMud: obj->value[3] = 1
            elif not form_flags.get("edible"):
                obj["type"] = "trash"  # [PRIMESUD] instance override; consumers use item.item_type()
        # 1stMud: obj_to_room(obj, ch->in_room);
        world.rooms[ch["room"]]["items"].append(obj)

    # 1stMud: walks ch->in_room->exit[0..5] and act()s "You hear
    # something's/someone's death cry." into every adjacent room.
    # [PRIMESUD] single-player: only the player can "hear" it, so just
    # check whether the player's current room is one exit away.
    death_room = ch.get("room")
    player = world.chars.get(1)
    if player is not None and player is not ch and death_room is not None:
        cry_msg = "You hear something's death cry." if ch.get("is_npc") else "You hear someone's death cry."
        for _ex in ROOM_DEFS[death_room].get("exits", {}).values():
            dest = _ex["to"] if isinstance(_ex, dict) else _ex
            if dest == player.get("room") and dest != death_room:
                chprintln(player, cry_msg)
                break


def create_money(gold, silver):
    """Create a coin item for the given gold/silver amounts (cf. 1stMud create_money in handler.c).
    [Verified: 31/07/2026] -- weight not tracked; zero/negative input returns
    None instead of 1stMud's bug-log + clamp to 1.

    Args:
        gold (int): Gold coin count.
        silver (int): Silver coin count.

    Returns:
        dict: Coin item instance, or None if both are zero.
    """
    if gold <= 0 and silver <= 0:
        return None
    gold = max(0, gold)
    silver = max(0, silver)
    if gold == 0 and silver == 1:
        obj = create_object(OBJ_VNUM_SILVER_ONE)
        obj["silver"] = 1
        obj["gold"] = 0
        obj["cost"] = 1
        return obj
    if gold == 1 and silver == 0:
        obj = create_object(OBJ_VNUM_GOLD_ONE)
        obj["silver"] = 0
        obj["gold"] = 1
        obj["cost"] = 100
        return obj
    if silver == 0:
        obj = create_object(OBJ_VNUM_GOLD_SOME)
        obj["short_descr"] = num_str(gold) + " gold coins"
        obj["silver"] = 0
        obj["gold"] = gold
        # 1stMud quirk: multi-gold pile cost is gold count, not gold * 100
        obj["cost"] = gold
        return obj
    if gold == 0:
        obj = create_object(OBJ_VNUM_SILVER_SOME)
        obj["short_descr"] = num_str(silver) + " silver coins"
        obj["silver"] = silver
        obj["gold"] = 0
        obj["cost"] = silver
        return obj
    obj = create_object(OBJ_VNUM_COINS)
    # [PRIMESUD] Singular/plural fix -- 1stMud names this pile "1 silver coins
    # and 5 gold coins"; the *_ONE objects it falls back on are "A silver coin".
    obj["short_descr"] = (count_str(silver, "silver coin") + " and "
                          + count_str(gold, "gold coin"))
    obj["silver"] = silver
    obj["gold"] = gold
    obj["cost"] = gold * 100 + silver
    return obj


def make_corpse(ch):
    """Create corpse for ch and place in room (cf. 1stMud make_corpse in fight.c).
    [Verified: 02/07/2026] -- arena check, floating items, and clan morgue
    (dead code in 1stMud) not ported.

    NPC: corpse contains mob loot (gold + equipment).
    PC: [PRIMESUD] empty corpse for dramatic effect; player keeps items on respawn.

    Args:
        ch (dict): Dying character (player or mob instance).

    Returns:
        dict: The corpse object. [PRIMESUD] 1stMud make_corpse is void;
            we return it so autoloot can use it directly instead of searching
            by name (which picks the oldest corpse when multiple exist).
    """
    # 1stMud: if (IsSet(ch->in_room->room_flags, ROOM_ARENA)) return;
    # [PRIMESUD] skip arena check (not ported)

    if ch.get("is_npc"):
        # 1stMud: name = ch->short_descr;
        name = MOB_DEFS[ch["tpl"]]["short_descr"]
        # 1stMud: corpse = create_object(get_obj_index(OBJ_VNUM_CORPSE_NPC), 0);
        corpse = create_object(OBJ_VNUM_CORPSE_NPC)
        # 1stMud: corpse->timer = number_range(3, 6);
        corpse["timer"] = randint(3, 6)
        corpse["contents"] = []
        # 1stMud: if (ch->gold > 0) { obj_to_obj(create_money(...), corpse); ... }
        # [PRIMESUD] silver-only mobs drop coins too (1stMud's gold-only guard
        # silently discards pure-silver wealth)
        coin = create_money(ch.get("gold", 0), ch.get("silver", 0))
        if coin is not None:
            corpse["contents"].append(coin)
        # 1stMud: corpse->cost = 0;  (default in PrimeSUD)

        # 1stMud: for (obj = ch->carrying_first ...) obj_to_obj(obj, corpse)
        for obj in list(ch["equip"].values()) + list(ch["inv"]):
            if obj is None:
                continue
            obj_tpl = item_tpl(obj)
            flags = item_extra_flags(obj, obj_tpl)
            # 1stMud: if (IsSet(obj->extra_flags, ITEM_INVENTORY)) extract_obj(obj)
            if flags.get("inventory"):
                continue
            # 1stMud: potion/scroll decay timers set on death drop
            if _item_type(obj, obj_tpl) == "potion":
                obj["timer"] = randint(500, 1000)
            elif _item_type(obj, obj_tpl) == "scroll":
                obj["timer"] = randint(1000, 2500)
            # 1stMud: if (IsSet(obj->extra_flags, ITEM_ROT_DEATH) && !floating)
            if flags.get("rot_death"):
                obj["timer"] = randint(5, 10)
                set_item_extra_flag(obj, obj_tpl, "rot_death", False)
            # 1stMud: RemBit(obj->extra_flags, ITEM_VIS_DEATH)
            if item_extra_flags(obj, obj_tpl).get("vis_death"):
                set_item_extra_flag(obj, obj_tpl, "vis_death", False)
            # 1stMud: floating item handling (WEAR_FLOAT scatter/evaporate)
            # [PRIMESUD] skip floating items (not ported)
            corpse["contents"].append(obj)
    else:
        # 1stMud: name = ch->name;
        name = ch.get("name", "someone")
        # 1stMud: corpse = create_object(get_obj_index(OBJ_VNUM_CORPSE_PC), 0);
        corpse = create_object(OBJ_VNUM_CORPSE_PC)
        # 1stMud: corpse->timer = number_range(25, 40);
        corpse["timer"] = randint(25, 40)
        # 1stMud: corpse->owner = str_dup(ch->name);
        corpse["owner"] = ch.get("name", "someone")
        # 1stMud: RemBit(ch->act, PLR_CANLOOT);
        # [PRIMESUD] skip PLR_CANLOOT (not ported)
        # 1stMud: if (is_clan(ch)) { gold/2 into corpse; }
        # [PRIMESUD] skip clan gold split (no clans)
        # 1stMud: item transfer loop (obj_to_obj for all carrying)
        # [PRIMESUD] skip -- player keeps all items on respawn

    # 1stMud: corpse->level = ch->level;
    corpse["level"] = ch.get("level", 1)
    # 1stMud: sprintf(buf, corpse->short_descr, name);
    corpse["short_descr"] = "The corpse of " + name
    # 1stMud: sprintf(buf, corpse->description, name);
    corpse["description"] = "The corpse of " + name + " is lying here."
    # 1stMud: obj_to_room(corpse, ch->in_room);
    world.rooms[ch["room"]]["items"].append(corpse)
    return corpse


def update_death(victim, killer):
    """Update mob-template and area stats (cf. 1stMud update_death in fight.c).

    Kills use mob/area perspective: a player death is an area kill; a mob
    death is an area death. [PRIMESUD] Sparse maps avoid loading templates;
    player/global/level stats, death sounds, and millionth-kill bonuses remain
    absent.
    """
    # Upstream explicitly excludes self-inflicted deaths.
    if victim is killer:
        return
    if victim.get("is_npc"):
        # Template stats follow pIndexData; area stats follow in_room->area.
        world.mob_stats.setdefault(victim["tpl"], [0, 0])[1] += 1
        area = world._vnum_to_tag(victim.get("room"))
        if area is not None:
            world.area_stats.setdefault(area, [0, 0])[1] += 1
    else:
        area = world._vnum_to_tag(victim.get("room"))
        if area is not None:
            world.area_stats.setdefault(area, [0, 0])[0] += 1
    if killer is not None and killer.get("is_npc"):
        world.mob_stats.setdefault(killer["tpl"], [0, 0])[0] += 1


def raw_kill(victim, killer):
    """Kill victim: stop fight, death cry, corpse, extract/respawn (cf. 1stMud raw_kill in fight.c).
    [Verified: 06/07/2026]
    -- update_all_qobjs (quests) not ported;
    [PRIMESUD] respawn flavour text, per-kill save, and post-death
    reset_char added.

    Args:
        victim (dict): Dying character (player or mob instance).
        killer (dict or None): Character that landed the killing blow, or None.

    Returns:
        dict: The corpse object created by make_corpse. [PRIMESUD]
    """
    stop_fighting(victim, both=True)
    victim.pop("run_buf", None)  # [PRIMESUD] 1stMud omits this (latent bug: run_buf survives death)
    _death_cry(victim)
    corpse = make_corpse(victim)

    if victim.get("is_npc"):
        # 1stMud: extract_char(victim, true) -- remove NPC from world
        _extract_char(victim, pull=True)
        # [PRIMESUD] save after every kill (1stmud only saves on level up)
        world.save_pending = True
        return corpse

    # 1stMud: extract_char(victim, false) -- teleport PC to altar
    _extract_char(victim, pull=False)
    # 1stMud: strip all affects
    for af in list(victim["affect_list"]):
        affect_remove(victim, af)
    # 1stMud: victim->affected_by = victim->race->aff
    race_data = race_lookup(victim.get("race", "Human")) or {}
    victim["affected_by"] = dict(race_data.get("aff", {}))
    # 1stMud: for (i = 0; i < MAX_AC; i++) victim->armor[i] = 100
    victim["armor"] = (100, 100, 100, 100)
    # [PRIMESUD] 1stMud's affected_by/armor wipe above is correct upstream
    # only because the corpse took all equipment; PrimeSUD players keep
    # their gear on respawn (see make_corpse), so re-derive equipment-granted
    # armor, stats, and affect bits. affect_list is empty after the strip
    # above, so no spell affects re-apply.
    reset_char(victim)
    # 1stMud: victim->position = POS_RESTING
    victim["pos"] = "resting"
    # 1stMud: victim->hit = Max(1, victim->hit) (etc.)
    victim["hit"] = max(1, victim["hit"])
    victim["mana"] = max(1, victim["mana"])
    victim["move"] = max(1, victim.get("move", 100))

    # [PRIMESUD] respawn flavour text (1stmud has no equivalent)
    chprintln(victim, "You have been KILLED!!")
    chprintln(victim, "Your lifeforce ebbs away...")
    wait(DEATH_MSG_DELAY)
    chprintln(victim, "A distant warmth draws you back.")
    wait(DEATH_MSG_DELAY)
    chprintln(victim, "You come to your senses. Alive, but barely.")
    wait(DEATH_MSG_DELAY)
    chprintln(victim, "")
    from info import do_look  # lazy import to avoid circular dependency
    do_look(victim, [])

    # [PRIMESUD] save after every kill (1stmud only saves on level up)
    world.save_pending = True
    return corpse


def _extract_char(ch, pull=True):
    """Remove character from room/world (cf. 1stMud extract_char in handler.c).

    Args:
        ch (dict): Character to extract.
        pull (bool): True = fully remove (NPC death), False = teleport to altar (PC death).
    """
    # 1stMud extract_char: nuke_pets always; die_follower only on fPull
    nuke_pets(ch)
    ch["pet"] = None
    if pull:
        die_follower(ch)

    # 1stMud: stop_fighting(ch, true) -- redundant with raw_kill but harmless
    stop_fighting(ch, both=True)

    if pull:
        # NPC: remove from room and world
        room_mobs = world.rooms[ch["room"]]["mobs"]
        if ch["id"] in room_mobs:
            room_mobs.remove(ch["id"])
        del world.chars[ch["id"]]
    else:
        # PC: teleport to altar (R_STARTING_ROOM)
        # 1stMud: char_from_room(ch); char_to_room(ch, ROOM_VNUM_ALTAR)
        ch["room"] = R_STARTING_ROOM


def advance_level(player):
    """Roll HP/MP gains, grant practice and train (cf. 1stMud advance_level in update.c).
    [Verified: 11/07/2026]
    -- last_level play-time stamp not ported; [PRIMESUD] full heal/restore
    on level.

    Level increment and XP deduction happen in gain_exp before this is called,
    matching 1stMud's flow.

    Args:
        player (dict): Player state dict.
    """

    con  = get_curr_stat(player, "con")
    wis  = get_curr_stat(player, "wis")
    int_ = get_curr_stat(player, "int")

    # HP: (con_app.hitp + get_hp_gain) * 9/10, min 2  (cf. 1stMud advance_level in update.c;
    # get_hp_gain in multiclass.c rolls the best class die + per-class fuzz)
    add_hp = max(2, (CON_APP_HITP[con] + classes.get_hp_gain(player)) * 9 // 10)

    # MP: number_range(2, (2*INT + WIS)//5), halved for non-casters, * 9/10, min 2
    # (cf. 1stMud advance_level in update.c: if (!has_spells(ch)) add_mana /= 2)
    mp_hi  = max(2, (2 * int_ + wis) // 5)
    add_mp = randint(2, mp_hi)
    if not classes.has_spells(player):
        add_mp //= 2
    add_mp = max(2, add_mp * 9 // 10)

    # MV: number_range(1, (CON+DEX)//6) * 9/10, min 6  (cf. 1stMud advance_level in update.c)
    dex = get_curr_stat(player, "dex")
    mv_hi = max(1, (con + dex) // 6)
    add_mv = max(6, randint(1, mv_hi) * 9 // 10)

    add_prac = WIS_APP_PRACTICE[wis]

    player["perm_hit"]  += add_hp
    player["perm_mana"] += add_mp
    player["perm_move"] += add_mv
    player["max_hit"]   += add_hp
    player["max_mana"]  += add_mp
    player["max_move"]  += add_mv
    player["hit"]        = player["max_hit"]  # [PRIMESUD] 1stMud only adds to max; full heal for UX
    player["mana"]       = player["max_mana"]
    player["move"]       = player["max_move"]  # [PRIMESUD] full restore for UX
    player["practice"] += add_prac
    player["train"]    += 1

    # cf. 1stMud advance_level: quest gear rescales to the new level
    update_all_qobjs(player)
    # [PRIMESUD] Owned pets grow with their player; no separate pet XP track.
    from mob import scale_pet  # deferred: mob imports combat
    scale_pet(player)

    chprintln(player, "You gain " + count_str(add_hp, "hit point") + ", "
              + num_str(add_mp) + " mana, " + num_str(add_mv) + " move, and "
              + count_str(add_prac, "practice") + ".")
    learned = player.get("learned", {})
    for _sn, data in SKILL_TABLE:
        # cf. 1stMud advance_level: skill_level(ch, sn) == ch->level (class-aware)
        if skill_level(player, _sn) == player["level"]:
            kind = "spell" if data.get("spell_fun", "spell_null") != "spell_null" else "skill"
            # [PRIMESUD] verb by actionability: learned==0 -> "learn" (must
            # 'gain' it first; do_practice refuses unknown skills), else ->
            # "use" (known, practicable now). 1stMud prints "learn" only at
            # learned==1 and a false "use" at learned==0; ROM 2.4 has no such
            # message at all. See FIXES.md.
            verb = "learn" if learned.get(_sn, 0) == 0 else "use"
            chprintln(player, "{MYou can now " + verb + " the {W" + data["name"]
                      + "{M " + kind + ".{x")


def gain_exp(ch, gain):
    """Add XP to ch and level up as needed (cf. 1stMud gain_exp in update.c).
    [Verified: 02/07/2026] -- [PRIMESUD] per-level XP model (xp/xp_next) replaces
    1stMud cumulative exp; wiznet/announce and per-level save not ported.

    Args:
        ch (dict): Player state dict.
        gain (int): XP to add (may be negative for death penalty).
    """
    # cf. 1stMud gain_exp: cap at calc_max_level (HERO + remort count)
    if ch.get("is_npc") or ch.get("level", 1) >= classes.calc_max_level(ch):
        return
    # 1stMud: ch->exp = Max(exp_per_level(...), ch->exp + gain)
    # [PRIMESUD] floor at 0 (no creation-point system)
    ch["xp"] = max(0, ch["xp"] + gain)
    while (ch.get("level", 1) < classes.calc_max_level(ch)
           and ch["xp"] >= ch["xp_next"]):
        chprintln(ch, "{YYou raise a level!!{x")  # [PRIMESUD] highlight among combat output
        ch["level"] += 1
        ch["xp"]    -= ch["xp_next"]
        # 1stMud: if (ch->level >= LEVEL_HERO) "Congratulations, you are now a %s!"
        # (high_level_name: "HERO" at LEVEL_HERO, "HERO+n" above; immortal tiers not ported)
        if ch["level"] >= LEVEL_HERO:
            nm = "HERO" if ch["level"] == LEVEL_HERO else "HERO+" + num_str(ch["level"] - LEVEL_HERO)
            chprintln(ch, "Congratulations, you are now a " + nm + "!")
        advance_level(ch)


def is_same_group(ach, bch):
    """True if ach and bch share a group leader (cf. 1stMud is_same_group in act_comm.c).
    [Verified: 02/07/2026]

    Resolves leader pointers: if a char has a leader, use the leader for
    comparison.  A player and their pet/charmies share the player as
    leader, so they count as one group.

    Args:
        ach (dict): First character.
        bch (dict): Second character.

    Returns:
        bool: True if both share the same (resolved) leader.
    """
    if ach is None or bch is None:
        return False
    # 1stMud: if (ach->leader != NULL) ach = ach->leader;
    a_leader = ach.get("leader")
    if a_leader is not None:
        ach = world.chars.get(a_leader, ach)
    b_leader = bch.get("leader")
    if b_leader is not None:
        bch = world.chars.get(b_leader, bch)
    return ach is bch


# -- Group level limit (cf. 1stMud mud_info.group_lvl_limit, default 20) -------
GROUP_LVL_LIMIT = 20


def group_gain(ch, victim):
    """Award XP to ch's group for killing victim (cf. 1stMud group_gain in fight.c).
    [Verified: 04/07/2026] -- bonus-XP event and gquest hook not ported;
    [PRIMESUD] owned pets do not dilute player XP.

    Iterates all characters in the same room that share ch's group.  NPCs
    contribute to the group level pool (at half level) but do not receive XP;
    owned pets are excluded because they share their owner's progression.
    Each PC member receives XP proportional to their share of the total group
    levels.

    Args:
        ch (dict): Killer (player or mob).
        victim (dict): Defeated character.
    """
    if victim is ch:
        return

    chars = world.chars
    rs = world.rooms[ch["room"]]

    # -- Count members and group levels (cf. 1stMud group_gain pass 1)
    members = 0
    group_levels = 0
    # Collect group chars from room: player + room mobs
    room_chars = []
    player = chars.get(1)
    if player is not None and player["room"] == ch["room"]:
        room_chars.append(player)
    for mid in rs["mobs"]:
        mob = chars.get(mid)
        if mob is not None:
            room_chars.append(mob)

    for gch in room_chars:
        if is_same_group(gch, ch):
            members += 1
            # [PRIMESUD] Persistent pets scale with their owner and cannot be
            # ungrouped; charging half their level makes using one reduce XP.
            if not (gch["is_npc"]
                    and chars.get(gch.get("master"), {}).get("pet") == gch["id"]):
                group_levels += gch["level"] // 2 if gch["is_npc"] else gch["level"]

    if members == 0:
        members = 1
        group_levels = ch["level"]

    # -- Find highest level in group (cf. 1stMud group_gain pass 2)
    highest_level = 0
    for gch in room_chars:
        if is_same_group(gch, ch) and gch["level"] > highest_level:
            highest_level = gch["level"]

    # -- Award XP to each PC group member (cf. 1stMud group_gain pass 3)
    for gch in room_chars:
        if not is_same_group(gch, ch) or gch["is_npc"]:
            continue

        # 1stMud: level range check (group_lvl_limit)
        if (highest_level - gch["level"] >= GROUP_LVL_LIMIT
                or highest_level - gch["level"] <= -GROUP_LVL_LIMIT):
            chprintln(gch, "Your powers are useless to such an advanced group of adventurers.")
            # 1stMud: if IsNPC(gch) && gch->master: act to master
            # [PRIMESUD] skip (gch is always a PC here)
            continue

        xp = xp_compute(gch, victim, group_levels)

        # 1stMud: if (mud_info.bonus.status == BONUS_XP) ...
        # [PRIMESUD] skip bonus XP event (not ported)
        # [PRIMESUD] singular/plural fixed; 1stMud always prints "points"
        chprintln(gch, "You receive " + count_str(xp, "experience point") + ".")
        gain_exp(gch, xp)

        # 1stMud: quest mob check (IsQuester && quest.mob == victim);
        # [PRIMESUD] vnum match inside quest_kill_check
        quest_kill_check(gch, victim)
        # 1stMud: gquest target check (is_gqmob)
        gq_kill_check(gch, victim)

        # 1stMud: worn anti-align items zap after the kill's alignment shift
        # (1stMud checks ch, the killer, not gch)
        for slot in list(gch["equip"].keys()):
            obj = gch["equip"].get(slot)
            if obj is None:
                continue
            ef = item_extra_flags(obj, item_tpl(obj))
            if ((ef.get("anti_evil") and is_evil(ch))
                    or (ef.get("anti_good") and is_good(ch))
                    or (ef.get("anti_neutral") and is_neutral(ch))):
                act("You are zapped by $p.", gch, obj, None, TO_CHAR)
                act("$n is zapped by $p.", gch, obj, None, TO_ROOM)
                # 1stMud: obj_from_char + obj_to_room
                unequip_char(gch, slot)
                obj_remove(gch["inv"], obj)
                world.rooms[gch["room"]]["items"].append(obj)


def _get_size(ch):
    """Return numeric size rank for ch (cf. 1stMud ch->size)."""
    if ch["is_npc"]:
        return SIZE_RANK.get(MOB_DEFS[ch["tpl"]].get("size", "medium"), 2)
    return SIZE_RANK.get(ch.get("size", "medium"), 2)


def number_fuzzy(n):
    """Return n-1 (25%), n (50%), or n+1 (25%), floored at 1
    (cf. 1stMud number_fuzzy in db.c).
    [Verified: 03/07/2026]
    """
    r = randint(0, 3)
    if r == 0:
        n -= 1
    elif r == 3:
        n += 1
    return max(1, n)


def _exit_to(exit_val):
    """Return destination vnum from a plain-vnum or dict exit. [PRIMESUD]"""
    return exit_val["to"] if isinstance(exit_val, dict) else exit_val


# -- Do_Fun ports from fight.c ------------------------------------------------

def do_murder(ch, args, victim=None):
    """Attack a target with a yell for help (cf. 1stMud do_murder in fight.c).

    In ROM/Merc MUDs, ``kill`` was the normal PvE command while ``murder``
    was for attacking players -- hence the victim yell and the charm/pet
    guard (charmed mobs can't murder).  By 1stMud both run check_killer,
    so the practical difference is just the yell broadcast and the noprefix
    flag (can't trigger by abbreviation).
    [Verified: 19/07/2026]
    -- check_killer not ported; yell rendered locally.

    Args:
        ch (dict): Acting character.
        args (list): Target keyword.  Ignored when `victim` is given.
        victim (dict, optional): Pre-resolved target, for callers that
            already know it (e.g. a mob attacking the player in
            special.py) -- see do_backstab's `victim` param for why
            name-based lookup can't reach the player. [PRIMESUD]
    """
    if victim is None and not args:
        chprintln(ch, "Murder whom?")
        return None

    # 1stMud: if (IsAffected(ch, AFF_CHARM) || (IsNPC(ch) && ACT_PET)) return;
    if ch["affected_by"].get("charm"):
        return None

    if victim is None:
        rs = world.rooms[ch["room"]]
        mob_id = get_char_room(" ".join(args), rs["mobs"], world.chars, ch)
        if mob_id is None:
            chprintln(ch, "They aren't here.")
            return None
        victim = world.chars[mob_id]

    if victim is ch:
        chprintln(ch, "Suicide is a mortal sin.")
        return None

    if is_safe(ch, victim):
        return None

    # 1stMud: IsNPC(victim) && fighting && !is_same_group -> kill stealing
    if (victim["is_npc"] and victim.get("fighting") is not None
            and not is_same_group(ch, world.chars.get(victim["fighting"]))):
        chprintln(ch, "Kill stealing is not permitted.")
        return None

    if ch.get("pos") == "fighting":
        chprintln(ch, "You do the best you can!")
        return None

    WaitState(ch, PULSE_VIOLENCE)

    # 1stMud: do_yell(victim, "Help!  I am being attacked by <ch>!")
    # [PRIMESUD] no comms channels; rendered as a scream in the room
    # [PRIMESUD] third-person about victim -- flagged, plain chprintln kept per sweep scope
    victim_name = MOB_DEFS[victim["tpl"]]["short_descr"] if victim["is_npc"] else "someone"
    ch_name = ch.get("name", "someone")
    chprintln(ch, upper(victim_name) + " screams 'Help!  I am being attacked by "
              + ch_name + "!'")

    # [PRIMESUD] check_killer not ported
    multi_hit(ch, victim)
    return None


def do_suicide(ch, args):
    """Confirm-gated suicide (cf. 1stMud do_suicide in fight.c).
    [Verified: 04/07/2026] -- ROOM_ARENA/ROOM_SAFE check not ported.

    Args:
        ch (dict): Acting character.
        args (list): Unused.
    """
    if ch["fighting"] is not None:
        chprintln(ch, "You too busy!")
        return None

    # [PRIMESUD] ROOM_ARENA / ROOM_SAFE check not ported

    if not ch.get("confirm_suicide"):
        act("$g disapproves of the taking of your own life.", ch, type=TO_CHAR)
        chprintln(ch, "If you REALLY want to commit suicide, type 'suicide' again. :(")
        ch["confirm_suicide"] = True
    else:
        act("$n uses a small knife to slit $s own throat!", ch, type=TO_ROOM)
        act("You use a small knife to slit your own throat!", ch, type=TO_CHAR)
        ch["confirm_suicide"] = False
        raw_kill(ch, None)
    return None


def do_berserk(ch, args):
    """Go berserk for combat bonuses (cf. 1stMud do_berserk in fight.c).
    [Verified: 02/07/2026] -- "to mellow" typo fixed.

    Args:
        ch (dict): Acting character.
        args (list): Unused.
    """
    skill = get_skill(ch, GSN_BERSERK, ch["is_npc"])
    # 1stMud: skill 0, or NPC without OFF_BERSERK (PC can_use_skpell handled in get_skill)
    if skill == 0 or (ch["is_npc"] and not ch["off_flags"].get("berserk")):
        chprintln(ch, "You turn red in the face, but nothing happens.")
        return None

    # 1stMud: AFF_BERSERK bit, berserk affect, or frenzy affect
    frenzy_sn = None
    for _sn, _sk in SKILL_TABLE:
        if _sk["name"] == "frenzy":
            frenzy_sn = _sn
            break
    if (ch["affected_by"].get("berserk") or is_affected(ch, GSN_BERSERK)
            or (frenzy_sn is not None and is_affected(ch, frenzy_sn))):
        chprintln(ch, "You get a little madder.")
        return None

    if ch["affected_by"].get("calm"):
        # [PRIMESUD] "to mellow" is 1stMud's typo; fixed to "too"
        chprintln(ch, "You're feeling too mellow to berserk.")
        return None

    if ch.get("mana", 0) < 50:
        chprintln(ch, "You can't get up enough energy.")
        return None

    chance = skill
    if ch.get("pos") == "fighting":
        chance += 10

    hp_pct = 100 * ch["hit"] // max(1, ch.get("max_hit", 1))
    chance += 25 - hp_pct // 2

    if randint(1, 100) < chance:
        WaitState(ch, PULSE_VIOLENCE)
        ch["mana"] -= 50
        ch["move"] = ch.get("move", 0) // 2

        ch["hit"] += ch["level"] * 2
        ch["hit"] = min(ch["hit"], ch.get("max_hit", ch["hit"]))

        chprintln(ch, "Your pulse races as you are consumed by rage!")
        act("$n gets a wild look in $s eyes.", ch, type=TO_ROOM)
        check_improve(ch, GSN_BERSERK, True, 2)

        dur = number_fuzzy(ch["level"] // 8)
        mod_hr_dr = max(1, ch["level"] // 5)
        mod_ac = max(10, 10 * (ch["level"] // 5))

        af_base = {
            "where": "to_affects",
            "type": GSN_BERSERK,
            "level": ch["level"],
            "duration": dur,
            "bitvector": "berserk",
        }
        af_hr = dict(af_base)
        af_hr["location"] = "hitroll"
        af_hr["modifier"] = mod_hr_dr
        affect_to_char(ch, af_hr)

        af_dr = dict(af_base)
        af_dr["location"] = "damroll"
        af_dr["modifier"] = mod_hr_dr
        affect_to_char(ch, af_dr)

        af_ac = dict(af_base)
        af_ac["location"] = "ac"
        af_ac["modifier"] = mod_ac
        affect_to_char(ch, af_ac)
    else:
        WaitState(ch, 3 * PULSE_VIOLENCE)
        ch["mana"] -= 25
        ch["move"] = ch.get("move", 0) // 2
        chprintln(ch, "Your pulse speeds up, but nothing happens.")
        check_improve(ch, GSN_BERSERK, False, 2)
    return None


def do_bash(ch, args):
    """Shield bash a target (cf. 1stMud do_bash in fight.c).
    [Verified: 02/07/2026] -- carry_weight adjustments, kill-stealing, charm
    master, and check_killer not ported (noted inline).

    Args:
        ch (dict): Acting character.
        args (list): Optional target keyword.
    """
    chance = get_skill(ch, GSN_BASH, ch["is_npc"])
    # 1stMud: skill 0, or NPC without OFF_BASH (PC can_use_skpell handled in get_skill)
    if chance == 0 or (ch["is_npc"] and not ch["off_flags"].get("bash")):
        chprintln(ch, "Bashing? What's that?")
        return None

    if not args:
        victim_id = ch["fighting"]
        if victim_id is None:
            chprintln(ch, "But you aren't fighting anyone!")
            return None
        victim = world.chars[victim_id]
    else:
        rs = world.rooms[ch["room"]]
        victim_id = get_char_room(" ".join(args), rs["mobs"], world.chars, ch)
        if victim_id is None:
            chprintln(ch, "They aren't here.")
            return None
        victim = world.chars[victim_id]

    if POS_ORDER[victim.get("pos", "standing")] < POS_ORDER["fighting"]:
        act("You'll have to let $M get back up first.", ch, None, victim,
            TO_CHAR)
        return None

    if victim is ch:
        chprintln(ch, "You try to bash your brains out, but fail.")
        return None

    if is_safe(ch, victim):
        return None
    # [PRIMESUD] kill-stealing check not ported (single-player)
    # [PRIMESUD] charm master check not ported

    # 1stMud: carry_weight adjustments; [PRIMESUD] carry_weight not ported
    ch_size = _get_size(ch)
    v_size = _get_size(victim)
    if ch_size < v_size:
        chance += (ch_size - v_size) * 15
    else:
        chance += (ch_size - v_size) * 10

    chance += get_curr_stat(ch, "str")
    chance -= (get_curr_stat(victim, "dex") * 4) // 3
    chance -= get_armor(victim, AC_BASH) // 25

    # 1stMud: if (IsSet(OFF_FAST) || IsAffected(AFF_HASTE)) chance +/- ...
    if ch["off_flags"].get("fast") or ch["affected_by"].get("haste"):
        chance += 10
    if victim["off_flags"].get("fast") or victim["affected_by"].get("haste"):
        chance -= 30

    chance += ch["level"] - victim["level"]

    if not victim["is_npc"]:
        dodge_sk = get_skill(victim, GSN_DODGE)
        if chance < dodge_sk:
            chance -= 3 * (dodge_sk - chance)

    if randint(1, 100) < chance:
        act("$n sends you sprawling with a powerful bash!", ch, None, victim,
            TO_VICT)
        act("You slam into $N, and send $M flying!", ch, None, victim,
            TO_CHAR)
        act("$n sends $N sprawling with a powerful bash.", ch, None, victim,
            TO_NOTVICT)
        check_improve(ch, GSN_BASH, True, 1)

        DazeState(victim, 3 * PULSE_VIOLENCE)
        WaitState(ch, SKILLS[GSN_BASH]["beats"])
        victim["pos"] = "resting"
        dam = randint(2, 2 + 2 * ch_size + chance // 20)
        damage(ch, victim, dam, GSN_BASH, DAM_BASH, show=False)
    else:
        damage(ch, victim, 0, GSN_BASH, DAM_BASH, show=False)
        act("You fall flat on your face!", ch, None, victim, TO_CHAR)
        act("$n falls flat on $s face.", ch, None, victim, TO_NOTVICT)
        act("You evade $n's bash, causing $m to fall flat on $s face.", ch,
            None, victim, TO_VICT)
        check_improve(ch, GSN_BASH, False, 1)
        ch["pos"] = "resting"
        WaitState(ch, SKILLS[GSN_BASH]["beats"] * 3 // 2)

    # [PRIMESUD] check_killer not ported
    return None


def do_dirt(ch, args):
    """Kick dirt in opponent's eyes (cf. 1stMud do_dirt in fight.c).
    [Verified: 02/07/2026] -- kill-stealing, charm master, and check_killer
    not ported (noted inline).

    Args:
        ch (dict): Acting character.
        args (list): Optional target keyword.
    """
    chance = get_skill(ch, GSN_DIRT, ch["is_npc"])
    # 1stMud: skill 0, or NPC without OFF_KICK_DIRT (PC can_use_skpell handled in get_skill)
    if chance == 0 or (ch["is_npc"] and not ch["off_flags"].get("kick_dirt")):
        chprintln(ch, "You get your feet dirty.")
        return None

    if not args:
        victim_id = ch["fighting"]
        if victim_id is None:
            chprintln(ch, "But you aren't in combat!")
            return None
        victim = world.chars[victim_id]
    else:
        rs = world.rooms[ch["room"]]
        victim_id = get_char_room(" ".join(args), rs["mobs"], world.chars, ch)
        if victim_id is None:
            chprintln(ch, "They aren't here.")
            return None
        victim = world.chars[victim_id]

    if victim["affected_by"].get("blind"):
        act("$E's already been blinded.", ch, None, victim, TO_CHAR)
        return None

    if victim is ch:
        chprintln(ch, "Very funny.")
        return None

    if is_safe(ch, victim):
        return None
    # [PRIMESUD] kill-stealing check not ported (single-player)
    # [PRIMESUD] charm master check not ported

    chance += get_curr_stat(ch, "dex")
    chance -= 2 * get_curr_stat(victim, "dex")

    if ch["off_flags"].get("fast") or ch["affected_by"].get("haste"):
        chance += 10
    if victim["off_flags"].get("fast") or victim["affected_by"].get("haste"):
        chance -= 25

    chance += (ch["level"] - victim["level"]) * 2

    if chance % 5 == 0:
        chance += 1

    # Sector-type modifier (cf. 1stMud switch on sector_type)
    room_def = ROOM_DEFS.get(ch["room"], {})
    sector = room_def.get("sector", "field")
    if sector == "inside":
        chance -= 20
    elif sector == "city":
        chance -= 10
    elif sector == "field" or sector == "path":
        chance += 5
    elif sector == "mountain" or sector == "swamp":
        chance -= 10
    elif sector in ("water_swim", "water_noswim", "air"):
        chance = 0
    elif sector == "desert":
        chance += 10

    if chance == 0:
        chprintln(ch, "There isn't any dirt to kick.")
        return None

    if randint(1, 100) < chance:
        act("$n is blinded by the dirt in $s eyes!", victim, None, None,
            TO_ROOM)
        act("$n kicks dirt in your eyes!", ch, None, victim, TO_VICT)
        damage(ch, victim, randint(2, 5), GSN_DIRT, DAM_NONE, show=False)
        chprintln(victim, "You can't see a thing!")
        check_improve(ch, GSN_DIRT, True, 2)
        WaitState(ch, SKILLS[GSN_DIRT]["beats"])

        af = {
            "where": "to_affects",
            "type": GSN_DIRT,
            "level": ch["level"],
            "duration": 0,
            "location": "hitroll",
            "modifier": -4,
            "bitvector": "blind",
        }
        affect_to_char(victim, af)
    else:
        damage(ch, victim, 0, GSN_DIRT, DAM_NONE, show=True)
        check_improve(ch, GSN_DIRT, False, 2)
        WaitState(ch, SKILLS[GSN_DIRT]["beats"])

    # [PRIMESUD] check_killer not ported
    return None


def do_trip(ch, args):
    """Trip an opponent (cf. 1stMud do_trip in fight.c).
    [Verified: 03/07/2026] -- kill-stealing and check_killer not ported
    (noted inline).

    Args:
        ch (dict): Acting character.
        args (list): Optional target keyword.
    """
    chance = get_skill(ch, GSN_TRIP, ch["is_npc"])
    # 1stMud: skill 0, or NPC without OFF_TRIP (PC can_use_skpell handled in get_skill)
    if chance == 0 or (ch["is_npc"] and not ch["off_flags"].get("trip")):
        chprintln(ch, "Tripping?  What's that?")
        return None

    if not args:
        victim_id = ch["fighting"]
        if victim_id is None:
            chprintln(ch, "But you aren't fighting anyone!")
            return None
        victim = world.chars[victim_id]
    else:
        rs = world.rooms[ch["room"]]
        victim_id = get_char_room(" ".join(args), rs["mobs"], world.chars, ch)
        if victim_id is None:
            chprintln(ch, "They aren't here.")
            return None
        victim = world.chars[victim_id]

    if is_safe(ch, victim):
        return None
    # [PRIMESUD] kill-stealing check not ported (single-player)

    if victim["affected_by"].get("flying"):
        act("$S feet aren't on the ground.", ch, None, victim, TO_CHAR)
        return None

    if POS_ORDER[victim.get("pos", "standing")] < POS_ORDER["fighting"]:
        act("$N is already down.", ch, None, victim, TO_CHAR)
        return None

    if victim is ch:
        chprintln(ch, "You fall flat on your face!")
        WaitState(ch, 2 * SKILLS[GSN_TRIP]["beats"])
        act("$n trips over $s own feet!", ch, type=TO_ROOM)
        return None

    # cf. 1stMud: AFF_CHARM && ch->master == victim -> "beloved master"
    if (ch["affected_by"].get("charm")
            and ch.get("master") == victim.get("id")):
        act("$N is your beloved master.", ch, None, victim, TO_CHAR)
        return None

    ch_size = _get_size(ch)
    v_size = _get_size(victim)
    if ch_size < v_size:
        chance += (ch_size - v_size) * 10

    chance += get_curr_stat(ch, "dex")
    chance -= get_curr_stat(victim, "dex") * 3 // 2

    if ch["off_flags"].get("fast") or ch["affected_by"].get("haste"):
        chance += 10
    if victim["off_flags"].get("fast") or victim["affected_by"].get("haste"):
        chance -= 20

    chance += (ch["level"] - victim["level"]) * 2

    if randint(1, 100) < chance:
        act("$n trips you and you go down!", ch, None, victim, TO_VICT)
        # [PRIMESUD] "$E goes down" fixes 1stMud's repeated "$N ... $N goes down"
        act("You trip $N and $E goes down!", ch, None, victim, TO_CHAR)
        act("$n trips $N, sending $M to the ground.", ch, None, victim, TO_NOTVICT)
        check_improve(ch, GSN_TRIP, True, 1)

        DazeState(victim, 2 * PULSE_VIOLENCE)
        WaitState(ch, SKILLS[GSN_TRIP]["beats"])
        victim["pos"] = "resting"
        dam = randint(2, 2 + 2 * v_size)
        damage(ch, victim, dam, GSN_TRIP, DAM_BASH, show=True)
        # Stance trip (cf. 1stMud do_trip fight.c:3187-3194)
        if (randint(1, 100) < chance - 5
                and valid_stance(get_stance(victim, STANCE_CURRENT))):
            set_stance(victim, STANCE_CURRENT, STANCE_NONE)
            act("You trip up $N's stance!", ch, None, victim, TO_CHAR)
            act("$n trips up $N's stance!", ch, None, victim, TO_NOTVICT)
            act("$n trips up your stance!", ch, None, victim, TO_VICT)
    else:
        damage(ch, victim, 0, GSN_TRIP, DAM_BASH, show=True)
        WaitState(ch, SKILLS[GSN_TRIP]["beats"] * 2 // 3)
        check_improve(ch, GSN_TRIP, False, 1)

    # [PRIMESUD] check_killer not ported
    return None


def do_flee(ch, args):
    """Attempt to flee from combat (cf. 1stMud do_flee in fight.c).
    [Verified: 20/07/2026] -- arena check not ported; [PRIMESUD] auto-look
    after fleeing.

    Works for both players and NPCs.

    Args:
        ch (dict): Acting character.
        args (list): Unused.
    """
    from info import do_look  # lazy import to avoid circular dependency

    if ch["fighting"] is None:
        if ch.get("pos") == "fighting":
            ch["pos"] = "standing"
        if not ch.get("is_npc"):
            chprintln(ch, "You aren't fighting anyone.")
        return None

    # [PRIMESUD] arena check not ported

    was_in = ch["room"]
    exits = ROOM_DEFS[was_in].get("exits", {})
    is_npc = ch.get("is_npc", False)

    for _attempt in range(6):
        # 1stMud: door = number_door() -- random of all 6 directions;
        # a missing exit wastes the attempt
        door = ("n", "e", "s", "w", "u", "d")[randint(0, 5)]
        exit_val = exits.get(door)
        if exit_val is None:
            continue

        if isinstance(exit_val, dict) and exit_val.get("closed"):
            continue

        # 1stMud: daze blocks flee through this exit
        if ch.get("daze", 0) > 0 and randint(0, ch["daze"]) != 0:
            continue

        dest = _exit_to(exit_val)
        if dest not in ROOM_DEFS:
            continue

        # NPCs can't flee into NO_MOB rooms
        if is_npc and ROOM_DEFS[dest].get("flags", {}).get("no_mob"):
            continue

        ch["room"] = dest
        if is_npc:
            ch_id = ch["id"]
            old_mobs = world.rooms.get(was_in, {}).get("mobs", [])
            if ch_id in old_mobs:
                old_mobs.remove(ch_id)
            world.rooms[dest]["mobs"].append(ch_id)

        # 1stMud: ch->in_room = was_in; act("$n has fled!", TO_ROOM); restore
        ch["room"] = was_in
        act("$n has fled!", ch, type=TO_ROOM)
        ch["room"] = dest

        if not is_npc:
            chprintln(ch, "You flee from combat!")
            # 1stMud: thieves sneak away free with chance 3 * (level / 2)
            if classes.is_class(ch, classes.CLASS_THIEF) and randint(1, 100) < 3 * (ch["level"] // 2):
                chprintln(ch, "You snuck away safely.")
            else:
                chprintln(ch, "You lost 10 exp.")
                gain_exp(ch, -10)

        stop_fighting(ch, both=True)
        if not is_npc:
            do_look(ch, ["auto"])  # [PRIMESUD] flee-look; "auto" so brief mode applies
        return None

    chprintln(ch, "PANIC! You couldn't escape!")
    return None


def do_rescue(ch, args):
    """Rescue another character from combat (cf. 1stMud do_rescue in fight.c).

    [PRIMESUD] Single-player: rescuing NPCs is blocked by 1stMud (!IsNPC(ch) &&
    IsNPC(victim) -> "Doesn't need your help!"). Ported for fidelity but largely
    a no-op in single-player.
    [Verified: 04/07/2026] -- check_killer not ported.

    Args:
        ch (dict): Acting character.
        args (list): Target keyword.
    """
    if not args:
        chprintln(ch, "Rescue whom?")
        return None

    rs = world.rooms[ch["room"]]
    victim_id = get_char_room(" ".join(args), rs["mobs"], world.chars, ch)
    if victim_id is None:
        chprintln(ch, "They aren't here.")
        return None
    victim = world.chars[victim_id]

    if victim is ch:
        chprintln(ch, "What about fleeing instead?")
        return None

    # 1stMud: if (!IsNPC(ch) && IsNPC(victim)) "Doesn't need your help!"
    if not ch["is_npc"] and victim["is_npc"]:
        chprintln(ch, "Doesn't need your help!")
        return None

    if ch["fighting"] == victim_id:
        chprintln(ch, "Too late.")
        return None

    fch_id = victim["fighting"]
    if fch_id is None:
        chprintln(ch, "That person is not fighting right now.")
        return None
    fch = world.chars.get(fch_id)
    if fch is None:
        chprintln(ch, "That person is not fighting right now.")
        return None

    # 1stMud: IsNPC(fch) && !is_same_group(ch, victim) -> kill stealing
    if fch.get("is_npc") and not is_same_group(ch, victim):
        chprintln(ch, "Kill stealing is not permitted.")
        return None

    WaitState(ch, SKILLS[GSN_RESCUE]["beats"])
    skill_pct = get_skill(ch, GSN_RESCUE, ch["is_npc"])
    if randint(1, 100) > skill_pct:
        chprintln(ch, "You fail the rescue.")
        check_improve(ch, GSN_RESCUE, False, 1)
        return None

    act("You rescue $N!", ch, None, victim, TO_CHAR)
    act("$n rescues you!", ch, None, victim, TO_VICT)
    act("$n rescues $N!", ch, None, victim, TO_NOTVICT)
    check_improve(ch, GSN_RESCUE, True, 1)

    stop_fighting(fch, both=False)
    stop_fighting(victim, both=False)

    # [PRIMESUD] check_killer not ported
    set_fighting(ch, fch)
    set_fighting(fch, ch)
    return None


def disarm(ch, victim):
    """Remove victim's weapon (cf. 1stMud disarm in fight.c).
    [Verified: 03/08/2026] -- ROOM_ARENA keep-item branch not ported;
    can_see_obj gate on the NPC pickup not modeled (mob visibility).

    Args:
        ch (dict): Attacker.
        victim (dict): Defender whose weapon is removed.
    """
    wobj = victim["equip"].get("wield")
    if wobj is None:
        return

    obj_tpl = item_tpl(wobj)
    flags = item_extra_flags(wobj, obj_tpl)
    if flags.get("noremove"):
        act("$S weapon won't budge!", ch, None, victim, TO_CHAR)
        act("$n tries to disarm you, but your weapon won't budge!", ch, None, victim, TO_VICT)
        act("$n tries to disarm $N, but fails.", ch, None, victim, TO_NOTVICT)
        return

    act("$n DISARMS you and sends your weapon flying!", ch, None, victim, TO_VICT)
    act("You disarm $N!", ch, None, victim, TO_CHAR)
    act("$n disarms $N!", ch, None, victim, TO_NOTVICT)

    # 1stMud: obj_from_char -- unequip (reverses stat/AC modifiers), off char
    unequip_char(victim, "wield")
    obj_remove(victim["inv"], wobj)

    # 1stMud: nodrop/inventory (or ROOM_ARENA, not ported) -> stays with victim
    if flags.get("nodrop") or flags.get("inventory"):
        victim["inv"].append(wobj)
    else:
        world.rooms[victim["room"]]["items"].append(wobj)
        # 1stMud: if IsNPC && wait==0 && can_see_obj -> get_obj (picks up to
        # inventory; does NOT re-wield)
        if victim["is_npc"] and victim.get("wait", 0) == 0:
            obj_remove(world.rooms[victim["room"]]["items"], wobj)
            victim["inv"].append(wobj)
            act("$n gets $p.", victim, wobj, None, TO_ROOM)


def do_disarm(ch, args):
    """Attempt to disarm opponent's weapon (cf. 1stMud do_disarm in fight.c).
    [Verified: 03/08/2026] -- check_killer and act_sound (skill sounds,
    globally unported) not ported.

    Args:
        ch (dict): Acting character.
        args (list): Unused.
    """
    chance = get_skill(ch, GSN_DISARM, ch["is_npc"])
    if chance == 0:
        chprintln(ch, "You don't know how to disarm opponents.")
        return None

    hth = 0
    if ch["equip"].get("wield") is None:
        hth = get_skill(ch, GSN_HAND_TO_HAND, ch["is_npc"])
        # 1stMud: unarmed NPCs also need OFF_DISARM
        if hth == 0 or (ch["is_npc"] and not ch["off_flags"].get("disarm")):
            chprintln(ch, "You must wield a weapon to disarm.")
            return None

    victim_id = ch["fighting"]
    if victim_id is None:
        chprintln(ch, "You aren't fighting anyone.")
        return None
    victim = world.chars[victim_id]

    if victim["equip"].get("wield") is None:
        chprintln(ch, "Your opponent is not wielding a weapon.")
        return None

    ch_weapon_sn, _ = _get_weapon_sn(ch)
    vict_weapon_sn, _ = _get_weapon_sn(victim)
    ch_weapon = _get_weapon_skill(ch, ch_weapon_sn)
    vict_weapon = _get_weapon_skill(victim, vict_weapon_sn)
    ch_vict_weapon = _get_weapon_skill(ch, vict_weapon_sn)

    if ch["equip"].get("wield") is None:
        chance = chance * hth // 150
    else:
        chance = chance * ch_weapon // 100

    chance += (ch_vict_weapon // 2 - vict_weapon) // 2

    chance += get_curr_stat(ch, "dex")
    chance -= 2 * get_curr_stat(victim, "str")

    chance += (ch["level"] - victim["level"]) * 2

    WaitState(ch, SKILLS[GSN_DISARM]["beats"])
    if randint(1, 100) < chance:
        disarm(ch, victim)
        if not ch["is_npc"]:
            check_improve(ch, GSN_DISARM, True, 1)
    else:
        act("You fail to disarm $N.", ch, None, victim, TO_CHAR)
        act("$n tries to disarm you, but fails.", ch, None, victim, TO_VICT)
        act("$n tries to disarm $N, but fails.", ch, None, victim, TO_NOTVICT)
        if not ch["is_npc"]:
            check_improve(ch, GSN_DISARM, False, 1)

    # [PRIMESUD] check_killer not ported
    return None


def do_surrender(ch, args):
    """Surrender to current opponent (cf. 1stMud do_surrender in fight.c).
    [Verified: 19/07/2026].

    Args:
        ch (dict): Acting character.
        args (list): Unused.
    """
    mob_id = ch["fighting"]
    if mob_id is None:
        chprintln(ch, "But you're not fighting!")
        return None

    mob = world.chars.get(mob_id)
    if mob is None:
        stop_fighting(ch, both=False)
        chprintln(ch, "But you're not fighting!")
        return None

    act("You surrender to $N!", ch, None, mob, TO_CHAR)
    act("$n surrenders to you!", ch, None, mob, TO_VICT)
    act("$n tries to surrender to $N!", ch, None, mob, TO_NOTVICT)

    stop_fighting(ch, both=True)

    # 1stMud: if (!IsNPC(ch) && IsNPC(mob) && (!HasTriggerMob(mob, TRIG_SURR)
    # || !p_percent_trigger(mob, NULL, NULL, ch, NULL, NULL, TRIG_SURR)))
    # mob resumes attack. percent_trigger() already returns False when the
    # mob carries no "surr" trigger, so a single call covers both halves of
    # the upstream condition (cf. mobprog.py kill_trigger/death_trigger for
    # the same call convention).
    if not ch["is_npc"] and mob["is_npc"]:
        from mobprog import percent_trigger  # deferred: keep mobprog off the boot path
        if not percent_trigger(mob, ch, None, None, "surr"):
            act("$N seems to ignore your cowardly act!", ch, None, mob, TO_CHAR)
            multi_hit(mob, ch)
    return None


def do_slay(ch, args):
    """Immortal instant-kill (cf. 1stMud do_slay in fight.c).

    [PRIMESUD] No immortal system, but ported for completeness. Could be
    used as a debug/GM command.
    [Verified: 04/07/2026] -- trust check and TO_VICT/TO_NOTVICT messages not
    ported (mob victims never see output).

    Args:
        ch (dict): Acting character.
        args (list): Target keyword.
    """
    if not args:
        chprintln(ch, "Slay whom?")
        return None

    rs = world.rooms[ch["room"]]
    mob_id = get_char_room(" ".join(args), rs["mobs"], world.chars, ch)
    if mob_id is None:
        chprintln(ch, "They aren't here.")
        return None

    victim = world.chars[mob_id]
    if victim is ch:
        chprintln(ch, "Suicide is a mortal sin.")
        return None

    # 1stMud: trust-level check; [PRIMESUD] no trust system
    act("You slay $M in cold blood!", ch, None, victim, TO_CHAR)
    raw_kill(victim, ch)
    return None


def do_sskill(ch, args):
    """Display fighting stance skills (cf. 1stMud do_sskill in fight.c).

    Args:
        ch (dict): Acting character.
        args (list): Unused.
    """
    # [PRIMESUD] simple header; 1stMud centers via stringf/draw_line
    chprintln(ch, "{w--{W[ {RFighting Stances{W ]{w--{x")
    for i in range(MAX_STANCE):
        name, stance, prereq = STANCE_TABLE[i][0], STANCE_TABLE[i][1], STANCE_TABLE[i][2]
        if prereq[0] == STANCE_NONE:
            continue

        if prereq[0] == STANCE_NORMAL:
            chprintln(ch, pad_right(name, 9) + ": {Y" + num_str(get_stance(ch, stance)) + "%{x")
            continue

        if prereq[0] == STANCE_CURRENT:
            chprintln(ch, pad_right(name, 9) + ": {R"
                      + stance_name(get_stance(ch, stance)) + "{x")
            continue

        if (get_stance(ch, prereq[0]) >= 200
                and get_stance(ch, prereq[1]) >= 200):
            chprintln(ch, pad_right(name, 9) + ": {Y" + num_str(get_stance(ch, stance)) + "%{x")
        else:
            chprintln(ch, pad_right(name, 9) + ": {yrequires master in "
                      + stance_name(prereq[0]) + " and " + stance_name(prereq[1]) + ".{x")
    chprintln(ch, "{w----{x")
    return None


def show_available_stances(ch, n_fun):
    """List stances ch can currently use (cf. 1stMud show_available_stances in fight.c).

    Args:
        ch (dict): Acting character.
        n_fun (str): Invoking command name for the syntax line.
    """
    # cf. 1stMud cmd_syntax(ch, NULL, n_fun, "<stance>", NULL)
    chprintln(ch, "Syntax: " + n_fun + " <stance>")
    names = []
    for i in range(MAX_STANCE):
        stance, prereq = STANCE_TABLE[i][1], STANCE_TABLE[i][2]
        if not valid_stance(stance):
            continue
        if stance == STANCE_NORMAL:
            continue  # [PRIMESUD] normal stance is internal/NPC-only
        if prereq[0] <= STANCE_NORMAL:
            names.append(STANCE_TABLE[i][0])
        elif (get_stance(ch, prereq[0]) >= 200
                and get_stance(ch, prereq[1]) >= 200):
            names.append(STANCE_TABLE[i][0])
    if not names:
        chprintln(ch, "Valid stances are: none!")
    else:
        chprintln(ch, "Valid stances are:  " + " ".join(names) + ".")
    return None


def _stance_status(ch):
    """Show current stance, autostance, and valid stances. [PRIMESUD]

    Args:
        ch (dict): Acting character.
    """
    cur = get_stance(ch, STANCE_CURRENT)
    auto = get_stance(ch, STANCE_AUTODROP)
    if valid_stance(cur):
        chprintln(ch, "Stance    : {Y" + stance_name(cur) + "{x ("
                  + num_str(get_stance(ch, cur)) + "%)")
    else:
        chprintln(ch, "Stance    : {wnone{x")
    if valid_stance(auto):
        chprintln(ch, "Autostance: {Y" + stance_name(auto) + "{x")
    else:
        chprintln(ch, "Autostance: {wnone{x")
    show_available_stances(ch, "stance")
    chprintln(ch, "'stance none' relaxes; see 'sskill' and 'help stancetable'.")


def do_stance(ch, args):
    """Set, clear, or show fighting stance (cf. 1stMud do_stance in fight.c).

    [PRIMESUD] Deviates from 1stMud's bare-argument toggle: bare 'stance'
    shows stance status, and 'stance none' relaxes (1stMud toggled into and
    out of the normal stance).  The normal stance is hidden from players
    but kept for NPCs.

    Args:
        ch (dict): Acting character.
        args (list): Optional stance name or 'none'.
    """
    if not args:
        # [PRIMESUD] status screen; 1stMud toggled normal stance here
        _stance_status(ch)
        return None

    if args[0] == "none":
        # [PRIMESUD] explicit relax, replacing 1stMud's bare toggle-off
        if not valid_stance(get_stance(ch, STANCE_CURRENT)):
            chprintln(ch, "You are not in a fighting stance.")
            return None
        set_stance(ch, STANCE_CURRENT, STANCE_NONE)
        chprintln(ch, "You relax from your fighting stance.")
        act("$n relaxes from $s fighting stance.", ch, type=TO_ROOM)
        return None

    if valid_stance(get_stance(ch, STANCE_CURRENT)):
        chprintln(ch, "You cannot change stances until you come up from the one you are currently in.")
        return None

    i = stance_lookup(args[0])

    # [PRIMESUD] normal stance is internal/NPC-only; hide from players
    if i != -1 and STANCE_TABLE[i][1] == STANCE_NORMAL and not ch.get("is_npc"):
        i = -1

    if i == -1 or not valid_stance(STANCE_TABLE[i][1]):
        show_available_stances(ch, "stance")
        return None

    if not can_use_stance(ch, STANCE_TABLE[i][1]):
        chprintln(ch, "You need to master " + stance_name(STANCE_TABLE[i][2][0])
                  + " and " + stance_name(STANCE_TABLE[i][2][1]) + " stances to use "
                  + STANCE_TABLE[i][0] + ".")
        return None

    set_stance(ch, STANCE_CURRENT, STANCE_TABLE[i][1])

    chprintln(ch, STANCE_TABLE[i][3])
    act(STANCE_TABLE[i][4], ch, type=TO_ROOM)

    if ch.get("is_npc"):
        set_stance(ch, STANCE_TABLE[i][1], min(ch["level"] * 4 // 2, 200))
    return None


def do_autostance(ch, args):
    """Set auto-stance on combat start (cf. 1stMud do_autostance in fight.c).

    Args:
        ch (dict): Acting character.
        args (list): Optional stance name or 'none'.
    """
    if ch.get("is_npc"):
        return None

    arg = args[0] if args else ""

    if arg == "none":
        chprintln(ch, "You no longer autostance.")
        set_stance(ch, STANCE_AUTODROP, STANCE_NONE)
        return None

    i = stance_lookup(arg)

    # [PRIMESUD] normal stance is internal/NPC-only; hide from players
    if i != -1 and STANCE_TABLE[i][1] == STANCE_NORMAL:
        i = -1

    if i == -1 or not valid_stance(STANCE_TABLE[i][1]):
        show_available_stances(ch, "autostance")
        return None

    if not can_use_stance(ch, STANCE_TABLE[i][1]):
        chprintln(ch, "You need to master " + stance_name(STANCE_TABLE[i][2][0])
                  + " and " + stance_name(STANCE_TABLE[i][2][1]) + " stances to use "
                  + STANCE_TABLE[i][0] + ".")
        return None

    set_stance(ch, STANCE_AUTODROP, STANCE_TABLE[i][1])

    chprintln(ch, "You now autostance to " + STANCE_TABLE[i][0] + ".")
    return None
