# VLM Prompt and Model Split Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the offline-validated candidate/dependency prompt and action-outcome prompt into the active location-scoped path, using `gpt-4o-mini` for candidate scans and `gpt-4o` for action-outcome observation.

**Architecture:** Keep the existing four-field initial scan and three-field outcome contracts unchanged. Add only prompt examples and a separately configurable outcome provider/model; do not modify Stagehand execution, candidate scheduling, graph projection, PDDL, targeted scans, or supplement scans. Preserve explicit-provider compatibility while making the OpenAI-backed active path construct independent candidate and outcome providers.

**Tech Stack:** Python 3.11, dataclasses, OpenAI-compatible Chat Completions, pytest.

**Spec:** `docs/superpowers/specs/2026-08-18-location-candidate-dependency-integration-design.zh-CN.md`

## Global Constraints

- Candidate discovery receives no profile facts, action contracts, expected workflow, prior candidate answers, or PDDL goal.
- Candidate response remains exactly `actions[].{action_id,description,target,requires}`.
- Outcome response remains exactly `{outcome,location_change,evidence}`.
- Candidate model default is `gpt-4o-mini`; outcome model default is `gpt-4o`; both remain independently configurable.
- `uncertain` remains a valid fail-closed outcome but the prompt prefers evidence-backed `success` or `failed`.
- Few-shot examples must remain domain-neutral and must not contain shopping, cart, checkout, payment, order, Practice Shopping, or SafeSym planning answers.
- Do not call or modify Stagehand SDK behavior in this implementation.
- Do not add action-name-specific logic for filtering or any other website action.
- Runtime experiment JSON under `outputs/` remains uncommitted.

---

### Task 1: Integrate the validated candidate/dependency prompt

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/business_affordance.py:62-93`
- Test: `tests/safesym_bridge/test_business_affordance.py`

**Interfaces:**
- Consumes: `VisualAffordanceRequest.max_actions` and the existing initial `output_schema`.
- Produces: the same `_prompt_for_request(request) -> str` payload with a revised `instruction` and a `few_shot_examples` array; parsing and result types do not change.

- [ ] **Step 1: Add failing prompt-contract tests**

Add tests that capture and parse the initial prompt outside the provider callback, then assert:

```python
payload = json.loads(captured["prompt"])
assert set(payload) == {"instruction", "max_candidates", "output_schema", "few_shot_examples"}
assert set(payload["output_schema"]) == {"actions"}
assert len(payload["few_shot_examples"]) == 3
assert "active interaction surface" in payload["instruction"]
assert "limit is not a quota" in payload["instruction"]
assert "independently" in payload["instruction"]
assert "profile" not in captured["prompt"].lower()
assert "checkout" not in captured["prompt"].lower()
assert "payment" not in captured["prompt"].lower()
assert result.trace.status == "summarized"
```

Also assert the three examples cover these generic cases without website-specific words:

```text
Create Project dialog: group related required fields into complete_project_details;
data-table toolbar: sort and column controls are independent;
Export Complete modal: ignore dimmed background and return only download_report.
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_business_affordance.py -q --tb=short
```

Expected: the new prompt/few-shot assertions fail while existing parser tests pass.

- [ ] **Step 3: Replace only the initial instruction and add generic few-shots**

Implement the approved rules in `_prompt_for_request`:

```text
an active surface is the frontmost operable page/dialog/drawer/modal;
covered background controls are not candidates;
return directly executable actions and visible blocked actions;
related controls serving one purpose may be grouped into one semantic action;
requires means an indispensable direct prerequisite, not recommendation, visual order, or independent-field order;
completed/history/result states are not actions or requirements;
return at most request.max_actions and allow an empty list.
```

Put the three approved examples in a top-level `few_shot_examples` list. Do not put the illustrative checkout output from the discussion into production code.

- [ ] **Step 4: Run candidate prompt and parser regression tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_business_affordance.py tests/safesym_bridge/test_location_exploration.py -q --tb=short
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```powershell
git add src/ai_web_explorer/grounded_web/business_affordance.py tests/safesym_bridge/test_business_affordance.py
git commit -m "feat: refine candidate dependency observation prompt"
```

---

### Task 2: Integrate the validated action-outcome prompt

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/action_outcome.py:79-110`
- Test: `tests/safesym_bridge/test_action_outcome.py`

**Interfaces:**
- Consumes: `build_action_outcome_prompt(action_description: str)`.
- Produces: the same JSON payload and the unchanged `ActionOutcomeResult(outcome, location_change, evidence)` parser contract.

- [ ] **Step 1: Add failing tests for the revised outcome prompt**

Parse `build_action_outcome_prompt("Apply a visible filter")` and assert:

```python
assert set(payload) == {
    "instruction", "action_description", "output_schema", "few_shot_examples"
}
assert set(payload["output_schema"]) == {
    "outcome", "location_change", "evidence"
}
assert len(payload["few_shot_examples"]) == 5
assert "prefer a definite success or failed judgment" in payload["instruction"]
assert "same main heading, controls, and page layout" in payload["instruction"]
assert "location_change must be false" in payload["instruction"]
```

