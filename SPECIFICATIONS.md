# Map-Visualizer — PRODUCT SPECIFICATIONS

Prioritized capability + robustness backlog for Map-Visualizer (Python 3 / matplotlib Agg headless
render core + PySide6 GUI; a 2D scalar-field / heatmap visualizer). This file is the product backlog
the repo's own SDD pipeline (feature-enhancer -> access-layer-builder -> packaging -> testing -> docs)
consumes to IMPLEMENT. It is NOT about the `.claude` orchestration vocabulary.

Each spec is concrete and testable: Priority (P1/P2/P3), Motivation, Scope, Acceptance criteria
(testable bullets), Notes/Dependencies. Grouped by theme. Highest-leverage themes first
(centralized widget-info popup, access layer, render robustness).

## Standing invariants (apply to EVERY spec)
- **Pyplot-free headless-core invariant.** The render core (`core/`) MUST construct
  `matplotlib.figure.Figure` + `matplotlib.backends.backend_agg.FigureCanvasAgg` explicitly and NEVER
  import `matplotlib.pyplot` nor any Qt symbol. A `block_pyplot_qt_in_core` guard (test/import-time
  check) MUST fail if `pyplot`, `PySide6`, or `tkinter` appear in any `core/` module. Source:
  research-matplotlib-agg-best-practices.md §2 [S3][S4].
- **Core-extraction precondition.** A pure, UI-independent core (`load_array`, `array_stats`,
  `render_map`, `list_colormaps`, `list_interpolations`) is the critical-path prerequisite; the GUI,
  access layer, packaging, and tests all consume it. (understanding-map-visualizer.md, opportunity #1.)
- **Version pins (campaign-fixed).** `matplotlib>=3.11,<3.12`, `numpy>=1.25`, Python 3.11–3.13.
  Source: research §1 [S1][S2].
- **Single capability.** The domain is read/compute-only 2D-array visualization — no writes, no
  network, no statefulness. Keep all surfaces side-effect-free.

---

## Theme A — UX / Centralized widget-info pop-up

### SPEC-01 Centralized widget-info pop-up (single component, registry-driven)
- **Priority:** P1
- **Motivation:** Replicate the FF-Explorer reference pattern (reference-ff-widget-popup.md): exactly
  ONE centralized info surface for the whole GUI, fed by a single widget->info registry — no scattered
  or ad-hoc per-widget popups. The legacy Tk app hand-rolled tooltips/`Toplevel`; the PySide6 port must
  delete that in favor of the framework singleton + registry (ref §1 history note).
- **Scope:** In the PySide6 GUI (`gui/`): use Qt's framework-managed `QToolTip` singleton as the one
  info surface. Author NO bespoke popup/tooltip/info class. Centralize all info text in ONE
  module-level registry (`_HELP_*` constants or a `dict[str,str]` keyed by stable widget id). Provide a
  single `attach_info(widget, key)` / `register_info(widget, key)` helper that sets BOTH the tooltip
  AND the accessible description from that one registry. Style the surface in ONE QSS block
  (`QToolTip { ... }`) themed from the active `Theme` (one theming point). Support state-driven dynamic
  text (e.g. colormap/mode-dependent help looked up from the registry), mirroring the reference's
  `_update_action_tooltip` pattern.
- **Acceptance criteria:**
  - Grep of `gui/` finds zero `class *Popup` / `class *Tooltip` / `class *Info` and zero tooltip
    `eventFilter`/`QHelpEvent`/`event()` overrides — only `setToolTip`/`register_info` calls.
  - Every interactive widget's info text resolves through the single registry; a test asserts NO inline
    string literal is passed to `setToolTip(...)` (all go via `register_info(widget, key)`).
  - Exactly one `QToolTip { ... }` QSS rule exists, emitted by the theme module; changing
    `Theme.tooltip_bg`/`tooltip_text` (light/dark) restyles every tooltip with no other edit.
  - Hover over any registered widget shows the singleton tooltip near the cursor; it auto-dismisses on
    mouse-leave/timeout (framework default, no app dismiss code).
  - A coverage test (`register_info` helper) enumerates interactive widgets and asserts each has a
    non-empty registry-backed info key — fails if any control lacks info.
- **Notes/Dependencies:** Reference = reference-ff-widget-popup.md (FF-Explorer, PySide6 binding §5).
  Mandate the reference's improvement gaps (ref §6): ALL text in one registry (no inline literals; gap
  1); accessibility — set `setAccessibleDescription()` + optional `setWhatsThis()` and a keyboard/focus
  trigger or `?` help affordance, not hover-only (gap 2); a uniform `register_info` coverage helper
  asserted in tests (gap 3); prefer rich-text/word-wrapped tooltips over manual `\n` (gap 4); no
  per-widget inline `setStyleSheet` that fights the central theme (gap 5); centralize dismiss/delay
  (gap 6). Depends on the PySide6 migration (SPEC-13).

