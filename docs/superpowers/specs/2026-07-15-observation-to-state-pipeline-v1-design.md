# Observation-to-State Pipeline v1 Design

Date: 2026-07-15

## Purpose

This design defines the next short-term module after grounded browser operation:
convert raw browser/DOM information into structured observations, typed state
facts, stable state signatures, and explainable deltas.

The long-term project goal remains:

```text
real website
-> structured observation
-> abstract state/action graph
-> planning model
-> SafeSym safety injection
-> safe action plan
```

This module serves the "structured observation -> abstract state/action graph"
part of that pipeline. It is not an HTML summarizer, not a general web agent,
and not an LLM-controlled fact extractor.

## Why This Module Comes Next

The project now has a better DOM-grounded operation loop: the agent can extract
candidates, execute browser actions, wait for page stability, and record traces.
The next bottleneck is state quality.

For SafeSym-facing planning, it is not enough to know that a click happened. The
system must know what changed, whether the change is stable, and which evidence
supports it.

The next short-term goal is therefore:

```text
raw DOM/browser page
-> PageStructureObservation
-> AbstractStateFact
-> StateSignature
-> typed observed delta
```

## Non-Goals

This stage must avoid scope drift.

Out of scope:

- LLM/VLM action selection.
- LLM/VLM deciding observed fact truth.
- Generic PDDL generation.
- Automatic sensitive-action classification.
- App-specific SauceDemo or ecommerce business rules.
- Storing full HTML/DOM dumps as planning state.
- Building a from-scratch general web agent.

## Long-Term Alignment

Each module should have a clear reason to exist in the SafeSym planning chain.

| Module | Short-term artifact | Long-term contribution | Must not become |
|---|---|---|---|
| Grounded operation | `BrowserAction` execution plus trace | Gives graph edges real browser evidence | LLM-driven browser autopilot |
| Page structure observation | Structured regions, controls, forms, indicators | Provides shared evidence for state, actions, LLM, and PDDL | Raw HTML summary |
| Abstract state facts | Typed, evidence-backed facts | Provides graph node and predicate material | Full DOM state dump |
| Delta inference | Typed before/after changes | Provides action-effect material | Unexplained diff log |
| Semantic assistor / LLM | Labels, rankings, explanations, hints | Improves semantic understanding | Fact source or selector generator |
| PDDL projector | Planning artifacts | Connects graph to SafeSym/planner | Browser explorer |
| SafeSym bridge | Safety injection/regression adapters | Produces safety-aware planning flow | Generic web operation layer |

## Layering

The intended layering is:

```text
Raw DOM / Browser
  -> PageStructureObservation
  -> AbstractStateFact[]
  -> StateSignature
  -> WebKobeGraph node/edge/delta
  -> PDDL / SafeSym projection
```

The same structure observation should support both state extraction and action
extraction. We should avoid two unrelated DOM scans that build incompatible
worldviews.

## PageStructureObservation v1

`PageStructureObservation` is the evidence-oriented page representation. It
answers:

```text
What structure is visible and operable on the page?
```

It should be generic and domain-neutral. It should not decide that something is
a cart, checkout, product, order, invoice, or admin task. It may preserve page
provided names such as `data-state="cart-count"` as evidence, but the observer
itself should classify that as a numeric indicator, not as ecommerce semantics.

Recommended top-level fields:

```text
page:
  url
  title

regions:
  id
  role
  label
  visible
  locator
  evidence

controls:
  id
  kind
  role
  name
  locator
  locator_strategy
  enabled
  visible
  metadata
  evidence

forms:
  id
  locator
  fields
  submit_controls
  evidence

indicators:
  id
  indicator_type
  key_hint
  value
  visible
  locator
  evidence

repeated_groups:
  id
  pattern_hint
  count
  representative_locator
  evidence
```

This schema is intentionally modest. It should give downstream code enough
typed material without pretending to understand every website.

## AbstractStateFact v1

`AbstractStateFact` is the planning-facing fact representation derived from
`PageStructureObservation`. It answers:

```text
What is currently true about the web environment?
```

Recommended fields:

```text
fact_id: stable string
fact_type: navigation | visibility | numeric | form_value |
           control_availability | selection | repeated_entity_count
value: scalar value
identity_role: identity | context | evidence_only
source_ref: reference to PageStructureObservation item
evidence: list of evidence records
```

Initial fact types:

- `navigation`: current URL, page title, route-like URL path.
- `visibility`: visible/hidden region or dialog/panel.
- `numeric`: numeric badge or indicator.
- `form_value`: current input/textarea value.
- `control_availability`: enabled/disabled visible control.
- `selection`: selected option or checked state.
- `repeated_entity_count`: count of repeated structural groups.

The fact system should preserve page hints, but not hard-code business meaning.
For example, `data-state="cart-count"` can become:

