# Instruction: SDD Constitution (Map-Visualizer)

## Principles Applied
Inherited: P1 (source grounding — phases read predecessor artifacts, not memory or prior context), P2 (determinism — gate conditions are explicit; no ambiguous phase transitions), P3 (systematicity — phase order and gate criteria are enumerated; each phase transition has a named decision point), P4 (consistency — same invariants and gates apply every pipeline run and every session), P6 (self-contained — all gates, invariants, and acceptance criteria stated here), P7 (reference hygiene — citations resolve to CLAUDE.md §CRITICAL invariants and .claude/instructions/python-repo-conventions.md; hook names resolve to CLAUDE.md §Hooks), P8 (this block is the P8 expression for this asset), P9 Role Separation (this instruction governs the cross-phase pipeline contract; per-agent instructions govern individual agent execution; no agent owns the constitution), P10 Exit-Status Determinism (Rule 20 requires each agent to report PASS/FAIL for each gate criterion and return EXIT STATUS at phase completion, per CLAUDE.md Operating contract), P11 Programmatic Determinism (harness hooks enforce invariants 1, 7, and 8 deterministically at the tool-use level — plans must not propose workarounds; R18/P11 canonical definition: `repo-enhancer/orchestrator.md` CONVENTIONS, do not restate), P12 Maximal-Effort Completeness (all 8 CLAUDE.md invariants and all 6 pre-implement pipeline phase gates are covered; no invariant is partial), P13 Token Economy (rules cite invariant/rule IDs rather than restating them; terse). Engineering Disciplines (R17): canonical definition at `repo-enhancer/orchestrator.md` CONVENTIONS; prompt layer = numbered gated directives with positive/negative examples; context layer = each phase reads only its predecessor artifact, not the full pipeline history; harness layer = gate conditions block phase advancement until the predecessor artifact exists and is approved.

Custom:
- C1 — Pipeline Gate Integrity: every phase must verify its predecessor artifact exists on disk and is approved before proceeding; no phase runs without its input artifact; no phase skips its predecessor regardless of perceived urgency.

Scope: applies to every Map-Visualizer coding agent (core-dev, gui-dev, access-dev, test-author, docs-writer, packaging-builder) and the active session when executing SDD pipeline phases (specify / clarify / plan / tasks / analyze / checklist / implement). The per-agent instructions own individual agent execution; this instruction owns the cross-phase contract that binds all of them.

