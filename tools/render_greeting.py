"""Render PrimeSUD greeting or score screens to a device-accurate PNG.

The PC shim (pc_shim/) is text/ANSI only -- its hpprime pixel calls are
no-ops -- so it cannot produce a real screen capture. This tool instead
reproduces the on-device pixel output directly: it blits glyphs from the
selected font atlas and recolours each {X run exactly like src/terminal.py
does on the calculator (dark mode, black background, per-run foreground
recolour).

Needs Pillow (dev-only, like build_dist's python_minifier):
    python -m pip install Pillow

Usage:
    python tools/render_greeting.py
    python tools/render_greeting.py --score
    python tools/render_greeting.py --font reference/fonts/scientifica5x10.font out.png
"""
import argparse
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "pc_shim"))
from colors import color_parse_runs  # noqa: E402

FONT = ROOT / "src" / "std5x10.font"
COLS, ROWS = 64, 22          # text grid (config.TERMINAL_COLS / _ROWS)
DEFAULT_FG = (255, 255, 255)  # dark-mode reset colour = white glyph
BG = (0, 0, 0)                # config.BG_COLOR = 0, dark mode
SCALE = 3

# Greeting art, verbatim from primesud.py show_greeting(). Static banner --
# duplicated here (not importable without booting the app); keep in sync.
FREE = "23.4K"  # representative heap; device shows live gc.mem_free()
_mem = "{G(Mem. free: %s)" % FREE
_pad = 64 - 23 - len(_mem) - 1
LINES = [
    '{C 8888888b.          d8b' + ' ' * _pad + _mem + '{x',
    "{C 888   Y88b         Y8P                                       {x",
    "{C 888    888                                                   {x",
    "{C 888   d88P 888d888 888 88888b.d88b.   .d88b.                 {x",
    '{C 8888888P"  888P"   888 888 "888 "88b d8P  Y8b                {x',
    "{C 888        888     888 888  888  888 88888888                {x",
    "{C 888        888     888 888  888  888 Y8b.                    {x",
    '{C 888        888     888 888  888  888  "Y8888                 {x',
    "{C                             .d8888b.  888     888 8888888b.  {x",
    '{C                            d88P  Y88b 888     888 888  "Y88b {x',
    "{C                            Y88b.      888     888 888    888 {x",
    '{C                             "Y888b.   888     888 888    888 {x',
    '{C                                "Y88b. 888     888 888    888 {x',
    '{C                                  "888 888     888 888    888 {x',
    "{C                            Y88b  d88P Y88b. .d88P 888  .d88P {x",
    '{C                             "Y8888P"   "Y88888P"  8888888P"  {x',
    "{c      Original DikuMUD by Hans Staerfeldt, Katja Nyboe,       {x",
    "{c      Tom Madsen, Michael Seifert, and Sebastian Hammer       {x",
    "{c      Based on MERC 2.1 code by Hatchet, Furey, and Kahn      {x",
    "{c      ROM 2.4 copyright (c) 1993-1998 Russ Taylor.            {x",
    "{c      1stMud Server copyright (c) 2001-2004, Markanth.        {x",
    "                    [Press Enter to start]                     ",
]


def score_lines():
    """Return a representative score sheet from the real game formatter."""
    import info
    from classes import CLASS_WARRIOR
    from player import create_char

    player = create_char(CLASS_WARRIOR)
    player.update({
        "name": "Aldren",
        "level": 17,
        "xp": 148750,
        "xp_next": 170000,
        "hit": 312,
        "max_hit": 365,
        "mana": 94,
        "max_mana": 128,
        "move": 176,
        "max_move": 210,
        "practice": 7,
        "train": 2,
        "quest_points": 43,
        "gold": 125,
        "silver": 684,
        "alignment": -375,
        "played": 187200,
        "gold_bank": 2400,
        "shares": 3,
        "armor": [-180, -140, -165, -95],
    })
    lines = []
    info.chprintln = lambda _player, value="": (
        lines.extend(value) if type(value) is list else lines.append(value))
    info.free_mem = lambda: FREE
    info.gc_collect = lambda: None
    info.do_score(player, [])
    return lines


def load_glyphs(font):
    """Map char -> per-pixel ink mask from the font atlas.

    Atlas is a horizontal strip of 5x10 glyphs, index = ord(c) - 32,
    black ink (0,0,0) on white. Returns (cw, ch, {char: set((x, y))}).
    """
    atlas = Image.open(font).convert("RGB")
    w, ch = atlas.size
    cw = (font.read_bytes()[-1] >> 3) + 4  # tml.py: char_width from last byte
    px = atlas.load()
    glyphs = {}
    for code in range(32, 127):
        base = (code - 32) * cw
        glyphs[chr(code)] = {
            (x, y)
            for x in range(cw)
            for y in range(ch)
            if px[base + x, y] == (0, 0, 0)
        }
    return cw, ch, glyphs


def render(lines, font):
    cw, ch, glyphs = load_glyphs(font)
    # Full 320x240 screen: 22 text rows (220px) + status bar (20px). The
    # device draws a gray separator across the status area at boot
    # (tml.__init__: rect at y = height + char_height//2), status empty here.
    img = Image.new("RGB", (COLS * cw, 240), BG)
    px = img.load()
    sep_y = ROWS * ch + ch // 2
    for x in range(COLS * cw):
        px[x, sep_y] = (0x7F, 0x7F, 0x7F)
        px[x, sep_y + 1] = (0x7F, 0x7F, 0x7F)
    for row, line in enumerate(lines[:ROWS]):
        x = 0
        for colour, seg in color_parse_runs(line):
            rgb = DEFAULT_FG if colour is None else (
                (colour >> 16) & 0xFF, (colour >> 8) & 0xFF, colour & 0xFF)
            for c in seg:
                if x >= COLS:
                    break
                for gx, gy in glyphs.get(c, ()):
                    px[x * cw + gx, row * ch + gy] = rgb
                x += 1
    return img


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("out", nargs="?", type=Path)
    parser.add_argument("--font", type=Path, default=FONT)
    parser.add_argument("--score", action="store_true")
    args = parser.parse_args()
    name = "score.png" if args.score else "greeting.png"
    out = args.out or ROOT / "docs" / "img" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    img = render(score_lines() if args.score else LINES, args.font)
    if SCALE != 1:
        img = img.resize((img.width * SCALE, img.height * SCALE), Image.NEAREST)
    img.save(out)
    print("wrote %s (%dx%d)" % (out, img.width, img.height))


if __name__ == "__main__":
    main()