```text
fact_type = numeric
fact_id = data_state.cart_count
value = 1
source_ref = indicator from [data-state="cart-count"]
```

The generic observer should not contain a rule that means "cart count is an
ecommerce cart state." That interpretation belongs to a semantic layer.

## StateSignature Policy

`StateSignature` is the compact identity-facing subset of facts used by graph
nodes and deltas.

The key design rule:

```text
state identity = stable facts that affect available actions, action effects,
                 safety decisions, or goal progress
context/evidence = explanatory material that should not split graph nodes
```

Initial identity candidates:

- URL path or stable route-like URL.
- Visible dialog/panel/region facts.
- Numeric indicators with stable evidence.
- Selected options and form values when they affect subsequent actions.
- Repeated entity counts when they affect available choices.
- Control availability when it gates a meaningful action.

Initial non-identity candidates:

- Large text blocks.
- Full HTML or DOM snapshots.
- Hover/focus state.
- Timestamps.
- Pixel-level layout.
- Text that changes frequently but does not affect planning.

This policy is deliberately conservative. If a fact might cause graph explosion
without clear planning value, it should start as context rather than identity.

## Delta v1

`Delta` compares before/after `AbstractStateFact` values and records typed
changes.

Recommended delta types:

- `navigation_changed`
- `visibility_changed`
- `numeric_changed`
- `form_value_changed`
- `control_availability_changed`
- `selection_changed`
- `repeated_entity_count_changed`

Each delta should include:

```text
fact_id
fact_type
delta_type
before
after
source_ref
evidence
identity_relevant: bool
```

No-delta actions should not automatically be failures. They may be idempotent,
focus-only, externally effective, or outside the current observation schema.
They should be traceable.

## Relationship to LLM/VLM

LLM/VLM is a future consumer, not the fact source.

Allowed future use:

- Rank DOM-grounded candidate actions.
- Name page states and capabilities.
- Explain typed deltas.
- Suggest PDDL predicate/action hints.
- Flag actions that might be sensitive.

Disallowed:

- Invent selectors.
- Decide fact truth without browser evidence.
- Mutate graph structure implicitly.
- Replace DOM/browser observation.
- Bypass SafeSym constraints.

The intended LLM input is:

```text
PageStructureObservation
+ AbstractStateFact[]
+ candidate BrowserAction[]
+ typed Delta[]
```

not raw unbounded HTML.

## Anti-Overfitting Rules

To keep this module generic:

- Do not add generic observer rules for `cart`, `product`, `checkout`, `order`,
  `payment`, or other app-domain concepts.
- Prefer fact types such as `numeric`, `visibility`, `control_availability`,
  and `repeated_entity_count`.
- Preserve domain words only as page-provided hints or evidence.
- Validate on at least two fixtures from different domains.
- Keep SauceDemo-specific interpretation in `safesym_bridge` or app profiles.
- If a rule only helps one fixture, it is not generic enough for this layer.

## Validation Fixtures

Use at least two local fixtures:

1. Existing `tests/fixtures/local_shop`
   - repeated product-card-like structures;
   - numeric indicator;
   - region visibility change;
   - button controls.

2. New non-ecommerce fixture, recommended name:
   `tests/fixtures/local_form_search`
   - search input;
   - select or checkbox filter;
   - result count;
   - validation or status region;
   - enabled/disabled submit/control state.

The second fixture is important. It prevents the generic observer from silently
becoming an ecommerce observer.

## Acceptance Criteria

This stage is complete when:

- `grounded_web` can produce a structured page observation without depending on
  `safesym_bridge`.
- The observation contains generic regions, controls, indicators, forms, and
  repeated groups where present.
- Typed facts can be derived from the observation.
- A state signature can be built from identity-relevant facts.
- Before/after execution produces typed deltas with evidence.
- `local_shop` and a non-ecommerce fixture both pass smoke tests.
- Existing `tests/safesym_bridge` regressions do not fail.
- No new generic code in `grounded_web` imports `safesym_bridge`.

## Implementation Direction

A likely implementation sequence:

1. Add lightweight data models for page structure observation.
2. Extend or wrap existing `dom_observer` so controls and structure share one
   observation source.
3. Add typed fact derivation from page structure.
4. Add state signature selection policy.
5. Add typed delta inference.
6. Add `local_form_search` fixture.
7. Wire the typed facts/deltas into Web-KOBE graph recording without removing
   existing compatibility fields.

## Engineering Guidance

This work should remain boring and inspectable. The value is not that the system
"understands the web" immediately. The value is that it can produce structured,
evidence-backed facts that later modules can trust.

If a future LLM decision is wrong, this layer should make the mistake debuggable:

```text
What did the browser observe?
Which facts were derived?
Which action was chosen?
What changed after execution?
Which evidence supports that claim?
```

That is the foundation the SafeSym planning pipeline needs.
