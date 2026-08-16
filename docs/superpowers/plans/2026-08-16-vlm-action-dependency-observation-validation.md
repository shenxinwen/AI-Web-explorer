# VLM Action Dependency Observation Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Validate on frozen Practice Shopping screenshots that a VLM can discover semantic actions, readiness, and visible action ordering without receiving the site's action vocabulary, locations, facts, contracts, workflow, or planning goal.

**Architecture:** Extend only the visual-affordance observation contract and add a standalone frozen-screenshot evaluator. Reuse the existing OpenAI-compatible image provider and archived screenshots. This is a Phase 0 gate: do not wire scheduling, SemanticPlanningGraph, PDDL, or SafeSym.

**Tech Stack:** Python 3.11+, dataclasses, pytest, existing OpenAI-compatible visual provider, JSON, Markdown.

**Spec:** docs/superpowers/specs/2026-08-16-vlm-observed-action-dependency-pddl-mvp-design.zh-CN.md

## Global Constraints

- Do not expose allowed_locations, completion_facts, business_facts, canonical_actions, action_contracts, workflow steps, or a PDDL goal to the prompt.
- Generic action-granularity, visible-requirement, readiness, and action-versus-result guidance is allowed.
- Dependencies remain hypotheses; do not promote them into PDDL in this plan.
- Reuse outputs/experiments/practice_automated_testing/latest/screenshots without modifying or committing screenshots.
- Never print or commit secrets, .env, authorization headers, or payment values.
- Do not execute browser actions or submit an order.
- Preserve all pre-existing working-tree changes.
- Stop after the Phase 0 report for main-task review.

## File Structure

- Modify src/ai_web_explorer/grounded_web/graph.py for backward-compatible action readiness.
- Modify src/ai_web_explorer/grounded_web/business_affordance.py for the prompt and dependency parser.
- Modify src/ai_web_explorer/grounded_web/__init__.py for the new public observation type.
- Modify tests/safesym_bridge/test_business_affordance.py and tests/safesym_bridge/test_location_exploration.py.
- Create examples/evaluate_visual_action_dependencies.py.
- Create tests/test_visual_action_dependency_evaluator.py.
- Create at runtime outputs/experiments/practice_automated_testing/dependency_observation_v0/observations.json.
- Create docs/experiments/practice-shopping-vlm-dependency-observation-v0.md.

---

### Task 1: Define the no-answer observation contract

**Interfaces:**
- Produce ProposedActionDependency(before_action_id: str, after_action_id: str, evidence: tuple[str, ...]).
- Produce VisualAffordanceResult.proposed_dependencies.
- Produce BusinessAffordance.readiness as ready, requires_preparation, or unknown.
- Load older affordance JSON without readiness as unknown.

- [ ] **Step 1: Write a failing prompt-boundary test**

Add a fake-provider test asserting that the prompt contains requires_preparation, dependencies, and action-result attribution, while action_contracts, cart_has_items, and place_order are absent when semantic_profile_context is None.

Example core assertions:

    prompt = captured["prompt"]
    assert "requires_preparation" in prompt
    assert "dependencies" in prompt
    assert "action result" in prompt.lower()
    assert "action_contracts" not in prompt
    assert "cart_has_items" not in prompt
    assert "place_order" not in prompt

- [ ] **Step 2: Run the test and verify expected failure**

Run: .venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_business_affordance.py::test_dependency_prompt_requests_visible_order_without_site_answers -v

Expected: FAIL because the current prompt only requests directly executable actions.

- [ ] **Step 3: Write failing parser tests**

Use a fake response with separate fill_login_credentials (ready) and login (requires_preparation) actions plus:

    {
      "before": "fill_login_credentials",
      "after": "login",
      "evidence": ["The visible form requires username and password."]
    }

Assert normalized readiness and endpoints. Add cases proving self-dependencies and dependencies whose endpoints are absent from the same response are dropped.

- [ ] **Step 4: Implement the minimal contract**

Add:

    VALID_READINESS = frozenset({"ready", "requires_preparation", "unknown"})

    @dataclass(frozen=True)
    class ProposedActionDependency:
        before_action_id: str
        after_action_id: str
        evidence: tuple[str, ...] = ()

Add readiness: str = "unknown" to BusinessAffordance and include it in serialization. Default missing persisted values to unknown.

Update initial and supplement prompt schemas to:
- return ready preparation actions and visible targets requiring preparation;
- keep preparation and submission separate;
- require dependency endpoints in the same response;
- treat visible success text as the preceding action's result;
- use screenshot evidence and generic interface semantics only;
- avoid hidden capabilities and complete-workflow guesses.

Normalize invalid readiness to unknown. Deduplicate endpoint pairs, retain first evidence, and drop missing endpoints and self-dependencies.

- [ ] **Step 5: Run focused and compatibility tests**

Run: .venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_business_affordance.py tests/safesym_bridge/test_location_exploration.py -q

