# VLM State Label Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the existing visual-affordance VLM name Phase A GUI states from the current screenshot, preserve the first name on revisits, and remove the naming paths this replaces.

**Architecture:** Extend `VisualAffordanceResult` with one optional `state_label`. Apply it only while recording the current node's first visual affordance observation; target matching and node identity remain unchanged. Remove profile/action-derived node labels and the disabled standalone semantic-naming pipeline, while keeping graph naming fields and generic PDDL identifier sanitization.

**Tech Stack:** Python 3.11+, dataclasses, pytest, existing WebKobeGraph explorer and VLM JSON provider.

## Global Constraints

- State labels describe only the currently visible GUI state, never the action path.
- The VLM receives no profile facts or global planning state in its prompt.
- Labels never participate in node identity, target matching, or deduplication.
- Do not retain product names, search terms, item counts, or other concrete business objects in labels.
- A revisited node keeps the earliest accepted label.
- First version has no vocabulary, label embeddings, or semantic label merge.
- Cleanup is limited to naming designs directly replaced by this change.

---

## File Map

- Modify `src/ai_web_explorer/grounded_web/business_affordance.py`: request `state_label`, parse it independently from action candidates.
- Modify `src/ai_web_explorer/grounded_web/explorer.py`: apply the VLM label to the currently observed node and preserve existing labels on revisit.
- Modify `src/ai_web_explorer/grounded_web/business_state_policy.py`: stop deriving `node_label` from planning facts or arrival actions.
- Modify `src/ai_web_explorer/grounded_web/business_profile.py`: remove the obsolete `state_label_hint` field and profile values.
- Delete `src/ai_web_explorer/grounded_web/semantic_naming.py`: remove the redundant standalone naming call.
- Modify `src/ai_web_explorer/grounded_web/__init__.py`, `src/ai_web_explorer/safesym_bridge/browser_runner.py`, and `src/ai_web_explorer/safesym_bridge/cli.py`: remove standalone naming imports, options, and wiring.
- Modify focused tests under `tests/safesym_bridge/` to cover the new path and delete obsolete expectations.

### Task 1: Parse a Free VLM State Label

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/business_affordance.py`
- Test: `tests/safesym_bridge/test_business_affordance.py`

**Interfaces:**
- Produces: `VisualAffordanceResult.state_label: str | None`.
- Keeps: action candidate parsing and `state_summary` behavior unchanged.

- [ ] **Step 1: Write failing parsing and prompt tests**

Add a test response with top-level `"state_label":"product_list_sorted"`, assert `result.state_label == "product_list_sorted"`, and assert the decoded prompt schema contains `state_label`. Also add a response with a non-string label and assert it yields `None` without losing parsed actions.

```python
assert payload["output_schema"]["state_label"] == "short snake_case visible state name"
assert result.state_label == "product_list_sorted"
assert [item.action_name for item in result.business_affordances] == ["sort_products"]
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `pytest tests/safesym_bridge/test_business_affordance.py -q`

Expected: failure because `VisualAffordanceResult` has no `state_label` and the schema does not request it.

- [ ] **Step 3: Add the minimal result field and prompt contract**

Add `state_label: str | None = None` to `VisualAffordanceResult`. In `_prompt_for_request`, request a top-level label and add instructions that it must be short English `snake_case`, describe only the visible state, and omit action history, concrete objects, search terms, and counts.

Parse only actual strings so dictionaries/lists cannot become misleading labels:

```python
def _optional_string(value: Any) -> str | None:
    return _clean_text(value) if isinstance(value, str) else None
```

