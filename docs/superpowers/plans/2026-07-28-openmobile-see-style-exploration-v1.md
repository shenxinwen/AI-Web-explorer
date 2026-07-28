# OpenMobile/SEE-Style Exploration V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal OpenMobile/SEE-style exploration loop where the existing `WebKobeGraph` can act as queryable exploration memory, detect revisited states with embeddings, guide Stagehand away from repeated actions, and keep PDDL/SafeSym projection profile-only.

**Architecture:** Keep `WebKobeGraph` as the only persistent graph truth. Add focused `grounded_web` helpers for state summaries, embedding-backed state matching, and graph-derived exploration context. Wire that context into `WebKobeExplorer`, `LlmActionSelectionRequest`, and Stagehand business-intent execution without changing PDDL semantics.

**Tech Stack:** Python 3.9+, dataclasses, pytest, existing `openai` dependency for optional real embeddings, existing Playwright/Stagehand runner boundaries.

## Global Constraints

- `WebKobeGraph` remains the only persistent memory source.
- `GraphExplorationIndex` is a derived query/cache view, not a second source of truth.
- PDDL consumes only graph location predicates and preset profile facts.
- DOM/UI/schema facts, screenshots, embeddings, and Stagehand text remain evidence and prompt context only.
- Real website experiments must remain explicit because they depend on network, model latency, and browser state.
- Use TDD for each task: write failing tests, run failing tests, implement, run passing tests, commit.
- Use `.\.venv\Scripts\python.exe -m pytest ...` for local tests.

---

## File Structure

- Create `src/ai_web_explorer/grounded_web/state_summary.py`
  - Owns compact state-summary construction and context markers.
- Create `src/ai_web_explorer/grounded_web/state_embedding.py`
  - Owns embedding provider protocol, cosine similarity, sidecar records, matching thresholds, and guard checks.
- Create `src/ai_web_explorer/grounded_web/exploration_index.py`
  - Owns graph-derived tried/avoid action summaries and prompt-ready exploration context.
- Modify `src/ai_web_explorer/grounded_web/explorer.py`
  - Builds summaries, updates embedding records, derives exploration context, passes it to selection/backend metadata.
- Modify `src/ai_web_explorer/grounded_web/llm_action_selector.py`
  - Adds optional exploration context to action-selection prompts.
- Modify `src/ai_web_explorer/grounded_web/stagehand_backend.py`
  - Allows Web-KOBE to append dynamic exploration context to business-milestone execution.
- Modify `src/ai_web_explorer/grounded_web/stagehand_prompt.py`
  - Adds a generic exploration goal builder that is not checkout-specific.
- Modify `src/ai_web_explorer/safesym_bridge/browser_runner.py`
  - Adds a generic Stagehand exploration runner.
- Modify `src/ai_web_explorer/safesym_bridge/cli.py`
  - Adds `web-kobe-stagehand-explore`.
- Add/modify tests under `tests/safesym_bridge/`.

---

### Task 1: State Summary Construction

**Files:**
- Create: `src/ai_web_explorer/grounded_web/state_summary.py`
- Test: `tests/safesym_bridge/test_state_summary.py`

**Interfaces:**
- Consumes: `StateSnapshot`, optional interactable dictionaries, optional active planning facts.
- Produces:
  - `StateSummary`
  - `build_state_summary(snapshot: StateSnapshot, interactables: list[dict[str, Any]], active_planning_facts: Iterable[str] = (), visual_summary: str | None = None) -> StateSummary`

- [ ] **Step 1: Write failing tests for deterministic summary text and markers**

Create `tests/safesym_bridge/test_state_summary.py`:

```python
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.state_summary import build_state_summary


def test_build_state_summary_includes_page_controls_and_planning_facts():
    snapshot = StateSnapshot(
        page_id="products",
        url="https://shop.test/products?sort=price",
        title="Products",
        signature={
            "url_path": "/products",
            "cart_count": 1,
            "modal_open": False,
        },
    )
    interactables = [
        {
            "semantic_id": "add_to_cart_backpack",
            "description": "Add backpack to cart",
            "action_kind": "click",
        },
        {
            "semantic_id": "open_cart",
            "description": "Open cart",
            "action_kind": "click",
        },
    ]

    summary = build_state_summary(
        snapshot=snapshot,
        interactables=interactables,
        active_planning_facts=["cart_has_items"],
        visual_summary="Cart badge shows 1 item.",
    )

    assert "url_path: /products" in summary.text
    assert "title: Products" in summary.text
    assert "planning_facts: cart_has_items" in summary.text
    assert "controls: Add backpack to cart; Open cart" in summary.text
    assert "visual: Cart badge shows 1 item." in summary.text
    assert summary.context_markers == ("cart_non_empty",)
    assert summary.planning_facts == ("cart_has_items",)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_state_summary.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'ai_web_explorer.grounded_web.state_summary'`.

- [ ] **Step 3: Implement minimal state summary module**

Create `src/ai_web_explorer/grounded_web/state_summary.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlsplit

from ai_web_explorer.grounded_web.models import StateSnapshot


@dataclass(frozen=True)
class StateSummary:
    text: str
    context_markers: tuple[str, ...]
    planning_facts: tuple[str, ...]


def _normalized_path(snapshot: StateSnapshot) -> str:
    signature_path = snapshot.signature.get("url_path")
    if signature_path:
        return str(signature_path)
    return urlsplit(snapshot.url).path or "/"


def _control_descriptions(interactables: list[dict[str, Any]]) -> list[str]:
    controls: list[str] = []
    for item in interactables:
        description = str(item.get("description") or item.get("semantic_id") or "")
        description = " ".join(description.split())
        if description and description not in controls:
            controls.append(description)
    return controls[:12]


def _context_markers(signature: dict[str, Any]) -> tuple[str, ...]:
    markers: list[str] = []
    cart_count = signature.get("cart_count")
    if cart_count not in (None, "", 0, "0", False):
        markers.append("cart_non_empty")
    if signature.get("cart_has_items") is True:
        markers.append("cart_non_empty")
    if signature.get("modal_open") is True or signature.get("dialog_open") is True:
        markers.append("modal_open")
    if signature.get("form_visible") is True:
        markers.append("form_visible")
    return tuple(dict.fromkeys(markers))


def build_state_summary(
    *,
    snapshot: StateSnapshot,
    interactables: list[dict[str, Any]],
    active_planning_facts: Iterable[str] = (),
    visual_summary: str | None = None,
) -> StateSummary:
    facts = tuple(dict.fromkeys(str(fact) for fact in active_planning_facts))
    controls = _control_descriptions(interactables)
    lines = [
        f"url_path: {_normalized_path(snapshot)}",
        f"title: {snapshot.title}",
    ]
    if facts:
        lines.append("planning_facts: " + ", ".join(facts))
    markers = _context_markers(snapshot.signature)
    if markers:
        lines.append("context_markers: " + ", ".join(markers))
    if controls:
        lines.append("controls: " + "; ".join(controls))
    if visual_summary:
        lines.append("visual: " + " ".join(visual_summary.split()))
    return StateSummary(
        text="\n".join(lines),
        context_markers=markers,
        planning_facts=facts,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_state_summary.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/state_summary.py tests/safesym_bridge/test_state_summary.py
git commit -m "feat: add exploration state summaries"
```

