# Behavior State Graph Phase A Implementation Plan

> **For agentic workers:** Execute this plan inline in the current session. Do not dispatch subagents or use multi-agent support. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate a completed raw WebKobeGraph into a conservative canonical behavior-state graph, an auditable consolidation report, and a `domain.pddl` containing only canonical locations and non-self-loop business transitions.

**Architecture:** Add a focused offline consolidation module that reads the existing raw `WebKobeGraph`, derives canonical action names and a fixed-point partition over eligible nodes, and returns a canonical graph plus report without mutating the raw graph. Reuse the existing graph dataclasses and domain projector by creating a Phase-A projection view that strips planning/observation facts and self-loops only for domain generation. Add a CLI command that writes `raw_graph.json`, `canonical_graph.json`, `consolidation_report.json`, and `domain.pddl`, never `problem.pddl`.

**Tech Stack:** Python dataclasses, existing WebKobeGraph JSON loader/serializer, deterministic normalization, pytest, argparse.

## Global Constraints

- Preserve the raw graph and its original action names, evidence, VLM facts, and execution traces.
- Do not add `action_signature`, `transition_signature`, or behavior-state identity fields to `WebKobeNode`/`WebKobeEdge`.
- Only nodes with complete frontiers, explicit successful results for every affordance, and no failed execution candidates may be merged.
- A successful action with no visible business change remains an explicit self-loop; failed execution is never treated as a self-loop.
- Canonicalization is deterministic and conservative: high-confidence exact alias groups may normalize; ambiguous names remain separate and are reported.
- Phase-A PDDL contains only canonical location predicates and non-self-loop business transitions; it does not contain observation facts or `PlanningState.active_facts` and does not produce `problem.pddl`.

---

### Task 1: Define failing tests for Phase-A consolidation

**Files:**
- Create: `tests/safesym_bridge/test_behavior_state_graph.py`
- Read: `src/ai_web_explorer/grounded_web/graph.py`, `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`

**Interfaces:**
- The tests will target `consolidate_behavior_state_graph(graph)` and `compile_phase_a_domain(graph)`.
- The returned artifact will expose `.canonical_graph` and `.report`, and the report will expose `.to_dict()`.

- [ ] **Step 1: Write a failing test for high-confidence action aliases.**

Construct two complete nodes whose affordances use `search_items` and `search_products`, with the same target behavior, and assert the report records one canonical action name chosen from the first-seen normalized name.

- [ ] **Step 2: Write a failing test for conservative frontier eligibility.**

Construct one node with an affordance that has no outgoing result and one node with a failed outgoing edge; assert both remain separate canonical nodes and the report contains rejection reasons.

- [ ] **Step 3: Write a failing test for fixed-point behavior equivalence.**

Construct two complete two-state cycles with different raw node IDs and assert the equivalent states merge while the action-to-target-group relation remains stable after remapping.

- [ ] **Step 4: Write a failing test for self-loops and Phase-A PDDL.**

Construct a successful self-loop and one successful non-self-loop, add `PlanningState.active_facts` and observed facts, and assert the canonical graph keeps the self-loop but `compile_phase_a_domain` emits only the non-self-loop location action and no fact predicates.

- [ ] **Step 5: Run the focused tests and verify the expected missing-API failures.**

Run `pytest tests/safesym_bridge/test_behavior_state_graph.py -q`.

Expected: collection or assertion failures because the Phase-A module and APIs do not yet exist.

### Task 2: Implement deterministic consolidation and report generation

**Files:**
- Create: `src/ai_web_explorer/grounded_web/behavior_state_graph.py`
- Modify: `src/ai_web_explorer/grounded_web/__init__.py` only if public exports are established there
- Test: `tests/safesym_bridge/test_behavior_state_graph.py`

**Interfaces:**
- `consolidate_behavior_state_graph(graph: WebKobeGraph) -> BehaviorStateGraphArtifacts`
- `BehaviorStateGraphArtifacts.raw_graph: WebKobeGraph`
- `BehaviorStateGraphArtifacts.canonical_graph: WebKobeGraph`
- `BehaviorStateGraphArtifacts.report: ConsolidationReport`
- `ConsolidationReport.to_dict() -> dict[str, Any]`

- [ ] **Step 1: Add the minimal action-name normalization helpers.**

Normalize text to lower snake case, preserve first-seen names, and only group the explicit high-confidence search aliases (`search_items`, `search_products`, `submit_search`). Record ambiguous/unrecognized names as separate actions with a report entry rather than guessing.

- [ ] **Step 2: Add frontier eligibility checks.**

