from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.frontier_replay import select_frontier
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    BusinessAffordance,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)


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