### SPEC-02 Keyboard/focus + help-affordance info trigger (accessibility)
- **Priority:** P2
- **Motivation:** Reference gap 2 — hover-only tooltips are invisible to keyboard-only and
  screen-reader users.
- **Scope:** Extend SPEC-01's centralized component so info is reachable without a mouse: show the
  registry text on keyboard focus and/or via a global `?`/WhatsThis affordance and `Shift+F1`.
- **Acceptance criteria:**
  - Tabbing focus onto a registered widget exposes its info (via accessible description and/or a
    focus-triggered tooltip) — verifiable through `QWidget.accessibleDescription()` equality with the
    registry value in a test.
  - A WhatsThis/`?` mode surfaces the same registry text for every registered widget.
  - No second registry or second info surface is introduced (still one component, one registry).
- **Notes/Dependencies:** Builds on SPEC-01; same single registry.

---

## Theme B — Access Layer (REST + MCP over the headless Agg core)

### SPEC-03 Pure headless render core (`core/`) — extraction
- **Priority:** P1
- **Motivation:** No UI-independent render path exists today; rendering mutates live Tk/mpl artists
  (understanding R-4). This blocks the access layer, tests, packaging, and the PySide6 port.
- **Scope:** Create `core/visualizer.py` (pyplot-free) exposing: `load_array(path) -> ndarray`,
  `array_stats(array_or_path) -> dict` (min, max, shape, nan_count, suggested sci exponent),
  `render_map(array_or_path, *, value_range=None, color_range=None, cmap='viridis',
  interpolation='nearest', mode='heatmap', figsize=(6.4,4.8), dpi=100) -> bytes` (PNG via Agg),
  `list_colormaps() -> list[str]`, `list_interpolations() -> list[str]`. Value/color-range clamp math
  ported from `map_range`/`map_colorange`; `sci_exp` reused.
- **Acceptance criteria:**
  - `block_pyplot_qt_in_core` guard passes: no `pyplot`/`PySide6`/`tkinter` import anywhere in `core/`.
  - `render_map` returns non-empty PNG bytes with no display/window and no files written.
  - `load_array` returns correct shapes for all four example fixtures (3x5, 1xN row, Nx1 column, `.dat`).
  - Colormap access uses `matplotlib.colormaps[name]` / `.get_cmap(...)`, NOT the removed
    `matplotlib.cm.get_cmap` (research §5 [S6][S7]).
- **Notes/Dependencies:** Prerequisite for SPEC-04..06, SPEC-10..12, SPEC-13. Source: understanding
  opportunity #1, access-layer candidates §; research §2 [S3].

### SPEC-04 REST interface (FastAPI) over `render_map`
- **Priority:** P1
- **Motivation:** Expose the headless render capability programmatically (R5 dual interface).
- **Scope:** A FastAPI app wrapping the core (NOT the GUI): `POST /render` (-> PNG/base64),
  `GET /colormaps`, `GET /interpolations`, `POST /stats`. Accepts array (uploaded file or inline
  numeric grid) + render params. Async handler offloads the synchronous render to a worker
  (`run_in_executor`) so the event loop never blocks (research §4).
- **Acceptance criteria:**
  - `POST /render` returns HTTP 200 with `image/png` (or base64 JSON) for a valid grid; bytes decode to
    a valid PNG of the requested `figsize*dpi` pixel dimensions.
  - `GET /colormaps` / `GET /interpolations` return the same lists as the core enumerations.
  - Invalid input (ragged/empty/non-numeric) returns a structured 4xx with a diagnostic message, never
    a 500 stack-leak or a hang.
  - The app imports the core only; importing the FastAPI module does not import `PySide6`/`tkinter`.
- **Notes/Dependencies:** Depends on SPEC-03, SPEC-15 (validation), SPEC-18 (thread-safe render).

