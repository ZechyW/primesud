"""Automated combat action engine and rotation editor [PRIMESUD].

No 1stMud equivalent. While a player fights with `autoskill` enabled, the
engine fires one appropriate debuff, offensive spell, or physical skill per
combat round on the player's behalf through the existing `do_cast`/`do_bash`/
`do_trip`/`do_dirt`/`do_disarm`/`do_kick` handlers -- mana, lag, fizzle, and
messages all run unchanged. Complements `autostance` and `wimpy`; does not
automate healing, quaffing, or flee. See AUTOSKILL_PLAN.md (design doc,
deleted after ship -- decisions harvested into DESIGN.md/FEATURES.md) for
the full rationale.
"""

import terminal
from terminal import tprint
from hpprime import eval as ppleval
from picker import _force_numeric_keys
from handler import is_affected, chprintln, PLR_AUTOSKILL, PLR_DEFAULTS
from skill_utils import can_use_skill_spell, is_runtime_spell, skill_level, get_skill, spell_mana
from skills_table import (SKILL_TABLE, SKILLS, GSN_BLINDNESS, GSN_CURSE,
                           GSN_BASH, GSN_TRIP, GSN_DIRT, GSN_DISARM, GSN_KICK,
                           GSN_HAND_TO_HAND)
from config import POS_ORDER
from combat import do_bash, do_trip, do_dirt, do_disarm, do_kick
from magic import do_cast
from util import num_str
import world

_LEARNED_FLOOR = 75
_OFFENSE_RESERVE_PCT = 25
_PAGE_SIZE = 10
_NAV_KEYS = {2: ("\\U", None), 12: ("\\D", None)}  # navpad Up/Dn sentinels


def _find_sn_by_name(name):
    """One-time lookup of a skill/spell number by name. [PRIMESUD]

    `weaken` has no GSN_* constant in the generated skills_table.py, so its
    sn is resolved here at import time instead of being hardcoded.
    """
    for sn, sk in SKILL_TABLE:
        if sk.get("name") == name:
            return sn
    return None


GSN_WEAKEN = _find_sn_by_name("weaken")
_DEBUFF_SNS = (GSN_BLINDNESS, GSN_WEAKEN, GSN_CURSE)  # fixed heuristic order
_DEBUFF_SET = set(sn for sn in _DEBUFF_SNS if sn is not None)
_SKILL_HANDLERS = {
    GSN_BASH: do_bash, GSN_TRIP: do_trip, GSN_DIRT: do_dirt,
    GSN_DISARM: do_disarm, GSN_KICK: do_kick,
}


def _build_candidates(player):
    """Ordered heuristic candidate list: debuffs, spells by level desc, skills. [PRIMESUD]

    Returns:
        list: (sn, name, kind, default_included) tuples, kind in
            ('debuff', 'spell', 'skill').
    """
    learned = player.get("learned", {})
    cands = []

    for sn in _DEBUFF_SNS:
        if sn is None:
            continue
        if (learned.get(sn, 0) > 0 and can_use_skill_spell(player, sn)
                and is_runtime_spell(sn)):
            cands.append((sn, SKILLS[sn]["name"], "debuff", learned[sn] >= _LEARNED_FLOOR))

    offense = []
    for sn, pct in learned.items():
        # _SKILL_HANDLERS check: kick's table entry is target=char_offensive,
        # so only its spell_fun being spell_null keeps it out of the spell
        # scan -- exclude the physical skills explicitly instead of relying
        # on that invariant surviving a skills_table.py regeneration
        if sn in _DEBUFF_SET or sn in _SKILL_HANDLERS or pct <= 0:
            continue
        sk = SKILLS.get(sn)
        if sk is None or sk.get("target") not in ("char_offensive", "obj_char_offensive"):
            continue
        if POS_ORDER["fighting"] < POS_ORDER.get(sk.get("min_pos"), 0):
            continue
        if not (can_use_skill_spell(player, sn) and is_runtime_spell(sn)):
            continue
        offense.append(sn)
    offense.sort(key=lambda sn: (-skill_level(player, sn), sn))
    for sn in offense:
        cands.append((sn, SKILLS[sn]["name"], "spell", learned[sn] >= _LEARNED_FLOOR))

    for sn in (GSN_BASH, GSN_TRIP, GSN_DIRT, GSN_DISARM, GSN_KICK):
        if get_skill(player, sn) > 0:
            cands.append((sn, SKILLS[sn]["name"], "skill", True))

    return cands


