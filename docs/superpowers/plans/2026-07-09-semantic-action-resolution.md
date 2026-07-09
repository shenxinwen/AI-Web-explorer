# Semantic Action Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Execute with one agent unless the user explicitly permits subagents.

**Goal:** Separate SauceDemo DOM semantic recognition from action execution configuration while preserving the existing graph-to-PDDL-to-SafeSym behavior.

**Architecture:** A resolver converts normalized DOM candidates into small `SemanticMatch` records. A domain action catalog combines those matches with candidate locators and deterministic execution definitions to build the existing `ExplorationAction` objects; `SauceDemoAdapter` coordinates both layers.

**Tech Stack:** Python 3, dataclasses, typing Protocol, pytest, AnyIO, Playwright

## Global Constraints

- Do not install WebArena or add Reddit support in this milestone.
- Do not call an LLM or VLM.
- Do not change `WebObservedGraph`, `GraphExplorer`, or PDDL models.
- Preserve the SauceDemo semantic action IDs and action order.
- Keep unmatched candidates observable and do not execute low-confidence matches.
- Use test-driven development and commit after every independently passing task.

---

## File Structure

**Create:**

- `src/ai_web_explorer/safesym_bridge/semantic_resolver.py`: resolver contracts and result models.
- `src/ai_web_explorer/safesym_bridge/saucedemo_resolver.py`: SauceDemo-only candidate matching.
- `src/ai_web_explorer/safesym_bridge/action_catalog.py`: generic action-definition and action-building logic.
- `src/ai_web_explorer/safesym_bridge/saucedemo_catalog.py`: SauceDemo execution definitions and priorities.
- `tests/safesym_bridge/test_semantic_resolver.py`: contract validation.
- `tests/safesym_bridge/test_saucedemo_resolver.py`: semantic matching tests.
- `tests/safesym_bridge/test_action_catalog.py`: generic catalog behavior tests.
- `tests/safesym_bridge/test_saucedemo_catalog.py`: SauceDemo action construction tests.

**Modify:**

- `src/ai_web_explorer/safesym_bridge/saucedemo_adapter.py`: coordinate observer, resolver, and catalog; remove the combined mapping function.
- `tests/safesym_bridge/test_saucedemo_adapter.py`: replace direct mapping tests with adapter integration tests.

Existing candidate cleaning in `dom_observer.py` remains the normalization
boundary for this milestone. Do not introduce an empty `CandidateNormalizer`
wrapper until a second website demonstrates additional normalization needs.

---

### Task 1: Semantic Resolver Contracts

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/semantic_resolver.py`
- Create: `tests/safesym_bridge/test_semantic_resolver.py`

**Interfaces:**
- Consumes: `StateSnapshot` and `list[DomInteractableCandidate]`.
- Produces: `SemanticMatch`, `ResolutionBatch`, and `SemanticActionResolver.resolve(state, candidates)`.

- [ ] **Step 1: Write the failing contract tests**

```python
from dataclasses import FrozenInstanceError

import pytest

from ai_web_explorer.safesym_bridge.semantic_resolver import (
    ResolutionBatch,
    SemanticMatch,
)


def test_semantic_match_is_immutable_and_contains_no_execution_data():
    match = SemanticMatch(
        candidate_id="dom_001",
        semantic_id="login_submit",
        confidence=1.0,
        resolver="saucedemo_rule",
    )

    assert match.candidate_id == "dom_001"
    assert not hasattr(match, "selector")
    assert not hasattr(match, "values")
    with pytest.raises(FrozenInstanceError):
        match.confidence = 0.5


def test_resolution_batch_reports_unmatched_candidates():
    match = SemanticMatch("dom_001", "login_submit", 1.0, "saucedemo_rule")
    batch = ResolutionBatch(
        matches=[match],
        unmatched_candidate_ids=["dom_002"],
    )

    assert batch.matches == [match]
    assert batch.unmatched_candidate_ids == ["dom_002"]
```

- [ ] **Step 2: Run the tests and verify the missing-module failure**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_semantic_resolver.py -v
```

Expected: FAIL during collection with
`ModuleNotFoundError: ai_web_explorer.safesym_bridge.semantic_resolver`.

