# Generic Web Exploration for SafeSym Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project preference:** The user requested single-agent, token-conscious work by default. Use Inline Execution unless the user explicitly allows subagents.

**Goal:** Build the first vertical slice of a Web-KOBE-style generic web exploration graph that can record browser-grounded semantic states/actions and project a constrained model into PDDL for SafeSym.

**Architecture:** Add a new `WebKobeGraph` exploration graph beside the existing `WebObservedGraph`, not inside it. The first slice uses deterministic local extraction and a no-op semantic assistor seam, then records one-step graph transitions and projects verified boolean/page-type effects into simple PDDL.

**Tech Stack:** Python 3.11, dataclasses, existing `ai_web_explorer.safesym_bridge` models, Playwright-compatible adapter protocols, pytest, existing PDDL text conventions.

## Global Constraints

- Preserve the existing `WebObservedGraph -> PDDL -> SafeSym` SauceDemo path.
- Do not fork UI-KOBE or import Android-specific UI-KOBE runtime code.
- Use LLM/VLM as a future semantic proposal seam, not as a required dependency in this first implementation.
- Store concrete browser evidence and execution traces with graph nodes/edges.
- Model website capability: what page states can do, not all page content instances.
- Keep SafeSym responsible for safety policy and safety-check injection.
- Do not use subagents unless the user explicitly allows them.
- Use `python -m pytest`, because bare `pytest` may not be on PATH.

---

## File Structure

Create focused files in the existing bridge package first. This keeps imports, tests, and CLI patterns close to the current PDDL/SafeSym code while avoiding a large package reshuffle.

- Create `src/ai_web_explorer/safesym_bridge/web_kobe_graph.py`
  - Dataclasses and JSON serialization for `WebKobeGraph`, `WebKobeNode`, `WebKobeEdge`, `ActionTarget`, `ReferenceObservation`, `BrowserAction`, `PddlActionHint`, and status constants.
  - Reuse existing capability graph concepts where practical by importing `Capability`, `Evidence`, `ExecutionTrace`, `ObservedDelta`, `PageFrame`, and `StateIndicator`.

- Create `src/ai_web_explorer/safesym_bridge/web_kobe_graph_manager.py`
  - In-memory graph update logic: add/merge nodes, merge state schemas, merge interactables, add/update edges, mark explored interactables.
  - No Playwright calls here.

- Create `src/ai_web_explorer/safesym_bridge/web_semantic_assistor.py`
  - `SemanticAssistor` protocol and `DeterministicSemanticAssistor` implementation.
  - Converts `StateSnapshot` and local observation data into page descriptions, state schemas, targets, and capabilities without LLM/VLM calls.

- Create `src/ai_web_explorer/safesym_bridge/web_action_extractor.py`
  - Converts existing DOM `DomInteractableCandidate` values or adapter actions into `BrowserAction` candidates and representative `ActionTarget` values.

- Create `src/ai_web_explorer/safesym_bridge/web_kobe_explorer.py`
  - One-step exploration loop with a protocol-based adapter.
  - Records source node, selected action, target node, observed delta, and execution trace.

- Create `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
  - Projects a constrained `WebKobeGraph` into `domain.pddl` and `problem.pddl`.
  - Supports page-type predicates, boolean indicators, object-free actions, and simple add/delete effects.

- Modify `src/ai_web_explorer/safesym_bridge/browser_runner.py`
  - Add a writer for Web-KOBE graph JSON once the graph can be built.

- Modify `src/ai_web_explorer/safesym_bridge/cli.py`
  - Add debug commands for Web-KOBE graph generation and PDDL projection.

- Modify docs:
  - `docs/current-project-overview.md`
  - `docs/safesym-bridge.md`

- Add tests:
  - `tests/safesym_bridge/test_web_kobe_graph.py`
  - `tests/safesym_bridge/test_web_kobe_graph_manager.py`
  - `tests/safesym_bridge/test_web_semantic_assistor.py`
  - `tests/safesym_bridge/test_web_action_extractor.py`
  - `tests/safesym_bridge/test_web_kobe_explorer.py`
  - `tests/safesym_bridge/test_web_kobe_pddl_projector.py`
  - extend `tests/safesym_bridge/test_cli.py`

---

### Task 1: WebKobeGraph Data Model

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/web_kobe_graph.py`
- Test: `tests/safesym_bridge/test_web_kobe_graph.py`

**Interfaces:**
- Consumes:
  - `Capability`, `Evidence`, `ExecutionTrace`, `ObservedDelta`, `PageFrame`, `StateIndicator` from `ai_web_explorer.safesym_bridge.capability_graph`
- Produces:
  - `WEB_KOBE_SCHEMA_VERSION: str`
  - `ActionTarget`
  - `ReferenceObservation`
  - `BrowserAction`
  - `PddlActionHint`
  - `WebKobeNode`
  - `WebKobeEdge`
  - `WebKobeGraph`
  - All model classes expose `to_dict() -> dict[str, Any]`.

- [ ] **Step 1: Write failing model serialization tests**

Create `tests/safesym_bridge/test_web_kobe_graph.py`:

