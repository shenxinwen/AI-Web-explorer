# Compact Graph Action Dependencies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve `required_action_ids` through compact graph serialization, reload, and semantic PDDL projection.

**Architecture:** Extend the existing `_compact_edge()` whitelist with the already-supported edge dependency field. Prove the complete artifact boundary with focused serialization and round-trip projection tests; do not alter core graph or scheduling structures.

**Tech Stack:** Python, dataclasses, pytest, existing WebKobe graph artifact and semantic planning modules

**Spec:** `docs/superpowers/specs/2026-08-21-compact-graph-action-dependencies-design.md`

## Global Constraints

- Only compact graph artifact serialization may change.
- Do not remove existing compact fields.
- Do not change execution, scheduling, VLM prompts, Stagehand, or SafeSym.
- Old compact artifacts without `required_action_ids` must remain loadable.
- Empty `required_action_ids` lists remain omitted.

---

### Task 1: Preserve edge dependencies in compact artifacts

**Files:**
- Modify: `tests/safesym_bridge/test_graph_artifacts.py`
- Modify: `src/ai_web_explorer/safesym_bridge/graph_artifacts.py`

**Interfaces:**
- Consumes: `WebKobeEdge.required_action_ids: list[str]` and `build_graph_artifact_payload(graph: WebKobeGraph) -> GraphArtifactPayload`
- Produces: compact edge dictionaries with optional `required_action_ids: list[str]`

- [ ] **Step 1: Write failing compact-edge and execution-event tests**

Update the fixture edge with `required_action_ids=["enter_username", "enter_password"]`, include it in `execution_events`, and assert both serialized locations preserve the list:

```python
assert payload.compact_graph["edges"][0]["required_action_ids"] == [
    "enter_username",
    "enter_password",
]
assert payload.compact_graph["execution_events"][0]["required_action_ids"] == [
    "enter_username",
    "enter_password",
]
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `python -m pytest tests/safesym_bridge/test_graph_artifacts.py -q`

Expected: the new assertions fail because `_compact_edge()` currently drops `required_action_ids`.

- [ ] **Step 3: Implement the minimal serializer change**

Add `"required_action_ids"` to the field tuple copied by `_compact_edge()`:

```python
for key in (
    "edge_id",
    "source_node_id",
    "target_node_id",
    "status",
    "visit_count",
    "visual_change_kind",
    "required_action_ids",
):
```

The existing empty-value compactor keeps the field optional.

- [ ] **Step 4: Run graph artifact tests**

Run: `python -m pytest tests/safesym_bridge/test_graph_artifacts.py -q`

Expected: PASS.

### Task 2: Verify compact round-trip reaches semantic PDDL

**Files:**
- Modify: `tests/safesym_bridge/test_graph_artifacts.py`

**Interfaces:**
- Consumes: `load_web_kobe_graph_json(path)` and the existing semantic planning/PDDL projection entry points used by current tests
- Produces: a regression test proving a reloaded dependent action has prerequisite completion predicates in generated PDDL

- [ ] **Step 1: Write the round-trip projection regression test**

Construct successful `enter_username`, `enter_password`, and `submit_login` edges, with `submit_login.required_action_ids` containing the first two IDs. Serialize the graph with `build_graph_artifact_payload()`, write only `compact_graph`, reload it, project it through the existing semantic planning path, and assert the `submit_login` PDDL action includes both completion predicates as preconditions.

- [ ] **Step 2: Run the regression test and verify its result**

Run: `python -m pytest tests/safesym_bridge/test_graph_artifacts.py -q`

Expected before Task 1 implementation: FAIL because the reloaded submit edge has no dependencies. Expected after Task 1: PASS.

- [ ] **Step 3: Run the directly affected suites**

Run: `python -m pytest tests/safesym_bridge/test_graph_artifacts.py tests/safesym_bridge/test_semantic_planning.py tests/safesym_bridge/test_web_kobe_pddl_projector.py -q`

Expected: PASS.

- [ ] **Step 4: Run the non-browser regression suite**

Run: `python -m pytest tests/safesym_bridge -q --ignore=tests/safesym_bridge/test_web_kobe_playwright_integration.py`

Expected: PASS with only previously documented skips.

- [ ] **Step 5: Review the diff**

Run: `git diff --check` and `git diff -- src/ai_web_explorer/safesym_bridge/graph_artifacts.py tests/safesym_bridge/test_graph_artifacts.py docs/superpowers/specs/2026-08-21-compact-graph-action-dependencies-design.md docs/superpowers/plans/2026-08-21-compact-graph-action-dependencies.md`

Expected: no whitespace errors and no changes outside the agreed artifact serializer, tests, spec, and plan.
