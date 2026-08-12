from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ai_web_explorer.grounded_web.graph import WebKobeGraph


@dataclass(frozen=True)
class ActionAttemptKey:
    source_node_id: str
    action_id: str


@dataclass(frozen=True)
class ResumePolicy:
    retry_keys: frozenset[ActionAttemptKey] = frozenset()
    max_attempts: int = 2

    def __post_init__(self):
        if self.max_attempts < 2:
            raise ValueError("resume_action_max_attempts must be at least 2")


def _action_id(edge) -> str:
    return edge.action.canonical_action_name or edge.action.semantic_id


def _events(graph: WebKobeGraph):
    return graph.execution_events or graph.edges


def _matching_attempts(graph: WebKobeGraph, source_node_id: str, action_id: str):
    return [
        event
        for event in _events(graph)
        if event.source_node_id == source_node_id and _action_id(event) == action_id
    ]


def is_action_eligible(
    graph: WebKobeGraph,
    *,
    source_node_id: str,
    action_id: str,
    policy: ResumePolicy,
) -> bool:
    attempts = _matching_attempts(graph, source_node_id, action_id)
    inflight = graph.meta.get("inflight_action") or {}
    inflight_matches = (
        inflight.get("source_node_id") == source_node_id
        and inflight.get("action_id") == action_id
    )
    if inflight_matches:
        attempts = attempts + [None]
    if not attempts:
        return True
    if any(event is not None and event.status != "failed_execution" for event in attempts):
        return False
    key = ActionAttemptKey(source_node_id, action_id)
    if key not in policy.retry_keys:
        return False
    return len(attempts) < policy.max_attempts


def resolve_retry_keys(
    graph: WebKobeGraph,
    requested_action_ids: Iterable[str],
) -> frozenset[ActionAttemptKey]:
    requested = set(requested_action_ids)
    resolved: dict[str, ActionAttemptKey] = {}
    inflight = graph.meta.get("inflight_action") or {}
    if inflight.get("action_id") in requested and inflight.get("source_node_id"):
        resolved[inflight["action_id"]] = ActionAttemptKey(
            inflight["source_node_id"], inflight["action_id"]
        )
    for event in reversed(_events(graph)):
        action_id = _action_id(event)
        if action_id in requested and action_id not in resolved:
            if event.status == "failed_execution":
                resolved[action_id] = ActionAttemptKey(event.source_node_id, action_id)
    missing = sorted(requested - resolved.keys())
    if missing:
        raise ValueError(f"unknown_resume_retry_action: {missing[0]}")
    return frozenset(resolved.values())


def validate_resume_graph(graph: WebKobeGraph, *, app_name: str) -> None:
    if graph.app != app_name:
        raise ValueError("resume_app_mismatch")
    node_ids = {node.node_id for node in graph.nodes}
    if not graph.start_node_id or graph.start_node_id not in node_ids:
        raise ValueError("resume_start_node_missing")
    if any(
        edge.source_node_id not in node_ids or edge.target_node_id not in node_ids
        for edge in graph.edges
    ):
        raise ValueError("resume_dangling_edge")


def derive_resume_cursor(graph: WebKobeGraph) -> str:
    explicit = graph.meta.get("resume_cursor_node_id")
    node_ids = {node.node_id for node in graph.nodes}
    if explicit in node_ids:
        return explicit
    inflight = graph.meta.get("inflight_action") or {}
    if inflight.get("source_node_id") in node_ids:
        return inflight["source_node_id"]
    events = _events(graph)
    if events:
        event = events[-1]
        candidate = event.target_node_id if event.status != "failed_execution" else event.source_node_id
        if candidate in node_ids:
            return candidate
    return graph.start_node_id


def select_resume_frontier(
    graph: WebKobeGraph,
    *,
    policy: ResumePolicy,
    blocked_node_ids=(),
):
    from ai_web_explorer.grounded_web.frontier_replay import select_frontier, reachable_frontier_for_node

    eligible = lambda node_id, action_id: is_action_eligible(
        graph,
        source_node_id=node_id,
        action_id=action_id,
        policy=policy,
    )
    blocked = set(blocked_node_ids)
    cursor = derive_resume_cursor(graph)
    if cursor not in blocked:
        target = reachable_frontier_for_node(graph, cursor, action_eligible=eligible)
        if target is not None:
            return target
    seen_retry_sources: set[str] = set()
    inflight = graph.meta.get("inflight_action") or {}
    inflight_key = ActionAttemptKey(
        inflight.get("source_node_id", ""),
        inflight.get("action_id", ""),
    )
    ordered_retry_keys: list[ActionAttemptKey] = []
    if inflight_key in policy.retry_keys:
        ordered_retry_keys.append(inflight_key)
    for event in reversed(_events(graph)):
        key = ActionAttemptKey(event.source_node_id, _action_id(event))
        if key in policy.retry_keys and key not in ordered_retry_keys:
            ordered_retry_keys.append(key)
    for key in ordered_retry_keys:
        if key.source_node_id in blocked or key.source_node_id in seen_retry_sources:
            continue
        seen_retry_sources.add(key.source_node_id)
        if not is_action_eligible(
            graph,
            source_node_id=key.source_node_id,
            action_id=key.action_id,
            policy=policy,
        ):
            continue
        target = reachable_frontier_for_node(
            graph,
            key.source_node_id,
            action_eligible=eligible,
        )
        if target is not None:
            return target
    target = select_frontier(
        graph,
        blocked_node_ids=blocked,
        action_eligible=eligible,
    )
    if target is not None:
        return target
    return select_frontier(
        graph,
        blocked_node_ids=blocked,
        include_start=True,
        action_eligible=eligible,
    )
