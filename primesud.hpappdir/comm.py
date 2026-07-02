"""Communication commands: say, tell (cf. 1stMud do_say/do_tell in act_comm.c)."""

import world
from handler import (act, chprintln, chprintlnf, is_name, get_char_room,
                   TO_CHAR, TO_ROOM)


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


# -- do_tell (cf. 1stMud do_tell in act_comm.c) ------------------------------

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
    mob_id = get_char_room(target, rs["mobs"], world.chars)
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