---

### Task 2: Embedding State Matching

**Files:**
- Create: `src/ai_web_explorer/grounded_web/state_embedding.py`
- Test: `tests/safesym_bridge/test_state_embedding.py`

**Interfaces:**
- Consumes: `StateSummary` from Task 1 and a callable embedding provider.
- Produces:
  - `EmbeddingProvider = Callable[[str], Sequence[float]]`
  - `StateEmbeddingRecord`
  - `StateMatch`
  - `cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float`
  - `find_best_state_match(current: StateSummary, records: Iterable[StateEmbeddingRecord], embedding_provider: EmbeddingProvider, same_threshold: float = 0.90, ambiguous_threshold: float = 0.82) -> StateMatch`
  - `read_state_embedding_records(path: Path) -> list[StateEmbeddingRecord]`
  - `write_state_embedding_records(path: Path, records: Iterable[StateEmbeddingRecord]) -> Path`

- [ ] **Step 1: Write failing tests for matching, ambiguity, and guard checks**

Create `tests/safesym_bridge/test_state_embedding.py`:

```python
from pathlib import Path

from ai_web_explorer.grounded_web.state_embedding import (
    StateEmbeddingRecord,
    cosine_similarity,
    find_best_state_match,
    read_state_embedding_records,
    write_state_embedding_records,
)
from ai_web_explorer.grounded_web.state_summary import StateSummary


def fake_embed(text: str):
    if "cart page" in text:
        return [1.0, 0.0, 0.0]
    if "similar product" in text:
        return [0.9, 0.1, 0.0]
    return [0.0, 1.0, 0.0]


def test_cosine_similarity_returns_expected_score():
    assert cosine_similarity([1, 0], [1, 0]) == 1.0
    assert cosine_similarity([1, 0], [0, 1]) == 0.0


def test_find_best_state_match_returns_same_when_embedding_is_high():
    current = StateSummary(
        text="cart page with checkout button",
        context_markers=("cart_non_empty",),
        planning_facts=("cart_has_items",),
    )
    records = [
        StateEmbeddingRecord(
            node_id="cart",
            summary_text="cart page",
            embedding=[1.0, 0.0, 0.0],
            planning_facts=("cart_has_items",),
            context_markers=("cart_non_empty",),
        )
    ]

    match = find_best_state_match(current, records, embedding_provider=fake_embed)

    assert match.status == "same"
    assert match.node_id == "cart"
    assert match.score == 1.0


def test_find_best_state_match_blocks_modal_context_conflict():
    current = StateSummary(
        text="cart page with checkout button",
        context_markers=("cart_non_empty", "modal_open"),
        planning_facts=("cart_has_items",),
    )
    records = [
        StateEmbeddingRecord(
            node_id="cart",
            summary_text="cart page",
            embedding=[1.0, 0.0, 0.0],
            planning_facts=("cart_has_items",),
            context_markers=("cart_non_empty",),
        )
    ]

    match = find_best_state_match(current, records, embedding_provider=fake_embed)

    assert match.status == "blocked"
    assert match.blocked_reason == "context_marker_conflict"


def test_state_embedding_sidecar_round_trips(tmp_path: Path):
    path = tmp_path / "state_embeddings.json"
    records = [
        StateEmbeddingRecord(
            node_id="products",
            summary_text="similar product list",
            embedding=[0.9, 0.1, 0.0],
            planning_facts=("product_list_visible",),
            context_markers=(),
        )
    ]

    write_state_embedding_records(path, records)
    loaded = read_state_embedding_records(path)

    assert loaded == records
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_state_embedding.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'ai_web_explorer.grounded_web.state_embedding'`.

- [ ] **Step 3: Implement embedding matching and sidecar IO**

Create `src/ai_web_explorer/grounded_web/state_embedding.py`:

```python
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

from ai_web_explorer.grounded_web.state_summary import StateSummary

EmbeddingProvider = Callable[[str], Sequence[float]]


@dataclass(frozen=True)
class StateEmbeddingRecord:
    node_id: str
    summary_text: str
    embedding: Sequence[float]
    planning_facts: tuple[str, ...] = ()
    context_markers: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "summary_text": self.summary_text,
            "embedding": list(self.embedding),
            "planning_facts": list(self.planning_facts),
            "context_markers": list(self.context_markers),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StateEmbeddingRecord":
        return cls(
            node_id=str(data["node_id"]),
            summary_text=str(data["summary_text"]),
            embedding=[float(value) for value in data["embedding"]],
            planning_facts=tuple(str(value) for value in data.get("planning_facts", [])),
            context_markers=tuple(str(value) for value in data.get("context_markers", [])),
        )


@dataclass(frozen=True)
class StateMatch:
    status: str
    node_id: str | None
    score: float
    blocked_reason: str | None = None


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return round(numerator / (left_norm * right_norm), 6)


def _context_compatible(current: StateSummary, record: StateEmbeddingRecord) -> bool:
    current_markers = set(current.context_markers)
    record_markers = set(record.context_markers)
    guarded = {"modal_open", "form_visible", "cart_non_empty"}
    return current_markers.intersection(guarded) == record_markers.intersection(guarded)


def find_best_state_match(
    current: StateSummary,
    records: Iterable[StateEmbeddingRecord],
    *,
    embedding_provider: EmbeddingProvider,
    same_threshold: float = 0.90,
    ambiguous_threshold: float = 0.82,
) -> StateMatch:
    current_embedding = embedding_provider(current.text)
    best_record: StateEmbeddingRecord | None = None
    best_score = 0.0
    for record in records:
        score = cosine_similarity(current_embedding, record.embedding)
        if score > best_score:
            best_record = record
            best_score = score
    if best_record is None:
        return StateMatch(status="new", node_id=None, score=0.0)
    if best_score >= same_threshold and not _context_compatible(current, best_record):
        return StateMatch(
            status="blocked",
            node_id=best_record.node_id,
            score=best_score,
            blocked_reason="context_marker_conflict",
        )
    if best_score >= same_threshold:
        return StateMatch(status="same", node_id=best_record.node_id, score=best_score)
    if best_score >= ambiguous_threshold:
        return StateMatch(status="ambiguous", node_id=best_record.node_id, score=best_score)
    return StateMatch(status="new", node_id=None, score=best_score)


def read_state_embedding_records(path: Path) -> list[StateEmbeddingRecord]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [StateEmbeddingRecord.from_dict(item) for item in data.get("records", [])]


def write_state_embedding_records(
    path: Path,
    records: Iterable[StateEmbeddingRecord],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"records": [record.to_dict() for record in records]}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_state_summary.py tests/safesym_bridge/test_state_embedding.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/state_embedding.py tests/safesym_bridge/test_state_embedding.py
git commit -m "feat: add embedding state matching"
```

