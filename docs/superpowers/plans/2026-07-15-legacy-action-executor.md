# Legacy Action Executor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Subagent-driven execution is intentionally not the default for this project because the user requested single-agent, token-saving work unless explicitly allowed.

**Goal:** Extract a small reusable executor for grounded browser actions so the project can reuse existing click/fill/select operation capability without importing the old ReAct exploration loop.

**Architecture:** Add a focused `LegacyActionExecutor` under the SafeSym bridge package. It consumes an already-grounded `BrowserAction`, performs sync Playwright-style locator operations, and returns a boolean success flag. It does not call LLMs, select actions, verify with screenshots, build graphs, or change the current async `WebKobePlaywrightAdapter` behavior.

**Tech Stack:** Python 3.11+, pytest, fake sync Playwright page/locator objects, existing `BrowserAction` model.

## Global Constraints

- Reuse existing browser operation patterns from `src/ai_web_explorer/executor.py`.
- Do not use the old `ExploreLoop` as the Web-KOBE/SafeSym explorer.
- Do not call LLMs from `LegacyActionExecutor`.
- Do not generate selectors inside `LegacyActionExecutor`.
- Do not change the public `web-kobe-explore` CLI behavior.
- Do not introduce new runtime dependencies.
- Do not use subagents unless the user explicitly permits them.

---

## File Structure

- Create `src/ai_web_explorer/safesym_bridge/legacy_action_executor.py`
  - Owns sync Playwright-style execution for grounded `BrowserAction`.
  - Supports `click`, `fill`, `select`, and `fill_then_click`.
  - Returns `False` for missing locator, missing select value, unsupported action kind, or execution exception.

- Create `tests/safesym_bridge/test_legacy_action_executor.py`
  - Uses fake page/locator objects.
  - Verifies operation order and arguments without launching a browser.

- Modify `docs/current-project-overview.md`
  - Adds a short note pointing to the reusable legacy operation executor.

---

### Task 1: Add LegacyActionExecutor for grounded sync browser actions

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/legacy_action_executor.py`
- Create: `tests/safesym_bridge/test_legacy_action_executor.py`

**Interfaces:**
- Consumes:
  - `BrowserAction` from `ai_web_explorer.safesym_bridge.web_kobe_graph`
  - `config.PLAYWRIGHT_TIMEOUT` and `config.ACTION_SLEEP_TIME`
- Produces:
  - `class LegacyActionExecutor`
  - `LegacyActionExecutor.__init__(page: Any, *, timeout: int = config.PLAYWRIGHT_TIMEOUT, sleep_seconds: float = config.ACTION_SLEEP_TIME) -> None`
  - `LegacyActionExecutor.execute_browser_action(action: BrowserAction) -> bool`

- [ ] **Step 1: Write failing tests for click, fill, select, fill_then_click, and failure cases**

Create `tests/safesym_bridge/test_legacy_action_executor.py`:

```python
from __future__ import annotations

from ai_web_explorer.safesym_bridge.legacy_action_executor import (
    LegacyActionExecutor,
)
from ai_web_explorer.safesym_bridge.web_kobe_graph import BrowserAction


class FakeLocator:
    def __init__(self, selector: str, calls: list[tuple]) -> None:
        self.selector = selector
        self.calls = calls
        self.first = self

    def scroll_into_view_if_needed(self, *, timeout: int) -> None:
        self.calls.append(("scroll", self.selector, timeout))

    def click(self, *, timeout: int) -> None:
        self.calls.append(("click", self.selector, timeout))

    def fill(self, value: str, *, timeout: int) -> None:
        self.calls.append(("fill", self.selector, value, timeout))

    def select_option(self, value: str, *, timeout: int) -> None:
        self.calls.append(("select", self.selector, value, timeout))


class FailingLocator(FakeLocator):
    def click(self, *, timeout: int) -> None:
        raise RuntimeError("click failed")


class FakePage:
    def __init__(self, *, failing_selector: str | None = None) -> None:
        self.calls: list[tuple] = []
        self.failing_selector = failing_selector

    def locator(self, selector: str):
        if selector == self.failing_selector:
            return FailingLocator(selector, self.calls)
        return FakeLocator(selector, self.calls)


def _executor(page: FakePage) -> LegacyActionExecutor:
    return LegacyActionExecutor(page, timeout=123, sleep_seconds=0)


def test_click_action_scrolls_then_clicks_target_locator() -> None:
    page = FakePage()
    action = BrowserAction(
        action_kind="click",
        locator="#buy",
        semantic_id="buy",
        input_values={},
    )

    assert _executor(page).execute_browser_action(action) is True

    assert page.calls == [
        ("scroll", "#buy", 123),
        ("click", "#buy", 123),
    ]


