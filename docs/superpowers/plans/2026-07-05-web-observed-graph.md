# Web Observed Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a UI-KOBE-inspired WebObservedGraph that records abstract page nodes, interactable elements, semantic edges, and can export the safety-relevant subset to SafeSym FSM JSON.

**Architecture:** Keep the graph inside `src/ai_web_explorer/safesym_bridge/` as a focused bridge artifact. Build the graph from existing `ObservedTransition` objects first, then export the graph through the existing SafeSym model path so current downstream validation remains intact.

**Tech Stack:** Python dataclasses, existing SafeSym bridge models/exporter/validator, pytest, Playwright runner already present in the project.

## Global Constraints

- Do not rewrite `loop.py` or integrate the main `ai-web-explorer` `ExploreLoop` in this plan.
- Do not implement generic LLM/embedding node merging in v1.
- Do not store merge reasoning, LLM explanations, confidence scores, screenshots, embeddings, full HTML, or Playwright traces in the main graph JSON.
- Preserve existing fixed and observed CLI behavior.
- `outputs/` remains generated local output and must not be committed.
- Run tests with the existing main virtualenv and worktree `PYTHONPATH`:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge -v
```

---

### Task 1: WebObservedGraph data model

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/observed_graph.py`
- Test: `tests/safesym_bridge/test_observed_graph.py`

**Interfaces:**
- Consumes: `ValidationResult` style is not needed in this task.
- Produces:
  - `@dataclass class InteractableElement`
  - `@dataclass class WebObservedNode`
  - `@dataclass class WebObservedEdge`
  - `@dataclass class WebObservedGraph`
  - `WebObservedGraph.to_dict(self) -> dict[str, object]`

- [ ] **Step 1: Write the failing model serialization test**

Add `tests/safesym_bridge/test_observed_graph.py`:

```python
from ai_web_explorer.safesym_bridge.observed_graph import (
    InteractableElement,
    WebObservedEdge,
    WebObservedGraph,
    WebObservedNode,
)


def test_web_observed_graph_to_dict_uses_expected_shape():
    graph = WebObservedGraph(
        app="saucedemo",
        start_node="login",
        total_steps_completed=1,
        nodes=[
            WebObservedNode(
                id="inventory",
                page_description="product listing page",
                url_patterns=["/inventory.html"],
                state_schema={"$.cart_count": "number"},
                observed_values={"$.cart_count": [0, 1]},
                last_state_snapshot={"$.cart_count": 1},
                interactable_elements=[
                    InteractableElement(
                        description="shopping cart link",
                        position="top right",
                        explored=True,
                        execution_hints={"selector": ".shopping_cart_link"},
                    )
                ],
                visit_count=2,
            )
        ],
        edges=[
            WebObservedEdge(
                source="inventory",
                target="cart",
                semantic_action="cart_open",
                instructions=["Click the shopping cart link"],
                target_observations=["cart page"],
                schema_deltas=[],
                preconditions=[],
                effects=[],
                visit_count=1,
            )
        ],
    )

    assert graph.to_dict() == {
        "meta": {
            "schema_version": "web-observed-graph-v1",
            "app": "saucedemo",
            "start_node": "login",
            "total_steps_completed": 1,
        },
        "nodes": [
            {
                "id": "inventory",
                "page_description": "product listing page",
                "url_patterns": ["/inventory.html"],
                "state_schema": {"$.cart_count": "number"},
                "observed_values": {"$.cart_count": [0, 1]},
                "last_state_snapshot": {"$.cart_count": 1},
                "interactable_elements": [
                    {
                        "description": "shopping cart link",
                        "position": "top right",
                        "explored": True,
                        "execution_hints": {"selector": ".shopping_cart_link"},
                    }
                ],
                "visit_count": 2,
            }
        ],
        "edges": [
            {
                "source": "inventory",
                "target": "cart",
                "semantic_action": "cart_open",
                "instructions": ["Click the shopping cart link"],
                "target_observations": ["cart page"],
                "schema_deltas": [],
                "preconditions": [],
                "effects": [],
                "visit_count": 1,
            }
        ],
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_observed_graph.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'ai_web_explorer.safesym_bridge.observed_graph'`.

