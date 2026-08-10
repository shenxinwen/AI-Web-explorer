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

## Current Mainline

```text
VLM proposes possible business actions
  -> local graph/embedding memory selects one candidate and deduplicates it
  -> Stagehand attempts the selected action
  -> after-action observation verifies the visible result
  -> local verifier confirms known profile boundaries
  -> Raw Graph preserves stable observations and auditable outcomes
  -> planning abstraction groups only strongly supported equivalents
  -> Planning Graph aggregates candidate capabilities with exact provenance
  -> Phase A emits cross-planning-state business transitions into domain.pddl
```

A VLM affordance is a candidate hypothesis, not a verified capability.
Stagehand reports an execution attempt, not a state transition. After-action
observation is the evidence used to classify the raw edge as an observed
transition, no-op, or failure. Planning groups may aggregate candidate
capabilities, but only observed successful edges verify transitions.

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
  -> update raw node and edge evidence
  -> checkpoint completed artifacts
  -> run planning abstraction and Phase A offline
  -> stop with `current_state_exhausted` when the current node has no candidate
  -> otherwise continue until the configured maximum step count
```

Current objective status:

```text
real browser chain: established
graph/PDDL/SafeSym engineering chain: established
VLM visual delta: connected; it only observes `candidate_added_facts` /
`candidate_removed_facts`
business affordance generation: initial version exists
embedding memory: connected for similar-state lookup and repetition guidance
target matching: initial version connected; post-action states can reuse
existing business nodes using embedding similarity and reliable local revisit
evidence; state summaries may include locally verified planning context, but it
is not an independent veto or decision gate;
explicit URL/signature/visual changes cannot merge the candidate back to the
source, while reliable non-source history may still be reused
source localization: normal exploration trusts the current-node pointer;
source embedding match is recovery/diagnostic only
forward-only frontier policy: the current node consumes its fixed first-visit
candidates and stops when they are exhausted; graph meta emits frontier_metrics
planning abstraction: implemented and covered by unit tests, but not yet
validated by a new real-browser experiment
consecutive unproductive stop policy: retained as an optional generic-controller
mechanism, but disabled by the real Stagehand runner
checkpoint persistence: after every completed action, latest embedding, trace,
graph, and evidence artifacts are refreshed; normal completion writes
`graph.meta.exploration_summary`
Stagehand thinking/tool_choice errors: continue after-state observation; a
change is a successful transition, no change is `no_observed_change`, and
unknown failures remain failed self-loops without Visual Delta
visual observations: retained only in
`execution_trace.metadata.visual_delta_trace`; excluded from `PlanningState`,
planning transitions, target-matching planning facts, and Phase A PDDL
Phase A domain: projects canonical locations and eligible non-self-loop
business transitions only
Visual Delta taxonomy: bounded categories are implemented, but their quality
and final taxonomy remain a pending review topic
ecommerce profile facts: first quality pass completed with product detail,
checkout required/complete, cart total, invoice, and availability facts
exploration responsibility boundary: VLM observes and proposes candidates,
local graph/embedding memory chooses and deduplicates, Stagehand attempts only
the selected action, and after-action observation verifies the outcome
domain-first projection: available through web-kobe-domain-from-graph
problem generation: diagnostic/query-stage only, requires explicit start/goal
free exploration strategy: not stable yet
profile fact verifier: minimal deterministic verifier connected; it only
confirms profile facts from local structured signatures
PDDL semantic quality: consumable, but not stable or readable enough
business node naming: new state labels are optional VLM suggestions and are
locally cleaned; labels do not define identity or matching
previous real-site runs: historical evidence only; the latest controlled
conclusion still needs revalidation
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
```

Historical `WebObservedGraph` designs remain only in old spec/plan documents.
Historical `BusinessTransition` JSON keys remain load-compatible, but the
runtime model and VLM judgment path have been removed.

### 2. Profile facts should have lower influence

Profile facts are not the complete set of possible web states. Their new
position is:

```text
candidate PDDL predicate vocabulary + preferred observation targets +
cross-site semantic alignment anchors
```

The graph remains load-compatible with historical profile/generated facts, but
new Visual Delta observations stay in raw edge traces rather than becoming
planning facts. Only locally verified facts enter planning/profile state;
promotion of visual observations requires a separate review policy.

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
Stagehand attempts exactly the selected action
after-action observation summarizes the visible business change
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
only exploration boundary. Visual observations remain isolated from planning
state and are not used as Phase A predicates, preconditions, or effects.

### 4. Stagehand is the operation layer, not state truth

Stagehand attempts the selected action and provides an execution trace. It does
not own candidate generation or state truth, and should not directly decide:

- node identity;
- planning facts;
- PDDL predicates/effects;
- safety triggers;
- exploration completion.

State truth should come from Web-KOBE before/after observations, VLM/structured
evidence, graph memory, and a future verifier.

The known `Thinking mode does not support this tool_choice` error is not enough
to conclude that the browser action did not happen. The explorer continues
after-state observation: URL/signature/visual change records a successful
transition, while no change records `no_observed_change` and preserves the
original error with `backend_reported_success=false`. Unknown execution errors
remain failed self-loops and skip Visual Delta.

In the preferred exploration loop, Stagehand should be treated as an action
executor. Its prompt should be closer to "execute this selected business action
and stop" than "explore the site and choose the next useful goal." Generic
Stagehand exploration prompts should only be fallback behavior.

### 5. PDDL projection should stay deterministic

The PDDL projector should consume the planning graph. It should not call
LLM/VLM directly and should not freely invent predicates.

Exploration should prioritize domain quality first. `domain.pddl` represents
the observed state/action model and can be generated without a concrete goal.
`problem.pddl` represents a specific planning query and should be produced only
for smoke tests, SafeSym checks, or user/task-selected start and goal states.

Planning abstraction produces `planning_graph.json` and
`planning_abstraction_report.json` from the Raw Graph. Phase A then consumes
the planning graph. Its relevant inputs are mainly:

```text
planning-group location
planning-group business affordances and observed capabilities
eligible non-self-loop edge action names
```

Naming work is deferred. The intended boundary is that LLM/VLM may help produce
semantic labels during exploration, while the projector only normalizes and
projects stored graph semantics. Phase A projects canonical locations and
eligible non-self-loop business transitions into `domain.pddl`; supporting
facts, `PlanningState`, profile facts, and Visual Delta observations are not
Phase A preconditions or effects.

### 6. Graph quality separates Raw observation identity from Planning-state identity

Graph quality should not be judged only by whether nodes, edges, and PDDL are
generated. It must preserve the distinction between two identities:

- Raw Graph identity prioritizes faithful observation. A clear, stable,
  observable URL/signature/visual change may therefore materialize a raw
  observation node even when the business interpretation is unchanged;
- Planning-state identity prioritizes semantic uniqueness. Planning abstraction
  may group presentation-equivalent observations with provenance, so a cart
  count change from 1 to 2 can remain a Raw Graph node while usually mapping to
  the same planning state when `cart_has_items` remains true and quantity is not
  modeled;
- embedding target matching must not override an explicit observation change
  by merging the candidate back to its source. Reliable non-source revisit
  evidence may reuse an existing historical raw observation;
- edges can represent different source paths, while Planning Graph groups
  represent the semantic state identity used for planning;
- node labels must be semantically stable; many `at_product_details_002` or
  `at_shopping_003` predicates usually indicate weak planning-group or naming
  policy;
- every node and edge should be traceable to evidence such as VLM summaries,
  planning facts, screenshots, or structured observations.

### 7. Exploration policy should be frontier-first

The confirmed V1 exploration policy is a simple forward-only frontier, not
free-form planning by Stagehand or VLM:

- each Raw observation node receives no more than the configured candidate limit
  when its business candidates are first generated. The limit is an upper bound,
  not a quota: fewer candidates or an empty list is valid, and revisits / target
  merges do not regenerate or append candidates to that node;
- local code marks candidates as untried, tried, no-op, or failed; VLM proposes
  candidates and evidence, but does not own memory;
- the current node prefers untried candidates; after execution, materialize a
  new Raw observation node for an explicit observed change, reuse an accepted
  existing historical raw observation, or stay put if no effective change
  occurred. Planning abstraction may group those Raw observations later;
- once the current node has no untried candidates, record
  `current_state_exhausted` and stop instead of repeating an older action;
- use the configured maximum step count as the main real-run limit. The generic
  controller retains an optional consecutive-unproductive threshold, but the
  real Stagehand runner currently disables it.

Short term, tried/no-op/failed state is derived from existing edges. Do not add
a large memory table yet. The old selector/locator fallback has been removed;
the business-affordance selector no longer chooses already-tried successful
actions after a node's local candidates are exhausted. Browser-back recovery is
not part of the current loop. `graph.meta.frontier_metrics` records per-node
candidates, tried/untried/no-op/failed action ids, and repeated target hits.
Replay and broader frontier recovery remain later work.

## Main Problems

### P0: planning abstraction and target matching still need real-browser validation

Previous Practice Automated Testing Shopping runs produced duplicate-looking
page/business state variants. Those historical results are not the current
latest conclusion; graph merge quality still needs a new controlled run.

Planning abstraction and target matching are implemented and covered by unit
tests, but no new real-browser experiment has validated their behavior together.
Target matching V1 is connected: after an action, the target state is
matched against existing nodes using embedding similarity and reliable local
revisit evidence. State summaries may include locally verified planning
context, but it is not an independent veto or decision gate. If a match is
accepted, the edge points to the existing node instead of creating another
state variant. The next real-site run must confirm whether this reduces
duplicate business nodes.

### P0: visual observations remain separate from planning state

Visual Delta facts are retained as reviewable raw edge evidence in
`execution_trace.metadata.visual_delta_trace`. They do not enter
`PlanningState`, planning transitions, target-matching planning facts, or Phase
A PDDL.

If visual observations should later become planner-facing facts, verification,
promotion, and projection must be designed separately.

### P0: PDDL semantic quality is still unstable

SafeSym can structurally consume current artifacts, but PDDL quality is not
stable enough:

- location predicates may still degrade into names such as `at_shopping_002`;
- materialized business nodes now derive labels from profile-provided hints /
  facts / actions, but non-business nodes and repeated labels can still be weak;
- action preconditions depend on correct source-node localization;
- Phase A intentionally remains a location-level skeleton; a future richer
  business-fact projection would be limited by verifier and profile coverage;
- Phase A currently projects only canonical locations and eligible non-self-loop
  business transitions; Visual Delta facts do not enter `domain.pddl`.

### P1: exploration still needs frontier validation and refinement

The system has candidate business affordances, local tried-action memory,
semantic action deduplication, and embedding memory, but it still lacks mature:

- candidate ranking and richer duplicate/no-op penalties;
- replay or browser-back recovery;
- coverage stop conditions.

It is closer to bounded exploration V1 than mature free exploration. A previous
run cycled between product list and product details. The main cause was not
that VLM produced no candidates; it was that the old selector fell back to
"successful but non-avoid" actions after all local candidates had been tried,
so low-progress successful actions could repeat. The minimal fix is now in
place: if a node has no untried business candidates, selection returns `None`
and the run ends with `current_state_exhausted`. The old LLM action
selector / OpenAI action selector modules have been deleted so exploration
cannot silently return to locator-driven behavior.

The generic controller still tracks consecutive unproductive steps and can use
the configured threshold. The real Stagehand runner disables that early stop:
it continues through failed/no-op/repeated steps until the maximum step count or
current-state exhaustion. Each completed action writes a latest checkpoint;
normal completion adds `graph.meta.exploration_summary` with requested steps,
completed steps, and stop reason. Checkpointing does not provide resume, replay,
or per-step artifact history.

Recent cleanup moved the generic Stagehand exploration default to
`observed_action`, preserves VLM candidate `supporting_facts` in graph
affordances, and removed global completed-action downranking from business
affordance selection. Repetition policy should now be based on the current or
embedding-matched node context.

Known `Thinking mode does not support this tool_choice` errors are
Stagehand/model-adapter exceptions and should trigger continued after-state
observation. A URL/signature/visual change records a successful transition; no
change records `no_observed_change`. Unknown failures remain failed self-loops
and do not call Visual Delta.

`BusinessAffordance.action_name`, `label`, and `target_hint` have partial
semantic overlap and remain a deferred schema-review item.

### P1: WebKobeExplorer has centralization risk

`WebKobeExplorer` coordinates observation, action choice, VLM, embedding,
source matching, edge construction, and planning transition. It is
the current mainline core, but new exploration policy should not keep growing
inside `explore_one_step`.

### P2: low-level UI evidence is out of the compact raw graph

Low-level DOM interactables may still be used at runtime as state summary /
embedding-matching input, but they are no longer emitted in compact
`graph.json` nodes. They do not own action choice, action memory, or frontier state.
`mark_interactable_explored`, `interactables_for_node`, the old LLM action
selector modules, and their tests have been removed. The business graph should
gradually center on:

```text
business_affordances + raw observed edges + planning_transition
```

### P2: verifier coverage is still limited

The local structured verifier can confirm a small set of profile boundaries,
but its coverage remains limited. VLM candidate facts stay observation-only;
promotion to planner-facing truth still requires an explicit local rule or
review process.

Short term, preserve provenance and evidence.

## Historical Experiment Context

A previous Practice Automated Testing Shopping run produced graph, embedding,
trace, screenshot, and domain artifacts under:

```text
outputs/experiments/practice_automated_testing/latest/
```

Those artifacts are historical evidence, not proof of the current checkpointed
runner. They still show the important unresolved quality problem: similar
business states can become duplicate-looking graph/PDDL locations. The next
controlled run should validate the current forward-only stop behavior,
checkpoint persistence, and target matching before drawing new conclusions.

## Next Priorities

1. Re-run Practice Automated Testing Shopping under controlled conditions and
   verify forward-only exhaustion, maximum-step behavior, checkpoint persistence,
   and progress toward cart/checkout states.
2. Use `graph.meta.frontier_metrics` to inspect candidates per node,
   tried/untried/no-op/failed counts, repeated-node hits, and stop reason.
3. Evaluate the generic controller's default consecutive-unproductive threshold
   separately; the real Stagehand runner does not currently use it.
4. Continue validating target matching and keep source embeddings limited to
   recovery/diagnostic use.
5. Inspect graph and domain PDDL quality, especially source/target,
   preconditions/effects, node labels, and duplicate `at_*_002` predicates.
6. Discuss promotion / optional projection policy for locally verified
   planner-facing facts.
7. Decide whether runtime DOM interactables should move into trace/debug
   artifacts or be removed from mainline state matching, and gradually split
   `WebKobeExplorer`.

## Experiment Management

By default, each run overwrites the latest output for its site:

```text
outputs/experiments/<site_name>/latest/
```

Copy results elsewhere only when explicitly archiving an experiment.

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
