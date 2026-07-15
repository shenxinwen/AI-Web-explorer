# Grounded Web Action Loop v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not use subagents unless the user explicitly permits multi-agent work.

**Goal:** Build a grounded one-step action loop that resolves `ActionIntent` into a concrete `BrowserAction`, executes it, observes before/after state, derives deltas, and classifies the outcome.

**Architecture:** Add a narrow protocol layer inside `grounded_web`: `action_intent.py` owns intent/expectation/result models plus deterministic resolution/evaluation helpers, and `action_loop.py` owns async orchestration through `AutomationBackend`. `WebKobeExplorer` will route selected actions through the loop while preserving the existing graph shape.

**Tech Stack:** Python dataclasses, async `AutomationBackend`, Playwright-backed adapter, pytest/anyio, existing `ObservedDelta`, `BrowserAction`, `StateSnapshot`, `typed_delta.py`, and `state_signature.py`.

## Global Constraints

- Do not call a real LLM API.
- Do not design prompts.
- Do not add multi-step planning.
- Do not allow LLMs or planners to generate raw CSS or XPath selectors.
- Do not move DOM or Playwright responsibility into `safesym_bridge`.
- Do not introduce app-specific assumptions such as shopping carts, checkout flows, or search result semantics beyond test fixtures.
- Keep `grounded_web` independent from `safesym_bridge` imports.
- Keep `current-project-overview.md` and `current-project-overview.zh-CN.md` updated when the stage changes the main pipeline.

---

## File Structure

- Create `src/ai_web_explorer/grounded_web/action_intent.py`
  - Owns `ActionExpectation`, `ActionIntent`, `OutcomeEvaluation`, `ActionExecutionResult`.
  - Owns pure helpers: `browser_action_from_record()`, `resolve_action_intent()`, and `evaluate_outcome()`.
- Create `src/ai_web_explorer/grounded_web/action_loop.py`
  - Owns async orchestration: `execute_action_intent()`.
  - Converts before/after facts into `ObservedDelta`, with schema-delta fallback.
- Modify `src/ai_web_explorer/grounded_web/explorer.py`
  - Reuse action loop results instead of directly calling `adapter.execute(selected)`.
  - Preserve graph output fields and existing `ExecutionTrace` behavior.
- Add `tests/safesym_bridge/test_grounded_action_intent.py`
  - Tests pure resolution and evaluation behavior.
- Add `tests/safesym_bridge/test_grounded_action_loop.py`
  - Tests async loop behavior with fake adapters.
- Modify `tests/safesym_bridge/test_observation_to_state_form_search.py`
  - Add one Playwright-backed action-loop fixture test using `local_form_search`.
- Modify `tests/safesym_bridge/test_web_kobe_explorer.py`
  - Adjust or extend expectations for new outcome statuses.
- Modify `docs/current-project-overview.md`
  - Record the new action-loop layer in the active pipeline.
- Modify `docs/current-project-overview.zh-CN.md`
  - Mirror the same stage update in Chinese, preserving UTF-8.

---

### Task 1: Add Action Intent Models, Resolver, and Evaluator

**Files:**
- Create: `src/ai_web_explorer/grounded_web/action_intent.py`
- Test: `tests/safesym_bridge/test_grounded_action_intent.py`

**Interfaces:**
- Consumes:
  - `ai_web_explorer.grounded_web.graph.BrowserAction`
  - `ai_web_explorer.grounded_web.models.StateSnapshot`
  - `ai_web_explorer.grounded_web.capability_graph.ObservedDelta`
- Produces:
  - `ActionExpectation`
  - `ActionIntent`
  - `OutcomeEvaluation`
  - `ActionExecutionResult`
  - `browser_action_from_record(record: BrowserAction | dict[str, Any]) -> BrowserAction`
  - `resolve_action_intent(intent: ActionIntent, available_actions: list[BrowserAction | dict[str, Any]]) -> BrowserAction | None`
  - `evaluate_outcome(*, execution_success: bool, execution_error: str | None, deltas: list[ObservedDelta], expectation: ActionExpectation | None) -> OutcomeEvaluation`