---

### Task 3: Graph Exploration Index

**Files:**
- Create: `src/ai_web_explorer/grounded_web/exploration_index.py`
- Test: `tests/safesym_bridge/test_exploration_index.py`

**Interfaces:**
- Consumes: `WebKobeGraph`, optional `StateMatch`.
- Produces:
  - `ExplorationContext`
  - `build_exploration_context(graph: WebKobeGraph, current_node_id: str, state_match: StateMatch | None = None) -> ExplorationContext`

- [ ] **Step 1: Write failing tests for tried/avoid action summaries**

Create `tests/safesym_bridge/test_exploration_index.py`:

```python
from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.exploration_index import build_exploration_context
from ai_web_explorer.grounded_web.graph import BrowserAction, WebKobeEdge, WebKobeGraph, WebKobeNode
from ai_web_explorer.grounded_web.state_embedding import StateMatch


def node(node_id: str) -> WebKobeNode:
    return WebKobeNode(
        node_id=node_id,
        page_description=node_id,
        page_frame=PageFrame(
            page_id=node_id,
            page_type=node_id,
            url=f"https://shop.test/{node_id}",
            url_pattern=f"https://shop.test/{node_id}",
            title=node_id,
        ),
        state_schema={},
        last_state_snapshot={},
    )


def edge(source: str, target: str, action_id: str, status: str) -> WebKobeEdge:
    return WebKobeEdge(
        source_node_id=source,
        target_node_id=target,
        instruction=action_id.replace("_", " "),
        action=BrowserAction("click", f"#{action_id}", action_id),
        capability=None,
        target_observation=target,
        observed_delta=[],
        schema_delta={},
        execution_trace=ExecutionTrace("click", f"#{action_id}", action_id, {}, source, target, status != "failed_execution"),
        status=status,
    )


def test_build_exploration_context_summarizes_tried_and_avoid_actions():
    graph = WebKobeGraph(
        app="shop",
        start_node_id="products",
        total_steps_completed=3,
        nodes=[node("products"), node("cart")],
        edges=[
            edge("products", "cart", "open_cart", "succeeded_with_navigation"),
            edge("products", "products", "theme_toggle", "no_observed_change"),
            edge("products", "products", "bad_button", "failed_execution"),
        ],
    )

    context = build_exploration_context(graph, current_node_id="products")

    assert context.tried_action_ids == ("open_cart", "theme_toggle", "bad_button")
    assert context.avoid_action_ids == ("theme_toggle", "bad_button")
    assert "Avoid repeating actions: theme_toggle, bad_button" in context.to_prompt_block()


def test_build_exploration_context_uses_matched_node_for_revisit_memory():
    graph = WebKobeGraph(
        app="shop",
        start_node_id="products",
        total_steps_completed=1,
        nodes=[node("products")],
        edges=[edge("products", "products", "open_filter", "no_observed_change")],
    )
    match = StateMatch(status="same", node_id="products", score=0.94)

    context = build_exploration_context(
        graph,
        current_node_id="new_products_node",
        state_match=match,
    )

    assert context.reference_node_id == "products"
    assert context.is_revisit is True
    assert context.avoid_action_ids == ("open_filter",)
    assert "This state appears to revisit node products" in context.to_prompt_block()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_exploration_index.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'ai_web_explorer.grounded_web.exploration_index'`.

- [ ] **Step 3: Implement graph-derived exploration context**

Create `src/ai_web_explorer/grounded_web/exploration_index.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from ai_web_explorer.grounded_web.graph import WebKobeGraph
from ai_web_explorer.grounded_web.state_embedding import StateMatch


@dataclass(frozen=True)
class ExplorationContext:
    current_node_id: str
    reference_node_id: str
    is_revisit: bool
    tried_action_ids: tuple[str, ...]
    avoid_action_ids: tuple[str, ...]
    state_match_status: str | None = None
    state_match_score: float | None = None

    def to_prompt_block(self) -> str:
        lines = [
            "Exploration memory:",
            f"Current graph node: {self.current_node_id}",
        ]
        if self.is_revisit:
            lines.append(
                f"This state appears to revisit node {self.reference_node_id}"
                f" with similarity {self.state_match_score:.2f}."
            )
        if self.tried_action_ids:
            lines.append("Already tried actions: " + ", ".join(self.tried_action_ids))
        if self.avoid_action_ids:
            lines.append("Avoid repeating actions: " + ", ".join(self.avoid_action_ids))
        lines.append(
            "Choose one useful site-function action that is not in the avoid list."
        )
        return "\n".join(lines)


def _unique(items: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))


def build_exploration_context(
    graph: WebKobeGraph,
    *,
    current_node_id: str,
    state_match: StateMatch | None = None,
) -> ExplorationContext:
    reference_node_id = (
        state_match.node_id
        if state_match is not None
        and state_match.status == "same"
        and state_match.node_id is not None
        else current_node_id
    )
    tried: list[str] = []
    avoid: list[str] = []
    for edge in graph.edges:
        if edge.source_node_id != reference_node_id:
            continue
        action_id = edge.action.canonical_action_name or edge.action.semantic_id
        tried.append(action_id)
        if edge.status in {"no_observed_change", "failed_execution"}:
            avoid.append(action_id)
    return ExplorationContext(
        current_node_id=current_node_id,
        reference_node_id=reference_node_id,
        is_revisit=reference_node_id != current_node_id,
        tried_action_ids=_unique(tried),
        avoid_action_ids=_unique(avoid),
        state_match_status=state_match.status if state_match is not None else None,
        state_match_score=state_match.score if state_match is not None else None,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_exploration_index.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/exploration_index.py tests/safesym_bridge/test_exploration_index.py
git commit -m "feat: add graph exploration index"
```

