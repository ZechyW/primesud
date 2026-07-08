# PrimeSUD

Single-player MUD for the HP Prime graphing calculator.

A port of 1stMud (a ROM 2.4 DikuMUD), running in a text UI on the calculator's 320x240 screen. Classes, races, spells, skills, quests, and shops; multiplayer mechanics are cut or reworked for solo play.

![PrimeSUD greeting screen](docs/img/greeting.png)

*Greeting screen, drawn with the on-device 5x10 font. Rebuild with `python tools/render_greeting.py`.*

## Features

- Combat with stances, full spell and skill tables, six classes with remort and multiclassing, races with per-race stat caps and skills, groups, healers, shops, training and practising. Ported functions are checked against 1stMud and dated in their docstrings.
- Quests and gquests. No gquest join window; auto-joined when one starts (see `DESIGN.md`).
- Stock ROM 2.4 area files load unmodified via `tools/are_to_primesud.py`: rooms, mobs, objects, resets, shops, specials. 22 areas bundled (Midgaard, Moria, the Shire, New Thalos, and others).
- Automap and per-room exploration tracking (`explored` command).
- Deviations from 1stMud documented in `DESIGN.md`.
- Build step minifies source to save space on the calculator, verifying no symbols or area data change.
- Runs on PC. Shims in `pc_shim/` replace the Prime's `hpprime`, `urandom`, and text layer, so plain CPython suffices.

## Requirements

Calculator: an HP Prime (or the Virtual Calculator emulator) and the HP Connectivity Kit for file transfer.

PC: Python 3, no runtime dependencies. The dist build also needs `python-minifier` and git-bash on PATH.

## Running on a PC

```
python run_source.py   # run src/ directly, no build
python run_dist.py      # build the minified dist first, then run it
```

`run_source.py` for everyday use. `run_dist.py` builds `dist/` and runs the minified copy, catching anything minification broke.

Saves live in the repo root (`primesud.sav`, gitignored), shared between both runners, so `dist/` stays a clean transfer copy.

## Deploying to a calculator

```
python tools/build_dist.py           # build dist/primesud.hpappdir
python tools/build_dist.py --check   # also verify symbols + area data survived
```

Regenerates derived data (areas, world tables, mob index, help), then writes ASCII-only, BOM-free files to `dist/primesud.hpappdir/`. Copy that folder over with the Connectivity Kit.

If the emulator runs clean but real hardware glitches or corrupts saves, reset the calculator first (Esc + Apps + On, or FCO).

## Layout

| Path | Contents |
|---|---|
| `src/` | Game code and data (`.py`, `area_*.txt`, fonts, help) |
| `pc_shim/` | Prime-runtime stand-ins for running on PC |
| `areas/` | Original ROM 2.4 `.are` files |
| `tools/` | Build, conversion, and data-gen scripts |
| `docs/` | Reference, device limits, PrimeSUD internals |
| `DESIGN.md` | Where and why PrimeSUD differs from 1stMud |
| `TODO.md` | Loose ends |

See `CLAUDE.md` for dev conventions and HP Prime constraints.
