from config import MAP_HALF_W, MAP_HALF_H, MAP_MAX_DEPTH

GW = MAP_HALF_W * 2 + 1
GH = MAP_HALF_H * 2 + 1

# Compact shows full grid width, clips (MAP_HALF_H - 2) rows from top/bottom
_CW = MAP_HALF_W * 2 + 1   # compact content width  = GW (13 with default config)
_CH = MAP_HALF_H * 2 - 3   # compact content height (5 with default config)
COMPACT_W = _CW + 2         # including | borders    (15 with default config)

_DIR_DELTA = {
    "n": (0, -1),
    "s": (0,  1),
    "e": ( 1, 0),
    "w": (-1, 0),
}
_EXIT_CHAR = {"n": "|", "s": "|", "e": "-", "w": "-"}

_FULL_LEGEND = [
    "  X  You are here",
    "  o  Room",
    "  U  Room (up exit)",
    "  D  Room (down exit)",
    "  B  Room (up+down)",
    "  |  N/S exit",
    "  -  E/W exit",
]


def _room_char(room):
    # [PRIMESUD] 1stMud only shows U/D/B for explored rooms; we show them unconditionally.
    if room is None:
        return 'o'
    has_u = 'u' in room['exits']
    has_d = 'd' in room['exits']
    if has_u and has_d:
        return 'B'
    if has_u:
        return 'U'
    if has_d:
        return 'D'
    return 'o'


def _map_exits(rooms, start_vnum, grid, start_gx, start_gy):
    grid[start_gy][start_gx] = _room_char(rooms.get(start_vnum))
    queue = [(start_vnum, start_gx, start_gy, 0)]
    head = 0
    while head < len(queue):
        vnum, gx, gy, depth = queue[head]
        head += 1
        if depth >= MAP_MAX_DEPTH:
            continue
        room = rooms.get(vnum)
        if room is None:
            continue
        for direction, exit_val in room["exits"].items():
            if isinstance(exit_val, dict) and exit_val.get("closed"):
                continue
            dest_vnum = exit_val["to"] if isinstance(exit_val, dict) else exit_val
            delta = _DIR_DELTA.get(direction)
            if delta is None:
                continue
            dx, dy = delta
            ex, ey = gx + dx, gy + dy
            rx, ry = gx + 2 * dx, gy + 2 * dy
            if not (0 <= ex < GW and 0 <= ey < GH):
                continue
            if not (0 <= rx < GW and 0 <= ry < GH):
                continue
            grid[ey][ex] = _EXIT_CHAR[direction]
            if grid[ry][rx] == ' ':
                grid[ry][rx] = _room_char(rooms.get(dest_vnum))
                queue.append((dest_vnum, rx, ry, depth + 1))


def _build_grid(player, rooms):
    grid = [[' '] * GW for _ in range(GH)]
    _map_exits(rooms, player["room"], grid, MAP_HALF_W, MAP_HALF_H)
    grid[MAP_HALF_H][MAP_HALF_W] = 'X'
    return grid


def build_compact_lines(player, rooms):
    """Bordered compact map: (_CH+2) rows × COMPACT_W cols."""
    grid = _build_grid(player, rooms)
    cx, cy = MAP_HALF_W, MAP_HALF_H
    r_w = MAP_HALF_W
    r_h = MAP_HALF_H - 2
    border = "{R" + '+' + '-' * _CW + '+' + "{x"
    lines = [border]
    for y in range(cy - r_h, cy + r_h + 1):
        lines.append('{R|{x' + ''.join(grid[y][cx - r_w:cx + r_w + 1]) + '{R|{x')
    lines.append(border)
    return lines


def build_full_lines(player, rooms):
    """Bordered full map with legend: (GH+2) rows × (GW+2) cols."""
    grid = _build_grid(player, rooms)
    border = '+' + '-' * GW + '+'
    lines = [border]
    for row in grid:
        lines.append('|' + ''.join(row) + '|')
    lines.append(border)
    for i, entry in enumerate(_FULL_LEGEND):
        if i < len(lines):
            lines[i] = lines[i] + entry
    return lines
