# Simple Grounded Web Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Subagent-driven execution is intentionally not the default for this project because the user requested single-agent, token-saving work unless explicitly allowed.

**Goal:** Add a small `SimpleGroundedWebAgent` facade that runs the existing DOM-grounded Web-KOBE exploration loop as a clear no-LLM baseline agent.

**Architecture:** Do not duplicate exploration logic. The new agent composes `AutomationBackend`, `WebKobeExplorer`, and `WebKobeExplorationController`, then exposes a simple `run(max_steps)` method. This makes the baseline agent explicit while keeping browser operation, exploration policy, state recording, and graph construction in their existing low-coupling modules.

**Tech Stack:** Python 3.11+, pytest/anyio, existing `AutomationBackend`, `WebKobeExplorer`, `WebKobeExplorationController`, and `DeterministicSemanticAssistor`.

## Global Constraints

- Do not introduce LLM action selection in this step.
- Do not duplicate `WebKobeExplorer` or `WebKobeExplorationController` logic.
- Do not change the existing `web-kobe-explore` CLI behavior in this step.
- Do not introduce new runtime dependencies.
- Keep this as a baseline agent for DOM-grounded operation and recording.
- Treat broader duplicate-code cleanup as follow-up refactoring, not part of this facade task.
- Do not use subagents unless the user explicitly permits them.

---

## File Structure

- Create `src/ai_web_explorer/safesym_bridge/simple_grounded_web_agent.py`
  - Owns the small facade class.
  - Accepts an `AutomationBackend`.
  - Internally constructs `WebKobeExplorer` and `WebKobeExplorationController`.
  - Exposes `run(max_steps: int) -> WebKobeExplorationResult`.

- Create `tests/safesym_bridge/test_simple_grounded_web_agent.py`
  - Uses a fake `AutomationBackend`; no real browser needed.
  - Verifies that `SimpleGroundedWebAgent` executes grounded actions and records a delta.
  - Verifies that it stops when no actions are available.

- Modify `docs/current-project-overview.md`
  - Adds a short note explaining that `SimpleGroundedWebAgent` is the explicit no-LLM baseline agent facade.

---

## Refactoring Note

The project currently contains overlapping structures from several historical directions:

- original `ExploreLoop` / `Executor` / `Describer`;
- Web-KOBE explorer/controller;
- Playwright adapter;
- Web-KOBE collector sidecar;
- sync and async action execution paths.

This plan does not clean all of that up. The safer rule is:

```text
Only refactor duplication when a new feature naturally touches that boundary.
```

For this task, the useful cleanup is naming and composition: make the baseline agent explicit without copying existing logic.

---

### Task 1: Add the SimpleGroundedWebAgent facade

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/simple_grounded_web_agent.py`
- Create: `tests/safesym_bridge/test_simple_grounded_web_agent.py`

**Interfaces:**
- Consumes:
  - `AutomationBackend` from `ai_web_explorer.safesym_bridge.automation_backend`
  - `WebKobeExplorer` from `ai_web_explorer.safesym_bridge.web_kobe_explorer`
  - `WebKobeExplorationController` and `WebKobeExplorationResult` from `ai_web_explorer.safesym_bridge.web_kobe_controller`
  - `DeterministicSemanticAssistor` and `SemanticAssistor`
- Produces:
  - `class SimpleGroundedWebAgent`
  - `SimpleGroundedWebAgent.__init__(backend: AutomationBackend, *, semantic_assistor: SemanticAssistor | None = None) -> None`
  - `SimpleGroundedWebAgent.run(max_steps: int = 1) -> WebKobeExplorationResult`

- [ ] **Step 1: Write the failing tests**

Create `tests/safesym_bridge/test_simple_grounded_web_agent.py`:

```python
from __future__ import annotations

import pytest

from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.simple_grounded_web_agent import (
    SimpleGroundedWebAgent,
)
from ai_web_explorer.safesym_bridge.web_kobe_graph import BrowserAction


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeBackend:
    app_name = "fake_shop"

    def __init__(self) -> None:
        self.executed: list[BrowserAction] = []
        self.state_index = 0

    async def observe_state(self) -> StateSnapshot:
        signatures = [
            {"cart_count": 0},
            {"cart_count": 1},
        ]
        signature = signatures[min(self.state_index, len(signatures) - 1)]
        return StateSnapshot(
            page_id="shop",
            url="http://example.test/shop",
            title="Shop",
            signature=signature,
        )

    async def list_interactables(self, state: StateSnapshot) -> list[dict]:
        if self.executed:
            return [
                {
                    "semantic_id": "add_to_cart",
                    "description": "Add to cart",
                    "locator": "#add",
                    "action_kind": "click",
                    "input_values": {},
                    "explored": True,
                }
            ]
        return [
            {
                "semantic_id": "add_to_cart",
                "description": "Add to cart",
                "locator": "#add",
                "action_kind": "click",
                "input_values": {},
                "explored": False,
            }
        ]

    async def execute(self, action: BrowserAction) -> bool:
        self.executed.append(action)
        self.state_index = 1
        return True


class NoActionBackend(FakeBackend):
    async def list_interactables(self, state: StateSnapshot) -> list[dict]:
        return []


