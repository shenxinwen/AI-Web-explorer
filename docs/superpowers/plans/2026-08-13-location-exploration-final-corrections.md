# Location Exploration Final Corrections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the three remaining runtime gaps without changing the approved location-scoped open-exploration design.

**Architecture:** Keep the existing profile validator, runtime-budget state, location memory, preflight, and PDDL projection. Wire the profile validator into the real Explorer request, preserve the controller-owned cumulative counters at the Runner boundary, and replace Raw Node replay validation with one non-mutating semantic checkpoint verification based on the target node's verified active business facts.

**Tech Stack:** Python 3.11, dataclasses, pytest/AnyIO, existing WebKobe Explorer/Controller/Stagehand/VLM provider and graph models.

## Scheme Alignment

This plan implements existing requirements; it does not add new semantics:

- `SemanticExperimentProfile` remains the runtime allow-list authority.
- Formal attempts and no-progress/replay budgets remain cumulative across checkpoint/resume.
- Replay remains a browser restoration mechanism, produces no graph/candidate/fact changes, and validates only target semantic location plus verified business facts.
- Ordinary completion facts and VLM `supporting_facts` are never replay requirements.
- Exploration remains open and is not guided by the SafeSym goal.

## Global Constraints

- Work only in `D:\GitHUb\ai-web-explorer-main\.worktrees\location-scoped-open-exploration` on `codex/location-scoped-open-exploration` after `b65551f`.
- Reuse `D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe`; do not download dependencies.
- Do not run the real website, paid VLM, or submit an order.
- Do not merge `main` or modify the main worktree.
- Do not create another Explorer, Controller, replay graph, or budget system.
- Preserve legacy behavior when no semantic experiment profile is selected.
- Each task ends with focused tests, `git diff --check`, and one commit.

---

### Task 1: Wire the Profile Validator into the Real Visual-Delta Request

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/explorer.py:575-592`
- Test: `tests/safesym_bridge/test_web_kobe_explorer.py`
- Test: `tests/safesym_bridge/test_location_scoped_feasibility_pipeline.py`

**Interfaces:**
- Existing input: `WebKobeExplorer.semantic_experiment_profile`.
- Existing consumer: `VisualDeltaRequest.semantic_experiment_profile`.
- Existing output: `VisualDeltaTrace.metadata["semantic_observation_rejections"]` and a fail-closed `semantic_observation`.

- [ ] **Step 1: Add a failing production-path test**

Construct a real `WebKobeExplorer` with the Practice profile. Return a valid JSON visual response containing:

```json
{
  "action_role": "navigation",
  "source_location": "shopping",
  "target_location": "evil_location",
  "completion_facts": ["invented_completion"],
  "semantic_evidence": ["Visible change."],
  "observable_change": true
}
```

Run one action through `explore_one_step()`. Assert the recorded edge has no semantic observation for `evil_location`, its trace contains both rejection reasons, and neither value appears in the semantic planning graph/PDDL.

- [ ] **Step 2: Verify RED**

```powershell
$env:PYTHONPATH='src'
& 'D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe' -m pytest tests/safesym_bridge/test_web_kobe_explorer.py -k "profile_runtime_rejects_out_of_contract_semantics" -q
```

Expected: FAIL because Explorer currently passes only `semantic_profile_context`, not the profile object.

- [ ] **Step 3: Make the one-line production wiring change**

Pass:

```python
semantic_experiment_profile=self.semantic_experiment_profile
```

when constructing `VisualDeltaRequest`. Do not duplicate validation in Explorer.

- [ ] **Step 4: Run focused tests and commit**

```powershell
& 'D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe' -m pytest tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_visual_delta_summarizer.py tests/safesym_bridge/test_location_scoped_feasibility_pipeline.py -q
git diff --check
git add src/ai_web_explorer/grounded_web/explorer.py tests/safesym_bridge
git commit -m "fix: enforce profile on explorer visual deltas"
```

Report the commit and exact test count, then continue.

---

### Task 2: Preserve Controller-Owned Cumulative Runtime State

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py:962-1010`
- Test: `tests/safesym_bridge/test_browser_runner.py`
- Test: `tests/safesym_bridge/test_web_kobe_controller.py`

**Interfaces:**
- Authoritative state: `graph.meta["exploration_runtime_state"]` written by `WebKobeExplorationController`.
- Compatibility mirrors: top-level `formal_action_attempts`, `consecutive_no_progress`, `semantic_progress_count`, and replay counters must equal the authoritative cumulative values.
- Run summary distinguishes `steps_completed` for this invocation from cumulative `formal_action_attempts`.

- [ ] **Step 1: Add failing Runner resume tests**

Use a fake Controller result whose graph contains:

```python
graph.meta["exploration_runtime_state"] = {
    "formal_action_attempts": 20,
    "consecutive_no_progress": 1,
    "semantic_progress_count": 7,
    "replay_attempt_count": 2,
    "frontier_replay_attempts": {"checkout": 1},
    "blocked_replay_node_ids": [],
}
```

and whose summary reports `steps_completed=1`. Assert the written checkpoint retains `formal_action_attempts=20`, while `exploration_summary.steps_completed == 1` and `exploration_summary.formal_action_attempts == 20`.

Add a second test that reloads this checkpoint and verifies zero formal action is executed when the accumulated count is already 20.

- [ ] **Step 2: Verify RED**

```powershell
& 'D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe' -m pytest tests/safesym_bridge/test_browser_runner.py -k "cumulative_runtime_state" -q
```

