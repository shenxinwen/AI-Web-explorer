import pytest

from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace
from ai_web_explorer.grounded_web.controller import (
    WebKobeExplorationController,
)
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    WebKobeEdge,
    WebKobeGraph,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _graph(
    *,
    completed: int,
    edge_status: str = "verified",
    execution_success: bool | None = None,
    meta: dict | None = None,
) -> WebKobeGraph:
    edges = []
    if completed:
        edges.append(
            WebKobeEdge(
                source_node_id="state",
                target_node_id="state",
                instruction="Click action",
                action=BrowserAction("click", "#action", f"action_{completed}"),
                capability=None,
                target_observation="state page",
                observed_delta=[],
                schema_delta=None,
                execution_trace=ExecutionTrace(
                    concrete_action_kind="click",
                    concrete_locator="#action",
                    concrete_target_sample=f"action_{completed}",
                    input_values_used={},
                    before_observation_id="state",
                    after_observation_id="state",
                    success=(
                        edge_status == "verified"
                        if execution_success is None
                        else execution_success
                    ),
                    error=(
                        None
                        if (
                            edge_status == "verified"
                            if execution_success is None
                            else execution_success
                        )
                        else "failed"
                    ),
                ),
                status=edge_status,
            )
        )
    graph_meta = dict(meta or {})
    graph_meta.setdefault("last_step_graph_changed", completed > 0)
    return WebKobeGraph(
        app="fake",
        start_node_id="state",
        total_steps_completed=completed,
        nodes=[],
        edges=edges,
        meta=graph_meta,
    )


class FakeExplorer:
    def __init__(self, graphs):
        self.graphs = list(graphs)
        self.calls = 0

    async def explore_one_step(self):
        graph = self.graphs[min(self.calls, len(self.graphs) - 1)]
        self.calls += 1
        return graph


@pytest.mark.anyio
async def test_controller_runs_until_max_steps():
    explorer = FakeExplorer(
        [
            _graph(completed=1),
            _graph(completed=2),
        ]
    )
    controller = WebKobeExplorationController(explorer)

    result = await controller.run(max_steps=2)

    assert explorer.calls == 2
    assert result.graph.total_steps_completed == 2
    assert result.summary.requested_steps == 2
    assert result.summary.steps_completed == 2
    assert result.summary.stop_reason == "max_steps"
    assert result.summary.edge_count == 1
    assert result.summary.failed_edge_count == 0


@pytest.mark.anyio
async def test_controller_treats_explorer_success_status_as_success():
    explorer = FakeExplorer(
        [
            _graph(completed=1, edge_status="succeeded_with_observed_change"),
            _graph(completed=2, edge_status="succeeded_with_navigation"),
            _graph(completed=3, edge_status="succeeded"),
        ]
    )
    controller = WebKobeExplorationController(explorer)

    result = await controller.run(max_steps=3)

    assert explorer.calls == 3
    assert result.summary.steps_completed == 3
    assert result.summary.stop_reason == "max_steps"
    assert result.summary.failed_edge_count == 0


@pytest.mark.anyio
async def test_controller_continues_after_no_observed_change():
    explorer = FakeExplorer(
        [
            _graph(
                completed=1,
                edge_status="no_observed_change",
                execution_success=True,
                meta={"last_step_graph_changed": False},
            ),
            _graph(completed=2),
        ]
    )
    controller = WebKobeExplorationController(explorer)

    result = await controller.run(max_steps=2)

    assert explorer.calls == 2
    assert result.graph.total_steps_completed == 2
    assert result.summary.steps_completed == 2
    assert result.summary.stop_reason == "max_steps"
    assert result.summary.failed_edge_count == 0


@pytest.mark.anyio
async def test_controller_stops_when_no_action_is_available():
    explorer = FakeExplorer(
        [
            _graph(completed=0),
        ]
    )
    controller = WebKobeExplorationController(explorer)

    result = await controller.run(max_steps=3)

    assert explorer.calls == 1
    assert result.graph.total_steps_completed == 0
    assert result.summary.steps_completed == 0
    assert result.summary.stop_reason == "no_available_action"


@pytest.mark.anyio
async def test_controller_reports_current_state_exhausted():
    explorer = FakeExplorer(
        [
            _graph(
                completed=0,
                meta={
                    "last_step_kind": "current_state_exhausted",
                    "last_step_status": "unproductive",
                },
            )
        ]
    )
    result = await WebKobeExplorationController(explorer).run(max_steps=3)

    assert explorer.calls == 1
    assert result.summary.stop_reason == "current_state_exhausted"


@pytest.mark.anyio
async def test_controller_continues_after_single_failed_action():
    explorer = FakeExplorer(
        [
            _graph(completed=1, edge_status="failed_execution"),
            _graph(completed=2),
        ]
    )
    controller = WebKobeExplorationController(explorer)

    result = await controller.run(max_steps=2)

    assert explorer.calls == 2
    assert result.graph.total_steps_completed == 2
    assert result.summary.steps_completed == 2
    assert result.summary.stop_reason == "max_steps"


@pytest.mark.anyio
async def test_controller_stops_after_consecutive_unproductive_steps():
    explorer = FakeExplorer(
        [
            _graph(
                completed=1,
                edge_status="failed_execution",
                meta={"last_step_graph_changed": False},
            ),
            _graph(
                completed=2,
                edge_status="no_observed_change",
                meta={"last_step_graph_changed": False},
            ),
            _graph(
                completed=3,
                edge_status="failed_execution",
                meta={"last_step_graph_changed": False},
            ),
            _graph(completed=4),
        ]
    )
    controller = WebKobeExplorationController(
        explorer,
        max_consecutive_unproductive_steps=3,
    )

    result = await controller.run(max_steps=5)

    assert explorer.calls == 3
    assert result.graph.total_steps_completed == 3
    assert result.summary.steps_completed == 3
    assert result.summary.stop_reason == "consecutive_unproductive_steps"
    assert result.summary.failed_edge_count == 1
    assert result.summary.consecutive_unproductive_steps == 3
    assert result.summary.max_consecutive_unproductive_steps == 3
    assert result.graph.meta["consecutive_unproductive_steps"] == 3


@pytest.mark.anyio
async def test_controller_stops_after_repeated_steps_without_new_graph_information():
    explorer = FakeExplorer(
        [
            _graph(completed=1, meta={"last_step_graph_changed": True}),
            _graph(completed=2, meta={"last_step_graph_changed": False}),
            _graph(completed=3, meta={"last_step_graph_changed": False}),
            _graph(completed=4, meta={"last_step_graph_changed": False}),
        ]
    )
    controller = WebKobeExplorationController(
        explorer,
        max_consecutive_unproductive_steps=3,
    )

    result = await controller.run(max_steps=10)

    assert explorer.calls == 4
    assert result.summary.stop_reason == "consecutive_unproductive_steps"
    assert result.summary.consecutive_unproductive_steps == 3


@pytest.mark.anyio
async def test_controller_stops_when_terminal_condition_matches():
    explorer = FakeExplorer(
        [
            _graph(completed=1),
            _graph(completed=2),
        ]
    )
    controller = WebKobeExplorationController(
        explorer,
        terminal_condition=lambda graph: graph.total_steps_completed >= 1,
    )

    result = await controller.run(max_steps=3)

    assert explorer.calls == 1
    assert result.graph.total_steps_completed == 1
    assert result.summary.steps_completed == 1
    assert result.summary.stop_reason == "terminal_condition"