---

### Task 4: Wire Exploration Context Into Explorer and Selectors

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Modify: `src/ai_web_explorer/grounded_web/llm_action_selector.py`
- Modify: `src/ai_web_explorer/grounded_web/stagehand_backend.py`
- Test: `tests/safesym_bridge/test_web_kobe_explorer.py`
- Test: `tests/safesym_bridge/test_llm_action_selector.py`
- Test: `tests/safesym_bridge/test_stagehand_backend.py`

**Interfaces:**
- Consumes: `StateSummary`, `StateEmbeddingRecord`, `EmbeddingProvider`, `ExplorationContext`.
- Produces:
  - `WebKobeExplorer(..., state_embedding_provider: EmbeddingProvider | None = None, state_embedding_records: list[StateEmbeddingRecord] | None = None, enable_exploration_memory: bool = False)`
  - `WebKobeExplorer.state_embedding_records`
  - `LlmActionSelectionRequest.exploration_context: dict[str, Any] | None`
  - `StagehandAutomationBackend.set_exploration_context(prompt_block: str | None) -> None`

- [ ] **Step 1: Write failing selector prompt test**

Add to `tests/safesym_bridge/test_llm_action_selector.py`:

```python
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.llm_action_selector import (
    LlmActionSelectionRequest,
    select_action_with_llm,
)
from ai_web_explorer.grounded_web.models import StateSnapshot


def test_select_action_prompt_includes_exploration_context():
    prompts = []

    def provider(prompt: str) -> str:
        prompts.append(prompt)
        return '{"selected_action_id":"open_search"}'

    request = LlmActionSelectionRequest(
        goal="Explore useful website functionality.",
        state=StateSnapshot("home", "https://shop.test/", "Home", {}),
        candidate_actions=[
            BrowserAction("click", "#search", "open_search", description="Open search")
        ],
        exploration_context={
            "prompt_block": "Avoid repeating actions: theme_toggle",
            "avoid_action_ids": ["theme_toggle"],
        },
    )

    result = select_action_with_llm(request, provider=provider)

    assert result.selected_action.semantic_id == "open_search"
    assert "Avoid repeating actions: theme_toggle" in prompts[0]
```

- [ ] **Step 2: Write failing Stagehand dynamic context test**

Add to `tests/safesym_bridge/test_stagehand_backend.py`:

```python
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.stagehand_backend import StagehandAutomationBackend


class FakeBaseBackend:
    app_name = "shop"

    async def observe_state(self):
        return StateSnapshot("home", "https://shop.test/", "Home", {})

    async def list_interactables(self, state):
        return []


class FakeProvider:
    def __init__(self):
        self.instructions = []

    async def execute_instruction(self, instruction, *, max_steps):
        self.instructions.append(instruction)

        class Result:
            success = True
            message = "ok"

        return Result()


@pytest.mark.anyio
async def test_stagehand_business_milestone_appends_exploration_context():
    provider = FakeProvider()
    backend = StagehandAutomationBackend(
        base_backend=FakeBaseBackend(),
        provider=provider,
        goal="Explore one useful action.",
        execution_mode="business_milestone",
    )
    state = await backend.observe_state()
    actions = await backend.list_interactables(state)

    backend.set_exploration_context("Avoid repeating actions: theme_toggle")
    success = await backend.execute(actions[0])

    assert success is True
    assert "Explore one useful action." in provider.instructions[0]
    assert "Avoid repeating actions: theme_toggle" in provider.instructions[0]
```

- [ ] **Step 3: Write failing explorer memory test**

Add to `tests/safesym_bridge/test_web_kobe_explorer.py`:

```python
from ai_web_explorer.grounded_web.state_embedding import StateEmbeddingRecord


class RevisitMemoryAdapter(RepeatedStateAdapter):
    def __init__(self):
        super().__init__()
        self.exploration_contexts = []

    def set_exploration_context(self, prompt_block):
        self.exploration_contexts.append(prompt_block)


@pytest.mark.anyio
async def test_explore_one_step_builds_memory_context_for_revisited_state():
    adapter = RevisitMemoryAdapter()

    def embed(text):
        return [1.0, 0.0, 0.0]

    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        enable_exploration_memory=True,
        state_embedding_provider=embed,
        state_embedding_records=[
            StateEmbeddingRecord(
                node_id="listing__existing",
                summary_text="listing state",
                embedding=[1.0, 0.0, 0.0],
            )
        ],
    )

    await explorer.explore_one_step()
    await explorer.explore_one_step()

    assert adapter.exploration_contexts
    assert any("Exploration memory:" in item for item in adapter.exploration_contexts)
    assert explorer.state_embedding_records
```

- [ ] **Step 4: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_llm_action_selector.py tests/safesym_bridge/test_stagehand_backend.py tests/safesym_bridge/test_web_kobe_explorer.py -v
```

Expected: FAIL because request/context/backend/explorer interfaces do not exist yet.

- [ ] **Step 5: Update LLM action selector to include exploration context**

Modify `src/ai_web_explorer/grounded_web/llm_action_selector.py`:

```python
@dataclass(frozen=True)
class LlmActionSelectionRequest:
    goal: str
    state: StateSnapshot
    candidate_actions: list[BrowserAction]
    exploration_context: dict[str, Any] | None = None
```

In `_prompt_for_request`, add this key to the payload:

```python
"exploration_context": request.exploration_context or {},
```

In `_trace`, add `exploration_context` to `LlmActionSelectionTrace` and `to_dict()` so selector traces preserve why actions were avoided.

- [ ] **Step 6: Update Stagehand backend with dynamic context**

Modify `src/ai_web_explorer/grounded_web/stagehand_backend.py`:

```python
def set_exploration_context(self, prompt_block: str | None) -> None:
    self._exploration_context_prompt = prompt_block
```

Initialize `self._exploration_context_prompt = None` in `__init__`.

In `_execute_business_milestone`, before calling the provider:

```python
instruction = goal
if self._exploration_context_prompt:
    instruction = "\n\n".join([goal, self._exploration_context_prompt])
