# Map-Visualizer — repo guide for Claude

Map-Visualizer is a 2-D numeric-array heatmap viewer with a **headless matplotlib (Agg) render
core**, a PySide6 desktop GUI, a dual MCP + REST access layer that returns PNG, PyInstaller
packaging, and a pytest + coverage gate. This file is the always-loaded operating contract for any
Claude session working in this repo. Keep it lean; it states the invariants and the commands, and
points to the detailed assets rather than restating them.

## AI asset suite (`.claude/`)
**Agents** (`.claude/agents/`) — operator drives the live service; the role agents evolve the repo
(one `docs/BACKLOG.md` item by ID, split by capability), with a read-only reviewer as the final gate:
| Agent | Role |
|---|---|
| `map-visualizer-operator` | drives the running MCP/REST service (render/stats/discovery); no code edits |
| `map-visualizer-core-dev` | headless Agg render core + render modes/params + loader hardening (`core.py`/`enums.py`) |
| `map-visualizer-gui-dev` | PySide6 GUI + QtAgg canvas; calls the shared core helpers (`gui/`) |
| `map-visualizer-access-dev` | MCP+REST returning PNG + Pydantic boundary validators → 422 (`api/`) |
| `map-visualizer-test-author` | pytest cases + custody of the >=90% core coverage gate |
| `map-visualizer-packaging-builder` | PyInstaller spec/excludes + no-bundle-in-VCS hygiene (`packaging/`) |
| `map-visualizer-docs-writer` | README / operating doc / access notes, matched to shipped code |
| `map-visualizer-reviewer` | read-only PASS/FAIL on correctness + headless-purity + every invariant |
| `map-visualizer-maintainer` | RETIRED redirect stub → the role agents above (do not dispatch) |

**Instructions** (`.claude/instructions/`, auto-applied; agents cite, never restate):
`ai-execution-discipline` (verify-before-edit · assumption checks · stop-and-confirm · acceptance-driven done · context budget); `python-repo-conventions` (Agg purity · typed→422 · deterministic offline tests · gate is the contract · no secrets/bundles).

**Skills** (`.claude/skills/<name>/`): `add-render-mode` (new mode/param across core→access→GUI→tests→docs);
`expose-op` (core fn → MCP tool + REST route returning PNG + 422 boundary + tests); `run-quality-gate`
(pytest+coverage + core-import + pyplot/Qt purity grep); `build-release` (PyInstaller build + verify excludes in the frozen bundle).

**Hooks** (`.claude/settings.json` + `.claude/hooks/`, native PreToolUse/PostToolUse on `Edit|Write`):
`block_pyplot_qt_in_core` (BLOCK pyplot/Qt/Tk import into core/enums → invariant 1); `block_secrets_and_bundles`
(BLOCK `.env`/keys + `packaging/bin|work` writes → invariant 8); `guard_tkinter_regression` (BLOCK legacy
`MVis_UI`/`MVis_utils`/tkinter re-introduction + Tk-exclude removal → invariant 7); `coverage_gate_reminder`
(advisory: run the gate after core/test edits; flag gate-weakening in `pyproject.toml`).

Backlog of work: `docs/BACKLOG.md` (`MV-B*` bugs, `MV-I*` features, acceptance criteria). Access-layer
operating guide: `docs/agent-operating-doc.md`.

## CRITICAL invariants — never violate
1. **AGG-ONLY HEADLESS CORE.** `map_visualizer/core.py` may import only
   `matplotlib.figure.Figure`, `matplotlib.backends.backend_agg.FigureCanvasAgg`,
   `matplotlib.colormaps`, `matplotlib.colors`, `matplotlib.image`. **Never** `matplotlib.pyplot`;
   **never** Qt/Tk/any interactive backend. Use `Figure.colorbar` (not `pyplot.colorbar`), build
   norms via `matplotlib.colors`, export vectors via `FigureCanvasAgg`/`savefig`. `enums.py` stays
   import-side-effect-free. All Qt code lives under `map_visualizer/gui/` ONLY. A single pyplot/Qt
   import in core silently breaks the PyInstaller bundle and the server — the worst regression here.
