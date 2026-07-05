"""Communication commands: say, tell (cf. 1stMud do_say/do_tell in act_comm.c)."""

import world
from handler import (act, chprintln, chprintlnf, is_name, get_char_room,
                   affect_strip, can_see,
                   TO_CHAR, TO_ROOM, TO_VICT, TO_NOTVICT, TO_ZONE)
from skill_utils import WaitState
from skills_table import GSN_CHARM_PERSON
from config import PULSE_VIOLENCE


# -- say_verb (cf. 1stMud say_verb in act_comm.c) ----------------------------

_VERB_TABLE = {
    0: {"say": "say", "ask": "ask", "exclaim": "exclaim",
        "demand": "demand", "scream": "scream", "mutter": "mutter"},
    1: {"say": "says", "ask": "asks", "exclaim": "exclaims",
        "demand": "demands", "scream": "screams", "mutter": "mutters"},
}


def say_verb(text, form):
    """Pick say/ask/exclaim verb from trailing punctuation (cf. 1stMud say_verb in act_comm.c).

    [PRIMESUD] Emoticon detection and drunk slur not ported.

    Args:
        text (str): The spoken text.
        form (int): 0 = first person ("say"), 1 = third person ("says").

    Returns:
        str: The verb string.
    """
    verbs = _VERB_TABLE[form]
    if len(text) < 3:
        return verbs["say"]
    last = text[-1]
    prev = text[-2]
    if last == "!":
        if prev == "!":
            return verbs["scream"]
        return verbs["exclaim"]
    if last == "?":
        if prev == "?":
            return verbs["demand"]
        return verbs["ask"]
    if last == "." and prev == "." and len(text) >= 3 and text[-3] == ".":
        return verbs["mutter"]
    return verbs["say"]


# -- do_say (cf. 1stMud do_say in act_comm.c) --------------------------------

def do_say(ch, args):
    """Say something to the room (cf. 1stMud do_say in act_comm.c).

    Args:
        ch (dict): Speaking character (player or mob instance).
        args (list): Words to say.
    """
    if not args:
        chprintln(ch, "Say what?")
        return

    argument = " ".join(args)
    verb_room = say_verb(argument, 1)
    verb_self = say_verb(argument, 0)
    act("{g$n $t '{G$T{g'{x", ch, verb_room, argument, TO_ROOM)
    act("{gYou $t '{G$T{g'{x", ch, verb_self, argument, TO_CHAR)
    # [PRIMESUD] TRIG_SPEECH (mob/obj/room speech triggers) not ported


# -- do_emote (cf. 1stMud do_emote in act_comm.c) ----------------------------

def do_emote(ch, args):
    """Act out a free-form emote (cf. 1stMud do_emote in act_comm.c).
    [Verified: 04/07/2026] -- COMM_NOEMOTE check not ported (comm flags /
    channel penalties do not exist); MOBtrigger guard not ported (mobprogs
    not ported).

    Args:
        ch (dict): Acting character (player or mob instance).
        args (list): Emote text words.
    """
    if not args:
        chprintln(ch, "Emote what?")
        return

    argument = " ".join(args)
    act("$n $T", ch, None, argument, TO_ROOM)
    act("$n $T", ch, None, argument, TO_CHAR)


# -- do_tell (cf. 1stMud do_tell in act_comm.c) ------------------------------

def do_yell(ch, args):
    """Yell to everyone in the area (cf. 1stMud do_yell in act_comm.c).

    [PRIMESUD] COMM_NOSHOUT, swearcheck, channel-ignore, and COMM_QUIET
    not ported.  Also used by mobs (e.g. do_steal failure).

    Args:
        ch (dict): Speaker (player or mob instance).
        args (list): Words to yell.
    """
    if not args:
        chprintln(ch, "Yell what?")
        return
    text = " ".join(args)
    act("You yell '$t'", ch, text, None, TO_CHAR)
    act("$n yells '$t'", ch, text, None, TO_ZONE)


