# Web-KOBE PDDL Planning Smoke v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not use subagents unless the project owner explicitly allows them.

**Goal:** Add a small planning-readiness smoke command that checks whether an explored `WebKobeGraph` can produce non-empty, connected, planner-facing PDDL artifacts.

**Architecture:** Add a focused `web_kobe_pddl_smoke.py` module that wraps the existing Web-KOBE PDDL projector, computes projectable-edge reachability, and emits a structured report. Extend the existing CLI with `web-kobe-pddl-smoke`; do not add a planner, do not run SafeSym, and do not treat missing safety injection as failure.

**Tech Stack:** Python 3.11, dataclasses, pathlib, json, argparse, pytest, existing `WebKobeGraph` and `web_kobe_pddl_projector` APIs.

## Global Constraints

- This milestone validates planning-readiness only.
- SafeSym safety injection is not required to trigger.
- `order_place_confirm` is not required.
- Do not implement or bundle a new planner.
- Do not run Fast Downward.
- Do not run SafeSym automatically.
- Do not infer sensitive actions.
- Do not infer user goals with LLMs.
- Do not add LLM/VLM reasoning.
- Do not expand browser operation capability.
- Do not introduce numeric PDDL fluents.
- Do not solve arbitrary planning problems.
- Unit tests must not require a real browser.
- Unit tests must not require SafeSym or Fast Downward.

---

## File Structure

- Create `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py`
  - Responsibility: planning-readiness analysis and artifact/report writing for existing `WebKobeGraph` inputs.
  - It depends on the projector; it does not duplicate browser exploration or SafeSym safety logic.

- Create `tests/safesym_bridge/test_web_kobe_pddl_smoke.py`
  - Responsibility: unit-test smoke report behavior using small in-memory `WebKobeGraph` fixtures.

- Modify `src/ai_web_explorer/safesym_bridge/cli.py`
  - Responsibility: expose `web-kobe-pddl-smoke`.

- Modify `tests/safesym_bridge/test_cli.py`
  - Responsibility: verify CLI writes `domain.pddl`, `problem.pddl`, and `smoke_report.json`.

- Modify `docs/safesym-bridge.md`
  - Responsibility: document the planning smoke command and its non-safety-trigger boundary.

- Modify `docs/current-project-overview.md`
  - Responsibility: note the planning-readiness smoke as the next bridge validation step.

- Modify `docs/current-project-overview.zh-CN.md`
  - Responsibility: mirror the English overview update in Chinese.

---

## Task 1: Add planning-readiness smoke analysis

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py`
- Create: `tests/safesym_bridge/test_web_kobe_pddl_smoke.py`

**Interfaces:**
- Consumes:
  - `WebKobeGraph`
  - `compile_web_kobe_graph_to_pddl(graph, *, goal_node_id, start_node_id=None)`
  - `PROJECTABLE_EDGE_STATUSES`
- Produces:
  - `WebKobePddlSmokeReport`
  - `analyze_web_kobe_pddl_smoke(graph: WebKobeGraph, *, goal_node_id: str, start_node_id: str | None = None, domain_path: Path | None = None, problem_path: Path | None = None) -> WebKobePddlSmokeReport`
  - `goal_reachable_through_projectable_edges(graph: WebKobeGraph, *, start_node_id: str, goal_node_id: str) -> bool`

- [ ] **Step 1: Write failing tests for reachable and unreachable reports**

Create `tests/safesym_bridge/test_web_kobe_pddl_smoke.py`:

```python
from pathlib import Path

from ai_web_explorer.grounded_web.capability_graph import (
    Evidence,
    ExecutionTrace,
    ObservedDelta,
    PageFrame,
)
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    ReferenceObservation,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.safesym_bridge.web_kobe_pddl_smoke import (
    analyze_web_kobe_pddl_smoke,
    goal_reachable_through_projectable_edges,
)