2. **`render()` returns valid bytes** — PNG by default (magic `\x89PNG\r\n\x1a\n`); a requested
   vector format returns valid `<?xml`/`<svg` or `%PDF` bytes.
3. **Render math is shared, not duplicated** — it lives in core behind the `draw_*` Axes helpers;
   the GUI calls the same helpers.
4. **Loader hardening preserved** — ragged / empty / all-NaN / oversize (`max_cells`) inputs raise
   the typed errors (`GridLoadError`, `GridValidationError`). Never weaken these guards.
5. **Access-layer errors map to 422** — all four typed core exceptions (`GridLoadError`,
   `GridValidationError`, `InvalidParameterError`, `RenderError`) → HTTP 422 with `{error, message}`;
   the MCP path raises a typed `isError`. No client input may escape to an unhandled HTTP 500.
6. **`max_cells` is server-side and fixed** — clients cannot raise it; a render-time bound is
   additive, never a replacement for the load guard.
7. **PyInstaller excludes stay effective** — `tkinter`, `backend_tkagg`, `wx`, `gtk`, `PyQt5`,
   `PyQt6`, `PySide2` remain excluded from the bundle.
8. **Never commit secrets or built bundles** — no keys/tokens/`.env`; `packaging/bin/` and
   `packaging/work/` stay out of VCS. Commit only on the **enhancement branch**, never main/master.

## Gate commands (run before calling any code change done)
```bash
# Full suite + >=90% core-coverage gate (gui/* and api/* omitted; configured in pyproject.toml)
python -m pytest

# Re-assert the headless invariant directly after a risky core edit
python -c "import map_visualizer.core; print('core imports clean')"
```
A `--cov-fail-under` failure or a non-zero exit means the change is NOT done. **Never** lower
`--cov-fail-under` or widen the coverage `omit` list to make the gate pass — that voids the repo's
regression contract.

## Working discipline (anti-literal-execution)
- **Verify before you edit.** Read the exact code region before changing it; never edit from memory.
  Grep/Glob to find real symbols and call sites first.
- **Confirm before irreversible actions.** File deletion/relocation, `git rm`, and dependency-pin
  changes get a stop-and-confirm (and a Grep proving no importer is broken) first.
- **Acceptance-driven done.** An item is done when its `docs/BACKLOG.md` acceptance criterion is
  proven by a passing test and a green gate — not when an edit applied or one test happened to pass.
- **Minimal change.** Implement only what the item requires; do not opportunistically refactor.
- **Don't invent facts** (versions, APIs, flags) — surface a RESEARCH REQUEST instead.

## Entry points
- GUI: `map-visualizer-gui` (`map_visualizer.gui.app:main`).
- Access layer (install `map-visualizer[api]` first): REST/HTTP `map-visualizer-api`
  (`map_visualizer.api.main:run_server`); MCP stdio `map-visualizer-mcp`
  (`map_visualizer.api.mcp_server:run_stdio`).
- Python: `>=3.11,<3.14`.

## Principles Applied
- P1 Source-of-Truth Grounding — every invariant and command traces to `pyproject.toml`,
  `map_visualizer/core.py`, the access layer, and the review/backlog; no invented conventions.
- P4 Consistency — the same invariant list and gate the operator/maintainer assets enforce, stated
  once here as the shared contract.
- P6 Self-Containment — the file is self-contained; detailed procedures are referenced (not
  restated) to their owning assets (`docs/BACKLOG.md`, the two agents, `docs/agent-operating-doc.md`).
- P7 Reference Hygiene — every referenced path exists in the repo; no restatement of the agents' own
  rules, only the shared invariants and commands.

## Sources
- `pyproject.toml` (coverage gate, deps, entry points, Python band).
- `map_visualizer/core.py`, `map_visualizer/enums.py`, `map_visualizer/api/{service,rest,mcp_server}.py`
  (headless core, typed exceptions, 422 mapping).
- `docs/review-map-visualizer.md` (verified invariants + defect escapes), `docs/BACKLOG.md` (work items).
- `.claude/agents/map-visualizer-operator.md`, `.claude/agents/map-visualizer-maintainer.md`.
