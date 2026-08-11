# Explored Trace PDDL V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compile the ordered successful actions in a frozen WebKobeGraph into an untyped, zero-argument STRIPS checkpoint state machine that SafeSym can parse and solve even when every browser action stays on the same URL and Raw/Planning nodes are self-loops.

**Architecture:** Add a pure `trace_pddl.py` compiler beside the existing Location compiler. It consumes Raw Graph edge order as the V1 trace, creates one initial checkpoint plus one checkpoint per eligible successful edge, and never consults DOM deltas, Planning Abstraction, Visual Delta, embeddings, or domain-specific action names. Phase A defaults to Trace V1 while retaining explicit `--projection location` compatibility; SafeSym continues to consume ordinary `domain.pddl` and `problem.pddl` files.

**Tech Stack:** Python 3.9+, dataclasses, existing `WebKobeGraph` models, argparse CLI, pytest, SafeSym parser/injector, Fast Downward.

## Global Constraints

- Preserve open-ended exploration: no start, goal, problem, or SafeSym plan may flow back into candidate generation, ranking, Stagehand prompts, or browser execution.
- Trace V1 plans only the recorded main action sequence; it does not claim full-site coverage, branch completeness, semantic state equality, or optimal business workflow.
- A trace edge is eligible only when `execution_trace.success` is true, `status != "failed_execution"`, the action identity normalizes to a non-empty PDDL symbol, and `after_observation_id` is non-empty.
- URL, Raw/Planning source-target equality, DOM delta, Visual Delta, PlanningState, embeddings, and evidence sidecars must not affect eligibility or generated PDDL.
- Failed or structurally incomplete edges remain auditable in `projection_report.json` but do not become actions or checkpoints.
- Keep `location_pddl.py` and its public functions byte-compatible for callers that explicitly select Location V1.
- Edge list order is semantic trace order. Node order and JSON object-key order are not semantic and must not alter output.
- Do not add dependencies or business-name allowlists/denylists.

---

### Task 1: Pure Trace Domain Compiler

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/trace_pddl.py`
- Create: `tests/safesym_bridge/test_trace_pddl.py`

**Interfaces:**
- Consumes: `WebKobeGraph.edges` in recorded order and each edge's `action`, `status`, and `execution_trace`.
- Produces constant `TRACE_PROJECTION_SCHEMA_VERSION = "trace-pddl-projection-v1"`.
- Produces immutable `TraceDomainProjection` with `domain: str` and `report: dict[str, Any]` fields.
- Produces `compile_trace_domain(graph: WebKobeGraph, *, domain_name: str = "web_kobe_trace") -> TraceDomainProjection`.

- [ ] **Step 1: Add the successful-self-loop regression fixture and failing test**

Create one Raw node and two ordered self-loop edges, `search_items` and `apply_category_filter`, both with `execution_trace.success=True`, non-empty `after_observation_id`, and `status="no_observed_change"`. Assert that the compiler creates three checkpoint predicates and two actions despite identical Raw source/target IDs:

```python
def test_trace_domain_projects_successful_self_loops_as_ordered_checkpoints():
    graph = _graph(
        edges=[
            _edge("page", "search_items", "page", status="no_observed_change"),
            _edge("page", "apply_category_filter", "page", status="no_observed_change"),
        ]
    )

    result = compile_trace_domain(graph)

    assert "(:requirements :strips)" in result.domain
    assert ":typing" not in result.domain
    assert ":types" not in result.domain
    assert ":constants" not in result.domain
    assert "(at " not in result.domain
    assert len(result.report["checkpoints"]) == 3
    assert [item["pddl_action"] for item in result.report["actions"]] == [
        "search_items",
        "apply_category_filter",
    ]
    assert "(not (state_initial))" in result.domain
    assert "(state_after_search_items)" in result.domain
```

- [ ] **Step 2: Run the new test and verify the missing-module failure**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_trace_pddl.py::test_trace_domain_projects_successful_self_loops_as_ordered_checkpoints -q
```

Expected: collection fails because `ai_web_explorer.safesym_bridge.trace_pddl` does not exist.

