# Complete Node Embedding Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure every graph node encountered in an embedding-enabled exploration has one state embedding record, including the initial source node.

**Architecture:** Generalize the existing target-only embedding writer into a node embedding writer, then add an idempotent source-side ensure step after source resolution and before action selection. Preserve all matching thresholds, acceptance rules, graph schemas, and PDDL behavior.

**Tech Stack:** Python 3.11+, dataclasses, pytest, existing WebKobeExplorer/state embedding provider.

## Global Constraints

- Every graph node encountered as a current source must have one embedding record when exploration memory is enabled.
- Existing node records are reused; source revisits must not call the embedding API again.
- Target embedding recording remains active after actions.
- Do not adjust matching thresholds, source protection, or revisit acceptance.
- Do not add graph, node, edge, memory-file, or PDDL fields.
- Do not automatically refresh an existing node embedding when its observation changes.

---

### Task 1: Reproduce the Missing Initial Embedding

**Files:**
- Test: `tests/safesym_bridge/test_web_kobe_explorer.py`

**Interfaces:**
- Observes: `WebKobeExplorer.state_embedding_records`.
- Proves: the initial graph source is indexed before the first action finishes.

- [ ] **Step 1: Add a failing initial-source test**

Create an embedding-enabled explorer with a recording fake provider. Run one exploration step and assert the start node appears in `state_embedding_records` in addition to the target node.

```python
record_ids = {record.node_id for record in explorer.state_embedding_records}
assert graph.start_node_id in record_ids
assert {node.node_id for node in graph.nodes} <= record_ids
```

The fake provider should append each summary text to `calls`, allowing later assertions about duplicate API calls.

- [ ] **Step 2: Verify the test fails for the right reason**

Run the exact new test:

```powershell
pytest tests/safesym_bridge/test_web_kobe_explorer.py::test_explore_one_step_records_initial_source_embedding -q
```

Expected: FAIL because only the action target is currently recorded.

### Task 2: Add an Idempotent Source Embedding Ensure Step

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Test: `tests/safesym_bridge/test_web_kobe_explorer.py`

**Interfaces:**
- Produces: `_record_state_embedding(...)` as the generalized replacement for `_record_target_embedding(...)`.
- Produces: `_ensure_source_embedding(...)` or an equivalently focused private helper.
- Consumes: resolved `source_id`, current `StateSnapshot`, current interactables, and the source node's active planning facts.

- [ ] **Step 1: Generalize the target embedding writer without changing behavior**

Rename `_record_target_embedding` to `_record_state_embedding` and rename its `target_id` parameter to `node_id`. Keep its existing summary generation, embedding call, record replacement, and append behavior unchanged. Update the action-after call site to pass the target node ID.

- [ ] **Step 2: Add an idempotent source helper**

The helper must return immediately when memory/provider is disabled or a record with the same `node_id` already exists.

```python
if (
    not self.enable_exploration_memory
    or self.state_embedding_provider is None
    or any(record.node_id == node_id for record in self.state_embedding_records)
):
    return
```

Otherwise call `_record_state_embedding` with the current source snapshot, interactables, and locally stored active planning facts.

- [ ] **Step 3: Wire the helper at the correct point**

In `explore_one_step`, call it after current-source resolution and `_refresh_matched_source_node`, but before screenshot candidate generation and action selection. This preserves the existing source-matching decision while ensuring the resolved source is indexed before any new transition.

Do not index the draft node before source resolution; that could create an embedding record for a transient ID that is immediately remapped to a known node.

- [ ] **Step 4: Run the new test**

Run:

```powershell
pytest tests/safesym_bridge/test_web_kobe_explorer.py::test_explore_one_step_records_initial_source_embedding -q
```

Expected: PASS.

- [ ] **Step 5: Add and run the no-repeat revisit test**

Add a focused test that calls the source ensure path twice for the same node, or performs two observations of the same current node, and asserts the embedding provider was called once for that source ID. Target calls must be separated in the assertion rather than hidden by a total-call count.

Also add a disabled-memory test asserting no source embedding call occurs when `enable_exploration_memory=False`.

Run the three focused tests and expect all PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/explorer.py tests/safesym_bridge/test_web_kobe_explorer.py
git commit -m "Ensure every graph source has an embedding"
```

### Task 3: Verify the Graph-to-Embedding Invariant

**Files:**
- Modify only if needed: `tests/safesym_bridge/test_browser_runner.py`
- Test: `tests/safesym_bridge/test_web_kobe_explorer.py`

**Interfaces:**
- Verifies: `{node.node_id for node in graph.nodes}` is a subset of `{record.node_id for record in explorer.state_embedding_records}` on the normal embedding-enabled path.
- Does not add a persisted validation field.

- [ ] **Step 1: Add a multi-step invariant assertion**

Extend an existing multi-step embedding explorer test or add one focused test with at least an initial node and one new target. After exploration:

```python
graph_node_ids = {node.node_id for node in graph.nodes}
embedding_node_ids = {
    record.node_id for record in explorer.state_embedding_records
}
assert graph_node_ids <= embedding_node_ids
```

- [ ] **Step 2: Run the explorer regression suite**

Run:

```powershell
pytest tests/safesym_bridge/test_web_kobe_explorer.py -q
```

Expected: all pass. If existing tests assert exact embedding call counts, update only those whose count legitimately gains the initial-source call; do not weaken matching assertions.

- [ ] **Step 3: Run all SafeSym bridge tests**

Run:

```powershell
pytest tests/safesym_bridge -q
```

Expected: all pass with only previously documented skips.

- [ ] **Step 4: Search for accidental scope expansion**

Run:

```powershell
git diff --check
git diff --stat
git diff -- src/ai_web_explorer/grounded_web/explorer.py tests/safesym_bridge/test_web_kobe_explorer.py
```

Expected: no threshold, matching acceptance, graph schema, runner output schema, or PDDL changes.

- [ ] **Step 5: Run the full test suite**

Run: `pytest -q`

Expected: all code tests pass; if the local Playwright fixture hits the known sandbox `spawn EPERM`, rerun only that fixture with browser permission and report both results precisely.

- [ ] **Step 6: Hand off for review**

Report branch/HEAD, commit list, exact test counts, files changed, and confirmation that no persistent fields or matching thresholds changed. Do not merge and do not run a real external experiment; the review session will merge and repeat the saved website scenario.
