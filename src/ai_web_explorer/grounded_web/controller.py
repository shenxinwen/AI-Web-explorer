from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from ai_web_explorer.grounded_web.frontier_replay import (
    is_replay_mismatch_reason,
    select_frontier,
)
from ai_web_explorer.grounded_web.graph import WebKobeGraph
from ai_web_explorer.grounded_web.location_exploration import ExplorationLimits

SUCCESS_EDGE_STATUSES = frozenset(
    {
        "verified",
        "succeeded",
        "succeeded_with_observed_change",
        "succeeded_with_navigation",
        "no_observed_change",
    }
)

StepCheckpoint = Callable[[WebKobeGraph], None]
RUNTIME_BUDGET_META_KEY = "exploration_runtime_state"


@dataclass
class ExplorationRuntimeState:
    formal_action_attempts: int = 0
    consecutive_no_progress: int = 0
    semantic_progress_count: int = 0
    replay_attempt_count: int = 0
    replay_success_count: int = 0
    replay_failure_count: int = 0
    replay_mismatch_count: int = 0
    frontier_replay_attempts: dict[str, int] | None = None
    blocked_replay_node_ids: list[str] | None = None

    @classmethod
    def from_graph(cls, graph: WebKobeGraph | None) -> "ExplorationRuntimeState":
        if graph is None:
            return cls(frontier_replay_attempts={}, blocked_replay_node_ids=[])
        payload = graph.meta.get(RUNTIME_BUDGET_META_KEY)
        if not isinstance(payload, dict):
            payload = graph.meta
        return cls(
            formal_action_attempts=int(payload.get("formal_action_attempts", 0)),
            consecutive_no_progress=int(
                payload.get(
                    "consecutive_no_progress",
                    payload.get("consecutive_unproductive_steps", 0),
                )
            ),
            semantic_progress_count=int(payload.get("semantic_progress_count", 0)),
            replay_attempt_count=int(payload.get("replay_attempt_count", 0)),
            replay_success_count=int(payload.get("replay_success_count", 0)),
            replay_failure_count=int(payload.get("replay_failure_count", 0)),
            replay_mismatch_count=int(payload.get("replay_mismatch_count", 0)),
            frontier_replay_attempts={
                str(key): int(value)
                for key, value in (
                    payload.get("frontier_replay_attempts", {})
                    if isinstance(payload.get("frontier_replay_attempts", {}), dict)
                    else {}
                ).items()
            },
            blocked_replay_node_ids=[
                str(item)
                for item in (
                    payload.get("blocked_replay_node_ids", [])
                    if isinstance(payload.get("blocked_replay_node_ids", []), list)
                    else []
                )
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "formal_action_attempts": self.formal_action_attempts,
            "consecutive_no_progress": self.consecutive_no_progress,
            "semantic_progress_count": self.semantic_progress_count,
            "replay_attempt_count": self.replay_attempt_count,
            "replay_success_count": self.replay_success_count,
            "replay_failure_count": self.replay_failure_count,
            "replay_mismatch_count": self.replay_mismatch_count,
            "frontier_replay_attempts": dict(
                sorted((self.frontier_replay_attempts or {}).items())
            ),
            "blocked_replay_node_ids": sorted(self.blocked_replay_node_ids or []),
        }


class StepExplorer(Protocol):
    async def explore_one_step(self) -> WebKobeGraph: ...


class FrontierReplayRunner(Protocol):
    async def replay(self, target: Any, *, start_url: str) -> Any: ...


@dataclass(frozen=True)
class WebKobeExplorationSummary:
    requested_steps: int
    steps_completed: int
    stop_reason: str
    node_count: int
    edge_count: int
    failed_edge_count: int
    consecutive_unproductive_steps: int = 0
    max_consecutive_unproductive_steps: int | None = 3
    historical_steps: int = 0
    total_steps_completed: int = 0
    semantic_progress_count: int = 0
    replay_attempt_count: int = 0
    frontier_replay_attempts: dict[str, int] | None = None


@dataclass(frozen=True)
class WebKobeExplorationResult:
    graph: WebKobeGraph
    summary: WebKobeExplorationSummary


def _failed_edge_count(graph: WebKobeGraph) -> int:
    return sum(1 for edge in graph.edges if edge.status not in SUCCESS_EDGE_STATUSES)


def _summary(
    graph: WebKobeGraph,
    *,
    requested_steps: int,
    baseline_completed: int,
    stop_reason: str,
    consecutive_unproductive_steps: int = 0,
    max_consecutive_unproductive_steps: int | None = 3,
    historical_steps: int = 0,
    semantic_progress_count: int = 0,
    replay_attempt_count: int = 0,
    frontier_replay_attempts: dict[str, int] | None = None,
) -> WebKobeExplorationSummary:
    return WebKobeExplorationSummary(
        requested_steps=requested_steps,
        steps_completed=max(graph.total_steps_completed - baseline_completed, 0),
        stop_reason=stop_reason,
        node_count=len(graph.nodes),
        edge_count=len(graph.edges),
        failed_edge_count=_failed_edge_count(graph),
        consecutive_unproductive_steps=consecutive_unproductive_steps,
        max_consecutive_unproductive_steps=max_consecutive_unproductive_steps,
        historical_steps=historical_steps,
        total_steps_completed=graph.total_steps_completed,
        semantic_progress_count=semantic_progress_count,
        replay_attempt_count=replay_attempt_count,
        frontier_replay_attempts=frontier_replay_attempts,
    )


def _last_step_is_productive(graph: WebKobeGraph) -> bool:
    if "last_step_semantic_progress" in graph.meta:
        return graph.meta.get("last_step_semantic_progress") is True
    return graph.meta.get("last_step_graph_changed") is True


class WebKobeExplorationController:
    def __init__(
        self,
        explorer: StepExplorer,
        *,
        terminal_condition: Callable[[WebKobeGraph], bool] | None = None,
        max_consecutive_unproductive_steps: int | None = 3,
        step_checkpoint: StepCheckpoint | None = None,
        frontier_replay_runner: FrontierReplayRunner | None = None,
        start_url: str | None = None,
        replay_metric_baseline: Mapping[str, int] | None = None,
        historical_steps: int = 0,
        limits: ExplorationLimits | None = None,
        runtime_budget_state: Mapping[str, Any] | None = None,
    ):
        self.explorer = explorer
        self.terminal_condition = terminal_condition
        self.max_consecutive_unproductive_steps = (
            None
            if max_consecutive_unproductive_steps is None
            else max(max_consecutive_unproductive_steps, 1)
        )
        self.step_checkpoint = step_checkpoint
        self.frontier_replay_runner = frontier_replay_runner
        self.start_url = start_url
        self.replay_metric_baseline = dict(replay_metric_baseline or {})
        self.historical_steps = historical_steps
        self.limits = limits or ExplorationLimits()
        self._limits_explicit = limits is not None
        self.runtime_budget_state = dict(runtime_budget_state or {})

    def _initial_graph(self) -> WebKobeGraph | None:
        manager = getattr(self.explorer, "manager", None)
        to_graph = getattr(manager, "to_graph", None)
        if to_graph is None:
            return None
        try:
            return to_graph()
        except (AttributeError, TypeError):
            return None

    def _write_runtime_state(
        self,
        graph: WebKobeGraph,
        state: ExplorationRuntimeState,
    ) -> None:
        payload = state.to_dict()
        graph.meta[RUNTIME_BUDGET_META_KEY] = payload
        graph.meta.update(payload)

    async def run(self, *, max_steps: int | None = None) -> WebKobeExplorationResult:
        if max_steps is None:
            max_steps = (
                self.limits.max_exploration_steps
                if self._limits_explicit
                else 1
            )
        requested_steps = max(max_steps, 0)
        graph: WebKobeGraph | None = self._initial_graph()
        state = ExplorationRuntimeState.from_graph(graph)
        state_payload = self.runtime_budget_state
        if state_payload:
            state = ExplorationRuntimeState.from_graph(
                WebKobeGraph(
                    app="",
                    start_node_id="",
                    total_steps_completed=0,
                    meta=state_payload,
                )
            )
        baseline_completed = 0
        previous_completed = 0
        stop_reason = "max_steps"
        consecutive_unproductive_steps = state.consecutive_no_progress
        blocked_replay_node_ids: set[str] = set(state.blocked_replay_node_ids or [])
        frontier_replay_attempts: dict[str, int] = dict(
            state.frontier_replay_attempts or {}
        )
        semantic_progress_count = state.semantic_progress_count
        replay_metrics = {
            "replay_attempt_count": max(
                state.replay_attempt_count,
                int(self.replay_metric_baseline.get("replay_attempt_count", 0)),
            ),
            "replay_success_count": max(
                state.replay_success_count,
                int(self.replay_metric_baseline.get("replay_success_count", 0)),
            ),
            "replay_failure_count": max(
                state.replay_failure_count,
                int(self.replay_metric_baseline.get("replay_failure_count", 0)),
            ),
            "replay_mismatch_count": max(
                state.replay_mismatch_count,
                int(self.replay_metric_baseline.get("replay_mismatch_count", 0)),
            ),
            "last_replay_reason": None,
        }
        replay_attempt_history = list(
            (graph.meta if graph is not None else {}).get(
                "replay_attempt_history",
                [],
            )
        )
        replay_enabled = (
            self.frontier_replay_runner is not None and self.start_url is not None
        )

        available_formal_attempts = requested_steps
        if self._limits_explicit:
            available_formal_attempts = min(
                available_formal_attempts,
                max(self.limits.max_exploration_steps - state.formal_action_attempts, 0),
            )

        if self._limits_explicit and available_formal_attempts == 0:
            if graph is None:
                graph = WebKobeGraph(
                    app="",
                    start_node_id="",
                    total_steps_completed=state.formal_action_attempts,
                )
            for key in (
                "replay_attempt_count",
                "replay_success_count",
                "replay_failure_count",
                "replay_mismatch_count",
            ):
                setattr(state, key, int(replay_metrics[key]))
            self._write_runtime_state(graph, state)
            return WebKobeExplorationResult(
                graph=graph,
                summary=_summary(
                    graph,
                    requested_steps=requested_steps,
                    baseline_completed=graph.total_steps_completed,
                    stop_reason="max_exploration_steps_reached",
                    consecutive_unproductive_steps=consecutive_unproductive_steps,
                    max_consecutive_unproductive_steps=self.max_consecutive_unproductive_steps,
                    historical_steps=self.historical_steps,
                    semantic_progress_count=semantic_progress_count,
                    replay_attempt_count=int(replay_metrics["replay_attempt_count"]),
                    frontier_replay_attempts=dict(sorted(frontier_replay_attempts.items())),
                ),
            )

        def apply_replay_metrics(target_graph: WebKobeGraph) -> WebKobeGraph:
            if not replay_enabled:
                return target_graph
            target_graph.meta.update(replay_metrics)
            target_graph.meta["replay_attempt_history"] = list(
                replay_attempt_history
            )
            target_graph.meta["blocked_replay_node_ids"] = sorted(
                blocked_replay_node_ids
            )
            if self._limits_explicit:
                target_graph.meta["frontier_replay_attempts"] = dict(
                    sorted(frontier_replay_attempts.items())
                )
            return target_graph

        for index in range(available_formal_attempts):
            graph = await self.explorer.explore_one_step()
            state.formal_action_attempts = max(
                state.formal_action_attempts,
                int(graph.meta.get("formal_action_attempts", 0)),
                int(graph.total_steps_completed),
            )
            if index == 0 and self._limits_explicit:
                persisted_frontier_attempts = graph.meta.get(
                    "frontier_replay_attempts", {}
                )
                if isinstance(persisted_frontier_attempts, dict):
                    frontier_replay_attempts.update(
                        {
                            str(key): int(value)
                            for key, value in persisted_frontier_attempts.items()
                        }
                    )
                persisted_blocked = graph.meta.get("blocked_replay_node_ids", [])
                if isinstance(persisted_blocked, list):
                    blocked_replay_node_ids.update(str(item) for item in persisted_blocked)
                persisted_history = graph.meta.get("replay_attempt_history", [])
                if isinstance(persisted_history, list) and not replay_attempt_history:
                    replay_attempt_history.extend(persisted_history)
                persisted_replay_count = graph.meta.get("replay_attempt_count")
                if persisted_replay_count is not None:
                    replay_metrics["replay_attempt_count"] = max(
                        replay_metrics["replay_attempt_count"],
                        int(persisted_replay_count),
                    )
            apply_replay_metrics(graph)
            if index == 0 and self.historical_steps:
                baseline_completed = self.historical_steps
                previous_completed = self.historical_steps
            elif index == 0:
                baseline_completed = max(graph.total_steps_completed - 1, 0)
                previous_completed = baseline_completed

            while (
                graph.total_steps_completed == previous_completed
                and graph.meta.get("last_step_kind") == "current_state_exhausted"
                and self.frontier_replay_runner is not None
                and self.start_url is not None
            ):
                if self._limits_explicit and replay_metrics["replay_attempt_count"] >= self.limits.max_total_replays:
                    stop_reason = "total_replay_limit_reached"
                    break
                frontier = select_frontier(
                    graph,
                    blocked_node_ids=blocked_replay_node_ids,
                )
                if frontier is None:
                    frontier = select_frontier(
                        graph,
                        blocked_node_ids=blocked_replay_node_ids,
                        include_start=True,
                    )
                if frontier is None:
                    stop_reason = (
                        "no_recoverable_frontier"
                        if self._limits_explicit
                        else "frontier_replay_exhausted"
                    )
                    break
                frontier_key = str(frontier.node_id)
                if self._limits_explicit and frontier_replay_attempts.get(
                    frontier_key, 0
                ) >= self.limits.max_replay_attempts_per_frontier:
                    blocked_replay_node_ids.add(frontier_key)
                    apply_replay_metrics(graph)
                    continue
                replay_metrics["replay_attempt_count"] += 1
                frontier_replay_attempts[frontier_key] = (
                    frontier_replay_attempts.get(frontier_key, 0) + 1
                )
                apply_replay_metrics(graph)
                replay_result = await self.frontier_replay_runner.replay(
                    frontier,
                    start_url=self.start_url,
                )
                replay_attempt_history.append(
                    {
                        "attempt": int(replay_metrics["replay_attempt_count"]),
                        "target_node_id": frontier.node_id,
                        "path_edge_ids": [step.edge_id for step in frontier.path],
                        "success": bool(replay_result.success),
                        "reason": replay_result.reason,
                        "failed_edge_id": replay_result.failed_edge_id,
                        "completed_steps": int(replay_result.completed_steps),
                    }
                )
                replay_metrics["last_replay_reason"] = replay_result.reason
                if not replay_result.success:
                    replay_metrics["replay_failure_count"] += 1
                    if is_replay_mismatch_reason(replay_result.reason):
                        replay_metrics["replay_mismatch_count"] += 1
                    if (
                        not self._limits_explicit
                        or frontier_replay_attempts[frontier_key]
                        >= self.limits.max_replay_attempts_per_frontier
                    ):
                        blocked_replay_node_ids.add(frontier.node_id)
                    apply_replay_metrics(graph)
                    continue
                replay_metrics["replay_success_count"] += 1
                if (
                    self._limits_explicit
                    and state.formal_action_attempts
                    >= self.limits.max_exploration_steps
                ):
                    stop_reason = "max_exploration_steps_reached"
                    break
                next_graph = await self.explorer.explore_one_step()
                graph = apply_replay_metrics(next_graph)
                state.formal_action_attempts = max(
                    state.formal_action_attempts,
                    int(graph.meta.get("formal_action_attempts", 0)),
                    int(graph.total_steps_completed),
                )
                if (
                    graph.total_steps_completed == previous_completed
                    and graph.meta.get("last_step_kind") == "current_state_exhausted"
                ):
                    blocked_replay_node_ids.add(frontier.node_id)
                    apply_replay_metrics(graph)

            if graph.total_steps_completed == previous_completed:
                if stop_reason == "max_steps":
                    stop_reason = (
                        "current_state_exhausted"
                        if graph.meta.get("last_step_kind") == "current_state_exhausted"
                        else "no_available_action"
                    )
                break

            previous_completed = graph.total_steps_completed
            if _last_step_is_productive(graph):
                consecutive_unproductive_steps = 0
                semantic_progress_count += 1
            else:
                consecutive_unproductive_steps += 1
            graph.meta["consecutive_unproductive_steps"] = (
                consecutive_unproductive_steps
            )
            graph.meta["max_consecutive_unproductive_steps"] = (
                self.max_consecutive_unproductive_steps
            )
            apply_replay_metrics(graph)
            state.consecutive_no_progress = consecutive_unproductive_steps
            state.semantic_progress_count = semantic_progress_count
            state.replay_attempt_count = int(replay_metrics["replay_attempt_count"])
            state.replay_success_count = int(replay_metrics["replay_success_count"])
            state.replay_failure_count = int(replay_metrics["replay_failure_count"])
            state.replay_mismatch_count = int(replay_metrics["replay_mismatch_count"])
            state.frontier_replay_attempts = dict(frontier_replay_attempts)
            state.blocked_replay_node_ids = sorted(blocked_replay_node_ids)
            self._write_runtime_state(graph, state)
            if self.step_checkpoint is not None:
                self.step_checkpoint(graph)
            if (
                self.max_consecutive_unproductive_steps is not None
                and consecutive_unproductive_steps
                >= self.max_consecutive_unproductive_steps
            ):
                stop_reason = (
                    "consecutive_no_progress_limit_reached"
                    if self._limits_explicit
                    else "consecutive_unproductive_steps"
                )
                break
            if self.terminal_condition is not None and self.terminal_condition(graph):
                stop_reason = "terminal_condition"
                break

        if self._limits_explicit and stop_reason == "max_steps":
            stop_reason = "max_exploration_steps_reached"

        if graph is None:
            graph = WebKobeGraph(
                app="",
                start_node_id="",
                total_steps_completed=baseline_completed,
            )
        apply_replay_metrics(graph)
        state.consecutive_no_progress = consecutive_unproductive_steps
        state.semantic_progress_count = semantic_progress_count
        state.replay_attempt_count = int(replay_metrics["replay_attempt_count"])
        state.replay_success_count = int(replay_metrics["replay_success_count"])
        state.replay_failure_count = int(replay_metrics["replay_failure_count"])
        state.replay_mismatch_count = int(replay_metrics["replay_mismatch_count"])
        state.frontier_replay_attempts = dict(frontier_replay_attempts)
        state.blocked_replay_node_ids = sorted(blocked_replay_node_ids)
        self._write_runtime_state(graph, state)

        return WebKobeExplorationResult(
            graph=graph,
            summary=_summary(
                graph,
                requested_steps=requested_steps,
                baseline_completed=baseline_completed,
                stop_reason=stop_reason,
                consecutive_unproductive_steps=consecutive_unproductive_steps,
                max_consecutive_unproductive_steps=(
                    self.max_consecutive_unproductive_steps
                ),
                historical_steps=self.historical_steps,
                semantic_progress_count=semantic_progress_count,
                replay_attempt_count=int(replay_metrics["replay_attempt_count"]),
                frontier_replay_attempts=(
                    dict(sorted(frontier_replay_attempts.items()))
                    if self._limits_explicit
                    else None
                ),
            ),
        )
