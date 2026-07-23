# Planner-Facing PDDL Projection Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make WebKobeGraph PDDL projection emit clean planner-facing artifacts that SafeSym can parse/inject and Fast Downward can solve for both base and safe PDDL.

**Architecture:** Keep WebKobeGraph as the evidence-rich exploration artifact, but make `safesym_bridge.web_kobe_pddl_projector` project only task/planning facts by default. Separate human-readable action names from unique PDDL action identity, and make STRIPS delete effects conservative by adding deleted planning facts as action preconditions.

**Tech Stack:** Python 3.11, pytest, existing `grounded_web` graph/business-profile dataclasses, SafeSym local checkout at `C:\Users\moon\Desktop\Projects\SafeSym`, Fast Downward at `C:\Users\moon\Desktop\Projects\AutoWebWorld\downward\fast-downward.py`.

## Global Constraints

- The project serves SafeSym; do not turn this into generic web-agent behavior.
- `grounded_web` owns exploration, observation, graph data, and evidence.
- `safesym_bridge` owns WebKobeGraph-to-PDDL projection and SafeSym/planner smoke validation.
- Stagehand is an operation backend and evidence source, not graph truth.
- PDDL should project only facts that help planning or safety.
- DOM/control facts, selectors, URL fragments, screenshot summaries, and LLM reasons stay as graph evidence by default.
- Safety action insertion is not required for this stage.
- Keep edits scoped; do not reintroduce legacy explore runtime or app-specific observers into the generic path.
- Keep `docs/current-project-overview.md` and `docs/current-project-overview.zh-CN.md` synchronized when project status changes.

---

## File Structure

- Modify `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
  - Add projection options.
  - Generate unique PDDL action names.
  - Project planning facts by default.
  - Stop default projection of observed/control deltas.
  - Add deleted planning facts to preconditions before deleting them.

- Modify `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py`
  - Add diagnostics for duplicate action names, projected action names, observed fact projection, and unsafe delete effects.
  - Keep the existing report fields backward-compatible.

- Modify `src/ai_web_explorer/grounded_web/business_profile.py`
  - Add lightweight generic profile fact descriptions for `required_info_missing` and `required_info_provided`.
  - Keep existing facts such as `checkout_info_complete` for compatibility.

- Modify `tests/safesym_bridge/test_web_kobe_pddl_projector.py`
  - Update tests from old DOM-delta projection behavior to planner-facing behavior.
  - Add unique-name and conservative-delete tests.

- Modify `tests/safesym_bridge/test_web_kobe_pddl_smoke.py`
  - Add smoke diagnostics tests.

- Modify `tests/safesym_bridge/test_visual_delta_summarizer.py` if it asserts the exact e-commerce profile fact set.

- Modify `docs/current-project-overview.md`
  - Correct current status and document clean planner-facing projection.

- Modify `docs/current-project-overview.zh-CN.md`
  - Synchronized Chinese update.

---

### Task 1: Add Unique Planner Action Identity

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
- Modify: `tests/safesym_bridge/test_web_kobe_pddl_projector.py`

**Interfaces:**
- Consumes: existing `compile_web_kobe_graph_to_pddl(graph, *, goal_node_id, start_node_id=None)`.
- Produces: PDDL action names in the shape `edge_001_<readable_suffix>`.
- Produces helper `_readable_action_suffix_for_edge(edge) -> str`.
- Produces helper `_unique_pddl_action_name(edge, *, index: int) -> str`.

- [ ] **Step 1: Write failing test for duplicate readable names producing unique PDDL action names**

Append this test to `tests/safesym_bridge/test_web_kobe_pddl_projector.py`:

```python
def test_compile_web_kobe_graph_to_pddl_makes_duplicate_readable_names_unique():
    graph = WebKobeGraph(
        app="example",
        start_node_id="inventory",
        total_steps_completed=2,
        nodes=[
            _node("inventory", "inventory", {}),
            _node("cart", "cart", {}),
            _node("checkout", "checkout", {}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="inventory",
                target_node_id="cart",
                instruction="open cart",
                action=BrowserAction(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_001",
                    canonical_action_name="advance_business_milestone",
                ),
                capability=None,
                target_observation="cart",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_001",
                    {},
                    "inventory",
                    "cart",
                    True,
                ),
                status="succeeded_with_observed_change",
            ),
            WebKobeEdge(
                source_node_id="cart",
                target_node_id="checkout",
                instruction="start checkout",
                action=BrowserAction(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_002",
                    canonical_action_name="advance_business_milestone",
                ),
                capability=None,
                target_observation="checkout",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_002",
                    {},
                    "cart",
                    "checkout",
                    True,
                ),
                status="succeeded_with_observed_change",
            ),
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(graph, goal_node_id="checkout")

    assert "(:action edge_001_advance_business_milestone" in artifacts.domain
    assert "(:action edge_002_advance_business_milestone" in artifacts.domain
    assert artifacts.domain.count("(:action advance_business_milestone") == 0
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py::test_compile_web_kobe_graph_to_pddl_makes_duplicate_readable_names_unique -q
```

Expected: FAIL because actions are still named directly from `canonical_action_name`.

- [ ] **Step 3: Implement unique action naming**

In `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`, replace `_pddl_action_name_for_edge` with readable suffix helpers:

```python
def _readable_action_suffix_for_edge(edge) -> str:
    if edge.pddl_hint is not None:
        return _action_name(edge.pddl_hint.action_name)
    canonical = _business_canonical_action_name(edge)
    if canonical is not None:
        return canonical
    if _is_order_completion_edge(edge):
        return "order_place_confirm"
    fallback = _action_name(edge.action.semantic_id)
    return fallback or "transition"