def do_tell(ch, args):
    """Tell something to a character in the room (cf. 1stMud do_tell in act_comm.c).

    [PRIMESUD] Simplified for single-player: target must be in same room.
    1stMud uses get_char_world (NPCs must be same room, players anywhere).
    COMM_NOTELL/DEAF/QUIET, is_ignoring, AFK, linkdead checks not ported.

    Args:
        ch (dict): Speaking character (player or mob instance).
        args (list): [target_name, ...message_words].
    """
    if len(args) < 2:
        chprintln(ch, "Tell whom what?")
        return

    target = args[0]
    argument = " ".join(args[1:])

    rs = world.rooms.get(ch.get("room"))
    if rs is None:
        chprintln(ch, "They aren't here.")
        return

    victim = None
    mob_id = get_char_room(target, rs["mobs"], world.chars, ch)
    if mob_id is not None:
        victim = world.chars[mob_id]
    else:
        # Check if targeting the player (for mob do_function use)
        player = world.chars.get(1)
        if player and player["room"] == ch["room"]:
            if is_name(target, player.get("name", "")):
                victim = player

    if victim is None:
        chprintln(ch, "They aren't here.")
        return

    victim_name = victim.get("name", "someone")
    ch_name = ch.get("name", "someone")
    chprintlnf(ch, "{cYou tell %s '{C%s{c'{x", victim_name, argument)
    chprintlnf(victim, "{c%s tells you '{C%s{c'{x", ch_name, argument)

    victim["reply"] = ch["id"]  # [PRIMESUD] stored as id, not dict ref (see _char_base)
    # [PRIMESUD] TRIG_SPEECH not ported


# -- do_reply (cf. 1stMud do_reply in act_comm.c) ----------------------------

def do_reply(ch, args):
    """Reply to last character who told you something (cf. 1stMud do_reply in act_comm.c).

    [PRIMESUD] Simplified for single-player: no COMM_NOTELL/DEAF/linkdead checks.

    Args:
        ch (dict): Speaking character.
        args (list): Words to reply.
    """
    # [PRIMESUD] reply stored as id; extracted (dead) targets resolve to None,
    # matching 1stMud's extract_char nulling wch->reply
    victim = world.chars.get(ch.get("reply"))
    if victim is None:
        chprintln(ch, "They aren't here.")
        return

    if not args:
        chprintln(ch, "Reply what?")
        return

    argument = " ".join(args)
    ch_name = ch.get("name", "someone")
    victim_name = victim.get("name", "someone")
    chprintlnf(ch, "{cYou tell %s '{C%s{c'{x", victim_name, argument)
    chprintlnf(victim, "{c%s tells you '{C%s{c'{x", ch_name, argument)
    victim["reply"] = ch["id"]  # [PRIMESUD] stored as id, not dict ref (see _char_base)


# -- do_function (cf. 1stMud do_function in interp.c) ------------------------

def do_function(ch, cmd_fn, argument):
    """Execute a command function as if ch invoked it (cf. 1stMud do_function in interp.c).

    Args:
        ch (dict): Character executing the command.
        cmd_fn (callable): Command function (e.g. do_say).
        argument (str): Raw argument string.
    """
    cmd_fn(ch, argument.split())


# -- Followers (cf. 1stMud add_follower..do_order in act_comm.c) --------------
# master/leader/pet stored as char ids, not dict refs (see _char_base).

def add_follower(ch, master):
    """Make ch follow master (cf. 1stMud add_follower in act_comm.c).

    Args:
        ch (dict): New follower (player or mob instance).
        master (dict): Character being followed.
    """
    if ch.get("master") is not None:
        # 1stMud: bug("Add_follower: non-null master.")
        return

    ch["master"] = master["id"]
    ch["leader"] = None

    if can_see(master, ch):
        act("$n now follows you.", ch, None, master, TO_VICT)

    act("You now follow $N.", ch, None, master, TO_CHAR)


