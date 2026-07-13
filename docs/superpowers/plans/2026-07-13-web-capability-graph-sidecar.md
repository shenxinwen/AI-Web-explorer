# Web Capability Graph Sidecar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. The user explicitly requested default single-agent work and no subagents unless explicitly allowed, so do not use subagent-driven execution for this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an experimental WebCapabilityGraph sidecar artifact for SauceDemo without replacing the existing WebObservedGraph, PDDL, or SafeSym pipeline.

**Architecture:** Introduce a small capability graph data model, a SauceDemo-focused builder that projects existing `ObservedTransition` records into capability-oriented states/transitions, and CLI/browser-runner entry points that write the sidecar JSON. Keep it side-by-side with the current graph-first path so the existing MVP remains stable.

**Tech Stack:** Python 3.9+, dataclasses, pytest, existing `ai_web_explorer.safesym_bridge` modules, Playwright only through existing browser runner paths.

## Global Constraints

- Preserve existing `WebObservedGraph -> PDDL -> SafeSym` behavior.
- Do not persist concrete product instances, product names, prices, or images in the capability graph core model.
- Keep SafeSym safety policy out of the WebCapabilityGraph model.
- Prefer deterministic SauceDemo projection for v1; no new LLM/VLM dependency.
- Do not touch unrelated dirty worktree files.
- Maintain current test style under `tests/safesym_bridge/`.

---

## File Structure

- Create `src/ai_web_explorer/safesym_bridge/capability_graph.py`
  - Owns v1 dataclasses and `to_dict()` serialization for capability graph artifacts.

- Create `src/ai_web_explorer/safesym_bridge/capability_builder.py`
  - Projects existing `ObservedTransition` records into `WebCapabilityGraph`.
  - Contains SauceDemo v1 action/page projection rules.

- Modify `src/ai_web_explorer/safesym_bridge/browser_runner.py`
  - Adds `write_capability_graph()` and `run_saucedemo_explored_capability_graph()`.

- Modify `src/ai_web_explorer/safesym_bridge/cli.py`
  - Adds debug `capability-graph` and browser `explore-capability-graph` commands.

- Create `tests/safesym_bridge/test_capability_graph.py`
  - Verifies dataclass serialization shape.

- Create `tests/safesym_bridge/test_capability_builder.py`
  - Verifies SauceDemo projection, abstract product target, self-loop state delta, and no content-instance leakage.

- Modify `tests/safesym_bridge/test_cli.py`
  - Verifies new CLI commands write or dispatch correctly.

- Modify `docs/current-project-overview.md`
  - Adds one short note that WebCapabilityGraph is an experimental sidecar.

---

### Task 1: Add WebCapabilityGraph data model

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/capability_graph.py`
- Test: `tests/safesym_bridge/test_capability_graph.py`

**Interfaces:**
- Produces: `WebCapabilityGraph.to_dict() -> dict[str, Any]`
- Produces: dataclasses `Evidence`, `PageFrame`, `StateIndicator`, `InputSlot`, `GroundingPattern`, `AvailabilityCondition`, `StateChangeHint`, `Capability`, `ObservedDelta`, `ExecutionTrace`, `CapabilityTransition`, `SemanticPageState`, `WebCapabilityGraph`
- Consumes: only Python stdlib dataclasses and typing

- [ ] **Step 1: Write the failing serialization test**

Create `tests/safesym_bridge/test_capability_graph.py`:

```python
from ai_web_explorer.safesym_bridge.capability_graph import (
    AvailabilityCondition,
    Capability,
    CapabilityTransition,
    Evidence,
    ExecutionTrace,
    GroundingPattern,
    ObservedDelta,
    PageFrame,
    SemanticPageState,
    StateChangeHint,
    StateIndicator,
    WebCapabilityGraph,
)


