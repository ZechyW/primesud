"""Generate AREA_BUILDERS and _AREA_ADJ static tables in src/world.py.

Cross-area room-exit adjacency and area builder names, computed offline
from the area_*.txt data files so do_areas/do_run can eventually consult
them without loading area files at runtime. Re-run after any area data
changes:

    python tools/gen_area_adj.py

Idempotent: running twice with unchanged area data produces byte-identical
output the second time.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPDIR = os.path.join(ROOT, "src")
sys.path.insert(0, APPDIR)
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import world

WORLD_PY = os.path.join(APPDIR, "world.py")
BEGIN = "# -- BEGIN GENERATED: tools/gen_area_adj.py (do not hand-edit) --"
END = "# -- END GENERATED --"


def extract_builder(credits):
    """Extract builder name from area credits string.

    Mirrors info._extract_builder (cf. 1stMud convert_area_credits in
    db2.c) so generated data matches what `areas` would show live.
    """
    idx = credits.find("} ")
    if idx >= 0:
        parts = credits[idx + 2:].split()
        if parts:
            return parts[0]
    return credits[:7] if credits else ""


def load_area_ns(fname):
    path = os.path.join(APPDIR, fname)
    ns = {}
    with open(path) as f:
        exec(f.read(), ns)
    return ns


def format_dict_block(name, items, value_fmt):
    """Render `name = {...}` with keys aligned like the hand-written tables.

    Args:
        name (str): Dict variable name.
        items (list): [(tag, value), ...] in output order.
        value_fmt (callable): value -> formatted RHS string (no trailing comma).
    """
    labels = ['"%s":' % tag for tag, _ in items]
    width = max((len(l) for l in labels), default=0) + 1
    lines = [name + " = {"]
    for (tag, value), label in zip(items, labels):
        lines.append("    " + label.ljust(width) + value_fmt(value) + ",")
    lines.append("}")
    return lines


def main():
    area_files = list(world._AREA_FILES)
    tags = [tag for _fname, tag, _name, _lo, _hi in area_files]
    ranges = [(lo, hi, tag) for _fname, tag, _name, lo, hi in area_files]

    def vnum_to_tag(vnum):
        for lo, hi, tag in ranges:
            if lo <= vnum <= hi:
                return tag
        return None

    builders = {}
    lvl_comments = {}
    adjacency = dict((tag, set()) for tag in tags)
    mismatches = []
    blind_exit_count = 0
    unclaimed_exits = []  # (tag, room_vnum, dir, target_vnum): points outside
    # every registered area's vnum range. Verified against reference/quickmud
    # .are files (2026-07-08): every occurrence in stock data targets a
    # 1stMud area that has not been converted to a PrimeSUD area_*.txt yet
    # (e.g. valley.are, hood.are, midennir.are) -- not a data error. Treated
    # like a blind exit (no adjacency edge) rather than a hard failure so
    # the tool still runs on real stock data; reported below for review.

    for fname, tag, _name, _lo, _hi in area_files:
        ns = load_area_ns(fname)
        area = ns["AREA"]

        file_levels = tuple(area["levels"])
        world_levels = world.AREA_LEVELS.get(tag)
        if world_levels is None or tuple(world_levels) != file_levels:
            mismatches.append((tag, world_levels, file_levels))

        builders[tag] = extract_builder(area.get("credits", ""))
        if area.get("lvl_comment"):
            lvl_comments[tag] = area["lvl_comment"]

        for rvnum, room in ns["ROOMS"].items():
            for _d, ev in room.get("exits", {}).items():
                if ev is None:
                    blind_exit_count += 1
                    continue
                if isinstance(ev, dict):
                    to = ev.get("to")
                else:
                    to = ev
                if to is None:
                    blind_exit_count += 1
                    continue
                dest_tag = vnum_to_tag(to)
                if dest_tag is None:
                    unclaimed_exits.append((tag, rvnum, _d, to))
                    continue
                if dest_tag != tag:
                    adjacency[tag].add(dest_tag)

    if mismatches:
        sys.stderr.write(
            "AREA_LEVELS mismatch(es) found (reported only, NOT auto-fixed -- "
            "adjacency/builder generation continues since it does not depend "
            "on AREA_LEVELS; resolve the desync by hand and re-run):\n")
        for tag, world_levels, file_levels in mismatches:
            sys.stderr.write(
                "  %s: world.py AREA_LEVELS=%r  file AREA['levels']=%r\n"
                % (tag, world_levels, file_levels))

    builder_items = [(tag, builders[tag]) for tag in tags]
    adj_items = [(tag, tuple(sorted(adjacency[tag]))) for tag in tags]

    comment_items = [(tag, lvl_comments[tag]) for tag in tags
                     if tag in lvl_comments]

    block_lines = [BEGIN]
    block_lines.append("# AREA_BUILDERS: {tag: builder name}, extracted from each area's credits")
    block_lines.append("# line (cf. info._extract_builder). AREA_LVL_COMMENTS: {tag: level")
    block_lines.append("# comment} for areas whose credits carry a non-numeric level token")
    block_lines.append('# ("All", "None"), shown verbatim in the do_areas level slot (cf.')
    block_lines.append("# 1stMud lvl_comment). AREA_ADJ: {tag: sorted tuple of neighbor tags")
    block_lines.append("# reachable via a room exit}, computed from ROOMS exits. Lets")
    block_lines.append("# do_areas/do_run consult this data without loading area files at")
    block_lines.append("# runtime. Regenerate with: python tools/gen_area_adj.py")
    block_lines.append("# [PRIMESUD]")
    block_lines.extend(format_dict_block(
        "AREA_BUILDERS", builder_items, lambda v: '"%s"' % v))
    block_lines.append("")
    block_lines.extend(format_dict_block(
        "AREA_LVL_COMMENTS", comment_items, lambda v: '"%s"' % v))
    block_lines.append("")
    block_lines.extend(format_dict_block(
        "_AREA_ADJ", adj_items,
        lambda v: "(" + ", ".join('"%s"' % t for t in v) + (",)" if len(v) == 1 else ")")))
    block_lines.append(END)
    new_block = "\n".join(block_lines)

    # Universal-newlines mode (default): read translates any CRLF/CR/LF to
    # "\n"; write below translates "\n" back to the platform's native
    # line ending, matching world.py's existing on-disk convention instead
    # of forcing a mismatched LF-only block into a CRLF file.
    with open(WORLD_PY, "r") as f:
        original = f.read()

    if BEGIN not in original or END not in original:
        sys.stderr.write(
            "ERROR: sentinel lines not found in %s -- insert the "
            "'BEGIN GENERATED'/'END GENERATED' block manually first.\n" % WORLD_PY)
        return 1

    begin_idx = original.index(BEGIN)
    end_idx = original.index(END)
    if end_idx < begin_idx:
        sys.stderr.write("ERROR: END GENERATED sentinel precedes BEGIN sentinel.\n")
        return 1
    end_idx += len(END)

    updated = original[:begin_idx] + new_block + original[end_idx:]

    if updated == original:
        print("No changes: %s already up to date." % WORLD_PY)
    else:
        with open(WORLD_PY, "w") as f:
            f.write(updated)
        print("Updated %s" % WORLD_PY)

    # -- Report (stdout): salient facts for human review. --
    print()
    print("Areas: %d" % len(tags))
    print("Blind exits (\"to\": None): %d" % blind_exit_count)

    if unclaimed_exits:
        print()
        print("WARNING: %d exit(s) target vnums outside every registered area's "
              "range (excluded from adjacency -- verify these are unconverted "
              "1stMud areas, not typos):" % len(unclaimed_exits))
        for tag, rvnum, d, to in unclaimed_exits:
            print("  %-12s room %-6d %-2s -> vnum %d" % (tag, rvnum, d, to))

    print()
    print("AREA_BUILDERS:")
    for tag, builder in builder_items:
        print("  %-12s %s" % (tag, builder))

    if comment_items:
        print()
        print("AREA_LVL_COMMENTS:")
        for tag, comment in comment_items:
            print("  %-12s %s" % (tag, comment))

    print()
    print("_AREA_ADJ:")
    for tag, neighbors in adj_items:
        print("  %-12s %s" % (tag, ", ".join(neighbors) if neighbors else "(none)"))

    one_way = []
    for tag, neighbors in adj_items:
        for other in neighbors:
            if tag not in adjacency[other]:
                one_way.append((tag, other))
    if one_way:
        print()
        print("One-way area links (A -> B but not B -> A):")
        for a, b in one_way:
            print("  %s -> %s" % (a, b))

    reachable = set()
    frontier = ["midgaard"] if "midgaard" in adjacency else []
    reachable.update(frontier)
    while frontier:
        nxt = []
        for t in frontier:
            for n in adjacency.get(t, ()):
                if n not in reachable:
                    reachable.add(n)
                    nxt.append(n)
        frontier = nxt
    unreachable = [t for t in tags if t not in reachable]
    if unreachable:
        print()
        print("Areas unreachable from midgaard (directed, area-level BFS):")
        for t in unreachable:
            print("  %s" % t)

    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
