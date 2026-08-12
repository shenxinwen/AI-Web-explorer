# Location-Scoped Exploration Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the real feasibility runtime so evidenced business facts, bounded recovery, safe final submission, and location-scoped candidate execution work outside the synthetic fixture.

**Architecture:** Keep the existing location memory and semantic projection. Make the parsed experiment profile a runtime authority, centralize action-budget consumption and replay validation, then add a conservative DOM preflight at the candidate boundary. Do not create a second explorer or compiler.

**Tech Stack:** Python 3.11, dataclasses, pytest/AnyIO, existing WebKobe graph/Stagehand/Playwright adapters, existing Minimal Semantic PDDL compiler.

## Global Constraints

- Work only in `D:\GitHUb\ai-web-explorer-main\.worktrees\location-scoped-open-exploration` on `codex/location-scoped-open-exploration`.
- Reuse `D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe` and local caches; do not redownload dependencies.
- Do not run Task 8, the real website, a paid VLM, or final external submission.
- Do not merge to `main`.
- Preserve legacy behavior when no semantic experiment profile is selected.
- No site-specific selectors, action order, products, credentials, or SafeSym goal in generic explorer/compiler code.
- After every task: run focused tests, run `git diff --check`, commit, and report the commit SHA.

---

### Task 1: Connect Evidenced Business Facts and Fail-Closed Final-Order Authorization

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/exploration_semantics.py`
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Test: `tests/safesym_bridge/test_planning_fact_verifier.py`
- Test: `tests/safesym_bridge/test_browser_runner.py`
- Test: `tests/safesym_bridge/test_cli.py`
- Test: `tests/safesym_bridge/test_location_scoped_feasibility_pipeline.py`

**Interfaces:**
- Explorer consumes a `SemanticExperimentProfile | None`, not only its prompt dictionary.
- `verify_experiment_planning_delta(profile, observable_change, candidate_added_facts, candidate_removed_facts, evidence, structured_delta)` produces the authoritative planning delta in profile mode.
- Introduce one pure authorization validator such as `validate_final_order_authorization(start_url, profile, allowed)`; both CLI and runner use it.

- [ ] **Step 1: Add failing runtime integration tests**

Add a fixture transition whose before/after signatures contain only generic visible structure. Its VLM response supplies `checkout_info_complete`, then `payment_info_complete`, then `order_submitted` with non-empty evidence and observable visual change. Assert the edge planning deltas contain those verified facts and the compiled problem reaches `at_confirmation + order_submitted`. Assert an invented fact and an allowed fact without evidence are rejected.

- [ ] **Step 2: Prove the tests fail for the production-path reason**

Run:

```powershell
$env:PYTHONPATH='src'
& 'D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe' -m pytest tests/safesym_bridge/test_location_scoped_feasibility_pipeline.py tests/safesym_bridge/test_planning_fact_verifier.py -q
```

Expected: the runtime integration assertion fails because only `verify_planning_delta()` is used.

- [ ] **Step 3: Wire the experiment verifier after final observable-change calculation**

Store the actual profile on `WebKobeExplorer`. Calculate `structured_planning_delta` first, collect visual candidates/evidence, calculate deterministic final observable change, then replace `planning_delta` with the experiment verifier result in profile mode. Build/apply `PlanningTransition` only after this final delta exists. Do not verify a VLM fact merely because the action name suggests it.

- [ ] **Step 4: Add failing authorization matrix tests**

Cover all combinations:

```text
practice profile + flag + exact controlled URL -> allowed
practice profile + no flag -> no authorization
practice profile + flag + other URL -> ValueError
no profile + flag -> ValueError
other profile + flag -> ValueError
```

Also assert `GeneratedCheckoutData.to_benchmark_context()` contains fictional data but no final-order permission.

- [ ] **Step 5: Implement one fail-closed authorization boundary**

Normalize URL scheme/host/path without accepting subdomains, query tricks, redirects, or prefix paths. Render final-order permission only after validation. Keep generated data available for form filling without granting submission.

- [ ] **Step 6: Run focused tests and commit**

```powershell
& 'D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe' -m pytest tests/safesym_bridge/test_location_scoped_feasibility_pipeline.py tests/safesym_bridge/test_planning_fact_verifier.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_cli.py -q
git diff --check
git add src/ai_web_explorer tests/safesym_bridge
git commit -m "fix: connect evidenced feasibility facts"
```

Stop and report Task 1 evidence before starting Task 2.

---

### Task 2: Enforce the Semantic Profile Contract at Runtime

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/exploration_semantics.py`
- Modify: `src/ai_web_explorer/grounded_web/visual_delta.py`
- Modify: `src/ai_web_explorer/grounded_web/semantic_model.py` only if a shared validation helper is required; do not expand the role vocabulary.
- Test: `tests/safesym_bridge/test_exploration_semantics.py`
- Test: `tests/safesym_bridge/test_visual_delta_summarizer.py`

**Interfaces:**
- All profile action-role examples are members of `SEMANTIC_ACTION_ROLES`.
- Add a profile-aware semantic observation validator that returns the accepted observation plus structured rejection reasons for trace metadata.

- [ ] **Step 1: Add failing role-vocabulary and allow-list tests**

Assert every profile role is accepted by the parser. Test rejection of an unknown location, invented completion fact, business fact outside the allow-list, mismatched source location, and presentation navigation. Test acceptance of each approved mapping.

- [ ] **Step 2: Run tests and verify current failures**

```powershell
& 'D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe' -m pytest tests/safesym_bridge/test_exploration_semantics.py tests/safesym_bridge/test_visual_delta_summarizer.py -q
```

