# Stagehand-Backed WebKobeGraph Exploration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Stagehand-backed single-step exploration path that uses Stagehand for browser action discovery/execution while this project records before/after observations, WebKobeGraph edges, and PDDL artifacts.

**Architecture:** Introduce a small Stagehand provider boundary in `grounded_web`, wrap it behind an `AutomationBackend` so the existing `WebKobeExplorer` can record graph edges, and expose a SauceDemo smoke command through `safesym_bridge`. Default tests use fake Stagehand providers; the real Stagehand SDK is loaded only by an opt-in provider factory.

**Tech Stack:** Python 3.9+, Playwright, existing `grounded_web` / `safesym_bridge` modules, optional `stagehand` Python SDK loaded lazily for real runs.

## Global Constraints

- Do not reintroduce the removed legacy `explore` runtime.
- Do not build a competing general-purpose web agent.
- Do not use Stagehand `agent()` as one opaque full-task runner.
- Keep the graph loop one transition at a time: before observation, one Stagehand observe/act step, after observation, graph edge.
- Stagehand action output is execution evidence, not the source of action effects.
- PDDL action effects must come from observed before/after deltas or verified node/navigation changes.
- Default automated tests must use fake Stagehand providers and must not require network access, browser credentials, or paid model calls.

---

## File Structure

- Create `src/ai_web_explorer/grounded_web/stagehand_actions.py`
  - Stagehand action/result dataclasses, provider protocol, conversion helpers.
- Modify `src/ai_web_explorer/grounded_web/capability_graph.py`
  - Add optional execution-trace metadata for Stagehand evidence.
- Modify `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
  - Preserve execution metadata when loading graph JSON.
- Create `src/ai_web_explorer/grounded_web/stagehand_backend.py`
  - `AutomationBackend` wrapper that delegates state observation to an existing backend and delegates one-step action discovery/execution to a Stagehand provider.
- Modify `src/ai_web_explorer/grounded_web/explorer.py`
  - Copy optional backend execution metadata into `WebKobeEdge.execution_trace`.
- Create `src/ai_web_explorer/grounded_web/stagehand_sdk_provider.py`
  - Opt-in real Stagehand SDK provider factory with lazy import and explicit missing-configuration errors.
- Modify `src/ai_web_explorer/safesym_bridge/browser_runner.py`
  - Add Stagehand-backed SauceDemo runner with provider injection for tests.
- Modify `src/ai_web_explorer/safesym_bridge/cli.py`
  - Add `web-kobe-saucedemo-stagehand-smoke`.
- Test files:
  - Create `tests/safesym_bridge/test_stagehand_actions.py`
  - Create `tests/safesym_bridge/test_stagehand_backend.py`
  - Modify `tests/safesym_bridge/test_web_kobe_explorer.py`
  - Modify `tests/safesym_bridge/test_web_kobe_pddl_projector.py`
  - Modify `tests/safesym_bridge/test_browser_runner.py`
  - Modify `tests/safesym_bridge/test_cli.py`

---

### Task 1: Stagehand Action Contracts

**Files:**
- Create: `src/ai_web_explorer/grounded_web/stagehand_actions.py`
- Test: `tests/safesym_bridge/test_stagehand_actions.py`

**Interfaces:**
- Produces: `StagehandObservedAction`, `StagehandActResult`, `StagehandStepTrace`, `StagehandProvider`, `stagehand_action_to_browser_action(action, *, index) -> BrowserAction`, `stagehand_trace_metadata(trace) -> dict[str, Any]`.
- Consumes: `BrowserAction` from `ai_web_explorer.grounded_web.graph`.

- [ ] **Step 1: Write the failing tests**

Create `tests/safesym_bridge/test_stagehand_actions.py`:

```python
from ai_web_explorer.grounded_web.stagehand_actions import (
    StagehandActResult,
    StagehandObservedAction,
    StagehandStepTrace,
    stagehand_action_to_browser_action,
    stagehand_trace_metadata,
)


def test_stagehand_action_to_browser_action_uses_method_selector_and_description():
    action = StagehandObservedAction(
        description="Click the Login button",
        method="click",
        selector="#login-button",
        arguments=[],
        raw={"backendNodeId": 123},
    )

    browser_action = stagehand_action_to_browser_action(action, index=2)

    assert browser_action.action_kind == "click"
    assert browser_action.locator == "#login-button"
    assert browser_action.semantic_id == "stagehand_002_click_login_button"
    assert browser_action.description == "Click the Login button"
    assert browser_action.input_values == {}


def test_stagehand_action_to_browser_action_maps_fill_argument_to_selector_value():
    action = StagehandObservedAction(
        description="Fill username",
        method="fill",
        selector="#user-name",
        arguments=["standard_user"],
        raw={},
    )

    browser_action = stagehand_action_to_browser_action(action, index=0)

    assert browser_action.action_kind == "fill"
    assert browser_action.input_values == {"#user-name": "standard_user"}