def _node(node_id: str, values: dict) -> WebKobeNode:
    evidence = [Evidence(source="unit_test")]
    return WebKobeNode(
        node_id=node_id,
        page_description=f"{node_id} page",
        page_frame=PageFrame(
            page_id=f"example:{node_id}",
            page_type=node_id,
            url=f"https://example.test/{node_id}",
            url_pattern=f"https://example.test/{node_id}",
            title=node_id,
            evidence=evidence,
        ),
        state_schema={key: [value] for key, value in values.items()},
        last_state_snapshot=values,
        reference_observation=ReferenceObservation(
            url=f"https://example.test/{node_id}",
            title=node_id,
        ),
        evidence=evidence,
    )


def _edge(
    source: str,
    target: str,
    semantic_id: str,
    *,
    success: bool = True,
    status: str = "succeeded_with_observed_change",
) -> WebKobeEdge:
    return WebKobeEdge(
        source_node_id=source,
        target_node_id=target,
        instruction=semantic_id,
        action=BrowserAction("click", f"#{semantic_id}", semantic_id),
        capability=None,
        target_observation=target,
        observed_delta=[
            ObservedDelta(
                "cart_count",
                0,
                1,
                "state_indicator_change",
                evidence=[Evidence(source="unit_test")],
            )
        ],
        schema_delta={"cart_count": {"before": 0, "after": 1}},
        execution_trace=ExecutionTrace(
            "click",
            f"#{semantic_id}",
            semantic_id,
            {},
            source,
            target,
            success,
        ),
        status=status,
    )


def _graph(edges: list[WebKobeEdge]) -> WebKobeGraph:
    return WebKobeGraph(
        app="local_shop",
        start_node_id="empty",
        total_steps_completed=len(edges),
        nodes=[
            _node("empty", {"cart_count": 0}),
            _node("filled", {"cart_count": 1}),
            _node("checkout", {"cart_count": 1, "checkout_visible": True}),
        ],
        edges=edges,
    )


def test_goal_reachable_through_projectable_edges_uses_successful_edges_only():
    graph = _graph([_edge("empty", "filled", "add_to_cart")])

    assert goal_reachable_through_projectable_edges(
        graph,
        start_node_id="empty",
        goal_node_id="filled",
    )


def test_goal_reachable_through_projectable_edges_ignores_no_change_edges():
    graph = _graph(
        [
            _edge(
                "empty",
                "filled",
                "add_to_cart",
                success=True,
                status="no_observed_change",
            )
        ]
    )

    assert not goal_reachable_through_projectable_edges(
        graph,
        start_node_id="empty",
        goal_node_id="filled",
    )


def test_analyze_web_kobe_pddl_smoke_reports_planning_ready_graph():
    graph = _graph([_edge("empty", "filled", "add_to_cart")])

    report = analyze_web_kobe_pddl_smoke(
        graph,
        goal_node_id="filled",
        domain_path=Path("out/domain.pddl"),
        problem_path=Path("out/problem.pddl"),
    )

    data = report.to_dict()
    assert data["graph_loaded"] is True
    assert data["app"] == "local_shop"
    assert data["start_node"] == "empty"
    assert data["goal_node"] == "filled"
    assert data["goal_reachable_in_graph"] is True
    assert data["projectable_edge_count"] == 1
    assert data["projected_action_count"] == 1
    assert data["projected_predicate_count"] >= 3
    assert data["planning_ready"] is True
    assert data["failure_reasons"] == []
    assert data["safety_trigger_expected"] is False
    assert "planning-readiness smoke" in data["safety_trigger_reason"]


