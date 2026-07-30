"""PrimeSUD colour-aware terminal print/status wrappers."""

from tml_prime import tml_prime as tml
from config import (
    TERMINAL_COLS, FONT_GROB, COLOR_GROB, SCRATCH_GROB, COLORFONT_GROB,
    DARK_MODE, BG_COLOR, TAB_SIZE, FONT,
    SCROLLBACK_SIZE, SCROLL_STEP, SWIPE_THRESHOLD, TOUCH_SCROLL_STEP,
    FLING_FRAME_MS, FLING_MIN_VELOCITY, FLING_DECAY_NUM, FLING_DECAY_DEN,
    FLING_SMOOTH_NUM, KEY_COMMANDS, REVEAL_MS_PER_LINE,
    REVEAL_MS_PER_CHAR,
)
from colors import (COLOR_CODE, ANSI_COLORS, _RESET_CODES, color_wrap_full,
                    resolve_random, strip_colors)
from hpprime import dimgrob, fillrect, getpix, grobh, grobw, pixon, strblit2
from prime_platform import ticks
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
    # [PRIMESUD] one FONT_GROB-sized band per colour ever seen -- ANSI_COLORS
    # has 16 distinct entries and resolve_random only ever emits codes from
    # that table, so 16 bands is a hard upper bound.
    dimgrob(COLORFONT_GROB, font_w, font_h * len(ANSI_COLORS), 0)
    _w_x = (ord('W') - 32) * tr.char_width + tr.char_width // 2
    font_fg = getpix(FONT_GROB, _w_x, tr.char_height // 2)
    fg_rows = [
        [x for x in range(font_w) if getpix(FONT_GROB, x, y) == font_fg]
        for y in range(font_h)
    ]
    current_fg = [None]
    _bands = {}  # [PRIMESUD] colour int -> cached band row in COLORFONT_GROB
    _max_bands = len(ANSI_COLORS)

    def set_color(color):
        # [PRIMESUD] the pixon repaint loop below cost ~30-40ms of Python
        # per-pixel writes at full game heap; a cached colour now costs one
        # native strblit2 blit instead (PERFORMANCE.md sec. Text rendering).
        if color == current_fg[0]:
            return
        current_fg[0] = color
        band = _bands.get(color)
        if band is not None:
            strblit2(FONT_GROB, 0, 0, font_w, font_h,
                     COLORFONT_GROB, 0, band * font_h, font_w, font_h)
            return
        _po = pixon
        for y, xs in enumerate(fg_rows):
            for x in xs:
                _po(FONT_GROB, x, y, color)
        if len(_bands) < _max_bands:
            band = len(_bands)
            _bands[color] = band
            strblit2(COLORFONT_GROB, 0, band * font_h, font_w, font_h,
                     FONT_GROB, 0, 0, font_w, font_h)
        # else: unreachable (ANSI_COLORS/resolve_random bound colours to
        # _max_bands distinct values) -- repaint above already ran, just
        # skip caching this defensively.

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
    _rr = resolve_random
    _pxy = tr.print_xy
    _pch = tr._put_char
    # [PRIMESUD] same key-command mapping the game loop passes to
    # poll_char (see primesud.py) -- paced reveal pumps the keyboard with
    # it so a queued hardware command key fast-forwards identically to a
    # plain character key.
    _KC = KEY_COMMANDS
    # [PRIMESUD] delay-loop safety valve: bounds CONSECUTIVE spins with
    # no clock progress, so a frozen Ticks() (a pc_shim/emulator quirk,
    # not seen on real firmware) degrades to "reveals faster than
    # intended" instead of a hang. Counting total spins instead was
    # wrong: a fast host (PC shim, ~6us/spin) burns any fixed total
    # before 25ms of real time elapses, silently truncating the reveal.
    _REVEAL_MAX_ITERS = 2000

    def _reveal_wait(ms):
        """Delay one row of the streaming output reveal. [PRIMESUD]

        Pumps the keyboard every spin so a hardware key lands in the
        local queue the same way the main loop's poll_char would.
        Returns True the instant a key is queued (caller should
        fast-forward the remaining reveal), False once `ms` has elapsed
        with nothing queued.
        """
        t0 = ticks()
        last = t0
        i = 0
        while i < _REVEAL_MAX_ITERS:
            tr._pump_keyboard(_KC)
            if tr.has_queued_keys():
                return True
            t = ticks()
            dt = t - t0
            if dt >= ms or dt < 0:  # elapsed, or clock wrapped/regressed
                return False
            if t != last:  # clock alive -- only count stalled spins
                last = t
                i = 0
            i += 1
        return False

    # [PRIMESUD] streaming-reveal state shared by every output path:
    # [skip_latch, last_row_ticks].  skip_latch: a key arrived during a
    # reveal wait -- draw everything instantly until control returns to
    # input (any set_status call resets; the key itself stays queued as
    # pending input).  last_row_ticks: when the last row was revealed;
    # cadence is time-based, so it carries across calls AND bursts -- a
    # burst starting right after another waits its share instead of
    # printing its first row on top of the previous burst's last row,
    # while a row after idle time (typed command echo, a combat round
    # two seconds later) still lands instantly.
    _reveal = [False, 0]

    def _pace_row():
        """Pace one physical row of the streaming output reveal. [PRIMESUD]

        Waits out whatever remains of REVEAL_MS_PER_LINE since the last
        revealed row, unless pacing is disabled or latched off by a key.
        """
        if REVEAL_MS_PER_LINE <= 0 or _reveal[0]:
            return
        dt = ticks() - _reveal[1]
        if 0 <= dt < REVEAL_MS_PER_LINE:  # wrapped clock -> instant
            if _reveal_wait(REVEAL_MS_PER_LINE - dt):
                _reveal[0] = True
                return
        _reveal[1] = ticks()
    # [PRIMESUD] int-keyed glyph x-offsets for the batch compose: bytes
    # iteration yields ints, so the per-char draw loop allocates nothing
    # (a small alloc costs ~0.5ms at full game heap on device --
    # PERFORMANCE.md sec. Text rendering).
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
        """Render complete lines offscreen, then reveal row by row. [PRIMESUD]

        Groups segments by colour (one font repaint per distinct colour),
        composes the whole batch into SCRATCH_GROB, then reveals this
        call's NEW rows one text-row at a time (REVEAL_MS_PER_LINE
        apart) for an old-school streaming feel -- shared _pace_row
        state, so cadence carries across calls. Each row lands at the
        live cursor position, scrolling the screen one row at a time
        as it fills; with REVEAL_MS_PER_CHAR set, each row's cells
        additionally stream left to right. Any locally-queued key --
        drained by the same
        _pump_keyboard the game loop's poll_char uses -- fast-forwards
        every remaining row in one blit and latches pacing off until
        the next status/prompt update. With pacing off or latched, the
        whole compose lands in one blit.
        """
        physical = []
        for text in lines:
            if _CC not in text:
                physical.extend(_wrap_plain(text, cols))
                continue
            # [PRIMESUD] resolve {?/{` here, before wrapping, so a random-colour
            # span that spills across pieces keeps one colour.
            text = _rr(text)
            if (len(text) - 2 * text.count(_CC) <= cols
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
        # The screen updates atomically (PERFORMANCE.md sec. Text
        # rendering).  With a scroll folded in, the scratch holds the
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
        # [PRIMESUD] streaming reveal. `row` is top + len(physical) (the
        # compose loop above increments it once per physical line), so
        # n_new == len(physical) is exactly this call's NEW line count --
        # never an already-on-screen row, even when a scroll folded
        # older survivors into the same scratch (base == 0 case: those
        # survivors occupy scratch/screen rows [0, top), always blit
        # instantly below; n == 0 case: base == top, so prefix_h == 0
        # and every scratch row is new).
        n_new = row - top
        if (REVEAL_MS_PER_LINE > 0 or REVEAL_MS_PER_CHAR > 0) \
                and not _reveal[0]:
            # [PRIMESUD] incremental reveal: each new row lands at the
            # cursor's live position, scrolling the screen itself one
            # row when it hits the bottom -- what a real terminal does
            # -- instead of jumping the survivors up by the whole batch
            # scroll first and slowly filling the vacated gap. The
            # scroll is the same overlapping G0 self-blit + bottom fill
            # tml._scroll_up uses, done raw here because the history
            # ring was already captured from the pristine G0 above
            # (tr._scroll_up would double-book it). Converges to the
            # scratch's final state: after all rows the cumulative
            # shift equals the folded scroll n.
            cy0 = tr.cursor_y  # original cursor, incl. pending lazy scroll
            shift = 0
            prefix_h = (top - base) * chh
            for i in range(n_new):
                # _pace_row pumps the keyboard and latches the skip the
                # moment a key is queued, so a mid-wait keypress
                # fast-forwards just as promptly as one queued before
                # the wait started.
                _pace_row()
                if _reveal[0]:
                    # Fast-forward: the scratch holds the final text
                    # area; one full blit lands everything pending,
                    # whatever the reveal's progress so far.
                    _sb(0, 0, base * chh, tr.width, h,
                        SCRATCH_GROB, 0, 0, tr.width, h)
                    break
                r = cy0 + i - shift
                d = r - tr.rows + 1
                if d > 0:  # d <= 2: one row of scroll, +1 for a pending
                    shift += d  # blank echo line (cursor_y == rows + 1)
                    r = tr.rows - 1
                    keep = (tr.rows - d) * chh
                    _sb(0, 0, 0, tr.width, keep,
                        0, 0, d * chh, tr.width, keep)
                    fillrect(0, 0, keep, tr.width, d * chh,
                             tr.back_color, tr.back_color)
                sy = prefix_h + i * chh
                if REVEAL_MS_PER_CHAR > 0:
                    # [PRIMESUD] char streaming: blit the row's visible
                    # cells left to right, one reveal wait apart. The
                    # remainder blit afterwards squares the row with the
                    # scratch (clears any stale cells past the text).
                    t = physical[i]
                    wv = len(_sc(t)) if _CC in t else len(t)
                    px = 0
                    for _k in range(wv):
                        if _reveal_wait(REVEAL_MS_PER_CHAR):
                            _reveal[0] = True
                            break
                        _sb(0, px, r * chh, cw, chh,
                            SCRATCH_GROB, px, sy, cw, chh)
                        px += cw
                    if _reveal[0]:
                        _sb(0, 0, base * chh, tr.width, h,
                            SCRATCH_GROB, 0, 0, tr.width, h)
                        break
                    if px < tr.width:
                        _sb(0, px, r * chh, tr.width - px, chh,
                            SCRATCH_GROB, px, sy, tr.width - px, chh)
                    _reveal[1] = ticks()  # next row paces from row end
                else:
                    _sb(0, 0, r * chh, tr.width, chh,
                        SCRATCH_GROB, 0, sy, tr.width, chh)
        else:
            _sb(0, 0, base * chh, tr.width, h, SCRATCH_GROB, 0, 0, tr.width, h)
        tr.cursor_x = 0
        tr.cursor_y = row

    # [PRIMESUD] Combat-round batching: one violence pulse produces many
    # complete-line tprint calls (per-hit messages, deaths, mob triggers).
    # Buffering them and flushing through print_lines cuts a busy round
    # from dozens of per-line screen draws to one blit -- ~4x faster than
    # per-line wrapped_print for the same content (PERFORMANCE.md sec.
    # Text rendering; ~1.07s combat round measured mostly in per-line
    # draws, PERFORMANCE.md sec. Input-lag phase benchmark).
    _batch_buf = []
    _batch_on = [False]

    def begin_batch():
        """Start buffering complete-line tprint output for one flush. [PRIMESUD]"""
        _batch_on[0] = True

    def end_batch():
        """Flush buffered lines through print_lines, then clear the buffer. [PRIMESUD]

        Safe to call with nothing buffered, or when batching was never
        started (idempotent) -- combat_update's try/finally always calls
        this even after an exception mid-round.
        """
        _batch_on[0] = False
        if _batch_buf:
            if tr.cursor_x == 0:
                print_lines(_batch_buf)
            else:
                # Defensive: violence output starts at column 0 in
                # practice, but if something left a partial line pending,
                # fall back to the normal per-line path instead of
                # corrupting print_lines' row math.
                for line in _batch_buf:
                    wrapped_print(line)
            del _batch_buf[:]

    tr.begin_batch = begin_batch
    tr.end_batch = end_batch

    def wrapped_print(*args, sep=' ', end='\n'):
        """Colour-aware print with word-wrap and per-run font recolouring. [PRIMESUD]"""
        if _batch_on[0]:
            is_list = len(args) == 1 and type(args[0]) is list
            if end == '\n':
                if is_list:
                    _batch_buf.extend(args[0])
                else:
                    text = sep.join(str(a) for a in args)
                    if '\n' in text:
                        _batch_buf.extend(text.split('\n'))
                    else:
                        _batch_buf.append(text)
                return
            # Partial-line print (end != '\n'): flush what is buffered so
            # far, in order, then fall through to render THIS call on the
            # normal immediate path below. Not expected mid-violence
            # (combat output is complete-line), but keeps output order
            # exact if it ever happens (e.g. a forced picker prompt).
            end_batch()
            _batch_on[0] = True
        # [PRIMESUD] a single list arg is a pre-split line batch, passed
        # through unjoined (join over %-formatted lines trips the device
        # heap bug, PRIME_FIRMWARE_BUGS.md).
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
        # [PRIMESUD] char streaming: complete lines route through
        # print_lines so the per-char reveal lives in one place; the
        # fast paths below draw whole runs at once. Partial-line prints
        # (end != '\n' or mid-row cursor) stay on the immediate paths.
        if REVEAL_MS_PER_CHAR > 0 and end == '\n' and tr.cursor_x == 0:
            print_lines([text])
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
                # [PRIMESUD] stream: pace rows that start at column 0;
                # continuations of a partial line (end='') never pace.
                if tr.cursor_x == 0:
                    _pace_row()
                if line:
                    _draw_run(line)
                auto_wrapped = line and tr.cursor_x == 0
                if not auto_wrapped:
                    for c2 in (end if idx == n - 1 else '\n'):
                        _pch(c2)
            return
        # Colour-first rendering: split+group in one pass, then render one
        # set_color/reset_color per distinct colour.
        text = _rr(text)
        if len(text) - 2 * text.count(_CC) <= cols and '{{' not in text:
            pieces = (text,)
        else:
            pieces = color_wrap_full(text, cols)
        n = len(pieces)
        for idx, piece in enumerate(pieces):
            colour_order, groups = _group_piece(piece)
            if tr.cursor_x == 0:  # [PRIMESUD] stream: pace each new row
                _pace_row()
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
    _sc = strip_colors

    def wrapped_set_status(text):
        """Colour-aware status bar renderer with visible-width truncation. [PRIMESUD]

        Composes offscreen into SCRATCH_GROB and blits once, same idiom as
        print_lines above -- glyph-by-glyph straight to the screen GROB
        measured ~123ms/call on device; this cuts it to ~10ms
        (PERFORMANCE.md sec. Text rendering). SCRATCH_GROB is shared with
        print_lines, but each use composes and blits within a single call
        (no cross-call state), so there is no conflict.
        """
        # [PRIMESUD] every set_status caller (show_prompt, pager page
        # indicator, autoskill picker) marks control back at input --
        # clear the streaming reveal's type-to-skip latch so the next
        # burst paces again. Cadence itself is time-based (_reveal[1]),
        # so it needs no reset here.
        _reveal[0] = False
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
        # [PRIMESUD] status row spans only the left `length` columns --
        # the rightmost 6 columns are the shift/alpha/lock indicator band
        # (tml._refresh_indicators), never touched by set_status.  Compose
        # scratch is exactly that width so the indicators are left alone.
        row = tr.rows + 1
        cw = tr.char_width
        chh = tr.char_height
        w = length * cw
        dimgrob(SCRATCH_GROB, w, chh, tr.back_color)
        colour_order, groups = _group_piece(text)
        bget = _bmap.get
        _sb = strblit2
        for colour in colour_order:
            if colour is None:
                reset_color()
            else:
                set_color(colour)
            for x, seg in groups[colour]:
                px = x * cw
                for bch in seg.encode():
                    fx = bget(bch, -1)
                    if fx >= 0:
                        _sb(SCRATCH_GROB, px, 0, cw, chh,
                            FONT_GROB, fx, 0, cw, chh)
                    px += cw
        # [PRIMESUD] no separate pad-with-spaces pass: the dimgrob fill
        # above already leaves every untouched cell at tr.back_color, so
        # a shorter new status fully overwrites a longer old one once the
        # final blit below covers the whole `w`-wide row.
        _sb(0, 0, row * chh, w, chh, SCRATCH_GROB, 0, 0, w, chh)
        # [PRIMESUD] deliberate normalisation: the old code only reset to
        # the default colour when padding ran (x < length); when the run
        # filled the row exactly it left the last colour active.  Always
        # resetting here is harmless (the next print/status call sets its
        # own colour state first) and keeps the contract simple.
        reset_color()
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
