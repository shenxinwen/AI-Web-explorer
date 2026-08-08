# Phase A Deterministic Transitions Implementation Plan

> **For agentic workers:** Execute this plan inline in one Codex task. Do not use subagents or multi-agent support. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure Phase A canonical graphs and domains contain only complete, successful, deterministic source/action transitions.

**Architecture:** Extend the existing offline consolidation fixed-point loop. Compare repeated targets only after mapping raw targets to provisional behavior groups; reject a source only when one canonical action reaches more than one target group. Preserve all evidence in the raw graph and report, while omitting every outgoing canonical edge whose source is ineligible for any reason.

**Tech Stack:** Python dataclasses, existing `WebKobeGraph` consolidation code, pytest.

## Global Constraints

- Do not add fields to `WebKobeNode`, `WebKobeEdge`, or `WebKobeGraph`.
- Do not modify VLM, Stagehand, embedding, PlanningState, or PDDL projector behavior.
- Preserve the raw graph unchanged.
- Reuse `rejected_nodes: dict[str, list[str]]` and the reason `action_target_conflict`; do not add a second eligibility structure to persisted artifacts.
- Multiple raw targets in the same final behavior group are deterministic and must remain eligible.
- Outgoing edges from any ineligible source (`frontier_incomplete`, `failed_execution`, `missing_target_node`, or `action_target_conflict`) must not enter the canonical graph.

---

### Task 1: Express deterministic-transition eligibility with tests

**Files:**
- Modify: `tests/safesym_bridge/test_behavior_state_graph.py`

**Interfaces:**
- Consumes: `consolidate_behavior_state_graph(graph)`
- Verifies: `.canonical_graph` and `.report.rejected_nodes`

- [ ] **Step 1: Add a failing test for equivalent repeated targets.**

Build one eligible source with two successful edges using the same action and two raw target nodes that have identical complete behavior signatures. Assert the source is not rejected and its two raw edges collapse to one canonical edge.

- [ ] **Step 2: Add a failing test for conflicting target behavior groups.**

Build one source with two successful edges using the same canonical action. Give the two targets different complete action sets so they remain different behavior groups. Assert the source has `action_target_conflict` and no outgoing canonical edge.

- [ ] **Step 3: Add parameterized coverage for all pre-existing rejection reasons.**

For `frontier_incomplete`, `failed_execution`, and `missing_target_node`, assert rejected source edges remain in `raw_graph.edges` but are absent from `canonical_graph.edges`.

- [ ] **Step 4: Run the focused tests and verify failure.**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_behavior_state_graph.py -q
```

Expected: new assertions fail because conflict detection and rejected-source edge filtering do not yet exist.

### Task 2: Implement fixed-point conflict rejection

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/behavior_state_graph.py`
- Test: `tests/safesym_bridge/test_behavior_state_graph.py`

**Interfaces:**
- Keep public signature unchanged: `consolidate_behavior_state_graph(graph, *, embedding_provider=None) -> BehaviorStateGraphArtifacts`.

- [ ] **Step 1: Add a private conflict detector.**

Given provisional groups, eligible nodes, outgoing edges, and the canonical action map, compute `action -> set(target_group)` for each eligible source. Return source node IDs whose any action has more than one target group.

- [ ] **Step 2: Wrap grouping and refinement in an eligibility fixed point.**

Run initial grouping and refinement, detect new conflicts, mark each new source ineligible, append `action_target_conflict` once to its rejection reasons, and restart grouping. Stop only when no new conflicting source is found.

- [ ] **Step 3: Filter canonical edges by final source eligibility.**

During canonical-edge construction, skip every raw edge whose source node is not finally eligible. Keep the raw edge untouched in `artifacts.raw_graph`; do not filter by target eligibility because an eligible deterministic source may legitimately reach a terminal or conservative singleton target.

- [ ] **Step 4: Keep report mappings auditable.**

Ensure rejected reasons remain in `rejected_nodes`. Keep one `edge_mappings` entry per raw edge. For an omitted edge, set `canonical_edge_id` to `None`, keep the raw/canonical source, target, and action values, set `collapsed_into_existing_edge` to `False`, and add report-only `omitted_reason: "source_ineligible"`. Do not add graph fields.

- [ ] **Step 5: Run the focused tests.**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_behavior_state_graph.py -q
```

Expected: all focused tests pass.

### Task 3: Verify CLI artifacts and regressions

**Files:**
- Modify only if an assertion is needed: `tests/safesym_bridge/test_behavior_state_graph_cli.py`
- Do not modify production CLI or projector code unless a failing compatibility test proves it necessary.

**Interfaces:**
- CLI remains `web-kobe-phase-a --graph PATH --output DIRECTORY`.

- [ ] **Step 1: Add or strengthen a CLI artifact assertion.**

Use a graph containing an ineligible source. Assert `raw_graph.json` keeps its edge, `canonical_graph.json` omits it, the report contains the rejection reason, and `domain.pddl` omits the action.

- [ ] **Step 2: Run Phase A and projector tests.**

```powershell
python -m pytest tests/safesym_bridge/test_behavior_state_graph.py tests/safesym_bridge/test_behavior_state_graph_cli.py tests/safesym_bridge/test_web_kobe_pddl_projector.py -q
```

- [ ] **Step 3: Run the complete test suite.**

```powershell
python -m pytest -q
```

- [ ] **Step 4: Review the final diff.**

Confirm no persistent graph fields were added, raw graph identity is preserved, no unrelated model/explorer/projector behavior changed, and every canonical source/action has at most one target.

- [ ] **Step 5: Commit the implementation.**

```powershell
git add src/ai_web_explorer/grounded_web/behavior_state_graph.py tests/safesym_bridge/test_behavior_state_graph.py tests/safesym_bridge/test_behavior_state_graph_cli.py
git commit -m "Enforce deterministic Phase A transitions"
```