- [ ] **Step 3: Write minimal model implementation**

Create `src/ai_web_explorer/safesym_bridge/observed_graph.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = "web-observed-graph-v1"


@dataclass(frozen=True)
class InteractableElement:
    description: str
    position: str
    explored: bool = False
    execution_hints: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "description": self.description,
            "position": self.position,
            "explored": self.explored,
        }
        if self.execution_hints:
            data["execution_hints"] = dict(self.execution_hints)
        return data


@dataclass(frozen=True)
class WebObservedNode:
    id: str
    page_description: str
    url_patterns: list[str]
    state_schema: dict[str, str]
    observed_values: dict[str, list[Any]]
    last_state_snapshot: dict[str, Any]
    interactable_elements: list[InteractableElement] = field(default_factory=list)
    visit_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "page_description": self.page_description,
            "url_patterns": self.url_patterns,
            "state_schema": self.state_schema,
            "observed_values": self.observed_values,
            "last_state_snapshot": self.last_state_snapshot,
            "interactable_elements": [
                element.to_dict() for element in self.interactable_elements
            ],
            "visit_count": self.visit_count,
        }


@dataclass(frozen=True)
class WebObservedEdge:
    source: str
    target: str
    semantic_action: str
    instructions: list[str]
    target_observations: list[str]
    schema_deltas: list[dict[str, dict[str, Any]]]
    preconditions: list[dict[str, Any]]
    effects: list[dict[str, Any]]
    visit_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "semantic_action": self.semantic_action,
            "instructions": self.instructions,
            "target_observations": self.target_observations,
            "schema_deltas": self.schema_deltas,
            "preconditions": self.preconditions,
            "effects": self.effects,
            "visit_count": self.visit_count,
        }


@dataclass(frozen=True)
class WebObservedGraph:
    app: str
    start_node: str
    total_steps_completed: int
    nodes: list[WebObservedNode]
    edges: list[WebObservedEdge]

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": {
                "schema_version": SCHEMA_VERSION,
                "app": self.app,
                "start_node": self.start_node,
                "total_steps_completed": self.total_steps_completed,
            },
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }
```

- [ ] **Step 4: Run model test to verify it passes**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_observed_graph.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/observed_graph.py tests/safesym_bridge/test_observed_graph.py
git commit -m "feat: add Web observed graph models"
```

---

### Task 2: Build graph from observed transitions

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/observed_graph.py`
- Modify: `tests/safesym_bridge/test_observed_graph.py`

**Interfaces:**
- Consumes:
  - `ObservedTransition`
  - `schema_type_for(value: Any) -> str`
- Produces:
  - `build_observed_graph(app: str, start_node: str, transitions: list[ObservedTransition]) -> WebObservedGraph`

- [ ] **Step 1: Write failing graph builder test**

Append to `tests/safesym_bridge/test_observed_graph.py`:

```python
from ai_web_explorer.safesym_bridge.observed_graph import build_observed_graph
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions


def test_build_observed_graph_accumulates_nodes_values_and_edges():
    graph = build_observed_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
    )
    data = graph.to_dict()

    assert data["meta"]["schema_version"] == "web-observed-graph-v1"
    assert data["meta"]["app"] == "saucedemo"
    assert data["meta"]["start_node"] == "login"
    assert data["meta"]["total_steps_completed"] == 6

    nodes = {node["id"]: node for node in data["nodes"]}
    assert set(nodes) == {
        "login",
        "inventory",
        "cart",
        "checkout_info",
        "checkout_overview",
        "checkout_complete",
    }
    assert nodes["inventory"]["page_description"] == "inventory page"
    assert nodes["inventory"]["state_schema"]["$.cart_count"] == "number"
    assert nodes["inventory"]["observed_values"]["$.cart_count"] == [0, 1]
    assert nodes["inventory"]["last_state_snapshot"]["$.cart_count"] == 1
    assert nodes["inventory"]["visit_count"] == 3

    edges = {
        (edge["source"], edge["target"], edge["semantic_action"]): edge
        for edge in data["edges"]
    }
    add_to_cart = edges[("inventory", "inventory", "product_add_to_cart")]
    assert add_to_cart["instructions"] == ["Click Add to cart"]
    assert add_to_cart["schema_deltas"] == [
        {"$.cart_count": {"before": 0, "after": 1}}
    ]
    assert add_to_cart["effects"] == [
        {"path": "$.cart_count", "op": "set", "value": 1}
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_observed_graph.py -v
```

