from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Iterable, TYPE_CHECKING

from ai_web_explorer.grounded_web.graph import WebKobeEdge, WebKobeGraph
from ai_web_explorer.grounded_web.location_exploration import (
    LOCATION_EXPLORATION_META_KEY,
    LocationExplorationMemory,
)
from ai_web_explorer.grounded_web.semantic_model import normalize_semantic_id

if TYPE_CHECKING:
    from ai_web_explorer.grounded_web.explorer import WebKobeExplorer


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
    semantic_location: str | None = None
    required_business_facts: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReplayResult:
    success: bool
    reached_node_id: str | None
    failed_edge_id: str | None
    reason: str
    completed_steps: int


class FrontierReplayRunner:
    def __init__(self, explorer: "WebKobeExplorer"):
        self.explorer = explorer

    async def replay(
        self,
        target: Any,
        *,
        start_url: str,
    ) -> ReplayResult:
        start_node_id = self.explorer.start_node_id
        if start_node_id is None:
            return ReplayResult(False, None, None, "entry_state_unavailable", 0)
        if not await self.explorer.adapter.reset_to(start_url):
            return ReplayResult(False, None, None, "entry_reset_failed", 0)
        if not await self.explorer.validate_current_node(start_node_id):
            return ReplayResult(False, None, None, "entry_state_mismatch", 0)

        completed_steps = 0
        for step in target.path:
            if not await self.explorer.execute_replay_action(step.edge.action):
                return ReplayResult(
                    False,
                    None,
                    step.edge_id,
                    "replay_action_failed",
                    completed_steps,
                )
            if not await self.explorer.validate_current_node(step.target_node_id):
                return ReplayResult(
                    False,
                    None,
                    step.edge_id,
                    "target_state_mismatch",
                    completed_steps,
                )
            completed_steps += 1
        if not await self.explorer.validate_current_node(
            target.node_id,
            expected_semantic_location=getattr(target, "semantic_location", None),
            expected_business_facts=getattr(target, "required_business_facts", ()),
        ):
            return ReplayResult(
                False,
                None,
                None,
                "target_business_facts_mismatch"
                if getattr(target, "required_business_facts", ())
                else "target_state_mismatch",
                completed_steps,
            )
        return ReplayResult(
            True,
            target.node_id,
            None,
            "replay_succeeded",
            completed_steps,
        )

def select_frontier(
    graph: WebKobeGraph,
    *,
    blocked_node_ids: Iterable[str] = (),
    include_start: bool = False,
    action_eligible: Callable[[str, str], bool] | None = None,
) -> FrontierTarget | None:
    """Select the nearest reachable node that still has an untried candidate.

    The entry node is excluded by default because it is the reset state, not a
    replay frontier.  ``include_start`` is an explicit escape hatch for callers
    that intentionally want to replay an entry-state candidate.
    """

    blocked = set(blocked_node_ids)
    nodes_by_id = {node.node_id: node for node in graph.nodes}
    location_memory = _location_memory(graph)
    adjacency: dict[str, list[WebKobeEdge]] = {}
    for edge in graph.edges:
        if (
            edge.status not in REPLAYABLE_EDGE_STATUSES
            or not edge.execution_trace.success
            or edge.execution_trace.metadata.get("replay_validation_status")
            == "unstable"
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

    queue = deque([graph.start_node_id])
    parent: dict[str, tuple[str, WebKobeEdge] | None] = {
        graph.start_node_id: None
    }
    while queue:
        node_id = queue.popleft()
        node = nodes_by_id.get(node_id)
        if (
            node is not None
            and (include_start or node_id != graph.start_node_id)
            and node_id not in blocked
        ):
            candidates = _location_candidate_action_ids(node, location_memory)
            untried = tuple(
                action_id
                for action_id in candidates
                if (
                    action_id not in tried_by_source.get(node_id, set())
                    or _location_action_is_pending(
                        node, action_id, location_memory
                    )
                    or (action_eligible is not None and action_eligible(node_id, action_id))
                )
                and (
                    action_eligible is None
                    or action_eligible(node_id, action_id)
                )
            )
            if untried:
                return FrontierTarget(
                    node_id=node_id,
                    path=_path_to(node_id, parent),
                    untried_action_ids=untried,
                    semantic_location=_node_semantic_location(node),
                    required_business_facts=_required_facts_for_candidates(
                        node, untried
                    ),
                )

        for edge in adjacency.get(node_id, []):
            if edge.target_node_id in parent:
                continue
            parent[edge.target_node_id] = (node_id, edge)
            queue.append(edge.target_node_id)
    return None


def reachable_frontier_for_node(
    graph: WebKobeGraph,
    node_id: str,
    *,
    action_eligible: Callable[[str, str], bool],
) -> FrontierTarget | None:
    target_node = next((node for node in graph.nodes if node.node_id == node_id), None)
    if target_node is None:
        return None
    nodes_by_id = {node.node_id: node for node in graph.nodes}
    adjacency: dict[str, list[WebKobeEdge]] = {}
    for edge in graph.edges:
        if (
            edge.status not in REPLAYABLE_EDGE_STATUSES
            or not edge.execution_trace.success
            or edge.execution_trace.metadata.get("replay_validation_status") == "unstable"
        ):
            continue
        if edge.source_node_id in nodes_by_id and edge.target_node_id in nodes_by_id:
            adjacency.setdefault(edge.source_node_id, []).append(edge)
    for edges in adjacency.values():
        edges.sort(key=lambda edge: edge.edge_id)
    parent: dict[str, tuple[str, WebKobeEdge] | None] = {graph.start_node_id: None}
    queue = deque([graph.start_node_id])
    while queue:
        current = queue.popleft()
        if current == node_id:
            tried = {_edge_action_id(edge) for edge in graph.edges if edge.source_node_id == node_id}
            candidates = tuple(
                action.action_name
                for action in target_node.business_affordances
                if (
                    action.action_name not in tried
                    or action_eligible(node_id, action.action_name)
                )
                and action_eligible(node_id, action.action_name)
            )
            if candidates:
                return FrontierTarget(
                    node_id,
                    _path_to(node_id, parent),
                    candidates,
                    semantic_location=_node_semantic_location(target_node),
                    required_business_facts=_required_facts_for_candidates(
                        target_node, candidates
                    ),
                )
            return None
        for edge in adjacency.get(current, []):
            if edge.target_node_id not in parent:
                parent[edge.target_node_id] = (current, edge)
                queue.append(edge.target_node_id)
    return None


def _path_to(
    node_id: str,
    parent: dict[str, tuple[str, WebKobeEdge] | None],
) -> tuple[ReplayStep, ...]:
    steps: list[ReplayStep] = []
    current = node_id
    while parent[current] is not None:
        source_node_id, edge = parent[current]
        steps.append(
            ReplayStep(
                edge_id=edge.edge_id,
                source_node_id=source_node_id,
                target_node_id=current,
                edge=edge,
            )
        )
        current = source_node_id
    steps.reverse()
    return tuple(steps)


def _candidate_action_ids(node) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            affordance.action_name
            for affordance in node.business_affordances
            if affordance.action_name
        )
    )


