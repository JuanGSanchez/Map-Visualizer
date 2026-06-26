---
name: run-quality-gate
description: >
  Run Map-Visualizer's full quality gate before a change is called done: pytest
  with the >=90% core-coverage threshold (gui/* and api/* omitted), the headless
  core-import check, and a grep that proves no pyplot/Qt import leaked into the
  render core. Reports the summary line and a PASS/FAIL, and NEVER lowers the
  threshold or widens the omit list to pass. Use as the deterministic gate step
  for any code change.
---

# Skill: run-quality-gate

The deterministic gate every code change passes before "done". Operated by
`map-visualizer-test-author` (custody) and used by `map-visualizer-reviewer` for
its verdict. Also serves as the **execution backend** for `.claude/skills/analyze/SKILL.md`
and `.claude/skills/checklist/SKILL.md` — those skills delegate their gate-check
step here. Obeys `.claude/instructions/python-repo-conventions.md` D7 (gate is
the contract — never weaken).

## When to use
After any core/access/test change, and as the reviewer's evidence step.

## Steps (run from repo root; report only the summary lines)
1. **Coverage gate.**
   ```bash
   cd "D:/Documentos/GitHub/Map-Visualizer" && python -m pytest
   ```
   `pyproject.toml` sets `--cov=map_visualizer --cov-report=term-missing --cov-fail-under=90` with `gui/*` and `api/*` omitted. Read the final summary: pass/fail, total coverage %, and any failing test ids. A non-zero exit or `--cov-fail-under` failure = FAIL.
2. **Headless import check.**
   ```bash
   cd "D:/Documentos/GitHub/Map-Visualizer" && python -c "import map_visualizer.core; print('core imports clean')"
   ```
   A non-zero exit = FAIL (a backend/Qt/pyplot pull or import-time error in core).
3. **Purity grep (defense in depth — the import alone can mask a lazy import).**
   ```bash
   cd "D:/Documentos/GitHub/Map-Visualizer" && grep -nE "matplotlib.pyplot|from matplotlib import pyplot|PySide6|PyQt5|PyQt6|import tkinter|backend_qt|backend_tk" map_visualizer/core.py map_visualizer/enums.py
   ```
   ANY match = FAIL (a forbidden import in the headless core).

## Rules
- **Never** edit `--cov-fail-under`, the `omit` list, or delete a failing test to reach PASS — a real failure is reported, not hidden (D7). Confirm `pyproject.toml`'s gate/omit are unchanged as part of PASS.
- Report the three results as `PASS`/`FAIL` with the summary line / matched line as evidence; do not dump full pytest output (context budget).
- Overall = PASS only if all three pass.

## Done = the three checks reported PASS/FAIL with evidence; on any FAIL, the change is NOT done.

## Principles Applied
P1 Source-of-Truth Grounding | P2 Full Determinism | P3 Systematicity | P4 Consistency |
P5 Context Budget Discipline | P6 Self-Containment | P7 Reference Hygiene |
P8 Principles Inheritance | P9 Role Separation | P10 Exit-Status Determinism |
P11 Programmatic Determinism | P12 Maximal-Effort Completeness | P13 Token Economy.
- P2 determinism (fixed commands; identical inputs → identical PASS/FAIL verdict), P3 systematicity
  (fixed three-step order: coverage → import → purity grep), P4 consistency (gate config in
  `pyproject.toml` is never weakened), P5 context budget (summary lines only — not full pytest
  output), P7 reference hygiene, P11 programmatic determinism (all three checks are deterministic
  script/Bash steps), P12 maximal completeness (overall PASS only if all three pass; no partial
  verdicts).
- R17 Engineering Disciplines — prompt/context/harness layers; canonical reference:
  `repo-enhancer/orchestrator.md` CONVENTIONS.

## Sources
- `pyproject.toml` (gate config + omit), `CLAUDE.md` § Gate commands, `map_visualizer/{core,enums}.py`,
  `.claude/instructions/python-repo-conventions.md`.