Expected: FAIL with `ImportError` or `AttributeError` for `build_observed_graph`.

- [ ] **Step 3: Implement graph builder helpers**

Add to `src/ai_web_explorer/safesym_bridge/observed_graph.py`:

```python
from collections import OrderedDict

from ai_web_explorer.safesym_bridge.fsm_exporter import schema_type_for
from ai_web_explorer.safesym_bridge.models import ObservedTransition, StateSnapshot


PAGE_DESCRIPTIONS = {
    "login": "login page",
    "inventory": "inventory page",
    "cart": "cart page",
    "checkout_info": "checkout information page",
    "checkout_overview": "checkout overview page",
    "checkout_complete": "checkout complete page",
}


def _url_pattern_for(url: str) -> str:
    if "saucedemo.com" not in url:
        return url
    if url.endswith("/") or url == "https://www.saucedemo.com":
        return "/"
    return "/" + url.rsplit("/", 1)[-1]


def _state_delta(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    delta: dict[str, dict[str, Any]] = {}
    for path in sorted(set(before) | set(after)):
        before_value = before.get(path)
        after_value = after.get(path)
        if before_value != after_value:
            delta[path] = {"before": before_value, "after": after_value}
    return delta


def _target_observation(snapshot: StateSnapshot) -> str:
    parts = [
        f"{path}={value}"
        for path, value in sorted(snapshot.signature.items())
        if value is not None
    ]
    description = PAGE_DESCRIPTIONS.get(snapshot.page_id, f"{snapshot.page_id} page")
    return f"{description} ({', '.join(parts)})" if parts else description


def build_observed_graph(
    *,
    app: str,
    start_node: str,
    transitions: list[ObservedTransition],
) -> WebObservedGraph:
    node_state: OrderedDict[str, dict[str, Any]] = OrderedDict()
    edge_state: OrderedDict[tuple[str, str, str], dict[str, Any]] = OrderedDict()

    def merge_snapshot(snapshot: StateSnapshot) -> None:
        if snapshot.page_id not in node_state:
            node_state[snapshot.page_id] = {
                "url_patterns": [],
                "state_schema": {},
                "observed_values": {},
                "last_state_snapshot": {},
                "visit_count": 0,
            }
        record = node_state[snapshot.page_id]
        pattern = _url_pattern_for(snapshot.url)
        if pattern not in record["url_patterns"]:
            record["url_patterns"].append(pattern)
        for path, value in snapshot.signature.items():
            record["state_schema"][path] = schema_type_for(value)
            values = record["observed_values"].setdefault(path, [])
            if value not in values:
                values.append(value)
        record["last_state_snapshot"] = dict(snapshot.signature)
        record["visit_count"] += 1

    for transition in transitions:
        merge_snapshot(transition.source)
        merge_snapshot(transition.target)
        edge_key = (
            transition.source.page_id,
            transition.target.page_id,
            transition.action.semantic_id,
        )
        delta = _state_delta(transition.source.signature, transition.target.signature)
        if edge_key not in edge_state:
            edge_state[edge_key] = {
                "instructions": [],
                "target_observations": [],
                "schema_deltas": [],
                "preconditions": transition.preconditions,
                "effects": transition.effects,
                "visit_count": 0,
            }
        record = edge_state[edge_key]
        if transition.action.raw_description not in record["instructions"]:
            record["instructions"].append(transition.action.raw_description)
        observation = _target_observation(transition.target)
        if observation not in record["target_observations"]:
            record["target_observations"].append(observation)
        if delta:
            record["schema_deltas"].append(delta)
        record["visit_count"] += 1

    nodes = [
        WebObservedNode(
            id=node_id,
            page_description=PAGE_DESCRIPTIONS.get(node_id, f"{node_id} page"),
            url_patterns=record["url_patterns"],
            state_schema=dict(sorted(record["state_schema"].items())),
            observed_values={
                path: values
                for path, values in sorted(record["observed_values"].items())
            },
            last_state_snapshot=dict(sorted(record["last_state_snapshot"].items())),
            interactable_elements=[],
            visit_count=record["visit_count"],
        )
        for node_id, record in node_state.items()
    ]
    edges = [
        WebObservedEdge(
            source=source,
            target=target,
            semantic_action=action,
            instructions=record["instructions"],
            target_observations=record["target_observations"],
            schema_deltas=record["schema_deltas"],
            preconditions=record["preconditions"],
            effects=record["effects"],
            visit_count=record["visit_count"],
        )
        for (source, target, action), record in edge_state.items()
    ]
    return WebObservedGraph(
        app=app,
        start_node=start_node,
        total_steps_completed=len(transitions),
        nodes=nodes,
        edges=edges,
    )
```

