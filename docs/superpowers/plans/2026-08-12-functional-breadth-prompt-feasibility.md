# Functional-Breadth Prompt Feasibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate that a domain-neutral affordance prompt can prioritize breadth across visible functional families before repeatedly exploring one local refinement family.

**Architecture:** Change only the JSON prompt produced by `business_affordance._prompt_for_request`. Keep external task goals, planning state, profiles, graph history, parsing, selection, state identity, replay, and PDDL behavior unchanged. Reuse the parser's existing `relevance_hint` and `confidence` support and the explorer's existing relevance-based ordering.

**Tech Stack:** Python 3.11, pytest, JSON prompts, Playwright/Stagehand, OpenAI `gpt-4o-mini` visual provider.

## Global Constraints

- Preserve open-ended exploration; do not inject an external task goal into the prompt.
- Do not add site-specific names or rules to production code.
- Do not introduce parameterized actions, cross-node action history, scheduler changes, state merging, or replay changes.
- Treat `max_candidates` as an upper bound, not a quota.
- Run the live experiment in a new output directory; do not overwrite the baseline.
- If the live run exposes a separate failure, report it with evidence and do not fix it in this implementation.

---

### Task 1: Add the functional-breadth prompt contract

**Files:**
- Modify: `tests/safesym_bridge/test_business_affordance.py:91-126`
- Modify: `src/ai_web_explorer/grounded_web/business_affordance.py:47-105`

**Interfaces:**
- Consumes: `VisualAffordanceRequest(goal, current_screenshot_path, current_signature, max_actions)`; `goal` remains intentionally excluded from the serialized prompt.
- Produces: the existing JSON prompt schema with action fields `intent`, `label`, `target`, `relevance_hint`, `confidence`, and `supporting_facts`.

- [ ] **Step 1: Replace the old prompt-isolation test with a failing breadth-and-isolation contract test**

Replace `test_visual_affordance_prompt_ignores_external_task_goal` with this parameterized test. It retains the task-isolation assertions and adds only the new domain-neutral prompt contract:

```python
@pytest.mark.parametrize(
    "external_goal",
    ["Reach checkout immediately", "Delete the selected document"],
)
def test_visual_affordance_prompt_prioritizes_breadth_without_external_task_goal(
    external_goal,
):
    request = VisualAffordanceRequest(
        goal=external_goal,
        current_screenshot_path="current.png",
        current_signature={"url_path": "/inventory"},
    )

    def provider(prompt, *, current_screenshot_path):
        payload = json.loads(prompt)
        instruction = payload["instruction"]
        action_schema = payload["output_schema"]["regions"][0]["actions"][0]

        assert "breadth of functional coverage" in instruction
        assert "one representative action per functional family" in instruction
        assert "new surface, object, dialog, page, or workflow stage" in instruction
        assert "local refinement" in instruction
        assert "concrete visible target" in instruction
        assert action_schema["relevance_hint"] == "core | supporting | low_value"
        assert action_schema["confidence"] == "number from 0.0 to 1.0"

        assert "profile" not in payload
        assert "current_planning_facts" not in payload
        assert request.goal not in prompt
        assert "pddl" not in prompt.lower()
        assert "graph" not in prompt.lower()
        assert "web-kobe" not in prompt.lower()
        assert "checkout" not in prompt.lower()
        assert "cart_has_items" not in prompt
        return '{"page_mode":"uncertain","regions":[]}'

    result = summarize_visual_affordances(request, provider=provider)

    assert result.trace.status == "summarized"
```

- [ ] **Step 2: Run the new test and verify RED**

Run:

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest tests/safesym_bridge/test_business_affordance.py::test_visual_affordance_prompt_prioritizes_breadth_without_external_task_goal -q
```

Expected: both parameter cases fail because the prompt does not yet contain `breadth of functional coverage` and the output schema does not contain `relevance_hint` or `confidence`.

- [ ] **Step 3: Make the minimal production prompt change**

In `_prompt_for_request`, retain all existing visible-evidence and page-mode rules. Add the following domain-neutral text to the `instruction` string before the existing action-validity rules:

```python
"Optimize for breadth of functional coverage, not interaction count. "
"Choose at most one representative action per functional family. "
"Prioritize actions likely to reveal a new surface, object, dialog, page, "
"or workflow stage as core. Classify major same-surface functions as "
"supporting. Classify local refinement actions as low_value when broader "
"functions are available. Order core actions before supporting actions, "
"and supporting actions before low_value actions. Avoid ambiguous umbrella "
"actions: every action must name one concrete visible target. "
```

Do not mention filters, sorting, products, carts, checkout, shopping, documents, or any other site-specific domain in production prompt text.

Add these fields to each action in `output_schema`, between `target` and `supporting_facts`:

```python
"relevance_hint": "core | supporting | low_value",
"confidence": "number from 0.0 to 1.0",
```

Do not add `request.goal`, `current_signature`, graph history, profile data, or planning facts to `payload`.

- [ ] **Step 4: Run the focused prompt tests and verify GREEN**

Run:

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest tests/safesym_bridge/test_business_affordance.py -q
```

Expected: all tests in the file pass.

