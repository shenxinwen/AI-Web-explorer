# Browser-Observed SafeSym Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a browser-observed SauceDemo flow that records real before/after page states and exports a SafeSym-compatible FSM JSON.

**Architecture:** Keep the browser-observed flow isolated in `ai_web_explorer.safesym_bridge`. Add deterministic state observation, transition recording, a Playwright SauceDemo runner, and CLI subcommands while reusing the existing exporter, effect inference, action semantics, and validator.

**Tech Stack:** Python 3.9+, dataclasses, asyncio, pathlib, json, Playwright async API, pytest.

## Global Constraints

- Keep all new bridge logic under `src/ai_web_explorer/safesym_bridge/`.
- Do not rewrite the existing `src/ai_web_explorer/loop.py`.
- Use deterministic URL and DOM rules for SauceDemo state observation.
- Do not use LLMs for browser-observed SauceDemo state observation.
- Write observed output to `outputs/saucedemo_observed_fsm.json` by default.
- Keep `outputs/` ignored by git.
- Preserve the fixed FSM generation path for backward compatibility.
- Use TDD: write failing tests first, then minimal implementation.
- Browser smoke tests must skip cleanly if Playwright browsers are unavailable.

---

## File structure

Create:

- `src/ai_web_explorer/safesym_bridge/state_observer.py`  
  Converts a Playwright page into a `StateSnapshot` using deterministic SauceDemo rules.

- `src/ai_web_explorer/safesym_bridge/transition_recorder.py`  
  Records `before → action → after` and returns an `ObservedTransition`.

- `src/ai_web_explorer/safesym_bridge/browser_runner.py`  
  Runs the real SauceDemo checkout flow in Playwright and writes observed FSM JSON.

Create tests:

- `tests/safesym_bridge/test_state_observer.py`
- `tests/safesym_bridge/test_transition_recorder.py`
- `tests/safesym_bridge/test_browser_runner.py`

Modify:

- `src/ai_web_explorer/safesym_bridge/cli.py`  
  Add `fixed` and `observed` subcommands. Keep old `--output` behavior as fixed mode.

- `tests/safesym_bridge/test_cli.py`  
  Add CLI tests for subcommands without launching a browser.

- `docs/safesym-bridge.md`  
  Document fixed and observed modes.

---

### Task 1: SauceDemo state observer helpers

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/state_observer.py`
- Test: `tests/safesym_bridge/test_state_observer.py`

**Interfaces:**
- Consumes:
  - `StateSnapshot` from `ai_web_explorer.safesym_bridge.models`
- Produces:
  - `page_id_from_url(url: str) -> str`
  - `parse_cart_count(text: str | None) -> int`
  - `signature_from_observed_values(page_id: str, values: dict[str, object]) -> dict[str, object]`

- [ ] **Step 1: Write failing tests**

Create `tests/safesym_bridge/test_state_observer.py`:

```python
from ai_web_explorer.safesym_bridge.state_observer import (
    page_id_from_url,
    parse_cart_count,
    signature_from_observed_values,
)


def test_page_id_from_saucedemo_urls():
    assert page_id_from_url("https://www.saucedemo.com/") == "login"
    assert page_id_from_url("https://www.saucedemo.com/inventory.html") == "inventory"
    assert page_id_from_url("https://www.saucedemo.com/cart.html") == "cart"
    assert page_id_from_url("https://www.saucedemo.com/checkout-step-one.html") == "checkout_info"
    assert page_id_from_url("https://www.saucedemo.com/checkout-step-two.html") == "checkout_overview"
    assert page_id_from_url("https://www.saucedemo.com/checkout-complete.html") == "checkout_complete"


def test_parse_cart_count_defaults_to_zero_for_empty_badge():
    assert parse_cart_count(None) == 0
    assert parse_cart_count("") == 0
    assert parse_cart_count(" ") == 0


def test_parse_cart_count_reads_integer_badge():
    assert parse_cart_count("1") == 1
    assert parse_cart_count(" 3 ") == 3


