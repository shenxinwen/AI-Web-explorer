# Planning State Abstraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve every stable GUI observation and its capabilities in the raw graph, then deterministically collapse only presentation-equivalent observations into a smaller planning graph whose cross-group transitions generate the Phase A domain.

**Architecture:** Exploration remains forward-only and records conservative observation nodes. Visual Delta contributes a small, auditable change-kind observation while the local profile verifier remains the only source of verified planning facts. A new offline `planning_abstraction.py` replaces the old behavior-state consolidator: it groups observations only when evidence is strong, aggregates capabilities with their observation sources, preserves unknown states, and feeds the existing Phase A PDDL projector.

**Tech Stack:** Python 3.11, frozen dataclasses, existing embedding providers, pytest, existing WebKobe JSON/PDDL pipeline. No new dependency.

## Global Constraints

- VLM receives no profile facts, planning facts, or global graph state.
- Visual Delta remains raw edge evidence and never writes directly into `PlanningState`.
- Only the local structured verifier may confirm profile facts.
- `supporting_facts` remain local pre-action evidence and never become Phase A PDDL preconditions.
- Candidate count is an upper bound; absence of a candidate is not evidence that a capability is unavailable.
- Each observation node receives Visual Affordance candidates at most once.
- Raw graph observations are never deleted or rewritten by planning abstraction.
- Preserve concrete observed actions, but do not introduce concrete business objects into planning-state names.
- Preserve the earliest canonical action name when semantic action names are merged.
- Unknown evidence stays separate; prefer extra planning states over an unsafe merge.
- DS Flash is the Stagehand model. The screenshot VLM uses the separately configured OpenAI-compatible visual model.
- Keep the implementation small. Do not add dynamic refinement, generated-fact promotion, learned thresholds, replay, or a general business ontology in this change.

## File Structure

- Create `src/ai_web_explorer/grounded_web/planning_abstraction.py`: offline observation-to-planning grouping, capability aggregation, canonical edge mapping, and audit report.
- Create `tests/safesym_bridge/test_planning_abstraction.py`: focused grouping and capability tests.
- Modify `src/ai_web_explorer/grounded_web/explorer.py`: conservatively materialize explicit same-page changes as observation nodes and stop target embedding from rewriting them.
- Modify `src/ai_web_explorer/grounded_web/business_state_policy.py` temporarily in Task 1, then delete it in Task 5 after its observation-ID helper moves to the new module or a small local helper.
- Modify `src/ai_web_explorer/grounded_web/visual_delta.py`: add a bounded visual change-kind observation.
- Modify `src/ai_web_explorer/grounded_web/planning_fact_verifier.py`: report known profile abstractions that stayed true across a concrete value change.
- Modify `src/ai_web_explorer/grounded_web/business_profile.py`: add backward-compatible `preserved_profile_facts` to `PlanningDelta`.
- Modify `src/ai_web_explorer/grounded_web/graph.py`: store `visual_change_kind` on each raw edge.
- Modify `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`: load the new backward-compatible fields.
- Modify `src/ai_web_explorer/safesym_bridge/graph_artifacts.py`: retain the new compact edge evidence.
- Modify `src/ai_web_explorer/safesym_bridge/cli.py`: replace old consolidation with planning abstraction.
- Delete `src/ai_web_explorer/grounded_web/behavior_state_graph.py`: its exact-action-set partition is incompatible with incomplete VLM candidates and view variants.
- Delete `tests/safesym_bridge/test_behavior_state_graph.py`: replace with planning-abstraction tests.
- Delete the dead `BusinessTransition` model and `business_state_policy.py` after observation-ID materialization has moved; keep legacy JSON readable by ignoring the old key.
- Update `docs/current-project-overview.zh-CN.md`, `docs/project-structure.zh-CN.md`, and `docs/project-decisions.zh-CN.md` with the final boundary.

---

### Task 1: Make the Raw Graph Preserve Explicit Observations

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Modify: `src/ai_web_explorer/grounded_web/business_state_policy.py`
- Test: `tests/safesym_bridge/test_web_kobe_explorer.py`
- Test: `tests/safesym_bridge/test_business_state_policy.py`

