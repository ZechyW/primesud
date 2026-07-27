"""PrimeSUD colour-aware terminal print/status wrappers."""

from tml_prime import tml_prime as tml
from config import (
    TERMINAL_COLS, FONT_GROB, COLOR_GROB, SCRATCH_GROB,
    DARK_MODE, BG_COLOR, TAB_SIZE, FONT,
    SCROLLBACK_SIZE, SCROLL_STEP, SWIPE_THRESHOLD, TOUCH_SCROLL_STEP,
    FLING_FRAME_MS, FLING_MIN_VELOCITY, FLING_DECAY_NUM, FLING_DECAY_DEN,
    FLING_SMOOTH_NUM,
)
from colors import (COLOR_CODE, ANSI_COLORS, _RESET_CODES, color_wrap_full,
                    color_parse_runs, strip_colors)
from hpprime import dimgrob, fillrect, getpix, grobh, grobw, pixon, strblit2
from util import pad_right


def _wrap_plain(text, width):
    """Plain-text word-wrap with no colour-code scanning."""
    lines = []
    while len(text) > width:
        i = text.rfind(' ', 0, width)
        if i <= 0:
            i = width - 1
        lines.append(text[:i])
        text = text[i:].lstrip(' ')
    lines.append(text)
    return lines


def install_color_print(tr):
    """Install PrimeSUD colour-code aware print wrappers on a tml instance. [PRIMESUD]"""
    font_w = grobw(FONT_GROB)
    font_h = grobh(FONT_GROB)
    dimgrob(COLOR_GROB, font_w, font_h, 0)
    strblit2(COLOR_GROB, 0, 0, font_w, font_h, FONT_GROB, 0, 0, font_w, font_h)
    _w_x = (ord('W') - 32) * tr.char_width + tr.char_width // 2
    font_fg = getpix(FONT_GROB, _w_x, tr.char_height // 2)
    fg_rows = [
        [x for x in range(font_w) if getpix(FONT_GROB, x, y) == font_fg]
        for y in range(font_h)
    ]
    current_fg = [None]

    def set_color(color):
        if color == current_fg[0]:
            return
        current_fg[0] = color
        _po = pixon
        for y, xs in enumerate(fg_rows):
            for x in xs:
                _po(FONT_GROB, x, y, color)

    def reset_color():
        if current_fg[0] is None:
            return
        current_fg[0] = None
        strblit2(FONT_GROB, 0, 0, font_w, font_h, COLOR_GROB, 0, 0, font_w, font_h)

    cols = TERMINAL_COLS
    # Closure-captured for faster lookup than globals in the hot print path.
    _CC = COLOR_CODE
    _ANSI = ANSI_COLORS
    _RST = _RESET_CODES
    _pxy = tr.print_xy
    _pch = tr._put_char
    # [PRIMESUD] int-keyed glyph x-offsets for the batch compose: bytes
    # iteration yields ints, so the per-char draw loop allocates nothing
    # (a small alloc costs ~0.5ms at full game heap on device --
    # BUILTINS.md sec. Text rendering performance).
    _bmap = {}
    for _ch, _ix in tr.char_map.items():
        _bmap[ord(_ch)] = _ix * tr.char_width

    def _group_piece(piece):
        """Split one physical colour-coded piece into per-colour segments. [PRIMESUD]

        Returns:
            (colour_order, groups): first-appearance colour order and
            {colour_or_None: [(x, seg), ...]} at visible x offsets.
        """
        x = 0
        current = None
        colour_order = []
        groups = {}
        parts = piece.split(_CC)
        seg = parts[0]
        if seg:
            colour_order.append(None)
            groups[None] = [(0, seg)]
            x = len(seg)
        skip = False
        for part in parts[1:]:
            if not part:
                # '{{' escape: literal '{'.
                if current not in groups:
                    colour_order.append(current)
                    groups[current] = []
                groups[current].append((x, _CC))
                x += 1
                skip = True
                continue
            if skip:
                skip = False
                seg = part
            else:
                code = part[0]
                seg = part[1:]
                if code in _ANSI:
                    current = _ANSI[code]
                elif code in _RST:
                    current = None
                else:
                    seg = _CC + part
            if seg:
                if current not in groups:
                    colour_order.append(current)
                    groups[current] = []
                groups[current].append((x, seg))
                x += len(seg)
        return colour_order, groups

    def _draw_run(s):
        """Draw s at the cursor with _put_char wrap semantics, one
        print_xy call per row instead of one draw per char. [PRIMESUD]"""
        while True:
            while tr.cursor_y >= tr.rows:
                tr._scroll_up()
            space = cols - tr.cursor_x
            if len(s) <= space:
                _pxy(tr.cursor_x, tr.cursor_y, s)
                tr.cursor_x += len(s)
                if tr.cursor_x >= cols:
                    tr.cursor_x = 0
                    tr.cursor_y += 1
                return
            _pxy(tr.cursor_x, tr.cursor_y, s[:space])
            tr.cursor_x = 0
            tr.cursor_y += 1
            s = s[space:]

    def print_lines(lines):
        """Render complete lines offscreen, then blit once. [PRIMESUD]

        Groups segments by colour (one font repaint per distinct colour),
        composes the whole batch into SCRATCH_GROB, and updates the screen
        with a single blit -- no visible char-by-char fill-in.
        """
        physical = []
        for text in lines:
            if _CC not in text:
                physical.extend(_wrap_plain(text, cols))
            elif (len(text) - 2 * text.count(_CC) <= cols
                    and '{{' not in text):
                physical.append(text)
            else:
                physical.extend(color_wrap_full(text, cols))
        if not physical:
            return

        # Keep batches to one screen.  Rendering any older prefix normally
        # lets rows which later scroll off enter the history ring unchanged.
        extra = len(physical) - tr.rows
        if extra > 0:
            for text in physical[:extra]:
                wrapped_print(text)
            physical = physical[extra:]

        # [PRIMESUD] fold the scroll into the compose: G0 is untouched
        # until the final blit, so the old screen stays visible during
        # the ~0.7ms/char glyph pass instead of scroll-blanked rows.
        # n1 = pending lazy scroll, n2 = overflow from this batch; when
        # n > 0 the batch always ends at the bottom row, so the compose
        # covers the whole text area.
        cy = tr.cursor_y
        n1 = cy - tr.rows + 1
        if n1 < 0:
            n1 = 0
        cy -= n1
        n2 = cy + len(physical) - tr.rows
        if n2 < 0:
            n2 = 0
        n = n1 + n2
        top = cy - n2

        row = top
        colour_order = []
        groups = {}
        for piece in physical:
            order_p, groups_p = _group_piece(piece)
            for colour in order_p:
                if colour not in groups:
                    colour_order.append(colour)
                    groups[colour] = []
                segs = groups[colour]
                for x, seg in groups_p[colour]:
                    segs.append((x, row, seg))
            row += 1

        # [PRIMESUD] offscreen compose: draw into a scratch GROB, blit once.
        # The screen updates atomically (BUILTINS.md sec. Text rendering
        # performance).  With a scroll folded in, the scratch holds the
        # whole text area: surviving G0 rows shifted up by n, batch below.
        cw = tr.char_width
        chh = tr.char_height
        base = 0 if n else top
        h = (row - base) * chh
        dimgrob(SCRATCH_GROB, tr.width, h, tr.back_color)
        _sb = strblit2
        if n:
            # Capture the scrolled-off rows into the history ring (reads
            # G0 only; matches tml_prime._scroll_up bookkeeping).
            # [PRIMESUD] cursor_y past rows (lazy scroll + trailing blank
            # lines, e.g. the interpret() echo at a full screen) makes n
            # exceed the rows G0 holds -- clamp every G0 read to the text
            # area or the separator/status band below it leaks into the
            # output; the excess rows are the pending blanks.
            hs = tr._hist_size
            if hs > 0:
                hg = tr._hist_grob
                hw = tr._hist_write
                for i in range(n):
                    hy = ((hw + i) % hs) * chh
                    if i < tr.rows:
                        _sb(hg, 0, hy, tr.width, chh,
                            0, 0, i * chh, tr.width, chh)
                    else:
                        fillrect(hg, 0, hy, tr.width, chh,
                                 tr.back_color, tr.back_color)
                tr._hist_write = (hw + n) % hs
                hc = tr._hist_count + n
                tr._hist_count = hc if hc < hs else hs
            avail = tr.rows - n
            if avail > top:
                avail = top
            if avail > 0:
                _sb(SCRATCH_GROB, 0, 0, tr.width, avail * chh,
                    0, 0, n * chh, tr.width, avail * chh)
        bget = _bmap.get
        for colour in colour_order:
            if colour is None:
                reset_color()
            else:
                set_color(colour)
            for x, y, seg in groups[colour]:
                px = x * cw
                py = (y - base) * chh
                for bch in seg.encode():
                    fx = bget(bch, -1)
                    if fx >= 0:
                        _sb(SCRATCH_GROB, px, py, cw, chh,
                            FONT_GROB, fx, 0, cw, chh)
                    px += cw
        _sb(0, 0, base * chh, tr.width, h, SCRATCH_GROB, 0, 0, tr.width, h)
        tr.cursor_x = 0
        tr.cursor_y = row

    def wrapped_print(*args, sep=' ', end='\n'):
        """Colour-aware print with word-wrap and per-run font recolouring. [PRIMESUD]"""
        # [PRIMESUD] a single list arg is a pre-split line batch, passed
        # through unjoined (join over %-formatted lines trips the device
        # heap bug, PRIME_STRING_FORMAT_BUG.md).
        if len(args) == 1 and type(args[0]) is list:
            if end == '\n' and tr.cursor_x == 0:
                print_lines(args[0])
            else:
                for line in args[0]:
                    wrapped_print(line)
            return
        text = sep.join(str(a) for a in args)
        if '\n' in text and end == '\n' and tr.cursor_x == 0:
            print_lines(text.split('\n'))
            return
        if '\n' in text:
            lines = text.split('\n')
            for idx, line in enumerate(lines):
                wrapped_print(line, end='\n' if idx < len(lines) - 1 else end)
            return
        if _CC not in text:
            # Fast path: skip color_wrap and all colour-code scanning.
            # [PRIMESUD] rows drawn via print_xy runs (alloc-free glyph
            # loop in tml_prime) instead of per-char _put_char.
            if current_fg[0] is not None:
                reset_color()
            lines = _wrap_plain(text, cols)
            n = len(lines)
            for idx, line in enumerate(lines):
                if line:
                    _draw_run(line)
                auto_wrapped = line and tr.cursor_x == 0
                if not auto_wrapped:
                    for c2 in (end if idx == n - 1 else '\n'):
                        _pch(c2)
            return
        # Colour-first rendering: split+group in one pass, then render one
        # set_color/reset_color per distinct colour.
        if len(text) - 2 * text.count(_CC) <= cols and '{{' not in text:
            pieces = (text,)
        else:
            pieces = color_wrap_full(text, cols)
        n = len(pieces)
        for idx, piece in enumerate(pieces):
            colour_order, groups = _group_piece(piece)
            if groups:
                # [PRIMESUD] lazy scroll: resolve any pending scroll before
                # drawing via print_xy (bypasses _put_char's check).
                while tr.cursor_y >= tr.rows:
                    tr._scroll_up()
            row = tr.cursor_y
            for colour in colour_order:
                if colour is None:
                    reset_color()
                else:
                    set_color(colour)
                for x_pos, seg in groups[colour]:
                    _pxy(x_pos, row, seg)
            is_last = idx == n - 1
            if not is_last:
                _pch('\n')
            elif end:
                for c in end:
                    _pch(c)

    tr.print = wrapped_print
    orig_set_status = tr.set_status
    _cpr = color_parse_runs
    _sc = strip_colors

    def wrapped_set_status(text):
        """Colour-aware status bar renderer with visible-width truncation. [PRIMESUD]"""
        length = tr.columns - 6
        if _CC not in text:
            if current_fg[0] is not None:
                reset_color()
            orig_set_status(text)
            return
        # Colour-aware: truncate to visible width, then render runs.
        plain = _sc(text)
        if len(plain) > length:
            # Truncate colour text to `length` visible chars.
            vis = 0
            trunc_i = 0
            n = len(text)
            while trunc_i < n and vis < length:
                if text[trunc_i] == _CC and trunc_i + 1 < n:
                    trunc_i += 2
                else:
                    vis += 1
                    trunc_i += 1
            text = text[:trunc_i]
            plain = plain[:length]
        row = tr.rows + 1
        runs = _cpr(text)
        x = 0
        for colour, seg in runs:
            if colour is None:
                reset_color()
            else:
                set_color(colour)
            _pxy(x, row, seg)
            x += len(seg)
        # Pad remaining with spaces in default colour.
        if x < length:
            reset_color()
            _pxy(x, row, ' ' * (length - x))
        tr.status_text = pad_right(plain, length)

    tr.set_status = wrapped_set_status


tr = None


def tprint(*args, **kwargs):
    """Module-level print -- delegates to tr.print (colour-aware)."""
    tr.print(*args, **kwargs)


def init_terminal():
    """Create the tml instance and install colour wrappers. [PRIMESUD]

    Called once from PrimeSud.run() so HP Prime's alphabetical .py
    auto-loading does not touch the display before the app is ready.
    """
    global tr
    if tr is not None:
        return
    tr = tml(
        dark_mode=DARK_MODE, tab_size=TAB_SIZE, bg_color=BG_COLOR, font=FONT,
        scrollback_size=SCROLLBACK_SIZE, scroll_step=SCROLL_STEP,
        touch_scroll_step=TOUCH_SCROLL_STEP, swipe_threshold=SWIPE_THRESHOLD,
        fling_frame_ms=FLING_FRAME_MS, fling_min_velocity=FLING_MIN_VELOCITY,
        fling_decay_num=FLING_DECAY_NUM, fling_decay_den=FLING_DECAY_DEN,
        fling_smooth_num=FLING_SMOOTH_NUM,
    )
    install_color_print(tr)