### SPEC-05 MCP interface (FastMCP) over the same core service
- **Priority:** P1
- **Motivation:** R5 single-core/dual-interface — expose the curated minimal toolset to MCP clients.
- **Scope:** A FastMCP server exposing tools `load_array`, `array_stats`, `render_map` (primary;
  carries the `mode` render-mode selection), `list_colormaps`, `list_interpolations`, backed by the
  SAME core service module as REST (no duplicated logic). Python ceiling 3.13 (FastMCP cap).
- **Acceptance criteria:**
  - Each tool is discoverable with a typed schema and a one-line description.
  - `render_map` over MCP returns PNG bytes/base64 identical to the REST path for identical inputs
    (shared core, deterministic output per SPEC-17).
  - Tool count stays minimal/curated (5 read/compute tools, no write/stateful tools).
- **Notes/Dependencies:** Depends on SPEC-03; shares the service module with SPEC-04.

### SPEC-06 Shared core-service module (single source for REST + MCP)
- **Priority:** P2
- **Motivation:** Prevent logic drift between the two interfaces (dossier F1/F2: one core, dual
  interface).
- **Scope:** A thin service layer both adapters import; request validation, param normalization, and
  error mapping live here once.
- **Acceptance criteria:**
  - Removing/altering a core function changes both interfaces identically (a contract test asserts REST
    and MCP `render_map` produce byte-identical output for a fixed input set).
  - No business/validation logic is duplicated in the REST or MCP adapter modules.
- **Notes/Dependencies:** Depends on SPEC-03/04/05.

---

## Theme C — Packaging

### SPEC-07 Dependency manifest + build backend
- **Priority:** P1
- **Motivation:** No manifest exists (understanding: declared deps NONE). R2.c needs pinned deps and a
  Python floor.
- **Scope:** Add `pyproject.toml` (PEP 621) with metadata, single-sourced version, console/GUI entry
  point, and `requirements.txt`. Pin `matplotlib>=3.11,<3.12`, `numpy>=1.25`; declare
  `requires-python = ">=3.11,<3.14"`. Optional extras: `[gui]` (PySide6), `[server]` (fastapi, fastmcp).
- **Acceptance criteria:**
  - A clean venv install from the manifest yields a runnable app and importable core.
  - Version is single-sourced (one location), not a literal duplicated in source.
  - `requires-python` rejects <3.11 and >=3.14.
- **Notes/Dependencies:** Research §1 [S1][S2]. Resolves understanding R2.c.

### SPEC-08 Cross-platform PyInstaller executable
- **Priority:** P2
- **Motivation:** R3 — deliver a packaged executable; `.gitignore` already anticipates PyInstaller but
  nothing is wired.
- **Scope:** A PyInstaller spec building a `--windowed`/`--noconsole` GUI binary. Bundle `Logo MVis.png`
  via `datas`/`--add-data`; validate matplotlib + numpy hooks (collect backend data files). Resolve all
  resource paths through a `sys._MEIPASS`-aware helper.
- **Acceptance criteria:**
  - Built binary launches the GUI from any working directory (not only the repo dir) and loads its icon.
  - matplotlib renders inside the frozen bundle (no missing-backend/data error).
  - Example `.txt`/`.dat` fixtures are NOT bundled (demo only).
- **Notes/Dependencies:** Depends on SPEC-09 (resource-path fix) and SPEC-13 (PySide6 GUI). Source:
  understanding packaging gaps.

### SPEC-09 Resource-path robustness (`__file__`/`_MEIPASS`, not `os.getcwd()`)
- **Priority:** P1
- **Motivation:** R-1 — `__rootf__ = os.getcwd()` breaks when launched outside the repo dir and in a
  frozen bundle.
- **Scope:** Replace `os.getcwd()` icon/resource resolution with a `resource_path(name)` helper that
  uses `sys._MEIPASS` when frozen else `os.path.dirname(__file__)`.
- **Acceptance criteria:**
  - Launching from an arbitrary cwd loads the icon and any bundled resource.
  - A unit test asserts `resource_path` resolves correctly under both frozen and source layouts.
- **Notes/Dependencies:** Precondition for SPEC-08.

---

## Theme D — Testing

### SPEC-10 pytest suite + coverage gate
- **Priority:** P1
- **Motivation:** Zero tests today (understanding: NONE). R4 requires a coverage gate.
- **Scope:** `pytest` + `pytest-cov` targeting the extracted core (exclude the Tk/Qt UI layer). Unit
  tests for `load_array` (3x5, 1xN, Nx1, `.dat`, malformed/ragged/empty/all-NaN), `sci_exp` across
  decades, value/color range clamp math, `list_colormaps`/`list_interpolations`.
