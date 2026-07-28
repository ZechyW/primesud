"""Room-neighborhood automap rendering helpers."""

from config import MAP_HALF_W, MAP_HALF_H, FULL_MAP_HALF_W, FULL_MAP_HALF_H, COMPACT_MAP_DEPTH, FULL_MAP_DEPTH, SECTOR_COLORS, SECTOR_SYMBOLS
from handler import room_is_dark

# Compact automap (shown side-by-side with room description)
GW = MAP_HALF_W * 2 + 1
GH = MAP_HALF_H * 2 + 1
_CW = MAP_HALF_W * 2 + 1   # compact content width  (11 with default config)
_CH = MAP_HALF_H * 2 - 3   # compact content height  (9 with default config)
COMPACT_W = _CW + 2         # including | borders    (13 with default config)

_DIR_DELTA = {
    "n": (0, -1),
    "s": (0,  1),
    "e": ( 1, 0),
    "w": (-1, 0),
}
_EXIT_CHAR        = {"n": "|", "s": "|", "e": "-", "w": "-"}
_EXIT_CHAR_CLOSED = {"n": "I", "s": "I", "e": "=", "w": "="}  # cf. map_chars_closed in automap.c

# cf. 1stMud show_map legend (automap.c); exactly 17 entries fit at
# FULL_MAP_HALF_H=8 (GH_FULL=17) -- build_full_lines drops any past that.
# Closed Doors omitted -- PrimeSUD skips closed exits in map traversal.
# [PRIMESUD] 1stMud's blank spacer row dropped to make room for '%'.
_FULL_LEGEND = [
    "   X   You are here",          # y=0
    "   o   Normal Rooms",          # y=1
    "   U   Room (up exit)",        # y=2
    "   D   Room (down exit)",      # y=3
    "   B   Room (up/down exit)",   # y=4
    "   |-  Exits",                 # y=5
    "   I=  Closed Doors",          # y=6
    "   *   Field/Forest",          # y=7
    "   !   Hills",                 # y=8
    "   @   Mountain",              # y=9
    "   =   Water",                 # y=10
    "   ~   Air",                   # y=11
    "   +   Desert",                # y=12
    "   :   Road/Path",             # y=13
    "   &   Swamp",                 # y=14
    "   #   Cave",                  # y=15
    "   %   Unloaded area",         # y=16  [PRIMESUD]
]


def _room_char(room):
    """Map character for a room (cf. 1stMud `show_map` in automap.c: room character selection)."""
    # [PRIMESUD] 1stMud only shows U/D/B for explored rooms; we show them unconditionally.
    if room is None:
        # [PRIMESUD] Room def not resident: an exit into an unloaded area (see
        # _map_exits' _data note) or a dangling vnum.  '%' is unused by
        # SECTOR_SYMBOLS, so it never masquerades as a real sector.
        return '%'
    has_u = 'u' in room['exits']
    has_d = 'd' in room['exits']
    if has_u and has_d:
        return 'B'
    if has_u:
        return 'U'
    if has_d:
        return 'D'
    return SECTOR_SYMBOLS.get(room.get('sector', 'inside'), 'o')


def _room_color(room):
    """Sector colour code for a room (cf. 1stMud `show_map` in automap.c: room color selection)."""
    if room is None:
        return ''
    return SECTOR_COLORS.get(room.get('sector', 'inside'), '')


