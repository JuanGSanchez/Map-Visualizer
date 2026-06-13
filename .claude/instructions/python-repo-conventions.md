# Instruction — Python Repo Conventions (Map-Visualizer)

Auto-applied. The repo-specific engineering rules every code/test/docs agent obeys.
Agents cite this file; they do not restate it. The authoritative invariant list lives
in `CLAUDE.md` § CRITICAL invariants — this file adds the conventions, not a copy.

## Directives

1. **Headless-core purity.** `map_visualizer/core.py` imports ONLY
   `matplotlib.figure.Figure`, `matplotlib.backends.backend_agg.FigureCanvasAgg`,
   `matplotlib.colormaps`, `matplotlib.colors`, `matplotlib.image`. NEVER
   `matplotlib.pyplot`; NEVER Qt/Tk/any interactive backend. Use `Figure.colorbar`
   (not `pyplot.colorbar`), build norms via `matplotlib.colors`, export vectors via
   `FigureCanvasAgg`/`savefig`. All Qt code stays under `map_visualizer/gui/`.
   `enums.py` stays import-side-effect-free. The `block-pyplot-qt-in-core` hook enforces this.
2. **Shared render math.** Render logic lives in core behind the `draw_*` Axes helpers;
   the GUI calls the SAME helpers — never duplicate render math in `gui/`.
3. **`render()` returns valid bytes.** PNG by default (magic `\x89PNG\r\n\x1a\n`); a
   requested vector format returns valid `<?xml`/`<svg` or `%PDF` bytes.
4. **Typed errors → 422.** New client-input validation raises one of the four typed core
   exceptions (`GridLoadError`, `GridValidationError`, `InvalidParameterError`,
   `RenderError`) at the boundary so the access layer maps it to HTTP 422 `{error,
   message}` / MCP `isError`. No client input may escape to an unhandled HTTP 500. Never
   catch a malformed case with a broad `except Exception` in a route.
5. **Loader hardening is sacrosanct.** Ragged / empty / all-NaN / oversize (`max_cells`)
   inputs keep raising their typed errors. `max_cells` is server-side and fixed; clients
   cannot raise it. A render-time bound is additive, never a replacement.
6. **Deterministic, offline tests.** Tests use fixed inline grids and assert on magic
   bytes / `array.shape` / axis or artist counts — never on a network, a wall clock, a
   random seed, or rendered pixel content. The access layer is exercised in-process
   (ASGI `httpx.AsyncClient`), not over a live socket.
7. **Coverage gate is the contract.** `python -m pytest` enforces `--cov-fail-under=90`
   on `map_visualizer` with `gui/*` and `api/*` omitted. Never lower `--cov-fail-under`,
   widen the `omit` list, or delete a failing test to make it pass. New core code ships
   with tests that cover it. The `coverage-gate-reminder` hook surfaces this on edits.
8. **No secrets, no committed bundles.** No keys/tokens/`.env`. `packaging/bin/` and
   `packaging/work/` stay out of VCS. PyInstaller excludes (`tkinter`, `backend_tkagg`,
   `wx`, `gtk`, `PyQt5`, `PyQt6`, `PySide2`) stay effective. No Tkinter regression — the
   legacy `MVis_UI.pyw`/`MVis_utils.py` are dead and must not be reintroduced or imported.
   The `block-secrets-and-bundles` and `guard-tkinter-regression` hooks enforce these.

## Principles Applied
- P1 Source-of-Truth Grounding — every rule traces to `CLAUDE.md`, `pyproject.toml`, the core, or the backlog.
- P4 Consistency — one convention set the whole roster shares.
- P6 Self-Containment — complete as stated; defers the invariant *list* to `CLAUDE.md` by reference.
- P7 Reference Hygiene — cited by agents, never restated; every named path/hook exists.

## Sources
- `CLAUDE.md` (invariant list + gate commands), `pyproject.toml` (gate config, omit list, deps),
  `map_visualizer/core.py` (Agg import set, typed exceptions), `docs/BACKLOG.md` (422 mapping, loader hardening).