Return `state_label=_optional_string(parsed.get("state_label"))`. Do not reject the whole VLM response when the field is absent or invalid.

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/safesym_bridge/test_business_affordance.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/business_affordance.py tests/safesym_bridge/test_business_affordance.py
git commit -m "Add VLM state labels to visual observations"
```

### Task 2: Apply Labels Without Renaming Revisits

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Test: `tests/safesym_bridge/test_web_kobe_explorer.py`

**Interfaces:**
- Consumes: `VisualAffordanceResult.state_label` from Task 1.
- Produces: a technical-only helper such as `_safe_vlm_state_label(value: str | None, fallback: str) -> str`.

- [ ] **Step 1: Write failing explorer tests**

Add a test where the visual-affordance provider returns `state_label=product_list_sorted`; after `_record_source_business_affordances`, assert the source node uses that label and its identity is unchanged.

Add a revisit test with an already observed node whose label is `product_list`; return a different VLM label and assert the stored label remains `product_list`. The test should also assert `node_id` is unchanged.

Add an invalid-label test such as `"!!!"` and assert the existing deterministic node label remains in place.

- [ ] **Step 2: Run the focused tests and verify failure**

Run the exact new tests with `pytest tests/safesym_bridge/test_web_kobe_explorer.py -q -k "state_label or revisit_label"`.

Expected: the VLM label is not yet written to the node.

- [ ] **Step 3: Apply only technical normalization**

Use the existing `slug_identifier` utility. Do not add semantic rules or a vocabulary.

```python
def _safe_vlm_state_label(value: str | None, *, fallback: str) -> str:
    if value:
        cleaned = slug_identifier(value, fallback="")
        if cleaned:
            return cleaned
    return slug_identifier(fallback, fallback="state")
```

In `_record_source_business_affordances`, set the VLM label only during the node's first successful visual-affordance recording. Keep the current early return for an already populated `business_affordances` list, and when merging an existing matched node always prefer `existing.node_label` as `_match_existing_target_node` already does.

Use the existing deterministic `source_node.node_label`, then `page_type`, then `node_id` as the fallback input. Do not introduce a new persisted counter.

Set `naming_provenance={"source": "visual_affordance_vlm"}` only when a valid VLM label is accepted; otherwise preserve existing provenance.

- [ ] **Step 4: Run explorer tests**

Run: `pytest tests/safesym_bridge/test_web_kobe_explorer.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/explorer.py tests/safesym_bridge/test_web_kobe_explorer.py
git commit -m "Use visual observations for state labels"
```

### Task 3: Remove Profile- and Action-Derived State Labels

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/business_state_policy.py`
- Modify: `src/ai_web_explorer/grounded_web/business_profile.py`
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Test: `tests/safesym_bridge/test_business_state_policy.py`
- Test: `tests/safesym_bridge/test_business_profile.py`

**Interfaces:**
- Changes: `resolve_business_target_node(...)` no longer accepts `state_label_hints`.
- Keeps: `_business_state_node_id(...)` behavior unchanged; action names may remain part of runtime identity in this task.

- [ ] **Step 1: Replace old naming tests with preservation tests**

Delete assertions that expect `cart_page_visible` or `open_product_details` to become the node label. Add one test proving a materialized business state retains the candidate's current visible-state label:

```python
target = resolve_business_target_node(
    source_node=_node("shopping"),
    candidate_node=_node("shopping_after", node_label="product_list_sorted"),
    business_transition=BusinessTransition(
        action_name="open_cart", relevance="core", meaningful_change=True
    ),
    planning_transition=PlanningTransition(added_facts=["cart_page_visible"]),
)
assert target.node_label == "product_list_sorted"
```

Keep the existing node identity assertions so cleanup does not accidentally change graph identity.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `pytest tests/safesym_bridge/test_business_state_policy.py tests/safesym_bridge/test_business_profile.py -q`

Expected: old profile label hints and label derivation are still present.

- [ ] **Step 3: Remove only replaced naming code**

In `resolve_business_target_node`, stop replacing `candidate_node.node_label`; only replace its business node ID. Remove `_business_state_node_label`, `_label_from_planning_transition`, `_generic_fact_label`, and the `state_label_hints` parameter.

Keep `_label_from_business_action` because `_business_state_node_id` still uses it for runtime identity. This task must not redesign IDs.

Remove `_state_label_hints_from_profile` and its call site from `explorer.py`.