def test_stagehand_trace_metadata_preserves_raw_action_and_result():
    trace = StagehandStepTrace(
        instruction="continue toward checkout overview",
        observed_action=StagehandObservedAction(
            description="Click checkout",
            method="click",
            selector="#checkout",
            arguments=[],
            raw={"backendNodeId": 99},
        ),
        act_result=StagehandActResult(
            success=True,
            message="Clicked checkout",
            action_description="Clicked button with text Checkout",
            raw={"actionId": "act_123"},
        ),
    )

    metadata = stagehand_trace_metadata(trace)

    assert metadata["action_source"] == "stagehand"
    assert metadata["stagehand_instruction"] == "continue toward checkout overview"
    assert metadata["stagehand_method"] == "click"
    assert metadata["stagehand_selector"] == "#checkout"
    assert metadata["stagehand_arguments"] == []
    assert metadata["stagehand_act_result"]["success"] is True
    assert metadata["stagehand_observed_action"]["backendNodeId"] == 99
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/safesym_bridge/test_stagehand_actions.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'ai_web_explorer.grounded_web.stagehand_actions'`.

- [ ] **Step 3: Implement the contracts**

Create `src/ai_web_explorer/grounded_web/stagehand_actions.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.models import StateSnapshot


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return cleaned or "action"


@dataclass(frozen=True)
class StagehandObservedAction:
    description: str
    method: str
    selector: str | None = None
    arguments: list[Any] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StagehandActResult:
    success: bool
    message: str | None = None
    action_description: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StagehandStepTrace:
    instruction: str
    observed_action: StagehandObservedAction | None
    act_result: StagehandActResult | None
    error: str | None = None


class StagehandProvider(Protocol):
    async def observe_next_action(
        self,
        *,
        instruction: str,
        state: StateSnapshot,
    ) -> list[StagehandObservedAction]: ...

    async def act(
        self,
        action: StagehandObservedAction,
    ) -> StagehandActResult: ...


def stagehand_action_to_browser_action(
    action: StagehandObservedAction,
    *,
    index: int,
) -> BrowserAction:
    method = action.method.strip().lower() or "act"
    selector = action.selector
    input_values: dict[str, str] = {}
    if method in {"fill", "type"} and selector and action.arguments:
        input_values[selector] = str(action.arguments[0])
    semantic_id = f"stagehand_{index:03d}_{method}_{_slug(action.description)}"
    return BrowserAction(
        action_kind=method,
        locator=selector,
        semantic_id=semantic_id,
        input_values=input_values,
        description=action.description,
    )


def stagehand_trace_metadata(trace: StagehandStepTrace) -> dict[str, Any]:
    observed_action = trace.observed_action
    act_result = trace.act_result
    metadata: dict[str, Any] = {
        "action_source": "stagehand",
        "stagehand_instruction": trace.instruction,
        "stagehand_error": trace.error,
    }
    if observed_action is not None:
        metadata.update(
            {
                "stagehand_description": observed_action.description,
                "stagehand_method": observed_action.method,
                "stagehand_selector": observed_action.selector,
                "stagehand_arguments": list(observed_action.arguments),
                "stagehand_observed_action": dict(observed_action.raw),
            }
        )
    if act_result is not None:
        metadata["stagehand_act_result"] = {
            "success": act_result.success,
            "message": act_result.message,
            "action_description": act_result.action_description,
            **dict(act_result.raw),
        }
    return metadata
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest tests/safesym_bridge/test_stagehand_actions.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/grounded_web/stagehand_actions.py tests/safesym_bridge/test_stagehand_actions.py
git commit -m "feat: add stagehand action contracts"
```

---

### Task 2: Execution Trace Metadata

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/capability_graph.py`
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
- Modify: `tests/safesym_bridge/test_web_kobe_pddl_projector.py`

**Interfaces:**
- Consumes: `ExecutionTrace(..., metadata=dict[str, Any])`.
- Produces: `ExecutionTrace.to_dict()["metadata"]` and loader preservation through `_execution_trace_from_dict`.

- [ ] **Step 1: Write the failing loader/preservation test**

Append to `tests/safesym_bridge/test_web_kobe_pddl_projector.py`:

```python
def test_load_web_kobe_graph_json_preserves_execution_trace_metadata(tmp_path):
    graph = WebKobeGraph(
        app="example",
        start_node_id="login",
        total_steps_completed=1,
        nodes=[
            _node("login", "login", {"is_logged_in": False}),
            _node("inventory", "inventory", {"is_logged_in": True}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="login",
                target_node_id="inventory",
                instruction="log in",
                action=BrowserAction("click", "#login-button", "stagehand_login"),
                capability=None,
                target_observation="inventory page",
                observed_delta=[
                    ObservedDelta(
                        "is_logged_in",
                        False,
                        True,
                        "state_indicator_change",
                        evidence=[Evidence(source="unit_test")],
                    )
                ],
                schema_delta={"is_logged_in": {"before": False, "after": True}},
                execution_trace=ExecutionTrace(
                    "click",
                    "#login-button",
                    "stagehand_login",
                    {},
                    "login",
                    "inventory",
                    True,
                    metadata={"action_source": "stagehand"},
                ),
            )
        ],
    )
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(graph.to_dict()), encoding="utf-8")

    loaded = load_web_kobe_graph_json(path)

    assert loaded.edges[0].execution_trace.metadata == {
        "action_source": "stagehand"
    }
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py::test_load_web_kobe_graph_json_preserves_execution_trace_metadata -v
```