- [ ] **Step 1: Write failing resolver/evaluator tests**

Create `tests/safesym_bridge/test_grounded_action_intent.py`:

```python
from ai_web_explorer.grounded_web.action_intent import (
    ActionExpectation,
    ActionIntent,
    evaluate_outcome,
    resolve_action_intent,
)
from ai_web_explorer.grounded_web.capability_graph import ObservedDelta
from ai_web_explorer.grounded_web.graph import BrowserAction


def test_resolve_action_intent_prefers_semantic_id_and_kind():
    intent = ActionIntent(
        action_kind="click",
        target_semantic_id="submit_search",
        target_description=None,
        input_values={},
        expectation=None,
        source="rule_based",
    )
    actions = [
        BrowserAction(
            action_kind="fill",
            locator="#query",
            semantic_id="query_input",
            description="Search query",
        ),
        BrowserAction(
            action_kind="click",
            locator="#submit",
            semantic_id="submit_search",
            description="Search",
        ),
    ]

    resolved = resolve_action_intent(intent, actions)

    assert resolved == actions[1]


def test_resolve_action_intent_falls_back_to_description_match():
    intent = ActionIntent(
        action_kind="click",
        target_semantic_id=None,
        target_description="search",
        input_values={},
        expectation=None,
        source="rule_based",
    )
    actions = [
        {
            "semantic_id": "submit_search",
            "description": "Search",
            "locator": "#submit",
            "action_kind": "click",
            "input_values": {},
        }
    ]

    resolved = resolve_action_intent(intent, actions)

    assert resolved is not None
    assert resolved.semantic_id == "submit_search"
    assert resolved.locator == "#submit"


def test_resolve_action_intent_returns_none_for_missing_target():
    intent = ActionIntent(
        action_kind="click",
        target_semantic_id="missing",
        target_description=None,
        input_values={},
        expectation=None,
        source="rule_based",
    )

    assert resolve_action_intent(intent, []) is None


def test_intent_input_values_override_resolved_action_values():
    intent = ActionIntent(
        action_kind="fill",
        target_semantic_id="query_input",
        target_description=None,
        input_values={"#query": "kobe"},
        expectation=None,
        source="rule_based",
    )
    action = BrowserAction(
        action_kind="fill",
        locator="#query",
        semantic_id="query_input",
        input_values={"#query": "test"},
        description="Query",
    )

    resolved = resolve_action_intent(intent, [action])

    assert resolved is not None
    assert resolved.input_values == {"#query": "kobe"}


def test_evaluate_outcome_failed_execution_preserves_error():
    outcome = evaluate_outcome(
        execution_success=False,
        execution_error="locator_not_visible",
        deltas=[],
        expectation=None,
    )

    assert outcome.status == "failed_execution"
    assert outcome.reason == "locator_not_visible"
    assert outcome.matched_expectation is False


def test_evaluate_outcome_no_observed_change():
    outcome = evaluate_outcome(
        execution_success=True,
        execution_error=None,
        deltas=[],
        expectation=None,
    )

    assert outcome.status == "no_observed_change"
    assert outcome.matched_expectation is None


def test_evaluate_outcome_field_changed_matches_delta():
    outcome = evaluate_outcome(
        execution_success=True,
        execution_error=None,
        deltas=[
            ObservedDelta(
                field="result_count",
                before=0,
                after=3,
                delta_type="numeric_changed",
            )
        ],
        expectation=ActionExpectation(kind="field_changed", field="result_count"),
    )

    assert outcome.status == "succeeded"
    assert outcome.matched_expectation is True


def test_evaluate_outcome_field_equals_mismatch_is_unexpected_change():
    outcome = evaluate_outcome(
        execution_success=True,
        execution_error=None,
        deltas=[
            ObservedDelta(
                field="status",
                before="idle",
                after="error",
                delta_type="value_changed",
            )
        ],
        expectation=ActionExpectation(
            kind="field_equals",
            field="status",
            expected_value="complete",
        ),
    )

    assert outcome.status == "unexpected_change"
    assert outcome.matched_expectation is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_grounded_action_intent.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'ai_web_explorer.grounded_web.action_intent'`.

