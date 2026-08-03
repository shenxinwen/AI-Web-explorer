# Current Project Overview

This is the high-level project handoff. It records the current direction,
phase, main problems, and next priorities. Detailed module structure lives in
`docs/project-structure.md`; decision rationale lives in
`docs/project-decisions.zh-CN.md`. The Chinese version,
`docs/current-project-overview.zh-CN.md`, is for human review.

## One-line Goal

This project is not a general-purpose web-agent product. It is a SafeSym-facing
web exploration and planning-modeling system:

```text
real website interaction
  -> observe page and business-state changes before and after actions
  -> build WebKobeGraph
  -> abstract planner-facing states and actions
  -> project into PDDL
  -> let SafeSym parse, inject safety checks, and validate planning artifacts
```

The core problem is not making a model finish one website task. The core problem
is:

```text
turn real web interaction into a stable, reviewable, plannable state graph that
SafeSym can consume.
```

Stagehand, Playwright, VLM/LLM providers, and embeddings are tools or evidence
sources. Web-KOBE must own graph structure, state memory, PDDL semantics, and
exploration control.

## Current Phase

The project has completed the early end-to-end validation chain:

```text
real browser execution -> graph -> PDDL -> SafeSym smoke
```

It is now moving from the task-guided checkout baseline toward bounded
exploration V1. The current target is a minimal usable exploration loop:

```text
observe current state
  -> generate immediately executable business action candidates
  -> choose an untried business action using the current-node frontier, tried
     candidates, graph memory, and embedding memory
  -> execute the action
  -> observe before/after business changes
  -> update node, edge, planning_state, and planning_transition
  -> generate or update PDDL/SafeSym artifacts
  -> if the current node is exhausted, backtrack to an older node with frontier
  -> continue or stop based on budget, repetition, frontier, or business coverage
```

Current objective status:

```text
real browser chain: established
graph/PDDL/SafeSym engineering chain: established
VLM visual delta: connected
business affordance generation: initial version exists
embedding memory: connected for similar-state lookup and repetition guidance
target matching: initial version connected; post-action states can reuse
existing business nodes using embeddings plus planning-fact compatibility
source localization: normal exploration trusts the current-node pointer;
source embedding match is recovery/diagnostic only
frontier / DFS exploration policy: minimal business-affordance selector/backtrack
behavior is implemented; graph meta now emits frontier_metrics
consecutive unproductive stop policy: implemented; failed/no-op steps no
longer stop the run until the threshold is reached
Stagehand thinking/tool_choice errors: treated as non-fatal; no visible change
becomes no-op instead of a failed edge
generated fact recording: graph layer records them, PDDL excludes them by default
ecommerce profile facts: first quality pass completed with product detail,
checkout required/complete, cart total, invoice, and availability facts
exploration responsibility boundary: VLM observes and proposes candidates,
local graph/embedding memory chooses and deduplicates, Stagehand executes only
the selected action; first prompt/runner boundary fixes are implemented
domain-first projection: available through web-kobe-domain-from-graph
problem generation: diagnostic/query-stage only, requires explicit start/goal
free exploration strategy: not stable yet
profile fact verifier: not real yet
PDDL semantic quality: consumable, but not stable or readable enough
business node naming: materialized business nodes can derive labels from
profile hints / facts / actions
same-page state variants: split when planning facts are incompatible
latest 8-step real-site run: completed on Practice Automated Testing Shopping;
graph/domain improved; source matching now has a trajectory guard, but needs
real-site revalidation
```

Detailed pipeline and module ownership are recorded in
`docs/project-structure.md`.

## Current Architectural Judgments

### 1. WebKobeGraph is the active graph model

The old `WebObservedGraph` exploration stack has been removed from the active
source tree. The active exploration, PDDL, and SafeSym chain should use:

```text
WebKobeGraph
WebKobeNode
WebKobeEdge
PlanningState
PlanningTransition
BusinessAffordance
BusinessTransition
```

Historical `WebObservedGraph` designs remain only in old spec/plan documents.

### 2. Profile facts should have lower influence

Profile facts are not the complete set of possible web states. Their new
position is:

```text
candidate PDDL predicate vocabulary + preferred observation targets +
cross-site semantic alignment anchors
```