- **Acceptance criteria:**
  - `pytest` runs headless in CI with no display.
  - Coverage of `core/` meets the campaign coverage gate; the run fails below threshold.
  - Malformed/ragged/empty/all-NaN inputs are asserted to raise/return defined errors, not silent
    sentinels.
- **Notes/Dependencies:** Depends on SPEC-03, SPEC-15.

### SPEC-11 Agg render-to-image smoke tests (per mode)
- **Priority:** P1
- **Motivation:** Verify headless rendering works for every render mode without a display.
- **Scope:** For each `mode` (heatmap, contour/contourf, 3D surface, histogram, row/column profile) a
  smoke test calls `render_map(..., mode=...)` and asserts valid PNG output. Compare via
  tolerance-based decoded-RGBA array (robust to sub-pixel AA across platforms) rather than exact bytes.
- **Acceptance criteria:**
  - Each mode produces a decodable PNG of the expected pixel dimensions.
  - A representative fixture renders within a tolerance of a stored baseline RGBA array.
  - Tests pass under the Agg backend with no GUI/display available.
- **Notes/Dependencies:** Research §6 [S11], §7 [S9][S3]. Depends on SPEC-14, SPEC-17.

### SPEC-12 Determinism + thread-safety tests
- **Priority:** P2
- **Motivation:** Lock in the robustness guarantees (SPEC-17, SPEC-18) with executable checks.
- **Scope:** A test renders the same input twice and asserts byte-identical PNG (metadata stripped); a
  concurrency test fires N parallel `render_map` calls and asserts no crash/segfault and correct output.
- **Acceptance criteria:**
  - Two renders of one fixed input produce identical PNG bytes after metadata stripping.
  - Concurrent renders (threadpool) complete without race/segfault and each returns a valid image.
- **Notes/Dependencies:** Research §3/§4/§7. Depends on SPEC-17, SPEC-18.

---

## Theme E — Features (render modes, controls, I/O) — R2.b headline

### SPEC-13 PySide6 GUI migration (Tk -> Qt) reusing the core
- **Priority:** P1
- **Motivation:** Current GUI is Tkinter; campaign target is PySide6. Migration is the host for the
  centralized popup (SPEC-01) and the optimized layout (SPEC-19).
- **Scope:** Port `MVis_UI(Tk)` to a `QMainWindow`, swapping `FigureCanvasTkAgg`/`NavigationToolbar2Tk`
  for the matplotlib Qt backend (`FigureCanvasQTAgg` + `NavigationToolbar2QT`). The GUI calls the
  pure core (SPEC-03) for all load/render logic; no render math remains in the widget layer.
- **Acceptance criteria:**
  - No `tkinter` import remains in the GUI; the app runs as a PySide6 window.
  - All current capabilities preserved: colormap/interpolation selection, value-range + colormap-range
    clamps, live pixel readout, pan/zoom/save toolbar, fullscreen.
  - GUI render paths delegate to `core` functions (verified by absence of mpl-artist mutation in GUI).
- **Notes/Dependencies:** Depends on SPEC-03. Hosts SPEC-01, SPEC-19. Fix copy-paste identity defects
  (R-6: "U Converter"/"FF Explorer" banners, duplicate `rootmin/rootmax`) during the port.

### SPEC-14 Multiple render modes (imshow heatmap, contour/contourf, 3D surface, histogram, profiles)
- **Priority:** P1
- **Motivation:** R2.b headline — only a single `imshow` mode exists today. Add the natural render
  modes for a scalar-field visualizer.
- **Scope:** Extend the core `render_map` `mode` enum: `heatmap` (imshow), `contour`, `contourf`,
  `surface3d` (`add_subplot(projection="3d")` + `plot_surface`), `histogram` (`ax.hist`), `profile_row`
  / `profile_col` (`ax.plot(Z[row,:])` / `Z[:,col]`). All via the pyplot-free OO API. Expose mode
  selection in the GUI and over REST/MCP.
- **Acceptance criteria:**
  - Each mode renders a valid PNG headlessly for a representative grid (see SPEC-11).
  - `contour`/`contourf` accept an explicit `levels` arg; `histogram` accepts explicit `bins`
    (deterministic output).
  - `surface3d` works without an explicit `import mpl_toolkits.mplot3d` (auto-registered, mpl>=3.2).
  - GUI mode selector switches modes live; REST/MCP `mode` param honored.
- **Notes/Dependencies:** Research §6 [S11][S3]. Pin levels/bins/interpolation for SPEC-17. Depends on
  SPEC-03.

