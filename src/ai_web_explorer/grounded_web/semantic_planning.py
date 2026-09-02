from __future__ import annotations

from dataclasses import replace
from typing import Any

from ai_web_explorer.grounded_web.graph import WebKobeEdge, WebKobeGraph
from ai_web_explorer.grounded_web.semantic_model import (
    SEMANTIC_ACTION_ROLES,
    SemanticAction,
    SemanticPlanningGraph,
    SemanticProjectionReport,
    normalize_semantic_id,
)


PROJECTABLE_EDGE_STATUSES = frozenset(
    {
        "verified",
        "succeeded",
        "succeeded_with_observed_change",
        "succeeded_with_navigation",
    }
)
PRESENTATION_ROLES = frozenset({"presentation_capability"})
GUARDED_ROLES = frozenset({"guarded_navigation", "form_completion", "commit"})
REQUIRED_FACT_CONFIDENCE = 0.80


def _unique_sorted(values: list[str]) -> list[str]:
    return sorted({normalize_semantic_id(value) for value in values if normalize_semantic_id(value)})


def _edge_name(edge: WebKobeEdge) -> str:
    return normalize_semantic_id(edge.action.canonical_action_name or edge.action.semantic_id)


def _completion_fact(
    location: str,
    action_name: str,
    *,
    disambiguate_location: bool = False,
) -> str:
    if disambiguate_location:
        return normalize_semantic_id(f"{action_name}_{location}_succeeded")
    return normalize_semantic_id(f"{action_name}_succeeded")


def _source_state(graph: WebKobeGraph, edge: WebKobeEdge):
    nodes = {node.node_id: node for node in graph.nodes}
    node = nodes.get(edge.source_node_id)
    return node.planning_state if node is not None else None


def _record_uncertain(
    uncertain: list[dict[str, Any]],
    *,
    edge: WebKobeEdge,
    fact: str,
    reason: str,
) -> None:
    uncertain.append(
        {
            "raw_edge_id": edge.edge_id,
            "fact": fact,
            "reason": reason,
        }
    )


def _record_provenance(
    provenance: list[dict[str, Any]],
    *,
    edge: WebKobeEdge,
    facts: list[str],
    kind: str,
    source: str,
) -> None:
    for fact in facts:
        provenance.append(
            {
                "raw_edge_id": edge.edge_id,
                "fact": fact,
                "kind": kind,
                "source": source,
                "evidence": list(edge.semantic_observation.evidence),
            }
        )


def _excluded(edge: WebKobeEdge, reason: str) -> dict[str, Any]:
    return {"raw_edge_id": edge.edge_id, "reason": reason}


