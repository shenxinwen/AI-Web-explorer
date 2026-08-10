# Step Checkpoint And Bounded Stop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the latest completed Stagehand exploration step and let the real runner continue until its configured maximum step count unless the current state has no candidate.

**Architecture:** The controller exposes a synchronous per-completed-step callback and makes the existing unproductive-step limit optionally disabled. The Stagehand runner supplies a callback that atomically refreshes embeddings and trace before committing the existing graph/evidence pair, then reuses the same writer after normal completion.

**Tech Stack:** Python 3.12, asyncio, dataclasses, pathlib, pytest/anyio, existing WebKobe graph serializers.

## Global Constraints

- Do not change state matching, node materialization, action selection, browser replay, or PDDL projection.
- Do not create per-step artifact history; overwrite the existing latest paths.
- The graph/evidence pair is the checkpoint commit marker and must be written last.
- A step that raises before returning must not create a partial graph transition.
- A checkpoint write error must propagate instead of being silently ignored.
- Current-state exhaustion remains a valid early stop for forward-only exploration.
- Do not add a resume mechanism in this change.

## File map

- Modify `src/ai_web_explorer/grounded_web/controller.py`: callback timing and optional unproductive-step termination.
- Modify `src/ai_web_explorer/grounded_web/state_embedding.py`: atomic replacement for embedding JSON.
- Modify `src/ai_web_explorer/safesym_bridge/browser_runner.py`: one checkpoint serializer used during and after exploration.
- Modify `tests/safesym_bridge/test_web_kobe_controller.py`: controller callback and disabled-limit behavior.
- Modify `tests/safesym_bridge/test_state_embedding.py`: embedding atomic-write protection.
- Modify `tests/safesym_bridge/test_browser_runner.py`: runner wiring, artifact order, and interrupted-run persistence.
- Modify `docs/current-project-overview.zh-CN.md`, `docs/project-structure.zh-CN.md`, and `docs/project-decisions.zh-CN.md`: describe the active stop and checkpoint behavior.

---

### Task 1: Controller checkpoint hook and optional unproductive limit

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/controller.py`
- Test: `tests/safesym_bridge/test_web_kobe_controller.py`

**Interfaces:**
- Produces: `StepCheckpoint = Callable[[WebKobeGraph], None]`.
- Produces: `WebKobeExplorationController(..., step_checkpoint: StepCheckpoint | None = None, max_consecutive_unproductive_steps: int | None = 3)`.
- Behavior: invoke `step_checkpoint(graph)` once after each call that increments `total_steps_completed`; do not invoke it for a no-candidate probe.

- [ ] **Step 1: Add failing callback tests**

Append tests equivalent to:

```python
@pytest.mark.anyio
async def test_controller_checkpoints_each_completed_step():
    explorer = FakeExplorer([_graph(completed=1), _graph(completed=2)])
    checkpoints = []
    controller = WebKobeExplorationController(
        explorer,
        step_checkpoint=lambda graph: checkpoints.append(graph.total_steps_completed),
    )

    await controller.run(max_steps=2)

    assert checkpoints == [1, 2]


@pytest.mark.anyio
async def test_controller_does_not_checkpoint_current_state_exhaustion_probe():
    explorer = FakeExplorer([
        _graph(completed=1),
        _graph(completed=1, meta={"last_step_kind": "current_state_exhausted"}),
    ])
    checkpoints = []
    result = await WebKobeExplorationController(
        explorer,
        step_checkpoint=lambda graph: checkpoints.append(graph.total_steps_completed),
    ).run(max_steps=3)

    assert checkpoints == [1]
    assert result.summary.stop_reason == "current_state_exhausted"
```

- [ ] **Step 2: Add the failing disabled-limit test**

```python
@pytest.mark.anyio
async def test_controller_can_disable_unproductive_step_stop():
    explorer = FakeExplorer([
        _graph(completed=index, meta={"last_step_graph_changed": False})
        for index in range(1, 5)
    ])
    controller = WebKobeExplorationController(
        explorer,
        max_consecutive_unproductive_steps=None,
    )

    result = await controller.run(max_steps=4)

    assert explorer.calls == 4
    assert result.summary.stop_reason == "max_steps"
    assert result.summary.consecutive_unproductive_steps == 4
    assert result.summary.max_consecutive_unproductive_steps is None