**Interfaces:**
- Consumes: the existing `state_changed`, selected `BrowserAction`, after snapshot, and Visual Delta candidate facts.
- Produces: `observation_change_node_id(source_node_id, action_name, after_signature, added_facts, removed_facts) -> str`; explicit observed changes are never reassigned to an existing node by embedding target matching.

- [ ] **Step 1: Add failing observation-identity tests**

Add tests showing that two visibly different same-URL results do not reuse the historical node merely because it is in the visit stack, and that the same source/action/outcome produces a stable observation ID.

```python
def test_observation_change_node_id_uses_after_signature():
    first = observation_change_node_id(
        source_node_id="listing",
        action_name="add_to_cart",
        after_signature={"cart_count": 1},
        added_facts=["cart_count_increased"],
        removed_facts=[],
    )
    second = observation_change_node_id(
        source_node_id="listing",
        action_name="add_to_cart",
        after_signature={"cart_count": 2},
        added_facts=["cart_count_increased"],
        removed_facts=[],
    )
    assert first != second
```

Add an explorer test whose embedding provider returns the start node with score `1.0` after a same-URL filter/search change; assert the edge target is a new observation node and target matching reports `blocked_reason == "explicit_observation_change"`.

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_business_state_policy.py tests/safesym_bridge/test_web_kobe_explorer.py
```

Expected: the new ID test fails because `after_signature` is unsupported, and the explorer test fails because the historical target is reused.

- [ ] **Step 3: Materialize every explicit same-page observation before target matching**

Change the helper payload to include a stable normalized after signature:

```python
def observation_change_node_id(
    *,
    source_node_id: str,
    action_name: str,
    after_signature: dict[str, Any],
    added_facts: list[str],
    removed_facts: list[str],
) -> str:
    payload = {
        "source_node_id": source_node_id,
        "action_name": action_name,
        "after_signature": after_signature,
        "added_facts": sorted(set(added_facts)),
        "removed_facts": sorted(set(removed_facts)),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()[:12]
    return f"{source_node_id}__observation_{digest}"
```

In `explore_one_step`, whenever `state_changed` is true and the URL path did not change, assign this observation ID regardless of whether the structured signature or only visual facts changed.

- [ ] **Step 4: Stop embedding target matching from rewriting explicit observations**

At the start of the accepted-match branch in `_match_existing_target_node`, block a same match when `has_explicit_change` is true:

```python
if has_explicit_change:
    return target_node, replace(
        target_match,
        status="blocked",
        blocked_reason="explicit_observation_change",
    )
```

Embedding remains available for source relocation/recovery and diagnostics. Remove `visit_stack` as acceptance evidence for target identity; it may remain for exploration bookkeeping.

- [ ] **Step 5: Run explorer tests**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_business_state_policy.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_state_embedding.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/explorer.py src/ai_web_explorer/grounded_web/business_state_policy.py tests/safesym_bridge/test_business_state_policy.py tests/safesym_bridge/test_web_kobe_explorer.py
git commit -m "Preserve explicit GUI observations in raw graph"
```

---

### Task 2: Record Minimal Transition Evidence

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/visual_delta.py`
- Modify: `src/ai_web_explorer/grounded_web/business_profile.py`
- Modify: `src/ai_web_explorer/grounded_web/planning_fact_verifier.py`
- Modify: `src/ai_web_explorer/grounded_web/graph.py`
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
- Modify: `src/ai_web_explorer/safesym_bridge/graph_artifacts.py`
- Test: `tests/safesym_bridge/test_visual_delta_summarizer.py`
- Test: `tests/safesym_bridge/test_planning_fact_verifier.py`
- Test: `tests/safesym_bridge/test_web_kobe_graph.py`
- Test: `tests/safesym_bridge/test_web_kobe_pddl_projector.py`

**Interfaces:**
- Produces: `VisualDeltaResult.visual_change_kind` with one of `none`, `presentation`, `state_indicator`, `surface`, `mixed`, `unknown`.
- Produces: `PlanningDelta.preserved_profile_facts: list[str]`.
- Produces: `WebKobeEdge.visual_change_kind: str = "unknown"`.
- Backward compatibility: missing JSON fields load as `unknown` and `[]`.

- [ ] **Step 1: Add failing Visual Delta classification tests**

Use provider responses such as:

```json
{
  "candidate_added_facts": ["results_reordered"],
  "candidate_removed_facts": [],
  "visual_change_kind": "presentation"
}
```

Assert invalid values become `unknown`, failed/no-change responses remain safe, and no profile vocabulary appears in the prompt.

- [ ] **Step 2: Add failing verifier tests for a preserved abstraction**

```python
def test_verify_planning_delta_preserves_non_empty_cart_across_count_change():
    delta = verify_planning_delta(
        profile=ecommerce_checkout_profile(),
        before_signature={"cart_count": 1},
        after_signature={"cart_count": 2},
    )
    assert delta.verified_added_facts == []
    assert delta.verified_removed_facts == []
    assert delta.preserved_profile_facts == ["cart_has_items"]
```

Also assert `0 -> 1` adds `cart_has_items`, `2 -> 0` removes it, and neither transition reports it as preserved.

- [ ] **Step 3: Run focused tests and verify failure**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_visual_delta_summarizer.py tests/safesym_bridge/test_planning_fact_verifier.py
```

Expected: FAIL because the new fields do not exist.

- [ ] **Step 4: Extend the Visual Delta prompt and parser without giving it planning authority**

Require one descriptive field:

```python
"visual_change_kind": (
    "none | presentation | state_indicator | surface | mixed | unknown. "
    "Describe only the visible kind of change. Do not decide whether a graph node "
    "or planning state should be created."
)
```

Definitions in the prompt:

- `presentation`: ordering, filtering, pagination, or layout of the current content.
- `state_indicator`: a stable visible counter, badge, status, selection, or completion marker changed.
- `surface`: a page, dialog, form step, drawer, or directly executable action surface opened/closed.
- `mixed`: more than one of the above.
- `none`: no stable visible change.
- `unknown`: evidence is insufficient.

Do not pass the business profile to this prompt.

- [ ] **Step 5: Extend the local verifier and models**

Add to `PlanningDelta`:

```python
preserved_profile_facts: list[str] = field(default_factory=list)
```

When a recognized cart-count key changes positive-to-positive and the profile contains `cart_has_items`, append `cart_has_items` to this list and add deterministic evidence. This is local structured verification, not a VLM fact.

- [ ] **Step 6: Persist evidence on raw edges and keep old JSON loadable**

Add to `WebKobeEdge`:

```python
visual_change_kind: str = "unknown"
```

Set it from `visual_result.visual_change_kind` in the explorer. Update `to_dict`, compact graph artifacts, and JSON loaders. Historical graphs without either new field must load with defaults.

- [ ] **Step 7: Run evidence and serialization tests**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_visual_delta_summarizer.py tests/safesym_bridge/test_planning_fact_verifier.py tests/safesym_bridge/test_web_kobe_graph.py tests/safesym_bridge/test_web_kobe_pddl_projector.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/visual_delta.py src/ai_web_explorer/grounded_web/business_profile.py src/ai_web_explorer/grounded_web/planning_fact_verifier.py src/ai_web_explorer/grounded_web/graph.py src/ai_web_explorer/grounded_web/explorer.py src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py src/ai_web_explorer/safesym_bridge/graph_artifacts.py tests/safesym_bridge
git commit -m "Record auditable planning abstraction evidence"
```

---

### Task 3: Build the Replacement Planning Abstraction

**Files:**
- Create: `src/ai_web_explorer/grounded_web/planning_abstraction.py`
- Create: `tests/safesym_bridge/test_planning_abstraction.py`

**Interfaces:**
- Consumes: `WebKobeGraph`, optional action `EmbeddingProvider`.
- Produces: `PlanningAbstractionArtifacts(raw_graph, planning_graph, report)`.
- Produces: `PlanningAbstractionReport.raw_to_planning_node`, `planning_node_groups`, `capabilities`, `edge_mappings`, `ambiguous_actions`.
- Produces: `build_planning_state_graph(graph, embedding_provider=None) -> PlanningAbstractionArtifacts`.

- [ ] **Step 1: Write failing grouping tests for the agreed experiment**

Build a raw graph with these observations:

```text
O0 --filter[presentation]--> O1
O1 --clear[presentation]--> O2
O2 --sort[presentation]--> O3
O3 --add_to_cart[cart_has_items added]--> O4
O4 --add_to_cart[state_indicator, cart_has_items preserved]--> O5
O5 --open_unknown[surface]--> O6
```

Assert:

```python
assert report.raw_to_planning_node["O0"] == report.raw_to_planning_node["O1"]
assert report.raw_to_planning_node["O1"] == report.raw_to_planning_node["O2"]
assert report.raw_to_planning_node["O2"] == report.raw_to_planning_node["O3"]
assert report.raw_to_planning_node["O3"] != report.raw_to_planning_node["O4"]
assert report.raw_to_planning_node["O4"] == report.raw_to_planning_node["O5"]
assert report.raw_to_planning_node["O5"] != report.raw_to_planning_node["O6"]
```

- [ ] **Step 2: Write failing capability aggregation tests**

Give O0 `filter`, O1 `clear`, O2 `sort`, and O3 `add_to_cart`. Assert the planning node aggregates all four canonical actions and the report records each action's exact `observed_node_ids`. The absence of an action on another member must not be treated as negative evidence.

- [ ] **Step 3: Write failing safety tests**

Assert:

- profile added/removed facts always prevent union even if VLM says `presentation`;
- `surface`, `mixed`, and `unknown` remain separate;
- `state_indicator` only unions when `preserved_profile_facts` is non-empty and there is no verified profile boundary change;
- failed edges never cause grouping;
- ambiguous semantic action matches preserve separate earliest names;
- raw graph objects remain unchanged.

- [ ] **Step 4: Run the new test module and verify failure**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_planning_abstraction.py
```

Expected: import failure because the module does not exist.

- [ ] **Step 5: Implement the minimal grouping predicate**

Use a small union-find over raw node IDs. Only successful edges can union endpoints.

```python
def _can_share_planning_state(edge: WebKobeEdge) -> tuple[bool, str]:
    delta = edge.planning_delta
    profile_boundary_changed = bool(
        delta
        and (
            delta.verified_added_facts
            or delta.verified_removed_facts
        )
    )
    if profile_boundary_changed:
        return False, "verified_profile_boundary_changed"
    if edge.visual_change_kind == "presentation":
        return True, "presentation_only"
    if (
        edge.visual_change_kind == "state_indicator"
        and delta is not None
        and delta.preserved_profile_facts
    ):
        return True, "verified_profile_abstraction_preserved"
    return False, "insufficient_equivalence_evidence"
```

Restrict added/removed checks to locally verified facts. Never use VLM candidate fact IDs as planning boundaries.

- [ ] **Step 6: Aggregate capabilities and preserve provenance**

Normalize affordance and executed-edge action names using the existing embedding thresholds and earliest-name rule. For each planning group, build:

```python
{
    "action_name": canonical_name,
    "observed_node_ids": [member IDs where it was observed],
    "source_action_names": [original names],
}
```

Set the representative planning node's `business_affordances` to the union of canonical affordances in first-observed order. Do not claim that every capability is directly executable on every observation; that distinction remains in the report.

- [ ] **Step 7: Map edges without losing same-group capabilities**

Map raw source/target IDs through the union-find representative. Keep same-group edges in `planning_graph` as self-loops for auditability and capability discovery. Deduplicate only identical `(planning_source, canonical_action, planning_target)` edges and sum `visit_count`. The existing Phase A projector will omit self-loops from PDDL.

- [ ] **Step 8: Run the planning abstraction tests**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_planning_abstraction.py
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/planning_abstraction.py tests/safesym_bridge/test_planning_abstraction.py
git commit -m "Add conservative planning state abstraction"
```

---

### Task 4: Route Phase A Through the New Planning Graph

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
- Modify: `tests/safesym_bridge/test_behavior_state_graph_cli.py`
- Modify: `tests/safesym_bridge/test_web_kobe_pddl_projector.py`
- Modify: `tests/safesym_bridge/test_cli.py`

**Interfaces:**
- Consumes: `build_planning_state_graph` from Task 3.
- Produces in Phase A output: `raw_graph.json`, `planning_graph.json`, `planning_abstraction_report.json`, `domain.pddl`.
- Compatibility: write `canonical_graph.json` and `consolidation_report.json` for one transition release only if external scripts/tests still require those names; their contents must point to or equal the new planning artifacts and be marked deprecated in metadata.

- [ ] **Step 1: Add a failing CLI artifact test**

Use a small graph containing a presentation edge and a profile-changing edge. Run `web-kobe-phase-a`; assert:

```python
assert (output / "raw_graph.json").exists()
assert (output / "planning_graph.json").exists()
assert (output / "planning_abstraction_report.json").exists()
assert (output / "domain.pddl").exists()
```

Assert the planning graph collapses the presentation edge, retains its capability as a self-loop, and the domain includes only the cross-group profile-changing action.

- [ ] **Step 2: Run CLI tests and verify failure**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_behavior_state_graph_cli.py tests/safesym_bridge/test_cli.py tests/safesym_bridge/test_web_kobe_pddl_projector.py
```

Expected: FAIL because the new artifact names and planning abstraction are not wired.

- [ ] **Step 3: Replace the Phase A CLI path**

Replace:

```python
artifacts = consolidate_behavior_state_graph(...)
```

with:

```python
artifacts = build_planning_state_graph(
    graph,
    embedding_provider=_phase_a_embedding_provider(),
)
```

Write the raw graph, planning graph, report, and compile `domain.pddl` from `artifacts.planning_graph`.

- [ ] **Step 4: Verify PDDL capability behavior**

Keep `compile_phase_a_domain` behavior:

- planning-graph self-loops stay in the JSON graph;
- self-loops do not generate no-effect PDDL actions;
- cross-group actions use only location predicates;
- supporting facts, Visual Delta facts, `PlanningState`, and planning deltas do not enter Phase A preconditions/effects.

Add assertions that `sort`, `filter`, and `clear` remain visible in `planning_graph.json` or the report, while not appearing as no-effect actions in `domain.pddl`.

- [ ] **Step 5: Run Phase A tests**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_behavior_state_graph_cli.py tests/safesym_bridge/test_cli.py tests/safesym_bridge/test_web_kobe_pddl_projector.py tests/safesym_bridge/test_planning_abstraction.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/cli.py src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py tests/safesym_bridge/test_behavior_state_graph_cli.py tests/safesym_bridge/test_cli.py tests/safesym_bridge/test_web_kobe_pddl_projector.py
git commit -m "Project Phase A from planning state groups"
```

---

### Task 5: Remove Superseded Structures and Document the Boundary

**Files:**
- Delete: `src/ai_web_explorer/grounded_web/behavior_state_graph.py`
- Delete: `tests/safesym_bridge/test_behavior_state_graph.py`
- Delete: `src/ai_web_explorer/grounded_web/business_state_policy.py`
- Delete: `tests/safesym_bridge/test_business_state_policy.py`
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Modify: `src/ai_web_explorer/grounded_web/graph.py`
- Modify: `src/ai_web_explorer/grounded_web/visual_delta.py`
- Modify: `src/ai_web_explorer/grounded_web/__init__.py`
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
- Modify: `src/ai_web_explorer/safesym_bridge/graph_artifacts.py`
- Modify: `tests/test_grounded_web_public_api.py`
- Modify: `tests/safesym_bridge/test_web_kobe_graph.py`
- Modify: `tests/safesym_bridge/test_web_kobe_pddl_projector.py`
- Modify: `docs/current-project-overview.zh-CN.md`
- Modify: `docs/project-structure.zh-CN.md`
- Modify: `docs/project-decisions.zh-CN.md`

**Interfaces:**
- Keeps: `WebKobeGraph`, `BusinessAffordance`, `PlanningDelta`, `PlanningState`, `PlanningTransition`, profile verifier, raw Visual Delta evidence, and Phase A projector.
- Removes: old exact-action-set behavior consolidator and inactive VLM `BusinessTransition` judgment path.
- Legacy JSON: old `business_transition` keys are ignored rather than rejected.

- [ ] **Step 1: Move the observation-ID helper to its permanent location**

Place the helper in `explorer.py` or a focused observation identity module. Do not leave `business_state_policy.py` alive solely for one hash function.

- [ ] **Step 2: Remove the inactive BusinessTransition path**

Remove:

- `BusinessTransition` from `graph.py` and public exports;
- `business_transition` from new `WebKobeEdge` serialization;
- compatibility-only `VisualDeltaResult.business_transition`;
- calls to `resolve_business_target_node` and `should_materialize_business_state`;
- old unit tests that construct this dead model.

The JSON loader should tolerate and ignore a historical `business_transition` key so old experiment graphs remain readable.

- [ ] **Step 3: Remove the old behavior consolidator**

Delete the implementation and old tests after all CLI imports use `planning_abstraction.py`. Do not delete `capability_graph.py`: `Evidence`, `PageFrame`, `ObservedDelta`, `ExecutionTrace`, and capability-related types are still used by the active graph model.

- [ ] **Step 4: Update Chinese project documentation**

Document this exact flow:

```text
VLM proposes directly executable actions
→ Stagehand executes one selected action
→ raw graph records the observation transition
→ local verifier confirms known profile boundaries
→ planning abstraction conservatively groups presentation-equivalent observations
→ planning graph aggregates observed capabilities
→ Phase A projector emits only cross-planning-state transitions
```

Also document:

- profile facts are strong but incomplete semantic anchors;
- Visual Delta `visual_change_kind` is observation evidence, not a planning decision;
- `0 -> 1` cart count changes `cart_has_items`, while `1 -> 2` preserves it;
- presentation actions remain capabilities in graph artifacts even when absent from PDDL;
- unknown changes remain separate;
- the old `BusinessTransition` and exact-action-set consolidator were removed.

- [ ] **Step 5: Run targeted tests**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_planning_abstraction.py tests/safesym_bridge/test_visual_delta_summarizer.py tests/safesym_bridge/test_planning_fact_verifier.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_web_kobe_pddl_projector.py tests/safesym_bridge/test_cli.py tests/test_grounded_web_public_api.py
```

Expected: PASS.

- [ ] **Step 6: Run the full non-browser suite**

Run:

```powershell
$env:PYTHONPATH='D:\GitHUb\ai-web-explorer-main\src'
.\.venv\Scripts\python.exe -m pytest -q --ignore=tests/safesym_bridge/test_web_kobe_playwright_integration.py
```

Expected: all tests pass with only the already-known intentional skips.

- [ ] **Step 7: Generate and inspect a fixture Phase A artifact**

Run the existing local graph/fixture path through `web-kobe-phase-a`. Verify:

- raw observations remain count-preserving;
- presentation observations group together;
- `sort`, `filter`, and `clear` appear as observed capabilities;
- a verified profile boundary creates a distinct planning node;
- the domain contains only cross-group actions;
- no supporting facts or Visual Delta facts appear in Phase A PDDL.

- [ ] **Step 8: Commit**

```powershell
git add -A src/ai_web_explorer tests docs/current-project-overview.zh-CN.md docs/project-structure.zh-CN.md docs/project-decisions.zh-CN.md
git commit -m "Replace legacy behavior consolidation with planning abstraction"
```

---

## Final Acceptance Checklist

- [ ] An explicit same-URL search/filter/sort change cannot be merged into a historical node by embedding or visit-stack membership.
- [ ] Every observation node still generates candidates at most once.
- [ ] Visual Delta never sees profile facts and never writes planning facts.
- [ ] `cart_count 0 -> 1` creates a verified `cart_has_items` boundary.
- [ ] `cart_count 1 -> 2` records `cart_has_items` as preserved and stays in the same planning group when the only visible change is a state indicator.
- [ ] Presentation-only filter/sort/clear observations can share a planning group.
- [ ] Unknown, surface, and mixed changes remain separate by default.
- [ ] Planning groups aggregate all observed capabilities without treating missing candidates as negative evidence.
- [ ] Capability provenance identifies the observation nodes where each action was actually visible.
- [ ] Planning-graph self-loops retain presentation capabilities for audit.
- [ ] Phase A PDDL omits self-loops and contains only location-level cross-group transitions.
- [ ] Old raw graph JSON remains readable.
- [ ] The exact-action-set consolidator and inactive BusinessTransition path are removed.
- [ ] Targeted and full non-browser test suites pass.