Expected: FAIL because Runner overwrites cumulative `20` with current-run `1`.

- [ ] **Step 3: Remove the competing counter writer**

After Controller returns, read the authoritative `exploration_runtime_state` and mirror its cumulative fields. Never derive cumulative fields from `summary.steps_completed`. Keep `steps_completed` only as the per-invocation field. Preserve the existing union of blocked resume frontiers without discarding controller state.

Do not add a third budget class or duplicate Controller accounting in Runner.

- [ ] **Step 4: Run focused tests and commit**

```powershell
& 'D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe' -m pytest tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_web_kobe_controller.py -q
git diff --check
git add src/ai_web_explorer/safesym_bridge/browser_runner.py tests/safesym_bridge
git commit -m "fix: preserve cumulative exploration runtime state"
```

Report the commit and exact test count, then continue.

---

### Task 3: Validate Replay as a Semantic Checkpoint, Not a Raw Node

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/frontier_replay.py`
- Modify: `src/ai_web_explorer/grounded_web/explorer.py:951-1020`
- Modify: `src/ai_web_explorer/grounded_web/visual_delta.py` only if a small replay-check request/result is colocated with the existing visual provider contract.
- Test: `tests/safesym_bridge/test_frontier_replay.py`
- Test: `tests/safesym_bridge/test_web_kobe_explorer.py`
- Test: `tests/safesym_bridge/test_location_scoped_feasibility_pipeline.py`

**Interfaces:**
- `FrontierTarget.required_business_facts` is derived from the target node's `planning_state.active_facts ∩ planning_state.profile_fact_ids`.
- It is never derived from `BusinessAffordance.supporting_facts` or completion facts.
- Replay executes stored actions without graph writes and performs one final `validate_replay_checkpoint(...)` call.
- The validation result contains observed semantic location, verified requested business facts, evidence, and a reason; it is returned as replay audit only and is not merged into the graph or candidate memory.

- [ ] **Step 1: Add failing requirement-source tests**

Create a frontier node with:

```python
planning_state.active_facts = ["cart_has_items", "products_sorted"]
planning_state.profile_fact_ids = ["cart_has_items"]
affordance.supporting_facts = ["checkout_button_visible", "products_sorted"]
```

Assert `required_business_facts == ("cart_has_items",)`. The UI supporting fact and ordinary completion fact must be absent.

- [ ] **Step 2: Add failing replay-purity and relaxed-path tests**

Test that replay succeeds when an intermediate Raw Node differs only in sorting/filtering signature or interactable ordering, provided stored actions execute and the final semantic checkpoint validates. Assert byte-identical graph and location memory before/after success and failure.

Test that the final checkpoint fails when:

- observed semantic location is not the expected location;
- any requested active business fact is not verified.

- [ ] **Step 3: Add a non-mutating closed-vocabulary replay checkpoint observation**

Reuse the configured visual provider without running candidate, targeted, or supplement scans. The request must contain only:

```text
expected semantic location
allowed semantic locations
requested business fact IDs and their evidence descriptions
current screenshot/current generic signature
```

The response may only confirm one allowed location and a subset of the requested facts, each with visible evidence. Unknown/malformed/provider-error results fail closed. Do not infer facts from action names.

For structured fallback, recognize already supported deterministic evidence such as `cart_count > 0 -> cart_has_items`; never require an exact `signature["cart_has_items"]` key when equivalent structured evidence exists. If a requested fact cannot be verified without the provider, fail closed.

- [ ] **Step 4: Simplify replay execution validation**

Keep reset success and stored-action execution success checks. Remove per-step Raw Node equality as a hard gate. Perform the semantic checkpoint verification once after the target path is replayed. Updating Explorer's temporary current pointer is allowed; nodes, edges, planning facts, edge metadata, location memory, scan state, and candidate attempts must remain unchanged.

- [ ] **Step 5: Run focused tests and commit**

```powershell
& 'D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe' -m pytest tests/safesym_bridge/test_frontier_replay.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_location_scoped_feasibility_pipeline.py -q
git diff --check
git add src/ai_web_explorer/grounded_web tests/safesym_bridge
git commit -m "fix: validate replay semantic checkpoints"
```

Report the commit and exact test count.

---

### Task 4: Final Regression Gate

**Files:**
- Modify tests only if a deterministic assertion is missing; no feature expansion.

- [ ] **Step 1: Run the complete non-browser suite**

```powershell
$env:PYTHONPATH='src'
& 'D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe' -m pytest -q --ignore=tests/test_local_shop_fixture.py --ignore=tests/safesym_bridge/test_web_kobe_playwright_integration.py
```

- [ ] **Step 2: Inspect repository state**

```powershell
git diff --check
git status --short
git log --oneline b65551f..HEAD
```

Expected: all non-browser tests pass; worktree is clean; exactly three correction commits follow `b65551f` unless a test-only fourth commit is explicitly justified.

- [ ] **Step 3: Stop before real experiment**

Do not run Playwright against the real site and do not call paid Stagehand/VLM services. Report:

- three commit SHAs;
- exact focused and full-suite counts;
- confirmation that profile filtering was exercised through `WebKobeExplorer`, not only the summarizer;
- confirmation that a 19+1 resume writes 20;
- confirmation that replay requirements exclude completion/supporting facts;
- confirmation that replay preserves full graph and location-memory bytes.

Wait for main-session review.
