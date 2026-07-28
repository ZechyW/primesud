"""Global quest system: timed kill-list events (cf. 1stMud gquest.c).

1stMud ROM derivative (c) 2001-2004 Markanth.

[PRIMESUD] Single-player adaptation.  The kill list is template vnums
(1stMud gq_mobs is already vnum-based); any live instance of a listed vnum
counts.  Multiplayer machinery -- join announcements to others, 'progress',
the note-board history ('hist'), immortal 'end'/'next' -- is skipped.
Target selection draws from area reset data instead of the live mob list
(PrimeSUD lazy-loads areas; see quest._random_quest_mob for the pattern).

State lives in the module-level gquest_info dict (cf. 1stMud GQuestInfo)
and is persisted by game_state (g.gq* save lines).
"""

import world
from world import MOB_DEFS, ROOM_DEFS, AREA_LEVELS
from config import (MAX_LEVEL, MAX_MORTAL_LEVEL, GQUEST_INITIAL_DELAY,
                    GQUEST_AUTO_DELAY_MIN, GQUEST_AUTO_DELAY_MAX,
                    mins_to_ticks, ticks_to_mins, on_minute)
from handler import chprintln
from quest import (chance, is_quester, mob_tell, quest_target_ok,
                   quest_area_def, _find_spec_mob, _intstr, _prefix,
                   _QUEST_AREA_EXCLUDE)
from urandom import randint
from util import sstr, num_str, pad_left, pad_right

# cf. 1stMud gquest_t in defines.h
GQUEST_OFF     = 0
GQUEST_WAITING = 1  # [PRIMESUD] unused live state; kept for legacy save load
GQUEST_RUNNING = 2

# cf. 1stMud GQuestInfo gquest_info; "joined"/"pmobs" fold the per-player
# GqData list into the single player's slot [PRIMESUD]
gquest_info = {
    "running":   GQUEST_OFF,
    "timer":     mins_to_ticks(GQUEST_INITIAL_DELAY),  # world ticks
    "mob_count": 0,
    "minlevel":  0,
    "maxlevel":  0,
    "qpoints":   0,
    "gold":      0,
    "cost":      0,
    "who":       "",
    "mobs":      [],         # master target vnums
    "joined":    False,
    "pmobs":     [],         # player's copy; -1 = killed
}


def _next_auto_timer():
    """Return the delay before the next auto gquest, in world ticks. [PRIMESUD]"""
    lo = GQUEST_AUTO_DELAY_MIN
    hi = GQUEST_AUTO_DELAY_MAX
    if hi < lo:
        hi = lo
    return mins_to_ticks(randint(lo, hi))


def gquester(player):
    """True if the player has joined the running gquest (cf. 1stMud Gquester in macro.h)."""
    return gquest_info["running"] != GQUEST_OFF and gquest_info["joined"]


def gq_is_target(vnum):
    """True if vnum is on the master gquest target list (cf. 1stMud is_gqmob(NULL, vnum))."""
    return gquest_info["running"] != GQUEST_OFF and vnum in gquest_info["mobs"]


def gq_is_player_target(vnum):
    """True if vnum is still on the player's remaining kill list (cf. 1stMud is_gqmob(gql, vnum))."""
    return (gquest_info["running"] != GQUEST_OFF and gquest_info["joined"]
            and vnum in gquest_info["pmobs"])


def _count_killed():
    """Number of targets the player has killed (cf. 1stMud count_gqmobs in gquest.c)."""
    if gquest_info["running"] == GQUEST_OFF or not gquest_info["joined"]:
        return 0
    return sum(1 for v in gquest_info["pmobs"] if v == -1)


