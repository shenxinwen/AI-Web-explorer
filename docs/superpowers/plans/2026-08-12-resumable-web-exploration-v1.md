# Resumable Web Exploration V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resume a saved Web-KOBE exploration graph in a fresh browser, replay to a stable reachable checkpoint, safely continue untried work, and optionally retry one explicitly authorized failed or outcome-unknown action.

**Architecture:** Add a graph-hydration path that does not replay history through mutating manager APIs. Add a write-ahead `inflight_action` marker around every Stagehand business attempt. Centralize resume eligibility and target selection in a small domain-neutral module, then wire it through the existing explorer, frontier replay, controller, browser runner, and CLI without changing PDDL semantics.

**Tech Stack:** Python 3.11, dataclasses, pytest/AnyIO, Playwright, Stagehand, existing WebKobeGraph JSON and atomic checkpoint writers.

## Global Constraints

- Preserve ordinary non-resume exploration behavior and CLI defaults.
- Do not inject goals, plans, PDDL state, or SafeSym feedback into exploration.
- Do not add website-specific action names or selectors to production code.
- Do not restore browser processes, cookies, localStorage, DOM objects, or Stagehand sessions.
- Never replay a path through an edge whose `replay_validation_status` is `unstable`.
- A replay provider/action failure blocks the target only for the current run; only a successful replay followed by target mismatch may persist `unstable`.
- Historical failed or inflight actions are not retryable by default. Retry requires an exact CLI authorization resolved to the most recent matching `(source_node_id, action_id)` attempt.
- `--steps` counts only new business attempts, not historical steps, baseline copies, or replay actions.
- Use TDD for every production behavior change and keep commits task-scoped.
- Do not run the real website/API experiment in the implementation worktree. The reviewing session will perform real-model acceptance after merging.

---

## File Structure

- Create `src/ai_web_explorer/grounded_web/resume.py`: pure resume cursor, retry authorization, attempt counting, eligibility, and resume-target selection.
- Modify `src/ai_web_explorer/grounded_web/graph_manager.py`: lossless `from_graph` hydration only.
- Modify `src/ai_web_explorer/grounded_web/explorer.py`: restore graph, shared eligibility, runtime preference, and write-ahead inflight lifecycle.
- Modify `src/ai_web_explorer/grounded_web/frontier_replay.py`: injectable eligibility and non-poisoning replay action failure.
- Modify `src/ai_web_explorer/grounded_web/controller.py`: cumulative replay metric baseline and resumed-run summary compatibility.
- Modify `src/ai_web_explorer/safesym_bridge/browser_runner.py`: baseline load/copy, resume bootstrap, shared checkpoint callback, event-based traces.
- Modify `src/ai_web_explorer/safesym_bridge/cli.py`: resume flags, validation, and clean conflict.
- Add focused tests beside each existing component; update project documentation only after behavior passes.

---

### Task 1: Lossless Graph Hydration

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/graph_manager.py`
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Test: `tests/safesym_bridge/test_web_kobe_graph_manager.py`
- Test: `tests/safesym_bridge/test_web_kobe_explorer.py`

**Interfaces:**
- Produces: `WebKobeGraphManager.from_graph(graph: WebKobeGraph) -> WebKobeGraphManager`.
- Produces: `WebKobeExplorer.restore_graph(graph: WebKobeGraph) -> None`.
- Guarantees: hydration does not call `add_edge`, append events, increment visits, or share mutable list/dict objects with the source graph.

- [ ] **Step 1: Add failing manager roundtrip tests**

Add a test that builds a graph containing two nodes, a canonical edge, duplicate ordered `execution_events`, replay metadata, meta, and a nonzero total. Assert exact `to_dict()` equality after hydration and mutation isolation:

```python
def test_graph_manager_from_graph_is_lossless_and_does_not_reappend_events():
    graph = _graph_with_duplicate_execution_events()

    manager = WebKobeGraphManager.from_graph(graph)
    restored = manager.to_graph(start_node_id=graph.start_node_id)

    assert restored.to_dict() == graph.to_dict()
    assert len(restored.execution_events) == 2

    graph.meta["mutated_after_restore"] = True
    graph.nodes[0].business_affordances.append(BusinessAffordance("late_action"))
    isolated = manager.to_graph(start_node_id=graph.start_node_id)
    assert "mutated_after_restore" not in isolated.meta
    assert [item.action_name for item in isolated.nodes[0].business_affordances] != [
        "late_action"
    ]