Assert the examples are domain-neutral and cover:

```text
record filtering -> success/false;
table sorting -> success/false;
stable export modal -> success/true;
visible form validation -> failed/false;
project-detail completion -> success/false.
```

Assert no example demonstrates `uncertain`, while the output schema still lists it.

- [ ] **Step 2: Run the focused test and verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_action_outcome.py -q --tb=short
```

Expected: new prompt assertions fail.

- [ ] **Step 3: Implement the approved instruction and five few-shots**

Use the exact semantic boundary validated offline:

```text
prefer visible-evidence success or failed;
use uncertain only for missing/uncomparable/conflicting images;
location_change means a different stable active interaction surface;
field values, counts, selections, filtering, search, sorting, pagination, and styling remain the same location;
if main heading, controls, and layout remain active and only items change, location_change=false;
stable page/modal/drawer/detail/workflow/result interfaces can change location;
brief toast/loading/dropdown/temporary acknowledgement cannot.
```

Do not change `parse_action_outcome`, semantic projection, or the allowed enum.

- [ ] **Step 4: Run outcome and explorer regression tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_action_outcome.py tests/safesym_bridge/test_web_kobe_explorer.py -q --tb=short
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```powershell
git add src/ai_web_explorer/grounded_web/action_outcome.py tests/safesym_bridge/test_action_outcome.py
git commit -m "feat: refine action outcome observation prompt"
```

---

### Task 3: Split candidate and outcome model configuration

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/openai_visual_delta.py`
- Modify: `src/ai_web_explorer/grounded_web/__init__.py`
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py:453-548,585-731`
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Modify: `.env.example`
- Test: `tests/safesym_bridge/test_action_outcome.py`
- Test: `tests/safesym_bridge/test_browser_runner.py`
- Test: `tests/safesym_bridge/test_cli.py`

**Interfaces:**
- Produces: `DEFAULT_OPENAI_ACTION_OUTCOME_MODEL = "gpt-4o"`.
- Produces: `create_openai_action_outcome_provider_from_env(*, model=None, request_timeout_seconds=None, openai_factory=None, load_dotenv=None, environ=None) -> OpenAIVisualDeltaProvider`.
- Adds runner keyword arguments `action_outcome_provider=None` and `action_outcome_model: str | None = None`.
- Adds CLI option `--action-outcome-model`, default `None`, allowing `OPENAI_ACTION_OUTCOME_MODEL` or the code default to resolve it.

- [ ] **Step 1: Add failing provider default tests**

Add a fake OpenAI factory test:

```python
provider = create_openai_action_outcome_provider_from_env(
    openai_factory=fake_factory,
    load_dotenv=lambda: None,
    environ={"OPENAI_API_KEY": "test-key"},
)
assert provider.model == "gpt-4o"

provider = create_openai_action_outcome_provider_from_env(
    openai_factory=fake_factory,
    load_dotenv=lambda: None,
    environ={
        "OPENAI_API_KEY": "test-key",
        "OPENAI_ACTION_OUTCOME_MODEL": "custom-outcome-model",
    },
)
assert provider.model == "custom-outcome-model"
```

Keep the existing candidate provider assertion `provider.model == "gpt-4o-mini"`.

- [ ] **Step 2: Add failing runner and CLI wiring tests**

For `run_stagehand_exploration`, monkeypatch both factories and assert the Explorer receives different provider objects:

```python
assert explorer.visual_delta_provider is candidate_provider
assert explorer.action_outcome_provider is outcome_provider
```

Assert explicit `visual_delta_provider` and explicit `action_outcome_provider` are preserved without factory calls. For backward compatibility, when only an explicit `visual_delta_provider` is supplied, reuse it for action outcomes unless an explicit outcome provider is supplied.

Add CLI parsing/forwarding assertions:

```text
--visual-delta-model gpt-4o-mini
--action-outcome-model gpt-4o
```

- [ ] **Step 3: Run tests and verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_action_outcome.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_cli.py -q --tb=short
```

Expected: missing factory/arguments/CLI option failures.

- [ ] **Step 4: Implement the separate outcome provider factory**

Reuse `OpenAIVisualDeltaProvider`; do not create a duplicate transport class. The new factory resolves models in this order:

```text
explicit model argument
OPENAI_ACTION_OUTCOME_MODEL
DEFAULT_OPENAI_ACTION_OUTCOME_MODEL (gpt-4o)
```

It must continue using `OPENAI_API_KEY`, optional `OPENAI_BASE_URL`, temperature `0`, and the same request timeout behavior.

- [ ] **Step 5: Wire independent providers into browser runners**

When `use_openai_visual_delta=True`, construct:

```python
resolved_visual_delta_provider = create_openai_visual_delta_provider_from_env(
    model=visual_delta_model,
    request_timeout_seconds=vlm_request_timeout_seconds,
)
resolved_action_outcome_provider = create_openai_action_outcome_provider_from_env(
    model=action_outcome_model,
    request_timeout_seconds=vlm_request_timeout_seconds,
)
```