Expected: PASS, including old dictionaries without readiness.

- [ ] **Step 6: Commit Task 1**

Stage only changed Task 1 files and commit with: feat: observe proposed action dependencies

---

### Task 2: Add a frozen-screenshot evaluator

**Interfaces:**
- Consume explicit --screenshots, --output, and optional --model arguments.
- Use create_openai_visual_delta_provider_from_env only in main().
- Expose evaluate_screenshots(..., provider=...) for network-free tests.
- Produce deterministic UTF-8 JSON and no graph edges or browser actions.

- [ ] **Step 1: Write a failing evaluator test**

Test that one fake screenshot and fake provider produce:
- schema_version equal to vlm-action-dependency-observation-v0;
- profile_context_supplied false;
- parsed actions, readiness, and dependencies;
- an output file equal to the returned dictionary.

- [ ] **Step 2: Run the test and verify expected failure**

Run: .venv\Scripts\python.exe -m pytest tests/test_visual_action_dependency_evaluator.py -v

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement the evaluator**

The evaluator must:
1. resolve explicit screenshot paths and reject missing files;
2. always set semantic_profile_context=None;
3. use a neutral goal with no site action or target state;
4. call summarize_visual_affordances once per screenshot;
5. serialize actions, readiness, dependencies, trace status, errors, and SHA-256 of the exact prompt;
6. include prompt-audit booleans for forbidden profile keys and known Practice Shopping answer tokens;
7. write sort_keys=True, two-space-indented UTF-8 JSON;
8. preserve a partial report and return nonzero if a provider or parse call fails.

- [ ] **Step 4: Run evaluator regression tests**

Run: .venv\Scripts\python.exe -m pytest tests/test_visual_action_dependency_evaluator.py tests/safesym_bridge/test_business_affordance.py -q

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Stage only the evaluator and its test. Commit with: test: add frozen dependency observation evaluator

---

### Task 3: Run Phase 0 and stop for review

**Inputs:**
- outputs/experiments/practice_automated_testing/latest/graph.json
- outputs/experiments/practice_automated_testing/latest/stagehand_trace.json
- outputs/experiments/practice_automated_testing/latest/screenshots/*.png

**Outputs:**
- Runtime observations.json under dependency_observation_v0.
- Committed docs/experiments/practice-shopping-vlm-dependency-observation-v0.md.

- [ ] **Step 1: Select the smallest representative screenshot set**

Use graph/trace evidence and visual inspection. Select only states actually present, aiming for initial shopping, cart-changed shopping, incomplete checkout, checkout after one preparation step, and confirmation. Record exact filenames and reasons; do not invent missing states.

- [ ] **Step 2: Run the evaluator**

Run the evaluator with explicit selected paths and:

    --output outputs/experiments/practice_automated_testing/dependency_observation_v0/observations.json

Use the existing .env without echoing it. If the configured endpoint fails, preserve the error and stop; do not switch providers silently.

- [ ] **Step 3: Apply the acceptance rubric**

The outcome is go only if every applicable item passes:
- no profile answer keys or site answer lists occur in the prompt;
- actions correspond to visible operations;
- visibly separate preparation and submission are not collapsed;
- visible form requirements yield sensible dependencies without failure clicks;
- success text is not emitted as a new action;
- every dependency endpoint exists in the same observation;
- hidden future capabilities are not invented;
- names are readable and sufficiently stable.

A major missing visible action or unsafe/fictional dependency is no-go.

- [ ] **Step 4: Write the report**

Record model identifier, provider kind without credentials, screenshot filenames/states, absence of profile context, action/readiness/dependency findings, attribution failures, rubric results, and final go/no-go. State that no browser action, PDDL generation, or SafeSym run occurred.

- [ ] **Step 5: Run final checks**

Run:
- .venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_business_affordance.py tests/safesym_bridge/test_location_exploration.py tests/test_visual_action_dependency_evaluator.py -q
- git diff --check
- git status --short

Expected: tests pass, no secrets/screenshots staged, unrelated user changes untouched.

- [ ] **Step 6: Commit only the reviewed report**

Commit docs/experiments/practice-shopping-vlm-dependency-observation-v0.md with: docs: report dependency observation validation

Do not commit observations.json until it is manually checked and explicitly requested.

- [ ] **Step 7: Stop and report to the main task**

Return commit hashes, exact test results, report path, go/no-go, false positives, omissions, naming drift, compound-action failures, and blockers. Do not begin scheduling, SemanticPlanningGraph, PDDL, or SafeSym work.

## Completion Gate

This Phase 0 plan is complete when the frozen-screenshot report is delivered, even if no-go. Only main-task acceptance can start the next plan:

    persist proposed dependencies
      -> schedule ready preparation actions
      -> verify dependencies through execution
      -> project predecessor completion facts
      -> generate PDDL
      -> SafeSym and real-plan replay acceptance