- [ ] **Step 3: Implement deterministic trace-step construction**

In `trace_pddl.py`, implement small pure helpers patterned after `location_pddl.py`:

```python
def _action_identity(edge: WebKobeEdge) -> str:
    return (edge.action.canonical_action_name or edge.action.semantic_id or "").strip()

def _exclusion_reason(edge: WebKobeEdge) -> str | None:
    if not edge.execution_trace.success or edge.status == "failed_execution":
        return "failed_execution"
    if not edge.execution_trace.after_observation_id.strip():
        return "missing_after_observation"
    if not _normalized_symbol(_action_identity(edge)):
        return "invalid_action_identity"
    return None
```

Iterate `graph.edges` without sorting. Start with checkpoint ID `checkpoint_000` and predicate `state_initial`. For each eligible edge at trace ordinal `n`, create a target checkpoint ID `checkpoint_{n:03d}_{digest}` and readable predicate `state_after_<action>`; append an eight-character SHA-256 digest only when a predicate or action name collides. The digest input must include the raw edge ID and trace ordinal. Connect every eligible edge from the most recently created checkpoint to its new target checkpoint. Excluded edges do not advance the checkpoint ordinal.

- [ ] **Step 4: Render the untyped one-hot STRIPS domain and report**

Render exactly one predicate per checkpoint and one grounded action per eligible edge:

```lisp
(define (domain web_kobe_trace)
  (:requirements :strips)
  (:predicates
    (state_initial)
    (state_after_search_items)
  )
  (:action search_items
    :parameters ()
    :precondition (state_initial)
    :effect (and
      (not (state_initial))
      (state_after_search_items)
    )
  )
)
```

The report shape must be:

```python
{
    "schema_version": "trace-pddl-projection-v1",
    "domain_name": "web_kobe_trace",
    "checkpoints": [
        {
            "checkpoint_id": "checkpoint_000",
            "trace_index": 0,
            "pddl_predicate": "state_initial",
            "incoming_raw_edge_id": None,
            "after_observation_id": graph.start_node_id,
        },
    ],
    "actions": [
        {
            "raw_edge_id": edge.edge_id,
            "source_checkpoint_id": "checkpoint_000",
            "target_checkpoint_id": "checkpoint_001_<digest>",
            "pddl_action": "search_items",
            "source_predicate": "state_initial",
            "target_predicate": "state_after_search_items",
            "original_action_identity": "search_items",
            "after_observation_id": edge.execution_trace.after_observation_id,
        },
    ],
    "excluded_edges": [],
}
```

For the initial checkpoint, use `graph.start_node_id` as its observation reference when non-empty; otherwise use `None` without rejecting the domain.

- [ ] **Step 5: Add exclusion, collision, empty-trace, and determinism tests**

Add named tests `test_trace_domain_excludes_failed_missing_observation_and_invalid_identity`, `test_trace_domain_with_no_successful_edges_is_a_legal_initial_only_domain`, `test_trace_domain_disambiguates_repeated_action_names_with_stable_digest`, `test_trace_domain_ignores_nodes_dom_visual_and_planning_fields`, and `test_trace_domain_is_stable_when_node_and_mapping_key_order_changes`. Each test must assert the exact report reason, predicate/action count, or byte-identical output described by its name rather than only checking that compilation returns.

The determinism test may reverse `graph.nodes` and reorder dictionary keys, but must not reverse `graph.edges`, because edge order is the trace. The source-scan test must assert that `trace_pddl.py` contains none of `checkout`, `cart`, `login`, `search`, `filter`, or `payment` outside test data.

- [ ] **Step 6: Run the compiler tests**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_trace_pddl.py -q
```

Expected: all Trace domain tests pass.

- [ ] **Step 7: Commit Task 1**

```powershell
git add src/ai_web_explorer/safesym_bridge/trace_pddl.py tests/safesym_bridge/test_trace_pddl.py
git commit -m "feat: compile successful exploration traces to PDDL"
```

---

### Task 2: Explicit Trace Problem Generation

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/trace_pddl.py`
- Modify: `tests/safesym_bridge/test_trace_pddl.py`