```

Use `instruction` for `execute_instruction`, `act_instruction`, and `StagehandStepTrace(instruction=instruction, ...)`.

- [ ] **Step 7: Update explorer to build and pass exploration context**

Modify `src/ai_web_explorer/grounded_web/explorer.py` imports:

```python
from ai_web_explorer.grounded_web.exploration_index import build_exploration_context
from ai_web_explorer.grounded_web.state_embedding import (
    EmbeddingProvider,
    StateEmbeddingRecord,
    find_best_state_match,
)
from ai_web_explorer.grounded_web.state_summary import build_state_summary
```

Extend `WebKobeExplorer.__init__`:

```python
state_embedding_provider: EmbeddingProvider | None = None,
state_embedding_records: list[StateEmbeddingRecord] | None = None,
enable_exploration_memory: bool = False,
```

Store:

```python
self.state_embedding_provider = state_embedding_provider
self.state_embedding_records = list(state_embedding_records or [])
self.enable_exploration_memory = enable_exploration_memory
```

After `source_id` is known in `explore_one_step`, build active facts:

```python
graph_before_action = self.manager.to_graph(start_node_id=self._start_node_id)
nodes_by_id = {node.node_id: node for node in graph_before_action.nodes}
source_node = nodes_by_id[source_id]
active_facts = (
    source_node.planning_state.active_facts
    if source_node.planning_state is not None
    else []
)
source_summary = build_state_summary(
    snapshot=before,
    interactables=source_interactables,
    active_planning_facts=active_facts,
)
state_match = None
if self.enable_exploration_memory and self.state_embedding_provider is not None:
    state_match = find_best_state_match(
        source_summary,
        self.state_embedding_records,
        embedding_provider=self.state_embedding_provider,
    )
exploration_context = build_exploration_context(
    graph_before_action,
    current_node_id=source_id,
    state_match=state_match,
)
set_context = getattr(self.adapter, "set_exploration_context", None)
if set_context is not None:
    set_context(exploration_context.to_prompt_block())
```

Change `_select_action` signature to accept `exploration_context`.

When constructing `LlmActionSelectionRequest`, pass:

```python
exploration_context={
    "prompt_block": exploration_context.to_prompt_block(),
    "avoid_action_ids": list(exploration_context.avoid_action_ids),
    "tried_action_ids": list(exploration_context.tried_action_ids),
}
```

After target node is identified, append or update the embedding record for the target:

```python
if self.enable_exploration_memory and self.state_embedding_provider is not None:
    target_summary = build_state_summary(
        snapshot=after,
        interactables=after_interactables,
        active_planning_facts=[],
        visual_summary=execution_metadata.get("visual_change_summary"),
    )
    target_embedding = self.state_embedding_provider(target_summary.text)
    self.state_embedding_records = [
        record
        for record in self.state_embedding_records
        if record.node_id != target_id
    ]
    self.state_embedding_records.append(
        StateEmbeddingRecord(
            node_id=target_id,
            summary_text=target_summary.text,
            embedding=list(target_embedding),
            planning_facts=target_summary.planning_facts,
            context_markers=target_summary.context_markers,
        )
    )
```

- [ ] **Step 8: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_state_summary.py tests/safesym_bridge/test_state_embedding.py tests/safesym_bridge/test_exploration_index.py tests/safesym_bridge/test_llm_action_selector.py tests/safesym_bridge/test_stagehand_backend.py tests/safesym_bridge/test_web_kobe_explorer.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/explorer.py src/ai_web_explorer/grounded_web/llm_action_selector.py src/ai_web_explorer/grounded_web/stagehand_backend.py tests/safesym_bridge/test_llm_action_selector.py tests/safesym_bridge/test_stagehand_backend.py tests/safesym_bridge/test_web_kobe_explorer.py
git commit -m "feat: wire exploration memory into action selection"
```

---

### Task 5: Generic Stagehand Exploration Runner and CLI

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/stagehand_prompt.py`
- Create: `src/ai_web_explorer/grounded_web/openai_state_embedding.py`
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Test: `tests/safesym_bridge/test_stagehand_prompt.py`
- Test: `tests/safesym_bridge/test_openai_state_embedding.py`
- Test: `tests/safesym_bridge/test_browser_runner.py`
- Test: `tests/safesym_bridge/test_cli.py`

**Interfaces:**
- Produces:
  - `build_generic_stagehand_exploration_goal(site_purpose: str | None = None) -> str`
  - `OpenAIStateEmbeddingProvider`
  - `create_openai_state_embedding_provider_from_env(model: str | None = None, ...) -> OpenAIStateEmbeddingProvider`
  - `run_stagehand_exploration(...) -> Path`
  - CLI subcommand `web-kobe-stagehand-explore`

- [ ] **Step 1: Write failing prompt test**

Create or modify `tests/safesym_bridge/test_stagehand_prompt.py`:

```python
from ai_web_explorer.grounded_web.stagehand_prompt import build_generic_stagehand_exploration_goal


def test_generic_stagehand_exploration_goal_is_not_checkout_specific():
    goal = build_generic_stagehand_exploration_goal(site_purpose="demo store")

    assert "demo store" in goal
    assert "Choose one useful site-function action" in goal
    assert "Avoid low-value footer, legal, social, theme, and language actions" in goal
    assert "checkout" not in goal.lower()
    assert "payment" not in goal.lower()
```

- [ ] **Step 2: Write failing OpenAI embedding provider test**

Create `tests/safesym_bridge/test_openai_state_embedding.py`:

```python
import pytest

from ai_web_explorer.grounded_web.openai_state_embedding import (
    DEFAULT_OPENAI_STATE_EMBEDDING_MODEL,
    OpenAIStateEmbeddingProvider,
    create_openai_state_embedding_provider_from_env,
)


class FakeEmbeddingResponse:
    class Item:
        embedding = [0.1, 0.2, 0.3]

    data = [Item()]


class FakeEmbeddings:
    def __init__(self):
        self.calls = []

    def create(self, *, model, input):
        self.calls.append((model, input))
        return FakeEmbeddingResponse()


class FakeClient:
    def __init__(self):
        self.embeddings = FakeEmbeddings()


def test_openai_state_embedding_provider_returns_embedding():
    client = FakeClient()
    provider = OpenAIStateEmbeddingProvider(client=client, model="text-embedding-test")

    assert provider("hello state") == [0.1, 0.2, 0.3]
    assert client.embeddings.calls == [("text-embedding-test", "hello state")]


def test_create_openai_state_embedding_provider_requires_key():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        create_openai_state_embedding_provider_from_env(
            environ={},
            load_dotenv=lambda: None,
            openai_factory=lambda **kwargs: FakeClient(),
        )


