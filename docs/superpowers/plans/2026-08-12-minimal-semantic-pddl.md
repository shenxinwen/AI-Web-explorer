# Minimal Semantic PDDL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the current open-ended Web-KOBE pipeline so that an explored graph deterministically produces SafeSym-consumable PDDL containing separate location facts, ordinary capability completion facts, and only the necessary verified business facts.

**Architecture:** Keep exploration, Stagehand execution, Raw Graph, checkpoints, resume, frontier replay, action normalization, and Location PDDL V1 unchanged. Add a small semantic observation record to each raw edge, project raw edges offline into a new `SemanticPlanningGraph`, apply a bounded generic rule set, and compile that graph with a new deterministic Minimal Semantic PDDL compiler. The old planning abstraction and location projector remain available as fallback; the new path does not reuse their `pre_facts=all_active_facts` or `supporting_facts=preconditions` behavior.

**Tech Stack:** Python 3.9+, frozen dataclasses, JSON, existing screenshot VLM provider, pytest, existing SafeSym smoke command. No new dependency.

## Global Constraints

- The acceptance contract is `docs/superpowers/specs/2026-08-12-location-capability-business-fact-pddl-acceptance-design.zh-CN.md`.
- Exploration remains open-ended; PDDL goals and planner output never enter candidate generation or action ranking.
- Every semantic action requires one source location and explicitly emits one post-action location.
- Presentation capabilities require only their source location unless direct evidence proves an additional dependency.
- `supporting_facts` remain evidence and never become Minimal Semantic PDDL preconditions.
- The full set of active facts must never be copied into `required_facts`.
- Business facts enter verified effects only through the existing structured verifier/profile path.
- VLM-observed capability completion facts may enter the semantic graph only for successful `presentation_capability` actions with visible evidence.
- Unknown or unverified preconditions are recorded in the projection report and omitted from PDDL.
- The compiler contains no branches for names such as `shopping`, `cart`, `checkout`, `sort`, or `filter`.
- Existing Location PDDL V1 output and CLI behavior remain backward compatible.
- Sensitive actions may be represented, but the live acceptance experiment stops at checkout and does not place an order.

---

## File Structure

- Create `src/ai_web_explorer/grounded_web/semantic_model.py`: immutable semantic observation and semantic planning graph contracts plus JSON serialization.
- Create `src/ai_web_explorer/grounded_web/semantic_planning.py`: generic role-based rules and raw-edge-to-semantic-graph projection.
- Create `src/ai_web_explorer/safesym_bridge/minimal_semantic_pddl.py`: deterministic domain/problem compiler and projection report.
- Modify `src/ai_web_explorer/grounded_web/visual_delta.py`: ask the screenshot VLM for coarse locations, action role, completion facts, candidate required facts, and evidence.
- Modify `src/ai_web_explorer/grounded_web/graph.py`: persist the optional semantic observation on `WebKobeEdge`.
- Modify `src/ai_web_explorer/grounded_web/explorer.py`: attach parsed semantic observations to successful raw edges.
- Modify `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`: backward-compatible loading of the new edge field only; do not expand the legacy compiler.
- Modify `src/ai_web_explorer/safesym_bridge/cli.py`: add `--projection semantic`, semantic start/goal flags, artifacts, and Location V1 fallback reporting.
- Create `tests/safesym_bridge/test_semantic_model.py`.
- Create `tests/safesym_bridge/test_semantic_planning.py`.
- Create `tests/safesym_bridge/test_minimal_semantic_pddl.py`.
- Modify `tests/safesym_bridge/test_visual_delta_summarizer.py`.
- Modify `tests/safesym_bridge/test_web_kobe_explorer.py`.
- Modify `tests/safesym_bridge/test_web_kobe_pddl_projector.py`.
- Modify `tests/safesym_bridge/test_cli.py`.

---

### Task 1: Add the Semantic Observation and Planning Graph Contracts

**Files:**
- Create: `src/ai_web_explorer/grounded_web/semantic_model.py`
- Modify: `src/ai_web_explorer/grounded_web/graph.py`
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
- Create: `tests/safesym_bridge/test_semantic_model.py`
- Modify: `tests/safesym_bridge/test_web_kobe_pddl_projector.py`

