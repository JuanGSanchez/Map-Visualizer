# Map-Visualizer — Post-review remediation specifications (2026-06-28)

Pre-merge critical-review output for the `enhancement/map-visualizer-20260625` branch (PR #1 → `main`).
The original product backlog (SPEC-01..SPEC-23) is **fully delivered** and archived in
`SPECIFICATIONS-archive-20260625.md`. This file lists ONLY the concrete, acceptance-testable
remediation items found by the pre-merge review. Each `RS-*` carries a priority (P1/P2/P3),
the defect, the fix scope, and a testable acceptance criterion.

All standing invariants from the archived spec and `CLAUDE.md` still apply (headless Agg-only core,
typed errors → 422, deterministic offline tests, ≥90 % core-coverage gate never weakened, no
secrets/bundles committed, commit only on the enhancement branch).

## Review verdict in one line
The branch is **functionally complete and merge-clean** (237 tests green, 94.49 % core coverage,
clean working tree, no stray/temp files tracked, `packaging/bin|work` correctly gitignored, core
import-pure of pyplot/Qt). One genuine robustness defect (RS-01) and three minor quality nits
(RS-02..RS-04) were found. None block the build; RS-01 is a correctness fix worth shipping before
merge.

---

## RS-01 — Single-row inline grid is misclassified as a file path (P2)

- **Priority:** P2 (real correctness/robustness defect in the access layer).
- **Defect:** `core.load_array` decides "path vs. raw text" with the heuristic
  `is_path = os.sep in source or altsep in source or "\n" not in source`. A single-row inline grid
  has no path separator and no newline, so it is treated as a **file path**, fails the extension
  check, and raises `GridLoadError: Unsupported file extension: '1 2 3'`. This breaks two legitimate
  inputs:
  - REST/MCP: a single-row JSON grid `[[1.0, 2.0, 3.0]]` — `service._coerce_grid` joins it to the
    newline-less string `"1.0 2.0 3.0"`, which the core then rejects as a bad path → HTTP **422 on
    valid input**.
  - Direct core use: `load_array("1 2 3")` (a 1×N inline row) raises instead of returning `(1, 3)`.
  - The same input **with** a trailing newline (`"1 2 3\n"`) works, proving the misclassification.
  - This contradicts the archived SPEC-15 promise to "keep the existing 1×N/N×1 reshape behavior"
    and SPEC-04/05's inline-grid contract.
- **Scope:** Replace the newline-based path heuristic with an extension-/separator-based one in
  `map_visualizer/core.py` `load_array`: treat `source` as a path **only** when it ends with a
  supported extension (`.txt`/`.dat`/`.csv`, case-insensitive) **or** contains a path separator;
  otherwise treat it as raw inline text. No change to the file-path, file-like, or PathLike branches.
  No API signature change.
- **Acceptance criteria:**
  - `load_array("1 2 3")` returns a `(1, 3)` array (no exception).
  - `service.render_from_inline_grid("[[1.0, 2.0, 3.0]]")` and
    `service.stats_from_inline_grid("[[1.0, 2.0, 3.0]]")` succeed and report `shape == [1, 3]`.
  - `POST /render` and `POST /stats` with a single-row JSON grid return **200**, not 422.
  - All previously-passing path tests still pass (missing file → `GridLoadError`; unsupported
    extension on a real path → `GridLoadError`; CSV/whitespace/semicolon load unchanged).
  - New pytest cases cover the single-row inline (text + JSON) path in `tests/test_core.py` and
    `tests/test_api.py`.
- **Owner:** core-dev (heuristic) + test-author (tests). Gate must stay ≥90 %.

---

## RS-02 — Dead `import textwrap` in the render core (P3)

- **Priority:** P3 (cleanliness; no behavioral impact).
- **Defect:** `map_visualizer/core.py` imports `textwrap` (line ~30) but never uses it.
- **Scope:** Remove the unused import. No other change.
- **Acceptance criteria:**
  - `grep -n "textwrap" map_visualizer/core.py` returns nothing.
  - `python -c "import map_visualizer.core"` still imports clean; full gate stays green.
- **Owner:** core-dev.

---

## RS-03 — Deprecated `HTTP_422_UNPROCESSABLE_ENTITY` constant (P3)

- **Priority:** P3 (forward-compat; emits a `DeprecationWarning`, no functional break).
- **Defect:** `map_visualizer/api/rest.py` `_core_error_to_422` uses
  `status.HTTP_422_UNPROCESSABLE_ENTITY`, which Starlette/FastAPI now deprecate in favour of
  `HTTP_422_UNPROCESSABLE_CONTENT`. The test run shows the `DeprecationWarning` on every 422 path.
- **Scope:** Use the literal `422` (transport-version-agnostic, never deprecated) in
  `_core_error_to_422`, keeping the structured `{error, message}` body unchanged. The 422 contract
  and all `*_422` tests are unaffected.
- **Acceptance criteria:**
  - No `HTTP_422_UNPROCESSABLE_ENTITY` reference remains in `api/rest.py`.
  - `pytest -W error::DeprecationWarning tests/test_api.py -k 422` no longer raises on that warning
    from `rest.py` (the project's own code), and all 422 tests still return 422.
- **Owner:** access-dev.

---

## RS-04 — numpy pin is tighter than the documented invariant (P3 — ACCEPTED, no code change)

- **Priority:** P3, **recorded as accepted** (no remediation action taken; documented for the
  maintainer).
- **Observation:** `pyproject.toml` pins `numpy~=2.4.6` (i.e. `>=2.4.6,<2.5.0`) while the
  `CLAUDE.md` / archived-spec standing invariant text reads `numpy>=1.25`. The `matplotlib~=3.11.0`
  pin is consistent with the `>=3.11,<3.12` invariant; only numpy diverges, and `~=2.4.6` is unusually
  tight for a library floor.
- **Why no change here:** Per `CLAUDE.md` working discipline, dependency-pin changes require a
  stop-and-confirm with the maintainer; the installed/tested stack is numpy 2.4.6 / matplotlib 3.11.0
  and the suite is green against it, so the campaign-fixed pin is functionally correct. Loosening the
  floor (e.g. `numpy>=2.0,<3`) or updating the invariant text is a maintainer policy decision, not a
  review defect.
- **Acceptance criteria (deferred / maintainer decision):** Either (a) reconcile `pyproject.toml`
  and `CLAUDE.md` to a single agreed numpy constraint, or (b) confirm `~=2.4.6` is the intended
  campaign pin and update the `CLAUDE.md` invariant text to match. No action is required for this PR
  to merge.
- **Owner:** packaging-builder / maintainer (out of band).

---

## Areas reviewed with NO real issue (explicitly cleared — no work invented)

- **All SPEC-01..SPEC-23 implemented, correct, and tested.** Every mode (heatmap, contour,
  contourf, surface3d, histogram, profile/profile_row/profile_col), every render param
  (value/color range, levels, bins, colorbar, title/labels, output_format, max_render_cells),
  the REST + MCP layer, packaging config, and the GUI are present with passing acceptance tests.
- **Merge-readiness:** working tree clean; no `subagent-report-*`/scratch/checkpoint files tracked;
  `packaging/bin/` and `packaging/work/` exist on disk only and are gitignored (0 tracked) — invariant
  8 honored; no `TODO`/`FIXME`/stub/`NotImplementedError` markers in `map_visualizer/`.
- **Headless purity:** `core.py`/`enums.py` import no pyplot/Qt/Tk (only docstring mentions);
  `import map_visualizer.core` is clean; all Qt lives under `gui/`.
- **SPEC-08 (PyInstaller):** spec config verified correct — `datas` bundles `Logo MVis.png`,
  excludes are effective (`tkinter`, `backend_tkagg`, `wx`, `gtk`, `PyQt5`, `PyQt6`, `PySide2`),
  Windows `.ico` icon wired, onedir mode, demo `.txt`/`.dat` fixtures NOT bundled. A full frozen
  build is a release action (artifacts VCS-ignored) and is intentionally not run/committed here.
- **SPEC-17 overlay (two-array composite):** genuinely OPTIONAL in the archived spec ("If
  implemented … overlay mode composites two arrays"); not implemented, and recorded as a future
  backlog item (`docs/BACKLOG.md` MV-I08). Accepted out-of-scope for this PR.
- **MCP returns PNG only:** intentional and documented — `docs/agent-operating-doc.md` ("MCP stays
  PNG") and `docs/BACKLOG.md` MV-I05 ("MCP `post_render` still returns PNG `Image`"); SVG/PDF are
  available via REST `image_format` and GUI export. Consistent.
- **Centralized widget-info popup is the sole info surface:** all interactive widgets register via
  the single `info.register_info` registry (one `QToolTip` QSS rule, one theming point); the only
  other dialogs are legitimate error `QMessageBox` and the `About` box — not ad-hoc info/tooltip
  popups. Confirmed by the GUI source-hygiene tests.
- **Coverage gate not weakened:** `--cov-fail-under=90` and the `gui/*`+`api/*` omit list are
  unchanged from the contract in `CLAUDE.md`.

## Priority summary
- **P1:** none.
- **P2:** RS-01.
- **P3:** RS-02, RS-03, RS-04 (RS-04 accepted/no-op).