def _unique_pddl_action_name(edge, *, index: int) -> str:
    suffix = _readable_action_suffix_for_edge(edge)
    return f"edge_{index:03d}_{suffix}"
```

Then in `compile_web_kobe_graph_to_pddl`, change the action loop to enumerate only projectable edges:

```python
    projectable_edges = [edge for edge in graph.edges if _is_projectable_edge(edge)]
    action_blocks = []
    for index, edge in enumerate(projectable_edges, start=1):
        action_name = _unique_pddl_action_name(edge, index=index)
        preconditions = [f"({_at(edge.source_node_id)})"]
        effects = _effects_for_edge(edge)
        action_blocks.append(
            "\n".join(
                [
                    f"  (:action {action_name}",
                    f"    :precondition (and {' '.join(preconditions)})",
                    f"    :effect (and {' '.join(effects)})",
                    "  )",
                ]
            )
        )
```

- [ ] **Step 4: Update older action-name tests**

In `tests/safesym_bridge/test_web_kobe_pddl_projector.py`, update assertions that expect exact old action names. For example:

```python
assert "(:action add_to_cart_product" in artifacts.domain
```

becomes:

```python
assert "(:action edge_001_add_to_cart_product" in artifacts.domain
```

Update these tests similarly:

- `test_compile_web_kobe_graph_to_pddl_uses_page_and_boolean_delta`
- `test_compile_web_kobe_graph_to_pddl_projects_successful_navigation_edges`
- `test_compile_web_kobe_graph_to_pddl_prefers_pddl_action_hint_name`
- `test_compile_web_kobe_graph_to_pddl_maps_order_completion_for_safesym`
- `test_compile_web_kobe_graph_to_pddl_excludes_non_projectable_edges`
- `test_compile_web_kobe_graph_to_pddl_prefers_business_canonical_action_name`
- `test_compile_web_kobe_graph_to_pddl_ignores_ui_level_canonical_action_name`

Use these expected shapes:

```python
"(:action edge_001_submit_final_order"
"(:action edge_001_order_place_confirm"
"(:action edge_001_submit_application"
"(:action edge_001_stagehand_business_milestone_001"
```

- [ ] **Step 5: Run projector tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py tests/safesym_bridge/test_web_kobe_pddl_projector.py
git commit -m "feat: make pddl action names unique"
```