```

- [ ] **Step 2: Run the manager test and verify RED**

Run:

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest tests/safesym_bridge/test_web_kobe_graph_manager.py::test_graph_manager_from_graph_is_lossless_and_does_not_reappend_events -q
```

Expected: FAIL because `from_graph` does not exist.

- [ ] **Step 3: Implement defensive hydration**

Implement a classmethod using `copy.deepcopy`; assign internal collections directly rather than calling mutating public APIs:

```python
@classmethod
def from_graph(cls, graph: WebKobeGraph) -> "WebKobeGraphManager":
    restored = copy.deepcopy(graph)
    manager = cls(app=restored.app)
    manager._nodes = OrderedDict((node.node_id, node) for node in restored.nodes)
    manager._edges = OrderedDict((edge.edge_id, edge) for edge in restored.edges)
    manager._execution_events = list(restored.execution_events)
    manager.total_steps_completed = restored.total_steps_completed
    manager.meta = dict(restored.meta)
    return manager
```

Reject duplicate node IDs or duplicate canonical edge IDs with clear `ValueError`s instead of silently overwriting.

- [ ] **Step 4: Add and implement explorer restore behavior**

Test that restoring sets the manager/start ID, clears the runtime current pointer/visit stack, and marks every node already containing affordances as observed so VLM candidates are not regenerated:

```python
def test_explorer_restore_graph_preserves_candidates_without_current_browser_pointer():
    explorer = _business_explorer(FakeAdapter())
    graph = _resume_graph()

    explorer.restore_graph(graph)

    assert explorer.start_node_id == graph.start_node_id
    assert explorer._current_node_id is None
    assert explorer.manager.to_graph(graph.start_node_id).to_dict() == graph.to_dict()
    assert explorer._visual_affordance_observed_node_ids == {
        node.node_id for node in graph.nodes if node.business_affordances
    }
```

Minimal implementation:

```python
def restore_graph(self, graph: WebKobeGraph) -> None:
    if graph.app != self.adapter.app_name:
        raise ValueError("resume_app_mismatch")
    self.manager = WebKobeGraphManager.from_graph(graph)
    self._start_node_id = graph.start_node_id
    self._current_node_id = None
    self._visit_stack = []
    self._visual_affordance_observed_node_ids = {
        node.node_id for node in graph.nodes if node.business_affordances
    }
```

- [ ] **Step 5: Run focused tests and commit**

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest tests/safesym_bridge/test_web_kobe_graph_manager.py tests/safesym_bridge/test_web_kobe_explorer.py -q
git add -- src/ai_web_explorer/grounded_web/graph_manager.py src/ai_web_explorer/grounded_web/explorer.py tests/safesym_bridge/test_web_kobe_graph_manager.py tests/safesym_bridge/test_web_kobe_explorer.py
git commit -m "feat: restore saved exploration graphs"
```

Expected: focused tests pass and worktree is clean after commit.

---

### Task 2: Write-Ahead Inflight Action Checkpoint

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Test: `tests/safesym_bridge/test_web_kobe_explorer.py`
- Test: `tests/safesym_bridge/test_browser_runner.py`

**Interfaces:**
- Produces constructor parameter `attempt_checkpoint: Callable[[WebKobeGraph], None] | None = None`.
- Persists `graph.meta["inflight_action"]` with `attempt_id`, `source_node_id`, and `action_id` before adapter execution.
- Adds the same `attempt_id` to completed edge `execution_trace.metadata`, clears inflight before returning the completed graph, and relies on the controller's existing completed-step checkpoint for commit.

- [ ] **Step 1: Add a failing pre-action checkpoint test**

Use an adapter whose `execute` asserts the checkpoint was already captured:

```python
@pytest.mark.anyio
async def test_explorer_checkpoints_inflight_before_adapter_execution():
    snapshots = []
    adapter = AssertingExecuteAdapter(
        before_execute=lambda: snapshots.append("adapter_execute")
    )
    explorer = _business_explorer(
        adapter,
        attempt_checkpoint=lambda graph: snapshots.append(graph.to_dict()),
    )

    graph = await explorer.explore_one_step()

    inflight = snapshots[0]["meta"]["inflight_action"]
    assert inflight["source_node_id"] == graph.edges[0].source_node_id
    assert inflight["action_id"] == graph.edges[0].action.semantic_id
    assert inflight["attempt_id"]
    assert snapshots[1] == "adapter_execute"
    assert "inflight_action" not in graph.meta
    assert graph.execution_events[-1].execution_trace.metadata["attempt_id"] == (
        inflight["attempt_id"]
    )
