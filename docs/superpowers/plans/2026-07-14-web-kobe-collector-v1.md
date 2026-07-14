# Web-KOBE Collector v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first Web-KOBE collector that reuses the original `ai-web-explorer` exploration flow while collecting Web-KOBE/SafeSym-oriented state, action, transition, delta, and evidence data during exploration.

**Architecture:** Do not build another exploration engine. Keep `ExploreLoop`, `Describer`, and `Executor` responsible for browser exploration and action execution. Add a hook-based collector layer and a minimal observation snapshot so exploration events can be recorded directly into `WebKobeGraph` without relying on the old `WebState` output as the primary data source.

**Tech Stack:** Python 3.11, existing synchronous Playwright-based `ai_web_explorer.loop`, existing `webstate.Action` / `webstate.WebState`, existing `safesym_bridge.web_kobe_graph` models, pytest.

## Global Constraints

- Reuse the original `ai-web-explorer` exploration method instead of expanding a separate Web-KOBE explorer.
- Do not depend on real LLM calls in default tests.
- Do not depend on real browser launches in default tests.
- Keep state merging simple for v1; collect richer information first.
- Keep SafeSym responsible for safety policy.
- Redact credentials and sensitive input values in execution traces.
- Use `.\.venv\Scripts\python.exe -m pytest` in this workspace.
- Do not use subagents unless the user explicitly allows them.

---

## File Structure

- Create `src/ai_web_explorer/safesym_bridge/web_kobe_collector.py`
  - Defines collector event inputs, a no-op collector, and `WebKobeCollector`.
  - Owns `WebKobeGraphManager`.
  - Converts observed exploration events into `WebKobeNode` and `WebKobeEdge`.

- Create `src/ai_web_explorer/safesym_bridge/web_kobe_observer.py`
  - Defines a lightweight `WebKobeObservation`.
  - Provides deterministic helpers for extracting page frame, state indicators,
    interactable evidence, and URL/title/heading data from a Playwright-like page.
  - Must be testable with fake page objects.

- Modify `src/ai_web_explorer/loop.py`
  - Add an optional collector to `LoopConfig` / `ExploreLoop`.
  - Call collector hooks during `_explore()` without changing exploration behavior.

- Modify `src/ai_web_explorer/__init__.py`
  - Later task only: optionally wire a CLI flag for collector output if the hook
    integration is stable. Do not make this the first task.

- Create `tests/safesym_bridge/test_web_kobe_observer.py`
  - Tests observation extraction without real browser.

- Create `tests/safesym_bridge/test_web_kobe_collector.py`
  - Tests collector event handling and graph output without real browser or LLM.

- Create or modify `tests/test_loop_collector_hooks.py`
  - Tests that `ExploreLoop._explore()` emits hook calls using fake dependencies.

- Modify docs:
  - `docs/current-project-overview.md`
  - `docs/safesym-bridge.md`

---

### Task 1: Lightweight Web-KOBE Observation

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/web_kobe_observer.py`
- Create: `tests/safesym_bridge/test_web_kobe_observer.py`

**Interfaces:**
- Produces:
  - `WebKobeObservation`
  - `async_or_sync_title(page) -> str`
  - `observe_web_kobe_page(page, *, web_state_id: str | None = None, llm_title: str | None = None) -> WebKobeObservation`

The first implementation should support synchronous Playwright-like pages because the original `ExploreLoop` uses sync Playwright.

- [ ] **Step 1: Write failing observer tests**

Create `tests/safesym_bridge/test_web_kobe_observer.py`:

```python
from ai_web_explorer.safesym_bridge.web_kobe_observer import (
    observe_web_kobe_page,
)


class FakeLocator:
    def __init__(self, text="", count_value=1):
        self._text = text
        self._count = count_value
        self.first = self

    def count(self):
        return self._count

    def inner_text(self):
        return self._text


class FakePage:
    url = "https://example.test/products?utm_source=x"

    def title(self):
        return "Example Products"

    def locator(self, selector):
        if selector == "h1":
            return FakeLocator("Products")
        if selector == ".shopping_cart_badge":
            return FakeLocator("", count_value=0)
        return FakeLocator("", count_value=0)


