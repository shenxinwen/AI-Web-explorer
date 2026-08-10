# Active Project Documentation Alignment Design

## Goal

Make the active project documentation accurately describe the current `main` branch after checkpoint integration, while reducing repetition and keeping historical decisions clearly separated from current behavior.

## Scope

Update only the active project documents:

- `docs/current-project-overview.zh-CN.md`
- `docs/current-project-overview.md`
- `docs/project-structure.zh-CN.md`
- `docs/project-structure.md`
- `docs/project-decisions.zh-CN.md`

Historical specifications and implementation plans under `docs/superpowers/` remain unchanged except for this design and its implementation plan.

## Current facts to align

- Real generic Stagehand exploration is forward-only and does not use browser-back recovery.
- The requested maximum step count is the main real-run limit.
- Current-state candidate exhaustion may still end a run early.
- The generic controller retains an optional consecutive-unproductive-step limit, but the real Stagehand runner currently disables it.
- Every completed action refreshes the latest embedding, trace, graph, and evidence checkpoint.
- Normal completion writes a final checkpoint with `graph.meta.exploration_summary`, including `requested_steps`, `steps_completed`, and `stop_reason`.
- Checkpointing preserves completed exploration only; it does not provide resume, replay, or per-step history.
- State matching, node materialization, PDDL behavior, and planning abstraction are not changed by this documentation task.

## Content cleanup rules

- Put current behavior before historical explanation.
- Keep one authoritative explanation per topic in each overview/structure document; replace nearby repetition with a short reference or remove it when no information is lost.
- Use consistent terms: `forward-only`, `current_state_exhausted`, `checkpoint`, `exploration_summary`, `Visual Delta`, `PlanningState`, and `Phase A`.
- Do not describe optional controller behavior as active real-run behavior.
- Preserve decision history, but mark superseded runtime effects explicitly instead of silently rewriting history.
- Keep the overview focused on status, boundaries, current problems, and next priorities; keep detailed module/function ownership in the structure documents.
- Do not expand the documents with new architecture proposals.

## Verification

- Search all five documents for stale claims about browser back and mandatory consecutive-unproductive termination.
- Confirm checkpoint and final summary descriptions match the current code.
- Confirm Chinese and English overview/structure documents describe the same current behavior.
- Run `git diff --check` and inspect the final document diff for accidental historical or architectural changes.
