"""Convert a fixed-width BDF font to TML's printable-ASCII PNG atlas."""
import argparse
from pathlib import Path

from PIL import BdfFontFile, Image


def convert(source, output, trim_plus=False):
    """Write printable ASCII from a 5-pixel BDF into a 5x10 TML font."""
    with source.open("rb") as stream:
        font = BdfFontFile.BdfFontFile(stream)
    glyphs = font.glyph[32:127]
    if any(glyph is None for glyph in glyphs):
        raise ValueError("font lacks printable ASCII glyphs")
    if any(glyph[0][0] != 5 for glyph in glyphs):
        raise ValueError("font is not fixed at a 5-pixel advance")

    bounds = []
    for _advance, dst, _src, bitmap in glyphs:
        box = bitmap.getbbox()
        if box:
            bounds.append((dst[0] + box[0], dst[1] + box[1],
                           dst[0] + box[2], dst[1] + box[3]))
    if min(box[0] for box in bounds) < 0 or max(box[2] for box in bounds) > 5:
        raise ValueError("printable ASCII ink does not fit five columns")
    top = min(box[1] for box in bounds)
    bottom = max(box[3] for box in bounds)
    if bottom - top > 10:
        raise ValueError("printable ASCII ink does not fit ten rows")

    atlas = Image.new("1", (95 * 5, 10), 1)
    pad = (10 - (bottom - top)) // 2
    for index, (_advance, dst, _src, bitmap) in enumerate(glyphs):
        atlas.paste(0, (index * 5 + dst[0], pad + dst[1] - top), bitmap)
    if trim_plus:
        x = (ord("+") - 32) * 5 + 4
        for y in range(10):
            atlas.putpixel((x, y), 1)
    output.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(output, "PNG")
    with output.open("ab") as stream:
        stream.write(b"\x08")  # TML: 5-pixel character width.


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--trim-plus", action="store_true")
    args = parser.parse_args()
    convert(args.source, args.output, args.trim_plus)


if __name__ == "__main__":
    main()