- [ ] **Step 3: Implement the resolver contracts**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ai_web_explorer.safesym_bridge.dom_observer import (
    DomInteractableCandidate,
)
from ai_web_explorer.safesym_bridge.models import StateSnapshot


@dataclass(frozen=True)
class SemanticMatch:
    candidate_id: str
    semantic_id: str
    confidence: float
    resolver: str


@dataclass(frozen=True)
class ResolutionBatch:
    matches: list[SemanticMatch]
    unmatched_candidate_ids: list[str]


class SemanticActionResolver(Protocol):
    async def resolve(
        self,
        state: StateSnapshot,
        candidates: list[DomInteractableCandidate],
    ) -> ResolutionBatch:
        ...
```

- [ ] **Step 4: Run the contract tests**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_semantic_resolver.py -v
```

Expected: `2 passed`.

- [ ] **Step 5: Commit the contracts**

```powershell
git add src/ai_web_explorer/safesym_bridge/semantic_resolver.py tests/safesym_bridge/test_semantic_resolver.py
git commit -m "feat: add semantic resolver contracts"
```

---

### Task 2: SauceDemo Rule Resolver

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/saucedemo_resolver.py`
- Create: `tests/safesym_bridge/test_saucedemo_resolver.py`

**Interfaces:**
- Consumes: `SemanticMatch`, `ResolutionBatch`, `StateSnapshot`, and normalized DOM candidates.
- Produces: `SauceDemoRuleResolver.resolve(state, candidates) -> ResolutionBatch`.

- [ ] **Step 1: Write failing tests for known and unknown candidates**

Create these local test helpers, then add:

```python
import pytest

from ai_web_explorer.safesym_bridge.dom_observer import (
    DomInteractableCandidate,
)
from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.saucedemo_resolver import (
    SauceDemoRuleResolver,
)


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def snapshot(page_id: str) -> StateSnapshot:
    return StateSnapshot(
        page_id=page_id,
        url=f"https://www.saucedemo.com/{page_id}",
        title=page_id,
        signature={},
    )


def candidate(
    *,
    candidate_id: str,
    locator: str,
    name: str,
    metadata: dict[str, str],
    kind: str = "button",
) -> DomInteractableCandidate:
    return DomInteractableCandidate(
        id=candidate_id,
        kind=kind,
        locator=locator,
        locator_strategy="test",
        name=name,
        visible=True,
        enabled=True,
        metadata=metadata,
    )


async def test_resolver_matches_login_without_execution_details():
    resolver = SauceDemoRuleResolver()
    login = candidate(
        candidate_id="dom_login",
        locator="#login-button",
        name="Login",
        metadata={"id": "login-button", "data-test": "login-button"},
    )

    batch = await resolver.resolve(snapshot("login"), [login])

    assert [(match.candidate_id, match.semantic_id) for match in batch.matches] == [
        ("dom_login", "login_submit")
    ]
    assert batch.matches[0].confidence == 1.0
    assert batch.matches[0].resolver == "saucedemo_rule"
    assert batch.unmatched_candidate_ids == []


async def test_resolver_reports_unknown_candidate():
    resolver = SauceDemoRuleResolver()
    unknown = candidate(
        candidate_id="dom_unknown",
        locator="#help",
        name="Help",
        metadata={"id": "help"},
    )

    batch = await resolver.resolve(snapshot("inventory"), [unknown])

    assert batch.matches == []
    assert batch.unmatched_candidate_ids == ["dom_unknown"]
```

```python
@pytest.mark.parametrize(
    ("page_id", "token", "semantic_id"),
    [
        ("inventory", "add-to-cart-sauce-labs-backpack", "product_add_to_cart"),
        ("inventory", "shopping-cart-link", "cart_open"),
        ("cart", "checkout", "cart_checkout_start"),
        ("checkout_info", "continue", "checkout_info_submit"),
        ("checkout_overview", "finish", "order_place_confirm"),
    ],
)
async def test_resolver_matches_checkout_path(page_id, token, semantic_id):
    resolver = SauceDemoRuleResolver()
    source = candidate(
        candidate_id=f"dom_{token}",
        locator=f'[data-test="{token}"]',
        name=token,
        metadata={"data-test": token},
    )

    batch = await resolver.resolve(snapshot(page_id), [source])

    assert [match.semantic_id for match in batch.matches] == [semantic_id]
    assert batch.unmatched_candidate_ids == []
