# Visual Delta Completion Facts Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Visual Delta request and audit a strict `completion_facts: list[str]` contract without promoting malformed or merely candidate facts into PDDL.

**Architecture:** Keep the existing semantic model and fail-closed list parser. Strengthen only the Visual Delta prompt boundary and add a stable trace rejection for malformed completion-fact shapes; valid semantic observations continue through the existing profile validator and semantic projection unchanged.

**Tech Stack:** Python 3.11, pytest, JSON prompt contracts, existing `SemanticExperimentProfile` and Minimal Semantic PDDL pipeline.

## Global Constraints

- Address only the completion-facts contract reproduced by the 2026-08-13 run.
- Do not fix or refactor Stagehand tool-choice/multi-step behavior in this change.
- Do not infer completion facts from `candidate_added_facts` or object keys.
- Do not add shopping-specific branches to generic parsing or PDDL code.
- Do not make paid VLM or website calls while implementing.
- Preserve raw provider responses and stable rejection reasons for audit.

---

### Task 1: Strengthen and verify the Visual Delta completion-facts contract

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/visual_delta.py:65-149`
- Modify: `src/ai_web_explorer/grounded_web/visual_delta.py:295-389`
- Test: `tests/safesym_bridge/test_visual_delta_summarizer.py`
- Test: `tests/safesym_bridge/test_location_scoped_feasibility_pipeline.py`

**Interfaces:**
- Consumes: `VisualDeltaRequest.semantic_profile_context`, provider JSON, and `semantic_observation_from_dict(data)`.
- Produces: the existing `VisualDeltaResult`; malformed completion-fact shapes add `completion_facts_must_be_list_of_fact_ids` to `trace.metadata["semantic_observation_rejections"]`.
- Preserves: `SemanticObservation.completion_facts: list[str]`, `PlanningDelta`, and all PDDL compiler interfaces.

- [ ] **Step 1: Add a failing prompt-contract test**

Add a focused test using `practice_shopping_feasibility_profile().to_prompt_context()` and capture the prompt passed to the provider:

```python
def test_profile_prompt_requires_selected_completion_fact_id_list():
    profile = practice_shopping_feasibility_profile()
    request = VisualDeltaRequest(
        goal="Filter products.",
        action=BrowserAction("business_intent", None, "filter_products"),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
        source_location_hint="shopping",
        allowed_location_ids=list(profile.allowed_locations),
        semantic_profile_context=profile.to_prompt_context(),
        semantic_experiment_profile=profile,
    )
    prompts = []

    summarize_visual_delta(
        request,
        provider=lambda prompt, **_kwargs: (
            prompts.append(prompt)
            or '{"action_role":"presentation_capability",'
               '"source_location":"shopping","target_location":"shopping",'
               '"completion_facts":[]}'
        ),
    )

    payload = json.loads(prompts[0])
    assert payload["output_schema"]["completion_facts"] == [
        "selected_completion_fact_id"
    ]
    assert "reference vocabulary" in payload["instruction"]
    assert "must be a JSON array of strings" in payload["instruction"]
```

- [ ] **Step 2: Add the real-run malformed-response regression test**

Use the object shape observed in `graph_evidence.json` and assert fail-closed behavior:

```python
def test_profile_completion_fact_vocabulary_object_is_not_promoted():
    result = summarize_visual_delta(
        _profile_delta_request(),
        provider=lambda *_args, **_kwargs: json.dumps(
            {
                "action_role": "presentation_capability",
                "source_location": "shopping",
                "target_location": "shopping",
                "completion_facts": {
                    "products_sorted": [],
                    "products_filtered": [],
                    "products_found": [],
                },
                "candidate_added_facts": ["products_filtered"],
            }
        ),
    )

    assert result.semantic_observation is not None
    assert result.semantic_observation.completion_facts == []
    assert result.planning_delta.verified_added_facts == []
    assert "completion_facts_must_be_list_of_fact_ids" in result.trace.metadata[
        "semantic_observation_rejections"
    ]
```

- [ ] **Step 3: Run the two new tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/safesym_bridge/test_visual_delta_summarizer.py::test_profile_prompt_requires_selected_completion_fact_id_list `
  tests/safesym_bridge/test_visual_delta_summarizer.py::test_profile_completion_fact_vocabulary_object_is_not_promoted
```

Expected: the prompt test fails because `output_schema` is absent; the audit test fails because the stable rejection reason is absent.

- [ ] **Step 4: Implement the explicit response schema**

In `_prompt_for_request()`, add wording that profile dictionaries are reference vocabularies, not response templates. Add this exact shape alongside `required_json_fields`:

```python
"output_schema": {
    "candidate_added_facts": ["visible_added_fact_id"],
    "candidate_removed_facts": ["visible_removed_fact_id"],
    "visual_change_kind": "none | presentation | state_indicator | surface | mixed | unknown",
    "action_role": "one allowed action role",
    "source_location": "one allowed location ID",
    "target_location": "one allowed location ID",
    "completion_facts": ["selected_completion_fact_id"],
    "candidate_required_facts": ["selected_business_fact_id"],
    "preserved_facts": ["selected_business_fact_id"],
    "semantic_evidence": ["short visible evidence statement"],
    "semantic_confidence": 0.0,
    "observable_change": False,
    "business_facts_added": ["selected_business_fact_id"],
    "business_facts_removed": ["selected_business_fact_id"],
},
```

The instruction must say that `completion_facts` is a JSON array of zero or more selected keys from `semantic_profile_context.completion_facts`, and must be `[]` when none is visibly supported.

- [ ] **Step 5: Add fail-closed contract auditing**

Before profile validation, append a stable reason only when the field is present and malformed:

```python
if "completion_facts" in parsed and (
    not isinstance(parsed["completion_facts"], list)
    or not all(isinstance(item, str) for item in parsed["completion_facts"])
):
    rejection_reasons.append("completion_facts_must_be_list_of_fact_ids")
```

Initialize `rejection_reasons` before this check, retain the existing
`semantic_observation_from_dict()` behavior, and do not coerce the malformed
value. Merge the reason with profile-validation reasons using the existing
stable de-duplication at trace creation.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/safesym_bridge/test_visual_delta_summarizer.py `
  tests/safesym_bridge/test_semantic_model.py `
  tests/safesym_bridge/test_location_scoped_feasibility_pipeline.py
```

Expected: all selected tests pass; existing valid-list tests still prove that approved completion facts survive.

- [ ] **Step 7: Run the mainline regression suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  --ignore=tests/test_local_shop_fixture.py `
  --ignore=tests/safesym_bridge/test_web_kobe_playwright_integration.py
```

Expected: all non-browser tests pass. Do not modify the deferred Playwright fixtures in this task.

- [ ] **Step 8: Review the diff against scope**

Run:

```powershell
git diff --check
git diff -- src/ai_web_explorer/grounded_web/visual_delta.py tests/safesym_bridge/test_visual_delta_summarizer.py
```

Verify explicitly that there are no changes to Stagehand, controller, replay,
profiles, semantic planning, or PDDL compilers and no object-to-list coercion.

- [ ] **Step 9: Commit the implementation**

```powershell
git add src/ai_web_explorer/grounded_web/visual_delta.py tests/safesym_bridge/test_visual_delta_summarizer.py
git commit -m "fix: enforce completion facts response contract"
```

Report the commit, focused/full test counts, and any remaining limitation. The
next paid experiment is outside this implementation task and will be run only
after review.
