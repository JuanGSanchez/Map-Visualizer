# RESEARCH REPORT — matplotlib / Agg headless best-practices (Map-Visualizer)

Request: RR-1 (strategy `docs/strategy-map-visualizer.md`). Status: COMPLETE.
Access date for all citations: **2026-06-26**. Target runtime: Python 3.11–3.13, matplotlib Agg
backend, headless server rendering via FastAPI/MCP.

> Citation integrity (C1): every finding below carries a source tag [S#] resolved in the Source List
> at the end. matplotlib.org doc pages were intermittently 403 to the fetcher; the findings are taken
> from the official documentation pages surfaced by search and are cited to those canonical URLs. Any
> non-official (blog/issue) source is flagged with reduced reliability inline.

---

## Summary

- **Pin: `matplotlib>=3.11,<3.12` and `numpy>=1.25`.** matplotlib 3.11.0 (released 2026-06-12) is the
  current stable line; it requires Python >=3.11 and ships wheels/classifiers for 3.11, 3.12, 3.13
  (and 3.14), covering the repo's 3.11–3.13 ceiling. Its declared floor is numpy >=1.25. [S1][S2]
- **Use the explicit (pyplot-free) object API for the server core:** construct
  `matplotlib.figure.Figure(...)`, attach `FigureCanvasAgg(fig)`, draw, and `fig.savefig(buf,
  format="png")`. This avoids pyplot's global figure registry entirely. [S3]
- **Memory:** pyplot leaks because its global registry holds references until `plt.close(fig)`. The
  object API has **no** global registry, so a per-request `Figure` is reclaimed by ordinary reference
  counting when it goes out of scope — **`gc.collect()` is not required** on the OO path (cargo-cult).
  [S4][S13]
- **Thread safety:** matplotlib is **not thread-safe**; the caller must serialize access. For a
  concurrent server, prefer **one `Figure` per request** plus either a module-level render **lock** or
  a **process pool**; do not share a `Figure`/canvas across threads. [S4][S5][S14]
- **Colormaps:** `matplotlib.cm.get_cmap` was deprecated in 3.7 and **removed in 3.9**. Use
  `matplotlib.colormaps[name]` (or `matplotlib.colormaps.get_cmap(...)`). [S6][S7][S8]
- **Deterministic PNG bytes:** fix `figsize`+`dpi`, and pass `metadata={"Software": None}` (PNG) /
  `metadata={"CreationDate": None}`-style overrides to strip the version/date stamp matplotlib injects
  by default — otherwise output bytes differ run-to-run. [S9][S10]

---

## 1. Version currency — matplotlib + numpy pins

**Finding.** Current stable matplotlib is **3.11.0, released 2026-06-12** (the 3.10.x line, e.g.
3.10.9 / 2026-04-23, is the prior series). PyPI metadata for 3.11.0 declares `Requires: Python >=3.11`
and lists classifiers for Python **3.11, 3.12, 3.13, 3.14** — fully covering the repo's 3.11–3.13
ceiling. [S1][S15]

**Finding.** matplotlib 3.11's declared minimum numpy is **numpy >=1.25** (per the 3.11.0
Dependencies page). numpy 1.25+ is available for all of 3.11–3.13, so no per-Python special-casing is
needed. [S2]

**Recommended pin (for `pyproject.toml` / requirements):**
```toml
dependencies = [
    "matplotlib>=3.11,<3.12",
    "numpy>=1.25",
]
```
Rationale: caps at the tested minor line for reproducibility while staying on the maintained 3.11
series; numpy floor matches matplotlib's own declared floor. [S1][S2]

---

## 2. Headless Agg rendering via the explicit object API (pyplot-free)