---

### Task 2: Project Planning Facts Instead Of Observed DOM Facts

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
- Modify: `tests/safesym_bridge/test_web_kobe_pddl_projector.py`

**Interfaces:**
- Produces `PddlProjectionOptions`.
- `compile_web_kobe_graph_to_pddl` gains keyword-only parameter `options: PddlProjectionOptions | None = None`.
- Default behavior: `include_observed_delta_facts=False`.
- Diagnostic compatibility: callers may pass `PddlProjectionOptions(include_observed_delta_facts=True)`.

- [ ] **Step 1: Write failing test that observed control facts are not projected by default**

Replace `test_compile_web_kobe_graph_to_pddl_declares_predicates_from_effect_deltas` with:

```python
def test_compile_web_kobe_graph_to_pddl_does_not_project_observed_control_facts_by_default():
    graph = WebKobeGraph(
        app="example",
        start_node_id="cart",
        total_steps_completed=1,
        nodes=[
            _node("cart", "cart", {"cart_visible": True}),
            _node("checkout", "checkout", {"cart_visible": False}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="cart",
                target_node_id="checkout",
                instruction="begin checkout",
                action=BrowserAction("click", "#checkout", "begin_checkout"),
                capability=None,
                target_observation="checkout page",
                observed_delta=[
                    ObservedDelta(
                        "control_place_order_enabled",
                        None,
                        True,
                        "control_availability_changed",
                        evidence=[Evidence(source="unit_test")],
                    )
                ],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "click",
                    "#checkout",
                    "checkout",
                    {},
                    "cart",
                    "checkout",
                    True,
                ),
                planning_delta=PlanningDelta(
                    candidate_added_facts=["checkout_started"],
                    evidence=["checkout page became visible"],
                ),
                status="succeeded_with_observed_change",
            )
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(graph, goal_node_id="checkout")

    assert "(checkout_started)" in artifacts.domain
    assert "control_place_order_enabled" not in artifacts.domain
```

- [ ] **Step 2: Write compatibility test for observed facts option**

Append:

```python
def test_compile_web_kobe_graph_to_pddl_can_include_observed_facts_for_diagnostics():
    from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
        PddlProjectionOptions,
    )

    graph = WebKobeGraph(
        app="example",
        start_node_id="cart",
        total_steps_completed=1,
        nodes=[
            _node("cart", "cart", {}),
            _node("checkout", "checkout", {}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="cart",
                target_node_id="checkout",
                instruction="begin checkout",
                action=BrowserAction("click", "#checkout", "begin_checkout"),
                capability=None,
                target_observation="checkout page",
                observed_delta=[
                    ObservedDelta(
                        "control_place_order_enabled",
                        None,
                        True,
                        "control_availability_changed",
                        evidence=[Evidence(source="unit_test")],
                    )
                ],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "click",
                    "#checkout",
                    "checkout",
                    {},
                    "cart",
                    "checkout",
                    True,
                ),
                status="succeeded_with_observed_change",
            )
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(
        graph,
        goal_node_id="checkout",
        options=PddlProjectionOptions(include_observed_delta_facts=True),
    )

    assert "(control_place_order_enabled)" in artifacts.domain
```

- [ ] **Step 3: Run the failing tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py::test_compile_web_kobe_graph_to_pddl_does_not_project_observed_control_facts_by_default tests/safesym_bridge/test_web_kobe_pddl_projector.py::test_compile_web_kobe_graph_to_pddl_can_include_observed_facts_for_diagnostics -q
```

Expected: FAIL because `PddlProjectionOptions` does not exist and observed deltas are still projected.

- [ ] **Step 4: Add projection options**

In `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`, add:

```python
@dataclass(frozen=True)
class PddlProjectionOptions:
    include_observed_delta_facts: bool = False
```

Change the compile signature:

```python
def compile_web_kobe_graph_to_pddl(
    graph: WebKobeGraph,
    *,
    goal_node_id: str,
    start_node_id: str | None = None,
    options: PddlProjectionOptions | None = None,
) -> WebKobePddlArtifacts:
```

Inside the function, add:

```python
    options = options or PddlProjectionOptions()