```

- [ ] **Step 3: Run the focused tests and confirm failure**

Run:

```powershell
./.venv/Scripts/python.exe -m pytest -q tests/safesym_bridge/test_web_kobe_controller.py -k "checkpoint or disable_unproductive"
```

Expected: FAIL because the constructor has no `step_checkpoint` argument and does not accept `None` for the limit.

- [ ] **Step 4: Implement the minimal controller API**

In `controller.py`:

```python
from typing import Callable, Protocol

StepCheckpoint = Callable[[WebKobeGraph], None]
```

Change the summary field and constructor:

```python
max_consecutive_unproductive_steps: int | None = 3

def __init__(
    self,
    explorer: StepExplorer,
    *,
    terminal_condition: Callable[[WebKobeGraph], bool] | None = None,
    max_consecutive_unproductive_steps: int | None = 3,
    step_checkpoint: StepCheckpoint | None = None,
):
    self.explorer = explorer
    self.terminal_condition = terminal_condition
    self.max_consecutive_unproductive_steps = (
        None
        if max_consecutive_unproductive_steps is None
        else max(max_consecutive_unproductive_steps, 1)
    )
    self.step_checkpoint = step_checkpoint
```

After confirming that `total_steps_completed` increased, update the consecutive counter as today. Guard only the stop comparison:

```python
if self.step_checkpoint is not None:
    self.step_checkpoint(graph)
if (
    self.max_consecutive_unproductive_steps is not None
    and consecutive_unproductive_steps >= self.max_consecutive_unproductive_steps
):
    stop_reason = "consecutive_unproductive_steps"
    break
```

Invoke the callback after graph metadata has been updated and before the unproductive or terminal-condition break. Keep no-action detection before the callback. Change `_summary` and the dataclass annotation to accept `int | None` without changing the default behavior for existing callers.

- [ ] **Step 5: Run the complete controller tests**

Run:

```powershell
./.venv/Scripts/python.exe -m pytest -q tests/safesym_bridge/test_web_kobe_controller.py
```

Expected: all tests PASS, including the existing explicit three-step limit tests.

- [ ] **Step 6: Commit Task 1**

```powershell
git add src/ai_web_explorer/grounded_web/controller.py tests/safesym_bridge/test_web_kobe_controller.py
git commit -m "Add per-step exploration checkpoint hook"
```

---

### Task 2: Atomic embedding and trace persistence

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/state_embedding.py`
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Test: `tests/safesym_bridge/test_state_embedding.py`
- Test: `tests/safesym_bridge/test_browser_runner.py`

**Interfaces:**
- Keeps: `write_state_embedding_records(path: Path, records: Iterable[StateEmbeddingRecord]) -> Path`.
- Produces: `_write_text_atomically(path: Path, text: str) -> Path` in `browser_runner.py` for trace output.
- Produces: `_write_stagehand_checkpoint(graph: WebKobeGraph, *, output_path: Path, embedding_path: Path | None, embedding_records: Iterable[StateEmbeddingRecord], stagehand_trace_path: Path | None) -> Path`.

- [ ] **Step 1: Add a failing embedding overwrite test**

In `test_state_embedding.py`, write an old valid payload, monkeypatch `Path.replace` to raise only for the target path, call `write_state_embedding_records`, and assert the old bytes remain:

```python
def test_failed_embedding_replace_preserves_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "state_embeddings.json"
    path.write_text('{"records":[{"node_id":"old"}]}', encoding="utf-8")
    old_bytes = path.read_bytes()
    original_replace = Path.replace

    def fail_target_replace(self, target):
        if Path(target) == path:
            raise OSError("replace failed")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_target_replace)
    with pytest.raises(OSError, match="replace failed"):
        write_state_embedding_records(path, [])

    assert path.read_bytes() == old_bytes
    assert list(tmp_path.glob("*.tmp")) == []
```

Add the required `Path` and `pytest` imports if absent.

- [ ] **Step 2: Add failing checkpoint helper tests**

In `test_browser_runner.py`, construct a graph containing one Stagehand edge and monkeypatch the three writers to append their names to a list. Assert `_write_stagehand_checkpoint` calls them in this order:

```python
assert calls == ["embedding", "trace", "graph"]
```

Also assert the trace JSON contains only edge metadata whose `action_source == "stagehand"`. Test `None` embedding and trace paths so the helper still writes the graph exactly once.

- [ ] **Step 3: Run the focused tests and confirm failure**

Run:

```powershell
./.venv/Scripts/python.exe -m pytest -q tests/safesym_bridge/test_state_embedding.py tests/safesym_bridge/test_browser_runner.py -k "embedding_replace or stagehand_checkpoint"
```

