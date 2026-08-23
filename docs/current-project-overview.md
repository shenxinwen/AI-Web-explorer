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
  -> let the VLM propose concrete actions and same-location requires
  -> create a candidate pool once for the semantic location
  -> locally select an unfinished action whose requirements succeeded
  -> let Stagehand execute one action
  -> observe outcome, location_change, and visible evidence
  -> record a location-scoped completion fact and optional location transition
  -> create an initial pool when a new location is first reached
  -> reset and replay stored actions when another frontier must be restored
  -> stop under bounded limits and project Minimal Semantic PDDL
```

PDDL goals and SafeSym plans are not fed back into candidate generation or action
ranking, so exploration is not a fixed task script. The active path does not pass
experiment-profile context or action contracts into candidate discovery. The
optional `BusinessFlowProfile` is used only by the local structured fact verifier
and planner-facing projection.

## Planning State

The planner-facing model separates three kinds of state:

- **Location facts** such as `at_shopping`, `at_checkout`, and
  `at_confirmation`. A new location is created only for a meaningful business
  surface change.
- **Completion facts** are generated locally for actions observed to succeed.
  They become another action's precondition only when that action explicitly
  listed the successful action in its same-location `requires`.
- **Business facts** such as `cart_has_items`, `checkout_info_complete`, and
  `order_submitted`. These may enable or constrain later actions.

The local verifier can consume structured facts from an optional
`BusinessFlowProfile`; there is no separate semantic experiment profile or
action-contract runtime path. Supporting or unrelated completion facts are not
promoted into PDDL preconditions.

## Location-scoped Deduplication and Scanning

The deduplication key is `(semantic location, canonical action)`. A successful
action is not selected again at the same location, but the same action may still
be explored at a different location. Failure and no-change retries are bounded.

When an action does not change location, the current candidate pool is inherited.
The active minimal path scans only on the first visit to a new location. It does
not trigger targeted or supplement scans; those remain legacy compatibility code.

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

The live Stagehand runner uses bounded candidate retries and a formal-action cap:

- the formal-action cap is experiment-specific; the latest SauceDemo run used 25;
- each candidate may be attempted at most twice, then it is marked failed and the
  scheduler moves to another candidate;
- the live runner does not use a global consecutive-no-progress threshold as an
  early stop condition;
- replay is limited to two attempts per frontier and four total attempts;
- exploration stops normally when all reachable candidates are exhausted.

These are parameterized `ExplorationLimits`, not website semantics.

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

## 2026-08-23 Current Execution, Replay, and Projection Status

The active path now carries an execution policy with two modes:

- `single_instance` executes only the first observed Stagehand action for a
  representative single-instance candidate, preventing repeated targets such as
  multiple add-to-cart controls from becoming repeated mutations;
- `composite` executes all actions returned by `observe` in order. The high-level
  action is eligible for the next outcome observation only after every required
  atomic action succeeds; one failure marks the high-level action as failed.

The policy is stored on `BrowserAction` and graph data and survives serialization,
resume, and semantic projection. The current experiment uses only these two modes;
batch execution is not active. The prompt describes the policy generically and does
not encode a SauceDemo-specific workflow.

The latest no-profile SauceDemo open-exploration run used GPT-4o, `observe_act`, a
25-step cap, and two attempts per candidate. It completed 13 formal actions, made
9 semantic-progress updates, performed no replay, and stopped with
`current_state_exhausted` before reaching the step cap. The trace confirmed two
observed/executed atomic actions for `enter_credentials`, one executed action out of
six observed add-to-cart targets under `single_instance`, and three observed/executed
atomic actions for `complete_checkout_information`.

At the checkout overview, the VLM returned both `cancel_checkout` and
`complete_checkout`; discovery-order scheduling selected cancel first, leaving the
finish action pending. This is a scheduling/goal-priority gap, not a composite-action
execution failure. No semantic experiment profile or action contract was enabled
in this run, so `cart_has_items` should not be treated as an active
`view_cart` prerequisite.

Replay remains reset-and-replay of the stored semantic path, not browser-session
snapshot restoration. A resume run made four replay attempts and all four failed
during action replay; no replay succeeded, and the current trace does not persist the
exact failed action ID. Replay is therefore implemented but not yet reliability-
accepted.

The same graph completed semantic projection with nine successful actions and five
semantic locations. Failed sort/filter edges were excluded. Without an explicit goal,
the run generated `domain.pddl` and a projection report but no `problem.pddl`; partial
planning over the explored subgraph is possible, but the graph does not yet contain a
complete checkout/order path.

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

- structured `cart_count` / `item_count` to `cart_has_items` rules;
- the `cart_non_empty` state-summary marker;
- the exact controlled PracticeAutomatedTesting URL used as the final-order
  safety boundary;
- the optional `ecommerce_checkout` BusinessFlowProfile fact vocabulary.

Fictional data and exact controlled-order URLs remain experiment or safety
configuration. A layered vocabulary may remain as terminology, but sending the
complete vocabulary, action examples, and contracts into candidate discovery is
answer hinting. Generalization work must therefore separate open discovery from
after-action normalization in addition to externalizing structured shortcuts.

## Current Minimal Action-Dependency Loop

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
- the new path does not invoke targeted or supplement scans; those mechanisms
  remain available for later experiments. Semantic experiment profiles and action
  contracts are no longer runtime dependencies.

This path is connected to the location-scoped runtime and has offline regression
coverage. A no-profile SauceDemo VLM run and semantic projection have now been
completed; a full no-answer-hints Practice Shopping planner acceptance is not yet the
current evidence. Implementation and acceptance details are in
`docs/superpowers/specs/2026-08-18-location-candidate-dependency-integration-design.zh-CN.md`.

## Current Status and Next Step

As of 2026-08-23, the location-scoped implementation, bounded candidate retries,
policy-aware Stagehand execution, resumable graph, and partial semantic projection
are established. The current phase has also demonstrated that composite actions can
be expanded while keeping the high-level action as the outcome-observation unit.
The remaining risks are scheduler priority for terminal actions, cross-location
business facts, and reliable reset-and-replay diagnostics. The next experiment should
address those gaps without adding a website-specific candidate script.

## Related Documents

- `docs/project-structure.md`: active modules and data flow;
- `docs/project-decisions.zh-CN.md`: decision history;
- `docs/safesym-bridge.md`: SafeSym bridge usage;
- `docs/superpowers/specs/2026-08-12-location-capability-business-fact-pddl-acceptance-design.zh-CN.md`;
- `docs/superpowers/specs/2026-08-12-location-scoped-open-exploration-feasibility-design.zh-CN.md`;
- `docs/experiments/`: historical experiments and evidence.