**Interfaces:**
- Consumes: the same deterministic checkpoint sequence produced by `compile_trace_domain`.
- Produces immutable `TraceProblemProjection` with `problem: str`, `start_checkpoint: str`, and `goal_checkpoint: str` fields.
- Produces `compile_trace_problem(graph: WebKobeGraph, *, start_checkpoint_id: str, goal_checkpoint_id: str, domain_name: str = "web_kobe_trace", problem_name: str = "web_kobe_trace_problem") -> TraceProblemProjection`.

- [ ] **Step 1: Write failing start/goal problem tests**

Obtain checkpoint IDs from `compile_trace_domain(graph).report` rather than duplicating digest logic in tests:

```python
def test_trace_problem_uses_explicit_reachable_checkpoints():
    graph = _three_step_trace()
    checkpoints = compile_trace_domain(graph).report["checkpoints"]

    result = compile_trace_problem(
        graph,
        start_checkpoint_id=checkpoints[0]["checkpoint_id"],
        goal_checkpoint_id=checkpoints[-1]["checkpoint_id"],
    )

    assert "(:domain web_kobe_trace)" in result.problem
    assert "(:init (state_initial))" in result.problem
    assert "(:goal (state_after_open_checkout))" in result.problem
```

Also add exact failure tests for unknown start, unknown goal, and a goal earlier than the selected start. A start equal to goal must produce a valid zero-step problem.

- [ ] **Step 2: Run problem tests and verify the missing-function failure**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_trace_pddl.py -k "problem" -q
```

Expected: failure because `compile_trace_problem` is not implemented.

- [ ] **Step 3: Implement problem compilation from checkpoint indices**

Rebuild the deterministic checkpoint sequence through a shared private helper used by both public compile functions. Validate IDs, then compare `trace_index`; reject backward reachability with:

```python
raise ValueError(
    f"goal_unreachable_in_explored_trace: {start_checkpoint_id} -> {goal_checkpoint_id}"
)
```

Render only the chosen start predicate in `:init` and the chosen goal predicate in `:goal`. Normalize custom domain/problem names through the same helper used by domain compilation so the report, domain, and problem names cannot disagree.

- [ ] **Step 4: Run all Trace compiler tests**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_trace_pddl.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 2**

```powershell
git add src/ai_web_explorer/safesym_bridge/trace_pddl.py tests/safesym_bridge/test_trace_pddl.py
git commit -m "feat: generate explicit trace planning problems"
```

---

### Task 3: Phase A Projection Selection and Artifact Integration

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Modify: `tests/safesym_bridge/test_behavior_state_graph_cli.py`

**Interfaces:**
- `web-kobe-phase-a --projection trace|location`, default `trace`.
- Trace query flags: `--start-checkpoint`, `--goal-checkpoint`.
- Location compatibility query flags remain: `--start-node`, `--goal-node`.
- Phase A output names remain `raw_graph.json`, `planning_graph.json`, `planning_abstraction_report.json`, `projection_report.json`, `domain.pddl`, and optional `problem.pddl`.

- [ ] **Step 1: Write failing CLI tests for default Trace output**

Update the default Phase A assertion to require:

```python
assert projection["schema_version"] == "trace-pddl-projection-v1"
assert "(:requirements :strips)" in domain
assert "(:types location)" not in domain
assert "(at ?location - location)" not in domain
assert "(state_initial)" in domain
```

Use a fixture containing successful self-loop edges and assert they appear as ordered actions in the domain.

- [ ] **Step 2: Write failing compatibility and flag-validation tests**

Add named tests `test_phase_a_location_projection_remains_available_explicitly`, `test_phase_a_trace_problem_requires_checkpoint_pair`, `test_phase_a_location_problem_requires_node_pair`, `test_phase_a_rejects_trace_flags_in_location_mode`, and `test_phase_a_rejects_node_flags_in_trace_mode`. Each validation test must assert exit code 2 and the exact parser message below.

Expected parser messages:

```text
--start-checkpoint and --goal-checkpoint must be provided together
--start-node and --goal-node must be provided together
checkpoint query flags require --projection trace
node query flags require --projection location
```

- [ ] **Step 3: Run the CLI tests and verify they fail against Location default**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_behavior_state_graph_cli.py -k "phase_a" -q
```