```python
from ai_web_explorer.safesym_bridge.capability_graph import (
    AvailabilityCondition,
    Capability,
    Evidence,
    ExecutionTrace,
    GroundingPattern,
    ObservedDelta,
    PageFrame,
    StateIndicator,
)
from ai_web_explorer.safesym_bridge.web_kobe_graph import (
    ActionTarget,
    BrowserAction,
    PddlActionHint,
    ReferenceObservation,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)


def test_web_kobe_graph_serializes_node_edge_and_evidence():
    evidence = [Evidence(source="dom", selector="#login-button", confidence=1.0)]
    page_frame = PageFrame(
        page_id="example:login",
        page_type="login",
        url="https://example.test/login",
        url_pattern="https://example.test/login",
        title="Example Login",
        heading="Sign in",
        evidence=evidence,
    )
    capability = Capability(
        capability_id="submit_login_form",
        semantic_action="login_submit",
        action_kind="composite",
        target_type="form",
        target_role="login_form",
        grounding=GroundingPattern(
            locator_strategy="form_fields",
            field_bindings={"username": "#user", "password": "#pass", "submit": "#login-button"},
        ),
        availability=AvailabilityCondition(required_page_type="login"),
        evidence=evidence,
    )
    node = WebKobeNode(
        node_id="n0_login",
        page_description="login page",
        page_frame=page_frame,
        state_schema={"logged_in": [False]},
        last_state_snapshot={"logged_in": False},
        state_indicators=[
            StateIndicator("logged_in", False, "planning_state", evidence=evidence)
        ],
        action_targets=[
            ActionTarget(
                target_type="form",
                occurrence="single",
                role="login_form",
                structural_pattern="#login-form",
                representative_locator="#login-button",
                supported_capabilities=["submit_login_form"],
                evidence=evidence,
            )
        ],
        interactable_elements=[
            {
                "semantic_id": "login_submit",
                "description": "Login",
                "locator": "#login-button",
                "explored": False,
            }
        ],
        capabilities=[capability],
        reference_observation=ReferenceObservation(
            url="https://example.test/login",
            title="Example Login",
            screenshot_path=None,
            dom_summary="form#login-form",
            accessibility_summary="button Login",
        ),
        visit_count=1,
        evidence=evidence,
    )
    edge = WebKobeEdge(
        source_node_id="n0_login",
        target_node_id="n1_home",
        instruction="submit login form",
        action=BrowserAction(
            action_kind="composite",
            locator="#login-button",
            semantic_id="submit_login_form",
            input_values={"username": "standard_user", "password": "secret_sauce"},
        ),
        capability=capability,
        target_observation="home page",
        observed_delta=[
            ObservedDelta(
                "logged_in",
                False,
                True,
                "state_indicator_change",
                evidence=evidence,
            )
        ],
        schema_delta={"logged_in": {"before": False, "after": True}},
        execution_trace=ExecutionTrace(
            concrete_action_kind="composite",
            concrete_locator="#login-button",
            concrete_target_sample="form",
            input_values_used={"username": "standard_user", "password": "secret_sauce"},
            before_observation_id="n0_login",
            after_observation_id="n1_home",
            success=True,
            error=None,
        ),
        pddl_hint=PddlActionHint(
            action_name="submit_login_form",
            preconditions=["at_login"],
            add_effects=["logged_in", "at_home"],
            del_effects=["at_login"],
        ),
        visit_count=1,
        status="verified",
        evidence=evidence,
    )
    graph = WebKobeGraph(
        app="example",
        start_node_id="n0_login",
        total_steps_completed=1,
        nodes=[node],
        edges=[edge],
        meta={"source": "unit_test"},
    )

    data = graph.to_dict()

    assert data["meta"]["schema_version"] == "web-kobe-graph-v1"
    assert data["meta"]["app"] == "example"
    assert data["nodes"][0]["action_targets"][0]["target_type"] == "form"
    assert data["nodes"][0]["capabilities"][0]["capability_id"] == "submit_login_form"
    assert data["edges"][0]["status"] == "verified"
    assert data["edges"][0]["pddl_hint"]["add_effects"] == ["logged_in", "at_home"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_graph.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'ai_web_explorer.safesym_bridge.web_kobe_graph'`.

- [ ] **Step 3: Implement graph dataclasses**

Create `src/ai_web_explorer/safesym_bridge/web_kobe_graph.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_web_explorer.safesym_bridge.capability_graph import (
    Capability,
    Evidence,
    ExecutionTrace,
    ObservedDelta,
    PageFrame,
    StateIndicator,
)

WEB_KOBE_SCHEMA_VERSION = "web-kobe-graph-v1"


def _list_to_dict(items: list[Any]) -> list[dict[str, Any]]:
    return [item.to_dict() if hasattr(item, "to_dict") else dict(item) for item in items]


@dataclass(frozen=True)
class ActionTarget:
    target_type: str
    occurrence: str
    role: str
    structural_pattern: str | None = None
    representative_locator: str | None = None
    supported_capabilities: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_type": self.target_type,
            "occurrence": self.occurrence,
            "role": self.role,
            "structural_pattern": self.structural_pattern,
            "representative_locator": self.representative_locator,
            "supported_capabilities": list(self.supported_capabilities),
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class ReferenceObservation:
    url: str
    title: str
    screenshot_path: str | None = None
    dom_summary: str | None = None
    accessibility_summary: str | None = None
    observation_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "screenshot_path": self.screenshot_path,
            "dom_summary": self.dom_summary,
            "accessibility_summary": self.accessibility_summary,
            "observation_hash": self.observation_hash,
        }


@dataclass(frozen=True)
class BrowserAction:
    action_kind: str
    locator: str | None
    semantic_id: str
    input_values: dict[str, str] = field(default_factory=dict)
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_kind": self.action_kind,
            "locator": self.locator,
            "semantic_id": self.semantic_id,
            "input_values": dict(self.input_values),
            "description": self.description,
        }


@dataclass(frozen=True)
class PddlActionHint:
    action_name: str
    preconditions: list[str] = field(default_factory=list)
    add_effects: list[str] = field(default_factory=list)
    del_effects: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_name": self.action_name,
            "preconditions": list(self.preconditions),
            "add_effects": list(self.add_effects),
            "del_effects": list(self.del_effects),
        }


@dataclass(frozen=True)
class WebKobeNode:
    node_id: str
    page_description: str
    page_frame: PageFrame
    state_schema: dict[str, list[Any]]
    last_state_snapshot: dict[str, Any]
    state_indicators: list[StateIndicator] = field(default_factory=list)
    action_targets: list[ActionTarget] = field(default_factory=list)
    interactable_elements: list[dict[str, Any]] = field(default_factory=list)
    capabilities: list[Capability] = field(default_factory=list)
    reference_observation: ReferenceObservation | None = None
    visit_count: int = 0
    status: str = "verified"
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "page_description": self.page_description,
            "page_frame": self.page_frame.to_dict(),
            "state_schema": {k: list(v) for k, v in self.state_schema.items()},
            "last_state_snapshot": dict(self.last_state_snapshot),
            "state_indicators": _list_to_dict(self.state_indicators),
            "action_targets": _list_to_dict(self.action_targets),
            "interactable_elements": [dict(item) for item in self.interactable_elements],
            "capabilities": _list_to_dict(self.capabilities),
            "reference_observation": (
                self.reference_observation.to_dict()
                if self.reference_observation is not None
                else None
            ),
            "visit_count": self.visit_count,
            "status": self.status,
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class WebKobeEdge:
    source_node_id: str
    target_node_id: str
    instruction: str
    action: BrowserAction
    capability: Capability | None
    target_observation: str
    observed_delta: list[ObservedDelta]
    schema_delta: dict[str, Any] | None
    execution_trace: ExecutionTrace
    pddl_hint: PddlActionHint | None = None
    visit_count: int = 1
    status: str = "verified"
    evidence: list[Evidence] = field(default_factory=list)

    @property
    def edge_id(self) -> str:
        return f"{self.source_node_id}__{self.action.semantic_id}__{self.target_node_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "instruction": self.instruction,
            "action": self.action.to_dict(),
            "capability": self.capability.to_dict() if self.capability else None,
            "target_observation": self.target_observation,
            "observed_delta": _list_to_dict(self.observed_delta),
            "schema_delta": self.schema_delta,
            "execution_trace": self.execution_trace.to_dict(),
            "pddl_hint": self.pddl_hint.to_dict() if self.pddl_hint else None,
            "visit_count": self.visit_count,
            "status": self.status,
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class WebKobeGraph:
    app: str
    start_node_id: str
    total_steps_completed: int
    nodes: list[WebKobeNode] = field(default_factory=list)
    edges: list[WebKobeEdge] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        meta = dict(self.meta)
        meta.update(
            {
                "schema_version": WEB_KOBE_SCHEMA_VERSION,
                "app": self.app,
                "start_node_id": self.start_node_id,
                "total_steps_completed": self.total_steps_completed,
            }
        )
        return {
            "meta": meta,
            "nodes": _list_to_dict(self.nodes),
            "edges": _list_to_dict(self.edges),
        }
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_graph.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/web_kobe_graph.py tests/safesym_bridge/test_web_kobe_graph.py
git commit -m "feat: add Web-KOBE graph model"
```