```

- [ ] **Step 2: Run the resolver tests and verify failure**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_saucedemo_resolver.py -v
```

Expected: FAIL during collection because `saucedemo_resolver` does not exist.

- [ ] **Step 3: Move matching logic into the rule resolver**

Implement `_matches()` with the existing ID, `data-test`, and class checks.
Define page-aware rule data:

```python
RULES = {
    "login": [
        ("login_submit", {"id_": "login-button", "data_test": "login-button"}),
    ],
    "inventory": [
        (
            "product_add_to_cart",
            {"data_test": "add-to-cart-sauce-labs-backpack"},
        ),
        (
            "cart_open",
            {
                "data_test": "shopping-cart-link",
                "class_name": "shopping_cart_link",
            },
        ),
    ],
    "cart": [
        ("cart_checkout_start", {"id_": "checkout", "data_test": "checkout"}),
    ],
    "checkout_info": [
        (
            "checkout_info_submit",
            {"id_": "continue", "data_test": "continue"},
        ),
    ],
    "checkout_overview": [
        (
            "order_place_confirm",
            {"id_": "finish", "data_test": "finish"},
        ),
    ],
}
```

For each candidate, emit the first matching `SemanticMatch`. If no rule
matches, append its ID to `unmatched_candidate_ids`. Use confidence `1.0` and
resolver name `"saucedemo_rule"`.

- [ ] **Step 4: Run resolver and existing adapter tests**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_saucedemo_resolver.py tests/safesym_bridge/test_saucedemo_adapter.py -v
```

Expected: all tests pass; the old adapter still uses its original mapping path.

- [ ] **Step 5: Commit the SauceDemo resolver**

```powershell
git add src/ai_web_explorer/safesym_bridge/saucedemo_resolver.py tests/safesym_bridge/test_saucedemo_resolver.py
git commit -m "feat: add SauceDemo semantic resolver"
```

---

### Task 3: Domain Action Catalog

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/action_catalog.py`
- Create: `src/ai_web_explorer/safesym_bridge/saucedemo_catalog.py`
- Create: `tests/safesym_bridge/test_action_catalog.py`
- Create: `tests/safesym_bridge/test_saucedemo_catalog.py`

**Interfaces:**
- Consumes: `SemanticMatch`, source candidates, and `StateSnapshot`.
- Produces: `ActionDefinition`, `DomainActionCatalog.build_actions(state, matches, candidates)`, and `create_saucedemo_action_catalog()`.

- [ ] **Step 1: Write failing generic catalog tests**

```python
import pytest

from ai_web_explorer.safesym_bridge.action_catalog import (
    ActionDefinition,
    DomainActionCatalog,
)
from ai_web_explorer.safesym_bridge.semantic_resolver import SemanticMatch


def test_catalog_builds_action_from_match_and_candidate():
    catalog = DomainActionCatalog(
        {
            ("login", "login_submit"): ActionDefinition(
                raw_description="Click Login",
                execution_kind="fill_then_click",
                values={"#user": "standard_user"},
                position="login form",
                priority=0,
            )
        }
    )
    source = candidate(
        candidate_id="dom_login",
        locator="#login-button",
        name="Login",
        metadata={"id": "login-button"},
    )

    actions = catalog.build_actions(
        snapshot("login"),
        [SemanticMatch("dom_login", "login_submit", 1.0, "rule")],
        [source],
    )

    assert actions[0].semantic_id == "login_submit"
    assert actions[0].selector == "#login-button"
    assert actions[0].values == {"#user": "standard_user"}


def test_catalog_rejects_missing_candidate():
    catalog = DomainActionCatalog({})

    with pytest.raises(ValueError, match="Missing candidate"):
        catalog.build_actions(
            snapshot("login"),
            [SemanticMatch("missing", "login_submit", 1.0, "rule")],
            [],
        )


def test_catalog_rejects_missing_definition():
    catalog = DomainActionCatalog({})
    source = candidate(
        candidate_id="dom_login",
        locator="#login-button",
        name="Login",
        metadata={"id": "login-button"},
    )

    with pytest.raises(ValueError, match="Missing action definition"):
        catalog.build_actions(
            snapshot("login"),
            [SemanticMatch("dom_login", "login_submit", 1.0, "rule")],
            [source],
        )
```

