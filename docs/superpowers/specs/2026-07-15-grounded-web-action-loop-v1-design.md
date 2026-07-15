# Grounded Web Action Loop v1 Design

## Goal

Build the first explicit action loop inside `grounded_web`: convert an intended web action into a concrete browser action, execute it through the existing Playwright adapter, observe the before/after state, derive typed deltas, and classify the outcome.

This is the last infrastructure layer before an LLM planner can be added safely. The LLM should eventually produce action intents and expectations; it should not directly manipulate Playwright selectors or own browser execution details.

## Background

The current mainline already has the important lower-level pieces:

- `action_extractor.py` and `action_ranker.py` discover and rank browser actions.
- `playwright_backend.py` executes `BrowserAction` instances and exposes state observations.
- `structure.py` extracts generic page structure from Playwright pages.
- `state_facts.py` derives typed state facts from structure observations.
- `typed_delta.py` compares before/after facts and produces typed state deltas.
- `explorer.py` records graph edges with execution traces and observed deltas.

The missing layer is a durable protocol for the operation itself. Today `execute()` mostly answers "did Playwright perform the action?" A web agent also needs to know what it meant to do, what concrete target was selected, what changed afterward, and whether that change matched the expected outcome.

## Non-goals

This version will not:

- call a real LLM API;
- design prompts;
- add multi-step planning;
- allow LLMs to generate raw CSS or XPath selectors;
- move DOM or Playwright responsibility into `safesym_bridge`;
- introduce app-specific assumptions such as shopping carts, checkout flows, or search result semantics beyond test fixtures.

## Architecture

The action loop is intentionally narrow:

```text
StateSnapshot + available BrowserAction records
        |
        v
ActionIntent
        |
        v
resolve intent to BrowserAction
        |
        v
execute through AutomationBackend
        |
        v
observe after-state
        |
        v
derive ObservedDelta
        |
        v
OutcomeEvaluation
        |
        v
ActionExecutionResult
```

`grounded_web` remains responsible for browser grounding, action execution, state observation, and outcome classification. `safesym_bridge` remains a higher-level bridge to symbolic task representations and should consume grounded results instead of controlling DOM details.

## Data model

### ActionExpectation

Represents the expected observable effect of an action. V1 should support simple, testable expectations:

- `any_state_change`: any typed delta is acceptable;
- `field_changed`: a named state field should change;
- `field_equals`: a named state field should equal an expected value after execution.

The expectation model should use state fact identifiers and state signature keys, not DOM selectors.

### ActionIntent

Represents an upper-layer decision before it is grounded to a concrete browser action.

Fields:

- `action_kind`: expected action type such as `click`, `fill`, `fill_then_click`, or `select`;
- `target_semantic_id`: preferred semantic target id when known;
- `target_description`: human-readable target description used as a fallback match hint;
- `input_values`: values to use for fill/select actions;
- `expectation`: optional `ActionExpectation`;
- `source`: origin of the intent, initially `rule_based`; the future LLM adapter will use `llm`.

The important design rule is that `ActionIntent` must not require a raw locator. Locators belong to discovered `BrowserAction` records and Playwright execution, not to the planner interface.

### OutcomeEvaluation

Classifies the observed result.

Statuses:

- `succeeded`: execution succeeded and the expectation matched;
- `succeeded_with_observed_change`: execution succeeded, no expectation was provided, and at least one state delta was observed;
- `failed_execution`: execution did not succeed at the browser/action layer;
- `no_observed_change`: execution reported success but no typed or schema-level state change was observed;
- `unexpected_change`: execution succeeded and state changed, but the expectation did not match.

The evaluator should include a short reason string suitable for logs and future LLM feedback.

### ActionExecutionResult

Carries the complete one-step record:

- original `ActionIntent`;
- resolved `BrowserAction`, or `None` when resolution failed;
- `StateSnapshot` before execution;
- `StateSnapshot` after execution when available;
- observed deltas;
- execution success flag;
- execution error string;
- `OutcomeEvaluation`.

This object is the future handoff point to graph recording, LLM reflection, and symbolic projection.

## Resolution behavior

V1 resolution should be deterministic and conservative:

1. Prefer an available action whose `semantic_id` equals `target_semantic_id` and whose `action_kind` matches.
2. If no semantic id match exists, allow a case-insensitive description match against `target_description`.
3. If there are multiple description matches, select the first action in the already-ranked available action list.
4. If no action matches, return an execution result with `failed_execution` and error `intent_target_not_found`.

This keeps the planner interface stable without introducing fuzzy LLM-like matching in the resolver.

## Execution behavior

The loop should work with the existing `AutomationBackend` interface:

1. observe the before-state;
2. list interactables for the before-state;
3. resolve `ActionIntent` to a `BrowserAction`;
4. execute the resolved action;
5. observe the after-state;
6. collect before/after facts from the adapter when available;
7. derive typed observed deltas when facts are available;
8. fall back to schema-level deltas when typed facts are unavailable;
9. evaluate the outcome;
10. return `ActionExecutionResult`.

No Playwright-specific calls should be added to the action loop. Browser-specific mechanics stay behind `AutomationBackend`.

## Explorer integration

`WebKobeExplorer.explore_one_step()` should keep its public behavior but route the selected action through the action loop. The graph edge should continue to contain:

- selected `BrowserAction`;
- observed deltas;
- schema delta;
- execution trace;
- status.

The edge status should come from `OutcomeEvaluation.status` where possible. Existing graph output should remain backward-compatible for tests and downstream consumers.

## Error handling

Resolution failure, unsupported action kinds, missing locators, invisible elements, disabled elements, and Playwright exceptions must be represented as `failed_execution` outcomes with explicit error strings.

Successful browser execution without observable state change should not be treated as a verified success. It should become `no_observed_change`, because this is critical feedback for future planners and LLMs.

`page_settle_timeout` may still be a non-fatal adapter warning when execution otherwise succeeded, but it should be preserved in the result error or metadata so it is not silently lost.

## Testing strategy

Tests should exercise the action loop without relying on app-specific domains:

1. successful intent resolves by semantic id and produces an observed delta on the existing local form/search fixture;
2. intent resolves by description when semantic id is absent;
3. missing target returns `failed_execution` with `intent_target_not_found`;
4. successful execution with no observable state delta returns `no_observed_change`;
5. expectation `field_changed` matches a typed delta;
6. expectation mismatch returns `unexpected_change`;
7. `WebKobeExplorer` still produces graph edges with execution traces and observed deltas.

The primary verification command remains:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge -q
```

When running from `main` without a local virtual environment, using any already-created project virtual environment is acceptable only as a temporary local convenience. The implementation itself must not depend on a worktree path.

## Long-term fit

This design prepares for LLM integration by making the LLM boundary explicit:

```text
LLM planner:
  goal + page state + available actions -> ActionIntent

grounded_web:
  ActionIntent -> concrete BrowserAction -> execution -> deltas -> outcome

safesym_bridge:
  grounded outcomes -> symbolic/task-level reasoning
```

The first LLM adapter should therefore plug into intent production, not into browser execution. This keeps the browser automation layer testable, replayable, and replaceable.

## Acceptance criteria

- A new action loop module can execute one `ActionIntent` end-to-end.
- The loop returns a complete `ActionExecutionResult`.
- The loop derives typed deltas when adapter facts are available.
- Execution success without observed state change is classified separately from verified success.
- `WebKobeExplorer` uses the action loop without breaking existing graph behavior.
- Existing `tests/safesym_bridge` pass.