def get_rotation(player):
    """Materialize the player's effective rotation. [PRIMESUD]

    No saved `autoskill_rot` -> pure heuristic default. Otherwise: saved
    entries first (in saved order, keeping saved include/exclude, dropping
    entries no longer in the candidate set), then any new candidates
    appended at the end in heuristic order with default inclusion.

    Args:
        player (dict): Player state dict.

    Returns:
        list: (sn, name, kind, included) tuples in fire order.
    """
    candidates = _build_candidates(player)
    saved = player.get("autoskill_rot")
    if saved is None:
        return [(sn, name, kind, incl) for sn, name, kind, incl in candidates]

    by_name = {}
    for sn, name, kind, incl in candidates:
        by_name[name] = (sn, kind)

    rotation = []
    seen = set()
    for entry in saved:
        included = not entry.startswith("!")
        name = entry[1:] if entry.startswith("!") else entry
        info = by_name.get(name)
        if info is None:
            continue  # no longer a known candidate -- dropped
        sn, kind = info
        rotation.append((sn, name, kind, included))
        seen.add(name)

    for sn, name, kind, incl in candidates:
        if name not in seen:
            rotation.append((sn, name, kind, incl))

    return rotation


def _mana_ok(player, cost):
    """True if paying `cost` mana leaves the offense reserve intact. [PRIMESUD]"""
    mana = player.get("mana", 0)
    if mana < cost:
        return False
    return mana - cost >= player.get("max_mana", 0) * _OFFENSE_RESERVE_PCT // 100


def _skill_eligible(player, victim, sn):
    """Cheap pre-filters mirroring each do_* handler's static early-outs. [PRIMESUD]

    Only mirrors conditions that would otherwise fail identically every
    round (position, equipment, existing affects) -- never the random
    success roll, which the handler itself still resolves.
    """
    if sn == GSN_BASH:
        return POS_ORDER.get(victim.get("pos", "standing"), 0) >= POS_ORDER["fighting"]
    if sn == GSN_TRIP:
        if victim.get("affected_by", {}).get("flying"):
            return False
        if POS_ORDER.get(victim.get("pos", "standing"), 0) < POS_ORDER["fighting"]:
            return False
        if (player.get("affected_by", {}).get("charm")
                and player.get("master") == victim.get("id")):
            return False
        return True
    if sn == GSN_DIRT:
        return not victim.get("affected_by", {}).get("blind")
    if sn == GSN_DISARM:
        if victim.get("equip", {}).get("wield") is None:
            return False
        if (player.get("equip", {}).get("wield") is None
                and get_skill(player, GSN_HAND_TO_HAND) == 0):
            return False
        return True
    return True  # GSN_KICK: no static gate beyond get_skill > 0


