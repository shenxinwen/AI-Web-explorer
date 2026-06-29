# SafeSym Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a SauceDemo-focused bridge that exports a SafeSym-compatible FSM JSON with semantic actions, preconditions, and effects.

**Architecture:** Add an isolated `ai_web_explorer.safesym_bridge` package. Start with deterministic data models, action semantics, effect inference, FSM export, and validation; then add a CLI that can generate the target SauceDemo FSM without changing the existing exploration loop.

**Tech Stack:** Python 3.9+, dataclasses, stdlib `json`, `argparse`, `pytest`; optional downstream SafeSym validation through a user-provided SafeSym path.

## Global Constraints

- Keep the bridge isolated under `src/ai_web_explorer/safesym_bridge/`.
- Do not rewrite `src/ai_web_explorer/loop.py` for the MVP.
- First target site is SauceDemo only.
- First target task is login → add to cart → checkout → submit info → place order.
- First required safety action ID is exactly `order_place_confirm`.
- Use structured SafeSym effects: `{ "path": "...", "op": "set", "value": ... }`.
- Use structured SafeSym preconditions: `{ "path": "...", "cond": "...", "value": ... }`.
- Use TDD for implementation tasks: write failing tests first, then minimal code.
- Existing user worktree changes must be preserved.

---

## File structure

Create:

- `src/ai_web_explorer/safesym_bridge/__init__.py`  
  Public package marker and small exports.

- `src/ai_web_explorer/safesym_bridge/models.py`  
  Dataclasses for snapshots, actions, transitions, pages, and FSMs. Also JSON serialization helpers.

- `src/ai_web_explorer/safesym_bridge/action_semantics.py`  
  Maps raw UI intent strings to SafeSym action IDs.

- `src/ai_web_explorer/safesym_bridge/effect_inferer.py`  
  Computes deltas, effects, and rule-based preconditions.

- `src/ai_web_explorer/safesym_bridge/fsm_exporter.py`  
  Builds the target SafeSym FSM JSON from observed transitions.

- `src/ai_web_explorer/safesym_bridge/task_spec.py`  
  Holds the SauceDemo task spec and deterministic target transition sequence for the first MVP.

- `src/ai_web_explorer/safesym_bridge/validator.py`  
  Validates internal FSM consistency and optionally validates against SafeSym if a path is provided.

- `src/ai_web_explorer/safesym_bridge/cli.py`  
  CLI entry point for generating and validating the SauceDemo FSM.

Create tests:

- `tests/safesym_bridge/test_models.py`
- `tests/safesym_bridge/test_action_semantics.py`
- `tests/safesym_bridge/test_effect_inferer.py`
- `tests/safesym_bridge/test_fsm_exporter.py`
- `tests/safesym_bridge/test_validator.py`
- `tests/safesym_bridge/test_cli.py`

---

### Task 1: Data models and JSON serialization

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/__init__.py`
- Create: `src/ai_web_explorer/safesym_bridge/models.py`
- Test: `tests/safesym_bridge/test_models.py`

**Interfaces:**
- Produces:
  - `Condition = dict[str, object]`
  - `Effect = dict[str, object]`
  - `StateSnapshot(page_id: str, url: str, title: str, signature: dict[str, object])`
  - `ObservedAction(raw_description: str, semantic_id: str, playwright_calls: list[dict[str, object]])`
  - `ObservedTransition(source: StateSnapshot, target: StateSnapshot, action: ObservedAction, preconditions: list[Condition], effects: list[Effect])`
  - `SafeSymAction(id: str, name: str, from_page: str, to_page: str, is_navigation: bool, preconditions: list[Condition], effects: list[Effect])`
  - `SafeSymPage(id: str, signature_schema: dict[str, str], actions: list[SafeSymAction])`
  - `SafeSymFsm(app: str, initial_page_id: str, terminal_pages: list[str], pages: list[SafeSymPage])`
  - `SafeSymFsm.to_dict() -> dict[str, object]`

- [ ] **Step 1: Write failing model serialization tests**

Create `tests/safesym_bridge/test_models.py`:

```python
from ai_web_explorer.safesym_bridge.models import (
    SafeSymAction,
    SafeSymFsm,
    SafeSymPage,
    StateSnapshot,
)


def test_state_snapshot_stores_signature():
    snapshot = StateSnapshot(
        page_id="inventory",
        url="https://www.saucedemo.com/inventory.html",
        title="Swag Labs",
        signature={"$.cart_count": 1, "$.is_logged_in": True},
    )

    assert snapshot.page_id == "inventory"
    assert snapshot.signature["$.cart_count"] == 1
    assert snapshot.signature["$.is_logged_in"] is True