Pass the first only to candidate/legacy visual observation inputs and the second to `WebKobeExplorer.action_outcome_provider`. Apply the same split to both runner construction sites currently assigning one resolved provider to both fields.

- [ ] **Step 6: Wire the CLI and environment example**

Add `--action-outcome-model` beside `--visual-delta-model`, forward it to the runner, and document:

```dotenv
OPENAI_VISUAL_DELTA_MODEL=gpt-4o-mini
OPENAI_ACTION_OUTCOME_MODEL=gpt-4o
```

Do not change `STAGEHAND_MODEL`.

- [ ] **Step 7: Run focused model-split tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_action_outcome.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_cli.py -q --tb=short
```

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

```powershell
git add .env.example src/ai_web_explorer/grounded_web/openai_visual_delta.py src/ai_web_explorer/grounded_web/__init__.py src/ai_web_explorer/safesym_bridge/browser_runner.py src/ai_web_explorer/safesym_bridge/cli.py tests/safesym_bridge/test_action_outcome.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_cli.py
git commit -m "feat: split candidate and outcome VLM models"
```

---

### Task 4: Record experiment evidence and verify the integration

**Files:**
- Modify: `docs/superpowers/specs/2026-08-18-location-candidate-dependency-integration-design.zh-CN.md`
- Modify: `docs/current-project-overview.zh-CN.md`
- Modify: `docs/project-decisions.zh-CN.md`
- Modify: `docs/safesym-bridge.md`
- Create: `docs/experiments/practice-shopping-vlm-dependency-outcome-acceptance-v1.md`

**Interfaces:**
- Consumes: runtime-only JSON under `outputs/experiments/practice_automated_testing/vlm_dependency_acceptance_v1/`.
- Produces: a committed evidence summary and updated active configuration documentation; does not commit screenshots, credentials, or raw runtime JSON.

- [ ] **Step 1: Write the evidence report**

Document these observed results without overstating scope:

```text
Candidate prompt v1: 9/9 structurally valid, semantic NO-GO due to field-chain dependencies and covered-background actions.
Candidate prompt v2 with three generic few-shots: 9/9 structurally valid; shopping actions independent, checkout dependency grouping stable, confirmation returned only download_invoice_pdf.
Outcome gpt-4o-mini initial: filtering location false 0/3.
Outcome gpt-4o-mini strengthened prompt: filtering location false 1/3; all other five cases 15/15 correct.
Outcome gpt-4o strengthened prompt, filtering-only control: filtering location false 3/3.
No Stagehand call, browser execution, PDDL generation, SafeSym injection, or planner run occurred in this offline experiment.
```

State the accepted model split and the limitation that the `gpt-4o` comparison currently covers only the filtering transition, not all transition types.

- [ ] **Step 2: Align active docs and spec**

Change the spec statement that the default experiment model is only `gpt-4o-mini` to the accepted split. Document both environment variables and clarify that Stagehand's model remains independent.

- [ ] **Step 3: Run the complete regression suite**

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge -q --tb=short
.venv\Scripts\python.exe -m pytest -q --tb=short
git diff --check
```

If the only full-suite failure is Playwright `spawn EPERM` in the restricted sandbox, rerun exactly `tests/test_local_shop_fixture.py` with approved local browser permission and record both results.

- [ ] **Step 4: Audit prompt leakage and git scope**

Run:

```powershell
git diff --check
git status --short
rg -n "Practice Shopping|practice_automated_testing|place_order|checkout|payment" src/ai_web_explorer/grounded_web/business_affordance.py
```

Expected: no site-specific answer token appears in the candidate prompt or its few-shots. References in outcome action descriptions, tests, docs, or experiment evidence must be clearly outside the candidate prompt.

- [ ] **Step 5: Commit Task 4**

```powershell
git add docs/superpowers/specs/2026-08-18-location-candidate-dependency-integration-design.zh-CN.md docs/current-project-overview.zh-CN.md docs/project-decisions.zh-CN.md docs/safesym-bridge.md docs/experiments/practice-shopping-vlm-dependency-outcome-acceptance-v1.md
git commit -m "docs: record VLM observation acceptance"
```

---

## Handoff Acceptance

The implementation session is complete only when:

1. Candidate and outcome response schemas are unchanged and strict.
2. Candidate prompt contains the three approved domain-neutral examples.
3. Outcome prompt contains the five approved domain-neutral examples.
4. OpenAI-backed active exploration independently resolves `gpt-4o-mini` for candidates and `gpt-4o` for outcomes.
5. Explicit provider injection remains backward compatible and test-covered.
6. Stagehand provider/model behavior is untouched.
7. Focused and bridge tests pass; full-suite browser restrictions are reported honestly.
8. No runtime JSON, screenshot, `.env`, API key, or unrelated file is committed.
9. The report states that a real Stagehand/PDDL/SafeSym experiment is the next acceptance stage, not part of this implementation.