def end_gquest():
    """Stop the gquest and schedule the next auto quest (cf. 1stMud end_gquest in gquest.c)."""
    # Refund a paid start that never got running
    if (gquest_info["running"] != GQUEST_RUNNING and gquest_info["who"]
            and gquest_info["cost"] > 0):
        player = world.chars.get(1)
        if player is not None and player.get("name") == gquest_info["who"]:
            player["trivia"] = player.get("trivia", 0) + gquest_info["cost"]
            chprintln(player,
                      "Unable to start global quest, being refunded "
                      + str(gquest_info["cost"]) + " TP.")
    gquest_info["running"] = GQUEST_OFF
    gquest_info["mob_count"] = 0
    gquest_info["timer"] = _next_auto_timer()
    gquest_info["qpoints"] = 0
    gquest_info["gold"] = 0
    gquest_info["minlevel"] = 0
    gquest_info["maxlevel"] = 0
    gquest_info["cost"] = 0
    gquest_info["who"] = ""
    gquest_info["mobs"] = []
    gquest_info["joined"] = False
    gquest_info["pmobs"] = []


def _collect_gq_vnums(need):
    """Collect candidate target vnums from area reset data. [PRIMESUD]

    Replaces 1stMud generate_gquest's live-mob scan.  Loads eligible areas
    one at a time until enough distinct candidates are found, to bound the
    lazy-load cost.

    Args:
        need (int): Requested target count.

    Returns:
        list: Distinct eligible mob vnums.
    """
    lo = gquest_info["minlevel"] - 10
    hi = gquest_info["maxlevel"] + 10
    tags = []
    for tag, (alo, ahi) in AREA_LEVELS.items():
        if tag in _QUEST_AREA_EXCLUDE:
            continue
        if alo <= hi and ahi >= lo:
            tags.append(tag)

    vnums = []
    seen = {}
    enough = max(15, need * 3)
    while tags and len(vnums) < enough:
        tag = tags.pop(randint(0, len(tags) - 1))
        adef = quest_area_def(tag)
        if adef is None:
            continue
        for entry in adef["resets"]:
            if entry[0] != "M":
                continue
            mvnum, rvnum = entry[1], entry[3]
            if mvnum in seen:
                continue
            tpl = MOB_DEFS._data.get(mvnum)
            rdef = ROOM_DEFS._data.get(rvnum)
            if tpl is None or rdef is None:
                continue
            if not (lo <= tpl.get("level", 1) <= hi):
                continue
            if not quest_target_ok(tpl, rdef):
                continue
            seen[mvnum] = True
            vnums.append(mvnum)
    return vnums


def generate_gquest(who_name):
    """Build the target list and open the joining window (cf. 1stMud generate_gquest in gquest.c).

    Args:
        who_name (str): Starting player's name, or "" for an auto quest.

    Returns:
        bool: False if not enough targets were found (gquest ended).
    """
    vnums = _collect_gq_vnums(gquest_info["mob_count"])
    if len(vnums) < 5:
        end_gquest()
        return False
    if len(vnums) < gquest_info["mob_count"]:
        gquest_info["mob_count"] = len(vnums)

    # cf. 1stMud is_random_gqmob: distinct picks
    mobs = []
    for _ in range(gquest_info["mob_count"]):
        mobs.append(vnums.pop(randint(0, len(vnums) - 1)))
    gquest_info["mobs"] = mobs
    gquest_info["pmobs"] = []
    gquest_info["joined"] = False
    gquest_info["qpoints"] = randint(15, 30) * gquest_info["mob_count"]
    gquest_info["gold"] = randint(100, 150) * gquest_info["mob_count"]
    # [PRIMESUD] 1stMud opens a 3-minute join window (GQUEST_WAITING) and
    # cancels with "Not enough people" if no one joins; single-player quests
    # start running immediately and the player may join at any time.
    gquest_info["timer"] = mins_to_ticks(
        randint(4 * gquest_info["mob_count"], 6 * gquest_info["mob_count"]))
    gquest_info["running"] = GQUEST_RUNNING
    gquest_info["who"] = who_name or "AutoQuest"

    player = world.chars.get(1)
    if player is not None:
        if who_name:
            chprintln(player,
                      "You announce a Global Quest for levels "
                      + str(gquest_info["minlevel"]) + " to "
                      + str(gquest_info["maxlevel"]) + " with "
                      + str(gquest_info["mob_count"]) + " targets.")
        else:
            chprintln(player,
                      "A Global Quest for levels " + str(gquest_info["minlevel"])
                      + " to " + str(gquest_info["maxlevel"])
                      + " has started.  Type 'gquest info' to see the quest.")
        # [PRIMESUD] auto-join the single player when eligible (same gates
        # as 'gquest join': no regular quest running, level in range)
        if (not is_quester(player)
                and gquest_info["minlevel"] <= player["level"]
                <= gquest_info["maxlevel"]):
            gquest_info["joined"] = True
            gquest_info["pmobs"] = list(gquest_info["mobs"])
            chprintln(player,
                      "You have " + _intstr(ticks_to_mins(gquest_info["timer"]), "minute")
                      + " to complete the task!")
        else:
            chprintln(player,
                      "You have " + _intstr(ticks_to_mins(gquest_info["timer"]), "minute")
                      + " to join and complete the task!")
    return True


