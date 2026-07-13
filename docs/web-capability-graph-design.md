# WebCapabilityGraph Design

## Purpose

This document proposes the next abstraction layer for the current
`ai-web-explorer` project.

The goal is not to build a website content database. The goal is to build a
website capability map:

```text
What semantic state is the website in?
What can be done from that state?
What state changes when that capability is executed?
```

This direction extends the current graph-first pipeline:

```text
browser observation
  -> semantic page state
  -> capability transition
  -> WebCapabilityGraph
  -> planning model / PDDL
  -> SafeSym
```

The key shift is from content-oriented modeling to capability-oriented
modeling. For example, on a shopping site we do not need to persist every
specific product, price, image, or description. We need to learn that a product
listing page exposes a capability such as `add_to_cart(product)`, and that
executing that capability changes relevant state such as `cart_nonempty`.

## Design Principles

### 1. Capability-first

The primary question is:

```text
What can this page or website state do?
```

Objects such as products, posts, fields, carts, and orders are modeled only
when they help describe an action target or a state-changing capability.

### 2. Abstract targets, not content instances

The graph should not store unnecessary concrete content instances.

For example:

```text
Sauce Labs Backpack
Sauce Labs Bike Light
Sauce Labs Bolt T-Shirt
```

should normally be abstracted as:

```text
target_type = product
target_role = listed_item
capability = add_to_cart(product)
```

Likewise, many forum posts can be abstracted as:

```text
target_type = post
target_role = listed_item
capability = open_post(post)
```

Concrete instances are still used during exploration and runtime grounding, but
they should not become the core long-lived knowledge unless the instance itself
is part of the process state, such as the current cart, current session, or
pending order.

### 3. State-change relevance

Only state indicators that affect capability availability, graph transitions,
planning goals, or execution verification should be retained.

Useful examples:

```text
cart_nonempty = true
required_fields_filled = false
order_review_ready = true
login_error_visible = false
```

Usually unnecessary examples:

```text
product image URL
specific product price
post author
visual styling class
tracking query parameter
```

### 4. Concrete execution, abstract storage

Exploration must execute concrete browser actions, because the browser can only
click, fill, or select real DOM elements.

The graph should store the abstract capability transition.

Example:

```text
Concrete exploration:
  click button[data-test="add-to-cart-sauce-labs-backpack"]

Abstract graph transition:
  product_listing_empty --add_to_cart(product)--> product_listing_nonempty
  delta: cart_nonempty false -> true
```

### 5. SafeSym separation

The web exploration layer does not decide safety policy.

This project should output a high-quality model of states, capabilities, and
effects. SafeSym remains responsible for deciding which actions require safety
checks and for injecting or enforcing those checks in the planning model.

## Relation to UI-KOBE

The UI-KOBE paper explores Android applications by building a knowledge graph of
semantic UI states and executable UI transitions. At runtime, the GUI agent
matches the current screen to the graph and chooses from local graph-guided
actions instead of relying entirely on online ReAct-style exploration.

The useful analogy for this project is:

```text
UI-KOBE semantic UI node
  -> SemanticPageState

UI-KOBE action edge
  -> CapabilityTransition

UI-KOBE schema delta
  -> ObservedDelta / StateIndicator diff

UI-KOBE graph-guided runtime
  -> current web page matched to a known state, then choose a known capability
```

This reinforces the project direction: pre-explore the interface, build a
capability graph, then make runtime agents cheaper and more stable by grounding
their decisions in the precomputed graph.

## Core Model

```text
WebCapabilityGraph
  nodes: SemanticPageState[]
  edges: CapabilityTransition[]
```

The graph stores abstract website behavior. It is not a DOM snapshot archive and
not a content database.

## SemanticPageState

`SemanticPageState` is a graph node. It represents a semantic page/function
state, not merely a URL, screenshot, or DOM tree.

```python
SemanticPageState:
    state_id: str
    page_frame: PageFrame
    state_indicators: list[StateIndicator]
    capabilities: list[Capability]
    evidence: list[Evidence]
```

It answers:

```text
Where am I?
Which planning-relevant state indicators are true?
What capabilities are available here?
Why does the system believe this?
```

Example:

```text
state_id = product_listing_cart_empty
page_type = product_listing
state_indicators:
  cart_nonempty = false
capabilities:
  add_to_cart(product)
  open_cart
```

Another state may share the same page type but differ in planning-relevant
state:

```text
state_id = product_listing_cart_nonempty
page_type = product_listing
state_indicators:
  cart_nonempty = true
capabilities:
  add_to_cart(product)
  open_cart
```

## PageFrame

`PageFrame` identifies the semantic page or workflow position.

```python
PageFrame:
    page_id: str
    page_type: str
    url: str
    url_pattern: str
    title: str
    heading: str | None
    signature_hints: dict
    evidence: list[Evidence]
```

Field meanings:

- `page_id`: stable site-local page identity, such as `saucedemo:cart`.
- `page_type`: generic page type, such as `login`, `product_listing`, `cart`,
  `checkout_form`, `checkout_review`, or `confirmation`.
- `url`: original URL retained for debugging.
- `url_pattern`: normalized URL pattern with session, tracking, or random
  parameters removed.
- `title`: browser document title.
- `heading`: primary visible heading when available.
- `signature_hints`: small page-identity hints such as `has_error` or
  `step=review`.
- `evidence`: sources used to identify the frame.

`PageFrame` should remain small. It names the location in the website map; it
should not absorb all state facts or content details.

## StateIndicator

`StateIndicator` represents a planning-relevant state value.

```python
StateIndicator:
    name: str
    value: bool | str | int
    role: str
    evidence: list[Evidence]
```

Examples:

```text
cart_nonempty = true
logged_in = false
required_fields_filled = false
order_review_ready = true
login_error_visible = true
```

State indicators should be selected by usefulness. They should help answer at
least one of these questions:

```text
Does this capability become available or unavailable?
Does this transition change graph state?
Can this be a planning precondition or effect?
Can this verify that execution succeeded?
```

## Capability

`Capability` is the central abstraction. It represents an abstract operation
available in a page state.

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
    evidence: list[Evidence]
```

It answers:

```text
What can be done?
What browser action kind is needed?
What abstract target does it act on?
What inputs are required?
How can it be grounded to the current DOM?
When is it available?
What state change is expected?
```

Example: adding a product to a cart.

```python
Capability(
    capability_id="add_to_cart_product",
    semantic_action="add_to_cart",
    action_kind="click",
    target_type="product",
    target_role="listed_item",
    input_schema=[],
    grounding=GroundingPattern(
        locator_strategy="css_pattern",
        locator_pattern='button[data-test^="add-to-cart"]',
        target_selection_policy="first_available",
    ),
    availability=AvailabilityCondition(
        required_page_type="product_listing",
        required_target_presence="product",
    ),
    expected_delta=[
        StateChangeHint("cart_nonempty", False, True),
    ],
)
```

Example: submitting a login form.

```python
Capability(
    capability_id="submit_login_form",
    semantic_action="login_submit",
    action_kind="composite",
    target_type="form",
    target_role="login_form",
    input_schema=[
        InputSlot("username", "text", required=True),
        InputSlot("password", "password", required=True),
    ],
    grounding=GroundingPattern(
        locator_strategy="form_fields",
        field_bindings={
            "username": "#user-name",
            "password": "#password",
            "submit": "#login-button",
        },
    ),
    availability=AvailabilityCondition(
        required_page_type="login",
    ),
    expected_delta=[
        StateChangeHint("logged_in", False, True),
        StateChangeHint("page_type", "login", "product_listing"),
    ],
)
```

## ActionTarget

The model may include lightweight action-target descriptions when useful, but
the target is abstract.

```python
ActionTarget:
    target_type: str
    occurrence: str
    role: str
    structural_pattern: str
    supported_capabilities: list[str]
```

Example:

```python
ActionTarget(
    target_type="product",
    occurrence="repeated",
    role="listed_item",
    structural_pattern=".inventory_item",
    supported_capabilities=["add_to_cart_product"],
)
```

This says the page contains repeated product-like action targets. It does not
say that the graph should persist every concrete product instance.

## GroundingPattern

`GroundingPattern` connects abstract capabilities back to concrete execution.

```python
GroundingPattern:
    locator_strategy: str
    locator_pattern: str
    target_selection_policy: str
    field_bindings: dict
```

Examples:

```text
locator_pattern = button[data-test^="add-to-cart"]
target_selection_policy = first_available
```

For a form:

```text
field_bindings:
  username -> #user-name
  password -> #password
  submit -> #login-button
