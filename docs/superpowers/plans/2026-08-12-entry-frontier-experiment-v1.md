# Entry Frontier Experiment V1.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans, superpowers:test-driven-development, and superpowers:verification-before-completion. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow reset-only exploration of untried actions on the entry surface and prepare a bounded real experiment using five candidates.

**Architecture:** Reuse the existing frontier selector, replay runner, controller blocked set, and graph metrics. Entry replay is an empty replay path after reset and entry validation; the following normal exploration step remains the only operation allowed to add an edge.

**Tech Stack:** Python 3.11+, asyncio, pytest, Playwright, Stagehand, existing Web-KOBE graph and Surface PDDL pipeline.

## Global Constraints

- No candidate refresh, coverage optimizer, business facts, or website-specific rules.
- Preserve the pure selector's compatibility unless controller opt-in requires an explicit `include_start=True` argument.
- No fixed loop counter; use the existing progress and blocked-frontier rules.
- Keep replay fail-closed and atomic.

---

### Task 1: Select the entry surface as an explicit frontier

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/controller.py`
- Possibly modify: `src/ai_web_explorer/grounded_web/frontier_replay.py`
- Test: `tests/safesym_bridge/test_frontier_replay.py`
- Test: `tests/safesym_bridge/test_web_kobe_controller.py`

- [ ] Add a failing test whose start node has two candidates and one tried outgoing action; controller-enabled selection must return the start node with an empty path and the remaining action.
- [ ] Run the focused test and confirm it fails because the start node is excluded.
- [ ] Make the minimal controller/selector change so frontier replay explicitly includes start without changing unrelated callers.
- [ ] Add a controller test proving reset-only replay resumes normal exploration and records progress only through `explore_one_step`.
- [ ] Add a no-progress regression proving entry replay is attempted once, the start node is blocked, and the run terminates.
- [ ] Run frontier and controller tests.
- [ ] Commit the change.

### Task 2: Align the deterministic browser experiment

**Files:**
- Modify: `tests/safesym_bridge/test_web_kobe_playwright_integration.py`
- Modify: `docs/experiments/frontier-replay-surface-pddl-v1.md`
- Test: `tests/safesym_bridge/test_cli.py`

- [ ] Keep at least three generic entry candidates in the fixture and assert the successful replay target is the entry surface.
- [ ] Assert candidate limit plumbing accepts 5 and the experiment CLI includes `--frontier-replay`, screenshots, Visual Delta, and `observed_action` mode.
- [ ] When Playwright is available, run the fixture and assert replay success, sibling entry actions, a deeper node, Surface PDDL without checkpoints, and SafeSym readiness.
- [ ] If Chromium still fails with `spawn EPERM`, report it as an environment limitation without weakening the test.
- [ ] Update the experiment note with exact configuration and required metrics; do not claim a real run unless it occurred.
- [ ] Commit the change.

### Task 3: Verify the bounded pipeline

**Files:**
- No production files expected beyond Tasks 1-2.

- [ ] Run replay, controller, browser-runner, CLI, Surface PDDL, Trace PDDL, and SafeSym focused tests.
- [ ] Run the complete non-browser pytest suite.
- [ ] Run `git diff --check`.
- [ ] Confirm no production shopping/cart/filter/sort/checkout branching was introduced.
- [ ] Report commits, exact test counts, browser status, and whether the worktree is clean and detached.
