# Grounded Web Operation v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Subagent-driven execution is intentionally not the default for this project because the user requested single-agent, token-saving work unless explicitly allowed.

**Goal:** Make the deterministic `grounded_web` baseline agent better at operating pages and recording state changes before introducing LLM/VLM action selection.

**Architecture:** Keep `grounded_web` as the generic operation/exploration boundary. Improve DOM candidate metadata, deterministic action values, deterministic action ranking, Playwright actionability/waiting, and trace detail without moving generic exploration logic into `safesym_bridge`.

**Tech Stack:** Python 3.11+, pytest/anyio, Playwright async API, existing `AutomationBackend`, `WebKobeExplorer`, `WebKobeGraph`, and `WebKobePlaywrightAdapter`.

## Global Constraints

- Do not introduce LLM/VLM action selection in this stage.
- Do not let any model invent selectors or decide observed fact truth.
- Do not introduce new runtime dependencies.
- Keep `AutomationBackend` as the browser-operation boundary.
- Keep exploration strategy in `WebKobeExplorer` / controller-level code.
- Keep `grounded_web` independent from `safesym_bridge`.
- Preserve SauceDemo SafeSym regression compatibility.
- Validate first on the local `tests/fixtures/local_shop` smoke path.
- Do not use subagents unless the user explicitly permits them.

---

## File Structure

- Modify `src/ai_web_explorer/grounded_web/dom_observer.py`
  - Preserve `data-action` metadata from DOM candidates.
  - Keep locator generation deterministic and DOM-grounded.

- Modify `src/ai_web_explorer/grounded_web/action_extractor.py`
  - Generate stable, field-aware default input values.
  - Keep `BrowserAction` as the output type.

- Modify `src/ai_web_explorer/grounded_web/playwright_backend.py`
  - Preserve candidate `metadata` and `locator_strategy` in interactable records.
  - Improve action execution: locator resolution, scroll into view, actionability checks, settle wait, and diagnostic error strings.

- Create `src/ai_web_explorer/grounded_web/action_ranker.py`
  - Own deterministic interactable ranking.
  - Return the best unexplored `BrowserAction` without knowing Playwright or SafeSym.

- Modify `src/ai_web_explorer/grounded_web/explorer.py`
  - Use the ranker instead of the current first-unexplored helper.
  - Record more precise execution trace errors when the backend exposes them.

- Modify tests:
  - `tests/safesym_bridge/test_dom_observer.py`
  - `tests/safesym_bridge/test_web_action_extractor.py`
  - `tests/safesym_bridge/test_web_kobe_explorer.py`
  - `tests/safesym_bridge/test_web_kobe_playwright_adapter.py`
  - `tests/safesym_bridge/test_web_kobe_grounded_exploration.py`

---

## Execution Policy

Implement one task at a time. Each task ends with a focused test run and a commit.

Use this implementation skill when executing this plan:

```text
superpowers:executing-plans
```

Do not switch to subagent-driven development unless the user explicitly allows subagents.

---

### Task 1: Preserve DOM operation metadata and improve deterministic input defaults

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/dom_observer.py`
- Modify: `src/ai_web_explorer/grounded_web/action_extractor.py`
- Modify: `src/ai_web_explorer/grounded_web/playwright_backend.py`
- Test: `tests/safesym_bridge/test_dom_observer.py`
- Test: `tests/safesym_bridge/test_web_action_extractor.py`
- Test: `tests/safesym_bridge/test_web_kobe_playwright_adapter.py`

**Interfaces:**
- Consumes:
  - `DomInteractableCandidate`
  - `browser_actions_from_candidates(candidates: list[DomInteractableCandidate]) -> list[BrowserAction]`
- Produces:
  - `DomInteractableCandidate.metadata["data-action"]` when present.
  - Field-aware input defaults in `BrowserAction.input_values`.
  - Interactable records include `metadata` and `locator_strategy`.

- [ ] **Step 1: Add failing DOM metadata test**

Append this test to `tests/safesym_bridge/test_dom_observer.py`:

```python
def test_candidate_from_element_preserves_data_action_metadata():
    candidate = candidate_from_element(
        5,
        {
            "tag": "button",
            "data_action": "open-cart",
            "text": "Cart",
            "visible": True,
            "enabled": True,
        },
    )

    assert candidate.kind == "button"
    assert candidate.name == "Cart"
    assert candidate.metadata["data-action"] == "open-cart"