- [ ] **Step 3: Implement models and pure helpers**

Create `src/ai_web_explorer/grounded_web/action_intent.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from ai_web_explorer.grounded_web.capability_graph import ObservedDelta
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.models import StateSnapshot


@dataclass(frozen=True)
class ActionExpectation:
    kind: str
    field: str | None = None
    expected_value: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "field": self.field,
            "expected_value": self.expected_value,
        }


@dataclass(frozen=True)
class ActionIntent:
    action_kind: str
    target_semantic_id: str | None = None
    target_description: str | None = None
    input_values: dict[str, str] = field(default_factory=dict)
    expectation: ActionExpectation | None = None
    source: str = "rule_based"

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_kind": self.action_kind,
            "target_semantic_id": self.target_semantic_id,
            "target_description": self.target_description,
            "input_values": dict(self.input_values),
            "expectation": (
                self.expectation.to_dict() if self.expectation is not None else None
            ),
            "source": self.source,
        }


@dataclass(frozen=True)
class OutcomeEvaluation:
    status: str
    reason: str
    matched_expectation: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "matched_expectation": self.matched_expectation,
        }


@dataclass(frozen=True)
class ActionExecutionResult:
    intent: ActionIntent
    action: BrowserAction | None
    before: StateSnapshot
    after: StateSnapshot | None
    observed_delta: list[ObservedDelta]
    execution_success: bool
    execution_error: str | None
    outcome: OutcomeEvaluation

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.to_dict(),
            "action": self.action.to_dict() if self.action is not None else None,
            "before": {
                "page_id": self.before.page_id,
                "url": self.before.url,
                "title": self.before.title,
                "signature": dict(self.before.signature),
            },
            "after": (
                {
                    "page_id": self.after.page_id,
                    "url": self.after.url,
                    "title": self.after.title,
                    "signature": dict(self.after.signature),
                }
                if self.after is not None
                else None
            ),
            "observed_delta": [delta.to_dict() for delta in self.observed_delta],
            "execution_success": self.execution_success,
            "execution_error": self.execution_error,
            "outcome": self.outcome.to_dict(),
        }


def browser_action_from_record(action: BrowserAction | dict[str, Any]) -> BrowserAction:
    if isinstance(action, BrowserAction):
        return action
    return BrowserAction(
        action_kind=str(action.get("action_kind") or ""),
        locator=action.get("locator"),
        semantic_id=str(action.get("semantic_id") or ""),
        input_values=dict(action.get("input_values") or {}),
        description=action.get("description"),
    )


def _with_intent_inputs(action: BrowserAction, intent: ActionIntent) -> BrowserAction:
    if not intent.input_values:
        return action
    return replace(action, input_values=dict(intent.input_values))


def resolve_action_intent(
    intent: ActionIntent,
    available_actions: list[BrowserAction | dict[str, Any]],
) -> BrowserAction | None:
    normalized = [browser_action_from_record(action) for action in available_actions]
    if intent.target_semantic_id is not None:
        for action in normalized:
            if (
                action.semantic_id == intent.target_semantic_id
                and action.action_kind == intent.action_kind
            ):
                return _with_intent_inputs(action, intent)

    description = (intent.target_description or "").strip().lower()
    if description:
        for action in normalized:
            action_description = (action.description or "").strip().lower()
            if action.action_kind == intent.action_kind and description in action_description:
                return _with_intent_inputs(action, intent)

    return None


def _expectation_matches(
    expectation: ActionExpectation,
    deltas: list[ObservedDelta],
) -> bool:
    if expectation.kind == "any_state_change":
        return bool(deltas)
    if expectation.kind == "field_changed":
        return any(delta.field == expectation.field for delta in deltas)
    if expectation.kind == "field_equals":
        return any(
            delta.field == expectation.field and delta.after == expectation.expected_value
            for delta in deltas
        )
    return False


def evaluate_outcome(
    *,
    execution_success: bool,
    execution_error: str | None,
    deltas: list[ObservedDelta],
    expectation: ActionExpectation | None,
) -> OutcomeEvaluation:
    if not execution_success:
        return OutcomeEvaluation(
            status="failed_execution",
            reason=execution_error or "adapter execution returned false",
            matched_expectation=False,
        )

    if not deltas:
        return OutcomeEvaluation(
            status="no_observed_change",
            reason="execution succeeded but no state delta was observed",
            matched_expectation=None if expectation is None else False,
        )

    if expectation is None:
        return OutcomeEvaluation(
            status="succeeded_with_observed_change",
            reason="execution succeeded and state changed",
            matched_expectation=None,
        )

    if _expectation_matches(expectation, deltas):
        return OutcomeEvaluation(
            status="succeeded",
            reason=f"expectation matched: {expectation.kind}",
            matched_expectation=True,
        )

    return OutcomeEvaluation(
        status="unexpected_change",
        reason=f"expectation did not match: {expectation.kind}",
        matched_expectation=False,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_grounded_action_intent.py -q
```