### SPEC-15 Data import formats + validation
- **Priority:** P2
- **Motivation:** R-3 — loader relies on `np.loadtxt` defaults only; ragged/empty/all-NaN inputs are
  swallowed (R-2).
- **Scope:** Broaden import beyond whitespace `.txt`/`.dat`: support delimiter sniffing and CSV; add an
  explicit validation step (rectangular shape, finite-value handling, size cap) returning structured
  diagnostics. Keep the existing 1xN/Nx1 reshape behavior.
- **Acceptance criteria:**
  - CSV and whitespace grids both load; delimiter is auto-detected or selectable.
  - Ragged rows raise a specific, message-bearing error (not a generic "invalid map format").
  - All-NaN / empty arrays are rejected with a clear diagnostic; a configurable size cap rejects
    oversized files before a full in-memory `imshow`.
- **Notes/Dependencies:** Feeds SPEC-10 tests, SPEC-16 error handling.

### SPEC-16 Export controls (PNG / SVG / PDF) + colorbar/legend/annotation/title controls
- **Priority:** P2
- **Motivation:** Today the only export is the toolbar's default PNG save; no axis labels/title/legend
  customization (understanding "what is NOT present").
- **Scope:** Add explicit export to PNG, SVG, and PDF from the core (`render_map(format=...)`) and a GUI
  export action. Add colorbar toggle, axis title/labels, and annotation controls surfaced in GUI and as
  render params.
- **Acceptance criteria:**
  - `render_map(format="svg"|"pdf"|"png")` returns valid bytes of the requested format.
  - GUI export writes a file in the chosen format; colorbar/title/labels render when enabled.
  - PDF export strips the `CreationDate` stamp for determinism (research §7 [S10]).
- **Notes/Dependencies:** Depends on SPEC-03/14. Determinism per SPEC-17.

### SPEC-17 Interactive pan/zoom + colormap/interpolation controls (GUI parity+)
- **Priority:** P3
- **Motivation:** Preserve and improve interactivity in the Qt port; colormap/interpolation already
  exist and must carry over.
- **Scope:** Wire the Qt navigation toolbar (pan/zoom/reset/save) and keep colormap + interpolation
  selectors driven by `list_colormaps()`/`list_interpolations()`. Optional multi-layer/overlay compare
  of two arrays.
- **Acceptance criteria:**
  - Pan/zoom/reset operate on the embedded Qt canvas.
  - Colormap and interpolation selectors are populated from the core enumerations and apply live.
  - (If implemented) overlay mode composites two arrays with adjustable alpha.
- **Notes/Dependencies:** Depends on SPEC-13. Lower priority than mode expansion.

---

## Theme F — Robustness

### SPEC-18 Deterministic PNG output
- **Priority:** P1
- **Motivation:** matplotlib injects a `Software`/version+date stamp into PNG metadata, so identical
  figures yield different bytes run-to-run — breaks render smoke tests (research §7 [S9][S10]).
- **Scope:** In `render_map`: fix `figsize`+`dpi`, pass `metadata={"Software": None}` (PNG) /
  `{"CreationDate": None}` (PDF) on save, avoid `bbox_inches="tight"`, and lock numeric axis tick
  formatting (`ax.ticklabel_format(...)`) so offset/scientific-notation drift can't change tick text.
- **Acceptance criteria:**
  - Two renders of one fixed input produce byte-identical PNG (after metadata stripping).
  - No `bbox_inches="tight"` in the render path; pixel dimensions equal `figsize*dpi`.
  - A test asserts tick text is stable across two equivalent renders.
- **Notes/Dependencies:** Research §7. Feeds SPEC-11/SPEC-12.

### SPEC-19 Figure lifecycle / memory (no leaks, no `gc.collect()` cargo-cult)
- **Priority:** P1
- **Motivation:** pyplot's global registry leaks figures; the OO path does not. The legacy `exit()`
  does cargo-cult `del locals()` + `gc.collect()` cleanup (understanding); research §3 debunks
  `gc.collect()` on the OO path.
- **Scope:** Build each render on a per-call `Figure`+`FigureCanvasAgg` with no global registry; rely
  on scope-exit reclamation. Remove all `gc.collect()`/`del self` cargo-cult cleanup. If any pyplot is
  ever unavoidable, wrap in `try/finally: plt.close(fig)`.
