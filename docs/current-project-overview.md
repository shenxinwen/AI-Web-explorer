# Current Project Overview

This is the active high-level handoff for the project. Module ownership lives in
`docs/project-structure.md`; decision rationale lives in
`docs/project-decisions.zh-CN.md`. Historical specs, plans, and experiments are
evolution records and do not override this document.

## Goal

The project is not a task-specific web agent. It openly explores a real website,
discovers basic functionality, and produces legal, reviewable PDDL that SafeSym
can parse and solve:

```text
open website exploration
  -> observe before/after action changes
  -> build a resumable WebKobeGraph
  -> separate locations, capability facts, and business facts
  -> generate Minimal Semantic PDDL
  -> validate and solve with SafeSym
```

The current acceptance goals are website exploration, valid SafeSym-facing PDDL,
and useful generality without turning exploration into a scripted task.

## Active Pipeline

The active runtime is location-scoped bounded open exploration:

```text
observe the current page
  -> let the VLM propose a small set of important actions
  -> create a candidate pool for the semantic location
  -> locally select an unfinished action for that location
  -> let Stagehand execute one action
  -> compare DOM, structured signature, and screenshots
  -> record a capability fact, business fact, or location transition
  -> run a targeted scan after business-fact changes
  -> create an initial pool when a new location is first reached
  -> reset and replay stored actions when another frontier must be restored
  -> stop under bounded limits and project Minimal Semantic PDDL
```

PDDL goals and SafeSym plans are not fed back into candidate generation or action
ranking. The semantic experiment profile constrains vocabulary, evidence, and
safety boundaries; it does not impose a fixed execution sequence.

## Planning State

The planner-facing model separates three kinds of state:

- **Location facts** such as `at_shopping`, `at_checkout`, and
  `at_confirmation`. A new location is created only for a meaningful business
  surface change.
- **Capability facts** such as `products_sorted`, `products_filtered`, and
  `products_found`. They describe verified site functionality and do not
  automatically become preconditions for other actions.
- **Business facts** such as `cart_has_items`, `checkout_info_complete`, and
  `order_submitted`. These may enable or constrain later actions.

Business preconditions come only from verified profile/structured facts.
Supporting facts, ordinary completion facts, and the complete active-fact set are
not automatically promoted into PDDL preconditions.

## Location-scoped Deduplication and Scanning

The deduplication key is `(semantic location, canonical action)`. A successful
action is not selected again at the same location, but the same action may still
be explored at a different location. Failure and no-change retries are bounded.

When an action does not change location, the current candidate pool is inherited.
A full candidate scan is reserved for the first visit to a new location. A
business-fact change triggers a targeted scan for newly enabled actions, and a
supplement scan is used only under bounded pool-exhaustion rules.

## Replay and Resume

Replay restores a frontier; it is not exploration:

```text
reset to the start URL
  -> execute the stored path
  -> validate the final semantic location and required business facts
  -> restore the temporary current-node pointer
  -> continue an unfinished candidate
```

Replay must not mutate nodes, edges, planning facts, candidate pools, scan state,
or candidate attempt counts. Checkpoints persist the graph, location memory,
cumulative formal-action budget, and replay metrics so interrupted experiments can
continue without clearing prior exploration.

## Bounded Termination

The current Practice Shopping feasibility defaults use 20 formal actions, three
consecutive no-progress attempts, two replay attempts per frontier, and four total
replays. Candidate retries are also bounded. These are parameterized
`ExplorationLimits`, not website semantics.

## PDDL Acceptance

Minimal Semantic PDDL preserves location and business state separately:

```lisp
(:action add_to_cart
  :precondition (and (at_shopping))
  :effect (and (at_shopping) (cart_has_items)))

(:action open_checkout
  :precondition (and (at_shopping) (cart_has_items))
  :effect (and
    (not (at_shopping))
    (at_checkout)
    (cart_has_items)))
```

`domain.pddl` contains explored and verified actions; `problem.pddl` contains the
initial location, initial business facts, and the requested goal. Sorting and
filtering may appear in the domain without appearing in the shortest checkout
plan. A location-only fallback remains available, but its projection report must
state why semantic projection was unavailable.

## Artifacts

A run can produce compact/raw graph artifacts, an evidence sidecar, Stagehand
traces, screenshots, location candidate memory, cumulative runtime state, a
SemanticPlanningGraph, projection reports, `domain.pddl`, `problem.pddl`, and a
SafeSym parse/solve report. The default experiment directory is a replaceable
`outputs/experiments/<site>/latest/`; historical runs are archived only when a
comparison is intentionally required.

## Generality and Known Hardcoding

The current system is accurately described as:

```text
generic exploration framework + optional domain/experiment profile
  + a few e-commerce structured shortcuts
```

The candidate pool, location-scoped deduplication, frontier replay, checkpoints,
runtime limits, semantic graph, and PDDL compiler are generic. The active open
exploration path does not hardcode a sort/filter/cart/checkout action sequence,
and the PDDL compiler has no branches for shopping-specific names.

Known hardcoded areas remain:

- the `practice_shopping_feasibility` vocabulary;
- structured `cart_count` / `item_count` to `cart_has_items` rules;
- the `cart_non_empty` state-summary marker;
- profile registration in the CLI/registry;
- the exact controlled PracticeAutomatedTesting URL used as the final-order
  safety boundary;
- the separate legacy e-commerce benchmark's guided checkout steps.

The vocabulary, fictional data, and controlled-order URL are experiment or safety
configuration. The main generalization debt is moving structured mappings such as
`cart_count -> cart_has_items` out of Explorer/Verifier code and into configurable
profiles, followed by external profile loading.

## Current Status and Next Step

As of 2026-08-13, the location-scoped implementation, resumable graph and budgets,
non-mutating replay, and offline Minimal Semantic PDDL acceptance path are merged.
The next step is one bounded real Practice Shopping experiment. It should inspect
candidate breadth and deduplication at `shopping`, verify `cart_has_items`, reach a
deeper checkout frontier through replay, and confirm that SafeSym can parse and
solve the resulting domain/problem.

## Related Documents

- `docs/project-structure.md`: active modules and data flow;
- `docs/project-decisions.zh-CN.md`: decision history;
- `docs/safesym-bridge.md`: SafeSym bridge usage;
- `docs/superpowers/specs/2026-08-12-location-capability-business-fact-pddl-acceptance-design.zh-CN.md`;
- `docs/superpowers/specs/2026-08-12-location-scoped-open-exploration-feasibility-design.zh-CN.md`;
- `docs/experiments/`: historical experiments and evidence.
