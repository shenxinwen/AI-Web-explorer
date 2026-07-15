# Automation Backend Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Subagent-driven execution is intentionally not the default for this project because the user requested single-agent, token-saving work unless explicitly allowed.

**Goal:** Introduce a small `AutomationBackend` boundary so Web-KOBE owns exploration/recording while browser operation remains a replaceable backend.

**Architecture:** Extract the existing adapter protocol out of `web_kobe_explorer.py` into a focused backend interface module. Keep the current Playwright adapter behavior unchanged and make it the first concrete backend. Update tests and docs only enough to prove the boundary exists without widening scope.

**Tech Stack:** Python 3.11+, typing `Protocol`, pytest, existing Playwright-backed Web-KOBE adapter.

## Global Constraints

- Do not build a new general-purpose web agent.
- Reuse existing browser automation capability; keep Web-KOBE/SafeSym responsible for exploration strategy and graph recording.
- Preserve the current `web-kobe-explore` CLI behavior.
- Do not introduce new runtime dependencies.
- Do not rename public CLI commands in this task.
- Do not use subagents unless the user explicitly permits them.

---

## File Structure

- Create `src/ai_web_explorer/safesym_bridge/automation_backend.py`
  - Owns the backend protocol and shared type aliases.
  - Keeps backend concepts separate from graph exploration logic.

- Modify `src/ai_web_explorer/safesym_bridge/web_kobe_explorer.py`
  - Imports `AutomationBackend` instead of defining a local protocol.
  - Keeps `WebKobeExplorer` behavior unchanged.

- Modify `src/ai_web_explorer/safesym_bridge/web_kobe_playwright_adapter.py`
  - Optionally documents that `WebKobePlaywrightAdapter` is the first concrete backend.
  - No behavior change required.

- Create or modify `tests/safesym_bridge/test_automation_backend.py`
  - Verifies the protocol is importable.
  - Verifies `WebKobePlaywrightAdapter` structurally satisfies the backend contract.
  - Verifies `WebKobeExplorer` accepts an `AutomationBackend`.

- Modify `docs/current-project-overview.md`
  - Add a short implementation note pointing to the new backend interface.

---

### Task 1: Extract the AutomationBackend protocol

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/automation_backend.py`
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_explorer.py`
- Test: `tests/safesym_bridge/test_automation_backend.py`

**Interfaces:**
- Produces:
  - `InteractableRecord = dict[str, Any]`
  - `@runtime_checkable class AutomationBackend(Protocol)`
  - `AutomationBackend.app_name: str`
  - `AutomationBackend.observe_state() -> StateSnapshot`
  - `AutomationBackend.list_interactables(state: StateSnapshot) -> list[InteractableRecord]`
  - `AutomationBackend.execute(action: BrowserAction) -> bool`
- Consumes:
  - `StateSnapshot` from `ai_web_explorer.safesym_bridge.models`
  - `BrowserAction` from `ai_web_explorer.safesym_bridge.web_kobe_graph`

- [ ] **Step 1: Write the failing protocol import test**

Create `tests/safesym_bridge/test_automation_backend.py` with:

```python
from __future__ import annotations

from typing import get_origin

from ai_web_explorer.safesym_bridge.automation_backend import (
    AutomationBackend,
    InteractableRecord,
)


def test_automation_backend_protocol_is_importable() -> None:
    assert AutomationBackend.__name__ == "AutomationBackend"
    assert get_origin(InteractableRecord) is dict
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_automation_backend.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'ai_web_explorer.safesym_bridge.automation_backend'
```

- [ ] **Step 3: Add the backend protocol module**

Create `src/ai_web_explorer/safesym_bridge/automation_backend.py`:

```python
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.web_kobe_graph import BrowserAction

InteractableRecord = dict[str, Any]


@runtime_checkable
class AutomationBackend(Protocol):
    """Browser operation boundary used by Web-KOBE exploration.

    Implementations operate the browser. They do not own exploration strategy,
    graph recording, state-delta inference, or SafeSym/PDDL projection.
    """

    app_name: str

    async def observe_state(self) -> StateSnapshot:
        ...

    async def list_interactables(
        self,
        state: StateSnapshot,
    ) -> list[InteractableRecord]:
        ...

    async def execute(self, action: BrowserAction) -> bool:
        ...
```

- [ ] **Step 4: Replace the local protocol in `web_kobe_explorer.py`**

Change imports near the top of `src/ai_web_explorer/safesym_bridge/web_kobe_explorer.py` from:

```python
from typing import Any, Protocol
```

to:

```python
from typing import Any
```

Add:

```python
from ai_web_explorer.safesym_bridge.automation_backend import AutomationBackend
```

Delete the local `class WebKobeAdapter(Protocol): ...` block.

Change the constructor annotation from:

```python
adapter: WebKobeAdapter,
```

to:

```python
adapter: AutomationBackend,
```

