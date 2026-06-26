# Instruction — AI Execution Discipline

Auto-applied to every Claude session in this repo. Counters literal/programmatic
execution: do the task the user *means*, prove it, and stop before irreversible or
ambiguous actions. Agents reference this file by name; they do not restate it.

## Directives

1. **Verify before you act.** Read the exact code region before editing it; Grep/Glob
   for the real symbol and its call sites first. Never edit, delete, or "fix" from
   memory or from a prompt's description alone.
2. **State assumptions.** Before a non-trivial change, name in one short block: the
   function(s) you will touch, the call sites affected, and the existing behavior that
   must be preserved. A wrong assumption is then caught before the edit, not after.
3. **Stop and confirm on irreversible or ambiguous work.** File delete/relocate,
   `git rm`, dependency-pin changes, and any destructive action get a stop-and-confirm
   plus a Grep proving no importer breaks. When a spec, index, or parameter is
   ambiguous or implied-but-absent, ask one targeted question instead of guessing the
   most plausible reading.
4. **Acceptance-criteria-driven done.** A task is done only when its stated acceptance
   criterion is demonstrably met — a passing test and a green gate — not when an edit
   applied or one command exited zero. "A render/build/edit succeeded" is not "the
   thing asked for was produced."
5. **Minimal change.** Implement only what the task requires. Do not opportunistically
   refactor, rename, or reformat untouched code; note such opportunities separately.
6. **Do not invent facts.** Versions, APIs, flags, and platform facts you do not have
   grounded are surfaced as a RESEARCH REQUEST — never guessed from memory.
7. **Context-budget discipline.** Grep then Read only the region you need; never read a
   whole large file reactively. Do not hold rendered image bytes or full command output
   in context — assert on magic bytes / shape / axis counts and report only the summary
   line. One unit of work per session; checkpoint before stopping if near the limit.

## Principles Applied
P1 Source-of-Truth Grounding | P2 Full Determinism | P3 Systematicity | P4 Consistency |
P5 Context Budget Discipline | P6 Self-Containment | P7 Reference Hygiene |
P8 Principles Inheritance | P9 Role Separation | P10 Exit-Status Determinism |
P11 Programmatic Determinism | P12 Maximal-Effort Completeness | P13 Token Economy.
- P3 Systematicity — a fixed verify → assume → confirm → prove sequence every agent follows.
- P4 Consistency — the single anti-literal-execution contract the whole roster cites once here.
- P5 Context Budget Discipline — directive §7 specifies Grep-before-Read, the Gleaner threshold
  (≥5 files → GATHERING REQUEST), and the ~70% checkpoint trigger.
- P6 Self-Containment — directives are complete; no external state assumed.
- P7 Reference Hygiene — agents cite this file by name; rules are not restated downstream.
- P8 Principles Inheritance — this instruction is inherited by all agents in the roster.
- R17 Engineering Disciplines — prompt/context/harness layers; canonical reference:
  `repo-enhancer/orchestrator.md` CONVENTIONS.
- R18/P11 Programmatic Determinism — deterministic steps (gate runs, import checks) done by
  scripts/hooks, not LLM prose; see `repo-enhancer/orchestrator.md` CONVENTIONS.

## Sources
- User requirement: every agent bakes in context-budget discipline + anti-programmatic-
  execution guardrails (verify-before-edit, assumption checks, stop-and-confirm, acceptance-driven done).
- `CLAUDE.md` § Working discipline (the repo's shared anti-literal-execution statement).