```

- [ ] **Step 5: Split observed and planning effect predicates**

Replace `_effect_predicates_for_edge` and `_effects_for_edge` with option-aware versions:

```python
def _observed_effect_predicates_for_edge(edge) -> list[str]:
    predicates = []
    for delta in edge.observed_delta:
        change = _delta_predicate_change(delta)
        if change is not None:
            predicates.append(change[0])
    return predicates


def _planning_effect_predicates_for_edge(edge) -> list[str]:
    predicates = []
    if edge.planning_delta is not None:
        predicates.extend(
            _predicate(fact)
            for fact in _trusted_added_planning_facts(edge.planning_delta)
        )
        predicates.extend(
            _predicate(fact)
            for fact in _trusted_removed_planning_facts(edge.planning_delta)
        )
    return predicates


def _effect_predicates_for_edge(
    edge,
    *,
    options: PddlProjectionOptions,
) -> list[str]:
    predicates = []
    if options.include_observed_delta_facts:
        predicates.extend(_observed_effect_predicates_for_edge(edge))
    predicates.extend(_planning_effect_predicates_for_edge(edge))
    return predicates
```

Update `_is_order_completion_edge` to call:

```python
effect_predicates = set(
    _effect_predicates_for_edge(edge, options=PddlProjectionOptions())
)
```

- [ ] **Step 6: Make effects option-aware**

Change `_effects_for_edge`:

```python
def _effects_for_edge(
    edge,
    *,
    options: PddlProjectionOptions,
) -> list[str]:
    effects = [
        f"(not ({_at(edge.source_node_id)}))",
        f"({_at(edge.target_node_id)})",
    ]
    if options.include_observed_delta_facts:
        for delta in edge.observed_delta:
            change = _delta_predicate_change(delta)
            if change is None:
                continue
            pred, becomes_true = change
            if becomes_true:
                effects.append(f"({pred})")
            else:
                effects.append(f"(not ({pred}))")
    if edge.planning_delta is not None:
        for fact in _trusted_added_planning_facts(edge.planning_delta):
            effects.append(f"({_predicate(fact)})")
        for fact in _trusted_removed_planning_facts(edge.planning_delta):
            effects.append(f"(not ({_predicate(fact)}))")
    return _unique_items(effects)
```

In `compile_web_kobe_graph_to_pddl`, update calls:

```python
predicate_names.update(_effect_predicates_for_edge(edge, options=options))
effects = _effects_for_edge(edge, options=options)
```

- [ ] **Step 7: Update positive numeric observed-delta tests**

`test_compile_web_kobe_graph_to_pddl_projects_positive_numeric_facts` should pass `PddlProjectionOptions(include_observed_delta_facts=True)` because numeric observed deltas are now diagnostic mode:

```python
from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
    PddlProjectionOptions,
)

artifacts = compile_web_kobe_graph_to_pddl(
    graph,
    goal_node_id="filled",
    options=PddlProjectionOptions(include_observed_delta_facts=True),
)
```

- [ ] **Step 8: Run projector tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py tests/safesym_bridge/test_web_kobe_pddl_projector.py
git commit -m "feat: project planning facts to pddl by default"
```

---

### Task 3: Make Planning Delete Effects STRIPS-Safe

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
- Modify: `tests/safesym_bridge/test_web_kobe_pddl_projector.py`

**Interfaces:**
- Produces helper `_preconditions_for_edge(edge, *, options: PddlProjectionOptions) -> list[str]`.
- Delete effects for removed planning facts are accompanied by matching positive preconditions.

- [ ] **Step 1: Write failing test for deleted planning fact preconditions**

Append:

```python
def test_compile_web_kobe_graph_to_pddl_requires_removed_planning_facts():
    graph = WebKobeGraph(
        app="example",
        start_node_id="inventory",
        total_steps_completed=2,
        nodes=[
            _node("inventory", "inventory", {}),
            _node("cart", "cart", {}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="inventory",
                target_node_id="cart",
                instruction="open cart",
                action=BrowserAction(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_001",
                    canonical_action_name="open_cart",
                ),
                capability=None,
                target_observation="cart",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_001",
                    {},
                    "inventory",
                    "cart",
                    True,
                ),
                planning_delta=PlanningDelta(
                    candidate_added_facts=["cart_page_visible"],
                    candidate_removed_facts=["product_list_visible"],
                    evidence=["cart page replaced product list"],
                ),
                status="succeeded_with_observed_change",
            )
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(graph, goal_node_id="cart")

    assert (
        ":precondition (and (at_inventory) (product_list_visible))"
        in artifacts.domain
    )
    assert "(not (product_list_visible))" in artifacts.domain
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py::test_compile_web_kobe_graph_to_pddl_requires_removed_planning_facts -q
```

Expected: FAIL because removed planning facts are not added to preconditions.

- [ ] **Step 3: Add precondition helper**

In `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`, add:

```python
def _removed_planning_predicates_for_edge(edge) -> list[str]:
    if edge.planning_delta is None:
        return []
    return [
        _predicate(fact)
        for fact in _trusted_removed_planning_facts(edge.planning_delta)
    ]


def _preconditions_for_edge(
    edge,
    *,
    options: PddlProjectionOptions,
) -> list[str]:
    preconditions = [f"({_at(edge.source_node_id)})"]
    for predicate in _removed_planning_predicates_for_edge(edge):
        preconditions.append(f"({predicate})")
    if options.include_observed_delta_facts:
        for delta in edge.observed_delta:
            change = _delta_predicate_change(delta)
            if change is None:
                continue
            pred, becomes_true = change
            if not becomes_true:
                preconditions.append(f"({pred})")
    return _unique_items(preconditions)
```

- [ ] **Step 4: Use precondition helper in action blocks**

In the action loop, replace:

```python
preconditions = [f"({_at(edge.source_node_id)})"]
```

with:

```python
preconditions = _preconditions_for_edge(edge, options=options)
```

- [ ] **Step 5: Run projector tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py -q
```

Expected: PASS.

- [ ] **Step 6: Run diagnostic Fast Downward smoke on latest output if available**

If `outputs/latest/ecommerce_stagehand_graph.json` exists in the active repo, run:

```powershell
.\.venv\Scripts\python.exe -m ai_web_explorer.safesym_bridge.cli web-kobe-pddl-smoke `
  --graph outputs/latest/ecommerce_stagehand_graph.json `
  --output outputs/latest/pddl_smoke `
  --goal-node swag_labs__6b282bea9d
```

Expected: command exits 0 and writes `outputs/latest/pddl_smoke/domain.pddl`.

- [ ] **Step 7: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py tests/safesym_bridge/test_web_kobe_pddl_projector.py
git commit -m "fix: make pddl delete effects strips safe"
```

---

### Task 4: Expand Lightweight E-Commerce Profile Facts

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/business_profile.py`
- Modify: `tests/safesym_bridge/test_visual_delta_summarizer.py` if exact fact lists fail.

**Interfaces:**
- `ecommerce_checkout_profile()` includes `required_info_missing` and `required_info_provided`.
- Existing `checkout_info_complete` remains available.

- [ ] **Step 1: Add profile test or inspect existing profile assertions**

Run:

```powershell
rg -n "checkout_info_complete|required_info|ecommerce_checkout_profile|planning_facts" tests -S
```

If there is already a profile test file, add the assertion there. If not, append this test to `tests/safesym_bridge/test_visual_delta_summarizer.py`:

```python
def test_ecommerce_profile_includes_lightweight_required_info_facts():
    from ai_web_explorer.grounded_web.business_profile import (
        ecommerce_checkout_profile,
    )

    profile = ecommerce_checkout_profile()
    facts = {fact.fact_id for fact in profile.planning_facts}

    assert "required_info_missing" in facts
    assert "required_info_provided" in facts
    assert "checkout_info_complete" in facts
```

