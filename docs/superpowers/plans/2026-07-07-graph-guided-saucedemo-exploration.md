# Graph-Guided SauceDemo Exploration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This project should default to inline/single-agent execution unless the user explicitly permits subagents.

**Goal:** Build a semi-generic browser exploration loop that uses a SauceDemo adapter to automatically produce an explored `WebObservedGraph` and graph-derived PDDL.

**Architecture:** Add a generic `GraphExplorer` that drives observe/list/choose/execute/record/update without knowing SauceDemo selectors. Add a `SauceDemoAdapter` that provides deterministic SauceDemo state observation, candidate actions, action execution, and goal detection. Keep PDDL generation downstream of graph construction.

**Tech Stack:** Python dataclasses/protocols, existing Playwright browser runner, existing SafeSym bridge models, `pytest`, optional `anyio` browser smoke tests.

## Global Constraints

- Do not implement arbitrary website understanding.
- Do not add LLM/VLM page description.
- Do not add generic DOM action extraction.
- Do not add complex search or backtracking.
- Do not integrate the main `ai-web-explorer` `ExploreLoop`.
- Do not add screenshot, HTML, trace, or embedding sidecar storage.
- Keep `GraphExplorer` independent from SauceDemo selectors, URLs, credentials, cart badge behavior, and checkout page names.
- Keep the pipeline as `Adapter -> GraphExplorer -> WebObservedGraph -> PDDL compiler`.
- Default to single-agent/inline implementation.

---

## File Structure

- Create `src/ai_web_explorer/safesym_bridge/graph_explorer.py`
  - Owns `ExplorationAction`, `ExplorationAdapter`, `ExplorationRunResult`, action selection, and `GraphExplorer`.
- Create `src/ai_web_explorer/safesym_bridge/saucedemo_adapter.py`
  - Owns `SauceDemoAdapter`, deterministic candidate actions, action execution, and goal detection.
- Modify `src/ai_web_explorer/safesym_bridge/observed_graph.py`
  - Add optional action-derived interactable element population while building graph.
- Modify `src/ai_web_explorer/safesym_bridge/browser_runner.py`
  - Add browser helpers that run graph-guided exploration and write explored graph/PDDL outputs.
- Modify `src/ai_web_explorer/safesym_bridge/cli.py`
  - Add `explore-graph` and `explore-pddl` subcommands.
- Create `tests/safesym_bridge/test_graph_explorer.py`
  - Fast unit tests using fake adapters/pages.
- Create `tests/safesym_bridge/test_saucedemo_adapter.py`
  - Fast adapter tests using constructed `StateSnapshot` values.
- Modify `tests/safesym_bridge/test_observed_graph.py`
  - Verify adapter-declared action metadata can populate node `interactable_elements`.
- Modify `tests/safesym_bridge/test_browser_runner.py`
  - Verify new writer functions are callable and add optional smoke coverage.
- Modify `tests/safesym_bridge/test_cli.py`
  - Verify new CLI subcommands through monkeypatching and generated files.

---

### Task 1: Add Generic Graph Explorer Core

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/graph_explorer.py`
- Create: `tests/safesym_bridge/test_graph_explorer.py`

**Interfaces:**
- Produces:
  - `ExplorationAction`
  - `ExplorationAdapter`
  - `ExplorationRunResult`
  - `choose_next_unexplored_action(current_state: StateSnapshot, actions: list[ExplorationAction], graph: WebObservedGraph | None) -> ExplorationAction | None`
  - `GraphExplorer(adapter: ExplorationAdapter, max_steps: int = 20)`
  - `await GraphExplorer.run(page, *, output_path: Path | None = None) -> ExplorationRunResult`
- Consumes:
  - `ObservedAction`, `ObservedTransition`, `StateSnapshot` from `models.py`
  - `preconditions_for`, `infer_effects`
  - `build_observed_graph`

- [ ] **Step 1: Write failing tests for action selection and successful exploration**

Create `tests/safesym_bridge/test_graph_explorer.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from ai_web_explorer.safesym_bridge.graph_explorer import (
    ExplorationAction,
    GraphExplorer,
    choose_next_unexplored_action,
)
from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.observed_graph import build_observed_graph
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions


def snapshot(page_id: str, *, order_created: bool = False) -> StateSnapshot:
    return StateSnapshot(
        page_id=page_id,
        url=f"https://example.test/{page_id}",
        title=page_id,
        signature={
            "$.is_logged_in": page_id != "login",
            "$.cart_count": 0,
            "$.order_created": order_created,
        },
    )


def action(page_id: str, semantic_id: str) -> ExplorationAction:
    return ExplorationAction(
        raw_description=f"Run {semantic_id}",
        semantic_id=semantic_id,
        page_id=page_id,
        execution_kind="click",
        selector=f"#{semantic_id}",
    )


def test_choose_next_unexplored_action_returns_first_new_action():
    chosen = choose_next_unexplored_action(
        snapshot("login"),
        [action("login", "login_submit")],
        None,
    )

    assert chosen is not None
    assert chosen.semantic_id == "login_submit"


def test_choose_next_unexplored_action_skips_existing_source_action():
    graph = build_observed_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
    )

    chosen = choose_next_unexplored_action(
        snapshot("login"),
        [
            action("login", "login_submit"),
            action("login", "login_help"),
        ],
        graph,
    )

    assert chosen is not None
    assert chosen.semantic_id == "login_help"


class FakeAdapter:
    app_name = "fake"
    start_node = "login"
    start_url = "https://example.test/"

    def __init__(self):
        self.states = [
            snapshot("login"),
            snapshot("inventory"),
            snapshot("checkout_complete", order_created=True),
        ]
        self.executed: list[str] = []

    async def observe_state(self, page):
        return self.states[len(self.executed)]

    async def list_actions(self, page, state):
        if state.page_id == "login":
            return [action("login", "login_submit")]
        if state.page_id == "inventory":
            return [action("inventory", "order_place_confirm")]
        return []

    async def execute_action(self, page, selected_action):
        self.executed.append(selected_action.semantic_id)

    def is_goal_state(self, state):
        return state.page_id == "checkout_complete" and bool(
            state.signature.get("$.order_created")
        )


@pytest.mark.anyio
async def test_graph_explorer_records_transitions_until_goal(tmp_path: Path):
    output_path = tmp_path / "graph.json"
    adapter = FakeAdapter()
    explorer = GraphExplorer(adapter, max_steps=5)

    result = await explorer.run(object(), output_path=output_path)

    assert result.stop_reason == "goal_reached"
    assert result.final_state.page_id == "checkout_complete"
    assert [edge.semantic_action for edge in result.graph.edges] == [
        "login_submit",
        "order_place_confirm",
    ]
    assert output_path.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests\safesym_bridge\test_graph_explorer.py -v
```

Expected: FAIL because `graph_explorer.py` does not exist.

- [ ] **Step 3: Implement graph explorer core**

Create `src/ai_web_explorer/safesym_bridge/graph_explorer.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ai_web_explorer.safesym_bridge.effect_inferer import (
    infer_effects,
    preconditions_for,
)
from ai_web_explorer.safesym_bridge.models import (
    ObservedAction,
    ObservedTransition,
    StateSnapshot,
)
from ai_web_explorer.safesym_bridge.observed_graph import (
    WebObservedGraph,
    build_observed_graph,
)


@dataclass(frozen=True)
class ExplorationAction:
    raw_description: str
    semantic_id: str
    page_id: str
    execution_kind: str
    selector: str | None = None
    values: dict[str, str] = field(default_factory=dict)
    position: str = ""


class ExplorationAdapter(Protocol):
    start_url: str
    app_name: str
    start_node: str

    async def observe_state(self, page) -> StateSnapshot:
        ...

    async def list_actions(
        self,
        page,
        state: StateSnapshot,
    ) -> list[ExplorationAction]:
        ...

    async def execute_action(self, page, action: ExplorationAction) -> None:
        ...

    def is_goal_state(self, state: StateSnapshot) -> bool:
        ...


@dataclass(frozen=True)
class ExplorationRunResult:
    graph: WebObservedGraph
    transitions: list[ObservedTransition]
    final_state: StateSnapshot
    stop_reason: str
    failed_actions: list[str] = field(default_factory=list)


