# Instruction: Matplotlib/Agg Best Practices (Map-Visualizer)

## Principles Applied
Inherited: P1 (source grounding — every directive references a source from research report RR-1; no API name or version number invented beyond RR-1's scope; citations carry traceable URLs), P2 (determinism — named render idioms and thread patterns; binary lock-vs-process-pool choice; no ambiguous "it depends" phrasing), P3 (systematicity — decision points enumerated in conditional_rules; each pattern has a named choice condition), P4 (consistency — same idioms across every core-dev/gui-dev session; one best-practices instruction for this framework), P6 (self-contained — all directives, source citations, and API-currency gotchas stated here; RR-1 path and sources are explicit), P7 (reference hygiene — all [S*] cites resolve to RR-1 §Sources; hook names resolve to CLAUDE.md §Hooks; no filler), P8 (this block is the P8 expression for this asset), P9 Role Separation (this instruction governs the matplotlib/Agg layer only; GUI embedding in map_visualizer/gui/ remains a thin canvas client; python-repo-conventions.md D1 is the source of the Agg-only mandate; this instruction does not duplicate it), P10 Exit-Status Determinism (n/a — this instruction does not mandate an exit-status output format; agents operating under it return EXIT STATUS per CLAUDE.md Operating contract), P11 Programmatic Determinism (directives direct core-dev toward the explicit object API and thread patterns rather than pyplot global state or ad-hoc threading; block_pyplot_qt_in_core.py hook enforces the import boundary mechanically; R18/P11 canonical definition: `repo-enhancer/orchestrator.md` CONVENTIONS, do not restate), P12 Maximal-Effort Completeness (all seven technical areas from RR-1 are covered: version pins, headless object API, figure lifecycle, thread safety, colormap currency, render modes, deterministic output), P13 Token Economy (cite [S*] IDs from RR-1 rather than restating source text; terse directives). Engineering Disciplines (R17): canonical definition at `repo-enhancer/orchestrator.md` CONVENTIONS; prompt layer = grouped numbered directives with positive/negative examples; context layer = load this instruction only when core-dev or gui-dev touches map_visualizer/core.py or map_visualizer/gui/ (just-in-time); harness layer = block_pyplot_qt_in_core.py hook enforces the import boundary; decision points in conditional_rules cover the thread-pattern and render-mode choices.

Custom:
- C1 — Research Grounding: every directive in this instruction references at least one source from RR-1 (`docs/research-matplotlib-agg-best-practices.md`, compiled 2026-06-26); no matplotlib API, version number, or behavioral claim may be stated without a [S*] citation that resolves to RR-1 §Sources.

Scope: applies to core-dev (`map_visualizer/core.py` — headless Agg render core) and gui-dev (`map_visualizer/gui/` — embedded canvas) on matplotlib `>=3.11,<3.12` [S1], numpy `>=1.25` [S2], Python 3.11–3.13 [S1]. Does not govern `map_visualizer/api/` — that is governed by `.claude/instructions/python-repo-conventions.md`. Does not add a SessionStart hook or duplicate any global harness.

<instructions>
  <context>
    Map-Visualizer's render core (map_visualizer/core.py) is a headless
    matplotlib/Agg renderer: it constructs a Figure, attaches a
    FigureCanvasAgg, draws via draw_* Axes helpers, and returns PNG bytes
    — no pyplot, no global figure registry, no display server required.
    [S3]

    The GUI layer (map_visualizer/gui/) is a thin canvas client: it embeds
    a matplotlib canvas widget and calls the same core draw_* helpers that
    the headless path uses. Under no circumstances may it duplicate render
    math. (CLAUDE.md Invariant 3; python-repo-conventions.md D2.)

    Dependency pins (pyproject.toml):
      matplotlib>=3.11,<3.12   # current stable, Python 3.11–3.13 [S1]
      numpy>=1.25              # matplotlib's declared floor [S2]

    Source for all technical claims: docs/research-matplotlib-agg-best-
    practices.md (RR-1, compiled 2026-06-26). [S*] citations below resolve
    to RR-1 §Sources.
  </context>

  <rules>
    <!-- Headless Agg object API (pyplot-free) -->

    1. Use the explicit object API for all server-side rendering: construct
       matplotlib.figure.Figure(...), attach FigureCanvasAgg(fig), draw
       via Axes helpers, then emit bytes with fig.savefig(buf,
       format="png"). Do NOT call matplotlib.pyplot in
       map_visualizer/core.py or map_visualizer/enums.py — pyplot's global
       figure registry (Gcf) is a correctness and leak hazard under server
       concurrency. The block_pyplot_qt_in_core.py hook (PreToolUse)
       enforces this mechanically. [S3][S4]

    2. The canonical render idiom for the server core:
         from matplotlib.figure import Figure
         from matplotlib.backends.backend_agg import FigureCanvasAgg
         import io

         fig = Figure(figsize=figsize, dpi=dpi)
         FigureCanvasAgg(fig)            # bind Agg backend explicitly
         ax = fig.add_subplot()          # or fig.subplots()
         # ... call draw_* helper(s) on ax ...
         buf = io.BytesIO()
         fig.savefig(buf, format="png", dpi=dpi,
                     metadata={"Software": None})
         return buf.getvalue()
       This is the only sanctioned idiom for map_visualizer/core.py. [S3]

    3. Never call FigureCanvasAgg.draw() explicitly before savefig —
       savefig invokes it internally. [S3]

    <!-- Figure lifecycle and memory -->

    4. A Figure constructed with the explicit object API (Rule 1) is NOT
       held by pyplot's global registry. When its last reference goes out
       of scope, CPython's reference counting reclaims it — no plt.close()
       and no gc.collect() are needed or useful on the server path. Treat
       any gc.collect() call in the render hot-path as removable
       cargo-cult. [S3][S4][S13]

    5. If pyplot is ever unavoidable in a utility context, wrap the figure
       in try/finally: plt.close(fig). Never rely on scope exit to release
       a pyplot-registered figure. [S4][S13]

    <!-- Thread safety for server rendering -->

    6. matplotlib is NOT thread-safe. The Agg backend's font cache is
       class-level; only one canvas may draw at a time without a race or
       segfault. [S4][S5][S14]

    7. For the async FastAPI/MCP render_map handler: always construct one
       new Figure per request (never share a Figure or canvas across
       requests or threads). Combine with one of the two serialization
       patterns in Rules 8–9. [S4]

    8. Lock pattern (threadpool): place a module-level threading.Lock
       around the savefig/draw step only; figure construction may remain
       parallel:
         _RENDER_LOCK = threading.Lock()
         ...
         with _RENDER_LOCK:
             fig.savefig(buf, format="png", metadata={"Software": None})
       [S4][S5]

    9. Process-pool pattern: use concurrent.futures.ProcessPoolExecutor
       (or run_in_executor on a ProcessPoolExecutor) so each worker has
       its own matplotlib interpreter state, sidestepping the shared font
       cache entirely. Preferred when render throughput matters. [S4]

    10. For async FastAPI/MCP handlers: offload the synchronous render via
        await loop.run_in_executor(pool, _sync_render, params) so the
        event loop is never blocked. Combine with Rule 8 (threads) or
        Rule 9 (processes). [S4]

    <!-- Colormap API currency -->

    11. Use matplotlib.colormaps["name"] to look up a colormap by name.
        Do NOT use matplotlib.cm.get_cmap — deprecated in 3.7, removed in
        3.9. [S6][S7]

    12. To normalize a str / None / Colormap argument coming from user
        input:
          cmap = matplotlib.colormaps.get_cmap(user_cmap or "viridis")
        Raise InvalidParameterError before calling if the name is not
        recognized. [S6][S7][S8]

    <!-- Render modes (all Agg-safe, pyplot-free) -->

    13. All render modes use the object API (Rule 2) and are Agg-safe:
        - Heatmap:
            ax.imshow(Z, cmap=cmap, interpolation="nearest",
                      origin="lower", aspect="auto")  [S8][S11]
        - Contour:
            ax.contour(X, Y, Z, levels=<explicit array>)  [S11]
        - Filled contour:
            ax.contourf(X, Y, Z, levels=<explicit array>)  [S11]
        - 3D surface:
            ax = fig.add_subplot(projection="3d")
            ax.plot_surface(X, Y, Z, cmap=cmap)
            (mpl_toolkits.mplot3d auto-registers since mpl 3.2 — no
            explicit import needed)  [S11]
        - Histogram:
            ax.hist(values, bins=<explicit count>)  [S11]
        - Row/column profile:
            ax.plot(x, Z[row, :]) / ax.plot(y, Z[:, col])  [S3]
        Pin all discretization arguments (interpolation, levels, bins)
        explicitly — unpinned arguments produce non-deterministic bytes.

    14. Multi-panel layouts: fig.subplots(nrows, ncols) or
        fig.add_subplot(r, c, i). All Agg-safe. [S3]

    15. Render logic lives in core behind draw_* Axes helpers. The GUI
        canvas calls the same helpers. Under no circumstances may render
        math be duplicated in map_visualizer/gui/. (CLAUDE.md Invariant 3;
        python-repo-conventions.md D2.) [S3]

    <!-- Deterministic PNG output -->

    16. Produce deterministic PNG bytes on every render:
        (a) Fix figsize and dpi: Figure(figsize=(w, h), dpi=d) — both must
            be constants or caller-controlled parameters, never defaults
            that could drift.
        (b) Pass metadata={"Software": None} to savefig to strip the
            matplotlib version/date stamp it injects by default; without
            this, identical figures produce different bytes across runs and
            versions. [S9][S10]
        (c) Avoid bbox_inches="tight" — layout-dependent cropping breaks
            byte stability. Use a fixed figsize or constrained_layout
            consistently, never both. [S9]
        (d) Lock tick formatting: ax.ticklabel_format(style="plain") to
            prevent offset/scientific-notation drift on numeric axes. [S9]

    17. For render-to-image smoke tests: compare decoded RGBA arrays
        (np.asarray(canvas.buffer_rgba())) with a numeric tolerance rather
        than raw byte equality, to tolerate cross-platform freetype/libpng
        build differences. [S3][S9]
  </rules>

  <conditional_rules>
    - If choosing between the two thread-serialization patterns: threadpool
      with moderate concurrency → lock pattern (Rule 8); high-throughput
      renders where parallel execution matters → process-pool (Rule 9).
      [S4][S5]
    - If an async FastAPI/MCP handler renders: always combine per-request
      Figure (Rule 7) + run_in_executor (Rule 10) + either Rule 8 or
      Rule 9. Choosing between them: Rule 8 if the server is I/O-bound
      elsewhere and render latency is acceptable; Rule 9 if render
      throughput is the bottleneck.
    - If a new render mode is added: place the draw_* helper in core.py
      (not gui/); verify it is in the Agg-safe list (Rule 13); pin all
      discretization args for deterministic output (Rule 16). [S11]
    - If a colormap argument comes from user input: normalize with
      matplotlib.colormaps.get_cmap(user_cmap or default) (Rule 12);
      raise InvalidParameterError for unrecognized names before passing to
      the Axes method. [S6][S7]
  </conditional_rules>

  <examples>
    <example>
      <input>Add a filled-contour render mode that accepts a colormap
      name and returns PNG bytes.</input>
      <output>
        CORRECT — explicit object API + colormap currency + deterministic
        output (Rules 1–2, 11–13, 16):

          import io, threading, matplotlib
          from matplotlib.figure import Figure
          from matplotlib.backends.backend_agg import FigureCanvasAgg

          _RENDER_LOCK = threading.Lock()

          def draw_contourf(ax, X, Y, Z, levels, cmap_name):
              cmap = matplotlib.colormaps.get_cmap(cmap_name or "viridis")
              ax.contourf(X, Y, Z, levels=levels, cmap=cmap)

          def render_contourf(X, Y, Z, levels, cmap_name="viridis",
                              figsize=(6.4, 4.8), dpi=100) -> bytes:
              fig = Figure(figsize=figsize, dpi=dpi)
              FigureCanvasAgg(fig)
              ax = fig.add_subplot()
              draw_contourf(ax, X, Y, Z, levels, cmap_name)
              ax.ticklabel_format(style="plain")
              buf = io.BytesIO()
              with _RENDER_LOCK:
                  fig.savefig(buf, format="png", dpi=dpi,
                              metadata={"Software": None})
              return buf.getvalue()

        INCORRECT:
          import matplotlib.pyplot as plt       # pyplot in core (Rule 1)
          plt.contourf(X, Y, Z)                # global state (Rule 1)
          plt.savefig(buf)                      # pyplot path (Rule 1)
          gc.collect()                          # cargo-cult (Rule 4)
          cmap = matplotlib.cm.get_cmap("v")   # removed in 3.9 (Rule 11)
          fig.savefig(buf, bbox_inches="tight") # breaks byte stability (Rule 16c)
      </output>
    </example>
    <example>
      <input>Handle concurrent render_map calls in the async FastAPI
      handler.</input>
      <output>
        CORRECT — per-request Figure + run_in_executor + lock (Rules 7–8, 10):

          import asyncio, threading, io
          from matplotlib.figure import Figure
          from matplotlib.backends.backend_agg import FigureCanvasAgg

          _RENDER_LOCK = threading.Lock()

          async def render_map_endpoint(params):
              loop = asyncio.get_running_loop()
              png = await loop.run_in_executor(
                  None, _sync_render, params)   # offload blocking render
              return Response(content=png, media_type="image/png")

          def _sync_render(params):
              fig = Figure(figsize=(6.4, 4.8), dpi=100)  # per-request (Rule 7)
              FigureCanvasAgg(fig)
              ax = fig.add_subplot()
              draw_heatmap(ax, params.Z, params.cmap)     # core helper (Rule 15)
              ax.ticklabel_format(style="plain")
              buf = io.BytesIO()
              with _RENDER_LOCK:               # serialize draw (Rule 8)
                  fig.savefig(buf, format="png", dpi=100,
                              metadata={"Software": None})
              return buf.getvalue()

        INCORRECT:
          _fig = Figure(...)                   # shared across requests (Rule 7)
          async def handler():
              _fig.savefig(buf)               # race condition, no lock (Rule 6)
      </output>
    </example>
  </examples>
</instructions>

<!--
  SOURCES:
  - User requirement: matplotlib/Agg best-practices instruction for
    Map-Visualizer's core-dev and gui-dev agents, grounded in RR-1
    (Group E, step 18).
  - docs/research-matplotlib-agg-best-practices.md (RR-1, 2026-06-26):
    all technical claims and [S*] citations ([S1]–[S15]).
  - CLAUDE.md §CRITICAL invariants 1–3, §Architecture, §Hooks
    (block_pyplot_qt_in_core.py).
  - .claude/instructions/python-repo-conventions.md D1 (Agg purity),
    D2 (render-math sharing).
  - asset-metaprompting/references/software-development.md §3:
    best-practices instruction grouped structure and grounding requirement.
  - templates/claude_instruction.md: structural template.
  - repo-enhancer/orchestrator.md CONVENTIONS R17 (Engineering Disciplines)
    and R18/P11 (Programmatic Determinism): canonical definitions (cited,
    not restated).
-->