def test_web_capability_graph_to_dict_uses_expected_shape():
    evidence = Evidence(
        source="dom",
        selector='button[data-test="checkout"]',
        text_sample="Checkout",
        url="https://www.saucedemo.com/cart.html",
        confidence=1.0,
    )
    capability = Capability(
        capability_id="checkout_start",
        semantic_action="checkout_start",
        action_kind="click",
        target_type="cart",
        target_role="current_cart",
        grounding=GroundingPattern(
            locator_strategy="css",
            locator_pattern='button[data-test="checkout"]',
            target_selection_policy="single",
        ),
        availability=AvailabilityCondition(
            required_page_type="cart",
            required_state_indicators={"cart_nonempty": True},
        ),
        expected_delta=[
            StateChangeHint(field="page_type", before="cart", after="checkout_info")
        ],
        evidence=[evidence],
    )
    graph = WebCapabilityGraph(
        app="saucedemo",
        start_state="cart_nonempty",
        total_steps_completed=1,
        states=[
            SemanticPageState(
                state_id="cart_nonempty",
                page_frame=PageFrame(
                    page_id="saucedemo:cart",
                    page_type="cart",
                    url="https://www.saucedemo.com/cart.html",
                    url_pattern="/cart.html",
                    title="Swag Labs",
                    heading="Your Cart",
                    signature_hints={"cart_nonempty": True},
                    evidence=[evidence],
                ),
                state_indicators=[
                    StateIndicator(
                        name="cart_nonempty",
                        value=True,
                        role="capability_precondition",
                        evidence=[evidence],
                    )
                ],
                capabilities=[capability],
                evidence=[evidence],
            )
        ],
        transitions=[
            CapabilityTransition(
                transition_id="cart_nonempty__checkout_start__checkout_info",
                source_state_id="cart_nonempty",
                capability_id="checkout_start",
                target_state_id="checkout_info",
                transition_kind="navigation",
                observed_delta=[
                    ObservedDelta(
                        field="page_type",
                        before="cart",
                        after="checkout_info",
                        delta_type="page_frame_change",
                        confidence=1.0,
                        evidence=[evidence],
                    )
                ],
                execution_trace=ExecutionTrace(
                    concrete_action_kind="click",
                    concrete_locator='button[data-test="checkout"]',
                    concrete_target_sample=None,
                    input_values_used={},
                    before_observation_id="cart_nonempty",
                    after_observation_id="checkout_info",
                    success=True,
                    error=None,
                ),
                evidence=[evidence],
            )
        ],
    )

    assert graph.to_dict() == {
        "meta": {
            "schema_version": "web-capability-graph-v1",
            "app": "saucedemo",
            "start_state": "cart_nonempty",
            "total_steps_completed": 1,
        },
        "states": [
            {
                "state_id": "cart_nonempty",
                "page_frame": {
                    "page_id": "saucedemo:cart",
                    "page_type": "cart",
                    "url": "https://www.saucedemo.com/cart.html",
                    "url_pattern": "/cart.html",
                    "title": "Swag Labs",
                    "heading": "Your Cart",
                    "signature_hints": {"cart_nonempty": True},
                    "evidence": [
                        {
                            "source": "dom",
                            "selector": 'button[data-test="checkout"]',
                            "text_sample": "Checkout",
                            "url": "https://www.saucedemo.com/cart.html",
                            "confidence": 1.0,
                        }
                    ],
                },
                "state_indicators": [
                    {
                        "name": "cart_nonempty",
                        "value": True,
                        "role": "capability_precondition",
                        "evidence": [
                            {
                                "source": "dom",
                                "selector": 'button[data-test="checkout"]',
                                "text_sample": "Checkout",
                                "url": "https://www.saucedemo.com/cart.html",
                                "confidence": 1.0,
                            }
                        ],
                    }
                ],
                "capabilities": [
                    {
                        "capability_id": "checkout_start",
                        "semantic_action": "checkout_start",
                        "action_kind": "click",
                        "target_type": "cart",
                        "target_role": "current_cart",
                        "input_schema": [],
                        "grounding": {
                            "locator_strategy": "css",
                            "locator_pattern": 'button[data-test="checkout"]',
                            "target_selection_policy": "single",
                            "field_bindings": {},
                        },
                        "availability": {
                            "required_page_type": "cart",
                            "required_state_indicators": {"cart_nonempty": True},
                            "required_target_presence": None,
                        },
                        "expected_delta": [
                            {
                                "field": "page_type",
                                "before": "cart",
                                "after": "checkout_info",
                            }
                        ],
                        "evidence": [
                            {
                                "source": "dom",
                                "selector": 'button[data-test="checkout"]',
                                "text_sample": "Checkout",
                                "url": "https://www.saucedemo.com/cart.html",
                                "confidence": 1.0,
                            }
                        ],
                    }
                ],
                "evidence": [
                    {
                        "source": "dom",
                        "selector": 'button[data-test="checkout"]',
                        "text_sample": "Checkout",
                        "url": "https://www.saucedemo.com/cart.html",
                        "confidence": 1.0,
                    }
                ],
            }
        ],
        "transitions": [
            {
                "transition_id": "cart_nonempty__checkout_start__checkout_info",
                "source_state_id": "cart_nonempty",
                "capability_id": "checkout_start",
                "target_state_id": "checkout_info",
                "transition_kind": "navigation",
                "observed_delta": [
                    {
                        "field": "page_type",
                        "before": "cart",
                        "after": "checkout_info",
                        "delta_type": "page_frame_change",
                        "confidence": 1.0,
                        "evidence": [
                            {
                                "source": "dom",
                                "selector": 'button[data-test="checkout"]',
                                "text_sample": "Checkout",
                                "url": "https://www.saucedemo.com/cart.html",
                                "confidence": 1.0,
                            }
                        ],
                    }
                ],
                "execution_trace": {
                    "concrete_action_kind": "click",
                    "concrete_locator": 'button[data-test="checkout"]',
                    "concrete_target_sample": None,
                    "input_values_used": {},
                    "before_observation_id": "cart_nonempty",
                    "after_observation_id": "checkout_info",
                    "success": True,
                    "error": None,
                },
                "evidence": [
                    {
                        "source": "dom",
                        "selector": 'button[data-test="checkout"]',
                        "text_sample": "Checkout",
                        "url": "https://www.saucedemo.com/cart.html",
                        "confidence": 1.0,
                    }
                ],
            }
        ],
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/safesym_bridge/test_capability_graph.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'ai_web_explorer.safesym_bridge.capability_graph'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/ai_web_explorer/safesym_bridge/capability_graph.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = "web-capability-graph-v1"


def _list_to_dict(items: list[Any]) -> list[dict[str, Any]]:
    return [item.to_dict() for item in items]


@dataclass(frozen=True)
class Evidence:
    source: str
    selector: str | None = None
    text_sample: str | None = None
    url: str | None = None
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "selector": self.selector,
            "text_sample": self.text_sample,
            "url": self.url,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class PageFrame:
    page_id: str
    page_type: str
    url: str
    url_pattern: str
    title: str
    heading: str | None = None
    signature_hints: dict[str, Any] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_id": self.page_id,
            "page_type": self.page_type,
            "url": self.url,
            "url_pattern": self.url_pattern,
            "title": self.title,
            "heading": self.heading,
            "signature_hints": dict(self.signature_hints),
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class StateIndicator:
    name: str
    value: bool | str | int
    role: str
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "role": self.role,
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class InputSlot:
    name: str
    kind: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "required": self.required,
        }