---

### Task 2: WebKobeGraphManager

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/web_kobe_graph_manager.py`
- Test: `tests/safesym_bridge/test_web_kobe_graph_manager.py`

**Interfaces:**
- Consumes:
  - `WebKobeNode`, `WebKobeEdge`, `WebKobeGraph`
- Produces:
  - `WebKobeGraphManager(app: str)`
  - `identify_or_add_node(node: WebKobeNode) -> str`
  - `add_edge(edge: WebKobeEdge) -> None`
  - `mark_interactable_explored(node_id: str, semantic_id: str) -> None`
  - `to_graph(start_node_id: str | None = None) -> WebKobeGraph`

- [ ] **Step 1: Write failing manager tests**

Create `tests/safesym_bridge/test_web_kobe_graph_manager.py`:

```python
from ai_web_explorer.safesym_bridge.capability_graph import Evidence, PageFrame
from ai_web_explorer.safesym_bridge.web_kobe_graph import (
    ReferenceObservation,
    WebKobeNode,
)
from ai_web_explorer.safesym_bridge.web_kobe_graph_manager import WebKobeGraphManager


def _node(node_id: str, values: dict, interactables=None) -> WebKobeNode:
    evidence = [Evidence(source="unit_test")]
    return WebKobeNode(
        node_id=node_id,
        page_description="product listing",
        page_frame=PageFrame(
            page_id="example:inventory",
            page_type="product_listing",
            url="https://example.test/inventory",
            url_pattern="https://example.test/inventory",
            title="Inventory",
            evidence=evidence,
        ),
        state_schema={key: [value] for key, value in values.items()},
        last_state_snapshot=values,
        interactable_elements=interactables or [],
        reference_observation=ReferenceObservation(
            url="https://example.test/inventory",
            title="Inventory",
        ),
        evidence=evidence,
    )


def test_identify_or_add_node_merges_schema_and_visit_count():
    manager = WebKobeGraphManager(app="example")

    first = _node("product_listing", {"cart_nonempty": False})
    second = _node("product_listing", {"cart_nonempty": True, "filter_open": False})

    assert manager.identify_or_add_node(first) == "product_listing"
    assert manager.identify_or_add_node(second) == "product_listing"

    graph = manager.to_graph()
    node = graph.nodes[0]
    assert node.visit_count == 2
    assert node.state_schema["cart_nonempty"] == [False, True]
    assert node.state_schema["filter_open"] == [False]
    assert node.last_state_snapshot == {"cart_nonempty": True, "filter_open": False}


