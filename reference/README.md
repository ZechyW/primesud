Sample Python apps for the HP Prime — general reference for available functionality.

---

Standalone app vs Python-based app:
- **Python-based app** has configurable settings (`shift-plot`).
  - Relies on "Automatically Load Files When Changed" to run; may need to hit Clear between runs.
  - Respects heap size config (increases memory available to the app).
- **Standalone app** runs a PPL wrapper.
  - Runs automatically without needing to hit Clear.
  - Heap size hard-limited to 1 MB.

---

## Samples

- **`keyspy/`** — utility for checking the bit index of any pressed key.
- **`trek/`** — a Python port of the classic 1972 Star Trek text game, adapted to run on the HP Prime via `tml.py`.
- **`jezzball/`** — a full graphical JezzBall clone (1.23 by komame); source of the environment setup/teardown pattern used in this project. Includes a binary compression loader in the deployed `.hpappdir`.
- **`standalone app/` and `python-based app/`** — bare `.hpapp`/`.hpappprgm` skeletons illustrating the two deployment modes described above.