Expected: FAIL because embedding writes directly and `_write_stagehand_checkpoint` does not exist.

- [ ] **Step 4: Make embedding output atomic**

Update `write_state_embedding_records` to write a named temporary file beside the target, replace only after the JSON is complete, and always clean the temporary path:

```python
def write_state_embedding_records(
    path: Path,
    records: Iterable[StateEmbeddingRecord],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"records": [record.to_dict() for record in records]}
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(text)
        temp_path.replace(path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return path
```

Import `tempfile`. Do not change the JSON schema.

- [ ] **Step 5: Implement atomic trace and the shared checkpoint helper**

In `browser_runner.py`, implement `_write_text_atomically` using the existing `_write_json_temp`:

```python
def _write_text_atomically(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _write_json_temp(path, text)
    try:
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)
    return path
```

Then add:

```python
def _write_stagehand_checkpoint(
    graph: WebKobeGraph,
    *,
    output_path: Path,
    embedding_path: Path | None,
    embedding_records,
    stagehand_trace_path: Path | None,
) -> Path:
    if embedding_path is not None:
        write_state_embedding_records(embedding_path, embedding_records)
    if stagehand_trace_path is not None:
        traces = [
            edge.execution_trace.metadata
            for edge in graph.edges
            if edge.execution_trace.metadata.get("action_source") == "stagehand"
        ]
        _write_text_atomically(
            stagehand_trace_path,
            json.dumps(traces, indent=2, ensure_ascii=False),
        )
    return write_web_kobe_graph(graph, output_path)
```

Keep this helper private and near the existing serialization helpers. Graph is deliberately last.

- [ ] **Step 6: Run persistence tests**

Run:

```powershell
./.venv/Scripts/python.exe -m pytest -q tests/safesym_bridge/test_state_embedding.py tests/safesym_bridge/test_browser_runner.py -k "write_web_kobe_graph or embedding or checkpoint"
```

Expected: all selected tests PASS.

- [ ] **Step 7: Commit Task 2**

```powershell
git add src/ai_web_explorer/grounded_web/state_embedding.py src/ai_web_explorer/safesym_bridge/browser_runner.py tests/safesym_bridge/test_state_embedding.py tests/safesym_bridge/test_browser_runner.py
git commit -m "Make exploration checkpoint artifacts atomic"
```

---

### Task 3: Wire checkpoints into real Stagehand exploration

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Test: `tests/safesym_bridge/test_browser_runner.py`

**Interfaces:**
- Consumes: `WebKobeExplorationController(..., step_checkpoint=..., max_consecutive_unproductive_steps=None)` from Task 1.
- Consumes: `_write_stagehand_checkpoint(...)` from Task 2.
- Behavior: real generic Stagehand exploration saves every completed step and repeats the same save after normal completion.

- [ ] **Step 1: Replace the generic runner fake-controller test with callback-aware assertions**

Update `test_run_stagehand_exploration_wires_generic_stagehand_backend` so its fake controller captures constructor keyword arguments:

```python
class FakeController:
    def __init__(
        self,
        explorer,
        *,
        max_consecutive_unproductive_steps=3,
        step_checkpoint=None,
    ):
        captured["explorer"] = explorer
        captured["limit"] = max_consecutive_unproductive_steps
        captured["checkpoint"] = step_checkpoint

    async def run(self, *, max_steps):
        graph = WebKobeGraph(
            app="demo",
            start_node_id="start",
            total_steps_completed=1,
        )
        captured["checkpoint"](graph)
        return WebKobeExplorationResult(
            graph=graph,
            summary=WebKobeExplorationSummary(
                requested_steps=max_steps,
                steps_completed=1,
                stop_reason="max_steps",
                node_count=0,
                edge_count=0,
                failed_edge_count=0,
                max_consecutive_unproductive_steps=None,
            ),
        )
```

Assert `captured["limit"] is None` and that the output, evidence, embedding, and trace files exist after the callback.

- [ ] **Step 2: Add an interrupted-run persistence test**

Use the same fake Playwright/backend setup. Its fake controller must invoke the supplied checkpoint with a one-step graph and then raise:

```python
async def run(self, *, max_steps):
    self.step_checkpoint(
        WebKobeGraph(
            app="demo",
            start_node_id="start",
            total_steps_completed=1,
        )
    )
    raise RuntimeError("experiment interrupted")
```

