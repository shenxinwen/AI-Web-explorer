# Capability Normalizer Design

## Purpose

This spec defines the next step for the web capability graph work:

```text
WebObservedGraph / ObservedTransition[]
  -> CapabilityNormalizer
  -> WebCapabilityGraph
```

The goal is to keep the current web/PDDL/SafeSym pipeline intact while moving
the experimental capability graph sidecar from SauceDemo-specific projection
toward a reusable Web-KOBE-style abstraction layer.

The project should not fork UI-KOBE as the main codebase. Instead, it should
reuse UI-KOBE's patterns inside the current web project:

```text
pre-explore interface
  -> build semantic state/action graph
  -> match current runtime state to graph
  -> present local graph-grounded actions
  -> fall back to exploration only when graph coverage is missing
```

## Decision Summary

The v1 design choices are:

- Continue building in `ai-web-explorer`, not by rewriting UI-KOBE for web.
- Use UI-KOBE as a design reference for semantic state graphs, representative
  repeated elements, self-loop deltas, graph-guided runtime, and graph audit.
- Implement a rule-based `CapabilityNormalizer` sidecar first.
- Keep LLM/VLM out of the default v1 path, but define a future
  `SemanticAssistor` seam.
- Add `ActionTarget` as a first-class part of `SemanticPageState`.
- Keep SafeSym responsible for safety policy; the web layer models what the
  website can do and what changes when actions execute.

## Why Not Modify UI-KOBE Directly?

UI-KOBE is Android-centered. Its code assumes Android screens, ADB/AITK
actions, screenshots, UI hierarchy, coordinate taps, Android activity/package
state, and Android runtime adapters.

This project is web-centered. It already has:

- Playwright browser execution.
- DOM and accessibility-oriented observation.
- `WebObservation` and `StateSnapshot`.
- DOM interactable candidates.
- Semantic action resolution.
- `GraphExplorer`.
- `WebObservedGraph`.
- graph-to-PDDL compilation.
- SafeSym integration.
- an experimental `WebCapabilityGraph` sidecar.

Adapting UI-KOBE directly would require replacing most of its execution and
observation stack. The practical path is to port the useful architecture, not
the Android-specific implementation.

## UI-KOBE Pattern Mapping

The intended mapping is:

```text
UI-KOBE semantic screen state
  -> SemanticPageState

UI-KOBE representative UI element group
  -> ActionTarget

UI-KOBE action edge
  -> CapabilityTransition

UI-KOBE schema delta
  -> ObservedDelta / StateIndicator diff

UI-KOBE state retrieval + verification
  -> PageFrame/state matching + optional SemanticAssistor

UI-KOBE local graph-guided runtime choices
  -> known capabilities from the matched SemanticPageState
```

The most important borrowed idea is representative grouping. A site may contain
many concrete products, posts, search results, or table rows, but the graph
should usually store one abstract target group:

```text
product cards -> ActionTarget(product, repeated, listed_item)
forum posts -> ActionTarget(post, repeated, listed_item)
search results -> ActionTarget(result, repeated, listed_item)
table rows -> ActionTarget(row, repeated, record)
```

The graph should answer:

```text
What can this page/state do?
```

not:

```text
What exact content instances are currently listed?
```

## Data Collection Strategy

The system should acquire data through real browser exploration:

```text
Playwright browser
  -> observe current page
  -> extract URL/title/heading/DOM/accessibility/forms/interactables
  -> normalize semantic state and abstract action targets
  -> execute one representative capability
  -> observe after state
  -> infer semantic before/after delta
  -> add capability graph transition
```

The primary data sources are:

1. Page observation
   - URL and normalized URL pattern.
   - document title.
   - primary heading or landmarks.
   - visible forms and controls.
   - DOM locators, roles, labels, names, IDs, and `data-*` attributes.
   - repeated structural patterns.

2. State indicators
   - planning-relevant values such as `logged_in`, `cart_nonempty`,
     `checkout_info_complete`, `order_review_ready`, `order_created`,
     `login_error_visible`, or `modal_open`.
   - not arbitrary content such as product price, image URL, post author, or
     styling class unless it affects capability availability or verification.

3. Executed transition evidence
   - concrete action kind.
   - locator or grounding pattern.
   - representative target sample.
   - before and after observation IDs.
   - execution success or error.

4. Semantic diff
   - page frame changes.
   - state indicator changes.
   - self-loop state deltas.
   - validation/failure transitions when safely explored.

This is active exploration, not passive crawling. The core knowledge comes from
observing what changes after representative actions execute.

