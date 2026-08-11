from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ai_web_explorer.grounded_web.graph import WebKobeEdge, WebKobeGraph


SURFACE_PROJECTION_SCHEMA_VERSION = "surface-pddl-projection-v1"
PROJECTABLE_EDGE_STATUSES = frozenset(
    {
        "verified",
        "succeeded",
        "succeeded_with_observed_change",
        "succeeded_with_navigation",
    }
)


@dataclass(frozen=True)
class SurfaceDomainProjection:
    domain: str
    report: dict[str, Any]


@dataclass(frozen=True)
class SurfaceProblemProjection:
    problem: str
    start_surface: str
    goal_surface: str


def _stable_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def _slug(value: str | None, *, fallback_prefix: str, stable_id: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")
    if not text:
        return f"{fallback_prefix}_{_stable_digest(stable_id)}"
    if text[0].isdigit():
        return f"n_{text}"
    return text


def _unique_name(base: str, *, stable_id: str, used_names: set[str]) -> str:
    if base not in used_names:
        used_names.add(base)
        return base
    candidate = f"{base}__{_stable_digest(stable_id)}"
    used_names.add(candidate)
    return candidate


def _surface_names(graph: WebKobeGraph) -> dict[str, str]:
    names: dict[str, str] = {}
    used_names: set[str] = set()
    for node in sorted(graph.nodes, key=lambda item: item.node_id):
        base = _slug(
            node.node_label or node.page_description,
            fallback_prefix="surface",
            stable_id=node.node_id,
        )
        names[node.node_id] = _unique_name(
            base,
            stable_id=node.node_id,
            used_names=used_names,
        )
    return names


def _action_identity(edge: WebKobeEdge) -> str:
    return (edge.action.canonical_action_name or edge.action.semantic_id or "").strip()


def _projectable_reason(edge: WebKobeEdge, known_node_ids: set[str]) -> str | None:
    if edge.source_node_id not in known_node_ids or edge.target_node_id not in known_node_ids:
        return "missing_surface_reference"
    if not edge.execution_trace.success or edge.status not in PROJECTABLE_EDGE_STATUSES:
        return "unverified_transition"
    if not _action_identity(edge):
        return "invalid_action_identity"
    return None


def _projectable_edges(graph: WebKobeGraph) -> tuple[list[WebKobeEdge], list[dict[str, str]]]:
    known_node_ids = {node.node_id for node in graph.nodes}
    projectable: list[WebKobeEdge] = []
    excluded: list[dict[str, str]] = []
    for edge in sorted(graph.edges, key=lambda item: item.edge_id):
        reason = _projectable_reason(edge, known_node_ids)
        if reason is None:
            projectable.append(edge)
        else:
            excluded.append({"edge_id": edge.edge_id, "reason": reason})
    return projectable, excluded


def _transition_names(
    edges: Sequence[WebKobeEdge],
    surface_names: Mapping[str, str],
) -> dict[str, str]:
    names: dict[str, str] = {}
    used_names: set[str] = set()
    for edge in sorted(edges, key=lambda item: item.edge_id):
        action = _slug(
            _action_identity(edge),
            fallback_prefix="transition",
            stable_id=edge.edge_id,
        )
        source = surface_names[edge.source_node_id]
        suffix = "on" if edge.source_node_id == edge.target_node_id else "from"
        base = f"{action}_{suffix}_{source}"
        names[edge.edge_id] = _unique_name(
            base,
            stable_id=edge.edge_id,
            used_names=used_names,
        )
    return names


def _render_domain(
    *,
    domain_name: str,
    surface_names: Mapping[str, str],
    edges: Sequence[WebKobeEdge],
    transition_names: Mapping[str, str],
) -> str:
    lines = [
        f"(define (domain {domain_name})",
        "  (:requirements :strips :typing)",
        "  (:types surface transition)",
        "  (:constants",
    ]
    lines.extend(
        f"    {surface_names[node_id]} - surface"
        for node_id in sorted(surface_names)
    )
    lines.extend(
        f"    transition_{transition_names[edge.edge_id]} - transition"
        for edge in sorted(edges, key=lambda item: item.edge_id)
    )
    lines.extend(
        [
            "  )",
            "  (:predicates",
            "    (at ?surface - surface)",
            "    (executed ?transition - transition)",
            "  )",
        ]
    )
    for edge in sorted(edges, key=lambda item: item.edge_id):
        action_name = transition_names[edge.edge_id]
        source = surface_names[edge.source_node_id]
        target = surface_names[edge.target_node_id]
        marker = f"transition_{action_name}"
        effects = []
        if source != target:
            effects.extend([f"(not (at {source}))", f"(at {target})"])
        effects.append(f"(executed {marker})")
        lines.extend(
            [
                f"  (:action {action_name}",
                "    :parameters ()",
                f"    :precondition (and (at {source}))",
                "    :effect (and",
                *(f"      {effect}" for effect in effects),
                "    )",
                "  )",
            ]
        )
    lines.append(")")
    return "\n".join(lines) + "\n"


def compile_surface_domain(
    graph: WebKobeGraph,
    *,
    domain_name: str = "web_kobe_surface",
) -> SurfaceDomainProjection:
    if not graph.nodes:
        raise ValueError("no_observed_surfaces")
    surfaces = _surface_names(graph)
    projectable, excluded = _projectable_edges(graph)
    transitions = _transition_names(projectable, surfaces)
    normalized_domain_name = _slug(
        domain_name,
        fallback_prefix="domain",
        stable_id=domain_name,
    )
    report = {
        "schema_version": SURFACE_PROJECTION_SCHEMA_VERSION,
        "domain_name": normalized_domain_name,
        "surfaces": [
            {"node_id": node_id, "pddl_constant": surfaces[node_id]}
            for node_id in sorted(surfaces)
        ],
        "transitions": [
            {
                "edge_id": edge.edge_id,
                "pddl_action": transitions[edge.edge_id],
                "transition_constant": f"transition_{transitions[edge.edge_id]}",
                "source_surface": surfaces[edge.source_node_id],
                "target_surface": surfaces[edge.target_node_id],
            }
            for edge in sorted(projectable, key=lambda item: item.edge_id)
        ],
        "excluded_edges": excluded,
    }
    return SurfaceDomainProjection(
        domain=_render_domain(
            domain_name=normalized_domain_name,
            surface_names=surfaces,
            edges=projectable,
            transition_names=transitions,
        ),
        report=report,
    )


def _is_reachable(
    graph: WebKobeGraph,
    *,
    start_node_id: str,
    goal_node_id: str,
) -> bool:
    projectable, _ = _projectable_edges(graph)
    adjacency: dict[str, set[str]] = {}
    for edge in projectable:
        adjacency.setdefault(edge.source_node_id, set()).add(edge.target_node_id)
    pending = [start_node_id]
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current == goal_node_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        pending.extend(sorted(adjacency.get(current, ()), reverse=True))
    return False


def compile_surface_problem(
    graph: WebKobeGraph,
    *,
    goal_node_id: str,
    problem_name: str = "web_kobe_surface_problem",
) -> SurfaceProblemProjection:
    surfaces = _surface_names(graph)
    start_node_id = graph.start_node_id
    if start_node_id not in surfaces:
        raise ValueError(f"unknown_start_surface: {start_node_id}")
    if goal_node_id not in surfaces:
        raise ValueError(f"unknown_goal_surface: {goal_node_id}")
    if not _is_reachable(
        graph,
        start_node_id=start_node_id,
        goal_node_id=goal_node_id,
    ):
        raise ValueError(f"goal_unreachable: {start_node_id} -> {goal_node_id}")
    normalized_problem_name = _slug(
        problem_name,
        fallback_prefix="problem",
        stable_id=problem_name,
    )
    start_surface = surfaces[start_node_id]
    goal_surface = surfaces[goal_node_id]
    problem = "\n".join(
        [
            f"(define (problem {normalized_problem_name})",
            "  (:domain web_kobe_surface)",
            f"  (:init (at {start_surface}))",
            f"  (:goal (at {goal_surface}))",
            ")",
            "",
        ]
    )
    return SurfaceProblemProjection(
        problem=problem,
        start_surface=start_surface,
        goal_surface=goal_surface,
    )
