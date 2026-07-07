"""Movement, doors, and recall command handlers."""

from classes import is_class
from handler import (can_see_room, chprintln, act, TO_CHAR, TO_ROOM, TO_VICT,
                     get_char_room, is_awake, is_name, affect_strip,
                     affect_to_char)
from combat import stop_fighting
from skill_utils import WaitState, check_improve, get_skill
from stances import valid_stance, get_stance, STANCE_CURRENT
from config import (EXIT_ORDER, EXIT_NAMES, REV_DIR, DIR_ALIASES,
                    MOVEMENT_LOSS, POS_ORDER,
                    SECT_AIR, SECT_WATER_NOSWIM,
                    R_RECALL, PULSE_PER_SECOND)
from info import do_look, find_path_to_area
from picker import pick_from
from quest import quest_room_check
from skills_table import (GSN_RECALL, GSN_PICK_LOCK, GSN_SNEAK, GSN_HIDE,
                          GSN_INVIS, GSN_MASS_INVIS, SKILLS)
from item import (get_obj_list, get_obj_here, create_object, obj_vnum,
                  item_container_flags, set_item_container_flag,
                  promote_obj, item_type as _item_type)
from terminal import tprint
from urandom import randint
import world
from world import ROOM_DEFS, ITEM_DEFS


def _exit_to(exit_val):
    """Return destination vnum from a plain-vnum or dict exit."""
    return exit_val["to"] if isinstance(exit_val, dict) else exit_val


def _close_auto_door(ch, auto_door):
    """Re-close (and re-lock) a door move_char auto-opened, unless noclose. [PRIMESUD]

    Args:
        ch (dict): Moving character.
        auto_door: (exit_dict, rev_exit_dict_or_None, keyword, relock) from
            move_char's auto-open, or None if no door was auto-opened.
    """
    if auto_door is None:
        return
    orig_exit, rev_exit, keyword, relock = auto_door
    if orig_exit.get("noclose"):
        return
    orig_exit["closed"] = True
    if rev_exit is not None:
        rev_exit["closed"] = True
    if relock:
        orig_exit["locked"] = True
        if rev_exit is not None:
            rev_exit["locked"] = True
        chprintln(ch, "You close and lock the " + keyword + " behind you.")
    else:
        chprintln(ch, "You close the " + keyword + " behind you.")


def _has_boat(ch):
    """Return True if ch carries a boat item (cf. 1stMud ITEM_BOAT check in move_char).

    Direct children only -- matches 1stMud carrying_first (act_move.c:131),
    which does not recurse into containers.
    """
    from world import ITEM_DEFS
    for obj in ch.get("inv", []):
        vnum = obj.get("vnum") if isinstance(obj, dict) else obj
        if ITEM_DEFS.get(vnum, {}).get("type") == "boat":
            return True
    for obj in ch.get("equip", {}).values():
        if obj is not None:
            vnum = obj.get("vnum") if isinstance(obj, dict) else obj
            if ITEM_DEFS.get(vnum, {}).get("type") == "boat":
                return True
    return False