**Interfaces:**
- Produces: `SemanticObservation`, `SemanticAction`, `SemanticPlanningGraph`, and `SemanticProjectionReport`.
- Adds: `WebKobeEdge.semantic_observation: SemanticObservation | None = None`.
- Preserves: historical graph JSON without `semantic_observation` loads with `None`.

- [ ] **Step 1: Write failing contract and round-trip tests**

```python
def test_semantic_observation_round_trips_through_edge_json():
    observation = SemanticObservation(
        action_role="presentation_capability",
        source_location="shopping",
        target_location="shopping",
        completion_facts=["products_sorted"],
        candidate_required_facts=[],
        preserved_facts=[],
        evidence=["Product order visibly changed."],
        confidence=0.93,
    )
    edge = _edge(semantic_observation=observation)
    loaded = load_web_kobe_graph_json(_write_graph(edge))
    assert loaded.edges[0].semantic_observation == observation


def test_historical_edge_without_semantic_observation_loads():
    data = _graph_dict()
    data["edges"][0].pop("semantic_observation", None)
    loaded = load_web_kobe_graph_json(_write_json(data))
    assert loaded.edges[0].semantic_observation is None
```

- [ ] **Step 2: Run the tests and verify the missing contracts fail**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_semantic_model.py tests/safesym_bridge/test_web_kobe_pddl_projector.py -k "semantic_observation or historical_edge"
```

Expected: FAIL because `SemanticObservation` and the edge field do not exist.

- [ ] **Step 3: Implement the immutable contracts**

Use these exact public fields:

```python
SEMANTIC_ACTION_ROLES = frozenset({
    "presentation_capability",
    "state_mutation",
    "navigation",
    "guarded_navigation",
    "form_completion",
    "commit",
    "unknown",
})

@dataclass(frozen=True)
class SemanticObservation:
    action_role: str
    source_location: str
    target_location: str
    completion_facts: list[str] = field(default_factory=list)
    candidate_required_facts: list[str] = field(default_factory=list)
    preserved_facts: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    confidence: float | None = None

@dataclass(frozen=True)
class SemanticAction:
    action_id: str
    action_name: str
    action_role: str
    source_location: str
    target_location: str
    required_facts: list[str] = field(default_factory=list)
    added_facts: list[str] = field(default_factory=list)
    removed_facts: list[str] = field(default_factory=list)
    preserved_facts: list[str] = field(default_factory=list)
    raw_edge_ids: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class SemanticPlanningGraph:
    start_location: str
    locations: list[str]
    capability_facts: list[str]
    business_facts: list[str]
    initial_business_facts: list[str]
    actions: list[SemanticAction]

@dataclass(frozen=True)
class SemanticProjectionReport:
    included_raw_edge_ids: list[str]
    excluded_edges: list[dict[str, Any]]
    uncertain_preconditions: list[dict[str, Any]]
    fact_provenance: list[dict[str, Any]]
```

Every contract gets a deterministic `to_dict()`. Parsing accepts only bounded action roles, normalized lowercase snake-case facts, non-empty normalized locations, confidence in `[0, 1]`, and at most eight entries per fact list. Invalid values degrade to `unknown`/empty rather than raising while loading historical experiments.

- [ ] **Step 4: Add edge persistence and loader compatibility**

Serialize the new field in `WebKobeEdge.to_dict()` and parse it in `_edge_from_dict()` through one `_semantic_observation_from_dict()` helper. Do not change `WEB_KOBE_SCHEMA_VERSION` in this task because the field is optional and backward compatible.

- [ ] **Step 5: Run focused and graph serialization tests**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_semantic_model.py tests/safesym_bridge/test_web_kobe_pddl_projector.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/semantic_model.py src/ai_web_explorer/grounded_web/graph.py src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py tests/safesym_bridge/test_semantic_model.py tests/safesym_bridge/test_web_kobe_pddl_projector.py
git commit -m "feat: add semantic planning contracts"
```

---

