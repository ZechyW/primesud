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
    "  |  N/S exit",
    "  -  E/W exit",
]


def _map_exits(rooms, vnum, grid, gx, gy, depth):
    room = rooms.get(vnum)
    if room is None:
        return
    grid[gy][gx] = 'o'
    if depth >= MAP_MAX_DEPTH:
        return
    for direction, dest_vnum in room["exits"].items():
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
            _map_exits(rooms, dest_vnum, grid, rx, ry, depth + 1)


def _build_grid(player, rooms):
    grid = [[' '] * GW for _ in range(GH)]
    _map_exits(rooms, player["room"], grid, MAP_HALF_W, MAP_HALF_H, 0)
    grid[MAP_HALF_H][MAP_HALF_W] = 'X'
    return grid


def build_compact_lines(player, rooms):
    """Bordered compact map: (_CH+2) rows × COMPACT_W cols."""
    grid = _build_grid(player, rooms)
    cx, cy = MAP_HALF_W, MAP_HALF_H
    r_w = MAP_HALF_W
    r_h = MAP_HALF_H - 2
    border = '+' + '-' * _CW + '+'
    lines = [border]
    for y in range(cy - r_h, cy + r_h + 1):
        lines.append('|' + ''.join(grid[y][cx - r_w:cx + r_w + 1]) + '|')
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
