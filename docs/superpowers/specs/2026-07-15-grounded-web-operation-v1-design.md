# Grounded Web Operation v1 Design

Date: 2026-07-15

## Purpose

The next stage strengthens `grounded_web` so the baseline agent can operate real
web pages and record state changes reliably. This stage should improve the
deterministic DOM-grounded operation loop before adding LLM/VLM intelligence.

The target loop is:

```text
observe page
-> extract DOM-grounded candidates
-> convert candidates into BrowserAction records
-> execute actions through AutomationBackend
-> wait for page stability
-> observe before/after state
-> record deltas and execution trace in WebKobeGraph
```

This is infrastructure work. It should make later LLM integration easier to
debug, not replace the verifiable browser/DOM facts with model guesses.

## Scope

In scope:

- Improve generic `grounded_web` operation behavior.
- Keep `AutomationBackend` as the browser-operation boundary.
- Keep exploration strategy in `WebKobeExplorer` / controller-level code.
- Add deterministic action ranking before LLM-based action selection.
- Improve default input/select values generated from DOM candidates.
- Improve execution stability and failure reporting.
- Validate first on the local `tests/fixtures/local_shop` smoke path.
- Preserve SauceDemo SafeSym regression compatibility.

Out of scope for this stage:

- Full unknown-site planning.
- Generic graph-to-PDDL generalization.
- Complex state recovery and backtracking.
- LLM/VLM as the primary browser controller.
- Letting an LLM invent selectors or decide observed fact truth.

## Architecture

### Automation backend

`src/ai_web_explorer/grounded_web/automation_backend.py` remains the stable
interface:

```text
observe_state()
list_interactables(state)
execute(action)
```

The Playwright implementation should become a more robust executor:

- resolve the locator;
- scroll the target into view;
- check basic actionability where possible;
- execute click, fill, select, or fill-then-click;
- wait for the page to settle;
- return enough information for precise trace/debugging.

The protocol currently returns `bool` from `execute`. The first implementation
can preserve this API and add private/internal error capture if needed. A later
step may introduce an explicit `ExecutionResult` if tests show the boolean is
too lossy.

### Action extraction

`action_extractor` should continue converting DOM candidates into
`BrowserAction` values. The default values should become slightly smarter while
remaining deterministic:

- email-like fields get a stable test email;
- password fields get a stable test password;
- username/search/text fields get meaningful stable values;
- number/quantity fields get a safe small numeric value;
- selects choose the first non-empty option.

This keeps the first version testable and avoids hidden model behavior.

### Action selection

The current first-unexplored policy should be replaced or wrapped with a small
deterministic ranker. The ranker should prefer actions that are more likely to
produce meaningful state transitions:

```text
explicit data-action/data-test button
-> button/link with clear name
-> select
-> input/textarea
-> weak CSS fallback
```

This is not intended to be the final intelligence layer. It is a baseline that
LLM action selection can later beat and be compared against.

### Graph recording

`WebKobeExplorer` already records before/after snapshots, schema deltas,
observed deltas, and execution traces. This stage should improve trace quality:

- distinguish execution failure from no available action;
- preserve the concrete locator and action kind;
- record whether the action produced an observed state delta;
- avoid treating every no-delta action as a hard failure.

No-delta can happen for legitimate UI operations, focus events, idempotent
buttons, or controls whose effects are outside the current observation schema.

## Data Flow

```text
WebKobeExplorationController
  -> WebKobeExplorer.explore_one_step()
    -> AutomationBackend.observe_state()
    -> AutomationBackend.list_interactables()
    -> deterministic action ranking
    -> AutomationBackend.execute()
    -> AutomationBackend.observe_state()
    -> schema_delta / observed_delta
    -> WebKobeGraph edge + execution_trace
```

`grounded_web` remains the mainline package. `safesym_bridge` may wrap or
consume this behavior for SauceDemo regression, but should not receive new
generic exploration ownership.

## Error Handling

The implementation should make failures explainable. The first set of failure
categories should include:

- no locator;
- locator not found;
- locator not visible/actionable;
- unsupported action kind;
- missing input/select value;
- Playwright execution error;
- page settle timeout.

If the public protocol remains boolean during the first pass, these categories
can be represented in tests through adapter internals or by a later explicit
result type. The important design requirement is that failures stop being an
opaque `False` at the graph/debugging layer.

## Testing

Validation should proceed from deterministic to browser-backed:

1. Unit tests for action extraction defaults.
2. Unit tests for action ranking.
3. Unit tests for Playwright adapter execution behavior using fakes.
4. Browser-backed local fixture smoke:

   ```bash
   python -m pytest tests/safesym_bridge/test_web_kobe_grounded_exploration.py
   ```

5. Existing bridge regression tests to ensure compatibility.
6. SauceDemo browser tests only when explicitly enabled by the existing
   environment gate.

The first success target is not "general web intelligence." It is a reliable
local fixture operation-and-recording loop that does not regress SauceDemo.

## LLM/VLM Integration Direction

LLM/VLM should be added after this deterministic layer is stable.

Allowed future responsibilities:

- choose among DOM-grounded candidates;
- name page states and capabilities;
- explain observed deltas;
- identify potentially sensitive actions;
- help decide whether two states are semantically similar.

Disallowed responsibilities:

- invent selectors;
- decide fact truth without browser evidence;
- silently mutate graph structure;
- replace Playwright/DOM observation;
- bypass SafeSym safety constraints.

The architectural rule is:

```text
browser/DOM observation = facts
LLM/VLM = semantic assistant
WebKobeGraph = recorded evidence and transitions
SafeSym/PDDL = planning and safety layer
```

## Implementation Sequence

1. Add tests for deterministic action value generation and ranking.
2. Improve `action_extractor` defaults.
3. Add or integrate a deterministic action ranker near `WebKobeExplorer`.
4. Improve `WebKobePlaywrightAdapter.execute()` actionability and waiting.
5. Improve execution trace/error detail without expanding module ownership.
6. Run local fixture smoke and bridge regressions.

## Review Notes

This design intentionally favors boring, observable engineering over early
agentic cleverness. That is the right trade-off for this project stage: once the
operation loop is reliable, LLM integration becomes a constrained decision
layer instead of an untestable source of truth.