def test_signature_from_observed_values_for_checkout_complete():
    signature = signature_from_observed_values(
        "checkout_complete",
        {
            "username_value": "",
            "password_value": "",
            "cart_count": 1,
            "checkout_first_name": "",
            "checkout_last_name": "",
            "checkout_postal_code": "",
        },
    )

    assert signature["$.is_logged_in"] is True
    assert signature["$.cart_count"] == 1
    assert signature["$.checkout_started"] is True
    assert signature["$.order_review_ready"] is True
    assert signature["$.order_created"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\src"; D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_state_observer.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'ai_web_explorer.safesym_bridge.state_observer'`.

- [ ] **Step 3: Implement helper functions**

Create `src/ai_web_explorer/safesym_bridge/state_observer.py`:

```python
from __future__ import annotations

from urllib.parse import urlparse

from ai_web_explorer.safesym_bridge.models import StateSnapshot


def page_id_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    if path in {"", "/"}:
        return "login"
    if path.endswith("/inventory.html"):
        return "inventory"
    if path.endswith("/cart.html"):
        return "cart"
    if path.endswith("/checkout-step-one.html"):
        return "checkout_info"
    if path.endswith("/checkout-step-two.html"):
        return "checkout_overview"
    if path.endswith("/checkout-complete.html"):
        return "checkout_complete"
    return "unknown"


def parse_cart_count(text: str | None) -> int:
    if not text or not text.strip():
        return 0
    return int(text.strip())


def signature_from_observed_values(
    page_id: str,
    values: dict[str, object],
) -> dict[str, object]:
    username_value = str(values.get("username_value") or "")
    password_value = str(values.get("password_value") or "")
    first_name = str(values.get("checkout_first_name") or "")
    last_name = str(values.get("checkout_last_name") or "")
    postal_code = str(values.get("checkout_postal_code") or "")
    cart_count = int(values.get("cart_count") or 0)

    checkout_started = page_id in {
        "checkout_info",
        "checkout_overview",
        "checkout_complete",
    }
    order_review_ready = page_id in {"checkout_overview", "checkout_complete"}
    order_created = page_id == "checkout_complete"

    return {
        "$.username_filled": bool(username_value),
        "$.password_filled": bool(password_value),
        "$.is_logged_in": page_id
        in {
            "inventory",
            "cart",
            "checkout_info",
            "checkout_overview",
            "checkout_complete",
        },
        "$.cart_count": cart_count,
        "$.checkout_started": checkout_started,
        "$.checkout_info_filled": bool(first_name and last_name and postal_code),
        "$.order_review_ready": order_review_ready,
        "$.order_created": order_created,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\src"; D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_state_observer.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/state_observer.py tests/safesym_bridge/test_state_observer.py
git commit -m "feat: add SauceDemo state observer helpers"
```

---

### Task 2: Async SauceDemo page observation

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/state_observer.py`
- Test: extend `tests/safesym_bridge/test_state_observer.py`

**Interfaces:**
- Consumes:
  - `page_id_from_url(url: str) -> str`
  - `parse_cart_count(text: str | None) -> int`
  - `signature_from_observed_values(page_id, values) -> dict[str, object]`
- Produces:
  - `async def observe_saucedemo_state(page) -> StateSnapshot`

- [ ] **Step 1: Write failing async observer test**

Append to `tests/safesym_bridge/test_state_observer.py`:

```python
import pytest


class FakeLocator:
    def __init__(self, *, value="", text="", count=1):
        self._value = value
        self._text = text
        self._count = count

    async def count(self):
        return self._count

    async def input_value(self):
        return self._value

    async def inner_text(self):
        return self._text


class FakePage:
    url = "https://www.saucedemo.com/inventory.html"

    async def title(self):
        return "Swag Labs"

    def locator(self, selector):
        locators = {
            "#user-name": FakeLocator(value=""),
            "#password": FakeLocator(value=""),
            ".shopping_cart_badge": FakeLocator(text="1", count=1),
            "#first-name": FakeLocator(value="", count=0),
            "#last-name": FakeLocator(value="", count=0),
            "#postal-code": FakeLocator(value="", count=0),
        }
        return locators[selector]


@pytest.mark.asyncio
async def test_observe_saucedemo_state_reads_page_snapshot():
    from ai_web_explorer.safesym_bridge.state_observer import observe_saucedemo_state

    snapshot = await observe_saucedemo_state(FakePage())

    assert snapshot.page_id == "inventory"
    assert snapshot.url == "https://www.saucedemo.com/inventory.html"
    assert snapshot.title == "Swag Labs"
    assert snapshot.signature["$.cart_count"] == 1
    assert snapshot.signature["$.is_logged_in"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\src"; D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_state_observer.py::test_observe_saucedemo_state_reads_page_snapshot -v
```

Expected: FAIL with `ImportError` or missing `observe_saucedemo_state`.

- [ ] **Step 3: Implement async observer**

Append to `src/ai_web_explorer/safesym_bridge/state_observer.py`:

```python
async def _input_value_or_empty(page, selector: str) -> str:
    locator = page.locator(selector)
    if await locator.count() == 0:
        return ""
    return await locator.input_value()


async def _inner_text_or_empty(page, selector: str) -> str:
    locator = page.locator(selector)
    if await locator.count() == 0:
        return ""
    return await locator.inner_text()


async def observe_saucedemo_state(page) -> StateSnapshot:
    page_id = page_id_from_url(page.url)
    title = await page.title()
    cart_badge_text = await _inner_text_or_empty(page, ".shopping_cart_badge")
    values = {
        "username_value": await _input_value_or_empty(page, "#user-name"),
        "password_value": await _input_value_or_empty(page, "#password"),
        "cart_count": parse_cart_count(cart_badge_text),
        "checkout_first_name": await _input_value_or_empty(page, "#first-name"),
        "checkout_last_name": await _input_value_or_empty(page, "#last-name"),
        "checkout_postal_code": await _input_value_or_empty(page, "#postal-code"),
    }
    return StateSnapshot(
        page_id=page_id,
        url=page.url,
        title=title,
        signature=signature_from_observed_values(page_id, values),
    )
```

- [ ] **Step 4: Run observer tests**

Run:

```bash
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\src"; D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_state_observer.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/state_observer.py tests/safesym_bridge/test_state_observer.py
git commit -m "feat: observe SauceDemo browser state"
```

---

### Task 3: Transition recorder

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/transition_recorder.py`
- Test: `tests/safesym_bridge/test_transition_recorder.py`

**Interfaces:**
- Consumes:
  - `semantic_id_for(raw_description: str) -> str`
  - `infer_effects(before, after) -> list[Effect]`
  - `preconditions_for(action_id: str) -> list[Condition]`
  - `ObservedAction`, `ObservedTransition`, `StateSnapshot`
- Produces:
  - `async def record_transition(page, raw_description: str, action_coro, observer=observe_saucedemo_state) -> ObservedTransition`

- [ ] **Step 1: Write failing transition recorder test**

Create `tests/safesym_bridge/test_transition_recorder.py`:

```python
from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.transition_recorder import record_transition


def snapshot(page_id, signature):
    return StateSnapshot(
        page_id=page_id,
        url=f"https://www.saucedemo.com/{page_id}",
        title="Swag Labs",
        signature=signature,
    )


async def test_record_transition_observes_before_and_after():
    calls = []
    snapshots = [
        snapshot("inventory", {"$.cart_count": 0, "$.is_logged_in": True}),
        snapshot("inventory", {"$.cart_count": 1, "$.is_logged_in": True}),
    ]

    async def observer(page):
        return snapshots.pop(0)

    async def action():
        calls.append("clicked")

    transition = await record_transition(
        page=object(),
        raw_description="Click Add to cart",
        action_coro=action,
        observer=observer,
    )

    assert calls == ["clicked"]
    assert transition.action.semantic_id == "product_add_to_cart"
    assert transition.source.page_id == "inventory"
    assert transition.target.page_id == "inventory"
    assert transition.preconditions == [
        {"path": "$.is_logged_in", "cond": "eq", "value": True}
    ]
    assert transition.effects == [
        {"path": "$.cart_count", "op": "set", "value": 1}
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\src"; D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_transition_recorder.py -v
```

Expected: FAIL with missing module.

- [ ] **Step 3: Implement transition recorder**

Create `src/ai_web_explorer/safesym_bridge/transition_recorder.py`:

```python
from __future__ import annotations

from collections.abc import Awaitable, Callable

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
from ai_web_explorer.safesym_bridge.state_observer import observe_saucedemo_state

Observer = Callable[[object], Awaitable[StateSnapshot]]
ActionCoroutineFactory = Callable[[], Awaitable[None]]


async def record_transition(
    page,
    raw_description: str,
    action_coro: ActionCoroutineFactory,
    observer: Observer = observe_saucedemo_state,
) -> ObservedTransition:
    before = await observer(page)
    action_id = semantic_id_for(raw_description)
    await action_coro()
    after = await observer(page)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\src"; D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_transition_recorder.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/transition_recorder.py tests/safesym_bridge/test_transition_recorder.py
git commit -m "feat: record observed SauceDemo transitions"
```

---

### Task 4: Browser runner assembly without launching browser in tests

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Test: `tests/safesym_bridge/test_browser_runner.py`

**Interfaces:**
- Consumes:
  - `build_fsm(app, initial_page_id, terminal_pages, transitions) -> SafeSymFsm`
  - `validate_fsm(fsm) -> ValidationResult`
- Produces:
  - `write_observed_fsm(transitions: list[ObservedTransition], output_path: Path) -> Path`

- [ ] **Step 1: Write failing write helper test**

Create `tests/safesym_bridge/test_browser_runner.py`:

```python
import json

from ai_web_explorer.safesym_bridge.browser_runner import write_observed_fsm
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions


def test_write_observed_fsm_writes_valid_json(tmp_path):
    output_path = tmp_path / "observed.json"

    result_path = write_observed_fsm(
        transitions=build_saucedemo_mvp_transitions(),
        output_path=output_path,
    )

    assert result_path == output_path
    data = json.loads(output_path.read_text(encoding="utf-8"))
    actions = [action for page in data["pages"] for action in page["actions"]]
    assert any(action["id"] == "order_place_confirm" for action in actions)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\src"; D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_browser_runner.py -v
```

Expected: FAIL with missing module.

- [ ] **Step 3: Implement writer helper**

Create `src/ai_web_explorer/safesym_bridge/browser_runner.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from ai_web_explorer.safesym_bridge.fsm_exporter import build_fsm
from ai_web_explorer.safesym_bridge.models import ObservedTransition
from ai_web_explorer.safesym_bridge.validator import validate_fsm


def write_observed_fsm(
    transitions: list[ObservedTransition],
    output_path: Path,
) -> Path:
    fsm = build_fsm(
        app="saucedemo",
        initial_page_id="login",
        terminal_pages=["checkout_complete"],
        transitions=transitions,
    )
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

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\src"; D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_browser_runner.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/browser_runner.py tests/safesym_bridge/test_browser_runner.py
git commit -m "feat: write browser-observed SafeSym FSM"
```

---

### Task 5: Real SauceDemo Playwright flow

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Test: extend `tests/safesym_bridge/test_browser_runner.py`

**Interfaces:**
- Consumes:
  - `record_transition(page, raw_description, action_coro) -> ObservedTransition`
  - `write_observed_fsm(transitions, output_path) -> Path`
- Produces:
  - `async def run_saucedemo_observed_flow(output_path: Path, *, headless: bool = True) -> Path`

- [ ] **Step 1: Write import-level test for runner API**

Append to `tests/safesym_bridge/test_browser_runner.py`:

```python
from pathlib import Path

from ai_web_explorer.safesym_bridge.browser_runner import run_saucedemo_observed_flow


def test_run_saucedemo_observed_flow_is_async_callable():
    assert callable(run_saucedemo_observed_flow)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\src"; D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_browser_runner.py::test_run_saucedemo_observed_flow_is_async_callable -v
```

Expected: FAIL with missing import.

- [ ] **Step 3: Implement real Playwright flow**

Append to `src/ai_web_explorer/safesym_bridge/browser_runner.py`:

```python
from playwright.async_api import async_playwright

from ai_web_explorer.safesym_bridge.transition_recorder import record_transition


async def run_saucedemo_observed_flow(
    output_path: Path,
    *,
    headless: bool = True,
) -> Path:
    transitions: list[ObservedTransition] = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        page = await browser.new_page()
        try:
            await page.goto("https://www.saucedemo.com/")

            await page.fill("#user-name", "standard_user")
            await page.fill("#password", "secret_sauce")
            transitions.append(
                await record_transition(
                    page,
                    "Click the Login button",
                    lambda: page.click("#login-button"),
                )
            )

            transitions.append(
                await record_transition(
                    page,
                    "Click Add to cart",
                    lambda: page.click('[data-test="add-to-cart-sauce-labs-backpack"]'),
                )
            )

            transitions.append(
                await record_transition(
                    page,
                    "Click the shopping cart link",
                    lambda: page.click(".shopping_cart_link"),
                )
            )

            transitions.append(
                await record_transition(
                    page,
                    "Click Checkout",
                    lambda: page.click("#checkout"),
                )
            )

            await page.fill("#first-name", "Safe")
            await page.fill("#last-name", "Sym")
            await page.fill("#postal-code", "12345")
            transitions.append(
                await record_transition(
                    page,
                    "Click Continue on checkout information",
                    lambda: page.click("#continue"),
                )
            )

            transitions.append(
                await record_transition(
                    page,
                    "Click Finish",
                    lambda: page.click("#finish"),
                )
            )

            return write_observed_fsm(transitions, output_path)
        finally:
            await browser.close()
```

- [ ] **Step 4: Run import-level test**

Run:

```bash
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\src"; D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_browser_runner.py::test_run_saucedemo_observed_flow_is_async_callable -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/browser_runner.py tests/safesym_bridge/test_browser_runner.py
git commit -m "feat: run observed SauceDemo browser flow"
```

---

### Task 6: CLI fixed and observed subcommands

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Test: modify `tests/safesym_bridge/test_cli.py`

**Interfaces:**
- Consumes:
  - `build_saucedemo_fsm() -> SafeSymFsm`
  - `run_saucedemo_observed_flow(output_path: Path, headless: bool = True) -> Path`
- Produces:
  - `fixed` CLI subcommand
  - `observed` CLI subcommand
  - backward-compatible no-subcommand fixed behavior

- [ ] **Step 1: Write failing CLI subcommand tests**

Append to `tests/safesym_bridge/test_cli.py`:

```python
def test_main_fixed_subcommand_writes_json_file(tmp_path):
    output_path = tmp_path / "fixed.json"

    exit_code = main(["fixed", "--output", str(output_path)])

    assert exit_code == 0
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["meta"]["app"] == "saucedemo"


def test_main_observed_subcommand_delegates_to_runner(tmp_path, monkeypatch):
    output_path = tmp_path / "observed.json"
    calls = []

    async def fake_runner(path, *, headless=True):
        calls.append((path, headless))
        path.write_text('{"ok": true}', encoding="utf-8")
        return path

    monkeypatch.setattr(
        "ai_web_explorer.safesym_bridge.cli.run_saucedemo_observed_flow",
        fake_runner,
    )

    exit_code = main(["observed", "--output", str(output_path), "--headed"])

    assert exit_code == 0
    assert calls == [(output_path, False)]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\src"; D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_cli.py -v
```

Expected: FAIL because subcommands are not implemented.

- [ ] **Step 3: Implement CLI subcommands**

Replace `src/ai_web_explorer/safesym_bridge/cli.py` with:

```python
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from ai_web_explorer.safesym_bridge.browser_runner import run_saucedemo_observed_flow
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


def write_fixed_fsm(output_path: Path) -> Path:
    fsm = build_saucedemo_fsm()
    validation = validate_fsm(fsm)
    if not validation.ok:
        joined = "; ".join(validation.errors)
        raise ValueError(f"Fixed FSM failed validation: {joined}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(fsm.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a SafeSym FSM for SauceDemo.")
    subparsers = parser.add_subparsers(dest="command")

    fixed = subparsers.add_parser("fixed", help="Generate deterministic fixed SauceDemo FSM.")
    fixed.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/saucedemo_fsm.json"),
        help="Path to write the generated fixed FSM JSON.",
    )

    observed = subparsers.add_parser("observed", help="Generate browser-observed SauceDemo FSM.")
    observed.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/saucedemo_observed_fsm.json"),
        help="Path to write the generated observed FSM JSON.",
    )
    observed.add_argument(
        "--headed",
        action="store_true",
        help="Run browser in headed mode instead of headless mode.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Backward-compatible fixed-mode output path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "observed":
            output_path = asyncio.run(
                run_saucedemo_observed_flow(args.output, headless=not args.headed)
            )
        else:
            output_path = write_fixed_fsm(args.output or Path("outputs/saucedemo_fsm.json"))
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"Wrote SafeSym FSM to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\src"; D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/cli.py tests/safesym_bridge/test_cli.py
git commit -m "feat: add SafeSym bridge CLI modes"
```

---

### Task 7: Optional browser smoke test

**Files:**
- Modify: `tests/safesym_bridge/test_browser_runner.py`

**Interfaces:**
- Consumes:
  - `run_saucedemo_observed_flow(output_path: Path, headless: bool = True) -> Path`

- [ ] **Step 1: Add skipped-by-default browser smoke test**

Append to `tests/safesym_bridge/test_browser_runner.py`:

```python
import os

import pytest


@pytest.mark.skipif(
    os.getenv("RUN_SAUCEDOMO_BROWSER_TEST") != "1",
    reason="Set RUN_SAUCEDOMO_BROWSER_TEST=1 to run the real browser smoke test.",
)
@pytest.mark.asyncio
async def test_run_saucedemo_observed_flow_smoke(tmp_path):
    output_path = tmp_path / "observed.json"

    result_path = await run_saucedemo_observed_flow(output_path, headless=True)

    assert result_path == output_path
    data = json.loads(output_path.read_text(encoding="utf-8"))
    actions = [action for page in data["pages"] for action in page["actions"]]
    assert any(action["id"] == "order_place_confirm" for action in actions)
```

- [ ] **Step 2: Run normal tests and confirm smoke test skips**

Run:

```bash
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\src"; D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_browser_runner.py -v
```

Expected: PASS with one skipped smoke test.

- [ ] **Step 3: Commit**

```bash
git add tests/safesym_bridge/test_browser_runner.py
git commit -m "test: add optional SauceDemo browser smoke test"
```

---

### Task 8: Documentation update and final verification

**Files:**
- Modify: `docs/safesym-bridge.md`

**Interfaces:**
- Consumes:
  - fixed CLI mode
  - observed CLI mode

- [ ] **Step 1: Update documentation**

Update `docs/safesym-bridge.md` so the generate section says:

```markdown
## Generate the FSM

Fixed deterministic FSM:

```bash
python -m ai_web_explorer.safesym_bridge.cli fixed --output outputs/saucedemo_fsm.json
```

Browser-observed FSM:

```bash
python -m ai_web_explorer.safesym_bridge.cli observed --output outputs/saucedemo_observed_fsm.json
```

For backward compatibility, this still generates the fixed FSM:

```bash
python -m ai_web_explorer.safesym_bridge.cli --output outputs/saucedemo_fsm.json
```
```

- [ ] **Step 2: Run all bridge tests**

Run:

```bash
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\src"; D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe -m pytest tests\safesym_bridge -v
```

Expected: PASS, with the optional browser smoke test skipped unless explicitly enabled.

- [ ] **Step 3: Run fixed CLI**

Run:

```bash
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\src"; D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe -m ai_web_explorer.safesym_bridge.cli fixed --output outputs\saucedemo_fsm.json
```

Expected:

```text
Wrote SafeSym FSM to outputs\saucedemo_fsm.json
```

- [ ] **Step 4: Run observed CLI if browser dependencies are available**

Run:

```bash
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\src"; D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe -m ai_web_explorer.safesym_bridge.cli observed --output outputs\saucedemo_observed_fsm.json
```

Expected when Playwright browsers are installed and network is available:

```text
Wrote SafeSym FSM to outputs\saucedemo_observed_fsm.json
```

If Playwright browsers are not installed, record the exact error and do not claim browser smoke success.

- [ ] **Step 5: Commit**

```bash
git add docs/safesym-bridge.md
git commit -m "docs: document browser-observed SafeSym bridge"
```

---

## Self-review checklist

- Spec coverage: Tasks 1–2 implement state observation; Task 3 implements transition recording; Tasks 4–5 implement observed FSM writing and real Playwright flow; Task 6 implements CLI modes; Task 7 adds optional browser smoke coverage; Task 8 documents and verifies.
- Completeness scan: every task has concrete files, commands, and expected results.
- Type consistency: `StateSnapshot`, `ObservedTransition`, `run_saucedemo_observed_flow`, `write_observed_fsm`, and `observe_saucedemo_state` names are consistent across tasks.
- Scope control: no task rewrites `loop.py`, adds LLM observation, or expands beyond SauceDemo.
