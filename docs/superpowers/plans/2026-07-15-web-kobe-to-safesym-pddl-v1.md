# Web-KOBE to SafeSym PDDL v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not use subagents unless the project owner explicitly allows them.

**Goal:** Generate simple SafeSym-consumable `domain.pddl` and `problem.pddl` files from an explored `WebKobeGraph` JSON.

**Architecture:** Extend the existing `web_kobe_pddl_projector.py` instead of introducing a second compiler. The projector remains the single boundary from grounded Web-KOBE graph data to planner-facing PDDL; the CLI adds a formal file-based entrypoint for explored graph JSON.

**Tech Stack:** Python dataclasses, argparse CLI, pytest, existing `ai_web_explorer.grounded_web.graph` and `ai_web_explorer.grounded_web.capability_graph` models.

## Global Constraints

- Keep PDDL simple STRIPS boolean PDDL.
- Do not add LLM/VLM reasoning in this milestone.
- Do not run SafeSym/Fast Downward automatically.
- Do not infer user goals or sensitive actions automatically.
- Use explicit `--goal-node`; use `--start-node` only as an optional override.
- Default start node is `graph.start_node_id`.
- Exclude failed, no-change, and unexpected edges from generated domain actions.
- Treat numeric/count values as boolean positive predicates such as `cart_count_positive`.
- Update both current project overview docs after implementation.
- Single-agent implementation only unless the user explicitly allows multi-agent work.

---

## File Structure

- Modify `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
  - Responsibility: compile `WebKobeGraph` objects to PDDL.
  - Add graph validation, start-node override, successful-edge filtering, positive numeric predicates, and JSON loader helpers.

- Modify `src/ai_web_explorer/safesym_bridge/cli.py`
  - Responsibility: expose formal command-line workflows.
  - Add `web-kobe-pddl-from-graph` command.

- Modify `tests/safesym_bridge/test_web_kobe_pddl_projector.py`
  - Responsibility: unit-test graph-to-PDDL projection behavior.
  - Add focused tests for numeric facts, edge filtering, start/goal validation, and JSON loading.

- Modify `tests/safesym_bridge/test_cli.py`
  - Responsibility: unit-test CLI routing and file output.
  - Add test for `web-kobe-pddl-from-graph`.

- Modify `docs/current-project-overview.md`
  - Responsibility: English living project overview.
  - Record that WebKobeGraph-to-PDDL projection is the current mainline.

- Modify `docs/current-project-overview.zh-CN.md`
  - Responsibility: Chinese living project overview.
  - Mirror the English overview update.

---

## Task 1: Strengthen projector validation and start/goal selection

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
- Modify: `tests/safesym_bridge/test_web_kobe_pddl_projector.py`

**Interfaces:**
- Consumes: `WebKobeGraph`, `WebKobeNode`
- Produces:
  - `compile_web_kobe_graph_to_pddl(graph: WebKobeGraph, *, goal_node_id: str, start_node_id: str | None = None) -> WebKobePddlArtifacts`

- [ ] **Step 1: Write failing tests for explicit start and missing goal**

Add these tests to `tests/safesym_bridge/test_web_kobe_pddl_projector.py`:

```python
def test_compile_web_kobe_graph_to_pddl_uses_custom_start_node():
    graph = WebKobeGraph(
        app="example",
        start_node_id="landing",
        total_steps_completed=0,
        nodes=[
            _node("landing", "landing", {"cart_nonempty": False}),
            _node("cart", "cart", {"cart_nonempty": True}),
        ],
        edges=[],
    )

    artifacts = compile_web_kobe_graph_to_pddl(
        graph,
        start_node_id="cart",
        goal_node_id="cart",
    )

    assert "(:init (at_cart) (cart_nonempty))" in artifacts.problem


def test_compile_web_kobe_graph_to_pddl_rejects_missing_goal_node():
    graph = WebKobeGraph(
        app="example",
        start_node_id="landing",
        total_steps_completed=0,
        nodes=[_node("landing", "landing", {})],
        edges=[],
    )

    with pytest.raises(ValueError, match="Unknown goal node"):
        compile_web_kobe_graph_to_pddl(graph, goal_node_id="missing")
