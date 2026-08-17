# VLM Observation Acceptance Experiment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Determine whether `gpt-4o-mini` can produce precise Practice Shopping candidate/dependency observations and action-transition observations without receiving profile answers, before changing the production explorer.

**Architecture:** Build one offline, throwaway evaluation harness around existing Practice Shopping screenshots and trace metadata. Phase 1 evaluates current-state candidate/dependency output with structural checks plus a semantic audit rubric; Phase 2 runs only if Phase 1 passes and evaluates before/action/after transition output. Keep all experiment logic outside `src/`, preserve raw model responses, and publish an evidence-backed GO/NO-GO report.

**Tech Stack:** Python 3.11, pytest, existing OpenAI provider configuration, `gpt-4o-mini` with temperature `0`, existing PNG screenshots and `stagehand_trace.json`.

**Spec:** `docs/superpowers/specs/2026-08-17-vlm-observation-acceptance-design.zh-CN.md`

## Global Constraints

- Do not modify production files under `src/ai_web_explorer/`.
- Do not inject the Practice Shopping profile, allowed location list, fact vocabulary, action contracts, canonical action examples, SafeSym goal, expected workflow, or completed action IDs into either VLM prompt.
- Use `gpt-4o-mini` by default with temperature `0`.
- Candidate recall is not a hard gate; returned actions and dependencies must be correct.
- A false dependency is a hard failure.
- A success/result-only page may correctly return `actions=[]` and must not produce an `order_submitted` action.
- Accept either fine-grained or coarse-grained prerequisite actions when they are directly executable and collectively cover the visible unmet requirements.
- Preserve every prompt, parsed response, raw response, screenshot path, model setting, structural violation, and manual semantic verdict in the runtime JSON.
- Do not execute a browser action, place an order, or call SafeSym during this experiment.
- Stop after Phase 1 and report NO-GO if its hard gates fail; do not use Phase 2 results to compensate for Phase 1 failure.

---

### Task 1: Candidate and Dependency Evaluation Harness

**Files:**
- Create: `examples/evaluate_vlm_observation_acceptance.py`
- Create: `tests/test_vlm_observation_acceptance.py`

**Interfaces:**
- Consumes: screenshot paths and a provider callable compatible with `provider(prompt, *, current_screenshot_path=...) -> str`.
- Produces: `build_candidate_prompt() -> str`, `parse_candidate_observation(payload: str | dict) -> CandidateObservation`, `validate_candidate_observation(observation: CandidateObservation) -> list[str]`, and `run_candidate_phase(cases, provider, repetitions=3) -> dict`.

- [ ] **Step 1: Write failing parser and prompt-audit tests**

Add tests asserting that the candidate schema contains only `location` and flat `actions`, with each action containing `id`, `instruction`, `status`, `requires`, and `evidence`. Assert the prompt contains the rules `ready requires=[]`, `blocked requires direct unmet action ids`, `unknown when evidence is insufficient`, `actions=[] is valid`, and semantic grouping is model-selected. Assert the prompt does not contain these answer tokens:

```python
FORBIDDEN_PROMPT_TOKENS = {
    "fill_billing_information",
    "fill_payment_information",
    "complete_checkout_information",
    "place_order",
    "order_submitted",
    "cart_has_items",
    "action_contracts",
    "canonical_action_examples",
    "semantic_profile_context",
}
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
rye run pytest -q tests/test_vlm_observation_acceptance.py -k "candidate_prompt or candidate_parser"
```

Expected: FAIL because the new module and interfaces do not exist.

- [ ] **Step 3: Implement the minimal candidate schema and prompt**

Use frozen dataclasses for `CandidateAction` and `CandidateObservation`. Normalize IDs to lowercase snake_case, reject duplicate IDs, reject unsupported status values, and preserve raw evidence strings. Do not add compatibility parsing for the old nested `regions`, `business_affordances`, profile facts, relevance, confidence, or action-role schema.

- [ ] **Step 4: Write failing structural validation tests**

Cover these exact rules:

```text
ready with non-empty requires                     -> violation
blocked with empty requires                       -> violation
unknown with non-empty requires                   -> violation
requires references an absent action id           -> violation
requires references a non-ready action             -> violation
self dependency                                    -> violation
dependency cycle                                   -> violation
empty actions                                      -> structurally valid
one ready coarse prerequisite + one blocked target -> structurally valid
two ready fine prerequisites + one blocked target  -> structurally valid
```

- [ ] **Step 5: Implement deterministic structural validation**