def test_analyze_web_kobe_pddl_smoke_reports_unreachable_goal():
    graph = _graph([_edge("empty", "filled", "add_to_cart")])

    report = analyze_web_kobe_pddl_smoke(graph, goal_node_id="checkout")

    data = report.to_dict()
    assert data["goal_reachable_in_graph"] is False
    assert data["planning_ready"] is False
    assert "goal is not reachable from start through projectable edges" in data[
        "failure_reasons"
    ]
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
& .\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_smoke.py -q
```

Expected: import failure because `web_kobe_pddl_smoke.py` does not exist.

- [ ] **Step 3: Implement smoke analysis module**

Create `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py`:

```python
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from ai_web_explorer.grounded_web.graph import WebKobeGraph
from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
    PROJECTABLE_EDGE_STATUSES,
    WebKobePddlArtifacts,
    compile_web_kobe_graph_to_pddl,
)

DEFAULT_SAFETY_TRIGGER_REASON = (
    "No safety-relevant action is required for generic Web-KOBE "
    "planning-readiness smoke."
)


@dataclass(frozen=True)
class WebKobePddlSmokeReport:
    graph_loaded: bool
    app: str
    start_node: str
    goal_node: str
    goal_reachable_in_graph: bool
    projectable_edge_count: int
    projected_action_count: int
    projected_predicate_count: int
    domain_path: str | None = None
    problem_path: str | None = None
    safety_trigger_expected: bool = False
    safety_trigger_reason: str = DEFAULT_SAFETY_TRIGGER_REASON
    planning_ready: bool = False
    failure_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "graph_loaded": self.graph_loaded,
            "app": self.app,
            "start_node": self.start_node,
            "goal_node": self.goal_node,
            "goal_reachable_in_graph": self.goal_reachable_in_graph,
            "projectable_edge_count": self.projectable_edge_count,
            "projected_action_count": self.projected_action_count,
            "projected_predicate_count": self.projected_predicate_count,
            "domain_path": self.domain_path,
            "problem_path": self.problem_path,
            "safety_trigger_expected": self.safety_trigger_expected,
            "safety_trigger_reason": self.safety_trigger_reason,
            "planning_ready": self.planning_ready,
            "failure_reasons": list(self.failure_reasons),
        }


def _node_ids(graph: WebKobeGraph) -> set[str]:
    return {node.node_id for node in graph.nodes}


def _require_node(graph: WebKobeGraph, node_id: str, *, role: str) -> None:
    if node_id not in _node_ids(graph):
        raise ValueError(f"Unknown {role} node: {node_id}")


def _is_projectable_edge(edge) -> bool:
    return edge.execution_trace.success and edge.status in PROJECTABLE_EDGE_STATUSES


def _projectable_edges(graph: WebKobeGraph):
    return [edge for edge in graph.edges if _is_projectable_edge(edge)]


def goal_reachable_through_projectable_edges(
    graph: WebKobeGraph,
    *,
    start_node_id: str,
    goal_node_id: str,
) -> bool:
    _require_node(graph, start_node_id, role="start")
    _require_node(graph, goal_node_id, role="goal")

    adjacency: dict[str, list[str]] = {}
    for edge in _projectable_edges(graph):
        adjacency.setdefault(edge.source_node_id, []).append(edge.target_node_id)

    queue: deque[str] = deque([start_node_id])
    visited: set[str] = set()
    while queue:
        node_id = queue.popleft()
        if node_id == goal_node_id:
            return True
        if node_id in visited:
            continue
        visited.add(node_id)
        queue.extend(target for target in adjacency.get(node_id, []) if target not in visited)
    return False


def _count_projected_actions(domain: str) -> int:
    return domain.count("(:action ")


def _count_projected_predicates(domain: str) -> int:
    in_predicates = False
    count = 0
    for line in domain.splitlines():
        stripped = line.strip()
        if stripped == "(:predicates":
            in_predicates = True
            continue
        if in_predicates and stripped == ")":
            break
        if in_predicates and stripped.startswith("("):
            count += 1
    return count


