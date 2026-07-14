# Generic Web Exploration for SafeSym Design

## Purpose

This spec resets the next project direction around the original goal:

```text
Help SafeSym understand unknown web environments by exploring them,
building a semantic web capability graph, and projecting that graph into PDDL.
```

The project should build a general web exploration agent that can inspect an
unknown website, learn what states and actions exist, and produce a planning
model that SafeSym can use for safety-aware planning.

The target architecture is:

```text
unknown website
  -> browser exploration agent
  -> Web-KOBE-style semantic exploration graph
  -> PDDL projection
  -> SafeSym safety injection / planning
```

This is different from building a website content database. The system should
learn what the website can do, which state changes actions cause, and how those
actions can be grounded back to real browser operations.

## Direction Update

The previous `CapabilityNormalizer` design remains useful, but it should be
treated as a component inside a larger exploration system.

Earlier framing:

```text
WebObservedGraph
  -> CapabilityNormalizer
  -> WebCapabilityGraph sidecar
```

Updated framing:

```text
browser observation
  -> Web-KOBE exploration loop
  -> one semantic exploration graph with evidence
  -> PDDL/SafeSym projection
```

In other words, the next milestone should not only refactor an existing graph
builder. It should start building the generic exploration agent that constructs
a semantic graph directly during exploration.

## Core Principle

Use LLM/VLM aggressively for semantic understanding when useful, but commit
knowledge only after browser-grounded verification.

```text
LLM/VLM proposes semantics.
Browser execution verifies behavior.
The graph stores committed, evidenced knowledge.
PDDL projects the verified planning model.
SafeSym adds safety constraints.
```

This lets the project benefit from LLM/VLM strengths without making the final
planning model depend only on unverified language-model guesses.

## Why UI-KOBE Matters

UI-KOBE provides the closest working pattern:

```text
explore interface
  -> identify semantic state
  -> keep a graph of states and actions
  -> store action evidence and state deltas
  -> revisit under-explored nodes
  -> use graph-guided runtime decisions
```

The web project should reuse this pattern, not the Android-specific code.

UI-KOBE assumptions:

```text
Android screenshot
ADB/AITK actions
activity/package identity
coordinate taps
mobile UI hierarchy
```

Web assumptions:

```text
DOM and accessibility tree
URL/title/heading
forms/buttons/links
Playwright locators
browser state
PDDL/SafeSym planning model
```

The correct transfer is architectural:

```text
UI-KOBE GraphManager
  -> WebKobeGraphManager

UI-KOBE page_description
  -> web page description / PageFrame

UI-KOBE state_schema
  -> web state schema / planning predicate candidates

UI-KOBE interactable_elements
  -> DOM interactables + ActionTargets

UI-KOBE schema_delta
  -> ObservedDelta / effect candidates

UI-KOBE graph audit
  -> Web graph audit and PDDL readiness audit
```

## Single Exploration Graph

The next main graph should be a Web-KOBE-style semantic exploration graph. It
should combine semantic abstraction with enough evidence to debug, replay, and
project into PDDL.

This avoids forcing two separate graph types during the exploratory phase.

The existing `WebObservedGraph` should remain available for the current
PDDL/SafeSym MVP path. It should not be expanded into a universal exploration
graph. Instead:

```text
WebKobeGraph
  main graph for generic exploration

WebObservedGraph
  compatibility graph for current SauceDemo PDDL/SafeSym path

WebKobeGraph -> PDDL
  long-term planning path

WebKobeGraph -> WebObservedGraph
  optional compatibility export if needed
```

## WebKobeGraph

`WebKobeGraph` is the new exploration-time graph. It represents semantic web
states and executable transitions.

It should answer:

```text
What kind of page/state is this?
What planning-relevant values are true here?
What abstract targets exist here?
What actions/capabilities are available?
What happened when each action was executed?
Can the result be projected into PDDL?
```

Recommended top-level shape:

```python
WebKobeGraph:
    app: str
    start_node_id: str
    total_steps_completed: int
    nodes: list[WebKobeNode]
    edges: list[WebKobeEdge]
    meta: dict
```

The graph can later be stored as JSON, with optional companion artifacts such
as screenshots, DOM snapshots, or embeddings.

## WebKobeNode

A node is a semantic web state.

```python
WebKobeNode:
    node_id: str
    page_description: str
    page_frame: PageFrame
    state_schema: dict[str, list[Any]]
    last_state_snapshot: dict[str, Any]
    state_indicators: list[StateIndicator]
    action_targets: list[ActionTarget]
    interactable_elements: list[InteractableElement]
    capabilities: list[Capability]
    reference_observation: ReferenceObservation
    visit_count: int
    evidence: list[Evidence]
```