Expected: Trace assertions fail because Phase A still always calls `compile_location_domain`.

- [ ] **Step 4: Add CLI projection selection**

Add parser arguments:

```python
web_kobe_phase_a_parser.add_argument(
    "--projection",
    choices=["trace", "location"],
    default="trace",
)
web_kobe_phase_a_parser.add_argument("--start-checkpoint", default=None)
web_kobe_phase_a_parser.add_argument("--goal-checkpoint", default=None)
```

Keep building and writing Planning Graph artifacts for diagnostics in both modes. In Trace mode, call `compile_trace_domain(graph)` on the loaded Raw Graph, not `artifacts.planning_graph`. In Location mode, preserve the existing `compile_location_domain(artifacts.planning_graph, edge_mappings=artifacts.report.edge_mappings)` call unchanged.

When no complete query pair is supplied, do not write `problem.pddl`; if a stale `problem.pddl` exists in the output directory from a prior run, unlink only that exact file. Trace mode calls `compile_trace_problem(graph, start_checkpoint_id=args.start_checkpoint, goal_checkpoint_id=args.goal_checkpoint)`; Location mode calls `compile_location_problem(artifacts.planning_graph, start_node_id=args.start_node, goal_node_id=args.goal_node)`.

- [ ] **Step 5: Preserve compact/full graph equivalence**

Extend the existing compact-input test to assert full and compact inputs produce identical Trace `domain.pddl` and `projection_report.json`. This must work without `graph_evidence.json`, screenshots, embeddings, Visual Delta hydration, or DOM sidecars because compact execution traces retain `after_observation_id` and `success`.

- [ ] **Step 6: Run Phase A and compatibility tests**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_behavior_state_graph_cli.py tests/safesym_bridge/test_location_pddl.py tests/safesym_bridge/test_trace_pddl.py -q
```

Expected: Trace is the Phase A default and all explicit Location compatibility tests pass.

- [ ] **Step 7: Commit Task 3**

```powershell
git add src/ai_web_explorer/safesym_bridge/cli.py tests/safesym_bridge/test_behavior_state_graph_cli.py
git commit -m "feat: make trace PDDL the Phase A default"
```

---

### Task 4: SafeSym Verification, Generality Contracts, and Documentation

**Files:**
- Modify: `tests/safesym_bridge/test_web_kobe_safesym_smoke.py`
- Modify: `tests/safesym_bridge/test_business_affordance.py`
- Modify: `docs/safesym-bridge.md`

**Interfaces:**
- SafeSym continues to consume unchanged filenames: `domain.pddl` and `problem.pddl`.
- `projection_report.json` is the audit interface for checkpoint/action provenance.
- No new runtime dependency or explorer prompt input is introduced.

- [ ] **Step 1: Convert the SafeSym smoke fixture to zero-argument predicates**

Change `_write_base_pddl` to write:

```lisp
(define (domain web_kobe_trace)
  (:requirements :strips)
  (:predicates (state_initial) (state_goal))
  (:action go_goal
    :parameters ()
    :precondition (state_initial)
    :effect (and (not (state_initial)) (state_goal))
  )
)
```

and a problem with `(:init (state_initial))` and `(:goal (state_goal))`. Keep the fake runner contract unchanged so parser, injection, base plan, and safe plan reporting are still exercised.

- [ ] **Step 2: Add architecture guard tests**

In `test_business_affordance.py`, assert exploration source does not import `trace_pddl`, accept `goal_checkpoint`, or include PDDL/problem text in candidate ranking or Stagehand prompts. Assert `trace_pddl.py` does not inspect `observed_delta`, `schema_delta`, `visual_change_kind`, `planning_delta`, `planning_transition`, node labels, URLs, or business action names.

- [ ] **Step 3: Run the focused SafeSym and architecture tests**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_web_kobe_safesym_smoke.py tests/safesym_bridge/test_business_affordance.py -q
```

