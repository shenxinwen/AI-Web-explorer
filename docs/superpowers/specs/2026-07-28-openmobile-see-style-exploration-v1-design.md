# OpenMobile/SEE-Style Web Exploration V1 Design

## Purpose

The next phase should stop optimizing task-guided checkout prompts and begin
building a minimal website-exploration loop. The goal is not full autonomous
coverage. The goal is to prove that Web-KOBE can repeatedly explore useful site
functionality, record state transitions in `WebKobeGraph`, and keep the
graph-to-PDDL-to-SafeSym chain consumable.

This design follows the practical ideas from OpenMobile and SEE:

- maintain graph/memory from previous interactions;
- choose actions with awareness of explored states and repeated actions;
- prefer semantically useful functionality over raw click coverage;
- use the collected graph as the bridge to planning artifacts.

## Non-goals

- Do not replace the current graph model.
- Do not build a full crawler, replay engine, backtracking system, or coverage
  optimizer.
- Do not introduce a separate persistent memory database.
- Do not project DOM/UI/schema facts, screenshots, embeddings, or Stagehand
  text directly into PDDL.
- Do not require a website-specific schema of arbitrary variables and types.

## Architecture

The first version keeps the current architecture boundaries:

```text
Stagehand
  -> action observation and execution

Web-KOBE grounded_web
  -> state observation, profile facts, graph construction, exploration policy

SafeSym bridge
  -> graph-to-PDDL projection, PDDL smoke, SafeSym smoke
```

`WebKobeGraph` remains the only persistent memory. A new derived
`GraphExplorationIndex` may be introduced, but it is only a query/cache view
built from the graph and optional embedding sidecar data. It must not become a
second source of truth.

## Exploration Loop

Each step should follow one simple loop:

```text
observe current state
build current state summary
retrieve similar graph nodes by embedding
derive explored/tried/avoid action context from the graph
ask Stagehand for candidate useful actions, or ask it to execute one guided action
execute one action
observe after state
infer planning transition
record node/edge/update planning_state
project PDDL in smoke mode when requested
```

The loop should run with bounded limits such as `max_steps`, same-state revisit
limits, and no-progress limits.

## State Identity

V1 should use embeddings as the primary revisit detection mechanism, because
they are simple and general across websites.

For each node, create a compact `state_summary_text` from:

- normalized URL/path;
- page title;
- visible main regions;
- visible forms, dialogs, modals, and carts;
- main useful controls;
- active profile planning facts;
- short visual summary when available.

The embedding lookup can be linear for now because experiment graphs are small.
Approximate thresholds:

- `>= 0.90`: likely same/revisited state;
- `0.82-0.90`: ambiguous similar state, do not hard-merge automatically;
- `< 0.82`: likely new state.

Two minimal guards prevent obvious bad merges:

- conflicting profile planning facts should block automatic merge;
- materially different modal/form/cart context should block automatic merge.

Embeddings should preferably be stored outside `graph.json`, for example in a
sidecar file such as `state_embeddings.json`, to keep the graph readable.

## Action Selection

Stagehand can provide candidate actions and perform low-level interaction. The
project should still own the exploration policy.

Initial policy:

- prefer actions tied to site functionality;
- prefer actions likely to change business state or reveal a new functional
  area;
- lower the score for repeated actions from the same or similar state;
- lower the score for no-op, failed, external, footer/legal/social, theme, and
  language actions;
- execute one action per step;
- if the current state is recognized as already visited, include tried/avoid
  actions in the Stagehand instruction so it chooses a different direction.

This mirrors SEE's practical ranking idea without implementing a complex search
algorithm.

## Graph Recording

The existing graph semantics remain:

- `node` represents a revisitable page/context state;
- `node.planning_state` records known profile facts at that state;
- `edge` represents one executed action;
- `edge.planning_transition` records `pre_facts`, `added_facts`, and
  `removed_facts`;
- failed or no-change edges may be retained as negative evidence for V1.

The graph should record enough metadata to explain exploration decisions, but
PDDL projection should remain profile-only.

Useful exploration metadata can include:

- matched prior node id and similarity score;
- whether the action was repeated;
- whether the edge caused a new state, known-state revisit, no-op, or failure;
- why the action was chosen or downranked.

## PDDL Mapping

No new PDDL strategy is required for V1. The current strategy remains correct:

- locations come from graph nodes;
- action preconditions/effects come from `edge.planning_transition`;
- only preset profile facts are planner-facing facts;
- UI facts, DOM evidence, screenshots, embeddings, and Stagehand natural
  language remain evidence, not predicates.

This keeps exploration improvements decoupled from SafeSym projection.

## Error Handling

Stagehand execution anomalies should not automatically stop an experiment. If
the page or planning facts changed, record the edge as
`succeeded_with_observed_change` and preserve the anomaly metadata.

Stop the run when:

- browser navigation fails irrecoverably;
- observation cannot be produced;
- graph serialization or PDDL smoke fails;
- the loop exceeds configured revisit/no-progress limits;
- a real-world sensitive action boundary would be crossed without explicit
  permission.

## Testing

Implementation should be test-driven and start with unit tests for:

- state summary construction;
- embedding-based node matching with guard rules;
- graph-derived explored/tried/avoid action summaries;
- repeated/no-op action downranking;
- PDDL projection still excluding UI/schema/embedding facts.

Then add one small integration-style test with a fake Stagehand backend that
simulates:

```text
home -> product list -> cart -> checkout-like form
```

Real website experiments should remain manual/explicit because they depend on
network, model latency, and browser state.

## Success Criteria

V1 is successful when:

- a site can be explored for several steps without a task-specific checkout
  script;
- repeated actions are visibly reduced compared with the current flow;
- revisited states can be detected and used to guide Stagehand away from
  duplicate behavior;
- graph output remains readable and SafeSym-consumable;
- generated PDDL still uses only node identity and profile planning facts.

## First Implementation Slice

The first slice should be intentionally small:

1. Add state summary generation.
2. Add embedding-backed state matching with guard checks.
3. Add a graph-derived exploration index.
4. Add a Stagehand exploration prompt/context that includes tried and avoid
   actions.
5. Add CLI support for an exploration-style experiment mode.
6. Verify with fake backend tests before running real websites.

This gives the project an OpenMobile/SEE-like exploration chain without locking
it into an over-designed architecture.
