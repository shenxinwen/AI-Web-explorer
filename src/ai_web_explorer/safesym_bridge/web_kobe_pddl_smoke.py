from __future__ import annotations

import json
import re
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
    goal_fact: str | None
    goal_reachable_in_graph: bool
    projectable_edge_count: int
    projected_action_count: int
    projected_predicate_count: int
    pddl_static_consistency_ready: bool
    undeclared_predicates: list[str] = field(default_factory=list)
    projected_action_names: list[str] = field(default_factory=list)
    duplicate_action_names: list[str] = field(default_factory=list)
    projected_observed_fact_count: int = 0
    unsafe_delete_effects: list[str] = field(default_factory=list)
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
            "goal_fact": self.goal_fact,
            "goal_reachable_in_graph": self.goal_reachable_in_graph,
            "projectable_edge_count": self.projectable_edge_count,
            "projected_action_count": self.projected_action_count,
            "projected_predicate_count": self.projected_predicate_count,
            "pddl_static_consistency_ready": self.pddl_static_consistency_ready,
            "undeclared_predicates": list(self.undeclared_predicates),
            "projected_action_names": list(self.projected_action_names),
            "duplicate_action_names": list(self.duplicate_action_names),
            "projected_observed_fact_count": self.projected_observed_fact_count,
            "unsafe_delete_effects": list(self.unsafe_delete_effects),
            "domain_path": self.domain_path,
            "problem_path": self.problem_path,
            "safety_trigger_expected": self.safety_trigger_expected,
            "safety_trigger_reason": self.safety_trigger_reason,
            "planning_ready": self.planning_ready,
            "failure_reasons": list(self.failure_reasons),
        }


@dataclass(frozen=True)
class WebKobePddlSmokeResult:
    artifacts: WebKobePddlArtifacts
    report: WebKobePddlSmokeReport
    output_dir: Path


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


def _projected_action_names(domain: str) -> list[str]:
    return re.findall(r"\(:action\s+([^\s()]+)", domain)


def _duplicate_action_names(domain: str) -> list[str]:
    names = _projected_action_names(domain)
    return sorted({name for name in names if names.count(name) > 1})


def _projected_observed_fact_count(domain: str) -> int:
    return len(re.findall(r"\(control_[a-zA-Z0-9_]+\)", domain))


def _unsafe_delete_effects(domain: str) -> list[str]:
    results: list[str] = []
    for block in domain.split("  (:action ")[1:]:
        action_name = block.splitlines()[0].strip()
        precondition_block = ""
        effect_block = ""
        if ":precondition" in block and ":effect" in block:
            precondition_block = block.split(":precondition", 1)[1].split(
                ":effect",
                1,
            )[0]
            effect_block = block.split(":effect", 1)[1]
        for predicate in re.findall(
            r"\(not\s+\(([a-zA-Z][a-zA-Z0-9_]*)\)\)",
            effect_block,
        ):
            if predicate.startswith("at_"):
                continue
            if f"({predicate})" not in precondition_block:
                results.append(f"{action_name}:{predicate}")
    return sorted(results)


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


def _predicate_names_in_text(text: str) -> set[str]:
    return set(re.findall(r"\(([a-zA-Z][a-zA-Z0-9_]*)\)", text))


def _declared_predicates(domain: str) -> set[str]:
    if "  (:predicates" not in domain:
        return set()
    block = domain.split("  (:predicates", 1)[1]
    if "  (:action" in block:
        block = block.split("  (:action", 1)[0]
    return _predicate_names_in_text(block)


def _used_predicates(domain: str, problem: str) -> set[str]:
    used: set[str] = set()
    if "  (:action" in domain:
        used.update(
            _predicate_names_in_text("  (:action" + domain.split("  (:action", 1)[1])
        )
    if "  (:init" in problem:
        used.update(
            _predicate_names_in_text("  (:init" + problem.split("  (:init", 1)[1])
        )
    return used - {"and", "not"}


