"""Social commands: smile, nod, wave, etc. (cf. 1stMud find_social / check_social in interp.c)."""

import world
from handler import act, chprintln, get_char_room, is_awake, is_name, \
    TO_CHAR, TO_ROOM, TO_VICT, TO_NOTVICT
from urandom import randint

SOCIALS_FILE = "socials.txt"  # [PRIMESUD] canonical source; idx via tools/build_socials_idx.py
SOCIALS_IDX = "socials.idx"   # [PRIMESUD] '<offset>|<length>|<name>' per entry, sorted by name


def find_social(command):
    """Find the alphabetically-first social whose name starts with *command* (cf. 1stMud find_social in interp.c).

    [PRIMESUD] 1stMud hashes by first letter and walks a chain in
    insertion (data-file) order; socials.idx is instead a flat index
    sorted alphabetically by name, so the first line whose name
    startswith(command) while scanning in order is the alphabetical-prefix
    match -- the PrimeSUD equivalent of "first hit in the bucket". Index
    lines past the first entry lexicographically greater than *command*
    (and not itself a prefix match) can only be non-matches, since the
    file is sorted, so the scan stops there.

    Args:
        command (str): Player-typed command word (already lowercased).

    Returns:
        tuple or None: (name, offset, length) of the matching social entry
            in SOCIALS_FILE, or None if no social name has this prefix.
    """
    if not command:
        return None
    with open(SOCIALS_IDX) as f:
        data = f.read()
    for line in data.split("\n"):
        if not line:
            continue
        off_s, len_s, name = line.split("|", 2)
        if name.startswith(command):
            return (name, int(off_s), int(len_s))
        if name > command:
            break  # sorted index: no further line can be a prefix match
    return None


def _find_victim(player, arg):
    """Find the check_social target: self by keyword, else a room mob (cf. 1stMud get_char_room in handler.c).

    [PRIMESUD] get_char_room (handler.py) only searches mob instances, so
    self-targeting ("smile self" / "smile <own name>") is matched directly
    against the player's own name first, mirroring the same pattern used
    by do_follow (comm.py) and magic._find_room_char.
    """
    if arg == "self" or is_name(arg, player.get("name", "")):
        return player
    rs = world.rooms.get(player.get("room"))
    if rs is None:
        return None
    mob_id = get_char_room(arg, rs["mobs"], world.chars, player)
    if mob_id is None:
        return None
    return world.chars[mob_id]


def check_social(player, command, argument):
    """Run a social command (smile, nod, wave, ...) if *command* matches one (cf. 1stMud check_social in interp.c).

    Loads the social's 7 messages with a single seek + read against
    SOCIALS_FILE (offset/length from find_social), then follows interp.c's
    branch order: no-arg, victim-not-found, self-targeted, and
    victim-found (with the NPC mirror-response/slap roll). act() already
    no-ops on an empty format string (cf. 1stMud act(NULL) no-op), so
    blank fields (e.g. "snore"'s found/auto messages) need no extra
    guarding here.

    Not ported [PRIMESUD]:
      - COMM_NOEMOTE ("You are anti-social!") -- comm flags don't exist.
      - is_ignoring (IGNORE_SOCIALS) -- single-player, no other players.
      - TO_SOCIALS colour prefix -- CTAG random-colour system absent
        (cf. src/handler.py:809 note).
      - victim->desc == NULL guard on the NPC mirror response -- always
        true here since get_char_room only ever returns NPC instances.

    Args:
        player (dict): Player state dict.
        command (str): Command word as typed (already lowercased).
        argument (str): Verbatim tail after the command word.

    Returns:
        bool: True if *command* matched a social (handled, whether or not
            it actually fired -- position gates etc. still count as
            handled), False if no social matched.
    """
    hit = find_social(command)
    if hit is None:
        return False
    name, offset, length = hit

    pos = player.get("pos", "standing")
    if pos == "dead":
        chprintln(player, "Lie still; you are DEAD.")
        return True
    if pos in ("incap", "mortal"):
        chprintln(player, "You are hurt far too bad for that.")
        return True
    if pos == "stunned":
        chprintln(player, "You are too stunned to do that.")
        return True
    if pos == "sleeping" and name != "snore":
        chprintln(player, "In your dreams, or what?")
        return True

    with open(SOCIALS_FILE) as f:
        f.seek(offset)
        data = f.read(length)
    (char_no_arg, others_no_arg, char_found, others_found, vict_found,
     char_auto, others_auto) = data.split("\n")[:7]

    # late import: commands.py imports socials [PRIMESUD] (cf. info.py's
    # _help_is_name late-import of commands.split_args for the same reason)
    from commands import one_argument
    arg, _rest = one_argument(argument)

    if not arg:
        act(others_no_arg, player, None, None, TO_ROOM)
        act(char_no_arg, player, None, None, TO_CHAR)
        return True

    victim = _find_victim(player, arg)
    if victim is None:
        chprintln(player, "They aren't here.")
        return True

    if victim is player:
        act(others_auto, player, None, victim, TO_ROOM)
        act(char_auto, player, None, victim, TO_CHAR)
        return True

    act(others_found, player, None, victim, TO_NOTVICT)
    act(char_found, player, None, victim, TO_CHAR)
    act(vict_found, player, None, victim, TO_VICT)

    if (not player.get("is_npc") and victim.get("is_npc")
            and not victim.get("affected_by", {}).get("charm")
            and is_awake(victim)):
        roll = randint(0, 15)  # cf. 1stMud number_bits(4)
        if roll <= 8:
            act(others_found, victim, None, player, TO_NOTVICT)
            act(char_found, victim, None, player, TO_CHAR)
            act(vict_found, victim, None, player, TO_VICT)
        elif roll <= 12:
            act("$n slaps $N.", victim, None, player, TO_NOTVICT)
            act("You slap $N.", victim, None, player, TO_CHAR)
            act("$n slaps you.", victim, None, player, TO_VICT)
        # 13-15: no response

    return True