### Task 2: Extract Coarse Semantic Observations After Each Action

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/visual_delta.py`
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Modify: `tests/safesym_bridge/test_visual_delta_summarizer.py`
- Modify: `tests/safesym_bridge/test_web_kobe_explorer.py`

**Interfaces:**
- Consumes: `SemanticObservation` from Task 1.
- Changes: `VisualDeltaResult.semantic_observation: SemanticObservation | None`.
- Produces: a persisted semantic observation for every successfully parsed before/after VLM comparison.

- [ ] **Step 1: Write failing Visual Delta parsing tests**

```python
def test_visual_delta_extracts_location_role_and_completion_fact():
    provider = lambda *_args, **_kwargs: json.dumps({
        "candidate_added_facts": [],
        "candidate_removed_facts": [],
        "visual_change_kind": "presentation",
        "action_role": "presentation_capability",
        "source_location": "shopping",
        "target_location": "shopping",
        "completion_facts": ["products_sorted"],
        "candidate_required_facts": [],
        "preserved_facts": [],
        "semantic_evidence": ["The visible product order changed."],
        "semantic_confidence": 0.92,
    })
    result = summarize_visual_delta(_request(), provider=provider)
    assert result.semantic_observation.source_location == "shopping"
    assert result.semantic_observation.target_location == "shopping"
    assert result.semantic_observation.completion_facts == ["products_sorted"]


def test_visual_delta_rejects_completion_fact_for_non_presentation_role():
    result = summarize_visual_delta(
        _request(),
        provider=_provider(action_role="navigation", completion_facts=["products_sorted"]),
    )
    assert result.semantic_observation.completion_facts == []
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_visual_delta_summarizer.py -k "location_role or completion_fact"
```

Expected: FAIL because `semantic_observation` is absent.

- [ ] **Step 3: Extend the prompt with bounded semantic fields**

Require exactly these additional JSON fields:

```json
{
  "action_role": "presentation_capability | state_mutation | navigation | guarded_navigation | form_completion | commit | unknown",
  "source_location": "coarse active business surface before the action",
  "target_location": "coarse active business surface after the action",
  "completion_facts": ["successful ordinary capability markers only"],
  "candidate_required_facts": ["facts visibly relevant to enabling the action"],
  "preserved_facts": ["relevant facts visibly still true after the action"],
  "semantic_evidence": ["short visible observations"],
  "semantic_confidence": 0.0
}
```

The instruction must explicitly say:

```text
Use the same coarse location when only sorting, filtering, searching, pagination,
counts, selections, or styling changed. A modal/drawer/workspace may be a new
location when it becomes the active business surface. Do not infer hidden state.
Do not copy every visible fact into candidate_required_facts.
```

Continue removing `supporting_facts` from the VLM request.

- [ ] **Step 4: Implement strict parsing and safe degradation**

Return `semantic_observation=None` when either location is empty or the role is `unknown`. Keep the existing `PlanningDelta` and `visual_change_kind` behavior unchanged. Permit completion facts only for `presentation_capability` and cap all lists at eight items.

- [ ] **Step 5: Attach observations to raw edges**

In `explorer.py`, carry `visual_result.semantic_observation` into `WebKobeEdge.semantic_observation`. Do not use it to choose the current exploration node, rank actions, or change replay behavior. Store its parsed content inside existing visual-delta trace metadata for audit.

- [ ] **Step 6: Run Visual Delta and explorer tests**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_visual_delta_summarizer.py tests/safesym_bridge/test_web_kobe_explorer.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/visual_delta.py src/ai_web_explorer/grounded_web/explorer.py tests/safesym_bridge/test_visual_delta_summarizer.py tests/safesym_bridge/test_web_kobe_explorer.py
git commit -m "feat: observe coarse semantic action effects"
```

---

### Task 3: Build a Rule-Based Semantic Planning Graph

**Files:**
- Create: `src/ai_web_explorer/grounded_web/semantic_planning.py`
- Create: `tests/safesym_bridge/test_semantic_planning.py`

**Interfaces:**
- Consumes: `WebKobeGraph`, edge `SemanticObservation`, verified `PlanningDelta`, and source `PlanningState`.
- Produces: `build_semantic_planning_graph(graph: WebKobeGraph) -> tuple[SemanticPlanningGraph, SemanticProjectionReport]`.

- [ ] **Step 1: Write failing tests for the accepted rules**

