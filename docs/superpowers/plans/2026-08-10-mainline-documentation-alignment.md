# Mainline Documentation Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the five active project documents consistently describe the agreed VLM-to-Raw-Graph-to-Planning-Graph-to-Phase-A mainline.

**Architecture:** Reorganize existing active documentation instead of adding another entry document. Overview files explain the current pipeline, boundaries, status, and open questions; structure files map the same pipeline to code and artifacts; the decisions log records the new governing decision and marks conflicting history as superseded.

**Tech Stack:** Markdown, Git, ripgrep, PowerShell. Documentation-only change.

## Global Constraints

- Follow `docs/superpowers/specs/2026-08-10-mainline-documentation-alignment-design.md` exactly.
- Modify only the five active documents listed below.
- Do not modify source code, tests, experiment outputs, historical specs, or historical plans.
- Do not run a real browser experiment.
- Preserve historical decisions, but explicitly mark directly conflicting statements as superseded.
- Keep Chinese and English overview/structure semantically aligned.
- Treat Visual Delta as an observer; document its current categories as implemented but still pending taxonomy review.
- Do not create another active documentation entry point.

## File Structure

- Modify `docs/current-project-overview.zh-CN.md`: canonical Chinese explanation of the mainline, current status, limitations, and next validation.
- Modify `docs/current-project-overview.md`: semantic English counterpart.
- Modify `docs/project-structure.zh-CN.md`: Chinese module, artifact, and data-flow mapping.
- Modify `docs/project-structure.md`: semantic English counterpart.
- Modify `docs/project-decisions.zh-CN.md`: new governing decision plus superseded-history markers.

---

### Task 1: Reorganize The Current Overviews

**Files:**
- Modify: `docs/current-project-overview.zh-CN.md`
- Modify: `docs/current-project-overview.md`

- [ ] **Step 1: Add the agreed end-to-end mainline near the start**

Use this semantic sequence in both languages:

```text
VLM proposes possible business actions
-> local memory selects one candidate
-> Stagehand attempts the selected action
-> after-action observation verifies the visible result
-> local verifier confirms known profile boundaries
-> raw graph preserves stable observations and auditable outcomes
-> planning abstraction groups only strongly supported equivalents
-> planning graph aggregates candidate capabilities with provenance
-> Phase A emits cross-state transitions into domain.pddl
```

- [ ] **Step 2: Make evidence levels explicit**

State that a VLM affordance is a candidate, a Stagehand result is an execution report, and after-action observation is the evidence used to classify the graph outcome. Do not call every candidate a verified capability.

- [ ] **Step 3: Correct current-status wording**

Replace claims that planning-state merging is absent with: implementation and tests exist, while real-browser validation is still pending. Describe exploration as forward-only; current-route exhaustion does not prove site-wide coverage.

- [ ] **Step 4: Align boundaries and open issues**

Cover Raw Graph versus Planning Graph, profile facts, embedding, sidecars, checkpoint, and Phase A exclusions. Mark Visual Delta taxonomy quality as the one explicit pending design discussion.

- [ ] **Step 5: Remove duplicated or superseded overview text**

Keep one canonical explanation per concept. Preserve useful experiment history only when labeled historical and not evidence of the current implementation.

- [ ] **Step 6: Compare Chinese and English sections**

Check that both versions make the same claims even when wording differs.

- [ ] **Step 7: Commit**

```powershell
git add docs/current-project-overview.zh-CN.md docs/current-project-overview.md
git commit -m "Align project overviews with current mainline"
```

---

### Task 2: Align Structure Documents With Runtime Ownership

**Files:**
- Modify: `docs/project-structure.zh-CN.md`
- Modify: `docs/project-structure.md`

- [ ] **Step 1: Align the layer map**

For each layer, identify its owner and boundary: VLM observation, local selection/memory, Stagehand execution, after-action verification, Raw Graph/evidence, checkpoint persistence, planning abstraction, Phase A projection.

- [ ] **Step 2: Correct capability terminology**

Document that `business_affordances` are observed candidates. Successful edges verify transitions. Planning groups aggregate candidate capabilities and retain exact observation provenance; they do not claim every action is executable from every raw observation.

- [ ] **Step 3: Align artifact ownership**

Document `graph.json`, `graph_evidence.json`, embeddings, Stagehand trace, `raw_graph.json`, `planning_graph.json`, `planning_abstraction_report.json`, and `domain.pddl`, including which consumers may depend on each.

- [ ] **Step 4: Rewrite the key data flow**

Ensure it shows per-step checkpoint before offline planning abstraction and shows Phase A consuming the planning graph, not the evidence sidecar.

- [ ] **Step 5: Remove stale active paths and concepts**

Search for removed modules, browser-back recovery, active DFS recovery, old canonical/consolidation terminology, and any statement that Visual Delta or supporting facts enter Phase A.

- [ ] **Step 6: Verify mentioned active module paths exist**

Use PowerShell `Test-Path` or `rg --files`; historical compatibility names may remain only when explicitly labeled historical.

- [ ] **Step 7: Commit**

```powershell
git add docs/project-structure.zh-CN.md docs/project-structure.md
git commit -m "Align project structure with current mainline"
```

---

### Task 3: Record The Governing Decision And Validate

**Files:**
- Modify: `docs/project-decisions.zh-CN.md`

- [ ] **Step 1: Add a 2026-08-10 governing decision**

Record the agreed mainline, evidence levels, Raw/Planning Graph split, profile/embedding limits, forward-only exploration, checkpoint boundary, Phase A exclusions, and pending Visual Delta taxonomy review.

- [ ] **Step 2: Mark conflicting history as superseded**

Do not erase history. Add concise replacement notes to decisions that describe active browser back/DFS recovery, candidate-set completeness, direct VLM planning authority, supporting-fact PDDL preconditions, or removed business-state policy paths.

- [ ] **Step 3: Run documentation searches**

```powershell
rg -n "business_state_policy.py|resolve_business_target_node|behavior_state_graph.py|browser back|DFS recovery|supporting_facts.*precondition|candidate.*verified" docs/current-project-overview.zh-CN.md docs/current-project-overview.md docs/project-structure.zh-CN.md docs/project-structure.md docs/project-decisions.zh-CN.md
```

Every remaining hit must be either current, explicitly historical, or explicitly superseded.

- [ ] **Step 4: Check links, module paths, and formatting**

Run:

```powershell
git diff --check
git status --short
```

Review the complete documentation diff. Confirm no source, test, output, spec, or plan file changed during execution.

- [ ] **Step 5: Commit**

```powershell
git add docs/project-decisions.zh-CN.md
git commit -m "Record aligned project mainline"
```

## Final Acceptance Checklist

- [ ] A reader can follow one consistent end-to-end mainline across all active documents.
- [ ] Candidate affordances are not described as automatically verified transitions.
- [ ] Raw observations and planning states have separate responsibilities.
- [ ] Embedding, profile facts, Visual Delta, Stagehand, sidecars, and checkpoint stay within their agreed boundaries.
- [ ] Forward-only exploration is not presented as complete site traversal.
- [ ] Planning abstraction is described as implemented and unit-tested but not yet real-experiment validated.
- [ ] Phase A exclusions match current code and agreed scope.
- [ ] Visual Delta taxonomy remains an explicit pending review item.
- [ ] Conflicting historical decisions are preserved but marked superseded.
- [ ] Only the five active documents changed.
