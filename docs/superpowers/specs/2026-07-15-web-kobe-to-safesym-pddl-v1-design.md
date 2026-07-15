# Web-KOBE to SafeSym PDDL v1 Design

## Goal

Build the first mainline projection from an explored `WebKobeGraph` into simple SafeSym-consumable PDDL artifacts.

This reconnects the current DOM-grounded Web-KOBE exploration path to the project's real objective:

```text
explore website
-> WebKobeGraph
-> domain.pddl / problem.pddl
-> SafeSym safety injection
-> planner
```

The project is not trying to become a full-featured general web agent. Web operation is now sufficient for the next milestone; the near-term focus is PDDL projection from observed graphs.

## Planning Model

Use standard classical planning separation:

- `domain.pddl` represents the observed transition model: predicates and actions derived from the graph.
- `problem.pddl` represents one concrete planning task: selected start state and selected goal state.

Do not precompute a graph path and export only that path in v1. The planner should choose a path from the action model. A graph path query may be useful later as a precheck or debug tool, but it is not the core export model.

## Existing Starting Point

The current file already exists:

```text
src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py
```

It can project a debug `WebKobeGraph` into simple PDDL using:

- node location predicates such as `at_listing_empty`;
- boolean state predicates;
- edge actions;
- boolean delta effects.

V1 should evolve this existing module rather than introduce a new compiler.

## Non-goals

This version will not:

- infer user tasks automatically;
- infer goal predicates automatically;
- infer sensitive actions automatically;
- run SafeSym or Fast Downward automatically;
- add LLM/VLM reasoning;
- add complete numeric PDDL fluents;
- export only a path subgraph;
- make claims about complete modeling of arbitrary websites.

The output remains model-bounded: SafeSym can reason only over the observed graph and the predicates/actions projected from it.

## Input and Output

### Input

Primary input:

```text
WebKobeGraph JSON
```

CLI arguments:

```text
--graph <path to WebKobeGraph JSON>
--output <directory for PDDL artifacts>
--goal-node <node id>
--start-node <node id, optional>
```

If `--start-node` is omitted, use `graph.start_node_id`.

### Output

```text
domain.pddl
problem.pddl
```

The generated files should be stable, readable, and simple STRIPS PDDL.

## Domain Projection

The domain represents the observed transition system.

### Predicates

Include:

1. one location predicate for every node:

```text
at_<node_id>
```

2. boolean facts:

```text
cart_panel_visible == true -> cart_panel_visible
```

3. numeric/count facts as positive predicates:

```text
cart_count > 0 -> cart_count_positive
cart_count == 0 -> not cart_count_positive
result_row_count > 0 -> result_row_count_positive
```

4. visibility facts remain ordinary booleans:

```text
checkout_panel_visible
```

Do not use PDDL numeric fluents in v1. Classical boolean projection is enough to validate the SafeSym chain.

### Actions

Project each successful `WebKobeEdge` into one PDDL action.

An edge is successful if:

```text
edge.execution_trace.success == true
edge.status in {"verified", "succeeded", "succeeded_with_observed_change"}
```

Exclude:

```text
failed_execution
no_observed_change
unexpected_change
```

Each action uses:

```text
action name = sanitized edge.action.semantic_id
precondition = at_<source_node_id>
effect =
  not at_<source_node_id>
  at_<target_node_id>
  projected observed_delta effects
```

If source and target are the same node, keeping `at_<target>` as an add effect is acceptable; deleting and re-adding the same atom is unnecessary but harmless if the implementation avoids duplicates.

### Delta Effects

Project observed deltas conservatively:

- boolean `after=True` adds predicate;
- boolean `after=False` deletes predicate;
- numeric `before <= 0` and `after > 0` adds `<field>_positive`;
- numeric `before > 0` and `after <= 0` deletes `<field>_positive`;
- numeric positive-to-positive changes do not need a PDDL effect in v1;
- string/text changes are ignored unless they are already represented by a boolean/count fact.

This keeps the model simple and planner-compatible.

## Problem Projection

The problem represents a concrete planning query over the observed model.

### Initial State

Include:

```text
at_<start_node_id>
```

plus predicates derived from the start node's `last_state_snapshot`:

- true boolean facts;
- positive numeric/count facts.

### Goal

V1 supports node goals:

```text
at_<goal_node_id>
```

Do not add automatic goal predicate inference in v1.

Later versions may support:

```text
--goal-predicate order_created
```

but this is not required now.

## Graph JSON Loading

Add a minimal loader that reads `WebKobeGraph.to_dict()` JSON and reconstructs enough `WebKobeGraph` objects for projection.

The loader only needs fields required by the projector:

- graph app;
- start node id;
- nodes:
  - node id;
  - page frame basics;
  - state schema;
  - last state snapshot;
- edges:
  - source node id;
  - target node id;
  - action semantic id/action kind/locator/input values/description;
  - observed deltas;
  - execution trace success/error;
  - status.

It does not need to reconstruct every optional evidence object perfectly. Evidence can be preserved where straightforward, but PDDL projection should not depend on it.

## CLI

Add a formal command:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-pddl-from-graph \
  --graph outputs/web_kobe_explored_graph.json \
  --output outputs/web_kobe_pddl \
  --goal-node <goal_node_id> \
  [--start-node <start_node_id>]
```

Keep the existing `web-kobe-pddl` debug command.

The new command should:

1. read a Web-KOBE graph JSON;
2. validate that the selected start and goal nodes exist;
3. compile PDDL;
4. write `domain.pddl` and `problem.pddl`.

Missing start/goal nodes should return a clear `ValueError` and CLI exit code `1`, matching existing CLI error handling.

## Testing Strategy

Add or extend tests for:

1. boolean delta projection;
2. numeric/count positive predicate projection;
3. failed/no-change/unexpected edges excluded from domain actions;
4. custom start node in problem init;
5. missing goal node raises `ValueError`;
6. JSON graph loader can read `WebKobeGraph.to_dict()` output;
7. CLI `web-kobe-pddl-from-graph` writes `domain.pddl` and `problem.pddl`.

Do not run SafeSym/Fast Downward in unit tests. Unit tests should verify stable PDDL output structure and CLI file generation.

## Acceptance Criteria

- Existing `compile_web_kobe_graph_to_pddl()` supports boolean and positive numeric/count predicates.
- Failed/no-change/unexpected edges are not projected as actions.
- A graph JSON can be loaded and compiled to PDDL.
- CLI can generate PDDL from an explored WebKobeGraph JSON.
- `problem.pddl` uses explicit start/goal node selection.
- Existing `tests/safesym_bridge` pass.
- `current-project-overview.md` and `current-project-overview.zh-CN.md` are updated to state that the next mainline is WebKobeGraph-to-PDDL projection for SafeSym.