```python
def test_sort_stays_at_location_and_adds_completion_fact():
    graph = _graph_with_edge(
        role="presentation_capability",
        source_location="shopping",
        target_location="shopping",
        completion_facts=["products_sorted"],
        source_active_facts=["unrelated_fact"],
    )
    semantic, _ = build_semantic_planning_graph(graph)
    action = semantic.actions[0]
    assert action.required_facts == []
    assert action.added_facts == ["products_sorted"]
    assert action.source_location == action.target_location == "shopping"


def test_add_to_cart_changes_fact_without_creating_combination_location():
    graph = _graph_with_verified_delta(
        role="state_mutation",
        source_location="shopping",
        target_location="shopping",
        verified_added=["cart_has_items"],
    )
    semantic, _ = build_semantic_planning_graph(graph)
    assert semantic.locations == ["shopping"]
    assert semantic.actions[0].added_facts == ["cart_has_items"]


def test_guarded_navigation_uses_only_confirmed_candidate_requirement():
    graph = _graph_with_edge(
        role="guarded_navigation",
        source_location="shopping",
        target_location="checkout",
        candidate_required_facts=["cart_has_items"],
        source_active_facts=["products_sorted", "cart_has_items"],
        source_profile_fact_ids=["cart_has_items"],
        confidence=0.9,
    )
    semantic, _ = build_semantic_planning_graph(graph)
    assert semantic.actions[0].required_facts == ["cart_has_items"]
    assert "products_sorted" not in semantic.actions[0].required_facts


def test_supporting_facts_never_become_requirements():
    graph = _graph_with_edge(
        role="navigation",
        supporting_facts=["checkout_button_visible"],
    )
    semantic, _ = build_semantic_planning_graph(graph)
    assert semantic.actions[0].required_facts == []
```

- [ ] **Step 2: Run tests and verify the builder is missing**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_semantic_planning.py
```

Expected: FAIL because `build_semantic_planning_graph` does not exist.

- [ ] **Step 3: Implement deterministic edge inclusion**

Include an edge only when:

```python
edge.execution_trace.success
and edge.status in PROJECTABLE_EDGE_STATUSES
and edge.semantic_observation is not None
and edge.semantic_observation.source_location
and edge.semantic_observation.target_location
```

Exclude all other edges with a structured reason such as `failed_execution`, `no_semantic_observation`, `unknown_action_role`, or `invalid_location`. Never manufacture semantic locations from node IDs in this primary path.

- [ ] **Step 4: Implement the small generic rule table**

Use these exact rules:

```python
PRESENTATION_ROLES = {"presentation_capability"}
GUARDED_ROLES = {
    "guarded_navigation",
    "form_completion",
    "commit",
}
REQUIRED_FACT_CONFIDENCE = 0.80
```

- `presentation_capability`: add normalized `completion_facts`; require no business facts.
- all other roles: ignore `completion_facts`.
- all roles: add/remove only `verified_added_facts`/`verified_removed_facts` from `PlanningDelta`; do not trust candidate business deltas.
- guarded roles: promote a candidate required fact only when confidence is at least `0.80`, the fact is active in the source planning state, and it appears in `source.planning_state.profile_fact_ids`.
- non-guarded roles: record candidate requirements as uncertain and omit them.
- never read `BrowserAction.supporting_facts` when computing `required_facts`.
- preserve promoted required facts in `preserved_facts` unless the same action removes them.
- do not copy any other active source facts.

- [ ] **Step 5: Normalize, deduplicate, and merge identical semantic actions**

Normalize IDs to lowercase snake case. Merge only actions with identical:

```text
action_name
action_role
source_location
target_location
required_facts
added_facts
removed_facts
```

Union their raw edge IDs and evidence. Stable-sort locations, facts, actions, and report records so input ordering cannot change output bytes.

Resolve `start_location` from semantic observations whose raw source node is `graph.start_node_id`. If they agree, use that location. If they conflict, report `conflicting_start_location` and mark the semantic graph unusable so the CLI takes the explicit Location V1 fallback; never choose a location by traversal or lexical order. Set `initial_business_facts` from the start node's active profile facts only; generated facts and capability completion facts are not assumed initially true.

- [ ] **Step 6: Add uncertainty and conflict tests**

Cover confidence below `0.80`, inactive candidates, generated/non-profile candidates, conflicting location observations, duplicate actions, and raw edge order reversal. Assert uncertain candidates appear in the report but not in action preconditions.

- [ ] **Step 7: Run the semantic planning tests**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_semantic_planning.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/semantic_planning.py tests/safesym_bridge/test_semantic_planning.py
git commit -m "feat: build rule based semantic planning graph"
```

