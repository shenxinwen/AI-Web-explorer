# Location Candidate Dependency Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the profile-answer-guided candidate/observation path with a minimal VLM action-dependency loop that records only verified actions and emits causal, solvable PDDL.

**Architecture:** Keep the existing location memory, Stagehand executor, raw graph, semantic projection, checkpoint, and SafeSym bridge. Add a minimal candidate parser carrying same-location `requires`, a minimal after-action observation parser, dependency-aware local scheduling, and deterministic completion predicates generated from successful actions. Bypass targeted and supplement scans in the new active path without deleting the legacy implementation.

**Tech Stack:** Python 3, dataclasses, pytest, OpenAI-compatible vision client, Stagehand SDK, PDDL, SafeSym, Fast Downward.

**Spec:** `docs/superpowers/specs/2026-08-18-location-candidate-dependency-integration-design.zh-CN.md`

## Global Constraints

- Candidate discovery must not receive concrete profile facts, action contracts, expected workflow, or the offline PDDL goal.
- Candidate JSON is limited to `actions[].action_id`, `description`, `target`, and `requires`.
- After-action JSON is limited to `outcome`, boolean `location_change`, and `evidence`.
- `requires` may reference only actions from the same initial scan and must reject dangling, self, and cyclic dependencies.
- Only actions confirmed successful and their successful dependencies enter planner-facing graph/PDDL.
- Use one initial candidate scan per new semantic location; bypass targeted and supplement scans.
- Keep Stagehand/DeepSeek execution response handling unchanged.
- Default VLM experiment model is `gpt-4o-mini` with temperature `0`.
- Do not add Practice Shopping button-text, fixed-action-ID, or workflow branches.

---

### Task 1: Minimal candidate response and validation

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/business_affordance.py`
- Test: `tests/safesym_bridge/test_business_affordance.py`

**Interfaces:**
- Consumes: existing `VisualAffordanceRequest`, provider callback, and `BusinessAffordance`.
- Produces: `VisualAffordanceResult.requires_by_action_id: dict[str, list[str]]`; initial prompt/response using only the four approved action fields.

- [ ] **Step 1: Write failing parser and prompt tests**

Add tests that assert the prompt contains no `semantic_profile_context`, `goal`, `regions`, `page_mode`, `relevance_hint`, `confidence`, or `supporting_facts`, and that this response produces two affordances plus the dependency map:

```python
{
    "actions": [
        {"action_id": "fill_billing", "description": "Fill billing", "target": "billing form", "requires": []},
        {"action_id": "place_order", "description": "Place order", "target": "Place Order", "requires": ["fill_billing"]},
    ]
}
```

Add separate tests proving `{"actions": []}` succeeds and dangling, self, and cyclic dependencies return a failed trace with no formal affordances.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `pytest tests/safesym_bridge/test_business_affordance.py -q`

Expected: FAIL because the result has no dependency map and the prompt still uses the legacy region schema.

- [ ] **Step 3: Implement the minimal initial-scan protocol**

Add the field:

```python
requires_by_action_id: dict[str, list[str]] = field(default_factory=dict)
```

Parse `actions`, normalize IDs with `normalize_semantic_id`, build `BusinessAffordance(action_name=action_id, label=description, target_hint=target, source="vlm")`, then validate the complete directed graph before returning formal candidates. Preserve raw response and validation errors in `VisualAffordanceTrace`. Do not alter the legacy targeted parser; make the new initial path explicit.

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/safesym_bridge/test_business_affordance.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/grounded_web/business_affordance.py tests/safesym_bridge/test_business_affordance.py
git commit -m "feat: parse minimal VLM action dependencies"
```

