from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ai_web_explorer.grounded_web.graph import WebKobeGraph


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


@dataclass(frozen=True)
class WebKobeExplorationResult:
    graph: WebKobeGraph
    summary: WebKobeExplorationSummary


def _failed_edge_count(graph: WebKobeGraph) -> int:
    return sum(1 for edge in graph.edges if edge.status != "verified")


def _summary(
    graph: WebKobeGraph,
    *,
    requested_steps: int,
    baseline_completed: int,
    stop_reason: str,
) -> WebKobeExplorationSummary:
    return WebKobeExplorationSummary(
        requested_steps=requested_steps,
        steps_completed=max(graph.total_steps_completed - baseline_completed, 0),
        stop_reason=stop_reason,
        node_count=len(graph.nodes),
        edge_count=len(graph.edges),
        failed_edge_count=_failed_edge_count(graph),
    )


class WebKobeExplorationController:
    def __init__(self, explorer: StepExplorer):
        self.explorer = explorer

    async def run(self, *, max_steps: int = 1) -> WebKobeExplorationResult:
        requested_steps = max(max_steps, 0)
        graph: WebKobeGraph | None = None
        baseline_completed = 0
        previous_completed = 0
        stop_reason = "max_steps"

        for index in range(requested_steps):
            graph = await self.explorer.explore_one_step()
            if index == 0:
                baseline_completed = max(graph.total_steps_completed - 1, 0)
                previous_completed = baseline_completed

            if graph.total_steps_completed == previous_completed:
                stop_reason = "no_available_action"
                break

            previous_completed = graph.total_steps_completed
            if graph.edges and graph.edges[-1].status != "verified":
                stop_reason = "failed_action"
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
            ),
        )