def build_semantic_planning_graph(
    graph: WebKobeGraph,
) -> tuple[SemanticPlanningGraph, SemanticProjectionReport]:
    excluded_edges: list[dict[str, Any]] = []
    uncertain_preconditions: list[dict[str, Any]] = []
    fact_provenance: list[dict[str, Any]] = []
    included_raw_edge_ids: list[str] = []
    candidates: list[SemanticAction] = []
    locations: set[str] = set()
    capability_facts: set[str] = set()
    business_facts: set[str] = set()
    nodes = {node.node_id: node for node in graph.nodes}
    successful_action_locations: dict[str, set[str]] = {}
    for edge in graph.edges:
        if (
            edge.execution_trace.success
            and edge.status in PROJECTABLE_EDGE_STATUSES
            and edge.semantic_observation is not None
        ):
            action_name = _edge_name(edge)
            observation = edge.semantic_observation
            source_location = normalize_semantic_id(observation.source_location)
            if source_location and action_name:
                successful_action_locations.setdefault(action_name, set()).add(
                    source_location
                )
    successful_completion_facts = {
        (location, action_name): _completion_fact(
            location,
            action_name,
            disambiguate_location=len(successful_action_locations[action_name]) > 1,
        )
        for action_name, locations_for_action in successful_action_locations.items()
        for location in locations_for_action
    }

    for edge in graph.edges:
        observation = edge.semantic_observation
        if not edge.execution_trace.success:
            excluded_edges.append(_excluded(edge, "failed_execution"))
            continue
        if edge.status not in PROJECTABLE_EDGE_STATUSES:
            excluded_edges.append(_excluded(edge, "non_projectable_status"))
            continue
        if observation is None:
            reason = (
                "semantic_observation_conflict"
                if (
                    edge.execution_trace.metadata.get("semantic_observation_conflict", {})
                    .get("status")
                    == "unresolved"
                )
                else "no_semantic_observation"
            )
            excluded_edges.append(_excluded(edge, reason))
            continue
        source_location = normalize_semantic_id(observation.source_location)
        target_location = normalize_semantic_id(observation.target_location)
        if not source_location or not target_location:
            excluded_edges.append(_excluded(edge, "invalid_location"))
            continue
        role = normalize_semantic_id(observation.action_role)
        if role not in SEMANTIC_ACTION_ROLES or role == "unknown":
            excluded_edges.append(_excluded(edge, "unknown_action_role"))
            continue
        missing_required_actions = sorted(
            {
                normalize_semantic_id(required_action_id)
                for required_action_id in edge.required_action_ids
                if normalize_semantic_id(required_action_id)
                and (
                    source_location,
                    normalize_semantic_id(required_action_id),
                )
                not in successful_completion_facts
            }
        )
        if missing_required_actions:
            excluded_edges.append(
                {
                    "raw_edge_id": edge.edge_id,
                    "reason": "missing_successful_required_action",
                    "missing_action_ids": missing_required_actions,
                }
            )
            continue

        source_state = _source_state(graph, edge)
        active_facts = set(
            _unique_sorted(source_state.active_facts if source_state else [])
        )
        profile_fact_ids = set(
            _unique_sorted(source_state.profile_fact_ids if source_state else [])
        )
        required_facts: list[str] = []
        if role in GUARDED_ROLES:
            confidence = observation.confidence or 0.0
            for candidate in _unique_sorted(observation.candidate_required_facts):
                if confidence < REQUIRED_FACT_CONFIDENCE:
                    _record_uncertain(
                        uncertain_preconditions,
                        edge=edge,
                        fact=candidate,
                        reason="confidence_below_threshold",
                    )
                elif candidate not in active_facts:
                    _record_uncertain(
                        uncertain_preconditions,
                        edge=edge,
                        fact=candidate,
                        reason="inactive_source_fact",
                    )
                elif candidate not in profile_fact_ids:
                    _record_uncertain(
                        uncertain_preconditions,
                        edge=edge,
                        fact=candidate,
                        reason="not_verified_profile_fact",
                    )
                else:
                    required_facts.append(candidate)
        else:
            for candidate in _unique_sorted(observation.candidate_required_facts):
                _record_uncertain(
                    uncertain_preconditions,
                    edge=edge,
                    fact=candidate,
                    reason="role_not_guarded",
                )

        dependency_facts: list[str] = []
        for required_action_id in edge.required_action_ids:
            completion_fact = successful_completion_facts.get(
                (
                    source_location,
                    normalize_semantic_id(required_action_id),
                )
            )
            if completion_fact is not None:
                dependency_facts.append(completion_fact)
        required_facts = _unique_sorted(required_facts + dependency_facts)
        planning_delta = edge.planning_delta
        verified_added = _unique_sorted(
            planning_delta.verified_added_facts if planning_delta else []
        )
        verified_removed = _unique_sorted(
            planning_delta.verified_removed_facts if planning_delta else []
        )
        action_name = _edge_name(edge)
        completion_fact = successful_completion_facts[(source_location, action_name)]
        added_facts = _unique_sorted(verified_added + [completion_fact])
        capability_facts.add(completion_fact)
        _record_provenance(
            fact_provenance,
            edge=edge,
            facts=[completion_fact],
            kind="action_completion",
            source="successful_action",
        )
        if role in PRESENTATION_ROLES and observation.evidence:
            completion_facts = _unique_sorted(observation.completion_facts)
            added_facts = _unique_sorted(added_facts + completion_facts)
            capability_facts.update(completion_facts)
            _record_provenance(
                fact_provenance,
                edge=edge,
                facts=completion_facts,
                kind="capability_completion",
                source="semantic_observation",
            )
        business_facts.update(verified_added)
        business_facts.update(verified_removed)
        business_facts.update(required_facts)
        _record_provenance(
            fact_provenance,
            edge=edge,
            facts=verified_added,
            kind="business_added",
            source="verified_planning_delta",
        )
        _record_provenance(
            fact_provenance,
            edge=edge,
            facts=verified_removed,
            kind="business_removed",
            source="verified_planning_delta",
        )
        _record_provenance(
            fact_provenance,
            edge=edge,
            facts=required_facts,
            kind="business_required",
            source="verified_profile_requirement",
        )
        # Only a verified profile requirement is eligible for preservation.
        # Other active/preserved profile facts are not action effects.
        preserved = _unique_sorted(required_facts)
        preserved = [fact for fact in preserved if fact not in verified_removed]
        business_facts.update(preserved)
        locations.update({source_location, target_location})
        included_raw_edge_ids.append(edge.edge_id)
        candidates.append(
            SemanticAction(
                action_id=_edge_name(edge),
                action_name=_edge_name(edge),
                action_role=role,
                source_location=source_location,
                target_location=target_location,
                required_facts=required_facts,
                added_facts=added_facts,
                removed_facts=verified_removed,
                preserved_facts=preserved,
                raw_edge_ids=[edge.edge_id],
                evidence=list(observation.evidence),
            )
        )

    merged: dict[tuple[Any, ...], SemanticAction] = {}
    for action in candidates:
        key = (
            action.action_name,
            action.action_role,
            action.source_location,
            action.target_location,
            tuple(action.required_facts),
            tuple(action.added_facts),
            tuple(action.removed_facts),
            tuple(action.preserved_facts),
        )
        existing = merged.get(key)
        if existing is None:
            merged[key] = action
        else:
            merged[key] = replace(
                existing,
                raw_edge_ids=sorted(set(existing.raw_edge_ids + action.raw_edge_ids)),
                evidence=sorted(set(existing.evidence + action.evidence)),
            )

    ordered_actions = sorted(
        merged.values(),
        key=lambda action: (
            action.action_name,
            action.action_role,
            action.source_location,
            action.target_location,
            action.required_facts,
            action.added_facts,
            action.removed_facts,
            action.preserved_facts,
        ),
    )
    used_action_ids: set[str] = set()
    normalized_actions: list[SemanticAction] = []
    for action in ordered_actions:
        action_id = action.action_id
        if action_id in used_action_ids:
            action_id = normalize_semantic_id(
                f"{action.action_name}_from_{action.source_location}_to_{action.target_location}"
            )
        suffix = 2
        base_id = action_id
        while action_id in used_action_ids:
            action_id = f"{base_id}_{suffix}"
            suffix += 1
        used_action_ids.add(action_id)
        normalized_actions.append(replace(action, action_id=action_id))

    start_locations = sorted(
        {
            action.source_location
            for action in normalized_actions
            if next(
                (
                    edge
                    for edge in graph.edges
                    if edge.edge_id in action.raw_edge_ids
                    and edge.source_node_id == graph.start_node_id
                ),
                None,
            )
            is not None
        }
    )
    start_location = start_locations[0] if len(start_locations) == 1 else ""
    if len(start_locations) > 1:
        excluded_edges.append(
            {
                "reason": "conflicting_start_location",
                "locations": start_locations,
            }
        )

    start_state = nodes.get(graph.start_node_id).planning_state if nodes.get(graph.start_node_id) else None
    initial_business_facts = _unique_sorted(
        [
            fact
            for fact in _unique_sorted(start_state.active_facts if start_state else [])
            if fact
            in set(
                _unique_sorted(start_state.profile_fact_ids if start_state else [])
            )
        ]
    )
    business_facts.update(initial_business_facts)

    report = SemanticProjectionReport(
        included_raw_edge_ids=sorted(set(included_raw_edge_ids)),
        excluded_edges=sorted(
            excluded_edges,
            key=lambda item: (str(item.get("raw_edge_id", "")), str(item.get("reason", ""))),
        ),
        uncertain_preconditions=sorted(
            uncertain_preconditions,
            key=lambda item: (item["raw_edge_id"], item["fact"], item["reason"]),
        ),
        fact_provenance=sorted(
            fact_provenance,
            key=lambda item: (item["raw_edge_id"], item["fact"], item["kind"]),
        ),
    )
    semantic = SemanticPlanningGraph(
        start_location=start_location,
        locations=sorted(locations),
        capability_facts=sorted(capability_facts),
        business_facts=sorted(business_facts),
        initial_business_facts=initial_business_facts,
        actions=normalized_actions,
    )
    return semantic, report


__all__ = [
    "GUARDED_ROLES",
    "PRESENTATION_ROLES",
    "PROJECTABLE_EDGE_STATUSES",
    "REQUIRED_FACT_CONFIDENCE",
    "build_semantic_planning_graph",
]
