"""Player command aliases (cf. 1stMud alias.c)."""

from terminal import tprint

MAX_ALIAS = 10  # cf. 1stMud defines.h:122


def substitute_alias(player, argument):
    """Expand a matching alias at the head of *argument*, if any
    (cf. 1stMud substitute_alias in alias.c).

    Runs once, from the top of commands.interpret(), before the command
    table lookup. On a match the alias name is replaced by its substitution
    text and any remaining tail is appended after a space; the result is
    handed straight to the normal interpret() flow, not fed back through
    substitute_alias, so expansion is never recursive (cf. alias.c: the C
    original calls interpret() directly at the end of substitute_alias, not
    itself).

    [PRIMESUD] ch->prefix accumulation (alias.c:45-54) is not ported -- there
    is no "prefix" command in PrimeSUD, so that branch and the "prefix" skip
    check (alias.c:58) are dropped entirely.
    [PRIMESUD] MAX_INPUT_LENGTH truncation (alias.c:84-88) is not ported --
    PrimeSUD defines no such input length cap.

    Args:
        player (dict): Player state dict.
        argument (str): Raw input line, as typed (pre-strip is fine; leading
            whitespace is tolerated).

    Returns:
        str: *argument* unchanged, or the alias-expanded command line.
    """
    if player.get("is_npc"):
        return argument
    aliases = player.get("aliases")
    if not aliases:
        return argument
    # cf. alias.c:56-58 !str_prefix("alias", argument) / !str_prefix("una", argument)
    # -- str_prefix is a case-insensitive literal prefix test on the whole
    # remaining input, not just the extracted command word.
    low = argument.lstrip().lower()
    if low.startswith("alias") or low.startswith("una"):
        return argument
    from commands import one_argument  # late import: commands imports aliases
    word, rest = one_argument(argument)
    for name, sub in aliases:
        if word == name:
            if rest:
                return sub + " " + rest
            return sub
    return argument


def do_alias(player, argument):
    """List, show, or define an alias (cf. 1stMud do_alias in alias.c).

    Args:
        player (dict): Player state dict.
        argument (str): Raw command tail (cf. 1stMud do_fun argument) -- the
            substitution text must survive verbatim (case, spacing), so this
            is the free-text tail, not a lowercased token list.

    Returns:
        None
    """
    if player.get("is_npc"):
        return None
    from commands import one_argument  # late import: commands imports aliases
    arg, argument = one_argument(argument)

    aliases = player.setdefault("aliases", [])

    if not arg:
        if not aliases:
            tprint("You have no aliases defined.")
            return None
        tprint("Your current aliases are:")
        for name, sub in aliases:
            tprint("    " + name + ":  " + sub)
        return None

    if arg.startswith("una") or arg == "alias":
        tprint("Sorry, that word is reserved.")
        return None

    if not argument:
        for name, sub in aliases:
            if name == arg:
                tprint(name + " aliases to '" + sub + "'.")
                return None
        tprint("That alias is not defined.")
        return None

    # [PRIMESUD] CMD_NOALIAS (alias.c:162-167) not ported -- PrimeSUD's
    # command table carries no per-command flags, so there is nothing to
    # check a looked-up command against here.
    # [PRIMESUD] save-format safety: alias lines are persisted as
    # "p.alias.<name>=<sub>" (game_state.py); a name containing '=' or '.'
    # would corrupt that line on save/load, so reject it up front. 1stMud's
    # one_argument already precludes whitespace in the extracted name.
    if "=" in arg or "." in arg or "~" in arg:
        tprint("Alias names may not contain '=', '.' or '~'.")
        return None
    # [PRIMESUD] '~' is the save-payload line separator (game_state.py); a
    # substitution containing it would corrupt the save on the next write.
    if "~" in argument:
        tprint("Alias text may not contain '~'.")
        return None

    for pair in aliases:
        if pair[0] == arg:
            pair[1] = argument
            tprint(arg + " is now realiased to '" + argument + "'.")
            return None

    if len(aliases) >= MAX_ALIAS:
        tprint("Sorry, you have reached the alias limit.")
        return None

    aliases.append([arg, argument])
    tprint(arg + " is now aliased to '" + argument + "'.")
    return None


def do_unalias(player, args):
    """Remove a defined alias (cf. 1stMud do_unalias in alias.c).

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments; only args[0] (the alias name)
            is used.

    Returns:
        None
    """
    if player.get("is_npc"):
        return None
    if not args:
        tprint("Unalias what?")
        return None
    arg = args[0]
    aliases = player.setdefault("aliases", [])
    for pair in aliases:
        if pair[0] == arg:
            aliases.remove(pair)
            tprint("Alias removed.")
            return None
    tprint("No alias of that name to remove.")
    return None