def test_create_openai_state_embedding_provider_uses_default_model():
    provider = create_openai_state_embedding_provider_from_env(
        environ={"OPENAI_API_KEY": "test"},
        load_dotenv=lambda: None,
        openai_factory=lambda **kwargs: FakeClient(),
    )

    assert provider.model == DEFAULT_OPENAI_STATE_EMBEDDING_MODEL
```

- [ ] **Step 3: Write failing runner and CLI tests**

Add to `tests/safesym_bridge/test_browser_runner.py`:

```python
@pytest.mark.anyio
async def test_run_stagehand_exploration_wires_generic_stagehand_backend(
    tmp_path,
    monkeypatch,
):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "graph.json"
    embedding_path = tmp_path / "state_embeddings.json"
    calls = []

    class FakePage:
        async def goto(self, url):
            calls.append(("goto", url))

    class FakeBrowser:
        async def new_page(self):
            return FakePage()

        async def close(self):
            calls.append(("close", None))

    class FakeChromium:
        async def launch(self, *, headless=True, args=None):
            calls.append(("launch", headless, args))
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakePlaywrightContext:
        async def __aenter__(self):
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    class FakeBaseAdapter:
        def __init__(self, page, *, app_name, page_id=None, screenshot_dir=None):
            self.app_name = app_name

    class FakeStagehandBackend:
        def __init__(self, *, base_backend, provider, goal, execution_mode, **kwargs):
            calls.append(("stagehand", goal, execution_mode))
            self.app_name = base_backend.app_name

    class FakeController:
        def __init__(self, explorer):
            assert explorer.enable_exploration_memory is True
            assert explorer.state_embedding_provider("x") == [1.0, 0.0]

        async def run(self, *, max_steps):
            return WebKobeExplorationResult(
                graph=WebKobeGraph(
                    app="demo",
                    start_node_id="start",
                    total_steps_completed=max_steps,
                ),
                summary=WebKobeExplorationSummary(
                    requested_steps=max_steps,
                    steps_completed=max_steps,
                    stop_reason="max_steps",
                    node_count=0,
                    edge_count=0,
                    failed_edge_count=0,
                ),
            )

    monkeypatch.setattr(playwright_async_api, "async_playwright", lambda: FakePlaywrightContext())
    monkeypatch.setattr(browser_runner, "WebKobePlaywrightAdapter", FakeBaseAdapter)
    monkeypatch.setattr(browser_runner, "StagehandAutomationBackend", FakeStagehandBackend)
    monkeypatch.setattr(browser_runner, "WebKobeExplorationController", FakeController)

    result = await browser_runner.run_stagehand_exploration(
        output_path,
        start_url="https://shop.test/",
        app_name="demo",
        provider=object(),
        steps=3,
        state_embedding_provider=lambda text: [1.0, 0.0],
        state_embedding_path=embedding_path,
        site_purpose="demo store",
    )

    assert result == output_path
    assert ("goto", "https://shop.test/") in calls
    assert any(call[0] == "stagehand" and call[2] == "business_milestone" for call in calls)
    assert output_path.exists()
    assert embedding_path.exists()
```

Add to `tests/safesym_bridge/test_cli.py`:

```python
def test_main_web_kobe_stagehand_explore_wires_runner(monkeypatch, tmp_path):
    output = tmp_path / "graph.json"
    trace = tmp_path / "trace.json"
    embeddings = tmp_path / "state_embeddings.json"
    calls = []

    async def fake_run_stagehand_exploration(
        output_path,
        *,
        start_url,
        app_name,
        stagehand_trace_path=None,
        model=None,
        steps=8,
        headless=True,
        screenshot_dir=None,
        state_embedding_path=None,
        use_openai_state_embeddings=False,
        state_embedding_model=None,
        site_purpose=None,
    ):
        calls.append(
            (
                output_path,
                start_url,
                app_name,
                stagehand_trace_path,
                model,
                steps,
                headless,
                screenshot_dir,
                state_embedding_path,
                use_openai_state_embeddings,
                state_embedding_model,
                site_purpose,
            )
        )
        output_path.write_text("{}", encoding="utf-8")
        return output_path

    monkeypatch.setattr(cli, "run_stagehand_exploration", fake_run_stagehand_exploration, raising=False)

    exit_code = main(
        [
            "web-kobe-stagehand-explore",
            "--url",
            "https://shop.test/",
            "--app-name",
            "demo",
            "--output",
            str(output),
            "--stagehand-trace",
            str(trace),
            "--steps",
            "4",
            "--model",
            "deepseek/test",
            "--screenshot-dir",
            str(tmp_path / "screenshots"),
            "--state-embedding-path",
            str(embeddings),
            "--openai-state-embeddings",
            "--state-embedding-model",
            "text-embedding-test",
            "--site-purpose",
            "demo store",
            "--headed",
        ]
    )

    assert exit_code == 0
    assert calls == [
        (
            output,
            "https://shop.test/",
            "demo",
            trace,
            "deepseek/test",
            4,
            False,
            tmp_path / "screenshots",
            embeddings,
            True,
            "text-embedding-test",
            "demo store",
        )
    ]
```

- [ ] **Step 4: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_stagehand_prompt.py tests/safesym_bridge/test_openai_state_embedding.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_cli.py -v
```

Expected: FAIL because generic prompt, OpenAI state embedding provider, runner, and CLI command are missing.

- [ ] **Step 5: Add generic Stagehand exploration prompt**

Modify `src/ai_web_explorer/grounded_web/stagehand_prompt.py`:

```python
GENERIC_EXPLORATION_ACTION_POLICY = (
    "Choose one useful site-function action from visible page evidence. "
    "Prefer actions that reveal product, search, filtering, account, cart, form, "
    "settings, content, or workflow functionality. Avoid low-value footer, legal, "
    "social, theme, and language actions unless they are central to the site. "
    "Stop after one meaningful transition and report visible evidence."
)


def build_generic_stagehand_exploration_goal(
    *,
    site_purpose: str | None = None,
) -> str:
    purpose = site_purpose or "the current website"
    return "\n\n".join(
        [
            f"Site purpose:\n{purpose}",
            f"Action policy:\n{GENERIC_EXPLORATION_ACTION_POLICY}",
            (
                "Memory policy:\nWeb-KOBE may append exploration memory below. "
                "Use it to avoid repeated or no-op actions."
            ),
        ]
    )
```

- [ ] **Step 6: Add OpenAI state embedding provider**

Create `src/ai_web_explorer/grounded_web/openai_state_embedding.py`:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Mapping

