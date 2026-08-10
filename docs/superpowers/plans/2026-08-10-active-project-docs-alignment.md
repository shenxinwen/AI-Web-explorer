# Active Project Documentation Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align and clean the five active project documents so they accurately describe the current checkpointed, forward-only `main` branch.

**Architecture:** Treat the Chinese overview as the current-status source, the Chinese structure document as the module-ownership source, and the Chinese decisions file as append-only history with explicit supersession notes. Mirror current behavior into the two English documents without copying historical detail that belongs in decisions.

**Tech Stack:** Markdown, Git, ripgrep, PowerShell.

## Global Constraints

- Modify only the five active documents named in the design.
- Preserve historical decisions; mark obsolete runtime effects instead of deleting history.
- Do not modify code, tests, experiment artifacts, PDDL, or historical specs/plans.
- Keep current behavior and future work clearly separated.
- Prefer removing repetition over adding new explanatory sections.

---

### Task 1: Align current runtime facts

**Files:**
- Modify: `docs/current-project-overview.zh-CN.md`
- Modify: `docs/current-project-overview.md`
- Modify: `docs/project-structure.zh-CN.md`
- Modify: `docs/project-structure.md`

**Interfaces:**
- Consumes: current `controller.py` and `browser_runner.py` behavior.
- Produces: matching Chinese and English descriptions of active exploration and persistence.

- [ ] **Step 1: Locate stale runtime claims**

Run:

```powershell
rg -n "browser back|backtrack|consecutive_unproductive|checkpoint|stop_reason|current_state_exhausted" docs/current-project-overview.zh-CN.md docs/current-project-overview.md docs/project-structure.zh-CN.md docs/project-structure.md
```

- [ ] **Step 2: Correct both overviews**

Make both overview documents state:

```text
real Stagehand runner: max steps + natural current-state exhaustion
generic controller: optional consecutive-unproductive limit retained
checkpoint: after each completed action; final save includes exploration_summary
not implemented: resume, replay, browser-back recovery, per-step artifact history
```

Remove English claims that active exploration performs browser back or always stops at the unproductive threshold.

- [ ] **Step 3: Correct both structure documents**

Document the controller callback, generic-runner configuration, checkpoint writer ordering, and final `graph.meta.exploration_summary`. Keep function/module details in structure rather than repeating them in overview.

- [ ] **Step 4: Inspect the Task 1 diff**

Run:

```powershell
git diff -- docs/current-project-overview.zh-CN.md docs/current-project-overview.md docs/project-structure.zh-CN.md docs/project-structure.md
```

Expected: runtime facts match in both languages; no code or historical plan files changed.

---

### Task 2: Clean repetition and clarify decision history

**Files:**
- Modify: `docs/current-project-overview.zh-CN.md`
- Modify: `docs/current-project-overview.md`
- Modify: `docs/project-structure.zh-CN.md`
- Modify: `docs/project-structure.md`
- Modify: `docs/project-decisions.zh-CN.md`

**Interfaces:**
- Produces: concise current documents and unambiguous supersession notes.

- [ ] **Step 1: Consolidate repeated overview statements**

In each overview, keep detailed stop/checkpoint behavior once in the current-status or exploration section. Elsewhere use one-line summaries. Preserve design boundaries for VLM, Visual Delta, profile facts, graph memory, PDDL, and SafeSym.

- [ ] **Step 2: Keep structure focused on ownership**

Remove repeated project-status prose from structure where overview already owns it. Retain module paths, responsibilities, data flow, artifact layout, and key functions.

- [ ] **Step 3: Mark superseded decision effects**

In the 2026-08-08 forward-only decision, replace the active-sounding effect with an explicit note:

```text
The generic controller can still stop on the optional unproductive threshold; since 2026-08-10 the real Stagehand runner disables that threshold and is primarily bounded by max steps plus current-state exhaustion.
```

Keep the 2026-08-03 controller decision labelled historical and avoid rewriting what happened at that time.

- [ ] **Step 4: Normalize terminology**

Use these exact spellings consistently:

```text
forward-only
current_state_exhausted
checkpoint
exploration_summary
Visual Delta
PlanningState
Phase A
Stagehand trace
graph/evidence
```

---

### Task 3: Verify and commit the active documents

**Files:**
- Verify: all five active documents

**Interfaces:**
- Produces: one reviewable documentation commit.

- [ ] **Step 1: Scan for stale contradictions**

Run:

```powershell
rg -n "triggers browser back|browser back / visit-stack backtracking|连续无进展和最大步数共同|真实.*连续无进展.*终止" docs/current-project-overview.zh-CN.md docs/current-project-overview.md docs/project-structure.zh-CN.md docs/project-structure.md docs/project-decisions.zh-CN.md
```

Expected: no unqualified claim that the real runner uses browser back or mandatory consecutive-unproductive termination.

- [ ] **Step 2: Confirm required current facts**

Run:

```powershell
rg -n "exploration_summary|current_state_exhausted|checkpoint|forward-only" docs/current-project-overview.zh-CN.md docs/current-project-overview.md docs/project-structure.zh-CN.md docs/project-structure.md docs/project-decisions.zh-CN.md
```

Expected: overview and structure in both languages contain the active facts; decisions records the current override.

- [ ] **Step 3: Check formatting and scope**

Run:

```powershell
git diff --check
git status --short
git diff --stat
```

Expected: only the five active documents are modified and formatting is clean.

- [ ] **Step 4: Commit**

```powershell
git add docs/current-project-overview.zh-CN.md docs/current-project-overview.md docs/project-structure.zh-CN.md docs/project-structure.md docs/project-decisions.zh-CN.md
git commit -m "Align active project documentation"
```