- [ ] **Step 4: Run graph builder tests**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_observed_graph.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/observed_graph.py tests/safesym_bridge/test_observed_graph.py
git commit -m "feat: build observed graph from transitions"
```

---

### Task 3: Export WebObservedGraph to SafeSym FSM

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/graph_exporter.py`
- Test: `tests/safesym_bridge/test_graph_exporter.py`

**Interfaces:**
- Consumes:
  - `WebObservedGraph`
  - `SafeSymFsm`, `SafeSymPage`, `SafeSymAction`
- Produces:
  - `graph_to_fsm(graph: WebObservedGraph, *, terminal_pages: list[str]) -> SafeSymFsm`

- [ ] **Step 1: Write failing exporter test**

Create `tests/safesym_bridge/test_graph_exporter.py`:

```python
from ai_web_explorer.safesym_bridge.graph_exporter import graph_to_fsm
from ai_web_explorer.safesym_bridge.observed_graph import build_observed_graph
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions


def test_graph_to_fsm_exports_safesym_shape_without_exploration_fields():
    graph = build_observed_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
    )

    fsm = graph_to_fsm(graph, terminal_pages=["checkout_complete"])
    data = fsm.to_dict()

    assert data["meta"] == {
        "app": "saucedemo",
        "initial_page_id": "login",
        "terminal_pages": ["checkout_complete"],
    }
    pages = {page["id"]: page for page in data["pages"]}
    assert "interactable_elements" not in pages["inventory"]
    assert pages["inventory"]["signature_schema"]["$.cart_count"] == "number"

    actions = [action for page in data["pages"] for action in page["actions"]]
    order_action = next(
        action for action in actions if action["id"] == "order_place_confirm"
    )
    assert order_action["from"] == "checkout_overview"
    assert order_action["to"] == "checkout_complete"
    assert order_action["effects"] == [
        {"path": "$.order_created", "op": "set", "value": True}
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_graph_exporter.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement graph exporter**

Create `src/ai_web_explorer/safesym_bridge/graph_exporter.py`:

```python
from __future__ import annotations

from ai_web_explorer.safesym_bridge.models import (
    SafeSymAction,
    SafeSymFsm,
    SafeSymPage,
)
from ai_web_explorer.safesym_bridge.observed_graph import WebObservedGraph


def graph_to_fsm(
    graph: WebObservedGraph,
    *,
    terminal_pages: list[str],
) -> SafeSymFsm:
    actions_by_page: dict[str, list[SafeSymAction]] = {
        node.id: [] for node in graph.nodes
    }
    for edge in graph.edges:
        actions_by_page.setdefault(edge.source, []).append(
            SafeSymAction(
                id=edge.semantic_action,
                name=edge.semantic_action,
                from_page=edge.source,
                to_page=edge.target,
                is_navigation=edge.source != edge.target,
                preconditions=edge.preconditions,
                effects=edge.effects,
            )
        )

    pages = [
        SafeSymPage(
            id=node.id,
            signature_schema=node.state_schema,
            actions=actions_by_page.get(node.id, []),
        )
        for node in graph.nodes
    ]
    return SafeSymFsm(
        app=graph.app,
        initial_page_id=graph.start_node,
        terminal_pages=terminal_pages,
        pages=pages,
    )
