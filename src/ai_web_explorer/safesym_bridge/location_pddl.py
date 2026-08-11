from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ai_web_explorer.grounded_web.graph import WebKobeEdge, WebKobeGraph


LOCATION_PROJECTION_SCHEMA_VERSION = "location-pddl-projection-v1"
PROJECTABLE_EDGE_STATUSES = frozenset(
    {
        "verified",
        "succeeded",
        "succeeded_with_observed_change",
        "succeeded_with_navigation",
    }
)


@dataclass(frozen=True)
class LocationDomainProjection:
    domain: str
    report: dict[str, Any]


@dataclass(frozen=True)
class LocationProblemProjection:
    problem: str
    start_location: str
    goal_location: str


def _stable_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def _slug(value: str | None, *, fallback_prefix: str, stable_id: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")
    if not text:
        return f"{fallback_prefix}_{_stable_digest(stable_id)}"
    if text[0].isdigit():
        return f"n_{text}"
    return text


def _unique_name(
    base: str,
    *,
    stable_id: str,
    used_names: set[str],
) -> str:
    if base not in used_names:
        used_names.add(base)
        return base
    candidate = f"{base}__{_stable_digest(stable_id)}"
    used_names.add(candidate)
    return candidate


def _location_names(graph: WebKobeGraph) -> dict[str, str]:
    names: dict[str, str] = {}
    used_names: set[str] = set()
    for node in sorted(graph.nodes, key=lambda item: item.node_id):
        base = _slug(
            node.node_label or node.page_description,
            fallback_prefix="location",
            stable_id=node.node_id,
        )
        names[node.node_id] = _unique_name(
            base,
            stable_id=node.node_id,
            used_names=used_names,
        )
    return names


def _action_identity(edge: WebKobeEdge) -> str:
    return (
        edge.action.canonical_action_name or edge.action.semantic_id or ""
    ).strip()


def _action_names(edges: Sequence[WebKobeEdge]) -> dict[str, str]:
    names: dict[str, str] = {}
    used_names: set[str] = set()
    for edge in sorted(edges, key=lambda item: item.edge_id):
        base = _slug(
            _action_identity(edge),
            fallback_prefix="action",
            stable_id=edge.edge_id,
        )
        names[edge.edge_id] = _unique_name(
            base,
            stable_id=edge.edge_id,
            used_names=used_names,
        )
    return names


def _exclusion_reason(
    edge: WebKobeEdge,
    known_node_ids: set[str],
) -> str | None:
    if (
        edge.source_node_id not in known_node_ids
        or edge.target_node_id not in known_node_ids
    ):
        return "missing_location_reference"
    if edge.source_node_id == edge.target_node_id:
        return "planning_self_loop"
    if (
        not edge.execution_trace.success
        or edge.status not in PROJECTABLE_EDGE_STATUSES
    ):
        return "unverified_transition"
    if not _action_identity(edge):
        return "invalid_action_identity"
    return None


def _raw_edge_ids_by_planning_edge(
    edge_mappings: Sequence[Mapping[str, Any]],
) -> dict[str, list[str]]:
    raw_ids: dict[str, set[str]] = {}
    for mapping in edge_mappings:
        planning_edge_id = str(mapping.get("planning_edge_id") or "")
        raw_edge_id = str(mapping.get("raw_edge_id") or "")
        if planning_edge_id and raw_edge_id:
            raw_ids.setdefault(planning_edge_id, set()).add(raw_edge_id)
    return {
        planning_edge_id: sorted(edge_ids)
        for planning_edge_id, edge_ids in raw_ids.items()
    }


def _projectable_edges(
    graph: WebKobeGraph,
) -> tuple[list[WebKobeEdge], list[dict[str, str]]]:
    known_node_ids = {node.node_id for node in graph.nodes}
    projectable: list[WebKobeEdge] = []
    excluded: list[dict[str, str]] = []
    for edge in sorted(graph.edges, key=lambda item: item.edge_id):
        reason = _exclusion_reason(edge, known_node_ids)
        if reason is None:
            projectable.append(edge)
        else:
            excluded.append({"planning_edge_id": edge.edge_id, "reason": reason})
    return projectable, excluded


def _render_domain(
    *,
    domain_name: str,
    locations: Mapping[str, str],
    edges: Sequence[WebKobeEdge],
    action_names: Mapping[str, str],
) -> str:
    lines = [
        f"(define (domain {domain_name})",
        "  (:requirements :strips :typing)",
        "  (:types location)",
        "  (:constants",
    ]
    lines.extend(
        f"    {locations[node_id]} - location"
        for node_id in sorted(locations)
    )
    lines.extend(
        [
            "  )",
        "  (:predicates",
        "    (at ?location - location)",
            "  )",
        ]
    )
    for edge in sorted(edges, key=lambda item: item.edge_id):
        action_name = action_names[edge.edge_id]
        source = locations[edge.source_node_id]
        target = locations[edge.target_node_id]
        lines.extend(
            [
                f"  (:action {action_name}",
                "    :parameters ()",
                f"    :precondition (and (at {source}))",
                "    :effect (and",
                f"      (not (at {source}))",
                f"      (at {target})",
                "    )",
                "  )",
            ]
        )
    lines.append(")")
    return "\n".join(lines) + "\n"


def compile_location_domain(
    graph: WebKobeGraph,
    *,
    edge_mappings: Sequence[Mapping[str, Any]] = (),
    domain_name: str = "web_kobe_location",
) -> LocationDomainProjection:
    if not graph.nodes:
        raise ValueError("no_planning_locations")
    locations = _location_names(graph)
    projectable, excluded = _projectable_edges(graph)
    action_names = _action_names(projectable)
    raw_ids = _raw_edge_ids_by_planning_edge(edge_mappings)
    actions = [
        {
            "planning_edge_id": edge.edge_id,
            "pddl_action": action_names[edge.edge_id],
            "source_location": locations[edge.source_node_id],
            "target_location": locations[edge.target_node_id],
            "raw_edge_ids": raw_ids.get(edge.edge_id, []),
        }
        for edge in sorted(projectable, key=lambda item: item.edge_id)
    ]
    report = {
        "schema_version": LOCATION_PROJECTION_SCHEMA_VERSION,
        "domain_name": domain_name,
        "locations": [
            {
                "planning_node_id": node_id,
                "pddl_constant": locations[node_id],
            }
            for node_id in sorted(locations)
        ],
        "actions": actions,
        "excluded_edges": excluded,
    }
    normalized_domain_name = _slug(
        domain_name,
        fallback_prefix="domain",
        stable_id=domain_name,
    )
    return LocationDomainProjection(
        domain=_render_domain(
            domain_name=normalized_domain_name,
            locations=locations,
            edges=projectable,
            action_names=action_names,
        ),
        report=report,
    )


def _is_reachable(graph: WebKobeGraph, start: str, goal: str) -> bool:
    adjacency: dict[str, set[str]] = {}
    known = {node.node_id for node in graph.nodes}
    for edge in graph.edges:
        if _exclusion_reason(edge, known) is None:
            adjacency.setdefault(edge.source_node_id, set()).add(
                edge.target_node_id
            )
    pending = [start]
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current == goal:
            return True
        if current in seen:
            continue
        seen.add(current)
        pending.extend(sorted(adjacency.get(current, ()), reverse=True))
    return False


def compile_location_problem(
    graph: WebKobeGraph,
    *,
    start_node_id: str,
    goal_node_id: str,
    domain_name: str = "web_kobe_location",
    problem_name: str = "web_kobe_location_problem",
) -> LocationProblemProjection:
    locations = _location_names(graph)
    if start_node_id not in locations:
        raise ValueError(f"unknown_start_location: {start_node_id}")
    if goal_node_id not in locations:
        raise ValueError(f"unknown_goal_location: {goal_node_id}")
    if not _is_reachable(graph, start_node_id, goal_node_id):
        raise ValueError(f"goal_unreachable: {start_node_id} -> {goal_node_id}")
    normalized_domain_name = _slug(
        domain_name,
        fallback_prefix="domain",
        stable_id=domain_name,
    )
    normalized_problem_name = _slug(
        problem_name,
        fallback_prefix="problem",
        stable_id=problem_name,
    )
    start_location = locations[start_node_id]
    goal_location = locations[goal_node_id]
    problem = "\n".join(
        [
            f"(define (problem {normalized_problem_name})",
            f"  (:domain {normalized_domain_name})",
            f"  (:init (at {start_location}))",
            f"  (:goal (at {goal_location}))",
            ")",
            "",
        ]
    )
    return LocationProblemProjection(
        problem=problem,
        start_location=start_location,
        goal_location=goal_location,
    )