def auto_skill_round(player):
    """Fire one automatic offensive action for a fighting player, if eligible. [PRIMESUD]

    Combat hook: call once per player per violence pulse (mirrors 1stMud
    mob special-attack dispatch). Performs all gating internally, so it is
    safe to call unconditionally from the combat loop. Walks
    `get_rotation(player)` in order and fires the first eligible entry
    through the normal command handlers, then returns.

    Args:
        player (dict): Player state dict; NPCs are skipped silently.
    """
    if player.get("is_npc"):
        return
    if not (player.get("flags", PLR_DEFAULTS) & PLR_AUTOSKILL):
        return
    if player.get("wait", 0) != 0:
        return
    if player.get("_cmd_queued"):
        return
    if player.get("pos") != "fighting":
        return
    victim_id = player.get("fighting")
    if victim_id is None or victim_id not in world.chars:
        return
    victim = world.chars[victim_id]

    for sn, name, kind, included in get_rotation(player):
        if not included:
            continue
        if kind == "debuff" or kind == "spell":
            if kind == "debuff" and is_affected(victim, sn):
                continue
            if not _mana_ok(player, spell_mana(player, sn)):
                continue
            do_cast(player, [name])
            return
        if not _skill_eligible(player, victim, sn):
            continue
        handler = _SKILL_HANDLERS.get(sn)
        if handler is not None:
            handler(player, [])
            return


# -- Rotation display + editor --------------------------------------------------

def _row_dicts(player):
    """Build working-list dicts (sn/name/kind/included/pct/new) for list/editor. [PRIMESUD]"""
    saved = player.get("autoskill_rot")
    saved_names = None
    if saved is not None:
        saved_names = set()
        for entry in saved:
            saved_names.add(entry[1:] if entry.startswith("!") else entry)
    learned = player.get("learned", {})
    work = []
    for sn, name, kind, included in get_rotation(player):
        is_new = saved_names is not None and name not in saved_names
        work.append({"sn": sn, "name": name, "kind": kind, "included": included,
                     "pct": learned.get(sn, 0), "new": is_new})
    return work


def _format_row(pos_in_page, name, pct, included, is_new):
    """Render one numbered rotation row, picker-style (1-9 then 0). [PRIMESUD]"""
    label = num_str(pos_in_page + 1) if pos_in_page < 9 else "0"
    line = "  " + label + ") " + name + " " + num_str(pct) + "%"
    if not included:
        line += " {D(off){x"
    if is_new:
        line += " {G(new){x"
    return line


def _render_rows(work, out):
    """Feed each formatted row to `out` (chprintln-bound or tprint). [PRIMESUD]"""
    for i, entry in enumerate(work):
        out(_format_row(i % _PAGE_SIZE, entry["name"], entry["pct"],
                         entry["included"], entry["new"]))


def _list_rotation(player):
    """Print the rotation read-only via chprintln. [PRIMESUD]"""
    work = _row_dicts(player)
    chprintln(player, "{YAutoskill rotation{x")
    if not work:
        chprintln(player, "  (no known offensive skills or spells yet)")
        return
    _render_rows(work, lambda line: chprintln(player, line))


def _print_rotation_rows(work):
    """Print the full working rotation once through the normal scroll path. [PRIMESUD]"""
    tprint("{YAutoskill rotation{x")
    tprint("{w[Up/Dn] sel  [+/-] move  [*] on/off  [Enter] save  [Esc] cancel{x")
    _render_rows(work, tprint)


def _update_status(tr, work, sel):
    """Update the status-line cursor only -- no list reprint. [PRIMESUD]"""
    entry = work[sel]
    tag = "" if entry["included"] else " (off)"
    # Key legend lives in the printed header (_print_rotation_rows); the
    # status line only fits the selection within columns-6 chars.
    tr.set_status("> " + num_str(sel + 1) + ") " + entry["name"] + tag
                  + "  [" + num_str(sel + 1) + "/" + num_str(len(work)) + "]")


def _save_rotation(player, work):
    """Commit the working list to player['autoskill_rot']. [PRIMESUD]"""
    rot = []
    for entry in work:
        rot.append(entry["name"] if entry["included"] else "!" + entry["name"])
    player["autoskill_rot"] = rot


