# Stagehand Tool Choice Observation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Treat the known Stagehand `tool_choice` compatibility error as an observation-required outcome, then align the three Chinese project documents with the current Phase A mainline.

**Architecture:** Keep the Stagehand backend result unchanged and derive a local `observation_allowed` decision inside `WebKobeExplorer`. Only the known compatibility error may proceed through after-state observation when the backend reports failure; URL, structural, and visual evidence then determine the edge status and target node. Unknown failures retain the existing failed-self-loop behavior.

**Tech Stack:** Python 3.11, pytest, Playwright/Stagehand adapter interfaces, WebKobeGraph, Markdown project documentation.

## Global Constraints

- Do not add fields to `WebKobeNode`, `WebKobeEdge`, `WebKobeGraph`, or other persisted graph structures.
- Do not change embedding thresholds, Visual Delta output fields, Phase A consolidation, or PDDL projection.
- Preserve `backend_reported_success=false` and the original Stagehand error in execution metadata.
- Do not solve business-affordance field overlap, Stagehand multi-step completion, URL/signature granularity, or Phase A automatic embedding calls.
- Do not run a real website experiment in this implementation task.
- Use one agent only; do not dispatch subagents.

---

### Task 1: Continue Observation for the Known Stagehand Compatibility Error

**Files:**
- Modify: `tests/safesym_bridge/test_web_kobe_explorer.py`
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`

**Interfaces:**
- Consumes: `_is_ignorable_stagehand_tool_choice_error(error: str | None) -> bool`, `AutomationBackend.execute`, `AutomationBackend.observe_state`, `VisualDeltaProvider`.
- Produces: local `observation_allowed: bool`; existing edge statuses `succeeded_with_navigation`, `succeeded_with_observed_change`, `no_observed_change`, and `failed_execution`.

- [ ] **Step 1: Replace the stale tool-choice expectations with failing integration tests**

Update `StagehandThinkingFailureVisualChangeAdapter` or add focused adapters so the known error returns `False` after changing URL/signature, while a separate adapter keeps the page unchanged. Change `test_explore_one_step_accepts_stagehand_tool_choice_error_with_visual_change` to assert:

```python
edge = graph.edges[0]
assert edge.status == "succeeded_with_observed_change"
assert edge.source_node_id != edge.target_node_id
assert edge.execution_trace.success is True
assert edge.execution_trace.error == "Thinking mode does not support this tool_choice"
assert edge.execution_trace.metadata["backend_reported_success"] is False
assert edge.execution_trace.metadata["visual_delta_trace"][
    "candidate_added_facts"
] == ["cart_has_items"]
```

Replace the stale unit expectation for `test_tool_choice_error_without_visible_change_is_non_fatal_noop`:

```python
status = explorer._edge_status(
    execution_success=False,
    execution_error=(
        "Failed to execute task: "
        "Thinking mode does not support this tool_choice"
    ),
    observed_delta=[],
)
assert status == "no_observed_change"
```

Add an `explore_one_step` integration assertion for the unchanged case:

```python
assert edge.status == "no_observed_change"
assert edge.source_node_id == edge.target_node_id
assert edge.execution_trace.error is not None
assert edge.execution_trace.metadata["backend_reported_success"] is False
```

Keep `test_failed_action_is_a_failed_self_loop_without_visual_delta_call` unchanged as the unknown-error guard.

- [ ] **Step 2: Run the focused tests and verify the current implementation fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests/safesym_bridge/test_web_kobe_explorer.py::test_explore_one_step_accepts_stagehand_tool_choice_error_with_visual_change `
  tests/safesym_bridge/test_web_kobe_explorer.py::test_tool_choice_error_without_visible_change_is_non_fatal_noop `
  tests/safesym_bridge/test_web_kobe_explorer.py::test_failed_action_is_a_failed_self_loop_without_visual_delta_call -q
```

Expected: the first two behaviors fail because the explorer currently skips after-state observation whenever `execute()` returns `False`; the unknown-failure test remains green.

- [ ] **Step 3: Implement the minimal observation gate**

Immediately after backend execution in `WebKobeExplorer.explore_one_step`, derive:

```python
execution_success = await self.adapter.execute(selected)
execution_error = getattr(self.adapter, "last_execution_error", None)
observation_allowed = execution_success or (
    _is_ignorable_stagehand_tool_choice_error(execution_error)
)
```

Use `observation_allowed`—not `execution_success`—for these existing decisions:

```python
if observation_allowed:
    after = await self._observe_after_action(
        before=before,
        before_facts=before_facts,
        execution_success=True,
    )
    # capture after screenshot, interactables, and draft
else:
    # preserve the existing ordinary-failure fallback to before state
```

```python
observed_delta = (
    _observed_delta_from_facts_or_signature(...)
    if observation_allowed
    else []
)
```

```python
if (
    observation_allowed
    and self.visual_delta_provider is not None
    and before_screenshot_path is not None
    and after_screenshot_path is not None
):
    # existing Visual Delta call
```

```python
if not observation_allowed or not state_changed:
    target_node = self.manager.node_for_id(source_id)
```

Keep metadata tied to the backend result:

```python
execution_metadata["backend_reported_success"] = execution_success
```

Update `_edge_status` in this order:

```python
if observed_delta:
    return "succeeded_with_observed_change"
if _is_ignorable_stagehand_tool_choice_error(execution_error):
    return "no_observed_change"
if not execution_success:
    return "failed_execution"
return "no_observed_change"
```