@dataclass(frozen=True)
class GroundingPattern:
    locator_strategy: str
    locator_pattern: str | None = None
    target_selection_policy: str = "single"
    field_bindings: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "locator_strategy": self.locator_strategy,
            "locator_pattern": self.locator_pattern,
            "target_selection_policy": self.target_selection_policy,
            "field_bindings": dict(self.field_bindings),
        }


@dataclass(frozen=True)
class AvailabilityCondition:
    required_page_type: str
    required_state_indicators: dict[str, Any] = field(default_factory=dict)
    required_target_presence: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "required_page_type": self.required_page_type,
            "required_state_indicators": dict(self.required_state_indicators),
            "required_target_presence": self.required_target_presence,
        }


@dataclass(frozen=True)
class StateChangeHint:
    field: str
    before: Any
    after: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True)
class Capability:
    capability_id: str
    semantic_action: str
    action_kind: str
    target_type: str | None
    target_role: str | None
    grounding: GroundingPattern
    availability: AvailabilityCondition
    input_schema: list[InputSlot] = field(default_factory=list)
    expected_delta: list[StateChangeHint] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "semantic_action": self.semantic_action,
            "action_kind": self.action_kind,
            "target_type": self.target_type,
            "target_role": self.target_role,
            "input_schema": _list_to_dict(self.input_schema),
            "grounding": self.grounding.to_dict(),
            "availability": self.availability.to_dict(),
            "expected_delta": _list_to_dict(self.expected_delta),
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class ObservedDelta:
    field: str
    before: Any
    after: Any
    delta_type: str
    confidence: float = 1.0
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "before": self.before,
            "after": self.after,
            "delta_type": self.delta_type,
            "confidence": self.confidence,
            "evidence": _list_to_dict(self.evidence),
        }


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
        }


@dataclass(frozen=True)
class CapabilityTransition:
    transition_id: str
    source_state_id: str
    capability_id: str
    target_state_id: str
    transition_kind: str
    observed_delta: list[ObservedDelta]
    execution_trace: ExecutionTrace
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "source_state_id": self.source_state_id,
            "capability_id": self.capability_id,
            "target_state_id": self.target_state_id,
            "transition_kind": self.transition_kind,
            "observed_delta": _list_to_dict(self.observed_delta),
            "execution_trace": self.execution_trace.to_dict(),
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class SemanticPageState:
    state_id: str
    page_frame: PageFrame
    state_indicators: list[StateIndicator]
    capabilities: list[Capability]
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "page_frame": self.page_frame.to_dict(),
            "state_indicators": _list_to_dict(self.state_indicators),
            "capabilities": _list_to_dict(self.capabilities),
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class WebCapabilityGraph:
    app: str
    start_state: str
    total_steps_completed: int
    states: list[SemanticPageState]
    transitions: list[CapabilityTransition]

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": {
                "schema_version": SCHEMA_VERSION,
                "app": self.app,
                "start_state": self.start_state,
                "total_steps_completed": self.total_steps_completed,
            },
            "states": _list_to_dict(self.states),
            "transitions": _list_to_dict(self.transitions),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/safesym_bridge/test_capability_graph.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/capability_graph.py tests/safesym_bridge/test_capability_graph.py
git commit -m "feat: add web capability graph model"
```

---

### Task 2: Add SauceDemo capability graph builder

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/capability_builder.py`
- Test: `tests/safesym_bridge/test_capability_builder.py`

**Interfaces:**
- Consumes: `ObservedTransition` from `src/ai_web_explorer/safesym_bridge/models.py`
- Consumes: dataclasses from `capability_graph.py`
- Produces: `build_capability_graph(app: str, start_node: str, transitions: list[ObservedTransition]) -> WebCapabilityGraph`

- [ ] **Step 1: Write failing builder tests**

Create `tests/safesym_bridge/test_capability_builder.py`:

```python
import json

from ai_web_explorer.safesym_bridge.capability_builder import build_capability_graph
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions


def test_build_capability_graph_projects_saucedemo_checkout_path():
    graph = build_capability_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
    )
    data = graph.to_dict()

    assert data["meta"] == {
        "schema_version": "web-capability-graph-v1",
        "app": "saucedemo",
        "start_state": "login_ready",
        "total_steps_completed": 6,
    }

    states = {state["state_id"]: state for state in data["states"]}
    assert {
        "login_ready",
        "product_listing_cart_empty",
        "product_listing_cart_nonempty",
        "cart_nonempty",
        "checkout_form_incomplete",
        "checkout_form_complete",
        "checkout_review_ready",
        "confirmation_order_created",
    }.issubset(states)

    product_listing = states["product_listing_cart_empty"]
    assert product_listing["page_frame"]["page_type"] == "product_listing"
    assert product_listing["page_frame"]["page_id"] == "saucedemo:inventory"
    capability_ids = {
        capability["capability_id"]
        for capability in product_listing["capabilities"]
    }
    assert "add_to_cart_product" in capability_ids
    assert "open_cart" in capability_ids


def test_build_capability_graph_abstracts_product_instances():
    graph = build_capability_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
    )
    data_text = json.dumps(graph.to_dict(), ensure_ascii=False)

    assert "add_to_cart_product" in data_text
    assert "target_type" in data_text
    assert "product" in data_text
    assert "sauce_labs_backpack" not in data_text
    assert "29.99" not in data_text
    assert "Sauce Labs Backpack" not in data_text


def test_build_capability_graph_records_self_loop_state_delta():
    graph = build_capability_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
    )
    data = graph.to_dict()
    transitions = {
        transition["capability_id"]: transition
        for transition in data["transitions"]
    }

    add_to_cart = transitions["add_to_cart_product"]
    assert add_to_cart["source_state_id"] == "product_listing_cart_empty"
    assert add_to_cart["target_state_id"] == "product_listing_cart_nonempty"
    assert add_to_cart["transition_kind"] == "state_delta"
    assert add_to_cart["observed_delta"] == [
        {
            "field": "cart_nonempty",
            "before": False,
            "after": True,
            "delta_type": "state_indicator_change",
            "confidence": 1.0,
            "evidence": [
                {
                    "source": "transition_diff",
                    "selector": None,
                    "text_sample": None,
                    "url": "https://www.saucedemo.com/inventory.html",
                    "confidence": 1.0,
                }
            ],
        }
    ]


def test_build_capability_graph_records_navigation_transition():
    graph = build_capability_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
    )
    transitions = {
        transition.capability_id: transition
        for transition in graph.transitions
    }

    checkout = transitions["checkout_start"]
    assert checkout.transition_kind == "navigation"
    assert checkout.source_state_id == "cart_nonempty"
    assert checkout.target_state_id == "checkout_form_incomplete"
    assert checkout.observed_delta[0].field == "page_type"
    assert checkout.observed_delta[0].before == "cart"
    assert checkout.observed_delta[0].after == "checkout_form"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/safesym_bridge/test_capability_builder.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'ai_web_explorer.safesym_bridge.capability_builder'`.

- [ ] **Step 3: Implement deterministic SauceDemo projection**

Create `src/ai_web_explorer/safesym_bridge/capability_builder.py`:

```python
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from ai_web_explorer.safesym_bridge.capability_graph import (
    AvailabilityCondition,
    Capability,
    CapabilityTransition,
    Evidence,
    ExecutionTrace,
    GroundingPattern,
    InputSlot,
    ObservedDelta,
    PageFrame,
    SemanticPageState,
    StateChangeHint,
    StateIndicator,
    WebCapabilityGraph,
)
from ai_web_explorer.safesym_bridge.models import ObservedTransition, StateSnapshot
from ai_web_explorer.safesym_bridge.observed_graph import _url_pattern_for


PAGE_TYPES = {
    "login": "login",
    "inventory": "product_listing",
    "cart": "cart",
    "checkout_info": "checkout_form",
    "checkout_overview": "checkout_review",
    "checkout_complete": "confirmation",
}

HEADINGS = {
    "login": None,
    "inventory": "Products",
    "cart": "Your Cart",
    "checkout_info": "Checkout: Your Information",
    "checkout_overview": "Checkout: Overview",
    "checkout_complete": "Checkout: Complete!",
}


@dataclass(frozen=True)
class CapabilityRule:
    capability_id: str
    semantic_action: str
    action_kind: str
    target_type: str | None
    target_role: str | None
    grounding: GroundingPattern
    availability: AvailabilityCondition
    input_schema: tuple[InputSlot, ...] = ()


CAPABILITY_RULES = {
    "login_submit": CapabilityRule(
        capability_id="submit_login_form",
        semantic_action="login_submit",
        action_kind="composite",
        target_type="form",
        target_role="login_form",
        input_schema=(
            InputSlot("username", "text", required=True),
            InputSlot("password", "password", required=True),
        ),
        grounding=GroundingPattern(
            locator_strategy="form_fields",
            locator_pattern=None,
            target_selection_policy="single",
            field_bindings={
                "username": "#user-name",
                "password": "#password",
                "submit": "#login-button",
            },
        ),
        availability=AvailabilityCondition(required_page_type="login"),
    ),
    "product_add_to_cart": CapabilityRule(
        capability_id="add_to_cart_product",
        semantic_action="add_to_cart",
        action_kind="click",
        target_type="product",
        target_role="listed_item",
        grounding=GroundingPattern(
            locator_strategy="css_pattern",
            locator_pattern='button[data-test^="add-to-cart"]',
            target_selection_policy="first_available",
        ),
        availability=AvailabilityCondition(
            required_page_type="product_listing",
            required_target_presence="product",
        ),
    ),
    "cart_open": CapabilityRule(
        capability_id="open_cart",
        semantic_action="open_cart",
        action_kind="click",
        target_type="cart",
        target_role="global_nav",
        grounding=GroundingPattern(
            locator_strategy="css",
            locator_pattern=".shopping_cart_link",
            target_selection_policy="single",
        ),
        availability=AvailabilityCondition(required_page_type="product_listing"),
    ),
    "cart_checkout_start": CapabilityRule(
        capability_id="checkout_start",
        semantic_action="checkout_start",
        action_kind="click",
        target_type="cart",
        target_role="current_cart",
        grounding=GroundingPattern(
            locator_strategy="css",
            locator_pattern='button[data-test="checkout"]',
            target_selection_policy="single",
        ),
        availability=AvailabilityCondition(
            required_page_type="cart",
            required_state_indicators={"cart_nonempty": True},
        ),
    ),
    "checkout_info_submit": CapabilityRule(
        capability_id="submit_checkout_info",
        semantic_action="submit_checkout_info",
        action_kind="composite",
        target_type="form",
        target_role="checkout_info_form",
        input_schema=(
            InputSlot("first_name", "text", required=True),
            InputSlot("last_name", "text", required=True),
            InputSlot("postal_code", "text", required=True),
        ),
        grounding=GroundingPattern(
            locator_strategy="form_fields",
            locator_pattern=None,
            target_selection_policy="single",
            field_bindings={
                "first_name": "#first-name",
                "last_name": "#last-name",
                "postal_code": "#postal-code",
                "submit": "#continue",
            },
        ),
        availability=AvailabilityCondition(
            required_page_type="checkout_form",
            required_state_indicators={"checkout_info_complete": True},
        ),
    ),
    "order_place_confirm": CapabilityRule(
        capability_id="place_order",
        semantic_action="place_order",
        action_kind="click",
        target_type="order",
        target_role="pending_order",
        grounding=GroundingPattern(
            locator_strategy="css",
            locator_pattern='button[data-test="finish"]',
            target_selection_policy="single",
        ),
        availability=AvailabilityCondition(
            required_page_type="checkout_review",
            required_state_indicators={"order_review_ready": True},
        ),
    ),
}


def _page_type(page_id: str) -> str:
    return PAGE_TYPES.get(page_id, page_id)


def _indicator_values(snapshot: StateSnapshot) -> dict[str, bool | str | int]:
    signature = snapshot.signature
    values: dict[str, bool | str | int] = {}
    if "is_logged_in" in signature:
        values["logged_in"] = bool(signature["is_logged_in"])
    if "cart_count" in signature:
        values["cart_nonempty"] = int(signature["cart_count"]) > 0
    if "checkout_info_filled" in signature:
        values["checkout_info_complete"] = bool(signature["checkout_info_filled"])
    if "order_review_ready" in signature:
        values["order_review_ready"] = bool(signature["order_review_ready"])
    if "order_created" in signature:
        values["order_created"] = bool(signature["order_created"])
    if "username_filled" in signature and "password_filled" in signature:
        values["login_form_ready"] = bool(signature["username_filled"]) and bool(
            signature["password_filled"]
        )
    return values


def _state_id(snapshot: StateSnapshot) -> str:
    page_type = _page_type(snapshot.page_id)
    indicators = _indicator_values(snapshot)
    if page_type == "login":
        return "login_ready" if indicators.get("login_form_ready") else "login"
    if page_type == "product_listing":
        return (
            "product_listing_cart_nonempty"
            if indicators.get("cart_nonempty")
            else "product_listing_cart_empty"
        )
    if page_type == "cart":
        return "cart_nonempty" if indicators.get("cart_nonempty") else "cart_empty"
    if page_type == "checkout_form":
        return (
            "checkout_form_complete"
            if indicators.get("checkout_info_complete")
            else "checkout_form_incomplete"
        )
    if page_type == "checkout_review":
        return (
            "checkout_review_ready"
            if indicators.get("order_review_ready")
            else "checkout_review"
        )
    if page_type == "confirmation":
        return (
            "confirmation_order_created"
            if indicators.get("order_created")
            else "confirmation"
        )
    return page_type


def _evidence(source: str, snapshot: StateSnapshot, *, text_sample: str | None = None) -> Evidence:
    return Evidence(
        source=source,
        selector=None,
        text_sample=text_sample,
        url=snapshot.url,
        confidence=1.0,
    )


def _state_indicators(snapshot: StateSnapshot) -> list[StateIndicator]:
    evidence = [_evidence("state_signature", snapshot)]
    return [
        StateIndicator(name=name, value=value, role="planning_state", evidence=evidence)
        for name, value in sorted(_indicator_values(snapshot).items())
    ]


def _page_frame(snapshot: StateSnapshot) -> PageFrame:
    evidence = [_evidence("url", snapshot), _evidence("state_signature", snapshot)]
    indicators = _indicator_values(snapshot)
    return PageFrame(
        page_id=f"saucedemo:{snapshot.page_id}",
        page_type=_page_type(snapshot.page_id),
        url=snapshot.url,
        url_pattern=_url_pattern_for(snapshot.url),
        title=snapshot.title,
        heading=HEADINGS.get(snapshot.page_id),
        signature_hints=indicators,
        evidence=evidence,
    )


def _observed_delta(before: StateSnapshot, after: StateSnapshot) -> list[ObservedDelta]:
    deltas: list[ObservedDelta] = []
    before_page_type = _page_type(before.page_id)
    after_page_type = _page_type(after.page_id)
    if before_page_type != after_page_type:
        deltas.append(
            ObservedDelta(
                field="page_type",
                before=before_page_type,
                after=after_page_type,
                delta_type="page_frame_change",
                evidence=[_evidence("transition_diff", after)],
            )
        )
    before_values = _indicator_values(before)
    after_values = _indicator_values(after)
    for key in sorted(set(before_values) | set(after_values)):
        before_value = before_values.get(key)
        after_value = after_values.get(key)
        if before_value != after_value:
            deltas.append(
                ObservedDelta(
                    field=key,
                    before=before_value,
                    after=after_value,
                    delta_type="state_indicator_change",
                    evidence=[_evidence("transition_diff", after)],
                )
            )
    return deltas


def _transition_kind(before: StateSnapshot, after: StateSnapshot) -> str:
    if _page_type(before.page_id) != _page_type(after.page_id):
        return "navigation"
    return "state_delta"


def _capability_for_transition(transition: ObservedTransition) -> Capability:
    rule = CAPABILITY_RULES[transition.action.semantic_id]
    deltas = _observed_delta(transition.source, transition.target)
    return Capability(
        capability_id=rule.capability_id,
        semantic_action=rule.semantic_action,
        action_kind=rule.action_kind,
        target_type=rule.target_type,
        target_role=rule.target_role,
        input_schema=list(rule.input_schema),
        grounding=rule.grounding,
        availability=rule.availability,
        expected_delta=[
            StateChangeHint(delta.field, delta.before, delta.after)
            for delta in deltas
        ],
        evidence=[
            _evidence(
                "resolver_rule",
                transition.source,
                text_sample=transition.action.raw_description,
            )
        ],
    )


def build_capability_graph(
    *,
    app: str,
    start_node: str,
    transitions: list[ObservedTransition],
) -> WebCapabilityGraph:
    states_by_id: OrderedDict[str, StateSnapshot] = OrderedDict()
    capabilities_by_state: dict[str, OrderedDict[str, Capability]] = {}
    graph_transitions: list[CapabilityTransition] = []

    for transition in transitions:
        source_id = _state_id(transition.source)
        target_id = _state_id(transition.target)
        states_by_id.setdefault(source_id, transition.source)
        states_by_id.setdefault(target_id, transition.target)
        capability = _capability_for_transition(transition)
        capabilities_by_state.setdefault(source_id, OrderedDict())
        capabilities_by_state[source_id][capability.capability_id] = capability
        graph_transitions.append(
            CapabilityTransition(
                transition_id=f"{source_id}__{capability.capability_id}__{target_id}",
                source_state_id=source_id,
                capability_id=capability.capability_id,
                target_state_id=target_id,
                transition_kind=_transition_kind(transition.source, transition.target),
                observed_delta=_observed_delta(transition.source, transition.target),
                execution_trace=ExecutionTrace(
                    concrete_action_kind=capability.action_kind,
                    concrete_locator=capability.grounding.locator_pattern,
                    concrete_target_sample=capability.target_type,
                    input_values_used={},
                    before_observation_id=source_id,
                    after_observation_id=target_id,
                    success=True,
                    error=None,
                ),
                evidence=[
                    _evidence(
                        "observed_transition",
                        transition.source,
                        text_sample=transition.action.raw_description,
                    )
                ],
            )
        )

    states = [
        SemanticPageState(
            state_id=state_id,
            page_frame=_page_frame(snapshot),
            state_indicators=_state_indicators(snapshot),
            capabilities=list(capabilities_by_state.get(state_id, {}).values()),
            evidence=[_evidence("state_signature", snapshot)],
        )
        for state_id, snapshot in states_by_id.items()
    ]
    start_state = _state_id(transitions[0].source) if transitions else start_node
    return WebCapabilityGraph(
        app=app,
        start_state=start_state,
        total_steps_completed=len(transitions),
        states=states,
        transitions=graph_transitions,
    )
```

