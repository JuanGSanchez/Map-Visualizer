---
name: map-visualizer-maintainer
description: >
  RETIRED — superseded by the role-decomposed maintenance roster. Do NOT
  dispatch this agent. Implementing a docs/BACKLOG.md item end-to-end now spans
  the specialized role agents below; route each capability to its owner. Kept as
  a redirect stub so existing references resolve.
tools: Read
principles_applied:
  inherited:
    - P4 — Consistency
    - P6 — Self-Containment
    - P7 — Reference Hygiene
  custom: []
---

# map-visualizer-maintainer — RETIRED (redirect)

This monolithic maintainer has been decomposed into a non-redundant role roster.
Route a `docs/BACKLOG.md` item by its capability tag to the owning agent:

| Capability | Owner |
|---|---|
| edit headless render core / add render mode (headless core) | `map-visualizer-core-dev` |
| edit PySide6 GUI | `map-visualizer-gui-dev` |
| add MCP tool + REST route returning PNG / extend render params / add Pydantic boundary validator | `map-visualizer-access-dev` |
| add / fix pytest cases · run the coverage gate | `map-visualizer-test-author` |
| regenerate PyInstaller spec / gitignore + repo hygiene (packaging) | `map-visualizer-packaging-builder` |
| edit docs / README | `map-visualizer-docs-writer` |
| final PASS/FAIL correctness + headless-purity verdict | `map-visualizer-reviewer` |

Operating the running service (render/stats/discovery) remains `map-visualizer-operator`.
Shared rules live in `.claude/instructions/{ai-execution-discipline,python-repo-conventions}.md`.

## Principles Applied
- P4 Consistency — one redirect so the roster has a single, current set of owners.
- P6 Self-Containment — the routing table is complete here.
- P7 Reference Hygiene — preserves resolvability for any asset still naming this file; points to live owners.

## Sources
- The role roster in `.claude/agents/map-visualizer-*-dev.md`, `-test-author.md`, `-packaging-builder.md`, `-docs-writer.md`, `-reviewer.md`.
- `CLAUDE.md` (authoritative roster + capability map).