def test_safesym_fsm_to_dict_uses_expected_json_shape():
    action = SafeSymAction(
        id="order_place_confirm",
        name="order_place_confirm",
        from_page="checkout_overview",
        to_page="checkout_complete",
        is_navigation=True,
        preconditions=[
            {"path": "$.cart_count", "cond": "gt", "value": 0},
            {"path": "$.order_review_ready", "cond": "eq", "value": True},
        ],
        effects=[
            {"path": "$.order_created", "op": "set", "value": True},
        ],
    )
    page = SafeSymPage(
        id="checkout_overview",
        signature_schema={
            "$.cart_count": "number",
            "$.order_review_ready": "boolean",
            "$.order_created": "boolean",
        },
        actions=[action],
    )
    fsm = SafeSymFsm(
        app="saucedemo",
        initial_page_id="login",
        terminal_pages=["checkout_complete"],
        pages=[page],
    )

    assert fsm.to_dict() == {
        "meta": {
            "app": "saucedemo",
            "initial_page_id": "login",
            "terminal_pages": ["checkout_complete"],
        },
        "pages": [
            {
                "id": "checkout_overview",
                "signature_schema": {
                    "$.cart_count": "number",
                    "$.order_review_ready": "boolean",
                    "$.order_created": "boolean",
                },
                "actions": [
                    {
                        "id": "order_place_confirm",
                        "name": "order_place_confirm",
                        "from": "checkout_overview",
                        "to": "checkout_complete",
                        "is_navigation": True,
                        "preconditions": [
                            {"path": "$.cart_count", "cond": "gt", "value": 0},
                            {"path": "$.order_review_ready", "cond": "eq", "value": True},
                        ],
                        "effects": [
                            {"path": "$.order_created", "op": "set", "value": True},
                        ],
                    }
                ],
            }
        ],
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/safesym_bridge/test_models.py -v
```

Expected: FAIL with `ModuleNotFoundError` or missing model classes.

- [ ] **Step 3: Implement minimal models**

Create `src/ai_web_explorer/safesym_bridge/__init__.py`:

```python
"""SafeSym bridge for exporting web task observations as FSM JSON."""
```

Create `src/ai_web_explorer/safesym_bridge/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Condition = dict[str, Any]
Effect = dict[str, Any]


@dataclass(frozen=True)
class StateSnapshot:
    page_id: str
    url: str
    title: str
    signature: dict[str, Any]


@dataclass(frozen=True)
class ObservedAction:
    raw_description: str
    semantic_id: str
    playwright_calls: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ObservedTransition:
    source: StateSnapshot
    target: StateSnapshot
    action: ObservedAction
    preconditions: list[Condition] = field(default_factory=list)
    effects: list[Effect] = field(default_factory=list)


@dataclass(frozen=True)
class SafeSymAction:
    id: str
    name: str
    from_page: str
    to_page: str
    is_navigation: bool
    preconditions: list[Condition] = field(default_factory=list)
    effects: list[Effect] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "from": self.from_page,
            "to": self.to_page,
            "is_navigation": self.is_navigation,
            "preconditions": self.preconditions,
            "effects": self.effects,
        }


@dataclass(frozen=True)
class SafeSymPage:
    id: str
    signature_schema: dict[str, str]
    actions: list[SafeSymAction] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "signature_schema": self.signature_schema,
            "actions": [action.to_dict() for action in self.actions],
        }


@dataclass(frozen=True)
class SafeSymFsm:
    app: str
    initial_page_id: str
    terminal_pages: list[str]
    pages: list[SafeSymPage]

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": {
                "app": self.app,
                "initial_page_id": self.initial_page_id,
                "terminal_pages": self.terminal_pages,
            },
            "pages": [page.to_dict() for page in self.pages],
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/safesym_bridge/test_models.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/__init__.py src/ai_web_explorer/safesym_bridge/models.py tests/safesym_bridge/test_models.py
git commit -m "feat: add SafeSym bridge data models"
```

---

### Task 2: Action semantics mapping

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/action_semantics.py`
- Test: `tests/safesym_bridge/test_action_semantics.py`

**Interfaces:**
- Consumes: no bridge modules.
- Produces:
  - `semantic_id_for(raw_description: str) -> str`

- [ ] **Step 1: Write failing action semantics tests**

Create `tests/safesym_bridge/test_action_semantics.py`:

```python
import pytest

from ai_web_explorer.safesym_bridge.action_semantics import semantic_id_for


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Click the Login button", "login_submit"),
        ("click Add to cart for Sauce Labs Backpack", "product_add_to_cart"),
        ("Click the shopping cart link", "cart_open"),
        ("Click Checkout", "cart_checkout_start"),
        ("Click Continue on checkout information", "checkout_info_submit"),
        ("Click Finish", "order_place_confirm"),
    ],
)
def test_semantic_id_for_known_saucedemo_actions(raw, expected):
    assert semantic_id_for(raw) == expected


def test_semantic_id_for_unknown_action_returns_normalized_fallback():
    assert semantic_id_for("Open Product Details") == "open_product_details"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/safesym_bridge/test_action_semantics.py -v
```