DEFAULT_OPENAI_STATE_EMBEDDING_MODEL = "text-embedding-3-small"


@dataclass(frozen=True)
class OpenAIStateEmbeddingProvider:
    client: Any
    model: str = DEFAULT_OPENAI_STATE_EMBEDDING_MODEL

    def __call__(self, text: str) -> list[float]:
        response = self.client.embeddings.create(model=self.model, input=text)
        return [float(value) for value in response.data[0].embedding]


def create_openai_state_embedding_provider_from_env(
    *,
    model: str | None = None,
    openai_factory: Callable[..., Any] | None = None,
    load_dotenv: Callable[[], Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> OpenAIStateEmbeddingProvider:
    if load_dotenv is None:
        from dotenv import load_dotenv as load_dotenv
    load_dotenv()

    env = os.environ if environ is None else environ
    api_key = env.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for OpenAI state embeddings.")
    if openai_factory is None:
        import openai

        openai_factory = openai.OpenAI
    base_url = env.get("OPENAI_BASE_URL") or None
    selected_model = model or env.get("OPENAI_STATE_EMBEDDING_MODEL") or DEFAULT_OPENAI_STATE_EMBEDDING_MODEL
    return OpenAIStateEmbeddingProvider(
        client=openai_factory(api_key=api_key, base_url=base_url),
        model=selected_model,
    )
```

- [ ] **Step 7: Add generic Stagehand exploration runner**

Modify `src/ai_web_explorer/safesym_bridge/browser_runner.py` imports:

```python
from ai_web_explorer.grounded_web.openai_state_embedding import (
    create_openai_state_embedding_provider_from_env,
)
from ai_web_explorer.grounded_web.stagehand_prompt import (
    build_generic_stagehand_exploration_goal,
)
from ai_web_explorer.grounded_web.state_embedding import (
    read_state_embedding_records,
    write_state_embedding_records,
)
```

Add:

```python
async def run_stagehand_exploration(
    output_path: Path,
    *,
    start_url: str,
    app_name: str = "web",
    stagehand_trace_path: Path | None = None,
    headless: bool = True,
    steps: int = 8,
    provider=None,
    model: str | None = None,
    screenshot_dir: Path | None = None,
    state_embedding_provider=None,
    state_embedding_path: Path | None = None,
    use_openai_state_embeddings: bool = False,
    state_embedding_model: str | None = None,
    site_purpose: str | None = None,
) -> Path:
    from playwright.async_api import async_playwright

    resolved_embedding_provider = state_embedding_provider
    if resolved_embedding_provider is None and use_openai_state_embeddings:
        resolved_embedding_provider = create_openai_state_embedding_provider_from_env(
            model=state_embedding_model
        )
    embedding_records = (
        read_state_embedding_records(state_embedding_path)
        if state_embedding_path is not None
        else []
    )
    stagehand_goal = build_generic_stagehand_exploration_goal(site_purpose=site_purpose)
    cdp_port = _pick_free_port() if provider is None else None
    launch_args = [f"--remote-debugging-port={cdp_port}"] if cdp_port is not None else None
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless, args=launch_args)
        local_cdp_url = _read_cdp_websocket_url(cdp_port) if cdp_port is not None else None
        page = await browser.new_page()
        try:
            await page.goto(start_url)
            resolved_provider = provider
            if resolved_provider is None:
                resolved_provider = await create_async_stagehand_provider_from_env(
                    model_name=model,
                    page=page,
                    local_cdp_url=local_cdp_url,
                )
            base_adapter = WebKobePlaywrightAdapter(
                page,
                app_name=app_name,
                screenshot_dir=screenshot_dir,
            )
            adapter = StagehandAutomationBackend(
                base_backend=base_adapter,
                provider=resolved_provider,
                goal=stagehand_goal,
                execution_mode="business_milestone",
            )
            explorer = WebKobeExplorer(
                adapter=adapter,
                semantic_assistor=DeterministicSemanticAssistor(app=app_name),
                goal="Explore useful website functionality.",
                capture_screenshots=screenshot_dir is not None,
                enable_exploration_memory=resolved_embedding_provider is not None,
                state_embedding_provider=resolved_embedding_provider,
                state_embedding_records=embedding_records,
            )
            controller = WebKobeExplorationController(explorer)
            result = await controller.run(max_steps=max(steps, 1))
            write_web_kobe_graph(result.graph, output_path)
            if state_embedding_path is not None:
                write_state_embedding_records(
                    state_embedding_path,
                    explorer.state_embedding_records,
                )
            if stagehand_trace_path is not None:
                traces = [
                    edge.execution_trace.metadata
                    for edge in result.graph.edges
                    if edge.execution_trace.metadata.get("action_source") == "stagehand"
                ]
                stagehand_trace_path.parent.mkdir(parents=True, exist_ok=True)
                stagehand_trace_path.write_text(
                    json.dumps(traces, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            return output_path
        finally:
            await browser.close()
```

- [ ] **Step 8: Add CLI command**

Modify `src/ai_web_explorer/safesym_bridge/cli.py` imports:

```python
run_stagehand_exploration,
```

Add parser:

```python
stagehand_explore_parser = subparsers.add_parser(
    "web-kobe-stagehand-explore",
    help="Run generic Stagehand-backed Web-KOBE exploration with graph memory.",
)
stagehand_explore_parser.add_argument("--url", required=True)
stagehand_explore_parser.add_argument("--app-name", default="web")
stagehand_explore_parser.add_argument("--output", type=Path, default=Path("outputs/latest/stagehand_explore_graph.json"))
stagehand_explore_parser.add_argument("--stagehand-trace", type=Path, default=Path("outputs/latest/stagehand_explore_trace.json"))
stagehand_explore_parser.add_argument("--model", default=None)
stagehand_explore_parser.add_argument("--steps", type=int, default=8)
stagehand_explore_parser.add_argument("--screenshot-dir", type=Path, default=None)
stagehand_explore_parser.add_argument("--state-embedding-path", type=Path, default=Path("outputs/latest/state_embeddings.json"))
stagehand_explore_parser.add_argument("--openai-state-embeddings", action="store_true")
stagehand_explore_parser.add_argument("--state-embedding-model", default=None)
stagehand_explore_parser.add_argument("--site-purpose", default=None)
stagehand_explore_parser.add_argument("--headed", action="store_true")
```

Add branch:

```python
elif args.mode == "web-kobe-stagehand-explore":
    output_path = asyncio.run(
        run_stagehand_exploration(
            args.output,
            start_url=args.url,
            app_name=args.app_name,
            stagehand_trace_path=args.stagehand_trace,
            model=args.model,
            steps=args.steps,
            headless=not args.headed,
            screenshot_dir=args.screenshot_dir,
            state_embedding_path=args.state_embedding_path,
            use_openai_state_embeddings=args.openai_state_embeddings,
            state_embedding_model=args.state_embedding_model,
            site_purpose=args.site_purpose,
        )
    )
```

- [ ] **Step 9: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_stagehand_prompt.py tests/safesym_bridge/test_openai_state_embedding.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 10: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/stagehand_prompt.py src/ai_web_explorer/grounded_web/openai_state_embedding.py src/ai_web_explorer/safesym_bridge/browser_runner.py src/ai_web_explorer/safesym_bridge/cli.py tests/safesym_bridge/test_stagehand_prompt.py tests/safesym_bridge/test_openai_state_embedding.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_cli.py
git commit -m "feat: add generic stagehand exploration runner"
```

---

### Task 6: PDDL Safety Regression and Full Verification

**Files:**
- Modify: `tests/safesym_bridge/test_web_kobe_pddl_projector.py`
- Modify: `docs/current-project-overview.md`
- Modify: `docs/current-project-overview.zh-CN.md`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: regression confidence that exploration metadata and embeddings do not leak into PDDL.

- [ ] **Step 1: Add regression test for metadata exclusion**

Add to `tests/safesym_bridge/test_web_kobe_pddl_projector.py`:

```python
def test_compile_web_kobe_graph_to_pddl_excludes_exploration_metadata():
    graph = WebKobeGraph(
        app="example",
        start_node_id="start",
        total_steps_completed=1,
        nodes=[
            WebKobeNode(
                node_id="start",
                page_description="start",
                page_frame=PageFrame(
                    page_id="start",
                    page_type="start",
                    url="https://example.test/",
                    url_pattern="https://example.test/",
                    title="Start",
                ),
                state_schema={},
                last_state_snapshot={},
                state_summary="url_path: / start embedding text",
            ),
            WebKobeNode(
                node_id="cart",
                page_description="cart",
                page_frame=PageFrame(
                    page_id="cart",
                    page_type="cart",
                    url="https://example.test/cart",
                    url_pattern="https://example.test/cart",
                    title="Cart",
                ),
                state_schema={},
                last_state_snapshot={},
            ),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="start",
                target_node_id="cart",
                instruction="open cart",
                action=BrowserAction("click", "#cart", "open_cart"),
                capability=None,
                target_observation="cart",
                observed_delta=[],
                schema_delta={"ui_region": {"before": "home", "after": "cart"}},
                execution_trace=ExecutionTrace(
                    "click",
                    "#cart",
                    "open_cart",
                    {},
                    "start",
                    "cart",
                    True,
                    metadata={
                        "exploration_context": "Avoid repeating actions: theme_toggle",
                        "state_similarity": 0.94,
                    },
                ),
                status="succeeded_with_navigation",
            )
        ],
        meta={"state_embeddings": [[0.1, 0.2, 0.3]]},
    )

    artifacts = compile_web_kobe_graph_to_pddl(graph, goal_node_id="cart")

    combined = artifacts.domain + "\n" + artifacts.problem
    assert "embedding" not in combined
    assert "theme_toggle" not in combined
    assert "state_similarity" not in combined
    assert "ui_region" not in combined
```

- [ ] **Step 2: Run test to verify current behavior**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py::test_compile_web_kobe_graph_to_pddl_excludes_exploration_metadata -v
```

Expected: PASS if the existing projector already excludes these fields. If it fails, fix only the projector filtering path that caused leakage.

- [ ] **Step 3: Update project overview docs**

Modify both overview docs to say:

```text
The near-term direction now includes an OpenMobile/SEE-style exploration V1.
The graph remains the only persistent memory. Embeddings and the exploration
index are query aids for revisit detection and action de-duplication; they do
not enter PDDL. The first target is a bounded generic Stagehand exploration
loop, not full free exploration coverage.
```

Chinese equivalent:

```text
近期方向加入 OpenMobile/SEE 风格的探索 V1。graph 仍然是唯一持久化记忆。
embedding 和 exploration index 只是用于重复状态识别和动作去重的查询辅助，
不会进入 PDDL。第一目标是有边界的通用 Stagehand 探索闭环，不是完整自由探索覆盖率。
```

- [ ] **Step 4: Run focused and full tests**

Run focused tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_state_summary.py tests/safesym_bridge/test_state_embedding.py tests/safesym_bridge/test_exploration_index.py tests/safesym_bridge/test_llm_action_selector.py tests/safesym_bridge/test_stagehand_backend.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_cli.py tests/safesym_bridge/test_web_kobe_pddl_projector.py -v
```

Run full suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add tests/safesym_bridge/test_web_kobe_pddl_projector.py docs/current-project-overview.md docs/current-project-overview.zh-CN.md
git commit -m "test: guard exploration metadata from pddl"
```

---

## Real Experiment Command After Implementation

After all tests pass, run a real exploration experiment only when explicitly requested:

```powershell
.\.venv\Scripts\python.exe -m ai_web_explorer.safesym_bridge.cli web-kobe-stagehand-explore `
  --url https://practiceautomatedtesting.com/shopping `
  --app-name practice_automated_testing_explore `
  --output outputs/experiments/practice_automated_testing/latest/graph.json `
  --stagehand-trace outputs/experiments/practice_automated_testing/latest/stagehand_trace.json `
  --screenshot-dir outputs/experiments/practice_automated_testing/latest/screenshots `
  --state-embedding-path outputs/experiments/practice_automated_testing/latest/state_embeddings.json `
  --openai-state-embeddings `
  --model deepseek/deepseek-v4-flash `
  --steps 6 `
  --site-purpose "public demo e-commerce shopping site"
```

This command requires browser/model/network approval and should not be run during unit-test implementation.

---

## Self-Review

**Spec coverage:** The plan covers state summaries, embedding state matching, graph-derived memory/index, Stagehand exploration prompt/context, generic exploration CLI, fake backend tests, and PDDL non-leakage.

**Scope control:** The plan does not add replay, backtracking, vector DB, verifier redesign, or full coverage optimization.

**Type consistency:** `StateSummary`, `StateEmbeddingRecord`, `StateMatch`, `ExplorationContext`, and the new `WebKobeExplorer` constructor parameters are introduced before later tasks consume them.

**PDDL boundary:** Task 6 explicitly verifies that exploration metadata and embedding text do not enter generated PDDL.
