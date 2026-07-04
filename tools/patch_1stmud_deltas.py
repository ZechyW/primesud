#!/usr/bin/env python3
"""Patch 1stMud-only deltas into generated area .dat files.

Data that exists in 1stMud but not in the QuickMUD .are files the
converter reads: cross-area exits, and mob act flags (1stMud gives its
midgaard guildmasters ACT_TRAIN/ACT_GAIN). Run after
are_to_primesud_quickmud.py conversion (regen_areas.sh does).

All patches are idempotent; safe to re-run on already-patched .dats.

Usage:
    python patch_1stmud_deltas.py
"""

import re
import sys
from pathlib import Path

# {area_name: {room_vnum: {direction: target_vnum}}}
CROSS_AREA_EXITS = {
    "midgaard": {
        3001: {"e": 200, "w": 201},   # quest area (1stMud-only)
        3054: {"d": 3},                # limbo (1stMud-only)
        3303: {"s": 202},              # quest area trivia shop (1stMud-only)
    },
}

# {area_name: {mob_vnum: (flag, ...)}} -- added to the mob's act_flags.
# 3020/3023 (mage/warrior GM): train + gain per 1stMud midgaard.are.
# 3021/3022 (cleric/thief GM): gain is [PRIMESUD] -- upstream has neither,
# but every guild must be gain/remort-capable single-area (CLASS_PLAN.md
# Phase D).
MOB_ACT_FLAGS = {
    "midgaard": {
        3020: ("train", "gain"),
        3021: ("gain",),
        3022: ("gain",),
        3023: ("train", "gain"),
    },
}

# {area_name: {room_vnum: (class_idx, ...)}} -- written as a "guild" field
# on the room (cf. 1stMud midgaard.are G <class> fields; single class per
# room upstream). Class indices per classes.py CLASS_TABLE: 0 mage,
# 1 cleric, 2 thief, 3 warrior, 4 paladin, 5 ranger. Paladin sharing the
# cleric rooms and ranger the warrior rooms is [PRIMESUD] -- no
# paladin/ranger guilds exist in midgaard (CLASS_PLAN.md).
ROOM_GUILDS = {
    "midgaard": {
        3018: (0,),     3019: (0,),      # Mage's Bar / Laboratory
        3002: (1, 4),   3003: (1, 4),    # Cleric's Inner Sanctum / Bar
        3028: (2,),     3029: (2,),      # Thieves Bar / Secret Yard
        3022: (3, 5),   3023: (3, 5),    # Bar of Swordsmen / Tournament Yard
    },
}

# {(src_area, dst_area): (reset_line, ...)} -- resets in src whose target
# room lives in dst. Left in src they force dst (and its own cross-area
# pulls) to load the moment src loads; moved to dst they run when dst
# actually loads. [PRIMESUD] defer-load optimization; same world state.
MOVE_RESETS = {
    ("midgaard", "shire"): (
        '    ("O", 3200, 1116),',   # the juke, The Ivy Bush
        '    ("O", 3200, 1144),',   # the juke, The Green Dragon
    ),
    ("midgaard", "immort"): (
        '    ("O", 3135, 1200),',   # a fountain, The Chat Room
        '    ("O", 3200, 1200),',   # the juke, The Chat Room
    ),
}

# {area: (reset_line, ...)} -- resets referencing another area's defs from
# a local room (nothing to move). Dropped to defer the foreign load.
DROP_RESETS = {
    "limbo": (
        # Morgue sarcophagus (obj 3415, chapel-owned): would pull all of
        # chapel the moment limbo loads. Limbo is preloaded at session start
        # for corpse storage; dropping this keeps that preload self-contained.
        '    ("O", 3415, 3),',
    ),
    "midgaard": (
        # Kate's Diner pipeweed bread: shire item def would pull shire (and
        # via shire's shiriff gear, ofcol2) at game start; still sold in shire
        '    ("G", 1103, -1),',
    ),
}

DIR_ORDER = "neswud"


def exit_sort_key(line):
    m = re.match(r'\s+"([neswud])":', line)
    return DIR_ORDER.index(m.group(1)) if m else 99