The graph can record both profile facts and generated facts. PDDL still
conservatively consumes profile facts by default. Generated fact promotion and
optional projection remain open design work.

Recent profile update: ecommerce checkout facts now distinguish required
checkout/payment information from completed information, and include common
product/order support states such as product details, cart totals, invoice
availability, and out-of-stock availability.

### 3. Exploration ownership must stay local

The current long-term exploration boundary is:

```text
VLM observes the current page and proposes business action candidates
local current-node pointer maintains source location
local graph / embedding memory handles target merge, recovery, and action
deduplication
Stagehand executes exactly the selected action
VLM summarizes before/after visible business change
graph policy decides create / merge / revisit
PDDL projector consumes stored graph semantics deterministically
```

This means VLM should not decide whether an action was already tried, whether a
state is new, or whether a node should be created. It has no stable graph
memory. It should provide visible evidence, candidate business actions, and
before/after change summaries.

Normal exploration should not use embeddings to relocalize the source on every
step. Source defaults to the target of the previous successful edge. If an
action creates a new node, move to it; if it matches an existing target node,
move there; if it produces no effective change, stay on the current node.
Source embedding match should be reserved for recovery cases such as browser
back, refresh, experiment resume, external navigation, or pointer/browser
desynchronization.

Action deduplication should not rely only on `node_id + action_slug`.
Embedding-assisted memory can still help query similar-node action history:

```text
current / target state summary
  -> embedding match against existing nodes / state variants
  -> inspect tried business actions or reusable target states from similar nodes
  -> downrank or skip repeated / low-value actions
```

Profile facts can help align planner-facing semantics, but they are not the
only exploration boundary. Generated facts may be recorded in graph memory while
remaining outside default PDDL projection.

### 4. Stagehand is the operation layer, not state truth

Stagehand can observe, propose candidates, execute actions, and provide traces.
It should not directly decide:

- node identity;
- planning facts;
- PDDL predicates/effects;
- safety triggers;
- exploration completion.

State truth should come from Web-KOBE before/after observations, VLM/structured
evidence, graph memory, and a future verifier.

In the preferred exploration loop, Stagehand should be treated as an action
executor. Its prompt should be closer to "execute this selected business action
and stop" than "explore the site and choose the next useful goal." Generic
Stagehand exploration prompts should only be fallback behavior.

### 5. PDDL projection should stay deterministic

The PDDL projector should consume graph semantics. It should not call LLM/VLM
directly and should not freely invent predicates.

Exploration should prioritize domain quality first. `domain.pddl` represents
the observed state/action model and can be generated without a concrete goal.
`problem.pddl` represents a specific planning query and should be produced only
for smoke tests, SafeSym checks, or user/task-selected start and goal states.

Current PDDL inputs are mainly:

```text
node location
node.planning_state.profile_fact_ids by default
edge.action.canonical_action_name
profile facts from edge.planning_transition pre/added/removed facts
```

Naming work is deferred. The intended boundary is that LLM/VLM may help produce
semantic labels during exploration, while the projector only normalizes and
projects stored graph semantics.

### 6. Graph quality starts with business-state uniqueness

Graph quality should not be judged only by whether nodes, edges, and PDDL are
generated. It must also preserve stable business-state identity:

- the same business state should have one node; for example, cart from home,
  product detail, or another page should resolve to the same cart node;
- edges can represent different source paths, but nodes should not duplicate
  the same state just because the source path differs;
- a new node must represent a meaningful business-state change; if
  `cart_has_items` is already true and item count changes are not modeled,
  adding the same item again should not create another business-state node;
- merge-before-create is the default policy; after an action, match the target
  state against existing nodes using planning facts, VLM state summary, and
  embeddings before materializing a new node;
- node labels must be semantically stable; many `at_product_details_002` or
  `at_shopping_003` predicates usually indicate weak merge or naming policy;
- every node and edge should be traceable to evidence such as VLM summaries,
  planning facts, screenshots, or structured observations.

### 7. Exploration policy should be frontier-first

The confirmed V1 exploration policy is simple DFS / frontier, not free-form
planning by Stagehand or VLM:

- each business node owns 3-5 immediately executable business affordances;
- local code marks candidates as untried, tried, no-op, or failed; VLM proposes
  candidates and evidence, but does not own memory;
