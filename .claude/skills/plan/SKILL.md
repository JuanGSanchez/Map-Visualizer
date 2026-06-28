---
name: plan
description: >
  Produces the technical implementation plan (the how) from a clarified feature
  spec — identifying affected components, defining the implementation strategy,
  and enforcing the headless-Agg-core architecture and sdd-constitution.md gates.
  Use this skill after `clarify` sets the spec to CLARIFIED, when the user says
  "write the plan", "plan this feature", "how do we implement this".
  Delegates all coding to core-dev / gui-dev / access-dev agents; writes no code.
version: 0.1.0
principles_applied:
  inherited:
    - P1 — Source-of-Truth Grounding
    - P2 — Full Determinism
    - P3 — Systematicity
    - P4 — Consistency
    - P5 — Context Budget Discipline
    - P6 — Self-Containment
    - P7 — Reference Hygiene
    - P8 — Principles Inheritance
    - P9 — Role Separation
    - P10 — Exit-Status Determinism
    - P11 — Programmatic Determinism
    - P12 — Maximal-Effort Completeness
    - P13 — Token Economy
  refs:
    - "R17 Engineering Disciplines; R18=P11 Programmatic Determinism: D:/Documentos/Recursos/Recursos IA/Repo Enhancer/repo-enhancer/orchestrator.md CONVENTIONS"
  custom:
    - id: C1
      name: Headless Agg Core Purity
      requires: the plan must not introduce pyplot, Qt, Tk, or any interactive-backend
        import into map_visualizer/core.py or map_visualizer/enums.py. Any render
        or draw_* logic change is scoped to core.py; any GUI wiring to
        map_visualizer/gui/; any transport wiring to map_visualizer/api/. A plan
        component that violates layer separation is flagged and must be redesigned
        before tasks are derived.
      rationale: The headless Agg core is the central Map-Visualizer invariant
        (CLAUDE.md Invariant 1); a pyplot or Qt import in core silently breaks the
        PyInstaller bundle and server render — the most damaging possible regression.
---

# Plan

Derives the technical implementation plan (the how) from a clarified spec, enforcing headless-Agg-core architecture and all 8 CLAUDE.md invariants.

## Workflow

### Step 1: Gate — spec.md must be CLARIFIED
Read `.claude/sdd/spec.md`. If it does not exist or Status is not CLARIFIED, STOP: "Run `specify` then `clarify` first."

### Step 2: Load governing instructions (just-in-time)
Read `.claude/instructions/sdd-constitution.md` for project-wide gates (coverage threshold, 8 invariants, layer rules). If the feature touches `map_visualizer/core.py` or `map_visualizer/gui/`, also read `.claude/instructions/matplotlib-best-practices.md`. Load only these; do not load other instructions.

If either file is missing, note the gap in plan.md and apply C1 and the default coverage gate (≥90%) as fallback.

### Step 3: Identify affected components
For each functional requirement in spec.md, determine which layer(s) change:
- **core** (`map_visualizer/core.py`, `map_visualizer/enums.py`) — headless Agg render logic, draw_* helpers, enumerations; owner: core-dev.
- **service** (`map_visualizer/api/service.py`) — shared transport-independent wrapper; owner: access-dev.
- **api** (`map_visualizer/api/rest.py`, `map_visualizer/api/mcp_server.py`) — transport wiring; owner: access-dev.
- **gui** (`map_visualizer/gui/`) — embedded canvas, thin client; owner: gui-dev.
- **tests** (`tests/`) — always affected; owner: test-author.
- **packaging** (`packaging/`) — PyInstaller spec; owner: packaging-builder (only if bundle changes).

Verify C1: no core or enums component change introduces a pyplot/Qt/Tk/interactive-backend import.

Shared-render-math check (CLAUDE.md Invariant 3): if the requirement adds or modifies a draw_* render helper, confirm it lives in core.py and is called from gui/ — not duplicated in gui/.