def move_char(ch, direction):
    """Move a character through an exit (cf. 1stMud move_char in act_move.c).

    Actor-generic: players get full checks plus room display; mobs (wander
    via mobile_update, follower recursion) get leave/arrive acts and
    room-list bookkeeping. Followers recurse into move_char, matching
    1stMud's move_char(fch, door, true).

    Checks: exit existence, visibility, closed doors (with pass_door /
    nopass), charm anchor, and for players: guild rooms, sector
    restrictions (air, water), movement-point cost, haste/slow modifiers.

    Position gate handled by command table (do_north etc. have
    min_pos = "standing").

    A closed door blocking a player's path is opened automatically
    (unlocked first if the player carries its key), then re-closed and
    re-locked (unless noclose) once the player and any followers are
    through -- no 1stMud equivalent. [PRIMESUD]

    [Verified: 03/07/2026; quest_room_check moved after follower loop to
    match 1stMud order and re-verified same day; [PRIMESUD] auto-door
    added 04/07/2026, auto-unlock with key added 05/07/2026] --
    private-room / area-closed checks, area entry
    sound, and exit/entry/greet progs not ported (see comments).

    Args:
        ch (dict): Moving character (player or mob instance).
        direction (str): Single-char direction key (n/e/s/w/u/d).
    """
    # -- p_exit_trigger (mob/obj/room progs) not ported --

    in_room = ROOM_DEFS[ch["room"]]
    exits = in_room.get("exits", {})
    is_npc = ch.get("is_npc", False)

    if direction not in exits:
        chprintln(ch, "Alas, you cannot go that way.")
        return

    exit_val = exits[direction]
    dest = _exit_to(exit_val)
    if dest not in ROOM_DEFS:
        chprintln(ch, "Alas, you cannot go that way.")
        return
    to_room = ROOM_DEFS[dest]

    if not can_see_room(ch, dest):
        chprintln(ch, "Alas, you cannot go that way.")
        return

    aff = ch.get("affected_by", {})

    # -- Closed door (with pass_door / nopass) --
    auto_door = None
    pending_door = None
    is_exit_dict = isinstance(exit_val, dict)
    if is_exit_dict and exit_val.get("closed"):
        if not aff.get("pass_door") or exit_val.get("nopass"):
            # 1stMud act "$d": first word of exit keyword, "door" if unset
            keyword = exit_val.get("keyword")
            keyword = keyword.split()[0] if keyword else "door"
            # [PRIMESUD] auto-door: open door (unlocking with a carried key
            # if needed), re-close/re-lock after moving; keep door/lock
            # semantics in sync with do_open/do_unlock
            if is_npc:
                chprintln(ch, "The " + keyword + " is closed.")
                return
            needs_unlock = False
            if exit_val.get("locked"):
                key = exit_val.get("key")
                if key is None or not _has_key(ch, key):
                    chprintln(ch, "The " + keyword + " is locked.")
                    return
                needs_unlock = True
            # open deferred until the remaining move checks pass, so a
            # failed move (charm, guild, sector, exhaustion) leaves the
            # door untouched
            pending_door = (keyword, needs_unlock)

    # -- Charm anchor (cf. 1stMud AFF_CHARM && master in same room) --
    if aff.get("charm") and ch.get("master") is not None:
        master = world.chars.get(ch["master"])
        if master is not None and master.get("room") == ch["room"]:
            chprintln(ch, "What?  And leave your beloved master?")
            return

    # -- Private room / area closed checks not ported --

    if not is_npc:
        # -- Guild room (cf. 1stMud act_move.c: to_room->guild + is_class) --
        # "guild" tuple patched onto rooms by patch_1stmud_deltas.py;
        # Paladin/Ranger share the Cleric/Warrior guilds (CLASS_PLAN.md).
        allowed = to_room.get("guild")
        if allowed is not None:
            member = False
            for cl in allowed:
                if is_class(ch, cl):
                    member = True
                    break
            if not member:
                chprintln(ch, "You aren't allowed in there.")
                return

        # -- Sector: air --
        in_sect = in_room.get("sector", "inside")
        to_sect = to_room.get("sector", "inside")
        if in_sect == SECT_AIR or to_sect == SECT_AIR:
            if not aff.get("flying"):
                chprintln(ch, "You can't fly.")
                return

        # -- Sector: deep water (need boat or flying) --
        if (in_sect == SECT_WATER_NOSWIM or to_sect == SECT_WATER_NOSWIM) \
                and not aff.get("flying"):
            found = _has_boat(ch)
            if not found:
                chprintln(ch, "You need a boat to go there.")
                return

        # -- Movement point cost --
        move_cost = (MOVEMENT_LOSS.get(in_sect, 1)
                     + MOVEMENT_LOSS.get(to_sect, 1)) // 2
        if aff.get("flying") or aff.get("haste"):
            move_cost //= 2
        if aff.get("slow"):
            move_cost *= 2
        if ch.get("move", 0) < move_cost:
            chprintln(ch, "You are too exhausted.")
            return

        WaitState(ch, 1)
        ch["move"] = ch.get("move", 0) - move_cost

    # [PRIMESUD] auto-door: all move checks passed -- open (and unlock) now
    if pending_door is not None:
        keyword, needs_unlock = pending_door
        if needs_unlock:
            exit_val["locked"] = False
            chprintln(ch, "You unlock and open the " + keyword + ".")
        else:
            chprintln(ch, "You open the " + keyword + ".")
        exit_val["closed"] = False
        rev_exit = None
        rev = REV_DIR.get(direction)
        if rev and dest in ROOM_DEFS:
            candidate = ROOM_DEFS[dest]["exits"].get(rev)
            if isinstance(candidate, dict) and _exit_to(candidate) == ch["room"]:
                candidate["closed"] = False
                if needs_unlock:
                    candidate["locked"] = False
                rev_exit = candidate
        auto_door = (exit_val, rev_exit, keyword, needs_unlock)

    # -- Stance drop on movement (cf. 1stMud move_char act_move.c:169)
    # [PRIMESUD] 1stMud passed "" (bare toggle); bare stance is now a
    # status screen, so relax explicitly via 'none'
    if valid_stance(get_stance(ch, STANCE_CURRENT)):
        from combat import do_stance  # lazy import (combat imports movement targets)
        do_stance(ch, ["none"])

    # -- Leave message (1stMud: act("$n leaves $T.", ch, NULL, dir_name[door], TO_ROOM))
    # Player actor: single-player, nobody to notify; skip.
    # 1stMud suppresses leave/arrive acts under AFF_SNEAK (invis_level n/a).
    if is_npc and not aff.get("sneak"):
        act("$n leaves $T.", ch, None, EXIT_NAMES.get(direction, direction), TO_ROOM)

    from_vnum = ch["room"]
    ch["room"] = dest
    if is_npc:
        # Mobs are tracked in per-room lists (players are not)
        if from_vnum in world.rooms and ch["id"] in world.rooms[from_vnum]["mobs"]:
            world.rooms[from_vnum]["mobs"].remove(ch["id"])
        if dest in world.rooms:
            world.rooms[dest]["mobs"].append(ch["id"])
        if not aff.get("sneak"):
            act("$n has arrived.", ch, type=TO_ROOM)
    else:
        # 1stMud: do_function(ch, &do_look, "auto") -- "auto" triggers brief mode;
        # PrimeSUD has no brief mode, so empty args shows full room.
        # [PRIMESUD] During speedwalk, intermediate rooms get brief one-liners.
        run_buf = ch.get("run_buf")
        if run_buf and any(a == "move" for a, _ in run_buf):
            _brief_room_line(ch)
        else:
            do_look(ch, [])

    # cf. 1stMud move_char: exit looping back to the same room skips
    # followers and quest checks
    if from_vnum == dest:
        _close_auto_door(ch, auto_door)
        return

    # -- Followers move too (cf. 1stMud move_char follower loop, act_move.c:232-257).
    # Mob followers come from the old room's mob list; the player (not tracked
    # in room lists) is checked separately so following a wandering mob works.
    followers = []
    if from_vnum in world.rooms:
        for fid in list(world.rooms[from_vnum]["mobs"]):
            fch = world.chars.get(fid)
            if fch is not None and fch.get("master") == ch["id"]:
                followers.append(fch)
    _p = world.chars.get(1)
    if (_p is not None and _p is not ch and _p.get("master") == ch["id"]
            and _p.get("room") == from_vnum):
        followers.append(_p)

    for fch in followers:
        # 1stMud: charmed follower below standing -> do_stand
        if (fch.get("affected_by", {}).get("charm")
                and POS_ORDER[fch["pos"]] < POS_ORDER["standing"]):
            fch["pos"] = "standing"

        if fch["pos"] != "standing" or not can_see_room(fch, dest):
            continue

        # 1stMud: ROOM_LAW blocks aggressive pets from entering the city
        if (to_room.get("flags", {}).get("law")
                and fch.get("is_npc")
                and fch.get("act_flags", {}).get("aggressive")):
            act("You can't bring $N into the city.", ch, None, fch, TO_CHAR)
            act("You aren't allowed in the city.", fch, None, None, TO_CHAR)
            continue

        act("You follow $N.", fch, None, ch, TO_CHAR)
        move_char(fch, direction)  # cf. 1stMud move_char(fch, door, true)

    # [PRIMESUD] re-close an auto-opened door once followers are through
    _close_auto_door(ch, auto_door)

    # cf. 1stMud move_char act_move.c:266: quest check runs after the
    # follower loop (entry/greet progs, also there, not ported)
    if not is_npc:
        quest_room_check(ch)


# -- Direction command handlers (cf. 1stMud do_north..do_down in act_move.c) --
# Each registered in command table with min_pos = "standing".
# was_room check cancels run_buf on blocked movement (cf. 1stMud free_runbuf).

def do_north(player, args):
    """Walk north (cf. 1stMud do_north in act_move.c). [Verified: 03/07/2026]"""
    was_room = player["room"]
    move_char(player, "n")
    if was_room == player["room"]:
        free_runbuf(player)


def do_east(player, args):
    """Walk east (cf. 1stMud do_east in act_move.c). [Verified: 03/07/2026]"""
    was_room = player["room"]
    move_char(player, "e")
    if was_room == player["room"]:
        free_runbuf(player)


def do_south(player, args):
    """Walk south (cf. 1stMud do_south in act_move.c). [Verified: 03/07/2026]"""
    was_room = player["room"]
    move_char(player, "s")
    if was_room == player["room"]:
        free_runbuf(player)


def do_west(player, args):
    """Walk west (cf. 1stMud do_west in act_move.c). [Verified: 03/07/2026]"""
    was_room = player["room"]
    move_char(player, "w")
    if was_room == player["room"]:
        free_runbuf(player)


def do_up(player, args):
    """Walk up (cf. 1stMud do_up in act_move.c). [Verified: 03/07/2026]"""
    was_room = player["room"]
    move_char(player, "u")
    if was_room == player["room"]:
        free_runbuf(player)


def do_down(player, args):
    """Walk down (cf. 1stMud do_down in act_move.c). [Verified: 03/07/2026]"""
    was_room = player["room"]
    move_char(player, "d")
    if was_room == player["room"]:
        free_runbuf(player)