```

- [ ] **Step 2: Verify RED**

Run the single test. Expected: constructor rejects `attempt_checkpoint` or no inflight snapshot exists.

- [ ] **Step 3: Implement begin/complete attempt lifecycle**

Add focused helpers:

```python
def _begin_action_attempt(self, *, source_id: str, action: BrowserAction) -> str:
    attempt_id = uuid.uuid4().hex
    self.manager.meta["inflight_action"] = {
        "attempt_id": attempt_id,
        "source_node_id": source_id,
        "action_id": action.canonical_action_name or action.semantic_id,
    }
    if self.attempt_checkpoint is not None:
        self.attempt_checkpoint(self.manager.to_graph(self._start_node_id))
    return attempt_id
```

Call it immediately before `adapter.execute(selected)`. Put `attempt_id` into `execution_metadata`. Clear `inflight_action` only after the edge/execution event has been added successfully. If adapter execution raises out of `explore_one_step`, leave inflight in manager memory and let the pre-action checkpoint remain the durable state.

- [ ] **Step 4: Add crash-boundary tests**

Cover:

```python
@pytest.mark.anyio
async def test_execute_exception_leaves_durable_inflight_without_event(): ...

@pytest.mark.anyio
async def test_reported_failure_completes_event_and_clears_inflight(): ...
```

The exception case must have one pre-action checkpoint, zero new execution events, and the inflight marker. The reported-false case must create one `failed_execution` event with matching attempt ID and no final inflight marker.

- [ ] **Step 5: Wire the Stagehand runner to the same atomic checkpoint writer**

Construct one closure and pass it both to `WebKobeExplorer(attempt_checkpoint=checkpoint)` and `WebKobeExplorationController(step_checkpoint=checkpoint)`. The closure may capture `explorer` by late binding so it can write current embedding records.

Add a browser-runner test asserting checkpoint call order for one attempt:

```python
assert written_graphs[0]["meta"]["inflight_action"]["action_id"] == "open_item"
assert "inflight_action" not in written_graphs[1]["meta"]
assert written_graphs[1]["total_steps_completed"] == 1
```

- [ ] **Step 6: Run tests and commit**

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_browser_runner.py -q
git add -- src/ai_web_explorer/grounded_web/explorer.py src/ai_web_explorer/safesym_bridge/browser_runner.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_browser_runner.py
git commit -m "feat: journal inflight exploration actions"
```

---

### Task 3: Shared Resume Eligibility and Retry Authorization

**Files:**
- Create: `src/ai_web_explorer/grounded_web/resume.py`
- Create: `tests/safesym_bridge/test_resume.py`
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Modify: `src/ai_web_explorer/grounded_web/frontier_replay.py`
- Test: `tests/safesym_bridge/test_web_kobe_explorer.py`
- Test: `tests/safesym_bridge/test_frontier_replay.py`

**Interfaces:**
- Produces immutable `ActionAttemptKey(source_node_id: str, action_id: str)`.
- Produces `ResumePolicy(retry_keys: frozenset[ActionAttemptKey], max_attempts: int = 2)`.
- Produces `resolve_retry_keys(graph, requested_action_ids) -> frozenset[ActionAttemptKey]` resolving each action ID to its most recent failed/inflight occurrence.
- Produces `is_action_eligible(graph, *, source_node_id, action_id, policy) -> bool`.
- Extends `select_frontier(..., action_eligible: Callable[[str, str], bool] | None = None)` while preserving default behavior.

- [ ] **Step 1: Add table-driven failing eligibility tests**