def choose_next_unexplored_action(
    current_state: StateSnapshot,
    actions: list[ExplorationAction],
    graph: WebObservedGraph | None,
) -> ExplorationAction | None:
    explored = set()
    if graph is not None:
        explored = {
            edge.semantic_action
            for edge in graph.edges
            if edge.source == current_state.page_id
        }
    for action in actions:
        if action.page_id == current_state.page_id and action.semantic_id not in explored:
            return action
    return None


class GraphExplorer:
    def __init__(self, adapter: ExplorationAdapter, *, max_steps: int = 20):
        self.adapter = adapter
        self.max_steps = max_steps

    async def run(self, page, *, output_path: Path | None = None) -> ExplorationRunResult:
        transitions: list[ObservedTransition] = []
        failed_actions: list[str] = []
        graph: WebObservedGraph | None = None
        current_state = await self.adapter.observe_state(page)
        stop_reason = "max_steps_reached"

        for _ in range(self.max_steps):
            graph = build_observed_graph(
                app=self.adapter.app_name,
                start_node=self.adapter.start_node,
                transitions=transitions,
            )
            if self.adapter.is_goal_state(current_state):
                stop_reason = "goal_reached"
                break

            actions = await self.adapter.list_actions(page, current_state)
            selected = choose_next_unexplored_action(current_state, actions, graph)
            if selected is None:
                stop_reason = "no_unexplored_actions"
                break

            before = current_state
            try:
                await self.adapter.execute_action(page, selected)
            except Exception:
                failed_actions.append(selected.raw_description)
                continue

            after = await self.adapter.observe_state(page)
            transitions.append(
                ObservedTransition(
                    source=before,
                    target=after,
                    action=ObservedAction(
                        raw_description=selected.raw_description,
                        semantic_id=selected.semantic_id,
                        playwright_calls=[],
                    ),
                    preconditions=preconditions_for(selected.semantic_id),
                    effects=infer_effects(before, after),
                )
            )
            current_state = after
            graph = build_observed_graph(
                app=self.adapter.app_name,
                start_node=self.adapter.start_node,
                transitions=transitions,
            )
            self._write_graph(graph, output_path)
        else:
            graph = build_observed_graph(
                app=self.adapter.app_name,
                start_node=self.adapter.start_node,
                transitions=transitions,
            )

        if graph is None:
            graph = build_observed_graph(
                app=self.adapter.app_name,
                start_node=self.adapter.start_node,
                transitions=transitions,
            )
        self._write_graph(graph, output_path)
        return ExplorationRunResult(
            graph=graph,
            transitions=transitions,
            final_state=current_state,
            stop_reason=stop_reason,
            failed_actions=failed_actions,
        )

    @staticmethod
    def _write_graph(graph: WebObservedGraph, output_path: Path | None) -> None:
        if output_path is None:
            return
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(graph.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
```

- [ ] **Step 4: Run graph explorer tests**

Run:

```powershell
python -m pytest tests\safesym_bridge\test_graph_explorer.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src\ai_web_explorer\safesym_bridge\graph_explorer.py tests\safesym_bridge\test_graph_explorer.py
git commit -m "feat: add graph exploration controller"
```

---

### Task 2: Add SauceDemo Adapter

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/saucedemo_adapter.py`
- Create: `tests/safesym_bridge/test_saucedemo_adapter.py`

**Interfaces:**
- Consumes:
  - `ExplorationAction`
  - `StateSnapshot`
  - `observe_saucedemo_state`
- Produces:
  - `SauceDemoAdapter`

- [ ] **Step 1: Write failing adapter tests**

Create `tests/safesym_bridge/test_saucedemo_adapter.py`:

```python
from __future__ import annotations

from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.saucedemo_adapter import SauceDemoAdapter


def snapshot(page_id: str, *, order_created: bool = False) -> StateSnapshot:
    return StateSnapshot(
        page_id=page_id,
        url=f"https://www.saucedemo.com/{page_id}",
        title=page_id,
        signature={
            "$.username_filled": False,
            "$.password_filled": False,
            "$.is_logged_in": page_id != "login",
            "$.cart_count": 0,
            "$.checkout_started": page_id.startswith("checkout"),
            "$.checkout_info_filled": False,
            "$.order_review_ready": page_id in {
                "checkout_overview",
                "checkout_complete",
            },
            "$.order_created": order_created,
        },
    )


async def collect_ids(page_id: str) -> list[str]:
    adapter = SauceDemoAdapter()
    actions = await adapter.list_actions(object(), snapshot(page_id))
    return [action.semantic_id for action in actions]


def test_adapter_metadata():
    adapter = SauceDemoAdapter()

    assert adapter.app_name == "saucedemo"
    assert adapter.start_node == "login"
    assert adapter.start_url == "https://www.saucedemo.com/"


async def test_login_actions():
    assert await collect_ids("login") == ["login_submit"]


async def test_inventory_actions():
    assert await collect_ids("inventory") == ["product_add_to_cart", "cart_open"]


async def test_cart_actions():
    assert await collect_ids("cart") == ["cart_checkout_start"]


async def test_checkout_info_actions():
    assert await collect_ids("checkout_info") == ["checkout_info_submit"]


async def test_checkout_overview_actions():
    assert await collect_ids("checkout_overview") == ["order_place_confirm"]


async def test_checkout_complete_has_no_actions():
    assert await collect_ids("checkout_complete") == []


def test_goal_detection_requires_complete_page_and_order_created():
    adapter = SauceDemoAdapter()

    assert adapter.is_goal_state(snapshot("checkout_complete", order_created=True))
    assert not adapter.is_goal_state(snapshot("checkout_complete", order_created=False))
    assert not adapter.is_goal_state(snapshot("checkout_overview", order_created=True))
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests\safesym_bridge\test_saucedemo_adapter.py -v
```

Expected: FAIL because `saucedemo_adapter.py` does not exist.

- [ ] **Step 3: Implement SauceDemoAdapter**

Create `src/ai_web_explorer/safesym_bridge/saucedemo_adapter.py`:

```python
from __future__ import annotations

from ai_web_explorer.safesym_bridge.graph_explorer import ExplorationAction
from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.state_observer import observe_saucedemo_state


class SauceDemoAdapter:
    app_name = "saucedemo"
    start_node = "login"
    start_url = "https://www.saucedemo.com/"

    async def observe_state(self, page) -> StateSnapshot:
        return await observe_saucedemo_state(page)

    async def list_actions(
        self,
        page,
        state: StateSnapshot,
    ) -> list[ExplorationAction]:
        actions_by_page = {
            "login": [
                ExplorationAction(
                    raw_description="Click the Login button",
                    semantic_id="login_submit",
                    page_id="login",
                    execution_kind="fill_then_click",
                    selector="#login-button",
                    values={
                        "#user-name": "standard_user",
                        "#password": "secret_sauce",
                    },
                    position="login form",
                )
            ],
            "inventory": [
                ExplorationAction(
                    raw_description="Click Add to cart",
                    semantic_id="product_add_to_cart",
                    page_id="inventory",
                    execution_kind="click",
                    selector='[data-test="add-to-cart-sauce-labs-backpack"]',
                    position="product list",
                ),
                ExplorationAction(
                    raw_description="Click the shopping cart link",
                    semantic_id="cart_open",
                    page_id="inventory",
                    execution_kind="click",
                    selector=".shopping_cart_link",
                    position="top right",
                ),
            ],
            "cart": [
                ExplorationAction(
                    raw_description="Click Checkout",
                    semantic_id="cart_checkout_start",
                    page_id="cart",
                    execution_kind="click",
                    selector="#checkout",
                    position="cart actions",
                )
            ],
            "checkout_info": [
                ExplorationAction(
                    raw_description="Click Continue on checkout information",
                    semantic_id="checkout_info_submit",
                    page_id="checkout_info",
                    execution_kind="fill_then_click",
                    selector="#continue",
                    values={
                        "#first-name": "Safe",
                        "#last-name": "Sym",
                        "#postal-code": "12345",
                    },
                    position="checkout form",
                )
            ],
            "checkout_overview": [
                ExplorationAction(
                    raw_description="Click Finish",
                    semantic_id="order_place_confirm",
                    page_id="checkout_overview",
                    execution_kind="click",
                    selector="#finish",
                    position="checkout summary",
                )
            ],
        }
        return actions_by_page.get(state.page_id, [])

    async def execute_action(self, page, action: ExplorationAction) -> None:
        for selector, value in action.values.items():
            await page.fill(selector, value)
        if action.selector is None:
            raise ValueError(f"Action has no selector: {action.semantic_id}")
        await page.click(action.selector)

    def is_goal_state(self, state: StateSnapshot) -> bool:
        return state.page_id == "checkout_complete" and bool(
            state.signature.get("$.order_created")
        )
```

- [ ] **Step 4: Run adapter tests**

Run:

```powershell
python -m pytest tests\safesym_bridge\test_saucedemo_adapter.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src\ai_web_explorer\safesym_bridge\saucedemo_adapter.py tests\safesym_bridge\test_saucedemo_adapter.py
git commit -m "feat: add SauceDemo exploration adapter"
```

---

### Task 3: Preserve Adapter Actions as Graph Interactable Elements

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/observed_graph.py`
- Modify: `src/ai_web_explorer/safesym_bridge/graph_explorer.py`
- Modify: `tests/safesym_bridge/test_observed_graph.py`
- Modify: `tests/safesym_bridge/test_graph_explorer.py`

**Interfaces:**
- Consumes:
  - `ExplorationAction`
  - existing `build_observed_graph`
- Produces:
  - optional `interactable_elements_by_node` parameter on `build_observed_graph`

- [ ] **Step 1: Write failing graph interactable test**

Append to `tests/safesym_bridge/test_observed_graph.py`:

```python
from ai_web_explorer.safesym_bridge.observed_graph import InteractableElement


def test_build_observed_graph_can_attach_interactable_elements():
    graph = build_observed_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
        interactable_elements_by_node={
            "inventory": [
                InteractableElement(
                    description="Click Add to cart",
                    position="product list",
                    explored=True,
                    execution_hints={
                        "selector": "[data-test=\"add-to-cart-sauce-labs-backpack\"]"
                    },
                )
            ]
        },
    )

    inventory = next(node for node in graph.nodes if node.id == "inventory")
    assert inventory.interactable_elements[0].description == "Click Add to cart"
    assert inventory.interactable_elements[0].explored is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests\safesym_bridge\test_observed_graph.py::test_build_observed_graph_can_attach_interactable_elements -v