def test_mark_interactable_explored_updates_matching_candidate():
    manager = WebKobeGraphManager(app="example")
    manager.identify_or_add_node(
        _node(
            "product_listing",
            {"cart_nonempty": False},
            interactables=[
                {
                    "semantic_id": "add_to_cart_product",
                    "description": "Add to cart",
                    "locator": "button.add",
                    "explored": False,
                }
            ],
        )
    )

    manager.mark_interactable_explored("product_listing", "add_to_cart_product")

    graph = manager.to_graph()
    assert graph.nodes[0].interactable_elements[0]["explored"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_graph_manager.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `web_kobe_graph_manager`.

- [ ] **Step 3: Implement manager**

Create `src/ai_web_explorer/safesym_bridge/web_kobe_graph_manager.py`:

```python
from __future__ import annotations

from collections import OrderedDict
from dataclasses import replace
from typing import Any

from ai_web_explorer.safesym_bridge.web_kobe_graph import (
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)


def _merge_schema(
    existing: dict[str, list[Any]],
    new_snapshot: dict[str, Any],
) -> dict[str, list[Any]]:
    merged = {key: list(values) for key, values in existing.items()}
    for key, value in new_snapshot.items():
        values = merged.setdefault(key, [])
        if value not in values:
            values.append(value)
    return merged


def _merge_interactables(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = [dict(item) for item in existing]
    seen = {
        (
            item.get("semantic_id"),
            item.get("locator"),
            item.get("description"),
        )
        for item in merged
    }
    for item in incoming:
        key = (item.get("semantic_id"), item.get("locator"), item.get("description"))
        if key not in seen:
            merged.append(dict(item))
            seen.add(key)
    return merged


class WebKobeGraphManager:
    def __init__(self, app: str):
        self.app = app
        self._nodes: OrderedDict[str, WebKobeNode] = OrderedDict()
        self._edges: OrderedDict[str, WebKobeEdge] = OrderedDict()
        self.total_steps_completed = 0

    def identify_or_add_node(self, node: WebKobeNode) -> str:
        existing = self._nodes.get(node.node_id)
        if existing is None:
            self._nodes[node.node_id] = replace(node, visit_count=max(node.visit_count, 1))
            return node.node_id

        self._nodes[node.node_id] = replace(
            existing,
            state_schema=_merge_schema(existing.state_schema, node.last_state_snapshot),
            last_state_snapshot=dict(node.last_state_snapshot),
            state_indicators=list(node.state_indicators or existing.state_indicators),
            action_targets=list(node.action_targets or existing.action_targets),
            interactable_elements=_merge_interactables(
                existing.interactable_elements,
                node.interactable_elements,
            ),
            capabilities=list(node.capabilities or existing.capabilities),
            reference_observation=node.reference_observation or existing.reference_observation,
            visit_count=existing.visit_count + 1,
            evidence=list(existing.evidence or node.evidence),
        )
        return node.node_id

    def add_edge(self, edge: WebKobeEdge) -> None:
        existing = self._edges.get(edge.edge_id)
        if existing is None:
            self._edges[edge.edge_id] = edge
        else:
            self._edges[edge.edge_id] = replace(
                existing,
                visit_count=existing.visit_count + 1,
                observed_delta=list(edge.observed_delta or existing.observed_delta),
                schema_delta=edge.schema_delta or existing.schema_delta,
                execution_trace=edge.execution_trace,
                evidence=list(existing.evidence or edge.evidence),
            )
        self.total_steps_completed += 1

    def mark_interactable_explored(self, node_id: str, semantic_id: str) -> None:
        node = self._nodes[node_id]
        interactables = []
        for item in node.interactable_elements:
            updated = dict(item)
            if updated.get("semantic_id") == semantic_id:
                updated["explored"] = True
            interactables.append(updated)
        self._nodes[node_id] = replace(node, interactable_elements=interactables)

    def to_graph(self, start_node_id: str | None = None) -> WebKobeGraph:
        resolved_start = start_node_id
        if resolved_start is None and self._nodes:
            resolved_start = next(iter(self._nodes))
        return WebKobeGraph(
            app=self.app,
            start_node_id=resolved_start or "",
            total_steps_completed=self.total_steps_completed,
            nodes=list(self._nodes.values()),
            edges=list(self._edges.values()),
        )
```

- [ ] **Step 4: Run manager tests**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_graph.py tests/safesym_bridge/test_web_kobe_graph_manager.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/web_kobe_graph_manager.py tests/safesym_bridge/test_web_kobe_graph_manager.py
git commit -m "feat: add Web-KOBE graph manager"
```

---

### Task 3: Deterministic Semantic Assistor and Action Extractor

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/web_semantic_assistor.py`
- Create: `src/ai_web_explorer/safesym_bridge/web_action_extractor.py`
- Test: `tests/safesym_bridge/test_web_semantic_assistor.py`
- Test: `tests/safesym_bridge/test_web_action_extractor.py`

**Interfaces:**
- Consumes:
  - `StateSnapshot`
  - `DomInteractableCandidate` from `dom_observer.py`
  - `ActionTarget`, `BrowserAction`, `WebKobeNode`
- Produces:
  - `SemanticStateDraft`
  - `SemanticAssistor` protocol
  - `DeterministicSemanticAssistor.describe_state(snapshot, candidates) -> SemanticStateDraft`
  - `browser_actions_from_candidates(candidates) -> list[BrowserAction]`

- [ ] **Step 1: Write failing semantic assistor test**

Create `tests/safesym_bridge/test_web_semantic_assistor.py`:

```python
from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.web_semantic_assistor import (
    DeterministicSemanticAssistor,
)


def test_deterministic_semantic_assistor_builds_listing_state_draft():
    snapshot = StateSnapshot(
        page_id="inventory",
        url="https://www.saucedemo.com/inventory.html",
        title="Swag Labs",
        signature={"cart_count": 0, "is_logged_in": True},
    )

    draft = DeterministicSemanticAssistor(app="saucedemo").describe_state(
        snapshot=snapshot,
        interactables=[
            {
                "semantic_id": "product_add_to_cart",
                "description": "Add to cart",
                "locator": 'button[data-test^="add-to-cart"]',
                "explored": False,
            }
        ],
    )

    assert draft.node_id == "inventory"
    assert draft.page_description == "inventory page"
    assert draft.page_frame.page_type == "inventory"
    assert draft.state_schema == {"cart_count": [0], "is_logged_in": [True]}
    assert draft.last_state_snapshot == {"cart_count": 0, "is_logged_in": True}
    assert draft.interactable_elements[0]["semantic_id"] == "product_add_to_cart"
```

- [ ] **Step 2: Write failing action extractor test**

Create `tests/safesym_bridge/test_web_action_extractor.py`:

```python
from ai_web_explorer.safesym_bridge.dom_observer import DomInteractableCandidate
from ai_web_explorer.safesym_bridge.web_action_extractor import (
    browser_actions_from_candidates,
)


def test_browser_actions_from_candidates_preserves_grounding():
    candidates = [
        DomInteractableCandidate(
            id="dom_001",
            kind="button",
            locator='button[data-test="checkout"]',
            locator_strategy="css",
            name="Checkout",
            visible=True,
            enabled=True,
            metadata={"id": "checkout"},
        )
    ]

    actions = browser_actions_from_candidates(candidates)

    assert len(actions) == 1
    assert actions[0].action_kind == "click"
    assert actions[0].locator == 'button[data-test="checkout"]'
    assert actions[0].semantic_id == "button_checkout"
    assert actions[0].description == "Checkout"
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_semantic_assistor.py tests/safesym_bridge/test_web_action_extractor.py -v
```

Expected: FAIL with missing modules.

- [ ] **Step 4: Implement semantic assistor**

Create `src/ai_web_explorer/safesym_bridge/web_semantic_assistor.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ai_web_explorer.safesym_bridge.capability_graph import Evidence, PageFrame
from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.observed_graph import _url_pattern_for


@dataclass(frozen=True)
class SemanticStateDraft:
    node_id: str
    page_description: str
    page_frame: PageFrame
    state_schema: dict[str, list[Any]]
    last_state_snapshot: dict[str, Any]
    interactable_elements: list[dict[str, Any]]
    evidence: list[Evidence]


class SemanticAssistor(Protocol):
    def describe_state(
        self,
        *,
        snapshot: StateSnapshot,
        interactables: list[dict[str, Any]],
    ) -> SemanticStateDraft:
        ...


class DeterministicSemanticAssistor:
    def __init__(self, app: str):
        self.app = app

    def describe_state(
        self,
        *,
        snapshot: StateSnapshot,
        interactables: list[dict[str, Any]],
    ) -> SemanticStateDraft:
        evidence = [
            Evidence(
                source="deterministic_assistor",
                url=snapshot.url,
                confidence=1.0,
            )
        ]
        last_state = dict(snapshot.signature)
        page_frame = PageFrame(
            page_id=f"{self.app}:{snapshot.page_id}",
            page_type=snapshot.page_id,
            url=snapshot.url,
            url_pattern=_url_pattern_for(snapshot.url),
            title=snapshot.title,
            heading=None,
            signature_hints=last_state,
            evidence=evidence,
        )
        return SemanticStateDraft(
            node_id=snapshot.page_id,
            page_description=f"{snapshot.page_id} page",
            page_frame=page_frame,
            state_schema={key: [value] for key, value in last_state.items()},
            last_state_snapshot=last_state,
            interactable_elements=[dict(item) for item in interactables],
            evidence=evidence,
        )
```

- [ ] **Step 5: Implement action extractor**

Create `src/ai_web_explorer/safesym_bridge/web_action_extractor.py`:

```python
from __future__ import annotations

import re

from ai_web_explorer.safesym_bridge.dom_observer import DomInteractableCandidate
from ai_web_explorer.safesym_bridge.web_kobe_graph import BrowserAction


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return cleaned or "unnamed"


def browser_actions_from_candidates(
    candidates: list[DomInteractableCandidate],
) -> list[BrowserAction]:
    actions: list[BrowserAction] = []
    for candidate in candidates:
        if candidate.kind in {"input", "textarea", "select"}:
            action_kind = "fill" if candidate.kind != "select" else "select"
        else:
            action_kind = "click"
        visible = candidate.name or candidate.metadata.get("id") or candidate.locator
        semantic_id = f"{candidate.kind}_{_slug(visible)}"
        actions.append(
            BrowserAction(
                action_kind=action_kind,
                locator=candidate.locator,
                semantic_id=semantic_id,
                description=candidate.name,
            )
        )
    return actions
```

- [ ] **Step 6: Run tests**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_semantic_assistor.py tests/safesym_bridge/test_web_action_extractor.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/web_semantic_assistor.py src/ai_web_explorer/safesym_bridge/web_action_extractor.py tests/safesym_bridge/test_web_semantic_assistor.py tests/safesym_bridge/test_web_action_extractor.py
git commit -m "feat: add deterministic Web-KOBE semantic extraction"
```

---

### Task 4: One-Step WebKobeExplorer

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/web_kobe_explorer.py`
- Test: `tests/safesym_bridge/test_web_kobe_explorer.py`

**Interfaces:**
- Consumes:
  - `StateSnapshot`
  - `BrowserAction`
  - `WebKobeGraphManager`
  - `SemanticAssistor`
- Produces:
  - `WebKobeExplorer`
  - `WebKobeAdapter` protocol:
    - `app_name: str`
    - `observe_state() -> Awaitable[StateSnapshot]`
    - `list_interactables(state: StateSnapshot) -> Awaitable[list[dict[str, Any]]]`
    - `execute(action: BrowserAction) -> Awaitable[bool]`
  - `explore_one_step() -> WebKobeGraph`

- [ ] **Step 1: Write failing one-step explorer test**

Create `tests/safesym_bridge/test_web_kobe_explorer.py`:

```python
import pytest

from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.web_kobe_explorer import WebKobeExplorer
from ai_web_explorer.safesym_bridge.web_kobe_graph import BrowserAction
from ai_web_explorer.safesym_bridge.web_semantic_assistor import (
    DeterministicSemanticAssistor,
)


class FakeAdapter:
    app_name = "fake"

    def __init__(self):
        self.states = [
            StateSnapshot(
                page_id="listing",
                url="https://example.test/listing",
                title="Listing",
                signature={"cart_nonempty": False},
            ),
            StateSnapshot(
                page_id="listing",
                url="https://example.test/listing",
                title="Listing",
                signature={"cart_nonempty": True},
            ),
        ]
        self.executed = []

    async def observe_state(self):
        return self.states[min(len(self.executed), 1)]

    async def list_interactables(self, state):
        return [
            {
                "semantic_id": "add_to_cart_product",
                "description": "Add to cart",
                "locator": "button.add",
                "action_kind": "click",
                "explored": False,
            }
        ]

    async def execute(self, action: BrowserAction):
        self.executed.append(action)
        return True


@pytest.mark.anyio
async def test_explore_one_step_records_self_loop_delta():
    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    graph = await explorer.explore_one_step()

    assert graph.total_steps_completed == 1
    assert len(graph.nodes) == 1
    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert edge.source_node_id == "listing"
    assert edge.target_node_id == "listing"
    assert edge.action.semantic_id == "add_to_cart_product"
    assert edge.schema_delta == {
        "cart_nonempty": {"before": False, "after": True}
    }
    assert edge.observed_delta[0].field == "cart_nonempty"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_explorer.py -v
```

Expected: FAIL with missing module.

- [ ] **Step 3: Implement one-step explorer**

Create `src/ai_web_explorer/safesym_bridge/web_kobe_explorer.py`:

```python
from __future__ import annotations

from typing import Any, Protocol

from ai_web_explorer.safesym_bridge.capability_graph import (
    Evidence,
    ExecutionTrace,
    ObservedDelta,
)
from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.web_kobe_graph import (
    BrowserAction,
    ReferenceObservation,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.safesym_bridge.web_kobe_graph_manager import WebKobeGraphManager
from ai_web_explorer.safesym_bridge.web_semantic_assistor import SemanticAssistor


class WebKobeAdapter(Protocol):
    app_name: str

    async def observe_state(self) -> StateSnapshot:
        ...

    async def list_interactables(
        self,
        state: StateSnapshot,
    ) -> list[dict[str, Any]]:
        ...

    async def execute(self, action: BrowserAction) -> bool:
        ...


def _schema_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any] | None:
    delta: dict[str, Any] = {}
    for key in sorted(set(before) | set(after)):
        before_value = before.get(key)
        after_value = after.get(key)
        if before_value != after_value:
            delta[key] = {"before": before_value, "after": after_value}
    return delta or None


def _observed_delta(before: dict[str, Any], after: dict[str, Any], url: str) -> list[ObservedDelta]:
    evidence = [Evidence(source="web_kobe_transition_diff", url=url)]
    deltas: list[ObservedDelta] = []
    for key, value in (_schema_delta(before, after) or {}).items():
        deltas.append(
            ObservedDelta(
                field=key,
                before=value["before"],
                after=value["after"],
                delta_type="state_indicator_change",
                evidence=evidence,
            )
        )
    return deltas


def _node_from_draft(draft) -> WebKobeNode:
    return WebKobeNode(
        node_id=draft.node_id,
        page_description=draft.page_description,
        page_frame=draft.page_frame,
        state_schema=draft.state_schema,
        last_state_snapshot=draft.last_state_snapshot,
        interactable_elements=draft.interactable_elements,
        reference_observation=ReferenceObservation(
            url=draft.page_frame.url,
            title=draft.page_frame.title,
        ),
        evidence=draft.evidence,
    )


def _first_unexplored_action(interactables: list[dict[str, Any]]) -> BrowserAction | None:
    for item in interactables:
        if item.get("explored"):
            continue
        semantic_id = str(item.get("semantic_id") or "unknown_action")
        return BrowserAction(
            action_kind=str(item.get("action_kind") or "click"),
            locator=item.get("locator"),
            semantic_id=semantic_id,
            description=item.get("description"),
        )
    return None


class WebKobeExplorer:
    def __init__(
        self,
        *,
        adapter: WebKobeAdapter,
        semantic_assistor: SemanticAssistor,
    ):
        self.adapter = adapter
        self.semantic_assistor = semantic_assistor
        self.manager = WebKobeGraphManager(app=adapter.app_name)

    async def explore_one_step(self) -> WebKobeGraph:
        before = await self.adapter.observe_state()
        before_interactables = await self.adapter.list_interactables(before)
        before_draft = self.semantic_assistor.describe_state(
            snapshot=before,
            interactables=before_interactables,
        )
        source_id = self.manager.identify_or_add_node(_node_from_draft(before_draft))

        selected = _first_unexplored_action(before_interactables)
        if selected is None:
            return self.manager.to_graph(start_node_id=source_id)

        success = await self.adapter.execute(selected)
        after = await self.adapter.observe_state()
        after_interactables = await self.adapter.list_interactables(after)
        after_draft = self.semantic_assistor.describe_state(
            snapshot=after,
            interactables=after_interactables,
        )
        target_id = self.manager.identify_or_add_node(_node_from_draft(after_draft))

        delta = _schema_delta(before_draft.last_state_snapshot, after_draft.last_state_snapshot)
        edge = WebKobeEdge(
            source_node_id=source_id,
            target_node_id=target_id,
            instruction=selected.description or selected.semantic_id,
            action=selected,
            capability=None,
            target_observation=after_draft.page_description,
            observed_delta=_observed_delta(
                before_draft.last_state_snapshot,
                after_draft.last_state_snapshot,
                after.url,
            ),
            schema_delta=delta,
            execution_trace=ExecutionTrace(
                concrete_action_kind=selected.action_kind,
                concrete_locator=selected.locator,
                concrete_target_sample=selected.semantic_id,
                input_values_used=dict(selected.input_values),
                before_observation_id=source_id,
                after_observation_id=target_id,
                success=success,
                error=None if success else "adapter execution returned false",
            ),
            status="verified" if success else "failed_execution",
            evidence=[Evidence(source="web_kobe_explorer", url=before.url)],
        )
        self.manager.add_edge(edge)
        self.manager.mark_interactable_explored(source_id, selected.semantic_id)
        return self.manager.to_graph(start_node_id=source_id)
```

- [ ] **Step 4: Run one-step explorer tests**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_explorer.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/web_kobe_explorer.py tests/safesym_bridge/test_web_kobe_explorer.py
git commit -m "feat: add one-step Web-KOBE explorer"
```

---

### Task 5: Simple WebKobeGraph to PDDL Projector

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
- Test: `tests/safesym_bridge/test_web_kobe_pddl_projector.py`

**Interfaces:**
- Consumes:
  - `WebKobeGraph`
  - `WebKobeNode`
  - `WebKobeEdge`
- Produces:
  - `WebKobePddlArtifacts(domain: str, problem: str)`
  - `compile_web_kobe_graph_to_pddl(graph: WebKobeGraph, goal_node_id: str) -> WebKobePddlArtifacts`

- [ ] **Step 1: Write failing PDDL projector test**

Create `tests/safesym_bridge/test_web_kobe_pddl_projector.py`:

```python
from ai_web_explorer.safesym_bridge.capability_graph import (
    Evidence,
    ExecutionTrace,
    ObservedDelta,
    PageFrame,
)
from ai_web_explorer.safesym_bridge.web_kobe_graph import (
    BrowserAction,
    ReferenceObservation,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
    compile_web_kobe_graph_to_pddl,
)


def _node(node_id: str, page_type: str, values: dict) -> WebKobeNode:
    evidence = [Evidence(source="unit_test")]
    return WebKobeNode(
        node_id=node_id,
        page_description=f"{page_type} page",
        page_frame=PageFrame(
            page_id=f"example:{page_type}",
            page_type=page_type,
            url=f"https://example.test/{page_type}",
            url_pattern=f"https://example.test/{page_type}",
            title=page_type,
            evidence=evidence,
        ),
        state_schema={key: [value] for key, value in values.items()},
        last_state_snapshot=values,
        reference_observation=ReferenceObservation(
            url=f"https://example.test/{page_type}",
            title=page_type,
        ),
        evidence=evidence,
    )


def test_compile_web_kobe_graph_to_pddl_uses_page_and_boolean_delta():
    graph = WebKobeGraph(
        app="example",
        start_node_id="listing_empty",
        total_steps_completed=1,
        nodes=[
            _node("listing_empty", "product_listing", {"cart_nonempty": False}),
            _node("listing_nonempty", "product_listing", {"cart_nonempty": True}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="listing_empty",
                target_node_id="listing_nonempty",
                instruction="add to cart",
                action=BrowserAction("click", "button.add", "add_to_cart_product"),
                capability=None,
                target_observation="product listing page",
                observed_delta=[
                    ObservedDelta(
                        "cart_nonempty",
                        False,
                        True,
                        "state_indicator_change",
                        evidence=[Evidence(source="unit_test")],
                    )
                ],
                schema_delta={"cart_nonempty": {"before": False, "after": True}},
                execution_trace=ExecutionTrace(
                    "click",
                    "button.add",
                    "product",
                    {},
                    "listing_empty",
                    "listing_nonempty",
                    True,
                ),
            )
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(
        graph,
        goal_node_id="listing_nonempty",
    )

    assert "(:action add_to_cart_product" in artifacts.domain
    assert "(at_listing_empty)" in artifacts.problem
    assert "(cart_nonempty)" in artifacts.domain
    assert "(:goal (and (at_listing_nonempty)))" in artifacts.problem
    assert "(not (at_listing_empty))" in artifacts.domain
    assert "(at_listing_nonempty)" in artifacts.domain
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py -v
```

Expected: FAIL with missing module.

- [ ] **Step 3: Implement constrained PDDL projector**

Create `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from ai_web_explorer.safesym_bridge.web_kobe_graph import WebKobeGraph
from ai_web_explorer.safesym_bridge.capability_graph import Evidence, PageFrame
from ai_web_explorer.safesym_bridge.web_kobe_graph import (
    ReferenceObservation,
    WebKobeNode,
)


@dataclass(frozen=True)
class WebKobePddlArtifacts:
    domain: str
    problem: str


def _predicate(name: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")


def _at(node_id: str) -> str:
    return f"at_{_predicate(node_id)}"


def _boolean_predicates(graph: WebKobeGraph) -> list[str]:
    names: set[str] = set()
    for node in graph.nodes:
        for key, value in node.last_state_snapshot.items():
            if isinstance(value, bool):
                names.add(_predicate(key))
    return sorted(names)


def _initial_predicates(graph: WebKobeGraph) -> list[str]:
    start = next(node for node in graph.nodes if node.node_id == graph.start_node_id)
    predicates = [_at(start.node_id)]
    for key, value in start.last_state_snapshot.items():
        if isinstance(value, bool) and value is True:
            predicates.append(_predicate(key))
    return sorted(predicates)


def _action_name(raw: str) -> str:
    return _predicate(raw)


def _effects_for_edge(edge) -> list[str]:
    effects = [f"(not ({_at(edge.source_node_id)}))", f"({_at(edge.target_node_id)})"]
    for delta in edge.observed_delta:
        if isinstance(delta.after, bool):
            pred = _predicate(delta.field)
            if delta.after:
                effects.append(f"({pred})")
            else:
                effects.append(f"(not ({pred}))")
    return effects


def compile_web_kobe_graph_to_pddl(
    graph: WebKobeGraph,
    *,
    goal_node_id: str,
) -> WebKobePddlArtifacts:
    predicates = sorted(
        set([_at(node.node_id) for node in graph.nodes] + _boolean_predicates(graph))
    )
    predicate_text = "\n".join(f"    ({name})" for name in predicates)

    action_blocks = []
    for edge in graph.edges:
        action_name = _action_name(edge.action.semantic_id)
        preconditions = [f"({_at(edge.source_node_id)})"]
        effects = _effects_for_edge(edge)
        action_blocks.append(
            "\n".join(
                [
                    f"  (:action {action_name}",
                    f"    :precondition (and {' '.join(preconditions)})",
                    f"    :effect (and {' '.join(effects)})",
                    "  )",
                ]
            )
        )

    domain = "\n".join(
        [
            "(define (domain web-kobe)",
            "  (:requirements :strips)",
            "  (:predicates",
            predicate_text,
            "  )",
            *action_blocks,
            ")",
        ]
    )
    init_text = " ".join(f"({name})" for name in _initial_predicates(graph))
    problem = "\n".join(
        [
            "(define (problem web-kobe-problem)",
            "  (:domain web-kobe)",
            f"  (:init {init_text})",
            f"  (:goal (and ({_at(goal_node_id)})))",
            ")",
        ]
    )
    return WebKobePddlArtifacts(domain=domain, problem=problem)
```

- [ ] **Step 4: Run projector tests**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py tests/safesym_bridge/test_web_kobe_pddl_projector.py
git commit -m "feat: project Web-KOBE graph to PDDL"
```

---

### Task 6: Browser Runner and CLI Debug Commands

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Test: extend `tests/safesym_bridge/test_cli.py`

**Interfaces:**
- Consumes:
  - `WebKobeGraph.to_dict()`
  - `compile_web_kobe_graph_to_pddl(...)`
- Produces:
  - `write_web_kobe_graph(graph: WebKobeGraph, output: Path) -> None`
  - CLI command `web-kobe-graph --output <path>`
  - CLI command `web-kobe-pddl --output <dir>`

- [ ] **Step 1: Add failing CLI tests**

Append to `tests/safesym_bridge/test_cli.py`:

```python
def test_main_web_kobe_graph_subcommand_writes_graph(monkeypatch, tmp_path):
    from ai_web_explorer.safesym_bridge import cli
    from ai_web_explorer.safesym_bridge.web_kobe_graph import WebKobeGraph

    output = tmp_path / "web_kobe_graph.json"

    def fake_build_debug_web_kobe_graph():
        return WebKobeGraph(
            app="debug",
            start_node_id="start",
            total_steps_completed=0,
            nodes=[],
            edges=[],
        )

    monkeypatch.setattr(cli, "build_debug_web_kobe_graph", fake_build_debug_web_kobe_graph)

    assert cli.main(["web-kobe-graph", "--output", str(output)]) == 0
    assert output.exists()
    assert "web-kobe-graph-v1" in output.read_text(encoding="utf-8")


def test_main_web_kobe_pddl_subcommand_writes_domain_and_problem(monkeypatch, tmp_path):
    from ai_web_explorer.safesym_bridge import cli
    from ai_web_explorer.safesym_bridge.web_kobe_graph import WebKobeGraph

    output = tmp_path / "web_kobe_pddl"

    def fake_build_debug_web_kobe_graph():
        return WebKobeGraph(
            app="debug",
            start_node_id="start",
            total_steps_completed=0,
            nodes=[],
            edges=[],
        )

    class FakeArtifacts:
        domain = "(define (domain web-kobe))"
        problem = "(define (problem web-kobe-problem))"

    monkeypatch.setattr(cli, "build_debug_web_kobe_graph", fake_build_debug_web_kobe_graph)
    monkeypatch.setattr(
        cli,
        "compile_web_kobe_graph_to_pddl",
        lambda graph, goal_node_id: FakeArtifacts(),
    )

    assert cli.main(["web-kobe-pddl", "--output", str(output), "--goal-node", "start"]) == 0
    assert (output / "domain.pddl").read_text(encoding="utf-8") == FakeArtifacts.domain
    assert (output / "problem.pddl").read_text(encoding="utf-8") == FakeArtifacts.problem
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/safesym_bridge/test_cli.py -v
```

Expected: FAIL because `web-kobe-graph` is not a known subcommand.

- [ ] **Step 3: Add debug graph builder and writer**

In `src/ai_web_explorer/safesym_bridge/browser_runner.py`, add:

```python
import json
from pathlib import Path

from ai_web_explorer.safesym_bridge.web_kobe_graph import WebKobeGraph


def build_debug_web_kobe_graph() -> WebKobeGraph:
    evidence = [Evidence(source="debug_builder")]
    start_node = WebKobeNode(
        node_id="start",
        page_description="debug start page",
        page_frame=PageFrame(
            page_id="debug:start",
            page_type="start",
            url="about:blank",
            url_pattern="about:blank",
            title="Debug",
            evidence=evidence,
        ),
        state_schema={},
        last_state_snapshot={},
        reference_observation=ReferenceObservation(url="about:blank", title="Debug"),
        visit_count=1,
        evidence=evidence,
    )
    return WebKobeGraph(
        app="debug",
        start_node_id="start",
        total_steps_completed=0,
        nodes=[start_node],
        edges=[],
        meta={"source": "debug_builder"},
    )


def write_web_kobe_graph(graph: WebKobeGraph, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(graph.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
```

If `browser_runner.py` already imports `json` or `Path`, reuse existing imports instead of duplicating them.

- [ ] **Step 4: Add CLI subcommands**

In `src/ai_web_explorer/safesym_bridge/cli.py`, import:

```python
from ai_web_explorer.safesym_bridge.browser_runner import (
    build_debug_web_kobe_graph,
    write_web_kobe_graph,
)
from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
    compile_web_kobe_graph_to_pddl,
)
```

Add parser setup:

```python
web_kobe_graph_parser = subparsers.add_parser(
    "web-kobe-graph",
    help="Write a debug Web-KOBE exploration graph JSON.",
)
web_kobe_graph_parser.add_argument("--output", required=True)

web_kobe_pddl_parser = subparsers.add_parser(
    "web-kobe-pddl",
    help="Write debug Web-KOBE PDDL domain/problem files.",
)
web_kobe_pddl_parser.add_argument("--output", required=True)
web_kobe_pddl_parser.add_argument("--goal-node", required=True)
```

Add command handling:

```python
if args.command == "web-kobe-graph":
    graph = build_debug_web_kobe_graph()
    write_web_kobe_graph(graph, Path(args.output))
    return 0

if args.command == "web-kobe-pddl":
    graph = build_debug_web_kobe_graph()
    artifacts = compile_web_kobe_graph_to_pddl(
        graph,
        goal_node_id=args.goal_node,
    )
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "domain.pddl").write_text(artifacts.domain, encoding="utf-8")
    (output / "problem.pddl").write_text(artifacts.problem, encoding="utf-8")
    return 0
```

Use the existing `cli.py` style for parser variable names and return behavior.

- [ ] **Step 5: Run CLI tests**

Run:

```bash
python -m pytest tests/safesym_bridge/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/browser_runner.py src/ai_web_explorer/safesym_bridge/cli.py tests/safesym_bridge/test_cli.py
git commit -m "feat: expose Web-KOBE debug CLI"
```

---

### Task 7: Documentation and Full Verification

**Files:**
- Modify: `docs/current-project-overview.md`
- Modify: `docs/safesym-bridge.md`

**Interfaces:**
- Consumes:
  - CLI commands from Task 6
  - PDDL projector from Task 5
- Produces:
  - docs showing that Web-KOBE graph is the new generic exploration direction while current SauceDemo graph/PDDL path remains available.

- [ ] **Step 1: Update current project overview**

In `docs/current-project-overview.md`, add a section after the experimental capability graph paragraph:

```markdown
An early Web-KOBE-style exploration graph is being introduced as the next
generic exploration direction:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-graph --output outputs/web_kobe_graph.json
python -m ai_web_explorer.safesym_bridge.cli web-kobe-pddl --output outputs/web_kobe_pddl --goal-node start
```

This graph is intended to become the main exploration-time representation for
unknown websites. It records semantic page states, browser-grounded actions,
observed deltas, and evidence so the project can later project unknown web
environments into SafeSym-compatible PDDL.
```

- [ ] **Step 2: Update SafeSym bridge doc**

In `docs/safesym-bridge.md`, add a "Generic Web-KOBE Direction" section:

```markdown
## Generic Web-KOBE Direction

The project is adding a Web-KOBE-style exploration graph for unknown web
environments. This does not replace the current SauceDemo graph/PDDL path yet.

The intended long-term chain is:

```text
unknown website
  -> Web-KOBE exploration graph
  -> PDDL projection
  -> SafeSym
```

Debug commands:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-graph --output outputs/web_kobe_graph.json
python -m ai_web_explorer.safesym_bridge.cli web-kobe-pddl --output outputs/web_kobe_pddl --goal-node start
```
```

- [ ] **Step 3: Run focused Web-KOBE tests**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_graph.py tests/safesym_bridge/test_web_kobe_graph_manager.py tests/safesym_bridge/test_web_semantic_assistor.py tests/safesym_bridge/test_web_action_extractor.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_web_kobe_pddl_projector.py tests/safesym_bridge/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 4: Run full bridge regression**

Run:

```bash
python -m pytest tests/safesym_bridge -v
```

Expected: PASS with existing skipped browser smoke tests still skipped unless local browser smoke dependencies are enabled.

- [ ] **Step 5: Generate debug artifacts manually**

Run:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-graph --output outputs/web_kobe_graph.json
python -m ai_web_explorer.safesym_bridge.cli web-kobe-pddl --output outputs/web_kobe_pddl --goal-node start
```

Expected:

- `outputs/web_kobe_graph.json` exists and contains `"schema_version": "web-kobe-graph-v1"`.
- `outputs/web_kobe_pddl/domain.pddl` exists.
- `outputs/web_kobe_pddl/problem.pddl` exists.

- [ ] **Step 6: Commit docs**

```bash
git add docs/current-project-overview.md docs/safesym-bridge.md
git commit -m "docs: document Web-KOBE SafeSym path"
```

---

## Self-Review Checklist

- Spec coverage:
  - Web-KOBE single semantic graph: Tasks 1 and 2.
  - Semantic exploration agent loop: Task 4.
  - LLM/VLM seam without required dependency: Task 3.
  - Browser-grounded verification: Task 4.
  - PDDL projection: Task 5.
  - SafeSym-compatible path and docs: Tasks 6 and 7.
  - Existing SauceDemo path preserved: Global Constraints and Task 7 regression.

- Scope decision:
  - The plan intentionally excludes graph audit, coverage checkpointing, real LLM/VLM integration, generic parameterized PDDL, and high-risk action handling from the first implementation slice.

- Type consistency:
  - `BrowserAction`, `ActionTarget`, `PddlActionHint`, `WebKobeNode`, `WebKobeEdge`, and `WebKobeGraph` are defined in Task 1 and reused consistently by later tasks.
  - `WebKobeGraphManager` methods are defined in Task 2 and consumed by Task 4.
  - `DeterministicSemanticAssistor.describe_state(...)` is defined in Task 3 and consumed by Task 4.
  - `compile_web_kobe_graph_to_pddl(...)` is defined in Task 5 and consumed by Task 6.

## Execution Handoff

Plan implementation should proceed task-by-task with tests and commits after
each task. Because the user requested single-agent work by default, Inline
Execution is the expected execution mode unless the user explicitly allows
subagents.