```python
@pytest.mark.parametrize(
    ("events", "inflight", "authorized", "expected"),
    [
        ([], None, False, True),
        (["failed_execution"], None, False, False),
        (["failed_execution"], None, True, True),
        (["failed_execution", "failed_execution"], None, True, False),
        (["succeeded_with_observed_change"], None, True, False),
        (["no_observed_change"], None, True, False),
        ([], "matching", False, False),
        ([], "matching", True, True),
    ],
)
def test_resume_action_eligibility(events, inflight, authorized, expected): ...
```

Count a matching inflight marker as one outcome-unknown attempt. An authorized inflight with default max 2 is eligible once; two completed failures are exhausted.

- [ ] **Step 2: Verify RED, then implement pure policy functions**

Keep `resume.py` independent of browser/Stagehand. Use `graph.execution_events or graph.edges` for old-graph fallback. A successful or no-op event always closes eligibility even if an older failure exists.

`resolve_retry_keys` must scan newest-to-oldest, resolve one exact source/action key per requested ID, prefer matching inflight as newest, and raise `ValueError("unknown_resume_retry_action: ...")` when no failed/inflight occurrence exists.

- [ ] **Step 3: Prove both selectors use the same policy**

Add one graph fixture where a node has `retry_me` with one failed event and `new_action` with no event. Assert:

```python
eligible = lambda node_id, action_id: is_action_eligible(
    graph,
    source_node_id=node_id,
    action_id=action_id,
    policy=policy,
)
frontier = select_frontier(graph, include_start=True, action_eligible=eligible)
assert frontier.untried_action_ids == ("retry_me", "new_action")
```

Restore the graph into an explorer with the same `ResumePolicy`; set a one-shot preferred key for `retry_me`; assert explorer selects `retry_me` once, clears preference after the attempt, and then follows ordinary relevance/tried suppression.

Do not remove failed edges or mutate historical candidates to implement retry.

- [ ] **Step 4: Run focused tests and commit**

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest tests/safesym_bridge/test_resume.py tests/safesym_bridge/test_frontier_replay.py tests/safesym_bridge/test_web_kobe_explorer.py -q
git add -- src/ai_web_explorer/grounded_web/resume.py src/ai_web_explorer/grounded_web/explorer.py src/ai_web_explorer/grounded_web/frontier_replay.py tests/safesym_bridge/test_resume.py tests/safesym_bridge/test_frontier_replay.py tests/safesym_bridge/test_web_kobe_explorer.py
git commit -m "feat: share resume action eligibility"
```

---

### Task 4: Resume Target Selection and Non-Poisoning Replay Failures

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/resume.py`
- Modify: `src/ai_web_explorer/grounded_web/frontier_replay.py`
- Test: `tests/safesym_bridge/test_resume.py`
- Test: `tests/safesym_bridge/test_frontier_replay.py`

**Interfaces:**
- Produces `derive_resume_cursor(graph) -> str`.
- Produces `select_resume_frontier(graph, *, policy, blocked_node_ids=()) -> FrontierTarget | None`.
- Changes `FrontierReplayRunner.replay`: action execution failure does not persist unstable; successful action plus target mismatch does.

- [ ] **Step 1: Add failing cursor and priority tests**

Cover cursor meta, successful last event target, failed/no-op last event source, inflight source, and empty graph start. Add a graph where cursor is reachable and eligible, a nearer sibling frontier also exists, and assert cursor wins. Add a cursor behind an unstable edge and assert fallback chooses the stable frontier.

Use the existing BFS parent/path construction semantics; do not duplicate a second incompatible replayability definition.

- [ ] **Step 2: Implement resume target selection**

Factor a reusable path lookup from `frontier_replay.py`, for example:

```python
def reachable_frontier_for_node(
    graph: WebKobeGraph,
    node_id: str,
    *,
    action_eligible: Callable[[str, str], bool],
) -> FrontierTarget | None:
    ...
```

`select_resume_frontier` tries the derived cursor, then the most recent authorized retry key source, then normal non-entry frontier, then entry fallback. It returns `None` when all are unavailable.

- [ ] **Step 3: Add RED tests for replay failure persistence**

```python
@pytest.mark.anyio
async def test_replay_action_failure_blocks_run_without_marking_edge_unstable(): ...

@pytest.mark.anyio
async def test_replay_target_mismatch_marks_edge_unstable(): ...
```

