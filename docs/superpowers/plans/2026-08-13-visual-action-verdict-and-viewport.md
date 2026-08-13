# Visual Action Verdict and Viewport Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fail-soft binary before/after visual action verdict and a configurable desktop viewport without changing semantic facts or PDDL contracts.

**Architecture:** A focused `visual_action_verdict.py` module owns the boolean VLM contract and audit trace. `WebKobeExplorer` consumes a positive verdict only as additional observable-change evidence, while the existing Visual Delta pipeline remains semantic authority. The generic Stagehand runner and CLI own viewport configuration.

**Tech Stack:** Python 3.11, dataclasses, JSON, Playwright async API, pytest.

## Global Constraints

- Work directly on `main`; first confirm it contains commit `ad3423e`.
- Use TDD and make no paid VLM or website calls.
- Do not change tool-choice handling, replay, resume, location memory, semantic profiles, semantic planning, or PDDL compilers.
- Do not add shopping-specific actions, facts, selectors, URLs, or branches.
- The action verdict must never directly create planning facts or locations.

---

### Task 1: Add the binary visual action-verdict contract

**Files:**
- Create: `src/ai_web_explorer/grounded_web/visual_action_verdict.py`
- Modify: `src/ai_web_explorer/grounded_web/__init__.py`
- Create or modify: `tests/safesym_bridge/test_visual_action_verdict.py`

**Interfaces:**
- `VisualActionVerdictRequest(action, before_screenshot_path, after_screenshot_path)`
- `VisualActionVerdictResult(succeeded: bool | None, trace: dict[str, Any])`
- `summarize_visual_action_verdict(request, *, provider) -> VisualActionVerdictResult`
- Provider call uses the same keyword image arguments as `VisualDeltaProvider`.

- [ ] Write failing tests proving the prompt contains the action description and
      asks only for `{"succeeded": true|false}`, both screenshot paths are passed,
      literal booleans parse, and strings/objects/malformed JSON/provider errors
      return `succeeded is None` with an auditable status.
- [ ] Run the new test module and verify RED.
- [ ] Implement the smallest parser and trace model needed by those tests. Do not
      coerce `"true"`, `1`, or truthy objects to booleans.
- [ ] Run the new tests and verify GREEN.

### Task 2: Wire the verdict as fail-soft observed-change evidence

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Modify: `tests/safesym_bridge/test_explorer.py` or the existing explorer test module
- Modify: `tests/safesym_bridge/test_browser_runner.py`

**Interfaces:**
- Add optional `visual_action_verdict_provider` to `WebKobeExplorer`.
- In `run_stagehand_exploration`, reuse the resolved visual provider for this
  narrow call when visual screenshot analysis is enabled; do not add another API
  credential or model option.

- [ ] Add failing explorer tests for: positive verdict adds observable-change
      evidence; false/unknown verdict does not erase URL/signature/Visual Delta
      evidence; missing screenshots skips the call; trace is written into edge
      execution metadata.
- [ ] Add a runner wiring test proving the resolved provider reaches both the
      action-verdict boundary and the existing Visual Delta boundary.
- [ ] Run those tests and verify RED.
- [ ] After after-screenshot capture, invoke the verifier with the selected action
      and existing screenshot paths. Include `verdict is True` in `state_changed`.
      Store its trace under `visual_action_verdict_trace`. Do not add its boolean
      to candidate/completion/business facts or semantic observations.
- [ ] Run the focused tests and verify GREEN.

### Task 3: Add a configurable desktop viewport

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Modify: `tests/safesym_bridge/test_browser_runner.py`
- Modify: `tests/safesym_bridge/test_cli.py`

**Interfaces:**
- `run_stagehand_exploration(..., viewport_width: int = 1440, viewport_height: int = 1000)`
- CLI: `--viewport-width` and `--viewport-height`, both using the existing positive-integer validator.

- [ ] Add failing tests proving default and custom dimensions reach
      `browser.new_page(viewport={"width": width, "height": height})`, and CLI
      rejects zero/negative values.
- [ ] Run the new focused tests and verify RED.
- [ ] Add the two runner parameters and CLI options, wire them through, and keep
      screenshots viewport-sized (no `full_page=True`).
- [ ] Run the focused tests and verify GREEN.

### Task 4: Regression and scope review

- [ ] Run the action-verdict, explorer, browser-runner, CLI, Visual Delta, and
      location-scoped feasibility tests.
- [ ] Run the complete non-browser suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  --ignore=tests/test_local_shop_fixture.py `
  --ignore=tests/safesym_bridge/test_web_kobe_playwright_integration.py
```

- [ ] Run `git diff --check` and inspect production changes for site-specific
      tokens (`shopping`, `product`, `cart`, the practice-site URL). Test fixtures
      may use domain examples; generic production code may not.
- [ ] Commit the implementation on `main` with a concise message and report the
      commit hash, focused/full test counts, changed files, and limitations. Do
      not run a real experiment; the parent task will review first.
