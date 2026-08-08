# Forward-Only Exploration Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace browser-history backtracking with a small forward-only exploration loop that avoids repeated semantic actions, stops after repeated lack of new graph information, and preserves every successful observed transition for Phase A PDDL.

**Architecture:** VLM affordances remain frozen on first observation of a node. The local selector consumes only untried semantic action families for the current or matched historical node; Stagehand executes one selected action. A step is productive only when it adds a node or a unique `(source, canonical action, target)` edge. Exhausting the current node ends the run without browser backtracking, and Phase A accepts partial frontiers while projecting only observed successful edges.

**Tech Stack:** Python 3.11, dataclasses, existing `WebKobeGraph`/embedding provider interfaces, pytest.

## Global Constraints

- Keep VLM limited to proposing visible business actions; it must not decide graph memory or completion.
- Keep Stagehand limited to executing the selected business action.
- Keep each node's first non-empty `business_affordances` list frozen on revisit.
- Do not add replay, browser-history recovery, low-level selector fallback, or a new persistent memory table.
- Do not use `supporting_facts` as Phase A PDDL preconditions.
- Record and project only transitions that actually executed and were observed.
- A historical-node hit is a normal forward transition: move the current pointer to that node and consume its remaining fixed candidates.
- Use the existing configured embedding provider for runtime action similarity; with no provider, retain exact-name matching.
- Preserve the earliest action name as the canonical name in Phase A consolidation.
- Use the project interpreter for tests: `$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'; & '.\.venv\Scripts\python.exe' -m pytest ...`.

---

### Task 1: End a run when the current node is exhausted

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/explorer.py:296-304,630-646`
- Modify: `src/ai_web_explorer/grounded_web/controller.py:73-159`
- Test: `tests/safesym_bridge/test_web_kobe_explorer.py`
- Test: `tests/safesym_bridge/test_web_kobe_controller.py`

**Interfaces:**
- Consumes: `WebKobeExplorer._select_action(...) -> BrowserAction | None`.
- Produces: `graph.meta["last_step_kind"] == "current_state_exhausted"` and controller `stop_reason == "current_state_exhausted"`.

- [ ] **Step 1: Replace the explorer backtrack expectation with a failing forward-stop test**

Update the existing exhausted-node test so the adapter exposes `go_back()` but the explorer must not call it:

```python
@pytest.mark.anyio
async def test_explore_one_step_stops_forward_when_current_node_is_exhausted():
    adapter = ExhaustedNodeBackAdapter()
    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    graph = await explorer.explore_one_step()

    assert adapter.back_calls == 0
    assert adapter.executed == []
    assert graph.total_steps_completed == 0
    assert graph.meta["last_step_kind"] == "current_state_exhausted"
    assert graph.meta["last_step_status"] == "unproductive"
```

- [ ] **Step 2: Add a failing controller test for the new stop reason**

```python
@pytest.mark.anyio
async def test_controller_reports_current_state_exhausted():
    explorer = FakeExplorer([
        _graph(
            completed=0,
            meta={
                "last_step_kind": "current_state_exhausted",
                "last_step_status": "unproductive",
            },
        )
    ])
    result = await WebKobeExplorationController(explorer).run(max_steps=3)
    assert explorer.calls == 1
    assert result.summary.stop_reason == "current_state_exhausted"
```

- [ ] **Step 3: Run the two focused tests and verify they fail**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
& '.\.venv\Scripts\python.exe' -m pytest -q `
  tests/safesym_bridge/test_web_kobe_explorer.py -k "stops_forward_when_current_node_is_exhausted" `
  tests/safesym_bridge/test_web_kobe_controller.py -k "reports_current_state_exhausted"
```

Expected: explorer still calls `go_back()` and controller returns `no_available_action`.

- [ ] **Step 4: Implement the minimal forward-only stop**

In `explore_one_step`, replace the `_try_backtrack()` branch with:

```python
if selected is None:
    self.manager.meta["last_step_kind"] = "current_state_exhausted"
    self.manager.meta["last_step_status"] = "unproductive"
    self.manager.meta["last_step_graph_changed"] = False
    return self.manager.to_graph(start_node_id=self._start_node_id)
```