For action failure, expect `reason == "replay_action_failed"` and no `replay_validation_status="unstable"`. For target mismatch after successful execution, expect `reason == "target_state_mismatch"` and persistent unstable.

- [ ] **Step 4: Implement minimal replay change and run tests**

Remove `_mark_edge(..., "unstable")` only from the execute-false branch. Keep target mismatch fail-closed. Run all frontier/controller tests to catch semantic regressions.

- [ ] **Step 5: Commit**

```powershell
git add -- src/ai_web_explorer/grounded_web/resume.py src/ai_web_explorer/grounded_web/frontier_replay.py tests/safesym_bridge/test_resume.py tests/safesym_bridge/test_frontier_replay.py
git commit -m "feat: select stable resume frontiers"
```

---

### Task 5: Resume Bootstrap, Metrics, and Checkpoint Trace History

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/controller.py`
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Test: `tests/safesym_bridge/test_web_kobe_controller.py`
- Test: `tests/safesym_bridge/test_browser_runner.py`

**Interfaces:**
- Extends controller with optional `replay_metric_baseline: Mapping[str, int] | None = None` without changing defaults.
- Extends `run_stagehand_exploration` with `resume_graph: WebKobeGraph | None = None`, `resume_policy: ResumePolicy | None = None`.
- Resume bootstrap occurs before the first new `explore_one_step` and consumes no `--steps` budget.

- [ ] **Step 1: Add controller metric baseline tests**

Start with historical replay counts, perform one new replay success/failure, and assert cumulative counts. Also assert historical `blocked_replay_node_ids` and consecutive-unproductive state are not inherited into the new run.

The final `exploration_summary` for a resume run must contain:

```python
{
    "requested_steps": 3,
    "steps_completed": 1,
    "historical_steps": 7,
    "total_steps_completed": 8,
    "stop_reason": "...",
}
```

- [ ] **Step 2: Implement cumulative baselines without changing ordinary runs**

Initialize numeric replay totals from the provided baseline; initialize blocked/current-run counters empty. Preserve existing keys for backward compatibility and add summary fields only when `historical_steps > 0`.

- [ ] **Step 3: Add browser-runner resume bootstrap tests**

Mock browser/provider and assert the order:

```text
load/restore graph
write baseline when output differs
reset entry
replay target path
validate target
set one-shot retry preference when authorized
run controller for N new attempts
```

Test no eligible target returns a final graph with zero new steps and `stop_reason="resume_frontier_exhausted"`.

Test same input/output path is not truncated when reset/replay raises before a new action. Test different output gets a valid baseline copy before browser work.

- [ ] **Step 4: Use execution events for Stagehand trace checkpoints**

Change `_write_stagehand_checkpoint` to use:

```python
trace_edges = graph.execution_events or graph.edges
```

Filter Stagehand metadata as today. Add a test with failed then successful duplicate canonical edge and assert both trace entries remain ordered.

- [ ] **Step 5: Run tests and commit**

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest tests/safesym_bridge/test_web_kobe_controller.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_resume.py -q
git add -- src/ai_web_explorer/grounded_web/controller.py src/ai_web_explorer/safesym_bridge/browser_runner.py tests/safesym_bridge/test_web_kobe_controller.py tests/safesym_bridge/test_browser_runner.py
git commit -m "feat: bootstrap resumed exploration runs"
```

---

### Task 6: CLI Contract and Validation

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Test: `tests/safesym_bridge/test_cli.py`

**Interfaces:**
- Adds `--resume-graph PATH`.
- Adds repeatable `--resume-retry-action ACTION_ID` using `action="append"`, default empty.
- Adds `--resume-action-max-attempts POSITIVE_INT`, default `2`, validated as at least 2 when resume retry actions are present.
- Resume automatically activates frontier replay internally.

- [ ] **Step 1: Add failing CLI parser/wiring tests**

Test:

- ordinary command passes `resume_graph=None` and preserves frontier flag;
- resume loads the graph before invoking runner and passes a resolved `ResumePolicy`;
- retry action without `--resume-graph` is rejected;
- max attempts below 2 is rejected when retry action exists;
- `--clean-output-dir` with resume is rejected before deleting anything;
- app mismatch, missing start node, dangling edge, and unknown retry action fail before browser runner invocation;
- resume input/output may be the same path;
- resume implies frontier replay.