Assert `run_stagehand_exploration` raises, the browser closes, and `graph.json`, `graph_evidence.json`, embedding JSON, and trace JSON still exist and parse successfully.

- [ ] **Step 3: Run the focused runner tests and confirm failure**

Run:

```powershell
./.venv/Scripts/python.exe -m pytest -q tests/safesym_bridge/test_browser_runner.py -k "run_stagehand_exploration"
```

Expected: FAIL because the runner neither supplies the callback nor disables the unproductive limit.

- [ ] **Step 4: Wire the generic real runner**

Replace the current controller construction and duplicate final writes in `run_stagehand_exploration` with:

```python
def checkpoint(graph: WebKobeGraph) -> None:
    _write_stagehand_checkpoint(
        graph,
        output_path=output_path,
        embedding_path=embedding_path,
        embedding_records=explorer.state_embedding_records,
        stagehand_trace_path=stagehand_trace_path,
    )

controller = WebKobeExplorationController(
    explorer,
    max_consecutive_unproductive_steps=None,
    step_checkpoint=checkpoint,
)
result = await controller.run(max_steps=max(steps, 1))
checkpoint(result.graph)
return output_path
```

Do not catch controller or checkpoint exceptions. The existing `finally` must continue closing the browser.

- [ ] **Step 5: Confirm whether legacy/e-commerce runners are in the active experiment path**

Use:

```powershell
rg -n "run_ecommerce_stagehand_step|run_stagehand_exploration" src tests docs
```

Only wire the generic `run_stagehand_exploration` used by the current `practice_automated_testing` command. Do not broaden this task to historical smoke runners unless the CLI active path proves they are also current production entry points.

- [ ] **Step 6: Run all runner and controller tests**

Run:

```powershell
./.venv/Scripts/python.exe -m pytest -q tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_web_kobe_controller.py tests/safesym_bridge/test_state_embedding.py
```

Expected: all tests PASS.

- [ ] **Step 7: Commit Task 3**

```powershell
git add src/ai_web_explorer/safesym_bridge/browser_runner.py tests/safesym_bridge/test_browser_runner.py
git commit -m "Checkpoint each completed Stagehand step"
```

---

### Task 4: Update active project documentation and verify the slice

**Files:**
- Modify: `docs/current-project-overview.zh-CN.md`
- Modify: `docs/project-structure.zh-CN.md`
- Modify: `docs/project-decisions.zh-CN.md`

**Interfaces:**
- Documents the implemented behavior only; no new runtime interface.

- [ ] **Step 1: Update the three active Chinese documents**

Record these exact decisions in the relevant controller/output sections:

```text
- 当前真实 Stagehand 实验以最大步数作为主要终止条件。
- 当前节点没有可执行候选时仍可自然提前结束。
- 当前真实实验暂时关闭连续无进展终止，但 controller 保留可选能力。
- 每个完成的动作都会原子更新 latest checkpoint；正常结束后再写一次最终结果。
- checkpoint 只防止已完成探索丢失，不提供恢复、重放或逐步历史版本。
```

Remove or mark obsolete any active-document sentence claiming the current real runner always stops after three unproductive steps. Preserve clearly labelled historical decision records.

- [ ] **Step 2: Run formatting and targeted tests**

Run:

```powershell
git diff --check
./.venv/Scripts/python.exe -m pytest -q tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_web_kobe_controller.py tests/safesym_bridge/test_state_embedding.py
```

Expected: `git diff --check` is silent and all tests PASS.

- [ ] **Step 3: Run the full test suite**

Run:

```powershell
./.venv/Scripts/python.exe -m pytest -q
```

Expected: all tests PASS. If a test fails, report the exact failure and determine whether it is caused by this slice before changing unrelated code.

- [ ] **Step 4: Inspect the final diff for scope**

Run:

```powershell
git status --short
git diff --stat HEAD~3
git diff HEAD~3 -- src/ai_web_explorer/grounded_web/controller.py src/ai_web_explorer/grounded_web/state_embedding.py src/ai_web_explorer/safesym_bridge/browser_runner.py
```

Expected: changes are limited to checkpoint persistence, runner stop configuration, tests, and the three active documents. There must be no state-matching or PDDL changes.

- [ ] **Step 5: Commit documentation**

```powershell
git add docs/current-project-overview.zh-CN.md docs/project-structure.zh-CN.md docs/project-decisions.zh-CN.md
git commit -m "Document bounded checkpointed exploration"
```