Expected: all tests in `test_grounded_action_intent.py` pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/ai_web_explorer/grounded_web/action_intent.py tests/safesym_bridge/test_grounded_action_intent.py
git commit -m "feat: add grounded action intent models"
```

---

### Task 2: Add Async Action Loop Orchestration

**Files:**
- Create: `src/ai_web_explorer/grounded_web/action_loop.py`
- Test: `tests/safesym_bridge/test_grounded_action_loop.py`

**Interfaces:**
- Consumes:
  - `AutomationBackend.observe_state()`
  - `AutomationBackend.list_interactables(state)`
  - `AutomationBackend.execute(action)`
  - `ActionIntent`
  - `resolve_action_intent()`
  - `evaluate_outcome()`
- Produces:
  - `execute_action_intent(adapter: AutomationBackend, intent: ActionIntent, *, before: StateSnapshot | None = None, available_actions: list[BrowserAction | dict[str, Any]] | None = None) -> ActionExecutionResult`

- [ ] **Step 1: Write failing async loop tests**

Create `tests/safesym_bridge/test_grounded_action_loop.py`:

```python
import pytest

from ai_web_explorer.grounded_web.action_intent import (
    ActionExpectation,
    ActionIntent,
)
from ai_web_explorer.grounded_web.action_loop import execute_action_intent
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.state_facts import AbstractStateFact
from ai_web_explorer.grounded_web.structure import StructureEvidence


@pytest.fixture
def anyio_backend():
    return "asyncio"


class LoopFakeAdapter:
    app_name = "fake"

    def __init__(self, *, fail_error: str | None = None, no_change: bool = False):
        self.executed = []
        self.last_execution_error = None
        self.fail_error = fail_error
        self.no_change = no_change
        self.fact_sets = [
            [
                AbstractStateFact(
                    fact_id="result_count",
                    fact_type="numeric",
                    value=0,
                    identity_role="identity",
                    source_ref="result-count",
                    evidence=[
                        StructureEvidence(
                            source="dom_indicator",
                            selector="#result-count",
                        )
                    ],
                )
            ],
            [
                AbstractStateFact(
                    fact_id="result_count",
                    fact_type="numeric",
                    value=3,
                    identity_role="identity",
                    source_ref="result-count",
                    evidence=[
                        StructureEvidence(
                            source="dom_indicator",
                            selector="#result-count",
                        )
                    ],
                )
            ],
        ]

    async def observe_state(self):
        index = min(len(self.executed), 1)
        if self.no_change:
            index = 0
        self.last_state_facts = self.fact_sets[index]
        return StateSnapshot(
            page_id="search",
            url="https://example.test/search",
            title="Search",
            signature={"result_count": self.fact_sets[index][0].value},
        )

    async def list_interactables(self, state):
        return [
            {
                "semantic_id": "submit_search",
                "description": "Search",
                "locator": "#submit",
                "action_kind": "click",
                "input_values": {},
            }
        ]

    async def execute(self, action: BrowserAction):
        self.executed.append(action)
        if self.fail_error is not None:
            self.last_execution_error = self.fail_error
            return False
        return True