Loader-hardening check (CLAUDE.md Invariant 4): if the requirement touches grid loading or input validation, confirm typed errors (GridLoadError, GridValidationError) still fire for all edge cases and max_cells remains server-side (Invariant 6).

422-mapping check (CLAUDE.md Invariant 5): if the requirement introduces new error conditions, confirm all four typed exceptions map to HTTP 422 / MCP isError.

### Step 4: Define implementation strategy
For each affected component describe:
- What changes (function/class/field additions or modifications).
- New data contracts (typed parameters) if any.
- How default behaviour is preserved for callers that do not pass the new option.
- Owner agent: `core-dev`, `gui-dev`, `access-dev`, `test-author`, `docs-writer`, or `packaging-builder`.

Keep descriptions at "what changes and why" — no code. Cite existing identifiers (e.g. `render`, `draw_heatmap`, `list_colormaps`) only if they exist in the repo.

### Step 5: Write .claude/sdd/plan.md
Create or overwrite `.claude/sdd/plan.md` using the output format below.

## Output Format

`.claude/sdd/plan.md`:

```
# Implementation Plan: <Feature Name>
Spec: .claude/sdd/spec.md (CLARIFIED)
Date: <YYYY-MM-DD>

## Affected Components
| Component                             | Change summary | Owner agent  |
|---------------------------------------|----------------|--------------|
| map_visualizer/core.py                | …              | core-dev     |
| map_visualizer/api/service.py         | …              | access-dev   |
...

## Implementation Strategy
### <Component>
<What changes, data contracts, default-preservation approach>

## Architecture Gate Checks
- Headless Agg core purity (Invariant 1/C1): PASS | FAIL — <reason if FAIL>
- Render validity (Invariant 2): PASS | FAIL — <reason>
- Shared render math (Invariant 3): PASS | FAIL — <reason>
- Loader hardening (Invariant 4): PASS | FAIL — <reason> (only if loader touched)
- 422 mapping (Invariant 5): PASS | FAIL — <reason> (only if error path touched)
- max_cells server-side (Invariant 6): PASS | FAIL — <reason>
- PyInstaller excludes (Invariant 7): PASS | N/A — <reason>
- No secrets or artifacts (Invariant 8): PASS
- Coverage gate feasibility: <expected coverage delta>

## Component Sequencing
<Which component must be complete before which>
```

Summary line emitted after write: `plan.md written — <N> components, invariant gate checks: PASS|FAIL.`

## Self-Containment Index

This skill package contains everything needed for its complete usage:
- SKILL.md (this file): workflow, output format

External dependencies:
- `.claude/sdd/spec.md` — input artifact (Status: CLARIFIED).
- `.claude/instructions/sdd-constitution.md` — project-wide gates and all 8 invariants; loaded in Step 2. If missing: apply C1 and default coverage gate; note gap.
- `.claude/instructions/matplotlib-best-practices.md` — Agg render-core guidance; load only if a requirement touches `map_visualizer/core.py` or `map_visualizer/gui/`. If missing: apply conservative Agg discipline (no pyplot/Qt in core; per-request Figure; lock pattern); note gap.
- `.claude/agents/map-visualizer-core-dev.md`, `map-visualizer-gui-dev.md`, `map-visualizer-access-dev.md` — referenced for owner assignment. If any is missing: assign by layer convention (core-dev for core/enums; gui-dev for gui/; access-dev for api/).

## Sources
- User requirement: SDD pipeline stage-3 skill (plan) for Map-Visualizer Group E.
- SDD pipeline: asset-metaprompting `references/software-development.md §2`.
- Map-Visualizer layer conventions: `map_visualizer/` directory structure, CLAUDE.md.
- `references/claude.md §SKILL`; `templates/claude_skill.md`.
- `D:/Documentos/Recursos/Recursos IA/Repo Enhancer/repo-enhancer/orchestrator.md` CONVENTIONS (R17/R18).
