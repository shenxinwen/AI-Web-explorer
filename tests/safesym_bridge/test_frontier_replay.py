import pytest
import json

from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.explorer import WebKobeExplorer
from ai_web_explorer.grounded_web.frontier_replay import (
    FrontierReplayRunner,
    ReplayStep,
    select_frontier,
)
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    BusinessAffordance,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.semantic_assistor import DeterministicSemanticAssistor
from ai_web_explorer.safesym_bridge.surface_pddl import compile_surface_domain
from ai_web_explorer.safesym_bridge.trace_pddl import compile_trace_domain
from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
    load_web_kobe_graph_json,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _node(node_id: str, *actions: str) -> WebKobeNode:
    return WebKobeNode(
        node_id=node_id,
        page_description=node_id,
        page_frame=PageFrame(
            page_id=node_id,
            page_type=node_id,
            url=f"https://fixture.test/{node_id}",
            url_pattern=f"https://fixture.test/{node_id}",
            title=node_id,
        ),
        state_schema={},
        last_state_snapshot={},
        business_affordances=[BusinessAffordance(action) for action in actions],
    )


def _edge(source: str, target: str, action_id: str, *, success: bool = True) -> WebKobeEdge:
    return WebKobeEdge(
        source_node_id=source,
        target_node_id=target,
        instruction=action_id,
        action=BrowserAction("click", f"#{action_id}", action_id),
        capability=None,
        target_observation=target,
        observed_delta=[],
        schema_delta={},
        execution_trace=ExecutionTrace(
            "click",
            f"#{action_id}",
            action_id,
            {},
            source,
            target,
            success,
        ),
        status="succeeded_with_navigation" if success else "failed_execution",
    )


def test_select_frontier_uses_shortest_reachable_path_deterministically():
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=3,
        nodes=[
            _node("start", "open_a", "open_b"),
            _node("a", "open_deep"),
            _node("b", "inspect_b"),
            _node("deep", "continue_deep"),
        ],
        edges=[
            _edge("start", "a", "open_a"),
            _edge("start", "b", "open_b"),
            _edge("a", "deep", "open_deep"),
        ],
    )

    target = select_frontier(graph)

    assert target is not None
    assert target.node_id == "b"
    assert [step.edge_id for step in target.path] == [
        "start__open_b__b",
    ]
    assert target.untried_action_ids == ("inspect_b",)


def test_select_frontier_does_not_use_failed_paths_or_blocked_frontiers():
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=2,
        nodes=[
            _node("start", "open_bad"),
            _node("bad", "unsafe_action"),
            _node("good", "inspect_good"),
        ],
        edges=[
            _edge("start", "bad", "open_bad", success=False),
        ],
    )

    assert select_frontier(graph) is None

    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=1,
        nodes=[_node("start", "open_good"), _node("good", "inspect_good")],
        edges=[_edge("start", "good", "open_good")],
    )
    assert select_frontier(graph, blocked_node_ids={"good"}) is None


def test_select_frontier_returns_none_when_all_candidates_are_exhausted():
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=1,
        nodes=[_node("start", "open_good"), _node("good", "inspect_good")],
        edges=[
            _edge("start", "good", "open_good"),
            _edge("good", "good", "inspect_good"),
        ],
    )

    assert select_frontier(graph) is None


def test_select_frontier_does_not_select_start_by_default():
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=0,
        nodes=[_node("start", "start_action")],
        edges=[],
    )

    assert select_frontier(graph) is None
    assert select_frontier(graph, include_start=True).node_id == "start"


def test_select_frontier_uses_one_global_bfs_parent_per_node_in_cycles():
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=3,
        nodes=[
            _node("start"),
            _node("left"),
            _node("right"),
            _node("deep", "continue_deep"),
        ],
        edges=[
            _edge("start", "left", "open_left"),
            _edge("start", "right", "open_right"),
            _edge("left", "right", "cycle_to_right"),
            _edge("right", "deep", "open_deep"),
        ],
    )

    target = select_frontier(graph)

    assert target is not None
    assert target.node_id == "deep"
    assert [step.edge_id for step in target.path] == [
        "start__open_right__right",
        "right__open_deep__deep",
    ]


def test_select_frontier_excludes_unstable_paths_but_uses_stable_detour():
    unstable_edge = _edge("start", "bad", "open_bad")
    unstable_edge.execution_trace.metadata["replay_validation_status"] = "unstable"
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=3,
        nodes=[
            _node("start"),
            _node("bad"),
            _node("detour"),
            _node("frontier", "inspect_frontier"),
        ],
        edges=[
            unstable_edge,
            _edge("bad", "frontier", "continue_bad"),
        ],
    )

    assert select_frontier(graph) is None

    graph.edges.extend(
        [
            _edge("start", "detour", "open_detour"),
            _edge("detour", "frontier", "continue_detour"),
        ]
    )
    target = select_frontier(graph)

    assert target is not None
    assert target.node_id == "frontier"
    assert [step.edge_id for step in target.path] == [
        "start__open_detour__detour",
        "detour__continue_detour__frontier",
    ]


class _ReplayAdapter:
    app_name = "fixture"

    def __init__(self, states, *, failing_actions=()):
        self.states = list(states)
        self.index = 0
        self.reset_calls = []
        self.executed = []
        self.failing_actions = set(failing_actions)
        self.last_execution_error = None

    async def reset_to(self, url):
        self.reset_calls.append(url)
        self.index = 0
        return True

    async def observe_state(self):
        return self.states[self.index]

    async def list_interactables(self, state):
        return []

    async def execute(self, action):
        self.executed.append(action.semantic_id)
        if action.semantic_id in self.failing_actions:
            self.last_execution_error = "replay_failed"
            return False
        self.index = min(self.index + 1, len(self.states) - 1)
        return True