@pytest.mark.anyio
async def test_execute_action_intent_returns_typed_delta_and_success():
    adapter = LoopFakeAdapter()
    result = await execute_action_intent(
        adapter,
        ActionIntent(
            action_kind="click",
            target_semantic_id="submit_search",
            expectation=ActionExpectation(
                kind="field_changed",
                field="result_count",
            ),
        ),
    )

    assert result.execution_success is True
    assert result.action is not None
    assert result.action.semantic_id == "submit_search"
    assert result.observed_delta[0].field == "result_count"
    assert result.observed_delta[0].delta_type == "numeric_changed"
    assert result.outcome.status == "succeeded"


@pytest.mark.anyio
async def test_execute_action_intent_reports_missing_target():
    adapter = LoopFakeAdapter()
    result = await execute_action_intent(
        adapter,
        ActionIntent(action_kind="click", target_semantic_id="missing"),
    )

    assert result.execution_success is False
    assert result.execution_error == "intent_target_not_found"
    assert result.action is None
    assert result.after is None
    assert result.outcome.status == "failed_execution"


@pytest.mark.anyio
async def test_execute_action_intent_reports_backend_failure():
    adapter = LoopFakeAdapter(fail_error="locator_disabled")
    result = await execute_action_intent(
        adapter,
        ActionIntent(action_kind="click", target_semantic_id="submit_search"),
    )

    assert result.execution_success is False
    assert result.execution_error == "locator_disabled"
    assert result.outcome.status == "failed_execution"


@pytest.mark.anyio
async def test_execute_action_intent_reports_no_observed_change():
    adapter = LoopFakeAdapter(no_change=True)
    result = await execute_action_intent(
        adapter,
        ActionIntent(action_kind="click", target_semantic_id="submit_search"),
    )

    assert result.execution_success is True
    assert result.observed_delta == []
    assert result.outcome.status == "no_observed_change"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_grounded_action_loop.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'ai_web_explorer.grounded_web.action_loop'`.

- [ ] **Step 3: Implement action loop orchestration**

Create `src/ai_web_explorer/grounded_web/action_loop.py`:

```python
from __future__ import annotations

from typing import Any

from ai_web_explorer.grounded_web.action_intent import (
    ActionExecutionResult,
    ActionIntent,
    OutcomeEvaluation,
    evaluate_outcome,
    resolve_action_intent,
)
from ai_web_explorer.grounded_web.automation_backend import AutomationBackend
from ai_web_explorer.grounded_web.capability_graph import Evidence, ObservedDelta
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.state_signature import schema_delta
from ai_web_explorer.grounded_web.typed_delta import (
    observed_deltas_from_typed,
    typed_deltas_from_facts,
)


def _schema_observed_delta(
    before: dict[str, Any],
    after: dict[str, Any],
    url: str,
) -> list[ObservedDelta]:
    evidence = [Evidence(source="grounded_action_loop_schema_diff", url=url)]
    deltas: list[ObservedDelta] = []
    for key, value in (schema_delta(before, after) or {}).items():
        deltas.append(
            ObservedDelta(
                field=key,
                before=value["before"],
                after=value["after"],
                delta_type="state_indicator_change",
                evidence=evidence,
            )
        )
    return deltas


def observed_delta_from_adapter(
    adapter: AutomationBackend,
    *,
    before_facts,
    after_facts,
    before_signature: dict[str, Any],
    after_signature: dict[str, Any],
    url: str,
) -> list[ObservedDelta]:
    if before_facts is not None and after_facts is not None:
        typed = typed_deltas_from_facts(before_facts, after_facts)
        return observed_deltas_from_typed(typed, url=url)
    return _schema_observed_delta(before_signature, after_signature, url)


