# Improvement Backlog — Map-Visualizer

- Repo slug: `map-visualizer`
- Working copy: `D:\Documentos\GitHub\Map-Visualizer`
- Enhancement branch: `enhancement/map-visualizer-20260612`
- Author: the-recommender (planning only — repo NOT modified). Date: 2026-06-13.
- Grounding: `docs/review-map-visualizer.md` (bugs), `docs/research-competitive-map-visualizer.md`
  (features), `docs/understanding-map-visualizer.md` (repo context).
- Hard invariant for every item: **KEEP THE CORE HEADLESS** — `map_visualizer/core.py` may import
  only `matplotlib.figure.Figure` + `matplotlib.backends.backend_agg.FigureCanvasAgg` (Agg). No
  `matplotlib.pyplot`, no Qt/Tk/backend leakage in core. GUI-only code stays under `map_visualizer/gui/`.
- "Asset capability needed:" tags name the generation-agent capability the orchestrator must exercise
  to deliver the item (edit headless render core / add render mode / add MCP tool + REST route /
  regenerate PyInstaller spec / add pytest cases / edit GUI / edit docs / gitignore+repo hygiene).

Asset-capability vocabulary used below (distinct tags):
`edit headless render core`, `add render mode (headless core)`, `add MCP tool + REST route returning PNG`,
`extend existing REST/MCP render params`, `add Pydantic boundary validator (REST/service)`,
`add pytest cases`, `fix/replace pytest case`, `edit PySide6 GUI`, `regenerate PyInstaller spec`,
`gitignore + repo hygiene`, `edit docs / README`, `update dependency manifest`.

================================================================================
## SECTION 1 — BUGS & FIXES (ordered by severity)
================================================================================

Severity order: CRITICAL > HIGH > MEDIUM > LOW. There are no CRITICAL functional bugs (the headless
core invariant holds per review §B). The two routing regressions (B1/B2) and the malformed-range 500
(C1) are the headline correctness escapes and lead the list.

---

### MV-B01 — Single-column file loads as a single ROW (shape regression)
- Severity: **HIGH** (silent data-shape corruption; locked in by a test).
- File:line: `map_visualizer/core.py:220-224` (reshape `(1, -1)`); test that cements it:
  `tests/test_core.py:155-163` (`test_1d_single_column_promoted`).
- Root cause: `np.loadtxt` flattens an N-line / one-number-per-line file to a 1-D array of length N.
  `load_array` then unconditionally reshapes ANY 1-D result to `(1, -1)`, yielding `(1, N)`. The
  original app and `example column.txt` treat that input as an N×1 column. The inline comment at
  `core.py:223-224` ("a single-column file loads as (N,1) naturally") is factually wrong for the
  one-number-per-line case.