```

- [ ] **Step 2: Run DOM metadata test and verify it fails**

Run:

```bash
python -m pytest tests/safesym_bridge/test_dom_observer.py::test_candidate_from_element_preserves_data_action_metadata -q
```

Expected: FAIL with `KeyError: 'data-action'`.

- [ ] **Step 3: Implement DOM data-action preservation**

In `src/ai_web_explorer/grounded_web/dom_observer.py`, update `_metadata()` by adding `data_action` to `key_map`:

```python
    key_map = {
        "tag": "tag",
        "role": "role",
        "type": "type",
        "id": "id",
        "class": "class",
        "data_test": "data-test",
        "data_action": "data-action",
        "placeholder": "placeholder",
        "aria_label": "aria-label",
        "title": "title",
        "href": "href",
        "candidate_id": "data-web-kobe-id",
    }
```

In `extract_dom_interactables()`, add this property to the evaluated element object:

```javascript
data_action: element.getAttribute("data-action") || "",
```

Place it next to the existing `data_test` field.

- [ ] **Step 4: Run DOM metadata tests**

Run:

```bash
python -m pytest tests/safesym_bridge/test_dom_observer.py -q
```

Expected: PASS.

- [ ] **Step 5: Add failing action default tests**

Replace `test_browser_actions_from_input_candidate_adds_default_fill_value` in `tests/safesym_bridge/test_web_action_extractor.py` with these tests:

```python
def test_browser_actions_from_email_input_uses_stable_email_value():
    candidates = [
        DomInteractableCandidate(
            id="dom_002",
            kind="input",
            locator="#email",
            locator_strategy="id",
            name="Email",
            visible=True,
            enabled=True,
            metadata={"type": "email", "placeholder": "Email address"},
        )
    ]

    actions = browser_actions_from_candidates(candidates)

    assert actions[0].action_kind == "fill"
    assert actions[0].input_values == {"#email": "test@example.com"}


def test_browser_actions_from_password_input_uses_stable_password_value():
    candidates = [
        DomInteractableCandidate(
            id="dom_003",
            kind="input",
            locator="#password",
            locator_strategy="id",
            name="Password",
            visible=True,
            enabled=True,
            metadata={"type": "password"},
        )
    ]

    actions = browser_actions_from_candidates(candidates)

    assert actions[0].input_values == {"#password": "secret_sauce"}


def test_browser_actions_from_search_input_uses_search_value():
    candidates = [
        DomInteractableCandidate(
            id="dom_004",
            kind="input",
            locator="#query",
            locator_strategy="id",
            name="Search",
            visible=True,
            enabled=True,
            metadata={"type": "search", "placeholder": "Search products"},
        )
    ]

    actions = browser_actions_from_candidates(candidates)

    assert actions[0].input_values == {"#query": "sample"}
```

Keep `test_browser_actions_from_candidates_preserves_grounding` and `test_browser_actions_from_select_candidate_uses_first_option_value`.

- [ ] **Step 6: Run action default tests and verify they fail**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_action_extractor.py -q
```

Expected: FAIL because inputs still use `"test"`.

- [ ] **Step 7: Implement field-aware default input values**

In `src/ai_web_explorer/grounded_web/action_extractor.py`, add this helper above `_input_values_for()`:

```python
def _default_input_value(candidate: DomInteractableCandidate) -> str:
    text = " ".join(
        [
            candidate.name,
            candidate.locator,
            candidate.metadata.get("type", ""),
            candidate.metadata.get("placeholder", ""),
            candidate.metadata.get("aria-label", ""),
        ]
    ).lower()
    input_type = candidate.metadata.get("type", "").lower()

    if input_type == "email" or "email" in text:
        return "test@example.com"
    if input_type == "password" or "password" in text:
        return "secret_sauce"
    if input_type in {"number", "range"} or "quantity" in text or "qty" in text:
        return "1"
    if input_type == "search" or "search" in text:
        return "sample"
    if "user" in text or "login" in text:
        return "standard_user"
    return "test"
```

Then update `_input_values_for()`:

```python
def _input_values_for(candidate: DomInteractableCandidate) -> dict[str, str]:
    if candidate.kind in {"input", "textarea"}:
        return {candidate.locator: _default_input_value(candidate)}
    if candidate.kind == "select":
        raw_options = candidate.metadata.get("option-values", "")
        options = [
            option.strip() for option in raw_options.split(",") if option.strip()
        ]
        if options:
            return {candidate.locator: options[0]}
    return {}
```

- [ ] **Step 8: Run focused tests**

Run:

```bash
python -m pytest tests/safesym_bridge/test_dom_observer.py tests/safesym_bridge/test_web_action_extractor.py -q
```

Expected: PASS.

- [ ] **Step 9: Add failing interactable metadata test**

In `tests/safesym_bridge/test_web_kobe_playwright_adapter.py`, update
`test_list_interactables_uses_dom_candidates` expected output to include
`metadata` and `locator_strategy`:

```python
    assert interactables == [
        {
            "semantic_id": "dom_001_button_add_to_cart",
            "description": "Add to cart",
            "locator": 'button[data-test="add-to-cart"]',
            "locator_strategy": "css",
            "action_kind": "click",
            "input_values": {},
            "metadata": {"data-test": "add-to-cart"},
            "explored": False,
        }
    ]
```

- [ ] **Step 10: Run interactable metadata test and verify it fails**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_playwright_adapter.py::test_list_interactables_uses_dom_candidates -q
```

Expected: FAIL because `list_interactables()` does not yet expose candidate
metadata and locator strategy.

- [ ] **Step 11: Preserve candidate metadata in interactable records**

In `src/ai_web_explorer/grounded_web/playwright_backend.py`, replace the generic
candidate/action mapping in `list_interactables()`:

```python
        return [
            {
                "semantic_id": action.semantic_id,
                "description": action.description,
                "locator": action.locator,
                "action_kind": action.action_kind,
                "input_values": dict(action.input_values),
                "explored": False,
            }
            for action in actions
        ]
```

with:

```python
        return [
            {
                "semantic_id": action.semantic_id,
                "description": action.description,
                "locator": action.locator,
                "locator_strategy": candidate.locator_strategy,
                "action_kind": action.action_kind,
                "input_values": dict(action.input_values),
                "metadata": dict(candidate.metadata),
                "explored": False,
            }
            for candidate, action in zip(candidates, actions, strict=True)
        ]
```

Also update `_interactable_record()` for `BrowserAction` fallback records:

```python
        return {
            "semantic_id": action.semantic_id,
            "description": action.description,
            "locator": action.locator,
            "locator_strategy": None,
            "action_kind": action.action_kind,
            "input_values": dict(action.input_values),
            "metadata": {},
            "explored": False,
        }
```

And preserve optional fields for dict records:

```python
    return {
        "semantic_id": action.get("semantic_id"),
        "description": action.get("description"),
        "locator": action.get("locator"),
        "locator_strategy": action.get("locator_strategy"),
        "action_kind": action.get("action_kind"),
        "input_values": dict(action.get("input_values") or {}),
        "metadata": dict(action.get("metadata") or {}),
        "explored": bool(action.get("explored", False)),
    }
