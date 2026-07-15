# Grounded Web Outcome Wait Policy v1 Design

## Goal

Make `no_observed_change` more reliable by adding bounded post-action observation polling to `grounded_web`'s action loop.

Today `execute_action_intent()` executes a resolved `BrowserAction`, observes once, derives deltas, and immediately classifies the outcome. That is too eager for modern web pages where DOM updates, route changes, and state indicators may appear shortly after the Playwright action returns.

## Design Decision

V1 adds waiting, not automatic retry.

```text
execute action
-> observe immediately
-> derive delta
-> if delta exists: evaluate normally
-> if no delta:
     poll observe for a bounded time window
     stop early when a delta appears
-> if still no delta:
     keep outcome as no_observed_change
```

Waiting is a low-risk observation strategy. Retry is a higher-risk execution strategy because many web actions have side effects such as add-to-cart, submit, delete, checkout, payment, or confirmation. Automatic retry should be a later policy that requires explicit idempotency or safety classification.

## Non-goals

This version will not:

- retry browser actions;
- classify action idempotency;
- call an LLM;
- add planner-level recovery;
- change Playwright locator execution semantics;
- treat `no_observed_change` as success;
- add sleeps to the controller or explorer layers.

## Policy Model

Add a small policy object inside `grounded_web`, likely in `action_loop.py` or a focused helper module:

```python
@dataclass(frozen=True)
class ObservationWaitPolicy:
    timeout_ms: int = 1200
    interval_ms: int = 200
```

Default values should be conservative:

- `timeout_ms=1200`
- `interval_ms=200`

The policy should be passed to `execute_action_intent()` as an optional keyword:

```python
async def execute_action_intent(
    adapter: AutomationBackend,
    intent: ActionIntent,
    *,
    before: StateSnapshot | None = None,
    available_actions: list[BrowserAction | dict[str, Any]] | None = None,
    wait_policy: ObservationWaitPolicy | None = None,
) -> ActionExecutionResult:
    ...
```

When `wait_policy` is `None`, use the default policy. Tests may pass shorter policies to keep the suite fast.

## Polling Behavior

After browser execution succeeds or fails, the loop should still observe the after-state once so diagnostics remain complete. Then:

1. derive deltas from before/after observations;
2. if deltas exist, evaluate immediately;
3. if execution failed, evaluate immediately as `failed_execution`;
4. if execution succeeded and no deltas exist, keep observing until either:
   - a delta appears, or
   - `timeout_ms` expires.

Each poll should:

- wait approximately `interval_ms`;
- call `adapter.observe_state()`;
- read `adapter.last_state_facts` when available;
- derive typed deltas if facts exist;
- fall back to schema deltas otherwise.

The returned `ActionExecutionResult.after` should be the final observed state, not necessarily the first after-state.

## Adapter Boundary

The action loop should not call Playwright APIs directly. Waiting should use adapter-neutral mechanisms only:

- call `adapter.observe_state()`;
- optionally use `asyncio.sleep()` between polls.

`WebKobePlaywrightAdapter._settle_page()` may stay as the browser-level actionability/settling helper. The new wait policy lives above it and checks whether the project-level state abstraction changed.

## Outcome Semantics

The policy should not introduce a new success status.

If a delta appears during polling:

- `evaluate_outcome()` receives that delta list;
- current statuses such as `succeeded`, `succeeded_with_observed_change`, or `unexpected_change` apply.

If no delta appears before timeout:

- current `no_observed_change` behavior remains;
- the reason should make clear that a bounded wait completed, for example:

```text
execution succeeded but no state delta was observed after 1200ms
```

If an expectation exists and no delta appears:

- `matched_expectation=False`;
- status remains `no_observed_change`.

## Diagnostics

V1 should expose enough diagnostic information for tests and later LLM feedback without overbuilding a trace model.

The simplest acceptable approach is to include the wait timeout in `OutcomeEvaluation.reason`. If implementation naturally adds metadata later, it should include:

- number of observation attempts;
- wait timeout;
- interval;
- final observed URL.

Metadata is not required for v1.

## Testing Strategy

Add fake-adapter tests that avoid real sleeps by passing a small policy:

1. first after-observation has no delta, a later poll has a delta, outcome becomes success;
2. no delta appears before timeout, outcome remains `no_observed_change`;
3. execution failure does not poll unnecessarily and remains `failed_execution`;
4. final `ActionExecutionResult.after` is the state that produced the delta or the final timeout observation.

Add one browser-backed regression only if existing fixtures can do it without making the suite slow. The fake-adapter tests are sufficient for v1 because the browser behavior is already covered by action-loop fixture tests.

## Long-term Fit

This policy gives future LLM planners better evidence. A `no_observed_change` result will mean:

```text
The action executed successfully, and the system waited for a bounded period,
but the page abstraction still did not change.
```

That is much more useful than the current meaning:

```text
The action executed successfully, and the first immediate observation did not change.
```

Retry should be designed later as a separate execution policy with explicit safety/idempotency rules.

## Acceptance Criteria

- `execute_action_intent()` supports a configurable observation wait policy.
- No browser action is retried by default.
- The loop polls after a successful no-delta execution and stops early when a delta appears.
- `no_observed_change` is only returned after the wait window expires without deltas.
- Existing action-loop outcomes remain backward-compatible.
- Existing `tests/safesym_bridge` pass.