```

Expected: FAIL because `build_observed_graph` does not accept `interactable_elements_by_node`.

- [ ] **Step 3: Add optional interactables parameter**

Modify `build_observed_graph` signature in `observed_graph.py`:

```python
def build_observed_graph(
    *,
    app: str,
    start_node: str,
    transitions: list[ObservedTransition],
    interactable_elements_by_node: dict[str, list[InteractableElement]] | None = None,
) -> WebObservedGraph:
```

Before building `nodes`, add:

```python
    interactable_elements_by_node = interactable_elements_by_node or {}
```

In `WebObservedNode(...)`, replace:

```python
            interactable_elements=[],
```

with:

```python
            interactable_elements=interactable_elements_by_node.get(node_id, []),
```

- [ ] **Step 4: Track candidate actions inside GraphExplorer**

In `graph_explorer.py`, add imports:

```python
from ai_web_explorer.safesym_bridge.observed_graph import InteractableElement
```

Add helper:

```python
def _element_for_action(
    action: ExplorationAction,
    *,
    explored: bool,
) -> InteractableElement:
    hints = {}
    if action.selector:
        hints["selector"] = action.selector
    hints["execution_kind"] = action.execution_kind
    return InteractableElement(
        description=action.raw_description,
        position=action.position,
        explored=explored,
        execution_hints=hints,
    )
