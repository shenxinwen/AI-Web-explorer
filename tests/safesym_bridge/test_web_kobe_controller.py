import pytest

from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.controller import (
    WebKobeExplorationController,
)
from ai_web_explorer.grounded_web.frontier_replay import ReplayResult
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    BusinessAffordance,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
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

def _frontier_graph() -> WebKobeGraph:
    def node(node_id: str, actions=()):
        return WebKobeNode(
            node_id=node_id,
            page_description=node_id,
            page_frame=PageFrame(
                page_id=node_id,
                page_type=node_id,
                url="https://fixture.test/shop",
                url_pattern="https://fixture.test/shop",
                title=node_id,
            ),
            state_schema={},
            last_state_snapshot={},
            business_affordances=[BusinessAffordance(action) for action in actions],
        )

    edge = WebKobeEdge(
        source_node_id="start",
        target_node_id="frontier",
        instruction="open frontier",
        action=BrowserAction("click", "#frontier", "open_frontier"),
        capability=None,
        target_observation="frontier",
        observed_delta=[],
        schema_delta={},
        execution_trace=ExecutionTrace(
            "click", "#frontier", "open_frontier", {}, "start", "frontier", True
        ),
        status="succeeded_with_navigation",
    )
    return WebKobeGraph(
        app="fake",
        start_node_id="start",
        total_steps_completed=0,
        nodes=[node("start"), node("frontier", ("inspect_frontier",))],
        edges=[edge],
        meta={
            "last_step_kind": "current_state_exhausted",
            "last_step_status": "unproductive",
        },
    )


class FakeExplorer:
    def __init__(self, graphs):
        self.graphs = list(graphs)
        self.calls = 0

    async def explore_one_step(self):
        graph = self.graphs[min(self.calls, len(self.graphs) - 1)]
        self.calls += 1
        return graph


class ReplayFakeExplorer(FakeExplorer):
    def __init__(
        self,
        graphs,
        replay_result,
        *,
        replay_targets=None,
        max_replay_calls=None,
    ):
        super().__init__(graphs)
        self.replay_result = replay_result
        self.replay_calls = []
        self.replay_targets = list(replay_targets or [])
        self.max_replay_calls = max_replay_calls

    async def replay(self, target, *, start_url):
        self.replay_calls.append((target.node_id, start_url))
        if (
            self.max_replay_calls is not None
            and len(self.replay_calls) > self.max_replay_calls
        ):
            raise AssertionError("same frontier replayed again")
        if self.replay_targets:
            return self.replay_targets.pop(0)
        return self.replay_result


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
async def test_controller_replays_frontier_only_when_enabled_then_resumes_exploration():
    explorer = ReplayFakeExplorer(
        [_frontier_graph(), _graph(completed=1)],
        ReplayResult(True, "frontier", None, "replay_succeeded", 1),
    )
    controller = WebKobeExplorationController(
        explorer,
        frontier_replay_runner=explorer,
        start_url="https://fixture.test/shop",
    )

    result = await controller.run(max_steps=1)

    assert explorer.replay_calls == [("frontier", "https://fixture.test/shop")]
    assert explorer.calls == 2
    assert result.summary.steps_completed == 1
    assert result.summary.stop_reason == "max_steps"
    assert result.graph.meta["replay_attempt_count"] == 1
    assert result.graph.meta["replay_success_count"] == 1
    assert result.graph.meta["replay_failure_count"] == 0


@pytest.mark.anyio
async def test_controller_blocks_failed_frontier_replay_and_stops_without_graph_edge():
    explorer = ReplayFakeExplorer(
        [_frontier_graph()],
        ReplayResult(
            False,
            "start",
            "start__open_frontier__frontier",
            "target_state_mismatch",
            0,
        ),
    )
    controller = WebKobeExplorationController(
        explorer,
        frontier_replay_runner=explorer,
        start_url="https://fixture.test/shop",
    )

    result = await controller.run(max_steps=3)

    assert explorer.replay_calls == [("frontier", "https://fixture.test/shop")]
    assert result.summary.stop_reason == "frontier_replay_exhausted"
    assert result.graph.meta["replay_attempt_count"] == 1
    assert result.graph.meta["replay_success_count"] == 0
    assert result.graph.meta["replay_failure_count"] == 1
    assert result.graph.meta["last_replay_reason"] == "target_state_mismatch"
    assert result.graph.meta["blocked_replay_node_ids"] == ["frontier"]