def test_observe_web_kobe_page_extracts_basic_page_frame():
    observation = observe_web_kobe_page(
        FakePage(),
        web_state_id="ws-123",
        llm_title="Product listing",
    )

    assert observation.url == "https://example.test/products?utm_source=x"
    assert observation.url_pattern == "https://example.test/products"
    assert observation.browser_title == "Example Products"
    assert observation.heading == "Products"
    assert observation.web_state_id == "ws-123"
    assert observation.llm_title == "Product listing"
    assert observation.state_indicators == {}
    assert observation.evidence[0].source == "browser"
```

- [ ] **Step 2: Run observer test to verify it fails**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_observer.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `web_kobe_observer`.

- [ ] **Step 3: Implement minimal observer**

Create `src/ai_web_explorer/safesym_bridge/web_kobe_observer.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from ai_web_explorer.safesym_bridge.capability_graph import Evidence


@dataclass(frozen=True)
class WebKobeObservation:
    url: str
    url_pattern: str
    browser_title: str
    heading: str | None = None
    web_state_id: str | None = None
    llm_title: str | None = None
    state_indicators: dict[str, Any] = field(default_factory=dict)
    interactables: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)


def _url_pattern(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/") or "/", "", ""))


def _safe_title(page) -> str:
    title = page.title
    return title() if callable(title) else str(title)


def _optional_inner_text(page, selector: str) -> str | None:
    try:
        locator = page.locator(selector)
        if locator.count() == 0:
            return None
        return locator.first.inner_text().strip()
    except Exception:
        return None


def observe_web_kobe_page(
    page,
    *,
    web_state_id: str | None = None,
    llm_title: str | None = None,
) -> WebKobeObservation:
    url = str(page.url)
    heading = _optional_inner_text(page, "h1")
    return WebKobeObservation(
        url=url,
        url_pattern=_url_pattern(url),
        browser_title=_safe_title(page),
        heading=heading,
        web_state_id=web_state_id,
        llm_title=llm_title,
        evidence=[Evidence(source="browser", url=url, confidence=1.0)],
    )
```

- [ ] **Step 4: Run observer test to verify it passes**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_observer.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/web_kobe_observer.py tests/safesym_bridge/test_web_kobe_observer.py
git commit -m "feat: add Web-KOBE page observer"
```

---

### Task 2: Web-KOBE Collector Core

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/web_kobe_collector.py`
- Create: `tests/safesym_bridge/test_web_kobe_collector.py`

**Interfaces:**
- Consumes:
  - `WebKobeObservation`
  - `webstate.Action`
  - `webstate.WebState`
  - `WebKobeGraphManager`
- Produces:
  - `NoOpWebKobeCollector`
  - `WebKobeCollector`
  - `on_state_observed(page, web_state, observation)`
  - `on_action_selected(source_state, action)`
  - `on_action_executed(action, success, tool_calls, error=None)`
  - `on_transition(source_state, action, target_state, before_observation, after_observation)`
  - `to_web_kobe_graph()`

- [ ] **Step 1: Write failing collector tests**

Create `tests/safesym_bridge/test_web_kobe_collector.py`:

```python
import uuid

from ai_web_explorer import webstate
from ai_web_explorer.safesym_bridge.web_kobe_collector import WebKobeCollector
from ai_web_explorer.safesym_bridge.web_kobe_observer import WebKobeObservation


def _state(title: str) -> webstate.WebState:
    return webstate.WebState(
        title=title,
        title_embedding=[],
        urls=[f"https://example.test/{title.lower().replace(' ', '-')}"],
        description=[],
        actions=[],
        transitions=[],
        ws_id=uuid.uuid5(uuid.NAMESPACE_DNS, title),
    )


def _observation(url: str, title: str, **state_indicators):
    return WebKobeObservation(
        url=url,
        url_pattern=url,
        browser_title=title,
        heading=title,
        web_state_id=title,
        llm_title=title,
        state_indicators=state_indicators,
    )


def test_collector_records_state_and_transition_delta():
    collector = WebKobeCollector(app="example")
    source = _state("Products")
    target = _state("Products")
    action = webstate.Action(
        description="Add a product to the cart",
        part=0,
        priority=10,
        status="success",
        function_calls=[],
    )
    before = _observation(
        "https://example.test/products",
        "Products",
        cart_count=0,
        cart_nonempty=False,
    )
    after = _observation(
        "https://example.test/products",
        "Products",
        cart_count=1,
        cart_nonempty=True,
    )

    collector.on_state_observed(page=None, web_state=source, observation=before)
    collector.on_action_selected(source_state=source, action=action)
    collector.on_action_executed(action=action, success=True, tool_calls=[])
    collector.on_transition(
        source_state=source,
        action=action,
        target_state=target,
        before_observation=before,
        after_observation=after,
    )

    graph = collector.to_web_kobe_graph()

    assert graph.app == "example"
    assert len(graph.nodes) == 1
    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert edge.action.semantic_id == "add_a_product_to_the_cart"
    assert edge.schema_delta == {
        "cart_count": {"before": 0, "after": 1},
        "cart_nonempty": {"before": False, "after": True},
    }
    assert edge.execution_trace.success is True
```

- [ ] **Step 2: Run collector test to verify it fails**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_collector.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `web_kobe_collector`.

- [ ] **Step 3: Implement minimal collector**

Create `src/ai_web_explorer/safesym_bridge/web_kobe_collector.py` with:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

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
from ai_web_explorer.safesym_bridge.web_kobe_graph_manager import WebKobeGraphManager
from ai_web_explorer.safesym_bridge.web_kobe_observer import WebKobeObservation


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned or "unknown"


def _node_id(web_state, observation: WebKobeObservation) -> str:
    return _slug(observation.llm_title or getattr(web_state, "title", "") or observation.url_pattern)


def _schema_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any] | None:
    delta = {}
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            delta[key] = {"before": before.get(key), "after": after.get(key)}
    return delta or None


class NoOpWebKobeCollector:
    def on_state_observed(self, **kwargs) -> None:
        return None

    def on_action_selected(self, **kwargs) -> None:
        return None

    def on_action_executed(self, **kwargs) -> None:
        return None

    def on_transition(self, **kwargs) -> None:
        return None


@dataclass
class _ExecutedAction:
    success: bool
    tool_calls: list
    error: str | None


class WebKobeCollector:
    def __init__(self, *, app: str):
        self.app = app
        self.manager = WebKobeGraphManager(app=app)
        self._observations: dict[int, WebKobeObservation] = {}
        self._executed: dict[int, _ExecutedAction] = {}
        self._start_node_id: str | None = None

    def on_state_observed(self, *, page, web_state, observation: WebKobeObservation) -> None:
        node_id = self._add_state(web_state, observation)
        if self._start_node_id is None:
            self._start_node_id = node_id

    def on_action_selected(self, *, source_state, action) -> None:
        return None

    def on_action_executed(
        self,
        *,
        action,
        success: bool,
        tool_calls: list,
        error: str | None = None,
    ) -> None:
        self._executed[id(action)] = _ExecutedAction(success, tool_calls, error)

    def on_transition(
        self,
        *,
        source_state,
        action,
        target_state,
        before_observation: WebKobeObservation,
        after_observation: WebKobeObservation,
    ) -> None:
        source_id = self._add_state(source_state, before_observation)
        target_id = self._add_state(target_state, after_observation)
        executed = self._executed.get(
            id(action),
            _ExecutedAction(success=getattr(action, "status", "") == "success", tool_calls=[], error=None),
        )
        semantic_id = _slug(action.description)
        delta = _schema_delta(before_observation.state_indicators, after_observation.state_indicators)
        evidence = [Evidence(source="web_kobe_collector", url=before_observation.url)]
        edge = WebKobeEdge(
            source_node_id=source_id,
            target_node_id=target_id,
            instruction=action.description,
            action=BrowserAction(
                action_kind="composite" if executed.tool_calls else "unknown",
                locator=None,
                semantic_id=semantic_id,
                description=action.description,
            ),
            capability=None,
            target_observation=after_observation.llm_title or after_observation.browser_title,
            observed_delta=[
                ObservedDelta(
                    field=field,
                    before=value["before"],
                    after=value["after"],
                    delta_type="state_indicator_change",
                    evidence=evidence,
                )
                for field, value in (delta or {}).items()
            ],
            schema_delta=delta,
            execution_trace=ExecutionTrace(
                concrete_action_kind="composite" if executed.tool_calls else "unknown",
                concrete_locator=None,
                concrete_target_sample=action.description,
                input_values_used={},
                before_observation_id=source_id,
                after_observation_id=target_id,
                success=executed.success,
                error=executed.error,
            ),
            status="verified" if executed.success else "failed_execution",
            evidence=evidence,
        )
        self.manager.add_edge(edge)

    def to_web_kobe_graph(self) -> WebKobeGraph:
        return self.manager.to_graph(start_node_id=self._start_node_id)

    def _add_state(self, web_state, observation: WebKobeObservation) -> str:
        node_id = _node_id(web_state, observation)
        evidence = [Evidence(source="web_kobe_collector", url=observation.url)]
        node = WebKobeNode(
            node_id=node_id,
            page_description=observation.llm_title or observation.browser_title,
            page_frame=PageFrame(
                page_id=f"{self.app}:{node_id}",
                page_type=node_id,
                url=observation.url,
                url_pattern=observation.url_pattern,
                title=observation.browser_title,
                heading=observation.heading,
                signature_hints=dict(observation.state_indicators),
                evidence=evidence,
            ),
            state_schema={key: [value] for key, value in observation.state_indicators.items()},
            last_state_snapshot=dict(observation.state_indicators),
            reference_observation=ReferenceObservation(
                url=observation.url,
                title=observation.browser_title,
            ),
            evidence=evidence,
        )
        return self.manager.identify_or_add_node(node)
```

- [ ] **Step 4: Run collector tests to verify pass**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_collector.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/web_kobe_collector.py tests/safesym_bridge/test_web_kobe_collector.py
git commit -m "feat: add Web-KOBE collector core"
```

---

### Task 3: ExploreLoop Collector Hooks

**Files:**
- Modify: `src/ai_web_explorer/loop.py`
- Test: `tests/test_loop_collector_hooks.py`

**Interfaces:**
- Consumes:
  - `NoOpWebKobeCollector`
  - `observe_web_kobe_page`
- Produces:
  - `LoopConfig.collector`
  - `ExploreLoop` hook calls:
    - `collector.on_state_observed(...)`
    - `collector.on_transition(...)`
    - `collector.on_action_selected(...)`
    - `collector.on_action_executed(...)`

- [ ] **Step 1: Write failing hook test**

Create `tests/test_loop_collector_hooks.py`.

This test should avoid real browser and LLM calls by constructing an `ExploreLoop`
instance with `object.__new__`, then injecting fake fields:

```python
from ai_web_explorer import loop, webstate


class RecordingCollector:
    def __init__(self):
        self.events = []

    def on_state_observed(self, **kwargs):
        self.events.append(("state", kwargs["web_state"].title))

    def on_transition(self, **kwargs):
        self.events.append(
            (
                "transition",
                kwargs["source_state"].title,
                kwargs["action"].description,
                kwargs["target_state"].title,
            )
        )

    def on_action_selected(self, **kwargs):
        self.events.append(("selected", kwargs["action"].description))

    def on_action_executed(self, **kwargs):
        self.events.append(("executed", kwargs["action"].description, kwargs["success"]))


class FakeDescriber:
    def __init__(self, titles):
        self.titles = list(titles)

    def is_loading(self):
        return False

    def get_title(self, confirm, store_title):
        return self.titles.pop(0)

    def get_title_embedding(self, title):
        return []

    def get_description(self):
        return []

    def get_actions(self, title, description):
        return [
            webstate.Action(
                description=f"Go from {title}",
                part=0,
                priority=10,
            )
        ]


class FakeExecutor:
    def execute(self, action):
        return True, []


class FakePage:
    url = "https://example.test/start"

    def title(self):
        return "Browser title"

    def locator(self, selector):
        class EmptyLocator:
            first = None

            def count(self):
                return 0

        locator = EmptyLocator()
        locator.first = locator
        return locator


def _make_loop(collector):
    explore_loop = object.__new__(loop.ExploreLoop)
    explore_loop._domain = "example.test"
    explore_loop._url = "https://example.test/start"
    explore_loop._openai_client = None
    explore_loop._config = loop.LoopConfig(iterations=1)
    explore_loop._config.collector = collector
    explore_loop._webstates = []
    explore_loop._webstate_current = None
    explore_loop._action_current = None
    explore_loop._page = FakePage()
    explore_loop._describer = FakeDescriber(["Start", "Next"])
    explore_loop._executor = FakeExecutor()
    return explore_loop


def test_explore_loop_emits_collector_events_for_state_action_and_transition():
    collector = RecordingCollector()
    explore_loop = _make_loop(collector)

    explore_loop._explore()
    explore_loop._explore()

    assert collector.events == [
        ("state", "Start"),
        ("selected", "Go from Start"),
        ("executed", "Go from Start", True),
        ("state", "Next"),
        ("transition", "Start", "Go from Start", "Next"),
        ("selected", "Go from Next"),
        ("executed", "Go from Next", True),
    ]
```

- [ ] **Step 2: Run hook test to verify it fails**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_loop_collector_hooks.py -v
```

Expected: FAIL because `LoopConfig` has no collector field and `_explore()` does not call hooks.

- [ ] **Step 3: Implement hook integration**

Modify `src/ai_web_explorer/loop.py`:

1. Add imports:

```python
from ai_web_explorer.safesym_bridge.web_kobe_collector import NoOpWebKobeCollector
from ai_web_explorer.safesym_bridge.web_kobe_observer import observe_web_kobe_page
```

2. Add to `LoopConfig`:

```python
collector: object | None = dataclasses.field(default=None)
```

3. In `ExploreLoop.__init__`, set:

```python
self._collector = config.collector or NoOpWebKobeCollector()
```

4. In `_explore()`, after `ws = self._get_webstate()`:

```python
observation = observe_web_kobe_page(
    self._page,
    web_state_id=str(ws.ws_id),
    llm_title=ws.title,
)
self._collector.on_state_observed(
    page=self._page,
    web_state=ws,
    observation=observation,
)
```

5. When appending a transition for a successful previous action, call:

```python
self._collector.on_transition(
    source_state=self._webstate_current,
    action=self._action_current,
    target_state=ws,
    before_observation=getattr(self, "_web_kobe_previous_observation", None),
    after_observation=observation,
)
```

Only call this when the previous observation is not `None`.

6. After selecting `self._action_current`, call:

```python
self._collector.on_action_selected(
    source_state=ws,
    action=self._action_current,
)
```

7. After execution and success/failure calculation, call:

```python
self._collector.on_action_executed(
    action=self._action_current,
    success=self._action_current.status == "success",
    tool_calls=tool_calls,
    error=None if self._action_current.status == "success" else "execution_failed",
)
self._web_kobe_previous_observation = observation
```

Initialize `_web_kobe_previous_observation = None` in `__init__`.

- [ ] **Step 4: Run hook test to verify pass**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_loop_collector_hooks.py -v
```

Expected: PASS.

- [ ] **Step 5: Run existing original-explorer tests**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/ai/test_loop.py tests/ai/test_webstate.py -v
```

If these exact files do not exist, run:

```bash
.\.venv\Scripts\python.exe -m pytest tests -k "loop or webstate" -v
```

Expected: PASS or unrelated OpenAI API-key collection failures should be reported separately.

- [ ] **Step 6: Commit**

```bash
git add src/ai_web_explorer/loop.py tests/test_loop_collector_hooks.py
git commit -m "feat: add Web-KOBE collector hooks to ExploreLoop"
```

---

### Task 4: Collector Output Command Path

**Files:**
- Modify: `src/ai_web_explorer/__init__.py`
- Modify or create: `tests/test_cli_collector_output.py`

**Interfaces:**
- Consumes:
  - `WebKobeCollector`
  - `LoopConfig.collector`
- Produces:
  - CLI option `--web-kobe-output <path>` for the original `explore` command.

This task should be done only after Task 3 is stable. It wires collector output
to the existing CLI without making `web-kobe-explore` the main path.

- [ ] **Step 1: Write failing CLI parser test**

Create `tests/test_cli_collector_output.py` with a minimal parser-focused test.
If direct parser testing is awkward because parser is module-global, use
`monkeypatch` on `sys.argv` and monkeypatch `ExploreLoop` to avoid real browser.

Expected behavior:

```bash
explore example.test -i 1 --web-kobe-output outputs/web_kobe.json
```

should create a `WebKobeCollector` and write `collector.to_web_kobe_graph()` to
the requested path after exploration.

- [ ] **Step 2: Run CLI test to verify failure**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_cli_collector_output.py -v
```

Expected: FAIL because the option does not exist.

- [ ] **Step 3: Implement CLI option**

Modify `src/ai_web_explorer/__init__.py`:

1. Add parser argument:

```python
parser.add_argument(
    "--web-kobe-output",
    type=str,
    default=None,
    help="Write a Web-KOBE graph collected during exploration to this JSON path.",
)
```

2. If `args.web_kobe_output` is set, create `WebKobeCollector(app=domain)`.
Pass it into `LoopConfig`.

3. After `explore_loop.start()`, write:

```python
if collector is not None:
    from pathlib import Path
    import json

    output_path = Path(args.web_kobe_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(collector.to_web_kobe_graph().to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
```

- [ ] **Step 4: Run CLI test**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_cli_collector_output.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/__init__.py tests/test_cli_collector_output.py
git commit -m "feat: expose Web-KOBE collector output in explore CLI"
```

---

### Task 5: Documentation and Verification

**Files:**
- Modify: `docs/current-project-overview.md`
- Modify: `docs/safesym-bridge.md`

**Interfaces:**
- Documents:
  - Original `explore` command remains the main unknown-site exploration method.
  - `--web-kobe-output` writes richer Web-KOBE collector data.
  - `web-kobe-explore` is experimental/legacy validation path, not the long-term main path.

- [ ] **Step 1: Update current project overview**

Add a section near the current Web-KOBE discussion:

```markdown
The preferred long-term path is to reuse the original `explore` command as the
unknown-site exploration engine and attach Web-KOBE collection as a sidecar:

```bash
rye run explore example.com -i 10 --web-kobe-output outputs/example_web_kobe.json
```

The older `web-kobe-explore` command is retained as an experimental validation
path, but new generic exploration work should add collector hooks to the
original explorer rather than expanding a separate exploration loop.
```

- [ ] **Step 2: Update SafeSym bridge doc**

Add the same architectural note to `docs/safesym-bridge.md`.

- [ ] **Step 3: Run focused tests**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_observer.py tests/safesym_bridge/test_web_kobe_collector.py tests/test_loop_collector_hooks.py -v
```

Expected: PASS.

- [ ] **Step 4: Run safesym bridge regression**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge -v
```

Expected: PASS with browser tests skipped unless explicitly enabled.

- [ ] **Step 5: Run broad feasible regression**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest -v
```

If collection fails because `OPENAI_API_KEY` is missing in existing tests, report it as an existing environment requirement and include the focused passing commands.

- [ ] **Step 6: Commit docs**

```bash
git add docs/current-project-overview.md docs/safesym-bridge.md
git commit -m "docs: document Web-KOBE collector path"
```

---

## Self-Review Checklist

- Spec coverage:
  - Reuses original explorer rather than replacing it: Tasks 3 and 4.
  - Directly collects richer information during exploration: Tasks 1, 2, and 3.
  - Keeps state merging simple for v1: Observation and collector use conservative node IDs; no complex merge policy in this plan.
  - Avoids default LLM/browser dependency in tests: all new tests use fakes.
  - Keeps SafeSym separation: collector only records graph data.

- Scope control:
  - This plan does not implement full capability normalization.
  - This plan does not implement graph audit.
  - This plan does not implement generic PDDL generation.
  - This plan does not delete the experimental controller/adapter path yet.

- Type consistency:
  - `WebKobeObservation` is consumed by `WebKobeCollector`.
  - `NoOpWebKobeCollector` supports the same hook names used by `ExploreLoop`.
  - `WebKobeCollector.to_web_kobe_graph()` returns `WebKobeGraph`.

## Execution Handoff

Because the user requested single-agent work by default, Inline Execution is the
expected implementation mode unless the user explicitly allows subagents.
