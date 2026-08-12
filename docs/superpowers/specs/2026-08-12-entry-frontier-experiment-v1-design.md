# Entry Frontier Experiment V1.1 Design

**Goal:** Make the first real Frontier Replay experiment exercise branching reliably on simple websites whose useful sibling actions are concentrated on the entry surface.

## Decision

The entry node may qualify as an exploration frontier when it has at least one untried business affordance. Selecting it performs entry reset and entry-state validation, then resumes ordinary exploration from that node. Its replay path is empty, so no replay edge is recorded or fabricated.

The experiment uses `max_candidates=5`. Five remains an upper bound rather than a quota. Candidate refresh on revisit is explicitly out of scope for V1.1.

## Selection and execution

- `select_frontier` continues to use deterministic global BFS and successful, non-unstable observed edges.
- The controller explicitly opts into entry-frontier selection; callers using the pure selector retain its existing default unless the implementation can preserve compatibility more cleanly through a dedicated parameter.
- A selected entry frontier is passed through the existing `FrontierReplayRunner`. The runner resets to `start_url`, validates `start_node_id`, executes zero replay actions, and reports success at the entry node.
- Normal `explore_one_step` then chooses one remaining entry affordance and records the resulting observed edge.
- If the follow-up exploration produces no progress, the entry node is added to the existing per-run blocked set. It cannot loop indefinitely.

## Experiment configuration

The first real run uses the generic Stagehand explorer with:

```text
--steps 10 (increase to 12 only if the run is still productive)
--max-candidates 5
--frontier-replay
--openai-visual-delta
--screenshot-dir <experiment screenshots>
--stagehand-execution-mode observed_action
```

Visual affordance generation and screenshots are required because the generic explorer needs stored business affordances to distinguish tried from untried actions.

## Acceptance criteria

1. An entry graph with two affordances and one tried outgoing action selects the entry frontier when controller replay is enabled.
2. Entry replay performs reset and entry validation, executes zero stored actions, then permits one normal exploration step.
3. Entry replay followed by no progress is attempted once and stops with the entry node blocked.
4. Non-entry frontier behavior, unstable-edge exclusion, replay metrics, Trace PDDL, and Surface PDDL remain unchanged.
5. The browser fixture contains at least three entry candidates and demonstrates at least one successful entry replay when Playwright is available.
6. The experiment report records candidate counts per visited surface, replay attempts/successes/failures, blocked frontier IDs, node/edge counts, deepest verified surface, Surface PDDL paths, and SafeSym parse/base/safe results.

## Non-goals

- Refreshing or topping up VLM candidates on revisit.
- Coverage scoring or semantic frontier ranking.
- Website-specific action names or branching.
- Replaying failed or unstable edges.
- Executing a SafeSym plan back on the website.

## Expected limitation

Candidate recall remains bounded by the first VLM observation of each surface. Using five candidates reduces the chance of prematurely omitting useful sibling actions but does not claim full site coverage.
