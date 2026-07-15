# Grounded Web Outcome Wait Policy v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not use subagents unless the user explicitly permits multi-agent work.

**Goal:** Add bounded post-action observation polling so `no_observed_change` is only returned after a short wait window, without retrying browser actions.

**Architecture:** Keep the policy inside `grounded_web.action_loop`. Add `ObservationWaitPolicy`, derive deltas immediately after execution, and only poll when execution succeeded but no delta was observed. Reuse existing typed-delta and schema-delta helpers so Explorer/Controller behavior remains unchanged.

**Tech Stack:** Python dataclasses, `asyncio.sleep`, async `AutomationBackend`, pytest/anyio, existing `ActionExecutionResult`, `OutcomeEvaluation`, `ObservedDelta`, `StateSnapshot`, and `typed_delta.py`.

## Global Constraints

- Do not retry browser actions.
- Do not classify action idempotency.
- Do not call an LLM.
- Do not add planner-level recovery.
- Do not change Playwright locator execution semantics.
- Do not treat `no_observed_change` as success.
- Do not add sleeps to the controller or explorer layers.
- Keep `grounded_web` independent from `safesym_bridge` imports.
- Keep `current-project-overview.md` and `current-project-overview.zh-CN.md` updated when the stage changes the main pipeline.

---

## File Structure

- Modify `src/ai_web_explorer/grounded_web/action_loop.py`
  - Add `ObservationWaitPolicy`.
  - Add internal async polling helper.
  - Add optional `wait_policy` argument to `execute_action_intent()`.
  - Keep all Playwright-specific waiting out of this module.
- Modify `tests/safesym_bridge/test_grounded_action_loop.py`
  - Add fake adapter coverage for delayed deltas, timeout no-change, failed execution no-poll, and final-after-state behavior.
- Modify `docs/current-project-overview.md`
  - Mention bounded post-action observation wait in the action-loop section.
- Modify `docs/current-project-overview.zh-CN.md`
  - Mirror the same update in Chinese, preserving UTF-8.

---

### Task 1: Add Wait Policy and Polling Tests

**Files:**
- Modify: `tests/safesym_bridge/test_grounded_action_loop.py`

**Interfaces:**
- Consumes:
  - `execute_action_intent(adapter, intent, *, wait_policy=...)`
  - `ObservationWaitPolicy(timeout_ms: int = 1200, interval_ms: int = 200)`
- Produces:
  - Tests proving delayed deltas are observed without retrying actions.

- [ ] **Step 1: Add imports for wait policy**

Modify the action-loop import:

```python
from ai_web_explorer.grounded_web.action_loop import (
    ObservationWaitPolicy,
    execute_action_intent,
)
```

- [ ] **Step 2: Add delayed-observation fake adapter**

Append this helper class after `LoopFakeAdapter`:

```python
class DelayedDeltaAdapter(LoopFakeAdapter):
    def __init__(self, *, delta_on_observation: int, fail_error: str | None = None):
        super().__init__(fail_error=fail_error)
        self.delta_on_observation = delta_on_observation
        self.observe_calls = 0

    async def observe_state(self):
        self.observe_calls += 1
        if self.observe_calls >= self.delta_on_observation:
            index = 1
        else:
            index = 0
        self.last_state_facts = self.fact_sets[index]
        return StateSnapshot(
            page_id="search",
            url=f"https://example.test/search?observe={self.observe_calls}",
            title="Search",
            signature={"result_count": self.fact_sets[index][0].value},
        )
```

- [ ] **Step 3: Add test for delayed delta during polling**

Append:

```python
@pytest.mark.anyio
async def test_execute_action_intent_waits_for_delayed_delta_without_retrying_action():
    adapter = DelayedDeltaAdapter(delta_on_observation=3)
    result = await execute_action_intent(
        adapter,
        ActionIntent(action_kind="click", target_semantic_id="submit_search"),
        wait_policy=ObservationWaitPolicy(timeout_ms=50, interval_ms=1),
    )

    assert len(adapter.executed) == 1
    assert adapter.observe_calls >= 3
    assert result.execution_success is True
    assert result.observed_delta[0].field == "result_count"
    assert result.outcome.status == "succeeded_with_observed_change"
    assert result.after is not None
    assert result.after.signature["result_count"] == 3
```

- [ ] **Step 4: Add test for timeout no-change reason**

Append:

```python
@pytest.mark.anyio
async def test_execute_action_intent_reports_no_change_after_wait_timeout():
    adapter = DelayedDeltaAdapter(delta_on_observation=100)
    result = await execute_action_intent(
        adapter,
        ActionIntent(action_kind="click", target_semantic_id="submit_search"),
        wait_policy=ObservationWaitPolicy(timeout_ms=5, interval_ms=1),
    )

    assert len(adapter.executed) == 1
    assert result.execution_success is True
    assert result.observed_delta == []
    assert result.outcome.status == "no_observed_change"
    assert "after 5ms" in result.outcome.reason
    assert result.after is not None
    assert result.after.url.startswith("https://example.test/search?observe=")
```

- [ ] **Step 5: Add test for execution failure no polling**

Append:

```python
@pytest.mark.anyio
async def test_execute_action_intent_does_not_poll_after_execution_failure():
    adapter = DelayedDeltaAdapter(
        delta_on_observation=3,
        fail_error="locator_disabled",
    )
    result = await execute_action_intent(
        adapter,
        ActionIntent(action_kind="click", target_semantic_id="submit_search"),
        wait_policy=ObservationWaitPolicy(timeout_ms=50, interval_ms=1),
    )

    assert len(adapter.executed) == 1
    assert adapter.observe_calls == 2
    assert result.execution_success is False
    assert result.outcome.status == "failed_execution"
    assert result.execution_error == "locator_disabled"
```

- [ ] **Step 6: Run tests to verify they fail**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_grounded_action_loop.py -q
```

Expected: collection fails with `ImportError` because `ObservationWaitPolicy` is not defined, or tests fail because `execute_action_intent()` does not accept `wait_policy`.

---

### Task 2: Implement Observation Wait Policy

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/action_loop.py`
- Test: `tests/safesym_bridge/test_grounded_action_loop.py`

**Interfaces:**
- Consumes:
  - `observed_delta_from_adapter(...) -> list[ObservedDelta]`
  - `evaluate_outcome(...) -> OutcomeEvaluation`
  - `AutomationBackend.observe_state()`
- Produces:
  - `ObservationWaitPolicy`
  - `execute_action_intent(..., wait_policy: ObservationWaitPolicy | None = None) -> ActionExecutionResult`

- [ ] **Step 1: Add imports and policy dataclass**

In `src/ai_web_explorer/grounded_web/action_loop.py`, add:

```python
import asyncio
from dataclasses import dataclass
```

Then add near the top of the file:

```python
@dataclass(frozen=True)
class ObservationWaitPolicy:
    timeout_ms: int = 1200
    interval_ms: int = 200
```

- [ ] **Step 2: Add a small delta bundle helper**

Add after `observed_delta_from_adapter()`:

```python
@dataclass(frozen=True)
class _ObservedStateDelta:
    state: StateSnapshot
    facts: Any
    deltas: list[ObservedDelta]
```

- [ ] **Step 3: Add helper to observe and derive deltas**

Add:

```python
async def _observe_state_delta(
    adapter: AutomationBackend,
    *,
    before_facts,
    before_signature: dict[str, Any],
) -> _ObservedStateDelta:
    state = await adapter.observe_state()
    facts = getattr(adapter, "last_state_facts", None)
    deltas = observed_delta_from_adapter(
        adapter,
        before_facts=before_facts,
        after_facts=facts,
        before_signature=before_signature,
        after_signature=state.signature,
        url=state.url,
    )
    return _ObservedStateDelta(state=state, facts=facts, deltas=deltas)
```

- [ ] **Step 4: Add bounded polling helper**

Add:

```python
async def _wait_for_observed_delta(
    adapter: AutomationBackend,
    *,
    before_facts,
    before_signature: dict[str, Any],
    initial: _ObservedStateDelta,
    policy: ObservationWaitPolicy,
) -> _ObservedStateDelta:
    if initial.deltas:
        return initial
    timeout_s = max(policy.timeout_ms, 0) / 1000
    interval_s = max(policy.interval_ms, 1) / 1000
    if timeout_s <= 0:
        return initial

    deadline = asyncio.get_running_loop().time() + timeout_s
    current = initial
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return current
        await asyncio.sleep(min(interval_s, remaining))
        current = await _observe_state_delta(
            adapter,
            before_facts=before_facts,
            before_signature=before_signature,
        )
        if current.deltas:
            return current
```

- [ ] **Step 5: Wire wait policy into execute_action_intent**

Change the function signature:

```python
async def execute_action_intent(
    adapter: AutomationBackend,
    intent: ActionIntent,
    *,
    before: StateSnapshot | None = None,
    available_actions: list[BrowserAction | dict[str, Any]] | None = None,
    wait_policy: ObservationWaitPolicy | None = None,
) -> ActionExecutionResult:
```

Replace the direct after-observation/delta block:

```python
after_state = await adapter.observe_state()
after_facts = getattr(adapter, "last_state_facts", None)
deltas = observed_delta_from_adapter(...)
```

with:

```python
policy = wait_policy or ObservationWaitPolicy()
observed = await _observe_state_delta(
    adapter,
    before_facts=before_facts,
    before_signature=before_state.signature,
)
if success and not observed.deltas:
    observed = await _wait_for_observed_delta(
        adapter,
        before_facts=before_facts,
        before_signature=before_state.signature,
        initial=observed,
        policy=policy,
    )
after_state = observed.state
deltas = observed.deltas
```

- [ ] **Step 6: Include timeout in no-change reason**

After `outcome = evaluate_outcome(...)`, add:

```python
if (
    success
    and not deltas
    and outcome.status == "no_observed_change"
):
    outcome = OutcomeEvaluation(
        status=outcome.status,
        reason=(
            "execution succeeded but no state delta was observed "
            f"after {policy.timeout_ms}ms"
        ),
        matched_expectation=outcome.matched_expectation,
    )
```

- [ ] **Step 7: Run action-loop tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_grounded_action_loop.py -q
```

Expected: all tests in `test_grounded_action_loop.py` pass.

- [ ] **Step 8: Commit**

Run:

```powershell
git add src/ai_web_explorer/grounded_web/action_loop.py tests/safesym_bridge/test_grounded_action_loop.py
git commit -m "feat: wait for observed action deltas"
```

---

### Task 3: Update Overview Docs

**Files:**
- Modify: `docs/current-project-overview.md`
- Modify: `docs/current-project-overview.zh-CN.md`

**Interfaces:**
- Consumes:
  - Implemented `ObservationWaitPolicy`.
- Produces:
  - Updated project map for future sessions.

- [ ] **Step 1: Update English overview**

In `docs/current-project-overview.md`, find the paragraph that begins:

```text
The grounded action loop is the current pre-LLM control boundary.
```

Extend it with:

```markdown
When an action executes successfully but produces no immediate delta, the loop
now waits for a bounded observation window and polls state before returning
`no_observed_change`. This is an observation policy, not an execution retry:
the browser action is not repeated by default.
```

- [ ] **Step 2: Update Chinese overview in UTF-8**

In `docs/current-project-overview.zh-CN.md`, find the Chinese action-loop paragraph near `ActionIntent -> BrowserAction`. Add the same meaning in Chinese:

```markdown
如果动作执行成功但第一次观察没有发现 delta，动作闭环会在有限时间窗口内继续轮询观察状态，然后才返回 `no_observed_change`。这是观察等待策略，不是动作重试；默认不会再次执行浏览器动作。
```

Use UTF-8-aware reading/writing. Verify the file still renders as Chinese text before committing.

- [ ] **Step 3: Check docs diff**

Run:

```powershell
git diff -- docs/current-project-overview.md docs/current-project-overview.zh-CN.md
```

Expected: diff only adds outcome wait policy wording.

- [ ] **Step 4: Commit**

Run:

```powershell
git add docs/current-project-overview.md docs/current-project-overview.zh-CN.md
git commit -m "docs: update overview for outcome wait policy"
```

---

### Task 4: Full Verification and Branch Finishing

**Files:**
- Uses all files touched in Tasks 1-3.

**Interfaces:**
- Consumes:
  - Implemented wait policy and docs updates.
- Produces:
  - Verified branch ready for local merge or PR.

- [ ] **Step 1: Run focused action-loop tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_grounded_action_loop.py -q
```

Expected: all action-loop tests pass.

- [ ] **Step 2: Run explorer/action-loop regressions**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_grounded_action_intent.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_observation_to_state_form_search.py -q
```

Expected: all selected regression tests pass.

- [ ] **Step 3: Run full safesym_bridge suite**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge -q
```

Expected: full `tests/safesym_bridge` passes.

- [ ] **Step 4: Check no grounded_web runtime dependency on safesym_bridge**

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

Expected: clean feature branch with all implementation commits present.

- [ ] **Step 6: Use finishing workflow**

Use `superpowers:finishing-a-development-branch` and present the normal completion choice to the user. Because the user prefers single-agent execution, do not dispatch a review subagent unless the user explicitly asks for one.
