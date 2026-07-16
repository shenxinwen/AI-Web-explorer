from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from ai_web_explorer.grounded_web.graph import WebKobeGraph
from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
    PROJECTABLE_EDGE_STATUSES,
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
        queue.extend(
            target for target in adjacency.get(node_id, []) if target not in visited
        )
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