**Finding.** The canonical pyplot-free idiom (matplotlib's own "CanvasAgg demo") builds a `Figure`,
attaches a `FigureCanvasAgg`, draws, and emits PNG bytes — no `pyplot`, hence no global state. [S3]

**Canonical idiom — render to an in-memory PNG buffer (server core):**
```python
import io
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

def render_png(figsize=(6.4, 4.8), dpi=100) -> bytes:
    fig = Figure(figsize=figsize, dpi=dpi)   # NOT plt.figure(): no global registry
    canvas = FigureCanvasAgg(fig)            # bind Agg canvas explicitly
    ax = fig.add_subplot()                   # or fig.subplots()
    ax.plot([1, 2, 3])
    buf = io.BytesIO()
    fig.savefig(buf, format="png")           # canvas.draw() is invoked internally
    return buf.getvalue()
    # fig has no external reference after return -> reclaimed normally (see §3)
```

**Alternative — raw RGBA pixels (for compositing / NumPy):**
```python
canvas = FigureCanvasAgg(fig)
canvas.draw()
rgba = np.asarray(canvas.buffer_rgba())      # H x W x 4 uint8
```
[S3]

**Why pyplot-free for a server:** `pyplot` maintains an interpreter-global figure manager (`Gcf`) and
implicit "current figure/axes" state. Under FastAPI/MCP concurrency that global state is shared and
mutable — a correctness and leak hazard. The `Figure`+`FigureCanvasAgg` construction owns no global
state. [S3][S4]

---

## 3. Figure lifecycle / memory management — and the `gc.collect()` myth

**Finding (pyplot path — the leak).** Figures created via `pyplot` (`plt.figure`, `plt.subplots`) are
held by pyplot's global registry and are **not** released until explicitly closed; matplotlib emits
`RuntimeWarning: More than 20 figures have been opened` (rcParam `figure.max_open_warning`) precisely
because they accumulate. The fix on that path is `plt.close(fig)` (or `plt.close("all")`), ideally in a
`try/finally` so an exception between create and close still releases the figure. [S4][S13]

**Finding (object-oriented path — no registry).** A `Figure` built directly (as in §2) is **not**
registered with pyplot's `Gcf`. Once the last reference goes out of scope, CPython reclaims it via
ordinary reference counting — there is no global holding it alive. Therefore on the OO path you do
**not** need `plt.close()` and you do **not** need `gc.collect()`. [S3][S4]

**Debunk — `gc.collect()` cargo-cult.** Community advice to call `gc.collect()` after rendering is a
workaround for the *pyplot* registry/back-reference problem (and occasionally GUI-backend leaks), not a
requirement of headless Agg. With the explicit `Figure`+`FigureCanvasAgg` pattern there is no reference
cycle to break and no global registry to drain, so a forced collection buys nothing but latency. Treat
any `gc.collect()` in the render hot-path as removable. *(Reliability note: the "call gc.collect()"
claim originates in community threads/blogs [S13] and matplotlib issue trackers, not the official API;
the no-registry basis for omitting it is the official FAQ/CanvasAgg behavior [S3][S4].)*

**Recommended teardown:**
- OO server core (§2): rely on scope exit; optionally `fig.clear()` only if you *reuse* a Figure.
- If any pyplot is unavoidable: wrap in `try/finally: plt.close(fig)`.

---

## 4. Thread safety for concurrent server rendering

**Finding (official).** "Matplotlib is **not thread-safe**: in fact, there are known race conditions
that affect certain artists. … it is your responsibility to set up the proper locks to serialize
access to Matplotlib artists." You "may be able to work on separate figures from separate threads,"
but only with a **non-interactive backend (typically Agg)**, because GUI backends require the main
thread. [S4]

**Finding (Agg internals).** The Agg backend's font cache is class-level and "not thread safe"; the
`FigureCanvas` acquires a **lock on the font at the start of `draw()`** and releases it when done —
so multiple renderers share cached fonts but **only one figure can draw at a time**. Concurrent draws
without serialization are a documented segfault/race risk. [S5][S14]

**Recommended patterns for FastAPI/MCP `render_map`:**
1. **Per-request `Figure`** (never share a Figure/canvas across requests/threads) — baseline, always
   apply. [S4]
2. **Module-level lock around the draw/savefig section** if rendering on a threadpool:
   ```python
   import threading
   _RENDER_LOCK = threading.Lock()
   def render_map(...):
       fig = Figure(...); FigureCanvasAgg(fig); ...build...
       with _RENDER_LOCK:          # serialize the draw (Agg font-cache safety)
           buf = io.BytesIO(); fig.savefig(buf, format="png")
       return buf.getvalue()
   ```
   This serializes only the unsafe draw step; figure construction stays parallel. [S4][S5]
3. **Process pool** (`concurrent.futures.ProcessPoolExecutor` or `run_in_executor`) for true
   parallelism — each process has its own matplotlib state, sidestepping the GIL and the shared font
   cache. Preferred when render throughput matters. [S4]

For an `async` FastAPI/MCP handler, offload the synchronous render to a worker (`await
loop.run_in_executor(pool, render_map, ...)`) so the event loop is never blocked, and combine with #1
+ (#2 for threads / #3 for processes).

---

## 5. Colormap / interpolation API currency

**Finding.** `matplotlib.cm.get_cmap` was **deprecated in matplotlib 3.7** and **removed in 3.9**;
`matplotlib.cm.register_cmap`/`unregister_cmap` were likewise deprecated/removed. [S6][S7]

**Finding.** Current recommended access: `matplotlib.colormaps[name]` for a name string, or
`matplotlib.colormaps.get_cmap(obj)` to normalize a str/None/`Colormap` to a `Colormap`.
`matplotlib.pyplot.get_cmap` remains available for backward compatibility but is the pyplot path; the
registry access is preferred in pyplot-free code. [S6][S7][S8]

**Recommended idiom:**
```python
import matplotlib
cmap = matplotlib.colormaps["viridis"]        # NOT matplotlib.cm.get_cmap("viridis")
# normalize an arg that may be str | None | Colormap:
cmap = matplotlib.colormaps.get_cmap(user_cmap or "viridis")
ax.imshow(data, cmap=cmap, interpolation="nearest")
```
Interpolation for image render modes is selected per-call via the `interpolation=` kwarg on
`imshow` (e.g. `"nearest"`, `"bilinear"`); pin it explicitly for deterministic output (§7). [S8]

---

## 6. Render modes (headless OO API)

All modes below work under Agg headless using the §2 `Figure`+`add_subplot` pattern (no pyplot). Each
is an Axes method; build the Figure, call the method, `savefig(buf, format="png")`. [S3][S11]

- **Heatmap (imshow):** `ax.imshow(Z, cmap=cmap, interpolation="nearest", origin="lower", aspect="auto")`.
  Fully headless; deterministic with fixed interpolation. [S8]
- **Contour / filled contour:** `ax.contour(X, Y, Z, levels=...)` and `ax.contourf(X, Y, Z, levels=...)`.
  Pass an explicit `levels` array for reproducibility. [S11]
- **3D surface:** create the 3D Axes via `ax = fig.add_subplot(projection="3d")` then
  `ax.plot_surface(X, Y, Z, cmap=cmap)`. As of mpl 3.2 the explicit `import mpl_toolkits.mplot3d` is no
  longer required to enable the `"3d"` projection (Axes3D auto-registers). Renders under Agg. [S11]
- **Histogram:** `ax.hist(values, bins=...)` — pin `bins` explicitly for deterministic bytes. [S11]
- **Row/column profile plots:** `ax.plot(x, Z[row, :])` / `ax.plot(y, Z[:, col])` — ordinary line
  plots on the OO API. [S3]

Multi-panel layouts: `fig.subplots(nrows, ncols)` or `fig.add_subplot(r, c, i)` — all Agg-safe. [S3]

---

## 7. Deterministic PNG output (for render-to-image smoke tests)

**Finding (the non-determinism source).** matplotlib injects default PNG metadata including a
**`Software`** key carrying the matplotlib version (and date-like provenance). Because these embed in
the file, identical figures produce **different bytes** across versions/runs unless overridden. The
`metadata=` argument to `savefig`/`print_png` controls this; passing a key as `None` removes it.
(The analogous PDF fix is `metadata={"CreationDate": None}`.) [S9][S10]

**Finding.** `figsize`+`dpi` fully determine pixel dimensions; fix both. `bbox_inches="tight"`
introduces layout-dependent cropping — **avoid** it for byte-stable output; use a fixed figsize and
(optionally) `fig.tight_layout()`/`constrained_layout` consistently or not at all. [S9]

**Recommended deterministic save:**
```python
fig = Figure(figsize=(6.4, 4.8), dpi=100)     # fixed pixel size
# ... build axes; pin interpolation/levels/bins; format ticks explicitly ...
ax.ticklabel_format(style="plain")            # disable offset/sci-notation drift on numeric axes
buf = io.BytesIO()
fig.savefig(
    buf,
    format="png",
    dpi=100,
    metadata={"Software": None},              # strip version/date stamp -> stable bytes
)
png = buf.getvalue()
```
For smoke tests, compare either the exact `png` bytes (with the metadata stripped) or, more robustly
against sub-pixel AA differences across platforms, the decoded RGBA array via
`np.asarray(canvas.buffer_rgba())` with a tolerance — matplotlib's own image comparison tests use a
tolerance rather than exact bytes for cross-platform stability. [S3][S9]

**Axis/scientific-notation note:** numeric axes can auto-switch to offset/scientific notation depending
on data range, changing tick text; call `ax.ticklabel_format(...)` (or set a fixed `Formatter`) to lock
it for reproducible renders. [S9]

---

## Limitations

- matplotlib.org pages returned HTTP 403 to the automated fetcher on 2026-06-26; findings rest on the
  official documentation surfaced via search (cited to canonical matplotlib.org URLs) rather than
  full-text fetch. The version/numpy facts were confirmed directly from the fetchable PyPI page [S1].
- The exact wording of the PNG `Software`-key default lives in `print_png`'s backend docstring, which
  could not be fetched directly; the metadata-override mechanism is confirmed from the `savefig` API
  page and a corroborating practitioner source [S9][S10] (the PDF `CreationDate` analogue is
  explicitly documented; the PNG `Software` analogue follows the same `metadata={key: None}` mechanism).
- Exact-byte PNG reproducibility can still vary across OS/freetype/libpng builds; for portable smoke
  tests prefer tolerance-based RGBA-array comparison over byte equality.
- The `gc.collect()` "needed" claim [S13] is community-sourced (reduced reliability); it is debunked
  for the OO path on the basis of the official no-registry behavior, not a single authoritative "do not
  call gc.collect" statement.

---

## Source List (accessed 2026-06-26)

- [S1] *matplotlib · PyPI* — https://pypi.org/project/matplotlib/ — matplotlib 3.11.0 (2026-06-12);
  Requires Python >=3.11; classifiers 3.11–3.14. Publisher: PyPI / Matplotlib Development Team.
- [S2] *Dependencies — Matplotlib 3.11.0 documentation* —
  https://matplotlib.org/stable/install/dependencies.html — numpy >=1.25 floor. Publisher: Matplotlib.
- [S3] *CanvasAgg demo — Matplotlib 3.11.0 documentation* —
  https://matplotlib.org/stable/gallery/user_interfaces/canvasagg.html — pyplot-free Figure +
  FigureCanvasAgg + savefig idiom. Publisher: Matplotlib.
- [S4] *Frequently Asked Questions — Matplotlib 3.11.0 documentation* —
  https://matplotlib.org/stable/users/faq.html — "not thread-safe", per-thread separate figures with
  non-interactive backend, pyplot figure retention/memory. Publisher: Matplotlib.
- [S5] *matplotlib.backends.backend_agg — Matplotlib documentation* —
  https://matplotlib.org/stable/api/backend_agg_api.html (font-cache lock detail also in the 3.4.3
  module source https://matplotlib.org/3.4.3/_modules/matplotlib/backends/backend_agg.html). Publisher:
  Matplotlib.
- [S6] *API Changes for 3.7.0 — Matplotlib documentation* —
  https://matplotlib.org/stable/api/prev_api_changes/api_changes_3.7.0.html — get_cmap deprecation.
- [S7] *API Changes for 3.9.0 — Matplotlib documentation* —
  https://matplotlib.org/stable/api/prev_api_changes/api_changes_3.9.0.html — get_cmap removal;
  matplotlib.colormaps[...] / .get_cmap recommended.
- [S8] *matplotlib.pyplot.get_cmap — Matplotlib 3.11.0 documentation* —
  https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.get_cmap.html — backward-compat status.
- [S9] *matplotlib.figure.Figure.savefig — Matplotlib 3.11.0 documentation* —
  https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.savefig.html — metadata,
  bbox_inches, dpi. Publisher: Matplotlib.
- [S10] *matplotlib.pyplot.savefig — Matplotlib 3.11.0 documentation* —
  https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html — metadata override for
  deterministic output (PDF CreationDate analogue). Publisher: Matplotlib.
- [S11] *The mplot3d toolkit — Matplotlib 3.11.0 documentation* —
  https://matplotlib.org/stable/users/explain/toolkits/mplot3d.html — add_subplot(projection="3d"),
  plot_surface, auto-registration since 3.2. (Contour/hist are standard Axes methods on the same OO
  API.) Publisher: Matplotlib.
- [S12] *Backends — Matplotlib 3.11.0 documentation* —
  https://matplotlib.org/stable/users/explain/figure/backends.html — Agg as non-interactive backend.
- [S13] *"Always close your Matplotlib figures" — Heitor's log* —
  https://heitorpb.github.io/bla/close-matplotlib-figures/ — try/finally close pattern; gc.collect
  community workaround. Reliability: LOW (personal blog) — used only for the practice/debunk framing.
- [S14] *matplotlib thread-safety vs core-dump/segfault · Issue #19608* —
  https://github.com/matplotlib/matplotlib/issues/19608 — corroborates concurrent-draw segfault risk.
  Reliability: MEDIUM (project issue tracker).
- [S15] *Release notes — Matplotlib documentation* —
  https://matplotlib.org/stable/users/release_notes.html — 3.11.0 / 3.10.x release lineage.