Also test that matches with `confidence < 1.0` are not built. Define the
first-stage threshold as `1.0` in `DomainActionCatalog`.

- [ ] **Step 2: Run the generic catalog tests and verify failure**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_action_catalog.py -v
```

Expected: FAIL during collection because `action_catalog` does not exist.

- [ ] **Step 3: Implement the generic catalog**

```python
@dataclass(frozen=True)
class ActionDefinition:
    raw_description: str
    execution_kind: str
    values: dict[str, str] = field(default_factory=dict)
    position: str = ""
    priority: int = 0
```

`DomainActionCatalog.__init__()` accepts:

```python
dict[tuple[str, str], ActionDefinition]
```

`build_actions()` must:

1. index candidates by candidate ID;
2. skip matches below `minimum_confidence`, default `1.0`;
3. raise `ValueError("Missing candidate: <id>")` before definition lookup;
4. look up definitions by `(state.page_id, match.semantic_id)`;
5. raise `ValueError("Missing action definition: <page>/<semantic>")` when absent;
6. build `ExplorationAction` using the candidate locator;
7. sort built actions by definition priority while preserving input order for
   equal priorities.

- [ ] **Step 4: Run the generic catalog tests**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_action_catalog.py -v
```

Expected: all generic catalog tests pass.

- [ ] **Step 5: Write failing SauceDemo catalog tests**

```python
from ai_web_explorer.safesym_bridge.saucedemo_catalog import (
    create_saucedemo_action_catalog,
)
from ai_web_explorer.safesym_bridge.semantic_resolver import SemanticMatch


def test_saucedemo_catalog_owns_login_values():
    catalog = create_saucedemo_action_catalog()
    login = candidate(
        candidate_id="dom_login",
        locator="#login-button",
        name="Login",
        metadata={"id": "login-button"},
    )

    actions = catalog.build_actions(
        snapshot("login"),
        [SemanticMatch("dom_login", "login_submit", 1.0, "saucedemo_rule")],
        [login],
    )

    assert actions[0].execution_kind == "fill_then_click"
    assert actions[0].values == {
        "#user-name": "standard_user",
        "#password": "secret_sauce",
    }


def test_saucedemo_catalog_preserves_inventory_priority():
    catalog = create_saucedemo_action_catalog()
    cart = candidate(
        candidate_id="dom_cart",
        locator=".shopping_cart_link",
        name="Cart",
        metadata={"class": "shopping_cart_link"},
    )
    add = candidate(
        candidate_id="dom_add",
        locator='[data-test="add-to-cart-sauce-labs-backpack"]',
        name="Add to cart",
        metadata={"data-test": "add-to-cart-sauce-labs-backpack"},
    )

    actions = catalog.build_actions(
        snapshot("inventory"),
        [
            SemanticMatch("dom_cart", "cart_open", 1.0, "saucedemo_rule"),
            SemanticMatch(
                "dom_add",
                "product_add_to_cart",
                1.0,
                "saucedemo_rule",
            ),
        ],
        [cart, add],
    )

    assert [action.semantic_id for action in actions] == [
        "product_add_to_cart",
        "cart_open",
    ]
```

Add these assertions for the remaining definitions:

```python
@pytest.mark.parametrize(
    ("page_id", "token", "semantic_id", "execution_kind"),
    [
        ("cart", "checkout", "cart_checkout_start", "click"),
        ("checkout_info", "continue", "checkout_info_submit", "fill_then_click"),
        ("checkout_overview", "finish", "order_place_confirm", "click"),
    ],
)
def test_saucedemo_catalog_builds_checkout_actions(
    page_id,
    token,
    semantic_id,
    execution_kind,
):
    catalog = create_saucedemo_action_catalog()
    source = candidate(
        candidate_id=f"dom_{token}",
        locator=f'[data-test="{token}"]',
        name=token,
        metadata={"data-test": token},
    )

    actions = catalog.build_actions(
        snapshot(page_id),
        [SemanticMatch(source.id, semantic_id, 1.0, "saucedemo_rule")],
        [source],
    )

    assert actions[0].semantic_id == semantic_id
    assert actions[0].execution_kind == execution_kind


def test_saucedemo_catalog_owns_checkout_information_values():
    catalog = create_saucedemo_action_catalog()
    source = candidate(
        candidate_id="dom_continue",
        locator="#continue",
        name="Continue",
        metadata={"id": "continue"},
    )

    actions = catalog.build_actions(
        snapshot("checkout_info"),
        [
            SemanticMatch(
                "dom_continue",
                "checkout_info_submit",
                1.0,
                "saucedemo_rule",
            )
        ],
        [source],
    )

    assert actions[0].values == {
        "#first-name": "Safe",
        "#last-name": "Sym",
        "#postal-code": "12345",
    }
```

