---
name: expose-op
description: >
  Expose an existing Map-Visualizer core function as a dual MCP tool + REST route
  that returns PNG (or JSON), over the SINGLE shared service module, with a
  Pydantic boundary validator so every malformed client input maps to HTTP 422
  {error, message} / MCP isError (never a 500), the inline-grid-only contract
  preserved, and pytest cases proving the 422 boundary in-process. Use when a
  backlog item adds a new agent-accessible operation (e.g. overlay render, line
  profile, ROI crop) over the access layer.
---

# Skill: expose-op

Wires one core function onto MCP + REST with a clean 422 boundary. Operated by
`map-visualizer-access-dev`. Obeys `.claude/instructions/python-repo-conventions.md`
(D4 typed→422, D5 inline-grid-only) and `ai-execution-discipline.md`.

## When to use
A `docs/BACKLOG.md` item tagged "add MCP tool + REST route returning PNG" or "add
Pydantic boundary validator" (e.g. MV-I08 overlay, MV-I09 line-profile/`/profile`,
MV-I10 ROI, the MV-B04 422 fix).

## Workflow
1. **Intake.** Read the item by ID; the core function it exposes must already exist (else request `map-visualizer-core-dev` first). Restate the acceptance criterion. No ID → stop and ask.
2. **Locate.** Grep the request model, the `_core_error_to_422` catch set, the `post_render` `Image` override, and the deref points (`[0]`/`[1]`). Read only those regions. State assumptions (which model, which catch set, which transport).
3. **Service.** Add/extend the function in the shared `service.py` so MCP and REST both call it — no per-transport render logic.
4. **REST route + model.** Add the route and a Pydantic request model with a validator enforcing shape/type (e.g. `conlist(float, min_length=2, max_length=2)`, positive-int bins, in-bounds endpoints). Add a defense-in-depth service guard raising `InvalidParameterError` BEFORE any deref. Keep the catch set exactly the four typed exceptions → 422 `{error, message}`. Keep inline-grid-only (no server paths).
5. **MCP tool.** Expose it via FastMCP; `post_render`-style image tools return a FastMCP `Image(format="png")`; `isError` propagates the typed message. Vector/JSON variants set the REST `media_type`; document MCP stays PNG.
6. **Tests (in-process).** Add `httpx.AsyncClient` ASGI cases asserting: the happy path returns valid PNG/JSON; EACH malformed shape (`[5]`, `[1,2,3]`, `["a","b"]`, inverted/out-of-bounds) returns 422 (not 500) with `{error, message}`; MCP raises `isError`.
7. **Gate + import.** `python -m pytest` green; `python -c "import map_visualizer.api.rest, map_visualizer.api.mcp_server"` clean. Confirm no client input path can 500.
8. **Docs.** Update `docs/agent-operating-doc.md` tool table + error table to the shipped route/tool.

## Done = all of: happy-path + every-malformed-shape→422 proven in-process, gate green, no 500 escape, docs in sync.

## Principles Applied
P1 Source-of-Truth Grounding | P2 Full Determinism | P3 Systematicity | P4 Consistency |
P5 Context Budget Discipline | P6 Self-Containment | P7 Reference Hygiene |
P8 Principles Inheritance | P9 Role Separation | P10 Exit-Status Determinism |
P11 Programmatic Determinism | P12 Maximal-Effort Completeness | P13 Token Economy.
- P1 grounding (real model/route symbols; Grep before writing), P2 determinism (in-process
  offline ASGI tests; fixed commands), P3 systematicity (fixed boundary-first order: service →
  REST model+validator → MCP tool → tests → gate → docs), P4 consistency (one shared service
  for both transports; reuses the typed→422 pattern), P5 context budget (Grep to locate then
  Read only the deref + catch-set region), P6 self-containment, P7 reference hygiene,
  P12 maximal completeness (every malformed-shape case proven in-process before done).
- R17 Engineering Disciplines — prompt/context/harness layers; canonical reference:
  `repo-enhancer/orchestrator.md` CONVENTIONS.

## Sources
- `docs/BACKLOG.md` (access items), `map_visualizer/api/{service,rest,mcp_server,main}.py`,
  `docs/agent-operating-doc.md` (tool/error tables), `tests/test_api.py`, `CLAUDE.md`, the two `.claude/instructions/`.