def patch_area(area_name, filepath):
    exits_to_add = CROSS_AREA_EXITS.get(area_name)
    if not exits_to_add:
        return False

    text = Path(filepath).read_text(encoding="utf-8")
    lines = text.split("\n")

    rooms_section = None
    for idx in range(len(lines)):
        if lines[idx].startswith("ROOMS = {"):
            rooms_section = idx
            break

    modified = False
    for vnum, new_exits in sorted(exits_to_add.items()):
        room_pattern = f"    {vnum}: {{"
        room_start = None
        for idx in range(rooms_section or 0, len(lines)):
            if lines[idx].startswith(room_pattern):
                room_start = idx
                break
        if room_start is None:
            print(f"  WARNING: room block for {vnum} not found", file=sys.stderr)
            continue

        exits_start = None
        for idx in range(room_start, min(room_start + 50, len(lines))):
            if '"exits": {' in lines[idx]:
                exits_start = idx
                break
        if exits_start is None:
            print(f"  WARNING: exits block not found for {vnum}", file=sys.stderr)
            continue

        exits_end = None
        for idx in range(exits_start + 1, min(exits_start + 50, len(lines))):
            if lines[idx].strip() == "},":
                exits_end = idx
                break
        if exits_end is None:
            print(f"  WARNING: exits end not found for {vnum}", file=sys.stderr)
            continue

        exit_lines = lines[exits_start + 1:exits_end]
        added = []
        for d in new_exits:
            target = new_exits[d]
            new_line = (f'            "{d}": {target},'
                        f"  # [PRIMESUD] cross-area (1stMud)")
            if new_line in exit_lines:   # already patched -- idempotent re-run
                continue
            exit_lines.append(new_line)
            added.append(d)
        if not added:
            continue
        exit_lines.sort(key=exit_sort_key)

        lines[exits_start + 1:exits_end] = exit_lines
        modified = True
        dirs = ", ".join(sorted(added, key=DIR_ORDER.index))
        print(f"  {vnum}: +{dirs}", file=sys.stderr)

    if modified:
        Path(filepath).write_text("\n".join(lines), encoding="utf-8")
    return modified


def patch_mob_flags(area_name, filepath):
    flags_to_add = MOB_ACT_FLAGS.get(area_name)
    if not flags_to_add:
        return False

    text = Path(filepath).read_text(encoding="utf-8")
    lines = text.split("\n")

    mob_section = end_section = None
    for idx in range(len(lines)):
        if lines[idx].startswith("MOBILES = {"):
            mob_section = idx
        elif mob_section is not None and re.match(r"^[A-Z_]+ = ", lines[idx]):
            end_section = idx
            break

    modified = False
    for vnum, flags in sorted(flags_to_add.items()):
        mob_pattern = f"    {vnum}: {{"
        act_idx = None
        for idx in range(mob_section or 0, end_section or len(lines)):
            if lines[idx].startswith(mob_pattern):
                for j in range(idx, min(idx + 30, len(lines))):
                    if '"act_flags": {' in lines[j]:
                        act_idx = j
                        break
                break
        if act_idx is None:
            print(f"  WARNING: act_flags for mob {vnum} not found", file=sys.stderr)
            continue

        line = lines[act_idx]
        prefix, suffix = line.rsplit("}", 1)
        added = [f for f in flags if f'"{f}"' not in prefix]
        if not added:
            continue
        lines[act_idx] = (prefix
                          + "".join(f', "{f}": True' for f in added)
                          + "}" + suffix
                          + "  # [PRIMESUD] +" + "/".join(added)
                          + " (patch_1stmud_deltas)")
        modified = True
        print(f"  mob {vnum}: +{'/'.join(added)}", file=sys.stderr)

    if modified:
        Path(filepath).write_text("\n".join(lines), encoding="utf-8")
    return modified


def patch_room_guilds(area_name, filepath):
    guilds_to_add = ROOM_GUILDS.get(area_name)
    if not guilds_to_add:
        return False

    text = Path(filepath).read_text(encoding="utf-8")
    lines = text.split("\n")

    rooms_section = None
    for idx in range(len(lines)):
        if lines[idx].startswith("ROOMS = {"):
            rooms_section = idx
            break

    modified = False
    for vnum, classes in sorted(guilds_to_add.items()):
        room_pattern = f"    {vnum}: {{"
        room_start = None
        for idx in range(rooms_section or 0, len(lines)):
            if lines[idx].startswith(room_pattern):
                room_start = idx
                break
        if room_start is None:
            print(f"  WARNING: room block for {vnum} not found", file=sys.stderr)
            continue
        if '"guild"' in lines[room_start + 1]:
            continue  # already patched
        tup = "(" + ", ".join(str(c) for c in classes) + ("," if len(classes) == 1 else "") + ")"
        lines.insert(room_start + 1,
                     f'        "guild": {tup},'
                     "  # [PRIMESUD] cf. 1stMud G field (patch_1stmud_deltas)")
        modified = True
        print(f"  room {vnum}: guild {tup}", file=sys.stderr)

    if modified:
        Path(filepath).write_text("\n".join(lines), encoding="utf-8")
    return modified