Delete `_try_backtrack` and its direct unit test. Keep `_visit_stack` because conservative target matching still uses it as evidence that an old node was genuinely visited; do not call browser history from exploration.

In the controller, when `total_steps_completed` does not increase, use `last_step_kind` as the stop reason when it is `current_state_exhausted`; otherwise retain `no_available_action` as a defensive fallback. Remove the productive `control_backtrack` special case and its test because exploration no longer emits that control action.

- [ ] **Step 5: Run focused explorer/controller tests**

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
& '.\.venv\Scripts\python.exe' -m pytest -q `
  tests/safesym_bridge/test_web_kobe_explorer.py `
  tests/safesym_bridge/test_web_kobe_controller.py
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```powershell
git add src/ai_web_explorer/grounded_web/explorer.py src/ai_web_explorer/grounded_web/controller.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_web_kobe_controller.py
git commit -m "Simplify exploration to forward-only stopping"
```

---

### Task 2: Count only new graph information as productive

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/explorer.py:448-530`
- Modify: `src/ai_web_explorer/grounded_web/controller.py:81-159`
- Test: `tests/safesym_bridge/test_web_kobe_explorer.py`
- Test: `tests/safesym_bridge/test_web_kobe_controller.py`

**Interfaces:**
- Produces: `graph.meta["last_step_graph_changed"]: bool` for every business edge.
- Consumes: stable edge identity already defined by `WebKobeEdge.edge_id`, which contains source, semantic action, and target identity.

- [ ] **Step 1: Add failing tests for novel and repeated transitions**

Add a small fake explorer sequence showing that a successful edge status does not by itself mean progress:

```python
@pytest.mark.anyio
async def test_controller_stops_after_repeated_steps_without_new_graph_information():
    explorer = FakeExplorer([
        _graph(completed=1, meta={"last_step_graph_changed": True}),
        _graph(completed=2, meta={"last_step_graph_changed": False}),
        _graph(completed=3, meta={"last_step_graph_changed": False}),
        _graph(completed=4, meta={"last_step_graph_changed": False}),
    ])
    controller = WebKobeExplorationController(
        explorer,
        max_consecutive_unproductive_steps=3,
    )
    result = await controller.run(max_steps=10)
    assert explorer.calls == 4
    assert result.summary.stop_reason == "consecutive_unproductive_steps"
    assert result.summary.consecutive_unproductive_steps == 3
```

Add explorer coverage for a repeated identical edge and assert the second occurrence sets `last_step_graph_changed` to `False`, while the first unique edge sets it to `True`.

- [ ] **Step 2: Run the focused tests and verify failure**

Expected: successful repeated edges currently reset the unproductive counter because `_last_step_is_productive` reads only edge status.

- [ ] **Step 3: Set graph novelty in the explorer**

Immediately before target insertion, capture known node IDs; immediately before edge insertion, capture known edge IDs. After insertion, set:

```python
node_was_new = target_id not in known_node_ids
edge_was_new = edge.edge_id not in known_edge_ids
graph_changed = node_was_new or edge_was_new
self.manager.meta["last_step_graph_changed"] = graph_changed
self.manager.meta["last_step_status"] = (
    "productive" if graph_changed else "unproductive"
)
```

Do not use edge execution success as the productivity signal. Failed and no-op edges may remain diagnostic raw edges, but a duplicate diagnostic edge is still not new graph information.

- [ ] **Step 4: Make the controller consume the novelty flag**

Replace `_last_step_is_productive` with a check of `graph.meta.get("last_step_graph_changed") is True`. Continue incrementing `total_steps_completed` for attempted business actions; this counter is the action budget, while graph novelty controls early stopping.

- [ ] **Step 5: Run explorer/controller tests**

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
& '.\.venv\Scripts\python.exe' -m pytest -q `
  tests/safesym_bridge/test_web_kobe_explorer.py `
  tests/safesym_bridge/test_web_kobe_controller.py
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```powershell
git add src/ai_web_explorer/grounded_web/explorer.py src/ai_web_explorer/grounded_web/controller.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_web_kobe_controller.py
git commit -m "Stop exploration after repeated known transitions"
```

---

### Task 3: Avoid repeated semantic actions in the current or matched state

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/exploration_index.py`
- Modify: `src/ai_web_explorer/grounded_web/explorer.py:916-938`
- Test: `tests/safesym_bridge/test_exploration_index.py`
- Test: `tests/safesym_bridge/test_web_kobe_explorer.py`