Expected: FAIL with missing module or function.

- [ ] **Step 3: Implement semantics mapping**

Create `src/ai_web_explorer/safesym_bridge/action_semantics.py`:

```python
from __future__ import annotations

import re


def _normalize_fallback(raw_description: str) -> str:
    text = raw_description.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown_action"


def semantic_id_for(raw_description: str) -> str:
    text = raw_description.strip().lower()

    if "login" in text:
        return "login_submit"
    if "add to cart" in text:
        return "product_add_to_cart"
    if "shopping cart" in text or text in {"cart", "open cart", "click cart"}:
        return "cart_open"
    if "checkout" in text and "continue" not in text:
        return "cart_checkout_start"
    if "continue" in text and "checkout" in text:
        return "checkout_info_submit"
    if "finish" in text or "place order" in text or "confirm order" in text:
        return "order_place_confirm"

    return _normalize_fallback(raw_description)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/safesym_bridge/test_action_semantics.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/action_semantics.py tests/safesym_bridge/test_action_semantics.py
git commit -m "feat: map SauceDemo actions to SafeSym semantics"
```

---

### Task 3: Effect inference and precondition rules

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/effect_inferer.py`
- Test: `tests/safesym_bridge/test_effect_inferer.py`

**Interfaces:**
- Consumes:
  - `StateSnapshot` from `models.py`
- Produces:
  - `infer_effects(before: StateSnapshot, after: StateSnapshot) -> list[Effect]`
  - `preconditions_for(action_id: str) -> list[Condition]`

- [ ] **Step 1: Write failing effect inference tests**

Create `tests/safesym_bridge/test_effect_inferer.py`:

```python
from ai_web_explorer.safesym_bridge.effect_inferer import (
    infer_effects,
    preconditions_for,
)
from ai_web_explorer.safesym_bridge.models import StateSnapshot


def snapshot(page_id, signature):
    return StateSnapshot(
        page_id=page_id,
        url=f"https://www.saucedemo.com/{page_id}",
        title="Swag Labs",
        signature=signature,
    )


def test_infer_effects_returns_set_for_changed_values_only():
    before = snapshot(
        "inventory",
        {"$.is_logged_in": True, "$.cart_count": 0},
    )
    after = snapshot(
        "inventory",
        {"$.is_logged_in": True, "$.cart_count": 1},
    )

    assert infer_effects(before, after) == [
        {"path": "$.cart_count", "op": "set", "value": 1}
    ]


def test_infer_effects_sorts_paths_for_stable_json():
    before = snapshot("a", {"$.z": False, "$.a": False})
    after = snapshot("b", {"$.z": True, "$.a": True})

    assert infer_effects(before, after) == [
        {"path": "$.a", "op": "set", "value": True},
        {"path": "$.z", "op": "set", "value": True},
    ]


def test_preconditions_for_order_place_confirm():
    assert preconditions_for("order_place_confirm") == [
        {"path": "$.cart_count", "cond": "gt", "value": 0},
        {"path": "$.order_review_ready", "cond": "eq", "value": True},
    ]


def test_preconditions_for_unknown_action_are_empty():
    assert preconditions_for("open_product_details") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/safesym_bridge/test_effect_inferer.py -v
```

Expected: FAIL with missing module or function.

- [ ] **Step 3: Implement effect inference**

Create `src/ai_web_explorer/safesym_bridge/effect_inferer.py`:

```python
from __future__ import annotations

from ai_web_explorer.safesym_bridge.models import Condition, Effect, StateSnapshot

_PRECONDITIONS: dict[str, list[Condition]] = {
    "login_submit": [
        {"path": "$.username_filled", "cond": "eq", "value": True},
        {"path": "$.password_filled", "cond": "eq", "value": True},
    ],
    "product_add_to_cart": [
        {"path": "$.is_logged_in", "cond": "eq", "value": True},
    ],
    "cart_checkout_start": [
        {"path": "$.cart_count", "cond": "gt", "value": 0},
    ],
    "checkout_info_submit": [
        {"path": "$.checkout_info_filled", "cond": "eq", "value": True},
    ],
    "order_place_confirm": [
        {"path": "$.cart_count", "cond": "gt", "value": 0},
        {"path": "$.order_review_ready", "cond": "eq", "value": True},
    ],
}


def infer_effects(before: StateSnapshot, after: StateSnapshot) -> list[Effect]:
    effects: list[Effect] = []
    paths = sorted(set(before.signature) | set(after.signature))
    for path in paths:
        before_value = before.signature.get(path)
        after_value = after.signature.get(path)
        if before_value != after_value:
            effects.append({"path": path, "op": "set", "value": after_value})
    return effects


def preconditions_for(action_id: str) -> list[Condition]:
    return [dict(condition) for condition in _PRECONDITIONS.get(action_id, [])]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/safesym_bridge/test_effect_inferer.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/effect_inferer.py tests/safesym_bridge/test_effect_inferer.py
