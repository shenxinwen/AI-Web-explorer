# Compact Graph and Evidence Sidecar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write a compact, Phase-A-compatible `graph.json` and move verbose diagnostic content into a sibling `graph_evidence.json` without changing graph semantics or state names.

**Architecture:** Add a pure artifact-splitting module that converts the existing in-memory `WebKobeGraph` into two JSON dictionaries. Keep the current graph dataclasses and exploration flow unchanged, teach the existing writer to emit both artifacts, and rely on the current tolerant loader to read compact graphs without hydrating evidence.

**Tech Stack:** Python 3.11, dataclasses, JSON, pathlib, pytest.

## Global Constraints

- Do not change node matching, action selection, stopping, state naming, Phase A consolidation, or PDDL semantics.
- Do not add persisted fields to `WebKobeNode`, `WebKobeEdge`, or `WebKobeGraph`.
- `graph.json` must remain loadable without `graph_evidence.json`.
- Historical full graph JSON must remain loadable without migration.
- Phase A and PDDL must never read or require the evidence sidecar.
- Concrete object-level visual facts may exist only in sidecar evidence, never compact state, PlanningState, or Phase A PDDL.
- Keep the first implementation simple: one `graph_evidence.json`, not one file per edge.

---

### Task 1: Build pure compact/evidence artifact dictionaries

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/graph_artifacts.py`
- Create: `tests/safesym_bridge/test_graph_artifacts.py`

**Interfaces:**
- Consumes: `WebKobeGraph`
- Produces: `GraphArtifactPayload(compact_graph: dict[str, Any], evidence_sidecar: dict[str, Any])`
- Produces: `build_graph_artifact_payload(graph: WebKobeGraph) -> GraphArtifactPayload`

- [ ] **Step 1: Write a representative failing test fixture**

Create a two-node, one-edge graph containing repeated URL evidence, a verbose
`observed_delta`, Stagehand metadata, visual-delta object facts, duplicated
instruction/description, empty planning structures, and one business
affordance. The fixture must use real graph dataclasses.

```python
def test_build_graph_artifact_payload_moves_verbose_evidence_out_of_graph():
    graph = _verbose_graph_fixture()

    payload = build_graph_artifact_payload(graph)

    edge = payload.compact_graph["edges"][0]
    assert edge["source_node_id"] == "product_list"
    assert edge["action"]["semantic_id"] == "search_items"
    assert edge["target_node_id"] == "search_results"
    assert edge["status"] == "succeeded_with_observed_change"
    assert edge["execution_trace"]["success"] is True
    assert "observed_delta" not in edge
    assert "metadata" not in edge["execution_trace"]
    assert "instruction" not in edge
    assert "description" not in edge["action"]
    assert edge["evidence_ref"] == "edge-evidence:product_list__search_items__search_results"

    evidence = payload.evidence_sidecar["edges"][edge["evidence_ref"]]
    assert evidence["observed_delta"]
    assert evidence["execution_trace"]["metadata"]["visual_delta_trace"]
```

- [ ] **Step 2: Run the new test and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_graph_artifacts.py
```

Expected: collection fails because `graph_artifacts` does not exist.

- [ ] **Step 3: Implement the payload type and compact node/edge helpers**

Create:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai_web_explorer.grounded_web.graph import WebKobeGraph

GRAPH_EVIDENCE_SCHEMA_VERSION = "web-kobe-graph-evidence-v1"


@dataclass(frozen=True)
class GraphArtifactPayload:
    compact_graph: dict[str, Any]
    evidence_sidecar: dict[str, Any]


def build_graph_artifact_payload(graph: WebKobeGraph) -> GraphArtifactPayload:
    ...