## Local Logic vs LLM/VLM

The v1 path should be deterministic and rule-based:

```text
Playwright / DOM
  -> local deterministic extraction
  -> SiteCapabilityProfile rules
  -> CapabilityNormalizer
  -> WebCapabilityGraph
```

Local logic should own:

- DOM candidate extraction.
- URL/title/heading normalization.
- page frame construction when profile rules cover it.
- form field extraction and grounding.
- state indicator extraction.
- before/after delta inference.
- capability grounding patterns.
- JSON serialization.
- tests and graph regression checks.

LLM/VLM should not write the canonical graph in v1. Later, a semantic assistant
can help with low-confidence semantic decisions:

- suggest page type names.
- suggest target group names.
- suggest capability names.
- verify whether two states should merge.
- explain unexpected transition outcomes.

Any future LLM/VLM output should be treated as a proposal that local code can
accept, reject, verify, and record with evidence/confidence. This keeps graph
construction reproducible and testable.

## Architecture

The v1 architecture is:

```text
ObservedTransition[]
  -> CapabilityNormalizer
      -> SiteCapabilityProfile
      -> PageFrame
      -> StateIndicator[]
      -> ActionTarget[]
      -> Capability[]
      -> ObservedDelta[]
  -> WebCapabilityGraph
```

### CapabilityNormalizer

`CapabilityNormalizer` is the generic orchestration layer. It should not know
SauceDemo-specific page IDs, headings, fields, or actions.

Responsibilities:

- iterate through observed transitions.
- normalize source and target snapshots into semantic states.
- ask the profile for page frame, state indicators, action targets, and
  capabilities.
- compute or delegate observed deltas.
- deduplicate states, capabilities, and targets.
- build `CapabilityTransition` records.
- return `WebCapabilityGraph`.

The current `build_capability_graph(...)` function can remain as the public
entry point while delegating to `CapabilityNormalizer`.

### SiteCapabilityProfile

`SiteCapabilityProfile` is the site-specific rule interface. SauceDemo should
be the first implementation.

Expected responsibilities:

- map raw `page_id` to semantic `page_type`.
- produce page headings or page identity hints.
- derive planning-relevant `StateIndicator` values from `StateSnapshot`.
- derive stable semantic state IDs.
- produce page-local `ActionTarget` values.
- normalize a semantic action into a `Capability`.
- define availability conditions.
- define expected delta hints.

The profile is where v1 keeps rule-based knowledge. This keeps the generic
normalizer reusable while allowing controlled site-specific behavior.

### SauceDemoCapabilityProfile

The initial profile should move the existing SauceDemo-specific logic out of
`capability_builder.py`, including:

- `PAGE_TYPES`.
- `HEADINGS`.
- `CAPABILITY_RULES`.
- `_indicator_values`.
- `_state_id`.
- rule-derived capabilities.
- rule-derived expected deltas.
- action targets for pages such as product listing, cart, login form, checkout
  form, and pending order review.

This should be a refactor of current behavior, not a semantic rewrite.

### SemanticAssistor

`SemanticAssistor` is a future seam, not a v1 requirement.

The default v1 implementation should behave as a no-op. The interface can be
introduced later when the project needs LLM/VLM assistance for low-confidence
classification, naming, or state merge verification.

## Data Model Changes

### ActionTarget

Add `ActionTarget` to `capability_graph.py`.

```python
ActionTarget:
    target_type: str
    occurrence: str
    role: str
    structural_pattern: str | None
    supported_capabilities: list[str]
    evidence: list[Evidence]
```

Field meanings:

- `target_type`: abstract object type, such as `product`, `post`, `result`,
  `row`, `form`, `cart`, or `order`.
- `occurrence`: `single` or `repeated`.
- `role`: page-local semantic role, such as `listed_item`, `login_form`,
  `current_cart`, `checkout_info_form`, or `pending_order`.
- `structural_pattern`: DOM or structural pattern when known, such as
  `.inventory_item`. This is a representative pattern, not a concrete content
  instance.
- `supported_capabilities`: capability IDs that can operate on this target.
- `evidence`: sources that justify the target abstraction.

Example:

```python
ActionTarget(
    target_type="product",
    occurrence="repeated",
    role="listed_item",
    structural_pattern=".inventory_item",
    supported_capabilities=["add_to_cart_product"],
    evidence=[Evidence(source="site_profile", selector=".inventory_item")],
)
```

### SemanticPageState

Extend `SemanticPageState` with:

```python
action_targets: list[ActionTarget]
```

The serialized JSON should include `action_targets` alongside
`state_indicators` and `capabilities`.