```

- [ ] **Step 12: Run Task 1 tests**

Run:

```bash
python -m pytest tests/safesym_bridge/test_dom_observer.py tests/safesym_bridge/test_web_action_extractor.py tests/safesym_bridge/test_web_kobe_playwright_adapter.py::test_list_interactables_uses_dom_candidates -q
```

Expected: PASS.

- [ ] **Step 13: Commit Task 1**

Run:

```bash
git add src/ai_web_explorer/grounded_web/dom_observer.py src/ai_web_explorer/grounded_web/action_extractor.py src/ai_web_explorer/grounded_web/playwright_backend.py tests/safesym_bridge/test_dom_observer.py tests/safesym_bridge/test_web_action_extractor.py tests/safesym_bridge/test_web_kobe_playwright_adapter.py
git commit -m "feat: improve grounded web action defaults"
```

---

### Task 2: Add deterministic action ranking and integrate it into WebKobeExplorer

**Files:**
- Create: `src/ai_web_explorer/grounded_web/action_ranker.py`
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Test: `tests/safesym_bridge/test_web_kobe_explorer.py`

**Interfaces:**
- Consumes:
  - `interactables: list[dict[str, Any]]`
- Produces:
  - `rank_interactables(interactables: list[dict[str, Any]]) -> list[dict[str, Any]]`
  - `select_unexplored_action(interactables: list[dict[str, Any]]) -> BrowserAction | None`

- [ ] **Step 1: Add failing explorer ranking test**

Append this test to `tests/safesym_bridge/test_web_kobe_explorer.py`:

```python
class RankedActionAdapter:
    app_name = "fake"

    def __init__(self):
        self.executed = []

    async def observe_state(self):
        return StateSnapshot(
            page_id="shop",
            url="https://example.test/shop",
            title="Shop",
            signature={"executed_count": len(self.executed)},
        )

    async def list_interactables(self, state):
        return [
            {
                "semantic_id": "name_input",
                "description": "Name",
                "locator": "#name",
                "action_kind": "fill",
                "input_values": {"#name": "test"},
                "explored": False,
                "metadata": {"type": "text"},
                "locator_strategy": "id",
            },
            {
                "semantic_id": "open_cart",
                "description": "Cart",
                "locator": '[data-action="open-cart"]',
                "action_kind": "click",
                "input_values": {},
                "explored": False,
                "metadata": {"data-action": "open-cart"},
                "locator_strategy": "data-action",
            },
        ]

    async def execute(self, action: BrowserAction):
        self.executed.append(action)
        return True


@pytest.mark.anyio
async def test_explore_one_step_prefers_explicit_action_button_over_input():
    adapter = RankedActionAdapter()
    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    graph = await explorer.explore_one_step()

    assert adapter.executed[0].semantic_id == "open_cart"
    assert graph.edges[0].action.semantic_id == "open_cart"
```

- [ ] **Step 2: Run ranking test and verify it fails**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_explorer.py::test_explore_one_step_prefers_explicit_action_button_over_input -q
```

Expected: FAIL because the current first-unexplored policy executes `name_input`.

- [ ] **Step 3: Create deterministic ranker**

Create `src/ai_web_explorer/grounded_web/action_ranker.py`:

```python
from __future__ import annotations

from typing import Any

from ai_web_explorer.grounded_web.graph import BrowserAction


def _truthy_metadata(item: dict[str, Any], key: str) -> bool:
    metadata = item.get("metadata") or {}
    return bool(metadata.get(key))


def _rank_score(item: dict[str, Any]) -> tuple[int, int, str]:
    action_kind = str(item.get("action_kind") or "click")
    description = str(item.get("description") or "")
    locator = str(item.get("locator") or "")
    semantic_id = str(item.get("semantic_id") or "")

    if item.get("explored"):
        return (100, 0, semantic_id)
    if _truthy_metadata(item, "data-action") or _truthy_metadata(item, "data-test"):
        return (0, 0, semantic_id)
    if action_kind == "click" and description:
        return (1, 0, semantic_id)
    if action_kind == "click":
        return (2, 0, semantic_id)
    if action_kind == "select":
        return (3, 0, semantic_id)
    if action_kind in {"fill", "fill_then_click"}:
        return (4, 0, semantic_id)
    if locator:
        return (5, 0, semantic_id)
    return (6, 0, semantic_id)


def rank_interactables(interactables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(interactables, key=_rank_score)


def select_unexplored_action(
    interactables: list[dict[str, Any]],
) -> BrowserAction | None:
    for item in rank_interactables(interactables):
        if item.get("explored"):
            continue
        semantic_id = str(item.get("semantic_id") or "unknown_action")
        return BrowserAction(
            action_kind=str(item.get("action_kind") or "click"),
            locator=item.get("locator"),
            semantic_id=semantic_id,
            input_values=dict(item.get("input_values") or {}),
            description=item.get("description"),
        )
    return None
```