### Task 2: Dependency-aware location memory and checkpointing

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/location_exploration.py`
- Test: `tests/safesym_bridge/test_location_exploration.py`

**Interfaces:**
- Consumes: `requires_by_action_id` from Task 1.
- Produces: persisted `LocationCandidateRecord.requires: list[str]`, dependency-aware `next_candidate`, and terminal status `blocked_by_failed_requirement`.

- [ ] **Step 1: Write failing memory tests**

Cover all of the following in focused tests:

```python
assert pool.candidates["place_order"].requires == ["fill_billing", "fill_payment"]
assert memory.next_candidate("checkout").action_name == "fill_billing"
```

Also assert: the dependent target is not selected early; after both prerequisites become `success`, it is selected before an independent action; a terminal prerequisite failure changes the dependent status to `blocked_by_failed_requirement`; independent actions remain eligible; `to_dict`/`from_dict` round-trip `requires` and the new status.

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest tests/safesym_bridge/test_location_exploration.py -q`

Expected: FAIL because records do not contain `requires` and selection ignores dependencies.

- [ ] **Step 3: Implement minimal dependency state**

Add only:

```python
requires: list[str] = field(default_factory=list)
```

to `LocationCandidateRecord`, including serialization. Extend `merge_scan(..., requires_by_action_id: Mapping[str, Iterable[str]] | None = None)` and store normalized same-location IDs. Define successful prerequisites strictly as records with `status == "success"`; do not use `terminal` or `completed_action_ids()` as success. Before selection, propagate terminal prerequisite failures to `blocked_by_failed_requirement`. Sort eligible records by `(participates_in_dependency_chain ? 0 : 1, discovery_order, action_id)`.

- [ ] **Step 4: Run focused and existing checkpoint tests**

Run: `pytest tests/safesym_bridge/test_location_exploration.py tests/safesym_bridge/test_web_kobe_controller.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/grounded_web/location_exploration.py tests/safesym_bridge/test_location_exploration.py
git commit -m "feat: schedule location candidates by dependencies"
```

### Task 3: Minimal action outcome observation and active-path integration

**Files:**
- Create: `src/ai_web_explorer/grounded_web/action_outcome.py`
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Modify: `src/ai_web_explorer/grounded_web/location_exploration.py`
- Modify: `src/ai_web_explorer/grounded_web/openai_visual_delta.py`
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Test: `tests/safesym_bridge/test_action_outcome.py`
- Test: `tests/safesym_bridge/test_web_kobe_explorer.py`

**Interfaces:**
- Consumes: before/after screenshots, executed `BrowserAction`, and source location ID.
- Produces: `ActionOutcomeResult(outcome: str, location_change: bool, evidence: str, trace: ...)`; successful candidate status update; one initial scan for a new location.

- [ ] **Step 1: Write failing outcome parser tests**

Test valid success, failed, and uncertain responses; reject non-boolean `location_change`, unknown outcomes, arrays, missing fields, and extra planner-facing fields such as `completion_facts`. Assert the prompt includes the generic same-location rule for filtering/search/sort/pagination and contains exactly the three response fields.

- [ ] **Step 2: Write failing explorer integration tests**

Using existing fake browser/provider patterns, assert that same-location success records candidate `success` without another scan; a location change creates/scans the target pool once; revisiting restores the existing pool; and the active path does not request targeted or supplement scans after a successful action.

- [ ] **Step 3: Run tests and confirm failure**

Run: `pytest tests/safesym_bridge/test_action_outcome.py tests/safesym_bridge/test_web_kobe_explorer.py -q`

Expected: FAIL because `action_outcome.py` and the active integration do not exist.

- [ ] **Step 4: Implement the strict three-field parser**

Use frozen dataclasses and a provider callback matching the current screenshot provider convention. Preserve raw JSON/error trace. Do not derive business facts, completion facts, roles, confidence, source location, or target location from the response.

- [ ] **Step 5: Integrate without deleting the legacy Visual Delta path**