git commit -m "feat: infer SafeSym effects and preconditions"
```

---

### Task 4: FSM exporter

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/fsm_exporter.py`
- Test: `tests/safesym_bridge/test_fsm_exporter.py`

**Interfaces:**
- Consumes:
  - `ObservedTransition`, `SafeSymFsm` from `models.py`
- Produces:
  - `schema_type_for(value: object) -> str`
  - `build_fsm(app: str, initial_page_id: str, terminal_pages: list[str], transitions: list[ObservedTransition]) -> SafeSymFsm`

- [ ] **Step 1: Write failing FSM exporter tests**

Create `tests/safesym_bridge/test_fsm_exporter.py`:

```python
from ai_web_explorer.safesym_bridge.fsm_exporter import build_fsm, schema_type_for
from ai_web_explorer.safesym_bridge.models import (
    ObservedAction,
    ObservedTransition,
    StateSnapshot,
)


def snapshot(page_id, signature):
    return StateSnapshot(
        page_id=page_id,
        url=f"https://www.saucedemo.com/{page_id}",
        title="Swag Labs",
        signature=signature,
    )


def test_schema_type_for_basic_json_values():
    assert schema_type_for(True) == "boolean"
    assert schema_type_for(1) == "number"
    assert schema_type_for("abc") == "string"
    assert schema_type_for(None) == "string"


def test_build_fsm_groups_actions_under_source_pages():
    transition = ObservedTransition(
        source=snapshot(
            "checkout_overview",
            {"$.cart_count": 1, "$.order_review_ready": True},
        ),
        target=snapshot(
            "checkout_complete",
            {"$.cart_count": 1, "$.order_review_ready": True, "$.order_created": True},
        ),
        action=ObservedAction(
            raw_description="Click Finish",
            semantic_id="order_place_confirm",
            playwright_calls=[],
        ),
        preconditions=[
            {"path": "$.cart_count", "cond": "gt", "value": 0},
            {"path": "$.order_review_ready", "cond": "eq", "value": True},
        ],
        effects=[
            {"path": "$.order_created", "op": "set", "value": True},
        ],
    )

    fsm = build_fsm(
        app="saucedemo",
        initial_page_id="login",
        terminal_pages=["checkout_complete"],
        transitions=[transition],
    )

    assert fsm.to_dict() == {
        "meta": {
            "app": "saucedemo",
            "initial_page_id": "login",
            "terminal_pages": ["checkout_complete"],
        },
        "pages": [
            {
                "id": "checkout_complete",
                "signature_schema": {
                    "$.cart_count": "number",
                    "$.order_created": "boolean",
                    "$.order_review_ready": "boolean",
                },
                "actions": [],
            },
            {
                "id": "checkout_overview",
                "signature_schema": {
                    "$.cart_count": "number",
                    "$.order_created": "boolean",
                    "$.order_review_ready": "boolean",
                },
                "actions": [
                    {
                        "id": "order_place_confirm",
                        "name": "order_place_confirm",
                        "from": "checkout_overview",
                        "to": "checkout_complete",
                        "is_navigation": True,
                        "preconditions": [
                            {"path": "$.cart_count", "cond": "gt", "value": 0},
                            {"path": "$.order_review_ready", "cond": "eq", "value": True},
                        ],
                        "effects": [
                            {"path": "$.order_created", "op": "set", "value": True},
                        ],
                    }
                ],
            },
        ],
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/safesym_bridge/test_fsm_exporter.py -v
```

Expected: FAIL with missing module or function.

- [ ] **Step 3: Implement FSM exporter**

Create `src/ai_web_explorer/safesym_bridge/fsm_exporter.py`:

```python
from __future__ import annotations

from collections import defaultdict
from typing import Any

from ai_web_explorer.safesym_bridge.models import (
    ObservedTransition,
    SafeSymAction,
    SafeSymFsm,
    SafeSymPage,
)


def schema_type_for(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    return "string"


def _collect_page_schemas(
    transitions: list[ObservedTransition],
) -> dict[str, dict[str, str]]:
    schemas: dict[str, dict[str, str]] = defaultdict(dict)
    page_ids = set()
    for transition in transitions:
        page_ids.add(transition.source.page_id)
        page_ids.add(transition.target.page_id)
        for snapshot in (transition.source, transition.target):
            for path, value in snapshot.signature.items():
                schemas[snapshot.page_id][path] = schema_type_for(value)
        for effect in transition.effects:
            path = str(effect["path"])
            value = effect.get("value")
            schemas[transition.source.page_id][path] = schema_type_for(value)
            schemas[transition.target.page_id][path] = schema_type_for(value)

    for page_id in page_ids:
        schemas.setdefault(page_id, {})

    return {page_id: dict(sorted(schema.items())) for page_id, schema in schemas.items()}


def build_fsm(
    app: str,
    initial_page_id: str,
    terminal_pages: list[str],
    transitions: list[ObservedTransition],
) -> SafeSymFsm:
    schemas = _collect_page_schemas(transitions)
    actions_by_page: dict[str, list[SafeSymAction]] = defaultdict(list)

    for transition in transitions:
        action_id = transition.action.semantic_id
        actions_by_page[transition.source.page_id].append(
            SafeSymAction(
                id=action_id,
                name=action_id,
                from_page=transition.source.page_id,
                to_page=transition.target.page_id,
                is_navigation=transition.source.page_id != transition.target.page_id,
                preconditions=transition.preconditions,
                effects=transition.effects,
            )
        )

    pages = [
        SafeSymPage(
            id=page_id,
            signature_schema=schemas[page_id],
            actions=actions_by_page.get(page_id, []),
        )
        for page_id in sorted(schemas)
    ]

    return SafeSymFsm(
        app=app,
        initial_page_id=initial_page_id,
        terminal_pages=terminal_pages,
        pages=pages,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/safesym_bridge/test_fsm_exporter.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/fsm_exporter.py tests/safesym_bridge/test_fsm_exporter.py
git commit -m "feat: export observed transitions as SafeSym FSM"
```