**Interfaces:**
- Add: `semantically_matches_action(candidate: str, existing: tuple[str, ...], *, embedding_provider: EmbeddingProvider | None, same_threshold: float = 0.90) -> bool`.
- Consume: `self.state_embedding_provider`, already configured locally and never exposed to VLM.

- [ ] **Step 1: Add failing helper tests**

Use a deterministic fake embedding provider so the test does not call an external model:

```python
def test_semantic_action_match_detects_paraphrase_with_embedding():
    vectors = {
        "sort_by_name": [1.0, 0.0],
        "order_items_alphabetically": [0.99, 0.01],
        "filter_by_price": [0.0, 1.0],
    }
    assert semantically_matches_action(
        "order_items_alphabetically",
        ("sort_by_name",),
        embedding_provider=lambda text: vectors[text],
    )
    assert not semantically_matches_action(
        "filter_by_price",
        ("sort_by_name",),
        embedding_provider=lambda text: vectors[text],
    )
```

Also test exact matching with `embedding_provider=None`.

- [ ] **Step 2: Add a failing selector test**

Create a node whose highest-ranked candidate is `order_items_alphabetically`, while the current `ExplorationContext.tried_action_ids` contains `sort_by_name`. Configure the fake embedding provider above and assert the selector chooses the next genuinely new candidate, such as `filter_by_price`.

- [ ] **Step 3: Run focused tests and verify failure**

Expected: the selector currently compares raw strings and selects the paraphrase.

- [ ] **Step 4: Implement conservative state-local semantic matching**

Normalize exact strings first. Only when exact matching fails and a provider exists, embed the candidate and the tried actions and compare with existing `cosine_similarity`. Treat similarity `>= 0.90` as the same action. If embedding raises an exception or vectors are incompatible, fall back to exact matching instead of stopping exploration.

In `_select_business_affordance_action`, check semantic equivalence against `avoid_action_ids` and `tried_action_ids`. Do not inspect actions from unrelated nodes; `build_exploration_context` already scopes memory to the current node or the accepted matched reference node.

- [ ] **Step 5: Run action-memory tests**

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
& '.\.venv\Scripts\python.exe' -m pytest -q `
  tests/safesym_bridge/test_exploration_index.py `
  tests/safesym_bridge/test_web_kobe_explorer.py
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```powershell
git add src/ai_web_explorer/grounded_web/exploration_index.py src/ai_web_explorer/grounded_web/explorer.py tests/safesym_bridge/test_exploration_index.py tests/safesym_bridge/test_web_kobe_explorer.py
git commit -m "Avoid repeated semantic actions in local exploration memory"
```

---

### Task 4: Preserve observed edges from partial frontiers in Phase A

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/behavior_state_graph.py:180-208,314-428`
- Test: `tests/safesym_bridge/test_behavior_state_graph.py`
- Test: `tests/safesym_bridge/test_behavior_state_graph_cli.py`

**Interfaces:**
- Preserve: `ConsolidationReport.rejected_nodes` for fatal problems only (`missing_target_node`, `failed_execution`, `action_target_conflict`).
- Produce: canonical edges for every successfully observed transition even when the source has unexecuted affordances.

- [ ] **Step 1: Replace the incomplete-frontier rejection test**

```python
def test_consolidation_keeps_observed_edge_from_partial_frontier():
    graph = _graph(
        [
            _node(
                "source",
                [BusinessAffordance("open_results"), BusinessAffordance("sort_results")],
            ),
            _node("target"),
        ],
        [_edge("source", "target", "open_results")],
    )

    artifacts = consolidate_behavior_state_graph(graph)

    assert "source" not in artifacts.report.rejected_nodes
    assert [(edge.source_node_id, edge.target_node_id) for edge in artifacts.canonical_graph.edges] == [
        ("source", "target")
    ]
