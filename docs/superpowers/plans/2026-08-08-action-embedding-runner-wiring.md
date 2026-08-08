# Action Embedding Runner Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the real Stagehand exploration runner use its resolved embedding provider for local action-semantic deduplication as well as state matching.

**Architecture:** Keep provider creation in `run_stagehand_exploration`. Pass the same resolved callable through the explorer's separate `state_embedding_provider` and `action_embedding_provider` constructor parameters; no new configuration or persistence is introduced.

**Tech Stack:** Python 3.11, pytest, AnyIO, OpenAI-compatible embeddings.

## Global Constraints

- Do not add embedding environment variables or graph fields.
- Keep `EMBEDDING_DIMENSION=1024` for the first real experiment.
- When embeddings are disabled, exact-name action deduplication remains the fallback.
- Do not change matching thresholds, PDDL, or visual-provider retry behavior.

---

### Task 1: Wire the resolved provider into action deduplication

**Files:**
- Modify: `tests/safesym_bridge/test_browser_runner.py:767-785`
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py:535-546`

**Interfaces:**
- Consumes: `resolved_embedding_provider: EmbeddingProvider | None`
- Produces: `WebKobeExplorer(..., action_embedding_provider=resolved_embedding_provider)`

- [ ] **Step 1: Write the failing regression assertion**

Add this assertion to `FakeController.__init__` in
`test_run_stagehand_exploration_wires_generic_stagehand_backend`:

```python
assert explorer.action_embedding_provider("x") == [1.0, 0.0]
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_browser_runner.py::test_run_stagehand_exploration_wires_generic_stagehand_backend
```

Expected: FAIL because `action_embedding_provider` is `None` and is not callable.

- [ ] **Step 3: Make the minimal production change**

In the existing `WebKobeExplorer` constructor call, add:

```python
action_embedding_provider=resolved_embedding_provider,
```

Keep `state_embedding_provider=resolved_embedding_provider` unchanged.

- [ ] **Step 4: Verify GREEN and focused regressions**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_browser_runner.py::test_run_stagehand_exploration_wires_generic_stagehand_backend
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_exploration_index.py tests/safesym_bridge/test_web_kobe_explorer.py
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add tests/safesym_bridge/test_browser_runner.py src/ai_web_explorer/safesym_bridge/browser_runner.py docs/superpowers/plans/2026-08-08-action-embedding-runner-wiring.md
git commit -m "Wire action embeddings into browser runner"
```
