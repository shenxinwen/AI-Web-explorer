from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

from ai_web_explorer.grounded_web.graph import (
    BusinessAffordance,
    BusinessTransition,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.state_embedding import (
    EmbeddingProvider,
    cosine_similarity,
)


CONSOLIDATION_SCHEMA_VERSION = "web-kobe-behavior-state-phase-a-v1"
_FAILED_STATUSES = {"failed_execution"}
ACTION_SAME_THRESHOLD = 0.90
ACTION_AMBIGUOUS_THRESHOLD = 0.82


@dataclass(frozen=True)
class ConsolidationReport:
    action_normalizations: list[dict[str, Any]]
    canonical_node_groups: list[dict[str, Any]]
    raw_to_canonical_node: dict[str, str]
    rejected_nodes: dict[str, list[str]]
    edge_mappings: list[dict[str, Any]]
    ambiguous_actions: list[str]
    schema_version: str = CONSOLIDATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "action_normalizations": [dict(item) for item in self.action_normalizations],
            "canonical_node_groups": [dict(item) for item in self.canonical_node_groups],
            "raw_to_canonical_node": dict(self.raw_to_canonical_node),
            "rejected_nodes": {
                node_id: list(reasons)
                for node_id, reasons in self.rejected_nodes.items()
            },
            "edge_mappings": [dict(item) for item in self.edge_mappings],
            "ambiguous_actions": list(self.ambiguous_actions),
        }


@dataclass(frozen=True)
class BehaviorStateGraphArtifacts:
    raw_graph: WebKobeGraph
    canonical_graph: WebKobeGraph
    report: ConsolidationReport


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")


def _affordance_action_name(affordance: BusinessAffordance) -> str:
    return _slug(affordance.action_name) or affordance.action_name.strip()


def _edge_action_name(edge: WebKobeEdge) -> str:
    business_transition: BusinessTransition | None = edge.business_transition
    raw_name = (
        business_transition.action_name
        if business_transition is not None and business_transition.action_name
        else edge.action.canonical_action_name or edge.action.semantic_id
    )
    return _slug(raw_name) or raw_name.strip()


def _affordance_action_text(affordance: BusinessAffordance) -> str:
    return "\n".join(
        [
            f"intent: {affordance.action_name}",
            f"label: {affordance.label or ''}",
            f"target_hint: {affordance.target_hint or ''}",
        ]
    )


def _ordered_action_descriptors(
    graph: WebKobeGraph,
) -> list[tuple[str, str]]:
    descriptors: list[tuple[str, str]] = []
    seen: set[str] = set()
    for node in graph.nodes:
        for affordance in node.business_affordances:
            name = _affordance_action_name(affordance)
            if name and name not in seen:
                seen.add(name)
                descriptors.append((name, _affordance_action_text(affordance)))
    for edge in graph.edges:
        name = _edge_action_name(edge)
        if name and name not in seen:
            seen.add(name)
            descriptors.append(
                (
                    name,
                    "\n".join(
                        [
                            f"intent: {name}",
                            f"label: {edge.action.action_label or ''}",
                            "target_hint: ",
                        ]
                    ),
                )
            )
    return descriptors


def _build_action_normalization(
    graph: WebKobeGraph,
    *,
    embedding_provider: EmbeddingProvider | None,
) -> tuple[dict[str, str], list[dict[str, Any]], list[str]]:
    descriptors = _ordered_action_descriptors(graph)
    action_map = {name: name for name, _ in descriptors}
    records: list[dict[str, Any]] = []
    if embedding_provider is None:
        return action_map, records, []

    embeddings = [
        (name, list(embedding_provider(text)))
        for name, text in descriptors
    ]
    groups: list[list[tuple[str, list[float]]]] = []
    ambiguous: list[str] = []
    for name, embedding in embeddings:
        compatible_groups: list[list[tuple[str, list[float]]]] = []
        ambiguous_groups: list[list[tuple[str, list[float]]]] = []
        for group in groups:
            scores = [cosine_similarity(embedding, item_embedding) for _, item_embedding in group]
            if scores and min(scores) >= ACTION_SAME_THRESHOLD:
                compatible_groups.append(group)
            elif scores and max(scores) >= ACTION_AMBIGUOUS_THRESHOLD:
                ambiguous_groups.append(group)
        if len(compatible_groups) == 1 and not ambiguous_groups:
            group = compatible_groups[0]
            group.append((name, embedding))
            continue
        if compatible_groups or ambiguous_groups:
            for group in compatible_groups + ambiguous_groups:
                for member_name, _ in group:
                    if member_name not in ambiguous:
                        ambiguous.append(member_name)
            if name not in ambiguous:
                ambiguous.append(name)
        groups.append([(name, embedding)])

    for group in groups:
        if len(group) < 2:
            continue
        canonical = group[0][0]
        if any(name in ambiguous for name, _ in group):
            continue
        for name, _ in group:
            action_map[name] = canonical
        records.append(
            {
                "raw_action_names": [name for name, _ in group],
                "canonical_action_name": canonical,
                "confidence": "high",
            }
        )
    return action_map, records, ambiguous