def _failure_reasons(
    *,
    goal_reachable: bool,
    projectable_edge_count: int,
    projected_action_count: int,
    projected_predicate_count: int,
    domain: str,
    problem: str,
) -> list[str]:
    reasons: list[str] = []
    if projectable_edge_count == 0:
        reasons.append("no projectable edges exist")
    if projected_action_count == 0:
        reasons.append("no PDDL actions were projected")
    if projected_predicate_count == 0:
        reasons.append("no PDDL predicates were projected")
    if "(:init" not in problem:
        reasons.append("problem is missing init section")
    if "(:goal" not in problem:
        reasons.append("problem is missing goal section")
    if not goal_reachable:
        reasons.append("goal is not reachable from start through projectable edges")
    if not domain.strip():
        reasons.append("domain PDDL is empty")
    if not problem.strip():
        reasons.append("problem PDDL is empty")
    return reasons


def analyze_web_kobe_pddl_smoke(
    graph: WebKobeGraph,
    *,
    goal_node_id: str,
    start_node_id: str | None = None,
    domain_path: Path | None = None,
    problem_path: Path | None = None,
) -> WebKobePddlSmokeReport:
    selected_start = start_node_id or graph.start_node_id
    artifacts = compile_web_kobe_graph_to_pddl(
        graph,
        start_node_id=start_node_id,
        goal_node_id=goal_node_id,
    )
    projectable_edge_count = len(_projectable_edges(graph))
    goal_reachable = goal_reachable_through_projectable_edges(
        graph,
        start_node_id=selected_start,
        goal_node_id=goal_node_id,
    )
    projected_action_count = _count_projected_actions(artifacts.domain)
    projected_predicate_count = _count_projected_predicates(artifacts.domain)
    reasons = _failure_reasons(
        goal_reachable=goal_reachable,
        projectable_edge_count=projectable_edge_count,
        projected_action_count=projected_action_count,
        projected_predicate_count=projected_predicate_count,
        domain=artifacts.domain,
        problem=artifacts.problem,
    )

    return WebKobePddlSmokeReport(
        graph_loaded=True,
        app=graph.app,
        start_node=selected_start,
        goal_node=goal_node_id,
        goal_reachable_in_graph=goal_reachable,
        projectable_edge_count=projectable_edge_count,
        projected_action_count=projected_action_count,
        projected_predicate_count=projected_predicate_count,
        domain_path=str(domain_path) if domain_path is not None else None,
        problem_path=str(problem_path) if problem_path is not None else None,
        planning_ready=not reasons,
        failure_reasons=reasons,
    )
```

- [ ] **Step 4: Run smoke analysis tests**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
& .\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_smoke.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py tests/safesym_bridge/test_web_kobe_pddl_smoke.py
git commit -m "feat: analyze web kobe pddl planning readiness"
```

---

## Task 2: Write PDDL smoke artifacts and report JSON

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py`
- Modify: `tests/safesym_bridge/test_web_kobe_pddl_smoke.py`

**Interfaces:**
- Consumes:
  - `analyze_web_kobe_pddl_smoke(...) -> WebKobePddlSmokeReport`
  - `compile_web_kobe_graph_to_pddl(...) -> WebKobePddlArtifacts`
- Produces:
  - `WebKobePddlSmokeResult`
  - `write_web_kobe_pddl_smoke(graph: WebKobeGraph, output_dir: Path, *, goal_node_id: str, start_node_id: str | None = None) -> WebKobePddlSmokeResult`

- [ ] **Step 1: Write failing artifact-writing test**

Append to `tests/safesym_bridge/test_web_kobe_pddl_smoke.py`:

```python
import json
```

Add this test:

```python
def test_write_web_kobe_pddl_smoke_writes_pddl_and_report(tmp_path):
    from ai_web_explorer.safesym_bridge.web_kobe_pddl_smoke import (
        write_web_kobe_pddl_smoke,
    )

    graph = _graph([_edge("empty", "filled", "add_to_cart")])

    result = write_web_kobe_pddl_smoke(
        graph,
        tmp_path,
        goal_node_id="filled",
    )

    domain_path = tmp_path / "domain.pddl"
    problem_path = tmp_path / "problem.pddl"
    report_path = tmp_path / "smoke_report.json"

    assert domain_path.exists()
    assert problem_path.exists()
    assert report_path.exists()
    assert "(:action add_to_cart" in domain_path.read_text(encoding="utf-8")
    assert "(:goal (and (at_filled)))" in problem_path.read_text(encoding="utf-8")
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["planning_ready"] is True
    assert data["domain_path"] == str(domain_path)
    assert data["problem_path"] == str(problem_path)
    assert result.report.planning_ready is True
    assert result.artifacts.domain == domain_path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
