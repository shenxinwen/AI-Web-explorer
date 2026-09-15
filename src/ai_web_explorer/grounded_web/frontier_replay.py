from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from typing import Any, Callable, Iterable, TYPE_CHECKING

from ai_web_explorer.grounded_web.graph import BrowserAction, WebKobeEdge, WebKobeGraph
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

REPLAY_MISMATCH_REASONS = frozenset(
    {
        "entry_state_mismatch",
        "target_state_mismatch",
        "target_semantic_location_mismatch",
        "target_semantic_location_not_allowed",
        "target_business_facts_mismatch",
        "target_business_facts_unknown",
    }
)


def is_replay_mismatch_reason(reason: str) -> bool:
    return reason in REPLAY_MISMATCH_REASONS


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
    attempted_steps: int = 0
    reset_attempted_steps: int = 0

    @property
    def gui_action_attempts(self) -> int:
        return self.reset_attempted_steps + self.attempted_steps


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
            return ReplayResult(
                False,
                None,
                None,
                "entry_reset_failed",
                0,
                reset_attempted_steps=1,
            )

        completed_steps = 0
        attempted_steps = 0
        for step in target.path:
            attempted_steps += 1
            if not await self.explorer.execute_replay_action(step.edge.action):
                return ReplayResult(
                    False,
                    None,
                    step.edge_id,
                    "replay_action_failed",
                    completed_steps,
                    attempted_steps,
                    reset_attempted_steps=1,
                )
            completed_steps += 1

        validate_target = getattr(
            self.explorer,
            "validate_replay_target",
            None,
        )
        if validate_target is not None and not await validate_target(target.node_id):
            return ReplayResult(
                False,
                None,
                None,
                "target_state_mismatch",
                completed_steps,
                attempted_steps,
                reset_attempted_steps=1,
            )

        # Restore context only after the observed target identity is confirmed.
        restore_context = getattr(
            self.explorer, "restore_replay_context", None
        )
        if restore_context is not None:
            restore_context(target.node_id)
        else:
            self.explorer._set_current_node(target.node_id)
        return ReplayResult(
            True,
            target.node_id,
            None,
            "replay_succeeded",
            completed_steps,
            attempted_steps,
            reset_attempted_steps=1,
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
                    path=_replay_path_with_requirements(
                        _path_to(node_id, parent),
                        graph=graph,
                        memory=location_memory,
                    ),
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
    location_memory = _location_memory(graph)
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
                action_id
                for action_id in _location_candidate_action_ids(
                    target_node, location_memory
                )
                if (
                    action_id not in tried
                    or action_eligible(node_id, action_id)
                )
                and action_eligible(node_id, action_id)
            )
            if candidates:
                return FrontierTarget(
                    node_id,
                    _replay_path_with_requirements(
                        _path_to(node_id, parent),
                        graph=graph,
                        memory=location_memory,
                    ),
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


def _replay_path_with_requirements(
    path: tuple[ReplayStep, ...],
    *,
    graph: WebKobeGraph,
    memory: LocationExplorationMemory | None,
) -> tuple[ReplayStep, ...]:
    """Insert completed same-location requirements before replay actions."""

    if memory is None:
        return path
    nodes_by_id = {node.node_id: node for node in graph.nodes}
    successful_edges_by_location_action: dict[
        tuple[str, str], list[WebKobeEdge]
    ] = {}
    for edge in graph.edges:
        source = nodes_by_id.get(edge.source_node_id)
        location_id = normalize_semantic_id(
            getattr(source, "semantic_location_hint", "") or ""
        )
        action_id = normalize_semantic_id(_edge_action_id(edge))
        if (
            not location_id
            or not action_id
            or edge.status not in REPLAYABLE_EDGE_STATUSES
            or not edge.execution_trace.success
            or edge.execution_trace.metadata.get("replay_validation_status")
            == "unstable"
        ):
            continue
        successful_edges_by_location_action.setdefault(
            (location_id, action_id), []
        ).append(edge)
    for edges in successful_edges_by_location_action.values():
        edges.sort(key=lambda edge: edge.edge_id)

    expanded: list[ReplayStep] = []
    emitted: set[tuple[str, str]] = set()
    expanding: set[tuple[str, str]] = set()

    def append_action(location_id: str, action_id: str, edge: WebKobeEdge) -> None:
        key = (location_id, action_id)
        if key in emitted or key in expanding:
            return
        expanding.add(key)
        pool = memory.locations.get(location_id)
        record = pool.candidates.get(action_id) if pool is not None else None
        for requirement in record.requires if record is not None else ():
            requirement_id = normalize_semantic_id(requirement)
            requirement_record = (
                pool.candidates.get(requirement_id) if pool is not None else None
            )
            requirement_edges = successful_edges_by_location_action.get(
                (location_id, requirement_id), []
            )
            if (
                requirement_record is not None
                and requirement_record.status == "success"
                and requirement_edges
            ):
                append_action(
                    location_id,
                    requirement_id,
                    requirement_edges[0],
                )
        expanding.remove(key)
        if key in emitted:
            return
        replay_edge = _edge_with_memory_action(edge, record)
        expanded.append(
            ReplayStep(
                edge_id=replay_edge.edge_id,
                source_node_id=replay_edge.source_node_id,
                target_node_id=replay_edge.target_node_id,
                edge=replay_edge,
            )
        )
        emitted.add(key)

    for step in path:
        source = nodes_by_id.get(step.source_node_id)
        target = nodes_by_id.get(step.target_node_id)
        location_id = normalize_semantic_id(
            getattr(source, "semantic_location_hint", "") or ""
        )
        target_location_id = normalize_semantic_id(
            getattr(target, "semantic_location_hint", "") or ""
        )
        action_id = normalize_semantic_id(_edge_action_id(step.edge))
        if not location_id or not action_id:
            expanded.append(step)
            continue
        if target_location_id and target_location_id == location_id:
            continue
        append_action(location_id, action_id, step.edge)
    return tuple(expanded)


def _edge_with_memory_action(edge: WebKobeEdge, record) -> WebKobeEdge:
    if record is None:
        return edge
    affordance = record.affordance
    label = (
        affordance.label
        or affordance.action_name.replace("_", " ").capitalize()
    ).strip()
    if label and label[-1] not in ".!?":
        label += "."
    details = [label]
    if affordance.target_hint:
        target = affordance.target_hint.strip().rstrip(".")
        details.append(f"Target: {target}.")
    return replace(
        edge,
        action=BrowserAction(
            action_kind="business_intent",
            locator=None,
            semantic_id=affordance.action_name,
            input_values={},
            description=" ".join(details),
            action_label=(
                affordance.label
                or affordance.action_name.replace("_", " ").title()
            ),
            canonical_action_name=affordance.action_name,
            naming_provenance={
                "source": "business_affordance",
                "affordance_source": affordance.source,
                "confidence": affordance.confidence,
            },
            supporting_facts=list(affordance.supporting_facts),
            execution_policy=affordance.execution_policy,
            expected_outcome=affordance.expected_outcome,
        ),
    )


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
    del action_ids
    planning_state = getattr(node, "planning_state", None)
    if planning_state is None:
        return ()
    profile_fact_ids = {
        normalize_semantic_id(fact)
        for fact in planning_state.profile_fact_ids
        if normalize_semantic_id(fact)
    }
    return tuple(
        dict.fromkeys(
            normalize_semantic_id(fact)
            for fact in planning_state.active_facts
            if normalize_semantic_id(fact) in profile_fact_ids
        )
    )


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
