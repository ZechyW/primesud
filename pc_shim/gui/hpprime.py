"""Tkinter-backed subset of the HP Prime graphics API."""

from collections import deque
import os
import time


class _Grob:
    def __init__(self, width, height, color=0):
        self.width = width
        self.height = height
        self.pixels = bytearray(_rgb(color) * (width * height))


def _rgb(color):
    return bytes(((color >> 16) & 255, (color >> 8) & 255, color & 255))


_grobs = {0: _Grob(320, 240, 0)}
_events = deque()
_root = None
_canvas = None
_canvas_image = None
_display_image = None
_tk = None
_scale = 1
_dirty = True
_closed = False
_pointer_down = False
_pointer_x = 0
_pointer_y = 0
# Viewport padding so Windows 11's rounded window corners don't clip pixels;
# grey (vs black) marks the exact 320x240 emulated area.
_PAD = 8
_MAX_SCALE = 8


def init_display(scale=1):
    """Open the graphical PC display."""
    global _root, _canvas, _canvas_image, _tk, _scale, _closed
    global _pointer_down
    if _root is not None:
        return
    import tkinter

    _tk = tkinter
    _scale = scale
    _closed = False
    _pointer_down = False
    _root = tkinter.Tk()
    _root.title("PrimeSUD")
    _root.resizable(False, False)
    _canvas = tkinter.Canvas(
        _root, width=320 * scale + 2 * _PAD, height=240 * scale + 2 * _PAD,
        borderwidth=0, highlightthickness=0, bg="#303030",
    )
    _canvas.pack()
    _canvas_image = _canvas.create_image(_PAD, _PAD, anchor="nw")
    _root.bind("<KeyPress>", _on_key)
    _root.bind("<MouseWheel>", _on_wheel)
    _canvas.bind("<ButtonPress-1>", _on_pointer_down)
    _canvas.bind("<B1-Motion>", _on_pointer_move)
    _canvas.bind("<ButtonRelease-1>", _on_pointer_up)
    _root.protocol("WM_DELETE_WINDOW", _on_close)
    _root.focus_force()
    pump_events()


def close_display():
    """Close the graphical PC display."""
    global _root, _closed
    if _root is not None:
        try:
            _root.destroy()
        except Exception:
            pass
    _root = None
    _closed = True


def _on_close():
    global _closed, _pointer_down
    if not _closed:
        _closed = True
        _pointer_down = False
        _events.append(("interrupt", None))


def _set_scale(scale):
    """Resize the desktop view without changing emulated coordinates."""
    global _scale, _dirty
    scale = min(_MAX_SCALE, max(1, scale))
    if scale == _scale:
        return
    _scale = scale
    _canvas.configure(
        width=320 * scale + 2 * _PAD,
        height=240 * scale + 2 * _PAD,
    )
    _dirty = True


def _on_key(event):
    key_bits = {
        "Escape": 4,
        "Left": 7,
        "Right": 8,
        "Up": 2,
        "Down": 12,
        "Return": 30,
        "KP_Enter": 30,
        "BackSpace": 19,
        "F1": 21,
        "F2": 22,
        "F3": 23,
        "F4": 24,
        "F5": 25,
        "F6": 26,
        "F7": 27,
        "F8": 28,
        "F9": 29,
        "F10": 20,
    }
    value = None
    if event.state & 4 and event.keysym in ("equal", "plus", "KP_Add"):
        _set_scale(_scale + 1)
    elif event.state & 4 and event.keysym in ("minus", "KP_Subtract"):
        _set_scale(_scale - 1)
    elif event.state & 4 and event.keysym == "0":
        _set_scale(1)
    elif event.state & 4 and event.keysym.lower() == "c":
        value = ("interrupt", None)
    elif event.keysym == "Prior":
        value = ("scroll_up", None) if event.state & 1 else ("bit", 1)
    elif event.keysym == "Next":
        value = ("scroll_down", None) if event.state & 1 else ("bit", 3)
    elif event.keysym in key_bits:
        value = ("bit", key_bits[event.keysym])
    elif (event.char == "\t"
          or (len(event.char) == 1 and ord(event.char) >= 32)):
        value = ("char", event.char)
    if value:
        _events.append(value)
    return "break"