For each raw node, collect affordance actions plus observed outgoing actions. Require every affordance to have a matching outgoing edge, require every candidate edge to have a successful execution trace and a non-failed status, and allow successful `no_observed_change` only as an explicit self-loop. Return a rejection reason list for incomplete or failed nodes.

- [ ] **Step 3: Add the fixed-point partition algorithm.**

Initialize eligible groups by canonical affordance/action sets and keep ineligible nodes singleton. Repeatedly refine each group using the canonical action-to-target-group mapping until no group changes. Use raw node order for stable representatives and group IDs.

- [ ] **Step 4: Build the canonical graph without mutating the raw graph.**

Use the first raw node as each group representative, remap edge source/target IDs, canonicalize copied `BrowserAction.canonical_action_name` and copied affordance `action_name`, deduplicate equivalent canonical edges while summing visit counts, and keep self-loops in the canonical graph. Keep planning/evidence data on copied structures for auditability; Phase-A PDDL filtering will be separate.

- [ ] **Step 5: Build the independent report.**

Include schema version, action normalization records, canonical node groups, raw-to-canonical node mapping, rejected node reasons, and edge mappings. Do not add these details as node or edge fields.

- [ ] **Step 6: Run focused tests and fix only implementation failures.**

Run `pytest tests/safesym_bridge/test_behavior_state_graph.py -q` and confirm the tests now pass.

### Task 3: Implement Phase-A domain projection

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
- Test: `tests/safesym_bridge/test_behavior_state_graph.py`
- Test: `tests/safesym_bridge/test_web_kobe_pddl_projector.py` only if a compatibility regression is exposed

**Interfaces:**
- `compile_phase_a_domain(graph: WebKobeGraph, *, options: PddlProjectionOptions | None = None) -> str`

- [ ] **Step 1: Write/retain the failing self-loop/fact exclusion assertion from Task 1.**

The assertion must prove that the Phase-A domain has location-only preconditions/effects, excludes self-loop actions, and contains no `PlanningState.active_facts`, `supporting_facts`, or observed delta predicates.

- [ ] **Step 2: Implement the Phase-A view.**

Create dataclass copies with planning state/delta/transition and observed deltas cleared, remove edges where source and target canonical IDs are equal, then call the existing deterministic `compile_web_kobe_graph_to_domain` projector. Preserve the existing general projector behavior for non-Phase-A callers.

- [ ] **Step 3: Run the focused Phase-A tests and the existing projector tests.**

Run `pytest tests/safesym_bridge/test_behavior_state_graph.py tests/safesym_bridge/test_web_kobe_pddl_projector.py -q`.

### Task 4: Add artifact serialization and CLI entry point

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Create: `tests/safesym_bridge/test_behavior_state_graph_cli.py`
- Test: `tests/safesym_bridge/test_cli.py` if shared CLI assumptions need coverage

**Interfaces:**
- CLI mode: `web-kobe-phase-a` (alias `web-kobe-consolidate`)
- Arguments: `--graph PATH`, `--output DIRECTORY`
- Output files: `raw_graph.json`, `canonical_graph.json`, `consolidation_report.json`, `domain.pddl`

- [ ] **Step 1: Write a failing CLI test.**

Write a raw graph fixture, invoke `main(["web-kobe-phase-a", "--graph", ..., "--output", ...])`, and assert all four files exist, canonical/report JSON load, and `problem.pddl` does not exist.

- [ ] **Step 2: Implement serialization and CLI dispatch.**

Write the input graph unchanged as `raw_graph.json`, serialize the canonical graph via `to_dict()`, serialize the report via `to_dict()`, and write only `compile_phase_a_domain(...)` to `domain.pddl`.

- [ ] **Step 3: Run CLI-focused tests.**

Run `pytest tests/safesym_bridge/test_behavior_state_graph_cli.py tests/safesym_bridge/test_cli.py -q`.

### Task 5: Regression verification and contract review

**Files:**
- Modify only implementation/tests above if verification exposes a concrete regression.

- [ ] **Step 1: Run the complete test suite.**

Run `pytest -q` and record the exact pass/fail result.

- [ ] **Step 2: Review the diff against the Phase-A design.**

Confirm raw graph preservation, canonical graph/report separation, conservative rejection behavior, fixed-point target grouping, action traceability, location-only domain output, and absence of `problem.pddl`.

- [ ] **Step 3: Run a final CLI smoke with the debug graph.**

Generate a temporary Phase-A output directory from an existing graph fixture, inspect the four artifact names and domain text, and ensure no problem artifact was created.