def failed_action_result(
    *,
    intent: ActionIntent,
    before: StateSnapshot,
    action: BrowserAction | None,
    error: str,
) -> ActionExecutionResult:
    outcome = OutcomeEvaluation(
        status="failed_execution",
        reason=error,
        matched_expectation=False,
    )
    return ActionExecutionResult(
        intent=intent,
        action=action,
        before=before,
        after=None,
        observed_delta=[],
        execution_success=False,
        execution_error=error,
        outcome=outcome,
    )


async def execute_action_intent(
    adapter: AutomationBackend,
    intent: ActionIntent,
    *,
    before: StateSnapshot | None = None,
    available_actions: list[BrowserAction | dict[str, Any]] | None = None,
) -> ActionExecutionResult:
    before_state = before if before is not None else await adapter.observe_state()
    before_facts = getattr(adapter, "last_state_facts", None)
    actions = (
        available_actions
        if available_actions is not None
        else await adapter.list_interactables(before_state)
    )
    action = resolve_action_intent(intent, actions)
    if action is None:
        return failed_action_result(
            intent=intent,
            before=before_state,
            action=None,
            error="intent_target_not_found",
        )

    success = await adapter.execute(action)
    execution_error = getattr(adapter, "last_execution_error", None)
    after_state = await adapter.observe_state()
    after_facts = getattr(adapter, "last_state_facts", None)
    deltas = observed_delta_from_adapter(
        adapter,
        before_facts=before_facts,
        after_facts=after_facts,
        before_signature=before_state.signature,
        after_signature=after_state.signature,
        url=after_state.url,
    )
    outcome = evaluate_outcome(
        execution_success=success,
        execution_error=execution_error,
        deltas=deltas,
        expectation=intent.expectation,
    )
    return ActionExecutionResult(
        intent=intent,
        action=action,
        before=before_state,
        after=after_state,
        observed_delta=deltas,
        execution_success=success,
        execution_error=execution_error,
        outcome=outcome,
    )
```

- [ ] **Step 4: Run loop tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_grounded_action_loop.py -q
```

Expected: all tests in `test_grounded_action_loop.py` pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/ai_web_explorer/grounded_web/action_loop.py tests/safesym_bridge/test_grounded_action_loop.py
git commit -m "feat: add grounded action execution loop"
```

---

### Task 3: Route WebKobeExplorer Through the Action Loop

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Modify: `tests/safesym_bridge/test_web_kobe_explorer.py`

**Interfaces:**
- Consumes:
  - `ActionIntent`
  - `execute_action_intent()`
- Produces:
  - `WebKobeExplorer.explore_one_step()` records graph edges using `ActionExecutionResult`.

- [ ] **Step 1: Add explorer regression test for no observed change status**

Append this test to `tests/safesym_bridge/test_web_kobe_explorer.py`:

```python
class NoChangeAdapter(FakeAdapter):
    async def observe_state(self):
        return StateSnapshot(
            page_id="listing",
            url="https://example.test/listing",
            title="Listing",
            signature={"cart_nonempty": False},
        )


