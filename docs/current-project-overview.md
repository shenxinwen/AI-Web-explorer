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
ranking, so exploration is not a fixed task script. The current implementation
does, however, pass the complete experiment-profile context to candidate scans
and Visual Delta. Because that context includes locations, facts, action examples,
and contracts, it can hint at expected capabilities even without prescribing an
execution order. This is now a documented generality limitation.

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
    (at_checkout)))
```

Under STRIPS frame semantics, `cart_has_items` persists unless an action removes
it; an already-true fact does not need to be emitted again as an effect.

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

## 2026-08-13 Live Feasibility Result

The active pipeline has now completed a real bounded Practice Shopping run:

- 11 formal actions were attempted under the 20-action cap, stopping normally
  after three consecutive no-progress attempts;
- the forward path reached checkout and confirmation without replay in this run;
- `cart_has_items`, `checkout_info_complete`, `payment_info_complete`, and
  `order_submitted` were verified;
- SemanticPlanningGraph, `domain.pddl`, and `problem.pddl` were generated;
- SafeSym parsing, safety-action injection, and Fast Downward solving succeeded.

This establishes an end-to-end feasible path, not a correct or complete learned
business model. Known issues exposed by the run are:

1. the visual result of `place_order` was also modeled as a separate
   `order_submitted` action, creating a planner shortcut around the form actions;
2. a visibly successful filter changed 10 products to 5, but Visual Delta put
   `products_filtered` in both added and removed candidates and omitted it from
   `completion_facts`, producing a no-effect PDDL action;
3. the closed profile currently acts as both terminology and capability hinting;
4. a no-profile SauceDemo smoke autonomously logged in with visible public test
   credentials, but named both login and inventory `swag_labs`, showing that
   cross-site execution generalizes better than open semantic induction.

The local evidence is under
`outputs/experiments/practice_automated_testing/latest/`.

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

Fictional data and exact controlled-order URLs remain experiment or safety
configuration. A layered vocabulary may remain as terminology, but sending the
complete vocabulary, action examples, and contracts into candidate discovery is
answer hinting. Generalization work must therefore separate open discovery from
after-action normalization in addition to externalizing structured shortcuts.

## Agreed Next-Stage Design (Not Implemented)

The next stage replaces answer-guided semantic validation with a smaller
VLM-observed action-dependency loop:

- candidate discovery sees the current page, not concrete profile facts,
  action contracts, an expected workflow, or the offline PDDL goal;
- one initial scan per new semantic location returns concrete actions and
  same-location `requires` links;
- the local candidate pool derives readiness from successful prerequisites and
  prioritizes executable dependency-chain actions;
- after-action observation returns only `outcome`, `location_change`, and short
  visible `evidence`;
- the local runtime, rather than the VLM, generates stable completion predicates
  for actions confirmed successful;
- only successful actions and successful dependency edges enter the
  planner-facing graph and PDDL;
- the new path bypasses profile-driven targeted scans, supplement scans, and the
  current multi-purpose Visual Delta fact schema.

This is an approved design, not current runtime behavior. The implementation and
acceptance details are in
`docs/superpowers/specs/2026-08-18-location-candidate-dependency-integration-design.zh-CN.md`.

## Current Status and Next Step

As of 2026-08-13, the location-scoped implementation, resumable graph and budgets,
non-mutating replay, live Practice Shopping exploration, Minimal Semantic PDDL,
and SafeSym solve path are established. The current phase has proven feasibility.
The next phase should not add a second website-specific answer profile first. It
should implement the minimal candidate-dependency loop on Practice Shopping,
then measure whether the explorer still discovers correct capabilities and
produces causal, solvable PDDL without the answer hints.

## Related Documents

- `docs/project-structure.md`: active modules and data flow;
- `docs/project-decisions.zh-CN.md`: decision history;
- `docs/safesym-bridge.md`: SafeSym bridge usage;
- `docs/superpowers/specs/2026-08-12-location-capability-business-fact-pddl-acceptance-design.zh-CN.md`;
- `docs/superpowers/specs/2026-08-12-location-scoped-open-exploration-feasibility-design.zh-CN.md`;
- `docs/experiments/`: historical experiments and evidence.