& .\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_smoke.py::test_write_web_kobe_pddl_smoke_writes_pddl_and_report -q
```

Expected: import failure because `write_web_kobe_pddl_smoke` does not exist.

- [ ] **Step 3: Implement artifact writing**

Modify `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py`.

Add imports:

```python
import json
```

Add result dataclass near `WebKobePddlSmokeReport`:

```python
@dataclass(frozen=True)
class WebKobePddlSmokeResult:
    artifacts: WebKobePddlArtifacts
    report: WebKobePddlSmokeReport
    output_dir: Path
```

Add writer function:

```python
def write_web_kobe_pddl_smoke(
    graph: WebKobeGraph,
    output_dir: Path,
    *,
    goal_node_id: str,
    start_node_id: str | None = None,
) -> WebKobePddlSmokeResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    domain_path = output_dir / "domain.pddl"
    problem_path = output_dir / "problem.pddl"
    report_path = output_dir / "smoke_report.json"

    artifacts = compile_web_kobe_graph_to_pddl(
        graph,
        start_node_id=start_node_id,
        goal_node_id=goal_node_id,
    )
    report = analyze_web_kobe_pddl_smoke(
        graph,
        start_node_id=start_node_id,
        goal_node_id=goal_node_id,
        domain_path=domain_path,
        problem_path=problem_path,
    )

    domain_path.write_text(artifacts.domain, encoding="utf-8")
    problem_path.write_text(artifacts.problem, encoding="utf-8")
    report_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return WebKobePddlSmokeResult(
        artifacts=artifacts,
        report=report,
        output_dir=output_dir,
    )
```

- [ ] **Step 4: Run smoke tests**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
& .\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_smoke.py -q
```