- [ ] **Step 2: Verify RED and implement minimal CLI changes**

Load via existing `load_web_kobe_graph_json`. Put structural validation in `resume.py` as `validate_resume_graph(graph, *, app_name) -> None`, leaving URL equality to runtime entry validation.

Do not delete or clean paths until all resume argument conflicts and graph validation pass.

- [ ] **Step 3: Run CLI and complete focused suite**

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest tests/safesym_bridge/test_cli.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_resume.py -q
```

- [ ] **Step 4: Commit**

```powershell
git add -- src/ai_web_explorer/safesym_bridge/cli.py src/ai_web_explorer/grounded_web/resume.py tests/safesym_bridge/test_cli.py tests/safesym_bridge/test_resume.py
git commit -m "feat: expose resumable exploration CLI"
```

---

### Task 7: Local End-to-End Fixture, Documentation, and Final Verification

**Files:**
- Modify: `tests/safesym_bridge/test_web_kobe_playwright_integration.py`
- Modify: `docs/current-project-overview.md`
- Modify: `docs/current-project-overview.zh-CN.md`
- Modify: `docs/project-structure.md`
- Modify: `docs/project-structure.zh-CN.md`
- Modify: `docs/project-decisions.zh-CN.md`

**Interfaces:**
- Produces a gated local-browser test proving first-run checkpoint -> fresh browser resume -> replay -> new completed edge.
- Documents truthful limitations: stable paths only, no browser/session restoration, explicit retry, inflight marker, and no claim of universal recovery.

- [ ] **Step 1: Add a gated local Playwright resume fixture**

Use the existing local fixture page and deterministic adapters/providers. First run must create a stable path and either a completed failure or injected inflight marker. Close that browser. Second run loads the saved graph into a fresh browser, resets to entry, replays to target, and records one new event.

Assertions:

```python
assert resumed.total_steps_completed == baseline.total_steps_completed + 1
assert resumed.execution_events[: len(baseline.execution_events)] == (
    baseline.execution_events
)
assert resumed.meta["replay_success_count"] >= 1
assert "inflight_action" not in resumed.meta
```

Add a negative fixture where the only path contains an unstable edge and assert no forced resume.

- [ ] **Step 2: Run the gated fixture if the environment permits**

Run the exact environment switch used by existing Playwright integration tests. If Chromium fails with `spawn EPERM`, report the environment failure and keep the test gated; do not weaken assertions or replace it with a fake passing test.

- [ ] **Step 3: Update documentation**

Replace statements saying checkpoints never support resume. Document CLI examples, inflight semantics, stable-path requirement, explicit retry authorization, current-run step budget, and event-based Stagehand traces. Do not claim that the current unstable shopping graph can reach its add-to-cart breakpoint.

- [ ] **Step 4: Run complete verification**

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest tests/safesym_bridge/test_resume.py tests/safesym_bridge/test_frontier_replay.py tests/safesym_bridge/test_web_kobe_controller.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_cli.py -q
& '.venv/Scripts/python.exe' -m pytest -q
git diff --check
git status --short
```

Record exact pass/fail/skip counts. The known local Chromium environment failure may be reported separately, but no non-browser regression is acceptable.

- [ ] **Step 5: Static scope audit**

```powershell
rg -n "practiceautomatedtesting|shopping|add_to_cart|checkout|product" src/ai_web_explorer/grounded_web/resume.py src/ai_web_explorer/grounded_web/graph_manager.py
```

Expected: no site/domain hardcoding in the new generic resume code. CLI help examples do not belong in production source.

- [ ] **Step 6: Commit documentation and integration test**

```powershell
git add -- tests/safesym_bridge/test_web_kobe_playwright_integration.py docs/current-project-overview.md docs/current-project-overview.zh-CN.md docs/project-structure.md docs/project-structure.zh-CN.md docs/project-decisions.zh-CN.md
git commit -m "docs: document resumable exploration checkpoints"
```

Final handoff must include all commit SHAs, RED evidence per task, focused/full test counts, gated Playwright result, `git diff --check`, clean detached worktree status, and an explicit statement that no real website/model API was invoked.