```

Inside `GraphExplorer.run`, maintain:

```python
        interactables: dict[str, dict[str, InteractableElement]] = {}
```

After `actions = await self.adapter.list_actions(...)`, add:

```python
            page_elements = interactables.setdefault(current_state.page_id, {})
            for candidate in actions:
                page_elements.setdefault(
                    candidate.semantic_id,
                    _element_for_action(candidate, explored=False),
                )
```

After successful execution and before rebuilding graph, mark selected explored:

```python
            interactables[before.page_id][selected.semantic_id] = _element_for_action(
                selected,
                explored=True,
            )
```

Whenever calling `build_observed_graph`, pass:

```python
interactable_elements_by_node={
    node_id: list(elements.values())
    for node_id, elements in interactables.items()
}
```

- [ ] **Step 5: Add explorer test for interactables**

Append to `tests/safesym_bridge/test_graph_explorer.py`:

```python
@pytest.mark.anyio
async def test_graph_explorer_marks_successful_action_interactable_explored():
    adapter = FakeAdapter()
    explorer = GraphExplorer(adapter, max_steps=1)

    result = await explorer.run(object())

    login = next(node for node in result.graph.nodes if node.id == "login")
    assert login.interactable_elements[0].description == "Run login_submit"
    assert login.interactable_elements[0].explored is True