- [ ] **Step 5: Run selector regression tests**

Run:

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest tests/safesym_bridge/test_web_kobe_explorer.py -q
```

Expected: all tests pass, including existing relevance/confidence ordering and tried-action suppression tests. Do not change selector production code if a failure is unrelated to the prompt contract; report it.

- [ ] **Step 6: Commit the prompt change**

```powershell
git add -- tests/safesym_bridge/test_business_affordance.py src/ai_web_explorer/grounded_web/business_affordance.py
git commit -m "feat: prioritize functional breadth in affordance prompt"
```

---

### Task 2: Verify regressions and run the bounded live feasibility experiment

**Files:**
- Create at runtime: `outputs/experiments/practice_automated_testing/frontier_replay_v1_mini_breadth_prompt_20260812/graph.json`
- Create at runtime: `outputs/experiments/practice_automated_testing/frontier_replay_v1_mini_breadth_prompt_20260812/stagehand_trace.json`
- Create at runtime: `outputs/experiments/practice_automated_testing/frontier_replay_v1_mini_breadth_prompt_20260812/screenshots/`
- Compare: `outputs/experiments/practice_automated_testing/frontier_replay_v1_mini_full_20260812/graph.json`

**Interfaces:**
- Consumes: the revised prompt through the existing `web-kobe-stagehand-explore` CLI.
- Produces: a six-step graph and trace used only for feasibility review; no committed schema or fixture changes.

- [ ] **Step 1: Run the complete non-browser regression suite**

Run:

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest -q
```

Expected: the same environment-gated browser skips as the current mainline and no new failures. Record exact passed/failed/skipped counts.

- [ ] **Step 2: Run a fresh six-step live experiment and wait for completion**

Run with a command timeout of at least 15 minutes; VLM and Stagehand responses can legitimately take tens of seconds per step:

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m ai_web_explorer.safesym_bridge.cli web-kobe-stagehand-explore `
  --url 'https://practiceautomatedtesting.com/shopping' `
  --app-name 'practice_automated_testing' `
  --output 'outputs/experiments/practice_automated_testing/frontier_replay_v1_mini_breadth_prompt_20260812/graph.json' `
  --stagehand-trace 'outputs/experiments/practice_automated_testing/frontier_replay_v1_mini_breadth_prompt_20260812/stagehand_trace.json' `
  --steps 6 `
  --max-candidates 5 `
  --frontier-replay `
  --openai-visual-delta `
  --visual-delta-model 'gpt-4o-mini' `
  --screenshot-dir 'outputs/experiments/practice_automated_testing/frontier_replay_v1_mini_breadth_prompt_20260812/screenshots' `
  --stagehand-execution-mode observed_action
```

Expected: the command exits normally and `graph.json` contains `meta.exploration_summary.steps_completed` greater than zero. Slow responses are not failures; wait while the process remains alive and artifacts continue to update.

- [ ] **Step 3: Print a compact baseline-versus-experiment report**

Run:

```powershell
@'
import json
from pathlib import Path

paths = {
    "baseline": Path("outputs/experiments/practice_automated_testing/frontier_replay_v1_mini_full_20260812/graph.json"),
    "breadth_prompt": Path("outputs/experiments/practice_automated_testing/frontier_replay_v1_mini_breadth_prompt_20260812/graph.json"),
}
for label, path in paths.items():
    data = json.loads(path.read_text(encoding="utf-8"))
    actions = [edge["action"]["semantic_id"] for edge in data.get("edges", [])]
    start_id = data["meta"]["start_node_id"]
    start = next(node for node in data["nodes"] if node["node_id"] == start_id)
    candidates = [
        {
            "action": item["action_name"],
            "relevance": item.get("relevance_hint"),
            "target": item.get("target_hint"),
        }
        for item in start.get("business_affordances", [])
    ]
    print(json.dumps({
        "run": label,
        "nodes": len(data.get("nodes", [])),
        "edges": len(data.get("edges", [])),
        "actions": actions,
        "start_candidates": candidates,
        "replay_attempts": data.get("meta", {}).get("replay_attempt_count", 0),
        "replay_successes": data.get("meta", {}).get("replay_success_count", 0),
        "steps": data.get("meta", {}).get("exploration_summary", {}).get("steps_completed"),
    }, ensure_ascii=False))
'@ | & '.venv/Scripts/python.exe' -
```

Expected baseline evidence: early productive actions are dominated by the same local refinement family. Feasibility succeeds when the new start candidates cover multiple functional families with boundary/major functions ranked above local refinements, and the executed trace reaches a non-refinement function before repeating the same refinement family. If Stagehand execution fails but candidate ordering satisfies this condition, report Prompt feasibility separately from execution failure.

- [ ] **Step 4: Report results without expanding scope**

Report:

1. exact test counts;
2. initial candidate order and relevance labels for baseline and new run;
3. executed semantic action sequence;
4. whether the Prompt-only feasibility criterion passed;
5. replay/action-execution issues as separate observations;
6. `git status --short` and the implementation commit hash.

Do not generate or solve PDDL in this experiment. Do not repair parameterization, state splitting, replay, Stagehand tool calling, or scheduling even if those issues recur.