- [ ] **Step 2: Run the failing test**

Run the exact test file that now contains the assertion:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_visual_delta_summarizer.py::test_ecommerce_profile_includes_lightweight_required_info_facts -q
```

Expected: FAIL because the two required-info facts are not yet in the profile.

- [ ] **Step 3: Add fact descriptions**

In `src/ai_web_explorer/grounded_web/business_profile.py`, add these `PlanningFactSpec` entries after `checkout_started` and before `checkout_info_complete`:

```python
        PlanningFactSpec(
            fact_id="required_info_missing",
            meaning=(
                "Required checkout, contact, shipping, or account information "
                "appears incomplete or still needs user input."
            ),
            related_stages=["checkout_info"],
            evidence_hints=[
                _hint("form", "Required fields appear empty or invalid."),
                _hint("message", "A validation message asks for missing information."),
            ],
            safety_relevance="information_verification",
        ),
        PlanningFactSpec(
            fact_id="required_info_provided",
            meaning=(
                "Required checkout, contact, shipping, or account information "
                "appears to have been provided."
            ),
            related_stages=["checkout_info", "order_review"],
            evidence_hints=[
                _hint("form", "Required fields have non-empty values."),
                _hint(
                    "navigation",
                    "The flow advances past information entry toward review.",
                ),
            ],
            safety_relevance="information_verification",
        ),
```

- [ ] **Step 4: Run profile-related tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_visual_delta_summarizer.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/business_profile.py tests/safesym_bridge/test_visual_delta_summarizer.py
git commit -m "feat: expand ecommerce planning fact profile"
```

---

### Task 5: Add PDDL Smoke Diagnostics

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py`
- Modify: `tests/safesym_bridge/test_web_kobe_pddl_smoke.py`

**Interfaces:**
- `WebKobePddlSmokeReport.to_dict()` includes:
  - `projected_action_names: list[str]`
  - `duplicate_action_names: list[str]`
  - `projected_observed_fact_count: int`
  - `unsafe_delete_effects: list[str]`
- Existing fields remain unchanged.

- [ ] **Step 1: Write diagnostics test**

Append to `tests/safesym_bridge/test_web_kobe_pddl_smoke.py`:

```python
def test_analyze_web_kobe_pddl_smoke_reports_action_and_fact_diagnostics():
    graph = _graph([_edge("empty", "filled", "add_to_cart")])

    report = analyze_web_kobe_pddl_smoke(graph, goal_node_id="filled")

    data = report.to_dict()
    assert data["projected_action_names"] == ["edge_001_add_to_cart"]
    assert data["duplicate_action_names"] == []
    assert data["projected_observed_fact_count"] == 0
    assert data["unsafe_delete_effects"] == []
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_smoke.py::test_analyze_web_kobe_pddl_smoke_reports_action_and_fact_diagnostics -q
```

Expected: FAIL because the report does not expose these fields.

- [ ] **Step 3: Extend report dataclass**

In `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py`, add fields:

```python
    projected_action_names: list[str] = field(default_factory=list)
    duplicate_action_names: list[str] = field(default_factory=list)
    projected_observed_fact_count: int = 0
    unsafe_delete_effects: list[str] = field(default_factory=list)
```

Add them to `to_dict()`:

```python
            "projected_action_names": list(self.projected_action_names),
            "duplicate_action_names": list(self.duplicate_action_names),
            "projected_observed_fact_count": self.projected_observed_fact_count,
            "unsafe_delete_effects": list(self.unsafe_delete_effects),
```

- [ ] **Step 4: Add simple PDDL text diagnostics**

Add helper functions:

```python
def _projected_action_names(domain: str) -> list[str]:
    return re.findall(r"\(:action\s+([^\s()]+)", domain)


def _duplicate_action_names(domain: str) -> list[str]:
    names = _projected_action_names(domain)
    return sorted({name for name in names if names.count(name) > 1})