Expected: invalid current role examples normalize to `unknown`; out-of-profile locations/facts are currently accepted.

- [ ] **Step 3: Correct mappings and implement fail-closed filtering**

Use exactly the role mapping from the remediation design. Filter observations before edge construction. Preserve rejected raw values in `VisualDeltaTrace.llm_response`, and add deterministic rejection reasons to trace metadata; never silently promote them.

- [ ] **Step 4: Run focused tests and commit**

```powershell
& 'D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe' -m pytest tests/safesym_bridge/test_exploration_semantics.py tests/safesym_bridge/test_visual_delta_summarizer.py tests/safesym_bridge/test_semantic_planning.py -q
git diff --check
git add src/ai_web_explorer/grounded_web tests/safesym_bridge
git commit -m "fix: enforce feasibility semantic contract"
```

Stop and report Task 2 evidence before starting Task 3.

---

### Task 3: Make Budgets and Replay Semantics Correct Across Resume

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/controller.py`
- Modify: `src/ai_web_explorer/grounded_web/frontier_replay.py`
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Modify: `src/ai_web_explorer/grounded_web/resume.py` only to isolate legacy policy from location-memory authority.
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Test: `tests/safesym_bridge/test_web_kobe_controller.py`
- Test: `tests/safesym_bridge/test_frontier_replay.py`
- Test: `tests/safesym_bridge/test_browser_runner.py`
- Test: `tests/safesym_bridge/test_resume.py`

**Interfaces:**
- One persisted runtime-budget state owns formal attempts, consecutive no-progress, replay totals, and per-frontier replay failures.
- A formal action is counted exactly when Stagehand execution begins, regardless of success or whether it follows replay.
- Replay validation consumes expected semantic location and required business facts and returns audit data without mutating graph edges.

- [ ] **Step 1: Add failing cumulative-budget tests**

Cover: resume after 19 formal attempts permits one more; resume after two no-progress attempts stops after one more; replay-success follow-up consumes formal budget; a 20-attempt checkpoint runs zero actions; Runner passes the configured three-step no-progress limit instead of `None`.

- [ ] **Step 2: Add failing replay purity and semantic validation tests**

Serialize the complete graph before and after successful and failed replay and assert byte equality, excluding only explicitly separated run metrics. Assert same Raw Node with missing `cart_has_items` fails recovery when the frontier action requires it. Assert ordinary `products_sorted` is ignored during recovery.

- [ ] **Step 3: Centralize counters and remove edge mutation from replay**

Restore counters before controller execution, compute remaining formal attempts, and route both normal and post-replay actions through one counter. Replace `_mark_edge(... verified/unstable)` with run-level audit entries. Do not alter candidate memory during replay.

- [ ] **Step 4: Make location memory authoritative for retries**

In location-scoped mode, allow `retryable_no_change` and `retryable_failure` while attempts remain even if legacy event history would reject them. Preserve legacy ResumePolicy behavior outside profile mode.

- [ ] **Step 5: Run focused tests and commit**

```powershell
& 'D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe' -m pytest tests/safesym_bridge/test_web_kobe_controller.py tests/safesym_bridge/test_frontier_replay.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_resume.py -q
git diff --check
git add src/ai_web_explorer tests/safesym_bridge
git commit -m "fix: preserve exploration budgets across replay"
```

Stop and report Task 3 evidence before starting Task 4.

---

### Task 4: Add Conservative Candidate Preflight and Replace the Synthetic Acceptance Shortcut

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/location_exploration.py`
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Test: `tests/safesym_bridge/test_location_exploration.py`
- Modify: `tests/safesym_bridge/test_location_scoped_feasibility_pipeline.py`

**Interfaces:**
- Add a small result type with status `available | stale | unknown` and evidence.
- Coordinator candidate selection accepts current interactables and preflights without a VLM call.
- Only `stale` transitions candidate status to `stale/disabled`; `unknown` remains executable.

- [ ] **Step 1: Add failing preflight tests**

Test exact visible canonical ID/target as available, explicit disabled/absent known target as stale, ambiguous label or missing DOM metadata as unknown, and verify stale consumes zero formal attempts.

- [ ] **Step 2: Implement the minimal preflight boundary**

Keep the implementation generic and deterministic. Reuse canonical IDs and grounded target metadata already present in interactables/affordances. Do not add site selectors or fuzzy semantic inference.

- [ ] **Step 3: Strengthen the end-to-end fixture**

Remove injected semantic business keys from `StateSnapshot.signature`. Drive all checkout/payment/order facts through VLM evidence and the production experiment verifier. Assert:

- each canonical action is attempted at most once after success within its location;
- no-change receives exactly two attempts;
- targeted scan occurs once for the cart fact delta;
- stale candidates consume no formal attempt;
- replay leaves graph JSON unchanged;
- PDDL reaches `at_confirmation` and `order_submitted` with necessary business preconditions and no ordinary capability prerequisites.

- [ ] **Step 4: Run all non-browser tests and commit**

```powershell
$env:PYTHONPATH='src'
& 'D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe' -m pytest -q --ignore=tests/test_local_shop_fixture.py --ignore=tests/safesym_bridge/test_web_kobe_playwright_integration.py
git diff --check
git status --short
git add src/ai_web_explorer tests/safesym_bridge
git commit -m "fix: preflight location candidates safely"
```

Expected: all non-browser tests pass and only the four remediation commits are ahead of `9286b1c`.

Stop. Do not run the real experiment. Report commit SHAs, exact test counts, remaining skipped browser gates, and any intentional deviations for main-session review.