def _map_exits(rooms, start_vnum, grid, colors, start_gx, start_gy, max_depth,
               infrared=False):
    """BFS exit traversal to populate map grid (cf. 1stMud `show_map` in automap.c: exit traversal).

    A dark destination (without observer infrared) is left blank and not
    traversed, standing in for 1stMud's can_see_room gate (can_see_room
    itself stays permissive elsewhere -- DESIGN.md "can_see_room").

    [PRIMESUD] `rooms` must be the resident room dict (world.ROOM_DEFS._data),
    never the LazyDict itself: a miss on the LazyDict lazy-loads the whole
    owning area, so mapping a room near a border would load the neighbour
    area on every look (and eviction would drop it again next step).  A
    missing dest still draws its corridor and a '%' cell -- the exit stays
    visible, and walking into it loads the area for real.
    """
    gh = len(grid)
    gw = len(grid[0]) if gh else 0
    start_room = rooms.get(start_vnum)
    grid[start_gy][start_gx] = _room_char(start_room)
    colors[start_gy][start_gx] = _room_color(start_room)
    queue = [(start_vnum, start_gx, start_gy, 0)]
    head = 0
    while head < len(queue):
        vnum, gx, gy, depth = queue[head]
        head += 1
        if depth >= max_depth:
            continue
        room = rooms.get(vnum)
        if room is None:
            continue
        for direction, exit_val in room["exits"].items():
            is_closed = isinstance(exit_val, dict) and exit_val.get("closed")
            dest_vnum = exit_val["to"] if isinstance(exit_val, dict) else exit_val
            if dest_vnum is None:  # blind exit: not traversable, not mapped
                continue
            delta = _DIR_DELTA.get(direction)
            if delta is None:
                continue
            dx, dy = delta
            ex, ey = gx + dx, gy + dy
            if not (0 <= ex < gw and 0 <= ey < gh):
                continue
            dest_room = rooms.get(dest_vnum)
            if is_closed:
                # Render door symbol but do not traverse (fixes 1stMud dead-code bug -- see FIXES.md)
                grid[ey][ex] = _EXIT_CHAR_CLOSED[direction]
                colors[ey][ex] = _room_color(dest_room)
                continue
            # cf. 1stMud show_map can_see_room gate (automap.c:167): skip a dark
            # destination entirely -- no corridor drawn, cell stays blank, not
            # traversed. dest_room is already loaded via .get() above.
            if dest_room is not None and room_is_dark(dest_vnum) and not infrared:
                continue
            rx, ry = gx + 2 * dx, gy + 2 * dy
            if not (0 <= rx < gw and 0 <= ry < gh):
                continue
            grid[ey][ex] = _EXIT_CHAR[direction]
            colors[ey][ex] = _room_color(dest_room)  # exit chars colored with dest sector (cf. 1stMud)
            if grid[ry][rx] == ' ':
                grid[ry][rx] = _room_char(dest_room)
                colors[ry][rx] = _room_color(dest_room)
                queue.append((dest_vnum, rx, ry, depth + 1))


def _build_grid(player, rooms, half_w, half_h, max_depth):
    """Allocate and populate a map grid centered on player (cf. 1stMud `show_map` in automap.c: grid construction)."""
    gw = half_w * 2 + 1
    gh = half_h * 2 + 1
    grid = [[' '] * gw for _ in range(gh)]
    colors = [[''] * gw for _ in range(gh)]
    infrared = bool(player.get("affected_by", {}).get("infrared"))
    _map_exits(rooms, player["room"], grid, colors, half_w, half_h, max_depth,
               infrared)
    grid[half_h][half_w] = 'X'
    # colors[half_h][half_w] already set by _map_exits to current room's sector color
    return grid, colors


def _colored_row(grid, colors, y, x0, x1, full=False):
    """Assemble one map row slice with per-cell sector colors (cf. 1stMud show_map in automap.c).

    Args:
        full: True for the standalone map command -- 2-wide cells with leading space and {D reset
              (cf. 1stMud show_map fSmall=false); False for compact side-by-side (fSmall=true).
    """
    row = ""
    for x in range(x0, x1):
        c = colors[y][x]
        ch = grid[y][x]
        if full:
            row += (" " + c + ch + "{D") if c else " {D."
        else:
            row += (c + ch) if c else ch
    return row


def build_compact_lines(player, rooms):
    """Bordered compact map: (_CH+2) rows x COMPACT_W cols (cf. 1stMud `show_map` in automap.c: compact output)."""
    grid, colors = _build_grid(player, rooms, MAP_HALF_W, MAP_HALF_H, COMPACT_MAP_DEPTH)
    cx, cy = MAP_HALF_W, MAP_HALF_H
    r_w = MAP_HALF_W
    r_h = MAP_HALF_H - 2
    border = "{R" + '+' + '-' * _CW + '+' + "{x"
    lines = [border]
    for y in range(cy - r_h, cy + r_h + 1):
        lines.append('{R|{x' + _colored_row(grid, colors, y, cx - r_w, cx + r_w + 1) + '{R|{x')
    lines.append(border)
    return lines


def build_full_lines(player, rooms):
    """Bordered full map with legend (cf. 1stMud show_map fSmall=false in automap.c).

    Grid: FULL_MAP_HALF_H*2+1 content rows x FULL_MAP_HALF_W*2+1 cells, 2 visible chars per cell.
    Legend attaches to content rows y=0..GH_FULL-1 (skipping both border lines).
    """
    half_w = FULL_MAP_HALF_W
    half_h = FULL_MAP_HALF_H
    gw_full = half_w * 2 + 1
    gh_full = half_h * 2 + 1
    grid, colors = _build_grid(player, rooms, half_w, half_h, FULL_MAP_DEPTH)
    # Border across the whole map, including length of longest legend line (26)
    border = '-' * (gw_full * 2 + 26)
    lines = [border]
    for y in range(gh_full):
        lines.append(_colored_row(grid, colors, y, 0, gw_full, full=True))
    lines.append(border)
    for i, entry in enumerate(_FULL_LEGEND):
        j = i + 1  # offset by 1 to skip top border; entries land on content rows
        if j < len(lines) - 1:  # don't attach to bottom border
            lines[j] = lines[j] + entry
    return lines
