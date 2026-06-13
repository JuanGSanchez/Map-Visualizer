---
name: add-render-mode
description: >
  Add a new visualization mode (or a new render parameter) to Map-Visualizer end
  to end while preserving the headless Agg core: a pure draw_*/build_* helper in
  map_visualizer/core.py (no pyplot/Qt), a RenderMode/enum + typed-exception
  validation, the MCP tool + REST param wiring returning PNG with 422 on bad
  input, a GUI selector, and pytest cases that hold the >=90% core gate. Use when
  a backlog item asks for a new mode (e.g. overlay) or a render param (norm,
  colorbar, contour labels, bins, downsample, roi, annotations).
---

# Skill: add-render-mode

Adds a render mode or render parameter across the four layers in the fixed,
invariant-safe order. Operated by `map-visualizer-core-dev` (and the slice owners
it hands off to). Obeys `.claude/instructions/{ai-execution-discipline,python-repo-conventions}.md` — verify before edit, typed→422, headless purity, gate is the contract.

## When to use
A `docs/BACKLOG.md` item tagged "add render mode (headless core)" or "extend
existing REST/MCP render params" (e.g. MV-I01 norm, MV-I02 colorbar, MV-I03
contour labels, MV-I06 bins, MV-I07 downsample, MV-I08 overlay, MV-I11 annotations).

## Workflow (fixed order — core first, then out)
1. **Intake.** Read the item by ID; restate its acceptance criterion and named files. No ID → stop and ask.
2. **Locate.** Grep the real symbols (`RenderMode`, `_render_heatmap`/`_render_contour`/`draw_*`, `build_norm`, the render signature) and Read only those regions. State assumptions (which helper, which call sites, what existing behavior must hold).
3. **Core helper (headless, pure).** Add the new draw/param logic on the Agg `Figure`/`Axes` in `core.py` — `Figure.colorbar` not `pyplot.colorbar`, norms via `matplotlib.colors`, vectors via `FigureCanvasAgg`. Add the enum to `enums.py` (import-side-effect-free). Validate the param → `InvalidParameterError` (bad enum/order/bounds) or `GridValidationError` (bad shape) so it maps to 422. NEVER import pyplot/Qt into core.
4. **Access wiring.** Add the param/field to the request model with a Pydantic validator (shape/type) + a defense-in-depth service guard raising the typed exception BEFORE any deref; enum-validate values. Keep one shared service for MCP + REST; preserve the PNG return contract.
5. **GUI selector.** Add the widget in `gui/main_window.py` calling the SAME core helper — never copy render math into `gui/`.
6. **Tests.** Add deterministic offline cases: assert the mode's signal (magic bytes / `len(ax.texts|lines)` / axis count / shape) AND 422 for each invalid param shape. Cover new core branches.
7. **Gate + invariant.** Run `python -m pytest` (>=90% core, green) and `python -c "import map_visualizer.core"` (clean → no pyplot/Qt). A red gate or dirty import = NOT done; never weaken the gate or import pyplot to pass.
8. **Docs.** Update the parameter reference + error table in `docs/agent-operating-doc.md` to the shipped signature.

## Done = all of: criterion proven by a test, gate green, core import clean, docs in sync.
Stop and confirm before changing a public render signature other layers depend on (Grep importers first).

## Principles Applied
- P1 grounding (every step targets a real symbol), P3 systematicity (fixed core-first order),
  P4 consistency (reuses the typed→422 + shared-helper pattern), P6 self-containment, P7 reference hygiene.

## Sources
- `docs/BACKLOG.md` (mode/param items), `map_visualizer/{core,enums}.py`, `map_visualizer/api/{service,rest,mcp_server}.py`,
  `map_visualizer/gui/main_window.py`, `tests/{test_core,test_api}.py`, `CLAUDE.md`, the two `.claude/instructions/`.