- [ ] **Step 4: Run builder tests**

Run:

```bash
pytest tests/safesym_bridge/test_capability_builder.py -v
```

Expected: PASS.

- [ ] **Step 5: Run model + builder tests together**

Run:

```bash
pytest tests/safesym_bridge/test_capability_graph.py tests/safesym_bridge/test_capability_builder.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/capability_builder.py tests/safesym_bridge/test_capability_builder.py
git commit -m "feat: build SauceDemo capability graph sidecar"
```

---

### Task 3: Add writer and browser-runner entry points

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Test: `tests/safesym_bridge/test_cli.py` in Task 4 covers the async runner monkeypatch path

**Interfaces:**
- Consumes: `build_capability_graph(app, start_node, transitions)`
- Produces: `write_capability_graph(transitions: list[ObservedTransition], output_path: Path) -> Path`
- Produces: `async run_saucedemo_explored_capability_graph(output_path: Path, *, headless: bool = True) -> Path`

- [ ] **Step 1: Add imports and writer**

Modify `src/ai_web_explorer/safesym_bridge/browser_runner.py`:

```python
from ai_web_explorer.safesym_bridge.capability_builder import build_capability_graph
```

Add after `write_observed_graph()`:

```python
def write_capability_graph(
    transitions: list[ObservedTransition],
    output_path: Path,
) -> Path:
    graph = build_capability_graph(
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

- [ ] **Step 2: Add explored sidecar runner**

Add to `src/ai_web_explorer/safesym_bridge/browser_runner.py` after `run_saucedemo_explored_graph()`:

```python
async def run_saucedemo_explored_capability_graph(
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
            result = await explorer.run(page)
            write_capability_graph(result.transitions, output_path)
            return output_path
        finally:
            await browser.close()
```

- [ ] **Step 3: Run focused import check**

Run:

```bash
python -c "from ai_web_explorer.safesym_bridge.browser_runner import write_capability_graph, run_saucedemo_explored_capability_graph; print(write_capability_graph.__name__, run_saucedemo_explored_capability_graph.__name__)"
```

Expected output:

```text
write_capability_graph run_saucedemo_explored_capability_graph
```

- [ ] **Step 4: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/browser_runner.py
git commit -m "feat: add capability graph browser runner"
```

---

### Task 4: Add CLI commands for fixed and explored capability graph output

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Modify: `tests/safesym_bridge/test_cli.py`

**Interfaces:**
- Consumes: `write_capability_graph()`
- Consumes: `run_saucedemo_explored_capability_graph()`
- Produces CLI command: `capability-graph --output <path>`
- Produces CLI command: `explore-capability-graph --output <path> [--headed]`

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/safesym_bridge/test_cli.py`:

```python

def test_main_capability_graph_subcommand_writes_capability_graph(tmp_path):
    output_path = tmp_path / "capability_graph.json"

    exit_code = main(["capability-graph", "--output", str(output_path)])

    assert exit_code == 0
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["meta"]["schema_version"] == "web-capability-graph-v1"
    assert data["meta"]["app"] == "saucedemo"
    assert "states" in data
    assert "transitions" in data


def test_main_explore_capability_graph_subcommand_runs_explorer(tmp_path, monkeypatch):
    output_path = tmp_path / "explored_capability_graph.json"
    calls = []

    async def fake_run_saucedemo_explored_capability_graph(path, *, headless=True):
        calls.append((path, headless))
        path.write_text(
            '{"meta": {"schema_version": "web-capability-graph-v1"}}',
            encoding="utf-8",
        )
        return path

    monkeypatch.setattr(
        cli,
        "run_saucedemo_explored_capability_graph",
        fake_run_saucedemo_explored_capability_graph,
    )

    exit_code = main(
        ["explore-capability-graph", "--output", str(output_path), "--headed"]
    )

    assert exit_code == 0
    assert calls == [(output_path, False)]
```

- [ ] **Step 2: Run CLI tests to verify new tests fail**

Run:

```bash
pytest tests/safesym_bridge/test_cli.py -v
```

Expected: FAIL because the new subcommands do not exist.

- [ ] **Step 3: Add imports**

Modify the import block in `src/ai_web_explorer/safesym_bridge/cli.py`:

```python
from ai_web_explorer.safesym_bridge.browser_runner import (
    run_saucedemo_explored_capability_graph,
    run_saucedemo_explored_graph,
    run_saucedemo_explored_pddl,
    write_capability_graph,
    write_observed_graph,
)
```

- [ ] **Step 4: Add fixed capability graph parser**

Add after the existing `graph_parser` block:

```python
    capability_graph_parser = subparsers.add_parser(
        "capability-graph",
        help="Experimental: write capability graph JSON from fixed MVP transitions.",
    )
    capability_graph_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/saucedemo_capability_graph.json"),
        help="Path to write the generated capability graph JSON.",
    )