```

- [ ] **Step 6: Run targeted tests**

Run:

```powershell
python -m pytest tests\safesym_bridge\test_observed_graph.py tests\safesym_bridge\test_graph_explorer.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src\ai_web_explorer\safesym_bridge\observed_graph.py src\ai_web_explorer\safesym_bridge\graph_explorer.py tests\safesym_bridge\test_observed_graph.py tests\safesym_bridge\test_graph_explorer.py
git commit -m "feat: record exploration actions as graph interactables"
```

---

### Task 4: Add Browser Runner Helpers and CLI Commands

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Modify: `tests/safesym_bridge/test_browser_runner.py`
- Modify: `tests/safesym_bridge/test_cli.py`

**Interfaces:**
- Consumes:
  - `GraphExplorer`
  - `SauceDemoAdapter`
  - `write_pddl_artifacts`
- Produces:
  - `run_saucedemo_explored_graph(output_path: Path, *, headless: bool = True) -> Path`
  - `run_saucedemo_explored_pddl(output_dir: Path, *, headless: bool = True) -> Path`
  - CLI subcommands `explore-graph` and `explore-pddl`

- [ ] **Step 1: Add failing browser runner tests**

Append to `tests/safesym_bridge/test_browser_runner.py`:

```python
from ai_web_explorer.safesym_bridge.browser_runner import (
    run_saucedemo_explored_graph,
    run_saucedemo_explored_pddl,
)


def test_run_saucedemo_explored_graph_is_async_callable():
    assert callable(run_saucedemo_explored_graph)


def test_run_saucedemo_explored_pddl_is_async_callable():
    assert callable(run_saucedemo_explored_pddl)
```

- [ ] **Step 2: Add failing CLI tests**

Append to `tests/safesym_bridge/test_cli.py`:

```python
def test_main_explore_graph_subcommand_runs_explorer(tmp_path, monkeypatch):
    output_path = tmp_path / "explored_graph.json"
    calls = []

    async def fake_run_saucedemo_explored_graph(path, *, headless=True):
        calls.append((path, headless))
        path.write_text('{"meta": {"app": "saucedemo"}}', encoding="utf-8")
        return path

    monkeypatch.setattr(
        cli,
        "run_saucedemo_explored_graph",
        fake_run_saucedemo_explored_graph,
    )

    exit_code = main(["explore-graph", "--output", str(output_path), "--headed"])

    assert exit_code == 0
    assert calls == [(output_path, False)]


def test_main_explore_pddl_subcommand_runs_explorer(tmp_path, monkeypatch):
    output_dir = tmp_path / "explored_pddl"
    calls = []

    async def fake_run_saucedemo_explored_pddl(path, *, headless=True):
        calls.append((path, headless))
        path.mkdir(parents=True, exist_ok=True)
        (path / "domain.pddl").write_text("(define (domain saucedemo))", encoding="utf-8")
        (path / "problem.pddl").write_text("(define (problem saucedemo-problem))", encoding="utf-8")
        return path

    monkeypatch.setattr(
        cli,
        "run_saucedemo_explored_pddl",
        fake_run_saucedemo_explored_pddl,
    )

    exit_code = main(["explore-pddl", "--output", str(output_dir)])

    assert exit_code == 0
    assert calls == [(output_dir, True)]
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```powershell
python -m pytest tests\safesym_bridge\test_browser_runner.py tests\safesym_bridge\test_cli.py -v
```