Return stable machine-readable strings such as:

```text
ready_has_requires:<action_id>
blocked_has_no_requires:<action_id>
unknown_has_requires:<action_id>
missing_requirement:<target_id>:<requirement_id>
requirement_not_ready:<target_id>:<requirement_id>
self_dependency:<action_id>
dependency_cycle:<id_a>:<id_b>
```

Do not attempt to automate semantic correctness from hard-coded expected action names.

- [ ] **Step 6: Add the bounded Phase 1 case runner**

Run three independent temperature-zero observations for each case:

```text
shopping_independence: before_0001.png
checkout_dependency:   before_0004.png
confirmation_empty:    after_0006.png
```

The runtime result for each observation must include `case_id`, screenshot path, prompt SHA-256, prompt audit, raw response, parsed response, structural violations, and an initially empty `semantic_audit` object. The runner must not contain expected canonical action IDs for the three screenshots.

- [ ] **Step 7: Run all harness tests**

Run:

```powershell
rye run pytest -q tests/test_vlm_observation_acceptance.py
```

Expected: PASS.

- [ ] **Step 8: Commit the harness**

```powershell
git add examples/evaluate_vlm_observation_acceptance.py tests/test_vlm_observation_acceptance.py
git commit -m "test: add VLM observation acceptance harness"
```

### Task 2: Phase 1 Candidate and Dependency Experiment

**Files:**
- Modify: `examples/evaluate_vlm_observation_acceptance.py`
- Create: `docs/experiments/practice-shopping-vlm-observation-acceptance-v1.md`
- Runtime only, do not commit: `outputs/experiments/practice_automated_testing/vlm_observation_acceptance_v1/candidate_observations.json`

**Interfaces:**
- Consumes: `run_candidate_phase(...) -> dict` from Task 1.
- Produces: a Phase 1 GO/NO-GO decision and semantic audit records for all nine observations.

- [ ] **Step 1: Run the candidate phase against the real screenshots**

Use the repository `.env`, the default `gpt-4o-mini`, temperature `0`, and three repetitions per screenshot. Write raw output only under the runtime output directory.

- [ ] **Step 2: Audit every returned action semantically**

For each of the nine observations, record booleans and a short evidence note for:

```text
all_returned_actions_visible_and_executable
no_result_fact_as_action
independent_actions_have_no_false_requires
blocked_requirements_collectively_cover_visible_unmet_needs
requirement_actions_are_directly_executable
success_page_empty_or_contains_only_real_executable_actions
```

Judge semantic coverage, not exact action IDs or prerequisite count. Accept a single coarse checkout-information action or separate billing/payment actions when each is executable and the combined dependency is complete.

- [ ] **Step 3: Apply the Phase 1 hard gate**

Phase 1 is GO only if all nine responses parse, have no structural violation, contain no invented/result action, contain no false dependency, and every returned blocked action has complete visible direct prerequisites. The shopping case need not enumerate all ordinary actions; the confirmation case should be empty unless a genuinely executable confirmation-page action is clearly visible.

- [ ] **Step 4: If Phase 1 fails, perform at most two prompt-only revisions**

Keep the same schema, model, screenshots, repetitions, and no-answer constraints. Record each prompt SHA and all failed outputs. Do not add site-specific action names, checkout vocabulary, expected workflow, or few-shot answers. Stop after the third total prompt version and report NO-GO if any hard gate still fails.

- [ ] **Step 5: Write the Phase 1 section of the report**

Include a table by prompt version, case, and repetition; list every returned action and dependency; identify false dependencies explicitly; distinguish structural pass from semantic pass; and state why the selected prompt does or does not pass. Do not average away a hard failure.

- [ ] **Step 6: Re-run tests and commit the Phase 1 evidence report**

Run:

```powershell
rye run pytest -q tests/test_vlm_observation_acceptance.py
git diff --check
```

Then commit only the harness change and Markdown report, not runtime JSON:

```powershell
git add examples/evaluate_vlm_observation_acceptance.py docs/experiments/practice-shopping-vlm-observation-acceptance-v1.md
git commit -m "docs: report VLM candidate dependency acceptance"
```

### Task 3: Conditional Action-Transition Observation Experiment

**Files:**
- Modify: `examples/evaluate_vlm_observation_acceptance.py`
- Modify: `tests/test_vlm_observation_acceptance.py`
- Modify: `docs/experiments/practice-shopping-vlm-observation-acceptance-v1.md`
- Runtime only, do not commit: `outputs/experiments/practice_automated_testing/vlm_observation_acceptance_v1/transition_observations.json`

