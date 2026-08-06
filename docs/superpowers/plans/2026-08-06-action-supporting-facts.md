# Action-Local Supporting Facts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make each VLM-generated business affordance carry compact action-local supporting facts, preserve those facts on the selected graph edge, and project them as PDDL action preconditions without adding them to global node state.

**Architecture:** Extend `BusinessAffordance` with `supporting_facts` and extend `BrowserAction` with the same immutable list so the selected action snapshot in `WebKobeEdge.action` contains the facts used at selection time. The affordance prompt emits only action metadata plus fact IDs; the existing post-execution `PlanningDelta` remains the sole source of observed action effects. The PDDL projector reads action-local facts for preconditions and leaves node planning state unchanged.

**Tech Stack:** Python dataclasses, JSON prompt/response parsing, pytest, existing WebKobeGraph serialization and PDDL projector.

## Global Constraints

- Keep `supporting_facts` action-local; never merge them into `PlanningState.active_facts`, `profile_fact_ids`, or `generated_fact_ids`.
- Do not expose profile facts or PDDL vocabulary in the affordance prompt.
- Do not ask VLM to predict action effects; post-execution observed facts remain in `PlanningDelta`.
- Keep legacy `expected_change` parsing compatible, but new prompts and new output must not depend on it.
- Use short, stable snake_case fact IDs and preserve raw screenshots/traces as the audit source.
- Do not introduce a new policy/observer/recorder abstraction in this change.

---

## File Map

- Modify `src/ai_web_explorer/grounded_web/graph.py`: add action-local facts to `BusinessAffordance` and the selected `BrowserAction` snapshot.
- Modify `src/ai_web_explorer/grounded_web/business_affordance.py`: change the VLM output schema and parse `supporting_facts` with bounded, normalized string values.
- Modify `src/ai_web_explorer/grounded_web/explorer.py`: copy affordance facts into the selected `BrowserAction` and remove expected-effect instructions from Stagehand execution text.
- Modify `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`: include action-local supporting facts in edge preconditions.
- Modify `tests/safesym_bridge/test_business_affordance.py`: cover the new prompt/response contract and legacy parsing.
- Modify `tests/safesym_bridge/test_web_kobe_graph.py`: cover serialization of affordance/action supporting facts.
- Modify `tests/safesym_bridge/test_web_kobe_explorer.py`: cover selection snapshot and no global-state mutation.
- Modify `tests/safesym_bridge/test_web_kobe_pddl_projector.py`: cover action-local facts as preconditions and effects remaining independent.

## Task 1: Add and Parse Action-Local Supporting Facts

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/graph.py` in `BrowserAction` and `BusinessAffordance`.
- Modify: `src/ai_web_explorer/grounded_web/business_affordance.py` in `_prompt_for_request()` and `_affordances_from_response()`.
- Test: `tests/safesym_bridge/test_business_affordance.py`.

**Interfaces:**
- Consumes: VLM JSON with `regions[].actions[].supporting_facts`.
- Produces: `BusinessAffordance.supporting_facts: list[str]` and serialized `supporting_facts`.

- [ ] **Step 1: Write the failing parser test**

Add a test response shaped as:

```json
{
  "page_mode": "single_surface",
  "regions": [{
    "region_id": "main",
    "purpose": "search",
    "actions": [{
      "intent": "search_items",
      "label": "Search",
      "target": "search input",
      "supporting_facts": ["search_input_visible", "result_collection_visible"]
    }]
  }]
}
```

Assert that the parsed affordance has exactly those two facts and that its new serialized form contains `supporting_facts`.

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
pytest tests/safesym_bridge/test_business_affordance.py -q
```

Expected: the new assertion fails because the model and parser do not yet expose `supporting_facts`.

- [ ] **Step 3: Implement the minimal model and parser change**

Add `supporting_facts: list[str] = field(default_factory=list)` to both frozen dataclasses where appropriate. In the affordance parser, accept only list values, convert each item to a trimmed string, discard empty items, preserve first-seen order, and cap the list at a small fixed bound of 8 facts per action. Add `supporting_facts` to the new prompt schema and remove `expected_effect` from the new schema. Keep the legacy `business_affordances` branch and legacy `expected_change` parsing intact.

- [ ] **Step 4: Add malformed and legacy coverage**

Add tests asserting that a non-list or empty fact value becomes `[]`, duplicate/blank values are removed, and an old `expected_change` response still parses without raising.

- [ ] **Step 5: Run focused tests**

Run:

```bash
pytest tests/safesym_bridge/test_business_affordance.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/ai_web_explorer/grounded_web/graph.py src/ai_web_explorer/grounded_web/business_affordance.py tests/safesym_bridge/test_business_affordance.py
git commit -m "Add action-local supporting facts to affordances"
```