def _outgoing_edges(graph: WebKobeGraph) -> dict[str, list[WebKobeEdge]]:
    outgoing: dict[str, list[WebKobeEdge]] = {node.node_id: [] for node in graph.nodes}
    for edge in graph.edges:
        outgoing.setdefault(edge.source_node_id, []).append(edge)
    return outgoing


def _frontier_state(
    node: WebKobeNode,
    *,
    outgoing: dict[str, list[WebKobeEdge]],
    action_map: dict[str, str],
    known_node_ids: set[str],
) -> tuple[bool, list[str], tuple[str, ...]]:
    edges = outgoing.get(node.node_id, [])
    affordance_actions = [
        action_map.get(_affordance_action_name(affordance), _affordance_action_name(affordance))
        for affordance in node.business_affordances
    ]
    edge_actions = [
        action_map.get(_edge_action_name(edge), _edge_action_name(edge))
        for edge in edges
    ]
    reasons: list[str] = []
    if any(edge.target_node_id not in known_node_ids for edge in edges):
        reasons.append("missing_target_node")
    if any(
        not edge.execution_trace.success or edge.status in _FAILED_STATUSES
        for edge in edges
    ):
        reasons.append("failed_execution")
    edge_action_set = set(edge_actions)
    if any(action not in edge_action_set for action in affordance_actions):
        reasons.append("frontier_incomplete")
    actions = tuple(sorted(set(affordance_actions) | set(edge_actions)))
    return not reasons, reasons, actions


def _initial_groups(
    nodes: list[WebKobeNode],
    *,
    eligible: dict[str, bool],
    action_sets: dict[str, tuple[str, ...]],
) -> list[list[str]]:
    groups: list[list[str]] = []
    keys: dict[tuple[Any, ...], int] = {}
    for node in nodes:
        if not eligible[node.node_id]:
            key = ("rejected", node.node_id)
        else:
            key = ("eligible", action_sets[node.node_id])
        group_index = keys.get(key)
        if group_index is None:
            group_index = len(groups)
            keys[key] = group_index
            groups.append([])
        groups[group_index].append(node.node_id)
    return groups


def _refine_groups(
    groups: list[list[str]],
    *,
    nodes: list[WebKobeNode],
    eligible: dict[str, bool],
    action_sets: dict[str, tuple[str, ...]],
    outgoing: dict[str, list[WebKobeEdge]],
    action_map: dict[str, str],
) -> list[list[str]]:
    group_for_node = {
        node_id: group[0] for group in groups for node_id in group
    }
    new_groups: list[list[str]] = []
    keys: dict[tuple[Any, ...], int] = {}
    for node in nodes:
        node_id = node.node_id
        if not eligible[node_id]:
            key = ("rejected", node_id)
        else:
            targets_by_action: dict[str, set[str]] = {}
            for edge in outgoing.get(node_id, []):
                action = action_map.get(_edge_action_name(edge), _edge_action_name(edge))
                targets_by_action.setdefault(action, set()).add(
                    group_for_node[edge.target_node_id]
                )
            transition_signature = tuple(
                (action, tuple(sorted(targets)))
                for action, targets in sorted(targets_by_action.items())
            )
            key = ("eligible", action_sets[node_id], transition_signature)
        group_index = keys.get(key)
        if group_index is None:
            group_index = len(new_groups)
            keys[key] = group_index
            new_groups.append([])
        new_groups[group_index].append(node_id)
    return new_groups


def _canonical_affordances(
    affordances: list[BusinessAffordance],
    action_map: dict[str, str],
) -> list[BusinessAffordance]:
    return [
        replace(
            affordance,
            action_name=action_map.get(
                _affordance_action_name(affordance), _affordance_action_name(affordance)
            ),
        )
        for affordance in affordances
    ]