This makes page meaning clearer:

```text
The page has a repeated product/listed_item target group.
That target supports add_to_cart_product.
```

instead of storing only capability-local `target_type` fields.

### Capability

Keep existing `Capability.target_type` and `Capability.target_role` fields in
v1 for compatibility and easy consumption.

`ActionTarget` should not replace those fields immediately. It should make the
target abstraction explicit while preserving the current capability JSON shape.

## Normalization Flow

The normalizer should build a graph with this flow:

1. Receive `app`, `start_node`, and observed transitions.
2. For each transition:
   - normalize source state ID.
   - normalize target state ID.
   - store source and target snapshots.
   - normalize transition action into a capability.
   - infer observed delta from source and target.
   - create `CapabilityTransition`.
3. For each stored state:
   - build `PageFrame`.
   - build `StateIndicator[]`.
   - build `ActionTarget[]`.
   - build available `Capability[]`.
   - create `SemanticPageState`.
4. Return `WebCapabilityGraph`.

The first implementation should preserve current output semantics except for
the addition of `action_targets`.

## SauceDemo v1 Examples

### Product listing

```text
page_type = product_listing
state_id = product_listing_cart_empty | product_listing_cart_nonempty

ActionTarget:
  target_type = product
  occurrence = repeated
  role = listed_item
  structural_pattern = .inventory_item
  supported_capabilities = [add_to_cart_product]

Capability:
  capability_id = add_to_cart_product
  semantic_action = add_to_cart
  action_kind = click
  target_type = product
  target_role = listed_item
  grounding = button[data-test^="add-to-cart"]

ObservedDelta:
  cart_nonempty false -> true
```

### Login

```text
page_type = login

ActionTarget:
  target_type = form
  occurrence = single
  role = login_form
  structural_pattern = #login_button_container
  supported_capabilities = [submit_login_form]
```

### Cart

```text
page_type = cart
state_indicator = cart_nonempty

ActionTarget:
  target_type = cart
  occurrence = single
  role = current_cart
  supported_capabilities = [checkout_start]
```

### Checkout review

```text
page_type = checkout_review
state_indicator = order_review_ready

ActionTarget:
  target_type = order
  occurrence = single
  role = pending_order
  supported_capabilities = [place_order]
```

## Error Handling and Confidence

v1 should be conservative:

- Unknown semantic actions should not crash graph construction unless the
  existing behavior already requires them.
- Unsupported actions can be skipped or recorded as low-confidence only if the
  caller explicitly opts into that behavior later.
- Missing profile rules should be easy to diagnose from test failures.
- Evidence should identify whether an item came from `site_profile`,
  `resolver_rule`, `state_signature`, `transition_diff`, or observed DOM data.

Confidence is already available on `Evidence` and `ObservedDelta`. v1 can keep
confidence at `1.0` for rule-derived values and reserve lower confidence for
future assisted or heuristic output.

## Testing Strategy

Tests should focus on behavior preservation plus the new abstraction boundary:

1. `ActionTarget` serialization.
2. `SemanticPageState.to_dict()` includes `action_targets`.
3. `build_capability_graph(...)` still represents the SauceDemo checkout path.
4. Product instances are still abstracted away.
5. Product listing states include a repeated `product/listed_item` target.
6. Login, cart, checkout form, and checkout review states include appropriate
   single action targets.
7. `CapabilityNormalizer` can be tested with the SauceDemo profile without
   browser execution.

Existing safesym bridge tests should remain the regression suite:

```bash
python -m pytest tests/safesym_bridge -v
```

## Non-Goals for v1

Do not implement these in v1:

- generic automatic repeated group discovery.
- LLM/VLM calls in the default graph construction path.
- runtime graph-guided agent execution.
- replacing `WebObservedGraph -> PDDL -> SafeSym`.
- generic PDDL compilation from `WebCapabilityGraph`.
- multi-site support beyond introducing a profile boundary.
- safety policy or safety-check injection.

These are later stages after the normalizer boundary is stable.

## Implementation Plan Entry Point

After this spec is approved, the implementation plan should start with a
low-risk refactor:

1. Add `ActionTarget` model and JSON output.
2. Add `SiteCapabilityProfile` protocol or abstract base.
3. Add `SauceDemoCapabilityProfile` by moving existing rules from
   `capability_builder.py`.
4. Add `CapabilityNormalizer`.
5. Make `build_capability_graph(...)` delegate to the normalizer.
6. Update tests and docs.

The implementation should avoid changing the active PDDL/SafeSym path.