Expected: FAIL with `TypeError: ExecutionTrace.__init__() got an unexpected keyword argument 'metadata'`.

- [ ] **Step 3: Add metadata to `ExecutionTrace`**

Modify `src/ai_web_explorer/grounded_web/capability_graph.py`:

```python
@dataclass(frozen=True)
class ExecutionTrace:
    concrete_action_kind: str
    concrete_locator: str | None
    concrete_target_sample: str | None
    input_values_used: dict[str, str]
    before_observation_id: str
    after_observation_id: str
    success: bool
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "concrete_action_kind": self.concrete_action_kind,
            "concrete_locator": self.concrete_locator,
            "concrete_target_sample": self.concrete_target_sample,
            "input_values_used": dict(self.input_values_used),
            "before_observation_id": self.before_observation_id,
            "after_observation_id": self.after_observation_id,
            "success": self.success,
            "error": self.error,
            "metadata": dict(self.metadata),
        }
```

- [ ] **Step 4: Preserve metadata in the JSON loader**

Modify `_execution_trace_from_dict` in `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`:

```python
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
        metadata=dict(data.get("metadata", {})),
    )
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py::test_load_web_kobe_graph_json_preserves_execution_trace_metadata tests/safesym_bridge/test_web_kobe_pddl_projector.py::test_compile_web_kobe_graph_to_pddl_excludes_non_projectable_edges -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_web_explorer/grounded_web/capability_graph.py src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py tests/safesym_bridge/test_web_kobe_pddl_projector.py
git commit -m "feat: preserve execution trace metadata"
```

---

### Task 3: Stagehand Automation Backend Wrapper

**Files:**
- Create: `src/ai_web_explorer/grounded_web/stagehand_backend.py`
- Test: `tests/safesym_bridge/test_stagehand_backend.py`

**Interfaces:**
- Consumes: `AutomationBackend`, `StagehandProvider`.
- Produces: `StagehandAutomationBackend(base_backend, provider, goal)` implementing `observe_state`, `list_interactables`, and `execute`.
- Produces attributes: `last_execution_error: str | None`, `last_execution_metadata: dict[str, Any]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/safesym_bridge/test_stagehand_backend.py`:

```python
import pytest

from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.stagehand_actions import (
    StagehandActResult,
    StagehandObservedAction,
)
from ai_web_explorer.grounded_web.stagehand_backend import (
    StagehandAutomationBackend,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeBaseBackend:
    app_name = "saucedemo"

    async def observe_state(self):
        return StateSnapshot(
            page_id="login",
            url="https://www.saucedemo.com/",
            title="Swag Labs",
            signature={"is_logged_in": False},
        )

    async def list_interactables(self, state):
        return []

    async def execute(self, action):
        raise AssertionError("Stagehand wrapper must execute through provider")


class FakeStagehandProvider:
    def __init__(self):
        self.observed = []
        self.acted = []

    async def observe_next_action(self, *, instruction, state):
        self.observed.append((instruction, state.page_id))
        return [
            StagehandObservedAction(
                description="Click the Login button",
                method="click",
                selector="#login-button",
                arguments=[],
                raw={"backendNodeId": 123},
            )
        ]

    async def act(self, action):
        self.acted.append(action)
        return StagehandActResult(
            success=True,
            message="Clicked login",
            action_description="Clicked button with text Login",
            raw={"actionId": "act_login"},
        )


@pytest.mark.anyio
async def test_stagehand_backend_exposes_one_observed_action_as_interactable():
    provider = FakeStagehandProvider()
    backend = StagehandAutomationBackend(
        base_backend=FakeBaseBackend(),
        provider=provider,
        goal="Log in and reach checkout overview.",
    )
    state = await backend.observe_state()

    actions = await backend.list_interactables(state)

    assert provider.observed == [
        ("Log in and reach checkout overview.", "login")
    ]
    assert actions[0]["semantic_id"] == "stagehand_000_click_login_button"
    assert actions[0]["description"] == "Click the Login button"
    assert actions[0]["locator"] == "#login-button"
    assert actions[0]["action_kind"] == "click"
    assert actions[0]["metadata"]["action_source"] == "stagehand"


@pytest.mark.anyio
async def test_stagehand_backend_execute_calls_provider_and_records_metadata():
    provider = FakeStagehandProvider()
    backend = StagehandAutomationBackend(
        base_backend=FakeBaseBackend(),
        provider=provider,
        goal="Log in.",
    )
    state = await backend.observe_state()
    action_dict = (await backend.list_interactables(state))[0]

    success = await backend.execute(action_dict)

    assert success is True
    assert provider.acted[0].description == "Click the Login button"
    assert backend.last_execution_error is None
    assert backend.last_execution_metadata["action_source"] == "stagehand"
    assert backend.last_execution_metadata["stagehand_selector"] == "#login-button"
    assert backend.last_execution_metadata["stagehand_act_result"]["success"] is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/safesym_bridge/test_stagehand_backend.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'ai_web_explorer.grounded_web.stagehand_backend'`.