@pytest.mark.anyio
async def test_explore_one_step_marks_success_without_delta_as_no_observed_change():
    explorer = WebKobeExplorer(
        adapter=NoChangeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    assert edge.status == "no_observed_change"
    assert edge.execution_trace.success is True
    assert edge.observed_delta == []
```

- [ ] **Step 2: Run focused explorer tests to verify failure**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_explorer.py -q
```

Expected: the new test fails because explorer still marks a successful no-delta execution as `verified`.

- [ ] **Step 3: Modify explorer imports**

In `src/ai_web_explorer/grounded_web/explorer.py`, replace direct typed-delta helper imports with action-loop imports.

Expected import block additions:

```python
from ai_web_explorer.grounded_web.action_intent import ActionIntent
from ai_web_explorer.grounded_web.action_loop import execute_action_intent
```

Remove the now-unused imports:

```python
from ai_web_explorer.grounded_web.state_signature import schema_delta
from ai_web_explorer.grounded_web.typed_delta import (
    observed_deltas_from_typed,
    typed_deltas_from_facts,
)
```

Keep `schema_delta` only if the implementation still uses it for `edge.schema_delta`.

- [ ] **Step 4: Replace direct adapter execution**

Inside `WebKobeExplorer.explore_one_step()`, replace:

```python
success = await self.adapter.execute(selected)
after = await self.adapter.observe_state()
```

with:

```python
result = await execute_action_intent(
    self.adapter,
    ActionIntent(
        action_kind=selected.action_kind,
        target_semantic_id=selected.semantic_id,
        target_description=selected.description,
        input_values=dict(selected.input_values),
        expectation=None,
        source="rule_based",
    ),
    before=before,
    available_actions=source_interactables,
)
after = result.after or before
```

Then update edge construction to use:

```python
action=result.action or selected
observed_delta=result.observed_delta
status=result.outcome.status
```

And update `ExecutionTrace` fields:

```python
concrete_action_kind=(result.action or selected).action_kind
concrete_locator=(result.action or selected).locator
concrete_target_sample=(result.action or selected).semantic_id
input_values_used=dict((result.action or selected).input_values)
success=result.execution_success
error=result.execution_error
```

Keep `schema_delta` computed from `before_draft.last_state_snapshot` and `after_draft.last_state_snapshot` so downstream graph output remains backward-compatible.

- [ ] **Step 5: Remove obsolete private delta helpers from explorer**

Delete `_observed_delta()` and `_observed_delta_from_adapter()` from `src/ai_web_explorer/grounded_web/explorer.py` if no call sites remain.

- [ ] **Step 6: Run focused explorer tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_explorer.py -q
```

Expected: all tests in `test_web_kobe_explorer.py` pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add src/ai_web_explorer/grounded_web/explorer.py tests/safesym_bridge/test_web_kobe_explorer.py
git commit -m "feat: route explorer through action loop"
```

---

### Task 4: Add Playwright Fixture Coverage for the Action Loop

**Files:**
- Modify: `tests/safesym_bridge/test_observation_to_state_form_search.py`

**Interfaces:**
- Consumes:
  - `WebKobePlaywrightAdapter`
  - `ActionIntent`
  - `ActionExpectation`
  - `execute_action_intent()`
- Produces:
  - Browser-backed proof that action loop can operate a real fixture and record typed deltas.

- [ ] **Step 1: Add imports**

Modify imports in `tests/safesym_bridge/test_observation_to_state_form_search.py`:

```python
from ai_web_explorer.grounded_web.action_intent import (
    ActionExpectation,
    ActionIntent,
)
from ai_web_explorer.grounded_web.action_loop import execute_action_intent
```

- [ ] **Step 2: Add Playwright-backed action-loop test**

Append:

```python
@pytest.mark.anyio
async def test_action_loop_operates_form_search_and_records_expected_delta():
    from playwright.async_api import async_playwright

    fixture_url = Path("tests/fixtures/local_form_search/index.html").resolve().as_uri()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(fixture_url)
            adapter = WebKobePlaywrightAdapter(
                page,
                app_name="local_form_search",
                page_id="local_form_search",
            )

            result = await execute_action_intent(
                adapter,
                ActionIntent(
                    action_kind="fill_then_click",
                    target_description="search",
                    input_values={
                        "#query": "kobe",
                    },
                    expectation=ActionExpectation(
                        kind="field_changed",
                        field="result_count",
                    ),
                    source="rule_based",
                ),
            )

            fields = {delta.field for delta in result.observed_delta}
            assert result.execution_success is True
            assert result.outcome.status == "succeeded"
            assert "result_count" in fields
            assert "result_row_count" in fields
        finally:
            await browser.close()
```

- [ ] **Step 3: Run fixture test**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_observation_to_state_form_search.py -q
```

Expected: all tests in `test_observation_to_state_form_search.py` pass.

- [ ] **Step 4: Commit**

Run:

```powershell
git add tests/safesym_bridge/test_observation_to_state_form_search.py
git commit -m "test: cover action loop on form search fixture"
```

---

### Task 5: Update Current Project Overview Documents

**Files:**
- Modify: `docs/current-project-overview.md`
- Modify: `docs/current-project-overview.zh-CN.md`

**Interfaces:**
- Consumes:
  - Implemented action loop modules and tests.
- Produces:
  - Updated project map for future sessions.

- [ ] **Step 1: Update English overview**

In `docs/current-project-overview.md`, update the active generic mainline section to include:

```text
active generic mainline:
  DOM-grounded Web-KOBE exploration
  -> page structure observation
  -> state facts and typed deltas
  -> ActionIntent / ActionExecutionResult / OutcomeEvaluation
  -> WebKobeExplorer
  -> WebKobeGraph
  -> later SafeSym/PDDL projection
```

Add a short paragraph:

```markdown
The grounded action loop is the current pre-LLM control boundary. It records
what the upper layer intended to do, which concrete `BrowserAction` was
selected, whether Playwright execution succeeded, which typed state deltas were
observed, and whether the outcome matched the expectation. Future LLM planners
should produce `ActionIntent` objects; they should not directly produce raw
selectors or own browser execution.
```

- [ ] **Step 2: Update Chinese overview in UTF-8**

Use the English flow below as the source of truth for the Chinese overview update. If the existing Chinese file displays incorrectly in PowerShell, inspect it with a UTF-8-aware editor before changing it.

```text
ActionIntent
-> BrowserAction
-> Playwright execution
-> before/after state
-> typed delta
-> OutcomeEvaluation
-> ActionExecutionResult
```

Open `docs/current-project-overview.zh-CN.md` with UTF-8 handling and add the same concept in Chinese near the current pipeline section:

```markdown
当前 `grounded_web` 新增了动作闭环边界：

```text
ActionIntent
-> BrowserAction
-> Playwright 执行
-> before/after state
-> typed delta
-> OutcomeEvaluation
-> ActionExecutionResult
```

这个边界是正式接入 LLM 前的关键工程层。未来 LLM 应该输出
`ActionIntent`，由 `grounded_web` 负责解析、执行、观察和评估结果；LLM
不应该直接生成 selector，也不应该拥有浏览器执行细节。
```
```

When editing this file, verify the file renders as Chinese text before committing.

- [ ] **Step 3: Run documentation status check**

Run:

```powershell
git diff -- docs/current-project-overview.md docs/current-project-overview.zh-CN.md
```

Expected: diff only contains overview updates for the action loop stage.

- [ ] **Step 4: Commit**

Run:

```powershell
git add docs/current-project-overview.md docs/current-project-overview.zh-CN.md
git commit -m "docs: update project overview for action loop"
```

---

### Task 6: Full Verification and Branch Finishing

**Files:**
- No new source files.
- Uses all files touched in Tasks 1-5.

**Interfaces:**
- Consumes:
  - Completed source, tests, and overview docs.
- Produces:
  - Verified branch ready for local merge or PR.

- [ ] **Step 1: Run focused action-loop tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_grounded_action_intent.py tests/safesym_bridge/test_grounded_action_loop.py -q
```

Expected: all focused action-loop tests pass.

- [ ] **Step 2: Run explorer and fixture regression tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_observation_to_state_form_search.py -q
```

Expected: all selected regression tests pass.

- [ ] **Step 3: Run full safesym_bridge suite**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge -q
```

Expected: the full `tests/safesym_bridge` suite passes.

- [ ] **Step 4: Check grounded_web does not import safesym_bridge**

Run:

```powershell
rg "safesym_bridge" src/ai_web_explorer/grounded_web
```

Expected: no runtime imports from `grounded_web` to `safesym_bridge`. Documentation comments are acceptable if they do not create imports.

- [ ] **Step 5: Check worktree status**

Run:

```powershell
git status --short --branch
```

Expected: clean branch with all implementation commits present.

- [ ] **Step 6: Use finishing workflow**

Use `superpowers:finishing-a-development-branch` and present the normal completion choice to the user. Because the user prefers single-agent execution, do not dispatch a review subagent unless the user explicitly asks for one.