Expected: all tests pass with the zero-argument predicate fixture.

- [ ] **Step 4: Document Trace V1 as the recommended Phase A path**

Update `docs/safesym-bridge.md` with:

```powershell
python -m ai_web_explorer.safesym_bridge.cli web-kobe-phase-a `
  --projection trace `
  --graph outputs/experiments/site/graph.json `
  --output outputs/experiments/site/trace_pddl_v1
```

Document how to read checkpoint IDs from `projection_report.json`, rerun with `--start-checkpoint` and `--goal-checkpoint`, then run `web-kobe-safesym-smoke`. State explicitly that successful same-URL/self-loop actions are included, failed actions are excluded, DOM differences are diagnostic only, and `--projection location` preserves the old page-level model.

- [ ] **Step 5: Run the full non-browser suite**

Run:

```powershell
python -m pytest -q --ignore=tests/test_local_shop_fixture.py
```

Expected: zero failures; the two opt-in real-browser tests remain skipped unless their environment flags are enabled.

- [ ] **Step 6: Regenerate and solve an existing real exploration trace**

Use the existing successful real graph first so verification does not depend on model/network availability:

```powershell
python -m ai_web_explorer.safesym_bridge.cli web-kobe-phase-a `
  --projection trace `
  --graph outputs/latest/ecommerce_stagehand_graph.json `
  --output outputs/experiments/trace_pddl_v1_review
```

Read the first and last `checkpoint_id` from `projection_report.json`, rerun Phase A with those explicit checkpoint flags, then run:

```powershell
python -m ai_web_explorer.safesym_bridge.cli web-kobe-safesym-smoke `
  --task-dir outputs/experiments/trace_pddl_v1_review `
  --safesym-root C:\Users\moon\Desktop\Projects\SafeSym `
  --rules C:\Users\moon\Desktop\Projects\SafeSym\configs\constraint_rules.json `
  --fast-downward C:\Users\moon\Desktop\Projects\AutoWebWorld\downward\fast-downward.py
```

Acceptance: `safesym_parse_ready`, `safety_injection_ready`, `base_plan_ready`, and `safe_plan_ready` are all true; `sas_plan` contains every eligible action in report order.

- [ ] **Step 7: Attempt the opt-in shopping-site acceptance run**

When the existing `.env` provides the already configured Stagehand and visual-affordance model credentials, run a bounded, non-purchasing exploration of `https://practiceautomatedtesting.com/shopping` using `web-kobe-stagehand-explore`, with screenshots enabled and `--steps 5`. Do not use a task goal or instruct it to reach checkout. Project the resulting graph with Trace V1 and solve from the first to last checkpoint. Record the observed actions and SafeSym result in a dated output directory.

If credentials or browser execution are unavailable, do not weaken tests or substitute fabricated success. Record the exact environmental blocker in the handoff; the existing real graph verification in Step 6 remains the deterministic acceptance gate.

- [ ] **Step 8: Commit Task 4**

```powershell
git add tests/safesym_bridge/test_web_kobe_safesym_smoke.py tests/safesym_bridge/test_business_affordance.py docs/safesym-bridge.md
git commit -m "docs: verify explored trace planning workflow"
```

---

## Final Review Checklist

- [ ] `git diff --check` reports no whitespace errors.
- [ ] `trace_pddl.py` contains no website/domain-specific action vocabulary.
- [ ] A successful Raw self-loop with a completed after-observation becomes a PDDL transition.
- [ ] Failed and missing-after-observation edges are excluded with structured reasons.
- [ ] Trace output is independent of Planning Abstraction, DOM/visual deltas, embeddings, and sidecars.
- [ ] Location compiler APIs and explicit `--projection location` behavior remain unchanged.
- [ ] Full non-browser tests pass.
- [ ] Real SafeSym parser, injection, base planning, and safe planning succeed on an existing real exploration graph.
- [ ] No task/goal information enters exploration.