- Fix approach: distinguish a single-column input from a single-row input before reshaping. For the
  text-file path, detect line count: if the source produced N physical numeric lines each with exactly
  one token, reshape to `(N, 1)`; if one physical line with N tokens, reshape to `(1, N)`. Practical
  implementation: read raw text and count rows/tokens (or pass `ndmin=2` to `np.loadtxt` so it
  preserves 2-D shape, then only promote genuine 0-D/1-D scalars). Preserve existing `(1, N)` behavior
  for true single-row inputs (do not break MV-B02's contract). Fix the misleading comment.
- Acceptance criterion: loading `example column.txt` (5 lines, one number each) yields
  `array.shape == (5, 1)`; loading `example row.txt` (`4 7 1 2 3`) yields `(1, 5)`. A pytest case
  asserts both shapes; the old `test_1d_single_column_promoted` is replaced (see MV-B03).
- Asset capability needed: **edit headless render core** + **fix/replace pytest case**.

---

### MV-B02 — Single-row whitespace text misclassified as a file path
- Severity: **HIGH** (breaks the documented inline-text contract for 1×N grids over the access layer).
- File:line: `map_visualizer/core.py:155-159` (`is_path = os.sep in source or altsep in source or "\n"
  not in source`).
- Root cause: the path-vs-text heuristic treats any `str` with **no newline** as a filesystem path. A
  legitimate single-row inline grid like `"4 7 1 2 3"` has no `\n` → routed to the path branch → fails
  the `.txt/.dat` extension check → `GridLoadError`. The access layer therefore cannot accept a 1×N
  grid in whitespace-text form (the JSON `[[...]]` form still works, masking the break).
- Fix approach: stop using "absence of newline" as the path signal. Decide by content/intent instead:
  (a) treat the string as a path only when it has no interior whitespace-separated numeric tokens AND
  ends with an allowed extension (`.txt`/`.dat`) or resolves to an existing file; otherwise (b) treat
  it as inline text. Equivalently, attempt a cheap numeric-token parse first; if it parses to numbers,
  it is inline text. Keep the existing inline-text parsing path for multi-row text unchanged.
- Acceptance criterion: `load_array("4 7 1 2 3")` returns shape `(1, 5)` with values `[4,7,1,2,3]`
  (no `GridLoadError`); existing file-path loads (`example.txt`, `example.dat`) still succeed. New
  pytest case asserts the single-row inline-text path.
- Asset capability needed: **edit headless render core** + **add pytest cases**.

---

### MV-B03 — Test suite documents the single-column regression instead of catching it
- Severity: **HIGH** (test-debt that actively locks in MV-B01; must change with the fix).
- File:line: `tests/test_core.py:155-163` (`test_1d_single_column_promoted` asserts `(1, 3)`).
- Root cause: the test encodes the buggy behavior (`shape == (1, 3)`) as the expected contract, so any
  correct fix to MV-B01 would "fail" this test and be reverted. No test loads `example column.txt` and
  expects N×1.
- Fix approach: replace `test_1d_single_column_promoted` with two correct cases — one asserting an
  N-line single-column file/text loads as `(N, 1)`, one asserting a single-row input loads as `(1, N)`.
  Add a direct `example column.txt` round-trip case expecting `(5, 1)`.
- Acceptance criterion: the renamed/added tests pass against the MV-B01 fix and fail against the old
  reshape logic; no remaining test asserts `(1, N)` for a single-column input.
- Asset capability needed: **fix/replace pytest case**.

---

### MV-B04 — Malformed `value_range`/`color_range` escapes the 422 mapping → HTTP 500
- Severity: **MEDIUM** (input-validation boundary escape; wrong status class, not a crash of the core).
- File:line: `map_visualizer/api/service.py:248-253` (indexes `[0]`/`[1]` and `float()`-casts the
  client range *before* the try/except domain); catch set at `map_visualizer/api/rest.py:333`.
- Root cause: a client-supplied `value_range`/`color_range` of the wrong length (e.g. `[5]` →
  `IndexError`, `[1,2,3]` → extra element ignored or mis-shaped) or with a non-numeric element
  (`ValueError`) is dereferenced before the domain-exception guard. Neither `IndexError` nor a bare
  `ValueError` is in the `(GridLoadError, GridValidationError, InvalidParameterError, RenderError)`
  catch set, so it propagates as an unhandled **HTTP 500** instead of a 422. Pydantic types the field
  as `list[float]` (catching non-numeric) but does **not** enforce length-2, so `[5]`/`[1,2,3]` reach
  the service and 500.
- Fix approach: enforce the shape at the boundary. Preferred: add a Pydantic validator on the render
  request model constraining `value_range`/`color_range` to exactly two finite floats (e.g.
  `conlist(float, min_length=2, max_length=2)` or a `field_validator`). Defense-in-depth: in the
  service, raise `InvalidParameterError` (already mapped to 422) when the range is not length-2 or not
  numeric, BEFORE the `[0]`/`[1]` dereference. Ensure the 422 body keeps the structured `{error,
  message}` shape.
- Acceptance criterion: `POST /render` with `value_range:[5]`, `value_range:[1,2,3]`, or
  `color_range:["a","b"]` returns **HTTP 422** (not 500) with `{error, message}`; the MCP path raises
  a typed error (`isError`), not an unhandled exception. pytest cases assert 422 for each malformed
  shape.
- Asset capability needed: **add Pydantic boundary validator (REST/service)** + **add pytest cases**.

---

### MV-B05 — Inverted `value_range`/`color_range` bounds not order-validated
- Severity: **MEDIUM** (silent misrender or confusing matplotlib error; robustness gap).
- File:line: `map_visualizer/core.py:332-353` (`apply_value_range`); `_render_heatmap` /
  `_render_contour` color_range paths (`core.py:656-671, 695-696`).
- Root cause: a caller passing `color_range=(10, 0)` or `value_range` with vmin>vmax is passed straight
  to `np.where`/matplotlib `set_clim`; no `InvalidParameterError` is raised. Result is an upside-down
  scale or an opaque matplotlib error rather than a typed 422.
- Fix approach: in `apply_value_range` and the color_range application points, validate `vmin < vmax`
  (allow equal only if intentionally supported; otherwise reject equal too) and raise
  `InvalidParameterError` with a clear message on violation. The REST/MCP layers already map
  `InvalidParameterError` → 422, so no access-layer change is needed beyond surfacing it.
- Acceptance criterion: rendering (core or via `/render`) with `value_range=(10,0)` or
  `color_range=(10,0)` raises `InvalidParameterError` (core) / returns **422** (REST); a valid
  ascending range still renders. pytest cases cover both core and REST.
- Asset capability needed: **edit headless render core** + **add pytest cases**.

---

### MV-B06 — Non-finite stats serialized as non-standard `NaN` JSON token
- Severity: **LOW** (interop defect; strict JSON clients reject the response).
- File:line: `map_visualizer/core.py:289-290` (`array_stats` `min`/`max` via plain `np.min/np.max`);
  surfaced by `/stats` (and `/render?format=base64` stats block) in `api/rest.py`.
- Root cause: `min`/`max` use plain `np.min/np.max`, so a partial-NaN grid yields `min=NaN`/`max=NaN`.
  FastAPI/Starlette's default encoder emits the non-standard `NaN` literal, which strict JSON parsers
  reject.
- Fix approach: coerce non-finite stat values to JSON `null` at the serialization boundary (preferred:
  in the response model / service mapping, so the core keeps returning float math). Alternatively, have
  `array_stats` return `None` for non-finite `min`/`max`. Keep `nanmin`/`nanmax` as the NaN-aware
  values (do not change their semantics). Document that `min`/`max` are raw (NaN-propagating) while
  `nanmin`/`nanmax` ignore NaN.
- Acceptance criterion: `/stats` on a partial-NaN grid returns `"min": null` / `"max": null` (valid
  JSON, parses under a strict parser); `nanmin`/`nanmax` remain finite numbers. pytest asserts the
  response is strict-JSON-parseable and `min`/`max` are `null`.
- Asset capability needed: **edit headless render core** (or response model) + **add pytest cases**.

---

### MV-B07 — Frozen PyInstaller bundle committed to the branch (not gitignored)
- Severity: **LOW** (repo hygiene; large binaries in VCS, no functional impact).
- File:line: `packaging/bin/` and `packaging/work/` (committed); `.gitignore` lists only `build/` /
  `dist/`.
- Root cause: the full frozen bundle (numpy/matplotlib/PySide6 binaries under
  `packaging/bin/MapVisualizer/_internal`) plus PyInstaller work dir are committed and not covered by
  `.gitignore`.
- Fix approach: add `packaging/bin/` and `packaging/work/` to `.gitignore`; remove the committed
  bundle from the branch (`git rm -r --cached`). Confirm the packaging spec still builds them locally.
- Acceptance criterion: `packaging/bin/` and `packaging/work/` are gitignored and absent from `git
  status`/tracked files on the branch; `git ls-files packaging/` lists only the spec + readme, not the
  frozen binaries.
- Asset capability needed: **gitignore + repo hygiene** (orchestrator dispatch; packaging agent may
  re-emit the spec/ignore rules).

---

### MV-B08 — Access layer has no auth / size / rate limit and it is undocumented
- Severity: **LOW** (acceptable for a local compute-only tool, but the security posture is undocumented).
- File:line: `map_visualizer/api/rest.py` (no auth middleware, no request-size/rate limit);
  `core.py:54` (`DEFAULT_MAX_CELLS` ~16.7M cells → a single render can pull ~128MB + a full mpl render).
- Root cause: the service exposes five compute endpoints with no authentication and no per-request size
  or rate limiting. The `max_cells` cap bounds a single render but the bound is large; the posture is
  not written down anywhere.
- Fix approach: do NOT add auth in this campaign (out of scope; would change the contract). Instead add
  an explicit deploy/security note in `api/README-access.md` stating: no auth (bind to localhost / use
  a reverse proxy for remote exposure), the server-side `max_cells` cap (and that clients cannot raise
  it), and the absence of rate limiting. Optionally note a recommended reverse-proxy size limit.
- Acceptance criterion: `api/README-access.md` contains a "Security / deployment" section documenting
  no-auth, the fixed `max_cells` cap, and no rate limiting, with a localhost-bind recommendation.
- Asset capability needed: **edit docs / README**.

---

### MV-B09 — Stale legacy Tkinter files remain at repo root
- Severity: **LOW** (confusion risk about the real entry point; dead code).
- File:line: repo root `MVis_UI.pyw`, `MVis_utils.py` (original Tkinter app, superseded by
  `map_visualizer/` package).
- Root cause: the original flat-layout Tkinter app was left in place after the package refactor; both
  the new `map_visualizer/` package and the dead originals coexist.
- Fix approach: remove `MVis_UI.pyw` and `MVis_utils.py` (and the stray `__pycache__/
  MVis_utils.cpython-311.pyc`) from the branch, OR move them under a clearly marked `legacy/` dir with a
  README note. Confirm nothing in the package, tests, packaging spec, or docs imports them first.
- Acceptance criterion: no module under `map_visualizer/`, `tests/`, `api/`, or `packaging/` references
  `MVis_UI`/`MVis_utils`; the originals are removed or relocated under `legacy/` with a note; README
  names `map_visualizer.gui.app` (Qt) as the sole desktop entry point.
- Asset capability needed: **gitignore + repo hygiene** + **edit docs / README**.

---

### MV-B10 — Dependency pins not yet revalidated as published/stable
- Severity: **LOW** (release-readiness, not a functional defect; flagged, not blocking).
- File:line: `pyproject.toml:18-22` (`numpy~=2.4.6`, `matplotlib~=3.11.0`, `PySide6~=6.11.1`).
- Root cause: the pins were chosen during enhancement; their published/stable status against the
  campaign Python band (3.11–3.13, FastMCP ceiling 3.13) was flagged for revalidation
  (the-researcher Q4) but not confirmed in the review.
- Fix approach: this is a **RESEARCH REQUEST**, not a code fix — see the embedded request below. Once
  the researcher confirms current stable versions compatible with Python 3.11–3.13 + FastMCP, update
  the pins in `pyproject.toml` (and the packaging build env) accordingly, or record that the current
  pins are confirmed.
- Acceptance criterion: `pyproject.toml` pins are either confirmed-current with a cited note, or
  updated to the researcher's recommended stable versions; the packaging build still succeeds with the
  resolved versions.
- Asset capability needed: **update dependency manifest** (after research) + **regenerate PyInstaller
  spec** if a pin changes the bundle.

  > RESEARCH REQUEST (for the-researcher, routed by orchestrator):
  > Confirm current stable, published versions of `numpy`, `matplotlib`, and `PySide6` compatible with
  > CPython 3.11–3.13 and FastMCP (ceiling 3.13). Validate that `numpy~=2.4.6`, `matplotlib~=3.11.0`,
  > `PySide6~=6.11.1` are real published releases or supply the nearest stable pins. Cite PyPI / release
  > notes. (F-series revalidation; review §D pyproject note.)

================================================================================
## SECTION 2 — IMPROVEMENTS & FEATURES (ordered by value/effort)
================================================================================

Ordering principle: highest (value ÷ effort) first. Value ∈ {HIGH, MED, LOW}; Effort ∈ {S, M, L}.
The first cluster (norm + colorbar + colormap guidance + contour labels) is the
"correctness-of-color / analysis-readout" cluster the research synthesis ranks highest for a
headless 2-D visualizer, and it maps cleanly onto MCP/REST parameters.

All core work obeys the headless invariant: render math lives in `map_visualizer/core.py` behind the
shared `draw_*` Axes helpers and the Agg `render()` path; the PySide6 GUI calls the same helpers.

---

### MV-I01 — Log / SymLog / Power colormap normalization
- Value: **HIGH** · Effort: **M**
- What it adds: a `norm` choice (linear / log / symlog / power) so dynamic-range data renders
  correctly. Log for strictly-positive data spanning orders of magnitude; SymLog (params `linthresh`,
  `linscale`) for mixed +/- data; Power (param `gamma`).
- Why: the single highest-value adoption in the research — linear norm crushes order-of-magnitude data
  and is the most common scientific-viz correctness defect; it composes with vmin/vmax and the colorbar
  (MV-I03).
- Reference tool: matplotlib colormap normalization.
  Citation: https://matplotlib.org/stable/users/explain/colors/colormapnorms.html
- Modules/files touched: `map_visualizer/core.py` (build `matplotlib.colors.{Normalize,LogNorm,
  SymLogNorm,PowerNorm}` from a `norm` enum + params; apply in `_render_heatmap`/`_render_contour`);
  `map_visualizer/enums.py` (add `NormMode` enum); `map_visualizer/api/service.py` + `api/rest.py`
  (accept `norm`, `linthresh`, `linscale`, `gamma`); `map_visualizer/gui/main_window.py` (norm selector
  widget); `tests/test_core.py` + `tests/test_api.py`.
- Rough approach (CORE HEADLESS): add a pure `build_norm(norm_mode, vmin, vmax, *, linthresh,
  linscale, gamma) -> matplotlib.colors.Normalize` helper in core (imports only `matplotlib.colors`,
  already used at `core.py:729`). Wire it into the heatmap/contour draw helpers so the same norm feeds
  both the Agg render and the Qt UI. Validate: log requires data>0 (raise `InvalidParameterError` for
  non-positive on `LogNorm`); symlog requires `linthresh>0`. Expose `norm` as an enum-validated field
  on the render request (reuse the MV-B04 validator pattern → 422 on bad params).
- Acceptance criteria: `render(mode=heatmap, norm=log)` on positive data produces valid PNG bytes and
  a visibly different mapping than `norm=linear`; `norm=log` on data with non-positive values raises
  `InvalidParameterError` → 422; `norm=symlog` with `linthresh` set renders; pytest covers all four
  norms in core + a REST round-trip for `norm`.
- Asset capability needed: **edit headless render core** + **extend existing REST/MCP render params** +
  **edit PySide6 GUI** + **add pytest cases**.

---

### MV-I02 — Quantitative colorbar tied to the active norm + vmin/vmax
- Value: **HIGH** · Effort: **S**
- What it adds: a colorbar drawn on the rendered figure that reflects the chosen norm (MV-I01) and the
  explicit vmin/vmax clamps, with a toggle (`show_colorbar`).
- Why: makes the legend quantitatively meaningful; without it a log/symlog map is unreadable. Cheap
  because the heatmap path already creates a `ScalarMappable`/`_render_heatmap` sets clim
  (`core.py:656-671`).
- Reference tool: matplotlib colorbar + normalization.
  Citation: https://matplotlib.org/stable/users/explain/colors/colormapnorms.html
- Modules/files touched: `map_visualizer/core.py` (`_render_heatmap`/`_render_contour` add
  `figure.colorbar(mappable, ax=...)` gated by a `show_colorbar` flag, using the active norm);
  `api/service.py` + `api/rest.py` (`show_colorbar` bool param); `gui/main_window.py` (toggle);
  `tests/test_core.py`.
- Rough approach (CORE HEADLESS): use `Figure.colorbar` (NOT `pyplot.colorbar`) on the existing
  `Figure` so it stays Agg-safe. Tie the colorbar's `Normalize` to the same instance produced by
  MV-I01's `build_norm` so the scale matches. Default `show_colorbar=True` for heatmap/contour.
- Acceptance criteria: `render(mode=heatmap, show_colorbar=True, norm=log)` produces a PNG whose byte
  size / axes count differs from `show_colorbar=False` (colorbar axis added); a smoke test asserts the
  figure has 2 axes when the colorbar is on; REST round-trip for `show_colorbar` returns valid PNG.
- Asset capability needed: **edit headless render core** + **extend existing REST/MCP render params** +
  **edit PySide6 GUI** + **add pytest cases**.

---

### MV-I03 — Contour inline labels (clabel)
- Value: **MED** · Effort: **S**
- What it adds: optional inline iso-value labels on the contour mode (`label_contours` flag, optional
  `contour_levels` count), so contour lines carry their value.
- Why: contour without labels forces the reader to guess gradient values; labeling is a standard,
  low-cost scientific readout. The contour mode already exists (`RenderMode.contour`,
  `_render_contour`).
- Reference tool: matplotlib `clabel` / Plotly contour labels.
  Citation: https://matplotlib.org/stable/gallery/user_interfaces/svg_histogram_sgskip.html ;
  https://plotly.com/graphs/
- Modules/files touched: `map_visualizer/core.py` (`_render_contour`: keep the `ContourSet` handle and
  call `ax.clabel(cs, inline=True, ...)` when `label_contours`); `enums.py`/params plumbing;
  `api/service.py` + `api/rest.py` (`label_contours`, `contour_levels`); `gui/main_window.py` (checkbox);
  `tests/test_core.py`.
- Rough approach (CORE HEADLESS): `_render_contour` already calls `ax.contour`; capture its return and
  conditionally `ax.clabel`. All on the `Axes` of the Agg `Figure`. Guard `contour_levels` to a sane
  positive int (→ `InvalidParameterError` otherwise).
- Acceptance criteria: `render(mode=contour, label_contours=True)` yields valid PNG and the contour
  axis has labeled text artists (assert `len(ax.texts) > 0` in a core test); `label_contours=False`
  has none; REST round-trip works.
- Asset capability needed: **edit headless render core** + **extend existing REST/MCP render params** +
  **edit PySide6 GUI** + **add pytest cases**.

---

### MV-I04 — Perceptually-uniform / colorblind-safe colormap guidance + curated default set
- Value: **MED** · Effort: **S**
- What it adds: a curated, documented colormap recommendation layer — default to viridis/magma/plasma/
  inferno (sequential), surface diverging maps for centered data, and document *why* (equal value
  interval → equal perceptual interval). Optionally a `list_recommended_colormaps()` helper grouping
  maps by purpose.
- Why: users currently get the full matplotlib list with no guidance and may pick perceptually
  non-uniform / rainbow maps that mislead. Pure documentation + a small enumeration; no render-math
  change.
- Reference tool: viridis / cmocean / Kenneth Moreland color advice.
  Citation: https://matplotlib.org/cmocean/ ; https://www.kennethmoreland.com/color-advice/
- Modules/files touched: `map_visualizer/core.py` (optional `list_recommended_colormaps()` returning a
  static curated grouping — no new heavy dep; cmocean is optional/guidance-only); `api/rest.py`
  (optional `/colormaps?recommended=true`); `README.md` + `docs/agent-operating-doc.md` (guidance
  section); `tests/test_core.py`.
- Rough approach (CORE HEADLESS): keep it a static curated list validated against
  `matplotlib.colormaps` at call time (no new runtime dependency — cmocean stays a documented
  suggestion, not a hard dep, to avoid bloating the PyInstaller bundle). Default `cmap` selection in
  GUI/core points at viridis.
- Acceptance criteria: `list_recommended_colormaps()` returns groups (sequential / diverging /
  cyclic), every returned name is a valid matplotlib colormap; README has a "Choosing a colormap"
  section citing the sources; default cmap is a perceptually-uniform map. pytest asserts all
  recommended names validate.
- Asset capability needed: **edit headless render core** + **edit docs / README** + **add pytest cases**
  (+ optional **extend existing REST/MCP render params** for the `recommended` query flag).

---

### MV-I05 — Vector export to SVG / PDF (alongside PNG)
- Value: **MED** · Effort: **S**
- What it adds: an output-`format` choice on `render()` and the REST route — `png` (default, raster,
  unchanged), `svg`, `pdf` — for publication-quality, infinite-zoom output.
- Why: PNG is fine for raster/headless preview but loses fidelity on zoom; SVG/PDF are standard for
  papers. `savefig` already drives the byte output (`core.py:524-526`); adding formats is small.
- Reference tool: matplotlib `savefig`; Plotly one-click PNG/SVG/PDF.
  Citation: https://www.geeksforgeeks.org/save-matplotlib-figure-as-svg-and-pdf-using-python/ ;
  https://plotly.com/python/interactive-html-export/
- Modules/files touched: `map_visualizer/core.py` (`render(..., out_format='png')` → `fig.savefig(buf,
  format=out_format, bbox_inches='tight')`; return bytes + a content-type hint); `enums.py`
  (`ExportFormat`); `api/service.py` + `api/rest.py` (`/render?format=svg|pdf` sets the correct
  `media_type`: `image/svg+xml`, `application/pdf`); MCP `post_render` still returns PNG `Image` for
  the inline-image contract (document that vector formats are REST-only or returned as a file payload);
  `gui/main_window.py` (save-as format options); `tests/test_core.py` + `tests/test_api.py`.
- Rough approach (CORE HEADLESS): Agg `FigureCanvasAgg` can `savefig` to svg/pdf via the figure's
  format dispatch (no pyplot, no extra backend import needed for svg/pdf output buffers). Validate
  `out_format` against the `ExportFormat` enum → `InvalidParameterError`/422 otherwise. Keep
  `bbox_inches='tight'` to avoid clipping labels/colorbar (pairs with MV-I02/MV-I03).
- Acceptance criteria: `render(out_format='svg')` returns bytes starting with `<?xml`/`<svg`;
  `out_format='pdf'` returns bytes starting with `%PDF`; `/render?format=svg` responds with
  `Content-Type: image/svg+xml`; default (no format) still returns a valid PNG. pytest covers all three
  formats in core + REST media-type assertions.
- Asset capability needed: **edit headless render core** + **extend existing REST/MCP render params** +
  **edit PySide6 GUI** + **add pytest cases**.

---

### MV-I06 — Histogram as a first-class render mode with norm awareness
- Value: **MED** · Effort: **S**
- What it adds: hardening/extending the existing `histogram` mode to accept `bins` and overlay the
  active vmin/vmax clamp lines, so the value distribution guides colormap/clamp choice; SVG-exportable
  (via MV-I05).
- Why: a histogram of array values is a core readout for choosing vmin/vmax and a colormap; the mode
  exists (`RenderMode.histogram`) but research calls for norm/clamp awareness.
- Reference tool: matplotlib SVG histogram.
  Citation: https://matplotlib.org/stable/gallery/user_interfaces/svg_histogram_sgskip.html
- Modules/files touched: `map_visualizer/core.py` (`_render_histogram`/`draw_histogram`: add `bins`
  param, draw vmin/vmax as `ax.axvline`s when a value_range is set); `api/service.py` + `api/rest.py`
  (`bins` param); `gui/main_window.py`; `tests/test_core.py`.
- Rough approach (CORE HEADLESS): extend the existing histogram draw helper on the Agg figure; validate
  `bins` is a positive int (→ `InvalidParameterError`). No new dependency.
- Acceptance criteria: `render(mode=histogram, bins=20, value_range=(a,b))` returns valid PNG with the
  configured bin count and two vertical clamp lines (assert `len(ax.lines) >= 2`); invalid `bins` (0,
  negative) → `InvalidParameterError`/422. pytest covers it.
- Asset capability needed: **edit headless render core** + **extend existing REST/MCP render params** +
  **edit PySide6 GUI** + **add pytest cases**.

---

### MV-I07 — Large-array downsampling / decimation for render
- Value: **HIGH** · Effort: **M**
- What it adds: an optional `max_render_cells` / `downsample` control that decimates (or block-reduces)
  a large array before rendering, bounding render cost and memory while keeping the visual.
- Why: `max_cells` is ~16.7M (review §C / `core.py:54`); a single `/render` can pull ~128MB + a full
  matplotlib render (DoS note, low). Downsampling keeps big grids responsive and is the directly
  transferable idea from napari/ParaView large-data handling.
- Reference tool: napari (large multi-dimensional data); Plotly WebGL.
  Citation: https://imagej.net/software/napari ; https://plotly.com/graphs/
- Modules/files touched: `map_visualizer/core.py` (a pure `downsample(array, target_cells) -> ndarray`
  via stride/block-mean, applied in `render()` before drawing when the array exceeds a render
  threshold); `api/service.py` + `api/rest.py` (`downsample`/`max_render_cells` param); `gui/
  main_window.py` (auto-downsample for live preview); `tests/test_core.py`.
- Rough approach (CORE HEADLESS): NumPy-only block-reduce (reshape-and-mean) or strided decimation in a
  pure core function. Default: render full size unless array > a configurable render threshold (keep the
  hard `max_cells` load guard intact — this is an additional *render-time* bound). Preserve aspect ratio
  and report the applied factor in stats. Decimation method (mean vs subsample) chosen for fidelity vs
  speed; document the choice.
- Acceptance criteria: a 5000×5000 array with `downsample` enabled renders to a valid PNG and the
  internal rendered array is ≤ `max_render_cells`; a unit test asserts `downsample(arr, N).size <= N`
  and that shape/aspect are preserved within one cell; full-size render path is unchanged when under
  threshold.
- Asset capability needed: **edit headless render core** + **extend existing REST/MCP render params** +
  **edit PySide6 GUI** + **add pytest cases**.

---

### MV-I08 — Multi-array overlay / compare (per-layer colormap + opacity)
- Value: **MED** · Effort: **L**
- What it adds: a render path that composites 2+ arrays as stacked layers, each with its own
  colormap/opacity (alpha), for side-by-side or overlaid comparison (e.g. data + mask).
- Why: layering is napari's core analysis surface and a natural "multiple visualization options"
  expansion (R2.b). Higher effort: it changes the render signature from one array to a list and ripples
  through the access-layer schema.
- Reference tool: napari image-layer overlay.
  Citation: https://napari.org/dev/howtos/layers/image.html
- Modules/files touched: `map_visualizer/core.py` (new `render_overlay(layers: list[Layer]) -> bytes`
  or an `overlay` mode where each layer carries `array, cmap, alpha, norm`); `enums.py` (add `overlay`
  to `RenderMode`, deferred in strategy D1); `api/service.py` + `api/rest.py` (new request schema:
  list of layer specs — keep inline-grid-only, no server paths, per review §C safety); `api/
  mcp_server.py` (new tool); `gui/main_window.py` (layer list UI — larger GUI change); `tests/
  test_core.py` + `tests/test_api.py`.
- Rough approach (CORE HEADLESS): draw each layer onto the same Agg `Axes` with `imshow(..., alpha=,
  cmap=, norm=)` in z-order; validate all layers share a compatible shape (or define resampling rules)
  → `GridValidationError` on mismatch. Bound total cells across layers by `max_cells`. Keep the
  inline-grid-only contract (no filesystem paths from clients).
- Acceptance criteria: `render_overlay([{array,cmap,alpha},{array,cmap,alpha}])` returns a valid PNG
  where the two layers are composited (assert ≥2 image artists on the axis); mismatched shapes raise
  `GridValidationError`/422; a 2-layer REST/MCP round-trip returns a PNG. pytest covers compose +
  mismatch.
- Asset capability needed: **add render mode (headless core)** + **add MCP tool + REST route returning
  PNG** + **add Pydantic boundary validator (REST/service)** + **edit PySide6 GUI** + **add pytest
  cases**.

---

### MV-I09 — Line-profile extraction along a selection (1-D profile from the 2-D array)
- Value: **MED** · Effort: **M**
- What it adds: sample values along a drawn/parameterized line segment (endpoints `(r0,c0)-(r1,c1)`)
  to produce a 1-D profile plot — a core scientific-imaging readout. Builds on the existing `profile`
  mode (currently row/column).
- Why: arbitrary-line profiles (not just row/column) are a standard ImageJ/napari readout and turn the
  tool into an analysis surface, mapping cleanly to MCP/REST params (two endpoints).
- Reference tool: ImageJ ROI profiles / napari_jroitools.
  Citation: https://github.com/jayunruh/napari_jroitools ; https://imagej.net/ij/docs/guide/146-10.html
- Modules/files touched: `map_visualizer/core.py` (a pure `line_profile(array, p0, p1, *,
  samples=None) -> ndarray` via bilinear sampling along the segment; a `profile` render variant that
  plots it); `enums.py` (profile sub-mode/endpoints); `api/service.py` + `api/rest.py` (`profile_p0`,
  `profile_p1` params; optionally a `/profile` route returning the sampled values as JSON AND a PNG
  plot); `gui/main_window.py` (draw-line interaction — GUI only); `tests/test_core.py`.
- Rough approach (CORE HEADLESS): pure NumPy bilinear interpolation along the segment (np.linspace
  endpoints, gather with bilinear weights); plot the resulting 1-D series on the Agg figure for the
  image return, and optionally return the raw samples via a JSON route. Validate endpoints are within
  bounds → `InvalidParameterError`/422. The draw-line UX is GUI-only and must not pull interactivity
  into core.
- Acceptance criteria: `line_profile(arr, (0,0), (0,4))` on a known row returns that row's values;
  out-of-bounds endpoints raise `InvalidParameterError`; `render(mode=profile, p0, p1)` returns a valid
  PNG; optional `/profile` returns the sample array as valid JSON. pytest covers sampling correctness +
  bounds.
- Asset capability needed: **edit headless render core** + **add MCP tool + REST route returning PNG**
  (+ optional JSON profile route) + **edit PySide6 GUI** + **add pytest cases**.

---

### MV-I10 — ROI selection (rectangle) returning the sub-region + region stats
- Value: **MED** · Effort: **M**
- What it adds: a rectangular ROI parameter `(r0,c0,r1,c1)` that crops the array before rendering/stats,
  returning the sub-region's render and its `array_stats` — so vmin/vmax/colormap choices can target a
  region.
- Why: ROI-then-readout is the ImageJ/napari analysis idiom; it pairs with the histogram (MV-I06) and
  profile (MV-I09) and is fully parameterizable over REST/MCP (no interactive drawing needed for the
  headless path).
- Reference tool: ImageJ/Fiji selections; napari-annotatorj.
  Citation: https://imagej.net/ij/docs/guide/146-10.html ; https://napari-hub.org/plugins/napari-annotatorj
- Modules/files touched: `map_visualizer/core.py` (a pure `crop_roi(array, r0,c0,r1,c1) -> ndarray`;
  accept an optional `roi` in `render()` and `array_stats()`); `api/service.py` + `api/rest.py` (`roi`
  param on `/render` and `/stats`); `gui/main_window.py` (rubber-band rectangle — GUI only); `tests/
  test_core.py` + `tests/test_api.py`.
- Rough approach (CORE HEADLESS): pure NumPy slice with bounds + ordering validation (reuse MV-B05's
  ordering guard → `InvalidParameterError`/422 on inverted/out-of-bounds ROI). Apply the crop before
  norm/clamp so the colorbar reflects the region. Keep it inline-grid-only (no server path traversal).
- Acceptance criteria: `crop_roi(arr, 1,1,3,3)` returns the expected 2×2 sub-array; out-of-bounds or
  inverted ROI raises `InvalidParameterError`/422; `/render?...&roi=...` returns a PNG of the cropped
  region and `/stats` with `roi` returns the region's stats. pytest covers crop + bounds.
- Asset capability needed: **edit headless render core** + **extend existing REST/MCP render params** +
  **edit PySide6 GUI** + **add pytest cases**.

---

### MV-I11 — Annotations overlay (title, axis labels, markers, text)
- Value: **LOW** · Effort: **S**
- What it adds: optional figure annotations — `title`, axis labels, point markers `(r,c,label)`, and
  free text — drawn onto the render and persisted in the exported figure (works with SVG/PDF via
  MV-I05).
- Why: annotated figures are publication/communication-ready; the understanding doc flags "no axis
  labeling/title/legend customization" as an R2.b gap. Low value relative to the color/analysis cluster
  but cheap and broadly useful.
- Reference tool: ImageJ/Fiji + napari annotations.
  Citation: https://github.com/jayunruh/napari_jroitools ; https://imagej.net/ij/docs/guide/146-10.html
- Modules/files touched: `map_visualizer/core.py` (render accepts `title`, `xlabel`, `ylabel`,
  `markers: list[(r,c,label)]`; draw via `ax.set_title`/`ax.set_xlabel`/`ax.annotate`); `api/service.py`
  + `api/rest.py` (annotation params); `gui/main_window.py` (annotation fields); `tests/test_core.py`.
- Rough approach (CORE HEADLESS): all annotation drawing is `Axes`/`Figure` text on the Agg figure;
  validate marker coordinates are in-bounds (→ `InvalidParameterError`). No new dependency. Keep
  annotation params optional so the default render is unchanged.
- Acceptance criteria: `render(..., title="T", markers=[(0,0,"a")])` returns valid PNG and the axis
  has the title + ≥1 annotation text (assert in a core test); out-of-bounds marker →
  `InvalidParameterError`; SVG export (MV-I05) contains the title text string. pytest covers it.
- Asset capability needed: **edit headless render core** + **extend existing REST/MCP render params** +
  **edit PySide6 GUI** + **add pytest cases**.

---

### MV-I12 — Interactive pan / zoom / hover / box-select polish (GUI-only)
- Value: **LOW** · Effort: **M**
- What it adds: GUI-side interactivity polish — smoother pan/zoom, a box-select that feeds the ROI
  (MV-I10), and a richer hover readout. Strictly GUI; no core/access-layer change.
- Why: improves the desktop UX (research item 6) but does not touch the headless contract or the
  programmatic surface, so it is the lowest leverage for the campaign's headless/access-layer thrust;
  included for completeness as an R2.b GUI enhancement.
- Reference tool: Plotly interactivity; napari pan/zoom default.
  Citation: https://plotly.com/graphs/ ; https://napari.org/dev/howtos/layers/image.html
- Modules/files touched: `map_visualizer/gui/main_window.py` ONLY (Qt event handlers, mpl
  `NavigationToolbar2QT`, a rubber-band selector wired to MV-I10's ROI core function); `tests/` (GUI
  tests optional — the coverage gate excludes `gui/*` per `pyproject.toml`).
- Rough approach (CORE HEADLESS — N/A, GUI only): reuse the existing core `draw_*`/`crop_roi`/
  `line_profile` functions from the Qt widgets; the box-select hands `(r0,c0,r1,c1)` to `crop_roi`. No
  pyplot; Qt backend stays confined to `gui/`. Do not add interactivity dependencies to core.
- Acceptance criteria: box-selecting a region in the GUI updates the view to that ROI using the core
  `crop_roi` (manual/QA check, since `gui/*` is coverage-excluded); hover readout shows X/Y/value; no
  new import appears in `core.py` (headless invariant re-asserted by the existing core import test).
- Asset capability needed: **edit PySide6 GUI** (no core/access-layer change).

---

### Cross-cutting notes for the orchestrator
- **Sequencing:** MV-B01/B02/B03 (loader correctness) and MV-B04/B05 (range validation) should land
  first in feature-enhancer/access-layer passes — several features (MV-I01, I05, I07, I10) reuse the
  `InvalidParameterError`→422 ordering/length validators those bugs introduce.
- **Single Gleaner-relevant read set:** all detail here is already extracted from 3 docs (< the
  threshold of 5); **no GATHERING REQUEST** is needed for this backlog.
- **Single embedded RESEARCH REQUEST:** MV-B10 (dependency-pin revalidation) — route to the-researcher
  before the packaging/manifest finalization.
- **No new agent/asset needed:** every capability tag maps onto an existing domain agent
  (feature-enhancer = core edits/render modes; access-layer-builder = MCP tool + REST route + Pydantic
  validators; testing = pytest cases; packaging = PyInstaller spec + gitignore; docs = README/access
  notes; GUI edits = feature-enhancer per its R2.b ownership). **No ASSET REQUEST to the-metaprompter**
  is required for the backlog itself (the in-repo agent asset R6 already exists and is verified PRESENT).
```
```