def stop_follower(ch):
    """Detach ch from its master, stripping charm (cf. 1stMud stop_follower in act_comm.c).

    Args:
        ch (dict): Follower to detach.
    """
    if ch.get("master") is None:
        # 1stMud: bug("Stop_follower: null master.")
        return

    master = world.chars.get(ch["master"])

    if ch.get("affected_by", {}).get("charm"):
        ch["affected_by"].pop("charm", None)
        affect_strip(ch, GSN_CHARM_PERSON)

    if master is not None and can_see(master, ch) and ch.get("room") is not None:
        act("$n stops following you.", ch, None, master, TO_VICT)
        act("You stop following $N.", ch, None, master, TO_CHAR)
    if master is not None and master.get("pet") == ch["id"]:
        master["pet"] = None

    ch["master"] = None
    ch["leader"] = None


def nuke_pets(ch):
    """Extract ch's pet from the world (cf. 1stMud nuke_pets in act_comm.c).

    Args:
        ch (dict): Pet owner.
    """
    pet = world.chars.get(ch.get("pet")) if ch.get("pet") is not None else None
    if pet is not None:
        stop_follower(pet)
        if pet.get("room") is not None:
            act("$N slowly fades away.", ch, None, pet, TO_NOTVICT)
        from combat import _extract_char  # lazy import to avoid circular dependency
        _extract_char(pet, pull=True)
    ch["pet"] = None


def die_follower(ch):
    """Sever all follower links on ch's death (cf. 1stMud die_follower in act_comm.c).

    Args:
        ch (dict): Dying character.
    """
    if ch.get("master") is not None:
        master = world.chars.get(ch["master"])
        if master is not None and master.get("pet") == ch["id"]:
            master["pet"] = None
        stop_follower(ch)

    ch["leader"] = None

    for fch in list(world.chars.values()):
        if fch.get("master") == ch["id"]:
            stop_follower(fch)
        if fch.get("leader") == ch["id"]:
            fch["leader"] = fch["id"]  # 1stMud: fch->leader = fch


def do_follow(ch, args):
    """Follow a character in the room, or 'follow self' to stop (cf. 1stMud do_follow in act_comm.c).

    Args:
        ch (dict): Player state dict.
        args (list): Target keyword.
    """
    if not args:
        chprintln(ch, "Follow whom?")
        return

    frag = " ".join(args)

    # 1stMud: victim == ch -> stop following.  get_char_room is mob-only in
    # PrimeSUD, so self-targeting is matched by keyword. [PRIMESUD]
    if frag == "self" or is_name(frag, ch.get("name", "")):
        if ch.get("master") is None:
            chprintln(ch, "You already follow yourself.")
            return
        stop_follower(ch)
        return

    rs = world.rooms.get(ch.get("room"))
    mob_id = get_char_room(frag, rs["mobs"], world.chars, ch) if rs else None
    if mob_id is None:
        chprintln(ch, "They aren't here.")
        return
    victim = world.chars[mob_id]

    if ch.get("affected_by", {}).get("charm") and ch.get("master") is not None:
        act("But you'd rather follow $N!", ch, None,
            world.chars.get(ch["master"]), TO_CHAR)
        return

    # 1stMud: PLR_NOFOLLOW / RemBit(ch->act, PLR_NOFOLLOW) -- other players
    # can't follow you in single-player; not ported.

    if ch.get("master") is not None:
        stop_follower(ch)

    add_follower(ch, victim)


