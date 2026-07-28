"""Integer fling step shared by graphical scrollback and its tests."""


def advance_fling(depth, accum_px, velocity, dt_ms, step_px, step_rows,
                  hist_count, min_velocity, decay_num, decay_den):
    if velocity == 0 or dt_ms <= 0:
        return depth, accum_px, velocity, False

    accum_px += velocity * dt_ms // 1000
    moved = False
    while accum_px >= step_px:
        new_depth = min(depth + step_rows, hist_count)
        if new_depth == depth:
            accum_px = 0
            break
        depth = new_depth
        accum_px -= step_px
        moved = True
    while accum_px <= -step_px:
        new_depth = max(depth - step_rows, 0)
        if new_depth == depth:
            accum_px = 0
            break
        depth = new_depth
        accum_px += step_px
        moved = True

    velocity = velocity * decay_num // decay_den
    if -min_velocity < velocity < min_velocity:
        velocity = 0
    if (velocity == 0 or (depth == 0 and accum_px < 0)
            or (depth == hist_count and accum_px > 0)):
        accum_px = 0
    return depth, accum_px, velocity, moved