---

### Task 4: Compile Minimal Semantic PDDL

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/minimal_semantic_pddl.py`
- Create: `tests/safesym_bridge/test_minimal_semantic_pddl.py`

**Interfaces:**
- Consumes: `SemanticPlanningGraph` and optional explicit start/goal query.
- Produces: `MinimalSemanticPddlArtifacts(domain, problem, report)`.
- Public functions:
  - `compile_minimal_semantic_domain(graph, *, domain_name="web_kobe_semantic")`
  - `compile_minimal_semantic_problem(graph, *, goal_location=None, goal_facts=(), problem_name="web_kobe_semantic_problem", domain_name="web_kobe_semantic")`

- [ ] **Step 1: Write the accepted shopping PDDL tests**

```python
def test_compiler_separates_location_capability_and_business_facts():
    graph = _practice_shopping_semantic_graph()
    domain = compile_minimal_semantic_domain(graph).domain
    assert ":precondition (and (at_shopping))" in _action(domain, "sort_products")
    assert ":effect (and (at_shopping) (products_sorted))" in _action(domain, "sort_products")
    assert "products_sorted" not in _action(domain, "add_to_cart_from_shopping").split(":effect")[0]
    assert ":precondition (and (at_shopping) (cart_has_items))" in _action(domain, "open_checkout")
    assert "(not (at_shopping))" in _action(domain, "open_checkout")
    assert "(at_checkout)" in _action(domain, "open_checkout")
    assert "(cart_has_items)" in _action(domain, "open_checkout").split(":effect")[1]


def test_problem_can_ask_for_checkout_location():
    graph = _practice_shopping_semantic_graph()
    problem = compile_minimal_semantic_problem(
        graph,
        goal_location="checkout",
    ).problem
    assert "(:init (at_shopping))" in problem
    assert "(:goal (and (at_checkout)))" in problem
```

- [ ] **Step 2: Run tests and verify compiler absence**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_minimal_semantic_pddl.py
```

Expected: FAIL because the compiler does not exist.

- [ ] **Step 3: Implement deterministic predicate and action compilation**

Use zero-arity STRIPS predicates. For every action:

```python
preconditions = [f"(at_{source_location})"] + required_fact_predicates
effects = []
if source_location != target_location:
    effects.append(f"(not (at_{source_location}))")
effects.append(f"(at_{target_location})")
effects.extend(added_fact_predicates)
effects.extend(f"(not ({fact}))" for fact in removed_facts)
effects.extend(preserved_fact_predicates)
```

Deduplicate while keeping deterministic order. A same-location action must emit `(at_<location>)` without deleting it. Declare predicates from all locations, capability facts, business facts, required facts, and effects.

- [ ] **Step 4: Implement problem validation**

- Initialize exactly one location: `graph.start_location`.
- Include `graph.initial_business_facts` in `:init`.
- Require at least one of `goal_location` or `goal_facts`.
- Reject unknown goals with `unknown_goal_location` or `unknown_goal_fact`.
- Run a simple forward STRIPS reachability check over the compiled semantic actions before writing the problem; reject an unreachable goal with `goal_unreachable`.

- [ ] **Step 5: Add safety and generalization tests**

Add tests proving:

- `supporting_facts` cannot appear because the compiler never consumes raw edges;
- order reversal produces byte-identical PDDL;
- a document fixture using `at_document_list`, `documents_found`, and `document_selected` compiles with the same code;
- an empty semantic action set still produces a valid domain;
- two active initial locations are structurally impossible because the graph carries one `start_location`;
- an unreachable checkout goal is rejected.