- [ ] **Step 3: Implement `StagehandAutomationBackend`**

Create `src/ai_web_explorer/grounded_web/stagehand_backend.py`:

```python
from __future__ import annotations

from typing import Any

from ai_web_explorer.grounded_web.automation_backend import AutomationBackend
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.stagehand_actions import (
    StagehandObservedAction,
    StagehandProvider,
    StagehandStepTrace,
    stagehand_action_to_browser_action,
    stagehand_trace_metadata,
)


class StagehandAutomationBackend:
    app_name: str

    def __init__(
        self,
        *,
        base_backend: AutomationBackend,
        provider: StagehandProvider,
        goal: str,
    ) -> None:
        self.base_backend = base_backend
        self.provider = provider
        self.goal = goal
        self.app_name = base_backend.app_name
        self.last_execution_error: str | None = None
        self.last_execution_metadata: dict[str, Any] = {}
        self._observed_actions_by_id: dict[str, StagehandObservedAction] = {}

    async def observe_state(self) -> StateSnapshot:
        state = await self.base_backend.observe_state()
        if hasattr(self.base_backend, "last_state_facts"):
            self.last_state_facts = getattr(self.base_backend, "last_state_facts")
        return state

    async def list_interactables(
        self,
        state: StateSnapshot,
    ) -> list[dict[str, Any]]:
        observed = await self.provider.observe_next_action(
            instruction=self.goal,
            state=state,
        )
        self._observed_actions_by_id = {}
        records: list[dict[str, Any]] = []
        for index, stagehand_action in enumerate(observed):
            action = stagehand_action_to_browser_action(
                stagehand_action,
                index=index,
            )
            self._observed_actions_by_id[action.semantic_id] = stagehand_action
            records.append(
                {
                    "semantic_id": action.semantic_id,
                    "description": action.description,
                    "locator": action.locator,
                    "action_kind": action.action_kind,
                    "input_values": dict(action.input_values),
                    "explored": False,
                    "metadata": {
                        "action_source": "stagehand",
                        "stagehand_method": stagehand_action.method,
                    },
                }
            )
        return records

    async def execute(self, action: BrowserAction | dict[str, Any]) -> bool:
        semantic_id = (
            action.semantic_id
            if isinstance(action, BrowserAction)
            else str(action.get("semantic_id", ""))
        )
        stagehand_action = self._observed_actions_by_id.get(semantic_id)
        if stagehand_action is None:
            self.last_execution_error = "stagehand_action_not_found"
            self.last_execution_metadata = {
                "action_source": "stagehand",
                "stagehand_error": self.last_execution_error,
            }
            return False
        try:
            result = await self.provider.act(stagehand_action)
        except Exception as error:
            self.last_execution_error = str(error)
            trace = StagehandStepTrace(
                instruction=self.goal,
                observed_action=stagehand_action,
                act_result=None,
                error=self.last_execution_error,
            )
            self.last_execution_metadata = stagehand_trace_metadata(trace)
            return False
        trace = StagehandStepTrace(
            instruction=self.goal,
            observed_action=stagehand_action,
            act_result=result,
        )
        self.last_execution_metadata = stagehand_trace_metadata(trace)
        self.last_execution_error = None if result.success else result.message
        return result.success
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest tests/safesym_bridge/test_stagehand_backend.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/grounded_web/stagehand_backend.py tests/safesym_bridge/test_stagehand_backend.py
git commit -m "feat: add stagehand automation backend"
```

---

### Task 4: Attach Stagehand Metadata to Graph Edges

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Modify: `tests/safesym_bridge/test_web_kobe_explorer.py`

**Interfaces:**
- Consumes: optional `adapter.last_execution_metadata`.
- Produces: `edge.execution_trace.metadata` containing Stagehand evidence.

- [ ] **Step 1: Add the failing explorer test**

Append to `tests/safesym_bridge/test_web_kobe_explorer.py`:

```python
class StagehandMetadataAdapter(FakeAdapter):
    def __init__(self):
        super().__init__()
        self.last_execution_metadata = {}

    async def execute(self, action: BrowserAction):
        self.executed.append(action)
        self.last_execution_metadata = {
            "action_source": "stagehand",
            "stagehand_selector": action.locator,
        }
        return True


@pytest.mark.anyio
async def test_explore_one_step_preserves_backend_execution_metadata():
    explorer = WebKobeExplorer(
        adapter=StagehandMetadataAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    graph = await explorer.explore_one_step()

    assert graph.edges[0].execution_trace.metadata == {
        "action_source": "stagehand",
        "stagehand_selector": "button.add",
    }
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest tests/safesym_bridge/test_web_kobe_explorer.py::test_explore_one_step_preserves_backend_execution_metadata -v
```

Expected: FAIL because `ExecutionTrace.metadata` is `{}`.

- [ ] **Step 3: Copy backend metadata into `ExecutionTrace`**

Modify the `ExecutionTrace(...)` construction in `src/ai_web_explorer/grounded_web/explorer.py`:

```python
            execution_trace=ExecutionTrace(
                concrete_action_kind=concrete_action.action_kind,
                concrete_locator=concrete_action.locator,
                concrete_target_sample=concrete_action.semantic_id,
                input_values_used=dict(concrete_action.input_values),
                before_observation_id=source_id,
                after_observation_id=target_id,
                success=result.execution_success,
                error=result.execution_error,
                metadata=dict(getattr(self.adapter, "last_execution_metadata", {}) or {}),
            ),
```

- [ ] **Step 4: Run focused explorer tests**

Run:

```bash
pytest tests/safesym_bridge/test_web_kobe_explorer.py::test_explore_one_step_preserves_backend_execution_metadata tests/safesym_bridge/test_web_kobe_explorer.py::test_explore_one_step_records_backend_execution_error -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/grounded_web/explorer.py tests/safesym_bridge/test_web_kobe_explorer.py
git commit -m "feat: record backend execution metadata on graph edges"
```

---

### Task 5: Stagehand SDK Provider Factory

**Files:**
- Create: `src/ai_web_explorer/grounded_web/stagehand_sdk_provider.py`
- Test: `tests/safesym_bridge/test_stagehand_sdk_provider.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `create_stagehand_provider_from_env(model_name: str | None = None) -> StagehandProvider`.
- Produces: `StagehandSdkProvider(session)` implementing the `StagehandProvider` protocol.

- [ ] **Step 1: Write tests for lazy dependency and response conversion**

Create `tests/safesym_bridge/test_stagehand_sdk_provider.py`:

```python
import sys
from types import SimpleNamespace

import pytest