- the current node prefers untried candidates; after execution, move to a new
  node, move to an accepted existing target node, or stay put if no effective
  change occurred;
- once a node has no untried candidates, do not repeat a successful non-avoid
  action; backtrack to an older node with frontier;
- stop on max steps, no frontier, repeated-state budget, consecutive no-op /
  failures, or an explicit terminal state.

Short term, tried/no-op/failed state is derived from existing edges. Do not add
a large memory table yet. The old selector/locator fallback has been removed;
the business-affordance selector no longer chooses already-tried successful
actions after a node's local candidates are exhausted. Successful browser back
now pops a lightweight visit stack and restores `_current_node_id`.
`graph.meta.frontier_metrics` records per-node candidates, tried/untried/no-op/
failed action ids, repeated target hits, and backtrack count. Full DFS recovery
can later use source embedding relocalization.

## Main Problems

### P0: identical business states do not merge reliably yet

The latest Practice Automated Testing Shopping 8-step run produced 6 nodes and
8 edges. The chain completed, but graph quality is still weak. Target matching
can reuse some existing nodes, but similar `product_details` / `product_list`
state variants still appear, and the PDDL still contains weak predicates such
as `at_product_details_002` and `at_product_list_002`.

This means embeddings already provide similar-state signals, but target-node
materialization and merge logic did not consume those signals strongly enough.
Target matching V1 is now connected: after an action, the target state is
matched against existing nodes using embeddings plus planning-fact
compatibility. If a match is accepted, the edge points to the existing node
instead of creating another state variant. The next real-site run must confirm
whether this reduces duplicate business nodes.

### P0: generated facts do not yet have a promotion strategy

The graph now records generated facts and preserves fact provenance in
`PlanningState.profile_fact_ids` / `PlanningState.generated_fact_ids`. The PDDL
projector excludes generated facts by default so unreviewed VLM facts do not
pollute SafeSym artifacts.

The remaining issue is policy: when should generated facts be promoted into
planner-facing facts, when should an experiment explicitly project them, and how
should a future verifier confirm them?

### P0: PDDL semantic quality is still unstable

SafeSym can structurally consume current artifacts, but PDDL quality is not
stable enough:

- location predicates may still degrade into names such as `at_shopping_002`;
- materialized business nodes now derive labels from profile-provided hints /
  facts / actions, but non-business nodes and repeated labels can still be weak;
- action preconditions depend on correct source-node localization;
- incomplete profile facts make PDDL degrade into a location path;
- generated facts are not projected by default, so real business states may be
  lost until a promotion/projection policy exists.

Recent fix: same-page states with incompatible planning facts are now split
into state variants instead of overwriting the existing page node. This reduces
the risk that a later state, such as `cart_has_items`, pollutes the exploration
start node.

### P1: exploration still needs frontier validation and refinement

The system has business affordances and embedding memory, but not mature:

- candidate action ranking;
- tried-action memory;
- duplicate/no-op penalty;
- backtracking;
- coverage stop conditions.

It is closer to bounded exploration V1 than mature free exploration. A previous
run cycled between product list and product details. The main cause was not
that VLM produced no candidates; it was that the old selector fell back to
"successful but non-avoid" actions after all local candidates had been tried,
so low-progress successful actions could repeat. The minimal fix is now in
place: if a node has no untried business candidates, selection returns `None`
and triggers browser back / visit-stack backtracking. The old LLM action
selector / OpenAI action selector modules have been deleted so exploration
cannot silently return to locator-driven behavior.

The controller now uses a consecutive-unproductive-step policy. A single
`failed_execution`, `no_observed_change`, or productive control backtrack does
not stop exploration. The run stops on max steps, terminal condition, no edge
with no productive control action, or `consecutive_unproductive_steps` reaching
the configured threshold. `graph.meta` records `last_step_kind`,
`last_step_status`, `consecutive_unproductive_steps`, and
`max_consecutive_unproductive_steps`.

Recent cleanup moved the generic Stagehand exploration default to
`observed_action`, preserves VLM candidate `expected_change` in graph
affordances, and removed global completed-action downranking from business
affordance selection. Repetition policy should now be based on the current or
embedding-matched node context.