- [ ] **Step 6: Run compiler tests**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_minimal_semantic_pddl.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/minimal_semantic_pddl.py tests/safesym_bridge/test_minimal_semantic_pddl.py
git commit -m "feat: compile minimal semantic PDDL"
```

---

### Task 5: Add CLI Artifacts and Location V1 Fallback

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Modify: `tests/safesym_bridge/test_cli.py`

**Interfaces:**
- Adds: `web-kobe-phase-a --projection semantic`.
- Adds: `--start-location`, `--goal-location`, and repeatable `--goal-fact` for semantic projection.
- Writes: `semantic_planning_graph.json`, `semantic_projection_report.json`, `domain.pddl`, and optional `problem.pddl`.
- Falls back: writes Location PDDL V1 and records `fallback_projection: "location"` only when semantic projection has no usable actions or locations.

- [ ] **Step 1: Write failing CLI artifact tests**

```python
def test_phase_a_semantic_projection_writes_semantic_artifacts(tmp_path):
    result = main([
        "web-kobe-phase-a",
        "--graph", str(_semantic_graph_json(tmp_path)),
        "--projection", "semantic",
        "--goal-location", "checkout",
        "--output", str(tmp_path / "out"),
    ])
    assert result == 0
    assert (tmp_path / "out/semantic_planning_graph.json").exists()
    assert (tmp_path / "out/semantic_projection_report.json").exists()
    assert "(cart_has_items)" in (tmp_path / "out/domain.pddl").read_text()


def test_semantic_projection_falls_back_without_semantic_observations(tmp_path):
    result = main([
        "web-kobe-phase-a",
        "--graph", str(_historical_location_graph_json(tmp_path)),
        "--projection", "semantic",
        "--output", str(tmp_path / "out"),
    ])
    assert result == 0
    report = json.loads((tmp_path / "out/semantic_projection_report.json").read_text())
    assert report["fallback_projection"] == "location"
```

- [ ] **Step 2: Run CLI tests and verify the new projection is rejected**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_cli.py -k "semantic_projection"
```

Expected: FAIL because `semantic` is not an accepted projection.

- [ ] **Step 3: Add semantic projection argument validation**

For `semantic`:

- reject `--start-node`, `--goal-node`, and checkpoint flags;
- accept `--start-location` only when it matches the projected graph start location in V1;
- require both a usable semantic graph and at least one goal flag to emit `problem.pddl`;
- emit domain-only artifacts when no goal is supplied;
- keep existing trace/location/surface validation unchanged.

- [ ] **Step 4: Write semantic and fallback artifacts**

Primary path:

```text
raw_graph.json
semantic_planning_graph.json
semantic_projection_report.json
domain.pddl
problem.pddl                 # only with explicit goal
```

Fallback path additionally records:

```json
{
  "fallback_projection": "location",
  "fallback_reason": "no_usable_semantic_actions"
}
```

Do not label fallback output as semantic success.

- [ ] **Step 5: Run the complete CLI and projection test group**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_cli.py tests/safesym_bridge/test_location_pddl.py tests/safesym_bridge/test_surface_pddl.py tests/safesym_bridge/test_trace_pddl.py tests/safesym_bridge/test_minimal_semantic_pddl.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/cli.py tests/safesym_bridge/test_cli.py
git commit -m "feat: expose semantic PDDL projection"
```

---

### Task 6: Prove the Acceptance Contract End to End

**Files:**
- Modify: `tests/safesym_bridge/test_semantic_planning.py`
- Modify: `tests/safesym_bridge/test_minimal_semantic_pddl.py`
- Modify: `docs/current-project-overview.zh-CN.md`
- Create: `docs/experiments/minimal-semantic-pddl-practice-shopping-v1.md`

**Interfaces:**
- Proves: the exact acceptance path `shopping -> shopping+cart_has_items -> checkout+cart_has_items`.
- Proves: a non-commerce fixture uses the same builder/compiler without code changes.

- [ ] **Step 1: Add the full synthetic PracticeAutomatedTesting acceptance fixture**

The fixture contains four independently observed actions:

```text
sort_products:
  shopping -> shopping
  adds products_sorted

filter_products:
  shopping -> shopping
  adds products_filtered

add_to_cart_from_shopping:
  shopping -> shopping
  verified adds cart_has_items

open_checkout:
  shopping -> checkout
  candidate requires cart_has_items
  source has verified cart_has_items
```

Assert the compiled plan model can reach `at_checkout` in exactly two business actions when capability actions are optional:

```text
add_to_cart_from_shopping
open_checkout
```

Use the existing lightweight STRIPS smoke helper for this unit test. Do not require an external browser.

- [ ] **Step 2: Add a cross-domain document fixture**

Use:

```text
search_documents:
  document_list -> document_list
  adds documents_found

select_document:
  document_list -> document_workspace
  adds document_selected