---

### Task 5: SauceDemo task spec and deterministic MVP transitions

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/task_spec.py`
- Test: extend `tests/safesym_bridge/test_fsm_exporter.py`

**Interfaces:**
- Consumes:
  - `semantic_id_for(raw_description: str) -> str`
  - `infer_effects(before, after) -> list[Effect]`
  - `preconditions_for(action_id: str) -> list[Condition]`
  - `ObservedAction`, `ObservedTransition`, `StateSnapshot`
- Produces:
  - `SAUCEDEMO_TASK: dict[str, object]`
  - `build_saucedemo_mvp_transitions() -> list[ObservedTransition]`

- [ ] **Step 1: Write failing SauceDemo transition test**

Append to `tests/safesym_bridge/test_fsm_exporter.py`:

```python
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions


def test_saucedemo_mvp_transitions_export_target_actions():
    transitions = build_saucedemo_mvp_transitions()
    fsm = build_fsm(
        app="saucedemo",
        initial_page_id="login",
        terminal_pages=["checkout_complete"],
        transitions=transitions,
    )
    data = fsm.to_dict()

    actions = [
        action
        for page in data["pages"]
        for action in page["actions"]
    ]
    action_ids = [action["id"] for action in actions]

    assert action_ids == [
        "login_submit",
        "product_add_to_cart",
        "cart_open",
        "cart_checkout_start",
        "checkout_info_submit",
        "order_place_confirm",
    ]

    add_to_cart = next(action for action in actions if action["id"] == "product_add_to_cart")
    assert add_to_cart["from"] == "inventory"
    assert add_to_cart["to"] == "inventory"
    assert add_to_cart["is_navigation"] is False
    assert add_to_cart["effects"] == [
        {"path": "$.cart_count", "op": "set", "value": 1}
    ]

    order_confirm = next(action for action in actions if action["id"] == "order_place_confirm")
    assert order_confirm["preconditions"] == [
        {"path": "$.cart_count", "cond": "gt", "value": 0},
        {"path": "$.order_review_ready", "cond": "eq", "value": True},
    ]
    assert order_confirm["effects"] == [
        {"path": "$.order_created", "op": "set", "value": True}
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/safesym_bridge/test_fsm_exporter.py::test_saucedemo_mvp_transitions_export_target_actions -v
```

Expected: FAIL with missing `task_spec`.

- [ ] **Step 3: Implement SauceDemo task transitions**

Create `src/ai_web_explorer/safesym_bridge/task_spec.py`:

```python
from __future__ import annotations

from ai_web_explorer.safesym_bridge.action_semantics import semantic_id_for
from ai_web_explorer.safesym_bridge.effect_inferer import (
    infer_effects,
    preconditions_for,
)
from ai_web_explorer.safesym_bridge.models import (
    ObservedAction,
    ObservedTransition,
    StateSnapshot,
)

SAUCEDEMO_TASK: dict[str, object] = {
    "app": "saucedemo",
    "start_url": "https://www.saucedemo.com/",
    "goal": "complete_checkout",
    "credentials": {
        "username": "standard_user",
        "password": "secret_sauce",
    },
}


def _snapshot(page_id: str, signature: dict[str, object]) -> StateSnapshot:
    url_by_page = {
        "login": "https://www.saucedemo.com/",
        "inventory": "https://www.saucedemo.com/inventory.html",
        "cart": "https://www.saucedemo.com/cart.html",
        "checkout_info": "https://www.saucedemo.com/checkout-step-one.html",
        "checkout_overview": "https://www.saucedemo.com/checkout-step-two.html",
        "checkout_complete": "https://www.saucedemo.com/checkout-complete.html",
    }
    return StateSnapshot(
        page_id=page_id,
        url=url_by_page[page_id],
        title="Swag Labs",
        signature=signature,
    )


def _transition(
    before: StateSnapshot,
    after: StateSnapshot,
    raw_description: str,
) -> ObservedTransition:
    action_id = semantic_id_for(raw_description)
    return ObservedTransition(
        source=before,
        target=after,
        action=ObservedAction(
            raw_description=raw_description,
            semantic_id=action_id,
            playwright_calls=[],
        ),
        preconditions=preconditions_for(action_id),
        effects=infer_effects(before, after),
    )


def build_saucedemo_mvp_transitions() -> list[ObservedTransition]:
    login_ready = _snapshot(
        "login",
        {
            "$.username_filled": True,
            "$.password_filled": True,
            "$.is_logged_in": False,
            "$.cart_count": 0,
        },
    )
    inventory_empty = _snapshot(
        "inventory",
        {
            "$.username_filled": True,
            "$.password_filled": True,
            "$.is_logged_in": True,
            "$.cart_count": 0,
        },
    )
    inventory_with_cart = _snapshot(
        "inventory",
        {
            "$.is_logged_in": True,
            "$.cart_count": 1,
        },
    )
    cart = _snapshot(
        "cart",
        {
            "$.is_logged_in": True,
            "$.cart_count": 1,
        },
    )
    checkout_info = _snapshot(
        "checkout_info",
        {
            "$.cart_count": 1,
            "$.checkout_started": True,
            "$.checkout_info_filled": False,
        },
    )
    checkout_info_filled = _snapshot(
        "checkout_info",
        {
            "$.cart_count": 1,
            "$.checkout_started": True,
            "$.checkout_info_filled": True,
        },
    )
    checkout_overview = _snapshot(
        "checkout_overview",
        {
            "$.cart_count": 1,
            "$.checkout_started": True,
            "$.checkout_info_filled": True,
            "$.order_review_ready": True,
            "$.order_created": False,
        },
    )
    checkout_complete = _snapshot(
        "checkout_complete",
        {
            "$.cart_count": 1,
            "$.order_review_ready": True,
            "$.order_created": True,
        },
    )

    return [
        _transition(login_ready, inventory_empty, "Click the Login button"),
        _transition(inventory_empty, inventory_with_cart, "Click Add to cart"),
        _transition(inventory_with_cart, cart, "Click the shopping cart link"),
        _transition(cart, checkout_info, "Click Checkout"),
        _transition(checkout_info_filled, checkout_overview, "Click Continue on checkout information"),
        _transition(checkout_overview, checkout_complete, "Click Finish"),
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/safesym_bridge/test_fsm_exporter.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/task_spec.py tests/safesym_bridge/test_fsm_exporter.py
git commit -m "feat: define SauceDemo MVP FSM transitions"
```

---

### Task 6: FSM validator

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/validator.py`
- Test: `tests/safesym_bridge/test_validator.py`

**Interfaces:**
- Consumes:
  - `SafeSymFsm`
- Produces:
  - `ValidationResult(ok: bool, errors: list[str])`
  - `validate_fsm(fsm: SafeSymFsm) -> ValidationResult`

- [ ] **Step 1: Write failing validator tests**

Create `tests/safesym_bridge/test_validator.py`:

```python
from ai_web_explorer.safesym_bridge.fsm_exporter import build_fsm
from ai_web_explorer.safesym_bridge.models import SafeSymAction, SafeSymFsm, SafeSymPage
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions
from ai_web_explorer.safesym_bridge.validator import validate_fsm


def test_validate_saucedemo_mvp_fsm_passes():
    fsm = build_fsm(
        app="saucedemo",
        initial_page_id="login",
        terminal_pages=["checkout_complete"],
        transitions=build_saucedemo_mvp_transitions(),
    )

    result = validate_fsm(fsm)

    assert result.ok is True
    assert result.errors == []


def test_validate_fsm_reports_broken_action_target():
    fsm = SafeSymFsm(
        app="saucedemo",
        initial_page_id="login",
        terminal_pages=["checkout_complete"],
        pages=[
            SafeSymPage(
                id="login",
                signature_schema={"$.username_filled": "boolean"},
                actions=[
                    SafeSymAction(
                        id="login_submit",
                        name="login_submit",
                        from_page="login",
                        to_page="missing_page",
                        is_navigation=True,
                        preconditions=[],
                        effects=[],
                    )
                ],
            )
        ],
    )

    result = validate_fsm(fsm)

    assert result.ok is False
    assert "action login_submit points to unknown to page missing_page" in result.errors
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/safesym_bridge/test_validator.py -v
```

Expected: FAIL with missing module or function.

- [ ] **Step 3: Implement validator**

Create `src/ai_web_explorer/safesym_bridge/validator.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from ai_web_explorer.safesym_bridge.models import SafeSymFsm


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: list[str]


def validate_fsm(fsm: SafeSymFsm) -> ValidationResult:
    errors: list[str] = []

    if not fsm.app:
        errors.append("meta.app is required")
    if not fsm.initial_page_id:
        errors.append("meta.initial_page_id is required")
    if not fsm.pages:
        errors.append("pages must not be empty")

    page_ids = {page.id for page in fsm.pages}
    if fsm.initial_page_id and fsm.initial_page_id not in page_ids:
        errors.append(f"initial_page_id {fsm.initial_page_id} is not a page")

    all_action_ids: list[str] = []
    known_schema_paths = {
        path
        for page in fsm.pages
        for path in page.signature_schema
    }

    for page in fsm.pages:
        if not page.id:
            errors.append("page id is required")
        if not page.signature_schema:
            errors.append(f"page {page.id} signature_schema must not be empty")

        for action in page.actions:
            all_action_ids.append(action.id)
            if not action.id:
                errors.append(f"action on page {page.id} is missing id")
            if not action.name:
                errors.append(f"action {action.id} is missing name")
            if action.from_page not in page_ids:
                errors.append(f"action {action.id} points to unknown from page {action.from_page}")
            if action.to_page not in page_ids:
                errors.append(f"action {action.id} points to unknown to page {action.to_page}")
            for effect in action.effects:
                path = str(effect.get("path", ""))
                if path not in known_schema_paths:
                    errors.append(f"action {action.id} effect path {path} is not in signature_schema")

    if "order_place_confirm" not in all_action_ids:
        errors.append("required action order_place_confirm is missing")

    return ValidationResult(ok=not errors, errors=errors)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/safesym_bridge/test_validator.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/validator.py tests/safesym_bridge/test_validator.py
git commit -m "feat: validate SafeSym bridge FSM output"
```

---

### Task 7: CLI to generate SauceDemo FSM JSON

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/cli.py`
- Test: `tests/safesym_bridge/test_cli.py`

**Interfaces:**
- Consumes:
  - `build_saucedemo_mvp_transitions()`
  - `build_fsm(...)`
  - `validate_fsm(fsm)`
- Produces:
  - `build_saucedemo_fsm() -> SafeSymFsm`
  - `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/safesym_bridge/test_cli.py`:

```python
import json

from ai_web_explorer.safesym_bridge.cli import build_saucedemo_fsm, main


def test_build_saucedemo_fsm_contains_required_order_action():
    fsm = build_saucedemo_fsm()
    data = fsm.to_dict()
    actions = [
        action
        for page in data["pages"]
        for action in page["actions"]
    ]

    assert any(action["id"] == "order_place_confirm" for action in actions)


def test_main_writes_json_file(tmp_path):
    output_path = tmp_path / "saucedemo_fsm.json"

    exit_code = main(["--output", str(output_path)])

    assert exit_code == 0
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["meta"]["app"] == "saucedemo"
    assert data["meta"]["initial_page_id"] == "login"
    assert data["meta"]["terminal_pages"] == ["checkout_complete"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/safesym_bridge/test_cli.py -v
```

Expected: FAIL with missing module or function.

- [ ] **Step 3: Implement CLI**

Create `src/ai_web_explorer/safesym_bridge/cli.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_web_explorer.safesym_bridge.fsm_exporter import build_fsm
from ai_web_explorer.safesym_bridge.models import SafeSymFsm
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions
from ai_web_explorer.safesym_bridge.validator import validate_fsm


def build_saucedemo_fsm() -> SafeSymFsm:
    return build_fsm(
        app="saucedemo",
        initial_page_id="login",
        terminal_pages=["checkout_complete"],
        transitions=build_saucedemo_mvp_transitions(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a SafeSym FSM for SauceDemo.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/saucedemo_fsm.json"),
        help="Path to write the generated FSM JSON.",
    )
    args = parser.parse_args(argv)

    fsm = build_saucedemo_fsm()
    validation = validate_fsm(fsm)
    if not validation.ok:
        for error in validation.errors:
            print(f"ERROR: {error}")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(fsm.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote SafeSym FSM to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/safesym_bridge/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Run all bridge tests**

Run:

```bash
pytest tests/safesym_bridge -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/cli.py tests/safesym_bridge/test_cli.py
git commit -m "feat: add SauceDemo SafeSym FSM CLI"
```

---

### Task 8: Optional SafeSym loader smoke validation

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/validator.py`
- Test: extend `tests/safesym_bridge/test_validator.py`

**Interfaces:**
- Consumes:
  - generated FSM JSON path
- Produces:
  - `validate_with_safesym_loader(fsm_path: str, safesym_root: str) -> ValidationResult`

- [ ] **Step 1: Write failing SafeSym loader validation tests**

Append to `tests/safesym_bridge/test_validator.py`:

```python
from ai_web_explorer.safesym_bridge.validator import validate_with_safesym_loader


def test_validate_with_safesym_loader_reports_missing_root(tmp_path):
    fsm_path = tmp_path / "fsm.json"
    fsm_path.write_text("{}", encoding="utf-8")

    result = validate_with_safesym_loader(
        fsm_path=str(fsm_path),
        safesym_root=str(tmp_path / "missing_safesym"),
    )

    assert result.ok is False
    assert result.errors == ["SafeSym root does not exist"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/safesym_bridge/test_validator.py::test_validate_with_safesym_loader_reports_missing_root -v
```

Expected: FAIL with missing `validate_with_safesym_loader`.

- [ ] **Step 3: Implement safe optional loader hook**

Append to `src/ai_web_explorer/safesym_bridge/validator.py`:

```python
import importlib
import sys
from pathlib import Path


def validate_with_safesym_loader(fsm_path: str, safesym_root: str) -> ValidationResult:
    root = Path(safesym_root)
    if not root.exists():
        return ValidationResult(ok=False, errors=["SafeSym root does not exist"])

    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    try:
        loader = importlib.import_module("safeww.fsm.loader")
    except Exception as exc:
        return ValidationResult(ok=False, errors=[f"could not import SafeSym loader: {exc}"])

    try:
        if hasattr(loader, "FsmDocument"):
            loader.FsmDocument.from_path(fsm_path)
        else:
            return ValidationResult(ok=False, errors=["SafeSym loader has no FsmDocument"])
    except Exception as exc:
        return ValidationResult(ok=False, errors=[f"SafeSym loader rejected FSM: {exc}"])

    return ValidationResult(ok=True, errors=[])
```

- [ ] **Step 4: Run validator tests**

Run:

```bash
pytest tests/safesym_bridge/test_validator.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/validator.py tests/safesym_bridge/test_validator.py
git commit -m "feat: add optional SafeSym loader validation"
```

---

### Task 9: Documentation and final verification

**Files:**
- Create: `docs/safesym-bridge.md`

**Interfaces:**
- Consumes:
  - CLI from Task 7
  - optional SafeSym loader validation from Task 8
- Produces:
  - user-facing instructions for generating the MVP FSM

- [ ] **Step 1: Create user-facing documentation**

Create `docs/safesym-bridge.md`:

```markdown
# SafeSym Bridge

This bridge generates a SafeSym-compatible FSM JSON for the SauceDemo checkout task.

The MVP target path is:

```text
login → inventory → cart → checkout_info → checkout_overview → checkout_complete
```

The most important safety action is:

```text
order_place_confirm
```

That action means the user confirmed the order. Its preconditions include:

- `$.cart_count > 0`
- `$.order_review_ready = true`

Its effect is:

- `$.order_created = true`

## Generate the FSM

Run from the repository root:

```bash
python -m ai_web_explorer.safesym_bridge.cli --output outputs/saucedemo_fsm.json
```

Expected result:

```text
Wrote SafeSym FSM to outputs/saucedemo_fsm.json
```

## Run bridge tests

```bash
pytest tests/safesym_bridge -v
```

Expected result:

```text
all tests pass
```

## SafeSym validation boundary

The MVP is successful when:

1. the generated JSON passes bridge validation;
2. SafeSym can load the FSM;
3. SafeSym can generate PDDL from the FSM;
4. SafeSym safety rules identify `order_place_confirm` as a financial/property-risk action.
```

- [ ] **Step 2: Run all bridge tests**

Run:

```bash
pytest tests/safesym_bridge -v
```

Expected: PASS.

- [ ] **Step 3: Generate the sample FSM**

Run:

```bash
python -m ai_web_explorer.safesym_bridge.cli --output outputs/saucedemo_fsm.json
```

Expected:

```text
Wrote SafeSym FSM to outputs/saucedemo_fsm.json
```

- [ ] **Step 4: Inspect generated JSON for the safety action**

Run:

```bash
python -c "import json; data=json.load(open('outputs/saucedemo_fsm.json', encoding='utf-8')); print([a['id'] for p in data['pages'] for a in p['actions']])"
```

Expected output includes:

```text
order_place_confirm
```

- [ ] **Step 5: Commit**

```bash
git add docs/safesym-bridge.md outputs/saucedemo_fsm.json
git commit -m "docs: document SafeSym bridge MVP"
```

---

## Self-review checklist

- Spec coverage: Tasks 1–7 implement the bridge package, target SauceDemo FSM, semantic action IDs, preconditions, effects, JSON export, and internal validation. Task 8 covers optional SafeSym loader validation. Task 9 covers user-facing docs and final sample generation.
- Type consistency: `StateSnapshot`, `ObservedAction`, `ObservedTransition`, `SafeSymAction`, `SafeSymPage`, and `SafeSymFsm` are introduced in Task 1 and reused with the same names and fields in later tasks.
- Scope control: The plan intentionally does not modify the main exploration loop or implement arbitrary website exploration.
- Safety target: `order_place_confirm` is created in Task 2, used in Task 5, validated in Task 6, and documented in Task 9.