```

Runtime execution can override `target_selection_policy` if the user task
contains a constraint, such as choosing a specific product or the cheapest
available item. The pre-explored graph still stores only the abstract pattern.

## CapabilityTransition

`CapabilityTransition` is a graph edge. It records what happened when a
capability was executed from a semantic state.

```python
CapabilityTransition:
    transition_id: str
    source_state_id: str
    capability_id: str
    target_state_id: str
    transition_kind: str
    observed_delta: list[ObservedDelta]
    execution_trace: ExecutionTrace
    evidence: list[Evidence]
```

Supported transition kinds for v1:

```text
navigation
  page type, URL pattern, or workflow position changes

state_delta
  same page type, but planning-relevant state changes

form_progress
  form or field completion state changes

modal_overlay
  menu, dialog, or overlay opens/closes

failure
  validation error or failed action state appears

unknown
  action executed, but semantic change could not be reliably classified
```

Example: add to cart.

```python
CapabilityTransition(
    transition_id="inventory_empty__add_to_cart_product__inventory_nonempty",
    source_state_id="inventory_cart_empty",
    capability_id="add_to_cart_product",
    target_state_id="inventory_cart_nonempty",
    transition_kind="state_delta",
    observed_delta=[
        ObservedDelta(
            field="cart_nonempty",
            before=False,
            after=True,
            delta_type="state_indicator_change",
            confidence=1.0,
        )
    ],
)
```

Example: checkout.

```python
CapabilityTransition(
    transition_id="cart_nonempty__checkout_start__checkout_info",
    source_state_id="cart_nonempty",
    capability_id="checkout_start",
    target_state_id="checkout_info",
    transition_kind="navigation",
    observed_delta=[
        ObservedDelta(
            field="page_type",
            before="cart",
            after="checkout_info",
            delta_type="page_frame_change",
            confidence=1.0,
        )
    ],
)
```

## ObservedDelta

`ObservedDelta` records a semantic difference between the before and after
states.

```python
ObservedDelta:
    field: str
    before: Any
    after: Any
    delta_type: str
    confidence: float
    evidence: list[Evidence]
```

It should compare semantic state, not raw DOM.

Good deltas:

```text
cart_nonempty false -> true
page_type cart -> checkout_info
required_fields_filled false -> true
login_error_visible false -> true
```

Usually bad deltas:

```text
random DOM id changed
CSS class changed
tracking query changed
list content changed without affecting capabilities
```

## ExecutionTrace

`ExecutionTrace` stores concrete exploration details for debugging and audit.
It is not the core planning abstraction.

```python
ExecutionTrace:
    concrete_action_kind: str
    concrete_locator: str
    concrete_target_sample: str | None
    input_values_used: dict
    before_observation_id: str
    after_observation_id: str
    success: bool
    error: str | None
```

Example:

```text
concrete_locator = button[data-test="add-to-cart-sauce-labs-backpack"]
concrete_target_sample = product
success = true
```

The concrete product sample helps reproduce the exploration, but it should not
turn into a long-lived domain entity unless the task model truly needs it.

## Evidence

`Evidence` records why the system believes a state, capability, or transition.

```python
Evidence:
    source: str
    selector: str | None
    text_sample: str | None
    url: str | None
    confidence: float
```

Example sources:

```text
url
title
heading
dom
accessibility
transition_diff
resolver_rule
llm_verifier
```

Evidence keeps the graph debuggable. It should support questions such as:

```text
Why is this page classified as cart?
Why is this button resolved as checkout_start?
Why did this edge produce cart_nonempty=true?
```

## Collection Pipeline

The proposed collection flow is:

```text
1. Observe browser state
   Capture URL, title, heading, visible text, interactables, forms,
   accessibility data, and optional screenshots.

2. Build PageFrame
   Normalize URL, classify page type, extract heading, and record evidence.

3. Extract StateIndicators
   Keep only state values that affect capabilities, transitions, goals, or
   execution verification.

4. Detect action targets
   Identify abstract target types such as product, post, form, field, cart, or
   order. Avoid persisting unnecessary concrete instances.

5. Resolve Capabilities
   Convert DOM candidates into abstract capabilities using page context,
   locator patterns, visible labels, roles, and resolver rules.

6. Select an unexplored capability
   Prefer capabilities not yet covered from the current semantic state, or
   transitions with low confidence.

7. Ground and execute
   Use GroundingPattern to pick a concrete DOM target and execute with
   Playwright.