def get_random_room(ch):
    """Pick a random reachable room (cf. 1stMud get_random_room in act_enter.c).

    [PRIMESUD] Picks a random area first, loads it if needed, then picks a
    room within it (same pattern as spell_teleport in magic.py) -- 1stMud
    sweeps all vnums 0-65535, which would force-load every area here.

    Returns:
        int or None: Room vnum, or None if no candidate found.
    """
    area_files = world._AREA_FILES
    if not area_files:
        return None
    # ponytail: bounded retry instead of 1stMud's infinite loop; None if
    # unlucky -- do_enter shows "doesn't seem to go anywhere"
    tried = set()
    for _ in range(min(10, len(area_files))):
        idx = randint(0, len(area_files) - 1)
        _, area_tag, _, _, _ = area_files[idx]
        if area_tag in tried:
            continue
        tried.add(area_tag)
        world._ensure_area_by_tag(area_tag)
        adef = None
        for a in world.AREA_DEFS:
            if a.get("tag") == area_tag:
                adef = a
                break
        if adef is None or "room_vnums" not in adef:
            continue
        candidates = []
        for vnum in adef["room_vnums"]:
            rd = ROOM_DEFS._data.get(vnum)
            if rd is None:
                continue
            flags = rd.get("flags", {})
            # TODO [PRIMESUD] arena / closed-area checks not yet ported
            if (can_see_room(ch, vnum)
                    and not flags.get("private") and not flags.get("solitary")
                    and not flags.get("safe")
                    and (ch["is_npc"]
                         or ch.get("act_flags", {}).get("aggressive")
                         or not flags.get("law"))):
                candidates.append(vnum)
        if candidates:
            return candidates[randint(0, len(candidates) - 1)]
    return None


def do_enter(ch, args):
    """Enter a portal object in the room (cf. 1stMud do_enter in act_enter.c).
    [Verified: 04/07/2026] -- IsTrusted immortal bypasses and mob entry/greet
    triggers not ported.

    Args:
        ch (dict): Character entering (player or follower mob).
        args (list): Portal keyword arguments.
    """
    if ch["fighting"] is not None:
        return
    if not args:
        chprintln(ch, "Nope, can't do it.")
        return

    old_vnum = ch["room"]
    rs = world.rooms[old_vnum]
    portal = get_obj_list(" ".join(args), rs["items"], ITEM_DEFS)
    if portal is None:
        chprintln(ch, "You don't see that here.")
        return
    # act $p rendering and instance mutation need a dict
    if not isinstance(portal, dict):
        inst = create_object(portal)
        rs["items"][rs["items"].index(portal)] = inst
        portal = inst

    tpl = ITEM_DEFS[obj_vnum(portal)]
    gate = portal.get("gate_flags", tpl.get("gate_flags", {}))
    exit_flags = portal.get("exit_flags", tpl.get("exit_flags", {}))
    if tpl.get("type") != "portal" or exit_flags.get("closed"):
        chprintln(ch, "You can't seem to find a way in.")
        return

    # 1stMud: curse or no_recall room bars exit unless GATE_NOCURSE
    old_flags = ROOM_DEFS.get(old_vnum, {}).get("flags", {})
    if (not gate.get("nocurse")
            and (ch.get("affected_by", {}).get("curse")
                 or old_flags.get("no_recall"))):
        chprintln(ch, "Something prevents you from leaving...")
        return

    # 1stMud value[3]: destination vnum; -1 = re-randomize each use
    to_vnum = portal["to_vnum"] if "to_vnum" in portal else tpl.get("to_vnum", 0)
    if gate.get("random") or to_vnum == -1:
        dest = get_random_room(ch)
        portal["to_vnum"] = dest  # 1stMud: portal->value[3] = location->vnum
    elif gate.get("buggy") and randint(1, 100) < 5:
        dest = get_random_room(ch)
    else:
        dest = to_vnum

    dest_flags = ROOM_DEFS.get(dest, {}).get("flags", {}) if dest else {}
    if (not dest or dest == old_vnum or dest not in ROOM_DEFS
            or not can_see_room(ch, dest)
            or dest_flags.get("private") or dest_flags.get("solitary")):
        act("$p doesn't seem to go anywhere.", ch, portal, None, TO_CHAR)
        return

    if (ch["is_npc"] and ch.get("act_flags", {}).get("aggressive")
            and dest_flags.get("law")):
        chprintln(ch, "Something prevents you from leaving...")
        return

    act("$n steps into $p.", ch, portal, None, TO_ROOM)
    if gate.get("normal_exit"):
        act("You enter $p.", ch, portal, None, TO_CHAR)
    else:
        act("You walk through $p and find yourself somewhere else...",
            ch, portal, None, TO_CHAR)

    ch["room"] = dest
    if ch["is_npc"]:
        if ch["id"] in rs["mobs"]:
            rs["mobs"].remove(ch["id"])
        world.rooms[dest]["mobs"].append(ch["id"])

    if gate.get("gowith"):
        if portal in rs["items"]:
            rs["items"].remove(portal)
        world.rooms[dest]["items"].append(portal)

    if gate.get("normal_exit"):
        act("$n has arrived.", ch, portal, None, TO_ROOM)
    else:
        act("$n has arrived through $p.", ch, portal, None, TO_ROOM)

    if not ch["is_npc"]:
        # 1stMud: do_function(ch, &do_look, "auto") -- no brief mode here
        do_look(ch, [])

    # 1stMud value[0]: charges > 0 count down; 0 -> -1 marks it spent
    charges = portal.get("charges")
    if charges is not None and charges > 0:
        charges -= 1
        portal["charges"] = charges if charges > 0 else -1

    # -- Followers enter too (cf. act_enter.c follower loop; recursion
    # decrements charges per follower, as in 1stMud)
    followers = []
    for fid in list(world.rooms[old_vnum]["mobs"]):
        fch = world.chars.get(fid)
        if fch is not None and fch.get("master") == ch["id"]:
            followers.append(fch)
    _p = world.chars.get(1)
    if (_p is not None and _p is not ch and _p.get("master") == ch["id"]
            and _p.get("room") == old_vnum):
        followers.append(_p)
    for fch in followers:
        if portal.get("charges") == -1:  # spent mid-loop
            continue
        if (fch.get("affected_by", {}).get("charm")
                and POS_ORDER[fch["pos"]] < POS_ORDER["standing"]):
            fch["pos"] = "standing"
        if fch["pos"] != "standing":
            continue
        if (dest_flags.get("law") and fch.get("is_npc")
                and fch.get("act_flags", {}).get("aggressive")):
            act("You can't bring $N into the city.", ch, None, fch, TO_CHAR)
            act("You aren't allowed in the city.", fch, None, None, TO_CHAR)
            continue
        act("You follow $N.", fch, None, ch, TO_CHAR)
        do_enter(fch, args)

    # spent portal fades (may sit in the old room or, via gowith, the new one)
    if portal.get("charges") == -1:
        act("$p fades out of existence.", ch, portal, None, TO_CHAR)
        for items in (rs["items"], world.rooms[dest]["items"]):
            if portal in items:
                items.remove(portal)
                break
    # 1stMud runs entry/greet mobprogs here (not ported); no quest room
    # check in do_enter -- that is a move_char-only mechanic