def _replay_node(node_id: str, state: str) -> WebKobeNode:
    return WebKobeNode(
        node_id=node_id,
        page_description=node_id,
        page_frame=PageFrame(
            page_id=state,
            page_type=state,
            url="https://fixture.test/shop",
            url_pattern="https://fixture.test/shop",
            title=state,
        ),
        state_schema={},
        last_state_snapshot={"surface": state},
    )


def _replay_step(source: str, target: str, action_id: str) -> ReplayStep:
    edge = _edge(source, target, action_id)
    return ReplayStep(
        edge_id=edge.edge_id,
        source_node_id=source,
        target_node_id=target,
        edge=edge,
    )


def _replay_explorer(adapter):
    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fixture"),
        business_profile=None,
    )
    explorer.manager.identify_or_add_node(_replay_node("start", "start"))
    explorer.manager.identify_or_add_node(_replay_node("target", "target"))
    explorer._start_node_id = "start"
    explorer._current_node_id = "start"
    return explorer


@pytest.mark.anyio
async def test_frontier_replay_resets_executes_and_validates_without_graph_edges():
    adapter = _ReplayAdapter(
        [
            StateSnapshot("start", "https://fixture.test/shop", "start", {"surface": "start"}),
            StateSnapshot("target", "https://fixture.test/shop", "target", {"surface": "target"}),
        ]
    )
    explorer = _replay_explorer(adapter)
    target = type(
        "Target",
        (),
        {
            "node_id": "target",
            "path": (_replay_step("start", "target", "open_target"),),
        },
    )()
    initial_edge_count = len(explorer.manager.to_graph().edges)

    result = await FrontierReplayRunner(explorer).replay(
        target,
        start_url="https://fixture.test/shop",
    )

    assert result.success is True
    assert result.reached_node_id == "target"
    assert result.completed_steps == 1
    assert adapter.reset_calls == ["https://fixture.test/shop"]
    assert adapter.executed == ["open_target"]
    assert len(explorer.manager.to_graph().edges) == initial_edge_count


@pytest.mark.anyio
async def test_frontier_replay_fails_closed_on_target_mismatch():
    adapter = _ReplayAdapter(
        [
            StateSnapshot("start", "https://fixture.test/shop", "start", {"surface": "start"}),
            StateSnapshot("wrong", "https://fixture.test/shop", "wrong", {"surface": "wrong"}),
        ]
    )
    explorer = _replay_explorer(adapter)
    target = type(
        "Target",
        (),
        {
            "node_id": "target",
            "path": (_replay_step("start", "target", "open_target"),),
        },
    )()

    result = await FrontierReplayRunner(explorer).replay(
        target,
        start_url="https://fixture.test/shop",
    )

    assert result.success is False
    assert result.reason == "target_state_mismatch"
    assert result.failed_edge_id == "start__open_target__target"
    assert result.completed_steps == 0
    assert len(explorer.manager.to_graph().edges) == 0


@pytest.mark.anyio
async def test_frontier_replay_stops_on_action_failure_without_observation():
    adapter = _ReplayAdapter(
        [StateSnapshot("start", "https://fixture.test/shop", "start", {"surface": "start"})],
        failing_actions={"open_target"},
    )
    explorer = _replay_explorer(adapter)
    target = type(
        "Target",
        (),
        {
            "node_id": "target",
            "path": (_replay_step("start", "target", "open_target"),),
        },
    )()

    result = await FrontierReplayRunner(explorer).replay(
        target,
        start_url="https://fixture.test/shop",
    )

    assert result.success is False
    assert result.reason == "replay_action_failed"
    assert result.completed_steps == 0


@pytest.mark.anyio
async def test_replay_mismatch_marks_existing_edge_unstable_across_graph_roundtrip(
    tmp_path,
):
    adapter = _ReplayAdapter(
        [
            StateSnapshot("start", "https://fixture.test/shop", "start", {"surface": "start"}),
            StateSnapshot("wrong", "https://fixture.test/shop", "wrong", {"surface": "wrong"}),
        ]
    )
    explorer = _replay_explorer(adapter)
    target = type(
        "Target",
        (),
        {
            "node_id": "target",
            "path": (_replay_step("start", "target", "open_target"),),
        },
    )()
    explorer.manager.add_edge(target.path[0].edge)

    result = await FrontierReplayRunner(explorer).replay(
        target,
        start_url="https://fixture.test/shop",
    )

    assert result.reason == "target_state_mismatch"
    current_edge = explorer.manager.to_graph().edges[0]
    assert current_edge.execution_trace.metadata["replay_validation_status"] == (
        "unstable"
    )

    graph_path = tmp_path / "graph.json"
    graph_path.write_text(
        json.dumps(explorer.manager.to_graph().to_dict()),
        encoding="utf-8",
    )
    restored = load_web_kobe_graph_json(graph_path)
    restored_edge = restored.edges[0]
    assert restored_edge.execution_trace.metadata["replay_validation_status"] == (
        "unstable"
    )
    assert "open_target" not in compile_surface_domain(restored).domain
    assert "open_target" in compile_trace_domain(restored).domain