```

Assert the same semantic builder and compiler produce legal PDDL without commerce-specific configuration in the compiler.

- [ ] **Step 3: Run all targeted tests**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_semantic_model.py tests/safesym_bridge/test_visual_delta_summarizer.py tests/safesym_bridge/test_semantic_planning.py tests/safesym_bridge/test_minimal_semantic_pddl.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_cli.py
```

Expected: PASS.

- [ ] **Step 4: Run the full non-browser suite**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q --ignore=tests/safesym_bridge/test_web_kobe_playwright_integration.py --ignore=tests/test_local_shop_fixture.py
```

Expected: all collected tests pass; only intentional skips remain.

- [ ] **Step 5: Run a bounded real-site experiment**

Run the existing observed-action explorer against `https://practiceautomatedtesting.com/shopping` with:

```text
open-ended candidate generation
business profile = ecommerce_checkout
visual delta enabled
frontier replay enabled
checkpoint/resume enabled
maximum five candidates per observed node
```

Stop without executing `place_order`. If one bounded run does not observe both `add_to_cart` and `open_checkout`, resume the same graph rather than clearing it.

- [ ] **Step 6: Project and inspect the real graph**

Run semantic projection with goal location `checkout`. Verify:

- `sort`/`filter` remain at shopping and add completion facts;
- no sorted-shopping or shopping-with-cart location exists;
- add-to-cart adds `cart_has_items` at shopping;
- open-checkout requires only shopping plus `cart_has_items`;
- the shortest plan to checkout excludes sort, filter, and product detail;
- every action/fact maps to raw edge evidence;
- no order is submitted.

Record commands, artifact paths, model configuration, observed deviations, and SafeSym result in `docs/experiments/minimal-semantic-pddl-practice-shopping-v1.md`.

- [ ] **Step 7: Run SafeSym smoke over the real artifacts**

Use the existing `web-kobe-safesym-smoke` command with the configured SafeSym root and safety rules. Expected:

```text
parser: pass
base planner: plan found
plan prefix: add_to_cart_from_shopping, open_checkout
no sensitive final submission action required
```

If SafeSym is unavailable in the execution environment, preserve the artifacts and report that external smoke remains unverified; do not replace it with a fake success.

- [ ] **Step 8: Update current project documentation**

Document the primary pipeline:

```text
open exploration
-> Raw Graph
-> semantic observation
-> generic semantic rules
-> SemanticPlanningGraph
-> Minimal Semantic PDDL
-> SafeSym
```

Document Location PDDL V1 as fallback and explicitly state that the legacy semantic projector is not the primary acceptance path.

- [ ] **Step 9: Commit**

```powershell
git add tests/safesym_bridge/test_semantic_planning.py tests/safesym_bridge/test_minimal_semantic_pddl.py docs/current-project-overview.zh-CN.md docs/experiments/minimal-semantic-pddl-practice-shopping-v1.md
git commit -m "test: prove minimal semantic PDDL acceptance path"
```

---

## Final Acceptance Checklist

- [ ] Raw exploration, resume, replay, and evidence formats still work.
- [ ] Historical raw graph JSON without semantic observations still loads.
- [ ] Each semantic action has one source location and one target location.
- [ ] Every PDDL action effect explicitly contains its post-action location.
- [ ] Sort/filter/search remain at the same location and add completion facts.
- [ ] Ordinary capability facts do not become unrelated action preconditions.
- [ ] Adding an item changes `cart_has_items` without creating a combination location.
- [ ] Opening checkout changes location and preserves `cart_has_items`.
- [ ] No action receives all active source facts as preconditions.
- [ ] `supporting_facts` never enter Minimal Semantic PDDL.
- [ ] Uncertain preconditions are omitted and reported.
- [ ] Verified business facts remain traceable to structured evidence.
- [ ] PracticeAutomatedTesting reaches checkout through add-to-cart then open-checkout.
- [ ] Sort/filter/product-detail are absent from the shortest checkout plan.
- [ ] No cart page or order-review page is invented for the practice site.
- [ ] No order is placed during acceptance.
- [ ] A non-commerce fixture uses the same builder/compiler.
- [ ] Location PDDL V1 remains available when semantic evidence is missing.
- [ ] SafeSym parses and solves the real semantic artifacts, or the external-environment blocker is reported truthfully with artifacts preserved.