- [ ] **Step 4: Integrate ranker into explorer**

In `src/ai_web_explorer/grounded_web/explorer.py`, add:

```python
from ai_web_explorer.grounded_web.action_ranker import select_unexplored_action
```

Remove the private `_first_unexplored_action()` helper.

Replace:

```python
        selected = _first_unexplored_action(source_interactables)
```

with:

```python
        selected = select_unexplored_action(source_interactables)
```

- [ ] **Step 5: Run explorer tests**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_explorer.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add src/ai_web_explorer/grounded_web/action_ranker.py src/ai_web_explorer/grounded_web/explorer.py tests/safesym_bridge/test_web_kobe_explorer.py
git commit -m "feat: rank grounded web actions deterministically"
```

---

### Task 3: Improve Playwright execution actionability, waiting, and diagnostics

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/playwright_backend.py`
- Test: `tests/safesym_bridge/test_web_kobe_playwright_adapter.py`

**Interfaces:**
- Consumes:
  - `WebKobePlaywrightAdapter.execute(action: BrowserAction) -> bool`
- Produces:
  - `WebKobePlaywrightAdapter.last_execution_error: str | None`
  - More robust `execute()` behavior while preserving the boolean protocol.

- [ ] **Step 1: Update fake locator test support**

In `tests/safesym_bridge/test_web_kobe_playwright_adapter.py`, update `FakeActionLocator` to support actionability helpers:

```python
class FakeActionLocator:
    def __init__(self, *, count_value: int = 1, visible: bool = True, enabled: bool = True):
        self.clicked = False
        self.filled = []
        self.selected = []
        self.count_value = count_value
        self.visible = visible
        self.enabled = enabled
        self.scrolled = False

    @property
    def first(self):
        return self

    async def count(self):
        return self.count_value

    async def is_visible(self):
        return self.visible

    async def is_enabled(self):
        return self.enabled

    async def scroll_into_view_if_needed(self):
        self.scrolled = True

    async def click(self):
        self.clicked = True

    async def fill(self, value):
        self.filled.append(value)

    async def select_option(self, value):
        self.selected.append(value)
```

Update `FakePage.__init__()` to accept the locator:

```python
class FakePage:
    def __init__(self, action_locator=None):
        self.url = "https://example.test/shop"
        self.action_locator = action_locator or FakeActionLocator()
        self.waits = []
        self.load_state_waits = []
```

Add this method to `FakePage`:

```python
    async def wait_for_load_state(self, state, timeout=None):
        self.load_state_waits.append((state, timeout))
```

- [ ] **Step 2: Add failing diagnostics tests**

Append these tests to `tests/safesym_bridge/test_web_kobe_playwright_adapter.py`:

```python
@pytest.mark.anyio
async def test_execute_scrolls_target_and_waits_for_page_settle():
    locator = FakeActionLocator()
    page = FakePage(locator)
    adapter = WebKobePlaywrightAdapter(page, page_id="fixture_shop")

    result = await adapter.execute(BrowserAction("click", "#add", "add"))

    assert result is True
    assert locator.scrolled is True
    assert page.load_state_waits == [("domcontentloaded", 1000)]
    assert page.waits == [100]
    assert adapter.last_execution_error is None


@pytest.mark.anyio
async def test_execute_reports_locator_not_found():
    page = FakePage(FakeActionLocator(count_value=0))
    adapter = WebKobePlaywrightAdapter(page, page_id="fixture_shop")

    result = await adapter.execute(BrowserAction("click", "#missing", "missing"))

    assert result is False
    assert adapter.last_execution_error == "locator_not_found"


@pytest.mark.anyio
async def test_execute_reports_locator_not_visible():
    page = FakePage(FakeActionLocator(visible=False))
    adapter = WebKobePlaywrightAdapter(page, page_id="fixture_shop")

    result = await adapter.execute(BrowserAction("click", "#hidden", "hidden"))

    assert result is False
    assert adapter.last_execution_error == "locator_not_visible"
```

- [ ] **Step 3: Run diagnostics tests and verify they fail**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_playwright_adapter.py::test_execute_scrolls_target_and_waits_for_page_settle tests/safesym_bridge/test_web_kobe_playwright_adapter.py::test_execute_reports_locator_not_found tests/safesym_bridge/test_web_kobe_playwright_adapter.py::test_execute_reports_locator_not_visible -q
```

Expected: FAIL because `last_execution_error`, `count()`, actionability checks, and load-state waiting are not implemented yet.

- [ ] **Step 4: Implement diagnostics and page settle helpers**

In `src/ai_web_explorer/grounded_web/playwright_backend.py`, add this attribute in `__init__()`:

```python
        self.last_execution_error: str | None = None
```

Add helpers inside `WebKobePlaywrightAdapter`:

```python
    def _fail_execution(self, error: str) -> bool:
        self.last_execution_error = error
        return False

    async def _settle_page(self) -> None:
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=1000)
        except Exception:
            self.last_execution_error = "page_settle_timeout"
        await self.page.wait_for_timeout(100)
```

Replace `execute()` with:

```python
    async def execute(self, action: BrowserAction) -> bool:
        self.last_execution_error = None
        if action.locator is None:
            return self._fail_execution("no_locator")

        locator = self.page.locator(action.locator)
        try:
            if await locator.count() == 0:
                return self._fail_execution("locator_not_found")

            target = locator.first
            if hasattr(target, "is_visible") and not await target.is_visible():
                return self._fail_execution("locator_not_visible")
            if hasattr(target, "is_enabled") and not await target.is_enabled():
                return self._fail_execution("locator_disabled")
            if hasattr(target, "scroll_into_view_if_needed"):
                await target.scroll_into_view_if_needed()

            if action.action_kind == "click":
                await target.click()
            elif action.action_kind == "fill":
                await target.fill(_first_input_value(action.input_values) or "test")
            elif action.action_kind == "fill_then_click":
                for selector, value in action.input_values.items():
                    fill_target = self.page.locator(selector).first
                    if hasattr(fill_target, "scroll_into_view_if_needed"):
                        await fill_target.scroll_into_view_if_needed()
                    await fill_target.fill(value)
                await target.click()
            elif action.action_kind == "select":
                value = _first_input_value(action.input_values)
                if value is None:
                    return self._fail_execution("missing_select_value")
                await target.select_option(value)
            else:
                return self._fail_execution("unsupported_action_kind")

            await self._settle_page()
            return self.last_execution_error is None or self.last_execution_error == "page_settle_timeout"
        except Exception as exc:
            return self._fail_execution(f"playwright_error:{type(exc).__name__}")
```

This preserves `bool` compatibility. A settle timeout is diagnostic information,
but the action may still have succeeded; later graph trace can surface it.

- [ ] **Step 5: Run Playwright adapter tests**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_playwright_adapter.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add src/ai_web_explorer/grounded_web/playwright_backend.py tests/safesym_bridge/test_web_kobe_playwright_adapter.py
git commit -m "feat: improve grounded playwright execution"
```

---