def _find_door(player, arg, exits):
    """Resolve a direction word or door keyword to a door exit
    (cf. 1stMud find_door in act_move.c).

    Args:
        player (dict): Player state dict.
        arg (str): Direction alias ("n", "north") or door keyword ("grate").
        exits (dict): Current room's exits.

    Returns:
        str: Direction key, or None after printing feedback.

    [Verified: 03/07/2026]
    """
    direction = DIR_ALIASES.get(arg.lower())
    if direction is None:
        for d in EXIT_ORDER:
            ev = exits.get(d)
            if (isinstance(ev, dict) and ev.get("isdoor")
                    and ev.get("keyword") and is_name(arg, ev["keyword"])):
                return d
        act("I see no $T here.", player, None, arg, TO_CHAR)
        return None
    if direction not in exits:
        act("I see no door $T here.", player, None, arg, TO_CHAR)
        return None
    exit_val = exits[direction]
    if not isinstance(exit_val, dict) or not exit_val.get("isdoor"):
        chprintln(player, "You can't do that.")
        return None
    return direction


# -- Containers ------------------------------------------------------------
# [PRIMESUD] ITEM_PORTAL branches of open/close/lock/unlock not ported --
# no portal objects exist in any stock area.

def _open_container(player, obj):
    """Container branch of do_open (cf. 1stMud do_open ITEM_CONTAINER branch
    in act_move.c:426-450). [PRIMESUD] split out so do_open can try this
    before falling back to door resolution, matching 1stMud's obj-then-door
    lookup order.
    """
    tpl = ITEM_DEFS[obj_vnum(obj)]
    if _item_type(obj, tpl) != "container":
        chprintln(player, "That's not a container.")
        return
    # [PRIMESUD] reset-spawned items may be plain vnum ints; flag mutation
    # and act() $p rendering need an instance dict
    obj = promote_obj(player, obj)
    flags = item_container_flags(obj, tpl)
    if not flags.get("closed"):
        chprintln(player, "It's already open.")
        return
    if not flags.get("closeable"):
        chprintln(player, "You can't do that.")
        return
    if flags.get("locked"):
        chprintln(player, "It's locked.")
        return
    set_item_container_flag(obj, tpl, "closed", False)
    act("You open $p.", player, obj, None, TO_CHAR)
    act("$n opens $p.", player, obj, None, TO_ROOM)


def _close_container(player, obj):
    """Container branch of do_close (cf. 1stMud do_close ITEM_CONTAINER branch
    in act_move.c:531-550). [PRIMESUD] split out, see _open_container.
    """
    tpl = ITEM_DEFS[obj_vnum(obj)]
    if _item_type(obj, tpl) != "container":
        chprintln(player, "That's not a container.")
        return
    # [PRIMESUD] reset-spawned items may be plain vnum ints; flag mutation
    # and act() $p rendering need an instance dict
    obj = promote_obj(player, obj)
    flags = item_container_flags(obj, tpl)
    if flags.get("closed"):
        chprintln(player, "It's already closed.")
        return
    if not flags.get("closeable"):
        chprintln(player, "You can't do that.")
        return
    set_item_container_flag(obj, tpl, "closed", True)
    act("You close $p.", player, obj, None, TO_CHAR)
    act("$n closes $p.", player, obj, None, TO_ROOM)


def _lock_container(player, obj):
    """Container branch of do_lock (cf. 1stMud do_lock ITEM_CONTAINER branch
    in act_move.c:655-684). [PRIMESUD] split out, see _open_container.

    Unlike the door branch, 1stMud prints no "*Click*" for containers.
    """
    tpl = ITEM_DEFS[obj_vnum(obj)]
    if _item_type(obj, tpl) != "container":
        chprintln(player, "That's not a container.")
        return
    # [PRIMESUD] reset-spawned items may be plain vnum ints; flag mutation
    # and act() $p rendering need an instance dict
    obj = promote_obj(player, obj)
    flags = item_container_flags(obj, tpl)
    if not flags.get("closed"):
        chprintln(player, "It's not closed.")
        return
    key = tpl.get("container_key")
    # [PRIMESUD] area converter omits container_key when 1stMud's
    # value[2] <= 0 ("It can't be locked."); the <0 vs. ==0 distinction
    # is lost in conversion but both mean "no valid key" in practice.
    if not key:
        chprintln(player, "It can't be locked.")
        return
    if not _has_key(player, key):
        chprintln(player, "You lack the key.")
        return
    if flags.get("locked"):
        chprintln(player, "It's already locked.")
        return
    set_item_container_flag(obj, tpl, "locked", True)
    act("You lock $p.", player, obj, None, TO_CHAR)
    act("$n locks $p.", player, obj, None, TO_ROOM)


def _unlock_container(player, obj):
    """Container branch of do_unlock (cf. 1stMud do_unlock ITEM_CONTAINER
    branch in act_move.c:786-815). [PRIMESUD] split out, see _open_container.

    Unlike the door branch, 1stMud prints no "*Click*" for containers.
    """
    tpl = ITEM_DEFS[obj_vnum(obj)]
    if _item_type(obj, tpl) != "container":
        chprintln(player, "That's not a container.")
        return
    # [PRIMESUD] reset-spawned items may be plain vnum ints; flag mutation
    # and act() $p rendering need an instance dict
    obj = promote_obj(player, obj)
    flags = item_container_flags(obj, tpl)
    if not flags.get("closed"):
        chprintln(player, "It's not closed.")
        return
    key = tpl.get("container_key")
    if not key:  # [PRIMESUD] see _lock_container
        chprintln(player, "It can't be unlocked.")
        return
    if not _has_key(player, key):
        chprintln(player, "You lack the key.")
        return
    if not flags.get("locked"):
        chprintln(player, "It's already unlocked.")
        return
    set_item_container_flag(obj, tpl, "locked", False)
    act("You unlock $p.", player, obj, None, TO_CHAR)
    act("$n unlocks $p.", player, obj, None, TO_ROOM)


def _pick_container(player, obj):
    """Container branch of do_pick (cf. 1stMud do_pick ITEM_CONTAINER branch
    in act_move.c:839-866). [PRIMESUD] split out, see _open_container.
    """
    tpl = ITEM_DEFS[obj_vnum(obj)]
    if _item_type(obj, tpl) != "container":
        chprintln(player, "That's not a container.")
        return
    obj = promote_obj(player, obj)
    flags = item_container_flags(obj, tpl)
    if not flags.get("closed"):
        chprintln(player, "It's not closed.")
        return
    key = tpl.get("container_key")
    if not key:  # [PRIMESUD] see _lock_container
        chprintln(player, "It can't be unlocked.")
        return
    if not flags.get("locked"):
        chprintln(player, "It's already unlocked.")
        return
    if flags.get("pickproof"):
        chprintln(player, "You failed.")
        return
    set_item_container_flag(obj, tpl, "locked", False)
    act("You pick the lock on $p.", player, obj, None, TO_CHAR)
    act("$n picks the lock on $p.", player, obj, None, TO_ROOM)
    check_improve(player, GSN_PICK_LOCK, True, 2)