def patch_move_resets(base):
    """Move MOVE_RESETS lines from src RESETS to dst RESETS. Idempotent."""
    for (src, dst), reset_lines in sorted(MOVE_RESETS.items()):
        src_path = base / f"area_{src}.dat"
        dst_path = base / f"area_{dst}.dat"
        if not (src_path.exists() and dst_path.exists()):
            print(f"  SKIP: {src} -> {dst} (file missing)", file=sys.stderr)
            continue
        src_lines = src_path.read_text(encoding="utf-8").split("\n")
        moved = []
        missing = []
        for rl in reset_lines:
            if rl in src_lines:
                src_lines.remove(rl)
                moved.append(rl)
            else:
                missing.append(rl)
        if missing:
            # Not in src: must already sit in dst with its moved-marker;
            # otherwise the converter's emission format drifted and the
            # move silently stopped applying.
            dst_text = dst_path.read_text(encoding="utf-8")
            for rl in missing:
                marker = rl + f"  # [PRIMESUD] moved from {src} (defer cross-area load)"
                if marker not in dst_text:
                    print(f"  WARNING: {src} -> {dst}: move pattern not found: "
                          f"{rl.strip()} (emission format drift?)",
                          file=sys.stderr)
        if not moved:
            continue  # already moved
        src_path.write_text("\n".join(src_lines), encoding="utf-8")

        dst_lines = dst_path.read_text(encoding="utf-8").split("\n")
        closing = None
        in_resets = False
        for idx in range(len(dst_lines)):
            if dst_lines[idx].startswith("RESETS = ("):
                in_resets = True
            elif in_resets and dst_lines[idx] == ")":
                closing = idx
                break
        if closing is None:
            print(f"  WARNING: RESETS end not found in {dst}", file=sys.stderr)
            continue
        dst_lines[closing:closing] = [
            rl + f"  # [PRIMESUD] moved from {src} (defer cross-area load)"
            for rl in moved
        ]
        dst_path.write_text("\n".join(dst_lines), encoding="utf-8")
        print(f"  {src} -> {dst}: {len(moved)} reset(s) moved", file=sys.stderr)


def patch_drop_resets(base):
    """Comment out DROP_RESETS lines in place. Idempotent."""
    for area_name, reset_lines in sorted(DROP_RESETS.items()):
        filepath = base / f"area_{area_name}.dat"
        if not filepath.exists():
            print(f"  SKIP: {filepath} not found", file=sys.stderr)
            continue
        lines = filepath.read_text(encoding="utf-8").split("\n")
        dropped = 0
        for rl in reset_lines:
            if rl in lines:
                idx = lines.index(rl)
                lines[idx] = ("    # [PRIMESUD] dropped " + rl.strip().rstrip(",")
                              + " (defer cross-area load)")
                dropped += 1
            else:
                # Pattern must match either the raw line or its already-
                # dropped marker; anything else means the converter's
                # emission format drifted and the drop silently stopped
                # applying (caught the hard way when E/G resets gained a
                # limit field).
                marker = ("    # [PRIMESUD] dropped " + rl.strip().rstrip(",")
                          + " (defer cross-area load)")
                if marker not in lines:
                    print(f"  WARNING: {area_name}: drop pattern not found: "
                          f"{rl.strip()} (emission format drift?)",
                          file=sys.stderr)
        if dropped:
            filepath.write_text("\n".join(lines), encoding="utf-8")
            print(f"  {area_name}: {dropped} reset(s) dropped", file=sys.stderr)


if __name__ == "__main__":
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__.strip())
        sys.exit(0)
    base = Path(__file__).resolve().parent.parent / "primesud.hpappdir"
    # All patches are idempotent: safe to re-run on already-patched .dats.
    for area_name in sorted(set(CROSS_AREA_EXITS) | set(MOB_ACT_FLAGS)
                            | set(ROOM_GUILDS)):
        filepath = base / f"area_{area_name}.dat"
        if filepath.exists():
            print(f"==> {area_name}", file=sys.stderr)
            patch_area(area_name, filepath)
            patch_mob_flags(area_name, filepath)
            patch_room_guilds(area_name, filepath)
        else:
            print(f"  SKIP: {filepath} not found", file=sys.stderr)
    print("==> reset moves/drops", file=sys.stderr)
    patch_move_resets(base)
    patch_drop_resets(base)
