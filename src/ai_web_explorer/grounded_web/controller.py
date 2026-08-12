from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from ai_web_explorer.grounded_web.frontier_replay import select_frontier
from ai_web_explorer.grounded_web.graph import WebKobeGraph

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
    )


def _last_step_is_productive(graph: WebKobeGraph) -> bool:
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

    async def run(self, *, max_steps: int = 1) -> WebKobeExplorationResult:
        requested_steps = max(max_steps, 0)
        graph: WebKobeGraph | None = None
        baseline_completed = 0
        previous_completed = 0
        stop_reason = "max_steps"
        consecutive_unproductive_steps = 0
        blocked_replay_node_ids: set[str] = set()
        replay_metrics = {
            "replay_attempt_count": 0,
            "replay_success_count": 0,
            "replay_failure_count": 0,
            "replay_mismatch_count": 0,
            "last_replay_reason": None,
        }
        replay_enabled = (
            self.frontier_replay_runner is not None and self.start_url is not None
        )

        def apply_replay_metrics(target_graph: WebKobeGraph) -> WebKobeGraph:
            if not replay_enabled:
                return target_graph
            target_graph.meta.update(replay_metrics)
            target_graph.meta["blocked_replay_node_ids"] = sorted(
                blocked_replay_node_ids
            )
            return target_graph

        for index in range(requested_steps):
            graph = await self.explorer.explore_one_step()
            apply_replay_metrics(graph)
            if index == 0:
                baseline_completed = max(graph.total_steps_completed - 1, 0)
                previous_completed = baseline_completed

            while (
                graph.total_steps_completed == previous_completed
                and graph.meta.get("last_step_kind") == "current_state_exhausted"
                and self.frontier_replay_runner is not None
                and self.start_url is not None
            ):
                frontier = select_frontier(
                    graph,
                    blocked_node_ids=blocked_replay_node_ids,
                    include_start=True,
                )
                if frontier is None:
                    stop_reason = "frontier_replay_exhausted"
                    break
                replay_metrics["replay_attempt_count"] += 1
                apply_replay_metrics(graph)
                replay_result = await self.frontier_replay_runner.replay(
                    frontier,
                    start_url=self.start_url,
                )
                replay_metrics["last_replay_reason"] = replay_result.reason
                if not replay_result.success:
                    replay_metrics["replay_failure_count"] += 1
                    if replay_result.reason in {
                        "entry_state_mismatch",
                        "target_state_mismatch",
                    }:
                        replay_metrics["replay_mismatch_count"] += 1
                    blocked_replay_node_ids.add(frontier.node_id)
                    apply_replay_metrics(graph)
                    continue
                replay_metrics["replay_success_count"] += 1
                next_graph = await self.explorer.explore_one_step()
                graph = apply_replay_metrics(next_graph)
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
            else:
                consecutive_unproductive_steps += 1
            graph.meta["consecutive_unproductive_steps"] = (
                consecutive_unproductive_steps
            )
            graph.meta["max_consecutive_unproductive_steps"] = (
                self.max_consecutive_unproductive_steps
            )
            apply_replay_metrics(graph)
            if self.step_checkpoint is not None:
                self.step_checkpoint(graph)
            if (
                self.max_consecutive_unproductive_steps is not None
                and consecutive_unproductive_steps
                >= self.max_consecutive_unproductive_steps
            ):
                stop_reason = "consecutive_unproductive_steps"
                break
            if self.terminal_condition is not None and self.terminal_condition(graph):
                stop_reason = "terminal_condition"
                break

        if graph is None:
            graph = WebKobeGraph(
                app="",
                start_node_id="",
                total_steps_completed=baseline_completed,
            )
        apply_replay_metrics(graph)

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
            ),
        )