def do_open(player, args):
    """Open a door in a given direction or by keyword, or open a closeable
    container (cf. 1stMud do_open in act_move.c).

    ITEM_PORTAL branch not ported -- no portal objects in any stock area
    [PRIMESUD].
    [Verified: 03/07/2026; act/chprintln output routing (NPC-safe invoker,
    room + far-side messages) added and re-verified 04/07/2026; container
    branch added and re-verified 05/07/2026]
    """
    exits = ROOM_DEFS[player["room"]]["exits"]
    _picked_dir = None
    if args:
        arg = " ".join(args)
        obj = get_obj_here(player, arg)
        if obj is not None:
            return _open_container(player, obj)
        # 1stMud prints "Open what?" on no args; [PRIMESUD] picker below instead
        direction = _find_door(player, arg, exits)
        if direction is None:
            return
    else:
        candidates = [d for d in EXIT_ORDER
                      if isinstance(exits.get(d), dict)
                      and exits[d].get("isdoor") and exits[d].get("closed")]
        if not candidates:
            chprintln(player, "There are no doors to open here.")
            return
        idx = pick_from("Open which door?", [EXIT_NAMES[d] for d in candidates])
        if idx < 0:
            return
        direction = candidates[idx]
        _picked_dir = direction
    exit_val = exits[direction]
    if not exit_val.get("closed"):
        chprintln(player, "It's already open.")
        return
    if exit_val.get("locked"):
        chprintln(player, "It's locked.")
        return
    exit_val["closed"] = False
    act("$n opens the $d.", player, None, exit_val.get("keyword"), TO_ROOM)
    chprintln(player, "Ok.")
    dest = exit_val["to"]
    rev = REV_DIR.get(direction)
    if rev and dest in ROOM_DEFS:
        rev_exit = ROOM_DEFS[dest]["exits"].get(rev)
        if isinstance(rev_exit, dict) and _exit_to(rev_exit) == player["room"]:
            rev_exit["closed"] = False
            # cf. act_move.c:483-485: notify chars on the far side
            for rch in world.chars.values():
                if rch.get("room") == dest:
                    act("The $d opens.", rch, None, rev_exit.get("keyword"),
                        TO_CHAR)
    return ("open " + EXIT_NAMES[_picked_dir].lower()) if _picked_dir is not None else None


def do_close(player, args):
    """Close a door in a given direction or by keyword, or close a closeable
    container (cf. 1stMud do_close in act_move.c).

    ITEM_PORTAL branch not ported -- no portal objects in any stock area
    [PRIMESUD].
    [Verified: 03/07/2026; act/chprintln output routing (NPC-safe invoker,
    room + far-side messages) added and re-verified 04/07/2026; container
    branch added and re-verified 05/07/2026]
    """
    exits = ROOM_DEFS[player["room"]]["exits"]
    _picked_dir = None
    if args:
        arg = " ".join(args)
        obj = get_obj_here(player, arg)
        if obj is not None:
            return _close_container(player, obj)
        # 1stMud prints "Close what?" on no args; [PRIMESUD] picker below instead
        direction = _find_door(player, arg, exits)
        if direction is None:
            return
    else:
        candidates = [d for d in EXIT_ORDER
                      if isinstance(exits.get(d), dict)
                      and exits[d].get("isdoor") and not exits[d].get("closed")]
        if not candidates:
            chprintln(player, "There are no open doors to close here.")
            return
        idx = pick_from("Close which door?", [EXIT_NAMES[d] for d in candidates])
        if idx < 0:
            return
        direction = candidates[idx]
        _picked_dir = direction
    exit_val = exits[direction]
    if exit_val.get("closed"):
        chprintln(player, "It's already closed.")
        return
    # [PRIMESUD] 1stMud only checks EX_NOCLOSE on portals, not doors;
    # guard kept so noclose exits stay open
    if exit_val.get("noclose"):
        chprintln(player, "You can't do that.")
        return
    exit_val["closed"] = True
    act("$n closes the $d.", player, None, exit_val.get("keyword"), TO_ROOM)
    chprintln(player, "Ok.")
    dest = exit_val["to"]
    rev = REV_DIR.get(direction)
    if rev and dest in ROOM_DEFS:
        rev_exit = ROOM_DEFS[dest]["exits"].get(rev)
        if isinstance(rev_exit, dict) and _exit_to(rev_exit) == player["room"]:
            rev_exit["closed"] = True
            # cf. act_move.c:578-580: notify chars on the far side
            for rch in world.chars.values():
                if rch.get("room") == dest:
                    act("The $d closes.", rch, None, rev_exit.get("keyword"),
                        TO_CHAR)
    return ("close " + EXIT_NAMES[_picked_dir].lower()) if _picked_dir is not None else None


# -- Locks ---------------------------------------------------------------------
# [PRIMESUD] ITEM_PORTAL branch of lock/unlock/pick not ported -- no portal
# objects in any stock area.  do_lock/do_unlock/do_pick now also cover
# ITEM_CONTAINER (see _lock_container/_unlock_container/_pick_container below).

def _has_key(ch, key_vnum):
    """True if ch carries the key item (cf. 1stMud has_key in act_move.c). [Verified: 03/07/2026]"""
    from item import obj_vnum
    for obj in ch["inv"] + [o for o in ch["equip"].values() if o is not None]:
        if obj_vnum(obj) == key_vnum:
            return True
    return False


def _door_for_lock_cmd(player, args, verb, want_locked):
    """Resolve target door for lock/unlock/pick: direction arg or picker [PRIMESUD].

    Args:
        player (dict): Player state dict.
        args (list): Command args; first token is a direction alias if present.
        verb (str): Command verb for prompts ("Lock" etc.).
        want_locked (bool): Picker candidates must be locked (True) or unlocked (False).

    Returns:
        (direction, exit_dict, picked) or (None, None, False) after printing feedback.
    """
    exits = ROOM_DEFS[player["room"]]["exits"]
    picked = False
    if args:
        direction = _find_door(player, " ".join(args), exits)
        if direction is None:
            return None, None, False
    else:
        candidates = [d for d in EXIT_ORDER
                      if isinstance(exits.get(d), dict)
                      and exits[d].get("isdoor") and exits[d].get("closed")
                      and exits[d].get("key") is not None
                      and bool(exits[d].get("locked")) == want_locked]
        if not candidates:
            chprintln(player, "There are no doors to " + verb.lower() + " here.")
            return None, None, False
        idx = pick_from(verb + " which door?", [EXIT_NAMES[d] for d in candidates])
        if idx < 0:
            return None, None, False
        direction = candidates[idx]
        picked = True
    return direction, exits[direction], picked


