# Web-KOBE Collector Architecture Design

## Purpose

This document corrects the long-term architecture direction for the Web-KOBE
work in this repository.

The original `ai-web-explorer` already contains a general-purpose website
exploration engine. It can open a website, ask an LLM to understand the current
page, generate candidate actions, execute those actions with Playwright, merge
similar states, backtrack to under-explored states, and output a state machine.

The Web-KOBE / SafeSym work should not replace that exploration engine. It
should reuse it and collect richer planning-facing information during
exploration.

The corrected direction is:

```text
original ai-web-explorer ExploreLoop
  -> browser and LLM-driven exploration
  -> Web-KOBE Collector hooks
  -> WebKobeGraph / capability graph
  -> PDDL projection
  -> SafeSym
```

## Architectural Decision

The project should treat the original explorer as the exploration engine and
Web-KOBE as the knowledge representation and collection layer.

In other words:

```text
ExploreLoop answers:
  How do we continue exploring an unknown website?

WebKobeCollector answers:
  What planning-relevant information should we record while exploring?

WebKobeGraph answers:
  What can this website do, and what changes when those capabilities execute?
```

This prevents the project from maintaining two competing exploration loops.

## Existing Exploration Capabilities to Reuse

The original code already provides several capabilities that should be reused.

Relevant files:

```text
src/ai_web_explorer/loop.py
src/ai_web_explorer/describer.py
src/ai_web_explorer/executor.py
src/ai_web_explorer/webstate.py
src/ai_web_explorer/html.py
src/ai_web_explorer/cookies.py
```

Reusable behavior:

- Playwright browser startup and page navigation.
- LLM-generated page titles.
- Title embedding or title matching for state deduplication.
- LLM-generated page descriptions.
- LLM-generated candidate actions.
- LLM-guided Playwright action execution.
- Action retry and visual verification.
- State transitions.
- Search for the next state with available actions.
- Replay of known transitions to return to an under-explored state.
- JSON / DOT output for the discovered state machine.

These are expensive to rebuild and already match the broad web-agent workflow
needed for unknown websites.

## What the Existing Explorer Does Not Collect Well Enough

The existing `WebState` graph is useful, but it is not enough for SafeSym-style
planning.

Current `WebState` information:

```text
title
title_embedding
urls
description
actions
transitions
```

Current `Action` information:

```text
description
part
priority
status
function_calls
```

This is enough to replay and visualize exploration, but it is too weak for
planning because it does not explicitly model:

- stable semantic page types;
- planning-relevant state indicators;
- abstract action targets such as product, post, form, field, cart, or order;
- capability names such as `add_to_cart(product)` or `submit_login_form`;
- before/after state deltas;
- execution evidence;
- preconditions and effects;
- confidence and audit status;
- PDDL projection hints.

The Web-KOBE work should fill this gap.

## What to Keep from Previous Web-KOBE Work

The following pieces remain valuable:

- `WebKobeGraph`, `WebKobeNode`, `WebKobeEdge`, and related data structures.
- `WebKobeGraphManager`.
- Web-KOBE to PDDL projection experiments.
- SauceDemo as a controlled benchmark.
- Capability-first modeling: focus on what the page can do, not what content it
  contains.
- Representative entity modeling: product cards, posts, rows, and results
  should usually become abstract target types instead of many concrete graph
  entities.
- UI-KOBE-inspired ideas: semantic state nodes, action edges, schema deltas,
  state matching, and graph-guided runtime reuse.

These pieces describe the target knowledge representation.

## What to Demote or Stop Expanding

The following pieces should be treated as experiments or transition code, not
as the long-term main exploration path:

- `WebKobeExplorationController`.
- `WebKobePlaywrightAdapter` as an independent generic exploration adapter.
- `web-kobe-explore` as a separate exploration command that bypasses the
  original `ExploreLoop`.

They proved that a real browser action can produce a Web-KOBE edge, which was
useful. But continuing to grow them would duplicate the original explorer.

They may remain useful for deterministic unit tests, local fixtures, and
SauceDemo smoke tests, but the main unknown-site exploration path should move
toward collector hooks inside or alongside the original explorer.

