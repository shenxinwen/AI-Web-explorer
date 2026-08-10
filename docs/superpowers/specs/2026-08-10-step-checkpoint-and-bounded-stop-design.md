# Step Checkpoint And Bounded Stop Design

## Goal

Preserve all completed exploration work when a real experiment is interrupted, and temporarily make the requested maximum step count the main exploration limit.

This change does not add resume/replay support and does not change state matching, node materialization, action selection, or PDDL projection.

## Stop behavior

Real Stagehand exploration uses the requested maximum step count as its main limit.

It may still stop early when the current state has no executable candidate. This is a natural end of the forward-only path, because the current implementation does not restore historical frontier states.

The consecutive-unproductive-step limit is disabled for this runner. The controller may retain the reusable mechanism for other callers, but the real experiment path must not stop merely because several completed steps added no new node or edge.

The existing optional terminal-condition interface remains available, but the real experiment runner does not configure one.

## Checkpoint timing

The runner saves a checkpoint after every completed exploration step, after the explorer has finished updating the graph and its embedding records.

It also saves once more after normal controller completion so final stop metadata and summaries are represented by the final artifacts.

If a step raises before it completes, no partial transition is invented. The most recent successfully written checkpoint remains available.

## Checkpoint contents

Each checkpoint updates the existing latest artifact paths instead of creating per-step snapshots:

- state embedding records;
- Stagehand trace;
- compact graph and graph evidence sidecar.

The graph is the authoritative commit marker and is written last. If interruption occurs between files, embedding or trace data may contain a harmless extra completed record, while the graph remains the last committed graph checkpoint.

Every JSON artifact must be written through a temporary file in the same directory and then replaced, so readers never receive a half-written JSON document. The existing paired graph/evidence writer remains responsible for preserving its current rollback behavior.

## Code boundaries

`grounded_web/controller.py` gains an optional callback invoked after each completed step. The controller owns timing; it does not know artifact paths or serialization details.

`safesym_bridge/browser_runner.py` owns a single checkpoint-writing helper. It closes over the explorer so it can read current state embedding records, derives Stagehand traces from graph edges, and reuses the existing graph writer. Both per-step and final persistence call this helper.

The real Stagehand runner explicitly disables the consecutive-unproductive limit. No unrelated controller callers are changed unless required to make the configuration explicit.

## Failure behavior

- Failure while writing a temporary file leaves the previous formal artifact intact.
- Failure while replacing graph/evidence preserves the previous graph/evidence pair using the existing rollback behavior.
- A checkpoint write failure is not silently ignored: the experiment fails clearly because continuing without durable progress would violate the checkpoint guarantee.
- Browser shutdown still runs through the existing `finally` block.

## Verification

Automated tests must prove:

1. A checkpoint callback runs after every completed controller step.
2. A later exploration exception leaves artifacts from earlier completed steps available.
3. Consecutive unproductive steps do not stop the configured real runner before its maximum step count.
4. Current-state exhaustion still ends the forward-only run naturally.
5. Embedding, trace, graph, and evidence are refreshed by checkpoints.
6. Failed JSON replacement does not expose truncated graph artifacts.