def _set_rev_lock(player, direction, exit_val, locked):
    """Mirror a lock state change onto the reverse exit (cf. 1stMud pexit_rev)."""
    dest = exit_val["to"]
    rev = REV_DIR.get(direction)
    if rev and dest in ROOM_DEFS:
        rev_exit = ROOM_DEFS[dest]["exits"].get(rev)
        if isinstance(rev_exit, dict) and _exit_to(rev_exit) == player["room"]:
            rev_exit["locked"] = locked


def do_lock(player, args):
    """Lock a closed door with its key, or lock a closed container with its
    key (cf. 1stMud do_lock in act_move.c).
    [Verified: 03/07/2026; act/chprintln output routing (NPC-safe invoker,
    room message) added and re-verified 04/07/2026; container branch added
    and re-verified 05/07/2026]
    """
    if args:
        obj = get_obj_here(player, " ".join(args))
        if obj is not None:
            return _lock_container(player, obj)
    direction, exit_val, picked = _door_for_lock_cmd(player, args, "Lock", False)
    if exit_val is None:
        return
    if not exit_val.get("closed"):
        chprintln(player, "It's not closed.")
        return
    if exit_val.get("key") is None:
        chprintln(player, "It can't be locked.")
        return
    if not _has_key(player, exit_val["key"]):
        chprintln(player, "You lack the key.")
        return
    if exit_val.get("locked"):
        chprintln(player, "It's already locked.")
        return
    exit_val["locked"] = True
    chprintln(player, "*Click*")
    act("$n locks the $d.", player, None, exit_val.get("keyword"), TO_ROOM)
    _set_rev_lock(player, direction, exit_val, True)
    return ("lock " + EXIT_NAMES[direction].lower()) if picked else None


def do_unlock(player, args):
    """Unlock a closed door with its key, or unlock a closed container with
    its key (cf. 1stMud do_unlock in act_move.c).
    [Verified: 03/07/2026; act/chprintln output routing (NPC-safe invoker,
    room message) added and re-verified 04/07/2026; container branch added
    and re-verified 05/07/2026]
    """
    if args:
        obj = get_obj_here(player, " ".join(args))
        if obj is not None:
            return _unlock_container(player, obj)
    direction, exit_val, picked = _door_for_lock_cmd(player, args, "Unlock", True)
    if exit_val is None:
        return
    if not exit_val.get("closed"):
        chprintln(player, "It's not closed.")
        return
    if exit_val.get("key") is None:
        chprintln(player, "It can't be unlocked.")
        return
    if not _has_key(player, exit_val["key"]):
        chprintln(player, "You lack the key.")
        return
    if not exit_val.get("locked"):
        chprintln(player, "It's already unlocked.")
        return
    exit_val["locked"] = False
    chprintln(player, "*Click*")
    act("$n unlocks the $d.", player, None, exit_val.get("keyword"), TO_ROOM)
    _set_rev_lock(player, direction, exit_val, False)
    return ("unlock " + EXIT_NAMES[direction].lower()) if picked else None


def do_pick(player, args):
    """Pick a door or container lock using the pick lock skill (cf. 1stMud do_pick in act_move.c).

    [Verified: 03/07/2026; act/chprintln output routing (NPC-safe invoker,
    room message) added and re-verified 04/07/2026; container branch added
    and re-verified 06/07/2026] -- [PRIMESUD] intentional
    reorder: target door is resolved (with picker) before WaitState/close-
    stander/skill roll, while 1stMud rolls before find_door. Deliberately
    removes a 1stMud quirk where picking a nonexistent door still costs lag,
    rolls the skill, and can train pick lock via check_improve on the failed
    roll (train-on-typo exploit). Do not "fix" back to 1stMud order.
    """
    obj = None
    if args:
        obj = get_obj_here(player, " ".join(args))
    if obj is None:
        direction, exit_val, picked = _door_for_lock_cmd(player, args, "Pick", True)
        if exit_val is None:
            return
    else:
        direction, exit_val, picked = None, None, False

    WaitState(player, SKILLS[GSN_PICK_LOCK]["beats"])

    # 1stMud: awake NPC more than 5 levels above ch blocks the attempt
    rs = world.rooms[player["room"]]
    for mob_id in rs["mobs"]:
        gch = world.chars[mob_id]
        if is_awake(gch) and player["level"] + 5 < gch["level"]:
            act("$N is standing too close to the lock.", player, None, gch, TO_CHAR)
            return

    # [PRIMESUD] 1stMud skips this roll for NPC invokers (act_move.c:889,
    # "!IsNPC(ch) && ..."); we roll for everyone -- intentional, revisit if
    # an NPC ever needs to pick locks reliably
    if randint(1, 100) > get_skill(player, GSN_PICK_LOCK):
        chprintln(player, "You failed.")
        check_improve(player, GSN_PICK_LOCK, False, 2)
        return

    if obj is not None:
        return _pick_container(player, obj)

    if not exit_val.get("closed"):
        chprintln(player, "It's not closed.")
        return
    if exit_val.get("key") is None:
        chprintln(player, "It can't be picked.")
        return
    if not exit_val.get("locked"):
        chprintln(player, "It's already unlocked.")
        return
    if exit_val.get("pickproof"):
        chprintln(player, "You failed.")
        return

    exit_val["locked"] = False
    chprintln(player, "*Click*")
    act("$n picks the $d.", player, None, exit_val.get("keyword"), TO_ROOM)
    check_improve(player, GSN_PICK_LOCK, True, 2)
    _set_rev_lock(player, direction, exit_val, False)
    return ("pick " + EXIT_NAMES[direction].lower()) if picked else None


# -- Position commands ---------------------------------------------------------
# [PRIMESUD] ITEM_FURNITURE branches (stand/rest/sit/sleep at/on/in objects,
# count_users, ch->on) not ported in all five commands below -- few furniture
# items in current areas.  Revisit if furniture matters later.

def do_stand(player, args):
    """Stand up, waking first if asleep (cf. 1stMud do_stand in act_move.c). [Verified: 03/07/2026]

    Args:
        player (dict): Player state dict.
        args (list): Furniture keyword -- not ported, ignored [PRIMESUD].
    """
    pos = player.get("pos", "standing")
    if pos == "sleeping":
        if player.get("affected_by", {}).get("sleep"):
            chprintln(player, "You can't wake up!")
            return
        chprintln(player, "You wake and stand up.")
        act("$n wakes and stands up.", player, None, None, TO_ROOM)
        player["pos"] = "standing"
        do_look(player, [])
    elif pos in ("resting", "sitting"):
        chprintln(player, "You stand up.")
        act("$n stands up.", player, None, None, TO_ROOM)
        player["pos"] = "standing"
    elif pos == "standing":
        chprintln(player, "You are already standing.")
    elif pos == "fighting":
        chprintln(player, "You are already fighting!")


