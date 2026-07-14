# Real Playwright Web-KOBE Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project preference:** The user requested single-agent, token-conscious work by default. Use Inline Execution unless the user explicitly allows subagents.

**Goal:** Connect the current Web-KOBE graph skeleton to a real Playwright-controlled page so one real browser action can produce a verified `WebKobeGraph` edge and delta.

**Architecture:** Add a Playwright-backed adapter that satisfies the existing `WebKobeAdapter` protocol. Keep the adapter deterministic in v1: local DOM extraction, simple cart-count state extraction, basic `click`/`fill`/`select` execution, and a runner/CLI that writes graph JSON.

**Tech Stack:** Python 3.11, Playwright async API, existing `dom_observer.py`, existing `web_action_extractor.py`, existing `WebKobeExplorer`, pytest with `anyio`, local HTML fixtures.

## Global Constraints

- Preserve the existing `WebObservedGraph -> PDDL -> SafeSym` SauceDemo path.
- Do not add LLM/VLM calls in this implementation slice.
- Use a controlled local fixture page for real browser tests; do not depend on public websites.
- Real browser tests must be skipped unless explicitly enabled by environment variable.
- Keep SafeSym responsible for safety policy.
- Use `.\.venv\Scripts\python.exe -m pytest` in this workspace.
- Do not use subagents unless the user explicitly allows them.

---

## File Structure

- Create `src/ai_web_explorer/safesym_bridge/web_kobe_playwright_adapter.py`
  - Real Playwright adapter implementing `observe_state()`, `list_interactables()`, and `execute(...)`.
  - Uses `extract_dom_interactables(page)` and `browser_actions_from_candidates(...)`.

- Modify `src/ai_web_explorer/safesym_bridge/browser_runner.py`
  - Add `run_web_kobe_exploration(...)`.

- Modify `src/ai_web_explorer/safesym_bridge/cli.py`
  - Add `web-kobe-explore`.

- Create `tests/safesym_bridge/test_web_kobe_playwright_adapter.py`
  - Unit-style tests with fake Playwright page/locator objects.

- Create `tests/safesym_bridge/test_web_kobe_playwright_integration.py`
  - Real Playwright fixture-page smoke test, skipped unless enabled.

- Modify `tests/safesym_bridge/test_browser_runner.py`
  - Add async-callable test for `run_web_kobe_exploration`.

- Modify `tests/safesym_bridge/test_cli.py`
  - Add CLI monkeypatch test for `web-kobe-explore`.

- Modify docs:
  - `docs/current-project-overview.md`
  - `docs/safesym-bridge.md`

---

### Task 1: WebKobePlaywrightAdapter

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/web_kobe_playwright_adapter.py`
- Test: `tests/safesym_bridge/test_web_kobe_playwright_adapter.py`

**Interfaces:**
- Consumes:
  - `StateSnapshot` from `models.py`
  - `BrowserAction` from `web_kobe_graph.py`
  - `extract_dom_interactables(page)` from `dom_observer.py`
  - `browser_actions_from_candidates(candidates)` from `web_action_extractor.py`
- Produces:
  - `WebKobePlaywrightAdapter(page, app_name="web", page_id=None)`
  - `await observe_state() -> StateSnapshot`
  - `await list_interactables(state: StateSnapshot) -> list[dict[str, Any]]`
  - `await execute(action: BrowserAction) -> bool`

- [ ] **Step 1: Write failing adapter tests**

Create `tests/safesym_bridge/test_web_kobe_playwright_adapter.py`:

```python
import pytest