Expected: FAIL because new runner functions and CLI commands do not exist.

- [ ] **Step 4: Implement browser runner helpers**

In `browser_runner.py`, add imports:

```python
from ai_web_explorer.safesym_bridge.graph_explorer import GraphExplorer
from ai_web_explorer.safesym_bridge.pddl_compiler import write_pddl_artifacts
from ai_web_explorer.safesym_bridge.saucedemo_adapter import SauceDemoAdapter
```

Add functions:

```python
async def run_saucedemo_explored_graph(
    output_path: Path,
    *,
    headless: bool = True,
) -> Path:
    from playwright.async_api import async_playwright

    adapter = SauceDemoAdapter()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        page = await browser.new_page()
        try:
            await page.goto(adapter.start_url)
            explorer = GraphExplorer(adapter)
            await explorer.run(page, output_path=output_path)
            return output_path
        finally:
            await browser.close()


async def run_saucedemo_explored_pddl(
    output_dir: Path,
    *,
    headless: bool = True,
) -> Path:
    from playwright.async_api import async_playwright

    adapter = SauceDemoAdapter()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        page = await browser.new_page()
        try:
            await page.goto(adapter.start_url)
            explorer = GraphExplorer(adapter)
            result = await explorer.run(page)
            write_pddl_artifacts(result.graph, output_dir)
            return output_dir
        finally:
            await browser.close()
```

- [ ] **Step 5: Implement CLI subcommands**

In `cli.py`, import:

```python
    run_saucedemo_explored_graph,
    run_saucedemo_explored_pddl,
```

Add parsers:

```python
    explore_graph_parser = subparsers.add_parser(
        "explore-graph",
        help="Run graph-guided SauceDemo browser exploration and write graph JSON.",
    )
    explore_graph_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/saucedemo_explored_graph.json"),
        help="Path to write the explored graph JSON.",
    )
    explore_graph_parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window while running exploration.",
    )

    explore_pddl_parser = subparsers.add_parser(
        "explore-pddl",
        help="Run graph-guided SauceDemo exploration and write PDDL artifacts.",
    )
    explore_pddl_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/safesym_e2e/explored_graph_pddl"),
        help="Directory to write domain.pddl and problem.pddl.",
    )
    explore_pddl_parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window while running exploration.",
    )
```

Add branches before `elif args.mode == "graph"`:

```python
        elif args.mode == "explore-graph":
            output_path = asyncio.run(
                run_saucedemo_explored_graph(
                    args.output,
                    headless=not args.headed,
                )
            )
        elif args.mode == "explore-pddl":
            output_path = asyncio.run(
                run_saucedemo_explored_pddl(
                    args.output,
                    headless=not args.headed,
                )
            )
```

- [ ] **Step 6: Run targeted tests**

Run:

```powershell
python -m pytest tests\safesym_bridge\test_browser_runner.py tests\safesym_bridge\test_cli.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src\ai_web_explorer\safesym_bridge\browser_runner.py src\ai_web_explorer\safesym_bridge\cli.py tests\safesym_bridge\test_browser_runner.py tests\safesym_bridge\test_cli.py
git commit -m "feat: add graph-guided exploration CLI"
```

---

### Task 5: Add Optional Browser Smoke Coverage and Full Verification

**Files:**
- Modify: `tests/safesym_bridge/test_browser_runner.py`
- Modify: `tests/safesym_bridge/test_cli.py` if CLI output assertions need strengthening

**Interfaces:**
- Consumes:
  - `run_saucedemo_explored_graph`
  - `run_saucedemo_explored_pddl`

- [ ] **Step 1: Add optional real-browser explored graph smoke test**

Append to `tests/safesym_bridge/test_browser_runner.py`:

```python
@pytest.mark.skipif(
    os.getenv("RUN_SAUCEDEMO_BROWSER_TEST") != "1",
    reason="Set RUN_SAUCEDEMO_BROWSER_TEST=1 to run the real browser smoke test.",
)
@pytest.mark.anyio
async def test_run_saucedemo_explored_graph_smoke(tmp_path):
    output_path = tmp_path / "saucedemo_explored_graph.json"

    result_path = await run_saucedemo_explored_graph(output_path)

    assert result_path == output_path
    data = json.loads(output_path.read_text(encoding="utf-8"))
    node_ids = {node["id"] for node in data["nodes"]}
    action_ids = {edge["semantic_action"] for edge in data["edges"]}
    assert {
        "login",
        "inventory",
        "cart",
        "checkout_info",
        "checkout_overview",
        "checkout_complete",
    }.issubset(node_ids)
    assert {
        "login_submit",
        "product_add_to_cart",
        "cart_open",
        "cart_checkout_start",
        "checkout_info_submit",
        "order_place_confirm",
    }.issubset(action_ids)
```

- [ ] **Step 2: Add optional real-browser explored PDDL smoke test**

Append to `tests/safesym_bridge/test_browser_runner.py`:

```python
@pytest.mark.skipif(
    os.getenv("RUN_SAUCEDEMO_BROWSER_TEST") != "1",
    reason="Set RUN_SAUCEDEMO_BROWSER_TEST=1 to run the real browser smoke test.",
)
@pytest.mark.anyio
async def test_run_saucedemo_explored_pddl_smoke(tmp_path):
    output_dir = tmp_path / "explored_graph_pddl"

    result_dir = await run_saucedemo_explored_pddl(output_dir)

    assert result_dir == output_dir
    domain = (output_dir / "domain.pddl").read_text(encoding="utf-8")
    problem = (output_dir / "problem.pddl").read_text(encoding="utf-8")
    assert "(:action login_fill_credentials" in domain
    assert "(:action checkout_info_fill" in domain
    assert "(:action order_place_confirm" in domain
    assert "(state_order_created)" in problem
```

- [ ] **Step 3: Run default tests**

Run:

```powershell
python -m pytest tests\safesym_bridge -v
```

Expected: PASS with browser smoke tests skipped unless `RUN_SAUCEDEMO_BROWSER_TEST=1`.

- [ ] **Step 4: Optionally run real browser smoke tests**

Run only when the environment has browser/network access:

```powershell
$env:RUN_SAUCEDEMO_BROWSER_TEST="1"
python -m pytest tests\safesym_bridge\test_browser_runner.py -v
```

Expected: PASS and explorer reaches `checkout_complete`.

- [ ] **Step 5: Commit**

```powershell
git add tests\safesym_bridge\test_browser_runner.py tests\safesym_bridge\test_cli.py
git commit -m "test: cover graph-guided SauceDemo exploration"
```

---

## Final Verification

- [ ] Run default SafeSym bridge tests:

```powershell
python -m pytest tests\safesym_bridge -v
```

Expected: all default tests pass, optional browser smoke tests skipped unless enabled.

- [ ] Run CLI help smoke:

```powershell
python -m ai_web_explorer.safesym_bridge.cli --help
```

Expected: help includes `explore-graph` and `explore-pddl`.

- [ ] If browser/network access is available, run:

```powershell
$env:RUN_SAUCEDEMO_BROWSER_TEST="1"
python -m pytest tests\safesym_bridge\test_browser_runner.py -v
```

Expected: browser smoke tests pass.

- [ ] Check git status:

```powershell
git status --short --branch
```

Expected: clean working tree after commits.

## Self-Review Notes

- Spec coverage: Tasks cover generic explorer, SauceDemo adapter, graph interactables, CLI workflows, default tests, and optional browser smoke tests.
- Scope control: The plan excludes arbitrary website understanding, LLM/VLM page description, generic DOM extraction, complex search/backtracking, and main `ExploreLoop` integration.
- Type consistency: `ExplorationAction`, `ExplorationAdapter`, `ExplorationRunResult`, `GraphExplorer`, and `SauceDemoAdapter` are introduced before later tasks consume them.