8. Observe after state
   Build the next SemanticPageState.

9. Infer ObservedDelta
   Compare semantic state before and after. Ignore raw DOM noise.

10. Add or merge graph edge
   Store a CapabilityTransition, then merge equivalent states or transitions
   when needed.
```

## Current Project Mapping

The current codebase already has many useful pieces.

```text
WebObservation
  -> raw material for SemanticPageState

StateSnapshot
  -> planner-facing projection of semantic state

DOM interactable candidates
  -> input to Capability resolution

semantic resolver / action catalog
  -> current rule-based source of Capability IDs

GraphExplorer
  -> exploration loop for discovering transitions

WebObservedGraph
  -> current graph structure, gradually upgradeable toward WebCapabilityGraph

EffectInferer
  -> source of ObservedDelta

PDDL compiler
  -> should compile capability transitions into planning actions/effects

SafeSym
  -> consumes the planning model and handles safety planning
```

## SauceDemo Mapping

Examples for the current MVP:

```text
login page:
  page_type = login
  capability = submit_login_form
  expected_delta = logged_in false -> true, page_type login -> product_listing

inventory page:
  page_type = product_listing
  action_target = product listed_item repeated
  capability = add_to_cart(product)
  observed_delta = cart_nonempty false -> true

cart page:
  page_type = cart
  state_indicator = cart_nonempty
  capability = checkout_start
  observed_delta = page_type cart -> checkout_info

checkout info page:
  page_type = checkout_form
  capability = submit_checkout_info
  input_schema = first_name, last_name, postal_code
  observed_delta = page_type checkout_form -> checkout_review

checkout overview page:
  page_type = checkout_review
  capability = place_order
  observed_delta = page_type checkout_review -> checkout_complete

checkout complete page:
  page_type = confirmation
  state_indicator = order_created true
```

## PDDL Projection

The graph should remain richer than PDDL, but each transition should be
projectable into planning facts and actions.

Example transition:

```text
source:
  at(product_listing)
  cart_empty

capability:
  add_to_cart_product

delta:
  cart_empty -> cart_nonempty
```

Possible PDDL action:

```lisp
(:action add_to_cart_product
  :precondition (and
    (at product_listing)
    (cart_empty)
  )
  :effect (and
    (not (cart_empty))
    (cart_nonempty)
  )
)
```

For the MVP, object parameters may be avoided when the concrete instance does
not matter:

```text
add_any_product_to_cart
```

Later, parameterized actions can be introduced when a task requires binding a
specific target at runtime:

```text
add_to_cart(?product)
open_post(?post)
fill_field(?field, ?value)
```

## Runtime Agent Use

At runtime, the agent should not need to parse the whole page from scratch when
the graph covers the current state.

Expected runtime flow:

```text
1. Observe current browser page.
2. Match it to a SemanticPageState.
3. Retrieve local capabilities and known transitions.
4. Select a capability based on the user task and planner output.
5. Ground the capability to the current DOM.
6. Execute.
7. Verify resulting state against expected or observed delta.
8. Fall back to exploratory behavior only if the state or needed capability is
   not covered.
```

This preserves a fallback path while making the common path graph-guided and
cheap.

## Open Design Questions

The following should be decided during implementation planning:

1. How aggressively should states be merged when page content differs but
   capabilities are the same?
2. Which state indicators are generic enough for v1, and which remain
   SauceDemo-specific?
3. Should v1 compile PDDL actions as object-free actions, parameterized actions,
   or both?
4. How should invalid/failure transitions be explored without creating unsafe or
   noisy graph branches?
5. What confidence threshold should be required before a transition becomes part
   of the main planning model?
6. Where should graph audit and node merge logic live?

## Recommended v1 Scope

The first implementation should be conservative:

```text
1. Add data models for SemanticPageState, Capability, CapabilityTransition,
   ObservedDelta, GroundingPattern, and Evidence.

2. Keep SauceDemo as the controlled target.

3. Generate WebCapabilityGraph as a sidecar or experimental output first,
   without immediately replacing existing WebObservedGraph/PDDL behavior.

4. Verify that the new model can represent the existing SauceDemo checkout
   path without storing concrete product details.

5. Only after the sidecar output is stable, migrate PDDL compilation toward the
   capability-transition representation.
```

This avoids replacing the current working MVP too early while giving the
project a clear path from SauceDemo-specific facts toward a reusable website
capability graph.