def do_rest(player, args):
    """Rest to speed regeneration (cf. 1stMud do_rest in act_move.c). [Verified: 03/07/2026]

    Args:
        player (dict): Player state dict.
        args (list): Furniture keyword -- not ported, ignored [PRIMESUD].
    """
    pos = player.get("pos", "standing")
    if pos == "fighting":
        chprintln(player, "You are already fighting!")
        return
    if pos == "sleeping":
        if player.get("affected_by", {}).get("sleep"):
            chprintln(player, "You can't wake up!")
            return
        chprintln(player, "You wake up and start resting.")
        act("$n wakes up and starts resting.", player, None, None, TO_ROOM)
        player["pos"] = "resting"
    elif pos == "resting":
        chprintln(player, "You are already resting.")
    elif pos == "standing":
        chprintln(player, "You rest.")
        act("$n sits down and rests.", player, None, None, TO_ROOM)
        player["pos"] = "resting"
    elif pos == "sitting":
        chprintln(player, "You rest.")
        act("$n rests.", player, None, None, TO_ROOM)
        player["pos"] = "resting"


def do_sit(player, args):
    """Sit down (cf. 1stMud do_sit in act_move.c). [Verified: 03/07/2026]

    Args:
        player (dict): Player state dict.
        args (list): Furniture keyword -- not ported, ignored [PRIMESUD].
    """
    pos = player.get("pos", "standing")
    if pos == "fighting":
        chprintln(player, "Maybe you should finish this fight first?")
        return
    if pos == "sleeping":
        if player.get("affected_by", {}).get("sleep"):
            chprintln(player, "You can't wake up!")
            return
        chprintln(player, "You wake and sit up.")
        act("$n wakes and sits up.", player, None, None, TO_ROOM)
        player["pos"] = "sitting"
    elif pos == "resting":
        chprintln(player, "You stop resting.")
        player["pos"] = "sitting"
    elif pos == "sitting":
        chprintln(player, "You are already sitting down.")
    elif pos == "standing":
        chprintln(player, "You sit down.")
        act("$n sits down on the ground.", player, None, None, TO_ROOM)
        player["pos"] = "sitting"


def do_sleep(player, args):
    """Go to sleep for maximum regeneration (cf. 1stMud do_sleep in act_move.c). [Verified: 03/07/2026]

    Args:
        player (dict): Player state dict.
        args (list): Furniture keyword -- not ported, ignored [PRIMESUD].
    """
    pos = player.get("pos", "standing")
    if pos == "sleeping":
        chprintln(player, "You are already sleeping.")
    elif pos in ("resting", "sitting", "standing"):
        chprintln(player, "You go to sleep.")
        act("$n goes to sleep.", player, None, None, TO_ROOM)
        player["pos"] = "sleeping"
    elif pos == "fighting":
        chprintln(player, "You are already fighting!")


def do_wake(player, args):
    """Wake yourself (stand) or a sleeping character (cf. 1stMud do_wake in act_move.c). [Verified: 03/07/2026]

    Args:
        player (dict): Player state dict.
        args (list): Optional target keyword; without it, acts as stand.
    """
    if not args:
        do_stand(player, [])
        return

    if not is_awake(player):
        chprintln(player, "You are asleep yourself!")
        return

    rs = world.rooms[player["room"]]
    victim_id = get_char_room(" ".join(args), rs["mobs"], world.chars, player)
    if victim_id is None:
        chprintln(player, "They aren't here.")
        return
    victim = world.chars[victim_id]

    if is_awake(victim):
        act("$N is already awake.", player, None, victim, TO_CHAR)
        return

    if victim.get("affected_by", {}).get("sleep"):
        act("You can't wake $M!", player, None, victim, TO_CHAR)
        return

    act("$n wakes you.", player, None, victim, TO_VICT)
    # 1stMud passes ch to do_stand here (apparent bug -- ROM 2.4 stands the
    # victim); [PRIMESUD] stand the victim so waking mobs actually works
    victim["pos"] = "standing"
    # ROM 2.4 victim do_stand side effect, so the waker sees it happen
    act("$n wakes and stands up.", victim, None, None, TO_ROOM)


# -- Stealth -------------------------------------------------------------------

def do_sneak(player, args):
    """Attempt to move silently via the sneak skill (cf. 1stMud do_sneak in act_move.c). [Verified: 03/07/2026; tprint->chprintln output routing re-verified 04/07/2026]

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments (unused).
    """
    chprintln(player, "You attempt to move silently.")
    affect_strip(player, GSN_SNEAK)

    if player.get("affected_by", {}).get("sneak"):
        return

    if randint(1, 100) < get_skill(player, GSN_SNEAK):
        check_improve(player, GSN_SNEAK, True, 3)
        affect_to_char(player, {
            "where":     "to_affects",
            "type":      GSN_SNEAK,
            "level":     player["level"],
            "duration":  player["level"],
            "location":  "none",
            "modifier":  0,
            "bitvector": "sneak",
        })
    else:
        check_improve(player, GSN_SNEAK, False, 3)


def do_hide(player, args):
    """Attempt to hide via the hide skill (cf. 1stMud do_hide in act_move.c). [Verified: 03/07/2026; tprint->chprintln output routing re-verified 04/07/2026]

    Hide is a bare AFF bit with no affect entry; any command except
    stealth/info commands removes it (see interpret in commands.py).

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments (unused).
    """
    chprintln(player, "You attempt to hide.")

    aff = player.setdefault("affected_by", {})
    aff.pop("hide", None)

    if randint(1, 100) < get_skill(player, GSN_HIDE):
        aff["hide"] = True
        check_improve(player, GSN_HIDE, True, 3)
    else:
        check_improve(player, GSN_HIDE, False, 3)


def do_visible(player, args):
    """Strip invisibility, sneak, and hide (cf. 1stMud do_visible in act_move.c). [Verified: 03/07/2026; tprint->chprintln output routing re-verified 04/07/2026]

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments (unused).
    """
    affect_strip(player, GSN_INVIS)
    affect_strip(player, GSN_MASS_INVIS)
    affect_strip(player, GSN_SNEAK)
    aff = player.get("affected_by", {})
    aff.pop("hide", None)
    aff.pop("invisible", None)
    aff.pop("sneak", None)
    chprintln(player, "Ok.")


def perform_recall(player, location, what="recall"):
    """Move player to recall destination (cf. 1stMud perform_recall in act_move.c).

    Only-players / arena checks and the "$n prays for transportation!" /
    "$n disappears." / "$n appears in the room." room acts are not ported
    (single-player, no arena). [PRIMESUD]

    [Verified: 03/07/2026; tprint->chprintln output routing re-verified 04/07/2026]
    """
    room = ROOM_DEFS[player["room"]]

    if location is None:
        chprintln(player, "You are completely lost.")
        return False

    if player["room"] == location:
        return True

    if room.get("flags", {}).get("no_recall") \
            or player.get("affected_by", {}).get("curse"):
        # 1stMud: act "$g has forsaken you." ($g = deity name; no deities here)
        chprintln(player, "Your deity has forsaken you.")
        return False

    if player["fighting"] is not None:
        skill = get_skill(player, GSN_RECALL)
        if randint(1, 100) < 80 * skill // 100:
            check_improve(player, GSN_RECALL, False, 6)
            WaitState(player, PULSE_PER_SECOND)
            chprintln(player, "You failed!")  # [PRIMESUD] 1stMud typo "You failed!."
            return False
        player["xp"] = max(0, player["xp"] - 25)
        check_improve(player, GSN_RECALL, True, 4)
        chprintln(player, "You " + what + " from combat!  You lose 25 exps.")
        stop_fighting(player, both=True)

    player["move"] = player.get("move", 0) // 2
    from_vnum = player["room"]
    player["room"] = location

    # cf. 1stMud do_recall: pet recalls with its master
    pet = world.chars.get(player.get("pet")) if player.get("pet") is not None else None
    if (pet is not None and pet.get("room") == from_vnum
            and from_vnum in world.rooms and location in world.rooms):
        if pet["id"] in world.rooms[from_vnum]["mobs"]:
            world.rooms[from_vnum]["mobs"].remove(pet["id"])
        pet["room"] = location
        world.rooms[location]["mobs"].append(pet["id"])

    do_look(player, [])
    return True


