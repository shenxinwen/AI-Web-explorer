# Project Mainline Cleanup Implementation Plan

> **For agentic workers:** Single-agent inline execution only for this project turn. Do not dispatch subagents unless the user explicitly allows it.

**Goal:** Reduce accumulated duplicate and obsolete structures while keeping the new Web-KOBE grounded exploration path as the primary project direction.

**Architecture:** Keep the active path centered on `AutomationBackend -> WebKobePlaywrightAdapter -> WebKobeExplorer -> WebKobeGraph`. Retain the original `ExploreLoop` and SauceDemo Graph/PDDL path as compatibility/regression layers, not as the generic mainline. Remove clearly unused experimental entry points and factor shared Web-KOBE state/delta helpers.

**Tech Stack:** Python, Playwright, pytest, existing `ai_web_explorer.safesym_bridge` modules.

## Global Constraints

- Do not use subagents.
- Do not delete compatibility code that still has tests or CLI coverage.
- Prefer behavior-preserving refactors.
- Run targeted tests after each cleanup group.

---

### Task 1: Clarify the module status map

**Files:**
- Modify: `docs/current-project-overview.md`
- Modify: `docs/safesym-bridge.md`

**Deliverable:** Documentation says Web-KOBE grounded exploration is the current mainline, while original explorer collector mode and SauceDemo Graph/PDDL are compatibility/regression routes.

### Task 2: Remove the obsolete fine-tuning CLI entry

**Files:**
- Modify: `pyproject.toml`
- Delete: `src/ai_web_explorer/ft.py`

**Deliverable:** The old `ft` console script and its script file are removed because they are not referenced by the new exploration/SafeSym pipeline.

### Task 3: Factor shared Web-KOBE state/delta helpers

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/state_signature.py`
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_observer.py`
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_playwright_adapter.py`
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_collector.py`
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_explorer.py`
- Test: `tests/safesym_bridge/test_state_signature.py`

**Deliverable:** Slugging, indicator coercion, and schema delta calculation live in one small module.

### Task 4: Add the grounded web mainline package boundary

**Files:**
- Create: `src/ai_web_explorer/grounded_web/__init__.py`
- Create: `src/ai_web_explorer/grounded_web/automation_backend.py`
- Create: `src/ai_web_explorer/grounded_web/playwright_backend.py`
- Create: `src/ai_web_explorer/grounded_web/dom_observer.py`
- Create: `src/ai_web_explorer/grounded_web/action_extractor.py`
- Create: `src/ai_web_explorer/grounded_web/state_signature.py`
- Create: `src/ai_web_explorer/grounded_web/explorer.py`
- Create: `src/ai_web_explorer/grounded_web/controller.py`
- Create: `src/ai_web_explorer/grounded_web/graph.py`
- Create: `src/ai_web_explorer/grounded_web/graph_manager.py`
- Create: `src/ai_web_explorer/grounded_web/semantic_assistor.py`
- Create: `src/ai_web_explorer/grounded_web/simple_agent.py`
- Test: `tests/test_grounded_web_public_api.py`

**Deliverable:** New code can import the active grounded exploration API from `ai_web_explorer.grounded_web` without depending directly on the SafeSym bridge package. Existing `safesym_bridge` imports remain compatible during migration.

### Task 5: Verify

**Commands:**

```bash
python -m pytest tests/test_grounded_web_public_api.py tests/safesym_bridge/test_state_signature.py tests/safesym_bridge/test_web_kobe_observer.py tests/safesym_bridge/test_web_kobe_graph_manager.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_web_kobe_playwright_adapter.py tests/safesym_bridge/test_simple_grounded_web_agent.py -q
```

```bash
python -m pytest tests/test_cli_start_url.py tests/test_cli_collector_output.py tests/test_loop_task_guidance.py tests/test_cookie_prefilter.py tests/test_html_helpers.py -q
```