- [ ] **Step 5: Run the new focused test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_automation_backend.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Run existing explorer tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_web_kobe_explorer.py tests\safesym_bridge\test_web_kobe_controller.py -q
```

Expected:

```text
passed
```

- [ ] **Step 7: Commit Task 1**

Run:

```powershell
git add src\ai_web_explorer\safesym_bridge\automation_backend.py src\ai_web_explorer\safesym_bridge\web_kobe_explorer.py tests\safesym_bridge\test_automation_backend.py
git commit -m "refactor: extract automation backend protocol"
```

---

### Task 2: Mark Playwright adapter as the first backend implementation

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_playwright_adapter.py`
- Modify: `tests/safesym_bridge/test_automation_backend.py`

**Interfaces:**
- Consumes:
  - `AutomationBackend` from `automation_backend.py`
  - `WebKobePlaywrightAdapter` from `web_kobe_playwright_adapter.py`
- Produces:
  - A runtime protocol compatibility test for `WebKobePlaywrightAdapter`.

- [ ] **Step 1: Add the Playwright compatibility test**

Append to `tests/safesym_bridge/test_automation_backend.py`:

```python
from ai_web_explorer.safesym_bridge.web_kobe_playwright_adapter import (
    WebKobePlaywrightAdapter,
)


class _FakePage:
    url = "http://example.test/"


def test_playwright_adapter_satisfies_automation_backend_protocol() -> None:
    adapter = WebKobePlaywrightAdapter(_FakePage(), app_name="fixture")

    assert isinstance(adapter, AutomationBackend)
```

- [ ] **Step 2: Run the compatibility test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_automation_backend.py::test_playwright_adapter_satisfies_automation_backend_protocol -q
```

Expected:

```text
1 passed
```

If this fails because `AutomationBackend` is not `@runtime_checkable`, add `@runtime_checkable` exactly as shown in Task 1.

- [ ] **Step 3: Add a class docstring to `WebKobePlaywrightAdapter`**

In `src/ai_web_explorer/safesym_bridge/web_kobe_playwright_adapter.py`, update:

```python
class WebKobePlaywrightAdapter:
```

to:

```python
class WebKobePlaywrightAdapter:
    """Playwright-backed AutomationBackend for Web-KOBE exploration.

    This class operates the browser and exposes grounded page observations and
    actions. Exploration strategy, graph recording, and SafeSym/PDDL projection
    stay in the Web-KOBE layer.
    """
```

- [ ] **Step 4: Run focused adapter tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_automation_backend.py tests\safesym_bridge\test_web_kobe_playwright_adapter.py -q
```

Expected:

```text
passed
```

- [ ] **Step 5: Commit Task 2**

Run:

```powershell
git add src\ai_web_explorer\safesym_bridge\web_kobe_playwright_adapter.py tests\safesym_bridge\test_automation_backend.py
git commit -m "test: mark playwright adapter as automation backend"
```

---

### Task 3: Document the implemented boundary

**Files:**
- Modify: `docs/current-project-overview.md`
- Optional modify: `docs/superpowers/specs/2026-07-15-automation-backend-boundary-design.md`
- Optional modify: `docs/superpowers/specs/2026-07-15-automation-backend-boundary-design.zh.md`

**Interfaces:**
- Consumes:
  - Implemented module path `src/ai_web_explorer/safesym_bridge/automation_backend.py`
- Produces:
  - Documentation that points developers to the actual backend protocol.

- [ ] **Step 1: Update current project overview**

In `docs/current-project-overview.md`, after the automation backend boundary paragraph, add:

```markdown
The concrete backend boundary lives in:

```text
src/ai_web_explorer/safesym_bridge/automation_backend.py
```

Current implementations should satisfy `AutomationBackend`. The first concrete
implementation is `WebKobePlaywrightAdapter`, which wraps Playwright browser
operation while leaving exploration policy and graph recording in
`WebKobeExplorer`.
```

- [ ] **Step 2: Run a doc grep sanity check**

Run:

```powershell
Select-String -Path docs\current-project-overview.md -Pattern "automation_backend.py","AutomationBackend","WebKobePlaywrightAdapter"
```

Expected:

```text
docs/current-project-overview.md contains all three terms
```

- [ ] **Step 3: Commit Task 3**

Run:

```powershell
git add docs\current-project-overview.md
git commit -m "docs: point overview to automation backend interface"
```

---

### Task 4: Regression check for current DOM-first path

**Files:**
- No source changes expected.

**Interfaces:**
- Consumes:
  - `AutomationBackend`
  - `WebKobeExplorer`
  - `WebKobePlaywrightAdapter`
- Produces:
  - Verification that the refactor did not break the current exploration path.

- [ ] **Step 1: Run focused SafeSym bridge tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_automation_backend.py tests\safesym_bridge\test_web_kobe_explorer.py tests\safesym_bridge\test_web_kobe_controller.py tests\safesym_bridge\test_web_kobe_playwright_adapter.py tests\safesym_bridge\test_web_kobe_grounded_exploration.py -q
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
