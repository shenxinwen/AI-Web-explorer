# Compact Graph and Evidence Sidecar Design

## Goal

Make `graph.json` the small, readable, planner-facing exploration record while
preserving verbose execution and observation evidence in a separate
`graph_evidence.json` sidecar.

This change is limited to artifact serialization and loading. It does not
change exploration, node matching, action selection, state naming, Phase A
semantics, or PDDL projection.

## Artifacts

Each experiment directory contains:

```text
graph.json
graph_evidence.json
state_embeddings.json
screenshots/
```

`graph.json` is the primary graph consumed by review tools and Phase A.
`graph_evidence.json` is optional diagnostic evidence. Screenshots and
embeddings remain separate existing artifacts.

## Compact Graph

The compact graph preserves all information needed to understand graph
topology, choose unexplored local actions, derive frontier metrics, and run
Phase A projection.

### Node content

Keep:

- `node_id`;
- `node_label` and one short state description;
- the page URL, title, page type, and compact state signature/snapshot;
- frozen `business_affordances`;
- non-empty planner-facing state;
- node status and a compact `evidence_ref` when verbose evidence exists.

Do not inline:

- repeated page-frame and node evidence arrays;
- DOM/accessibility dumps;
- screenshot details already represented by screenshot artifacts;
- empty planning objects, empty arrays, empty dictionaries, and null optional
  values that have defined loader defaults.

The current state naming is preserved in this change. Improving names such as
`shopping_002` is a separate follow-up.

### Edge content

Keep:

- stable edge identity;
- `source_node_id`, canonical business action, and `target_node_id`;
- action label, target hint, and local `supporting_facts` when present;
- final edge status and visit count;
- compact execution outcome needed by eligibility checks;
- non-empty planning transition data;
- `evidence_ref` when verbose evidence exists.

Do not inline:

- duplicated instruction and action description text;
- duplicated semantic and canonical action names when they are equal;
- full `observed_delta` control lists;
- full Stagehand result, reasoning, aria tree, XPath, and provider metadata;
- full visual-delta prompt and raw response;
- repeated URL evidence;
- empty planning/business transition structures.

## Evidence Sidecar

Use one `graph_evidence.json` file rather than one file per node or edge. Its
top-level shape is:

```json
{
  "schema_version": "web-kobe-graph-evidence-v1",
  "nodes": {
    "node-evidence:<node_id>": {}
  },
  "edges": {
    "edge-evidence:<edge_id>": {}
  }
}
```

The compact graph stores these stable keys in `evidence_ref`. A node entry may
contain verbose page/node evidence. An edge entry may contain the original
instruction, full action description, observed/schema delta, complete
execution trace metadata, full visual-delta response, and repeated evidence.

The sidecar is diagnostic only. Phase A and PDDL must never require it.

Concrete product names or transient visual facts may remain in the sidecar as
raw evidence, but they must not be promoted into compact graph state,
PlanningState, or Phase A PDDL.

## Loading and Compatibility

The graph loader must accept:

1. historical full graph JSON;
2. new compact graph JSON without a sidecar;
3. new compact graph JSON with a sidecar available to diagnostic tooling.

Missing optional fields use existing dataclass defaults. Where an existing
dataclass requires a compact execution value, the compact graph retains that
value rather than requiring evidence hydration.

Loading a compact graph for Phase A must not hydrate the evidence sidecar.
Existing historical experiments must remain projectable without migration.

## Writer Boundary

Do not change `WebKobeNode`, `WebKobeEdge`, or `WebKobeGraph` persisted domain
semantics merely to support file layout. Add a focused artifact writer that
derives compact graph and sidecar dictionaries from the in-memory graph.

The generic Stagehand experiment runner writes both files. Phase A output may
continue to call its input copy `raw_graph.json`, but that copy is the compact
primary graph supplied as input; it must not re-inline the sidecar.

## Failure Handling

- Failure to write either file must fail the artifact write; do not leave a
  compact graph that references a missing sidecar as a successful output.
- A compact graph without `evidence_ref` remains valid.
- A missing sidecar does not block Phase A.
- A dangling `evidence_ref` is reported by diagnostic validation but does not
  change graph topology or PDDL semantics.

## Tests

Add tests that prove:

- verbose edge metadata and observed deltas move to the sidecar;
- compact graph retains topology, candidates, final statuses, and Phase A
  eligibility inputs;
- duplicated and empty values are omitted;
- every emitted `evidence_ref` resolves in the sidecar;
- historical full graphs still load;
- compact graphs load and project without the sidecar;
- Phase A output from a compact graph has the same canonical nodes, canonical
  edges, and domain actions as projection from the equivalent full graph;
- concrete object-level visual facts remain outside compact graph and PDDL.

## Acceptance Criteria

Using the latest five-edge experiment as a fixture or equivalent generated
graph:

- compact `graph.json` is materially smaller than the current full graph;
- it is readable without opening the sidecar;
- `graph_evidence.json` preserves the removed diagnostic information;
- Phase A produces the same four canonical nodes and five canonical edges;
- generated `domain.pddl` is semantically unchanged;
- no state naming behavior is changed.

## Non-goals

- State or action renaming.
- Candidate-provider retry or failure/empty distinction.
- Changes to exploration stopping.
- Changes to matching thresholds.
- Business facts in Phase A.
- `problem.pddl` generation.
