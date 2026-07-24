# Font candidates

Most of these compact bitmap fonts were selected for PrimeSUD's 5x10 terminal
during a review of the
[Tecate bitmap-fonts collection](https://github.com/Tecate/bitmap-fonts).
`std5x10.font` came from
[Text Mode Layer (tml) 1.0](https://www.hpcalc.org/details/9661).
`neep5x11.font` was adapted from its 5x11 source to fit a 5x10 cell.

The collection catalogs fonts from many original authors rather than creating
them. Authorship and licensing therefore remain font-specific; consult the
upstream collection and its bundled font documentation before redistributing
these files outside PrimeSUD.

## Files

- `edges5x10.font`
- `glean5x10.font`
- `lemon5x10.font`
- `lime5x10.font`
- `neep5x10.font`
- `neep5x11.font`
- `scientifica5x10.font`
- `spleen5x10.font`
- `std5x10.font`
- `tamzen5x10.font`

Matching `greeting-*.png` and `score-*.png` files are 640x480 reference
renders. `font-candidates.png` is the comparison sheet.

Each `.font` file is a horizontal PNG atlas containing printable ASCII
characters, followed by TML's character-width byte. These are reference
candidates.

[`tools/convert_bdf_font.py`](../../tools/convert_bdf_font.py) documents the
conversion used for compatible BDF sources. Some atlases also have small
PrimeSUD-specific pixel adjustments for cleaner table borders; Git history
records those changes.