from ai_web_explorer.grounded_web.stagehand_sdk_provider import (
    StagehandSdkProvider,
    create_stagehand_provider_from_env,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_create_stagehand_provider_from_env_reports_missing_sdk(monkeypatch):
    monkeypatch.setitem(sys.modules, "stagehand", None)

    with pytest.raises(ValueError, match="stagehand Python SDK is required"):
        create_stagehand_provider_from_env(model_name="openai/gpt-5-nano")


class FakeAction:
    def __init__(self, data):
        self.data = data

    def to_dict(self, exclude_none=True):
        return dict(self.data)


class FakeSession:
    def __init__(self):
        self.observed_instruction = None
        self.acted_input = None

    async def observe(self, instruction):
        self.observed_instruction = instruction
        return SimpleNamespace(
            data=SimpleNamespace(
                result=[
                    FakeAction(
                        {
                            "description": "Click Login",
                            "method": "click",
                            "selector": "#login-button",
                            "arguments": [],
                            "backendNodeId": 123,
                        }
                    )
                ]
            )
        )

    async def act(self, input):
        self.acted_input = input
        return SimpleNamespace(
            data=SimpleNamespace(
                result=SimpleNamespace(
                    success=True,
                    message="Clicked",
                    actionDescription="Clicked Login",
                ),
                actionId="act_1",
            )
        )


@pytest.mark.anyio
async def test_stagehand_sdk_provider_converts_observe_and_act_results():
    session = FakeSession()
    provider = StagehandSdkProvider(session=session)

    actions = await provider.observe_next_action(
        instruction="log in",
        state=SimpleNamespace(page_id="login"),
    )
    result = await provider.act(actions[0])

    assert session.observed_instruction == "log in"
    assert actions[0].description == "Click Login"
    assert actions[0].method == "click"
    assert actions[0].selector == "#login-button"
    assert actions[0].raw["backendNodeId"] == 123
    assert session.acted_input["selector"] == "#login-button"
    assert result.success is True
    assert result.raw["actionId"] == "act_1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/safesym_bridge/test_stagehand_sdk_provider.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'ai_web_explorer.grounded_web.stagehand_sdk_provider'`.

- [ ] **Step 3: Add optional Stagehand dependency**

Modify `pyproject.toml` dependencies:

```toml
dependencies = [
    "playwright>=1.42.0",
    "openai>=1.14.2",
    "python-dotenv>=1.0.0",
    "stagehand>=0.1.0",
]
```

If the resolver reports a different published version floor for the official v3 SDK, use the lowest resolved version and keep the lazy import behavior.

- [ ] **Step 4: Implement SDK provider**

Create `src/ai_web_explorer/grounded_web/stagehand_sdk_provider.py`:

```python
from __future__ import annotations

from typing import Any

from ai_web_explorer.grounded_web.stagehand_actions import (
    StagehandActResult,
    StagehandObservedAction,
)


def _to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        return dict(value.to_dict(exclude_none=True))
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(exclude_none=True))
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {"value": value}


def _result_items(response: Any) -> list[Any]:
    data = getattr(response, "data", None)
    result = getattr(data, "result", None)
    if result is None and isinstance(data, dict):
        result = data.get("result")
    if result is None:
        return []
    return list(result if isinstance(result, list) else [result])


class StagehandSdkProvider:
    def __init__(self, *, session: Any) -> None:
        self.session = session

    async def observe_next_action(self, *, instruction, state):
        response = await self.session.observe(instruction=instruction)
        actions = []
        for item in _result_items(response):
            data = _to_dict(item)
            actions.append(
                StagehandObservedAction(
                    description=str(data.get("description", "")),
                    method=str(data.get("method") or data.get("action") or "act"),
                    selector=data.get("selector"),
                    arguments=list(data.get("arguments") or []),
                    raw=data,
                )
            )
        return actions

    async def act(self, action: StagehandObservedAction) -> StagehandActResult:
        action_input = {
            "description": action.description,
            "method": action.method,
            "selector": action.selector,
            "arguments": list(action.arguments),
        }
        response = await self.session.act(input=action_input)
        raw_data = _to_dict(getattr(response, "data", response))
        result_data = _to_dict(raw_data.get("result"))
        return StagehandActResult(
            success=bool(result_data.get("success", raw_data.get("success", True))),
            message=result_data.get("message"),
            action_description=(
                result_data.get("actionDescription")
                or result_data.get("action_description")
            ),
            raw=raw_data,
        )


def create_stagehand_provider_from_env(
    *,
    model_name: str | None = None,
) -> StagehandSdkProvider:
    try:
        from stagehand import AsyncStagehand
    except Exception as error:
        raise ValueError(
            "stagehand Python SDK is required for real Stagehand-backed runs."
        ) from error

    client = AsyncStagehand()
    session_options = {}
    if model_name is not None:
        session_options["model_name"] = model_name
    session = client.sessions.create(**session_options)
    raise ValueError(
        "create_stagehand_provider_from_env must be awaited through "
        "create_async_stagehand_provider_from_env."
    )


async def create_async_stagehand_provider_from_env(
    *,
    model_name: str | None = None,
) -> StagehandSdkProvider:
    try:
        from stagehand import AsyncStagehand
    except Exception as error:
        raise ValueError(
            "stagehand Python SDK is required for real Stagehand-backed runs."
        ) from error

    client = AsyncStagehand()
    session_options = {}
    if model_name is not None:
        session_options["model_name"] = model_name
    session = await client.sessions.create(**session_options)
    return StagehandSdkProvider(session=session)
```

- [ ] **Step 5: Run tests**

Run:

```bash
pytest tests/safesym_bridge/test_stagehand_sdk_provider.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/ai_web_explorer/grounded_web/stagehand_sdk_provider.py tests/safesym_bridge/test_stagehand_sdk_provider.py
git commit -m "feat: add optional stagehand sdk provider"
```

---

### Task 6: SauceDemo Stagehand Runner and CLI

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Modify: `tests/safesym_bridge/test_browser_runner.py`
- Modify: `tests/safesym_bridge/test_cli.py`

**Interfaces:**
- Produces: `run_saucedemo_stagehand_step(output_path, *, stagehand_trace_path=None, headless=True, steps=8, provider=None, model=None) -> Path`.
- Produces CLI mode: `web-kobe-saucedemo-stagehand-smoke`.

- [ ] **Step 1: Add runner test with fake provider and fake controller**

Append to `tests/safesym_bridge/test_browser_runner.py`:

```python
@pytest.mark.anyio
async def test_run_saucedemo_stagehand_step_wires_stagehand_backend(
    tmp_path,
    monkeypatch,
):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "stagehand_graph.json"
    trace_path = tmp_path / "stagehand_trace.json"
    calls = []

    class FakePage:
        async def goto(self, url):
            calls.append(("goto", url))

    class FakeBrowser:
        async def new_page(self):
            calls.append(("new_page", None))
            return FakePage()

        async def close(self):
            calls.append(("close", None))

    class FakeChromium:
        async def launch(self, *, headless=True):
            calls.append(("launch", headless))
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakePlaywrightContext:
        async def __aenter__(self):
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    class FakeProvider:
        pass

    class FakeController:
        def __init__(self, explorer):
            calls.append(("controller", explorer.adapter.app_name))
            explorer.adapter.last_execution_metadata = {
                "action_source": "stagehand",
                "stagehand_selector": "#login-button",
            }

        async def run(self, *, max_steps=1):
            assert max_steps == 6
            return WebKobeExplorationResult(
                graph=WebKobeGraph(
                    app="saucedemo",
                    start_node_id="login",
                    total_steps_completed=max_steps,
                    meta={
                        "stagehand_traces": [
                            {
                                "action_source": "stagehand",
                                "stagehand_selector": "#login-button",
                            }
                        ]
                    },
                ),
                summary=WebKobeExplorationSummary(
                    requested_steps=max_steps,
                    steps_completed=max_steps,
                    stop_reason="max_steps",
                    node_count=0,
                    edge_count=0,
                    failed_edge_count=0,
                ),
            )

    monkeypatch.setattr(
        playwright_async_api,
        "async_playwright",
        lambda: FakePlaywrightContext(),
    )
    monkeypatch.setattr(
        browser_runner,
        "WebKobeExplorationController",
        FakeController,
        raising=False,
    )

    result_path = await browser_runner.run_saucedemo_stagehand_step(
        output_path,
        stagehand_trace_path=trace_path,
        provider=FakeProvider(),
        steps=6,
    )

    assert result_path == output_path
    assert calls == [
        ("launch", True),
        ("new_page", None),
        ("goto", "https://www.saucedemo.com/"),
        ("controller", "saucedemo"),
        ("close", None),
    ]
    assert json.loads(output_path.read_text(encoding="utf-8"))["meta"]["app"] == (
        "saucedemo"
    )
    assert json.loads(trace_path.read_text(encoding="utf-8")) == [
        {
            "action_source": "stagehand",
            "stagehand_selector": "#login-button",
        }
    ]
```

- [ ] **Step 2: Add CLI test**

Append to `tests/safesym_bridge/test_cli.py`:

```python
def test_main_web_kobe_saucedemo_stagehand_smoke_wires_runner(
    monkeypatch,
    tmp_path,
):
    output = tmp_path / "graph.json"
    trace = tmp_path / "trace.json"
    calls = []

    async def fake_run(output_path, **kwargs):
        calls.append((output_path, kwargs))
        output_path.write_text('{"meta": {"app": "saucedemo"}}', encoding="utf-8")
        return output_path

    monkeypatch.setattr(
        "ai_web_explorer.safesym_bridge.cli.run_saucedemo_stagehand_step",
        fake_run,
        raising=False,
    )

    assert (
        main(
            [
                "web-kobe-saucedemo-stagehand-smoke",
                "--output",
                str(output),
                "--stagehand-trace",
                str(trace),
                "--steps",
                "6",
                "--model",
                "openai/gpt-5-nano",
            ]
        )
        == 0
    )
    assert calls[0][0] == output
    assert calls[0][1]["stagehand_trace_path"] == trace
    assert calls[0][1]["steps"] == 6
    assert calls[0][1]["model"] == "openai/gpt-5-nano"
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
pytest tests/safesym_bridge/test_browser_runner.py::test_run_saucedemo_stagehand_step_wires_stagehand_backend tests/safesym_bridge/test_cli.py::test_main_web_kobe_saucedemo_stagehand_smoke_wires_runner -v
```

Expected: FAIL because the runner and CLI mode do not exist.

- [ ] **Step 4: Implement runner**

Add imports in `src/ai_web_explorer/safesym_bridge/browser_runner.py`:

```python
from ai_web_explorer.grounded_web.stagehand_backend import (
    StagehandAutomationBackend,
)
from ai_web_explorer.grounded_web.stagehand_sdk_provider import (
    create_async_stagehand_provider_from_env,
)
```

Add function:

```python
async def run_saucedemo_stagehand_step(
    output_path: Path,
    *,
    stagehand_trace_path: Path | None = None,
    headless: bool = True,
    steps: int = 8,
    provider=None,
    model: str | None = None,
) -> Path:
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        page = await browser.new_page()
        try:
            await page.goto("https://www.saucedemo.com/")
            resolved_provider = provider
            if resolved_provider is None:
                resolved_provider = await create_async_stagehand_provider_from_env(
                    model_name=model,
                )
            base_adapter = WebKobePlaywrightAdapter(
                page,
                app_name="saucedemo",
            )
            adapter = StagehandAutomationBackend(
                base_backend=base_adapter,
                provider=resolved_provider,
                goal=(
                    "Log in to SauceDemo as standard_user, add one item to the "
                    "cart, open the cart, start checkout, fill checkout "
                    "information, and stop on checkout overview. Do not click "
                    "Finish."
                ),
            )
            explorer = WebKobeExplorer(
                adapter=adapter,
                semantic_assistor=DeterministicSemanticAssistor(app="saucedemo"),
                goal="Reach SauceDemo checkout overview without placing the order.",
            )
            controller = WebKobeExplorationController(explorer)
            result = await controller.run(max_steps=max(steps, 1))
            graph = result.graph
            write_web_kobe_graph(graph, output_path)
            if stagehand_trace_path is not None:
                traces = [
                    edge.execution_trace.metadata
                    for edge in graph.edges
                    if edge.execution_trace.metadata.get("action_source")
                    == "stagehand"
                ]
                stagehand_trace_path.parent.mkdir(parents=True, exist_ok=True)
                stagehand_trace_path.write_text(
                    json.dumps(traces, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            return output_path
        finally:
            await browser.close()
```

- [ ] **Step 5: Implement CLI mode**

Modify imports in `src/ai_web_explorer/safesym_bridge/cli.py`:

```python
from ai_web_explorer.safesym_bridge.browser_runner import (
    build_debug_web_kobe_graph,
    run_web_kobe_exploration,
    run_saucedemo_openai_selector_step,
    run_saucedemo_stagehand_step,
    write_web_kobe_graph,
)
```

Add parser after the existing SauceDemo LLM parser:

```python
    saucedemo_stagehand_parser = subparsers.add_parser(
        "web-kobe-saucedemo-stagehand-smoke",
        help=(
            "Run Stagehand-backed single-step SauceDemo Web-KOBE exploration "
            "and write graph plus Stagehand trace."
        ),
    )
    saucedemo_stagehand_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/saucedemo_stagehand_graph.json"),
        help="Path to write the Web-KOBE graph JSON.",
    )
    saucedemo_stagehand_parser.add_argument(
        "--stagehand-trace",
        type=Path,
        default=Path("outputs/saucedemo_stagehand_trace.json"),
        help="Path to write Stagehand execution trace JSON.",
    )
    saucedemo_stagehand_parser.add_argument(
        "--model",
        default=None,
        help="Optional Stagehand model override.",
    )
    saucedemo_stagehand_parser.add_argument(
        "--steps",
        type=int,
        default=8,
        help="Maximum number of Stagehand-backed graph steps.",
    )
    saucedemo_stagehand_parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window while running the smoke.",
    )
```

Add dispatch branch:

```python
        elif args.mode == "web-kobe-saucedemo-stagehand-smoke":
            output_path = asyncio.run(
                run_saucedemo_stagehand_step(
                    args.output,
                    stagehand_trace_path=args.stagehand_trace,
                    model=args.model,
                    steps=args.steps,
                    headless=not args.headed,
                )
            )
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
pytest tests/safesym_bridge/test_browser_runner.py::test_run_saucedemo_stagehand_step_wires_stagehand_backend tests/safesym_bridge/test_cli.py::test_main_web_kobe_saucedemo_stagehand_smoke_wires_runner -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/browser_runner.py src/ai_web_explorer/safesym_bridge/cli.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_cli.py
git commit -m "feat: add saucedemo stagehand graph smoke"
```

---

### Task 7: Documentation and Verification

**Files:**
- Modify: `docs/current-project-overview.md`
- Modify: `docs/current-project-overview.zh-CN.md`
- Modify: `docs/safesym-bridge.md`

**Interfaces:**
- Consumes: CLI mode `web-kobe-saucedemo-stagehand-smoke`.
- Produces: documented command and testing notes.

- [ ] **Step 1: Update docs with the command**

Add this text to `docs/current-project-overview.md` near the Stagehand next-direction section:

- `The planned Stagehand-backed smoke command is:`
- fenced `bash` command:
  `python -m ai_web_explorer.safesym_bridge.cli web-kobe-saucedemo-stagehand-smoke --output outputs/saucedemo_stagehand_graph.json --stagehand-trace outputs/saucedemo_stagehand_trace.json --steps 8`
- `It starts at the SauceDemo login page and should stop at checkout_overview. It must not click Finish.`

Add the equivalent Chinese note to `docs/current-project-overview.zh-CN.md`:

- Add a Chinese sentence saying that this is the planned Stagehand-backed smoke command.
- fenced `bash` command:
  `python -m ai_web_explorer.safesym_bridge.cli web-kobe-saucedemo-stagehand-smoke --output outputs/saucedemo_stagehand_graph.json --stagehand-trace outputs/saucedemo_stagehand_trace.json --steps 8`
- Add a Chinese sentence saying it starts at the SauceDemo login page, should stop at `checkout_overview`, and must not click `Finish`.

Add this command reference to `docs/safesym-bridge.md`:

- heading: `### Stagehand-Backed SauceDemo Graph Smoke`
- fenced `bash` command:
  `python -m ai_web_explorer.safesym_bridge.cli web-kobe-saucedemo-stagehand-smoke --output outputs/saucedemo_stagehand_graph.json --stagehand-trace outputs/saucedemo_stagehand_trace.json --steps 8`
- note: `This command is opt-in because real Stagehand runs require external credentials and browser/model access. Default tests use fake providers.`

- [ ] **Step 2: Run retained non-browser tests**

Run:

```bash
pytest tests/safesym_bridge/test_stagehand_actions.py tests/safesym_bridge/test_stagehand_backend.py tests/safesym_bridge/test_stagehand_sdk_provider.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_web_kobe_pddl_projector.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 3: Run full retained tests if time allows**

Run:

```bash
pytest -q
```

Expected: retained suite passes. Browser tests may require external execution permissions in restricted sandbox; record exact failures if Playwright spawn fails with EPERM.

- [ ] **Step 4: Commit**

```bash
git add docs/current-project-overview.md docs/current-project-overview.zh-CN.md docs/safesym-bridge.md
git commit -m "docs: document stagehand graph smoke"
```

---

## Self-Review Notes

- Spec coverage:
  - Single-step Stagehand observe/act is covered by Tasks 1, 3, 5, and 6.
  - Project-owned before/after observation and graph edges are covered by Tasks 3 and 4.
  - Stagehand evidence on graph edges is covered by Tasks 1, 2, and 4.
  - PDDL exclusion of failed/no-change edges remains covered by existing projector behavior and Task 2 metadata preservation.
  - Fake-provider default tests are covered by Tasks 1, 3, 5, and 6.
  - Real Stagehand SDK loading is opt-in and covered by Task 5.
- Placeholder scan:
  - The plan contains no unfinished markers or unspecified test commands.
- Type consistency:
  - `StagehandProvider.observe_next_action` returns `list[StagehandObservedAction]`.
  - `StagehandProvider.act` returns `StagehandActResult`.
  - `StagehandAutomationBackend` exposes `last_execution_metadata`, consumed by `WebKobeExplorer`.
  - `ExecutionTrace.metadata` is a `dict[str, Any]` preserved through graph JSON loading.