def _undeclared_predicates(domain: str, problem: str) -> list[str]:
    return sorted(_used_predicates(domain, problem) - _declared_predicates(domain))


def _failure_reasons(
    *,
    goal_reachable: bool,
    projectable_edge_count: int,
    projected_action_count: int,
    projected_predicate_count: int,
    undeclared_predicates: list[str],
    duplicate_action_names: list[str],
    unsafe_delete_effects: list[str],
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
    if undeclared_predicates:
        reasons.append(
            "domain uses undeclared predicates: " + ", ".join(undeclared_predicates)
        )
    if duplicate_action_names:
        reasons.append(
            "domain has duplicate action names: " + ", ".join(duplicate_action_names)
        )
    if unsafe_delete_effects:
        reasons.append(
            "domain has delete effects without matching preconditions: "
            + ", ".join(unsafe_delete_effects)
        )
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
    goal_fact: str | None = None,
    start_node_id: str | None = None,
    domain_path: Path | None = None,
    problem_path: Path | None = None,
) -> WebKobePddlSmokeReport:
    selected_start = start_node_id or graph.start_node_id
    artifacts = compile_web_kobe_graph_to_pddl(
        graph,
        start_node_id=start_node_id,
        goal_node_id=goal_node_id,
        goal_fact=goal_fact,
    )
    projectable_edge_count = len(_projectable_edges(graph))
    goal_reachable = goal_reachable_through_projectable_edges(
        graph,
        start_node_id=selected_start,
        goal_node_id=goal_node_id,
    )
    projected_action_count = _count_projected_actions(artifacts.domain)
    projected_action_names = _projected_action_names(artifacts.domain)
    duplicate_action_names = _duplicate_action_names(artifacts.domain)
    projected_observed_fact_count = _projected_observed_fact_count(artifacts.domain)
    unsafe_delete_effects = _unsafe_delete_effects(artifacts.domain)
    projected_predicate_count = _count_projected_predicates(artifacts.domain)
    undeclared_predicates = _undeclared_predicates(
        artifacts.domain,
        artifacts.problem,
    )
    reasons = _failure_reasons(
        goal_reachable=goal_reachable,
        projectable_edge_count=projectable_edge_count,
        projected_action_count=projected_action_count,
        projected_predicate_count=projected_predicate_count,
        undeclared_predicates=undeclared_predicates,
        duplicate_action_names=duplicate_action_names,
        unsafe_delete_effects=unsafe_delete_effects,
        domain=artifacts.domain,
        problem=artifacts.problem,
    )

    return WebKobePddlSmokeReport(
        graph_loaded=True,
        app=graph.app,
        start_node=selected_start,
        goal_node=goal_node_id,
        goal_fact=goal_fact,
        goal_reachable_in_graph=goal_reachable,
        projectable_edge_count=projectable_edge_count,
        projected_action_count=projected_action_count,
        projected_predicate_count=projected_predicate_count,
        pddl_static_consistency_ready=not undeclared_predicates,
        undeclared_predicates=undeclared_predicates,
        projected_action_names=projected_action_names,
        duplicate_action_names=duplicate_action_names,
        projected_observed_fact_count=projected_observed_fact_count,
        unsafe_delete_effects=unsafe_delete_effects,
        domain_path=str(domain_path) if domain_path is not None else None,
        problem_path=str(problem_path) if problem_path is not None else None,
        planning_ready=not reasons,
        failure_reasons=reasons,
    )


def write_web_kobe_pddl_smoke(
    graph: WebKobeGraph,
    output_dir: Path,
    *,
    goal_node_id: str,
    goal_fact: str | None = None,
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
        goal_fact=goal_fact,
    )
    report = analyze_web_kobe_pddl_smoke(
        graph,
        start_node_id=start_node_id,
        goal_node_id=goal_node_id,
        goal_fact=goal_fact,
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
