# Web-KOBE Exploration Controller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small Web-KOBE exploration controller that owns multi-step exploration flow and stop reasons.

**Architecture:** Keep `WebKobeExplorer.explore_one_step()` as the single-step graph mutation primitive. Add `WebKobeExplorationController` as the process-level loop that runs steps, detects stop reasons, and returns a summary. Update the Playwright runner to call the controller instead of owning the loop.

**Tech Stack:** Python 3.11, pytest, existing Web-KOBE graph/explorer/runner modules.

## Global Constraints

- Do not add LLM/VLM calls in this slice.
- Do not replace the existing SauceDemo observed graph/PDDL path.
- Keep the controller deterministic and small.
- Use `.\.venv\Scripts\python.exe -m pytest` in this workspace.
- Do not use subagents unless explicitly allowed by the user.

---

### Task 1: Controller

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/web_kobe_controller.py`
- Create: `tests/safesym_bridge/test_web_kobe_controller.py`

**Interfaces:**
- Consumes: `WebKobeExplorer.explore_one_step()`
- Produces:
  - `WebKobeExplorationSummary`
  - `WebKobeExplorationResult`
  - `WebKobeExplorationController.run(max_steps: int = 1) -> WebKobeExplorationResult`

- [ ] Write failing tests for `max_steps`, `no_available_action`, and failed-action stop summary.
- [ ] Run focused tests and confirm missing module failure.
- [ ] Implement the controller and summary/result dataclasses.
- [ ] Run focused tests and confirm pass.
- [ ] Commit.

### Task 2: Runner Integration

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Modify: `tests/safesym_bridge/test_browser_runner.py`

**Interfaces:**
- Consumes: `WebKobeExplorationController`
- Produces: `run_web_kobe_exploration(...)` using the controller.

- [ ] Write a test proving the runner can call a monkeypatched controller.
- [ ] Run focused test and confirm failure.
- [ ] Update the runner to instantiate and call the controller.
- [ ] Run focused tests and confirm pass.
- [ ] Commit.

### Task 3: Documentation and Verification

**Files:**
- Modify: `docs/current-project-overview.md`
- Modify: `docs/safesym-bridge.md`

- [ ] Document that `web-kobe-explore` now uses the controller loop.
- [ ] Run focused Web-KOBE tests.
- [ ] Run `tests/safesym_bridge`.
- [ ] Commit docs if changed.
