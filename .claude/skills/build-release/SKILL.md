---
name: build-release
description: >
  Build Map-Visualizer's PyInstaller release bundle and VERIFY the toolkit
  excludes survived into the frozen output (tkinter, backend_tkagg, wx, gtk,
  PyQt5, PyQt6, PySide2 absent), keeping the build out of VCS (packaging/bin/,
  packaging/work/ gitignored, never committed). Reports the produced exe + size
  and a PASS/FAIL on excludes. Use to produce or validate a release build.
---

# Skill: build-release

Builds the frozen GUI bundle and proves the excludes held. Operated by
`map-visualizer-packaging-builder`. Obeys `.claude/instructions/python-repo-conventions.md`
D8 (excludes effective, no committed bundle/secret) and `ai-execution-discipline.md`
(stop-and-confirm before any `git rm` of an already-committed bundle).

## When to use
A `docs/BACKLOG.md` item that re-emits the spec, changes a pin (MV-B10), or
restores bundle hygiene (MV-B07); or a release verification.

## Steps (run from repo root)
1. **Pre-check.** Confirm the spec excludes are intact:
   ```bash
   cd "D:/Documentos/GitHub/Map-Visualizer" && grep -nE "tkinter|backend_tkagg|wx|gtk|PyQt5|PyQt6|PySide2" packaging/MapVisualizer.spec
   ```
   All seven must be present in the `excludes` list. A missing one = STOP (add it; never drop one).
2. **Build.**
   ```bash
   cd "D:/Documentos/GitHub/Map-Visualizer" && python packaging/build.py --clean
   ```
   Outputs to `packaging/bin/` and `packaging/work/`. Report the produced exe path + total bundle size from the build output.
3. **Verify excludes in the FROZEN bundle** (not just the spec):
   ```bash
   cd "D:/Documentos/GitHub/Map-Visualizer" && python -c "import pathlib,sys; root=pathlib.Path('packaging/bin'); bad=[p for tk in ('tkinter','PyQt5','PyQt6','PySide2','wx','gtk','backend_tkagg') for p in root.rglob('*') if tk.lower() in p.name.lower()]; print('FAIL excludes leaked:', sorted({str(p) for p in bad})) if bad else print('PASS excludes effective')"
   ```
   Any match = FAIL (an excluded toolkit leaked into the bundle).
4. **VCS hygiene.**
   ```bash
   cd "D:/Documentos/GitHub/Map-Visualizer" && git ls-files packaging/
   ```
   Must list ONLY the spec, build driver, scripts, and readme — NEVER `bin/`/`work/` binaries. Confirm `.gitignore` covers `packaging/bin/` and `packaging/work/`.

## Rules
- **Never** `git add` the built bundle or a secret. Removing an already-committed bundle (`git rm -r --cached packaging/bin packaging/work`) is destructive — stop and confirm, name what is removed, and re-run step 4 after.
- **Never** drop an exclude to fix a build — add the missing one.
- Apply a changed dependency pin only from a researcher-confirmed version (MV-B10), never from memory.

## Done = build produced, excludes PASS in the frozen bundle, and `git ls-files packaging/` shows no bundle binaries.

## Principles Applied
- P2 determinism (fixed build + verification commands), P3 systematicity,
  P5 context budget (report exe/size + PASS/FAIL, not full build log), P7 reference hygiene.

## Sources
- `packaging/MapVisualizer.spec` (excludes), `packaging/build.py`, `packaging/README-packaging.md`,
  `pyproject.toml` (pinned deps, pyinstaller), `.gitignore`, `CLAUDE.md` (invariants 7-8),
  `.claude/instructions/python-repo-conventions.md`.