```

Implementation rules:

- Start from each dataclass's existing `to_dict()` output; do not duplicate
  domain conversion logic.
- Compact nodes retain `node_id`, one short description, minimal `page_frame`
  (`page_id`, `page_type`, `url`, `url_pattern`, `title`, `heading`,
  `signature_hints`), `state_schema`, `last_state_snapshot`, frozen
  `business_affordances`, status/visit count, labels/naming, and non-empty
  planning state.
- Compact edges retain source, target, compact action, final status/visit
  count, a minimal execution trace (`concrete_action_kind`,
  `before_observation_id`, `after_observation_id`, `success`, and non-empty
  `error`), and non-empty planner-facing transition data.
- `semantic_id` always remains because the historical loader requires it.
  Omit `canonical_action_name` only when it equals `semantic_id`.
- Preserve action label, local `supporting_facts`, and non-empty input values.
  Target hints remain on the source node's frozen business affordances; do not
  parse them back out of the verbose action description.
- Move node/page evidence and removed node fields into
  `nodes["node-evidence:<node_id>"]`.
- Move instruction, action description/provenance duplicates, target
  observation, observed/schema delta, full execution trace, PDDL hint, and
  edge evidence into `edges["edge-evidence:<edge_id>"]`.
- Add `evidence_ref` to a compact item only when its sidecar payload is
  non-empty.
- Remove null, empty list, and empty dictionary values recursively only from
  optional compact fields; never remove required loader keys listed above.
- Preserve graph meta and add no planner semantics to it.

- [ ] **Step 4: Add coverage for compactness and evidence references**

```python
def test_compact_payload_omits_empty_values_and_resolves_every_reference():
    payload = build_graph_artifact_payload(_verbose_graph_fixture())
    encoded_full = json.dumps(_verbose_graph_fixture().to_dict())
    encoded_compact = json.dumps(payload.compact_graph)

    assert len(encoded_compact) < len(encoded_full)
    assert _find_null_or_empty_optional_values(payload.compact_graph) == []
    for node in payload.compact_graph["nodes"]:
        if "evidence_ref" in node:
            assert node["evidence_ref"] in payload.evidence_sidecar["nodes"]
    for edge in payload.compact_graph["edges"]:
        if "evidence_ref" in edge:
            assert edge["evidence_ref"] in payload.evidence_sidecar["edges"]
```

Also assert that a concrete visual fact such as
`wireless_mouse_is_first_in_list` is absent from serialized compact JSON and
present in serialized sidecar JSON.

- [ ] **Step 5: Run Task 1 tests**

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_graph_artifacts.py
```

Expected: all Task 1 tests pass.

- [ ] **Step 6: Commit Task 1**

```powershell
git add src/ai_web_explorer/safesym_bridge/graph_artifacts.py tests/safesym_bridge/test_graph_artifacts.py
git commit -m "Add compact graph artifact payload"
```

---

### Task 2: Make the experiment writer emit graph and sidecar together

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py:139-149`
- Modify: `tests/safesym_bridge/test_browser_runner.py:50-145`
- Modify: `tests/safesym_bridge/test_browser_runner.py:733-839`

**Interfaces:**
- Consumes: `build_graph_artifact_payload(graph)` from Task 1
- Keeps: `write_web_kobe_graph(graph: WebKobeGraph, output_path: Path) -> Path`
- Adds optional keyword: `evidence_path: Path | None = None`
- Default evidence path: `output_path.with_name("graph_evidence.json")`

- [ ] **Step 1: Write failing writer assertions**

Update the existing frontier-metrics writer test:

```python
browser_runner.write_web_kobe_graph(graph, output_path)

evidence_path = output_path.with_name("graph_evidence.json")
assert output_path.exists()
assert evidence_path.exists()
data = json.loads(output_path.read_text(encoding="utf-8"))
evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
assert data["meta"]["frontier_metrics"]["frontier_node_count"] == 2
assert evidence["schema_version"] == "web-kobe-graph-evidence-v1"
```

In the Stagehand runner test, assert the sibling sidecar exists after
`run_stagehand_exploration` returns.

- [ ] **Step 2: Run focused tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_browser_runner.py::test_write_web_kobe_graph_adds_frontier_metrics tests/safesym_bridge/test_browser_runner.py::test_run_stagehand_exploration_wires_generic_stagehand_backend
```

Expected: FAIL because no sidecar is written.

- [ ] **Step 3: Implement the writer integration**

Change the function signature to:

```python
def write_web_kobe_graph(
    graph: WebKobeGraph,
    output_path: Path,
    *,
    evidence_path: Path | None = None,
) -> Path:
```

Build the payload, add existing frontier metrics to the compact graph meta,
and write the sidecar before the graph. When `evidence_path` is `None`, use
`output_path.with_name("graph_evidence.json")`.

Writing order is required:

1. create both parent directories;
2. write sidecar JSON;
3. write compact graph JSON that references it.

If sidecar writing fails, the new compact graph must not be written.

- [ ] **Step 4: Verify writer and Stagehand tests**

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_cli.py
```

Expected: all tests pass and existing CLI call signatures remain compatible.

- [ ] **Step 5: Commit Task 2**

```powershell
git add src/ai_web_explorer/safesym_bridge/browser_runner.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_cli.py
git commit -m "Write compact graph with evidence sidecar"
```

---

### Task 3: Prove compact graphs load and project without evidence hydration

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py:550-575`
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py:139-181`
- Modify: `tests/safesym_bridge/test_web_kobe_pddl_projector.py`
- Modify: `tests/safesym_bridge/test_behavior_state_graph_cli.py`

**Interfaces:**
- Consumes compact `action` dictionaries where `canonical_action_name` may be
  omitted when equal to `semantic_id`.
- Consumes compact graph dictionaries containing unknown `evidence_ref` keys;
  those keys are diagnostic and ignored by the graph dataclasses.
- Keeps `load_web_kobe_graph_json(path: Path) -> WebKobeGraph` unchanged.

- [ ] **Step 1: Write a compact-loader regression test**

Use `build_graph_artifact_payload(_graph_fixture()).compact_graph`, write only
that dictionary to a temporary `graph.json`, and do not write a sidecar.

```python
loaded = load_web_kobe_graph_json(graph_path)

