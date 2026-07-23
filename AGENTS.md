# PrimeSUD -- AGENTS.md

See [CLAUDE.md](CLAUDE.md) -- single source of truth for project instructions.

## Codex test sandbox

On managed Windows, run `python -m pytest -q -p no:cacheprovider` with
elevated permissions from the start. Do not use a repo-local `--basetemp`;
those directories may become inaccessible and hard to clean up.

In PowerShell, do not pass wildcard paths to `rg`; use
`rg <pattern> <dir> -g '<glob>'` to avoid OS Error 123.
