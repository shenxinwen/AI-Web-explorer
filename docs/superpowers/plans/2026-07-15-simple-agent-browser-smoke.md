# Simple Agent Browser Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Subagent-driven execution is intentionally not the default for this project because the user requested single-agent work unless explicitly allowed.

**Goal:** Prove `SimpleGroundedWebAgent` can operate a real browser fixture and record state deltas for click/fill/select.

**Architecture:** Reuse the existing `SimpleGroundedWebAgent`, `WebKobePlaywrightAdapter`, DOM observer, action builder, and Web-KOBE graph path. Add one browser smoke for `local_shop`, one minimal `local_form` fixture, and the smallest DOM/action extraction enhancement needed for `select` actions to have a real option value.

**Tech Stack:** Python 3.11+, pytest/anyio, Playwright async API, existing SafeSym bridge modules.

## Global Constraints

- Do not introduce LLM action selection.
- Do not add a new exploration strategy.
- Do not duplicate Web-KOBE explorer/controller logic.
- Keep browser operation DOM-grounded.
- Keep changes limited to fixture/test coverage and minimal input/select candidate support.
- Do not use subagents unless explicitly permitted.

---

## File Structure

- Modify `src/ai_web_explorer/safesym_bridge/dom_observer.py`
  - Include select option values in candidate metadata.

- Modify `src/ai_web_explorer/safesym_bridge/web_action_extractor.py`
  - Add input values for `fill` and `select` browser actions.

- Create `tests/fixtures/local_form/index.html`
  - Minimal form fixture with input, select, submit, and `[data-state]` indicators.

- Create `tests/safesym_bridge/test_simple_grounded_web_agent_browser.py`
  - Real browser smoke tests for `local_shop` and `local_form`.

---

### Task 1: Add real browser smoke for existing local_shop

**Files:**
- Create: `tests/safesym_bridge/test_simple_grounded_web_agent_browser.py`

**Interfaces:**
- Consumes:
  - `SimpleGroundedWebAgent`
  - `WebKobePlaywrightAdapter`
  - `tests/fixtures/local_shop/index.html`
- Produces:
  - A browser test proving the facade can run the existing click-based fixture.

Steps:

1. Write a Playwright async test that opens `local_shop`, builds `WebKobePlaywrightAdapter`, wraps it in `SimpleGroundedWebAgent`, runs `max_steps=3`, and asserts `cart_panel_visible` / `cart_count` deltas.
2. Run the test. If Chromium launch fails with `spawn EPERM`, rerun with elevated permissions.
3. Commit the test if it passes without production changes.

---

### Task 2: Add local_form fixture and fill/select action support

**Files:**
- Create: `tests/fixtures/local_form/index.html`
- Modify: `src/ai_web_explorer/safesym_bridge/dom_observer.py`
- Modify: `src/ai_web_explorer/safesym_bridge/web_action_extractor.py`
- Modify/Create tests as needed:
  - `tests/safesym_bridge/test_dom_observer.py`
  - `tests/safesym_bridge/test_web_action_extractor.py`
  - `tests/safesym_bridge/test_simple_grounded_web_agent_browser.py`

**Interfaces:**
- Produces:
  - select candidates include first non-empty option value in metadata;
  - fill actions include `{locator: "test"}`;
  - select actions include `{locator: first_option_value}`.

Steps:

1. Add failing unit tests for select option extraction/action values.
2. Add `local_form` fixture with:
   - input `#name`;
   - select `#topic` with a non-empty option;
   - submit button;
   - `[data-state]` indicators for name/topic/submitted.
3. Implement minimal DOM/action extraction support.
4. Add browser smoke running `SimpleGroundedWebAgent(max_steps=3)` on `local_form`.
5. Assert observed deltas include `name_value`, `topic_value`, and `submitted`.
6. Commit fixture, tests, and minimal implementation.

---

### Task 3: Regression

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\safesym_bridge tests\test_local_shop_fixture.py tests\test_cli_start_url.py tests\test_cookie_prefilter.py tests\test_html_helpers.py tests\test_cli_collector_output.py tests\test_loop_task_guidance.py -q
```

If Chromium launch fails with `spawn EPERM`, rerun with elevated permissions.

Expected:

```text
passed
```

