# Planner-Facing PDDL Projection Hardening Design

Date: 2026-07-23

## Context

The project serves SafeSym. Its value is not operating websites as a general web
agent, but turning real web interaction evidence into a WebKobeGraph and then
into PDDL artifacts that SafeSym can parse, safety-inject, and solve.

The latest SauceDemo Stagehand milestone experiment reached the checkout
completion page and produced PDDL artifacts that SafeSym could parse and
inject. However, Fast Downward solve failed. The investigation found two
projection-layer issues:

- planner action names can be duplicated because readable
  `canonical_action_name` values are used directly as PDDL action names;
- delete effects can remove facts that are not known to be true in the action
  precondition/source state, causing Fast Downward's translator to emit
  conditional effects that the current search configuration does not support.

The next stage should harden the WebKobeGraph-to-PDDL projection layer before
adding more websites or expanding the exploration layer.

## Goal

Make the latest SauceDemo WebKobeGraph project into clean planner-facing PDDL
that passes:

```text
web-kobe-pddl-smoke
SafeSym parser
SafeSym safety injection
Fast Downward base solve
Fast Downward safe solve
```

Safety action insertion is not required in this stage. It depends on later
alignment between projected action/fact semantics and SafeSym constraint rules.

## Non-Goals

This stage will not implement:

- a full planning fact verifier;
- parameterized product/order objects;
- generic profile auto-generation;
- broad cross-site benchmark expansion;
- mandatory SafeSym safety-action triggering;
- Stagehand operation-layer changes unless needed for regression wiring.

## Core Principle

Only project facts that help planning or safety.

A fact should enter PDDL only if it helps at least one of these:

1. the planner understand task progress;
2. the planner understand whether a business action is applicable;
3. SafeSym understand where safety checks may be needed.

DOM/control facts, selectors, URL fragments, screenshot summaries, and LLM
reasons are evidence. They should remain in graph metadata and should not enter
PDDL by default.

## PDDL Fact Policy

The projector should emit these predicate categories:

```text
at_<node_id>
  Graph location predicates. These remain the spine of the task graph.

profile planning facts
  Task-level facts from PlanningDelta, such as cart_nonempty,
  checkout_started, order_review_ready, and order_completed.
```

The projector should not default to emitting:

```text
observed_delta control_* facts
raw DOM selector facts
URL path facts
button/input visibility facts
VLM/LLM reason text
```

Those signals are still valuable evidence for observation, debugging, and later
verification, but they are not planner-facing truth.

## Profile Facts V1

The e-commerce checkout profile should remain lightweight and generic. Each fact
may have a short semantic description to help VLM/LLM normalization, but the
description must not mention SauceDemo-specific selectors, URLs, product names,
or button text.

Initial v1 fact set:

```text
logged_in
product_list_visible
cart_empty
cart_nonempty
cart_page_visible
checkout_started
required_info_missing
required_info_provided
order_review_ready
order_place_pending_sensitive
order_completed
error_visible
```

These facts are sufficient for the current checkout path and provide room for
SafeSym-facing semantics such as "a final commitment is pending" without
encoding site-specific UI details.

## Action Identity

Readable action names and PDDL action identity must be separated.

LLM-generated names may populate:

```text
BrowserAction.canonical_action_name
BrowserAction.action_label
```

They should not be used directly as unique PDDL action names.

The projector should generate stable unique action names from graph order or
edge identity plus a readable suffix, for example:

```text
edge_001_authenticate_user
edge_002_add_item_to_cart
edge_003_open_cart
edge_004_start_checkout
edge_005_submit_checkout_info
edge_006_complete_order
```

The numeric prefix provides uniqueness. The suffix provides reviewability. If
semantic naming fails, the projector can fall back to a sanitized edge/action
identifier while preserving uniqueness.

## Preconditions And Effects

Short-term projection remains STRIPS-oriented.

Each business edge projects to one action:

```text
precondition:
  at_<source_node>
  plus any planning facts that must be true to safely delete them

effect:
  not at_<source_node>
  at_<target_node>
  added profile planning facts
  conservative removed profile planning facts
```

Delete effects must be conservative:

- a removed fact may be emitted only when the source state or generated
  precondition establishes that the fact is true before the action;
- otherwise the removal stays in graph metadata and is not projected as a PDDL
  delete effect.

This avoids implicit conditional effects in Fast Downward's translation.

## Smoke And Diagnostics

`web-kobe-pddl-smoke` should report more than static predicate consistency.
New diagnostics should include:

```text
duplicate_action_names
projected_action_names
projected_fact_sources
unsafe_delete_effects
projected_planning_fact_count
projected_observed_fact_count
```

For this stage, `projected_observed_fact_count` should be zero in the clean
planner-facing mode.

The full acceptance smoke is:

```text
web-kobe-pddl-smoke
web-kobe-safesym-smoke --fast-downward <fast-downward.py>
```

Expected result:

```text
planning_ready: true
safesym_parse_ready: true
safety_injection_ready: true
base_plan_ready: true
safe_plan_ready: true
failure_reasons: []
```

## Data Flow

```text
WebKobeGraph
  -> projectable business edges
  -> unique planner action names
  -> at_node predicates
  -> profile planning facts from PlanningDelta
  -> conservative STRIPS effects
  -> domain.pddl / problem.pddl
  -> SafeSym parse/inject
  -> Fast Downward solve
```

Observed deltas stay available as evidence:

```text
observed_delta / DOM / screenshots / LLM reasons
  -> graph metadata
  -> future verifier evidence
  -> not default PDDL predicates
```

## Testing Strategy

Add focused unit tests around the projector:

- duplicate readable names still produce unique PDDL action names;
- observed/control deltas are not projected in clean planner-facing mode;
- planning delta facts are projected;
- unsafe delete effects are omitted or made safe through preconditions;
- generated PDDL contains no duplicate action names;
- PDDL smoke reports duplicate actions and unsafe deletes when present.

Then run integration smoke against the latest SauceDemo graph:

- PDDL smoke passes;
- SafeSym parser passes;
- SafeSym injection passes;
- Fast Downward base plan exists;
- Fast Downward safe plan exists.

## Documentation

Update both synchronized overview files after implementation:

```text
docs/current-project-overview.md
docs/current-project-overview.zh-CN.md
```

The docs should state the real current status:

- SafeSym parse/inject can consume the generated PDDL;
- the previous planner failure came from projection-layer issues;
- the new projector emits planner-facing facts, not raw DOM/control dumps;
- safety action insertion is deferred until rule/action/fact alignment.

## Open Decisions

The implementation may choose whether the clean planner-facing mode becomes the
default immediately or is first introduced behind a projector option. The
recommended direction is to make clean projection the default for new
WebKobeGraph PDDL smoke runs, while keeping a diagnostic path for observed
control facts if existing tests require it.