from ai_web_explorer.safesym_bridge.dom_observer import DomInteractableCandidate
from ai_web_explorer.safesym_bridge.web_kobe_graph import BrowserAction
from ai_web_explorer.safesym_bridge.web_kobe_playwright_adapter import (
    WebKobePlaywrightAdapter,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeTextLocator:
    def __init__(self, text: str, count_value: int = 1):
        self.text = text
        self.count_value = count_value

    async def count(self):
        return self.count_value

    @property
    def first(self):
        return self

    async def inner_text(self):
        return self.text


class FakeActionLocator:
    def __init__(self):
        self.clicked = False
        self.filled = []
        self.selected = []

    @property
    def first(self):
        return self

    async def click(self):
        self.clicked = True

    async def fill(self, value):
        self.filled.append(value)

    async def select_option(self, value):
        self.selected.append(value)


class FakePage:
    def __init__(self):
        self.url = "https://example.test/shop"
        self.action_locator = FakeActionLocator()
        self.waits = []

    async def title(self):
        return "Fixture Shop"

    def locator(self, selector):
        if selector == '[data-state="cart-count"]':
            return FakeTextLocator("1")
        if selector == "#cart-count":
            return FakeTextLocator("", count_value=0)
        return self.action_locator

    async def wait_for_timeout(self, ms):
        self.waits.append(ms)


@pytest.mark.anyio
async def test_observe_state_reads_title_url_and_cart_count():
    adapter = WebKobePlaywrightAdapter(
        FakePage(),
        app_name="fixture",
        page_id="fixture_shop",
    )

    snapshot = await adapter.observe_state()

    assert snapshot.page_id == "fixture_shop"
    assert snapshot.url == "https://example.test/shop"
    assert snapshot.title == "Fixture Shop"
    assert snapshot.signature == {"cart_count": 1, "cart_nonempty": True}


@pytest.mark.anyio
async def test_list_interactables_uses_dom_candidates(monkeypatch):
    async def fake_extract_dom_interactables(page):
        return [
            DomInteractableCandidate(
                id="dom_001",
                kind="button",
                locator='button[data-test="add-to-cart"]',
                locator_strategy="css",
                name="Add to cart",
                visible=True,
                enabled=True,
                metadata={"data-test": "add-to-cart"},
            )
        ]

    monkeypatch.setattr(
        "ai_web_explorer.safesym_bridge.web_kobe_playwright_adapter.extract_dom_interactables",
        fake_extract_dom_interactables,
    )
    adapter = WebKobePlaywrightAdapter(FakePage(), page_id="fixture_shop")
    state = await adapter.observe_state()

    interactables = await adapter.list_interactables(state)

    assert interactables == [
        {
            "semantic_id": "button_add_to_cart",
            "description": "Add to cart",
            "locator": 'button[data-test="add-to-cart"]',
            "action_kind": "click",
            "explored": False,
        }
    ]


@pytest.mark.anyio
async def test_execute_click_fill_and_select_actions():
    page = FakePage()
    adapter = WebKobePlaywrightAdapter(page, page_id="fixture_shop")

    assert await adapter.execute(BrowserAction("click", "#add", "add")) is True
    assert page.action_locator.clicked is True

    assert await adapter.execute(
        BrowserAction("fill", "#name", "fill_name", {"value": "Alice"})
    ) is True
    assert page.action_locator.filled == ["Alice"]

    assert await adapter.execute(
        BrowserAction("select", "#sort", "select_sort", {"value": "price"})
    ) is True
    assert page.action_locator.selected == ["price"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_playwright_adapter.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `web_kobe_playwright_adapter`.

- [ ] **Step 3: Implement adapter**

Create `src/ai_web_explorer/safesym_bridge/web_kobe_playwright_adapter.py`:

```python
from __future__ import annotations

import re
from typing import Any

from ai_web_explorer.safesym_bridge.dom_observer import extract_dom_interactables
from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.web_action_extractor import (
    browser_actions_from_candidates,
)
from ai_web_explorer.safesym_bridge.web_kobe_graph import BrowserAction


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned or "page"


async def _optional_inner_text(page, selector: str) -> str | None:
    locator = page.locator(selector)
    if await locator.count() == 0:
        return None
    return (await locator.first.inner_text()).strip()


def _first_input_value(values: dict[str, str]) -> str | None:
    if not values:
        return None
    return next(iter(values.values()))


class WebKobePlaywrightAdapter:
    def __init__(
        self,
        page,
        *,
        app_name: str = "web",
        page_id: str | None = None,
    ):
        self.page = page
        self.app_name = app_name
        self.page_id = page_id

    async def observe_state(self) -> StateSnapshot:
        title = await self.page.title()
        page_id = self.page_id or _slug(title or self.page.url)
        signature: dict[str, Any] = {}

        cart_text = await _optional_inner_text(self.page, '[data-state="cart-count"]')
        if cart_text is None:
            cart_text = await _optional_inner_text(self.page, "#cart-count")
        if cart_text is not None:
            match = re.search(r"-?\d+", cart_text)
            cart_count = int(match.group(0)) if match else 0
            signature["cart_count"] = cart_count
            signature["cart_nonempty"] = cart_count > 0

        return StateSnapshot(
            page_id=page_id,
            url=self.page.url,
            title=title,
            signature=signature,
        )

    async def list_interactables(
        self,
        state: StateSnapshot,
    ) -> list[dict[str, Any]]:
        candidates = await extract_dom_interactables(self.page)
        actions = browser_actions_from_candidates(candidates)
        return [
            {
                "semantic_id": action.semantic_id,
                "description": action.description,
                "locator": action.locator,
                "action_kind": action.action_kind,
                "explored": False,
            }
            for action in actions
        ]

    async def execute(self, action: BrowserAction) -> bool:
        if action.locator is None:
            return False
        locator = self.page.locator(action.locator).first
        try:
            if action.action_kind == "click":
                await locator.click()
            elif action.action_kind == "fill":
                await locator.fill(_first_input_value(action.input_values) or "test")
            elif action.action_kind == "select":
                value = _first_input_value(action.input_values)
                if value is None:
                    return False
                await locator.select_option(value)
            else:
                return False
            await self.page.wait_for_timeout(100)
            return True
        except Exception:
            return False
```

- [ ] **Step 4: Run adapter tests**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_playwright_adapter.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/web_kobe_playwright_adapter.py tests/safesym_bridge/test_web_kobe_playwright_adapter.py
git commit -m "feat: add Playwright Web-KOBE adapter"
```

---

### Task 2: Real Playwright Fixture Smoke Test

**Files:**
- Create: `tests/safesym_bridge/test_web_kobe_playwright_integration.py`

**Interfaces:**
- Consumes:
  - `WebKobePlaywrightAdapter`
  - `WebKobeExplorer`
  - `DeterministicSemanticAssistor`
- Produces:
  - Skipped-by-default real Playwright test proving a browser click records a self-loop delta.

- [ ] **Step 1: Write failing integration test**

Create `tests/safesym_bridge/test_web_kobe_playwright_integration.py`:

```python
import os

import pytest

from ai_web_explorer.safesym_bridge.web_kobe_explorer import WebKobeExplorer
from ai_web_explorer.safesym_bridge.web_kobe_playwright_adapter import (
    WebKobePlaywrightAdapter,
)
from ai_web_explorer.safesym_bridge.web_semantic_assistor import (
    DeterministicSemanticAssistor,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


FIXTURE_HTML = """
<!doctype html>
<html>
  <head><title>Fixture Shop</title></head>
  <body>
    <main>
      <h1>Fixture Shop</h1>
      <p>Cart: <span id="cart-count" data-state="cart-count">0</span></p>
      <section class="product-card">
        <h2>Example Product</h2>
        <button id="add-to-cart" data-test="add-to-cart">Add to cart</button>
      </section>
    </main>
    <script>
      document.querySelector("#add-to-cart").addEventListener("click", () => {
        document.querySelector("#cart-count").textContent = "1";
      });
    </script>
  </body>
</html>
"""


@pytest.mark.skipif(
    os.getenv("RUN_WEB_KOBE_BROWSER_TEST") != "1",
    reason="Set RUN_WEB_KOBE_BROWSER_TEST=1 to run the real Web-KOBE browser test.",
)
@pytest.mark.anyio
async def test_playwright_web_kobe_explorer_records_real_self_loop_delta():
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.set_content(FIXTURE_HTML)
            adapter = WebKobePlaywrightAdapter(
                page,
                app_name="fixture",
                page_id="fixture_shop",
            )
            explorer = WebKobeExplorer(
                adapter=adapter,
                semantic_assistor=DeterministicSemanticAssistor(app="fixture"),
            )

            graph = await explorer.explore_one_step()

            assert graph.start_node_id == "fixture_shop"
            assert len(graph.edges) == 1
            edge = graph.edges[0]
            assert edge.source_node_id == "fixture_shop"
            assert edge.target_node_id == "fixture_shop"
            assert edge.schema_delta == {
                "cart_count": {"before": 0, "after": 1},
                "cart_nonempty": {"before": False, "after": True},
            }
            assert {
                delta.field: (delta.before, delta.after)
                for delta in edge.observed_delta
            } == {
                "cart_count": (0, 1),
                "cart_nonempty": (False, True),
            }
        finally:
            await browser.close()
```

- [ ] **Step 2: Run skipped-by-default test**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_playwright_integration.py -v
```

Expected: SKIPPED unless `RUN_WEB_KOBE_BROWSER_TEST=1` is set.

- [ ] **Step 3: Optionally run real browser smoke test when browser is available**

Run:

```bash
$env:RUN_WEB_KOBE_BROWSER_TEST='1'
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_playwright_integration.py -v
```

Expected when Playwright browser dependencies are installed: PASS.

If Playwright browser binaries are missing, leave the skipped-by-default test in place and report the dependency gap. Do not install browsers unless the user explicitly approves.

- [ ] **Step 4: Commit**

```bash
git add tests/safesym_bridge/test_web_kobe_playwright_integration.py
git commit -m "test: add Web-KOBE Playwright smoke fixture"
```

---

### Task 3: Browser Runner Support

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Modify: `tests/safesym_bridge/test_browser_runner.py`

**Interfaces:**
- Consumes:
  - `WebKobePlaywrightAdapter`
  - `WebKobeExplorer`
  - `DeterministicSemanticAssistor`
  - `write_web_kobe_graph(graph, output_path)`
- Produces:
  - `async def run_web_kobe_exploration(url, output_path, app_name="web", page_id=None, steps=1, headless=True) -> Path`

- [ ] **Step 1: Write failing browser runner test**

Append to `tests/safesym_bridge/test_browser_runner.py`:

```python
from ai_web_explorer.safesym_bridge.browser_runner import run_web_kobe_exploration


def test_run_web_kobe_exploration_is_async_callable():
    assert callable(run_web_kobe_exploration)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_browser_runner.py::test_run_web_kobe_exploration_is_async_callable -v
```

Expected: FAIL with import error or missing name.

- [ ] **Step 3: Implement browser runner**

Modify `src/ai_web_explorer/safesym_bridge/browser_runner.py` imports:

```python
from ai_web_explorer.safesym_bridge.web_kobe_explorer import WebKobeExplorer
from ai_web_explorer.safesym_bridge.web_kobe_playwright_adapter import (
    WebKobePlaywrightAdapter,
)
from ai_web_explorer.safesym_bridge.web_semantic_assistor import (
    DeterministicSemanticAssistor,
)
```

Add:

```python
async def run_web_kobe_exploration(
    url: str,
    output_path: Path,
    *,
    app_name: str = "web",
    page_id: str | None = None,
    steps: int = 1,
    headless: bool = True,
) -> Path:
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        page = await browser.new_page()
        try:
            await page.goto(url)
            adapter = WebKobePlaywrightAdapter(
                page,
                app_name=app_name,
                page_id=page_id,
            )
            explorer = WebKobeExplorer(
                adapter=adapter,
                semantic_assistor=DeterministicSemanticAssistor(app=app_name),
            )
            graph = None
            for _ in range(max(steps, 1)):
                graph = await explorer.explore_one_step()
            if graph is None:
                graph = explorer.manager.to_graph()
            write_web_kobe_graph(graph, output_path)
            return output_path
        finally:
            await browser.close()
```

- [ ] **Step 4: Run browser runner test**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_browser_runner.py::test_run_web_kobe_exploration_is_async_callable -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/browser_runner.py tests/safesym_bridge/test_browser_runner.py
git commit -m "feat: add Web-KOBE Playwright runner"
```

---

### Task 4: CLI Command

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Modify: `tests/safesym_bridge/test_cli.py`

**Interfaces:**
- Consumes:
  - `run_web_kobe_exploration(...)`
- Produces:
  - CLI command:
    - `web-kobe-explore --url <url> --output <path> --page-id <id> --app-name <name> --steps <n> [--headed]`

- [ ] **Step 1: Write failing CLI test**

Append to `tests/safesym_bridge/test_cli.py`:

```python
def test_main_web_kobe_explore_subcommand_runs_playwright_runner(
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "web_kobe_explored_graph.json"
    calls = []

    async def fake_run_web_kobe_exploration(
        url,
        output_path_arg,
        *,
        app_name="web",
        page_id=None,
        steps=1,
        headless=True,
    ):
        calls.append((url, output_path_arg, app_name, page_id, steps, headless))
        output_path_arg.write_text(
            '{"meta": {"schema_version": "web-kobe-graph-v1"}}',
            encoding="utf-8",
        )
        return output_path_arg

    monkeypatch.setattr(
        cli,
        "run_web_kobe_exploration",
        fake_run_web_kobe_exploration,
    )

    exit_code = main(
        [
            "web-kobe-explore",
            "--url",
            "http://127.0.0.1:8000/index.html",
            "--output",
            str(output_path),
            "--app-name",
            "fixture",
            "--page-id",
            "fixture_shop",
            "--steps",
            "2",
            "--headed",
        ]
    )

    assert exit_code == 0
    assert calls == [
        (
            "http://127.0.0.1:8000/index.html",
            output_path,
            "fixture",
            "fixture_shop",
            2,
            False,
        )
    ]
```

- [ ] **Step 2: Run CLI test to verify it fails**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_cli.py::test_main_web_kobe_explore_subcommand_runs_playwright_runner -v
```

Expected: FAIL because command/import does not exist.

- [ ] **Step 3: Implement CLI command**

Modify `src/ai_web_explorer/safesym_bridge/cli.py` imports:

```python
from ai_web_explorer.safesym_bridge.browser_runner import (
    run_web_kobe_exploration,
)
```

Add parser:

```python
web_kobe_explore_parser = subparsers.add_parser(
    "web-kobe-explore",
    help="Run real Playwright Web-KOBE exploration and write graph JSON.",
)
web_kobe_explore_parser.add_argument("--url", required=True)
web_kobe_explore_parser.add_argument(
    "--output",
    type=Path,
    default=Path("outputs/web_kobe_explored_graph.json"),
)
web_kobe_explore_parser.add_argument("--app-name", default="web")
web_kobe_explore_parser.add_argument("--page-id", default=None)
web_kobe_explore_parser.add_argument("--steps", type=int, default=1)
web_kobe_explore_parser.add_argument(
    "--headed",
    action="store_true",
    help="Show the browser window while running exploration.",
)
```

Add handling before the debug fixed graph/PDDL branches:

```python
elif args.mode == "web-kobe-explore":
    output_path = asyncio.run(
        run_web_kobe_exploration(
            args.url,
            args.output,
            app_name=args.app_name,
            page_id=args.page_id,
            steps=args.steps,
            headless=not args.headed,
        )
    )
```

- [ ] **Step 4: Run CLI test**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_cli.py::test_main_web_kobe_explore_subcommand_runs_playwright_runner -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/cli.py tests/safesym_bridge/test_cli.py
git commit -m "feat: expose Web-KOBE Playwright explore CLI"
```

---

### Task 5: Documentation and Verification

**Files:**
- Modify: `docs/current-project-overview.md`
- Modify: `docs/safesym-bridge.md`

**Interfaces:**
- Consumes:
  - `web-kobe-explore` CLI command
  - skipped-by-default Playwright smoke test
- Produces:
  - Documentation showing real Playwright Web-KOBE exploration is available.

- [ ] **Step 1: Update current project overview**

Add this paragraph after the existing Web-KOBE debug command section in `docs/current-project-overview.md`:

```markdown
A real Playwright-backed Web-KOBE exploration command is also available for
controlled local or fixture pages:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-explore \
  --url http://127.0.0.1:8000/index.html \
  --output outputs/web_kobe_explored_graph.json \
  --page-id fixture_shop \
  --steps 1
```

This command opens the page with Playwright, observes local state, extracts DOM
interactables, executes a small number of actions, and records browser-grounded
Web-KOBE graph edges.
```

- [ ] **Step 2: Update SafeSym bridge doc**

Add this paragraph to the `Generic Web-KOBE Direction` section in `docs/safesym-bridge.md`:

```markdown
For a real Playwright-backed exploration run against a controlled page:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-explore \
  --url http://127.0.0.1:8000/index.html \
  --output outputs/web_kobe_explored_graph.json \
  --page-id fixture_shop \
  --steps 1
```

The first version is intentionally local and deterministic. It is meant to
prove the browser-grounded graph loop before adding LLM/VLM semantic assistance.
```

- [ ] **Step 3: Run focused tests**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_playwright_adapter.py tests/safesym_bridge/test_web_kobe_playwright_integration.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_cli.py -v
```

Expected: PASS for unit/CLI tests, with the real browser integration test SKIPPED unless `RUN_WEB_KOBE_BROWSER_TEST=1`.

- [ ] **Step 4: Run full regression**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge -v
```

Expected: PASS, with existing browser smoke tests skipped unless enabled.

- [ ] **Step 5: Commit docs**

```bash
git add docs/current-project-overview.md docs/safesym-bridge.md
git commit -m "docs: document Playwright Web-KOBE exploration"
```

---

## Self-Review Checklist

- Spec coverage:
  - Real Playwright adapter: Task 1.
  - Fixture self-loop smoke test: Task 2.
  - Browser runner: Task 3.
  - CLI command: Task 4.
  - Docs and full regression: Task 5.

- Scope decision:
  - The plan intentionally excludes LLM/VLM, automatic ActionTarget inference, embedding state matching, graph audit, coverage checkpoints, and parameterized PDDL.

- Type consistency:
  - `WebKobePlaywrightAdapter` consumes and returns the exact `WebKobeAdapter` protocol types used by `WebKobeExplorer`.
  - `run_web_kobe_exploration(...)` is introduced in Task 3 and consumed by Task 4.
  - The CLI uses `--app-name`, `--page-id`, `--steps`, and `--headed` consistently with the runner signature.

## Execution Handoff

Implement task-by-task with TDD. Because the user requested single-agent work
by default, Inline Execution is the expected implementation mode unless the
user explicitly allows subagents.
