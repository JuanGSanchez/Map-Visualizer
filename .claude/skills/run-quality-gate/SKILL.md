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
its verdict. Obeys `.claude/instructions/python-repo-conventions.md` D7 (gate is
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
- P2 determinism (fixed commands, identical inputs → identical verdict), P3 systematicity,
  P5 context budget (summary lines only), P7 reference hygiene.

## Sources
- `pyproject.toml` (gate config + omit), `CLAUDE.md` § Gate commands, `map_visualizer/{core,enums}.py`,
  `.claude/instructions/python-repo-conventions.md`.