def _projected_observed_fact_count(domain: str) -> int:
    return len(re.findall(r"\(control_[a-zA-Z0-9_]+\)", domain))


def _unsafe_delete_effects(domain: str) -> list[str]:
    results: list[str] = []
    for block in domain.split("  (:action ")[1:]:
        action_name = block.splitlines()[0].strip()
        precondition_block = ""
        effect_block = ""
        if ":precondition" in block and ":effect" in block:
            precondition_block = block.split(":precondition", 1)[1].split(
                ":effect",
                1,
            )[0]
            effect_block = block.split(":effect", 1)[1]
        for predicate in re.findall(r"\(not\s+\(([a-zA-Z][a-zA-Z0-9_]*)\)\)", effect_block):
            if predicate.startswith("at_"):
                continue
            if f"({predicate})" not in precondition_block:
                results.append(f"{action_name}:{predicate}")
    return sorted(results)
```

- [ ] **Step 5: Wire diagnostics into `analyze_web_kobe_pddl_smoke`**

After artifacts are compiled:

```python
    action_names = _projected_action_names(artifacts.domain)
    duplicate_action_names = _duplicate_action_names(artifacts.domain)
    projected_observed_fact_count = _projected_observed_fact_count(artifacts.domain)
    unsafe_delete_effects = _unsafe_delete_effects(artifacts.domain)
```

Pass fields to `WebKobePddlSmokeReport`:

```python
        projected_action_names=action_names,
        duplicate_action_names=duplicate_action_names,
        projected_observed_fact_count=projected_observed_fact_count,
        unsafe_delete_effects=unsafe_delete_effects,
```

- [ ] **Step 6: Make diagnostics affect planning readiness**

Update `_failure_reasons` signature to accept:

```python
duplicate_action_names: list[str],
unsafe_delete_effects: list[str],
```

Add:

```python
    if duplicate_action_names:
        reasons.append(
            "domain has duplicate action names: "
            + ", ".join(duplicate_action_names)
        )
    if unsafe_delete_effects:
        reasons.append(
            "domain has delete effects without matching preconditions: "
            + ", ".join(unsafe_delete_effects)
        )
```

Update the call in `analyze_web_kobe_pddl_smoke`.

- [ ] **Step 7: Run smoke tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_smoke.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py tests/safesym_bridge/test_web_kobe_pddl_smoke.py
git commit -m "feat: add pddl smoke diagnostics"
```

---

### Task 6: Update Docs To Match Real Planner-Facing Status

**Files:**
- Modify: `docs/current-project-overview.md`
- Modify: `docs/current-project-overview.zh-CN.md`

**Interfaces:**
- Documentation states clean projection status accurately in both languages.

- [ ] **Step 1: Update English overview**

In `docs/current-project-overview.md`, update the Stagehand business-milestone caveats and current limitations to state:

```text
The latest planner-facing hardening changes make PDDL action names unique and
project profile planning facts by default. DOM/control observed deltas remain
graph evidence and are not default planner-facing predicates.
```

Also replace any claim that the latest milestone run had no duplicate actions
or solved through Fast Downward before this hardening with:

```text
Before hardening, SafeSym parse/inject could consume the generated PDDL, but
Fast Downward solve exposed projection-layer issues: duplicate readable action
names and delete effects for facts not established in preconditions.
```

- [ ] **Step 2: Update Chinese overview**

In `docs/current-project-overview.zh-CN.md`, add the synchronized Chinese status:

```text
最新的 planner-facing hardening 让 PDDL action name 由代码唯一化，并默认只投影
profile planning facts。DOM/control observed_delta 保留为图上的证据，不再默认进入
planner-facing predicates。
```

Also include:

```text
hardening 之前，SafeSym parse/inject 可以消费生成的 PDDL，但 Fast Downward solve
暴露了投影层问题：可读 action name 重复，以及 delete effect 删除了 precondition
中没有建立为真的 fact。
```

- [ ] **Step 3: Check synchronized terminology**

Run:

```powershell
Select-String -Path docs/current-project-overview.md,docs/current-project-overview.zh-CN.md -Pattern "planner-facing hardening|duplicate action|observed_delta|Fast Downward"
```

Expected: both files contain matching status updates.

- [ ] **Step 4: Commit**

```powershell
git add docs/current-project-overview.md docs/current-project-overview.zh-CN.md
git commit -m "docs: update pddl projection status"
```

---

### Task 7: Run Full Local Verification

**Files:**
- No source changes expected.
- Writes: `outputs/latest/pddl_smoke/*` if the latest graph exists.

**Interfaces:**
- Verifies all modified code and the B-stage acceptance criteria.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests/safesym_bridge/test_web_kobe_pddl_projector.py `
  tests/safesym_bridge/test_web_kobe_pddl_smoke.py `
  tests/safesym_bridge/test_visual_delta_summarizer.py `
  -q
```

Expected: PASS.

- [ ] **Step 2: Run broader retained safesym_bridge tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge -q
```

Expected: PASS or only known sandbox browser skips/failures that are unrelated to projection. If a Playwright browser spawn fails with EPERM in restricted sandbox, rerun with external permission or report it explicitly.

- [ ] **Step 3: Regenerate PDDL smoke from latest graph**

If `outputs/latest/ecommerce_stagehand_graph.json` exists, run:

```powershell
.\.venv\Scripts\python.exe -m ai_web_explorer.safesym_bridge.cli web-kobe-pddl-smoke `
  --graph outputs/latest/ecommerce_stagehand_graph.json `
  --output outputs/latest/pddl_smoke `
  --goal-node swag_labs__6b282bea9d
```

Expected `outputs/latest/pddl_smoke/smoke_report.json`:

```json
{
  "planning_ready": true,
  "duplicate_action_names": [],
  "projected_observed_fact_count": 0,
  "unsafe_delete_effects": []
}
```

- [ ] **Step 4: Run SafeSym parser/injection/planner smoke**

Run:

```powershell
.\.venv\Scripts\python.exe -m ai_web_explorer.safesym_bridge.cli web-kobe-safesym-smoke `
  --task-dir outputs/latest/pddl_smoke `
  --safesym-root C:\Users\moon\Desktop\Projects\SafeSym `
  --rules C:\Users\moon\Desktop\Projects\SafeSym\configs\constraint_rules.json `
  --fast-downward C:\Users\moon\Desktop\Projects\AutoWebWorld\downward\fast-downward.py
```

Expected `outputs/latest/pddl_smoke/safesym_smoke_report.json`:

```json
{
  "safesym_parse_ready": true,
  "safety_injection_ready": true,
  "base_plan_ready": true,
  "safe_plan_ready": true,
  "failure_reasons": []
}
```

`safety_actions_inserted` may remain `false` in this stage.

- [ ] **Step 5: Check formatting and whitespace**

Run:

```powershell
.\.venv\Scripts\python.exe -m black --check src tests
git diff --check
```

Expected: black passes. `git diff --check` reports no new whitespace errors; CRLF warnings are acceptable only if they match existing repository behavior and do not indicate trailing whitespace.

- [ ] **Step 6: Final commit if verification changed docs or smoke snapshots intentionally**

If no files changed during verification, skip this step. If documentation or checked-in artifacts changed intentionally:

```powershell
git add <changed-files>
git commit -m "test: verify pddl planner-facing smoke"
```

---

## Self-Review

- Spec coverage: The tasks cover unique action identity, profile-only fact projection, conservative delete effects, smoke diagnostics, profile fact descriptions, docs synchronization, and SafeSym/Fast Downward acceptance.
- Placeholder scan: This plan intentionally contains no TBD/TODO/FIXME placeholders. Every task has exact files, tests, commands, and expected results.
- Type consistency: New interfaces are `PddlProjectionOptions`, `_unique_pddl_action_name`, `_readable_action_suffix_for_edge`, `_preconditions_for_edge`, and option-aware effect helpers. Later tasks use the same names.