```

- [ ] **Step 4: Run exporter test**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_graph_exporter.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/graph_exporter.py tests/safesym_bridge/test_graph_exporter.py
git commit -m "feat: export observed graph to SafeSym FSM"
```

---

### Task 4: Write observed graph JSON from browser runner

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Modify: `tests/safesym_bridge/test_browser_runner.py`

**Interfaces:**
- Consumes:
  - `build_observed_graph(app, start_node, transitions)`
  - `graph_to_fsm(graph, terminal_pages)`
- Produces:
  - `write_observed_graph(transitions: list[ObservedTransition], output_path: Path) -> Path`
  - `write_observed_fsm(...)` uses graph export internally while preserving return behavior.

- [ ] **Step 1: Write failing graph writer test**

Append to `tests/safesym_bridge/test_browser_runner.py`:

```python
from ai_web_explorer.safesym_bridge.browser_runner import write_observed_graph


def test_write_observed_graph_writes_graph_json(tmp_path):
    output_path = tmp_path / "saucedemo_observed_graph.json"

    result_path = write_observed_graph(
        transitions=build_saucedemo_mvp_transitions(),
        output_path=output_path,
    )

    assert result_path == output_path
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["meta"]["schema_version"] == "web-observed-graph-v1"
    assert data["meta"]["app"] == "saucedemo"
    assert any(node["id"] == "inventory" for node in data["nodes"])
    assert any(
        edge["semantic_action"] == "order_place_confirm"
        for edge in data["edges"]
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_browser_runner.py -v
```

Expected: FAIL with import error for `write_observed_graph`.

- [ ] **Step 3: Implement graph writer and route FSM export through graph**

Modify `src/ai_web_explorer/safesym_bridge/browser_runner.py`:

```python
from ai_web_explorer.safesym_bridge.graph_exporter import graph_to_fsm
from ai_web_explorer.safesym_bridge.observed_graph import build_observed_graph
```

Add:

```python
def write_observed_graph(
    transitions: list[ObservedTransition],
    output_path: Path,
) -> Path:
    graph = build_observed_graph(
        app="saucedemo",
        start_node="login",
        transitions=transitions,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(graph.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path
```

Replace `write_observed_fsm` body with:

```python
def write_observed_fsm(
    transitions: list[ObservedTransition],
    output_path: Path,
) -> Path:
    graph = build_observed_graph(
        app="saucedemo",
        start_node="login",
        transitions=transitions,
    )
    fsm = graph_to_fsm(graph, terminal_pages=["checkout_complete"])
    validation = validate_fsm(fsm)
    if not validation.ok:
        joined = "; ".join(validation.errors)
        raise ValueError(f"Observed FSM failed validation: {joined}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(fsm.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path
```

- [ ] **Step 4: Run browser runner tests**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_browser_runner.py -v
```

Expected: PASS with real-browser smoke test skipped by default.

- [ ] **Step 5: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/browser_runner.py tests/safesym_bridge/test_browser_runner.py
git commit -m "feat: write observed graph from browser runner"
```

---

### Task 5: CLI graph output and docs

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Modify: `tests/safesym_bridge/test_cli.py`
- Modify: `docs/safesym-bridge.md`

**Interfaces:**
- Consumes:
  - `write_observed_graph(...)`
  - existing `run_saucedemo_observed_flow(...)`
- Produces:
  - Optional CLI subcommand: `graph`
  - Existing `fixed` and `observed` modes unchanged.

- [ ] **Step 1: Write failing CLI graph test**

Append to `tests/safesym_bridge/test_cli.py`:

```python
def test_main_graph_subcommand_writes_observed_graph(tmp_path):
    output_path = tmp_path / "observed_graph.json"

    exit_code = main(["graph", "--output", str(output_path)])

    assert exit_code == 0
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["meta"]["schema_version"] == "web-observed-graph-v1"
    assert data["meta"]["app"] == "saucedemo"
```