## Proposed Component: WebKobeCollector

`WebKobeCollector` is a hook-based collection layer. It does not choose actions
and does not drive the browser. It observes the original explorer's process and
records richer graph data.

Conceptual interface:

```python
class WebKobeCollector:
    def on_state_observed(
        self,
        *,
        page,
        web_state,
        observation,
    ) -> None:
        ...

    def on_action_selected(
        self,
        *,
        source_state,
        action,
    ) -> None:
        ...

    def on_action_executed(
        self,
        *,
        action,
        success: bool,
        tool_calls: list,
        error: str | None,
    ) -> None:
        ...

    def on_transition(
        self,
        *,
        source_state,
        action,
        target_state,
        before_observation,
        after_observation,
    ) -> None:
        ...

    def to_web_kobe_graph(self) -> WebKobeGraph:
        ...
```

The exact function signatures can be refined during implementation, but the
separation should remain: the collector observes and records; the explorer
explores.

## Hook Points in the Original ExploreLoop

The smallest useful integration points are in `ExploreLoop._explore()`.

Current conceptual flow:

```text
1. get current WebState
2. if previous action succeeded, append StateTransition
3. select next action
4. execute action
5. mark action success/failure
```

Collector-enhanced flow:

```text
1. get current WebState
2. collector.on_state_observed(...)
3. if previous action succeeded:
     collector.on_transition(...)
     append StateTransition
4. select next action
5. collector.on_action_selected(...)
6. execute action
7. collector.on_action_executed(...)
8. next iteration observes the resulting state
```

The first implementation should avoid invasive rewrites. A `collector` optional
field can be added to `LoopConfig` or `ExploreLoop.__init__`, defaulting to a
no-op collector.

## Information to Collect

The collector should collect planning-facing information, not raw page dumps.

### Page and state information

- URL and normalized URL pattern.
- Browser title.
- Main heading when available.
- LLM title from the original explorer.
- Existing `WebState` ID.
- Semantic page type when known or inferred.
- State indicators that affect capabilities, transitions, goals, or execution
  verification.
- Evidence for each state indicator.

### Interactable and action information

- Original LLM action description.
- Action priority and part.
- Tool calls generated by the executor.
- Concrete selectors used by tool calls.
- Action kind: click, fill, select, composite, unknown.
- Abstract target type when inferable: product, post, result, form, field,
  cart, order, navigation item.
- Representative target pattern for repeated entities.
- Input values used, with secrets redacted where appropriate.

### Transition information

- Source semantic state.
- Target semantic state.
- Executed action.
- Success or failure.
- Before and after observations.
- Semantic delta between before and after.
- Evidence for the delta.
- Whether the transition is navigation, self-loop state change, form progress,
  failure, modal/overlay, or unknown.

## Data Flow

```text
ExploreLoop
  observes page and creates WebState
    -> WebKobeCollector records SemanticPageState draft

ExploreLoop
  selects Action
    -> WebKobeCollector records candidate capability draft

Executor
  generates and executes Playwright tool calls
    -> WebKobeCollector records concrete grounding and execution trace

ExploreLoop
  observes target WebState
    -> WebKobeCollector compares before/after observations
    -> WebKobeCollector adds WebKobeEdge / CapabilityTransition
```

The original `WebState` graph remains available. The Web-KOBE graph becomes a
richer sidecar built from the same exploration process.

## State and Capability Abstraction Rules

The collector should follow the project principle:

```text
Model what the website can do, not every content item it contains.
```

Examples:

```text
Many product cards
  -> one target_type = product
  -> capability = add_to_cart(product)

Many forum posts
  -> one target_type = post
  -> capability = open_post(post)

Many search results
  -> one target_type = result
  -> capability = open_result(result)
```

Concrete examples still matter for grounding and replay, but should be stored as
evidence or representative samples, not as long-lived graph nodes unless the
instance itself is planning-relevant.

## Relation to SauceDemo

SauceDemo remains the controlled validation target.

For SauceDemo, the collector can reuse the existing deterministic observers and
profiles:

```text
src/ai_web_explorer/safesym_bridge/state_observer.py
src/ai_web_explorer/safesym_bridge/saucedemo_adapter.py
src/ai_web_explorer/safesym_bridge/saucedemo_catalog.py
```

This lets the project compare:

```text
original WebState output
deterministic WebObservedGraph output
collector-produced WebKobeGraph output
```

The three outputs should describe the same browser behavior at different
abstraction levels.

## Relation to SafeSym

SafeSym should not explore websites and should not decide what the web graph
contains. SafeSym consumes a planning model derived from the collected graph.

The collector's responsibility is to produce a graph with enough semantic
structure for later PDDL projection:

```text
states
capabilities
preconditions
effects
execution evidence
```

SafeSym remains responsible for safety policy and safety-check insertion.

## Implementation Strategy

The implementation should be incremental.

### Phase 1: Read-only collector sidecar

Add a no-op-compatible collector that can be called from `ExploreLoop` without
changing exploration behavior.

Deliverable:

```text
ExploreLoop can run normally while collector receives state/action/transition
events.
```

### Phase 2: WebState to WebKobeGraph conversion

Build a converter that maps existing `WebState`, `Action`, and
`StateTransition` objects into a basic `WebKobeGraph`.

Deliverable:

```text
Existing explorer output can be projected into WebKobeGraph shape.
```

### Phase 3: richer observation during hooks

Use DOM, screenshots, title, URL, and executor tool calls to add evidence,
grounding, and deltas.

Deliverable:

```text
WebKobeGraph nodes and edges carry planning-relevant evidence and execution
traces.
```

### Phase 4: capability normalization

Normalize repeated content and concrete actions into reusable capabilities.

Deliverable:

```text
Concrete actions such as clicking one product card become abstract capabilities
such as add_to_cart(product).
```

### Phase 5: PDDL projection and audit

Project the collector-built graph into PDDL and add audit checks for noisy
states, duplicate nodes, unsupported deltas, and unsafe projections.

Deliverable:

```text
Collector-built graph can support SafeSym planning.
```

## Migration Plan for Recent Experimental Code

Recent Web-KOBE Playwright adapter and controller code should not be immediately
deleted. It should be reclassified.

Recommended handling:

```text
Keep:
  WebKobeGraph data models
  graph manager
  PDDL projector
  SauceDemo smoke tests where useful

Demote:
  WebKobeExplorationController
  WebKobePlaywrightAdapter as a generic exploration path
  web-kobe-explore as the future main CLI

Future:
  Either adapt these tests to collector output or remove them after collector
  coverage replaces them.
```

This avoids churn while steering new work toward the correct architecture.

## Testing Strategy

Testing should avoid requiring real LLM calls by default.

Recommended tests:

- Unit tests for `WebState -> WebKobeGraph` conversion.
- Unit tests for collector event ordering.
- Unit tests for target abstraction, such as multiple products becoming one
  product target type.
- SauceDemo deterministic tests using existing state observers and action
  profiles.
- Optional real browser tests gated by environment variables.
- Optional LLM integration tests gated by API key and explicit opt-in.

## Open Questions for Implementation

The implementation plan should decide:

1. Whether collector hooks should live directly in `ExploreLoop` or in a thin
   subclass/wrapper.
2. Whether the first converter should consume in-memory `WebState` objects or
   JSON output from `explore -o json`.
3. How much of the current `WebKobeGraph` model should be reused unchanged.
4. How to redact credentials and sensitive form input in `ExecutionTrace`.
5. Whether `web-kobe-explore` should be repointed to the original explorer or
   replaced by a new `explore --collector web-kobe` style command.

## Recommended Next Step

The next implementation should not add more independent exploration logic.

Recommended next implementation:

```text
Build a WebState-to-WebKobeGraph converter first.
```

Reason:

```text
It reuses existing explorer output immediately, requires minimal changes to the
old explorer, is easy to test without LLM/browser calls, and gives the project a
bridge from existing state-machine data to the richer Web-KOBE graph.
```

After the converter works, add collector hooks to enrich the graph during live
exploration.