@pytest.mark.anyio
async def test_simple_grounded_agent_executes_one_grounded_action_and_records_delta():
    backend = FakeBackend()
    agent = SimpleGroundedWebAgent(backend)

    result = await agent.run(max_steps=1)

    assert len(backend.executed) == 1
    assert backend.executed[0].locator == "#add"
    assert result.summary.steps_completed == 1
    assert result.summary.stop_reason == "max_steps"
    assert result.graph.edges[0].status == "verified"
    assert result.graph.edges[0].schema_delta == {
        "cart_count": {"before": 0, "after": 1}
    }


@pytest.mark.anyio
async def test_simple_grounded_agent_stops_when_no_action_is_available():
    agent = SimpleGroundedWebAgent(NoActionBackend())

    result = await agent.run(max_steps=3)

    assert result.summary.steps_completed == 0
    assert result.summary.stop_reason == "no_available_action"
    assert result.graph.edges == []
```

- [ ] **Step 2: Run tests and verify they fail because the module does not exist**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_simple_grounded_web_agent.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'ai_web_explorer.safesym_bridge.simple_grounded_web_agent'
```

- [ ] **Step 3: Implement the minimal facade**

Create `src/ai_web_explorer/safesym_bridge/simple_grounded_web_agent.py`:

```python
from __future__ import annotations

from ai_web_explorer.safesym_bridge.automation_backend import AutomationBackend
from ai_web_explorer.safesym_bridge.web_kobe_controller import (
    WebKobeExplorationController,
    WebKobeExplorationResult,
)
from ai_web_explorer.safesym_bridge.web_kobe_explorer import WebKobeExplorer
from ai_web_explorer.safesym_bridge.web_semantic_assistor import (
    DeterministicSemanticAssistor,
    SemanticAssistor,
)


class SimpleGroundedWebAgent:
    """No-LLM baseline agent for DOM-grounded web exploration.

    The agent is intentionally a facade over the existing Web-KOBE exploration
    engine. It does not own browser automation, selector generation, graph
    recording, or SafeSym/PDDL projection.
    """

    def __init__(
        self,
        backend: AutomationBackend,
        *,
        semantic_assistor: SemanticAssistor | None = None,
    ) -> None:
        self.backend = backend
        self.semantic_assistor = semantic_assistor or DeterministicSemanticAssistor(
            app=backend.app_name
        )
        self.explorer = WebKobeExplorer(
            adapter=backend,
            semantic_assistor=self.semantic_assistor,
        )
        self.controller = WebKobeExplorationController(self.explorer)

    async def run(self, *, max_steps: int = 1) -> WebKobeExplorationResult:
        return await self.controller.run(max_steps=max_steps)
```

- [ ] **Step 4: Run focused tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_simple_grounded_web_agent.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Run existing Web-KOBE controller/explorer tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_web_kobe_explorer.py tests\safesym_bridge\test_web_kobe_controller.py tests\safesym_bridge\test_automation_backend.py -q
```

Expected:

```text
passed
```

- [ ] **Step 6: Commit Task 1**

Run:

```powershell
git add src\ai_web_explorer\safesym_bridge\simple_grounded_web_agent.py tests\safesym_bridge\test_simple_grounded_web_agent.py
git commit -m "feat: add simple grounded web agent facade"
```

---

### Task 2: Document the baseline agent and refactoring rule

**Files:**
- Modify: `docs/current-project-overview.md`

**Interfaces:**
- Consumes:
  - Implemented module path `src/ai_web_explorer/safesym_bridge/simple_grounded_web_agent.py`
- Produces:
  - Documentation that identifies `SimpleGroundedWebAgent` as the no-LLM baseline.
  - Documentation that duplicate-structure cleanup should happen opportunistically at touched boundaries.

- [ ] **Step 1: Update current project overview**

In `docs/current-project-overview.md`, near the Web-KOBE generic exploration section, add:

```markdown
The explicit no-LLM baseline agent facade lives in:

```text
src/ai_web_explorer/safesym_bridge/simple_grounded_web_agent.py
```

`SimpleGroundedWebAgent` composes `AutomationBackend`,
`WebKobeExplorer`, and `WebKobeExplorationController`. It exists to make the
baseline agent concept clear without duplicating the Web-KOBE exploration
engine. It observes grounded candidates, executes the simple first-unexplored
policy, and records before/action/after deltas through the existing graph path.

There are still overlapping structures from the original explorer, Web-KOBE
collector, Playwright adapters, and sync/async action executors. Refactoring
should happen gradually when a feature touches a boundary, not as a broad
rewrite.
```

- [ ] **Step 2: Run a doc grep sanity check**

Run:

```powershell
Select-String -Path docs\current-project-overview.md -Pattern "SimpleGroundedWebAgent","simple_grounded_web_agent.py","first-unexplored","overlapping structures"
```

Expected:

```text
docs/current-project-overview.md contains all four terms
```

- [ ] **Step 3: Commit Task 2**

Run:

```powershell
git add docs\current-project-overview.md
git commit -m "docs: document simple grounded baseline agent"
```

---

### Task 3: Regression check

**Files:**
- No source changes expected.

- [ ] **Step 1: Run focused non-browser tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\safesym_bridge\test_simple_grounded_web_agent.py tests\safesym_bridge\test_legacy_action_executor.py tests\safesym_bridge\test_automation_backend.py tests\safesym_bridge\test_web_kobe_explorer.py tests\safesym_bridge\test_web_kobe_controller.py tests\safesym_bridge\test_web_kobe_playwright_adapter.py -q
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