<instructions>
  <context>
    Map-Visualizer uses the SDD pipeline: specify → clarify → plan → tasks →
    analyze → checklist → implement. This instruction is the project constitution
    — the non-negotiable contract every phase, artifact, and agent must satisfy.
    Its purpose is to keep each pipeline artifact a trustworthy handoff to the
    next phase across sessions, agents, and context windows.

    Existing reality this constitution reflects:
    - Architecture: "one core, many faces" (CLAUDE.md §Architecture). One
      headless Agg render core (`map_visualizer/core.py`) powers a PySide6 GUI
      (`map_visualizer/gui/`), a dual FastAPI+FastMCP access layer over one
      shared service (`map_visualizer/api/`), and a PyInstaller build. Every
      new capability must propagate through this architecture.
    - 8 invariants (CLAUDE.md §CRITICAL invariants 1–8) and 8 coding rules
      (.claude/instructions/python-repo-conventions.md D1–D8) are in force
      throughout every phase.
    - The central invariant is the **UI-independent, headless-renderable,
      pyplot-free core**: `map_visualizer/core.py` may import ONLY the
      permitted Agg set. A single `pyplot` or Qt import in core silently
      breaks the PyInstaller bundle and the server — the worst regression here.
    - Hooks enforce invariants mechanically (`block_pyplot_qt_in_core.py`,
      `block_secrets_and_bundles.py`, `guard_tkinter_regression.py`). Plans
      must not propose workarounds.
    - There is NO orchestrator agent. Orchestration and SDD pipeline ordering
      are coordinated through CLAUDE.md (the project operating contract).
  </context>

  <rules>
    <!-- Phase gate rules (C1: predecessor artifact must exist before each phase begins) -->

    1. Mandatory phase order. Execute phases in this order only:
       specify → clarify → plan → tasks → analyze → checklist → implement.
       No phase begins until its predecessor artifact exists on disk and is
       approved. Under no circumstances write code before spec.md, plan.md,
       and tasks.md exist and are cross-artifact-consistent.

    2. Specify gate. spec.md must state user-facing requirements (what and why)
       with explicit acceptance criteria per requirement. All requirements must
       be unambiguous when the clarify phase closes; none may remain open.

    3. Clarify gate. Every underspecified area in spec.md must be resolved
       through structured questioning before plan begins. Record every
       resolution in spec.md. A plan must not proceed while any requirement
       reads as ambiguous.

    4. Plan gate. plan.md must: (a) assign every new or modified module to its
       subsystem owner (core-dev / gui-dev / access-dev / test-author /
       docs-writer / packaging-builder); (b) state all data-model changes;
       (c) explicitly confirm that each of the 8 CLAUDE.md invariants holds
       under the plan. A plan that proposes importing pyplot, Qt, or any
       interactive backend into `map_visualizer/core.py` (violates Invariant 1),
       duplicating render math in the GUI layer (violates Invariant 3), or
       weakening loader hardening guards (violates Invariant 4) is rejected
       without modification. Instead, redesign to preserve the invariant.

    5. Tasks gate. tasks.md must list dependency-ordered, single-owner work
       items. Each item must name: its owning agent, a done criterion
       (feature-level and verifiable), and a test criterion (the specific
       test(s) that must pass before the item is marked done).

    6. Analyze gate. Before implement begins, a cross-artifact consistency
       check must verify: (a) every spec requirement is covered by at least
       one plan component; (b) every plan component appears in at least one
       task; (c) no task introduces a latent invariant violation. All
       conflicts identified here must be resolved before implement begins;
       implement does not begin with open conflicts.

    7. Checklist gate. A project-specific quality checklist covering CLAUDE.md
       Invariants 1–8 and python-repo-conventions.md Rules D1–D8 must be
       generated and run against the implementation. All items must pass, or
       be documented exceptions with a risk assessment, before the feature is
       declared done.

    <!-- Non-negotiable architecture invariants (carry through every phase) -->

    8. Headless Agg core purity (CLAUDE.md Invariant 1;
       python-repo-conventions.md D1). `map_visualizer/core.py` and
       `map_visualizer/enums.py` must import ONLY the permitted Agg set
       (`matplotlib.figure.Figure`, `matplotlib.backends.backend_agg.
       FigureCanvasAgg`, `matplotlib.colormaps`, `matplotlib.colors`,
       `matplotlib.image`). NEVER `matplotlib.pyplot`; NEVER Qt/Tk/any
       interactive backend. Every plan and task that touches core.py must
       explicitly confirm this invariant holds after the change. The
       `block_pyplot_qt_in_core.py` hook (PreToolUse) enforces this
       mechanically; plans must not propose workarounds.

    9. Render validity (CLAUDE.md Invariant 2; python-repo-conventions.md D3).
       `render()` must return valid bytes — PNG by default (magic
       `\x89PNG\r\n\x1a\n`); a requested vector format returns valid
       `<?xml`/`<svg` or `%PDF` bytes. No plan or task may change render()
       to return partial, empty, or unvalidated bytes.

    10. Shared render math (CLAUDE.md Invariant 3;
        python-repo-conventions.md D2). Render logic lives in core behind
        `draw_*` Axes helpers; the GUI calls the SAME helpers. Under no
        circumstances may a plan duplicate render math in `map_visualizer/gui/`.
        Instead: place the logic in a `draw_*` helper in core.py, call it
        from the GUI canvas.

    11. Loader hardening (CLAUDE.md Invariant 4;
        python-repo-conventions.md D5). Ragged / empty / all-NaN / oversize
        (`max_cells`) inputs must continue to raise the typed errors
        (`GridLoadError`, `GridValidationError`). `max_cells` is server-side
        and fixed; clients cannot raise it. A render-time bound is additive,
        never a replacement for the load guard. Under no circumstances may a
        plan weaken these guards.

    12. 422 mapping (CLAUDE.md Invariant 5; python-repo-conventions.md D4).
        All four typed core exceptions (`GridLoadError`, `GridValidationError`,
        `InvalidParameterError`, `RenderError`) must map to HTTP 422 with
        `{error, message}` in the REST layer; the MCP path raises a typed
        `isError`. No client input may escape to an unhandled HTTP 500. Under
        no circumstances may a plan add broad `except Exception` handlers that
        swallow typed errors in a route.

    13. max_cells server-side (CLAUDE.md Invariant 6). Clients cannot raise
        `max_cells`; a render-time bound is additive to, never a replacement
        for, the load guard. A plan that exposes `max_cells` as a client
        parameter is rejected.

    14. PyInstaller excludes (CLAUDE.md Invariant 7;
        python-repo-conventions.md D8). `tkinter`, `backend_tkagg`, `wx`,
        `gtk`, `PyQt5`, `PyQt6`, `PySide2` remain excluded from the bundle.
        Under no circumstances may a plan remove or comment out these excludes.
        The `guard_tkinter_regression.py` hook (PreToolUse) enforces the
        Tkinter/legacy regression boundary.

    15. No secrets or build artifacts (CLAUDE.md Invariant 8;
        python-repo-conventions.md D8). Under no circumstances do commits
        include credentials, tokens, keys, `.env` content, or build output
        (`packaging/bin/`, `packaging/work/`). The `block_secrets_and_bundles.py`
        hook (PreToolUse) enforces this. All commits land on the enhancement
        branch (enhancement/*), never main or master.

    <!-- Cross-cutting standards (apply throughout the pipeline) -->

    16. Stdlib/pathlib first. Plans must not propose adding a dependency for
        something stdlib covers. Any new dependency must appear in
        `pyproject.toml` under the correct optional group with a pinned range
        and a one-line rationale.

    17. Type all public APIs. Every new public function/method in `core.py`,
        `api/service.py`, and new helpers must carry parameter and return type
        hints. A task is not done if its public surface is untyped.

    18. Deterministic, offline tests (python-repo-conventions.md D6). Tests
        use fixed inline grids and assert on magic bytes / `array.shape` /
        artist counts — never on a network, wall clock, random seed, or
        rendered pixel content. The access layer is exercised in-process
        (ASGI `httpx.AsyncClient`), not over a live socket.

    19. Coverage gate (CLAUDE.md §Gate commands; python-repo-conventions.md
        D7). The gate is `--cov-fail-under=90` on `map_visualizer` with
        `gui/*` and `api/*` omitted (configured in `pyproject.toml`). No plan
        or task may lower the threshold, widen the omit list, or defer tests
        to a later task. Every implement task ships its tests in the same work
        item. The `coverage_gate_reminder.py` hook (PostToolUse) surfaces this.

    <!-- Acceptance gates: what "done" means -->

    20. A feature is "done" only when all of the following hold, reported as
        explicit PASS/FAIL per criterion in the agent's phase completion
        output, followed by an EXIT STATUS payload:
        (a) cross-artifact analysis (Phase 5) is complete and all conflicts
            resolved (analyze gate — PASS);
        (b) project checklist (Phase 6) is run and all items pass
            (checklist gate — PASS);
        (c) `python -m pytest` passes with `--cov-fail-under=90` on
            `map_visualizer` (coverage gate — PASS);
        (d) all 8 CLAUDE.md invariants hold — hooks verify invariants 1, 7,
            and 8 mechanically; agents verify 2–6 before reporting PASS;
        (e) all changes committed on the enhancement branch, never main/master
            (branch gate — PASS).
  </rules>

  <conditional_rules>
    - If a plan touches `map_visualizer/core.py` or `map_visualizer/enums.py`,
      then tasks.md must include an explicit "Agg-purity re-check" task
      (owner: core-dev; done criterion: "no pyplot/Qt/Tk import added to
      core.py or enums.py") as a prerequisite for every other task that
      modifies core.py.
    - If a plan introduces or modifies a render mode (`draw_*` helper), then
      tasks.md must include a "GUI-canvas integration check" task (owner:
      gui-dev; done criterion: "GUI canvas calls the same core draw_* helper;
      no render math duplicated in gui/") before any downstream GUI task is
      marked done (Rule 10).
    - If a plan adds or modifies client-input validation, then tasks.md must
      include a "422-mapping contract test" task (owner: test-author; done
      criterion: "typed exception maps to HTTP 422 {error, message} and MCP
      isError") before any other access-layer task is marked done (Rule 12).
    - If the coverage gate drops below 90% at any point during implement, then
      halt the phase, report the gap, and escalate to the user; do not advance
      or merge (Rule 19).
    - If a task requires a new dependency, then the `pyproject.toml` entry
      (and PyInstaller spec hidden-imports update, if needed) is part of the
      same task, not a follow-up task (Rule 16).
  </conditional_rules>

  <output_format>
    At each phase gate: report PASS or FAIL for each gate criterion (Rules
    2–7). At implement completion: report PASS or FAIL for each acceptance
    gate criterion (Rule 20a–e). End with the agent's EXIT STATUS payload.
  </output_format>

  <examples>
    <example>
      <input>Plan: add a row-profile render mode that plots Z[row, :] for
      a user-specified row index.</input>
      <output>
        Accepted. plan.md assigns the change to core-dev (core.py: new
        `draw_profile` Axes helper) and access-dev (api/: expose via
        service.py; raise InvalidParameterError for out-of-range row).
        Data model: new `row` typed parameter on the render call.
        Invariant check: (1) core.py gains no pyplot/Qt import — PASS;
        (2) render() returns valid PNG bytes — PASS; (3) draw_profile
        lives in core; GUI will call it — PASS; (4) loader hardening
        unaffected — PASS; (5) InvalidParameterError → 422 — PASS;
        (6–8) unaffected — PASS. tasks.md entry: owner=core-dev,
        done="draw_profile(ax, Z, row) renders correct line plot",
        test="test_core.py asserts line count == 1 and data range correct".
        Agg-purity re-check task and 422-mapping contract test included.
      </output>
    </example>
    <example>
      <input>Plan: add row-profile by duplicating the imshow logic in
      gui/canvas.py to avoid changing core.</input>
      <output>
        Rejected (Rule 10 — shared render math). Render logic that belongs
        in core must not live in the GUI layer. Instead: add a `draw_profile`
        helper to core.py, call it from gui/canvas.py, and surface it via
        api/service.py so access-dev inherits it. No render math in gui/.
      </output>
    </example>
  </examples>
</instructions>

<!--
  SOURCES:
  - User requirement: SDD constitution instruction governing pipeline gates
    and invariants for Map-Visualizer (Group E, step 17).
  - CLAUDE.md §CRITICAL invariants 1–8, §Architecture, §Gate commands, §Hooks:
    existing repo reality (8 invariants, headless-Agg-core architecture,
    coverage gate, branch policy, hook roster).
  - .claude/instructions/python-repo-conventions.md D1–D8: coding rules
    carried through every pipeline phase.
  - asset-metaprompting/references/software-development.md §2: SDD phase
    definitions (specify/clarify/plan/tasks/analyze/checklist/implement)
    and the gate-before-proceed property.
  - templates/claude_instruction.md: structural template.
  - repo-enhancer/orchestrator.md CONVENTIONS R17 (Engineering Disciplines)
    and R18/P11 (Programmatic Determinism): canonical definitions (cited,
    not restated).
-->