def auto_gquest():
    """Start an automatic gquest scaled to the player (cf. 1stMud auto_gquest in gquest.c).

    [PRIMESUD] 1stMud surveys all online players; here the band derives
    from the one player's level.  The hero-count widening branch (needs
    3+ hero-level players) can never fire and is skipped.
    """
    if gquest_info["running"] != GQUEST_OFF:
        return
    player = world.chars.get(1)
    if player is None:
        end_gquest()
        return

    lbonus = randint(10, 20)
    minlvl = max(1, player["level"] - lbonus)
    maxlvl = min(MAX_MORTAL_LEVEL, player["level"] + lbonus)
    half = (maxlvl - minlvl) // 2
    middle = max(minlvl, min(maxlvl - half, maxlvl))
    minlvl = max(1, randint(minlvl, max(minlvl, (middle * 2) // 3)))
    hi = min(MAX_MORTAL_LEVEL, max((middle * 3) // 2, minlvl + 10))
    maxlvl = min(MAX_MORTAL_LEVEL, randint(min(hi, maxlvl), max(hi, maxlvl)))

    # [PRIMESUD] the randomized band can drift off the player's level
    # (e.g. low levels); clamp so the single player is always eligible
    minlvl = min(minlvl, player["level"])
    maxlvl = max(maxlvl, player["level"])

    gquest_info["mob_count"] = randint(5, 30 - lbonus)
    gquest_info["minlevel"] = max(1, minlvl)
    gquest_info["maxlevel"] = min(MAX_MORTAL_LEVEL, maxlvl)
    gquest_info["cost"] = 0
    generate_gquest("")


def start_gquest(player, args):
    """Handle 'gquest start <min> <max> <#mobs>' at the registar (cf. 1stMud start_gquest in gquest.c)."""
    registar = _find_spec_mob(player, "spec_registar")
    if registar is None:
        chprintln(player, "You can't do that here.")
        return
    if registar.get("fighting") is not None:
        chprintln(player, "Wait until the fighting stops.")
        return
    # 1stMud: same player can't start twice in a row --
    # [PRIMESUD] skipped, there is only one player

    if len(args) < 3:
        chprintln(player, "Syntax: gquest start <min level> <max level> <#mobs>")
        return
    try:
        blevel, elevel, mobs = int(args[0]), int(args[1]), int(args[2])
    except ValueError:
        chprintln(player, "Syntax: gquest start <min level> <max level> <#mobs>")
        return

    if blevel <= 0 or blevel > MAX_LEVEL or elevel > MAX_LEVEL:
        chprintln(player, "Level must be between 1 and " + str(MAX_LEVEL) + ".")
        return
    if elevel <= blevel:
        chprintln(player, "Max level must be greater than the min level.")
        return
    if elevel - blevel < 10:
        chprintln(player, "Level difference must 10 levels or higher.")
        return
    if mobs < 5 or mobs > 25:
        chprintln(player, "Number of mobs must be between 5 and 25.")
        return
    if gquest_info["running"] != GQUEST_OFF:
        chprintln(player, "There is already a global quest running!")
        return

    cost = 5 + mobs // 5
    if player.get("trivia", 0) < cost:
        mob_tell(player, registar,
                 "It costs " + str(cost) + " Trivia Points to start a global quest with "
                 + str(mobs) + " mobs.")
        return
    mob_tell(player, registar,
             str(mobs) + " mobs have cost you " + str(cost) + " trivia points.")
    player["trivia"] -= cost

    gquest_info["minlevel"] = blevel
    gquest_info["maxlevel"] = elevel
    gquest_info["mob_count"] = mobs
    gquest_info["cost"] = cost
    gquest_info["who"] = player["name"]
    if not generate_gquest(player["name"]):
        # end_gquest already refunded via the cost/who bookkeeping
        chprintln(player, "Failed to start Gquest.")


def gq_kill_check(player, victim):
    """Credit a gquest target kill (cf. 1stMud group_gain gquest hook in fight.c:2143)."""
    if (gquest_info["running"] != GQUEST_RUNNING or not gquest_info["joined"]
            or not victim.get("is_npc")):
        return
    vnum = victim.get("tpl")
    pmobs = gquest_info["pmobs"]
    if vnum not in pmobs:
        return
    pmobs[pmobs.index(vnum)] = -1
    # [PRIMESUD] "that that mob" typo fixed
    chprintln(player, "Congratulations, that mob was part of your global quest!")
    line = "You receive an extra 3 Quest Points"
    player["quest_points"] = player.get("quest_points", 0) + 3
    if chance(max(5, min(gquest_info["mob_count"], 95))):
        line += " and a Trivia Point!"
        player["trivia"] = player.get("trivia", 0) + 1
    else:
        line += "."
    chprintln(player, line)


def gquest_update():
    """Tick the gquest state machine (cf. 1stMud gquest_update in update.c pulse_point).

    [PRIMESUD] Timers count world ticks; durations are balanced in real
    minutes like 1stMud's 60s pulse_point, so per-minute messages fire on
    whole-minute boundaries (on_minute) and display via ticks_to_mins.
    """
    player = world.chars.get(1)
    running = gquest_info["running"]

    if running == GQUEST_OFF:
        if gquest_info["timer"] > 0:
            gquest_info["timer"] -= 1
            if gquest_info["timer"] == 0:
                auto_gquest()
            # [PRIMESUD] countdown announcements: every 20 real minutes,
            # then at the 5- and 1-minute marks
            elif player is not None and on_minute(gquest_info["timer"]):
                mins = ticks_to_mins(gquest_info["timer"])
                if mins % 20 == 0 or mins in (1, 5):
                    chprintln(player,
                              "{WA global quest will begin in about "
                              + _intstr(mins, "minute") + ".{x")
    elif running == GQUEST_RUNNING:
        # [PRIMESUD] 1stMud ends the quest here if no players remain; kept
        # running so the (single) player can join or rejoin until time runs
        # out.
        if gquest_info["timer"] == 0:
            end_gquest()
            if player is not None:
                chprintln(player,
                          "Time has run out on the Global Quest, next quest will start in "
                          + _intstr(ticks_to_mins(gquest_info["timer"]), "minute") + ".")
            return
        if (player is not None and on_minute(gquest_info["timer"])
                and ticks_to_mins(gquest_info["timer"]) in (1, 2, 3, 4, 5, 10, 15)):
            chprintln(player, _intstr(ticks_to_mins(gquest_info["timer"]), "minute")
                      + " remaining in the global quest.")
        gquest_info["timer"] -= 1


def _target_lines(player, vnums):
    """Print the numbered target list (cf. 1stMud do_gquest info/check loops)."""
    count = 0
    for vnum in vnums:
        if vnum < 0:
            continue
        tpl = MOB_DEFS.get(vnum)
        if tpl is None:
            continue
        count += 1
        tag = world._vnum_to_tag(vnum)
        adef = quest_area_def(tag) if tag else None
        area_name = adef.get("name", tag) if adef else "?"
        # [PRIMESUD] columns narrowed/truncated to fit the calculator screen
        chprintln(player, pad_left(num_str(count), 2) + ") ["
                  + pad_right(area_name[:16], 16) + "] "
                  + pad_right(tpl["short_descr"][:25], 25) + " (level "
                  + pad_left(num_str(tpl.get("level", 1)), 3) + ")")


def do_gquest(player, args):
    """Global quest command (cf. 1stMud do_gquest in gquest.c).

    [PRIMESUD] 'progress' (other players) and 'hist' (note-board history)
    skipped; immortal 'end'/'next' skipped.
    """
    arg1 = args[0].lower() if args else ""

    if arg1 == "":
        chprintln(player, "Syntax: gquest join     - join a global quest")
        chprintln(player, "        gquest quit     - quit the global quest")
        chprintln(player, "        gquest info     - show global quest info")
        chprintln(player, "        gquest time     - show global quest time")
        chprintln(player, "        gquest check    - show what targets you have left")
        chprintln(player, "        gquest complete - completes the current quest")
        chprintln(player, "        gquest start    - starts a gquest")
        return

    if _prefix(arg1, "start"):
        start_gquest(player, args[1:])
        return

    if gquest_info["running"] == GQUEST_OFF:
        chprintln(player,
                  "There is no global quest running.  The next Gquest will start in "
                  + _intstr(ticks_to_mins(gquest_info["timer"]), "minute") + ".")
        return

    if _prefix(arg1, "join"):
        if player.get("fighting") is not None:
            chprintln(player, "You're a little busy right now.")
            return
        if is_quester(player):
            chprintln(player, "Why don't you finish your other quest first.")
            return
        if gquest_info["joined"]:
            # [PRIMESUD] "Your allready" typos fixed
            chprintln(player, "You're already in the global quest.")
            return
        if (gquest_info["minlevel"] > player["level"]
                or gquest_info["maxlevel"] < player["level"]):
            chprintln(player, "This gquest is not in your level range.")
            return
        gquest_info["joined"] = True
        gquest_info["pmobs"] = list(gquest_info["mobs"])
        chprintln(player,
                  "Your global quest flag is now on. Use 'gquest info' to see the quest(s).")
        return

    if _prefix(arg1, "quit"):
        if not gquest_info["joined"]:
            # [PRIMESUD] "Your not" typo fixed
            chprintln(player, "You're not in a global quest.")
            return
        gquest_info["joined"] = False
        gquest_info["pmobs"] = []
        chprintln(player,
                  "Your global quest flag is now off. Sorry you couldn't complete it.")
        return

    if _prefix(arg1, "info"):
        chprintln(player, "[ GLOBAL QUEST INFO ]")
        chprintln(player, "Started by  : " + (gquest_info["who"] or "Unknown"))
        chprintln(player, "Levels      : " + str(gquest_info["minlevel"])
                  + " - " + str(gquest_info["maxlevel"]))
        chprintln(player, "Status      : Running for "
                  + _intstr(ticks_to_mins(gquest_info["timer"]), "minute") + ".")
        chprintln(player, "[ Quest Rewards ]")
        chprintln(player, "Qp Reward   : " + str(gquest_info["qpoints"]))
        chprintln(player, "Gold Reward : " + str(gquest_info["gold"]))
        chprintln(player, "[ Quest Targets ]")
        _target_lines(player, gquest_info["mobs"])
        return

    if _prefix(arg1, "time"):
        chprintln(player, "The Global Quest is Running for "
                  + _intstr(ticks_to_mins(gquest_info["timer"]), "minute") + ".")
        return

    if _prefix(arg1, "check"):
        if not gquest_info["joined"]:
            chprintln(player, "You aren't on a global quest.")
            return
        chprintln(player, "[ You have " + str(gquest_info["mob_count"] - _count_killed())
                  + " of " + str(gquest_info["mob_count"]) + " mobs left ]")
        _target_lines(player, gquest_info["pmobs"])
        return

    if _prefix(arg1, "complete"):
        if not gquest_info["joined"]:
            # [PRIMESUD] "Your not" typo fixed
            chprintln(player, "You're not in a global quest.")
            return
        killed = _count_killed()
        if killed != gquest_info["mob_count"]:
            # [PRIMESUD] 1stMud intstr(..., "minute") slip fixed to "mob"
            chprintln(player,
                      "You haven't finished just yet, theres still "
                      + _intstr(gquest_info["mob_count"] - killed, "mob") + " to kill.")
            return
        chprintln(player, "YES! You have completed the global quest.")
        # 1stMud: post_gquest note-board history -- [PRIMESUD] skipped
        player["quest_points"] = player.get("quest_points", 0) + gquest_info["qpoints"]
        player["gold"] += gquest_info["gold"]
        chprintln(player, "You receive " + str(gquest_info["gold"]) + " gold and "
                  + str(gquest_info["qpoints"]) + " quest points.")
        end_gquest()
        chprintln(player,
                  "You have completed the global quest, next gquest in "
                  + _intstr(ticks_to_mins(gquest_info["timer"]), "minute") + ".")
        world.save_pending = True
        return

    do_gquest(player, [])


# -- Persistence [PRIMESUD] ----------------------------------------------------

def gq_save_lines():
    """Serialise gquest state to save lines (str+concat per PRIME_FIRMWARE_BUGS)."""
    gq = gquest_info
    line = ("g.gquest=" + sstr(gq["running"]) + "|" + sstr(gq["timer"])
            + "|" + sstr(gq["mob_count"]) + "|" + sstr(gq["minlevel"])
            + "|" + sstr(gq["maxlevel"]) + "|" + sstr(gq["qpoints"])
            + "|" + sstr(gq["gold"]) + "|" + sstr(gq["cost"])
            + "|" + ("1" if gq["joined"] else "0") + "|" + sstr(gq["who"]))
    mobs = ""
    for v in gq["mobs"]:
        mobs = mobs + ("," if mobs else "") + sstr(v)
    pmobs = ""
    for v in gq["pmobs"]:
        pmobs = pmobs + ("," if pmobs else "") + sstr(v)
    return [line, "g.gqmobs=" + mobs, "g.gqpmobs=" + pmobs]


def gq_load_line(key, val):
    """Restore one gquest save line; True if the key was consumed."""
    if key == "g.gquest":
        parts = val.split("|")
        while len(parts) < 10:
            parts.append("")
        gquest_info["running"] = int(parts[0] or 0)
        gquest_info["timer"] = int(parts[1] or 0)
        gquest_info["mob_count"] = int(parts[2] or 0)
        gquest_info["minlevel"] = int(parts[3] or 0)
        gquest_info["maxlevel"] = int(parts[4] or 0)
        gquest_info["qpoints"] = int(parts[5] or 0)
        gquest_info["gold"] = int(parts[6] or 0)
        gquest_info["cost"] = int(parts[7] or 0)
        gquest_info["joined"] = parts[8] == "1"
        gquest_info["who"] = parts[9]
        # [PRIMESUD] legacy save from before the join window was removed:
        # promote to running with a fresh run timer
        if gquest_info["running"] == GQUEST_WAITING:
            gquest_info["running"] = GQUEST_RUNNING
            gquest_info["timer"] = mins_to_ticks(5 * gquest_info["mob_count"])
        return True
    if key == "g.gqmobs":
        gquest_info["mobs"] = [int(v) for v in val.split(",") if v]
        return True
    if key == "g.gqpmobs":
        gquest_info["pmobs"] = [int(v) for v in val.split(",") if v]
        return True
    return False


def gq_reset():
    """Reset gquest state for a new game. [PRIMESUD]"""
    gquest_info["cost"] = 0   # never refund across games
    gquest_info["who"] = ""
    end_gquest()
    # Fresh games wait the fixed initial delay, not the random auto range
    gquest_info["timer"] = mins_to_ticks(GQUEST_INITIAL_DELAY)
