# MUD Colorizer (vendored)

Browser tool for colouring MUD text (gradients, xterm/ANSI code formats).
Open `index.html` in any browser; no build step, no dependencies.

Upstream: https://github.com/Coffee-Nerd/MUD-Colorizer by Coffee-Nerd (Asterion),
MIT licensed (see `LICENSE`). Vendored 2026-08-12.

PrimeSUD adaptation: adds a "PrimeSUD/ROM: {X (16-color)" output format that
quantizes colours to the 16-entry palette from `src/colors.py` and emits
ROM-style `{r`/`{G`/`{x` codes usable directly in game strings. Added blocks
are marked `// PrimeSUD adaptation` in `index.html`.