**Interfaces:**
- Consumes: Phase 1 GO decision and existing `stagehand_trace.json` screenshot pairs.
- Produces: `build_transition_prompt(action_description: str) -> str`, `parse_transition_observation(...) -> TransitionObservation`, and `run_transition_phase(...) -> dict`.

- [ ] **Step 1: Enforce the Phase 1 gate**

If Phase 1 is NO-GO, do not call the transition observer. Add `phase_2_status: not_run_due_to_phase_1_no_go` to the report and stop this task.

- [ ] **Step 2: Write failing transition schema tests**

The only accepted output fields are:

```json
{
  "outcome": "success | failure | unknown",
  "location_change": "changed | unchanged | unknown",
  "other_significant_change": false,
  "evidence": ["short visible evidence"]
}
```

Assert the prompt receives the executed action description and before/after screenshots but no profile, location answer list, facts, contracts, candidate history, or workflow goal.

- [ ] **Step 3: Implement the minimal transition parser and prompt**

Reject missing fields, extra legacy semantic fields, non-boolean `other_significant_change`, unsupported enum values, and malformed evidence. Do not generate candidates or facts in this observer.

- [ ] **Step 4: Run representative existing trace pairs**

Use three repetitions for each pair:

```text
before_0001.png + add_to_cart                    + after_0001.png
before_0002.png + filter_products                + after_0002.png
before_0003.png + view_cart                      + after_0003.png
before_0004.png + complete_checkout_information  + after_0004.png
before_0005.png + complete_payment_information   + after_0005.png
before_0006.png + place_order                    + after_0006.png
```

Use the trace action description as observation context, not the profile contract or expected effect.

- [ ] **Step 5: Audit transition correctness**

For each response, compare only against visible before/after evidence and record:

```text
outcome_matches_visible_change
location_change_matches_active_surface_change
other_significant_change_excludes_only_the_executed_action_direct_result
evidence_is_grounded_in_the_pair
```

Treat an incorrect location-change classification or an incorrect `other_significant_change` classification as a hard failure. Do not infer hidden business completion.

- [ ] **Step 6: Complete the report with an independent Phase 2 verdict**

Report Phase 2 GO only when all responses parse and pass the semantic audit. State the candidate prompt and transition prompt separately. Do not claim production readiness; the result only validates VLM output contracts on the bounded screenshot set.

- [ ] **Step 7: Run tests and commit**

Run:

```powershell
rye run pytest -q tests/test_vlm_observation_acceptance.py
git diff --check
```

Commit:

```powershell
git add examples/evaluate_vlm_observation_acceptance.py tests/test_vlm_observation_acceptance.py docs/experiments/practice-shopping-vlm-observation-acceptance-v1.md
git commit -m "test: validate VLM action transition observations"
```

### Task 4: Final Experiment Audit and Handoff

**Files:**
- Modify: `docs/experiments/practice-shopping-vlm-observation-acceptance-v1.md`

**Interfaces:**
- Consumes: committed harness, Phase 1 results, and optional Phase 2 results.
- Produces: one final recommendation for whether production candidate-pool design may begin.

- [ ] **Step 1: Audit prompt leakage**

Search committed harness prompts and captured prompt text for every forbidden token from Task 1. Explain any occurrence outside the prompt, such as audit labels or trace action descriptions. A forbidden answer token inside the candidate prompt is an automatic NO-GO.

- [ ] **Step 2: Audit evidence completeness**

Confirm the report links every conclusion to a screenshot, prompt SHA, raw response, parsed response, and semantic audit entry. Confirm raw runtime JSON remains uncommitted and its path is documented.

- [ ] **Step 3: State one bounded final verdict**

Use exactly one of:

```text
GO: candidate/dependency VLM output is sufficient to begin candidate-pool integration design.
NO-GO: candidate/dependency output still violates at least one hard gate; do not modify downstream components.
```

Report Phase 2 separately and do not let it change the Phase 1 verdict.

- [ ] **Step 4: Final verification**

Run:

```powershell
rye run pytest -q tests/test_vlm_observation_acceptance.py
git diff --check
git status --short
```

Expected: tests pass; diff check passes; only documented runtime observation JSON may remain untracked or ignored; no production source file changed.

- [ ] **Step 5: Commit the final report update**

```powershell
git add docs/experiments/practice-shopping-vlm-observation-acceptance-v1.md
git commit -m "docs: finalize VLM observation acceptance verdict"
```