def _edit_rotation(player):
    """Blocking rotation editor: reorder, toggle, save, or discard. [PRIMESUD]

    Cursor lives in the status line (set_status), never reprinted with the
    list; only reordering ('+'/'-') or toggling ('*') reprint the list,
    since the terminal is scrollback-only and cannot update printed rows
    in place. See AUTOSKILL_PLAN.md "Editor UI" for the full key table.
    """
    work = _row_dicts(player)
    if not work:
        tprint("You have no offensive skills or spells to automate yet.")
        return

    tr = terminal.tr
    # raw copy keeps colour codes; plain status_text is the stub fallback
    old_status = getattr(tr, "status_text_raw", tr.status_text)
    sb0 = tr._scrollback_ms
    _force_numeric_keys()
    sel = 0
    _print_rotation_rows(work)
    _update_status(tr, work, sel)
    try:
        while True:
            result = tr.poll_char(_NAV_KEYS)
            if result is None:
                ppleval("WAIT(1/1e3)")
                continue
            char, _auto_submit = result
            if tr._scrollback_ms:
                tr._scrollback_ms = 0

            if char == "\\e":
                tprint("Cancelled.")
                return
            if char == "\n":
                _save_rotation(player, work)
                tprint("Rotation saved.")
                return
            if char == "\\U":
                sel = (sel - 1) % len(work)
                _update_status(tr, work, sel)
            elif char == "\\D":
                sel = (sel + 1) % len(work)
                _update_status(tr, work, sel)
            elif char == "*":
                work[sel]["included"] = not work[sel]["included"]
                _print_rotation_rows(work)
                _update_status(tr, work, sel)
            elif char == "+":
                if sel < len(work) - 1:
                    work[sel], work[sel + 1] = work[sel + 1], work[sel]
                    sel += 1
                    _print_rotation_rows(work)
                    _update_status(tr, work, sel)
            elif char == "-":
                if sel > 0:
                    work[sel], work[sel - 1] = work[sel - 1], work[sel]
                    sel -= 1
                    _print_rotation_rows(work)
                    _update_status(tr, work, sel)
            elif isinstance(char, str) and char.isdigit():
                page = sel // _PAGE_SIZE
                offset = 9 if char == "0" else int(char) - 1
                target = page * _PAGE_SIZE + offset
                if target < len(work):
                    sel = target
                    _update_status(tr, work, sel)
    finally:
        tr._scrollback_ms = sb0
        tr.set_status(old_status)
        tr.resync_keyboard()


def do_autoskill(player, args):
    """Show/configure autoskill and its rotation. [PRIMESUD] (no 1stMud equivalent)

    Bare call shows status and usage. 'on'/'off' set the PLR_AUTOSKILL flag;
    'edit' opens the blocking rotation editor; 'list' prints the rotation
    read-only; 'reset' discards any custom order/exclusions back to the pure
    heuristic default.

    Args:
        player (dict): Player state dict.
        args (list): Command arguments; args[0] in
            ('on', 'off', 'edit', 'list', 'reset'), or empty for help.
    """
    if not args:
        state = "on" if player.get("flags", PLR_DEFAULTS) & PLR_AUTOSKILL else "off"
        chprintln(player, "Autoskill is " + state + ". It uses offensive skills and spells automatically in combat.")
        chprintln(player, "Usage: autoskill <on|off|edit|list|reset>")
        return None

    sub = args[0].lower()
    if sub == "on":
        player["flags"] = player.get("flags", PLR_DEFAULTS) | PLR_AUTOSKILL
        chprintln(player, "You now attack with your skills and spells automatically.")
        return None
    if sub == "off":
        player["flags"] = player.get("flags", PLR_DEFAULTS) & ~PLR_AUTOSKILL
        chprintln(player, "You no longer attack with your skills and spells automatically.")
        return None
    if sub == "edit":
        _edit_rotation(player)
        return None
    if sub == "list":
        _list_rotation(player)
        return None
    if sub == "reset":
        player.pop("autoskill_rot", None)
        chprintln(player, "Autoskill rotation reset to the default order.")
        return None

    chprintln(player, "Usage: autoskill <on|off|edit|list|reset>")
    return None