```

Also add `import pytest` at the top of the test file.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py -q
```

Expected: tests fail because `start_node_id` is not accepted and missing goal validation is not implemented.

- [ ] **Step 3: Implement validation and start override**

In `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`, replace `_initial_predicates` and update the compiler signature:

```python
def _nodes_by_id(graph: WebKobeGraph) -> dict[str, object]:
    return {node.node_id: node for node in graph.nodes}


def _require_node(graph: WebKobeGraph, node_id: str, *, role: str):
    nodes = _nodes_by_id(graph)
    if node_id not in nodes:
        raise ValueError(f"Unknown {role} node: {node_id}")
    return nodes[node_id]


def _initial_predicates(graph: WebKobeGraph, *, start_node_id: str) -> list[str]:
    start = _require_node(graph, start_node_id, role="start")
    predicates = [_at(start.node_id)]
    for key, value in start.last_state_snapshot.items():
        if isinstance(value, bool) and value is True:
            predicates.append(_predicate(key))
    return sorted(set(predicates))
```

Update:

```python
def compile_web_kobe_graph_to_pddl(
    graph: WebKobeGraph,
    *,
    goal_node_id: str,
    start_node_id: str | None = None,
) -> WebKobePddlArtifacts:
    selected_start_node_id = start_node_id or graph.start_node_id
    _require_node(graph, selected_start_node_id, role="start")
    _require_node(graph, goal_node_id, role="goal")
```

Update init generation:

```python
init_text = " ".join(
    f"({name})"
    for name in _initial_predicates(graph, start_node_id=selected_start_node_id)
)
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py -q
```

