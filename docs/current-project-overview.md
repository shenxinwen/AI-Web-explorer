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
  -> choose one action using graph memory / embedding memory / repetition penalty
  -> execute the action
  -> observe before/after business changes
  -> update node, edge, planning_state, and planning_transition
  -> generate or update PDDL/SafeSym artifacts
  -> continue or stop based on budget, repetition, frontier, or business coverage
```

Current objective status:

```text
real browser chain: established
graph/PDDL/SafeSym engineering chain: established
VLM visual delta: connected
business affordance generation: initial version exists
embedding memory: connected for similar-state lookup and repetition guidance
generated fact recording: graph layer records them, PDDL excludes them by default
ecommerce profile facts: first quality pass completed with product detail,
checkout required/complete, cart total, invoice, and availability facts
exploration responsibility boundary: VLM observes and proposes candidates,
local graph/embedding memory chooses and deduplicates, Stagehand executes only
the selected action; first prompt boundary fixes are implemented
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
local graph / embedding memory locates the current state, deduplicates actions,
and chooses one candidate
Stagehand executes exactly the selected action
VLM summarizes before/after visible business change
graph policy decides create / merge / revisit
PDDL projector consumes stored graph semantics deterministically
```

This means VLM should not decide whether an action was already tried, whether a
state is new, or whether a node should be created. It has no stable graph
memory. It should provide visible evidence, candidate business actions, and
before/after change summaries.

Action deduplication should be embedding-assisted, not only
`node_id + action_slug`. The intended query shape is:

```text
current state summary
  -> embedding match against existing nodes / state variants
  -> inspect tried business actions from similar nodes
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

## Main Problems

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

### P1: exploration does not yet have a real frontier

The system has business affordances and embedding memory, but not mature:

- candidate action ranking;
- tried-action memory;
- duplicate/no-op penalty;
- backtracking;
- coverage stop conditions.

It is closer to bounded single-path exploration than mature free exploration.
The next version should make embedding memory operational in selection and
revisit handling rather than leaving it as diagnostic metadata.

### P1: WebKobeExplorer has centralization risk

`WebKobeExplorer` coordinates observation, action choice, VLM, embedding,
source matching, edge construction, planning transition, and backtracking. It is
the current mainline core, but new exploration policy should not keep growing
inside `explore_one_step`.

### P2: graph still mixes business state and low-level UI structure

`interactable_elements`, selectors, and low-level action traces still exist in
the graph structure. Keep them short term for compatibility and debugging, but
the business graph should gradually center on:

```text
business_affordances + business_transition + planning_transition
```

### P2: verifier is missing

Facts currently come mostly from VLM candidates or lightweight structured rules.
A future verifier must decide which facts become planner-facing truth.

Short term, preserve provenance and evidence.

## Latest Experiment

The 2026-08-01 8-step run on Practice Automated Testing Shopping completed and
wrote:

```text
outputs/experiments/practice_automated_testing/latest/
```

High-signal result:

- 8 nodes and 8 edges were produced.
- The root `shopping` node stayed free of later cart/order facts, so the
  same-page incompatible-state split fixed the earlier pollution failure.
- `domain_only/domain.pddl` was generated without choosing a concrete
  `problem.pddl` goal.
- VLM produced both profile facts and one generated fact
  (`product_details_visible`), with provenance preserved.

Open problems from this run:

- Source matching previously mapped later actions back to an earlier `checkout`
  node. A lightweight current-node pointer and planning-fact compatibility
  guard now prevent this in tests, but the fix still needs a real-site rerun.
- Embedding summaries previously included repeated Stagehand policy/control
  boilerplate. Summary generation now prefers business labels for Stagehand
  business-intent controls, but real traces should be inspected again.
- Graph edge metadata still embeds large visual prompt/response traces. These
  should mostly live in trace artifacts, while graph should keep compact
  evidence and planner-relevant state.
- Low-value or already-covered actions such as `download_invoice_pdf` can still
  appear as planner actions.

## Next Priorities

1. Re-run the Practice Automated Testing Shopping experiment to validate the
   source-matching trajectory guard, cleaned embedding summaries, and updated
   ecommerce profile facts.
2. Re-run a bounded exploration experiment to validate that VLM candidates,
   embedding-assisted memory, and Stagehand business-intent execution follow
   the confirmed responsibility boundary.
3. Inspect whether checkout substeps now form a sequential chain rather than
   multiple edges fanning out from `checkout`.
4. Keep using domain-only projection as the primary exploration artifact;
   generate `problem.pddl` only for explicit smoke/query checks.
5. Reduce graph trace bloat by moving verbose prompts/responses to trace files
   and keeping graph evidence compact.
6. Discuss generated fact promotion / optional projection policy.
7. Revisit PDDL action naming and low-value action filtering after graph
   semantics are stable.
8. Once the graph layer stabilizes, refactor or detach `interactable_elements`
   and gradually split `WebKobeExplorer`.

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