The existing visual-fact promotion then turns the known-error/no-structural-change case into `succeeded_with_observed_change` when Visual Delta is non-empty. Remove the obsolete promotion condition that requires `_planning_delta_has_fact_change(planning_delta)` for this error, because visual observations no longer enter planning deltas.

Apply a planning transition only when the observed edge is not a failed execution:

```python
if self.business_profile is not None and edge_status != "failed_execution":
    self.manager.apply_planning_transition(edge)
```

- [ ] **Step 4: Run explorer regressions**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_explorer.py -q
```

Expected: all explorer tests pass. Confirm the unknown failure still skips Visual Delta, while the known compatibility error captures an after screenshot and Visual Delta trace.

- [ ] **Step 5: Commit the behavior change**

```powershell
git add src/ai_web_explorer/grounded_web/explorer.py tests/safesym_bridge/test_web_kobe_explorer.py
git commit -m "Handle Stagehand tool choice errors by observation"
```

---

### Task 2: Align Chinese Project Documentation with the Current Mainline

**Files:**
- Modify: `docs/current-project-overview.zh-CN.md`
- Modify: `docs/project-structure.zh-CN.md`
- Modify: `docs/project-decisions.zh-CN.md`

**Interfaces:**
- Consumes: behavior implemented in Task 1; Phase A behavior graph introduced by commits `bcd956c`, `9802291`, `c9a0fa0`, and `e3aa88b`.
- Produces: current-state overview, module responsibility reference, and append-only decision record.

- [ ] **Step 1: Update the current project overview**

Edit the overview so its current-state statements explicitly say:

```text
Visual Delta only observes candidate_added_facts/candidate_removed_facts.
Visual observations remain in raw edge trace and do not enter PlanningState or Phase A PDDL.
Phase A currently projects only canonical locations and non-self-loop business transitions into domain.pddl.
Explicit URL/signature/visual change prevents target matching from merging the target back into its source node.
The known Stagehand tool_choice error triggers after-state observation; change means success, no change means no_observed_change.
Experiments overwrite outputs/experiments/<site>/latest/ unless explicitly archived.
```

Replace stale experiment claims with the latest confirmed status rather than retaining the old 8-step graph as “current.” Add this deferred item without solving it:

```text
BusinessAffordance.action_name, label, and target_hint have partially overlapping semantics and require a later schema review.
```

- [ ] **Step 2: Update the project structure document**

Correct the Visual Delta and explorer sections to state:

```text
VisualDeltaRequest prompt consumes the selected action and before/after screenshots; legacy request attributes are not prompt inputs.
New exploration does not generate VLM BusinessTransition judgments.
Visual observations are stored in execution_trace.metadata.visual_delta_trace.
Structured profile verification may still build PlanningState, but visual observations are isolated from it.
Target matching may reuse a reliable non-source history node but cannot map an explicitly changed target back to its source.
```

Do not remove historical types that remain load-compatible.

- [ ] **Step 3: Append a new decision record**

At the latest section of `docs/project-decisions.zh-CN.md`, append a dated decision containing:

```markdown
## 2026-08-08 - Stagehand tool_choice 异常必须继续动作后观察

更改：
- 仅对 `Thinking mode does not support this tool_choice` 启用继续观察。
- 有明确变化时记录成功转换；无变化时记录 `no_observed_change` 自环。
- 保留原始 error 和 `backend_reported_success=false`。

原因：
- Stagehand 可能先完成输入、点击或按键，再在工具协议收尾阶段返回该错误。
- 执行器错误不能替代 Web-KOBE 的动作后页面观察。

边界：
- 未知错误仍是失败自环且不调用 Visual Delta。
- 视觉变化事实不进入 PlanningState 或 Phase A PDDL。
```

Also append the experiment convention and target-source protection as current consequences, without rewriting earlier historical decisions.

- [ ] **Step 4: Review documentation consistency**

Run:

```powershell
rg -n "generated facts|meaningful_change|business_relevance|BusinessTransition|PlanningState|tool_choice|target matching|Phase A|latest" `
  docs/current-project-overview.zh-CN.md `
  docs/project-structure.zh-CN.md `
  docs/project-decisions.zh-CN.md
```

Inspect every current-tense match. Historical decision entries may retain old behavior, but the overview and structure documents must not claim that Visual Delta facts enter PlanningState/PDDL or that new exploration uses VLM `BusinessTransition` judgments.

- [ ] **Step 5: Commit the documentation alignment**

```powershell
git add docs/current-project-overview.zh-CN.md docs/project-structure.zh-CN.md docs/project-decisions.zh-CN.md
git commit -m "Align Chinese project docs with Phase A mainline"
```

---

### Task 3: Final Verification

**Files:**
- Verify only; no expected file changes.

**Interfaces:**
- Consumes: Task 1 behavior and Task 2 documentation.
- Produces: a clean, tested implementation branch ready for review.

- [ ] **Step 1: Run focused cross-layer tests**

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests/safesym_bridge/test_web_kobe_explorer.py `
  tests/safesym_bridge/test_visual_delta_summarizer.py `
  tests/safesym_bridge/test_behavior_state_graph.py `
  tests/safesym_bridge/test_web_kobe_pddl_projector.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run the full suite**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass; existing intentional skips remain skipped.

- [ ] **Step 3: Check scope and persisted schemas**

```powershell
git diff main...HEAD --stat
git diff main...HEAD -- src/ai_web_explorer/grounded_web/graph.py src/ai_web_explorer/grounded_web/capability_graph.py
git status --short
```

Expected: no persisted graph schema changes and a clean worktree. Report both commit hashes, test results, and any remaining limitations.