### Task 4: Record execution diagnostics in WebKobeExplorer and run smoke/regressions

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Test: `tests/safesym_bridge/test_web_kobe_explorer.py`
- Test: `tests/safesym_bridge/test_web_kobe_grounded_exploration.py`

**Interfaces:**
- Consumes:
  - Optional backend attribute `last_execution_error: str | None`
- Produces:
  - `WebKobeEdge.execution_trace.error` uses concrete backend diagnostics when available.
  - No-delta successful actions remain `verified`.

- [ ] **Step 1: Add failing trace diagnostic test**

Append this adapter and test to `tests/safesym_bridge/test_web_kobe_explorer.py`:

```python
class FailingDiagnosticAdapter(FakeAdapter):
    def __init__(self):
        super().__init__()
        self.last_execution_error = None

    async def execute(self, action: BrowserAction):
        self.executed.append(action)
        self.last_execution_error = "locator_not_visible"
        return False


@pytest.mark.anyio
async def test_explore_one_step_records_backend_execution_error():
    explorer = WebKobeExplorer(
        adapter=FailingDiagnosticAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    assert edge.status == "failed_execution"
    assert edge.execution_trace.error == "locator_not_visible"
```

- [ ] **Step 2: Run diagnostic trace test and verify it fails**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_explorer.py::test_explore_one_step_records_backend_execution_error -q
```

Expected: FAIL because explorer currently writes `"adapter execution returned false"`.

- [ ] **Step 3: Implement diagnostic trace propagation**

In `src/ai_web_explorer/grounded_web/explorer.py`, replace the current `error=` expression:

```python
                error=None if success else "adapter execution returned false",
```

with:

```python
                error=(
                    None
                    if success
                    else str(
                        getattr(
                            self.adapter,
                            "last_execution_error",
                            "adapter execution returned false",
                        )
                        or "adapter execution returned false"
                    )
                ),
```

- [ ] **Step 4: Run explorer tests**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_explorer.py -q
```

Expected: PASS.

- [ ] **Step 5: Run local browser-backed smoke**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_grounded_exploration.py -q
```

Expected: PASS. The existing assertions should still include:

```python
assert result.summary.steps_completed == 3
assert ("cart_panel_visible", False, True) in deltas
assert ("cart_count", 0, 1) in deltas
```

- [ ] **Step 6: Run focused grounded web regression set**

Run:

```bash
python -m pytest tests/safesym_bridge/test_dom_observer.py tests/safesym_bridge/test_web_action_extractor.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_web_kobe_playwright_adapter.py tests/safesym_bridge/test_web_kobe_grounded_exploration.py tests/safesym_bridge/test_simple_grounded_web_agent.py -q
```

Expected: PASS.

- [ ] **Step 7: Run bridge regression suite**

Run:

```bash
python -m pytest tests/safesym_bridge -q
```

Expected: PASS with the current skipped browser-gated tests preserved.

- [ ] **Step 8: Commit Task 4**

Run:

```bash
git add src/ai_web_explorer/grounded_web/explorer.py tests/safesym_bridge/test_web_kobe_explorer.py
git commit -m "feat: record grounded execution diagnostics"
```

---

## Post-Implementation Review

After all tasks pass:

1. Check `git status --short` is clean.
2. Check recent commits:

   ```bash
   git log -4 --oneline
   ```

3. Confirm no generic exploration code was added to `safesym_bridge`.
4. Confirm `grounded_web` still does not import `safesym_bridge`:

   ```bash
   rg "safesym_bridge" src/ai_web_explorer/grounded_web
   ```

   Expected: no matches.

5. Report the final tests run and any skipped/gated tests.

## Future LLM/VLM Hook

Do not implement this in the current plan. The next plan can introduce an
LLM-backed action selector only after this deterministic path is stable.

The future hook should consume DOM-grounded candidates and produce a ranked
choice. It must not invent selectors, decide fact truth, or mutate graph
structure without recorded browser evidence.
