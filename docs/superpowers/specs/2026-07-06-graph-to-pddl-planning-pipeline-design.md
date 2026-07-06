# Graph to PDDL Planning Pipeline Design

Date: 2026-07-06

## Goal

Build the first end-to-end planning path from the existing SauceDemo `WebObservedGraph` to Fast Downward.

The immediate target is not generic website exploration. The target is to prove that the bridge's graph structure can support SafeSym's safety-planning workflow:

```text
WebObservedGraph
  -> planning-enriched graph actions
  -> PDDL domain/problem
  -> SafeSym safety constraint injection
  -> Fast Downward plan
```

FSM export remains useful for compatibility and debugging, but this milestone should not depend on SafeSym's current `FSM -> PDDL` canonical builder.

## Why direct Graph -> PDDL

The current observed graph already contains the planning concepts we need:

- abstract page nodes;
- semantic actions;
- source and target pages;
- preconditions;
- effects;
- observed state variables.

SafeSym's core safety and planner steps consume PDDL. Its FSM layer is mainly a way to build that PDDL. Since our graph is becoming the main world model, it is reasonable to compile PDDL directly from the graph and keep FSM as a compatibility artifact.

This also avoids two current blockers in the FSM path:

1. The generated domain misses form-filling actions, so the planner cannot satisfy predicates such as `state_username_filled`.
2. The observed FSM path currently exposes a downstream symbol-normalization issue for numeric value `0`.

The direct compiler should produce a small, deterministic PDDL model that avoids these blockers.

## First implementation scope

The first version is SauceDemo-specific by design.

It should support this plan shape:

```text
login_fill_credentials
login_submit
product_add_to_cart
cart_open
cart_checkout_start
checkout_info_fill
checkout_info_submit
order_place_confirm
```

The exact planner output may contain additional SafeSym-injected check/support actions, but the unsafe business action `order_place_confirm` must be constrained by SafeSym's safety injection.

Do not implement these in this milestone:

- generic website PDDL compilation;
- LLM or embedding-based node merging;
- main `ExploreLoop` integration;
- automatic discovery of arbitrary form fields;
- rich numeric reasoning;
- screenshot, DOM, or trace evidence storage.

Those are later phases after the planning chain is proven.

## Data model assumptions

The input is the current `WebObservedGraph`:

```text
nodes:
  id
  state_schema
  observed_values
  last_state_snapshot

edges:
  source
  target
  semantic_action
  preconditions
  effects
```

The compiler should read the graph's planning-relevant subset only. Exploration-only fields such as `interactable_elements`, `instructions`, `target_observations`, and `visit_count` should not affect PDDL generation.

For this milestone, the compiler may add a small set of SauceDemo planner actions that were not directly observed as graph edges:

- `login_fill_credentials`
- `checkout_info_fill`

These are not browser-click navigation actions. They are symbolic planning actions that model the fact that a user or agent can fill required form fields before submitting.

## PDDL representation

Use a simple PDDL style that is easy to inspect and compatible with SafeSym's safety injector.

### Pages

Represent page location with an `at` predicate:

```lisp
(at login)
(at inventory)
(at cart)
(at checkout_info)
(at checkout_overview)
(at checkout_complete)
```

Each graph edge moves the `at` predicate from source page to target page.

### Boolean state

Boolean state variables become zero-argument predicates:

```text
$.is_logged_in        -> state_is_logged_in
$.username_filled     -> state_username_filled
$.password_filled     -> state_password_filled
$.checkout_info_filled -> state_checkout_info_filled
$.order_created       -> state_order_created
```

When a value is `true`, the predicate is present. When a value is `false`, the predicate is absent or removed with `not`.

### Cart count

Avoid value-specific numeric predicates in this milestone.

For planning, the important fact is whether the cart has at least one item. Therefore:

```text
$.cart_count > 0 -> state_cart_count_positive
$.cart_count = 0 -> not state_cart_count_positive
```

This avoids brittle numeric naming and is enough for the checkout flow.

## Generated actions

### Graph edge actions

Each graph edge becomes one PDDL action:

```text
source + semantic_action + target
```

The action's preconditions include:

- current page: `(at <source>)`;
- graph edge preconditions mapped into PDDL predicates.

The action's effects include:

- removing `(at <source>)`;
- adding `(at <target>)`;
- graph edge effects mapped into PDDL predicates.

If source and target are the same page, the action should keep the page location valid.

### Added form-fill actions

Add two symbolic actions:

```text
login_fill_credentials
```

Preconditions:

```text
(at login)
```

Effects:

```text
state_username_filled
state_password_filled
```

And:

```text
checkout_info_fill
```

Preconditions:

```text
(at checkout_info)
```

Effects:

```text
state_checkout_info_filled
```

These actions are needed because a planner cannot assume a form field has been filled unless an action makes that fact true.

## Problem file

The generated problem should start at the graph's start node:

```text
(at login)
```

The initial state should not assume credentials or checkout information are already filled. Those facts should be achieved by planner actions.

The goal should be:

```text
(and
  (at checkout_complete)
  (state_order_created)
)
```

This goal verifies both navigation completion and task completion.

## SafeSym safety injection

After generating raw PDDL, run SafeSym's safety compiler using `configs/constraint_rules.json`.

The compiler output should preserve action names that safety rules need to match. In particular:

```text
order_place_confirm
```

must remain recognizable so SafeSym can inject confirmation/check requirements before order placement.

Success should be judged on the safety-injected PDDL, not only the raw PDDL.

## CLI shape

Add a CLI path that can produce planning artifacts from the current graph.

Suggested command:

```text
python -m ai_web_explorer.safesym_bridge.cli pddl --output outputs/safesym_e2e/graph_pddl
```

Expected output:

```text
outputs/safesym_e2e/graph_pddl/domain.pddl
outputs/safesym_e2e/graph_pddl/problem.pddl
```

A later command may run SafeSym injection and Fast Downward automatically, but the first version can keep generation and external verification separate if that makes the implementation smaller.

## Testing strategy

Use test-driven development.

Required tests:

1. PDDL compiler emits page predicates and all expected actions.
2. Form-fill actions exist and make login/checkout submit actions reachable.
3. Cart count is represented as `state_cart_count_positive`, not as numeric value predicates.
4. Generated problem starts at `login`.
5. Generated problem goal requires `checkout_complete` and `state_order_created`.
6. CLI writes `domain.pddl` and `problem.pddl`.

Integration verification:

1. Generate graph-derived PDDL.
2. Run SafeSym safety injection with `constraint_rules.json`.
3. Run Fast Downward against the injected PDDL.
4. Confirm a plan is found.

## Success criteria

This milestone is complete only when:

- existing SafeSym bridge tests still pass;
- graph-derived `domain.pddl` and `problem.pddl` are generated;
- SafeSym safety injection succeeds;
- Fast Downward finds a plan from the safety-injected PDDL;
- the resulting plan includes the form-fill actions before their corresponding submit actions;
- `order_place_confirm` remains safety-constrained.

## Follow-up stages

After this milestone:

1. Generalize form-fill action generation from graph/interactable data.
2. Populate `interactable_elements` from observed pages.
3. Use graph state and interactables to guide further browser exploration.
4. Add abstract node merging with LLM or embedding support.
5. Integrate the graph pipeline into the main `ExploreLoop`.