Expected: all smoke tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py tests/safesym_bridge/test_web_kobe_pddl_smoke.py
git commit -m "feat: write web kobe pddl smoke artifacts"
```

---

## Task 3: Add `web-kobe-pddl-smoke` CLI

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Modify: `tests/safesym_bridge/test_cli.py`

**Interfaces:**
- Consumes:
  - `load_web_kobe_graph_json(path: Path) -> WebKobeGraph`
  - `write_web_kobe_pddl_smoke(graph, output_dir, *, goal_node_id, start_node_id=None)`
- Produces:
  - CLI command `web-kobe-pddl-smoke`

- [ ] **Step 1: Write failing CLI test**

Append to `tests/safesym_bridge/test_cli.py`:

```python
def test_main_web_kobe_pddl_smoke_writes_report(tmp_path):
    graph_path = tmp_path / "web_kobe_graph.json"
    output_dir = tmp_path / "web_kobe_smoke"
    graph = WebKobeGraph(
        app="example",
        start_node_id="empty",
        total_steps_completed=1,
        nodes=[
            WebKobeNode(
                node_id="empty",
                page_description="empty page",
                page_frame=PageFrame(
                    page_id="empty",
                    page_type="listing",
                    url="https://example.test",
                    url_pattern="https://example.test",
                    title="empty",
                ),
                state_schema={"cart_count": [0]},
                last_state_snapshot={"cart_count": 0},
            ),
            WebKobeNode(
                node_id="filled",
                page_description="filled page",
                page_frame=PageFrame(
                    page_id="filled",
                    page_type="listing",
                    url="https://example.test",
                    url_pattern="https://example.test",
                    title="filled",
                ),
                state_schema={"cart_count": [1]},
                last_state_snapshot={"cart_count": 1},
            ),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="empty",
                target_node_id="filled",
                instruction="add to cart",
                action=BrowserAction("click", "button.add", "add_to_cart"),
                capability=None,
                target_observation="filled cart",
                observed_delta=[ObservedDelta("cart_count", 0, 1, "state_indicator_change")],
                schema_delta={"cart_count": {"before": 0, "after": 1}},
                execution_trace=ExecutionTrace(
                    "click",
                    "button.add",
                    "add",
                    {},
                    "empty",
                    "filled",
                    True,
                ),
                status="succeeded_with_observed_change",
            )
        ],
    )
    graph_path.write_text(json.dumps(graph.to_dict()), encoding="utf-8")

    exit_code = main(
        [
            "web-kobe-pddl-smoke",
            "--graph",
            str(graph_path),
            "--output",
            str(output_dir),
            "--goal-node",
            "filled",
        ]
    )

    assert exit_code == 0
    assert (output_dir / "domain.pddl").exists()
    assert (output_dir / "problem.pddl").exists()
    report = json.loads((output_dir / "smoke_report.json").read_text(encoding="utf-8"))
    assert report["planning_ready"] is True
    assert report["safety_trigger_expected"] is False
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
& .\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_cli.py::test_main_web_kobe_pddl_smoke_writes_report -q
```

Expected: argparse rejects `web-kobe-pddl-smoke` as an invalid command.

- [ ] **Step 3: Implement CLI parser and branch**

In `src/ai_web_explorer/safesym_bridge/cli.py`, add import:

```python
from ai_web_explorer.safesym_bridge.web_kobe_pddl_smoke import (
    write_web_kobe_pddl_smoke,
)
```

Add parser after `web-kobe-pddl-from-graph`:

```python
    web_kobe_pddl_smoke_parser = subparsers.add_parser(
        "web-kobe-pddl-smoke",
        help="Write Web-KOBE PDDL plus planning-readiness smoke report.",
    )
    web_kobe_pddl_smoke_parser.add_argument(
        "--graph",
        type=Path,
        required=True,
        help="Path to an explored Web-KOBE graph JSON.",
    )
    web_kobe_pddl_smoke_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/web_kobe_pddl_smoke"),
        help="Directory to write domain.pddl, problem.pddl, and smoke_report.json.",
    )
    web_kobe_pddl_smoke_parser.add_argument(
        "--goal-node",
        required=True,
        help="Goal node ID for the generated Web-KOBE PDDL problem.",
    )
    web_kobe_pddl_smoke_parser.add_argument(
        "--start-node",
        default=None,
        help="Optional start node override. Defaults to graph.start_node_id.",
    )
```

Add command branch after `web-kobe-pddl-from-graph`:

```python
        elif args.mode == "web-kobe-pddl-smoke":
            graph = load_web_kobe_graph_json(args.graph)
            result = write_web_kobe_pddl_smoke(
                graph,
                args.output,
                start_node_id=args.start_node,
                goal_node_id=args.goal_node,
            )
            output_path = result.output_dir
```

- [ ] **Step 4: Run CLI tests**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
& .\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_cli.py -q
```

Expected: all CLI tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/ai_web_explorer/safesym_bridge/cli.py tests/safesym_bridge/test_cli.py
git commit -m "feat: add web kobe pddl smoke cli"
```

---

## Task 4: Update docs and run full verification

**Files:**
- Modify: `docs/safesym-bridge.md`
- Modify: `docs/current-project-overview.md`
- Modify: `docs/current-project-overview.zh-CN.md`

**Interfaces:**
- Consumes: completed `web-kobe-pddl-smoke` behavior.
- Produces: updated user-facing docs and verified clean branch.

- [ ] **Step 1: Update `docs/safesym-bridge.md`**

Add this section under the generic Web-KOBE direction command examples:

```markdown
### Planning-readiness smoke