Wire the new result into the location-scoped active exploration path. Map `success` to `record_attempt(... observable_change=True, failed=False)` and explicit successful status; map `failed` to the existing retry/failure policy; leave `uncertain` retryable. When `location_change` is false, update local memory only. When true, use the existing observation/location identity mechanism to switch or restore pools, then initial-scan only if `initial_scan_complete` is false. Pass `requires_by_action_id` from Task 1 into `merge_scan`. Do not invoke targeted/supplement scans in this path.

- [ ] **Step 6: Set the VLM default and preserve DeepSeek execution**

Change only the observation-model default to `gpt-4o-mini`, temperature `0`. Do not change `StagehandSdkProvider.act_instruction`, `execute_instruction`, or their DeepSeek response parsing.

- [ ] **Step 7: Run focused integration tests**

Run: `pytest tests/safesym_bridge/test_action_outcome.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_stagehand_sdk_provider.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/ai_web_explorer/grounded_web/action_outcome.py src/ai_web_explorer/grounded_web/explorer.py src/ai_web_explorer/grounded_web/location_exploration.py src/ai_web_explorer/grounded_web/openai_visual_delta.py src/ai_web_explorer/safesym_bridge/browser_runner.py tests/safesym_bridge/test_action_outcome.py tests/safesym_bridge/test_web_kobe_explorer.py
git commit -m "feat: observe minimal action outcomes"
```

### Task 4: Solidify successful dependencies into semantic graph and PDDL

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/graph.py`
- Modify: `src/ai_web_explorer/grounded_web/graph_manager.py`
- Modify: `src/ai_web_explorer/grounded_web/semantic_model.py`
- Modify: `src/ai_web_explorer/grounded_web/semantic_planning.py`
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
- Modify: `src/ai_web_explorer/safesym_bridge/minimal_semantic_pddl.py`
- Test: `tests/safesym_bridge/test_web_kobe_graph.py`
- Test: `tests/safesym_bridge/test_semantic_planning.py`
- Test: `tests/safesym_bridge/test_minimal_semantic_pddl.py`

**Interfaces:**
- Consumes: successful candidate `requires` from location memory.
- Produces: `WebKobeEdge.required_action_ids`, location-qualified completion facts, and PDDL prerequisite facts.

- [ ] **Step 1: Write failing graph round-trip tests**

Assert a verified `place_order` edge serializes and reloads:

```python
required_action_ids=["fill_billing", "fill_payment"]
```

Assert unsuccessful/unverified edges never contribute formal dependencies.

- [ ] **Step 2: Write failing semantic/PDDL tests**

Build three successful checkout actions and assert projection generates:

```text
completed_checkout_fill_billing
completed_checkout_fill_payment
completed_checkout_place_order
```

Assert `place_order` requires the first two facts, each successful action adds its own completion fact, same-location actions retain `at_checkout`, and navigation deletes `at_checkout` and adds `at_order_confirmation`.

- [ ] **Step 3: Run tests and confirm failure**

Run: `pytest tests/safesym_bridge/test_web_kobe_graph.py tests/safesym_bridge/test_semantic_planning.py tests/safesym_bridge/test_minimal_semantic_pddl.py -q`

Expected: FAIL because successful action dependencies are not explicit graph data and completion predicates are not deterministic.

- [ ] **Step 4: Implement graph persistence**

Add `required_action_ids: list[str] = field(default_factory=list)` to `WebKobeEdge`, including serialization, loading, and edge merge. Populate it only while creating an edge confirmed successful; read the source-location record from local memory and include only prerequisite records with `status == "success"`.

- [ ] **Step 5: Implement deterministic completion projection**

Use one helper shared by projection logic:

```python
def completion_fact(location_id: str, action_id: str) -> str:
    return normalize_semantic_id(f"completed_{location_id}_{action_id}")