## Task 2: Snapshot Supporting Facts on the Selected Action

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/explorer.py` in `_business_action_from_affordance()`.
- Modify: `tests/safesym_bridge/test_web_kobe_explorer.py`.
- Modify: `tests/safesym_bridge/test_web_kobe_graph.py`.

**Interfaces:**
- Consumes: `BusinessAffordance.supporting_facts` from Task 1.
- Produces: `BrowserAction.supporting_facts`, serialized through `WebKobeEdge.action`.

- [ ] **Step 1: Write the failing action snapshot test**

Create an affordance with:

```python
BusinessAffordance(
    action_name="search_items",
    label="Search",
    target_hint="search input",
    supporting_facts=["search_input_visible"],
)
```

Build the business action through the existing explorer helper or the smallest existing explorer fixture and assert `action.supporting_facts == ["search_input_visible"]`. Assert the action description does not contain an `Expected visible change:` clause.

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
pytest tests/safesym_bridge/test_web_kobe_explorer.py -k "supporting_facts or expected_visible_change" -q
```

Expected: failure because `BrowserAction` has no snapshot field and the builder still carries expected-effect text.

- [ ] **Step 3: Implement the snapshot change**

Copy `affordance.supporting_facts` into `BrowserAction.supporting_facts` in `_business_action_from_affordance()`. Include the list in `BrowserAction.to_dict()`. Remove only the expected-effect text from the new Stagehand instruction; retain target and action identity. Do not alter node candidate merging or planning-state propagation.

- [ ] **Step 4: Add graph serialization and node-isolation assertions**

Build a `WebKobeEdge` containing the selected action and assert its serialized `action.supporting_facts` is present. Assert the source node's `planning_state.active_facts` is unchanged and does not contain `search_input_visible` merely because the action carries it.

- [ ] **Step 5: Run focused tests**

Run:

```bash
pytest tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_web_kobe_graph.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/ai_web_explorer/grounded_web/explorer.py src/ai_web_explorer/grounded_web/graph.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_web_kobe_graph.py
git commit -m "Preserve supporting facts on selected graph actions"
```

## Task 3: Project Action-Local Facts as PDDL Preconditions

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py` in `_preconditions_for_edge()`.
- Test: `tests/safesym_bridge/test_web_kobe_pddl_projector.py`.

**Interfaces:**
- Consumes: `edge.action.supporting_facts` from Task 2, plus existing planning transition and observed deltas.
- Produces: PDDL action preconditions containing the action-local fact predicates.

- [ ] **Step 1: Write the failing projector test**

Construct an edge whose action has:

```python
supporting_facts=["search_input_visible", "result_collection_visible"]
```

and whose planning transition has no facts. Compile the graph and assert the corresponding PDDL action contains:

```lisp
(search_input_visible)
(result_collection_visible)
```

Also assert those facts are not added to the source node's planning state and are not emitted as effects solely because they are supporting facts.

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py -k "supporting_facts" -q
```

Expected: failure because preconditions currently come only from location, planning transition, removed facts, and optional observed deltas.

- [ ] **Step 3: Implement the minimal projector change**

In `_preconditions_for_edge()`, append one predicate per `edge.action.supporting_facts`, pass them through the existing predicate sanitizer, and deduplicate with `_unique_items()`. Do not add them to `_effects_for_edge()`. Keep current location and planning-transition behavior unchanged.

- [ ] **Step 4: Add compatibility coverage**

Assert an edge whose action has the default empty list produces the same PDDL as before. Assert action-local facts are still emitted when `planning_transition` is absent and when generated planning facts are enabled by default.

- [ ] **Step 5: Run focused tests**

Run:

```bash
pytest tests/safesym_bridge/test_web_kobe_pddl_projector.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py tests/safesym_bridge/test_web_kobe_pddl_projector.py
git commit -m "Project action supporting facts as preconditions"
```

## Task 4: Full Regression and Contract Review

**Files:**
- Modify: only the tests or implementation files above if a regression is exposed.

- [ ] **Step 1: Run the complete test suite**

Run:

```bash
pytest -q
```

Expected: the full suite passes with no new skips or warnings required by this change.

- [ ] **Step 2: Inspect serialized graph output**

Use an existing graph fixture or a focused test to confirm the JSON shape is:

```json
"action": {
  "canonical_action_name": "search_items",
  "supporting_facts": ["search_input_visible"]
}
```

and that the node's `planning_state` does not acquire the same fact automatically.

- [ ] **Step 3: Review the prompt contract**

Confirm the prompt asks for directly executable actions, treats the action limit as an upper bound, groups by functional region, and now requests only compact supporting fact IDs instead of expected effects, profile facts, PDDL terms, meanings, or evidence.

- [ ] **Step 4: Commit the final regression-only changes if needed**

```bash
git add src tests
git commit -m "Verify action-local fact projection contract"
```
