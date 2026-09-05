# PrimeSUD -- AGENTS.md

See [CLAUDE.md](CLAUDE.md) -- single source of truth for project instructions.
Read it before acting; its standing instructions are binding.

## Codex test sandbox

On managed Windows, run `python -m pytest -q -p no:cacheprovider` with
elevated permissions from the start. Do not use a repo-local `--basetemp`;
those directories may become inaccessible and hard to clean up.

In PowerShell, do not pass wildcard paths to `rg`; use
`rg <pattern> <dir> -g '<glob>'` to avoid OS Error 123.

## Docker sandbox test gate

Host-mounted folders do not support symlinks (virtiofs/FUSE), so a
project-local `.venv` on the mount is broken -- `uv venv` symlinks the
interpreter in and reports success, but the link never exists
(`uv run` then fails with "Failed to spawn"). Keep the venv on the
local overlay fs instead:

```
UV_PROJECT_ENVIRONMENT=/tmp/primesud-venv uv run pytest -q -n 4
UV_PROJECT_ENVIRONMENT=/tmp/primesud-venv uv run python tools/check_ascii_py.py
```