```

Every included successful action adds its own completion fact. Convert every `required_action_id` to a completion fact at the action's source location and append it to `SemanticAction.required_facts`. Do not add facts for failed, blocked, or unexecuted candidates.

- [ ] **Step 6: Run focused tests**

Run: `pytest tests/safesym_bridge/test_web_kobe_graph.py tests/safesym_bridge/test_semantic_planning.py tests/safesym_bridge/test_minimal_semantic_pddl.py -q`

Expected: PASS, including an assertion that a plan cannot apply `place_order` before both prerequisites.

- [ ] **Step 7: Commit**

```bash
git add src/ai_web_explorer/grounded_web/graph.py src/ai_web_explorer/grounded_web/graph_manager.py src/ai_web_explorer/grounded_web/semantic_model.py src/ai_web_explorer/grounded_web/semantic_planning.py src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py src/ai_web_explorer/safesym_bridge/minimal_semantic_pddl.py tests/safesym_bridge/test_web_kobe_graph.py tests/safesym_bridge/test_semantic_planning.py tests/safesym_bridge/test_minimal_semantic_pddl.py
git commit -m "feat: compile verified action dependencies to PDDL"
```

### Task 5: Regression and Practice Shopping acceptance

**Files:**
- Modify: `tests/safesym_bridge/test_web_kobe_playwright_integration.py`
- Modify: `docs/safesym-bridge.md`
- Create: `outputs/experiments/practice_automated_testing/latest/dependency-mvp-acceptance.json` only if the repository's existing experiment-output policy permits tracked output; otherwise keep it local and summarize in the report.

**Interfaces:**
- Consumes: complete new path from Tasks 1–4.
- Produces: reproducible offline acceptance plus one bounded live Practice Shopping report.

- [ ] **Step 1: Add an offline end-to-end acceptance test**

Fixture the candidate and outcome providers so checkout returns billing, payment, and `place_order` dependencies; confirmation returns `actions=[]`; filtering has no `requires`. Assert candidate order, successful unlock, graph persistence, PDDL parse, and no direct `place_order` shortcut.

- [ ] **Step 2: Run the full non-browser suite**

Run: `pytest tests/safesym_bridge -q`

Expected: PASS. Fix regressions only where the new active-path contract intentionally changed; do not rewrite legacy tests merely to hide failures.

- [ ] **Step 3: Run the bounded real experiment**

Use the documented Practice Shopping command, the controlled-order safety whitelist, `gpt-4o-mini`, temperature `0`, and existing action/time budgets. Capture prompt/response traces, graph, domain/problem PDDL, SafeSym injection report, and Fast Downward plan.

- [ ] **Step 4: Evaluate the explicit acceptance matrix**

Report PASS/FAIL for: real actions only; no false `requires` on independent actions; checkout dependency chain found; `place_order` unlocks only after prerequisites; no `order_submitted` pseudo-action; empty confirmation actions allowed; all verified actions retained; no failed/unexecuted actions in Domain; SafeSym injects; Fast Downward solves; plan includes prerequisites; prompt contains no Practice Shopping answer profile or goal.

- [ ] **Step 5: Update operator documentation**

Document the two minimal JSON contracts, the separation between Stagehand/DeepSeek execution and VLM observation, the one-scan limitation, and the exact acceptance command. Label legacy targeted/supplement behavior as bypassed rather than deleted.

- [ ] **Step 6: Commit**

```bash
git add tests/safesym_bridge/test_web_kobe_playwright_integration.py docs/safesym-bridge.md
git commit -m "test: accept dependency-driven exploration path"
```

## Final Verification Gate

- [ ] Run `git status --short` and confirm only intentional experiment artifacts, if any, remain.
- [ ] Run `pytest tests/safesym_bridge -q` and record the pass count.
- [ ] Parse the generated Domain and Problem with the repository's documented parser command.
- [ ] Run SafeSym safety injection and record success.
- [ ] Run Fast Downward and inspect that the plan cannot skip required checkout actions.
- [ ] Compare captured candidate and action-outcome prompts against the forbidden answer-hint fields in Global Constraints.
- [ ] Produce a short implementation report containing commits, test evidence, live-run evidence, known limitations, and any deviation from this plan.