Important details:

- `page_description` is a reusable semantic description, not content-specific
  prose.
- `state_schema` accumulates observed dynamic keys and values across visits,
  similar to UI-KOBE.
- `last_state_snapshot` stores the most recent structured state observation.
- `action_targets` represent abstract object groups such as products, posts,
  rows, forms, carts, or orders.
- `interactable_elements` retain concrete exploration candidates and explored
  status.
- `capabilities` are graph-facing operations that may become PDDL actions.
- `reference_observation` can contain URL, screenshot path, DOM summary,
  accessibility summary, or hashes.

## WebKobeEdge

An edge records one or more observed executions from a source state to a target
state.

```python
WebKobeEdge:
    source_node_id: str
    target_node_id: str
    instruction: str
    action: BrowserAction
    capability: Capability | None
    target_observation: str
    observed_delta: list[ObservedDelta]
    schema_delta: dict[str, Any] | None
    execution_trace: ExecutionTrace
    pddl_hint: PddlActionHint | None
    visit_count: int
    evidence: list[Evidence]
```

The edge should keep both:

- semantic information needed for planning.
- concrete information needed for replay and debugging.

Self-loop edges are first-class. Many important web actions change state
without changing the page type:

```text
product_listing --add_to_cart(product)--> product_listing
cart_nonempty false -> true

form_page --fill_required_field--> form_page
required_fields_filled false -> true

listing_page --open_filter_menu--> listing_page
filter_panel_open false -> true
```

## ActionTarget

An `ActionTarget` is an abstract object or region that can be acted on. It
should usually represent a repeated group, not a concrete content instance.

```python
ActionTarget:
    target_type: str
    occurrence: str
    role: str
    structural_pattern: str | None
    representative_locator: str | None
    supported_capabilities: list[str]
    evidence: list[Evidence]
```

Examples:

```text
product / repeated / listed_item
post / repeated / listed_item
result / repeated / search_result
row / repeated / record
form / single / login_form
cart / single / current_cart
order / single / pending_order
```

Concrete instances can be used for grounding and examples, but they should not
become long-lived graph entities unless the planning task truly requires a
specific object.

## Capability

A `Capability` is an abstract operation available from a state.

```python
Capability:
    capability_id: str
    semantic_action: str
    action_kind: str
    target_type: str | None
    target_role: str | None
    input_schema: list[InputSlot]
    grounding: GroundingPattern
    availability: AvailabilityCondition
    expected_delta: list[StateChangeHint]
    pddl_hint: PddlActionHint | None
    evidence: list[Evidence]
```

Capabilities bridge the agent world and the planning world:

```text
agent-facing:
  "add a product to the cart"

browser-facing:
  click button[data-test^="add-to-cart"]

planner-facing:
  action add_to_cart_product
  precondition at_product_listing and cart_empty
  effect cart_nonempty
```

## LLM/VLM Responsibilities

LLM/VLM should be actively used where they can reduce brittle hand-coded
semantics.

Useful LLM/VLM tasks:

1. Page description
   - produce a reusable semantic description of the current page.
   - avoid overfitting to specific content.

2. Page type and state schema proposal
   - identify whether a page is login, listing, detail, cart, checkout, forum
     thread, search results, settings, etc.
   - suggest dynamic state keys worth tracking.

3. ActionTarget proposal
   - group repeated products, posts, rows, cards, or search results.
   - name target types and roles.

4. Capability proposal
   - name actions such as `search`, `open_result`, `add_to_cart`,
     `submit_form`, `open_post`, `apply_filter`, or `place_order`.
   - identify input slots for forms.

5. State matching and merge verification
   - decide whether two observations are the same semantic state when
     deterministic signals are ambiguous.

6. Exploration planning
   - select useful unexplored actions from the local graph state.
   - prioritize structural coverage rather than repeated content.

7. Graph audit
   - find duplicate states, wrong edges, missing expected capabilities, noisy
     deltas, and PDDL projection gaps.

8. PDDL draft assistance
   - propose predicate/action names and candidate preconditions/effects from
     the graph.

LLM/VLM output should include confidence and evidence references where
possible. The system should store it as semantic evidence, not as unquestioned
truth.

## Local Browser Responsibilities

Local deterministic code and Playwright remain responsible for grounding and
verification.

Local code should handle:

- loading pages and controlling browser state.
- extracting URL, title, headings, DOM candidates, forms, roles, labels,
  selectors, and accessibility information.
- executing clicks, fills, selections, keyboard actions, back/forward, and
  waits.
