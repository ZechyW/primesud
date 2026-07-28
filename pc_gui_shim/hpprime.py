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
_scale = 2
_dirty = True
_closed = False
_pointer_down = False
_pointer_x = 0
_pointer_y = 0


def init_display(scale=2):
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
        _root, width=320 * scale, height=240 * scale,
        borderwidth=0, highlightthickness=0,
    )
    _canvas.pack()
    _canvas_image = _canvas.create_image(0, 0, anchor="nw")
    _root.bind("<KeyPress>", _on_key)
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
        _events.append("\x03")


def _on_key(event):
    special = {
        "Return": "\n",
        "KP_Enter": "\n",
        "BackSpace": "\b",
        "Escape": "\\e",
        "Left": "\\L",
        "Right": "\\R",
        "Up": 12,
        "Down": 13,
        "Prior": 10,
        "Next": 11,
        "F1": 14,
        "F2": 15,
        "F3": 16,
        "F4": 17,
        "F5": 18,
        "F6": 19,
        "F7": 20,
        "F8": 21,
        "F9": 22,
        "F10": 23,
    }
    value = special.get(event.keysym)
    if value is None:
        if event.state & 4 and event.keysym.lower() == "c":
            value = "\x03"
        elif (event.char == "\t"
              or (len(event.char) == 1 and ord(event.char) >= 32)):
            value = event.char
    if value is not None:
        _events.append(value)
    return "break"


def _pointer_position(event):
    return (
        min(319, max(0, event.x // _scale)),
        min(239, max(0, event.y // _scale)),
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
        _events.append("\x03")


def wait_event():
    """Return next desktop key event, blocking while pumping Tk."""
    while not _events:
        pump_events()
        time.sleep(0.01)
    return _events.popleft()


def poll_event():
    """Return next desktop key event, or None."""
    pump_events()
    return _events.popleft() if _events else None


def has_events():
    return bool(_events)


def wait_ms(ms):
    """Wait without starving Tk's event loop."""
    end = time.monotonic() + ms / 1000.0
    while True:
        pump_events()
        remaining = end - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 0.01))


def _present():
    global _dirty, _display_image
    if not _dirty or _root is None:
        return
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
    return 0


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


def fillrect(grob, x, y, width, height, color, border=None):
    target = _grobs.get(grob)
    if target is None:
        return
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(target.width, x + width)
    y2 = min(target.height, y + height)
    if x1 >= x2 or y1 >= y2:
        return
    row = _rgb(color) * (x2 - x1)
    for py in range(y1, y2):
        start = (py * target.width + x1) * 3
        target.pixels[start:start + len(row)] = row
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