Known `Thinking mode does not support this tool_choice` errors are
Stagehand/model-adapter exceptions and should not terminate experiments by
themselves. If no visible change occurs, the action should be recorded as
`no_observed_change`; local action memory can then avoid it and continue with
another candidate.

### P1: WebKobeExplorer has centralization risk

`WebKobeExplorer` coordinates observation, action choice, VLM, embedding,
source matching, edge construction, planning transition, and backtracking. It is
the current mainline core, but new exploration policy should not keep growing
inside `explore_one_step`.

### P2: graph still keeps low-level UI evidence fields

`interactable_elements` still exists on nodes as page evidence and debugging
data. It no longer owns action choice, action memory, or frontier state.
`mark_interactable_explored`, `interactables_for_node`, the old LLM action
selector modules, and their tests have been removed. The business graph should
gradually center on:

```text
business_affordances + business_transition + planning_transition
```

### P2: verifier is missing

Facts currently come mostly from VLM candidates or lightweight structured rules.
A future verifier must decide which facts become planner-facing truth.

Short term, preserve provenance and evidence.

## Latest Experiment

The latest 8-step run on Practice Automated Testing Shopping completed and
wrote:

```text
outputs/experiments/practice_automated_testing/latest/
```

High-signal result:

- 6 nodes and 8 edges were produced.
- The run completed all 8 steps after treating the known Stagehand
  `Thinking mode does not support this tool_choice` exception as non-fatal.
- Target matching accepted some repeated states, but the graph still produced
  duplicate-looking product list/detail state variants.
- `domain_only/domain.pddl` was generated without choosing a concrete
  `problem.pddl` goal.
- The run stayed around product list/detail and cart-related states; it did not
  progress reliably to checkout.

Open problems from this run:

- The old selector/locator fallback that could loop after exhausting local
  candidates has been removed. Next runs should verify that business-affordance
  selection now backtracks instead of repeating successful low-progress actions.
- Business action memory is derived from graph edges, not stored as explicit
  candidate status on each node; this is acceptable short term but needs a
  clearer frontier policy.
- Similar business states still produce duplicate-looking `at_*_002`
  predicates, so merge-before-create still needs real-site improvement.
- Graph edge metadata still embeds large visual prompt/response traces. These
  should mostly live in trace artifacts, while graph should keep compact
  evidence and planner-relevant state.
- Low-value or already-covered actions such as `download_invoice_pdf` can still
  appear as planner actions.

## Next Priorities

1. Re-run Practice Automated Testing Shopping and check whether the minimal
   frontier/DFS behavior escapes the product list/detail loop and reaches
   cart/checkout states.
2. Use `graph.meta.frontier_metrics` to inspect candidates per node,
   tried/untried/no-op/failed counts, backtracks, and repeated-node hits.
3. Check whether the default consecutive-unproductive threshold of 3 is too
   strict or too loose for real websites.
4. Continue validating target matching and keep source embeddings limited to
   recovery/diagnostic use.
5. Inspect graph and domain PDDL quality, especially source/target,
   preconditions/effects, node labels, and duplicate `at_*_002` predicates.
6. Discuss generated fact promotion / optional projection policy.
7. Once the graph layer stabilizes, decide whether `interactable_elements`
   should remain as compact evidence or move into trace artifacts, and
   gradually split `WebKobeExplorer`.

## Experiment Management

Keep only the latest valid output for each site:

```text
outputs/experiments/<site_name>/latest/
```

Each experiment report should record:

- command and models;
- prompt mode;
- execution mode;
- stop reason;
- graph node and edge counts;
- node merge / revisit behavior;
- embedding records and memory hits;
- final planning facts;
- generated facts;
- PDDL readiness;
- SafeSym consumability;
- anomalies and failed/no-op edges;
- screenshot-backed human-verifiable state changes;
- objective conclusion for structural chain, semantic chain, and exploration
  ability.

## Related Documents

```text
docs/project-structure.md
  Current pipeline, module boundaries, and major functions.

docs/project-structure.zh-CN.md
  Chinese version of the project structure document.

docs/project-decisions.zh-CN.md
  Project decision record. Update it after meaningful architecture, pipeline,
  data-structure, or mainline cleanup changes.

docs/safesym-bridge.md
  SafeSym bridge commands and experiment usage.

docs/current-project-overview.zh-CN.md
  Chinese version of this overview.
```