```

Keep separate tests proving failed executions and missing targets remain rejected.

- [ ] **Step 2: Update the CLI golden behavior test**

The Phase A CLI must write the successful partial-frontier action into `canonical_graph.json` and `domain.pddl`; it must not report `frontier_incomplete` as a rejected-node reason.

- [ ] **Step 3: Run focused tests and verify failure**

Expected: the source is currently ineligible and its successful edge is omitted.

- [ ] **Step 4: Make incomplete frontier diagnostic-only outside consolidation**

Remove `frontier_incomplete` from `_frontier_state` rejection reasons. Existing `graph.meta.frontier_metrics` remains the place to inspect untried candidates. Do not add a new report field. Keep fatal checks unchanged.

Do not project unexecuted affordances as PDDL actions: Phase A domain generation must continue consuming canonical edges only.

- [ ] **Step 5: Run Phase A tests**

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
& '.\.venv\Scripts\python.exe' -m pytest -q `
  tests/safesym_bridge/test_behavior_state_graph.py `
  tests/safesym_bridge/test_behavior_state_graph_cli.py `
  tests/safesym_bridge/test_web_kobe_pddl_projector.py
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

```powershell
git add src/ai_web_explorer/grounded_web/behavior_state_graph.py tests/safesym_bridge/test_behavior_state_graph.py tests/safesym_bridge/test_behavior_state_graph_cli.py
git commit -m "Keep observed transitions from partial frontiers"
```

---

### Task 5: Update project decisions and run final verification

**Files:**
- Modify: `docs/current-project-overview.zh-CN.md`
- Modify: `docs/project-decisions.zh-CN.md`
- Modify: `docs/project-structure.zh-CN.md` only if function responsibilities changed materially.

**Interfaces:**
- Documents the implemented behavior; does not introduce new behavior.

- [ ] **Step 1: Update the Chinese overview**

Replace DFS/browser-back wording with the implemented policy:

```text
单轮探索保持前向执行。命中历史节点时复用该节点首次生成的固定候选，并跳过当前或相似状态中已尝试的同义动作。当前节点候选耗尽时结束本轮，不使用浏览器历史回退。停止条件为最大步数、当前状态耗尽，或连续多步没有新增节点和新的语义转换。
```

- [ ] **Step 2: Add one decision record**

Record why the project chose forward-only bounded exploration instead of browser-history recovery: Phase A needs trustworthy observed transitions, not exhaustive single-run traversal; browser history cannot restore same-URL UI states; multiple experiments and local semantic memory provide incremental coverage.

- [ ] **Step 3: Run the focused regression suite**

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
& '.\.venv\Scripts\python.exe' -m pytest -q `
  tests/safesym_bridge/test_exploration_index.py `
  tests/safesym_bridge/test_web_kobe_explorer.py `
  tests/safesym_bridge/test_web_kobe_controller.py `
  tests/safesym_bridge/test_behavior_state_graph.py `
  tests/safesym_bridge/test_behavior_state_graph_cli.py `
  tests/safesym_bridge/test_web_kobe_pddl_projector.py
```

Expected: all selected tests pass.

- [ ] **Step 4: Run the complete test suite**

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
& '.\.venv\Scripts\python.exe' -m pytest -q
```

Expected: PASS with no new failures. Record the exact passed/skipped counts in the execution report.

- [ ] **Step 5: Review the final diff for scope**

```powershell
git status --short
git diff --check
git diff --stat HEAD~4..HEAD
```

Confirm there is no replay logic, browser-history exploration call, low-level selector fallback, new persistent memory table, or supporting-fact Phase A precondition.

- [ ] **Step 6: Commit documentation**

```powershell
git add docs/current-project-overview.zh-CN.md docs/project-decisions.zh-CN.md docs/project-structure.zh-CN.md
git commit -m "Document forward-only exploration policy"
```

## Execution Report Required From Worker

Return:

1. Commit hashes for each task.
2. Exact focused and full test outputs.
3. Files changed.
4. Any deviation from this plan and why.
5. Confirmation that the worker did not run a real website experiment and did not modify experiment artifacts.