def test_fill_action_uses_first_input_value() -> None:
    page = FakePage()
    action = BrowserAction(
        action_kind="fill",
        locator="#email",
        semantic_id="fill_email",
        input_values={"#email": "student@example.com"},
    )

    assert _executor(page).execute_browser_action(action) is True

    assert page.calls == [
        ("scroll", "#email", 123),
        ("fill", "#email", "student@example.com", 123),
    ]


def test_fill_action_uses_safe_default_when_no_value_is_available() -> None:
    page = FakePage()
    action = BrowserAction(
        action_kind="fill",
        locator="#search",
        semantic_id="fill_search",
        input_values={},
    )

    assert _executor(page).execute_browser_action(action) is True

    assert page.calls == [
        ("scroll", "#search", 123),
        ("fill", "#search", "test", 123),
    ]


def test_select_action_uses_first_input_value() -> None:
    page = FakePage()
    action = BrowserAction(
        action_kind="select",
        locator="#country",
        semantic_id="select_country",
        input_values={"#country": "US"},
    )

    assert _executor(page).execute_browser_action(action) is True

    assert page.calls == [
        ("scroll", "#country", 123),
        ("select", "#country", "US", 123),
    ]


def test_select_action_without_value_returns_false() -> None:
    page = FakePage()
    action = BrowserAction(
        action_kind="select",
        locator="#country",
        semantic_id="select_country",
        input_values={},
    )

    assert _executor(page).execute_browser_action(action) is False

    assert page.calls == []


def test_fill_then_click_fills_each_field_then_clicks_target() -> None:
    page = FakePage()
    action = BrowserAction(
        action_kind="fill_then_click",
        locator="#submit",
        semantic_id="submit_login",
        input_values={
            "#username": "standard_user",
            "#password": "secret_sauce",
        },
    )

    assert _executor(page).execute_browser_action(action) is True

    assert page.calls == [
        ("scroll", "#username", 123),
        ("fill", "#username", "standard_user", 123),
        ("scroll", "#password", 123),
        ("fill", "#password", "secret_sauce", 123),
        ("scroll", "#submit", 123),
        ("click", "#submit", 123),
    ]


def test_action_without_locator_returns_false() -> None:
    page = FakePage()
    action = BrowserAction(
        action_kind="click",
        locator=None,
        semantic_id="missing_locator",
        input_values={},
    )

    assert _executor(page).execute_browser_action(action) is False

    assert page.calls == []


def test_unsupported_action_kind_returns_false() -> None:
    page = FakePage()
    action = BrowserAction(
        action_kind="hover",
        locator="#menu",
        semantic_id="hover_menu",
        input_values={},
    )

    assert _executor(page).execute_browser_action(action) is False

    assert page.calls == []


def test_playwright_operation_exception_returns_false() -> None:
    page = FakePage(failing_selector="#buy")
    action = BrowserAction(
        action_kind="click",
        locator="#buy",
        semantic_id="buy",
        input_values={},
    )

    assert _executor(page).execute_browser_action(action) is False
```

- [ ] **Step 2: Run tests and verify they fail because the module does not exist**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_legacy_action_executor.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'ai_web_explorer.safesym_bridge.legacy_action_executor'
```

- [ ] **Step 3: Implement the minimal LegacyActionExecutor**

Create `src/ai_web_explorer/safesym_bridge/legacy_action_executor.py`:

```python
from __future__ import annotations

import logging
import time
from typing import Any

from ai_web_explorer import config
from ai_web_explorer.safesym_bridge.web_kobe_graph import BrowserAction


def _first_input_value(values: dict[str, str]) -> str | None:
    if not values:
        return None
    return next(iter(values.values()))


class LegacyActionExecutor:
    """Sync Playwright-style executor for already-grounded browser actions.

    This reuses the original ai-web-explorer operation pattern: locate the
    element, scroll it into view, perform click/fill/select, then wait briefly.
    It does not call LLMs or choose actions.
    """

    def __init__(
        self,
        page: Any,
        *,
        timeout: int = config.PLAYWRIGHT_TIMEOUT,
        sleep_seconds: float = config.ACTION_SLEEP_TIME,
    ) -> None:
        self._page = page
        self._timeout = timeout
        self._sleep_seconds = sleep_seconds

    def execute_browser_action(self, action: BrowserAction) -> bool:
        if action.locator is None:
            return False

        try:
            if action.action_kind == "click":
                self._click(action.locator)
            elif action.action_kind == "fill":
                self._fill(
                    action.locator,
                    _first_input_value(action.input_values) or "test",
                )
            elif action.action_kind == "select":
                value = _first_input_value(action.input_values)
                if value is None:
                    return False
                self._select(action.locator, value)
            elif action.action_kind == "fill_then_click":
                for selector, value in action.input_values.items():
                    self._fill(selector, value)
                self._click(action.locator)
            else:
                return False

            if self._sleep_seconds > 0:
                time.sleep(self._sleep_seconds)
            return True
        except Exception:
            logging.exception("Failed to execute grounded browser action")
            return False

    def _first_locator(self, selector: str):
        locator = self._page.locator(selector).first
        locator.scroll_into_view_if_needed(timeout=self._timeout)
        return locator

    def _click(self, selector: str) -> None:
        self._first_locator(selector).click(timeout=self._timeout)

    def _fill(self, selector: str, value: str) -> None:
        self._first_locator(selector).fill(value, timeout=self._timeout)

    def _select(self, selector: str, value: str) -> None:
        self._first_locator(selector).select_option(value, timeout=self._timeout)
```

- [ ] **Step 4: Run focused tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_legacy_action_executor.py -q
```

Expected:

```text
9 passed
```

- [ ] **Step 5: Run existing backend protocol tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_automation_backend.py tests\safesym_bridge\test_web_kobe_playwright_adapter.py -q
```

Expected:

```text
passed
```

- [ ] **Step 6: Commit Task 1**

Run:

```powershell
git add src\ai_web_explorer\safesym_bridge\legacy_action_executor.py tests\safesym_bridge\test_legacy_action_executor.py
git commit -m "feat: add legacy action executor"
```

---

### Task 2: Document the reusable operation executor

**Files:**
- Modify: `docs/current-project-overview.md`

**Interfaces:**
- Consumes:
  - Implemented module path `src/ai_web_explorer/safesym_bridge/legacy_action_executor.py`
- Produces:
  - Documentation stating that `LegacyActionExecutor` is a small operation primitive, not a full explorer.

- [ ] **Step 1: Update current project overview**

In `docs/current-project-overview.md`, after the paragraph that mentions `WebKobePlaywrightAdapter`, add:

```markdown
A small reusable operation executor is also planned or available at:

```text
src/ai_web_explorer/safesym_bridge/legacy_action_executor.py
```

`LegacyActionExecutor` reuses the original project's basic operation pattern:
scroll a grounded locator into view, then perform click/fill/select. It is not a
ReAct loop, does not call an LLM, and does not own exploration policy. Its role
is to make old-operation reuse explicit before a future `AiWebExplorerBackend`
is designed.
```

- [ ] **Step 2: Run a doc grep sanity check**

Run:

```powershell
Select-String -Path docs\current-project-overview.md -Pattern "legacy_action_executor.py","LegacyActionExecutor","AiWebExplorerBackend"
```

Expected:

```text
docs/current-project-overview.md contains all three terms
```

- [ ] **Step 3: Commit Task 2**

Run:

```powershell
git add docs\current-project-overview.md
git commit -m "docs: document legacy action executor"
```

---

### Task 3: Regression check

**Files:**
- No source changes expected.

**Interfaces:**
- Consumes:
  - `LegacyActionExecutor`
  - existing `AutomationBackend`
  - existing `WebKobePlaywrightAdapter`

- [ ] **Step 1: Run non-browser focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_legacy_action_executor.py tests\safesym_bridge\test_automation_backend.py tests\safesym_bridge\test_web_kobe_explorer.py tests\safesym_bridge\test_web_kobe_controller.py tests\safesym_bridge\test_web_kobe_playwright_adapter.py -q
```

Expected:

```text
passed
```

- [ ] **Step 2: Run the broader previously passing subset**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\safesym_bridge tests\test_local_shop_fixture.py tests\test_cli_start_url.py tests\test_cookie_prefilter.py tests\test_html_helpers.py tests\test_cli_collector_output.py tests\test_loop_task_guidance.py -q
```

Expected:

```text
passed
```

If this fails with `BrowserType.launch: spawn EPERM`, rerun the same command with elevated permissions because the failure is caused by sandboxed Chromium launch, not by Python test assertions.

- [ ] **Step 3: Check git status**

Run:

```powershell
git status --short
```

Expected:

```text
Only pre-existing unrelated working tree changes remain, or a clean tree if all implementation changes were committed.
```

Do not stage unrelated files.

