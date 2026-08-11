from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.safesym_bridge.surface_pddl import (
    compile_surface_domain,
    compile_surface_problem,
)


def _node(node_id: str, label: str) -> WebKobeNode:
    return WebKobeNode(
        node_id=node_id,
        page_description=label,
        page_frame=PageFrame(
            page_id=node_id,
            page_type=label,
            url="https://fixture.test/shop",
            url_pattern="https://fixture.test/shop",
            title=label,
        ),
        state_schema={},
        last_state_snapshot={},
        node_label=label,
    )


def _edge(source: str, target: str, action: str, *, success: bool = True) -> WebKobeEdge:
    return WebKobeEdge(
        source_node_id=source,
        target_node_id=target,
        instruction=action,
        action=BrowserAction("click", f"#{action}", action),
        capability=None,
        target_observation=target,
        observed_delta=[],
        schema_delta={},
        execution_trace=ExecutionTrace(
            "click", f"#{action}", action, {}, source, target, success
        ),
        status="succeeded_with_navigation" if success else "failed_execution",
    )


def surface_graph_fixture() -> WebKobeGraph:
    return WebKobeGraph(
        app="fixture",
        start_node_id="shopping",
        total_steps_completed=4,
        nodes=[
            _node("shopping", "shopping"),
            _node("product", "product_detail"),
        ],
        edges=[
            _edge("shopping", "shopping", "filter"),
            _edge("shopping", "shopping", "clear"),
            _edge("shopping", "shopping", "sort"),
            _edge("shopping", "product", "open_product"),
            _edge("product", "shopping", "failed_action", success=False),
        ],
    )


def _action_block(domain: str, action_name: str) -> str:
    start = domain.index(f"(:action {action_name}")
    end = domain.index("\n  )", start) + len("\n  )")
    return domain[start:end]


def test_surface_domain_uses_observed_sources_not_trace_order():
    projection = compile_surface_domain(surface_graph_fixture())

    assert ":precondition (and (at shopping))" in _action_block(
        projection.domain, "filter_on_shopping"
    )
    assert ":precondition (and (at shopping))" in _action_block(
        projection.domain, "sort_on_shopping"
    )
    assert "checkpoint" not in projection.domain
    assert "transition_filter_on_shopping" in projection.domain
    assert "failed_action" not in projection.domain


def test_surface_domain_keeps_same_surface_and_moves_cross_surface():
    domain = compile_surface_domain(surface_graph_fixture()).domain

    same_surface = _action_block(domain, "filter_on_shopping")
    assert "(executed transition_filter_on_shopping)" in same_surface
    assert "(not (at shopping))" not in same_surface

    cross_surface = _action_block(domain, "open_product_from_shopping")
    assert "(not (at shopping))" in cross_surface
    assert "(at product_detail)" in cross_surface
    assert "(executed transition_open_product_from_shopping)" in cross_surface


def test_surface_problem_uses_graph_start_and_reachable_goal():
    result = compile_surface_problem(
        surface_graph_fixture(),
        goal_node_id="product",
    )

    assert result.start_surface == "shopping"
    assert result.goal_surface == "product_detail"
    assert "(:domain web_kobe_surface)" in result.problem
    assert "(:init (at shopping))" in result.problem
    assert "(:goal (at product_detail))" in result.problem