```

- [ ] **Step 5: Add explored capability graph parser**

Add after the existing `explore_graph_parser` block:

```python
    explore_capability_graph_parser = subparsers.add_parser(
        "explore-capability-graph",
        help="Experimental: run browser exploration and write capability graph JSON.",
    )
    explore_capability_graph_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/saucedemo_explored_capability_graph.json"),
        help="Path to write the explored capability graph JSON.",
    )
    explore_capability_graph_parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window while running exploration.",
    )
```

- [ ] **Step 6: Add mode dispatch**

Modify the `try` block in `main()` so it includes these branches:

```python
        if args.mode == "explore-graph":
            output_path = asyncio.run(
                run_saucedemo_explored_graph(
                    args.output,
                    headless=not args.headed,
                )
            )
        elif args.mode == "explore-capability-graph":
            output_path = asyncio.run(
                run_saucedemo_explored_capability_graph(
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
        elif args.mode == "graph":
            output_path = write_observed_graph(
                build_saucedemo_mvp_transitions(),
                args.output,
            )
        elif args.mode == "capability-graph":
            output_path = write_capability_graph(
                build_saucedemo_mvp_transitions(),
                args.output,
            )
        elif args.mode == "pddl":
            output_path = write_saucedemo_pddl(args.output)
        else:
            parser.print_help()
            return 2
```

- [ ] **Step 7: Run CLI tests**

Run:

```bash
pytest tests/safesym_bridge/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 8: Run capability-related tests**

Run:

```bash
pytest tests/safesym_bridge/test_capability_graph.py tests/safesym_bridge/test_capability_builder.py tests/safesym_bridge/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/cli.py tests/safesym_bridge/test_cli.py
git commit -m "feat: expose capability graph CLI"
```

---

### Task 5: Document the experimental sidecar and run regression checks

**Files:**
- Modify: `docs/current-project-overview.md`

**Interfaces:**
- Consumes: CLI commands from Task 4
- Produces: documentation note for users

- [ ] **Step 1: Update current project overview**

In `docs/current-project-overview.md`, after the recommended CLI block, add:

````markdown
An experimental capability-graph sidecar is also available:

```bash
python -m ai_web_explorer.safesym_bridge.cli capability-graph --output outputs/saucedemo_capability_graph.json
python -m ai_web_explorer.safesym_bridge.cli explore-capability-graph --output outputs/saucedemo_explored_capability_graph.json
```

This sidecar does not replace `WebObservedGraph -> PDDL -> SafeSym`. It projects
the same observed transitions into a capability-first artifact that focuses on
semantic page states, abstract capabilities, and observed state deltas.
```
````

- [ ] **Step 2: Generate fixed capability graph artifact manually**

Run:

```bash
python -m ai_web_explorer.safesym_bridge.cli capability-graph --output outputs/saucedemo_capability_graph.json
```

Expected output:

```text
Wrote output to outputs\saucedemo_capability_graph.json
```

On non-Windows shells, the path separator may appear as `/`; the important part is that the command exits `0` and writes the JSON file.

- [ ] **Step 3: Inspect generated artifact for abstraction boundary**

Run:

```bash
python -c "import json; data=json.load(open('outputs/saucedemo_capability_graph.json', encoding='utf-8')); text=json.dumps(data); print(data['meta']['schema_version']); print('add_to_cart_product' in text); print('Sauce Labs Backpack' in text)"
```

Expected output:

```text
web-capability-graph-v1
True
False
```

- [ ] **Step 4: Run focused regression tests**

Run:

```bash
pytest tests/safesym_bridge/test_capability_graph.py tests/safesym_bridge/test_capability_builder.py tests/safesym_bridge/test_cli.py tests/safesym_bridge/test_observed_graph.py tests/safesym_bridge/test_pddl_compiler.py -v
```

Expected: PASS.

- [ ] **Step 5: Run full safesym bridge tests if focused tests pass**

Run:

```bash
pytest tests/safesym_bridge -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add docs/current-project-overview.md outputs/saucedemo_capability_graph.json
git commit -m "docs: document capability graph sidecar"
```

If generated outputs are intentionally ignored by git in this repository, use this commit instead:

```bash
git add docs/current-project-overview.md
git commit -m "docs: document capability graph sidecar"
```

---

## Self-Review

### Spec coverage

- Data model from `docs/web-capability-graph-design.md`: covered by Task 1.
- Capability-first SauceDemo projection: covered by Task 2.
- Abstract product target and no concrete product content: covered by Task 2 tests.
- Self-loop/state-delta support: covered by Task 2 tests.
- Sidecar output without replacing current pipeline: covered by Tasks 3 and 4.
- Documentation update: covered by Task 5.
- PDDL/SafeSym separation: preserved because no PDDL compiler or SafeSym code is modified.

### Placeholder scan

No task uses unspecified placeholder steps. Each code-writing step includes exact code or exact insertion text. Each verification step includes exact commands and expected results.

### Type consistency

- `build_capability_graph(app: str, start_node: str, transitions: list[ObservedTransition]) -> WebCapabilityGraph` is defined in Task 2 and consumed in Task 3.
- `write_capability_graph(transitions: list[ObservedTransition], output_path: Path) -> Path` is defined in Task 3 and consumed in Task 4.
- `run_saucedemo_explored_capability_graph(output_path: Path, *, headless: bool = True) -> Path` is defined in Task 3 and consumed in Task 4.
- Capability graph dataclass field names used in tests match Task 1 implementation.