@pytest.mark.anyio
async def test_controller_blocks_frontier_when_successful_replay_has_no_followup_progress():
    explorer = ReplayFakeExplorer(
        [_frontier_graph()],
        ReplayResult(True, "frontier", None, "replay_succeeded", 1),
        max_replay_calls=1,
    )
    controller = WebKobeExplorationController(
        explorer,
        frontier_replay_runner=explorer,
        start_url="https://fixture.test/shop",
    )

    result = await controller.run(max_steps=1)

    assert explorer.replay_calls == [("frontier", "https://fixture.test/shop")]
    assert result.summary.stop_reason == "frontier_replay_exhausted"
    assert result.graph.meta["blocked_replay_node_ids"] == ["frontier"]


@pytest.mark.anyio
async def test_controller_moves_to_another_frontier_after_replay_has_no_progress():
    graph = _frontier_graph()
    graph.nodes.append(
        WebKobeNode(
            node_id="other",
            page_description="other",
            page_frame=PageFrame(
                page_id="other",
                page_type="other",
                url="https://fixture.test/shop",
                url_pattern="https://fixture.test/shop",
                title="other",
            ),
            state_schema={},
            last_state_snapshot={},
            business_affordances=[BusinessAffordance("inspect_other")],
        )
    )
    graph.edges.append(
        WebKobeEdge(
            source_node_id="start",
            target_node_id="other",
            instruction="open other",
            action=BrowserAction("click", "#other", "open_other"),
            capability=None,
            target_observation="other",
            observed_delta=[],
            schema_delta={},
            execution_trace=ExecutionTrace(
                "click", "#other", "open_other", {}, "start", "other", True
            ),
            status="succeeded_with_navigation",
        )
    )
    explorer = ReplayFakeExplorer(
        [graph],
        ReplayResult(True, "other", None, "replay_succeeded", 1),
        replay_targets=[
            ReplayResult(True, "frontier", None, "replay_succeeded", 1),
            ReplayResult(True, "other", None, "replay_succeeded", 1),
        ],
        max_replay_calls=2,
    )
    controller = WebKobeExplorationController(
        explorer,
        frontier_replay_runner=explorer,
        start_url="https://fixture.test/shop",
    )

    result = await controller.run(max_steps=1)

    assert [node_id for node_id, _ in explorer.replay_calls] == [
        "frontier",
        "other",
    ]
    assert result.summary.stop_reason == "frontier_replay_exhausted"
    assert result.graph.meta["blocked_replay_node_ids"] == ["frontier", "other"]


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


@pytest.mark.anyio
async def test_controller_checkpoints_each_completed_step():
    explorer = FakeExplorer([_graph(completed=1), _graph(completed=2)])
    checkpoints = []
    controller = WebKobeExplorationController(
        explorer,
        step_checkpoint=lambda graph: checkpoints.append(
            graph.total_steps_completed
        ),
    )

    await controller.run(max_steps=2)

    assert checkpoints == [1, 2]


@pytest.mark.anyio
async def test_controller_does_not_checkpoint_current_state_exhaustion_probe():
    explorer = FakeExplorer(
        [
            _graph(completed=1),
            _graph(completed=1, meta={"last_step_kind": "current_state_exhausted"}),
        ]
    )
    checkpoints = []
    result = await WebKobeExplorationController(
        explorer,
        step_checkpoint=lambda graph: checkpoints.append(
            graph.total_steps_completed
        ),
    ).run(max_steps=3)

    assert checkpoints == [1]
    assert result.summary.stop_reason == "current_state_exhausted"


@pytest.mark.anyio
async def test_controller_can_disable_unproductive_step_stop():
    explorer = FakeExplorer(
        [
            _graph(completed=index, meta={"last_step_graph_changed": False})
            for index in range(1, 5)
        ]
    )
    controller = WebKobeExplorationController(
        explorer,
        max_consecutive_unproductive_steps=None,
    )

    result = await controller.run(max_steps=4)

    assert explorer.calls == 4
    assert result.summary.stop_reason == "max_steps"
    assert result.summary.consecutive_unproductive_steps == 4
    assert result.summary.max_consecutive_unproductive_steps is None