def consolidate_behavior_state_graph(
    graph: WebKobeGraph,
    *,
    embedding_provider: EmbeddingProvider | None = None,
) -> BehaviorStateGraphArtifacts:
    nodes = list(graph.nodes)
    node_ids = {node.node_id for node in nodes}
    action_map, normalization_records, ambiguous_actions = _build_action_normalization(
        graph,
        embedding_provider=embedding_provider,
    )
    outgoing = _outgoing_edges(graph)
    eligible: dict[str, bool] = {}
    rejected_nodes: dict[str, list[str]] = {}
    action_sets: dict[str, tuple[str, ...]] = {}
    for node in nodes:
        is_eligible, reasons, actions = _frontier_state(
            node,
            outgoing=outgoing,
            action_map=action_map,
            known_node_ids=node_ids,
        )
        eligible[node.node_id] = is_eligible
        action_sets[node.node_id] = actions
        if reasons:
            rejected_nodes[node.node_id] = reasons

    groups = _initial_groups(
        nodes,
        eligible=eligible,
        action_sets=action_sets,
    )
    while True:
        refined = _refine_groups(
            groups,
            nodes=nodes,
            eligible=eligible,
            action_sets=action_sets,
            outgoing=outgoing,
            action_map=action_map,
        )
        if refined == groups:
            break
        groups = refined

    raw_to_canonical_node = {
        node_id: group[0] for group in groups for node_id in group
    }
    canonical_nodes: list[WebKobeNode] = []
    canonical_node_groups: list[dict[str, Any]] = []
    for group in groups:
        representative = next(node for node in nodes if node.node_id == group[0])
        canonical_nodes.append(
            replace(
                representative,
                business_affordances=_canonical_affordances(
                    representative.business_affordances,
                    action_map,
                ),
            )
        )
        canonical_node_groups.append(
            {
                "canonical_node_id": group[0],
                "raw_node_ids": list(group),
                "merge_eligible": all(eligible[node_id] for node_id in group),
            }
        )

    canonical_edges: list[WebKobeEdge] = []
    edge_keys: dict[tuple[str, str, str], int] = {}
    edge_mappings: list[dict[str, Any]] = []
    for edge in graph.edges:
        canonical_action = action_map.get(_edge_action_name(edge), _edge_action_name(edge))
        canonical_edge = replace(
            edge,
            source_node_id=raw_to_canonical_node.get(
                edge.source_node_id, edge.source_node_id
            ),
            target_node_id=raw_to_canonical_node.get(
                edge.target_node_id, edge.target_node_id
            ),
            action=replace(edge.action, canonical_action_name=canonical_action),
        )
        key = (
            canonical_edge.source_node_id,
            canonical_action,
            canonical_edge.target_node_id,
        )
        canonical_index = edge_keys.get(key)
        if canonical_index is None:
            edge_keys[key] = len(canonical_edges)
            canonical_edges.append(canonical_edge)
            collapsed = False
        else:
            existing = canonical_edges[canonical_index]
            canonical_edges[canonical_index] = replace(
                existing,
                visit_count=existing.visit_count + canonical_edge.visit_count,
                evidence=list(dict.fromkeys(existing.evidence + canonical_edge.evidence)),
            )
            collapsed = True
        edge_mappings.append(
            {
                "raw_edge_id": edge.edge_id,
                "canonical_edge_id": canonical_edge.edge_id,
                "canonical_source_node_id": canonical_edge.source_node_id,
                "canonical_target_node_id": canonical_edge.target_node_id,
                "canonical_action_name": canonical_action,
                "collapsed_into_existing_edge": collapsed,
            }
        )

    canonical_graph = replace(
        graph,
        start_node_id=raw_to_canonical_node.get(graph.start_node_id, graph.start_node_id),
        nodes=canonical_nodes,
        edges=canonical_edges,
        meta={
            **graph.meta,
            "artifact": "canonical_behavior_state_graph",
            "source_schema_version": graph.to_dict()["meta"].get("schema_version"),
        },
    )
    report = ConsolidationReport(
        action_normalizations=normalization_records,
        canonical_node_groups=canonical_node_groups,
        raw_to_canonical_node=raw_to_canonical_node,
        rejected_nodes=rejected_nodes,
        edge_mappings=edge_mappings,
        ambiguous_actions=ambiguous_actions,
    )
    return BehaviorStateGraphArtifacts(
        raw_graph=graph,
        canonical_graph=canonical_graph,
        report=report,
    )


__all__ = [
    "BehaviorStateGraphArtifacts",
    "CONSOLIDATION_SCHEMA_VERSION",
    "ConsolidationReport",
    "consolidate_behavior_state_graph",
]