- **Acceptance criteria:**
  - No `pyplot`, `plt.figure`, or `gc.collect()` in the render hot-path (guard/grep test).
  - Rendering N images in a loop does not grow live `Figure` count or RSS unboundedly (a memory test
    asserts bounded growth).
  - No `RuntimeWarning: More than 20 figures have been opened` is ever emitted.
- **Notes/Dependencies:** Research §2/§3 [S3][S4][S13].

### SPEC-20 Thread-safe concurrent rendering
- **Priority:** P1
- **Motivation:** matplotlib is not thread-safe; the Agg font cache is class-level and concurrent
  `draw()` is a documented segfault/race risk (research §4 [S4][S5][S14]). The REST/MCP server is
  concurrent.
- **Scope:** Per-request `Figure` (never shared across threads/requests) PLUS a module-level
  `threading.Lock` around the `draw`/`savefig` section, OR a `ProcessPoolExecutor` for true
  parallelism. Async handlers offload the synchronous render via `run_in_executor`.
- **Acceptance criteria:**
  - No `Figure`/canvas is shared across requests (per-request construction verified).
  - The draw/savefig section is serialized by a lock or isolated per-process.
  - A concurrency stress test (N parallel renders) completes with zero crashes and all valid images.
- **Notes/Dependencies:** Research §4. Backs SPEC-04/05; tested by SPEC-12.

### SPEC-21 Structured error handling + logging
- **Priority:** P2
- **Motivation:** R-2 — pervasive bare `except: pass` hides malformed-file/ragged/NaN/clim errors;
  app uses `print` (hidden under `.pyw`), no logging.
- **Scope:** Replace blanket `try/except: pass` in read + render paths with specific exception handling
  that surfaces actionable diagnostics (GUI message + structured API error). Introduce the `logging`
  module (configurable level) in place of `print`.
- **Acceptance criteria:**
  - No bare `except:`/`except Exception: pass` remains in core or read paths (lint/grep test).
  - A malformed/ragged/NaN load yields a specific user-facing message (GUI) and a structured error
    (REST/MCP), each naming the cause.
  - Logging emits at configurable levels; no `print` for diagnostics in core.
- **Notes/Dependencies:** Pairs with SPEC-15. Feeds SPEC-10.

### SPEC-22 Performance on large grids
- **Priority:** P3
- **Motivation:** R-3 — no size cap; a huge file loads fully into memory and a single `imshow`.
- **Scope:** Add a configurable size cap / downsampling for oversized grids before render; cap
  `figsize*dpi` work; document large-grid guidance.
- **Acceptance criteria:**
  - Files above the configured cell-count threshold are rejected or downsampled with a clear notice.
  - A large-grid render completes within a documented time/memory budget on the reference machine.
- **Notes/Dependencies:** Depends on SPEC-15.

### SPEC-23 GUI accessibility (beyond tooltips)
- **Priority:** P3
- **Motivation:** Extend accessibility past the info popup (SPEC-02) to the whole GUI.
- **Scope:** Set accessible names/roles on interactive widgets, ensure full keyboard navigation/tab
  order, and honor the active theme's contrast.
- **Acceptance criteria:**
  - Every interactive widget exposes a non-empty accessible name; tab order reaches all controls.
  - Keyboard-only operation can load a file, change mode/colormap, and export.
- **Notes/Dependencies:** Depends on SPEC-13; complements SPEC-01/02.

---

## Priority summary
- **P1 (10):** SPEC-01, SPEC-03, SPEC-04, SPEC-05, SPEC-07, SPEC-09, SPEC-10, SPEC-11, SPEC-13,
  SPEC-14, SPEC-18, SPEC-19, SPEC-20.
- **P2 (7):** SPEC-02, SPEC-06, SPEC-08, SPEC-12, SPEC-15, SPEC-16, SPEC-21.
- **P3 (4):** SPEC-17, SPEC-22, SPEC-23.

(Counts: P1 = 13, P2 = 7, P3 = 3; total 23.)

## Suggested implementation order (SDD pipeline)
1. SPEC-03 core extraction (unblocks everything) -> SPEC-09 resource path.
2. SPEC-18/19/20 render robustness (deterministic, no-leak, thread-safe core).
3. SPEC-04/05/06 access layer (REST + MCP over the core).
4. SPEC-07/08 packaging.
5. SPEC-10/11/12 testing (coverage gate + render smoke + determinism/concurrency).
6. SPEC-13 PySide6 migration -> SPEC-01/02 centralized popup -> SPEC-14/15/16/17 feature expansion.
7. SPEC-21/22/23 remaining robustness/accessibility.