def do_recall(player, args):
    """Teleport to the area's recall room (cf. 1stMud perform_recall in act_move.c).

    Per-area recall VNUMs (area->recall in 1stMud) are not yet implemented;
    all areas fall back to R_RECALL (ROOM_VNUM_TEMPLE).  Pet recall is
    handled in perform_recall.

    [Verified: 03/07/2026]
    """
    location = R_RECALL
    perform_recall(player, location, "recall")


_RUN_DIRS = frozenset(("n", "e", "s", "w", "u", "d"))


def _parse_run_buf(buf):
    """Parse a speedwalk string into a list of (action, direction) tuples.

    Format matches 1stMud run_buf: digits are repeat counts, direction
    chars (n/e/s/w/u/d) are steps, 'o' prefix means open door before
    moving (cf. 1stMud read_from_buffer in comm.c).

    Returns:
        list: [(action, dir), ...] where action is "move" or "open".
              None on parse error.
    """
    steps = []
    i = 0
    while i < len(buf):
        count = 0
        while i < len(buf) and buf[i].isdigit():
            count = count * 10 + int(buf[i])
            i += 1
        if i >= len(buf):
            break
        ch = buf[i]
        i += 1
        if ch == "o":
            if i >= len(buf) or buf[i] not in _RUN_DIRS:
                return None
            steps.append(("open", buf[i]))
            i += 1
        elif ch in _RUN_DIRS:
            if count < 1:
                count = 1
            for _ in range(count):
                steps.append(("move", ch))
        else:
            return None
    return steps


def _brief_room_line(player):
    """One-line room summary for speedwalk intermediate steps. [PRIMESUD]"""
    room = ROOM_DEFS[player["room"]]
    exits = " ".join(
        EXIT_NAMES.get(d, d) for d in EXIT_ORDER
        if d in room.get("exits", {})
        and not (isinstance(room["exits"][d], dict)
                 and (room["exits"][d].get("closed")
                      or room["exits"][d].get("to") is None))
    )
    exit_str = "[" + exits + "]" if exits else "[none]"
    chprintln(player, "{Y" + room["name"] + "{x {g" + exit_str + "{x")


def free_runbuf(player):
    """Clear player's run buffer (cf. 1stMud free_runbuf in comm.c)."""
    player.pop("run_buf", None)


_DIR_CMDS = {
    "n": do_north, "e": do_east, "s": do_south,
    "w": do_west, "u": do_up, "d": do_down,
}


def run_buf_step(player):
    """Consume one step from player's run_buf (cf. 1stMud read_from_buffer in comm.c).

    Called once per pulse from game_loop when wait==0. Delegates move
    steps to direction commands (do_north etc.) for SSOT -- any future
    mechanics added there apply during runs too. Blocked-movement
    cancellation handled by direction commands via free_runbuf
    (cf. 1stMud do_north in act_move.c). Brief vs full room display
    handled by move_char checking run_buf state.

    Returns:
        bool: True if a step was consumed.
    """
    run_buf = player.get("run_buf")
    if not run_buf:
        return False

    # Combat cancels run (cf. 1stMud read_from_buffer POS_FIGHTING check).
    # [PRIMESUD] 1stMud cancels silently; we notify the player.
    if player.get("fighting") is not None:
        chprintln(player, "You stop running -- you are fighting!")
        free_runbuf(player)
        return False

    action, d = run_buf.pop(0)

    if action == "open":
        do_open(player, [EXIT_NAMES[d]])
    else:
        _DIR_CMDS[d](player, [])

    if not player.get("run_buf"):
        free_runbuf(player)

    return True


def do_run(player, args):
    """Parse speedwalk and store in run_buf for tick-based execution
    (cf. 1stMud do_run in act_move.c).

    With args: parse speedwalk string (e.g. '3s2en', 'son2e').
    Without args: [PRIMESUD] present picker of all other areas (static
    tables only, no area loads to build the list), then lazily pathfind
    to just the chosen one via info.find_path_to_area -- zero-load
    area-graph BFS, then load only the areas on that chain, then a
    restricted room-level BFS; falls back to loading every area only if
    that restricted search can't complete the chain at room granularity.

    Steps are consumed one-per-pulse by run_buf_step() in game_loop
    (cf. 1stMud read_from_buffer consuming run_buf in comm.c).
    move_char WaitState(1) means each move takes two pulses (one to
    move, one recovery). Movement-point cost applies per step so the
    player can exhaust mid-run.

    Intermediate rooms show brief one-liners. [PRIMESUD] Final
    destination gets full do_look. Combat or blocked movement cancels
    the run (cf. 1stMud free_runbuf). Keyboard input (Enter) also
    cancels. [PRIMESUD]

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments (speedwalk string tokens).
    """
    # [PRIMESUD] 1stMud overwrites run_buf; we guard instead.
    if player.get("run_buf"):
        chprintln(player, "You are already running!")
        return

    if not args:
        # [PRIMESUD] No-args picker: list all other areas from the static
        # tables (zero area loads), then pathfind lazily to just the one
        # picked -- computing directions for every area up front is
        # exactly the load-everything cost this is meant to avoid.
        # (1stMud prints "You run in place!" on no args)
        source_area = ROOM_DEFS.get(player.get("room"), {}).get("area")
        sorted_areas = sorted(world._AREA_FILES, key=lambda a: a[2].lower())
        candidates = [(name, tag) for _fname, tag, name, _vlo, _vhi in sorted_areas
                     if tag != source_area]
        if not candidates:
            chprintln(player, "No accessible areas from here.")
            return
        labels = [name for name, _tag in candidates]
        idx = pick_from("Run to which area?", labels)
        if idx < 0:
            return
        buf = find_path_to_area(player, candidates[idx][1])
        if not buf:
            chprintln(player, "You cannot get there from here.")
            return
    else:
        buf = "".join(args)

    # Validate (cf. 1stMud do_run validation in act_move.c)
    has_dir = False
    for ch in buf:
        if ch in _RUN_DIRS:
            has_dir = True
        elif ch != "o" and not ch.isdigit():
            chprintln(player, "Invalid direction!")
            return
    if not has_dir:
        chprintln(player, "No directions specified!")
        return

    steps = _parse_run_buf(buf)
    if steps is None:
        chprintln(player, "Invalid direction!")
        return

    player["run_buf"] = steps
    chprintln(player, "You start running...")