Before requiring SafeSym safety injection, use the planning smoke to check that
an explored `WebKobeGraph` produces non-empty, connected PDDL artifacts:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-pddl-smoke \
  --graph outputs/web_kobe_explored_graph.json \
  --output outputs/web_kobe_pddl_smoke \
  --goal-node <goal_node_id>
```

This writes:

```text
domain.pddl
problem.pddl
smoke_report.json
```

This smoke validates planning-readiness only. If the graph does not contain a
safety-relevant action such as `order_place_confirm`, SafeSym safety injection
not triggering is expected and should not be treated as a failure.
```

- [ ] **Step 2: Update current overview docs**

In `docs/current-project-overview.md`, add a short note near the Web-KOBE PDDL command list:

```markdown
The next short-term validation is `web-kobe-pddl-smoke`, which checks whether
an explored WebKobeGraph yields non-empty, graph-reachable PDDL artifacts. This
is planning-readiness validation, not SafeSym safety-trigger validation.
```

In `docs/current-project-overview.zh-CN.md`, add the matching Chinese note:

```markdown
下一步短期验证是 `web-kobe-pddl-smoke`：检查探索得到的 WebKobeGraph 是否能生成非空、图上可达的 PDDL artifact。这是 planning-readiness 验证，不是 SafeSym 安全规则触发验证。
```

- [ ] **Step 3: Run focused tests**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
& .\.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_pddl_smoke.py tests/safesym_bridge/test_cli.py -q
```

Expected: all focused tests pass.

- [ ] **Step 4: Run full SafeSym bridge tests**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
& .\.venv\Scripts\python.exe -m pytest tests/safesym_bridge -q
```

Expected: all bridge tests pass. If Playwright browser launch fails with sandbox `EPERM`, rerun the same command with required escalation and record that the sandbox blocked Chromium startup.

- [ ] **Step 5: Verify CLI help**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
& .\.venv\Scripts\python.exe -m ai_web_explorer.safesym_bridge.cli --help
```

Expected: help output includes `web-kobe-pddl-smoke`.

- [ ] **Step 6: Commit docs and final verification state**

```bash
git add docs/safesym-bridge.md docs/current-project-overview.md docs/current-project-overview.zh-CN.md
git commit -m "docs: document web kobe pddl planning smoke"
```

- [ ] **Step 7: Inspect git status**

Run:

```bash
git status --short
```

Expected: no uncommitted changes.

---

## Self-Review

### Spec coverage

- Planning-readiness only: Task 1 report fields and Task 4 docs.
- No safety-trigger requirement: Task 1 report defaults and Task 4 docs.
- CLI command `web-kobe-pddl-smoke`: Task 3.
- Graph JSON loading through existing projector loader: Task 3.
- Start/goal validation: Task 1 uses existing compiler validation and reachability validation.
- Reachability through projectable edges: Task 1.
- PDDL artifact writing: Task 2.
- `smoke_report.json`: Task 2.
- Failure reporting for no actions, no predicates, missing init/goal, unreachable goal: Task 1.
- Tests without browser/SafeSym/Fast Downward: Task 1 through Task 3.
- Docs explaining non-triggered safety injection is expected: Task 4.

### Marker scan

No unresolved markers or incomplete sections are present. Each task includes files, interfaces, concrete test code, implementation code, commands, expected outcomes, and commit commands.

### Type consistency

The plan consistently uses `WebKobePddlSmokeReport`, `WebKobePddlSmokeResult`, `analyze_web_kobe_pddl_smoke`, `write_web_kobe_pddl_smoke`, and `goal_reachable_through_projectable_edges`. CLI wiring consumes `load_web_kobe_graph_json` and `write_web_kobe_pddl_smoke`.
