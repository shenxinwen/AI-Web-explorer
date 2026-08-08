from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

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
class StepExplorer(Protocol):
    async def explore_one_step(self) -> WebKobeGraph: ...


@dataclass(frozen=True)
class WebKobeExplorationSummary:
    requested_steps: int
    steps_completed: int
    stop_reason: str
    node_count: int
    edge_count: int
    failed_edge_count: int
    consecutive_unproductive_steps: int = 0
    max_consecutive_unproductive_steps: int = 3


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
    max_consecutive_unproductive_steps: int = 3,
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
        max_consecutive_unproductive_steps: int = 3,
    ):
        self.explorer = explorer
        self.terminal_condition = terminal_condition
        self.max_consecutive_unproductive_steps = max(
            max_consecutive_unproductive_steps,
            1,
        )

    async def run(self, *, max_steps: int = 1) -> WebKobeExplorationResult:
        requested_steps = max(max_steps, 0)
        graph: WebKobeGraph | None = None
        baseline_completed = 0
        previous_completed = 0
        stop_reason = "max_steps"
        consecutive_unproductive_steps = 0

        for index in range(requested_steps):
            graph = await self.explorer.explore_one_step()
            if index == 0:
                baseline_completed = max(graph.total_steps_completed - 1, 0)
                previous_completed = baseline_completed

            if graph.total_steps_completed == previous_completed:
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
            if (
                consecutive_unproductive_steps
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