def do_ditch(ch, args):
    """Force a follower to stop following you (cf. 1stMud do_ditch in act_comm.c).

    Args:
        ch (dict): Player state dict.
        args (list): Follower keyword.
    """
    if not args:
        chprintln(ch, "Ditch whom?")
        return

    rs = world.rooms.get(ch.get("room"))
    mob_id = get_char_room(" ".join(args), rs["mobs"], world.chars, ch) if rs else None
    if mob_id is None:
        chprintln(ch, "They aren't here.")
        return
    victim = world.chars[mob_id]

    if ch.get("affected_by", {}).get("charm") and ch.get("master") is not None:
        act("But you'd rather follow $N!", ch, None,
            world.chars.get(ch["master"]), TO_CHAR)
        return

    # 1stMud: victim == ch -> "You try to ditch yourself.... unsuccessfuly."
    # Unreachable in PrimeSUD (mob-only lookup).

    if victim.get("master") != ch["id"]:
        chprintln(ch, "They aren't following you.")
        return

    stop_follower(victim)


def _order_interpret(och, words):
    """Execute an ordered command as an NPC. [PRIMESUD]

    1stMud pipes orders through interpret() -- the full command table.
    PrimeSUD command handlers assume the player as actor (tprint output,
    pickers), so only an NPC-safe subset is dispatched here, prefix-matched
    like interpret.  Unknown commands are silently ignored, matching the
    net effect of a failed NPC command in 1stMud.

    Args:
        och (dict): Ordered mob instance.
        words (list): Order words, e.g. ["kill", "rat"].
    """
    from combat import multi_hit, is_safe, do_flee  # lazy import (cycle)

    cmd = words[0]
    rest = words[1:]

    if ("kill".startswith(cmd) or "murder".startswith(cmd) or cmd == "hit") and rest:
        rs = world.rooms.get(och.get("room"))
        if rs is None:
            return
        targets = [m for m in rs["mobs"] if m != och["id"]]
        mob_id = get_char_room(" ".join(rest), targets, world.chars, och)
        if mob_id is None:
            return
        victim = world.chars[mob_id]
        if is_safe(och, victim) or och.get("fighting") is not None:
            return
        WaitState(och, PULSE_VIOLENCE)
        multi_hit(och, victim)
    elif "flee".startswith(cmd):
        do_flee(och, [])


def do_order(ch, args):
    """Order charmed followers to act (cf. 1stMud do_order in act_comm.c).

    Args:
        ch (dict): Player state dict.
        args (list): [target|'all', command, ...command args].
    """
    if len(args) < 2:
        chprintln(ch, "Order whom to do what?")
        return

    arg = args[0]
    order_words = args[1:]

    # 1stMud: refuse "order X delete" / "order X mob"
    if order_words[0] in ("delete", "mob"):
        chprintln(ch, "That will NOT be done.")
        return

    if ch.get("affected_by", {}).get("charm"):
        chprintln(ch, "You feel like taking, not giving, orders.")
        return

    rs = world.rooms.get(ch.get("room"))
    if rs is None:
        chprintln(ch, "You have no followers here.")
        return

    if arg == "all":
        f_all = True
        victim = None
    else:
        f_all = False
        mob_id = get_char_room(arg, rs["mobs"], world.chars, ch)
        if mob_id is None:
            chprintln(ch, "They aren't here.")
            return
        victim = world.chars[mob_id]

        # 1stMud: victim == ch -> "Aye aye, right away!" (unreachable: mob-only lookup)

        if (not victim.get("affected_by", {}).get("charm")
                or victim.get("master") != ch["id"]):
            chprintln(ch, "Do it yourself!")
            return

    found = False
    for och_id in list(rs["mobs"]):
        och = world.chars.get(och_id)
        if och is None:
            continue
        if (och.get("affected_by", {}).get("charm")
                and och.get("master") == ch["id"]
                and (f_all or och is victim)):
            found = True
            act("$n orders you to '" + " ".join(order_words) + "'.",
                ch, None, och, TO_VICT)
            _order_interpret(och, order_words)

    if found:
        WaitState(ch, PULSE_VIOLENCE)
        chprintln(ch, "Ok.")
    else:
        chprintln(ch, "You have no followers here.")