assert loaded.start_node_id == "listing"
assert loaded.edges[0].action.semantic_id == "view_details"
assert loaded.edges[0].action.canonical_action_name == "view_details"
assert loaded.edges[0].execution_trace.success is True
```

The canonical action assertion requires the loader to fall back to
`semantic_id` when the compact writer omits an equal canonical name.

- [ ] **Step 2: Run the loader test and verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_web_kobe_pddl_projector.py -k compact
```

Expected: FAIL because `canonical_action_name` currently becomes `None`.

- [ ] **Step 3: Add the minimal loader fallback**

In `_action_from_dict`:

```python
semantic_id = str(data["semantic_id"])
canonical_action_name = data.get("canonical_action_name") or semantic_id
```

Pass both values into `BrowserAction`. Do not load or inspect the sidecar.

- [ ] **Step 4: Add Phase A semantic-equivalence coverage**

In the Phase A CLI test:

1. build one full graph fixture;
2. project the full graph in memory;
3. write its compact dictionary without the sidecar;
4. run `web-kobe-phase-a` on the compact file;
5. compare canonical node IDs, canonical edge triples, and domain action lines.

Change the Phase A CLI's `raw_graph.json` write so it preserves the parsed input
JSON dictionary instead of reserializing `artifacts.raw_graph.to_dict()`. This
keeps compact input compact and keeps historical full input full. Add a small
JSON-object reader helper shared with `load_web_kobe_graph_json` if needed; do
not read a sidecar. The Phase A output must not create or require
`graph_evidence.json`.

- [ ] **Step 5: Verify loader and Phase A suites**

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_web_kobe_pddl_projector.py tests/safesym_bridge/test_behavior_state_graph.py tests/safesym_bridge/test_behavior_state_graph_cli.py
```

Expected: all tests pass with no network calls.

- [ ] **Step 6: Commit Task 3**

```powershell
git add src/ai_web_explorer/safesym_bridge/cli.py src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py tests/safesym_bridge/test_web_kobe_pddl_projector.py tests/safesym_bridge/test_behavior_state_graph_cli.py
git commit -m "Load compact graphs for Phase A"
```

---

### Task 4: Document artifacts and verify the complete change

**Files:**
- Modify: `docs/current-project-overview.zh-CN.md`
- Modify: `docs/project-structure.zh-CN.md`
- Modify: `docs/safesym-bridge.md`

**Interfaces:**
- Documents `graph.json` as the compact primary graph.
- Documents `graph_evidence.json` as optional diagnostic evidence.
- States explicitly that Phase A does not hydrate or require the sidecar.

- [ ] **Step 1: Update the three current-facing documents**

Document:

- which fields remain in the compact graph;
- which evidence moves to the sidecar;
- how `evidence_ref` resolves;
- that old full graph files remain loadable;
- that state naming is unchanged and remains the next separate topic.

Do not claim candidate-generation failure/empty distinction is solved.

- [ ] **Step 2: Run focused and full verification**

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/safesym_bridge/test_graph_artifacts.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_web_kobe_pddl_projector.py tests/safesym_bridge/test_behavior_state_graph.py tests/safesym_bridge/test_behavior_state_graph_cli.py tests/safesym_bridge/test_cli.py
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
git diff --check
```

Expected: all tests pass, except environment-only Playwright launch restrictions
must be rerun with the already approved browser permission before being called
an environment failure.

- [ ] **Step 3: Run artifact acceptance against the latest experiment**

Use the latest five-edge experiment as read-only input. Write compact acceptance
artifacts to a new review directory; do not overwrite the experiment's current
`graph.json`.

Verify and report:

- full and compact byte sizes;
- every compact `evidence_ref` resolves;
- four nodes and five edges remain;
- Phase A still produces four canonical nodes, five canonical edges, and five
  domain actions;
- `wireless_mouse_is_first_in_list` is absent from compact graph and present in
  sidecar;
- the generated domain text matches the pre-change Phase A domain text.

- [ ] **Step 4: Commit documentation**

```powershell
git add docs/current-project-overview.zh-CN.md docs/project-structure.zh-CN.md docs/safesym-bridge.md
git commit -m "Document compact graph evidence artifacts"
```

- [ ] **Step 5: Final handoff report**

Report commits, changed files, focused/full test counts, compact/full byte
sizes, acceptance topology counts, domain equivalence, and `git status`.