def _node_semantic_location(node) -> str | None:
    for value in (
        getattr(node, "semantic_location_hint", None),
        getattr(node, "node_label", None),
        getattr(getattr(node, "page_frame", None), "page_type", None),
    ):
        normalized = normalize_semantic_id(value) if value else ""
        if normalized:
            return normalized
    return None


def _required_facts_for_candidates(
    node,
    action_ids: Iterable[str],
) -> tuple[str, ...]:
    wanted = set(action_ids)
    facts: set[str] = set()
    for affordance in getattr(node, "business_affordances", ()):
        if affordance.action_name in wanted:
            facts.update(
                normalize_semantic_id(fact)
                for fact in affordance.supporting_facts
                if normalize_semantic_id(fact)
            )
    return tuple(sorted(facts))


def _location_memory(graph: WebKobeGraph) -> LocationExplorationMemory | None:
    payload = graph.meta.get(LOCATION_EXPLORATION_META_KEY)
    if not isinstance(payload, dict):
        return None
    try:
        return LocationExplorationMemory.from_dict(payload)
    except ValueError:
        return None


def _location_candidate_action_ids(
    node,
    memory: LocationExplorationMemory | None,
) -> tuple[str, ...]:
    location_id = normalize_semantic_id(node.semantic_location_hint or "")
    if memory is None or not location_id or location_id not in memory.locations:
        return _candidate_action_ids(node)
    pool = memory.pool_for(location_id)
    return tuple(
        action_id
        for action_id, record in sorted(
            pool.candidates.items(),
            key=lambda item: (item[1].discovery_order, item[0]),
        )
        if record.status
        in {"pending", "retryable_no_change", "retryable_failure"}
        and record.attempts < memory.limits.max_action_attempts_per_candidate
    )


def _location_action_is_pending(
    node,
    action_id: str,
    memory: LocationExplorationMemory | None,
) -> bool:
    if memory is None:
        return False
    location_id = normalize_semantic_id(node.semantic_location_hint or "")
    if not location_id or location_id not in memory.locations:
        return False
    record = memory.pool_for(location_id).candidates.get(normalize_semantic_id(action_id))
    return bool(
        record is not None
        and record.status
        in {"pending", "retryable_no_change", "retryable_failure"}
    )


def _edge_action_id(edge: WebKobeEdge) -> str:
    return edge.action.canonical_action_name or edge.action.semantic_id
