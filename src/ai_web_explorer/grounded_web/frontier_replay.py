from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable

from ai_web_explorer.grounded_web.graph import WebKobeEdge, WebKobeGraph


REPLAYABLE_EDGE_STATUSES = frozenset(
    {
        "verified",
        "succeeded",
        "succeeded_with_observed_change",
        "succeeded_with_navigation",
        "no_observed_change",
    }
)


@dataclass(frozen=True)
class ReplayStep:
    edge_id: str
    source_node_id: str
    target_node_id: str
    edge: WebKobeEdge


@dataclass(frozen=True)
class FrontierTarget:
    node_id: str
    path: tuple[ReplayStep, ...]
    untried_action_ids: tuple[str, ...]


def select_frontier(
    graph: WebKobeGraph,
    *,
    blocked_node_ids: Iterable[str] = (),
) -> FrontierTarget | None:
    """Select the nearest reachable node that still has an untried candidate."""

    blocked = set(blocked_node_ids)
    nodes_by_id = {node.node_id: node for node in graph.nodes}
    adjacency: dict[str, list[WebKobeEdge]] = {}
    for edge in graph.edges:
        if (
            edge.status not in REPLAYABLE_EDGE_STATUSES
            or not edge.execution_trace.success
        ):
            continue
        if edge.source_node_id not in nodes_by_id or edge.target_node_id not in nodes_by_id:
            continue
        adjacency.setdefault(edge.source_node_id, []).append(edge)
    for edges in adjacency.values():
        edges.sort(key=lambda edge: edge.edge_id)

    tried_by_source: dict[str, set[str]] = {}
    for edge in graph.edges:
        tried_by_source.setdefault(edge.source_node_id, set()).add(
            _edge_action_id(edge)
        )

    queue = deque([(graph.start_node_id, tuple(), frozenset({graph.start_node_id}))])
    while queue:
        node_id, path, visited = queue.popleft()
        node = nodes_by_id.get(node_id)
        if node is not None and node_id not in blocked:
            candidates = _candidate_action_ids(node)
            untried = tuple(
                action_id
                for action_id in candidates
                if action_id not in tried_by_source.get(node_id, set())
            )
            if untried:
                return FrontierTarget(
                    node_id=node_id,
                    path=path,
                    untried_action_ids=untried,
                )

        for edge in adjacency.get(node_id, []):
            if edge.target_node_id in visited:
                continue
            step = ReplayStep(
                edge_id=edge.edge_id,
                source_node_id=edge.source_node_id,
                target_node_id=edge.target_node_id,
                edge=edge,
            )
            queue.append(
                (
                    edge.target_node_id,
                    path + (step,),
                    visited | {edge.target_node_id},
                )
            )
    return None


def _candidate_action_ids(node) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            affordance.action_name
            for affordance in node.business_affordances
            if affordance.action_name
        )
    )


def _edge_action_id(edge: WebKobeEdge) -> str:
    return edge.action.canonical_action_name or edge.action.semantic_id