This first graph subcommand should use the deterministic fixed SauceDemo transitions. It gives users a cheap way to inspect the graph shape without launching a browser.

- [ ] **Step 2: Run CLI test to verify it fails**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_cli.py -v
```

Expected: FAIL with argparse rejecting `graph`.

- [ ] **Step 3: Implement CLI graph subcommand**

Modify imports in `src/ai_web_explorer/safesym_bridge/cli.py`:

```python
from ai_web_explorer.safesym_bridge.browser_runner import (
    run_saucedemo_observed_flow,
    write_observed_graph,
)
```

Add parser:

```python
    graph_parser = subparsers.add_parser(
        "graph",
        help="Write the SauceDemo observed graph JSON from fixed MVP transitions.",
    )
    graph_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/saucedemo_observed_graph.json"),
        help="Path to write the generated observed graph JSON.",
    )
```

Add branch in `main` before the fixed fallback:

```python
        elif args.mode == "graph":
            output_path = write_observed_graph(
                build_saucedemo_mvp_transitions(),
                args.output,
            )
```

- [ ] **Step 4: Run CLI tests**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Update docs**

Add to `docs/safesym-bridge.md` under the generation section:

````markdown
## Generate the observed graph

The graph command writes the UI-KOBE-inspired intermediate graph used by the bridge:

```bash
python -m ai_web_explorer.safesym_bridge.cli graph --output outputs/saucedemo_observed_graph.json
```

The graph is useful for debugging exploration state. SafeSym still consumes the exported FSM JSON, not the graph directly.
````

- [ ] **Step 6: Run full bridge tests**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge -v
```

Expected: all tests pass, with the real-browser smoke test skipped unless `RUN_SAUCEDEMO_BROWSER_TEST=1`.

- [ ] **Step 7: Verify generated graph and FSM commands**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m ai_web_explorer.safesym_bridge.cli graph --output outputs\saucedemo_observed_graph.json
```

Expected:

```text
Wrote SafeSym FSM to outputs\saucedemo_observed_graph.json
```

If the wording still says `SafeSym FSM`, adjust the print message in `cli.py` to:

```python
print(f"Wrote output to {output_path}")
```

Then rerun CLI tests.

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m ai_web_explorer.safesym_bridge.cli fixed --output outputs\saucedemo_fsm.json
```

Expected:

```text
Wrote output to outputs\saucedemo_fsm.json
```

- [ ] **Step 8: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/cli.py tests/safesym_bridge/test_cli.py docs/safesym-bridge.md
git commit -m "feat: add observed graph CLI output"
```

---

### Task 6: Final verification

**Files:**
- No required source changes unless a verification failure exposes a bug.

**Interfaces:**
- Consumes all previous tasks.
- Produces evidence that the branch is ready for review/merge.

- [ ] **Step 1: Run all bridge tests**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge -v
```

Expected: all tests pass, with the optional browser smoke test skipped by default.

- [ ] **Step 2: Generate fixed FSM**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m ai_web_explorer.safesym_bridge.cli fixed --output outputs\saucedemo_fsm.json
```

Expected: exit code 0 and output file exists.

- [ ] **Step 3: Generate observed graph**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m ai_web_explorer.safesym_bridge.cli graph --output outputs\saucedemo_observed_graph.json
```

Expected: exit code 0 and output file exists.

- [ ] **Step 4: Generate observed FSM with real browser if environment allows**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m ai_web_explorer.safesym_bridge.cli observed --output outputs\saucedemo_observed_fsm.json
```

Expected: exit code 0 if network and Playwright browser are available. If the browser or network fails, record the exact error and do not claim real-browser verification passed.

- [ ] **Step 5: Check git status**

Run:

```powershell
git status --short --branch
```

Expected: only user-owned pre-existing note/comment changes remain, or the tree is clean.

- [ ] **Step 6: Commit any verification docs only if changed**

If docs were updated during verification:

```powershell
git add docs/safesym-bridge.md
git commit -m "docs: update observed graph usage"
```

If no files changed, do not create an empty commit.