def _on_wheel(event):
    # Windows: event.delta is a multiple of 120 per notch.
    kind = "scroll_up" if event.delta > 0 else "scroll_down"
    for _ in range(max(1, abs(event.delta) // 120)):
        _events.append((kind, None))
    return "break"


def _pointer_position(event):
    return (
        min(319, max(0, (event.x - _PAD) // _scale)),
        min(239, max(0, (event.y - _PAD) // _scale)),
    )


def _on_pointer_down(event):
    global _pointer_down, _pointer_x, _pointer_y
    _pointer_x, _pointer_y = _pointer_position(event)
    _pointer_down = True
    return "break"


def _on_pointer_move(event):
    global _pointer_x, _pointer_y
    _pointer_x, _pointer_y = _pointer_position(event)
    return "break"


def _on_pointer_up(event):
    global _pointer_down, _pointer_x, _pointer_y
    _pointer_x, _pointer_y = _pointer_position(event)
    _pointer_down = False
    return "break"


def pump_events():
    """Present pending pixels and process Tk events."""
    global _closed
    if _root is None or _closed:
        return
    _present()
    try:
        _root.update_idletasks()
        _root.update()
    except Exception:
        _closed = True
        _events.append(("interrupt", None))


def poll_event():
    """Return next desktop key event, or None."""
    return _events.popleft() if _events else None


def has_events():
    return bool(_events)


def clear_events():
    _events.clear()


def wait_ms(ms):
    """Wait without starving Tk's event loop."""
    end = time.monotonic() + ms / 1000.0
    while True:
        pump_events()
        remaining = end - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 0.01))


_FRAME_S = 0.016  # min seconds between canvas presents (~60fps)
_last_present = 0.0


def _present():
    # Throttled: a full present (PPM encode + PhotoImage + zoom) costs
    # ~5ms, and the streaming reveal pumps once per char wait -- an
    # unthrottled present floors every REVEAL_MS_PER_CHAR wait at ~5ms.
    # Dirty state persists, so the frame lands on a pump within
    # _FRAME_S of the last draw; the game loop pumps continuously.
    global _dirty, _display_image, _last_present
    if not _dirty or _root is None:
        return
    now = time.monotonic()
    if now - _last_present < _FRAME_S:
        return
    _last_present = now
    screen = _grobs[0]
    header = ("P6\n" + str(screen.width) + " " + str(screen.height)
              + "\n255\n").encode("ascii")
    image = _tk.PhotoImage(data=header + bytes(screen.pixels), format="PPM")
    _display_image = image.zoom(_scale, _scale) if _scale != 1 else image
    _canvas.itemconfigure(_canvas_image, image=_display_image)
    _dirty = False


def _mark_dirty(grob):
    global _dirty
    if grob == 0:
        _dirty = True


def _load_png(grob, filename):
    image = _tk.PhotoImage(file=os.path.abspath(filename), format="png")
    width = image.width()
    height = image.height()
    target = _Grob(width, height)
    pixels = target.pixels
    pos = 0
    for y in range(height):
        for x in range(width):
            color = image.get(x, y)
            if isinstance(color, str):
                color = _root.winfo_rgb(color)
                color = (color[0] >> 8, color[1] >> 8, color[2] >> 8)
            pixels[pos:pos + 3] = bytes(color[:3])
            pos += 3
    _grobs[grob] = target


def eval(expr):
    """Evaluate small PPL subset used by text renderer."""
    if expr == "GETKEY":
        return -1
    if expr == "Ticks":
        return int(time.monotonic() * 1000)
    if expr == "AFiles":
        return [name for name in os.listdir(".") if name.endswith(".font")]
    if expr.startswith("WAIT("):
        value = expr[5:-1]
        if "/" in value:
            numerator, denominator = value.split("/", 1)
            seconds = float(numerator) / float(denominator)
        else:
            seconds = float(value)
        wait_ms(seconds * 1000)
        return 0
    if expr.startswith("G") and ':=AFiles("' in expr:
        prefix, filename = expr.split(':=AFiles("', 1)
        filename = filename[:-2]
        _load_png(int(prefix[1:]), filename)
        return "PNG"
    if expr.startswith("INVERT_P("):
        body = expr[9:-1]
        if body.startswith("G"):
            grob = int(body[1:])
            target = _grobs[grob]
            for i in range(len(target.pixels)):
                target.pixels[i] = 255 - target.pixels[i]
            _mark_dirty(grob)
        else:
            x1, y1, x2, y2 = (int(value) for value in body.split(","))
            target = _grobs[0]
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(target.width - 1, x2)
            y2 = min(target.height - 1, y2)
            for y in range(y1, y2 + 1):
                start = (y * target.width + x1) * 3
                end = (y * target.width + x2 + 1) * 3
                for i in range(start, end):
                    target.pixels[i] = 255 - target.pixels[i]
            _mark_dirty(0)
        return 0
    return 0


def keyboard():
    # Device scrollback uses keyboard() only as an event-availability gate.
    return 1 if _events else 0


def mouse():
    if _pointer_down:
        return [(_pointer_x, _pointer_y, 1)]
    return [(-1, 0, 0)]


def dimgrob(grob, width, height, color=0):
    if width <= 0 or height <= 0:
        if grob != 0:
            _grobs.pop(grob, None)
        return
    _grobs[grob] = _Grob(width, height, color)
    _mark_dirty(grob)


def grobw(grob):
    target = _grobs.get(grob)
    return target.width if target is not None else 0


def grobh(grob):
    target = _grobs.get(grob)
    return target.height if target is not None else 0


def getpix(grob, x, y):
    target = _grobs.get(grob)
    if target is None or not (0 <= x < target.width and 0 <= y < target.height):
        return 0
    pos = (y * target.width + x) * 3
    return (target.pixels[pos] << 16
            | target.pixels[pos + 1] << 8
            | target.pixels[pos + 2])


def pixon(grob, x, y, color):
    target = _grobs.get(grob)
    if target is None or not (0 <= x < target.width and 0 <= y < target.height):
        return
    pos = (y * target.width + x) * 3
    target.pixels[pos:pos + 3] = _rgb(color)
    _mark_dirty(grob)


def fillrect(grob, x, y, width, height, edge_color, fill_color=None):
    target = _grobs.get(grob)
    if target is None:
        return
    if fill_color is None:
        fill_color = edge_color
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(target.width, x + width)
    y2 = min(target.height, y + height)
    if x1 >= x2 or y1 >= y2:
        return
    edge = _rgb(edge_color)
    fill = _rgb(fill_color)
    for py in range(y1, y2):
        interior = py != y and py != y + height - 1
        row_color = fill if interior else edge
        row = row_color * (x2 - x1)
        start = (py * target.width + x1) * 3
        target.pixels[start:start + len(row)] = row
        if interior:
            if x1 == x:
                target.pixels[start:start + 3] = edge
            if x2 == x + width:
                end = (py * target.width + x2 - 1) * 3
                target.pixels[end:end + 3] = edge
    _mark_dirty(grob)


def rect(grob, x, y, width, height, color):
    fillrect(grob, x, y, width, height, color)


def strblit2(dest_grob, dx, dy, width, height,
             src_grob, sx, sy, src_width, src_height):
    dest = _grobs.get(dest_grob)
    src = _grobs.get(src_grob)
    if dest is None or src is None or width <= 0 or height <= 0:
        return

    if width == src_width and height == src_height:
        left = max(0, -dx, -sx)
        top = max(0, -dy, -sy)
        right = min(width, dest.width - dx, src.width - sx)
        bottom = min(height, dest.height - dy, src.height - sy)
        if left >= right or top >= bottom:
            return
        rows = None
        if dest is src:
            rows = []
            for py in range(top, bottom):
                start = ((sy + py) * src.width + sx + left) * 3
                rows.append(bytes(src.pixels[start:start + (right - left) * 3]))
        for index, py in enumerate(range(top, bottom)):
            dstart = ((dy + py) * dest.width + dx + left) * 3
            if rows is None:
                sstart = ((sy + py) * src.width + sx + left) * 3
                dest.pixels[dstart:dstart + (right - left) * 3] = (
                    src.pixels[sstart:sstart + (right - left) * 3]
                )
            else:
                dest.pixels[dstart:dstart + len(rows[index])] = rows[index]
        _mark_dirty(dest_grob)
        return

    source = bytes(src.pixels) if dest is src else src.pixels
    for oy in range(height):
        dest_y = dy + oy
        src_y = sy + oy * src_height // height
        if not (0 <= dest_y < dest.height and 0 <= src_y < src.height):
            continue
        for ox in range(width):
            dest_x = dx + ox
            src_x = sx + ox * src_width // width
            if not (0 <= dest_x < dest.width and 0 <= src_x < src.width):
                continue
            dpos = (dest_y * dest.width + dest_x) * 3
            spos = (src_y * src.width + src_x) * 3
            dest.pixels[dpos:dpos + 3] = source[spos:spos + 3]
    _mark_dirty(dest_grob)