- checking whether an element is visible/enabled.
- comparing before/after structured observations.
- computing observed deltas.
- replaying known paths.
- writing graph artifacts.
- running tests.

This split is important:

```text
LLM/VLM can say what an action probably means.
The browser must prove what the action actually does.
```

## Exploration Loop

The generic exploration loop should look like:

```text
1. Observe current browser state.
2. Build local observation:
     URL, title, heading, DOM, accessibility, forms, candidates.
3. Ask semantic layer for:
     page_description, state schema, action targets, capabilities.
4. Identify existing graph node or create a new node.
5. Select an unexplored or high-value local action.
6. Ground the action to Playwright.
7. Execute the action.
8. Observe the resulting browser state.
9. Identify or create target node.
10. Compute schema_delta and observed_delta.
11. Add or update graph edge.
12. Mark concrete interactable/capability as explored.
13. Save graph.
14. Periodically audit, merge, and resume from under-explored nodes.
```

This is close to UI-KOBE, with browser-specific observation and grounding.

## State Matching

State matching should combine deterministic signals and semantic verification.

Deterministic signals:

- URL pattern.
- title.
- primary heading.
- DOM landmarks.
- form structure.
- capability signature.
- state indicator keys.
- action target types.

Semantic signals:

- LLM/VLM page description.
- embedding similarity over page descriptions.
- screenshot or visual comparison when useful.
- verifier result for candidate merge.

Recommended matching flow:

```text
1. Generate current page description and structured state snapshot.
2. Retrieve candidate nodes by deterministic keys and embedding similarity.
3. If confidence is high, update existing node.
4. If confidence is medium, ask verifier.
5. If verifier rejects or no candidate exists, create a new node.
6. Merge state schema and interactable elements into the chosen node.
```

This follows UI-KOBE's retrieval-plus-verification pattern.

## Exploration Policy

The explorer should prioritize coverage and structural diversity:

- explore global navigation and major workflow entries early.
- explore one representative repeated item rather than every item.
- prefer actions that may change page type, workflow state, or planning facts.
- include self-loop actions when they affect state.
- avoid unsafe or irreversible actions by default unless configured as allowed.
- revisit under-explored reachable nodes by replaying known paths.

For SafeSym, unsafe action classification should remain separate from safety
planning. The explorer may avoid obviously irreversible actions during data
collection, but SafeSym remains responsible for safety policy and injected
checks.

## PDDL Projection

PDDL projection is a first-class requirement, not an afterthought.

The graph should retain enough structure to produce:

```text
objects / symbolic state names
predicates / StateIndicators
actions / Capabilities
preconditions / AvailabilityConditions
effects / ObservedDeltas
initial state / matched start node
goal state / user or task objective
```

Potential projection:

```text
WebKobeNode.page_frame.page_type
  -> (at <page_type>)

StateIndicator(cart_nonempty = true)
  -> (cart_nonempty)

Capability(add_to_cart_product)
  -> (:action add_to_cart_product ...)

ObservedDelta(cart_nonempty false -> true)
  -> effect: (cart_nonempty)
```

For early v1, PDDL projection can support a constrained subset:

- boolean state indicators.
- page-type navigation.
- object-free actions.
- simple add/delete effects.

Parameterized actions can come later:

```text
add_to_cart(?product)
open_post(?post)
fill_field(?field ?value)
```

## SafeSym Boundary

The web explorer should not decide the safety policy.

The explorer provides:

- available actions.
- state predicates.
- preconditions and effects.
- action grounding.
- evidence and confidence.
- optional tags that may help SafeSym identify sensitive actions.

SafeSym handles:

- which actions require safety checks.
- which checks must be inserted.
- how safety constraints affect planning.
- whether a plan is safe.

This separation keeps the web model reusable and keeps safety reasoning in
SafeSym.

## Error Handling

The system should treat uncertainty as data.

Recommended edge/node statuses:

- `verified`: executed and before/after delta recorded.
- `semantic_proposed`: proposed by LLM/VLM but not yet executed.
- `failed_execution`: browser action failed.
- `no_observable_change`: action executed but no semantic delta was detected.
- `external_navigation`: action left the target site/app boundary.
- `unsafe_skipped`: action was skipped by exploration policy.
- `needs_review`: audit or low confidence flagged the item.

Graph construction should not silently discard uncertainty. It should store
enough status and evidence for later audit or re-exploration.

## Relationship to Existing Code

Reuse existing project pieces:

- `browser_runner.py` for Playwright orchestration patterns.
- `WebObservation` and `StateSnapshot` as useful observation primitives.
- `dom_observer.py` for DOM candidate extraction.
- semantic resolver concepts for mapping candidates to actions.
- `GraphExplorer` loop concepts.
- `effect_inferer.py` for before/after deltas.
- `capability_graph.py` model ideas such as `Capability`, `Evidence`,
  `ObservedDelta`, `GroundingPattern`, and `ExecutionTrace`.
- current PDDL compiler tests as guidance for planning compatibility.

Do not force all generic exploration data into `WebObservedGraph`. That graph
should remain compatible with the current SauceDemo PDDL/SafeSym path.

New modules can be introduced for the generic agent:

```text
web_kobe_graph.py
web_kobe_graph_manager.py
web_kobe_explorer.py
web_semantic_assistor.py
web_state_matcher.py
web_action_extractor.py
web_exploration_policy.py
web_pddl_projector.py
web_graph_auditor.py
```

The exact file split can be refined during implementation planning.

## Milestones

### Milestone 1: Web-KOBE graph skeleton

Build and serialize `WebKobeGraph`, `WebKobeNode`, and `WebKobeEdge`.

Success criteria:

- graph JSON can store nodes, edges, action targets, capabilities, deltas, and
  evidence.
- tests cover serialization and basic graph updates.

### Milestone 2: Generic browser exploration loop

Create a Playwright-based loop that observes a page, identifies/creates a node,
chooses an action, executes it, records an edge, and saves the graph.

Success criteria:

- can run for a small step budget on SauceDemo or another controlled site.
- records self-loop and navigation transitions.
- marks explored interactables.

### Milestone 3: LLM/VLM semantic assistor

Add a semantic assistance seam for page description, target grouping,
capability naming, and state matching.

Success criteria:

- local deterministic extraction still runs without LLM/VLM.
- LLM/VLM output is stored with evidence/confidence.
- graph construction can use assisted semantics when configured.

### Milestone 4: PDDL projection subset

Project the graph into a simple PDDL domain/problem.

Success criteria:

- page type and boolean state indicators become predicates.
- verified capabilities become actions.
- observed deltas become effects.
- output can be passed to the existing SafeSym pipeline for a controlled task.

### Milestone 5: Audit and coverage

Add graph audit, merge suggestions, and under-explored node continuation.

Success criteria:

- duplicate states can be flagged and verified.
- suspicious edges can be retried.
- low-coverage nodes can be revisited by replaying known paths.

## Non-Goals for the First Implementation

Do not try to solve all of these immediately:

- full arbitrary website support.
- perfect state abstraction.
- complete PDDL support for all web interactions.
- reliable parameterized object planning.
- autonomous handling of high-risk real purchases, posts, or irreversible
  actions.
- replacing the existing SauceDemo PDDL/SafeSym path.
- production browser agent runtime.

The first implementation should prove the chain:

```text
unknown-ish web page
  -> semantic exploration graph
  -> simple PDDL projection
  -> SafeSym-compatible planning model
```

Quality can improve after the chain is alive.

## Testing Strategy

Testing should proceed from local units to browser-level smoke tests:

1. graph model serialization.
2. node merge/schema update logic.
3. edge delta recording.
4. action target and capability storage.
5. deterministic action extraction from static HTML fixtures.
6. state matcher behavior with mocked semantic assistor outputs.
7. exploration policy action selection.
8. PDDL projection for a small graph.
9. browser smoke test on SauceDemo or a local fixture site.
10. SafeSym compile/planning smoke test for a constrained graph.

Existing command family should remain healthy:

```bash
python -m pytest tests/safesym_bridge -v
```

New tests can live under:

```text
tests/safesym_bridge/test_web_kobe_*.py
```

or a new package if the implementation grows beyond the bridge module.

## Open Questions

These should be answered during implementation planning:

1. Should `WebKobeGraph` live inside `safesym_bridge` or a new top-level
   package such as `web_kobe`?
2. Which LLM/VLM provider path should be used first in this local project?
3. Should the first browser smoke test use SauceDemo, a local fixture website,
   or both?
4. How should risky actions be labeled or skipped during exploration before
   SafeSym receives the model?
5. Should PDDL projection target the existing compiler shape first, or a new
   generic projector?

## Implementation Plan Entry Point

After this design is approved, the implementation plan should start with the
smallest vertical slice:

```text
WebKobeGraph model
  -> deterministic page observation
  -> one-step browser exploration
  -> graph edge with delta
  -> simple PDDL projection
```

Then add LLM/VLM assistance once the local graph path is testable.

This keeps the work grounded while still moving toward the real goal:

```text
SafeSym understands and plans in previously unknown web environments.
```