Remove `PlanningFactSpec.state_label_hint`, its `to_dict()` entry, all `state_label_hint=` values in `ecommerce_checkout_profile()`, and tests that only validate those values. Keep every planning fact itself.

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/safesym_bridge/test_business_state_policy.py tests/safesym_bridge/test_business_profile.py tests/safesym_bridge/test_web_kobe_explorer.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/business_state_policy.py src/ai_web_explorer/grounded_web/business_profile.py src/ai_web_explorer/grounded_web/explorer.py tests/safesym_bridge/test_business_state_policy.py tests/safesym_bridge/test_business_profile.py
git commit -m "Remove obsolete state label derivation"
```

### Task 4: Delete the Redundant Standalone Naming Pipeline

**Files:**
- Delete: `src/ai_web_explorer/grounded_web/semantic_naming.py`
- Delete: `tests/safesym_bridge/test_semantic_naming.py`
- Modify: `src/ai_web_explorer/grounded_web/__init__.py`
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Modify: `tests/safesym_bridge/test_web_kobe_explorer.py`
- Modify: `tests/safesym_bridge/test_browser_runner.py`
- Modify: `tests/safesym_bridge/test_cli.py`

**Interfaces:**
- Removes: `SemanticNamingProvider`, `--deepseek-semantic-naming`, and `--semantic-naming-model`.
- Keeps: `node_label`, `state_summary`, `canonical_action_name`, and `naming_provenance` graph fields.

- [ ] **Step 1: Add a guard test for the supported naming path**

In `test_cli.py`, assert the parser no longer exposes the two standalone naming options. In the explorer test from Task 2, keep the assertion that visual-affordance naming works without a second naming provider.

- [ ] **Step 2: Remove the standalone pipeline and wiring**

Delete `semantic_naming.py` and its dedicated tests. Remove imports/exports, constructor parameters, browser-runner arguments, CLI flags, provider construction, and tests that exist only for that option.

Do not delete graph fields or `slug_identifier`. Do not alter business-affordance action names, action embedding deduplication, target matching, or the PDDL projector.

- [ ] **Step 3: Search for stale references**

Run:

```powershell
rg -n "semantic_naming|deepseek-semantic-naming|semantic-naming-model|state_label_hint" src tests docs --glob '!docs/superpowers/**'
```

Expected: no runtime or test references. Historical experiment artifacts are out of scope.

- [ ] **Step 4: Run the full test suite**

Run: `pytest -q`

Expected: all tests pass, with only previously documented skips.

- [ ] **Step 5: Inspect the resulting diff for scope**

Run: `git diff --stat` and `git diff --check`.

Expected: changes are limited to state naming, obsolete naming wiring, and their tests; no exploration, matching, compact graph, or PDDL behavior is redesigned.

- [ ] **Step 6: Commit**

```powershell
git add src/ai_web_explorer tests/safesym_bridge
git commit -m "Remove standalone semantic naming pipeline"
```

### Task 5: Produce Review Evidence

**Files:**
- No source changes expected.

**Interfaces:**
- Produces: commit list, test output, stale-reference search, and one small real-run artifact for reviewer inspection.

- [ ] **Step 1: Run the focused regression set**

Run:

```powershell
pytest tests/safesym_bridge/test_business_affordance.py tests/safesym_bridge/test_business_state_policy.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_web_kobe_pddl_projector.py -q
```

Expected: all pass.

- [ ] **Step 2: Run the full suite again from a clean command**

Run: `pytest -q`

Expected: all pass, with only previously documented skips.

- [ ] **Step 3: Run one small configured DS Flash experiment**

Use the repository's existing `practice_automated_testing` experiment command and the user's configured DS Flash environment. Do not copy API keys into logs or commits. Keep the run small enough to inspect several distinct visible states.

Expected evidence:

- compact graph nodes have readable VLM-generated `node_label` values;
- a revisited node keeps its earlier name;
- graph node IDs and target matching remain independent from labels;
- generated Phase A `domain.pddl` parses and uses readable state predicates/actions where labels are projected.

If the external VLM call is unavailable, report this as an unrun acceptance check; do not fabricate results or weaken unit tests.

- [ ] **Step 4: Hand off for review**

Report the commit hashes, exact test counts, experiment output path, and any naming drift observed. Do not merge; the review session will inspect and decide.
