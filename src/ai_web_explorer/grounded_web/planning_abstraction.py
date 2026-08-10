from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

from ai_web_explorer.grounded_web.business_profile import PlanningDelta
from ai_web_explorer.grounded_web.graph import (
    BusinessAffordance,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.state_embedding import (
    EmbeddingProvider,
    cosine_similarity,
)


PLANNING_ABSTRACTION_SCHEMA_VERSION = "web-kobe-planning-state-v1"
ACTION_SAME_THRESHOLD = 0.90
ACTION_AMBIGUOUS_THRESHOLD = 0.82


@dataclass(frozen=True)
class PlanningAbstractionReport:
    raw_to_planning_node: dict[str, str]
    planning_node_groups: list[dict[str, Any]]
    capabilities: list[dict[str, Any]]
    edge_mappings: list[dict[str, Any]]
    ambiguous_actions: list[str]
    schema_version: str = PLANNING_ABSTRACTION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "raw_to_planning_node": dict(self.raw_to_planning_node),
            "planning_node_groups": [dict(item) for item in self.planning_node_groups],
            "capabilities": [dict(item) for item in self.capabilities],
            "edge_mappings": [dict(item) for item in self.edge_mappings],
            "ambiguous_actions": list(self.ambiguous_actions),
        }


@dataclass(frozen=True)
class PlanningAbstractionArtifacts:
    raw_graph: WebKobeGraph
    planning_graph: WebKobeGraph
    report: PlanningAbstractionReport


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")


def _affordance_action_name(affordance: BusinessAffordance) -> str:
    raw_name = affordance.action_name.strip()
    return _slug(raw_name) or raw_name


def _edge_action_name(edge: WebKobeEdge) -> str:
    raw_name = edge.action.canonical_action_name or edge.action.semantic_id
    return _slug(raw_name) or raw_name.strip()


def _affordance_text(affordance: BusinessAffordance, name: str) -> str:
    return "\n".join(
        [
            f"intent: {name}",
            f"label: {affordance.label or ''}",
            f"target_hint: {affordance.target_hint or ''}",
        ]
    )


def _edge_text(edge: WebKobeEdge, name: str) -> str:
    return "\n".join(
        [
            f"intent: {name}",
            f"label: {edge.action.action_label or ''}",
            "target_hint: ",
        ]
    )


def _action_descriptors(graph: WebKobeGraph) -> list[tuple[str, str]]:
    descriptors: list[tuple[str, str]] = []
    seen: set[str] = set()
    for node in graph.nodes:
        for affordance in node.business_affordances:
            name = _affordance_action_name(affordance)
            if name and name not in seen:
                seen.add(name)
                descriptors.append((name, _affordance_text(affordance, name)))
    for edge in graph.edges:
        name = _edge_action_name(edge)
        if name and name not in seen:
            seen.add(name)
            descriptors.append((name, _edge_text(edge, name)))
    return descriptors


def _action_normalization(
    graph: WebKobeGraph,
    embedding_provider: EmbeddingProvider | None,
) -> tuple[dict[str, str], list[str]]:
    descriptors = _action_descriptors(graph)
    action_map = {name: name for name, _ in descriptors}
    if embedding_provider is None:
        return action_map, []
    try:
        embeddings = [
            (name, list(embedding_provider(text)))
            for name, text in descriptors
        ]
    except Exception:
        return action_map, []

    groups: list[list[tuple[str, list[float]]]] = []
    ambiguous: list[str] = []
    for name, embedding in embeddings:
        compatible: list[list[tuple[str, list[float]]]] = []
        near: list[list[tuple[str, list[float]]]] = []
        for group in groups:
            scores = [
                cosine_similarity(embedding, member_embedding)
                for _, member_embedding in group
            ]
            if scores and min(scores) >= ACTION_SAME_THRESHOLD:
                compatible.append(group)
            elif scores and max(scores) >= ACTION_AMBIGUOUS_THRESHOLD:
                near.append(group)
        if len(compatible) == 1 and not near:
            compatible[0].append((name, embedding))
            continue
        if compatible or near:
            for group in compatible + near:
                for member_name, _ in group:
                    if member_name not in ambiguous:
                        ambiguous.append(member_name)
            if name not in ambiguous:
                ambiguous.append(name)
        groups.append([(name, embedding)])

    for group in groups:
        if len(group) < 2 or any(name in ambiguous for name, _ in group):
            continue
        canonical = group[0][0]
        for name, _ in group:
            action_map[name] = canonical
    return action_map, ambiguous