- [ ] **Step 6: Run SauceDemo catalog tests and verify failure**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_saucedemo_catalog.py -v
```

Expected: FAIL because `saucedemo_catalog` does not exist.

- [ ] **Step 7: Implement SauceDemo catalog definitions**

Create `create_saucedemo_action_catalog()` with definitions for all six
semantic actions. Move execution kinds, values, descriptions, positions, and
the current `ACTION_PRIORITY` values into those definitions. Do not import
anything from `saucedemo_adapter.py`.

- [ ] **Step 8: Run both catalog suites**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_action_catalog.py tests/safesym_bridge/test_saucedemo_catalog.py -v
```

Expected: all catalog tests pass.

- [ ] **Step 9: Commit the catalogs**

```powershell
git add src/ai_web_explorer/safesym_bridge/action_catalog.py src/ai_web_explorer/safesym_bridge/saucedemo_catalog.py tests/safesym_bridge/test_action_catalog.py tests/safesym_bridge/test_saucedemo_catalog.py
git commit -m "feat: add domain action catalog"
```

---

### Task 4: Adapter Migration and Regression Verification

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/saucedemo_adapter.py`
- Modify: `tests/safesym_bridge/test_saucedemo_adapter.py`

**Interfaces:**
- Consumes: `SauceDemoRuleResolver.resolve()` and `DomainActionCatalog.build_actions()`.
- Produces: unchanged `SauceDemoAdapter.list_actions()` and `execute_action()` behavior for callers.

- [ ] **Step 1: Replace direct mapping tests with failing adapter integration tests**

Remove imports and tests for `actions_from_candidates()`. Add injectable
dependencies and diagnostics expectations:

```python
async def test_adapter_resolves_dom_candidates_through_new_layers(monkeypatch):
    login = candidate(
        locator="#login-button",
        name="Login",
        metadata={"id": "login-button", "data-test": "login-button"},
    )

    async def fake_extract(page):
        return [login]

    monkeypatch.setattr(
        "ai_web_explorer.safesym_bridge.saucedemo_adapter."
        "extract_dom_interactables",
        fake_extract,
    )
    adapter = SauceDemoAdapter()

    actions = await adapter.list_actions(object(), snapshot("login"))

    assert [action.semantic_id for action in actions] == ["login_submit"]
    assert adapter.last_resolution is not None
    assert adapter.last_resolution.unmatched_candidate_ids == []


async def test_adapter_reports_unmatched_dom_without_static_execution(monkeypatch):
    unknown = candidate(
        locator="#help",
        name="Help",
        metadata={"id": "help"},
    )

    async def fake_extract(page):
        return [unknown]

    monkeypatch.setattr(
        "ai_web_explorer.safesym_bridge.saucedemo_adapter."
        "extract_dom_interactables",
        fake_extract,
    )
    adapter = SauceDemoAdapter()

    actions = await adapter.list_actions(object(), snapshot("inventory"))

    assert actions == []
    assert adapter.last_resolution.unmatched_candidate_ids == ["dom_001"]
```

Retain the existing tests that use `object()` to force DOM extraction failure;
they verify the static fallback remains available when observation itself
raises an exception.

- [ ] **Step 2: Run adapter tests and verify failure**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_saucedemo_adapter.py -v
```

Expected: FAIL because `last_resolution` does not exist and the adapter still
falls back to static actions for an unmatched nonempty observation.

- [ ] **Step 3: Migrate `SauceDemoAdapter`**

Implement:

```python
class SauceDemoAdapter:
    app_name = "saucedemo"
    start_node = "login"
    start_url = "https://www.saucedemo.com/"

    def __init__(
        self,
        resolver: SemanticActionResolver | None = None,
        catalog: DomainActionCatalog | None = None,
    ) -> None:
        self.resolver = resolver or SauceDemoRuleResolver()
        self.catalog = catalog or create_saucedemo_action_catalog()
        self.last_resolution: ResolutionBatch | None = None
```

Change `list_actions()` to:

```python
async def list_actions(self, page, state):
    try:
        candidates = await extract_dom_interactables(page)
    except Exception:
        self.last_resolution = None
        return static_actions_for_state(state)

    self.last_resolution = await self.resolver.resolve(state, candidates)
    return self.catalog.build_actions(
        state,
        self.last_resolution.matches,
        candidates,
    )
```

Then delete `ACTION_PRIORITY`, `_matches()`, and
`actions_from_candidates()` from the adapter. Retain `static_actions_for_state`
only as the DOM-observation failure fallback.

- [ ] **Step 4: Run all new and adapter tests**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_semantic_resolver.py tests/safesym_bridge/test_saucedemo_resolver.py tests/safesym_bridge/test_action_catalog.py tests/safesym_bridge/test_saucedemo_catalog.py tests/safesym_bridge/test_saucedemo_adapter.py -v
```

Expected: all selected tests pass.

- [ ] **Step 5: Run the complete bridge suite**

Run:

```powershell
python -m pytest tests/safesym_bridge -v
```

Expected: the same pass/skip baseline as before implementation, with the new
tests added and no failures.

- [ ] **Step 6: Run real-browser graph exploration**

Run with the repository virtual environment and source path:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m ai_web_explorer.safesym_bridge.cli explore-graph --output outputs/semantic_resolver_smoke/graph.json
```

Expected:

- command exits with code `0`;
- `outputs/semantic_resolver_smoke/graph.json` exists;
- graph edges include `login_submit`, `product_add_to_cart`, `cart_open`,
  `cart_checkout_start`, `checkout_info_submit`, and `order_place_confirm`;
- terminal node is `checkout_complete`.

- [ ] **Step 7: Run graph-derived PDDL smoke verification**

Run:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m ai_web_explorer.safesym_bridge.cli explore-pddl --output outputs/semantic_resolver_smoke/pddl
```

Expected:

- command exits with code `0`;
- `domain.pddl` and `problem.pddl` exist;
- the generated domain contains the six SauceDemo semantic actions.

Inject SafeSym constraints:

```powershell
$env:PYTHONPATH = "C:\Users\moon\Desktop\Projects\SafeSym"
python -m safeww.cli.inject_safety --task-dir outputs/semantic_resolver_smoke/pddl --rules "C:\Users\moon\Desktop\Projects\SafeSym\configs\constraint_rules.json"
```

Expected: `[OK] outputs\semantic_resolver_smoke\pddl` and
`Processed 1/1 tasks`. The directory must now contain `safe_domain.pddl` and
`safe_problem.pddl`.

Run Fast Downward:

```powershell
& "C:\Users\moon\Desktop\Projects\AutoWebWorld\downward\fast-downward.py" outputs/semantic_resolver_smoke/pddl/safe_domain.pddl outputs/semantic_resolver_smoke/pddl/safe_problem.pddl --search "astar(lmcut())"
```

Expected: return code `0` and `Solution found`. Inspect `sas_plan` and confirm
`check_information_verification_checkout_info_submit` precedes
`checkout_info_submit`, and
`check_human_confirmation_order_place_confirm` precedes
`order_place_confirm`.

- [ ] **Step 8: Commit the adapter migration**

Do not add generated `outputs/` files.

```powershell
git add src/ai_web_explorer/safesym_bridge/saucedemo_adapter.py tests/safesym_bridge/test_saucedemo_adapter.py
git commit -m "refactor: separate SauceDemo semantic resolution"
```

---

## Completion Check

Before reporting completion:

```powershell
git status --short
python -m pytest tests/safesym_bridge -v
```

Confirm:

- no implementation task remains unchecked;
- no generated browser output is staged;
- `actions_from_candidates` no longer appears under `src/`;
- all resolver, catalog, adapter, graph, and PDDL tests pass;
- real-browser graph and PDDL smoke tests succeeded;
- SafeSym and Fast Downward still produce a safe plan.
