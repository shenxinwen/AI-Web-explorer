# Compact Graph Action Dependencies Design

## Objective

Preserve semantic action dependencies when a `WebKobeGraph` is written as the compact `graph.json` artifact, so loading that artifact and projecting it to semantic PDDL produces the same action preconditions as projecting the in-memory graph.

## Scope

This change is limited to compact graph artifact serialization. It does not change the core `WebKobeEdge` model, candidate scheduling, execution behavior, semantic extraction prompts, or SafeSym.

The current compact fields remain unchanged. The field audit found no exact duplicate that can be removed safely: similarly named fields serve location naming, state recovery, execution ordering, projection, or diagnostics. Avoiding speculative field deletion keeps checkpoint compatibility intact.

## Data Contract

For every compact edge, including entries under `execution_events`, serialize `required_action_ids` when it is non-empty. Empty lists continue to be omitted by `_without_empty_optional_values`.

`required_action_ids` is the frozen dependency evidence attached to a successful action edge. It is distinct from mutable candidate-pool `requires` state and is the dependency source consumed by `SemanticPlanningGraph` projection.

## Processing Flow

1. `WebKobeEdge.to_dict()` emits `required_action_ids`.
2. `_compact_edge()` retains the field.
3. `build_graph_artifact_payload()` uses `_compact_edge()` for both merged graph edges and ordered execution events.
4. `load_web_kobe_graph_json()` restores the field.
5. Semantic planning projection turns the restored dependency IDs into completion-predicate preconditions.

## Compatibility

Existing compact artifacts without `required_action_ids` remain loadable because the loader already defaults the missing field to an empty list. This is therefore an additive artifact-schema correction and requires no migration.

## Verification

- A compact edge preserves non-empty `required_action_ids`.
- A compact execution event preserves non-empty `required_action_ids`.
- Saving and loading the compact graph preserves dependencies.
- Semantic PDDL generated from the reloaded graph requires the prerequisite action completion predicates.
- Existing graph artifact and semantic planning tests remain green.