class _UnionFind:
    def __init__(self, values: list[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            parent = self.find(parent)
            self.parent[value] = parent
        return parent

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _can_share_planning_state(edge: WebKobeEdge) -> tuple[bool, str]:
    if not edge.execution_trace.success or edge.status == "failed_execution":
        return False, "failed_execution"
    delta = edge.planning_delta
    profile_boundary_changed = bool(
        delta
        and (delta.verified_added_facts or delta.verified_removed_facts)
    )
    if profile_boundary_changed:
        return False, "verified_profile_boundary_changed"
    if edge.visual_change_kind == "presentation":
        return True, "presentation_only"
    if (
        edge.visual_change_kind == "state_indicator"
        and delta is not None
        and delta.preserved_profile_facts
    ):
        return True, "verified_profile_abstraction_preserved"
    return False, "insufficient_equivalence_evidence"


def _groups(
    graph: WebKobeGraph,
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    node_ids = [node.node_id for node in graph.nodes]
    node_set = set(node_ids)
    union_find = _UnionFind(node_ids)
    for edge in graph.edges:
        if edge.source_node_id not in node_set or edge.target_node_id not in node_set:
            continue
        allowed, _ = _can_share_planning_state(edge)
        if allowed:
            union_find.union(edge.source_node_id, edge.target_node_id)

    members_by_root: dict[str, list[str]] = {}
    for node_id in node_ids:
        members_by_root.setdefault(union_find.find(node_id), []).append(node_id)
    raw_to_planning = {
        node_id: members[0]
        for members in members_by_root.values()
        for node_id in members
    }
    groups = [
        {
            "planning_node_id": members[0],
            "raw_node_ids": list(members),
        }
        for members in members_by_root.values()
    ]
    return raw_to_planning, groups


def _aggregate_capabilities(
    graph: WebKobeGraph,
    raw_to_planning: dict[str, str],
    action_map: dict[str, str],
) -> tuple[dict[str, list[BusinessAffordance]], list[dict[str, Any]]]:
    affordances_by_group: dict[str, list[BusinessAffordance]] = {}
    records: dict[tuple[str, str], dict[str, Any]] = {}

    def record(group_id: str, action: str, source_name: str, node_id: str) -> None:
        key = (group_id, action)
        item = records.setdefault(
            key,
            {
                "planning_node_id": group_id,
                "action_name": action,
                "observed_node_ids": [],
                "source_action_names": [],
            },
        )
        if node_id not in item["observed_node_ids"]:
            item["observed_node_ids"].append(node_id)
        if source_name not in item["source_action_names"]:
            item["source_action_names"].append(source_name)

    for node in graph.nodes:
        group_id = raw_to_planning[node.node_id]
        group_affordances = affordances_by_group.setdefault(group_id, [])
        existing_names = {item.action_name for item in group_affordances}
        for affordance in node.business_affordances:
            source_name = _affordance_action_name(affordance)
            canonical = action_map.get(source_name, source_name)
            record(group_id, canonical, source_name, node.node_id)
            if canonical not in existing_names:
                group_affordances.append(replace(affordance, action_name=canonical))
                existing_names.add(canonical)

    for edge in graph.edges:
        group_id = raw_to_planning.get(edge.source_node_id)
        if group_id is None:
            continue
        source_name = _edge_action_name(edge)
        record(group_id, action_map.get(source_name, source_name), source_name, edge.source_node_id)
    return affordances_by_group, list(records.values())


def build_planning_state_graph(
    graph: WebKobeGraph,
    *,
    embedding_provider: EmbeddingProvider | None = None,
) -> PlanningAbstractionArtifacts:
    action_map, ambiguous_actions = _action_normalization(graph, embedding_provider)
    raw_to_planning, group_records = _groups(graph)
    affordances_by_group, capabilities = _aggregate_capabilities(
        graph, raw_to_planning, action_map
    )
    nodes_by_id = {node.node_id: node for node in graph.nodes}
    planning_nodes = [
        replace(
            nodes_by_id[group["raw_node_ids"][0]],
            node_id=group["planning_node_id"],
            business_affordances=affordances_by_group.get(
                group["planning_node_id"], []
            ),
        )
        for group in group_records
    ]

    planning_edges: list[WebKobeEdge] = []
    edge_indexes: dict[tuple[str, str, str], int] = {}
    edge_mappings: list[dict[str, Any]] = []
    for edge in graph.edges:
        source = raw_to_planning.get(edge.source_node_id, edge.source_node_id)
        target = raw_to_planning.get(edge.target_node_id, edge.target_node_id)
        raw_action = _edge_action_name(edge)
        canonical_action = action_map.get(raw_action, raw_action)
        mapped = replace(
            edge,
            source_node_id=source,
            target_node_id=target,
            action=replace(edge.action, canonical_action_name=canonical_action),
        )
        key = (source, canonical_action, target)
        existing_index = edge_indexes.get(key)
        if existing_index is None:
            edge_indexes[key] = len(planning_edges)
            planning_edges.append(mapped)
            collapsed = False
        else:
            existing = planning_edges[existing_index]
            planning_edges[existing_index] = replace(
                existing,
                visit_count=existing.visit_count + mapped.visit_count,
                evidence=list(dict.fromkeys(existing.evidence + mapped.evidence)),
            )
            collapsed = True
        edge_mappings.append(
            {
                "raw_edge_id": edge.edge_id,
                "planning_edge_id": mapped.edge_id,
                "planning_source_node_id": source,
                "planning_target_node_id": target,
                "canonical_action_name": canonical_action,
                "collapsed_into_existing_edge": collapsed,
            }
        )

    planning_graph = replace(
        graph,
        start_node_id=raw_to_planning.get(graph.start_node_id, graph.start_node_id),
        nodes=planning_nodes,
        edges=planning_edges,
        meta={
            **graph.meta,
            "artifact": "planning_state_graph",
            "source_schema_version": graph.to_dict()["meta"].get("schema_version"),
        },
    )
    report = PlanningAbstractionReport(
        raw_to_planning_node=raw_to_planning,
        planning_node_groups=group_records,
        capabilities=capabilities,
        edge_mappings=edge_mappings,
        ambiguous_actions=ambiguous_actions,
    )
    return PlanningAbstractionArtifacts(
        raw_graph=graph,
        planning_graph=planning_graph,
        report=report,
    )


__all__ = [
    "PLANNING_ABSTRACTION_SCHEMA_VERSION",
    "PlanningAbstractionArtifacts",
    "PlanningAbstractionReport",
    "build_planning_state_graph",
]