Expected: all projector tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py tests/safesym_bridge/test_web_kobe_pddl_projector.py
git commit -m "feat: validate web kobe pddl start and goal nodes"
```

---

## Task 2: Add numeric/count positive predicate projection

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
- Modify: `tests/safesym_bridge/test_web_kobe_pddl_projector.py`

**Interfaces:**
- Consumes: node `last_state_snapshot`, edge `observed_delta`
- Produces:
  - `_state_predicate_for_value(key: str, value: object) -> str | None`
  - `_positive_predicate(name: str) -> str`

- [ ] **Step 1: Write failing tests for positive numeric facts**

Add:

```python
def test_compile_web_kobe_graph_to_pddl_projects_positive_numeric_facts():
    graph = WebKobeGraph(
        app="example",
        start_node_id="empty",
        total_steps_completed=1,
        nodes=[
            _node("empty", "listing", {"cart_count": 0}),
            _node("filled", "listing", {"cart_count": 1}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="empty",
                target_node_id="filled",
                instruction="add to cart",
                action=BrowserAction("click", "button.add", "add_to_cart"),
                capability=None,
                target_observation="filled cart",
                observed_delta=[
                    ObservedDelta(
                        "cart_count",
                        0,
                        1,
                        "state_indicator_change",
                        evidence=[Evidence(source="unit_test")],
                    )
                ],
                schema_delta={"cart_count": {"before": 0, "after": 1}},
                execution_trace=ExecutionTrace(
                    "click",
                    "button.add",
                    "add",
                    {},
                    "empty",
                    "filled",
                    True,
                ),
            )
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(graph, goal_node_id="filled")

    assert "(cart_count_positive)" in artifacts.domain
    assert "(:effect (and (not (at_empty)) (at_filled) (cart_count_positive)))" in artifacts.domain
    assert "(cart_count_positive)" not in artifacts.problem
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py::test_compile_web_kobe_graph_to_pddl_projects_positive_numeric_facts -q
```

Expected: fails because numeric predicates are not projected.

- [ ] **Step 3: Implement positive numeric projection**

Add helpers:

```python
def _is_positive_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value > 0


def _is_zero_or_negative_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value <= 0


def _positive_predicate(name: str) -> str:
    return f"{_predicate(name)}_positive"


def _state_predicate_for_value(key: str, value: object) -> str | None:
    if isinstance(value, bool):
        return _predicate(key)
    if _is_positive_number(value):
        return _positive_predicate(key)
    return None
```

Replace `_boolean_predicates` with:

```python
def _state_predicates(graph: WebKobeGraph) -> list[str]:
    names: set[str] = set()
    for node in graph.nodes:
        for key, value in node.last_state_snapshot.items():
            predicate = _state_predicate_for_value(key, value)
            if predicate is not None:
                names.add(predicate)
    return sorted(names)
```

Update `_initial_predicates`:

```python
for key, value in start.last_state_snapshot.items():
    if isinstance(value, bool) and value is True:
        predicates.append(_predicate(key))
    elif _is_positive_number(value):
        predicates.append(_positive_predicate(key))
```

Update `_effects_for_edge` numeric handling:

```python
elif _is_zero_or_negative_number(delta.before) and _is_positive_number(delta.after):
    effects.append(f"({_positive_predicate(delta.field)})")
elif _is_positive_number(delta.before) and _is_zero_or_negative_number(delta.after):
    effects.append(f"(not ({_positive_predicate(delta.field)}))")
```

Update predicate list:

```python
predicates = sorted(set([_at(node.node_id) for node in graph.nodes] + _state_predicates(graph)))
```

- [ ] **Step 4: Run projector tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py tests/safesym_bridge/test_web_kobe_pddl_projector.py
git commit -m "feat: project web kobe numeric facts as positive predicates"
```

---

## Task 3: Filter unsuccessful and unsafe-to-project graph edges

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
- Modify: `tests/safesym_bridge/test_web_kobe_pddl_projector.py`

**Interfaces:**
- Produces:
  - `_is_projectable_edge(edge) -> bool`

- [ ] **Step 1: Write failing edge filtering test**

Add:

```python
def test_compile_web_kobe_graph_to_pddl_excludes_non_projectable_edges():
    nodes = [
        _node("start", "start", {}),
        _node("success", "success", {}),
        _node("failed", "failed", {}),
        _node("no_change", "no_change", {}),
        _node("unexpected", "unexpected", {}),
    ]

    def edge(target: str, semantic_id: str, success: bool, status: str) -> WebKobeEdge:
        return WebKobeEdge(
            source_node_id="start",
            target_node_id=target,
            instruction=semantic_id,
            action=BrowserAction("click", f"#{semantic_id}", semantic_id),
            capability=None,
            target_observation=target,
            observed_delta=[],
            schema_delta={},
            execution_trace=ExecutionTrace(
                "click",
                f"#{semantic_id}",
                semantic_id,
                {},
                "start",
                target,
                success,
            ),
            status=status,
        )

    graph = WebKobeGraph(
        app="example",
        start_node_id="start",
        total_steps_completed=4,
        nodes=nodes,
        edges=[
            edge("success", "go_success", True, "succeeded_with_observed_change"),
            edge("failed", "go_failed", False, "failed_execution"),
            edge("no_change", "go_no_change", True, "no_observed_change"),
            edge("unexpected", "go_unexpected", True, "unexpected_change"),
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(graph, goal_node_id="success")

    assert "(:action go_success" in artifacts.domain
    assert "(:action go_failed" not in artifacts.domain
    assert "(:action go_no_change" not in artifacts.domain
    assert "(:action go_unexpected" not in artifacts.domain
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py::test_compile_web_kobe_graph_to_pddl_excludes_non_projectable_edges -q
```

Expected: fails because all edges are currently projected.

- [ ] **Step 3: Implement projectable edge filter**

Add:

```python
PROJECTABLE_EDGE_STATUSES = {
    "verified",
    "succeeded",
    "succeeded_with_observed_change",
}


def _is_projectable_edge(edge) -> bool:
    return edge.execution_trace.success and edge.status in PROJECTABLE_EDGE_STATUSES
```

Update the action loop:

```python
for edge in graph.edges:
    if not _is_projectable_edge(edge):
        continue
    action_name = _action_name(edge.action.semantic_id)
```

- [ ] **Step 4: Run projector tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py tests/safesym_bridge/test_web_kobe_pddl_projector.py
git commit -m "feat: filter web kobe pddl actions by observed success"
```

---

## Task 4: Load WebKobeGraph from JSON

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
- Modify: `tests/safesym_bridge/test_web_kobe_pddl_projector.py`

**Interfaces:**
- Produces:
  - `load_web_kobe_graph_json(path: Path) -> WebKobeGraph`
  - `_web_kobe_graph_from_dict(data: dict[str, object]) -> WebKobeGraph`

- [ ] **Step 1: Write failing JSON loader test**

Add imports:

```python
import json
```

Update projector import:

```python
from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
    compile_web_kobe_graph_to_pddl,
    load_web_kobe_graph_json,
)
```

Add:

```python
def test_load_web_kobe_graph_json_reads_to_dict_output(tmp_path):
    graph = WebKobeGraph(
        app="example",
        start_node_id="empty",
        total_steps_completed=1,
        nodes=[
            _node("empty", "listing", {"cart_count": 0}),
            _node("filled", "listing", {"cart_count": 1}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="empty",
                target_node_id="filled",
                instruction="add to cart",
                action=BrowserAction("click", "button.add", "add_to_cart"),
                capability=None,
                target_observation="filled cart",
                observed_delta=[
                    ObservedDelta(
                        "cart_count",
                        0,
                        1,
                        "state_indicator_change",
                        evidence=[Evidence(source="unit_test")],
                    )
                ],
                schema_delta={"cart_count": {"before": 0, "after": 1}},
                execution_trace=ExecutionTrace(
                    "click",
                    "button.add",
                    "add",
                    {},
                    "empty",
                    "filled",
                    True,
                ),
            )
        ],
    )
    path = tmp_path / "web_kobe_graph.json"
    path.write_text(json.dumps(graph.to_dict()), encoding="utf-8")

    loaded = load_web_kobe_graph_json(path)

    assert loaded.app == "example"
    assert loaded.start_node_id == "empty"
    assert loaded.nodes[1].last_state_snapshot == {"cart_count": 1}
    assert loaded.edges[0].action.semantic_id == "add_to_cart"
    assert loaded.edges[0].execution_trace.success is True
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py::test_load_web_kobe_graph_json_reads_to_dict_output -q
```

Expected: fails because `load_web_kobe_graph_json` does not exist.

- [ ] **Step 3: Implement minimal JSON loader**

Add imports:

```python
import json
from pathlib import Path
from typing import Any

from ai_web_explorer.grounded_web.capability_graph import (
    Evidence,
    ExecutionTrace,
    ObservedDelta,
    PageFrame,
)
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    ReferenceObservation,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
```

Add helpers:

```python
def _evidence_from_dict(data: dict[str, Any]) -> Evidence:
    return Evidence(
        source=str(data.get("source", "json")),
        selector=data.get("selector"),
        text_sample=data.get("text_sample"),
        url=data.get("url"),
        confidence=float(data.get("confidence", 1.0)),
    )


def _page_frame_from_dict(data: dict[str, Any]) -> PageFrame:
    return PageFrame(
        page_id=str(data.get("page_id", "")),
        page_type=str(data.get("page_type", "")),
        url=str(data.get("url", "")),
        url_pattern=str(data.get("url_pattern", data.get("url", ""))),
        title=str(data.get("title", "")),
        heading=data.get("heading"),
        signature_hints=dict(data.get("signature_hints", {})),
        evidence=[_evidence_from_dict(item) for item in data.get("evidence", [])],
    )


def _reference_observation_from_dict(data: dict[str, Any] | None) -> ReferenceObservation | None:
    if data is None:
        return None
    return ReferenceObservation(
        url=str(data.get("url", "")),
        title=str(data.get("title", "")),
        screenshot_path=data.get("screenshot_path"),
        dom_summary=data.get("dom_summary"),
        accessibility_summary=data.get("accessibility_summary"),
        observation_hash=data.get("observation_hash"),
    )


def _node_from_dict(data: dict[str, Any]) -> WebKobeNode:
    return WebKobeNode(
        node_id=str(data["node_id"]),
        page_description=str(data.get("page_description", "")),
        page_frame=_page_frame_from_dict(dict(data.get("page_frame", {}))),
        state_schema={key: list(values) for key, values in dict(data.get("state_schema", {})).items()},
        last_state_snapshot=dict(data.get("last_state_snapshot", {})),
        reference_observation=_reference_observation_from_dict(data.get("reference_observation")),
        visit_count=int(data.get("visit_count", 0)),
        status=str(data.get("status", "verified")),
        evidence=[_evidence_from_dict(item) for item in data.get("evidence", [])],
    )


def _action_from_dict(data: dict[str, Any]) -> BrowserAction:
    return BrowserAction(
        action_kind=str(data.get("action_kind", "")),
        locator=data.get("locator"),
        semantic_id=str(data["semantic_id"]),
        input_values=dict(data.get("input_values", {})),
        description=data.get("description"),
    )


def _observed_delta_from_dict(data: dict[str, Any]) -> ObservedDelta:
    return ObservedDelta(
        field=str(data["field"]),
        before=data.get("before"),
        after=data.get("after"),
        delta_type=str(data.get("delta_type", "unknown")),
        confidence=float(data.get("confidence", 1.0)),
        evidence=[_evidence_from_dict(item) for item in data.get("evidence", [])],
    )


def _execution_trace_from_dict(data: dict[str, Any]) -> ExecutionTrace:
    return ExecutionTrace(
        concrete_action_kind=str(data.get("concrete_action_kind", "")),
        concrete_locator=data.get("concrete_locator"),
        concrete_target_sample=data.get("concrete_target_sample"),
        input_values_used=dict(data.get("input_values_used", {})),
        before_observation_id=str(data.get("before_observation_id", "")),
        after_observation_id=str(data.get("after_observation_id", "")),
        success=bool(data.get("success", False)),
        error=data.get("error"),
    )


def _edge_from_dict(data: dict[str, Any]) -> WebKobeEdge:
    return WebKobeEdge(
        source_node_id=str(data["source_node_id"]),
        target_node_id=str(data["target_node_id"]),
        instruction=str(data.get("instruction", "")),
        action=_action_from_dict(dict(data["action"])),
        capability=None,
        target_observation=str(data.get("target_observation", "")),
        observed_delta=[_observed_delta_from_dict(item) for item in data.get("observed_delta", [])],
        schema_delta=data.get("schema_delta"),
        execution_trace=_execution_trace_from_dict(dict(data.get("execution_trace", {}))),
        visit_count=int(data.get("visit_count", 1)),
        status=str(data.get("status", "verified")),
        evidence=[_evidence_from_dict(item) for item in data.get("evidence", [])],
    )


def _web_kobe_graph_from_dict(data: dict[str, Any]) -> WebKobeGraph:
    meta = dict(data.get("meta", {}))
    return WebKobeGraph(
        app=str(meta.get("app", "web")),
        start_node_id=str(meta["start_node_id"]),
        total_steps_completed=int(meta.get("total_steps_completed", 0)),
        nodes=[_node_from_dict(item) for item in data.get("nodes", [])],
        edges=[_edge_from_dict(item) for item in data.get("edges", [])],
        meta=meta,
    )


def load_web_kobe_graph_json(path: Path) -> WebKobeGraph:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("WebKobeGraph JSON root must be an object")
    return _web_kobe_graph_from_dict(data)
```

- [ ] **Step 4: Run projector tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py tests/safesym_bridge/test_web_kobe_pddl_projector.py
git commit -m "feat: load web kobe graph json for pddl projection"
```

---

## Task 5: Add formal CLI command for graph JSON to PDDL

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Modify: `tests/safesym_bridge/test_cli.py`

**Interfaces:**
- Consumes:
  - `load_web_kobe_graph_json(path: Path) -> WebKobeGraph`
  - `compile_web_kobe_graph_to_pddl(graph, goal_node_id=..., start_node_id=...)`
- Produces:
  - CLI command `web-kobe-pddl-from-graph`

- [ ] **Step 1: Write failing CLI test**

Update test import helper as needed:

```python
from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, ObservedDelta, PageFrame
from ai_web_explorer.grounded_web.graph import BrowserAction, WebKobeEdge, WebKobeGraph, WebKobeNode
```

Add:

```python
def test_main_web_kobe_pddl_from_graph_writes_domain_and_problem(tmp_path):
    graph_path = tmp_path / "web_kobe_graph.json"
    output_dir = tmp_path / "web_kobe_pddl"
    graph = WebKobeGraph(
        app="example",
        start_node_id="empty",
        total_steps_completed=1,
        nodes=[
            WebKobeNode(
                node_id="empty",
                page_description="empty page",
                page_frame=PageFrame(
                    page_id="empty",
                    page_type="listing",
                    url="https://example.test",
                    url_pattern="https://example.test",
                    title="empty",
                ),
                state_schema={"cart_count": [0]},
                last_state_snapshot={"cart_count": 0},
            ),
            WebKobeNode(
                node_id="filled",
                page_description="filled page",
                page_frame=PageFrame(
                    page_id="filled",
                    page_type="listing",
                    url="https://example.test",
                    url_pattern="https://example.test",
                    title="filled",
                ),
                state_schema={"cart_count": [1]},
                last_state_snapshot={"cart_count": 1},
            ),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="empty",
                target_node_id="filled",
                instruction="add to cart",
                action=BrowserAction("click", "button.add", "add_to_cart"),
                capability=None,
                target_observation="filled cart",
                observed_delta=[ObservedDelta("cart_count", 0, 1, "state_indicator_change")],
                schema_delta={"cart_count": {"before": 0, "after": 1}},
                execution_trace=ExecutionTrace(
                    "click",
                    "button.add",
                    "add",
                    {},
                    "empty",
                    "filled",
                    True,
                ),
            )
        ],
    )
    graph_path.write_text(json.dumps(graph.to_dict()), encoding="utf-8")

    exit_code = main(
        [
            "web-kobe-pddl-from-graph",
            "--graph",
            str(graph_path),
            "--output",
            str(output_dir),
            "--goal-node",
            "filled",
        ]
    )

    assert exit_code == 0
    assert "(:action add_to_cart" in (output_dir / "domain.pddl").read_text(encoding="utf-8")
    assert "(:goal (and (at_filled)))" in (output_dir / "problem.pddl").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_cli.py::test_main_web_kobe_pddl_from_graph_writes_domain_and_problem -q
```

Expected: fails because command is not registered.

- [ ] **Step 3: Implement CLI command**

In `src/ai_web_explorer/safesym_bridge/cli.py`, update import:

```python
from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
    compile_web_kobe_graph_to_pddl,
    load_web_kobe_graph_json,
)
```

Add parser after `web-kobe-pddl`:

```python
    web_kobe_pddl_from_graph_parser = subparsers.add_parser(
        "web-kobe-pddl-from-graph",
        help="Write PDDL from an explored Web-KOBE graph JSON.",
    )
    web_kobe_pddl_from_graph_parser.add_argument(
        "--graph",
        type=Path,
        required=True,
        help="Path to an explored Web-KOBE graph JSON.",
    )
    web_kobe_pddl_from_graph_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/web_kobe_pddl"),
        help="Directory to write domain.pddl and problem.pddl.",
    )
    web_kobe_pddl_from_graph_parser.add_argument(
        "--goal-node",
        required=True,
        help="Goal node ID for the generated Web-KOBE PDDL problem.",
    )
    web_kobe_pddl_from_graph_parser.add_argument(
        "--start-node",
        default=None,
        help="Optional start node override. Defaults to graph.start_node_id.",
    )
```

Add branch:

```python
        elif args.mode == "web-kobe-pddl-from-graph":
            graph = load_web_kobe_graph_json(args.graph)
            artifacts = compile_web_kobe_graph_to_pddl(
                graph,
                start_node_id=args.start_node,
                goal_node_id=args.goal_node,
            )
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / "domain.pddl").write_text(
                artifacts.domain,
                encoding="utf-8",
            )
            (args.output / "problem.pddl").write_text(
                artifacts.problem,
                encoding="utf-8",
            )
            output_path = args.output
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_cli.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/cli.py tests/safesym_bridge/test_cli.py
git commit -m "feat: add web kobe pddl from graph cli"
```

---

## Task 6: Update current project overview docs

**Files:**
- Modify: `docs/current-project-overview.md`
- Modify: `docs/current-project-overview.zh-CN.md`

**Interfaces:**
- Consumes: completed implementation behavior
- Produces: updated living architecture notes

- [ ] **Step 1: Update English overview**

In `docs/current-project-overview.md`, update the current status / next milestone section to include:

```markdown
The current mainline is now WebKobeGraph-to-PDDL projection: take the graph produced by grounded Web-KOBE exploration, project successful observed transitions into a simple STRIPS `domain.pddl`, and create a concrete `problem.pddl` from explicit start/goal node selection. This keeps `grounded_web` as the exploration/observation layer and `safesym_bridge` as the planner-facing projection layer.
```

- [ ] **Step 2: Update Chinese overview**

In `docs/current-project-overview.zh-CN.md`, add the matching Chinese status:

```markdown
当前主线已经收束到 WebKobeGraph-to-PDDL 投影：使用 grounded Web-KOBE 探索得到的状态图，将成功且有观察意义的转移投影成简单 STRIPS `domain.pddl`，并通过显式 start/goal 节点生成具体 `problem.pddl`。这保持了 `grounded_web` 作为网页探索/观察层、`safesym_bridge` 作为面向规划器投影层的边界。
```

- [ ] **Step 3: Commit**

```bash
git add docs/current-project-overview.md docs/current-project-overview.zh-CN.md
git commit -m "docs: update overview for web kobe pddl projection"
```

---

## Task 7: Full verification

**Files:**
- No source edits expected.

**Interfaces:**
- Verifies all previous task outputs.

- [ ] **Step 1: Run SafeSym bridge tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/safesym_bridge -q
```

Expected: all tests pass.

- [ ] **Step 2: Manually verify CLI help includes new command**

Run:

```bash
.venv\Scripts\python.exe -m ai_web_explorer.safesym_bridge.cli --help
```

Expected: help includes `web-kobe-pddl-from-graph`.

- [ ] **Step 3: Inspect git status**

Run:

```bash
git status --short
```

Expected: no uncommitted changes.

---

## Self-Review

### Spec coverage

- Explicit graph JSON input: Task 4 and Task 5.
- `domain.pddl` / `problem.pddl` output: Task 5.
- Explicit start/goal node selection: Task 1 and Task 5.
- Whole-graph domain, selected-node problem: Task 1 through Task 5.
- Boolean predicates: preserved from existing projector.
- Numeric/count positive predicates: Task 2.
- Successful-edge filtering: Task 3.
- Failed/no-change/unexpected exclusion: Task 3.
- JSON loader from `WebKobeGraph.to_dict()`: Task 4.
- CLI formal command: Task 5.
- Current overview updates: Task 6.
- Full verification: Task 7.

### Placeholder scan

No `TBD`, `TODO`, or unspecified “add tests” steps remain. Each task has concrete files, interfaces, commands, and expected outcomes.

### Type consistency

The plan consistently uses `compile_web_kobe_graph_to_pddl(graph, *, goal_node_id, start_node_id=None)`, `load_web_kobe_graph_json(path)`, existing `WebKobeGraph`, `WebKobeNode`, `WebKobeEdge`, `BrowserAction`, `ObservedDelta`, `ExecutionTrace`, and `PageFrame` types.
